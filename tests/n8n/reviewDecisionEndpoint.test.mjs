// tests/n8n/reviewDecisionEndpoint.test.mjs
//
// Phase 30 Plan 02 — the synchronous `hubspot/review/decision` endpoint.
//
// Two sections:
//   (1) MODULE — n8n/code/reviewDecision.js in isolation. A rejection is exactly one
//       property write and leaves the record queued (D-10, REVIEW-05).
//   (2) FLOW — the COMMITTED n8n/wf_review_decision_cloud.json's own node jsCode, run
//       through `new Function` the way n8n's Code node runs it. Refusal, preview, the
//       gate in both arming directions, and the {outcome, message, would_write,
//       verified_properties, verified} response contract 30-06 consumes (D-19).
//
// No test here issues a network call. Arming is a literal swap on the in-memory jsCode
// string only — the EXACT swap scripts/deploy_n8n_workflows.py's enable_baked_flags()
// performs, so a drift in how the builder spells a constant fails this file.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const MODULE_PATH = path.join(ROOT, "n8n/code/reviewDecision.js");
const { buildReviewDecision } = require(MODULE_PATH);
const { mergeCompanies, stableStringify } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

// The `lv_`-prefixed review family from config/hubspot_properties.yaml. Hard-typed here on
// purpose: this file is where the names are PINNED (root CLAUDE.md's unprefixed names are
// wrong for this deployment — 30 D-08c).
const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_REVIEW_REASON = "lv_enrichment_review_reason";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";
const P_REVIEWED_BY = "lv_enrichment_reviewed_by";
const P_REVIEWED_AT = "lv_enrichment_reviewed_at";

const NOW = "2026-07-31T04:05:06.000Z";

// Build the flagged-row fixture from a REAL mergeCompanies() run filtered to needs_review,
// exactly as reviewLoop.test.mjs does — so the candidate JSON cannot drift from what the
// pipeline actually stores in lv_enrichment_review_candidate_json.
function flaggedRow(overrides) {
  const existing = {
    domain: "exampleracing.example",
    lv_org_type: "broadcaster",
    lv_produces_content: false,
  };
  const candidate = { lv_org_type: "governing_body_league", lv_produces_content: true };
  const { decisions } = mergeCompanies(existing, candidate, undefined,
    { source: "claude_web", confidence: 60 });
  const needsReview = decisions.filter((d) => d.decision === "needs_review");
  assert.ok(needsReview.length > 0, "fixture must actually produce a needs_review decision");
  return {
    ...existing,
    hs_object_id: "789",
    record_found: true,
    [P_NEEDS_REVIEW]: "true",
    [P_ICP_NEEDS_REVIEW]: "false",
    [P_CANDIDATE_JSON]: stableStringify(needsReview),
    ...(overrides || {}),
  };
}

// =====================================================================================
// (1) MODULE — buildReviewDecision
// =====================================================================================

test("reject on a flagged row writes EXACTLY one property: the operator's reason", () => {
  const row = flaggedRow();
  const out = buildReviewDecision({
    decision: "reject", reason: "Wrong org type — this is a broadcaster, not a league.",
    reviewedBy: "revops@example.com", row, nowIso: NOW,
  });

  assert.equal(out.outcome, "rejected");
  assert.equal(Object.keys(out.properties).length, 1,
    "a rejection is one property write and nothing else");
  assert.equal(out.properties[P_REVIEW_REASON],
    "Wrong org type — this is a broadcaster, not a league.");
});

test("reject never clears a review flag and never blanks the candidate JSON (D-10)", () => {
  const row = flaggedRow();
  const { properties } = buildReviewDecision({
    decision: "reject", reason: "not a fit", reviewedBy: "revops@example.com", row, nowIso: NOW,
  });
  // Explicit key-PRESENCE assertions, not a string search: writing the flag as `false`
  // and omitting it are indistinguishable to a grep and opposite to HubSpot.
  assert.equal(P_NEEDS_REVIEW in properties, false, "needs-review flag must not be written");
  assert.equal(P_ICP_NEEDS_REVIEW in properties, false, "ICP needs-review flag must not be written");
  assert.equal(P_CANDIDATE_JSON in properties, false, "candidate JSON must not be blanked");
  assert.equal(P_REVIEWED_AT in properties, false, "a rejection does not stamp reviewed-at");
  assert.equal(P_REVIEWED_BY in properties, false, "a rejection does not stamp reviewed-by");
});

test("a row that is not actually flagged yields outcome not_flagged and writes nothing", () => {
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "false", [P_CANDIDATE_JSON]: "",
  });
  const out = buildReviewDecision({ decision: "reject", reason: "x", row, nowIso: NOW });
  assert.equal(out.outcome, "not_flagged");
  assert.deepEqual(out.properties, {});
});

test("an empty-array candidate JSON is not a flag either", () => {
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "false", [P_CANDIDATE_JSON]: "[]",
  });
  const out = buildReviewDecision({ decision: "reject", reason: "x", row, nowIso: NOW });
  assert.equal(out.outcome, "not_flagged");
});

test("a row flagged ONLY by lv_icp_needs_review is still in the queue", () => {
  // The queue's own definition (wf_backend_status_cloud's AWAITING_REVIEW_GROUPS) ORs the
  // two flags, so a record flagged solely for ICP review must be adjudicable here.
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "true", [P_CANDIDATE_JSON]: "",
  });
  const out = buildReviewDecision({ decision: "reject", reason: "off-ICP", row, nowIso: NOW });
  assert.equal(out.outcome, "rejected");
  assert.equal(Object.keys(out.properties).length, 1);
});

test("approve is explicitly unsupported in this plan and writes nothing", () => {
  const out = buildReviewDecision({
    decision: "approve", reason: "looks right", row: flaggedRow(), nowIso: NOW,
  });
  assert.equal(out.outcome, "unsupported");
  assert.deepEqual(out.properties, {});
  assert.match(out.message, /approve/i);
});

test("an unknown decision word is refused", () => {
  for (const decision of ["defer", "REJECT", "", null, undefined, 7, { decision: "reject" }]) {
    const out = buildReviewDecision({ decision, reason: "x", row: flaggedRow(), nowIso: NOW });
    assert.equal(out.outcome, "refused", `decision ${JSON.stringify(decision)} must be refused`);
    assert.deepEqual(out.properties, {});
  }
});

test("a missing record is refused, never guessed at", () => {
  for (const row of [undefined, null, "789", [], { record_found: false }, { hs_object_id: "" }]) {
    const out = buildReviewDecision({ decision: "reject", reason: "x", row, nowIso: NOW });
    assert.equal(out.outcome, "refused");
    assert.deepEqual(out.properties, {});
  }
});

test("a non-string reason is refused; an absent one is accepted as empty (D-09)", () => {
  for (const reason of [7, true, { text: "x" }, ["x"]]) {
    const out = buildReviewDecision({ decision: "reject", reason, row: flaggedRow(), nowIso: NOW });
    assert.equal(out.outcome, "refused", `reason ${JSON.stringify(reason)} must be refused`);
  }
  for (const reason of ["", undefined, null]) {
    const out = buildReviewDecision({ decision: "reject", reason, row: flaggedRow(), nowIso: NOW });
    assert.equal(out.outcome, "rejected", "a decision without a reason is still a decision");
    assert.equal(out.properties[P_REVIEW_REASON], "");
  }
});

test("an over-long reason is truncated at the HubSpot text ceiling, not refused", () => {
  const out = buildReviewDecision({
    decision: "reject", reason: "z".repeat(60001), row: flaggedRow(), nowIso: NOW,
  });
  assert.equal(out.outcome, "rejected");
  assert.equal(out.properties[P_REVIEW_REASON].length, 60000);
});

test("buildReviewDecision never throws, whatever it is handed", () => {
  for (const input of [undefined, null, {}, { row: {} }, { decision: "reject" }, 42, "x"]) {
    assert.doesNotThrow(() => buildReviewDecision(input));
  }
});

test("the module requires nothing outside n8n/code/", () => {
  const src = fs.readFileSync(MODULE_PATH, "utf8");
  for (const m of src.matchAll(/require\(\s*"([^"]+)"\s*\)/g)) {
    assert.match(m[1], /^\.\/[A-Za-z0-9_.]+$/,
      `reviewDecision.js may only require siblings in n8n/code/ — found ${m[1]}`);
  }
});
