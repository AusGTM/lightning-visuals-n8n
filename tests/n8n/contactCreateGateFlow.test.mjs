// tests/n8n/contactCreateGateFlow.test.mjs
//
// Regression guard for D-15/D-16/D-16a/D-16b (Phase 23 Plan 01): Set Config used to
// hardcode `allow_create: false` unconditionally, and that field never reached Decide
// Action anyway — Extract From File emits fresh items parsed from the binary CSV, so a
// value seeded on the webhook item upstream of it does not survive (the BUG 12/BUG 21
// row-loss family). The fix bakes the EXISTING overlayable ALLOW_HUBSPOT_CREATE constant
// into Decide Action itself, composed at the build site.
//
// This test executes the repo's OWN committed node jsCode via `new Function` — the same
// mechanism n8n's Code node uses at runtime — over the actual committed
// n8n/wf_contact_ingest_cloud.json. No external or untrusted input is ever interpolated
// into the function body.
//
// The armed variant is produced by string-replacing the disabled declaration with the
// enabled one — the EXACT same literal swap scripts/deploy_n8n_workflows.py's
// enable_baked_flags() performs — so this test fails if the declaration's spelling ever
// drifts out of the overlay's reach.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

function loadWorkflow() {
  return JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
}

function jsCodeOf(wf, name) {
  const node = wf.nodes.find((n) => n.name === name);
  assert.ok(node, `node present: ${name}`);
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) against seed items, the same shape
 * n8n's Code node executes it under. Returns the resulting json objects. */
function runCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  const out = fn($input) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// A net-new contact row shaped the way Merge Contacts hands it to Decide Action.
function netNewRow() {
  return {
    identity: { outcome: "net_new" },
    merge: { canonicalPatch: {} },
    email: "new.contact@example.com",
    firstname: "New",
    lastname: "Contact",
    // 2026-08-25: a create is HELD unless the row resolved to a company. Every create
    // case below is about the create GATE, so each row arrives already associated —
    // the hold itself is pinned by its own test in companyAssociationFlow.test.mjs.
    company_id: "9600000001",
    company_match: "domain",
    company_domain: "example.com",
  };
}

const DISABLED_DECL = 'const ALLOW_HUBSPOT_CREATE = "false";';
const ENABLED_DECL = 'const ALLOW_HUBSPOT_CREATE = "true";';

function armCreateConstant(jsCode) {
  assert.ok(
    jsCode.includes(DISABLED_DECL),
    "committed jsCode must carry the disabled ALLOW_HUBSPOT_CREATE declaration verbatim " +
      "for this swap to be equivalent to enable_baked_flags()"
  );
  return jsCode.replace(DISABLED_DECL, ENABLED_DECL);
}

test("Decide Action: committed (disarmed) build routes a net_new row to review", () => {
  const wf = loadWorkflow();
  const jsCode = jsCodeOf(wf, "Decide Action");
  const seed = netNewRow();
  const [result] = runCode(jsCode, [seed]);
  // Non-vacuity: the seed must actually reach Decide Action as net_new before the
  // action assertion means anything.
  assert.equal(result.outcome, "net_new", "seed row reached Decide Action as net_new");
  assert.equal(result.action, "review", "disarmed build must not create a net-new contact");
});

test("Decide Action: overlay-enabled build routes the SAME net_new row to create", () => {
  const wf = loadWorkflow();
  const armedJs = armCreateConstant(jsCodeOf(wf, "Decide Action"));
  const seed = netNewRow();
  const [result] = runCode(armedJs, [seed]);
  assert.equal(result.outcome, "net_new");
  assert.equal(result.action, "create", "armed build must allow creating a net-new contact");
  // BUG 19 behaviour preserved: identity must be seeded onto the create payload.
  assert.equal(result.properties.email, seed.email);
  assert.equal(result.properties.firstname, seed.firstname);
  assert.equal(result.properties.lastname, seed.lastname);
});

test("Decide Action: lookup_failed still downgrades a create to review even when armed", () => {
  const wf = loadWorkflow();
  const armedJs = armCreateConstant(jsCodeOf(wf, "Decide Action"));
  const seed = { ...netNewRow(), lookup_failed: true };
  const [result] = runCode(armedJs, [seed]);
  assert.equal(result.outcome, "net_new");
  assert.equal(result.action, "review", "a failed lookup must never be treated as a genuine create");
});

test("HubSpot Create Write Gate: a create-action row is dropped with an empty allowlist, and passes once armed with a matching domain", () => {
  const wf = loadWorkflow();
  const gateJs = jsCodeOf(wf, "HubSpot Create Write Gate");

  const createRow = { action: "create", hs_object_id: null, identity_keys: { domain: "exampleco.example" } };

  // Committed (disarmed): both write-safety booleans false, allowlist empty -> dropped.
  const disarmed = runCode(gateJs, [createRow]);
  assert.equal(disarmed.length, 0, "disarmed gate must drop the row (no items pass)");

  // Arm ALLOW_HUBSPOT_RECORD_WRITES + ALLOW_HUBSPOT_CREATE, but leave the allowlist
  // empty — the allowlist is a REAL second key, not satisfied by the two booleans alone.
  const booleansOnlyJs = gateJs
    .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";', 'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
    .replace('const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";');
  const stillDropped = runCode(booleansOnlyJs, [createRow]);
  assert.equal(stillDropped.length, 0, "booleans armed but allowlist empty must still drop the row");

  // Now also populate the domain allowlist with a matching value -> the row passes.
  const fullyArmedJs = booleansOnlyJs.replace(
    'const TEST_RECORD_DOMAINS = "";',
    'const TEST_RECORD_DOMAINS = "exampleco.example";'
  );
  const passed = runCode(fullyArmedJs, [createRow]);
  assert.equal(passed.length, 1, "fully armed gate with a matching allowlist entry must pass the row");
  assert.equal(passed[0].action, "create");
});

// --- BUG 27: the create gate must pass DECIDE ACTION'S OWN OUTPUT --------------------
// Found live by the 23-06 armed canary (runs 1122/1123/1126): the gate derived domain
// from identity_keys.domain/json.domain — fields Decide Action never emits — so a
// net-new create evaluated _writeSafetyAllows('create', null, null) and was denied
// however armed the backend was. The earlier tests here fed the gate hand-shaped items,
// which is exactly how the mismatch shipped: a contract held in two places needs a test
// that reads both. This one RUNS Decide Action, then feeds its verbatim output to the
// gate — the two node bodies can no longer disagree silently.

function armedGateCode(wf) {
  return jsCodeOf(wf, "HubSpot Create Write Gate")
    .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
             'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
    .replace(DISABLED_DECL, ENABLED_DECL)
    .replace('const TEST_RECORD_DOMAINS = "";',
             'const TEST_RECORD_DOMAINS = "australiagtm.com";');
}

function decideActionOutput(wf, email) {
  const armedDecide = jsCodeOf(wf, "Decide Action").replace(DISABLED_DECL, ENABLED_DECL);
  const row = { ...netNewRow(), email };
  const out = runCode(armedDecide, [row]);
  assert.equal(out.length, 1);
  assert.equal(out[0].action, "create");
  return out;
}

test("BUG 27: an armed create gate passes Decide Action's verbatim net-new output when the email domain is allowlisted", () => {
  const wf = loadWorkflow();
  const decided = decideActionOutput(wf, "canary-23-06-20260731@australiagtm.com");
  assert.equal(decided[0].hs_object_id, null, "net-new has no id — domain is the only allowlist path");

  const through = runCode(armedGateCode(wf), decided);
  assert.equal(through.length, 1, "the canary's exact failure: armed + allowlisted domain must pass");
});

test("BUG 27 guard still binds: a non-allowlisted domain is dropped even when armed", () => {
  const wf = loadWorkflow();
  const decided = decideActionOutput(wf, "someone@elsewhere.example");
  assert.equal(runCode(armedGateCode(wf), decided).length, 0);
});

test("BUG 27 guard still binds: disarmed drops the allowlisted row too", () => {
  const wf = loadWorkflow();
  const decided = decideActionOutput(wf, "canary-23-06-20260731@australiagtm.com");
  const disarmedGate = jsCodeOf(wf, "HubSpot Create Write Gate")
    .replace('const TEST_RECORD_DOMAINS = "";',
             'const TEST_RECORD_DOMAINS = "australiagtm.com";');
  assert.equal(runCode(disarmedGate, decided).length, 0);
});
