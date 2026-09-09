// tests/n8n/ingestWebhookRespondsAllEntries.test.mjs
//
// F10 (uat-batch-review-row-reads-failed, execution 12181): the ingest webhook's
// `Webhook Trigger` used to use `responseMode: "lastNode"` with no `responseData` — n8n
// defaults an unset `responseData` to `firstEntryJson`, so a multi-row chunk's
// `Build Ingest Response` output (one item per row) collapsed to a single dict at the
// webhook boundary. Live: a 2-row ingest (Greg's update, Barry's review) returned only
// Greg's item; Barry's review row never reached the client's `written_records` at all.
//
// Superseded, not merely fixed, by D-70-07 (Phase 70 Plan 02): the webhook no longer
// answers with row data on the wire AT ALL — it answers with an ack
// (`{run_id, accepted, row_ids}`, "Build Ingest Ack") under `responseMode:
// "responseNode"`, and every row's real outcome is read from the settled execution's
// runData (D-70-05). The F10 defect class (a multi-row response collapsing to one item
// at the webhook boundary) cannot recur on this lane any more because there is no
// second, row-carrying response body to collapse — this test now pins THAT contract
// instead of the retired `lastNode`/`allEntries` one.
//
// This is a static config assertion, not a jsCode execution test — n8n applies
// `responseMode` at the webhook-response layer, outside any Code node this repo can
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

function loadWf(relPath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relPath), "utf8"));
}

function webhookTriggerParams(wf) {
  const node = wf.nodes.find((n) => n.name === "Webhook Trigger");
  assert.ok(node, "Webhook Trigger present");
  return node.parameters;
}

// wf_contact_ingest_local.json (the local replica) has no Webhook Trigger node at all
// (Manual Trigger + fixture rows) — this gap only exists on the cloud template, the
// only variant with a real webhook boundary.
test("wf_contact_ingest_cloud.json: the webhook answers with an ack node, never a row-carrying body", () => {
  const wf = loadWf("n8n/wf_contact_ingest_cloud.json");
  const params = webhookTriggerParams(wf);
  assert.equal(params.responseMode, "responseNode",
    "D-70-07: the ack-only responder, not the retired lastNode/allEntries contract");
  assert.ok(!("responseData" in params),
    "responseData does not apply under responseNode — a leftover key here would be dead config");

  const respondNodes = wf.nodes.filter((n) => n.type === "n8n-nodes-base.respondToWebhook");
  assert.equal(respondNodes.length, 1, "exactly one responder on this lane");
  const feeders = Object.entries(wf.connections)
    .filter(([, spec]) => (spec.main || []).some(
      (outs) => (outs || []).some((c) => c.node === "Respond to Webhook")))
    .map(([src]) => src);
  assert.deepEqual(feeders, ["Build Ingest Ack"],
    "D-70-07: no business lane feeds Respond to Webhook on this lane — the ack is the ONLY inbound edge");
});
