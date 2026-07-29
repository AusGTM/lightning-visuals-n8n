// tests/n8n/personaGroupCopyLoop.test.mjs
//
// Phase 18 Plan 02 (COPY-02) — compiled-node-body differential proving the persona
// field reaches the contacts merge call. Reuses the tests/n8n/writePatchBodyFlow.test.mjs
// `loadWorkflow()` + `runJsCode()` harness verbatim (the `new Function(...)` idiom over
// the repo's own committed jsCode — no external or untrusted input is ever interpolated
// into the function body) and its SEED_ROW vocabulary (action, object_type contacts,
// identity_keys, existingRecord, scored.winners).
//
// "Merge Winners" is NOT one of tests/test_companies_factory_frozen.py's
// FROZEN_NODE_NAMES, so there is no pre-fix write-once fixture for it (unlike COPY-01's
// Merge Company). Its red evidence is a recorded verbatim `node --test` run captured
// BEFORE the source edit landed (see 18-02-SUMMARY.md), not a durable fixture compare.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

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

// Seed row: same vocabulary as writePatchBodyFlow's SEED_ROW. jobtitle stays blank so
// the (already-working) stale_refreshable field promotes today, proving non-vacuity.
// persona_group is set on scored.winners using the unprefixed read-side key the wrapper
// reads (mirrors the pre-existing linkedin_url read-side field name); the corresponding
// canonical property (lv_persona_group) is blank on existingRecord.
function seedRow(personaValue) {
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
    scored: {
      winners: {
        email: "someone-else@example.com",
        phone: "+61388888888",
        jobtitle: "Head of Broadcast",
        seniority: "Director",
        ...(personaValue === undefined ? {} : { persona_group: personaValue }),
      },
    },
  };
}

test("(a) VACUITY GUARD: merge result is real and an already-working field still promotes", () => {
  const nodes = loadWorkflow();
  const out = runJsCode(nodes["Merge Winners"].parameters.jsCode, [seedRow("Broadcast Ops")]);
  assert.ok(out[0].merge && typeof out[0].merge === "object", "merge is a real object, not the null skip branch");
  assert.equal(out[0].merge.canonicalPatch.seniority, "Director", "system_owned field still promotes today");
});

test("(b) GREEN (RED until the fix lands): persona value promotes to lv_persona_group in canonicalPatch", () => {
  const nodes = loadWorkflow();
  const out = runJsCode(nodes["Merge Winners"].parameters.jsCode, [seedRow("Broadcast Ops")]);
  assert.equal(out[0].merge.canonicalPatch.lv_persona_group, "Broadcast Ops",
    "COPY-02: persona value must reach the lv_-prefixed canonical key");
});

test("(c) EDGE D-COPY-empty: a whitespace-only persona winner produces no lv_persona_group key", () => {
  const nodes = loadWorkflow();
  const out = runJsCode(nodes["Merge Winners"].parameters.jsCode, [seedRow("   ")]);
  assert.ok(!("lv_persona_group" in out[0].merge.canonicalPatch), "blank guard must skip a whitespace-only value");
  const decision = out[0].merge.decisions.find((d) => d.field === "lv_persona_group");
  assert.ok(!decision, "no decision entry should exist for a value that never reached the merge call");
});

test("(d) EDGE D-COPY-adjacency: every canonical key present without a persona winner is still present with one", () => {
  const nodes = loadWorkflow();
  const withoutPersona = runJsCode(nodes["Merge Winners"].parameters.jsCode, [seedRow(undefined)]);
  const withPersona = runJsCode(nodes["Merge Winners"].parameters.jsCode, [seedRow("Broadcast Ops")]);
  const baseKeys = Object.keys(withoutPersona[0].merge.canonicalPatch);
  assert.ok(baseKeys.length > 0, "the persona-free row must itself promote at least one field");
  for (const key of baseKeys) {
    assert.ok(key in withPersona[0].merge.canonicalPatch,
      `existing canonical key ${key} must survive the persona addition`);
    assert.equal(withPersona[0].merge.canonicalPatch[key], withoutPersona[0].merge.canonicalPatch[key],
      `existing canonical key ${key} must be unchanged by the persona addition`);
  }
});
