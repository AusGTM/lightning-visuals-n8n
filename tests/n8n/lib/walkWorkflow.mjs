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

function runCode(node, items, ctx) {
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
 *
 * Returns `{ runData, trace }`. `trace.unhandledTypes`, `trace.stalled`, `trace.respond`,
 * `trace.respondSuppressed`, `trace.trigger`, `trace.orderingUsed` — see 70-01-PLAN.md.
 */
export function walkWorkflow(wf, opts) {
  const { triggerNode, triggerItems, httpStubs = {}, env = {} } = opts || {};
  const nodesByName = {};
  for (const n of wf.nodes || []) nodesByName[n.name] = n;

  const triggerNodeObj = nodesByName[triggerNode];
  if (!triggerNodeObj) throw new Error(`trigger node not found: ${triggerNode}`);

  const outgoing = wf.connections || {};
  const order = wf.settings && wf.settings.executionOrder === "v1" ? "v1" : "legacy";

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
    if (outItems.length === 0 && node && node.alwaysOutputData === true) {
      outItems = [{}];
    }
    if (outItems.length === 0) return; // nothing to deliver — this wave is dropped here
    for (const edge of connectionsFrom(fromName, outputIndex)) {
      enqueue({ targetName: edge.node, inputIndex: edge.index || 0, items: outItems.slice() });
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
      const state = mergeState[node.name] || (mergeState[node.name] = { buffers: {}, fired: false });
      if (state.fired) continue; // fires ONCE per replay (spec — not n8n's real multi-wave behaviour)
      state.buffers[delivery.inputIndex] = (state.buffers[delivery.inputIndex] || []).concat(delivery.items);
      let ready = true;
      for (let i = 0; i < numberInputs; i += 1) {
        if (!state.buffers[i] || state.buffers[i].length === 0) { ready = false; break; }
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
    const ctx = { runData, httpStubs, staticData, env, runIndex };
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

  for (const [name, state] of Object.entries(mergeState)) {
    if (state.fired) continue;
    const node = nodesByName[name];
    const numberInputs = (node.parameters && node.parameters.numberInputs) || 2;
    const missingInputs = [];
    for (let i = 0; i < numberInputs; i += 1) {
      if (!state.buffers[i] || state.buffers[i].length === 0) missingInputs.push(i);
    }
    trace.stalled.push({ node: name, reason: "merge_input_never_fired", missingInputs });
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
    console.error("usage: walkWorkflow.mjs --workflow <path> --rows <fixture.json> --node <nodeName>");
    process.exitCode = 1;
    return;
  }
  try {
    const wf = loadWorkflow(opts.workflow);
    const fixture = JSON.parse(fs.readFileSync(opts.rows, "utf8"));
    const candidates = (wf.nodes || []).filter((n) => TRIGGER_TYPES.has(n.type));
    if (candidates.length !== 1) {
      throw new Error(`expected exactly one trigger node in ${opts.workflow}, found ${candidates.length}`);
    }
    const { runData, trace } = walkWorkflow(wf, {
      triggerNode: candidates[0].name,
      triggerItems: fixture.triggerItems || [],
      httpStubs: fixture.httpStubs || {},
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
