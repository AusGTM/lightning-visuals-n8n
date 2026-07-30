// tests/n8n/lushaRequest.test.mjs
//
// Phase 20 Plan 02 Task 1 — n8n/code/lushaRequest.js's direct unit tests. Pins the
// never-pay-for-a-present-field rule (lushaReveal), the prototype-safe allow-list lookup
// (T-20-02 mitigation), and the two v3 body builders' identity + no-identity shapes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { LUSHA_REVEAL_BY_FIELD, lushaReveal, lushaContactBody, lushaContactEnrichByIdBody, lushaCompanyBody } =
  require(path.join(ROOT, "n8n/code/lushaRequest.js"));

// ---- lushaReveal() ----------------------------------------------------------

test("lushaReveal([]) -> []", () => {
  assert.deepEqual(lushaReveal([]), []);
});

test("lushaReveal(['jobtitle']) -> [] (free preview field, never reveal-billed)", () => {
  assert.deepEqual(lushaReveal(["jobtitle"]), []);
});

test("lushaReveal(['mobilephone']) -> exactly the phone reveal value", () => {
  assert.deepEqual(lushaReveal(["mobilephone"]), ["phones"]);
});

test("lushaReveal(['email','mobilephone']) -> both reveal values, stable order", () => {
  assert.deepEqual(lushaReveal(["email", "mobilephone"]), ["emails", "phones"]);
});

test("lushaReveal(['mobilephone','email']) -> same array regardless of input order", () => {
  assert.deepEqual(lushaReveal(["mobilephone", "email"]), ["emails", "phones"]);
});

test("lushaReveal hostile input: unmapped + prototype-chain names all drop out", () => {
  assert.deepEqual(
    lushaReveal(["lv_org_type", "__proto__", "constructor", "phone"]),
    []
  );
});

test("lushaReveal(undefined) and lushaReveal(null) -> [] without throwing", () => {
  assert.doesNotThrow(() => lushaReveal(undefined));
  assert.doesNotThrow(() => lushaReveal(null));
  assert.deepEqual(lushaReveal(undefined), []);
  assert.deepEqual(lushaReveal(null), []);
});

test("LUSHA_REVEAL_BY_FIELD is frozen and has exactly the two confirmed entries", () => {
  assert.ok(Object.isFrozen(LUSHA_REVEAL_BY_FIELD));
  assert.deepEqual(Object.keys(LUSHA_REVEAL_BY_FIELD).sort(), ["email", "mobilephone"]);
  assert.equal(LUSHA_REVEAL_BY_FIELD.email, "emails");
  assert.equal(LUSHA_REVEAL_BY_FIELD.mobilephone, "phones");
});

// ---- lushaContactBody() ------------------------------------------------------

test("lushaContactBody: email identity + missing mobilephone -> email + phone reveal", () => {
  const body = lushaContactBody({ email: "a@b.com" }, ["mobilephone"]);
  assert.deepEqual(body, { contacts: [{ email: "a@b.com" }], reveal: ["phones"] });
});

test("lushaContactBody: no usable identity key -> no-identity skip-not-retry form", () => {
  const body = lushaContactBody({}, ["email"]);
  assert.deepEqual(body, { contacts: [] });
});

test("lushaContactBody: no usable identity even with name fields blank/absent -> {contacts:[]}", () => {
  const body = lushaContactBody({ email: null, linkedin_url: "" }, []);
  assert.deepEqual(body, { contacts: [] });
});

test("lushaContactBody: never carries a caller-chosen index key (no contactId)", () => {
  const body = lushaContactBody({ email: "a@b.com" }, []);
  assert.ok(!("contactId" in body.contacts[0]));
});

test("lushaContactBody: nothing missing -> reveal defaults to minimal non-empty ['emails'] (v3 rejects empty reveal)", () => {
  const body = lushaContactBody({ email: "a@b.com" }, []);
  assert.deepEqual(body.reveal, ["emails"]);
  assert.ok(body.reveal.length > 0);
});

test("lushaContactBody: broader identity set (firstName/lastName/companyName/companyDomain) maps unchanged", () => {
  const body = lushaContactBody(
    { firstName: "Kyle", lastName: "Bettler", companyName: "Racing NSW", domain: "racingnsw.com.au" },
    []
  );
  assert.deepEqual(body.contacts[0], {
    firstName: "Kyle",
    lastName: "Bettler",
    companyName: "Racing NSW",
    companyDomain: "racingnsw.com.au",
  });
});

test("lushaContactBody: only jobtitle missing -> empty reveal from lushaReveal, defaulted to ['emails']", () => {
  const body = lushaContactBody({ email: "a@b.com" }, ["jobtitle"]);
  assert.deepEqual(body.reveal, ["emails"]);
});

// ---- lushaContactEnrichByIdBody() — Task 2b confirmed-free stored-id path -----

test("lushaContactEnrichByIdBody: stored id present -> {ids:[id], reveal} (no contacts key)", () => {
  const body = lushaContactEnrichByIdBody("v1.SYNTHETIC_ID", ["mobilephone"]);
  assert.deepEqual(body, { ids: ["v1.SYNTHETIC_ID"], reveal: ["phones"] });
  assert.ok(!("contacts" in body));
});

test("lushaContactEnrichByIdBody: nothing missing -> reveal defaults to ['emails']", () => {
  const body = lushaContactEnrichByIdBody("v1.SYNTHETIC_ID", []);
  assert.deepEqual(body.reveal, ["emails"]);
});

test("lushaContactEnrichByIdBody: storedId null/undefined/'' -> null (caller falls back to lushaContactBody)", () => {
  assert.equal(lushaContactEnrichByIdBody(null, []), null);
  assert.equal(lushaContactEnrichByIdBody(undefined, []), null);
  assert.equal(lushaContactEnrichByIdBody("", []), null);
});

test("lushaContactEnrichByIdBody: a stored id never regresses the no-id body — lushaContactBody() unchanged", () => {
  const noId = lushaContactBody({ email: "a@b.com" }, ["mobilephone"]);
  assert.deepEqual(noId, { contacts: [{ email: "a@b.com" }], reveal: ["phones"] });
});

// ---- lushaCompanyBody() -------------------------------------------------------

test("lushaCompanyBody: domain-only identity -> body carries only domain, no reveal key", () => {
  const body = lushaCompanyBody({ domain: "racingnsw.com.au" });
  assert.deepEqual(body, { companies: [{ domain: "racingnsw.com.au" }] });
  assert.ok(!("reveal" in body));
});

test("lushaCompanyBody: companyName is excluded even when present (BUG 17 — companies lane 400s on it)", () => {
  const body = lushaCompanyBody({ domain: "x.com", companyName: "X Pty Ltd" });
  assert.deepEqual(body.companies[0], { domain: "x.com" });
  assert.ok(!("companyName" in body.companies[0]));
});

test("lushaCompanyBody: no domain -> no-identity form", () => {
  const body = lushaCompanyBody({});
  assert.deepEqual(body, { companies: [] });
});
