// tests/n8n/decideCompanyActionCreateSeedProvenance.test.mjs
//
// Quick task 260904-pav, Task 2 — the two seams that make the provenance-aware
// `manual_protected` correction (Task 1) reachable at all. Both live in
// ENRICH_DECIDE_CO_CLOUD's node jsCode, NOT in the pure mergeCompanies module, so
// tests/n8n/mergeCompanies.test.mjs cannot reach them.
//
//   SEAM 1 (the seed). The create branch seeds `properties.domain = id.domain` (BUG 19)
//   and wrote no provenance, so the record it created carried a system-written domain
//   with no entry at all — and the fail-closed rule refuses that. Without a
//   `create_seed` stamp the correction path has nothing to key on and Task 1 is inert.
//
//   SEAM 2 (the blob). The enrichment lane REPLACED lv_enrichment_provenance with this
//   run's merge.provenance, and merge.provenance only ever carries fields in this run's
//   candidate set. So the first enrich after a create wiped the seed. Making the write
//   additive is required for the fix to function, and independently repairs a latent
//   loss affecting EVERY field, not just domain.
//
// Harness idiom copied verbatim from
// tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs — `new Function(...)`
// over the committed workflow's own jsCode, so the assertions track the shipped artifact.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadNodeJsCode(name) {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n/wf_enrichment_cloud.json"), "utf8"));
  return wf.nodes.find((n) => n.name === name).parameters.jsCode;
}

function runCodeNode(jsCode, row) {
  const $input = { all: () => [{ json: row }], get item() { return { json: row }; } };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, row, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}

const DECIDE = loadNodeJsCode("Decide Company Action");
const MERGE_COMPANY = loadNodeJsCode("Merge Company");

function provenanceOf(out) {
  const raw = out.properties && out.properties.lv_enrichment_provenance;
  return raw === undefined ? undefined : JSON.parse(raw);
}

// --- SEAM 1: the create seed ---------------------------------------------------------
function createRow(mode) {
  return {
    action: "create",
    mode,
    identity_keys: { domain: "brisbanelions.com.au", companyName: "Brisbane Lions" },
    merge: null,
  };
}

test("create: the seeded domain gets a create_seed provenance entry", () => {
  const out = runCodeNode(DECIDE, createRow("write"));
  assert.equal(out.properties.domain, "brisbanelions.com.au", "BUG 19's seed is unchanged");
  const entry = provenanceOf(out).domain;
  assert.ok(entry, "the seeded domain must carry a provenance entry to key a correction on");
  assert.equal(entry.source, "create_seed");
  assert.equal(entry.validation_status, "request_echo");
  assert.equal(entry.confidence, 0, "an unverified echo of the caller's own request is not evidence");
  assert.equal(entry.value, "brisbanelions.com.au");
  assert.ok(entry.verified_at, "same entry shape as every other provenance writer");
});

test("create in return-only mode stamps nothing — the !returnOnly gate is unmoved", () => {
  const out = runCodeNode(DECIDE, createRow("propose"));
  assert.ok(!("domain" in out.properties), "a propose response never carries the caller's identity");
  assert.equal(out.properties.lv_enrichment_provenance, undefined);
});

test("create with no domain in identity_keys stamps no entry", () => {
  const row = { ...createRow("write"), identity_keys: { companyName: "Nameless" } };
  const out = runCodeNode(DECIDE, row);
  assert.equal(out.properties.lv_enrichment_provenance, undefined);
});

// --- SEAM 2: the blob is additive ----------------------------------------------------
const PRIOR_BLOB = JSON.stringify({
  domain: { source: "create_seed", confidence: 0, verified_at: "2026-09-04T00:00:00.000Z",
            validation_status: "request_echo", value: "brisbanelions.com.au" },
  lv_org_type: { source: "claude_web", confidence: 90, verified_at: "2026-08-01T00:00:00.000Z",
                 validation_status: "provider_only", value: "individual_club_team" },
});

function enrichRow(existingProvenance) {
  return {
    action: "enrich",
    mode: "write",
    identity_keys: {},
    existingRecord: { hs_object_id: "285583534546", domain: "brisbanelions.com.au",
                      lv_enrichment_provenance: existingProvenance },
    merge: {
      canonicalPatch: { lv_content_type: "streaming" },
      cacheKeys: {},
      provenance: { lv_content_type: { source: "claude_web", confidence: 90,
                                       verified_at: "2026-09-04T12:00:00.000Z",
                                       validation_status: "provider_only", value: "streaming" } },
      decisions: [{ field: "lv_content_type", decision: "promote" }],
    },
  };
}

test("enrich: a field this run did not touch keeps its provenance entry", () => {
  const blob = provenanceOf(runCodeNode(DECIDE, enrichRow(PRIOR_BLOB)));
  assert.equal(blob.domain.source, "create_seed",
    "the create seed must survive the first enrich, or the correction path can never fire");
  assert.equal(blob.lv_org_type.source, "claude_web", "and so must every other untouched field");
  assert.equal(blob.lv_content_type.value, "streaming", "this run's own entry is written");
});

test("enrich: this run wins on collision — same spread order as the review lane", () => {
  const row = enrichRow(JSON.stringify({
    lv_content_type: { source: "june_2026", confidence: 70, verified_at: "2026-06-01T00:00:00.000Z",
                       validation_status: "provider_only", value: "highlights" },
  }));
  const blob = provenanceOf(runCodeNode(DECIDE, row));
  assert.equal(blob.lv_content_type.source, "claude_web");
  assert.equal(blob.lv_content_type.value, "streaming");
});

test("enrich: an unparseable existing blob is treated as empty and does not throw", () => {
  let out;
  assert.doesNotThrow(() => { out = runCodeNode(DECIDE, enrichRow("{not json")); });
  const blob = provenanceOf(out);
  assert.deepEqual(Object.keys(blob), ["lv_content_type"]);
});

test("a row with no merge and no seed writes no provenance property at all", () => {
  // The recompute lane (merge: null, CLAUDE.md §13.0): making the blob additive must not
  // start rewriting the property on rows that have nothing new to say.
  const out = runCodeNode(DECIDE, {
    action: "enrich", mode: "write", identity_keys: {},
    existingRecord: { hs_object_id: "1", lv_enrichment_provenance: PRIOR_BLOB },
    merge: null,
  });
  assert.equal(out.properties.lv_enrichment_provenance, undefined);
});

// --- SEAM 3: Merge Company hands the row's conflict state to mergeCompanies ----------
test("Merge Company passes rowConflicted from the conflicts it already computed", () => {
  // Asserted on the emitted node source, deliberately. The waterfall fold calls
  // mergeCompanies at a flat confidence of 85 and `domain` demands 95, so no input to
  // this node can produce an observably different DECISION today — per the plan's finding
  // 5 there is no domain candidate source at all yet. What is observable, and what this
  // pins, is that the harveynorman.com.au franchisor guard is wired to the correction
  // path rather than left at its fail-closed default.
  assert.match(MERGE_COMPANY, /rowConflicted:\s*conflicts\.length\s*>\s*0/);
  const waterfallCall = MERGE_COMPANY.indexOf('source: "waterfall"');
  assert.ok(waterfallCall !== -1);
  assert.ok(MERGE_COMPANY.slice(waterfallCall - 200, waterfallCall + 200).includes("rowConflicted"),
    "the flag belongs on the waterfall fold — the only call whose field allowlist has `domain`");
});
