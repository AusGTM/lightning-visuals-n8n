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
import { execFileSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const {
  buildRequest, buildUrl, normalizeResponse, capRoleTitles, titlesForFamilies,
  DISCOVERY_PEOPLE_CAP, DISCOVERY_ENDPOINTS, ZOOMINFO_JOBTITLE_MAX,
} = require(path.join(ROOT, "n8n/code/discoverySearch.js"));

// Python oracle: PyYAML parses the REAL shipped vocabulary, no JS-side YAML
// reimplementation and no hand-written fixture -- same idiom
// tests/n8n/columnMapIdentityParity.test.mjs already uses for config/column_mapping.yaml.
// A fixture would not catch a regression in the SHIPPED file's own family ordering (the
// exact class of bug D-11c closes: the last-declared families getting cut).
const PY = path.join(ROOT, ".venv/bin/python");
function shippedRoleFamilyMap() {
  const script =
    "import json,yaml;" +
    "cfg=yaml.safe_load(open('operator-claude-plugin/config/role_vocabulary.yaml'));" +
    "print(json.dumps({f['label']: f.get('members', []) for f in cfg['families']}))";
  return JSON.parse(execFileSync(PY, ["-c", script], { cwd: ROOT }).toString());
}

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

// Isolation findings, 73.1-09 Task 3 follow-through (execution 12666, 2026-09-18): a real
// 42-title role vocabulary OR-joins to 757 chars, and ZoomInfo's own 400 (PFAPI0006) says
// "jobTitle must be less than 500 characters" -- rung 1 could never succeed as originally
// built. ZOOMINFO_JOBTITLE_MAX is the vendor's own ceiling, capRoleTitles is the greedy
// stop-before-cap builder, and buildRequest must apply it so no caller can bypass it.
test("ZOOMINFO_JOBTITLE_MAX is the vendor-documented ceiling", () => {
  assert.equal(ZOOMINFO_JOBTITLE_MAX, 500);
});

test("capRoleTitles keeps titles whole under the cap, never splits mid-title, reports used/dropped", () => {
  // 20 titles of 30 chars (+" OR " joiners) = well past 500 chars joined.
  const titles = Array.from({ length: 20 }, (_, i) => `Title Number ${String(i).padStart(2, "0")} Long Role`);
  const { joined, used, dropped } = capRoleTitles(titles, 500);
  assert.ok(joined.length < 500, `joined length ${joined.length} must be strictly under the cap`);
  assert.ok(used.length > 0 && used.length < titles.length, "some but not all titles fit");
  assert.equal(used.length + dropped, titles.length);
  assert.deepEqual(joined.split(" OR "), used, "kept titles must appear whole, in original order");
});

test("capRoleTitles is a no-op when the joined string already fits", () => {
  const titles = ["CEO", "President", "Secretary"];
  const { joined, used, dropped } = capRoleTitles(titles, 500);
  assert.equal(joined, "CEO OR President OR Secretary");
  assert.deepEqual(used, titles);
  assert.equal(dropped, 0);
});

test("buildRequest(zoominfo) applies the 500-char cap itself -- a caller cannot bypass it", () => {
  const titles = Array.from({ length: 42 }, (_, i) => `Some Fairly Long Senior Role Title ${i}`);
  const joinedUncapped = titles.join(" OR ");
  assert.ok(joinedUncapped.length >= 500, "fixture must actually exceed the cap to test anything");
  const body = buildRequest("zoominfo", { domain: "example.org", roleTitles: titles });
  assert.ok(body.data.attributes.jobTitle.length < 500);
  assert.notEqual(body.data.attributes.jobTitle, joinedUncapped);
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

// ---- Plan 10 (D-11a/D-11c): titlesForFamilies over the SHIPPED vocabulary ----------

test("73.1-10/D-11c: titlesForFamilies over the shipped vocabulary survives all four D-11c members into a rung-1 request with zero drop", () => {
  const map = shippedRoleFamilyMap();
  const titles = titlesForFamilies(map, ["Executive Officer", "Board Chair"]);
  const { dropped } = capRoleTitles(titles, ZOOMINFO_JOBTITLE_MAX);
  assert.equal(dropped, 0, "two families' worth of titles must fit well under the 500-char cap");
  const body = buildRequest("zoominfo", { domain: "example.org", roleTitles: titles });
  const jobTitle = body.data.attributes.jobTitle;
  for (const member of ["Executive Officer", "Board Chair", "Board Chairwoman", "Chairwoman"]) {
    assert.ok(jobTitle.includes(member), `jobTitle must include "${member}"`);
  }
});

test("73.1-10: an absent or empty role_families selection falls back to every member in map order -- deliberate, not an accident", () => {
  const map = shippedRoleFamilyMap();
  const everyMember = Object.values(map).flat();
  assert.deepEqual(titlesForFamilies(map, null), everyMember);
  assert.deepEqual(titlesForFamilies(map, []), everyMember);
  assert.deepEqual(titlesForFamilies(map, undefined), everyMember);
});

test("73.1-10: an unknown family label contributes nothing and does not throw -- the lane is not a second validator", () => {
  const map = shippedRoleFamilyMap();
  assert.doesNotThrow(() => titlesForFamilies(map, ["Not A Real Family"]));
  assert.deepEqual(titlesForFamilies(map, ["Not A Real Family"]), []);
  // A real family alongside an unknown one still contributes its own members.
  assert.deepEqual(
    titlesForFamilies(map, ["Not A Real Family", "Executive Officer"]),
    ["Executive Officer"],
  );
});

test("unknown/retired provider raises rather than silently returning an empty/malformed body", () => {
  for (const provider of ["bing", "apollo", "lusha"]) {
    assert.throws(() => buildRequest(provider, { domain: "example.org" }));
    assert.throws(() => buildUrl(provider, { domain: "example.org" }));
    assert.throws(() => normalizeResponse(provider, {}));
  }
});
