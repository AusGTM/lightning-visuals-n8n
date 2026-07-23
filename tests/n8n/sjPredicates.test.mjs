// tests/n8n/sjPredicates.test.mjs
//
// Phase 16-02 — SJ-1/SJ-2/SJ-3 scheduled-maintenance predicate shapes (Approach C: keyed
// on pipeline-owned inputs only, never a derived ICP output). Reads the BUILT workflow
// JSON (run `python scripts/build_cloud_workflows.py` first) rather than re-deriving the
// shape by hand, so a drift between the builder and this test is directly visible.
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

function filterGroups(node) {
  return node.parameters.filterGroupsUi.filterGroupsValues.map((g) => g.filtersUi.filterValues);
}

const DERIVED_ICP_OUTPUT_RE = /lv_icp_tier|lv_icp_fit_score|lv_icp_scored_at/;

// --- SJ-3: 15-min requested poller ----------------------------------------------------

test("SJ-3: single AND'd group of lv_enrichment_requested=true + lv_enrichment_status!=running", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "SJ-3 Search (requested poller)");
  const groups = filterGroups(node);
  assert.equal(groups.length, 1, "SJ-3 predicate is a single AND'd group, not OR'd groups");
  const filters = groups[0];
  assert.equal(filters.length, 2);
  const requested = filters.find((f) => f.propertyName === "lv_enrichment_requested");
  const status = filters.find((f) => f.propertyName === "lv_enrichment_status");
  assert.ok(requested && requested.operator === "EQ" && requested.value === "true");
  assert.ok(status && status.operator === "NEQ" && status.value === "running");
});

test("SJ-3: dispatches matched rows into enrichment via a terminal Execute Workflow node", () => {
  const wf = loadWorkflow();
  const dispatch = wf.nodes.find(
    (n) => n.type === "n8n-nodes-base.executeWorkflow" && n.name.startsWith("SJ-3"));
  assert.ok(dispatch, "SJ-3 must terminate in an Execute Workflow dispatch node, not a bare search");
  const search = findNode(wf, "SJ-3 Search (requested poller)");
  assert.ok(wf.connections[search.name], "SJ-3 search node must have an outgoing connection");
});

test("no SJ filter block anywhere in the built workflow references a derived ICP output field", () => {
  const wf = loadWorkflow();
  const sjNodes = wf.nodes.filter((n) => n.name.startsWith("SJ-"));
  const blob = JSON.stringify(sjNodes);
  assert.ok(!DERIVED_ICP_OUTPUT_RE.test(blob),
    "SJ predicates must key on pipeline-owned inputs only (Approach C, spec §0.7)");
});
