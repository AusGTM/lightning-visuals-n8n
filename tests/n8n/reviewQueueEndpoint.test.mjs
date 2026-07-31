// tests/n8n/reviewQueueEndpoint.test.mjs
//
// Phase 30 Plan 04 — the read-only `hubspot/review/queue` endpoint (REVIEW-01).
//
// Two sections:
//   (1) STRUCTURE — walks the COMMITTED n8n/wf_review_decision_cloud.json's connection
//       graph FORWARD from `Review Queue Webhook` and asserts no reachable node can
//       mutate a HubSpot record, using the same definition tests/test_write_gate_coverage.py
//       uses. A read endpoint must not be able to become a write endpoint by a later
//       miswiring, and "we did not wire one" is a claim, not a guarantee (T-30-16).
//   (2) BEHAVIOUR — runs the committed nodes' own jsCode through `new Function` the way
//       n8n's Code node runs it: the request parse (what a caller may and may not say)
//       and the row adapter (what reaches the client, byte for byte).
//
// No test here issues a network call, and nothing on this path can be armed — there is no
// write-safety constant on the queue branch because there is no write on it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_review_decision_cloud.json");
const WF = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));

const QUEUE_WEBHOOK = "Review Queue Webhook";
const PARSE = "Parse Review Queue Request";
const ROWS = "Review Queue Rows";

// The `lv_`-prefixed names, pinned here the same way reviewDecisionEndpoint.test.mjs pins
// them: the root CLAUDE.md's unprefixed names are wrong for this deployment (30 D-08c).
const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";
const P_PROVENANCE = "lv_enrichment_provenance";
const P_CONTACT_PROVENANCE = "lv_contact_enrichment_provenance";

function nodeNamed(name) {
  const node = WF.nodes.find((n) => n.name === name);
  assert.ok(node, `node present in the committed workflow: ${name}`);
  return node;
}

function jsCodeOf(name) {
  const node = nodeNamed(name);
  assert.equal(node.type, "n8n-nodes-base.code");
  return node.parameters.jsCode;
}

/** Runs a jsCode body (mode: runOnceForAllItems) the way n8n's Code node runs it.
 * `nodeOutputs` supplies the `$('Node Name')` accessor; a node not listed there throws,
 * so a body silently reaching for an unexpected upstream node fails loudly. */
function runNode(jsCode, seedItems, nodeOutputs) {
  const wrap = (rows) => rows.map((j) => ({ json: j }));
  const $input = {
    all: () => wrap(seedItems),
    first: () => (seedItems.length ? { json: seedItems[0] } : undefined),
  };
  const $ = (name) => {
    assert.ok(nodeOutputs && name in nodeOutputs,
      `jsCode reached for an upstream node this test did not provide: ${name}`);
    const items = wrap(nodeOutputs[name]);
    return { first: () => items[0], all: () => items, item: items[0] };
  };
  const fn = new Function("$input", "$", `"use strict";\n${jsCode}`);
  return (fn($input, $) || []).map((it) => (it && it.json !== undefined ? it.json : it));
}

// =====================================================================================
// (1) STRUCTURE — the queue path cannot write
// =====================================================================================

/** tests/test_write_gate_coverage.py::_is_write_node, transcribed. Kept in step with it
 * deliberately: two definitions of "write node" that disagree would let a node be a write
 * to one guard and not the other. */
function isWriteNode(node) {
  const params = node.parameters || {};
  if (node.type === "n8n-nodes-base.hubspot") {
    return params.operation === "create" || params.operation === "update";
  }
  if (node.type === "n8n-nodes-base.httpRequest") {
    const url = String(params.url || "");
    const method = String(params.method || "").toUpperCase();
    return url.includes("hubapi.com") && !url.includes("/search")
      && ["POST", "PATCH", "PUT"].includes(method);
  }
  return false;
}

function reachableFrom(startName) {
  const seen = new Set([startName]);
  const frontier = [startName];
  while (frontier.length) {
    const name = frontier.pop();
    const spec = WF.connections[name];
    for (const outputs of (spec && spec.main) || []) {
      for (const conn of outputs || []) {
        if (!seen.has(conn.node)) { seen.add(conn.node); frontier.push(conn.node); }
      }
    }
  }
  return seen;
}

test("the workflow really does contain write nodes — so the reachability guard below is not vacuous", () => {
  const writes = WF.nodes.filter(isWriteNode).map((n) => n.name);
  assert.deepEqual(writes.sort(),
    ["Review Contact Decision Update", "Review Decision Update"],
    "if these stop being recognised as writes, the queue guard proves nothing");
});

test("NO write node is reachable from the queue webhook, in any request shape", () => {
  const reachable = reachableFrom(QUEUE_WEBHOOK);
  const writes = WF.nodes.filter((n) => reachable.has(n.name) && isWriteNode(n));
  assert.deepEqual(writes.map((n) => n.name), [],
    "a read endpoint must be structurally incapable of writing (T-30-16)");
});

test("the queue branch reaches neither write gate — not even one that would then deny", () => {
  const reachable = reachableFrom(QUEUE_WEBHOOK);
  const gated = WF.nodes.filter(
    (n) => reachable.has(n.name)
      && String((n.parameters || {}).jsCode || "").includes("_writeSafetyAllows"));
  assert.deepEqual(gated.map((n) => n.name), []);
});

test("the queue branch shares no node with the decision branch, and has its own responder", () => {
  const queue = reachableFrom(QUEUE_WEBHOOK);
  const decision = reachableFrom("Review Decision Webhook");
  const shared = [...queue].filter((n) => decision.has(n));
  assert.deepEqual(shared, [],
    "a responder fed by two independent request paths returns one caller the other's "
    + "body (28 D-14) — the two branches must not converge anywhere");

  const responder = nodeNamed("Respond Review Queue");
  assert.equal(responder.type, "n8n-nodes-base.respondToWebhook");
  // firstIncomingItem, matching D-24: the client parses a dict, never body[0].
  assert.equal(responder.parameters.respondWith, "firstIncomingItem");
  assert.ok(queue.has("Respond Review Queue"), "the queue webhook must reach its responder");
});

test("the queue webhook is POST + headerAuth + responseNode, like every other endpoint here", () => {
  const wh = nodeNamed(QUEUE_WEBHOOK);
  assert.equal(wh.parameters.path, "hubspot/review/queue");
  assert.equal(wh.parameters.httpMethod, "POST");
  assert.equal(wh.parameters.authentication, "headerAuth");
  assert.equal(wh.parameters.responseMode, "responseNode");
  assert.equal(WF.active, false, "committed inactive");
});

test("both queue searches request the detail an operator needs, and only ever hit /search", () => {
  const co = nodeNamed("Review Queue Search");
  const ct = nodeNamed("Review Queue Contact Search");
  for (const n of [co, ct]) {
    assert.ok(String(n.parameters.url).includes("/search"),
      `${n.name} must be a search, not an object endpoint`);
  }
  const coBody = String(co.parameters.jsonBody);
  for (const p of [P_CANDIDATE_JSON, P_PROVENANCE, "lv_icp_tier", "lv_icp_score_breakdown",
                   "lv_anti_icp_reason", "domain", "name"]) {
    assert.ok(coBody.includes(`"${p}"`), `companies queue must request ${p}`);
  }
  // Contacts render from a DIFFERENT set: `lv_contact_enrichment_provenance`, not the
  // companies blob, and no `domain` (30 D-29 — TEST_RECORD_IDS is the only allowlist that
  // can reach a contact). The candidate-JSON property IS requested, because it belongs to
  // the shared review family both lanes use; it is simply never populated on a contact,
  // whose only producer is the companies enrichment lane (30 D-27). The client must
  // therefore treat a contact as candidate-less by EMPTINESS, not by key absence.
  const ctBody = String(ct.parameters.jsonBody);
  assert.ok(ctBody.includes(`"${P_CONTACT_PROVENANCE}"`));
  assert.ok(!ctBody.includes(`"${P_PROVENANCE}"`),
    "the contacts lane must not request the COMPANIES provenance blob");
  assert.ok(!ctBody.includes('"domain"'), "a contact has no domain (30 D-29)");

  // Both lanes OR the same two flags Phase 27's status surface COUNTS with, so the number
  // the operator is told and the list they are handed cannot disagree.
  for (const body of [coBody, ctBody]) {
    assert.ok(body.includes(`"${P_NEEDS_REVIEW}"`) && body.includes(`"${P_ICP_NEEDS_REVIEW}"`));
  }
});

// =====================================================================================
// (2) BEHAVIOUR — the committed nodes' own jsCode
// =====================================================================================

test("Parse Review Queue Request: object_type defaults to companies when absent", () => {
  const [out] = runNode(jsCodeOf(PARSE), [{ body: {} }], {});
  assert.equal(out.object_type, "companies");
  assert.equal(out.limit, 100);
});

test("Parse Review Queue Request: contacts is selectable; any other value reads as companies", () => {
  assert.equal(runNode(jsCodeOf(PARSE), [{ body: { object_type: "contacts" } }], {})[0].object_type,
    "contacts");
  for (const v of ["deals", "COMPANIES", 7, null, { $ne: null }]) {
    assert.equal(runNode(jsCodeOf(PARSE), [{ body: { object_type: v } }], {})[0].object_type,
      "companies", `unrecognised object_type ${JSON.stringify(v)} must fail to companies`);
  }
});

test("Parse Review Queue Request: limit is clamped server-side and never lands on zero", () => {
  const limitOf = (limit) => runNode(jsCodeOf(PARSE), [{ body: { limit } }], {})[0].limit;
  assert.equal(limitOf(25), 25);
  assert.equal(limitOf("25"), 25);
  assert.equal(limitOf(25.9), 25);
  assert.equal(limitOf(5000), 100, "clamped to HubSpot search's own maximum (T-30-19)");
  // A page size of zero would render as an empty queue — the one confusion this endpoint
  // exists to prevent — so every unusable value reads as the maximum, not as nothing.
  for (const v of [0, -1, "abc", null, undefined, {}, []]) {
    assert.equal(limitOf(v), 100, `limit ${JSON.stringify(v)} must read as the maximum`);
  }
});

test("Parse Review Queue Request: nothing else in the body is read (T-30-17)", () => {
  const [out] = runNode(jsCodeOf(PARSE), [{
    body: {
      object_type: "companies", limit: 10,
      properties: ["hs_object_id"], filterGroups: [], record_id: "789",
      decision: "approve", lv_enrichment_needs_review: "false",
    },
  }], {});
  assert.deepEqual(Object.keys(out).sort(), ["limit", "object_type"],
    "the caller may choose WHICH queue and HOW MANY, never WHAT is read");
});

/** A HubSpot CRM v3 search envelope holding two flagged companies. `total` deliberately
 * exceeds the page, which is the truncation case REVIEW-01 turns on. */
const CANDIDATE_A = '[{"field":"lv_org_type","current_value":"broadcaster",'
  + '"proposed_value":"governing_body_league","decision":"needs_review"}]';
const PROVENANCE_A = '{"lv_org_type":{"source":"claude_web","confidence":60,'
  + '"verified_at":"2026-07-30T00:00:00.000Z","validation_status":"llm_classified",'
  + '"value":"governing_body_league"}}';

function envelope(rows, total) {
  return { total, results: rows, paging: {} };
}

const TWO_FLAGGED = envelope([
  {
    id: "789",
    properties: {
      name: "Example Racing League", domain: "exampleracing.example",
      [P_NEEDS_REVIEW]: "true", [P_ICP_NEEDS_REVIEW]: "false",
      [P_CANDIDATE_JSON]: CANDIDATE_A, [P_PROVENANCE]: PROVENANCE_A,
      lv_icp_tier: "B", lv_anti_icp_reason: "",
    },
  },
  {
    id: "790",
    properties: {
      name: "Other Co", domain: "other.example",
      [P_NEEDS_REVIEW]: "false", [P_ICP_NEEDS_REVIEW]: "true",
      [P_CANDIDATE_JSON]: "", [P_PROVENANCE]: "",
      lv_icp_tier: "D", lv_anti_icp_reason: "Non-ANZ geography",
    },
  },
], 7);

const PARSED_COMPANIES = { [PARSE]: [{ object_type: "companies", limit: 2 }] };

test("Review Queue Rows: one envelope item carrying every row, the page size and the WHOLE total", () => {
  const out = runNode(jsCodeOf(ROWS), [TWO_FLAGGED], PARSED_COMPANIES);
  assert.equal(out.length, 1, "one item out — never one per row (D-22/D-24)");
  const [env] = out;
  assert.equal(env.object_type, "companies");
  assert.equal(env.search_ok, true);
  assert.equal(env.total, 7, "the whole backlog, not this page");
  assert.equal(env.returned, 2);
  assert.notEqual(env.total, env.returned,
    "a truncated page must be visibly a page, never an empty or complete queue");
  assert.deepEqual(env.rows.map((r) => r.hs_object_id), ["789", "790"]);
});

test("Review Queue Rows: stored strings reach the client UNPARSED and unmodified (D-11)", () => {
  const [env] = runNode(jsCodeOf(ROWS), [TWO_FLAGGED], PARSED_COMPANIES);
  const row = env.rows[0];
  // Strict equality on the string: any parse-and-reserialize inside the node fails here,
  // even a byte-identical round trip through a differently-ordered JSON.stringify.
  assert.strictEqual(row[P_CANDIDATE_JSON], CANDIDATE_A);
  assert.strictEqual(row[P_PROVENANCE], PROVENANCE_A);
  assert.equal(typeof row[P_CANDIDATE_JSON], "string");
  assert.equal(typeof row[P_PROVENANCE], "string");
  // Identity and the ICP narrative pass through as stored, too.
  assert.equal(row.name, "Example Racing League");
  assert.equal(row.lv_icp_tier, "B");
  assert.equal(env.rows[1].lv_anti_icp_reason, "Non-ANZ geography");
});

test("Review Queue Rows: an EMPTY queue still answers — zero rows, zero total, search_ok", () => {
  const out = runNode(jsCodeOf(ROWS), [envelope([], 0)], PARSED_COMPANIES);
  assert.equal(out.length, 1,
    "zero items here would reach no responder and hang the caller ~100s until "
    + "Cloudflare 524s (D-22) — and an empty queue is this phase's normal end state");
  assert.deepEqual(out[0].rows, []);
  assert.equal(out[0].total, 0);
  assert.equal(out[0].returned, 0);
  assert.equal(out[0].search_ok, true, "an empty queue is a SUCCESSFUL read");
});

test("Review Queue Rows: a FAILED search is not reported as an empty queue", () => {
  // HubSpot search nodes run onError: continueRegularOutput, so a 401/429 arrives as an
  // item with no `results` array. Rendered as an envelope it would read "0 flagged
  // records" and tell the operator their backlog was clear when it was never read.
  const out = runNode(jsCodeOf(ROWS),
    [{ error: { message: "Request failed with status code 401" } }], PARSED_COMPANIES);
  assert.equal(out.length, 1);
  assert.equal(out[0].search_ok, false);
  assert.deepEqual(out[0].rows, []);
});

test("Review Queue Rows: the contacts lane stamps its own object_type", () => {
  const [env] = runNode(jsCodeOf(ROWS), [envelope([{
    id: "42",
    properties: {
      email: "a@example.com", firstname: "A", lastname: "B",
      [P_NEEDS_REVIEW]: "true", [P_CONTACT_PROVENANCE]: "{}", [P_CANDIDATE_JSON]: "",
    },
  }], 1)], { [PARSE]: [{ object_type: "contacts", limit: 100 }] });
  assert.equal(env.object_type, "contacts");
  assert.equal(env.rows[0].hs_object_id, "42");
  assert.equal(env.rows[0].email, "a@example.com");
  assert.strictEqual(env.rows[0][P_CONTACT_PROVENANCE], "{}");
  // Present but EMPTY, which is how a contact always comes back: the property belongs to
  // the shared review family, and nothing in this deployment ever fills it for a contact.
  assert.strictEqual(env.rows[0][P_CANDIDATE_JSON], "");
});

test("Review Queue Rows: a search node's own single-record shape still adapts", () => {
  // Defensive, mirroring REVIEW_EXTRACT_RECORD: an item that IS a record rather than an
  // envelope must not be read as a failed search.
  const [env] = runNode(jsCodeOf(ROWS),
    [{ id: "1", properties: { name: "Solo" } }], PARSED_COMPANIES);
  assert.equal(env.search_ok, true);
  assert.equal(env.returned, 1);
  assert.equal(env.rows[0].name, "Solo");
});
