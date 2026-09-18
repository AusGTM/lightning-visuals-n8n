// tests/n8n/discoverySearch.test.mjs
//
// Phase 73.1 Plan 07 Task 2 / Plan 09 Task 2 — pure-function coverage for
// n8n/code/discoverySearch.js's buildRequest/buildUrl/normalizeResponse.
// ZoomInfo-only, per the operator's D-12 ruling (2026-09-18, 73.1-D12-VERDICT.json):
// "ZoomInfo retained as tier-2 source, others (Apollo/Lusha) dropped for search phase.
// Full waterfall only used on enrich." Apollo and Lusha are no longer exported by this
// module at all — see the module's own header comment for the measured reasons (Apollo
// obfuscates the last name on preview; Lusha's preview carries no name/title). Graph-
// level behaviours (the emitted per-company ceiling) live in
// tests/n8n/suggestDiscoveryLane.test.mjs alongside the rest of this lane's walker tests.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const { buildRequest, buildUrl, normalizeResponse, DISCOVERY_PEOPLE_CAP, DISCOVERY_ENDPOINTS } =
  require(path.join(ROOT, "n8n/code/discoverySearch.js"));

test("DISCOVERY_ENDPOINTS names exactly one provider: zoominfo", () => {
  assert.deepEqual(Object.keys(DISCOVERY_ENDPOINTS), ["zoominfo"]);
  assert.equal(DISCOVERY_ENDPOINTS.zoominfo, "https://api.zoominfo.com/gtm/data/v1/contacts/search");
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

// Test 4 — empty roleTitles -> the rung-2 unfiltered body, still capped at 10 (via
// buildUrl now that pagination moved off the body).
test("buildRequest with empty roleTitles produces the unfiltered rung-2 body, still capped", () => {
  const body = buildRequest("zoominfo", { domain: "example.org", roleTitles: [], limit: 999 });
  const json = JSON.stringify(body);
  assert.ok(!json.includes("jobTitle"), "zoominfo unfiltered body must carry no title-filter key");
  assert.ok(buildUrl("zoominfo", { limit: 999 }).includes(`page[size]=${DISCOVERY_PEOPLE_CAP}`),
    "zoominfo pagination is clamped in the URL, not the body");
});

// Test 5 — normalizeResponse turns ZoomInfo's fixture into a uniform person shape, never
// an email or phone value (D-12: search-only).
test("normalizeResponse(zoominfo) produces a uniform person shape, never email/phone", () => {
  const rows = normalizeResponse("zoominfo", { data: [
    { attributes: { firstName: "Jo", lastName: "Bloggs", jobTitle: "President", email: "jo@example.org" } },
  ] });
  assert.equal(rows.length, 1);
  const p = rows[0];
  assert.equal(p.provider, "zoominfo");
  assert.ok(p.firstname && p.lastname && p.jobtitle, "person must carry firstname/lastname/jobtitle");
  assert.equal(p.email, undefined, "person must never carry email");
  assert.equal(p.phone, undefined, "person must never carry phone");
});

// Test 5b — at most 10 people even when the fixture carries more.
test("normalizeResponse caps at 10 people even when the fixture carries more", () => {
  const many = Array.from({ length: 25 }, (_, i) => ({
    attributes: { firstName: `F${i}`, lastName: "L", jobTitle: "Director" } }));
  const rows = normalizeResponse("zoominfo", { data: many });
  assert.equal(rows.length, DISCOVERY_PEOPLE_CAP);
});

// Test 10 (module half) — no normalised person carries any reveal field.
test("normalizeResponse never emits a reveal-shaped field even when the fixture offers one", () => {
  const rows = normalizeResponse("zoominfo", { data: [
    { attributes: { firstName: "Reveal", lastName: "Case", jobTitle: "GM",
                     mobilePhone: "0411111111", email: "r@example.org" } },
  ] });
  assert.deepEqual(Object.keys(rows[0]).sort(), ["firstname", "jobtitle", "lastname", "provider"]);
});

test("unknown/retired provider raises rather than silently returning an empty/malformed body", () => {
  for (const provider of ["bing", "apollo", "lusha"]) {
    assert.throws(() => buildRequest(provider, { domain: "example.org" }));
    assert.throws(() => buildUrl(provider, { domain: "example.org" }));
    assert.throws(() => normalizeResponse(provider, {}));
  }
});
