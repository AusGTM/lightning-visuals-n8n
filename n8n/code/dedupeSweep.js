// dedupeSweep.js — pure-JS dedupe/mangled maintenance sweep for n8n Code nodes.
//
// Mirrors src/sweep.py dedupe_sweep. CLASSIFY ONLY — flags records to review, never
// writes. The correctness property that matters: dedupe keys are compared AFTER
// normalization, so two phones in different raw formats sharing one E.164 collapse
// into a single duplicate group (0412… ≡ +61412…). mangled = a non-empty raw
// email/phone that normalizes to null.
//
// records: [{ id, properties: { email, phone, linkedin_url } }, ...]

const { normalizeEmailBasic } = require("./normalizeEmail");
const { normalizePhoneAU } = require("./normalizePhone");
const { canonicalizeLinkedin } = require("./resolveIdentity");

// Fixed (key_type, normalizer, property) order — deterministic output.
const DUP_KEYS = [
  ["email", normalizeEmailBasic, "email"],
  ["phone", normalizePhoneAU, "phone"],
  ["linkedin_url", canonicalizeLinkedin, "linkedin_url"],
];

// Fixed (field, normalizer, reason) order for mangled detection.
const MANGLED_FIELDS = [
  ["email", normalizeEmailBasic, "invalid email"],
  ["phone", normalizePhoneAU, "unparseable phone"],
];

function dedupeSweep(records) {
  records = records || [];
  const duplicates = [];
  const reviewIds = new Set();

  for (const [keyType, normalizer, prop] of DUP_KEYS) {
    const byKey = new Map();
    for (const rec of records) {
      const raw = (rec.properties || {})[prop];
      const key = normalizer(raw);
      if (!key) continue; // blank or mangled -> not a group key
      if (!byKey.has(key)) byKey.set(key, []);
      byKey.get(key).push(String(rec.id));
    }
    for (const key of [...byKey.keys()].sort()) {
      const ids = byKey.get(key);
      if (ids.length >= 2) {
        const sorted = [...ids].sort();
        duplicates.push({ key_type: keyType, key_value: key, ids: sorted });
        sorted.forEach((id) => reviewIds.add(id));
      }
    }
  }

  const mangled = [];
  const sortedRecords = [...records].sort((a, b) =>
    String(a.id) < String(b.id) ? -1 : String(a.id) > String(b.id) ? 1 : 0);
  for (const rec of sortedRecords) {
    const props = rec.properties || {};
    for (const [field, normalizer, reason] of MANGLED_FIELDS) {
      const raw = props[field];
      if (raw === null || raw === undefined || raw === "") continue; // blank is NOT mangled
      if (normalizer(raw) === null) {
        const rid = String(rec.id);
        mangled.push({ id: rid, field, raw, reason });
        reviewIds.add(rid);
      }
    }
  }

  const toReviewIds = [...reviewIds].sort();
  return {
    duplicates,
    mangled,
    counts: { duplicates: duplicates.length, mangled: mangled.length },
    duplicate_count: duplicates.length,
    mangled_count: mangled.length,
    to_review_ids: toReviewIds,
  };
}

module.exports = { dedupeSweep };
