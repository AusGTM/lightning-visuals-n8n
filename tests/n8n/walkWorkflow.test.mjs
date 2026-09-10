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
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

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
function wf(nodes, connections, settings) {
  return { nodes, connections, settings: settings || {} };
}

// A passthrough Code node's jsCode: return $input.all() unchanged.
const PASSTHROUGH = "return $input.all();";

test("collapse case (F5): two lanes into a converged Gate, a downstream reader that " +
  "recovers Gate BY NAME with a bare .all() loses the first lane entirely", () => {
  // Comment naming the live execution this encodes: execution 12163
  // (.planning/debug/resolved/uat-batch-review-row-reads-failed.md, F5) — "Enrichment
  // Gate" ran twice (run 0 = email lane, run 1 = name lane) and BOTH runs of "Normalize +
  // Score" (fed by a SINGLE edge from the Gate) returned the Gate's LAST run only,
  // because n8n's own docs confirm bare `$('Node').all()` returns "the items of the
  // node's most recent run". A walker that silently merged the two Gate runs into one
  // combined run would never be able to detect this — the whole point of this test.
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
  const readerRows = nodeItems(runData, "Reader");
  const distinctIds = new Set(readerRows.map((r) => r.id));
  assert.equal(distinctIds.size, 1,
    "the walker SEES the F5 collapse: only ONE distinct row (the Gate's last run) ever " +
    "reaches the reader, even though the Gate fired twice with two different rows");
  assert.ok(!distinctIds.has("row-A"), "row-A (the FIRST lane) is missing entirely, not merely duplicated");
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

test("zero-item delivery case: a lane that RAN and emitted nothing still satisfies its " +
  "Merge input — the Merge fires and the empty input contributes no items", () => {
  // CHANGED by Phase 70 plan 70-09 (D-70-20). This case used to be the "hang case" and
  // asserted that `return []` never delivers, so the Merge stalled. Execution 12203
  // (70-UAT.md § Test 2) proved the live engine does the opposite: `Associate Lane
  // Sentinel` returned `[]` and the runData `source` array names it as the producer that
  // TOOK the Merge's input. The genuine hang shape — a producer that never RAN — is the
  // case immediately below, and it is the one that still stalls.
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [];"), // RAN, emitted nothing -> still a delivery
      mergeNode("Merge", 2),
    ],
    {
      Trigger: { main: [[edge("LaneA"), edge("LaneB")]] },
      LaneA: { main: [[edge("Merge", 0)]] },
      LaneB: { main: [[edge("Merge", 1)]] },
    }
  );
  const { runData, trace } = walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{}] });
  assert.deepEqual(trace.stalled, [],
    "execution 12203: a zero-item output is a DELIVERY, so nothing stalls here");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }],
    "the empty input satisfied readiness and contributed no items of its own");
  assert.equal(trace.merges.Merge.sources[1], "LaneB",
    "and the empty lane is named as the producer that took input 1 — the runData " +
    "`source` reading execution 12203 was diagnosed from");
});

test("hang case: a Merge whose second configured input never DELIVERS never fires", () => {
  // research Pitfall 1, restated after D-70-20: the walker must still be able to say WHY
  // a graph would hang live. The shape that hangs is now a producer that never RAN —
  // execution 12200 (70-UAT.md § Test 1), where "HubSpot Associate Company" was fed zero
  // items, never ran, and contributed nothing at all to its carry Merge.
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
  assert.equal(trace.stalled.length, 1);
  assert.equal(trace.stalled[0].node, "Merge");
  assert.deepEqual(trace.stalled[0].missingInputs, [1]);
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
  assert.equal(trace.stalled.length, 0, "the Merge is NOT stalled");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }, {}],
    "the converged run carries lane A's real row plus one empty marker item");
});

test("mutually-exclusive-branch case: alwaysOutputData on the downstream node of the empty " +
  "branch does NOT help — that node never ran, so the Merge stalls", () => {
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
  assert.equal(trace.stalled.length, 1);
  assert.equal(trace.stalled[0].node, "Merge");
  assert.deepEqual(trace.stalled[0].missingInputs, [1]);
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
  assert.equal(trace.stalled.length, 0);
  assert.equal(runData.FalseSink.length, 1, "FalseSink ran once, fed the IF's forced empty marker");
  assert.equal(runData.Merge.length, 1, "the Merge fired exactly once");
  assert.deepEqual(runData.Merge[0], [{ id: "row-A" }, {}]);
});

test("respond case: two nodes wired into one respondToWebhook — only the first firing " +
  "is recorded as trace.respond, the second is suppressed", () => {
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
  assert.equal(trace.respond.items[0].id, "row-1", "the FIRST firing wins trace.respond");
  assert.equal(trace.respondSuppressed.length, 1, "the second firing is recorded, not silently dropped");
  assert.equal(trace.respondSuppressed[0].items[0].id, "row-2");
});

test("paired-item case: $('Upstream').item resolves against the reader's OWN current run index " +
  "(research Open Question 3 / Pitfall 4) — documented here, not merely asserted", () => {
  const graph = wf(
    [
      triggerNode("Trigger"),
      codeNode("LaneA", "return [{ json: { id: 'row-A' } }];"),
      codeNode("LaneB", "return [{ json: { id: 'row-B' } }];"),
      codeNode("Upstream", PASSTHROUGH), // two inbound edges -> run 0 = row-A, run 1 = row-B
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
  // Documented pairing: Reader's run 0 (fed by Upstream's run 0, the LaneA delivery)
  // resolves `.item` against Upstream run 0 (row-A); Reader's run 1 resolves against
  // Upstream run 1 (row-B). Index-paired by construction — see makeDollar's `.item`.
  assert.deepEqual(runData.Reader[0], [{ id: "row-A" }], "Reader's run 0 paired with Upstream's run 0");
  assert.deepEqual(runData.Reader[1], [{ id: "row-B" }], "Reader's run 1 paired with Upstream's run 1");
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
