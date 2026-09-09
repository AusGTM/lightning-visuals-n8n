// tests/n8n/ingestReviewBranchResponds.test.mjs
//
// F1 (uat-batch-review-row-reads-failed, run 377a913c1c9d49129663c6c8740f436d, execution
// 12147): the ingest lane's review branch (`IF Create`'s false output -> `Set Review`)
// was wired as a DEAD END. `Set Review` is a `n8n-nodes-base.set` node whose whole
// output is `{"queue": "needs_review"}` (BUG 21/12's field-dropping shape), and
// `responseMode: "lastNode"` on `Webhook Trigger` means the webhook responds with
// whatever node executed LAST. When every row in a batch is held for review, `Build
// Ingest Response` — the lane's ONE synchronous-body builder, wired only downstream of
// the two write branches (`scripts/build_cloud_workflows.py:982`) — never executes at
// all, so the operator gets a bare `{"queue": "needs_review"}` with no `action`, no
// `reason`, no `row_id`. `Decide Action`'s real reason
// ("no company in HubSpot matched name ...") never reaches the response body.
//
// Same `new Function` harness as ingestResponseRowId.test.mjs — this repo's OWN
// committed jsCode, not a hand-transcribed copy — plus a structural connectivity check
// over the built JSON's `connections` graph (the defect is in the WIRING, not the JS).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");
const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};

function targetsOf(sourceName) {
  const spec = wf.connections[sourceName];
  if (!spec) return [];
  return (spec.main || []).flatMap((outs) => (outs || []).map((c) => c.node));
}

// Breadth-first reachability over the connections graph — "does Set Review's output
// EVER reach Build Ingest Response", direct or transitive, so the fix is free to route
// through an intermediate node without this test caring which.
function reaches(fromName, toName) {
  const seen = new Set([fromName]);
  const queue = [fromName];
  while (queue.length) {
    const cur = queue.shift();
    for (const next of targetsOf(cur)) {
      if (next === toName) return true;
      if (!seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }
  return false;
}

test("Set Review's output reaches Build Ingest Response — a review-only batch must still get a real response body", () => {
  node("Set Review");
  node("Build Ingest Response");
  assert.ok(
    reaches("Set Review", "Build Ingest Response"),
    "Set Review is wired as a dead end: a batch where every row is held for review " +
    "never reaches Build Ingest Response, so the webhook responds with Set Review's " +
    "bare {queue: \"needs_review\"} and Decide Action's real action/reason/row_id are lost"
  );
});

test("Build Ingest Response reports a review-only decided row correctly when it IS given the chance to run (the JS logic itself was never the bug)", () => {
  const jsCode = node("Build Ingest Response").parameters.jsCode;
  const decided = [{
    action: "review",
    outcome: "net_new",
    hs_object_id: null,
    company_id: null,
    reason: "no company in HubSpot matched name \"Devonport Racing Club\" — create or " +
            "enrich the company first, or name its record id on the row",
    properties: {},
    row_id: "row-1",
  }];
  const $input = { all: () => [] };
  const $ = (name) => {
    const table = {
      "Decide Action": decided,
      "Build Association Request": [],
      "HubSpot Associate Company Write Gate": [],
    };
    if (!(name in table)) throw new Error(`no node named ${name}`);
    return { all: () => table[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  const out = fn($input, $).map((it) => it.json);
  assert.equal(out.length, 1);
  assert.equal(out[0].action, "review");
  assert.match(out[0].reason, /no company in HubSpot matched name/);
  assert.equal(out[0].row_id, "row-1");
});
