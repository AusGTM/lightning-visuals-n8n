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
const { isCitationSufficient, applyEvidenceSufficiency } =
  require(path.join(ROOT, "n8n/code/judge.js"));

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
