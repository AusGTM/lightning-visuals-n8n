// tests/n8n/mobilephoneLaneFlow.test.mjs
//
// 73.1-06 (D-16a/D-16a-i/D-16d). Drives the COMMITTED n8n/wf_contact_ingest_cloud.json
// through the 70-01 walker to prove the ingest lane's two new identity-ladder rungs --
// "IF Linkedin Searchable" -> "HubSpot Linkedin Search" -> "Adapt Linkedin Search", and
// "IF Mobilephone Searchable" -> "HubSpot Mobilephone Search" -> "Adapt Mobilephone
// Search" -- spliced between "Adapt Search Results" and "Resolve Identity".
//
// D-16a-i: `mobilephone` matches on EQ only when there is EXACTLY ONE hit; more than one
// hit routes to review and never updates. `phone` (a landline) is NEVER searched at all
// -- it is CREATE-only identity, carried through the ordinary MERGE_CONTACTS non-clobber
// engine, never a match rung.
//
// Same ARM()/loadArmedWorkflow() idiom as ingestWidenedFieldsFlow.test.mjs -- the
// committed JSON ships disarmed; an offline proof of the armed shape mutates the LOADED
// jsCode strings in memory, never the file on disk. Arms EVERY node's jsCode by regex
// sweep (mirrors operator-claude-plugin/scripts/n8n_arming.py's set_write_safety), never
// a hand-written node-name list -- a subset-armed workflow is a test artifact, not a
// deployable state.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

const COMPANY_ID = "9800001";
const COMPANY_NAME = "Mobilephone Lane Co";

function armWorkflow(wf, { testRecordIds = "" } = {}) {
  // Sweep EVERY node's jsCode for both write-safety declarations, whatever value they
  // currently hold -- mirrors n8n_arming.set_write_safety's bidirectional regex, not a
  // hand-written list of node names.
  let recordWritesHits = 0;
  let createHits = 0;
  for (const node of wf.nodes) {
    const js = node.parameters && node.parameters.jsCode;
    if (typeof js !== "string") continue;
    let next = js.replace(
      /const\s+ALLOW_HUBSPOT_RECORD_WRITES\s*=\s*[^;]+;/,
      'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'
    );
    if (next !== js) recordWritesHits += 1;
    const beforeCreate = next;
    next = next.replace(
      /const\s+ALLOW_HUBSPOT_CREATE\s*=\s*[^;]+;/,
      'const ALLOW_HUBSPOT_CREATE = "true";'
    );
    if (next !== beforeCreate) createHits += 1;
    next = next.replace(
      'const TEST_RECORD_IDS = "";',
      `const TEST_RECORD_IDS = "${testRecordIds}";`
    );
    node.parameters.jsCode = next;
  }
  assert.ok(recordWritesHits >= 1, "ALLOW_HUBSPOT_RECORD_WRITES must be declared somewhere on this lane");
  assert.ok(createHits >= 1, "ALLOW_HUBSPOT_CREATE must be declared somewhere on this lane (Decide Action)");
  return wf;
}

function loadArmedWorkflow(opts) {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  return armWorkflow(wf, opts);
}

// Every fixture below resolves its company by NAME (these rows carry no email, so
// there is no email-domain to resolve a company by) -- "HubSpot Company Search by
// Domain" always misses, "HubSpot Company Search by Name" hits on COMPANY_NAME.
function companyStubs() {
  return {
    "HubSpot Company Search by Domain": (items) => items.map(() => ({ results: [] })),
    "HubSpot Company Search by Name": (items) => items.map((it) =>
      it.company_search_name === COMPANY_NAME
        ? { results: [{ id: COMPANY_ID, properties: { name: COMPANY_NAME } }] }
        : { results: [] }
    ),
    "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
  };
}

// --- Test 1: a single mobilephone-only row walks clean, zero stalled Merges ------------

test("a batch of one row carrying only firstname, lastname and mobilephone walks from the webhook to a decided outcome with zero stalled nodes and zero Merges that fired with an unfilled input", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "" });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { firstname: "Mo", lastname: "Bile", mobilephone: "+61411000001", company: COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [] }],
      "HubSpot Search by Email": [{ results: [] }],
      "HubSpot Mobilephone Search": [{ results: [] }],
      ...companyStubs(),
      "HubSpot Create": (items) => items.map((it) => ({ id: "700001", properties: it.properties })),
    },
  });

  assert.deepEqual(starvedWithData(trace), [], "no Merge on this lane may stall on this batch");
  const decided = nodeItems(runData, "Decide Action");
  assert.equal(decided.length, 1, "the single row reaches a decided outcome");
});

// --- Test 2: a four-way mixed batch, every row reaches Build Ingest Response -----------

test("a batch mixing an email row, a linkedin row, a mobilephone row and a row with none of them walks clean and every row reaches Build Ingest Response", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "" });
  const EMAIL_ROW = "mixedbatch@example.invalid";
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: EMAIL_ROW, firstname: "Em", lastname: "Ail", company: COMPANY_NAME },
      { firstname: "Link", lastname: "Din", linkedin_url: "https://linkedin.com/in/mixedbatch",
        company: COMPANY_NAME },
      { firstname: "Mo", lastname: "Bile", mobilephone: "+61411000002", company: COMPANY_NAME },
      { firstname: "None", lastname: "Ofthem", company: COMPANY_NAME }, // weak name+company only
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: EMAIL_ROW, status: "VALID" }] }],
      "HubSpot Search by Email": (items) => items.map(() => ({ results: [] })),
      "HubSpot Linkedin Search": [{ results: [] }],
      "HubSpot Mobilephone Search": [{ results: [] }],
      ...companyStubs(),
      "HubSpot Create": (items) => items.map((it) => ({ id: "700002", properties: it.properties })),
    },
  });

  assert.deepEqual(starvedWithData(trace), [], "no Merge on this mixed batch may stall");
  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 4, "all four rows reach the final report exactly once");
});

// --- Test 3: exactly one mobilephone hit -> update -------------------------------------

test("a mobilephone search returning exactly one hit produces an update action for that row", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "601" });
  const MOBILE = "+61411000003";
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { firstname: "Match", lastname: "One", mobilephone: MOBILE, company: COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [] }],
      "HubSpot Search by Email": [{ results: [] }],
      "HubSpot Mobilephone Search": [{
        results: [{ id: "601", properties: { mobilephone: MOBILE, firstname: "Match", lastname: "One" } }],
      }],
      "HubSpot Contact History": [{ propertiesWithHistory: {} }],
      ...companyStubs(),
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);
  const decided = nodeItems(runData, "Decide Action");
  assert.equal(decided.length, 1);
  assert.equal(decided[0].action, "update");
  assert.equal(decided[0].contact_id, "601");
});

// --- Test 4: more than one hit -> review, never a pick ---------------------------------

test("a mobilephone search returning two hits produces a review action naming multiple matches, and no update", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "" });
  const MOBILE = "+61411000004";
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { firstname: "Match", lastname: "Many", mobilephone: MOBILE, company: COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [] }],
      "HubSpot Search by Email": [{ results: [] }],
      "HubSpot Mobilephone Search": [{
        results: [
          { id: "602", properties: { mobilephone: MOBILE } },
          { id: "603", properties: { mobilephone: MOBILE } },
        ],
      }],
      ...companyStubs(),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);
  const decided = nodeItems(runData, "Decide Action");
  assert.equal(decided.length, 1);
  assert.equal(decided[0].action, "review");
  assert.equal(decided[0].contact_id, null, "never a pick among multiple hits");
  assert.ok(/multiple mobilephone matches/.test(decided[0].reason),
    `reason must name the multiple-match cause, got: ${decided[0].reason}`);

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(updateRows.length, 0, "no update ever fires on an ambiguous mobilephone match");
});

// --- Test 5: zero hits -> falls through to create --------------------------------------

test("a mobilephone search returning zero hits falls through to create", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "" });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { firstname: "Net", lastname: "New", mobilephone: "+61411000005", company: COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [] }],
      "HubSpot Search by Email": [{ results: [] }],
      "HubSpot Mobilephone Search": [{ results: [] }],
      ...companyStubs(),
      "HubSpot Create": (items) => items.map((it) => ({ id: "700005", properties: it.properties })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);
  const decided = nodeItems(runData, "Decide Action");
  assert.equal(decided.length, 1);
  assert.equal(decided[0].action, "create");
  assert.equal(decided[0].outcome, "net_new");
});

// --- Test 6: `phone` alone is NEVER routed into the mobilephone search (D-16a-i) -------

test("a row carrying a phone and no mobilephone is never routed into the mobilephone search at all, and the phone value is carried onto the created contact", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "" });
  const PHONE = "+61288880000";
  let mobilephoneSearchCalls = 0;
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { firstname: "Land", lastname: "Line", phone: PHONE, company: COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [] }],
      "HubSpot Search by Email": [{ results: [] }],
      "HubSpot Mobilephone Search": (items) => {
        mobilephoneSearchCalls += items.length;
        return items.map(() => ({ results: [] }));
      },
      ...companyStubs(),
      "HubSpot Create": (items) => items.map((it) => ({ id: "700006", properties: it.properties })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);
  assert.equal(mobilephoneSearchCalls, 0,
    "D-16a-i: a phone-only row must never reach the mobilephone search node at all");

  // Asserted at "Decide Action" -- the proposed create's own payload -- rather than
  // requiring "HubSpot Create" to actually fire: this row has no email and no
  // resolved domain, so "HubSpot Create Write Gate"'s allowlist (TEST_RECORD_DOMAINS/
  // TEST_RECORD_IDS, BUG 27's email-derived-domain fallback) has no key to arm it by
  // -- a genuinely separate, pre-existing write-gate/allowlist-scoping question this
  // plan does not touch (write_request.domain is only ever derived FROM an email,
  // scripts/build_cloud_workflows.py's `_buildWriteRequest`). The claim this test
  // proves -- "the phone value is carried onto the created contact" -- is the row's
  // own proposed properties, which the write gate would PATCH byte-for-byte were it
  // armed.
  const decided = nodeItems(runData, "Decide Action");
  assert.equal(decided.length, 1);
  assert.equal(decided[0].action, "create");
  assert.equal(decided[0].properties.phone, PHONE,
    "phone is create-only identity (D-16a-i) -- its own value must land on the created contact's "
    + "proposed payload via the ordinary MERGE_CONTACTS non-clobber engine");
});

// --- Test 7: the resolving identity key reaches Build Ingest Response (D-16d) ---------

test("the decided row names which identity key resolved it, and that value reaches Build Ingest Response", () => {
  const wf = loadArmedWorkflow({ testRecordIds: "701" });
  const MOBILE = "+61411000007";
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { firstname: "Resolved", lastname: "By", mobilephone: MOBILE, company: COMPANY_NAME },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [] }],
      "HubSpot Search by Email": [{ results: [] }],
      "HubSpot Mobilephone Search": [{
        results: [{ id: "701", properties: { mobilephone: MOBILE } }],
      }],
      "HubSpot Contact History": [{ propertiesWithHistory: {} }],
      ...companyStubs(),
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);
  const decided = nodeItems(runData, "Decide Action");
  assert.equal(decided.length, 1);
  assert.equal(decided[0].resolved_by, "mobilephone",
    "D-16d: the resolving identity key, in laneOf's own vocabulary");

  const rows = nodeItems(runData, "Build Ingest Response");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].resolved_by, "mobilephone",
    "the resolving key must reach the lane's final per-row report");
});

// --- Test 8: generation contracts on the committed JSON --------------------------------

test("the generated wf_contact_ingest_cloud.json passes every generation contract, contains zero executeWorkflow dispatch nodes, and every Merge has at most 10 inputs", () => {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

  const executeWorkflowNodes = wf.nodes.filter((n) => n.type === "n8n-nodes-base.executeWorkflow");
  assert.equal(executeWorkflowNodes.length, 0, "no self-dispatch node may exist on this lane");

  const merges = wf.nodes.filter((n) => n.type === "n8n-nodes-base.merge");
  assert.ok(merges.length > 0, "the new rungs must have added at least one Merge");
  for (const m of merges) {
    const inputs = m.parameters && m.parameters.numberInputs;
    assert.ok(inputs <= 10, `${m.name} declares ${inputs} inputs, over n8n's own 10-input cap`);
  }

  assert.equal(wf.settings.executionOrder, "v1");

  const linkedinNodes = ["IF Linkedin Searchable", "HubSpot Linkedin Search", "Adapt Linkedin Search"];
  const mobilephoneNodes = ["IF Mobilephone Searchable", "HubSpot Mobilephone Search", "Adapt Mobilephone Search"];
  for (const name of [...linkedinNodes, ...mobilephoneNodes]) {
    assert.ok(wf.nodes.some((n) => n.name === name), `${name} must exist on the committed workflow`);
  }
});
