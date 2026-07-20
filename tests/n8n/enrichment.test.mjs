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

const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));
const { scoreCandidates } = require(path.join(ROOT, "n8n/code/scoreEnrichment.js"));
const { decideAction } = require(path.join(ROOT, "n8n/code/enrichmentGate.js"));
const { normalizePhone } = require(path.join(ROOT, "n8n/code/normalizePhone.js"));

const FIX = path.join(ROOT, "tests/fixtures/enrichment");
const load = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name), "utf8"));
const NOW = "2026-07-14T00:00:00Z";

const lushaC = load("lusha_contact.json");
const apolloC = load("apollo_contact.json");
const zoomC = load("zoominfo_contact.json");
const lushaCo = load("lusha_company.json");
const apolloCo = load("apollo_company.json");
const zoomCo = load("zoominfo_company.json");
const apolloLive = load("apollo_live_match.json"); // real people/match: nested under `person`
const lushaLive = load("lusha_live_person.json"); // real v2 person: nested under contact.data
const zoomLive = load("zoominfo_live_enrich.json"); // real GTM enrich: data[].attributes + meta.matchStatus

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

test("toCandidates: Lusha US contact -> +1 E.164 via country_iso2; region-less non-AU dropped", () => {
  const usContact = { contact: { data: {
    location: { country_iso2: "US" },
    phoneNumbers: [{ number: "(475) 450-4590", phoneType: "mobile", doNotCall: false }],
    updateDate: "2026-06-01",
  } } };
  const mob = find(toCandidates("lusha", usContact, "contacts"), "mobilephone", "lusha");
  assert.ok(mob, "US number parsed with country_iso2=US");
  assert.equal(mob.normalizedValue, "+14754504590");
  // Same US number but NO country signal -> AU heuristic returns null -> null-drop (no candidate).
  const noGeo = { contact: { data: {
    phoneNumbers: [{ number: "(475) 450-4590", phoneType: "mobile", doNotCall: false }],
  } } };
  assert.equal(toCandidates("lusha", noGeo, "contacts").filter((c) => c.field === "mobilephone").length, 0);
});

test("toCandidates: Lusha live v2 (contact.data + emailAddresses/phoneNumbers) maps fields", () => {
  const c = toCandidates("lusha", lushaLive, "contacts");
  const email = find(c, "email", "lusha");
  assert.ok(email, "email candidate present from contact.data.emailAddresses");
  assert.equal(email.accuracy, 1.0); // A+ work
  assert.equal(email.normalizedValue, "mjames@australianturfclub.com.au");
  const mob = find(c, "mobilephone", "lusha");
  assert.ok(mob, "mobilephone from phoneNumbers[].phoneType=mobile");
  assert.equal(mob.normalizedValue, "+61412867770");
  assert.equal(find(c, "jobtitle", "lusha").normalizedValue, "general manager of broadcast");

  const co = toCandidates("lusha", lushaLive, "companies");
  assert.equal(find(co, "lv_revenue_band", "lusha").normalizedValue, "50-500M"); // 250M lower bound
  assert.equal(find(co, "lv_employee_band", "lusha").normalizedValue, "201-500");
  assert.equal(find(co, "lv_country_region_normalized", "lusha").normalizedValue, "AU");
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

test("toCandidates: Lusha A+ email -> 1.0; mobile phone -> mobilephone/0.8; doNotCall suppressed", () => {
  const c = toCandidates("lusha", lushaC, "contacts");
  assert.equal(find(c, "email", "lusha").accuracy, 1.0);
  const ph = find(c, "mobilephone", "lusha");
  assert.equal(ph.accuracy, 0.8);
  assert.equal(ph.normalizedValue, "+61412345678"); // 0412 345 678 -> E.164
  // doNotCall phone is dropped, not scored
  const dnc = toCandidates("lusha",
    { phones: [{ number: "0412 000 000", type: "mobile", doNotCall: true }] }, "contacts");
  assert.equal(dnc.length, 0);
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
    ...toCandidates("lusha", lushaC, "contacts"),
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
    ...toCandidates("lusha", lushaCo, "companies"),
    ...toCandidates("apollo", apolloCo, "companies"),
    ...toCandidates("zoominfo", zoomCo, "companies"),
  ];
}

test("score revenue: Apollo+Lusha band consensus beats lone ZoomInfo band", () => {
  const { best } = scoreCandidates(allCompanyCandidates(), { now: NOW });
  const rev = best.lv_revenue_band;
  assert.equal(rev.normalizedValue, "5-50M"); // 12M & 10M-25M agree; ZoomInfo 65M -> 50-500M loses
  assert.ok(rev.agreedBy.includes("lusha") || rev.agreedBy.includes("apollo"));
  assert.notEqual(rev.normalizedValue, "50-500M");
});

test("score industry: NAICS agreement (Lusha≡ZoomInfo) wins over Apollo free-text", () => {
  const { best } = scoreCandidates(allCompanyCandidates(), { now: NOW });
  const ind = best.industry;
  assert.equal(ind.normalizedValue, "711211");
  assert.ok(["lusha", "zoominfo"].includes(ind.source));
  assert.ok(ind.agreedBy.length >= 1);
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
  const r = decideAction(
    { jobtitle: "Analyst", jobtitle_verified_at: "2025-01-01T00:00:00Z" },
    ["jobtitle"], POLICY, NOW);
  assert.equal(r.action, "enrich");
  assert.deepEqual(r.staleFields, ["jobtitle"]);
});

test("gate: fresh + complete + valid -> skip", () => {
  const r = decideAction(
    { email: "a@b.com", jobtitle: "Analyst", jobtitle_verified_at: "2026-07-01T00:00:00Z" },
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
  const c = toCandidates("zoominfo", zoomLiveCo, "companies");
  assert.equal(find(c, "industry", "zoominfo").normalizedValue, "71");
});

test("toCandidates: Lusha live company unwraps `data` and reads `employees`", () => {
  // Live /v2/company wraps in `data` and returns headcount as a spaced range string;
  // without the unwrap this response produced ZERO candidates.
  const raw = { data: { name: "Racing NSW", revenueRange: [10000000, 50000000],
                        employees: "51 - 200", mainIndustry: "Entertainment",
                        location: { countryIso2: "AU" } }, meta: {} };
  const c = toCandidates("lusha", raw, "companies");
  assert.ok(c.length > 0, "live company response must yield candidates");
  assert.equal(find(c, "lv_revenue_band", "lusha").normalizedValue, "5-50M");
  // spaced range collapses onto the lv_employee_band enum value
  assert.equal(find(c, "lv_employee_band", "lusha").normalizedValue, "51-200");
  assert.equal(find(c, "lv_country_region_normalized", "lusha").normalizedValue, "AU");
});
