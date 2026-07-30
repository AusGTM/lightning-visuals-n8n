// tests/n8n/backendStatusResponse.test.mjs
//
// Phase 25 Plan 02 Task 2 (D-10/D-17) — proves `Build Credit Status` distinguishes a
// genuine zero balance from every "cannot read" case, and never falls back to a number.
// Reads the ACTUAL emitted jsCode out of the committed n8n/wf_backend_status_cloud.json
// via the same `new Function` execution mechanism
// tests/n8n/mergeCompanyStaleTimestamp.test.mjs / researchChainRowFlow.test.mjs use — no
// external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WORKFLOW_PATH = path.join(ROOT, "n8n/wf_backend_status_cloud.json");

function loadJsCode(nodeName) {
  const wf = JSON.parse(fs.readFileSync(WORKFLOW_PATH, "utf8"));
  const node = wf.nodes.find((n) => n.name === nodeName);
  assert.ok(node, `node present: ${nodeName}`);
  return node.parameters.jsCode;
}

// outputs: { "Lusha Usage": [{...}], "Apollo Usage": [], ... } — one raw body per node
// name; an absent key or an empty array simulates a probe node that never executed.
function runBuildCreditStatus(jsCode, { providersRequested, outputs }) {
  const nodeOutputs = { ...outputs, "Status Credit Request": [{ providers_requested: providersRequested }] };
  const $ = (name) => ({
    all: () => (nodeOutputs[name] || []).map((j) => ({ json: j })),
    first: () => {
      const rows = nodeOutputs[name] || [];
      return rows.length ? { json: rows[0] } : undefined;
    },
  });
  const $input = { all: () => [], get item() { return { json: undefined }; } };
  const $now = new Date("2026-07-31T00:00:00Z");
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, undefined, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}

const ALL = ["lusha", "apollo", "zoominfo"];

function byProvider(balances) {
  const m = {};
  for (const b of balances) m[b.provider] = b;
  return m;
}

test("Build Credit Status: Lusha 200 body yields the numeric remaining balance", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const { balances } = runBuildCreditStatus(jsCode, {
    providersRequested: ALL,
    outputs: {
      "Lusha Usage": [{ credits: { total: 4200, used: 82, remaining: 4118 } }],
      "Apollo Usage": [],
      "ZoomInfo Usage": [],
    },
  });
  const lusha = byProvider(balances).lusha;
  assert.equal(lusha.credits, 4118);
  assert.equal(lusha.unreadable, false);
});

test("Build Credit Status: Apollo 403 (live shape) yields the unreadable marker, and configured stays true — a refused read is not an unconfigured provider", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const { balances } = runBuildCreditStatus(jsCode, {
    providersRequested: ALL,
    outputs: {
      "Lusha Usage": [],
      "Apollo Usage": [{ error: "API_INACCESSIBLE", message: "not authorized", statusCode: 403 }],
      "ZoomInfo Usage": [],
    },
  });
  const apollo = byProvider(balances).apollo;
  assert.equal(apollo.credits, null);
  assert.equal(apollo.unreadable, true);
  assert.equal(apollo.configured, true, "a refused read is not an unconfigured provider");
  assert.equal(apollo.status, 403);
});

test("Build Credit Status: ZoomInfo 200 JSON:API body yields the balance under the uniqueIdLimit entry", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const raw = {
    data: [{ attributes: { usage: [
      { limitType: "requestLimit", totalLimit: 0, currentUsage: 0, usageRemaining: 0 },
      { limitType: "uniqueIdLimit", totalLimit: 12000, currentUsage: 2655, usageRemaining: 9345 },
    ] } }],
  };
  const { balances } = runBuildCreditStatus(jsCode, {
    providersRequested: ALL,
    outputs: { "Lusha Usage": [], "Apollo Usage": [], "ZoomInfo Usage": [raw] },
  });
  const zoominfo = byProvider(balances).zoominfo;
  assert.equal(zoominfo.credits, 9345);
  assert.equal(zoominfo.unreadable, false);
});

test("Build Credit Status: a provider whose usage node never executed yields the unreadable marker", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const { balances } = runBuildCreditStatus(jsCode, {
    providersRequested: ALL,
    outputs: { "Lusha Usage": [], "Apollo Usage": [], "ZoomInfo Usage": [] },
  });
  for (const b of balances) {
    assert.equal(b.credits, null);
    assert.equal(b.unreadable, true);
    assert.equal(b.error, "not_executed");
  }
});

test("Build Credit Status: a provider whose usage node returned an error-carrying item yields the unreadable marker", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const { balances } = runBuildCreditStatus(jsCode, {
    providersRequested: ALL,
    outputs: {
      "Lusha Usage": [{ error: "ETIMEDOUT" }],
      "Apollo Usage": [],
      "ZoomInfo Usage": [],
    },
  });
  const lusha = byProvider(balances).lusha;
  assert.equal(lusha.credits, null);
  assert.equal(lusha.unreadable, true);
});

// The point of this file: a genuine zero balance and every unreadable case must produce
// DIFFERENT output. An assertion of the form "unreadable is falsy" passes against the
// exact defect D-10/D-17 exist to prevent (0 and null are both falsy under `!x`, but they
// are NOT the same state) — this test asserts the two are genuinely distinguishable,
// never collapsing to the same shape.
test("Build Credit Status: a genuine zero balance is DISTINGUISHABLE from an unreadable balance (D-10/D-17)", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const zeroRun = runBuildCreditStatus(jsCode, {
    providersRequested: ["lusha"],
    outputs: { "Lusha Usage": [{ credits: { total: 100, used: 100, remaining: 0 } }] },
  });
  const unreadableRun = runBuildCreditStatus(jsCode, {
    providersRequested: ["lusha"],
    outputs: { "Lusha Usage": [] },
  });
  const zero = zeroRun.balances[0];
  const unreadable = unreadableRun.balances[0];

  assert.equal(zero.credits, 0, "genuine zero balance surfaces as the number 0");
  assert.equal(zero.unreadable, false, "a genuine zero is NOT unreadable");
  assert.equal(unreadable.credits, null, "unreadable never defaults to a number");
  assert.equal(unreadable.unreadable, true);

  // The actual "different output" assertion — not merely "both are falsy":
  assert.notDeepEqual(zero, unreadable);
  assert.notEqual(zero.unreadable, unreadable.unreadable);
  assert.notStrictEqual(zero.credits, unreadable.credits);
});

test("Build Credit Status: no emitted per-provider value carries any key beyond the extracted fields (T-25-03)", () => {
  const jsCode = loadJsCode("Build Credit Status");
  const { balances } = runBuildCreditStatus(jsCode, {
    providersRequested: ALL,
    outputs: {
      "Lusha Usage": [{ credits: { total: 4200, used: 82, remaining: 4118 }, accountId: "secret-account-id" }],
      "Apollo Usage": [{ error: "API_INACCESSIBLE", message: "not authorized", statusCode: 403 }],
      "ZoomInfo Usage": [{
        data: [{ attributes: { usage: [
          { limitType: "uniqueIdLimit", totalLimit: 12000, currentUsage: 2655, usageRemaining: 9345 },
        ] } }],
      }],
    },
  });
  const EXPECTED_KEYS = ["provider", "configured", "credits", "unreadable", "error", "status"].sort();
  for (const b of balances) {
    assert.deepEqual(Object.keys(b).sort(), EXPECTED_KEYS, `unexpected keys on ${b.provider}`);
    assert.equal(JSON.stringify(b).indexOf("secret-account-id"), -1, "raw provider body must never leak");
  }
});
