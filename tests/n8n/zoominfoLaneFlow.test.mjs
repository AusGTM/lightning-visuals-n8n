// tests/n8n/zoominfoLaneFlow.test.mjs
//
// Phase 70 code review WR-07 — dynamic (walker-replay) cover for the ZoomInfo slice of
// the Merge/sentinel network. Before this file, the three ZoomInfo carry Merges
// ("ZoomInfo Mint Carry Merge", "ZoomInfo Mint Company Carry Merge", "ZoomInfo Usage
// Mint Carry Merge"), their D-70-20 pass-throughs and the "Collect Credits" credit lane
// were checked ONLY by the static structural contract (assert_merge_input_contract:
// every input has a producer, no over-wide Merge). Static analysis can prove an input is
// fed by SOMETHING; only a replay can prove a sentinel and its lane's real producer are
// mutually exclusive — mergeInputContract.test.mjs's own header says exactly that.
//
// Two things kept this lane out of every replay: no test set `providers` at all, so
// "IF ZoomInfo Enabled" always took its false branch; and the three provider-call Code
// nodes ("ZoomInfo Enrich", "ZoomInfo Company", "ZoomInfo Usage") `await`, which the
// walker cannot execute. `codeStubs` (walkWorkflow.mjs) closes the second — the same
// substitution `httpStubs` already makes for an HTTP hop, fenced in both directions so
// it can never stand in for executable jsCode.
//
// NOTE: this replays the repo's OWN committed workflow jsCode/expressions via `new
// Function` — the same mechanism n8n's Code/IF nodes use at runtime — over trusted,
// in-repo JSON. No external or untrusted input is ever interpolated into a function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { walkWorkflow, loadWorkflow, codeNodeAwaits } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

const load = () => loadWorkflow(WF_PATH);

// The three carry Merges this finding is about, each with the producer pair that may
// legitimately claim its two inputs: the real Mint HTTP response on input 0, and the
// carried row (the pass-through off the SAME "needs mint" true branch) on input 1.
const CARRY_MERGES = {
  "ZoomInfo Mint Carry Merge": [
    "ZoomInfo Mint",
    "IF ZoomInfo Needs Mint -> ZoomInfo Mint Carry Merge Pass-Through",
  ],
  "ZoomInfo Mint Company Carry Merge": [
    "ZoomInfo Mint Company",
    "IF ZoomInfo Company Needs Mint -> ZoomInfo Mint Company Carry Merge Pass-Through",
  ],
  "ZoomInfo Usage Mint Carry Merge": [
    "ZoomInfo Usage Mint",
    "IF ZoomInfo Usage Needs Mint -> ZoomInfo Usage Mint Carry Merge Pass-Through",
  ],
};

const AWAITING_CODE_NODES = ["ZoomInfo Enrich", "ZoomInfo Company", "ZoomInfo Usage"];

// ZoomInfo (Okta) issues short-lived bearer tokens and the lane re-mints when one is
// spent — `needsMint` treats a token expiring within 60s as already gone. `expiresIn`
// therefore decides how many lanes mint: omit it (the gate's conservative 5-minute
// default) and the first lane to need a token mints for all three; pass a lifetime
// inside the skew and every lane mints its own, which is what exercises all three carry
// Merges in their FIRED shape.
function baseStubs(expiresIn) {
  const token = expiresIn === undefined
    ? [{ access_token: "tok" }]
    : [{ access_token: "tok", expires_in: expiresIn }];
  return {
    "HubSpot Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search Fallback": (items) => items.map(() => ({ results: [] })),
    "HubSpot Linkedin Search": (items) => items.map(() => ({ results: [] })),
    "Lusha Enrich": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Match": (items) => items.map(() => ({})),
    "ZoomInfo Mint": token,
    "Contact Web Research": (items) => items.map(() => ({})),
    "Contact Judge Call": (items) => items.map(() => ({})),
    "HubSpot Create": (items) => items.map(() => ({ id: "999", properties: {} })),
    "HubSpot Update": (items) => items.map(() => ({ id: "111", properties: {} })),
    "HubSpot Company Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Company Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Company Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "Lusha Company": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Org": (items) => items.map(() => ({})),
    "ZoomInfo Mint Company": token,
    "Claude Web Research": (items) => items.map(() => ({})),
    "Judge Call": (items) => items.map(() => ({})),
    "HubSpot Company Create": (items) => items.map(() => ({ id: "888", properties: {} })),
    "HubSpot Company Update": (items) => items.map(() => ({ id: "888", properties: {} })),
    "Lusha Usage": [{}],
    "Apollo Usage": [{}],
    "ZoomInfo Usage Mint": token,
    "HubSpot List By Name": [{}],
    "HubSpot List Memberships": [{}],
  };
}

// A provider call that matched nothing. The lane's ROUTING is what this file replays —
// what ZoomInfo answered is the business of the provider-adapter tests.
function baseCodeStubs() {
  return {
    "ZoomInfo Enrich": (items) => items.map((item) => ({ ...item, zoominfo: { matched: false } })),
    "ZoomInfo Company": (items) => items.map((item) => ({ ...item, zoominfo: { matched: false } })),
    "ZoomInfo Usage": (items) => items.map((item) => ({ ...item, zoom_usage: {} })),
  };
}

const EVENTS = [
  { objectId: "1", objectType: "contact", email: "a@b.com", run_id: "case" },
  { objectId: "2", objectType: "company", domain: "example.test", run_id: "case" },
];

function run(providers, { codeStubs = baseCodeStubs(), expiresIn } = {}) {
  return walkWorkflow(load(), {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: { providers, events: EVENTS } }],
    httpStubs: baseStubs(expiresIn),
    codeStubs,
  });
}

// A token already inside the gate's 60-second re-mint skew: every ZoomInfo lane mints
// its own rather than reusing a sibling lane's cached one.
const SHORT_LIVED = { expiresIn: 1 };

// Row IDENTITY, not row content: enriching through ZoomInfo legitimately puts
// ZoomInfo-shaped fields (a minted token, a per-provider credit entry) ON a row. What
// must not move is WHICH rows reach the result channel, and with what verdict.
const responseRowIdentities = (runData) => (runData["Build Response"] || []).flat()
  .map((row) => ({
    id: row.object_id ?? row.hs_object_id ?? null,
    object_type: row.object_type,
    action: row.action,
  }));

// =============================================================================================
// The premise: the lane really is await-bearing, and the walker refuses it by name.
// =============================================================================================

test("exactly the three ZoomInfo provider-call Code nodes await — the walker's own reason this lane went unreplayed", () => {
  // `codeNodeAwaits` is the walker's OWN predicate — the one the fence uses — so this
  // premise cannot drift from the mechanism it justifies.
  const awaiting = load().nodes
    .filter((n) => n.type === "n8n-nodes-base.code" && codeNodeAwaits(n))
    .map((n) => n.name);
  assert.deepEqual(awaiting.sort(), [...AWAITING_CODE_NODES].sort(),
    "if this set changes, the codeStubs below cover the wrong nodes");
});

test("an await-bearing Code node reached with no stub throws by name, never an opaque SyntaxError", () => {
  assert.throws(() => run(["zoominfo"], { codeStubs: {} }), (error) => {
    assert.match(error.message, /awaits/);
    assert.match(error.message, /codeStubs/);
    assert.ok(AWAITING_CODE_NODES.some((name) => error.message.includes(name)), error.message);
    return true;
  });
});

test("a codeStub for a Code node the walker CAN run is refused — a stub never stands in for executable jsCode", () => {
  assert.throws(
    () => run(["zoominfo"], {
      codeStubs: { ...baseCodeStubs(), "ZoomInfo Token Gate": [{ zoom_needs_mint: false }] },
    }),
    /ZoomInfo Token Gate has no await/);
});

// =============================================================================================
// Lane live: the carry Merges' inputs, claimed by their real producers.
// =============================================================================================

test("lane live: ALL THREE ZoomInfo carry Merges fire, each claimed on both inputs by its own producer pair", () => {
  const { trace } = run(["zoominfo"], SHORT_LIVED);

  assert.deepEqual(trace.stalled, [], "no lane may be left waiting on an input nobody feeds");

  for (const [name, [mintNode, passThrough]] of Object.entries(CARRY_MERGES)) {
    const merge = trace.merges[name];
    assert.ok(merge && merge.fired, `${name} did not fire — this lane went unreplayed`);
    assert.equal(merge.sources[0], mintNode, `${name} input 0`);
    assert.equal(merge.sources[1], passThrough, `${name} input 1`);
    // A carry Merge combines by POSITION: unequal counts would silently pair a row with
    // another row's HTTP response, which is the whole reason the carry exists.
    assert.equal(merge.itemCounts[0], merge.itemCounts[1], `${name} pairs 1:1`);
  }
});

test("lane live: a still-valid cached token bypasses a carry Merge entirely, and starves nothing", () => {
  // The other half of the shape. The token cache is workflow-global, so with a normal
  // lifetime the first ZoomInfo lane to need a token mints for all of them and the
  // remaining lanes take their IF's false branch straight past the carry Merge. A
  // bypassed Merge that never fires must not leave anything waiting on it — the failure
  // this whole sentinel network exists to prevent.
  const { trace } = run(["zoominfo"]);

  assert.deepEqual(trace.stalled, []);
  const fired = Object.keys(CARRY_MERGES).filter((name) => (trace.merges[name] || {}).fired);
  assert.equal(fired.length, 1,
    "one lane mints on a cold cache and the rest reuse it; which one is an ordering detail");
});

test("lane live: Collect Credits input 2 is claimed by the real ZoomInfo usage adapter, never its skip sentinel", () => {
  const { trace } = run(["zoominfo"]);
  const credits = trace.merges["Collect Credits"];

  assert.ok(credits.fired, "Collect Credits must fire — a starved input hangs the credit lane");
  assert.equal(credits.sources[2], "Adapt ZoomInfo Usage");
  // The two providers this run did NOT request are the mirror image, which is what makes
  // the assertion above a real exclusion rather than a coincidence.
  assert.equal(credits.sources[0], "Lusha Credit Skipped");
  assert.equal(credits.sources[1], "Apollo Credit Skipped");
});

// =============================================================================================
// Lane dead: nothing on the ZoomInfo lane runs, and the sentinel takes the slot instead.
// =============================================================================================

test("lane dead: no ZoomInfo carry Merge fires and no ZoomInfo call is made", () => {
  const { runData, trace } = run(["lusha"]);

  assert.deepEqual(trace.stalled, []);
  for (const name of Object.keys(CARRY_MERGES)) {
    const merge = trace.merges[name];
    assert.ok(!merge || !merge.fired, `${name} must not fire when ZoomInfo is not requested`);
  }
  for (const name of [...Object.values(CARRY_MERGES).map(([mint]) => mint), ...AWAITING_CODE_NODES]) {
    assert.ok(!runData[name], `${name} ran with ZoomInfo not requested`);
  }

  const credits = trace.merges["Collect Credits"];
  assert.ok(credits.fired);
  assert.equal(credits.sources[2], "ZoomInfo Credit Skipped",
    "the skip sentinel takes the slot precisely when the real lane cannot");
});

test("the ZoomInfo lane changes what enriched a row, never which rows come back", () => {
  // A differential, so it pins the lane's effect on the result channel rather than
  // endorsing any particular baseline row set (that is the convergence tests' subject).
  assert.deepEqual(responseRowIdentities(run(["zoominfo"]).runData),
                   responseRowIdentities(run(["lusha"]).runData));
});
