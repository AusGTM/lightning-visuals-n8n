// n8n/code/contactJudge.js — Phase 16.2 sibling of judge.js for the CONTACTS judge chain
// (jobtitle/seniority ONLY). Field config lives HERE, in a module-level constant, never
// as a 3rd argument to computeContactEscalation (judge.js:97-102 arity discipline —
// computeEscalation/computeContactEscalation both stay 2-arg functions).
//
// Production runtime logic (AR-4) — co-inlined alongside judge.js/escalation.generated.js
// into the contact Judge Gate / Build Contact Judge Request / Apply Contact Judge Verdict
// Code node bodies by build_cloud_workflows.py's inline(); judge.js/escalation.generated.js
// stay git-unchanged (companies byte-identity guard).
const { ESCALATION_CONFIDENCE_BAND, JUDGE_MIN_CONFIDENCE, JUDGE_OUTPUT_REQUIRED } =
  require("./escalation.generated");

// Field config — never a 3rd arg to computeContactEscalation.
const _CONTACT_JUDGE_FIELDS = ["jobtitle", "seniority"];

function _norm(v) {
  return typeof v === "string" ? v.trim().toLowerCase() : v;
}

// Does this candidate carry a jobtitle/seniority signal at all (vs. nothing to judge)?
function _carriesSignal(data) {
  return !!(data && (_norm(data.jobtitle) || _norm(data.seniority)));
}

// computeContactEscalation(researchCandidate, existingRecord) -> {needsJudge, reasons}.
// EXACTLY two arguments (judge.js:97-102 arity discipline). RO-1 carries over: an
// unmatched candidate never escalates. NO jobtitle_stale_refresh reason here — staleness
// is a RESEARCH gate/needsResearch trigger (CONTACTS_TARGET, Plan 01), where a clock is
// allowed; this function stays clock-free (LOW-7). NO vendor/veto/org reasons; NO
// provider-vs-research comparison (SC-3 honest mirror — companies does not adjudicate
// provider-vs-research either, only existing-record conflicts).
function computeContactEscalation(researchCandidate, existingRecord) {
  if (!researchCandidate || !researchCandidate.matched) return { needsJudge: false, reasons: [] };

  const existing = existingRecord || {};
  const data = researchCandidate.data || {};
  const reasons = [];

  const existingJobtitle = _norm(existing.jobtitle);
  const researchJobtitle = _norm(data.jobtitle);
  if (existingJobtitle && researchJobtitle && existingJobtitle !== researchJobtitle) {
    reasons.push("jobtitle_conflict");
  }

  const existingSeniority = _norm(existing.seniority);
  const researchSeniority = _norm(data.seniority);
  if (existingSeniority && researchSeniority && existingSeniority !== researchSeniority) {
    reasons.push("seniority_conflict");
  }

  const [lo, hi] = ESCALATION_CONFIDENCE_BAND;
  const conf = researchCandidate.confidence;
  if (typeof conf === "number" && conf >= lo && conf <= hi && _carriesSignal(data)) {
    reasons.push("confidence_band");
  }

  return { needsJudge: reasons.length > 0, reasons };
}

// applyContactUnadjudicated(researchCandidate, reasons) -> a NEW candidate. Contact
// analog of judge.js's applyUnadjudicated (:141-175) — drops the conflicting field so the
// existing record value stands (fail-safe for a trigger that fired but the judge did not
// run/confirm).
function applyContactUnadjudicated(researchCandidate, reasons) {
  if (!researchCandidate) return researchCandidate;
  const data = { ...(researchCandidate.data || {}) };
  const evidence_by_field = { ...(researchCandidate.evidence_by_field || {}) };
  const rs = reasons || [];

  if (rs.includes("jobtitle_conflict")) {
    delete data.jobtitle;
    delete evidence_by_field.jobtitle;
  }
  if (rs.includes("seniority_conflict")) {
    delete data.seniority;
    delete evidence_by_field.seniority;
  }

  return {
    ...researchCandidate,
    data,
    evidence_by_field,
    judge_flags: { ...(researchCandidate.judge_flags || {}), unadjudicated: true, reasons: rs },
  };
}

// buildContactJudgeRequestBody(row, model, maxTokens) — JG-2: identity + jobtitle/
// seniority ONLY, no size/vendor field name anywhere, and NO tools key at all (the judge
// reasons over evidence already retrieved, it must never re-search).
function buildContactJudgeRequestBody(row, model, maxTokens) {
  const id = (row && row.identity_keys) || {};
  const existing = (row && row.existingRecord) || {};
  const rc = (row && row.research_candidate) || {};
  const data = rc.data || {};

  const restrictedData = {};
  for (const f of _CONTACT_JUDGE_FIELDS) {
    if (f in data) restrictedData[f] = data[f];
  }

  const contact = {
    name: id.contactName || existing.name || null,
    company: id.companyName || existing.company || null,
    existing_jobtitle: existing.jobtitle || null,
    existing_seniority: existing.seniority || null,
    research_candidate: {
      data: restrictedData,
      evidence_by_field: rc.evidence_by_field || {},
    },
    escalation_reasons: (row && row.judge_reasons) || [],
  };

  const system = [
    "You are adjudicating a contact role conflict for a CRM enrichment pipeline.",
    "Adjudicate STRICTLY from the evidence already supplied below - never re-research,",
    "never assert any fact that no cited URL in evidence_by_field supports. If there is",
    "no evidence for a claim, the decision MUST be needs_review with a null chosen",
    "value, NEVER a guess - a missing citation is never evidence of absence.",
    "chosen_field, if you promote or confirm a value, MUST be exactly \"jobtitle\" or",
    "\"seniority\" - never any other field name.",
    "Return ONLY one JSON object (no prose, no markdown fences) with exactly these keys: " +
      JSON.stringify([...JUDGE_OUTPUT_REQUIRED, "chosen_field"]) + ".",
  ].join(" ");

  return {
    model,
    max_tokens: maxTokens || 2048,
    system,
    messages: [{
      role: "user",
      content: JSON.stringify({ task: "judge_contact_role_conflict", contact }),
    }],
  };
}

// applyContactJudgeVerdict(researchCandidate, verdict, reasons) -> a NEW candidate.
// SECURITY-HARDENED (gpt #5): the generic judge.js applyJudgeVerdict writes ANY model
// chosen_field verbatim — safe for companies (a closed, code-controlled field set), NOT
// safe here because ENRICH_PARSE_EVENT_CLOUD spreads raw caller event props into the row,
// so a verdict (or an injected marker upstream) naming chosen_field:"email" must NEVER
// write it. Promotes ONLY when chosen_field is in the {jobtitle, seniority} allowlist AND
// decision is promote/confirm AND confidence clears JUDGE_MIN_CONFIDENCE — the ONLY path
// that can ever write into data[chosen_field]. Every other verdict (including a validly-
// shaped promote naming an out-of-allowlist field) routes through applyContactUnadjudicated.
function applyContactJudgeVerdict(researchCandidate, verdict, reasons) {
  const v = verdict || {};
  const promotes = (v.decision === "promote" || v.decision === "confirm") &&
    typeof v.confidence === "number" && v.confidence >= JUDGE_MIN_CONFIDENCE &&
    _CONTACT_JUDGE_FIELDS.indexOf(v.chosen_field) !== -1;

  if (promotes) {
    const data = { ...((researchCandidate && researchCandidate.data) || {}) };
    if (Object.prototype.hasOwnProperty.call(v, "chosen_value")) {
      data[v.chosen_field] = v.chosen_value;
    }
    return {
      ...(researchCandidate || {}),
      data,
      judge_flags: {
        ...((researchCandidate && researchCandidate.judge_flags) || {}),
        adjudicated: true,
        decision: v.decision,
        promoted_field: v.chosen_field, // the ONLY trusted per-field adjudication signal
      },
    };
  }

  const demoted = applyContactUnadjudicated(researchCandidate, reasons);
  return {
    ...demoted,
    judge_flags: { ...(demoted.judge_flags || {}), needs_review: true, verdict_reason: v.reason || null },
  };
}

module.exports = {
  _CONTACT_JUDGE_FIELDS, computeContactEscalation, applyContactUnadjudicated,
  buildContactJudgeRequestBody, applyContactJudgeVerdict,
};
