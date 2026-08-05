// n8n/code/matchProposal.js — pure-JS match-lane routing and proposal shaping.
//
// Phase 36 Plan 01 (36-CONTEXT.md §7 step 1). `Build Identity` stamps a single `lane`
// value per enrichment row so every downstream routing IF and adapter reads ONE source
// of truth instead of re-deriving its own predicate (36-CONTEXT.md
// <assumption_delta_decision>: "lane becomes the one field that names a row's
// identity-resolution strategy"). Pure, deterministic, no n8n globals — mirrors
// listExpansion.js/providerSelection.js, inlined into a Code node by the builder's
// inline() (Code nodes cannot import sibling modules at runtime).
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

// tokenize(s) — lower-case, strip non-alphanumeric to spaces, split, drop empties.
// Used ONLY for the company token-overlap re-check below — never for substring
// matching (36-CONTEXT.md §12 Risk 3: a false NEGATIVE here costs one enrichment; a
// false POSITIVE corrupts a record, so this stays strict).
function tokenize(s) {
  return String(s == null ? "" : s)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .filter(Boolean);
}

function sharesToken(a, b) {
  const setA = new Set(tokenize(a));
  for (const tok of tokenize(b)) if (setA.has(tok)) return true;
  return false;
}

// mediumCandidates(searchResults, identityKeys) — re-verifies every HubSpot search hit
// BY VALUE before reporting it as a candidate. `CONTAINS_TOKEN` is fuzzy by design; a
// hit surviving the server-side filter is not yet a verified match (the BUG 22b lesson,
// applied prophylactically here — never trust that the search already filtered).
function mediumCandidates(searchResults, identityKeys) {
  const idKeys = isPlainObject(identityKeys) ? identityKeys : {};
  const lastName = trimmedOrValue(idKeys.lastName);
  const companyName = trimmedOrValue(idKeys.companyName);
  if (!lastName || !companyName || !Array.isArray(searchResults)) return [];

  const wantLastName = String(lastName).toLowerCase();
  const out = [];
  for (const hit of searchResults) {
    if (!isPlainObject(hit) || !isPlainObject(hit.properties)) continue;
    const props = hit.properties;
    const hitLastName = props.lastname == null ? "" : String(props.lastname).toLowerCase();
    if (hitLastName !== wantLastName) continue;
    if (!sharesToken(props.company, companyName)) continue;
    out.push({
      hs_object_id: hit.id,
      firstname: props.firstname != null ? props.firstname : null,
      lastname: props.lastname != null ? props.lastname : null,
      email: props.email != null ? props.email : null,
      jobtitle: props.jobtitle != null ? props.jobtitle : null,
      company: props.company != null ? props.company : null,
    });
  }
  return out;
}

// summarizeMatch({ lane, existingRecord, lookupFailed, candidates, objectIdSupplied })
//   -> { tier: "high"|"medium"|"none"|"unknown", auto, reason, candidates }
// `unknown` is not `none` (36-CONTEXT.md §6): "we did not find one" (none) and "we could
// not look" (unknown — the search failed or never ran) must stay distinguishable.
function summarizeMatch(input) {
  const opts = isPlainObject(input) ? input : {};
  const lane = opts.lane;
  const candidates = Array.isArray(opts.candidates) ? opts.candidates : [];

  if (opts.lookupFailed === true) {
    return { tier: "unknown", auto: false, reason: "the match search failed to run", candidates: [] };
  }

  if (lane === "fetch_by_id" || lane === "email") {
    const hasRecord = isPlainObject(opts.existingRecord) && Object.keys(opts.existingRecord).length > 0;
    if (hasRecord) {
      return { tier: "high", auto: true, reason: `matched by ${lane}`, candidates: [] };
    }
    return { tier: "none", auto: false, reason: "searched, no hit", candidates: [] };
  }

  if (lane === "name") {
    if (candidates.length > 0) {
      return { tier: "medium", auto: false, reason: "candidate(s) found by name+company, unverified", candidates };
    }
    return { tier: "none", auto: false, reason: "searched, no hit", candidates: [] };
  }

  // lane "none" (or anything unrecognized): there was no searchable identity, so the
  // search never ran — this is a "could not look", not a "did not find one".
  return { tier: "unknown", auto: false, reason: "no searchable identity — the row has no email, object id, or name+company pair", candidates: [] };
}

module.exports = { laneOf, mediumCandidates, summarizeMatch };
