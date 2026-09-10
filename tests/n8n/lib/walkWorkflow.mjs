// walkWorkflow.mjs — a connections-driven offline interpreter for committed n8n workflow
// JSON (D-70-16, D-70-18 — .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/).
//
// Generalises tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs's `makeDollar`/
// `runOneNodeRun` (hand-fed per-test run history, single node) and
// tests/n8n/researchChainRowFlow.test.mjs's fuller `new Function` signature (a fixed
// in-repo chain, still hand-walked) into ONE interpreter that drives `wf.connections`
// itself and computes run history, rather than having each test author it by hand. Every
// later Phase 70 plan's acceptance is "the walker replays the committed JSON and every row
// comes back once" — this module is that instrument, and this module is superseded-from
// (not deleted) by the two seed files above; they are retired separately in plan 70-04
// when nodeRunRecovery.js itself is deleted.
//
// This runs committed `jsCode` via `new Function` — the SAME mechanism n8n's own Code
// node uses at runtime (researchChainRowFlow.test.mjs's header note, restated here) — over
// repo-controlled JSON, never attacker-controlled input (T-70-09, accepted).
//
// Core semantic (n8n/code/nodeRunRecovery.js's header is the in-repo statement of this):
// a node with MORE THAN ONE inbound connection runs ONCE PER FIRING INBOUND EDGE-RUN, not
// once on a merged item array. This is exactly what produces the F5 collapse when a
// downstream reader recovers its upstream BY NAME with a bare last-run accessor — see
// tests/n8n/walkWorkflow.test.mjs's "collapse case", this walker's own RED evidence
// (D-70-18: no historical RED was taken against the pre-Phase-70 JSON; the walker's
// ability to SEE the defect class is proven on synthetic graphs instead).

import fs from "node:fs";
import path from "node:path";

// --- node type sets ---------------------------------------------------------------

const TRIGGER_TYPES = new Set([
  "n8n-nodes-base.webhook",
  "n8n-nodes-base.scheduleTrigger",
  "n8n-nodes-base.executeWorkflowTrigger",
]);
const HTTP_TYPES = new Set(["n8n-nodes-base.httpRequest", "n8n-nodes-base.hubspot"]);
// ponytail: `extractFromFile`'s real job (binary CSV -> per-row JSON) is n8n's own
// well-tested built-in decode, not workflow business logic — modelling it here would
// mean re-implementing a CSV parser to prove nothing about the graph. Treated as an
// opaque identity boundary: a fixture seeds the trigger with ALREADY-"extracted" row
// items, and this node passes them through unchanged. Explicitly named here (not left to
// the generic "any other type" fallback) so it never pollutes `trace.unhandledTypes` for
// a real ingest replay. Upgrade path: a real CSV/XLSX decode if a workflow ever needs the
// walker itself to prove something about extraction.
const PASSTHROUGH_TYPES = new Set(["n8n-nodes-base.noOp", "n8n-nodes-base.extractFromFile"]);

// --- loading -----------------------------------------------------------------------

export function loadWorkflow(relPath) {
  const abs = path.isAbsolute(relPath) ? relPath : path.resolve(process.cwd(), relPath);
  return JSON.parse(fs.readFileSync(abs, "utf8"));
}

// nodeItems(runData, name) — concatenates every run of a node in order. The JS twin of
// operator-claude-plugin/scripts/report.py::all_node_items, which proved live (executions
// 12096/12098) that reading only the LAST run silently drops rows from earlier runs.
export function nodeItems(runData, name) {
  const runs = runData[name] || [];
  return runs.flat();
}

function unwrapJson(it) {
  return it && it.json !== undefined ? it.json : it;
}

// --- tiny n8n expression evaluation (IF conditions, Set assignments) ---------------

// Evaluates a `={{ ... }}`-shaped n8n expression string against one item's $json. Only
// the WHOLE-STRING `{{ ... }}` shape is supported (the only shape this repo's committed
// workflows use for IF/Set values) — ponytail: a mixed literal+`{{ }}` template string
// would need real template splicing; add it if a workflow ever needs it.
// Phase 70 Plan 03 (Rule 3 — blocking issue): the enrichment lane's real IF nodes
// (`IF Bare Event`, `IF Has Email`, `IF Name Searchable`, ...) use `$('Node').item`/
// `.first()` inside their condition expressions — `evalExpr` only ever injected
// `$json`, so evaluating any of them threw `$ is not defined` before a single
// enrichment-lane test could run. `ctx` (the SAME `{runData, runIndex, ...}` `runCode`
// already threads through) is now optional here too: `$` resolves via the SAME
// `makeDollar` `.item`/`.first()`/`.all()` contract Code nodes get, keyed off the
// CURRENT node's own run index — never a second, divergent resolver.
function evalExpr(exprStr, item, ctx) {
  const m = /^\{\{([\s\S]*)\}\}$/.exec(String(exprStr).trim());
  if (!m) return exprStr;
  const dollar = ctx
    ? makeDollar(ctx.runData, ctx.runIndex)
    : function $() { throw new Error("$(...) used in an expression evaluated with no ctx"); };
  const fn = new Function("$json", "$", `"use strict"; return (${m[1]});`);
  return fn(item || {}, dollar);
}

function resolveValue(raw, item, ctx) {
  if (typeof raw !== "string") return raw;
  if (!raw.startsWith("=")) return raw;
  return evalExpr(raw.slice(1), item, ctx);
}

function applyOperator(operator, left, right, caseSensitive) {
  const type = (operator && operator.type) || "string";
  const operation = (operator && operator.operation) || "equals";
  if (operation === "exists") return left !== undefined && left !== null;
  if (operation === "notExists") return left === undefined || left === null;
  if (type === "number") {
    const l = Number(left);
    const r = Number(right);
    switch (operation) {
      case "equals": return l === r;
      case "notEquals": return l !== r;
      case "gt": return l > r;
      case "lt": return l < r;
      case "gte": return l >= r;
      case "lte": return l <= r;
      default: return l === r;
    }
  }
  if (type === "boolean") {
    switch (operation) {
      case "false": return Boolean(left) === false;
      case "true":
      default: return Boolean(left) === true;
    }
  }
  // string (default)
  let l = left === undefined || left === null ? "" : String(left);
  let r = right === undefined || right === null ? "" : String(right);
  if (caseSensitive === false) { l = l.toLowerCase(); r = r.toLowerCase(); }
  switch (operation) {
    case "notEquals": return l !== r;
    case "contains": return l.includes(r);
    case "notContains": return !l.includes(r);
    case "equals":
    default: return l === r;
  }
}

function evaluateIfConditions(conditionsParam, item, ctx) {
  const combinator = (conditionsParam && conditionsParam.combinator) || "and";
  const list = (conditionsParam && conditionsParam.conditions) || [];
  const caseSensitive = conditionsParam && conditionsParam.options
    ? conditionsParam.options.caseSensitive
    : undefined;
  if (list.length === 0) return true;
  const results = list.map((cond) => {
    const left = resolveValue(cond.leftValue, item, ctx);
    const right = resolveValue(cond.rightValue, item, ctx);
    return applyOperator(cond.operator, left, right, caseSensitive);
  });
  return combinator === "or" ? results.some(Boolean) : results.every(Boolean);
}

// --- `$` resolver --------------------------------------------------------------------

// makeDollar mirrors enrichmentGateRunRecoveryFlow.test.mjs's `makeDollar` seed exactly
// for `.all(branch, run)` (bare `.all()` -> most recent run — n8n's own documented
// contract), then adds `.first()`/`.last()`/`.item` per D-70-16's requirement.
// `selfRunIndex` is the CURRENTLY EXECUTING node's own run index (not the referenced
// node's) — `.item` pairs positionally against it, per research Open Question 3 /
// Pitfall 4: this walker resolves `.item` to the referenced node's run at the SAME index
// as the reader's own current run, first item of that run.
function makeDollar(runData, selfRunIndex) {
  return function $(name) {
    const runs = runData[name];
    function resolveRun(run) {
      if (!runs) throw new Error(`no node named ${name}`);
      const r = run === undefined ? runs.length - 1 : run;
      if (r < 0 || r >= runs.length) throw new Error(`no run ${r} for ${name}`);
      return runs[r];
    }
    return {
      all(_branch, run) { return resolveRun(run).map((j) => ({ json: j })); },
      first() { const arr = (runs && runs[runs.length - 1]) || []; return { json: arr[0] }; },
      last() { const arr = (runs && runs[runs.length - 1]) || []; return { json: arr[arr.length - 1] }; },
      get item() {
        const arr = (runs && (runs[selfRunIndex] !== undefined ? runs[selfRunIndex] : runs[runs.length - 1])) || [];
        return { json: arr[0] };
      },
    };
  };
}

// --- one node run --------------------------------------------------------------------

// A Code node whose body contains `await` cannot be driven by `new Function` (that
// constructor builds a SYNCHRONOUS function, so the body is a SyntaxError). Three nodes
// in n8n/wf_enrichment_cloud.json are in that shape — every one of them a provider call
// awaiting `this.helpers.httpRequest`, i.e. the same network hop `httpStubs` already
// stands in for at an HTTP node. `codeStubs` is that same substitution for that same
// reason, and is deliberately fenced so it can never become a way to skip executable
// logic (D-70-19: the walker may only gain fidelity toward the engine):
//   - an await-bearing Code node reached with NO stub throws by name, naming this
//     option — previously an opaque SyntaxError from deep inside `new Function`;
//   - a stub supplied for a Code node the walker CAN run throws too, so real committed
//     jsCode is always executed rather than replaced by a test's expectation.
const AWAIT_RE = /(^|[^.\w$])await\s/;

export function codeNodeAwaits(node) {
  return AWAIT_RE.test((node.parameters && node.parameters.jsCode) || "");
}

function runCode(node, items, ctx) {
  const stub = (ctx.codeStubs || {})[node.name];
  if (stub !== undefined) {
    if (!codeNodeAwaits(node)) {
      throw new Error(
        `codeStubs must not stand in for an executable Code node: ${node.name} has no ` +
        `await in its jsCode, so the walker runs its real body — delete the stub`);
    }
    const raw = typeof stub === "function" ? stub(items, node) : stub;
    return (raw || []).map(unwrapJson);
  }
  if (codeNodeAwaits(node)) {
    throw new Error(
      `Code node ${node.name} awaits — the walker runs Code bodies synchronously and ` +
      `cannot execute it. Supply codeStubs[${JSON.stringify(node.name)}] (the same ` +
      `substitution httpStubs makes for an HTTP hop) to replay a lane through it.`);
  }
  const $ = makeDollar(ctx.runData, ctx.runIndex);
  const $input = {
    all: () => items.map((j) => ({ json: j })),
    first: () => ({ json: items[0] }),
    last: () => ({ json: items[items.length - 1] }),
    get item() { return { json: items[0] }; },
  };
  const $json = items[0];
  const $node = { name: node.name };
  const now = new Date();
  const $getWorkflowStaticData = () => ctx.staticData;
  // Phase 70 Plan 03 (Rule 3 — blocking issue): `n8n/code/nodeRunRecovery.js`'s
  // `recoverConvergedRun` (still present at several HTTP-hop carry-read sites this plan
  // deliberately leaves alone — those are 70-04's job) reads n8n's own built-in
  // `$runIndex` global. Never injected before because no enrichment-lane node had been
  // walked yet. `ctx.runIndex` is the SAME value `makeDollar`'s `.item` already uses for
  // this node's own current run.
  const $runIndex = ctx.runIndex;
  const fn = new Function(
    "$", "$input", "$json", "$node", "$now", "$today", "$getWorkflowStaticData", "$env",
    "$runIndex",
    `"use strict";\n${node.parameters.jsCode}`
  );
  const out = fn($, $input, $json, $node, now, now, $getWorkflowStaticData, ctx.env || {}, $runIndex) || [];
  return out.map(unwrapJson);
}

function runSet(node, items) {
  const p = node.parameters || {};
  const v2 = (p.assignments && p.assignments.assignments) || [];
  if (v2.length) {
    return items.map((item) => {
      const next = { ...item };
      for (const a of v2) next[a.name] = resolveValue(a.value, item);
      return next;
    });
  }
  const v1 = p.values || {};
  const flat = [].concat(v1.string || [], v1.number || [], v1.boolean || []);
  if (flat.length) {
    return items.map((item) => {
      const next = { ...item };
      for (const a of flat) next[a.name] = resolveValue(a.value, item);
      return next;
    });
  }
  return items;
}

/**
 * runNode(node, inputItems, ctx) — one execution of a single (non-merge, non-respond,
 * non-trigger) node against a batch of plain (unwrapped) input items. Returns
 * `{outputs: [[...items], ...]}` — one array per output branch (index 0 is the sole
 * branch for most node types; `n8n-nodes-base.if` produces `[trueItems, falseItems]`).
 * Sets `unhandled: true` when the node's type is not one this walker models, so an
 * unmodelled type is visible on `trace.unhandledTypes` rather than silently passed
 * through (T-70-07).
 *
 * `ctx`: `{ runData, httpStubs, staticData, env, runIndex }`.
 */
export function runNode(node, items, ctx) {
  const type = node.type;
  if (type === "n8n-nodes-base.code") {
    return { outputs: [runCode(node, items, ctx)] };
  }
  if (type === "n8n-nodes-base.if") {
    const trueItems = [];
    const falseItems = [];
    for (const item of items) {
      const ok = evaluateIfConditions(node.parameters && node.parameters.conditions, item, ctx);
      (ok ? trueItems : falseItems).push(item);
    }
    return { outputs: [trueItems, falseItems] };
  }
  if (HTTP_TYPES.has(type)) {
    const stub = (ctx.httpStubs || {})[node.name];
    if (stub === undefined) {
      throw new Error(`unstubbed HTTP node: ${node.name}`);
    }
    const raw = typeof stub === "function" ? stub(items, node) : stub;
    return { outputs: [(raw || []).map(unwrapJson)] };
  }
  if (type === "n8n-nodes-base.set") {
    return { outputs: [runSet(node, items)] };
  }
  if (PASSTHROUGH_TYPES.has(type)) {
    return { outputs: [items] };
  }
  return { outputs: [items], unhandled: true };
}

// --- the walker ------------------------------------------------------------------------

/**
 * walkWorkflow(wf, opts) — replays `wf` from its own `connections` map.
 *
 * opts:
 *   triggerNode: string — the ONE trigger node to seed (a real execution has one entry
 *     point; seeding more than one would show a convergence receiving items on every
 *     inbound edge and pass a graph that actually hangs live — see
 *     n8n/wf_enrichment_cloud.json's webhook + Execute Workflow Trigger pair).
 *   triggerItems: array of plain (unwrapped) items to seed that trigger with.
 *   httpStubs: { [nodeName]: array | (inputItems, node) => items } — an unstubbed HTTP
 *     node throws by name (never silently returns []), so a test cannot pass on an
 *     unmodelled hop.
 *   codeStubs: { [nodeName]: array | (inputItems, node) => items } — the same
 *     substitution for a Code node whose body `await`s (the walker runs Code bodies
 *     synchronously and cannot execute one). Both directions throw: an await-bearing
 *     Code node with no stub, and a stub for a node the walker could have run.
 *   allowLegacy: boolean (default falsey) — D-70-30 (gap-closure round 3, plan 70-16).
 *     The ONLY escape from the non-v1 refusal below. Reserved for
 *     tests/n8n/walkerEngineFidelity.test.mjs's frozen fixtures — RECORDED legacy-engine
 *     divergences from executions 12203, 12206 and 12316, all on bodies whose settings
 *     carried no execution order. NOT a supported mode for any graph this repo
 *     generates: every committed n8n/wf_*.json runs on v1 (D-70-28), and every synthetic
 *     graph this test suite builds now declares v1 too (`wf()`'s settings default).
 *
 * Returns `{ runData, trace }`. `trace.unhandledTypes`, `trace.respond`,
 * `trace.respondSuppressed`, `trace.trigger`, `trace.orderingUsed` — see 70-01-PLAN.md —
 * plus `trace.merges` (Phase 70 plan 70-09, extended by quick task 260911-0tz's v1
 * fidelity work): per Merge node, `{fired, sources, itemCounts, runs}`. `runs` is the
 * primary representation — `[{sources, itemCounts}, ...]` in fire order — under v1 a Merge
 * can fire more than once per execution (see propagate()'s rule (c) note below and the
 * v1 end-of-run drain). `fired` (now "at least one run fired"), `sources` and
 * `itemCounts` are RETAINED and carry run 0's values, for six existing consumer files
 * that read the flat shape. Added because the defect executions 12203 and 12206 exposed
 * is invisible in item counts alone: which node took input 0 IS the finding.
 *
 * `trace.stalled` — see the BL-01 comment above the v1 stall pass below (quick task
 * 260911-1z5): the v1 shapes it can report are NOT, on their own, evidence of a lost
 * row — read `starvedWithData(trace)` (exported below) for that question, never
 * `trace.stalled` directly, on a v1 walk.
 *
 * Throws (D-70-30) when `wf.settings.executionOrder` is not `"v1"` and `opts.allowLegacy`
 * was not passed — this walker models the v1 contract only; it does not, and after
 * G-70-6 must not, claim to model the legacy engine the retired bodies ran on.
 */
export function walkWorkflow(wf, opts) {
  const { triggerNode, triggerItems, httpStubs = {}, codeStubs = {}, env = {}, allowLegacy } = opts || {};
  const nodesByName = {};
  for (const n of wf.nodes || []) nodesByName[n.name] = n;

  const triggerNodeObj = nodesByName[triggerNode];
  if (!triggerNodeObj) throw new Error(`trigger node not found: ${triggerNode}`);

  const outgoing = wf.connections || {};
  const order = wf.settings && wf.settings.executionOrder === "v1" ? "v1" : "legacy";

  // D-70-30 (gap-closure round 3, plan 70-16): refuse a non-v1 body unless the caller
  // explicitly opts into the one documented escape. G-70-6 retired the legacy body this
  // walker used to silently fall back to modelling; from here on, silence is a bug, not
  // a default.
  if (order !== "v1" && !allowLegacy) {
    throw new Error(
      `walkWorkflow: settings.executionOrder = ${JSON.stringify(wf.settings && wf.settings.executionOrder)}, ` +
      `want "v1" — D-70-30: this walker models n8n's v1 execution order only. Pass ` +
      `allowLegacy explicitly if this is a recorded legacy-engine fixture ` +
      `(walkerEngineFidelity.test.mjs only) — never for a graph this repo generates.`
    );
  }

  const runData = {};
  const staticData = {};
  const trace = {
    orderingUsed: order,
    unhandledTypes: [],
    stalled: [],
    respond: null,
    respondSuppressed: [],
    trigger: triggerNode,
  };

  // mergeState: nodeName -> the LEGACY single-fire shape ({buffers, arrived, sources,
  // fired}) or the v1 run-indexed shape ({pending, runs}) — see the two branches in the
  // walk loop below. Never both on the same node: `order` is fixed for the whole walk.
  const mergeState = {};

  let queue = [];
  function enqueue(delivery) { queue.push(delivery); }
  function dequeue() { return order === "v1" ? queue.pop() : queue.shift(); }

  function connectionsFrom(name, outputIndex) {
    const perNode = outgoing[name];
    return (perNode && perNode.main && perNode.main[outputIndex]) || [];
  }

  // mergeBuffers(node, buffers, numberInputs) — the append / combineByPosition /
  // combineAll MATHS, extracted (quick task 260911-0tz, plan Step 3b) so both the legacy
  // arrival state machine and the v1 run-indexed one share it; only the ARRIVAL/
  // first-wins/discard state machine differs between them, never this. `buffers[i]` may
  // be absent (the v1 end-of-run drain can fire a run with an unfilled input) — an absent
  // input contributes `[]` to the maths, exactly as D-70-30's rule (c) v1 flip requires.
  function mergeBuffers(node, buffers, numberInputs) {
    // D-70-04 (Phase 70 Plan 02): `mode: "combine"` + `combineBy: "combineByPosition"`
    // pairs item i of every input into ONE shallow-merged object (n8n's own
    // combineByPosition.ts, verified 2026-09-09) rather than concatenating them as
    // separate items — needed for the carry-merge's re-attach-fields use. Every OTHER
    // mode this repo uses (absent, or explicit "append") keeps the original
    // concatenation behaviour; existing 70-01 fixtures never set `mode` at all, so
    // this is additive, not a change to their semantics.
    const combineByValue = node.parameters && node.parameters.mode === "combine"
      ? (node.parameters.combineBy || "combineByFields")
      : null;
    const isCombineByPosition = combineByValue === "combineByPosition";
    // Phase 70 Plan 02 Task 3 (D-70-04): "combineAll" — the cartesian product across
    // every input, used for a genuine 1-to-N broadcast (one config item onto every
    // row), never for a per-item HTTP hop (that stays combineByPosition). n8n's own
    // Merge node exposes this as a third `combineBy` value alongside the two above
    // (merge_node's own docstring, Task 2's source citation).
    const isCombineAll = combineByValue === "combineAll";
    if (isCombineByPosition) {
      // Last input wins a key clash (this repo's carry-merges always wire the
      // CARRIED ROW last and set `resolveClash: "preferLast"` — see
      // scripts/build_cloud_workflows.py's `merge_node` docstring), never n8n's own
      // combineByPosition default (`addSuffix`, which renames the clashing keys).
      const counts = [];
      for (let i = 0; i < numberInputs; i += 1) counts.push((buffers[i] || []).length);
      const n = Math.min(...counts);
      const merged = [];
      for (let i = 0; i < n; i += 1) {
        let combined = {};
        for (let inp = 0; inp < numberInputs; inp += 1) combined = { ...combined, ...(buffers[inp] || [])[i] };
        merged.push(combined);
      }
      return merged;
    }
    if (isCombineAll) {
      // Cartesian product across all configured inputs, same last-input-wins clash
      // rule as combineByPosition above.
      let combos = [{}];
      for (let inp = 0; inp < numberInputs; inp += 1) {
        const next = [];
        for (const base of combos) {
          for (const it of (buffers[inp] || [])) next.push({ ...base, ...it });
        }
        combos = next;
      }
      return combos;
    }
    const merged = [];
    for (let i = 0; i < numberInputs; i += 1) merged.push(...(buffers[i] || []));
    return merged;
  }

  // requiredInputsFor(node) — n8n Merge v3.2's per-mode gate for the v1 end-of-run drain
  // (Step 3c): `1` for every `append`/`combine` Merge this repo's builder emits
  // (packages/nodes-base/nodes/Merge/v3/actions/versionDescription.ts, `requiredInputs`).
  // `chooseBranch` (`requiredInputs: [0, 1]`) is not modelled — this repo emits none
  // today — and THROWS by node name rather than guess, per the plan's own instruction.
  function requiredInputsFor(node) {
    const mode = node.parameters && node.parameters.mode;
    if (mode === "chooseBranch") {
      throw new Error(
        `walkWorkflow: Merge node "${node.name}" uses mode "chooseBranch" ` +
        `(requiredInputs [0, 1]) — not modelled, this repo emits none today`);
    }
    return 1;
  }

  function propagate(fromName, outputIndex, items) {
    const node = nodesByName[fromName];
    let outItems = items;
    // The always-output-data substitution is UNCHANGED and models a different rule from
    // the one below: a node that RAN and produced nothing, whose AOD flag forces one
    // empty marker item onto the wire. Live evidence it is still the right model:
    // execution 12200 (70-UAT.md § Test 1), where "HubSpot Associate Company" never ran
    // at all and its own alwaysOutputData contributed nothing.
    if (outItems.length === 0 && node && node.alwaysOutputData === true) {
      outItems = [{}];
    }
    // D-70-30 rule (c) — OBSERVED 2026-09-10 (Gate 11, executions 12354/12355/12356,
    // frozen at `tests/n8n/fixtures/frozen/exec_1235{4,5,6}.runData.json`, pinned by
    // `tests/n8n/v1RuntimeRecordings.test.mjs`, reproduced by walking the frozen v1 graph
    // in `tests/n8n/walkerEngineFidelityV1.test.mjs`, quick task 260911-0tz): under v1, a
    // node that RAN and emitted ZERO items makes NO DELIVERY to its targets — `Merge
    // Company` ran with 0 items into `Decide Company Action Merge` input 1 and never
    // appeared in that Merge's `source`, on any of the three recordings. This is the
    // OPPOSITE of the legacy rule below, and the two are kept as explicit branches on
    // `order` (not one patched state machine) so the three legacy fixtures in
    // `walkerEngineFidelity.test.mjs` (12203/12206/12316) keep meaning what they meant
    // when they were written.
    //
    // LEGACY (executions 12203 and 12206, 70-UAT.md § Tests 2 and 3; D-70-20; both ran on
    // bodies whose `settings.executionOrder` was ABSENT): a node that ran and emitted
    // ZERO items STILL delivers — the runData `source` arrays of both executions name a
    // sentinel whose output was `[]` as the producer that took a Merge input. What this
    // walker calls a "delivery" there may in fact have been the legacy `addEmptyItem`
    // push (`addNodeToBeExecuted`, `packages/core/src/execution-engine/workflow-
    // execute.ts`) rather than a genuine zero-item delivery — the two are
    // indistinguishable from runData alone, and the legacy branch models the OBSERVED
    // OUTCOME either way, never the mechanism behind it.
    //
    // INFERRED, NOT OBSERVED (both branches): this also governs whether an IF node's
    // EMPTY branch is a delivery to a Merge input. No execution in this repo has ever
    // isolated that question from the zero-item-output question above (an IF is not a
    // Code node and its empty branch may or may not behave identically). Under v1 it is
    // MOOT for a Merge input specifically: an empty branch delivers NOTHING either way,
    // by the rule just observed, so there is nothing left to infer for that consumer.
    // Under legacy the inference stands unverified, unchanged from before this task.
    if (order === "v1" && outItems.length === 0) return;

    // BL-02 (quick task 260911-1z5): ONE producer node-run's deliveries to SEVERAL inputs
    // of the SAME Merge land in ONE pending run. This rule is CONSISTENT WITH the Gate 11
    // recordings (12354/12355/12356: `Companies Absent Sentinel Gate`'s single node-run
    // is recorded as the source of BOTH inputs of `Decide Company Action Merge`'s run 0)
    // but was NOT isolated by them — a per-input FIFO queue model (input i's k-th delivery
    // joins run k) reproduces the same recording whenever that gate reaches input 0 first
    // (NF-MJ-01, 260911-1z5 review). The two models diverge on a Merge where two grouped
    // producers OVERLAP on an input; that shape is pinned as a KNOWN-UNOBSERVED case in
    // walkWorkflow.test.mjs and recorded in .planning/todos/pending/2026-09-11-merge-
    // input-contract-allows-many-producers-per-input.md. Grouping unit is ONE propagate() call — one
    // node-run, one output index — so two different output indexes of one IF landing on
    // the same Merge stay two separate deliveries (unobserved either way, not modelled).
    // Edges to a non-Merge target are unaffected, one delivery per edge as always.
    // Applies to BOTH engines. Note the queue ORDER this changes: non-Merge edges are
    // enqueued inside the loop and every Merge group AFTER it, so a Merge delivery moves
    // to the end of its producer's batch (under v1's `queue.pop()` that means dequeued
    // FIRST). Under legacy (FIFO) the batch's relative order is preserved and a grouped
    // delivery is consumed as ONE unit at the Merge, so nothing observable changes for
    // the LEGACY arrival rules (three legacy fixtures 12203/12206/12316 stay green under
    // it, zero code diff to their file) — it only becomes
    // load-bearing where the v1 run-indexed model needs to fill several inputs of one
    // pending run ATOMICALLY, which an ungrouped one-delivery-per-edge model cannot do.
    const mergeGroups = new Map(); // targetName -> delivery with inputIndexes: [...]
    for (const edge of connectionsFrom(fromName, outputIndex)) {
      const targetNode = nodesByName[edge.node];
      if (targetNode && targetNode.type === "n8n-nodes-base.merge") {
        let grouped = mergeGroups.get(edge.node);
        if (!grouped) {
          grouped = { targetName: edge.node, inputIndexes: [], items: outItems.slice(), fromName };
          mergeGroups.set(edge.node, grouped);
        }
        grouped.inputIndexes.push(edge.index || 0);
      } else {
        enqueue({
          targetName: edge.node, inputIndex: edge.index || 0,
          items: outItems.slice(), fromName,
        });
      }
    }
    for (const grouped of mergeGroups.values()) enqueue(grouped);
  }

  // Seed the ONE trigger.
  runData[triggerNode] = [triggerItems.slice()];
  propagate(triggerNode, 0, triggerItems);

  // v1FiresCount / FIRE_CAP (MN-02, quick task 260911-1z5): a SINGLE counter shared by
  // every v1 Merge fire, main-loop AND drain alike. Scoping the guard to the drain alone
  // (as the review's own snippet did) can never fire once MN-01's per-Merge drain cap is
  // in place — drain fires are bounded by the number of Merge nodes in the graph, always
  // <= FIRE_CAP. The real hang risk is a Merge whose own output re-completes its own
  // input(s): the MAIN LOOP's arrival code fires a v1 Merge as many times as genuine
  // complete deliveries arrive (uncapped, correctly — `Decide Company Action Merge`'s own
  // run 0 is exactly this shape, a real double-fire), so a feedback edge there has no
  // per-Merge cap to stop it. One shared counter catches either shape.
  // Both caps below (FIRE_CAP, DELIVERY_CAP) share one rationale: they bound a walk that
  // would otherwise never return, and they sit far above any measured legitimate walk —
  // the committed 287-node enrichment graph dequeues at most 191 deliveries and fires at
  // most 19 Merges across every walk in the suite (measured, 260911-3mu round-4 review),
  // independent of row count (no splitInBatches node exists in any committed
  // workflow). The `max(1000, …)` floors keep a SMALL graph with a genuinely high-fan-in
  // Merge from tripping a size-derived bound (NF-NT-06).
  let v1FiresCount = 0;
  const FIRE_CAP = Math.max(1000, (wf.nodes || []).length * 4);
  function recordV1Fire(nodeName, site) {
    v1FiresCount += 1;
    if (v1FiresCount > FIRE_CAP) {
      throw new Error(
        `walkWorkflow: v1 Merge fires did not converge at "${nodeName}" (fired from the ` +
        `${site}) — feedback edge into a Merge input?`);
    }
  }
  // NF-NT-04 (260911-1z5 review): a feedback cycle that never passes through a Merge is
  // invisible to the fire counter above and hung the walker forever (T→A→B→A). One shared
  // delivery counter bounds the whole walk; a real walk on the 287-node enrichment graph
  // dequeues at most 191 deliveries on any suite walk, so 50 per node is far above any
  // legitimate shape and far below "forever".
  let deliveriesProcessed = 0;
  // Strictly above FIRE_CAP so that a SHORT Merge-driven cycle (<= 4 deliveries per fire)
  // trips the Merge-naming guard first. A longer Merge cycle, or a cycle with no Merge on
  // it at all, lands here instead — the message names both possibilities (NF4-MN-01).
  const DELIVERY_CAP = Math.max(FIRE_CAP * 4, (wf.nodes || []).length * 50);

  // processQueue() drains `queue` to empty. Factored out (quick task 260911-0tz, Step 3c)
  // so the v1 end-of-run drain below can RESUME it after firing a pending Merge run — a
  // drained Merge's output can start work downstream, including another Merge.
  function processQueue() {
    while (queue.length) {
      const delivery = dequeue();
      deliveriesProcessed += 1;
      if (deliveriesProcessed > DELIVERY_CAP) {
        throw new Error(
          `walkWorkflow: ${deliveriesProcessed} deliveries processed without the queue ` +
          `draining (last: "${delivery.targetName}") — feedback cycle (no Merge on it, or ` +
          `a Merge cycle longer than 4 hops per fire)?`);
      }
      const node = nodesByName[delivery.targetName];
      if (!node) continue; // dangling connection target — should not happen on real JSON

      if (node.type === "n8n-nodes-base.merge") {
        const numberInputs = (node.parameters && node.parameters.numberInputs) || 2;

        if (order === "legacy") {
          // LEGACY arrival state machine — UNCHANGED RULES (byte-identical to the
          // pre-70-16 behaviour save for calling the extracted `mergeBuffers` maths
          // helper, and looping a grouped delivery's `inputIndexes` — BL-02 above — which
          // changes nothing observable here: a grouped delivery is one queue entry
          // consumed as one unit, and under FIFO its position relative to the rest of
          // its producer's batch is what the ungrouped edges had (see propagate)).
          const state = mergeState[node.name]
            || (mergeState[node.name] = { buffers: {}, arrived: {}, sources: {}, fired: false });
          // ENGINE RULE (executions 12203 and 12206): a Merge fires AT MOST ONCE per
          // execution, and a delivery arriving after it has fired is discarded.
          // Execution 12206 observed exactly that: "Adapt Search" (2 items) and "Adapt
          // Linkedin Search" (2 items) reached "Enrichment Gate Merge" AFTER it had
          // already fired on the sentinels' deliveries, and the real rows were dropped.
          if (state.fired) continue;
          for (const inputIndex of delivery.inputIndexes) {
            // ENGINE RULE (executions 12203 and 12206): the FIRST delivery to an input
            // wins. A later delivery to an already-arrived input is discarded — this is
            // what let a sentinel's `[]` claim an input ahead of the real producer's row.
            if (state.arrived[inputIndex]) continue;
            state.arrived[inputIndex] = true;
            state.sources[inputIndex] = delivery.fromName;
            state.buffers[inputIndex] = delivery.items.slice();
          }
          // Readiness is ARRIVAL, tracked separately from the items buffered, because
          // after the delivery change an arrived input can legitimately hold zero items
          // (execution 12203: "Associate Carry Merge" input 1 arrived carrying nothing
          // and the Merge fired anyway, combining 1 x 0 into 0 items).
          let ready = true;
          for (let i = 0; i < numberInputs; i += 1) {
            if (!state.arrived[i]) { ready = false; break; }
          }
          if (!ready) continue;
          state.fired = true;
          const merged = mergeBuffers(node, state.buffers, numberInputs);
          runData[node.name] = runData[node.name] || [];
          runData[node.name].push(merged);
          propagate(node.name, 0, merged);
          continue;
        }

        // v1 — run-indexed pending buffering (Step 3b), the direct model of D-70-30 rule
        // (c) flipped: nothing is EVER discarded (the legacy "first delivery wins, later
        // ones dropped" rule is legacy-only). A delivery to input i goes to the EARLIEST
        // pending run whose input i is not yet filled (`Array.prototype.find` returns the
        // first match, i.e. earliest by creation order); if every pending run already has
        // i filled, a NEW pending run opens. Run-indexed, not "reset arrived after each
        // fire": under a reset-and-discard model the observed `[2, 1]` split on
        // 12354/12355/12356 would depend on which of the two sentinel gates happened to
        // reach input 0 first; under run-indexed buffering `[2, 1]` holds in EITHER
        // arrival order and only the source NAMES swap — the engine is the target, not
        // the walker's own queue order.
        //
        // BL-02 (quick task 260911-1z5): a GROUPED delivery (one producer node-run
        // filling several inputs of this Merge at once, via `propagate`'s grouping above)
        // fills ALL of its `inputIndexes` in ONE pending run, ATOMICALLY — the earliest
        // pending run in which every one of those inputs is unfilled, else a new one. This
        // is what lets `Companies Absent Sentinel Gate`'s single node-run claim BOTH
        // inputs of one engine run instead of being split across two walker runs.
        let state = mergeState[node.name];
        if (!state) {
          // MN-07 (quick task 260911-1z5): refuse a `chooseBranch` Merge on the common
          // (first-delivery) path too, not only from the end-of-run drain below.
          requiredInputsFor(node);
          state = mergeState[node.name] = { pending: [], runs: [] };
        }
        const target = state.pending.find(
          (p) => delivery.inputIndexes.every((i) => p.filled[i] === undefined))
          || (() => {
            const created = { filled: {}, sources: {} };
            state.pending.push(created);
            return created;
          })();
        for (const inputIndex of delivery.inputIndexes) {
          target.filled[inputIndex] = delivery.items.slice();
          target.sources[inputIndex] = delivery.fromName;
        }

        let complete = true;
        for (let i = 0; i < numberInputs; i += 1) {
          if (target.filled[i] === undefined) { complete = false; break; }
        }
        if (!complete) continue; // still short an input — stays pending for a later
        // delivery, or for the end-of-run drain below.

        state.pending.splice(state.pending.indexOf(target), 1);
        const merged = mergeBuffers(node, target.filled, numberInputs);
        runData[node.name] = runData[node.name] || [];
        runData[node.name].push(merged);
        state.runs.push({
          sources: { ...target.sources },
          itemCounts: Object.fromEntries(
            Object.entries(target.filled).map(([i, items]) => [i, items.length])),
          outputCount: merged.length, // NF-BL-01: what the merge maths let OUT
        });
        recordV1Fire(node.name, "main-loop arrival"); // MN-02: shared cap — a real double-complete-fire like
        // this one is observed engine behaviour and stays uncapped by count, but a
        // feedback edge that keeps re-completing must still be bounded.
        propagate(node.name, 0, merged);
        continue;
      }

      if (TRIGGER_TYPES.has(node.type)) continue; // a trigger is never re-delivered to

      // D-70-30 rule (a) — the ONE v1 rule this walker modelled before this task, and
      // unchanged by it. Originally recorded as ENGINE RULE (execution 12200, 70-UAT.md §
      // Test 1): a node fed ZERO items does not RUN, and so contributes no run entry and
      // no delivery of its own. This holds under both engines — it is the counterpart of
      // rule (c) above, and the two together are what make a gated sentinel possible at
      // all: under legacy, an empty delivery still satisfies a Merge input but never
      // starts a lane; under v1, an empty OUTPUT is not even a delivery in the first
      // place (rule (c) above), so this check is now mostly moot for a v1 graph — the
      // filtering already happened in `propagate` — but it stays load-bearing for the
      // legacy branch, where a zero-item delivery IS enqueued and must be discarded here
      // before a downstream node is allowed to "run" on nothing.
      if (delivery.items.length === 0) continue;

      if (node.type === "n8n-nodes-base.respondToWebhook") {
        const runIndex = (runData[node.name] || []).length;
        runData[node.name] = runData[node.name] || [];
        runData[node.name].push(delivery.items);
        if (trace.respond === null) {
          trace.respond = { node: node.name, items: delivery.items, runIndex };
        } else {
          trace.respondSuppressed.push({ node: node.name, items: delivery.items, runIndex });
        }
        continue; // terminal — no propagation
      }

      const runIndex = (runData[node.name] || []).length;
      const ctx = { runData, httpStubs, codeStubs, staticData, env, runIndex };
      const result = runNode(node, delivery.items, ctx);
      // For an IF node, the "row set" recorded for by-name reads is the pre-split input —
      // an IF only routes, it does not transform or drop.
      const isIf = node.type === "n8n-nodes-base.if";
      runData[node.name] = runData[node.name] || [];
      runData[node.name].push(isIf ? delivery.items : (result.outputs[0] || []));
      if (result.unhandled && !trace.unhandledTypes.includes(node.type)) {
        trace.unhandledTypes.push(node.type);
      }
      result.outputs.forEach((branchItems, idx) => propagate(node.name, idx, branchItems));
    }
  }

  processQueue();

  // D-70-30 rule (b), v1 half — IMPLEMENTED (Step 3c, quick task 260911-0tz), CAPPED
  // (MN-01) and GUARDED (MN-02) by quick task 260911-1z5. The open question this pass
  // used to defer ("does a zero-item arrival count toward `inputsWithData`") is closed by
  // observation: it does not, because under v1 a zero-item output is not a delivery AT
  // ALL (rule (c) above) — there is no zero-item arrival left to count. What IS observed
  // (Gate 11, 12354/12355/12356): a Merge with only SOME of its inputs ever filled still
  // fires at end-of-run, once its filled-input count reaches `requiredInputs` (always `1`
  // here — see `requiredInputsFor` above). `Decide Company Action Merge` run 1 fired on
  // input 0 alone, input 1 forever absent.
  //
  // MN-01 (quick task 260911-1z5): the drain fires AT MOST ONE pending run per Merge —
  // 12354-12356 only ever observed ONE drained run, and CLAUDE.md §13.0.3's
  // `requiredInputs` row says a waiting node "executes once". `drainedOnce` enforces this;
  // any pending run left over once a Merge is in `drainedOnce` is reported by the stall
  // pass below as `merge_pending_runs_undrained` — never fired, never dropped silently.
  //
  // Repeat: fire the EARLIEST pending run of any Merge NOT already in `drainedOnce` whose
  // filled-input count is `>= requiredInputs`, scanning `mergeState` in `Object.entries`
  // insertion order when two Merges both qualify. This scan order is DETERMINISTIC, but it
  // is derived from THIS WALKER's own queue/insertion order, never from any observed
  // engine ordering — BL-02 (quick task 260911-1z5) is the proof: the walker's rule for
  // WHICH pending run an input fills matches the engine, but the walker's own dequeue
  // order does not always match which producer's delivery arrives first, and that is what
  // determines which name ends up in `sources`. Propagate a fired run's output, then
  // RESUME `processQueue()` (a drained Merge's output can start work downstream, including
  // another Merge), then rescan — `mergeState` may have grown. Repeat until no pending run
  // qualifies. Absent inputs contribute `[]` to the merge maths (via `mergeBuffers`'s
  // `|| []` fallback) and `undefined` to that run's `sources`/`itemCounts` (the key is
  // simply never set).
  if (order === "v1") {
    const drainedOnce = new Set();
    let progressed = true;
    while (progressed) {
      progressed = false;
      for (const [name, state] of Object.entries(mergeState)) {
        // NT-01 (quick task 260911-1z5): every mergeState entry is v1-shaped under v1
        // (the two shapes are keyed on `order`, fixed for the whole walk) — reaching a
        // non-pending-shaped state here is an impossible state and must be loud, not
        // silently skipped.
        if (!state.pending) {
          throw new Error(
            `walkWorkflow: merge state for "${name}" is not v1-shaped during the v1 ` +
            `drain — impossible state`);
        }
        if (drainedOnce.has(name)) continue; // MN-01 cap
        const node = nodesByName[name];
        const numberInputs = (node.parameters && node.parameters.numberInputs) || 2;
        const requiredInputs = requiredInputsFor(node);
        const idx = state.pending.findIndex(
          (p) => Object.keys(p.filled).length >= requiredInputs);
        if (idx === -1) continue;
        const target = state.pending.splice(idx, 1)[0];
        const merged = mergeBuffers(node, target.filled, numberInputs);
        runData[name] = runData[name] || [];
        runData[name].push(merged);
        state.runs.push({
          sources: { ...target.sources },
          itemCounts: Object.fromEntries(
            Object.entries(target.filled).map(([i, items]) => [i, items.length])),
          outputCount: merged.length, // NF-BL-01: what the merge maths let OUT
        });
        drainedOnce.add(name);
        recordV1Fire(name, "end-of-run drain"); // MN-02: shared cap with the main-loop fire site above
        propagate(name, 0, merged);
        progressed = true;
        processQueue();
        break; // rescan mergeState — it may have grown from the propagate/processQueue above
      }
    }
  }

  // trace.stalled — BL-01 (quick task 260911-1z5): the v1-native starvation detector.
  // The pre-existing v1 pass ("a Merge is stalled iff it received zero deliveries, ever")
  // was structurally unreachable: every Merge in `mergeState` fires at least once (the
  // drain guarantees a Merge with even ONE filled input fires at end-of-run), so
  // `state.runs.length > 0` was always true and the old push was dead code. The v1 half
  // below enumerates the GRAPH's Merge nodes (not `mergeState`, which only ever contains
  // Merges that received at least one delivery) and reports three shapes:
  //   - `merge_never_delivered_to` — absent from `mergeState` entirely;
  //   - `merge_fired_with_unfilled_input` — a fired run whose `sources[k]` is undefined;
  //   - `merge_pending_runs_undrained` (MN-01) — a leftover pending run the one-run-per-
  //     Merge cap left un-fired.
  // None of these three is, on its own, evidence of a lost row: the first two are the
  // BY-DESIGN D-70-23 gated-sentinel shapes (a lane the batch never drove, or an input
  // nobody ever delivered to). `starvedWithData(trace)` (below) is the ONE shared filter
  // that narrows this list to genuine loss — read that, not `trace.stalled` directly,
  // when the question is "did a row get dropped". Entries are pushed in graph node order,
  // then run index, so a `deepEqual` assertion against this array is stable. The LEGACY
  // branch's `merge_input_never_fired` semantics are UNCHANGED.
  if (order === "v1") {
    for (const n of (wf.nodes || []).filter((x) => x.type === "n8n-nodes-base.merge")) {
      const state = mergeState[n.name];
      const numberInputs = (n.parameters && n.parameters.numberInputs) || 2;
      if (!state) {
        trace.stalled.push({
          node: n.name, reason: "merge_never_delivered_to",
          missingInputs: [...Array(numberInputs).keys()],
        });
        continue;
      }
      state.runs.forEach((r, i) => {
        const missing = [...Array(numberInputs).keys()].filter((k) => r.sources[k] === undefined);
        if (missing.length) {
          trace.stalled.push({
            node: n.name, reason: "merge_fired_with_unfilled_input", run: i, missingInputs: missing,
          });
        }
        // NF3-BL-01 (260911-3mu review): `merge_dropped_rows` — the merge maths let OUT
        // fewer items than the largest input carried IN. For `combineByPosition`
        // (`Math.min` across inputs) and `combineAll` this is every unequal-count pairing,
        // including the annihilation case (`outputCount === 0`) and the case where EVERY
        // input is filled but with different counts — e.g. an `alwaysOutputData` HTTP node
        // that returned nothing contributing ONE marker against a carry lane's TWO rows
        // (`Associate Carry Merge` on the committed ingest graph, pinned in
        // writeGateShape.test.mjs). `append`'s output is the SUM of its inputs, so this
        // never fires for append. The entry carries the counts it was judged on, so
        // `starvedWithData` needs no cross-lookup into `trace.merges` (NF3-MN-03).
        const maxIn = Math.max(0, ...Object.values(r.itemCounts));
        if (typeof r.outputCount !== "number") {
          // NF4-NT-01: every v1 fire site records outputCount; its absence is an impossible
          // state and must be loud, never a silent "no drop" (the NF3-MN-03 rule).
          throw new Error(
            `walkWorkflow: v1 run ${i} of Merge "${n.name}" has no outputCount — impossible state`);
        }
        if (r.outputCount < maxIn) {
          trace.stalled.push({
            node: n.name, reason: "merge_dropped_rows", run: i,
            itemCounts: { ...r.itemCounts }, outputCount: r.outputCount,
          });
        }
      });
      state.pending.forEach((p, i) => {
        trace.stalled.push({
          node: n.name, reason: "merge_pending_runs_undrained", run: i,
          filledInputs: Object.keys(p.filled).map(Number),
          itemCounts: Object.fromEntries(
            Object.entries(p.filled).map(([k, items]) => [k, items.length])),
        });
      });
    }
  } else {
    // legacy — UNCHANGED.
    for (const [name, state] of Object.entries(mergeState)) {
      const node = nodesByName[name];
      const numberInputs = (node.parameters && node.parameters.numberInputs) || 2;
      if (state.fired) continue;
      // Keyed on ARRIVAL, never on an empty buffer: an input that arrived carrying zero
      // items is satisfied (execution 12203), and reporting it as missing would name the
      // wrong inputs and hide the starvation this trace exists to expose.
      const missingInputs = [];
      for (let i = 0; i < numberInputs; i += 1) {
        if (!state.arrived[i]) missingInputs.push(i);
      }
      trace.stalled.push({ node: name, reason: "merge_input_never_fired", missingInputs });
    }
  }

  // trace.merges — which producer took each Merge input, and whether the Merge fired.
  // `runs` (quick task 260911-0tz, <assumption_delta_decision>) is the PRIMARY
  // representation — `[{sources, itemCounts}, ...]` in fire order, because under v1 a
  // Merge can fire more than once per execution and item counts alone hide which run a
  // given source belongs to. `fired`/`sources`/`itemCounts` are RETAINED, carrying run
  // 0's values, for the six existing consumer files that read the flat shape
  // (ingestMixedBatch, ingestTracerFlow, mergeInputContract, walkerEngineFidelity,
  // walkWorkflow, zoominfoLaneFlow) — rewriting them is not this task. MJ-02 (quick task
  // 260911-1z5): under v1, `fired` is equivalent to key presence in `trace.merges` and
  // carries no information of its own (every Merge that ever entered `mergeState` fires
  // at least once — see the drain above) — it is RETAINED here only for the legacy
  // consumers and for the unfired-legacy diagnostic MJ-01 restores just below.
  trace.merges = {};
  for (const [name, state] of Object.entries(mergeState)) {
    let runs;
    if (state.runs) {
      runs = state.runs;
    } else {
      runs = state.fired
        ? [{
            sources: { ...state.sources },
            itemCounts: Object.fromEntries(
              Object.entries(state.buffers).map(([i, items]) => [i, items.length])),
          }]
        : [];
    }
    // MJ-01 (quick task 260911-1z5): an unfired LEGACY Merge still reports which inputs
    // HAD arrived — the pre-70-16 partial view, restored. The 12203/12206 diagnostic is
    // "who claimed input 0 before it starved", and that is most needed exactly when the
    // Merge never fired. A v1 Merge that never fired has no `state.sources`/`state.
    // buffers` to fall back to (v1 only ever tracks pending runs), so this fallback is a
    // no-op there — the "byte-identical to the pre-70-16 legacy behaviour" claim below
    // now holds for `trace.merges` too, not only the arrival state machine.
    trace.merges[name] = {
      fired: runs.length > 0,
      sources: runs[0] ? { ...runs[0].sources } : { ...(state.sources || {}) },
      itemCounts: runs[0] ? { ...runs[0].itemCounts } : Object.fromEntries(
        Object.entries(state.buffers || {}).map(([i, items]) => [i, items.length])),
      runs,
    };
  }

  return { runData, trace };
}

// starvedWithData(trace) — BL-01 (quick task 260911-1z5), the ONE definition the ~30
// class-(a) `trace.stalled` consumers share. Under legacy, `trace.stalled` semantics are
// unchanged (not this task's subject) and this is a pass-through. Under v1: only a
// `merge_pending_runs_undrained` entry whose `itemCounts` total >= 1 is a genuine loss —
// under the run-indexed pending model a delivery carrying items ALWAYS lands in SOME
// pending run, so that is the only shape where a real row went in and never came out.
// `merge_never_delivered_to` (a lane the batch never drove) and `merge_fired_with_
// unfilled_input` (an input nobody ever delivered to) are the BY-DESIGN D-70-23 gated-
// sentinel shapes, not losses.
//
// NF-BL-01 (260911-1z5 review) then NF3-BL-01 (260911-3mu review): the paragraph above
// was TRUE of delivery and FALSE of the merge maths. A `combine`/`combineByPosition`
// Merge computes `Math.min(...counts)` across its inputs — an unfilled input contributes
// `[]` (rows IN, ZERO out: annihilation), and two FILLED inputs with unequal counts drop
// the difference (rows in, fewer out) with no unfilled input to report at all. 23 of the
// enrichment graph's 33 Merges are `combine`. The stall pass therefore emits
// `merge_dropped_rows` whenever a fired run's `outputCount` is below its largest input
// count, and THAT is the second loss shape here — it subsumes the earlier
// `outputCount === 0` arm and never fires for `append` (sum of inputs). It does not fire
// on 12354's `Decide Company Action Merge` run 1 (append: 1 in, 1 out).
// (NF-NT-01: under v1 every delivery carries >= 1 item — `alwaysOutputData`'s `[{}]`
// substitution runs before rule (c)'s `return` — so the `total >= 1` test on the
// undrained arm is currently always true; it is kept as the stated predicate, not as a
// filter that has ever excluded anything.)
//
// The naive "declared producers ran with items" predicate the orchestrator's brief
// proposed false-positives twice against the very recording this task reproduces:
// (1) on 12354, `Companies Absent Sentinel Gate` is a declared producer of `Decide
// Company Action Merge` input 1, ran with items, and run 1 reads input 1 unfilled — its
// items in fact landed in run 0, so flagging it would name a loss that never happened;
// (2) `runData[ifNode]` records an IF's PRE-SPLIT input (this walker's own convention), so
// an IF that routed every item to its TRUE branch still reads as "emitted >= 1 item" while
// its FALSE branch — the one feeding the Merge — delivered nothing at all.
export function starvedWithData(trace) {
  // NF-NT-02: under legacy this is a PASS-THROUGH of `merge_input_never_fired` entries,
  // which carry no `itemCounts` at all — the name is a v1 concept; on an `allowLegacy`
  // walk read `trace.stalled` directly (no committed site calls this on a legacy walk).
  if (trace.orderingUsed === "legacy") return trace.stalled;
  return trace.stalled.filter((s) => {
    if (s.reason === "merge_pending_runs_undrained") {
      const total = Object.values(s.itemCounts || {}).reduce((sum, n) => sum + n, 0);
      return total >= 1;
    }
    if (s.reason === "merge_dropped_rows") return true; // rows in, fewer out — self-contained entry
    return false;
  });
}

// --- CLI -------------------------------------------------------------------------------

function parseArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i += 2) {
    opts[argv[i].replace(/^--/, "")] = argv[i + 1];
  }
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.workflow || !opts.rows || !opts.node) {
    console.error("usage: walkWorkflow.mjs --workflow <path> --rows <fixture.json> --node <nodeName> [--trigger <nodeName>]");
    process.exitCode = 1;
    return;
  }
  try {
    const wf = loadWorkflow(opts.workflow);
    const fixture = JSON.parse(fs.readFileSync(opts.rows, "utf8"));
    // Phase 70 Plan 07 Task 3 (Rule 3 — blocking issue): the auto-detect below refuses a
    // workflow with more than one trigger, and wf_enrichment_cloud.json has two
    // ("Webhook Trigger" and "Execute Workflow Trigger"), so the CLI could not be run
    // against the very lane scripts/prove_phase70_runtime.py has to predict. `--trigger`
    // names one explicitly; omitted, the single-trigger auto-detect is byte-identical to
    // what it always did.
    let triggerName = opts.trigger;
    if (!triggerName) {
      const candidates = (wf.nodes || []).filter((n) => TRIGGER_TYPES.has(n.type));
      if (candidates.length !== 1) {
        throw new Error(
          `expected exactly one trigger node in ${opts.workflow}, found ${candidates.length}` +
          ` (${candidates.map((n) => n.name).join(", ")}) — pass --trigger <nodeName>`);
      }
      triggerName = candidates[0].name;
    }
    const { runData, trace } = walkWorkflow(wf, {
      triggerNode: triggerName,
      triggerItems: fixture.triggerItems || [],
      httpStubs: fixture.httpStubs || {},
      codeStubs: fixture.codeStubs || {},
    });
    console.error("trace:", JSON.stringify(trace));
    console.log(JSON.stringify(nodeItems(runData, opts.node), null, 2));
  } catch (e) {
    console.error(e && e.stack ? e.stack : String(e));
    process.exitCode = 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
