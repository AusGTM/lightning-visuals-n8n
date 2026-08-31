// tests/n8n/ingestResponseRowId.test.mjs
//
// 57-02 Task 4 — AFTER-01's join key. `Build Ingest Response`'s return object is an
// EXPLICIT field list: a field not named there dies at this exact boundary before
// `written_records.classify_item` (which reads `row_id` off the response item, added
// 57-02 Task 2) ever sees it. Pins that `row_id` is now named, and that every field
// the node emitted before this change is STILL named — a field list is exactly the
// shape that loses things silently.
//
// Same `new Function` harness as pairPipelineAssociationFlow.test.mjs — this repo's
// OWN committed jsCode, not a hand-transcribed copy.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");
const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};
const jsCode = node("Build Ingest Response").parameters.jsCode;

function runCode(seedItems, nodeOutputs = {}) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const $ = (name) => {
    if (!(name in nodeOutputs)) throw new Error(`no node named ${name}`);
    return { all: () => nodeOutputs[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

test("Build Ingest Response's field list names row_id, and every field it named before this task", () => {
  // "association" is a shorthand property (`{ ..., association, ... }`), never
  // written as `association:` in this node's source — matched by its own field name
  // as a whole word instead of the `field:` idiom every other field uses.
  const preExisting = [
    "action", "outcome", "contact_id", "hs_object_id", "email", "company_id",
    "company_match", "association", "reason", "email_status",
  ];
  const returnBlock = jsCode.slice(jsCode.indexOf("return { json: {"));
  for (const field of preExisting) {
    const re = new RegExp(`\\b${field}\\b`);
    assert.ok(re.test(returnBlock), `field list still names ${field}`);
  }
  assert.ok(jsCode.includes("row_id:"), "field list now names row_id (AFTER-01's join key)");
});

test("a row carrying row_id echoes it through unchanged", () => {
  const decided = [{ action: "review", hs_object_id: null, row_id: "row-42" }];
  const report = runCode([], {
    "Decide Action": decided,
    "Build Association Request": [],
    "HubSpot Associate Company Write Gate": [],
  });

  assert.equal(report.length, 1);
  assert.equal(report[0].row_id, "row-42");
});

test("a row with no row_id (the pair pipeline's final ingest leg, REVIEW-57-H7) reports null, never crashes", () => {
  const decided = [{ action: "update", hs_object_id: "123" }];
  const report = runCode([], {
    "Decide Action": decided,
    "Build Association Request": [],
    "HubSpot Associate Company Write Gate": [],
  });

  assert.equal(report.length, 1);
  assert.equal(report[0].row_id, null);
});

test("a batch mixing a row_id-carrying row and a row_id-less row reports both independently", () => {
  const decided = [
    { action: "enrich", hs_object_id: "1", row_id: "r1" },
    { action: "create", hs_object_id: null },
  ];
  const report = runCode([], {
    "Decide Action": decided,
    "Build Association Request": [],
    "HubSpot Associate Company Write Gate": [],
  });

  assert.equal(report.length, 2);
  assert.equal(report[0].row_id, "r1");
  assert.equal(report[1].row_id, null);
});
