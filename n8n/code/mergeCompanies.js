// mergeCompanies.js — pure-JS DETERMINISTIC non-clobber merge for COMPANY records.
//
// Companies sibling of mergeContacts.js. Same deterministic gate + source_metadata +
// staging_property shape (src/merge_policy.py), different field policy and two rules
// contacts do not have:
//   - `domain` hard guard (mirrors the contacts `email` guard)
//   - evidence-URL requirement on the ICP fields (field_policy.yaml
//     lv_produces_content.require_evidence_url / lv_org_type.require_evidence_url_for)
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

function stagingProperty(provider, field) {
  return `${provider}_${field}`;
}

function _nowIso() {
  return new Date().toISOString();
}

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
//   opts:          { source="provider", confidence=80, evidence={field: url} }
//                  `evidence` mirrors enrichmentGate's opts.validity: an upstream-supplied
//                  per-field map, absent = no evidence.
function mergeCompanies(existingProps, candidateRow, fieldPolicy, opts) {
  existingProps = existingProps || {};
  candidateRow = candidateRow || {};
  const policy = fieldPolicy || DEFAULT_COMPANY_POLICY;
  const source = (opts && opts.source) || "provider";
  const confidence = (opts && opts.confidence != null) ? opts.confidence : 80;
  const evidence = (opts && opts.evidence) || {};
  const verifiedAt = _nowIso();

  const canonicalPatch = {};
  const stagingPatch = {};
  const metadataPatch = {};
  const decisions = [];

  for (const field of Object.keys(candidateRow)) {
    const value = candidateRow[field];
    if (_isBlank(value)) continue; // nothing to merge

    const currentValue = existingProps[field];
    const fieldPol = policy[field] || { class: "fill_blank_only", min_confidence: 80 };
    const evidenceUrl = evidence[field];

    // Always stage the raw candidate under its provider-namespaced key.
    stagingPatch[stagingProperty(source, field)] = value;

    const gate = _gate(field, currentValue, confidence, fieldPol, evidenceUrl, value);
    let decision = gate.decision;

    // HARD GUARD: domain never promotes to canonical on the enrich path (belt-and-braces —
    // the manual_protected class + the 95 threshold already prevent it, but this holds
    // regardless of policy edits). Mirrors the mergeContacts email guard.
    if (field === "domain" && decision === "promote") decision = "stage_only";

    const validationStatus = _statusFor(decision);

    // Stamp source metadata for every field with a chosen candidate.
    const meta = {
      [`${field}_source`]: source,
      [`${field}_confidence`]: confidence,
      [`${field}_verified_at`]: verifiedAt,
      [`${field}_validation_status`]: validationStatus,
    };
    if (!_isBlank(evidenceUrl)) meta[`${field}_evidence_url`] = evidenceUrl;
    Object.assign(metadataPatch, meta);

    if (decision === "promote") {
      canonicalPatch[field] = value;
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

  return { canonicalPatch, stagingPatch, metadataPatch, decisions };
}

module.exports = { mergeCompanies, stagingProperty, DEFAULT_COMPANY_POLICY };
