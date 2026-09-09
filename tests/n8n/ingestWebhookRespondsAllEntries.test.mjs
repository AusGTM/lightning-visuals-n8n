// tests/n8n/ingestWebhookRespondsAllEntries.test.mjs
//
// F10 (uat-batch-review-row-reads-failed, execution 12181): the ingest webhook's
// `Webhook Trigger` uses `responseMode: "lastNode"` with no `responseData` — n8n
// defaults an unset `responseData` to `firstEntryJson`, so a multi-row chunk's
// `Build Ingest Response` output (one item per row) collapsed to a single dict at the
// webhook boundary. Live: a 2-row ingest (Greg's update, Barry's review) returned only
// Greg's item; Barry's review row never reached the client's `written_records` at all.
//
// This is a static config assertion, not a jsCode execution test — n8n applies
// `responseData` at the webhook-response layer, outside any Code node this repo can
// run offline. Pinning the committed JSON's own parameter is the closest offline proof
// available (matches this repo's own precedent, e.g. reviewAllowlistRefusal.test.mjs's
// "committed jsCode must carry ... verbatim" style assertions on structure, not just
// behavior).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function webhookTriggerParams(relPath) {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, relPath), "utf8"));
  const node = wf.nodes.find((n) => n.name === "Webhook Trigger");
  assert.ok(node, `Webhook Trigger present in ${relPath}`);
  return node.parameters;
}

// wf_contact_ingest_local.json (the local replica) has no Webhook Trigger node at all
// (Manual Trigger + fixture rows) — this gap only exists on the cloud template, the
// only variant with a real webhook boundary.
test("wf_contact_ingest_cloud.json: Webhook Trigger returns every entry, not just the first", () => {
  const params = webhookTriggerParams("n8n/wf_contact_ingest_cloud.json");
  assert.equal(params.responseMode, "lastNode",
    "this test targets the lastNode response mode's own default-firstEntryJson gap");
  assert.equal(params.responseData, "allEntries",
    "an unset responseData defaults to firstEntryJson under responseMode:lastNode, " +
    "collapsing a multi-row Build Ingest Response output to one item");
});
