// tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs
//
// Phase 70 Plan 04 Task 3 (D-70-01) — rewritten from a hand-modeled `recoverConvergedRun`
// interpreter test to a WALKER-DRIVEN acceptance of the real convergence.
//
// Original bug (confirmed live, execution 12163, 2026-09-09 —
// .planning/debug/resolved/uat-batch-review-row-reads-failed.md, F5): "Enrichment Gate"/
// "Company Gate" have more than one inbound connection (one lane per identity path —
// email, linkedin, name, fetch-by-id, unmatchable for contacts; fetch-by-id vs
// domain/name-search for companies) and n8n runs a node with multiple inbound edges ONCE
// PER FIRING EDGE, not once on a merged item array. Downstream readers recovering it BY
// NAME (`$('Gate').all()`, required because an HTTP hop replaces `$json`) got only the
// gate's MOST RECENT run — a 4-row mixed batch (2 email, 2 no-email) lost the email rows
// entirely. `n8n/code/nodeRunRecovery.js` (`recoverConvergedRun`) was the interim
// mitigation; this file used to test it directly in isolation.
//
// D-70-04 retires the mechanism this module patched, not just the module: "Enrichment
// Gate"/"Company Gate" downstream consumers no longer read either gate by name at all —
// they sit behind a real n8n Merge ("Enrichment Gate Merge"/"Company Gate Merge",
// Phase 70 Plan 03 Task 1) that collects every firing lane's rows into ONE array before
// the reader ever runs. This file now proves THAT property directly against the
// COMMITTED workflow, driven end to end through tests/n8n/lib/walkWorkflow.mjs (the same
// mechanism n8n uses at runtime) with a batch that fires TWO DIFFERENT contacts lanes in
// one execution — fetch-by-id (an event with no email) and email (an event with one) —
// exactly the F5 shape, minus the interim workaround.
//
// NOTE: this replays the repo's OWN committed workflow jsCode/expressions via `new
// Function` — the same mechanism n8n's Code/IF nodes use at runtime — over trusted,
// in-repo JSON. No external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { walkWorkflow, loadWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function load() {
  return loadWorkflow(WF_PATH);
}

// A generous stub set covering every HTTP node either lane below can reach on a
// disarmed batch (both write flags are "false" in the committed JSON).
function baseStubs() {
  return {
    "HubSpot Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "HubSpot Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search Fallback": (items) => items.map(() => ({ results: [] })),
    "HubSpot Linkedin Search": (items) => items.map(() => ({ results: [] })),
    "Lusha Enrich": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Match": (items) => items.map(() => ({})),
    "ZoomInfo Mint": [{ access_token: "tok" }],
    "Contact Web Research": (items) => items.map(() => ({})),
    "Contact Judge Call": (items) => items.map(() => ({})),
    "HubSpot Create": (items) => items.map((it, i) => ({ id: `create-${i}`, properties: it })),
    "HubSpot Update": (items) => items.map((it, i) => ({ id: `update-${i}`, properties: it })),
    "Lusha Usage": [{}],
    "Apollo Usage": [{}],
    "ZoomInfo Usage Mint": [{ access_token: "tok" }],
  };
}

// fetch-by-id lane: objectId present, NO email — laneOf() (n8n/code/matchProposal.js)
// resolves this to "fetch_by_id" specifically because email is absent.
function bareEvent(objectId) {
  return { objectId, objectType: "contact", run_id: "case" };
}
// email lane: objectId AND email both present — laneOf() resolves "email" whenever
// email is present, regardless of objectId (a realistic property-change webhook shape).
function emailEvent(objectId, email) {
  return { objectId, objectType: "contact", email, run_id: "case" };
}

function run(events, stubOverrides) {
  const wf = load();
  return walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { events } }],
    httpStubs: { ...baseStubs(), ...(stubOverrides || {}) },
  });
}

test("a batch firing TWO DIFFERENT contacts identity lanes reaches Enrichment Gate with BOTH rows, not collapsed to the last lane (F5 repro, D-70-01)", () => {
  const { runData, trace } = run([bareEvent("1"), emailEvent("2", "a@example.com")]);
  assert.deepEqual(trace.stalled, []);

  const gateRows = nodeItems(runData, "Enrichment Gate");
  const rowIds = gateRows.map((r) => r.object_id).sort();
  assert.deepEqual(rowIds, ["1", "2"],
    "both lanes' rows must reach the gate — a by-name recovery collapsing to the most " +
    "recent run would return only one of them");

  // And downstream of the gate: neither row is lost or duplicated by the time it
  // reaches the terminal convergence (the exact per-field content of each row is
  // covered by enrichmentConvergenceMerge.test.mjs's own mixed-batch test; this
  // assertion is scoped to the count, which is what a collapsed/duplicated run would
  // break).
  const responseRows = nodeItems(runData, "Build Response");
  assert.equal(responseRows.length, 2, "exactly one response row per input row");
});

test("Normalize + Score reads the carried row off $input, never a by-name lookup of Enrichment Gate (D-70-04)", () => {
  const wf = load();
  const node = wf.nodes.find((n) => n.name === "Normalize + Score");
  assert.ok(node, "node present: Normalize + Score");
  assert.equal(node.parameters.jsCode.includes("$('"), false);
  assert.equal(node.parameters.jsCode.includes('$("'), false);
});
