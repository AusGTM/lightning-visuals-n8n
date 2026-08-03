// n8n/code/hubspotEnums.js — hand-written enum validator over the generated HubSpot
// company enum data (hubspotEnums.generated.js). Consumed by BOTH the two places a
// candidate value can reach HubSpot: mergeCompanies.js (staging) and reviewApply.js
// (review approve) — one guard, every caller (31-CONTEXT.md "The fix shape").
//
// VALIDATE-AND-REFUSE, NO mapping layer (31-CONTEXT.md, decided 2026-08-03, do not
// relitigate): the ONLY mapping normalizeEnumValue performs is an exact case-insensitive
// label -> value match ("Sports" -> "SPORTS"). Everything else is refused, not guessed at
// — providers speak NAICS-ish sector labels, HubSpot's 148 `industry` values are
// LinkedIn-derived, and mapping between them is judgment, not lookup. The raw provider
// string survives elsewhere (staging fields / provenance), so refusing canonical
// promotion loses nothing.

const { COMPANY_ENUM_PROPERTIES } = require("./hubspotEnums.generated");

function isEnumBound(property) {
  return Object.prototype.hasOwnProperty.call(COMPANY_ENUM_PROPERTIES, property);
}

function _isBlank(v) {
  return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
}

// MESSAGE HINT ONLY (31-CONTEXT.md § Deferred Ideas — fuzzy matching as a mapping
// mechanism is explicitly deferred). Never consulted by normalizeEnumValue; only used to
// make enumRefusalMessage's sentence actionable.
//
// Token rule: lowercase the offending value, split on non-alphanumerics, drop tokens
// shorter than 4 chars (this is what stops the live case matching on the word "and"),
// score each label by how many of its own tokens appear in that set, keep the top 3 with
// score >= 1.
function _tokenize(text) {
  return String(text)
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length >= 4);
}

function _hintLabels(entry, offendingValue) {
  const offendingTokens = new Set(_tokenize(offendingValue));
  if (offendingTokens.size === 0) return [];

  const scored = [];
  for (const label of Object.keys(entry.labelToValue || {})) {
    // labelToValue keys are already lowercased by the generator.
    const labelTokens = _tokenize(label);
    let score = 0;
    for (const t of labelTokens) if (offendingTokens.has(t)) score += 1;
    if (score > 0) scored.push({ label, score });
  }
  scored.sort((a, b) => b.score - a.score);
  // Recover the ORIGINAL (non-lowercased) label text for the message: the generator's
  // `values` + a value->original-label lookup is not kept, so read it back off the
  // matching value via COMPANY_ENUM_PROPERTIES itself is unnecessary — labelToValue's own
  // keys are what we scored, and callers only need real accepted labels, which the
  // lowercased key already is (HubSpot label text has no meaningful casing to preserve
  // here beyond what json.dumps already carried through the generator).
  return scored.slice(0, 3).map((s) => s.label);
}

function enumRefusalMessage(property, value) {
  const entry = COMPANY_ENUM_PROPERTIES[property];
  const optionCount = entry ? (entry.values || []).length : 0;
  let msg = `"${value}" is not a value HubSpot accepts for ${property} `
    + `(${optionCount} option${optionCount === 1 ? "" : "s"} available).`;
  const hints = entry ? _hintLabels(entry, value) : [];
  if (hints.length) {
    msg += ` Closest accepted label(s): ${hints.join(", ")}.`;
  }
  return msg;
}

function _normalizeSingle(property, entry, value) {
  if (entry.values.indexOf(value) !== -1) {
    return { ok: true, value, reason: null };
  }
  const lower = String(value).toLowerCase();
  if (Object.prototype.hasOwnProperty.call(entry.labelToValue, lower)) {
    return { ok: true, value: entry.labelToValue[lower], reason: null };
  }
  return { ok: false, value, reason: enumRefusalMessage(property, value) };
}

// normalizeEnumValue(property, value) -> { ok, value, reason }
//
// - A property that is not enum-bound returns ok with the value unchanged.
// - A blank value returns ok unchanged.
// - Single-select: exact match against `values` wins first; otherwise a lowercased
//   lookup in `labelToValue` returns the INTERNAL value; otherwise not-ok, `value` left
//   as the ORIGINAL so the caller can report it.
// - Multi-select: split an array into elements (or a string on ";"), normalize each
//   part, ok only when EVERY part is ok, preserving the container shape passed in
//   (array in -> array out, string in -> semicolon-joined string out).
// - Never throws.
function normalizeEnumValue(property, value) {
  if (!isEnumBound(property)) return { ok: true, value, reason: null };
  if (_isBlank(value)) return { ok: true, value, reason: null };

  const entry = COMPANY_ENUM_PROPERTIES[property];

  if (!entry.multiSelect) {
    return _normalizeSingle(property, entry, value);
  }

  const wasString = typeof value === "string";
  const parts = wasString ? value.split(";") : (Array.isArray(value) ? value : [value]);
  const results = parts.map((p) => _normalizeSingle(property, entry, wasString ? p.trim() : p));
  const bad = results.find((r) => !r.ok);
  if (bad) return { ok: false, value, reason: bad.reason };

  const normalized = results.map((r) => r.value);
  return { ok: true, value: wasString ? normalized.join(";") : normalized, reason: null };
}

module.exports = { isEnumBound, normalizeEnumValue, enumRefusalMessage };
