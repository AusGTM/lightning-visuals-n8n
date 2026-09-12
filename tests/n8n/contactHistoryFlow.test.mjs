// tests/n8n/contactHistoryFlow.test.mjs
//
// Phase 72 Plan 04 Task 3 (D-72-06/07): drives the COMMITTED
// n8n/wf_contact_ingest_cloud.json through the walker to prove the ingest lane's new
// "HubSpot Contact History" hop actually feeds the recency gate a genuine "existing
// value's own clock" — the mechanism CLAUDE.md T-72-02 requires (no third timestamp
// source: only the run's own dispatch clock and HubSpot's own propertiesWithHistory
// timestamp are legitimate).
//
// `source_by_field` is a REQUEST-level multipart field (CLAUDE.md §13.0.2) — only
// item[0]'s `body` is read by "Set Config Fields", then broadcast onto every row by the
// "Source By Field Broadcast" combineAll merge. A field's own history timestamp only
// wins a recency comparison when that SAME batch's source_by_field names it
// provider-sourced (D-72-07) — which is why "stale but unnamed" and "stale and named"
// are separate batches/tests here, not two rows in one batch.
//
// Same ARM()/loadArmedWorkflow() idiom as ingestCarryMerge.test.mjs — the committed JSON
// ships disarmed; arming mutates the LOADED jsCode strings in memory, never the file on
// disk. Create stays disabled throughout (only "HubSpot Update Write Gate" and
// "Associate Lane Sentinel" are armed) so a net_new row lands at review with no need to
// stub HubSpot Create/Associate for it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

const DOMAIN = "contacthistory.example";
const COMPANY_ID = "9800001";

function loadArmedWorkflow({ testRecordIds = "" } = {}) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  // "Decide Action" no longer bakes the write-safety allowlist and the association has
  // no gate of its own (D-70-15) — "HubSpot Update Write Gate" is the single arming
  // surface for the update lane; "Associate Lane Sentinel" duplicates its predicate
  // purely for Merge plumbing and must be armed identically (real arming tool
  // n8n_arming.set_write_safety rewrites both).
  const armNames = ["HubSpot Update Write Gate", "Associate Lane Sentinel"];
  for (const name of armNames) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `node present: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace(
        'const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'
      )
      .replace('const TEST_RECORD_IDS = "";', `const TEST_RECORD_IDS = "${testRecordIds}";`);
  }
  return wf;
}

function daysAgoIso(days) {
  return new Date(Date.now() - days * 86400000).toISOString();
}

function domainStubs() {
  return {
    "HubSpot Company Search by Domain": (items) => items.map(() => (
      { results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }
    )),
    "HubSpot Company Search by Name": (items) => items.map(() => ({ results: [] })),
    "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
  };
}

// --- Static: the propertiesWithHistory query is derived, never a literal string --------

test("HubSpot Contact History's query is derived from refreshable_contact_props() at build time", () => {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const node = wf.nodes.find((n) => n.name === "HubSpot Contact History");
  assert.ok(node, "HubSpot Contact History node must exist");
  assert.match(node.parameters.url, /propertiesWithHistory=jobtitle/);
  assert.equal(node.onError, "continueRegularOutput",
    "a non-200 must become an item, not fail the batch");
});

// --- Behavior: mixed batch — one matched (history hop) + one net_new (no hop) ----------

const MATCHED_EMAIL = "matched@" + DOMAIN;
const MATCHED_CONTACT_ID = "111";
const NETNEW_EMAIL = "netnew@" + DOMAIN;

test("mixed batch: exactly one GET for the matched row, none for net_new, no Merge starves, and the timestamp reaches Merge Contacts as historyByField.jobtitle", () => {
  const wf = loadArmedWorkflow({ testRecordIds: MATCHED_CONTACT_ID });
  const staleTimestamp = daysAgoIso(200);
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      {
        body: { source_by_field: { jobtitle: "apollo" } },
        email: MATCHED_EMAIL, firstname: "Matched", lastname: "Row", company: "Contact History Co",
        jobtitle: "New Title",
      },
      { email: NETNEW_EMAIL, firstname: "Net", lastname: "New", company: "Contact History Co",
        jobtitle: "Some Title" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{
        results: [
          { email: MATCHED_EMAIL, status: "VALID" },
          { email: NETNEW_EMAIL, status: "VALID" },
        ],
      }],
      "HubSpot Search by Email": [
        { results: [{ id: MATCHED_CONTACT_ID, properties: { email: MATCHED_EMAIL, jobtitle: "Old Title" } }] },
        { results: [] },
      ],
      "HubSpot Contact History": [
        { propertiesWithHistory: { jobtitle: [{ value: "Old Title", timestamp: staleTimestamp }] } },
      ],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      ...domainStubs(),
    },
  });

  assert.deepEqual(starvedWithData(trace), [], "no Merge may lose a row on this batch");

  const historyRows = nodeItems(runData, "HubSpot Contact History");
  assert.equal(historyRows.length, 1, "exactly one GET — the matched row only");

  const merged = nodeItems(runData, "Merge Contacts");
  const byEmail = Object.fromEntries(merged.map((r) => [r.email, r]));

  assert.equal(byEmail[MATCHED_EMAIL].historyByField.jobtitle, staleTimestamp,
    "the matched row's own history timestamp must reach Merge Contacts as historyByField.jobtitle");
  assert.equal(byEmail[NETNEW_EMAIL].historyByField, undefined,
    "a net_new row never reaches the history hop and carries no historyByField at all");

  const jobtitleDecision = (email) =>
    (byEmail[email].merge.decisions || []).find((d) => d.field === "jobtitle");
  assert.equal(jobtitleDecision(MATCHED_EMAIL).decision, "promote",
    "stale existing value + provider-sourced candidate (source_by_field names jobtitle) -> promote");
  assert.equal(jobtitleDecision(NETNEW_EMAIL).decision, "promote",
    "net_new: blank existing value always promotes regardless of freshness");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(updateRows.length, 1);
  assert.equal(updateRows[0].properties.jobtitle, "New Title",
    "the promoted value must land in the update body");
});

// --- Behavior: a matched row whose history is FRESH must not promote -------------------

test("a matched row whose jobtitle history is 30 days old (fresh) does not update jobtitle", () => {
  const wf = loadArmedWorkflow({ testRecordIds: MATCHED_CONTACT_ID });
  const freshTimestamp = daysAgoIso(30);
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{
      body: { source_by_field: { jobtitle: "apollo" } },
      email: MATCHED_EMAIL, firstname: "Matched", lastname: "Row", company: "Contact History Co",
      jobtitle: "New Title",
    }],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: MATCHED_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [
        { results: [{ id: MATCHED_CONTACT_ID, properties: { email: MATCHED_EMAIL, jobtitle: "Old Title" } }] },
      ],
      "HubSpot Contact History": [
        { propertiesWithHistory: { jobtitle: [{ value: "Old Title", timestamp: freshTimestamp }] } },
      ],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      ...domainStubs(),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const merged = nodeItems(runData, "Merge Contacts");
  const decision = (merged[0].merge.decisions || []).find((d) => d.field === "jobtitle");
  assert.equal(decision.decision, "needs_review",
    "a fresh existing value keeps the pre-72 refusal reason — recency has not passed TTL");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(
    Object.prototype.hasOwnProperty.call(updateRows[0].properties, "jobtitle"),
    false,
    "a needs_review field must never reach the update body"
  );
});

// --- Behavior: same stale row, but source_by_field does NOT name jobtitle -------------

test("the SAME stale row on a batch whose source_by_field does not name jobtitle does not update jobtitle (conservative direction)", () => {
  const wf = loadArmedWorkflow({ testRecordIds: MATCHED_CONTACT_ID });
  const staleTimestamp = daysAgoIso(200);
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{
      // No `body.source_by_field` naming jobtitle at all -- resolves to the flat
      // csv source, which carries no observation time and can never win (D-72-07).
      email: MATCHED_EMAIL, firstname: "Matched", lastname: "Row", company: "Contact History Co",
      jobtitle: "New Title",
    }],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: MATCHED_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [
        { results: [{ id: MATCHED_CONTACT_ID, properties: { email: MATCHED_EMAIL, jobtitle: "Old Title" } }] },
      ],
      "HubSpot Contact History": [
        { propertiesWithHistory: { jobtitle: [{ value: "Old Title", timestamp: staleTimestamp }] } },
      ],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      ...domainStubs(),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const merged = nodeItems(runData, "Merge Contacts");
  assert.equal(merged[0].historyByField.jobtitle, staleTimestamp,
    "the history hop itself still ran and stamped the timestamp -- what refuses is the source map, not a missing GET");
  const decision = (merged[0].merge.decisions || []).find((d) => d.field === "jobtitle");
  assert.equal(decision.decision, "needs_review",
    "an unnamed field carries no observation time and can never win the recency comparison, however stale the existing value");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(
    Object.prototype.hasOwnProperty.call(updateRows[0].properties, "jobtitle"),
    false
  );
});

// --- Behavior: a failed/non-200 history response leaves historyByField absent ----------

test("a failed HubSpot Contact History response leaves historyByField absent and falls back to unknown freshness", () => {
  const wf = loadArmedWorkflow({ testRecordIds: MATCHED_CONTACT_ID });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{
      body: { source_by_field: { jobtitle: "apollo" } },
      email: MATCHED_EMAIL, firstname: "Matched", lastname: "Row", company: "Contact History Co",
      jobtitle: "New Title",
    }],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: MATCHED_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [
        { results: [{ id: MATCHED_CONTACT_ID, properties: { email: MATCHED_EMAIL, jobtitle: "Old Title" } }] },
      ],
      // onError: continueRegularOutput turns a non-200 into an error-shaped item rather
      // than failing the batch -- "Adapt Contact History" treats any `error` key as no
      // history at all, never a wrong timestamp.
      "HubSpot Contact History": [{ error: "Not Found", status: "error" }],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      ...domainStubs(),
    },
  });

  assert.deepEqual(starvedWithData(trace), [], "a failed history GET must not starve the Merge");

  const merged = nodeItems(runData, "Merge Contacts");
  assert.equal(merged[0].historyByField.jobtitle, undefined,
    "a failed response must not stamp a wrong timestamp");
  const decision = (merged[0].merge.decisions || []).find((d) => d.field === "jobtitle");
  assert.equal(decision.decision, "needs_review",
    "unknown freshness -- the pre-72 outcome -- is the safe fallback for a failed history fetch");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(
    Object.prototype.hasOwnProperty.call(updateRows[0].properties, "jobtitle"),
    false
  );
});
