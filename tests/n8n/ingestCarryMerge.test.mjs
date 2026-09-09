// tests/n8n/ingestCarryMerge.test.mjs
//
// Phase 70 Plan 02 Task 3 (D-70-04): drives the COMMITTED n8n/wf_contact_ingest_cloud.json
// through the 70-01 walker for a four-row batch exercising every carry merge this task
// adds on the search/company-link side of the lane:
//   - "Verify Email Carry Merge" (the batch email-verify hop)
//   - "Search By Email Carry Merge" (per-row identity search)
//   - "Company Domain Carry Merge" / "Company Name Carry Merge" (the two-search chain,
//     with "Stash Domain Search" nesting the domain response between them)
// Row 1: email resolves to an existing contact (update), company resolves by DOMAIN.
// Row 2: email resolves to nothing (review, create disabled), company resolves by DOMAIN.
// Row 3: email resolves to nothing (review, create disabled), company resolves ONLY by
//        NAME (the domain search misses, the name search hits).
// Row 4: email resolves to a DIFFERENT existing contact (update), company resolves ONLY
//        by NAME.
//
// Same ARM()/loadArmedWorkflow() idiom as ingestTracerFlow.test.mjs — the committed JSON
// ships disarmed; an offline proof of the armed shape mutates the LOADED jsCode strings
// in memory, never the file on disk.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

const ROW1_EMAIL = "existing@acme-domain.example";
const ROW1_CONTACT_ID = "111";
const ROW1_COMPANY_ID = "9001";

const ROW2_EMAIL = "newperson@acme-domain.example";
const ROW2_COMPANY_ID = "9001"; // same domain-resolved company as row 1

const ROW3_EMAIL = "another@no-domain-match.example";
const ROW3_COMPANY_NAME = "Devonport Racing Club";
const ROW3_COMPANY_ID = "9002";

const ROW4_EMAIL = "fourth@no-domain-match.example";
const ROW4_CONTACT_ID = "444";
const ROW4_COMPANY_NAME = "Harness Racing NSW";
const ROW4_COMPANY_ID = "9003";

function loadArmedWorkflow({ testRecordIds = "" } = {}) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  // Phase 70 Plan 05 Task 2/3: "Decide Action" no longer bakes the write-safety
  // allowlist (its D-70-06 precheck is gone) and the association no longer has a gate of
  // its own (D-70-15 — one verdict, taken at the update gate). The update gate is the
  // single arming surface for this whole lane now.
  const armNames = ["HubSpot Update Write Gate"];
  for (const name of armNames) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `node present: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace(
        'const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'
      )
      .replace('const TEST_RECORD_IDS = "";', `const TEST_RECORD_IDS = "${testRecordIds}";`);
  }
  return wf;
}

function fourRowFixture() {
  return {
    triggerItems: [
      { email: ROW1_EMAIL, firstname: "One", lastname: "Person", company: "Acme Domain Co" },
      { email: ROW2_EMAIL, firstname: "Two", lastname: "Person", company: "Acme Domain Co" },
      { email: ROW3_EMAIL, firstname: "Three", lastname: "Person", company: ROW3_COMPANY_NAME },
      { email: ROW4_EMAIL, firstname: "Four", lastname: "Person", company: ROW4_COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{
        results: [
          { email: ROW1_EMAIL, status: "VALID" },
          { email: ROW2_EMAIL, status: "VALID" },
          { email: ROW3_EMAIL, status: "VALID" },
          { email: ROW4_EMAIL, status: "VALID" },
        ],
      }],
      "HubSpot Search by Email": [
        { results: [{ id: ROW1_CONTACT_ID, properties: { email: ROW1_EMAIL } }] },
        { results: [] },
        { results: [] },
        { results: [{ id: ROW4_CONTACT_ID, properties: { email: ROW4_EMAIL } }] },
      ],
      // Row 1 and Row 2 resolve by DOMAIN; Row 3 and Row 4 miss on domain (their
      // company_domain derives from an email whose domain no company owns) and fall
      // through to the NAME search below.
      "HubSpot Company Search by Domain": [
        { results: [{ id: ROW1_COMPANY_ID, properties: { domain: "acme-domain.example" } }] },
        { results: [{ id: ROW2_COMPANY_ID, properties: { domain: "acme-domain.example" } }] },
        { results: [] },
        { results: [] },
      ],
      "HubSpot Company Search by Name": [
        { results: [] },
        { results: [] },
        { results: [{ id: ROW3_COMPANY_ID, properties: { name: ROW3_COMPANY_NAME } }] },
        { results: [{ id: ROW4_COMPANY_ID, properties: { name: ROW4_COMPANY_NAME } }] },
      ],
      "HubSpot Update": [
        { id: ROW1_CONTACT_ID, properties: { email: ROW1_EMAIL } },
        { id: ROW4_CONTACT_ID, properties: { email: ROW4_EMAIL } },
      ],
      "HubSpot Associate Company": [{ status: "ok" }, { status: "ok" }],
    },
  };
}

test("a four-row batch reaches Build Ingest Response exactly once per row, each with the company match it should have, and pre-search fields survive the search hops", () => {
  const wf = loadArmedWorkflow({ testRecordIds: `${ROW1_CONTACT_ID},${ROW4_CONTACT_ID}` });
  const fixture = fourRowFixture();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: fixture.triggerItems,
    httpStubs: fixture.httpStubs,
  });

  // "Ingest Merge Response" — the ONE convergence Merge this batch's correctness rests
  // on — must never stall. ("Create Carry Merge" legitimately never fires on this
  // batch: nothing here is a create, ALLOW_HUBSPOT_CREATE stays baked false — an
  // accepted, documented gap, not asserted here as a false "no Merge ever stalls".)
  const ingestMergeStalled = trace.stalled.some((s) => s.node === "Ingest Merge Response");
  assert.equal(ingestMergeStalled, false, "Ingest Merge Response must never stall");

  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 4, "all four rows appear exactly once — no F5 collapse");

  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));

  // Row 1: update + domain match.
  assert.equal(byEmail[ROW1_EMAIL].action, "update");
  assert.equal(byEmail[ROW1_EMAIL].contact_id, ROW1_CONTACT_ID);
  assert.equal(byEmail[ROW1_EMAIL].company_id, ROW1_COMPANY_ID);
  assert.equal(byEmail[ROW1_EMAIL].company_match, "domain");
  assert.equal(byEmail[ROW1_EMAIL].association, "associated",
    "the write carry merge must re-attach the association write's own response to this row");

  // Row 2: review (net_new, create disabled) + domain match — company_id survives
  // even though this row never reaches a write node at all.
  assert.equal(byEmail[ROW2_EMAIL].action, "review");
  assert.equal(byEmail[ROW2_EMAIL].company_id, ROW2_COMPANY_ID);
  assert.equal(byEmail[ROW2_EMAIL].company_match, "domain");
  assert.equal(byEmail[ROW2_EMAIL].association, "not_confirmed",
    "a company resolved but never reached because this row is review, not a write");

  // Row 3: review + NAME-only match — the domain search missed, "Stash Domain Search"
  // carried that miss through, and the name search resolved it.
  assert.equal(byEmail[ROW3_EMAIL].action, "review");
  assert.equal(byEmail[ROW3_EMAIL].company_id, ROW3_COMPANY_ID);
  assert.equal(byEmail[ROW3_EMAIL].company_match, "name");

  // Row 4: update + NAME-only match — proves the company-link carry chain and the
  // write carry chain compose correctly on the SAME row.
  assert.equal(byEmail[ROW4_EMAIL].action, "update");
  assert.equal(byEmail[ROW4_EMAIL].contact_id, ROW4_CONTACT_ID);
  assert.equal(byEmail[ROW4_EMAIL].company_id, ROW4_COMPANY_ID);
  assert.equal(byEmail[ROW4_EMAIL].company_match, "name");
  assert.equal(byEmail[ROW4_EMAIL].association, "associated");

  // Fields present before the "Verify Emails (batch)" / "HubSpot Search by Email" hops
  // survive to the final report — the Rule-1 regression this task's carry merge fixes
  // (the old by-name read recovered "Normalize Phone", losing "Apply Email"'s own
  // email_status/email_valid fields before they ever reached Decide Action).
  for (const row of rows) {
    assert.equal(row.email_status, "VALID",
      `${row.email}: email_status must survive the search carry merge`);
  }
});

test("splice_carry_merge_after's mechanism retired every by-name read on this lane (D-70-03)", () => {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const httpNodes = wf.nodes.filter((n) =>
    n.type === "n8n-nodes-base.httpRequest" &&
    ["Verify Emails (batch)", "HubSpot Search by Email", "HubSpot Company Search by Domain",
     "HubSpot Company Search by Name", "HubSpot Update", "HubSpot Create",
     "HubSpot Associate Company"].includes(n.name));
  assert.equal(httpNodes.length, 7, "every HTTP hop this task carries a row across is present");
  for (const httpNode of httpNodes) {
    const targets = (wf.connections[httpNode.name]?.main || []).flatMap(
      (outs) => (outs || []).map((c) => c.node));
    assert.equal(targets.length, 1, `${httpNode.name} has exactly one outbound edge`);
    const target = wf.nodes.find((n) => n.name === targets[0]);
    assert.equal(target.type, "n8n-nodes-base.merge",
      `${httpNode.name}'s only consumer must be a carry merge, not a by-name reader`);
  }
});
