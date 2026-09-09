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

function armGate(constants, gateName = "HubSpot Update Write Gate") {
  let js = jsCodeOf(gateName);
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

// Phase 70 Plan 05 Task 2 sub-step 2c (D-70-06): the precheck this file was written for
// is GONE. It predicted the gate's verdict inside "Decide Action" instead of reporting
// it — a second copy of the predicate that could disagree with the first (its own
// comment conceded create rows were left uncovered for exactly that reason). The
// discriminating case quoted in this file's header is answered differently now, and
// better: the gate no longer FILTERS a refused row away (D-70-14), it EMITS it onto
// "Ingest Merge Response" directly, so a batch of nothing but refused writes still
// reaches "Build Ingest Response" — with no dependence on "Set Review" and no precheck.

test("Decide Action: the committed build reports the row's REAL action; permission is not its call any more", () => {
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  assert.equal(decided.outcome, "match", "seed row reached Decide Action as a match");
  assert.equal(decided.action, "update");
  assert.equal(decided.write_request.hs_object_id, "35551");
  assert.equal(decided.write_request.domain, "wyongraceclub.com.au",
    "F11's fix survives: the gate's allowlist domain is emitted, not re-derived");
});

test("HubSpot Update Write Gate: the COMMITTED (disarmed) build refuses, and EMITS the refusal", () => {
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  const [gated] = runCode(jsCodeOf("HubSpot Update Write Gate"), [decided]);
  assert.equal(gated.write_allowed, false,
    "the disarmed build (ALLOW_HUBSPOT_RECORD_WRITES=false) must never permit a write");
  assert.equal(gated.action, "write_blocked");
  assert.ok(gated.write_blocked_reason);
});

test("HubSpot Update Write Gate: armed but the domain is NOT on the allowlist -> still write_blocked", () => {
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  const js = armGate({ ALLOW_HUBSPOT_RECORD_WRITES: "true", TEST_RECORD_DOMAINS: "some-other-domain.example" });
  assert.equal(runCode(js, [decided])[0].action, "write_blocked");
});

test("HubSpot Update Write Gate: armed AND the domain IS on the allowlist -> permitted (regression pin, F11)", () => {
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  const js = armGate({ ALLOW_HUBSPOT_RECORD_WRITES: "true", TEST_RECORD_DOMAINS: "wyongraceclub.com.au" });
  const [gated] = runCode(js, [decided]);
  assert.equal(gated.write_allowed, true);
  assert.equal(gated.action, "update");
  assert.equal(gated.hs_object_id, "35551");
});

test("full flow: a refused row reaches Build Ingest Response reported as write_blocked, with no review row and no write chain at all", () => {
  // The gate's false branch is wired straight onto "Ingest Merge Response" (the same
  // input the association lane feeds), so "Build Ingest Response" sees TWO items for
  // this one row: the tagged decided snapshot (which still says "update" — that is the
  // pre-write intention, and reporting it unchanged is exactly execution 12181's
  // misreport) and the gate's own emitted refusal. The gate's verdict wins.
  const [decided] = runCode(jsCodeOf("Decide Action"), [gregRow()]);
  const [gated] = runCode(jsCodeOf("HubSpot Update Write Gate"), [decided]);

  const report = runCode(jsCodeOf("Build Ingest Response"),
    [{ ...decided, _decided_snapshot: true }, gated]);
  assert.equal(report.length, 1, "the blocked row must still be reported, exactly once");
  assert.equal(report[0].action, "write_blocked", "never the pre-block decided action (\"update\")");
  assert.equal(report[0].hs_object_id, "35551");
  assert.ok(report[0].reason, "the gate's own reason reaches the operator");
  assert.notEqual(report[0].association, "associated",
    "one verdict covers both (D-70-15) — a refused write never associated anything");
});
