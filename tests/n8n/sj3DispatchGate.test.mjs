// tests/n8n/sj3DispatchGate.test.mjs
//
// Phase 44 Plan 01 — the SJ-3 dispatch gate + drain, in the two-layer shape
// reviewLoop.test.mjs establishes: (1) direct import-and-call of the pure module
// n8n/code/sj3DispatchGate.js, full branch coverage with no n8n runtime; (2) structural
// wiring assertions on the BUILT n8n/wf_scheduled_maintenance_cloud.json (run
// `python scripts/build_cloud_workflows.py` first), so a drift between the builder and
// this test is directly visible.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { sj3Gate } = require(path.join(ROOT, "n8n/code/sj3DispatchGate.js"));

function assertMutuallyExclusive(rows) {
  for (const row of rows) {
    assert.equal(typeof row.sj3_dispatch, "boolean");
    assert.equal(typeof row.sj3_drain, "boolean");
    assert.notEqual(row.sj3_dispatch, row.sj3_drain,
      "sj3_dispatch and sj3_drain must be mutually exclusive on every row, always");
  }
}

// --- (1) pure module -------------------------------------------------------------------

test("sj3Gate: allows-true for all rows -> all sj3_dispatch, input order, payload untouched", () => {
  const rows = [
    { hs_object_id: "1", domain: "a.example", lv_enrichment_requested: "true" },
    { hs_object_id: "2", domain: "b.example", lv_enrichment_requested: "true" },
  ];
  const out = sj3Gate(rows, { allows: () => true });
  assert.equal(out.length, 2);
  assert.deepEqual(out.map((r) => r.hs_object_id), ["1", "2"], "input order preserved");
  for (const [i, row] of out.entries()) {
    assert.equal(row.sj3_dispatch, true);
    assert.equal(row.sj3_drain, false);
    // payload otherwise untouched
    const { sj3_dispatch, sj3_drain, ...rest } = row;
    assert.deepEqual(rest, rows[i]);
  }
  assertMutuallyExclusive(out);
});

test("sj3Gate: allows-false for all rows -> all sj3_drain", () => {
  const out = sj3Gate([{ hs_object_id: "1" }, { hs_object_id: "2" }], { allows: () => false });
  assert.equal(out.length, 2);
  for (const row of out) {
    assert.equal(row.sj3_dispatch, false);
    assert.equal(row.sj3_drain, true);
  }
  assertMutuallyExclusive(out);
});

test("sj3Gate: mixed -> exactly the permitted subset dispatches, exactly the declined subset drains, no row both", () => {
  const rows = [
    { hs_object_id: "1" }, { hs_object_id: "2" }, { hs_object_id: "3" }, { hs_object_id: "4" },
  ];
  const permitted = new Set(["2", "4"]);
  const out = sj3Gate(rows, { allows: (row) => permitted.has(row.hs_object_id) });
  assert.deepEqual(out.filter((r) => r.sj3_dispatch).map((r) => r.hs_object_id), ["2", "4"]);
  assert.deepEqual(out.filter((r) => r.sj3_drain).map((r) => r.hs_object_id), ["1", "3"]);
  assert.equal(out.filter((r) => r.sj3_dispatch && r.sj3_drain).length, 0);
  assertMutuallyExclusive(out);
});

test("sj3Gate: empty input returns an empty array, throws nothing", () => {
  assert.deepEqual(sj3Gate([], { allows: () => true }), []);
  assert.deepEqual(sj3Gate(undefined, { allows: () => true }), []);
});

test("sj3Gate: a non-boolean truthy predicate result does not dispatch (allows must return true)", () => {
  // fail-closed: only a literal `true` permits — a predicate leaking a truthy object
  // (e.g. a row) must not widen dispatch.
  const out = sj3Gate([{ hs_object_id: "1" }], { allows: () => ({ oops: 1 }) });
  assert.equal(out[0].sj3_dispatch, false);
  assert.equal(out[0].sj3_drain, true);
});

test("sj3Gate: missing/absent allows predicate fails closed (everything drains)", () => {
  const out = sj3Gate([{ hs_object_id: "1" }], {});
  assert.equal(out[0].sj3_dispatch, false);
  assert.equal(out[0].sj3_drain, true);
});

// --- (2) workflow wiring ----------------------------------------------------------------

const WF_PATH = path.join(ROOT, "n8n/wf_scheduled_maintenance_cloud.json");

function loadWorkflow() {
  return JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
}

function findNode(wf, name) {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node "${name}" must exist in ${path.basename(WF_PATH)}`);
  return n;
}

function successors(wf, name) {
  const spec = wf.connections[name];
  assert.ok(spec, `node "${name}" must have outgoing connections`);
  return spec.main.flat().map((c) => c.node);
}

test("wiring: the permitted path reaches the Execute Workflow terminal through Build Dispatch Event", () => {
  const wf = loadWorkflow();
  const gate = findNode(wf, "SJ-3 Dispatch Gate");
  assert.equal(gate.type, "n8n-nodes-base.code");
  // D-02: one definition of "permitted" — the gate embeds the shared write-safety
  // predicate verbatim and routes through the pure module.
  assert.match(gate.parameters.jsCode, /_writeSafetyAllows\("enrich"/);
  assert.match(gate.parameters.jsCode, /sj3Gate\(/);
  assert.ok(successors(wf, "SJ-3 Dispatch Gate").includes("SJ-3 Build Dispatch Event"));
  const build = findNode(wf, "SJ-3 Build Dispatch Event");
  assert.match(build.parameters.jsCode, /sj3_dispatch === true/,
    "Build Dispatch Event must filter to permitted rows (GATE-01: declined rows never dispatch)");
  assert.deepEqual(successors(wf, "SJ-3 Build Dispatch Event"), ["SJ-3 Dispatch To Enrichment"]);
  const dispatch = findNode(wf, "SJ-3 Dispatch To Enrichment");
  assert.equal(dispatch.type, "n8n-nodes-base.executeWorkflow");
});

test("wiring: the declined path reaches SJ-3 Drain Clear Flag through SJ-3 Drain Gate", () => {
  const wf = loadWorkflow();
  assert.ok(successors(wf, "SJ-3 Dispatch Gate").includes("SJ-3 Drain Gate"),
    "the Drain Gate is a second consumer of the Dispatch Gate's single output (fan-out)");
  const drainGate = findNode(wf, "SJ-3 Drain Gate");
  assert.match(drainGate.parameters.jsCode, /sj3_drain === true/);
  assert.deepEqual(successors(wf, "SJ-3 Drain Gate"), ["SJ-3 Drain Clear Flag"]);
  const clear = findNode(wf, "SJ-3 Drain Clear Flag");
  assert.equal(clear.type, "n8n-nodes-base.hubspot");
  assert.equal(clear.parameters.operation, "update");
});

test("wiring: SJ-3 Drain Gate reads ALLOW_SJ3_DRAIN_WRITES and nothing of the shared allowlist machinery", () => {
  const wf = loadWorkflow();
  const js = findNode(wf, "SJ-3 Drain Gate").parameters.jsCode;
  assert.match(js, /ALLOW_SJ3_DRAIN_WRITES/);
  // D-06, pinned structurally: comments are part of jsCode, so the node documents its
  // exclusions without naming the excluded identifiers (see the builder).
  assert.ok(!js.includes("_writeSafetyAllows"),
    "the drain gate must not call the shared write-safety helper (D-06)");
  assert.ok(!js.includes("TEST_RECORD"),
    "the drain gate must not consult the record allowlist (D-06)");
});

test("wiring: SJ-3 Drain Clear Flag's patch is exactly the two baked literal pairs (DRAIN-02)", () => {
  const wf = loadWorkflow();
  const clear = findNode(wf, "SJ-3 Drain Clear Flag");
  const pairs = clear.parameters.updateFields.customPropertiesUi.customPropertiesValues
    .map((p) => [p.property, p.value]);
  assert.deepEqual(pairs, [
    ["lv_enrichment_requested", "false"],
    ["lv_enrichment_status", "skipped"],
  ]);
});
