// tests/n8n/ingestWidenedFieldsFlow.test.mjs
//
// Phase 72 Plan 01 (D-72-01 tracer, D-72-03, D-72-22). Drives the COMMITTED
// n8n/wf_contact_ingest_cloud.json through the 70-01 walker to prove the thinnest
// end-to-end path this phase exists to open: a `mobilephone` value travels
// CSV header -> columnMap.js -> the ingest lane's candidate -> mergeContacts() -> the
// HubSpot Create/Update body, and is PROTECTED rather than clobbered when the matched
// HubSpot contact already holds a different value.
//
// F71-5 recorded Busteed 352422766048 landing with email + phone + title while his held
// row carried a paid-for mobilephone +61 419 212 580 — this is the tracer for that
// defect.
//
// D-72-22 (operator ruling, 2026-09-12, raised as a blocking-human checkpoint by this
// very task): mergeContacts() is called with a flat `{ source: "csv", confidence: 80 }`,
// while `mobilephone` is fill_blank_only @ 85 — so a CSV-carried mobile could never
// promote, even into a blank field, without a per-field confidence override. Every
// positive fixture below therefore carries `source_by_field: { mobilephone: <provider> }`
// on the request envelope (the same request-level multipart field dispatch.py sends,
// parsed once by "Set Config Fields" and broadcast onto every row by the "Source By
// Field Broadcast" combineAll merge — see suggestionProvenanceFlow.test.mjs's Task 1/2
// for the same mechanism's isolated-jsCode proof). The negative test at the bottom pins
// the other half of the ruling: a field resolving to the flat csv source stays exactly
// as untrusted as before.
//
// Same ARM()/loadArmedWorkflow() idiom as ingestTracerFlow.test.mjs / ingestCarryMerge.test.mjs
// — the committed JSON ships disarmed; an offline proof of the armed shape mutates the
// LOADED jsCode strings in memory, never the file on disk. Arms EVERY node's jsCode by
// regex sweep (mirrors operator-claude-plugin/scripts/n8n_arming.py's set_write_safety),
// never a hand-written node-name list — a subset-armed workflow is a test artifact, not
// a deployable state.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";
import { walkWorkflow, nodeItems, starvedWithData } from "./lib/walkWorkflow.mjs";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json");

const { mapRow } = require(path.join(ROOT, "n8n/code/columnMap.js"));

const DOMAIN = "widenedfields.example";
const COMPANY_ID = "9700001";

function armWorkflow(wf, { testRecordDomains = "" } = {}) {
  // Sweep EVERY node's jsCode for both write-safety declarations, whatever value they
  // currently hold — mirrors n8n_arming.set_write_safety's bidirectional regex, not a
  // hand-written list of node names. "Decide Action" bakes ALLOW_HUBSPOT_CREATE
  // independently of the write gates (it decides net_new -> create vs. review before
  // any gate runs), so it must be swept too, not just the two write gates.
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
      'const TEST_RECORD_DOMAINS = "";',
      `const TEST_RECORD_DOMAINS = "${testRecordDomains}";`
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

// --- Header aliasing (D-72-03) — cheap direct check, independent of the walker -----------

test("a CSV column headed 'mobile' maps to canonical key mobilephone; 'phone' still maps to phone", () => {
  assert.deepEqual(mapRow({ mobile: "0411 111 111" }), { mobilephone: "0411 111 111" });
  assert.deepEqual(mapRow({ phone: "02 9000 0000" }), { phone: "02 9000 0000" });
  assert.deepEqual(mapRow({ Mobile: "0411 111 111", Phone: "02 9000 0000" }),
    { mobilephone: "0411 111 111", phone: "02 9000 0000" });
});

// --- Main tracer: create / protect / fill, all in one batch -----------------------------

const ROW_A_EMAIL = "newmobile@" + DOMAIN;   // net_new -> create
const ROW_B_EMAIL = "protected@" + DOMAIN;   // matched, HubSpot holds a DIFFERENT mobile
const ROW_C_EMAIL = "fillme@" + DOMAIN;      // matched, HubSpot holds NO mobile
const ROW_B_CONTACT_ID = "222";
const ROW_C_CONTACT_ID = "333";

const ROW_B_EXISTING_MOBILE = "+61400000000";
const ROW_A_MOBILE = "+61411111111";
const ROW_B_MOBILE = "+61422222222"; // the CSV's own value for row B — must NOT land
const ROW_C_MOBILE = "+61433333333";

function tracerFixture() {
  return {
    // Only item[0]'s `body` is read by "Set Config Fields" ($input.first()) — the
    // round-level source map is genuinely one-per-request, matching dispatch.py's own
    // multipart field (CLAUDE.md D-72-22 / §13.0.2's `source_by_field` idiom).
    triggerItems: [
      {
        body: { source_by_field: { mobilephone: "zoominfo" } },
        email: ROW_A_EMAIL, firstname: "New", lastname: "Mobile", company: "Widened Fields Co",
        mobilephone: ROW_A_MOBILE,
      },
      { email: ROW_B_EMAIL, firstname: "Pro", lastname: "Tected", company: "Widened Fields Co",
        mobilephone: ROW_B_MOBILE },
      { email: ROW_C_EMAIL, firstname: "Fill", lastname: "Me", company: "Widened Fields Co",
        mobilephone: ROW_C_MOBILE },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{
        results: [
          { email: ROW_A_EMAIL, status: "VALID" },
          { email: ROW_B_EMAIL, status: "VALID" },
          { email: ROW_C_EMAIL, status: "VALID" },
        ],
      }],
      "HubSpot Search by Email": (items) => items.map((it) => {
        const email = it.email_normalized || it.email;
        if (email === ROW_B_EMAIL) {
          return { results: [{ id: ROW_B_CONTACT_ID,
            properties: { email: ROW_B_EMAIL, mobilephone: ROW_B_EXISTING_MOBILE } }] };
        }
        if (email === ROW_C_EMAIL) {
          // No mobilephone property at all — a genuinely blank/absent existing value.
          return { results: [{ id: ROW_C_CONTACT_ID, properties: { email: ROW_C_EMAIL } }] };
        }
        return { results: [] }; // row A: net_new
      }),
      // Rows B and C resolve a contact_id above; row A is net_new.
      "HubSpot Contact History": (items) => items.map(() => ({ propertiesWithHistory: {} })),
      "HubSpot Company Search by Domain": (items) => items.map((it) =>
        it.company_search_domain === DOMAIN
          ? { results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }
          : { results: [] }
      ),
      "HubSpot Company Search by Name": (items) => items.map(() => ({ results: [] })),
      "HubSpot Create": (items) => items.map((it) => ({ id: "555555", properties: it.properties })),
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  };
}

test("D-72-01 tracer: mobilephone reaches HubSpot Create for a net_new row, is withheld from an update that already holds a different value, and fills a blank one", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const fixture = tracerFixture();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: fixture.triggerItems,
    httpStubs: fixture.httpStubs,
  });

  assert.deepEqual(starvedWithData(trace), [], "no Merge on this lane may lose a row on this batch");

  // Semantic check at the merge decision itself, before the write-node proof below.
  const merged = nodeItems(runData, "Merge Contacts");
  const byEmail = Object.fromEntries(merged.map((r) => [r.email, r]));
  const decisionFor = (email, field) =>
    (byEmail[email].merge.decisions || []).find((d) => d.field === field);

  assert.equal(decisionFor(ROW_A_EMAIL, "mobilephone").decision, "promote",
    "row A: blank existing (net_new -> {}), provider-graded confidence clears 85 -> promote");
  assert.equal(decisionFor(ROW_B_EMAIL, "mobilephone").decision, "stage_only",
    "row B: fill_blank_only with a non-blank existing value -> stage_only, never a clobber");
  assert.equal(decisionFor(ROW_C_EMAIL, "mobilephone").decision, "promote",
    "row C: existing mobilephone genuinely blank/absent -> promote");

  // The tracer's actual proof: walk the real HubSpot Create / Update request bodies.
  const createRows = nodeItems(runData, "HubSpot Create");
  assert.equal(createRows.length, 1, "only row A is a create");
  assert.equal(createRows[0].properties.mobilephone, ROW_A_MOBILE,
    "F71-5's exact defect: a paid-for mobile must reach the HubSpot Create body");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(updateRows.length, 2, "rows B and C are both updates");
  const updateByObjectId = Object.fromEntries(updateRows.map((r) => [r.id, r]));

  assert.equal(
    Object.prototype.hasOwnProperty.call(updateByObjectId[ROW_B_CONTACT_ID].properties, "mobilephone"),
    false,
    "row B: a DIFFERENT non-blank existing mobilephone must not be overwritten"
  );
  assert.equal(updateByObjectId[ROW_C_CONTACT_ID].properties.mobilephone, ROW_C_MOBILE,
    "row C: a blank/absent existing mobilephone must be filled");
});

// --- Negative: no source_by_field entry for mobilephone -> stays at the flat csv 80 -----

test("D-72-22 negative: without source_by_field naming mobilephone, a CSV mobile stays at the flat csv confidence and never reaches HubSpot Create", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const email = "noprovenance@" + DOMAIN;
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email, firstname: "No", lastname: "Provenance", company: "Widened Fields Co",
        mobilephone: "+61455555555" },
      // No `body.source_by_field` at all on this batch's item[0] — the round-level map
      // is genuinely absent, not merely empty for this one field.
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email, status: "VALID" }] }],
      "HubSpot Search by Email": [{ results: [] }], // net_new
      "HubSpot Company Search by Domain": [{ results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
      "HubSpot Create": (items) => items.map((it) => ({ id: "666666", properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const merged = nodeItems(runData, "Merge Contacts");
  assert.equal(merged.length, 1);
  const decision = (merged[0].merge.decisions || []).find((d) => d.field === "mobilephone");
  assert.ok(decision, "mobilephone must still be a candidate field even though it cannot promote");
  assert.equal(decision.decision, "needs_review",
    "flat csv confidence (80) is below mobilephone's fill_blank_only threshold (85) — the ruling's csv-typed-stays-untrusted half");
  assert.equal(decision.confidence, 80, "no source_by_field entry -> the flat csv confidence, never the provider grade");

  const createRows = nodeItems(runData, "HubSpot Create");
  assert.equal(createRows.length, 1);
  assert.equal(
    Object.prototype.hasOwnProperty.call(createRows[0].properties, "mobilephone"),
    false,
    "a needs_review field must never reach the HubSpot Create body"
  );
});

// --- Task 2: pin what existingProps now changes for the seven keys that predate this
// plan --------------------------------------------------------------------------------
//
// Task 1 turned a lane that never gated into one that does. This pins the resulting
// behavior for every pre-existing candidate key, so a later plan cannot regress it
// silently and so the operator sees exactly what changed. F71-5's "provider jobtitle
// replaced the CSV jobtitle" happened in the PLUGIN's merge_enriched, not on this lane —
// the lane promoted jobtitle only because it merged against an empty existing-props
// object (71-UAT.md). With real existing props, a differing non-blank jobtitle now
// routes to review instead of applying, until plan 04's TTL branch lands.

const ROW_D_EMAIL = "differing@" + DOMAIN;
const ROW_D_CONTACT_ID = "444";

function existingFieldsFixture() {
  return {
    triggerItems: [
      { email: ROW_D_EMAIL, firstname: "CsvFirst", lastname: "CsvLast",
        company: "Widened Fields Co", jobtitle: "CSV Title", phone: "0400111222" },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: ROW_D_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{
        results: [{ id: ROW_D_CONTACT_ID, properties: {
          email: ROW_D_EMAIL, firstname: "HsFirst", lastname: "HsLast",
          jobtitle: "HS Title", phone: "+61400999888",
        } }],
      }],
      "HubSpot Contact History": [{ propertiesWithHistory: {} }],
      "HubSpot Company Search by Domain": [{ results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  };
}

test("existingProps gate: phone/firstname/lastname/jobtitle/email all stay off an update body once HubSpot holds different non-blank values", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const fixture = existingFieldsFixture();
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: fixture.triggerItems,
    httpStubs: fixture.httpStubs,
  });

  assert.deepEqual(starvedWithData(trace), []);

  const merged = nodeItems(runData, "Merge Contacts");
  assert.equal(merged.length, 1);
  const decisions = merged[0].merge.decisions || [];
  const decisionFor = (field) => decisions.find((d) => d.field === field);

  assert.equal(decisionFor("phone").decision, "stage_only",
    "phone: fill_blank_only @ 80, protect_if_current_present true -- a differing non-blank existing value must not be overwritten");
  assert.equal(decisionFor("firstname").decision, "stage_only",
    "firstname: no config/field_policy.yaml entry -- the engines' fill_blank_only/80 default now protects a non-blank existing value too");
  assert.equal(decisionFor("lastname").decision, "stage_only",
    "lastname: same fill_blank_only/80 default as firstname");
  assert.equal(decisionFor("jobtitle").decision, "needs_review",
    "jobtitle: stale_refreshable pre-TTL -- blank existing -> promote, else -> needs_review (not the plugin's own refreshable_keys rule, which never reaches this lane)");
  assert.equal(decisionFor("email").decision, "stage_only",
    "email: fill_blank_only @ 80 -- the row's own match key, already non-blank on every matched row");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(updateRows.length, 1);
  const properties = updateRows[0].properties;
  for (const field of ["phone", "firstname", "lastname", "jobtitle", "email"]) {
    assert.equal(
      Object.prototype.hasOwnProperty.call(properties, field),
      false,
      `${field} must not appear in the update body once existingProps protects it`
    );
  }
});

// --- Plan 02 Task 1: the remaining seven widened keys (D-72-01) --------------------------
//
// Mirrors the Task 1 <behavior>: a net_new row with all seven values produces a Create body
// carrying all seven; a matched row whose HubSpot contact already holds different non-blank
// values withholds the five fill_blank_only location keys but STILL promotes the two
// system_owned keys (seniority, lv_persona_group — mergeContacts.js's _gate never consults
// currentValue for system_owned, only the confidence threshold).

const WIDENED_VALUES = {
  city: "Sydney", state: "NSW", country: "Australia",
  hs_state_code: "NSW", hs_country_region_code: "AU",
  seniority: "Director", lv_persona_group: "marketing",
};
const WIDENED_KEYS = Object.keys(WIDENED_VALUES);
const LOCATION_KEYS = ["city", "state", "country", "hs_state_code", "hs_country_region_code"];
const SYSTEM_OWNED_KEYS = ["seniority", "lv_persona_group"];

test("a CSV column headed 'persona group'/'state/region'/'country code' etc. maps to the new widened canonical keys", () => {
  assert.deepEqual(mapRow({ "Persona Group": "marketing" }), { lv_persona_group: "marketing" });
  assert.deepEqual(mapRow({ "State/Region": "NSW" }), { state: "NSW" });
  assert.deepEqual(mapRow({ "Country Code": "AU" }), { hs_country_region_code: "AU" });
  assert.deepEqual(mapRow({ "Seniority Level": "Director" }), { seniority: "Director" });
  // A header outside the table is still dropped.
  assert.deepEqual(mapRow({ Notes: "irrelevant" }), {});
});

const ROW_F_EMAIL = "widenextras@" + DOMAIN; // net_new -> all seven must reach Create

test("D-72-01: the remaining seven widened keys reach HubSpot Create for a net_new row", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: ROW_F_EMAIL, firstname: "Widen", lastname: "Extras", company: "Widened Fields Co",
        ...WIDENED_VALUES },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: ROW_F_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{ results: [] }], // net_new
      "HubSpot Company Search by Domain": [{ results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
      "HubSpot Create": (items) => items.map((it) => ({ id: "777777", properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const createRows = nodeItems(runData, "HubSpot Create");
  assert.equal(createRows.length, 1);
  for (const key of WIDENED_KEYS) {
    assert.equal(createRows[0].properties[key], WIDENED_VALUES[key],
      `${key} must reach the HubSpot Create body on a net_new row`);
  }
});

const ROW_G_EMAIL = "widenupdate@" + DOMAIN;
const ROW_G_CONTACT_ID = "888";
const ROW_G_EXISTING = {
  city: "Melbourne", state: "VIC", country: "Australia",
  hs_state_code: "VIC", hs_country_region_code: "AU",
  seniority: "Manager", lv_persona_group: "sales",
};

test("D-72-01: the five location keys are withheld from an update that already holds different values; the two system_owned keys still promote", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      { email: ROW_G_EMAIL, firstname: "Widen", lastname: "Update", company: "Widened Fields Co",
        ...WIDENED_VALUES },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: ROW_G_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{
        results: [{ id: ROW_G_CONTACT_ID, properties: { email: ROW_G_EMAIL, ...ROW_G_EXISTING } }],
      }],
      "HubSpot Contact History": [{ propertiesWithHistory: {} }],
      "HubSpot Company Search by Domain": [{ results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const merged = nodeItems(runData, "Merge Contacts");
  assert.equal(merged.length, 1);
  const decisions = merged[0].merge.decisions || [];
  const decisionFor = (field) => decisions.find((d) => d.field === field);

  for (const key of LOCATION_KEYS) {
    assert.equal(decisionFor(key).decision, "stage_only",
      `${key}: fill_blank_only with a differing non-blank existing value must not clobber`);
  }
  for (const key of SYSTEM_OWNED_KEYS) {
    assert.equal(decisionFor(key).decision, "promote",
      `${key}: system_owned promotes on confidence alone, regardless of the existing value`);
  }

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(updateRows.length, 1);
  const properties = updateRows[0].properties;
  for (const key of LOCATION_KEYS) {
    assert.equal(Object.prototype.hasOwnProperty.call(properties, key), false,
      `${key} must not appear in the update body — existingProps protects it`);
  }
  for (const key of SYSTEM_OWNED_KEYS) {
    assert.equal(properties[key], WIDENED_VALUES[key],
      `${key} must land with the CSV's new value even though HubSpot already held a different one`);
  }
});

// --- Plan 02 Task 2: hs_linkedin_url lands as a SECOND write target (D-72-04) ------------

const LINKEDIN_URL = "https://www.linkedin.com/in/widenedfields";
const ROW_H_EMAIL = "linkedinboth@" + DOMAIN; // net_new -> both targets must reach Create

test("D-72-04: a linkedin_url header value produces a Create body carrying BOTH lv_linkedin_url and hs_linkedin_url", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      {
        body: { source_by_field: { lv_linkedin_url: "apollo", hs_linkedin_url: "apollo" } },
        email: ROW_H_EMAIL, firstname: "Linked", lastname: "InBoth", company: "Widened Fields Co",
        linkedin_url: LINKEDIN_URL,
      },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: ROW_H_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{ results: [] }], // net_new
      "HubSpot Company Search by Domain": [{ results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
      "HubSpot Create": (items) => items.map((it) => ({ id: "888888", properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const createRows = nodeItems(runData, "HubSpot Create");
  assert.equal(createRows.length, 1);
  assert.equal(createRows[0].properties.lv_linkedin_url, LINKEDIN_URL,
    "the canonical PN-1 target must still land (D-72-04 is additive, not a replacement)");
  assert.equal(createRows[0].properties.hs_linkedin_url, LINKEDIN_URL,
    "the native portal property must now land from the same value");
});

const ROW_I_EMAIL = "linkedinupdate@" + DOMAIN;
const ROW_I_CONTACT_ID = "999";
const ROW_I_EXISTING_LINKEDIN = "https://www.linkedin.com/in/someone-else";

test("D-72-04: hs_linkedin_url is withheld from an update whose contact already holds a different non-blank value", () => {
  const wf = loadArmedWorkflow({ testRecordDomains: DOMAIN });
  const { runData, trace } = walkWorkflow(wf, {
    triggerNode: "Webhook Trigger",
    triggerItems: [
      {
        body: { source_by_field: { lv_linkedin_url: "apollo", hs_linkedin_url: "apollo" } },
        email: ROW_I_EMAIL, firstname: "Linked", lastname: "InUpdate", company: "Widened Fields Co",
        linkedin_url: LINKEDIN_URL,
      },
    ],
    httpStubs: {
      "Verify Emails (batch)": [{ results: [{ email: ROW_I_EMAIL, status: "VALID" }] }],
      "HubSpot Search by Email": [{
        results: [{ id: ROW_I_CONTACT_ID, properties: {
          email: ROW_I_EMAIL, hs_linkedin_url: ROW_I_EXISTING_LINKEDIN,
        } }],
      }],
      "HubSpot Contact History": [{ propertiesWithHistory: {} }],
      "HubSpot Company Search by Domain": [{ results: [{ id: COMPANY_ID, properties: { domain: DOMAIN } }] }],
      "HubSpot Company Search by Name": [{ results: [] }],
      "HubSpot Update": (items) => items.map((it) => ({ id: it.hs_object_id, properties: it.properties })),
      "HubSpot Associate Company": (items) => items.map(() => ({ status: "ok" })),
    },
  });

  assert.deepEqual(starvedWithData(trace), []);

  const merged = nodeItems(runData, "Merge Contacts");
  assert.equal(merged.length, 1);
  const decisions = merged[0].merge.decisions || [];
  const decisionFor = (field) => decisions.find((d) => d.field === field);
  assert.equal(decisionFor("hs_linkedin_url").decision, "stage_only",
    "fill_blank_only with a differing non-blank existing value must not clobber");

  const updateRows = nodeItems(runData, "HubSpot Update");
  assert.equal(updateRows.length, 1);
  assert.equal(
    Object.prototype.hasOwnProperty.call(updateRows[0].properties, "hs_linkedin_url"),
    false,
    "hs_linkedin_url must not appear in the update body once existingProps protects it"
  );
});
