// tests/n8n/walkerEngineFidelity.test.mjs
//
// Phase 70 plan 70-09 (gaps G-70-2 / G-70-3, decisions D-70-19 / D-70-20): the walker's
// fidelity to the LIVE n8n Cloud engine, stated as reproductions of two executions this
// repo actually watched on 2026-09-10.
//
// Why this file exists. Every offline suite was green while the live engine dropped rows.
// `tests/n8n/lib/walkWorkflow.mjs` dropped a zero-item wave; the engine DELIVERS it. So
// an offline green meant nothing, and no graph fix could be believed until the instrument
// told the truth. These cases are written against the observed runData of executions
// 12203 and 12206 — the outcome the engine PRODUCED, never the outcome the design
// intended. D-70-19: the walker moves toward the engine, never toward the plans and never
// toward a green suite.
//
// Every case runs against a FROZEN copy of the graph as committed on 2026-09-10 (see
// `fixtures/frozen/README.md`), because Wave 2 changes the live graph under `n8n/` and
// "the current committed JSON" would otherwise stop meaning what these executions ran.
//
// The armed case rewrites the loaded jsCode literals in memory — the same rewrite
// `n8n_arming.set_write_safety` performs live and the one `tests/n8n/writeGateShape.test.mjs`
// already uses. It is deliberately NOT a second arming mechanism, and it never touches a
// file on disk.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FROZEN = path.join(HERE, "fixtures", "frozen");
const FROZEN_INGEST = path.join(FROZEN, "wf_contact_ingest_cloud.2026-09-10.json");

// =====================================================================================
// Execution 12203 — Gate 70-05-A, the first ARMED batch with a mixed verdict on one gate.
//
// Observed (70-UAT.md § Test 2): Darwin Turf Club `9605267534`; contact `7101` Grant
// Dewsbury on the allowlist, contact `2751` Steve Taylor off it, both in ONE batch, both
// resolving the same company by domain. HubSpot itself was written CORRECTLY — 7101
// PATCHed, the 7101 -> 9605267534 association created, 2751 untouched. What FAILED was
// the REPORT: `Build Ingest Response` returned 2 rows, and BOTH came back
// `action: "update"`, `association: "not_confirmed"`.
//
// Cause, from the runData `source` arrays: `Associate Carry Merge` (combineByPosition)
// fired with input 1 taken by `Associate Lane Sentinel`'s ZERO-ITEM output (armed, a real
// association was in flight, so the sentinel emitted `[]`) instead of `Build Association
// Request`'s one item — 1 x 0 combined to 0 items and the association result was dropped.
// `Ingest Merge Response` fired with input 3 taken by `HubSpot Update Gate Unreached
// Sentinel`'s ZERO-ITEM output instead of the gate IF's refusal row, so the
// `write_blocked` row for 2751 — which `HubSpot Update Write Gate IF` out1 DID emit —
// never reached the response builder.
// =====================================================================================

const A_EMAIL = "grant@darwinturfclub.org.au";   // contact 7101, ON the allowlist
const B_EMAIL = "steve@darwinturfclub.org.au";   // contact 2751, OFF the allowlist
const A_ID = "7101";
const B_ID = "2751";
const COMPANY_ID = "9605267534";
const COMPANY_DOMAIN = "darwinturfclub.org.au";

// Every node on this lane that DECLARES a write flag. The operator's read-back on 12203
// confirmed all THREE were rewritten by `june_run_arm.py`; arming a subset here would be
// a test artifact rather than the state the engine ran under.
const ARMING_NODES = ["HubSpot Update Write Gate", "HubSpot Create Write Gate",
  "Associate Lane Sentinel"];

function armedIngestGraph() {
  const wf = JSON.parse(fs.readFileSync(FROZEN_INGEST, "utf8"));
  for (const name of ARMING_NODES) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `execution 12203 armed this node, so it must exist in the frozen graph: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const TEST_RECORD_IDS = "";', `const TEST_RECORD_IDS = "${A_ID}";`);
  }
  return wf;
}

function run12203() {
  return walkWorkflow(armedIngestGraph(), {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: A_EMAIL, firstname: "Grant", lastname: "Dewsbury", company: "Darwin Turf Club" },
      { email: B_EMAIL, firstname: "Steve", lastname: "Taylor", company: "Darwin Turf Club" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [
        { email: A_EMAIL, status: "VALID" }, { email: B_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [
        { results: [{ id: A_ID, properties: { email: A_EMAIL } }] },
        { results: [{ id: B_ID, properties: { email: B_EMAIL } }] },
      ],
      // Both contacts resolve the SAME company, by domain — the shape that made the
      // association lane live for one row and refused for the other.
      "HubSpot Company Search by Domain": [
        { results: [{ id: COMPANY_ID, properties: { domain: COMPANY_DOMAIN } }] },
        { results: [{ id: COMPANY_ID, properties: { domain: COMPANY_DOMAIN } }] },
      ],
      "HubSpot Company Search by Name": [{ results: [] }, { results: [] }],
      // Only the permitted contact is written, and only its association is created —
      // exactly what HubSpot showed after 12203.
      "HubSpot Update": [{ id: A_ID, properties: { email: A_EMAIL } }],
      "HubSpot Associate Company": [{ status: "ok" }],
    },
  });
}

test("execution 12203 (armed mixed verdict, ingest lane): the walker reproduces what the engine DID — both rows report update/not_confirmed and the refusal row never reaches the response builder", () => {
  const { runData } = run12203();
  const rows = nodeItems(runData, "Build Ingest Response");

  // The one thing 12203 got right: two rows in, two rows out, never four.
  assert.equal(rows.length, 2,
    "execution 12203 observed: Build Ingest Response returned exactly 2 rows, never 4");

  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));

  // --- the association fact, asserted FIRST because it is the fact this file exists for.
  // HubSpot really did create the 7101 -> 9605267534 association on 12203. The REPORT did
  // not say so, because the sentinel's zero-item output claimed the carry Merge's input
  // ahead of the real association result.
  assert.equal(byEmail[A_EMAIL].association, "not_confirmed",
    "execution 12203 observed: the PERMITTED row reported association 'not_confirmed' " +
    "even though HubSpot created the association — Associate Carry Merge fired with " +
    "input 1 taken by Associate Lane Sentinel's zero-item output");
  assert.equal(byEmail[B_EMAIL].association, "not_confirmed",
    "execution 12203 observed: the refused row reported association 'not_confirmed'");

  // --- the refusal fact: the gate DID emit a write_blocked row, and it was dropped.
  assert.equal(byEmail[B_EMAIL].action, "update",
    "execution 12203 observed: the REFUSED row still reported action 'update' — the " +
    "gate's write_blocked row never reached Build Ingest Response");
  assert.equal(byEmail[A_EMAIL].action, "update",
    "execution 12203 observed: the permitted row reported action 'update'");

  // The gate itself behaved correctly — this is what makes the drop a REPORTING defect
  // rather than an authorization one.
  const gateRows = nodeItems(runData, "HubSpot Update Write Gate IF");
  const refused = gateRows.find((r) => r.hs_object_id === B_ID);
  assert.ok(refused && refused.write_allowed === false,
    "execution 12203 observed: HubSpot Update Write Gate IF out1 DID emit the " +
    "write_blocked row for 2751 — the row exists, it simply never reached the merge");

  // --- the carry Merge: one run, zero items out (1 real association x 0 sentinel items).
  assert.equal((runData["Associate Carry Merge"] || []).length, 1,
    "execution 12203 observed: Associate Carry Merge ran exactly once");
  assert.equal(runData["Associate Carry Merge"][0].length, 0,
    "execution 12203 observed: Associate Carry Merge emitted ZERO items — " +
    "combineByPosition of 1 real association against the sentinel's empty input");

  // --- the response Merge: one run, and the refusal row is absent from the merged set.
  // The load-bearing assertion of this file: a row that a node genuinely emitted is
  // missing from the merged result because a sentinel's [] claimed its input first.
  assert.equal((runData["Ingest Merge Response"] || []).length, 1,
    "execution 12203 observed: Ingest Merge Response ran exactly once");
  const merged = runData["Ingest Merge Response"][0];
  assert.equal(merged.some((it) => it && it.write_allowed === false), false,
    "execution 12203 observed: the write_blocked row emitted by the update gate's second " +
    "output is ABSENT from Ingest Merge Response's merged set — input 3 was taken by " +
    "HubSpot Update Gate Unreached Sentinel's zero-item output");
});

// =====================================================================================
// Execution 12206 — Gate 3 / D-70-19, the disarmed `enrichment_single_lane` send.
//
// Observed (70-UAT.md § Test 3, and `70-RUNTIME-VERDICT.json` § enrichment_single_lane):
// two contact rows with unresolvable `.invalid` identities, propose mode, disarmed. The
// execution settled `success` — no hang — and 0 rows came back against 2 predicted.
// `Enrichment Gate Merge` (append, 5 inputs) fired ONCE on starved-lane sentinel
// deliveries; the real rows (`Adapt Search`, `Adapt Linkedin Search`) reached it AFTER it
// had fired and were dropped; `Build Response` never ran; the lane terminated silently.
//
// TWO DIVERGENCES between this replay and the live runData, recorded rather than tuned
// away (D-70-19 — the walker is never adjusted to make an assertion land):
//
//   1. INPUT PROVENANCE. Live, `Enrichment Gate Merge` input 0 was claimed by
//      `Contacts Lane FetchById Absent Sentinel` (one marker item) and inputs 1-4 by
//      `Contacts Absent Sentinel`'s `[]`, so the Merge carried 1 marker and
//      `Enrichment Gate` ran and filtered it to 0. This replay has `Contacts Absent
//      Sentinel` — one hop off `IF Scale Up Route`, i.e. shallower — claiming all five,
//      so the Merge carries 0 items and `Enrichment Gate` never runs at all. Which of
//      two producers claims a shared input first is an ORDERING question this repo has
//      no live evidence to settle, and depth-first ordering was tried and rejected: it
//      swings the 12203 case above back to the outcome the design intended, which the
//      engine demonstrably did not produce. The OUTCOME is identical either way — zero
//      real rows past the gate — so the assertions below are written on the outcome and
//      on the mechanism, never on which sentinel won the race.
//   2. `Build Response Merge` (15 inputs). Live it NEVER EXECUTED. Under this corrected
//      walker every one of its 15 inputs receives a delivery and it fires, carrying only
//      sentinel markers, which `Filter Build Response Rows` then removes — so
//      `Build Response` still never runs and the lane still yields zero rows. The
//      difference matters for Wave 2: it means starvation does NOT explain the live
//      non-firing, and n8n's documented 2-10 input range is left as the leading
//      hypothesis rather than a confounded one. See
//      `70-WALKER-RED-INVENTORY.md` § "The 15-input observation".
// =====================================================================================

const FROZEN_ENRICHMENT = path.join(FROZEN, "wf_enrichment_cloud.2026-09-10.json");

// The same neutral "nothing resolved" body `scripts/prove_phase70_runtime.py` sends into
// the walker for this send — every identity search runs against synthetic `.invalid`
// addresses that resolve nothing, and every provider is disabled, so every HTTP hop
// returns nothing on BOTH sides of the comparison.
const NEUTRAL_HTTP_BODY = {
  results: [], data: {}, matched: false, access_token: "stub-token", id: null, properties: {},
};

function run12206() {
  const wf = JSON.parse(fs.readFileSync(FROZEN_ENRICHMENT, "utf8"));
  const httpStubs = {};
  for (const n of wf.nodes) {
    if (n.type === "n8n-nodes-base.httpRequest" || n.type === "n8n-nodes-base.hubspot") {
      httpStubs[n.name] = Array.from({ length: 8 }, () => ({ ...NEUTRAL_HTTP_BODY }));
    }
  }
  return walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { run_id: null, mode: "propose", events: [
      { objectType: "contact", email: "p70-single-a@runtime-proof.invalid", row_id: "e-single-a" },
      { objectType: "contact", email: "p70-single-b@runtime-proof.invalid", row_id: "e-single-b" },
    ] } }],
    httpStubs,
  });
}

test("execution 12206 (disarmed propose batch, enrichment lane): the walker reproduces the silent termination — a sentinel's zero-item delivery claims every Enrichment Gate Merge input, the real rows arrive after the fire, and Build Response never runs", () => {
  const { runData, trace } = run12206();

  // --- the gate Merge fired ONCE, and every input was taken by a starved-lane sentinel.
  const gateMerge = trace.merges["Enrichment Gate Merge"];
  assert.equal((runData["Enrichment Gate Merge"] || []).length, 1,
    "execution 12206 observed: Enrichment Gate Merge fired exactly once");
  const claimants = Object.values(gateMerge.sources);
  assert.equal(claimants.length, 5,
    "execution 12206 observed: all five Enrichment Gate Merge inputs received a delivery");
  for (const [input, producer] of Object.entries(gateMerge.sources)) {
    assert.match(producer, /Sentinel$/,
      `execution 12206 observed: Enrichment Gate Merge input ${input} was claimed by a ` +
      `starved-lane sentinel (${producer}), never by the lane's real producer`);
  }

  // --- the real rows EXIST upstream and are absent from the merged set. This is the
  // whole defect: nothing errored, nothing stalled, the rows were simply too late.
  assert.equal(nodeItems(runData, "Adapt Search").length, 2,
    "execution 12206 observed: Adapt Search really did produce the two rows — they exist");
  const mergedItems = nodeItems(runData, "Enrichment Gate Merge");
  assert.equal(mergedItems.some((it) => it && it.row_id), false,
    "execution 12206 observed: not one real row is in Enrichment Gate Merge's output — " +
    "the merge had already fired on the sentinels when the real rows arrived, and a " +
    "delivery to a fired merge is discarded");

  // --- the gate contributes zero rows, and the response builder never runs.
  assert.equal(nodeItems(runData, "Enrichment Gate").length, 0,
    "execution 12206 observed: Enrichment Gate contributed ZERO rows downstream");
  assert.equal((runData["Build Response"] || []).length, 0,
    "execution 12206 observed: Build Response NEVER RAN — the response lane terminated " +
    "silently and the execution still finished 'success'");
  assert.equal(nodeItems(runData, "Build Response").length, 0,
    "execution 12206 observed: 0 rows recovered against 2 rows sent (70-RUNTIME-VERDICT" +
    ".json: recovered_row_count 0, predicted_row_count 2)");

  // --- and the caller was told the batch was accepted. The ack is the only thing that
  // answered, which is exactly why the loss was silent to the client.
  assert.ok(trace.respond, "execution 12206 observed: the ack still fired");
  assert.equal(trace.respond.items[0].accepted, true,
    "execution 12206 observed: the caller was told accepted:true while every row was lost");
  assert.deepEqual(trace.respond.items[0].row_ids, ["e-single-a", "e-single-b"],
    "execution 12206 observed: the ack even named both rows it had already dropped");
});

// =====================================================================================
// Execution 12316 — Phase 70 Plan 14 (gap G-70-5, D-70-26(b)). [observed live], execution
// 12316, dated 2026-09-10. A child of the runaway self-dispatch loop (135 child executions
// in six minutes, 12211-12348; see CLAUDE.md §13.0.2, 70-UAT.md § Test 4). This case is a
// RECORD, not a model — D-70-19/D-70-26 forbid teaching the walker a mechanism nobody
// isolated. The cause of what follows is UNKNOWN.
//
// The engine's own runData (`exec_12316.runData.json`, committed at planning time,
// verified below, NEVER regenerated) names, for eleven nodes, the `source` — the producer
// the engine itself recorded as having delivered to that node's run — beside
// `declared_producers`, read from this file's own frozen `connections` map. For eight of
// the eleven, source and declared producer agree. For exactly THREE, they do not:
//
//   - "Recompute Requested Sentinel Gate": engine source "Companies Absent Sentinel Gate"
//     (a DIFFERENT sentinel's gate); declared producer "Recompute Requested Sentinel".
//   - "Dispatch Self": engine source "Recompute Requested Sentinel Gate" (the gate from
//     the line above); declared producer "Build Scale Up Fan-Out".
//   - "Build Scale Up Fan-Out": engine source "Refusal Row Absent Sentinel Gate" (yet
//     ANOTHER sentinel's gate); declared producer "IF Scale Up Route".
//
// No edge in this file's own `connections` map explains any of the three. The walker
// replays ONLY declared connections — `propagate()` enqueues exactly the edges
// `connectionsFrom` returns — so it structurally CANNOT reproduce a delivery with no
// declared edge. That is not a walker deficiency this case is proving; it is the reason
// the case exists: the engine ran three nodes off connections that, on paper, do not
// exist, and the walker must never be adjusted to pretend it knows why.
// =====================================================================================

const FROZEN_ENRICHMENT_GAP_CLOSURE = path.join(FROZEN, "wf_enrichment_cloud.gap-closure.2026-09-10.json");
const EXEC_12316_RUNDATA = path.join(FROZEN, "exec_12316.runData.json");

const MISMATCHED_12316_NODES = [
  "Recompute Requested Sentinel Gate",
  "Dispatch Self",
  "Build Scale Up Fan-Out",
];

function loadFrozen12316() {
  const wf = JSON.parse(fs.readFileSync(FROZEN_ENRICHMENT_GAP_CLOSURE, "utf8"));
  const runDataFixture = JSON.parse(fs.readFileSync(EXEC_12316_RUNDATA, "utf8"));
  return { wf, runDataFixture };
}

// The frozen connections' own declared producers for a node — computed from THIS file's
// graph, never hand-copied, so a drift between the fixture and its own connections map
// fails here rather than silently mismatching the sidecar's `declared_producers` field.
function declaredProducersOf(wf, targetName) {
  const producers = [];
  for (const [srcName, spec] of Object.entries(wf.connections || {})) {
    for (const branch of (spec.main || [])) {
      for (const edge of (branch || [])) {
        if (edge.node === targetName) producers.push(srcName);
      }
    }
  }
  return producers;
}

test("execution 12316 fixtures: the committed frozen body was verified, never regenerated — 291 nodes, empty settings, no node carries a credentials block", () => {
  const { wf } = loadFrozen12316();
  assert.equal(wf.nodes.length, 291,
    "the gap-closure body execution 12316 actually ran carries 291 nodes (pre-70-13; " +
    "70-13 later deleted the scale-up lane to 287 — this frozen copy predates that and " +
    "must, since it is the body the engine executed)");
  assert.deepEqual(wf.settings, {}, "execution 12316's frozen body carries empty settings");
  const withCredentials = wf.nodes.filter((n) => n.credentials).map((n) => n.name);
  assert.deepEqual(withCredentials, [],
    "no node in this committed fixture may carry a credentials block (T-70-67)");
});

test("execution 12316 fixtures: the committed runData sidecar names exactly three nodes whose engine source is not among their declared producers", () => {
  const { wf, runDataFixture } = loadFrozen12316();
  const mismatched = [];
  for (const [name, entry] of Object.entries(runDataFixture.nodes)) {
    const observedSource = (entry.source[0] && entry.source[0].previousNode) || null;
    const declared = declaredProducersOf(wf, name);
    // The sidecar's own `declared_producers` field must agree with what THIS frozen
    // graph's connections actually declare — belt-and-braces against the sidecar itself
    // drifting from the fixture it describes.
    assert.deepEqual([...declared].sort(), [...entry.declared_producers].sort(),
      `${name}: the sidecar's declared_producers must match this frozen graph's own connections`);
    if (observedSource !== null && !declared.includes(observedSource)) {
      mismatched.push({ name, observedSource, declared });
    }
  }
  assert.equal(mismatched.length, 3,
    `exactly three nodes must show an engine source outside their declared producers, got: ${JSON.stringify(mismatched)}`);
  assert.deepEqual(mismatched.map((m) => m.name).sort(), [...MISMATCHED_12316_NODES].sort());
});

test("execution 12316 (D-70-26(b), [observed live], 2026-09-10, cause unknown): the walker does NOT reproduce the three unconnected-source runs — a prohibition guard, not a model", () => {
  const { wf, runDataFixture } = loadFrozen12316();

  // Seeded from the SUB-WORKFLOW entry point with the single empty item the engine
  // actually delivered (`exec_12316.runData.json`'s "Execute Workflow Trigger" entry:
  // out0_item_count 1, out0_first_item_json {}) — the execution entered here, not the
  // webhook, exactly as a self-dispatched child does.
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Execute Workflow Trigger",
    triggerItems: [{}],
    // No httpStubs supplied deliberately: the empty seed parses to object_type "unknown"
    // (matches the sidecar's "Parse HubSpot Event" entry exactly) and routes through the
    // unsupported-object-type terminal to "Build Response" without reaching an HTTP node
    // at all. If a future graph edit makes this walk reach an unstubbed HTTP node, the
    // walker throws by name — telling the next agent what changed rather than silently
    // passing.
    httpStubs: {},
  });

  // Prove the walk actually completed rather than dying early — a prohibition case that
  // passes vacuously (the walk stalled before it could reach these nodes either way)
  // proves nothing.
  assert.ok(trace.respond, "the walk must reach the responder for this to be a real replay, not a stall");
  assert.equal((runData["Build Response"] || []).length, 1, "Build Response ran exactly once");
  assert.equal((runData["IF Scale Up Route"] || []).length, 1, "IF Scale Up Route ran");
  const scaleUpTrueOut = runData["IF Scale Up Route"][0];
  // The walker's own IF modelling records the pre-split input, not the branch outputs —
  // confirm via the merged Parse HubSpot Event row instead: scale_up normalized false, so
  // the walker's OWN model sends the true (scale-up) branch zero items and, per
  // `propagate()`'s "a node fed ZERO items does not RUN" rule, none of the three should
  // ever run.
  assert.equal(scaleUpTrueOut[0].scale_up, false,
    "the parsed row scale_up is false, so the walker's true branch carries no items");

  for (const name of MISMATCHED_12316_NODES) {
    const declared = declaredProducersOf(wf, name);
    const observedSource = runDataFixture.nodes[name].source[0].previousNode;
    assert.equal(runData[name], undefined,
      `${name} must NOT run in the walk — the engine ran it off an observed source ` +
      `("${observedSource}") that is not among its declared producers (${JSON.stringify(declared)}); ` +
      `if this assertion ever fails, the walker has started reproducing an unisolated ` +
      `mechanism and D-70-26(b) is violated`);
  }
});
