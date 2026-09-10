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

// Phase 66 Plan 02 (D-66-01 companies half): ENRICH_CO_GATE's REQUIRED widened from 2 to
// 13 fields (66-COVERAGE.md's derivation). "Complete" must mean complete against the
// WIDENED list, or this fixture no longer gates to `skip` at all (missing, not stale) and
// every assertion below that depends on a genuine skip verdict is testing the wrong thing.
// Only lv_org_type/lv_produces_content carry a stale_after_days TTL in POLICY, so only
// those two need a _verified_at stamp — the other 11 just need to be non-blank.
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
    // Phase 70 Plan 04 (D-70-04): "recompute" now rides the row itself (Company Gate
    // reads bare `row.recompute`, never `$('Parse HubSpot Event')`) — mirrored here
    // exactly like `mode` already is, since a real "Parse HubSpot Event" -> "Company
    // Gate" edge carries the whole parsed row forward.
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

  // Phase 70 Plan 03 (D-70-01): "Build Response" now sits behind a real Merge — the
  // true lane's sole edge is the Merge, not the Code node directly. Phase 70 Plan 11
  // (D-70-20): the routing IF's own edge no longer lands on the Merge input directly
  // — a pass-through sits between them (no routing IF has a direct edge to a Merge
  // input on this lane any more).
  assert.deepEqual(
    targetsOf(r.wf, "IF Company Skip", 0), ["IF Company Skip -> Build Response Merge Pass-Through"]);
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

  // Phase 70 Plan 03 (D-70-01): "Company Gate" now ALSO fans to two starved-lane
  // sentinels (D-70-01's global-sentinel mechanism) — additive edges off this same
  // single-producer node, never a re-point of the original "IF Company Recompute" edge.
  assert.deepEqual(
    targetsOf(wf, "Company Gate", 0),
    ["IF Company Recompute", "Companies Waterfall Absent Sentinel", "Companies None Skip Sentinel"],
    "Company Gate no longer feeds Build Company Requests directly");
  // Phase 70 Plan 03 (D-70-01): "Decide Company Action" now sits behind a real Merge —
  // the true lane's sole edge is that Merge, not the Code node directly; the Merge
  // itself is free of provider/research/judge nodes exactly as this test's name says.
  // Phase 70 Plan 11 (D-70-20): that edge is now a pass-through, never a direct
  // routing-IF-to-Merge edge — still ONE hop, still free of any costly node.
  assert.deepEqual(
    targetsOf(wf, "IF Company Recompute", 0),
    ["IF Company Recompute -> Decide Company Action Merge Pass-Through"],
    "the true lane is ONE hop (a pass-through) — nothing costly may sit between the gate and the sole veto writer");
  assert.deepEqual(targetsOf(wf, "IF Company Recompute", 1), ["IF Company Skip"]);

  for (const costly of COSTLY_NODES) {
    assert.ok(
      !targetsOf(wf, "IF Company Recompute", 0).includes(costly),
      `${costly} must not sit on the recompute lane`);
  }
});

// --- behaviour 6: execution 11858's refusal, now sourced from the gate --------------------
//
// CLAUDE.md §13.0: "Execution 11858 ran the whole lane, derived the correct veto, and
// returned action: write_blocked because the allowlist was empty. Deriving is free;
// writing still needs a deliberately armed, record-scoped window." That behaviour is
// unchanged — only its SOURCE moved. Phase 70 Plan 05 Task 2 sub-step 2b (D-70-13) took
// the write-permission predicate out of "Decide Company Action" and gave the enrichment
// lane the spliced gate it had never had, so the refusal is now the gate's verdict rather
// than a value the decision node stamped on itself.

test("execution 11858's refusal survives, now emitted by the spliced gate rather than by Decide Company Action", () => {
  const { wf, byName } = loadWorkflow();
  const r = runLane({ existingRecord: completeRecord("US"), recompute: true });

  // The lane still runs end to end and still derives the veto — that is the free half.
  assert.equal(r.decided.properties.lv_anti_icp_flag, "true");
  assert.equal(r.decided.action, "enrich",
    "the decision node now reports WHAT the row is; permission is not its call");
  assert.equal(r.decided.write_request.hs_object_id, r.decided.hs_object_id,
    "and it emits the canonical write_request the gate reads (D-70-12)");

  // The paid half: with the allowlist empty, the gate refuses — and EMITS the refusal
  // (D-70-14) rather than dropping the row, so the caller still gets a report.
  const gate = byName["HubSpot Company Update Write Gate"];
  assert.ok(gate, "the enrichment lane's companies-update gate exists (2b)");
  const gated = runCode(gate, [r.decided], {});
  assert.equal(gated.length, 1, "a refused row is a row, never a silence");
  assert.equal(gated[0].write_allowed, false, "empty allowlist denies every write");
  assert.equal(gated[0].action, "write_blocked",
    "the exact outcome execution 11858 returned, from its new home");
  assert.ok(gated[0].write_blocked_reason);

  // And it reaches the response: the gate's false lane has its own Build Response Merge
  // input, so nothing about this refusal depends on the write node having run. Phase 70
  // Plan 11 (D-70-20): that false lane is now a pass-through, not a direct edge.
  assert.deepEqual(
    targetsOf(wf, "HubSpot Company Update Write Gate IF", 0), ["HubSpot Company Update"]);
  assert.deepEqual(
    targetsOf(wf, "HubSpot Company Update Write Gate IF", 1),
    ["HubSpot Company Update Write Gate IF -> Build Response Merge Pass-Through"]);
});
