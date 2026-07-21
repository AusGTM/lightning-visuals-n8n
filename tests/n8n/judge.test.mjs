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
  normalizeVendorFlag, computeEscalation, applyUnadjudicated,
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
