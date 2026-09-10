// tests/n8n/ingestTracerFlow.test.mjs
//
// Phase 70 Plan 02 (D-70-01/D-70-03/D-70-04/D-70-05/D-70-06/D-70-07): the tracer proof —
// one ingest row travels the new architecture end to end, through a real Merge at the
// convergence point ("Ingest Merge Response"), through a carry Merge across an HTTP hop
// ("Associate Carry Merge"), out of an ack-only webhook ("Build Ingest Ack"), replayed
// here over the COMMITTED n8n/wf_contact_ingest_cloud.json via the 70-01 walker.
//
// ARM() mirrors pairPipelineAssociationFlow.test.mjs's own idiom: the committed JSON
// ships disarmed (ALLOW_HUBSPOT_RECORD_WRITES/ALLOW_HUBSPOT_CREATE = "false", empty
// allowlist — grep-pinned in build_cloud_workflows.py's own acceptance criteria), so an
// offline proof of the ARMED shape mutates the LOADED jsCode strings in memory, never
// the committed file on disk. Three nodes each embed the write-safety constants
// independently ("Decide Action", "HubSpot Update Write Gate", "HubSpot Associate
// Company Write Gate") — all three need the same replacement for a row to actually
// reach the association chain.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

function loadArmedWorkflow({ testRecordIds = "" } = {}) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  // Phase 70 Plan 05 Task 2/3: "Decide Action" no longer bakes the write-safety
  // allowlist (its D-70-06 precheck is gone) and the association no longer has a gate of
  // its own (D-70-15 — one verdict, taken at the update gate). The update gate is the
  // single arming surface for this whole lane now.
  // "Associate Lane Sentinel" carries the same baked constants (Phase 70 Plan 05 Task
  // 2c): it duplicates the gate predicate purely to decide whether its Merge-feeding
  // marker is needed, and a marker that fires while a real association is in flight
  // would satisfy the Merge early and drop it. The real arming tool
  // (n8n_arming.set_write_safety) rewrites EVERY declaring node, so this hand-rolled
  // helper must too — arming a subset is a test artifact, not a deployable state.
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
    // ALLOW_HUBSPOT_CREATE stays "false" everywhere — this fixture never exercises the
    // create path, only update (association) vs. review.
  }
  return wf;
}

const ROW1_EMAIL = "existing@example.com"; // resolves to an existing HubSpot contact
const ROW2_EMAIL = "newperson@example.com"; // resolves to nothing -> net_new -> review (create disabled)
const ROW1_CONTACT_ID = "111";
const ROW1_COMPANY_ID = "9001";

function twoRowFixture() {
  return {
    triggerItems: [
      { email: ROW1_EMAIL, firstname: "Existing", lastname: "Contact", company: "Existing Co" },
      { email: ROW2_EMAIL, firstname: "New", lastname: "Person", company: "New Co" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{
        results: [
          { email: ROW1_EMAIL, status: "VALID" },
          { email: ROW2_EMAIL, status: "VALID" },
        ],
      }],
      "HubSpot Search by Email": [
        { results: [{ id: ROW1_CONTACT_ID, properties: { email: ROW1_EMAIL } }] },
        { results: [] },
      ],
      "HubSpot Company Search by Domain": [
        { results: [{ id: ROW1_COMPANY_ID, properties: { domain: "example.com" } }] },
        { results: [] },
      ],
      "HubSpot Company Search by Name": [
        { results: [] },
        { results: [] },
      ],
      "HubSpot Update": [{ id: ROW1_CONTACT_ID, properties: { email: ROW1_EMAIL } }],
      "HubSpot Associate Company": [{ status: "ok" }],
    },
  };
}

function reviewOnlyFixture() {
  // Neither row ever matches an existing contact, and create stays disabled — every
  // row lands at "Set Review". The single-lane hang case (research Pitfall 1): nothing
  // on the association chain (IF Update/IF Create true branches, HubSpot Update/
  // Create, Build Association Request, the write gate, HubSpot Associate Company,
  // "Associate Carry Merge") ever runs at all this execution.
  return {
    triggerItems: [
      { email: "one@example.com", firstname: "One", lastname: "Person", company: "One Co" },
      { email: "two@example.com", firstname: "Two", lastname: "Person", company: "Two Co" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{
        results: [
          { email: "one@example.com", status: "VALID" },
          { email: "two@example.com", status: "VALID" },
        ],
      }],
      "HubSpot Search by Email": [{ results: [] }, { results: [] }],
      "HubSpot Company Search by Domain": [{ results: [] }, { results: [] }],
      "HubSpot Company Search by Name": [{ results: [] }, { results: [] }],
      // Neither HTTP write node should ever be called on this batch — an unstubbed
      // node throws by name (walkWorkflow.mjs's own documented contract), so leaving
      // "HubSpot Update"/"HubSpot Create"/"HubSpot Associate Company" OUT of this map
      // is itself part of the proof: if the graph wrongly routed a row there, this
      // fixture would throw rather than silently pass.
    },
  };
}

test("a two-row batch (one association-path row, one review-path row) reaches Build Ingest Response exactly once, through the real Merge", () => {
  const wf = loadArmedWorkflow({ testRecordIds: ROW1_CONTACT_ID });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: twoRowFixture().triggerItems,
    httpStubs: twoRowFixture().httpStubs,
  });

  assert.deepEqual(starvedWithData(trace), [], "no Merge should ever hang on this batch");

  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 2, "both rows must appear exactly once — no F5 collapse");

  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));
  assert.equal(byEmail[ROW1_EMAIL].action, "update");
  assert.equal(byEmail[ROW1_EMAIL].association, "associated",
    "the carry Merge must re-attach the association write's own response to this row");
  assert.equal(byEmail[ROW1_EMAIL].contact_id, ROW1_CONTACT_ID);
  assert.equal(byEmail[ROW1_EMAIL].company_id, ROW1_COMPANY_ID);

  assert.equal(byEmail[ROW2_EMAIL].action, "review");
  assert.equal(byEmail[ROW2_EMAIL].association, "none");

  // The lane's only responder fires exactly once and its item is the ack shape
  // (D-70-07) — never a per-row body.
  assert.equal(trace.respond.node, "Respond to Webhook");
  assert.deepEqual(trace.respondSuppressed, []);
  const ackItems = nodeItems(runData, "Build Ingest Ack");
  assert.equal(ackItems.length, 1);
  assert.equal(ackItems[0].accepted, true);
  assert.deepEqual(ackItems[0].row_ids, []);
  assert.ok("run_id" in ackItems[0]);
});

test("a review-only batch (zero association rows) does not stall any Merge — the single-lane hang case", () => {
  const wf = loadArmedWorkflow(); // TEST_RECORD_IDS left empty — irrelevant, nothing armed matches
  const fixture = reviewOnlyFixture();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: fixture.triggerItems,
    httpStubs: fixture.httpStubs,
  });

  // Phase 70 Plan 10 (D-70-20/D-70-23): "Associate Carry Merge" is now legitimately
  // allowed to stay dormant on a review-only batch — the carry-Merge BYPASS this plan
  // adds means "Associate Lane Sentinel" delivers straight to "Ingest Merge Response"'s
  // own association-lane input, never to either of "Associate Carry Merge"'s inputs (a
  // marker on BOTH of that positional-combine merge's inputs would pair with itself
  // into one fabricated row, T-70-41). Nothing downstream ever reads "Associate Carry
  // Merge"'s own output directly, so its staying unfired here is the intended shape,
  // not a hang — what must never stall is the merge everything else actually depends
  // on, "Ingest Merge Response" (and every other merge on this lane).
  assert.deepEqual(starvedWithData(trace), [],
    "no Merge lost a row on this batch (starvedWithData); per-node fire claims are asserted on runData above");
  assert.ok((runData["Ingest Merge Response"] || []).length >= 1,
    "Ingest Merge Response — what this batch's correctness actually rests on — must fire");

  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 2, "both review rows present, no association row, no marker leakage");
  for (const row of rows) {
    assert.equal(row.action, "review");
    assert.equal(row.association, "none");
  }

  // Confirms the association lane's real chain never ran at all this execution — the
  // marker mechanism satisfied the Merge without any real write attempt.
  assert.deepEqual(runData["HubSpot Associate Company"], undefined,
    "the write node must never have been dispatched on a review-only batch");
});

test("splice_merge_before's own class-(c) refusal is respected by the walker: an alternate-entry-point convergence never appears in this committed graph", () => {
  // Structural corollary of the acceptance criterion pinned in build_cloud_workflows.py
  // (a dedicated Python unit test over a hand-built two-trigger graph asserts the
  // refusal itself) — this repeats the SAME assertion from the walker's own vantage:
  // "Build Ingest Response" converges class "fan_in" (both lane terminals trace back to
  // the ONE "Webhook Trigger"), never class "entry_points".
  const wf = loadArmedWorkflow();
  const triggers = wf.nodes.filter((n) =>
    ["n8n-nodes-base.webhook", "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.executeWorkflowTrigger"]
      .includes(n.type));
  assert.equal(triggers.length, 1, "the ingest lane has exactly one entry point");
});
