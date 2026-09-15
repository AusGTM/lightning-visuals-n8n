// tests/n8n/companyNameOnlyOutcome.test.mjs
//
// D-73-22 (folded F-B4) + D-73-20 (F-B7 total > 1). Illawarra (stress attempt 2, exec
// 12449): a name-only company row sent `HubSpot Company Search` with `domain EQ ""`,
// HubSpot 400'd, and the resulting error item was mislabelled a failed lookup — the row
// then reported `skip: "no existing record"`, a nonsensical pairing that never told the
// operator a domain was needed. 73-03 Task 1's `.invalid` sentinel already turns that 400
// into a clean zero-hit 200; this task makes the OUTCOME legible: never `create`, never
// `skip` for a name-only row that could not resolve by exact name — always `review`, with
// a reason naming the failure shape and what to supply.
//
// Drives the repo's own committed jsCode for "Adapt Company Name Search" and
// "Company Gate" against n8n/wf_enrichment_cloud.json, in the established per-node style
// (companyNameFallbackFlow.test.mjs, companyRecomputeLaneFlow.test.mjs) — real committed
// code, no untrusted input interpolated.
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

const envelope = (companies) => ({
  total: companies.length,
  results: companies.map((c) => ({ id: c.id, properties: { name: c.name, domain: c.domain } })),
});

// Runs "Adapt Company Name Search" the way companyNameFallbackFlow.test.mjs does — a
// minimal fabricated row (never the real "Adapt Company Search" output, which carries the
// domain search's own stale results/total that would clash-override this hop's fresh
// response under the carry merge's "carried-row-last" rule).
function runNameAdapter(row, searchItem) {
  const [out] = runCode(node("Adapt Company Name Search").parameters.jsCode,
    [{ ...searchItem, ...row }]);
  return out;
}

function runGate(row) {
  const [out] = runCode(node("Company Gate").parameters.jsCode, [row]);
  return out;
}

const NAME_ONLY = { identity_keys: { domain: null, companyName: "Illawarra Turf Club" },
  existingRecord: {}, lookup_failed: false };

// --- shape 1: exactly one hit -> enrich, company_match_basis "name" -----------------

test("one exact-name hit: enrich on that record, company_match_basis name", () => {
  const named = runNameAdapter(NAME_ONLY,
    envelope([{ id: "1", name: "Illawarra Turf Club", domain: "illawarraturfclub.example" }]));
  assert.equal(named.existingRecord.hs_object_id, "1");
  assert.equal(named.company_match_basis, "name");

  const gated = runGate(named);
  assert.notEqual(gated.action, "create");
  assert.notEqual(gated.action, "skip");
});

// --- shape 2: zero hits -> review, reason names the outcome + no domain + remedy ----

test("zero exact-name hits: review, never create, never skip — reason names the outcome, the missing domain, and the remedy", () => {
  const named = runNameAdapter(NAME_ONLY, envelope([]));
  assert.equal(named.name_search_outcome, "zero_hits");

  const gated = runGate(named);
  assert.equal(gated.action, "review");
  assert.match(gated.gate.reason, /no existing company matched by exact name/);
  assert.match(gated.gate.reason, /no domain/);
  assert.match(gated.gate.reason, /supply one/);
});

// --- shape 3: many hits -> review, reason carries the count -------------------------

test("more than one exact-name hit: review, never create, never skip — reason carries the count and the remedy", () => {
  const named = runNameAdapter(NAME_ONLY, envelope([
    { id: "1", name: "Illawarra Turf Club", domain: "a.example" },
    { id: "2", name: "Illawarra Turf Club", domain: "b.example" },
  ]));
  assert.equal(named.name_search_outcome, "many_hits");
  assert.equal(named.name_search_hit_count, 2);

  const gated = runGate(named);
  assert.equal(gated.action, "review");
  assert.match(gated.gate.reason, /2 companies share this exact name/);
  assert.match(gated.gate.reason, /could not be isolated/);
  assert.match(gated.gate.reason, /no domain/);
  assert.match(gated.gate.reason, /supply one/);
});

// --- transport failure: stays lookup_failed, keeps its own pre-existing reason ------

test("a genuine HTTP failure on the name search stamps lookup_failed and keeps the pre-existing skip reason — never merged into either name-only reason", () => {
  const named = runNameAdapter(NAME_ONLY, { error: "ECONNRESET" });
  assert.equal(named.lookup_failed, true);
  assert.equal(named.name_search_outcome, undefined);

  const gated = runGate(named);
  assert.equal(gated.action, "skip");
  assert.equal(gated.gate.reason, "no existing record",
    "the pre-existing fail-closed reason is untouched by the name-only wording");
});

// --- domain-present name-fallback precedent is untouched ----------------------------

test("a domain-present row's zero/many-hit name-fallback outcome is unaffected (existing precedent, never review)", () => {
  const domainRow = { identity_keys: { domain: "x.example", companyName: "Racing Club" },
    existingRecord: {}, lookup_failed: false };
  const named = runNameAdapter(domainRow, envelope([
    { id: "1", name: "Racing Club", domain: "a.example" },
    { id: "2", name: "Racing Club", domain: "b.example" },
  ]));
  assert.equal(named.name_search_outcome, undefined, "only a name-only row gets the outcome stamp");
  const gated = runGate(named);
  assert.equal(gated.action, "create", "a domain-present row still creates from its own domain");
});

// --- D-73-20: a two-hit domain search resolves, never a review, names both ids ------

test("a two-hit domain IN search resolves to one record, preferring the bare-domain hit, naming both ids — never a review", () => {
  const identityRow = { identity_keys: { domain: "wyongraceclub.com.au", companyName: "Wyong Race Club" } };
  const merged = { ...identityRow,
    results: [
      { id: "999", properties: { name: "Wyong Race Club (dup)", domain: "www.wyongraceclub.com.au" } },
      { id: "111", properties: { name: "Wyong Race Club", domain: "wyongraceclub.com.au" } },
    ],
  };
  const [searched] = runCode(node("Adapt Company Search").parameters.jsCode, [merged]);
  assert.equal(searched.existingRecord.hs_object_id, "111", "the bare-domain hit is preferred");
  assert.match(searched.domain_match_note, /111/);
  assert.match(searched.domain_match_note, /999/);

  const nameSearchRow = { identity_keys: searched.identity_keys,
    existingRecord: searched.existingRecord, lookup_failed: searched.lookup_failed,
    domain_match_note: searched.domain_match_note };
  const named = runNameAdapter(nameSearchRow, { results: [], total: 0 });

  const gated = runGate(named);
  assert.notEqual(gated.action, "review");
  assert.match(gated.gate.reason, /111/);
  assert.match(gated.gate.reason, /999/);
});
