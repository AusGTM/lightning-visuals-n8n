// tests/n8n/juneCandidateFold.test.mjs
//
// Phase 41 Task 1 (D-08 tracer): proves a June-2026 validation-dataset company travels
// through the deployed "Merge Company" node's candidate set and out the far end as a
// promoted canonical value with june_2026-sourced provenance. Task 3 adds the
// precedence filter, the D-04 disagreement gate, and the native firmographic band fold
// on top of this same node — those get their own test cases appended here.
//
// Reuses tests/n8n/countryRegionResearchMergePromotion.test.mjs's `runMergeCompany()`
// harness verbatim (the `new Function(...)` idiom over the repo's own committed jsCode —
// no external or untrusted input is ever interpolated into the function body).
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

const MERGE_COMPANY_BODY = loadMergeCompanyBody();

// Racing NSW (15008671672) -- config/june_candidates.json's own worked example
// (41-01-PLAN.md Task 1 acceptance): lv_org_type governing_body_league, lv_produces_
// content "true", lv_country_region_normalized AU, _confidence 85, evidence a real URL.
const RACING_NSW_ID = "15008671672";

function baseRow(hsObjectId, overrides = {}) {
  return {
    identity_keys: { domain: "example.example" },
    existingRecord: { hs_object_id: hsObjectId, domain: "example.example", name: "Example Co" },
    scored: { best: {}, winners: {}, sourcesByField: {} },
    ...overrides,
  };
}

test("(a) a June-tabled id with no research candidate promotes lv_org_type from june_2026 with evidence", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, baseRow(RACING_NSW_ID));
  assert.ok(out.merge && typeof out.merge === "object", "merge is a real object, not the null skip branch");
  assert.equal(out.merge.canonicalPatch.lv_org_type, "governing_body_league");
  const entry = out.merge.provenance.lv_org_type;
  assert.ok(entry, "provenance entry present");
  assert.equal(entry.source, "june_2026");
  assert.ok(entry.evidence_url && entry.evidence_url.length > 0, "evidence_url must be non-empty");
});

test("(b) the same June id also promotes lv_produces_content and lv_country_region_normalized from june_2026", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, baseRow(RACING_NSW_ID));
  assert.equal(out.merge.canonicalPatch.lv_produces_content, "true");
  assert.equal(out.merge.canonicalPatch.lv_country_region_normalized, "AU");
  assert.equal(out.merge.provenance.lv_produces_content.source, "june_2026");
});

test("(c) an hs_object_id absent from JUNE_CANDIDATES yields byte-identical (no june_2026) merge output", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, baseRow("999999999999"));
  assert.ok(out.merge && typeof out.merge === "object");
  const juneProvenanceEntries = Object.values(out.merge.provenance).filter((p) => p.source === "june_2026");
  assert.equal(juneProvenanceEntries.length, 0, "no field may carry june_2026 provenance for an untabled id");
  assert.deepEqual(out.merge.canonicalPatch, {}, "no candidate at all -> empty canonicalPatch");
});

test("(d) a June id still folds in even when a firmographic waterfall candidate is present on other fields", () => {
  const row = baseRow(RACING_NSW_ID, {
    scored: {
      best: { lv_content_type: { normalizedValue: ["live_broadcast"], source: "zoominfo", agreedBy: [] } },
      winners: {},
      sourcesByField: { lv_content_type: ["zoominfo"] },
    },
  });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.equal(out.merge.canonicalPatch.lv_org_type, "governing_body_league",
    "june_2026 fold must not be crowded out by an unrelated waterfall candidate");
});
