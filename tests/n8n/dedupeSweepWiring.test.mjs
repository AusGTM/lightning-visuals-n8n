// tests/n8n/dedupeSweepWiring.test.mjs
//
// Phase 16-02 Task 3 — dedupeSweep.js (pure function, tested elsewhere) wired into an
// active scheduled workflow as a CLASSIFY-ONLY node: it must never write to HubSpot
// itself, and its output must feed a downstream HubSpot write node (RO-2-style
// structural/graph guard, mirrors tests/test_architecture_guard.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n/wf_scheduled_maintenance_cloud.json");

function loadWorkflow() {
  return JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
}

function findNode(wf, name) {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node "${name}" must exist in ${path.basename(WF_PATH)}`);
  return n;
}

test("a Dedupe Sweep node exists", () => {
  const wf = loadWorkflow();
  findNode(wf, "Dedupe Sweep");
});

test("Dedupe Sweep's own parameters reference no HubSpot API URL (classify-only)", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "Dedupe Sweep");
  const blob = JSON.stringify(node.parameters);
  assert.ok(!/api\.hubapi\.com/.test(blob), "Dedupe Sweep must never call HubSpot directly");
  assert.equal(node.type, "n8n-nodes-base.code");
});

test("Dedupe Sweep feeds a downstream HubSpot write node that consumes to_review_ids", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "Dedupe Sweep");
  const outgoing = wf.connections[node.name];
  assert.ok(outgoing, "Dedupe Sweep must have an outgoing connection");
  const targets = outgoing.main[0].map((c) => c.node);
  assert.equal(targets.length, 1);
  // BUG 15: a write-safety gate now sits between the sweep and the write node, so the
  // write is only reachable for allowlisted records. Hop through it — the property under
  // test is still "the sweep reaches a HubSpot update that sets the review flag".
  const gate = findNode(wf, targets[0]);
  assert.match(gate.parameters.jsCode, /_writeSafetyAllows/,
    "the sweep must dispatch into a write-safety gate, not straight at the write node");
  const afterGate = wf.connections[gate.name].main[0].map((c) => c.node);
  assert.equal(afterGate.length, 1);
  const downstream = findNode(wf, afterGate[0]);
  assert.equal(downstream.type, "n8n-nodes-base.hubspot");
  assert.equal(downstream.parameters.operation, "update");
  const props = downstream.parameters.updateFields.customPropertiesUi.customPropertiesValues;
  const set = props.find((p) => p.property === "lv_enrichment_needs_review");
  assert.ok(set && set.value === "true", "downstream node must write lv_enrichment_needs_review=true");
});

test("the Dedupe Sweep wrapper reads dedupeSweep(records) output shape (to_review_ids)", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "Dedupe Sweep");
  assert.match(node.parameters.jsCode, /to_review_ids/);
  assert.match(node.parameters.jsCode, /dedupeSweep\(records\)/);
});

test("the wrapper maps lv_linkedin_url -> linkedin_url for the frozen dedupeSweep.js contract, without editing the module", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "Dedupe Sweep");
  assert.match(node.parameters.jsCode, /linkedin_url:\s*r\.lv_linkedin_url/);
});
