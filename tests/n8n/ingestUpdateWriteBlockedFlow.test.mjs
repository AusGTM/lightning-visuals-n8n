// tests/n8n/ingestUpdateWriteBlockedFlow.test.mjs
//
// F12 (uat-batch-review-row-reads-failed, execution 12181): "Build Ingest Response"
// reconstructs every row from "Decide Action" by name, so a row the downstream write
// gate silently refused still reported its ORIGINAL decided action ("update") as if it
// had landed — Greg Purcell's update was gated out (F11) yet the response said
// `action: "update", reason: "single email match"`.
//
// The discriminating case (why a "just add write_blocked to Build Ingest Response"
// fix is not enough): a Code node that filters to zero items never fires its own
// outgoing connection — the same "wave dropping" semantics this repo already relies on
// elsewhere (IF Company Skip's true lane). A batch with ONLY update/create rows, all
// refused by the write-safety allowlist, and NO review row at all, would leave
// "Build Ingest Response" with nothing to run off — the exact F1 dead-end shape,
// recurring for a different reason. So the write-safety verdict must be knowable
// BEFORE the IF-node fan-out, inside "Decide Action" itself (mirroring
// ENRICH_DECIDE_CLOUD's own precedent), routing a blocked row through "Set Review"'s
// already-wired edge into "Build Ingest Response" (F1) — no new wiring, no dependence
// on any node downstream of the IF split.
//
// Same `new Function` harness as pairPipelineAssociationFlow.test.mjs, over this
// repo's OWN committed n8n/wf_contact_ingest_cloud.json.
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

function armDecideAction(constants) {
  let js = jsCodeOf("Decide Action");
  for (const [name, value] of Object.entries(constants)) {
    const fromEmpty = `const ${name} = "";`;
    const fromFalse = `const ${name} = "false";`;
    const decl = js.includes(fromFalse) ? fromFalse : fromEmpty;
    assert.ok(js.includes(decl), `committed jsCode must carry the disabled ${name} declaration verbatim`);
    js = js.replace(decl, `const ${name} = ${JSON.stringify(value)};`);
  }
  return js;
}

// Execution 12181's Greg Purcell: an existing contact, resolved by domain, no
// hs_object_id on any allowlist.
function gregRow() {
  return {
    identity: { outcome: "match", contact_id: "35551" },
    merge: { canonicalPatch: {} },
    company_id: "9600000001",
    company_match: "domain",
    company_domain: "wyongraceclub.com.au",
    email_normalized: "greg@wyongraceclub.com.au",
  };
}

test("Decide Action: the COMMITTED (disarmed) build reports write_blocked for an update, never update", () => {
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  assert.equal(decided.outcome, "match", "seed row reached Decide Action as a match");
  assert.equal(decided.action, "write_blocked",
    "the disarmed build (ALLOW_HUBSPOT_RECORD_WRITES=false) must never report a live action");
});

test("Decide Action: armed but the domain is NOT on the allowlist -> still write_blocked", () => {
  const js = armDecideAction({ ALLOW_HUBSPOT_RECORD_WRITES: "true", TEST_RECORD_DOMAINS: "some-other-domain.example" });
  const [decided] = runCode(js, [gregRow()]);
  assert.equal(decided.action, "write_blocked");
});

test("Decide Action: armed AND the domain IS on the allowlist -> update (regression pin, F11)", () => {
  const js = armDecideAction({ ALLOW_HUBSPOT_RECORD_WRITES: "true", TEST_RECORD_DOMAINS: "wyongraceclub.com.au" });
  const [decided] = runCode(js, [gregRow()]);
  assert.equal(decided.action, "update");
  assert.equal(decided.hs_object_id, "35551");
});

test("full flow: a write_blocked row reaches Build Ingest Response with NO review row and NO write chain at all", () => {
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  assert.equal(decided.action, "write_blocked");

  // Neither IF Update ($json.action === "update") nor IF Create ($json.action ===
  // "create") matches "write_blocked" — this row falls through both to Set Review,
  // exactly the same false-lane routing a genuine review row takes. Nothing on the
  // association chain ever ran for this batch (no HubSpot write, no association
  // request, no association gate) — proven by feeding Build Ingest Response only the
  // empty node outputs a batch with zero write attempts would actually produce.
  const report = runCode(jsCodeOf("Build Ingest Response"), [], {
    "Decide Action": [decided],
    "Build Association Request": [],
    "HubSpot Associate Company Write Gate": [],
    "HubSpot Associate Company": [],
  });
  assert.equal(report.length, 1, "the blocked row must still be reported, not silently dropped");
  assert.equal(report[0].action, "write_blocked", "never the pre-block decided action (\"update\")");
  assert.equal(report[0].hs_object_id, "35551");
});
