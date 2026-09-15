// tests/n8n/companyFreemailRefusal.test.mjs
//
// F-B3 (stress attempt 2, exec 12449): "Country Racing Collective", website `gmail.com`,
// was accepted and CREATED (company 288135240183) — freemail is never a company's own
// domain, and neither the plugin's domain clean nor the backend refused it. D-73-08/09:
// refused in BOTH engines from the ONE authoritative set, n8n/code/companyLink.js's
// FREEMAIL_DOMAINS (JS) mirrored in operator-claude-plugin/scripts/enrichment.py
// (Python, pinned by tests/test_people_and_url_normalisation.py's parity test). This file
// pins the backend half: a functional parity check over the REAL committed set, driving
// "Decide Company Action"'s own jsCode (no restated literal, no parsing of the source).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { FREEMAIL_DOMAINS } = require(path.join(ROOT, "n8n", "code", "companyLink.js"));
const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};

function decide(row) {
  const $input = { all: () => [{ json: row }] };
  const fn = new Function("$input", `"use strict";\n${node("Decide Company Action").parameters.jsCode}`);
  const [out] = fn($input);
  return out.json !== undefined ? out.json : out;
}

const createRow = (domain) => ({
  action: "create",
  mode: null,
  identity_keys: { domain, companyName: "Test Co" },
  existingRecord: {},
  gate: { reason: "no existing record" },
});

test("every freemail domain in the authoritative set refuses a create, review, D-73-09 reason", () => {
  for (const domain of FREEMAIL_DOMAINS) {
    const out = decide(createRow(domain));
    assert.equal(out.action, "review", `domain ${domain} must not create a company`);
    assert.equal(out.reason, "freemail domain — supply the real website");
  }
});

test("the live F-B3 domain (gmail.com) is refused, never created", () => {
  const out = decide(createRow("gmail.com"));
  assert.equal(out.action, "review");
  assert.equal(out.reason, "freemail domain — supply the real website");
  assert.equal(out.properties.domain, undefined, "no seeded domain on a refused create");
});

test("a legitimate company domain is unaffected — still creates normally", () => {
  const out = decide(createRow("wyongraceclub.com.au"));
  assert.equal(out.action, "create");
  assert.equal(out.properties.domain, "wyongraceclub.com.au");
});

test("an enrich (not a create) on a freemail-domain record is untouched by this refusal", () => {
  const row = { action: "enrich", mode: null,
    identity_keys: { domain: "gmail.com", companyName: "Test Co" },
    existingRecord: { hs_object_id: "123" }, gate: { reason: "missing: industry" } };
  const out = decide(row);
  assert.equal(out.action, "enrich", "the refusal only ever fires on a create");
});

test("a propose (returnOnly) row is never held on freemail — it reports proposed like every other propose row", () => {
  const out = decide({ ...createRow("gmail.com"), mode: "propose" });
  assert.equal(out.action, "proposed", "a propose call writes nothing regardless");
});
