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
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { mergeCompanies, DEFAULT_COMPANY_POLICY } =
  require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

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
  assert.equal(canonicalPatch.lv_produces_content, true);
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

// --- Flat opts.confidence default ------------------------------------------------------
test("mergeCompanies: flat opts.confidence default (80) applies when opts omits it", () => {
  const { decisions } = mergeCompanies({}, { lv_content_type: ["live_broadcast"] }, undefined, {});
  const d = decisions.find((x) => x.field === "lv_content_type");
  assert.equal(d.confidence, 80);
});
