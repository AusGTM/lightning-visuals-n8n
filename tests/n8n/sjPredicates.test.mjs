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

// BUG 10 / Phase 16.6: SJ-1/SJ-2/SJ-3/Review Search moved off the native
// n8n-nodes-base.hubspot node (which has no `operation: "search"` for resource:company —
// n8n's node schema only offers create/delete/get/getAll/getRecentlyCreatedUpdated/
// searchByDomain/update for companies; the native node silently returned json:null live)
// onto a credential-bound httpRequest node whose filters live inside a single `jsonBody`
// expression string, not `filterGroupsUi.filterGroupsValues`. This parses the SAME
// (propertyName, operator, value?) facts out of that expression — it is not valid JSON on
// its own (unquoted keys, and a dynamic filter's value is a raw JS expression like
// `$json.cutoff_ms`, never re-quoted), so a small regex-driven extractor stands in for a
// full JS parser, matching exactly the shape scripts/build_cloud_workflows.py's
// _hs_search_json_body_expr() emits.
function filterGroups(node) {
  const body = node.parameters.jsonBody;
  const groupRe = /\{\s*filters:\s*\[([^\]]*)\]\s*\}/g;
  const filterRe = /\{\s*propertyName:\s*"([^"]*)",\s*operator:\s*"([^"]*)"(?:,\s*value:\s*("(?:[^"\\]|\\.)*"|[^,}]+))?\s*\}/g;
  const groups = [];
  let gm;
  while ((gm = groupRe.exec(body)) !== null) {
    const filters = [];
    let fm;
    filterRe.lastIndex = 0;
    while ((fm = filterRe.exec(gm[1])) !== null) {
      const filter = { propertyName: fm[1], operator: fm[2] };
      if (fm[3] !== undefined) {
        const raw = fm[3].trim();
        filter.value = raw.startsWith('"') ? JSON.parse(raw) : raw;
      }
      filters.push(filter);
    }
    groups.push(filters);
  }
  return groups;
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

// --- SJ-1: hourly input-gap scan ------------------------------------------------------

test("SJ-1: three separate single-filter OR'd groups on lv_org_type/lv_produces_content only", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "SJ-1 Search (input-gap scan)");
  const groups = filterGroups(node);
  assert.equal(groups.length, 3, "SJ-1 predicate is three OR'd groups, not one AND'd group (Pitfall 3)");
  for (const g of groups) {
    assert.equal(g.length, 1, "each SJ-1 group has exactly one filter");
    assert.ok(["lv_org_type", "lv_produces_content"].includes(g[0].propertyName));
  }
  const notHasOrgType = groups.find((g) => g[0].propertyName === "lv_org_type" && g[0].operator === "NOT_HAS_PROPERTY");
  const eqUnknownOrgType = groups.find((g) => g[0].propertyName === "lv_org_type" && g[0].operator === "EQ" && g[0].value === "unknown");
  const notHasContent = groups.find((g) => g[0].propertyName === "lv_produces_content" && g[0].operator === "NOT_HAS_PROPERTY");
  assert.ok(notHasOrgType, "must include lv_org_type NOT_HAS_PROPERTY");
  assert.ok(eqUnknownOrgType, "must include lv_org_type EQ unknown");
  assert.ok(notHasContent, "must include lv_produces_content NOT_HAS_PROPERTY");
});

test("SJ-1: terminates in a HubSpot Update that sets lv_enrichment_requested=true", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "SJ-1 Set Requested");
  assert.equal(node.type, "n8n-nodes-base.hubspot");
  assert.equal(node.parameters.operation, "update");
  const props = node.parameters.updateFields.customPropertiesUi.customPropertiesValues;
  const set = props.find((p) => p.property === "lv_enrichment_requested");
  assert.ok(set && set.value === "true");
});

// --- SJ-2: monthly stale refresh + RT-5 -------------------------------------------------

test("SJ-2: epoch-ms cutoff Code node feeds a two-LT-filter search on the two verified-at cache keys", () => {
  const wf = loadWorkflow();
  const epochNode = findNode(wf, "SJ-2 Epoch Cutoff (180d)");
  assert.match(epochNode.parameters.jsCode, /Date\.now\(\)\s*-\s*180\s*\*\s*86400000/,
    "cutoff must be a Code-node-computed epoch-ms value, not a date string");

  const node = findNode(wf, "SJ-2 Search (stale refresh)");
  const groups = filterGroups(node);
  assert.equal(groups.length, 2, "SJ-2 predicate is two OR'd groups");
  for (const g of groups) {
    assert.equal(g.length, 1);
    assert.equal(g[0].operator, "LT");
    assert.match(g[0].value, /cutoff_ms/);
  }
  const props = groups.map((g) => g[0].propertyName).sort();
  assert.deepEqual(props, ["lv_org_type_verified_at", "lv_produces_content_verified_at"]);
});

test("SJ-2: an Adapt step of the ENRICH_ADAPT_CO_SEARCH shape feeds Company Gate with a populated existingRecord, not raw rows", () => {
  const wf = loadWorkflow();
  const adapt = findNode(wf, "SJ-2 Adapt Search");
  assert.match(adapt.parameters.jsCode, /existingRecord/);
  assert.match(adapt.parameters.jsCode, /lookup_failed/);
  const gate = findNode(wf, "SJ-2 Company Gate");
  assert.match(gate.parameters.jsCode, /decideAction\(row\.existingRecord/,
    "Company Gate must read row.existingRecord (populated by the Adapt step), never a raw search row");
});

test("SJ-2: terminates in a HubSpot Update that sets lv_enrichment_requested=true, gated behind the Company Gate's skip decision", () => {
  const wf = loadWorkflow();
  const node = findNode(wf, "SJ-2 Set Requested");
  assert.equal(node.type, "n8n-nodes-base.hubspot");
  const props = node.parameters.updateFields.customPropertiesUi.customPropertiesValues;
  const set = props.find((p) => p.property === "lv_enrichment_requested");
  assert.ok(set && set.value === "true");

  const ifNode = findNode(wf, "SJ-2 IF Skip");
  const wf_conns = wf.connections[ifNode.name];
  assert.ok(wf_conns, "SJ-2 IF Skip must have outgoing connections");
  const falseBranch = wf_conns.main[1].map((c) => c.node);
  // BUG 15: the write now sits behind a write-safety gate, so the non-skip branch
  // dispatches at the gate and the gate dispatches at the Update.
  assert.ok(falseBranch.includes("SJ-2 Set Requested Write Gate"),
    "the non-skip branch dispatches to the write-safety gate");
  const gate = findNode(wf, "SJ-2 Set Requested Write Gate");
  assert.match(gate.parameters.jsCode, /_writeSafetyAllows/);
  const afterGate = wf.connections[gate.name].main[0].map((c) => c.node);
  assert.ok(afterGate.includes("SJ-2 Set Requested"), "the gate dispatches to the terminal Update");
});
