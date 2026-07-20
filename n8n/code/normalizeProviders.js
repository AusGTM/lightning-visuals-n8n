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
  if (v <= 9) return "1-9";
  if (v <= 50) return "10-50";
  if (v <= 200) return "51-200";
  if (v <= 500) return "201-500";
  if (v <= 1000) return "501-1000";
  return "1001+";
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

function lushaCandidates(rawResponse, objectType) {
  const out = [];
  const src = "lusha";
  // Live v2 person nests the record under contact.data; flat fixtures pass through.
  const raw = (rawResponse && rawResponse.contact && rawResponse.contact.data) || rawResponse || {};
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
    }
  } else {
    // company firmographics — no per-field grade -> base 0.6. Live nests under `company`
    // with array revenueRange/companySize [lo,hi] and location.countryIso2; fixtures are flat.
    // Live /v2/company wraps the record in `data`; the person endpoint uses `company`;
    // fixtures are flat. Without the `data` unwrap the live company response yielded
    // ZERO candidates (every lookup hit the envelope, not the record).
    const co = raw.company || raw.data || raw;
    const rev = Array.isArray(co.revenueRange) ? co.revenueRange[0] : co.revenueRange;
    _push(out, "lv_revenue_band", src, rev, normalizeRevenueBand(rev), 0.6, updated);
    // Live /v2/company returns the headcount as `employees` ("51 - 200", a spaced range
    // string); companySize/employeeCount are null there and only appear in the fixtures.
    const emp = Array.isArray(co.companySize)
      ? co.companySize[co.companySize.length - 1]
      : (co.companySize != null ? co.companySize
        : (co.employeeCount != null ? co.employeeCount : co.employees));
    _push(out, "lv_employee_band", src, emp, normalizeEmployeeBand(emp), 0.6, updated);
    const naics = (co.naicsCodes || [])[0];
    _push(out, "industry", src, naics || co.mainIndustry, naics ? String(naics) : _norm(co.mainIndustry), 0.6, updated);
    const country = (co.location && co.location.countryIso2) || co.countryIso2;
    _push(out, "lv_country_region_normalized", src, country, normalizeCountryRegion(country), 0.6, updated);
  }
  return out;
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
  } else {
    const org = (raw.person && raw.person.organization) || raw.organization || raw.org || raw;
    // Live org revenue is `organization_revenue` (number); flat fixtures use `annual_revenue`.
    const revenue = org.annual_revenue != null ? org.annual_revenue : org.organization_revenue;
    _push(out, "lv_revenue_band", src, revenue, normalizeRevenueBand(revenue), 0.6, updated);
    _push(out, "lv_employee_band", src, org.estimated_num_employees, normalizeEmployeeBand(org.estimated_num_employees), 0.6, updated);
    // Apollo org industry is free-text (no NAICS in this contract) -> lowercase text key.
    _push(out, "industry", src, org.industry, _norm(org.industry), 0.6, updated);
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
    const fullMatch = raw.matchStatus === "FULL_MATCH" || raw.matchStatus === undefined;
    // matchStatus != FULL_MATCH drops person fields entirely (§2).
    if (!fullMatch) return out;
    // Live contactAccuracyScore is a STRING ("91.0"); coerce before the /100.
    const scoreNum = Number(raw.contactAccuracyScore);
    const acc = Number.isFinite(scoreNum) && raw.contactAccuracyScore !== "" && raw.contactAccuracyScore != null
      ? scoreNum / 100 : 0.6;
    _push(out, "email", src, raw.email, normalizeEmailBasic(raw.email), acc, recency);
    // Phones: structural 0.8 (no per-field grade) per §2 "mobilePhone present=0.8".
    // ZoomInfo GTM enrich returns no country field, so region falls back to the AU
    // heuristic; E.164 numbers pass through, non-AU national is null-dropped (safe).
    // (Add a verified `country` outputField later to parse non-AU ZoomInfo nationals.)
    const region = _iso2(raw.country);
    const phone = normalizePhone(raw.phone, region);
    if (phone) _push(out, "phone", src, raw.phone, phone, 0.8, recency);
    const mobile = normalizePhone(raw.mobilePhone, region);
    if (mobile) _push(out, "mobilephone", src, raw.mobilePhone, mobile, 0.8, recency);
    _push(out, "jobtitle", src, raw.jobTitle, _norm(raw.jobTitle), acc, recency);
    // managementLevel is an array (["Director"]) in the live GTM response; take the first.
    const ml = Array.isArray(raw.managementLevel) ? raw.managementLevel[0] : raw.managementLevel;
    _push(out, "seniority", src, ml, _norm(ml), acc, recency);
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
    const ziCountry = _iso2(raw.country);
    _push(out, "lv_country_region_normalized", src, raw.country,
      normalizeCountryRegion(ziCountry || raw.country), 0.6, recency);
    // Live GTM naicsCodes are OBJECTS ({id,name}, most-general first); the flat fixtures
    // are bare code strings. String(obj) would have staged "[object Object]" as industry.
    const naics0 = (raw.naicsCodes || [])[0];
    const naics = naics0 && typeof naics0 === "object" ? naics0.id : naics0;
    // primaryIndustry is an array in the live response (["Hospitality", "Sports Teams ..."]).
    const pi = Array.isArray(raw.primaryIndustry) ? raw.primaryIndustry[0] : raw.primaryIndustry;
    _push(out, "industry", src, naics || pi, naics ? String(naics) : _norm(pi), 0.6, recency);
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
  normalizeRevenueBand,
  normalizeEmployeeBand,
  normalizeCountryRegion,
};
