// tests/n8n/writeGateShape.test.mjs
//
// D-70-12 (Phase 70 Plan 05 Task 1): the canonical write_request contract — every gated
// write's upstream emits `{action, hs_object_id, domain, email}`, and the gate reads
// ONLY that shape. Runs the repo's OWN committed jsCode via `new Function` (the same
// mechanism n8n's Code node uses), over the actual committed workflow JSON files — no
// external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadWorkflow(name) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", name), "utf8"));
}

function jsCodeOf(wf, name) {
  const node = wf.nodes.find((n) => n.name === name);
  assert.ok(node, `node present: ${name}`);
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) against seed items, the same shape
 * n8n's Code node executes it under. Returns the resulting json objects. */
function runCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })), first: () => ({ json: seedItems[0] }) };
  const out = new Function("$input", `"use strict";\n${jsCode}`)($input) || [];
  return out.map((it) => it.json);
}

const INGEST = loadWorkflow("wf_contact_ingest_cloud.json");
const MAINTENANCE = loadWorkflow("wf_scheduled_maintenance_cloud.json");
const REVIEW = loadWorkflow("wf_review_decision_cloud.json");

// --- named case: gate jsCode references no identity key outside write_request --------
//
// The four-way fallback ladder this used to read directly: `existingRecord.hs_object_id`,
// `identity_keys.domain`, `properties.email`, bare `.email`. All four are gone; the only
// identity access left in any gate's own jsCode is through `write_request` (aliased
// `wr` below by every gate this plan built).
const GATES = [
  ["wf_contact_ingest_cloud.json", INGEST, "HubSpot Update Write Gate"],
  ["wf_contact_ingest_cloud.json", INGEST, "HubSpot Create Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "SJ-1 Set Requested Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "SJ-2 Set Requested Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "Dedupe Set Needs Review Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "Review Apply Update Write Gate"],
  ["wf_review_decision_cloud.json", REVIEW, "Review Decision Update Write Gate"],
  ["wf_review_decision_cloud.json", REVIEW, "Review Contact Decision Update Write Gate"],
];

for (const [fileName, wf, gateName] of GATES) {
  test(`${fileName}: ${gateName} reads only write_request (no identity fallback ladder)`, () => {
    const js = jsCodeOf(wf, gateName);
    assert.match(js, /it\.json\.write_request/, "gate must read it.json.write_request");
    for (const legacyKey of ["identity_keys", "existingRecord", "properties.email", "it.json.email", "it.json.domain"]) {
      assert.ok(!js.includes(legacyKey), `${gateName} must not reference legacy identity key ${legacyKey}`);
    }
  });
}

// --- named case: an empty allowlist denies on all four lanes --------------------------
//
// Ingest (create), scheduled-maintenance (enrich), review-decision (review) all go
// through splice_write_gates' gate. D-70-14 (Phase 70 Plan 05 Task 2): the gate's Code
// node now STAMPS a verdict onto every item rather than filtering any away — length
// stays 1 in every case below; the permit/deny signal is `write_allowed`. The
// enrichment lane has no spliced gate yet (Task 2's own remaining work) — its OWN
// inline _writeSafetyAllows call is unchanged by this task, and an empty allowlist
// denies there too, proved directly against Decide Action's committed jsCode.
test("ingest: HubSpot Create Write Gate denies a fully-identified row with an empty allowlist", () => {
  const js = jsCodeOf(INGEST, "HubSpot Create Write Gate");
  const row = { action: "create", write_request: { action: "create", hs_object_id: null, domain: "exampleco.example", email: "jo@exampleco.example" } };
  const out = runCode(js, [row]);
  assert.equal(out.length, 1, "committed (disarmed) build must still emit the row (D-70-14, no drop)");
  assert.equal(out[0].write_allowed, false, "committed (disarmed) build must deny — empty allowlist");
});

test("scheduled-maintenance: SJ-1 Set Requested Write Gate denies a fully-identified row with an empty allowlist", () => {
  const js = jsCodeOf(MAINTENANCE, "SJ-1 Set Requested Write Gate");
  const row = { write_request: { action: "enrich", hs_object_id: "999", domain: "exampleco.example", email: null } };
  const out = runCode(js, [row]);
  assert.equal(out.length, 1, "committed (disarmed) build must still emit the row (D-70-14, no drop)");
  assert.equal(out[0].write_allowed, false, "committed (disarmed) build must deny — empty allowlist");
});

test("review-decision: Review Decision Update Write Gate denies a fully-identified row with an empty allowlist", () => {
  const js = jsCodeOf(REVIEW, "Review Decision Update Write Gate");
  const row = { write_request: { action: "review", hs_object_id: "999", domain: null, email: null } };
  const out = runCode(js, [row]);
  assert.equal(out.length, 1, "committed (disarmed) build must still emit the row (D-70-14, no drop)");
  assert.equal(out[0].write_allowed, false, "committed (disarmed) build must deny — empty allowlist");
});

test("enrichment lane: the empty-allowlist denial now comes from the spliced gate, not Decide Action", () => {
  // Task 2 sub-step 2b moved the predicate out of "Decide Action" and into the lane's
  // own gate. The denial itself is unchanged — proved behaviourally here, on the
  // committed (disarmed) build, for each of the lane's four gates.
  const enrichment = loadWorkflow("wf_enrichment_cloud.json");
  for (const [gate, action] of [
    ["HubSpot Create Write Gate", "create"],
    ["HubSpot Update Write Gate", "enrich"],
    ["HubSpot Company Create Write Gate", "create"],
    ["HubSpot Company Update Write Gate", "enrich"],
  ]) {
    const js = jsCodeOf(enrichment, gate);
    assert.match(js, /function _writeSafetyAllows/);
    assert.match(js, /empty allowlist denies everything/);
    const out = runCode(js, [
      { write_request: { action, hs_object_id: "999", domain: "armed.example", email: null } },
    ]);
    assert.equal(out.length, 1, `${gate}: committed build must still EMIT the row (D-70-14)`);
    assert.equal(out[0].write_allowed, false, `${gate}: empty allowlist must deny`);
    assert.equal(out[0].action, "write_blocked");
  }
});

// --- named case: the review lane's emitted write_request carries a null domain --------
//
// D-70-13: "Build Review Decision" forces domain: null regardless of object type — the
// review lane's contacts-stay-id-only rule (30-02) is now an emitted VALUE, applying
// uniformly to both write nodes this one node feeds.
test("review lane: Build Review Decision always emits write_request.domain === null", () => {
  const js = jsCodeOf(REVIEW, "Build Review Decision");
  assert.match(js, /_buildWriteRequest\("review",\s*row\.hs_object_id \|\| null,\s*null,/,
    "the domain argument to _buildWriteRequest must be the literal null, not a row field");
});

// --- named case: a fully-refused two-row batch never reduces item count below input ---
//
// D-70-14 (Phase 70 Plan 05 Task 2): the gate's Code node stamps a verdict on every
// item and never filters — a fully refused batch still produces one row per input row
// at the gate itself, each carrying `action: "write_blocked"` and a reason. (Whether
// that refusal reaches a lane's response builder is a separate, per-lane routing
// question — Task 2c/3's job, tracked in 70-05-SUMMARY.md's "Next Phase Readiness".
// This case only pins the gate's OWN non-dropping contract.)
test("ingest: HubSpot Update Write Gate stamps both rows write_blocked rather than dropping either", () => {
  const js = jsCodeOf(INGEST, "HubSpot Update Write Gate");
  const rows = [
    { action: "update", write_request: { action: "enrich", hs_object_id: "1", domain: null, email: null } },
    { action: "update", write_request: { action: "enrich", hs_object_id: "2", domain: null, email: null } },
  ];
  const out = runCode(js, rows);
  assert.equal(out.length, 2, "disarmed gate emits both rows (D-70-14 — no filtering)");
  assert.ok(out.every((r) => r.write_allowed === false && r.action === "write_blocked" && r.write_blocked_reason));
});

// --- named case: a gate node's jsCode never reduces output below input count ----------
test("every spliced write gate's Code node preserves item count on a mixed permit/refuse batch", () => {
  const gateCases = [
    [INGEST, "HubSpot Update Write Gate"],
    [INGEST, "HubSpot Create Write Gate"],
    [MAINTENANCE, "SJ-1 Set Requested Write Gate"],
    [MAINTENANCE, "SJ-2 Set Requested Write Gate"],
    [MAINTENANCE, "Dedupe Set Needs Review Write Gate"],
    [MAINTENANCE, "Review Apply Update Write Gate"],
    [REVIEW, "Review Decision Update Write Gate"],
    [REVIEW, "Review Contact Decision Update Write Gate"],
  ];
  for (const [wf, gateName] of gateCases) {
    const js = jsCodeOf(wf, gateName);
    const rows = [
      { write_request: { action: "enrich", hs_object_id: "1", domain: null, email: null } },
      { write_request: null },
    ];
    assert.equal(runCode(js, rows).length, 2, `${gateName}: output count must equal input count`);
  }
});

// =============================================================================================
// Phase 70 Plan 05 Task 2 sub-step 2b — the enrichment lane's FIRST-EVER spliced gate.
// Before this sub-step the enrichment lane decided write permission inline inside
// "Decide Action"/"Decide Company Action"; D-70-13 moves that predicate to one home per
// lane, so the lane gains four real gates it has never had.
// =============================================================================================

const ENRICHMENT = loadWorkflow("wf_enrichment_cloud.json");

test("the enrichment lane has a spliced two-node gate in front of each of its four HubSpot writes", () => {
  for (const write of ["HubSpot Create", "HubSpot Update",
                       "HubSpot Company Update", "HubSpot Company Create"]) {
    for (const suffix of [" Write Gate", " Write Gate IF"]) {
      const name = write + suffix;
      assert.ok(ENRICHMENT.nodes.some((n) => n.name === name),
        `wf_enrichment_cloud.json must contain ${name}`);
    }
    // the write node's ONLY inbound edge is its own gate IF's true output
    const inbound = Object.entries(ENRICHMENT.connections).flatMap(([src, spec]) =>
      (spec.main || []).flatMap((outs, idx) =>
        (outs || []).filter((c) => c.node === write).map(() => [src, idx])));
    assert.deepEqual(inbound, [[write + " Write Gate IF", 0]],
      `${write} is reachable only through its gate's true branch`);
  }
});

test("the enrichment lane's gate IF false branch has its OWN Build Response Merge input, never a share of the write path's", () => {
  // Sharing the write terminal's input was tried FIRST and is wrong: on an armed batch
  // with a MIXED verdict the refusal (zero hops from the gate) beats the permitted row's
  // real multi-hop delivery to the shared input, the Merge fires and locks, and the real
  // arrival is dropped. Caught by driving the committed graph through the walker, not by
  // reasoning — see the armed-mixed case at the end of this file. A marker may share an
  // input (no data, filtered downstream); two REAL producers may not.
  // Phase 70 Plan 11 (D-70-20): "Build Response Merge" no longer receives these edges
  // directly — it was split into lane-grouped STAGE merges (each within n8n's own
  // ten-input cap), and every routing-IF-direct edge (including these two write-gate
  // edges) now runs through a pass-through first (no routing IF has a direct edge to
  // a Merge input on this lane any more). `resolveStageInput` follows AT MOST one
  // pass-through hop and lands on the (stage merge, index) pair that is this input's
  // real identity now — "own dedicated input" is asserted at that level, not against
  // the now-3-input top merge every write shares.
  const isMerge = (name) => {
    const n = ENRICHMENT.nodes.find((x) => x.name === name);
    return Boolean(n && n.type === "n8n-nodes-base.merge");
  };
  const resolveStageInput = (src, outIdx) => {
    const targets = ((ENRICHMENT.connections[src] || {}).main || [])[outIdx] || [];
    const out = [];
    for (const c of targets) {
      if (isMerge(c.node)) { out.push({ stage: c.node, index: c.index }); continue; }
      const next = ((ENRICHMENT.connections[c.node] || {}).main || [])[0] || [];
      for (const c2 of next) if (isMerge(c2.node)) out.push({ stage: c2.node, index: c2.index });
    }
    return out;
  };
  const realProducers = {
    "HubSpot Create": "HubSpot Create",
    "HubSpot Update": "HubSpot Update",
    "HubSpot Company Update": "HubSpot Company Update",
    "HubSpot Company Create": "Adapt Company Create",
  };
  const seen = new Set();
  for (const [write, realProducer] of Object.entries(realProducers)) {
    const real = resolveStageInput(realProducer, 0);
    assert.equal(real.length, 1, `${realProducer} feeds a stage Merge on exactly one input`);
    const refusal = resolveStageInput(write + " Write Gate IF", 1);
    assert.equal(refusal.length, 1, `${write}'s refusal feeds a stage Merge on exactly one input`);
    assert.notDeepEqual(refusal[0], real[0], `${write}'s refusal must not share the write path's input`);
    const refusalKey = `${refusal[0].stage}:${refusal[0].index}`;
    assert.ok(!seen.has(refusalKey), `${write}'s refusal input is its own`);
    seen.add(refusalKey);

    // ...and both inputs are covered on the ways their own producer can fail to deliver.
    // Phase 70 Plan 10 (D-70-23): a sentinel's own outgoing edge no longer points at a
    // Merge input directly — `_add_starved_lane_sentinel` now wires "condition -> gate
    // -> targets", and the GATE is the only node with edges to `targets` (the class fix
    // for the sentinel-pre-empts-a-real-row defect, executions 12204-12206). Assert the
    // gate node's presence, not the sentinel Code node's — the OLD wiring this test used
    // to pin is exactly the shape that no longer exists.
    const feeders = (stage, idx) => Object.entries(ENRICHMENT.connections)
      .filter(([, spec]) => (spec.main || []).some((outs) =>
        (outs || []).some((c) => c.node === stage && c.index === idx)))
      .map(([src]) => src);
    assert.ok(feeders(refusal[0].stage, refusal[0].index).includes(`${write} No Refusal Sentinel Gate`),
      `${write}: the refusal input needs a marker when the gate refused nothing`);
    assert.ok(feeders(real[0].stage, real[0].index).includes(`${write} All Refused Sentinel Gate`),
      `${write}: the write input needs a marker when the gate allowed nothing`);
  }
});


test("neither enrichment Decide node computes write permission any more — one home per lane", () => {
  for (const name of ["Decide Action", "Decide Company Action"]) {
    const js = jsCodeOf(ENRICHMENT, name);
    assert.ok(!js.includes("_writeSafetyAllows("),
      `${name} must not call _writeSafetyAllows — the gate owns that decision now`);
    assert.ok(js.includes("_buildWriteRequest("),
      `${name} must emit the canonical write_request instead`);
  }
});

test("the enrichment lane's carry merges pair with the gate IF's TRUE output, never the gate Code node (count mismatch)", () => {
  // The gate Code node stamps EVERY row (refused included); the write node receives only
  // the permitted subset. A combineByPosition carry merge fed from the Code node would
  // pair row i of the HTTP response with row i of the FULL wave on any partially-refused
  // batch. The IF's true output is the wave that actually entered the write node.
  //
  // Phase 70 Plan 10 (D-70-23)'s ingest-lane audit found the routing-IF-direct-edge-
  // to-Merge-input shape and retargeted it through a pass-through
  // (`_retarget_merge_edge_through_passthrough`), named `f"{write} Permitted
  // Pass-Through"` (the ingest lane's own hand-chosen name). Phase 70 Plan 11
  // (D-70-20) closed the SAME gap on the enrichment lane's own gate IF, via the
  // generic `_retarget_all_if_direct_edges` helper, whose pass-through names follow
  // the generic `f"{source} -> {merge_name} Pass-Through"` pattern instead — a
  // DIFFERENT literal name, same structural shape ("passthrough-generic" below).
  const carries = [
    ["wf_enrichment_cloud.json", ENRICHMENT, "HubSpot Company Create Carry Merge",
     "HubSpot Company Create Write Gate IF", "passthrough-generic"],
    ["wf_contact_ingest_cloud.json", INGEST, "Update Carry Merge",
     "HubSpot Update Write Gate IF", "passthrough"],
    ["wf_contact_ingest_cloud.json", INGEST, "Create Carry Merge",
     "HubSpot Create Write Gate IF", "passthrough"],
    // "Associate Carry Merge" carries from "Build Association Request": Task 3 (D-70-15)
    // removed the association's own second gate, so its direct predecessor IS the carry
    // source again — one verdict, taken at the update/create gate upstream. Not an IF,
    // so no pass-through question applies.
    ["wf_contact_ingest_cloud.json", INGEST, "Associate Carry Merge",
     "Build Association Request", "direct"],
  ];
  const feedersOf = (wf, mergeName) => Object.entries(wf.connections).flatMap(([src, spec]) =>
    (spec.main || []).flatMap((outs, idx) =>
      (outs || []).filter((c) => c.node === mergeName && c.index === 1).map(() => [src, idx])));
  for (const [file, wf, mergeName, expectedSource, shape] of carries) {
    if (shape === "direct") {
      const feeders = feedersOf(wf, mergeName);
      // A starved-lane sentinel may ALSO feed this input (D-70-01) — what must not
      // appear is the gate's Code node, whose item count includes the refused rows.
      assert.ok(feeders.some(([src, idx]) => src === expectedSource && idx === 0),
        `${file}: ${mergeName}'s carry input must come from ${expectedSource}'s true output`);
      if (expectedSource.endsWith(" Write Gate IF")) {
        assert.ok(!feeders.some(([src]) => src === expectedSource.slice(0, -3)),
          `${file}: ${mergeName} must not be carried from the gate Code node (count mismatch)`);
      }
    } else {
      // "passthrough" / "passthrough-generic": the IF's true branch feeds a
      // pass-through, and the pass-through — never the IF itself — feeds the carry
      // Merge's input 1. Only the NAME the two retarget helpers chose differs.
      const passthroughName = shape === "passthrough-generic"
        ? `${expectedSource} -> ${mergeName} Pass-Through`
        : `${expectedSource.slice(0, -" Write Gate IF".length)} Permitted Pass-Through`;
      const feeders = feedersOf(wf, mergeName);
      assert.ok(feeders.some(([src]) => src === passthroughName),
        `${file}: ${mergeName}'s carry input must come from ${passthroughName}`);
      assert.ok(!feeders.some(([src]) => src === expectedSource),
        `${file}: ${mergeName} must not be carried directly from ${expectedSource} any more`);
      const ifTrueFeedsPassthrough = ((wf.connections[expectedSource] || {}).main || [])[0]
        ?.some((c) => c.node === passthroughName);
      assert.ok(ifTrueFeedsPassthrough,
        `${file}: ${passthroughName} must be fed from ${expectedSource}'s true output`);
    }
  }
});

// --- walker-driven: a FULLY REFUSED batch still produces one row per input row --------
//
// D-70-14's whole point, and the shape that dead-ended before: with nothing armed the
// gate refuses every row, and the response builder must still see two rows for a two-row
// batch, with "Build Response Merge" satisfied (never stalled). Drives the COMMITTED
// wf_enrichment_cloud.json through tests/n8n/lib/walkWorkflow.mjs — no live n8n call.
test("enrichment lane: a fully refused two-row batch produces exactly two rows at the response builder, with no stalled merge", async () => {
  const { walkWorkflow, loadWorkflow: loadWf, nodeItems, starvedWithData } =
    await import("./lib/walkWorkflow.mjs");
  const wf = loadWf(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"));
  const events = ["11", "22"].map((id) => ({
    objectId: id, objectType: "company", domain: `co-${id}.example`,
    recompute: true, row_id: `row-${id}`,
  }));
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { run_id: "case-refused-batch", events } }],
    httpStubs: {
      "HubSpot Company Search": [
        { results: [{ id: "11", properties: { domain: "co-11.example", name: "Co 11" } }] },
        { results: [{ id: "22", properties: { domain: "co-22.example", name: "Co 22" } }] },
      ],
      "HubSpot Company Name Search": [{ results: [] }, { results: [] }],
    },
  });
  assert.deepEqual(starvedWithData(trace), [], "no merge may stall on a fully refused batch");
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 2, "one row per input row reaches the response builder");
  for (const r of rows) {
    assert.equal(r.action, "write_blocked", "the refusal is an EMITTED row, not a silence");
    assert.ok(r.write_blocked_reason, "and it carries the gate's reason");
  }
  assert.deepEqual(rows.map((r) => r.row_id).sort(), ["row-11", "row-22"]);
});

// =============================================================================================
// Phase 70 Plan 05 Task 2 sub-step 2c (D-70-06) + Task 3 (D-70-15) — the ingest lane.
// The pre-write refusal precheck is removed rather than extended to create rows, and an
// update and its association share ONE write_request and ONE allowlist verdict.
// =============================================================================================

/** jsCode with `//` comment lines dropped — a node's prose may legitimately NAME a
 * function it no longer calls. */
function codeOf(wf, name) {
  return jsCodeOf(wf, name)
    .split("\n").filter((l) => !l.trim().startsWith("//")).join("\n");
}

test("ingest: the pre-write refusal precheck is gone from Decide Action (D-70-06)", () => {
  const js = codeOf(INGEST, "Decide Action");
  assert.ok(!js.includes("_writeSafetyAllows("),
    "the row's outcome of record is the write node's own output — a precheck that " +
    "PREDICTS the gate's verdict is a second copy of the predicate that can disagree");
  assert.ok(js.includes("_buildWriteRequest("));
});

test("ingest: ONE gate covers both the update and its association (D-70-15)", () => {
  assert.ok(!INGEST.nodes.some((n) => n.name === "HubSpot Associate Company Write Gate"),
    "the association's second allowlist verdict is removed — it runs only downstream of " +
    "a write that already passed a gate");
  const inbound = Object.entries(INGEST.connections).flatMap(([src, spec]) =>
    (spec.main || []).flatMap((outs, idx) =>
      (outs || []).filter((c) => c.node === "HubSpot Associate Company").map(() => [src, idx])));
  assert.deepEqual(inbound, [["Build Association Request", 0]]);
});

test("ingest: each gate's refusal lane has its OWN Ingest Merge Response input, with both its sentinels", () => {
  // Phase 70 Plan 10 (D-70-23): two structural changes to what this test pins.
  // (1) The write gate IF's false branch no longer feeds `merge` directly — a
  //     pass-through sits between them (`_retarget_merge_edge_through_passthrough`),
  //     because no routing IF has a direct edge to a Merge input on this lane's
  //     contract any more.
  // (2) A sentinel's own outgoing edge no longer feeds `merge` directly either —
  //     `_add_starved_lane_sentinel` now wires "condition -> gate -> targets", and
  //     the gate is the only node with edges to `merge`.
  const merge = "Ingest Merge Response";
  const indexOf = (src, outIdx) =>
    ((INGEST.connections[src] || {}).main || [])[outIdx]
      ?.filter((c) => c.node === merge).map((c) => c.index) ?? [];
  const assocIdx = indexOf("Associate Carry Merge", 0);
  assert.equal(assocIdx.length, 1);
  const seen = new Set(assocIdx);
  for (const write of ["HubSpot Update", "HubSpot Create"]) {
    const refusal = indexOf(`${write} Refusal Pass-Through`, 0);
    assert.equal(refusal.length, 1);
    assert.ok(!seen.has(refusal[0]), `${write}'s refusal input is its own, never shared`);
    seen.add(refusal[0]);
    const feeders = Object.entries(INGEST.connections)
      .filter(([, spec]) => (spec.main || []).some((outs) =>
        (outs || []).some((c) => c.node === merge && c.index === refusal[0])))
      .map(([src]) => src).sort();
    assert.deepEqual(feeders, [
      `${write} Gate Unreached Sentinel Gate`,
      `${write} No Refusal Sentinel Gate`,
      `${write} Refusal Pass-Through`,
    ].sort(), `${write}: the refusal input is fed on every way its producer can be silent`);
  }
});


test("ingest: Associate Lane Sentinel asks whether the association lane can deliver AT ALL, company_id included", () => {
  // Once the precheck is gone a row can be action update/create and still never reach
  // "HubSpot Associate Company" — "Build Association Request" drops any row with no
  // resolved company (CLAUDE.md §13.0.1: an update is never HELD for lack of a company,
  // it simply has nothing to associate). The sentinel is graph plumbing and must ask the
  // same question the lane actually answers.
  const js = jsCodeOf(INGEST, "Associate Lane Sentinel");
  assert.match(js, /company_id/,
    "a batch of updates with no resolved company would otherwise starve Associate Carry Merge");
});

test("ingest: Build Ingest Response reports the GATE's verdict, not the pre-write intention (D-70-06)", () => {
  const js = jsCodeOf(INGEST, "Build Ingest Response");
  assert.match(js, /write_blocked/,
    "with the precheck gone, the decided snapshot still says 'update' for a row the gate " +
    "refused — F11/execution 12181's exact misreport unless the gate's own emitted row " +
    "overrides it here");
});

// --- walker-driven: the ingest lane's two newly-reachable starvation shapes -----------
//
// Both become reachable only once the D-70-06 precheck is removed. Before that, every
// refused row was relabelled "write_blocked" inside "Decide Action" and fell through both
// routing IFs to "Set Review", so neither case could occur.
async function walkIngest({ triggerItems, httpStubs }) {
  const { walkWorkflow, loadWorkflow: loadWf, nodeItems, starvedWithData } =
    await import("./lib/walkWorkflow.mjs");
  const wf = loadWf(path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json"));
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger", triggerItems, httpStubs,
  });
  const ran = (name) => (nodeItems(runData, name) || []).length > 0;
  return {
    trace, ran, rows: nodeItems(runData, "Build Ingest Response"),
    noRealLoss: starvedWithData(trace),
  };
}

const INGEST_EMAIL = "solo@wyongraceclub.com.au";

test("ingest: a batch of nothing but REFUSED updates still reaches Build Ingest Response, one row, reported blocked", async () => {
  const { trace, ran, rows, noRealLoss } = await walkIngest({
    triggerItems: [{ email: INGEST_EMAIL, firstname: "Solo", lastname: "Person", company: "Wyong Race Club" }],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: INGEST_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{ results: [{ id: "35551", properties: { email: INGEST_EMAIL } }] }],
      "HubSpot Company Search by Domain": [
        { results: [{ id: "9600000001", properties: { domain: "wyongraceclub.com.au" } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
    },
  });
  assert.deepEqual(noRealLoss, [],
    "Ingest Merge Response must never stall — the gate's refusal lane feeds it directly");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].action, "write_blocked",
    "the gate's verdict, not the pre-write intention (F11 / execution 12181)");
  assert.notEqual(rows[0].association, "associated");
  // D-70-15: one verdict covers both — a refused row runs NEITHER.
  assert.equal(ran("HubSpot Update"), false, "the refused write must not have run");
  assert.equal(ran("HubSpot Associate Company"), false,
    "and neither must its association");
});

test("ingest: a batch of updates that resolve NO company does not stall — an update is never held for lack of a company", async () => {
  // Task 3 / CLAUDE.md §13.0.1. "Build Association Request" drops a row with no company,
  // so on this batch the association lane delivers nothing at all — which is why
  // "Associate Lane Sentinel" has to ask about company_id, not just row.action.
  const { trace, rows, noRealLoss } = await walkIngest({
    triggerItems: [{ email: INGEST_EMAIL, firstname: "Solo", lastname: "Person", company: "Nowhere Pty" }],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: INGEST_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{ results: [{ id: "35551", properties: { email: INGEST_EMAIL } }] }],
      "HubSpot Company Search by Domain": [{ results: [] }],
      "HubSpot Company Search by Name": [{ results: [] }],
    },
  });
  assert.deepEqual(noRealLoss, []);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].association, "none", "nothing to associate, and nothing held");
});

// --- walker-driven: an ARMED batch with a MIXED verdict on ONE gate -------------------
//
// The case that ruled out sharing the write path's Merge input, and the primary armed use
// case of an allowlist: two update rows, both with a resolved company, only one on the
// allowlist. With the refusal sharing the write terminal's input, the refused row's
// zero-hop delivery satisfied "Ingest Merge Response" first, the Merge fired and locked,
// and the PERMITTED row's real association arrival was dropped — it came back
// `association: "not_confirmed"` when HubSpot had in fact associated it. Nothing stalls
// in that failure mode and every disarmed test stays green, which is exactly why this
// case is pinned here rather than trusted to reasoning.
const MIX_A = "allowed@acme-domain.example";
const MIX_B = "refused@acme-domain.example";

test("ingest, ARMED with a mixed verdict: the permitted row keeps its association and the refused row reports blocked", async () => {
  const { walkWorkflow, loadWorkflow: loadWf, nodeItems, starvedWithData } =
    await import("./lib/walkWorkflow.mjs");
  const wf = loadWf(path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json"));
  // Arm EVERY declaring node, the way n8n_arming.set_write_safety does — the gate and
  // the Merge-feeding sentinel that duplicates its predicate for plumbing.
  for (const name of ["HubSpot Update Write Gate", "Associate Lane Sentinel"]) {
    const n = wf.nodes.find((x) => x.name === name);
    assert.ok(n, `node present: ${name}`);
    n.parameters.jsCode = n.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
               'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const TEST_RECORD_IDS = "";', 'const TEST_RECORD_IDS = "111";');
  }
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: MIX_A, firstname: "Al", lastname: "Lowed", company: "Acme Domain Co" },
      { email: MIX_B, firstname: "Re", lastname: "Fused", company: "Acme Domain Co" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [
        { email: MIX_A, status: "VALID" }, { email: MIX_B, status: "VALID" }] }],
      "HubSpot Search by Email": [
        { results: [{ id: "111", properties: { email: MIX_A } }] },
        { results: [{ id: "222", properties: { email: MIX_B } }] },
      ],
      "HubSpot Company Search by Domain": [
        { results: [{ id: "900", properties: { domain: "acme-domain.example" } }] },
        { results: [{ id: "900", properties: { domain: "acme-domain.example" } }] },
      ],
      "HubSpot Company Search by Name": [{ results: [] }, { results: [] }],
      "HubSpot Update": [{ id: "111", properties: { email: MIX_A } }],
      "HubSpot Associate Company": [{ status: "ok" }],
    },
  });
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal((runData["Ingest Merge Response"] || []).length, 1,
    "the response Merge fires exactly once — a second run would double every reported row");
  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 2);
  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));
  assert.equal(byEmail[MIX_A].action, "update");
  assert.equal(byEmail[MIX_A].association, "associated",
    "the permitted row's real association arrival must not be beaten to the Merge by the refusal");
  assert.equal(byEmail[MIX_B].action, "write_blocked");
  assert.notEqual(byEmail[MIX_B].association, "associated");
});
