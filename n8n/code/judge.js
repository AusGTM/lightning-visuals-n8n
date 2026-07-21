// n8n/code/judge.js — Phase 14 judge wiring: JG-4 evidence sufficiency, JG-1/RO-1/RO-2
// escalation triggers, JG-2 judge payload, JG-3 never-throws verdict handling.
// Production runtime logic (AR-4: nodes can't require() project files at runtime, so
// this file is hand-written) — thresholds/vocabulary come from the GENERATED
// escalation.generated.js (Phase 14 D3, same split as taxonomy.js/taxonomy.generated.js).
const { KNOWN_VIDEO_HOSTS } = require("./escalation.generated");

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

module.exports = { isCitationSufficient, applyEvidenceSufficiency };
