// mergeCompanies.js — pure-JS DETERMINISTIC non-clobber merge for COMPANY records.
//
// Companies sibling of mergeContacts.js. Same deterministic gate + provenance-blob shape
// (src/merge_policy.py), different field policy and two rules contacts do not have:
//   - `domain` hard guard (mirrors the contacts `email` guard)
//   - evidence-URL requirement on the ICP fields (field_policy.yaml
//     lv_produces_content.require_evidence_url / lv_org_type.require_evidence_url_for)
//
// PROVENANCE MODEL (Phase 15): per-field metadata/staging is ONE provenance object keyed
// by field ({source, confidence, verified_at, evidence_url?, validation_status, value}),
// not flat `{field}_source`/`{provider}_{field}` properties. The caller (the
// build_cloud_workflows.py wrapper) serializes it ONCE via stableStringify() into
// `lv_enrichment_provenance`, alongside the 2 cache-key datetimes this module surfaces on
// `cacheKeys` for lv_org_type / lv_produces_content.
//
// NO Haiku / NO Sonnet — the LLM stages merge_policy runs after the gate are omitted
// (n8n Code nodes cannot call them; escalation happens downstream). The decision IS the
// gate's decision.
//
// This computes the POLICY decision only. Whether a promoted field actually ships to
// HubSpot is the write gate's call (ALLOW_CANONICAL_WRITES, CLAUDE.md §18.5/§29) — that
// is deliberately NOT duplicated here.

const { EVIDENCE_GATED_ORG_TYPES } = require("./taxonomy.generated");

// Default companies field policy (source of truth: config/field_policy.yaml `companies`).
// lv_org_type's gated set is NOT hand-typed here (spec TX-4) — it derives from
// config/taxonomy.yaml org_types.*.requires_evidence via the generated taxonomy module,
// so adding/removing an evidence-gated org_type is a taxonomy.yaml + rebuild, not a
// second hand edit here.
const DEFAULT_COMPANY_POLICY = {
  domain:                  { class: "manual_protected",  min_confidence: 95 },
  industry:                { class: "stale_refreshable", min_confidence: 75 },
  numberofemployees:       { class: "stale_refreshable", min_confidence: 70 },
  annualrevenue:           { class: "review_required",   min_confidence: 85 },
  lv_revenue_band:         { class: "system_owned",      min_confidence: 75 },
  lv_employee_band:        { class: "system_owned",      min_confidence: 70 },
  // 75: deliberately above the flat-firmographic band (lv_employee_band at 70) because
  // this field is the geography input to the non-ANZ hard veto, so a wrong promotion
  // disqualifies a real account -- and below the evidence-gated judgment fields (85)
  // because it is a normalized enum with no evidence-URL requirement, so demanding
  // provider certainty here would leave it effectively stage-only and defeat the
  // purpose. This threshold is a reviewable judgment, not a derived constant.
  lv_country_region_normalized: { class: "system_owned", min_confidence: 75 },
  lv_org_type:             { class: "system_owned",      min_confidence: 80,
                             require_evidence_url_for: EVIDENCE_GATED_ORG_TYPES },
  lv_produces_content:     { class: "system_owned",      min_confidence: 85,
                             require_evidence_url: true },
  lv_content_type:         { class: "system_owned",      min_confidence: 75 },
  lv_sponsorship_reliant:  { class: "system_owned",      min_confidence: 70 },
  lv_is_hardware_vendor:   { class: "system_owned",      min_confidence: 85 },
  lv_is_gambling_operator: { class: "system_owned",      min_confidence: 85 },
  // lv_icp_fit_score / lv_icp_tier: Approach C (Phase 15 criterion 4) — HubSpot owns
  // these derived outputs. Removed from policy so either falls to the default
  // non-promoting policy (fill_blank_only) if it ever appears in a candidate, never
  // "score_output".
  lv_anti_icp_flag:        { class: "veto_output",       min_confidence: 0 },
  lv_anti_icp_reason:      { class: "veto_output",       min_confidence: 0 },
};

function _isBlank(v) {
  return v === null || v === undefined || v === "" ||
         (Array.isArray(v) && v.length === 0);
}

function _nowIso() {
  return new Date().toISOString();
}

// Recursively sort object keys before JSON.stringify — the JS half of the shared
// byte-identical serialization contract with src/merge_policy.py's serialize_provenance()
// (Python: json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)).
// JSON.stringify already emits compact ("," / ":") separators and raw (non-escaped)
// UTF-8 by default, matching Python's ensure_ascii=False — the only remaining gap is key
// ORDER, which this closes.
function _sortedForStringify(value) {
  if (Array.isArray(value)) return value.map(_sortedForStringify);
  if (value !== null && typeof value === "object") {
    const out = {};
    for (const k of Object.keys(value).sort()) out[k] = _sortedForStringify(value[k]);
    return out;
  }
  return value;
}

function stableStringify(value) {
  return JSON.stringify(_sortedForStringify(value));
}

// The 2 company cache-key fields (RT-5/SJ-2's queryable datetimes) — everything else
// rides in the provenance blob.
const COMPANY_CACHE_KEY_FIELDS = {
  lv_org_type: "lv_org_type_verified_at",
  lv_produces_content: "lv_produces_content_verified_at",
};

// Does this field+value need an evidence URL before it may promote?
// require_evidence_url: always. require_evidence_url_for: only for the listed values
// (e.g. lv_org_type may promote to "other" unevidenced, but not to "hardware_vendor").
function _needsEvidence(policy, value) {
  if (!policy) return false;
  if (policy.require_evidence_url === true) return true;
  const gated = policy.require_evidence_url_for;
  if (Array.isArray(gated)) return gated.indexOf(value) !== -1;
  return false;
}

// Deterministic gate — single candidate, mirrors merge_policy.deterministic_gate.
// has_conflict is always false with one candidate, so the conflict branch is dropped.
function _gate(field, currentValue, confidence, policy, evidenceUrl, value) {
  const fieldClass = (policy && policy.class) || "fill_blank_only";
  const minConfidence = (policy && policy.min_confidence != null) ? policy.min_confidence : 80;

  if (confidence < minConfidence) {
    return { decision: "needs_review",
             reason: `Best confidence ${confidence} below threshold ${minConfidence}.` };
  }
  // Evidence gate runs BEFORE the class branches: an unevidenced ICP claim is never
  // promotable no matter how system_owned the field is (CLAUDE.md §21.3).
  if (_needsEvidence(policy, value) && _isBlank(evidenceUrl)) {
    return { decision: "needs_review",
             reason: `Field ${field}=${value} requires an evidence URL; none supplied.` };
  }
  if (fieldClass === "manual_protected") {
    return { decision: "stage_only", reason: "Field is manual_protected." };
  }
  if (fieldClass === "review_required") {
    return { decision: "needs_review", reason: "Field requires review." };
  }
  if (fieldClass === "system_owned" || fieldClass === "score_output" || fieldClass === "veto_output") {
    return { decision: "promote", reason: "System-owned field passed confidence threshold." };
  }
  if (fieldClass === "fill_blank_only") {
    if (_isBlank(currentValue)) {
      return { decision: "promote", reason: "Current value blank and candidate passed threshold." };
    }
    return { decision: "stage_only", reason: "Current value exists and field is fill_blank_only." };
  }
  if (fieldClass === "stale_refreshable") {
    if (_isBlank(currentValue)) {
      return { decision: "promote", reason: "Current value blank and candidate passed threshold." };
    }
    return { decision: "needs_review", reason: "Refresh candidate requires review in MVP." };
  }
  return { decision: "stage_only", reason: "Default conservative behavior." };
}

function _statusFor(decision) {
  // Deterministic (no LLM) validation_status from source_registry vocabulary.
  return decision === "needs_review" ? "human_review_required" : "provider_only";
}

// mergeCompanies(existingProps, candidateRow, fieldPolicy?, opts?)
//   existingProps: current HubSpot company properties (the record being enriched)
//   candidateRow:  canonical-keyed candidate values (post normalizeProviders + score)
//   fieldPolicy:   companies policy block; defaults to DEFAULT_COMPANY_POLICY
//   opts:          { source="provider", confidence=80, evidence={field: url},
//                    confidenceByField={field: number} }
//                  `evidence` mirrors enrichmentGate's opts.validity: an upstream-supplied
//                  per-field map, absent = no evidence.
//                  `confidenceByField` (Phase 15.5 TA-8, additive) — a per-field override
//                  of the flat `confidence`; when a field has an entry here it wins,
//                  otherwise the flat value (and its 80 default) applies exactly as
//                  before. Every current caller omits this key and is therefore
//                  byte-identical. READ D2 (docs/... §8.5 / RESEARCH.md) before ever
//                  wiring an A/R/G/T composite score in here: this map must only ever
//                  carry a 0-100 confidence on the SAME scale as `confidence`
//                  (the judge verdict's per-field confidence), never the composite.
function mergeCompanies(existingProps, candidateRow, fieldPolicy, opts) {
  existingProps = existingProps || {};
  candidateRow = candidateRow || {};
  const policy = fieldPolicy || DEFAULT_COMPANY_POLICY;
  const source = (opts && opts.source) || "provider";
  const flatConfidence = (opts && opts.confidence != null) ? opts.confidence : 80;
  const confidenceByField = (opts && opts.confidenceByField) || {};
  const evidence = (opts && opts.evidence) || {};
  const verifiedAt = _nowIso();

  const canonicalPatch = {};
  const provenance = {};
  const cacheKeys = {};
  const decisions = [];

  for (const field of Object.keys(candidateRow)) {
    const value = candidateRow[field];
    if (_isBlank(value)) continue; // nothing to merge

    const currentValue = existingProps[field];
    const fieldPol = policy[field] || { class: "fill_blank_only", min_confidence: 80 };
    const evidenceUrl = evidence[field];
    // The resolved per-field value is used EVERYWHERE the flat one used to be — the gate
    // threshold, the provenance entry, and the decision record — so the recorded
    // confidence and the confidence that made the decision can never disagree.
    const confidence = confidenceByField[field] != null ? confidenceByField[field] : flatConfidence;

    const gate = _gate(field, currentValue, confidence, fieldPol, evidenceUrl, value);
    let decision = gate.decision;

    // HARD GUARD: domain never promotes to canonical on the enrich path (belt-and-braces —
    // the manual_protected class + the 95 threshold already prevent it, but this holds
    // regardless of policy edits). Mirrors the mergeContacts email guard.
    if (field === "domain" && decision === "promote") decision = "stage_only";

    const validationStatus = _statusFor(decision);

    // ONE provenance entry per field — replaces the old flat metadataPatch/stagingPatch.
    const entry = { source, confidence, verified_at: verifiedAt,
                    validation_status: validationStatus, value };
    if (!_isBlank(evidenceUrl)) entry.evidence_url = evidenceUrl;
    provenance[field] = entry;

    if (decision === "promote") {
      canonicalPatch[field] = value;
      // STALE-TIMESTAMP FIX (Phase 16.3, companies twin of Phase 16.2 gpt #6): the
      // cache-key datetime is stamped ONLY when the field is actually ACCEPTED — moved
      // inside this branch (was previously unconditional) so a needs_review/stale-but-
      // unpromoted candidate is never marked fresh, which would otherwise suppress the
      // next stale-refresh check (CLAUDE.md §19.5) forever.
      if (COMPANY_CACHE_KEY_FIELDS[field]) {
        cacheKeys[COMPANY_CACHE_KEY_FIELDS[field]] = verifiedAt;
      }
    }

    decisions.push({
      field,
      current_value: currentValue === undefined ? null : currentValue,
      chosen_value: value,
      source_provider: source,
      decision,
      confidence,
      reason: gate.reason,
      validation_status: validationStatus,
      evidence_url: _isBlank(evidenceUrl) ? null : evidenceUrl,
      verified_at: verifiedAt,
    });
  }

  return { canonicalPatch, provenance, cacheKeys, decisions };
}

module.exports = { mergeCompanies, stableStringify, DEFAULT_COMPANY_POLICY };
