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
