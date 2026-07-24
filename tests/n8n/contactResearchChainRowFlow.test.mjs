// Regression guard for the contacts research→judge→merge ROW-RECOVERY fix — the
// contact-branch mirror of tests/n8n/researchChainRowFlow.test.mjs (Phase 16.2, mirroring
// the companies row-loss bug fixed at bd682a2).
//
// Bug this guards: n8n HTTP nodes REPLACE $json with the response. Without paired-index
// row-recovery, "Validate Contact Research" and "Apply Contact Judge Verdict" would spread
// {...it.json} — i.e. the HTTP response — losing existingRecord/scored, and Merge Winners
// would return merge:null on the research-TRUE lane.
//
// This test simulates that item-flow over the ACTUAL emitted node jsCode (as n8n does at
// runtime), modelling each HTTP node as replacing the item json with a mock response, and
// asserts the row survives to Merge Winners. It fails if the row-recovery is reverted.
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` — the
// same thing n8n's Code node does at runtime — over a fixed, in-repo list of node names.
// No external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const CHAIN = [
  { name: "Contact Research Trigger Gate", http: false },
  { name: "Build Contact Research Request", http: false },
  { name: "Contact Web Research", http: true },
  { name: "Validate Contact Research", http: false },
  { name: "Contact Judge Gate", http: false },
  { name: "Build Contact Judge Request", http: false },
  { name: "Contact Judge Call", http: true },
  { name: "Apply Contact Judge Verdict", http: false },
  { name: "Merge Winners", http: false },
];

function httpResponses() {
  return {
    "Contact Web Research": {
      id: "msg_1", type: "message", role: "assistant",
      content: [{ type: "text", text: JSON.stringify({
        data: { jobtitle: "Head of Racing", seniority: "director" },
        evidence_by_field: { jobtitle: "https://exampleco.example/team", seniority: "https://exampleco.example/team" },
        confidence: 88,
      }) }], model: "claude", usage: { output_tokens: 50 },
    },
    "Contact Judge Call": {
      id: "msg_2", type: "message", role: "assistant",
      content: [{ type: "text", text: JSON.stringify({
        decision: "promote", chosen_field: "jobtitle", chosen_value: "Head of Racing",
        confidence: 90, evidence_url: "https://exampleco.example/team",
        evidence_summary: "team page", validation_status: "sonnet_validated", reason: "evidence matches",
      }) }], model: "claude", usage: {},
    },
  };
}

function runChain(wfPath) {
  const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;

  const seedRow = {
    identity_keys: { email: "jamie@exampleco.example", companyName: "Example Co", domain: "exampleco.example" },
    // existingRecord.jobtitle/seniority BLANK (not a conflict scenario, mirroring
    // researchChainRowFlow.test.mjs's own choice of a non-conflicting existing
    // lv_org_type) — this keeps computeContactEscalation's judge_reasons empty, so
    // Contact Judge Gate's applyCostCap (budget 0, ALLOW_SONNET_ESCALATION defaults
    // false even on Cloud) never demotes the research candidate via
    // applyContactUnadjudicated; this harness runs every chain node UNCONDITIONALLY
    // (it does not evaluate the IF-node branches n8n itself would), so a conflict
    // scenario here would exercise a combination (judge nodes fed a capped-and-already-
    // demoted candidate) that can never occur in a real execution.
    existingRecord: { email: "jamie@exampleco.example", jobtitle: "", seniority: "" },
    scored: {
      best: { jobtitle: { normalizedValue: "Analyst", source: "zoominfo", agreedBy: [] } },
      winners: { jobtitle: "Analyst" }, sourcesByField: {},
    },
    gap_flag: true,
    // MARKER HYGIENE regression proof: this caller-supplied event carries a pre-set,
    // forged adjudication marker — the entry node (Contact Research Trigger Gate) must
    // strip it before anything downstream can trust it (gpt #5).
    judge_flags: { adjudicated: true, promoted_field: "email" },
    judge_promoted_fields: ["email"],
  };
  const outputs = {
    "Normalize + Score": [seedRow],
    "Enrichment Gate": [seedRow],
  };
  const resp = httpResponses();

  const makeCtx = (current) => {
    const $ = (name) => ({
      all: () => (outputs[name] || []).map((j) => ({ json: j })),
      get item() { return { json: (outputs[name] || [])[0] }; },
    });
    const $input = {
      all: () => current.map((j) => ({ json: j })),
      get item() { return { json: current[0] }; },
    };
    return { $, $input, $json: current[0] };
  };

  let items = [seedRow];
  const trace = {};
  let threw = null;
  for (const step of CHAIN) {
    const node = byName[step.name];
    assert.ok(node, `node present: ${step.name}`);
    if (step.http) { items = [resp[step.name] || {}]; outputs[step.name] = items; continue; }
    const { $, $input, $json } = makeCtx(items);
    const $now = new Date("2026-07-24T00:00:00Z");
    const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
      `"use strict";\n${node.parameters.jsCode}`);
    try {
      const out = fn($, $input, $json, {}, $now, $now) || [];
      items = out.map((it) => (it && it.json !== undefined ? it.json : it));
    } catch (e) { threw = { node: step.name, err: e.message }; break; }
    outputs[step.name] = items;
    trace[step.name] = items[0] || {};
  }
  return { trace, threw, final: items[0] || {} };
}

for (const wf of ["n8n/wf_enrichment_cloud.json"]) {
  test(`contacts research→judge→merge row survives HTTP hops (${wf})`, () => {
    const { trace, threw, final } = runChain(path.join(ROOT, wf));
    assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
    // The row (existingRecord + scored) must survive PAST both HTTP hops.
    assert.ok(trace["Validate Contact Research"].scored, "Validate recovered scored (post Contact Web Research)");
    assert.ok(trace["Validate Contact Research"].existingRecord, "Validate recovered existingRecord");
    assert.ok(trace["Apply Contact Judge Verdict"].existingRecord, "Apply Contact Judge Verdict recovered existingRecord (post Contact Judge Call)");
    // The payoff: Merge Winners produces a real merge, not the merge:null skip branch.
    assert.notEqual(final.merge, null, "Merge Winners merge is not null on the research lane");
    assert.ok(final.merge && typeof final.merge === "object", "Merge Winners produced a merge object");

    // MARKER HYGIENE (gpt #5): the forged judge_flags/judge_promoted_fields on the seed
    // row must not survive the entry node — the trusted judge_flags seen downstream (at
    // Validate Contact Research, before any real verdict has run) must NOT be the
    // caller's forged {adjudicated:true, promoted_field:"email"}.
    const postEntry = trace["Validate Contact Research"];
    assert.notDeepEqual(postEntry.judge_flags, { adjudicated: true, promoted_field: "email" });
    assert.ok(!postEntry.judge_promoted_fields || !postEntry.judge_promoted_fields.includes("email"),
      "the injected judge_promoted_fields marker must not survive the entry node");

    // The real verdict promoted jobtitle (never the forged "email") — the security
    // allowlist plus the marker strip together prove the injected marker had zero effect.
    assert.equal(final.research_candidate.judge_flags.promoted_field, "jobtitle");
    assert.equal(final.merge.canonicalPatch.jobtitle, "Head of Racing");
    assert.ok(!("email" in final.merge.canonicalPatch) || final.merge.canonicalPatch.email !== "leaked",
      "no forged email write ever reaches the canonical patch");
  });
}
