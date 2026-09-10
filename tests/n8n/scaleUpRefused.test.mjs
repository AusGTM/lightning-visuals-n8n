// tests/n8n/scaleUpRefused.test.mjs
//
// Phase 70 Plan 13 Task 1 (G-70-5, D-70-24). Replaces scaleUpFanOutFlow.test.mjs, which
// asserted the fan-out WORKED. On 2026-09-10 the gap-closure enrichment body dispatched
// 135 child executions in six minutes from four disarmed proof sends (12211-12348):
// "Dispatch Self" ran once per execution with a marker item although its only declared
// producer emitted zero items, and its runData `source` named a gate node that has no
// connection to it. The mechanism was never isolated, so D-70-24 removed the node rather
// than guarding it — after Gate 5 no in-graph guard is trusted on this engine.
//
// This file therefore asserts the ABSENCE of the lane and the REFUSAL of the request that
// used to drive it, walking the real committed graph.
import { test } from "node:test";
import assert from "node:assert/strict";
import { walkWorkflow, loadWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const WF = "n8n/wf_enrichment_cloud.json";

const DELETED_NODES = [
  "IF Scale Up Route",
  "Build Scale Up Fan-Out",
  "Dispatch Self",
  "Build Scale Up Ack",
];

function walk(body) {
  return walkWorkflow(loadWorkflow(WF), {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body }],
    httpStubs: {},
  });
}

function targetsOf(wf, nodeName, branchIndex = 0) {
  const branch = ((wf.connections[nodeName] || {}).main || [])[branchIndex] || [];
  return branch.map((e) => e.node);
}

// --- absence: the only guarantee this engine gave us ------------------------------------

test("the fan-out lane does not exist in the enrichment graph at all", () => {
  const wf = loadWorkflow(WF);
  for (const name of DELETED_NODES) {
    assert.equal(
      wf.nodes.find((n) => n.name === name), undefined,
      `"${name}" must not exist — D-70-24 removed the lane; recursion is impossible by ` +
      "absence, never by an in-graph guard (G-70-5, executions 12211-12348)",
    );
    assert.equal(wf.connections[name], undefined, `no connections may remain for "${name}"`);
  }
});

test("no Execute Workflow node survives in the enrichment graph — nothing can dispatch anything", () => {
  const wf = loadWorkflow(WF);
  const execNodes = wf.nodes.filter((n) => n.type === "n8n-nodes-base.executeWorkflow");
  assert.deepEqual(execNodes.map((n) => n.name), []);
});

test("no node's jsCode still reads fan_depth", () => {
  const wf = loadWorkflow(WF);
  for (const n of wf.nodes) {
    const code = (n.parameters || {}).jsCode;
    if (typeof code !== "string") continue;
    assert.ok(!/\bfan_depth\b/.test(code), `"${n.name}" still reads fan_depth`);
  }
});

// --- the request that used to fan is refused ---------------------------------------------

function assertRefused(rows) {
  assert.equal(rows.length, 1, "the request is refused WHOLE — exactly one terminating row");
  assert.equal(rows[0].outcome, "refused");
  assert.match(rows[0].reason, /retired/i, "the reason must say the fan-out is retired");
  assert.match(rows[0].reason, /12211/, "the reason must name the executions that retired it");
  assert.match(rows[0].reason, /12348/);
  assert.match(rows[0].reason, /not run/i, "the caller must be told the request was not run at all");
}

test("envelope-level scale_up:true is refused as a row, and nothing is dispatched", () => {
  const { runData, trace } = walk({
    run_id: "case-scale-up-envelope",
    scale_up: true,
    events: [{ objectId: "1", objectType: "company", row_id: "row-1" }],
  });
  assertRefused(nodeItems(runData, "Build Response"));
  // The responder is still the ack, and only the ack (D-70-07). A refusal built inside
  // "Parse HubSpot Event" carries no run_id/row_id, exactly like the oversize and
  // empty-array refusals it copies.
  assert.equal(trace.respond.items.length, 1);
  assert.deepEqual(trace.respond.items[0], { run_id: null, accepted: true, row_ids: [] });
});

test("event-level scale_up:true is refused identically — the retired normalization OR'd envelope and event, so the refusal must too", () => {
  const { runData } = walk({
    run_id: "case-scale-up-event",
    events: [{ objectId: "1", objectType: "company", row_id: "row-1", scale_up: true }],
  });
  assertRefused(nodeItems(runData, "Build Response"));
});

test("scale_up is refused STRICTLY on boolean true — a truthy non-boolean is not an opt-in and is not refused", () => {
  const { runData } = walk({
    run_id: "case-scale-up-string",
    scale_up: "true",
    events: [{ objectId: "1", objectType: "unknown-thing" }],
  });
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.notEqual(rows[0].outcome, "refused",
    'the string "true" never opted a request in, so it must not opt one into a refusal either');
});

// --- the default path is what it was before the lane was ever spliced in -----------------

test("Parse HubSpot Event feeds IF Object Type Supported directly again — the splice is gone", () => {
  const wf = loadWorkflow(WF);
  const targets = new Set(targetsOf(wf, "Parse HubSpot Event"));
  assert.ok(targets.has("IF Object Type Supported"),
    "the edge the fan-out lane re-pointed is restored to its pre-splice target");
  assert.ok(targets.has("Credit Request"));
  assert.ok(targets.has("Build Ack"));
});

test("the five pre-fork sentinels are fed from Parse HubSpot Event, not from a routing IF that no longer exists", () => {
  const wf = loadWorkflow(WF);
  const targets = new Set(targetsOf(wf, "Parse HubSpot Event"));
  for (const sentinel of [
    "Contacts Absent Sentinel", "Companies Absent Sentinel", "Unsupported Absent Sentinel",
    "Recompute Not Requested Sentinel", "Recompute Requested Sentinel",
  ]) {
    assert.ok(targets.has(sentinel), `"${sentinel}" must be fed from Parse HubSpot Event`);
  }
});

test("an ordinary request (no scale_up key at all) still reaches Build Response as a real row", () => {
  const { runData } = walk({
    run_id: "case-ordinary",
    mode: "propose",
    events: [{ objectId: "1", objectType: "unknown-thing" }],
  });
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.notEqual(rows[0].outcome, "refused");
});
