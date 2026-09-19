// tests/n8n/pairCreateOutcome.test.mjs
//
// Phase 73 Plan 06, Task 1 (D-73-01, F-A6 Pitfall 0) — unit coverage for the pure
// identity-join module, independent of any graph. `n8n/code/pairCreateOutcome.js` is
// CommonJS (inlined into an n8n Code node by scripts/build_cloud_workflows.py via
// `inline()`), so it is `require()`d here rather than imported — the same pattern every
// other n8n/code/*.js unit-test file in this directory uses.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { pairCreateOutcome, identityKey } = require("../../n8n/code/pairCreateOutcome.js");

function carriedRow(overrides) {
  return {
    action: "create",
    outcome: "net_new",
    contact_id: null,
    hs_object_id: null,
    email: null,
    company_id: null,
    properties: {},
    ...overrides,
  };
}

function successResponse(overrides) {
  return { id: "new-1", properties: {}, ...overrides };
}

test("identityKey: email wins over every other rung, casefolded and trimmed", () => {
  assert.equal(identityKey({ email: "  Person@Example.com  " }), "email:person@example.com");
  assert.equal(
    identityKey({ email: null, firstname: "Ann", lastname: "Lee", company: "Acme" }),
    "name:ann|lee|acme"
  );
  assert.equal(identityKey({ linkedin_url: "  HTTPS://LinkedIn.com/in/Ann  " }),
    "linkedin:https://linkedin.com/in/ann");
});

test("identityKey: returns null when no rung of the ladder resolves", () => {
  assert.equal(identityKey({}), null);
  assert.equal(identityKey({ firstname: "Ann" }), null); // incomplete name group
});

test("a shrinking response set never mis-associates a later row (the Pitfall 0 case)", () => {
  // Three carried rows, only rows 1 and 3's create responses arrive (row 2's create
  // silently returned nothing) — the exact shape that broke combineByPosition: row 3's
  // response used to pair with row 2's carried row once row 2's own response went
  // missing, one gap shifting every later pairing out of alignment.
  const row1 = carriedRow({ email: "row1@example.com" });
  const row2 = carriedRow({ email: "row2@example.com" });
  const row3 = carriedRow({ email: "row3@example.com" });
  const resp1 = successResponse({ id: "hs-1", properties: { email: "row1@example.com" } });
  const resp3 = successResponse({ id: "hs-3", properties: { email: "row3@example.com" } });

  const out = pairCreateOutcome([row1, row2, row3, resp1, resp3]);

  assert.equal(out.length, 3, "one output item per carried row");
  const byEmail = Object.fromEntries(out.map((r) => [r.email, r]));
  assert.equal(byEmail["row1@example.com"].create_outcome, "success");
  assert.equal(byEmail["row1@example.com"].id, "hs-1");
  assert.equal(byEmail["row3@example.com"].create_outcome, "success");
  assert.equal(byEmail["row3@example.com"].id, "hs-3",
    "row 3 must pair with its OWN response, never row 2's slot under the old positional pairing");
  assert.equal(byEmail["row2@example.com"].create_outcome, "none",
    "row 2 received no response — marked, never silently dropped, never paired with someone else's");
});

test("output order follows the carried rows' own order, not the response order", () => {
  const row1 = carriedRow({ email: "a@example.com" });
  const row2 = carriedRow({ email: "b@example.com" });
  // Responses arrive in the OPPOSITE order to the carried rows.
  const resp2 = successResponse({ id: "hs-b", properties: { email: "b@example.com" } });
  const resp1 = successResponse({ id: "hs-a", properties: { email: "a@example.com" } });

  const out = pairCreateOutcome([resp2, resp1, row1, row2]);
  assert.deepEqual(out.map((r) => r.email), ["a@example.com", "b@example.com"]);
  assert.equal(out[0].id, "hs-a");
  assert.equal(out[1].id, "hs-b");
});

test("a carried row with an uncomputable identity key is refused, never guessed", () => {
  const row = carriedRow({ email: null, firstname: null, lastname: null, company: null });
  const resp = successResponse({ id: "hs-1" });
  const out = pairCreateOutcome([row, resp]);
  assert.equal(out.length, 1);
  assert.equal(out[0].create_outcome, "refused");
  assert.equal(out[0].create_outcome_reason, "no computable identity key");
});

test("two carried rows sharing one identity key are both refused, not paired to one response", () => {
  const row1 = carriedRow({ email: "dup@example.com" });
  const row2 = carriedRow({ email: "dup@example.com" });
  const resp = successResponse({ id: "hs-1", properties: { email: "dup@example.com" } });
  const out = pairCreateOutcome([row1, row2, resp]);
  assert.equal(out.length, 2);
  for (const item of out) {
    assert.equal(item.create_outcome, "refused");
    assert.equal(item.create_outcome_reason, "identity key matches more than one carried row");
  }
});

test("a key matching more than one response refuses that row rather than picking one", () => {
  const row = carriedRow({ email: "ambig@example.com" });
  const resp1 = successResponse({ id: "hs-1", properties: { email: "ambig@example.com" } });
  const resp2 = successResponse({ id: "hs-2", properties: { email: "ambig@example.com" } });
  const out = pairCreateOutcome([row, resp1, resp2]);
  assert.equal(out.length, 1);
  assert.equal(out[0].create_outcome, "refused");
  assert.equal(out[0].create_outcome_reason, "identity key matches more than one create response");
});

test("an error item (no action, no id) pairs onto its own row as create_outcome: error", () => {
  const row = carriedRow({ email: "fails@example.com" });
  const errorItem = { message: "Contact already exists. Existing ID: 999", properties: { email: "fails@example.com" } };
  const out = pairCreateOutcome([row, errorItem]);
  assert.equal(out.length, 1);
  assert.equal(out[0].create_outcome, "error");
  assert.equal(out[0].create_error, errorItem);
});

test("name-and-company identity ladder pairs a row with no email", () => {
  const row = carriedRow({ email: null, firstname: "Sam", lastname: "Lee", company: "Acme Pty" });
  const resp = successResponse({
    id: "hs-9",
    properties: { firstname: "Sam", lastname: "Lee", company: "Acme Pty" },
  });
  const out = pairCreateOutcome([row, resp]);
  assert.equal(out.length, 1);
  assert.equal(out[0].create_outcome, "success");
  assert.equal(out[0].id, "hs-9");
});

// --- Phase 74 Plan 05 Task 1 (D-74-04/D-74-05, CR-02) — the explicit `_create_error`
// stamp beats both shape checks, and correctness no longer rests on a guessed shape. ---

test("a stamped item carrying a non-empty action field still classifies as an error outcome (stamp beats the carried-row test)", () => {
  const row = carriedRow({ email: "stamped-action@example.com" });
  // Shaped exactly like a CARRIED row (non-empty `action`) — the OLD classifier would
  // have pushed this to `carried`, producing a SECOND (bogus) carried row that shares
  // `row`'s own identity key and refuses BOTH via "identity key matches more than one
  // carried row". The stamp must route it to `responses` before that shape test ever runs.
  const stampedLikeCarried = {
    action: "create", outcome: "net_new", email: "stamped-action@example.com",
    _create_error: true,
  };
  const out = pairCreateOutcome([row, stampedLikeCarried]);
  assert.equal(out.length, 1, "the stamped item must never become a second carried row");
  assert.equal(out[0].create_outcome, "error");
  assert.equal(out[0].create_error, stampedLikeCarried);
});

test("a stamped item carrying an id still classifies as an error outcome (stamp beats the success-response test)", () => {
  const row = carriedRow({ email: "stamped-id@example.com" });
  // Shaped exactly like a SUCCESS response (a usable `id`) — a real HubSpot error body
  // that happens to echo a conflicting record's id (e.g. "Existing ID: 555" surfaced as
  // a structured field) must never be read as a success just because `id` is present.
  const stampedLikeSuccess = {
    id: "555", properties: { email: "stamped-id@example.com" }, _create_error: true,
  };
  const out = pairCreateOutcome([row, stampedLikeSuccess]);
  assert.equal(out.length, 1);
  assert.equal(out[0].create_outcome, "error");
  assert.notEqual(out[0].create_outcome, "success");
});

test("an item with no stamp classifies exactly as it does today: carried row, then success response, then error", () => {
  const row = carriedRow({ email: "unstamped@example.com" });
  const success = successResponse({ id: "hs-1", properties: { email: "unstamped@example.com" } });
  const out = pairCreateOutcome([row, success]);
  assert.equal(out[0].create_outcome, "success", "no stamp present — the shape ladder is unchanged");
});

test("mirrors the graph stub (tests/n8n/ingestCreateErrorLane.test.mjs) with its invented `properties.email` removed: the rejected row's own error item still pairs as create_outcome error, via the stamp, not the guessed shape", () => {
  // The hand-written graph-level stub (D-74-05's UNOBSERVED tag) invents
  // `properties: { email: EMAIL_2 }` on the error item so `identityKey()`'s `_emailOf()`
  // resolves — CR-02's exact flagged assumption. This reconstructs that same 3-row batch
  // at the unit level with that nested shape GONE, replaced by only what this module's
  // header now documents a real error item might plausibly carry back: the outbound
  // request's own top-level fields, spread onto the response the way an n8n HTTP node's
  // error item can echo request data (T-73-06-01's own premise). Without the stamp, that
  // spread makes the item carry `action`/`outcome` too — shaped exactly like a THIRD
  // carried row that collides with row 2's own identity key, so the OLD classifier
  // refuses BOTH (never reports a failure at all — the silent-wrong-answer bug D-74-04
  // exists to close). With the stamp read first, it is unambiguously an error, joined via
  // its own top-level `email`.
  const row1 = carriedRow({ email: "survivor1@laneone.example" });
  const row2 = carriedRow({ email: "rejected@lanetwo.example" });
  const row3 = carriedRow({ email: "survivor3@lanethree.example" });
  const resp1 = successResponse({ id: "hs-created-1", properties: { email: "survivor1@laneone.example" } });
  const resp3 = successResponse({ id: "hs-created-3", properties: { email: "survivor3@lanethree.example" } });
  const rejectedNoInventedShape = {
    ...carriedRow({ email: "rejected@lanetwo.example" }), // the request echo, no nested properties.email
    message: "Contact already exists. Existing ID: 555",
    _create_error: true,
  };

  const out = pairCreateOutcome([row1, row2, row3, resp1, resp3, rejectedNoInventedShape]);
  const byEmail = Object.fromEntries(out.map((r) => [r.email, r]));

  assert.equal(byEmail["survivor1@laneone.example"].create_outcome, "success");
  assert.equal(byEmail["survivor3@lanethree.example"].create_outcome, "success");
  assert.equal(byEmail["rejected@lanetwo.example"].create_outcome, "error",
    "still a create failure with the invented properties.email shape removed");
  assert.notEqual(byEmail["rejected@lanetwo.example"].create_outcome, "refused",
    "must not be silently swallowed as an identity collision with its own carried row");
});

test("the carried row's own properties win over the response's on a key clash (preferLast parity)", () => {
  const row = carriedRow({ email: "row@example.com", properties: { email: "row@example.com", lv_enrichment_requested: "true" } });
  const resp = successResponse({ id: "hs-7", properties: { email: "row@example.com" } });
  const out = pairCreateOutcome([row, resp]);
  assert.equal(out[0].properties.lv_enrichment_requested, "true",
    "the carried row's own properties (the request actually sent) must survive the join");
  assert.equal(out[0].id, "hs-7", "the response's id must still survive (carried row has none)");
});
