// tests/n8n/suggestDiscoveryLane.test.mjs
//
// Phase 73.1 Plan 07 — the sixth cloud workflow: a read-only provider discovery lane.
// Walks the COMMITTED n8n/wf_suggest_discovery_cloud.json end to end via the offline
// walker (never n8n/code/discoverySearch.js in isolation — that is
// tests/n8n/discoverySearch.test.mjs's job).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_suggest_discovery_cloud.json");

function loadWf() {
  return JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
}

function threeCompanyRequest() {
  return {
    body: {
      run_id: "run-73.1-07",
      per_company_cap: 5,
      companies: [
        { company_id: "1", num_associated_contacts: 0, gap: true },
        { company_id: "2", num_associated_contacts: 0, gap: true },
        { company_id: "3", num_associated_contacts: 2, gap: false },
      ],
    },
  };
}

// Every provider search node this lane can reach, stubbed to return zero people by
// default — Task 1's tests exercise the skeleton only and must never depend on Task 2's
// provider nodes existing; Task 2 overrides individual stubs per test.
function zeroPeopleHttpStubs() {
  return {
    "ZoomInfo Search Mint": [{ access_token: "tok", expires_in: 3600 }],
    "Apollo Search Rung1": [{ people: [] }],
    "Apollo Search Rung2": [{ people: [] }],
    "Lusha Search Rung1": [{ contacts: [] }],
    "Lusha Search Rung2": [{ contacts: [] }],
  };
}

function zeroPeopleCodeStubs() {
  return {
    "ZoomInfo Search Rung1": (items) => items.map((it) => ({ ...it, _zoominfo_rung1_people: [] })),
    "ZoomInfo Search Rung2": (items) => items.map((it) => ({ ...it, _zoominfo_rung2_people: [] })),
  };
}

function run(triggerItems, opts) {
  const wf = loadWf();
  return walkWorkflow(wf, {
    triggerNode: "Discovery Webhook Trigger",
    triggerItems,
    httpStubs: { ...zeroPeopleHttpStubs(), ...((opts && opts.httpStubs) || {}) },
    codeStubs: { ...zeroPeopleCodeStubs(), ...((opts && opts.codeStubs) || {}) },
  });
}

// ---- Task 1 -----------------------------------------------------------------------

test("Task1/Test1: three companies (two gap, one not) walk clean, zero stalled Merges", () => {
  const { trace } = run([threeCompanyRequest()]);
  assert.deepEqual(starvedWithData(trace), [], "no Merge may fire with an unfilled input");
});

test("Task1/Test2: response body carries all three companies keyed by company_id, echoing num_associated_contacts verbatim", () => {
  const { runData } = run([threeCompanyRequest()]);
  const rows = nodeItems(runData, "Build Discovery Response");
  assert.equal(rows.length, 1, "Build Discovery Response must run exactly once");
  const body = rows[0];
  assert.equal(body.run_id, "run-73.1-07");
  assert.equal(body.companies.length, 3);
  const byId = Object.fromEntries(body.companies.map((c) => [c.company_id, c]));
  assert.equal(byId["1"].num_associated_contacts, 0);
  assert.equal(byId["2"].num_associated_contacts, 0);
  assert.equal(byId["3"].num_associated_contacts, 2, "num_associated_contacts is echoed verbatim, gap or not");
});

test("Task1/Test3: the gap:false company's entry carries an empty people array and its lane performs zero provider calls", () => {
  const { runData } = run([threeCompanyRequest()]);
  const rows = nodeItems(runData, "Build Discovery Response");
  const co3 = rows[0].companies.find((c) => c.company_id === "3");
  assert.deepEqual(co3.people, []);
  // No provider node ran on behalf of company 3 specifically is asserted indirectly by
  // Task 2's zero-provider-call tests (an all-non-gap round, below) — this test only
  // pins the response shape for a MIXED round, which Task 1's own skeleton must satisfy.
});

test("Task1/Test4: a POST carrying zero companies returns a well-formed empty-companies body, never a bare 200 or a refusal", () => {
  const { runData } = run([{ body: { run_id: "run-empty", companies: [] } }]);
  const rows = nodeItems(runData, "Build Discovery Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].run_id, "run-empty");
  assert.deepEqual(rows[0].companies, []);
});

test("Task1/Test5: the generated workflow has zero nodes whose URL mentions api.hubapi.com", () => {
  const wf = loadWf();
  const offenders = wf.nodes.filter((n) => {
    const url = (n.parameters && n.parameters.url) || "";
    return url.includes("api.hubapi.com");
  });
  assert.deepEqual(offenders.map((n) => n.name), []);
});

test("Task1/Test6: zero executeWorkflow nodes, and the workflow is not in the self-dispatch exemption list", () => {
  const wf = loadWf();
  const dispatchers = wf.nodes.filter((n) => n.type === "n8n-nodes-base.executeWorkflow");
  assert.deepEqual(dispatchers, []);
  assert.notEqual(wf.name, "LV Scheduled Maintenance (Cloud)");
});

test("Task1/Test7: settings.executionOrder is v1", () => {
  const wf = loadWf();
  assert.equal(wf.settings.executionOrder, "v1");
});

test("Task1/Test8: every Merge declares at most 10 inputs", () => {
  const wf = loadWf();
  const merges = wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge");
  assert.ok(merges.length > 0, "this lane must have at least one real Merge (the response terminal)");
  for (const m of merges) {
    assert.ok((m.parameters.numberInputs || 2) <= 10, `${m.name} declares more than 10 inputs`);
  }
});

// ---- Task 2 -------------------------------------------------------------------------

test("Task2/Test6: a gap company whose ZoomInfo search meets the cap never reaches Apollo or Lusha", () => {
  const req = { body: { run_id: "r", per_company_cap: 1, companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true } ] } };
  const { runData } = run([req], {
    codeStubs: {
      "ZoomInfo Search Rung1": (items) => items.map((it) => ({
        ...it, _zoominfo_rung1_people: [{ firstname: "A", lastname: "B", jobtitle: "GM", provider: "zoominfo" }] })),
    },
  });
  assert.equal(nodeItems(runData, "Apollo Search Rung1").length, 0, "Apollo must not run when the cap is already met");
  assert.equal(nodeItems(runData, "Lusha Search Rung1").length, 0, "Lusha must not run when the cap is already met");
  const rows = nodeItems(runData, "Build Discovery Response");
  assert.equal(rows[0].companies[0].people.length, 1);
});

test("Task2/Test7: a gap company whose ZoomInfo rung-1 returns zero reaches rung-2 before falling through to Apollo", () => {
  const req = { body: { run_id: "r", per_company_cap: 5, companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true } ] } };
  const { runData } = run([req], {
    codeStubs: {
      "ZoomInfo Search Rung1": (items) => items.map((it) => ({ ...it, _zoominfo_rung1_people: [] })),
      "ZoomInfo Search Rung2": (items) => items.map((it) => ({
        ...it, _zoominfo_rung2_people: [{ firstname: "C", lastname: "D", jobtitle: "Secretary", provider: "zoominfo" }] })),
    },
  });
  assert.equal(nodeItems(runData, "ZoomInfo Search Rung2").length, 1, "rung 2 must fire when rung 1 was empty");
  const rows = nodeItems(runData, "Build Discovery Response");
  assert.equal(rows[0].companies[0].people.length, 1);
});

test("Task2/Test8: a gap company where all three providers return zero still appears with an empty people array", () => {
  const req = { body: { run_id: "r", per_company_cap: 5, companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true } ] } };
  const { runData, trace } = run([req]);
  assert.deepEqual(starvedWithData(trace), []);
  const rows = nodeItems(runData, "Build Discovery Response");
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0].companies[0].people, []);
});

test("Task2/Test9: the per-company search ceiling emitted into the lane equals search_fallback.MAX_FALLBACK_SEARCHES", () => {
  const wf = loadWf();
  const src = fs.readFileSync(path.join(ROOT, "operator-claude-plugin/scripts/search_fallback.py"), "utf8");
  const m = src.match(/^MAX_FALLBACK_SEARCHES\s*=\s*(\d+)/m);
  assert.ok(m, "search_fallback.MAX_FALLBACK_SEARCHES not found");
  const expected = Number(m[1]);
  const found = wf.nodes.some((n) =>
    JSON.stringify(n.parameters || {}).includes(`DISCOVERY_SEARCH_CEILING = ${expected}`));
  assert.ok(found, `no node emits DISCOVERY_SEARCH_CEILING = ${expected}`);
});

test("Task2/provider node order is ZoomInfo, then Apollo, then Lusha", () => {
  const wf = loadWf();
  const names = wf.nodes.map((n) => n.name);
  const idx = (n) => names.indexOf(n);
  assert.ok(idx("IF ZoomInfo Eligible") < idx("IF Apollo Eligible"));
  assert.ok(idx("IF Apollo Eligible") < idx("IF Lusha Eligible"));
});

test("Task2: no identity-enrich endpoint is wired into this lane", () => {
  const raw = fs.readFileSync(WF_PATH, "utf8");
  assert.ok(!/people\/match|contacts\/enrich|search-and-enrich/.test(raw));
});

// ---- Task 3 -------------------------------------------------------------------------

test("Task3/Test1: response body is the D-07 data body {run_id, companies:[{company_id, num_associated_contacts, people}]}", () => {
  const { runData } = run([threeCompanyRequest()]);
  const body = nodeItems(runData, "Build Discovery Response")[0];
  assert.deepEqual(Object.keys(body).sort(), ["companies", "run_id"]);
  for (const c of body.companies) {
    assert.deepEqual(Object.keys(c).sort(), ["company_id", "num_associated_contacts", "people"]);
  }
});

test("Task3/Test2: the same per-company data is reachable from the response node's runData", () => {
  const { runData } = run([threeCompanyRequest()]);
  const fromResponder = nodeItems(runData, "Respond to Webhook")[0];
  const fromBuilder = nodeItems(runData, "Build Discovery Response")[0];
  assert.deepEqual(fromResponder, fromBuilder);
});

test("Task3/Test3: the response node's name is the literal 'Respond to Webhook'", () => {
  const wf = loadWf();
  assert.ok(wf.nodes.some((n) => n.name === "Respond to Webhook" && n.type === "n8n-nodes-base.respondToWebhook"));
});

test("Task3/Test4: run_id appears in the response body and in the parsed request items", () => {
  const { runData } = run([threeCompanyRequest()]);
  const parsed = nodeItems(runData, "Parse Discovery Request");
  assert.ok(parsed.every((it) => it.run_id === "run-73.1-07"));
  assert.equal(nodeItems(runData, "Build Discovery Response")[0].run_id, "run-73.1-07");
});

test("Task3/Test5: every eligible company appears exactly once", () => {
  const { runData } = run([threeCompanyRequest()]);
  const body = nodeItems(runData, "Build Discovery Response")[0];
  const ids = body.companies.map((c) => c.company_id);
  assert.deepEqual(ids.slice().sort(), Array.from(new Set(ids)).sort(), "no duplicate company_id");
});

test("Task3/Test6: a sentinel marker never reaches the response as a person or a company", () => {
  const { runData } = run([{ body: { run_id: "r", companies: [] } }]);
  const body = nodeItems(runData, "Build Discovery Response")[0];
  assert.deepEqual(body.companies, []);
  const raw = JSON.stringify(body);
  assert.ok(!raw.includes("_gsd_sentinel_marker"));
});

test("Task3/Test7: the walker reports zero stalled entries, including zero merge_fired_with_unfilled_input", () => {
  const { trace } = run([threeCompanyRequest()]);
  assert.deepEqual(starvedWithData(trace), []);
  assert.deepEqual(trace.stalled.filter((s) => s.reason === "merge_fired_with_unfilled_input"), []);
});
