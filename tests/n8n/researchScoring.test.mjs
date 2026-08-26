// tests/n8n/researchScoring.test.mjs
//
// Phase 15.5 Task 4 — scoreResearchCandidates + the self-confirmation guard (D1) +
// TA-1/TA-2/TA-6. Driven from tests/fixtures/research_scoring_cases.json (SYNTHETIC
// page_age + prior_on_file layered onto the 20 real Phase-13 smoke rows).
//
// Run: node --test tests/n8n/researchScoring.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  scoreResearchCandidates, isIndependentPrior, _JUDGE_DATA_FIELDS,
} = require(path.join(ROOT, "n8n/code/judge.js"));
const { DEFAULT_COMPANY_POLICY } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

const fixturePath = path.join(ROOT, "tests/fixtures/research_scoring_cases.json");
const { cases: CASES } = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

function findCase(company) {
  const c = CASES.find((x) => x.company === company);
  assert.ok(c, `fixture must carry a row for ${company}`);
  return c;
}

// Build the {provenance blob entry} shape mergeCompanies/scoreResearchCandidates read,
// from a fixture row's synthetic prior_on_file block.
function provenanceFromPrior(prior) {
  if (!prior) return {};
  const entry = { confidence: 90, verified_at: prior.verified_at, value: prior.value };
  if (prior.source !== undefined) entry.source = prior.source;
  return { [prior.field]: entry };
}

function existingRecordFromPrior(prior) {
  if (!prior) return {};
  return { [prior.field]: prior.value };
}

// --- Task 4(e) note: widening existingRecord to include the 4 new search properties
// must not change promotion behavior — every one of them is system_owned, and
// system_owned ignores the current value entirely (assert, don't assume).
test("Task 4(e): the 4 newly-widened company-search fields are all system_owned (ignores current value)", () => {
  for (const f of ["lv_content_type", "lv_is_hardware_vendor", "lv_is_gambling_operator"]) {
    assert.equal(DEFAULT_COMPANY_POLICY[f].class, "system_owned", `${f} must be system_owned`);
  }
});

// --- TA-1: no-prior case (Supertech Electronics) ------------------------------------
test("TA-1: a researched field with no prior on file scores on accuracy/recency/trust alone, agreement 0, components present regardless of escalation", () => {
  const supertech = findCase("Supertech Electronics");
  const researchCandidate = {
    matched: true, confidence: 70,
    data: { lv_is_hardware_vendor: true },
    evidence_by_field: { lv_is_hardware_vendor: supertech.citation_url },
    recency_by_field: { lv_is_hardware_vendor: supertech.page_age },
    recency_source_by_field: { lv_is_hardware_vendor: "page_age" },
  };
  const result = scoreResearchCandidates(researchCandidate, {}, {}, { now: "2026-07-01T00:00:00Z" });
  assert.ok(result.lv_is_hardware_vendor, "field must be scored");
  assert.equal(result.lv_is_hardware_vendor.prior_on_file, null, "no prior on file");
  assert.equal(result.lv_is_hardware_vendor.research.components.G, 0, "agreement must be 0 with no prior");
  assert.ok(result.lv_is_hardware_vendor.research.components.A > 0, "accuracy component present");
  assert.equal(result.lv_is_hardware_vendor.ranked.length, 1, "ranked carries only the research candidate");
});

// --- Recency is ordering only ---------------------------------------------------------
test("Recency is ordering only: fresh vs Wyong-style stale page_age produce different composite scores, same set of fields carrying values, nothing turns false", () => {
  const wyong = findCase("Wyong");
  const base = {
    matched: true, confidence: 85,
    data: { lv_produces_content: true },
    evidence_by_field: { lv_produces_content: wyong.citation_url },
  };
  const fresh = { ...base, recency_by_field: { lv_produces_content: "June 1, 2026" }, recency_source_by_field: { lv_produces_content: "page_age" } };
  const stale = { ...base, recency_by_field: { lv_produces_content: wyong.page_age }, recency_source_by_field: { lv_produces_content: "page_age" } };

  const freshResult = scoreResearchCandidates(fresh, {}, {}, { now: "2026-07-01T00:00:00Z" });
  const staleResult = scoreResearchCandidates(stale, {}, {}, { now: "2026-07-01T00:00:00Z" });

  assert.notEqual(freshResult.lv_produces_content.research.score, staleResult.lv_produces_content.research.score,
    "fresh vs stale page_age must change the composite score");
  assert.deepEqual(Object.keys(freshResult), Object.keys(staleResult), "same set of fields carry values");
  assert.equal(freshResult.lv_produces_content.research.value, true);
  assert.equal(staleResult.lv_produces_content.research.value, true, "nothing turns false due to recency");
});

test("Unknown recency is neutral: an unmatched page_age produces the same recency component as no evidence url at all", () => {
  const candidateUnmatched = {
    matched: true, confidence: 85,
    data: { lv_org_type: "governing_body_league" },
    evidence_by_field: { lv_org_type: "https://x/about" },
    recency_by_field: { lv_org_type: null },
    recency_source_by_field: { lv_org_type: "unmatched" },
  };
  const candidateNoEvidence = {
    matched: true, confidence: 85,
    data: { lv_org_type: "governing_body_league" },
    evidence_by_field: {},
  };
  const r1 = scoreResearchCandidates(candidateUnmatched, {}, {}, { now: "2026-07-01T00:00:00Z" });
  const r2 = scoreResearchCandidates(candidateNoEvidence, {}, {}, { now: "2026-07-01T00:00:00Z" });
  assert.equal(r1.lv_org_type.research.components.R, 0.5, "unmatched page_age -> neutral recency");
  assert.equal(r2.lv_org_type.research.components.R, 0.5, "no evidence url -> neutral recency (same value)");
  assert.equal(r1.lv_org_type.recency_source, "unmatched");
});

// --- THE GUARD ------------------------------------------------------------------------
const atc = findCase("Australian Turf Club"); // synthetic prior source: claude_web (pipeline)

function guardResearchCandidate(prior) {
  return {
    matched: true, confidence: 85,
    data: { lv_org_type: prior.value },
    evidence_by_field: { lv_org_type: atc.citation_url },
    recency_by_field: { lv_org_type: atc.page_age },
    recency_source_by_field: { lv_org_type: "page_age" },
  };
}

test("THE GUARD, positive case: a prior EQUAL to the research value whose provenance source is one of our own pipeline sources yields agreement 0 and prior_on_file.independent false", () => {
  const rc = guardResearchCandidate(atc.prior_on_file);
  const existing = existingRecordFromPrior(atc.prior_on_file);
  const provenance = provenanceFromPrior(atc.prior_on_file);
  assert.equal(atc.prior_on_file.source, "claude_web", "fixture precondition: this row's prior is pipeline-sourced");

  const result = scoreResearchCandidates(rc, existing, provenance, { now: "2026-07-01T00:00:00Z" });
  assert.equal(result.lv_org_type.prior_on_file.independent, false);
  assert.equal(result.lv_org_type.research.components.G, 0, "pipeline-source prior must not raise agreement");
});

test("THE GUARD, negative control: the SAME values with NO provenance entry (legacy prior) yields agreement 1 and prior_on_file.independent true", () => {
  const rc = guardResearchCandidate(atc.prior_on_file);
  const existing = existingRecordFromPrior(atc.prior_on_file);
  const provenance = {}; // no provenance entry at all -> legacy value

  const result = scoreResearchCandidates(rc, existing, provenance, { now: "2026-07-01T00:00:00Z" });
  assert.equal(result.lv_org_type.prior_on_file.independent, true);
  assert.equal(result.lv_org_type.research.components.G, 1, "legacy no-provenance prior IS independent -> real agreement");
});

test("THE GUARD, fail-closed case: a prior whose provenance source is an unrecognized string is treated as non-independent", () => {
  const panasonic = findCase("Panasonic Studio Productions"); // synthetic source: legacy_import (unrecognized)
  assert.equal(panasonic.prior_on_file.source, "legacy_import");
  assert.equal(isIndependentPrior({ source: "legacy_import" }), false);
  assert.equal(isIndependentPrior({ source: "some_never_seen_tool" }), false);
  assert.equal(isIndependentPrior({}), false, "an entry present with no source at all also fails closed");
  assert.equal(isIndependentPrior(undefined), true, "no entry at all is legacy/independent");
  assert.equal(isIndependentPrior(null), true);
  assert.equal(isIndependentPrior({ source: "human" }), true);
  assert.equal(isIndependentPrior({ source: "manual" }), true);
});

test("THE GUARD, DELIBERATE-BREAK: allowlisting the pipeline source in a LOCALLY-SHADOWED predicate flips agreement to 1, proving the guard is load-bearing", () => {
  // Locally-shadowed copy of the predicate (does NOT edit/restore n8n/code/judge.js).
  function brokenIsIndependentPrior() { return true; } // pretend everything is independent

  const rc = guardResearchCandidate(atc.prior_on_file);
  const existing = existingRecordFromPrior(atc.prior_on_file);
  const provenance = provenanceFromPrior(atc.prior_on_file);

  // Re-derive what scoreResearchCandidates would do if isIndependentPrior always
  // returned true: prior joins the research candidate in the SAME scoreCandidates call,
  // manufacturing agreement out of the pipeline's own earlier guess.
  const { scoreCandidates } = require(path.join(ROOT, "n8n/code/scoreEnrichment.js"));
  const researchCand = { field: "lv_org_type", source: "claude_web", value: rc.data.lv_org_type,
    normalizedValue: rc.data.lv_org_type, accuracy: rc.confidence / 100, recencyDate: rc.recency_by_field.lv_org_type };
  const provEntry = provenance.lv_org_type;
  const priorCand = { field: "lv_org_type", source: "prior_on_file", value: existing.lv_org_type,
    normalizedValue: existing.lv_org_type, accuracy: provEntry.confidence / 100, recencyDate: provEntry.verified_at };

  assert.equal(brokenIsIndependentPrior(provEntry), true, "the shadowed predicate always says independent");
  const scored = scoreCandidates([researchCand, priorCand],
    { trust: { claude_web: 0.78, prior_on_file: 0.9 }, now: "2026-07-01T00:00:00Z" });
  assert.equal(scored.best.lv_org_type.components.G, 1,
    "with the broken (always-independent) predicate, agreement becomes 1 -- proving the real guard's non-independent branch is what keeps it at 0");

  // The REAL predicate on the same input still says non-independent, and the REAL
  // function still yields agreement 0 -- the positive assertion above has teeth.
  const realResult = scoreResearchCandidates(rc, existing, provenance, { now: "2026-07-01T00:00:00Z" });
  assert.equal(realResult.lv_org_type.research.components.G, 0);
});

// --- Disagreement -----------------------------------------------------------------
test("Disagreement: a prior that DIFFERS from the research value yields agreement 0 whether or not it is independent, and ranked carries both", () => {
  const gravity = findCase("GRAVITY MEDIA"); // synthetic prior: content_producer, source claude_web
  const rc = {
    matched: true, confidence: 85,
    data: { lv_org_type: "governing_body_league" }, // DIFFERS from the prior's content_producer
    evidence_by_field: { lv_org_type: gravity.citation_url },
    recency_by_field: { lv_org_type: gravity.page_age },
    recency_source_by_field: { lv_org_type: "page_age" },
  };
  const existing = existingRecordFromPrior(gravity.prior_on_file);
  const provenance = provenanceFromPrior(gravity.prior_on_file); // pipeline source -> non-independent anyway
  const result = scoreResearchCandidates(rc, existing, provenance, { now: "2026-07-01T00:00:00Z" });
  assert.equal(result.lv_org_type.research.components.G, 0);
  assert.equal(result.lv_org_type.ranked.length, 2, "ranked carries both candidates");
  assert.ok(result.lv_org_type.ranked.some((c) => c.source === "claude_web"));
  assert.ok(result.lv_org_type.ranked.some((c) => c.source === "prior_on_file"));

  // Same disagreement, but with an INDEPENDENT prior source -> still agreement 0 (values differ).
  const provenanceIndependent = { lv_org_type: { ...provenance.lv_org_type, source: "human" } };
  const resultIndependent = scoreResearchCandidates(rc, existing, provenanceIndependent, { now: "2026-07-01T00:00:00Z" });
  assert.equal(resultIndependent.lv_org_type.research.components.G, 0);
  assert.equal(resultIndependent.lv_org_type.prior_on_file.independent, true);
});

// --- ranked ordering --------------------------------------------------------------
test("The ranked array is ordered by the same deterministic tie-break as the argmax, and contains every candidate", () => {
  const rockhampton = findCase("Rockhampton Jockey Club"); // independent (human) prior
  const rc = {
    matched: true, confidence: 95, // higher accuracy than the prior's synthetic 0.9
    data: { lv_org_type: "individual_club_team" }, // agrees with the prior -> real agreement
    evidence_by_field: { lv_org_type: rockhampton.citation_url },
    recency_by_field: { lv_org_type: rockhampton.page_age },
    recency_source_by_field: { lv_org_type: "page_age" },
  };
  const existing = existingRecordFromPrior(rockhampton.prior_on_file);
  const provenance = provenanceFromPrior(rockhampton.prior_on_file);
  const result = scoreResearchCandidates(rc, existing, provenance, { now: "2026-07-01T00:00:00Z" });
  const ranked = result.lv_org_type.ranked;
  assert.equal(ranked.length, 2);
  for (let i = 1; i < ranked.length; i += 1) {
    assert.ok(ranked[i - 1].score >= ranked[i].score, "ranked must be sorted score-descending");
  }
});

// --- TA-2 tier boundary sanity (full static proof lives in tests/test_judge_spec.py) --
// UPDATED (gap-closure 58-06, operator ruling 2026-08-26, T-58-26/§21.2):
// lv_country_region_normalized joined the judge-eligible set — execution 11983 proved a
// cross-provider region conflict can fire the Non-ANZ hard veto unadjudicated, so the
// judge must be able to see and adjudicate the disputed region.
test("TA-2: _JUDGE_DATA_FIELDS is exactly the 6 expected classification fields", () => {
  assert.deepEqual([..._JUDGE_DATA_FIELDS].sort(), [
    "lv_content_type", "lv_country_region_normalized", "lv_is_gambling_operator",
    "lv_is_hardware_vendor", "lv_org_type", "lv_produces_content",
  ].sort());
});
