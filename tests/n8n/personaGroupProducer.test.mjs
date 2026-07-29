// tests/n8n/personaGroupProducer.test.mjs
//
// GAP 2 (COPY-02, 18-VERIFICATION.md) — no provider mapper in
// n8n/code/normalizeProviders.js ever emitted a persona_group candidate, so Plan 18-02's
// correctly-wired copy step (tests/n8n/personaGroupCopyLoop.test.mjs) had nothing to
// copy in any live run. This test proves the missing producer from two angles: Layer 1
// requires normalizeProviders.js directly (same idiom as tests/n8n/enrichment.test.mjs)
// and asserts mapper output over RECORDED fixtures; Layer 2 drives a RECORDED provider
// response through the COMPILED "Normalize + Score" then "Merge Winners" node bodies
// read out of the committed n8n/wf_enrichment_cloud.json (harness copied verbatim from
// tests/n8n/writePatchBodyFlow.test.mjs / tests/n8n/personaGroupCopyLoop.test.mjs — the
// `new Function(...)` idiom over the repo's own build artifact; no external or untrusted
// input is ever interpolated into the function body).
//
// Discipline: the persona value must reach Merge Winners ONLY by having been produced
// upstream by Normalize + Score — this file never writes onto scored.winners directly.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");
const FIX = path.join(ROOT, "tests/fixtures/enrichment");

const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));

const load = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name), "utf8"));
const apolloContact = load("apollo_contact.json");       // departments: ["media_and_communication"]
const lushaLivePerson = load("lusha_live_person.json");  // jobTitle.departments: ["Other"] (non-signal)
const apolloLiveMatch = load("apollo_live_match.json");  // no departments field at all
const lushaLiveV2 = load("lusha_live_person_v2.json");   // no jobTitle key at all

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
  const $now = new Date("2026-07-29T00:00:00Z");
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, items[0], {}, $now, $now) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// ---------------------------------------------------------------------------
// Layer 1: mapper-level proof over recorded fixtures.
// ---------------------------------------------------------------------------

test("(a) VACUITY GUARD: Apollo contacts candidates over the recorded fixture still contain jobtitle/seniority unchanged", () => {
  const c = toCandidates("apollo", apolloContact, "contacts");
  const jobtitle = find(c, "jobtitle", "apollo");
  const seniority = find(c, "seniority", "apollo");
  assert.ok(jobtitle, "jobtitle candidate still present");
  assert.equal(jobtitle.accuracy, 0.6);
  assert.ok(seniority, "seniority candidate still present");
  assert.equal(seniority.accuracy, 0.6);
});

test("(b) GREEN (RED until the fix lands): Apollo contacts candidates include a persona candidate carrying the recorded department string", () => {
  const c = toCandidates("apollo", apolloContact, "contacts");
  const persona = find(c, "persona_group", "apollo");
  assert.ok(persona, "COPY-02: Apollo mapper must emit a persona_group candidate");
  assert.equal(persona.value, "media_and_communication");
});

test("(c) GREEN (RED until the fix lands, then asserts absence permanently): Lusha's live 'Other' department label produces NO persona candidate, jobtitle/seniority still present", () => {
  const c = toCandidates("lusha", lushaLivePerson, "contacts");
  assert.ok(find(c, "jobtitle", "lusha"), "jobtitle candidate still present");
  assert.ok(find(c, "seniority", "lusha"), "seniority candidate still present");
  assert.ok(!find(c, "persona_group", "lusha"),
    "D-GAP2-othervalue: a semantically-empty 'Other' label is a non-signal, not a harness failure");
});

test("(d) EDGE: recorded shapes with no department field at all emit no persona candidate and do not throw", () => {
  assert.doesNotThrow(() => toCandidates("apollo", apolloLiveMatch, "contacts"));
  assert.ok(!find(toCandidates("apollo", apolloLiveMatch, "contacts"), "persona_group", "apollo"));
  assert.doesNotThrow(() => toCandidates("lusha", lushaLiveV2, "contacts"));
  assert.ok(!find(toCandidates("lusha", lushaLiveV2, "contacts"), "persona_group", "lusha"));
});

// ---------------------------------------------------------------------------
// Layer 2: row-flow proof — compiled Normalize + Score, then compiled Merge Winners,
// chained through the OUTPUT row Normalize + Score actually produces.
// ---------------------------------------------------------------------------

function seedRow(providers) {
  return {
    action: "enrich",
    object_type: "contacts",
    identity_keys: { domain: null },
    existingRecord: {
      hs_object_id: "201",
      email: "brendan@lightningvisuals.com",
      phone: "+61399999999",
      jobtitle: "",
      seniority: "",
      lv_persona_group: "",
    },
    providers,
  };
}

test("(e) GREEN (RED until the fix lands): the compiled Normalize + Score body, given the recorded Apollo response, yields a non-null persona entry in scored.winners", () => {
  const nodes = loadWorkflow();
  const row = seedRow({ apollo: apolloContact, lusha: null, zoominfo: null });
  const out = runJsCode(nodes["Normalize + Score"].parameters.jsCode, [row]);
  assert.ok(out[0].scored, "Normalize + Score produced a real scored object, not the null skip branch");
  assert.equal(out[0].scored.winners.persona_group, "media_and_communication",
    "COPY-02: the recorded Apollo department must win the waterfall for persona_group");
});

test("(f) GREEN (RED until the fix lands): feeding that produced row into the compiled Merge Winners body yields lv_persona_group in canonicalPatch, with every other promoted field unchanged", () => {
  const nodes = loadWorkflow();
  const row = seedRow({ apollo: apolloContact, lusha: null, zoominfo: null });

  // The row that reaches Merge Winners comes ONLY from Normalize + Score's own output —
  // never a hand-edited scored.winners.
  const scoredOut = runJsCode(nodes["Normalize + Score"].parameters.jsCode, [row]);
  const mergeOut = runJsCode(nodes["Merge Winners"].parameters.jsCode, scoredOut);
  assert.ok(mergeOut[0].merge && typeof mergeOut[0].merge === "object", "merge is a real object");
  assert.equal(mergeOut[0].merge.canonicalPatch.lv_persona_group, "media_and_communication",
    "COPY-02: the produced persona value must reach the lv_-prefixed canonical key");

  // D-COPY-adjacency (derived, not hand-written): every canonical key a persona-free run
  // of the SAME provider row produces is still present and unchanged with the persona
  // candidate added — proves the fix is additive, not disruptive.
  const noPersonaRow = seedRow({ apollo: { ...apolloContact, departments: undefined }, lusha: null, zoominfo: null });
  const scoredNoPersona = runJsCode(nodes["Normalize + Score"].parameters.jsCode, [noPersonaRow]);
  const mergeNoPersona = runJsCode(nodes["Merge Winners"].parameters.jsCode, scoredNoPersona);
  const baseKeys = Object.keys(mergeNoPersona[0].merge.canonicalPatch);
  assert.ok(baseKeys.length > 0, "the persona-free row must itself promote at least one field");
  for (const key of baseKeys) {
    assert.ok(key in mergeOut[0].merge.canonicalPatch, `existing canonical key ${key} must survive the persona addition`);
    assert.equal(mergeOut[0].merge.canonicalPatch[key], mergeNoPersona[0].merge.canonicalPatch[key],
      `existing canonical key ${key} must be unchanged by the persona addition`);
  }
});
