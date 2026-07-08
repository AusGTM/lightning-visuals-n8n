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

module.exports = { normalizePhoneAU };
