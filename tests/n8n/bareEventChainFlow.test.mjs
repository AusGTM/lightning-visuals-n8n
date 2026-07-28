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
