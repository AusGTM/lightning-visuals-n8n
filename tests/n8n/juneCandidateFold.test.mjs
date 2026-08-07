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

// --- Task 3: D-01 precedence, D-04 disagreement gate, native firmographic band fold ---
// Racing NSW's own June row: lv_org_type governing_body_league, lv_produces_content
// "true" -- used as the real (not synthetic) June side of every disagreement/precedence
// case below, since JUNE_CANDIDATES is a baked `const` the harness cannot inject rows into.

function researchRow(hsObjectId, researchOverrides = {}, otherOverrides = {}) {
  return baseRow(hsObjectId, {
    research_candidate: {
      matched: true,
      confidence: 90,
      data: {},
      evidence_by_field: {},
      ...researchOverrides,
    },
    ...otherOverrides,
  });
}

test("(e) D-04: June (governing_body_league) vs fresh research (broadcaster) disagree on lv_org_type " +
     "-> suppressed from canonicalPatch, cache key deleted, exactly one needs_review decision", () => {
  const row = researchRow(RACING_NSW_ID, { data: { lv_org_type: "broadcaster" } });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.ok(!("lv_org_type" in out.merge.canonicalPatch),
    "a disagreed field must never reach canonicalPatch, from EITHER source");
  assert.ok(!("lv_org_type_verified_at" in out.merge.cacheKeys),
    "the cache-key stamp must be deleted, not just the canonical value (Phase 16.3 discipline)");
  const needsReview = out.merge.decisions.filter((d) => d.field === "lv_org_type" && d.decision === "needs_review");
  assert.equal(needsReview.length, 1);
  assert.equal(needsReview[0].source_provider, "june_2026");
});

test("(f) D-04: June and fresh research AGREE on lv_org_type -> promotes normally, no synthetic needs_review", () => {
  const row = researchRow(RACING_NSW_ID, {
    data: { lv_org_type: "governing_body_league" },
    evidence_by_field: { lv_org_type: "https://example.example/about" },
  });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.equal(out.merge.canonicalPatch.lv_org_type, "governing_body_league");
  const needsReview = out.merge.decisions.filter((d) => d.field === "lv_org_type" && d.decision === "needs_review");
  assert.equal(needsReview.length, 0, "agreement must not synthesize a needs_review decision");
});

test("(g) D-01 precedence: research silent on lv_produces_content -> June's value promotes", () => {
  // Research answers ONLY lv_content_type -- neither org_type nor produces_content -- so
  // both remain free for June to fill, and (since neither is disputed) neither trips the
  // D-04 gate.
  const row = researchRow(RACING_NSW_ID, { data: { lv_content_type: ["live_broadcast"] } });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.equal(out.merge.canonicalPatch.lv_produces_content, "true");
  assert.equal(out.merge.provenance.lv_produces_content.source, "june_2026");
  assert.equal(out.merge.canonicalPatch.lv_org_type, "governing_body_league");
  assert.equal(out.merge.provenance.lv_org_type.source, "june_2026");
});

test("(h) F1: annualrevenue with no waterfall band -> lv_revenue_band derives from the native field", () => {
  const row = baseRow("999999999999", {
    existingRecord: { hs_object_id: "999999999999", domain: "example.example",
                       annualrevenue: "12000000" },
  });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.equal(out.merge.canonicalPatch.lv_revenue_band, "5-50M");
  assert.equal(out.merge.provenance.lv_revenue_band.source, "hubspot_native");
});

test("(h2) F1 EDGE: a blank annualrevenue yields no lv_revenue_band key (Number('') === 0 landmine)", () => {
  const row = baseRow("999999999999", {
    existingRecord: { hs_object_id: "999999999999", domain: "example.example", annualrevenue: "" },
  });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.ok(!("lv_revenue_band" in out.merge.canonicalPatch));
});

test("(i) F1: a waterfall-supplied lv_revenue_band survives the native fold unchanged", () => {
  const row = baseRow("999999999999", {
    existingRecord: { hs_object_id: "999999999999", domain: "example.example",
                       annualrevenue: "12000000" },  // would native-band to 5-50M if it ever ran
    scored: {
      best: { lv_revenue_band: { normalizedValue: "50-500M", source: "zoominfo", agreedBy: [] } },
      winners: {},
      sourcesByField: { lv_revenue_band: ["zoominfo"] },
    },
  });
  const out = runMergeCompany(MERGE_COMPANY_BODY, row);
  assert.equal(out.merge.canonicalPatch.lv_revenue_band, "50-500M",
    "the waterfall's own band must win; the native fold must not have run");
});

test("(j) D-07: a June-folded record's canonicalPatch never carries a firmographic field", () => {
  const out = runMergeCompany(MERGE_COMPANY_BODY, baseRow(RACING_NSW_ID));
  for (const f of ["domain", "annualrevenue", "numberofemployees", "industry"]) {
    assert.ok(!(f in out.merge.canonicalPatch), `${f} must stay staged-only, never canonical`);
  }
});
