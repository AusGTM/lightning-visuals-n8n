// tests/n8n/ingestSearchThrottle.test.mjs
//
// Phase 73 Plan 02 Task 2 (F-A3r, D-73-15). Reads the COMMITTED
// n8n/wf_contact_ingest_cloud.json and derives its throttled search nodes from the
// generated `options.batching` shape itself — never a hard-coded node-name list — so a
// future fourth per-row search node landing without this throttle fails this test
// automatically instead of silently shipping unthrottled.
//
// 250ms (F-A3) left 1 residual 429 on a 48-row send (SESSION-2026-09-15.md, F-A3r row):
// HubSpot's CRM Search cap is account-wide and shared with the scheduled jobs, so 4 req/s
// left no headroom. D-73-15 widens to 400ms — 2.5 req/s, 50% headroom under the 5 req/s
// cap. retryOnFail is deliberately NOT added (RESEARCH Pitfall 3: n8n ignores it under
// `onError: continueRegularOutput`, the mode every ingest search node uses).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

function throttledSearchNodes() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  return wf.nodes.filter((n) => n.parameters?.options?.batching?.batch);
}

test("wf_contact_ingest_cloud carries exactly three throttled search nodes", () => {
  const nodes = throttledSearchNodes();
  assert.equal(nodes.length, 3,
    `expected exactly three batching-throttled nodes, found ${nodes.length}: ${nodes.map((n) => n.name).join(", ")}`);
});

test("every throttled search node runs at 400ms (2.5 req/s, 50% headroom under HubSpot's 5 req/s cap)", () => {
  const nodes = throttledSearchNodes();
  assert.ok(nodes.length > 0, "no throttled nodes found — did the generator regress?");
  for (const n of nodes) {
    const batch = n.parameters.options.batching.batch;
    assert.equal(batch.batchInterval, 400, `${n.name} must throttle at 400ms`);
    assert.equal(batch.batchSize, 1, `${n.name} must process exactly one item per interval`);
  }
});

test("no throttled search node carries a retryOnFail setting (D-73-15 rejected retry in favour of the wider interval)", () => {
  const nodes = throttledSearchNodes();
  for (const n of nodes) {
    assert.equal(Object.prototype.hasOwnProperty.call(n, "retryOnFail"), false,
      `${n.name} must not carry retryOnFail`);
  }
});
