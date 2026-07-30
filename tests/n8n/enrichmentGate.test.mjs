// tests/n8n/enrichmentGate.test.mjs
//
// Phase 16-02 Task 2 — enrichmentGate.js's FIRST direct unit test (previously only
// exercised indirectly, per 16-RESEARCH.md Wave-0 gap). Proves RT-5's already-built
// freshness behavior: a fresh required field skips, a stale one re-enriches, and a
// present value with NO _verified_at is conservatively treated as stale.
// enrichmentGate.js is FROZEN — this file characterizes it, never modifies it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { decideAction } = require(path.join(ROOT, "n8n/code/enrichmentGate.js"));

const REQUIRED = ["lv_org_type", "lv_produces_content"];
const POLICY = {
  lv_org_type: { stale_after_days: 180 },
  lv_produces_content: { stale_after_days: 180 },
};
const NOW = "2026-07-23T00:00:00Z";

function daysAgoIso(days) {
  return new Date(Date.parse(NOW) - days * 86400000).toISOString();
}

// FRESH: BOTH required fields present AND BOTH _verified_at ~10 days ago -> skip.
// (16-RESEARCH.md's original fixture set only ONE required field, which short-circuits
// to `enrich` via missingFields before staleness is ever evaluated — review kimi LOW,
// fixed here: both fields must be present for the skip branch to actually exercise RT-5.)
test("RT-5: both required fields present and verified ~10 days ago -> skip", () => {
  const existingRecord = {
    lv_org_type: "governing_body_league",
    lv_org_type_verified_at: daysAgoIso(10),
    lv_produces_content: true,
    lv_produces_content_verified_at: daysAgoIso(10),
  };
  const gate = decideAction(existingRecord, REQUIRED, POLICY, NOW);
  assert.equal(gate.action, "skip");
  assert.deepEqual(gate.staleFields, []);
  assert.deepEqual(gate.missingFields, []);
});

// STALE: both present, but verified 200 days ago (> 180-day TTL) -> enrich.
test("RT-5: both required fields present but verified 200 days ago -> enrich (stale)", () => {
  const existingRecord = {
    lv_org_type: "governing_body_league",
    lv_org_type_verified_at: daysAgoIso(200),
    lv_produces_content: true,
    lv_produces_content_verified_at: daysAgoIso(200),
  };
  const gate = decideAction(existingRecord, REQUIRED, POLICY, NOW);
  assert.equal(gate.action, "enrich");
  assert.deepEqual(gate.staleFields.sort(), ["lv_org_type", "lv_produces_content"]);
  assert.deepEqual(gate.missingFields, []);
});

// NEVER-VERIFIED: both present, NO _verified_at at all -> treated as stale (unknown
// freshness == needs validation), not skip.
test("RT-5: both required fields present with no _verified_at -> enrich (unknown freshness)", () => {
  const existingRecord = {
    lv_org_type: "governing_body_league",
    lv_produces_content: true,
  };
  const gate = decideAction(existingRecord, REQUIRED, POLICY, NOW);
  assert.equal(gate.action, "enrich");
  assert.deepEqual(gate.staleFields.sort(), ["lv_org_type", "lv_produces_content"]);
  assert.deepEqual(gate.missingFields, []);
});

// Sanity: a genuinely missing required field still dominates over staleness (existing
// documented behavior, not new — proves this test file agrees with the source comment).
test("RT-5 sanity: a missing required field enriches for 'missing', not 'stale'", () => {
  const existingRecord = { lv_org_type: "governing_body_league", lv_org_type_verified_at: daysAgoIso(10) };
  const gate = decideAction(existingRecord, REQUIRED, POLICY, NOW);
  assert.equal(gate.action, "enrich");
  assert.deepEqual(gate.missingFields, ["lv_produces_content"]);
});
