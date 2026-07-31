// tests/n8n/reviewWriteFlagSeparation.test.mjs
//
// D-02 / D-08e (Phase 30 Plan 01): review writeback is armed by its OWN backend constant,
// ALLOW_HUBSPOT_REVIEW_WRITES, and arming it must grant nothing on the dispatch path that
// Phase 28's arm/dispatch/disarm cycle drives. Without an executable proof, "the two gates
// are separate" is a claim about a shared function that every write gate in every cloud
// workflow inlines — exactly the kind of claim that rots into a shared boolean.
//
// This drives the repo's OWN committed jsCode through `new Function` — the same mechanism
// n8n's Code node uses — over the actual committed n8n/wf_contact_ingest_cloud.json, and
// arms constants by swapping the EXACT disabled declaration for the enabled one, which is
// what scripts/deploy_n8n_workflows.py's enable_baked_flags() does. So a drift in how the
// builder spells a declaration fails this test rather than passing vacuously. No external
// or untrusted input is ever interpolated into the function body — the only source is the
// committed workflow artifact in this repo (same rationale as contactCreateGateFlow.test.mjs).
//
// The reverse direction — a review-action row permitted with ONLY the review constant
// armed — is proved in 30-02 against the review write gate, which does not exist yet.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");
const GATE_NODE = "HubSpot Create Write Gate";
const DOMAIN = "exampleco.example";

function gateJs() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const node = wf.nodes.find((n) => n.name === GATE_NODE);
  assert.ok(node, `node present: ${GATE_NODE}`);
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) against seed items. Returns items out. */
function runCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  return new Function("$input", `"use strict";\n${jsCode}`)($input) || [];
}

/** The literal swap enable_baked_flags() performs, asserted to have actually matched. */
function arm(jsCode, name, value) {
  const from = `const ${name} = "${name.startsWith("TEST_RECORD_") ? "" : "false"}";`;
  const to = `const ${name} = "${value}";`;
  assert.ok(
    jsCode.includes(from),
    `committed jsCode must carry ${from} verbatim for this swap to match enable_baked_flags()`
  );
  return jsCode.replace(from, to);
}

const createRow = {
  action: "create",
  hs_object_id: null,
  identity_keys: { domain: DOMAIN },
};

test("committed (disarmed) create gate drops a create row", () => {
  assert.equal(runCode(gateJs(), [createRow]).length, 0);
});

test("arming ONLY ALLOW_HUBSPOT_REVIEW_WRITES grants nothing on the dispatch path", () => {
  // Review constant armed AND a matching allowlist entry present — the allowlist is not
  // the thing denying this row. If this ever passes, the review flag has become a second
  // way to satisfy the dispatch gate and D-02's separation is gone.
  let js = arm(gateJs(), "ALLOW_HUBSPOT_REVIEW_WRITES", "true");
  js = arm(js, "TEST_RECORD_DOMAINS", DOMAIN);
  assert.equal(
    runCode(js, [createRow]).length,
    0,
    "review arming must not enable a create/dispatch write"
  );
});

test("arming the dispatch constants DOES pass the same row (the drop above was the missing dispatch arm, not a broken harness)", () => {
  let js = arm(gateJs(), "ALLOW_HUBSPOT_RECORD_WRITES", "true");
  js = arm(js, "ALLOW_HUBSPOT_CREATE", "true");
  js = arm(js, "TEST_RECORD_DOMAINS", DOMAIN);
  const out = runCode(js, [createRow]);
  assert.equal(out.length, 1, "dispatch-armed gate with a matching allowlist entry passes");
  assert.equal(out[0].json.action, "create");
});

test("dispatch arming leaves ALLOW_HUBSPOT_REVIEW_WRITES baked false (Phase 28's cycle cannot arm review)", () => {
  let js = arm(gateJs(), "ALLOW_HUBSPOT_RECORD_WRITES", "true");
  js = arm(js, "ALLOW_HUBSPOT_CREATE", "true");
  assert.ok(js.includes('const ALLOW_HUBSPOT_REVIEW_WRITES = "false";'));
});
