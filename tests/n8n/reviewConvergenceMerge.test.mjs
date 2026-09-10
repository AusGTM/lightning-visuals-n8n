// tests/n8n/reviewConvergenceMerge.test.mjs
//
// Phase 70 Plan 03 Task 3 (D-70-01) — the walker-driven acceptance for the
// review-decision lane's three new convergence Merges ("Review Extract Record Merge",
// "Review Queue Rows Merge", "Build Review Response Merge") and their starved-lane
// sentinel network. Drives the COMMITTED n8n/wf_review_decision_cloud.json through
// tests/n8n/lib/walkWorkflow.mjs, asserting `starvedWithData` (quick task 260911-1z5's
// shared no-real-loss filter over `trace.stalled`) is empty and that each
// converged node runs exactly once over all its real inputs — never twice, never
// starved forever.
//
// This lane's response contract does NOT change (D-70-08): both responders
// ("Respond Review Decision", "Respond Review Queue") keep answering with a body, and
// this file asserts their shape is unaffected by the Merge insertion.
//
// NOTE: this replays the repo's OWN committed workflow jsCode/expressions via `new
// Function` — the same mechanism n8n's Code/IF nodes use at runtime — over trusted,
// in-repo JSON. No external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { walkWorkflow, loadWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_review_decision_cloud.json");

function load() {
  return loadWorkflow(WF_PATH);
}

function companyRecord(id, extra) {
  return { results: [{ id, properties: { domain: "acme.example", ...extra } }] };
}
function contactRecord(id, extra) {
  return { results: [{ id, properties: { email: "a@example.com", ...extra } }] };
}

// =============================================================================================
// Structural: Merge count matches classify_convergence's own verdict, never a magic number.
// =============================================================================================

test("the review-decision workflow has exactly 10 Merge nodes", () => {
  // Phase 70 Plan 04 (D-70-04) added 7 carry merges (one per HTTP hop needing its
  // pre-hop row re-attached) on top of Plan 03 Task 3's original 3 fan-in convergences.
  const wf = load();
  const merges = wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge");
  assert.deepEqual(
    merges.map((m) => m.name).sort(),
    [
      "Build Review Response Merge", "Review Extract Record Merge", "Review Queue Rows Merge",
      "Review Extract Record Carry Merge",
      "Review Decision Update Carry Merge", "Review Verify Fetch Carry Merge",
      "Review Contact Decision Update Carry Merge", "Review Contact Verify Fetch Carry Merge",
      "Review Queue Search Carry Merge", "Review Queue Contact Search Carry Merge",
    ].sort(),
  );
});

test("the review responder's inbound edge count is unchanged from before this task (2, both real terminals)", () => {
  const wf = load();
  const inbound = [];
  for (const [src, spec] of Object.entries(wf.connections)) {
    (spec.main || []).forEach((branch) => {
      for (const edge of branch || []) {
        if (edge.node === "Respond Review Decision") inbound.push(src);
      }
    });
  }
  assert.deepEqual(inbound, ["Build Review Response"]);
});

test("backend-status has 7 carry-merge nodes (Phase 70 Plan 04, D-70-04)", () => {
  // Was zero at Plan 03 Task 3 time; Plan 04 threaded a carry merge across every HTTP
  // hop in this workflow's two straight-line chains (credit probes, HubSpot counts).
  const wf = loadWorkflow(path.join(ROOT, "n8n", "wf_backend_status_cloud.json"));
  const merges = wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge");
  assert.equal(merges.length, 7);
});

// =============================================================================================
// Behavioural: each of the 5 request shapes named in the plan's <behavior> block.
// =============================================================================================

test("Review Extract Record + Build Review Response run once each on a dry-run companies decision — no stall, one response", () => {
  const wf = load();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Review Decision Webhook",
    triggerItems: [{ body: {
      object_type: "companies", record_id: "123", decision: "approve", dry_run: true,
    } }],
    httpStubs: { "Review Fetch By Id": [companyRecord("123")] },
  });
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(trace.respondSuppressed.length, 0);
  assert.ok(trace.respond);
  assert.equal(nodeItems(runData, "Review Extract Record").length, 1);
  assert.equal(nodeItems(runData, "Build Review Response").length, 1);
});

test("Review Extract Record + Build Review Response run once each on a contacts decision — no stall, one response", () => {
  const wf = load();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Review Decision Webhook",
    triggerItems: [{ body: {
      object_type: "contacts", record_id: "456", decision: "reject", reason: "no fit", dry_run: false,
    } }],
    httpStubs: {
      "Review Contact Fetch By Id": [contactRecord("456")],
      "Review Contact Verify Fetch": [contactRecord("456", { lv_enrichment_review_reason: "no fit" })],
    },
  });
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(trace.respondSuppressed.length, 0);
  assert.ok(trace.respond);
  assert.equal(nodeItems(runData, "Review Extract Record").length, 1);
  assert.equal(nodeItems(runData, "Build Review Response").length, 1);
});

test("Review Queue Rows runs once on a queue request with rows on ONLY the companies branch — the single-branch case named in the plan", () => {
  const wf = load();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Review Queue Webhook",
    triggerItems: [{ body: { object_type: "companies", limit: 10 } }],
    httpStubs: { "Review Queue Search": [{ results: [{ id: "1", properties: {} }], total: 1 }] },
  });
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(trace.respondSuppressed.length, 0);
  assert.ok(trace.respond);
  const rows = nodeItems(runData, "Review Queue Rows");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].object_type, "companies");
  assert.equal(rows[0].total, 1);
});

test("Review Queue Rows runs once on a queue request with rows on ONLY the contacts branch — no stall", () => {
  const wf = load();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Review Queue Webhook",
    triggerItems: [{ body: { object_type: "contacts", limit: 10 } }],
    httpStubs: { "Review Queue Contact Search": [{ results: [{ id: "2", properties: {} }], total: 1 }] },
  });
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(trace.respondSuppressed.length, 0);
  assert.ok(trace.respond);
  const rows = nodeItems(runData, "Review Queue Rows");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].object_type, "contacts");
});

test("Build Review Response picks the real verify-fetch envelope over a starved-lane marker, regardless of merge item order", () => {
  // Unit-level, not walker-driven: driving the FULL business chain to a genuine
  // armed companies write (needs_review flags, a real candidate, an armed write
  // gate) is `reviewDecisionEndpoint.test.mjs`'s job, not this convergence file's.
  // What THIS test isolates is the exact defect the plan's own action text names:
  // `$input.first()` used to grab WHATEVER happened to land at merge input index 0,
  // which could silently be a sentinel marker (`{}`) instead of the real verify-fetch
  // envelope depending on splice order. Drives the repo's OWN committed jsCode via
  // `new Function` (the same mechanism n8n's Code node uses) with the marker BEFORE
  // the real item — the exact ordering that would have broken `$input.first()`.
  //
  // Phase 70 Plan 04 (D-70-04): "Build Review Response" no longer reads `$('Build
  // Review Decision')` — "Review Verify Fetch Carry Merge" re-attaches those fields
  // onto the real verify envelope BEFORE this node runs, so the real item here already
  // carries both. The starved-lane marker stays a bare `{}`, exactly as a real
  // sentinel would (it never crosses a carry merge).
  const wf = load();
  const node = wf.nodes.find((n) => n.name === "Build Review Response");
  assert.ok(node, "Build Review Response present in the built workflow");

  const decision = { outcome: "applied", message: "applied", would_write: { lv_org_type: "content_producer" }, dry_run: false };
  const $input = { all: () => [
    { json: {} },  // the starved-lane marker, deliberately FIRST
    { json: { ...decision, results: [{ id: "123", properties: { lv_org_type: "content_producer" } }] } },
  ] };
  const fn = new Function("$input", `"use strict";\n${node.parameters.jsCode}`);
  const [out] = fn($input);

  assert.deepEqual(out.json.verified_properties, { lv_org_type: "content_producer" });
  assert.equal(out.json.verified, true);
});

test("the review-decision response body is byte-shape-identical to the pre-merge contract for a dry run", () => {
  const wf = load();
  const { trace } = walkWorkflow(wf, {
    triggerNode: "Review Decision Webhook",
    triggerItems: [{ body: {
      object_type: "companies", record_id: "123", decision: "approve", dry_run: true,
    } }],
    httpStubs: { "Review Fetch By Id": [companyRecord("123")] },
  });
  const [body] = trace.respond.items;
  assert.deepEqual(
    Object.keys(body).sort(),
    ["message", "outcome", "verified", "verified_properties", "would_write"].sort(),
  );
  assert.equal(body.verified_properties, null);
  assert.equal(body.verified, null);
});

test("the review-queue response body is byte-shape-identical to the pre-merge contract", () => {
  const wf = load();
  const { trace } = walkWorkflow(wf, {
    triggerNode: "Review Queue Webhook",
    triggerItems: [{ body: { object_type: "companies", limit: 10 } }],
    httpStubs: { "Review Queue Search": [{ results: [], total: 0 }] },
  });
  const [body] = trace.respond.items;
  assert.deepEqual(
    Object.keys(body).sort(),
    ["object_type", "returned", "rows", "search_ok", "total"].sort(),
  );
});
