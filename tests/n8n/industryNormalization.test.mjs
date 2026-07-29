// tests/n8n/industryNormalization.test.mjs
//
// NORM-01 red-before-green proof: a numeric provider industry code must never masquerade
// as a normalized `industry` candidate value, and must never win the cross-provider
// waterfall on the ZoomInfo source-trust constant alone (ROADMAP Phase 18 criteria 1+2).
//
// Built against the REAL recorded execution-19 shape:
//   - ZoomInfo side: the committed live fixture tests/fixtures/enrichment/zoominfo_live_company.json
//     (Racing NSW, real recorded GTM response) used verbatim, unmodified.
//   - Apollo side: a minimal constructed raw shape carrying the industry text observed live
//     during execution-19 (see APOLLO_EXEC19_COMPANY below) — never fixture-ized.
//
// Run: node --test tests/n8n/industryNormalization.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));
const { scoreCandidates } = require(path.join(ROOT, "n8n/code/scoreEnrichment.js"));

const FIX = path.join(ROOT, "tests/fixtures/enrichment");
const load = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name), "utf8"));
const NOW = "2026-07-14T00:00:00Z"; // pinned; scoreCandidates never reads ambient Date.now

const zoomLiveCo = load("zoominfo_live_company.json"); // real GTM companies/enrich, Racing NSW

// Apollo's `"media production"` industry text was observed LIVE during execution-19
// (see .planning/debug/bug-17-lusha-company-400.md, "Related observation" section) but was
// never captured as a committed fixture — reconstructed here as the minimal raw shape
// apolloCandidates() reads (raw.organization.industry), carrying no updated_at, matching the
// live observation that ZoomInfo's numeric code beat it on trust alone with both A and R tied.
const APOLLO_EXEC19_COMPANY = {
  organization: {
    industry: "media production",
  },
};

function find(cands, field, source) {
  return cands.find((c) => c.field === field && c.source === source);
}

const ALL_DIGITS = /^\d+$/;

// --- CRITERION 1: single provider, no scoring ----------------------------------
test("CRITERION 1: ZoomInfo live industry candidate is human-readable text, never a bare NAICS code", () => {
  const c = toCandidates("zoominfo", zoomLiveCo, "companies");
  const industry = find(c, "industry", "zoominfo");
  assert.ok(industry, "zoominfo must still emit an industry candidate for this fixture");
  assert.doesNotMatch(
    String(industry.normalizedValue),
    ALL_DIGITS,
    "normalizedValue must not be an all-ASCII-digit NAICS code"
  );
  // D-NORM-precedence: the NAICS entry's own .name text, not primaryIndustry.
  assert.equal(industry.value, "Arts, Entertainment, and Recreation");
  assert.equal(industry.normalizedValue, "arts, entertainment, and recreation");
});

// --- CRITERION 2: both providers scored together (the actual waterfall) --------
test("CRITERION 2: industry waterfall winner is text even though ZoomInfo's source trust beats Apollo's", () => {
  const zi = toCandidates("zoominfo", zoomLiveCo, "companies");
  const apollo = toCandidates("apollo", APOLLO_EXEC19_COMPANY, "companies");
  const all = [...zi, ...apollo];

  const { best, ranked } = scoreCandidates(all, { now: NOW });
  const ind = best.industry;

  assert.ok(ind, "an industry winner must exist");
  assert.doesNotMatch(
    String(ind.normalizedValue),
    ALL_DIGITS,
    "no all-digit value may win the industry waterfall on trust alone"
  );

  // Document WHY this is the trust-tiebreak shape: both candidates tie on A and R and have
  // zero agreement (a numeric code never text-agrees with a competitor), so only T (source
  // trust: zoominfo 0.85 vs apollo 0.75) separates them. This test does NOT assert which
  // provider wins — only that the winning VALUE'S SHAPE is text, per the criterion.
  const industryRanked = ranked.industry;
  assert.equal(industryRanked.length, 2, "exactly one candidate per provider");
  const [top, second] = industryRanked;
  assert.equal(top.components.A, second.components.A, "accuracy ties (both ungraded 0.6)");
  assert.equal(top.components.R, second.components.R, "recency ties (neither carries a recencyDate)");
  assert.equal(top.components.G, 0, "no cross-provider agreement on a bare-text vs bare-text mismatch");
  assert.equal(second.components.G, 0, "no cross-provider agreement on a bare-text vs bare-text mismatch");
  assert.notEqual(top.components.T, second.components.T, "source trust is the sole differentiator");
});

// --- EDGE D-NORM-empty: ZoomInfo bare code + no text fallback -> zero candidates -
test("EDGE D-NORM-empty: ZoomInfo bare NAICS code with no primaryIndustry emits ZERO industry candidates", () => {
  const mk = (attrs) => ({
    data: [{ id: "1", type: "Company", attributes: attrs, meta: { matchStatus: "FULL_MATCH" } }],
  });
  const raw = mk({ name: "Bare Code Co", naicsCodes: ["711211"] }); // no .name, no primaryIndustry
  const c = toCandidates("zoominfo", raw, "companies");
  assert.equal(
    c.filter((x) => x.field === "industry").length,
    0,
    "a bare code with no fallback text must never emit a numeric industry candidate"
  );
});

// --- EDGE D-NORM-empty, Lusha twin ---------------------------------------------
test("EDGE D-NORM-empty (Lusha): bare NAICS code with no mainIndustry emits ZERO industry candidates", () => {
  const raw = { naicsCodes: ["711211"], revenueRange: "10M-25M" }; // no mainIndustry
  const c = toCandidates("lusha", raw, "companies");
  assert.equal(
    c.filter((x) => x.field === "industry").length,
    0,
    "a bare code with no fallback text must never emit a numeric industry candidate"
  );
});
