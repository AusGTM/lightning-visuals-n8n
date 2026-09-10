// tests/n8n/walkerEngineFidelity.test.mjs
//
// Phase 70 plan 70-09 (gaps G-70-2 / G-70-3, decisions D-70-19 / D-70-20): the walker's
// fidelity to the LIVE n8n Cloud engine, stated as reproductions of two executions this
// repo actually watched on 2026-09-10.
//
// Why this file exists. Every offline suite was green while the live engine dropped rows.
// `tests/n8n/lib/walkWorkflow.mjs` dropped a zero-item wave; the engine DELIVERS it. So
// an offline green meant nothing, and no graph fix could be believed until the instrument
// told the truth. These cases are written against the observed runData of executions
// 12203 and 12206 — the outcome the engine PRODUCED, never the outcome the design
// intended. D-70-19: the walker moves toward the engine, never toward the plans and never
// toward a green suite.
//
// Every case runs against a FROZEN copy of the graph as committed on 2026-09-10 (see
// `fixtures/frozen/README.md`), because Wave 2 changes the live graph under `n8n/` and
// "the current committed JSON" would otherwise stop meaning what these executions ran.
//
// The armed case rewrites the loaded jsCode literals in memory — the same rewrite
// `n8n_arming.set_write_safety` performs live and the one `tests/n8n/writeGateShape.test.mjs`
// already uses. It is deliberately NOT a second arming mechanism, and it never touches a
// file on disk.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FROZEN = path.join(HERE, "fixtures", "frozen");
const FROZEN_INGEST = path.join(FROZEN, "wf_contact_ingest_cloud.2026-09-10.json");

// =====================================================================================
// Execution 12203 — Gate 70-05-A, the first ARMED batch with a mixed verdict on one gate.
//
// Observed (70-UAT.md § Test 2): Darwin Turf Club `9605267534`; contact `7101` Grant
// Dewsbury on the allowlist, contact `2751` Steve Taylor off it, both in ONE batch, both
// resolving the same company by domain. HubSpot itself was written CORRECTLY — 7101
// PATCHed, the 7101 -> 9605267534 association created, 2751 untouched. What FAILED was
// the REPORT: `Build Ingest Response` returned 2 rows, and BOTH came back
// `action: "update"`, `association: "not_confirmed"`.
//
// Cause, from the runData `source` arrays: `Associate Carry Merge` (combineByPosition)
// fired with input 1 taken by `Associate Lane Sentinel`'s ZERO-ITEM output (armed, a real
// association was in flight, so the sentinel emitted `[]`) instead of `Build Association
// Request`'s one item — 1 x 0 combined to 0 items and the association result was dropped.
// `Ingest Merge Response` fired with input 3 taken by `HubSpot Update Gate Unreached
// Sentinel`'s ZERO-ITEM output instead of the gate IF's refusal row, so the
// `write_blocked` row for 2751 — which `HubSpot Update Write Gate IF` out1 DID emit —
// never reached the response builder.
// =====================================================================================

const A_EMAIL = "grant@darwinturfclub.org.au";   // contact 7101, ON the allowlist
const B_EMAIL = "steve@darwinturfclub.org.au";   // contact 2751, OFF the allowlist
const A_ID = "7101";
const B_ID = "2751";
const COMPANY_ID = "9605267534";
const COMPANY_DOMAIN = "darwinturfclub.org.au";

// Every node on this lane that DECLARES a write flag. The operator's read-back on 12203
// confirmed all THREE were rewritten by `june_run_arm.py`; arming a subset here would be
// a test artifact rather than the state the engine ran under.
const ARMING_NODES = ["HubSpot Update Write Gate", "HubSpot Create Write Gate",
  "Associate Lane Sentinel"];

function armedIngestGraph() {
  const wf = JSON.parse(fs.readFileSync(FROZEN_INGEST, "utf8"));
  for (const name of ARMING_NODES) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `execution 12203 armed this node, so it must exist in the frozen graph: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const TEST_RECORD_IDS = "";', `const TEST_RECORD_IDS = "${A_ID}";`);
  }
  return wf;
}

function run12203() {
  return walkWorkflow(armedIngestGraph(), {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: A_EMAIL, firstname: "Grant", lastname: "Dewsbury", company: "Darwin Turf Club" },
      { email: B_EMAIL, firstname: "Steve", lastname: "Taylor", company: "Darwin Turf Club" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [
        { email: A_EMAIL, status: "VALID" }, { email: B_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [
        { results: [{ id: A_ID, properties: { email: A_EMAIL } }] },
        { results: [{ id: B_ID, properties: { email: B_EMAIL } }] },
      ],
      // Both contacts resolve the SAME company, by domain — the shape that made the
      // association lane live for one row and refused for the other.
      "HubSpot Company Search by Domain": [
        { results: [{ id: COMPANY_ID, properties: { domain: COMPANY_DOMAIN } }] },
        { results: [{ id: COMPANY_ID, properties: { domain: COMPANY_DOMAIN } }] },
      ],
      "HubSpot Company Search by Name": [{ results: [] }, { results: [] }],
      // Only the permitted contact is written, and only its association is created —
      // exactly what HubSpot showed after 12203.
      "HubSpot Update": [{ id: A_ID, properties: { email: A_EMAIL } }],
      "HubSpot Associate Company": [{ status: "ok" }],
    },
  });
}

test("execution 12203 (armed mixed verdict, ingest lane): the walker reproduces what the engine DID — both rows report update/not_confirmed and the refusal row never reaches the response builder", () => {
  const { runData } = run12203();
  const rows = nodeItems(runData, "Build Ingest Response");

  // The one thing 12203 got right: two rows in, two rows out, never four.
  assert.equal(rows.length, 2,
    "execution 12203 observed: Build Ingest Response returned exactly 2 rows, never 4");

  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));

  // --- the association fact, asserted FIRST because it is the fact this file exists for.
  // HubSpot really did create the 7101 -> 9605267534 association on 12203. The REPORT did
  // not say so, because the sentinel's zero-item output claimed the carry Merge's input
  // ahead of the real association result.
  assert.equal(byEmail[A_EMAIL].association, "not_confirmed",
    "execution 12203 observed: the PERMITTED row reported association 'not_confirmed' " +
    "even though HubSpot created the association — Associate Carry Merge fired with " +
    "input 1 taken by Associate Lane Sentinel's zero-item output");
  assert.equal(byEmail[B_EMAIL].association, "not_confirmed",
    "execution 12203 observed: the refused row reported association 'not_confirmed'");

  // --- the refusal fact: the gate DID emit a write_blocked row, and it was dropped.
  assert.equal(byEmail[B_EMAIL].action, "update",
    "execution 12203 observed: the REFUSED row still reported action 'update' — the " +
    "gate's write_blocked row never reached Build Ingest Response");
  assert.equal(byEmail[A_EMAIL].action, "update",
    "execution 12203 observed: the permitted row reported action 'update'");

  // The gate itself behaved correctly — this is what makes the drop a REPORTING defect
  // rather than an authorization one.
  const gateRows = nodeItems(runData, "HubSpot Update Write Gate IF");
  const refused = gateRows.find((r) => r.hs_object_id === B_ID);
  assert.ok(refused && refused.write_allowed === false,
    "execution 12203 observed: HubSpot Update Write Gate IF out1 DID emit the " +
    "write_blocked row for 2751 — the row exists, it simply never reached the merge");

  // --- the carry Merge: one run, zero items out (1 real association x 0 sentinel items).
  assert.equal((runData["Associate Carry Merge"] || []).length, 1,
    "execution 12203 observed: Associate Carry Merge ran exactly once");
  assert.equal(runData["Associate Carry Merge"][0].length, 0,
    "execution 12203 observed: Associate Carry Merge emitted ZERO items — " +
    "combineByPosition of 1 real association against the sentinel's empty input");

  // --- the response Merge: one run, and the refusal row is absent from the merged set.
  // The load-bearing assertion of this file: a row that a node genuinely emitted is
  // missing from the merged result because a sentinel's [] claimed its input first.
  assert.equal((runData["Ingest Merge Response"] || []).length, 1,
    "execution 12203 observed: Ingest Merge Response ran exactly once");
  const merged = runData["Ingest Merge Response"][0];
  assert.equal(merged.some((it) => it && it.write_allowed === false), false,
    "execution 12203 observed: the write_blocked row emitted by the update gate's second " +
    "output is ABSENT from Ingest Merge Response's merged set — input 3 was taken by " +
    "HubSpot Update Gate Unreached Sentinel's zero-item output");
});
