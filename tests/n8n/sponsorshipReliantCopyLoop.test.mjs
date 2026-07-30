// tests/n8n/sponsorshipReliantCopyLoop.test.mjs
//
// Phase 18 Plan 02 (COPY-01) — compiled-node-body differential proving the sponsorship
// field reaches the companies merge call. Reuses tests/n8n/mergeCompanyStaleTimestamp.
// test.mjs's `runMergeCompany()` harness verbatim (the `new Function(...)` idiom over
// the repo's own committed jsCode — no external or untrusted input is ever interpolated
// into the function body).
//
// PRE body: tests/fixtures/merge_company_prefix_jscode.json's cloud "Merge Company"
// entry — a write-once red-evidence snapshot that predates BOTH the Phase 16.3 fix and
// this one. Read here, never regenerated (confirmed by direct inspection: its
// researchData field-name array holds exactly the pre-existing five entries, NOT
// lv_sponsorship_reliant — the string DOES appear elsewhere in that body, inlined as
// part of DEFAULT_COMPANY_POLICY, which is precisely why the field WOULD promote if it
// ever reached the merge call).
// POST body: read LIVE out of the committed n8n/wf_enrichment_cloud.json, so the
// assertion tracks what actually deploys.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const PRE_FIXTURE = JSON.parse(
  fs.readFileSync(path.join(ROOT, "tests/fixtures/merge_company_prefix_jscode.json"), "utf8")
).cloud["Merge Company"];

function loadPostBody() {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n/wf_enrichment_cloud.json"), "utf8"));
  const node = wf.nodes.find((n) => n.name === "Merge Company");
  return node.parameters.jsCode;
}

function runMergeCompany(jsCode, row) {
  const $input = { all: () => [{ json: row }], get item() { return { json: row }; } };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, row, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}

// Row fixture: identity_keys with a domain, an existingRecord with that domain, a name,
// and the sponsorship property explicitly blank; a non-null but empty scored object so
// the node does not take its merge-null skip branch and the firmographic lane
// contributes nothing; and a research_candidate carrying BOTH the sponsorship field (a
// boolean) and one already-copied research field (lv_content_type, a non-empty array)
// that promotes without an evidence gate (system_owned, 75 threshold, no
// require_evidence_url* entry).
function row(sponsorshipValue) {
  const data = { lv_content_type: ["live_broadcast"] };
  if (sponsorshipValue !== undefined) data.lv_sponsorship_reliant = sponsorshipValue;
  return {
    identity_keys: { domain: "exampleco.example" },
    existingRecord: {
      domain: "exampleco.example",
      name: "Example Co",
      lv_sponsorship_reliant: "",
    },
    scored: { best: {}, winners: {}, sourcesByField: {} },
    research_candidate: {
      matched: true,
      confidence: 90,
      data,
      evidence_by_field: {},
    },
  };
}

test("(a) VACUITY GUARD (PRE body): merge result is real and the control field promotes", () => {
  const out = runMergeCompany(PRE_FIXTURE, row(true));
  assert.ok(out.merge && typeof out.merge === "object", "merge is a real object, not the null skip branch");
  assert.equal(out.merge.canonicalPatch.lv_content_type[0], "live_broadcast",
    "control field must promote, proving the row/harness are wired correctly");
});

test("(b) RED (durable): the PRE body never produces an lv_sponsorship_reliant key or decision", () => {
  const out = runMergeCompany(PRE_FIXTURE, row(true));
  assert.ok(!("lv_sponsorship_reliant" in out.merge.canonicalPatch),
    "pre-fix wrapper never built lv_sponsorship_reliant into researchData");
  const decision = out.merge.decisions.find((d) => d.field === "lv_sponsorship_reliant");
  assert.ok(!decision, "no decision entry should exist pre-fix");
});

test("(c) GREEN (fails until the fix lands): the POST body promotes lv_sponsorship_reliant", () => {
  const out = runMergeCompany(loadPostBody(), row(true));
  assert.equal(out.merge.canonicalPatch.lv_sponsorship_reliant, true,
    "COPY-01: sponsorship value must reach lv_sponsorship_reliant in canonicalPatch");
  const decision = out.merge.decisions.find((d) => d.field === "lv_sponsorship_reliant");
  assert.ok(decision, "a decision entry must exist for the promoted field");
  assert.equal(decision.decision, "promote");
});

test("(d) EDGE D-COPY-empty: a null sponsorship value produces no key, control field still promotes", () => {
  const out = runMergeCompany(loadPostBody(), row(null));
  assert.ok(!("lv_sponsorship_reliant" in out.merge.canonicalPatch),
    "tri-state null must be skipped by the existing blank/tri-state guard");
  assert.equal(out.merge.canonicalPatch.lv_content_type[0], "live_broadcast",
    "control field must still promote");
});

test("(e) EDGE D-COPY-adjacency: an empty research candidate never contributes lv_sponsorship_reliant", () => {
  const emptyRow = row(true);
  emptyRow.research_candidate.data = {};
  const out = runMergeCompany(loadPostBody(), emptyRow);
  assert.ok(!("lv_sponsorship_reliant" in out.merge.canonicalPatch),
    "the sponsorship key can only ever come from the research fold, never the firmographic loop");
});
