// tests/n8n/pairPipelineAssociationFlow.test.mjs
//
// Phase 61 Plan 06 Task 1 — the "pair pipeline" (ingest -> enrich -> create ->
// associate) drives its actual HubSpot writes through the INGEST lane
// (n8n/wf_contact_ingest_cloud.json), which already carries the 2026-08-25
// association rule (CLAUDE.md §13.0.1): `enrich-before-ingest/SKILL.md` step 7
// dispatches its real write via `dispatch.dispatch` -> the contact-upload webhook,
// never the enrichment webhook (which this flow only ever calls in `mode: propose`,
// return-only, for the waterfall preview).
//
// This is a BATCH test, not three single-row tests: it drives all three shapes
// through "Decide Action" in ONE call, the way a real batch actually runs, so a row
// mixing bug (values crossing between rows in the same execution) cannot hide behind
// three separate single-item calls. The load-bearing assertion is the SECOND row: a
// create that resolves no company must be HELD, never landed unassociated — a test
// that only proves the first row associates would pass on an implementation that
// lands an unassociated contact whenever resolution fails, which is precisely the
// outcome the 2026-08-25 contract forbids.
//
// Same `new Function` harness as companyAssociationFlow.test.mjs / contactCreateGateFlow.test.mjs
// — this repo's OWN committed jsCode, not a hand-transcribed copy.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");
const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};
const jsCodeOf = (name) => node(name).parameters.jsCode;

function runCode(jsCode, seedItems, nodeOutputs = {}) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const $ = (name) => {
    if (!(name in nodeOutputs)) throw new Error(`no node named ${name}`);
    return { all: () => nodeOutputs[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

const ARM = (js) =>
  js
    .replace('const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";')
    .replace(
      'const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
      'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'
    );

test("a batch of three rows: resolved create, unresolved create, and an update — one call, one execution", () => {
  const batch = [
    // Row 1: resolves a company -> lands, associated.
    {
      identity: { outcome: "net_new" },
      merge: { canonicalPatch: {} },
      email: "jo@resolved.example",
      firstname: "Jo",
      lastname: "Rider",
      company: "Resolved Co",
      company_id: "9600000001",
      company_match: "domain",
      company_domain: "resolved.example",
    },
    // Row 2: no company resolves -> HELD, never landed unassociated. The
    // load-bearing assertion in this file.
    {
      identity: { outcome: "net_new" },
      merge: { canonicalPatch: {} },
      email: "sam@unresolved.example",
      firstname: "Sam",
      lastname: "Smith",
      company: "Nowhere Co",
      company_id: null,
      company_hold_reason: "no company in HubSpot matched domain unresolved.example",
    },
    // Row 3: an existing contact being enriched — not a create at all, so an empty
    // company_id is not a hold; it simply has nothing to associate.
    {
      identity: { outcome: "match", contact_id: "555" },
      merge: { canonicalPatch: { jobtitle: "CEO" } },
      company_id: null,
    },
  ];

  const decided = runCode(ARM(jsCodeOf("Decide Action")), batch);
  assert.equal(decided.length, 3, "every row in the batch reaches a decision");

  const [resolved, held, updated] = decided;

  assert.equal(resolved.action, "create");
  assert.equal(resolved.company_id, "9600000001");
  assert.equal(resolved.properties.email, "jo@resolved.example");

  assert.equal(held.action, "review", "an unassociated contact must never be created");
  assert.match(held.reason, /no company in HubSpot matched/);
  assert.equal(held.company_id, null);

  assert.equal(updated.action, "update");
  assert.equal(updated.company_id, null);
  assert.equal(updated.reason, null, "an update with nothing to associate is not held");

  // Downstream of the two write IFs: only the RESOLVED create's write response ever
  // reaches "Build Association Request" — the held row never reached a write node at
  // all, so there is no response for it to join against. Joined BY VALUE (email),
  // never by position, mirroring companyAssociationFlow.test.mjs's own proof.
  const writeResponses = [
    { id: "12345", properties: { email: "JO@resolved.example" } },
  ];
  const requested = runCode(jsCodeOf("Build Association Request"), writeResponses, {
    "Decide Action": decided,
  });
  assert.equal(requested.length, 1, "only the resolved create's write is an association request");
  assert.equal(requested[0].contact_id, "12345");
  assert.equal(requested[0].company_id, "9600000001");
  assert.equal(
    requested[0].assoc_url,
    "https://api.hubapi.com/crm/v4/objects/contacts/12345/associations/default/companies/9600000001"
  );

  // Build Ingest Response reports all three rows, associated or not — a held row is
  // still visible in the batch's own report, never silently dropped.
  const gated = [{ contact_id: "12345" }];
  const report = runCode(jsCodeOf("Build Ingest Response"), [{ status: "ok" }], {
    "Decide Action": decided,
    "Build Association Request": requested,
    "HubSpot Associate Company Write Gate": gated,
  });
  assert.equal(report.length, 3);
  assert.equal(report[0].association, "associated");
  assert.equal(report[1].action, "review");
  assert.equal(report[1].association, "none");
  assert.match(report[1].reason, /no company in HubSpot matched/);
  assert.equal(report[2].action, "update");
  assert.equal(report[2].association, "none");
  assert.equal(report[2].reason, null);
});
