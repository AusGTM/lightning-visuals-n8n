// Regression guard for the companies research→judge→merge ROW-RECOVERY fix.
//
// Bug (confirmed 2026-07-24, cross-AI review kimi-k3 BLOCKER-1): n8n HTTP nodes REPLACE
// $json with the response. The provider waterfall recovers the row via $('Company Gate'),
// but the research/judge chain's post-HTTP Code nodes (Validate Research Output, Apply Judge
// Verdict) originally spread {...it.json} — i.e. the HTTP response — losing existingRecord/
// scored. On the research-TRUE lane, Merge Company then saw no `scored` and returned
// merge:null, and Apply Judge Verdict threw on an undefined research_candidate. The rest of
// the offline suite never caught it because it exercises the JS functions in isolation, never
// the n8n item-flow across HTTP hops.
//
// This test simulates that item-flow over the ACTUAL emitted node jsCode (as n8n does at
// runtime), modelling each HTTP node as replacing the item json with a mock response, and
// asserts the row survives to Merge Company. It fails if the row-recovery is reverted.
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` — the same
// thing n8n's Code node does at runtime — over a fixed, in-repo list of node names. No
// external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const CHAIN = [
  { name: "Research Trigger Gate", http: false },
  { name: "Build Research Request", http: false },
  { name: "Claude Web Research", http: true },
  { name: "Validate Research Output", http: false },
  { name: "Judge Gate", http: false },
  { name: "Build Judge Request", http: false },
  { name: "Judge Call", http: true },
  { name: "Apply Judge Verdict", http: false },
  { name: "Merge Company", http: false },
];

function httpResponses() {
  return {
    "Claude Web Research": {
      id: "msg_1", type: "message", role: "assistant",
      content: [{ type: "text", text: JSON.stringify({
        lv_org_type: "content_producer", confidence: 88,
        evidence_by_field: { lv_org_type: { url: "https://exampleco.example/about" } },
      }) }], model: "claude", usage: { output_tokens: 50 },
    },
    "Judge Call": {
      id: "msg_2", type: "message", role: "assistant",
      content: [{ type: "text", text: JSON.stringify({
        decision: "promote", chosen_field: "lv_org_type", confidence: 90, reason: "evidence",
      }) }], model: "claude", usage: {},
    },
  };
}

function runChain(wfPath) {
  const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;

  const seedRow = {
    identity_keys: { domain: "exampleco.example" },
    existingRecord: { domain: "exampleco.example", name: "Example Co", lv_org_type: "" },
    scored: {
      best: { lv_org_type: { normalizedValue: "content_producer", source: "zoominfo", agreedBy: [] } },
      winners: { lv_org_type: "content_producer" }, sourcesByField: {},
    },
    gap_flag: true,
  };
  const outputs = {
    "Normalize + Score Company": [seedRow],
    "Company Gate": [seedRow],
    "Build Company Requests": [seedRow],
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

// Cloud is the deployable variant and bakes config flags as constants (no $vars/$env), so the
// emitted jsCode runs standalone here. The row-recovery fix lives in the SHARED
// ENRICH_VALIDATE_RESEARCH / ENRICH_APPLY_JUDGE_VERDICT constants — identical in the local-live
// variant — so exercising cloud fully guards the fix; local-live's only delta is $vars-based
// flag reads, which are unrelated to the HTTP-hop row loss.
for (const wf of ["n8n/wf_enrichment_cloud.json"]) {
  test(`research→judge→merge row survives HTTP hops (${wf})`, () => {
    const { trace, threw, final } = runChain(path.join(ROOT, wf));
    assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
    // The row (existingRecord + scored) must survive PAST both HTTP hops.
    assert.ok(trace["Validate Research Output"].scored, "Validate recovered scored (post Claude Web Research)");
    assert.ok(trace["Validate Research Output"].existingRecord, "Validate recovered existingRecord");
    assert.ok(trace["Apply Judge Verdict"].existingRecord, "Apply Judge Verdict recovered existingRecord (post Judge Call)");
    // The payoff: Merge Company produces a real merge, not the merge:null skip branch.
    assert.notEqual(final.merge, null, "Merge Company merge is not null on the research lane");
    assert.ok(final.merge && typeof final.merge === "object", "Merge Company produced a merge object");
  });
}
