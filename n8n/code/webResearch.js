// n8n/code/webResearch.js — hand-written JS twin of src/taxonomy.py's
// validate_research_output / to_provider_result (Phase 13, OC-1..4/TS-1..3/AT-2/ER-1).
// Production runtime logic (AR-4: nodes can't require() project files at runtime, so
// this file is hand-written and proven equal to Python by test, not generated) —
// parity is proven by tests/n8n/parity.test.mjs against the shared fixture table in
// tests/fixtures/research_validation_cases.json.
const { normalizeOrgTypeResult, normalizeContentTypes } = require("./taxonomy");

const ALLOWED_REPRESENTS = new Set(["group", "subsidiary", "franchise_outlet", "single_entity", "unknown"]);

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
// resolves to toProviderResult({}) (matched:false, needs_review:true via the OC-4 path),
// so the company continues through Merge Company exactly as it would with
// ALLOW_WEB_RESEARCH=false (skip-not-retry, CLAUDE.md Section 26.2).
function researchCandidateFromHttpItem(item) {
  // NOTE: toProviderResult({}) would NOT give matched:false — an empty object is still a
  // dict, so validateResearchOutput takes its "else" branch where `matched` defaults to
  // true (OC-4's matched:false path is keyed on non-dict input only). Pass matched:false
  // explicitly so every failure path here is unambiguously unusable downstream.
  try {
    if (!item || item.error || !Array.isArray(item.content)) {
      return toProviderResult({ matched: false });
    }
    const parsed = extractFinalJson(item.content);
    return toProviderResult(parsed);
  } catch (e) {
    return toProviderResult({ matched: false });
  }
}

module.exports = {
  validateResearchOutput, toProviderResult, extractFinalJson, researchCandidateFromHttpItem,
};
