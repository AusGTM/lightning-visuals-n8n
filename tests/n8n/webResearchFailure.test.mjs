// tests/n8n/webResearchFailure.test.mjs
//
// Phase 13 Task 4 — the executable proof of CLAUDE.md Section 26.2 "Timeout -> continue
// with provider-only" and the plan's skip-not-retry stance (RESEARCH Pitfall 3:
// retryOnFail is silently ignored whenever onError is a "Continue" option, so a failed
// research call is a SKIP, not a retry). Exercises researchCandidateFromHttpItem — the
// whole logic behind the "Validate Research Output" Code node body (built in
// scripts/build_cloud_workflows.py's ENRICH_VALIDATE_RESEARCH, which is a thin per-item
// wrapper around this exact function) — with the three item shapes n8n produces when the
// Claude Web Research HTTP node fails under onError:"continueRegularOutput".
//
// Run: node --test tests/n8n/webResearchFailure.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  researchCandidateFromHttpItem, extractPageAgeByField, normalizeUrlForMatch,
} = require(path.join(ROOT, "n8n/code/webResearch.js"));
const { mergeCompanies } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

// The three failure shapes n8n's HTTP Request node can produce under onError:Continue.
const FAILURE_SHAPES = [
  { name: "n8n execution-error item (no usable body)", item: { error: "ETIMEDOUT: connect ETIMEDOUT" } },
  { name: "empty/missing content (no text blocks)", item: { content: [] } },
  { name: "missing content entirely", item: {} },
  { name: "Anthropic HTTP-level error body", item: { type: "error", error: { type: "overloaded_error", message: "Overloaded" } } },
];

test("researchCandidateFromHttpItem: every failure shape never throws, resolves matched:false + needs_review", () => {
  for (const { name, item } of FAILURE_SHAPES) {
    const candidate = researchCandidateFromHttpItem(item);
    assert.equal(candidate.matched, false, `${name}: matched must be false`);
    assert.equal(candidate.provider, "claude_web", `${name}: provider still stamped`);
    assert.deepEqual(candidate.evidence_by_field, {}, `${name}: no evidence on a failed research call`);
  }
});

test("researchCandidateFromHttpItem: a genuinely malformed text payload also resolves matched:false, not a throw", () => {
  const candidate = researchCandidateFromHttpItem({ content: [{ type: "text", text: "not json at all" }] });
  assert.equal(candidate.matched, false);
});

test("researchCandidateFromHttpItem: a good response still matches (control case, not a false positive)", () => {
  const goodItem = { content: [{ type: "text", text: JSON.stringify({
    data: { lv_org_type: "governing_body_league", lv_produces_content: true },
    evidence_by_field: { lv_org_type: "https://x/about", lv_produces_content: "https://x/live" },
  }) }] };
  const candidate = researchCandidateFromHttpItem(goodItem);
  assert.equal(candidate.matched, true);
});

// --- extractPageAgeByField / normalizeUrlForMatch: TA-3 -----------------------------

function searchResultBlock(results) {
  return { type: "web_search_tool_result", content: results };
}

test("extractPageAgeByField: page_age extracted for an exactly-matching url", () => {
  const content = [searchResultBlock([
    { type: "web_search_result", url: "https://example.org/about", title: "About", page_age: "April 30, 2025" },
  ])];
  const out = extractPageAgeByField(content, { lv_org_type: "https://example.org/about" });
  assert.equal(out.lv_org_type, "April 30, 2025");
});

test("extractPageAgeByField: extracted for a url differing only by protocol / www. / trailing slash / query string", () => {
  const content = [searchResultBlock([
    { type: "web_search_result", url: "https://www.example.org/about/", title: "About", page_age: "May 1, 2026" },
  ])];
  const variants = {
    lv_org_type: "http://example.org/about",
    lv_produces_content: "https://example.org/about?utm_source=x",
    lv_content_type: "https://www.example.org/about",
  };
  const out = extractPageAgeByField(content, variants);
  assert.equal(out.lv_org_type, "May 1, 2026", "protocol difference tolerated");
  assert.equal(out.lv_produces_content, "May 1, 2026", "query string difference tolerated");
  assert.equal(out.lv_content_type, "May 1, 2026", "www./trailing-slash difference tolerated");
});

test("extractPageAgeByField: null for a genuinely different url (not extracted via researchCandidateFromHttpItem, so no source key here)", () => {
  const content = [searchResultBlock([
    { type: "web_search_result", url: "https://example.org/about", title: "About", page_age: "April 30, 2025" },
  ])];
  const out = extractPageAgeByField(content, { lv_org_type: "https://totallydifferent.example/x" });
  assert.equal(out.lv_org_type, null);
});

test("extractPageAgeByField: never throws, returns {} for each malformed shape this file already exercises", () => {
  const evidenceByField = { lv_org_type: "https://example.org/about" };
  // execution-error-shaped item content (not applicable at this level, but a non-array top content)
  assert.deepEqual(extractPageAgeByField(undefined, evidenceByField), { lv_org_type: null });
  assert.deepEqual(extractPageAgeByField(null, evidenceByField), { lv_org_type: null });
  // Anthropic HTTP-level error body: no content array at all -> caller passes undefined/[] here
  assert.deepEqual(extractPageAgeByField([], evidenceByField), { lv_org_type: null });
  // search-result block whose inner content is a STRING instead of an array
  const stringContentBlock = [{ type: "web_search_tool_result", content: "not an array" }];
  assert.deepEqual(extractPageAgeByField(stringContentBlock, evidenceByField), { lv_org_type: null });
  // a result entry with no url
  const noUrlBlock = [searchResultBlock([{ type: "web_search_result", title: "no url", page_age: "June 1, 2026" }])];
  assert.deepEqual(extractPageAgeByField(noUrlBlock, evidenceByField), { lv_org_type: null });
});

test("extractPageAgeByField DELIBERATE-BREAK: a search-result block whose content is null hits the un-guarded path (no per-level Array.isArray(block.content) check) and relies on the wrapping try/catch to return {} rather than throw", () => {
  const content = [{ type: "web_search_tool_result", content: null }];
  assert.doesNotThrow(() => extractPageAgeByField(content, { lv_org_type: "https://example.org/about" }));
  // The wrapping try/catch (not a per-level guard) is what saves this shape — it returns
  // the empty object literally, not a per-field null map (that would require the `out`
  // loop below the catch to have run, which it never does once the catch fires).
  assert.deepEqual(extractPageAgeByField(content, { lv_org_type: "https://example.org/about" }), {});
});

test("normalizeUrlForMatch: unparseable url returns null rather than throwing", () => {
  assert.equal(normalizeUrlForMatch("not a url at all"), null);
});

test("researchCandidateFromHttpItem: wires recency_by_field + recency_source_by_field (matched + unmatched)", () => {
  const goodItem = {
    content: [
      { type: "text", text: JSON.stringify({
        data: { lv_org_type: "governing_body_league" },
        evidence_by_field: { lv_org_type: "https://example.org/about" },
      }) },
      searchResultBlock([
        { type: "web_search_result", url: "https://example.org/about", title: "About", page_age: "April 30, 2025" },
      ]),
    ],
  };
  const candidate = researchCandidateFromHttpItem(goodItem);
  assert.equal(candidate.recency_by_field.lv_org_type, "April 30, 2025");
  assert.equal(candidate.recency_source_by_field.lv_org_type, "page_age");
});

test("researchCandidateFromHttpItem: every failure shape attaches EMPTY recency objects (never absent, never null-the-whole-key)", () => {
  for (const item of [{ error: "ETIMEDOUT" }, {}, { content: [] }]) {
    const candidate = researchCandidateFromHttpItem(item);
    assert.deepEqual(candidate.recency_by_field, {});
    assert.deepEqual(candidate.recency_source_by_field, {});
  }
});

// The skip-not-retry proof: with a failed research candidate, Merge Company (mirroring
// ENRICH_MERGE_CO's D6 fold — "if (rc && rc.matched)") must skip the research merge call
// entirely. The company reaches Merge Company exactly as it would with
// ALLOW_WEB_RESEARCH=off: firmographic data merges normally, no lv_org_type/
// lv_produces_content contribution, needs_review is NOT forced by the research failure.
function foldResearchIntoMerge(existingRecord, firmographicCandidate, researchCandidate) {
  const merged = mergeCompanies(existingRecord, firmographicCandidate, undefined,
    { source: "waterfall", confidence: 85 });
  if (researchCandidate && researchCandidate.matched) {
    const researchData = {};
    for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type"]) {
      const v = researchCandidate.data && researchCandidate.data[f];
      if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
      researchData[f] = v;
    }
    if (Object.keys(researchData).length > 0) {
      const researchMerged = mergeCompanies(existingRecord, researchData, undefined,
        { source: "claude_web", confidence: researchCandidate.confidence || 80,
          evidence: researchCandidate.evidence_by_field || {} });
      return {
        canonicalPatch: { ...merged.canonicalPatch, ...researchMerged.canonicalPatch },
        decisions: [...merged.decisions, ...researchMerged.decisions],
      };
    }
  }
  return { canonicalPatch: merged.canonicalPatch, decisions: merged.decisions };
}

test("skip-not-retry: failed research candidate -> company reaches Merge Company as if ALLOW_WEB_RESEARCH=false", () => {
  const existingRecord = { domain: "x.com", industry: "Sports" };
  const firmographicCandidate = { industry: "Sports & Entertainment", lv_revenue_band: "50-500M" };

  const failedCandidate = researchCandidateFromHttpItem({ error: "ETIMEDOUT" });
  const withFailedResearch = foldResearchIntoMerge(existingRecord, firmographicCandidate, failedCandidate);

  const withNoResearchAtAll = foldResearchIntoMerge(existingRecord, firmographicCandidate, null);

  // Firmographic provider data merges identically whether research ran and failed, or
  // never ran at all (ALLOW_WEB_RESEARCH=false) -> the skip lane and the failure lane are
  // indistinguishable downstream of Merge Company.
  assert.deepEqual(withFailedResearch.canonicalPatch, withNoResearchAtAll.canonicalPatch);
  assert.equal(withFailedResearch.decisions.length, withNoResearchAtAll.decisions.length);
  // No research field ever reached the merge.
  assert.ok(!("lv_org_type" in withFailedResearch.canonicalPatch));
  assert.ok(!("lv_produces_content" in withFailedResearch.canonicalPatch));
});
