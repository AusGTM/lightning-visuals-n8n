// tests/n8n/v1RuntimeRecordings.test.mjs
//
// Phase 70 Gate 11 (2026-09-10): the first runtime observation of executionOrder "v1" on
// this instance. These are READER assertions over the frozen runData of executions
// 12354-12358 (`fixtures/frozen/exec_1235{4..8}.runData.json`) — the engine's recorded
// outcome, never a walk. Each assertion pins one row of CLAUDE.md §13.0.3 tagged
// `[observed live]` against these execution ids, so the fixtures cannot drift from the
// claims made about them. No graph is walked here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const FROZEN = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "frozen");
const load = (id) => JSON.parse(fs.readFileSync(path.join(FROZEN, `exec_${id}.runData.json`), "utf8"));
const items = (run) => (run.data?.main?.[0] ?? []).length;

const ENRICHMENT = [12354, 12355, 12356];
const INGEST = [12357, 12358];

test("frozen recordings carry no live secret — webhook request headers are redacted", () => {
  // The Webhook Trigger's runData item carries the caller's request headers verbatim,
  // including x-enrichment-secret (CLAUDE.md §18.1). Every recording frozen from a live
  // execution must have them redacted before it is committed.
  for (const id of [...ENRICHMENT, ...INGEST]) {
    const raw = fs.readFileSync(path.join(FROZEN, `exec_${id}.runData.json`), "utf8");
    for (const m of raw.matchAll(/"x-enrichment-secret":\s*"([^"]*)"/g)) {
      assert.equal(m[1], "<redacted>", `${id}: x-enrichment-secret must be redacted`);
    }
    assert.doesNotMatch(raw, /"x-real-ip":\s*"(?!<redacted>)/, `${id}: x-real-ip must be redacted`);
  }
});

test("Gate 11: every recording ran on executionOrder v1 and settled success", () => {
  for (const id of [...ENRICHMENT, ...INGEST]) {
    const e = load(id);
    assert.equal(e.execution_id, String(id));
    assert.equal(e.settings.executionOrder, "v1");
    assert.equal(e.status, "success");
  }
});

test("Gate 11: none of Gate 8's legacy symptoms — a node on an empty branch does not run under v1", () => {
  for (const id of [...ENRICHMENT, ...INGEST]) {
    const rd = load(id).runData;
    assert.equal(rd["HubSpot Update"], undefined, `${id}: HubSpot Update must not run disarmed`);
    assert.equal(rd["IF List Expanded"], undefined, `${id}: IF List Expanded must not run on an empty list lane`);
    assert.equal(rd["Apply Contact Judge Verdict"], undefined, `${id}: judge verdict must not run on a marker`);
  }
  for (const id of ENRICHMENT) {
    const rd = load(id).runData;
    assert.equal(rd["Enrichment Gate Merge"].length, 1, `${id}: Enrichment Gate Merge fires once`);
    assert.equal(items(rd["Enrichment Gate Merge"][0]), 6, `${id}: 4 markers + 2 real rows`);
    assert.equal(items(rd["Build Response"][0]), 2, `${id}: both real rows reach Build Response`);
  }
});

test("Gate 11: under v1 a Merge can fire twice — Decide Company Action Merge, marker-only, consumer 0 items each run", () => {
  for (const id of ENRICHMENT) {
    const rd = load(id).runData;
    const merge = rd["Decide Company Action Merge"];
    assert.equal(merge.length, 2, `${id}: Merge fired twice`);
    assert.deepEqual(merge.map(items), [2, 1]);
    assert.deepEqual(merge[0].source.map((s) => s.previousNode), ["Companies Absent Sentinel Gate", "Companies Absent Sentinel Gate"]);
    assert.equal(merge[1].source[0].previousNode, "Recompute Not Requested Sentinel Gate");
    assert.equal(merge[1].source[1], null, `${id}: run 1 input 1 had NO delivery — the end-of-run drain fired on one input`);
    const decide = rd["Decide Company Action"];
    assert.deepEqual(decide.map(items), [0, 0], `${id}: consumer ran twice, filtered the markers both times`);
    assert.equal(rd["IF Company Create"], undefined, `${id}: nothing downstream of a 0-item run`);
  }
});

test("Gate 11: under v1 a node that RAN and emitted zero items is NOT a delivery to a Merge input", () => {
  for (const id of ENRICHMENT) {
    const rd = load(id).runData;
    assert.equal(items(rd["Merge Company"][0]), 0, `${id}: Merge Company ran with 0 items`);
    const sources = rd["Decide Company Action Merge"].flatMap((r) => r.source.map((s) => s?.previousNode ?? null));
    assert.ok(!sources.includes("Merge Company"), `${id}: Merge Company's [] never appeared as a source on its declared input`);
  }
});
