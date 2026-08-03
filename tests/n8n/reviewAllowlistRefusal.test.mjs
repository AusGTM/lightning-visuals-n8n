// tests/n8n/reviewAllowlistRefusal.test.mjs
//
// Phase 31 Plan 02 — BUG 30: an allowlist drop used to answer NO body at all, and the
// client reported the same `unparseable_response` for that AND for a genuine workflow
// error. `Build Review Decision` now computes the SAME `_writeSafetyAllows("review", ...)`
// verdict the committed `Review Decision Update Write Gate` applies, and answers an
// explicit `not_allowlisted` refusal before the row ever reaches the gate.
//
// This file pins:
//   (1) the COMMITTED (disarmed) pre-check refuses explicitly, with an empty would_write
//       and dry_run forced true — never silence
//   (2) arming the pre-check reaches the ordinary outcome and the write branch
//   (3) a preview (dry_run absent) never sees the refusal, whatever the arming
//   (4) a reject and an approve refuse IDENTICALLY when not permitted
//   (5) a contacts row (no `domain`) follows the SAME id-only allowlist rule as the gate
//   (6) AGREEMENT MATRIX — the pre-check and the COMMITTED write gate NEVER disagree on
//       permit/deny, across the same four arming combinations
//       reviewDecisionEndpoint.test.mjs exercises for the gate alone ((b)(c)(c2)(d)). This
//       is what stops the pre-check silently becoming a second, weaker authority (T-31-06).
//
// No test here issues a network call. Arming is the EXACT literal swap
// scripts/deploy_n8n_workflows.py's enable_baked_flags() performs (see armConstants).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { mergeCompanies, stableStringify } =
  require(path.join(ROOT, "n8n/code/mergeCompanies.js"));

const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_REVIEW_REASON = "lv_enrichment_review_reason";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";

const WF_PATH = path.join(ROOT, "n8n", "wf_review_decision_cloud.json");
const WF = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

function jsCodeOf(name) {
  const node = WF.nodes.find((n) => n.name === name);
  assert.ok(node, `node present in the committed workflow: ${name}`);
  assert.equal(node.type, "n8n-nodes-base.code");
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) the way n8n's Code node runs it. */
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

// Same fixture shape as reviewDecisionEndpoint.test.mjs's flaggedRow(): a REAL
// mergeCompanies() run filtered to needs_review, so the candidate JSON cannot drift from
// what the pipeline actually stores.
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

const PRECHECK = "Build Review Decision";
const GATE = "Review Decision Update Write Gate";

const REJECT_BODY = {
  object_type: "companies", record_id: "789", decision: "reject",
  reason: "Broadcaster, not a governing body — the evidence URL is a rights page.",
  reviewed_by: "revops@example.com",
};
const APPROVE_BODY = {
  object_type: "companies", record_id: "789", decision: "approve",
  reason: "Evidence supports the governing-body classification.",
  reviewed_by: "revops@example.com",
};

/** webhook item -> Parse Review Decision -> Build Review Decision (optionally an ARMED
 * copy of the pre-check's jsCode). Returns both. */
function drive(body, row, precheckJs) {
  const [parsed] = runNode(jsCodeOf("Parse Review Decision"), [{ body }], {});
  const [built] = runNode(precheckJs || jsCodeOf(PRECHECK), [row || flaggedRow()],
    { "Parse Review Decision": [parsed] });
  return { parsed, built };
}

// =====================================================================================
// (1) the COMMITTED (disarmed) pre-check refuses explicitly
// =====================================================================================

test("a real submit through the COMMITTED disarmed pre-check returns not_allowlisted, empty would_write, dry_run true", () => {
  const { built } = drive({ ...REJECT_BODY, dry_run: false });
  assert.equal(built.outcome, "not_allowlisted");
  assert.deepEqual(built.would_write, {});
  assert.equal(built.dry_run, true,
    "a refusal must route straight to the response, never touch the write gate");
  assert.match(built.message, /allowlist/i);
});

// =====================================================================================
// (2) arming the pre-check reaches the ordinary outcome and the write branch
// =====================================================================================

test("the SAME row through the pre-check armed with ALLOW_HUBSPOT_REVIEW_WRITES + a matching allowlist reaches the ordinary outcome", () => {
  const armed = armConstants(jsCodeOf(PRECHECK), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "789",
  });
  const { built } = drive({ ...REJECT_BODY, dry_run: false }, undefined, armed);
  assert.equal(built.outcome, "rejected");
  assert.equal(built.dry_run, false, "an authorised write must reach the gate");
  assert.deepEqual(built.would_write, { [P_REVIEW_REASON]: REJECT_BODY.reason });
});

// =====================================================================================
// (3) a preview never sees the refusal, whatever the arming
// =====================================================================================

test("a preview (dry_run absent) against the disarmed pre-check still returns the full would_write patch and never not_allowlisted", () => {
  const { parsed, built } = drive(REJECT_BODY);
  assert.equal(parsed.dry_run, true, "absent dry_run must default to true (D-03)");
  assert.equal(built.outcome, "rejected");
  assert.notEqual(built.outcome, "not_allowlisted");
  assert.deepEqual(built.would_write, { [P_REVIEW_REASON]: REJECT_BODY.reason });
  assert.equal(built.dry_run, true);
});

test("a preview against an ARMED pre-check still shows the exact write and stays a preview", () => {
  const armed = armConstants(jsCodeOf(PRECHECK), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "789",
  });
  const { built } = drive(REJECT_BODY, undefined, armed);
  assert.notEqual(built.outcome, "not_allowlisted");
  assert.equal(built.dry_run, true, "a preview never reaches the write branch, armed or not");
});

// =====================================================================================
// (4) a reject and an approve refuse IDENTICALLY when not permitted
// =====================================================================================

test("a reject and an approve both refuse identically when not permitted", () => {
  const { built: rejected } = drive({ ...REJECT_BODY, dry_run: false });
  const { built: approved } = drive({ ...APPROVE_BODY, dry_run: false });
  assert.equal(rejected.outcome, "not_allowlisted");
  assert.equal(approved.outcome, "not_allowlisted");
  assert.deepEqual(rejected.would_write, {});
  assert.deepEqual(approved.would_write, {});
});

// =====================================================================================
// (5) a contacts row follows the SAME id-only allowlist rule as the gate (30-02 g3)
// =====================================================================================

test("a contacts row with no domain: an id-matching allowlist permits, a domain-only allowlist does not", () => {
  const contactRow = {
    hs_object_id: "4242", record_found: true,
    email: "person@example.com", firstname: "Pat", lastname: "Lee",
    [P_NEEDS_REVIEW]: "true", [P_CANDIDATE_JSON]: "",
  };
  const contactBody = { ...REJECT_BODY, object_type: "contacts", dry_run: false };
  assert.equal("domain" in contactRow, false, "non-vacuity for the assertion below");

  const armedByDomain = armConstants(jsCodeOf(PRECHECK), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_DOMAINS: "example.com",
  });
  const byDomain = drive(contactBody, contactRow, armedByDomain);
  assert.equal(byDomain.built.outcome, "not_allowlisted",
    "a domain allowlist cannot reach a contact — the pre-check must agree with the gate");

  const armedById = armConstants(jsCodeOf(PRECHECK), {
    ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "4242",
  });
  const byId = drive(contactBody, contactRow, armedById);
  assert.equal(byId.built.outcome, "rejected");
});

// =====================================================================================
// (6) AGREEMENT MATRIX — the pre-check and the COMMITTED write gate never disagree
// =====================================================================================

const ARMING_MATRIX = [
  { name: "(b) disarmed", constants: {} },
  { name: "(c) review armed + a matching allowlist",
    constants: { ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "789" } },
  { name: "(c2) review armed, empty allowlist",
    constants: { ALLOW_HUBSPOT_REVIEW_WRITES: "true" } },
  { name: "(d) the two DISPATCH constants armed instead, review left disarmed",
    constants: {
      ALLOW_HUBSPOT_RECORD_WRITES: "true", ALLOW_HUBSPOT_CREATE: "true", TEST_RECORD_IDS: "789",
    } },
];

for (const { name, constants } of ARMING_MATRIX) {
  test(`agreement matrix ${name}: pre-check permit/deny matches the committed write gate`, () => {
    const precheckJs = armConstants(jsCodeOf(PRECHECK), constants);
    const gateJs = armConstants(jsCodeOf(GATE), constants);

    const { built } = drive({ ...REJECT_BODY, dry_run: false }, undefined, precheckJs);
    const precheckPermits = built.outcome !== "not_allowlisted";

    // Drive the SAME row through the gate via a DISARMED pre-check's output, so the row
    // still carries the hs_object_id/domain the gate itself reads — same shape (b)(c)(c2)(d)
    // already use in reviewDecisionEndpoint.test.mjs.
    const disarmedBuilt = drive({ ...REJECT_BODY, dry_run: false }).built;
    const gatePermits = runNode(gateJs, [disarmedBuilt], {}).length === 1;

    assert.equal(precheckPermits, gatePermits,
      `${name}: pre-check said permit=${precheckPermits}, gate said permit=${gatePermits}`);
  });
}
