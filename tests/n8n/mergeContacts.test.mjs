// tests/n8n/mergeContacts.test.mjs
//
// Phase 16.2 Task 2 — proves the additive evidence/confidenceByField port onto
// mergeContacts.js (mirroring mergeCompanies.js:93-99,113-116,150-202): (a) the ONE
// existing caller's shape is unchanged when the new opts are absent (the additive
// proof); (b) an evidence-required field withholds promotion without a URL; (c) the
// same field promotes and carries the URL in provenance once one is supplied; (d)
// confidenceByField overrides the flat confidence per field.
//
// Run: node --test tests/n8n/mergeContacts.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { mergeContacts, DEFAULT_CONTACT_POLICY } =
  require(path.join(ROOT, "n8n/code/mergeContacts.js"));

// A jobtitle policy override carrying an evidence requirement — DEFAULT_CONTACT_POLICY
// itself declares no require_evidence_url/require_evidence_url_for entries (the port is
// inert for every existing contact field), so tests (b)/(c) supply an override policy,
// the same technique mergeCompanies.test.mjs uses for its own evidence-gate cases.
const EVIDENCE_REQUIRED_POLICY = {
  ...DEFAULT_CONTACT_POLICY,
  jobtitle: { ...DEFAULT_CONTACT_POLICY.jobtitle, require_evidence_url: true },
};

// --- (a) additive proof: absent opts -> provenance/decisions shape unchanged ---------
test("mergeContacts: return shape is exactly canonicalPatch/provenance/cacheKeys/decisions", () => {
  const result = mergeContacts({}, { jobtitle: "VP Engineering" }, undefined,
    { source: "waterfall", confidence: 90 });
  assert.deepEqual(Object.keys(result).sort(),
    ["cacheKeys", "canonicalPatch", "decisions", "provenance"]);
});

test("mergeContacts: absent evidence/confidenceByField opts is byte-identical to the pre-port shape (the ONE existing ENRICH_MERGE caller)", () => {
  // mergeContacts(existing, candidate, undefined, {source, confidence}) — exactly the
  // ENRICH_MERGE provider call shape (build_cloud_workflows.py's ENRICH_MERGE), which
  // omits both new opts.
  const result = mergeContacts({}, { jobtitle: "VP Engineering", seniority: "vp" },
    undefined, { source: "waterfall", confidence: 90 });

  assert.equal(result.canonicalPatch.jobtitle, "VP Engineering");
  assert.equal(result.canonicalPatch.seniority, "vp");

  const jobtitleEntry = result.provenance.jobtitle;
  assert.equal(jobtitleEntry.source, "waterfall");
  assert.equal(jobtitleEntry.confidence, 90);
  assert.equal(jobtitleEntry.validation_status, "provider_only");
  assert.equal(jobtitleEntry.value, "VP Engineering");
  assert.ok(!("evidence_url" in jobtitleEntry), "provenance omits evidence_url entirely when none supplied");

  const jobtitleDecision = result.decisions.find((d) => d.field === "jobtitle");
  assert.equal(jobtitleDecision.confidence, 90);
  assert.equal(jobtitleDecision.evidence_url, null, "decisions record still carries evidence_url:null (mirrors mergeCompanies' unconditional key)");
});

test("mergeContacts: opts.confidenceByField:{} (present-but-empty) is byte-identical to opts omitting it entirely (modulo verified_at)", () => {
  const withoutOption = mergeContacts({}, { jobtitle: "VP Engineering" }, undefined,
    { source: "waterfall", confidence: 90 });
  const withEmptyMap = mergeContacts({}, { jobtitle: "VP Engineering" }, undefined,
    { source: "waterfall", confidence: 90, confidenceByField: {} });
  const strip = (r) => JSON.parse(JSON.stringify(r).replace(/"verified_at":"[^"]*"/g, '"verified_at":"_"'));
  assert.deepEqual(strip(withoutOption), strip(withEmptyMap));
});

// --- (b) evidence-required field, no URL -> withheld ----------------------------------
test("mergeContacts: an evidence-required field at high confidence with NO evidence url is withheld (needs_review, not promoted)", () => {
  const { canonicalPatch, decisions } = mergeContacts({}, { jobtitle: "VP Engineering" },
    EVIDENCE_REQUIRED_POLICY, { source: "claude_web", confidence: 95 });
  assert.ok(!("jobtitle" in canonicalPatch));
  const d = decisions.find((x) => x.field === "jobtitle");
  assert.equal(d.decision, "needs_review");
  assert.equal(d.evidence_url, null);
});

// --- (c) evidence-required field, WITH URL -> promotes, provenance carries it ---------
test("mergeContacts: the same evidence-required field WITH an evidence url promotes, provenance carries evidence_url", () => {
  const { canonicalPatch, provenance } = mergeContacts({}, { jobtitle: "VP Engineering" },
    EVIDENCE_REQUIRED_POLICY,
    { source: "claude_web", confidence: 95, evidence: { jobtitle: "https://acme.example/team" } });
  assert.equal(canonicalPatch.jobtitle, "VP Engineering");
  assert.equal(provenance.jobtitle.evidence_url, "https://acme.example/team");
});

// --- (d) confidenceByField overrides the flat confidence per field --------------------
test("mergeContacts: confidenceByField overrides one field above threshold while a second field absent from the map still uses the flat (sub-threshold) confidence", () => {
  const candidate = { jobtitle: "VP Engineering", seniority: "vp" };
  // Flat confidence (60) is below both fields' thresholds (75 / 75).
  const { canonicalPatch, decisions } = mergeContacts({}, candidate, undefined,
    { source: "claude_web", confidence: 60, confidenceByField: { jobtitle: 90 } });
  // jobtitle is stale_refreshable: a blank current value promotes once the (overridden)
  // confidence clears its threshold (75).
  assert.equal(canonicalPatch.jobtitle, "VP Engineering", "overridden field (jobtitle, confidence 90) promotes");
  assert.ok(!("seniority" in canonicalPatch), "field absent from the map keeps the flat (sub-threshold) confidence and does not promote");
  assert.equal(decisions.find((d) => d.field === "seniority").confidence, 60);
});

test("mergeContacts: recorded confidence matches deciding confidence for an overridden field (provenance + decision both carry the overridden value)", () => {
  const { provenance, decisions } = mergeContacts({}, { jobtitle: "VP Engineering" }, undefined,
    { source: "claude_web", confidence: 60, confidenceByField: { jobtitle: 90 } });
  assert.equal(provenance.jobtitle.confidence, 90);
  assert.equal(decisions.find((d) => d.field === "jobtitle").confidence, 90);
});

// --- Existing behavior stays unchanged (email hard-guard, cache keys) -----------------
test("mergeContacts: email hard guard still forces stage_only even when opts carries evidence/confidenceByField", () => {
  const overridePolicy = { ...DEFAULT_CONTACT_POLICY, email: { class: "system_owned", min_confidence: 0 } };
  const { canonicalPatch, decisions } = mergeContacts({}, { email: "new@example.com" },
    overridePolicy, { source: "claude_web", confidence: 100, confidenceByField: { email: 100 } });
  assert.ok(!("email" in canonicalPatch), "email must never appear in canonicalPatch");
  const d = decisions.find((x) => x.field === "email");
  assert.equal(d.decision, "stage_only");
});

test("mergeContacts: cache-key mapping for jobtitle is unaffected by the port", () => {
  const { cacheKeys } = mergeContacts({}, { jobtitle: "VP Engineering", seniority: "vp" },
    undefined, { source: "claude_web", confidence: 90 });
  assert.ok(cacheKeys.lv_jobtitle_verified_at, "jobtitle has a cache-key mapping");
  assert.ok(!("seniority_verified_at" in cacheKeys), "seniority has no cache-key mapping");
});
