// Functional/e2e regression for the Phase 16.4 fetch-by-objectId lane (SC-5 e2e tier).
//
// Every existing row-flow test in this repo (researchChainRowFlow.test.mjs,
// contactResearchChainRowFlow.test.mjs) seeds its fixture AFTER identity resolution, with
// identity_keys already populated. This is the FIRST test to drive a payload from the raw
// webhook body through `Parse HubSpot Event` — the one hop earlier than the harness has
// ever gone — proving that a GENUINE bare HubSpot event (objectId/objectType only, no
// email/domain/name) reaches a populated identity via the new fetch-by-id lane, not the
// old empty-identity shim.
//
// NOTE: this executes the repo's OWN committed workflow jsCode via `new Function` — the
// same thing n8n's Code node does at runtime — over a fixed, in-repo list of node names.
// No external or untrusted input is ever interpolated into the function body. IF/Set
// nodes are NOT in the driven list: the harness executes Code nodes and mocks HTTP nodes,
// modelling exactly the lane under test (the same idiom researchChainRowFlow.test.mjs
// already uses).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function runChain(wfPath, chainSpec, seedBody, httpMocks) {
  const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;

  const outputs = {};

  const makeCtx = (current) => {
    const $ = (name) => ({
      all: () => (outputs[name] || []).map((j) => ({ json: j })),
      get item() { return { json: (outputs[name] || [])[0] }; },
    });
    const $input = {
      all: () => current.map((j) => ({ json: j })),
      get item() { return { json: current[0] }; },
    };
    return { $, $input, $json: current[0] };
  };

  let items = [{ body: seedBody }];
  const trace = {};
  let threw = null;
  for (const step of chainSpec) {
    const node = byName[step.name];
    assert.ok(node, `node present in built workflow: ${step.name}`);
    if (step.http) {
      items = [httpMocks[step.name] || {}];
      outputs[step.name] = items;
      continue;
    }
    const { $, $input, $json } = makeCtx(items);
    const $now = new Date("2026-07-28T00:00:00Z");
    const fn = new Function("$", "$input", "$json", "$node", "$now", "$today",
      `"use strict";\n${node.parameters.jsCode}`);
    try {
      const out = fn($, $input, $json, {}, $now, $now) || [];
      items = out.map((it) => (it && it.json !== undefined ? it.json : it));
    } catch (e) { threw = { node: step.name, err: e.message }; break; }
    outputs[step.name] = items;
    trace[step.name] = items[0] || {};
  }
  return { trace, threw, final: items[0] || {} };
}

// --- contacts: a bare event carrying NO email/firstname/lastname/company -------------
const CONTACT_SEED_BODY = {
  providers: ["lusha", "apollo"],
  events: [{
    objectId: 789, objectType: "contact",
    subscriptionType: "contact.propertyChange",
    propertyName: "lv_enrichment_requested",
    occurredAt: 1783316400000,
  }],
};

const CONTACT_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Identity", http: false },
  { name: "HubSpot Fetch By Id", http: true },
  { name: "Adapt Fetch By Id", http: false },
  { name: "Enrichment Gate", http: false },
  { name: "Lusha Enrich", http: true },
  { name: "Apollo Match", http: true },
  { name: "Normalize + Score", http: false },
  { name: "Merge Winners", http: false },
  { name: "Decide Action", http: false },
];

const CONTACT_HTTP_MOCKS = {
  // Deliberately WITHOUT mobilephone, so decideAction returns "enrich" (a REQUIRED field
  // is missing) rather than "skip" — the run continues past the gate deterministically.
  "HubSpot Fetch By Id": {
    results: [{
      id: "789",
      properties: {
        email: "riley.chen@exampleracing.example",
        firstname: "Riley",
        lastname: "Chen",
        jobtitle: "Ops Manager",
        company: "Example Racing League",
        lv_linkedin_url: "https://linkedin.com/in/riley-chen",
      },
    }],
    total: 1,
  },
  "Lusha Enrich": {},
  "Apollo Match": {},
};

test("contacts: a bare HubSpot event drives the full compiled chain to a patch payload targeting the fetched record id", () => {
  const { trace, threw, final } = runChain(WF_PATH, CONTACT_CHAIN, CONTACT_SEED_BODY, CONTACT_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);

  // (b) SC-2 payoff: non-null identity_keys.email, impossible without the fetch feeding
  // the backfill — the seed body carries no email anywhere.
  const adapted = trace["Adapt Fetch By Id"];
  assert.ok(adapted, "Adapt Fetch By Id produced output");
  assert.notEqual(adapted.identity_keys && adapted.identity_keys.email, null,
    "identity_keys.email is non-null, backfilled from the fetched record");
  assert.equal(adapted.identity_keys.email, "riley.chen@exampleracing.example");

  // (c) the row survives the fetch-by-id hop: object_id/object_type/provider_enabled/
  // providers_requested all carried through from Parse HubSpot Event.
  assert.equal(adapted.object_id, "789");
  assert.equal(adapted.object_type, "contacts");
  assert.ok(adapted.provider_enabled && typeof adapted.provider_enabled === "object",
    "provider_enabled survived the hop");
  assert.ok(Array.isArray(adapted.providers_requested) && adapted.providers_requested.length > 0,
    "providers_requested survived the hop and is non-empty");

  // (d) the gate sees the fetched record and correctly demands enrichment (missing
  // mobilephone), not skip/create.
  assert.equal(trace["Enrichment Gate"].action, "enrich");

  // (e) Decide Action's final output targets the REAL fetched record id, and is
  // write_blocked — the correct offline expectation (WRITE_SAFETY_DEFAULTS ships every
  // allowlist empty).
  assert.equal(final.hs_object_id, "789");
  assert.equal(final.action, "write_blocked");
  assert.ok(final.properties && typeof final.properties === "object" && !Array.isArray(final.properties),
    "properties is a plain object");
});

// --- companies: a bare event carrying NO domain/name -----------------------------------
const COMPANY_SEED_BODY = {
  providers: ["lusha", "apollo"],
  events: [{
    objectId: 4567, objectType: "company",
    subscriptionType: "company.propertyChange",
    propertyName: "lv_enrichment_requested",
    occurredAt: 1783316400000,
  }],
};

// DELIBERATELY excludes the research/judge chain (Research Trigger Gate -> IF Research
// Needed -> ... -> Merge Company): the harness runs every listed node unconditionally
// regardless of the IF branching n8n itself evaluates, and the research/judge lane's
// false lanes fan straight into "Merge Company" anyway — this list drives exactly that
// lane, never the cost-cap/escalation lane the real workflow would gate behind a live
// research call.
const COMPANY_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Company Identity", http: false },
  { name: "HubSpot Company Fetch By Id", http: true },
  { name: "Adapt Company Fetch By Id", http: false },
  { name: "Company Gate", http: false },
  { name: "Build Company Requests", http: false },
  { name: "Lusha Company", http: true },
  { name: "Apollo Org", http: true },
  { name: "Normalize + Score Company", http: false },
  { name: "Merge Company", http: false },
  { name: "Decide Company Action", http: false },
];

const COMPANY_HTTP_MOCKS = {
  // Deliberately WITHOUT lv_org_type/lv_produces_content, so decideAction sees missing
  // REQUIRED fields and returns "enrich" rather than "skip".
  "HubSpot Company Fetch By Id": {
    results: [{
      id: "4567",
      properties: {
        name: "Example Racing League",
        domain: "exampleracing.example",
      },
    }],
    total: 1,
  },
  "Lusha Company": {},
  "Apollo Org": {},
};

test("companies: a bare HubSpot event drives the full compiled chain to a patch payload targeting the fetched record id", () => {
  const { trace, threw, final } = runChain(WF_PATH, COMPANY_CHAIN, COMPANY_SEED_BODY, COMPANY_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);

  // SC-2 payoff: non-null identity_keys.domain, impossible without the fetch feeding the
  // backfill — the seed body carries no domain anywhere.
  const adapted = trace["Adapt Company Fetch By Id"];
  assert.ok(adapted, "Adapt Company Fetch By Id produced output");
  assert.notEqual(adapted.identity_keys && adapted.identity_keys.domain, null,
    "identity_keys.domain is non-null, backfilled from the fetched record");
  assert.equal(adapted.identity_keys.domain, "exampleracing.example");

  // row survives the fetch-by-id hop.
  assert.equal(adapted.object_id, "4567");
  assert.equal(adapted.object_type, "companies");
  assert.ok(adapted.provider_enabled && typeof adapted.provider_enabled === "object",
    "provider_enabled survived the hop");
  assert.ok(Array.isArray(adapted.providers_requested) && adapted.providers_requested.length > 0,
    "providers_requested survived the hop and is non-empty");

  // the gate sees the fetched record and correctly demands enrichment (missing
  // lv_org_type/lv_produces_content), not skip/create.
  assert.equal(trace["Company Gate"].action, "enrich");

  // Decide Company Action's final output targets the REAL fetched record id.
  assert.equal(final.hs_object_id, "4567");
  assert.ok(final.properties && typeof final.properties === "object" && !Array.isArray(final.properties),
    "properties is a plain object");
});

// =========================================================================================
// Phase 16.4-02 Task 1 — INTEGRATION tier: dedicated row-flow regression, caller-envelope
// back-compat, safe degradation, and the true live plain-array payload shape. SC-3/SC-4/SC-6.
// =========================================================================================

// --- (2) ROW-FLOW REGRESSION: a dedicated, minimal chain stopping right after the adapter,
// so a red here points at exactly one thing — the bd682a2 bug class (a post-HTTP Code node
// reading the current item instead of recovering the row BY NODE NAME). Reuses the same seed
// body/mocks as the main e2e test above; this is a NARROWER, purpose-built assertion, not a
// duplicate of it. ------------------------------------------------------------------------

const CONTACT_ROW_FLOW_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Identity", http: false },
  { name: "HubSpot Fetch By Id", http: true },
  { name: "Adapt Fetch By Id", http: false },
];

test("contacts row-flow (bd682a2 bug class): object_id, object_type, provider_enabled and a non-empty providers_requested all survive the HTTP hop via node-name recovery", () => {
  const { trace, threw } = runChain(WF_PATH, CONTACT_ROW_FLOW_CHAIN, CONTACT_SEED_BODY, CONTACT_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Fetch By Id"];
  assert.equal(adapted.object_id, "789",
    "bd682a2 regression: object_id did not survive the fetch hop — the adapter is reading the current item, not the pre-hop row by node name");
  assert.equal(adapted.object_type, "contacts",
    "bd682a2 regression: object_type did not survive the fetch hop");
  assert.deepEqual(adapted.provider_enabled, { lusha: true, apollo: true, zoominfo: false },
    "bd682a2 regression: provider_enabled did not survive the fetch hop");
  assert.deepEqual(adapted.providers_requested, ["lusha", "apollo"],
    "bd682a2 regression: providers_requested must be the EXACT non-empty array the envelope requested — a dropped-then-defaulted empty array is the silent failure this guards against");
});

const COMPANY_ROW_FLOW_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Company Identity", http: false },
  { name: "HubSpot Company Fetch By Id", http: true },
  { name: "Adapt Company Fetch By Id", http: false },
];

test("companies row-flow (bd682a2 bug class): object_id, object_type, provider_enabled and a non-empty providers_requested all survive the HTTP hop via node-name recovery", () => {
  const { trace, threw } = runChain(WF_PATH, COMPANY_ROW_FLOW_CHAIN, COMPANY_SEED_BODY, COMPANY_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Company Fetch By Id"];
  assert.equal(adapted.object_id, "4567",
    "bd682a2 regression: object_id did not survive the fetch hop — the adapter is reading the current item, not the pre-hop row by node name");
  assert.equal(adapted.object_type, "companies",
    "bd682a2 regression: object_type did not survive the fetch hop");
  assert.deepEqual(adapted.provider_enabled, { lusha: true, apollo: true, zoominfo: false },
    "bd682a2 regression: provider_enabled did not survive the fetch hop");
  assert.deepEqual(adapted.providers_requested, ["lusha", "apollo"],
    "bd682a2 regression: providers_requested must be the EXACT non-empty array the envelope requested — a dropped-then-defaulted empty array is the silent failure this guards against");
});

// --- BUG 23 (Phase 17.01) — the no-match case, driven to the write decision ---------------
//
// The http mocks throughout this file already model every HTTP-typed step as exactly ONE
// item, including the 0-result case (`{results: [], total: 0}` below) — that IS the CRM v3
// envelope shape, i.e. what the httpRequest transport this lane now uses actually returns.
// It was NOT always a faithful model: before BUG 23's fix, "HubSpot Search" and "HubSpot
// Fetch By Id" were the native n8n-nodes-base.hubspot node, which — live-established by
// execution 22 (BUG 22, the ingest lane) — emits ZERO items on zero hits, and n8n stops the
// chain there. A one-item `{results:[], total:0}` mock against that native node would have
// been a lie: the equivalent live run would have died before "Adapt Search" ever ran.
// CONTACT_DIRECT_FIELD_CHAIN below already exercises a 0-result "HubSpot Search" mock, but
// only stops at "Enrichment Gate" and asserts identity derivation — it never drives the
// no-match case to a write decision. The precondition assertion and chain below close that
// gap: the offline twin of Plan 02's live case B (a nonexistent email must reach
// action:"create", write-gated).

test("precondition: HubSpot Search and HubSpot Fetch By Id are the httpRequest envelope transport (BUG 23), never the native node", () => {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  for (const name of ["HubSpot Search", "HubSpot Fetch By Id"]) {
    assert.equal(byName[name].type, "n8n-nodes-base.httpRequest",
      `${name} must be the credential-bound httpRequest envelope transport — a native ` +
      "node emits zero items on zero hits (BUG 23/22), which would silently invalidate " +
      "every one-item HTTP mock in this file rather than fail loudly");
  }
});

const CONTACT_NO_MATCH_SEED_BODY = {
  providers: ["lusha", "apollo"],
  events: [{
    objectId: 999, objectType: "contact",
    subscriptionType: "contact.propertyChange",
    email: "lv-bug23-canary-delete-me@lv-canary-delete-me.example",
  }],
};

// CONTACT_CHAIN with the fetch-by-id hop swapped for the direct-search hop — same
// providers/gate/score/merge/decide tail, so a no-match search is driven all the way to
// the write decision instead of stopping at the gate.
const CONTACT_NO_MATCH_CHAIN = CONTACT_CHAIN.map((step) => {
  if (step.name === "HubSpot Fetch By Id") return { name: "HubSpot Search", http: true };
  if (step.name === "Adapt Fetch By Id") return { name: "Adapt Search", http: false };
  return step;
});

const CONTACT_NO_MATCH_HTTP_MOCKS = {
  "HubSpot Search": { results: [], total: 0 },
  "Lusha Enrich": {},
  "Apollo Match": {},
};

test("BUG 23: a no-match search reaches action:create through the gate, write-gated by default (never routed to skip via lookup_failed)", () => {
  const { trace, threw, final } = runChain(
    WF_PATH, CONTACT_NO_MATCH_CHAIN, CONTACT_NO_MATCH_SEED_BODY, CONTACT_NO_MATCH_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);

  const adapted = trace["Adapt Search"];
  assert.equal(adapted.lookup_failed, false,
    "a 0-result search is CONFIRMED-ABSENT, not a lookup failure — getting this backwards " +
    "would route a genuine new contact to skip");
  assert.deepEqual(adapted.existingRecord, {});

  assert.equal(trace["Enrichment Gate"].action, "create",
    "BUG 23: this is the path that was structurally unreachable before the transport swap");

  assert.equal(final.action, "write_blocked",
    "write-gated by default — WRITE_SAFETY_DEFAULTS ships every allowlist empty");
  assert.equal(final.properties.email, "lv-bug23-canary-delete-me@lv-canary-delete-me.example",
    "the BUG 19 create-seed: this chain's Lusha/Apollo mocks are both {}, so the merge " +
    "carries no email candidate at all and canonicalPatch is empty on that field " +
    "regardless of policy (260826-20w T-20w-01) — the create must still seed identity " +
    "directly from identity_keys");
});

// --- (3) CALLER-ENVELOPE BACK-COMPAT: the direct-field envelope the WHOLE existing offline
// suite drives, through the OLD lane only (Build Identity -> HubSpot Search -> Adapt Search).
// The fetch-by-id nodes are not even IN this chain — proof the false lane is byte-for-byte
// untouched by this phase, not merely "not asserted to have changed". --------------------

const CONTACT_ENVELOPE_SEED_BODY = {
  providers: ["lusha"],
  events: [{
    objectId: 321, objectType: "contact",
    subscriptionType: "contact.propertyChange",
    email: "Someone@ExampleCo.example",
  }],
};

const CONTACT_DIRECT_FIELD_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Identity", http: false },
  { name: "HubSpot Search", http: true },
  { name: "Adapt Search", http: false },
  { name: "Enrichment Gate", http: false },
];

test("contacts caller-envelope back-compat: an email in the body resolves identity_keys the OLD way, never touching a fetch node, and providers_requested still resolves from the envelope", () => {
  const { trace, threw } = runChain(WF_PATH, CONTACT_DIRECT_FIELD_CHAIN, CONTACT_ENVELOPE_SEED_BODY,
    { "HubSpot Search": { results: [], total: 0 } });
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Search"];
  // Pre-16.4 ENRICH_BUILD_IDENTITY derivation exactly: normalizeEmailBasic + domain from
  // the email's own domain part (no `domain` field was ever sent in this body).
  assert.deepEqual(adapted.identity_keys, {
    email: "someone@exampleco.example",
    domain: "exampleco.example",
    linkedin_url: null,
    firstName: null,
    lastName: null,
    companyName: null,
  });
  assert.deepEqual(adapted.providers_requested, ["lusha"],
    "the 16.1 per-request providers selection must still resolve from the envelope on this lane");
});

const COMPANY_ENVELOPE_SEED_BODY = {
  providers: ["apollo"],
  events: [{
    objectId: 654, objectType: "company",
    subscriptionType: "company.propertyChange",
    domain: "https://www.ExampleCo.com/about",
  }],
};

const COMPANY_DIRECT_FIELD_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Company Identity", http: false },
  { name: "HubSpot Company Search", http: true },
  { name: "Adapt Company Search", http: false },
  { name: "Company Gate", http: false },
];

test("companies caller-envelope back-compat: a domain in the body resolves identity_keys the OLD way, never touching a fetch node, and providers_requested still resolves from the envelope", () => {
  const { trace, threw } = runChain(WF_PATH, COMPANY_DIRECT_FIELD_CHAIN, COMPANY_ENVELOPE_SEED_BODY,
    { "HubSpot Company Search": { results: [], total: 0 } });
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Company Search"];
  // Pre-16.4 ENRICH_BUILD_CO_IDENTITY derivation exactly: cleanDomain(row.domain).
  assert.deepEqual(adapted.identity_keys, { domain: "exampleco.com", companyName: null });
  assert.deepEqual(adapted.providers_requested, ["apollo"],
    "the 16.1 per-request providers selection must still resolve from the envelope on this lane");
});

// --- (4) SAFE DEGRADATION: a fetch failure (0-results and errored) degrades to
// lookup_failed:true -> action:"skip" through the gate WRAPPER's create->skip override —
// never through the frozen enrichmentGate.js module the unit tier alone can reach. --------

const CONTACT_DEGRADE_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Identity", http: false },
  { name: "HubSpot Fetch By Id", http: true },
  { name: "Adapt Fetch By Id", http: false },
  { name: "Enrichment Gate", http: false },
];

test("contacts safe degradation: a 0-result fetch on a known hs_object_id degrades to lookup_failed and the gate skips (never create)", () => {
  const { trace, threw } = runChain(WF_PATH, CONTACT_DEGRADE_CHAIN, CONTACT_SEED_BODY,
    { "HubSpot Fetch By Id": { results: [], total: 0 } });
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Fetch By Id"];
  assert.equal(adapted.lookup_failed, true);
  assert.match(adapted.fetch_diagnostic, /zero-results/);
  assert.equal(trace["Enrichment Gate"].action, "skip",
    'a 0-result fetch on a KNOWN hs_object_id must degrade to "skip", never "create" (no duplicate-record risk on a server-assigned id)');
});

test("contacts safe degradation: an errored fetch response ALSO degrades to lookup_failed and the gate skips, with a diagnostic distinguishable from the zero-results case", () => {
  const { trace, threw } = runChain(WF_PATH, CONTACT_DEGRADE_CHAIN, CONTACT_SEED_BODY,
    { "HubSpot Fetch By Id": { error: "HubSpot 500: upstream timeout" } });
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Fetch By Id"];
  assert.equal(adapted.lookup_failed, true);
  assert.match(adapted.fetch_diagnostic, /HubSpot 500: upstream timeout/);
  assert.doesNotMatch(adapted.fetch_diagnostic, /zero-results/);
  assert.equal(trace["Enrichment Gate"].action, "skip");
});

const COMPANY_DEGRADE_CHAIN = [
  { name: "Parse HubSpot Event", http: false },
  { name: "Build Company Identity", http: false },
  { name: "HubSpot Company Fetch By Id", http: true },
  { name: "Adapt Company Fetch By Id", http: false },
  { name: "Company Gate", http: false },
];

test("companies safe degradation: a 0-result fetch on a known hs_object_id degrades to lookup_failed and the gate skips (never create)", () => {
  const { trace, threw } = runChain(WF_PATH, COMPANY_DEGRADE_CHAIN, COMPANY_SEED_BODY,
    { "HubSpot Company Fetch By Id": { results: [], total: 0 } });
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Company Fetch By Id"];
  assert.equal(adapted.lookup_failed, true);
  assert.match(adapted.fetch_diagnostic, /zero-results/);
  assert.equal(trace["Company Gate"].action, "skip",
    'a 0-result fetch on a KNOWN hs_object_id must degrade to "skip", never "create" (no duplicate-record risk on a server-assigned id)');
});

// --- (5) THE TRUE LIVE SHAPE: a plain HubSpot event array body — no envelope, no top-level
// `providers` key — is the ONLY payload shape a real private-app webhook subscription can
// ever produce. It must resolve to zero providers enabled (the documented safe default,
// CONTEXT Locked Decision 2) while STILL resolving an identity via the fetch-by-id lane. --

const CONTACT_PLAIN_ARRAY_SEED_BODY = [{
  objectId: 789, objectType: "contact",
  subscriptionType: "contact.propertyChange",
  propertyName: "lv_enrichment_requested",
  occurredAt: 1783316400000,
}];

test("contacts true live shape: a plain HubSpot event array (no envelope) resolves zero providers enabled and STILL resolves identity via the fetch lane", () => {
  const { trace, threw } = runChain(WF_PATH, CONTACT_ROW_FLOW_CHAIN, CONTACT_PLAIN_ARRAY_SEED_BODY, CONTACT_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Fetch By Id"];
  assert.deepEqual(adapted.providers_requested, []);
  assert.deepEqual(adapted.provider_enabled, { lusha: false, apollo: false, zoominfo: false });
  assert.equal(adapted.identity_keys.email, "riley.chen@exampleracing.example",
    "identity still resolves via the fetch backfill even though no provider is enabled");
});

const COMPANY_PLAIN_ARRAY_SEED_BODY = [{
  objectId: 4567, objectType: "company",
  subscriptionType: "company.propertyChange",
  propertyName: "lv_enrichment_requested",
  occurredAt: 1783316400000,
}];

test("companies true live shape: a plain HubSpot event array (no envelope) resolves zero providers enabled and STILL resolves identity via the fetch lane", () => {
  const { trace, threw } = runChain(WF_PATH, COMPANY_ROW_FLOW_CHAIN, COMPANY_PLAIN_ARRAY_SEED_BODY, COMPANY_HTTP_MOCKS);
  assert.equal(threw, null, `no node threw (got: ${JSON.stringify(threw)})`);
  const adapted = trace["Adapt Company Fetch By Id"];
  assert.deepEqual(adapted.providers_requested, []);
  assert.deepEqual(adapted.provider_enabled, { lusha: false, apollo: false, zoominfo: false });
  assert.equal(adapted.identity_keys.domain, "exampleracing.example",
    "identity still resolves via the fetch backfill even though no provider is enabled");
});
