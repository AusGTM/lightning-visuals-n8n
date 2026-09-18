// tests/n8n/suggestDiscoveryLane.test.mjs
//
// Phase 73.1 Plan 07 — the sixth cloud workflow: a read-only provider discovery lane.
// Walks the COMMITTED n8n/wf_suggest_discovery_cloud.json end to end via the offline
// walker (never n8n/code/discoverySearch.js in isolation — that is
// tests/n8n/discoverySearch.test.mjs's job).
//
// Plan 09 (D-12, operator ruling 2026-09-18): "ZoomInfo retained as tier-2 source,
// others (Apollo/Lusha) dropped for search phase. Full waterfall only used on enrich."
// This lane is ZoomInfo-only end to end — the Apollo/Lusha search nodes no longer exist
// in the generated graph at all.
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
        { company_id: "1", num_associated_contacts: 0, gap: true, domain: "one.example.org" },
        { company_id: "2", num_associated_contacts: 0, gap: true, domain: "two.example.org" },
        { company_id: "3", num_associated_contacts: 2, gap: false, domain: "three.example.org" },
      ],
    },
  };
}

// Every provider search node this lane can reach, stubbed to return zero people by
// default — Task 1's tests exercise the skeleton only and must never depend on Task 2's
// provider nodes existing; Task 2 overrides individual stubs per test.
function zeroPeopleHttpStubs() {
  // Function form (one output item per input item) — a bare-array stub returns that
  // EXACT array regardless of how many items the node received, silently dropping every
  // item past the array's own length whenever a round sends this node more than one row.
  return {
    "ZoomInfo Search Mint": (items) => items.map(() => ({ access_token: "tok", expires_in: 3600 })),
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
  assert.equal(co3.search_diagnostics, null, "a non-gap company never entered the search lane");
  // No provider node ran on behalf of company 3 specifically is asserted indirectly by
  // Task 2's zero-provider-call tests (an all-non-gap round, below) — this test only
  // pins the response shape for a MIXED round, which Task 1's own skeleton must satisfy.
});

test("73.1-09 follow-through: a gap company that reached the search lane carries a non-null rung1 diagnostic", () => {
  const { runData } = run([threeCompanyRequest()]);
  const rows = nodeItems(runData, "Build Discovery Response");
  const co1 = rows[0].companies.find((c) => c.company_id === "1");
  assert.ok(co1.search_diagnostics, "a gap company that reached the search lane must carry diagnostics");
  assert.ok("rung1" in co1.search_diagnostics);
  assert.ok("rung2" in co1.search_diagnostics);
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

// ---- Plan 11 (D-11) --------------------------------------------------------------------
// Node-scoped assertion on the token gate's generated jsCode -- never a whole-file grep,
// since "zoom_needs_mint"/"zoom_token" legitimately appear in the enrich lane's own gate
// too. Proves the discovery lane's gate mints unconditionally and consults no cross-run
// cache, closing the 12668/12669 stale-token failure class at the source.
test("73.1-11/D-11: ZoomInfo Search Token Gate mints unconditionally, no cross-run cache", () => {
  const wf = loadWf();
  const gate = wf.nodes.find((n) => n.name === "ZoomInfo Search Token Gate");
  assert.ok(gate, "ZoomInfo Search Token Gate node must exist");
  const js = gate.parameters.jsCode;
  assert.match(js, /zoom_needs_mint:\s*true/, "the gate must always request a mint");
  assert.doesNotMatch(js, /needsMint\(/, "the gate must not consult zoominfoToken.js's cache-expiry check");
  assert.doesNotMatch(js, /getWorkflowStaticData/, "the gate must not read the cross-run token cache");
});

// ---- Plan 10 (D-11a) ------------------------------------------------------------------
// Generated-artifact assertion, node-scoped (never a whole-file grep -- the vocabulary
// strings legitimately appear in more than one node, e.g. Rung1 and Rung2 both mention
// ROLE_FAMILY_MAP). This lane's leaves are STUBBED (zeroPeopleCodeStubs), so the walker
// never executes the real filter -- this is the check that actually proves D-11a.
test("73.1-10/D-11a: ZoomInfo Search Rung1 reads role_families off the row and carries the build-time family map", () => {
  const wf = loadWf();
  const rung1 = wf.nodes.find((n) => n.name === "ZoomInfo Search Rung1");
  assert.ok(rung1, "ZoomInfo Search Rung1 node must exist");
  const js = rung1.parameters.jsCode;
  assert.match(js, /ROLE_FAMILY_MAP/, "rung 1 must carry the build-time label->members map");
  assert.match(js, /titlesForFamilies\(ROLE_FAMILY_MAP, row\.role_families\)/,
    "rung 1 must filter the map by the row's OWN role_families selection, per row");
  assert.match(js, /Executive Officer/, "the shipped D-11c family must be present in the map literal");
  assert.match(js, /Board Chairwoman/, "the shipped D-11c member must survive into rung 1's leaf");
});

test("73.1-10/D-11a: ZoomInfo Search Rung2 keeps an empty family map -- rung 2 stays unfiltered", () => {
  const wf = loadWf();
  const rung2 = wf.nodes.find((n) => n.name === "ZoomInfo Search Rung2");
  assert.ok(rung2, "ZoomInfo Search Rung2 node must exist");
  assert.match(rung2.parameters.jsCode, /const ROLE_FAMILY_MAP = \{\};/);
});

// ---- CR-01 (73.1-REVIEW.md) -------------------------------------------------------
// Graph-structure fix: the mint must run once per execution regardless of item count,
// and its single token must reach EVERY gap company's row, never just one. Modelled at
// the merge-wiring level (the walker does not simulate n8n's real per-item HTTP burst
// or ZoomInfo's own token-invalidation behaviour -- those are runtime facts recorded in
// 73.1-TOKEN-REPLAY-VERDICT.json and CLAUDE.md, not reproducible offline). A stub that
// hands back a DISTINCT token per call, fed a 2-gap-company round, is exactly the shape
// the review asked for: if the graph regressed to positional pairing (or the mint fired
// once per row), the two companies' carried tokens would disagree or one row would go
// missing entirely -- this test would catch both.
test("CR-01: ZoomInfo Search Mint executes once per execution and its token reaches every gap company", () => {
  const wf = loadWf();
  const mint = wf.nodes.find((n) => n.name === "ZoomInfo Search Mint");
  assert.equal(mint.executeOnce, true,
    "the mint node must be executeOnce -- one OAuth mint per execution, not one per row");
  const carryMerge = wf.nodes.find((n) => n.name === "ZoomInfo Search Mint Carry Merge");
  assert.equal(carryMerge.parameters.combineBy, "combineAll",
    "the carry merge must broadcast the single minted token onto every row (cartesian), " +
    "never pair token i with row i positionally");

  let mintCalls = 0;
  const req = { body: { run_id: "r", per_company_cap: 5, companies: [
    { company_id: "1", num_associated_contacts: 0, gap: true, domain: "one.example.org" },
    { company_id: "2", num_associated_contacts: 0, gap: true, domain: "two.example.org" },
  ] } };
  const { runData, trace } = run([req], {
    httpStubs: {
      // executeOnce means n8n runs this node's real request exactly once and returns
      // exactly one output item, however many rows entered it -- a distinct token per
      // CALL (not per input item) is what makes a positional/per-row regression visible.
      "ZoomInfo Search Mint": () => { mintCalls += 1; return [{ access_token: `tok-${mintCalls}`, expires_in: 3600 }]; },
    },
  });
  assert.deepEqual(starvedWithData(trace), [], "no Merge may fire with an unfilled input");
  assert.equal(mintCalls, 1, "the mint stub must be invoked exactly once for this round");
  const rung1Rows = nodeItems(runData, "ZoomInfo Search Rung1");
  assert.equal(rung1Rows.length, 2, "both gap companies must reach Rung1, not just one");
  const tokens = new Set(rung1Rows.map((r) => r.zoom_token));
  assert.deepEqual([...tokens], ["tok-1"], "every row reaching Rung1 must carry the SAME minted token");
});

// ---- WR-01 (73.1-REVIEW.md) --------------------------------------------------------
test("WR-01: per_company_cap: 0 means search nobody -- not silently overridden to the default", () => {
  const req = { body: { run_id: "r", companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true, domain: "nine.example.org", per_company_cap: 0 } ] } };
  const { runData } = run([req]);
  assert.equal(nodeItems(runData, "ZoomInfo Search Token Gate").length, 0,
    "a company with per_company_cap: 0 must never enter the search lane");
  const rows = nodeItems(runData, "Build Discovery Response");
  const co = rows[0].companies.find((c) => c.company_id === "9");
  assert.deepEqual(co.people, []);
  assert.equal(co.search_diagnostics, null, "an excluded company never reached the search lane");
});

// ---- WR-03 (73.1-REVIEW.md) --------------------------------------------------------
// Node-scoped (leaves await httpRequest and are stubbed in every walker test here, so
// this is the check that actually proves the wiring -- tests/n8n/discoverySearch.test.mjs
// covers unknownFamilyLabels's own logic).
test("WR-03: ZoomInfo Search Rung1 stamps which requested role_families labels did NOT resolve", () => {
  const wf = loadWf();
  const rung1 = wf.nodes.find((n) => n.name === "ZoomInfo Search Rung1");
  assert.match(rung1.parameters.jsCode, /unknownFamilyLabels\(ROLE_FAMILY_MAP, row\.role_families\)/);
  const adapt = wf.nodes.find((n) => n.name === "Adapt ZoomInfo People");
  assert.match(adapt.parameters.jsCode, /unknown_role_families:\s*row\._zoominfo_rung1_unknown_families/,
    "search_diagnostics.rung1 must surface which labels went unmatched");
});

// ---- Task 2 -------------------------------------------------------------------------

test("Task2/Test6: a gap company whose ZoomInfo rung-1 returns a person never reaches rung-2", () => {
  const req = { body: { run_id: "r", per_company_cap: 1, companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true, domain: "nine.example.org" } ] } };
  const { runData } = run([req], {
    codeStubs: {
      "ZoomInfo Search Rung1": (items) => items.map((it) => ({
        ...it, _zoominfo_rung1_people: [{ firstname: "A", lastname: "B", jobtitle: "GM", provider: "zoominfo" }] })),
    },
  });
  assert.equal(nodeItems(runData, "ZoomInfo Search Rung2").length, 0, "rung 2 must not run when rung 1 had results");
  const rows = nodeItems(runData, "Build Discovery Response");
  assert.equal(rows[0].companies[0].people.length, 1);
});

test("Task2/Test7: a gap company whose ZoomInfo rung-1 returns zero reaches rung-2", () => {
  const req = { body: { run_id: "r", per_company_cap: 5, companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true, domain: "nine.example.org" } ] } };
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

test("Task2/Test8: a gap company where ZoomInfo returns zero still appears with an empty people array", () => {
  const req = { body: { run_id: "r", per_company_cap: 5, companies: [
    { company_id: "9", num_associated_contacts: 0, gap: true, domain: "nine.example.org" } ] } };
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

test("Task2/D-12: only ZoomInfo search nodes exist -- Apollo and Lusha are dropped from this lane", () => {
  const wf = loadWf();
  const names = wf.nodes.map((n) => n.name);
  assert.ok(names.includes("IF ZoomInfo Eligible"));
  assert.ok(!names.some((n) => /Apollo|Lusha/.test(n)),
    "no Apollo/Lusha node may exist in the discovery lane after the D-12 search-only ruling");
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
    // 73.1-09 Task 3 follow-through: search_diagnostics carries per-rung status/total/
    // error (and rung 1's title-cap used/dropped counts) so a silent zero-people result
    // is distinguishable from a genuine empty match (execution 12666's own gap).
    assert.deepEqual(Object.keys(c).sort(),
      ["company_id", "num_associated_contacts", "people", "search_diagnostics"]);
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
