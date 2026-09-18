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

// 73.1-09 Task 3 follow-through (execution 12666, 2026-09-18): ZoomInfo's own 400
// (PFAPI0006, pointer /data/attributes/jobTitle) says "jobTitle must be less than 500
// characters" -- a real 42-title role vocabulary OR-joins to 757 chars, so rung 1 could
// never have succeeded as originally built. The vendor says "less than", so the cap is
// applied strictly (< 500, never <=).
const ZOOMINFO_JOBTITLE_MAX = 500;

/**
 * capRoleTitles(titles, max) -> { joined, used, dropped }. Greedily OR-joins titles in
 * list order, stopping BEFORE the joined string would reach `max` chars -- a title is
 * kept whole or not at all, never split mid-string. `used` is the array of titles that
 * made it in (order preserved); `dropped` is a count, not a list (nobody downstream needs
 * to know WHICH titles were cut, only how many).
 */
function capRoleTitles(titles, max) {
  const cap = Number.isFinite(max) ? max : ZOOMINFO_JOBTITLE_MAX;
  const list = Array.isArray(titles) ? titles.filter(Boolean) : [];
  const used = [];
  let joined = "";
  for (const t of list) {
    const next = joined ? `${joined} OR ${t}` : t;
    if (next.length >= cap) break;
    joined = next;
    used.push(t);
  }
  return { joined, used, dropped: list.length - used.length };
}

/**
 * titlesForFamilies(familyMap, chosen) -> array of member strings (D-11a). `familyMap` is a
 * plain object of label -> array of member strings (build-time config, e.g.
 * scripts/build_cloud_workflows.py's `_discovery_role_family_map()`). `chosen` is the
 * round's selected family LABELS, operator order preserved -- when non-empty, walks
 * `chosen` in order and appends each named family's members (deduped across families,
 * first occurrence wins); a label absent from `familyMap` contributes nothing and never
 * throws -- the plugin already validates labels against this same vocabulary
 * (role_classify.chosen_families), so this function must not be a second validator.
 * Empty/absent/null `chosen` falls back to every member in map insertion order -- the
 * pre-D-11a build-time behaviour, preserved as the fallback for a caller that omits the
 * field entirely.
 */
function titlesForFamilies(familyMap, chosen) {
  const map = (familyMap && typeof familyMap === "object") ? familyMap : {};
  const labels = (Array.isArray(chosen) && chosen.length) ? chosen : Object.keys(map);
  const seen = new Set();
  const out = [];
  for (const label of labels) {
    const members = Array.isArray(map[label]) ? map[label] : [];
    for (const m of members) {
      if (!seen.has(m)) {
        seen.add(m);
        out.push(m);
      }
    }
  }
  return out;
}

/**
 * unknownFamilyLabels(familyMap, chosen) -> array of `chosen` labels absent from
 * `familyMap`, caller order preserved, deduped. Never throws. WR-03 (73.1-REVIEW.md):
 * `titlesForFamilies` deliberately never signals an unrecognized label (that stays a
 * silent zero-contribution, by design -- see its own docstring), which left a
 * stale/misspelled `role_families` entry indistinguishable from "operator genuinely
 * wants an unfiltered search". This companion function lets a caller (the rung-1 leaf)
 * echo which requested labels did NOT resolve, without changing `titlesForFamilies`'s
 * own pinned return shape. Empty/absent `chosen` returns [] -- the fallback-to-
 * everything case is not an unknown-label situation.
 */
function unknownFamilyLabels(familyMap, chosen) {
  const map = (familyMap && typeof familyMap === "object") ? familyMap : {};
  const labels = Array.isArray(chosen) ? chosen : [];
  const seen = new Set();
  const out = [];
  for (const label of labels) {
    if (!(label in map) && !seen.has(label)) {
      seen.add(label);
      out.push(label);
    }
  }
  return out;
}

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
    if (roleTitles.length) {
      const { joined } = capRoleTitles(roleTitles, ZOOMINFO_JOBTITLE_MAX);
      if (joined) attributes.jobTitle = joined;
    }
    return { data: { type: "ContactSearch", attributes } };
  }
  throw new Error(`discoverySearch.buildRequest: unknown provider ${provider}`);
}

/**
 * buildUrl(provider, opts) -> the bare URL to POST `buildRequest`'s body to, with NO
 * query string embedded (73.1-11 Task 3, execution 12670: the discovery lane's live
 * rung-1 400'd inside n8n on a literal-bracket query string appended to this URL,
 * while the byte-identical request succeeded outside n8n via a direct Python replay --
 * isolating the query string itself, not the account, credential, or request body, as
 * the live-vs-offline discrepancy). ZoomInfo is the only supported provider (D-12).
 * Pagination is now `buildQuery`'s job, passed via the httpRequest node's own `qs`
 * option so n8n's own query-string serializer builds it, never a hand-joined string.
 */
function buildUrl(provider, opts) {
  const o = opts || {};
  if (provider === "zoominfo") {
    void o;
    return DISCOVERY_ENDPOINTS.zoominfo;
  }
  throw new Error(`discoverySearch.buildUrl: unknown provider ${provider}`);
}

/**
 * buildQuery(provider, opts) -> the query-string parameters object for `buildUrl`'s
 * endpoint, passed to `this.helpers.httpRequest`'s `qs` option (73.1-11 Task 3).
 * `opts`: { limit }. ZoomInfo is the only supported provider (D-12).
 */
function buildQuery(provider, opts) {
  const o = opts || {};
  if (provider === "zoominfo") {
    const limit = _clampLimit(o.limit);
    return { "page[size]": limit, "page[number]": 1 };
  }
  throw new Error(`discoverySearch.buildQuery: unknown provider ${provider}`);
}

/**
 * extractErrorDetail(e) -> a short string of the vendor's own JSON:API error detail
 * (code/title/detail/source.pointer from `errors[0]`), when the caught exception's
 * response body is readable -- 73.1-11 Task 3's diagnostic gap: the rung leaf used to
 * keep only `e.message`, discarding whatever the vendor actually said. Never returns
 * the raw response body/object whole -- an error body can echo the outbound request's
 * own Authorization header back (the ingest lane's create-error-path rule, applied to
 * this read path too). Returns null on any shape it cannot read -- never throws.
 */
function extractErrorDetail(e) {
  if (!e) return null;
  let data = (e.response && e.response.data)
    || (e.cause && e.cause.response && e.cause.response.data);
  if (typeof data === "string") {
    try { data = JSON.parse(data); } catch (_err) { return null; }
  }
  if (!data || typeof data !== "object") return null;
  const errors = Array.isArray(data.errors) ? data.errors : [];
  const first = errors[0];
  if (!first || typeof first !== "object") return null;
  const parts = [];
  if (first.code) parts.push(`code=${first.code}`);
  if (first.title) parts.push(`title=${first.title}`);
  if (first.detail) parts.push(`detail=${first.detail}`);
  if (first.source && first.source.pointer) parts.push(`pointer=${first.source.pointer}`);
  return parts.length ? parts.join(" ").slice(0, 400) : null;
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

module.exports = {
  DISCOVERY_ENDPOINTS, DISCOVERY_PEOPLE_CAP, ZOOMINFO_JOBTITLE_MAX,
  buildRequest, buildUrl, buildQuery, normalizeResponse, capRoleTitles, titlesForFamilies,
  unknownFamilyLabels, extractErrorDetail,
};
