// tests/n8n/outcomeContractFlow.test.mjs
//
// Phase 61 Plan 04 Task 1 (REVIEW-05). Provider agreement (scoreEnrichment.js's
// `agreedBy`), material conflicts (providerConflict.js's groups) and the judge's own
// per-field verdict (`judge_confidence_by_field`) are all computed somewhere INSIDE
// n8n, while the plugin's `classify_matches` only ever saw match-oriented response
// data. `Build Response` already spreads the whole row across every terminal — this
// file drives a row through the REAL committed jsCode (both `Decide Action`, the
// per-terminal shaper, and `Build Response`, the one convergence point every terminal
// feeds) and asserts the five named signals + version survive to the client, mirroring
// linkedinLaneFlow.test.mjs's "evaluate the repo's OWN built jsCode via `new Function`"
// idiom rather than a hand-built payload.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};

function runDecideAction(rows) {
  const $input = { all: () => rows.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${node("Decide Action").parameters.jsCode}`);
  return fn($input).map((it) => (it && it.json !== undefined ? it.json : it));
}

function runBuildResponse(items, extraOutputs) {
  const outputs = {
    "Parse HubSpot Event": [{ json: { providers_requested: [] } }],
    ...(extraOutputs || {}),
  };
  const $ = (name) => {
    if (!(name in outputs)) throw new Error(`no node named ${name}`);
    const rows = outputs[name];
    return { all: () => rows, first: () => rows[0] };
  };
  const $input = { all: () => items.map((j) => ({ json: j })) };
  const fn = new Function("$", "$input", `"use strict";\n${node("Build Response").parameters.jsCode}`);
  return fn($, $input).map((it) => (it && it.json !== undefined ? it.json : it));
}

test("Decide Action + Build Response stamp outcome_contract_version and all five named signals, real jsCode end to end", () => {
  const row = {
    row_id: "row-1", object_type: "contacts", mode: "propose", action: "proposed",
    match: {
      tier: "medium", auto: false, reason: "candidate(s) found by name+company, unverified",
      candidates: [{ hs_object_id: "1" }, { hs_object_id: "2" }],
    },
    scored: { best: { jobtitle: { agreedBy: ["apollo"] } } },
    judge_confidence_by_field: { jobtitle: 88 },
  };

  const [decided] = runDecideAction([row]);
  const [built] = runBuildResponse([decided]);

  assert.equal(built.outcome_contract_version, 1);
  assert.equal(built.match.tier, "medium");
  assert.equal(built.candidate_count, 2, "the true medium-tier candidate cardinality, not re-derived client-side (REVIEW-C9)");
  assert.deepEqual(built.provider_agreement, { jobtitle: ["apollo"] });
  assert.deepEqual(built.judge_adjudicated_fields, { jobtitle: 88 });
  assert.equal(built.material_conflicts, null, "contacts compute no conflict groups today — explicit absence, not a dropped key");
});

test("a row with no enrichment signals carries them as explicit null, never a missing key", () => {
  const row = {
    row_id: "row-2", object_type: "contacts", mode: "propose", action: "proposed",
    match: { tier: "none", auto: false, reason: "searched, no hit", candidates: [] },
  };

  const [decided] = runDecideAction([row]);
  const [built] = runBuildResponse([decided]);

  assert.equal(built.outcome_contract_version, 1);
  assert.equal(built.candidate_count, 0);
  assert.ok("provider_agreement" in built, "the key itself must be present, even when its value is null");
  assert.equal(built.provider_agreement, null);
  assert.ok("material_conflicts" in built);
  assert.equal(built.material_conflicts, null);
  assert.ok("judge_adjudicated_fields" in built);
  assert.equal(built.judge_adjudicated_fields, null);
});

test("Build Response stamps the contract even on the Skip terminal, which bypasses Decide Action entirely", () => {
  const row = {
    row_id: "row-3", object_type: "contacts", action: "skip",
    match: { tier: "high", auto: true, reason: "matched by email", candidates: [] },
  };

  const [built] = runBuildResponse([row]);

  assert.equal(built.outcome_contract_version, 1);
  assert.equal(built.match.tier, "high");
  assert.equal(built.candidate_count, 0, "high tier's own candidates array is deliberately emptied — count is meaningful for medium tier only");
});
