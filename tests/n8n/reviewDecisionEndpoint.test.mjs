// tests/n8n/reviewDecisionEndpoint.test.mjs
//
// Phase 30 Plan 02 — the synchronous `hubspot/review/decision` endpoint.
//
// Two sections:
//   (1) MODULE — n8n/code/reviewDecision.js in isolation. A rejection is exactly one
//       property write and leaves the record queued (D-10, REVIEW-05).
//   (2) FLOW — the COMMITTED n8n/wf_review_decision_cloud.json's own node jsCode, run
//       through `new Function` the way n8n's Code node runs it. Refusal, preview, the
//       gate in both arming directions, and the {outcome, message, would_write,
//       verified_properties, verified} response contract 30-06 consumes (D-19).
//
// No test here issues a network call. Arming is a literal swap on the in-memory jsCode
// string only — the EXACT swap scripts/deploy_n8n_workflows.py's enable_baked_flags()
// performs, so a drift in how the builder spells a constant fails this file.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const MODULE_PATH = path.join(ROOT, "n8n/code/reviewDecision.js");
const { buildReviewDecision } = require(MODULE_PATH);
const { mergeCompanies, stableStringify } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

// The `lv_`-prefixed review family from config/hubspot_properties.yaml. Hard-typed here on
// purpose: this file is where the names are PINNED (root CLAUDE.md's unprefixed names are
// wrong for this deployment — 30 D-08c).
const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_REVIEW_REASON = "lv_enrichment_review_reason";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";
const P_REVIEWED_BY = "lv_enrichment_reviewed_by";
const P_REVIEWED_AT = "lv_enrichment_reviewed_at";

const NOW = "2026-07-31T04:05:06.000Z";

// Build the flagged-row fixture from a REAL mergeCompanies() run filtered to needs_review,
// exactly as reviewLoop.test.mjs does — so the candidate JSON cannot drift from what the
// pipeline actually stores in lv_enrichment_review_candidate_json.
function flaggedRow(overrides) {
  const existing = {
    domain: "exampleracing.example",
    lv_org_type: "broadcaster",
    lv_produces_content: false,
  };
  const candidate = { lv_org_type: "governing_body_league", lv_produces_content: true };
  const { decisions } = mergeCompanies(existing, candidate, undefined,
    { source: "claude_web", confidence: 60 });
  const needsReview = decisions.filter((d) => d.decision === "needs_review");
  assert.ok(needsReview.length > 0, "fixture must actually produce a needs_review decision");
  return {
    ...existing,
    hs_object_id: "789",
    record_found: true,
    [P_NEEDS_REVIEW]: "true",
    [P_ICP_NEEDS_REVIEW]: "false",
    [P_CANDIDATE_JSON]: stableStringify(needsReview),
    ...(overrides || {}),
  };
}

// =====================================================================================
// (1) MODULE — buildReviewDecision
// =====================================================================================

test("reject on a flagged row writes EXACTLY one property: the operator's reason", () => {
  const row = flaggedRow();
  const out = buildReviewDecision({
    decision: "reject", reason: "Wrong org type — this is a broadcaster, not a league.",
    reviewedBy: "revops@example.com", row, nowIso: NOW,
  });

  assert.equal(out.outcome, "rejected");
  assert.equal(Object.keys(out.properties).length, 1,
    "a rejection is one property write and nothing else");
  assert.equal(out.properties[P_REVIEW_REASON],
    "Wrong org type — this is a broadcaster, not a league.");
});

test("reject never clears a review flag and never blanks the candidate JSON (D-10)", () => {
  const row = flaggedRow();
  const { properties } = buildReviewDecision({
    decision: "reject", reason: "not a fit", reviewedBy: "revops@example.com", row, nowIso: NOW,
  });
  // Explicit key-PRESENCE assertions, not a string search: writing the flag as `false`
  // and omitting it are indistinguishable to a grep and opposite to HubSpot.
  assert.equal(P_NEEDS_REVIEW in properties, false, "needs-review flag must not be written");
  assert.equal(P_ICP_NEEDS_REVIEW in properties, false, "ICP needs-review flag must not be written");
  assert.equal(P_CANDIDATE_JSON in properties, false, "candidate JSON must not be blanked");
  assert.equal(P_REVIEWED_AT in properties, false, "a rejection does not stamp reviewed-at");
  assert.equal(P_REVIEWED_BY in properties, false, "a rejection does not stamp reviewed-by");
});

test("a row that is not actually flagged yields outcome not_flagged and writes nothing", () => {
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "false", [P_CANDIDATE_JSON]: "",
  });
  const out = buildReviewDecision({ decision: "reject", reason: "x", row, nowIso: NOW });
  assert.equal(out.outcome, "not_flagged");
  assert.deepEqual(out.properties, {});
});

test("an empty-array candidate JSON is not a flag either", () => {
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "false", [P_CANDIDATE_JSON]: "[]",
  });
  const out = buildReviewDecision({ decision: "reject", reason: "x", row, nowIso: NOW });
  assert.equal(out.outcome, "not_flagged");
});

test("a row flagged ONLY by lv_icp_needs_review is still in the queue", () => {
  // The queue's own definition (wf_backend_status_cloud's AWAITING_REVIEW_GROUPS) ORs the
  // two flags, so a record flagged solely for ICP review must be adjudicable here.
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "true", [P_CANDIDATE_JSON]: "",
  });
  const out = buildReviewDecision({ decision: "reject", reason: "off-ICP", row, nowIso: NOW });
  assert.equal(out.outcome, "rejected");
  assert.equal(Object.keys(out.properties).length, 1);
});

test("approve is explicitly unsupported in this plan and writes nothing", () => {
  const out = buildReviewDecision({
    decision: "approve", reason: "looks right", row: flaggedRow(), nowIso: NOW,
  });
  assert.equal(out.outcome, "unsupported");
  assert.deepEqual(out.properties, {});
  assert.match(out.message, /approve/i);
});

test("an unknown decision word is refused", () => {
  for (const decision of ["defer", "REJECT", "", null, undefined, 7, { decision: "reject" }]) {
    const out = buildReviewDecision({ decision, reason: "x", row: flaggedRow(), nowIso: NOW });
    assert.equal(out.outcome, "refused", `decision ${JSON.stringify(decision)} must be refused`);
    assert.deepEqual(out.properties, {});
  }
});

test("a missing record is refused, never guessed at", () => {
  for (const row of [undefined, null, "789", [], { record_found: false }, { hs_object_id: "" }]) {
    const out = buildReviewDecision({ decision: "reject", reason: "x", row, nowIso: NOW });
    assert.equal(out.outcome, "refused");
    assert.deepEqual(out.properties, {});
  }
});

test("a non-string reason is refused; an absent one is accepted as empty (D-09)", () => {
  for (const reason of [7, true, { text: "x" }, ["x"]]) {
    const out = buildReviewDecision({ decision: "reject", reason, row: flaggedRow(), nowIso: NOW });
    assert.equal(out.outcome, "refused", `reason ${JSON.stringify(reason)} must be refused`);
  }
  for (const reason of ["", undefined, null]) {
    const out = buildReviewDecision({ decision: "reject", reason, row: flaggedRow(), nowIso: NOW });
    assert.equal(out.outcome, "rejected", "a decision without a reason is still a decision");
    assert.equal(out.properties[P_REVIEW_REASON], "");
  }
});

test("an over-long reason is truncated at the HubSpot text ceiling, not refused", () => {
  const out = buildReviewDecision({
    decision: "reject", reason: "z".repeat(60001), row: flaggedRow(), nowIso: NOW,
  });
  assert.equal(out.outcome, "rejected");
  assert.equal(out.properties[P_REVIEW_REASON].length, 60000);
});

test("buildReviewDecision never throws, whatever it is handed", () => {
  for (const input of [undefined, null, {}, { row: {} }, { decision: "reject" }, 42, "x"]) {
    assert.doesNotThrow(() => buildReviewDecision(input));
  }
});

test("the module requires nothing outside n8n/code/", () => {
  const src = fs.readFileSync(MODULE_PATH, "utf8");
  for (const m of src.matchAll(/require\(\s*"([^"]+)"\s*\)/g)) {
    assert.match(m[1], /^\.\/[A-Za-z0-9_.]+$/,
      `reviewDecision.js may only require siblings in n8n/code/ — found ${m[1]}`);
  }
});

// =====================================================================================
// (2) FLOW — the COMMITTED workflow's own node jsCode
// =====================================================================================

const WF_PATH = path.join(ROOT, "n8n", "wf_review_decision_cloud.json");
const WF = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

function jsCodeOf(name) {
  const node = WF.nodes.find((n) => n.name === name);
  assert.ok(node, `node present in the committed workflow: ${name}`);
  assert.equal(node.type, "n8n-nodes-base.code");
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) the way n8n's Code node runs it.
 * `nodeOutputs` supplies the `$('Node Name')` accessor; a node not listed there throws,
 * so a body silently reaching for an unexpected upstream node fails loudly. */
function runNode(jsCode, seedItems, nodeOutputs) {
  const wrap = (rows) => rows.map((j) => ({ json: j }));
  const $input = {
    all: () => wrap(seedItems),
    first: () => (seedItems.length ? { json: seedItems[0] } : undefined),
  };
  const $ = (name) => {
    assert.ok(nodeOutputs && name in nodeOutputs,
      `jsCode reached for an upstream node this test did not provide: ${name}`);
    const items = wrap(nodeOutputs[name]);
    return { first: () => items[0], all: () => items, item: items[0] };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

/** The EXACT literal swap enable_baked_flags() performs, with a match assertion so a
 * drift in how the builder spells a constant fails here rather than passing vacuously. */
function armConstants(jsCode, constants) {
  let out = jsCode;
  for (const [name, value] of Object.entries(constants)) {
    const from = `const ${name} = "";`;
    const fromFalse = `const ${name} = "false";`;
    const decl = out.includes(fromFalse) ? fromFalse : from;
    assert.ok(out.includes(decl),
      `committed jsCode must carry the disabled ${name} declaration verbatim`);
    out = out.replace(decl, `const ${name} = ${JSON.stringify(value)};`);
  }
  return out;
}

const GATE = "Review Decision Update Write Gate";
const REJECT_BODY = {
  object_type: "companies",
  record_id: "789",
  decision: "reject",
  reason: "Broadcaster, not a governing body — the evidence URL is a rights page.",
  reviewed_by: "revops@example.com",
};

/** webhook item -> Parse Review Decision -> Build Review Decision. Returns both. */
function drive(body, row) {
  const [parsed] = runNode(jsCodeOf("Parse Review Decision"), [{ body }], {});
  const [built] = runNode(jsCodeOf("Build Review Decision"), [row || flaggedRow()],
    { "Parse Review Decision": [parsed] });
  return { parsed, built };
}

// --- (a) preview: dry_run absent -> would_write, and the gate is never fed -------------

test("(a) a rejection with dry_run ABSENT previews: exactly the review-reason property, routed to the response", () => {
  const { parsed, built } = drive(REJECT_BODY);
  assert.equal(parsed.dry_run, true, "absent dry_run must default to true (D-03)");
  assert.equal(built.outcome, "rejected");
  assert.deepEqual(Object.keys(built.would_write), [P_REVIEW_REASON]);
  assert.equal(built.would_write[P_REVIEW_REASON], REJECT_BODY.reason);
  assert.equal(built.dry_run, true, "the dry-run branch routes to the response, not the gate");
});

test("(a2) a non-writing outcome routes to the response even when dry_run is explicitly false", () => {
  const unflagged = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "false", [P_CANDIDATE_JSON]: "",
  });
  const { built } = drive({ ...REJECT_BODY, dry_run: false }, unflagged);
  assert.equal(built.outcome, "not_flagged");
  assert.deepEqual(built.would_write, {});
  assert.equal(built.dry_run, true, "nothing to write must never reach the write gate");
});

// --- (b)/(c)/(d) the gate, in both arming directions -----------------------------------

test("(b) a real rejection through the COMMITTED (disarmed) gate yields zero items", () => {
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  assert.equal(built.dry_run, false, "non-vacuity: this row does reach the write branch");
  assert.equal(built.hs_object_id, "789");
  assert.equal(built.domain, "exampleracing.example",
    "row-carry: the gate's domain allowlist can only work if the row still carries domain");
  assert.equal(runNode(jsCodeOf(GATE), [built], {}).length, 0);
});

test("(c) the SAME row passes with ONLY ALLOW_HUBSPOT_REVIEW_WRITES armed + a matching allowlist", () => {
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  const armed = armConstants(jsCodeOf(GATE), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "789",
  });
  const passed = runNode(armed, [built], {});
  assert.equal(passed.length, 1, "review arming must authorise a review write");
  assert.deepEqual(Object.keys(passed[0].properties), [P_REVIEW_REASON]);
});

test("(c2) the review flag armed with an EMPTY allowlist still denies everything", () => {
  // Inherited from the shared allowlist check and deliberately NOT special-cased for
  // review (30-01): an armed deploy with no TEST_RECORD_* entry reports success and
  // grants nothing. Asserted, not treated as a bug.
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  const armed = armConstants(jsCodeOf(GATE), { ALLOW_HUBSPOT_REVIEW_WRITES: "true" });
  assert.equal(runNode(armed, [built], {}).length, 0);
});

test("(d) the two DISPATCH constants armed instead, review left disarmed, drops the row", () => {
  // (b) and (d) differ from (c) only in WHICH constant is armed, so this pair fails the
  // moment the review gate starts reading a dispatch constant (D-02).
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  const armed = armConstants(jsCodeOf(GATE), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true", ALLOW_HUBSPOT_CREATE: "true", TEST_RECORD_IDS: "789",
  });
  assert.equal(runNode(armed, [built], {}).length, 0);
});

// --- (e) the caller cannot inject a write (T-30-05, D-05/D-07) -------------------------

test("(e) extra properties/field/value keys in the body are parsed as if absent", () => {
  const clean = drive({ ...REJECT_BODY, dry_run: false });
  const injected = drive({
    ...REJECT_BODY,
    dry_run: false,
    properties: { domain: "attacker.example", lv_org_type: "governing_body_league" },
    field: "lv_org_type",
    value: "governing_body_league",
    lv_enrichment_needs_review: "false",
  });

  assert.deepEqual(Object.keys(injected.parsed).sort(),
    ["decision", "dry_run", "object_type", "reason", "record_id", "reviewed_by"],
    "Parse Review Decision emits exactly the six accepted keys and nothing else");
  assert.deepEqual(injected.built.properties, clean.built.properties,
    "the built patch body is unchanged by the injected keys");
  assert.deepEqual(injected.built.would_write, clean.built.would_write);
  assert.equal("domain" in injected.built.properties, false);
  assert.equal("lv_org_type" in injected.built.properties, false);
});

// --- (f) the response contract 30-06 consumes (D-19) -----------------------------------

const CONTRACT_KEYS = ["message", "outcome", "verified", "verified_properties", "would_write"];

function verifyEnvelope(properties) {
  return { results: [{ id: "789", properties }] };
}

function respond(built, verifyItem) {
  return runNode(jsCodeOf("Build Review Response"), [verifyItem],
    { "Build Review Decision": [built] })[0];
}

test("(f1) a written decision whose refetch matches would_write: verified true, properties populated", () => {
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  const out = respond(built, verifyEnvelope({ [P_REVIEW_REASON]: REJECT_BODY.reason }));

  assert.deepEqual(Object.keys(out).sort(), CONTRACT_KEYS);
  assert.equal(out.outcome, "rejected");
  assert.equal(out.verified, true);
  assert.deepEqual(out.verified_properties, { [P_REVIEW_REASON]: REJECT_BODY.reason });
});

test("(f2) a written decision whose refetch still holds pre-write content: verified false, and the key is visible", () => {
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  const out = respond(built, verifyEnvelope({ [P_REVIEW_REASON]: "an older reason" }));

  assert.deepEqual(Object.keys(out).sort(), CONTRACT_KEYS);
  assert.equal(out.verified, false);
  assert.equal(out.verified_properties[P_REVIEW_REASON], "an older reason",
    "the operator must be able to see WHAT the record actually holds");
});

test("(f3) the dry-run branch returns the same five keys with verified_properties and verified null", () => {
  const { built } = drive(REJECT_BODY);
  // On the dry-run branch the responder's input IS the decision item itself.
  const out = respond(built, built);

  assert.deepEqual(Object.keys(out).sort(), CONTRACT_KEYS);
  assert.equal(out.verified_properties, null);
  assert.equal(out.verified, null);
  assert.deepEqual(out.would_write, { [P_REVIEW_REASON]: REJECT_BODY.reason },
    "a dry run still returns the exact write it would have made (REVIEW-03)");
});

test("(f4) a written decision whose refetch found nothing reports null, never a default-true", () => {
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  const out = respond(built, { results: [] });

  assert.deepEqual(Object.keys(out).sort(), CONTRACT_KEYS);
  assert.equal(out.verified_properties, null);
  assert.equal(out.verified, null, "an unreadable read-back is a failure to report, not a success");
});

test("(f5) a refused request returns the contract too, with an empty would_write", () => {
  const { built } = drive({ ...REJECT_BODY, decision: "defer" });
  const out = respond(built, built);
  assert.deepEqual(Object.keys(out).sort(), CONTRACT_KEYS);
  assert.equal(out.outcome, "refused");
  assert.deepEqual(out.would_write, {});
  assert.equal(out.verified_properties, null);
  assert.equal(out.verified, null);
});

// --- committed-artifact wiring ---------------------------------------------------------

test("the verify refetch is reachable ONLY from the write branch, and both branches converge on one responder", () => {
  const feeders = (name) => Object.entries(WF.connections)
    .filter(([, spec]) => (spec.main || []).some((o) => (o || []).some((c) => c.node === name)))
    .map(([src]) => src);

  assert.deepEqual(feeders("Review Verify Fetch"), ["Review Decision Update"],
    "a dry run must never pay for the refetch, and the refetch must follow the PATCH");
  assert.deepEqual(feeders("Build Review Response").sort(),
    ["Review IF Dry Run", "Review Verify Fetch"]);
  assert.deepEqual(feeders("Respond Review Decision"), ["Build Review Response"],
    "one node shapes the response body on both branches");

  const [dryBranch, writeBranch] = WF.connections["Review IF Dry Run"].main;
  assert.deepEqual(dryBranch.map((c) => c.node), ["Build Review Response"]);
  assert.deepEqual(writeBranch.map((c) => c.node), [GATE]);

  // The verify fetch must read the record independently, not the PATCH's echo.
  const verify = WF.nodes.find((n) => n.name === "Review Verify Fetch");
  assert.equal(verify.type, "n8n-nodes-base.httpRequest");
  assert.match(verify.parameters.url, /objects\/companies\/search$/);
  assert.match(verify.parameters.jsonBody, /propertyName:\s*"hs_object_id"/);
  assert.equal(WF.active, false);
});
