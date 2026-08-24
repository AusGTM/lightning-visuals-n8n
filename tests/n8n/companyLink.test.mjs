// tests/n8n/companyLink.test.mjs
//
// Unit guard for n8n/code/companyLink.js — the contact -> company resolver behind the
// operator ruling of 2026-08-25 ("a contact must ALWAYS be associated with a company,
// and an existing company must never be recreated").
//
// The rules worth pinning are the ones whose failure is SILENT: a freemail address
// associating every contact onto one arbitrary company, and a near-miss name match
// putting a person at the wrong organisation.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const link = require(path.join(ROOT, "n8n", "code", "companyLink.js"));

const envelope = (companies) => ({
  total: companies.length,
  results: companies.map((c, i) => ({ id: c.id || String(100 + i), properties: c })),
});

test("companyDomainForRow: a work email yields its domain", () => {
  assert.equal(
    link.companyDomainForRow({ email: "Jo@RacingExample.com.au" }),
    "racingexample.com.au"
  );
});

test("companyDomainForRow: freemail yields null, never the ISP as a company", () => {
  for (const e of ["jo@gmail.com", "jo@bigpond.com", "jo@optusnet.com.au", "jo@icloud.com"]) {
    assert.equal(link.companyDomainForRow({ email: e }), null, e);
  }
});

test("companyDomainForRow: an explicit column outranks the email domain", () => {
  assert.equal(
    link.companyDomainForRow({ email: "jo@gmail.com", company_domain: "https://www.Club.com.au/about" }),
    "club.com.au"
  );
});

test("resolveCompanyLink: a manual company id wins over any search", () => {
  const out = link.resolveCompanyLink(
    { company_id: " 9604614548 ", email: "jo@club.com.au", company: "Club" },
    envelope([{ id: "111", name: "Club", domain: "club.com.au" }]),
    envelope([])
  );
  assert.equal(out.company_id, "9604614548");
  assert.equal(out.company_match, "manual");
});

test("resolveCompanyLink: an exact domain hit resolves and reports its basis", () => {
  const out = link.resolveCompanyLink(
    { email: "jo@club.com.au", company: "Some Other Name" },
    envelope([{ id: "222", name: "The Club", domain: "www.Club.com.au" }]),
    envelope([])
  );
  assert.equal(out.company_id, "222");
  assert.equal(out.company_match, "domain");
});

test("resolveCompanyLink: falls back to an EXACT name match when no domain matched", () => {
  const out = link.resolveCompanyLink(
    { email: "jo@gmail.com", company: "Melbourne Racing Club" },
    envelope([]),
    envelope([{ id: "333", name: "melbourne racing club", domain: "mrc.net.au" }])
  );
  assert.equal(out.company_id, "333");
  assert.equal(out.company_match, "name");
});

test("resolveCompanyLink: two companies with the same name is ambiguity, not a match", () => {
  const out = link.resolveCompanyLink(
    { email: "jo@gmail.com", company: "Racing Club" },
    envelope([]),
    envelope([
      { id: "444", name: "Racing Club", domain: "a.example" },
      { id: "555", name: "Racing Club", domain: "b.example" },
    ])
  );
  assert.equal(out.company_id, null);
  assert.match(out.company_hold_reason, /no company in HubSpot matched/);
});

test("resolveCompanyLink: a domain search that returned a DIFFERENT domain never matches", () => {
  // HubSpot search is EQ, but the guard is on this side too: an envelope carrying a
  // near-miss (a subdomain, a parent group) must not be taken as the row's company.
  const out = link.resolveCompanyLink(
    { email: "jo@club.com.au", company: null },
    envelope([{ id: "666", name: "Group", domain: "group.club.com.au" }]),
    envelope([])
  );
  assert.equal(out.company_id, null);
});

test("resolveCompanyLink: an errored search item degrades to a hold, never a throw", () => {
  const out = link.resolveCompanyLink(
    { email: "jo@club.com.au", company: "Club" },
    { error: "ECONNRESET" },
    { error: "ECONNRESET" }
  );
  assert.equal(out.company_id, null);
  assert.equal(out.company_match, null);
  assert.ok(out.company_hold_reason);
});

test("resolveCompanyLink: nothing to match on is its own hold reason", () => {
  const out = link.resolveCompanyLink({ email: "jo@gmail.com" }, envelope([]), envelope([]));
  assert.equal(out.company_id, null);
  assert.match(out.company_hold_reason, /no company domain or name/);
});

test("associationUrl: v4 default contact->company endpoint, or null when incomplete", () => {
  assert.equal(
    link.associationUrl("101", "202"),
    "https://api.hubapi.com/crm/v4/objects/contacts/101/associations/default/companies/202"
  );
  assert.equal(link.associationUrl("101", null), null);
  assert.equal(link.associationUrl(null, "202"), null);
});
