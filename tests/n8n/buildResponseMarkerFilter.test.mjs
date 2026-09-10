// tests/n8n/buildResponseMarkerFilter.test.mjs
//
// Phase 70 Plan 14 (gap G-70-5, D-70-25). Gate 5's disarmed `enrichment_2x2` send
// recovered EIGHT rows for FOUR input rows (70-RUNTIME-VERDICT.json, executions
// 12209/12210): the extra four were marker items — an item carrying none of a row's
// identity keys — that a "Credits Broadcast" combineAll splice had already made
// non-empty (stamping shared fields like `remaining_credits` onto every item on its
// input, phantom marker included) before "Build Response"'s existing NEGATIVE filter
// (`Object.keys(it.json || {}).length > 0`, plus the sentinel's own reserved key) ever
// saw them. A non-empty marker sails through that filter and comes back with a full
// outcome projection stamped on it — indistinguishable from a real row to a caller
// reading runData.
//
// This file pins the fix with the exact key sets 70-RUNTIME-VERDICT.json recorded, run
// through the COMMITTED node's own jsCode via the walker's exported single-node runner
// (`runNode`) — never a whole walk, because the walker cannot reproduce the leak (it was
// never isolated as a walkable mechanism; see walkerEngineFidelity.test.mjs's own
// divergence case for the sibling defect this same UAT round surfaced).
//
// RED-first discipline (recorded here, not just claimed): before the generator carried
// `hasRowIdentity`, running this file against the then-committed JSON returned 2 items
// from the first case (the marker survived) and the first item carried neither `action`
// nor `row_id` — see 70-14-SUMMARY.md's own RED transcript for the exact assertion
// failure this file's Task 1 commit fixes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { runNode } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function jsCodeNode(wfRelPath, nodeName) {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, wfRelPath), "utf8"));
  const node = wf.nodes.find((n) => n.name === nodeName);
  assert.ok(node, `${nodeName} present in ${wfRelPath}`);
  assert.equal(node.type, "n8n-nodes-base.code");
  return node;
}

// The Gate 5 verdict's FIRST recovered shape (70-RUNTIME-VERDICT.json,
// sends[0].recovered_shapes[0]): "candidate_count, contactability, contactability_fields,
// judge_adjudicated_fields, material_conflicts, num_associated_contacts, object_type,
// outcome_contract_version, provider_agreement, reason, remaining_credits" — ten of those
// eleven keys are stamped by "Build Response"'s OWN projection on every row it emits, real
// or marker; the only key the marker itself carried going IN was `object_type`. So "an
// item carrying only an object type" (the plan's own description of this shape) is the
// correct fixture for the INPUT side, not the full eleven-key OUTPUT shape the verdict
// recorded — feeding it through the unmodified projection reproduces the recorded output
// key set exactly.
const MARKER_OBJECT_TYPE_ONLY = { object_type: "unsupported" };

// The Gate 5 verdict's THIRD recovered shape (sends[0].recovered_shapes[4], 23 keys —
// event_id/event_type/fan_depth/mode/object_id/object_type/occurred_at/property_name/
// provider_enabled/providers_requested/recompute/run_id/scale_up plus the ten keys
// "Build Response" itself always stamps, outcome_contract_version included): none of them
// a row_id, action, outcome or HubSpot object id. `object_id: null` is the load-bearing
// value, and it is not invented — the same execution round's runaway self-dispatch
// (70-UAT.md § Test 4, `observed:`) describes each child's event as `object_type:
// "unknown"`, `run_id: null`, entering with a bare item carrying no objectId, and
// `exec_12316.runData.json`'s "Parse HubSpot Event" entry (a sibling child of the same
// loop) records `out0_first_item_json.object_id: null` verbatim. A genuinely unsupported
// webhook event carries a REAL (non-null) object id and must survive this filter; this
// marker's is null because it never carried one to begin with.
const MARKER_RAW_PARSED_EVENT = {
  event_id: "sub:undefined:undefined",
  object_id: null,
  object_type: "unknown",
  property_name: null,
  event_type: null,
  occurred_at: "2026-09-10T07:08:55.987Z",
  provider_enabled: { lusha: false, apollo: false, zoominfo: false },
  providers_requested: [],
  mode: null,
  recompute: false,
  run_id: null,
  scale_up: false,
  fan_depth: 0,
};

// An ordinary row — carries an action and a row id, exactly like every predicted shape in
// 70-RUNTIME-VERDICT.json's `sends[0].predicted_shapes`.
const ORDINARY_ROW = { row_id: "e-li-a", action: "proposed", object_type: "contacts" };

// A row identified ONLY by its row id, no action yet (mid-pipeline shape) — must also
// survive.
const ROW_ID_ONLY = { row_id: "e-li-b" };

// A request-level refusal — "Parse HubSpot Event"'s own shape for an oversize/empty
// events array or the (now-retired) scale-up refusal: `outcome: "refused"`, no action, no
// row id, no object id (CLAUDE.md's ENRICH_PARSE_EVENT_CLOUD refusal-as-terminating-item
// idiom; plan 70-13 kept this shape for the list-expansion/oversize refusals). This is the
// row D-70-14/D-70-13's refusal-survival case depends on — the acceptance criterion is
// explicit that it must keep reaching the caller.
const REFUSAL_ROW = {
  outcome: "refused",
  reason: "Request carries an empty events array — nothing to enrich.",
  events: [],
  object_type: "unknown",
};

function runBuildResponse(items) {
  const node = jsCodeNode("n8n/wf_enrichment_cloud.json", "Build Response");
  const { outputs } = runNode(node, items, {});
  return outputs[0];
}

test("Build Response: an object-type-only marker (Gate 5's first recovered shape) is dropped; an ordinary action+row_id row survives untouched", () => {
  const out = runBuildResponse([MARKER_OBJECT_TYPE_ONLY, ORDINARY_ROW]);
  assert.equal(out.length, 1, "the marker must not reach the caller as a row");
  assert.equal(out[0].row_id, "e-li-a");
  assert.equal(out[0].action, "proposed");
  // The survivor still gets the full outcome projection — the fix must not touch what a
  // real row receives.
  assert.equal(out[0].outcome_contract_version, 2);
  assert.ok("contactability" in out[0]);
});

test("Build Response: a raw parsed event with a null object id (Gate 5's third recovered shape) is dropped", () => {
  const out = runBuildResponse([MARKER_RAW_PARSED_EVENT, ORDINARY_ROW]);
  assert.equal(out.length, 1, "an identity-less raw event must not reach the caller as a row");
  assert.equal(out[0].row_id, "e-li-a");
});

test("Build Response: a row identified only by its row id (no action yet) survives", () => {
  const out = runBuildResponse([ROW_ID_ONLY]);
  assert.equal(out.length, 1);
  assert.equal(out[0].row_id, "e-li-b");
});

test("Build Response: a request-level refusal identified only by its outcome survives — no action, no row id, no object id", () => {
  const out = runBuildResponse([REFUSAL_ROW, MARKER_OBJECT_TYPE_ONLY]);
  assert.equal(out.length, 1, "the refusal is real; the object-type-only marker beside it is not");
  assert.equal(out[0].outcome, "refused");
  assert.equal(out[0].row_id, undefined);
  assert.equal(out[0].action, undefined);
});

test("Build Response: an unsupported-type event carrying a REAL (non-null) object id survives — only a null object id marks a marker", () => {
  const realUnsupported = { ...MARKER_RAW_PARSED_EVENT, object_id: "999888" };
  const out = runBuildResponse([realUnsupported]);
  assert.equal(out.length, 1, "a genuinely unsupported webhook event is a real terminal, not a marker");
  assert.equal(out[0].object_id, "999888");
});

test("Build Response: a raw HubSpot write response ({id, properties}, no other identity key) survives — the armed write lane's own contract", () => {
  const out = runBuildResponse([{ id: "111", properties: { email: "a@b.example" } }]);
  assert.equal(out.length, 1, "the write node's own response IS the returned row on this lane");
  assert.equal(out[0].id, "111");
});

// =====================================================================================
// "Build Ingest Response" — the acceptance criterion says applying the same rule here is
// "expected to change nothing today"; that claim is a no-op ONLY if nothing ever reaches
// this node with none of the identity keys. The ingest suites staying green proves the
// COMMON path is untouched; it proves nothing about the filter itself being reachable.
// This section proves the filter is live on this node, not merely present in its body.
// =====================================================================================

function runBuildIngestResponse(items) {
  const node = jsCodeNode("n8n/wf_contact_ingest_cloud.json", "Build Ingest Response");
  const { outputs } = runNode(node, items, {});
  return outputs[0];
}

test("Build Ingest Response: the shared identity filter is present in the committed jsCode", () => {
  const node = jsCodeNode("n8n/wf_contact_ingest_cloud.json", "Build Ingest Response");
  assert.match(node.parameters.jsCode, /hasRowIdentity/,
    "D-70-25 applies the SAME shared predicate at the ingest emit point, not a second copy");
});

test("Build Ingest Response: a starved-lane sentinel's own marker shape (_decided_snapshot true, nothing else) projects to zero identity keys and is dropped", () => {
  // `decided` admits this item (it IS the _decided_snapshot tag the node keys on), but its
  // own projection stamps every identity key null/undefined when nothing else backs it —
  // action: row.action (undefined), outcome: null, contact_id/hs_object_id: null,
  // row_id: null. This is the shape a starved "Decide Action Snapshot" fan-out delivery
  // would carry if it ever reached this node with nothing decided behind it.
  const out = runBuildIngestResponse([{ _decided_snapshot: true }]);
  assert.equal(out.length, 0, "an identity-less decided-snapshot projection must not reach the caller as a row");
});

test("Build Ingest Response: an ordinary decided row (real action, row id) survives, alongside the dropped marker", () => {
  const out = runBuildIngestResponse([
    { _decided_snapshot: true },
    { _decided_snapshot: true, action: "update", row_id: "i-a", hs_object_id: "555" },
  ]);
  assert.equal(out.length, 1, "only the real decided row returns");
  assert.equal(out[0].row_id, "i-a");
  assert.equal(out[0].action, "update");
});
