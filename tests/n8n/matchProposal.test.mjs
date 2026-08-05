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
const { laneOf, mediumCandidates, summarizeMatch } = require(path.join(ROOT, "n8n/code/matchProposal.js"));

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

test("order is input order — no sort, no tie-break", () => {
  const hits = [
    { id: "1", properties: { lastname: "Doe", company: "Gold Coast Turf Club B" } },
    { id: "2", properties: { lastname: "Doe", company: "Gold Coast Turf Club A" } },
  ];
  const out = mediumCandidates(hits, IDENTITY);
  assert.deepEqual(out.map((c) => c.hs_object_id), ["1", "2"]);
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

test("auto is true for exactly one tier: high", () => {
  const cases = [
    summarizeMatch({ lane: "fetch_by_id", existingRecord: { hs_object_id: "1" } }),
    summarizeMatch({ lane: "email", existingRecord: {} }),
    summarizeMatch({ lane: "name", candidates: [{ hs_object_id: "1" }] }),
    summarizeMatch({ lane: "name", candidates: [] }),
    summarizeMatch({ lane: "none" }),
    summarizeMatch({ lane: "email", lookupFailed: true }),
  ];
  const autos = cases.map((c) => c.auto);
  assert.deepEqual(autos, [true, false, false, false, false, false]);
});
