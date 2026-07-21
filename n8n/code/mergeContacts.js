// mergeContacts.js — pure-JS DETERMINISTIC non-clobber merge for n8n Code nodes.
//
// Mirrors the DETERMINISTIC parts of src/merge_policy.py (deterministic_gate +
// source_metadata) for a single upload candidate per field.
// NO Haiku / NO Sonnet — the LLM classification/validation stages that merge_policy
// runs after the gate are intentionally omitted here (n8n Code nodes cannot call
// them; escalation happens in a downstream node). So the decision IS the gate's
// decision. Source = "csv" @ confidence 80 (matches src/ingest.py row_to_provider_result).
//
// Email can NEVER land in canonicalPatch on this enrich path (belt-and-braces: the
// manual_protected class + the 95 threshold already prevent it, and an explicit
// guard enforces it regardless of policy edits).
//
// PROVENANCE MODEL (Phase 15): per-field metadata/staging is ONE provenance object keyed
// by field ({source, confidence, verified_at, validation_status, value}), not flat
// `{field}_source`/`{provider}_{field}` properties. The caller (the
// build_cloud_workflows.py wrapper) serializes it ONCE via stableStringify() into
// `lv_contact_enrichment_provenance`, alongside the 2 cache-key datetimes this module
// surfaces on `cacheKeys` for jobtitle / mobilephone.

// Default contacts field policy (source of truth: config/field_policy.yaml `contacts`).
// PN-1: linkedin_url/persona_group are NOT HubSpot-native (absent from the verified-
// native list) -> lv_-prefixed canonical field keys.
const DEFAULT_CONTACT_POLICY = {
  email:           { class: "manual_protected",  min_confidence: 95 },
  phone:           { class: "fill_blank_only",   min_confidence: 80 },
  mobilephone:     { class: "fill_blank_only",   min_confidence: 85 },
  jobtitle:        { class: "stale_refreshable", min_confidence: 75 },
  lv_linkedin_url: { class: "fill_blank_only",   min_confidence: 85 },
  seniority:       { class: "system_owned",      min_confidence: 75 },
  lv_persona_group:{ class: "system_owned",      min_confidence: 75 },
};

function _isBlank(v) {
  return v === null || v === undefined || v === "" ||
         (Array.isArray(v) && v.length === 0);
}

function _nowIso() {
  return new Date().toISOString();
}

// Recursively sort object keys before JSON.stringify — see mergeCompanies.js's
// stableStringify() (identical implementation, duplicated per the existing
// self-contained-per-Code-node pattern this repo already uses for _isBlank/_nowIso/etc.)
// for the full parity-with-Python rationale.
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

// The 2 contact cache-key fields (queryable datetimes) — everything else rides in the
// provenance blob.
const CONTACT_CACHE_KEY_FIELDS = {
  jobtitle: "lv_jobtitle_verified_at",
  mobilephone: "lv_mobilephone_verified_at",
};

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
  const provenance = {};
  const cacheKeys = {};
  const decisions = [];

  for (const field of Object.keys(candidateRow)) {
    const value = candidateRow[field];
    if (_isBlank(value)) continue; // nothing to merge

    const currentValue = existingProps[field];
    const fieldPol = policy[field] || { class: "fill_blank_only", min_confidence: 80 };

    const gate = _gate(field, currentValue, confidence, fieldPol);
    let decision = gate.decision;

    // HARD GUARD: email never promotes to canonical on the enrich path.
    if (field === "email" && decision === "promote") decision = "stage_only";

    const validationStatus = _statusFor(decision);

    // ONE provenance entry per field — replaces the old flat metadataPatch/stagingPatch.
    provenance[field] = { source, confidence, verified_at: verifiedAt,
                          validation_status: validationStatus, value };

    if (CONTACT_CACHE_KEY_FIELDS[field]) {
      cacheKeys[CONTACT_CACHE_KEY_FIELDS[field]] = verifiedAt;
    }

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

  return { canonicalPatch, provenance, cacheKeys, decisions };
}

module.exports = { mergeContacts, stableStringify, DEFAULT_CONTACT_POLICY };
