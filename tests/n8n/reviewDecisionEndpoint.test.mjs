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

// --- approve (Plan 03) ------------------------------------------------------------------
//
// The approve path applies the record's OWN stored candidate through reviewApply's
// compare-and-set — the phase's single non-clobber authority (D-05/D-08d/D-15). These
// cases pin the outcomes; tests/n8n/reviewHumanProvenance.test.mjs pins the blob.

const P_PROVENANCE = "lv_enrichment_provenance";

function approve(overrides) {
  const { row, ...rest } = overrides || {};
  return buildReviewDecision({
    objectType: "companies", decision: "approve", reason: "Confirmed from the About page.",
    reviewedBy: "revops@example.com", row: row || flaggedRow(), nowIso: NOW, ...rest,
  });
}

/** The held candidate as an ARRAY, so a case can forge an extra decision into it. */
function heldDecisions(row) {
  return JSON.parse(row[P_CANDIDATE_JSON]);
}

test("approve on a clean flagged row applies the held candidate, clears the queue, and stamps the human", () => {
  const out = approve();
  assert.equal(out.outcome, "applied");

  // reviewApply's canonical patch — the candidate's own chosen values, unchanged.
  assert.equal(out.properties.lv_org_type, "governing_body_league");
  assert.equal(out.properties.lv_produces_content, true);
  // ...plus its clear patch, which is what takes the record OUT of the queue. Unlike a
  // rejection (D-10), an approval is entitled to: the decision is recorded alongside it.
  assert.equal(out.properties[P_NEEDS_REVIEW], false);
  assert.equal(out.properties[P_CANDIDATE_JSON], "");
  assert.equal(typeof out.properties[P_REVIEWED_AT], "string",
    "reviewApply's clear patch stamps reviewed-at; this module must not stamp it twice");
  assert.equal(out.properties[P_REVIEWED_BY], "revops@example.com");
  assert.equal(typeof out.properties[P_PROVENANCE], "string");
});

test("approve on a drifted record writes NOTHING and leaves it queued (reviewApply's stale path)", () => {
  // A manual edit landed after the candidate was frozen: the live value no longer matches
  // the decision's stored current_value.
  const row = flaggedRow({ lv_org_type: "content_producer" });
  const out = approve({ row });

  assert.equal(out.outcome, "stale");
  assert.deepEqual(out.properties, {});
  assert.match(out.message, /lv_org_type/, "the operator must learn WHICH field drifted");
  assert.equal(P_NEEDS_REVIEW in out.properties, false, "a stale record stays in the queue");
});

test("approve with no held candidate is refused honestly — this is what a dedupe-flagged row hits", () => {
  for (const candidate of ["", "[]", undefined, null, "   "]) {
    const row = flaggedRow({ [P_CANDIDATE_JSON]: candidate, [P_ICP_NEEDS_REVIEW]: "true" });
    const out = approve({ row });
    assert.equal(out.outcome, "no_candidate", `candidate ${JSON.stringify(candidate)}`);
    assert.deepEqual(out.properties, {});
  }
});

test("approve on a malformed candidate applies nothing and says so, rather than clearing the queue", () => {
  const out = approve({ row: flaggedRow({ [P_CANDIDATE_JSON]: '[{"field":' }) });
  assert.equal(out.outcome, "no_candidate");
  assert.deepEqual(out.properties, {},
    "a candidate that cannot be read must never reach reviewApply's clear patch");
});

test("approve on a row that is not actually flagged yields not_flagged and writes nothing", () => {
  const row = flaggedRow({
    [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "false", [P_CANDIDATE_JSON]: "",
  });
  const out = approve({ row });
  assert.equal(out.outcome, "not_flagged");
  assert.deepEqual(out.properties, {});
});

test("a forged candidate naming a manual_protected / review_required field cannot write it (REVIEW-02, T-30-11)", () => {
  // reviewApply's allowlist is the set of policy KEYS, and `domain` is one of them with
  // class manual_protected — so membership alone does NOT exclude it. This is D-12's hole.
  const base = flaggedRow();
  const forged = heldDecisions(base).concat([
    { field: "domain", current_value: "exampleracing.example", chosen_value: "attacker.example",
      decision: "needs_review", confidence: 99 },
    { field: "annualrevenue", current_value: null, chosen_value: "999999999",
      decision: "needs_review", confidence: 99 },
  ]);
  const out = approve({ row: flaggedRow({ [P_CANDIDATE_JSON]: JSON.stringify(forged) }) });

  assert.equal(out.outcome, "applied");
  assert.equal("domain" in out.properties, false,
    "a manual_protected field is never written by a review decision");
  assert.equal("annualrevenue" in out.properties, false,
    "nor is a review_required one");
  assert.equal(out.properties.lv_org_type, "governing_body_league",
    "a legitimate field in the SAME candidate still applies");
  assert.match(out.message, /domain/,
    "and the operator is told which fields were withheld");
});

test("approve on a contact writes nothing: no contacts candidate producer exists in this repo", () => {
  const out = approve({ objectType: "contacts" });
  assert.equal(out.outcome, "no_candidate");
  assert.deepEqual(out.properties, {});
});

test("an absent reviewed-by label is omitted, never written as an empty string", () => {
  for (const reviewedBy of [undefined, null, "", "   ", 7]) {
    const out = approve({ reviewedBy });
    assert.equal(P_REVIEWED_BY in out.properties, false,
      `writing "" would ERASE a previously recorded reviewer (${JSON.stringify(reviewedBy)})`);
    assert.equal(out.outcome, "applied");
  }
  const long = approve({ reviewedBy: "r".repeat(400) });
  assert.equal(long.properties[P_REVIEWED_BY].length, 255);
});

test("the compare-and-set is DELEGATED to reviewApply, never re-implemented here (D-05/D-15)", () => {
  const src = fs.readFileSync(MODULE_PATH, "utf8");
  assert.match(src, /require\("\.\/reviewApply"\)/,
    "reviewDecision.js must import the existing engine");
  assert.equal(/current_value/.test(src), false,
    "a second copy of the staleness comparison would be a second non-clobber authority");
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
  assert.deepEqual(feeders("Review Contact Verify Fetch"), ["Review Contact Decision Update"],
    "the contacts lane reads back too — a write with no read-back reports null forever");
  assert.deepEqual(feeders("Build Review Response").sort(),
    ["Review Contact Verify Fetch", "Review IF Dry Run", "Review Verify Fetch"]);
  assert.deepEqual(feeders("Respond Review Decision"), ["Build Review Response"],
    "one node shapes the response body on both branches");

  const [dryBranch, writeBranch] = WF.connections["Review IF Dry Run"].main;
  assert.deepEqual(dryBranch.map((c) => c.node), ["Build Review Response"]);
  assert.deepEqual(writeBranch.map((c) => c.node), ["Review IF Contact Write"]);

  // The verify fetch must read the record independently, not the PATCH's echo.
  const verify = WF.nodes.find((n) => n.name === "Review Verify Fetch");
  assert.equal(verify.type, "n8n-nodes-base.httpRequest");
  assert.match(verify.parameters.url, /objects\/companies\/search$/);
  assert.match(verify.parameters.jsonBody, /propertyName:\s*"hs_object_id"/);
  assert.equal(WF.active, false);
});

// --- (g) the contacts lane (Plan 03) ----------------------------------------------------

const CONTACT_GATE = "Review Contact Decision Update Write Gate";

test("(g1) object_type routes the fetch: contacts to the contact search, everything else to the company one", () => {
  const [contactBranch, companyBranch] = WF.connections["Review IF Contacts"].main;
  assert.deepEqual(contactBranch.map((c) => c.node), ["Review Contact Fetch By Id"]);
  assert.deepEqual(companyBranch.map((c) => c.node), ["Review Fetch By Id"]);

  const contactFetch = WF.nodes.find((n) => n.name === "Review Contact Fetch By Id");
  assert.match(contactFetch.parameters.url, /objects\/contacts\/search$/);
  // The contacts blob is a DIFFERENT property from the companies one (D-08a).
  assert.match(contactFetch.parameters.jsonBody, /lv_contact_enrichment_provenance/);
  assert.equal(/lv_enrichment_provenance"/.test(contactFetch.parameters.jsonBody), false);
  // Both lanes must fetch the same review family, or a decision would be possible on one
  // object type and not the other.
  for (const p of [P_NEEDS_REVIEW, P_ICP_NEEDS_REVIEW, P_REVIEW_REASON, P_CANDIDATE_JSON]) {
    assert.match(contactFetch.parameters.jsonBody, new RegExp(p));
  }

  // Both fetches converge on ONE extract node and ONE decision node.
  const feeders = (name) => Object.entries(WF.connections)
    .filter(([, spec]) => (spec.main || []).some((o) => (o || []).some((c) => c.node === name)))
    .map(([src]) => src).sort();
  assert.deepEqual(feeders("Review Extract Record"),
    ["Review Contact Fetch By Id", "Review Fetch By Id"]);
});

test("(g2) the write branch re-splits on object type, and BOTH PATCHes sit behind their own gate", () => {
  const [contactWrite, companyWrite] = WF.connections["Review IF Contact Write"].main;
  assert.deepEqual(contactWrite.map((c) => c.node), [CONTACT_GATE],
    "the contacts PATCH is reachable only through a write gate");
  assert.deepEqual(companyWrite.map((c) => c.node), [GATE]);
  assert.deepEqual(WF.connections[CONTACT_GATE].main[0].map((c) => c.node),
    ["Review Contact Decision Update"]);

  const patch = WF.nodes.find((n) => n.name === "Review Contact Decision Update");
  assert.match(patch.parameters.url, /objects\/contacts\//);
  assert.equal(patch.parameters.method, "PATCH");
});

test("(g3) a contacts REJECTION works exactly as a company one, and the contacts gate reads the review constant", () => {
  const contactRow = {
    hs_object_id: "4242", record_found: true,
    email: "person@example.com", firstname: "Pat", lastname: "Lee",
    [P_NEEDS_REVIEW]: "true", [P_CANDIDATE_JSON]: "",
  };
  const { built } = drive({ ...REJECT_BODY, object_type: "contacts", dry_run: false },
    contactRow);
  assert.equal(built.outcome, "rejected");
  assert.deepEqual(Object.keys(built.would_write), [P_REVIEW_REASON]);
  assert.equal(built.dry_run, false, "non-vacuity: this row does reach the write branch");

  assert.equal(runNode(jsCodeOf(CONTACT_GATE), [built], {}).length, 0,
    "committed and disarmed");
  // A contact carries no `domain`, so TEST_RECORD_IDS is the ONLY way to allowlist one.
  assert.equal("domain" in built, false, "non-vacuity for the assertion below");
  const armedByDomain = armConstants(jsCodeOf(CONTACT_GATE), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_DOMAINS: "example.com",
  });
  assert.equal(runNode(armedByDomain, [built], {}).length, 0,
    "a domain allowlist cannot reach a contact — the operator must use TEST_RECORD_IDS");
  const armedById = armConstants(jsCodeOf(CONTACT_GATE), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "4242",
  });
  assert.equal(runNode(armedById, [built], {}).length, 1);

  const dispatchArmed = armConstants(jsCodeOf(CONTACT_GATE), {
    ALLOW_HUBSPOT_RECORD_WRITES: "true", ALLOW_HUBSPOT_CREATE: "true", TEST_RECORD_IDS: "4242",
  });
  assert.equal(runNode(dispatchArmed, [built], {}).length, 0,
    "arming dispatch must never authorise a review write (D-02)");
});

test("(g4) a contacts APPROVE writes nothing and says why — no contact candidate is ever produced", () => {
  const contactRow = {
    hs_object_id: "4242", record_found: true, email: "person@example.com",
    [P_NEEDS_REVIEW]: "true", [P_CANDIDATE_JSON]: "",
  };
  const { built } = drive(
    { ...REJECT_BODY, object_type: "contacts", decision: "approve", dry_run: false },
    contactRow);
  assert.equal(built.outcome, "no_candidate");
  assert.deepEqual(built.would_write, {});
  assert.equal(built.dry_run, true, "nothing to write must never reach a write gate");

  const out = respond(built, built);
  assert.deepEqual(Object.keys(out).sort(), CONTRACT_KEYS);
  assert.equal(out.verified_properties, null);
  assert.equal(out.verified, null);
});

test("(g5) an APPROVE on a company routes through the endpoint's own inlined reviewApply", () => {
  // The whole point of Plan 03: the committed node's jsCode, not just the module.
  const { built } = drive({ ...REJECT_BODY, decision: "approve", dry_run: false });
  assert.equal(built.outcome, "applied");
  assert.equal(built.would_write.lv_org_type, "governing_body_league");
  assert.equal(built.would_write[P_NEEDS_REVIEW], false, "an approval clears the queue");
  assert.equal(typeof built.would_write[P_PROVENANCE], "string");
  assert.equal(JSON.parse(built.would_write[P_PROVENANCE]).lv_org_type.source, "human");
  assert.equal("domain" in built.would_write, false,
    "the manual_protected guard is live in the committed node, not only in the module");
});

// --- (h) the 15-minute backstop is untouched (D-08e/D-15) --------------------------------

test("(h) the scheduled maintenance workflow still carries its 15-minute review loop, wired in order", () => {
  const MW = JSON.parse(fs.readFileSync(
    path.join(ROOT, "n8n", "wf_scheduled_maintenance_cloud.json"), "utf8"));
  const names = new Set(MW.nodes.map((n) => n.name));
  for (const n of ["Review Trigger (15 min)", "Review Search (approved=true)",
                   "Apply Review", "Review Apply Update"]) {
    assert.ok(names.has(n), `the backstop node must still exist: ${n}`);
  }
  const next = (name) => (MW.connections[name].main[0] || []).map((c) => c.node);
  assert.deepEqual(next("Review Trigger (15 min)"), ["Review Search (approved=true)"]);
  assert.deepEqual(next("Review Search (approved=true)"), ["Review Extract Rows"]);
  assert.deepEqual(next("Review Extract Rows"), ["Apply Review"]);
  assert.ok(next("Apply Review").length, "Apply Review still feeds the loop's continuation");
  assert.equal(MW.active, false);
});
