// tests/n8n/ingestMixedBatch.test.mjs
//
// Phase 70 Plan 07 Task 1 (D-70-17) — THE acceptance test for the ingest lane: one mixed
// batch spanning 2 identity lanes x 2 actions, asserting every input row returns exactly
// once from the write node's own output. Drives the COMMITTED
// n8n/wf_contact_ingest_cloud.json through tests/n8n/lib/walkWorkflow.mjs.
//
// The two identity lanes on THIS lane are the two company-resolution keys CLAUDE.md
// §13.0.1 names — exact email-domain match and exact company-name match. (Contact
// identity itself is email-only here: this lane has no contact name/LinkedIn search, so
// a name-only row can never reach an `update`. See ingestCarryMerge.test.mjs's own
// 7-HTTP-hop list.) The two actions are `update` (email resolves an existing contact)
// and the create path (email resolves nothing).
//
// This mirrors the shape of the real supervised batch in
// .planning/uat/UAT-autonomous-batch-2026-09-09.md — Natalie (company resolved by
// domain, written) alongside Barry (company absent by name, held) — rather than an
// invented shape.
//
// D-70-18, recorded by the operator in 70-CONTEXT.md: GREEN on the refactored JSON is
// enough here; no historical RED was taken against the pre-Phase-70 JSON. The evidence
// that this instrument can SEE the defect class (an F5-style collapse, a Merge input
// that never fires, a second Respond) lives in tests/n8n/walkWorkflow.test.mjs, which is
// the walker's own RED.
//
// As in ingestCarryMerge.test.mjs, the committed JSON ships DISARMED; the armed cases
// mutate the LOADED jsCode strings in memory and never the file on disk.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

// --- the 2x2 batch ------------------------------------------------------------------
// lane          | action  | row
// domain-match  | update  | R_DOMAIN_UPDATE  (email resolves contact 111)
// domain-match  | create  | R_DOMAIN_CREATE  (email resolves nothing)
// name-match    | update  | R_NAME_UPDATE    (email resolves contact 444)
// name-match    | create  | R_NAME_CREATE    (email resolves nothing)
const R_DOMAIN_UPDATE = "domain-update@acme-domain.example";
const R_DOMAIN_CREATE = "domain-create@acme-domain.example";
const R_NAME_UPDATE = "name-update@no-domain-match.example";
const R_NAME_CREATE = "name-create@no-domain-match.example";

const CONTACT_DOMAIN_UPDATE = "111";
const CONTACT_NAME_UPDATE = "444";
const COMPANY_BY_DOMAIN = "9001";
const COMPANY_BY_NAME = "9002";
const NAME_COMPANY = "Devonport Racing Club";

// `TEST_RECORD_IDS` must name every contact the batch is permitted to write.
const ARMED_ALLOWLIST = `${CONTACT_DOMAIN_UPDATE},${CONTACT_NAME_UPDATE}`;

// Every node on this lane that DECLARES a write flag — the two gates AND
// "Associate Lane Sentinel", which duplicates the gate predicate for Merge plumbing.
// The real arming tool (n8n_arming.set_write_safety) rewrites all of them; arming a
// subset here would be a test artifact, not a deployable state, and would reproduce the
// dropped-association bug on a real batch.
const ARMING_NODES = ["HubSpot Update Write Gate", "HubSpot Create Write Gate",
  "Associate Lane Sentinel"];

function loadWorkflow({ armed = false } = {}) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  if (!armed) return wf;
  for (const name of ARMING_NODES) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `node present: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const TEST_RECORD_IDS = "";',
        `const TEST_RECORD_IDS = "${ARMED_ALLOWLIST}";`);
  }
  return wf;
}

function triggerRows(emails) {
  const spec = {
    [R_DOMAIN_UPDATE]: { firstname: "Domain", lastname: "Update", company: "Acme Domain Co" },
    [R_DOMAIN_CREATE]: { firstname: "Domain", lastname: "Create", company: "Acme Domain Co" },
    [R_NAME_UPDATE]: { firstname: "Name", lastname: "Update", company: NAME_COMPANY },
    [R_NAME_CREATE]: { firstname: "Name", lastname: "Create", company: NAME_COMPANY },
  };
  return emails.map((email) => ({ email, ...spec[email] }));
}

function stubs(emails) {
  const resolvesContact = {
    [R_DOMAIN_UPDATE]: CONTACT_DOMAIN_UPDATE,
    [R_NAME_UPDATE]: CONTACT_NAME_UPDATE,
  };
  const resolvesByDomain = new Set([R_DOMAIN_UPDATE, R_DOMAIN_CREATE]);
  return {
    "Verify Emails (batch)": [{ results: emails.map((email) => ({ email, status: "VALID" })) }],
    // Every per-row HTTP stub keys off the ROW's own identity, never its position —
    // the point of the test is that the graph, not the fixture, keeps rows aligned.
    "HubSpot Search by Email": (items) => items.map((it) => {
      const id = resolvesContact[it.email];
      return id ? { results: [{ id, properties: { email: it.email } }] } : { results: [] };
    }),
    "HubSpot Company Search by Domain": (items) => items.map((it) => (
      resolvesByDomain.has(it.email)
        ? { results: [{ id: COMPANY_BY_DOMAIN, properties: { domain: "acme-domain.example" } }] }
        : { results: [] }
    )),
    "HubSpot Company Search by Name": (items) => items.map((it) => (
      resolvesByDomain.has(it.email)
        ? { results: [] }
        : { results: [{ id: COMPANY_BY_NAME, properties: { name: NAME_COMPANY } }] }
    )),
    "HubSpot Update": (items) => items.map((it) => ({
      id: resolvesContact[it.email] ?? null, properties: { email: it.email },
    })),
    "HubSpot Create": (items) => items.map((it) => ({
      id: `new-${it.email}`, properties: { email: it.email },
    })),
    "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
  };
}

function run(emails, { armed = false } = {}) {
  const { runData, trace } = walkWorkflow(loadWorkflow({ armed }), {
    triggerNode: "Webhook Trigger",
    triggerItems: triggerRows(emails),
    httpStubs: stubs(emails),
  });
  return { runData, trace, rows: nodeItems(runData, "Build Ingest Response") };
}

// Every assertion this file makes about "exactly once" in one place: the returned rows
// map onto the input rows by the row's OWN identity (its email), never by position, and
// the mapping is a bijection — no duplicate, no missing row, no leaked sentinel marker.
function assertEveryRowExactlyOnce(rows, emails) {
  assert.equal(rows.length, emails.length,
    `one row per input row (got ${rows.length} for ${emails.length} inputs)`);
  const returned = rows.map((r) => r.email);
  assert.equal(new Set(returned).size, returned.length,
    `no duplicate identities among the returned rows: ${JSON.stringify(returned)}`);
  assert.deepEqual([...returned].sort(), [...emails].sort(),
    "the returned identities are exactly the input identities");
}

// The lane answers with the D-70-07 ack ONLY — never a row-carrying body — and the
// responder fires exactly once per request.
function assertAckFiredOnce(trace) {
  assert.deepEqual(trace.stalled, [], "no Merge may stall on this batch");
  assert.ok(trace.respond, "the responder must fire");
  assert.equal(trace.respondSuppressed.length, 0, "the responder must fire exactly once");
  assert.equal(trace.respond.items.length, 1, "one ack item");
  const [ack] = trace.respond.items;
  assert.equal(ack.accepted, true);
  assert.ok("run_id" in ack && "row_ids" in ack, "the ack shape is {run_id, accepted, row_ids}");
  assert.deepEqual(Object.keys(ack).sort(), ["accepted", "row_ids", "run_id"],
    "the ack carries nothing else — row outcomes are read from runData (D-70-05)");
}

// =====================================================================================
// The D-70-17 primary case: 2 identity lanes x 2 actions.
// =====================================================================================

test("ingest 2x2 mixed batch (company by domain / by name) x (update / create): every row returns exactly once, carrying the write node's own outcome", () => {
  const emails = [R_DOMAIN_UPDATE, R_DOMAIN_CREATE, R_NAME_UPDATE, R_NAME_CREATE];
  const { rows, trace } = run(emails, { armed: true });

  assertAckFiredOnce(trace);
  assertEveryRowExactlyOnce(rows, emails);

  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));

  // Both update rows report the id the WRITE NODE returned for that row — not the id
  // the search found, and not a neighbouring row's id.
  assert.equal(byEmail[R_DOMAIN_UPDATE].action, "update");
  assert.equal(byEmail[R_DOMAIN_UPDATE].contact_id, CONTACT_DOMAIN_UPDATE);
  assert.equal(byEmail[R_DOMAIN_UPDATE].company_id, COMPANY_BY_DOMAIN);
  assert.equal(byEmail[R_DOMAIN_UPDATE].company_match, "domain");
  assert.equal(byEmail[R_DOMAIN_UPDATE].association, "associated");

  assert.equal(byEmail[R_NAME_UPDATE].action, "update");
  assert.equal(byEmail[R_NAME_UPDATE].contact_id, CONTACT_NAME_UPDATE);
  assert.equal(byEmail[R_NAME_UPDATE].company_id, COMPANY_BY_NAME);
  assert.equal(byEmail[R_NAME_UPDATE].company_match, "name");
  assert.equal(byEmail[R_NAME_UPDATE].association, "associated");

  // The two create-path rows resolved their company on their own lane and each carries
  // a reason. `ALLOW_HUBSPOT_CREATE` is baked false in the committed JSON and is NOT
  // armed here (this phase writes nothing new), so both land on the held/refused side
  // rather than creating a person — the D-70-11 design fact.
  for (const email of [R_DOMAIN_CREATE, R_NAME_CREATE]) {
    const row = byEmail[email];
    assert.notEqual(row.action, "create", `${email}: no person is created by this batch`);
    assert.ok(row.reason, `${email}: a non-write outcome always carries a reason`);
  }
  assert.equal(byEmail[R_DOMAIN_CREATE].company_match, "domain");
  assert.equal(byEmail[R_NAME_CREATE].company_match, "name");
});

// =====================================================================================
// The D-70-17 addendum case: a SINGLE-lane batch. The 2x2 shape exercises every lane by
// construction and so cannot catch a Merge waiting on an input that never fires — which
// is both the common real shape and Gate 1's hang probe (70-DEFERRED-GATES.md).
// =====================================================================================

test("ingest single-lane-only batch (every row an update on the association path, review path empty): rows return and no Merge stalls", () => {
  const emails = [R_DOMAIN_UPDATE, R_NAME_UPDATE];
  const { rows, trace } = run(emails, { armed: true });

  assertAckFiredOnce(trace);
  assertEveryRowExactlyOnce(rows, emails);
  for (const row of rows) {
    assert.equal(row.action, "update");
    assert.equal(row.association, "associated");
  }
  // Named explicitly: the review lane contributed nothing to this batch, and the
  // response Merge still fired.
  assert.equal(trace.stalled.length, 0, "Ingest Merge Response must not wait on the empty review lane");
});

// =====================================================================================
// The fully-refused case — the shape that dead-ended before this phase, when a refusal
// was a thrown error or a body-borne status rather than an emitted row.
// =====================================================================================

test("ingest fully-refused batch (disarmed, every row a would-be update): every row returns once carrying its refusal reason", () => {
  const emails = [R_DOMAIN_UPDATE, R_NAME_UPDATE];
  const { rows, trace } = run(emails, { armed: false });

  assertAckFiredOnce(trace);
  assertEveryRowExactlyOnce(rows, emails);
  for (const row of rows) {
    assert.equal(row.action, "write_blocked",
      `${row.email}: the disarmed gate refuses this write`);
    assert.ok(row.reason && row.reason.length > 0,
      `${row.email}: the refusal reaches the caller WITH its reason, as a row`);
    // A refusal still names the record it WOULD have written — that is what makes it
    // actionable to the operator — but never claims the write or the association.
    assert.ok(row.contact_id, `${row.email}: the refusal names the record it would have written`);
    assert.notEqual(row.association, "associated",
      "a refused write never claims an association");
  }
});
