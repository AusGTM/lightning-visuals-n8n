// enrichmentGate.js — pure-JS create/enrich/skip idempotency gate for n8n Code nodes.
//
// decideAction(existingRecord, requiredFields, policy, nowIso, opts)
//   → { action: 'create'|'enrich'|'skip', staleFields, missingFields, invalidFields, reason }
//
// Mirrors ENRICHMENT-WORKFLOW-PLAN.md §3:
//   - null/empty existingRecord ............... CREATE
//   - a required field is missing/blank ....... enrich (missing)
//   - stale: now - <field>_verified_at > policy.stale_after_days ... enrich (stale)
//       (a staleable field present but with NO _verified_at is treated as stale —
//        unknown freshness == needs validation)
//   - invalid: email fails a passed-in validity map (or basic syntax) / phone not E.164
//   - none of the above ....................... SKIP
//
// PURE + DETERMINISTIC: `nowIso` injected (no Date.now here). `opts.validity` is an
// optional { fieldName: boolean } map from an upstream verifier; when absent, email
// falls back to basic syntax and phone to normalizePhoneAU (E.164) checks.

const { normalizeEmailBasic } = require("./normalizeEmail");
const { normalizePhoneAU } = require("./normalizePhone");

function _isBlank(v) {
  return v === null || v === undefined || v === "" ||
         (Array.isArray(v) && v.length === 0);
}

function _isEmpty(record) {
  if (!record) return true;
  return Object.keys(record).every((k) => _isBlank(record[k]));
}

function _staleAfterDays(policy, field) {
  const p = policy && policy[field];
  return p && p.stale_after_days != null ? p.stale_after_days : null;
}

// Phase 15: staleness reads the REAL cache-key property, never the provenance blob
// (HubSpot cannot filter/read inside a JSON text property). Any leading `lv_` on `field`
// is stripped and re-prefixed exactly once, so `lv_org_type` -> `lv_org_type_verified_at`
// and `jobtitle` -> `lv_jobtitle_verified_at` (mirrors PN-4 composition).
function _cacheKeyName(field) {
  const base = String(field).replace(/^lv_/, "");
  return `lv_${base}_verified_at`;
}

function _fieldValid(field, value, validity) {
  if (validity && Object.prototype.hasOwnProperty.call(validity, field)) {
    return validity[field] === true;
  }
  if (field === "email") return normalizeEmailBasic(value) !== null;
  if (field === "phone" || field === "mobilephone") return normalizePhoneAU(value) !== null;
  return true; // no validation rule for this field
}

function decideAction(existingRecord, requiredFields, policy, nowIso, opts) {
  opts = opts || {};
  const validity = opts.validity || null;
  requiredFields = requiredFields || [];
  policy = policy || {};

  if (_isEmpty(existingRecord)) {
    return { action: "create", staleFields: [], missingFields: [], invalidFields: [],
             reason: "no existing record" };
  }

  const missingFields = [];
  const staleFields = [];
  const invalidFields = [];
  const now = Date.parse(nowIso);

  for (const field of requiredFields) {
    const value = existingRecord[field];

    if (_isBlank(value)) {
      missingFields.push(field);
      continue; // missing dominates — nothing else to check
    }

    if (!_fieldValid(field, value, validity)) {
      invalidFields.push(field);
    }

    const ttl = _staleAfterDays(policy, field);
    if (ttl != null) {
      const verifiedAt = existingRecord[_cacheKeyName(field)];
      if (_isBlank(verifiedAt)) {
        staleFields.push(field); // present value, unknown freshness -> validate
      } else {
        const then = Date.parse(verifiedAt);
        const ageDays = Number.isNaN(then) || Number.isNaN(now) ? Infinity : (now - then) / 86400000;
        if (ageDays > ttl) staleFields.push(field);
      }
    }
  }

  const needs = missingFields.length || staleFields.length || invalidFields.length;
  if (needs) {
    const parts = [];
    if (missingFields.length) parts.push(`missing: ${missingFields.join(",")}`);
    if (staleFields.length) parts.push(`stale: ${staleFields.join(",")}`);
    if (invalidFields.length) parts.push(`invalid: ${invalidFields.join(",")}`);
    return { action: "enrich", staleFields, missingFields, invalidFields, reason: parts.join("; ") };
  }

  return { action: "skip", staleFields: [], missingFields: [], invalidFields: [],
           reason: "all required fields present, fresh and valid" };
}

module.exports = { decideAction };
