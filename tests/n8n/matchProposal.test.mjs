// tests/n8n/matchProposal.test.mjs
//
// Phase 36 Plan 01 — the pure-function pin on n8n/code/matchProposal.js, the module
// `Build Identity` and the match-lane adapters inline. Task 1 covers `laneOf`; Task 2
// adds `mediumCandidates`/`summarizeMatch` in this same file.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  laneOf, mediumCandidates, summarizeMatch, isReturnOnly,
  linkedinAgreement, verifiedLinkedinHits,
} = require(path.join(ROOT, "n8n/code/matchProposal.js"));

// --- fetch_by_id: object_id present, no email — mirrors IF Bare Event's true branch ------

test("object_id present and no email selects fetch_by_id", () => {
  assert.equal(laneOf({ object_id: "123", identity_keys: {} }), "fetch_by_id");
});

test("object_id present with an email selects email, not fetch_by_id (matches IF Bare Event false)", () => {
  assert.equal(
    laneOf({ object_id: "123", identity_keys: { email: "jane@example.com" } }),
    "email"
  );
});

// --- email lane ----------------------------------------------------------------------------

test("no object_id, email present selects email", () => {
  assert.equal(laneOf({ identity_keys: { email: "jane@example.com" } }), "email");
});

test("an empty-string email is falsy and must not select email", () => {
  assert.equal(laneOf({ identity_keys: { email: "" } }), "none");
});

test("an empty-string email with object_id falls through to fetch_by_id", () => {
  assert.equal(laneOf({ object_id: "123", identity_keys: { email: "" } }), "fetch_by_id");
});

// --- linkedin lane (Phase 61 Plan 02, D-61-05 CORRECTED) ------------------------------------

test("a linkedin_url with no email selects linkedin", () => {
  assert.equal(
    laneOf({ identity_keys: { linkedin_url: "https://www.linkedin.com/in/x/" } }),
    "linkedin"
  );
});

test("email and linkedin_url both present selects email — email wins", () => {
  assert.equal(
    laneOf({ identity_keys: { email: "jane@example.com", linkedin_url: "https://linkedin.com/in/x" } }),
    "email"
  );
});

test("linkedin_url and lastName+companyName both present selects linkedin — a strong key outranks the weak pair (D-61-03)", () => {
  assert.equal(
    laneOf({ identity_keys: {
      linkedin_url: "https://linkedin.com/in/x", lastName: "Doe", companyName: "Gold Coast Turf Club",
    } }),
    "linkedin"
  );
});

test("a whitespace-only linkedin_url is not a present key and yields none", () => {
  assert.equal(laneOf({ identity_keys: { linkedin_url: "   " } }), "none");
});

// --- name lane -----------------------------------------------------------------------------

test("lastName and companyName both present, no email/object_id, selects name", () => {
  assert.equal(
    laneOf({ identity_keys: { lastName: "Doe", companyName: "Gold Coast Turf Club" } }),
    "name"
  );
});

test("lastName present but companyName absent does not select name", () => {
  assert.equal(laneOf({ identity_keys: { lastName: "Doe" } }), "none");
});

test("a whitespace-only companyName does not select name", () => {
  assert.equal(
    laneOf({ identity_keys: { lastName: "Doe", companyName: "   " } }),
    "none"
  );
});

// --- none lane -------------------------------------------------------------------------------

test("nothing searchable selects none", () => {
  assert.equal(laneOf({ identity_keys: {} }), "none");
});

test("a missing identity_keys object entirely does not throw and selects none without object_id", () => {
  let out;
  assert.doesNotThrow(() => { out = laneOf({}); });
  assert.equal(out, "none");
});

test("a missing identity_keys object with an object_id selects fetch_by_id", () => {
  assert.equal(laneOf({ object_id: "123" }), "fetch_by_id");
});

test("laneOf called with nothing at all does not throw and selects none", () => {
  let out;
  assert.doesNotThrow(() => { out = laneOf(); });
  assert.equal(out, "none");
});

// --- object_id truthiness: number 0 vs string "0" --------------------------------------------

test("object_id as the number 0 is falsy and does not select fetch_by_id", () => {
  assert.equal(laneOf({ object_id: 0, identity_keys: {} }), "none");
});

test('object_id as the string "0" is truthy and selects fetch_by_id', () => {
  assert.equal(laneOf({ object_id: "0", identity_keys: {} }), "fetch_by_id");
});

// ============================================================================================
// Task 2: mediumCandidates — a CONTAINS_TOKEN hit is re-verified by value, never trusted as-is
// ============================================================================================

const IDENTITY = { lastName: "Doe", companyName: "Gold Coast Turf Club" };

test("a hit with matching lastname (case-insensitive) and a shared company token is kept", () => {
  const hits = [{ id: "1", properties: {
    lastname: "doe", firstname: "Jane", email: "jane@example.com",
    jobtitle: "Director", company: "Gold Coast Turf Club",
  } }];
  const out = mediumCandidates(hits, IDENTITY);
  assert.deepEqual(out, [{
    hs_object_id: "1", firstname: "Jane", lastname: "doe",
    email: "jane@example.com", jobtitle: "Director", company: "Gold Coast Turf Club",
  }]);
});

test("a wrong-surname hit yields zero candidates — Definition of Done item 4", () => {
  const hits = [{ id: "1", properties: { lastname: "Smith", company: "Gold Coast Turf Club" } }];
  const out = mediumCandidates(hits, IDENTITY);
  assert.deepEqual(out, []);
});

test("a matching surname but no shared company token yields zero candidates", () => {
  const hits = [{ id: "1", properties: { lastname: "Doe", company: "Unrelated Enterprises" } }];
  const out = mediumCandidates(hits, IDENTITY);
  assert.deepEqual(out, []);
});

test("a kept candidate is projected to exactly the six named keys, nothing else", () => {
  const hits = [{ id: "1", properties: {
    lastname: "Doe", firstname: "Jane", email: "jane@example.com",
    jobtitle: "Director", company: "Gold Coast Turf Club",
    phone: "+61400000000", hs_lead_status: "NEW",
  } }];
  const out = mediumCandidates(hits, IDENTITY);
  assert.deepEqual(Object.keys(out[0]).sort(), [
    "company", "email", "firstname", "hs_object_id", "jobtitle", "lastname",
  ]);
});

test("a non-array searchResults returns an empty array, never throws", () => {
  assert.doesNotThrow(() => assert.deepEqual(mediumCandidates(null, IDENTITY), []));
  assert.doesNotThrow(() => assert.deepEqual(mediumCandidates(undefined, IDENTITY), []));
  assert.doesNotThrow(() => assert.deepEqual(mediumCandidates("nope", IDENTITY), []));
});

test("a hit with no properties is dropped, not thrown on", () => {
  const out = mediumCandidates([{ id: "1" }], IDENTITY);
  assert.deepEqual(out, []);
});

test("a row with no lastName or no companyName yields zero candidates", () => {
  const hit = [{ id: "1", properties: { lastname: "Doe", company: "Gold Coast Turf Club" } }];
  assert.deepEqual(mediumCandidates(hit, { companyName: "Gold Coast Turf Club" }), []);
  assert.deepEqual(mediumCandidates(hit, { lastName: "Doe" }), []);
});

// --------------------------------------------------------------------------------------
// F1 (2026-08-25) — requireCompanyToken:false, the weaker fallback search's
// re-verification. A contact created by the ingest lane leaves `company` (text) null
// (associated to a company OBJECT instead) — the exact live mechanism proven on contact
// 347569451461 / Football NSW, execution 11948.
// --------------------------------------------------------------------------------------

test("requireCompanyToken:false keeps a lastname-matching hit even with a blank company property", () => {
  const hits = [{ id: "347569451461", properties: {
    lastname: "Tsatsimas", firstname: "John", email: null, jobtitle: null, company: null,
  } }];
  const out = mediumCandidates(hits, { lastName: "Tsatsimas", companyName: "Football NSW" },
    { requireCompanyToken: false });
  assert.deepEqual(out, [{
    hs_object_id: "347569451461", firstname: "John", lastname: "Tsatsimas",
    email: null, jobtitle: null, company: null,
  }]);
});

test("requireCompanyToken defaults to true — a 2-arg call is byte-identical to before this option existed", () => {
  const hits = [{ id: "1", properties: { lastname: "Doe", company: "Unrelated Enterprises" } }];
  assert.deepEqual(mediumCandidates(hits, IDENTITY), []);
});

test("requireCompanyToken:false still enforces lastname equality", () => {
  const hits = [{ id: "1", properties: { lastname: "Smith", company: null } }];
  const out = mediumCandidates(hits, { lastName: "Tsatsimas", companyName: "Football NSW" },
    { requireCompanyToken: false });
  assert.deepEqual(out, []);
});

test("requireCompanyToken:false narrows to a matching firstname when one was supplied", () => {
  const hits = [
    { id: "1", properties: { lastname: "Tsatsimas", firstname: "John", company: null } },
    { id: "2", properties: { lastname: "Tsatsimas", firstname: "Maria", company: null } },
  ];
  const out = mediumCandidates(
    hits, { firstName: "John", lastName: "Tsatsimas", companyName: "Football NSW" },
    { requireCompanyToken: false });
  assert.deepEqual(out.map((c) => c.hs_object_id), ["1"]);
});

test("requireCompanyToken:false keeps every lastname hit when no firstname was supplied", () => {
  const hits = [
    { id: "1", properties: { lastname: "Tsatsimas", firstname: "John", company: null } },
    { id: "2", properties: { lastname: "Tsatsimas", firstname: "Maria", company: null } },
  ];
  const out = mediumCandidates(
    hits, { lastName: "Tsatsimas", companyName: "Football NSW" },
    { requireCompanyToken: false });
  assert.deepEqual(out.map((c) => c.hs_object_id), ["1", "2"]);
});

test("a firstname on the company-token-verified (default) path is never filtered on — scoped to the fallback only", () => {
  const hits = [{ id: "1", properties: {
    lastname: "Doe", firstname: "Someone Else", company: "Gold Coast Turf Club",
  } }];
  const out = mediumCandidates(hits, { firstName: "Jane", ...IDENTITY });
  assert.deepEqual(out.map((c) => c.hs_object_id), ["1"], (
    "the default (company-token-verified) path must ignore firstName entirely"
  ));
});

test("order is input order — no sort, no tie-break", () => {
  const hits = [
    { id: "1", properties: { lastname: "Doe", company: "Gold Coast Turf Club B" } },
    { id: "2", properties: { lastname: "Doe", company: "Gold Coast Turf Club A" } },
  ];
  const out = mediumCandidates(hits, IDENTITY);
  assert.deepEqual(out.map((c) => c.hs_object_id), ["1", "2"]);
});

// ============================================================================================
// verifiedLinkedinHits / linkedinAgreement — the strong-key re-verification (T-61-05,
// REVIEW-02). A hit surviving the server-side filter is a narrowing, never a verdict.
// ============================================================================================

test("a stored value differing only in trailing slash matches", () => {
  const hits = [{ id: "1", properties: { lv_linkedin_url: "https://www.linkedin.com/in/robert-cavallucci-14698741/" } }];
  const out = verifiedLinkedinHits(hits, "https://www.linkedin.com/in/robert-cavallucci-14698741");
  assert.deepEqual(out.map((h) => h.id), ["1"]);
});

test("a stored value differing only in scheme/host case matches", () => {
  const hits = [{ id: "1", properties: { lv_linkedin_url: "HTTPS://LinkedIn.com/in/x" } }];
  const out = verifiedLinkedinHits(hits, "https://linkedin.com/in/x");
  assert.deepEqual(out.map((h) => h.id), ["1"]);
});

test("a stored value with a query string matches an input without one", () => {
  const hits = [{ id: "1", properties: { lv_linkedin_url: "https://linkedin.com/in/x?trk=public_profile" } }];
  const out = verifiedLinkedinHits(hits, "https://linkedin.com/in/x");
  assert.deepEqual(out.map((h) => h.id), ["1"]);
});

test("a different profile under the same host does not match", () => {
  const hits = [{ id: "1", properties: { lv_linkedin_url: "https://linkedin.com/in/someone-else" } }];
  assert.deepEqual(verifiedLinkedinHits(hits, "https://linkedin.com/in/x"), []);
});

test("a contact stored ONLY under native hs_linkedin_url is found (REVIEW-02)", () => {
  const hits = [{ id: "1", properties: { hs_linkedin_url: "https://linkedin.com/in/x" } }];
  const out = verifiedLinkedinHits(hits, "https://linkedin.com/in/x");
  assert.deepEqual(out.map((h) => h.id), ["1"]);
});

test("a contact matching under BOTH properties is one hit, not two", () => {
  const hits = [{ id: "1", properties: {
    lv_linkedin_url: "https://linkedin.com/in/x", hs_linkedin_url: "https://linkedin.com/in/x",
  } }];
  const out = verifiedLinkedinHits(hits, "https://linkedin.com/in/x");
  assert.equal(out.length, 1);
});

test("a self-disagreeing record (lv_linkedin_url and hs_linkedin_url point at different profiles) is never a verified hit", () => {
  const hits = [{ id: "1", properties: {
    lv_linkedin_url: "https://linkedin.com/in/x", hs_linkedin_url: "https://linkedin.com/in/someone-else",
  } }];
  assert.deepEqual(verifiedLinkedinHits(hits, "https://linkedin.com/in/x"), []);
  assert.equal(linkedinAgreement(hits[0].properties), null);
});

test("two verified hits both survive — dedup and cardinality are separate steps", () => {
  const hits = [
    { id: "1", properties: { lv_linkedin_url: "https://linkedin.com/in/x" } },
    { id: "2", properties: { hs_linkedin_url: "https://linkedin.com/in/x/" } },
  ];
  const out = verifiedLinkedinHits(hits, "https://linkedin.com/in/x");
  assert.deepEqual(out.map((h) => h.id).sort(), ["1", "2"]);
});

test("verifiedLinkedinHits never throws on malformed input", () => {
  assert.deepEqual(verifiedLinkedinHits(null, "https://linkedin.com/in/x"), []);
  assert.deepEqual(verifiedLinkedinHits([{ id: "1" }], "https://linkedin.com/in/x"), []);
  assert.deepEqual(verifiedLinkedinHits([{ id: "1", properties: {} }], ""), []);
});

// ============================================================================================
// summarizeMatch({lane:"linkedin", ...}) — 0/1/>1 verified hits (REVIEW-03/HIGH-3): a
// closed cardinality rule, never a two-outcome shortcut (REVIEW-C4).
// ============================================================================================

test("linkedin lane, zero verified candidates, is none", () => {
  const out = summarizeMatch({ lane: "linkedin", candidates: [] });
  assert.equal(out.tier, "none");
  assert.equal(out.auto, false);
});

test("linkedin lane, exactly one verified candidate, is high and auto", () => {
  const out = summarizeMatch({ lane: "linkedin", candidates: [{ hs_object_id: "1" }] });
  assert.equal(out.tier, "high");
  assert.equal(out.auto, true);
  assert.deepEqual(out.candidates, []);
});

test("linkedin lane, more than one verified candidate, is medium carrying both — never a pick", () => {
  const out = summarizeMatch({
    lane: "linkedin",
    candidates: [{ hs_object_id: "1" }, { hs_object_id: "2" }],
  });
  assert.equal(out.tier, "medium");
  assert.equal(out.auto, false);
  assert.equal(out.candidates.length, 2);
});

test("linkedin lane, a failed lookup, is unknown — never none (a linkedin-only row is never `unknown` on a SUCCESSFUL search)", () => {
  const out = summarizeMatch({ lane: "linkedin", lookupFailed: true });
  assert.equal(out.tier, "unknown");
  assert.equal(out.auto, false);
});

// ============================================================================================
// Task 2: summarizeMatch — unknown vs none, auto only for high
// ============================================================================================

test("a failed match search returns tier unknown, never none", () => {
  const out = summarizeMatch({ lane: "email", lookupFailed: true });
  assert.equal(out.tier, "unknown");
  assert.equal(out.auto, false);
  assert.deepEqual(out.candidates, []);
  assert.equal(typeof out.reason, "string");
});

test("lane fetch_by_id with a non-empty existingRecord is a high auto-match", () => {
  const out = summarizeMatch({ lane: "fetch_by_id", existingRecord: { hs_object_id: "1" } });
  assert.equal(out.tier, "high");
  assert.equal(out.auto, true);
});

test("lane email with a non-empty existingRecord is a high auto-match", () => {
  const out = summarizeMatch({ lane: "email", existingRecord: { hs_object_id: "1" } });
  assert.equal(out.tier, "high");
  assert.equal(out.auto, true);
});

test("lane email with an empty existingRecord and no failure is none", () => {
  const out = summarizeMatch({ lane: "email", existingRecord: {} });
  assert.equal(out.tier, "none");
  assert.equal(out.auto, false);
});

test("lane fetch_by_id with an empty existingRecord and no failure is none", () => {
  const out = summarizeMatch({ lane: "fetch_by_id", existingRecord: {} });
  assert.equal(out.tier, "none");
  assert.equal(out.auto, false);
});

test("lane name with one or more candidates is medium, never auto", () => {
  const out = summarizeMatch({ lane: "name", candidates: [{ hs_object_id: "1" }] });
  assert.equal(out.tier, "medium");
  assert.equal(out.auto, false);
  assert.deepEqual(out.candidates, [{ hs_object_id: "1" }]);
});

test("lane name with zero candidates is none", () => {
  const out = summarizeMatch({ lane: "name", candidates: [] });
  assert.equal(out.tier, "none");
  assert.equal(out.auto, false);
  assert.deepEqual(out.candidates, []);
});

test("lane none (nothing to search on, the search never ran) is unknown, never none", () => {
  const out = summarizeMatch({ lane: "none" });
  assert.equal(out.tier, "unknown");
  assert.equal(out.auto, false);
  assert.match(out.reason, /no searchable identity/i);
});

test("a failed search AND a never-run search are BOTH unknown, distinguishable from none", () => {
  const a = summarizeMatch({ lane: "email", lookupFailed: true });
  const b = summarizeMatch({ lane: "none" });
  assert.equal(a.tier, "unknown");
  assert.equal(b.tier, "unknown");
});

// ============================================================================================
// Quick task 260904-5a8: summarizeMatch's "company" arm — a CALL-SITE LITERAL, never a
// `laneOf` return value and never carried on a row (premise_corrections C1). Fixes a false
// sentence: a companies row used to fall through to the "none" arm and report contacts
// vocabulary ("no email, object id, or name+company pair") about a row that was never
// searched by any of those keys. gating_boundary: `match.tier` gates downstream behaviour,
// `match.reason` does not — this arm keeps tier "unknown"/auto false, same as the
// fallthrough it replaces, and reads no `existingRecord`.
// ============================================================================================

test("lane company is unknown/non-auto and its reason names domain-then-name resolution, not contacts vocabulary", () => {
  const out = summarizeMatch({ lane: "company" });
  assert.equal(out.tier, "unknown");
  assert.equal(out.auto, false);
  assert.deepEqual(out.candidates, []);
  assert.match(out.reason, /domain/i);
  assert.match(out.reason, /company name/i);
  assert.doesNotMatch(out.reason, /email/i);
  assert.doesNotMatch(out.reason, /object id/i);
  assert.doesNotMatch(out.reason, /name\+company/i);
});

test("lane company with lookupFailed true still returns the lookupFailed verdict — the failure arm runs first, unchanged", () => {
  const out = summarizeMatch({ lane: "company", lookupFailed: true });
  assert.equal(out.tier, "unknown");
  assert.equal(out.auto, false);
  assert.equal(out.reason, "the match search failed to run");
  assert.deepEqual(out.candidates, []);
});

test("lane none is byte-identical to today, reason string included, after the company arm was added", () => {
  const out = summarizeMatch({ lane: "none" });
  assert.equal(out.tier, "unknown");
  assert.equal(out.auto, false);
  assert.equal(
    out.reason,
    "no searchable identity — the row has no email, object id, or name+company pair"
  );
  assert.deepEqual(out.candidates, []);
});

// ============================================================================================
// Phase 36 Plan 04, Task 1: isReturnOnly — the two-state write-guard predicate. Not an
// allow-list of mode names: `mode` is either the write literal (case/whitespace-
// insensitive) or it is return-only, with no third state. A typo therefore fails safe
// toward returning proposals, never toward writing (36-CONTEXT.md §6).
// ============================================================================================

test("mode absent (undefined) is false — today's behaviour, byte-identical", () => {
  assert.equal(isReturnOnly(undefined), false);
});

test("mode null is false — same as absent", () => {
  assert.equal(isReturnOnly(null), false);
});

test('mode "write" is false', () => {
  assert.equal(isReturnOnly("write"), false);
});

test('mode "WRITE" is false — case-insensitive', () => {
  assert.equal(isReturnOnly("WRITE"), false);
});

test('mode " Write " is false — whitespace-insensitive', () => {
  assert.equal(isReturnOnly(" Write "), false);
});

test('mode "propose" is true', () => {
  assert.equal(isReturnOnly("propose"), true);
});

test('a typo mode "proprose" is true — fails safe toward returning proposals, not writing', () => {
  assert.equal(isReturnOnly("proprose"), true);
});

test("an empty string mode is true", () => {
  assert.equal(isReturnOnly(""), true);
});

test("mode as the number 0 is true", () => {
  assert.equal(isReturnOnly(0), true);
});

test("mode as an empty object is true", () => {
  assert.equal(isReturnOnly({}), true);
});

test("isReturnOnly never throws for any input", () => {
  for (const v of [undefined, null, "write", "propose", 0, {}, [], Symbol("x"), () => {}]) {
    assert.doesNotThrow(() => isReturnOnly(v));
  }
});

test("auto is true for exactly one tier: high", () => {
  const cases = [
    summarizeMatch({ lane: "fetch_by_id", existingRecord: { hs_object_id: "1" } }),
    summarizeMatch({ lane: "email", existingRecord: {} }),
    summarizeMatch({ lane: "name", candidates: [{ hs_object_id: "1" }] }),
    summarizeMatch({ lane: "name", candidates: [] }),
    summarizeMatch({ lane: "linkedin", candidates: [{ hs_object_id: "1" }] }),
    summarizeMatch({ lane: "linkedin", candidates: [{ hs_object_id: "1" }, { hs_object_id: "2" }] }),
    summarizeMatch({ lane: "linkedin", candidates: [] }),
    summarizeMatch({ lane: "none" }),
    summarizeMatch({ lane: "email", lookupFailed: true }),
  ];
  const autos = cases.map((c) => c.auto);
  assert.deepEqual(autos, [true, false, false, false, true, false, false, false, false]);
});
