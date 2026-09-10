// tests/n8n/creditsSummaryUnderV1.test.mjs
//
// Quick task 260911-0tz, Task B — pins the credit lane's behaviour under v1 with all
// three providers enabled, the shape that makes each `Collect Credits` input reachable
// from more than one producer edge (D-70-30's todo, "Builder follow-on": six producer
// edges into a two-input append Merge is the shape that multi-fires under v1).
//
// ENGINE RULE THIS TEST RELIES ON (from Task A, both observed on executions
// 12354/12355/12356, `tests/n8n/walkerEngineFidelityV1.test.mjs`): under v1, a node that
// RAN and emitted ZERO items makes NO delivery to a Merge input (D-70-30 rule (c)), and a
// Merge with a partially-filled pending run DRAINS at end-of-run once its filled-input
// count reaches `requiredInputs` (always `1` for the append/combine Merges this repo
// emits). Without both rules this test would assert nothing: it is what keeps EACH
// `Collect Credits` input claimed by exactly the ONE producer that actually ran (the
// real usage adapter when the provider is enabled, its skip sentinel when it is not),
// never both.
//
// Walks the COMMITTED `n8n/wf_enrichment_cloud.json` (v1 — no `allowLegacy`).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

const EMAIL_A = "credits-a@runtime-proof.invalid";
const EMAIL_B = "credits-b@runtime-proof.invalid";

// enrichmentMixedBatch.test.mjs's baseStubs() shape, reused verbatim for the contact
// lane's HTTP nodes (row alignment isn't this file's subject — every provider call
// below matches nothing, the same "no data" shape enrichmentMixedBatch uses), plus the
// ZoomInfo contact-enrichment lane's own Mint/Enrich pair that
// enrichmentMixedBatch never reaches (its tests never enable a provider).
function baseStubs() {
  return {
    "HubSpot Fetch By Id": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Name Search Fallback": (items) => items.map(() => ({ results: [] })),
    "HubSpot Search": (items) => items.map(() => ({ results: [] })),
    "HubSpot Linkedin Search": (items) => items.map(() => ({ results: [] })),
    "Lusha Enrich": (items) => items.map(() => ({ matched: false, data: {} })),
    "Apollo Match": (items) => items.map(() => ({})),
    "ZoomInfo Mint": [{ access_token: "tok" }],
    "Contact Web Research": (items) => items.map(() => ({})),
    "Contact Judge Call": (items) => items.map(() => ({})),
    "HubSpot Create": (items) => items.map((_, i) => ({ id: `created-${i}`, properties: {} })),
    "HubSpot Update": (items) => items.map((it) => ({
      id: it.write_request?.hs_object_id ?? it.hs_object_id ?? null, properties: {},
    })),

    // --- credit lane: shaped so `remaining_credits` is not trivially null (Task B). ---
    // Lusha's extractCredits arm: raw.credits.remaining (extractCredits, providerSelection.js).
    "Lusha Usage": [{ credits: { remaining: 42 } }],
    // Apollo's arm trusts ONLY a top-level numeric `remaining` (extractCredits's apollo
    // arm, read before choosing this shape) — this account's real key 403s live and
    // carries none, but the STUB below supplies exactly the shape the arm DOES trust, so
    // it produces a real number here, not null.
    "Apollo Usage": [{ remaining: 7 }],
    // ZoomInfo Usage Mint (HTTP, the OAuth2 token endpoint) — the shape
    // zoominfoToken.js::parseTokenResponse expects: access_token + expires_in.
    "ZoomInfo Usage Mint": [{ access_token: "tok", expires_in: 3600 }],
  };
}

// codeStubs — the two await-bearing Code nodes this run reaches with zoominfo enabled:
// "ZoomInfo Enrich" (contact-enrichment lane) and "ZoomInfo Usage" (credit lane).
// "ZoomInfo Usage" wraps `await this.helpers.httpRequest` itself, so its stub replaces
// the WHOLE node — the raw ZoomInfo usage-endpoint shape `extractCredits`'s zoominfo arm
// reads: `data[0].attributes.usage[]` keyed by `limitType`, `uniqueIdLimit` preferred.
function codeStubs() {
  return {
    "ZoomInfo Enrich": (items) => items.map((item) => ({ ...item, zoominfo: { matched: false } })),
    "ZoomInfo Usage": (items) => items.map(() => ({
      data: [{ attributes: { usage: [
        { limitType: "uniqueIdLimit", usageRemaining: 99, totalLimit: 1000 },
      ] } }],
    })),
  };
}

// The 12354 shape (2 contact-by-email rows, propose mode) with all three providers ON.
const EVENTS = [
  { objectType: "contact", email: EMAIL_A, row_id: "credits-a" },
  { objectType: "contact", email: EMAIL_B, row_id: "credits-b" },
];

function run() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  return walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [{ body: {
      providers: ["lusha", "apollo", "zoominfo"], mode: "propose", events: EVENTS,
    } }],
    httpStubs: baseStubs(),
    codeStubs: codeStubs(),
  });
}

test("credit lane under v1, all three providers enabled: Collect Credits fires once, the skip sentinels never run, and both response rows share one remaining_credits summary", () => {
  const { runData, trace } = run();

  assert.equal(runData["Collect Credits"].length, 1,
    "Collect Credits must fire exactly once — RED-capable by construction: if the walker " +
    "predicts Collect Credits firing more than once, this assertion fails. A second " +
    "summary would reach Credits Broadcast (combineAll) on input 1 with input 0 already " +
    "filled from the first — the FIRST summary silently wins rather than remaining_credits " +
    "visibly duplicating, so this count is the assertion that actually catches a double-fire.");
  assert.equal(runData["Build Credits Summary"].length, 1,
    "Build Credits Summary must run exactly once — it is fed directly off Collect Credits");

  // The load-bearing negative: the disabled-lane sentinels must not run when the
  // provider IS enabled.
  assert.equal(runData["Lusha Credit Skipped"], undefined,
    "Lusha is enabled on this request — its skip sentinel must never run");
  assert.equal(runData["Apollo Credit Skipped"], undefined,
    "Apollo is enabled on this request — its skip sentinel must never run");
  assert.equal(runData["ZoomInfo Credit Skipped"], undefined,
    "ZoomInfo is enabled on this request — its skip sentinel must never run");

  const collectCredits = trace.merges["Collect Credits"];
  assert.deepEqual(
    [collectCredits.runs[0].sources[0], collectCredits.runs[0].sources[1], collectCredits.runs[0].sources[2]],
    ["Adapt Lusha Usage", "Adapt Apollo Usage", "Adapt ZoomInfo Usage"],
    "each input was claimed by its real usage adapter, never the sibling skip sentinel " +
    "that shares the same input (Collect Credits input 0 has TWO producer edges — " +
    "Adapt Lusha Usage and Lusha Credit Skipped — and likewise for inputs 1 and 2)");

  // MN-04 (quick task 260911-1z5): NOT `nodeItems(...).length === 2` — that also passes
  // on a 1+1 run split, the exact collapse shape `walkerEngineFidelityV1.test.mjs:112-117`
  // explicitly declines to assert that way.
  assert.equal(runData["Build Response"].length, 1, "Build Response runs exactly once");
  assert.equal(runData["Build Response"][0].length, 2, "both rows in that one run");
  const rows = nodeItems(runData, "Build Response");
  assert.equal(rows.length, 2, "both rows return");
  // MN-05 (quick task 260911-1z5): deepEqual on CONTENT, not `===` on array identity —
  // this offline walker never clones items between nodes, so a reference match is a
  // walker artifact, not an engine guarantee (n8n serializes item data across node
  // boundaries live). The intent this pins is unchanged: one shared summary, not a
  // per-row recomputation.
  assert.deepEqual(rows[0].remaining_credits, rows[1].remaining_credits,
    "both rows carry the SAME remaining_credits content — one shared summary, not a " +
    "per-row recomputation (Credits Broadcast's combineAll spreads the single Build " +
    "Credits Summary item onto every row)");
  // Build Credits Summary's own shape (n8n/wf_enrichment_cloud.json): an ARRAY of
  // `{provider, credits}`, never a keyed object — filtered to requested providers only.
  const summary = rows[0].remaining_credits;
  assert.ok(Array.isArray(summary), "remaining_credits must be an array");
  const byProvider = Object.fromEntries(summary.map((r) => [r.provider, r.credits]));
  assert.deepEqual(Object.keys(byProvider).sort(), ["apollo", "lusha", "zoominfo"],
    "remaining_credits lists all three providers");
  assert.equal(byProvider.lusha, 42, "Lusha's stubbed remaining credits pass through extractCredits");
  assert.equal(byProvider.zoominfo, 99, "ZoomInfo's stubbed remaining credits pass through extractCredits");
  assert.equal(byProvider.apollo, 7, "Apollo's stubbed remaining credits pass through extractCredits");
});
