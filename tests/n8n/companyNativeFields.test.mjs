// tests/n8n/companyNativeFields.test.mjs
//
// 58-05 (gap-closure): native `country`/`city`/`numberofemployees` candidates on the
// three company branches of normalizeProviders.js, their fill_blank_only classification
// in mergeCompanies.js/config/field_policy.yaml, and the pin that ENRICH_DECIDE_CO_CLOUD's
// wholesale canonicalPatch spread needs no key-allowlist edit to carry them.
//
// Task 1 wires `country` end to end (the tracer). Task 2 extends the same shape to
// `city` and `numberofemployees`, with the numeric-only headcount guard.
//
// Run: node --test tests/n8n/companyNativeFields.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));
const { mergeCompanies, DEFAULT_COMPANY_POLICY } =
  require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

function byField(candidates, field) {
  return candidates.find((c) => c.field === field);
}

// ---------------------------------------------------------------------------------------
// --- Task 1: country, all three company branches ----------------------------------------
// ---------------------------------------------------------------------------------------

// Live-shaped fixture, exec 11979 (Series Futsal Victoria) -- Lusha v3 companies envelope.
test("toCandidates('lusha', <fixture with location.country>, 'companies') yields a country candidate carrying the full name", () => {
  const raw = {
    requestId: "r1",
    results: [{
      id: "v1.SYNTHETIC",
      location: { city: "Brunswick", state: "Victoria", country: "Australia", countryIso2: "AU" },
      updateDate: "2026-08-26",
    }],
  };
  const cands = toCandidates("lusha", raw, "companies");
  const country = byField(cands, "country");
  assert.ok(country, "country candidate present");
  assert.equal(country.value, "Australia", "value is the full name, not the ISO2 code");
});

test("toCandidates('lusha', <fixture with no location>, 'companies') yields no country candidate", () => {
  const raw = { requestId: "r1", results: [{ id: "v1.SYNTHETIC", updateDate: "2026-08-26" }] };
  const cands = toCandidates("lusha", raw, "companies");
  assert.ok(!byField(cands, "country"), "no country candidate when location is absent");
});

// Live-shaped fixture, exec 11979 -- Apollo organization object.
test("toCandidates('apollo', <fixture with organization.country>, 'companies') yields a country candidate", () => {
  const raw = { organization: { city: "Melbourne", state: "Victoria", country: "Australia" } };
  const cands = toCandidates("apollo", raw, "companies");
  const country = byField(cands, "country");
  assert.ok(country, "country candidate present");
  assert.equal(country.value, "Australia");
});

test("toCandidates('apollo', <fixture with no country key>, 'companies') yields no country candidate", () => {
  const raw = { organization: { city: "Melbourne" } };
  const cands = toCandidates("apollo", raw, "companies");
  assert.ok(!byField(cands, "country"), "no country candidate when organization.country is absent");
});

// Live-shaped fixture, exec 11979 -- ZoomInfo GTM companies/enrich JSON:API envelope.
test("toCandidates('zoominfo', <fixture with attributes.country>, 'companies') yields a country candidate", () => {
  const raw = { data: [{ attributes: { country: "Australia" }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] };
  const cands = toCandidates("zoominfo", raw, "companies");
  const country = byField(cands, "country");
  assert.ok(country, "country candidate present");
  assert.equal(country.value, "Australia");
});

test("toCandidates('zoominfo', <fixture with no country key>, 'companies') yields no country candidate", () => {
  const raw = { data: [{ attributes: {}, id: "1", meta: { matchStatus: "FULL_MATCH" } }] };
  const cands = toCandidates("zoominfo", raw, "companies");
  assert.ok(!byField(cands, "country"), "no country candidate when attributes.country is absent");
});

// --- mergeCompanies: fill_blank_only behaviour for country -------------------------------

test("mergeCompanies: country candidate against a BLANK existing value promotes to canonicalPatch", () => {
  const { canonicalPatch, decisions } = mergeCompanies(
    { country: "" },
    { country: "Australia" },
    undefined,
    { source: "waterfall", confidence: 85 },
  );
  assert.equal(canonicalPatch.country, "Australia");
  const d = decisions.find((x) => x.field === "country");
  assert.equal(d.decision, "promote");
});

test("mergeCompanies: country candidate against a NON-BLANK existing value stays out of canonicalPatch", () => {
  const { canonicalPatch, decisions } = mergeCompanies(
    { country: "New Zealand" },
    { country: "Australia" },
    undefined,
    { source: "waterfall", confidence: 85 },
  );
  assert.equal(canonicalPatch.country, undefined, "existing country must never be overwritten");
  const d = decisions.find((x) => x.field === "country");
  assert.equal(d.decision, "stage_only");
});

// --- Cross-engine parity: config/field_policy.yaml <-> DEFAULT_COMPANY_POLICY ------------
//
// Deliberately no npm YAML dependency (repo convention, see normalizeProviders.js header)
// -- a small hand-rolled block extractor is enough for this file's simple 2-space-indented
// shape, and reads BOTH files rather than hardcoding two literals to compare.

function yamlSectionText(yamlText, sectionName) {
  const lines = yamlText.split("\n");
  const startIdx = lines.findIndex((l) => l === `${sectionName}:`);
  if (startIdx === -1) throw new Error(`section ${sectionName} not found`);
  const body = [];
  for (let i = startIdx + 1; i < lines.length; i++) {
    if (/^\S/.test(lines[i])) break; // dedent to column 0 -> next top-level section
    body.push(lines[i]);
  }
  return body.join("\n");
}

function yamlFieldPolicy(sectionText, fieldName) {
  const lines = sectionText.split("\n");
  const fieldRe = new RegExp(`^  ${fieldName}:\\s*$`);
  const startIdx = lines.findIndex((l) => fieldRe.test(l));
  if (startIdx === -1) return null;
  const block = [];
  for (let i = startIdx + 1; i < lines.length; i++) {
    if (/^  \S/.test(lines[i])) break; // next top-level (2-space) field or comment
    block.push(lines[i]);
  }
  const text = block.join("\n");
  const classMatch = text.match(/class:\s*(\S+)/);
  const confMatch = text.match(/min_confidence:\s*(\d+)/);
  return {
    class: classMatch ? classMatch[1] : null,
    min_confidence: confMatch ? Number(confMatch[1]) : null,
  };
}

function assertParity(fieldName) {
  const yamlText = fs.readFileSync(path.join(ROOT, "config/field_policy.yaml"), "utf8");
  const companiesSection = yamlSectionText(yamlText, "companies");
  const yamlPolicy = yamlFieldPolicy(companiesSection, fieldName);
  assert.ok(yamlPolicy, `config/field_policy.yaml companies.${fieldName} entry not found`);
  const jsPolicy = DEFAULT_COMPANY_POLICY[fieldName];
  assert.ok(jsPolicy, `DEFAULT_COMPANY_POLICY.${fieldName} entry not found`);
  assert.equal(yamlPolicy.class, jsPolicy.class,
    `${fieldName}: yaml class=${yamlPolicy.class} vs JS class=${jsPolicy.class}`);
  assert.equal(yamlPolicy.min_confidence, jsPolicy.min_confidence,
    `${fieldName}: yaml min_confidence=${yamlPolicy.min_confidence} vs JS min_confidence=${jsPolicy.min_confidence}`);
}

test("config/field_policy.yaml and DEFAULT_COMPANY_POLICY agree on country's class and min_confidence", () => {
  assertParity("country");
});

// --- Pin: ENRICH_DECIDE_CO_CLOUD's wholesale spread needs no key-allowlist edit ----------

test("ENRICH_DECIDE_CO_CLOUD builds its properties patch with an unfiltered canonicalPatch spread -- no key allowlist to edit for a newly-promoted field", () => {
  const pySrc = fs.readFileSync(path.join(ROOT, "scripts/build_cloud_workflows.py"), "utf8");
  const start = pySrc.indexOf("ENRICH_DECIDE_CO_CLOUD = inline(");
  assert.ok(start !== -1, "ENRICH_DECIDE_CO_CLOUD definition not found in build_cloud_workflows.py");
  const nextConst = pySrc.indexOf("\nENRICH_", start + 1);
  const body = pySrc.slice(start, nextConst === -1 ? pySrc.length : nextConst);
  assert.ok(
    body.includes("properties = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}), ...(row.lusha_ids || {}) };"),
    "the wholesale canonicalPatch spread is missing or was rewritten -- if a key allowlist " +
    "was added here, country/city/numberofemployees would need to be added to it explicitly",
  );
  // Reproduce the exact spread shape in isolation to prove ITS semantics carry an
  // arbitrary key through unedited (the source-text pin above proves the REAL code still
  // reads this way; this proves what that shape actually does).
  const merge = { canonicalPatch: { country: "Australia", an_arbitrary_future_field: "x" }, cacheKeys: {} };
  const row = {};
  const properties = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}), ...(row.lusha_ids || {}) };
  assert.equal(properties.country, "Australia");
  assert.equal(properties.an_arbitrary_future_field, "x", "an arbitrary promoted key survives the spread untouched");
});

// ---------------------------------------------------------------------------------------
// --- Task 2: city + numberofemployees, all three company branches -----------------------
// ---------------------------------------------------------------------------------------

// --- city: present/absent per branch, live-shaped fixtures -------------------------------

test("toCandidates('lusha', <fixture with location.city>, 'companies') yields a city candidate; no location -> none", () => {
  const withCity = { requestId: "r1", results: [{ id: "v1.SYNTHETIC",
    location: { city: "Brunswick", country: "Australia" }, updateDate: "2026-08-26" }] };
  assert.equal(byField(toCandidates("lusha", withCity, "companies"), "city").value, "Brunswick");
  const noLocation = { requestId: "r1", results: [{ id: "v1.SYNTHETIC", updateDate: "2026-08-26" }] };
  assert.ok(!byField(toCandidates("lusha", noLocation, "companies"), "city"));
});

test("toCandidates('apollo', <fixture with organization.city>, 'companies') yields a city candidate; no city key -> none", () => {
  const withCity = { organization: { city: "Melbourne", country: "Australia" } };
  assert.equal(byField(toCandidates("apollo", withCity, "companies"), "city").value, "Melbourne");
  const noCity = { organization: { country: "Australia" } };
  assert.ok(!byField(toCandidates("apollo", noCity, "companies"), "city"));
});

test("toCandidates('zoominfo', <company fixture>, 'companies') never yields a city candidate -- ZOOM_CO_OUTPUT_FIELDS requests no city outputField (documented absence, not a gap)", () => {
  const raw = { data: [{ attributes: { country: "Australia", city: "should never appear" }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] };
  const cands = toCandidates("zoominfo", raw, "companies");
  assert.ok(!byField(cands, "city"),
    "even if a fixture smuggled a city key into attributes, the ZoomInfo companies branch must not read it -- the live outputFields list never requests it");
});

// --- numberofemployees: numeric-only guard, all three branches ---------------------------

test("toCandidates('lusha', <numeric employeeCount>, 'companies') yields numberofemployees; a spaced range string yields none, and lv_employee_band is unaffected either way", () => {
  const numeric = { requestId: "r1", results: [{ id: "v1.SYNTHETIC", employeeCount: 12, updateDate: "2026-08-26" }] };
  const numericCands = toCandidates("lusha", numeric, "companies");
  assert.equal(byField(numericCands, "numberofemployees").value, 12);
  assert.equal(byField(numericCands, "lv_employee_band").normalizedValue, "10-50");

  const ranged = { company: { employees: "51 - 200" } }; // legacy /v2/company shape
  const rangedCands = toCandidates("lusha", ranged, "companies");
  assert.ok(!byField(rangedCands, "numberofemployees"),
    "a spaced range string must never become a numberofemployees candidate");
  assert.equal(byField(rangedCands, "lv_employee_band").normalizedValue, "51-200",
    "the guard narrows nothing about the pre-existing band candidate");
});

test("toCandidates('apollo', <fixture with estimated_num_employees>, 'companies') yields numberofemployees", () => {
  const raw = { organization: { estimated_num_employees: 11 } };
  assert.equal(byField(toCandidates("apollo", raw, "companies"), "numberofemployees").value, 11);
});

test("toCandidates('zoominfo', <numeric employeeCount>, 'companies') yields numberofemployees; employeeRange alone (no employeeCount) yields none, and lv_employee_band still promotes from the range", () => {
  const numeric = { data: [{ attributes: { employeeCount: 13, employeeRange: "10 - 20" }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] };
  const numericCands = toCandidates("zoominfo", numeric, "companies");
  assert.equal(byField(numericCands, "numberofemployees").value, 13);

  const rangeOnly = { data: [{ attributes: { employeeRange: "10 - 20" }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] };
  const rangeCands = toCandidates("zoominfo", rangeOnly, "companies");
  assert.ok(!byField(rangeCands, "numberofemployees"),
    "employeeRange alone must never become a numberofemployees candidate");
  assert.equal(byField(rangeCands, "lv_employee_band").normalizedValue, "10-20",
    "the guard narrows nothing about the pre-existing band candidate's own fallback");
});

test("toCandidates: a zero headcount is treated as no-data, not a candidate, on every branch that can supply one", () => {
  assert.ok(!byField(toCandidates("apollo", { organization: { estimated_num_employees: 0 } }, "companies"), "numberofemployees"));
  assert.ok(!byField(toCandidates("zoominfo",
    { data: [{ attributes: { employeeCount: 0 }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] }, "companies"),
    "numberofemployees"));
});

// --- mergeCompanies: fill_blank_only behaviour for city + numberofemployees --------------

test("mergeCompanies: city and numberofemployees each fill a blank existing value and stay out of a non-blank one", () => {
  const blank = mergeCompanies({ city: "", numberofemployees: "" },
    { city: "Brunswick", numberofemployees: 12 }, undefined, { source: "waterfall", confidence: 85 });
  assert.equal(blank.canonicalPatch.city, "Brunswick");
  assert.equal(blank.canonicalPatch.numberofemployees, 12);

  const nonBlank = mergeCompanies({ city: "Sydney", numberofemployees: 500 },
    { city: "Brunswick", numberofemployees: 12 }, undefined, { source: "waterfall", confidence: 85 });
  assert.equal(nonBlank.canonicalPatch.city, undefined);
  assert.equal(nonBlank.canonicalPatch.numberofemployees, undefined);
});

// --- Cross-engine parity, extended to all three fields -----------------------------------

test("config/field_policy.yaml and DEFAULT_COMPANY_POLICY agree on city's and numberofemployees' class and min_confidence", () => {
  assertParity("city");
  assertParity("numberofemployees");
});
