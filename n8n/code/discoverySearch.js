// n8n/code/discoverySearch.js — provider search-by-role request builder and response
// normaliser for the discovery lane (Phase 73.1 Plan 07/09, D-06/D-11/D-11a/D-11b/D-12).
//
// [observed live 2026-09-18, D-12 rounds 2-4] — ZoomInfo-only, per the operator's D-12
// ruling (73.1-D12-VERDICT.json's own `operator_ruling`, recorded 2026-09-18):
// "ZoomInfo retained as tier-2 source, others (Apollo/Lusha) dropped for search phase.
// Full waterfall only used on enrich." This module used to also build Apollo and Lusha
// discovery-search request bodies; both are DELETED here, not disabled, because the
// probe found neither one a usable search-preview source on this account:
//   - Apollo (round 4, tennis.com.au, 888 total_entries): every preview item's own name
//     field is `last_name_obfuscated`, never a real `last_name` — Apollo will not hand
//     back a person's full name on a bare search, only on a paid reveal, which D-12
//     keeps out of this lane entirely.
//   - Lusha (round 4, same domain, 1313 totalResults, 1 credit charged per REQUEST even
//     for a subsequent round returning zero results): the search preview carries no
//     name and no title at all (`contactId`, `companyId`, `companyName`, `fqdn`, `has*`
//     flags, `isShown` only) — a name/title needs `/prospecting/contact/enrich`, a
//     second, more expensive call this lane does not make.
//   - ZoomInfo (round 4, same domain, 1094 totalResults, 0 credits charged across
//     rounds 2-4): the preview DOES carry `firstName`/`lastName`/`jobTitle` directly,
//     with no reveal fields (no email/phone value, only `has*` boolean flags) and no
//     measured cost — the only provider of the three actually usable as a free-preview
//     discovery source.
// Stage 2's existing enrich path keeps the full ZoomInfo -> Apollo -> Lusha waterfall
// unchanged (CLAUDE.md's provider adapter contract, §16) — this narrowing is scoped to
// the discovery (search) lane only.
//
// scripts/probe_provider_discovery.py (plan 09) derives ZoomInfo's request body and URL
// from THIS module's `buildRequest`/`buildUrl`/`DISCOVERY_ENDPOINTS` rather than holding
// a second, driftable copy for the shipped provider. It keeps its OWN frozen copies of
// the retired Apollo/Lusha shapes for future evidence-gathering, since this module no
// longer carries them at all.
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

// ZoomInfo-only, per the D-12 operator ruling (see header comment). Round-2-corrected
// endpoint — see n8n/code/discoverySearch.js's git history / 73.1-D12-VERDICT.round1.json
// for what the original (wrong) shapes were and why they changed.
const DISCOVERY_ENDPOINTS = Object.freeze({
  zoominfo: "https://api.zoominfo.com/gtm/data/v1/contacts/search",
});

function _clampLimit(limit) {
  return Math.min(Number.isFinite(limit) ? limit : DISCOVERY_PEOPLE_CAP, DISCOVERY_PEOPLE_CAP);
}

/**
 * buildRequest(provider, opts) -> request body (POJO). `opts`: { domain, roleTitles, limit }.
 * `roleTitles` empty/absent -> the rung-2 UNFILTERED body (D-11a). Never carries an
 * already-known identity field (firstname/lastname/email/linkedinUrl) — a discovery body
 * has no already-known person in it (Task 2 Test 1). ZoomInfo's pagination is NOT part of
 * this body — see `buildUrl`. ZoomInfo is the only supported provider (D-12).
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
  throw new Error(`discoverySearch.buildRequest: unknown provider ${provider}`);
}

/**
 * buildUrl(provider, opts) -> the URL to POST `buildRequest`'s body to. `opts`: { limit }.
 * ZoomInfo's pagination is a query-string parameter. ZoomInfo is the only supported
 * provider (D-12).
 */
function buildUrl(provider, opts) {
  const o = opts || {};
  if (provider === "zoominfo") {
    const limit = _clampLimit(o.limit);
    return `${DISCOVERY_ENDPOINTS.zoominfo}?page[size]=${limit}&page[number]=1`;
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
 * "found nobody" answer, not an error. ZoomInfo is the only supported provider (D-12).
 */
function normalizeResponse(provider, body) {
  const raw = body || {};
  let rows;
  if (provider === "zoominfo") {
    rows = (Array.isArray(raw.data) ? raw.data : []).map((d) => {
      const a = (d && d.attributes) || {};
      return _person(a.firstName, a.lastName, a.jobTitle, "zoominfo");
    });
  } else {
    throw new Error(`discoverySearch.normalizeResponse: unknown provider ${provider}`);
  }
  return rows.slice(0, DISCOVERY_PEOPLE_CAP);
}

module.exports = { DISCOVERY_ENDPOINTS, DISCOVERY_PEOPLE_CAP, buildRequest, buildUrl, normalizeResponse };
