// BUG 19 behavioral proof — executes the repo's OWN compiled decide-node jsCode from the
// built workflow (same new Function harness precedent as bareEventChainFlow.test.mjs).
//
// Two directions, both load-bearing:
//   create -> the payload MUST carry identity (else the record is invisible to the very
//             search that gated the create; confirmed live 2026-07-29, name=None/
//             domain=None, search total=0).
//   enrich -> the payload MUST NOT carry the seed (an unconditional seed would clobber
//             an existing human value on update, regardless of the field's policy class —
//             260826-20w T-20w-01 reclassified contact email fill_blank_only, which
//             already protects an existing value via its own non-blank branch; the SEED
//             is a separate, additive guard this file tests, not a restatement of it).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const wf = JSON.parse(readFileSync("n8n/wf_enrichment_cloud.json", "utf8"));
const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};

function runDecide(name, rows) {
  const $input = { all: () => rows.map((r) => ({ json: r })) };
  // SAFETY: the interpolated string is this repo's own committed n8n/wf_enrichment_cloud.json
  // jsCode — not untrusted input — and executing it verbatim is the point of the test
  // (transcribing it would test the transcription, not the artifact). Same harness pattern
  // as tests/n8n/bareEventChainFlow.test.mjs.
  const fn = new Function("$input", "$json", "$now", `"use strict";\n${node(name).parameters.jsCode}`);
  return fn($input, rows[0], new Date("2026-07-29T00:00:00Z")).map((it) => it.json);
}

const CO_MERGE = { canonicalPatch: { lv_org_type: "governing_body_league" }, cacheKeys: {}, decisions: [], provenance: {} };

test("companies create: payload carries domain + name from identity_keys", () => {
  const [out] = runDecide("Decide Company Action", [{
    action: "create",
    identity_keys: { domain: "seed-canary.example", companyName: "Seed Canary" },
    merge: CO_MERGE,
  }]);
  assert.equal(out.properties.domain, "seed-canary.example");
  assert.equal(out.properties.name, "Seed Canary");
  assert.equal(out.properties.lv_org_type, "governing_body_league");
  // Committed build ships write-safety disabled — the gate must still block the write.
  assert.equal(out.action, "write_blocked");
});

test("companies enrich: payload does NOT receive the identity seed (non-clobber)", () => {
  const [out] = runDecide("Decide Company Action", [{
    action: "enrich",
    identity_keys: { domain: "seed-canary.example", companyName: "Seed Canary" },
    existingRecord: { hs_object_id: "123" },
    merge: CO_MERGE,
  }]);
  assert.equal(out.properties.domain, undefined,
    "seeding domain on enrich is the exact clobber manual_protected exists to prevent");
  assert.equal(out.properties.name, undefined);
});

test("contacts create: payload carries email from identity_keys", () => {
  const [out] = runDecide("Decide Action", [{
    action: "create",
    identity_keys: { email: "seed@canary.example" },
    merge: { canonicalPatch: { seniority: "Manager" }, cacheKeys: {}, provenance: {} },
  }]);
  assert.equal(out.properties.email, "seed@canary.example");
  assert.equal(out.properties.seniority, "Manager");
  assert.equal(out.action, "write_blocked");
});

test("contacts enrich: payload does NOT receive the email seed (non-clobber)", () => {
  const [out] = runDecide("Decide Action", [{
    action: "enrich",
    identity_keys: { email: "seed@canary.example" },
    existingRecord: { hs_object_id: "201" },
    merge: { canonicalPatch: { seniority: "Manager" }, cacheKeys: {}, provenance: {} },
  }]);
  assert.equal(out.properties.email, undefined,
    "this fixture's merge object carries no email candidate at all, and the identity " +
    "seed only fires on create — the seed must never reach an update (260826-20w T-20w-01 " +
    "reclassified email fill_blank_only, but this test proves the SEED guard, not the " +
    "merge policy, so it is unaffected)");
});
