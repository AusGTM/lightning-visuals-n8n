// n8n/code/providerSelection.js — pure-JS provider-selection cost gate for n8n Code nodes.
//
// Phase 16.1: the caller-supplied `providers` webhook field is the PRIMARY burn gate
// (CONTEXT Locked Decision 1 — no global build-time kill-switch). This module is pure,
// deterministic, and carries NO n8n globals — mirrors enrichmentGate.js exactly, inlined
// into Code nodes via the builder's inline() (Code nodes cannot require() siblings).
//
// parseWebhookBody(body)
//   -> { events, providers, mode }
//   Explicit payload contract (reviews A4): a bare HubSpot event array carries no
//   top-level `providers` slot; an envelope `{ providers, events: [...] }` object carries
//   the caller's selection at the envelope level. A single bare event object (neither an
//   array nor an envelope with `.events`) is treated as the one event, and its own
//   `.providers` field (if any) IS the envelope-level providers value here — the n8n
//   wrapper additionally falls back to `event.providers` per-event when this returns
//   undefined (`parsed.providers ?? event.providers`), covering the same single-event case
//   without double logic.
//   `mode` (Phase 36-03, 36-CONTEXT.md sec6): read at the envelope level with the IDENTICAL
//   idiom as `providers` — absent means today's behaviour byte-identically, `"write"` means
//   today's behaviour explicitly, and any other value is return-only (a typo can never
//   write). Two states, never an allow-list: `mode != null && String(mode).toLowerCase()
//   !== "write"`. That predicate is applied downstream at Decide Action, not here.
//
// resolveEnabledProviders(raw, allNames)
//   -> { provider_enabled: { <name>: boolean, ... }, providers_requested: [...] }
//   "all"                    -> every name in allNames enabled
//   "none" / "" / null / undefined / anything else (absent/unrecognized) -> none enabled
//   an array                 -> exactly those names (lowercased, intersected with
//                                allNames; unknown names dropped)
//
// extractCredits(provider, raw)
//   -> number | null
//   Three null-safe per-provider credit extractors (RESEARCH.md Task 1, live-curl-
//   validated). Forward-provisioned here for Plan 02 (16.1 does not call this at
//   runtime); unit-tested now so Plan 02 can consume it with zero further verification.
//   Every extractor returns null on ANY shape mismatch — never throws, never fails the run.

function parseWebhookBody(body) {
  const events = Array.isArray(body)
    ? body
    : (body && Array.isArray(body.events) ? body.events : [body]);
  const providers = (body && !Array.isArray(body)) ? body.providers : undefined;
  const mode = (body && !Array.isArray(body)) ? body.mode : undefined;
  return { events, providers, mode };
}

function resolveEnabledProviders(raw, allNames) {
  const all = Array.isArray(allNames) ? allNames : [];
  const allLower = all.map((n) => String(n).toLowerCase());
  let enabledLower;

  if (raw === "all") {
    enabledLower = allLower.slice();
  } else if (Array.isArray(raw)) {
    const requestedLower = raw.map((n) => String(n).toLowerCase());
    enabledLower = allLower.filter((n) => requestedLower.indexOf(n) !== -1);
  } else {
    // "none" | "" | null | undefined | any other unrecognized value -> nothing enabled
    // (CONTEXT Locked Decision 2 — safe default, explicit opt-in required).
    enabledLower = [];
  }

  const enabledSet = new Set(enabledLower);
  const provider_enabled = {};
  const providers_requested = [];
  for (const name of all) {
    const lower = String(name).toLowerCase();
    const isEnabled = enabledSet.has(lower);
    provider_enabled[name] = isEnabled;
    if (isEnabled) providers_requested.push(name);
  }

  return { provider_enabled, providers_requested };
}

function extractCredits(provider, raw) {
  const p = String(provider || "").toLowerCase();

  if (p === "lusha") {
    // 200 body -> { credits: { total, used, remaining } } [VERIFIED: live curl 200]
    return (raw && raw.credits && typeof raw.credits.remaining === "number")
      ? raw.credits.remaining : null;
  }

  if (p === "apollo") {
    // THIS account's key 403s (non-master) [VERIFIED: live curl 403] -> raw carries no
    // `remaining` field -> null. A master key's usage_stats body (undocumented shape for
    // this account) is read defensively: only a top-level numeric `remaining` is trusted.
    return (raw && typeof raw.remaining === "number") ? raw.remaining : null;
  }

  if (p === "zoominfo") {
    // JSON:API: data[0].attributes.usage[] keyed by limitType. [VERIFIED: live curl 200]
    // The real redeemable-records balance lives under limitType === "uniqueIdLimit";
    // fall back to the first entry with a non-zero totalLimit before giving up (Open
    // Question #1 — a different ZoomInfo plan may report its balance under another key).
    const usage = (raw && raw.data && raw.data[0] && raw.data[0].attributes
      && raw.data[0].attributes.usage) || [];
    if (!Array.isArray(usage)) return null;
    let entry = usage.find((u) => u && u.limitType === "uniqueIdLimit");
    if (!entry) entry = usage.find((u) => u && typeof u.totalLimit === "number" && u.totalLimit > 0);
    return (entry && typeof entry.usageRemaining === "number") ? entry.usageRemaining : null;
  }

  return null;
}

module.exports = { parseWebhookBody, resolveEnabledProviders, extractCredits };
