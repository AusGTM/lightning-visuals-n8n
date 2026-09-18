// n8n/code/discoverySearch.js — provider search-by-role request builders and response
// normalisers for the discovery lane (Phase 73.1 Plan 07, D-06/D-11/D-11a/D-11b/D-12).
//
// [ASSUMED] — every endpoint and body shape below is UNCONFIRMED. No search-by-role-title
// endpoint has ever been called live in this repository. Every currently-wired provider
// endpoint in this codebase (Apollo `/v1/people/match`, ZoomInfo
// `/gtm/data/v1/contacts/enrich`, Lusha `/v3/contacts/search-and-enrich`) requires an
// already-known identity and CANNOT answer "who works at this company with this title".
//   - ZoomInfo: `/gtm/data/v1/companies/search` is the one CONFIRMED-LIVE search shape in
//     this codebase (memory `zoominfo-gtm-companies-contract`, docs). The contacts-search
//     URL/body below is INFERRED from it by JSON:API family (`ContactSearch` type), never
//     observed.
//   - Apollo: the people-search endpoint and its `person_titles` parameter are from vendor
//     documentation only; this account's Apollo API key is not a master key and its
//     balance already reads 403/unreadable on the confirmed-live usage endpoint
//     (memory `provider-credit-check-endpoints`) — whether search fares any better is
//     unknown.
//   - Lusha: the prospecting/search product is NOT documented in
//     `docs/LUSHA-V3-CONTRACT.md` at all (that contract covers `/v3/contacts/enrich` and
//     `/v3/contacts/search-and-enrich` only, both identity-based) and may not be entitled
//     on this plan's Lusha account.
// `scripts/probe_provider_discovery.py` (plan 09) is what resolves each one against the
// live providers, disarmed, before any credit is spent. Until then this module is built
// and tested entirely behind offline fixtures (D-12's stated assumption).
//
// D-12: SEARCH-ONLY. `normalizeResponse` never carries an email or a phone field, however
// generous a fixture provider response would be — reveal stays in stage 2's existing
// enrich path (CLAUDE.md's provider adapter contract, §16).
//
// NO npm, dependency-free (no CommonJS/ESM module-loading statement in the body below) —
// this module is inline()'d verbatim into n8n Code nodes by
// scripts/build_cloud_workflows.py, mirroring n8n/code/lushaRequest.js's own convention.

// D-11a: at most 10 results per provider per company, applied inside normalizeResponse
// BEFORE anything else sees them (Task 2 acceptance criterion) — never left to a caller.
const DISCOVERY_PEOPLE_CAP = 10;

// [ASSUMED] endpoints — see the header comment above for what is and is not known about
// each one. Named constants, not inlined literals, so scripts/probe_provider_discovery.py
// (plan 09) has exactly one place to correct per provider once the live probe reports.
const DISCOVERY_ENDPOINTS = Object.freeze({
  zoominfo: "https://api.zoominfo.com/gtm/data/v1/contacts/search",
  apollo: "https://api.apollo.io/v1/mixed_people/search",
  lusha: "https://api.lusha.com/prospecting/contacts/search",
});

/**
 * buildRequest(provider, opts) -> request body (POJO). `opts`: { domain, roleTitles, limit }.
 * `roleTitles` empty/absent -> the rung-2 UNFILTERED body (D-11a). Never carries an
 * already-known identity field (firstname/lastname/email/linkedinUrl) — a discovery body
 * has no already-known person in it (Task 2 Test 1).
 */
function buildRequest(provider, opts) {
  const o = opts || {};
  const domain = o.domain || null;
  const roleTitles = Array.isArray(o.roleTitles) ? o.roleTitles.filter(Boolean) : [];
  const limit = Math.min(Number.isFinite(o.limit) ? o.limit : DISCOVERY_PEOPLE_CAP,
                          DISCOVERY_PEOPLE_CAP);

  if (provider === "zoominfo") {
    // JSON:API family, per the confirmed-live companies/search shape.
    const attributes = { companyDomain: domain, maxResults: limit };
    if (roleTitles.length) attributes.jobTitle = roleTitles;
    return { data: { type: "ContactSearch", attributes } };
  }
  if (provider === "apollo") {
    const body = { q_organization_domains: domain, per_page: limit };
    if (roleTitles.length) body.person_titles = roleTitles;
    return body;
  }
  if (provider === "lusha") {
    const body = { filters: { companies: { domains: [domain] } }, pages: { page: 0, size: limit } };
    if (roleTitles.length) body.filters.contacts = { jobTitles: roleTitles };
    return body;
  }
  throw new Error(`discoverySearch.buildRequest: unknown provider ${provider}`);
}

function _person(firstname, lastname, jobtitle, provider) {
  // D-12/D-11b: raw provider title only, never a role_family (classification stays
  // plugin-side, role_classify.classify_title) — and never email/phone (search-only).
  return {
    firstname: firstname || null,
    lastname: lastname || null,
    jobtitle: jobtitle || null,
    provider,
  };
}

/**
 * normalizeResponse(provider, body) -> array of uniform person shapes, capped at
 * DISCOVERY_PEOPLE_CAP regardless of how many the fixture/response carries (Task 2
 * Test 5). Never throws on a missing/empty result list — an empty array is a legitimate
 * "found nobody" answer, not an error.
 */
function normalizeResponse(provider, body) {
  const raw = body || {};
  let rows;
  if (provider === "zoominfo") {
    rows = (Array.isArray(raw.data) ? raw.data : []).map((d) => {
      const a = (d && d.attributes) || {};
      return _person(a.firstName, a.lastName, a.jobTitle, "zoominfo");
    });
  } else if (provider === "apollo") {
    rows = (Array.isArray(raw.people) ? raw.people : []).map((p) =>
      _person(p && p.first_name, p && p.last_name, p && p.title, "apollo"));
  } else if (provider === "lusha") {
    rows = (Array.isArray(raw.contacts) ? raw.contacts : []).map((c) =>
      _person(c && c.firstName, c && c.lastName, c && c.jobTitle, "lusha"));
  } else {
    throw new Error(`discoverySearch.normalizeResponse: unknown provider ${provider}`);
  }
  return rows.slice(0, DISCOVERY_PEOPLE_CAP);
}

module.exports = { DISCOVERY_ENDPOINTS, DISCOVERY_PEOPLE_CAP, buildRequest, normalizeResponse };
