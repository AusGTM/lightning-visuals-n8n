// tests/n8n/judge.test.mjs
//
// Phase 14 Task 2 — JG-4 citation sufficiency over the 20 real Phase-13 smoke rows.
// Run: node --test tests/n8n/judge.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  isCitationSufficient, applyEvidenceSufficiency,
  normalizeVendorFlag, computeEscalation, applyUnadjudicated, applyCostCap,
  buildJudgeRequestBody,
} = require(path.join(ROOT, "n8n/code/judge.js"));

const fixturePath = path.join(ROOT, "tests/fixtures/evidence_sufficiency_cases.json");
const { evidence_cases: CASES } = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

test("isCitationSufficient: all 19 claim:true rows of the 20-row fixture match expected verdict", () => {
  let ran = 0;
  for (const c of CASES) {
    if (c.claim !== true) continue; // row 9 (QRIC) is claim:false -> judge_only, excluded
    ran += 1;
    const expected = c.expected === "sufficient";
    assert.equal(
      isCitationSufficient(c.citation_url, c.domain), expected,
      `${c.company}: expected ${c.expected} for ${c.citation_url} vs domain ${c.domain}`
    );
  }
  assert.equal(ran, 19, "the claim:true loop must run exactly 19 times (judge_only row excluded)");
});

test("isCitationSufficient: judge_only row (QRIC, claim:false) is excluded from the sufficiency loop by construction", () => {
  const qric = CASES.find((c) => c.expected === "judge_only");
  assert.ok(qric, "fixture must carry exactly one judge_only row");
  assert.equal(qric.claim, false);
});

test("applyEvidenceSufficiency: Supertech-shaped candidate demotes lv_produces_content to null, never false", () => {
  const supertech = CASES.find((c) => c.company === "Supertech Electronics");
  const candidate = {
    provider: "claude_web",
    data: { lv_produces_content: true, lv_org_type: "hardware_vendor" },
    evidence_by_field: { lv_produces_content: supertech.citation_url },
  };
  const result = applyEvidenceSufficiency(candidate, supertech.domain);
  assert.equal(result.data.lv_produces_content, null);
  assert.notEqual(result.data.lv_produces_content, false);
  assert.ok(result.judge_flags && result.judge_flags.insufficient_content_evidence === true);
  assert.ok(!("lv_produces_content" in result.evidence_by_field), "evidence key dropped");
  // No in-place mutation of the caller's object.
  assert.equal(candidate.data.lv_produces_content, true);
});

test("applyEvidenceSufficiency: a sufficient row (Sunshine Coast) is left untouched", () => {
  const sctc = CASES.find((c) => c.company === "Sunshine Coast Turf Club");
  const candidate = {
    provider: "claude_web",
    data: { lv_produces_content: true },
    evidence_by_field: { lv_produces_content: sctc.citation_url },
  };
  const result = applyEvidenceSufficiency(candidate, sctc.domain);
  assert.equal(result.data.lv_produces_content, true);
  assert.equal(result.evidence_by_field.lv_produces_content, sctc.citation_url);
});

test("applyEvidenceSufficiency: a false claim is returned unchanged (Pitfall 3 — heuristic never touches it)", () => {
  const qric = CASES.find((c) => c.company === "Queensland Racing Integrity Commission");
  const candidate = {
    provider: "claude_web",
    data: { lv_produces_content: false },
    evidence_by_field: { lv_produces_content: qric.citation_url },
  };
  const result = applyEvidenceSufficiency(candidate, qric.domain);
  assert.equal(result, candidate, "false claims must pass through untouched (same reference is fine, no-op)");
  assert.equal(result.data.lv_produces_content, false);
});

// --- computeEscalation: JG-1 trigger matrix / RO-1 / RO-2 ---------------------------

test("RO-1(a): computeEscalation(null, {...}) -> needsJudge:false", () => {
  const r = computeEscalation(null, { lv_org_type: "governing_body_league" });
  assert.equal(r.needsJudge, false);
  assert.deepEqual(r.reasons, []);
});

test("RO-1(b): an unmatched candidate cannot escalate even carrying a trigger value", () => {
  const r = computeEscalation({ matched: false, data: { lv_produces_content: false } }, {});
  assert.equal(r.needsJudge, false);
});

test("RO-2: a row carrying a populated size-disagreement array + a benign candidate -> needsJudge:false; arity is 2", () => {
  assert.equal(computeEscalation.length, 2, "computeEscalation must not grow a third argument");
  // Pass the row's fields explicitly, proving the function never receives the array at all.
  const row = {
    conflicts: [{ field: "lv_revenue_band", chosen: "50-500M", candidates: [] }],
  };
  const benignCandidate = {
    matched: true, confidence: 92,
    data: { lv_org_type: "governing_body_league", lv_produces_content: true },
  };
  const r = computeEscalation(benignCandidate, row.existingRecord || {});
  assert.equal(r.needsJudge, false, "a size disagreement alone must never trigger the judge");
});

test("JG-1(a): existing org_type known + research flips it -> needsJudge:true, org_type_conflict", () => {
  const r = computeEscalation(
    { matched: true, confidence: 92, data: { lv_org_type: "content_producer" } },
    { lv_org_type: "governing_body_league" },
  );
  assert.equal(r.needsJudge, true);
  assert.ok(r.reasons.includes("org_type_conflict"));
});

test("JG-1(b): existing org_type blank/unknown -> first-time resolution is NOT a flip", () => {
  const r = computeEscalation(
    { matched: true, confidence: 92, data: { lv_org_type: "content_producer", lv_produces_content: true } },
    { lv_org_type: "unknown" },
  );
  assert.ok(!r.reasons.includes("org_type_conflict"));
  assert.equal(r.needsJudge, false);
});

test("JG-1(c): lv_produces_content:false -> needsJudge:true, reason produces_content_false", () => {
  const r = computeEscalation({ matched: true, confidence: 92, data: { lv_produces_content: false } }, {});
  assert.equal(r.needsJudge, true);
  assert.ok(r.reasons.includes("produces_content_false"));
});

test("JG-1(d): lv_is_hardware_vendor as a STRING 'true' -> needsJudge:true (proves normalizeVendorFlag feeds the trigger)", () => {
  const r = computeEscalation({ matched: true, confidence: 92, data: { lv_is_hardware_vendor: "true" } }, {});
  assert.equal(r.needsJudge, true);
  assert.ok(r.reasons.includes("hardware_vendor_detected"));
});

test("JG-1(e): confidence-band boundaries — 75/80/85 trigger, 74/86 do not", () => {
  const data = { lv_org_type: "content_producer" };
  for (const conf of [75, 80, 85]) {
    const r = computeEscalation({ matched: true, confidence: conf, data }, {});
    assert.ok(r.reasons.includes("confidence_band"), `confidence ${conf} should trigger confidence_band`);
    assert.equal(r.needsJudge, true);
  }
  for (const conf of [74, 86]) {
    const r = computeEscalation({ matched: true, confidence: conf, data }, {});
    assert.ok(!r.reasons.includes("confidence_band"), `confidence ${conf} should NOT trigger confidence_band`);
  }
});

test("normalizeVendorFlag: strict true/false/null, unrecognised -> null never false", () => {
  assert.equal(normalizeVendorFlag(true), true);
  assert.equal(normalizeVendorFlag(false), false);
  assert.equal(normalizeVendorFlag("true"), true);
  assert.equal(normalizeVendorFlag("yes"), true);
  assert.equal(normalizeVendorFlag(1), true);
  assert.equal(normalizeVendorFlag("bogus"), null);
  assert.equal(normalizeVendorFlag(undefined), null);
  assert.notEqual(normalizeVendorFlag("bogus"), false);
});

// --- applyCostCap: TA-7 -------------------------------------------------------------

test("applyCostCap: 15 needs_judge rows into a budget of 10 -> exactly 10 survive, exactly 5 capped, input order determines which", () => {
  const rows = Array.from({ length: 15 }, (_, i) => ({ id: i, needs_judge: true }));
  const result = applyCostCap(rows, 10);
  const survived = result.filter((r) => r.needs_judge === true);
  const capped = result.filter((r) => r.judge_capped === true);
  assert.equal(survived.length, 10, "exactly 10 must survive");
  assert.equal(capped.length, 5, "exactly 5 must be capped");
  assert.deepEqual(survived.map((r) => r.id), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], "input order determines which survive");
  assert.deepEqual(capped.map((r) => r.id), [10, 11, 12, 13, 14], "input order determines which are capped");
  for (const r of capped) assert.notEqual(r.needs_judge, true, "capped rows must not carry needs_judge:true");
});

test("applyCostCap: budget 0 caps all 15", () => {
  const rows = Array.from({ length: 15 }, (_, i) => ({ id: i, needs_judge: true }));
  const result = applyCostCap(rows, 0);
  assert.equal(result.filter((r) => r.needs_judge === true).length, 0);
  assert.equal(result.filter((r) => r.judge_capped === true).length, 15);
});

test("applyCostCap: rows with needs_judge false are returned unchanged and never consume budget", () => {
  const rows = [
    { id: 0, needs_judge: false },
    { id: 1, needs_judge: true },
    { id: 2, needs_judge: false },
  ];
  const result = applyCostCap(rows, 1);
  assert.equal(result[0], rows[0], "untouched row is the SAME reference");
  assert.equal(result[1].needs_judge, true, "the one needs_judge row still fits in the budget");
  assert.equal(result[2], rows[2], "untouched row is the SAME reference");
});

test("applyCostCap: a non-finite maxPerRun caps everything (same path as budget 0)", () => {
  const rows = [{ id: 0, needs_judge: true }];
  assert.equal(applyCostCap(rows, NaN)[0].judge_capped, true);
  assert.equal(applyCostCap(rows, undefined)[0].judge_capped, true);
});

test("applyCostCap: does not mutate its input array or the input row objects", () => {
  const rows = [{ id: 0, needs_judge: true }, { id: 1, needs_judge: true }];
  const snapshot = JSON.parse(JSON.stringify(rows));
  applyCostCap(rows, 1);
  assert.deepEqual(rows, snapshot, "input rows must be untouched after the call");
});

test("applyCostCap composition: a capped row carrying a hardware-vendor true, put through the existing unadjudicated fail-safe, comes back null (never false)", () => {
  const rows = [
    { id: 0, needs_judge: true, judge_reasons: ["hardware_vendor_detected"],
      research_candidate: { data: { lv_is_hardware_vendor: true }, evidence_by_field: { lv_is_hardware_vendor: "https://x/about" } } },
    { id: 1, needs_judge: true, judge_reasons: [] },
  ];
  const capped = applyCostCap(rows, 0); // both capped
  const demoted = applyUnadjudicated(capped[0].research_candidate, capped[0].judge_reasons);
  assert.equal(demoted.data.lv_is_hardware_vendor, null);
  assert.notEqual(demoted.data.lv_is_hardware_vendor, false);
  assert.ok(!("lv_is_hardware_vendor" in demoted.evidence_by_field), "evidence key dropped");
});

test("Fail-safe: applyUnadjudicated demotes a hardware-vendor candidate to null (never false), leaves evidenced false content untouched", () => {
  const candidate = {
    matched: true,
    data: { lv_is_hardware_vendor: true, lv_produces_content: false },
    evidence_by_field: { lv_is_hardware_vendor: "https://x/about", lv_produces_content: "https://x/media" },
  };
  const result = applyUnadjudicated(candidate, ["hardware_vendor_detected"]);
  assert.equal(result.data.lv_is_hardware_vendor, null);
  assert.notEqual(result.data.lv_is_hardware_vendor, false);
  assert.equal(result.data.lv_produces_content, false, "TS-3: evidenced false content is left untouched (D5 table)");
  assert.equal(result.judge_flags.unadjudicated, true);
});

// --- buildJudgeRequestBody: TA-5/TA-6 payload grounding ------------------------------

function scoringRow(extra) {
  return {
    identity_keys: { companyName: "Example Racing", domain: "example.com.au" },
    existingRecord: { lv_org_type: "governing_body_league", lv_revenue_band: "50-500M", numberofemployees: 200 },
    research_candidate: {
      data: { lv_org_type: "content_producer", lv_produces_content: true },
      evidence_by_field: { lv_org_type: "https://example.com.au/about" },
    },
    judge_reasons: ["org_type_conflict"],
    research_scoring: {
      lv_org_type: { field: "lv_org_type", ranked: [], research: { score: 0.7, components: { A: 0.7, R: 0.5, G: 0, T: 0.78 } },
        recency_source: "page_age", prior_on_file: { value: "governing_body_league", independent: false } },
      lv_produces_content: { field: "lv_produces_content", ranked: [], research: { score: 0.8 }, recency_source: "unmatched", prior_on_file: null },
      ...extra,
    },
  };
}

test("buildJudgeRequestBody: TA-5 — the scoring key appears in the serialized body, restricted to judge-eligible fields", () => {
  const row = scoringRow();
  const body = buildJudgeRequestBody(row, "claude-sonnet-5", 4096);
  assert.ok(body.messages[0].content.includes("\"scoring\""), "scoring key must appear in the serialized body");
  const parsed = JSON.parse(body.messages[0].content);
  assert.deepEqual(Object.keys(parsed.company.scoring).sort(), ["lv_org_type", "lv_produces_content"]);
});

test("buildJudgeRequestBody: TA-5 — an extra non-judge-eligible field on row.research_scoring is dropped from the payload", () => {
  const row = scoringRow({ lv_revenue_band: { field: "lv_revenue_band", research: { score: 0.9 } } });
  const body = buildJudgeRequestBody(row, "claude-sonnet-5", 4096);
  const parsed = JSON.parse(body.messages[0].content);
  assert.ok(!("lv_revenue_band" in parsed.company.scoring), "non-judge-eligible field must be restricted out");
});

test("buildJudgeRequestBody: JG-2 holds with the new scoring key — no size-band/numeric firmographic name anywhere in the FULL serialized body", () => {
  const row = scoringRow({ lv_revenue_band: { field: "lv_revenue_band", research: { score: 0.9 } } });
  const body = buildJudgeRequestBody(row, "claude-sonnet-5", 4096);
  const serialized = JSON.stringify(body);
  assert.ok(!/revenue/i.test(serialized), "no revenue field anywhere in the serialized body");
  assert.ok(!/employee/i.test(serialized), "no employee field anywhere in the serialized body");
  assert.ok(!("tools" in body), "still no tools key");
});

test("buildJudgeRequestBody: TA-6 — the prompt names the prior-on-file label and says agreement with it is not evidence", () => {
  const row = scoringRow();
  const body = buildJudgeRequestBody(row, "claude-sonnet-5", 4096);
  assert.ok(body.system.includes("prior_on_file"), "prompt must name the prior_on_file label");
  assert.ok(/not.*independent corroborating source/i.test(body.system));
  assert.ok(/not evidence/i.test(body.system));
});

test("buildJudgeRequestBody: a row with no research_scoring at all still produces a valid body", () => {
  const row = scoringRow();
  delete row.research_scoring;
  const body = buildJudgeRequestBody(row, "claude-sonnet-5", 4096);
  const parsed = JSON.parse(body.messages[0].content);
  assert.deepEqual(parsed.company.scoring, {});
  assert.equal(body.max_tokens, 4096);
});
