// tests/n8n/companyAssociationFlow.test.mjs
//
// The lane-level half of the 2026-08-25 association rule, executed against the COMMITTED
// n8n/wf_contact_ingest_cloud.json — the same `new Function` mechanism n8n's Code node
// uses at runtime (see contactCreateGateFlow.test.mjs's note; no untrusted input is
// interpolated into a function body here either).
//
// Three properties, each of which fails silently if it regresses:
//   1. an armed create with NO resolved company is HELD, not landed unassociated;
//   2. the association request joins a write RESPONSE back to its row by value — index
//      alignment is not available downstream of the write IFs;
//   3. the association PUT is gated like every other write in this lane.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");
const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};
const jsCodeOf = (name) => node(name).parameters.jsCode;

function runCode(jsCode, seedItems, nodeOutputs = {}) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const $ = (name) => {
    if (!(name in nodeOutputs)) throw new Error(`no node named ${name}`);
    return { all: () => nodeOutputs[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

const ARM = (js) =>
  js
    .replace('const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";')
    .replace(
      'const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
      'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'
    );

const netNew = (extra = {}) => ({
  identity: { outcome: "net_new" },
  merge: { canonicalPatch: {} },
  email: "jo@club.example",
  firstname: "Jo",
  lastname: "Rider",
  company: "Club",
  ...extra,
});

test("an armed create with no resolved company is held for review, with the reason kept", () => {
  const [held] = runCode(ARM(jsCodeOf("Decide Action")), [
    netNew({ company_id: null, company_hold_reason: "no company in HubSpot matched domain club.example" }),
  ]);
  assert.equal(held.action, "review", "an unassociated contact must never be created");
  assert.match(held.reason, /no company in HubSpot matched/);
  assert.equal(held.company_id, null);
});

test("the same armed create lands once a company is resolved", () => {
  const [created] = runCode(ARM(jsCodeOf("Decide Action")), [
    netNew({ company_id: "9600000001", company_match: "domain", company_domain: "club.example" }),
  ]);
  assert.equal(created.action, "create");
  assert.equal(created.company_id, "9600000001");
  assert.equal(created.properties.email, "jo@club.example");
});

test("an UPDATE with no resolved company is not held — it simply has nothing to associate", () => {
  const [updated] = runCode(jsCodeOf("Decide Action"), [
    { identity: { outcome: "match", contact_id: "555" }, merge: { canonicalPatch: { jobtitle: "CEO" } } },
  ]);
  assert.equal(updated.action, "update");
  assert.equal(updated.company_id, null);
});

test("Build Association Request joins by value: update by id, create by email", () => {
  const decided = [
    { action: "update", hs_object_id: "555", company_id: "900", company_domain: "club.example", properties: {} },
    { action: "create", hs_object_id: null, company_id: "901", company_domain: "other.example",
      properties: { email: "jo@other.example" } },
    { action: "update", hs_object_id: "777", company_id: null, properties: {} },
  ];
  const writeResponses = [
    { id: "555", properties: {} },                                   // update response
    { id: "12345", properties: { email: "JO@other.example" } },      // create response
    { id: "777", properties: {} },                                   // update, no company
    { error: "HubSpot rejected the write" },                         // failed write
  ];
  const out = runCode(jsCodeOf("Build Association Request"), writeResponses, {
    "Decide Action": decided,
  });
  assert.equal(out.length, 2, "only rows with a resolved company and a real id are requested");
  assert.deepEqual(
    out.map((r) => [r.contact_id, r.company_id, r.domain]),
    [["555", "900", "club.example"], ["12345", "901", "other.example"]]
  );
  assert.equal(
    out[1].assoc_url,
    "https://api.hubapi.com/crm/v4/objects/contacts/12345/associations/default/companies/901",
    "the created contact's own new id is what gets associated"
  );
});

test("the association PUT is a gated write node reading only fields its gate emits", () => {
  const assoc = node("HubSpot Associate Company");
  assert.equal(assoc.parameters.method, "PUT");
  assert.equal(assoc.parameters.url, "={{ $json.assoc_url }}");
  assert.equal(assoc.parameters.nodeCredentialType, "hubspotAppToken");
  assert.ok(!("onError" in assoc), "a refused association must fail the execution, not flow on");

  const feeders = Object.entries(wf.connections)
    .filter(([, spec]) =>
      (spec.main || []).some((outs) => (outs || []).some((c) => c.node === "HubSpot Associate Company")))
    .map(([src]) => src);
  assert.deepEqual(feeders, ["HubSpot Associate Company Write Gate"]);

  const gateJs = jsCodeOf("HubSpot Associate Company Write Gate");
  assert.match(gateJs, /_writeSafetyAllows/);
  const row = { action: "enrich", hs_object_id: "12345", domain: "club.example", assoc_url: "u" };
  assert.equal(runCode(gateJs, [row]).length, 0, "disarmed: the association is dropped");
  const armed = ARM(gateJs).replace(
    'const TEST_RECORD_DOMAINS = "";',
    'const TEST_RECORD_DOMAINS = "club.example";'
  );
  assert.equal(runCode(armed, [row]).length, 1, "armed with a matching domain: it passes");
});

test("Build Ingest Response reports every decided row, associated or not", () => {
  const decided = [
    { action: "create", outcome: "net_new", hs_object_id: null, company_id: "901",
      company_match: "domain", properties: { email: "jo@other.example" } },
    { action: "review", outcome: "net_new", hs_object_id: null, company_id: null,
      reason: "no company in HubSpot matched domain club.example", properties: {} },
  ];
  const requested = [{ contact_id: "12345", email: "jo@other.example", company_id: "901" }];
  const gated = [{ contact_id: "12345" }];
  const out = runCode(jsCodeOf("Build Ingest Response"), [{ status: "ok" }], {
    "Decide Action": decided,
    "Build Association Request": requested,
    "HubSpot Associate Company Write Gate": gated,
  });
  assert.equal(out.length, 2);
  assert.equal(out[0].association, "associated");
  assert.equal(out[0].contact_id, "12345", "the created row reports the id HubSpot minted");
  assert.equal(out[1].association, "none");
  assert.match(out[1].reason, /no company in HubSpot matched/);
  // report.py's sync_response_is_sufficient() accepts a body only when every item carries
  // a row-identifying key — pin that shape here rather than discovering it in a live run.
  for (const item of out) {
    assert.ok("contact_id" in item && "hs_object_id" in item && "email" in item);
  }
});
