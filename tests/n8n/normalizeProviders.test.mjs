// tests/n8n/normalizeProviders.test.mjs
//
// 260826-20w Task 2 commit 1 — proves the five new contact location candidates
// (city/state/country/hs_state_code/hs_country_region_code) that toCandidates()
// (n8n/code/normalizeProviders.js) now emits for the "lusha" and "apollo" contact
// mappers. Fixtures are shaped like the real payloads captured live in Task 1
// (260826-20w-CALIBRATION.md §a/§f): Lusha v3's `location.{city,country,countryIso2}`
// (no `state` key — never observed live), Apollo's flat `person.{city,state,country}`
// (full names, never a code).
//
// Run: node --test tests/n8n/normalizeProviders.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));

function byField(candidates, field) {
  return candidates.find((c) => c.field === field);
}

// --- Lusha: location.{city,country,countryIso2} -> city, country, hs_country_region_code
test("toCandidates('lusha', <fixture with location.city/country/countryIso2>, 'contacts') yields city/country/hs_country_region_code", () => {
  const raw = {
    requestId: "r1",
    results: [{
      id: "v1.SYNTHETIC",
      location: { country: "Australia", countryIso2: "AU", city: "Sydney", continent: "Oceania" },
      updateDate: "2026-05-01",
    }],
  };
  const cands = toCandidates("lusha", raw, "contacts");
  const city = byField(cands, "city");
  const country = byField(cands, "country");
  const hsCountry = byField(cands, "hs_country_region_code");
  assert.ok(city, "city candidate present");
  assert.equal(city.value, "Sydney");
  assert.ok(country, "country candidate present");
  assert.equal(country.value, "Australia");
  assert.ok(hsCountry, "hs_country_region_code candidate present");
  assert.equal(hsCountry.normalizedValue, "AU");
  // No state key in the fixture (matches every live sample) -> no state/hs_state_code candidate.
  assert.ok(!byField(cands, "state"), "no state candidate when location has no state key");
  assert.ok(!byField(cands, "hs_state_code"), "no hs_state_code candidate when location has no state key");
});

test("toCandidates('lusha', ...): a code-shaped state DOES yield hs_state_code (synthetic — never observed live)", () => {
  const raw = {
    results: [{
      id: "v1.SYNTHETIC2",
      location: { country: "United States", countryIso2: "US", city: "Austin", state: "TX" },
      updateDate: "2026-05-01",
    }],
  };
  const cands = toCandidates("lusha", raw, "contacts");
  const hsState = byField(cands, "hs_state_code");
  assert.ok(hsState, "hs_state_code candidate present for a code-shaped state");
  assert.equal(hsState.normalizedValue, "TX");
});

// --- Apollo: flat person.{city,state,country} -----------------------------------------
test("toCandidates('apollo', <fixture with flat city/state/country>, 'contacts') yields city/state/country", () => {
  const raw = {
    person: { city: "Sydney", state: "New South Wales", country: "Australia", email: null },
  };
  const cands = toCandidates("apollo", raw, "contacts");
  const city = byField(cands, "city");
  const state = byField(cands, "state");
  const country = byField(cands, "country");
  assert.ok(city, "city candidate present");
  assert.equal(city.value, "Sydney");
  assert.ok(state, "state candidate present");
  assert.equal(state.value, "New South Wales");
  assert.ok(country, "country candidate present");
  assert.equal(country.value, "Australia");
  // Full names, not codes -> no hs_* candidates (no name->code lookup table).
  assert.ok(!byField(cands, "hs_state_code"), "a full state NAME never yields hs_state_code");
  assert.ok(!byField(cands, "hs_country_region_code"), "a full country NAME never yields hs_country_region_code");
});

test("toCandidates('apollo', ...): a code-shaped country/state DOES yield hs_* candidates (synthetic — never observed live)", () => {
  const raw = { person: { city: "Austin", state: "TX", country: "US" } };
  const cands = toCandidates("apollo", raw, "contacts");
  assert.equal(byField(cands, "hs_country_region_code").normalizedValue, "US");
  assert.equal(byField(cands, "hs_state_code").normalizedValue, "TX");
});

test("toCandidates: an absent location payload never fabricates a candidate", () => {
  const lushaCands = toCandidates("lusha", { results: [{ id: "x" }] }, "contacts");
  assert.ok(!byField(lushaCands, "city"));
  assert.ok(!byField(lushaCands, "state"));
  assert.ok(!byField(lushaCands, "country"));
  const apolloCands = toCandidates("apollo", { person: {} }, "contacts");
  assert.ok(!byField(apolloCands, "city"));
  assert.ok(!byField(apolloCands, "state"));
  assert.ok(!byField(apolloCands, "country"));
});

// --- ZoomInfo: no location outputField verified live -> zero location candidates ------
test("toCandidates('zoominfo', ..., 'contacts') emits no location candidates (no verified outputField, 260826-20w-CALIBRATION.md §f)", () => {
  const raw = {
    data: [{
      attributes: {
        firstName: "John", lastName: "Doe", jobTitle: "CEO",
        contactAccuracyScore: "87.0", validDate: "2026-04-11T00:00:00Z",
      },
      meta: { matchStatus: "FULL_MATCH" },
    }],
  };
  const cands = toCandidates("zoominfo", raw, "contacts");
  for (const f of ["city", "state", "country", "hs_state_code", "hs_country_region_code"]) {
    assert.ok(!byField(cands, f), `zoominfo must not emit a ${f} candidate`);
  }
});

// --- ZoomInfo: flat attributes city/state/country -> same five candidates -------------
// outputFields city/state/country LIVE-verified on this account 2026-08-26 via
// scripts/probe_zoominfo_location_fields.mjs (HTTP 200, FULL_MATCH, country populated).
test("toCandidates('zoominfo', <GTM attrs with city/state/country>, 'contacts') yields the location candidates", () => {
  const raw = {
    data: [{
      type: "Contact", id: "1",
      meta: { matchStatus: "FULL_MATCH" },
      attributes: {
        firstName: "John", lastName: "Tsatsimas", jobTitle: "CEO",
        contactAccuracyScore: "91.0", validDate: "2026-08-01",
        city: "Sydney", state: "NSW", country: "Australia",
      },
    }],
  };
  const cands = toCandidates("zoominfo", raw, "contacts");
  assert.equal(byField(cands, "city").value, "Sydney");
  assert.equal(byField(cands, "state").value, "NSW");
  assert.equal(byField(cands, "country").value, "Australia");
  // "NSW" is code-shaped (2-3 chars) -> hs_state_code; "Australia" is a name -> no
  // hs_country_region_code (code-shaped-only rule, no name->code lookup).
  assert.equal(byField(cands, "hs_state_code").normalizedValue, "NSW");
  assert.ok(!byField(cands, "hs_country_region_code"),
    "country NAME must not become hs_country_region_code (code-shaped only)");
});

test("toCandidates('zoominfo', ...): null city/state (the live John probe shape) emits no null candidates", () => {
  const raw = {
    data: [{
      type: "Contact", id: "1",
      meta: { matchStatus: "FULL_MATCH" },
      attributes: { firstName: "John", lastName: "Tsatsimas", country: "Australia",
        city: null, state: null, contactAccuracyScore: "91.0" },
    }],
  };
  const cands = toCandidates("zoominfo", raw, "contacts");
  assert.ok(!byField(cands, "city"), "null city emits no candidate");
  assert.ok(!byField(cands, "state"), "null state emits no candidate");
  assert.equal(byField(cands, "country").value, "Australia");
});

// =========================================================================================
// Phase 72 Plan 06 (D-72-14/D-72-15) — company-branch state/hs_state_code/phone producers.
// Only Lusha and Apollo get producers (named live evidence below); ZoomInfo gets none
// (ZOOM_CO_OUTPUT_FIELDS requests neither field for companies, mirroring 58-05's `city`
// precedent). hs_country_region_code is out of scope entirely for companies (72-PORTAL-
// PROBE.json: the property does not exist, 404).
// =========================================================================================

// --- Lusha company: state (name) + hs_state_code (guarded, code-shaped only) ------------
// Documented live (LUSHA-V3-CONTRACT.md §5, confirmed-live companies/search-and-enrich
// example): co.location carries {city,state,country,countryIso2} — state is a full NAME
// ("New South Wales"), no dedicated state-code field in that documented shape.
test("toCandidates('lusha', <fixture with location.state full name>, 'companies') yields a state candidate, no hs_state_code", () => {
  const raw = {
    requestId: "r1",
    results: [{
      id: "v1.SYNTHETIC",
      location: { city: "Sydney", state: "New South Wales", country: "Australia", countryIso2: "AU" },
      updateDate: "2026-08-26",
    }],
  };
  const cands = toCandidates("lusha", raw, "companies");
  const state = byField(cands, "state");
  assert.ok(state, "state candidate present");
  assert.equal(state.value, "New South Wales");
  assert.ok(!byField(cands, "hs_state_code"), "a full state NAME never yields hs_state_code");
});

test("toCandidates('lusha', <fixture with a code-shaped location.state>, 'companies') DOES yield hs_state_code (synthetic — never observed live for Lusha companies)", () => {
  const raw = {
    results: [{
      id: "v1.SYNTHETIC2",
      location: { city: "Austin", state: "TX", country: "United States", countryIso2: "US" },
      updateDate: "2026-08-26",
    }],
  };
  const cands = toCandidates("lusha", raw, "companies");
  assert.equal(byField(cands, "hs_state_code").normalizedValue, "TX");
});

test("toCandidates('lusha', <fixture with no location>, 'companies') yields no state/hs_state_code candidate", () => {
  const raw = { requestId: "r1", results: [{ id: "v1.SYNTHETIC", updateDate: "2026-08-26" }] };
  const cands = toCandidates("lusha", raw, "companies");
  assert.ok(!byField(cands, "state"), "no state candidate when location is absent");
  assert.ok(!byField(cands, "hs_state_code"), "no hs_state_code candidate when location is absent");
});

test("toCandidates('lusha', ..., 'companies') never yields a phone candidate — documented absence (LUSHA-V3-CONTRACT.md §5 companies lane has no phone field)", () => {
  const raw = {
    results: [{ id: "v1.SYNTHETIC", location: { city: "Sydney", country: "Australia" }, updateDate: "2026-08-26" }],
  };
  const cands = toCandidates("lusha", raw, "companies");
  assert.ok(!byField(cands, "phone"), "Lusha companies lane has no phone field to produce from");
});

// --- Apollo company (org): state (name) + hs_state_code (guarded) + phone --------------
// Live evidence: docs/reports/2026-07-17-dryrun-batch.md (FanDuel org: state:"New York",
// full name); docs/reports/2026-07-15-dry-run-gillon-mclachlan.md (Tabcorp org:
// phone:"+61 3 9246 6010", primary_phone.sanitized_number:"+61392466010").
test("toCandidates('apollo', <fixture with organization.state full name>, 'companies') yields a state candidate, no hs_state_code", () => {
  const raw = { organization: { city: "New York", state: "New York", country: "United States" } };
  const cands = toCandidates("apollo", raw, "companies");
  const state = byField(cands, "state");
  assert.ok(state, "state candidate present");
  assert.equal(state.value, "New York");
  assert.ok(!byField(cands, "hs_state_code"), "a full state NAME never yields hs_state_code");
});

test("toCandidates('apollo', <fixture with a code-shaped organization.state>, 'companies') DOES yield hs_state_code (synthetic — never observed live for Apollo companies)", () => {
  const raw = { organization: { city: "Austin", state: "TX", country: "United States" } };
  const cands = toCandidates("apollo", raw, "companies");
  assert.equal(byField(cands, "hs_state_code").normalizedValue, "TX");
});

test("toCandidates('apollo', <fixture with no state key>, 'companies') yields no state/hs_state_code candidate", () => {
  const raw = { organization: { city: "Melbourne" } };
  const cands = toCandidates("apollo", raw, "companies");
  assert.ok(!byField(cands, "state"), "no state candidate when organization.state is absent");
  assert.ok(!byField(cands, "hs_state_code"), "no hs_state_code candidate when organization.state is absent");
});

test("toCandidates('apollo', <fixture with organization.primary_phone.sanitized_number>, 'companies') yields a phone candidate", () => {
  const raw = {
    organization: {
      country: "Australia",
      phone: "+61 3 9246 6010",
      primary_phone: { number: "+61 3 9246 6010", sanitized_number: "+61392466010" },
    },
  };
  const cands = toCandidates("apollo", raw, "companies");
  const phone = byField(cands, "phone");
  assert.ok(phone, "phone candidate present");
  // The already-sanitized primary_phone.sanitized_number is preferred over the raw
  // `phone` string -- both `value` (the raw input fed to normalizePhone) and
  // `normalizedValue` reflect the sanitized form.
  assert.equal(phone.value, "+61392466010");
  assert.equal(phone.normalizedValue, "+61392466010");
});

test("toCandidates('apollo', <fixture with primary_phone:{} (FanDuel live shape) and null phone>, 'companies') yields no phone candidate", () => {
  const raw = { organization: { country: "United States", phone: null, primary_phone: {} } };
  const cands = toCandidates("apollo", raw, "companies");
  assert.ok(!byField(cands, "phone"), "an empty primary_phone object plus null phone must not fabricate a candidate");
});

test("toCandidates('apollo', <fixture with no organization key>, 'companies') yields no state/phone candidate", () => {
  const cands = toCandidates("apollo", {}, "companies");
  assert.ok(!byField(cands, "state"));
  assert.ok(!byField(cands, "phone"));
});

// --- ZoomInfo company: no state/hs_state_code/phone producer at all --------------------
// ZOOM_CO_OUTPUT_FIELDS (build_cloud_workflows.py) requests neither field for companies
// today — a scoping choice (mirrors 58-05's `city` precedent), not an API limitation.
test("toCandidates('zoominfo', <fixture with state/phone in the raw attributes>, 'companies') yields no state/hs_state_code/phone candidate", () => {
  const raw = { data: [{ attributes: { country: "Australia", state: "NSW", phone: "0298765432" }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] };
  const cands = toCandidates("zoominfo", raw, "companies");
  for (const f of ["state", "hs_state_code", "phone"]) {
    assert.ok(!byField(cands, f), `zoominfo companies must not emit a ${f} candidate (not a requested outputField)`);
  }
});

// --- D-72-16 regression pin: the two pre-existing lv_country_region_normalized company
// pushes (Lusha, ZoomInfo) must never grow — no code path in THIS plan may add a third.
test("toCandidates: exactly two company branches (lusha, zoominfo) push lv_country_region_normalized; apollo's company branch still does not", () => {
  const lushaCands = toCandidates("lusha",
    { results: [{ id: "x", location: { countryIso2: "AU" }, updateDate: "2026-08-26" }] }, "companies");
  assert.ok(byField(lushaCands, "lv_country_region_normalized"), "lusha company branch keeps its region push");
  const zoomCands = toCandidates("zoominfo",
    { data: [{ attributes: { country: "Australia" }, id: "1", meta: { matchStatus: "FULL_MATCH" } }] }, "companies");
  assert.ok(byField(zoomCands, "lv_country_region_normalized"), "zoominfo company branch keeps its region push");
  const apolloCands = toCandidates("apollo", { organization: { country: "Australia" } }, "companies");
  assert.ok(!byField(apolloCands, "lv_country_region_normalized"), "apollo company branch must not gain a region push in this plan");
});
