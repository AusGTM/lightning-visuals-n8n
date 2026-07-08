// mergeContacts.js — pure-JS DETERMINISTIC non-clobber merge for n8n Code nodes.
//
// Mirrors the DETERMINISTIC parts of src/merge_policy.py (deterministic_gate +
// source_metadata + staging_property) for a single upload candidate per field.
// NO Haiku / NO Sonnet — the LLM classification/validation stages that merge_policy
// runs after the gate are intentionally omitted here (n8n Code nodes cannot call
// them; escalation happens in a downstream node). So the decision IS the gate's
// decision. Source = "csv" @ confidence 80 (matches src/ingest.py row_to_provider_result).
//
// Email can NEVER land in canonicalPatch on this enrich path (belt-and-braces: the
// manual_protected class + the 95 threshold already prevent it, and an explicit
// guard enforces it regardless of policy edits).

// Default contacts field policy (source of truth: config/field_policy.yaml `contacts`).
const DEFAULT_CONTACT_POLICY = {
  email:        { class: "manual_protected",  min_confidence: 95 },
  phone:        { class: "fill_blank_only",   min_confidence: 80 },
  mobilephone:  { class: "fill_blank_only",   min_confidence: 85 },
  jobtitle:     { class: "stale_refreshable", min_confidence: 75 },
  linkedin_url: { class: "fill_blank_only",   min_confidence: 85 },
  seniority:    { class: "system_owned",      min_confidence: 75 },
  persona_group:{ class: "system_owned",      min_confidence: 75 },
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

// Deterministic gate — single candidate, mirrors merge_policy.deterministic_gate.
// has_conflict is always false with one candidate, so the conflict branch is dropped.
function _gate(field, currentValue, confidence, policy) {
  const fieldClass = (policy && policy.class) || "fill_blank_only";
  const minConfidence = (policy && policy.min_confidence != null) ? policy.min_confidence : 80;

  if (confidence < minConfidence) {
    return { decision: "needs_review",
             reason: `Best confidence ${confidence} below threshold ${minConfidence}.` };
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

// mergeContacts(existingProps, candidateRow, fieldPolicy?, opts?)
//   existingProps: current HubSpot contact properties (the record being enriched)
//   candidateRow:  canonical-keyed upload row (post column-map + normalization)
//   fieldPolicy:   contacts policy block; defaults to DEFAULT_CONTACT_POLICY
//   opts:          { source="csv", confidence=80 }
function mergeContacts(existingProps, candidateRow, fieldPolicy, opts) {
  existingProps = existingProps || {};
  candidateRow = candidateRow || {};
  const policy = fieldPolicy || DEFAULT_CONTACT_POLICY;
  const source = (opts && opts.source) || "csv";
  const confidence = (opts && opts.confidence != null) ? opts.confidence : 80;
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

    // Always stage the raw candidate under its provider-namespaced key.
    stagingPatch[stagingProperty(source, field)] = value;

    const gate = _gate(field, currentValue, confidence, fieldPol);
    let decision = gate.decision;

    // HARD GUARD: email never promotes to canonical on the enrich path.
    if (field === "email" && decision === "promote") decision = "stage_only";

    const validationStatus = _statusFor(decision);

    // Stamp source metadata for every field with a chosen candidate.
    const meta = {
      [`${field}_source`]: source,
      [`${field}_confidence`]: confidence,
      [`${field}_verified_at`]: verifiedAt,
      [`${field}_validation_status`]: validationStatus,
    };
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
      verified_at: verifiedAt,
    });
  }

  return { canonicalPatch, stagingPatch, metadataPatch, decisions };
}

module.exports = { mergeContacts, stagingProperty, DEFAULT_CONTACT_POLICY };
