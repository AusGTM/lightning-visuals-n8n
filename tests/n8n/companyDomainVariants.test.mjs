// tests/n8n/companyDomainVariants.test.mjs
//
// F-B7 (stress attempt 2, 2026-09-15, exec 12449 and friends): the companies branch's own
// domain search matched `domain EQ <bare>` only, so it never found the three live portal
// records stored under a `www.` domain (Racing Victoria, Wyong, Canberra RC) — all three
// got duplicated. Folded in: F-B4's empty-`values` 400 — a name-only row's domain filter
// sent `value: ""`, HubSpot rejected the search outright, and the resulting error item was
// mislabelled `lookup_failed`.
//
// Drives the repo's own committed jsCode/jsonBody for "Build Company Identity" and
// "HubSpot Company Search" against n8n/wf_enrichment_cloud.json — the same per-node
// runner tests/n8n/companyNameFallbackFlow.test.mjs and companyRecomputeLaneFlow.test.mjs
// already established for this branch (no external or untrusted input is ever
// interpolated into a function body; this executes the repo's OWN committed code, the
// same thing n8n's Code/HTTP nodes do at runtime).
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

function runCode(jsCode, items) {
  const $input = { all: () => items.map((j) => ({ json: j })) };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  return (fn($input) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

function buildIdentity(rows) {
  return runCode(node("Build Company Identity").parameters.jsCode, rows);
}

// The exact filter body "HubSpot Company Search" sends — evaluated as a real n8n
// expression against a given row, never restated. Returns the parsed filter object AND
// the raw JS so the "resolves live" test can re-evaluate it per stub call.
function searchFilter(row) {
  const raw = node("HubSpot Company Search").parameters.jsonBody;
  const m = /^=\{\{([\s\S]*)\}\}$/.exec(String(raw).trim());
  assert.ok(m, "HubSpot Company Search jsonBody is not an n8n expression");
  const fn = new Function("$json", `"use strict"; return (${m[1].trim()});`);
  const body = JSON.parse(fn(row));
  return body.filterGroups[0].filters[0];
}

test("a request domain gets a [bare, www.bare] variant pair", () => {
  const [row] = buildIdentity([{ domain: "wyongraceclub.com.au" }]);
  assert.deepEqual(row.domain_variants, ["wyongraceclub.com.au", "www.wyongraceclub.com.au"]);
});

test("a www.-prefixed request domain is stripped first, never doubled", () => {
  const [row] = buildIdentity([{ domain: "www.wyongraceclub.com.au" }]);
  assert.deepEqual(row.domain_variants, ["wyongraceclub.com.au", "www.wyongraceclub.com.au"]);
});

test("a no-domain row gets exactly one variant, the .invalid sentinel — never an empty array", () => {
  const [row] = buildIdentity([{ company: "Illawarra Turf Club" }]);
  assert.deepEqual(row.domain_variants, ["no-company-domain.invalid"]);
  assert.notEqual(row.domain_variants.length, 0, "HubSpot 400s on an empty values array");
});

test("stored portal domains are never touched — only the request-side candidates change", () => {
  const [row] = buildIdentity([{ domain: "wyongraceclub.com.au" }]);
  assert.equal(row.identity_keys.domain, "wyongraceclub.com.au", "the identity anchor is unchanged");
});

test("the search filter is ONE IN request over domain_variants, never an EQ", () => {
  const [row] = buildIdentity([{ domain: "wyongraceclub.com.au" }]);
  const filter = searchFilter(row);
  assert.equal(filter.propertyName, "domain");
  assert.equal(filter.operator, "IN");
  assert.deepEqual(filter.values, ["wyongraceclub.com.au", "www.wyongraceclub.com.au"]);
});

test("a no-domain row's search body carries the sentinel, never an empty values list", () => {
  const [row] = buildIdentity([{ company: "Illawarra Turf Club" }]);
  const filter = searchFilter(row);
  assert.deepEqual(filter.values, ["no-company-domain.invalid"]);
});

// The live F-B7 case: a portal record stored under `www.wyongraceclub.com.au` must
// resolve from a bare-domain request. The stub answers ONLY the domain(s) the evaluated
// filter actually asked for — never a canned response — so this fails pre-fix (a bare-only
// EQ request never asks for the www. form, gets zero hits, and Company Gate says "create").
test("a www.-stored portal record resolves from a bare-domain request (F-B7, the live duplicate)", () => {
  const [identityRow] = buildIdentity([{ domain: "wyongraceclub.com.au" }]);
  const filter = searchFilter(identityRow);
  const asked = filter.values ?? [filter.value];

  const STORED_DOMAIN = "www.wyongraceclub.com.au";
  const searchResponse = asked.includes(STORED_DOMAIN)
    ? { total: 1, results: [{ id: "18700000001",
        properties: { name: "Wyong Race Club", domain: STORED_DOMAIN } }] }
    : { total: 0, results: [] };

  const merged = { ...searchResponse, ...identityRow };
  const [searched] = runCode(node("Adapt Company Search").parameters.jsCode, [merged]);
  assert.equal(searched.lookup_failed, false);

  // Feed a MINIMAL row into the name-fallback adapter (companyNameFallbackFlow.test.mjs's
  // own convention) — the real "Adapt Company Search" output still carries the domain
  // search's own `results`/`total`, which would otherwise clash-override the name
  // search's fresh response under the carry merge's "carried-row-last" rule.
  const nameSearchRow = { identity_keys: searched.identity_keys,
    existingRecord: searched.existingRecord, lookup_failed: searched.lookup_failed };
  const [named] = runCode(node("Adapt Company Name Search").parameters.jsCode,
    [{ results: [], total: 0, ...nameSearchRow }]);

  const [gated] = runCode(node("Company Gate").parameters.jsCode, [named]);
  assert.equal(gated.existingRecord.hs_object_id, "18700000001");
  assert.notEqual(gated.action, "create", "a www.-stored record must never be re-created");
});

test("a no-domain row's clean zero-hit search is never mislabelled a failed lookup (F-B4)", () => {
  const [identityRow] = buildIdentity([{ company: "Illawarra Turf Club" }]);
  const merged = { total: 0, results: [], ...identityRow };
  const [searched] = runCode(node("Adapt Company Search").parameters.jsCode, [merged]);
  assert.equal(searched.lookup_failed, false);
  assert.deepEqual(searched.existingRecord, {});
});
