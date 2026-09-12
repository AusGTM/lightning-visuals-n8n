// tests/n8n/overflowSlots.test.mjs
//
// Phase 72 Plan 05 (D-72-11/D-72-12) — the second phone/mobile a waterfall disagreement
// supplies lands in a SINGLE overflow slot instead of being discarded. Exercised
// against BOTH JS engines (mergeContacts.js / mergeCompanies.js) from ONE shared
// fixture table, mirrored in tests/test_merge_policy.py for the Python oracle (Phase 46
// parity). `opts.rankedByField[field]` is the caller's PRE-SORTED candidate list
// (n8n/code/scoreEnrichment.js's scoreCandidates().ranked) — the engines never re-sort,
// only dedupe on normalizedValue and split winner / single overflow / provenance tail.
//
// Run: node --test tests/n8n/overflowSlots.test.mjs
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

function rc(field, source, value, normalizedValue) {
  return { field, source, value, normalizedValue: normalizedValue != null ? normalizedValue : value };
}

// --- (1) Winner takes the primary slot, runner-up takes `_2`, both provenanced -------

test("mergeContacts overflow: zoominfo wins mobilephone, apollo runner-up lands in lv_mobilephone_2", () => {
  const ranked = { mobilephone: [
    rc("mobilephone", "zoominfo", "+61400000001"),
    rc("mobilephone", "apollo", "+61400000002"),
  ] };
  const result = mergeContacts({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.mobilephone, "+61400000001");
  assert.equal(result.canonicalPatch.lv_mobilephone_2, "+61400000002");
  assert.equal(result.provenance.mobilephone.source, "zoominfo");
  assert.equal(result.provenance.lv_mobilephone_2.source, "apollo");
});

test("mergeCompanies overflow: winner takes phone, runner-up lands in lv_phone_2", () => {
  const ranked = { phone: [
    rc("phone", "zoominfo", "+61212340001"),
    rc("phone", "apollo", "+61212340002"),
  ] };
  const result = mergeCompanies({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.phone, "+61212340001");
  assert.equal(result.canonicalPatch.lv_phone_2, "+61212340002");
  assert.equal(result.provenance.phone.source, "zoominfo");
  assert.equal(result.provenance.lv_phone_2.source, "apollo");
});

// --- (2) A third candidate is provenance-only; no `_3` slot ever exists --------------

test("mergeContacts overflow: a third distinct candidate rides on the primary field's provenance only, no lv_mobilephone_3 anywhere", () => {
  const ranked = { mobilephone: [
    rc("mobilephone", "zoominfo", "+61400000001"),
    rc("mobilephone", "apollo", "+61400000002"),
    rc("mobilephone", "lusha", "+61400000003"),
  ] };
  const result = mergeContacts({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.lv_mobilephone_3, undefined);
  assert.equal(result.provenance.lv_mobilephone_3, undefined);
  assert.deepEqual(result.provenance.mobilephone.overflow_tail,
    [{ source: "lusha", value: "+61400000003" }]);
  const blob = JSON.stringify(result);
  assert.ok(!blob.includes("mobilephone_3"), "no _3 slot key anywhere in the result");
});

// --- (3) Two candidates agreeing on the SAME normalized value is not an overflow ------

test("mergeContacts overflow: two candidates with equal normalizedValue fill the slot once, lv_mobilephone_2 absent", () => {
  const ranked = { mobilephone: [
    rc("mobilephone", "zoominfo", "0400 000 001", "0400000001"),
    rc("mobilephone", "apollo", "0400000001", "0400000001"),
  ] };
  const result = mergeContacts({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.mobilephone, "0400 000 001");
  assert.equal(result.canonicalPatch.lv_mobilephone_2, undefined);
  assert.equal(result.provenance.lv_mobilephone_2, undefined);
});

// --- (3b) Two candidates agreeing only under case folding is not an overflow (WR-02) -

test("mergeContacts overflow: mixed-case agreeing candidates on phone do not manufacture lv_phone_2 (WR-02)", () => {
  const ranked = { phone: [
    rc("phone", "zoominfo", "+61 2 9663 8460 EXT 12"),
    rc("phone", "apollo", "+61 2 9663 8460 ext 12"),
  ] };
  const result = mergeContacts({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.lv_phone_2, undefined);
  assert.equal(result.provenance.lv_phone_2, undefined);
});

test("mergeCompanies overflow: mixed-case agreeing candidates on phone do not manufacture lv_phone_2 (WR-02)", () => {
  const ranked = { phone: [
    rc("phone", "zoominfo", "+61 2 9663 8460 EXT 12"),
    rc("phone", "apollo", "+61 2 9663 8460 ext 12"),
  ] };
  const result = mergeCompanies({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.lv_phone_2, undefined);
  assert.equal(result.provenance.lv_phone_2, undefined);
});

// --- (4) The `_2` slot obeys its own fill_blank_only policy --------------------------

test("mergeContacts overflow: existing non-blank lv_mobilephone_2 is not overwritten (fill_blank_only)", () => {
  const ranked = { mobilephone: [
    rc("mobilephone", "zoominfo", "+61400000001"),
    rc("mobilephone", "apollo", "+61400000002"),
  ] };
  const result = mergeContacts({ lv_mobilephone_2: "existing-value" }, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.lv_mobilephone_2, undefined);
  const decision = result.decisions.find((d) => d.field === "lv_mobilephone_2");
  assert.equal(decision.decision, "stage_only");
});

// --- (5) No candidate for a field with no configured overflow slot leaks a "_2" ------

test("mergeContacts overflow: a field with no configured overflow slot (email) never gains a _2 property", () => {
  const ranked = { email: [
    rc("email", "zoominfo", "a@example.com"),
    rc("email", "apollo", "b@example.com"),
  ] };
  const result = mergeContacts({}, {}, undefined,
    { source: "waterfall", confidence: 90, now: NOW, rankedByField: ranked });
  assert.equal(result.canonicalPatch.email, "a@example.com");
  assert.equal(result.canonicalPatch.lv_email_2, undefined);
  assert.deepEqual(result.provenance.email.overflow_tail, [{ source: "apollo", value: "b@example.com" }]);
});

// --- (6) No judge call / no material-conflict suppression for phone or email ---------

test("escalation config: phone/mobilephone/email are absent from MATERIAL_CONFLICT_GROUPS (RO-2 untouched)", () => {
  const { MATERIAL_CONFLICT_GROUPS } = require(path.join(ROOT, "n8n/code/escalation.generated.js"));
  const watched = new Set(MATERIAL_CONFLICT_GROUPS.flatMap((g) => g.fields));
  assert.equal(watched.has("phone"), false);
  assert.equal(watched.has("mobilephone"), false);
  assert.equal(watched.has("email"), false);
});
