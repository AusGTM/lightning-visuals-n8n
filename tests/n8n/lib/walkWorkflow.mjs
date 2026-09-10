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
 * Returns `{ runData, trace }`. `trace.unhandledTypes`, `trace.stalled`, `trace.respond`,
 * `trace.respondSuppressed`, `trace.trigger`, `trace.orderingUsed` — see 70-01-PLAN.md —
 * plus `trace.merges` (Phase 70 plan 70-09): per Merge node, `{fired, sources, itemCounts}`
 * keyed by input index, naming the producer whose delivery CLAIMED each input. Added
 * because the defect executions 12203 and 12206 exposed is invisible in item counts
 * alone: which node took input 0 IS the finding.
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

  // mergeState: nodeName -> { buffers: {inputIndex: items[]}, fired: bool }
  const mergeState = {};

  let queue = [];
  function enqueue(delivery) { queue.push(delivery); }
  function dequeue() { return order === "v1" ? queue.pop() : queue.shift(); }

  function connectionsFrom(name, outputIndex) {
    const perNode = outgoing[name];
    return (perNode && perNode.main && perNode.main[outputIndex]) || [];
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
    // D-70-30 rule (c) — UNOBSERVED under v1. Originally recorded as ENGINE RULE
    // (executions 12203 and 12206, 70-UAT.md § Tests 2 and 3; D-70-20): a node that ran
    // and emitted ZERO items still DELIVERS to its targets. The runData `source` arrays
    // of both executions name a sentinel whose output was `[]` as the producer that took
    // a Merge input. This line used to read `if (outItems.length === 0) return;` —
    // dropping the wave — which is why every offline suite was green while the live
    // engine dropped rows.
    //
    // Gap-closure round 3 (plan 70-16, D-70-30): both executions 12203 and 12206 ran on
    // bodies whose `settings.executionOrder` was ABSENT — n8n's LEGACY order. What this
    // walker calls a "delivery" may in fact have been the legacy `addEmptyItem` push
    // (`addNodeToBeExecuted`, `packages/core/src/execution-engine/workflow-execute.ts`)
    // rather than a genuine zero-item delivery — the two are indistinguishable from
    // runData alone. Under v1 there is no such push, so whether a zero-item OUTPUT still
    // counts as a delivery to a Merge input is UNOBSERVED. Left UNCHANGED deliberately —
    // not because it is believed correct under v1, but because reimplementing it now
    // would replace one unobserved model with another (D-70-19 forbids that), and
    // freezing this rule lets Gate 11 isolate the ONE variable this plan actually
    // changes: the executionOrder flip itself. A zero-item delivery is still enqueued
    // exactly like any other; what it means at the CONSUMING end depends on whether the
    // target is a Merge (see the walk loop below).
    //
    // INFERRED, NOT OBSERVED (unchanged by D-70-30): this also makes an IF node's EMPTY
    // branch a delivery to a Merge input. No execution in this repo has ever observed
    // whether the live engine does that (an IF is not a Code node and may not emit an
    // empty branch at all). The routing pass-throughs plan 70-10 adds make every
    // generated graph independent of the answer either way; until an observation exists,
    // treat this branch of the model as unverified.
    for (const edge of connectionsFrom(fromName, outputIndex)) {
      enqueue({
        targetName: edge.node, inputIndex: edge.index || 0,
        items: outItems.slice(), fromName,
      });
    }
  }

  // Seed the ONE trigger.
  runData[triggerNode] = [triggerItems.slice()];
  propagate(triggerNode, 0, triggerItems);

  while (queue.length) {
    const delivery = dequeue();
    const node = nodesByName[delivery.targetName];
    if (!node) continue; // dangling connection target — should not happen on real JSON

    if (node.type === "n8n-nodes-base.merge") {
      const numberInputs = (node.parameters && node.parameters.numberInputs) || 2;
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
      const state = mergeState[node.name]
        || (mergeState[node.name] = { buffers: {}, arrived: {}, sources: {}, fired: false });
      // ENGINE RULE (executions 12203 and 12206): a Merge fires AT MOST ONCE per
      // execution, and a delivery arriving after it has fired is discarded. Execution
      // 12206 observed exactly that: "Adapt Search" (2 items) and "Adapt Linkedin Search"
      // (2 items) reached "Enrichment Gate Merge" AFTER it had already fired on the
      // sentinels' deliveries, and the real rows were dropped.
      if (state.fired) continue;
      // ENGINE RULE (executions 12203 and 12206): the FIRST delivery to an input wins.
      // A later delivery to an already-arrived input is discarded — this is what let a
      // sentinel's `[]` claim an input ahead of the real producer's row.
      if (state.arrived[delivery.inputIndex]) continue;
      state.arrived[delivery.inputIndex] = true;
      state.sources[delivery.inputIndex] = delivery.fromName;
      state.buffers[delivery.inputIndex] = delivery.items.slice();
      // Readiness is ARRIVAL, tracked separately from the items buffered, because after
      // the delivery change an arrived input can legitimately hold zero items (execution
      // 12203: "Associate Carry Merge" input 1 arrived carrying nothing and the Merge
      // fired anyway, combining 1 x 0 into 0 items).
      let ready = true;
      for (let i = 0; i < numberInputs; i += 1) {
        if (!state.arrived[i]) { ready = false; break; }
      }
      if (!ready) continue;
      state.fired = true;
      let merged;
      if (isCombineByPosition) {
        // Last input wins a key clash (this repo's carry-merges always wire the
        // CARRIED ROW last and set `resolveClash: "preferLast"` — see
        // scripts/build_cloud_workflows.py's `merge_node` docstring), never n8n's own
        // combineByPosition default (`addSuffix`, which renames the clashing keys).
        const counts = [];
        for (let i = 0; i < numberInputs; i += 1) counts.push(state.buffers[i].length);
        const n = Math.min(...counts);
        merged = [];
        for (let i = 0; i < n; i += 1) {
          let combined = {};
          for (let inp = 0; inp < numberInputs; inp += 1) combined = { ...combined, ...state.buffers[inp][i] };
          merged.push(combined);
        }
      } else if (isCombineAll) {
        // Cartesian product across all configured inputs, same last-input-wins clash
        // rule as combineByPosition above.
        let combos = [{}];
        for (let inp = 0; inp < numberInputs; inp += 1) {
          const next = [];
          for (const base of combos) {
            for (const it of state.buffers[inp]) next.push({ ...base, ...it });
          }
          combos = next;
        }
        merged = combos;
      } else {
        merged = [];
        for (let i = 0; i < numberInputs; i += 1) merged.push(...state.buffers[i]);
      }
      runData[node.name] = runData[node.name] || [];
      runData[node.name].push(merged);
      propagate(node.name, 0, merged);
      continue;
    }

    if (TRIGGER_TYPES.has(node.type)) continue; // a trigger is never re-delivered to

    // D-70-30 rule (a) — the ONE v1 rule this walker MODELS. Originally recorded as
    // ENGINE RULE (execution 12200, 70-UAT.md § Test 1): a node fed ZERO items does not
    // RUN, and so contributes no run entry and no delivery of its own. On 12200
    // "HubSpot Associate Company" received zero items, never ran, and its own
    // alwaysOutputData therefore contributed nothing to the carry Merge — the sentinel
    // alone satisfied it. Execution 12200 ran under n8n's LEGACY order — its own
    // `settings` carried no `executionOrder` — but this rule is expected to hold A
    // FORTIORI under v1: v1's documented behaviour (Gate 8's engine citation,
    // `addNodeToBeExecuted`'s `addEmptyItem` branch,
    // `packages/core/src/execution-engine/workflow-execute.ts`) is that legacy pushes an
    // empty-item run onto an otherwise-empty branch specifically so a waiting Merge can
    // finish; v1 removes exactly that push, so a node fed zero items running EVEN LESS
    // under v1 than it did under the legacy execution 12200 observed is the stronger, not
    // the weaker, claim. This is the counterpart of the delivery rule in `propagate`
    // above (D-70-30 rule (c), UNOBSERVED under v1), and the two together are what make a
    // gated sentinel possible at all: an empty delivery still SATISFIES a Merge input,
    // but it never STARTS a lane.
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

  // D-70-30 rule (b) — NOT MODELLED. This pass REPORTS starvation; it does not DRAIN.
  // n8n's v1 path (documented, not observed on this instance) drains a still-waiting
  // Merge at end-of-run once its arrived-with-data input count reaches `requiredInputs`
  // — for the Merge v3.2 node this repo generates
  // (`packages/nodes-base/nodes/Merge/v3/actions/versionDescription.ts`), that is `1` for
  // the `append` and `combine` modes this repo emits. This walker deliberately does NOT
  // implement that drain: a faithful implementation would have to decide whether a
  // zero-item arrival counts toward `inputsWithData`, which is exactly what D-70-30 rule
  // (c) above calls UNOBSERVED — implementing the drain now would silently answer that
  // open question rather than leave it open, replacing one unobserved model with another
  // (D-70-19 forbids that). On a graph that satisfies the Merge-input contract
  // (`assert_merge_input_contract`, D-70-20 — every input has at least one producer),
  // this walker's report-only pass and a hypothetical v1 drain agree UNLESS an input
  // receives no non-empty delivery at all; every committed n8n/wf_*.json satisfies that
  // contract, so `trace.stalled` staying starvation-only rather than draining costs
  // nothing on the graphs this repo actually generates.
  for (const [name, state] of Object.entries(mergeState)) {
    if (state.fired) continue;
    const node = nodesByName[name];
    const numberInputs = (node.parameters && node.parameters.numberInputs) || 2;
    // Keyed on ARRIVAL, never on an empty buffer: an input that arrived carrying zero
    // items is satisfied (execution 12203), and reporting it as missing would name the
    // wrong inputs and hide the starvation this trace exists to expose.
    const missingInputs = [];
    for (let i = 0; i < numberInputs; i += 1) {
      if (!state.arrived[i]) missingInputs.push(i);
    }
    trace.stalled.push({ node: name, reason: "merge_input_never_fired", missingInputs });
  }

  // trace.merges — which producer took each Merge input, and whether the Merge fired.
  // Needed because the defect this walker now models is invisible in item counts alone:
  // on execution 12206 the question "which node claimed input 0" IS the finding.
  trace.merges = {};
  for (const [name, state] of Object.entries(mergeState)) {
    trace.merges[name] = {
      fired: state.fired,
      sources: { ...state.sources },
      itemCounts: Object.fromEntries(
        Object.entries(state.buffers).map(([i, items]) => [i, items.length])),
    };
  }

  return { runData, trace };
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
