// n8n/code/judge.js — Phase 14 judge wiring: JG-4 evidence sufficiency, JG-1/RO-1/RO-2
// escalation triggers, JG-2 judge payload, JG-3 never-throws verdict handling.
// Production runtime logic (AR-4: nodes can't require() project files at runtime, so
// this file is hand-written) — thresholds/vocabulary come from the GENERATED
// escalation.generated.js (Phase 14 D3, same split as taxonomy.js/taxonomy.generated.js).
const {
  KNOWN_VIDEO_HOSTS, ESCALATION_CONFIDENCE_BAND, JUDGE_MIN_CONFIDENCE, JUDGE_OUTPUT_REQUIRED,
} = require("./escalation.generated");
const { scoreCandidates } = require("./scoreEnrichment");

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
// carrying only a revenue-band-shaped size guess must not trigger this reason (Phase
// 15.5 Task 4 verify: Judge Gate's built jsCode must not name any size field at all, so
// this comment is deliberately field-name-agnostic).
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

// applyCostCap(rows, maxPerRun) -> a NEW array (TA-7). Walks rows in input order,
// decrementing a budget only for rows whose needs_judge is true; a row that wants the
// judge but has no budget left comes back as a NEW object with needs_judge false and a
// judge_capped true marker (never mutates the caller's row). Rows that never wanted the
// judge pass through untouched. maxPerRun of 0 or non-finite caps everything — this is
// what lets the ALLOW_SONNET_ESCALATION kill switch and the per-run budget share one
// code path in the wrapper (pass 0 when off, MAX_PER_RUN when on).
function applyCostCap(rows, maxPerRun) {
  const budget = Number.isFinite(maxPerRun) ? maxPerRun : 0;
  let remaining = budget;
  return (rows || []).map((row) => {
    if (!row || !row.needs_judge) return row;
    if (remaining <= 0) {
      return { ...row, needs_judge: false, judge_capped: true };
    }
    remaining -= 1;
    return row;
  });
}

// buildJudgeRequestBody(row, model, maxTokens) -> the Anthropic Messages body. JG-2:
// identity + classification ONLY — no revenue/employee size-band field, no raw
// annualrevenue/numberofemployees, anywhere in the serialized body, and NO tools key at
// all (Pitfall 5 — the judge reasons over evidence already retrieved, it must never
// re-search). Field-name-agnostic on purpose: this whole file gets inlined into the
// Judge Gate node, whose built jsCode Task 4's own verify step greps for zero size-field
// name references at all, not merely zero references inside the payload builder.
const _JUDGE_DATA_FIELDS = [
  "lv_org_type", "lv_produces_content", "lv_content_type",
  "lv_is_hardware_vendor", "lv_is_gambling_operator",
];

// Source trust for the two candidates scoreResearchCandidates ever constructs. Passed
// EXPLICITLY to scoreCandidates — without this the engine's unknown-source fallback
// would silently score both claude_web and prior_on_file at 0.6 (config/source_registry.yaml:
// claude_web trust_rank 78, hubspot/crm trust_rank 90 — the prior IS the CRM record).
const _RESEARCH_SCORING_TRUST = { claude_web: 0.78, prior_on_file: 0.9 };

// isIndependentPrior(provenanceEntry) -> boolean (D1's self-confirmation guard). A prior
// with NO provenance entry at all is independent (legacy / pre-pipeline / manually-typed
// value — Phase 15's provenance blob simply predates it). A prior whose provenance
// `source` is in the independent-origin allowlist (human, manual) is independent.
// EVERYTHING ELSE — including every source our own pipeline writes (claude_web,
// waterfall, apollo, zoominfo, lusha, ...) and any unrecognized/malformed source string —
// is NOT independent. Ambiguity fails CLOSED: we cannot prove independence, and the
// failure mode of guessing wrong is invisible confidence inflation.
const _INDEPENDENT_PRIOR_SOURCES = new Set(["human", "manual"]);

function isIndependentPrior(provenanceEntry) {
  if (provenanceEntry === undefined || provenanceEntry === null) return true; // no entry -> legacy, independent
  const source = provenanceEntry.source;
  return _INDEPENDENT_PRIOR_SOURCES.has(String(source));
}

function _isBlankValue(v) {
  return v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);
}

// Deterministic tie-break for a hand-merged ranked list (only needed when the prior is
// scored in a SEPARATE call from the research candidate — see below — so the two
// singleton `ranked[field]` arrays scoreCandidates already sorted internally must be
// combined into one list using the exact same rule scoreEnrichment.js's `ranked` uses).
function _sortRankedByScore(list, trust) {
  return [...list].sort((a, b) => {
    if (a.score !== b.score) return b.score - a.score;
    const ta = (trust && trust[String(a.source).toLowerCase()]) || 0;
    const tb = (trust && trust[String(b.source).toLowerCase()]) || 0;
    if (ta !== tb) return tb - ta;
    return String(a.source) < String(b.source) ? -1 : (String(a.source) > String(b.source) ? 1 : 0);
  });
}

// scoreResearchCandidates(researchCandidate, existingRecord, provenance, opts) -> the
// core of Phase 15.5 (TA-1/TA-2/TA-6). Scores each judge-eligible field's research value
// against a "prior on file" candidate built from the existing record + its Phase-15
// provenance blob, using the SAME unmodified scoreCandidates engine the provider
// waterfall uses — one formula, one weight set, one place a scoring bug can live.
//
// THE SELF-CONFIRMATION GUARD is the primary structural decision here, not a filter
// tacked on afterwards (D1): an INDEPENDENT prior joins the research candidate in the
// SAME scoreCandidates call, so the agreement (G) component is real in both directions.
// A NON-INDEPENDENT prior (written by our own pipeline) is scored in a SEPARATE call,
// alone — a lone candidate has no other sources in its group, so the existing engine
// gives it (and the research candidate in the other call) G=0, with no change to the
// engine at all. This is what stops the pipeline from manufacturing confidence by
// agreeing with its own earlier guess.
//
// Returns, per field carrying a non-blank research value: { field, ranked, research,
// recency_source, prior_on_file }. `research` is the research candidate's OWN scored
// entry — never the group argmax (the argmax may be the prior; the value being grounded
// is always the researched one). Fields absent from the research candidate's data get
// nothing attached (criterion 1: no information is discarded, but nothing is invented).
function scoreResearchCandidates(researchCandidate, existingRecord, provenance, opts) {
  const rc = researchCandidate || {};
  const data = rc.data || {};
  const existing = existingRecord || {};
  const prov = provenance || {};
  const now = opts && opts.now; // never read the clock here — scoreCandidates already
                                // defaults nowIso when this is undefined; injectable only.
  const trust = _RESEARCH_SCORING_TRUST;

  const result = {};

  for (const field of _JUDGE_DATA_FIELDS) {
    const value = data[field];
    if (_isBlankValue(value)) continue; // no research value for this field -> attach nothing

    const researchCand = {
      field, source: "claude_web", value, normalizedValue: value,
      accuracy: typeof rc.confidence === "number" ? rc.confidence / 100 : 0.6,
      recencyDate: (rc.recency_by_field && rc.recency_by_field[field]) || null,
    };

    const priorValue = existing[field];
    let priorCand = null;
    let independent = null;
    if (!_isBlankValue(priorValue)) {
      const provEntry = prov[field];
      priorCand = {
        field, source: "prior_on_file", value: priorValue, normalizedValue: priorValue,
        accuracy: (provEntry && typeof provEntry.confidence === "number") ? provEntry.confidence / 100 : 0.6, // D1 default
        recencyDate: (provEntry && provEntry.verified_at) || existing[field + "_verified_at"] || null,
      };
      independent = isIndependentPrior(provEntry);
    }

    let rankedList;
    if (priorCand && independent) {
      const scored = scoreCandidates([researchCand, priorCand], { trust, now });
      rankedList = scored.ranked[field];
    } else if (priorCand) {
      const rScored = scoreCandidates([researchCand], { trust, now });
      const pScored = scoreCandidates([priorCand], { trust, now });
      rankedList = _sortRankedByScore([...rScored.ranked[field], ...pScored.ranked[field]], trust);
    } else {
      const rScored = scoreCandidates([researchCand], { trust, now });
      rankedList = rScored.ranked[field];
    }

    const researchEntry = rankedList.find((c) => c.source === "claude_web");
    const priorEntry = priorCand ? rankedList.find((c) => c.source === "prior_on_file") : null;

    result[field] = {
      field,
      ranked: rankedList,
      research: researchEntry,
      recency_source: (rc.recency_source_by_field && rc.recency_source_by_field[field]) || "unmatched",
      prior_on_file: priorCand ? {
        value: priorValue,
        components: priorEntry ? priorEntry.components : null,
        independent,
      } : null,
    };
  }

  return result;
}

function buildJudgeRequestBody(row, model, maxTokens) {
  const id = (row && row.identity_keys) || {};
  const existing = (row && row.existingRecord) || {};
  const rc = (row && row.research_candidate) || {};
  const data = rc.data || {};

  const restrictedData = {};
  for (const f of _JUDGE_DATA_FIELDS) {
    if (f in data) restrictedData[f] = data[f];
  }

  const company = {
    name: id.companyName || existing.name || null,
    domain: id.domain || existing.domain || null,
    existing_lv_org_type: existing.lv_org_type || null,
    research_candidate: {
      data: restrictedData,
      evidence_by_field: rc.evidence_by_field || {},
    },
    escalation_reasons: (row && row.judge_reasons) || [],
  };

  const system = [
    "You are adjudicating a company classification conflict for an ICP scoring pipeline.",
    "Adjudicate identity and classification STRICTLY from the evidence already supplied",
    "below - never re-research, never assert any fact that no cited URL in",
    "evidence_by_field supports. If there is no evidence for a claim, the decision MUST",
    "be needs_review with a null chosen value, NEVER false - a missing citation is never",
    "evidence of absence (TS-1).",
    "Return ONLY one JSON object (no prose, no markdown fences) with exactly these keys: " +
      JSON.stringify([...JUDGE_OUTPUT_REQUIRED, "chosen_field"]) + ".",
  ].join(" ");

  return {
    model,
    max_tokens: maxTokens || 4096,
    system,
    messages: [{
      role: "user",
      content: JSON.stringify({ task: "judge_classification_conflict", company }),
    }],
  };
}

// extractFinalJson — DUPLICATED from n8n/code/webResearch.js, not require()'d: Task 5's
// Judge Gate / Build Judge Request / Apply Judge Verdict Code nodes inline only
// escalation.generated.js + judge.js (not webResearch.js), so this file carries its own
// copy. Keep in parity by hand with webResearch.js's version if either changes — same
// regex, same fallback order.
function extractFinalJson(content) {
  const text = (Array.isArray(content) ? content : [])
    .filter((b) => b && b.type === "text")
    .map((b) => b.text)
    .join("");
  const stripped = text.trim().replace(/^```(?:json)?\s*|\s*```$/gm, "").trim();
  try {
    return JSON.parse(stripped);
  } catch (e) {
    const m = stripped.match(/\{[\s\S]*\}/);
    if (!m) throw e;
    return JSON.parse(m[0]);
  }
}

// judgeVerdictFromHttpItem(item) — mirrors researchCandidateFromHttpItem (webResearch.js)
// exactly: NEVER THROWS, whatever shape the HTTP node hands it under
// onError:"continueRegularOutput". Every failure shape (n8n execution-error item,
// missing/empty content, Anthropic HTTP-level error body, unparseable text, a verdict
// missing a JUDGE_OUTPUT_REQUIRED key) resolves to
// { decision: "needs_review", chosen_value: null, confidence: 0, reason: "<shape>" }.
// JG-3: any verdict whose confidence < JUDGE_MIN_CONFIDENCE is rewritten to
// decision: "needs_review" before returning, regardless of what the model said.
function judgeVerdictFromHttpItem(item) {
  const fallback = (reason) => ({ decision: "needs_review", chosen_value: null, confidence: 0, reason });
  try {
    if (!item || item.error || !Array.isArray(item.content)) {
      return fallback("no usable judge response (execution error / missing content)");
    }
    const parsed = extractFinalJson(item.content);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return fallback("judge response was not a JSON object");
    }
    for (const key of JUDGE_OUTPUT_REQUIRED) {
      if (!(key in parsed)) return fallback(`judge verdict missing required key: ${key}`);
    }

    let verdict = { ...parsed };
    const confidence = Number(verdict.confidence);
    verdict.confidence = Number.isFinite(confidence) ? confidence : 0;
    if (!(verdict.confidence >= JUDGE_MIN_CONFIDENCE)) {
      verdict = { ...verdict, decision: "needs_review" }; // JG-3
    }
    return verdict;
  } catch (e) {
    return fallback("judge response failed to parse: " + ((e && e.message) || "unknown error"));
  }
}

// applyJudgeVerdict(researchCandidate, verdict, reasons) -> a NEW candidate. Only a
// promote/confirm verdict at confidence >= JUDGE_MIN_CONFIDENCE keeps the adjudicated
// value; there is no other path that can promote. Everything else (needs_review,
// reject, missing verdict, sub-threshold confidence) routes through applyUnadjudicated —
// the same D5 fail-safe an unadjudicated trigger uses.
function applyJudgeVerdict(researchCandidate, verdict, reasons) {
  const v = verdict || {};
  const promotes = (v.decision === "promote" || v.decision === "confirm") &&
    typeof v.confidence === "number" && v.confidence >= JUDGE_MIN_CONFIDENCE;

  if (promotes) {
    const data = { ...((researchCandidate && researchCandidate.data) || {}) };
    if (v.chosen_field && Object.prototype.hasOwnProperty.call(v, "chosen_value")) {
      data[v.chosen_field] = v.chosen_value;
    }
    return {
      ...(researchCandidate || {}),
      data,
      judge_flags: {
        ...((researchCandidate && researchCandidate.judge_flags) || {}),
        adjudicated: true,
        decision: v.decision,
      },
    };
  }

  const demoted = applyUnadjudicated(researchCandidate, reasons);
  return {
    ...demoted,
    judge_flags: {
      ...(demoted.judge_flags || {}),
      needs_review: true,
      verdict_reason: v.reason || null,
    },
  };
}

module.exports = {
  isCitationSufficient, applyEvidenceSufficiency,
  normalizeVendorFlag, computeEscalation, applyUnadjudicated, applyCostCap,
  isIndependentPrior, scoreResearchCandidates, _JUDGE_DATA_FIELDS,
  buildJudgeRequestBody, judgeVerdictFromHttpItem, applyJudgeVerdict,
};
