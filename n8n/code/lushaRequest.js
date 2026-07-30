// lushaRequest.js — v3 Lusha request-body builders (contacts + companies lanes) and the
// contacts-lane reveal allow-list.
//
// Phase 20 (Lusha v2 -> v3 migration). Shapes confirmed live against api.lusha.com on
// 2026-07-30 — see docs/LUSHA-V3-CONTRACT.md (the contract of record, not RESEARCH.md's
// pre-probe hypothesis).
//
// REQ-lusha-selective-reveal was re-scoped upstream (commit 559eda5) after the v3 probe
// REFUTED assumption A3 (selective reveal as a cost lever — a reveal:["emails"] call and a
// reveal:["emails","phones"] call against the same stored id billed the SAME 0 credits).
// reveal[] survives here as PII-MINIMIZATION HYGIENE ONLY: never ask the provider to
// reveal a field HubSpot already holds, even though doing so wouldn't cost more. The real
// cost lever is stored-id re-enrichment (Plan 04), not this module.
//
// docs/LUSHA-V3-CONTRACT.md §6 confirms an empty `reveal: []` is REJECTED (400: "reveal
// must contain at least 1 elements") — that constraint was measured against
// /v3/contacts/enrich, and is treated here as a general request-validation rule that also
// applies to /v3/contacts/search-and-enrich (the endpoint this module builds for — see
// §7's "ship on the combined endpoint" verdict). lushaContactBody() therefore always
// emits a non-empty reveal array, defaulting to ["emails"] when nothing is missing.
//
// NO npm, dependency-free (no CommonJS/ESM module-loading statements) — this module is
// inline()'d verbatim into n8n Code nodes by scripts/build_cloud_workflows.py (mirrors
// normalizeProviders.js's module convention).

// Fixed allow-list: HubSpot field name (as it appears in the enrichment gate's
// `missingFields` array) -> the Lusha v3 reveal value string. ONLY two entries.
//
// - `jobtitle` is deliberately absent: docs/LUSHA-V3-CONTRACT.md's contacts response
//   (§4) returns `jobTitle` in the free preview (no reveal gate covers it) — it is never
//   a billed/gated reveal field, so it must never appear in a reveal list.
// - landline `phone` is deliberately absent: it is not in the contacts gate's REQUIRED
//   list (scripts/build_cloud_workflows.py ENRICH_GATE: ["email","jobtitle","mobilephone"]),
//   so it can never legitimately appear in `missingFields` — omitting it here is a second,
//   independent line of defense (belt-and-braces, not load-bearing on its own).
const LUSHA_REVEAL_BY_FIELD = Object.freeze({
  email: "emails",
  mobilephone: "phones",
});

// lushaReveal(missingFields) -> reveal value array, filtered through the frozen literal
// map above. Threat T-20-02 mitigation: reads use `hasOwnProperty` so a prototype-chain
// property name (e.g. "__proto__", "constructor") can never resolve to a value, and
// anything not an exact literal key (e.g. the ungated landline "phone") silently drops
// out rather than reaching the provider request. Sorted so output order never depends on
// input order (keeps the contract test deterministic). Tolerates non-array input.
function lushaReveal(missingFields) {
  if (!Array.isArray(missingFields)) return [];
  const out = [];
  for (const field of missingFields) {
    if (typeof field !== "string") continue;
    if (Object.prototype.hasOwnProperty.call(LUSHA_REVEAL_BY_FIELD, field)) {
      out.push(LUSHA_REVEAL_BY_FIELD[field]);
    }
  }
  return out.sort();
}

function _blank(v) {
  return v === null || v === undefined || v === "";
}

// lushaContactBody(identityKeys, missingFields) -> the v3
// POST /v3/contacts/search-and-enrich request body.
//
// identityKeys accepts any subset of the confirmed contacts identity properties
// (docs/LUSHA-V3-CONTRACT.md §3): email, linkedin_url, firstName, lastName, companyName,
// domain. This is deliberately generic — the CLOUD emission site passes only
// {email, linkedin_url} (the identity set live-confirmed for it pre-migration), while the
// LOCAL-LIVE builder and the dry-run harness pass the broader
// {firstName,lastName,companyName,domain,email,linkedin_url} set they already send. That
// split is carried forward on purpose (see scripts/build_cloud_workflows.py's Lusha Enrich
// node comment), not unified by this module.
//
// When no usable identity key is present, this returns the no-identity skip-not-retry form
// (`{ contacts: [] }`) rather than an element whose only content is a caller-chosen id —
// v3 rejects the v2-style synthetic `contactId` index key outright (docs/LUSHA-V3-CONTRACT.md
// §3: "property contactId should not exist").
function lushaContactBody(identityKeys, missingFields) {
  const id = identityKeys || {};
  const contact = {};
  if (!_blank(id.email)) contact.email = id.email;
  if (!_blank(id.linkedin_url)) contact.linkedinUrl = id.linkedin_url;
  if (!_blank(id.firstName)) contact.firstName = id.firstName;
  if (!_blank(id.lastName)) contact.lastName = id.lastName;
  if (!_blank(id.companyName)) contact.companyName = id.companyName;
  if (!_blank(id.domain)) contact.companyDomain = id.domain;

  if (Object.keys(contact).length === 0) {
    return { contacts: [] };
  }

  const revealed = lushaReveal(missingFields);
  // §6: an empty reveal is an invalid request — default to the minimal non-empty set.
  const reveal = revealed.length ? revealed : ["emails"];

  return { contacts: [contact], reveal };
}

// lushaCompanyBody(identityKeys) -> the v3 POST /v3/companies/search-and-enrich request
// body. domain ONLY (docs/LUSHA-V3-CONTRACT.md §5) — BUG 17 established live that
// `companyName` 400s this lane ("property companyName should not exist" on the retired
// v2 endpoint), and the v3 probe's winning body (§5) confirms `domain` is still the only
// accepted identity property. No `reveal` key: §5/§6 confirm the companies lane exposes
// no `has`/`canReveal` structure at all — there is no reveal mechanism to derive one for.
function lushaCompanyBody(identityKeys) {
  const id = identityKeys || {};
  if (_blank(id.domain)) {
    return { companies: [] };
  }
  return { companies: [{ domain: id.domain }] };
}

module.exports = {
  LUSHA_REVEAL_BY_FIELD,
  lushaReveal,
  lushaContactBody,
  lushaCompanyBody,
};
