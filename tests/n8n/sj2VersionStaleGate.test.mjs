// tests/n8n/sj2VersionStaleGate.test.mjs
//
// Phase 75 Plan 03 (D-75-13/D-75-15). SJ-2 (the monthly "stale refresh" scheduled job,
// CLAUDE.md §19.5) is the BACKSTOP for the version-stale sweep the cloud enrichment
// lane's on-demand recompute reroute (tests/n8n/companyVersionStaleRecompute.test.mjs)
// leaves to a scheduled/on-demand dispatch. D-75-13's verified blocker: a search-filter
// change alone is inert unless BOTH halves move -- "SJ-2 Search"'s fetch list must select
// a version-stale-but-input-fresh company AND "SJ-2 Company Gate" (SJ2_CO_GATE) must stop
// treating a version mismatch as "skip", or a company that IS selected still never has
// `lv_enrichment_requested` set. This test pins both halves.
//
// Run: node --test tests/n8n/sj2VersionStaleGate.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_scheduled_maintenance_cloud.json");

const { VERSION } = require(path.join(ROOT, "n8n/code/icpScoring.generated.js"));
const STALE_VERSION = "lv-icp-v0.1";

// HubSpot's own documented cap (developers.hubspot.com/docs/api/crm/search, fetched and
// grepped live during Phase 75 Plan 03): "a maximum of five filterGroups with up to 6
// filters in each group, with a maximum of 18 filters in total."
const HUBSPOT_MAX_FILTER_GROUPS = 5;
const HUBSPOT_MAX_FILTERS_PER_GROUP = 6;
const HUBSPOT_MAX_FILTERS_TOTAL = 18;

function loadWorkflow() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return { wf, byName };
}

function runCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  const out = fn($input) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// Extracts the filterGroups literal array out of the node's n8n-expression jsonBody
// string via the same JSON.stringify({...}) shape every _hs_http_search_node emits, by
// executing the expression body (it is a pure object literal, never untrusted input --
// this is the repo's own committed generation output).
function filterGroupsOf(node) {
  const raw = node.parameters.jsonBody;
  const m = /^=\{\{([\s\S]*)\}\}$/.exec(String(raw).trim());
  assert.ok(m, "jsonBody is not an n8n expression");
  // The expression itself IS `JSON.stringify({ filterGroups: [...], properties: [...],
  // ... })` -- evaluating it returns the serialized string directly; `$json.cutoff_ms`
  // is the only free variable inside it.
  const fn = new Function("$json", `"use strict"; return (${m[1].trim()});`);
  const bodyJsonString = fn({ cutoff_ms: 1700000000000 });
  return JSON.parse(bodyJsonString);
}

// --- behaviour 1: the search fetches lv_icp_scoring_version and carries the 4 groups ---

test("SJ-2 Search (stale refresh) fetches lv_icp_scoring_version", () => {
  const { byName } = loadWorkflow();
  const node = byName["SJ-2 Search (stale refresh)"];
  assert.ok(node, "SJ-2 Search (stale refresh) node exists");
  const body = filterGroupsOf(node);
  assert.ok(body.properties.includes("lv_icp_scoring_version"));
});

test("SJ-2 Search's filterGroups is 4 entries: 2 pre-existing TTL groups + 2 version groups, each version group ANDs HAS_PROPERTY lv_org_type", () => {
  const { byName } = loadWorkflow();
  const node = byName["SJ-2 Search (stale refresh)"];
  const body = filterGroupsOf(node);
  const groups = body.filterGroups;
  assert.equal(groups.length, 4,
    "2 existing verified-at TTL groups + 2 new version-stale groups (org_type-anchored only -- " +
    "the produces_content variant was refused: 2 existing + 4 would be 6, over HubSpot's 5-group cap");

  // The two pre-existing TTL groups, untouched.
  assert.deepEqual(groups[0].filters.map((f) => f.propertyName), ["lv_org_type_verified_at"]);
  assert.deepEqual(groups[1].filters.map((f) => f.propertyName), ["lv_produces_content_verified_at"]);

  // The two new version groups, each a 2-filter AND: a version-mismatch test + the
  // load-bearing HAS_PROPERTY lv_org_type conjunct (D-75-15).
  const versionGroups = groups.slice(2);
  for (const g of versionGroups) {
    assert.equal(g.filters.length, 2);
    const anchor = g.filters.find((f) => f.propertyName === "lv_org_type");
    assert.ok(anchor, "every version group ANDs a scoring-input HAS_PROPERTY conjunct");
    assert.equal(anchor.operator, "HAS_PROPERTY");
  }
  const versionFilters = versionGroups.flatMap((g) => g.filters.filter((f) => f.propertyName === "lv_icp_scoring_version"));
  const operators = versionFilters.map((f) => f.operator).sort();
  assert.deepEqual(operators, ["NEQ", "NOT_HAS_PROPERTY"],
    "one group tests NOT_HAS_PROPERTY (no record carries the property on day one), " +
    "one tests NEQ against the current version -- OR'd via being separate top-level groups");
  const neq = versionFilters.find((f) => f.operator === "NEQ");
  assert.equal(neq.value, VERSION, "the NEQ value is the CURRENT generated version");
});

test("the emitted filterGroups stays within HubSpot's documented cap", () => {
  const { byName } = loadWorkflow();
  const node = byName["SJ-2 Search (stale refresh)"];
  const body = filterGroupsOf(node);
  assert.ok(body.filterGroups.length <= HUBSPOT_MAX_FILTER_GROUPS,
    `${body.filterGroups.length} groups exceeds the documented cap of ${HUBSPOT_MAX_FILTER_GROUPS}`);
  let totalFilters = 0;
  for (const g of body.filterGroups) {
    assert.ok(g.filters.length <= HUBSPOT_MAX_FILTERS_PER_GROUP,
      `a group with ${g.filters.length} filters exceeds the per-group cap of ${HUBSPOT_MAX_FILTERS_PER_GROUP}`);
    totalFilters += g.filters.length;
  }
  assert.ok(totalFilters <= HUBSPOT_MAX_FILTERS_TOTAL,
    `${totalFilters} total filters exceeds the documented cap of ${HUBSPOT_MAX_FILTERS_TOTAL}`);
});

// --- behaviour 2: SJ2_CO_GATE treats a version mismatch as not-skip, fresh-on-all stays skip

function freshBaseRecord(scoringVersion) {
  const FRESH = new Date(Date.now() - 86400000).toISOString();
  return {
    hs_object_id: "18047161864",
    domain: "sj2versionstale.example",
    lv_org_type: "broadcaster",
    lv_produces_content: "true",
    lv_org_type_verified_at: FRESH,
    lv_produces_content_verified_at: FRESH,
    lv_icp_scoring_version: scoringVersion,
  };
}

test("SJ2_CO_GATE: input-fresh but version-stale reaches enrich (not skip)", () => {
  const { byName } = loadWorkflow();
  const gate = byName["SJ-2 Company Gate"];
  assert.ok(gate, "SJ-2 Company Gate node exists");
  const row = { hs_object_id: "18047161864", domain: "sj2versionstale.example",
    existingRecord: freshBaseRecord(STALE_VERSION), lookup_failed: false };
  const [out] = runCode(gate.parameters.jsCode, [row]);
  assert.equal(out.action, "enrich");
  assert.match(out.gate.reason, /version-stale/);
});

test("SJ2_CO_GATE: fresh on all three (inputs AND version) stays skip", () => {
  const { byName } = loadWorkflow();
  const gate = byName["SJ-2 Company Gate"];
  const row = { hs_object_id: "18047161864", domain: "sj2versionstale.example",
    existingRecord: freshBaseRecord(VERSION), lookup_failed: false };
  const [out] = runCode(gate.parameters.jsCode, [row]);
  assert.equal(out.action, "skip");
});

test("SJ2_CO_GATE: a lookup-failed row is never rerouted by version staleness (no real existingRecord to be stale about)", () => {
  const { byName } = loadWorkflow();
  const gate = byName["SJ-2 Company Gate"];
  const row = { hs_object_id: "18047184159", domain: "unknown.example",
    existingRecord: {}, lookup_failed: true };
  const [out] = runCode(gate.parameters.jsCode, [row]);
  assert.equal(out.action, "skip", "lookup_failed forces create -> skip; version staleness must not re-flip it to enrich");
});

// --- behaviour 3: RECOMPUTE_REQUESTED stays a dead constant; write_request stays "enrich" -

test("SJ2_CO_GATE still declares RECOMPUTE_REQUESTED = false (SJ-2 can never carry a request-level intent)", () => {
  const { byName } = loadWorkflow();
  const gate = byName["SJ-2 Company Gate"];
  assert.match(gate.parameters.jsCode, /const RECOMPUTE_REQUESTED = false;/);
});

test("SJ2_CO_GATE's write_request keeps its plain \"enrich\" classification, even on a version-stale row -- SJ-2 stays allowlist-gated, never widened onto D-75-16's standing authority", () => {
  const { byName } = loadWorkflow();
  const gate = byName["SJ-2 Company Gate"];
  const row = { hs_object_id: "18047161864", domain: "sj2versionstale.example",
    existingRecord: freshBaseRecord(STALE_VERSION), lookup_failed: false };
  const [out] = runCode(gate.parameters.jsCode, [row]);
  assert.equal(out.write_request.action, "enrich");
});
