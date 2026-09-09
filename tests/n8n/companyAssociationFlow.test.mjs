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
  // F12: Decide Action now also pre-computes an update's write-safety verdict, so its
  // id needs to be on the allowlist too, or it reports write_blocked before this
  // test's own "not held" assertion is even reachable — orthogonal to what this test
  // checks (the hold rule, not write-safety), so armed here rather than left to collide.
  const armedJs = ARM(jsCodeOf("Decide Action")).replace(
    'const TEST_RECORD_IDS = "";', 'const TEST_RECORD_IDS = "555";');
  const [updated] = runCode(armedJs, [
    { identity: { outcome: "match", contact_id: "555" }, merge: { canonicalPatch: { jobtitle: "CEO" } } },
  ]);
  assert.equal(updated.action, "update");
  assert.equal(updated.company_id, null);
});

test("Build Association Request reads the carried fields directly off $input", () => {
  // Phase 70 Plan 02 Task 3 (D-70-04): this node's own direct predecessor is now a
  // carry merge (combineByPosition) spliced after "HubSpot Update"/"HubSpot Create" —
  // each item below is what THAT merge would already have produced: the write's own
  // HTTP response (`id`/`properties`) shallow-merged with the pre-write row Decide
  // Action stamped (`company_id`/`company_domain`/`hs_object_id`/`email`), the carried
  // row wired LAST so its identity fields win any key clash. No separate
  // "Decide Action" list to join against.
  const merged = [
    { id: "555", properties: {}, action: "update", hs_object_id: "555",
      company_id: "900", company_domain: "club.example" },
    { id: "12345", properties: { email: "JO@other.example" }, action: "create",
      hs_object_id: null, email: "jo@other.example", company_id: "901", company_domain: "other.example" },
    { id: "777", properties: {}, action: "update", hs_object_id: "777", company_id: null },
    // A write that failed (no `id` at all) — defensive case only: `on_error=None` on
    // every write node in this lane means this never reaches here live (a rejected
    // write fails the whole execution instead), but the function stays fail-closed.
    { error: "HubSpot rejected the write", action: "create", hs_object_id: null, company_id: null },
  ];
  const out = runCode(jsCodeOf("Build Association Request"), merged);
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
  // D-70-15 (Phase 70 Plan 05 Task 3): the association's OWN second allowlist gate is
  // gone. It ran downstream of a write that had already passed a gate, so a second
  // verdict could only ever disagree with the first (different action string, different
  // domain source). One write_request, one verdict — taken at "HubSpot Update Write
  // Gate"/"HubSpot Create Write Gate" upstream — and the association's only remaining
  // condition is a resolved company id, which "Build Association Request" applies by
  // dropping any row without one (CLAUDE.md §13.0.1: an update is NEVER held for lack of
  // a company; it simply has nothing to associate).
  assert.deepEqual(feeders, ["Build Association Request"]);
  assert.ok(!wf.nodes.some((n) => n.name === "HubSpot Associate Company Write Gate"));

  // The row a refused write would have produced never gets here at all: the update gate
  // emits it as `write_blocked` onto "Ingest Merge Response" directly, so neither the
  // write nor the association runs.
  const buildAssocJs = jsCodeOf("Build Association Request");
  const noCompany = runCode(buildAssocJs, [
    { id: "12345", email: "solo@club.example", company_id: null, row_id: "r1" },
  ]);
  assert.equal(noCompany.length, 0,
    "no resolved company -> nothing to associate (the update itself already ran)");
  const withCompany = runCode(buildAssocJs, [
    { id: "12345", email: "solo@club.example", company_id: "77", company_domain: "club.example",
      row_id: "r1" },
  ]);
  assert.equal(withCompany.length, 1);
  assert.equal(withCompany[0].company_id, "77");

});

test("Build Ingest Response reports every decided row, associated or not", () => {
  const decided = [
    { action: "create", outcome: "net_new", hs_object_id: null, company_id: "901",
      company_match: "domain", properties: { email: "jo@other.example" }, _decided_snapshot: true },
    { action: "review", outcome: "net_new", hs_object_id: null, company_id: null,
      reason: "no company in HubSpot matched domain club.example", properties: {},
      _decided_snapshot: true },
  ];
  // Phase 70 Plan 02 Task 3 (D-70-04): "Build Ingest Response" now reads $input.all()
  // (fed by "Ingest Merge Response", a THREE-input Merge) exclusively — this item is
  // the shape "Associate Carry Merge" delivers for a real association attempt (the
  // write response's own fields plus the row's carried contact_id/email/company_id),
  // and `decided` above carries `_decided_snapshot: true` (from "Decide Action
  // Snapshot") on the SAME item stream, never a separate `$('Decide Action')` lookup.
  const arrived = [
    { action: "enrich", contact_id: "12345", email: "jo@other.example", company_id: "901",
      status: "ok" },
  ];
  const out = runCode(jsCodeOf("Build Ingest Response"), [...arrived, ...decided]);
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
