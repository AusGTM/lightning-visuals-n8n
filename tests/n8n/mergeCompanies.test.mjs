// tests/n8n/mergeCompanies.test.mjs
//
// Phase 15.5 Task 1 (Wave-0 gap A) — mergeCompanies.js's FIRST direct unit tests.
// Zero production change in this commit: this file characterizes CURRENT behavior so
// Task 5's diff (opts.confidenceByField) is provably additive rather than assumed to be.
//
// Run: node --test tests/n8n/mergeCompanies.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";
import { stripVerifiedAt } from "./verifiedAtStrip.mjs";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { mergeCompanies, DEFAULT_COMPANY_POLICY } =
  require(path.join(ROOT, "n8n/code/mergeCompanies.js"));
const { scoreResearchCandidates } = require(path.join(ROOT, "n8n/code/judge.js"));

const fixturePath = path.join(ROOT, "tests/fixtures/research_scoring_cases.json");
const { cases: SCORING_CASES } = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

// --- Return shape --------------------------------------------------------------------
test("mergeCompanies: return shape is exactly canonicalPatch/provenance/cacheKeys/decisions", () => {
  const result = mergeCompanies({}, { lv_content_type: ["live_broadcast"] }, undefined,
    { source: "claude_web", confidence: 90 });
  assert.deepEqual(Object.keys(result).sort(),
    ["cacheKeys", "canonicalPatch", "decisions", "provenance"]);
});

// --- Promotion -------------------------------------------------------------------------
test("mergeCompanies: system_owned field (lv_content_type, no evidence requirement) above threshold promotes", () => {
  const { canonicalPatch, provenance } = mergeCompanies({}, { lv_content_type: ["live_broadcast"] },
    undefined, { source: "claude_web", confidence: 90 });
  assert.deepEqual(canonicalPatch.lv_content_type, ["live_broadcast"]);
  const entry = provenance.lv_content_type;
  assert.ok(entry, "provenance entry present");
  assert.equal(entry.source, "claude_web");
  assert.equal(entry.confidence, 90);
  assert.ok(entry.verified_at, "verified_at stamped");
  assert.equal(entry.validation_status, "provider_only");
  assert.deepEqual(entry.value, ["live_broadcast"]);
});

// --- Threshold ---------------------------------------------------------------------
test("mergeCompanies: same field below min_confidence -> needs_review, absent from canonicalPatch, still provenanced", () => {
  const minConf = DEFAULT_COMPANY_POLICY.lv_content_type.min_confidence;
  const { canonicalPatch, provenance, decisions } = mergeCompanies({},
    { lv_content_type: ["live_broadcast"] }, undefined,
    { source: "claude_web", confidence: minConf - 1 });
  assert.ok(!("lv_content_type" in canonicalPatch), "must not promote below threshold");
  assert.ok(provenance.lv_content_type, "staging survives even when promotion does not");
  const d = decisions.find((x) => x.field === "lv_content_type");
  assert.equal(d.decision, "needs_review");
});

// --- lv_country_region_normalized threshold (Plan 21-02, REQ-country-region-policy) ---
test("mergeCompanies: lv_country_region_normalized at min_confidence promotes with provenance", () => {
  const minConf = DEFAULT_COMPANY_POLICY.lv_country_region_normalized.min_confidence;
  const { canonicalPatch, provenance, decisions } = mergeCompanies({},
    { lv_country_region_normalized: "AU" }, undefined,
    { source: "lusha", confidence: minConf });
  assert.equal(canonicalPatch.lv_country_region_normalized, "AU");
  const entry = provenance.lv_country_region_normalized;
  assert.ok(entry, "provenance entry present");
  assert.equal(entry.confidence, minConf);
  const d = decisions.find((x) => x.field === "lv_country_region_normalized");
  assert.equal(d.decision, "promote");
});

test("mergeCompanies: lv_country_region_normalized below min_confidence stages only, still provenanced", () => {
  const minConf = DEFAULT_COMPANY_POLICY.lv_country_region_normalized.min_confidence;
  const { canonicalPatch, provenance, decisions } = mergeCompanies({},
    { lv_country_region_normalized: "AU" }, undefined,
    { source: "lusha", confidence: minConf - 1 });
  assert.ok(!("lv_country_region_normalized" in canonicalPatch), "must not promote below threshold");
  assert.ok(provenance.lv_country_region_normalized, "staging survives even when promotion does not");
  const d = decisions.find((x) => x.field === "lv_country_region_normalized");
  assert.equal(d.decision, "needs_review");
});

// --- Domain hard guard ---------------------------------------------------------------
test("mergeCompanies: domain hard guard forces stage_only even when the gate itself would promote", () => {
  // Deliberately override the policy so the deterministic gate alone WOULD promote
  // (system_owned, min_confidence 0) — proving the hard guard is a second, independent
  // check, not just a restatement of the manual_protected class.
  const overridePolicy = { ...DEFAULT_COMPANY_POLICY, domain: { class: "system_owned", min_confidence: 0 } };
  const { canonicalPatch, decisions } = mergeCompanies({ domain: "old.example" },
    { domain: "new.example" }, overridePolicy, { source: "zoominfo", confidence: 100 });
  assert.ok(!("domain" in canonicalPatch), "domain must never appear in canonicalPatch");
  const d = decisions.find((x) => x.field === "domain");
  assert.equal(d.decision, "stage_only");
});

// --- Evidence gate -------------------------------------------------------------------
test("mergeCompanies: lv_produces_content at high confidence with NO evidence url is withheld", () => {
  const { canonicalPatch, decisions } = mergeCompanies({}, { lv_produces_content: true },
    undefined, { source: "claude_web", confidence: 95 });
  assert.ok(!("lv_produces_content" in canonicalPatch));
  const d = decisions.find((x) => x.field === "lv_produces_content");
  assert.equal(d.decision, "needs_review");
  assert.equal(d.evidence_url, null);
});

test("mergeCompanies: lv_produces_content at high confidence WITH an evidence url promotes, provenance carries it", () => {
  const { canonicalPatch, provenance } = mergeCompanies({}, { lv_produces_content: true },
    undefined, { source: "claude_web", confidence: 95, evidence: { lv_produces_content: "https://x/live" } });
  // 43-01 (D-09/D-10, PIPE-02): canonicalPatch coerces a boolean-typed promoted candidate
  // to its quoted string form; provenance's own `value` stays the raw candidate type
  // (unaffected — the coercion is scoped to canonicalPatch only).
  assert.equal(canonicalPatch.lv_produces_content, "true");
  assert.equal(provenance.lv_produces_content.value, true);
  assert.equal(provenance.lv_produces_content.evidence_url, "https://x/live");
});

// --- Evidence-gated org-type set (read from the module's own policy, TX-4 discipline) --
test("mergeCompanies: lv_org_type promoting to a gated value without a url is withheld, an ungated value at the same confidence promotes", () => {
  const gated = DEFAULT_COMPANY_POLICY.lv_org_type.require_evidence_url_for;
  assert.ok(Array.isArray(gated) && gated.length > 0, "policy must expose a non-empty gated set");
  const gatedValue = gated[0];
  const allOrgTypeValues = ["governing_body_league", "content_producer", "broadcaster",
    "individual_club_team", "regulator", "gambling_operator", "hardware_vendor", "other", "unknown"];
  const ungatedValue = allOrgTypeValues.find((v) => gated.indexOf(v) === -1);
  assert.ok(ungatedValue, "fixture must be able to find an ungated org_type value");

  const gatedResult = mergeCompanies({}, { lv_org_type: gatedValue }, undefined,
    { source: "claude_web", confidence: 90 });
  assert.ok(!("lv_org_type" in gatedResult.canonicalPatch), `gated value ${gatedValue} must not promote unevidenced`);

  const ungatedResult = mergeCompanies({}, { lv_org_type: ungatedValue }, undefined,
    { source: "claude_web", confidence: 90 });
  assert.equal(ungatedResult.canonicalPatch.lv_org_type, ungatedValue, `ungated value ${ungatedValue} promotes unevidenced`);
});

// --- Blank handling ------------------------------------------------------------------
test("mergeCompanies: null / '' / [] candidate values are skipped entirely", () => {
  const { canonicalPatch, provenance, decisions } = mergeCompanies({},
    { lv_org_type: null, industry: "", lv_content_type: [] }, undefined,
    { source: "zoominfo", confidence: 95 });
  assert.deepEqual(canonicalPatch, {});
  assert.deepEqual(provenance, {});
  assert.deepEqual(decisions, []);
});

// --- Cache keys ------------------------------------------------------------------------
test("mergeCompanies: a promoted lv_org_type sets the lv_org_type_verified_at cache key; a field with no mapping sets none", () => {
  const { cacheKeys } = mergeCompanies({}, { lv_org_type: "other", industry: "Sports" },
    undefined, { source: "zoominfo", confidence: 95 });
  assert.ok(cacheKeys.lv_org_type_verified_at, "lv_org_type has a cache-key mapping");
  assert.ok(!("industry_verified_at" in cacheKeys), "industry has no cache-key mapping");
  assert.equal(Object.keys(cacheKeys).length, 1);
});

// --- Phase 16.3 (companies twin of Phase 16.2 gpt #6): stale-timestamp fix — cache key
// stamped ONLY on promote. Uses the evidence-gate withhold mechanism (companies-native,
// since companies has no stale_refreshable field with a cache-key mapping) rather than
// mergeContacts.test.mjs's stale_refreshable path — the gated set is read from the
// module's own policy (TX-4 discipline), mirroring the existing test at :89-105. -------

test("stale-timestamp fix: a needs_review (unevidenced gated) lv_org_type emits NO lv_org_type_verified_at", () => {
  const gated = DEFAULT_COMPANY_POLICY.lv_org_type.require_evidence_url_for;
  const gatedValue = gated[0];
  const { canonicalPatch, cacheKeys, decisions } = mergeCompanies(
    {}, { lv_org_type: gatedValue }, undefined, { source: "claude_web", confidence: 90 });
  assert.ok(!("lv_org_type" in canonicalPatch));
  assert.equal(decisions.find((d) => d.field === "lv_org_type").decision, "needs_review");
  assert.ok(!("lv_org_type_verified_at" in cacheKeys), "unpromoted unevidenced lv_org_type must not be marked fresh");
});

test("stale-timestamp fix: a promoted lv_org_type DOES emit lv_org_type_verified_at", () => {
  const gated = DEFAULT_COMPANY_POLICY.lv_org_type.require_evidence_url_for;
  const gatedValue = gated[0];
  const { canonicalPatch, cacheKeys } = mergeCompanies(
    {}, { lv_org_type: gatedValue }, undefined,
    { source: "claude_web", confidence: 90, evidence: { lv_org_type: "https://x/about" } });
  assert.equal(canonicalPatch.lv_org_type, gatedValue);
  assert.ok(cacheKeys.lv_org_type_verified_at, "promoted lv_org_type keeps its cache-key stamp");
});

// --- Flat opts.confidence default ------------------------------------------------------
test("mergeCompanies: flat opts.confidence default (80) applies when opts omits it", () => {
  const { decisions } = mergeCompanies({}, { lv_content_type: ["live_broadcast"] }, undefined, {});
  const d = decisions.find((x) => x.field === "lv_content_type");
  assert.equal(d.confidence, 80);
});

// --- Phase 15.5 Task 5: opts.confidenceByField (TA-8, D2-safe) + the TS-1 proof --------

function findScoringCase(company) {
  const c = SCORING_CASES.find((x) => x.company === company);
  assert.ok(c, `fixture must carry a row for ${company}`);
  return c;
}

test("mergeCompanies: confidenceByField absent is byte-identical to the Task 1 characterization (waterfall path unaffected)", () => {
  const withoutOption = mergeCompanies({}, { lv_content_type: ["live_broadcast"] }, undefined,
    { source: "claude_web", confidence: 90 });
  const withEmptyMap = mergeCompanies({}, { lv_content_type: ["live_broadcast"] }, undefined,
    { source: "claude_web", confidence: 90, confidenceByField: {} });
  // Strip verified_at (a timestamp) before comparing, per the plan's "modulo the timestamp".
  const strip = stripVerifiedAt;
  assert.deepEqual(strip(withoutOption), strip(withEmptyMap));
});

test("mergeCompanies: confidenceByField overrides one field above threshold while a second field absent from the map still uses the flat confidence and still does not promote", () => {
  const candidate = { lv_org_type: "broadcaster", lv_content_type: ["live_broadcast"] };
  // Flat confidence (60) is below BOTH fields' thresholds (80 / 75).
  const { canonicalPatch, decisions } = mergeCompanies({}, candidate, undefined,
    { source: "claude_web", confidence: 60, confidenceByField: { lv_org_type: 90 } });
  assert.equal(canonicalPatch.lv_org_type, "broadcaster", "overridden field promotes");
  assert.ok(!("lv_content_type" in canonicalPatch), "field absent from the map keeps the flat (sub-threshold) confidence");
  assert.equal(decisions.find((d) => d.field === "lv_content_type").confidence, 60);
});

test("mergeCompanies: recorded confidence matches deciding confidence for an overridden field (provenance + decision both carry the overridden value)", () => {
  const { provenance, decisions } = mergeCompanies({}, { lv_org_type: "broadcaster" }, undefined,
    { source: "claude_web", confidence: 60, confidenceByField: { lv_org_type: 90 } });
  assert.equal(provenance.lv_org_type.confidence, 90);
  assert.equal(decisions.find((d) => d.field === "lv_org_type").confidence, 90);
});

test("TA-4/TS-1/criterion-5: fresh vs stale page_age move the composite score but produce IDENTICAL canonicalPatch — recency changes ranking, changes nothing else", () => {
  // Vary recency where it is ACTUALLY consumed (scoreResearchCandidates), not at the merge
  // boundary where it never arrives. Two runs differ ONLY in page_age: fresh vs Wyong's
  // 2021-stale date. `now` is injected so the age math is deterministic.
  const now = "2026-07-23T00:00:00Z";
  const rc = (verifiedAt) => ({
    confidence: 90,
    data: { lv_org_type: "broadcaster" },
    recency_by_field: { lv_org_type: verifiedAt },
    recency_source_by_field: { lv_org_type: "page_age" },
  });
  const fresh = scoreResearchCandidates(rc("2026-06-01"), {}, {}, { now });
  const stale = scoreResearchCandidates(rc("2021-04-06"), {}, {}, { now }); // Wyong's real stale listing

  // 1. Recency genuinely moves the score — the ordering-bias half is real, not inert.
  const freshR = fresh.lv_org_type.research.components.R;
  const staleR = stale.lv_org_type.research.components.R;
  assert.ok(freshR > staleR, `fresh recency (${freshR}) must exceed stale (${staleR})`);
  assert.notEqual(fresh.lv_org_type.research.score, stale.lv_org_type.research.score);

  // 2. ...yet the PROMOTED value is identical, and both promote (TS-1: recency never gates
  //    a value out, never flips it to false — it only reorders). Same value in both merges.
  const strip = stripVerifiedAt;
  const merge = (score) => mergeCompanies({}, { lv_org_type: score.lv_org_type.research.value },
    undefined, { source: "claude_web", confidence: 90 }).canonicalPatch;
  assert.equal(fresh.lv_org_type.research.value, stale.lv_org_type.research.value);
  assert.deepEqual(strip(merge(fresh)), strip(merge(stale)));
  assert.equal(merge(stale).lv_org_type, "broadcaster", "stale evidence still promotes — recency is bias, not a gate");
});

test("TA-4/TS-1: across every case in the fixture, no field anywhere in canonicalPatch or provenance is boolean false as a result of scoring or recency", () => {
  for (const c of SCORING_CASES) {
    const candidate = { lv_org_type: "broadcaster", lv_content_type: ["live_broadcast"] };
    const existing = c.prior_on_file ? { [c.prior_on_file.field]: c.prior_on_file.value } : {};
    const { canonicalPatch, provenance } = mergeCompanies(existing, candidate, undefined,
      { source: "claude_web", confidence: 90 });
    for (const v of Object.values(canonicalPatch)) assert.notEqual(v, false, `case ${c.company}: canonicalPatch value must never be false`);
    for (const entry of Object.values(provenance)) assert.notEqual(entry.value, false, `case ${c.company}: provenance value must never be false`);
  }
});

test("DELIBERATE-BREAK (D2): wiring the composite score (x100) into confidenceByField for the stale row makes a previously-promoted field STOP promoting", () => {
  const wyong = findScoringCase("Wyong");
  const field = "lv_org_type";
  const staleResearchCandidate = {
    matched: true, confidence: 88, // A = 0.88, matching the D2 worked example in PLAN.md
    data: { [field]: "broadcaster" },
    evidence_by_field: {},
    recency_by_field: { [field]: wyong.page_age }, // 2021 -> very old -> low R
    recency_source_by_field: { [field]: "page_age" },
  };
  const scored = scoreResearchCandidates(staleResearchCandidate, {}, {}, { now: "2026-07-01T00:00:00Z" });
  const composite = scored[field].research.score;
  assert.ok(composite < 0.80, "D2 arithmetic: the composite must land below the 0-1/0-100 scale mismatch threshold");

  // Baseline: flat confidence 90 promotes.
  const baseline = mergeCompanies({}, { [field]: "broadcaster" }, undefined,
    { source: "claude_web", confidence: 90 });
  assert.equal(baseline.canonicalPatch[field], "broadcaster", "baseline (flat confidence) promotes");

  // THE BREAK: composite (0-1) * 100 wired directly into confidenceByField (0-100 scale) —
  // this is EXACTLY what D2 forbids (RESEARCH's literal TA-8), reproduced here on purpose
  // to prove it was arithmetically necessary to reject, not stylistic.
  const broken = mergeCompanies({}, { [field]: "broadcaster" }, undefined,
    { source: "claude_web", confidence: 90, confidenceByField: { [field]: composite * 100 } });
  assert.ok(!(field in broken.canonicalPatch),
    "D2 proof: gating on the composite collapses a previously-promoted field's promotion");
});

test("TA-4/TS-1 via the PRODUCTION confidenceByField path: fresh vs stale page_age produce a byte-identical canonicalPatch", () => {
  // The 15.5 verifier's open human-verification item, closed. The neighbouring TA-4/TS-1
  // test proves recency moves the composite yet the promoted VALUE is stable — but it
  // merges with a flat `confidence`, so it does not exercise the parameter through which
  // recency could actually leak: `confidenceByField`.
  //
  // Production builds that map in "Apply Judge Verdict" (build_cloud_workflows.py:2225-2231):
  //     judge_confidence_by_field[verdict.chosen_field] = verdict.confidence
  // i.e. the JUDGE's own per-field confidence, never the A/R/G/T composite. This test
  // derives the map that way from two rows differing ONLY in page_age and asserts the
  // merges are identical — the real evidence the structural argument deserves.
  //
  // Its non-vacuity partner is the DELIBERATE-BREAK (D2) test above: wire the composite
  // into the SAME parameter and promotion collapses.
  //
  // WHICH ASSERTION ACTUALLY BITES — measured, not assumed. Simulating the leak
  // (confidenceByField = composite*100) gives: promoted=false, provenance.confidence=48.3
  // on BOTH lanes. So the two lanes still produce equal canonicalPatches ({} === {}) and
  // the deepEqual below would PASS under a real leak. It is necessary but not sufficient.
  // The assertions that catch the leak are the promotion check and the provenance-confidence
  // check at the end. Recorded because an equality-only version of this test would look
  // like a proof and be one only by luck.
  const now = "2026-07-23T00:00:00Z";
  const field = "lv_org_type";
  const researchCandidate = (verifiedAt) => ({
    confidence: 90,
    data: { [field]: "broadcaster" },
    recency_by_field: { [field]: verifiedAt },
    recency_source_by_field: { [field]: "page_age" },
  });

  // The judge adjudicates the field; its verdict confidence is what production propagates.
  const verdict = { chosen_field: field, confidence: 88 };
  const productionConfidenceByField = (scored) => {
    // Mirror of Apply Judge Verdict's derivation — deliberately reads ONLY the verdict.
    void scored; // the composite is in scope and is deliberately NOT consulted
    return { [verdict.chosen_field]: verdict.confidence };
  };

  const runLane = (verifiedAt) => {
    const scored = scoreResearchCandidates(researchCandidate(verifiedAt), {}, {}, { now });
    return {
      composite: scored[field].research.score,
      merged: mergeCompanies({}, { [field]: scored[field].research.value }, undefined, {
        source: "claude_web",
        confidence: 90,
        confidenceByField: productionConfidenceByField(scored),
      }),
    };
  };

  const fresh = runLane("2026-06-01");
  const stale = runLane("2021-04-06"); // Wyong's real stale listing

  // Precondition: the two lanes genuinely differ upstream, so the equality below is a
  // real invariant rather than two identical inputs compared to each other.
  assert.notEqual(fresh.composite, stale.composite,
    "the lanes must differ in composite score, or this proves nothing");

  const strip = stripVerifiedAt;
  assert.deepEqual(strip(fresh.merged.canonicalPatch), strip(stale.merged.canonicalPatch));
  assert.equal(stale.merged.canonicalPatch[field], "broadcaster",
    "stale evidence still promotes through the production path — recency is bias, not a gate");
  // Provenance must record the JUDGE's confidence, not the composite — the leak would show here first.
  assert.equal(fresh.merged.provenance[field].confidence, 88);
  assert.equal(stale.merged.provenance[field].confidence, 88);
});
