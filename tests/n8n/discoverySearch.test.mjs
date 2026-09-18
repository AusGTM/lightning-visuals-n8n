// tests/n8n/discoverySearch.test.mjs
//
// Phase 73.1 Plan 07 Task 2 — pure-function coverage for n8n/code/discoverySearch.js's
// buildRequest/normalizeResponse. Graph-level behaviours (rung ordering, provider order,
// the emitted per-company ceiling) live in tests/n8n/suggestDiscoveryLane.test.mjs
// alongside the rest of this lane's walker tests.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const { buildRequest, normalizeResponse, DISCOVERY_PEOPLE_CAP, DISCOVERY_ENDPOINTS } =
  require(path.join(ROOT, "n8n/code/discoverySearch.js"));

// Test 1 — Apollo body carries the domain and the title filter and a limit of 10, and
// NO firstname/lastname/email.
test("buildRequest(apollo) carries domain + title filter + limit 10, no known-identity fields", () => {
  const body = buildRequest("apollo", { domain: "example.org", roleTitles: ["CEO", "President"], limit: 25 });
  assert.equal(body.q_organization_domains, "example.org");
  assert.deepEqual(body.person_titles, ["CEO", "President"]);
  assert.equal(body.per_page, DISCOVERY_PEOPLE_CAP, "limit is clamped to the 10-person cap");
  for (const key of ["firstname", "first_name", "lastname", "last_name", "email", "linkedinUrl", "linkedin_url"]) {
    assert.equal(body[key], undefined, `apollo discovery body must not carry ${key}`);
  }
});

// Test 2 — same for zoominfo (JSON:API envelope) and lusha.
test("buildRequest(zoominfo) is a JSON:API ContactSearch envelope, no known-identity fields", () => {
  const body = buildRequest("zoominfo", { domain: "example.org", roleTitles: ["CEO"], limit: 10 });
  assert.equal(body.data.type, "ContactSearch");
  assert.equal(body.data.attributes.companyDomain, "example.org");
  assert.deepEqual(body.data.attributes.jobTitle, ["CEO"]);
  assert.equal(body.data.attributes.maxResults, 10);
  assert.equal(body.data.attributes.firstName, undefined);
  assert.equal(body.data.attributes.email, undefined);
});

test("buildRequest(lusha) carries domain + title filter, no known-identity fields", () => {
  const body = buildRequest("lusha", { domain: "example.org", roleTitles: ["Secretary"], limit: 10 });
  assert.deepEqual(body.filters.companies.domains, ["example.org"]);
  assert.deepEqual(body.filters.contacts.jobTitles, ["Secretary"]);
  assert.equal(body.pages.size, 10);
  assert.equal(body.firstname, undefined);
  assert.equal(body.email, undefined);
});

// Test 3 — empty roleTitles -> the rung-2 unfiltered body, still capped at 10.
test("buildRequest with empty roleTitles produces the unfiltered rung-2 body, still capped", () => {
  for (const provider of ["zoominfo", "apollo", "lusha"]) {
    const body = buildRequest(provider, { domain: "example.org", roleTitles: [], limit: 999 });
    const json = JSON.stringify(body);
    assert.ok(!json.includes("jobTitle") && !json.includes("person_titles") && !json.includes("jobTitles"),
      `${provider} unfiltered body must carry no title-filter key`);
  }
  assert.equal(buildRequest("apollo", { domain: "x", roleTitles: [], limit: 999 }).per_page, DISCOVERY_PEOPLE_CAP);
  assert.equal(buildRequest("zoominfo", { domain: "x", roleTitles: [], limit: 999 }).data.attributes.maxResults,
    DISCOVERY_PEOPLE_CAP);
  assert.equal(buildRequest("lusha", { domain: "x", roleTitles: [], limit: 999 }).pages.size, DISCOVERY_PEOPLE_CAP);
});

// Test 4 — normalizeResponse turns each provider's fixture into a uniform person shape,
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

// Test 5 — at most 10 people per provider per company, even when the fixture carries more.
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
  assert.throws(() => normalizeResponse("bing", {}));
});

test("DISCOVERY_ENDPOINTS names exactly the three providers this lane waterfalls through", () => {
  assert.deepEqual(Object.keys(DISCOVERY_ENDPOINTS).sort(), ["apollo", "lusha", "zoominfo"]);
});
