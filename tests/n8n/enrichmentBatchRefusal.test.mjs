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
import { walkWorkflow, loadWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

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

// --- Task 2: the boundary matrix — 20 vs 21, 2 vs 3, empty in both modes --------------

test("mode:propose, exactly 20 events (the propose ceiling): accepted, 20 rows, none refused", () => {
  const rows = runParseHubSpotEvent({ mode: "propose", events: makeEvents(20) });
  assert.equal(rows.length, 20);
  for (const r of rows) assert.notEqual(r.outcome, "refused");
});

test("mode:propose, 21 events (one over): refused whole, one item, empty events, reason names 21 and 20", () => {
  const rows = runParseHubSpotEvent({ mode: "propose", events: makeEvents(21) });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].outcome, "refused");
  assert.equal(rows[0].events.length, 0);
  assert.match(rows[0].reason, /21/, "reason must name the actual count");
  assert.match(rows[0].reason, /the limit is 20 record/, "reason must quote its OWN (propose) ceiling, never the write ceiling");
});

test("mode:write (explicit), exactly 2 events: accepted, 2 rows — old ceiling still holds when mode is stated", () => {
  const rows = runParseHubSpotEvent({ mode: "write", events: makeEvents(2) });
  assert.equal(rows.length, 2);
  for (const r of rows) assert.notEqual(r.outcome, "refused");
});

test("mode:write (explicit), 3 events: refused, reason names the write ceiling (2)", () => {
  const rows = runParseHubSpotEvent({ mode: "write", events: makeEvents(3) });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].outcome, "refused");
  assert.match(rows[0].reason, /the limit is 2 record/, "reason must quote the write ceiling, never the propose ceiling");
});

test("mode:propose, empty events array: refused with the empty-array reason, not swallowed by the size branch", () => {
  const rows = runParseHubSpotEvent({ mode: "propose", events: [] });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].outcome, "refused");
  assert.match(rows[0].reason, /empty/i);
});

test("a typo mode (\"proprose\"), 3 events: accepted — unrecognised mode gets the return-only ceiling, never the writer's", () => {
  const rows = runParseHubSpotEvent({ mode: "proprose", events: makeEvents(3) });
  assert.equal(rows.length, 3);
  for (const r of rows) assert.notEqual(r.outcome, "refused");
});

// =============================================================================================
// Phase 70 Plan 03 Task 2 (D-70-07) — walker-driven: each of the four body-borne refusal/
// status shapes now reaches "Build Response" as a ROW instead of the HTTP body, while
// "Respond to Webhook" still fires exactly once with the ack shape
// `{run_id, accepted, row_ids}`. Drives the COMMITTED workflow through
// tests/n8n/lib/walkWorkflow.mjs — the same interpreter enrichmentConvergenceMerge.test.mjs
// uses — never a live n8n/HubSpot call.
// =============================================================================================

function loadWf() {
  return loadWorkflow(WF_PATH);
}

function assertAckOnlyResponse(trace, { runId = null } = {}) {
  assert.deepEqual(trace.stalled, []);
  assert.equal(trace.respondSuppressed.length, 0, "the responder must fire exactly once");
  assert.ok(trace.respond, "the responder must fire at all");
  const [ack] = trace.respond.items;
  assert.equal(ack.accepted, true);
  assert.equal(ack.run_id, runId);
  assert.ok(Array.isArray(ack.row_ids));
}

test("unsupported object type: the refusal reaches Build Response as a row, and the responder still answers with the ack only", () => {
  const wf = loadWf();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { run_id: "case-unsupported", events: [
      { objectId: "1", objectType: "deal", row_id: "row-1" },
    ] } }],
    httpStubs: {},
  });
  assertAckOnlyResponse(trace, { runId: "case-unsupported" });
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].object_type, "unsupported");
  assert.equal(rows[0].row_id, "row-1");
});

test("recompute_refused: a recompute request resolving to no existing company reaches Build Response as a row, and the responder still answers with the ack only", () => {
  const wf = loadWf();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { run_id: "case-recompute", events: [
      { objectId: "1", objectType: "company", domain: "nowhere.example", recompute: true, row_id: "row-1" },
    ] } }],
    httpStubs: {
      "HubSpot Company Search": [{ results: [] }],
      "HubSpot Company Name Search": [{ results: [] }],
    },
  });
  assertAckOnlyResponse(trace, { runId: "case-recompute" });
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].action, "recompute_refused");
  assert.ok(rows[0].reason, "the top-level reason hoist (D-70-07) must be populated");
});

test("list-expansion refusal: the reason reaches Build Response as a row, and the responder still answers with the ack only", () => {
  const wf = loadWf();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { list: { objectType: "company", name: "Some List" } } }],
    httpStubs: {
      "HubSpot List By Name": [{ objectTypeId: "0-2", listId: "1" }],
      "HubSpot List Memberships": [{ results: [] }],
    },
  });
  assertAckOnlyResponse(trace, { runId: null });
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].action, "list_expansion_refused");
  assert.match(rows[0].reason, /no members/i);
});

test("scale_up: the dispatch confirmation reaches Build Response as a row (not the body), and the responder still answers with the ack only", () => {
  const wf = loadWf();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { scale_up: true, run_id: "case-scale-up", events: [
      { objectId: "1", objectType: "company", row_id: "row-1" },
    ] } }],
    httpStubs: {},
  });
  assertAckOnlyResponse(trace, { runId: "case-scale-up" });
  assert.deepEqual(trace.respond.items[0].row_ids, ["row-1"]);
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].action, "scale_up_dispatched");
  assert.equal(rows[0].row_id, "row-1");
});
