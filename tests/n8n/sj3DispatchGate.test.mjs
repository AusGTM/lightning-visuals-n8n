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
    // payload otherwise untouched (Plan 02: every row also carries the sj3_tick summary)
    const { sj3_dispatch, sj3_drain, sj3_tick, ...rest } = row;
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

// --- (1b) Plan 02: cap + tick summary (CAP-01/CAP-02/D-09) ------------------------------

function assertTickInvariants(rows) {
  assert.ok(rows.length > 0, "invariant check needs rows");
  const t = rows[0].sj3_tick;
  for (const row of rows) {
    assert.deepEqual(row.sj3_tick, t, "every row carries the SAME sj3_tick summary object");
  }
  assert.equal(t.found, t.permitted + t.declined, "found === permitted + declined");
  assert.equal(t.permitted, t.dispatched + t.deferred, "permitted === dispatched + deferred");
  return t;
}

test("sj3Gate cap: all permitted, under the cap -> all dispatch, outcome=dispatched", () => {
  const rows = [{ hs_object_id: "1" }, { hs_object_id: "2" }, { hs_object_id: "3" }];
  const out = sj3Gate(rows, { allows: () => true, cap: 10 });
  assert.deepEqual(out.map((r) => r.sj3_dispatch), [true, true, true]);
  assert.deepEqual(out.map((r) => r.sj3_drain), [false, false, false]);
  const t = assertTickInvariants(out);
  assert.deepEqual(t, {
    found: 3, permitted: 3, dispatched: 3, declined: 0, deferred: 0,
    cap: 10, outcome: "dispatched",
  });
});

test("sj3Gate cap: 5 permitted, cap 2 -> first two dispatch, tail three DEFERRED not drained (D-09)", () => {
  const rows = ["1", "2", "3", "4", "5"].map((id) => ({ hs_object_id: id }));
  const out = sj3Gate(rows, { allows: () => true, cap: 2 });
  assert.deepEqual(out.map((r) => r.hs_object_id), ["1", "2", "3", "4", "5"], "input order");
  assert.deepEqual(out.map((r) => r.sj3_dispatch), [true, true, false, false, false],
    "cap applies in input order — the deferred remainder is the tail, not an arbitrary subset");
  assert.deepEqual(out.map((r) => r.sj3_drain), [false, false, false, false, false],
    "deferred rows are NEVER drained — they keep their flag for the next tick (D-09)");
  const t = assertTickInvariants(out);
  assert.deepEqual(t, {
    found: 5, permitted: 5, dispatched: 2, declined: 0, deferred: 3,
    cap: 2, outcome: "capped_partial",
  });
});

test("sj3Gate cap: declined rows drain regardless of position and never consume cap budget", () => {
  // permitted at 1,3,5; declined at 2,4 — with cap 2, permitted 1 and 3 dispatch,
  // permitted 5 defers; both declined rows drain even though one sits past the cap point.
  const rows = ["1", "2", "3", "4", "5"].map((id) => ({ hs_object_id: id }));
  const permitted = new Set(["1", "3", "5"]);
  const out = sj3Gate(rows, { allows: (r) => permitted.has(r.hs_object_id), cap: 2 });
  assert.deepEqual(out.filter((r) => r.sj3_dispatch).map((r) => r.hs_object_id), ["1", "3"]);
  assert.deepEqual(out.filter((r) => r.sj3_drain).map((r) => r.hs_object_id), ["2", "4"],
    "declined rows drain regardless of cap position");
  assert.deepEqual(
    out.filter((r) => !r.sj3_dispatch && !r.sj3_drain).map((r) => r.hs_object_id), ["5"],
    "the permitted row past the cap is deferred, not drained");
  const t = assertTickInvariants(out);
  assert.deepEqual(t, {
    found: 5, permitted: 3, dispatched: 2, declined: 2, deferred: 1,
    cap: 2, outcome: "capped_partial",
  });
});

test("sj3Gate cap: fully gate-closed tick reports outcome=gate_closed, all rows drain", () => {
  const out = sj3Gate([{ hs_object_id: "1" }, { hs_object_id: "2" }],
    { allows: () => false, cap: 40 });
  const t = assertTickInvariants(out);
  assert.deepEqual(t, {
    found: 2, permitted: 0, dispatched: 0, declined: 2, deferred: 0,
    cap: 40, outcome: "gate_closed",
  });
});

test("sj3Gate cap: an invalid cap fails CLOSED (behaves as 0, reported as the effective cap)", () => {
  const out = sj3Gate([{ hs_object_id: "1" }], { allows: () => true, cap: -3 });
  assert.equal(out[0].sj3_dispatch, false);
  assert.equal(out[0].sj3_drain, false, "deferred, not drained — the work is preserved");
  const t = assertTickInvariants(out);
  assert.equal(t.cap, 0, "sj3_tick echoes the EFFECTIVE cap, not the raw invalid opt");
  assert.equal(t.outcome, "capped_partial");
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

test("wiring: the gate node bakes a numeric dispatch cap and passes it to sj3Gate (CAP-01)", () => {
  const wf = loadWorkflow();
  const js = findNode(wf, "SJ-3 Dispatch Gate").parameters.jsCode;
  // The cap is a build-time constant DERIVED from config/execution_budget.yaml — never
  // computed at n8n runtime. This pins that a number was baked; the derivation itself is
  // pinned Python-side (the builder KeyErrors on a missing config key).
  assert.match(js, /const SJ3_DISPATCH_CAP = \d+;/,
    "the built gate node must carry a numeric baked cap constant");
  assert.match(js, /cap: SJ3_DISPATCH_CAP/,
    "the baked cap must actually be passed into sj3Gate");
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
