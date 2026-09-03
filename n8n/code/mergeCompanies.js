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
// Phase 31 (BUG 28): staging never offers an unmappable enum candidate for review — see
// the ENUM GUARD comments inline below and n8n/code/hubspotEnums.js for the validator.
const { normalizeEnumValue } = require("./hubspotEnums");

// Default companies field policy (source of truth: config/field_policy.yaml `companies`).
// lv_org_type's gated set is NOT hand-typed here (spec TX-4) — it derives from
// config/taxonomy.yaml org_types.*.requires_evidence via the generated taxonomy module,
// so adding/removing an evidence-gated org_type is a taxonomy.yaml + rebuild, not a
// second hand edit here.
const DEFAULT_COMPANY_POLICY = {
  // system_correctable_sources (quick task 260904-pav): the provenance sources whose
  // recorded value this engine may correct despite manual_protected. Exactly ONE member,
  // and not by accident: `create_seed` (ENRICH_DECIDE_CO_CLOUD's create branch) is the
  // only source in the system that ever writes a canonical `domain`. Every other source's
  // `domain` provenance entry is a STAGED REFUSAL — mergeCompanies provenances every
  // field, promoted or not — so admitting `waterfall`/`claude_web`/`hubspot_native`/
  // `june_2026` would let a candidate this gate already refused authorise its own
  // promotion on the next run. An absent key means "never correctable", which is what
  // every other field (and the unreachable contacts branch) keeps.
  domain:                  { class: "manual_protected",  min_confidence: 95,
                             system_correctable_sources: ["create_seed"] },
  industry:                { class: "stale_refreshable", min_confidence: 75 },
  // 58-05 Task 2: reclassified stale_refreshable -> fill_blank_only (operator ruling,
  // 2026-08-26, 58-03-SUMMARY.md Decisions Made item (b); CLAUDE.md §29 amended to match).
  // Scope: THIS lane only, blank-fill, provider-sourced values -- a non-blank existing
  // headcount is now protected outright rather than routed to needs_review.
  numberofemployees:       { class: "fill_blank_only",   min_confidence: 70 },
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
  // 58-05 Task 1: native `country` -- fill_blank_only mirrors the class already used
  // elsewhere in this file for exactly this behaviour (a blank fills, a non-blank is
  // protected). 75 mirrors lv_country_region_normalized's threshold above, since both
  // are derived from the same provider location signal.
  country:                 { class: "fill_blank_only",   min_confidence: 75 },
  // 58-05 Task 2: native `city` -- same class/confidence reasoning as `country` above
  // (same fill_blank_only behaviour, same provider location signal family).
  city:                    { class: "fill_blank_only",   min_confidence: 75 },
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
  // 80 (D-04 / P2): these two entries are NOT on a live path after D-01 — the veto is
  // derived directly in ENRICH_DECIDE_CO_CLOUD from already-merged fields, never supplied
  // to mergeCompanies() as a candidate. They stay declared here only so a future
  // accidental candidate is born guarded: 0 made _gate()'s `confidence < minConfidence`
  // check unreachable (confidence is never negative), which is exactly what let P2
  // promote a veto at confidence 5 with no defensible provenance. 80 matches the already-
  // gated inputs the veto derives from (lv_is_hardware_vendor at 85,
  // lv_country_region_normalized at its own threshold above).
  lv_anti_icp_flag:        { class: "veto_output",       min_confidence: 80 },
  lv_anti_icp_reason:      { class: "veto_output",       min_confidence: 80 },
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

// Parse the record's `lv_enrichment_provenance` blob. Fails CLOSED: anything that is not
// a readable plain object degrades to {} and therefore to today's refusal. Deliberately
// module-private rather than an import — the wrapper's own _parseProvenanceBlob lives in
// scripts/build_cloud_workflows.py, not in n8n/code/, so there is nothing to share.
function _parseProvenanceEntries(raw) {
  if (raw === null || raw === undefined || raw === "") return {};
  let parsed = raw;
  if (typeof raw === "string") {
    try { parsed = JSON.parse(raw); } catch (e) { return {}; }
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
  return parsed;
}

// May this manual_protected field's EXISTING value be corrected by the candidate?
// (quick task 260904-pav; CLAUDE.md §17.2's "existing value was previously written by the
// enrichment system" PROMOTE clause, finally implemented.) FOUR conjuncts, each of which
// refuses on its own:
//   1. the field's policy opts in via a non-empty system_correctable_sources list;
//   2. the record carries a provenance entry for this field whose `source` is on it;
//   3. the entry's recorded `value` is STILL the record's current value — otherwise a
//      human has since retyped it, or a previously refused candidate left the entry
//      behind, and neither may authorise a write;
//   4. rowConflicted === false STRICTLY. No permissive default: `undefined` refuses, so a
//      caller that has not opted in never gets this path with the franchisor guard off.
// The confidence bar is not restated here — _gate only reaches the class branches after
// its own `confidence < minConfidence` check, so a correction is automatically held to
// domain's 95, the highest threshold in the policy.
function _isSystemCorrectable(policy, entry, currentValue, rowConflicted) {
  const sources = policy && policy.system_correctable_sources;
  if (!Array.isArray(sources) || sources.length === 0) return false;
  if (!entry || typeof entry !== "object") return false;
  if (sources.indexOf(entry.source) === -1) return false;
  if (_isBlank(entry.value) || _isBlank(currentValue)) return false;
  if (String(entry.value) !== String(currentValue)) return false;
  return rowConflicted === false;
}

// Deterministic gate — single candidate, mirrors merge_policy.deterministic_gate.
// has_conflict is always false with one candidate, so the conflict branch is dropped.
function _gate(field, currentValue, confidence, policy, evidenceUrl, value,
               provenanceEntry, rowConflicted) {
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
    if (_isSystemCorrectable(policy, provenanceEntry, currentValue, rowConflicted)) {
      return { decision: "promote", correction: true,
               reason: `Existing value was written by the enrichment system ` +
                       `(provenance source ${provenanceEntry.source}) and still matches; ` +
                       `candidate passed the ${minConfidence} threshold on a conflict-free row.` };
    }
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
//                    confidenceByField={field: number}, rowConflicted=<boolean> }
//                  `rowConflicted` (260904-pav) — the caller's statement that some field
//                  on this row has materially conflicting sources. Only ever read by the
//                  manual_protected correction path, and only `false` (strictly) unlocks
//                  it; omitting the key refuses, so an un-migrated caller cannot get the
//                  correction with the franchisor guard silently off.
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
  // 260904-pav: parsed ONCE per call, not per field, and read strictly (see
  // _isSystemCorrectable) — `undefined` is not "no conflict", it is "caller did not say".
  const provenanceEntries = _parseProvenanceEntries(existingProps.lv_enrichment_provenance);
  const rowConflicted = opts && opts.rowConflicted;
  const verifiedAt = _nowIso();

  const canonicalPatch = {};
  const provenance = {};
  const cacheKeys = {};
  const decisions = [];

  for (const field of Object.keys(candidateRow)) {
    let value = candidateRow[field];
    if (_isBlank(value)) continue; // nothing to merge

    const currentValue = existingProps[field];
    const fieldPol = policy[field] || { class: "fill_blank_only", min_confidence: 80 };
    const evidenceUrl = evidence[field];
    // The resolved per-field value is used EVERYWHERE the flat one used to be — the gate
    // threshold, the provenance entry, and the decision record — so the recorded
    // confidence and the confidence that made the decision can never disagree.
    const confidence = confidenceByField[field] != null ? confidenceByField[field] : flatConfidence;

    // ENUM GUARD (Phase 31, BUG 28): run BEFORE the gate, so the gate's evidence check,
    // canonicalPatch, the provenance entry and the decision record all see whichever value
    // would actually be written. An exact case-insensitive label match (e.g. "Sports" ->
    // "SPORTS") normalizes `value` in place; an unmappable value leaves `value` as the
    // ORIGINAL provider string (nothing lost — it stays readable in provenance) and is
    // handled below, after the gate has spoken.
    const enumCheck = normalizeEnumValue(field, value);
    if (enumCheck.ok) value = enumCheck.value;

    const gate = _gate(field, currentValue, confidence, fieldPol, evidenceUrl, value,
                       provenanceEntries[field], rowConflicted);
    let decision = gate.decision;

    // HARD GUARD: domain never promotes to canonical on the enrich path (belt-and-braces —
    // the manual_protected class + the 95 threshold already prevent it, but this holds
    // regardless of policy edits). Mirrors the mergeContacts email guard.
    // 260904-pav: the ONE exception is the provenance-aware correction — a domain the
    // system parked itself, still unedited, on a conflict-free row, at >=95. Tested on
    // gate.correction (a structural flag), never on the reason string, and never by
    // relaxing the guard to "unless promote": every other domain promote still demotes.
    if (field === "domain" && decision === "promote" && !gate.correction) decision = "stage_only";
    // ENUM GUARD cont'd: a value HubSpot's enum will refuse is NEVER offered for review —
    // it stays staged (never needs_review, never promote), whatever the gate decided,
    // because no human approval can make an invalid enum value valid.
    if (!enumCheck.ok) decision = "stage_only";

    let validationStatus = _statusFor(decision);
    // The registered validation-status vocabulary (CLAUDE.md §6.1) already has `rejected`
    // — deterministic, not derived from `decision` like every other status here, so the
    // refusal reads as a refusal rather than an ordinary stage_only.
    if (!enumCheck.ok) validationStatus = "rejected";

    // ONE provenance entry per field — replaces the old flat metadataPatch/stagingPatch.
    const entry = { source, confidence, verified_at: verifiedAt,
                    validation_status: validationStatus, value };
    if (!_isBlank(evidenceUrl)) entry.evidence_url = evidenceUrl;
    provenance[field] = entry;

    if (decision === "promote") {
      // D-09/D-10 (43-01, PIPE-02): coercion only — min_confidence for the two
      // veto_output entries above is already 80 (Phase 40 D-04) and this path is not
      // live today (same comment). This is defence-in-depth for the class Task 2 closed
      // at the properties-finalization loop: a boolean-typed candidate is born as its
      // quoted string form the moment it is promoted here, so a future accidental veto
      // candidate is correct at birth, not just correct downstream. Every other type
      // (string, array, number) passes through unchanged — BUG-27's downstream array
      // join must still see arrays.
      canonicalPatch[field] = typeof value === "boolean" ? (value ? "true" : "false") : value;
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
      reason: enumCheck.ok ? gate.reason : enumCheck.reason,
      validation_status: validationStatus,
      evidence_url: _isBlank(evidenceUrl) ? null : evidenceUrl,
      verified_at: verifiedAt,
    });
  }

  return { canonicalPatch, provenance, cacheKeys, decisions };
}

module.exports = { mergeCompanies, stableStringify, DEFAULT_COMPANY_POLICY };
