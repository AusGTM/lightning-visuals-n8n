// Regression guard for the F5 multi-run convergence fix
// (.planning/debug/uat-batch-review-row-reads-failed.md), executed against the ACTUAL
// committed jsCode in n8n/wf_enrichment_cloud.json — the same `new Function` mechanism
// n8n's Code node uses at runtime (see researchChainRowFlow.test.mjs's note).
//
// Bug (confirmed live, execution 12163, 2026-09-09): "Enrichment Gate"/"Company Gate"
// have more than one inbound connection (one lane per identity path — email, linkedin,
// name, fetch-by-id, unmatchable for contacts; fetch-by-id vs domain/name-search for
// companies) and n8n runs a node with multiple inbound edges ONCE PER FIRING EDGE, not
// once on a merged item array. "Normalize + Score"/"Normalize + Score Company" read
// their upstream gate BY NAME (required — HTTP provider hops replace $json) via a bare
// `$('Gate').all()`, which n8n's own docs say returns only the node's MOST RECENT run.
// A 4-row mixed batch (2 email rows, 2 no-email/name rows) came back with only the
// no-email rows twice; the two email rows vanished from every downstream node.
//
// This models n8n's documented `.all(branchIndex, runIndex)` / `$runIndex` contract
// (bare `.all()` = most recent run; `.all(0, r)` = a specific run) directly, and proves
// two things a naive `.all(0, $runIndex)` fix would NOT prove:
//   (A) the F5 repro itself — two upstream runs, no drop, must not collapse to the last;
//   (B) the drift case — a THIRD upstream run that is entirely `action: "skip"` (e.g.
//       the unmatchable/"IF Name Searchable" false lane, or "IF Company Skip"'s true
//       lane) never reaches this node at all, so this node's OWN run count falls behind
//       the gate's raw run count — pairing by raw run index would return the wrong
//       (dropped) run for every wave after the drop.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");
const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};
const jsCodeOf = (name) => node(name).parameters.jsCode;

// runData: { nodeName: [ run0Items, run1Items, ... ] } — each runNItems is a plain array
// of $json objects (NOT wrapped in {json}). Mirrors n8n's own per-node run history.
function makeDollar(runData) {
  return (name) => ({
    all: (branch, run) => {
      const runs = runData[name];
      if (!runs) throw new Error(`no node named ${name}`);
      const r = run === undefined ? runs.length - 1 : run; // bare .all() -> most recent run
      if (r < 0 || r >= runs.length) throw new Error(`no run ${r} for ${name}`);
      return runs[r].map((j) => ({ json: j }));
    },
  });
}

// Invokes ONE run (runIndex) of the named node's jsCode, feeding it the given $input
// items and the upstream run history it may read BY NAME.
function runOneNodeRun(jsCode, inputItems, runData, runIndex) {
  const $ = makeDollar(runData);
  const $input = { all: () => inputItems.map((j) => ({ json: j })) };
  const $runIndex = runIndex;
  // ZoomInfo Token Gate reads $getWorkflowStaticData("global") for its token cache —
  // irrelevant to the run-recovery assertions here, so a fresh empty store per call is
  // enough (the code's own needsMint(undefined, ...) branch handles it safely).
  const $getWorkflowStaticData = () => ({});
  const fn = new Function(
    "$", "$input", "$runIndex", "$getWorkflowStaticData", `"use strict";\n${jsCode}`
  );
  const out = fn($, $input, $runIndex, $getWorkflowStaticData) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

const emailRow = (row_id) => ({
  row_id, action: "create", object_type: "contacts",
  identity_keys: { email: `${row_id}@example.com` },
  existingRecord: {}, gate: { missingFields: [] },
});
const nameRow = (row_id) => ({
  row_id, action: "enrich", object_type: "contacts",
  identity_keys: { firstName: "F", lastName: row_id, companyName: "Co" },
  existingRecord: {}, gate: { missingFields: [] },
});
const unmatchableSkipRow = (row_id) => ({ row_id, action: "skip", object_type: "contacts" });

const companyRow = (row_id) => ({
  row_id, action: "create",
  identity_keys: { domain: `${row_id}.example` },
  existingRecord: {}, gate: { missingFields: [] },
});
const companySkipRow = (row_id) => ({ row_id, action: "skip" });

test("F5 repro (A): Normalize + Score — two upstream Enrichment Gate runs, both must survive, in order", () => {
  const jsCode = jsCodeOf("Normalize + Score");
  const runData = {
    "Enrichment Gate": [
      [emailRow("row-1"), emailRow("row-4")],
      [nameRow("row-2"), nameRow("row-3")],
    ],
  };
  const run0 = runOneNodeRun(jsCode, runData["Enrichment Gate"][0], runData, 0);
  const run1 = runOneNodeRun(jsCode, runData["Enrichment Gate"][1], runData, 1);
  assert.deepEqual(run0.map((r) => r.row_id), ["row-1", "row-4"],
    "run 0 (email lane) must return the email lane's own rows, not the last lane's");
  assert.deepEqual(run1.map((r) => r.row_id), ["row-2", "row-3"],
    "run 1 (name lane) must return the name lane's own rows");
});

test("F5 drift case (B): Normalize + Score — an all-skip middle Gate run must not shift the pairing", () => {
  const jsCode = jsCodeOf("Normalize + Score");
  // Three Gate runs; the middle is entirely skip and never reaches this node at all —
  // "Normalize + Score" itself therefore only runs twice (its own $runIndex is 0, 1).
  const runData = {
    "Enrichment Gate": [
      [emailRow("row-1")],
      [unmatchableSkipRow("row-x"), unmatchableSkipRow("row-y")],
      [nameRow("row-9")],
    ],
  };
  const readerRun0 = runOneNodeRun(jsCode, runData["Enrichment Gate"][0], runData, 0);
  const readerRun1 = runOneNodeRun(jsCode, runData["Enrichment Gate"][2], runData, 1);
  assert.deepEqual(readerRun0.map((r) => r.row_id), ["row-1"]);
  assert.deepEqual(readerRun1.map((r) => r.row_id), ["row-9"],
    "the reader's second run must pair with the Gate's SECOND SURVIVING run (index 2), not its raw run index 1 (the dropped all-skip run)");
});

test("F5 repro (A), companies: Normalize + Score Company — two upstream Company Gate runs, both must survive", () => {
  const jsCode = jsCodeOf("Normalize + Score Company");
  const runData = {
    "Company Gate": [
      [companyRow("co-1")],
      [companyRow("co-2"), companyRow("co-3")],
    ],
  };
  const run0 = runOneNodeRun(jsCode, runData["Company Gate"][0], runData, 0);
  const run1 = runOneNodeRun(jsCode, runData["Company Gate"][1], runData, 1);
  assert.deepEqual(run0.map((r) => r.row_id), ["co-1"]);
  assert.deepEqual(run1.map((r) => r.row_id), ["co-2", "co-3"]);
});

test("F5 drift case (B), companies: Normalize + Score Company — an all-skip middle Company Gate run must not shift the pairing", () => {
  const jsCode = jsCodeOf("Normalize + Score Company");
  const runData = {
    "Company Gate": [
      [companyRow("co-1")],
      [companySkipRow("co-skip")],
      [companyRow("co-9")],
    ],
  };
  const readerRun0 = runOneNodeRun(jsCode, runData["Company Gate"][0], runData, 0);
  const readerRun1 = runOneNodeRun(jsCode, runData["Company Gate"][2], runData, 1);
  assert.deepEqual(readerRun0.map((r) => r.row_id), ["co-1"]);
  assert.deepEqual(readerRun1.map((r) => r.row_id), ["co-9"]);
});

test("ZoomInfo Token Gate: recovers the correct Enrichment Gate run by paired index, not the last one", () => {
  const jsCode = jsCodeOf("ZoomInfo Token Gate");
  const runData = {
    "Enrichment Gate": [
      [emailRow("row-1"), emailRow("row-4")],
      [nameRow("row-2"), nameRow("row-3")],
    ],
  };
  // $input here is the prior Apollo HTTP node's response (replaces $json) — content is
  // irrelevant to this assertion, only the paired-index recovery of `row` matters.
  const apolloResponseFor = (n) => Array.from({ length: n }, () => ({ some: "apollo-response" }));
  const run0 = runOneNodeRun(jsCode, apolloResponseFor(2), runData, 0);
  const run1 = runOneNodeRun(jsCode, apolloResponseFor(2), runData, 1);
  assert.deepEqual(run0.map((r) => r.row_id), ["row-1", "row-4"]);
  assert.deepEqual(run1.map((r) => r.row_id), ["row-2", "row-3"]);
});
