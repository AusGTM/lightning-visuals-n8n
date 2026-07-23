// reviewApply.js — pure-JS §22.2 review-loop apply function for n8n Code nodes.
//
// CONSUMER CONTRACT: consumes EXACTLY what ENRICH_DECIDE_CO_CLOUD (build_cloud_workflows.py)
// writes into lv_enrichment_review_candidate_json — stableStringify(needsReview), where
// needsReview is mergeCompanies()'s decisions[] filtered to decision === "needs_review".
// Each decision is shaped { field, current_value, chosen_value, source_provider, decision,
// confidence, reason, validation_status, evidence_url, verified_at } (mergeCompanies.js:213-224).
//
// reviewApply(candidateJson, refetchedProperties) -> { canonicalPatch, clearPatch, stale, reason }
//
// STRUCTURAL Approach-C guard: canonicalPatch only ever accepts a field that is a key of
// mergeCompanies' own DEFAULT_COMPANY_POLICY — the same allowlist mergeCompanies itself
// promotes from. The two HubSpot-derived ICP score/tier outputs (Approach C) are
// deliberately ABSENT from that policy object (see mergeCompanies.js's own comment), so a
// candidate JSON that illegitimately names one is silently dropped without this file ever
// naming either field literally.
//
// FAIL-CLOSED: malformed / truncated JSON never throws -> empty patches + a reason.
// NON-CLOBBER (compare-and-set): a held decision's `current_value` is compared against the
// freshly-refetched live value of that field. If ANY field disagrees, a newer manual edit
// landed after the candidate was created — apply NOTHING (both patches stay empty), report
// stale=true, and leave the record queued (do not clear its review flags). All-or-nothing
// avoids a partial-apply/re-check loop: applying only the non-conflicting fields this run
// would change their live values without clearing lv_enrichment_review_candidate_json, so
// the NEXT run's compare-and-set would see its own just-applied write as a "conflict".

const { DEFAULT_COMPANY_POLICY } = require("./mergeCompanies");

function reviewApply(candidateJson, refetchedProperties) {
  refetchedProperties = refetchedProperties || {};

  let decisions;
  try {
    decisions = JSON.parse(candidateJson);
    if (!Array.isArray(decisions)) throw new Error("candidate JSON is not an array");
  } catch (e) {
    return { canonicalPatch: {}, clearPatch: {}, stale: false,
             reason: "malformed review candidate JSON" };
  }

  const allowedFields = Object.keys(DEFAULT_COMPANY_POLICY);
  const canonicalPatch = {};
  const staleFields = [];

  for (const d of decisions) {
    if (!d || typeof d.field !== "string" || allowedFields.indexOf(d.field) === -1) continue;
    const liveValue = refetchedProperties[d.field];
    const normalizedLive = liveValue === undefined ? null : liveValue;
    const storedCurrent = d.current_value === undefined ? null : d.current_value;
    if (JSON.stringify(normalizedLive) !== JSON.stringify(storedCurrent)) {
      staleFields.push(d.field);
      continue;
    }
    canonicalPatch[d.field] = d.chosen_value;
  }

  if (staleFields.length > 0) {
    return {
      canonicalPatch: {}, clearPatch: {}, stale: true,
      reason: `field(s) changed since candidate was created, re-review required: ${staleFields.join(",")}`,
    };
  }

  const clearPatch = {
    lv_enrichment_needs_review: false,
    lv_enrichment_review_approved: false,
    lv_enrichment_review_reason: "",
    lv_enrichment_review_candidate_json: "",
    lv_enrichment_reviewed_at: new Date().toISOString(),
  };

  return { canonicalPatch, clearPatch, stale: false, reason: "applied" };
}

module.exports = { reviewApply };
