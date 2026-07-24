// n8n/code/contactResearch.js — Phase 16.2 sibling of webResearch.js for the CONTACTS
// research chain (jobtitle/seniority ONLY — no phone/email/mobile PII ever enters this
// module, CLAUDE.md Section 16). Reuses webResearch.js's field-agnostic helpers
// (extractFinalJson, normalizeUrlForMatch) by requiring them — webResearch.js itself
// stays git-unchanged (companies byte-identity guard, Plan 01's frozen fixture).
//
// Production runtime logic (AR-4: n8n Code nodes can't require() sibling files at
// runtime) — this module is co-inlined alongside webResearch.js into the contact
// Validate Contact Research node body by build_cloud_workflows.py's inline(), never
// required at n8n runtime; the require() here exists for standalone node:test only
// (strip_module() drops it during inlining).
const { extractFinalJson, normalizeUrlForMatch } = require("./webResearch");

const CONTACT_RESEARCH_FIELDS = ["jobtitle", "seniority"];

function _trimOrNull(v) {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t === "" ? null : t;
}

// EVIDENCE URL (gpt #10): a jobtitle/seniority value may only survive validation if its
// cited evidence_by_field.<field> is a PARSEABLE https: URL — presence of SOME string is
// insufficient (a "javascript:"/empty/malformed value must demote just like a missing
// one). Reuses normalizeUrlForMatch's tolerant URL parsing (returns null on unparseable)
// plus an explicit protocol check.
function _hasSufficientEvidence(url) {
  if (typeof url !== "string" || url === "") return false;
  if (normalizeUrlForMatch(url) === null) return false; // unparseable, never throws
  try {
    return new URL(url).protocol === "https:";
  } catch (e) {
    return false; // no parse throw escapes this function
  }
}

// validateContactResearch(raw) — coerces data.jobtitle/data.seniority to trimmed-
// string-or-null (NO taxonomy normalization: contact titles/seniority are free-text,
// normalizeProviders.js already pushes them un-normalized). A value demotes to null
// (tri-state, mirrors judge.js's applyEvidenceSufficiency direction — never invents a
// false, only withholds) UNLESS its evidence_by_field.<field> passes _hasSufficientEvidence.
function validateContactResearch(raw) {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    // OC-4 mirror: non-dict input is unambiguously unusable.
    return { matched: false, data: {}, evidence_by_field: {}, confidence: 0 };
  }

  const rawData = raw.data || {};
  const rawEvidence = raw.evidence_by_field || {};
  const data = {};
  const evidence_by_field = {};

  for (const field of CONTACT_RESEARCH_FIELDS) {
    const value = _trimOrNull(rawData[field]);
    if (value === null) {
      data[field] = null;
      continue;
    }
    const url = rawEvidence[field];
    if (_hasSufficientEvidence(url)) {
      data[field] = value;
      evidence_by_field[field] = url;
    } else {
      data[field] = null; // demoted: evidence missing/insufficient, never a guess
    }
  }

  return {
    matched: raw.matched !== false, // default true unless explicitly false (OC-4)
    data,
    evidence_by_field,
    confidence: typeof raw.confidence === "number" ? raw.confidence : 0,
  };
}

function _unmatchedContactCandidate() {
  return { matched: false, data: {}, evidence_by_field: {}, confidence: 0 };
}

// contactResearchCandidateFromHttpItem(item) — the "Validate Contact Research" Code
// node's whole job: turn whatever item the Contact Web Research HTTP node produced under
// onError:"continueRegularOutput" into a research candidate, WITHOUT EVER THROWING
// (skip-not-retry, CLAUDE.md Section 26.2). Mirrors webResearch.js's
// researchCandidateFromHttpItem exactly for the three n8n failure shapes: an execution-
// error item, an Anthropic HTTP-level error body, and empty/missing content — plus a
// genuinely malformed text payload.
function contactResearchCandidateFromHttpItem(item) {
  try {
    if (!item || item.error || !Array.isArray(item.content)) {
      return _unmatchedContactCandidate();
    }
    const parsed = extractFinalJson(item.content);
    return validateContactResearch(parsed);
  } catch (e) {
    return _unmatchedContactCandidate();
  }
}

module.exports = {
  CONTACT_RESEARCH_FIELDS, validateContactResearch, contactResearchCandidateFromHttpItem,
};
