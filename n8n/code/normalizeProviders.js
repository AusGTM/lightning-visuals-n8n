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

const { normalizePhoneAU } = require("./normalizePhone");
const { normalizeEmailBasic } = require("./normalizeEmail");

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
  // Already a band string (e.g. ZoomInfo employeeRange "201-500") -> pass through.
  if (typeof value === "string" && !/^\d+$/.test(value.trim())) return value.trim();
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
  let a = LUSHA_EMAIL_CONF[e.confidence];
  if (a === null || a === undefined) a = 0.4; // null/unknown grade
  if (e.type && String(e.type).toLowerCase() !== "work") a *= 0.8; // private/personal
  return _clamp01(a);
}

// ---- provider mappers -------------------------------------------------------
function _push(out, field, source, value, normalizedValue, accuracy, recencyDate) {
  if (value === null || value === undefined || value === "") return;
  out.push({ field, source, value, normalizedValue, accuracy: _clamp01(accuracy), recencyDate: recencyDate || null });
}

function lushaCandidates(raw, objectType) {
  const out = [];
  const src = "lusha";
  if (objectType === "contacts") {
    for (const e of raw.emails || []) {
      _push(out, "email", src, e.email, normalizeEmailBasic(e.email), lushaEmailAccuracy(e), e.updateDate);
    }
    for (const p of raw.phones || []) {
      if (p.doNotCall) continue; // suppress (not just downscore) per §2
      const t = String(p.type || "").toLowerCase();
      const acc = t === "mobile" || t === "direct" ? 0.8 : 0.5;
      const field = t === "mobile" ? "mobilephone" : "phone";
      _push(out, field, src, p.number, normalizePhoneAU(p.number), acc, p.updateDate);
    }
    if (raw.jobTitle) {
      // No per-field grade for Lusha title -> ungraded base 0.6.
      _push(out, "jobtitle", src, raw.jobTitle.title, _norm(raw.jobTitle.title), 0.6, raw.updateDate);
      _push(out, "seniority", src, raw.jobTitle.seniority, _norm(raw.jobTitle.seniority), 0.6, raw.updateDate);
    }
  } else {
    // company firmographics — no per-field grade -> base 0.6.
    _push(out, "lv_revenue_band", src, raw.revenueRange, normalizeRevenueBand(raw.revenueRange), 0.6, raw.updateDate);
    _push(out, "lv_employee_band", src, raw.employeeCount, normalizeEmployeeBand(raw.employeeCount), 0.6, raw.updateDate);
    const naics = (raw.naicsCodes || [])[0];
    _push(out, "industry", src, naics, naics ? String(naics) : null, 0.6, raw.updateDate);
    _push(out, "lv_country_region_normalized", src, raw.countryIso2, normalizeCountryRegion(raw.countryIso2), 0.6, raw.updateDate);
  }
  return out;
}

function apolloCandidates(raw, objectType) {
  const out = [];
  const src = "apollo";
  if (objectType === "contacts") {
    _push(out, "email", src, raw.email, normalizeEmailBasic(raw.email), apolloEmailAccuracy(raw), raw.updated_at);
    for (const p of raw.phone_numbers || []) {
      if (p.dnc_status || p.doNotCall) continue; // suppress
      const status = p.status || p.status_cd;
      const acc = status === "valid_number" ? 1.0 : 0.5;
      const t = String(p.type || "").toLowerCase();
      const field = t === "mobile" ? "mobilephone" : "phone";
      _push(out, field, src, p.sanitized_number, normalizePhoneAU(p.sanitized_number), acc, raw.updated_at);
    }
    _push(out, "jobtitle", src, raw.title, _norm(raw.title), 0.6, raw.updated_at);
    _push(out, "seniority", src, raw.seniority, _norm(raw.seniority), 0.6, raw.updated_at);
  } else {
    const org = raw.organization || raw.org || raw;
    _push(out, "lv_revenue_band", src, org.annual_revenue, normalizeRevenueBand(org.annual_revenue), 0.6, raw.updated_at);
    _push(out, "lv_employee_band", src, org.estimated_num_employees, normalizeEmployeeBand(org.estimated_num_employees), 0.6, raw.updated_at);
    // Apollo org industry is free-text (no NAICS in this contract) -> lowercase text key.
    _push(out, "industry", src, org.industry, _norm(org.industry), 0.6, raw.updated_at);
  }
  return out;
}

function zoominfoCandidates(raw, objectType) {
  const out = [];
  const src = "zoominfo";
  const recency = raw.validDate || raw.lastUpdatedDate;
  if (objectType === "contacts") {
    const fullMatch = raw.matchStatus === "FULL_MATCH" || raw.matchStatus === undefined;
    // matchStatus != FULL_MATCH drops person fields entirely (§2).
    if (!fullMatch) return out;
    const acc = typeof raw.contactAccuracyScore === "number" ? raw.contactAccuracyScore / 100 : 0.6;
    _push(out, "email", src, raw.email, normalizeEmailBasic(raw.email), acc, recency);
    // Phones: structural 0.8 (no per-field grade) per §2 "mobilePhone present=0.8".
    _push(out, "phone", src, raw.phone, normalizePhoneAU(raw.phone), 0.8, recency);
    _push(out, "mobilephone", src, raw.mobilePhone, normalizePhoneAU(raw.mobilePhone), 0.8, recency);
    _push(out, "jobtitle", src, raw.jobTitle, _norm(raw.jobTitle), acc, recency);
    _push(out, "seniority", src, raw.managementLevel, _norm(raw.managementLevel), acc, recency);
  } else {
    _push(out, "lv_revenue_band", src, raw.revenue != null ? raw.revenue : raw.revenueRange,
      normalizeRevenueBand(raw.revenue != null ? raw.revenue : raw.revenueRange), 0.6, recency);
    _push(out, "lv_employee_band", src, raw.employeeCount != null ? raw.employeeCount : raw.employeeRange,
      normalizeEmployeeBand(raw.employeeCount != null ? raw.employeeCount : raw.employeeRange), 0.6, recency);
    const naics = (raw.naicsCodes || [])[0];
    _push(out, "industry", src, naics || raw.primaryIndustry, naics ? String(naics) : _norm(raw.primaryIndustry), 0.6, recency);
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
