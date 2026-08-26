// normalizeProviders.js — pure-JS provider-response → common candidate shape.
//
// toCandidates(providerName, rawResponse, objectType) flattens ONE provider's raw
// API response into an array of common-shape candidates, one per usable field:
//   { field, source, value, normalizedValue, accuracy, recencyDate }
// where `field` is the canonical HubSpot property, `value` is the raw provider
// value, `normalizedValue` is the cross-check key (E.164 phone / lowercased email /
// revenue band / employee band / NAICS code), `accuracy` (0-1) is derived from the
// provider's per-field quality signal (see ENRICHMENT-WORKFLOW-PLAN.md §2 A-table),
// and `recencyDate` is the field's freshness date for the recency term.
//
// NO npm. Reuses normalizePhoneAU / normalizeEmailBasic from siblings. Revenue and
// employee band normalizers are local (mirror src/normalizer.py) — small enough to
// keep here rather than import a fourth module.

const { normalizePhoneAU, normalizePhone } = require("./normalizePhone");
const { normalizeEmailBasic } = require("./normalizeEmail");

// Country NAME -> ISO2 (Apollo returns names like "United States"; Lusha gives country_iso2
// directly). Unmapped -> undefined, so normalizePhone falls back to its AU heuristic.
const _COUNTRY_ISO2 = {
  australia: "AU", "new zealand": "NZ", "united states": "US", "united states of america": "US",
  canada: "CA", "united kingdom": "GB", "great britain": "GB", england: "GB", ireland: "IE",
  india: "IN", singapore: "SG",
};
function _iso2(nameOrCode) {
  if (!nameOrCode) return undefined;
  const v = String(nameOrCode).trim();
  if (/^[A-Za-z]{2}$/.test(v)) return v.toUpperCase();  // already ISO2
  return _COUNTRY_ISO2[v.toLowerCase()];
}

// 260826-20w Task 2: hs_country_region_code / hs_state_code candidates are derived ONLY
// from a value that is ALREADY code-shaped (an ISO2 country code, a 2-3 char state
// abbreviation) — deliberately NOT a name->code lookup table. Task 1's live sample found
// Apollo returns full names for both ("New South Wales", "Australia") 100% of the time it
// returns anything at all, and Lusha has no `state` field whatsoever — so a name-lookup
// table here would either be untestable against real traffic or duplicate the existing
// (deliberately narrower) `_iso2` name map that phone normalization owns. Returns the
// UPPERCASED code, or null when the value is not already code-shaped (a full name never
// produces a candidate).
function _codeShaped(value, minLen, maxLen) {
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  return new RegExp(`^[A-Za-z]{${minLen},${maxLen}}$`).test(s) ? s.toUpperCase() : null;
}

// ---- local value normalizers (mirror src/normalizer.py band logic) ----------
// Parse a revenue value (number OR range string like "10M-25M") to lower-bound
// dollars, then map to the CLAUDE.md revenue bands. Range strings use the LOWER
// bound so "10M-25M" -> 5-50M, "50M-100M" -> 50-500M.
function _revenueToDollars(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return value;
  const s = String(value);
  const m = s.match(/([\d.]+)\s*([kmb]?)/i); // first magnitude
  if (!m) return null;
  let n = parseFloat(m[1]);
  if (Number.isNaN(n)) return null;
  const unit = (m[2] || "").toLowerCase();
  if (unit === "k") n *= 1e3;
  else if (unit === "m") n *= 1e6;
  else if (unit === "b") n *= 1e9;
  return n;
}

function normalizeRevenueBand(value) {
  const v = _revenueToDollars(value);
  if (v === null) return null;
  // ZERO IS NO-DATA, NOT A BAND. Apollo returns `organization_revenue: 0.0` (a number,
  // not null) for every company it has no revenue figure for — confirmed live against
  // mrc.racing.com, whose HubSpot record already carries annualrevenue 206,078,000.
  // Banding that 0 as "<1M" is worse than saying nothing: "<1M" scores 0 ICP points
  // where the truthful "50-500M" scores +10, so a missing figure silently reads as a
  // disqualifying one. Guarded here rather than at the Apollo call site because
  // ZoomInfo's `revenue * 1000` collapses to 0 the same way. Downstream, a null band is
  // dropped by Merge Company's `v != null` candidate filter — no candidate is emitted.
  if (v <= 0) return null;
  if (v < 1e6) return "<1M";
  if (v < 5e6) return "1-5M";
  if (v < 50e6) return "5-50M";
  if (v < 500e6) return "50-500M";
  if (v < 750e6) return "500-750M";
  if (v < 1e9) return "750M-1B";
  if (v < 1.2e9) return "1B-1.2B";
  return "1.2B+";
}

function normalizeEmployeeBand(value) {
  if (value === null || value === undefined || value === "") return null;
  // Already a band string (e.g. ZoomInfo employeeRange "201-500") -> pass through, with
  // whitespace around the hyphen collapsed: live Lusha returns "51 - 200", and the spaced
  // form is NOT an lv_employee_band enum value ("51-200" is).
  if (typeof value === "string" && !/^\d+$/.test(value.trim())) {
    return value.trim().replace(/\s*-\s*/g, "-");
  }
  const v = parseInt(value, 10);
  if (Number.isNaN(v)) return null;
  // Same zero-is-no-data rule as normalizeRevenueBand: a headcount of 0 is a provider
  // saying "unknown", never a real company, and "1-9" is a lie that reads as a real
  // (tiny) size to the scorer.
  if (v <= 0) return null;
  if (v <= 9) return "1-9";
  if (v <= 50) return "10-50";
  if (v <= 200) return "51-200";
  if (v <= 500) return "201-500";
  if (v <= 1000) return "501-1000";
  return "1001+";
}

// 58-05 Task 2: guard for the native `numberofemployees` candidate — HubSpot's property is
// a NUMBER, and Lusha's/ZoomInfo's headcount fallbacks are SPACED RANGE STRINGS ("51 - 200",
// "10 - 20") that normalizeEmployeeBand happily accepts for the band enum but that would be
// a fabricated point-estimate if parsed into a single number (CLAUDE.md T-58-21). A
// candidate is admitted ONLY from a value that is already numeric — never parsed, rounded,
// or endpoint-taken from a range. Also rejects <= 0, mirroring normalizeEmployeeBand's own
// zero-is-no-data rule (a provider's 0 means "unknown", never a real company of size zero).
function _numericHeadcount(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value
    : (/^\d+(\.\d+)?$/.test(String(value).trim()) ? Number(value) : NaN);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function normalizeCountryRegion(value) {
  if (!value) return null;
  const v = String(value).trim().toLowerCase();
  if (["australia", "au", "aus"].includes(v)) return "AU";
  if (["new zealand", "nz"].includes(v)) return "NZ";
  return "Other";
}

function _clamp01(n) {
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

// ---- per-provider accuracy helpers (ENRICHMENT-WORKFLOW-PLAN.md §2) ---------
const APOLLO_EMAIL_A = { verified: 1.0, guessed: null, pending: 0.3, unavailable: 0, bounced: 0 };

function apolloEmailAccuracy(raw) {
  const status = raw.email_status;
  let a;
  if (status === "guessed") {
    // guessed = 0.5 * extrapolated_confidence (default confidence 1.0 when absent).
    let ex = raw.extrapolated_email_confidence;
    if (ex === null || ex === undefined) ex = 1.0;
    if (ex > 1) ex = ex / 100; // tolerate 0-100 scale
    a = 0.5 * ex;
  } else {
    a = APOLLO_EMAIL_A[status];
    if (a === null || a === undefined) a = 0; // unknown status -> no trust
  }
  if (raw.email_domain_catchall) a *= 0.6; // catchall penalty
  return _clamp01(a);
}

const LUSHA_EMAIL_CONF = { "A+": 1.0, A: 0.8 };
function lushaEmailAccuracy(e) {
  // Live v2 email item uses emailConfidence/emailType; flat fixtures use confidence/type.
  const conf = e.confidence != null ? e.confidence : e.emailConfidence;
  const type = e.type != null ? e.type : e.emailType;
  let a = LUSHA_EMAIL_CONF[conf];
  if (a === null || a === undefined) a = 0.4; // null/unknown grade
  if (type && String(type).toLowerCase() !== "work") a *= 0.8; // private/personal
  return _clamp01(a);
}

// ---- provider mappers -------------------------------------------------------
function _push(out, field, source, value, normalizedValue, accuracy, recencyDate) {
  if (value === null || value === undefined || value === "") return;
  out.push({ field, source, value, normalizedValue, accuracy: _clamp01(accuracy), recencyDate: recencyDate || null });
}

// Prefer human-readable industry text over a raw NAICS code; a bare numeric code is never
// a valid `industry` text value (NORM-01). Precedence: the NAICS entry's own `.name` text
// when the entry is an object carrying one; otherwise the provider's industry text fallback
// (first element when the fallback is an array); otherwise null — no candidate is fabricated
// from a bare code.
function _industryText(naicsEntry, textFallback) {
  if (naicsEntry && typeof naicsEntry === "object" && naicsEntry.name) {
    return { raw: naicsEntry.name, key: _norm(naicsEntry.name) };
  }
  const fallback = Array.isArray(textFallback) ? textFallback[0] : textFallback;
  if (fallback) return { raw: fallback, key: _norm(fallback) };
  return null; // bare numeric code, no name, no fallback text -> skip, don't fabricate
}

// COPY-02 (18-VERIFICATION.md GAP 2, D-GAP2-provider/D-GAP2-othervalue): a provider's OWN
// department field, when present, is the persona_group producer -- no invented title-to-
// persona taxonomy. Takes the first element when the value is an array. Lusha's live
// "Other" label is a semantically-empty non-signal (case-insensitive compare) -- a
// persona group of "Other" is not a classification, it renders in a HubSpot view as
// though a decision were made when none was, which is strictly worse for the RevOps
// reviewer than the property staying blank. Returns null rather than fabricating a value
// from a non-value, mirroring _industryText's contract.
function _personaGroup(departments) {
  const first = Array.isArray(departments) ? departments[0] : departments;
  if (!first) return null;
  if (String(first).trim().toLowerCase() === "other") return null;
  return first;
}

// _lushaRecord(rawResponse, objectType) -- Lusha envelope adapter, sibling to _zoomRecord().
// The v3 Enrichment API (the live contract as of 2026-07-30, confirmed against a real
// api.lusha.com session and recorded in docs/LUSHA-V3-CONTRACT.md) is a flat
// { requestId, results: [...], billing } envelope, positionally aligned with the request's
// single-item array (this waterfall sends one identity per call, so results[0] is safe with
// no match-back key). A per-result `error` (no-match/error shape, contract §9), a missing or
// non-array `results`, a non-object input and a null input all resolve to {} -- zero
// candidates, never a throw (skip-not-retry, CLAUDE.md Sec 26.1). v2's envelope handling
// (a plural contactId-keyed `{contacts:{...}}` map and a singular `{contact:{data}}}` form)
// was retired in this phase (Plan 20-03) ahead of v2's 2026-11-18 sunset -- no v2-shaped
// response can reach this function once Plan 05's redeploy ships.
//
// v3 field names already match the intermediate shape the extraction logic below reads
// (emails[].email/.type/.confidence, phones[].number/.type/.doNotCall, jobTitle.title/
// .seniority/.departments) for CONTACTS, so _lushaV3Contact only renames the one field that
// differs: location.countryIso2 (v3, camelCase) -> location.country_iso2 (the snake_case key
// the extraction's region lookup reads). For COMPANIES, v3's revenueRange/employeeCount ship
// as {min,max}/{exact,min,max} objects rather than the [lo,hi] array or plain number the
// extraction expects, and industry classification is a flat `industry` string rather than
// naicsCodes -- _lushaV3Company does that reshaping.
function _lushaV3Contact(entry) {
  const loc = entry.location || {};
  return {
    id: entry.id,
    emails: entry.emails,
    phones: entry.phones,
    jobTitle: entry.jobTitle,
    location: { ...loc, country_iso2: loc.countryIso2 },
    updateDate: entry.updateDate,
  };
}

function _lushaV3Company(entry) {
  const rr = entry.revenueRange;
  const revenueRange = rr && typeof rr === "object" && !Array.isArray(rr) ? [rr.min, rr.max] : rr;
  let ec = entry.employeeCount;
  if (ec && typeof ec === "object") {
    ec = ec.exact != null ? ec.exact
      : (ec.min != null && ec.max != null ? Math.round((ec.min + ec.max) / 2) : null);
  }
  return {
    id: entry.id,
    revenueRange,
    employeeCount: ec,
    mainIndustry: entry.industry,
    location: entry.location,
    updateDate: entry.updateDate,
  };
}

function _lushaRecord(rawResponse, objectType) {
  const raw = rawResponse;
  if (!raw || typeof raw !== "object") return {};

  if (Array.isArray(raw.results)) {
    const entry = raw.results[0];
    if (!entry || typeof entry !== "object" || entry.error) return {};
    return objectType === "companies" ? _lushaV3Company(entry) : _lushaV3Contact(entry);
  }

  // Bare/flat fallback: offline unit tests pass a record's fields directly with no envelope
  // at all (e.g. `{ phones: [...] }`). Not a v2 envelope shape -- v3 has no wrapper either
  // once unwrapped above, so this is the same pass-through both versions relied on.
  return raw;
}

function lushaCandidates(rawResponse, objectType) {
  const out = [];
  const src = "lusha";
  const raw = _lushaRecord(rawResponse, objectType) || {};
  const updated = raw.updateDate;
  const region = raw.location && (raw.location.country_iso2 || raw.location.country); // ISO2 or name
  if (objectType === "contacts") {
    // Live: emailAddresses/phoneNumbers with emailType/phoneType; fixtures: emails/phones with type.
    for (const e of raw.emailAddresses || raw.emails || []) {
      _push(out, "email", src, e.email, normalizeEmailBasic(e.email), lushaEmailAccuracy(e), e.updateDate || updated);
    }
    for (const p of raw.phoneNumbers || raw.phones || []) {
      if (p.doNotCall) continue; // suppress (not just downscore) per §2
      const norm = normalizePhone(p.number, _iso2(region));
      if (!norm) continue; // null-drop: un-normalizable phone never reaches HubSpot
      const t = String(p.phoneType || p.type || "").toLowerCase();
      const acc = t === "mobile" || t === "direct" ? 0.8 : 0.5;
      const field = t === "mobile" ? "mobilephone" : "phone";
      _push(out, field, src, p.number, norm, acc, p.updateDate || updated);
    }
    if (raw.jobTitle) {
      // No per-field grade for Lusha title -> ungraded base 0.6.
      _push(out, "jobtitle", src, raw.jobTitle.title, _norm(raw.jobTitle.title), 0.6, updated);
      _push(out, "seniority", src, raw.jobTitle.seniority, _norm(raw.jobTitle.seniority), 0.6, updated);
      // COPY-02: persona_group producer, reading Lusha's own department field off the
      // same jobTitle object the block already destructures. Unprefixed field name here
      // (read-side key, mirrors seniority/jobtitle above) -- the PN-1 lv_ rename happens
      // only at the merge/canonical-write boundary, which this file never touches.
      const persona = _personaGroup(raw.jobTitle.departments);
      _push(out, "persona_group", src, persona, _norm(persona), 0.6, updated);
    }
    // 260826-20w Task 2 commit 1: five HubSpot-native contact location properties.
    // Lusha v3 contacts (_lushaV3Contact) carry location.{city,country,countryIso2,
    // state?} (countryIso2 renamed to country_iso2 above) — city/country observed live
    // (execs 11935/37/48/56: "Sydney"/"Australia"); `state` has never been observed
    // present on a live contact or in the offline fixture. `country_iso2` is a DEDICATED
    // code field (distinct from the free-text `country` name), guaranteed code-shaped by
    // Lusha's own contract, so it feeds hs_country_region_code directly. No name->code
    // lookup for hs_state_code — Lusha never supplies a state value to begin with.
    const loc = raw.location || {};
    _push(out, "city", src, loc.city, _norm(loc.city), 0.6, updated);
    _push(out, "state", src, loc.state, _norm(loc.state), 0.6, updated);
    _push(out, "country", src, loc.country, _norm(loc.country), 0.6, updated);
    const lushaCountryCode = _codeShaped(loc.country_iso2, 2, 2);
    if (lushaCountryCode) {
      _push(out, "hs_country_region_code", src, loc.country_iso2, lushaCountryCode, 0.6, updated);
    }
    const lushaStateCode = _codeShaped(loc.state, 2, 3);
    if (lushaStateCode) {
      _push(out, "hs_state_code", src, loc.state, lushaStateCode, 0.6, updated);
    }
  } else {
    // company firmographics — no per-field grade -> base 0.6. `raw.company` serves the
    // contacts/person endpoint's nested company object (extraction, not envelope -- kept
    // regardless of envelope version); the retired v2 `/v2/company` `data`-wrapper term was
    // dropped here in Plan 20-03 Task 3 (docs/LUSHA-V3-CONTRACT.md §5 confirms v3's companies
    // response is flat, no `data` key). `raw` itself is the v3 adapter's own flat output.
    const co = raw.company || raw;
    const rev = Array.isArray(co.revenueRange) ? co.revenueRange[0] : co.revenueRange;
    _push(out, "lv_revenue_band", src, rev, normalizeRevenueBand(rev), 0.6, updated);
    // Live /v2/company returns the headcount as `employees` ("51 - 200", a spaced range
    // string); companySize/employeeCount are null there and only appear in the fixtures.
    const emp = Array.isArray(co.companySize)
      ? co.companySize[co.companySize.length - 1]
      : (co.companySize != null ? co.companySize
        : (co.employeeCount != null ? co.employeeCount : co.employees));
    _push(out, "lv_employee_band", src, emp, normalizeEmployeeBand(emp), 0.6, updated);
    // 58-05 Task 2: native `numberofemployees` candidate — SAME `emp` value as the band
    // above, but admitted only when already numeric (_numericHeadcount rejects the
    // "51 - 200" spaced-range shape the /v2/company legacy fallback comment above
    // documents; live v3 execs 11929/11932/11975/11979 all carried a plain number here
    // via _lushaV3Company's employeeCount reshaping, so the guard has never fired live).
    const empCount = _numericHeadcount(emp);
    _push(out, "numberofemployees", src, empCount, empCount, 0.6, updated);
    const naics0 = (co.naicsCodes || [])[0];
    const industry = _industryText(naics0, co.mainIndustry);
    _push(out, "industry", src, industry && industry.raw, industry && industry.key, 0.6, updated);
    const country = (co.location && co.location.countryIso2) || co.countryIso2;
    _push(out, "lv_country_region_normalized", src, country, normalizeCountryRegion(country), 0.6, updated);
    // 58-05 Task 1: native `country` candidate — the human-readable name already present
    // alongside the ISO2 code the lv_* derivation above uses (live evidence execs
    // 11932/11979: co.location.{country:"Australia", countryIso2:"AU"} both present).
    // Matches the shape the portal's `country` property already holds on real records
    // (checked live: MRC/ATC/Newcastle Jockey Club etc. all carry "Australia", never "AU").
    const countryName = co.location && co.location.country;
    _push(out, "country", src, countryName, _norm(countryName), 0.6, updated);
    // 58-05 Task 2: native `city` candidate — live evidence execs 11932/11979:
    // co.location.city present ("Glenwood"/"Brunswick") when Lusha matched; absent
    // (empty location) in the 2/4 sampled executions where Lusha found no match.
    const cityName = co.location && co.location.city;
    _push(out, "city", src, cityName, _norm(cityName), 0.6, updated);
  }
  return out;
}

// lushaRecordId(rawResponse, objectType) -- extracts the opaque Lusha record identifier
// (docs/LUSHA-V3-CONTRACT.md §4/§5: `results[i].id`) for Plan 04's HubSpot staging
// properties (lusha_contact_id / lusha_company_id). A deliberate SIBLING of
// lushaCandidates(), not a field inside it -- REQ-lusha-v3-normalize requires the
// candidate stream stay field-identical, so the id must never enter scoreCandidates as a
// candidate. Reuses the SAME _lushaRecord() envelope adapter Plan 03 built (a no-match, a
// per-record error, a missing/non-object entry, `{}` and `null` all resolve through that
// adapter to {} / no id). Never throws; returns null for anything that is not a non-empty
// string id.
function lushaRecordId(rawResponse, objectType) {
  try {
    const rec = _lushaRecord(rawResponse, objectType);
    const id = rec && rec.id;
    return typeof id === "string" && id.trim() !== "" ? id : null;
  } catch (e) {
    return null;
  }
}

function apolloCandidates(raw, objectType) {
  const out = [];
  const src = "apollo";
  // Live people/match nests the record under `person`; flat fixtures don't. Read
  // through `person` so both shapes work (mirrors the org fallback below).
  const person = raw.person || raw;
  const updated = person.updated_at || raw.updated_at;
  if (objectType === "contacts") {
    _push(out, "email", src, person.email, normalizeEmailBasic(person.email), apolloEmailAccuracy(person), updated);
    const region = _iso2(person.country || (person.organization && person.organization.country));
    for (const p of person.phone_numbers || []) {
      if (p.dnc_status || p.doNotCall) continue; // suppress
      const norm = normalizePhone(p.sanitized_number, region);
      if (!norm) continue; // null-drop: un-normalizable phone never reaches HubSpot
      const status = p.status || p.status_cd;
      const acc = status === "valid_number" ? 1.0 : 0.5;
      const t = String(p.type || "").toLowerCase();
      const field = t === "mobile" ? "mobilephone" : "phone";
      _push(out, field, src, p.sanitized_number, norm, acc, updated);
    }
    _push(out, "jobtitle", src, person.title, _norm(person.title), 0.6, updated);
    _push(out, "seniority", src, person.seniority, _norm(person.seniority), 0.6, updated);
    // COPY-02: same persona_group producer, reading Apollo's own department field.
    const persona = _personaGroup(person.departments);
    _push(out, "persona_group", src, persona, _norm(persona), 0.6, updated);
    // 260826-20w Task 2 commit 1: Apollo's person record carries flat city/state/country
    // (live exec 11948: "Sydney"/"New South Wales"/"Australia" — full names, no dedicated
    // ISO/code field at all). hs_country_region_code/hs_state_code candidates are only
    // emitted when the raw value already happens to be code-shaped (_codeShaped) — Task
    // 1's live sample never observed that from Apollo, so in practice these two never
    // fire from Apollo today; the tests exercise the code-shaped path with a synthetic
    // fixture to prove the logic itself.
    _push(out, "city", src, person.city, _norm(person.city), 0.6, updated);
    _push(out, "state", src, person.state, _norm(person.state), 0.6, updated);
    _push(out, "country", src, person.country, _norm(person.country), 0.6, updated);
    const apolloCountryCode = _codeShaped(person.country, 2, 2);
    if (apolloCountryCode) {
      _push(out, "hs_country_region_code", src, person.country, apolloCountryCode, 0.6, updated);
    }
    const apolloStateCode = _codeShaped(person.state, 2, 3);
    if (apolloStateCode) {
      _push(out, "hs_state_code", src, person.state, apolloStateCode, 0.6, updated);
    }
  } else {
    const org = (raw.person && raw.person.organization) || raw.organization || raw.org || raw;
    // Live org revenue is `organization_revenue` (number); flat fixtures use `annual_revenue`.
    const revenue = org.annual_revenue != null ? org.annual_revenue : org.organization_revenue;
    _push(out, "lv_revenue_band", src, revenue, normalizeRevenueBand(revenue), 0.6, updated);
    _push(out, "lv_employee_band", src, org.estimated_num_employees, normalizeEmployeeBand(org.estimated_num_employees), 0.6, updated);
    // 58-05 Task 2: native `numberofemployees` candidate — SAME org.estimated_num_employees
    // value as the band above, guarded through _numericHeadcount for parity with the other
    // two branches even though Apollo's own field is already a plain integer (live evidence
    // execs 11929/11932/11975/11979: 8/13/9/11).
    const empCount = _numericHeadcount(org.estimated_num_employees);
    _push(out, "numberofemployees", src, empCount, empCount, 0.6, updated);
    // Apollo org industry is free-text (no NAICS in this contract) -> lowercase text key.
    _push(out, "industry", src, org.industry, _norm(org.industry), 0.6, updated);
    // 58-05 Task 1: native `country` candidate. Apollo's org record has no dedicated
    // lv_country_region_normalized candidate today (unlike Lusha/ZoomInfo) -- this is the
    // first location signal this branch emits for companies. Live evidence (execs
    // 11929/11932/11975/11979): org.country is a flat full name ("Australia") 4/4 times,
    // same shape the portal's `country` property already holds.
    _push(out, "country", src, org.country, _norm(org.country), 0.6, updated);
    // 58-05 Task 2: native `city` candidate — live evidence execs 11929/11932/11975/11979:
    // org.city present 4/4 times ("Cairns"/"Sydney"/"Cairns"/"Melbourne").
    _push(out, "city", src, org.city, _norm(org.city), 0.6, updated);
  }
  return out;
}

// Unwrap the GTM enrich response envelope to a flat contact record.
// Live GTM (confirmed 200): { data: [ { attributes:{...fields}, meta:{matchStatus}, id } ] }
// (JSON:API). We flatten attributes and lift matchStatus/id up. Older/flat fixture
// envelopes ({data:[rec]}, {data:{result:[{data:[rec]}]}}, flat) still pass through.
function _zoomRecord(raw) {
  if (!raw || typeof raw !== "object") return raw || {};
  let rec = raw;
  if (Array.isArray(raw.data)) rec = raw.data[0] || {};
  else if (raw.data && typeof raw.data === "object" && raw.data.attributes) rec = raw.data;
  if (rec && rec.attributes) {
    return { ...rec.attributes, id: rec.id,
      matchStatus: (rec.meta && rec.meta.matchStatus) || rec.attributes.matchStatus };
  }
  const r = raw.data != null ? raw.data : raw;
  if (Array.isArray(r)) return r[0] || {};
  if (r && Array.isArray(r.result)) {
    const first = r.result[0];
    if (first && Array.isArray(first.data)) return first.data[0] || {};
    return first || {};
  }
  return r;
}

function zoominfoCandidates(rawResponse, objectType) {
  const out = [];
  const src = "zoominfo";
  const raw = _zoomRecord(rawResponse) || {};
  const recency = raw.validDate || raw.lastUpdatedDate;
  if (objectType === "contacts") {
    // Location candidates: LIVE-verified 2026-08-26 (scripts/
    // probe_zoominfo_location_fields.mjs, FULL_MATCH probe on this account): GTM
    // contacts/enrich ACCEPTS outputFields city/state/country/zipCode/metroArea —
    // `country` came back populated ("Australia"), city/state null for that contact
    // but schema-valid. Requested in ZOOM_OUTPUT_FIELDS (build_cloud_workflows.py)
    // as city/state/country; mapped below with the same code-shaped-only rule for
    // hs_* codes as Lusha/Apollo. rejected by the same probe: location, region,
    // personCity/personState/personCountry (400 PFAPI0009).
    const fullMatch = raw.matchStatus === "FULL_MATCH" || raw.matchStatus === undefined;
    // matchStatus != FULL_MATCH drops person fields entirely (§2).
    if (!fullMatch) return out;
    // Live contactAccuracyScore is a STRING ("91.0"); coerce before the /100.
    const scoreNum = Number(raw.contactAccuracyScore);
    const acc = Number.isFinite(scoreNum) && raw.contactAccuracyScore !== "" && raw.contactAccuracyScore != null
      ? scoreNum / 100 : 0.6;
    _push(out, "email", src, raw.email, normalizeEmailBasic(raw.email), acc, recency);
    // Phones: structural 0.8 (no per-field grade) per §2 "mobilePhone present=0.8".
    // `country` is now a verified, requested outputField (probe 2026-08-26), so non-AU
    // ZoomInfo nationals parse with their real region; absent country still falls back
    // to the AU heuristic inside normalizePhone.
    const region = _iso2(raw.country);
    const phone = normalizePhone(raw.phone, region);
    if (phone) _push(out, "phone", src, raw.phone, phone, 0.8, recency);
    const mobile = normalizePhone(raw.mobilePhone, region);
    if (mobile) _push(out, "mobilephone", src, raw.mobilePhone, mobile, 0.8, recency);
    _push(out, "jobtitle", src, raw.jobTitle, _norm(raw.jobTitle), acc, recency);
    // managementLevel is an array (["Director"]) in the live GTM response; take the first.
    const ml = Array.isArray(raw.managementLevel) ? raw.managementLevel[0] : raw.managementLevel;
    _push(out, "seniority", src, ml, _norm(ml), acc, recency);
    // Location (probe-verified outputFields, 2026-08-26). Same shape as Lusha/Apollo:
    // names as-is; hs_* codes only from an already-code-shaped value, never a lookup.
    _push(out, "city", src, raw.city, _norm(raw.city), 0.6, recency);
    _push(out, "state", src, raw.state, _norm(raw.state), 0.6, recency);
    _push(out, "country", src, raw.country, _norm(raw.country), 0.6, recency);
    const ziCountryCode = _codeShaped(raw.country, 2, 2);
    if (ziCountryCode) {
      _push(out, "hs_country_region_code", src, raw.country, ziCountryCode, 0.6, recency);
    }
    const ziStateCode = _codeShaped(raw.state, 2, 3);
    if (ziStateCode) {
      _push(out, "hs_state_code", src, raw.state, ziStateCode, 0.6, recency);
    }
  } else {
    // UNITS: GTM `revenue` is in THOUSANDS, not dollars — confirmed live against three
    // records (Racing NSW 268163 + revenueRange "$250 mil. - $500 mil."; ZoomInfo 1254000
    // + "$1 bil. - $5 bil."; FanDuel 14050000 + "Over $5 bil."), and Apollo independently
    // reports Racing NSW annual_revenue 268000000 dollars. Feeding the raw number to
    // normalizeRevenueBand (which expects dollars) banded every company 1000x low —
    // FanDuel's $14b read as "5-50M". Prefer the unambiguous `revenueRange` string;
    // fall back to revenue*1000.
    const ziRev = raw.revenueRange != null && raw.revenueRange !== ""
      ? raw.revenueRange
      : (typeof raw.revenue === "number" ? raw.revenue * 1000 : null);
    _push(out, "lv_revenue_band", src, ziRev, normalizeRevenueBand(ziRev), 0.6, recency);
    // employeeCount is an exact integer; employeeRange ("100 - 250") is NOT an
    // lv_employee_band enum value, so it is only a last resort.
    _push(out, "lv_employee_band", src, raw.employeeCount != null ? raw.employeeCount : raw.employeeRange,
      normalizeEmployeeBand(raw.employeeCount != null ? raw.employeeCount : raw.employeeRange), 0.6, recency);
    // 58-05 Task 2: native `numberofemployees` candidate — from raw.employeeCount ONLY,
    // NEVER the raw.employeeRange fallback the band above accepts ("10 - 20" is exactly
    // the spaced-range shape _numericHeadcount exists to refuse). Live evidence execs
    // 11929/11932/11975/11979 all carried employeeCount as a plain integer, so the
    // employeeRange-only case is untested against live traffic here (offline fixture only).
    const empCount = _numericHeadcount(raw.employeeCount);
    _push(out, "numberofemployees", src, empCount, empCount, 0.6, recency);
    const ziCountry = _iso2(raw.country);
    _push(out, "lv_country_region_normalized", src, raw.country,
      normalizeCountryRegion(ziCountry || raw.country), 0.6, recency);
    // 58-05 Task 1: native `country` candidate — the same raw.country value the
    // lv_country_region_normalized derivation above already reads, already a full name
    // (live evidence execs 11929/11932/11975/11979: "Australia"/"United States").
    // ZoomInfo GTM company enrich requests no `city` outputField (ZOOM_CO_OUTPUT_FIELDS
    // has no city entry) and none of the 4 sampled live company executions carried one —
    // documented absence, not a gap (Task 2 leaves this branch without a city push).
    _push(out, "country", src, raw.country, _norm(raw.country), 0.6, recency);
    // Live GTM naicsCodes are OBJECTS ({id,name}, most-general first); the flat fixtures
    // are bare code strings. String(obj) would have staged "[object Object]" as industry.
    // primaryIndustry is an array in the live response (["Hospitality", "Sports Teams ..."]).
    // NORM-01: prefer the NAICS entry's own human-readable name over its bare numeric code;
    // a code is never a valid industry text value (see _industryText).
    const naics0 = (raw.naicsCodes || [])[0];
    const industry = _industryText(naics0, raw.primaryIndustry);
    _push(out, "industry", src, industry && industry.raw, industry && industry.key, 0.6, recency);
  }
  return out;
}

function _norm(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim().toLowerCase();
  return s === "" ? null : s;
}

const MAPPERS = { lusha: lushaCandidates, apollo: apolloCandidates, zoominfo: zoominfoCandidates };

function toCandidates(providerName, rawResponse, objectType) {
  const mapper = MAPPERS[String(providerName || "").toLowerCase()];
  if (!mapper || !rawResponse) return [];
  return mapper(rawResponse, objectType === "companies" ? "companies" : "contacts");
}

module.exports = {
  toCandidates,
  lushaRecordId,
  normalizeRevenueBand,
  normalizeEmployeeBand,
  normalizeCountryRegion,
};
