// Tests for the ZoomInfo token cache/refresh helpers (autonomous auth).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { needsMint, computeExpiry, parseTokenResponse, isAuthError, extractErrorStatus } =
  require("../../n8n/code/zoominfoToken.js");

const NOW = 1_800_000_000_000; // fixed epoch ms for determinism

test("needsMint: no cache -> mint", () => {
  assert.equal(needsMint(null, NOW), true);
  assert.equal(needsMint({}, NOW), true);
  assert.equal(needsMint({ access_token: "x" }, NOW), true); // no exp
});

test("needsMint: fresh token -> reuse", () => {
  const cached = { access_token: "x", exp: NOW + 10 * 60000 }; // 10 min left
  assert.equal(needsMint(cached, NOW), false);
});

test("needsMint: within skew of expiry -> mint (proactive refresh)", () => {
  const cached = { access_token: "x", exp: NOW + 30000 }; // 30s left, skew 60s
  assert.equal(needsMint(cached, NOW), true);
  // custom skew
  assert.equal(needsMint({ access_token: "x", exp: NOW + 30000 }, NOW, 10000), false);
});

test("computeExpiry: expires_in seconds -> absolute ms", () => {
  assert.equal(computeExpiry(1000, NOW), NOW + 1000 * 1000);
  // missing/invalid -> conservative 5 min
  assert.equal(computeExpiry(undefined, NOW), NOW + 5 * 60000);
  assert.equal(computeExpiry(0, NOW), NOW + 5 * 60000);
  assert.equal(computeExpiry("nope", NOW), NOW + 5 * 60000);
});

test("parseTokenResponse: extracts token + computes exp", () => {
  const p = parseTokenResponse({ access_token: "abc", token_type: "Bearer", expires_in: 3600 }, NOW);
  assert.equal(p.access_token, "abc");
  assert.equal(p.token_type, "Bearer");
  assert.equal(p.exp, NOW + 3600 * 1000);
  // accepts a raw JSON string too
  assert.equal(parseTokenResponse('{"access_token":"zzz","expires_in":60}', NOW).access_token, "zzz");
});

test("parseTokenResponse: tokenless response throws (never cache a bad token)", () => {
  assert.throws(() => parseTokenResponse({ error: "invalid_client" }, NOW), /missing access_token/);
});

test("isAuthError: only 401 triggers re-mint", () => {
  assert.equal(isAuthError(401), true);
  for (const s of [200, 400, 403, 404, 429, 500]) assert.equal(isAuthError(s), false);
});

// Bug B (live 2026-07-28): the ZoomInfo Enrich catch block checked
// `e.statusCode || e.httpCode || (e.response && e.response.statusCode)`, which misses the
// real axios shape (`e.response.status`) — the exact shape n8n's httpRequest throws for a
// live 401. extractErrorStatus() must recognize every shape actually observed, plus a
// last-resort message parse, without ever misclassifying non-401s as auth errors.
test("extractErrorStatus: axios shape {response:{status}} (the live 401 that was missed)", () => {
  assert.equal(extractErrorStatus({ response: { status: 401 } }), 401);
  assert.equal(isAuthError(extractErrorStatus({ response: { status: 401 } })), true);
});

test("extractErrorStatus: n8n NodeApiError httpCode as a STRING", () => {
  assert.equal(extractErrorStatus({ httpCode: "401" }), 401);
  assert.equal(isAuthError(extractErrorStatus({ httpCode: "401" })), true);
});

test("extractErrorStatus: bare statusCode", () => {
  assert.equal(extractErrorStatus({ statusCode: 401 }), 401);
  assert.equal(isAuthError(extractErrorStatus({ statusCode: 401 })), true);
});

test("extractErrorStatus: message-only error, last-resort parse", () => {
  const e = new Error("Request failed with status code 401");
  assert.equal(extractErrorStatus(e), 401);
  assert.equal(isAuthError(extractErrorStatus(e)), true);
});

test("extractErrorStatus: negative cases — 403/429/5xx must never read as auth errors", () => {
  for (const shape of [
    { response: { status: 403 } },
    { httpCode: "429" },
    { statusCode: 500 },
    new Error("Request failed with status code 429"),
    {},
    null,
    undefined,
  ]) {
    assert.equal(isAuthError(extractErrorStatus(shape)), false, JSON.stringify(shape));
  }
});
