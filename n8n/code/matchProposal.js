// n8n/code/matchProposal.js — pure-JS match-lane routing and proposal shaping.
//
// Phase 36 Plan 01 (36-CONTEXT.md §7 step 1). `Build Identity` stamps a single `lane`
// value per enrichment row so every downstream routing IF and adapter reads ONE source
// of truth instead of re-deriving its own predicate (36-CONTEXT.md
// <assumption_delta_decision>: "lane becomes the one field that names a row's
// identity-resolution strategy"). Pure, deterministic, no n8n globals — mirrors
// listExpansion.js/providerSelection.js, inlined into a Code node by the builder's
// inline() (Code nodes cannot require() siblings).
//
// laneOf(row) -> "fetch_by_id" | "email" | "name" | "none"
//   The `fetch_by_id` branch mirrors `IF Bare Event`'s boolean expression exactly
//   (scripts/build_cloud_workflows.py, `IF Bare Event` node build):
//     !!$('Build Identity').item.json.object_id &&
//     !$('Build Identity').item.json.identity_keys.email
//   If the two predicates ever drift, a row is routed to one lane and filtered into
//   another and silently disappears (36-CONTEXT.md key_links).

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

// Trims a string field before the truthiness check so a whitespace-only value (e.g.
// companyName: "   ") is never mistaken for a present identity key. Non-strings pass
// through untouched — object_id may legitimately be a number.
function trimmedOrValue(value) {
  return typeof value === "string" ? value.trim() : value;
}

function laneOf(row) {
  const r = isPlainObject(row) ? row : {};
  const identityKeys = isPlainObject(r.identity_keys) ? r.identity_keys : {};
  const objectId = r.object_id;
  const email = trimmedOrValue(identityKeys.email);
  const lastName = trimmedOrValue(identityKeys.lastName);
  const companyName = trimmedOrValue(identityKeys.companyName);

  if (objectId && !email) return "fetch_by_id";
  if (email) return "email";
  if (lastName && companyName) return "name";
  return "none";
}

module.exports = { laneOf };
