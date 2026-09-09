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
  ["wf_contact_ingest_cloud.json", INGEST, "HubSpot Associate Company Write Gate"],
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

test("enrichment lane (unchanged in this task): Decide Action's own empty-allowlist denial still holds", () => {
  const enrichment = loadWorkflow("wf_enrichment_cloud.json");
  const js = jsCodeOf(enrichment, "Decide Action");
  // Decide Action embeds _writeSafetyAllows itself (no spliced gate on this lane yet —
  // Task 2). Proving the shared allowlist function denies with nothing armed is a direct
  // structural check, not a behavioural run of the whole (very large) node.
  assert.match(js, /function _writeSafetyAllows/);
  assert.match(js, /empty allowlist denies everything/);
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
    [INGEST, "HubSpot Associate Company Write Gate"],
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

test("the enrichment lane's gate IF false branch lands on the SAME Build Response Merge input its write path already feeds — no new starvable input", () => {
  // The refusal and the success arrive on one channel (D-70-14). Reusing the existing
  // input index is what keeps the ~30-entry starved-lane sentinel network correct
  // without re-keying a single sentinel: every sentinel is keyed on the ROUTING IF's
  // predicate, and the gate sits strictly downstream of routing, always delivering on
  // exactly one of two outputs that both land here.
  const merge = "Build Response Merge";
  const indexOf = (src, outIdx) =>
    ((ENRICHMENT.connections[src] || {}).main || [])[outIdx]
      ?.filter((c) => c.node === merge).map((c) => c.index) ?? [];
  for (const [write, realProducer] of [
    ["HubSpot Create", "HubSpot Create"],
    ["HubSpot Update", "HubSpot Update"],
    ["HubSpot Company Update", "HubSpot Company Update"],
    ["HubSpot Company Create", "Adapt Company Create"],
  ]) {
    const real = indexOf(realProducer, 0);
    assert.equal(real.length, 1, `${realProducer} feeds ${merge} on exactly one index`);
    assert.deepEqual(indexOf(write + " Write Gate IF", 1), real,
      `${write}'s refusal lane must reuse ${realProducer}'s own ${merge} input index`);
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
  const carries = [
    ["wf_enrichment_cloud.json", ENRICHMENT, "HubSpot Company Create Carry Merge",
     "HubSpot Company Create Write Gate IF"],
    ["wf_contact_ingest_cloud.json", INGEST, "Update Carry Merge", "HubSpot Update Write Gate IF"],
    ["wf_contact_ingest_cloud.json", INGEST, "Create Carry Merge", "HubSpot Create Write Gate IF"],
    ["wf_contact_ingest_cloud.json", INGEST, "Associate Carry Merge",
     "HubSpot Associate Company Write Gate IF"],
  ];
  for (const [file, wf, mergeName, expectedSource] of carries) {
    const feeders = Object.entries(wf.connections).flatMap(([src, spec]) =>
      (spec.main || []).flatMap((outs, idx) =>
        (outs || []).filter((c) => c.node === mergeName && c.index === 1).map(() => [src, idx])));
    assert.deepEqual(feeders, [[expectedSource, 0]],
      `${file}: ${mergeName}'s carry input must come from ${expectedSource}'s true output`);
  }
});
