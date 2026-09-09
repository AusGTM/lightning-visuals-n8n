// Tests for recoverConvergedRun (n8n/code/nodeRunRecovery.js) — the F5 fix.
//
// Bug (confirmed live, execution 12163, 2026-09-09 —
// .planning/debug/uat-batch-review-row-reads-failed.md): a node with more than one
// inbound connection (e.g. "Enrichment Gate", "Company Gate") runs once per firing
// inbound lane, not once on a merged item array. A bare `$('Node').all()` (no run
// index) returns only that node's MOST RECENT run — n8n's own docs confirm this — so a
// reader invoked once per lane collapsed every run onto the SAME (last) upstream run.
//
// n8n's documented fix for "same run as the current node" is
// `$('Node').all(0, $runIndex)`. That alone is insufficient whenever a wave can be
// dropped ENTIRELY between the two nodes (e.g. an all-skip lane never reaches the
// provider chain at all) — a dropped wave still consumes an upstream run index without
// ever producing a run of the reader, so a later wave's `$runIndex` then points at the
// WRONG (dropped) upstream run. recoverConvergedRun scans for the `runIndex`-th
// SURVIVING run instead, immune to that drift.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { recoverConvergedRun } = require("../../n8n/code/nodeRunRecovery.js");

const keepNonSkip = (it) => it.json.action !== "skip";

// A fake `all(nodeName, branchIndex, runIndex)` over a fixed array-of-runs, mirroring
// n8n's `.all(0, r)` contract exactly enough for this pure function: out-of-range throws
// (one of the two "past the end" signals recoverConvergedRun must tolerate; the other,
// returning [], is covered by a separate case below).
function allOverRunsThrowing(runs) {
  return (_name, _branch, r) => {
    if (r < 0 || r >= runs.length) throw new Error("no such run");
    return runs[r];
  };
}
function allOverRunsEmpty(runs) {
  return (_name, _branch, r) => (r < runs.length ? runs[r] : []);
}

test("single run: behaves like a plain .all(0, $runIndex) read", () => {
  const runs = [[{ json: { id: "a", action: "create" } }, { json: { id: "b", action: "create" } }]];
  const got = recoverConvergedRun(allOverRunsThrowing(runs), "Gate", 0, keepNonSkip);
  assert.deepEqual(got.map((it) => it.json.id), ["a", "b"]);
});

// Scenario (A) — the F5 repro itself: two runs, both actionable. A bare `.all()` (no
// run index) would return runs[1] (the last run) for BOTH reader invocations; this must
// return the run PAIRED to the reader's own $runIndex instead.
test("F5 repro: two actionable runs, no drop — each runIndex gets its OWN run, not the last one", () => {
  const runs = [
    [{ json: { id: "row-1", action: "create" } }, { json: { id: "row-4", action: "create" } }],
    [{ json: { id: "row-2", action: "create" } }, { json: { id: "row-3", action: "create" } }],
  ];
  const run0 = recoverConvergedRun(allOverRunsThrowing(runs), "Enrichment Gate", 0, keepNonSkip);
  const run1 = recoverConvergedRun(allOverRunsThrowing(runs), "Enrichment Gate", 1, keepNonSkip);
  assert.deepEqual(run0.map((it) => it.json.id), ["row-1", "row-4"]);
  assert.deepEqual(run1.map((it) => it.json.id), ["row-2", "row-3"]);
});

// Scenario (B) — the drift case that distinguishes this fix from bare
// `.all(0, $runIndex)`: three upstream runs, the MIDDLE one entirely skip (e.g. the "IF
// Name Searchable" false / unmatchable lane, or "IF Company Skip"'s true lane). That
// middle run never reaches the reader at all (the reader's own node only runs for
// waves with >=1 non-skip item), so the reader itself only runs TWICE. A naive
// `.all(0, $runIndex)` would pair the reader's run 1 with the upstream's run 1 — the
// all-skip run — losing the third wave entirely. recoverConvergedRun must instead pair
// the reader's run 1 with the upstream's run 2 (the second SURVIVING run).
test("drift case: an all-skip middle run must be skipped, not paired by raw run index", () => {
  const runs = [
    [{ json: { id: "row-1", action: "create" } }],                        // run 0: survives
    [{ json: { id: "row-x", action: "skip" } }, { json: { id: "row-y", action: "skip" } }], // run 1: all-skip, dropped
    [{ json: { id: "row-9", action: "enrich" } }],                        // run 2: survives
  ];
  // The reader itself only ever runs for surviving waves, so its own $runIndex is 0 and 1.
  const readerRun0 = recoverConvergedRun(allOverRunsThrowing(runs), "Company Gate", 0, keepNonSkip);
  const readerRun1 = recoverConvergedRun(allOverRunsThrowing(runs), "Company Gate", 1, keepNonSkip);
  assert.deepEqual(readerRun0.map((it) => it.json.id), ["row-1"]);
  assert.deepEqual(readerRun1.map((it) => it.json.id), ["row-9"], "must skip the dropped all-skip run, not return []");
});

test("a run that is only PARTIALLY skip still contributes its surviving items", () => {
  const runs = [
    [{ json: { id: "row-1", action: "create" } }, { json: { id: "row-skip", action: "skip" } }],
  ];
  const got = recoverConvergedRun(allOverRunsThrowing(runs), "Gate", 0, keepNonSkip);
  assert.deepEqual(got.map((it) => it.json.id), ["row-1"]);
});

test("a different keep predicate (zoom_needs_mint) selects the correct subset — ZoomInfo Cache Token's own class", () => {
  const runs = [
    [{ json: { id: "row-1", zoom_needs_mint: false } }],  // run 0: cached token, no mint -> dropped for THIS reader
    [{ json: { id: "row-2", zoom_needs_mint: true } }],   // run 1: needed a mint -> survives
    [{ json: { id: "row-3", zoom_needs_mint: false } }],  // run 2: cached again -> dropped
    [{ json: { id: "row-4", zoom_needs_mint: true } }],   // run 3: needed a mint -> survives
  ];
  const keepMint = (it) => it.json.zoom_needs_mint === true;
  const readerRun0 = recoverConvergedRun(allOverRunsThrowing(runs), "ZoomInfo Token Gate", 0, keepMint);
  const readerRun1 = recoverConvergedRun(allOverRunsThrowing(runs), "ZoomInfo Token Gate", 1, keepMint);
  assert.deepEqual(readerRun0.map((it) => it.json.id), ["row-2"]);
  assert.deepEqual(readerRun1.map((it) => it.json.id), ["row-4"]);
});

test("terminates whether 'past the end' throws or returns [] — both signals are honoured", () => {
  const runs = [[{ json: { id: "only", action: "create" } }]];
  // Requesting a runIndex beyond what exists must return [] (not throw, not hang),
  // regardless of which "past the end" signal the underlying .all() uses.
  assert.deepEqual(recoverConvergedRun(allOverRunsThrowing(runs), "Gate", 5, keepNonSkip), []);
  assert.deepEqual(recoverConvergedRun(allOverRunsEmpty(runs), "Gate", 5, keepNonSkip), []);
});

test("no matching run at all -> empty array, never throws out", () => {
  const got = recoverConvergedRun(allOverRunsThrowing([]), "Gate", 0, keepNonSkip);
  assert.deepEqual(got, []);
});
