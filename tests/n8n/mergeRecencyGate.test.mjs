// tests/n8n/mergeRecencyGate.test.mjs
//
// Phase 72 Plan 04 — the recency/TTL gate for `stale_refreshable` fields, exercised
// against BOTH JS engines (mergeContacts.js / mergeCompanies.js) from ONE shared
// fixture table. The Python oracle (src/merge_policy.py::deterministic_gate) is
// exercised against the mirrored table in tests/test_merge_policy.py — the two files
// together are the Phase 46 parity evidence: all three engines must agree
// field-for-field on every fixture.
//
// Before this plan, EVERY non-blank `stale_refreshable` candidate answered
// needs_review unconditionally ("Refresh candidate requires review in MVP.") — no TTL,
// no recency, no staleness check existed anywhere in the gate. This file proves the
// real branch: a genuinely stale existing value with a genuinely newer provider
// observation promotes; everything else (fresh, unknown freshness, no clock on the
// candidate) still refuses exactly as before.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { mergeContacts } = require(path.join(ROOT, "n8n/code/mergeContacts.js"));
const { mergeCompanies } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

const NOW = "2026-09-12T00:00:00.000Z";
const STALE_200D = "2026-02-24T00:00:00.000Z"; // ~200 days before NOW
const FRESH_30D = "2026-08-13T00:00:00.000Z";  // ~30 days before NOW

// --- Contacts: jobtitle (stale_after_days: 180) ---------------------------------------

test("mergeContacts recency: stale existing value + provider observation newer -> promote", () => {
  const result = mergeContacts(
    { jobtitle: "Old Title", lv_jobtitle_verified_at: STALE_200D },
    { jobtitle: "New Title" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW,
      historyByField: { jobtitle: STALE_200D } }
  );
  assert.equal(result.decisions.find((d) => d.field === "jobtitle").decision, "promote");
  assert.equal(result.canonicalPatch.jobtitle, "New Title");
});

test("mergeContacts recency: fresh existing value (30d) -> needs_review, unchanged pre-72 reason", () => {
  const result = mergeContacts(
    { jobtitle: "Old Title" },
    { jobtitle: "New Title" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW,
      historyByField: { jobtitle: FRESH_30D } }
  );
  const d = result.decisions.find((x) => x.field === "jobtitle");
  assert.equal(d.decision, "needs_review");
  assert.equal(d.reason, "Refresh candidate requires review in MVP.");
});

test("mergeContacts recency: no history timestamp at all -> needs_review naming unknown freshness (byte-identical pre-72 outcome)", () => {
  const result = mergeContacts(
    { jobtitle: "Old Title" },
    { jobtitle: "New Title" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW } // no historyByField at all
  );
  const d = result.decisions.find((x) => x.field === "jobtitle");
  assert.equal(d.decision, "needs_review");
  assert.match(d.reason.toLowerCase(), /unknown freshness/);
});

test("mergeContacts recency: stale existing value but candidate is CSV-sourced (no clock) -> needs_review (recency, not merely staleness)", () => {
  const result = mergeContacts(
    { jobtitle: "Old Title" },
    { jobtitle: "New Title" },
    undefined,
    { source: "csv", confidence: 80, now: NOW,
      historyByField: { jobtitle: STALE_200D } }
  );
  const d = result.decisions.find((x) => x.field === "jobtitle");
  assert.equal(d.decision, "needs_review");
  assert.notEqual(d.reason, "Refresh candidate requires review in MVP.",
    "must be a DISTINCT reason from the plain-fresh case -- this is a recency refusal, not a staleness refusal");
});

test("mergeContacts recency: per-field source resolution -- opts.sourceByField[field] names a provider -> promote; names csv -> needs_review (same stale fixture)", () => {
  const provider = mergeContacts(
    { jobtitle: "Old Title" },
    { jobtitle: "New Title" },
    undefined,
    { source: "csv", confidence: 90, now: NOW,
      sourceByField: { jobtitle: "zoominfo" },
      historyByField: { jobtitle: STALE_200D } }
  );
  assert.equal(provider.decisions.find((d) => d.field === "jobtitle").decision, "promote");

  const csv = mergeContacts(
    { jobtitle: "Old Title" },
    { jobtitle: "New Title" },
    undefined,
    { source: "csv", confidence: 90, now: NOW,
      sourceByField: { jobtitle: "csv" },
      historyByField: { jobtitle: STALE_200D } }
  );
  assert.equal(csv.decisions.find((d) => d.field === "jobtitle").decision, "needs_review");
});

test("mergeContacts recency: blank current value still promotes unconditionally (unchanged pre-72 arm)", () => {
  const result = mergeContacts(
    {},
    { jobtitle: "New Title" },
    undefined,
    { source: "csv", confidence: 80, now: NOW }
  );
  assert.equal(result.decisions.find((d) => d.field === "jobtitle").decision, "promote");
});

test("mergeContacts recency: fill_blank_only field (mobilephone) is unaffected by this plan -- non-blank existing value still stages", () => {
  const result = mergeContacts(
    { mobilephone: "+61 400 000 000" },
    { mobilephone: "+61 411 111 111" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW,
      historyByField: { mobilephone: STALE_200D } }
  );
  assert.equal(result.decisions.find((d) => d.field === "mobilephone").decision, "stage_only");
});

test("mergeContacts: opts.now absent falls back to real wall clock -- verified_at is a parseable, recent ISO timestamp", () => {
  const before = Date.now();
  const result = mergeContacts({}, { jobtitle: "New Title" }, undefined, { source: "csv", confidence: 80 });
  const after = Date.now();
  const stamp = Date.parse(result.provenance.jobtitle.verified_at);
  assert.ok(stamp >= before && stamp <= after, "verified_at falls within the call's own wall-clock window");
});

// --- Companies: industry (stale_after_days: 365) --------------------------------------

const STALE_400D = "2025-08-08T00:00:00.000Z"; // >365 days before NOW
const FRESH_100D = "2026-06-04T00:00:00.000Z"; // <365 days before NOW

test("mergeCompanies recency: stale existing value (400d, TTL 365d) + provider observation newer -> promote", () => {
  const result = mergeCompanies(
    { industry: "Sports" },
    { industry: "Media Production" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW,
      historyByField: { industry: STALE_400D } }
  );
  assert.equal(result.decisions.find((d) => d.field === "industry").decision, "promote");
});

test("mergeCompanies recency: fresh existing value (100d, TTL 365d) -> needs_review, unchanged pre-72 reason", () => {
  const result = mergeCompanies(
    { industry: "Sports" },
    { industry: "Media Production" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW,
      historyByField: { industry: FRESH_100D } }
  );
  const d = result.decisions.find((x) => x.field === "industry");
  assert.equal(d.decision, "needs_review");
  assert.equal(d.reason, "Refresh candidate requires review in MVP.");
});

test("mergeCompanies recency: no history timestamp -> needs_review naming unknown freshness", () => {
  const result = mergeCompanies(
    { industry: "Sports" },
    { industry: "Media Production" },
    undefined,
    { source: "zoominfo", confidence: 90, now: NOW }
  );
  const d = result.decisions.find((x) => x.field === "industry");
  assert.equal(d.decision, "needs_review");
  assert.match(d.reason.toLowerCase(), /unknown freshness/);
});

test("mergeCompanies recency: stale existing value but candidate carries no clock (source resolves to hubspot_native) -> needs_review", () => {
  const result = mergeCompanies(
    { industry: "Sports" },
    { industry: "Media Production" },
    undefined,
    { source: "hubspot_native", confidence: 90, now: NOW,
      historyByField: { industry: STALE_400D } }
  );
  const d = result.decisions.find((x) => x.field === "industry");
  assert.equal(d.decision, "needs_review");
  assert.notEqual(d.reason, "Refresh candidate requires review in MVP.");
});

test("mergeCompanies recency: per-field source resolution via opts.sourceByField", () => {
  const provider = mergeCompanies(
    { industry: "Sports" },
    { industry: "Media Production" },
    undefined,
    { source: "hubspot_native", confidence: 90, now: NOW,
      sourceByField: { industry: "zoominfo" },
      historyByField: { industry: STALE_400D } }
  );
  assert.equal(provider.decisions.find((d) => d.field === "industry").decision, "promote");

  const nonProvider = mergeCompanies(
    { industry: "Sports" },
    { industry: "Media Production" },
    undefined,
    { source: "hubspot_native", confidence: 90, now: NOW,
      sourceByField: { industry: "hubspot_native" },
      historyByField: { industry: STALE_400D } }
  );
  assert.equal(nonProvider.decisions.find((d) => d.field === "industry").decision, "needs_review");
});

test("mergeCompanies recency: manual_protected field (domain) is unaffected by this plan", () => {
  const result = mergeCompanies(
    { domain: "example.example" },
    { domain: "other.example" },
    undefined,
    { source: "zoominfo", confidence: 95, now: NOW,
      historyByField: { domain: STALE_400D } }
  );
  assert.equal(result.decisions.find((d) => d.field === "domain").decision, "stage_only");
});
