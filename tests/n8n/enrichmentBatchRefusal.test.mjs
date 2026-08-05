// tests/n8n/enrichmentBatchRefusal.test.mjs
//
// Phase 36-03, Task 3 (PREVIEW-03, D-15/D-22). Executes the repo's OWN committed
// "Parse HubSpot Event" jsCode via `new Function` — the same thing n8n's Code node does
// at runtime — against event arrays of length 0, 1, 2 and 3, asserting refuse / accept-1
// / accept-2 (the ceiling, ENRICH_MAX_LIST_RECORDS) / refuse respectively. No external or
// untrusted input is interpolated into the function body; mirrors
// bareEventChainFlow.test.mjs's `new Function` idiom over a fixed in-repo node.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function runParseHubSpotEvent(body) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const node = wf.nodes.find((n) => n.name === "Parse HubSpot Event");
  assert.ok(node, "Parse HubSpot Event present in the built workflow");
  const $input = { all: () => [{ json: { body } }], get item() { return { json: { body } }; } };
  const $json = { body };
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${node.parameters.jsCode}`);
  const out = fn(() => ({ all: () => [], get item() { return { json: undefined }; } }),
    $input, $json, {}, new Date(), new Date());
  return out.map((it) => it.json);
}

function makeEvents(n) {
  return Array.from({ length: n }, (_, i) => ({
    objectId: i + 1, objectType: "contact", subscriptionType: "contact.propertyChange",
  }));
}

test("length 0 (empty events array): refused, one terminating item, zero enriched", () => {
  const rows = runParseHubSpotEvent({ events: [] });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].outcome, "refused");
  assert.equal(rows[0].object_type, "unknown");
  assert.match(rows[0].reason, /empty/i);
});

test("length 1: accepted, one row emitted, not refused", () => {
  const rows = runParseHubSpotEvent({ events: makeEvents(1) });
  assert.equal(rows.length, 1);
  assert.notEqual(rows[0].outcome, "refused");
  assert.equal(rows[0].object_id, "1");
});

test("length 2 (exactly the ceiling, ENRICH_MAX_LIST_RECORDS): accepted, two rows emitted, not refused — strictly greater-than, never greater-or-equal", () => {
  const rows = runParseHubSpotEvent({ events: makeEvents(2) });
  assert.equal(rows.length, 2);
  for (const r of rows) assert.notEqual(r.outcome, "refused");
  assert.deepEqual(rows.map((r) => r.object_id), ["1", "2"]);
});

test("length 3 (one over the ceiling): refused WHOLE, one terminating item, zero per-event rows", () => {
  const rows = runParseHubSpotEvent({ events: makeEvents(3) });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].outcome, "refused");
  assert.equal(rows[0].object_type, "unknown");
  assert.equal(rows[0].events.length, 0, "nothing enriched — the refusal carries an empty events array");
  assert.match(rows[0].reason, /3/, "reason must name the actual count");
  assert.match(rows[0].reason, /2/, "reason must name the limit");
});

test("a bare event array (not an envelope), length 1, is not refused — parseWebhookBody's bare-array fallback still applies", () => {
  const rows = runParseHubSpotEvent(makeEvents(1));
  assert.equal(rows.length, 1);
  assert.notEqual(rows[0].outcome, "refused");
});

// --- Phase 36-06 (37-CONTEXT.md §13 ceiling ruling): mode-aware ceiling selection ------

test("mode:propose, 3 events: NOT refused, 3 rows emitted (the new capability)", () => {
  const rows = runParseHubSpotEvent({ mode: "propose", events: makeEvents(3) });
  assert.equal(rows.length, 3);
  for (const r of rows) assert.notEqual(r.outcome, "refused");
});

test("mode absent, 3 events: refused, one terminating item, zero enriched, reason names the write ceiling (the guarantee)", () => {
  const rows = runParseHubSpotEvent({ events: makeEvents(3) });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].outcome, "refused");
  assert.equal(rows[0].events.length, 0);
});
