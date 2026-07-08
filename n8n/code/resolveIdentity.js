// resolveIdentity.js — pure-JS contact identity resolver for n8n Code nodes.
//
// Mirrors src/identity.py resolve_identity EXACTLY, including the core safety rule:
// a row with no valid email can NEVER be net_new. Auto-match only on STRONG keys
// (email / linkedin_url); every weak-key hit routes to ambiguous (needs_review).
//
// PURE: the actual HubSpot searches happen upstream in an n8n HubSpot node. This
// function receives their results pre-fetched as `searchResultsByKey`, a map keyed
// by the search/match name -> array of candidate ids:
//   { email:[ids], linkedin_url:[ids], phone_lastname:[ids], name_company:[ids] }
// A missing key is treated as zero hits.

const { normalizeEmailBasic } = require("./normalizeEmail");
const { normalizePhoneAU } = require("./normalizePhone");

// Deterministic LinkedIn key — mirrors identity.canonicalize_linkedin.
function canonicalizeLinkedin(url) {
  if (!url) return null;
  let s = String(url).trim();
  if (s === "") return null;
  if (!s.includes("//")) s = "https://" + s;
  let scheme = "", rest = s;
  const schemeIdx = s.indexOf("//");
  if (schemeIdx > 0) {
    scheme = s.slice(0, schemeIdx - 1); // drop the ':' before '//'
    rest = s.slice(schemeIdx + 2);
  } else {
    rest = s.slice(schemeIdx + 2);
  }
  // rest = host[/path][?query][#frag]
  let host = rest, path = "";
  const slash = rest.indexOf("/");
  if (slash >= 0) {
    host = rest.slice(0, slash);
    path = rest.slice(slash);
  }
  // drop query/fragment
  path = path.split("?")[0].split("#")[0];
  if (path.endsWith("/")) path = path.slice(0, -1);
  return scheme.toLowerCase() + "://" + host.toLowerCase() + path;
}

function _ids(searchResultsByKey, key) {
  const v = searchResultsByKey && searchResultsByKey[key];
  return Array.isArray(v) ? v.map(String) : [];
}

function resolveIdentity(row, searchResultsByKey) {
  row = row || {};
  searchResultsByKey = searchResultsByKey || {};

  const email = normalizeEmailBasic(row.email); // null if absent OR malformed
  const linkedin = canonicalizeLinkedin(row.linkedin_url);
  const phone = normalizePhoneAU(row.phone);
  const firstname = String(row.firstname || "").trim();
  const lastname = String(row.lastname || "").trim();
  const company = String(row.company || "").trim();

  // 1. Email (STRONG). A valid email is the ONLY route to net_new.
  if (email) {
    const ids = _ids(searchResultsByKey, "email");
    if (ids.length === 1) {
      return { outcome: "match", contact_id: ids[0], match_key: "email",
               candidate_ids: ids, reason: "single email match" };
    }
    if (ids.length > 1) {
      return { outcome: "ambiguous", contact_id: null, match_key: "email",
               candidate_ids: ids, reason: "multiple email matches" };
    }
    return { outcome: "net_new", contact_id: null, match_key: null,
             candidate_ids: [], reason: "valid email, no existing match" };
  }

  // 2. No valid email past here. LinkedIn (STRONG).
  if (linkedin) {
    const ids = _ids(searchResultsByKey, "linkedin_url");
    if (ids.length === 1) {
      return { outcome: "match", contact_id: ids[0], match_key: "linkedin_url",
               candidate_ids: ids, reason: "single linkedin match" };
    }
    if (ids.length > 1) {
      return { outcome: "ambiguous", contact_id: null, match_key: "linkedin_url",
               candidate_ids: ids, reason: "multiple linkedin matches" };
    }
    // 0 hits -> fall through to weak keys.
  }

  // 3. Weak keys: a hit here is NEVER confident -> only ever ambiguous (review).
  if (phone && lastname) {
    const ids = _ids(searchResultsByKey, "phone_lastname");
    if (ids.length) {
      return { outcome: "ambiguous", contact_id: null, match_key: "phone_lastname",
               candidate_ids: ids, reason: "weak-key match requires review" };
    }
  }

  if (firstname && lastname && company) {
    const ids = _ids(searchResultsByKey, "name_company");
    if (ids.length) {
      return { outcome: "ambiguous", contact_id: null, match_key: "name_company",
               candidate_ids: ids, reason: "weak-key match requires review" };
    }
  }

  // 4. HARD SAFETY RULE: no valid email AND no confident match AND no weak-key
  // candidate -> ambiguous, NEVER net_new.
  return { outcome: "ambiguous", contact_id: null, match_key: null,
           candidate_ids: [], reason: "no email, insufficient identity" };
}

module.exports = { resolveIdentity, canonicalizeLinkedin };
