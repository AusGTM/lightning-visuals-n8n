// tests/n8n/contactJudge.test.mjs
//
// Phase 16.2 Task 1 — contactJudge.js: computeContactEscalation's 2-arg arity + trigger
// matrix (normalized compare, gpt #12; no stale reason, LOW-7), applyContactUnadjudicated,
// buildContactJudgeRequestBody's JG-2 payload shape, and the SECURITY-HARDENED
// applyContactJudgeVerdict (chosen_field allowlist + decision/confidence gate, gpt #5).
//
// Run: node --test tests/n8n/contactJudge.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  _CONTACT_JUDGE_FIELDS, computeContactEscalation, applyContactUnadjudicated,
  buildContactJudgeRequestBody, applyContactJudgeVerdict,
} = require(path.join(ROOT, "n8n/code/contactJudge.js"));

// --- computeContactEscalation: arity + RO-1 + trigger matrix ---------------------------

test("arity: computeContactEscalation takes exactly two arguments (judge.js:97-102 discipline)", () => {
  assert.equal(computeContactEscalation.length, 2);
});

test("RO-1(a): computeContactEscalation(null, {...}) -> needsJudge:false", () => {
  const r = computeContactEscalation(null, { jobtitle: "Analyst" });
  assert.equal(r.needsJudge, false);
  assert.deepEqual(r.reasons, []);
});

test("RO-1(b): an unmatched candidate cannot escalate even carrying a trigger-shaped value", () => {
  const r = computeContactEscalation({ matched: false, data: { jobtitle: "CEO" } }, { jobtitle: "Analyst" });
  assert.equal(r.needsJudge, false);
});

test("jobtitle_conflict: existing jobtitle known + research differs -> needsJudge:true", () => {
  const r = computeContactEscalation(
    { matched: true, confidence: 92, data: { jobtitle: "Head of Racing" } },
    { jobtitle: "Analyst" },
  );
  assert.equal(r.needsJudge, true);
  assert.ok(r.reasons.includes("jobtitle_conflict"));
});

test("gpt #12: jobtitle_conflict does NOT false-positive on casing (\"CEO\" vs \"ceo\")", () => {
  const r = computeContactEscalation(
    { matched: true, confidence: 92, data: { jobtitle: "ceo" } },
    { jobtitle: "CEO" },
  );
  assert.ok(!r.reasons.includes("jobtitle_conflict"));
});

test("jobtitle_conflict does not fire when existing jobtitle is blank (first-time resolution, not a flip)", () => {
  const r = computeContactEscalation(
    { matched: true, confidence: 92, data: { jobtitle: "Head of Racing" } },
    { jobtitle: "" },
  );
  assert.ok(!r.reasons.includes("jobtitle_conflict"));
  assert.equal(r.needsJudge, false);
});

test("seniority_conflict: normalized compare, mirrors jobtitle_conflict", () => {
  const r = computeContactEscalation(
    { matched: true, confidence: 92, data: { seniority: "Director" } },
    { seniority: "manager" },
  );
  assert.equal(r.needsJudge, true);
  assert.ok(r.reasons.includes("seniority_conflict"));

  const noConflict = computeContactEscalation(
    { matched: true, confidence: 92, data: { seniority: "  Director  " } },
    { seniority: "director" },
  );
  assert.ok(!noConflict.reasons.includes("seniority_conflict"));
});

test("confidence_band: [75,85] with a carried signal triggers; outside the band does not", () => {
  const data = { jobtitle: "Head of Racing" };
  for (const conf of [75, 80, 85]) {
    const r = computeContactEscalation({ matched: true, confidence: conf, data }, {});
    assert.ok(r.reasons.includes("confidence_band"), `confidence ${conf} should trigger confidence_band`);
  }
  for (const conf of [74, 86]) {
    const r = computeContactEscalation({ matched: true, confidence: conf, data }, {});
    assert.ok(!r.reasons.includes("confidence_band"), `confidence ${conf} should NOT trigger confidence_band`);
  }
});

test("confidence_band does not fire when the candidate carries no jobtitle/seniority signal", () => {
  const r = computeContactEscalation({ matched: true, confidence: 80, data: {} }, {});
  assert.ok(!r.reasons.includes("confidence_band"));
  assert.equal(r.needsJudge, false);
});

test("NO stale reason ever appears (LOW-7 — staleness lives in the research gate, not here)", () => {
  const r = computeContactEscalation(
    { matched: true, confidence: 92, data: { jobtitle: "Head of Racing" } },
    { jobtitle: "Head of Racing" },
  );
  assert.ok(!r.reasons.some((x) => /stale/i.test(x)));
});

// --- applyContactUnadjudicated: drops the conflicting field -----------------------------

test("applyContactUnadjudicated drops data.jobtitle on jobtitle_conflict, leaves seniority untouched", () => {
  const candidate = {
    data: { jobtitle: "Head of Racing", seniority: "director" },
    evidence_by_field: { jobtitle: "https://x/team", seniority: "https://x/team" },
  };
  const result = applyContactUnadjudicated(candidate, ["jobtitle_conflict"]);
  assert.ok(!("jobtitle" in result.data));
  assert.ok(!("jobtitle" in result.evidence_by_field));
  assert.equal(result.data.seniority, "director");
  assert.equal(result.judge_flags.unadjudicated, true);
  // no in-place mutation
  assert.equal(candidate.data.jobtitle, "Head of Racing");
});

test("applyContactUnadjudicated drops data.seniority on seniority_conflict", () => {
  const candidate = { data: { jobtitle: "Head of Racing", seniority: "director" }, evidence_by_field: {} };
  const result = applyContactUnadjudicated(candidate, ["seniority_conflict"]);
  assert.ok(!("seniority" in result.data));
  assert.equal(result.data.jobtitle, "Head of Racing");
});

test("applyContactUnadjudicated: null researchCandidate passes through, never throws", () => {
  assert.equal(applyContactUnadjudicated(null, []), null);
});

// --- buildContactJudgeRequestBody: JG-2 payload shape -----------------------------------

function scoringRow(extra) {
  return {
    identity_keys: { contactName: "Jamie Rivera", companyName: "Example Racing" },
    existingRecord: { jobtitle: "Analyst", seniority: "manager" },
    research_candidate: {
      data: { jobtitle: "Head of Racing", seniority: "director" },
      evidence_by_field: { jobtitle: "https://x/team" },
    },
    judge_reasons: ["jobtitle_conflict"],
    ...extra,
  };
}

test("buildContactJudgeRequestBody: no size/vendor field name, no tools key, no web-search tool reference", () => {
  const body = buildContactJudgeRequestBody(scoringRow(), "claude-sonnet-5", 2048);
  const serialized = JSON.stringify(body);
  assert.ok(!/revenue/i.test(serialized));
  assert.ok(!/employee/i.test(serialized));
  assert.ok(!/hardware/i.test(serialized));
  assert.ok(!/gambling/i.test(serialized));
  assert.ok(!("tools" in body), "no tools key at all (Pitfall 5 analog)");
  assert.ok(!/web.search/i.test(serialized), "no web-search tool reference");
  assert.equal(body.max_tokens, 2048);
});

test("buildContactJudgeRequestBody: restricts research_candidate.data to jobtitle/seniority only", () => {
  const row = scoringRow({
    research_candidate: {
      data: { jobtitle: "Head of Racing", seniority: "director", email: "leak@example.com" },
      evidence_by_field: {},
    },
  });
  const body = buildContactJudgeRequestBody(row, "claude-sonnet-5", 2048);
  const parsed = JSON.parse(body.messages[0].content);
  assert.deepEqual(Object.keys(parsed.contact.research_candidate.data).sort(), ["jobtitle", "seniority"]);
  assert.ok(!JSON.stringify(parsed).includes("leak@example.com"), "no PII field ever enters the payload");
});

test("buildContactJudgeRequestBody: required output keys include chosen_field, restricted to jobtitle/seniority", () => {
  const body = buildContactJudgeRequestBody(scoringRow(), "claude-sonnet-5", 2048);
  assert.ok(body.system.includes("chosen_field"));
  assert.ok(body.system.includes("jobtitle"));
  assert.ok(body.system.includes("seniority"));
});

test("buildContactJudgeRequestBody: a row with no research_candidate at all still produces a valid body", () => {
  const row = scoringRow();
  delete row.research_candidate;
  const body = buildContactJudgeRequestBody(row, "claude-sonnet-5", 2048);
  const parsed = JSON.parse(body.messages[0].content);
  assert.deepEqual(parsed.contact.research_candidate.data, {});
});

// --- applyContactJudgeVerdict: SECURITY-HARDENED (gpt #5) -------------------------------

test("SECURITY: chosen_field:'email' never writes email, even at promote/confidence:95", () => {
  const candidate = { data: { jobtitle: "Analyst" } };
  const verdict = { decision: "promote", chosen_field: "email", chosen_value: "leaked@example.com", confidence: 95 };
  const result = applyContactJudgeVerdict(candidate, verdict, []);
  assert.ok(!("email" in result.data));
  assert.ok(!result.judge_flags || result.judge_flags.promoted_field !== "email");
  assert.notEqual(result.judge_flags && result.judge_flags.promoted_field, "email");
});

test("SECURITY: a validated promote on chosen_field:'jobtitle' writes it + sets judge_flags.promoted_field", () => {
  const candidate = { data: { jobtitle: "Analyst" } };
  const verdict = { decision: "promote", chosen_field: "jobtitle", chosen_value: "Head of Racing", confidence: 90 };
  const result = applyContactJudgeVerdict(candidate, verdict, []);
  assert.equal(result.data.jobtitle, "Head of Racing");
  assert.equal(result.judge_flags.promoted_field, "jobtitle");
  assert.equal(result.judge_flags.adjudicated, true);
});

test("SECURITY: sub-threshold confidence (70) routes to unadjudicated, never promotes", () => {
  const candidate = { data: { jobtitle: "Analyst" } };
  const verdict = { decision: "promote", chosen_field: "jobtitle", chosen_value: "Head of Racing", confidence: 70 };
  const result = applyContactJudgeVerdict(candidate, verdict, ["jobtitle_conflict"]);
  assert.ok(!("jobtitle" in result.data), "sub-threshold verdict must drop jobtitle (unadjudicated), not keep old value implicitly promoted");
  assert.ok(!result.judge_flags.promoted_field);
});

test("SECURITY: a garbage/malformed verdict never throws and never promotes", () => {
  for (const garbage of [null, undefined, "not an object", 42, []]) {
    assert.doesNotThrow(() => applyContactJudgeVerdict({ data: { jobtitle: "Analyst" } }, garbage, []));
    const result = applyContactJudgeVerdict({ data: { jobtitle: "Analyst" } }, garbage, []);
    assert.ok(!result.judge_flags || !result.judge_flags.promoted_field);
  }
});

test("SECURITY: decision confirm at sufficient confidence also promotes (mirrors judge.js's promote/confirm pair)", () => {
  const candidate = { data: { seniority: "manager" } };
  const verdict = { decision: "confirm", chosen_field: "seniority", chosen_value: "director", confidence: 85 };
  const result = applyContactJudgeVerdict(candidate, verdict, []);
  assert.equal(result.data.seniority, "director");
  assert.equal(result.judge_flags.promoted_field, "seniority");
});

test("_CONTACT_JUDGE_FIELDS is exactly jobtitle/seniority", () => {
  assert.deepEqual(_CONTACT_JUDGE_FIELDS, ["jobtitle", "seniority"]);
});
