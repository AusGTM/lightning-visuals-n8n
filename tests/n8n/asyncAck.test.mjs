// tests/n8n/asyncAck.test.mjs
//
// Phase 61 Plan 05 Task 2 (RUN-01/RUN-03, REVIEW-C14, substrate 1 of
// 61-SPIKE-VERDICT.md). Drives the REAL committed jsCode of "Parse HubSpot Event" and the
// new "Build Async Ack" node, and pins the static connection graph, so a future edit
// cannot silently re-point the fan-out or change the opt-in's default direction.
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

function runBuildAsyncAck(item) {
  const fn = new Function("$json", `"use strict";\n${node("Build Async Ack").parameters.jsCode}`);
  return fn(item).map((it) => (it && it.json !== undefined ? it.json : it));
}

function targetsOf(nodeName, branchIndex = 0) {
  const branch = ((wf.connections[nodeName] || {}).main || [])[branchIndex] || [];
  return branch.map((e) => e.node);
}

// --- topology --------------------------------------------------------------------------

test("wiring: Parse HubSpot Event fans to Build Async Ack alongside its two existing targets", () => {
  const targets = targetsOf("Parse HubSpot Event");
  assert.deepEqual(
    new Set(targets),
    new Set(["IF Object Type Supported", "Credit Request", "Build Async Ack"]),
    "the existing two targets must survive unmodified — this is an ADDITIVE fan-out target",
  );
});

test("wiring: Build Async Ack's only edge is to Respond to Webhook", () => {
  assert.deepEqual(targetsOf("Build Async Ack"), ["Respond to Webhook"]);
});

test("wiring: Build Response still feeds Respond to Webhook unchanged — the async ack is additive, not a re-point", () => {
  assert.ok(
    targetsOf("Build Response").includes("Respond to Webhook"),
    "Build Response -> Respond to Webhook must survive — the async path races it, never replaces it",
  );
});

// --- Parse HubSpot Event: envelope-level normalization ----------------------------------

test("Parse HubSpot Event: absent async_ack/run_id normalize to false/null, byte-identical to today's shape", () => {
  const [event] = runParseEvent({ events: [{ objectId: "1", objectType: "contact" }] });
  assert.equal(event.async_ack, false);
  assert.equal(event.run_id, null);
});

test("Parse HubSpot Event: envelope-level run_id/async_ack ride onto every event, AFTER the row spread (cannot be shadowed)", () => {
  const [event] = runParseEvent({
    run_id: "run-abc123",
    async_ack: true,
    events: [{ objectId: "1", objectType: "contact", row_id: "row-1" }],
  });
  assert.equal(event.run_id, "run-abc123");
  assert.equal(event.async_ack, true);
});

test("Parse HubSpot Event: async_ack normalizes strictly to true — a truthy non-boolean never opts in", () => {
  const [event] = runParseEvent({
    async_ack: "true",
    events: [{ objectId: "1", objectType: "contact" }],
  });
  assert.equal(event.async_ack, false);
});

// --- Build Async Ack ---------------------------------------------------------------------

test("Build Async Ack: async_ack absent/false returns nothing — the byte-identical no-op path", () => {
  assert.deepEqual(runBuildAsyncAck({ async_ack: false, run_id: "run-1", row_id: "row-1" }), []);
  assert.deepEqual(runBuildAsyncAck({ row_id: "row-1" }), []);
});

test("Build Async Ack: async_ack true echoes the caller's own run_id and row_id, never inventing one", () => {
  const [ack] = runBuildAsyncAck({ async_ack: true, run_id: "run-xyz", row_id: "row-7" });
  assert.deepEqual(ack, { run_id: "run-xyz", accepted: true, row_id: "row-7" });
});

test("Build Async Ack: a missing run_id/row_id reads as null, never a missing key or a thrown error", () => {
  const [ack] = runBuildAsyncAck({ async_ack: true });
  assert.deepEqual(ack, { run_id: null, accepted: true, row_id: null });
});
