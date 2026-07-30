// tests/n8n/judgeFailure.test.mjs
//
// Phase 14 Task 4 — the executable proof of JG-3 ("a judge verdict below confidence 80
// never promotes") and the never-throws contract judgeVerdictFromHttpItem must satisfy,
// mirroring tests/n8n/webResearchFailure.test.mjs's structure and its failure shapes.
//
// Run: node --test tests/n8n/judgeFailure.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { judgeVerdictFromHttpItem, applyJudgeVerdict, buildJudgeRequestBody } =
  require(path.join(ROOT, "n8n/code/judge.js"));

// The four failure shapes n8n's HTTP Request node can produce under onError:Continue,
// plus a text block that is not JSON.
const FAILURE_SHAPES = [
  { name: "n8n execution-error item (no usable body)", item: { error: "ETIMEDOUT: connect ETIMEDOUT" } },
  { name: "empty/missing content (no text blocks)", item: { content: [] } },
  { name: "missing content entirely", item: {} },
  { name: "Anthropic HTTP-level error body", item: { type: "error", error: { type: "overloaded_error", message: "Overloaded" } } },
  { name: "text block that is not JSON", item: { content: [{ type: "text", text: "not json at all" }] } },
];

test("judgeVerdictFromHttpItem: every failure shape never throws, resolves needs_review/confidence:0", () => {
  for (const { name, item } of FAILURE_SHAPES) {
    const verdict = judgeVerdictFromHttpItem(item);
    assert.equal(verdict.decision, "needs_review", `${name}: decision must be needs_review`);
    assert.equal(verdict.confidence, 0, `${name}: confidence must be 0`);
    assert.equal(verdict.chosen_value, null, `${name}: chosen_value must be null`);
  }
});

function wellFormedVerdict(confidence, decision = "promote") {
  return {
    content: [{ type: "text", text: JSON.stringify({
      decision, chosen_value: "content_producer", confidence,
      evidence_url: "https://x/about", evidence_summary: "cited",
      validation_status: "sonnet_validated", reason: "identity matches cited source",
      chosen_field: "lv_org_type",
    }) }],
  };
}

test("JG-3 boundary: confidence 79 -> rewritten to needs_review even though the model said promote", () => {
  const verdict = judgeVerdictFromHttpItem(wellFormedVerdict(79));
  assert.equal(verdict.decision, "needs_review");
  assert.equal(verdict.confidence, 79);
});

test("JG-3 boundary: confidence 80 -> promote survives", () => {
  const verdict = judgeVerdictFromHttpItem(wellFormedVerdict(80));
  assert.equal(verdict.decision, "promote");
  assert.equal(verdict.confidence, 80);
});

test("JG-3: applyJudgeVerdict leaves no promoted vendor flag behind for the sub-80 verdict", () => {
  const candidate = {
    data: { lv_is_hardware_vendor: true, lv_org_type: "content_producer" },
    evidence_by_field: { lv_is_hardware_vendor: "https://x/about" },
  };
  const verdict = judgeVerdictFromHttpItem(wellFormedVerdict(79));
  const result = applyJudgeVerdict(candidate, verdict, ["hardware_vendor_detected"]);
  assert.equal(result.data.lv_is_hardware_vendor, null);
  assert.notEqual(result.data.lv_is_hardware_vendor, false);
  assert.equal(result.judge_flags.needs_review, true);
});

test("applyJudgeVerdict: there is no path in which a sub-80 verdict produces a promoted value", () => {
  for (const confidence of [0, 1, 50, 79]) {
    for (const decision of ["promote", "confirm", "needs_review", "reject"]) {
      const result = applyJudgeVerdict(
        { data: { lv_org_type: "existing_value" } },
        { decision, confidence, chosen_field: "lv_org_type", chosen_value: "flipped" },
        [],
      );
      assert.notEqual(result.data.lv_org_type, "flipped",
        `decision=${decision} confidence=${confidence} must never promote`);
    }
  }
});

test("applyJudgeVerdict: a genuine promote at confidence >= 80 keeps the adjudicated value", () => {
  const result = applyJudgeVerdict(
    { data: { lv_org_type: "existing_value" } },
    { decision: "promote", confidence: 88, chosen_field: "lv_org_type", chosen_value: "content_producer" },
    [],
  );
  assert.equal(result.data.lv_org_type, "content_producer");
  assert.equal(result.judge_flags.adjudicated, true);
});

// --- JG-2 payload shape -------------------------------------------------------------
test("buildJudgeRequestBody: JG-2 — no revenue/employee fields, no tools key, at all", () => {
  const row = {
    identity_keys: { companyName: "Supertech Electronics", domain: "supertech-electronics.com.au" },
    existingRecord: { lv_org_type: "governing_body_league", lv_revenue_band: "50-500M", numberofemployees: 200 },
    research_candidate: {
      data: {
        lv_org_type: "hardware_vendor", lv_produces_content: true,
        lv_is_hardware_vendor: true, lv_revenue_band: "5-50M", annualrevenue: 4000000,
      },
      evidence_by_field: { lv_org_type: "https://x/about" },
    },
    judge_reasons: ["org_type_conflict", "hardware_vendor_detected"],
  };
  const body = buildJudgeRequestBody(row, "claude-sonnet-5", 4096);
  const serialized = JSON.stringify(body);

  assert.ok(!/revenue/i.test(serialized), "no revenue field anywhere in the serialized body");
  assert.ok(!/employee/i.test(serialized), "no employee field anywhere in the serialized body");
  assert.ok(!("tools" in body), "no tools key at all (Pitfall 5)");
  assert.ok(!/web_search/.test(serialized), "no web_search tool reference");
  assert.equal(body.max_tokens, 4096);
  assert.ok(serialized.includes("hardware_vendor"), "the vendor-flag classification IS carried");
});
