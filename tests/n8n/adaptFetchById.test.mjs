// tests/n8n/adaptFetchById.test.mjs
//
// Phase 16.4-02 Task 1 — UNIT tier for n8n/code/adaptFetchById.js, exercised directly
// against the pure module (createRequire idiom, mirrors tests/n8n/enrichmentGate.test.mjs).
// adaptFetchById.js is the module 16.4-01 shipped; this file characterizes what it
// actually does, never what a future revision might do.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { adaptFetchByIdResult, backfillIdentityKeys } = require(
  path.join(ROOT, "n8n/code/adaptFetchById.js")
);

// === adaptFetchByIdResult ===============================================================

test("adaptFetchByIdResult: missing/undefined item -> lookup_failed, empty existingRecord, error-named diagnostic", () => {
  const result = adaptFetchByIdResult(undefined);
  assert.equal(result.lookup_failed, true);
  assert.deepEqual(result.existingRecord, {});
  assert.equal(result.fetch_diagnostic, "error: no response item");
});

test("adaptFetchByIdResult: null item -> same missing-item path", () => {
  const result = adaptFetchByIdResult(null);
  assert.equal(result.lookup_failed, true);
  assert.deepEqual(result.existingRecord, {});
  assert.equal(result.fetch_diagnostic, "error: no response item");
});

test("adaptFetchByIdResult: { error } -> lookup_failed, diagnostic CARRIES the error text", () => {
  const result = adaptFetchByIdResult({ error: "HubSpot 429: rate limited" });
  assert.equal(result.lookup_failed, true);
  assert.deepEqual(result.existingRecord, {});
  assert.match(result.fetch_diagnostic, /HubSpot 429: rate limited/,
    "the errored diagnostic must carry the actual error text, not a generic label");
});

test("adaptFetchByIdResult: { json: { error } } -> lookup_failed, diagnostic CARRIES the error text", () => {
  const result = adaptFetchByIdResult({ json: { error: "malformed body" } });
  assert.equal(result.lookup_failed, true);
  assert.deepEqual(result.existingRecord, {});
  assert.match(result.fetch_diagnostic, /malformed body/);
});

test("adaptFetchByIdResult: { json: { results: [], total: 0 } } -> lookup_failed, diagnostic DISTINCT from the errored case", () => {
  // Track B property (this is the one case whose meaning DIFFERS from the sibling search
  // adapter's identical input): the id came from HubSpot's own event, so 0 results means
  // deleted/merged/stale-event, not confirmed-absent — a create could not set a
  // server-assigned hs_object_id anyway, so this fails closed rather than creating.
  const result = adaptFetchByIdResult({ json: { results: [], total: 0 } });
  assert.equal(result.lookup_failed, true);
  assert.deepEqual(result.existingRecord, {});
  assert.match(result.fetch_diagnostic, /zero-results/);
  assert.doesNotMatch(result.fetch_diagnostic, /^error:/,
    "the zero-results diagnostic must be distinguishable from the errored-response diagnostic");
});

test("adaptFetchByIdResult: search-envelope match -> lookup_failed false, flat properties spread, hs_object_id preserved", () => {
  const result = adaptFetchByIdResult({
    json: { results: [{ id: "789", properties: { name: "Example Racing League", domain: "exampleracing.example" } }], total: 1 },
  });
  assert.equal(result.lookup_failed, false);
  assert.deepEqual(result.existingRecord, {
    name: "Example Racing League", domain: "exampleracing.example", hs_object_id: "789",
  });
  assert.equal(result.fetch_diagnostic, "ok: matched via search envelope");
});

test("adaptFetchByIdResult: single-object response shape -> lookup_failed false, hs_object_id preserved", () => {
  const result = adaptFetchByIdResult({ json: { id: "456", properties: { email: "a@b.example" } } });
  assert.equal(result.lookup_failed, false);
  assert.deepEqual(result.existingRecord, { email: "a@b.example", hs_object_id: "456" });
  assert.equal(result.fetch_diagnostic, "ok: matched via single object");
});

test("adaptFetchByIdResult: bare-object response shape -> lookup_failed false", () => {
  const result = adaptFetchByIdResult({ json: { id: "999" } });
  assert.equal(result.lookup_failed, false);
  assert.deepEqual(result.existingRecord, { id: "999" });
  assert.equal(result.fetch_diagnostic, "ok: matched via bare object");
});

// === backfillIdentityKeys =================================================================

test("backfillIdentityKeys: contacts, all-null identity_keys + full fetched record -> every field backfilled, domain derived from the backfilled email", () => {
  const out = backfillIdentityKeys(
    "contacts",
    { email: "riley.chen@exampleracing.example", firstname: "Riley", lastname: "Chen",
      company: "Example Racing League", lv_linkedin_url: "https://linkedin.com/in/riley-chen" },
    { email: null, firstName: null, lastName: null, companyName: null, linkedin_url: null, domain: null }
  );
  assert.deepEqual(out, {
    email: "riley.chen@exampleracing.example",
    firstName: "Riley",
    lastName: "Chen",
    companyName: "Example Racing League",
    linkedin_url: "https://linkedin.com/in/riley-chen",
    domain: "exampleracing.example",
  });
});

test("backfillIdentityKeys: contacts, caller's email survives unchanged even when the fetched record carries a DIFFERENT email (fill-only-blanks, never overwrite)", () => {
  const out = backfillIdentityKeys(
    "contacts",
    { email: "riley.chen@exampleracing.example", firstname: "Riley", lastname: "Chen" },
    { email: "caller-supplied@other.example", firstName: null, lastName: null, companyName: null,
      linkedin_url: null, domain: null }
  );
  assert.equal(out.email, "caller-supplied@other.example", "the caller's own email must never be overwritten");
  assert.equal(out.firstName, "Riley", "blank fields still get backfilled from the fetched record");
  assert.equal(out.lastName, "Chen");
  // domain was blank, so it derives from whichever email SURVIVED (the caller's), not the
  // fetched record's — a second proof of the same fill-only-blanks contract.
  assert.equal(out.domain, "other.example");
});

test("backfillIdentityKeys: companies, all-null -> domain (cleaned) and companyName populated from the fetched record", () => {
  const out = backfillIdentityKeys(
    "companies",
    { domain: "https://www.ExampleCo.com/about", name: "Example Co" },
    { domain: null, companyName: null }
  );
  assert.deepEqual(out, { domain: "exampleco.com", companyName: "Example Co" });
});

test("backfillIdentityKeys: empty/absent existingRecord -> input identity_keys returned unchanged, no throw, no invented keys", () => {
  const input = { email: "x@y.example", domain: "y.example" };
  assert.deepEqual(backfillIdentityKeys("contacts", {}, input), input);
  assert.deepEqual(backfillIdentityKeys("contacts", null, input), input);
  assert.deepEqual(backfillIdentityKeys("contacts", undefined, input), input);
});

test("backfillIdentityKeys: an unrecognized objectType does not throw and invents no keys when nothing in the fetched record matches its (contact-shaped) field map", () => {
  // The module has exactly two shapes: companies (objectType === "companies") and
  // everything else (treated as contact-shaped). An objectType this module has never
  // heard of does not throw — it falls through to the contact field map, and since this
  // fetched record carries none of that map's field names, nothing gets backfilled.
  const input = { foo: "bar" };
  const out = backfillIdentityKeys("deals", { unrelated_field: "some value" }, input);
  assert.deepEqual(out, input);
});
