// tests/n8n/matchProposal.test.mjs
//
// Phase 36 Plan 01 — the pure-function pin on n8n/code/matchProposal.js, the module
// `Build Identity` and the match-lane adapters inline. Task 1 covers `laneOf` only;
// `mediumCandidates`/`summarizeMatch` are added by Task 2 in this same file.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { laneOf } = require(path.join(ROOT, "n8n/code/matchProposal.js"));

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
