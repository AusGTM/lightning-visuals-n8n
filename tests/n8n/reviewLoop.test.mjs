// tests/n8n/reviewLoop.test.mjs
//
// Phase 16-02 Task 4 — closes the §22.2 review loop. reviewApply() consumes EXACTLY the
// candidate JSON shape 16-01 Task 5's ENRICH_DECIDE_CO_CLOUD producer writes into
// lv_enrichment_review_candidate_json: stableStringify(needsReview), where needsReview is
// mergeCompanies()'s decisions[] filtered to decision === "needs_review" (mergeCompanies.js
// :213-224). Four cases: producer-consumer contract, Approach-C negative, non-clobber
// compare-and-set, and fail-closed malformed JSON — plus a workflow-wiring check.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { reviewApply } = require(path.join(ROOT, "n8n/code/reviewApply.js"));
const { mergeCompanies, stableStringify } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

// Build a candidate JSON in the EXACT shape 16-01's producer emits: run the real
// mergeCompanies() and take its own needs_review decisions, stably-stringified — the same
// call the producer wrapper makes (ENRICH_DECIDE_CO_CLOUD).
function producerCandidateJson(existingProps, candidateRow, opts) {
  const { decisions } = mergeCompanies(existingProps, candidateRow, undefined, opts);
  const needsReview = decisions.filter((d) => d.decision === "needs_review");
  assert.ok(needsReview.length > 0, "fixture must actually produce a needs_review decision");
  return { candidateJson: stableStringify(needsReview), decisions: needsReview };
}

// --- (1) PRODUCER-CONSUMER contract ---------------------------------------------------

test("reviewApply: consumes the exact producer shape for held needs_review candidates and applies them", () => {
  // lv_org_type below its 80 threshold -> needs_review; lv_produces_content with no
  // evidence url -> needs_review (mergeCompanies' own evidence gate). Both fields are
  // legitimate DEFAULT_COMPANY_POLICY keys, so both are eligible for reviewApply.
  const existing = { lv_org_type: "broadcaster", lv_produces_content: false };
  const candidate = { lv_org_type: "governing_body_league", lv_produces_content: true };
  const { candidateJson } = producerCandidateJson(existing, candidate, { source: "claude_web", confidence: 60 });

  const refetched = { ...existing }; // nothing changed since the candidate was created
  const result = reviewApply(candidateJson, refetched);

  assert.equal(result.stale, false);
  assert.deepEqual(result.canonicalPatch, {
    lv_org_type: "governing_body_league",
    lv_produces_content: true,
  });
  assert.deepEqual(result.clearPatch, {
    lv_enrichment_needs_review: false,
    lv_enrichment_review_approved: false,
    lv_enrichment_review_reason: "",
    lv_enrichment_review_candidate_json: "",
    lv_enrichment_reviewed_at: result.clearPatch.lv_enrichment_reviewed_at,
  });
  assert.ok(result.clearPatch.lv_enrichment_reviewed_at, "reviewed_at must be stamped");
});

// --- (2) NEGATIVE Approach-C -----------------------------------------------------------

test("reviewApply: a candidate JSON illegitimately naming a derived ICP output field never reaches canonicalPatch", () => {
  const forged = JSON.stringify([
    { field: "lv_icp_tier", current_value: null, chosen_value: "A", decision: "needs_review" },
    { field: "lv_icp_fit_score", current_value: null, chosen_value: 90, decision: "needs_review" },
    { field: "lv_org_type", current_value: "broadcaster", chosen_value: "governing_body_league", decision: "needs_review" },
  ]);
  const result = reviewApply(forged, { lv_org_type: "broadcaster" });
  assert.ok(!("lv_icp_tier" in result.canonicalPatch));
  assert.ok(!("lv_icp_fit_score" in result.canonicalPatch));
  assert.equal(result.canonicalPatch.lv_org_type, "governing_body_league",
    "a legitimate field in the same candidate JSON still applies");
});

// --- (3) NON-CLOBBER (compare-and-set) --------------------------------------------------

test("reviewApply: a held decision whose stored current_value differs from the refetched live value is dropped, stale=true, flags NOT cleared", () => {
  const existing = { lv_org_type: "broadcaster" };
  const candidate = { lv_org_type: "governing_body_league" };
  const { candidateJson } = producerCandidateJson(existing, candidate, { source: "claude_web", confidence: 10 });

  // A newer manual edit landed after the candidate was created — live value has moved on.
  const refetched = { lv_org_type: "individual_club_team" };
  const result = reviewApply(candidateJson, refetched);

  assert.equal(result.stale, true);
  assert.deepEqual(result.canonicalPatch, {}, "no clobber — nothing applied");
  assert.deepEqual(result.clearPatch, {}, "flags stay set — record remains queued for re-review");
  assert.match(result.reason, /lv_org_type/);
});

// --- (4) FAIL-CLOSED ---------------------------------------------------------------------

test("reviewApply: malformed/truncated candidate JSON returns empty patches + a reason, never throws", () => {
  const result = reviewApply('[{"field":"lv_org_type","current_value":truncat', { lv_org_type: "broadcaster" });
  assert.deepEqual(result.canonicalPatch, {});
  assert.deepEqual(result.clearPatch, {});
  assert.equal(result.stale, false);
  assert.equal(result.reason, "malformed review candidate JSON");
});

test("reviewApply: a candidate JSON that is valid JSON but not an array also fails closed", () => {
  const result = reviewApply('{"not":"an array"}', {});
  assert.deepEqual(result.canonicalPatch, {});
  assert.equal(result.reason, "malformed review candidate JSON");
});

test("reviewApply: absent/empty candidate JSON is a no-op, not a crash", () => {
  const result = reviewApply("[]", {});
  assert.deepEqual(result.canonicalPatch, {});
  assert.equal(result.stale, false);
});

// --- Workflow wiring ---------------------------------------------------------------------

test("the built workflow contains an Apply Review node reachable from a review-approved search, which requests hs_object_id + candidate fields' current values", () => {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n/wf_scheduled_maintenance_cloud.json"), "utf8"));
  const applyReview = wf.nodes.find((n) => n.name === "Apply Review");
  assert.ok(applyReview, "Apply Review node must exist");
  assert.equal(applyReview.type, "n8n-nodes-base.code");
  assert.match(applyReview.parameters.jsCode, /reviewApply\(/);

  const search = wf.nodes.find((n) => n.name === "Review Search (approved=true)");
  assert.ok(search, "review-approved search node must exist");
  // BUG 10 / Phase 16.6: "Review Search (approved=true)" moved off the native
  // n8n-nodes-base.hubspot node (no `operation: "search"` exists for resource:company —
  // n8n's node schema only offers create/delete/get/getAll/getRecentlyCreatedUpdated/
  // searchByDomain/update; the native node silently returned json:null live) onto a
  // credential-bound httpRequest node whose filter + properties live inside a single
  // `jsonBody` expression string, not filterGroupsUi/additionalFields.
  assert.equal(search.type, "n8n-nodes-base.httpRequest");
  assert.equal(search.parameters.authentication, "predefinedCredentialType");
  assert.equal(search.parameters.nodeCredentialType, "hubspotAppToken");
  const body = search.parameters.jsonBody;
  assert.match(body, /propertyName:\s*"lv_enrichment_review_approved"/);
  assert.match(body, /operator:\s*"EQ"/);
  assert.match(body, /value:\s*"true"/);
  // `properties` is a genuine JSON array literal, not a CSV string (2026-07-28 / Phase
  // 16.6): n8n/HubSpot's search API requires an array and 400s on a CSV string.
  const propsMatch = body.match(/properties:\s*(\[[^\]]*\])/);
  assert.ok(propsMatch, "jsonBody must carry a `properties: [...]` array");
  const props = JSON.parse(propsMatch[1]);
  assert.ok(props.includes("hs_object_id"));
  assert.ok(props.includes("lv_org_type"));
  assert.ok(props.includes("lv_produces_content"));
  assert.ok(props.includes("lv_enrichment_review_candidate_json"));

  // Reachability: trigger -> search -> extract -> apply review.
  assert.ok(wf.connections["Review Trigger (15 min)"]);
  assert.ok(wf.connections[search.name]);
  assert.ok(wf.connections["Review Extract Rows"]);
});
