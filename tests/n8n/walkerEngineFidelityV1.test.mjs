// tests/n8n/walkerEngineFidelityV1.test.mjs
//
// Quick task 260911-0tz — v1 REPRODUCTIONS, the inverse of walkerEngineFidelity.test.mjs's
// three RECORDED LEGACY divergences. Every case here walks the frozen v1 graph copy
// (`fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json`, a byte copy of the committed
// `n8n/wf_enrichment_cloud.json` at commit `ec102a4`, `settings.executionOrder: "v1"`) with
// no `allowLegacy` escape — this file is what proves the walker's v1 branch reproduces what
// the live engine ACTUALLY DID on executions 12354, 12355 and 12356 (Gate 11, 2026-09-10),
// frozen at `fixtures/frozen/exec_1235{4,5,6}.runData.json` and first read (no walk) by
// `tests/n8n/v1RuntimeRecordings.test.mjs`.
//
// D-70-19: the walker moves toward the engine. Both `triggerItems` and `httpStubs` below are
// taken from the recording's OWN runData, never hand-written, so this fixture cannot drift
// from the run it claims to reproduce.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FROZEN = path.join(HERE, "fixtures", "frozen");
const FROZEN_V1_GRAPH = path.join(FROZEN, "wf_enrichment_cloud.v1.2026-09-10.json");

const HTTP_TYPES = new Set(["n8n-nodes-base.httpRequest", "n8n-nodes-base.hubspot"]);

function loadRecording(id) {
  return JSON.parse(fs.readFileSync(path.join(FROZEN, `exec_${id}.runData.json`), "utf8"));
}

// httpStubs sourced from the recording's own runData — the SAME httpStubs mechanism
// enrichmentMixedBatch.test.mjs uses, fed by the engine's recorded responses instead of by
// hand. Returns run k's items on call k, and REFUSES whenever the walker calls a node MORE
// times than the recording ran it live (NT-02, quick task 260911-1z5) — the fallback used
// to refuse only for a node that ran more than once live, silently replaying run 0 for a
// node that ran exactly once but was called more than once by the walk; that asymmetry is
// gone, so ANY over-call is now a refusal, never a silent replay.
function httpStubsFromRecording(wf, rd) {
  const stubs = {};
  for (const n of wf.nodes) {
    if (!HTTP_TYPES.has(n.type) || !rd[n.name]) continue;
    const runs = rd[n.name];
    let calls = 0;
    stubs[n.name] = () => {
      const k = calls;
      calls += 1;
      if (k >= runs.length) {
        throw new Error(
          `${n.name}: call ${k} exceeds the ${runs.length} recorded run(s) — the walker ` +
          `called this node MORE times than the engine ran it live, a genuine ` +
          `misalignment (NT-02) rather than something safe to paper over by replaying ` +
          `the last recorded run`);
      }
      return runs[k].data.main[0].map((it) => it.json);
    };
  }
  return stubs;
}

function triggerItemsFromRecording(rd) {
  return [{ body: rd["Webhook Trigger"][0].data.main[0][0].json.body }];
}

function walkRecording(id) {
  const wf = JSON.parse(fs.readFileSync(FROZEN_V1_GRAPH, "utf8"));
  const recording = loadRecording(id);
  const rd = recording.runData;
  return walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    // No allowLegacy — the frozen copy IS v1, and reproducing 12354/12355/12356 on
    // anything else would not be a reproduction of what the engine ran.
    triggerItems: triggerItemsFromRecording(rd),
    httpStubs: httpStubsFromRecording(wf, rd),
  });
}

const EXECUTIONS = [12354, 12355, 12356];

for (const id of EXECUTIONS) {
  test(`execution ${id} (v1, Gate 11): the walker reproduces the engine's Decide Company Action Merge double-fire and Merge Company's non-delivery`, () => {
    const { runData, trace } = walkRecording(id);

    // Raw runData counts FIRST (D-70-19 Step 2: a clean assertion failure, not a TypeError
    // on an undefined `runs`, is what the pre-fix RED must look like).
    assert.equal(runData["Decide Company Action Merge"].length, 2,
      `${id}: Decide Company Action Merge must fire twice, exactly as the engine did`);
    assert.deepEqual(runData["Decide Company Action Merge"].map((r) => r.length), [2, 1],
      `${id}: run 0 carries 2 marker items (both inputs from the same sentinel gate), ` +
      `run 1 carries 1 (the end-of-run drain firing on a single arrived input)`);
    assert.equal(trace.merges["Decide Company Action Merge"].runs[1].sources[1], undefined,
      `${id}: run 1 input 1 must be UNFILLED — the drain fired on input 0 alone`);

    // BL-02 (quick task 260911-1z5): the two per-input source-attribution assertions the
    // 0tz REVIEW found omitted — the one recorded fact the walker got WRONG. Landed as
    // REAL (non-todo) assertions: BL-02's grouping fix (one producer node-run's
    // deliveries to several inputs of the same Merge land in ONE pending run, ATOMICALLY)
    // reproduces this exactly on all three executions, with NO dequeue-order change
    // needed (grouping alone was sufficient — see the plan's own Task A `<done>` record
    // in 260911-1z5-SUMMARY.md for the walker's actual sources at every state reached).
    const runs = trace.merges["Decide Company Action Merge"].runs;
    assert.deepEqual([runs[0].sources[0], runs[0].sources[1]],
      ["Companies Absent Sentinel Gate", "Companies Absent Sentinel Gate"],
      `${id}: run 0's single node-run producer must claim BOTH inputs`);
    assert.equal(runs[1].sources[0], "Recompute Not Requested Sentinel Gate",
      `${id}: run 1's input 0 must be claimed by the drain's actual producer`);

    // NF-MJ-02 (260911-1z5 review): the detector's report on the RECORDING itself, so
    // CLAUDE.md §13.0.3's claim that this file pins `merge_fired_with_unfilled_input`
    // against 12354/12355/12356 is true.
    assert.deepEqual(trace.stalled.filter((s) => s.node === "Decide Company Action Merge"),
      [{ node: "Decide Company Action Merge", reason: "merge_fired_with_unfilled_input",
         run: 1, missingInputs: [1] }],
      `${id}: the drained run-1 is reported as fired-with-unfilled-input, nothing else on that Merge`);
    assert.deepEqual(starvedWithData(trace), [], `${id}: nothing was actually lost on this execution`);

    assert.equal(runData["Decide Company Action"].length, 2,
      `${id}: Decide Company Action ran twice, once per Merge run`);
    assert.deepEqual(runData["Decide Company Action"].map((r) => r.length), [0, 0],
      `${id}: both runs filtered to zero items — markers only`);

    assert.equal(runData["Merge Company"][0].length, 0,
      `${id}: Merge Company ran and emitted zero items`);
    const decideMergeSources = trace.merges["Decide Company Action Merge"].runs
      .flatMap((r) => Object.values(r.sources));
    assert.ok(!decideMergeSources.includes("Merge Company"),
      `${id}: Merge Company's zero-item output must never appear as a source of Decide ` +
      `Company Action Merge — under v1 a zero-item output makes no delivery`);

    assert.equal(runData["Enrichment Gate Merge"].length, 1,
      `${id}: Enrichment Gate Merge fires exactly once`);
    assert.equal(runData["Enrichment Gate Merge"][0].length, 6,
      `${id}: 4 markers + 2 real rows`);

    // NOT nodeItems(...).length === 2 — that also passes on a 1+1 run split, the exact
    // collapse shape this instrument exists to see.
    assert.equal(runData["Build Response"].length, 1,
      `${id}: Build Response must run exactly once`);
    assert.equal(runData["Build Response"][0].length, 2,
      `${id}: both real rows reach Build Response in its single run`);

    assert.equal(runData["HubSpot Update"], undefined,
      `${id}: HubSpot Update must not run — disarmed propose-mode batch`);
  });
}

// --- D-74-03 pin: execution 12522 (ingest lane, zero-rejection create batch) --------------
//
// Two-part pin, deliberately NOT a full 46-row graph replay of 12522 (unlike the
// enrichment-lane family above, seeding this graph's real "Webhook Trigger" would require
// reproducing the whole multipart request envelope column-mapping config drives on, not
// just the extracted rows — out of scope for pinning one padding rule). Part 1 reads the
// recording directly (no walk) for the raw shape 74-CONTEXT.md's D-74-01 citation records.
// Part 2 drives the SAME committed graph with the corrected walker on a small synthetic
// create-only batch (the same idiom ingestCreateErrorLane.test.mjs's "zero-rejection
// batch" test already uses) and asserts the walker's OWN prediction agrees with the
// recording on the three points D-74-03 is actually about: alwaysOutputData rescues output
// 0 only, output 1 makes no delivery when empty, and the Merge drains exactly once.
const INGEST_WF_PATH = path.join(HERE, "..", "..", "n8n", "wf_contact_ingest_cloud.json");

test("execution 12522 (ingest lane, D-74-03): the RAW recording shows HubSpot Create " +
  "outs [21, 0] and Create Carry Merge drains once with 42 items, input 2 absent", () => {
  const recording = loadRecording(12522);
  const rd = recording.runData;

  assert.equal(rd["HubSpot Create"].length, 1, "HubSpot Create ran exactly once");
  assert.deepEqual((rd["HubSpot Create"][0].data.main || []).map((b) => (b || []).length), [21, 0],
    "output 0 (success) carries 21 items, output 1 (error) is empty — [VERIFIED live, " +
    "74-CONTEXT.md D-74-01]");

  assert.equal(rd["Create Carry Merge"].length, 1,
    "Create Carry Merge fired exactly once — the v1 end-of-run drain, not the main loop " +
    "(input 2 never delivered to complete it there)");
  assert.equal(rd["Create Carry Merge"][0].data.main[0].length, 42,
    "21 (HubSpot Create output 0) + 21 (Permitted Pass-Through) + 0 (output 1) = 42");

  assert.equal(rd["Build Association Request Merge"][0].data.main[0].length, 22);
  assert.equal(rd["Ingest Merge Response"].length, 1,
    "Ingest Merge Response fired once with every input delivered or sentinel-covered");
  assert.equal(rd["Build Ingest Response"][0].data.main[0].length, 46,
    "every one of the 46 input rows returned exactly once");
});

test("execution 12522 (ingest lane, D-74-03): the corrected walker's own prediction for " +
  "this same graph agrees — output 0 padded, output 1 makes no delivery, one drain run", () => {
  const wf = JSON.parse(fs.readFileSync(INGEST_WF_PATH, "utf8"));
  const decide = wf.nodes.find((n) => n.name === "Decide Action");
  decide.parameters.jsCode = decide.parameters.jsCode.replace(
    'const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";');
  // Phase 74 Plan 05 Task 3 (D-74-02): "Create Failure Row Sentinel" carries the same
  // baked write-safety constants — arm it too, or its own unarmed copy fires a marker
  // onto "Ingest Merge Response" input 5 alongside this batch's real delivery.
  for (const name of ["HubSpot Create Write Gate", "Associate Lane Sentinel", "Create Failure Row Sentinel"]) {
    const node = wf.nodes.find((n) => n.name === name);
    node.parameters.jsCode = node.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";')
      .replace('const TEST_RECORD_DOMAINS = "";', 'const TEST_RECORD_DOMAINS = "one.example,two.example";');
  }
  const items = [
    { email: "one@one.example", firstname: "One", lastname: "Row", company: "One Co" },
    { email: "two@two.example", firstname: "Two", lastname: "Row", company: "Two Co" },
  ];
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: items,
    httpStubs: {
      "Verify Emails (batch)": [{ results: items.map((r) => ({ email: r.email, status: "VALID" })) }],
      "HubSpot Search by Email": items.map(() => ({ results: [] })),
      "HubSpot Company Search by Domain": [
        { results: [{ id: "1", properties: { domain: "one.example" } }] },
        { results: [{ id: "2", properties: { domain: "two.example" } }] },
      ],
      "HubSpot Company Search by Name": items.map(() => ({ results: [] })),
      "HubSpot Create": [
        { id: "c1", properties: { email: "one@one.example" } },
        { id: "c2", properties: { email: "two@two.example" } },
      ],
      "HubSpot Associate Company": (rows) => rows.map(() => ({ status: "ok" })),
    },
  });

  assert.equal(runData["HubSpot Create"].length, 1);
  assert.equal(runData["HubSpot Create"][0].length, 2,
    "output 0 (success) carries both real rows — matches the RECORDING'S own non-empty-" +
    "output-0 shape, just at this test's own (smaller) scale");

  assert.equal(runData["Create Carry Merge"].length, 1,
    "Create Carry Merge fires exactly once — the same v1 end-of-run drain 12522 shows");
  const mergeRuns = trace.merges["Create Carry Merge"].runs;
  assert.equal(mergeRuns.length, 1);
  assert.equal(mergeRuns[0].sources[2], undefined,
    "input 2 (fed by HubSpot Create's error output) is UNFILLED — output 1 stayed empty " +
    "and alwaysOutputData did not rescue it (D-74-03: rescues output 0 only, never " +
    "whichever branch happens to be empty)");
  assert.deepEqual(
    trace.stalled.filter((s) => s.node === "Create Carry Merge"),
    [{ node: "Create Carry Merge", reason: "merge_fired_with_unfilled_input",
       run: 0, missingInputs: [2] }],
    "the by-design D-70-23 shape on a zero-rejection batch — matches 12522's own shape, " +
    "not a loss");
  assert.deepEqual(starvedWithData(trace), [], "nothing was actually lost");
});

// MN-06 (quick task 260911-1z5): nothing kept the frozen v1 graph honest after the next
// regeneration of n8n/wf_enrichment_cloud.json. One assertion, pinned as a digest, so a
// future regeneration that silently diverges from what 12354/12355/12356 actually ran
// goes RED here rather than continuing to pass against a copy that no longer reproduces
// anything.
test("the frozen v1 graph is byte-identical to what executions 12354/12355/12356 actually ran (MN-06)", () => {
  const digest = crypto.createHash("sha256")
    .update(fs.readFileSync(FROZEN_V1_GRAPH))
    .digest("hex");
  assert.equal(digest, "77a4e8c0137580c1b1d827586a2d600d1fbf2942e883596caeb58f77318eab7d",
    "this frozen copy must never be edited: it is the byte image of ec102a4's " +
    "n8n/wf_enrichment_cloud.json, the graph executions 12354/12355/12356 ran. A later " +
    "regeneration of n8n/ is EXPECTED to diverge from it (NF-MN-04) — that is not what " +
    "this test detects; only an edit to the frozen file is. Do not update this digest.");
});
