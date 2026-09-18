// n8n/code/discoverySearch.js — provider search-by-role request builders and response
// normalisers for the discovery lane (Phase 73.1 Plan 07/09, D-06/D-11/D-11a/D-11b/D-12).
//
// [ASSUMED] — round 1 of the D-12 live probe (2026-09-18, pickleballaustralia.org.au)
// found all three original shapes below WRONG:
//   - ZoomInfo 400'd: "Invalid field requested", pointer /data/attributes/companyDomain.
//   - Apollo 422'd: "This endpoint is deprecated for API callers. Please use the new
//     mixed_people/api_search endpoint."
//   - Lusha 404'd: "no Route matched with those values" at /prospecting/contacts/search.
// See .planning/phases/73.1-provider-backed-contact-discovery-as-source-tier-2/
// 73.1-D12-VERDICT.round1.json for the recorded failures. This module now carries the
// shapes documented in each vendor's own current API reference (read 2026-09-18)
// instead — still UNCONFIRMED on this account until round 2 of the probe reports.
//   - ZoomInfo: `POST /gtm/data/v1/contacts/search`, JSON:API `ContactSearch` envelope.
//     The valid company filter is `companyWebsite` (not `companyDomain`). The title
//     filter is `jobTitle`, a single string supporting `OR` (not an array). Pagination
//     is QUERY-STRING (`?page[size]=N&page[number]=1`), not a body attribute —
//     `maxResults` is not a valid ZoomInfo attribute at all.
//   - Apollo: `POST /api/v1/mixed_people/api_search` (the old `/v1/mixed_people/search`
//     is the deprecated route that 422s for every caller). `q_organization_domains_list`
//     is an array; `person_titles` is an array.
//   - Lusha: `POST /prospecting/contact/search` (singular `contact`; the plural
//     `/prospecting/contacts/search` 404s). Filters nest one level deeper than first
//     assumed: `filters.companies.include.domains` and
//     `filters.contacts.include.jobTitles`. Lusha's own response envelope for a search
//     result is still UNCONFIRMED — `normalizeResponse` tolerates either a `data[]` or a
//     `contacts[]` envelope until round 2 settles which one is real.
//
// `scripts/probe_provider_discovery.py` (plan 09) derives its request bodies and URLs
// from THIS module's `buildRequest`/`buildUrl`/`DISCOVERY_ENDPOINTS` rather than holding
// a second, driftable copy — round 1's failure mode was exactly that kind of drift made
// real. Round 2 is what resolves each shape against the live providers, disarmed.
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

// Round-1-corrected endpoints — see the header comment above for what changed and why.
const DISCOVERY_ENDPOINTS = Object.freeze({
  zoominfo: "https://api.zoominfo.com/gtm/data/v1/contacts/search",
  apollo: "https://api.apollo.io/api/v1/mixed_people/api_search",
  lusha: "https://api.lusha.com/prospecting/contact/search",
});

function _clampLimit(limit) {
  return Math.min(Number.isFinite(limit) ? limit : DISCOVERY_PEOPLE_CAP, DISCOVERY_PEOPLE_CAP);
}

/**
 * buildRequest(provider, opts) -> request body (POJO). `opts`: { domain, roleTitles, limit }.
 * `roleTitles` empty/absent -> the rung-2 UNFILTERED body (D-11a). Never carries an
 * already-known identity field (firstname/lastname/email/linkedinUrl) — a discovery body
 * has no already-known person in it (Task 2 Test 1). ZoomInfo's pagination is NOT part of
 * this body — see `buildUrl`.
 */
function buildRequest(provider, opts) {
  const o = opts || {};
  const domain = o.domain || null;
  const roleTitles = Array.isArray(o.roleTitles) ? o.roleTitles.filter(Boolean) : [];

  if (provider === "zoominfo") {
    // JSON:API family. `companyWebsite` (not `companyDomain`); `jobTitle` is a single
    // OR-joined string (not an array); no `maxResults` — pagination is query-string only.
    const attributes = { companyWebsite: domain };
    if (roleTitles.length) attributes.jobTitle = roleTitles.join(" OR ");
    return { data: { type: "ContactSearch", attributes } };
  }
  if (provider === "apollo") {
    const limit = _clampLimit(o.limit);
    const body = { q_organization_domains_list: [domain], per_page: limit, page: 1 };
    if (roleTitles.length) body.person_titles = roleTitles;
    return body;
  }
  if (provider === "lusha") {
    const limit = _clampLimit(o.limit);
    const body = {
      filters: { companies: { include: { domains: [domain] } } },
      pages: { page: 0, size: limit },
    };
    if (roleTitles.length) body.filters.contacts = { include: { jobTitles: roleTitles } };
    return body;
  }
  throw new Error(`discoverySearch.buildRequest: unknown provider ${provider}`);
}

/**
 * buildUrl(provider, opts) -> the URL to POST `buildRequest`'s body to. `opts`: { limit }.
 * ZoomInfo's pagination is a query-string parameter (round 1 correction); Apollo and
 * Lusha are the bare endpoint.
 */
function buildUrl(provider, opts) {
  const o = opts || {};
  if (provider === "zoominfo") {
    const limit = _clampLimit(o.limit);
    return `${DISCOVERY_ENDPOINTS.zoominfo}?page[size]=${limit}&page[number]=1`;
  }
  if (provider === "apollo" || provider === "lusha") {
    return DISCOVERY_ENDPOINTS[provider];
  }
  throw new Error(`discoverySearch.buildUrl: unknown provider ${provider}`);
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
    // [ASSUMED] response envelope -- round 1 never reached a 2xx to observe it (404
    // before any body was returned). Tolerate either shape until round 2 settles it.
    const items = Array.isArray(raw.data) ? raw.data
      : (Array.isArray(raw.contacts) ? raw.contacts : []);
    rows = items.map((c) => {
      const first = (c && (c.firstName || (c.name && c.name.first))) || null;
      const last = (c && (c.lastName || (c.name && c.name.last))) || null;
      return _person(first, last, c && c.jobTitle, "lusha");
    });
  } else {
    throw new Error(`discoverySearch.normalizeResponse: unknown provider ${provider}`);
  }
  return rows.slice(0, DISCOVERY_PEOPLE_CAP);
}

module.exports = { DISCOVERY_ENDPOINTS, DISCOVERY_PEOPLE_CAP, buildRequest, buildUrl, normalizeResponse };
