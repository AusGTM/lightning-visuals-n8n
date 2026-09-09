// tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs
//
// Gap G1, filled 2026-09-03 by the retroactive nyquist pass for Phase 61
// (61-VALIDATION.md).
//
// Phase 61 Plan 06 Task 1 closed CLAUDE.md §13.0.1's contact-association gap BY REFUSAL:
// `ENRICH_DECIDE_CLOUD` downgrades EVERY `create` on wf_enrichment_cloud's contacts
// branch to `action: "review"` — INCLUDING AN ARMED ONE — rather than duplicating the
// ingest lane's resolve+associate subgraph. The load-bearing property is that the
// association rule keeps exactly ONE operational implementation
// (wf_contact_ingest_cloud); a second copy here would be a driftable duplicate of the
// same rule, which is the outcome §13.0.1's closing sentence warns about.
//
// WHY THIS TEST EXISTS: that refusal had no regression guard. `61-VERIFICATION.md`
// truth 7 cites tests/n8n/pairPipelineAssociationFlow.test.mjs, which loads
// n8n/wf_contact_ingest_cloud.json — the OTHER lane. So does contactCreateGateFlow.
// A tree-wide grep for the refusal's own reason string ("not associated on this lane")
// and its flag (contactCreateHeldForAssociation) returned ZERO hits in tests/. Deleting
// the entire downgrade block from scripts/build_cloud_workflows.py broke no test.
//
// THE TAUTOLOGY TRAP THIS AVOIDS: a disarmed variant passes vacuously. Disarmed, a
// create becomes "write_blocked" at _writeSafetyAllows and never reaches the downgrade
// branch at all — so a test that only asserts "not create" while disarmed proves
// nothing. The armed case is the one under test, and the disarmed case is asserted
// separately as an explicit non-vacuity control.
//
// This executes the repo's OWN committed node jsCode via `new Function` — the same
// mechanism n8n's Code node uses at runtime — over the actual committed
// n8n/wf_enrichment_cloud.json. No external or untrusted input is interpolated into the
// function body. The armed variant is produced by string-replacing each disabled
// declaration with its enabled form, the EXACT literal swap
// scripts/deploy_n8n_workflows.py::enable_baked_flags() performs, so this test fails if
// a declaration's spelling ever drifts out of the overlay's reach.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function loadWorkflow() {
  return JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
}

function jsCodeOf(wf, name) {
  const node = wf.nodes.find((n) => n.name === name);
  assert.ok(node, `node present: ${name}`);
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) against seed items, the same shape
 * n8n's Code node executes it under. `Decide Action` reads one other node by name
 * (`Build Identity`), so `$` is stubbed to return the seed row for it. */
function runCode(jsCode, seedItems) {
  const items = seedItems.map((j) => ({ json: j }));
  const $input = { all: () => items };
  const $ = () => ({
    item: items[0],
    first: () => items[0],
    all: () => items,
  });
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  const out = fn($input, $) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// The three declarations the deploy-time overlay flips for an armed contact create on
// this lane. Asserted present verbatim before the swap, so a spelling drift fails here
// rather than silently producing a still-disarmed "armed" variant.
const OVERLAY = [
  ['const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
   'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'],
  ['const ALLOW_HUBSPOT_CREATE = "false";',
   'const ALLOW_HUBSPOT_CREATE = "true";'],
  ['const TEST_RECORD_DOMAINS = "";',
   'const TEST_RECORD_DOMAINS = "example.com";'],
];

function arm(jsCode) {
  let armed = jsCode;
  for (const [disabled, enabled] of OVERLAY) {
    assert.ok(
      armed.includes(disabled),
      `committed jsCode must carry ${disabled} verbatim for this swap to be ` +
      "equivalent to enable_baked_flags()",
    );
    armed = armed.replace(disabled, enabled);
  }
  return armed;
}

/** A net-new contact on the ENRICHMENT lane: no existing record, a high (auto) match,
 * write mode, and an allowlisted domain — everything an armed create needs. */
function createRow() {
  return {
    action: "create",
    mode: "write",
    identity_keys: { email: "new.contact@example.com", domain: "example.com" },
    match: { tier: "high", auto: true },
    merge: { canonicalPatch: {}, decisions: [] },
    existingRecord: null,
  };
}

test("Decide Action (enrichment lane): a contact create is downgraded to review, never landed unassociated", () => {
  // Phase 70 Plan 05 Task 2 (D-70-13): the write-permission constants left this node for
  // the lane's own spliced gate, so there is nothing to arm HERE any more — and nothing
  // to arm AROUND either: the hold is unconditional (see the companion test below).
  const wf = loadWorkflow();
  const [result] = runCode(jsCodeOf(wf, "Decide Action"), [createRow()]);

  assert.equal(
    result.action, "review",
    "an armed create on the enrichment lane must be HELD for review — this lane has no " +
    "company-resolution or association mechanism, and landing an unassociated contact " +
    "violates the 2026-08-25 operator ruling (CLAUDE.md §13.0.1)",
  );
  assert.equal(result.needs_review, true, "the held row must be flagged for review");
  assert.equal(result.properties.lv_enrichment_needs_review, "true");
  assert.equal(result.properties.lv_enrichment_status, "needs_review");
  assert.match(
    result.properties.lv_enrichment_review_reason,
    /ingest lane/,
    "the review reason must name the contact-upload ingest lane as the route to take " +
    "instead — a hold with no route is an operator dead end",
  );
});

test("Decide Action (enrichment lane): the hold is UNCONDITIONAL — arming the lane's own gate cannot land the create", () => {
  // Non-vacuity, restated for Phase 70 Plan 05 Task 2. Before the gate existed, a
  // disarmed create was stopped earlier by the inline _writeSafetyAllows, so the hold
  // was only observable on an armed run. Now the hold happens in this node regardless of
  // any write flag, and the row it emits ("review") matches neither "IF Create"
  // (=="create") nor "IF Enrich" (=="enrich") — so "HubSpot Create Write Gate" never
  // even runs for it. Arming the gate is therefore a genuine no-op for this row, which
  // is a STRONGER guarantee than the old armed-only one, not a weaker one.
  const wf = loadWorkflow();
  const [result] = runCode(jsCodeOf(wf, "Decide Action"), [createRow()]);
  assert.equal(result.action, "review", "the hold applies with nothing armed");

  const gateJs = jsCodeOf(wf, "HubSpot Create Write Gate");
  for (const [disabled] of OVERLAY) {
    assert.ok(gateJs.includes(disabled),
      `the arming surface moved to the gate, which must carry ${disabled} verbatim`);
  }
  // Even fully armed, the gate would refuse to see this row at all: it is reachable only
  // via "IF Create"'s true branch, and this row's action is "review".
  const [gated] = runCode(arm(gateJs), [result]);
  assert.notEqual(gated.action, "create");
});

test("Decide Action (enrichment lane): the association rule keeps exactly ONE implementation", () => {
  // §13.0.1's load-bearing property. The enrichment lane refuses; it must never grow a
  // second copy of the ingest lane's resolve+associate subgraph, because two copies of
  // one rule drift. Asserted on node names — a structural fact, not prose.
  const wf = loadWorkflow();
  const names = new Set(wf.nodes.map((n) => n.name));
  for (const ingestOnly of [
    "Build Company Link",
    "Adapt Company Link",
    "Build Association Request",
    "HubSpot Associate Company",
    "HubSpot Associate Company Write Gate",
  ]) {
    assert.ok(
      !names.has(ingestOnly),
      `"${ingestOnly}" belongs to wf_contact_ingest_cloud, the ONE lane that implements ` +
      "contact→company association. A copy here would be a second, driftable " +
      "implementation of the same rule — the outcome CLAUDE.md §13.0.1 refuses. If this " +
      "lane genuinely needs association, move the rule rather than duplicating it.",
    );
  }
});
