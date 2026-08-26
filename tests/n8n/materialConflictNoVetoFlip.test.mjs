// tests/n8n/materialConflictNoVetoFlip.test.mjs
//
// Gap-closure 58-06 Task 1: the §21.2 pin. Built from live execution `11983`'s own
// runData (workflow 950HPb7a1GgSAIyZ, 2026-08-26T09:25Z, Series Futsal Victoria
// `283816805830`) -- fetched read-only via plain urllib per project memory
// (executions_client.py's `requests` transport fails in this environment; documented in
// 58-06-SUMMARY.md's forensic section).
//
// Captured shape at "Normalize + Score Company" (the live conflict this plan closes):
//   scored.sourcesByField.lv_country_region_normalized =
//     [{source:"lusha",value:"AU"}, {source:"zoominfo",value:"Other"}]
//   scored.best.lv_country_region_normalized =
//     {value:"United States", normalizedValue:"Other", source:"zoominfo", agreedBy:[]}
//   scored.sourcesByField.country =
//     [{source:"lusha",value:"australia"},{source:"apollo",value:"australia"},
//      {source:"zoominfo",value:"united states"}]  -- lusha/apollo AGREE, no conflict here
//   scored.winners.country = "Australia" (lusha's raw value, the group's non-conflicted
//     sibling -- must ALSO be withheld while the group is unresolved, per the plan's own
//     acceptance criterion, even though `country` itself has no raw conflict)
//
// Reuses tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs's
// `new Function(...)` harness idiom verbatim, chaining Merge Company -> Decide Company
// Action against the BUILT (committed) wf_enrichment_cloud.json jsCode -- never a
// reimplementation of either node's logic.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadNodeJsCode(name) {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n/wf_enrichment_cloud.json"), "utf8"));
  const node = wf.nodes.find((n) => n.name === name);
  return node.parameters.jsCode;
}

function runCodeNode(jsCode, row) {
  const $input = { all: () => [{ json: row }], get item() { return { json: row }; } };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, row, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}

const MERGE_COMPANY_BODY = loadNodeJsCode("Merge Company");
const DECIDE_COMPANY_ACTION_BODY = loadNodeJsCode("Decide Company Action");

// The 11983 shape, with a BLANK existing region (per the plan: SFV's live record holds
// "Other" post-incident, so `?? existing` would derive `true` from existing state and the
// test would assert the wrong thing for the wrong reason -- the pre-incident blank is the
// state that actually proves the guarantee).
function elevenNineEightThreeRow(judgeVerdictOverride) {
  const base = {
    action: "enrich",
    identity_keys: { domain: "seriesfutsal.com" },
    existingRecord: {
      hs_object_id: "283816805830",
      name: "Series Futsal Victoria",
      domain: "seriesfutsal.com",
      lv_country_region_normalized: undefined,
      lv_produces_content: true,
      lv_is_hardware_vendor: false,
      lv_org_type: "content_producer",
    },
    scored: {
      best: {
        lv_country_region_normalized: {
          field: "lv_country_region_normalized", value: "United States",
          normalizedValue: "Other", source: "zoominfo", agreedBy: [],
        },
        country: {
          field: "country", value: "Australia", normalizedValue: "australia",
          source: "lusha", agreedBy: ["apollo"],
        },
      },
      winners: { country: "Australia" },
      sourcesByField: {
        lv_country_region_normalized: [
          { source: "lusha", value: "AU" },
          { source: "zoominfo", value: "Other" },
        ],
        country: [
          { source: "lusha", value: "australia" },
          { source: "apollo", value: "australia" },
          { source: "zoominfo", value: "united states" },
        ],
      },
    },
    research_candidate: { matched: false, confidence: 0, data: {}, evidence_by_field: {} },
  };
  if (judgeVerdictOverride) {
    return { ...base, ...judgeVerdictOverride };
  }
  return base;
}

function runMergeThenDecide(inputRow) {
  const merged = runCodeNode(MERGE_COMPANY_BODY, inputRow);
  return runCodeNode(DECIDE_COMPANY_ACTION_BODY, { ...inputRow, merge: merged.merge, conflicts: merged.conflicts });
}

test("11983 shape, no judge verdict: lv_country_region_normalized and country both " +
     "ABSENT from derived properties, no anti-ICP flip, and the company is flagged " +
     "naming both disagreeing sources", () => {
  const out = runMergeThenDecide(elevenNineEightThreeRow());

  assert.ok(!("lv_country_region_normalized" in out.properties),
    "the disputed field must never promote the trust-rank loser (zoominfo's wrong-branch " +
    "US match) unadjudicated");
  assert.ok(!("country" in out.properties),
    "country is the SAME disputed fact's other serialization -- it must be withheld too, " +
    "even though it individually has no raw conflict (lusha/apollo agree on it)");
  assert.equal(out.properties.lv_anti_icp_flag, "false",
    "T-58-26: an unadjudicated provider conflict must never flip the veto false->true");
  assert.equal(out.properties.lv_anti_icp_reason, "");
  assert.equal(out.properties.lv_enrichment_needs_review, "true");
  assert.match(out.properties.lv_enrichment_review_reason, /lv_country_region_normalized/);
  assert.match(out.properties.lv_enrichment_review_reason, /AU/);
  assert.match(out.properties.lv_enrichment_review_reason, /Other/);
});

test("11983 shape, judge adjudicated AU: the adjudicated value promotes, no flip", () => {
  const row = elevenNineEightThreeRow({
    research_candidate: {
      matched: true, confidence: 70,
      data: { lv_country_region_normalized: "AU" },
      evidence_by_field: { lv_country_region_normalized: "https://example.com/about" },
      judge_flags: { adjudicated: true, decision: "promote" },
    },
    judge_confidence_by_field: { lv_country_region_normalized: 90 },
  });
  const out = runMergeThenDecide(row);

  assert.equal(out.properties.lv_country_region_normalized, "AU",
    "the judge's adjudicated value must promote, not the trust-rank loser");
  assert.equal(out.properties.lv_anti_icp_flag, "false");
  assert.equal(out.properties.lv_anti_icp_reason, "");
});

test("11983 shape, judge adjudicated a non-ANZ value: the adjudicated value promotes " +
     "AND the veto DOES fire -- suppression is conditional, not a blanket ban", () => {
  const row = elevenNineEightThreeRow({
    research_candidate: {
      matched: true, confidence: 70,
      data: { lv_country_region_normalized: "Other" },
      evidence_by_field: { lv_country_region_normalized: "https://example.com/about" },
      judge_flags: { adjudicated: true, decision: "promote" },
    },
    judge_confidence_by_field: { lv_country_region_normalized: 90 },
  });
  const out = runMergeThenDecide(row);

  assert.equal(out.properties.lv_country_region_normalized, "Other");
  assert.equal(out.properties.lv_anti_icp_flag, "true",
    "a genuinely-adjudicated non-ANZ verdict must still be able to fire the veto -- " +
    "suppression is suppress-UNLESS-adjudicated, never a blanket ban");
  assert.equal(out.properties.lv_anti_icp_reason, "Non-ANZ geography");
});

test("an agreeing multi-source lv_country_region_normalized still promotes and is not flagged", () => {
  const row = elevenNineEightThreeRow();
  row.scored.best.lv_country_region_normalized = {
    field: "lv_country_region_normalized", value: "Australia", normalizedValue: "AU",
    source: "lusha", agreedBy: ["zoominfo"],
  };
  row.scored.sourcesByField.lv_country_region_normalized = [
    { source: "lusha", value: "AU" },
    { source: "zoominfo", value: "AU" },
  ];
  const out = runMergeThenDecide(row);

  assert.equal(out.properties.lv_country_region_normalized, "AU");
  assert.notEqual(out.properties.lv_enrichment_needs_review, "true");
  assert.equal(out.properties.lv_anti_icp_flag, "false");
});
