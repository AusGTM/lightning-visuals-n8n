// End-to-end oracle for BUG 11 (Phase 16.7-01): drives a real merge-shaped row through
// the BUILT "Merge Winners" and "Decide Action" node bodies, then evaluates the BUILT
// "HubSpot Update" node's own url/jsonBody expressions against the emitted item — the
// literal outbound HTTP request the live run would issue.
//
// Defect: the deployed "HubSpot Update" / "HubSpot Company Update" nodes are native
// `n8n-nodes-base.hubspot` nodes with an EMPTY `updateFields` map. They reference
// `$json.properties` nowhere, so a request literally cannot be constructed from their
// parameters — a canary fired against them would issue a property-less update, and a
// non-clobber proof against an empty write is vacuous. This is BUG 11 (same shape as
// BUG 10 — a node config that passes the whole offline suite and deploys clean, wrong
// only against the real API), found here by reading the built artifact instead of by
// burning an armed live window on it.
//
// Mechanism: `new Function(...)` over `parameters.jsCode` read out of the committed
// workflow JSON — the same idiom `researchChainRowFlow.test.mjs` / `bareEventChainFlow.
// test.mjs` already establish for executing a BUILT Code node body offline. This oracle
// starts one stage later than bareEventChainFlow (at a "Merge Winners"-shaped row, not a
// raw webhook body), reusing the same row vocabulary (existingRecord/scored/identity_keys/
// object_type/action) so the two harnesses stay legible together.
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
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function loadWorkflow() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return byName;
}

// --- (1) tiny expression evaluator ------------------------------------------------------
// Given an n8n parameter string that begins with `=`, substitutes each `{{ ... }}`
// segment by evaluating its inner JavaScript with `$json` bound to the item under test,
// and returns the resulting string. Exists so the test asserts against the request the
// NODE would build (by reading its own url/body parameters), not against a request the
// test author retyped by hand.
function evalNodeExpr(paramValue, $json) {
  if (typeof paramValue !== "string" || !paramValue.startsWith("=")) return undefined;
  const template = paramValue.slice(1);
  return template.replace(/\{\{([\s\S]*?)\}\}/g, (_, expr) => {
    const fn = new Function("$json", `"use strict"; return (${expr});`);
    const val = fn($json);
    return typeof val === "string" ? val : String(val);
  });
}

// Runs a Code node's jsCode over a list of plain-object items, mirroring n8n's own
// $input/$json context. No node in this chain reads `$(name)` by node name (verified by
// reading ENRICH_MERGE / ENRICH_DECIDE_CLOUD), so `$` is a harmless stub.
function runJsCode(jsCode, items) {
  const $input = {
    all: () => items.map((j) => ({ json: j })),
    get item() { return { json: items[0] }; },
  };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date("2026-07-29T00:00:00Z");
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, items[0], {}, $now, $now) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// Textually rewrites the write-safety constants baked into "Decide Action"'s jsCode to
// the armed literals — the SAME textual rewrite `enable_baked_flags()` performs at deploy
// time (scripts/deploy_n8n_workflows.py), done in-test rather than by importing the
// deploy script (it is not the unit under test here). Returns the match count per
// rewrite so a rewrite that matched nothing fails loudly instead of silently leaving the
// disarmed body in place.
function armWriteSafety(jsCode) {
  const rewrites = [
    { from: 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
      to:   'const ALLOW_HUBSPOT_RECORD_WRITES = "true";' },
    { from: 'const TEST_RECORD_IDS = "";',
      to:   'const TEST_RECORD_IDS = "201";' },
  ];
  let code = jsCode;
  const counts = {};
  for (const { from, to } of rewrites) {
    const count = code.split(from).length - 1;
    counts[from] = count;
    code = code.split(from).join(to);
  }
  return { code, counts };
}

// Evaluates a write node's own url/jsonBody parameters against the emitted item and
// returns the literal outbound request. THIS IS THE ASSERTION THAT FAILS RED TODAY: the
// committed "HubSpot Update" node is a native n8n-nodes-base.hubspot node with no url and
// no jsonBody parameter at all — no request can be constructed from its parameters.
function buildOutboundPatchRequest(node, item) {
  assert.equal(node.type, "n8n-nodes-base.httpRequest",
    `${node.name}: expected a credential-bound httpRequest node carrying the computed ` +
    `patch; got type=${node.type} (BUG 11: the native hubspot node's updateFields is an ` +
    `empty map and references $json.properties nowhere — no PATCH request can be built)`);
  const params = node.parameters || {};
  assert.equal(params.method, "PATCH", `${node.name}: expected PATCH method, got ${params.method}`);
  const url = evalNodeExpr(params.url, item);
  assert.ok(url, `${node.name}: no url expression present — cannot construct a request`);
  const bodyStr = evalNodeExpr(params.jsonBody, item);
  assert.ok(bodyStr, `${node.name}: no jsonBody expression present — cannot construct a request body`);
  const body = JSON.parse(bodyStr);
  return { method: params.method, url, body };
}

// --- (2) the seed row --------------------------------------------------------------------
// Shaped like "Merge Winners"' input (identity_keys/existingRecord/scored/object_type/
// action — the same vocabulary bareEventChainFlow.test.mjs uses one stage earlier).
// hs_object_id 201 is the real contact from 16.7-CONTEXT.md's ground truth (Brendan
// Carmody, brendan@lightningvisuals.com) — the exact record Plan 02's armed window will
// target.
//
// Expected per-field outcome, derived from DEFAULT_CONTACT_POLICY (mergeContacts.js
// lines 24-32) and _gate (lines 85-122) against a flat candidate confidence of 85 (the
// literal `mergeContacts(existingRecord, candidate, undefined, { confidence: 85 })` call
// "Merge Winners" makes):
//   email     class manual_protected,  min_confidence 95 -> 85 < 95            -> needs_review (never promotes; also hard-guarded regardless of class)
//   phone     class fill_blank_only,   min_confidence 80 -> 85 >= 80, but the existing
//             value is NON-BLANK ("+61399999999", the protected-field probe)    -> stage_only (non-clobber: this is the behaviour the whole phase exists to prove)
//   jobtitle  class stale_refreshable, min_confidence 75 -> 85 >= 75, existing value
//             is BLANK ("")                                                     -> promote (+ cache-key lv_jobtitle_verified_at, CONTACT_CACHE_KEY_FIELDS.jobtitle)
//   seniority class system_owned,      min_confidence 75 -> 85 >= 75 (system_owned
//             promotes irrespective of blank/non-blank)                         -> promote
const SEED_ROW = {
  action: "enrich",
  object_type: "contacts",
  identity_keys: { domain: null },
  existingRecord: {
    hs_object_id: "201",
    email: "brendan@lightningvisuals.com",
    phone: "+61399999999",   // protected probe: non-blank, fill_blank_only
    jobtitle: "",            // blank: stale_refreshable promotes
    seniority: "",           // blank: system_owned promotes regardless
  },
  scored: {
    winners: {
      email: "someone-else@example.com",
      phone: "+61388888888",
      jobtitle: "Head of Broadcast",
      seniority: "Director",
    },
  },
};

// --- (3) run the chain, disarmed first (proves the harness is really running the
// shipped safety gate, not a hand-rolled stand-in) ---------------------------------------

test("disarmed (committed build, empty allowlist): Decide Action emits action write_blocked for hs_object_id 201", () => {
  const nodes = loadWorkflow();
  const mergeOut = runJsCode(nodes["Merge Winners"].parameters.jsCode, [SEED_ROW]);
  assert.ok(mergeOut[0].merge, "Merge Winners produced a merge result");
  const decideOut = runJsCode(nodes["Decide Action"].parameters.jsCode, mergeOut);
  assert.equal(decideOut[0].hs_object_id, "201");
  assert.equal(decideOut[0].action, "write_blocked",
    "TEST_RECORD_IDS ships empty in the committed build — every write must be blocked");
});

test("armed (in-test constant rewrite, mirrors enable_baked_flags): Decide Action emits a non-empty properties patch honoring the non-clobber policy", () => {
  const nodes = loadWorkflow();
  const mergeOut = runJsCode(nodes["Merge Winners"].parameters.jsCode, [SEED_ROW]);
  const { code: armedCode, counts } = armWriteSafety(nodes["Decide Action"].parameters.jsCode);
  for (const [target, count] of Object.entries(counts)) {
    assert.equal(count, 1, `constant rewrite must match exactly once (got ${count}): ${target}`);
  }
  const decideOut = runJsCode(armedCode, mergeOut);
  const item = decideOut[0];

  assert.equal(item.hs_object_id, "201");
  assert.equal(item.action, "enrich", "armed + non-empty allowlist -> action enrich, not write_blocked");
  assert.ok(item.properties && typeof item.properties === "object" && !Array.isArray(item.properties));

  // Promotes: system_owned seniority (flat confidence 85 clears its 75 threshold).
  assert.equal(item.properties.seniority, "Director");
  // Promotes: stale_refreshable jobtitle, existing value blank.
  assert.equal(item.properties.jobtitle, "Head of Broadcast");
  assert.ok(item.properties.lv_jobtitle_verified_at, "cache-key datetime present for the promoted field");
  assert.ok(item.properties.lv_contact_enrichment_provenance, "provenance blob present");

  // Excluded: email (85 < 95 threshold, plus the hard email guard regardless of class).
  assert.equal(item.properties.email, undefined);
  // Excluded: phone (fill_blank_only, existing value non-blank) — THE non-clobber proof.
  assert.equal(item.properties.phone, undefined);

  // Stash for the next test (module-level items don't share test bodies in node:test,
  // so this test's assertions above establish the fixture the outbound-request test
  // re-derives independently below, rather than passing state between tests).
});

test("outbound PATCH request (RED today — BUG 11): the HubSpot Update node's own url/jsonBody expressions, evaluated against the armed item, yield a real PATCH to CRM v3 for id 201", () => {
  const nodes = loadWorkflow();
  const mergeOut = runJsCode(nodes["Merge Winners"].parameters.jsCode, [SEED_ROW]);
  const { code: armedCode } = armWriteSafety(nodes["Decide Action"].parameters.jsCode);
  const armedItem = runJsCode(armedCode, mergeOut)[0];

  const req = buildOutboundPatchRequest(nodes["HubSpot Update"], armedItem);
  assert.equal(req.method, "PATCH");
  assert.match(req.url, /^https:\/\/api\.hubapi\.com\/crm\/v3\/objects\/contacts\/201$/,
    `url must be a literal PATCH to CRM v3 object id 201, got: ${req.url}`);
  assert.deepEqual(req.body, { properties: armedItem.properties },
    "PATCH body must be an object with a single properties key equal to the emitted patch");
});
