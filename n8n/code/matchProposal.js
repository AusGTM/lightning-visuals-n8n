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
// laneOf(row) -> "fetch_by_id" | "email" | "linkedin" | "name" | "none"
//   The `fetch_by_id` branch mirrors `IF Bare Event`'s boolean expression exactly
//   (scripts/build_cloud_workflows.py, `IF Bare Event` node build):
//     !!$('Build Identity').item.json.object_id &&
//     !$('Build Identity').item.json.identity_keys.email
//   If the two predicates ever drift, a row is routed to one lane and filtered into
//   another and silently disappears (36-CONTEXT.md key_links).
//
// Phase 61 Plan 02 (D-61-05 CORRECTED): the `linkedin` lane, positioned after `email`
// (email wins when both are present, mirroring resolveIdentity.js's own strong-key
// ordering) and before `name` (linkedin is a strong key and outranks the weak
// lastName+companyName pair, D-61-03).

const { canonicalizeLinkedin } = require("./resolveIdentity");

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
  const linkedinUrl = trimmedOrValue(identityKeys.linkedin_url);
  const lastName = trimmedOrValue(identityKeys.lastName);
  const companyName = trimmedOrValue(identityKeys.companyName);

  if (objectId && !email) return "fetch_by_id";
  if (email) return "email";
  if (linkedinUrl) return "linkedin";
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

// toCandidateShape(hit) — projects a raw HubSpot search hit down to the six-key
// candidate surface every match-lane proposal exposes to the caller. Shared by
// mediumCandidates (name lane) and verifiedLinkedinHits (linkedin lane) so both
// lanes' "unverified/ambiguous candidate" shape can never drift apart.
function toCandidateShape(hit) {
  const props = hit.properties || {};
  return {
    hs_object_id: hit.id,
    firstname: props.firstname != null ? props.firstname : null,
    lastname: props.lastname != null ? props.lastname : null,
    email: props.email != null ? props.email : null,
    jobtitle: props.jobtitle != null ? props.jobtitle : null,
    company: props.company != null ? props.company : null,
  };
}

// mediumCandidates(searchResults, identityKeys, opts) — re-verifies every HubSpot search
// hit BY VALUE before reporting it as a candidate. `CONTAINS_TOKEN` is fuzzy by design; a
// hit surviving the server-side filter is not yet a verified match (the BUG 22b lesson,
// applied prophylactically here — never trust that the search already filtered).
//
// `opts.requireCompanyToken` (F1, 2026-08-25, default true — every existing 2-arg call
// site is byte-identical): false is the WEAKER fallback search's re-verification, used
// when the lastname+company search returns zero hits. Live mechanism: a contact created
// by the ingest lane is associated to a company OBJECT and leaves the `company` TEXT
// property null (contact 347569451461 / Football NSW, execution 11948) — re-checking a
// company token that is blank by construction would filter the one true candidate back
// out, which is exactly why the fallback search drops the company filter in the first
// place rather than loosening it. In that mode `firstName` (when the caller supplied
// one) narrows the match instead: the weaker search has no company signal at all, so a
// common surname would otherwise surface every namesake in the portal as an "ambiguous"
// candidate. The company-token-verified path already has a strong signal and gains
// nothing from a nickname/spelling firstname mismatch silently dropping a true
// candidate, so this narrowing is scoped to the fallback path only.
function mediumCandidates(searchResults, identityKeys, opts) {
  const idKeys = isPlainObject(identityKeys) ? identityKeys : {};
  const lastName = trimmedOrValue(idKeys.lastName);
  const companyName = trimmedOrValue(idKeys.companyName);
  if (!lastName || !companyName || !Array.isArray(searchResults)) return [];

  const options = isPlainObject(opts) ? opts : {};
  const requireCompanyToken = options.requireCompanyToken !== false;
  const firstName = requireCompanyToken ? null : trimmedOrValue(idKeys.firstName);

  const wantLastName = String(lastName).toLowerCase();
  const wantFirstName = firstName ? String(firstName).toLowerCase() : null;
  const out = [];
  for (const hit of searchResults) {
    if (!isPlainObject(hit) || !isPlainObject(hit.properties)) continue;
    const props = hit.properties;
    const hitLastName = props.lastname == null ? "" : String(props.lastname).toLowerCase();
    if (hitLastName !== wantLastName) continue;
    if (requireCompanyToken && !sharesToken(props.company, companyName)) continue;
    if (wantFirstName) {
      const hitFirstName = props.firstname == null ? "" : String(props.firstname).toLowerCase();
      if (hitFirstName !== wantFirstName) continue;
    }
    out.push(toCandidateShape(hit));
  }
  return out;
}

// linkedinAgreement(props) — the value `props.lv_linkedin_url` and `props.hs_linkedin_url`
// agree on, canonicalized, or null when neither is present. REVIEW-02/T-61-05: when BOTH
// properties are present on the same contact and canonicalize to DIFFERENT profiles, the
// record disagrees with itself and this returns null (never one of the two answers) — a
// self-disagreeing record is not a verified hit under any of its own values.
function linkedinAgreement(props) {
  const p = isPlainObject(props) ? props : {};
  const lv = canonicalizeLinkedin(p.lv_linkedin_url);
  const hs = canonicalizeLinkedin(p.hs_linkedin_url);
  if (lv && hs && lv !== hs) return null;
  return lv || hs || null;
}

// verifiedLinkedinHits(searchResults, rawLinkedinUrl) — re-verifies every HubSpot search
// hit BY VALUE (never trusts the server-side filter as a verdict, mirroring
// mediumCandidates' discipline for a strong key): a hit counts only when
// linkedinAgreement(hit.properties) canonicalizes to the SAME value as the row's own
// linkedin_url. Deduplicates by contact id (T-61-05/REVIEW-02: a contact matching under
// both lv_linkedin_url and hs_linkedin_url is ONE hit, not two) and returns the raw
// verified hits (id + properties) — cardinality and shaping are the caller's job, because
// the caller needs the FULL hit to build existingRecord on a single verified match.
function verifiedLinkedinHits(searchResults, rawLinkedinUrl) {
  const wanted = canonicalizeLinkedin(rawLinkedinUrl);
  if (!wanted || !Array.isArray(searchResults)) return [];
  const seen = new Set();
  const out = [];
  for (const hit of searchResults) {
    if (!isPlainObject(hit) || !isPlainObject(hit.properties) || hit.id == null) continue;
    const id = String(hit.id);
    if (seen.has(id)) continue;
    if (linkedinAgreement(hit.properties) !== wanted) continue;
    seen.add(id);
    out.push(hit);
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

  // Phase 61 Plan 02 Task 1, REVIEW-C4: a DEDICATED arm, never joined to the
  // fetch_by_id/email arm above. That arm reads `existingRecord` alone and is
  // two-outcome by construction (matchProposal.js:128-133); linkedin is three-outcome
  // (0/1/>1 verified hits) and needs its own cardinality read. `candidates` here is the
  // caller-supplied array of ALREADY-VERIFIED hits (verifiedLinkedinHits' output, shaped
  // via toCandidateShape) — not an unverified CONTAINS_TOKEN proposal like the name lane.
  if (lane === "linkedin") {
    if (candidates.length === 1) {
      return { tier: "high", auto: true, reason: "matched by linkedin", candidates: [] };
    }
    if (candidates.length > 1) {
      return { tier: "medium", auto: false, reason: "multiple verified linkedin matches — never a pick", candidates };
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

// isReturnOnly(mode) — the propose-mode write-guard predicate (36-CONTEXT.md §6/§4
// decision 1). Deliberately NOT an allow-list of mode names: two states, no third.
// `mode` absent/null or the write literal (case- and whitespace-insensitive) is `false`
// (today's write behaviour, byte-identical); every other value — including a typo — is
// `true` (return-only). That asymmetry is the fail-safe: an unrecognised value can only
// ever fail TOWARD returning proposals, never toward writing. String() never throws, so
// this never throws for any input.
function isReturnOnly(mode) {
  if (mode === undefined || mode === null) return false;
  return String(mode).trim().toLowerCase() !== "write";
}

module.exports = {
  laneOf, mediumCandidates, summarizeMatch, isReturnOnly,
  linkedinAgreement, verifiedLinkedinHits, toCandidateShape,
};
