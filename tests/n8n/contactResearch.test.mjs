// tests/n8n/contactResearch.test.mjs
//
// Phase 16.2 Task 1 — contactResearch.js: never-throws HTTP-item handling (mirrors
// webResearchFailure.test.mjs's failure-shape table) + validateContactResearch's
// trim/evidence-URL gating (gpt #10 — presence of a citation string alone is
// insufficient; only a parseable https: URL keeps a value).
//
// Run: node --test tests/n8n/contactResearch.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { validateContactResearch, contactResearchCandidateFromHttpItem, CONTACT_RESEARCH_FIELDS } =
  require(path.join(ROOT, "n8n/code/contactResearch.js"));

// --- contactResearchCandidateFromHttpItem: never-throws (mirrors webResearchFailure) ---

const FAILURE_SHAPES = [
  { name: "n8n execution-error item (no usable body)", item: { error: "ETIMEDOUT: connect ETIMEDOUT" } },
  { name: "empty/missing content (no text blocks)", item: { content: [] } },
  { name: "missing content entirely", item: {} },
  { name: "Anthropic HTTP-level error body", item: { type: "error", error: { type: "overloaded_error", message: "Overloaded" } } },
];

test("contactResearchCandidateFromHttpItem: every failure shape never throws, resolves matched:false", () => {
  for (const { name, item } of FAILURE_SHAPES) {
    const candidate = contactResearchCandidateFromHttpItem(item);
    assert.equal(candidate.matched, false, `${name}: matched must be false`);
    assert.deepEqual(candidate.data, {}, `${name}: no data on a failed research call`);
    assert.deepEqual(candidate.evidence_by_field, {}, `${name}: no evidence on a failed research call`);
  }
});

test("contactResearchCandidateFromHttpItem: a genuinely malformed text payload also resolves matched:false, not a throw", () => {
  const candidate = contactResearchCandidateFromHttpItem({ content: [{ type: "text", text: "not json at all" }] });
  assert.equal(candidate.matched, false);
});

test("contactResearchCandidateFromHttpItem: a good response with sufficient evidence matches (control case)", () => {
  const goodItem = { content: [{ type: "text", text: JSON.stringify({
    data: { jobtitle: "Head of Racing", seniority: "director" },
    evidence_by_field: { jobtitle: "https://exampleco.example/team", seniority: "https://exampleco.example/team" },
    confidence: 88,
  }) }] };
  const candidate = contactResearchCandidateFromHttpItem(goodItem);
  assert.equal(candidate.matched, true);
  assert.equal(candidate.data.jobtitle, "Head of Racing");
  assert.equal(candidate.data.seniority, "director");
  assert.equal(candidate.confidence, 88);
  assert.equal(candidate.evidence_by_field.jobtitle, "https://exampleco.example/team");
});

// --- validateContactResearch: trim + non-dict + evidence-URL gating (gpt #10) ----------

test("validateContactResearch: trims whitespace-padded jobtitle/seniority", () => {
  const result = validateContactResearch({
    data: { jobtitle: "  Head of Racing  ", seniority: " director " },
    evidence_by_field: { jobtitle: "https://x/team", seniority: "https://x/team" },
  });
  assert.equal(result.data.jobtitle, "Head of Racing");
  assert.equal(result.data.seniority, "director");
});

test("validateContactResearch: missing/non-string field values coerce to null", () => {
  const result = validateContactResearch({ data: { jobtitle: 123, seniority: undefined } });
  assert.equal(result.data.jobtitle, null);
  assert.equal(result.data.seniority, null);
});

test("validateContactResearch: non-dict raw input -> matched:false (OC-4 mirror)", () => {
  for (const bad of [null, "a string", 42, ["array"]]) {
    const result = validateContactResearch(bad);
    assert.equal(result.matched, false, `${JSON.stringify(bad)} must yield matched:false`);
    assert.deepEqual(result.data, {});
  }
});

test("validateContactResearch: matched defaults true unless explicitly false", () => {
  const withoutMatched = validateContactResearch({ data: {} });
  assert.equal(withoutMatched.matched, true);
  const explicitFalse = validateContactResearch({ data: {}, matched: false });
  assert.equal(explicitFalse.matched, false);
});

test("EVIDENCE URL (gpt #10): jobtitle with a valid https: evidence URL promotes", () => {
  const result = validateContactResearch({
    data: { jobtitle: "Head of Racing" },
    evidence_by_field: { jobtitle: "https://exampleco.example/team" },
  });
  assert.equal(result.data.jobtitle, "Head of Racing");
  assert.equal(result.evidence_by_field.jobtitle, "https://exampleco.example/team");
});

test("EVIDENCE URL (gpt #10): a javascript: URL demotes to null", () => {
  const result = validateContactResearch({
    data: { jobtitle: "Head of Racing" },
    evidence_by_field: { jobtitle: "javascript:alert(1)" },
  });
  assert.equal(result.data.jobtitle, null);
  assert.ok(!("jobtitle" in result.evidence_by_field), "evidence key dropped on demotion");
});

test("EVIDENCE URL (gpt #10): an empty-string evidence URL demotes to null", () => {
  const result = validateContactResearch({
    data: { jobtitle: "Head of Racing" },
    evidence_by_field: { jobtitle: "" },
  });
  assert.equal(result.data.jobtitle, null);
});

test("EVIDENCE URL (gpt #10): an unparseable evidence URL demotes to null", () => {
  const result = validateContactResearch({
    data: { jobtitle: "Head of Racing" },
    evidence_by_field: { jobtitle: "not a url" },
  });
  assert.equal(result.data.jobtitle, null);
});

test("EVIDENCE URL (gpt #10): a missing evidence_by_field entry demotes to null", () => {
  const result = validateContactResearch({ data: { jobtitle: "Head of Racing" }, evidence_by_field: {} });
  assert.equal(result.data.jobtitle, null);
});

test("EVIDENCE URL (gpt #10): a non-https (plain http) URL also demotes to null", () => {
  const result = validateContactResearch({
    data: { jobtitle: "Head of Racing" },
    evidence_by_field: { jobtitle: "http://exampleco.example/team" },
  });
  assert.equal(result.data.jobtitle, null);
});

test("evidence gating applies independently per field (jobtitle demoted, seniority kept)", () => {
  const result = validateContactResearch({
    data: { jobtitle: "Head of Racing", seniority: "director" },
    evidence_by_field: { jobtitle: "javascript:alert(1)", seniority: "https://exampleco.example/team" },
  });
  assert.equal(result.data.jobtitle, null);
  assert.equal(result.data.seniority, "director");
  assert.ok(!("jobtitle" in result.evidence_by_field));
  assert.equal(result.evidence_by_field.seniority, "https://exampleco.example/team");
});

test("CONTACT_RESEARCH_FIELDS is exactly jobtitle/seniority (no PII field)", () => {
  assert.deepEqual(CONTACT_RESEARCH_FIELDS, ["jobtitle", "seniority"]);
});
