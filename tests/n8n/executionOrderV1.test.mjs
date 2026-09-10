// executionOrderV1.test.mjs — D-70-28 / G-70-6 (blocker).
//
// Gate 8 (disarmed executions 12349-12353) put four Gate-8 symptoms on the record at
// once: `HubSpot Update` ran with no real input item and PATCHed an empty id; `IF List
// Expanded` emitted a refusal on an empty list lane; gated sentinels delivered markers
// on inputs whose sentinel emitted zero items; `Enrichment Gate Merge` fired twice and
// dropped every real row. One engine rule explains all four: with `settings
// .executionOrder` absent (n8n's legacy default), `addNodeToBeExecuted`'s `addEmptyItem`
// branch (`packages/core/src/execution-engine/workflow-execute.ts`) pushes every node on
// an empty branch onto the stack with ONE `{ json: {} }` item so a waiting Merge can
// finish — nobody chose legacy, it was inherited on every live body throughout.
//
// D-70-28 rules the flip: every committed `n8n/wf_*.json` must carry
// `settings.executionOrder === "v1"`, decided ONCE in the generator and never per
// workflow. This file is the RED-first proof (Task 1) — it must fail before Task 2
// touches the generator, and pass after with zero changes to this file.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const N8N_DIR = path.join(ROOT, "n8n");
const BUILDER_PATH = path.join(ROOT, "scripts", "build_cloud_workflows.py");

// Discovered, not hard-coded — a ninth workflow added later is caught automatically.
const WORKFLOW_FILES = fs.readdirSync(N8N_DIR)
  .filter((f) => f.startsWith("wf_") && f.endsWith(".json"))
  .sort();

test("every committed workflow runs on n8n's v1 execution order", () => {
  assert.ok(WORKFLOW_FILES.length > 0, "no n8n/wf_*.json files found — discovery is broken");
  const failures = [];
  for (const file of WORKFLOW_FILES) {
    const wf = JSON.parse(fs.readFileSync(path.join(N8N_DIR, file), "utf8"));
    const found = wf.settings && wf.settings.executionOrder;
    if (found !== "v1") {
      failures.push(`${file}: settings.executionOrder = ${JSON.stringify(found)}, want "v1"`);
    }
  }
  assert.deepEqual(failures, [], `D-70-28 violated:\n${failures.join("\n")}`);
});

test("the builder decides the execution order once, not per workflow", () => {
  const text = fs.readFileSync(BUILDER_PATH, "utf8");
  const lines = text.split("\n");

  // The constant is defined exactly once, at column zero.
  const definitions = lines.filter((l) => l.startsWith("WORKFLOW_SETTINGS = "));
  assert.equal(
    definitions.length, 1,
    `expected exactly one top-level "WORKFLOW_SETTINGS = " definition, found ${definitions.length}`
  );

  // The emission IDIOM — not the bare identifier, which the constant's own comment and
  // the generation-time assertion both legitimately mention — occurs exactly once per
  // generated body (eight committed workflows).
  const idiomMatches = text.match(/dict\(WORKFLOW_SETTINGS\)/g) || [];
  assert.equal(
    idiomMatches.length, 8,
    `expected the emission idiom "dict(WORKFLOW_SETTINGS)" exactly 8 times (one per ` +
    `generated body), found ${idiomMatches.length} — D-70-28 requires no per-workflow ` +
    `settings decision anywhere in the builder`
  );
});
