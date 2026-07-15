// Tests for the ZoomInfo token cache/refresh helpers (autonomous auth).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { needsMint, computeExpiry, parseTokenResponse, isAuthError } =
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
