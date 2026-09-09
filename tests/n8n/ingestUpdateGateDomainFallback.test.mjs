// tests/n8n/ingestUpdateGateDomainFallback.test.mjs
//
// F11 (uat-batch-review-row-reads-failed, execution 12181), historical subject: "HubSpot
// Update Write Gate" used to read a row's domain as `identity_keys.domain || json.domain`
// — a fallback ladder that grew from two separate live incidents (F11 here, BUG 27 on the
// create side). D-70-12 (Phase 70 Plan 05 Task 1) deleted that ladder outright: the gate
// now reads ONLY `write_request`, and the case this file protected — an update row's
// domain reaching the gate at all — is now an EMITTER-SIDE assertion (Decide Action must
// stamp `write_request.domain`), not a gate-side fallback.
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

// Phase 70 Plan 05 Task 2 sub-step 2c (D-70-06): F12's pre-write precheck inside
// "Decide Action" is GONE, and with it the arming surface that used to live there. The
// node now decides WHAT the row is and emits the canonical `write_request`; the gate is
// the ONE place that decides whether it may be written. Nothing to arm here any more —
// which is precisely the "one home per lane" property D-70-13 asked for.
function decideAction(wf) {
  return jsCodeOf(wf, "Decide Action");
}

test("Decide Action (ingest, cloud): an update row's write_request carries the company domain (D-70-12)", () => {
  const wf = loadWorkflow();
  const [decided] = runCode(decideAction(wf), [matchedUpdateRow()]);
  assert.equal(decided.action, "update", "seed row must actually reach Decide Action as an update");
  assert.equal(decided.company_domain, "wyongraceclub.com.au");
  // The case this file used to protect via the (now-deleted) gate-side fallback: the
  // emitter must be the one to populate the identity the gate will check.
  assert.ok(decided.write_request, "Decide Action must stamp write_request on every row");
  assert.equal(decided.write_request.domain, "wyongraceclub.com.au",
    "write_request.domain is what HubSpot Update Write Gate now reads exclusively");
  assert.equal(decided.write_request.hs_object_id, "35551");
  assert.equal(decided.write_request.action, "update");
});

test("HubSpot Update Write Gate: a domain-only allowlist admits an update Decide Action produced", () => {
  const wf = loadWorkflow();
  const [decided] = runCode(decideAction(wf), [matchedUpdateRow()]);

  const gateJs = armConstants(jsCodeOf(wf, "HubSpot Update Write Gate"), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true",
    TEST_RECORD_DOMAINS: "wyongraceclub.com.au",
  });
  const gated = runCode(gateJs, [decided]);
  assert.equal(gated.length, 1,
    "the gate must admit Decide Action's own update row when its company domain is on the allowlist");
  assert.equal(gated[0].hs_object_id, "35551");
});

test("HubSpot Update Write Gate: still denies when the domain is not on the allowlist (the ONE home for the predicate)", () => {
  const wf = loadWorkflow();
  const [decided] = runCode(decideAction(wf), [matchedUpdateRow()]);

  const gateJs = armConstants(jsCodeOf(wf, "HubSpot Update Write Gate"), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true",
    TEST_RECORD_DOMAINS: "some-other-domain.example",
  });
  // D-70-14 (Phase 70 Plan 05 Task 2): the gate's Code node stamps a verdict now — it
  // never drops. Length stays 1; check the verdict instead.
  const gated = runCode(gateJs, [decided]);
  assert.equal(gated.length, 1, "the gate still emits the row (D-70-14, no drop)");
  assert.equal(gated[0].write_allowed, false, "an unlisted domain must still be refused");
});

test("HubSpot Update Write Gate: a row with no write_request at all is refused, not rescued (D-70-12)", () => {
  const wf = loadWorkflow();
  const gateJs = armConstants(jsCodeOf(wf, "HubSpot Update Write Gate"), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true",
    TEST_RECORD_DOMAINS: "wyongraceclub.com.au",
  });
  // The legacy fields the deleted ladder used to fall back to, with no write_request.
  const legacyShapedRow = {
    hs_object_id: "35551", domain: "wyongraceclub.com.au",
    identity_keys: { domain: "wyongraceclub.com.au" },
  };
  const gated = runCode(gateJs, [legacyShapedRow]);
  assert.equal(gated.length, 1, "the gate still emits the row (D-70-14, no drop)");
  assert.equal(gated[0].write_allowed, false,
    "a row without write_request must be refused even though every legacy fallback field is present and allowlisted");
});
