// tests/n8n/reviewHumanProvenance.test.mjs
//
// Phase 30 Plan 03 — the human-provenance stamp an approval writes (D-08/D-08a/D-08b,
// REVIEW-04).
//
// This file guards ONE thing the rest of the endpoint tests cannot: the provenance blob
// is rewritten WHOLE on every approval, so a bug here silently erases audit history that
// no other assertion would notice (T-30-13). Every fixture blob is therefore built from a
// REAL mergeCompanies() run rather than hand-typed, so the shape under test is the shape
// the pipeline actually writes.
//
// The blob model is the deployed one, not the root CLAUDE.md's: ONE JSON object per
// record (`lv_enrichment_provenance` / `lv_contact_enrichment_provenance`) keyed by field,
// entries `{source, confidence, verified_at, validation_status, value, evidence_url?}`,
// and NO `verified_by_model` key anywhere (30 D-08a). The absence of that key is asserted
// by key PRESENCE, not by a string search — a grep cannot tell an absent key from one
// whose value happens to be null.
//
// No network call, no I/O beyond reading the module under test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { buildReviewDecision, buildHumanProvenance } =
  require(path.join(ROOT, "n8n/code/reviewDecision.js"));
const { mergeCompanies, stableStringify } =
  require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

const NOW = "2026-07-31T04:05:06.000Z";
const P_PROVENANCE = "lv_enrichment_provenance";

// A real pipeline-written blob: three fields, one of which no decision below touches.
function realBlob() {
  const { provenance } = mergeCompanies(
    { domain: "exampleracing.example", industry: "Sports",
      lv_org_type: "broadcaster", lv_produces_content: false },
    { industry: "Sports & Entertainment", lv_org_type: "governing_body_league",
      lv_produces_content: true },
    undefined, { source: "claude_web", confidence: 60 });
  assert.ok(provenance.industry && provenance.lv_org_type && provenance.lv_produces_content,
    "fixture must be a real three-field provenance object");
  return provenance;
}

// --- entry shape -----------------------------------------------------------------------

test("an approved field's entry carries the human source, status, timestamp, value and reason", () => {
  const { entries } = buildHumanProvenance({
    existingJson: stableStringify(realBlob()),
    applied: { lv_org_type: "governing_body_league" },
    reason: "Confirmed from the About page — it sanctions the series.",
    verifiedAt: NOW,
  });
  const entry = entries.lv_org_type;

  assert.equal(entry.source, "human", "config/source_registry.yaml's registered reviewer source");
  assert.equal(entry.confidence, 100);
  assert.equal(entry.verified_at, NOW, "the DECISION's time, threaded in, never re-computed here");
  assert.equal(entry.validation_status, "human_approved");
  assert.equal(entry.value, "governing_body_league");
  assert.equal(entry.reason, "Confirmed from the About page — it sanctions the series.");
});

test("the entry carries NO model-attribution key — the deployed blob has never had one (D-08a)", () => {
  const { entries } = buildHumanProvenance({
    existingJson: stableStringify(realBlob()),
    applied: { lv_org_type: "governing_body_league" }, reason: "x", verifiedAt: NOW,
  });
  assert.equal("verified_by_model" in entries.lv_org_type, false,
    "verified_by_model is a root-CLAUDE.md fiction; introducing it here would fork the shape");
  assert.deepEqual(Object.keys(entries.lv_org_type).sort(),
    ["confidence", "reason", "source", "superseded_source", "validation_status",
     "value", "verified_at"]);
});

test("the machine attribution the human decision replaced is preserved, not erased", () => {
  const blob = realBlob();
  assert.equal(blob.lv_org_type.source, "claude_web", "non-vacuity: there IS a prior source");
  const { entries } = buildHumanProvenance({
    existingJson: stableStringify(blob),
    applied: { lv_org_type: "governing_body_league" }, reason: "", verifiedAt: NOW,
  });
  assert.equal(entries.lv_org_type.superseded_source, "claude_web");
});

test("a field with no prior entry records an empty superseded source, never a missing key", () => {
  const { entries } = buildHumanProvenance({
    existingJson: stableStringify(realBlob()),
    applied: { lv_revenue_band: "5-50M" }, reason: "", verifiedAt: NOW,
  });
  assert.equal("superseded_source" in entries.lv_revenue_band, true);
  assert.equal(entries.lv_revenue_band.superseded_source, "");
});

test("an empty operator reason is an empty string, not a missing key", () => {
  for (const reason of ["", undefined, null, 7]) {
    const { entries } = buildHumanProvenance({
      existingJson: "{}", applied: { lv_org_type: "broadcaster" }, reason, verifiedAt: NOW,
    });
    assert.equal("reason" in entries.lv_org_type, true, `reason ${JSON.stringify(reason)}`);
    assert.equal(entries.lv_org_type.reason, "");
  }
});

// --- additivity (D-08b) ------------------------------------------------------------------

test("entries for fields this decision did not touch survive byte-identically", () => {
  const blob = realBlob();
  const before = JSON.parse(JSON.stringify(blob.industry));
  const { entries, json } = buildHumanProvenance({
    existingJson: stableStringify(blob),
    applied: { lv_org_type: "governing_body_league", lv_produces_content: true },
    reason: "operator confirmed", verifiedAt: NOW,
  });

  assert.deepEqual(entries.industry, before,
    "an untouched field's entry must be deep-equal before and after the merge");
  assert.deepEqual(JSON.parse(json).industry, before,
    "and must survive the re-serialization too");
  assert.deepEqual(Object.keys(JSON.parse(json)).sort(),
    ["industry", "lv_org_type", "lv_produces_content"],
    "the merge is an overlay, never a replacement");
});

test("the blob is re-serialized with stableStringify, so key order stays byte-comparable", () => {
  const { json } = buildHumanProvenance({
    existingJson: stableStringify(realBlob()),
    applied: { lv_org_type: "governing_body_league" }, reason: "x", verifiedAt: NOW,
  });
  assert.equal(json, stableStringify(JSON.parse(json)),
    "re-stringifying the parsed blob must be a fixed point — sorted keys, compact separators");
});

// --- a blob that cannot be read ----------------------------------------------------------

test("an unreadable existing blob degrades to empty and is REPORTED, never thrown", () => {
  for (const existingJson of ['{"lv_org_type":', "not json at all", "[]", '"a string"', "7"]) {
    const out = buildHumanProvenance({
      existingJson, applied: { lv_org_type: "broadcaster" }, reason: "x", verifiedAt: NOW,
    });
    assert.equal(out.unreadable, true, `must report unreadable for ${existingJson}`);
    assert.deepEqual(Object.keys(out.entries), ["lv_org_type"]);
  }
});

test("an absent or blank blob is simply empty — that is not an error", () => {
  for (const existingJson of [undefined, null, "", "   ", "{}"]) {
    const out = buildHumanProvenance({
      existingJson, applied: { lv_org_type: "broadcaster" }, reason: "x", verifiedAt: NOW,
    });
    assert.equal(out.unreadable, false);
    assert.deepEqual(Object.keys(out.entries), ["lv_org_type"]);
  }
});

test("buildHumanProvenance never throws, whatever it is handed", () => {
  for (const input of [undefined, null, {}, 42, "x", { applied: "nope" }]) {
    assert.doesNotThrow(() => buildHumanProvenance(input));
  }
});

// --- the blob as buildReviewDecision actually writes it -----------------------------------

test("an approval writes the merged blob into lv_enrichment_provenance and says the blob was unreadable when it was", () => {
  const existing = { domain: "exampleracing.example", lv_org_type: "broadcaster",
                     lv_produces_content: false };
  const { decisions } = mergeCompanies(existing,
    { lv_org_type: "governing_body_league", lv_produces_content: true },
    undefined, { source: "claude_web", confidence: 60 });
  const held = decisions.filter((d) => d.decision === "needs_review");

  const row = {
    ...existing, hs_object_id: "789", record_found: true,
    lv_enrichment_needs_review: "true",
    lv_enrichment_review_candidate_json: stableStringify(held),
    [P_PROVENANCE]: stableStringify(realBlob()),
  };

  const { properties, outcome, message } = buildReviewDecision({
    objectType: "companies", decision: "approve", reason: "checked the About page",
    reviewedBy: "revops@example.com", row, nowIso: NOW,
  });
  assert.equal(outcome, "applied");

  const blob = JSON.parse(properties[P_PROVENANCE]);
  assert.equal(blob.lv_org_type.source, "human");
  assert.equal(blob.lv_org_type.verified_at, NOW);
  assert.equal(blob.lv_produces_content.reason, "checked the About page");
  assert.deepEqual(blob.industry, realBlob().industry,
    "the field this approval never touched is carried through untouched");
  assert.doesNotMatch(message, /provenance/i,
    "a readable blob is the quiet path — no warning to the operator");

  const broken = buildReviewDecision({
    objectType: "companies", decision: "approve", reason: "x", reviewedBy: "revops",
    row: { ...row, [P_PROVENANCE]: '{"lv_org_type":' }, nowIso: NOW,
  });
  assert.equal(broken.outcome, "applied", "an unreadable blob must not block the decision");
  assert.match(broken.message, /provenance/i,
    "but the operator must be told the previous provenance could not be read");
  assert.deepEqual(Object.keys(JSON.parse(broken.properties[P_PROVENANCE])).sort(),
    ["lv_org_type", "lv_produces_content"]);
});
