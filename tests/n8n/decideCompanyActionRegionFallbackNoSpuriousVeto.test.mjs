// tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs
//
// fix-40 VETO-01/02 live evidence run (2026-08-07): two real AU disposable companies
// received a spurious "Non-ANZ geography" veto alongside their correct no-content/
// hardware-vendor reasons. Root cause: ENRICH_COMPANY_SEARCH_PROPERTIES_CSV never
// requested lv_country_region_normalized, so existingRecord.lv_country_region_normalized
// was always undefined, and ENRICH_DECIDE_CO_CLOUD's veto derivation falls back to that
// field directly (`properties.lv_country_region_normalized ?? existing.
// lv_country_region_normalized`) whenever no candidate this run freshly re-promotes
// region. Fixed by adding the property to the CSV (test_hubspot_properties_config.py
// pins that). This test locks the BEHAVIORAL contract the CSV fix exists to satisfy:
// chained Merge Company -> Decide Company Action, with an existingRecord shaped exactly
// like what the FIXED fetch now returns (region present) and a matched:false research
// candidate (the live "fake company, no domain" case) -- no non-ANZ veto may fire.
//
// Reuses tests/n8n/countryRegionResearchMergePromotion.test.mjs's `new Function(...)`
// harness idiom verbatim, extended to also load and run Decide Company Action.
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

// A row shaped like the FIXED fetch: existingRecord carries lv_country_region_normalized
// (the CSV now requests it), and a matched:false research candidate -- the live "fake
// disposable company, no domain, research legitimately finds nothing" case.
function row(existingRegion, existingProducesContent, existingIsHardwareVendor) {
  return {
    action: "enrich",
    identity_keys: { domain: null },
    existingRecord: {
      hs_object_id: "999",
      name: "ZZ-SCORING-TEST-DELETE-ME-fixture",
      lv_country_region_normalized: existingRegion,
      lv_produces_content: existingProducesContent,
      lv_is_hardware_vendor: existingIsHardwareVendor,
    },
    scored: { best: {}, winners: {}, sourcesByField: {} },
    research_candidate: { matched: false, confidence: 0, data: {}, evidence_by_field: {} },
  };
}

function runMergeThenDecide(inputRow) {
  const merged = runCodeNode(MERGE_COMPANY_BODY, inputRow);
  return runCodeNode(DECIDE_COMPANY_ACTION_BODY, { ...inputRow, merge: merged.merge });
}

test("existing AU + research matched:false: no candidate re-promotes region, " +
     "no non-ANZ veto fires", () => {
  const out = runMergeThenDecide(row("AU", true, false));
  assert.ok(!("lv_country_region_normalized" in out.properties),
    "vacuity check: region must NOT have been freshly re-promoted this run -- otherwise " +
    "this test would pass for the wrong reason (the ?? fallback never exercised)");
  assert.equal(out.properties.lv_anti_icp_flag, "false");
  assert.equal(out.properties.lv_anti_icp_reason, "");
});

test("existing US (genuinely non-ANZ) + research matched:false: the veto still fires " +
     "correctly -- the fix must not blind the derivation to a real non-ANZ company", () => {
  const out = runMergeThenDecide(row("US", true, false));
  assert.equal(out.properties.lv_anti_icp_flag, "true");
  assert.equal(out.properties.lv_anti_icp_reason, "Non-ANZ geography");
});

// debug: blank-region-fires-non-anz-veto (2026-08-10) -- distinct from the two tests
// above. Those cover "region WAS set but this run's fetch didn't request it" (the CSV
// fix). This covers a company whose region has GENUINELY never been enriched: HubSpot
// property-history live evidence traced 17 real companies (13 AU racing clubs + 1 NZ
// club, e.g. Bunbury Turf Club 9604738976) PATCHed lv_anti_icp_flag="true"/
// "Non-ANZ geography" by this exact node while lv_country_region_normalized had no
// history at all -- never set, not merely unfetched this run.
test("existing region genuinely never enriched (undefined) + research matched:false: " +
     "no non-ANZ veto fires", () => {
  const out = runMergeThenDecide(row(undefined, true, false));
  assert.ok(!("lv_country_region_normalized" in out.properties),
    "vacuity check: region must NOT have been freshly re-promoted this run -- otherwise " +
    "this test would pass for the wrong reason (the ?? fallback never exercised)");
  assert.equal(out.properties.lv_anti_icp_flag, "false");
  assert.equal(out.properties.lv_anti_icp_reason, "");
});

test("existing region as an explicit empty string + research matched:false: treated " +
     "identically to undefined -- both mean 'never enriched', not a known non-ANZ value",
     () => {
  const out = runMergeThenDecide(row("", true, false));
  assert.equal(out.properties.lv_anti_icp_flag, "false");
  assert.equal(out.properties.lv_anti_icp_reason, "");
});

test("existing AU + no-content veto: fires ONLY the no-content reason, never a spurious " +
     "non-ANZ prefix (the exact live-caught defect on disposable D1)", () => {
  const out = runMergeThenDecide(row("AU", false, false));
  assert.equal(out.properties.lv_anti_icp_flag, "true");
  assert.equal(out.properties.lv_anti_icp_reason, "No broadcast or streaming content");
});

test("existing AU + hardware-vendor veto: fires ONLY the hardware reason, never a " +
     "spurious non-ANZ prefix (the exact live-caught defect on disposable D2)", () => {
  const out = runMergeThenDecide(row("AU", true, true));
  assert.equal(out.properties.lv_anti_icp_flag, "true");
  assert.equal(out.properties.lv_anti_icp_reason, "Hardware/AV/LED vendor, not sports-media buyer");
});
