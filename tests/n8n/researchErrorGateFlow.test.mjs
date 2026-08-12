// Phase 48 Plan 02 — regression guard for the D-04 RESEARCH-ERROR GATE.
//
// Defect (folded todo .planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-
// failure.md, live exec 11833): _http_node's default onError="continueRegularOutput" means
// an Anthropic 400 (e.g. credit exhaustion) on the Claude Web Research HTTP node arrives as
// DATA on its main output -- execution status "success", zero node-level errors -- and
// flows into Validate Research Output exactly like a real response. Judge a run by
// node-level runData, never by executionStatus (CLAUDE.md constraints Trap 1).
//
// The fix is a gate, not a driver-side check: "IF Research Errored" sits immediately after
// Claude Web Research (bare $json read is correct there -- the immediate upstream IS the
// HTTP node, nothing can have replaced the item in between) and routes an error-shaped
// payload to "Build Research Failure Response" instead of "Validate Research Output". That
// Code node recovers the pre-HTTP row BY NODE NAME from "Build Research Request" -- the
// SAME idiom Validate Research Output already uses -- so the row reaching Build Response
// carries the same action/gate shape every other terminal produces.
//
// This test drives the REAL emitted expression/jsCode of the committed workflow with faked
// `$()` node lookups (the companyRecomputeLaneFlow.test.mjs template) -- it does not
// hand-copy the expression or jsCode as a string literal, since that would assert the
// routing the test exists to pin rather than the routing the builder actually emits.
//
// NOTE: this executes the repo's OWN committed workflow jsCode/expressions via
// `new Function` -- the same thing n8n does at runtime -- over a fixed, in-repo list of node
// names. No external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function loadWorkflow() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return { wf, byName };
}

function makeCtx(current, outputs) {
  const $ = (name) => {
    const rows = () => (outputs[name] || []).map((j) => ({ json: j }));
    return {
      all: rows,
      first: () => rows()[0],
      get item() { return rows()[0]; },
    };
  };
  const $input = {
    all: () => current.map((j) => ({ json: j })),
    get item() { return { json: current[0] }; },
    first: () => ({ json: current[0] }),
  };
  return { $, $input, $json: current[0] };
}

function runCode(node, current, outputs) {
  const { $, $input, $json } = makeCtx(current, outputs);
  const now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${node.parameters.jsCode}`);
  const out = fn($, $input, $json, {}, now, now) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}

// An IF node has no jsCode -- its predicate lives in the condition's leftValue as an n8n
// expression (`={{ ... }}`). Evaluate the REAL committed expression, never a restatement.
function ifExpression(node) {
  const raw = node.parameters.conditions.conditions[0].leftValue;
  const m = /^=\{\{([\s\S]*)\}\}$/.exec(String(raw).trim());
  assert.ok(m, `IF node leftValue is not an n8n expression: ${raw}`);
  return m[1].trim();
}

function evalIf(node, current, outputs) {
  const { $, $input, $json } = makeCtx(current, outputs);
  const fn = new Function("$", "$input", "$json", `"use strict"; return (${ifExpression(node)});`);
  return fn($, $input, $json) === true;
}

function targetsOf(wf, nodeName, branchIndex) {
  const branch = ((wf.connections[nodeName] || {}).main || [])[branchIndex] || [];
  return branch.map((e) => e.node);
}

// --- fixtures ---------------------------------------------------------------------------

// The exact error-shaped payload confirmed live on exec 11833 (folded todo's own quote).
const LIVE_ERROR_PAYLOAD = {
  error: {
    message: "400 - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\"," +
      "\"message\":\"Your credit balance is too low to access the Anthropic API...\"}}",
    name: "AxiosError",
  },
};

const HEALTHY_PAYLOAD = { content: [{ type: "text", text: "{\"matched\":true}" }] };

const DEGENERATE_PAYLOAD = {};

const PRE_HTTP_ROW = {
  object_type: "companies",
  object_id: "15008671672",
  identity_keys: { domain: "racingnsw.example" },
  existingRecord: { name: "Racing NSW" },
};

// --- behaviour: the gate's real expression on three payload shapes ------------------------

test("IF Research Errored's REAL expression returns true on the live-observed error shape", () => {
  const { byName } = loadWorkflow();
  const node = byName["IF Research Errored"];
  assert.ok(node, "IF Research Errored node present in the built workflow");
  assert.ok(!ifExpression(node).includes("$("), "the gate reads bare $json, no $() node-name lookup");
  assert.equal(evalIf(node, [LIVE_ERROR_PAYLOAD], {}), true);
});

test("IF Research Errored's REAL expression returns false on a healthy shape", () => {
  const { byName } = loadWorkflow();
  const node = byName["IF Research Errored"];
  assert.equal(evalIf(node, [HEALTHY_PAYLOAD], {}), false);
});

test("IF Research Errored's REAL expression returns true on a degenerate shape (fail closed)", () => {
  const { byName } = loadWorkflow();
  const node = byName["IF Research Errored"];
  assert.equal(evalIf(node, [DEGENERATE_PAYLOAD], {}), true);
});

// --- behaviour: the failure terminal's REAL jsCode recovers identity + states the reason --

test("Build Research Failure Response recovers the pre-HTTP row and states the error reason", () => {
  const { byName } = loadWorkflow();
  const node = byName["Build Research Failure Response"];
  assert.ok(node, "Build Research Failure Response node present in the built workflow");
  assert.ok(node.parameters.jsCode.includes("catch"), "recovery is try/catch guarded");
  assert.ok(
    node.parameters.jsCode.includes("Build Research Request"),
    "recovers the row by name from Build Research Request");

  const outputs = { "Build Research Request": [PRE_HTTP_ROW] };
  const out = runCode(node, [LIVE_ERROR_PAYLOAD], outputs);

  assert.equal(out.length, 1);
  assert.equal(out[0].action, "research_failed");
  assert.match(out[0].gate.reason, /credit balance is too low/);
  assert.equal(out[0].object_id, "15008671672", "identity fields survive from the recovered row");
  assert.equal(out[0].identity_keys.domain, "racingnsw.example");
});

test("Build Research Failure Response fails closed when $('Build Research Request') throws", () => {
  const { byName } = loadWorkflow();
  const node = byName["Build Research Failure Response"];

  // No "Build Research Request" key in outputs -> makeCtx's $() returns an empty rows()
  // array, exactly mirroring the real try/catch's [] fallback when the node lookup throws.
  const out = runCode(node, [LIVE_ERROR_PAYLOAD], {});

  assert.equal(out.length, 1);
  assert.equal(out[0].action, "research_failed", "still reports research_failed with no identity to recover");
  assert.match(out[0].gate.reason, /credit balance is too low/);
});

// --- behaviour: the true/false wiring matches the four specified edges --------------------

test("the wiring routes true->failure terminal, false->Validate Research Output, unchanged", () => {
  const { wf } = loadWorkflow();

  assert.deepEqual(targetsOf(wf, "Claude Web Research", 0), ["IF Research Errored"]);
  assert.deepEqual(targetsOf(wf, "IF Research Errored", 0), ["Build Research Failure Response"]);
  assert.deepEqual(targetsOf(wf, "IF Research Errored", 1), ["Validate Research Output"]);
  assert.deepEqual(targetsOf(wf, "Build Research Failure Response", 0), ["Build Response"]);
});

// --- behaviour: a healthy payload still reaches Validate Research Output unchanged --------

test("a healthy research response still reaches Validate Research Output's real jsCode", () => {
  const { byName } = loadWorkflow();
  const gate = byName["IF Research Errored"];
  const validate = byName["Validate Research Output"];

  assert.equal(evalIf(gate, [HEALTHY_PAYLOAD], {}), false, "false lane: not errored");

  // Validate Research Output recovers its row from "Build Research Request" too (pre-
  // existing idiom, unaffected by this gate) -- confirm the additive claim: a healthy
  // payload's candidate still gets built without throwing.
  const outputs = { "Build Research Request": [PRE_HTTP_ROW] };
  const out = runCode(validate, [HEALTHY_PAYLOAD], outputs);
  assert.equal(out.length, 1);
  assert.ok(out[0].research_candidate, "a healthy payload still produces a research_candidate");
});
