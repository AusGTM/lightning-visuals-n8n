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
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const { normalizePhoneAU } = require(path.join(ROOT, "n8n/code/normalizePhone.js"));
const { normalizeEmailBasic } = require(path.join(ROOT, "n8n/code/normalizeEmail.js"));
const { mapRow, requiredIdentity } = require(path.join(ROOT, "n8n/code/columnMap.js"));
const { resolveIdentity } = require(path.join(ROOT, "n8n/code/resolveIdentity.js"));
const { mergeContacts } = require(path.join(ROOT, "n8n/code/mergeContacts.js"));
const { mergeCompanies } = require(path.join(ROOT, "n8n/code/mergeCompanies.js"));
const { dedupeSweep } = require(path.join(ROOT, "n8n/code/dedupeSweep.js"));

// --- Python oracle helpers ----------------------------------------------------
const PY = path.join(ROOT, ".venv/bin/python");

function pyPhone(raw) {
  const out = execFileSync(PY, ["-c",
    "import sys,json;from src.normalizer import normalize_phone;print(json.dumps(normalize_phone(json.loads(sys.argv[1]))))",
    JSON.stringify(raw)], { cwd: ROOT }).toString().trim();
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
  const { canonicalPatch, stagingPatch, metadataPatch, decisions } = mergeContacts(existing, candidate);

  // email (manual_protected, min_conf 95 > csv 80) -> never canonical
  assert.ok(!("email" in canonicalPatch), "email must not be canonical");
  // blank phone (fill_blank_only, 80>=80) -> promote
  assert.equal(canonicalPatch.phone, "+61412345678");
  // present jobtitle (stale_refreshable) -> needs_review, not promoted
  assert.ok(!("jobtitle" in canonicalPatch));
  const jt = decisions.find((d) => d.field === "jobtitle");
  assert.equal(jt.decision, "needs_review");

  // every candidate field is staged and carries source metadata
  for (const f of ["email", "phone", "jobtitle"]) {
    assert.ok((`csv_${f}`) in stagingPatch, `staged csv_${f}`);
    assert.equal(metadataPatch[`${f}_source`], "csv");
    assert.equal(metadataPatch[`${f}_confidence`], 80);
    assert.ok(metadataPatch[`${f}_verified_at`], `${f} verified_at stamped`);
    assert.ok(metadataPatch[`${f}_validation_status`], `${f} validation_status stamped`);
  }
});

// --- mergeCompanies -----------------------------------------------------------
test("mergeCompanies: domain never canonical, ICP fields promote, present industry -> review", () => {
  const existing = { domain: "racingnsw.com.au", industry: "Sports", lv_org_type: "" };
  const candidate = {
    domain: "racingnsw.com.au",
    industry: "Sports & Entertainment",
    lv_org_type: "governing_body_league",
    lv_revenue_band: "50-500M",
  };
  const opts = { source: "zoominfo", confidence: 85,
                 evidence: { lv_org_type: "https://racingnsw.com.au/about" } };
  const { canonicalPatch, stagingPatch, metadataPatch, decisions } =
    mergeCompanies(existing, candidate, undefined, opts);

  // domain (manual_protected, min_conf 95 > 85) -> never canonical
  assert.ok(!("domain" in canonicalPatch), "domain must not be canonical");
  // lv_org_type (system_owned, 85>=80) + evidence URL supplied -> promote
  assert.equal(canonicalPatch.lv_org_type, "governing_body_league");
  // lv_revenue_band (system_owned, 85>=75) -> promote
  assert.equal(canonicalPatch.lv_revenue_band, "50-500M");
  // present industry (stale_refreshable) -> needs_review, not promoted
  assert.ok(!("industry" in canonicalPatch));
  assert.equal(decisions.find((d) => d.field === "industry").decision, "needs_review");

  // every candidate field is staged and carries source metadata
  for (const f of ["domain", "industry", "lv_org_type", "lv_revenue_band"]) {
    assert.ok((`zoominfo_${f}`) in stagingPatch, `staged zoominfo_${f}`);
    assert.equal(metadataPatch[`${f}_source`], "zoominfo");
    assert.equal(metadataPatch[`${f}_confidence`], 85);
    assert.ok(metadataPatch[`${f}_verified_at`], `${f} verified_at stamped`);
    assert.ok(metadataPatch[`${f}_validation_status`], `${f} validation_status stamped`);
  }
  assert.equal(metadataPatch.lv_org_type_evidence_url, "https://racingnsw.com.au/about");
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
