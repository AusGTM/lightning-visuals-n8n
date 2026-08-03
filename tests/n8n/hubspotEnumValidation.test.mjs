// tests/n8n/hubspotEnumValidation.test.mjs
//
// Phase 31 (BUGS 28/29, REVIEW-05) — a review approval can never carry a value HubSpot's
// enum will refuse. Three sections, mirroring reviewDecisionEndpoint.test.mjs:
//   (1) MODULE  — n8n/code/hubspotEnums.js in isolation.
//   (2) FLOW    — the COMMITTED n8n/wf_review_decision_cloud.json's own node jsCode, the
//                 live `industry` case refused end to end for both dry_run states, plus
//                 the committed wf_scheduled_maintenance_cloud.json's 15-minute backstop.
//   (3) STAGING — n8n/code/mergeCompanies.js: an unmappable enum candidate is staged, not
//                 offered for review (Task 2).
//
// Run: node --test tests/n8n/hubspotEnumValidation.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const { normalizeEnumValue, enumRefusalMessage, isEnumBound } =
  require(path.join(ROOT, "n8n/code/hubspotEnums.js"));
const { mergeCompanies, stableStringify } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));
const { reviewApply } = require(path.join(ROOT, "n8n/code/reviewApply.js"));

// The recorded live failure (30-07-SUMMARY.md / 31-CONTEXT.md): company 9604614548's
// approve PATCH 400'd on this exact `industry` candidate.
const LIVE_INDUSTRY_VALUE = "arts, entertainment, and recreation";

// =====================================================================================
// (1) MODULE — n8n/code/hubspotEnums.js
// =====================================================================================

test("normalizeEnumValue refuses the live industry value, naming both the property and the value", () => {
  const r = normalizeEnumValue("industry", LIVE_INDUSTRY_VALUE);
  assert.equal(r.ok, false);
  assert.match(r.reason, /industry/);
  assert.match(r.reason, new RegExp(LIVE_INDUSTRY_VALUE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("normalizeEnumValue maps an exact case-insensitive label match to the internal value", () => {
  const r = normalizeEnumValue("industry", "Sports");
  assert.equal(r.ok, true);
  assert.equal(r.value, "SPORTS");
});

test("normalizeEnumValue passes an already-internal value through unchanged", () => {
  const r = normalizeEnumValue("industry", "SPORTS");
  assert.equal(r.ok, true);
  assert.equal(r.value, "SPORTS");
});

test("normalizeEnumValue passes a non-enum-bound property through untouched", () => {
  assert.equal(isEnumBound("domain"), false);
  const r = normalizeEnumValue("domain", "exampleracing.example");
  assert.deepEqual(r, { ok: true, value: "exampleracing.example", reason: null });
});

test("normalizeEnumValue: a multi-select array of valid values passes, preserving array shape", () => {
  const r = normalizeEnumValue("lv_content_type", ["live_broadcast", "streaming"]);
  assert.equal(r.ok, true);
  assert.deepEqual(r.value, ["live_broadcast", "streaming"]);
});

test("normalizeEnumValue: a multi-select array with one invalid element refuses the whole value", () => {
  const r = normalizeEnumValue("lv_content_type", ["live_broadcast", "not_a_real_content_type"]);
  assert.equal(r.ok, false);
  assert.match(r.reason, /lv_content_type/);
});

test("enumRefusalMessage for the live industry value returns real accepted labels including entertainment", () => {
  const entry = require(path.join(ROOT, "n8n/code/hubspotEnums.generated.js")).COMPANY_ENUM_PROPERTIES.industry;
  const msg = enumRefusalMessage("industry", LIVE_INDUSTRY_VALUE);
  assert.match(msg, /industry/);
  assert.match(msg, /148 options/);
  // Pull the hint clause back out and assert every listed label is a REAL accepted label
  // (a key of the generated labelToValue map) — never invented, never a guess.
  const hintMatch = msg.match(/Closest accepted label\(s\): (.+)\.$/);
  assert.ok(hintMatch, `expected a hint clause in: ${msg}`);
  const hints = hintMatch[1].split(", ");
  assert.ok(hints.length > 0 && hints.length <= 3);
  for (const h of hints) {
    assert.ok(Object.prototype.hasOwnProperty.call(entry.labelToValue, h),
      `hint "${h}" must be a real accepted label of industry`);
  }
  assert.ok(hints.some((h) => h.toLowerCase() === "entertainment"),
    `expected "entertainment" among the hints, got: ${hints.join(", ")}`);
});

test("enumRefusalMessage omits the hint clause when nothing scores", () => {
  const msg = enumRefusalMessage("industry", "###");
  assert.equal(/Closest accepted label/.test(msg), false);
});

// --- reviewApply given the live industry candidate ------------------------------------
//
// Hand-crafted in the EXACT producer shape (mergeCompanies.js decisions[] entry, per
// reviewApply.js's own CONSUMER CONTRACT comment) rather than derived by calling
// mergeCompanies() itself: post-Task-2, mergeCompanies never manufactures a needs_review
// decision for an enum-invalid value (it stages it instead — see the STAGING section
// below). A stored candidate holding an invalid value can therefore only exist as
// T-31-02 describes: written before this guard existed, or hand-edited directly in
// HubSpot. reviewApply's OWN guard must still refuse it regardless of how it got there —
// that is precisely what these fixtures exercise.
function industryCandidateJson(existingIndustry, candidateIndustryValue, opts) {
  const entry = {
    field: "industry",
    current_value: existingIndustry,
    chosen_value: candidateIndustryValue,
    source_provider: (opts && opts.source) || "zoominfo",
    decision: "needs_review",
    confidence: (opts && opts.confidence) || 90,
    reason: "Refresh candidate requires review in MVP.",
    validation_status: "human_review_required",
    evidence_url: null,
    verified_at: "2026-08-03T00:00:00.000Z",
  };
  return stableStringify([entry]);
}

test("reviewApply: a stored candidate carrying the live industry value returns empty patches with a populated invalid", () => {
  const candidateJson = industryCandidateJson("SPORTS", LIVE_INDUSTRY_VALUE,
    { source: "zoominfo", confidence: 90 });
  const result = reviewApply(candidateJson, { industry: "SPORTS" });

  assert.deepEqual(result.canonicalPatch, {});
  assert.deepEqual(result.clearPatch, {});
  assert.equal(result.stale, false);
  assert.equal(result.invalid.length, 1);
  assert.equal(result.invalid[0].field, "industry");
  assert.match(result.invalid[0].reason, /industry/);
});

test("reviewApply: a valid candidate still returns the patches it returns today", () => {
  const candidateJson = industryCandidateJson("SPORTS", "Sports",
    { source: "zoominfo", confidence: 90 });
  const result = reviewApply(candidateJson, { industry: "SPORTS" });

  assert.deepEqual(result.canonicalPatch, { industry: "SPORTS" });
  assert.equal(result.stale, false);
  assert.deepEqual(result.invalid, []);
  assert.ok(Object.keys(result.clearPatch).length > 0);
});

// =====================================================================================
// (2) FLOW — the COMMITTED workflows' own node jsCode
// =====================================================================================

const WF_DECISION_PATH = path.join(ROOT, "n8n", "wf_review_decision_cloud.json");
const WF_DECISION = JSON.parse(fs.readFileSync(WF_DECISION_PATH, "utf8"));

function jsCodeOf(wf, name) {
  const node = wf.nodes.find((n) => n.name === name);
  assert.ok(node, `node present in the committed workflow: ${name}`);
  assert.equal(node.type, "n8n-nodes-base.code");
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) the way n8n's Code node runs it. */
function runNode(jsCode, seedItems, nodeOutputs) {
  const wrap = (rows) => rows.map((j) => ({ json: j }));
  const $input = {
    all: () => wrap(seedItems),
    first: () => (seedItems.length ? { json: seedItems[0] } : undefined),
  };
  const $ = (name) => {
    assert.ok(nodeOutputs && name in nodeOutputs,
      `jsCode reached for an upstream node this test did not provide: ${name}`);
    const items = wrap(nodeOutputs[name]);
    return { first: () => items[0], all: () => items, item: items[0] };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";

function industryFlaggedRow() {
  const candidateJson = industryCandidateJson("SPORTS", LIVE_INDUSTRY_VALUE,
    { source: "zoominfo", confidence: 90 });
  return {
    hs_object_id: "9604614548",
    record_found: true,
    domain: "exampleracing.example",
    industry: "SPORTS",
    [P_NEEDS_REVIEW]: "true",
    [P_ICP_NEEDS_REVIEW]: "false",
    [P_CANDIDATE_JSON]: candidateJson,
  };
}

function driveDecision(body, row) {
  const [parsed] = runNode(jsCodeOf(WF_DECISION, "Parse Review Decision"), [{ body }], {});
  const [built] = runNode(jsCodeOf(WF_DECISION, "Build Review Decision"), [row],
    { "Parse Review Decision": [parsed] });
  return { parsed, built };
}

const APPROVE_BODY = {
  object_type: "companies",
  record_id: "9604614548",
  decision: "approve",
  reviewed_by: "revops@example.com",
};

test("(FLOW a) approving the live industry candidate is refused on PREVIEW (dry_run absent)", () => {
  const row = industryFlaggedRow();
  const { parsed, built } = driveDecision(APPROVE_BODY, row);
  assert.equal(parsed.dry_run, true, "absent dry_run must default to true (D-03)");
  assert.equal(built.outcome, "refused");
  assert.deepEqual(built.would_write, {});
  assert.equal(built.dry_run, true);
  assert.match(built.message, /industry/);
  assert.match(built.message, new RegExp(LIVE_INDUSTRY_VALUE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("(FLOW b) approving the live industry candidate is refused IDENTICALLY on the real submit (dry_run: false)", () => {
  const row = industryFlaggedRow();
  const { built } = driveDecision({ ...APPROVE_BODY, dry_run: false }, row);
  assert.equal(built.outcome, "refused");
  assert.deepEqual(built.would_write, {});
  // hasWrite is false (empty properties), so dry_run resolves true regardless of the
  // caller's request — this is what makes preview and apply return the SAME refusal, and
  // what routes the row to Build Review Response instead of the write gate (BUG 29's fix).
  assert.equal(built.dry_run, true, "an empty write must never reach the write gate");
  assert.match(built.message, /industry/);
  assert.match(built.message, new RegExp(LIVE_INDUSTRY_VALUE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("(FLOW c) a valid candidate on the same endpoint still applies (no regression)", () => {
  const candidateJson = industryCandidateJson("SPORTS", "Sports",
    { source: "zoominfo", confidence: 90 });
  const row = {
    hs_object_id: "789", record_found: true, domain: "exampleracing.example",
    industry: "SPORTS", [P_NEEDS_REVIEW]: "true", [P_ICP_NEEDS_REVIEW]: "false",
    [P_CANDIDATE_JSON]: candidateJson,
  };
  const { built } = driveDecision({ ...APPROVE_BODY, record_id: "789", dry_run: false }, row);
  assert.equal(built.outcome, "applied");
  assert.equal(built.properties.industry, "SPORTS");
});

// --- The 15-minute backstop (wf_scheduled_maintenance_cloud.json) ---------------------

test("(FLOW d) the scheduled-maintenance Apply Review node emits review_skip true for the live industry candidate", () => {
  const wf = JSON.parse(fs.readFileSync(
    path.join(ROOT, "n8n", "wf_scheduled_maintenance_cloud.json"), "utf8"));
  const jsCode = jsCodeOf(wf, "Apply Review");
  const row = industryFlaggedRow();
  const [out] = runNode(jsCode, [row], {});
  assert.equal(out.review_skip, true);
  assert.deepEqual(out.properties, {});
  assert.equal(out.stale, false);
  assert.equal(out.invalid.length, 1);
});

test("(FLOW e) the scheduled-maintenance Apply Review node emits review_skip false for a valid candidate", () => {
  const wf = JSON.parse(fs.readFileSync(
    path.join(ROOT, "n8n", "wf_scheduled_maintenance_cloud.json"), "utf8"));
  const jsCode = jsCodeOf(wf, "Apply Review");
  const candidateJson = industryCandidateJson("SPORTS", "Sports",
    { source: "zoominfo", confidence: 90 });
  const row = {
    hs_object_id: "789", industry: "SPORTS",
    lv_enrichment_review_candidate_json: candidateJson,
  };
  const [out] = runNode(jsCode, [row], {});
  assert.equal(out.review_skip, false);
  assert.equal(out.properties.industry, "SPORTS");
});

test("(FLOW f) the scheduled-maintenance Review IF Stale node switches on review_skip, not stale", () => {
  const wf = JSON.parse(fs.readFileSync(
    path.join(ROOT, "n8n", "wf_scheduled_maintenance_cloud.json"), "utf8"));
  const node = wf.nodes.find((n) => n.name === "Review IF Stale");
  assert.ok(node, "Review IF Stale node must exist");
  const field = node.parameters.conditions.conditions[0].leftValue;
  assert.match(field, /review_skip/);
});

// =====================================================================================
// (3) STAGING — n8n/code/mergeCompanies.js (Task 2): an unmappable enum candidate is
// staged, never offered for review.
// =====================================================================================

test("STAGING: an unmappable industry candidate on a company with a stored industry stages, does not need_review", () => {
  const r = mergeCompanies({ industry: "SPORTS" }, { industry: LIVE_INDUSTRY_VALUE },
    undefined, { source: "waterfall", confidence: 85 });
  const d = r.decisions.find((x) => x.field === "industry");

  assert.equal(d.decision, "stage_only");
  assert.notEqual(d.decision, "needs_review");
  assert.deepEqual(r.canonicalPatch, {});
});

test("STAGING: the refused field's provenance carries validation_status rejected and the ORIGINAL provider string", () => {
  const r = mergeCompanies({ industry: "SPORTS" }, { industry: LIVE_INDUSTRY_VALUE },
    undefined, { source: "waterfall", confidence: 85 });
  assert.equal(r.provenance.industry.validation_status, "rejected");
  assert.equal(r.provenance.industry.value, LIVE_INDUSTRY_VALUE,
    "the raw provider string must survive in provenance even though it never promotes");
});

test("STAGING: the matching decisions[] entry carries the refusal message as its reason", () => {
  const r = mergeCompanies({ industry: "SPORTS" }, { industry: LIVE_INDUSTRY_VALUE },
    undefined, { source: "waterfall", confidence: 85 });
  const d = r.decisions.find((x) => x.field === "industry");
  assert.match(d.reason, /industry/);
  assert.match(d.reason, new RegExp(LIVE_INDUSTRY_VALUE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("STAGING: a candidate industry of Sports still promotes with SPORTS", () => {
  const r = mergeCompanies({}, { industry: "Sports" }, undefined,
    { source: "waterfall", confidence: 85 });
  assert.deepEqual(r.canonicalPatch, { industry: "SPORTS" });
});

test("STAGING: the refused field never stamps a cache-key datetime and never reaches canonicalPatch", () => {
  // lv_org_type is one of the two cache-keyed fields (COMPANY_CACHE_KEY_FIELDS).
  const r = mergeCompanies({ lv_org_type: "broadcaster" },
    { lv_org_type: "not_a_real_org_type" }, undefined,
    { source: "claude_web", confidence: 90, evidence: { lv_org_type: "https://x.example" } });
  assert.deepEqual(r.canonicalPatch, {});
  assert.deepEqual(r.cacheKeys, {});
});

const LV_ENUM_PROMOTION_CASES = [
  ["lv_org_type", "governing_body_league",
    { source: "claude_web", confidence: 90, evidence: { lv_org_type: "https://x.example" } }],
  ["lv_content_type", ["live_broadcast", "streaming"], { source: "claude_web", confidence: 90 }],
  ["lv_revenue_band", "5-50M", { source: "zoominfo", confidence: 90 }],
  ["lv_employee_band", "201-500", { source: "zoominfo", confidence: 90 }],
  ["lv_country_region_normalized", "AU", { source: "zoominfo", confidence: 90 }],
];

for (const [field, value, opts] of LV_ENUM_PROMOTION_CASES) {
  test(`STAGING: ${field} still promotes with an unchanged value today`, () => {
    const r = mergeCompanies({}, { [field]: value }, undefined, opts);
    assert.deepEqual(r.canonicalPatch, { [field]: value });
  });
}

const NON_ENUM_FIELD_CASES = [
  ["domain", "exampleracing.example"],
  ["numberofemployees", 220],
  ["annualrevenue", 65000000],
  ["lv_produces_content", true],
  ["lv_sponsorship_reliant", true],
];

for (const [field, value] of NON_ENUM_FIELD_CASES) {
  test(`STAGING: non-enum-bound field ${field} is untouched by the enum guard`, () => {
    const before = mergeCompanies({}, { [field]: value }, undefined,
      { source: "waterfall", confidence: 90,
        evidence: field === "lv_produces_content" ? { lv_produces_content: "https://x.example" } : {} });
    const d = before.decisions.find((x) => x.field === field);
    assert.equal(d.chosen_value, value,
      `${field}'s decision value must be exactly what was passed in`);
  });
}
