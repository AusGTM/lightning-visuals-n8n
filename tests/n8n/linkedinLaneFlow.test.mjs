// tests/n8n/linkedinLaneFlow.test.mjs
//
// Phase 61 Plan 02 (D-61-05 CORRECTED). The exact walk-failure row —
// `https://www.linkedin.com/in/robert-cavallucci-14698741/`, no other fields — must route
// to a `linkedin` lane, reach a HubSpot search node, and come back with a verdict that is
// not "could not look". This file pins that end to end against the committed
// wf_enrichment_cloud.json, mirroring companyNameFallbackFlow.test.mjs's node-execution
// idiom (evaluate the repo's OWN built jsCode via `new Function`, mock only HTTP nodes).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const wf = JSON.parse(fs.readFileSync(path.join(ROOT, "n8n", "wf_enrichment_cloud.json"), "utf8"));

const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};

// runNode(nodeName, buildIdentityRows, extraOutputs) — evaluates the named Code node's
// OWN committed jsCode. `extraOutputs` supplies whatever other node this Code node reads
// by name (HubSpot search envelopes, the name lane's fallback search, etc).
function runNode(nodeName, buildIdentityRows, extraOutputs) {
  const outputs = { "Build Identity": buildIdentityRows, ...(extraOutputs || {}) };
  const $ = (name) => {
    if (!(name in outputs)) throw new Error(`no node named ${name}`);
    return { all: () => outputs[name].map((j) => ({ json: j })) };
  };
  const fn = new Function("$", `"use strict";\n${node(nodeName).parameters.jsCode}`);
  return (fn($) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

const envelope = (hits) => ({ total: hits.length, results: hits });

// runBuildIdentity(row) — evaluates the committed "Build Identity" jsCode for real, so the
// variant-set tests below exercise the ACTUAL emitted `linkedin_url_variants` (Task 2),
// not a hand-rolled stand-in.
function runBuildIdentity(row) {
  const $input = { all: () => [{ json: row }] };
  const fn = new Function("$input", `"use strict";\n${node("Build Identity").parameters.jsCode}`);
  return fn($input)[0].json;
}

// =============================================================================================
// Wiring: the linkedin lane sits between "IF Has Email" and "IF Name Searchable", and its
// own search->adapter chain feeds "Enrichment Gate" like every other lane.
// =============================================================================================

test("the linkedin lane sits between IF Has Email and IF Name Searchable, and its adapter feeds Enrichment Gate", () => {
  const edge = (from, i = 0) => (wf.connections[from]?.main?.[i] || []).map((c) => c.node);
  assert.deepEqual(edge("IF Has Email", 0), ["HubSpot Search"]);
  assert.deepEqual(edge("IF Has Email", 1), ["IF Linkedin Searchable"]);
  assert.deepEqual(edge("IF Linkedin Searchable", 0), ["HubSpot Linkedin Search"]);
  assert.deepEqual(edge("IF Linkedin Searchable", 1), ["IF Name Searchable"]);
  assert.deepEqual(edge("HubSpot Linkedin Search"), ["Adapt Linkedin Search"]);
  assert.deepEqual(edge("Adapt Linkedin Search"), ["Enrichment Gate"]);
  // "IF Name Searchable"'s own true/false targets are unchanged by this splice.
  assert.deepEqual(edge("IF Name Searchable", 0), ["HubSpot Name Search"]);
  assert.deepEqual(edge("IF Name Searchable", 1), ["Enrichment Gate"]);
});

test("HubSpot Linkedin Search is the credential-bound httpRequest transport, never the native node (BUG 23/10 lesson)", () => {
  assert.equal(node("HubSpot Linkedin Search").type, "n8n-nodes-base.httpRequest");
});

// =============================================================================================
// Adapt Linkedin Search — the exact walk-failure row, isolated
// =============================================================================================

const WALK_FAILURE_URL = "https://www.linkedin.com/in/robert-cavallucci-14698741/";

test("the exact walk-failure row (a LinkedIn URL and nothing else) reaches a tier other than unknown on a hit", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "9001", properties: { lv_linkedin_url: WALK_FAILURE_URL, firstname: "Robert", lastname: "Cavallucci" } },
    ])],
  });
  assert.notEqual(row.match.tier, "unknown");
  assert.equal(row.match.tier, "high");
  assert.equal(row.match.auto, true);
  assert.equal(row.existingRecord.hs_object_id, "9001");
});

test("the exact walk-failure row on a zero-hit search is none, not unknown — the search ran", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([])],
  });
  assert.equal(row.match.tier, "none");
  assert.deepEqual(row.existingRecord, {});
});

test("a failed linkedin search is unknown, and the row is never created off it", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [{ error: "ECONNRESET" }],
  });
  assert.equal(row.match.tier, "unknown");
  assert.equal(row.lookup_failed, true);
  assert.deepEqual(row.existingRecord, {});
});

test("two verified linkedin hits is ambiguity, never a pick — medium with both candidates, auto false", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "1", properties: { lv_linkedin_url: WALK_FAILURE_URL } },
      { id: "2", properties: { hs_linkedin_url: WALK_FAILURE_URL } },
    ])],
  });
  assert.equal(row.match.tier, "medium");
  assert.equal(row.match.auto, false);
  assert.equal(row.match.candidates.length, 2);
  assert.deepEqual(row.existingRecord, {});
});

// =============================================================================================
// THE DECISIVE TEST: a mixed batch (email + linkedin-only + name-only rows in ONE request)
// gets exactly one response item per row_id, and the linkedin row's tier is never unknown —
// the failure this phase exists to stop, in the shape it would take.
// =============================================================================================

test("mixed batch: an email row, a linkedin-only row and a name-only row each produce exactly one item, and the linkedin row is never unknown", () => {
  const rows = [
    { row_id: "row-email", identity_keys: { email: "jane@example.com" }, lane: "email" },
    { row_id: "row-linkedin", identity_keys: { linkedin_url: WALK_FAILURE_URL }, lane: "linkedin" },
    { row_id: "row-name", identity_keys: { lastName: "Doe", companyName: "Gold Coast Turf Club" }, lane: "name" },
  ];

  const emailOut = runNode("Adapt Search", rows, {
    "HubSpot Search": [envelope([{ id: "100", properties: { email: "jane@example.com" } }])],
  });
  const linkedinOut = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([{ id: "9001", properties: { lv_linkedin_url: WALK_FAILURE_URL } }])],
  });
  const nameOut = runNode("Adapt Name Search", rows, {
    "HubSpot Name Search": [envelope([
      { id: "300", properties: { lastname: "Doe", company: "Gold Coast Turf Club" } },
    ])],
    "HubSpot Name Search Fallback": [],
  });

  // 36-CONTEXT.md Finding A: each adapter filters to ITS OWN lane before index-aligning —
  // exactly one output row per adapter here, none dropped, none duplicated.
  assert.equal(emailOut.length, 1);
  assert.equal(linkedinOut.length, 1);
  assert.equal(nameOut.length, 1);

  const byRowId = {};
  for (const r of [...emailOut, ...linkedinOut, ...nameOut]) {
    assert.ok(!(r.row_id in byRowId), `row_id ${r.row_id} produced more than one response item`);
    byRowId[r.row_id] = r;
  }
  assert.deepEqual(Object.keys(byRowId).sort(), ["row-email", "row-linkedin", "row-name"]);

  // The decisive assertion: the linkedin row's tier is not "unknown" — it dead-ends nowhere.
  assert.notEqual(byRowId["row-linkedin"].match.tier, "unknown");
  assert.equal(byRowId["row-linkedin"].match.tier, "high");
});

// =============================================================================================
// Task 2 (REVIEW-01/REVIEW-C5): the search survives stored-value variance. The WRITTEN-DOWN
// variant set is pinned here — "Build Identity" computes it, "HubSpot Linkedin Search"
// consumes it via `$json.linkedin_url_variants` (two `IN` groups, never a cross-product).
// =============================================================================================

test("the linkedin search filter is exactly two IN groups over identity_keys.linkedin_url_variants — never a variant x property cross-product (REVIEW-C5)", () => {
  const body = node("HubSpot Linkedin Search").parameters.jsonBody;
  const groupCount = (body.match(/filters: \[/g) || []).length;
  assert.equal(groupCount, 2, `expected exactly 2 filter groups, body was: ${body}`);
  assert.match(body, /propertyName: "lv_linkedin_url", operator: "IN", values: \$json\.linkedin_url_variants/);
  assert.match(body, /propertyName: "hs_linkedin_url", operator: "IN", values: \$json\.linkedin_url_variants/);
  assert.doesNotMatch(body, /CONTAINS_TOKEN/, "CONTAINS_TOKEN on a URL-valued property is [unknown] offline — not adopted (REVIEW-01)");
});

test("the covered variant set: canonical form, raw input as given, and the trailing-slash/www./scheme combinations of the canonical form", () => {
  const out = runBuildIdentity({ linkedin_url: "https://www.linkedin.com/in/robert-cavallucci-14698741/" });
  const variants = out.linkedin_url_variants;
  assert.ok(Array.isArray(variants) && variants.length > 0 && variants.length <= 9,
    "the variant set is a BOUNDED promise, not unlimited normalization tolerance");
  for (const v of [
    "https://linkedin.com/in/robert-cavallucci-14698741",
    "https://linkedin.com/in/robert-cavallucci-14698741/",
    "https://www.linkedin.com/in/robert-cavallucci-14698741",
    "https://www.linkedin.com/in/robert-cavallucci-14698741/",
    "http://linkedin.com/in/robert-cavallucci-14698741",
    "http://www.linkedin.com/in/robert-cavallucci-14698741/",
  ]) {
    assert.ok(variants.includes(v), `variant set is missing ${v}`);
  }
});

test("a bare linkedin_url still yields the raw-input variant even when it is not one of the 8 structural combinations", () => {
  const out = runBuildIdentity({ linkedin_url: "https://linkedin.com/in/x?trk=public_profile" });
  assert.ok(out.linkedin_url_variants.includes("https://linkedin.com/in/x?trk=public_profile"),
    "the raw operator-supplied value as given is always in the set, per the written-down promise");
});

test("no linkedin_url at all yields an empty, never undefined, variant array", () => {
  const out = runBuildIdentity({});
  assert.deepEqual(out.linkedin_url_variants, []);
});

// --- stored-value variance: the RE-VERIFICATION (canonicalize both sides), pinned through
// the real "Adapt Linkedin Search" adapter, not just the unit-level matchProposal helpers ---

test("a stored value differing only in trailing slash still matches the operator's input, through the real adapter", () => {
  const rows = [{
    row_id: "r1",
    identity_keys: { linkedin_url: "https://www.linkedin.com/in/robert-cavallucci-14698741" },
    lane: "linkedin",
  }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "9001", properties: { lv_linkedin_url: "https://www.linkedin.com/in/robert-cavallucci-14698741/" } },
    ])],
  });
  assert.equal(row.match.tier, "high");
  assert.equal(row.existingRecord.hs_object_id, "9001");
});

test("a stored value with a query string matches an input without one, through the real adapter", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: "https://linkedin.com/in/x" }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "1", properties: { lv_linkedin_url: "https://linkedin.com/in/x?trk=public_profile" } },
    ])],
  });
  assert.equal(row.match.tier, "high");
});

test("a different profile under the same host does NOT match, through the real adapter (false positive here writes to the wrong person)", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: "https://linkedin.com/in/x" }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "1", properties: { lv_linkedin_url: "https://linkedin.com/in/someone-else" } },
    ])],
  });
  assert.equal(row.match.tier, "none");
  assert.deepEqual(row.existingRecord, {});
});

test("a contact stored ONLY under native hs_linkedin_url is found, not missed into a duplicate create (REVIEW-02)", () => {
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: "https://linkedin.com/in/x" }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([
      { id: "1", properties: { hs_linkedin_url: "https://linkedin.com/in/x" } },
    ])],
  });
  assert.equal(row.match.tier, "high");
  assert.equal(row.existingRecord.hs_object_id, "1");
});

test("a stored form outside the written-down variant set is a known miss — tier none, not guessed", () => {
  // A stored value that is neither the raw input nor any of the 8 structural combinations
  // (a completely different subdomain) would never be returned by the live search — this
  // pins the DECLARED miss, not a live behaviour: the mock search simply returns nothing,
  // exactly as HubSpot would for an IN filter none of whose variants match.
  const rows = [{ row_id: "r1", identity_keys: { linkedin_url: "https://linkedin.com/in/x" }, lane: "linkedin" }];
  const [row] = runNode("Adapt Linkedin Search", rows, {
    "HubSpot Linkedin Search": [envelope([])],
  });
  assert.equal(row.match.tier, "none");
  assert.notEqual(row.match.tier, "unknown", "a known miss is `none` (searched, no hit), never `unknown` (could not look)");
});
