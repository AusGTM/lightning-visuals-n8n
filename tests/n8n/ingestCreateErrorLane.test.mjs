// tests/n8n/ingestCreateErrorLane.test.mjs
//
// Phase 73 Plan 06 Task 3 (D-73-01, F-A6) — the create_failed refusal lane. Drives the
// COMMITTED n8n/wf_contact_ingest_cloud.json through the walker: three net-new rows all
// route to create, one of them is rejected by HubSpot (execution 12454's shape — a
// duplicate email). The other two must still associate to their own companies, the
// rejected row must reach the ingest response exactly once as a `create_failed` row
// carrying HubSpot's reason, and the batch must complete — not abort.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

const EMAIL_1 = "survivor1@laneone.example";
const EMAIL_2 = "rejected@lanetwo.example";
const EMAIL_3 = "survivor3@lanethree.example";
const COMPANY_1 = "9301";
const COMPANY_2 = "9302";
const COMPANY_3 = "9303";
const CREATED_1 = "hs-created-1";
const CREATED_3 = "hs-created-3";

function armGraphForCreate(wf, domains) {
  const domainsCsv = domains.join(",");
  const decide = wf.nodes.find((n) => n.name === "Decide Action");
  assert.ok(decide, "node present: Decide Action");
  decide.parameters.jsCode = decide.parameters.jsCode.replace(
    'const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";');
  for (const name of ["HubSpot Create Write Gate", "Associate Lane Sentinel"]) {
    const node = wf.nodes.find((n) => n.name === name);
    assert.ok(node, `node present: ${name}`);
    node.parameters.jsCode = node.parameters.jsCode
      .replace('const ALLOW_HUBSPOT_RECORD_WRITES = "false";',
        'const ALLOW_HUBSPOT_RECORD_WRITES = "true";')
      .replace('const ALLOW_HUBSPOT_CREATE = "false";', 'const ALLOW_HUBSPOT_CREATE = "true";')
      .replace('const TEST_RECORD_DOMAINS = "";', `const TEST_RECORD_DOMAINS = "${domainsCsv}";`);
  }
  return wf;
}

function triggerItems() {
  return [
    { email: EMAIL_1, firstname: "Survivor", lastname: "One", company: "Lane One Co" },
    { email: EMAIL_2, firstname: "Rejected", lastname: "Two", company: "Lane Two Co" },
    { email: EMAIL_3, firstname: "Survivor", lastname: "Three", company: "Lane Three Co" },
  ];
}

function commonStubs() {
  return {
    "Verify Emails (batch)": [{
      results: triggerItems().map((r) => ({ email: r.email, status: "VALID" })),
    }],
    "HubSpot Search by Email": triggerItems().map(() => ({ results: [] })), // net-new
    "HubSpot Company Search by Domain": [
      { results: [{ id: COMPANY_1, properties: { domain: "laneone.example" } }] },
      // The rejected row still resolves its OWN company — HubSpot rejects the CREATE
      // itself (a duplicate email, D-73-01's exact execution-12454 shape), never a
      // missing-company hold, which would divert it to review before it ever reached
      // "HubSpot Create" at all (2026-08-25 operator ruling: a create with no resolved
      // company is HELD, not attempted).
      { results: [{ id: COMPANY_2, properties: { domain: "lanetwo.example" } }] },
      { results: [{ id: COMPANY_3, properties: { domain: "lanethree.example" } }] },
    ],
    "HubSpot Company Search by Name": triggerItems().map(() => ({ results: [] })),
    "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
  };
}

test("one rejected create costs its own row: the other two associate to their own companies, the rejection reaches the response once", () => {
  const wf = armGraphForCreate(
    JSON.parse(fs.readFileSync(WF_PATH, "utf8")),
    ["laneone.example", "lanetwo.example", "lanethree.example"]
  );

  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: triggerItems(),
    httpStubs: {
      ...commonStubs(),
      "HubSpot Create": {
        success: [
          { id: CREATED_1, properties: { email: EMAIL_1 } },
          { id: CREATED_3, properties: { email: EMAIL_3 } },
        ],
        error: [
          {
            message: "Contact already exists. Existing ID: 555",
            properties: { email: EMAIL_2 },
            // A realistic n8n HTTP error shape can carry the OUTBOUND request
            // configuration, including its own Authorization header — T-73-06-01's
            // exact threat. Never read, never echoed.
            request: { headers: { Authorization: "Bearer super-secret-token" } },
          },
        ],
      },
    },
  });

  assert.deepEqual(starvedWithData(trace), [], "no merge may lose a row on this batch");

  const rows = nodeItems(runData, "Build Ingest Response");
  const byEmail = Object.fromEntries(rows.map((r) => [r.email, r]));

  // The two survivors associate to their OWN company, not each other's and not the
  // rejected row's (which never resolved one at all).
  assert.equal(byEmail[EMAIL_1].contact_id, CREATED_1);
  assert.equal(byEmail[EMAIL_1].company_id, COMPANY_1);
  assert.equal(byEmail[EMAIL_1].association, "associated");

  assert.equal(byEmail[EMAIL_3].contact_id, CREATED_3);
  assert.equal(byEmail[EMAIL_3].company_id, COMPANY_3);
  assert.equal(byEmail[EMAIL_3].association, "associated");

  // Exactly one refusal row, naming its own row and a reason built from whitelisted
  // fields only — never a raw dump of the error object.
  const refusals = rows.filter((r) => r.action === "create_failed");
  assert.equal(refusals.length, 1, "exactly one refusal row reaches the ingest response");
  assert.equal(refusals[0].email, EMAIL_2);
  assert.equal(refusals[0].outcome, "create_failed");
  assert.ok(refusals[0].reason.includes("Contact already exists. Existing ID: 555"),
    "the reason carries HubSpot's own message");
  assert.ok(!JSON.stringify(refusals[0]).includes("super-secret-token"),
    "T-73-06-01: the refusal row must never carry the outbound request's Authorization header");

  // The rejected row never claims an association and never reaches the association hop.
  assert.notEqual(byEmail[EMAIL_2].action, "create");
  assert.notEqual(byEmail[EMAIL_2].association, "associated");
  assert.equal(runData["HubSpot Associate Company"].flat().length, 2,
    "only the two survivors ever reach the association write");

  // Every input row returns exactly once — no duplicate, no leaked sentinel marker.
  assert.equal(rows.length, 3);
});

test("zero-rejection batch: the response is unchanged in shape and Create Carry Merge does not starve", () => {
  const wf = armGraphForCreate(
    JSON.parse(fs.readFileSync(WF_PATH, "utf8")),
    ["laneone.example", "lanethree.example"]
  );
  const items = [triggerItems()[0], triggerItems()[2]]; // rows 1 and 3 only, no row 2
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: items,
    httpStubs: {
      "Verify Emails (batch)": [{
        results: items.map((r) => ({ email: r.email, status: "VALID" })),
      }],
      "HubSpot Search by Email": items.map(() => ({ results: [] })),
      "HubSpot Company Search by Domain": [
        { results: [{ id: COMPANY_1, properties: { domain: "laneone.example" } }] },
        { results: [{ id: COMPANY_3, properties: { domain: "lanethree.example" } }] },
      ],
      "HubSpot Company Search by Name": items.map(() => ({ results: [] })),
      "HubSpot Create": [
        { id: CREATED_1, properties: { email: EMAIL_1 } },
        { id: CREATED_3, properties: { email: EMAIL_3 } },
      ],
      "HubSpot Associate Company": (rows) => rows.map(() => ({ status: "ok" })),
    },
  });

  assert.deepEqual(starvedWithData(trace), [], "no merge may lose a row on the zero-rejection batch");

  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 2, "no row is lost");
  for (const row of rows) {
    assert.notEqual(row.action, "create_failed", "no rejection on this batch");
    assert.equal(row.association, "associated");
  }

  // "Build Create Failure Row" must have run exactly once, emitting its own sentinel
  // marker rather than a refusal row.
  const failureRowRuns = nodeItems(runData, "Build Create Failure Row");
  assert.equal(failureRowRuns.length, 1);
  assert.equal(failureRowRuns[0]._gsd_sentinel_marker, true);
});
