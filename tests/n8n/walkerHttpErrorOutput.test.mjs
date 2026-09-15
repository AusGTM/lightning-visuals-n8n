// tests/n8n/walkerHttpErrorOutput.test.mjs
//
// Phase 73 Plan 06 Task 2 (D-73-19) — the walker cannot see an HTTP node's second
// (error) output at all before this task (73-RESEARCH.md Pitfall 2): `runNode`'s
// HTTP_TYPES branch always returned exactly one output array, so a node built with
// `onError: "continueErrorOutput"` had no way to drive its error branch offline. This is
// the RED evidence that gap exists, and the GREEN proof the walker's own extension
// closes it, on tiny synthetic graphs — not the real committed workflow (that lane is
// Task 3's job).
import { test } from "node:test";
import assert from "node:assert/strict";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

// --- tiny graph-builder helpers (ponytail: plain objects, mirrors walkWorkflow.test.mjs) ---

function codeNode(name, jsCode) {
  return { name, type: "n8n-nodes-base.code", parameters: { jsCode } };
}
function httpNode(name, onError) {
  const node = { name, type: "n8n-nodes-base.httpRequest", parameters: {} };
  if (onError) node.onError = onError;
  return node;
}
function triggerNode(name) {
  return { name, type: "n8n-nodes-base.webhook", parameters: {} };
}
function edge(target, inputIndex) {
  return { node: target, type: "main", index: inputIndex || 0 };
}
function wf(nodes, connections) {
  return { nodes, connections, settings: { executionOrder: "v1" } };
}

function twoOutputGraph(onError) {
  return wf(
    [
      triggerNode("Trigger"),
      httpNode("Http", onError),
      codeNode("Successes", "return $input.all();"),
      codeNode("Errors", "return $input.all();"),
    ],
    {
      Trigger: { main: [[edge("Http")]] },
      Http: { main: [[edge("Successes")], [edge("Errors")]] },
    }
  );
}

test("an HTTP node with continueErrorOutput and a {success, error} stub yields two output branches", () => {
  const graph = twoOutputGraph("continueErrorOutput");
  const { runData } = walkWorkflow(graph, {
    triggerNode: "Trigger",
    triggerItems: [{ id: "row-1" }],
    httpStubs: {
      Http: {
        success: [{ id: "row-1", status: "ok" }],
        error: [{ message: "conflict" }],
      },
    },
  });
  assert.deepEqual(nodeItems(runData, "Successes"), [{ id: "row-1", status: "ok" }]);
  assert.deepEqual(nodeItems(runData, "Errors"), [{ message: "conflict" }]);
});

test("a {success, error} stub with one side omitted treats the missing side as empty", () => {
  const graph = twoOutputGraph("continueErrorOutput");
  const { runData } = walkWorkflow(graph, {
    triggerNode: "Trigger",
    triggerItems: [{ id: "row-1" }],
    httpStubs: { Http: { success: [{ id: "row-1" }] } }, // no `error` key at all
  });
  assert.deepEqual(nodeItems(runData, "Successes"), [{ id: "row-1" }]);
  assert.equal(runData.Errors, undefined, "Errors never ran — fed zero items");
});

test("a plain array stub still yields exactly one output branch, even on a continueErrorOutput node", () => {
  const graph = twoOutputGraph("continueErrorOutput");
  const { runData } = walkWorkflow(graph, {
    triggerNode: "Trigger",
    triggerItems: [{ id: "row-1" }],
    httpStubs: { Http: [{ id: "row-1", status: "ok" }] }, // plain array, no {success,error} shape
  });
  assert.deepEqual(nodeItems(runData, "Successes"), [{ id: "row-1", status: "ok" }]);
  assert.equal(runData.Errors, undefined, "the plain-array stub form never drives a second output");
});

test("a function stub resolving to {success, error} also drives two output branches", () => {
  const graph = twoOutputGraph("continueErrorOutput");
  const { runData } = walkWorkflow(graph, {
    triggerNode: "Trigger",
    triggerItems: [{ id: "row-1" }, { id: "row-2" }],
    httpStubs: {
      Http: (items) => ({
        success: items.filter((it) => it.id === "row-1").map((it) => ({ id: it.id })),
        error: items.filter((it) => it.id === "row-2").map((it) => ({ message: "rejected" })),
      }),
    },
  });
  assert.deepEqual(nodeItems(runData, "Successes"), [{ id: "row-1" }]);
  assert.deepEqual(nodeItems(runData, "Errors"), [{ message: "rejected" }]);
});

test("an HTTP node without continueErrorOutput never reads the {success, error} shape as special", () => {
  // No onError at all — a stub shaped like {success, error} is just a plain object, and
  // the node's single output is that object's own (unwrapped) json, exactly as it
  // always was for every other HTTP node in this repo.
  const graph = wf(
    [triggerNode("Trigger"), httpNode("Http", undefined), codeNode("Reader", "return $input.all();")],
    { Trigger: { main: [[edge("Http")]] }, Http: { main: [[edge("Reader")]] } }
  );
  const { runData } = walkWorkflow(graph, {
    triggerNode: "Trigger",
    triggerItems: [{ id: "row-1" }],
    httpStubs: { Http: [{ success: ["not special here"], error: ["also not special"] }] },
  });
  assert.deepEqual(nodeItems(runData, "Reader"),
    [{ success: ["not special here"], error: ["also not special"] }]);
});

test("an unstubbed HTTP node still throws by name, continueErrorOutput or not", () => {
  const graph = twoOutputGraph("continueErrorOutput");
  assert.throws(
    () => walkWorkflow(graph, { triggerNode: "Trigger", triggerItems: [{ id: "row-1" }], httpStubs: {} }),
    /unstubbed HTTP node: Http/
  );
});
