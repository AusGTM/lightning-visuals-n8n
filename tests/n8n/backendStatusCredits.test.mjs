// tests/n8n/backendStatusCredits.test.mjs
//
// Phase 73 Plan 05 Task 1 (F-B6) — walks the COMMITTED `n8n/wf_backend_status_cloud.json`
// end to end, the same graph-level proof `creditsSummaryUnderV1.test.mjs` already runs for
// the enrichment lane's own credit branch (the SIBLING probe code that read real balances
// live in the same stress session — SESSION-2026-09-15.md, Stage D). Every prior test
// covering this workflow (backendStatusResponse.test.mjs, backendStatus.test.mjs) exercises
// "Build Credit Status" or "backendStatus.js" IN ISOLATION, hand-feeding each node its own
// merged input — none of them walk the graph's own `connections`, so none of them could
// have caught a carry-merge wired to the wrong node. This file is the missing offline
// instrument RESEARCH Pitfall 4 calls for: diagnose the wiring before writing anything.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_backend_status_cloud.json");

// Live shapes from the SAME stress session (SESSION-2026-09-15.md, Stage D — "provider
// balances (from enrich runData): Lusha total 4200/used 492/remaining 3708; ZoomInfo
// remaining 9358; Apollo null"). Apollo's 403 shape mirrors backendStatusResponse.test.mjs
// and the ENRICH_STATUS_BUILD_RESPONSE `raw.error` branch it exercises.
function httpStubs() {
  return {
    "Lusha Usage": [{ credits: { total: 4200, used: 492, remaining: 3708 } }],
    "Apollo Usage": [{ error: "API_INACCESSIBLE", message: "not authorized", statusCode: 403 }],
    "ZoomInfo Usage Mint": [{ access_token: "tok", expires_in: 3600 }],
    "HS Requested Search (Companies)": [{ total: 5, results: [] }],
    "HS Review Search (Companies)": [{ total: 2, results: [] }],
    "HS Requested Search (Contacts)": [{ total: 11, results: [] }],
    "HS Review Search (Contacts)": [{ total: 3, results: [] }],
    // 73.1-06 (D-14c): the portal-proof probe joining this same chain.
    "HubSpot Account Info": [{ portalId: 22617666 }],
  };
}

// "ZoomInfo Usage" is the one await-bearing Code node on this lane (it wraps
// `await this.helpers.httpRequest` itself, mirroring creditsSummaryUnderV1.test.mjs's
// identical stub for the enrichment lane's twin node) — the raw shape
// extractCredits's zoominfo arm reads: data[0].attributes.usage[] keyed by limitType,
// uniqueIdLimit preferred.
function codeStubs() {
  return {
    "ZoomInfo Usage": (items) => items.map(() => ({
      data: [{ attributes: { usage: [
        { limitType: "uniqueIdLimit", usageRemaining: 9358, totalLimit: 12000 },
      ] } }],
    })),
  };
}

function run() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  return walkWorkflow(wf, {
    triggerNode: "Status Webhook Trigger",
    triggerItems: [{}],
    httpStubs: httpStubs(),
    codeStubs: codeStubs(),
  });
}

test("backend-status graph: Lusha and ZoomInfo report real remaining balances, Apollo's 403 never reports as not_configured or as a number", () => {
  const { runData } = run();

  const rows = nodeItems(runData, "Build Status");
  assert.equal(rows.length, 1, "Build Status must run exactly once");
  const body = rows[0];

  const balances = body.balances;
  assert.ok(Array.isArray(balances) && balances.length === 3,
    "the balances array must survive the whole carry-merge chain to Build Status — " +
    "an empty/missing array here is exactly the F-B6 symptom (every provider reads as " +
    "not_configured downstream)");
  const byProvider = Object.fromEntries(balances.map((b) => [b.provider, b]));

  assert.equal(byProvider.lusha.credits, 3708, "Lusha's real remaining balance reaches Build Status");
  assert.equal(byProvider.lusha.unreadable, false);
  assert.equal(byProvider.zoominfo.credits, 9358, "ZoomInfo's real remaining balance reaches Build Status");
  assert.equal(byProvider.zoominfo.unreadable, false);
  assert.equal(byProvider.apollo.credits, null, "Apollo's 403 must never produce a number");
  assert.equal(byProvider.apollo.unreadable, true);

  // credential_health's ok/refused/unknown states derive from an httpStatus() field
  // this repo's httpRequest nodes never populate on a bare 2xx (no `fullResponse`
  // option is set anywhere in this graph) — a real success therefore reads
  // state:"unknown"/reason:"no_response" regardless of this fix, a PRE-EXISTING,
  // separate characteristic of this endpoint, not part of F-B6. The one property
  // D-73-17 actually requires here is that a genuinely-configured, answering
  // provider is never mislabeled `not_configured` — that reason is reserved for a
  // provider whose probe never ran/never had a credential at all.
  const health = Object.fromEntries(body.credential_health.map((h) => [h.source, h]));
  assert.notEqual(health.lusha.reason, "not_configured",
    "Lusha answered with a real balance — never the same as not having been probed");
  assert.notEqual(health.zoominfo.reason, "not_configured",
    "ZoomInfo answered with a real balance — never the same as not having been probed");
  assert.notEqual(health.apollo.reason, "not_configured",
    "Apollo has a real, provisioned credential that answered 403 — that is refused, " +
    "never the same thing as never having been probed at all (D-73-17)");
  assert.notEqual(health.apollo.state, "ok", "a 403 can never read as ok");
});
