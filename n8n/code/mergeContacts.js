// mergeContacts.js — pure-JS DETERMINISTIC non-clobber merge for n8n Code nodes.
//
// Mirrors the DETERMINISTIC parts of src/merge_policy.py (deterministic_gate +
// source_metadata) for a single upload candidate per field.
// NO Haiku / NO Sonnet — the LLM classification/validation stages that merge_policy
// runs after the gate are intentionally omitted here (n8n Code nodes cannot call
// them; escalation happens in a downstream node). So the decision IS the gate's
// decision. Source = "csv" @ confidence 80 (matches src/ingest.py row_to_provider_result).
//
// EMAIL PERMISSIVE PROMOTION (260826-20w, T-20w-01, operator ruling): email now
// promotes into a BLANK contact record exactly like every other fill_blank_only field —
// it is no longer forced to stage_only regardless of policy. HubSpot's own dedupe/merge
// handles identity collisions on write; this client does not rebuild that logic
// client-side. What changed instead of a hard withhold: a promoted email's provenance
// entry (and the decisions-array row) carries the human-review validation status, so the
// decide node can flag the record for a human to see in the triage queue. An email that
// already exists on the record is completely unaffected — fill_blank_only's existing-
// value branch still routes to stage_only, the same non-clobber guarantee every other
// field in this policy carries. See 260826-20w-CALIBRATION.md for the threshold
// calibration (min_confidence 80, chosen to admit all three real contact-enrichment
// ingest lanes: waterfall 85, hubspot_native 85, csv 80).
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
//
// email: fill_blank_only @ 80 (260826-20w, T-20w-01 — was manual_protected @ 95, which
// no real candidate ever cleared). 80 is the highest confidence bar that still admits all
// three real ingest-lane constants this repo has (waterfall 85, hubspot_native 85, csv
// 80 — scripts/build_cloud_workflows.py) — the merge boundary discards per-candidate
// accuracy and always passes one of exactly these three flat numbers, so there is no
// finer distribution to calibrate against. See 260826-20w-CALIBRATION.md.
//
// city/state/country/hs_state_code/hs_country_region_code: fill_blank_only @ 80
// (260826-20w Task 2 commit 1) — five HubSpot-native contact properties, confirmed
// present/string/writable in the operator's 2026-08-26 portal export. 80 is at/below the
// only confidence these fields' one live source (the waterfall path) ever carries (85),
// so any threshold at or below 85 is behaviourally identical today; 80 is chosen to match
// the email threshold above rather than invent a second number.
const DEFAULT_CONTACT_POLICY = {
  email:                   { class: "fill_blank_only", min_confidence: 80 },
  phone:                   { class: "fill_blank_only",   min_confidence: 80 },
  mobilephone:             { class: "fill_blank_only",   min_confidence: 85 },
  // stale_after_days (Phase 72 Plan 04, D-72-06/07): mirrors config/field_policy.yaml
  // contacts.jobtitle exactly. Every production call site passes fieldPolicy=undefined,
  // so this default IS what the recency gate reads -- omitting it would leave the TTL
  // branch permanently dead (_isStale sees undefined -> false -> always needs_review).
  jobtitle:                { class: "stale_refreshable", min_confidence: 75, stale_after_days: 180 },
  lv_linkedin_url:         { class: "fill_blank_only",   min_confidence: 85 },
  // hs_linkedin_url: fill_blank_only @ 85 (Phase 72 Plan 02, D-72-04) — a write-only
  // mirror of lv_linkedin_url for the native portal property. Deliberately NOT chased
  // by ENRICH_GATE's REQUIRED list — see config/field_policy.yaml's comment.
  hs_linkedin_url:         { class: "fill_blank_only",   min_confidence: 85 },
  seniority:               { class: "system_owned",      min_confidence: 75 },
  lv_persona_group:        { class: "system_owned",      min_confidence: 75 },
  city:                    { class: "fill_blank_only",   min_confidence: 80 },
  state:                   { class: "fill_blank_only",   min_confidence: 80 },
  country:                 { class: "fill_blank_only",   min_confidence: 80 },
  hs_state_code:           { class: "fill_blank_only",   min_confidence: 80 },
  hs_country_region_code:  { class: "fill_blank_only",   min_confidence: 80 },
};

function _isBlank(v) {
  return v === null || v === undefined || v === "" ||
         (Array.isArray(v) && v.length === 0);
}

function _nowIso() {
  return new Date().toISOString();
}

// Phase 72 Plan 04 (D-72-07): the ONLY two legitimate observation-time sources are the
// run's own resolved `now` and HubSpot's own property-history timestamp. A candidate
// whose resolved source is not one of these four live providers carries NO observation
// time at all and can therefore never win a recency comparison -- this is what closes
// the backdated-CSV-column injection vector (T-72-02) by construction, not by policy.
function _isProviderSource(name) {
  return name === "apollo" || name === "lusha" || name === "zoominfo" || name === "claude_web";
}

// True only when `historyTimestamp` is a parseable instant strictly more than
// `staleAfterDays` before `now`. Missing/unparseable input is NEVER stale -- unknown
// freshness is not staleness, it is its own (more conservative) refusal branch.
function _isStale(historyTimestamp, staleAfterDays, now) {
  if (_isBlank(historyTimestamp) || staleAfterDays == null) return false;
  const t = Date.parse(historyTimestamp);
  const n = Date.parse(now);
  if (Number.isNaN(t) || Number.isNaN(n)) return false;
  return (n - t) > staleAfterDays * 86400000;
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

// Does this field+value need an evidence URL before it may promote? (Phase 16.2 Task 2
// additive port of mergeCompanies.js's _needsEvidence — inert for every contact field
// today: DEFAULT_CONTACT_POLICY declares no require_evidence_url/require_evidence_url_for
// entries, so this only bites once Plan 02's research fold supplies a policy that does.)
function _needsEvidence(policy, value) {
  if (!policy) return false;
  if (policy.require_evidence_url === true) return true;
  const gated = policy.require_evidence_url_for;
  if (Array.isArray(gated)) return gated.indexOf(value) !== -1;
  return false;
}

// Deterministic gate — single candidate, mirrors merge_policy.deterministic_gate.
// has_conflict is always false with one candidate, so the conflict branch is dropped.
// Phase 16.2 Task 2 (additive): evidenceUrl/value are new trailing params, mirroring
// mergeCompanies.js's _gate — every existing call site below still passes only the
// first 4 args, so evidenceUrl/value are undefined and _needsEvidence(...) is false.
function _gate(field, currentValue, confidence, policy, evidenceUrl, value,
               historyTimestamp, candidateObservedAt, now) {
  const fieldClass = (policy && policy.class) || "fill_blank_only";
  const minConfidence = (policy && policy.min_confidence != null) ? policy.min_confidence : 80;

  if (confidence < minConfidence) {
    return { decision: "needs_review",
             reason: `Best confidence ${confidence} below threshold ${minConfidence}.` };
  }
  // Evidence gate runs BEFORE the class branches: an unevidenced claim is never
  // promotable no matter how system_owned the field is (mirrors mergeCompanies.js,
  // CLAUDE.md §21.3) — inert today since no contact policy entry requires evidence.
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
    // Phase 72 Plan 04 (D-72-06/07): the real TTL branch. `historyTimestamp` is the
    // EXISTING value's own HubSpot property-history timestamp (opts.historyByField,
    // Task 3's fetch) -- unknown freshness (no timestamp reached the gate at all) is
    // its own, more conservative refusal, never treated as staleness.
    if (_isBlank(historyTimestamp)) {
      return { decision: "needs_review",
               reason: `Unknown freshness for the existing ${field} value (no history ` +
                       `timestamp available); needs review.` };
    }
    const staleAfterDays = policy && policy.stale_after_days;
    if (!_isStale(historyTimestamp, staleAfterDays, now)) {
      return { decision: "needs_review", reason: "Refresh candidate requires review in MVP." };
    }
    // The existing value IS stale -- but only a candidate with its OWN observation
    // time strictly newer than that history timestamp may replace it. A clockless
    // candidate (candidateObservedAt absent -- csv/human/hubspot/unlisted sources)
    // can never win this comparison, by construction (T-72-02).
    if (_isBlank(candidateObservedAt) || Date.parse(candidateObservedAt) <= Date.parse(historyTimestamp)) {
      return { decision: "needs_review",
               reason: `Existing ${field} value is stale (older than ${staleAfterDays} days) ` +
                       `but the candidate carries no observation newer than ${historyTimestamp}; ` +
                       `needs review.` };
    }
    return { decision: "promote",
             reason: `Existing ${field} value is stale (older than ${staleAfterDays} days: ` +
                     `history ${historyTimestamp}, now ${now}) and the candidate's own ` +
                     `observation ${candidateObservedAt} is newer.` };
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
//   opts:          { source="csv", confidence=80, evidence={field: url},
//                    confidenceByField={field: number}, sourceByField={field: string} }
//                  Phase 16.2 Task 2 (additive port of mergeCompanies.js's opts,
//                  mergeCompanies.js:150-169): `evidence` is a per-field evidence-URL
//                  map (absent = no evidence); `confidenceByField` overrides the flat
//                  `confidence` for one field. The ONE existing caller (ENRICH_MERGE's
//                  provider `mergeContacts(existing, candidate, undefined, {source,
//                  confidence})`) omits both keys and is therefore byte-identical —
//                  proven by tests/n8n/mergeContacts.test.mjs.
//                  Phase 62 Plan 04 (D-62-17): `sourceByField` mirrors
//                  `confidenceByField` exactly — it overrides the flat `source` for one
//                  field only, resolved into BOTH the provenance entry's `source` and
//                  the decisions-array row's `source_provider`, so the two can never
//                  disagree. Absent (every caller before this plan) keeps the function
//                  byte-identical to today's flat-source behaviour.
function mergeContacts(existingProps, candidateRow, fieldPolicy, opts) {
  existingProps = existingProps || {};
  candidateRow = candidateRow || {};
  const policy = fieldPolicy || DEFAULT_CONTACT_POLICY;
  const source = (opts && opts.source) || "csv";
  const flatConfidence = (opts && opts.confidence != null) ? opts.confidence : 80;
  const confidenceByField = (opts && opts.confidenceByField) || {};
  const sourceByField = (opts && opts.sourceByField) || {};
  const evidence = (opts && opts.evidence) || {};
  // Phase 72 Plan 04: resolved ONCE per call and used EVERYWHERE the wall clock used to
  // be read directly -- the TTL comparison and the provenance verified_at stamp share
  // the SAME instant, so a test supplying opts.now gets a deterministic provenance
  // stamp without post-hoc stripping. Absent -> real wall clock, byte-identical to
  // every caller before this plan.
  const now = (opts && opts.now) || _nowIso();
  // Phase 72 Plan 04 (D-72-07): the existing value's OWN HubSpot property-history
  // timestamp, per field -- absent for every caller before Plan 04's ingest-lane fetch
  // (Task 3) exists, which is exactly the pre-72 "unknown freshness" degrade.
  const historyByField = (opts && opts.historyByField) || {};
  const verifiedAt = now;

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
    // Same resolution, mirrored for source (Phase 62 Plan 04, D-62-17): the recorded
    // source and the source that was chosen can never disagree.
    const resolvedSource = sourceByField[field] != null ? sourceByField[field] : source;
    // Phase 72 Plan 04 (D-72-07): resolved PER FIELD from the SAME resolvedSource the
    // provenance entry already records -- never a second, independent lookup. Only a
    // field whose resolved source is one of the four live providers carries the
    // resolved `now` as its own observation time; csv/human/hubspot/unlisted sources
    // carry none and can therefore never win a recency comparison.
    const historyTimestamp = historyByField[field];
    const candidateObservedAt = _isProviderSource(resolvedSource) ? now : undefined;

    const gate = _gate(field, currentValue, confidence, fieldPol, evidenceUrl, value,
                       historyTimestamp, candidateObservedAt, now);
    const decision = gate.decision;

    // EMAIL PERMISSIVE PROMOTION (260826-20w, T-20w-01): a promoted email keeps its
    // promotion (no demotion to stage_only) but its validation_status is redirected to
    // the human-review literal, so the decide node's review-flag predicate (promote AND
    // human-review status) picks it up. Every other field's promotion is unaffected.
    const isEmailField = field === "email";
    const promoted = decision === "promote";
    let validationStatus = _statusFor(decision);
    if (isEmailField && promoted) validationStatus = "human_review_required";

    // ONE provenance entry per field — replaces the old flat metadataPatch/stagingPatch.
    const entry = { source: resolvedSource, confidence, verified_at: verifiedAt,
                    validation_status: validationStatus, value };
    if (!_isBlank(evidenceUrl)) entry.evidence_url = evidenceUrl;
    provenance[field] = entry;

    if (decision === "promote") {
      canonicalPatch[field] = value;
      // STALE-TIMESTAMP FIX (Phase 16.2 gpt #6): the cache-key datetime is stamped ONLY
      // when the field is actually ACCEPTED — moved inside this branch (was previously
      // unconditional) so a needs_review/stale-but-unpromoted candidate is never marked
      // fresh, which would otherwise suppress the next stale-refresh check forever.
      // Mirrored onto mergeCompanies.js in Phase 16.3 — both paths now carry the fix.
      if (CONTACT_CACHE_KEY_FIELDS[field]) {
        cacheKeys[CONTACT_CACHE_KEY_FIELDS[field]] = verifiedAt;
      }
    }

    decisions.push({
      field,
      current_value: currentValue === undefined ? null : currentValue,
      chosen_value: value,
      source_provider: resolvedSource,
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

// foldContactResearch(providerMerge, researchMerge, judgePromotedFields, existingRecord)
// -> {canonicalPatch, provenance, cacheKeys, decisions} — Phase 16.2 (SC-3) fold of a
// SECOND mergeContacts() result (the Claude web-research candidate, jobtitle/seniority)
// into the provider merge's result. This is a WRITE-SAFETY GATE, NOT adjudication (the
// judge already adjudicated any existing-record conflict upstream) — for each field the
// research candidate carries a decision for, research wins ONLY when:
//   (a) the judge PROMOTED it (field is in judgePromotedFields, the fresh chain-set
//       marker derived from applyContactJudgeVerdict's judge_flags.promoted_field — NEVER
//       the caller-injectable judge_confidence_by_field), OR
//   (b) it fills a GENUINE gap: the provider produced no canonical value for the field
//       AND the existing HubSpot record is also blank there (kimi HIGH-2 — provider-
//       absent alone is not a gap when the existing record already holds a value).
// Otherwise the provider/existing value stands, and the withheld research decision is
// rewritten to stage_only/"withheld_by_overlap_precedence" so the audit trail
// (decisions) agrees with the actual canonicalPatch (gpt #8).
function foldContactResearch(providerMerge, researchMerge, judgePromotedFields, existingRecord) {
  const provider = providerMerge || {};
  const research = researchMerge || {};
  const providerCanonical = provider.canonicalPatch || {};
  const researchCanonical = research.canonicalPatch || {};
  const researchProvenance = research.provenance || {};
  const researchCacheKeys = research.cacheKeys || {};
  const promoted = judgePromotedFields || [];
  const existing = existingRecord || {};

  const canonicalPatch = { ...providerCanonical };
  const provenance = { ...(provider.provenance || {}) };
  const cacheKeys = { ...(provider.cacheKeys || {}) };
  const decisions = [...(provider.decisions || [])];

  for (const decision of (research.decisions || [])) {
    const field = decision.field;
    const judgePromoted = promoted.indexOf(field) !== -1;
    const providerHasField = Object.prototype.hasOwnProperty.call(providerCanonical, field);
    const genuineGap = !providerHasField && _isBlank(existing[field]);
    const researchWins = judgePromoted || genuineGap;

    if (!researchWins) {
      decisions.push({ ...decision, decision: "stage_only", reason: "withheld_by_overlap_precedence" });
      continue;
    }

    decisions.push(decision);
    if (decision.decision !== "promote") continue; // researchWins but its own gate withheld it

    canonicalPatch[field] = researchCanonical[field];
    provenance[field] = researchProvenance[field];
    const cacheKeyName = CONTACT_CACHE_KEY_FIELDS[field];
    if (cacheKeyName && cacheKeyName in researchCacheKeys) {
      cacheKeys[cacheKeyName] = researchCacheKeys[cacheKeyName];
    }
  }

  return { canonicalPatch, provenance, cacheKeys, decisions };
}

module.exports = { mergeContacts, stableStringify, DEFAULT_CONTACT_POLICY, foldContactResearch };
