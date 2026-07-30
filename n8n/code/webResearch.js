// n8n/code/webResearch.js — hand-written JS twin of src/taxonomy.py's
// validate_research_output / to_provider_result (Phase 13, OC-1..4/TS-1..3/AT-2/ER-1).
// Production runtime logic (AR-4: nodes can't require() project files at runtime, so
// this file is hand-written and proven equal to Python by test, not generated) —
// parity is proven by tests/n8n/parity.test.mjs against the shared fixture table in
// tests/fixtures/research_validation_cases.json.
const { normalizeOrgTypeResult, normalizeContentTypes } = require("./taxonomy");

const ALLOWED_REPRESENTS = new Set(["group", "subsidiary", "franchise_outlet", "single_entity", "unknown"]);

// CLAUDE.md §14.2 web-research return contract (AU|NZ|ANZ|Other|Unknown) — a value
// outside this set is model garbage/hallucination, not a real region. It is already
// passed through generically as `data.lv_country_region_normalized` by the wholesale
// `{...raw.data}` spread below (mirrors lv_sponsorship_reliant, Phase 18 COPY-01); this
// guard only clamps an unrecognized value so it never silently promotes as an invented
// enum string (existing provider-side normalizeCountryRegion, n8n/code/normalizeProviders.js,
// is NOT reused here — it maps raw country NAMES like "Australia", not this field's
// already-normalized enum output, and would wrongly demote a valid "ANZ"/"Unknown" to "Other").
const ALLOWED_COUNTRY_REGIONS = new Set(["AU", "NZ", "ANZ", "Other", "Unknown"]);

function validateResearchOutput(raw) {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return {
      matched: false,
      data: {},
      evidence_by_field: {},
      entity_resolution: { represents: "unknown", likely_revenue_band: null, notes: "" },
      needs_review: true,
    };
  }

  const data = { ...(raw.data || {}) };
  const evidenceByField = { ...(raw.evidence_by_field || {}) };

  const orgResult = normalizeOrgTypeResult(data.lv_org_type);
  data.lv_org_type = orgResult.value;
  data.lv_content_type = normalizeContentTypes(data.lv_content_type);

  let producesContent = data.lv_produces_content;
  if (producesContent === false && !evidenceByField.lv_produces_content) {
    producesContent = null; // TS-2: unevidenced False is not evidence of absence
  }
  data.lv_produces_content = producesContent;

  if (data.lv_country_region_normalized !== undefined && data.lv_country_region_normalized !== null &&
      !ALLOWED_COUNTRY_REGIONS.has(data.lv_country_region_normalized)) {
    data.lv_country_region_normalized = "Unknown";
  }

  const er = raw.entity_resolution || {};
  const represents = ALLOWED_REPRESENTS.has(er.represents) ? er.represents : "unknown";

  return {
    matched: raw.matched !== false,
    data,
    evidence_by_field: evidenceByField,
    entity_resolution: {
      represents,
      likely_revenue_band: er.likely_revenue_band ?? null,
      notes: er.notes || "",
    },
    needs_review: orgResult.needs_review,
  };
}

function toProviderResult(raw) {
  const validated = validateResearchOutput(raw);
  const src = (raw && typeof raw === "object" && !Array.isArray(raw)) ? raw : {};
  return {
    provider: src.provider || "claude_web",
    object_type: src.object_type || "companies",
    matched: validated.matched,
    confidence: src.confidence || 0,
    data: validated.data,
    evidence: { evidence_urls: Object.values(validated.evidence_by_field) },
    evidence_by_field: validated.evidence_by_field,
  };
}

// normalizeUrlForMatch — tolerant URL matching (TA-3): the model's cited url in
// evidence_by_field and the search result's own url are two independently-generated
// strings that usually — not always — match exactly. Mirrors the same www.-stripping
// shape isCitationSufficient (judge.js) already uses so the two normalizations cannot
// drift in opposite directions: lowercase, strip protocol (via URL parsing), strip a
// leading www., drop query/fragment (URL.pathname already excludes both), drop a single
// trailing slash. Returns null (never throws) on an unparseable url.
function normalizeUrlForMatch(url) {
  try {
    const parsed = new URL(String(url));
    const host = String(parsed.hostname || "").toLowerCase().replace(/^www\./, "");
    let pathname = parsed.pathname || "";
    if (pathname.length > 1 && pathname.endsWith("/")) pathname = pathname.slice(0, -1);
    return host + pathname;
  } catch (e) {
    return null;
  }
}

// extractPageAgeByField(content, evidenceByField) -> {field: page_age string|null} (TA-3).
// Anthropic's web_search_tool_result content blocks carry, per result, url/title/page_age
// ("when the site was last updated", free text) — researchCandidateFromHttpItem reads
// this exact `content` array today and discards every page_age. Recover them, matched by
// normalized url against each judge-eligible field's cited evidence url.
//
// V5/ASVS: never throws on any malformed/adversarial content shape — a Code node
// exception fails the whole n8n item and breaks the continue-on-error contract every
// node in this chain relies on. Deliberately NOT guarded by an Array.isArray(block.content)
// check at every level (see tests/n8n/webResearchFailure.test.mjs's DELIBERATE-BREAK,
// content:null) — a content:null block relies on THIS wrapping try/catch, not a
// per-level guard, to prove the catch itself is load-bearing rather than merely
// redundant with narrower checks.
function extractPageAgeByField(content, evidenceByField) {
  const byUrl = {};
  try {
    const blocks = Array.isArray(content) ? content : [];
    for (const block of blocks) {
      if (!block || block.type !== "web_search_tool_result") continue;
      for (const result of block.content) {
        if (!result || typeof result !== "object" || !result.url) continue;
        const key = normalizeUrlForMatch(result.url);
        if (key !== null) byUrl[key] = result.page_age || null;
      }
    }
  } catch (e) {
    return {};
  }

  const out = {};
  for (const [field, url] of Object.entries(evidenceByField || {})) {
    const key = url ? normalizeUrlForMatch(url) : null;
    out[field] = (key !== null ? byUrl[key] : null) || null;
  }
  return out;
}

// extractFinalJson — Pattern 1 (RESEARCH reference): pull the JSON object out of the
// model's final text content blocks, tolerating ```fences``` / stray prose. Mirrors
// src/web_research.py:_extract_json byte-for-byte (same regex, same fallback order).
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

// researchCandidateFromHttpItem — the "Validate Research Output" Code node's whole job:
// turn whatever item the Claude Web Research HTTP node produced under
// onError:"continueRegularOutput" into a research candidate, WITHOUT EVER THROWING
// (OC-4). Three failure shapes this must survive (Phase 13 Task 4): an n8n execution-
// error item (`{error: ...}`, no usable body), an Anthropic HTTP-level error body
// (`{"type":"error","error":{...}}` — has no `content` array), and an empty/missing
// `content` (no text blocks). Any of these — or a genuinely malformed text payload —
// resolves to toProviderResult({matched:false}) (needs_review:true via the OC-4 default-
// org-type path), so the company continues through Merge Company exactly as it would with
// ALLOW_WEB_RESEARCH=false (skip-not-retry, CLAUDE.md Section 26.2).
// Task 3 (TA-3): every failure path attaches EMPTY recency objects (not merely absent
// keys) — a silently-always-null recency looks identical to "the world has no page
// ages"; recency_source_by_field makes the match rate observable in a future smoke run.
function _unmatchedCandidate() {
  // NOTE: toProviderResult({}) would NOT give matched:false — an empty object is still a
  // dict, so validateResearchOutput takes its "else" branch where `matched` defaults to
  // true (OC-4's matched:false path is keyed on non-dict input only). Pass matched:false
  // explicitly so every failure path here is unambiguously unusable downstream.
  return { ...toProviderResult({ matched: false }), recency_by_field: {}, recency_source_by_field: {} };
}

function researchCandidateFromHttpItem(item) {
  try {
    if (!item || item.error || !Array.isArray(item.content)) {
      return _unmatchedCandidate();
    }
    const parsed = extractFinalJson(item.content);
    const candidate = toProviderResult(parsed);
    const pageAgeByField = extractPageAgeByField(item.content, candidate.evidence_by_field);
    const recency_by_field = {};
    const recency_source_by_field = {};
    for (const field of Object.keys(candidate.evidence_by_field || {})) {
      const age = pageAgeByField[field];
      recency_by_field[field] = age || null;
      recency_source_by_field[field] = age ? "page_age" : "unmatched";
    }
    return { ...candidate, recency_by_field, recency_source_by_field };
  } catch (e) {
    return _unmatchedCandidate();
  }
}

module.exports = {
  validateResearchOutput, toProviderResult, extractFinalJson, researchCandidateFromHttpItem,
  normalizeUrlForMatch, extractPageAgeByField,
};
