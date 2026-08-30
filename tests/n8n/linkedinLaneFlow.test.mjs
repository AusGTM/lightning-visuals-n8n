// tests/n8n/linkedinLaneFlow.test.mjs
//
// Phase 61 Plan 02 (D-61-05 CORRECTED). The exact walk-failure row —
// `https://www.linkedin.com/in/robert-cavallucci-14698741/`, no other fields — must route
// to a `linkedin` lane, reach a HubSpot search node, and come back with a verdict that is
// not "could not look". This file pins that end to end against the committed
// wf_enrichment_cloud.json, mirroring companyNameFallbackFlow.test.mjs's node-execution
// idiom (evaluate the repo's OWN built jsCode via `new Function`, mock only HTTP nodes).
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

// runNode(nodeName, buildIdentityRows, extraOutputs) — evaluates the named Code node's
// OWN committed jsCode. `extraOutputs` supplies whatever other node this Code node reads
// by name (HubSpot search envelopes, the name lane's fallback search, etc).
function runNode(nodeName, buildIdentityRows, extraOutputs) {
  const outputs = { "Build Identity": buildIdentityRows, ...(extraOutputs || {}) };
  const $ = (name) => {
    if (!(name in outputs)) throw new Error(`no node named ${name}`);
    return { all: () => outputs[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$", `"use strict";\n${node(nodeName).parameters.jsCode}`);
  return (fn($) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

const envelope = (hits) => ({ total: hits.length, results: hits });

// =============================================================================================
// Wiring: the linkedin lane sits between "IF Has Email" and "IF Name Searchable", and its
// own search->adapter chain feeds "Enrichment Gate" like every other lane.
// =============================================================================================

test("the linkedin lane sits between IF Has Email and IF Name Searchable, and its adapter feeds Enrichment Gate", () => {
  const edge = (from, i = 0) => (wf.connections[from]?.main?.[i] || []).map((c) => c.node);
  assert.deepEqual(edge("IF Has Email", 0), ["HubSpot Search"]);
  assert.deepEqual(edge("IF Has Email", 1), ["IF Linkedin Searchable"]);
  assert.deepEqual(edge("IF Linkedin Searchable", 0), ["HubSpot Linkedin Search"]);
  assert.deepEqual(edge("IF Linkedin Searchable", 1), ["IF Name Searchable"]);
  assert.deepEqual(edge("HubSpot Linkedin Search"), ["Adapt Linkedin Search"]);
  assert.deepEqual(edge("Adapt Linkedin Search"), ["Enrichment Gate"]);
  // "IF Name Searchable"'s own true/false targets are unchanged by this splice.
  assert.deepEqual(edge("IF Name Searchable", 0), ["HubSpot Name Search"]);
  assert.deepEqual(edge("IF Name Searchable", 1), ["Enrichment Gate"]);
});

test("HubSpot Linkedin Search is the credential-bound httpRequest transport, never the native node (BUG 23/10 lesson)", () => {
  assert.equal(node("HubSpot Linkedin Search").type, "n8n-nodes-base.httpRequest");
});

// =============================================================================================
// Adapt Linkedin Search — the exact walk-failure row, isolated
// =============================================================================================

const WALK_FAILURE_URL = "https://www.linkedin.com/in/robert-cavallucci-14698741/";

test("the exact walk-failure row (a LinkedIn URL and nothing else) reaches a tier other than unknown on a hit", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "9001", properties: { lv_linkedin_url: WALK_FAILURE_URL, firstname: "Robert", lastname: "Cavallucci" } },
    ])],
  });
  assert.notEqual(row.match.tier, "unknown");
  assert.equal(row.match.tier, "high");
  assert.equal(row.match.auto, true);
  assert.equal(row.existingRecord.hs_object_id, "9001");
});

test("the exact walk-failure row on a zero-hit search is none, not unknown — the search ran", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([])],
  });
  assert.equal(row.match.tier, "none");
  assert.deepEqual(row.existingRecord, {});
});

test("a failed linkedin search is unknown, and the row is never created off it", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [{ error: "ECONNRESET" }],
  });
  assert.equal(row.match.tier, "unknown");
  assert.equal(row.lookup_failed, true);
  assert.deepEqual(row.existingRecord, {});
});

test("two verified linkedin hits is ambiguity, never a pick — medium with both candidates, auto false", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "1", properties: { lv_linkedin_url: WALK_FAILURE_URL } },
      { id: "2", properties: { hs_linkedin_url: WALK_FAILURE_URL } },
    ])],
  });
  assert.equal(row.match.tier, "medium");
  assert.equal(row.match.auto, false);
  assert.equal(row.match.candidates.length, 2);
  assert.deepEqual(row.existingRecord, {});
});

// =============================================================================================
// THE DECISIVE TEST: a mixed batch (email + linkedin-only + name-only rows in ONE request)
// gets exactly one response item per row_id, and the linkedin row's tier is never unknown —
// the failure this phase exists to stop, in the shape it would take.
// =============================================================================================

test("mixed batch: an email row, a linkedin-only row and a name-only row each produce exactly one item, and the linkedin row is never unknown", () => {
  const rows = [
    { row_id: "row-email", identity_keys: { email: "jane@example.com" }, lane: "email" },
    { row_id: "row-linkedin", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" },
    { row_id: "row-name", identity_keys: { lastName: "Doe", companyName: "Gold Coast Turf Club" }, lane: "name" },
  ];

  const emailOut = runNode("Adapt Search", rows, {
    "HubSpot Search": [envelope([{ id: "100", properties: { email: "jane@example.com" } }])],
  });
  const linkedinOut = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([{ id: "9001", properties: { lv_linkedin_url: WALK_FAILURE_URL } }])],
  });
  const nameOut = runNode("Adapt Name Search", rows, {
    "HubSpot Name Search": [envelope([
      { id: "300", properties: { lastname: "Doe", company: "Gold Coast Turf Club" } },
    ])],
    "HubSpot Name Search Fallback": [],
  });

  // 36-CONTEXT.md Finding A: each adapter filters to ITS OWN lane before index-aligning —
  // exactly one output row per adapter here, none dropped, none duplicated.
  assert.equal(emailOut.length, 1);
  assert.equal(linkedinOut.length, 1);
  assert.equal(nameOut.length, 1);

  const byRowId = {};
  for (const r of [...emailOut, ...linkedinOut, ...nameOut]) {
    assert.ok(!(r.row_id in byRowId), `row_id ${r.row_id} produced more than one response item`);
    byRowId[r.row_id] = r;
  }
  assert.deepEqual(Object.keys(byRowId).sort(), ["row-email", "row-linkedin", "row-name"]);

  // The decisive assertion: the linkedin row's tier is not "unknown" — it dead-ends nowhere.
  assert.notEqual(byRowId["row-linkedin"].match.tier, "unknown");
  assert.equal(byRowId["row-linkedin"].match.tier, "high");
});
