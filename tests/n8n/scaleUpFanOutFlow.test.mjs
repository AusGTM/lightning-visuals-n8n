// tests/n8n/scaleUpFanOutFlow.test.mjs
//
// Phase 61 Plan 06 Task 5 (T-61-25, RUN-02/AFTER-02's substrate-3 scale-up path).
// Drives the REAL committed jsCode of "Parse HubSpot Event", "Build Scale Up Fan-Out" and
// "Build Scale Up Ack", and pins the static connection graph, so a future edit cannot
// silently widen the fan-out or weaken the depth bound. Mirrors asyncAck.test.mjs's own
// pattern (`new Function` over the repo's OWN committed jsCode) deliberately, per the
// plan's "a pattern, not an invention" framing for this third request-level flag.
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

function runBuildScaleUpFanOut(item) {
  const fn = new Function("$json", `"use strict";\n${node("Build Scale Up Fan-Out").parameters.jsCode}`);
  return fn(item).map((it) => (it && it.json !== undefined ? it.json : it));
}

function runBuildScaleUpAck(item) {
  const fn = new Function("$json", `"use strict";\n${node("Build Scale Up Ack").parameters.jsCode}`);
  return fn(item).map((it) => (it && it.json !== undefined ? it.json : it));
}

function targetsOf(nodeName, branchIndex = 0) {
  const branch = ((wf.connections[nodeName] || {}).main || [])[branchIndex] || [];
  return branch.map((e) => e.node);
}

// --- topology: flag OFF is functionally today's path -----------------------------------

test("wiring: Parse HubSpot Event's first target is now IF Scale Up Route, not IF Object Type Supported directly", () => {
  assert.deepEqual(
    new Set(targetsOf("Parse HubSpot Event")),
    new Set(["IF Scale Up Route", "Credit Request", "Build Async Ack"]),
  );
});

test("wiring: IF Scale Up Route's FALSE lane reaches IF Object Type Supported — functionally byte-identical for every non-opted-in request", () => {
  assert.deepEqual(targetsOf("IF Scale Up Route", 1), ["IF Object Type Supported"]);
});

test("wiring: IF Scale Up Route's TRUE lane feeds the fan-out chain, never the business chain", () => {
  assert.deepEqual(targetsOf("IF Scale Up Route", 0), ["Build Scale Up Fan-Out"]);
});

test("wiring: Build Scale Up Fan-Out -> Dispatch Self -> Build Scale Up Ack -> Respond to Webhook", () => {
  assert.deepEqual(targetsOf("Build Scale Up Fan-Out"), ["Dispatch Self"]);
  assert.deepEqual(targetsOf("Dispatch Self"), ["Build Scale Up Ack"]);
  assert.deepEqual(targetsOf("Build Scale Up Ack"), ["Respond to Webhook"]);
});

test("wiring: Build Response still feeds Respond to Webhook unchanged — the fan-out path races it, never replaces it", () => {
  assert.ok(targetsOf("Build Response").includes("Respond to Webhook"));
});

test("Dispatch Self is a detached self-reference: waitForSubWorkflow=false, references this workflow's own name/id", () => {
  const n = node("Dispatch Self");
  assert.equal(n.type, "n8n-nodes-base.executeWorkflow");
  assert.equal(n.parameters.mode, "each");
  assert.equal(n.parameters.options.waitForSubWorkflow, false);
  assert.equal(n.parameters.workflowId.value, "LVenrichmentCloud01");
  assert.equal(n.parameters.workflowId.cachedResultName, "LV Enrichment (Cloud template)");
  assert.equal(wf.name, "LV Enrichment (Cloud template)", "the reference target IS this workflow's own name");
  assert.equal(wf.id, "LVenrichmentCloud01", "the reference target IS this workflow's own local id");
});

// --- Parse HubSpot Event: envelope-level normalization ----------------------------------

test("Parse HubSpot Event: absent scale_up/fan_depth normalize to false/0, byte-identical to today's shape", () => {
  const [event] = runParseEvent({ events: [{ objectId: "1", objectType: "contact" }] });
  assert.equal(event.scale_up, false);
  assert.equal(event.fan_depth, 0);
});

test("Parse HubSpot Event: envelope-level scale_up rides onto every event, AFTER the row spread (cannot be shadowed)", () => {
  const [event] = runParseEvent({
    scale_up: true,
    events: [{ objectId: "1", objectType: "contact", scale_up: false }],
  });
  assert.equal(event.scale_up, true, "envelope-level scale_up wins over a per-event false, same idiom as async_ack");
});

test("Parse HubSpot Event: scale_up normalizes strictly to true — a truthy non-boolean never opts in", () => {
  const [event] = runParseEvent({ scale_up: "true", events: [{ objectId: "1", objectType: "contact" }] });
  assert.equal(event.scale_up, false);
});

test("Parse HubSpot Event: a caller-supplied fan_depth normalizes via Number()||0, never trusted beyond that", () => {
  const [a] = runParseEvent({ events: [{ objectId: "1", objectType: "contact", fan_depth: "3" }] });
  assert.equal(a.fan_depth, 3);
  const [b] = runParseEvent({ events: [{ objectId: "1", objectType: "contact", fan_depth: "not-a-number" }] });
  assert.equal(b.fan_depth, 0);
});

// --- Build Scale Up Fan-Out: the depth bound, asserted directly -------------------------

test("Build Scale Up Fan-Out: scale_up absent/false returns nothing — the byte-identical no-op path", () => {
  assert.deepEqual(runBuildScaleUpFanOut({ scale_up: false, fan_depth: 0 }), []);
  assert.deepEqual(runBuildScaleUpFanOut({ fan_depth: 0 }), []);
});

test("Build Scale Up Fan-Out: scale_up=true and fan_depth=0 (no depth supplied) fans out exactly once, forcing scale_up=false and fan_depth=1 on the child", () => {
  const [child] = runBuildScaleUpFanOut({
    scale_up: true, fan_depth: 0, object_id: "789", object_type: "companies",
    providers_requested: [], mode: "propose", run_id: "run-1", row_id: "row-1",
  });
  assert.equal(child.scale_up, false, "the child can never re-fan even if every other guard were absent");
  assert.equal(child.fan_depth, 1);
  assert.equal(child.objectId, "789");
  assert.equal(child.objectType, "companies");
  assert.deepEqual(child.providers, []);
  assert.equal(child.mode, "propose");
  assert.equal(child.run_id, "run-1");
});

test("TERMINATION (T-61-25): a fan-out invoked with NO depth supplied still stops after one hop — feeding the emitted child back in produces []", () => {
  // Simulates a caller who never passed fan_depth at all — the field is `undefined` on
  // the very first request, exactly as a real caller who has never heard of this
  // mechanism would send. Number(undefined) || 0 -> 0, so this is a REAL "no depth
  // supplied" case, not a stand-in for one.
  const first = { scale_up: true, object_id: "789", object_type: "companies" };
  assert.equal(first.fan_depth, undefined, "sanity: this test genuinely supplies no depth");
  const [child] = runBuildScaleUpFanOut(first);
  assert.equal(child.fan_depth, 1);
  assert.equal(child.scale_up, false);
  // Feed the emitted child event back through Parse HubSpot Event (the bare-event shape
  // it is dispatched in) and then back through the SAME fan-out gate — this is exactly
  // what the depth guard is FOR: even if a malicious or buggy caller re-submitted the
  // dispatched child's own body as a fresh request, it would not fan a second time.
  const [reparsed] = runParseEvent(child);
  assert.equal(reparsed.scale_up, false, "the forced-false stop already prevents a second hop on its own");
  assert.deepEqual(runBuildScaleUpFanOut(reparsed), [], "no second fan-out, even resubmitted");

  // The independent, depth-only stop: even if a caller forged scale_up back to true on
  // the resubmission (bypassing the forced-false stop), fan_depth alone still blocks it.
  const forged = { ...reparsed, scale_up: true };
  assert.deepEqual(runBuildScaleUpFanOut(forged), [], "the depth bound alone terminates it, independent of the forced-false flag");
});

test("Build Scale Up Fan-Out: fan_depth already at the ceiling never fans, regardless of scale_up", () => {
  assert.deepEqual(runBuildScaleUpFanOut({ scale_up: true, fan_depth: 1 }), []);
  assert.deepEqual(runBuildScaleUpFanOut({ scale_up: true, fan_depth: 99 }), []);
});

// --- Build Scale Up Ack -----------------------------------------------------------------

test("Build Scale Up Ack: reports dispatch, never a business outcome", () => {
  const [ack] = runBuildScaleUpAck({ run_id: "run-1" });
  assert.deepEqual(ack, { scale_up_dispatched: true, run_id: "run-1" });
});

test("Build Scale Up Ack: a missing run_id reads as null, never a missing key or a thrown error", () => {
  const [ack] = runBuildScaleUpAck({});
  assert.deepEqual(ack, { scale_up_dispatched: true, run_id: null });
});
