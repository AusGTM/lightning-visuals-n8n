// tests/n8n/parity.test.mjs
//
// Parity suite for the pure-JS n8n Code-node ports against the tested Python oracle.
// Run: node --test tests/n8n/parity.test.mjs
//
// Two kinds of assertion:
//   1. EXPECTED-OUTCOME parity — the JS matches the same outcomes the Python tests encode.
//   2. GENUINE Python parity — for phone normalization and identity outcomes we shell
//      out to `.venv/bin/python` and assert JS === Python on the same inputs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const { normalizePhoneAU } = require(path.join(ROOT, "n8n/code/normalizePhone.js"));
const { normalizeEmailBasic } = require(path.join(ROOT, "n8n/code/normalizeEmail.js"));
const { mapRow, requiredIdentity } = require(path.join(ROOT, "n8n/code/columnMap.js"));
const { resolveIdentity } = require(path.join(ROOT, "n8n/code/resolveIdentity.js"));
const { mergeContacts } = require(path.join(ROOT, "n8n/code/mergeContacts.js"));
const { mergeCompanies, stableStringify } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));
const { dedupeSweep } = require(path.join(ROOT, "n8n/code/dedupeSweep.js"));
const {
  normalizeOrgType, normalizeOrgTypeResult, normalizeContentTypes,
} = require(path.join(ROOT, "n8n/code/taxonomy.js"));
const {
  validateResearchOutput, toProviderResult,
} = require(path.join(ROOT, "n8n/code/webResearch.js"));
const { isCitationSufficient } = require(path.join(ROOT, "n8n/code/judge.js"));

// --- Python oracle helpers ----------------------------------------------------
const PY = path.join(ROOT, ".venv/bin/python");

function pyPhone(raw) {
  const out = execFileSync(PY, ["-c",
    "import sys,json;from src.normalizer import normalize_phone;print(json.dumps(normalize_phone(json.loads(sys.argv[1]))))",
    JSON.stringify(raw)], { cwd: ROOT }).toString().trim();
  return JSON.parse(out);
}

// NM-6 oracle: one subprocess call runs the whole shared fixture table through
// src.taxonomy and returns all three normalizers' outputs per case.
function pyTaxonomy(fixtureRelPath) {
  const script = `
import json, sys
from src.taxonomy import normalize_org_type, normalize_org_type_result, normalize_content_types
with open(sys.argv[1]) as f:
    cases = json.load(f)
print(json.dumps({
    "org_type": [normalize_org_type(c) for c in cases["org_type_cases"]],
    "org_type_result": [normalize_org_type_result(c) for c in cases["org_type_cases"]],
    "content_types": [normalize_content_types(c) for c in cases["content_type_list_cases"]],
}))
`;
  const out = execFileSync(PY, ["-c", script, fixtureRelPath], { cwd: ROOT }).toString().trim();
  return JSON.parse(out);
}

// Phase 13 oracle: one subprocess call runs the whole shared research-cases fixture
// through src.taxonomy's validate_research_output/to_provider_result and returns, per
// case, the validate dict and the to_provider_result projected to a JSON-safe shape.
function pyResearch(fixtureRelPath) {
  const script = `
import json, sys
from src.taxonomy import validate_research_output, to_provider_result
with open(sys.argv[1]) as f:
    cases = json.load(f)["research_cases"]
def project(r):
    return {"provider": r.provider, "object_type": r.object_type, "matched": r.matched,
            "confidence": r.confidence, "data": r.data, "evidence_by_field": r.evidence_by_field}
print(json.dumps({
    "validate": [validate_research_output(c) for c in cases],
    "provider_result": [project(to_provider_result(c)) for c in cases],
}))
`;
  const out = execFileSync(PY, ["-c", script, fixtureRelPath], { cwd: ROOT }).toString().trim();
  return JSON.parse(out);
}

// Python identity oracle: build an hs_search stub from a propertyName-keyed canned
// dict (same shape as tests/test_identity.py make_search) and run resolve_identity.
function pyIdentity(row, cannedByProp) {
  const script = `
import sys, json
from src.identity import resolve_identity
row, canned = json.loads(sys.argv[1]), json.loads(sys.argv[2])
def hs_search(object_type, filters, properties, limit=100):
    prop = filters[0]["propertyName"]
    return canned.get(prop, {"results": [], "total": 0})
r = resolve_identity(row, hs_search=hs_search)
print(json.dumps({"outcome": r.outcome, "contact_id": r.contact_id,
                  "match_key": r.match_key, "candidate_ids": r.candidate_ids,
                  "reason": r.reason}))
`;
  const out = execFileSync(PY, ["-c", script, JSON.stringify(row), JSON.stringify(cannedByProp)],
    { cwd: ROOT }).toString().trim();
  return JSON.parse(out);
}

// Map a JS searchResultsByKey (match_key names) -> Python propertyName-keyed canned.
function toCanned(searchMap) {
  const propOf = { email: "email", linkedin_url: "linkedin_url",
                   phone_lastname: "phone", name_company: "firstname" };
  const canned = {};
  for (const [k, ids] of Object.entries(searchMap)) {
    canned[propOf[k]] = { results: ids.map((id) => ({ id })), total: ids.length };
  }
  return canned;
}

// --- normalizePhoneAU ---------------------------------------------------------
test("normalizePhoneAU: expected outcomes", () => {
  assert.equal(normalizePhoneAU("0412 345 678"), "+61412345678");
  assert.equal(normalizePhoneAU("+14155552671"), "+14155552671"); // kept as-is
  assert.equal(normalizePhoneAU("0468 12 12 12"), "+61468121212"); // AU mobile
  assert.equal(normalizePhoneAU("61412345678"), "+61412345678");
  assert.equal(normalizePhoneAU("(04) 1234 5678"), "+61412345678");
  assert.equal(normalizePhoneAU("garbage"), null);
  assert.equal(normalizePhoneAU(""), null);
  assert.equal(normalizePhoneAU(null), null);
});

test("normalizePhoneAU: GENUINE parity vs Python phonenumbers", () => {
  // Only rows where the AU heuristic and phonenumbers agree (per DISCLAIMER, the
  // heuristic diverges on invalid '+...' and non-AU nationals — those are excluded).
  for (const raw of ["0412 345 678", "+14155552671", "0468 12 12 12",
                     "61412345678", "(04) 1234 5678", "garbage", ""]) {
    assert.equal(normalizePhoneAU(raw), pyPhone(raw), `phone parity for ${JSON.stringify(raw)}`);
  }
});

// --- resolveIdentity ----------------------------------------------------------
const IDENTITY_CASES = [
  { name: "email single hit -> match",
    row: { email: "alice@example.com" }, search: { email: ["501"] },
    expect: { outcome: "match", contact_id: "501", match_key: "email" } },
  { name: "email multi hit -> ambiguous",
    row: { email: "alice@example.com" }, search: { email: ["501", "502"] },
    expect: { outcome: "ambiguous", contact_id: null, match_key: "email" } },
  { name: "email zero hits -> net_new",
    row: { email: "alice@example.com" }, search: {},
    expect: { outcome: "net_new", contact_id: null } },
  { name: "no-email linkedin single hit -> match",
    row: { linkedin_url: "https://LinkedIn.com/in/alice/" }, search: { linkedin_url: ["777"] },
    expect: { outcome: "match", contact_id: "777", match_key: "linkedin_url" } },
  { name: "no-email phone+lastname hit -> ambiguous (NOT match/net_new)",
    row: { phone: "0412 345 678", lastname: "Baker" }, search: { phone_lastname: ["900"] },
    expect: { outcome: "ambiguous", match_key: "phone_lastname", contact_id: null } },
  { name: "no-email no-hit -> ambiguous, NEVER net_new",
    row: { phone: "0412 345 678", lastname: "Baker" }, search: {},
    expect: { outcome: "ambiguous", reason: "no email, insufficient identity" } },
  { name: "invalid email -> treated as no-email -> ambiguous",
    row: { email: "not-an-email" }, search: {},
    expect: { outcome: "ambiguous", reason: "no email, insufficient identity" } },
];

test("resolveIdentity: expected outcomes + no-email-never-net_new hard rule", () => {
  for (const c of IDENTITY_CASES) {
    const r = resolveIdentity(c.row, c.search);
    for (const [k, v] of Object.entries(c.expect)) {
      assert.deepEqual(r[k], v, `${c.name}: ${k}`);
    }
    assert.notEqual(r.outcome, undefined);
    if (!c.row.email || normalizeEmailBasic(c.row.email) === null) {
      assert.notEqual(r.outcome, "net_new", `${c.name}: no valid email must never be net_new`);
    }
  }
});

test("resolveIdentity: GENUINE parity vs Python resolve_identity", () => {
  for (const c of IDENTITY_CASES) {
    const js = resolveIdentity(c.row, c.search);
    const py = pyIdentity(c.row, toCanned(c.search));
    assert.deepEqual(
      { outcome: js.outcome, contact_id: js.contact_id, match_key: js.match_key,
        candidate_ids: js.candidate_ids, reason: js.reason },
      py, `identity parity: ${c.name}`);
  }
});

// --- columnMap ----------------------------------------------------------------
test("columnMap: aliased/mixed-case headers -> canonical, unmapped dropped", () => {
  const row = mapRow({
    "  First Name ": "Alice", "SURNAME": "Baker", "E-Mail": "a@b.com",
    "Job Title": "Engineer", "LinkedIn URL": "https://li/x", "Mobile": "0412 345 678",
    "Account": "Example", "unmapped col": "drop me",
  });
  assert.deepEqual(row, {
    firstname: "Alice", lastname: "Baker", email: "a@b.com", jobtitle: "Engineer",
    linkedin_url: "https://li/x", phone: "0412 345 678", company: "Example",
  });
  assert.ok(!("unmapped col" in row));
});

test("columnMap: requiredIdentity — email OR firstname+lastname+company", () => {
  assert.equal(requiredIdentity({ email: "a@b.com" }), true);
  assert.equal(requiredIdentity({ firstname: "A", lastname: "B", company: "C" }), true);
  assert.equal(requiredIdentity({ firstname: "A", lastname: "B" }), false); // missing company
  assert.equal(requiredIdentity({ phone: "0412345678" }), false);           // no identity
  assert.equal(requiredIdentity({}), false);
});

// --- mergeContacts ------------------------------------------------------------
test("mergeContacts: email not canonical, blank phone filled, jobtitle conflict -> review", () => {
  const existing = { jobtitle: "Analyst", phone: "", email: "old@corp.com" };
  const candidate = { email: "new@corp.com", phone: "+61412345678", jobtitle: "Engineer" };
  const { canonicalPatch, provenance, decisions } = mergeContacts(existing, candidate);

  // email (manual_protected, min_conf 95 > csv 80) -> never canonical
  assert.ok(!("email" in canonicalPatch), "email must not be canonical");
  // blank phone (fill_blank_only, 80>=80) -> promote
  assert.equal(canonicalPatch.phone, "+61412345678");
  // present jobtitle (stale_refreshable) -> needs_review, not promoted
  assert.ok(!("jobtitle" in canonicalPatch));
  const jt = decisions.find((d) => d.field === "jobtitle");
  assert.equal(jt.decision, "needs_review");

  // Phase 15: every candidate field has ONE provenance entry (no flat staging/metadata
  // keys) — {source, confidence, verified_at, validation_status, value}.
  for (const f of ["email", "phone", "jobtitle"]) {
    assert.ok(provenance[f], `provenance entry for ${f}`);
    assert.equal(provenance[f].source, "csv");
    assert.equal(provenance[f].confidence, 80);
    assert.ok(provenance[f].verified_at, `${f} verified_at stamped`);
    assert.ok(provenance[f].validation_status, `${f} validation_status stamped`);
    assert.equal(provenance[f].value, candidate[f]);
  }
});

// --- mergeCompanies -----------------------------------------------------------
test("mergeCompanies: domain never canonical, ICP fields promote, present industry -> stage (unmappable label)", () => {
  const existing = { domain: "racingnsw.com.au", industry: "Sports", lv_org_type: "" };
  const candidate = {
    domain: "racingnsw.com.au",
    industry: "Sports & Entertainment",
    lv_org_type: "governing_body_league",
    lv_revenue_band: "50-500M",
  };
  const opts = { source: "zoominfo", confidence: 85,
                 evidence: { lv_org_type: "https://racingnsw.com.au/about" } };
  const { canonicalPatch, provenance, cacheKeys, decisions } =
    mergeCompanies(existing, candidate, undefined, opts);

  // domain (manual_protected, min_conf 95 > 85) -> never canonical
  assert.ok(!("domain" in canonicalPatch), "domain must not be canonical");
  // lv_org_type (system_owned, 85>=80) + evidence URL supplied -> promote
  assert.equal(canonicalPatch.lv_org_type, "governing_body_league");
  // lv_revenue_band (system_owned, 85>=75) -> promote
  assert.equal(canonicalPatch.lv_revenue_band, "50-500M");
  // present industry (stale_refreshable) would have gated to needs_review, but
  // "Sports & Entertainment" is not an exact case-insensitive match for any HubSpot
  // industry option (Phase 31, BUG 28's enum guard) — it is forced to stage_only instead,
  // never offered as an approvable review candidate.
  assert.ok(!("industry" in canonicalPatch));
  assert.equal(decisions.find((d) => d.field === "industry").decision, "stage_only");
  assert.equal(provenance.industry.validation_status, "rejected");

  // Phase 15: every candidate field has ONE provenance entry (no flat staging/metadata
  // keys) — {source, confidence, verified_at, validation_status, value}.
  for (const f of ["domain", "industry", "lv_org_type", "lv_revenue_band"]) {
    assert.ok(provenance[f], `provenance entry for ${f}`);
    assert.equal(provenance[f].source, "zoominfo");
    assert.equal(provenance[f].confidence, 85);
    assert.ok(provenance[f].verified_at, `${f} verified_at stamped`);
    assert.ok(provenance[f].validation_status, `${f} validation_status stamped`);
    assert.equal(provenance[f].value, candidate[f]);
  }
  assert.equal(provenance.lv_org_type.evidence_url, "https://racingnsw.com.au/about");

  // Cache key: lv_org_type's verified_at mirrors to the top-level queryable property;
  // lv_produces_content has no candidate this call, so its cache key is absent.
  assert.equal(cacheKeys.lv_org_type_verified_at, provenance.lv_org_type.verified_at);
  assert.ok(!("lv_produces_content_verified_at" in cacheKeys));
});

test("mergeCompanies: unevidenced ICP claims -> needs_review, never canonical", () => {
  const candidate = {
    lv_org_type: "hardware_vendor",  // in require_evidence_url_for -> gated
    lv_produces_content: true,       // require_evidence_url: true -> always gated
  };
  const { canonicalPatch, decisions } =
    mergeCompanies({}, candidate, undefined, { source: "apollo", confidence: 90 });

  for (const f of ["lv_org_type", "lv_produces_content"]) {
    assert.ok(!(f in canonicalPatch), `${f} must not promote without evidence`);
    const d = decisions.find((x) => x.field === f);
    assert.equal(d.decision, "needs_review");
    assert.equal(d.validation_status, "human_review_required");
    assert.equal(d.evidence_url, null);
  }
});

test("mergeCompanies: require_evidence_url_for gates only the listed values", () => {
  // "other" is NOT in lv_org_type.require_evidence_url_for -> promotes unevidenced
  const { canonicalPatch } =
    mergeCompanies({}, { lv_org_type: "other" }, undefined, { confidence: 90 });
  assert.equal(canonicalPatch.lv_org_type, "other");
});

// --- dedupeSweep --------------------------------------------------------------
test("dedupeSweep: cross-format phone dup collapses; garbage -> mangled", () => {
  const records = [
    { id: "1", properties: { phone: "0412 345 678" } },
    { id: "2", properties: { phone: "+61412345678" } },      // same E.164 as #1
    { id: "3", properties: { email: "dup@x.com" } },
    { id: "4", properties: { email: "DUP@X.com" } },          // same lowercased email
    { id: "5", properties: { email: "not-an-email", phone: "garbage" } }, // mangled x2
    { id: "6", properties: { phone: "" } },                   // blank -> ignored
  ];
  const r = dedupeSweep(records);

  const phoneDup = r.duplicates.find((d) => d.key_type === "phone");
  assert.ok(phoneDup, "phone duplicate group exists");
  assert.deepEqual(phoneDup.ids, ["1", "2"], "0412… and +61412… collapse to one group");
  assert.equal(phoneDup.key_value, "+61412345678");

  const emailDup = r.duplicates.find((d) => d.key_type === "email");
  assert.deepEqual(emailDup.ids, ["3", "4"]);

  const mangledIds = r.mangled.map((m) => m.id);
  assert.ok(mangledIds.includes("5"));
  assert.equal(r.mangled.filter((m) => m.id === "5").length, 2); // both email + phone

  assert.deepEqual(r.to_review_ids, ["1", "2", "3", "4", "5"]);
  assert.equal(r.counts.duplicates, r.duplicate_count);
  assert.ok(!r.to_review_ids.includes("6")); // blank phone is not a finding
});

// --- taxonomy: NM-6 Python/JS parity -------------------------------------------
test("taxonomy: NM-6 GENUINE parity vs Python src.taxonomy across the shared fixture", () => {
  const fixturePath = path.join(ROOT, "tests/fixtures/taxonomy_parity_cases.json");
  const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  const py = pyTaxonomy("tests/fixtures/taxonomy_parity_cases.json");

  const jsOrgType = fixture.org_type_cases.map((c) => normalizeOrgType(c));
  const jsOrgTypeResult = fixture.org_type_cases.map((c) => normalizeOrgTypeResult(c));
  const jsContentTypes = fixture.content_type_list_cases.map((c) => normalizeContentTypes(c));

  assert.deepStrictEqual(jsOrgType, py.org_type, "normalize_org_type parity");
  assert.deepStrictEqual(jsOrgTypeResult, py.org_type_result, "normalize_org_type_result parity");
  assert.deepStrictEqual(jsContentTypes, py.content_types, "normalize_content_types parity");
});

// --- webResearch: JS/Python parity (Phase 13) ----------------------------------
test("webResearch: GENUINE parity vs Python src.taxonomy validate_research_output/to_provider_result", () => {
  const fixturePath = path.join(ROOT, "tests/fixtures/research_validation_cases.json");
  const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  const cases = fixture.research_cases;
  const py = pyResearch("tests/fixtures/research_validation_cases.json");

  const jsValidate = cases.map((c) => validateResearchOutput(c));
  const jsProviderResult = cases.map((c) => {
    const r = toProviderResult(c);
    return { provider: r.provider, object_type: r.object_type, matched: r.matched,
             confidence: r.confidence, data: r.data, evidence_by_field: r.evidence_by_field };
  });

  assert.deepStrictEqual(jsValidate, py.validate, "validateResearchOutput parity");
  assert.deepStrictEqual(jsProviderResult, py.provider_result, "toProviderResult parity");
});

// --- judge: JG-4 GENUINE parity vs Python src.judge.is_citation_sufficient ----------
// Name carries "judge" + "parity" so --test-name-pattern="judge.*parity" targets it.
function pyJudgeSufficiency(fixtureRelPath) {
  const script = `
import json, sys
from src.judge import is_citation_sufficient
with open(sys.argv[1]) as f:
    cases = json.load(f)["evidence_cases"]
print(json.dumps([is_citation_sufficient(c["citation_url"], c["domain"]) for c in cases]))
`;
  const out = execFileSync(PY, ["-c", script, fixtureRelPath], { cwd: ROOT }).toString().trim();
  return JSON.parse(out);
}

test("judge: JG-4 GENUINE parity vs Python src.judge.is_citation_sufficient over the 20-row fixture", () => {
  const fixturePath = path.join(ROOT, "tests/fixtures/evidence_sufficiency_cases.json");
  const { evidence_cases: cases } = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  const py = pyJudgeSufficiency("tests/fixtures/evidence_sufficiency_cases.json");
  const js = cases.map((c) => isCitationSufficient(c.citation_url, c.domain));
  assert.deepStrictEqual(js, py, "isCitationSufficient parity (JS vs Python) over all 20 rows");
});

// --- provenance blob: Python json.dumps(sort_keys=True, separators=(",",":"),
// ensure_ascii=False) vs JS stableStringify MUST be byte-identical (Phase 15 Task 5).
function pySerializeProvenance(entries) {
  const script = `
import json, sys
from src.merge_policy import serialize_provenance
print(serialize_provenance(json.loads(sys.argv[1])))
`;
  const out = execFileSync(PY, ["-c", script, JSON.stringify(entries)], { cwd: ROOT }).toString();
  // print() adds exactly one trailing newline; serialize_provenance() itself returns none —
  // strip exactly one for a fair byte comparison.
  return out.replace(/\n$/, "");
}

const PROVENANCE_FIXTURE = {
  lv_org_type: { source: "zoominfo", confidence: 85, verified_at: "2026-07-22T00:00:00Z",
                 validation_status: "provider_only", value: "governing_body_league" },
  lv_produces_content: { source: "claude_web", confidence: 88, verified_at: "2026-07-22T00:00:00Z",
                          validation_status: "llm_classified", value: true,
                          evidence_url: ["https://example.org/watch-live"] },
  // Non-ASCII fixture row — RESEARCH.md/PLAN.md Task 5: ensure_ascii=False is
  // load-bearing, not cosmetic. A macron in a plausible AU/NZ club name/evidence string.
  lv_content_type: { source: "claude_web", confidence: 80, verified_at: "2026-07-22T00:00:00Z",
                      validation_status: "llm_classified",
                      value: "Ngā Puna Wai Sports Hub live_broadcast" },
};

test("provenance blob: Python and JS produce byte-identical serialization (incl. non-ASCII row)", () => {
  const js = stableStringify(PROVENANCE_FIXTURE);
  const py = pySerializeProvenance(PROVENANCE_FIXTURE);
  assert.equal(js, py, "provenance blob byte-parity (Python json.dumps vs JS stableStringify)");
  assert.ok(js.includes("Ngā"), "non-ASCII characters must survive unescaped in the JS serialization");
  assert.ok(py.includes("Ngā"), "non-ASCII characters must survive unescaped in the Python "
    + "serialization (ensure_ascii=False) — without this the byte-identical claim is unproven");
});

test("provenance blob DELIBERATE-BREAK 1: changing one candidate value changes the blob, Python==JS still holds", () => {
  const changed = JSON.parse(JSON.stringify(PROVENANCE_FIXTURE));
  changed.lv_org_type.value = "content_producer";  // deliberately different from the base fixture
  const jsBase = stableStringify(PROVENANCE_FIXTURE);
  const jsChanged = stableStringify(changed);
  assert.notEqual(jsChanged, jsBase, "changing a candidate value must change the serialized blob");
  const pyChanged = pySerializeProvenance(changed);
  assert.equal(jsChanged, pyChanged, "Python/JS parity must still hold after the value change");
});

test("provenance blob DELIBERATE-BREAK 2: dropping ensure_ascii=False breaks parity on the non-ASCII row", () => {
  // Simulates dropping `ensure_ascii=False` from src/merge_policy.py's
  // serialize_provenance() WITHOUT touching the real source file: Python's json.dumps
  // defaults to ensure_ascii=True, which \uXXXX-escapes every non-ASCII character;
  // JSON.stringify never does. This proves the flag is load-bearing, not cosmetic — see
  // the SUMMARY for the companion one-time proof performed directly against the source.
  const brokenScript = `
import json, sys
entries = json.loads(sys.argv[1])
print(json.dumps(entries, sort_keys=True, separators=(",", ":")))
`;
  const broken = execFileSync(PY, ["-c", brokenScript, JSON.stringify(PROVENANCE_FIXTURE)],
    { cwd: ROOT }).toString().replace(/\n$/, "");
  const js = stableStringify(PROVENANCE_FIXTURE);
  assert.notEqual(broken, js,
    "dropping ensure_ascii=False must break byte-parity on the non-ASCII row (lv_content_type) — "
    + "proves the flag is load-bearing, not cosmetic");
  assert.ok(broken.includes("\\u"), "the broken (ensure_ascii default True) variant must \\u-escape the macron");
  assert.ok(js.includes("Ngā"), "the correct JS serialization keeps the raw UTF-8 characters");
});

// --- 47.5-C: hardware-veto trigger, GENUINE oracle-vs-node parity ------------------
// The veto predicate lives in TWO engines (47.5-C-DECISION.md): src/icp_scoring.py and
// the `Decide Company Action` node built into n8n/wf_enrichment_cloud.json. Phase 46's
// parity rule says they move together; this table proves they are EQUAL rather than
// inspecting each separately. Run through Merge Company -> Decide Company Action with a
// matched:false research candidate, the same harness idiom
// decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs uses, so the `?? existing`
// fallback path is the one exercised — that is the lane a recompute actually takes.

function loadNodeJsCode(name) {
  const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n/wf_enrichment_cloud.json"), "utf8"));
  return wf.nodes.find((n) => n.name === name).parameters.jsCode;
}

function runCodeNode(jsCode, row) {
  const $input = { all: () => [{ json: row }], get item() { return { json: row }; } };
  const $ = () => ({ all: () => [], get item() { return { json: undefined }; } });
  const $now = new Date();
  const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
    `"use strict";\n${jsCode}`);
  const out = fn($, $input, row, {}, $now, $now) || [];
  return (out[0] && out[0].json) || {};
}

// (lv_is_hardware_vendor, lv_org_type, veto fires?) — mirrors tests/test_icp_scoring.py's
// HARDWARE_VETO_TABLE, including the explicit-false-plus-org-type edge (an explicit
// false boolean must NOT suppress the org-type trigger under OR) and both single-trigger
// paths, so neither half can rot. The third column is the ANTI-VACUITY column: without
// it, two engines that both dropped the veto would still "agree" and the parity
// assertions would pass on a broken rubric.
const HARDWARE_VETO_CASES = [
  [true, "hardware_vendor", true],
  [true, "broadcaster", true],
  [null, "hardware_vendor", true],
  [false, "hardware_vendor", true],
  [null, "broadcaster", false],
  [false, "broadcaster", false],
  [null, "unknown", false],
];

function pyVeto(cases) {
  const script = `
import json, sys
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score
out = []
for is_hw, org_type, _fires in json.loads(sys.argv[1]):
    patch = {"lv_org_type": org_type, "lv_produces_content": True,
             "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"}
    if is_hw is not None:
        patch["lv_is_hardware_vendor"] = is_hw
    r = compute_icp_score(HubSpotRecord(object_type="companies", id="789", properties={}), patch)
    out.append({"flag": "true" if r.anti_icp_flag else "false",
                "reason": r.anti_icp_reason or ""})
print(json.dumps(out))
`;
  const raw = execFileSync(PY, ["-c", script, JSON.stringify(cases)], { cwd: ROOT }).toString().trim();
  return JSON.parse(raw);
}

test("hardware veto: GENUINE parity between src/icp_scoring.py and the built " +
     "Decide Company Action node across the (boolean x org_type) table", () => {
  const MERGE_COMPANY = loadNodeJsCode("Merge Company");
  const DECIDE_COMPANY_ACTION = loadNodeJsCode("Decide Company Action");
  const expected = pyVeto(HARDWARE_VETO_CASES);
  const HARDWARE_REASON = "Hardware/AV/LED vendor, not sports-media buyer";

  HARDWARE_VETO_CASES.forEach(([isHw, orgType, fires], i) => {
    const row = {
      action: "enrich",
      identity_keys: { domain: null },
      existingRecord: {
        hs_object_id: "999",
        name: "ZZ-SCORING-TEST-DELETE-ME-fixture",
        lv_country_region_normalized: "AU",
        lv_produces_content: true,
        lv_org_type: orgType,
        ...(isHw === null ? {} : { lv_is_hardware_vendor: isHw }),
      },
      scored: { best: {}, winners: {}, sourcesByField: {} },
      research_candidate: { matched: false, confidence: 0, data: {}, evidence_by_field: {} },
    };
    const merged = runCodeNode(MERGE_COMPANY, row);
    const out = runCodeNode(DECIDE_COMPANY_ACTION, { ...row, merge: merged.merge });
    const label = `(lv_is_hardware_vendor=${isHw}, lv_org_type=${orgType})`;
    // Anti-vacuity: pin the expected outcome first, so a rubric that lost the veto in
    // BOTH engines fails here rather than passing as "agreement".
    assert.equal(expected[i].flag, fires ? "true" : "false",
      `${label}: the Python oracle's veto outcome is not the decided one`);
    assert.equal(expected[i].reason, fires ? HARDWARE_REASON : "",
      `${label}: the Python oracle's reason string is not the decided one`);
    assert.equal(out.properties.lv_anti_icp_flag, expected[i].flag,
      `${label}: node flag disagrees with the Python oracle`);
    assert.equal(out.properties.lv_anti_icp_reason, expected[i].reason,
      `${label}: node reason string disagrees with the Python oracle`);
  });
});

test("hardware veto: the reason string the node emits is byte-identical to the rubric YAML", () => {
  // Vacuity guard for the table above — if BOTH engines dropped the veto the parity
  // assertions would still pass. Pin the actual expected string independently.
  const DECIDE_COMPANY_ACTION = loadNodeJsCode("Decide Company Action");
  const yamlReason = fs.readFileSync(path.join(ROOT, "config/icp_scoring.yaml"), "utf8")
    .match(/hardware_vendor:\s*\n\s*enabled:.*\n\s*reason:\s*"([^"]+)"/)[1];
  assert.equal(yamlReason, "Hardware/AV/LED vendor, not sports-media buyer");
  assert.ok(DECIDE_COMPANY_ACTION.includes(yamlReason),
    "the built node must carry the rubric's reason string verbatim");
});
