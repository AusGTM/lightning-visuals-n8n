// tests/n8n/walkerEngineFidelityV1.test.mjs
//
// Quick task 260911-0tz — v1 REPRODUCTIONS, the inverse of walkerEngineFidelity.test.mjs's
// three RECORDED LEGACY divergences. Every case here walks the frozen v1 graph copy
// (`fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json`, a byte copy of the committed
// `n8n/wf_enrichment_cloud.json` at commit `ec102a4`, `settings.executionOrder: "v1"`) with
// no `allowLegacy` escape — this file is what proves the walker's v1 branch reproduces what
// the live engine ACTUALLY DID on executions 12354, 12355 and 12356 (Gate 11, 2026-09-10),
// frozen at `fixtures/frozen/exec_1235{4,5,6}.runData.json` and first read (no walk) by
// `tests/n8n/v1RuntimeRecordings.test.mjs`.
//
// D-70-19: the walker moves toward the engine. Both `triggerItems` and `httpStubs` below are
// taken from the recording's OWN runData, never hand-written, so this fixture cannot drift
// from the run it claims to reproduce.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FROZEN = path.join(HERE, "fixtures", "frozen");
const FROZEN_V1_GRAPH = path.join(FROZEN, "wf_enrichment_cloud.v1.2026-09-10.json");

const HTTP_TYPES = new Set(["n8n-nodes-base.httpRequest", "n8n-nodes-base.hubspot"]);

function loadRecording(id) {
  return JSON.parse(fs.readFileSync(path.join(FROZEN, `exec_${id}.runData.json`), "utf8"));
}

// httpStubs sourced from the recording's own runData — the SAME httpStubs mechanism
// enrichmentMixedBatch.test.mjs uses, fed by the engine's recorded responses instead of by
// hand. Returns run k's items on call k; falls back to the last run once calls outrun
// recorded runs, and REFUSES that fallback silently for a node that ran more than once
// live (a genuine misalignment risk) rather than a node that only ever ran once.
function httpStubsFromRecording(wf, rd) {
  const stubs = {};
  for (const n of wf.nodes) {
    if (!HTTP_TYPES.has(n.type) || !rd[n.name]) continue;
    const runs = rd[n.name];
    let calls = 0;
    stubs[n.name] = () => {
      const k = calls;
      calls += 1;
      if (k >= runs.length) {
        if (runs.length > 1) {
          throw new Error(
            `${n.name}: call ${k} exceeds the ${runs.length} recorded run(s) — the ` +
            `run-0-only fallback would misalign a multi-run HTTP node, so this stub ` +
            `refuses rather than silently reusing the last run`);
        }
        return runs[runs.length - 1].data.main[0].map((it) => it.json);
      }
      return runs[k].data.main[0].map((it) => it.json);
    };
  }
  return stubs;
}

function triggerItemsFromRecording(rd) {
  return [{ body: rd["Webhook Trigger"][0].data.main[0][0].json.body }];
}

function walkRecording(id) {
  const wf = JSON.parse(fs.readFileSync(FROZEN_V1_GRAPH, "utf8"));
  const recording = loadRecording(id);
  const rd = recording.runData;
  return walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    // No allowLegacy — the frozen copy IS v1, and reproducing 12354/12355/12356 on
    // anything else would not be a reproduction of what the engine ran.
    triggerItems: triggerItemsFromRecording(rd),
    httpStubs: httpStubsFromRecording(wf, rd),
  });
}

const EXECUTIONS = [12354, 12355, 12356];

for (const id of EXECUTIONS) {
  test(`execution ${id} (v1, Gate 11): the walker reproduces the engine's Decide Company Action Merge double-fire and Merge Company's non-delivery`, () => {
    const { runData, trace } = walkRecording(id);

    // Raw runData counts FIRST (D-70-19 Step 2: a clean assertion failure, not a TypeError
    // on an undefined `runs`, is what the pre-fix RED must look like).
    assert.equal(runData["Decide Company Action Merge"].length, 2,
      `${id}: Decide Company Action Merge must fire twice, exactly as the engine did`);
    assert.deepEqual(runData["Decide Company Action Merge"].map((r) => r.length), [2, 1],
      `${id}: run 0 carries 2 marker items (both inputs from the same sentinel gate), ` +
      `run 1 carries 1 (the end-of-run drain firing on a single arrived input)`);
    assert.equal(trace.merges["Decide Company Action Merge"].runs[1].sources[1], undefined,
      `${id}: run 1 input 1 must be UNFILLED — the drain fired on input 0 alone`);

    assert.equal(runData["Decide Company Action"].length, 2,
      `${id}: Decide Company Action ran twice, once per Merge run`);
    assert.deepEqual(runData["Decide Company Action"].map((r) => r.length), [0, 0],
      `${id}: both runs filtered to zero items — markers only`);

    assert.equal(runData["Merge Company"][0].length, 0,
      `${id}: Merge Company ran and emitted zero items`);
    const decideMergeSources = trace.merges["Decide Company Action Merge"].runs
      .flatMap((r) => Object.values(r.sources));
    assert.ok(!decideMergeSources.includes("Merge Company"),
      `${id}: Merge Company's zero-item output must never appear as a source of Decide ` +
      `Company Action Merge — under v1 a zero-item output makes no delivery`);

    assert.equal(runData["Enrichment Gate Merge"].length, 1,
      `${id}: Enrichment Gate Merge fires exactly once`);
    assert.equal(runData["Enrichment Gate Merge"][0].length, 6,
      `${id}: 4 markers + 2 real rows`);

    // NOT nodeItems(...).length === 2 — that also passes on a 1+1 run split, the exact
    // collapse shape this instrument exists to see.
    assert.equal(runData["Build Response"].length, 1,
      `${id}: Build Response must run exactly once`);
    assert.equal(runData["Build Response"][0].length, 2,
      `${id}: both real rows reach Build Response in its single run`);

    assert.equal(runData["HubSpot Update"], undefined,
      `${id}: HubSpot Update must not run — disarmed propose-mode batch`);
  });
}
