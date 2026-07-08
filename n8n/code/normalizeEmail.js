// normalizeEmail.js — pure-JS email normalization for n8n Code nodes.
//
// normalizeEmailBasic does a BASIC syntactic check + trim/lowercase only. The
// authoritative validation is the external rapid-email-verifier API downstream;
// applyEmailVerification maps that verifier's response onto the row. This mirrors
// src/normalizer.py normalize_email closely enough for identity/dedupe parity:
// obviously-malformed -> null, otherwise trimmed+lowercased.

function normalizeEmailBasic(raw) {
  if (raw === null || raw === undefined) return null;
  const s = String(raw).trim().toLowerCase();
  if (s === "") return null;
  // Basic shape: local@domain.tld, no spaces, one @, a dotted domain.
  // Deliberately conservative — the verifier API is the real authority.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)) return null;
  return s;
}

// Map a rapid-email-verifier result onto the row. `verifierResult` shape:
//   { status: "VALID"|"PROBABLY_VALID"|"INVALID_FORMAT"|"INVALID_DOMAIN"|"DISPOSABLE",
//     aliasOf?: "canonical@example.com" }
// Returns the fields to merge onto the row.
function applyEmailVerification(row, verifierResult) {
  const status = (verifierResult && verifierResult.status) || "INVALID_FORMAT";
  const alias = verifierResult && verifierResult.aliasOf;
  const raw = row ? row.email : undefined;

  // aliasOf is the canonical address when the verifier resolved one.
  const canonical = alias
    ? normalizeEmailBasic(alias)
    : normalizeEmailBasic(raw);

  const valid = status === "VALID" || status === "PROBABLY_VALID";

  return {
    email_normalized: valid ? canonical : normalizeEmailBasic(raw),
    email_valid: valid,
    email_status: status,
    needs_review_reason: valid ? null : `email verifier: ${status}`,
  };
}

module.exports = { normalizeEmailBasic, applyEmailVerification };
