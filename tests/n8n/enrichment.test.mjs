// tests/n8n/enrichment.test.mjs
//
// Wave A — scoring + staleness + provider-normalization engine.
// Run: node --test tests/n8n/enrichment.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const { toCandidates, lushaRecordId } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));
const { scoreCandidates } = require(path.join(ROOT, "n8n/code/scoreEnrichment.js"));
const { decideAction } = require(path.join(ROOT, "n8n/code/enrichmentGate.js"));
const { normalizePhone } = require(path.join(ROOT, "n8n/code/normalizePhone.js"));

const FIX = path.join(ROOT, "tests/fixtures/enrichment");
const load = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name), "utf8"));
const NOW = "2026-07-14T00:00:00Z";

const apolloC = load("apollo_contact.json");
const zoomC = load("zoominfo_contact.json");
const apolloCo = load("apollo_company.json");
const zoomCo = load("zoominfo_company.json");
const apolloLive = load("apollo_live_match.json"); // real people/match: nested under `person`
const zoomLive = load("zoominfo_live_enrich.json"); // real GTM enrich: data[].attributes + meta.matchStatus
// Lusha v3 is the live contract as of 2026-07-30 (docs/LUSHA-V3-CONTRACT.md) -- the v2
// `{contacts:{...}}`/`{contact:{data:{...}}}` envelopes these fixtures replaced were
// retired in Plan 03 Task 3 (v2 sunsets 2026-11-18; every emission site now targets v3).
const lushaV3Contact = load("lusha_v3_contact.json"); // v3 contacts: results[] flat envelope
const lushaV3Company = load("lusha_v3_company.json"); // v3 companies: results[] flat envelope
const lushaV3NoMatch = load("lusha_v3_no_match.json"); // v3 no-match: results[0].error, outer 200
// Plan 04 Task 2b: the CONFIRMED-FREE stored-id path's OWN envelope (POST
// /v3/contacts/enrich), captured live 2026-07-30 (docs/LUSHA-V3-CONTRACT.md §8.1) —
// structurally identical result-item shape to the search-and-enrich fixture above, but
// `phones` is genuinely ABSENT (not `phones: []`) since `reveal` only asked for emails.
const lushaV3ContactEnrichById = load("lusha_v3_contact_enrich_by_id.json");

function find(cands, field, source) {
  return cands.find((c) => c.field === field && c.source === source);
}

// --- toCandidates: real fields -> common shape + correct accuracy --------------
test("toCandidates: Apollo verified email -> accuracy 1.0", () => {
  const c = toCandidates("apollo", apolloC, "contacts");
  const email = find(c, "email", "apollo");
  assert.equal(email.accuracy, 1.0);
  assert.equal(email.normalizedValue, "jamie.rivera@exampleracing.example");
  assert.equal(email.recencyDate, "2026-06-20");
});

test("toCandidates: Apollo bounced -> 0; catchall verified -> 0.6", () => {
  const bounced = toCandidates("apollo", { email: "x@y.com", email_status: "bounced" }, "contacts");
  assert.equal(find(bounced, "email", "apollo").accuracy, 0);
  const catchall = toCandidates("apollo",
    { email: "x@y.com", email_status: "verified", email_domain_catchall: true }, "contacts");
  assert.equal(find(catchall, "email", "apollo").accuracy, 0.6);
  const guessed = toCandidates("apollo",
    { email: "x@y.com", email_status: "guessed", extrapolated_email_confidence: 0.8 }, "contacts");
  assert.equal(Math.round(find(guessed, "email", "apollo").accuracy * 100), 40); // 0.5*0.8
});

test("toCandidates: Apollo live people/match (nested `person`) maps contact + company fields", () => {
  const contacts = toCandidates("apollo", apolloLive, "contacts");
  const email = find(contacts, "email", "apollo");
  assert.ok(email, "email candidate present from nested person");
  assert.equal(email.accuracy, 1.0); // verified
  assert.equal(email.normalizedValue, "gillon.mclachlan@tabcorp.com.au");
  assert.equal(find(contacts, "jobtitle", "apollo").normalizedValue, "chief executive officer");
  assert.equal(find(contacts, "mobilephone", "apollo").normalizedValue, "+61400000001");

  const co = toCandidates("apollo", apolloLive, "companies");
  // organization_revenue 1.7B -> 1.2B+ band; not annual_revenue (absent in live shape)
  assert.equal(find(co, "lv_revenue_band", "apollo").normalizedValue, "1.2B+");
  assert.equal(find(co, "lv_employee_band", "apollo").normalizedValue, "1001+");
  assert.equal(find(co, "industry", "apollo").normalizedValue, "entertainment");
});

test("normalizePhone: region-aware (keyed off provider country)", () => {
  // Known region -> correct calling code; national trunk/leading-1 handled.
  assert.equal(normalizePhone("(475) 450-4590", "US"), "+14754504590");
  assert.equal(normalizePhone("0412 345 678", "AU"), "+61412345678");
  assert.equal(normalizePhone("020 7946 0018", "GB"), "+442079460018");
  assert.equal(normalizePhone("021 123 4567", "NZ"), "+64211234567");
  // Country name (Apollo-style) resolves via ISO2 too (US already carries a 1).
  assert.equal(normalizePhone("1 (203) 260-8401", "US"), "+12032608401");
  // E.164 passthrough regardless of region.
  assert.equal(normalizePhone("+12032608401", "AU"), "+12032608401");
  // Unknown/absent region -> AU heuristic; non-AU national -> null (caller drops it).
  assert.equal(normalizePhone("(475) 450-4590", null), null);
  assert.equal(normalizePhone("0412 345 678", null), "+61412345678");
  // Length sanity gate rejects garbage.
  assert.equal(normalizePhone("12345", "US"), null);
});

// --- toCandidates: v3 envelope (results[] flat array, confirmed live 2026-07-30) --------
// v2's plural contactId-keyed `{contacts:{...}}` map and singular `{contact:{data:{...}}}`
// envelope tests (and the fixtures/behaviours they pinned: contact.data unwrap, live email/
// mobile/jobtitle/company extraction, per-contact error skip, missing-data skip, empty-map
// skip) were retired in Plan 03 Task 3 -- every behaviour they protected has a v3-driven
// equivalent below (email extraction, per-email confidence grading, mobile-vs-landline
// routing, do-not-call suppression, un-normalizable-phone dropping, job title/seniority/
// department extraction, revenue/headcount band normalization, industry classification,
// country normalization, per-record error handling).
const byField = (arr) => [...arr].sort((a, b) => a.field.localeCompare(b.field));

test("toCandidates: v3 US contact -> +1 E.164 via location.countryIso2; region-less non-AU dropped", () => {
  const usContact = { results: [{
    location: { countryIso2: "US" },
    phones: [{ number: "(475) 450-4590", type: "mobile", doNotCall: false }],
    updateDate: "2026-06-01",
  }] };
  const mob = find(toCandidates("lusha", usContact, "contacts"), "mobilephone", "lusha");
  assert.ok(mob, "US number parsed with location.countryIso2=US");
  assert.equal(mob.normalizedValue, "+14754504590");
  // Same US number but NO country signal -> AU heuristic returns null -> null-drop (no candidate).
  const noGeo = { results: [{
    phones: [{ number: "(475) 450-4590", type: "mobile", doNotCall: false }],
  }] };
  assert.equal(toCandidates("lusha", noGeo, "contacts").filter((c) => c.field === "mobilephone").length, 0);
});

test("toCandidates: v3 contacts field set is exactly the v2 contacts field set", () => {
  const c = toCandidates("lusha", lushaV3Contact, "contacts");
  const fields = [...new Set(c.map((x) => x.field))].sort();
  assert.deepEqual(fields, ["email", "jobtitle", "mobilephone", "persona_group", "phone", "seniority"]);
});

test("toCandidates: v3 A+ email confidence grades to accuracy 1.0; job title/seniority/department extracted", () => {
  const c = toCandidates("lusha", lushaV3Contact, "contacts");
  assert.equal(find(c, "email", "lusha").accuracy, 1.0); // A+ work
  assert.equal(find(c, "jobtitle", "lusha").normalizedValue, "head of broadcast");
  assert.equal(find(c, "seniority", "lusha").normalizedValue, "director");
  assert.equal(find(c, "persona_group", "lusha").normalizedValue, "broadcast");
});

test("toCandidates: v3 mobile-discriminated phone -> mobilephone/0.8, other -> phone/0.8", () => {
  const c = toCandidates("lusha", lushaV3Contact, "contacts");
  const mob = find(c, "mobilephone", "lusha");
  assert.equal(mob.accuracy, 0.8);
  assert.equal(mob.normalizedValue, "+61412345678");
  assert.equal(find(c, "phone", "lusha").normalizedValue, "+61290001234");
});

test("toCandidates: v3 do-not-call phone produces no candidate", () => {
  const c = toCandidates("lusha", lushaV3Contact, "contacts");
  // Only one mobilephone and one phone candidate exist -- the doNotCall mobile entry
  // (0400 000 999) must not have produced a second mobilephone candidate.
  assert.equal(c.filter((x) => x.field === "mobilephone").length, 1);
  assert.notEqual(find(c, "mobilephone", "lusha").value, "0400 000 999");
});

test("toCandidates: v3 un-normalizable phone produces no candidate", () => {
  const c = toCandidates("lusha", lushaV3Contact, "contacts");
  assert.equal(c.filter((x) => x.value === "123").length, 0);
});

test("toCandidates: v3 companies field set is exactly lv_revenue_band/lv_employee_band/industry/lv_country_region_normalized", () => {
  const c = toCandidates("lusha", lushaV3Company, "companies");
  const fields = [...new Set(c.map((x) => x.field))].sort();
  assert.deepEqual(fields, ["industry", "lv_country_region_normalized", "lv_employee_band", "lv_revenue_band"]);
  assert.equal(find(c, "lv_revenue_band", "lusha").normalizedValue, "5-50M");
  assert.equal(find(c, "lv_employee_band", "lusha").normalizedValue, "51-200");
  assert.equal(find(c, "industry", "lusha").normalizedValue, "entertainment");
  assert.equal(find(c, "lv_country_region_normalized", "lusha").normalizedValue, "AU");
});

// The v2 plural/singular envelope wrappers no longer exist (retired, Plan 20-03 Task 3), so
// "the v2 candidate set" for equivalent input is now proven against the bare/flat shape --
// the pre-envelope intermediate object BOTH v2's unwrap and v3's adapter fed into the SAME
// unchanged extraction logic below. Deep-equality here is exactly the "downstream is
// untouched" guarantee: same values in, byte-identical candidates out, regardless of envelope.
test("toCandidates: v3 contacts candidate set deep-equals the flat pre-envelope shape for the same underlying data", () => {
  const shared = {
    emails: [{ email: "same@example.com", type: "work", confidence: "A+", updateDate: "2026-05-01" }],
    phones: [{ number: "0412 345 678", type: "mobile", doNotCall: false, updateDate: "2026-04-15" }],
    jobTitle: { title: "Head of Broadcast", seniority: "Director", departments: ["Broadcast"] },
    updateDate: "2026-05-01",
  };
  const flatRaw = { ...shared, location: { country_iso2: "AU" } };
  const v3Raw = { requestId: "x", results: [{ ...shared, location: { country: "Australia", countryIso2: "AU" } }],
    billing: { creditsCharged: 1, resultsReturned: 1 } };
  assert.deepEqual(
    byField(toCandidates("lusha", v3Raw, "contacts")),
    byField(toCandidates("lusha", flatRaw, "contacts")));
});

test("toCandidates: v3 companies candidate set deep-equals the flat pre-envelope shape for the same underlying data", () => {
  const flatRaw = { revenueRange: [10000000, 50000000], employeeCount: 191,
    mainIndustry: "Entertainment", location: { countryIso2: "AU" } };
  const v3Raw = { requestId: "x", results: [{
    revenueRange: { min: 10000000, max: 50000000 }, employeeCount: { exact: 191, min: 51, max: 200 },
    industry: "Entertainment", location: { countryIso2: "AU" } }],
    billing: { creditsCharged: 2, resultsReturned: 1 } };
  assert.deepEqual(
    byField(toCandidates("lusha", v3Raw, "companies")),
    byField(toCandidates("lusha", flatRaw, "companies")));
});

test("toCandidates: v3 no-match envelope -> zero candidates, never throw", () => {
  assert.doesNotThrow(() => toCandidates("lusha", lushaV3NoMatch, "contacts"));
  assert.deepEqual(toCandidates("lusha", lushaV3NoMatch, "contacts"), []);
});

test("toCandidates: v3 per-record error marker -> zero candidates, never throw", () => {
  const raw = { requestId: "x", results: [{ error: { code: "NOT_FOUND", message: "Contact not found" } }],
    billing: { creditsCharged: 0, resultsReturned: 0 } };
  assert.doesNotThrow(() => toCandidates("lusha", raw, "contacts"));
  assert.deepEqual(toCandidates("lusha", raw, "contacts"), []);
});

test("toCandidates: v3 missing record object, {}, and null -> zero candidates, never throw", () => {
  const missingRecord = { requestId: "x", results: [], billing: { creditsCharged: 0, resultsReturned: 0 } };
  assert.doesNotThrow(() => toCandidates("lusha", missingRecord, "contacts"));
  assert.deepEqual(toCandidates("lusha", missingRecord, "contacts"), []);
  assert.doesNotThrow(() => toCandidates("lusha", {}, "contacts"));
  assert.deepEqual(toCandidates("lusha", {}, "contacts"), []);
  assert.doesNotThrow(() => toCandidates("lusha", null, "contacts"));
  assert.deepEqual(toCandidates("lusha", null, "contacts"), []);
});

// --- lushaRecordId: Plan 04 (REQ-lusha-id-staging) extraction, sibling of toCandidates ---

test("lushaRecordId: v3 contact fixture returns results[0].id", () => {
  assert.equal(lushaRecordId(lushaV3Contact, "contacts"), "v1.SYNTHETIC_CONTACT_ID_0001");
});

test("lushaRecordId: v3 company fixture returns results[0].id", () => {
  assert.equal(lushaRecordId(lushaV3Company, "companies"), "v1.SYNTHETIC_COMPANY_ID_0002");
});

test("lushaRecordId: no-match fixture returns null", () => {
  assert.equal(lushaRecordId(lushaV3NoMatch, "contacts"), null);
});

test("lushaRecordId: a per-record error marker returns null", () => {
  const raw = { requestId: "x", results: [{ error: { code: "NOT_FOUND", message: "Contact not found" } }],
    billing: { creditsCharged: 0, resultsReturned: 0 } };
  assert.equal(lushaRecordId(raw, "contacts"), null);
});

test("lushaRecordId: {} and null never throw and return null", () => {
  assert.doesNotThrow(() => lushaRecordId({}, "contacts"));
  assert.equal(lushaRecordId({}, "contacts"), null);
  assert.doesNotThrow(() => lushaRecordId(null, "contacts"));
  assert.equal(lushaRecordId(null, "contacts"), null);
});

test("lushaRecordId: an id-less bare record (no id field) returns null, never throws", () => {
  assert.doesNotThrow(() => lushaRecordId({ emails: [] }, "contacts"));
  assert.equal(lushaRecordId({ emails: [] }, "contacts"), null);
});

test("toCandidates: the /contacts/enrich (stored-id reuse) envelope parses through the SAME adapter, no code change needed", () => {
  // §8.1: phones absent (not []) when reveal didn't ask for it — the existing
  // raw.phoneNumbers || raw.phones || [] fallback already tolerates an absent key.
  const c = toCandidates("lusha", lushaV3ContactEnrichById, "contacts");
  const fields = [...new Set(c.map((x) => x.field))].sort();
  assert.deepEqual(fields, ["email", "jobtitle", "seniority"]);
  assert.equal(find(c, "email", "lusha").normalizedValue, "redacted-synthetic@example-corp.com.au");
});

test("lushaRecordId: the /contacts/enrich (stored-id reuse) envelope also yields results[0].id", () => {
  assert.equal(lushaRecordId(lushaV3ContactEnrichById, "contacts"), "v1.SYNTHETIC_CONTACT_ID_0001");
});

test("toCandidates: lushaCandidates()'s field set is unchanged by the presence of lushaRecordId", () => {
  // Guards REQ-lusha-v3-normalize's field-identical candidate stream: the id must never
  // leak into the candidate stream as a new field, even though it is now extractable.
  const contactFields = new Set(toCandidates("lusha", lushaV3Contact, "contacts").map((c) => c.field));
  assert.deepEqual([...contactFields].sort(),
    ["email", "jobtitle", "mobilephone", "persona_group", "phone", "seniority"]);
  assert.ok(!contactFields.has("id"), "id must never appear as a candidate field");
  assert.ok(!contactFields.has("lusha_contact_id"), "lusha_contact_id must never appear as a candidate field");

  const companyFields = new Set(toCandidates("lusha", lushaV3Company, "companies").map((c) => c.field));
  assert.deepEqual([...companyFields].sort(),
    ["industry", "lv_country_region_normalized", "lv_employee_band", "lv_revenue_band"]);
  assert.ok(!companyFields.has("id"), "id must never appear as a candidate field");
  assert.ok(!companyFields.has("lusha_company_id"), "lusha_company_id must never appear as a candidate field");
});

test("toCandidates: ZoomInfo live GTM enrich (data[].attributes + meta.matchStatus)", () => {
  const c = toCandidates("zoominfo", zoomLive, "contacts");
  const title = find(c, "jobtitle", "zoominfo");
  assert.ok(title, "jobtitle from attributes");
  assert.equal(title.normalizedValue, "general manager, av broadcast");
  assert.equal(title.accuracy, 0.91); // contactAccuracyScore "91.0" (string) -> 0.91
  // managementLevel is an array ["Director"] -> first element
  assert.equal(find(c, "seniority", "zoominfo").normalizedValue, "director");
  // matchStatus lives in meta; FULL_MATCH must NOT drop fields
  assert.ok(c.length >= 2);
});

test("toCandidates: ZoomInfo legacy/flat envelopes still unwrap (back-compat)", () => {
  const enveloped = { data: { result: [{ data: [zoomC] }] } };
  assert.equal(find(toCandidates("zoominfo", enveloped, "contacts"), "email", "zoominfo").accuracy, 0.95);
  assert.ok(find(toCandidates("zoominfo", { data: [zoomC] }, "contacts"), "email", "zoominfo"));
});

test("toCandidates: ZoomInfo uses contactAccuracyScore; non-FULL_MATCH drops person fields", () => {
  const c = toCandidates("zoominfo", zoomC, "contacts");
  assert.equal(find(c, "email", "zoominfo").accuracy, 0.95); // 95/100
  assert.equal(find(c, "jobtitle", "zoominfo").accuracy, 0.95);
  assert.equal(find(c, "mobilephone", "zoominfo").accuracy, 0.8); // structural
  const partial = toCandidates("zoominfo",
    { email: "z@x.com", matchStatus: "PARTIAL", contactAccuracyScore: 99 }, "contacts");
  assert.equal(partial.length, 0);
});

// --- scoreCandidates: right winner per field -----------------------------------
function allContactCandidates() {
  return [
    ...toCandidates("lusha", lushaV3Contact, "contacts"),
    ...toCandidates("apollo", apolloC, "contacts"),
    ...toCandidates("zoominfo", zoomC, "contacts"),
  ];
}

test("score email: high-accuracy consensus source wins over lone high-accuracyScore", () => {
  const { best } = scoreCandidates(allContactCandidates(), { now: NOW });
  const email = best.email;
  // jamie.rivera (Apollo verified + Lusha A+, they agree) beats ZoomInfo's lone j.rivera
  assert.equal(email.normalizedValue, "jamie.rivera@exampleracing.example");
  assert.ok(["apollo", "lusha"].includes(email.source), `winner source ${email.source}`);
  assert.ok(email.agreedBy.length >= 1, "email winner has a consensus partner");
  assert.notEqual(email.source, "zoominfo");
});

test("score phone: cross-format E.164 agreement boosts and wins", () => {
  const { best } = scoreCandidates(allContactCandidates(), { now: NOW });
  const mob = best.mobilephone;
  // "0412 345 678" (Lusha) ≡ "+61412345678" (Apollo) ≡ "+61 412 345 678" (ZoomInfo)
  assert.equal(mob.normalizedValue, "+61412345678");
  assert.equal(mob.agreedBy.length, 2, "all three sources agree -> 2 others");
  assert.equal(mob.source, "apollo"); // valid_number A=1.0 tops the consensus
});

test("score: fresh source beats stale when accuracy ties", () => {
  const cands = [
    { field: "phone", source: "apollo", value: "fresh", normalizedValue: "+61400000001", accuracy: 0.8, recencyDate: "2026-07-10" },
    { field: "phone", source: "lusha", value: "stale", normalizedValue: "+61400000002", accuracy: 0.8, recencyDate: "2025-01-01" },
  ];
  const { best } = scoreCandidates(cands, { now: NOW });
  assert.equal(best.phone.source, "apollo"); // fresher R wins despite Lusha's higher trust
  assert.equal(best.phone.value, "fresh");
});

test("score: candidate with no recencyDate gets neutral R=0.5", () => {
  const { best } = scoreCandidates(
    [{ field: "phone", source: "apollo", value: "x", normalizedValue: "+61400000000", accuracy: 1, recencyDate: null }],
    { now: NOW });
  assert.equal(best.phone.components.R, 0.5);
});

// --- company scoring: revenue disagreement resolved by consensus; NAICS agree ---
function allCompanyCandidates() {
  return [
    ...toCandidates("lusha", lushaV3Company, "companies"),
    ...toCandidates("apollo", apolloCo, "companies"),
    ...toCandidates("zoominfo", zoomCo, "companies"),
  ];
}

test("score revenue: Apollo+Lusha band consensus beats lone ZoomInfo band", () => {
  const { best } = scoreCandidates(allCompanyCandidates(), { now: NOW });
  const rev = best.lv_revenue_band;
  assert.equal(rev.normalizedValue, "5-50M"); // 12M (Apollo) & 10M-50M (Lusha v3) agree; ZoomInfo 65M -> 50-500M loses
  assert.ok(rev.agreedBy.includes("lusha") || rev.agreedBy.includes("apollo"));
  assert.notEqual(rev.normalizedValue, "50-500M");
});

// NORM-01 (2026-07-29): this test previously pinned the bare NAICS code "711211" as the
// winning industry value, with Lusha and ZoomInfo "agreeing" on that code. NORM-01
// deliberately retired code-as-agreement-key behavior (D-NORM-lusha). Plan 20-03 (v3
// migration) then gave Lusha its own flat `industry` field ("Entertainment"), a THIRD,
// genuinely distinct value that still loses to the real cross-provider consensus below:
// Apollo ("Spectator Sports") and ZoomInfo (naicsCodes bare string falls back to its own
// primaryIndustry text, "Spectator Sports") agree on TEXT, so their consensus still wins
// over Lusha's lone "Entertainment" value.
test("score industry: Apollo+ZoomInfo agree on text; ZoomInfo wins on fresher recency", () => {
  const { best } = scoreCandidates(allCompanyCandidates(), { now: NOW });
  const ind = best.industry;
  assert.equal(ind.normalizedValue, "spectator sports");
  assert.equal(ind.source, "zoominfo"); // fresher recency date (validDate) on the flat fixtures
  assert.ok(ind.agreedBy.includes("apollo"));
});

test("scoreCandidates: winners map is flat and merge-ready", () => {
  const { winners } = scoreCandidates(allContactCandidates(), { now: NOW });
  assert.equal(typeof winners.email, "string");
  assert.equal(typeof winners.mobilephone, "string");
});

// --- enrichmentGate: create / enrich / skip ------------------------------------
const POLICY = { jobtitle: { stale_after_days: 180 }, numberofemployees: { stale_after_days: 180 } };

test("gate: null record -> create", () => {
  assert.equal(decideAction(null, ["email"], POLICY, NOW).action, "create");
  assert.equal(decideAction({}, ["email"], POLICY, NOW).action, "create");
});

test("gate: verified_at past TTL -> enrich(stale)", () => {
  // Phase 15: staleness reads the REAL cache-key property (lv_<field>_verified_at), never
  // a bare `<field>_verified_at` — this fixture uses the cache-key name so the TTL/age
  // arithmetic branch is actually exercised (a stale bare-named key would ALSO read as
  // stale via the "no verified_at" branch, silently testing the wrong code path).
  const r = decideAction(
    { jobtitle: "Analyst", lv_jobtitle_verified_at: "2025-01-01T00:00:00Z" },
    ["jobtitle"], POLICY, NOW);
  assert.equal(r.action, "enrich");
  assert.deepEqual(r.staleFields, ["jobtitle"]);
});

test("gate: fresh + complete + valid -> skip", () => {
  const r = decideAction(
    { email: "a@b.com", jobtitle: "Analyst", lv_jobtitle_verified_at: "2026-07-01T00:00:00Z" },
    ["email", "jobtitle"], POLICY, NOW);
  assert.equal(r.action, "skip");
});

test("gate: blank required field -> enrich(missing)", () => {
  const r = decideAction({ email: "a@b.com", jobtitle: "" }, ["email", "jobtitle"], POLICY, NOW);
  assert.equal(r.action, "enrich");
  assert.deepEqual(r.missingFields, ["jobtitle"]);
});

test("gate: invalid email -> enrich(invalid); invalid phone (not E.164) -> enrich(invalid)", () => {
  const bad = decideAction({ email: "not-an-email" }, ["email"], POLICY, NOW);
  assert.equal(bad.action, "enrich");
  assert.deepEqual(bad.invalidFields, ["email"]);
  const badPhone = decideAction({ phone: "12345" }, ["phone"], POLICY, NOW);
  assert.deepEqual(badPhone.invalidFields, ["phone"]);
});

test("gate: present staleable field with no verified_at is treated as stale", () => {
  const r = decideAction({ jobtitle: "Analyst" }, ["jobtitle"], POLICY, NOW);
  assert.equal(r.action, "enrich");
  assert.deepEqual(r.staleFields, ["jobtitle"]);
});

// --- companies branch: live-shape normalization (probed 2026-07-20) -----------
const zoomLiveCo = load("zoominfo_live_company.json"); // real GTM companies/enrich

test("toCandidates: ZoomInfo company revenue is THOUSANDS, not dollars", () => {
  // Racing NSW: revenue 268163 (thousands) == $268m, revenueRange "$250 mil. - $500 mil.".
  // Reading the raw number as dollars banded it "<1M" — a 1000x error.
  const c = toCandidates("zoominfo", zoomLiveCo, "companies");
  assert.equal(find(c, "lv_revenue_band", "zoominfo").normalizedValue, "50-500M");
});

test("toCandidates: ZoomInfo revenue falls back to revenue*1000 with no revenueRange", () => {
  const mk = (attrs) => ({ data: [{ id: "1", type: "Company", attributes: attrs,
                                    meta: { matchStatus: "FULL_MATCH" } }] });
  const c = toCandidates("zoominfo", mk({ name: "X", revenue: 268163 }), "companies");
  assert.equal(find(c, "lv_revenue_band", "zoominfo").normalizedValue, "50-500M");

  // FanDuel: 14050000 thousands == $14.05b -> top band (was "5-50M" before the fix).
  const fd = toCandidates("zoominfo", mk({ name: "FanDuel", revenue: 14050000,
                                           country: "United States" }), "companies");
  assert.equal(find(fd, "lv_revenue_band", "zoominfo").normalizedValue, "1.2B+");
  // non-ANZ -> hard veto input
  assert.equal(find(fd, "lv_country_region_normalized", "zoominfo").normalizedValue, "Other");
});

test("toCandidates: ZoomInfo live naicsCodes are objects, not code strings", () => {
  // String({id,name}) would have staged "[object Object]" as the industry.
  // NORM-01 (2026-07-29): this test previously pinned "71" (the bare NAICS sector code) as
  // the expected normalizedValue. The fix reads the NAICS entry's own human-readable `.name`
  // instead of its numeric `.id`, so the expected value changes from the code to the name.
  const c = toCandidates("zoominfo", zoomLiveCo, "companies");
  assert.equal(find(c, "industry", "zoominfo").normalizedValue, "arts, entertainment, and recreation");
});

