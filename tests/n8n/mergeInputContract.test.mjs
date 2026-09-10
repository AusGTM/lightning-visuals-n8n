// tests/n8n/mergeInputContract.test.mjs
//
// Phase 70 Plan 10 (D-70-20/D-70-23) — the structural Merge-input contract, read from
// the connections map alone over every committed `n8n/wf_*.json`. This is the cheap,
// decisive instrument this plan's own objective promises: it is a pure graph property,
// needs no fixtures and no HTTP stubs, and it fails the moment a future generator
// change re-creates the defect class this plan retired.
//
// What each static rule encodes, in the live executions that motivated it:
//
//   - No Merge declares more than ten inputs: n8n's own Merge node caps declared
//     inputs at ten (`merge_node`'s own docstring, scripts/build_cloud_workflows.py).
//     "Build Response Merge" on the enrichment lane is split across two Merges for
//     exactly this reason (D-70-20); this rule is what would catch a future regression
//     back to one over-wide Merge.
//   - No node whose name marks it a sentinel has a direct edge to a Merge input: this
//     is the exact shape of executions 12203 (`Associate Carry Merge` fired 1x0, the
//     permitted row's real "associated" outcome came back "not_confirmed") and 12206
//     (`Enrichment Gate Merge` fired on a sentinel's own `[]`, `Build Response Merge`
//     never fired, the run reported success with zero rows) — a sentinel's own Code
//     node ALWAYS runs (fed the real lane's row set) and its empty OUTPUT still counts
//     as a delivery (the engine rule execution 12200 also established: a node fed ZERO
//     items never runs — the counterpart rule that makes a GATE possible at all,
//     D-70-23). `_add_starved_lane_sentinel` now wires "condition -> gate -> targets",
//     and the gate — never the sentinel's own Code node — is the only node with edges
//     to a Merge input.
//   - No routing IF has a direct edge to a Merge input: whether the live engine treats
//     an IF's own empty branch as a delivery is UNOBSERVED (D-70-01's addendum) — a
//     Merge input must not depend on the answer either way. Where this plan found the
//     shape on the ingest lane (`_retarget_merge_edge_through_passthrough`), a
//     pass-through now sits between the IF and the Merge input.
//   - Every declared Merge input has at least one producer: an input nothing feeds can
//     never fire (execution 12206's `Build Response Merge`, never fired, zero rows,
//     execution still reported `success`).
//
// Deliberately NOT asserted: that every Merge input has exactly one producer. Two
// producers sharing an input is legitimate and sometimes required when they are
// mutually exclusive — the credit collector on the enrichment lane already does it
// correctly (a fetched usage figure on one branch, a "check was skipped" marker on the
// other, never both in the same execution) — and D-70-23's own gated-sentinel mechanism
// is now a SECOND legitimate instance: a sentinel's gate and a real producer sharing one
// Merge input, safe because the gate makes NO delivery at all whenever the real producer
// would. Static analysis cannot tell a safe share from an unsafe one; only a replay can,
// because under the corrected walker a double delivery visibly loses rows (D-70-19's
// rule: the walker is corrected toward the engine, never toward the plans). Do not
// "tighten" this file into asserting one-producer-per-input — that would fail the two
// safe shares above and every future one shaped like them.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, loadWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const N8N_DIR = path.join(ROOT, "n8n");

// Every committed workflow this generator emits — no hardcoded per-workflow allowance
// other than PENDING below.
const WORKFLOW_FILES = fs.readdirSync(N8N_DIR)
  .filter((f) => f.startsWith("wf_") && f.endsWith(".json"))
  .sort();

// Phase 70 Plan 11 emptied this list: every committed workflow now satisfies the
// Merge-input contract. Recomputed and asserted EXACT below — a workflow added here
// that already satisfies the contract fails the test just as loudly as a workflow off
// the list that violates it, so the list cannot silently be repopulated later.
const PENDING = [].sort();

const SENTINEL_NAME_RE = /Sentinel$/;

/** Computes the structural violations named in this file's header for one committed
 * workflow. Returns `{overWide, sentinelDirect, ifDirect, unfed}` — each an array of
 * human-readable strings, empty when the workflow satisfies the contract. */
function structuralViolations(wf) {
  const nodesByName = new Map(wf.nodes.map((n) => [n.name, n]));
  const merges = wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge");
  const mergeNames = new Set(merges.map((m) => m.name));
  const conns = wf.connections || {};

  const overWide = [];
  for (const m of merges) {
    const ni = (m.parameters && m.parameters.numberInputs) || 2;
    if (ni > 10) overWide.push(`${m.name} declares ${ni} inputs (n8n's own cap is ten)`);
  }

  const fedInputs = new Map(merges.map((m) => [m.name, new Set()]));
  const sentinelDirect = [];
  const ifDirect = [];
  for (const [src, spec] of Object.entries(conns)) {
    const srcNode = nodesByName.get(src);
    for (const outs of (spec.main || [])) {
      for (const c of (outs || [])) {
        if (!mergeNames.has(c.node)) continue;
        fedInputs.get(c.node).add(c.index);
        if (SENTINEL_NAME_RE.test(src)) {
          sentinelDirect.push(`${src} -> ${c.node}[${c.index}] (sentinel's own Code node, not its gate)`);
        }
        if (srcNode && srcNode.type === "n8n-nodes-base.if") {
          ifDirect.push(`${src} -> ${c.node}[${c.index}] (routing IF, no pass-through)`);
        }
      }
    }
  }

  const unfed = [];
  for (const m of merges) {
    const ni = (m.parameters && m.parameters.numberInputs) || 2;
    const fed = fedInputs.get(m.name);
    for (let i = 0; i < ni; i += 1) {
      if (!fed.has(i)) unfed.push(`${m.name}[${i}] has no producer at all`);
    }
  }

  return { overWide, sentinelDirect, ifDirect, unfed };
}

function isEmpty(v) {
  return v.overWide.length === 0 && v.sentinelDirect.length === 0
    && v.ifDirect.length === 0 && v.unfed.length === 0;
}

// =====================================================================================
// Static rules, over every committed workflow.
// =====================================================================================

for (const file of WORKFLOW_FILES) {
  test(`${file}: Merge-input structural contract`, () => {
    const wf = loadWorkflow(path.join(N8N_DIR, file));
    const v = structuralViolations(wf);
    const onPending = PENDING.includes(file);
    if (onPending) {
      assert.ok(!isEmpty(v),
        `${file} is on the PENDING list but satisfies the contract — remove it, it converted`);
    } else {
      assert.ok(isEmpty(v),
        `${file} violates the Merge-input contract but is not on PENDING — convert it ` +
        `or add it:\n${JSON.stringify(v, null, 2)}`);
    }
  });
}

test("PENDING names exactly the workflows that violate the contract, in both directions", () => {
  const actual = WORKFLOW_FILES.filter((f) => {
    const wf = loadWorkflow(path.join(N8N_DIR, f));
    return !isEmpty(structuralViolations(wf));
  }).sort();
  assert.deepEqual(actual, PENDING,
    "the pending list must be exactly the set of workflows currently violating the " +
    "contract — emptying it is plan 70-11's acceptance");
});

// =====================================================================================
// Dynamic rule: a converted workflow, replayed on a single-lane batch, stalls no Merge
// and returns every input row exactly once at its response node. The structural rules
// above prove every declared input has SOME producer; only a replay proves a real
// execution actually delivers to it and that no input receives two competing real
// deliveries (D-70-19: the walker is the engine's own observed rule, not a guess).
//
// Every converted (non-PENDING) workflow is accounted for below by exactly one bucket —
// this is itself asserted, so a new workflow cannot silently fall through un-replayed
// and un-excused.
// =====================================================================================

const CONVERTED = WORKFLOW_FILES.filter((f) => !PENDING.includes(f));

// The walker's own supported trigger set (tests/n8n/lib/walkWorkflow.mjs's TRIGGER_TYPES
// — not exported, so mirrored here; a workflow whose only trigger is outside this set
// cannot be driven by this instrument at all).
const WALKER_TRIGGER_TYPES = new Set([
  "n8n-nodes-base.webhook",
  "n8n-nodes-base.scheduleTrigger",
  "n8n-nodes-base.executeWorkflowTrigger",
]);

function walkerSupportedTrigger(wf) {
  return wf.nodes.find((n) => WALKER_TRIGGER_TYPES.has(n.type)) || null;
}

function hasMergeNodes(wf) {
  return wf.nodes.some((n) => n.type === "n8n-nodes-base.merge");
}

// The walker runs every Code node's jsCode via a synchronous `new Function(...)` (the
// same mechanism n8n's own Code node uses, per walkWorkflow.mjs's own header) — a body
// containing `await` throws immediately, a walker limitation unrelated to the Merge-
// input contract this file checks.
function hasAwaitingCodeNode(wf) {
  return wf.nodes.some((n) =>
    n.type === "n8n-nodes-base.code" && /\bawait\s/.test(n.parameters.jsCode || ""));
}

const accountedFor = new Set();

// --- Bucket 1: no Merge nodes at all — the stall rule is vacuous. -------------------
for (const file of CONVERTED) {
  const wf = loadWorkflow(path.join(N8N_DIR, file));
  if (hasMergeNodes(wf)) continue;
  accountedFor.add(file);
  test(`${file}: no Merge nodes — the never-stalls rule is vacuously satisfied`, () => {
    assert.equal(hasMergeNodes(wf), false, `${file} was expected to carry zero Merge nodes`);
  });
}

// --- Bucket 2: no walker-supported trigger — static rules still apply, no replay. ---
for (const file of CONVERTED) {
  if (accountedFor.has(file)) continue;
  const wf = loadWorkflow(path.join(N8N_DIR, file));
  if (walkerSupportedTrigger(wf)) continue;
  accountedFor.add(file);
  test(`${file}: no walker-supported trigger — dynamic replay is not possible, structural rules stand alone`, () => {
    assert.equal(walkerSupportedTrigger(wf), null,
      `${file} was expected to have no trigger in ${[...WALKER_TRIGGER_TYPES].join(", ")}`);
  });
}

// --- Bucket 3: the walker cannot execute a Code node's jsCode (contains `await`). ---
for (const file of CONVERTED) {
  if (accountedFor.has(file)) continue;
  const wf = loadWorkflow(path.join(N8N_DIR, file));
  if (!hasAwaitingCodeNode(wf)) continue;
  accountedFor.add(file);
  test(`${file}: a Code node's jsCode contains 'await' — the walker's synchronous runner cannot execute it`, () => {
    assert.equal(hasAwaitingCodeNode(wf), true,
      `${file} was expected to carry at least one awaiting Code node`);
  });
}

// --- Bucket 4: replayed. -------------------------------------------------------------

test("wf_contact_ingest_cloud.json: single-lane batch (every row a review row, no association lane touched) stalls no Merge, every row returns once", () => {
  const file = "wf_contact_ingest_cloud.json";
  accountedFor.add(file);
  const wf = loadWorkflow(path.join(N8N_DIR, file));

  // Disarmed (committed) build: create is gated off, so a row resolving no existing
  // contact lands at "Set Review" rather than attempting a write — this is a genuine
  // single-lane batch on the ingest lane (research Pitfall 1's shape): the association
  // chain (IF Update/IF Create true branches, HubSpot Update/Create, Build Association
  // Request, the write gates, HubSpot Associate Company, Associate Carry Merge) never
  // runs at all this execution.
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: "one@example.com", firstname: "One", lastname: "Person", company: "One Co" },
      { email: "two@example.com", firstname: "Two", lastname: "Person", company: "Two Co" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{
        results: [
          { email: "one@example.com", status: "VALID" },
          { email: "two@example.com", status: "VALID" },
        ],
      }],
      "HubSpot Search by Email": [{ results: [] }, { results: [] }],
      "HubSpot Company Search by Domain": [{ results: [] }, { results: [] }],
      "HubSpot Company Search by Name": [{ results: [] }, { results: [] }],
      // Neither write node is stubbed: if the graph wrongly routed a row there, this
      // fixture throws (walkWorkflow.mjs's own documented contract) rather than
      // silently passing.
    },
  });

  // "Associate Carry Merge" is the one intentionally-bypassed carry Merge on this
  // batch shape (D-70-20/D-70-23): nothing is ever associated, so its own input never
  // arrives from "HubSpot Associate Company" — by design, not a hang, since nothing
  // downstream reads its output directly. What must never stall is every other Merge,
  // above all "Ingest Merge Response", the one this batch's correctness rests on.
  const unexpectedStalls = trace.stalled.filter((s) => s.node !== "Associate Carry Merge");
  assert.deepEqual(unexpectedStalls, [], "no merge other than the bypassed carry Merge may stall");
  assert.equal(trace.merges["Ingest Merge Response"] && trace.merges["Ingest Merge Response"].fired,
    true, "Ingest Merge Response must fire");

  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 2, "one response row per input row");
  const emails = rows.map((r) => r.email).sort();
  assert.deepEqual(emails, ["one@example.com", "two@example.com"]);
  for (const row of rows) {
    assert.equal(row.action, "review");
    assert.equal(row.association, "none");
  }
});

test("wf_review_decision_cloud.json: a dry-run companies decision stalls no Merge, one response row", () => {
  const file = "wf_review_decision_cloud.json";
  accountedFor.add(file);
  const wf = loadWorkflow(path.join(N8N_DIR, file));

  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Review Decision Webhook",
    triggerItems: [{ body: {
      object_type: "companies", record_id: "123", decision: "approve", dry_run: true,
    } }],
    httpStubs: { "Review Fetch By Id": [{ results: [{ id: "123", properties: { domain: "acme.example" } }] }] },
  });

  assert.deepEqual(trace.stalled, [], "no merge may stall on a dry-run companies decision");
  assert.equal(nodeItems(runData, "Build Review Response").length, 1, "one response row");
});

test("every CONVERTED workflow falls into exactly one bucket: no-merges, no-trigger, awaiting-code, or replayed", () => {
  const missing = CONVERTED.filter((f) => !accountedFor.has(f));
  assert.deepEqual(missing, [],
    "a converted workflow fell through without a replay or a documented exclusion — " +
    `add a bucket or a replay for: ${JSON.stringify(missing)}`);
  assert.deepEqual([...accountedFor].sort(), [...CONVERTED].sort(),
    "accountedFor must be exactly the converted set — no extra, no missing");
});
