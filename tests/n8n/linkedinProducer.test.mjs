// tests/n8n/linkedinProducer.test.mjs
//
// Phase 66 Plan 01 Task 3 (D-66-02, D-66-03, RICH-03) — no provider mapper in
// n8n/code/normalizeProviders.js ever emitted a linkedin_url candidate, so lv_linkedin_url
// had no producer at all. This test proves the fix from two angles: Layer 1 exercises the
// host guard and the Apollo producer directly over toCandidates() output; Layer 2 is the
// D-66-03 key-seam proof — the produced candidate is fed through the REAL scoreEnrichment
// and mergeContacts logic (via the compiled node bodies read out of the committed
// n8n/wf_enrichment_cloud.json, the same `new Function(...)` idiom
// tests/n8n/personaGroupProducer.test.mjs already uses), so this test proves the merge
// actually consumes what the producer emits, not a hand-written reimplementation of it.
//
// Also covers the D-66-01 gate-widening behavior: decideAction against a fully-populated
// twelve-field record skips, and a single blanked field reports as missing.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));
const { scoreCandidates } = require(path.join(ROOT, "n8n/code/scoreEnrichment.js"));
const { canonicalizeLinkedin } = require(path.join(ROOT, "n8n/code/resolveIdentity.js"));
const { mergeContacts } = require(path.join(ROOT, "n8n/code/mergeContacts.js"));
const { decideAction } = require(path.join(ROOT, "n8n/code/enrichmentGate.js"));

function find(cands, field, source) {
  return cands.find((c) => c.field === field && c.source === source);
}

function loadWorkflow() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return byName;
}

function runJsCode(jsCode, items) {
  const $input = {
    all: () => items.map((j) => ({ json: j })),
    get item() { return { json: items[0] }; },
  };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date("2026-09-05T00:00:00Z");
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today", "$runIndex",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, items[0], {}, $now, $now, 0) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// ---------------------------------------------------------------------------
// Layer 1: producer-level proof — the host guard + the Apollo push.
// ---------------------------------------------------------------------------

test("(a) an Apollo response nesting a person with a linkedin.com URL produces exactly one candidate, field unprefixed, source apollo", () => {
  const raw = { person: { linkedin_url: "https://www.linkedin.com/in/example/" } };
  const c = toCandidates("apollo", raw, "contacts");
  const hits = c.filter((x) => x.field === "linkedin_url");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].source, "apollo");
  assert.equal(hits[0].value, "https://www.linkedin.com/in/example/");
});

test("(b) the same response with person flat (not nested) produces the same candidate", () => {
  const raw = { linkedin_url: "https://www.linkedin.com/in/example/" };
  const c = toCandidates("apollo", raw, "contacts");
  const hit = find(c, "linkedin_url", "apollo");
  assert.ok(hit);
  assert.equal(hit.value, "https://www.linkedin.com/in/example/");
});

test("(c) a LinkedIn value on a non-linkedin.com host produces NO candidate (T-66-01)", () => {
  const raw = { person: { linkedin_url: "https://evil-linkedin.com/in/example/" } };
  const c = toCandidates("apollo", raw, "contacts");
  assert.ok(!find(c, "linkedin_url", "apollo"));
});

test("(d) a lookalike suffix host (linkedin.com.evil.example) produces NO candidate", () => {
  const raw = { person: { linkedin_url: "https://linkedin.com.evil.example/in/example/" } };
  const c = toCandidates("apollo", raw, "contacts");
  assert.ok(!find(c, "linkedin_url", "apollo"));
});

test("(e) absent, empty, or null linkedin_url produces NO candidate, and does not throw", () => {
  for (const raw of [{ person: {} }, { person: { linkedin_url: "" } }, { person: { linkedin_url: null } }, {}]) {
    assert.doesNotThrow(() => toCandidates("apollo", raw, "contacts"));
    assert.ok(!find(toCandidates("apollo", raw, "contacts"), "linkedin_url", "apollo"));
  }
});

test("(f) a subdomain of linkedin.com (www, country-prefixed) IS accepted", () => {
  for (const url of ["https://www.linkedin.com/in/x/", "https://au.linkedin.com/in/x/", "https://linkedin.com/in/x/"]) {
    const c = toCandidates("apollo", { person: { linkedin_url: url } }, "contacts");
    const hit = find(c, "linkedin_url", "apollo");
    assert.ok(hit, `expected a candidate for ${url}`);
    assert.equal(hit.value, url);
  }
});

test("(g) a host that merely ENDS WITH a linkedin.com-lookalike suffix is NOT accepted", () => {
  for (const url of ["https://notlinkedin.com/in/x/", "https://fake-linkedin.com/in/x/"]) {
    const c = toCandidates("apollo", { person: { linkedin_url: url } }, "contacts");
    assert.ok(!find(c, "linkedin_url", "apollo"), `expected NO candidate for ${url}`);
  }
});

// ---------------------------------------------------------------------------
// Layer 2: the D-66-03 key-seam proof — scoreCandidates -> ENRICH_MERGE's rename ->
// mergeContacts, run through the REAL compiled node bodies.
// ---------------------------------------------------------------------------

test("(h) scoreCandidates groups the candidate under the UNPREFIXED winner key", () => {
  const c = toCandidates("apollo", { person: { linkedin_url: "https://www.linkedin.com/in/example/" } }, "contacts");
  const { winners } = scoreCandidates(c, { now: "2026-09-05T00:00:00Z" });
  assert.equal(winners.linkedin_url, "https://www.linkedin.com/in/example/");
});

test("(i) the exact rename expression ENRICH_MERGE uses lands the value under the PREFIXED merge candidate key", () => {
  const c = toCandidates("apollo", { person: { linkedin_url: "https://www.linkedin.com/in/example/" } }, "contacts");
  const { winners } = scoreCandidates(c, { now: "2026-09-05T00:00:00Z" });
  // This IS the expression ENRICH_MERGE runs (scripts/build_cloud_workflows.py, search
  // `canonicalizeLinkedin(winners.`) — not a reimplementation.
  const candidate = {};
  const canonicalWinnerLinkedin = canonicalizeLinkedin(winners.linkedin_url);
  if (canonicalWinnerLinkedin) candidate.lv_linkedin_url = canonicalWinnerLinkedin;
  assert.ok(candidate.lv_linkedin_url, "candidate must carry the prefixed key");
  assert.equal(candidate.lv_linkedin_url, canonicalizeLinkedin("https://www.linkedin.com/in/example/"));
});

test("(j) mergeContacts promotes the produced value into a BLANK existing record", () => {
  const c = toCandidates("apollo", { person: { linkedin_url: "https://www.linkedin.com/in/example/" } }, "contacts");
  const { winners } = scoreCandidates(c, { now: "2026-09-05T00:00:00Z" });
  const candidate = { lv_linkedin_url: canonicalizeLinkedin(winners.linkedin_url) };
  const { canonicalPatch, decisions } = mergeContacts({}, candidate, undefined, { source: "waterfall", confidence: 85 });
  assert.equal(canonicalPatch.lv_linkedin_url, candidate.lv_linkedin_url);
  const d = decisions.find((x) => x.field === "lv_linkedin_url");
  assert.equal(d.decision, "promote");
});

test("(k) mergeContacts STAGES ONLY against an existing record already holding a different LinkedIn URL (D-66-08 non-clobber)", () => {
  const c = toCandidates("apollo", { person: { linkedin_url: "https://www.linkedin.com/in/example/" } }, "contacts");
  const { winners } = scoreCandidates(c, { now: "2026-09-05T00:00:00Z" });
  const candidate = { lv_linkedin_url: canonicalizeLinkedin(winners.linkedin_url) };
  const existing = { lv_linkedin_url: "https://www.linkedin.com/in/someone-else/" };
  const { canonicalPatch, decisions } = mergeContacts(existing, candidate, undefined, { source: "waterfall", confidence: 85 });
  assert.equal(canonicalPatch.lv_linkedin_url, undefined, "a populated stored value must never be overwritten");
  const d = decisions.find((x) => x.field === "lv_linkedin_url");
  assert.equal(d.decision, "stage_only");
});

// ---------------------------------------------------------------------------
// Layer 2b: row-flow proof through the REAL compiled "Normalize + Score" then
// "Merge Winners" node bodies (mirrors personaGroupProducer.test.mjs's harness).
// ---------------------------------------------------------------------------

function gateRow() {
  return {
    action: "enrich",
    object_type: "contacts",
    identity_keys: { domain: null },
    existingRecord: { hs_object_id: "301", email: "x@lightningvisuals.com", lv_linkedin_url: "" },
  };
}

// F5 fix (2026-09-09, .planning/debug/uat-batch-review-row-reads-failed.md):
// "Normalize + Score" now reads $runIndex to pair with the SAME run of
// "Enrichment Gate" (recoverConvergedRun, n8n/code/nodeRunRecovery.js). This
// harness models exactly ONE run of everything, so $runIndex is always 0; the
// mock .all() below ignores the (branch, run) args it is now called with,
// same single-run behaviour as before.
function runNormalizeAndScore(jsCode, providerResponses) {
  const outputs = {
    "Enrichment Gate": [gateRow()],
    "Lusha Enrich": providerResponses.lusha !== undefined ? [providerResponses.lusha] : [],
    "Apollo Match": providerResponses.apollo !== undefined ? [providerResponses.apollo] : [],
    "ZoomInfo Enrich": providerResponses.zoominfo !== undefined ? [providerResponses.zoominfo] : [],
  };
  const $ = (name) => ({
    all: () => (outputs[name] || []).map((j) => ({ json: j })),
    get item() { return { json: (outputs[name] || [])[0] }; },
  });
  const $input = { all: () => [], get item() { return { json: undefined }; } };
  const $now = new Date("2026-09-05T00:00:00Z");
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today", "$runIndex",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, undefined, {}, $now, $now, 0) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

test("(l) the compiled Normalize + Score then Merge Winners bodies carry a live Apollo LinkedIn URL through to lv_linkedin_url in canonicalPatch", () => {
  const nodes = loadWorkflow();
  const apolloResponse = { person: { linkedin_url: "https://www.linkedin.com/in/example/" } };
  const scoredOut = runNormalizeAndScore(nodes["Normalize + Score"].parameters.jsCode, { apollo: apolloResponse });
  assert.ok(scoredOut[0].scored, "Normalize + Score produced a real scored object");
  assert.equal(scoredOut[0].scored.winners.linkedin_url, "https://www.linkedin.com/in/example/");
  const mergeOut = runJsCode(nodes["Merge Winners"].parameters.jsCode, scoredOut);
  assert.equal(mergeOut[0].merge.canonicalPatch.lv_linkedin_url, canonicalizeLinkedin("https://www.linkedin.com/in/example/"));
});

// ---------------------------------------------------------------------------
// D-66-01 gate widening: decideAction against a fully-populated twelve-field record.
// ---------------------------------------------------------------------------

const REQUIRED = [
  "city", "country", "email", "hs_country_region_code", "hs_state_code", "jobtitle",
  "lv_linkedin_url", "lv_persona_group", "mobilephone", "phone", "seniority", "state",
];
const POLICY = { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } };
const NOW = "2026-09-05T00:00:00Z";

function daysAgoIso(days) {
  return new Date(Date.parse(NOW) - days * 86400000).toISOString();
}

// The two cache-key timestamps are load-bearing in the fixture, not decoration: POLICY
// carries a TTL for jobtitle/mobilephone, and decideAction treats a present value with a
// blank cache key as stale (unknown freshness -> validate). Copied from the RT-5 skip
// fixture in tests/n8n/enrichmentGate.test.mjs, which pairs each TTL'd field with a
// recent timestamp for exactly this reason.
function fullRecord() {
  return {
    city: "Sydney", country: "Australia", email: "a@b.com",
    hs_country_region_code: "AU", hs_state_code: "NSW", jobtitle: "GM",
    lv_linkedin_url: "https://www.linkedin.com/in/example/", lv_persona_group: "media_and_communication",
    mobilephone: "+61412345678", phone: "+61299999999", seniority: "director", state: "NSW",
    lv_jobtitle_verified_at: daysAgoIso(10),
    lv_mobilephone_verified_at: daysAgoIso(10),
  };
}

test("(m) decideAction against a fully-populated 12-field record with fresh cache keys -> skip", () => {
  const gate = decideAction(fullRecord(), REQUIRED, POLICY, NOW);
  assert.equal(gate.action, "skip");
  assert.deepEqual(gate.missingFields, []);
});

test("(n) blanking any one of the twelve fields puts that field name in missingFields", () => {
  for (const field of REQUIRED) {
    const record = fullRecord();
    record[field] = "";
    const gate = decideAction(record, REQUIRED, POLICY, NOW);
    assert.ok(gate.missingFields.includes(field), `expected ${field} in missingFields`);
  }
});
