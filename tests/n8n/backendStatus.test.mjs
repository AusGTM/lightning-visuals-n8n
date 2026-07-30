// tests/n8n/backendStatus.test.mjs
//
// Phase 27 Plan 01 Task 1 — backendStatus.js's first direct unit test. Proves the
// unknown-vs-zero contract (D-08) is a tested property of a pure module before any node
// is wired to it: extractSearchTotal's fail-closed shape checks, deriveSourceHealth's
// never-ok-on-non-2xx and unconfigured-is-not-refused states, and buildStatusBody's
// null-preserving round-trip and non-throwing degrade-to-unknown behavior.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { extractSearchTotal, deriveSourceHealth, buildStatusBody } =
  require(path.join(ROOT, "n8n/code/backendStatus.js"));

// --- extractSearchTotal ---------------------------------------------------------------

test("extractSearchTotal: well-formed search response returns the numeric total", () => {
  assert.equal(extractSearchTotal({ total: 7, results: [] }), 7);
});

test("extractSearchTotal: a genuine numeric zero stays 0, not null", () => {
  const total = extractSearchTotal({ total: 0, results: [] });
  assert.equal(total, 0);
  assert.notEqual(total, null);
});

test("extractSearchTotal: non-object input -> null, not 0", () => {
  const total = extractSearchTotal("not an object");
  assert.equal(total, null);
  assert.notEqual(total, 0);
});

test("extractSearchTotal: array input -> null", () => {
  assert.equal(extractSearchTotal([1, 2, 3]), null);
});

test("extractSearchTotal: null/undefined input -> null", () => {
  assert.equal(extractSearchTotal(null), null);
  assert.equal(extractSearchTotal(undefined), null);
});

test("extractSearchTotal: missing total field -> null", () => {
  assert.equal(extractSearchTotal({ results: [] }), null);
});

test("extractSearchTotal: non-numeric total (string) -> null", () => {
  const total = extractSearchTotal({ total: "7" });
  assert.equal(total, null);
  assert.notEqual(total, 0);
});

test("extractSearchTotal: boolean total -> null (truthy is not numeric)", () => {
  assert.equal(extractSearchTotal({ total: true }), null);
  assert.equal(extractSearchTotal({ total: false }), null);
});

test("extractSearchTotal: error-shaped response body -> null", () => {
  assert.equal(extractSearchTotal({ status: 400, message: "Property does not exist" }), null);
});

test("extractSearchTotal: NaN/Infinity total -> null", () => {
  assert.equal(extractSearchTotal({ total: NaN }), null);
  assert.equal(extractSearchTotal({ total: Infinity }), null);
});

// --- deriveSourceHealth ----------------------------------------------------------------

test("deriveSourceHealth: a 2xx probe with usable data -> ok", () => {
  const health = deriveSourceHealth({ configured: true, status: 200, value: { remaining: 100 } });
  assert.equal(health.state, "ok");
  assert.equal(health.status, 200);
});

test("deriveSourceHealth: Apollo's non-master-key 403 -> refused, never ok, carries the code", () => {
  const health = deriveSourceHealth({ configured: true, status: 403, value: null });
  assert.equal(health.state, "refused");
  assert.notEqual(health.state, "ok");
  assert.equal(health.status, 403);
});

test("deriveSourceHealth: any non-2xx status never yields ok (401/429/500 sweep)", () => {
  for (const status of [401, 429, 500, 503]) {
    const health = deriveSourceHealth({ configured: true, status, value: { ok: true } });
    assert.notEqual(health.state, "ok");
    assert.equal(health.state, "refused");
    assert.equal(health.status, status);
  }
});

test("deriveSourceHealth: unconfigured source -> unknown, distinct from refused", () => {
  const health = deriveSourceHealth({ configured: false, status: null, value: null });
  assert.equal(health.state, "unknown");
  assert.notEqual(health.state, "refused");
  assert.notEqual(health.state, "ok");
});

test("deriveSourceHealth: configured but unreachable (no status) -> unknown", () => {
  const health = deriveSourceHealth({ configured: true, status: null, value: null });
  assert.equal(health.state, "unknown");
});

test("deriveSourceHealth: a 2xx with no usable value -> unknown, not ok", () => {
  const health = deriveSourceHealth({ configured: true, status: 200, value: null });
  assert.equal(health.state, "unknown");
  assert.notEqual(health.state, "ok");
});

test("deriveSourceHealth: malformed/absent probe -> unknown, never throws", () => {
  assert.equal(deriveSourceHealth(undefined).state, "unknown");
  assert.equal(deriveSourceHealth(null).state, "unknown");
  assert.equal(deriveSourceHealth("bogus").state, "unknown");
});

// --- buildStatusBody --------------------------------------------------------------------

test("buildStatusBody: round-trips a real count as a number", () => {
  const body = buildStatusBody({ counts: { companies_requested_unresolved: 12 } });
  assert.equal(body.counts.companies_requested_unresolved, 12);
});

test("buildStatusBody: a failed count comes back as JSON null, not 0, not omitted", () => {
  const body = buildStatusBody({ counts: {} });
  assert.equal(body.counts.companies_requested_unresolved, null);
  assert.notEqual(body.counts.companies_requested_unresolved, 0);
  assert.ok("companies_requested_unresolved" in body.counts, "key must be present, not omitted");
  // JSON round-trip: null must serialize as the literal `null`, never disappear.
  const roundTripped = JSON.parse(JSON.stringify(body));
  assert.equal(roundTripped.counts.companies_requested_unresolved, null);
  assert.ok("companies_requested_unresolved" in roundTripped.counts);
});

test("buildStatusBody: covers all four counts (companies/contacts x requested/review)", () => {
  const body = buildStatusBody({
    counts: {
      companies_requested_unresolved: 1,
      companies_awaiting_review: 2,
      contacts_requested_unresolved: 3,
      contacts_awaiting_review: 4,
    },
  });
  assert.deepEqual(body.counts, {
    companies_requested_unresolved: 1,
    companies_awaiting_review: 2,
    contacts_requested_unresolved: 3,
    contacts_awaiting_review: 4,
  });
});

test("buildStatusBody: never throws on malformed input — every branch degrades to unknown", () => {
  assert.doesNotThrow(() => buildStatusBody(undefined));
  assert.doesNotThrow(() => buildStatusBody(null));
  assert.doesNotThrow(() => buildStatusBody("bogus"));
  assert.doesNotThrow(() => buildStatusBody({ counts: "not an object", health: "not an array" }));

  const degraded = buildStatusBody(null);
  assert.equal(degraded.counts.companies_requested_unresolved, null);
  assert.deepEqual(degraded.credential_health, []);
});

test("buildStatusBody: preserves credential_health entries, defaulting a malformed one to unknown", () => {
  const body = buildStatusBody({
    health: [
      { source: "apollo", state: "refused", status: 403, reason: "http_403" },
      { source: "hubspot", state: "ok", status: 200, reason: null },
      "bogus-entry",
    ],
  });
  assert.deepEqual(body.credential_health[0], { source: "apollo", state: "refused", status: 403, reason: "http_403" });
  assert.deepEqual(body.credential_health[1], { source: "hubspot", state: "ok", status: 200, reason: null });
  assert.equal(body.credential_health[2].state, "unknown");
});
