// reviewDecision.js — pure-JS decision-to-property-patch for the SYNCHRONOUS
// `hubspot/review/decision` endpoint (Phase 30 Plan 02, D-08e).
//
// Sibling of reviewApply.js, not a replacement for it. reviewApply is the 15-minute
// backstop loop's compare-and-set APPLY engine (approve -> promote the held candidate ->
// clear the flags); this module serves the operator-driven endpoint. 30-03 routes the
// approve branch INTO reviewApply rather than re-implementing it (D-08d/D-15).
//
// CONSUMER CONTRACT: `Build Review Decision` (scripts/build_cloud_workflows.py) calls
//
//   buildReviewDecision({ decision, reason, reviewedBy, row, nowIso })
//     -> { properties, outcome, message }
//
// where `row` is the freshly-refetched HubSpot record already flattened by
// `Review Extract Record` ({ ...record.properties, hs_object_id, record_found }), and
// `properties` is put straight onto the row for the shared credential-bound PATCH node.
// `outcome` is one of: rejected | not_flagged | unsupported | refused.
//
// `reviewedBy` and `nowIso` are accepted but deliberately UNUSED on every branch this
// plan owns — they belong to 30-03's approve path, which stamps lv_enrichment_reviewed_by
// / lv_enrichment_reviewed_at as the human-provenance record. A rejection stamps neither,
// on purpose (below).
//
// D-10 / REVIEW-05 — THE LOAD-BEARING RULE: a rejection RECORDS THE REASON AND NOTHING
// ELSE. It never clears lv_enrichment_needs_review or lv_icp_needs_review, never blanks
// lv_enrichment_review_candidate_json, and never stamps a reviewed-at. The record stays in
// the queue WITH a recorded decision. "Clear the flag for consistency" is precisely the
// silent de-queueing REVIEW-05 forbids, so the rejection branch is kept literally minimal:
// build the one-key patch and return.
//
// FAIL-CLOSED: never throws, never does I/O, requires nothing outside n8n/code/. Anything
// unrecognised is `refused` with EMPTY properties — the endpoint's only writing outcome is
// `rejected`.

// The `lv_`-prefixed review family (config/hubspot_properties.yaml). The generic
// unprefixed names in the root CLAUDE.md do not exist in this deployment (30 D-08c).
const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_REVIEW_REASON = "lv_enrichment_review_reason";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";
// Named for the same reason the two flags above are: so the D-10 guarantee reads as an
// explicit non-write of a known property rather than an accidental omission. 30-03's
// approve branch is what writes these two.
const P_REVIEWED_BY = "lv_enrichment_reviewed_by";  // eslint-disable-line no-unused-vars
const P_REVIEWED_AT = "lv_enrichment_reviewed_at";  // eslint-disable-line no-unused-vars

// HubSpot's own textarea ceiling — the same [:60000] cap merge_policy.py and the
// enrichment wrapper apply to every JSON blob they stage.
const MAX_TEXT = 60000;

// HubSpot returns booleancheckbox values as the STRINGS "true"/"false", so a bare
// truthiness test would read "false" as flagged.
function _truthy(v) {
  if (v === true) return true;
  if (typeof v === "string") return v.trim().toLowerCase() === "true";
  return false;
}

function buildReviewDecision(input) {
  const inp = (input && typeof input === "object") ? input : {};
  const refused = (message) => ({ properties: {}, outcome: "refused", message });

  const row = inp.row;
  if (!row || typeof row !== "object" || Array.isArray(row)) {
    return refused("no record to decide on");
  }
  if (row.record_found === false || row.hs_object_id === undefined
      || row.hs_object_id === null || row.hs_object_id === "") {
    return refused("record not found");
  }

  // D-09: a decision without a reason is still a decision, so absent reads as empty. A
  // reason of the WRONG TYPE is a malformed request, not an empty one.
  let reason = inp.reason;
  if (reason === undefined || reason === null) reason = "";
  if (typeof reason !== "string") return refused("reason must be text");
  if (reason.length > MAX_TEXT) reason = reason.slice(0, MAX_TEXT);

  if (inp.decision === "approve") {
    return {
      properties: {}, outcome: "unsupported",
      message: "approve is not served by this endpoint yet — use the review-approved "
             + "backstop loop, or wait for the approve path (Phase 30 Plan 03)",
    };
  }
  if (inp.decision !== "reject") {
    return refused("unknown decision " + JSON.stringify(inp.decision)
                   + ' — expected "approve" or "reject"');
  }

  // Flagged the way the queue itself defines flagged: either review flag set, or a held
  // candidate. "[]" is reviewApply's own empty default, so it is not a candidate.
  const rawCandidate = row[P_CANDIDATE_JSON];
  const candidate = (rawCandidate === undefined || rawCandidate === null)
    ? "" : String(rawCandidate).trim();
  const flagged = _truthy(row[P_NEEDS_REVIEW]) || _truthy(row[P_ICP_NEEDS_REVIEW])
                  || (candidate !== "" && candidate !== "[]");
  if (!flagged) {
    return {
      properties: {}, outcome: "not_flagged",
      message: "record is not in the review queue — nothing to decide",
    };
  }

  return {
    properties: { [P_REVIEW_REASON]: reason },
    outcome: "rejected",
    message: "rejection reason recorded; the record stays in the review queue",
  };
}

module.exports = { buildReviewDecision };
