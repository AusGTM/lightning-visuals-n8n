// tests/n8n/suggestionProvenanceFlow.test.mjs
//
// Phase 62 Plan 04 (D-62-17, D-62-16). Drives the REAL committed jsCode in
// n8n/wf_contact_ingest_cloud.json and n8n/wf_enrichment_cloud.json — the same
// `new Function` mechanism n8n's Code node uses at runtime (see
// companyAssociationFlow.test.mjs / outcomeContractFlow.test.mjs's own note; no
// untrusted input is interpolated into a function body here either).
//
// Task 1: a suggestion round's round-level source map, read by 'Merge Contacts' from
// the request envelope (via the 'Set Config' node) rather than off the row, produces
// mixed per-field provenance — claude_web for the fields web research named, the
// waterfall's own source for the fields it filled. Absent map -> today's flat csv.
//
// Task 2: 'Adapt Company Search' carries num_associated_contacts onto the row as a
// top-level key (never nested only inside existingRecord), and 'Build Response' stamps
// it explicitly (null on failure/zero-hit-search's own null, the number 0 on a real
// zero-hit count) so absence and a real zero can never look alike to the plugin.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function loadWorkflow(relPath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relPath), "utf8"));
}

function nodeOf(wf, name) {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
}

// Same `$`/`$input` mock shape as outcomeContractFlow.test.mjs / companyAssociationFlow.test.mjs
// — `all()` and `first()` both available, and a lookup for an unknown node throws (mirrors
// n8n's real behavior for a node not present/executed in the current workflow).
function runCode(jsCode, seedItems, nodeOutputs = {}) {
  const $input = { all: () => seedItems.map((j) => ({ json: j })) };
  const $ = (name) => {
    if (!(name in nodeOutputs)) throw new Error(`no node named ${name}`);
    const rows = nodeOutputs[name];
    return { all: () => rows.map((j) => ({ json: j })), first: () => (rows[0] === undefined ? undefined : { json: rows[0] }) };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

// --- Task 1: per-field provenance via the round-level source map -------------------------

const ingestWf = loadWorkflow("n8n/wf_contact_ingest_cloud.json");
const mergeContactsJs = nodeOf(ingestWf, "Merge Contacts").parameters.jsCode;

const SUGGESTION_ROW = {
  firstname: "Jo", lastname: "Rider", jobtitle: "Board Member", email: "jo@example.com",
  phone_normalized: "+61491570156",
};

test("a suggested row's provenance carries claude_web for the fields research named and the waterfall's own source for email/phone, from one map present on 'Set Config'", () => {
  const sourceMap = { firstname: "claude_web", lastname: "claude_web", jobtitle: "claude_web",
    email: "lusha", phone: "lusha" };
  const [out] = runCode(mergeContactsJs, [SUGGESTION_ROW], {
    "Set Config": [{ body: { source_by_field: sourceMap } }],
  });
  const provenance = out.merge.provenance;
  for (const field of ["firstname", "lastname", "jobtitle"]) {
    assert.equal(provenance[field].source, "claude_web", `${field} carries claude_web`);
  }
  assert.equal(provenance.email.source, "lusha");
  assert.equal(provenance.phone.source, "lusha");
});

test("the source map arrives as a JSON string on the multipart form field (dispatch.py's filename=None shape) and still parses", () => {
  const sourceMap = { jobtitle: "claude_web" };
  const [out] = runCode(mergeContactsJs, [SUGGESTION_ROW], {
    "Set Config": [{ body: { source_by_field: JSON.stringify(sourceMap) } }],
  });
  assert.equal(out.merge.provenance.jobtitle.source, "claude_web");
  // A field the map did not name still falls back to the flat "csv" default.
  assert.equal(out.merge.provenance.email.source, "csv");
});

test("with no source map present, every field's provenance reads the flat csv source — byte-identical to today's CSV upload", () => {
  const [out] = runCode(mergeContactsJs, [SUGGESTION_ROW], {
    "Set Config": [{ body: {} }],
  });
  const provenance = out.merge.provenance;
  for (const field of Object.keys(provenance)) {
    assert.equal(provenance[field].source, "csv", `${field} keeps the flat csv source`);
  }
});

test("with no 'Set Config' node at all (the local template's own shape) the read fails closed to {} — still the flat csv source", () => {
  const [out] = runCode(mergeContactsJs, [SUGGESTION_ROW], {});
  const provenance = out.merge.provenance;
  for (const field of Object.keys(provenance)) {
    assert.equal(provenance[field].source, "csv");
  }
});

// --- Task 2: num_associated_contacts on the company search and on the response -----------

const enrichWf = loadWorkflow("n8n/wf_enrichment_cloud.json");

test("the 'HubSpot Company Search' node's body requests num_associated_contacts alongside the properties the lane already asks for", () => {
  const searchNode = nodeOf(enrichWf, "HubSpot Company Search");
  const body = searchNode.parameters.jsonBody || searchNode.parameters.body;
  assert.match(body, /num_associated_contacts/);
});

test("Adapt Company Search: a search hit reporting 0 carries the row-level num_associated_contacts as the number 0, distinguishable from null", () => {
  const js = nodeOf(enrichWf, "Adapt Company Search").parameters.jsCode;
  const [out] = runCode(js, [{ identity_keys: { domain: "acme.example" } }], {
    "Build Company Identity": [{ identity_keys: { domain: "acme.example" } }],
    "HubSpot Company Search": [{ results: [{ id: "1", properties: { num_associated_contacts: "0" } }] }],
  });
  assert.equal(out.num_associated_contacts, 0);
  assert.notEqual(out.num_associated_contacts, null);
});

test("Adapt Company Search: a real nonzero count coerces the HubSpot string property to a number", () => {
  const js = nodeOf(enrichWf, "Adapt Company Search").parameters.jsCode;
  const [out] = runCode(js, [{ identity_keys: { domain: "acme.example" } }], {
    "Build Company Identity": [{ identity_keys: { domain: "acme.example" } }],
    "HubSpot Company Search": [{ results: [{ id: "1", properties: { num_associated_contacts: "3" } }] }],
  });
  assert.equal(out.num_associated_contacts, 3);
});

test("Adapt Company Search: a lookup_failed row carries num_associated_contacts as explicit null, never a missing key", () => {
  const js = nodeOf(enrichWf, "Adapt Company Search").parameters.jsCode;
  const [out] = runCode(js, [{ identity_keys: { domain: "acme.example" } }], {
    "Build Company Identity": [{ identity_keys: { domain: "acme.example" } }],
    "HubSpot Company Search": [{ error: "timeout" }],
  });
  assert.equal(out.lookup_failed, true);
  assert.ok("num_associated_contacts" in out, "the key is present even on a failed lookup");
  assert.equal(out.num_associated_contacts, null);
});

test("Adapt Company Search: a zero-hit search (no error, empty results) also stamps null — no promotion to a false zero", () => {
  const js = nodeOf(enrichWf, "Adapt Company Search").parameters.jsCode;
  const [out] = runCode(js, [{ identity_keys: { domain: "acme.example" } }], {
    "Build Company Identity": [{ identity_keys: { domain: "acme.example" } }],
    "HubSpot Company Search": [{ results: [] }],
  });
  assert.equal(out.lookup_failed, false);
  assert.equal(out.num_associated_contacts, null);
});

function runBuildResponse(items, extraOutputs) {
  const outputs = {
    "Parse HubSpot Event": [{ providers_requested: [] }],
    ...(extraOutputs || {}),
  };
  return runCode(nodeOf(enrichWf, "Build Response").parameters.jsCode, items, outputs);
}

test("Build Response stamps num_associated_contacts on the response, present as explicit null when the row does not carry one", () => {
  const [built] = runBuildResponse([{ row_id: "row-1", action: "skip" }]);
  assert.ok("num_associated_contacts" in built);
  assert.equal(built.num_associated_contacts, null);
});

test("Build Response stamps a real zero count as the number 0, distinguishable from null", () => {
  const [built] = runBuildResponse([{ row_id: "row-1", action: "skip", num_associated_contacts: 0 }]);
  assert.equal(built.num_associated_contacts, 0);
  assert.notEqual(built.num_associated_contacts, null);
});

test("Build Response bumped outcome_contract_version to 2 for this additive field", () => {
  const [built] = runBuildResponse([{ row_id: "row-1", action: "skip" }]);
  assert.equal(built.outcome_contract_version, 2);
});
