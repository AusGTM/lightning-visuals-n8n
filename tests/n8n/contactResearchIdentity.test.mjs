// tests/n8n/contactResearchIdentity.test.mjs
//
// Found LIVE 2026-08-25, execution 11934 (contact 347569451461, John Tsatsimas). The
// research payload read `id.contactName || row.contactName` — a key NOTHING in the graph
// sets; Build Identity emits firstName/lastName. So `name` was always null, and for a
// contact with no company and no domain the research call carried no identity at all.
// Haiku answered "I need more information to research this contact", which is prose, so
// validation extracted nothing and the row reported a clean empty result: a failure that
// looked exactly like "this person could not be found".
//
// Runs the committed "Build Contact Research Request" jsCode (same mechanism n8n uses).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8"));
const jsCode = wf.nodes.find((n) => n.name === "Build Contact Research Request").parameters.jsCode;

function contactPayload(row) {
  const $input = { all: () => [{ json: row }] };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  const out = fn($input)[0].json.research_request_body;
  if (!out) return null;
  return JSON.parse(out.messages[0].content).contact;
}

// The live row, exactly as Build Identity shaped it for contact 347569451461.
const tsatsimasRow = () => ({
  research_needed: true,
  identity_keys: {
    email: null, domain: null,
    linkedin_url: "https://www.linkedin.com/in/john-tsatsimas-b193a3193/",
    firstName: "John", lastName: "Tsatsimas", companyName: null,
  },
});

test("the live case: a name-and-LinkedIn-only contact is researchable", () => {
  const contact = contactPayload(tsatsimasRow());
  assert.equal(contact.name, "John Tsatsimas", "the name must reach the research call");
  assert.equal(contact.linkedin_url, "https://www.linkedin.com/in/john-tsatsimas-b193a3193/");
  // The whole point: at least one identifier is present, so the model has something to
  // research instead of asking for more information.
  assert.ok(contact.name || contact.company || contact.domain || contact.linkedin_url);
});

test("a first name alone still composes, and a nameless row stays null (never an empty string)", () => {
  const first = contactPayload({ research_needed: true,
    identity_keys: { firstName: "John", lastName: null } });
  assert.equal(first.name, "John");
  const none = contactPayload({ research_needed: true, identity_keys: {} });
  assert.equal(none.name, null, "an absent name must be null, not \"\" — prefer unknown to blank");
});

test("company and domain still win when present, and are unchanged by this fix", () => {
  const contact = contactPayload({ research_needed: true,
    identity_keys: { firstName: "Jo", lastName: "Rider", companyName: "Club", domain: "club.example" } });
  assert.equal(contact.company, "Club");
  assert.equal(contact.domain, "club.example");
  assert.equal(contact.name, "Jo Rider");
});

test("a row that needs no research still builds no request body", () => {
  const $input = { all: () => [{ json: { research_needed: false, identity_keys: { firstName: "X" } } }] };
  const fn = new Function("$input", `"use strict";\n${jsCode}`);
  assert.equal(fn($input)[0].json.research_request_body, null);
});
