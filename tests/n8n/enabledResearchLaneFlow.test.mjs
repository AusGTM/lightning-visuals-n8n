// Phase 16.5 Task 3 — the offline oracle for Plan 02/03's live runs.
//
// Plan 02/03 spend real Anthropic dollars firing the research->judge lane live, against
// a build with ALLOW_WEB_RESEARCH/ALLOW_SONNET_ESCALATION enabled. This file drives the
// EXACT node bodies that build will ship — the committed wf_enrichment_cloud.json with
// the same two exact-literal replacements the Python deploy-time overlay
// (scripts/deploy_n8n_workflows.py::enable_baked_flags) performs — through both the
// contacts and companies research-then-judge lanes, from a raw bare-event webhook body,
// asserting the research gate fires, the judge escalates, and the row survives BOTH HTTP
// hops to a non-null merge. So Plan 02/03's live runs CONFIRM a prediction instead of
// discovering one.
//
// This is a SECOND, independent implementation of the enabling rewrite (deliberately —
// see (1) below): if the Python overlay's literal ever drifts from what this file
// assumes, tests/test_enabled_build_invariants.py's parity/diff assertions catch the
// Python side, and this file's own non-zero-replacement assertion catches the JS side.
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` — the
// same thing n8n's Code node does at runtime — over a fixed, in-repo list of node names.
// No external or untrusted input is ever interpolated into the function body. Ports
// tests/n8n/bareEventChainFlow.test.mjs's runner unchanged except for accepting a
// workflow OBJECT (so the enabled in-memory dict can be driven directly) rather than a
// path — this repo already keeps a per-file copy of this harness (bareEventChainFlow,
// researchChainRowFlow, contactResearchChainRowFlow); this is the fourth, by convention.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

// --- (1) THE ENABLED WORKFLOW: the same two exact-literal replacements the Python
// overlay performs (enable_baked_flags), independently reimplemented here. ---------------
const OVERLAY_FLAGS = ["ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"];

function enableBakedFlagsJs(rawText, flags) {
  let text = rawText;
  let totalReplacements = 0;
  for (const flag of flags) {
    const disabled = `const ${flag} = false;`;
    const enabled = `const ${flag} = true;`;
    const count = text.split(disabled).length - 1;
    totalReplacements += count;
    text = text.split(disabled).join(enabled);
  }
  return { text, totalReplacements };
}

function loadEnabledWorkflow() {
  const rawText = fs.readFileSync(WF_PATH, "utf8");
  const { text, totalReplacements } = enableBakedFlagsJs(rawText, OVERLAY_FLAGS);
  // Assert the replacement actually changed something BEFORE running anything — a
  // silent no-op here would make every downstream assertion meaningless.
  assert.ok(totalReplacements > 0, "in-test literal replacement changed zero sites");
  return JSON.parse(text);
}

// --- runner, ported from bareEventChainFlow.test.mjs unchanged except: takes a workflow
// OBJECT rather than a path. -------------------------------------------------------------
function runChain(wf, chainSpec, seedBody, httpMocks) {
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;

  const outputs = {};

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

  let items = [{ body: seedBody }];
  const trace = {};
  let threw = null;
  for (const step of chainSpec) {
    const node = byName[step.name];
    assert.ok(node, `node present in built workflow: ${step.name}`);
    if (step.http) {
      items = [httpMocks[step.name] || {}];
      outputs[step.name] = items;
      continue;
    }
    const { $, $input, $json } = makeCtx(items);
    const $now = new Date("2026-07-28T00:00:00Z");
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

// =========================================================================================
// (2) THE CONTACTS LANE
// =========================================================================================

// The TRUE live webhook shape: a bare HubSpot event ARRAY (contact 201, the real
// hs_object_id verified live against portal 22617666 — STATE.md's Track B checkpoint),
// no envelope, no top-level `providers` key. A plain array resolves to ZERO providers
// enabled by design (CONTEXT Locked Decision 2) — exactly what makes the research gate
// reachable through the provider_gap branch: with all three providers enabled the
// waterfall would supply both jobtitle and seniority winners and provider_gap would never
// fire. This is why Plan 02 fires a zero-provider run rather than the all-provider run
// that passed canary step 3.
const CONTACT_SEED_BODY = [{
  objectId: 201, objectType: "contact",
  subscriptionType: "contact.propertyChange",
  propertyName: "lv_enrichment_requested",
  occurredAt: 1783316400000,
}];

const CONTACT_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Identity", http: false },
  { name: "HubSpot Fetch By Id", http: true },
  { name: "Adapt Fetch By Id", http: false },
  { name: "Enrichment Gate", http: false },
  { name: "Normalize + Score", http: false },
  { name: "Contact Research Trigger Gate", http: false },
  { name: "Build Contact Research Request", http: false },
  { name: "Contact Web Research", http: true },
  { name: "Validate Contact Research", http: false },
  { name: "Contact Judge Gate", http: false },
  { name: "Build Contact Judge Request", http: false },
  { name: "Contact Judge Call", http: true },
  { name: "Apply Contact Judge Verdict", http: false },
  { name: "Merge Winners", http: false },
  { name: "Decide Action", http: false },
];

// Record shape as observed live for contact 201: email/firstname/lastname/jobtitle/
// mobilephone present, real hs_object_id, BOTH cache-key datetimes null (verified null in
// the portal today), and NO seniority — the provider_gap branch on seniority (jobtitle IS
// present so it cannot provider_gap; seniority is absent from both existingRecord AND
// provider winners since zero providers ran) is what fires needsResearch.
const CONTACT_HTTP_MOCKS = {
  "HubSpot Fetch By Id": {
    results: [{
      id: "201",
      properties: {
        email: "riley.chen@exampleracing.example",
        firstname: "Riley",
        lastname: "Chen",
        jobtitle: "Product Manager", // the ZoomInfo/Apollo-agreed live value (STATE.md)
        mobilephone: "+61400000000",
        lv_jobtitle_verified_at: null,
        lv_mobilephone_verified_at: null,
        // seniority deliberately absent.
      },
    }],
    total: 1,
  },
  // A jobtitle DIFFERENT from the existing record's ("Product Manager") — the live
  // Lusha-vs-Apollo/ZoomInfo disagreement STATE.md surfaced ("Chief Executive Officer" vs
  // "Product Manager") — fires jobtitle_conflict in computeContactEscalation. Both fields
  // carry a parseable https evidence URL so validateContactResearch keeps both values.
  "Contact Web Research": {
    id: "msg_1", type: "message", role: "assistant",
    content: [{
      type: "text",
      text: JSON.stringify({
        data: { jobtitle: "Chief Executive Officer", seniority: "director" },
        evidence_by_field: {
          jobtitle: "https://exampleracing.example/about/leadership",
          seniority: "https://exampleracing.example/about/leadership",
        },
        confidence: 88,
      }),
    }],
    model: "claude", usage: { output_tokens: 50 },
  },
  "Contact Judge Call": {
    id: "msg_2", type: "message", role: "assistant",
    content: [{
      type: "text",
      text: JSON.stringify({
        decision: "promote", chosen_field: "jobtitle", chosen_value: "Chief Executive Officer",
        confidence: 90, evidence_url: "https://exampleracing.example/about/leadership",
        evidence_summary: "leadership page names the CEO", validation_status: "sonnet_validated",
        reason: "cited leadership page corroborates the researched title",
      }),
    }],
    model: "claude", usage: {},
  },
};

test("contacts: enabled build fires the research gate, escalates the judge, and the row survives both HTTP hops to a non-null merge", () => {
  const enabledWf = loadEnabledWorkflow();
  const { trace, threw, final } = runChain(enabledWf, CONTACT_CHAIN, CONTACT_SEED_BODY, CONTACT_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);

  // (b) payoff assertion, impossible with the flag disabled.
  const gate = trace["Contact Research Trigger Gate"];
  assert.equal(gate.research_needed, true);
  assert.equal(gate.research_skip_reason, undefined);

  // (c) the row survives the FIRST HTTP hop (Contact Web Research) — the contacts mirror
  // of the bd682a2 property.
  const validated = trace["Validate Contact Research"];
  assert.ok(validated.existingRecord, "existingRecord survived the first HTTP hop");
  assert.ok(validated.scored, "scored survived the first HTTP hop");
  assert.ok(validated.identity_keys, "identity_keys survived the first HTTP hop");
  assert.ok(validated.object_id, "object_id survived the first HTTP hop");

  // (d) escalation is genuinely exercised, not merely enabled.
  const judgeGate = trace["Contact Judge Gate"];
  assert.equal(judgeGate.needs_judge, true);
  assert.ok(Array.isArray(judgeGate.judge_reasons) && judgeGate.judge_reasons.length > 0);
  assert.ok(judgeGate.judge_reasons.includes("jobtitle_conflict"),
    `expected jobtitle_conflict among judge_reasons, got: ${JSON.stringify(judgeGate.judge_reasons)}`);

  // (e) the row survives the SECOND HTTP hop (Contact Judge Call).
  const applied = trace["Apply Contact Judge Verdict"];
  assert.ok(applied.existingRecord, "existingRecord survived the second HTTP hop");
  assert.ok(applied.scored, "scored survived the second HTTP hop");

  // (f) the payoff: Merge Winners produces a real merge, not the merge:null skip branch —
  // exactly the symptom bd682a2 fixed, in its contacts mirror.
  const mergeOutput = trace["Merge Winners"];
  assert.notEqual(mergeOutput.merge, null, "Merge Winners merge is not null on the research lane");
  assert.ok(mergeOutput.merge && typeof mergeOutput.merge === "object");

  // (g) write safety is not relaxed by enablement — Decide Action still reports the
  // write-blocked outcome, and its target id is the fetched record id.
  assert.equal(final.action, "write_blocked");
  assert.equal(final.hs_object_id, "201");
});

// =========================================================================================
// (3) THE COMPANIES LANE — the literal bd682a2 chain, and the one Plan 03 exercises live.
// =========================================================================================

// The real Melbourne Racing Club object id, verified live against portal 22617666
// (STATE.md's Track B checkpoint): hs_object_id 9604614548, domain mrc.racing.com.
const COMPANY_SEED_BODY = [{
  objectId: 9604614548, objectType: "company",
  subscriptionType: "company.propertyChange",
  propertyName: "lv_enrichment_requested",
  occurredAt: 1783316400000,
}];

const COMPANY_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Company Identity", http: false },
  { name: "HubSpot Company Fetch By Id", http: true },
  { name: "Adapt Company Fetch By Id", http: false },
  { name: "Company Gate", http: false },
  { name: "Build Company Requests", http: false },
  { name: "Normalize + Score Company", http: false },
  { name: "Research Trigger Gate", http: false },
  { name: "Build Research Request", http: false },
  { name: "Claude Web Research", http: true },
  { name: "Validate Research Output", http: false },
  { name: "Judge Gate", http: false },
  { name: "Build Judge Request", http: false },
  { name: "Judge Call", http: true },
  { name: "Apply Judge Verdict", http: false },
  { name: "Merge Company", http: false },
  { name: "Decide Company Action", http: false },
];

const COMPANY_HTTP_MOCKS = {
  // lv_org_type/lv_produces_content deliberately BLANK — this is what makes the RT-3
  // predicate fire (orgUnresolved || contentBlank).
  "HubSpot Company Fetch By Id": {
    results: [{
      id: "9604614548",
      properties: { name: "Melbourne Racing Club", domain: "mrc.racing.com" },
    }],
    total: 1,
  },
  // org-type and produces-content signals with per-field evidence URLs. existingRecord's
  // lv_org_type is blank so org_type_conflict cannot fire (computeEscalation requires an
  // existing KNOWN org type to compare against) — the escalation trigger this fixture
  // uses is produces_content_false, which fires unconditionally on an evidenced `false`
  // claim (applyEvidenceSufficiency is a no-op for anything other than a `true` claim,
  // judge.js:47), so the judge gate escalates for real.
  "Claude Web Research": {
    id: "msg_1", type: "message", role: "assistant",
    content: [{
      type: "text",
      text: JSON.stringify({
        data: {
          lv_org_type: "governing_body_league",
          lv_produces_content: false,
        },
        confidence: 85,
        evidence_by_field: {
          lv_org_type: "https://mrc.racing.com/about",
          lv_produces_content: "https://mrc.racing.com/broadcast",
        },
      }),
    }],
    model: "claude", usage: { output_tokens: 50 },
  },
  "Judge Call": {
    id: "msg_2", type: "message", role: "assistant",
    content: [{
      type: "text",
      text: JSON.stringify({
        decision: "promote", chosen_field: "lv_produces_content", chosen_value: false,
        confidence: 90, evidence_url: "https://mrc.racing.com/broadcast",
        evidence_summary: "broadcast page shows no content output", validation_status: "sonnet_validated",
        reason: "cited broadcast page corroborates no content output",
      }),
    }],
    model: "claude", usage: {},
  },
};

test("companies: enabled build fires the research gate, escalates the judge, and the row survives both HTTP hops to a non-null merge (bd682a2 chain)", () => {
  const enabledWf = loadEnabledWorkflow();
  const { trace, threw, final } = runChain(enabledWf, COMPANY_CHAIN, COMPANY_SEED_BODY, COMPANY_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);

  const gate = trace["Research Trigger Gate"];
  assert.equal(gate.research_needed, true);
  assert.equal(gate.research_skip_reason, undefined);

  // row survives the FIRST HTTP hop — the literal bd682a2 checkpoint.
  const validated = trace["Validate Research Output"];
  assert.ok(validated.existingRecord, "existingRecord survived the first HTTP hop");
  assert.ok(validated.scored, "scored survived the first HTTP hop");

  const judgeGate = trace["Judge Gate"];
  assert.equal(judgeGate.needs_judge, true);
  assert.ok(Array.isArray(judgeGate.judge_reasons) && judgeGate.judge_reasons.length > 0);
  assert.ok(judgeGate.judge_reasons.includes("produces_content_false"),
    `expected produces_content_false among judge_reasons, got: ${JSON.stringify(judgeGate.judge_reasons)}`);

  // row survives the SECOND HTTP hop.
  const applied = trace["Apply Judge Verdict"];
  assert.ok(applied.existingRecord, "existingRecord survived the second HTTP hop");
  assert.ok(applied.scored, "scored survived the second HTTP hop");

  // the bd682a2 assertion proper: Merge Company produces a real merge, not merge:null.
  const mergeOutput = trace["Merge Company"];
  assert.notEqual(mergeOutput.merge, null, "Merge Company merge is not null on the research lane");
  assert.ok(mergeOutput.merge && typeof mergeOutput.merge === "object");

  assert.equal(final.action, "write_blocked");
  assert.equal(final.hs_object_id, "9604614548");
});

// =========================================================================================
// (4) THE DISABLED CONTROL — proves the overlay, not something incidental, is the cause.
// =========================================================================================

test("contacts disabled control: the SAME chain over the UNMODIFIED committed workflow never fires the research gate", () => {
  const committedWf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const { trace, threw } = runChain(committedWf, CONTACT_CHAIN, CONTACT_SEED_BODY, CONTACT_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const gate = trace["Contact Research Trigger Gate"];
  assert.equal(gate.research_needed, false);
  assert.equal(gate.research_skip_reason, "ALLOW_WEB_RESEARCH=false");
});
