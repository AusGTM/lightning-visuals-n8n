// tests/n8n/zeroFirmographicSentinel.test.mjs
//
// A provider's ZERO firmographic is a missing-data sentinel, never a real band.
//
// Found live 2026-07-31 while end-to-end probing the deployed cloud enrichment workflow
// against HubSpot company 9604614548 (Melbourne Racing Club, mrc.racing.com):
//
//   Apollo /v1/organizations/enrich -> { organization_revenue: 0.0,
//                                        organization_revenue_printed: null,
//                                        estimated_num_employees: 250 }
//   HubSpot's own record            -> annualrevenue 206,078,000
//   Chain emitted                   -> lv_revenue_band "<1M"
//
// `_revenueToDollars` short-circuits only on null/undefined/"", so a numeric 0 fell
// straight through to the `v < 1e6` branch. The ICP cost is asymmetric: "<1M" scores 0
// where the truthful "50-500M" scores +10 (config/icp_scoring.yaml base_score.revenue_band),
// so an absent figure reads to the scorer as a disqualifying one. Harmless only while
// canonical writes are disarmed.
//
// Run: node --test tests/n8n/zeroFirmographicSentinel.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { toCandidates, normalizeRevenueBand, normalizeEmployeeBand } =
  require(path.join(ROOT, "n8n/code/normalizeProviders.js"));

const NOW = "2026-07-31T00:00:00Z";
const find = (cands, field) => cands.filter((c) => c.field === field);

test("zero revenue is no-data, not <1M", () => {
  assert.equal(normalizeRevenueBand(0), null);
  assert.equal(normalizeRevenueBand(0.0), null);
  assert.equal(normalizeRevenueBand(-1), null);
  // ZoomInfo's thousands-to-dollars conversion collapses to 0 the same way.
  assert.equal(normalizeRevenueBand(0 * 1000), null);
});

test("real revenue figures still band exactly as before", () => {
  assert.equal(normalizeRevenueBand(1), "<1M");            // smallest non-zero, still <1M
  assert.equal(normalizeRevenueBand(206078000), "50-500M"); // the MRC truth from HubSpot
  assert.equal(normalizeRevenueBand(12000000), "5-50M");
  assert.equal(normalizeRevenueBand("$250 mil. - $500 mil."), "50-500M");
  assert.equal(normalizeRevenueBand(null), null);
  assert.equal(normalizeRevenueBand(""), null);
});

test("zero headcount is no-data, not 1-9", () => {
  assert.equal(normalizeEmployeeBand(0), null);
  assert.equal(normalizeEmployeeBand("0"), null);
  assert.equal(normalizeEmployeeBand(-5), null);
  assert.equal(normalizeEmployeeBand(1), "1-9");   // smallest real headcount unchanged
  assert.equal(normalizeEmployeeBand(250), "201-500");
});

test("the live Apollo MRC shape emits no revenue band, but keeps its real headcount", () => {
  // Verbatim field subset of the live 2026-07-31 organizations/enrich response.
  const apolloMrc = {
    organization: {
      name: "Racing.com",
      organization_revenue: 0.0,
      organization_revenue_printed: null,
      estimated_num_employees: 250,
      industry: "media production",
    },
  };
  const cands = toCandidates("apollo", apolloMrc, "companies", NOW);

  const revenue = find(cands, "lv_revenue_band");
  assert.deepEqual(revenue.map((c) => c.normalizedValue), [0].map(() => null),
    "a 0 revenue must never carry a band; it may only appear un-normalized");
  for (const c of revenue) {
    assert.equal(c.normalizedValue, null);
  }

  // The rest of the record is untouched — this guard is revenue/headcount only.
  assert.deepEqual(find(cands, "lv_employee_band").map((c) => c.normalizedValue), ["201-500"]);
  assert.deepEqual(find(cands, "industry").map((c) => c.normalizedValue), ["media production"]);
});
