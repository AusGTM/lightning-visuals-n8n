// BUG 27 behavioral proof — HubSpot v3 PATCH rejects JSON arrays in property values
// (live 400 on execution 328, 2026-07-30: lv_content_type=["live_broadcast"] →
// "Cannot deserialize value ... from Array value"). Multi-checkbox values must be
// semicolon-joined strings. Executes the repo's OWN compiled decide-node jsCode from
// the built workflow (same new Function harness as createIdentitySeed.test.mjs).
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
  // SAFETY: interpolated string is this repo's own committed jsCode (see
  // createIdentitySeed.test.mjs for the precedent + rationale).
  const fn = new Function("$input", "$json", "$now", `"use strict";\n${node(name).parameters.jsCode}`);
  return fn($input, rows[0], new Date("2026-07-30T00:00:00Z")).map((it) => it.json);
}

test("companies: array-valued canonicalPatch field serializes to semicolon-joined string", () => {
  const [out] = runDecide("Decide Company Action", [{
    action: "enrich",
    existingRecord: { hs_object_id: "9604614548" },
    identity_keys: { domain: "bug27.example" },
    merge: {
      canonicalPatch: { lv_content_type: ["live_broadcast", "streaming"], lv_org_type: "broadcaster" },
      cacheKeys: {}, decisions: [], provenance: {},
    },
  }]);
  assert.equal(out.properties.lv_content_type, "live_broadcast;streaming");
  assert.equal(out.properties.lv_org_type, "broadcaster", "scalar values pass through untouched");
  for (const [k, v] of Object.entries(out.properties)) {
    assert.ok(!Array.isArray(v), `no array value may reach the PATCH body (${k})`);
  }
});

test("contacts: array values in the assembled patch serialize to semicolon-joined strings", () => {
  const [out] = runDecide("Decide Action", [{
    action: "enrich",
    object_type: "contacts",
    existingRecord: { hs_object_id: "201" },
    identity_keys: { email: "bug27@example.test" },
    merge: {
      canonicalPatch: { jobtitle: "Head of Racing", persona_group: ["ops", "media"] },
      cacheKeys: {}, decisions: [], provenance: {},
    },
  }]);
  assert.equal(out.properties.persona_group, "ops;media");
  assert.equal(out.properties.jobtitle, "Head of Racing");
  for (const [k, v] of Object.entries(out.properties)) {
    assert.ok(!Array.isArray(v), `no array value may reach the PATCH body (${k})`);
  }
});
