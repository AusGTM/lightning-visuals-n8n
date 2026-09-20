// tests/n8n/companyVersionStaleRecompute.test.mjs
//
// Phase 75 Plan 03 (D-75-12/D-75-16/D-75-17/D-75-19). A company whose
// lv_icp_scoring_version differs from the generated VERSION and whose Company Gate
// verdict would otherwise be "skip" is rerouted into Decide Company Action through the
// EXISTING zero-cost recompute lane (Company Gate -> IF Company Recompute -> Decide
// Company Action) -- no provider, research, judge or merge node runs -- while a
// version-fresh skip still reaches Build Response unchanged, and the webhook
// `recompute: true` lane is untouched. Decide Company Action's write_request.action
// becomes "recompute" on that path ONLY, giving it its own standing write authority
// (ALLOW_HUBSPOT_RECOMPUTE_WRITES) unreachable from the allowlist-gated ALLOW_HUBSPOT_*
// family.
//
// This test drives the ACTUAL emitted jsCode of the committed workflow via `new Function`
// (the companyRecomputeLaneFlow.test.mjs template) -- the same mechanism n8n's Code node
// uses at runtime. No external or untrusted input is ever interpolated into the function
// body.
//
// Run: node --test tests/n8n/companyVersionStaleRecompute.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLOUD_WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");
const LOCAL_LIVE_WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_local_live.json");

const { VERSION } = require(path.join(ROOT, "n8n/code/icpScoring.generated.js"));
const STALE_VERSION = "lv-icp-v0.1"; // a real, superseded rubric version (Plan 01's bump)

function loadWorkflow(wfPath) {
  const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return { wf, byName };
}

function makeCtx(current, outputs) {
  const $ = (name) => {
    const rows = () => (outputs[name] || []).map((j) => ({ json: j }));
    return {
      all: rows,
      first: () => rows()[0],
      get item() { return rows()[0]; },
    };
  };
  const $input = {
    all: () => current.map((j) => ({ json: j })),
    get item() { return { json: current[0] }; },
    first: () => ({ json: current[0] }),
  };
  return { $, $input, $json: current[0] };
}

function runCode(node, current, outputs) {
  const { $, $input, $json } = makeCtx(current, outputs);
  const now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${node.parameters.jsCode}`);
  const out = fn($, $input, $json, {}, now, now) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

function ifExpression(node) {
  const raw = node.parameters.conditions.conditions[0].leftValue;
  const m = /^=\{\{([\s\S]*)\}\}$/.exec(String(raw).trim());
  assert.ok(m, `IF node leftValue is not an n8n expression: ${raw}`);
  return m[1].trim();
}

function evalIf(node, current, outputs) {
  const { $, $input, $json } = makeCtx(current, outputs);
  const fn = new Function("$", "$input", "$json", `"use strict"; return (${ifExpression(node)});`);
  return fn($, $input, $json) === true;
}

// A "runOnceForAllItems" node that reads only $input (the write gates -- see
// _write_gate_js in scripts/build_cloud_workflows.py).
function runInputOnlyCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  const out = fn($input) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// Phase 66 Plan 02 (D-66-01 companies half): ENRICH_CO_GATE's REQUIRED is the 13-field
// completeness list -- mirrors companyRecomputeLaneFlow.test.mjs's own fixture exactly,
// with lv_icp_scoring_version added as the ONE extra axis this plan introduces. Only
// lv_org_type/lv_produces_content carry a stale_after_days TTL in POLICY.
const FRESH = new Date(Date.now() - 86400000).toISOString();

function completeRecord({ region = "DE", scoringVersion } = {}) {
  const rec = {
    hs_object_id: "18047161864",
    name: "Version Stale Fixture Co",
    domain: "versionstale.example",
    lv_org_type: "broadcaster",
    lv_produces_content: "true",
    lv_org_type_verified_at: FRESH,
    lv_produces_content_verified_at: FRESH,
    lv_country_region_normalized: region,
    industry: "sports",
    numberofemployees: 42,
    lv_revenue_band: "5-50M",
    lv_employee_band: "10-50",
    country: "Australia",
    city: "Melbourne",
    lv_content_type: "live_broadcast",
    lv_sponsorship_reliant: "false",
    lv_is_hardware_vendor: "false",
    lv_is_gambling_operator: "false",
  };
  if (scoringVersion !== undefined) rec.lv_icp_scoring_version = scoringVersion;
  return rec;
}

function webhookEvent({ recompute, id = "18047161864" }) {
  const event = {
    objectId: id,
    objectType: "company",
    subscriptionType: "company.propertyChange",
    propertyName: "lv_country_region_normalized",
    occurredAt: 1786000000000,
  };
  if (recompute) event.recompute = true;
  return [event];
}

// Drive: Parse HubSpot Event -> Company Gate -> IF Company Recompute -> (Decide | IF Company Skip)
function runLane({ existingRecord, recompute, identity_keys }) {
  const { wf, byName } = loadWorkflow(CLOUD_WF_PATH);
  const outputs = {};

  for (const name of ["Parse HubSpot Event", "Company Gate", "Decide Company Action",
                       "IF Company Recompute", "IF Company Skip"]) {
    assert.ok(byName[name], `node present: ${name}`);
  }

  const parsed = runCode(
    byName["Parse HubSpot Event"], [{ body: webhookEvent({ recompute }) }], outputs);
  outputs["Parse HubSpot Event"] = parsed;

  const seedRow = {
    object_type: "companies",
    object_id: parsed[0].object_id,
    identity_keys: identity_keys || { domain: "versionstale.example" },
    existingRecord,
    lookup_failed: false,
    mode: parsed[0].mode,
    recompute: parsed[0].recompute,
  };

  const gated = runCode(byName["Company Gate"], [seedRow], outputs);
  outputs["Company Gate"] = gated;

  const recomputeLane = evalIf(byName["IF Company Recompute"], gated, outputs);

  let decided = null;
  let skipLane = null;
  if (recomputeLane) {
    decided = runCode(byName["Decide Company Action"], gated, outputs);
    outputs["Decide Company Action"] = decided;
  } else {
    skipLane = evalIf(byName["IF Company Skip"], gated, outputs);
  }

  return {
    wf, byName, parsed: parsed[0], gate: gated[0], recomputeLane, skipLane,
    decided: decided && decided[0],
  };
}

// --- behaviour 1: version-stale skip reroutes into Decide, same lane as a real request --

test("a version-stale skip reroutes: recompute=true, recompute_reason=version_stale, action=enrich, reaches Decide", () => {
  const r = runLane({
    existingRecord: completeRecord({ scoringVersion: STALE_VERSION }),
    recompute: false,
  });

  assert.equal(r.parsed.recompute, false, "whole-request intent was never asked for");
  assert.equal(r.gate.gate.action, "skip", "decideAction's own verdict is still skip");
  assert.equal(r.gate.action, "enrich", "the version-stale reroute flips skip -> enrich");
  assert.equal(r.gate.recompute, true, "the row is marked recompute for IF Company Recompute");
  assert.equal(r.gate.recompute_reason, "version_stale");
  assert.match(r.gate.gate.reason, /version-stale/);
  assert.equal(r.recomputeLane, true, "IF Company Recompute takes the true lane");
  assert.ok(r.decided, "Decide Company Action ran");
  assert.notEqual(r.decided.action, "create");
  assert.notEqual(r.decided.action, "skip");
});

test("undefined lv_icp_scoring_version (never scored) is stale exactly like a superseded string", () => {
  const r = runLane({
    existingRecord: completeRecord({}), // no scoringVersion key at all
    recompute: false,
  });

  assert.equal(r.gate.recompute, true);
  assert.equal(r.gate.recompute_reason, "version_stale");
});

// --- behaviour 2: version-fresh skip is UNCHANGED -- the regression guard -----------------

test("a version-fresh skip is NOT rerouted: recompute=false, recompute_reason=null, reaches Build Response", () => {
  const r = runLane({
    existingRecord: completeRecord({ scoringVersion: VERSION }),
    recompute: false,
  });

  assert.equal(r.gate.action, "skip", "no staleness on any axis, so the verdict is untouched");
  assert.equal(r.gate.recompute, false);
  assert.equal(r.gate.recompute_reason, null);
  assert.equal(r.recomputeLane, false, "IF Company Recompute takes the false lane");
  assert.equal(r.skipLane, true, "IF Company Skip takes the true lane -> Build Response");
});

// --- behaviour 3: operator-requested recompute is UNCHANGED, even on a stale record -------

test("an operator-requested recompute keeps recompute_reason=requested, never version_stale, even when the record IS version-stale", () => {
  const r = runLane({
    existingRecord: completeRecord({ scoringVersion: STALE_VERSION }),
    recompute: true,
  });

  assert.equal(r.parsed.recompute, true);
  assert.equal(r.gate.recompute, true);
  assert.equal(r.gate.recompute_reason, "requested",
    "the two intents are distinguishable -- request wins, never silently merged with staleness");
  assert.equal(r.recomputeLane, true);
});

test("recompute + create verdict is still refused (BUG-19 shape), unaffected by version staleness", () => {
  const r = runLane({
    existingRecord: {}, // search found nothing -> decideAction returns create
    recompute: true,
    identity_keys: { domain: "nosuchcompany.example", companyName: "No Such Company" },
  });

  assert.equal(r.gate.gate.action, "create");
  assert.equal(r.gate.action, "recompute_refused");
  assert.equal(r.gate.recompute_reason, "requested");
});

// --- behaviour 4: a create/enrich verdict is NEVER rerouted by version staleness ----------

test("a create verdict is never rerouted by version staleness -- no junk company is seeded", () => {
  const r = runLane({
    existingRecord: {}, // decideAction returns create
    recompute: false,
    identity_keys: { domain: "nosuchcompany.example", companyName: "No Such Company" },
  });

  assert.equal(r.gate.gate.action, "create");
  assert.equal(r.gate.action, "create", "create is untouched -- VERSION_RECOMPUTE requires action===skip");
  assert.equal(r.gate.recompute, false);
  assert.equal(r.gate.recompute_reason, null);
});

test("an enrich verdict (present-but-unstamped fields) is never rerouted by version staleness", () => {
  const r = runLane({
    existingRecord: {
      hs_object_id: "17317184159",
      name: "Unstamped Fixture Co",
      domain: "unstamped.example",
      lv_org_type: "broadcaster",
      lv_produces_content: "true",
      lv_country_region_normalized: "DE",
      // no lv_icp_scoring_version -- would read as version-stale, but the verdict here
      // is "enrich" (unstamped freshness fields), never "skip"
    },
    recompute: false,
    identity_keys: { domain: "unstamped.example" },
  });

  assert.equal(r.gate.gate.action, "enrich");
  assert.equal(r.gate.action, "enrich");
  assert.equal(r.gate.recompute, false, "VERSION_RECOMPUTE requires action===skip, not enrich");
  assert.equal(r.gate.recompute_reason, null);
});

// --- behaviour 5: write_request.action is "recompute" ONLY on a version-stale row --------

test("write_request.action is recompute on a version-stale row, while the row's own action stays enrich", () => {
  const r = runLane({
    existingRecord: completeRecord({ scoringVersion: STALE_VERSION }),
    recompute: false,
  });

  assert.equal(r.decided.action, "enrich", "the row's own action is unchanged by D-75-16");
  assert.equal(r.decided.write_request.action, "recompute",
    "the write gate's authority classification moves; the row's action does not");
});

test("write_request.action is enrich (not recompute) on an ordinary dispatch with no recompute intent at all", () => {
  // A verdict of "enrich" with no recompute intent takes the full provider waterfall on
  // the real lane (not simulated by runLane's simplified routing) before reaching Decide
  // Company Action -- feed the node directly, the same shape Merge Company hands it.
  const { byName } = loadWorkflow(CLOUD_WF_PATH);
  const row = {
    object_type: "companies",
    action: "enrich",
    recompute: false,
    existingRecord: {
      hs_object_id: "17317184159", name: "Ordinary Co", domain: "ordinary.example",
      lv_org_type: "broadcaster", lv_produces_content: "true",
      lv_country_region_normalized: "DE",
    },
    identity_keys: { domain: "ordinary.example" },
  };
  const [decided] = runCode(byName["Decide Company Action"], [row], {});
  assert.equal(decided.action, "enrich");
  assert.equal(decided.write_request.action, "enrich",
    "row.recompute is false, so write_request tracks the SAME plain classification as action");
});

test("write_request.action is ALSO recompute on an operator-requested row whose verdict happens to already be enrich -- D-75-16 grants the authority to every recompute-lane write, not only the version-stale reason", () => {
  const r = runLane({
    existingRecord: {
      hs_object_id: "17317184159", name: "Ordinary Co", domain: "ordinary.example",
      lv_org_type: "broadcaster", lv_produces_content: "true",
      lv_country_region_normalized: "DE",
    },
    recompute: true,
    identity_keys: { domain: "ordinary.example" },
  });

  assert.equal(r.gate.gate.action, "enrich");
  assert.equal(r.gate.recompute, true);
  assert.equal(r.gate.recompute_reason, "requested",
    "the RESPONSE still distinguishes the two intents even though the write authority does not");
  assert.equal(r.decided.write_request.action, "recompute",
    "the plan's own predicate is row.recompute===true && action===\"enrich\" -- it does not " +
    "further branch on recompute_reason, so an operator-requested recompute whose verdict " +
    "is already \"enrich\" rides the SAME write authority a version-stale reroute does");
});

// --- behaviour 6: the exact 4-key recompute PATCH property set, pinned by SORTED equality -

test("a bare recompute row's PATCH carries exactly 4 properties -- sorted array equality, not a subset check", () => {
  const r = runLane({
    existingRecord: completeRecord({ scoringVersion: STALE_VERSION }),
    recompute: false,
  });

  assert.ok(r.decided, "Decide Company Action ran");
  const keys = Object.keys(r.decided.properties).sort();
  assert.deepEqual(
    keys,
    ["lv_anti_icp_flag", "lv_anti_icp_flag_num", "lv_anti_icp_reason", "lv_icp_scoring_version"],
    "a bare recompute row (no merge object) must carry ONLY the veto triple + version stamp -- " +
    "an added key here (e.g. a status property riding the recompute path) must be RED"
  );
  assert.equal(r.decided.properties.lv_icp_scoring_version, VERSION);
});

// --- behaviour 7: no new node, no new Merge-starvation surface ---------------------------

test("the reroute rides the existing lane -- no new IF/Merge node, IF Company Skip's edges unchanged", () => {
  const { wf } = loadWorkflow(CLOUD_WF_PATH);
  const names = wf.nodes.map((n) => n.name);
  assert.equal(names.filter((n) => n === "IF Company Recompute").length, 1);
  const suspiciousVersionIfNodes = names.filter((n) => n.startsWith("IF ") && n.includes("Version"));
  assert.deepEqual(suspiciousVersionIfNodes, [], "no new version-named IF node was spliced");

  const c = wf.connections;
  assert.equal(
    c["IF Company Skip"].main[0][0].node,
    "IF Company Skip -> Build Response Merge Pass-Through",
    "IF Company Skip's true edge is unchanged by this plan");
});

// --- behaviour 8: the per-lane VERSION_STALE_REROUTE literal ------------------------------

test("VERSION_STALE_REROUTE is true on the cloud lane and false on the local-live preview lane", () => {
  const { byName: cloudByName } = loadWorkflow(CLOUD_WF_PATH);
  const { byName: liveByName } = loadWorkflow(LOCAL_LIVE_WF_PATH);

  const cloudMatch = /const VERSION_STALE_REROUTE = (\w+);/.exec(cloudByName["Company Gate"].parameters.jsCode);
  const liveMatch = /const VERSION_STALE_REROUTE = (\w+);/.exec(liveByName["Company Gate"].parameters.jsCode);
  assert.ok(cloudMatch, "cloud Company Gate declares VERSION_STALE_REROUTE");
  assert.ok(liveMatch, "local-live Company Gate declares VERSION_STALE_REROUTE");
  assert.equal(cloudMatch[1], "true");
  assert.equal(liveMatch[1], "false");
});

test("local-live's Company Gate never reroutes a version-stale row, even though it carries the same jsCode shape", () => {
  const { byName } = loadWorkflow(LOCAL_LIVE_WF_PATH);
  const outputs = {};
  const seedRow = {
    object_type: "companies",
    identity_keys: { domain: "versionstale.example" },
    existingRecord: completeRecord({ scoringVersion: STALE_VERSION }),
    lookup_failed: false,
  };
  const [gated] = runCode(byName["Company Gate"], [seedRow], outputs);
  assert.equal(gated.recompute, false,
    "VERSION_STALE_REROUTE=false on this lane -- ANDed against VERSION_RECOMPUTE, so it can never fire");
  assert.equal(gated.recompute_reason, null);
  // decideAction's own verdict is still "skip" (gate.gate.action) -- but the ROW's action
  // stays "skip" too, since nothing rewrote it. This lane has no IF Company Skip at all
  // (it flows unconditionally into "Build Company Requests"), so this assertion is scoped
  // to what THIS plan owns: the reroute never fires here.
  assert.equal(gated.action, gated.gate.action, "action was never rewritten on this lane");
});

// --- behaviour 9: the write-gate wiring end to end -- the key_link this plan's must_haves
// name explicitly: Decide Company Action's write_request classification -> HubSpot
// Company Update Write Gate -> _writeSafetyAllows('recompute', ...) -> the new flag ------

const DISABLED_RECOMPUTE_DECL = 'const ALLOW_HUBSPOT_RECOMPUTE_WRITES = "false";';
const ENABLED_RECOMPUTE_DECL = 'const ALLOW_HUBSPOT_RECOMPUTE_WRITES = "true";';

function armRecompute(jsCode) {
  assert.ok(
    jsCode.includes(DISABLED_RECOMPUTE_DECL),
    "committed jsCode must carry the disabled ALLOW_HUBSPOT_RECOMPUTE_WRITES declaration " +
      "verbatim for this swap to be equivalent to a real deploy-time overlay");
  return jsCode.replace(DISABLED_RECOMPUTE_DECL, ENABLED_RECOMPUTE_DECL);
}

test("HubSpot Company Update Write Gate: disarmed build denies a recompute-classified row even with an empty allowlist requirement bypassed", () => {
  const { byName } = loadWorkflow(CLOUD_WF_PATH);
  const gate = byName["HubSpot Company Update Write Gate"];
  assert.ok(gate, "the enrichment lane's companies-update gate exists");
  const row = {
    action: "enrich",
    write_request: { action: "recompute", hs_object_id: "18047161864", domain: null, email: null },
  };
  const [out] = runInputOnlyCode(gate.parameters.jsCode, [row]);
  assert.equal(out.write_allowed, false, "ALLOW_HUBSPOT_RECOMPUTE_WRITES ships false");
  assert.equal(out.action, "write_blocked");
  assert.match(out.write_blocked_reason, /recompute/i);
});

test("HubSpot Company Update Write Gate: armed build allows a recompute-classified row with NO allowlist entry at all", () => {
  const { byName } = loadWorkflow(CLOUD_WF_PATH);
  const gate = byName["HubSpot Company Update Write Gate"];
  const armedJs = armRecompute(gate.parameters.jsCode);
  const row = {
    action: "enrich",
    write_request: { action: "recompute", hs_object_id: "18047161864", domain: null, email: null },
  };
  const [out] = runInputOnlyCode(armedJs, [row]);
  assert.equal(out.write_allowed, true,
    "ALLOW_HUBSPOT_RECOMPUTE_WRITES alone grants it -- TEST_RECORD_IDS/TEST_RECORD_DOMAINS " +
    "are both empty in this jsCode and that is deliberately irrelevant here (D-75-16)");
});

test("HubSpot Company Update Write Gate: arming ALLOW_HUBSPOT_RECOMPUTE_WRITES grants NOTHING to an ordinary enrich-classified sibling row", () => {
  const { byName } = loadWorkflow(CLOUD_WF_PATH);
  const gate = byName["HubSpot Company Update Write Gate"];
  const armedJs = armRecompute(gate.parameters.jsCode);
  const row = {
    action: "enrich",
    write_request: { action: "enrich", hs_object_id: "18047161864", domain: null, email: null },
  };
  const [out] = runInputOnlyCode(armedJs, [row]);
  assert.equal(out.write_allowed, false,
    "the recompute flag is unreachable from the allowlist-gated enrich/create/review family");
  assert.equal(out.action, "write_blocked");
});
