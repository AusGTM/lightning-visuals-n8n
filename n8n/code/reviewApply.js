// reviewApply.js — pure-JS §22.2 review-loop apply function for n8n Code nodes.
//
// CONSUMER CONTRACT: consumes EXACTLY what ENRICH_DECIDE_CO_CLOUD (build_cloud_workflows.py)
// writes into lv_enrichment_review_candidate_json — stableStringify(needsReview), where
// needsReview is mergeCompanies()'s decisions[] filtered to decision === "needs_review".
// Each decision is shaped { field, current_value, chosen_value, source_provider, decision,
// confidence, reason, validation_status, evidence_url, verified_at } (mergeCompanies.js:213-224).
//
// reviewApply(candidateJson, refetchedProperties) -> { canonicalPatch, clearPatch, stale, invalid, reason }
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
//
// ENUM GUARD (Phase 31, BUG 28/29, REVIEW-05): after the stale compare-and-set, every
// candidate value bound for an enum-bound HubSpot property (n8n/code/hubspotEnums.js) is
// re-validated. A candidate holding a value HubSpot's enum will refuse (e.g. an older
// stored `industry` candidate carrying a raw provider label) is pushed onto `invalid`
// instead of `canonicalPatch`. `invalid` non-empty is ALL-OR-NOTHING, exactly like
// `stale`: empty canonicalPatch, empty clearPatch — a partial apply that cleared the queue
// while refusing a field is the silent de-queueing REVIEW-05 forbids. A candidate that
// normalizes cleanly (an exact case-insensitive label match, e.g. "Sports" -> "SPORTS")
// promotes with the NORMALIZED value so an older stored candidate still approves correctly.

const { DEFAULT_COMPANY_POLICY } = require("./mergeCompanies");
const { normalizeEnumValue } = require("./hubspotEnums");

function reviewApply(candidateJson, refetchedProperties) {
  refetchedProperties = refetchedProperties || {};

  let decisions;
  try {
    decisions = JSON.parse(candidateJson);
    if (!Array.isArray(decisions)) throw new Error("candidate JSON is not an array");
  } catch (e) {
    return { canonicalPatch: {}, clearPatch: {}, stale: false, invalid: [],
             reason: "malformed review candidate JSON" };
  }

  const allowedFields = Object.keys(DEFAULT_COMPANY_POLICY);
  const canonicalPatch = {};
  const staleFields = [];
  const invalid = [];

  for (const d of decisions) {
    if (!d || typeof d.field !== "string" || allowedFields.indexOf(d.field) === -1) continue;
    const liveValue = refetchedProperties[d.field];
    const normalizedLive = liveValue === undefined ? null : liveValue;
    const storedCurrent = d.current_value === undefined ? null : d.current_value;
    if (JSON.stringify(normalizedLive) !== JSON.stringify(storedCurrent)) {
      staleFields.push(d.field);
      continue;
    }
    const enumCheck = normalizeEnumValue(d.field, d.chosen_value);
    if (!enumCheck.ok) {
      invalid.push({ field: d.field, value: d.chosen_value, reason: enumCheck.reason });
      continue;
    }
    canonicalPatch[d.field] = enumCheck.value;
  }

  if (staleFields.length > 0) {
    return {
      canonicalPatch: {}, clearPatch: {}, stale: true, invalid: [],
      reason: `field(s) changed since candidate was created, re-review required: ${staleFields.join(",")}`,
    };
  }

  if (invalid.length > 0) {
    return {
      canonicalPatch: {}, clearPatch: {}, stale: false, invalid,
      reason: `field(s) hold a value HubSpot will refuse, re-review required: ${invalid.map((i) => i.field).join(",")}`,
    };
  }

  // D-07 (43-01, PIPE-01): string literals, never bare JS booleans — HubSpot EQ filters
  // compare strings (the 36-07 precedent for lv_enrichment_requested, and Phase 40 D-04's
  // lv_anti_icp_flag fix). Neither ENRICH_APPLY_REVIEW nor buildReviewDecision's approve
  // branch (the two consumers that spread this object into a PATCH body) carries any
  // coercion of its own, so an unstringified value here would ship straight through.
  const clearPatch = {
    lv_enrichment_needs_review: "false",
    lv_enrichment_review_approved: "false",
    lv_enrichment_review_reason: "",
    lv_enrichment_review_candidate_json: "",
    lv_enrichment_reviewed_at: new Date().toISOString(),
  };

  return { canonicalPatch, clearPatch, stale: false, invalid: [], reason: "applied" };
}

module.exports = { reviewApply };
