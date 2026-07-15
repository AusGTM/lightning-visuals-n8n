// zoominfoToken.js — pure token cache/refresh helpers for the ZoomInfo OAuth2 flow.
//
// ZoomInfo (Okta) issues short-lived bearer tokens. For AUTONOMOUS operation the
// workflow must mint its own token from long-lived client_id + client_secret and
// re-mint when it expires or is rejected (401) — never store a static token.
//
// These are PURE functions (no n8n, no network) so they unit-test against Node.
// The n8n Code node wraps them around $getWorkflowStaticData (cross-run cache),
// this.helpers.httpRequest (mint + enrich), and Date.now().
//
// Cache shape stored in workflow static data: { access_token, exp, token_type }
//   exp = absolute expiry in epoch MILLISECONDS.

// Mint a new token iff there is no cached token or it is within `skewMs` of expiry.
// Minting slightly early (default 60s skew) avoids using a token that dies mid-request.
function needsMint(cached, nowMs, skewMs = 60000) {
  if (!cached || !cached.access_token || !cached.exp) return true;
  return cached.exp - nowMs <= skewMs;
}

// Absolute expiry (epoch ms) from the token response's `expires_in` (seconds).
// Missing/invalid expires_in -> conservative 5-minute lifetime so we re-mint soon
// rather than trust an unknown-lifetime token indefinitely.
function computeExpiry(expiresInSec, nowMs) {
  const secs = Number(expiresInSec);
  if (!Number.isFinite(secs) || secs <= 0) return nowMs + 5 * 60000;
  return nowMs + secs * 1000;
}

// Parse an OAuth token-endpoint response into the cache shape. Accepts the JSON
// object or a raw JSON string. Throws if no token field is present (fail loud —
// a tokenless response must not be cached as if valid).
function parseTokenResponse(body, nowMs) {
  const b = typeof body === "string" ? JSON.parse(body) : (body || {});
  const token = b.access_token || b.jwt || b.token;
  if (!token) throw new Error("ZoomInfo token response missing access_token");
  return {
    access_token: token,
    exp: computeExpiry(b.expires_in, nowMs),
    token_type: b.token_type || "Bearer",
  };
}

// A 401 means the token was rejected (expired/revoked) -> clear cache, re-mint, retry once.
// Other statuses (400/403/404/429/5xx) are NOT auth failures and must not trigger a re-mint.
function isAuthError(statusCode) {
  return Number(statusCode) === 401;
}

module.exports = { needsMint, computeExpiry, parseTokenResponse, isAuthError };
