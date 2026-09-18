// tests/n8n/discoverySearch.test.mjs
//
// Phase 73.1 Plan 07 Task 2 / Plan 09 Task 2 (round-1 correction) — pure-function
// coverage for n8n/code/discoverySearch.js's buildRequest/buildUrl/normalizeResponse.
// Round 1 of the D-12 live probe (2026-09-18, pickleballaustralia.org.au) found all
// three original [ASSUMED] shapes wrong (ZoomInfo 400, Apollo 422, Lusha 404); these
// tests now pin the corrected shapes documented in each vendor's own current API
// reference. Graph-level behaviours (rung ordering, provider order, the emitted
// per-company ceiling) live in tests/n8n/suggestDiscoveryLane.test.mjs alongside the
// rest of this lane's walker tests.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const { buildRequest, buildUrl, normalizeResponse, DISCOVERY_PEOPLE_CAP, DISCOVERY_ENDPOINTS } =
  require(path.join(ROOT, "n8n/code/discoverySearch.js"));

// DISCOVERY_ENDPOINTS carries the round-1-corrected URLs -- the originals 400/422/404'd
// live; see 73.1-D12-VERDICT.round1.json for the recorded failures.
test("DISCOVERY_ENDPOINTS carries the round-1-corrected URLs", () => {
  assert.equal(DISCOVERY_ENDPOINTS.zoominfo, "https://api.zoominfo.com/gtm/data/v1/contacts/search");
  assert.equal(DISCOVERY_ENDPOINTS.apollo, "https://api.apollo.io/api/v1/mixed_people/api_search");
  assert.equal(DISCOVERY_ENDPOINTS.lusha, "https://api.lusha.com/prospecting/contact/search");
});

// Test 1 — Apollo body carries the domain as an ARRAY (q_organization_domains_list) and
// the title filter as an array, limited to 10, and NO known-identity fields.
test("buildRequest(apollo) carries domain array + title filter + limit 10, no known-identity fields", () => {
  const body = buildRequest("apollo", { domain: "example.org", roleTitles: ["CEO", "President"], limit: 25 });
  assert.deepEqual(body.q_organization_domains_list, ["example.org"]);
  assert.deepEqual(body.person_titles, ["CEO", "President"]);
  assert.equal(body.per_page, DISCOVERY_PEOPLE_CAP, "limit is clamped to the 10-person cap");
  assert.equal(body.page, 1);
  for (const key of ["firstname", "first_name", "lastname", "last_name", "email", "linkedinUrl", "linkedin_url",
                      "q_organization_domains"]) {
    assert.equal(body[key], undefined, `apollo discovery body must not carry ${key}`);
  }
});

// Test 2 — ZoomInfo is a JSON:API ContactSearch envelope keyed on companyWebsite (not
// companyDomain) with a STRING jobTitle (not an array) and NO maxResults attribute --
// pagination moved to the URL (buildUrl), per ZoomInfo's own documented grammar.
test("buildRequest(zoominfo) is a JSON:API ContactSearch envelope keyed on companyWebsite, string jobTitle, no maxResults", () => {
  const body = buildRequest("zoominfo", { domain: "example.org", roleTitles: ["CEO"], limit: 10 });
  assert.equal(body.data.type, "ContactSearch");
  assert.equal(body.data.attributes.companyWebsite, "example.org");
  assert.equal(body.data.attributes.jobTitle, "CEO");
  assert.equal(body.data.attributes.companyDomain, undefined, "companyDomain is not a valid ZoomInfo attribute");
  assert.equal(body.data.attributes.maxResults, undefined, "maxResults is not a valid ZoomInfo attribute");
  assert.equal(body.data.attributes.firstName, undefined);
  assert.equal(body.data.attributes.email, undefined);
});

test("buildRequest(zoominfo) joins multiple role titles with OR", () => {
  const body = buildRequest("zoominfo", { domain: "example.org", roleTitles: ["CEO", "President", "Secretary"] });
  assert.equal(body.data.attributes.jobTitle, "CEO OR President OR Secretary");
});

test("buildUrl(zoominfo) carries pagination as a query string, not a body attribute", () => {
  const url = buildUrl("zoominfo", { limit: 7 });
  assert.equal(url, "https://api.zoominfo.com/gtm/data/v1/contacts/search?page[size]=7&page[number]=1");
});

test("buildUrl(apollo) and buildUrl(lusha) are the bare endpoint, no query string", () => {
  assert.equal(buildUrl("apollo", { limit: 5 }), DISCOVERY_ENDPOINTS.apollo);
  assert.equal(buildUrl("lusha", { limit: 5 }), DISCOVERY_ENDPOINTS.lusha);
});

// Test 3 — Lusha nests each filter one level deeper (`include`), per the round-1
// correction, and NO known-identity fields.
test("buildRequest(lusha) carries domain + title filter under the `include` level, no known-identity fields", () => {
  const body = buildRequest("lusha", { domain: "example.org", roleTitles: ["Secretary"], limit: 10 });
  assert.deepEqual(body.filters.companies.include.domains, ["example.org"]);
  assert.deepEqual(body.filters.contacts.include.jobTitles, ["Secretary"]);
  assert.equal(body.pages.size, 10);
  assert.equal(body.firstname, undefined);
  assert.equal(body.email, undefined);
});

// Test 4 — empty roleTitles -> the rung-2 unfiltered body, still capped at 10 (via
// buildRequest for apollo/lusha, via buildUrl for zoominfo now that pagination moved).
test("buildRequest with empty roleTitles produces the unfiltered rung-2 body, still capped", () => {
  for (const provider of ["zoominfo", "apollo", "lusha"]) {
    const body = buildRequest(provider, { domain: "example.org", roleTitles: [], limit: 999 });
    const json = JSON.stringify(body);
    assert.ok(!json.includes("jobTitle") && !json.includes("person_titles") && !json.includes("jobTitles"),
      `${provider} unfiltered body must carry no title-filter key`);
  }
  assert.equal(buildRequest("apollo", { domain: "x", roleTitles: [], limit: 999 }).per_page, DISCOVERY_PEOPLE_CAP);
  assert.ok(buildUrl("zoominfo", { limit: 999 }).includes(`page[size]=${DISCOVERY_PEOPLE_CAP}`),
    "zoominfo pagination is clamped in the URL, not the body");
  assert.equal(buildRequest("lusha", { domain: "x", roleTitles: [], limit: 999 }).pages.size, DISCOVERY_PEOPLE_CAP);
});

// Test 5 — normalizeResponse turns each provider's fixture into a uniform person shape,
// never an email or phone value (D-12: search-only).
test("normalizeResponse produces a uniform person shape, never email/phone", () => {
  const zoominfo = normalizeResponse("zoominfo", { data: [
    { attributes: { firstName: "Jo", lastName: "Bloggs", jobTitle: "President", email: "jo@example.org" } },
  ] });
  const apollo = normalizeResponse("apollo", { people: [
    { first_name: "Sam", last_name: "Lee", title: "Secretary", email: "sam@example.org", phone: "0400000000" },
  ] });
  const lusha = normalizeResponse("lusha", { contacts: [
    { firstName: "Ali", lastName: "Khan", jobTitle: "Treasurer", email: "ali@example.org" },
  ] });
  for (const [rows, provider] of [[zoominfo, "zoominfo"], [apollo, "apollo"], [lusha, "lusha"]]) {
    assert.equal(rows.length, 1);
    const p = rows[0];
    assert.equal(p.provider, provider);
    assert.ok(p.firstname && p.lastname && p.jobtitle, `${provider} person must carry firstname/lastname/jobtitle`);
    assert.equal(p.email, undefined, `${provider} person must never carry email`);
    assert.equal(p.phone, undefined, `${provider} person must never carry phone`);
  }
});

// Lusha's response envelope is UNCONFIRMED (round 1 never reached a 2xx). Tolerate
// EITHER a `data[]` or a `contacts[]` envelope until round 2 settles which one is real.
test("normalizeResponse(lusha) tolerates either a data[] or a contacts[] response envelope", () => {
  const viaData = normalizeResponse("lusha", { data: [
    { firstName: "Via", lastName: "Data", jobTitle: "GM" },
  ] });
  const viaContacts = normalizeResponse("lusha", { contacts: [
    { firstName: "Via", lastName: "Contacts", jobTitle: "GM" },
  ] });
  assert.equal(viaData[0].lastname, "Data");
  assert.equal(viaContacts[0].lastname, "Contacts");
});

// Test 5b — at most 10 people per provider per company, even when the fixture carries more.
test("normalizeResponse caps at 10 people even when the fixture carries more", () => {
  const many = Array.from({ length: 25 }, (_, i) => ({ first_name: `F${i}`, last_name: "L", title: "Director" }));
  const rows = normalizeResponse("apollo", { people: many });
  assert.equal(rows.length, DISCOVERY_PEOPLE_CAP);
});

// Test 10 (module half) — no normalised person carries any reveal field.
test("normalizeResponse never emits a reveal-shaped field even when the fixture offers one", () => {
  const rows = normalizeResponse("lusha", { contacts: [
    { firstName: "Reveal", lastName: "Case", jobTitle: "GM", mobilePhone: "0411111111", email: "r@example.org" },
  ] });
  assert.deepEqual(Object.keys(rows[0]).sort(), ["firstname", "jobtitle", "lastname", "provider"]);
});

test("unknown provider raises rather than silently returning an empty/malformed body", () => {
  assert.throws(() => buildRequest("bing", { domain: "example.org" }));
  assert.throws(() => buildUrl("bing", { domain: "example.org" }));
  assert.throws(() => normalizeResponse("bing", {}));
});

test("DISCOVERY_ENDPOINTS names exactly the three providers this lane waterfalls through", () => {
  assert.deepEqual(Object.keys(DISCOVERY_ENDPOINTS).sort(), ["apollo", "lusha", "zoominfo"]);
});
