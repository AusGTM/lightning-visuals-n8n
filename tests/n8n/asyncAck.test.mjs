// tests/n8n/asyncAck.test.mjs
//
// Phase 61 Plan 05 Task 2 (RUN-01/RUN-03, REVIEW-C14, substrate 1 of
// 61-SPIKE-VERDICT.md) originally pinned the opt-in `async_ack` mechanism. Phase 70
// Plan 03 Task 2 (D-70-07) retires that opt-in — the responder ("Respond to Webhook")
// now has EXACTLY ONE inbound edge (from "Build Ack", renamed from "Build Async Ack")
// and answers unconditionally, every request, with `{run_id, accepted, row_ids}`. This
// file is REWRITTEN against the new contract rather than deleted, since the subject
// ("Build Ack"/the responder's wiring) still exists — only the opt-in flag is gone.
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` — the
// same thing n8n's Code node does at runtime — over a fixed, in-repo list of node names.
// No external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};

function runParseEvent(body) {
  const fn = new Function("$json", `"use strict";\n${node("Parse HubSpot Event").parameters.jsCode}`);
  return fn({ body }).map((it) => (it && it.json !== undefined ? it.json : it));
}

function runBuildAck(items) {
  const $input = { all: () => items.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${node("Build Ack").parameters.jsCode}`);
  return fn($input).map((it) => (it && it.json !== undefined ? it.json : it));
}

function targetsOf(nodeName, branchIndex = 0) {
  const branch = ((wf.connections[nodeName] || {}).main || [])[branchIndex] || [];
  return branch.map((e) => e.node);
}

function inboundEdges(target) {
  const edges = [];
  for (const [src, spec] of Object.entries(wf.connections)) {
    for (const outputs of spec.main || []) {
      for (const conn of outputs || []) {
        if (conn.node === target) edges.push(src);
      }
    }
  }
  return edges;
}

// --- topology: Respond to Webhook has exactly one inbound edge (D-70-07) ---------------

test("wiring: Respond to Webhook has exactly one inbound edge, from Build Ack", () => {
  assert.deepEqual(inboundEdges("Respond to Webhook"), ["Build Ack"]);
});

test("wiring: Build Ack has two inbound edges — Parse HubSpot Event and IF List Expanded's false lane", () => {
  const edges = new Set(inboundEdges("Build Ack"));
  assert.deepEqual(edges, new Set(["Parse HubSpot Event", "IF List Expanded"]));
});

test("wiring: Build Ack's only edge is to Respond to Webhook", () => {
  assert.deepEqual(targetsOf("Build Ack"), ["Respond to Webhook"]);
});

test("wiring: Build Response no longer feeds Respond to Webhook — it is a terminal leaf, read from runData only", () => {
  const spec = wf.connections["Build Response"];
  const targets = spec ? (spec.main || []).flat() : [];
  assert.deepEqual(targets, []);
});

test("wiring: async_ack is gone from the built workflow JSON entirely (outside comments)", () => {
  const text = fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8");
  const withoutComments = text.split("\n").filter((line) => !/^\s*\/\//.test(line)).join("\n");
  assert.equal((withoutComments.match(/async_ack/g) || []).length, 0);
});

// --- Parse HubSpot Event: envelope-level normalization ----------------------------------

test("Parse HubSpot Event: absent run_id normalizes to null, and no async_ack key exists at all", () => {
  const [event] = runParseEvent({ events: [{ objectId: "1", objectType: "contact" }] });
  assert.equal(event.run_id, null);
  assert.equal("async_ack" in event, false);
});

test("Parse HubSpot Event: envelope-level run_id rides onto every event, AFTER the row spread (cannot be shadowed)", () => {
  const [event] = runParseEvent({
    run_id: "run-abc123",
    events: [{ objectId: "1", objectType: "contact", row_id: "row-1" }],
  });
  assert.equal(event.run_id, "run-abc123");
});

test("Parse HubSpot Event: a per-event run_id is used only when the envelope carries none", () => {
  const [event] = runParseEvent({
    events: [{ objectId: "1", objectType: "contact", run_id: "row-level-run-id" }],
  });
  assert.equal(event.run_id, "row-level-run-id");
});

// --- Build Ack ----------------------------------------------------------------------------

test("Build Ack: fires unconditionally — no opt-in flag gates it anymore", () => {
  const [ack] = runBuildAck([{ run_id: "run-xyz", row_id: "row-7" }]);
  assert.deepEqual(ack, { run_id: "run-xyz", accepted: true, row_ids: ["row-7"] });
});

test("Build Ack: a missing run_id/row_id reads as null/empty, never a missing key or a thrown error", () => {
  const [ack] = runBuildAck([{}]);
  assert.deepEqual(ack, { run_id: null, accepted: true, row_ids: [] });
});

test("Build Ack: row_ids collects one id per event row that carried one, in order", () => {
  const [ack] = runBuildAck([
    { run_id: "run-1", row_id: "a" },
    { run_id: "run-1", row_id: "b" },
    { run_id: "run-1" }, // no row_id — dropped, not null-padded
  ]);
  assert.deepEqual(ack, { run_id: "run-1", accepted: true, row_ids: ["a", "b"] });
});

test("Build Ack: zero input items still answers deterministically with an empty ack shape", () => {
  const [ack] = runBuildAck([]);
  assert.deepEqual(ack, { run_id: null, accepted: true, row_ids: [] });
});

test("Build Ack: a list-expansion-refusal item (no run_id/row_id fields at all) still produces a clean ack", () => {
  const [ack] = runBuildAck([{ outcome: "refused", reason: "no members", events: [] }]);
  assert.deepEqual(ack, { run_id: null, accepted: true, row_ids: [] });
});
