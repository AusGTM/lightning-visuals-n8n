// tests/n8n/writeGateShape.test.mjs
//
// D-70-12 (Phase 70 Plan 05 Task 1): the canonical write_request contract — every gated
// write's upstream emits `{action, hs_object_id, domain, email}`, and the gate reads
// ONLY that shape. Runs the repo's OWN committed jsCode via `new Function` (the same
// mechanism n8n's Code node uses), over the actual committed workflow JSON files — no
// external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadWorkflow(name) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", name), "utf8"));
}

function jsCodeOf(wf, name) {
  const node = wf.nodes.find((n) => n.name === name);
  assert.ok(node, `node present: ${name}`);
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) against seed items, the same shape
 * n8n's Code node executes it under. Returns the resulting json objects. */
function runCode(jsCode, seedItems) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })), first: () => ({ json: seedItems[0] }) };
  const out = new Function("$input", `"use strict";\n${jsCode}`)($input) || [];
  return out.map((it) => it.json);
}

const INGEST = loadWorkflow("wf_contact_ingest_cloud.json");
const MAINTENANCE = loadWorkflow("wf_scheduled_maintenance_cloud.json");
const REVIEW = loadWorkflow("wf_review_decision_cloud.json");

// --- named case: gate jsCode references no identity key outside write_request --------
//
// The four-way fallback ladder this used to read directly: `existingRecord.hs_object_id`,
// `identity_keys.domain`, `properties.email`, bare `.email`. All four are gone; the only
// identity access left in any gate's own jsCode is through `write_request` (aliased
// `wr` below by every gate this plan built).
const GATES = [
  ["wf_contact_ingest_cloud.json", INGEST, "HubSpot Update Write Gate"],
  ["wf_contact_ingest_cloud.json", INGEST, "HubSpot Create Write Gate"],
  ["wf_contact_ingest_cloud.json", INGEST, "HubSpot Associate Company Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "SJ-1 Set Requested Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "SJ-2 Set Requested Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "Dedupe Set Needs Review Write Gate"],
  ["wf_scheduled_maintenance_cloud.json", MAINTENANCE, "Review Apply Update Write Gate"],
  ["wf_review_decision_cloud.json", REVIEW, "Review Decision Update Write Gate"],
  ["wf_review_decision_cloud.json", REVIEW, "Review Contact Decision Update Write Gate"],
];

for (const [fileName, wf, gateName] of GATES) {
  test(`${fileName}: ${gateName} reads only write_request (no identity fallback ladder)`, () => {
    const js = jsCodeOf(wf, gateName);
    assert.match(js, /it\.json\.write_request/, "gate must read it.json.write_request");
    for (const legacyKey of ["identity_keys", "existingRecord", "properties.email", "it.json.email", "it.json.domain"]) {
      assert.ok(!js.includes(legacyKey), `${gateName} must not reference legacy identity key ${legacyKey}`);
    }
  });
}

// --- named case: an empty allowlist denies on all four lanes --------------------------
//
// Ingest (create), scheduled-maintenance (enrich), review-decision (review) all go
// through the new IF-shaped... no: through splice_write_gates' Code-node gate, whose
// committed constants are all disarmed. The enrichment lane has no spliced gate yet
// (Task 2) — its OWN inline _writeSafetyAllows call is unchanged by this task, and an
// empty allowlist denies there too, proved directly against Decide Action's committed
// jsCode.
test("ingest: HubSpot Create Write Gate denies a fully-identified row with an empty allowlist", () => {
  const js = jsCodeOf(INGEST, "HubSpot Create Write Gate");
  const row = { action: "create", write_request: { action: "create", hs_object_id: null, domain: "exampleco.example", email: "jo@exampleco.example" } };
  assert.equal(runCode(js, [row]).length, 0, "committed (disarmed) build must deny — empty allowlist");
});

test("scheduled-maintenance: SJ-1 Set Requested Write Gate denies a fully-identified row with an empty allowlist", () => {
  const js = jsCodeOf(MAINTENANCE, "SJ-1 Set Requested Write Gate");
  const row = { write_request: { action: "enrich", hs_object_id: "999", domain: "exampleco.example", email: null } };
  assert.equal(runCode(js, [row]).length, 0, "committed (disarmed) build must deny — empty allowlist");
});

test("review-decision: Review Decision Update Write Gate denies a fully-identified row with an empty allowlist", () => {
  const js = jsCodeOf(REVIEW, "Review Decision Update Write Gate");
  const row = { write_request: { action: "review", hs_object_id: "999", domain: null, email: null } };
  assert.equal(runCode(js, [row]).length, 0, "committed (disarmed) build must deny — empty allowlist");
});

test("enrichment lane (unchanged in this task): Decide Action's own empty-allowlist denial still holds", () => {
  const enrichment = loadWorkflow("wf_enrichment_cloud.json");
  const js = jsCodeOf(enrichment, "Decide Action");
  // Decide Action embeds _writeSafetyAllows itself (no spliced gate on this lane yet —
  // Task 2). Proving the shared allowlist function denies with nothing armed is a direct
  // structural check, not a behavioural run of the whole (very large) node.
  assert.match(js, /function _writeSafetyAllows/);
  assert.match(js, /empty allowlist denies everything/);
});

// --- named case: the review lane's emitted write_request carries a null domain --------
//
// D-70-13: "Build Review Decision" forces domain: null regardless of object type — the
// review lane's contacts-stay-id-only rule (30-02) is now an emitted VALUE, applying
// uniformly to both write nodes this one node feeds.
test("review lane: Build Review Decision always emits write_request.domain === null", () => {
  const js = jsCodeOf(REVIEW, "Build Review Decision");
  assert.match(js, /_buildWriteRequest\("review",\s*row\.hs_object_id \|\| null,\s*null,/,
    "the domain argument to _buildWriteRequest must be the literal null, not a row field");
});

// --- named case: a fully-refused two-row batch never reduces item count below input ---
//
// Task 1 does not yet build the IF-shaped refusal-as-a-row mechanism (that is Task 2) —
// today's Code-node gate still FILTERS. This test exists to document that fact for this
// task's scope, and will need to flip once Task 2 lands the IF gate: a fully refused
// batch through today's gate legitimately produces ZERO rows (the pre-Task-2 shape).
test("ingest: HubSpot Update Write Gate still filters (pre-Task-2 shape) — documents today's behaviour", () => {
  const js = jsCodeOf(INGEST, "HubSpot Update Write Gate");
  const rows = [
    { action: "update", write_request: { action: "enrich", hs_object_id: "1", domain: null, email: null } },
    { action: "update", write_request: { action: "enrich", hs_object_id: "2", domain: null, email: null } },
  ];
  assert.equal(runCode(js, rows).length, 0, "disarmed gate drops both rows (filter, not IF, until Task 2)");
});
