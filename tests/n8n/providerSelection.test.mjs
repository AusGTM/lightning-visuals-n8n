// tests/n8n/providerSelection.test.mjs
//
// Phase 16.1 Task 1 — providerSelection.js's first direct unit test. Proves
// resolveEnabledProviders' "all"/"none"/absent/array-with-unknown-dropped resolution
// (CONTEXT Locked Decisions 1/2), the A4 envelope-vs-bare-array payload contract
// (reviews A4), and extractCredits' three null-safe extractors (RESEARCH.md Task 1,
// live-curl-validated) including the Apollo-403 and malformed-input null paths.
// providerSelection.js is pure — this file characterizes it, never n8n runtime state.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const { parseWebhookBody, resolveEnabledProviders, extractCredits } =
  require(path.join(ROOT, "n8n/code/providerSelection.js"));

const ALL = ["lusha", "apollo", "zoominfo"];

// --- resolveEnabledProviders --------------------------------------------------------

test("resolveEnabledProviders: \"all\" enables every registered name", () => {
  const { provider_enabled, providers_requested } = resolveEnabledProviders("all", ALL);
  assert.deepEqual(provider_enabled, { lusha: true, apollo: true, zoominfo: true });
  assert.deepEqual(providers_requested.sort(), ["apollo", "lusha", "zoominfo"]);
});

test("resolveEnabledProviders: \"none\" enables nothing", () => {
  const { provider_enabled, providers_requested } = resolveEnabledProviders("none", ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: false, zoominfo: false });
  assert.deepEqual(providers_requested, []);
});

test("resolveEnabledProviders: \"\" (blank) enables nothing", () => {
  const { provider_enabled } = resolveEnabledProviders("", ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: false, zoominfo: false });
});

test("resolveEnabledProviders: absent (undefined) enables nothing — safe default", () => {
  const { provider_enabled, providers_requested } = resolveEnabledProviders(undefined, ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: false, zoominfo: false });
  assert.deepEqual(providers_requested, []);
});

test("resolveEnabledProviders: null enables nothing", () => {
  const { provider_enabled } = resolveEnabledProviders(null, ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: false, zoominfo: false });
});

test("resolveEnabledProviders: an anomalous non-array/non-string value enables nothing (fail closed)", () => {
  const { provider_enabled } = resolveEnabledProviders({ bogus: true }, ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: false, zoominfo: false });
});

test("resolveEnabledProviders: an array enables EXACTLY those names", () => {
  const { provider_enabled, providers_requested } = resolveEnabledProviders(["apollo"], ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: true, zoominfo: false });
  assert.deepEqual(providers_requested, ["apollo"]);
});

test("resolveEnabledProviders: array is case-insensitive and drops unknown names", () => {
  const { provider_enabled, providers_requested } =
    resolveEnabledProviders(["APOLLO", "bogus-provider"], ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: true, zoominfo: false });
  assert.deepEqual(providers_requested, ["apollo"]);
});

test("resolveEnabledProviders: an explicit empty array enables nothing", () => {
  const { provider_enabled, providers_requested } = resolveEnabledProviders([], ALL);
  assert.deepEqual(provider_enabled, { lusha: false, apollo: false, zoominfo: false });
  assert.deepEqual(providers_requested, []);
});

// --- parseWebhookBody (reviews A4 — envelope vs bare-array contract) ---------------

test("A4: a bare HubSpot event array carries NO providers slot -> providers undefined", () => {
  const body = [{ objectId: 1, objectType: "contact" }, { objectId: 2, objectType: "company" }];
  const { events, providers } = parseWebhookBody(body);
  assert.equal(events, body);
  assert.equal(providers, undefined);
});

test("A4: an envelope {providers, events:[...]} is parsed as caller-injected selection", () => {
  const body = { providers: "all", events: [{ objectId: 1, objectType: "contact" }] };
  const { events, providers } = parseWebhookBody(body);
  assert.deepEqual(events, body.events);
  assert.equal(providers, "all");
});

test("A4: an envelope with an array providers selection round-trips", () => {
  const body = { providers: ["lusha", "apollo"], events: [{ objectId: 1 }, { objectId: 2 }] };
  const { events, providers } = parseWebhookBody(body);
  assert.deepEqual(events, body.events);
  assert.deepEqual(providers, ["lusha", "apollo"]);
});

test("A4: a single bare event object (no envelope, no array) is treated as the one event", () => {
  const body = { objectId: 1, objectType: "contact" };
  const { events, providers } = parseWebhookBody(body);
  assert.deepEqual(events, [body]);
  assert.equal(providers, undefined);
});

test("A4: a single bare event object carrying its OWN providers field surfaces it (per-event fallback covers this without double logic)", () => {
  const body = { objectId: 1, objectType: "contact", providers: ["zoominfo"] };
  const { events, providers } = parseWebhookBody(body);
  assert.deepEqual(events, [body]);
  assert.deepEqual(providers, ["zoominfo"]);
});

// --- parseWebhookBody mode extraction (Phase 36-03, 36-CONTEXT.md sec6) -------------
// mode is read at the ENVELOPE level exactly as providers already is — same guard, same
// undefined default. It is NOT an allow-list: any non-"write" value is return-only.

test("mode: an envelope {mode, events:[...]} surfaces mode at the top level", () => {
  const body = { mode: "propose", events: [{ objectId: 1 }] };
  const { events, providers, mode } = parseWebhookBody(body);
  assert.deepEqual(events, body.events);
  assert.equal(providers, undefined);
  assert.equal(mode, "propose");
});

test("mode: an envelope with no mode key -> mode undefined", () => {
  const body = { events: [{ objectId: 1 }] };
  const { mode } = parseWebhookBody(body);
  assert.equal(mode, undefined);
});

test("mode: a bare array body -> mode undefined (bare arrays carry no envelope fields)", () => {
  const body = [{ objectId: 1 }, { objectId: 2 }];
  const { events, mode } = parseWebhookBody(body);
  assert.equal(events, body);
  assert.equal(mode, undefined);
});

test("mode: an explicit mode:\"write\" round-trips", () => {
  const body = { mode: "write", events: [{ objectId: 1 }] };
  const { mode } = parseWebhookBody(body);
  assert.equal(mode, "write");
});

test("mode: null body -> mode undefined, no throw", () => {
  const { events, providers, mode } = parseWebhookBody(null);
  assert.deepEqual(events, [null]);
  assert.equal(providers, undefined);
  assert.equal(mode, undefined);
});

test("mode: undefined body -> mode undefined, no throw", () => {
  const { events, providers, mode } = parseWebhookBody(undefined);
  assert.deepEqual(events, [undefined]);
  assert.equal(providers, undefined);
  assert.equal(mode, undefined);
});

test("mode: a single bare event object carrying its own mode field surfaces it, matching how providers already behaves for a single bare event", () => {
  const body = { mode: "propose" };
  const { events, mode } = parseWebhookBody(body);
  assert.deepEqual(events, [body]);
  assert.equal(mode, "propose");
});

test("mode: events/providers outputs are byte-identical to before for a mode-carrying envelope", () => {
  const body = { mode: "propose", providers: ["lusha"], events: [{ objectId: 1 }, { objectId: 2 }] };
  const { events, providers, mode } = parseWebhookBody(body);
  assert.deepEqual(events, body.events);
  assert.deepEqual(providers, ["lusha"]);
  assert.equal(mode, "propose");
});

// --- extractCredits -------------------------------------------------------------------

test("extractCredits: lusha valid 200 body -> credits.remaining", () => {
  const raw = { credits: { total: 4200, used: 82, remaining: 4118 } };
  assert.equal(extractCredits("lusha", raw), 4118);
});

test("extractCredits: lusha malformed body -> null", () => {
  assert.equal(extractCredits("lusha", { unexpected: true }), null);
  assert.equal(extractCredits("lusha", null), null);
});

test("extractCredits: apollo 403 body (no remaining field) -> null [VERIFIED: live curl 403]", () => {
  const raw = { error: "API_INACCESSIBLE", message: "not authorized" };
  assert.equal(extractCredits("apollo", raw), null);
});

test("extractCredits: apollo malformed/absent -> null", () => {
  assert.equal(extractCredits("apollo", undefined), null);
});

test("extractCredits: zoominfo picks the uniqueIdLimit entry's usageRemaining", () => {
  const raw = {
    data: [{ attributes: { usage: [
      { limitType: "requestLimit", totalLimit: 0, currentUsage: 0, usageRemaining: 0 },
      { limitType: "recordLimit", totalLimit: 0, currentUsage: 0, usageRemaining: 0 },
      { limitType: "uniqueIdLimit", totalLimit: 12000, currentUsage: 2655, usageRemaining: 9345 },
    ] } }],
  };
  assert.equal(extractCredits("zoominfo", raw), 9345);
});

test("extractCredits: zoominfo falls back to the entry with a non-zero totalLimit when uniqueIdLimit is absent", () => {
  const raw = {
    data: [{ attributes: { usage: [
      { limitType: "requestLimit", totalLimit: 0, currentUsage: 0, usageRemaining: 0 },
      { limitType: "someOtherLimit", totalLimit: 500, currentUsage: 100, usageRemaining: 400 },
    ] } }],
  };
  assert.equal(extractCredits("zoominfo", raw), 400);
});

test("extractCredits: zoominfo malformed shape -> null", () => {
  assert.equal(extractCredits("zoominfo", {}), null);
  assert.equal(extractCredits("zoominfo", { data: [] }), null);
  assert.equal(extractCredits("zoominfo", null), null);
});

test("extractCredits: unknown provider name -> null", () => {
  assert.equal(extractCredits("bogus", { credits: { remaining: 1 } }), null);
});
