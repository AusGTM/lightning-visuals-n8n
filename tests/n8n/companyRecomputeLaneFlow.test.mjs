// Phase 47.5 Plan 01 — regression guard for the REQUEST-LEVEL RECOMPUTE LANE.
//
// Defect (root-caused live from n8n execution 11846, Simtech LED 18047161864): a company
// whose enrichment inputs are all present, fresh and valid gets `action:"skip"` from
// `Company Gate`; `Normalize + Score Company` then drops every skipped row on its first
// line, so the branch ends there and `Decide Company Action` — the ONLY node that writes
// lv_anti_icp_flag / lv_anti_icp_reason — never runs. A complete record's veto is frozen,
// correct or not, and the caller sees a bare 200 (RECOMP-02: silent success).
//
// The fix is a request-level lane, not a mode value: `IF Company Recompute` reads
// `$('Parse HubSpot Event').first().json.recompute === true` (whole-request, so the two
// lanes are mutually exclusive per execution by construction) and routes straight into
// `Decide Company Action` — no provider, no research, no judge, no merge. Its false lane
// runs `IF Company Skip`, which terminates a skipped row at `Build Response` carrying its
// gate reason instead of dying silently.
//
// This test drives the ACTUAL emitted jsCode of the committed workflow across the hop
// sequence with faked `$()` node lookups (the researchChainRowFlow.test.mjs template), AND
// evaluates the two IF nodes' real leftValue expressions against the same context — an IF
// node carries no jsCode, so without that the test would assume the routing it exists to
// pin.
//
// NOTE: this executes the repo's OWN committed workflow jsCode/expressions via
// `new Function` — the same thing n8n does at runtime — over a fixed, in-repo list of node
// names. No external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

// Nodes that cost money or time. None may appear on the recompute lane.
const COSTLY_NODES = [
  "Build Company Requests", "Lusha Company", "Apollo Org", "ZoomInfo Company",
  "Normalize + Score Company", "Research Trigger Gate", "IF Research Needed",
  "Build Research Request", "Claude Web Research", "Validate Research Output",
  "Judge Gate", "IF Needs Judge", "Build Judge Request", "Judge Call",
  "Apply Judge Verdict", "Merge Company",
];

function loadWorkflow() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
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

// An IF node has no jsCode — its predicate lives in the condition's leftValue as an n8n
// expression (`={{ ... }}`). Evaluate the REAL committed expression, never a restatement.
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

function targetsOf(wf, nodeName, branchIndex) {
  const branch = ((wf.connections[nodeName] || {}).main || [])[branchIndex] || [];
  return branch.map((e) => e.node);
}

// --- fixtures ---------------------------------------------------------------------------

// ENRICH_CO_GATE calls decideAction with a REAL `new Date()`, not an injectable clock, so
// the freshness stamps must be computed relative to now or the test rots (TTL is 180 days).
const FRESH = new Date(Date.now() - 86400000).toISOString();

function completeRecord(region) {
  return {
    hs_object_id: "18047161864",
    name: "Recompute Fixture Co",
    domain: "recompute.example",
    lv_org_type: "broadcaster",
    lv_produces_content: "true",
    lv_org_type_verified_at: FRESH,
    lv_produces_content_verified_at: FRESH,
    lv_country_region_normalized: region,
  };
}

// Present required values with NO _verified_at stamps — the gate reads unknown freshness as
// stale and returns `enrich` (plan 03's acceptance shape: the intent is request-level, so
// the verdict never decides which lane carries the row).
function unstampedRecord(region) {
  return {
    hs_object_id: "17317184159",
    name: "Unstamped Fixture Co",
    domain: "unstamped.example",
    lv_org_type: "broadcaster",
    lv_produces_content: "true",
    lv_country_region_normalized: region,
  };
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
  const { wf, byName } = loadWorkflow();
  const outputs = {};

  for (const name of ["Parse HubSpot Event", "Company Gate", "Decide Company Action"]) {
    assert.ok(byName[name], `node present: ${name}`);
  }
  for (const name of ["IF Company Recompute", "IF Company Skip"]) {
    assert.ok(byName[name], `node present: ${name}`);
  }

  const parsed = runCode(
    byName["Parse HubSpot Event"], [{ body: webhookEvent({ recompute }) }], outputs);
  outputs["Parse HubSpot Event"] = parsed;

  const seedRow = {
    object_type: "companies",
    object_id: parsed[0].object_id,
    identity_keys: identity_keys || { domain: "recompute.example" },
    existingRecord,
    lookup_failed: false,
    mode: parsed[0].mode,
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
    wf, parsed: parsed[0], gate: gated[0], recomputeLane, skipLane,
    decided: decided && decided[0],
  };
}

// --- behaviour 1: complete record + recompute reaches Decide, veto from existingRecord ----

test("recompute carries a COMPLETE record (gate verdict skip) to Decide, veto derived from existingRecord", () => {
  const r = runLane({ existingRecord: completeRecord("US"), recompute: true });

  assert.equal(r.parsed.recompute, true, "Parse HubSpot Event normalized recompute to true");
  assert.equal(r.gate.gate.action, "skip", "decideAction's own verdict is still skip");
  assert.equal(r.gate.action, "enrich", "the gate flips skip -> enrich under the recompute intent");
  assert.equal(r.recomputeLane, true, "IF Company Recompute takes the true lane");

  // Merge-free derivation: `row.merge` is absent, so properties is {} and the ?? chain
  // falls through to existingRecord.
  assert.equal(r.decided.properties.lv_anti_icp_flag, "true");
  assert.equal(r.decided.properties.lv_anti_icp_reason, "Non-ANZ geography");
  assert.notEqual(r.decided.action, "create");
  assert.notEqual(r.decided.action, "skip");
  assert.notEqual(r.decided.action, "proposed", "no mode was sent, so isReturnOnly stays false");
});

test("a corrected region on the SAME complete record clears the veto — the whole point of the lane", () => {
  const r = runLane({ existingRecord: completeRecord("AU"), recompute: true });

  assert.equal(r.recomputeLane, true);
  assert.equal(r.decided.properties.lv_anti_icp_flag, "false");
  assert.equal(r.decided.properties.lv_anti_icp_reason, "");
});

// --- behaviour 2: no intent -> observable skip terminal, never Build Company Requests -----

test("without the recompute intent a complete record terminates observably at Build Response", () => {
  const r = runLane({ existingRecord: completeRecord("US"), recompute: false });

  assert.equal(r.parsed.recompute, false, "absent recompute normalizes to false, fail-closed");
  assert.equal(r.gate.action, "skip", "no intent, so the gate's verdict is untouched");
  assert.equal(r.recomputeLane, false, "IF Company Recompute takes the false lane");
  assert.equal(r.skipLane, true, "IF Company Skip takes the true lane");
  assert.equal(
    r.gate.gate.reason, "all required fields present, fresh and valid",
    "the gate reason rides to Build Response so the caller can tell 'complete' from 'broken'");

  assert.deepEqual(targetsOf(r.wf, "IF Company Skip", 0), ["Build Response"]);
  assert.deepEqual(targetsOf(r.wf, "IF Company Skip", 1), ["Build Company Requests"]);
});

// --- behaviour 3: recompute + create verdict is REFUSED (BUG-19 shape) --------------------

test("a recompute for a record that resolves to no company is refused, never created", () => {
  const r = runLane({
    existingRecord: {},           // search found nothing -> decideAction returns create
    recompute: true,
    identity_keys: { domain: "nosuchcompany.example", companyName: "No Such Company" },
  });

  assert.equal(r.gate.gate.action, "create", "decideAction's own verdict is create");
  assert.equal(r.gate.action, "recompute_refused", "the gate refuses rather than enriching");
  assert.match(r.gate.gate.reason, /recompute/i, "the refusal reason is readable in the response");
  assert.equal(r.recomputeLane, true, "the request-level lane still carries the row to Decide");

  // BUG 19: the create-seed branch is gated on action === "create" and must not fire.
  assert.notEqual(r.decided.action, "create");
  assert.equal(r.decided.properties.domain, undefined, "no seeded domain");
  assert.equal(r.decided.properties.name, undefined, "no seeded name");
});

// --- behaviour 4: an enrich verdict under the intent ALSO takes the recompute lane --------

test("an enrich verdict under the recompute intent takes the same lane (request-level, not per-verdict)", () => {
  const r = runLane({
    existingRecord: unstampedRecord("US"),
    recompute: true,
    identity_keys: { domain: "unstamped.example" },
  });

  assert.equal(r.gate.gate.action, "enrich", "present-but-unstamped reads as stale");
  assert.equal(r.gate.action, "enrich", "enrich is untouched by the recompute mapping");
  assert.equal(r.recomputeLane, true, "the lane is chosen by the REQUEST, never by the verdict");
  assert.equal(r.decided.properties.lv_anti_icp_flag, "true");
});

// --- behaviour 5: the lane is free — no provider, research or judge node on it ------------

test("the recompute lane is a single edge into Decide Company Action — zero provider/research/judge nodes", () => {
  const { wf } = loadWorkflow();

  assert.deepEqual(
    targetsOf(wf, "Company Gate", 0), ["IF Company Recompute"],
    "Company Gate no longer feeds Build Company Requests directly");
  assert.deepEqual(
    targetsOf(wf, "IF Company Recompute", 0), ["Decide Company Action"],
    "the true lane is ONE edge — nothing may sit between the gate and the sole veto writer");
  assert.deepEqual(targetsOf(wf, "IF Company Recompute", 1), ["IF Company Skip"]);

  for (const costly of COSTLY_NODES) {
    assert.ok(
      !targetsOf(wf, "IF Company Recompute", 0).includes(costly),
      `${costly} must not sit on the recompute lane`);
  }
});
