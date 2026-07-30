// adaptFetchById.js — pure-JS adapter for the HubSpot fetch-by-objectId lane (Phase 16.4).
//
// adaptFetchByIdResult(item) maps ONE row of a HubSpot search-by-hs_object_id node's raw
// output into { existingRecord, lookup_failed, fetch_diagnostic }. Same three response
// shapes as ENRICH_ADAPT_SEARCH (search envelope / single object / bare object), but
// DIFFERENT 0-results semantics: unlike an email/domain search, the id here came from a
// real HubSpot webhook event, so zero results means deleted/merged/stale-event — not
// confirmed-absent — and hs_object_id is server-assigned so a create could never set it
// anyway. Both the error case and the 0-results case map to lookup_failed:true, reusing
// the EXISTING create->skip override at ENRICH_GATE/ENRICH_CO_GATE unmodified — zero new
// failure vocabulary. `fetch_diagnostic` carries enough to tell the two failure modes
// apart at a glance in n8n's per-node execution view (Track B: hs_object_id filterability
// is MEDIUM confidence, unproven against this portal).
//
// backfillIdentityKeys(objectType, existingRecord, currentIdentityKeys) fills ONLY the
// currently-blank identity_keys from the fetched record — never overwrites a value the
// caller/event already supplied (a caller-envelope payload that somehow reaches this lane
// keeps its own values). Field derivation mirrors ENRICH_BUILD_IDENTITY (contacts) /
// ENRICH_BUILD_CO_IDENTITY (companies) exactly, so the backfilled shape is identical to
// what the direct-field lane would have produced.

function _truncate(s, n) {
  const str = String(s === null || s === undefined ? "" : s);
  return str.length > n ? str.slice(0, n) : str;
}

function _isBlank(v) {
  return v === null || v === undefined || v === "";
}

function adaptFetchByIdResult(item) {
  const failed = !item || item.error || (item.json && item.json.error);
  if (failed) {
    const errText = (item && (item.error || (item.json && item.json.error))) || "no response item";
    return {
      existingRecord: {},
      lookup_failed: true,
      fetch_diagnostic: `error: ${_truncate(errText, 200)}`,
    };
  }

  const res = item.json || {};

  if (Array.isArray(res.results)) {                                       // search envelope
    if (!res.results.length) {
      // 0 results on a KNOWN hs_object_id: the event came from HubSpot itself, so this
      // means deleted/merged/stale-event, NOT confirmed-absent (unlike an email/domain
      // search's legitimate 0-results case). Fail closed via lookup_failed rather than
      // risk a duplicate create on a server-assigned id a create could never set anyway.
      return {
        existingRecord: {},
        lookup_failed: true,
        fetch_diagnostic: "zero-results: hs_object_id not found (deleted/merged/stale event)",
      };
    }
    const first = res.results[0];
    return {
      existingRecord: { ...(first.properties || {}), hs_object_id: first.id },
      lookup_failed: false,
      fetch_diagnostic: "ok: matched via search envelope",
    };
  }

  if (res.properties) {                                                   // single object
    return {
      existingRecord: { ...res.properties, hs_object_id: res.id },
      lookup_failed: false,
      fetch_diagnostic: "ok: matched via single object",
    };
  }

  if (res.id) {                                                           // bare object
    return { existingRecord: res, lookup_failed: false, fetch_diagnostic: "ok: matched via bare object" };
  }

  // Well-formed 200 but an unrecognized shape — fail closed, never guess confirmed-absent.
  return {
    existingRecord: {},
    lookup_failed: true,
    fetch_diagnostic: "error: unrecognized response shape",
  };
}

// Contacts: mirrors ENRICH_BUILD_IDENTITY's field derivation exactly.
const _CONTACT_MAP = {
  email: "email",
  firstName: "firstname",
  lastName: "lastname",
  companyName: "company",
  linkedin_url: "lv_linkedin_url",
};

// Companies: mirrors ENRICH_BUILD_CO_IDENTITY's field derivation. `domain` is cleaned
// below (not a raw pass-through) — see cleanDomain.
const _COMPANY_MAP = {
  domain: "domain",
  companyName: "name",
};

// Identical to ENRICH_BUILD_CO_IDENTITY's cleanDomain. HubSpot's own stored `domain`
// property is normally already in this form, but the fetched value is run through the
// SAME cleaning defensively (never a raw pass-through) so a backfilled domain is
// guaranteed to match the stored form the rest of the companies branch expects, even if
// the property ever carries a scheme/www/path variant.
function cleanDomain(raw) {
  if (!raw) return null;
  let d = String(raw).trim().toLowerCase();
  d = d.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
  return d || null;
}

function backfillIdentityKeys(objectType, existingRecord, currentIdentityKeys) {
  if (!existingRecord || Object.keys(existingRecord).length === 0) {
    return currentIdentityKeys; // nothing fetched -> nothing to backfill, unchanged
  }

  const out = { ...(currentIdentityKeys || {}) };
  const isCompany = objectType === "companies";
  const map = isCompany ? _COMPANY_MAP : _CONTACT_MAP;

  for (const keyName of Object.keys(map)) {
    if (!_isBlank(out[keyName])) continue; // never overwrite a caller-supplied value
    const recordField = map[keyName];
    let v = existingRecord[recordField];
    if (isCompany && keyName === "domain") v = cleanDomain(v);
    if (!_isBlank(v)) out[keyName] = v;
  }

  if (!isCompany && _isBlank(out.domain) && !_isBlank(out.email)) {
    // Contacts only: domain derives from the (possibly just-backfilled) email's own
    // domain part — mirrors ENRICH_BUILD_IDENTITY:806 exactly.
    const parts = String(out.email).split("@");
    if (parts.length === 2 && parts[1]) out.domain = parts[1];
  }

  return out;
}

module.exports = { adaptFetchByIdResult, backfillIdentityKeys };
