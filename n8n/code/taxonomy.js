// n8n/code/taxonomy.js — hand-written normalizer logic (spec D2) over the generated
// vocabulary data in taxonomy.generated.js. NM-1..NM-5 contracts, character-for-character
// behavioural match of src/taxonomy.py — parity is proven by tests/n8n/parity.test.mjs
// (NM-6), which shells out to the Python oracle for every case in
// tests/fixtures/taxonomy_parity_cases.json.
//
// No node in the current workflows requires() this yet — the web-research node that
// consumes it lands in Phase 13 (spec REQ-web-retrieval). Built now because NM-6 parity
// is a Phase 12 success criterion, and building the JS side later against a Python side
// that has already drifted is exactly how parity bugs are born.
const {
  ORG_TYPES, ORG_TYPE_SYNONYMS, DEFAULT_ORG_TYPE,
  CONTENT_TYPES, CONTENT_TYPE_SYNONYMS,
} = require("./taxonomy.generated");

// NM-3 comparison form. Must match src.taxonomy.normalize_key byte-for-byte: lowercase,
// every non-alphanumeric run -> single space, trim. `[^a-z0-9]+` (NOT `\W+`, which keeps
// `_` and would normalize "governing_body_league" differently than Python does).
function normalizeKey(raw) {
  if (raw === null || raw === undefined) return "";
  const s = String(raw).trim();
  if (s === "") return "";
  return s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

// Canonical keys map to themselves too (in normalized form) — an already-canonical
// value in any casing/punctuation still matches before the synonym table is checked.
function _lookup(canonicalKeys, synonyms) {
  const table = {};
  for (const key of canonicalKeys) table[normalizeKey(key)] = key;
  Object.assign(table, synonyms); // synonyms keyed by normalizeKey already (generated)
  return table;
}

const ORG_TYPE_LOOKUP = _lookup(ORG_TYPES, ORG_TYPE_SYNONYMS);
const CONTENT_TYPE_LOOKUP = _lookup(CONTENT_TYPES, CONTENT_TYPE_SYNONYMS);

// NM-1/NM-2/NM-3: canonical org_type key, or DEFAULT_ORG_TYPE. Never anything outside
// ORG_TYPES.
function normalizeOrgType(raw) {
  const key = normalizeKey(raw);
  const hit = ORG_TYPE_LOOKUP[key];
  return hit !== undefined ? hit : DEFAULT_ORG_TYPE;
}

// NM-4: needs_review is true whenever the result is the default AND the raw input was
// not already (a normalized form of) the default — blank/null input also counts as
// unmapped and reviews.
function normalizeOrgTypeResult(raw) {
  const value = normalizeOrgType(raw);
  const wasAlreadyDefault = normalizeKey(raw) === normalizeKey(DEFAULT_ORG_TYPE);
  const needsReview = value === DEFAULT_ORG_TYPE && !wasAlreadyDefault;
  return { value, needs_review: needsReview };
}

// NM-5: drop unrecognised entries, de-duplicate, preserve first-seen order. Non-array
// input -> [].
function normalizeContentTypes(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const item of raw) {
    const key = normalizeKey(item);
    const canonical = CONTENT_TYPE_LOOKUP[key];
    if (canonical === undefined) continue;
    if (!out.includes(canonical)) out.push(canonical);
  }
  return out;
}

module.exports = { normalizeKey, normalizeOrgType, normalizeOrgTypeResult, normalizeContentTypes };
