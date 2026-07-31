// tests/n8n/listExpansion.test.mjs
//
// Phase 25 Plan 03 Task 2 — the pure-function pin on n8n/code/listExpansion.js, the module
// `Expand List To Events` inlines.
//
// The two refusals that matter most are the OVERSIZE case and the VIEW case, and each is
// asserted twice: that the reason is present AND that `events` is empty. A test asserting
// only the reason passes against a node that refuses and expands at the same time — which
// is the defect, not the fix.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { expandListToEvents, VIEW_REFUSAL } = require(path.join(ROOT, "n8n/code/listExpansion.js"));

// The ceiling is a PARAMETER of the module, so these tests do not depend on the builder's
// current value (2, derived in 25-BLOCKERS.md and expected to move once the full-waterfall
// probe B4 runs). tests/test_enrichment_list_branch.py pins the built-in value separately.
const MAX = 3;

const LIST_BODY = (extra = {}) => ({
  list: { name: "New Targets.xlsx", objectType: "contacts" },
  ...extra,
});
const RESOLVED = { list: { listId: "15", name: "New Targets.xlsx" } };
const members = (n, start = 100) => ({
  results: Array.from({ length: n }, (_, i) => ({ recordId: String(start + i) })),
});

function run(overrides = {}) {
  return expandListToEvents({
    body: LIST_BODY(),
    listResult: RESOLVED,
    membershipsResult: members(2),
    maxRecords: MAX,
    ...overrides,
  });
}

// --- (a) the success path ---------------------------------------------------------------

test("N ids at the ceiling expand to N events carrying those ids and the caller's object type", () => {
  const out = run({ membershipsResult: members(MAX) });
  assert.equal(out.refused, false);
  assert.deepEqual(out.events, [
    { objectId: "100", objectType: "contacts" },
    { objectId: "101", objectType: "contacts" },
    { objectId: "102", objectType: "contacts" },
  ]);
});

test("a companies list expands with the companies object type, not the contacts default", () => {
  const out = expandListToEvents({
    body: { list: { name: "Targets", objectType: "companies" } },
    listResult: RESOLVED,
    membershipsResult: members(1),
    maxRecords: MAX,
  });
  assert.equal(out.refused, false);
  assert.deepEqual(out.events, [{ objectId: "100", objectType: "companies" }]);
});

test("a numeric recordId is stringified, matching what Parse HubSpot Event consumes", () => {
  const out = run({ membershipsResult: { results: [{ recordId: 100 }] } });
  assert.deepEqual(out.events, [{ objectId: "100", objectType: "contacts" }]);
});

// --- (b) the provider selection survives expansion unchanged (T-25-02) --------------------

test("the provider selection on the incoming body appears unchanged on the expanded envelope", () => {
  const out = expandListToEvents({
    body: LIST_BODY({ providers: ["lusha", "zoominfo"] }),
    listResult: RESOLVED,
    membershipsResult: members(2),
    maxRecords: MAX,
  });
  assert.deepEqual(out.providers, ["lusha", "zoominfo"]);
});

test("an EMPTY provider selection survives as an empty selection, not as an absent one", () => {
  const out = expandListToEvents({
    body: LIST_BODY({ providers: [] }),
    listResult: RESOLVED,
    membershipsResult: members(2),
    maxRecords: MAX,
  });
  assert.ok("providers" in out, "an explicitly empty selection must be carried through");
  assert.deepEqual(out.providers, []);
});

test("an absent provider selection stays absent, so the parser resolves it to zero providers", () => {
  const out = run();
  assert.equal("providers" in out, false);
});

test('"all" is carried through verbatim rather than being expanded here', () => {
  const out = expandListToEvents({
    body: LIST_BODY({ providers: "all" }),
    listResult: RESOLVED,
    membershipsResult: members(2),
    maxRecords: MAX,
  });
  assert.equal(out.providers, "all");
});

// --- (c) oversize: refused, NEVER truncated (D-15, T-25-07) -------------------------------

test("a membership response above the ceiling refuses, naming the ceiling", () => {
  const out = run({ membershipsResult: members(MAX + 1) });
  assert.equal(out.refused, true);
  assert.match(out.reason, new RegExp(`${MAX} record`));
});

test("a membership response above the ceiling produces ZERO events", () => {
  const out = run({ membershipsResult: members(MAX + 1) });
  assert.deepEqual(out.events, [], "an oversize list must never be silently truncated");
});

test("a `total` above the ceiling refuses even when the returned page is at or below it", () => {
  const out = run({ membershipsResult: { ...members(1), total: 102 } });
  assert.equal(out.refused, true);
  assert.deepEqual(out.events, []);
});

// --- (d) the paging cursor: a page is not a list (25-BLOCKERS.md, D-08/D-20/D-22/D-33) ----

test("a paging cursor refuses even when the returned page is at or below the ceiling", () => {
  const out = run({
    membershipsResult: { ...members(1), paging: { next: { after: "MTAx" } } },
  });
  assert.equal(out.refused, true, "a cursor means the read is a PAGE, not the whole list");
  assert.match(out.reason, new RegExp(`${MAX} record`));
});

test("a paging cursor produces ZERO events, so a truncated page can never be enriched", () => {
  const out = run({
    membershipsResult: { ...members(1), paging: { next: { after: "MTAx" } } },
  });
  assert.deepEqual(out.events, []);
});

test("the cursor refusal says the full list is larger than one response", () => {
  const out = run({
    membershipsResult: { ...members(1), paging: { next: { after: "MTAx" } } },
  });
  assert.match(out.reason, /first page/i);
});

test("an empty `paging.next` is not a cursor and does not refuse a within-ceiling list", () => {
  const out = run({ membershipsResult: { ...members(2), paging: { next: {} } } });
  assert.equal(out.refused, false);
  assert.equal(out.events.length, 2);
});

// --- (e) the list did not resolve — a refusal distinct from oversize -----------------------

test("an unresolvable list name refuses with a reason distinct from the oversize refusal", () => {
  const unresolved = run({ listResult: null });
  const oversize = run({ membershipsResult: members(MAX + 1) });
  assert.equal(unresolved.refused, true);
  assert.deepEqual(unresolved.events, []);
  assert.notEqual(unresolved.reason, oversize.reason);
  assert.match(unresolved.reason, /no contacts list named/i);
});

test("a 404/error body carrying no listId refuses rather than falling through to nothing", () => {
  const out = run({ listResult: { status: 404, message: "resource not found" } });
  assert.equal(out.refused, true);
  assert.deepEqual(out.events, []);
});

test("a flat body carrying listId at the top level still resolves", () => {
  const out = run({ listResult: { listId: 15 } });
  assert.equal(out.refused, false);
  assert.equal(out.events.length, 2);
});

// --- (f) a saved view is refused and redirected, never resolved (amendment #7, Pitfall 2) --

test("an input naming a saved view produces the refusal recorded in 25-BLOCKERS.md", () => {
  const out = expandListToEvents({
    body: { providers: ["lusha"], view: { name: "My Targets" } },
    listResult: RESOLVED,
    membershipsResult: members(2),
    maxRecords: MAX,
  });
  assert.equal(out.refused, true);
  assert.equal(out.reason, VIEW_REFUSAL);
  assert.match(out.reason, /HubSpot doesn't expose views through its API/);
  assert.match(out.reason, /Save that view as a list/);
});

test("a view input produces ZERO events even when a list resolved alongside it", () => {
  const out = expandListToEvents({
    body: { view: { name: "My Targets" }, list: { name: "New Targets.xlsx", objectType: "contacts" } },
    listResult: RESOLVED,
    membershipsResult: members(2),
    maxRecords: MAX,
  });
  assert.deepEqual(out.events, [], "a view must never be resolved against the list endpoint");
  assert.equal(out.reason, VIEW_REFUSAL);
});

// --- (g) malformed input: a refusal, never an exception and never an empty success ---------

for (const [label, overrides] of [
  ["a null body", { body: null }],
  ["a body naming no list", { body: { providers: [] } }],
  ["a blank list name", { body: { list: { name: "   ", objectType: "contacts" } } }],
  ["an unknown object type", { body: { list: { name: "X", objectType: "deals" } } }],
  ["a membership body with no results array", { membershipsResult: { total: 4 } }],
  ["a null membership body", { membershipsResult: null }],
  ["an empty membership list", { membershipsResult: { results: [] } }],
  ["a membership row with no usable record id", { membershipsResult: { results: [{}] } }],
]) {
  test(`${label} refuses without throwing, and never returns an empty success`, () => {
    let out;
    assert.doesNotThrow(() => { out = run(overrides); });
    assert.equal(out.refused, true, `${label} must refuse`);
    assert.equal(typeof out.reason, "string");
    assert.ok(out.reason.length > 0, "a refusal must carry a plain-language reason");
    assert.deepEqual(out.events, []);
  });
}

test("expandListToEvents called with nothing at all refuses instead of throwing", () => {
  let out;
  assert.doesNotThrow(() => { out = expandListToEvents(); });
  assert.equal(out.refused, true);
  assert.deepEqual(out.events, []);
});

test("an absent maxRecords refuses rather than defaulting to an unbounded expansion", () => {
  const out = expandListToEvents({
    body: LIST_BODY(),
    listResult: RESOLVED,
    membershipsResult: members(2),
  });
  assert.equal(out.refused, true, "no ceiling must mean no expansion, not an infinite one");
  assert.deepEqual(out.events, []);
});
