// Normalizes every wall-clock stamp in a merge result so two results built by
// separate calls can be compared for equality.
//
// The key shape is BOTH bare (`verified_at`, inside provenance entries) and
// prefixed (`lv_jobtitle_verified_at`, in the canonical patch). A pattern
// anchored on `"verified_at":` misses the prefixed form, which is exactly the
// 1 ms flake this replaced: two mergeContacts() calls straddling a millisecond
// boundary differed on the one stamp that was never stripped.
//
// ponytail: one copy, imported. Four inline copies is four chances to re-narrow it.
export const stripVerifiedAt = (r) =>
  JSON.parse(JSON.stringify(r).replace(/("\w*verified_at":")[^"]*"/g, '$1_"'));
