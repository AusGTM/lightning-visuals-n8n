// tests/n8n/enrichmentMixedBatch.test.mjs
//
// Phase 70 Plan 07 Task 1 (D-70-17) — THE acceptance test for the enrichment lane: a
// mixed batch spanning 2 identity lanes x 2 actions, asserting every input row returns
// exactly once from the write node's own output. Drives the COMMITTED
// n8n/wf_enrichment_cloud.json through tests/n8n/lib/walkWorkflow.mjs.
//
// The two identity lanes here are `email` and `linkedin_url` — two of the three identity
// groups `config/column_mapping.yaml`'s `required_identity.any_of` names (CLAUDE.md
// §13.0.2). The third, name-only, is deliberately NOT used as a lane: `matchProposal.js`
// `summarizeMatch`'s `name` arm returns `auto: false` always, so a name-only row can
// never produce an `update` and cannot supply the second half of the 2x2.
//
// A NOTE ON THE BATCH SIZE, which shapes this whole file: `Parse HubSpot Event` caps a
// WRITE-mode request at MAX_WRITE_EVENTS = 2 and refuses an oversize request WHOLE
// (never truncates). A 4-row write batch is therefore refused by the backend's own
// ceiling and can prove nothing about row alignment. So the 2x2 is covered in the shape
// the backend actually accepts:
//   - one 4-row PROPOSE batch (ceiling 20) covering all four cells at once, proving row
//     alignment across both identity lanes and both match outcomes;
//   - two 2-row ARMED WRITE batches, one per identity lane, proving that the outcome a
//     row reports came from the write node's own output.
// This is the real contract, not a workaround: the live D-70-19 send is bound by the
// same ceiling.
//
// D-70-18, recorded by the operator in 70-CONTEXT.md: GREEN on the refactored JSON is
// enough here; no historical RED was taken against the pre-Phase-70 JSON. The evidence
// that this instrument can SEE the defect class lives in tests/n8n/walkWorkflow.test.mjs.
//
// The committed JSON ships DISARMED; the armed cases mutate the LOADED jsCode strings in
// memory and never the file on disk.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

const EMAIL_MATCHED = "exists@mixed.example";
const EMAIL_UNMATCHED = "newperson@mixed.example";
const LINKEDIN_MATCHED = "https://www.linkedin.com/in/mixed-exists";
const LINKEDIN_UNMATCHED = "https://www.linkedin.com/in/mixed-new";

const CONTACT_BY_EMAIL = "111";
const CONTACT_BY_LINKEDIN = "222";

// Every node on this lane that DECLARES a write flag. The real arming tool
// (n8n_arming.set_write_safety) rewrites all of them; arming a subset is a test
// artifact, not a deployable state.
const ARMING_NODES = ["HubSpot Create Write Gate", "HubSpot Update Write Gate",
  "HubSpot Company Create Write Gate", "HubSpot Company Update Write Gate"];

function loadWorkflow({ allowlist = null } = {}) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  if (allowlist === null) return wf;
  for (const name of ARMING_NODES) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `node present: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const TEST_RECORD_IDS = "";', `const TEST_RECORD_IDS = "${allowlist}";`);
  }
  return wf;
}

// Every HTTP node a contacts batch can reach, all returning "no data" — this phase's
// batches are about ROW ALIGNMENT, not provider content, and every provider is disabled
// on these requests anyway.
function baseStubs() {
  return {
    "HubSpot Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search Fallback": (items) => items.map(() => ({ results: [] })),
    "Lusha Enrich": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Match": (items) => items.map(() => ({})),
    "ZoomInfo Mint": [{ access_token: "tok" }],
    "Contact Web Research": (items) => items.map(() => ({})),
    "Contact Judge Call": (items) => items.map(() => ({})),
    "HubSpot Create": (items) => items.map((_, i) => ({ id: `created-${i}`, properties: {} })),
    "Lusha Usage": [{}],
    "Apollo Usage": [{}],
    "ZoomInfo Usage Mint": [{ access_token: "tok" }],
    // Both identity searches key off the ROW's own identity, never its position — the
    // point of the test is that the graph, not the fixture, keeps rows aligned.
    "HubSpot Search": (items) => items.map((it) => (
      it.identity_keys?.email === EMAIL_MATCHED
        ? { results: [{ id: CONTACT_BY_EMAIL, properties: { email: EMAIL_MATCHED } }] }
        : { results: [] }
    )),
    "HubSpot Linkedin Search": (items) => items.map((it) => (
      String(it.linkedin_url || "") === LINKEDIN_MATCHED
        ? { results: [{ id: CONTACT_BY_LINKEDIN, properties: { lv_linkedin_url: LINKEDIN_MATCHED } }] }
        : { results: [] }
    )),
    "HubSpot Update": (items) => items.map((it) => ({
      id: it.write_request?.hs_object_id ?? it.hs_object_id ?? null, properties: {},
    })),
  };
}

function run(events, { mode = "propose", allowlist = null, runId = "mixed-batch" } = {}) {
  const { runData, trace } = walkWorkflow(loadWorkflow({ allowlist }), {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { run_id: runId, mode, events } }],
    httpStubs: baseStubs(),
  });
  return { runData, trace, rows: nodeItems(runData, "Build Response") };
}

const EMAIL_ROWS = [
  { objectType: "contact", email: EMAIL_MATCHED, row_id: "email-matched" },
  { objectType: "contact", email: EMAIL_UNMATCHED, row_id: "email-unmatched" },
];
const LINKEDIN_ROWS = [
  { objectType: "contact", linkedin_url: LINKEDIN_MATCHED, row_id: "linkedin-matched" },
  { objectType: "contact", linkedin_url: LINKEDIN_UNMATCHED, row_id: "linkedin-unmatched" },
];

// The responder answers with the D-70-07 ack ONLY — never a row-carrying body — exactly
// once per request.
function assertAckFiredOnce(trace, { runId = "mixed-batch", rowIds = null } = {}) {
  assert.deepEqual(trace.stalled, [], "no Merge may stall on this batch");
  assert.ok(trace.respond, "the responder must fire");
  assert.equal(trace.respondSuppressed.length, 0, "the responder must fire exactly once");
  assert.equal(trace.respond.items.length, 1, "one ack item");
  const [ack] = trace.respond.items;
  assert.equal(ack.accepted, true);
  assert.equal(ack.run_id, runId);
  assert.deepEqual(Object.keys(ack).sort(), ["accepted", "row_ids", "run_id"],
    "the ack carries nothing else — row outcomes are read from runData (D-70-05)");
  if (rowIds) assert.deepEqual([...ack.row_ids].sort(), [...rowIds].sort());
}

// =====================================================================================
// The D-70-17 primary case: 2 identity lanes x 2 actions, in the one request shape the
// backend's own ceiling allows all four cells to share.
// =====================================================================================

test("enrichment 2x2 mixed batch (email / linkedin_url) x (matched / unmatched): every row returns exactly once, keyed by its own row_id", () => {
  const events = [...EMAIL_ROWS, ...LINKEDIN_ROWS];
  const expectedRowIds = events.map((e) => e.row_id);
  const { rows, trace } = run(events);

  assertAckFiredOnce(trace, { rowIds: expectedRowIds });

  assert.equal(rows.length, 4, "one row per input row — never fewer (a collapse), never a phantom marker");
  const returned = rows.map((r) => r.row_id);
  assert.equal(new Set(returned).size, returned.length,
    `no duplicate identities among the returned rows: ${JSON.stringify(returned)}`);
  assert.deepEqual([...returned].sort(), [...expectedRowIds].sort(),
    "the returned identities are exactly the input identities");

  const byRow = Object.fromEntries(rows.map((r) => [r.row_id, r]));
  // Each matched row carries the record ITS OWN identity lane resolved — not the other
  // lane's, which is exactly what a positional misalignment would produce.
  assert.equal(byRow["email-matched"].hs_object_id, CONTACT_BY_EMAIL);
  assert.equal(byRow["linkedin-matched"].hs_object_id, CONTACT_BY_LINKEDIN);
  assert.equal(byRow["email-unmatched"].hs_object_id, null);
  assert.equal(byRow["linkedin-unmatched"].hs_object_id, null);
});

// =====================================================================================
// The write-node half of the 2x2: one armed WRITE batch per identity lane, each within
// MAX_WRITE_EVENTS. The reported outcome must come from the write node's own output.
// =====================================================================================

for (const [lane, events, matchedRowId, matchedId] of [
  ["email", EMAIL_ROWS, "email-matched", CONTACT_BY_EMAIL],
  ["linkedin_url", LINKEDIN_ROWS, "linkedin-matched", CONTACT_BY_LINKEDIN],
]) {
  test(`enrichment armed write batch on the ${lane} identity lane (matched + unmatched): both rows return once and the write outcome is the write node's own`, () => {
    const { rows, runData, trace } = run(events, { mode: "write", allowlist: matchedId });

    assertAckFiredOnce(trace, { rowIds: events.map((e) => e.row_id) });
    assert.equal(rows.length, 2, "one row per input row");

    // The permitted row reached the write node, and the write node's OWN response is
    // what came back — the enrichment lane wires "HubSpot Update" straight into
    // "Build Response Merge" input 2, so the returned item IS that response.
    const writeResponses = nodeItems(runData, "HubSpot Update");
    assert.equal(writeResponses.length, 1, `exactly the one permitted ${lane} row was written`);
    assert.equal(writeResponses[0].id, matchedId);
    const written = rows.find((r) => r.id === matchedId);
    assert.ok(written, `the ${lane} write response reached the caller as a row`);

    // The unmatched row never reaches a write node: a contact create on THIS lane is
    // downgraded to review because it cannot be associated with a company here
    // (CLAUDE.md §13.0.1, closed by refusal). That is the D-70-11 design fact — under
    // autonomy a new person is never created without the operator's approval.
    const unmatched = rows.find((r) => r.row_id === `${lane === "email" ? "email" : "linkedin"}-unmatched`);
    assert.ok(unmatched, "the unmatched row returned too — a batch never drops its held rows");
    assert.equal(unmatched.action, "review");
    assert.equal(unmatched.hs_object_id, null);
    assert.equal(nodeItems(runData, "HubSpot Create").length, 0,
      "no person is created by this batch");
  });
}

// =====================================================================================
// The D-70-17 addendum case: a SINGLE-lane batch. The 2x2 exercises every lane by
// construction and so cannot catch a Merge waiting on an input that never fires — the
// common real shape, and Gate 1's hang probe (70-DEFERRED-GATES.md).
// =====================================================================================

test("enrichment single-lane-only batch (email identity only, no companies lane, no linkedin lane): rows return and no Merge stalls", () => {
  const { rows, trace } = run(EMAIL_ROWS, { mode: "write", allowlist: CONTACT_BY_EMAIL });

  assertAckFiredOnce(trace, { rowIds: EMAIL_ROWS.map((e) => e.row_id) });
  assert.equal(rows.length, 2, "both rows return with every companies-side merge input silent");
  assert.equal(trace.stalled.length, 0,
    "Build Response Merge must not wait on the companies lane this batch never touched");
});

// =====================================================================================
// The fully-refused case — the shape that dead-ended before this phase, when a refusal
// was a body-borne status rather than an emitted row.
// =====================================================================================

test("enrichment fully-refused batch (disarmed, both rows would-be writes): every row returns once carrying its refusal", () => {
  const events = [
    { objectType: "contact", email: EMAIL_MATCHED, row_id: "email-matched" },
    { objectType: "contact", linkedin_url: LINKEDIN_MATCHED, row_id: "linkedin-matched" },
  ];
  const { rows, runData, trace } = run(events, { mode: "write" });

  assertAckFiredOnce(trace, { rowIds: events.map((e) => e.row_id) });
  assert.equal(rows.length, 2, "one row per input row, each carrying its own refusal");
  assert.equal(nodeItems(runData, "HubSpot Update").length, 0, "zero writes when disarmed");

  const byRow = Object.fromEntries(rows.map((r) => [r.row_id, r]));
  for (const rowId of ["email-matched", "linkedin-matched"]) {
    const row = byRow[rowId];
    assert.ok(row, `${rowId}: the refusal reached the caller as a row, not as an HTTP body`);
    assert.equal(row.action, "write_blocked");
    assert.ok(row.write_blocked_reason || row.reason,
      `${rowId}: the refusal carries a reason`);
  }
  // Each refusal still names the record it WOULD have written — that is what makes it
  // actionable — and the two rows name DIFFERENT records, one per identity lane.
  assert.equal(byRow["email-matched"].hs_object_id, CONTACT_BY_EMAIL);
  assert.equal(byRow["linkedin-matched"].hs_object_id, CONTACT_BY_LINKEDIN);
});
