// n8n/code/judge.js — Phase 14 judge wiring: JG-4 evidence sufficiency, JG-1/RO-1/RO-2
// escalation triggers, JG-2 judge payload, JG-3 never-throws verdict handling.
// Production runtime logic (AR-4: nodes can't require() project files at runtime, so
// this file is hand-written) — thresholds/vocabulary come from the GENERATED
// escalation.generated.js (Phase 14 D3, same split as taxonomy.js/taxonomy.generated.js).
const { KNOWN_VIDEO_HOSTS, ESCALATION_CONFIDENCE_BAND } = require("./escalation.generated");

// isCitationSufficient — JG-4/TS-1. Sufficiency-of-PRESENCE only: does this citation
// actually substantiate a `lv_produces_content: true` claim, or is it a bare homepage /
// third-party directory / tourism listing that happens to mention the company? Applies
// ONLY to `true` claims (see applyEvidenceSufficiency below) — an evidenced `false` claim
// (e.g. QRIC) is a DIFFERENT judgement (sufficiency-of-ABSENCE) and never reaches this
// function; it routes to the judge unconditionally instead (Pitfall 3).
//
// Rule (validated by hand against all 20 real Phase-13 smoke rows, 19/20 exact — the
// 20th, RWWA racingwa.com.au vs HubSpot domain rwwa.com.au, is an accepted alias-domain
// false negative that fails safe to needs_review, never to a wrong `false` or a wrong
// veto; RESEARCH A3, no registrable-domain-family fuzzing in v1):
//   (citation host, `www.` stripped, equals the company's domain, `www.` stripped — OR
//   is a known video host) AND (citation path is neither `/` nor empty). Query strings
//   and fragments are ignored (row 1 carries `?cbrd=1`).
function isCitationSufficient(url, companyDomain) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch (e) {
    return false; // no parse throw escapes this function
  }
  const stripWww = (h) => String(h || "").toLowerCase().replace(/^www\./, "");
  const host = stripWww(parsed.hostname);
  const domain = stripWww(companyDomain);
  const hostMatches = host === domain || KNOWN_VIDEO_HOSTS.includes(host);
  const nonRootPath = parsed.pathname !== "" && parsed.pathname !== "/";
  return hostMatches && nonRootPath;
}

// applyEvidenceSufficiency — D6: runs on EVERY researched company regardless of
// ALLOW_SONNET_ESCALATION (deterministic, free). Returns a NEW candidate object (no
// in-place mutation of the caller's). TS-1: never writes `false` — insufficient evidence
// demotes a `true` claim to `null` (needs_review), the same tri-state direction TS-2
// already uses for unevidenced `false`.
function applyEvidenceSufficiency(researchCandidate, companyDomain) {
  if (!researchCandidate || !researchCandidate.data) return researchCandidate;
  if (researchCandidate.data.lv_produces_content !== true) return researchCandidate; // no-op

  const citationUrl = researchCandidate.evidence_by_field &&
    researchCandidate.evidence_by_field.lv_produces_content;
  const sufficient = citationUrl && isCitationSufficient(citationUrl, companyDomain);
  if (sufficient) return researchCandidate; // untouched, evidence key intact

  const data = { ...researchCandidate.data, lv_produces_content: null };
  const evidence_by_field = { ...(researchCandidate.evidence_by_field || {}) };
  delete evidence_by_field.lv_produces_content;
  return {
    ...researchCandidate,
    data,
    evidence_by_field,
    judge_flags: { ...(researchCandidate.judge_flags || {}), insufficient_content_evidence: true },
  };
}

// normalizeVendorFlag — the model may answer "true"/"yes"/1 for a vendor-flag field.
// lv_is_hardware_vendor / lv_is_gambling_operator are HubSpot booleans AND hard-veto
// inputs, so anything unrecognised becomes null, NEVER false (mirrors icp_scoring.py's
// boolish, unmapped -> None, not a silent False).
function normalizeVendorFlag(v) {
  if (v === true || v === false) return v;
  if (typeof v === "number") {
    if (v === 1) return true;
    if (v === 0) return false;
    return null;
  }
  if (typeof v === "string") {
    const s = v.trim().toLowerCase();
    if (["true", "yes", "1"].includes(s)) return true;
    if (["false", "no", "0"].includes(s)) return false;
    return null;
  }
  return null;
}

// Does this research candidate's data actually carry a classification signal (org_type
// or produces_content), as opposed to only a firmographic guess? JG-1(confidence_band):
// the confidence band is about classification confidence, not a size guess — a candidate
// carrying only e.g. lv_revenue_band must not trigger this reason.
function _carriesClassification(data) {
  const hasOrgType = !!(data && data.lv_org_type && data.lv_org_type !== "");
  const hasContent = !!(data && (data.lv_produces_content === true || data.lv_produces_content === false));
  return hasOrgType || hasContent;
}

// computeEscalation(researchCandidate, existingRecord) -> { needsJudge, reasons } — JG-1's
// trigger set. Exactly two arguments (RO-2 arity discipline, asserted by the tests): this
// function must never grow a third argument carrying the size-disagreement array or its
// watch-list constant. RO-2: size-band disagreement is detected DOWNSTREAM inside Merge
// Company and is deliberately invisible here — this gate runs before that node, so no
// model call can ever be triggered by a size disagreement alone.
function computeEscalation(researchCandidate, existingRecord) {
  // RO-1 first: no retrieval -> no judgement, ever. An unmatched candidate cannot
  // escalate even if it happens to carry a trigger-shaped value.
  if (!researchCandidate || !researchCandidate.matched) return { needsJudge: false, reasons: [] };

  const existing = existingRecord || {};
  const data = researchCandidate.data || {};
  const reasons = [];

  const existingOrgType = existing.lv_org_type;
  const existingOrgTypeKnown = !!existingOrgType && existingOrgType !== "unknown";
  if (existingOrgTypeKnown && data.lv_org_type && data.lv_org_type !== existingOrgType) {
    reasons.push("org_type_conflict");
  }

  if (data.lv_produces_content === false) {
    reasons.push("produces_content_false");
  }

  if (normalizeVendorFlag(data.lv_is_hardware_vendor) === true) {
    reasons.push("hardware_vendor_detected");
  }
  if (normalizeVendorFlag(data.lv_is_gambling_operator) === true) {
    reasons.push("gambling_operator_detected");
  }

  const [lo, hi] = ESCALATION_CONFIDENCE_BAND;
  const conf = researchCandidate.confidence;
  if (typeof conf === "number" && conf >= lo && conf <= hi && _carriesClassification(data)) {
    reasons.push("confidence_band");
  }

  return { needsJudge: reasons.length > 0, reasons };
}

// applyUnadjudicated(researchCandidate, reasons) -> the D5 fail-safe. Applied when a
// trigger fired but the judge did not run (kill switch off, cap exhausted) or did not
// confirm. Returns a NEW candidate (no in-place mutation).
function applyUnadjudicated(researchCandidate, reasons) {
  if (!researchCandidate) return researchCandidate;
  const data = { ...(researchCandidate.data || {}) };
  const evidence_by_field = { ...(researchCandidate.evidence_by_field || {}) };

  // Unadjudicated hard-veto INPUT must never promote (Pitfall 6) -> demote to null,
  // never false.
  if (normalizeVendorFlag(data.lv_is_hardware_vendor) === true) {
    data.lv_is_hardware_vendor = null;
    delete evidence_by_field.lv_is_hardware_vendor;
  }
  if (normalizeVendorFlag(data.lv_is_gambling_operator) === true) {
    data.lv_is_gambling_operator = null;
    delete evidence_by_field.lv_is_gambling_operator;
  }
  // Never flip a promoted org type on an unadjudicated re-research: drop the candidate's
  // value entirely so the existing record value stands.
  if ((reasons || []).includes("org_type_conflict")) {
    delete data.lv_org_type;
    delete evidence_by_field.lv_org_type;
  }
  // lv_produces_content: UNCHANGED (D5 table) — an evidenced `false` still flows
  // (Phase 13 TS-3); not this phase's call to neuter it.

  return {
    ...researchCandidate,
    data,
    evidence_by_field,
    judge_flags: {
      ...(researchCandidate.judge_flags || {}),
      unadjudicated: true,
      reasons: reasons || [],
    },
  };
}

module.exports = {
  isCitationSufficient, applyEvidenceSufficiency,
  normalizeVendorFlag, computeEscalation, applyUnadjudicated,
};
