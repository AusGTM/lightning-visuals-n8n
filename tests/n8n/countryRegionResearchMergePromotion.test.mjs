// tests/n8n/countryRegionResearchMergePromotion.test.mjs
//
// REQ-country-region-policy closure gap (companion to
// researchRequestCountryRegionContract.test.mjs): now that the research lane can
// actually produce lv_country_region_normalized (Build Research Request / Validate
// Research Output), prove the value reaches the Merge Company node's research fold and
// is decided by the SAME field-policy threshold (system_owned, min_confidence 75,
// mergeCompanies.js DEFAULT_COMPANY_POLICY) that Phase 21-04 wired but the research lane
// could never before exercise.
//
// Reuses tests/n8n/mergeCompanyStaleTimestamp.test.mjs / sponsorshipReliantCopyLoop.
// test.mjs's `runMergeCompany()` harness verbatim — the `new Function(...)` idiom over
// the repo's own committed jsCode, no external or untrusted input interpolated.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadMergeCompanyBody() {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n/wf_enrichment_cloud.json"), "utf8"));
  const node = wf.nodes.find((n) => n.name === "Merge Company");
  return node.parameters.jsCode;
}

function runMergeCompany(jsCode, row) {
  const $input = { all: () => [{ json: row }], get item() { return { json: row }; } };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, row, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}

// Row fixture: a research_candidate carrying ONLY lv_country_region_normalized (plus one
// already-covered control field, lv_content_type, that promotes with no evidence gate) at
// a configurable confidence, and no firmographic (`scored`) candidate for region so the
// research fold is the only possible source of a decision on this field.
function row(regionValue, confidence) {
  return {
    identity_keys: { domain: "exampleracing.example" },
    existingRecord: { domain: "exampleracing.example", name: "Example Racing League" },
    scored: { best: {}, winners: {}, sourcesByField: {} },
    research_candidate: {
      matched: true,
      confidence,
      data: { lv_content_type: ["live_broadcast"], lv_country_region_normalized: regionValue },
      evidence_by_field: {},
    },
  };
}

const MERGE_COMPANY_BODY = loadMergeCompanyBody();

test("(a) VACUITY GUARD: merge result is real and the control field promotes", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, row("AU", 90));
  assert.ok(out.merge && typeof out.merge === "object", "merge is a real object, not the null skip branch");
  assert.equal(out.merge.canonicalPatch.lv_content_type[0], "live_broadcast",
    "control field must promote, proving the row/harness are wired correctly");
});

test("(b) confidence >= 75 (field policy threshold): lv_country_region_normalized promotes", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, row("AU", 80));
  assert.equal(out.merge.canonicalPatch.lv_country_region_normalized, "AU",
    "REQ-country-region-policy: a confident research region value must reach canonicalPatch");
  const decision = out.merge.decisions.find((d) => d.field === "lv_country_region_normalized");
  assert.ok(decision, "a decision entry must exist for the field");
  assert.equal(decision.decision, "promote");
});

test("(c) confidence < 75: lv_country_region_normalized stays needs_review, never promoted", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, row("AU", 60));
  assert.ok(!("lv_country_region_normalized" in out.merge.canonicalPatch),
    "below-threshold confidence must not promote the field");
  const decision = out.merge.decisions.find((d) => d.field === "lv_country_region_normalized");
  assert.ok(decision, "a decision entry must still exist (needs_review, not silently dropped)");
  assert.equal(decision.decision, "needs_review");
});

test("(d) EDGE: a null region value produces no key, control field still promotes", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, row(null, 90));
  assert.ok(!("lv_country_region_normalized" in out.merge.canonicalPatch),
    "tri-state null must be skipped by the existing blank/tri-state guard");
  assert.equal(out.merge.canonicalPatch.lv_content_type[0], "live_broadcast",
    "control field must still promote");
});

test("(e) EDGE: an unlisted region value ('Freedonia') that slipped past Validate Research Output " +
     "is now caught by Merge Company's OWN enum guard (Phase 31, BUG 28) — staged, never promoted", () => {
  // Superseded by Phase 31: Merge Company now DOES re-validate every enum-bound candidate
  // (n8n/code/hubspotEnums.js), so an unmappable value is a second line of defense rather
  // than relying solely on Validate Research Output upstream — the exact defense-in-depth
  // T-31-02 (31-01-PLAN.md threat register) exists for: a value that slips past the
  // upstream guard must still never reach canonicalPatch or the review queue.
  const out = runMergeCompany(MERGE_COMPANY_BODY, row("Freedonia", 90));
  assert.ok(!("lv_country_region_normalized" in out.merge.canonicalPatch),
    "an unmappable region value must never reach canonicalPatch");
  const decision = out.merge.decisions.find((d) => d.field === "lv_country_region_normalized");
  assert.equal(decision.decision, "stage_only",
    "an unmappable enum value stages, it is never offered for human review");
  assert.equal(out.merge.provenance.lv_country_region_normalized.validation_status, "rejected");
});
