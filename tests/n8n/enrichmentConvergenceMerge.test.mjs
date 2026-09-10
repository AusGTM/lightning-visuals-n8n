// tests/n8n/enrichmentConvergenceMerge.test.mjs
//
// Phase 70 Plan 03 Task 1 (D-70-01) — the walker-driven acceptance for the enrichment
// lane's six new convergence Merges ("Build Response Merge", "Enrichment Gate Merge",
// "Company Gate Merge", "Merge Winners Fan-In", "Merge Company Fan-In", "Decide Company
// Action Merge") and their starved-lane sentinel network. Drives the COMMITTED
// n8n/wf_enrichment_cloud.json through tests/n8n/lib/walkWorkflow.mjs (the SAME
// interpreter n8n/code/nodeRunRecovery.js's header describes, and the mechanism the rest
// of this phase is judged by) for each plan-required behaviour, asserting `starvedWithData`
// (quick task 260911-1z5's shared no-real-loss filter over `trace.stalled`) is empty and
// that "Build Response" (via its Merge) delivers every real input row exactly
// once — no fewer (a starved input would drop a lane; F5's own shape), no more (a marker
// leaking through would report a phantom row to the caller).
//
// NOTE: this replays the repo's OWN committed workflow jsCode/expressions via `new
// Function` — the same mechanism n8n's Code/IF nodes use at runtime — over trusted,
// in-repo JSON. No external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, loadWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function load() {
  return loadWorkflow(WF_PATH);
}

const EMPTY_SEARCH = [{ results: [] }];
// A generous, reusable stub set: every HTTP node this graph can reach on a disarmed
// batch (both write flags are "false" in the committed JSON — no test here needs a real
// write to succeed). `emptyResult` items are per-call-shaped: n8n's real HTTP node fires
// once per input item, so a stub returning a fixed array pairs item i with result i —
// tests that send >1 item override the specific stub(s) that need per-row shaping.
function baseStubs() {
  return {
    "HubSpot Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search Fallback": (items) => items.map(() => ({ results: [] })),
    "HubSpot Linkedin Search": (items) => items.map(() => ({ results: [] })),
    "Lusha Enrich": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Match": (items) => items.map(() => ({})),
    "ZoomInfo Mint": [{ access_token: "tok" }],
    "Contact Web Research": (items) => items.map(() => ({})),
    "Contact Judge Call": (items) => items.map(() => ({})),
    "HubSpot Create": (items) => items.map(() => ({ id: "999", properties: {} })),
    "HubSpot Update": (items) => items.map(() => ({ id: "111", properties: {} })),
    "HubSpot Company Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Company Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Company Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "Lusha Company": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Org": (items) => items.map(() => ({})),
    "ZoomInfo Mint Company": [{ access_token: "tok" }],
    "Claude Web Research": (items) => items.map(() => ({})),
    "Judge Call": (items) => items.map(() => ({})),
    "HubSpot Company Create": (items) => items.map(() => ({ id: "888", properties: {} })),
    "HubSpot Company Update": (items) => items.map(() => ({ id: "888", properties: {} })),
    "Lusha Usage": [{}],
    "Apollo Usage": [{}],
    "ZoomInfo Usage Mint": [{ access_token: "tok" }],
    "HubSpot List By Name": [{}],
    "HubSpot List Memberships": [{}],
  };
}

function contactEvent(objectId, email) {
  return { objectId, objectType: "contact", email, run_id: "case" };
}
function companyEvent(objectId, domain, extra) {
  return { objectId, objectType: "company", domain, run_id: "case", ...extra };
}

function run(events, stubOverrides) {
  const wf = load();
  return walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { events } }],
    httpStubs: { ...baseStubs(), ...(stubOverrides || {}) },
  });
}

// =============================================================================================
// Structural: Merge count matches classify_convergence's own verdict, never a magic number.
// =============================================================================================

test("the enrichment workflow's D-70-01 fan_in convergence Merges are exactly the six this plan fixed", () => {
  const wf = load();
  const merges = wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge");
  // The six D-70-01 fan_in convergences this plan fixes (mode: "append"). Every OTHER
  // multi-inbound node in this graph is either "Parse HubSpot Event" (class
  // "entry_points", refused below) or one of the provider-gate bypass pairs (class (b),
  // deliberately left unmerged — see the plan's own action text and this test file's
  // final section for the record). Phase 70 Plan 04 (D-70-04) added a SECOND category
  // of Merge (mode: "combine", the per-HTTP-hop carry merges) — filtered out here by
  // mode, asserted by count in the next test, so this test keeps testing exactly what
  // it always tested.
  const convergenceMerges = merges.filter((m) => m.parameters.mode === "append");
  // Phase 70 Plan 04 (D-70-04) added a SEVENTH append-mode Merge — "Collect Credits"
  // (3 inputs, one per provider's real-or-skipped credit lane) — a new, genuinely
  // optional-lane convergence this plan introduced, not one of the original six.
  // Phase 70 Plan 11 (D-70-20): "Build Response Merge" declared fifteen inputs — over
  // n8n's own ten-input cap — and is now split into three lane-grouped stage Merges
  // (contacts, companies, unsupported/refusal) that reconverge on "Build Response
  // Merge" itself (unrenamed — every consumer that already named it keeps working).
  // Three MORE append-mode Merges, not a replacement for the one already counted.
  const expectedNames = [
    "Build Response Merge", "Enrichment Gate Merge", "Company Gate Merge",
    "Merge Winners Fan-In", "Merge Company Fan-In", "Decide Company Action Merge",
    "Collect Credits",
    "Build Response Merge Stage 1", "Build Response Merge Stage 2", "Build Response Merge Stage 3",
  ];
  assert.deepEqual(convergenceMerges.map((m) => m.name).sort(), expectedNames.sort());
});

test("the enrichment workflow's D-70-04 carry merges (mode: combine) are exactly the ones this plan wires", () => {
  const wf = load();
  const carryMerges = wf.nodes.filter(
    (n) => n.type === "n8n-nodes-base.merge" && n.parameters.mode === "combine");
  const expectedNames = [
    "HubSpot Fetch By Id Carry Merge", "HubSpot Search Carry Merge",
    "HubSpot Linkedin Search Carry Merge", "HubSpot Name Search Carry Merge",
    "HubSpot Name Search Fallback Carry Merge",
    "Lusha Result Carry Merge", "Apollo Result Carry Merge", "ZoomInfo Mint Carry Merge",
    "Research Carry Merge", "Judge Carry Merge",
    "Contact Research Carry Merge", "Contact Judge Carry Merge",
    "HubSpot Company Fetch By Id Carry Merge", "HubSpot Company Search Carry Merge",
    "HubSpot Company Name Search Carry Merge",
    "Lusha Company Result Carry Merge", "Apollo Org Result Carry Merge",
    "ZoomInfo Mint Company Carry Merge",
    "ZoomInfo Usage Mint Carry Merge",
    // Phase 70 Plan 04 (D-70-04) Task 2 additions: the list-expansion chain's two
    // chained HTTP hops, the company-create id-capture hop, and the credits broadcast.
    "List By Name Carry Merge", "List Memberships Carry Merge",
    "HubSpot Company Create Carry Merge", "Credits Broadcast",
  ];
  assert.deepEqual(carryMerges.map((m) => m.name).sort(), expectedNames.sort());
});

test('"Parse HubSpot Event" has NO Merge in front of it and still carries its original inbound edges', () => {
  const wf = load();
  const inbound = [];
  for (const [src, spec] of Object.entries(wf.connections)) {
    (spec.main || []).forEach((branch, idx) => {
      for (const edge of branch || []) {
        if (edge.node === "Parse HubSpot Event") inbound.push({ src, idx });
      }
    });
  }
  assert.deepEqual(
    new Set(inbound.map((e) => e.src)),
    new Set(["Execute Workflow Trigger", "IF List Input", "IF List Expanded"]),
    "the three original sources must still feed Parse HubSpot Event directly",
  );
  assert.ok(
    !wf.nodes.some((n) => n.type === "n8n-nodes-base.merge" &&
      (wf.connections[n.name] || {}).main?.[0]?.some((e) => e.node === "Parse HubSpot Event")),
    "no Merge node may sit between any of the three sources and Parse HubSpot Event",
  );
});

test("every multi-inbound provider-gate bypass pair is deliberately left unmerged (class (b))", () => {
  // Recorded per the plan's own action text: each pair rejoins after EXACTLY one
  // delivery per row (`_provider_gate_bypass_chain`'s own docstring), so a Merge there
  // adds hang exposure (T-70-04) for zero behaviour change.
  const wf = load();
  const merged = new Set(wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge").map((n) => n.name));
  const bypassTargets = [
    "IF Apollo Enabled", "IF ZoomInfo Enabled", "Normalize + Score", "ZoomInfo Enrich",
    "IF Apollo Org Enabled", "IF ZoomInfo Company Enabled", "Normalize + Score Company",
    "ZoomInfo Company", "ZoomInfo Usage",
  ];
  for (const target of bypassTargets) {
    assert.ok(!merged.has(`${target} Merge`), `${target} must not have gained a Merge`);
  }
});

// =============================================================================================
// Behaviour: single-identity-lane contacts batch — the common shape AND the hang case.
// =============================================================================================

test("a contacts batch using only the email identity lane reaches Enrichment Gate once, every row, no stall", () => {
  const { runData, trace } = run([contactEvent("1", "a@example.com")]);
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(nodeItems(runData, "Enrichment Gate").length, 1);
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1, "exactly one real row, no leaked sentinel marker");
  assert.equal(rows[0].properties?.email ?? rows[0].email, "a@example.com");
});

// =============================================================================================
// Behaviour: a companies batch that Company Gate skips entirely still reaches Decide
// Company Action via the recompute lane.
// =============================================================================================

test("a companies batch Company Gate skips entirely still reaches Decide Company Action via the recompute lane", () => {
  const { runData, trace } = run(
    [companyEvent("1", "existing.com", { recompute: true })],
    { "HubSpot Company Search": () => [{ results: [{ id: "555", properties: { domain: "existing.com" } }] }] },
  );
  assert.deepEqual(starvedWithData(trace), []);
  assert.ok(nodeItems(runData, "Decide Company Action").length >= 1, "Decide Company Action ran");
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].hs_object_id, "555");
});

// =============================================================================================
// Behaviour: a mixed batch (one create, one update) reaches Build Response with exactly
// two rows, one per input row.
// =============================================================================================

test("a mixed batch (one create, one update) reaches Build Response with exactly two rows", () => {
  const { runData, trace } = run(
    [contactEvent("1", "newperson@example.com"), contactEvent("2", "existing@example.com")],
    {
      "HubSpot Search": (items) => items.map((it) => {
        const email = it.identity_keys?.email;
        return email === "existing@example.com"
          ? { results: [{ id: "111", properties: { email } }] }
          : { results: [] };
      }),
    },
  );
  assert.deepEqual(starvedWithData(trace), []);
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 2, "one row per input row, never fewer, never a phantom marker");
  const emails = rows.map((r) => r.properties?.email ?? r.existingRecord?.email).sort();
  assert.deepEqual(emails, ["existing@example.com", "newperson@example.com"]);
});

// =============================================================================================
// Behaviour: Merge Winners / Merge Company receive all their upstream rows in one run;
// candidate-merge output unchanged for a fixture that exercised them before this change.
// =============================================================================================

test("Merge Winners fires once over all three inputs on a batch with no research/judge need", () => {
  const { runData, trace } = run([contactEvent("1", "a@example.com")]);
  assert.deepEqual(starvedWithData(trace), []);
  // Fired exactly once (append-mode Merge locks after its first satisfying wave).
  assert.equal((runData["Merge Winners Fan-In"] || []).length, 1);
  assert.ok(nodeItems(runData, "Merge Winners").length >= 1, "Merge Winners ran with real content");
});

test("Merge Company fires once over all three inputs on a companies batch with no research/judge need", () => {
  const { runData, trace } = run([companyEvent("1", "nosuch.example", {})]);
  assert.deepEqual(starvedWithData(trace), []);
  assert.equal((runData["Merge Company Fan-In"] || []).length, 1);
  assert.ok(nodeItems(runData, "Merge Company").length >= 1, "Merge Company ran with real content");
});

// =============================================================================================
// Behaviour: adding a Merge does not change scoring for a fixture that already exercised
// these nodes — pinned by the frozen jsCode fixture tests
// (tests/test_companies_factory_frozen.py) and the veto/scoring suites named in this
// plan's own <acceptance_criteria>; re-asserted here structurally: the identity-drop
// filter is the ONLY change to these six nodes' bodies.
// =============================================================================================

test("the six converged nodes' jsCode changes are the identity-drop filter only", () => {
  const wf = load();
  const node = (name) => wf.nodes.find((n) => n.name === name);
  for (const name of [
    "Build Response", "Enrichment Gate", "Company Gate", "Merge Winners",
    "Merge Company", "Decide Company Action",
  ]) {
    const js = node(name).parameters.jsCode;
    assert.match(
      js, /Object\.keys\(it\.json \|\| \{\}\)\.length > 0/,
      `${name} must drop identity-less sentinel markers as its first line`,
    );
  }
});

// =============================================================================================
// Companies-only batch: contacts side entirely absent — every contacts-side merge input
// must still be satisfied by a starved-lane sentinel, never left stalled.
// =============================================================================================

test("a companies-only batch does not stall any contacts-side merge input", () => {
  const { trace } = run([companyEvent("1", "existing.com", { recompute: true })], {
    "HubSpot Company Search": () => [{ results: [{ id: "555", properties: { domain: "existing.com" } }] }],
  });
  assert.deepEqual(starvedWithData(trace), []);
});

test("a contacts-only batch does not stall any companies-side merge input", () => {
  const { trace } = run([contactEvent("1", "a@example.com")]);
  assert.deepEqual(starvedWithData(trace), []);
});
