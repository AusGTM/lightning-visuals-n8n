// n8n/code/backendStatus.js — pure-JS null-safe extraction and credential-health
// derivation for the `hubspot/backend-status` endpoint's full-health slice (Phase 27).
//
// Mirrors providerSelection.js exactly: no n8n globals, no require() of siblings, every
// exported function total and non-throwing. Inlined into Code nodes via the builder's
// inline() (Code nodes cannot require() siblings).
//
// extractSearchTotal(raw)
//   -> number | null
//   Reads a HubSpot CRM v3 search response's `.total` field. Every shape mismatch
//   (non-object, missing field, non-numeric, boolean) yields null — a genuine numeric
//   zero is the ONLY input that returns 0 (D-08: unknown is never zero).
//
// deriveSourceHealth(probe)
//   -> { state: "ok" | "refused" | "unknown", status: number|null, reason: string|null }
//   `probe` is `{configured, status, value}` for one credential-bearing source. A non-2xx
//   status can NEVER produce "ok" (T-27-04); an unconfigured/unreachable source produces
//   "unknown", distinct from "refused" (D-08 — an absent credential is not a refusal).
//
// buildStatusBody(parts)
//   -> { counts: {...}, credential_health: [...], checked_at }
//   Assembles the response, preserving `null` counts as JSON null (STATUS-06) — never 0,
//   never an omitted key. Never throws; every malformed branch degrades to unknown/null.

function extractSearchTotal(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const total = raw.total;
  if (typeof total !== "number" || !Number.isFinite(total)) return null;
  return total;
}

function deriveSourceHealth(probe) {
  const p = probe && typeof probe === "object" ? probe : {};
  const configured = p.configured === true;
  const status = typeof p.status === "number" && Number.isFinite(p.status) ? p.status : null;

  if (!configured) {
    // No credential to probe with at all — cannot-tell, never "refused" (D-08).
    return { state: "unknown", status: null, reason: "not_configured" };
  }
  if (status === null) {
    // Configured but no usable status came back (timeout, not executed, malformed shape).
    return { state: "unknown", status: null, reason: "no_response" };
  }
  if (status >= 200 && status < 300) {
    if (p.value === null || p.value === undefined) {
      // A 2xx with no usable value is still a "can't tell," never a false "ok".
      return { state: "unknown", status, reason: "unrecognized_response_shape" };
    }
    return { state: "ok", status, reason: null };
  }
  // Any non-2xx (401/403/429/5xx/...) is reachable-but-refused — never "ok".
  return { state: "refused", status, reason: "http_" + status };
}

function buildStatusBody(parts) {
  const safe = parts && typeof parts === "object" && parts !== null ? parts : {};
  const counts = safe.counts && typeof safe.counts === "object" ? safe.counts : {};
  const health = Array.isArray(safe.health) ? safe.health : [];

  const normCount = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

  return {
    counts: {
      companies_requested_unresolved: normCount(counts.companies_requested_unresolved),
      companies_awaiting_review: normCount(counts.companies_awaiting_review),
      contacts_requested_unresolved: normCount(counts.contacts_requested_unresolved),
      contacts_awaiting_review: normCount(counts.contacts_awaiting_review),
    },
    credential_health: health.map((h) => {
      const entry = h && typeof h === "object" ? h : {};
      const state = entry.state === "ok" || entry.state === "refused" ? entry.state : "unknown";
      return {
        source: typeof entry.source === "string" ? entry.source : "unknown",
        state,
        status: typeof entry.status === "number" ? entry.status : null,
        reason: typeof entry.reason === "string" ? entry.reason : null,
      };
    }),
    checked_at: typeof safe.checked_at === "string" ? safe.checked_at : new Date().toISOString(),
  };
}

module.exports = { extractSearchTotal, deriveSourceHealth, buildStatusBody };
