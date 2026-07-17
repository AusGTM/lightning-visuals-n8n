// normalizePhone.js — pure-JS AU phone normalizer for n8n Code nodes.
//
// DISCLAIMER: This is an AU-ONLY heuristic, NOT libphonenumber. It cannot import
// npm (n8n Code nodes run pure JS with no requires), so it recognises only the AU
// formats the ingestion pipeline actually sees. Any number that is non-AU or
// ambiguous returns null — the caller must route null to review, never silently
// drop or guess. A leading '+' is trusted as already-E.164 and passed through
// (separators stripped) WITHOUT a validity check, so an invalid '+...' string is
// kept as-is here where the Python oracle (phonenumbers.is_valid_number) would
// reject it. Swap this for a phone-validation API for global fidelity later.
//
// Mirrors src/normalizer.py normalize_phone for the AU cases the parity test pins.

function normalizePhoneAU(raw) {
  if (raw === null || raw === undefined || raw === "") return null;
  // Strip spaces, dashes, parens, dots — everything that is pure separator.
  const s = String(raw).replace(/[\s\-().]/g, "");
  if (s === "") return null;

  // Already international: trust the '+', keep the digits after it.
  if (s.startsWith("+")) {
    const digits = s.slice(1);
    if (!/^\d+$/.test(digits)) return null; // "+garbage" -> review
    return "+" + digits;
  }

  if (!/^\d+$/.test(s)) return null; // any non-digit leftover -> not AU/ambiguous

  // 0XXXXXXXXX — 10-digit AU national (mobile 04.. or landline 0[2378]..).
  if (s.length === 10 && s[0] === "0") {
    return "+61" + s.slice(1);
  }

  // 61XXXXXXXXX — AU country code without the '+'.
  if (s.length === 11 && s.startsWith("61")) {
    return "+" + s;
  }

  return null; // anything else is non-AU or ambiguous -> review
}

// normalizePhone(raw, region) — region-aware E.164 normalizer.
//
// Still NOT libphonenumber (n8n Code nodes can't require npm), but deterministic and
// keyed off the ISO2 country the PROVIDERS already return (Lusha location.country_iso2,
// Apollo person country, etc.) instead of guessing. Rules, in order:
//   1. Already `+E.164` -> trust and keep (digits 6-15).
//   2. Known region -> prepend that country's calling code (stripping a trunk 0 for
//      AU/NZ/GB/IE, a leading 1 for US/CA), gated by a per-country NSN-length sanity check.
//   3. Unknown/absent region -> fall back to normalizePhoneAU (AU heuristic). A non-AU
//      national number then returns null -> the caller drops it (never a bad write).
// The NSN-length gate is a sanity filter, not full validation; swap for a phone API when
// global precision matters (same external-call pattern as the email verifier).
const CALLING_CODE = { AU: "61", NZ: "64", US: "1", CA: "1", GB: "44", IE: "353", IN: "91", SG: "65" };
const NSN_LEN = { "61": [9], "64": [8, 9], "1": [10], "44": [9, 10], "353": [9], "91": [10], "65": [8] };
const TRUNK_REGIONS = /^(AU|NZ|GB|IE)$/;

function _nsnOk(cc, nsn) {
  const lens = NSN_LEN[cc];
  return lens ? lens.includes(nsn.length) : (nsn.length >= 6 && nsn.length <= 14);
}

function normalizePhone(raw, region) {
  if (raw === null || raw === undefined || raw === "") return null;
  const s = String(raw).replace(/[\s\-().]/g, "");
  if (s === "") return null;
  if (s.startsWith("+")) {
    const d = s.slice(1);
    return /^\d{6,15}$/.test(d) ? "+" + d : null;
  }
  if (!/^\d+$/.test(s)) return null;
  const r = String(region || "").toUpperCase();
  const cc = CALLING_CODE[r];
  if (!cc) return normalizePhoneAU(s); // unknown region -> AU heuristic (non-AU -> null)
  if (s.startsWith(cc) && _nsnOk(cc, s.slice(cc.length))) return "+" + s; // already has CC
  let nsn = s;
  if (TRUNK_REGIONS.test(r) && nsn.startsWith("0")) nsn = nsn.slice(1);          // trunk 0
  if (cc === "1" && nsn.length === 11 && nsn.startsWith("1")) nsn = nsn.slice(1); // US/CA leading 1
  return _nsnOk(cc, nsn) ? "+" + cc + nsn : null;
}

module.exports = { normalizePhoneAU, normalizePhone };
