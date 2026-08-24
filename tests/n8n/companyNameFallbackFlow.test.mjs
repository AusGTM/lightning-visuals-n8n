// tests/n8n/companyNameFallbackFlow.test.mjs
//
// Found LIVE, 2026-08-25, by the ingest lane's own rehearsal (n8n execution 11922):
// Harness Racing NSW is company 18756544347 in portal 22617666 under domain
// `www.harnessmediacentre.com.au`. A companies request for `hrnsw.com.au` therefore
// resolved to NOTHING and `Company Gate` said "create" — a duplicate of a company that
// was already there, which is exactly what the operator ruled out.
//
// The fix is the same second key the ingest lane already resolves on: an EXACT name
// search, applied only where the domain search found nothing. This pins the four
// behaviours that matter, against the committed wf_enrichment_cloud.json.
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

function runAdapter(rows, searchItems) {
  const outputs = { "Adapt Company Search": rows, "HubSpot Company Name Search": searchItems };
  const $ = (name) => {
    if (!(name in outputs)) throw new Error(`no node named ${name}`);
    return { all: () => outputs[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$", `"use strict";\n${node("Adapt Company Name Search").parameters.jsCode}`);
  return (fn($) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

const envelope = (companies) => ({
  total: companies.length,
  results: companies.map((c) => ({ id: c.id, properties: { name: c.name, domain: c.domain } })),
});

test("the name search sits between the domain adapter and the gate, on the search branch only", () => {
  const edge = (from) => (wf.connections[from]?.main?.[0] || []).map((c) => c.node);
  assert.deepEqual(edge("Adapt Company Search"), ["HubSpot Company Name Search"]);
  assert.deepEqual(edge("HubSpot Company Name Search"), ["Adapt Company Name Search"]);
  assert.deepEqual(edge("Adapt Company Name Search"), ["Company Gate"]);
  // The fetch-by-id branch already holds its record and must not be re-resolved.
  assert.deepEqual(edge("Adapt Company Fetch By Id"), ["Company Gate"]);
});

test("the live HRNSW case: a domain miss resolves by exact name instead of creating a duplicate", () => {
  const [row] = runAdapter(
    [{ identity_keys: { domain: "hrnsw.com.au", companyName: "Harness Racing New South Wales" },
       existingRecord: {}, lookup_failed: false }],
    [envelope([{ id: "18756544347", name: "Harness Racing New South Wales",
                domain: "www.harnessmediacentre.com.au" }])]
  );
  assert.equal(row.existingRecord.hs_object_id, "18756544347");
  assert.equal(row.company_match_basis, "name");
});

test("a domain hit is never overridden by a name search", () => {
  const [row] = runAdapter(
    [{ identity_keys: { domain: "club.example", companyName: "Club" },
       existingRecord: { hs_object_id: "111", name: "The Club" }, lookup_failed: false }],
    [envelope([{ id: "999", name: "Club", domain: "elsewhere.example" }])]
  );
  assert.equal(row.existingRecord.hs_object_id, "111");
  assert.equal(row.company_match_basis, undefined);
});

test("a failed domain lookup stays unknown — never resolved by name, never created", () => {
  const [row] = runAdapter(
    [{ identity_keys: { domain: "club.example", companyName: "Club" },
       existingRecord: {}, lookup_failed: true }],
    [envelope([{ id: "999", name: "Club", domain: "club.example" }])]
  );
  assert.deepEqual(row.existingRecord, {});
  assert.equal(row.lookup_failed, true);
});

test("two companies with the same name is ambiguity — the row stays unresolved", () => {
  const [row] = runAdapter(
    [{ identity_keys: { domain: "x.example", companyName: "Racing Club" },
       existingRecord: {}, lookup_failed: false }],
    [envelope([{ id: "1", name: "Racing Club", domain: "a.example" },
               { id: "2", name: "Racing Club", domain: "b.example" }])]
  );
  assert.deepEqual(row.existingRecord, {});
});

test("a near-miss name (CONTAINS, not EQ) never resolves", () => {
  const [row] = runAdapter(
    [{ identity_keys: { domain: "x.example", companyName: "Racing Victoria" },
       existingRecord: {}, lookup_failed: false }],
    [envelope([{ id: "3", name: "Racing Victoria Foundation", domain: "rvf.example" }])]
  );
  assert.deepEqual(row.existingRecord, {});
});

test("an errored name search degrades to unresolved, never throws", () => {
  const [row] = runAdapter(
    [{ identity_keys: { domain: "x.example", companyName: "Club" },
       existingRecord: {}, lookup_failed: false }],
    [{ error: "ECONNRESET" }]
  );
  assert.deepEqual(row.existingRecord, {});
});
