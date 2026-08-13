// tests/n8n/antiIcpFlagMirror.test.mjs
//
// Phase 50 Plan 06 Task 4 (D-20) -- behavioural drift control for the n8n engine.
// Executes the BUILT `Decide Company Action` node from n8n/wf_enrichment_cloud.json
// (never a hand-inspection of scripts/build_cloud_workflows.py's source text), reusing
// tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs's
// loadNodeJsCode/runCodeNode harness verbatim. Asserts, for every veto trigger
// independently, several triggers together, and the clean no-veto case, that
// lv_anti_icp_flag and its numeric mirror lv_anti_icp_flag_num are always a matching
// pair -- never half-set. A test that only checked the veto case would pass a build that
// hardcodes the mirror; the no-veto case is what gives this guard teeth.
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

// Same fixture shape as decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs's row().
function row(region, producesContent, isHardwareVendor, orgType) {
  return {
    action: "enrich",
    identity_keys: { domain: null },
    existingRecord: {
      hs_object_id: "999",
      name: "ZZ-SCORING-TEST-DELETE-ME-fixture",
      lv_country_region_normalized: region,
      lv_produces_content: producesContent,
      lv_is_hardware_vendor: isHardwareVendor,
      lv_org_type: orgType,
    },
    scored: { best: {}, winners: {}, sourcesByField: {} },
    research_candidate: { matched: false, confidence: 0, data: {}, evidence_by_field: {} },
  };
}

function runMergeThenDecide(inputRow) {
  const merged = runCodeNode(MERGE_COMPANY_BODY, inputRow);
  return runCodeNode(DECIDE_COMPANY_ACTION_BODY, { ...inputRow, merge: merged.merge });
}

function assertMatchingPair(out, expectVeto) {
  const flag = out.properties.lv_anti_icp_flag;
  const num = out.properties.lv_anti_icp_flag_num;
  assert.ok(flag === "true" || flag === "false", `lv_anti_icp_flag must be a string true/false, got ${flag}`);
  assert.ok(num === "1" || num === "0", `lv_anti_icp_flag_num must be a string 1/0, got ${num}`);
  const flagIsTrue = flag === "true";
  const numIsOne = num === "1";
  assert.equal(flagIsTrue, numIsOne,
    `mirror mismatch: lv_anti_icp_flag=${flag} but lv_anti_icp_flag_num=${num} -- the pair must never be half-set`);
  assert.equal(flagIsTrue, expectVeto, `expected veto=${expectVeto} but lv_anti_icp_flag=${flag}`);
}

test("clean no-veto case: AU, content, non-hardware -- flag/mirror pair is false/0", () => {
  const out = runMergeThenDecide(row("AU", true, false, "governing_body_league"));
  assertMatchingPair(out, false);
});

test("non-ANZ trigger alone: flag/mirror pair is true/1", () => {
  const out = runMergeThenDecide(row("US", true, false, "governing_body_league"));
  assertMatchingPair(out, true);
});

test("no-content trigger alone: flag/mirror pair is true/1", () => {
  const out = runMergeThenDecide(row("AU", false, false, "governing_body_league"));
  assertMatchingPair(out, true);
});

test("hardware-vendor boolean trigger alone: flag/mirror pair is true/1", () => {
  const out = runMergeThenDecide(row("AU", true, true, "broadcaster"));
  assertMatchingPair(out, true);
});

test("hardware-vendor org-type trigger alone (Simtech LED's shape): flag/mirror pair is true/1", () => {
  const out = runMergeThenDecide(row("AU", true, false, "hardware_vendor"));
  assertMatchingPair(out, true);
});

test("multiple triggers together (non-ANZ + no-content + hardware-vendor): flag/mirror pair is true/1", () => {
  const out = runMergeThenDecide(row("US", false, true, "hardware_vendor"));
  assertMatchingPair(out, true);
  assert.equal(
    out.properties.lv_anti_icp_reason,
    "Non-ANZ geography; No broadcast or streaming content; Hardware/AV/LED vendor, not sports-media buyer",
  );
});

test("genuinely never-enriched region (undefined) + no other trigger: flag/mirror pair is false/0", () => {
  const out = runMergeThenDecide(row(undefined, true, false, "governing_body_league"));
  assertMatchingPair(out, false);
});
