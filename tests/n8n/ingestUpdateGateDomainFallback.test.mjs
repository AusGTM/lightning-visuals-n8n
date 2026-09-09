// tests/n8n/ingestUpdateGateDomainFallback.test.mjs
//
// F11 (uat-batch-review-row-reads-failed, execution 12181): "HubSpot Update Write Gate"
// reads a row's domain as `identity_keys.domain || json.domain`, but the ingest lane's
// "Decide Action" only ever emits `company_domain` (and `email`) on an update row — the
// CREATE gate has an email-domain fallback for this exact class of gap (BUG 27), the
// UPDATE gate had none. A domain-only allowlist (TEST_RECORD_DOMAINS, no
// TEST_RECORD_IDS) could therefore never admit an update, matching BUG 24's precedent
// (a gate reading a field its own lane never emits) — fixed the same way BUG 24 was:
// make the lane populate the field the gate already reads, not touch the shared gate.
//
// Runs the repo's OWN committed node jsCode via `new Function`, same mechanism n8n's
// Code node uses, over the actual committed n8n/wf_contact_ingest_cloud.json. No
// external or untrusted input is ever interpolated into the function body.
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

function runCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  const out = fn($input) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

/** The exact literal swap deploy_n8n_workflows.py's enable_baked_flags() performs. */
function armConstants(jsCode, constants) {
  let out = jsCode;
  for (const [name, value] of Object.entries(constants)) {
    const fromEmpty = `const ${name} = "";`;
    const fromFalse = `const ${name} = "false";`;
    const decl = out.includes(fromFalse) ? fromFalse : fromEmpty;
    assert.ok(out.includes(decl),
      `committed jsCode must carry the disabled ${name} declaration verbatim: ${name}`);
    out = out.replace(decl, `const ${name} = ${JSON.stringify(value)};`);
  }
  return out;
}

// Shaped exactly as "Decide Action" hands "IF Update" -> the gate: an existing contact
// (execution 12181's Greg Purcell), matched by name/company, no hs_object_id in the
// allowlist, only the company's domain armed.
function matchedUpdateRow() {
  return {
    identity: { outcome: "match", contact_id: "35551" },
    merge: { canonicalPatch: {} },
    company_id: "9600000001",
    company_match: "domain",
    company_domain: "wyongraceclub.com.au",
    email_normalized: "greg@wyongraceclub.com.au",
  };
}

// F12 (uat-batch-review-row-reads-failed): Decide Action now ALSO pre-computes an
// update's write-safety verdict (scripts/build_cloud_workflows.py), so it must be armed
// with the SAME allowlist the gate tests below use, or it reports `write_blocked`
// before the row ever reaches the gate — arming both here proves the gate is still an
// independent, second check (defense-in-depth), not a dead one Decide Action now
// bypasses.
function armedDecideAction(wf) {
  return armConstants(jsCodeOf(wf, "Decide Action"), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true",
    TEST_RECORD_DOMAINS: "wyongraceclub.com.au",
  });
}

test("Decide Action (ingest, cloud): an update row carries `domain`, not just `company_domain`", () => {
  const wf = loadWorkflow();
  const [decided] = runCode(armedDecideAction(wf), [matchedUpdateRow()]);
  assert.equal(decided.action, "update", "seed row must actually reach Decide Action as an update");
  assert.equal(decided.company_domain, "wyongraceclub.com.au");
  assert.equal(decided.domain, "wyongraceclub.com.au",
    "the field name HubSpot Update Write Gate reads (`domain`) must be populated too");
});

test("HubSpot Update Write Gate: a domain-only allowlist admits an update Decide Action produced", () => {
  const wf = loadWorkflow();
  const [decided] = runCode(armedDecideAction(wf), [matchedUpdateRow()]);

  const gateJs = armConstants(jsCodeOf(wf, "HubSpot Update Write Gate"), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true",
    TEST_RECORD_DOMAINS: "wyongraceclub.com.au",
  });
  const gated = runCode(gateJs, [decided]);
  assert.equal(gated.length, 1,
    "the gate must admit Decide Action's own update row when its company domain is on the allowlist");
  assert.equal(gated[0].hs_object_id, "35551");
});

test("HubSpot Update Write Gate: still denies when the domain is not on the allowlist (defense-in-depth, independent of Decide Action's own precheck)", () => {
  const wf = loadWorkflow();
  const [decided] = runCode(armedDecideAction(wf), [matchedUpdateRow()]);

  const gateJs = armConstants(jsCodeOf(wf, "HubSpot Update Write Gate"), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true",
    TEST_RECORD_DOMAINS: "some-other-domain.example",
  });
  const gated = runCode(gateJs, [decided]);
  assert.equal(gated.length, 0, "an unlisted domain must still be refused");
});
