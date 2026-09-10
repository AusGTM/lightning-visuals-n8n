// walkWorkflow.test.mjs — the walker's own RED-detection unit tests (D-70-18).
//
// D-70-18: the operator declined a historical RED against the pre-Phase-70 committed
// JSON. Instead, THESE tests are the RED evidence: they prove the walker built in
// tests/n8n/lib/walkWorkflow.mjs can SEE the defect class on small synthetic graphs
// before any real workflow is refactored under it. A walker that passed these while the
// real workflows stayed broken would make every later plan's GREEN meaningless — that is
// exactly the property the collapse case and the hang case exist to rule out.
//
// Every graph here is built inline as a plain object ({nodes, connections, settings}) —
// NOT the committed JSON — so these cases stay stable while the real workflows are
// refactored under them in later Phase 70 plans.
import { test } from "node:test";
import assert from "node:assert/strict";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

// --- tiny graph-builder helpers (ponytail: plain objects, no builder class) --------

function codeNode(name, jsCode, extra) {
  return { name, type: "n8n-nodes-base.code", parameters: { jsCode }, ...extra };
}
function ifNode(name, leftValue, rightValue, extra) {
  return {
    name,
    type: "n8n-nodes-base.if",
    parameters: {
      conditions: {
        combinator: "and",
        options: {},
        conditions: [{ leftValue, rightValue, operator: { type: "string", operation: "equals" } }],
      },
    },
    ...extra,
  };
}
function mergeNode(name, numberInputs) {
  return { name, type: "n8n-nodes-base.merge", parameters: { numberInputs } };
}
function triggerNode(name) {
  return { name, type: "n8n-nodes-base.webhook", parameters: {} };
}
function respondNode(name) {
  return { name, type: "n8n-nodes-base.respondToWebhook", parameters: {} };
}
// edge(target, inputIndex) — one entry of a `connections[from].main[outputIndex]` array.
function edge(target, inputIndex) {
  return { node: target, type: "main", index: inputIndex || 0 };
}
// D-70-30 (gap-closure round 3, plan 70-16): defaults to n8n's v1 execution order —
// every committed n8n/wf_*.json runs on it (D-70-28), and the walker now REFUSES any
// graph that does not declare it. A call site that needs a non-v1 graph (there is
// exactly one, below, proving the refusal itself) must pass `settings` explicitly.
function wf(nodes, connections, settings) {
  return { nodes, connections, settings: settings || { executionOrder: "v1" } };
}

// A passthrough Code node's jsCode: return $input.all() unchanged.
const PASSTHROUGH = "return $input.all();";

test("collapse case (F5) under v1: two lanes into a converged Gate, a downstream reader " +
  "that recovers Gate BY NAME with a bare .all() no longer loses a lane, RE-DERIVED " +
  "under D-70-30's pop-order dequeue", () => {
  // Comment naming the live execution this encodes: execution 12163
  // (.planning/debug/resolved/uat-batch-review-row-reads-failed.md, F5) — under n8n's
  // LEGACY (FIFO/shift) order, "Enrichment Gate" ran twice (run 0 = email lane, run 1 =
  // name lane) and BOTH runs of "Normalize + Score" (fed by a SINGLE edge from the Gate)
  // returned the Gate's LAST run only, because n8n's own docs confirm bare
  // `$('Node').all()` returns "the items of the node's most recent run".
  //
  // RE-DERIVED for v1 (gap-closure round 3, plan 70-16, D-70-28/D-70-30): this file's
  // `wf()` helper now defaults every synthetic graph to v1's execution order, and the
  // walker's ONLY behavioural difference between v1 and legacy is the dequeue direction
  // (pop, not shift — see the walker's own header comment). For THIS topology that
  // change means: Trigger enqueues [LaneA, LaneB] in that order, so v1's pop-order
  // processes LaneB's ENTIRE path (LaneB -> Gate run 0 -> Reader run 0) to completion
  // BEFORE LaneA even runs -- unlike legacy's shift-order, which finishes both Lane
  // nodes, then both Gate runs, before Reader ever fires. Reader therefore fires once
  // per Gate run, immediately after each one, and captures each run's row distinctly —
  // the collapse this case originally demonstrated does NOT reproduce for this exact
  // topology under v1. This is a genuine, re-derived finding, not a test that was
  // "fixed" to pass: it is kept (rather than deleted) precisely to record that a bare
  // by-name last-run read is FRAGILE across execution orders, which is why D-70-01 bans
  // it system-wide regardless of which order a workflow runs under — this case just
  // shows the fragility runs both ways.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [{ json: { id: 'row-B' } }];"),
      codeNode("Gate", PASSTHROUGH), // two inbound edges -> fires once per lane
      codeNode("Reader", "return $('Gate').all();"), // by-name, bare last-run accessor
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Gate")]] },
      LaneB: { main: [[edge("Gate")]] },
      Gate: { main: [[edge("Reader")]] },
    }
  );
  const { runData } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.Gate.length, 2, "Gate fired once per inbound edge, not once merged");
  assert.deepEqual(runData.Gate, [[{ id: "row-B" }], [{ id: "row-A" }]],
    "v1's pop-order runs LaneB (the LAST-enqueued edge) to completion first");
  const readerRows = nodeItems(runData, "Reader");
  const distinctIds = new Set(readerRows.map((r) => r.id));
  assert.equal(distinctIds.size, 2,
    "under v1, Reader fires once per Gate run and captures BOTH rows distinctly — the " +
    "collapse this case demonstrates under legacy does not reproduce here");
  assert.ok(distinctIds.has("row-A") && distinctIds.has("row-B"),
    "neither lane is lost under v1's execution order for this topology");
});

test("merge case: the same lanes into a Merge before the Gate — the reader sees both rows in one run", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [{ json: { id: 'row-B' } }];"),
      mergeNode("Merge", 2),
      codeNode("Gate", PASSTHROUGH),
      codeNode("Reader", "return $('Gate').all();"),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
      Merge: { main: [[edge("Gate")]] },
      Gate: { main: [[edge("Reader")]] },
    }
  );
  const { runData } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.Gate.length, 1, "Gate now fires exactly once — the Merge collapsed the fan-in");
  const readerRows = nodeItems(runData, "Reader");
  assert.deepEqual(readerRows.map((r) => r.id).sort(), ["row-A", "row-B"],
    "both rows survive, in one run, once the fan-in happens through a real Merge");
});

test("zero-item delivery case, LEGACY-ONLY (quick task 260911-0tz, D-70-30 rule (c) v1 " +
  "flip): a lane that RAN and emitted nothing still satisfies its Merge input under the " +
  "LEGACY engine — the Merge fires and the empty input contributes no items", () => {
  // CHANGED by Phase 70 plan 70-09 (D-70-20). This case used to be the "hang case" and
  // asserted that `return []` never delivers, so the Merge stalled. Execution 12203
  // (70-UAT.md § Test 2) proved the live LEGACY engine does the opposite: `Associate Lane
  // Sentinel` returned `[]` and the runData `source` array names it as the producer that
  // TOOK the Merge's input. The genuine hang shape — a producer that never RAN — is the
  // case immediately below, and it is the one that still stalls.
  //
  // MOVED to legacy-only (quick task 260911-0tz, plan Step 5): Gate 11 (executions
  // 12354/12355/12356, `tests/n8n/v1RuntimeRecordings.test.mjs`,
  // `tests/n8n/walkerEngineFidelityV1.test.mjs`) observed the OPPOSITE under v1 — `Merge
  // Company` ran with 0 items and never appeared as a Merge source. This case still
  // documents the recorded LEGACY mechanism (D-70-19: a fidelity case against a frozen
  // recording, never deleted just because the default engine moved on), so it now
  // declares legacy settings and passes `allowLegacy: true` rather than asserting
  // something the v1 engine no longer does.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [];"), // RAN, emitted nothing -> still a delivery, LEGACY only
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
    },
    {} // no executionOrder declared — the LEGACY body execution 12203 actually ran on
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}], allowLegacy: true });
  // LEFT AS `trace.stalled` (quick task 260911-1z5, Task B site #26): this is the LEGACY
  // branch, whose `merge_input_never_fired` semantics BL-01 left unchanged — the
  // `starvedWithData` rewrite is a v1-only concern (`starvedWithData` itself is a
  // pass-through under `orderingUsed === "legacy"`), so this class-(a)-shaped assertion
  // is NOT one of the ~30 sites that went vacuous and needed re-deriving.
  assert.deepEqual(trace.stalled, [],
    "execution 12203: a zero-item output is a DELIVERY under legacy, so nothing stalls here");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }],
    "the empty input satisfied readiness and contributed no items of its own");
  assert.equal(trace.merges.Merge.sources[1], "LaneB",
    "and the empty lane is named as the producer that took input 1 — the runData " +
    "`source` reading execution 12203 was diagnosed from");
});

test("hang case, RE-DERIVED for v1 (quick task 260911-0tz, D-70-30 rule (b) drain): a " +
  "Merge whose second configured input never DELIVERS no longer stalls — it DRAINS at " +
  "end-of-run and fires on the one input that did arrive, absent input contributing " +
  "nothing", () => {
  // research Pitfall 1, restated after D-70-20: the walker must still be able to say WHY
  // a graph would hang live. execution 12200 (70-UAT.md § Test 1): "HubSpot Associate
  // Company" was fed zero items, never ran, and contributed nothing at all to its carry
  // Merge — that half of this case (LaneB never running) is UNCHANGED.
  //
  // RE-DERIVED for v1 (Gate 11, executions 12354/12355/12356): a Merge with only ONE of
  // its two inputs ever filled no longer stalls — it drains at end-of-run once its
  // filled-input count reaches `requiredInputs` (1, for every append/combine Merge this
  // repo emits). `Decide Company Action Merge` run 1 fired on input 0 alone, input 1
  // forever absent — this is that exact shape on a synthetic graph.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("Upstream", "return [];"), // ran empty -> LaneB is fed zero items
      codeNode("LaneB", PASSTHROUGH),     // never runs, so never delivers
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("Upstream")]] },
      Upstream: { main: [[edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.LaneB, undefined,
    "execution 12200: a node fed zero items does not run, and records no run entry");
  // BL-01 (quick task 260911-1z5): the pre-1z5 detector could never see this shape at
  // all (a Merge that fires with an unfilled input) — it is now reported explicitly, and
  // `starvedWithData` (the shared filter) narrows it back to "nothing was actually lost".
  assert.deepEqual(trace.stalled,
    [{ node: "Merge", reason: "merge_fired_with_unfilled_input", run: 0, missingInputs: [1] }],
    "v1: a Merge with at least one filled input drains at end-of-run instead of stalling, " +
    "and now REPORTS which input it fired without");
  assert.deepEqual(starvedWithData(trace), [],
    "nobody ever delivered to input 1 — the by-design D-70-23 gated-sentinel shape, not a loss");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once, via the drain");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }],
    "only input 0's row survives — input 1 never delivered, so it contributes nothing");
  assert.equal(trace.merges.Merge.runs[0].sources[1], undefined,
    "input 1 is absent from the fired run's sources — nobody ever claimed it");
});

test("always-output-data case: the flag on the node that ran empty satisfies the Merge exactly once", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [];", { alwaysOutputData: true }), // ran, produced 0 items, AOD forces one marker
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  // BL-01 (quick task 260911-1z5): tightened from a length check — both inputs filled,
  // so the fired run has NO missing input and `trace.stalled` is genuinely empty here,
  // not merely "no genuine loss" (starvedWithData would also be empty, but the stronger
  // claim is the one this case actually demonstrates).
  assert.deepEqual(trace.stalled, [], "the Merge is NOT stalled");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }, {}],
    "the converged run carries lane A's real row plus one empty marker item");
});

test("mutually-exclusive-branch case, RE-DERIVED for v1 (quick task 260911-0tz, D-70-30 " +
  "rule (b) drain): alwaysOutputData on the downstream node of the empty branch still " +
  "doesn't help it run, but the Merge no longer stalls — it drains and fires on the " +
  "live branch alone", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      // an always-true condition (comparing $json.id to itself) — every item routes
      // true, so the false branch is genuinely empty for this run, not merely unlucky.
      ifNode("Splitter", "={{ $json.id }}", "={{ $json.id }}"),
      codeNode("TrueSink", PASSTHROUGH),
      codeNode("FalseSink", PASSTHROUGH, { alwaysOutputData: true }), // flag on the DOWNSTREAM node — too late
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("Splitter")]] },
      Splitter: { main: [[edge("TrueSink")], [edge("FalseSink")]] },
      TrueSink: { main: [[edge("Merge", 0)]] },
      FalseSink: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{ id: "row-A" }] });
  assert.equal(runData.FalseSink, undefined, "FalseSink never ran — it never received a delivery");
  // BL-01 (quick task 260911-1z5): as the hang case above — the fired run's own
  // unfilled input 1 is reported explicitly, and starvedWithData confirms it is not a
  // genuine loss (FalseSink never ran at all, so nobody ever had a row to deliver).
  assert.deepEqual(trace.stalled,
    [{ node: "Merge", reason: "merge_fired_with_unfilled_input", run: 0, missingInputs: [1] }],
    "v1: the end-of-run drain fires the Merge on TrueSink's single filled input");
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once, via the drain");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }],
    "only the live branch's row survives — the dead branch's input is absent");
});

test("mutually-exclusive-branch case: alwaysOutputData on the IF itself DOES fire the Merge", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      ifNode("Splitter", "={{ $json.id }}", "={{ $json.id }}", { alwaysOutputData: true }), // flag on the IF
      codeNode("TrueSink", PASSTHROUGH),
      codeNode("FalseSink", PASSTHROUGH), // no flag needed here — it now gets a real delivery
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("Splitter")]] },
      Splitter: { main: [[edge("TrueSink")], [edge("FalseSink")]] },
      TrueSink: { main: [[edge("Merge", 0)]] },
      FalseSink: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{ id: "row-A" }] });
  // BL-01 (quick task 260911-1z5): both inputs filled this time — the fired run has no
  // missing input, so `trace.stalled` is genuinely empty, not merely "no genuine loss".
  assert.deepEqual(trace.stalled, []);
  assert.equal(runData.FalseSink.length, 1, "FalseSink ran once, fed the IF's forced empty marker");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }, {}]);
});

test("respond case: two nodes wired into one respondToWebhook — only the first firing " +
  "is recorded as trace.respond, the second is suppressed", () => {
  // RE-DERIVED for v1 (gap-closure round 3, plan 70-16, D-70-28/D-70-30): under v1's
  // pop-order dequeue, Trigger enqueues [First, Second] and pop() takes Second (the
  // LAST-enqueued edge) first, so Second's whole path resolves before First's. "First
  // firing wins" is still true — it is just Second's delivery that fires first under
  // this order, not First's, by construction of pop().
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("First", "return [{ json: { id: 'row-1' } }];"),
      codeNode("Second", "return [{ json: { id: 'row-2' } }];"),
      respondNode("Respond"),
    ],
    {
      Trigger: { main: [[edge("First"), edge("Second")]] },
      First: { main: [[edge("Respond")]] },
      Second: { main: [[edge("Respond")]] },
    }
  );
  const { trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(trace.respond.items[0].id, "row-2",
    "under v1's pop-order, Second (the last-enqueued edge) fires first and wins trace.respond");
  assert.equal(trace.respondSuppressed.length, 1, "the second firing is recorded, not silently dropped");
  assert.equal(trace.respondSuppressed[0].items[0].id, "row-1");
});

test("paired-item case: $('Upstream').item resolves against the reader's OWN current run index " +
  "(research Open Question 3 / Pitfall 4) — documented here, not merely asserted", () => {
  // RE-DERIVED for v1 (gap-closure round 3, plan 70-16, D-70-28/D-70-30): under v1's
  // pop-order dequeue, LaneB (the LAST-enqueued edge) runs — and resolves all the way
  // through Upstream and Reader — before LaneA even starts, so Upstream's run 0 carries
  // row-B (not row-A) and Reader's run 0 pairs against it. The PAIRING rule itself
  // (Reader's run i pairs with Upstream's run i) is unchanged; only WHICH row lands in
  // which run index is swapped by the dequeue-direction flip.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [{ json: { id: 'row-B' } }];"),
      codeNode("Upstream", PASSTHROUGH), // two inbound edges -> under v1, run 0 = row-B, run 1 = row-A
      codeNode("Reader", "return [{ json: $('Upstream').item.json }];"),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Upstream")]] },
      LaneB: { main: [[edge("Upstream")]] },
      Upstream: { main: [[edge("Reader")]] },
    }
  );
  const { runData } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  // Documented pairing: Reader's run 0 (fed by Upstream's run 0, the LaneB delivery
  // under v1's pop-order) resolves `.item` against Upstream run 0 (row-B); Reader's
  // run 1 resolves against Upstream run 1 (row-A). Index-paired by construction — see
  // makeDollar's `.item`.
  assert.deepEqual(runData.Reader[0], [{ id: "row-B" }], "Reader's run 0 paired with Upstream's run 0");
  assert.deepEqual(runData.Reader[1], [{ id: "row-A" }], "Reader's run 1 paired with Upstream's run 1");
});

test("mixed-batch case: a 2-lane x 2-action graph through a Merge returns exactly 4 rows, no duplicates", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'a-1' } }, { json: { id: 'a-2' } }];"),
      codeNode("LaneB", "return [{ json: { id: 'b-1' } }, { json: { id: 'b-2' } }];"),
      mergeNode("Merge", 2),
      codeNode("Converged", PASSTHROUGH),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
      Merge: { main: [[edge("Converged")]] },
    }
  );
  const { runData } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.Converged.length, 1, "Converged runs exactly once — the Merge already combined both lanes");
  const rows = nodeItems(runData, "Converged");
  assert.equal(rows.length, 4);
  assert.equal(new Set(rows.map((r) => r.id)).size, 4, "no duplicates");
});

// --- Plan 70-09 Task 3: pricing the literal D-70-20 mechanism -----------------------
//
// Neither case below asserts a preference. Both are MEASUREMENTS of a mechanism under
// consideration for Wave 2 (70-CONTEXT.md's "Gap-closure decisions", D-70-20), priced
// against Gate 1's own rule (execution 12200, 70-UAT.md § Test 1: a node fed zero items
// does not run) rather than assumed.

test("D-70-20 mechanism price (1/2), RE-DERIVED for v1 (quick task 260911-0tz, D-70-30 " +
  "rule (b) drain): a sentinel on its OWN dedicated input still cannot deliver the real " +
  "producer's row, but the end-of-run drain now FIRES the Merge anyway — carrying the " +
  "marker alone, the real lane silently absent rather than stalling the Merge", () => {
  // D-70-20 literally describes "a sentinel always emits exactly one marker item on its
  // own dedicated append-mode input" (70-CONTEXT.md). This prices that literal shape:
  // a dedicated input only ever guarantees ITS OWN arrival, never a sibling input's — so
  // when the real producer's lane dies upstream (execution 12200's rule), the real row is
  // never there to be merged.
  //
  // RE-DERIVED for v1 (Gate 11, executions 12354/12355/12356): the PRICE changed. Under
  // the pre-70-16 model this starved the whole Merge (no data reaches downstream at all).
  // Under v1's end-of-run drain, AlwaysMarker's single filled input satisfies
  // `requiredInputs` (1) on its own — the Merge FIRES, carrying only the marker, with the
  // real lane's absence silent rather than visible as a stall. This is the more
  // dangerous shape, not the safer one: it is exactly the mechanism behind `Decide
  // Company Action Merge`'s run 1 firing on one input alone.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("Upstream", "return [];"), // ran, emitted nothing -> RealLane below never runs
      codeNode("RealLane", PASSTHROUGH),  // fed zero items -> never runs -> input 0 starves
      codeNode("AlwaysMarker", "return [{ json: {} }];"), // unconditional -- the literal mechanism
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("Upstream"), edge("AlwaysMarker")]] },
      Upstream: { main: [[edge("RealLane")]] },
      RealLane: { main: [[edge("Merge", 0)]] },
      AlwaysMarker: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.RealLane, undefined, "the real producer's own lane never ran");
  // BL-01 (quick task 260911-1z5): RealLane never ran, so input 0 is the fired run's
  // missing input — reported explicitly now, and starvedWithData confirms it is the
  // by-design gated-sentinel shape, not a loss (nobody ever had a row for input 0).
  assert.deepEqual(trace.stalled,
    [{ node: "Merge", reason: "merge_fired_with_unfilled_input", run: 0, missingInputs: [0] }],
    "v1: the Merge no longer stalls — AlwaysMarker's single filled input satisfies the " +
    "end-of-run drain (requiredInputs 1)");
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once, via the drain");
  assert.deepEqual(runData.Merge[0], [{}],
    "only the sentinel's marker survives — input 0's absence contributes nothing, and " +
    "is silently missing rather than stalling the Merge");
  assert.equal(trace.merges.Merge.runs[0].sources[0], undefined,
    "input 0 has no source — the real lane never delivered");
});

test("D-70-20 mechanism price (2/2): the Wave 2 alternative -- a sentinel gated to fire " +
  "only when the real lane is dead, SHARING the real producer's input -- fires the " +
  "Merge in both shapes, preserving the real row when live and the marker when dead", () => {
  // Mutually exclusive with the real lane by construction (the SAME routing predicate
  // sends a row to exactly one of the two branches, never both, mirroring
  // wire_gate_refusal_lane's "unreached_source" sentinels in scripts/build_cloud_
  // workflows.py) -- so sharing the input is safe precisely because the two producers
  // can never both deliver in the same execution.
  function build(live) {
    return wf(
      [
        triggerNode("Trigger"),
        ifNode("Router", "={{ $json.live }}", "true"),
        codeNode("RealLane", "return [{ json: { id: 'row-real' } }];"),
        // Fed from Router's FALSE branch ONLY -- it is fed at all exactly when the real
        // lane is dead, so its own condition can emit unconditionally once run.
        codeNode("Sentinel", "return [{ json: {} }];"),
        codeNode("LaneB", "return [{ json: { id: 'row-B' } }];"),
        mergeNode("Merge", 2),
      ],
      {
        Trigger: { main: [[edge("Router"), edge("LaneB")]] },
        Router: { main: [[edge("RealLane")], [edge("Sentinel")]] },
        RealLane: { main: [[edge("Merge", 0)]] },
        Sentinel: { main: [[edge("Merge", 0)]] }, // SHARED input -- the point being priced
        LaneB: { main: [[edge("Merge", 1)]] },
      }
    );
  }

  const liveRun = walkWorkflow(build(true), { triggerNode: "Trigger", triggerItems: [{ live: "true" }] });
  assert.equal(liveRun.runData.Merge.length, 1, "live shape: the Merge fires once (NF-NT-03: runData, not the tautological `fired`)");
  assert.deepEqual(liveRun.runData.Merge[0].map((r) => r.id).sort(), ["row-B", "row-real"],
    "the real row survives -- the gated sentinel never ran (fed zero items on the dead branch)");

  const deadRun = walkWorkflow(build(false), { triggerNode: "Trigger", triggerItems: [{ live: "false" }] });
  assert.equal(deadRun.runData.Merge.length, 1, "dead shape: the Merge still fires once");
  const deadRows = deadRun.runData.Merge[0];
  assert.ok(deadRows.some((r) => r.id === "row-B"), "LaneB's real row still arrives");
  assert.equal(deadRows.length, 2, "the marker fills the starved input instead of stalling the Merge");
});

// =============================================================================================
// BL-01 (quick task 260911-1z5): the v1-native starvation detector must be proven
// non-vacuous, not merely "does not crash". Case (i) is the detector's simplest shape;
// case (ii) is the ONE case that proves `starvedWithData` is not vacuously empty — without
// it BL-01 would reintroduce the exact defect it closes.
// =============================================================================================

test("BL-01 case P1 (quick task 260911-1z5): both producers return [] — the Merge never " +
  "enters mergeState, and the detector reports it by NAME, not as dead code", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [];"),
      codeNode("LaneB", "return [];"),
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.Merge, undefined, "the Merge never fired — no run entry at all");
  assert.deepEqual(trace.stalled,
    [{ node: "Merge", reason: "merge_never_delivered_to", missingInputs: [0, 1] }]);
  assert.deepEqual(starvedWithData(trace), [], "a Merge nobody ever fed is not a loss");
});

test("BL-01/MN-01 case (quick task 260911-1z5): two producers both target input 0 of a " +
  "2-input Merge, input 1 never fed — the drain fires ONCE (the cap) and the OTHER row " +
  "is reported lost, non-vacuously (the one case proving starvedWithData is not " +
  "vacuously empty)", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return [{ json: { id: 'row-A' } }];"),
      codeNode("B", "return [{ json: { id: 'row-B' } }];"),
      mergeNode("M", 2),
    ],
    {
      Trigger: { main: [[edge("A"), edge("B")]] },
      A: { main: [[edge("M", 0)]] },
      B: { main: [[edge("M", 0)]] }, // SAME input as A — the MN-01 shape, input 1 never fed
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.M.length, 1, "MN-01: the drain caps at ONE fired run per Merge");
  const undrained = trace.stalled.filter((s) => s.reason === "merge_pending_runs_undrained");
  assert.equal(undrained.length, 1, "exactly one leftover pending run, never fired, never dropped");
  assert.equal(
    Object.values(undrained[0].itemCounts).reduce((a, b) => a + b, 0), 1,
    "the leftover pending run carries the OTHER producer's one real item");
  assert.notEqual(starvedWithData(trace).length, 0,
    "BL-01's whole point — a row that went in and never came out must be visible");
});

// =============================================================================================
// MN-01/MN-02 (quick task 260911-1z5): the review's OWN feedback graph, and the guard it
// asked for. MN-01's per-Merge drain cap already terminates the review's literal graph
// WITHOUT ever reaching the guard — a drain-only guard (as the review's own snippet
// scoped it) would be provably dead code once that cap lands: drain fires are bounded by
// the number of Merge nodes in the graph, always < nodes.length * 4. The shape that still
// needs a guard is a Merge whose own output re-completes its own input via the MAIN
// LOOP's arrival code, which stays UNCAPPED by count (a real double-complete-fire, like
// `Decide Company Action Merge`'s own run 0, must still be allowed) — so the fire-count
// cap is shared between the drain and the main loop (walkWorkflow.mjs's `recordV1Fire`).
// =============================================================================================

test("MN-02 graph (quick task 260911-1z5), AS the review's own example: A -> M.input0, " +
  "M -> Loop -> M.input1 — MN-01's per-Merge drain cap already terminates this without a " +
  "throw, a deviation from the review's literal fix recorded here rather than silently " +
  "changed", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return [{ json: { id: 'row-A' } }];"),
      codeNode("Loop", PASSTHROUGH),
      mergeNode("M", 2),
    ],
    {
      Trigger: { main: [[edge("A")]] },
      A: { main: [[edge("M", 0)]] },
      M: { main: [[edge("Loop")]] },
      Loop: { main: [[edge("M", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.M.length, 1, "MN-01's cap fires M once, using input 0 alone");
  const undrained = trace.stalled.filter((s) => s.reason === "merge_pending_runs_undrained");
  assert.equal(undrained.length, 1,
    "the feedback delivery to input 1 opens a NEW pending run that MN-01 refuses to " +
    "re-fire — this is what stops the review's original infinite ping-pong, without " +
    "ever reaching the guard below");
});

test("MN-02 guard (quick task 260911-1z5): a self-referential SINGLE-input Merge that " +
  "keeps re-completing its own input via the MAIN LOOP is bounded by the shared " +
  "fire-count cap, never hangs node --test", () => {
  // numberInputs: 1 means ANY single delivery is immediately "complete" — the main
  // loop's arrival code fires it right away, uncapped by count, exactly the shape that
  // makes a self-referencing Merge genuinely dangerous.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return [{ json: { id: 'seed' } }];"),
      codeNode("Loop", PASSTHROUGH),
      mergeNode("M", 1),
    ],
    {
      Trigger: { main: [[edge("A")]] },
      A: { main: [[edge("M", 0)]] },
      M: { main: [[edge("Loop")]] },
      Loop: { main: [[edge("M", 0)]] }, // feedback into M's OWN single input
    }
  );
  assert.throws(
    () => walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] }),
    (error) => {
      assert.match(error.message, /"M"/);
      assert.match(error.message, /feedback edge/);
      return true;
    }
  );
});

// =============================================================================================
// Round-3 cases (260911-1z5 review findings NF-BL-01, NF-MJ-01, NF-MN-05, NF-NT-04).
// =============================================================================================

test("NF-BL-01: a combine/combineByPosition Merge fired with an unfilled input ANNIHILATES " +
  "the filled input's rows (rows in, zero out) — starvedWithData must report it", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("Real", "return [{ json: { id: 'r1' } }, { json: { id: 'r2' } }];"),
      codeNode("Dead", "return [];"),
      { name: "M", type: "n8n-nodes-base.merge",
        parameters: { numberInputs: 2, mode: "combine", combineBy: "combineByPosition" } },
      codeNode("Sink", "return $input.all();"),
    ],
    {
      Trigger: { main: [[edge("Real"), edge("Dead")]] },
      Real: { main: [[edge("M", 0)]] },
      Dead: { main: [[edge("M", 1)]] },
      M: { main: [[edge("Sink")]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.deepEqual(runData.M, [[]], "2 rows in, 0 out — the merge maths took Math.min with an absent input");
  assert.equal(runData.Sink, undefined, "nothing downstream ran");
  assert.deepEqual(trace.stalled,
    [{ node: "M", reason: "merge_fired_with_unfilled_input", run: 0, missingInputs: [1] }]);
  // RED-first (observed against the pre-round-3 walker at commit 7f573285): starvedWithData
  // returned [] here — "no row was lost" while 2 rows were destroyed.
  const lost = starvedWithData(trace);
  assert.equal(lost.length, 1, "annihilation IS a loss: rows went in and never came out");
  assert.equal(lost[0].node, "M");
  assert.equal(trace.merges.M.runs[0].outputCount, 0);
});

test("NF-BL-01 (no false positive): an append Merge drained on one arrived input passes its " +
  "row through — the 12354 Decide Company Action Merge run-1 shape is NOT a loss", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return [{ json: { id: 'a' } }];"),
      codeNode("Dead", "return [];"),
      mergeNode("M", 2),
    ],
    {
      Trigger: { main: [[edge("A"), edge("Dead")]] },
      A: { main: [[edge("M", 0)]] },
      Dead: { main: [[edge("M", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.deepEqual(runData.M, [[{ id: "a" }]]);
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(trace.merges.M.runs[0].outputCount, 1);
});

test("NF-MJ-01 (KNOWN-UNOBSERVED, pinned): two grouped producers OVERLAPPING on an input of a " +
  "3-input append Merge — the atomic-fill rule opens a second pending run that MN-01's cap " +
  "then refuses to drain; a per-input-queue model would have completed one run (P,P,Q). " +
  "Gate 11 did not isolate the two models. This pins the walker's CURRENT choice so the " +
  "divergence is visible, not a claim that the engine does this", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("P", "return [{ json: { id: 'p' } }];"),
      codeNode("Q", "return [{ json: { id: 'q' } }];"),
      mergeNode("M", 3),
    ],
    {
      Trigger: { main: [[edge("P"), edge("Q")]] },
      P: { main: [[edge("M", 0), edge("M", 1)]] },
      Q: { main: [[edge("M", 1), edge("M", 2)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.equal(runData.M.length, 1, "one drained run (MN-01 cap)");
  const undrained = trace.stalled.filter((s) => s.reason === "merge_pending_runs_undrained");
  assert.equal(undrained.length, 1, "the overlapping producer's run is left undrained");
  assert.equal(starvedWithData(trace).length, 1,
    "reported as a loss under the current grouping model — a walker artifact OR a real engine " +
    "loss; see .planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md");
});

test("NF-MN-05 (MJ-01 coverage): an unfired LEGACY Merge keeps its partial sources/itemCounts " +
  "view (the 12203/12206 diagnostic: who claimed input 0 before it starved)", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return [{ json: { id: 'a' } }];"),
      mergeNode("M", 2),
    ],
    {
      Trigger: { main: [[edge("A")]] },
      A: { main: [[edge("M", 0)]] },
    }
  );
  graph.settings = {}; // a LEGACY recording shape — the only way this branch is reached
  const { trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}], allowLegacy: true });
  assert.deepEqual(trace.merges.M, { fired: false, sources: { 0: "A" }, itemCounts: { 0: 1 }, runs: [] });
});

test("NF-NT-04: a feedback cycle with NO Merge on it terminates with a thrown error, not a hang", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return $input.all();"),
      codeNode("B", "return $input.all();"),
    ],
    {
      Trigger: { main: [[edge("A")]] },
      A: { main: [[edge("B")]] },
      B: { main: [[edge("A")]] },
    }
  );
  assert.throws(
    () => walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] }),
    /feedback cycle with no Merge/
  );
});

test("MN-07 (quick task 260911-1z5): a chooseBranch Merge is refused on the MAIN path, " +
  "not only from the drain", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("A", "return [{ json: { id: 'row-A' } }];"),
      { name: "M", type: "n8n-nodes-base.merge", parameters: { numberInputs: 2, mode: "chooseBranch" } },
    ],
    {
      Trigger: { main: [[edge("A")]] },
      A: { main: [[edge("M", 0)]] },
    }
  );
  assert.throws(
    () => walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] }),
    /chooseBranch/
  );
});

// =============================================================================================
// D-70-30 / G-70-6 (gap-closure round 3, plan 70-16): the walker models n8n's v1
// execution order only. A graph whose settings do not declare it is refused, not
// silently walked under an engine mode this repo has retired. The one documented escape
// option (see the walker's own doc comment in lib/walkWorkflow.mjs) is proved ELSEWHERE
// — by walkerEngineFidelity.test.mjs going green under it, never by a second passing
// case here. Do not reach for that escape in this file: this suite's job is to prove the
// refusal, not to route around it.
// =============================================================================================

test("walkWorkflow refuses a graph whose settings do not declare n8n's v1 execution order", () => {
  const graph = wf(
    [triggerNode("Trigger"), codeNode("A", PASSTHROUGH)],
    { Trigger: { main: [[edge("A")]] } },
    {} // explicit override -- wf()'s default is now v1; this is the ONE call site in
    // this file that needs a non-v1 graph, to prove the refusal itself
  );
  assert.throws(
    () => walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] }),
    (error) => {
      assert.match(error.message, /executionOrder/);
      assert.match(error.message, /D-70-30/);
      return true;
    }
  );
});
