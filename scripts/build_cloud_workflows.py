#!/usr/bin/env python3
# scripts/build_cloud_workflows.py
#
# Milestone 3 Wave B build step. n8n Cloud Code nodes CANNOT require() sibling
# files or npm, so each Code node must carry a FULLY SELF-CONTAINED copy of the
# Wave-A module functions it needs. This script is the single source of truth:
# it reads n8n/code/*.js, strips the `require(...)`/`module.exports` lines, and
# inlines the needed functions into each Code node body, then emits both:
#   - n8n/wf_contact_ingest_cloud.json  (production-shaped, REAL HubSpot/HTTP nodes)
#   - n8n/wf_contact_ingest_local.json  (locally-executable, HubSpot mocked)
#
# Re-run after editing any n8n/code/*.js module to regenerate the workflows.
#
# ponytail: generating JSON from Python (json.dump handles all escaping) beats
# hand-transcribing JS into JSON string literals — no drift, no escape bugs.

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "n8n" / "code"

# Regenerate the taxonomy data module FIRST — before any inline() call below reads
# n8n/code/taxonomy.generated.js — so this builder can never emit a workflow carrying
# a stale vocabulary (spec TX-4/AR-4). gen_taxonomy_js.py is a sibling script; running
# this file directly (`python scripts/build_cloud_workflows.py`) puts scripts/ on
# sys.path[0], so the plain import resolves.
import gen_taxonomy_js  # noqa: E402
import gen_escalation_js  # noqa: E402
import provider_registry  # noqa: E402 — Phase 16.1 (reviews A3): SIDE-EFFECT-FREE, no
# codegen write happens on this import (unlike gen_taxonomy_js/gen_escalation_js above) —
# a read-only importer (Plan 02's check_provider_credits.py) can pull PROVIDER_REGISTRY
# without triggering the two writes below.

(CODE / "taxonomy.generated.js").write_text(gen_taxonomy_js.render())
(CODE / "escalation.generated.js").write_text(gen_escalation_js.render())

# June-2026 validation dataset (Phase 41, 41-CONTEXT.md D-08): read at module scope, same
# discipline as the two codegen writes above -- the "Merge Company" node inlines the
# `rows` object as a JS constant so this builder can never emit a workflow carrying a
# stale table. No separate gen_*_js.py / .generated.js pair: ENRICH_MERGE_CO is the
# table's only consumer and there is no cross-module reuse (Task 1 action note). Defaults
# to {} when the config file does not exist yet, so a fresh checkout can still build.
_JUNE_CANDIDATES_PATH = ROOT / "config" / "june_candidates.json"
if _JUNE_CANDIDATES_PATH.exists():
    JUNE_CANDIDATES_ROWS = json.loads(_JUNE_CANDIDATES_PATH.read_text())["rows"]
else:
    JUNE_CANDIDATES_ROWS = {}
JUNE_CANDIDATES_JS = "const JUNE_CANDIDATES = " + json.dumps(JUNE_CANDIDATES_ROWS) + ";\n"

# Phase 70 Plan 10 (D-70-23): the reserved key a starved-lane sentinel's GATE stamps
# onto its one marker item (`_add_starved_lane_sentinel`, `_sentinel_gate_js`), defined
# once here — near the top, before any Code-node-body string that needs to reference it
# as an f-string interpolation — and read by every consumer that must never mistake a
# marker for a real row on a shared Merge input.
SENTINEL_MARKER_KEY = "_gsd_sentinel_marker"

# ---- module inliner ---------------------------------------------------------

_REQUIRE_RE = re.compile(r"^\s*const\s*\{[^}]*\}\s*=\s*require\(")
_REQUIRE_OPEN_RE = re.compile(r"^\s*const\s*\{\s*$")  # multi-line destructuring require, opening line
_EXPORTS_RE = re.compile(r"^\s*module\.exports")


def strip_module(name: str) -> str:
    """Load a Wave-A module, drop require() lines (single- or multi-line destructuring —
    Phase 13: n8n/code/taxonomy.js's `require` spans 4 lines, which _REQUIRE_RE alone
    does not match per-line) and everything from the first `module.exports` onward
    (exports are always the module's trailing statement, and may span multiple lines —
    truncating avoids orphaning the export body)."""
    src = (CODE / name).read_text()
    kept = []
    skipping_multiline_require = False
    for ln in src.splitlines():
        if _EXPORTS_RE.match(ln):
            break
        if skipping_multiline_require:
            if "require(" in ln:
                skipping_multiline_require = False
            continue
        if _REQUIRE_RE.match(ln):
            continue
        if _REQUIRE_OPEN_RE.match(ln):
            skipping_multiline_require = True
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def inline(*modules: str) -> str:
    """Concatenate stripped modules (dependency order matters for the reader)."""
    return "\n\n".join(strip_module(m) for m in modules)


# D-70-12 (Phase 70 Plan 05 Task 1): the single canonical write-request shape every gated
# write's upstream decide/set node must emit — `{action, hs_object_id, domain, email}`,
# exactly those four keys. The four-way identity fallback ladder `_write_gate_js` used to
# carry (two live incidents' worth of "the row didn't have the field the gate reads") is
# deleted, not extended; every emitting node calls this ONE shared helper instead of
# growing its own copy of the ladder. The create-row email-domain derivation — a create
# has no `hs_object_id`, so its email domain is its only allowlist path — moves in here,
# once: `action` decides whether the derivation applies, so a non-create call passing a
# real `domain` is never second-guessed, and a `null` domain a caller passes ON PURPOSE
# (the review lane's contacts-stay-id-only rule, D-70-13) is never overridden either.
# Defined here (near the top of the module, ahead of every Code-node-body constant that
# embeds it) rather than beside WRITE_SAFETY_GATE_JS/_write_safety_const, which are
# composed at build sites specifically BECAUSE they depend on constants defined later in
# this module (see "D-16b" at this file's ingest builder) — this helper has no such
# dependency, so module-level string concatenation (`+ WRITE_REQUEST_JS +`) works at every
# call site, early or late, without that workaround.
def _write_request_js() -> str:
    """Embedded verbatim into every decide/set Code node that feeds a gated write (same
    no-shared-runtime constraint as WRITE_SAFETY_GATE_JS — Code nodes cannot require()
    each other). Defines `_buildWriteRequest(action, hsObjectId, domain, email)`; callers
    pass their own row's fields and assign the result to `write_request` on their return
    object. `assert_write_request_emitters` (below) checks for this function's own name
    in a gated write's upstream Code node jsCode at generation time."""
    return r"""
function _buildWriteRequest(action, hsObjectId, domain, email) {
  var d = domain || null;
  if (!d && action === "create" && email && String(email).indexOf("@") !== -1) {
    d = String(email).split("@").pop().toLowerCase();
  }
  return { action: action, hs_object_id: hsObjectId || null, domain: d, email: email || null };
}
"""


WRITE_REQUEST_JS = _write_request_js()


# ---- Code-node bodies (inlined module + n8n I/O wrapper) --------------------
# Every wrapper runs "Once for All Items": read $input.all() (or reference a
# prior node by name to preserve rows across the collapse→HTTP→expand hop),
# return [{json:...}].

MAP_COLUMNS = inline("columnMap.js") + r"""

// --- n8n wrapper: map arbitrary upload headers -> canonical props ---
const rows = $input.all();
const out = [];
for (const it of rows) {
  const raw = it.json;
  const mapped = mapRow(raw);
  const ok = requiredIdentity(mapped);
  out.push({ json: {
    ...mapped,
    allow_create: raw.allow_create === true,
    // Phase 70 Plan 02 (D-70-04): mapRow() drops every key outside its own alias
    // table, same reason `allow_create` above is re-added explicitly — `source_by_field`
    // (broadcast onto every row by the "combineAll" merge between "Extract From File"
    // and this node) would otherwise be lost here, before "Merge Contacts" ever reads it.
    source_by_field: raw.source_by_field || {},
    reject: !ok,
    ...(ok ? {} : {
      outcome: "rejected",
      reject_reason: "missing required identity (need email OR firstname+lastname+company)"
    })
  }});
}
return out;
"""

NORMALIZE_PHONE = inline("normalizePhone.js") + r"""

// --- n8n wrapper: AU-heuristic phone -> E.164 (null => review) ---
return $input.all().map((it) => {
  const row = it.json;
  return { json: { ...row, phone_normalized: normalizePhoneAU(row.phone) } };
});
"""

BUILD_VERIFY_BATCH = inline("normalizeEmail.js") + r"""

// --- n8n wrapper: collapse rows -> ONE item {emails:[...]} for the batch API ---
// Phase 70 Plan 02 (D-70-04): `_rows` carries the N pre-collapse rows THROUGH the
// batch call as a NESTED field on this same one-item output — "Verify Emails (batch)"'s
// own jsonBody sends only `$json.emails` (HTTP_VERIFY), so `_rows` never reaches the
// external API. The carry-merge spliced after that HTTP node re-attaches this item
// (still 1-item, matching the HTTP response's own 1-item count) so "Apply Email" reads
// both the verifier's `results` and its own N rows back via $input, never by name.
const rows = $input.all();
const emails = [];
const seen = new Set();
for (const it of rows) {
  const e = normalizeEmailBasic(it.json.email);
  if (e && !seen.has(e)) { seen.add(e); emails.push(e); }
}
return [{ json: { emails, _rows: rows.map((it) => it.json) } }];
"""

APPLY_EMAIL = inline("normalizeEmail.js") + r"""

// --- n8n wrapper: merge the batch verifier response back onto every row ---
// Phase 70 Plan 02 (D-70-04): this node's own direct predecessor is now the carry
// merge spliced after "Verify Emails (batch)" — $input's ONE item carries BOTH
// `_rows` (the N pre-collapse rows "Build Verify Batch" nested through the API call)
// and `results` (the verifier's own response), so both reads are $input, never a
// by-name lookup of an upstream node.
const carried = ($input.first() && $input.first().json) || {};
const rows = (carried._rows || []).map((json) => ({ json }));
const results = carried.results || [];
const byEmail = {};
for (const r of results) { if (r && r.email) byEmail[String(r.email).toLowerCase()] = r; }

return rows.map((it) => {
  const row = it.json;
  const e = normalizeEmailBasic(row.email);
  let vres;
  if (!e) {
    vres = { status: "NO_EMAIL" };
  } else if (byEmail[e]) {
    vres = { status: byEmail[e].status };
  } else {
    vres = { status: "PROBABLY_VALID", _fallback: true };  // verifier unreachable -> non-gating
  }
  const applied = applyEmailVerification(row, vres);
  return { json: {
    ...row,
    ...applied,
    email_status: vres.status,
    email_verify_fallback: vres._fallback === true
  }};
});
"""

# LOCAL ONLY: canned HubSpot search results so resolveIdentity exercises every path.
HUBSPOT_SEARCH_MOCK = r"""// HubSpot Search (MOCK) — LOCAL variant only.
// Cloud uses a real n8n-nodes-base.hubspot search node; here we return canned
// results so resolveIdentity exercises match / net_new / ambiguous:
//   bob.smith@example.com -> email hit contact "200"  => match
//   alice@example.com     -> 0 hits                    => net_new
//   Carol Jones/Some Company (no email) -> name_company hit "300" => ambiguous (weak key)
//   Dave Nguyen (no email, no weak hit) -> hard-safety  => ambiguous
return $input.all().map((it) => {
  const row = it.json;
  const email = String(row.email_normalized || row.email || "").toLowerCase().trim();
  const srk = {};
  if (email === "bob.smith@example.com") srk.email = ["200"];
  const nameKey = [
    String(row.firstname || "").toLowerCase().trim(),
    String(row.lastname || "").toLowerCase().trim(),
    String(row.company || "").toLowerCase().trim(),
  ].join("|");
  if (nameKey === "carol|jones|some company") srk.name_company = ["300"];
  return { json: { ...row, searchResultsByKey: srk } };
});
"""

# CLOUD ONLY: adapt the real HubSpot search node's output into searchResultsByKey.
ADAPT_SEARCH_RESULTS = r"""// Adapt Search Results — CLOUD variant.
// Maps the real HubSpot "Search by Email" node output into the searchResultsByKey shape
// resolveIdentity expects. A search with 0 hits yields an empty id list => net_new.
//
// BUG 22b (found live 2026-07-29, execution 21): the old adapter indexed `search[i]` and
// took ANY id it found. The native search node FLATTENS results into one item per contact
// — so `search[0]` was simply the first contact the search returned, and (stacked on the
// then-empty filter, BUG 22a) a made-up email "matched" an arbitrary real record. Index
// alignment against a flattened list is unsound for multi-row uploads even with the
// filter fixed. Match by VALUE instead: a hit counts only if the candidate's own email
// equals this row's normalized email — order-independent, multi-row safe, and immune to
// an unfiltered search (100 wrong contacts contribute zero hits).
//
// Phase 36 Finding B (36-CONTEXT.md §5B): `lookup_failed` below is declared OUTSIDE the
// per-row loop, so ONE failed search item stamps the whole batch. That used to be
// reachable by a legitimate emailless row (the `.invalid` sentinel on `HubSpot Search by
// Email`'s filter value fixes that upstream). Now that a legitimate row can no longer
// manufacture this flag, the scope is deliberate: it can only be set by a genuine
// HubSpot search failure, where fail-closed on the whole batch is the correct answer.
// This scope is intentionally NOT narrowed to per-row here — out of scope for this fix.
//
// Phase 70 Plan 02 (D-70-04): this node's own direct predecessor is now the carry
// merge spliced after "HubSpot Search by Email" — each of $input's N items is already
// {...searchResponse_i, ...applyEmailRow_i} (the row wired last, per merge_node's
// resolveClash: "preferLast"), so both the search envelope and the row ride the SAME
// item. carry_source = "Apply Email" (not "Normalize Phone", the by-name read this
// replaces): "Apply Email" is this hop's OWN literal predecessor AND carries the
// richer, later row (email_status/email_valid) that "Normalize Phone" never had — the
// old by-name read silently dropped those fields before they ever reached "Decide
// Action" (Rule 1 bug, fixed as a side effect of retiring the read, not a separate
// change).
const merged = $input.all().map((it) => it.json);
const candidates = [];
let lookup_failed = false;
for (const m of merged) {
  // onError:continueRegularOutput puts a failed search in the ITEM (the Lusha/ZoomInfo
  // masking mechanism). Treating an errored search as "no hits" would read as net_new and
  // duplicate-create once creates are armed — the enrichment lanes' lookup_failed pattern
  // applies here identically.
  if (m.error || m.status === "error") { lookup_failed = true; continue; }
  if (Array.isArray(m.results)) {                          // CRM v3 search envelope
    for (const c of m.results) if (c && c.id) candidates.push(c);
  } else if (m.id) {                                        // single-object result (fixtures)
    candidates.push(m);
  }
}
function candidateEmail(c) {
  return normalizeEmailBasicSafe((c.properties && c.properties.email) || c.email);
}
return merged.map((m) => {
  const row = { ...m };
  delete row.results; delete row.total; delete row.error; delete row.status;
  const rowEmail = normalizeEmailBasicSafe(row.email_normalized || row.email);
  const hits = [];
  if (rowEmail) {
    for (const c of candidates) {
      if (candidateEmail(c) === rowEmail) hits.push(String(c.id));
    }
  }
  const srk = {};
  if (rowEmail && hits.length) srk.email = hits;
  return { json: { ...row, searchResultsByKey: srk, lookup_failed } };
});

function normalizeEmailBasicSafe(raw) {
  if (raw === null || raw === undefined) return null;
  const s = String(raw).trim().toLowerCase();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) ? s : null;
}
"""

RESOLVE_IDENTITY = inline("normalizeEmail.js", "normalizePhone.js", "resolveIdentity.js") + r"""

// --- n8n wrapper: strong-key auto-match, weak keys -> review, no-email never net_new ---
return $input.all().map((it) => {
  const row = it.json;
  if (row.reject) {
    return { json: { ...row, identity: { outcome: "rejected", contact_id: null,
      match_key: null, candidate_ids: [], reason: row.reject_reason || "missing identity" } } };
  }
  const identity = resolveIdentity(row, row.searchResultsByKey || {});
  return { json: { ...row, identity } };
});
"""

MERGE_CONTACTS = inline("mergeContacts.js") + r"""

// --- n8n wrapper: deterministic non-clobber merge (email never promotes) ---
// PN-1: linkedin_url is NOT HubSpot-native (absent from the verified-native list) -> the
// MERGE CANDIDATE / canonical field key is lv_linkedin_url. `row.linkedin_url` (the raw
// mapped-column name from columnMap.js) stays unprefixed on the READ side — only the
// write-side candidate key renames.
// Phase 62 Plan 04 (D-62-17): a round-level per-field source map, originally sourced
// by a NODE-NAME read of 'Set Config' — D-16b's reason still holds (a row-seeded value
// does not survive Extract From File's fresh-item parse), but Phase 70 Plan 02
// (D-70-04) closes it differently: a "combineAll" broadcast merge (cartesian, 1 config
// item x N csv rows) spliced between "Extract From File" and "Map Columns" stamps
// `source_by_field` onto every row BEFORE the fresh-item parse can drop it, and
// "Map Columns" re-adds it explicitly (mapRow drops any key outside its own alias
// table, the same reason it already re-adds `allow_create`). Reading `row.source_by_field`
// here is therefore just $json, never a by-name lookup — and degrades to {} exactly as
// before on any row that never carries the key at all (build_local()'s workflow has no
// "Set Config" node and no caller has ever sent this field on a plain CSV upload).
return $input.all().map((it) => {
  const row = it.json;
  const sourceByField = row.source_by_field || {};
  const candidate = {};
  for (const f of ["email", "firstname", "lastname", "jobtitle", "company"]) {
    if (row[f] != null && String(row[f]).trim() !== "") candidate[f] = row[f];
  }
  if (row.linkedin_url != null && String(row.linkedin_url).trim() !== "") {
    candidate.lv_linkedin_url = row.linkedin_url;
  }
  if (row.phone_normalized) candidate.phone = row.phone_normalized;
  // LOCAL/template: no existing HubSpot props fetched here => {} (blanks promote per policy).
  const merged = mergeContacts({}, candidate, undefined,
    { source: "csv", confidence: 80, sourceByField });
  return { json: { ...row, merge: merged } };
});
"""

DECIDE_LOCAL = r"""// Decide Action (dry-run echo) — LOCAL variant.
// Replaces the HubSpot update/create write nodes: ECHOES the would-be payload,
// performs NO real write. `create` stays gated behind allow_create (default false).
// Phase 15: this is the SINGLE serialization point for the provenance blob — the
// stamper (mergeContacts.js) returns the parsed provenance object, never a string.
function _sortedForStringify(v) {
  if (Array.isArray(v)) return v.map(_sortedForStringify);
  if (v !== null && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = _sortedForStringify(v[k]);
    return out;
  }
  return v;
}
function _stableStringify(v) { return JSON.stringify(_sortedForStringify(v)); }
function _buildContactPatch(merge) {
  if (!merge) return {};
  const patch = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}) };
  if (merge.provenance && Object.keys(merge.provenance).length) {
    patch.lv_contact_enrichment_provenance = _stableStringify(merge.provenance).slice(0, 60000);
  }
  return patch;
}

return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity || {};
  const outcome = id.outcome || "rejected";
  const allow_create = row.allow_create === true;
  const patch = _buildContactPatch(row.merge);
  let action, hubspot_op = null;
  if (outcome === "match") {
    action = "update";
    hubspot_op = { method: "PATCH", endpoint: "/crm/v3/objects/contacts/" + id.contact_id, properties: patch };
  } else if (outcome === "net_new") {
    if (allow_create) {
      action = "create";
      // BUG 19: canonicalPatch never contains identity (email is manual_protected — right
      // for an update, wrong for a create, where identity is the one thing that MUST be
      // written or the record can never be matched again). Seed it from the ingest row,
      // create branch ONLY — seeding on update would be the clobber the policy prevents.
      if (row.email) patch.email = row.email;
      if (row.firstname) patch.firstname = row.firstname;
      if (row.lastname) patch.lastname = row.lastname;
      hubspot_op = { method: "POST", endpoint: "/crm/v3/objects/contacts", properties: patch };
    } else {
      action = "review";  // create gated off => route to review queue
    }
  } else if (outcome === "ambiguous") {
    action = "review";
  } else {
    action = "skip";      // rejected: failed required-identity gate
  }
  return { json: {
    email: row.email || null,
    name: [row.firstname, row.lastname].filter(Boolean).join(" ") || null,
    outcome,
    action,
    match_key: id.match_key || null,
    candidate_ids: id.candidate_ids || [],
    reason: id.reason || row.reject_reason || null,
    email_status: row.email_status || null,
    email_valid: row.email_valid === true,
    email_verify_fallback: row.email_verify_fallback === true,
    allow_create,
    dry_run: true,
    hubspot_op
  }};
});
"""

# ---- contact -> company association lane (ingest, 2026-08-25) ---------------
# Operator ruling: a contact must ALWAYS be associated with a company, and a company that
# already exists must NEVER be recreated. The lane resolves — it never creates a company:
# an unresolved row is HELD at Decide Action rather than landing an orphan contact or a
# junk company shell. The company lane in wf_enrichment_cloud already owns company
# creation + dedupe on the same `domain` anchor.

BUILD_COMPANY_LINK = inline("companyLink.js") + r"""

// --- n8n wrapper: per-row company search keys (one item in, one item out) ---
// The `.invalid` sentinels are the Phase 36 Finding B idiom: a filter value that is
// `undefined` makes HubSpot reject the whole search (swallowed by
// onError:continueRegularOutput into an error item), while an RFC 2606 `.invalid` value
// returns a clean 200 with zero hits. Sentinel in, empty result out, row order preserved.
return $input.all().map((it) => {
  const row = it.json;
  return { json: { ...row,
    company_search_domain: companyDomainForRow(row) || "no-company-domain.invalid",
    company_search_name: companyNameForRow(row) || "no company name .invalid",
  }};
});
"""

CO_LINK_DOMAIN_SEARCH_BODY = (
    '={{ JSON.stringify({ filterGroups: [ { filters: [ { propertyName: "domain", '
    'operator: "EQ", value: $json.company_search_domain } ] } ], '
    'properties: ["name","domain"], limit: 5 }) }}'
)

# Phase 70 Plan 02 (D-70-04): this hop's OWN direct predecessor after the carry merge
# spliced behind "HubSpot Company Search by Domain" is "Stash Domain Search" — the row
# rides $json directly now, never a $() lookup of "Build Company Link" (whose response
# would no longer even be this node's own predecessor once a hop sits between them).
CO_LINK_NAME_SEARCH_BODY = (
    '={{ JSON.stringify({ filterGroups: [ { filters: [ { propertyName: "name", '
    'operator: "EQ", value: $json.company_search_name } ] } ], '
    'properties: ["name","domain"], limit: 5 }) }}'
)

# Phase 70 Plan 02 (D-70-04): spliced immediately after "HubSpot Company Search by
# Domain"'s carry merge. Both that search's response and the Name search's own response
# (spliced after IT) are `{total, results}` envelopes — combining them by position on
# the SAME item would let the second clash-overwrite the first (merge_node's
# resolveClash: "preferLast"). Nesting the domain response under
# `_company_domain_search` here, BEFORE the name search runs, is what keeps the two
# separate all the way to "Adapt Company Link".
STASH_DOMAIN_SEARCH = r"""// Stash Domain Search — see build_cloud_workflows.py's own
// comment at this node's call site for why the domain search's response is nested
// rather than left at the top level.
return $input.all().map((it) => {
  const { results, total, error, ...row } = it.json;
  return { json: { ...row, _company_domain_search: { results, total, error } } };
});
"""

ADAPT_COMPANY_LINK = inline("companyLink.js") + r"""

// --- n8n wrapper: resolve each row's company id from the two searches ---
// Phase 70 Plan 02 (D-70-04): this node's own direct predecessor is now the carry
// merge spliced after "HubSpot Company Search by Name" — every $input item already
// carries the row's own fields, the NAME search's response at the top level
// (results/total/error), and the DOMAIN search's response nested under
// `_company_domain_search` ("Stash Domain Search" put it there for exactly this
// reason). No $() lookup, no index alignment against a separately-fetched list.
return $input.all().map((it) => {
  const { results, total, error, _company_domain_search, ...row } = it.json;
  const byName = { results, total, ...(error !== undefined ? { error } : {}) };
  const byDomain = _company_domain_search || {};
  const link = resolveCompanyLink(row, byDomain, byName);
  return { json: { ...row, ...link } };
});
"""

BUILD_ASSOCIATION_REQUEST = inline("companyLink.js") + WRITE_REQUEST_JS + r"""

// --- n8n wrapper: written contact -> association request ---
// Phase 70 Plan 02 (D-70-04): this node's own direct predecessor is now a carry merge
// spliced after "HubSpot Update"/"HubSpot Create" (carry_source = each write's own
// Write Gate) — every $input item already carries BOTH the write's HTTP response
// (`id`, `properties`) AND the pre-write row Decide Action stamped (`company_id`,
// `company_domain`, `company_match`, `row_id`, `email`), combined by position with the
// carried row wired LAST (merge_node's resolveClash: "preferLast"). No by-name read of
// "Decide Action", no separate join-by-value search over a fetched list — the pairing
// already happened at the merge, and item count/order agree by construction (a literal
// fan-out of the same delivery feeds both the HTTP node and this node's other input).
return $input.all().map((it) => {
  const row = it.json || {};
  // `row.id` is what HubSpot minted/confirmed for THIS write; `row.hs_object_id` is the
  // pre-write value the carried row already had (null for a create — the contact did
  // not exist before this write — kept only as a defensive fallback).
  const contactId = row.id != null ? String(row.id) : (row.hs_object_id ? String(row.hs_object_id) : null);
  if (!contactId) return null;
  const email = String(row.email || (row.properties && row.properties.email) || "").toLowerCase();
  const company_id = row.company_id ? String(row.company_id) : null;
  // An UPDATE with no resolved company is not held (the contact already exists, and it
  // may already carry an association this lane cannot see) — it simply has nothing to
  // associate. Only creates are held, at Decide Action.
  if (!company_id) return null;
  return { json: {
    action: "enrich",
    hs_object_id: contactId,
    contact_id: contactId,
    email: email || null,
    domain: row.company_domain || null,
    company_id,
    company_match: row.company_match || null,
    assoc_url: associationUrl(contactId, company_id),
    // Phase 70 Plan 02 (D-70-01/D-70-04): carried so "Build Ingest Response" can join
    // this association attempt back to its row BY VALUE — the same join key Decide
    // Action already emits pre-write.
    row_id: row.row_id ?? null,
    // D-70-12 (Phase 70 Plan 05 Task 1): "HubSpot Associate Company Write Gate" reads
    // only this now — same action/id/domain/email the fields above already compute.
    write_request: _buildWriteRequest("enrich", contactId, row.company_domain || null, email || null),
  }};
}).filter(Boolean);
"""

BUILD_INGEST_RESPONSE = r"""// Build Ingest Response — the lane's per-row report, now read from the settled
// execution's runData (D-70-05/D-70-07), never from the synchronous webhook body.
// Phase 70 Plan 02 (D-70-01/D-70-04): sits behind "Ingest Merge Response", a
// THREE-input append-mode Merge: the association lane, the review lane, and
// "Decide Action Snapshot" — a tagged, literal fan-out of "Decide Action"'s own full
// row set (a single-producer node, safe to fan out further; this is the full ground
// truth this node needs even for a row that was written but never reached the
// association lane at all, e.g. an update with no company to associate, dropped at
// "Build Association Request"). No node is read by name any more — every input
// arrives on $input, distinguished by the `_decided_snapshot` tag "Decide Action
// Snapshot" stamps (a real association attempt never carries it; a starved lane's
// harmless sentinel marker carries neither the tag nor an `action` field at all).
//
// [Rule 1 - Bug, found writing this task's own carry-merge test] `arrived` used to be
// "any item with an `action` field" — but "Set Review" ALSO feeds this Merge (D-70-01),
// and its contribution is the row's OWN ORIGINAL decided action/email/company_id
// untouched. A review row that DOES resolve a company (association: "not_confirmed" is
// the correct report — nothing ever tried to associate it) self-matched against its
// OWN Set-Review contribution by email, misreporting "associated". `action: "enrich"`
// is the literal, unique stamp only "Build Association Request" ever writes — never a
// value Decide Action itself produces — so filtering on it (not merely "has an action")
// admits a real association attempt and nothing else.
// Phase 70 Plan 10 (D-70-23): a starved-lane sentinel's marker is already excluded by
// construction below (it carries neither `_decided_snapshot` nor a matching `action`),
// but this is the explicit, defensive filter every consumer of the reserved key must
// carry — belt-and-braces against a future change to the predicates below ever
// admitting one by accident.
const allItems = $input.all().map((it) => it.json).filter(Boolean)
  .filter((row) => row.__SENTINEL_MARKER_KEY__ !== true);
const decided = allItems.filter((row) => row._decided_snapshot === true);
const arrived = allItems.filter((row) => row._decided_snapshot !== true && row.action === "enrich");
// Phase 70 Plan 05 Task 2 sub-step 2c (D-70-06): the write gates now EMIT the rows they
// refuse (D-70-14) straight onto this Merge, carrying `action: "write_blocked"` plus a
// reason. The decided snapshot still says "update"/"create" for those rows — reporting
// it unchanged is exactly the misreport execution 12181 showed (Greg Purcell's blocked
// update reported as landed). The gate's verdict is the write node's own answer, so it
// wins here. This is what replaces the pre-write precheck: a report, not a prediction.
const blocked = allItems.filter((row) =>
  row._decided_snapshot !== true && row.action === "write_blocked");
const blockedByRowId = {};
const blockedByContactId = {};
const blockedByEmail = {};
for (const row of blocked) {
  if (row.row_id) blockedByRowId[String(row.row_id)] = row;
  if (row.hs_object_id) blockedByContactId[String(row.hs_object_id)] = row;
  if (row.email) blockedByEmail[String(row.email).toLowerCase()] = row;
}
const byRowId = {};
const byContactId = {};
const byEmail = {};
for (const row of arrived) {
  if (row.row_id) byRowId[String(row.row_id)] = row;
  if (row.contact_id) byContactId[String(row.contact_id)] = row;
  if (row.email) byEmail[String(row.email).toLowerCase()] = row;
}
return decided.map((row) => {
  const email = String((row.properties && row.properties.email) || row.email || "").toLowerCase();
  const assoc = (row.row_id && byRowId[String(row.row_id)]) ||
                (row.hs_object_id && byContactId[String(row.hs_object_id)]) ||
                (email && byEmail[email]) || null;
  const contactId = (assoc && assoc.contact_id) || row.hs_object_id || row.contact_id || null;
  const block = (row.row_id && blockedByRowId[String(row.row_id)]) ||
                (row.hs_object_id && blockedByContactId[String(row.hs_object_id)]) ||
                (email && blockedByEmail[email]) || null;
  let association;
  if (!row.company_id) {
    association = "none";
  } else if (assoc) {
    association = "associated";
  } else {
    association = "not_confirmed";  // never reached the write gate, or HubSpot refused it
  }
  return { json: {
    action: block ? "write_blocked" : row.action,
    outcome: block ? "write_blocked" : (row.outcome || null),
    contact_id: contactId,
    hs_object_id: contactId,
    email: email || null,
    company_id: row.company_id || null,
    company_match: row.company_match || null,
    // A refused write never reached the association lane either — one verdict covers
    // both (D-70-15), so it cannot report "associated".
    association: block && association === "associated" ? "not_confirmed" : association,
    reason: (block && block.write_blocked_reason) || row.reason || null,
    email_status: row.email_status || null,
    // 57-02 Task 4 (AFTER-01's join key): `Decide Action` already emits `row_id`
    // pre-write. Closes the join for every lane whose rows carry `row_id` into the
    // backend. Does NOT close it for the pair pipeline's FINAL ingest dispatch —
    // `extraction.strip_row_id` removes the key before `write_dispatch_csv`
    // (enrich-before-ingest/SKILL.md:639), so those rows echo `null` here regardless.
    row_id: row.row_id ?? null,
  }};
});
""".replace("__SENTINEL_MARKER_KEY__", SENTINEL_MARKER_KEY)

# Phase 70 Plan 02 (D-70-04): fed directly from "Set Config" — the ONE place the JSON
# STRING form of the multipart `source_by_field` field (dispatch.py's `filename=None`
# idiom, D-62-17) gets parsed. Its single output item is broadcast onto every CSV row
# by a "combineAll" merge spliced between "Extract From File" and "Map Columns", so the
# value survives Extract From File's fresh-item parse (D-16b) without any downstream
# node reading "Set Config" by name.
SET_CONFIG_FIELDS = r"""// Set Config Fields — parses the round-level source map once, for the "combineAll"
// broadcast merge to fan onto every row.
function _sourceByFieldFromEnvelope(cfg) {
  const body = (cfg && (cfg.body ?? cfg)) || {};
  let map = (body && typeof body === 'object') ? body.source_by_field : null;
  if (typeof map === 'string') {
    try { map = JSON.parse(map); } catch (e) { map = null; }
  }
  return (map && typeof map === 'object' && !Array.isArray(map)) ? map : {};
}
const cfg = ($input.first() && $input.first().json) || {};
return [{ json: { source_by_field: _sourceByFieldFromEnvelope(cfg) } }];
"""

# Phase 70 Plan 02 (D-70-01/D-70-04): fed directly from "Decide Action" — a literal
# fan-out of a single-producer node (one inbound edge, one run per execution), safe
# under the same rule detect_by_name_reads exists to enforce. Tags every row so
# "Build Ingest Response" can split its $input into "the full decided set" vs "a real
# lane contribution" without a by-name read of either.
DECIDE_ACTION_SNAPSHOT = r"""// Decide Action Snapshot — see build_cloud_workflows.py's
// own comment at this node's call site.
return $input.all().map((it) => ({ json: { ...it.json, _decided_snapshot: true } }));
"""

DECIDE_CLOUD = r"""// Decide Action — CLOUD variant.
// Computes action + the HubSpot property patch, then the IF nodes route to the
// real HubSpot update/create (gated) / Set review nodes.
// Phase 15: this is the SINGLE serialization point for the provenance blob — the
// stamper (mergeContacts.js) returns the parsed provenance object, never a string.
function _sortedForStringify(v) {
  if (Array.isArray(v)) return v.map(_sortedForStringify);
  if (v !== null && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = _sortedForStringify(v[k]);
    return out;
  }
  return v;
}
function _stableStringify(v) { return JSON.stringify(_sortedForStringify(v)); }
function _buildContactPatch(merge) {
  if (!merge) return {};
  const patch = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}) };
  if (merge.provenance && Object.keys(merge.provenance).length) {
    patch.lv_contact_enrichment_provenance = _stableStringify(merge.provenance).slice(0, 60000);
  }
  return patch;
}

return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity || {};
  const outcome = id.outcome || "rejected";
  // D-16/D-16a/D-16b: this used to read row.allow_create, a field seeded on the webhook
  // item at Set Config — but Extract From File emits fresh items parsed from the binary
  // CSV, so nothing seeded upstream of it survives to here (BUG 12/BUG 21 row-loss
  // family). The sole authority is the baked ALLOW_HUBSPOT_CREATE constant this node
  // declares (composed at the build site, prepended ahead of this jsCode) — the SAME
  // overlayable constant HubSpot Create Write Gate downstream already reads, so arming
  // creation here still requires that gate's allowlist too. Not OR'd with a row value.
  const allow_create = String(ALLOW_HUBSPOT_CREATE).toLowerCase() === "true";
  const properties = _buildContactPatch(row.merge);
  let action;
  if (outcome === "match") action = "update";
  else if (outcome === "net_new") action = allow_create ? "create" : "review";
  else if (outcome === "ambiguous") action = "review";
  else action = "skip";
  // Fail-closed, mirroring the enrichment lanes' lookup_failed -> never-create override:
  // a "net_new" produced by a FAILED search is not a new contact, it is an unknown.
  if (row.lookup_failed === true && action === "create") action = "review";
  // Operator ruling 2026-08-25: a contact must ALWAYS be associated with a company. A
  // create with no resolved company is HELD, not landed — an orphan contact is silent
  // and permanent, a held row is visible and one operator answer away (name the company
  // record id on the row, or create/enrich the company first). Creates only: an update
  // targets a record that already exists and may already carry an association this lane
  // cannot see, so holding it would block ordinary enrichment for no gain.
  let company_hold = null;
  if (action === "create" && !row.company_id) {
    action = "review";
    company_hold = row.company_hold_reason || "no company matched this contact";
  }
  if (action === "create") {
    // BUG 19: identity is never in canonicalPatch (manual_protected), so a create without
    // this seed writes a record the by-email search can never find again — and the next
    // run creates another. Create branch ONLY; on update this would be a clobber.
    if (row.email) properties.email = row.email;
    if (row.firstname) properties.firstname = row.firstname;
    if (row.lastname) properties.lastname = row.lastname;
    // 37-CONTEXT.md §13(b) / operator's option-b ruling (resolves 37-07's checkpoint):
    // stamp the poller's work-queue flag so a freshly created contact is swept by the
    // already-deployed scheduled poller (daily cadence since 2026-08-10) with no further operator action. This
    // is a work-queue flag the poller searches for, NOT a write gate — it grants no
    // permission and opens no write path (ALLOW_HUBSPOT_CREATE above already gates this
    // whole branch). Create branch ONLY for the same reason the identity seeds above are:
    // an update targets a record whose enrichment state the operator may already have
    // curated, and re-flagging it would re-queue work that was deliberately finished.
    properties.lv_enrichment_requested = "true";
  }
  // F12 (uat-batch-review-row-reads-failed, execution 12181): "HubSpot Update Write
  // Gate" (downstream, spliced by splice_write_gates) filters its input to nothing
  // when the allowlist refuses a row — a Code node emitting [] never fires its own
  // outgoing connection (the same "wave dropping" semantics as "IF Company Skip"'s
  // Phase 70 Plan 05 Task 2 sub-step 2c (D-70-06): the pre-write refusal PRECHECK that
  // used to sit here — a second copy of `_writeSafetyAllows`, added 2026-09-09 after
  // execution 12181 reported Greg Purcell's blocked update as if it had landed — is
  // GONE. It predicted the gate's verdict instead of reporting it, which is a copy that
  // can disagree (its own comment admitted as much: create rows were deliberately left
  // uncovered precisely because reproducing the create gate's email-domain derivation
  // here risked a false "write_blocked"). The row's outcome of record is now the write
  // node's own output: "HubSpot Update/Create Write Gate" EMITS a refused row (D-70-14)
  // carrying `action: "write_blocked"` and a reason, and "Build Ingest Response"
  // overlays that verdict onto the decided snapshot. Create rows are covered by
  // construction, closing the follow-up the precheck filed
  // (.planning/todos/pending/2026-09-09-ingest-create-row-has-no-write-blocked-precheck.md).
  return { json: {
    action,
    outcome,
    // BUG 16: this lane historically emitted only `contact_id`, while the write nodes and
    // the write-safety gates spliced in Phase 16.10 both read `hs_object_id` — so the
    // gates evaluated _writeSafetyAllows(action, null, null) and denied unconditionally,
    // whatever the allowlist said. Emitting both converges this lane on the same row
    // contract the enrichment lane uses. `contact_id` is retained: Resolve Identity and
    // the response path still read it.
    contact_id: id.contact_id || null,
    hs_object_id: id.contact_id || null,
    reason: company_hold || id.reason || row.reject_reason || null,
    email_status: row.email_status || null,
    // The association lane's row context (2026-08-25). `company_id` is what Build
    // Association Request joins on; `email` makes a created row identifiable in the
    // synchronous response before HubSpot has minted its id.
    email: row.email_normalized || row.email || null,
    company_id: row.company_id || null,
    company_match: row.company_match || null,
    company_domain: row.company_domain || null,
    // F11 (uat-batch-review-row-reads-failed, execution 12181): "HubSpot Update Write
    // Gate" (spliced in front of "HubSpot Update" by splice_write_gates, action
    // "enrich") reads a row's domain as `identity_keys.domain || json.domain` — neither
    // of which this lane ever emitted, so a domain-only TEST_RECORD_DOMAINS allowlist
    // could never admit an update (Greg Purcell, execution 12181: gate emitted 0 items,
    // HubSpot Update never ran). Same class of gap as BUG 24 (Review Search omitting
    // `domain`) — fixed the same way: populate the field the gate already reads, not
    // the shared gate itself (widening the gate's fallback logic would also reach the
    // scheduled-maintenance "enrich" call sites, an unreviewed scope change). Scoped to
    // NON-create actions only: "HubSpot Create Write Gate" already derives its own
    // allowlist domain from the row's email (BUG 27) when no `domain` is present, and a
    // create's `company_domain` is the ASSOCIATED company, not necessarily the
    // contact's own email domain — populating `domain` there too would silently change
    // which domain the create gate checks (caught live by
    // contactCreateGateFlow.test.mjs's BUG 27 regression).
    domain: action !== "create" ? (row.company_domain || null) : null,
    // D-70-12 (Phase 70 Plan 05 Task 1): the canonical shape "HubSpot Update Write
    // Gate"/"HubSpot Create Write Gate" now read EXCLUSIVELY — same action/id/domain
    // values the fields above already computed for the (now-deleted) fallback ladder,
    // stamped once through the shared helper rather than re-derived at the gate.
    write_request: _buildWriteRequest(
      action, id.contact_id || null,
      action !== "create" ? (row.company_domain || null) : null,
      row.email_normalized || row.email || null
    ),
    properties
  }};
});
"""

# ---- workflow assembly helpers ---------------------------------------------

_idc = [0]


def nid(prefix="n"):
    _idc[0] += 1
    return f"{prefix}{_idc[0]:04d}0000-0000-4000-8000-000000000000"



# Phase 70 Plan 10 (D-70-23): every "identity-less sentinel marker" filter idiom that
# predates the gated sentinel (a bare `{}` used to BE the marker, so `Object.keys(it.json
# || {}).length > 0` was enough to drop it) now also excludes the reserved marker key —
# a gated sentinel's marker is stamped with `SENTINEL_MARKER_KEY: true` so it is never
# mistakable for a real row (D-70-23's own acceptance criterion), which means it is no
# longer a bare `{}` and the OLD idiom alone would let it through. Rewritten in `code_node`
# below, once, for every Code node this builder emits — never per call site — so every
# response builder that already used this idiom keeps working without an edit at its own
# definition.
_OLD_MARKER_FILTER_JS = "Object.keys(it.json || {}).length > 0"
_NEW_MARKER_FILTER_JS = (
    f"{_OLD_MARKER_FILTER_JS} && it.json[{SENTINEL_MARKER_KEY!r}] !== true"
)


def code_node(name, js, x, y):
    js = js.replace(_OLD_MARKER_FILTER_JS, _NEW_MARKER_FILTER_JS)
    return {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": js},
        "id": nid("c"), "name": name,
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [x, y],
    }


def chain(names):
    """Linear main-connection between consecutive node names."""
    conns = {}
    for a, b in zip(names, names[1:]):
        conns[a] = {"main": [[{"node": b, "type": "main", "index": 0}]]}
    return conns


def fan(*chains):
    """Merge linear chains that share nodes, fanning out on collision instead of
    overwriting. Used where one trigger feeds several sibling branches."""
    conns = {}
    for c in chains:
        for node, spec in c.items():
            if node not in conns:
                conns[node] = {"main": [list(spec["main"][0])]}
                continue
            for target in spec["main"][0]:
                if target not in conns[node]["main"][0]:
                    conns[node]["main"][0].append(target)
    return conns


# ---- LOCAL workflow ---------------------------------------------------------

FIXTURE_EMIT = r"""// Emit Fixture Rows (mock parsed file) — LOCAL variant.
// Represents the output of a parsed CSV upload. CLOUD instead uses
// Webhook-upload -> Extract-from-File to produce these same raw rows.
// Headers are deliberately messy (aliases) to exercise columnMap.
const rows = [
  { "Email Address": "bob.smith@example.com", "First Name": "Bob", "Last Name": "Smith", "Job Title": "New Title From Upload", "Phone": "0412 345 678", "Company": "Example Co", "LinkedIn": "https://linkedin.com/in/bob-upload" },
  { "Email Address": "alice@example.com", "First Name": "Alice", "Last Name": "Anderson", "Job Title": "Analyst", "Phone": "0400 111 222", "Company": "Example Media", "LinkedIn": "" },
  { "Email Address": "", "First Name": "Carol", "Last Name": "Jones", "Job Title": "Coordinator", "Phone": "0400 222 333", "Company": "Some Company", "LinkedIn": "" },
  { "Email Address": "", "First Name": "Dave", "Last Name": "Nguyen", "Job Title": "Manager", "Phone": "", "Company": "Another Company", "LinkedIn": "" },
  { "Email Address": "", "First Name": "", "Last Name": "", "Job Title": "Just A Title", "Phone": "0400 999 888", "Company": "", "LinkedIn": "" }
];
const allow_create = false;  // create gated OFF in the local proof
return rows.map((r) => ({ json: { ...r, allow_create } }));
"""

HTTP_VERIFY = {
    "parameters": {
        "method": "POST",
        "url": "https://rapid-email-verifier.fly.dev/api/validate/batch",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={ "emails": {{ JSON.stringify($json.emails) }} }',
        "options": {"timeout": 20000},
    },
    "id": nid("h"),
    "name": "Verify Emails (batch)",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [0, 0],
    # non-gating: if the verifier is unreachable, keep going (Apply Email falls back).
    "onError": "continueRegularOutput",
}


def build_local():
    nodes = []
    y = 300
    x = 260
    manual = {"parameters": {}, "id": nid("t"), "name": "Manual Trigger",
              "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [x, y]}
    nodes.append(manual)

    seq = [
        ("Emit Fixture Rows", FIXTURE_EMIT),
        ("Map Columns", MAP_COLUMNS),
        ("Normalize Phone", NORMALIZE_PHONE),
        ("Build Verify Batch", BUILD_VERIFY_BATCH),
    ]
    for name, js in seq:
        x += 220
        nodes.append(code_node(name, js, x, y))

    x += 220
    http = dict(HTTP_VERIFY)
    http["position"] = [x, y]
    nodes.append(http)

    tail = [
        ("Apply Email", APPLY_EMAIL),
        ("HubSpot Search (MOCK)", HUBSPOT_SEARCH_MOCK),
        ("Resolve Identity", RESOLVE_IDENTITY),
        ("Merge Contacts", MERGE_CONTACTS),
        ("Decide Action", DECIDE_LOCAL),
    ]
    for name, js in tail:
        x += 220
        nodes.append(code_node(name, js, x, y))

    order = ["Manual Trigger", "Emit Fixture Rows", "Map Columns", "Normalize Phone",
             "Build Verify Batch", "Verify Emails (batch)", "Apply Email",
             "HubSpot Search (MOCK)", "Resolve Identity", "Merge Contacts", "Decide Action"]

    note = {
        "parameters": {"content": (
            "## LV Contact Ingest — LOCAL (headless-executable)\n"
            "Same Wave-A JS as the Cloud template, inlined into Code nodes.\n"
            "**Mocked for local run:** file input -> Emit Fixture Rows; HubSpot "
            "search/update/create -> Code mocks (dry-run echo, NO real writes).\n"
            "**REAL:** the email verifier HTTP node calls the live free API.\n"
            "AU-phone normalizer is a heuristic; non-AU/ambiguous -> null -> review."
        ), "height": 260, "width": 420},
        "id": nid("s"), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [260, 520],
    }
    nodes.append(note)

    conns = chain(order)
    # Phase 70 Plan 02 (D-70-04): the same carry merge as build_cloud() — APPLY_EMAIL
    # is a SHARED Code body between the two workflows, and it now reads `_rows`/
    # `results` off $input rather than by name, so this hop needs the merge here too.
    splice_carry_merge_after(nodes, conns, "Verify Emails (batch)", "Build Verify Batch",
                             merge_name="Verify Email Carry Merge")

    return {
        "id": "LVcontactIngest01",
        "name": "LV Contact Ingest (local replica)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
    }


# ---- CLOUD workflow ---------------------------------------------------------

def build_cloud():
    nodes = []
    y = 300
    x = 220

    webhook = {
        # Security fix (found during activation day, 2026-07-29): this webhook shipped
        # UNAUTHENTICATED while the enrichment webhook has always required Header Auth —
        # anyone with the URL could submit CSVs. Same native headerAuth, same shared
        # "LV Enrichment Webhook" credential: both webhook nodes are named
        # "Webhook Trigger", so the existing NODE_CREDENTIAL_MAP entry binds this one
        # identically with zero deploy-script changes.
        # F10 (uat-batch-review-row-reads-failed, execution 12181): an unset
        # `responseData` defaults to `firstEntryJson` under `responseMode: lastNode` —
        # a multi-row `Build Ingest Response` output (one item per decided row)
        # collapsed to a single item at the webhook boundary. Live: a 2-row batch
        # (Greg's update, Barry's review) answered with Greg's item only; Barry's
        # review row never reached the client at all. `allEntries` is n8n's own
        # documented value for "return every item, not just the first"
        # (docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook).
        # D-70-07 (Phase 70 Plan 02): `responseNode` + a dedicated "Respond to Webhook"
        # fed ONLY by "Build Ingest Ack" — this lane's only responder. `responseData`
        # (`allEntries`, the F10 fix) no longer applies under `responseNode` and is
        # dropped; the ack's shape is fixed by "Build Ingest Ack" itself, not this param.
        "parameters": {"httpMethod": "POST", "path": "hubspot/contact-upload",
                       "responseMode": "responseNode",
                       "authentication": "headerAuth", "options": {}},
        "id": nid("w"), "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [x, y],
    }
    nodes.append(webhook)

    x += 220
    # BUG 21 (found live 2026-07-29, execution 20 — the workflow's FIRST EVER run): this
    # was an n8n-nodes-base.set v3.4, which drops the item's BINARY alongside the json it
    # already drops — so the uploaded CSV never reached Extract From File ("Make sure that
    # the previous node outputs a binary file") and the ingest lane could not process ANY
    # upload. Same mechanism as BUG 12 (Set v3.4 emitting only its assigned fields), one
    # payload channel over. Same twice-earned fix: a Code node whose behaviour this repo
    # can test offline — spread json, carry binary through explicitly.
    set_cfg = code_node("Set Config", r"""// Set Config — row-and-binary-carrying passthrough.
// BUG 21: the Set node this replaces dropped the webhook's binary CSV on the floor.
// D-16b: this row's `allow_create` is NOT the Cloud create gate any more — it does not
// survive Extract From File's fresh-item parse, and the real gate now lives at Decide
// Action, which reads the baked ALLOW_HUBSPOT_CREATE constant instead. This seed stays
// here only for the LOCAL/dry-run echo lane (DECIDE_LOCAL), which legitimately keeps
// reading a row-seeded gate.
// D-70-05/D-70-07 (Phase 70 Plan 02): normalizes the caller's own client-minted
// `run_id` (a multipart form FIELD, so n8n parses it into `$json.body.run_id` — the
// same `filename=None` idiom `source_by_field` already proves) and echoes it as this
// node's OWN output field. This is the ingest lane's echo node: `watch.
// _execution_carries_run_id` correlates a settled execution by finding THIS node's
// output carrying the requested `run_id`, exactly the mechanism the enrichment lane's
// "Parse HubSpot Event" already provides there. A request that carries no `run_id`
// echoes `null` — this lane keeps working for a caller that predates the change.
return $input.all().map((it) => {
  const body = it.json.body || {};
  return {
    json: { ...it.json, allow_create: false, run_id: body.run_id ?? it.json.run_id ?? null },
    binary: it.binary,
  };
});
""", x, y)
    nodes.append(set_cfg)

    # D-70-07: the lane's ONLY responder, fed directly from "Set Config" — before
    # "Extract From File" parses the uploaded CSV into rows, so `row_ids` is always
    # empty for this lane today (no per-row identity exists yet at ack time). Every
    # row's real outcome lives in the settled execution's runData (D-70-05), read via
    # `run_id` correlation on "Set Config"'s own echoed field above — never in this
    # body.
    build_ack = code_node("Build Ingest Ack", r"""// Build Ingest Ack — D-70-07: the lane's ONLY responder.
const item = ($input.first() && $input.first().json) || {};
return [{ json: { run_id: item.run_id ?? null, accepted: true, row_ids: [] } }];
""", x, y + 180)
    nodes.append(build_ack)
    respond = {
        "parameters": {"respondWith": "allIncomingItems", "options": {}},
        "id": nid("rw"), "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
        "position": [x + 220, y + 180],
    }
    nodes.append(respond)

    # Phase 70 Plan 02 (D-70-04): a THIRD fan-out off "Set Config" (alongside "Extract
    # From File" and "Build Ingest Ack") — parses `source_by_field` once. Its one output
    # item is broadcast onto every CSV row by a "combineAll" merge spliced right after
    # "Extract From File", below.
    nodes.append(code_node("Set Config Fields", SET_CONFIG_FIELDS, x, y + 360))

    x += 220
    extract = {
        "parameters": {"operation": "csv", "binaryPropertyName": "data", "options": {}},
        "id": nid("e"), "name": "Extract From File",
        "type": "n8n-nodes-base.extractFromFile", "typeVersion": 1, "position": [x, y],
    }
    nodes.append(extract)

    for name, js in [("Map Columns", MAP_COLUMNS), ("Normalize Phone", NORMALIZE_PHONE),
                     ("Build Verify Batch", BUILD_VERIFY_BATCH)]:
        x += 220
        nodes.append(code_node(name, js, x, y))

    x += 220
    http = dict(HTTP_VERIFY)
    http["id"] = nid("h")
    http["position"] = [x, y]
    nodes.append(http)

    x += 220
    nodes.append(code_node("Apply Email", APPLY_EMAIL, x, y))

    x += 220
    # BUG 22a (found live 2026-07-29, execution 21 — the lane's first COMPLETE run): this
    # node shipped with `filterGroupsValues: []` — an EMPTY filter, the BUG 11 family's
    # placeholder-never-populated shape — so the "search by email" returned the newest 100
    # contacts in the portal, unfiltered. Stacked on BUG 22b (the adapter taking the first
    # hit), a made-up canary email "matched" an arbitrary real contact; only the disarmed
    # write gate stopped a mis-targeted PATCH.
    #
    # Then execution 22, with the filter fixed on the native node: a no-match search emits
    # ZERO items and n8n stops the chain there — the lane dies exactly on ingest's primary
    # case (a genuinely new contact). The empty filter had been masking that by always
    # returning a full page. So the transport moves to the BUG 10 answer: a credential-
    # bound httpRequest POST to the real CRM v3 search endpoint, which returns the
    # {total, results} envelope as ONE item whether it matched or not. The adapter's
    # envelope branch already parses that shape. Same "LV HubSpot" credential via its
    # existing NODE_CREDENTIAL_MAP entry (cred_type hubspotAppToken binds identically on
    # an httpRequest node — the BUG 10 mechanism).
    # Phase 36 Finding B (36-CONTEXT.md §5B): an emailless row left this filter value
    # `undefined`. `JSON.stringify` drops an `undefined` object key, so HubSpot received
    # a filter with no `value` at all, rejected it, and `onError: continueRegularOutput`
    # (the BUG 22 transport, above) swallowed the rejection into the ITEM rather than
    # throwing. `ADAPT_SEARCH_RESULTS` below then stamped that one row's failure onto
    # `lookup_failed` for the WHOLE batch (its scope is declared outside the per-row
    # loop), demoting every sibling row's `create` action to `review` — this feature's
    # own re-upload path breaking on its own emailless output. The RFC 2606 `.invalid`
    # sentinel can never be a real address, so HubSpot now returns 200 with zero hits
    # instead of rejecting the filter, and `lookup_failed` stays false.
    hs_search = _http_node(
        "HubSpot Search by Email",
        "https://api.hubapi.com/crm/v3/objects/contacts/search", x, y,
        auth="hubspot",
        json_body=("={{ JSON.stringify({ filterGroups: [ { filters: [ { propertyName: "
                   "\"email\", operator: \"EQ\", value: ($json.email_normalized || $json.email || "
                   "\"no-email@invalid.invalid\") } ] } ], "
                   "properties: [\"email\", \"firstname\", \"lastname\", \"jobtitle\", \"phone\", "
                   "\"mobilephone\", \"hs_object_id\"], limit: 10 }) }}"),
    )
    nodes.append(hs_search)

    # D-16b: the create constant is composed HERE, at the build site, rather than at
    # DECIDE_CLOUD's module-level definition — _write_safety_const is defined later in
    # this module, so calling it at definition time would raise NameError. Prepending it
    # to this one node's jsCode (not Set Config, not the other three chain nodes) keeps
    # Decide Action the single Cloud-only place this lane reads the baked constant.
    # F12 added the WHOLE of WRITE_SAFETY_GATE_JS here so this node could pre-compute an
    # update's write-safety verdict itself. Phase 70 Plan 05 Task 2 sub-step 2c (D-70-06)
    # deleted that precheck, so the node is back to needing exactly ONE baked constant:
    # ALLOW_HUBSPOT_CREATE, which routes create-vs-review — a decision about WHAT the row
    # is, not whether it may be written. `_writeSafetyAllows` and the allowlists live in
    # the spliced gates now, which is also where arming happens.
    # D-70-12 (Phase 70 Plan 05 Task 1): also needs `_buildWriteRequest` — DECIDE_CLOUD's
    # own return object stamps `write_request` on every row it emits.
    decide_action_js = (_write_safety_const("ALLOW_HUBSPOT_CREATE") + "\n"
                        + WRITE_REQUEST_JS + DECIDE_CLOUD)
    for name, js in [("Adapt Search Results", ADAPT_SEARCH_RESULTS),
                     ("Resolve Identity", RESOLVE_IDENTITY),
                     ("Merge Contacts", MERGE_CONTACTS),
                     ("Build Company Link", BUILD_COMPANY_LINK)]:
        x += 220
        nodes.append(code_node(name, js, x, y))

    # Contact -> company resolution (2026-08-25). Both searches fire for every row —
    # ponytail: two reads per row instead of a branch that would break index alignment;
    # HubSpot search calls are free and this lane is batch-sized, not per-request. Upgrade
    # path if the rate limit ever bites: skip the name search when the domain hit.
    x += 220
    nodes.append(_http_node(
        "HubSpot Company Search by Domain",
        "https://api.hubapi.com/crm/v3/objects/companies/search", x, y,
        auth="hubspot", json_body=CO_LINK_DOMAIN_SEARCH_BODY))
    x += 220
    # Phase 70 Plan 02 (D-70-04): nests the domain search's own response so the carry
    # merge spliced after "HubSpot Company Search by Name" (below) never clashes the
    # two searches' identically-shaped `{total, results}` envelopes onto one key.
    nodes.append(code_node("Stash Domain Search", STASH_DOMAIN_SEARCH, x, y))
    x += 220
    nodes.append(_http_node(
        "HubSpot Company Search by Name",
        "https://api.hubapi.com/crm/v3/objects/companies/search", x, y,
        auth="hubspot", json_body=CO_LINK_NAME_SEARCH_BODY))

    for name, js in [("Adapt Company Link", ADAPT_COMPANY_LINK),
                     ("Decide Action", decide_action_js)]:
        x += 220
        nodes.append(code_node(name, js, x, y))

    # Phase 70 Plan 02 (D-70-01/D-70-04): a fan-out off "Decide Action" (single
    # producer, safe to read further downstream without a by-name lookup) feeding
    # "Ingest Merge Response" as its third input — the full ground truth "Build Ingest
    # Response" needs for a row that never reached either lane terminal at all.
    nodes.append(code_node("Decide Action Snapshot", DECIDE_ACTION_SNAPSHOT, x, y + 460))

    # IF Update -> HubSpot Update ; else IF Create -> HubSpot Create ; else Set Review
    x += 220
    if_update = _if_node("IF Update", "update", x, y)
    nodes.append(if_update)
    # BUG 11/13 reached wf_enrichment_cloud.json only; this lane kept the original
    # empty-field-map defect until 2026-07-29. Now on the same credential-bound PATCH node,
    # reading `hs_object_id` which Decide Action emits as of the BUG 16 fix above.
    nodes.append(_hs_http_patch_node("HubSpot Update", "contacts", x + 220, y - 120))

    if_create = _if_node("IF Create", "create", x + 220, y + 60)
    nodes.append(if_create)
    # Same BUG 13 shape as the enrichment lane's create node: `additionalFields: {}`
    # discarded the patch, and `$json.properties.email` can never resolve because `email`
    # is manual_protected and never promotes into the patch.
    nodes.append(_hs_http_create_node("HubSpot Create", "contacts", x + 440, y - 20))

    # F1's original fix made "Set Review" a dead end that "Build Ingest Response" never
    # needed to read (it reconstructed everything from "Decide Action" by name instead).
    # Phase 70 Plan 02 (D-70-01) inverts that: "Build Ingest Response" now reads $input
    # off an explicit Merge, so "Set Review"'s OWN output is what the review lane
    # contributes — it must be a Code node carrying the FULL decided row through (a Set
    # node here would drop every field but `queue`, the same BUG 12/21 class), not the
    # bare `{queue: "needs_review"}` shape it emitted before.
    nodes.append(code_node("Set Review", r"""// Set Review — the review lane's own contribution to "Ingest Merge Response".
// IF nodes only route; every item reaching here still carries Decide Action's full row
// (action/outcome/contact_id/company_id/reason/row_id/...). Also fed by "Review Lane
// Sentinel" on a batch where nothing would otherwise reach this node at all (every row
// routed to update/create) — that marker carries no other field, so it becomes
// `{queue: "needs_review"}` here and is dropped downstream as identity-less.
return $input.all().map((it) => ({ json: { ...it.json, queue: "needs_review" } }));
""", x + 440, y + 140))

    # Association subgraph (2026-08-25). Both write branches converge here; the v4
    # `default` endpoint is idempotent (re-running an ingest re-asserts the same
    # HubSpot-defined contact->company association rather than duplicating it), takes no
    # body, and needs no association-type ids.
    nodes.append(code_node("Build Association Request", BUILD_ASSOCIATION_REQUEST,
                           x + 660, y - 20))
    assoc = {
        "parameters": {"method": "PUT", "url": "={{ $json.assoc_url }}",
                       "authentication": "predefinedCredentialType",
                       "nodeCredentialType": "hubspotAppToken",
                       "options": {"timeout": 20000}},
        "id": nid("h"), "name": "HubSpot Associate Company",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [x + 880, y - 20],
        # No onError: a refused association must fail the execution like every other
        # write node in this lane, not flow on as a healthy item (BUG 11 family).
    }
    nodes.append(assoc)
    nodes.append(code_node("Build Ingest Response", BUILD_INGEST_RESPONSE,
                           x + 1320, y - 20))

    # D-70-01 (Phase 70 Plan 02): a GLOBAL, whole-batch check computed once from every
    # row "Decide Action" produced (fed by a fan-out off that single-producer node — safe
    # to read via $input directly, not a by-name read), one per lane. Each is the
    # mechanism that satisfies "Ingest Merge Response"'s two inputs on a single-lane
    # batch (research Pitfall 1) WITHOUT racing real content converging on the same
    # Merge from a slower path: a per-branch `alwaysOutputData` flag on "IF Update"/
    # "IF Create" was tried first and rejected, by hand-tracing the mixed-batch case
    # before writing this graph — "IF Create"'s own empty TRUE branch fires independently
    # of whether "IF Update"'s TRUE branch is ALSO carrying a real row toward the SAME
    # merge input in the SAME execution, and the offline walker's (and n8n's own,
    # verified via workflow-execute.ts::addNodeToBeExecuted) "wait for every configured
    # input" Merge semantics fire and lock on WHICHEVER pair of deliveries satisfies it
    # first — a fast marker beating a slow multi-hop real delivery would drop the real
    # row. A GLOBAL check is mutually exclusive with the real chain by construction (it
    # emits a marker only when NO row will ever traverse that chain at all), so it can
    # never race it.
    associate_sentinel_js = r"""// Associate Lane Sentinel — see build_cloud_workflows.py's own comment above this
// node's call site for why this is a global, single-producer check rather than a
// per-IF alwaysOutputData flag. `rows` is bound by `_add_starved_lane_sentinel`'s own
// template, above this body.
// Phase 70 Plan 05 Task 2 sub-step 2c: `company_id` is part of the question now. With
// the pre-write refusal precheck removed (D-70-06) a row can be action update/create and
// still never reach "HubSpot Associate Company": "Build Association Request" drops any
// row with no resolved company (CLAUDE.md §13.0.1 — an update is never HELD for lack of
// a company, it simply has nothing to associate). A batch of updates that all resolve no
// company would otherwise leave "Associate Carry Merge" with zero deliveries on both
// inputs and hang "Ingest Merge Response" forever. This stays a pre-gate check on
// purpose: a row the GATE refuses is covered by the gate's own false branch, which
// delivers to the very same "Ingest Merge Response" input this lane feeds.
// The `_writeSafetyAllows` call below is a duplicate of the gates' predicate, and is
// deliberately NOT a second authorization: it decides only whether this marker is needed
// to keep a Merge input fed. The real gates remain the sole place a write is permitted.
// Same pattern, for the same reason, as the review lane's own BUG-30 precheck. It is
// required because the marker shares "Ingest Merge Response"'s association-lane input
// with the real association delivery, so the two must be mutually EXCLUSIVE — a marker
// that fires while a real association is still in flight would satisfy the Merge early
// and the real arrival would be dropped (wire_gate_refusal_lane's docstring records the
// walker run that caught exactly that).
const anyAssoc = rows.some((r) => {
  if (!r || !r.company_id) return false;
  if (r.action !== "update" && r.action !== "create") return false;
  const wr = r.write_request;
  if (!wr) return false;
  return _writeSafetyAllows(r.action === "create" ? "create" : "enrich",
                            wr.hs_object_id || null, wr.domain || null);
});
return anyAssoc ? [] : [{}];
"""
    review_sentinel_js = r"""// Review Lane Sentinel — the review-side twin of "Associate Lane Sentinel". Fires
// only when EVERY row this execution decided is update/create (so "Set Review" would
// otherwise never even be enqueued at all, on a create-only or update-only batch).
// `rows` is bound by `_add_starved_lane_sentinel`'s own template, above this body.
const anyNonWrite = rows.some((r) => r && r.action !== "update" && r.action !== "create");
return anyNonWrite ? [] : [{}];
"""

    conns = chain([
        "Webhook Trigger", "Set Config", "Extract From File", "Map Columns",
        "Normalize Phone", "Build Verify Batch", "Verify Emails (batch)", "Apply Email",
        "HubSpot Search by Email", "Adapt Search Results", "Resolve Identity",
        "Merge Contacts", "Build Company Link", "HubSpot Company Search by Domain",
        # Phase 70 Plan 02 (D-70-04): "Stash Domain Search" sits between the two company
        # searches now — see its own call-site comment above.
        "Stash Domain Search", "HubSpot Company Search by Name", "Adapt Company Link",
        "Decide Action", "IF Update",
    ])
    # D-70-07: "Set Config" fans to "Extract From File" (the existing pipeline,
    # unchanged), "Build Ingest Ack" (the immediate response), AND "Set Config Fields"
    # (D-70-04's source_by_field parse) — all three receive the SAME items; neither
    # delays or gates the pipeline.
    conns["Set Config"]["main"][0].append({"node": "Build Ingest Ack", "type": "main", "index": 0})
    conns["Set Config"]["main"][0].append({"node": "Set Config Fields", "type": "main", "index": 0})
    conns.update(chain(["Build Ingest Ack", "Respond to Webhook"]))
    # D-70-01: "Decide Action" fans to "IF Update" (the existing pipeline, unchanged)
    # and "Decide Action Snapshot" (D-70-04's tagged full-row-set fan-out, "Ingest
    # Merge Response"'s third input) — both receive the SAME complete row set from
    # Decide Action's single run. The two sentinels (Associate Lane, Review Lane) fan
    # off the SAME node too, but that edge is wired by `_add_starved_lane_sentinel`
    # itself, below, once their real targets (`ingest_merge_response`, "Associate
    # Carry Merge") exist (Phase 70 Plan 10, D-70-23).
    conns["Decide Action"]["main"][0].append(
        {"node": "Decide Action Snapshot", "type": "main", "index": 0})
    conns["Decide Action Snapshot"] = {
        "main": [[{"node": "Build Ingest Response", "type": "main", "index": 0}]]}

    conns.update(chain(["Build Association Request", "HubSpot Associate Company", "Build Ingest Response"]))
    for write_node in ("HubSpot Update", "HubSpot Create"):
        conns[write_node] = {"main": [
            [{"node": "Build Association Request", "type": "main", "index": 0}]
        ]}
    # IF branches
    conns["IF Update"] = {"main": [
        [{"node": "HubSpot Update", "type": "main", "index": 0}],   # true
        [{"node": "IF Create", "type": "main", "index": 0}],        # false
    ]}
    conns["IF Create"] = {"main": [
        [{"node": "HubSpot Create", "type": "main", "index": 0}],   # true (gated)
        [{"node": "Set Review", "type": "main", "index": 0}],       # false
    ]}
    # F1 (uat-batch-review-row-reads-failed, run 377a913c…, execution 12147): a batch
    # where every row is held for review must still reach "Build Ingest Response" — the
    # explicit Merge in front of it (below) is what now makes that ONE run over every
    # row rather than a dead end.
    conns["Set Review"] = {"main": [
        [{"node": "Build Ingest Response", "type": "main", "index": 0}]
    ]}

    note = {
        "parameters": {"content": (
            "## LV Contact Ingest — CLOUD template\n"
            "Import to n8n Cloud, then add **HubSpot credentials** on the three "
            "HubSpot nodes (search / update / create).\n\n"
            "**Flow:** Webhook upload -> Extract-from-File -> inlined Code nodes "
            "(map/normalize/resolve/merge) -> IF(action) -> HubSpot update / "
            "create (GATED, off by default) / Set review.\n\n"
            "**Email verify:** real HTTP node -> rapid-email-verifier batch API "
            "(up to 100/call); non-gating fallback if unreachable.\n\n"
            "**AU-phone DISCLAIMER:** the inline JS is an AU-only heuristic (no "
            "libphonenumber in Code nodes). Non-AU / ambiguous numbers -> null -> "
            "review. Swap in a phone-validation API for global coverage."
        ), "height": 360, "width": 460},
        "id": nid("s"), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [220, 500],
    }
    nodes.append(note)

    # Phase 70 Plan 05 Task 3 (D-70-15): ONE verdict covers an update and its
    # association. The association PUT used to carry its own second `_writeSafetyAllows`
    # call, which could disagree with the verdict that already permitted the write it
    # runs downstream of (different action string, different domain source). It now runs
    # off that same permitted output, conditioned only on a resolved company id — which
    # "Build Association Request" already applies by dropping any row without one, per
    # CLAUDE.md §13.0.1: an update is NEVER held for lack of a company, it simply has
    # nothing to associate, and "Build Ingest Response" reports `association: "none"`.
    splice_write_gates(nodes, conns, {
        "HubSpot Update": "enrich",
        "HubSpot Create": "create",
    })

    # D-70-02/D-70-04 (Phase 70 Plan 02 Task 3): every carry merge on this lane, via the
    # one generalised helper. Each `carry_source` is the SAME delivery that feeds the
    # HTTP node it follows — either that node's own direct predecessor, or (for the
    # three write nodes) the write gate `splice_write_gates` just spliced in front of it
    # — so item count and order always agree between a merge's two inputs. Task 2's
    # hand-wired "Associate Carry Merge" is refactored onto this mechanism rather than
    # left as a second, driftable one-off.
    splice_carry_merge_after(nodes, conns, "HubSpot Update", "HubSpot Update Write Gate IF",
                             merge_name="Update Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Create", "HubSpot Create Write Gate IF",
                             merge_name="Create Carry Merge")
    # Phase 70 Plan 10 (D-70-23) ingest-lane audit: the two calls above each fan the
    # gate IF's TRUE branch straight onto its own carry Merge's second input
    # (`splice_carry_merge_after`'s `carry_source` contract) — a routing IF with a
    # direct edge to a Merge input, same class as the refusal-lane edge already
    # retargeted below. Route it through a pass-through for the same reason: this repo
    # has never observed whether the live engine treats an IF's own empty branch as a
    # delivery, and a Merge input must not depend on the answer either way.
    for _carry_write, _carry_merge_name in (
            ("HubSpot Update", "Update Carry Merge"), ("HubSpot Create", "Create Carry Merge")):
        _retarget_merge_edge_through_passthrough(
            nodes, conns, f"{_carry_write} Write Gate IF", 0, _carry_merge_name,
            f"{_carry_write} Permitted Pass-Through", 40, 760)
    splice_carry_merge_after(nodes, conns, "HubSpot Associate Company",
                             "Build Association Request",
                             merge_name="Associate Carry Merge")
    splice_carry_merge_after(nodes, conns, "Verify Emails (batch)", "Build Verify Batch",
                             merge_name="Verify Email Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Search by Email", "Apply Email",
                             merge_name="Search By Email Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Company Search by Domain", "Build Company Link",
                             merge_name="Company Domain Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Company Search by Name", "Stash Domain Search",
                             merge_name="Company Name Carry Merge")
    # combineAll (cartesian, never combineByPosition): one "Set Config Fields" item
    # broadcast onto every one of "Extract From File"'s N rows — a genuine 1-to-N
    # relationship, not a per-item HTTP hop.
    splice_carry_merge_after(nodes, conns, "Extract From File", "Set Config Fields",
                             merge_name="Source By Field Broadcast", combine_by="combineAll")

    # D-70-01/D-70-23 (Phase 70 Plan 10): "Build Association Request" is fed by BOTH
    # "Update Carry Merge" and "Create Carry Merge" — a genuine two-lane convergence
    # this repo had left un-merged (each carry Merge's own delivery just dispatched the
    # Code node separately). An explicit APPEND Merge here is what D-70-01 requires for
    # any node fed by two lanes, and it is also the safe home for this plan's
    # "never-stall" sentinels (below, via `carry_merge=`): a marker landing on an
    # APPEND input is inert here (the node's own `if (!contactId) return null` drops
    # it), unlike a marker forced onto either `combineByPosition` carry Merge's OWN
    # input, which would pair with the OTHER input's real content into a fabricated
    # write response (Rule 1, found running this task's own suite).
    build_association_request_merge = splice_merge_before(
        nodes, conns, "Build Association Request",
        merge_name="Build Association Request Merge")

    # D-70-01: the three inbound edges into "Build Ingest Response" ("Associate Carry
    # Merge", "Set Review", "Decide Action Snapshot") become one explicit, append-mode
    # Merge — the converged node runs ONCE over every row instead of once per inbound
    # edge.
    ingest_merge_response = splice_merge_before(
        nodes, conns, "Build Ingest Response", merge_name="Ingest Merge Response")

    # Phase 70 Plan 10 (D-70-23): the two ingest-lane sentinels, now wired through
    # `_add_starved_lane_sentinel`'s gated "condition -> gate -> targets" shape (the
    # class fix) rather than hand-wired straight to a Merge input. Created here,
    # after `ingest_merge_response` and "Associate Carry Merge" both exist, because
    # the association sentinel's real target is an INDEX on the former, resolved off
    # the latter's own already-spliced edge.
    #
    # The association sentinel targets "Ingest Merge Response"'s own association-lane
    # input — the SAME input "Associate Carry Merge" feeds — rather than either input
    # of that carry Merge itself (D-70-20's carry-Merge bypass, D-70-23's amendment
    # audited against this lane): a marker on BOTH inputs of a positional
    # (combineByPosition) carry Merge would pair with itself into one fabricated row
    # (T-70-41); a marker on the carry Merge's own CONSUMER is inert and mutually
    # exclusive with the carry Merge's own real delivery by construction (the carry
    # Merge only ever fires when an association actually ran).
    assoc_carry_idx = _merge_input_index(conns, "Associate Carry Merge", ingest_merge_response)
    _add_starved_lane_sentinel(
        nodes, conns, "Review Lane Sentinel", "Decide Action", review_sentinel_js,
        [("Set Review", 0)], 60, 1180)
    _add_starved_lane_sentinel(
        nodes, conns, "Associate Lane Sentinel", "Decide Action",
        WRITE_SAFETY_GATE_JS + associate_sentinel_js,
        [(ingest_merge_response, assoc_carry_idx)], 60, 1020)

    # Phase 70 Plan 05 Task 2 sub-step 2c (D-70-14): each write gate's REFUSAL lane gets
    # its OWN "Ingest Merge Response" input, never a share of the association lane's —
    # see wire_gate_refusal_lane's docstring for the armed-mixed-batch drop that ruled
    # sharing out. With the D-70-06 precheck gone this is the ONLY path a refused row has
    # to the response, and it is what lets "Build Ingest Response" report the gate's
    # actual verdict rather than the pre-write intention. No `mirror_index` here: this
    # merge's write-lane input is fed straight by "Associate Lane Sentinel" (Phase 70
    # Plan 10, D-70-23 — the sentinel now bypasses "Associate Carry Merge" and targets
    # this exact input), so the "gate never ran" question is asked directly, off the
    # same routing predicate "IF Update"/"IF Create" test.
    for _gate_write, _routed_action, _carry_merge_name in (
            ("HubSpot Update", "update", "Update Carry Merge"),
            ("HubSpot Create", "create", "Create Carry Merge")):
        _bar_idx = _merge_input_index(
            conns, _carry_merge_name, build_association_request_merge)
        wire_gate_refusal_lane(
            nodes, conns, _gate_write, ingest_merge_response, 40, 900,
            unreached_source="Decide Action",
            unreached_condition_js=(
                'if (rows.length > 0 && !rows.some((r) => r.action === '
                f'"{_routed_action}")) return [{{}}]; return [];'),
            # Phase 70 Plan 10 (D-70-23): the write node's own carry Merge may
            # legitimately never fire on a fully-refused (or write-unreached) batch —
            # that is fine, since nothing downstream needs its OWN delivery directly.
            # What must never starve is "Build Association Request Merge"'s own input
            # for this write path, so the sentinels target THAT merge, never the
            # `combineByPosition` carry Merge itself.
            carry_merge=(build_association_request_merge, _bar_idx))
        # Phase 70 Plan 10 (D-70-23) ingest-lane audit: retarget the write gate IF's
        # false (refusal) branch, which `wire_gate_refusal_lane` just wired straight
        # to `ingest_merge_response`, through a pass-through — no routing IF has a
        # direct edge to a Merge input on this lane, so this input obeys the one rule
        # this repo has observed (fed zero items, never runs) regardless of whether
        # the live engine treats an IF's own empty branch as a delivery.
        _retarget_merge_edge_through_passthrough(
            nodes, conns, f"{_gate_write} Write Gate IF", 1, ingest_merge_response,
            f"{_gate_write} Refusal Pass-Through", 40, 860)

    # Pre-probe placement (Task 2's human-check settles this live): "Set Review" is a
    # Code node and takes the flag directly per the plan's own literal suggestion; the
    # association terminal ("HubSpot Associate Company") sits downstream of two IFs.
    # Traced by hand against both the offline walker's model and n8n's own execution
    # engine (workflow-execute.ts::ensureAlwaysOutputData) before writing this graph:
    # neither flag is what actually satisfies "Ingest Merge Response" on a starved lane
    # here — a node that received ZERO deliveries is never dispatched at all, flag or
    # not, and the two sentinel nodes above are the mechanism that DOES. Both flags are
    # kept because (a) the plan's own <action> text names them as the candidate
    # placement the live probe evaluates, and (b) neither is harmful here — "Set
    # Review"'s own computation is only ever empty if its OWN input is (never true,
    # since it always receives at least the count it was given), and "HubSpot Associate
    # Company" never runs with zero input regardless of this flag.
    set_always_output_data(nodes, ["Set Review", "HubSpot Associate Company"])

    return {
        "id": "LVcontactIngestCloud01",
        "name": "LV Contact Ingest (Cloud template)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
    }


def _if_node(name, action_value, x, y):
    return {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ $json.action }}",
                "rightValue": action_value,
                "operator": {"type": "string", "operation": "equals"},
            }],
        }},
        "id": nid("if"), "name": name,
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }


def _if_not_equal_node(name, field, value, x, y):
    """IF node testing `$json.<field> != value` (string notEquals). Phase 16.1 (reviews
    A1/A2): used for the single `action != "skip"` provider-gate dispatch lane and the
    object-type-supported check — the `equals` counterpart is `_if_node`/inline IF specs
    elsewhere in this file."""
    return {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ $json." + field + " }}",
                "rightValue": value,
                "operator": {"type": "string", "operation": "notEquals"},
            }],
        }},
        "id": nid("if"), "name": name,
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }


# =============================================================================
# ENRICHMENT workflow (ENRICHMENT-WORKFLOW-PLAN.md §4 + §5 Wave B)
# =============================================================================
# Idempotent, quality-scored waterfall: HubSpot-first -> create/enrich/skip ->
# score ALL sources per field (not FIFO) -> non-clobber merge. Reuses the Wave-A
# engine (enrichmentGate / normalizeProviders / scoreEnrichment) + M3 mergeContacts,
# all inlined into Code nodes (same no-require constraint as the contact workflow).

FIX_ENRICH = ROOT / "tests" / "fixtures" / "enrichment"


def _fixture(name: str):
    return json.loads((FIX_ENRICH / name).read_text())


# ---- Criterion 5 parity single-source (Phase 16 Task 4) ---------------------
# The 7 config flags (research/judge cost caps + model knobs) and 6 secrets both
# enrichment builders (local-live docker replica + Cloud webhook) consume. ONE dict/list
# each — every call site below reads THESE, never a builder-local literal, so a flag or
# secret added/dropped/renamed in one builder but not the other is structurally
# impossible (tests/test_builder_flag_parity.py proves it once the Cloud companies
# branch lands, Task 5).
CONFIG_FLAG_DEFAULTS = {
    "ALLOW_WEB_RESEARCH": "true",
    "MAX_WEB_RESEARCH_PER_RUN": "10",
    "ANTHROPIC_RESEARCH_MODEL": "claude-haiku-4-5",
    "ANTHROPIC_JUDGE_MODEL": "claude-sonnet-5",
    "WEB_RESEARCH_MAX_SEARCHES": "5",
    "ALLOW_JUDGE_ESCALATION": "true",
    "MAX_JUDGE_VALIDATIONS_PER_RUN": "50",
}

SECRET_ENV_NAMES = [
    "HUBSPOT_PRIVATE_APP_TOKEN",
    "LUSHA_API_KEY",
    "APOLLO_API_KEY",
    "ANTHROPIC_API_KEY",
    "ZOOMINFO_CLIENT_ID",
    "ZOOMINFO_CLIENT_SECRET",
]


def _flag_const(name: str, cloud: bool) -> str:
    """One JS `const NAME = ...;` declaration for a CONFIG_FLAG_DEFAULTS entry.

    cloud=True bakes the literal default value at build time (AR-4: nothing not already
    in the JSON exists at n8n Cloud runtime) — zero $env/$vars survives.
    cloud=False (LOCAL-LIVE docker replica) reads $vars/$env at runtime, falling back to
    the SAME default so an unset `docker exec -e` still behaves like Cloud.
    """
    assert name in CONFIG_FLAG_DEFAULTS, f"unknown config flag: {name}"
    default = CONFIG_FLAG_DEFAULTS[name]
    if cloud:
        # Bake as the most literal JS type the value represents — a bare number for a
        # digit-string, a bare boolean for "true"/"false", a quoted string otherwise
        # (e.g. the model name) — never a runtime lookup expression.
        if default.isdigit():
            literal = default
        elif default in ("true", "false"):
            literal = default
        else:
            literal = json.dumps(default)
        return f"const {name} = {literal};"
    return f"const {name} = ($vars && $vars.{name}) || $env.{name} || {json.dumps(default)};"


def _env_secret_expr(name: str) -> str:
    """n8n expression reading a secret from $vars (Cloud Variables) or $env (docker -e) —
    the LOCAL-LIVE docker-replica secret-reading idiom. Cloud never calls this: secrets
    there are credential-bound (auth='header'/'basic', or the native HubSpot node), so
    this exists ONLY for local-live header/body call sites, and only for a name present
    in SECRET_ENV_NAMES — the single source both builders' secret handling is scoped to.
    """
    assert name in SECRET_ENV_NAMES, f"unknown secret: {name}"
    return "{{ ($vars && $vars." + name + ") || $env." + name + " }}"


# ---- Cloud-only write-safety gate (Phase 16 Task 6, review #9) --------------
# SEPARATE from CONFIG_FLAG_DEFAULTS (parity-guarded, tests/test_builder_flag_parity.py
# asserts exactly 6 flags) — these are Cloud-write-only; LOCAL/LOCAL-LIVE never write a
# HubSpot record (Decide Action there is a dry-run echo), so they must NOT enter the
# parity set. Baked into ENRICH_DECIDE_CLOUD/ENRICH_DECIDE_CO_CLOUD the same AR-4 way as
# CONFIG_FLAG_DEFAULTS: an activated-but-not-write-enabled Cloud workflow performs zero
# record writes (ALLOW_HUBSPOT_RECORD_WRITES defaults false), and even once enabled, a
# create additionally requires ALLOW_HUBSPOT_CREATE, and every write requires the target
# record's domain or hs_object_id to be on the TEST_RECORD_* allowlist (an empty
# allowlist denies everything — no accidental "allow all" via an unset env var).
# ALLOW_HUBSPOT_REVIEW_WRITES (Phase 30 Plan 01, D-02/D-08e) is the review-writeback
# authority and is deliberately NOT reachable from ALLOW_HUBSPOT_RECORD_WRITES in either
# direction: Phase 28's arm/dispatch/disarm cycle flips the dispatch flag, and nothing it
# arms may enable a review write — nor the reverse. Same allowlist requirement applies.
WRITE_SAFETY_DEFAULTS = {
    "ALLOW_HUBSPOT_RECORD_WRITES": "false",
    "ALLOW_HUBSPOT_CREATE": "false",
    "ALLOW_HUBSPOT_REVIEW_WRITES": "false",
    "TEST_RECORD_DOMAINS": "",
    "TEST_RECORD_IDS": "",
    # ALLOW_SJ3_DRAIN_WRITES (Phase 44 Plan 01, D-05 — operator-approved 2026-08-10) is
    # the FIRST write authority in this system that is enabled at rest, and the bound is
    # deliberate and narrow: it may only ever set lv_enrichment_requested to "false" and
    # lv_enrichment_status to "skipped", on records the SJ-3 gate declined in the SAME
    # tick. It removes queued work; it cannot create or alter data. It is NOT precedent
    # for defaulting any other write on. A "false"-defaulting drain was considered and
    # rejected: it would run only inside an armed window, which is precisely when the
    # queue is not stuck — leaving the runaway free to re-form every time the system
    # rests disarmed. Unreachable from ALLOW_HUBSPOT_RECORD_WRITES /
    # ALLOW_HUBSPOT_REVIEW_WRITES in either direction (no branch of _writeSafetyAllows
    # reads it, and its one reader — "SJ-3 Drain Gate" — reads nothing else), and
    # deliberately absent from the deploy overlay / arm system, following the
    # ALLOW_JUDGE_ESCALATION / ALLOW_WEB_RESEARCH default-true precedent
    # (scripts/deploy_n8n_workflows.py's _OVERLAY_FLAG_SPEC comment).
    "ALLOW_SJ3_DRAIN_WRITES": "true",
}


def _write_safety_const(name: str) -> str:
    """Always-baked Cloud build-time constant — no $env/$vars form exists (unlike
    _flag_const) because there is no local-live counterpart to keep in parity with."""
    assert name in WRITE_SAFETY_DEFAULTS, f"unknown write-safety constant: {name}"
    return f"const {name} = {json.dumps(WRITE_SAFETY_DEFAULTS[name])};"


# Shared write-safety gate function, embedded verbatim into both ENRICH_DECIDE_CLOUD and
# ENRICH_DECIDE_CO_CLOUD (Code nodes cannot require() each other — same no-shared-runtime
# constraint that governs every other inlined module in this file).
WRITE_SAFETY_GATE_JS = (
    "\n".join(_write_safety_const(k) for k in WRITE_SAFETY_DEFAULTS)
    + r"""
function _writeSafetyAllows(action, hsObjectId, domain) {
  // Review writeback has its OWN authority (D-02): the review action never consults
  // ALLOW_HUBSPOT_RECORD_WRITES, and no other action consults ALLOW_HUBSPOT_REVIEW_WRITES,
  // so arming either gate grants nothing on the other path. The allowlist below is
  // shared and mandatory for both.
  if (action === "review") {
    if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
  } else {
    if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
    if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
  }
  const allowedDomains = String(TEST_RECORD_DOMAINS).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowedDomains.length && !allowedIds.length) return false;  // empty allowlist denies everything
  if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
  if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
  return false;
}
"""
)



# ---- shared inlined Code-node bodies (Cloud + local both use these) ----------

# Build identity search keys from the trigger payload (email/domain/linkedin).
ENRICH_BUILD_IDENTITY = inline("normalizeEmail.js", "resolveIdentity.js", "matchProposal.js") + r"""

// Phase 61 Plan 02 Task 2 (REVIEW-01/REVIEW-C5): the WRITTEN-DOWN, BOUNDED search-variant
// set for "HubSpot Linkedin Search" — NOT an unbounded normalization promise. Covers the
// canonicalized host+path crossed with {https,http} x {no-www.,www.} x {no-slash,
// trailing-slash} (8 combinations) plus the raw operator-supplied value as given
// (deduplicated against the 8) = up to 9 variants. A stored form outside this set is a
// KNOWN search miss (tier `none`), never guessed — the re-verification in "Adapt Linkedin
// Search" (canonicalizeLinkedin on both sides) is what actually tolerates trailing-slash/
// case/query-string variance; THIS set only has to get the record BACK from HubSpot so
// that re-verification has something to look at.
function linkedinUrlVariants(raw) {
  const canonical = canonicalizeLinkedin(raw);
  if (!canonical) return [];
  const schemeSep = canonical.indexOf("://");
  let hostPath = schemeSep >= 0 ? canonical.slice(schemeSep + 3) : canonical;
  if (hostPath.indexOf("www.") === 0) hostPath = hostPath.slice(4);
  const out = new Set();
  for (const scheme of ["https", "http"]) {
    for (const www of ["", "www."]) {
      for (const slash of ["", "/"]) {
        out.add(scheme + "://" + www + hostPath + slash);
      }
    }
  }
  const rawTrimmed = typeof raw === "string" ? raw.trim() : raw;
  if (rawTrimmed) out.add(String(rawTrimmed));
  return Array.from(out);
}

// --- n8n wrapper: normalise the incoming identity into HubSpot search keys ---
return $input.all().map((it) => {
  const row = it.json;
  const email = normalizeEmailBasic(row.email);
  const identity_keys = {
    email,
    domain: row.domain || (email ? email.split("@")[1] : null),
    linkedin_url: row.linkedin_url || null,
    // Name+company let the providers match when no email is in hand (the common
    // pre-enrichment case). ZoomInfo/Apollo accept firstName+lastName+companyName.
    firstName: row.firstname || row.first_name || null,
    lastName: row.lastname || row.last_name || null,
    companyName: row.company || row.companyName || null,
  };
  return { json: { ...row,
    object_type: row.object_type || "contacts",
    identity_keys,
    // 36-CONTEXT.md §5A: each adapter filters to ITS OWN lane before index-aligning
    // against its own HTTP node — this one stamped field is the single source of
    // truth plan 36-02's match-lane routing IFs read too, so routing and filtering
    // provably cannot disagree.
    lane: laneOf({ object_id: row.object_id, identity_keys }),
    // Phase 61 Plan 02 Task 2: kept OFF identity_keys deliberately — a sibling field, not
    // a new identity_keys member, so this addition cannot perturb any test that pins
    // identity_keys' own exact shape (e.g. bareEventChainFlow.test.mjs).
    linkedin_url_variants: linkedinUrlVariants(row.linkedin_url),
  }};
});
"""

# Required-field set + policy for the staleness gate (contacts working set from
# ENRICHMENT-WORKFLOW-PLAN.md §3 + CLAUDE.md field_policy).
ENRICH_GATE = inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js") + r"""

// --- n8n wrapper: decideAction(existingRecord) -> create | enrich | skip ---
// D-66-01/RICH-01: `phone` (the landline) is chased alongside mobilephone. POLICY below
// stays byte-identical for it — no stale_after_days entry — because `stale_after_days`
// is read only by decideAction's `stale_refreshable`-shaped TTL branch, and `phone` is
// `fill_blank_only` (config/field_policy.yaml), whose branch never consults a TTL. A TTL
// entry here would be inert, and the only way to activate one is a field-class change
// D-66-08 forbids. See lushaRequest.js for the reveal-map half of this change.
//
// Phase 66 Plan 01 Task 3: REQUIRED widened to all twelve config/field_policy.yaml
// `contacts` keys — every field the merge policy can promote is now both fetched (Task 2)
// and produced (this task's LinkedIn producer; every other key already had one). Key
// spelling here is the HUBSPOT PROPERTY name (prefixed for the LinkedIn/persona fields),
// the opposite of the normalizer's UNPREFIXED push key described in prose above the
// Apollo push site — the two are correct in their own lanes: decideAction indexes
// existingRecord, a HubSpot property bag.
//
// What widening costs (not free at the batch level): almost no contact will ever hold
// all twelve fields, so rows that used to gate to "skip" now gate to "enrich" and reach
// the provider calls — per-call cost is unchanged (see the RICH-06 comment at the "Lusha
// Enrich" node), but calls per batch rise. The sharp edge is specifically the two
// single-producer fields: lv_persona_group and lv_linkedin_url each have exactly ONE
// producing branch (Apollo) — ZoomInfo returns no persona/departments field and its
// LinkedIn output field is unprobed (pending-probe, see normalizeProviders.js), and
// neither field has a Lusha producer either. For any contact Apollo does not match, both
// stay permanently blank, permanently missing, and permanently "enrich", including on
// every scheduled tick once armed. Accepted (T-66-04) rather than mitigated because
// D-66-01 is a locked decision and mitigating would mean narrowing the chase, which is
// the phase goal; the existing bound holds — nothing is armed, no unattended
// credit-spending batch has ever run, and the search limit is 100.
const REQUIRED = [
  "city", "country", "email", "hs_country_region_code", "hs_state_code", "jobtitle",
  "lv_linkedin_url", "lv_persona_group", "mobilephone", "phone", "seniority", "state",
];
const POLICY = { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } };
const NOW = new Date().toISOString();
// Phase 70 Plan 03 (D-70-01): this node now sits behind a real Merge with a starved-lane
// sentinel on every input that could otherwise never fire (Enrichment Gate's 5 identity
// lanes) — a sentinel's marker carries no row identity (`{}`) and must never be treated
// as a real row.
return $input.all().filter((it) => Object.keys(it.json || {}).length > 0).map((it) => {
  const row = it.json;
  const gate = decideAction(row.existingRecord || {}, REQUIRED, POLICY, NOW);
  let action = gate.action;
  // Fail-closed (Task 6, review #8): a HubSpot lookup FAILURE (non-200/malformed) is
  // tagged lookup_failed=true by the Adapt step and MUST NOT be treated as confirmed-
  // absent — decideAction({}) returns "create" (enrichmentGate.js:61, frozen), which
  // would create a DUPLICATE record on every transient search failure. This override
  // lives in the wrapper, never in the frozen module. row.lookup_failed is undefined
  // for LOCAL/LOCAL-LIVE (their Adapt Search never sets it) — a no-op there.
  if (row.lookup_failed === true && action === "create") action = "skip";
  // Phase 36 Plan 02, Task 3 (36-CONTEXT.md §7 step 8): a row with no email, no
  // linkedin_url, and not both a surname and a company name has no identity ANY of the
  // three providers can match on — never burn three provider calls (Lusha/Apollo/
  // ZoomInfo) on a row that can only ever return zero candidates. Same condition
  // laneOf() reports as lane "none" and summarizeMatch() reports as tier "unknown" — the
  // gate here is the cost control, the tier is the honesty; the two must never disagree.
  // Companies (ENRICH_CO_GATE) deliberately get NO equivalent rule — 36-CONTEXT.md §7
  // step 8 is contacts-only (36-RESEARCH.md §C).
  const ik = row.identity_keys || {};
  if (!ik.email && !ik.linkedin_url && !(ik.lastName && ik.companyName)) action = "skip";
  return { json: { ...row, gate, action } };
});
"""

# Normalize the 3 provider responses -> candidates, score best-per-field with
# provenance. `providers` carries {lusha,apollo,zoominfo} raw responses (null on skip).
ENRICH_NORMALIZE_SCORE = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
) + r"""

// --- n8n wrapper: toCandidates(all 3) -> scoreCandidates -> best-per-field ---
return $input.all().map((it) => {
  const row = it.json;
  const p = row.providers;
  if (!p) return { json: { ...row, scored: null, gap_flag: false } };  // skip branch
  const ot = row.object_type || "contacts";
  const cands = [
    ...toCandidates("lusha", p.lusha, ot),
    ...toCandidates("apollo", p.apollo, ot),
    ...toCandidates("zoominfo", p.zoominfo, ot),
  ];
  const gap_flag = cands.length === 0;  // ALL sources returned nothing -> flag manual
  const { best, winners } = scoreCandidates(cands, { now: new Date().toISOString() });
  // Plan 04: the matched Lusha record id rides as its OWN row field (never a candidate --
  // it must never enter scoreCandidates/the merge policy). Omitted entirely when null, so
  // an absent id can never become an empty-string write over a previously stored id.
  const lushaId = lushaRecordId(p.lusha, ot);
  const lusha_ids = lushaId
    ? (ot === "companies" ? { lusha_company_id: lushaId } : { lusha_contact_id: lushaId })
    : null;
  return { json: { ...row, scored: { best, winners }, gap_flag, ...(lusha_ids ? { lusha_ids } : {}) } };
});
"""

# Hand scored winners to the non-clobber merge (email never promotes to canonical).
ENRICH_MERGE = inline("resolveIdentity.js", "mergeContacts.js") + r"""

// --- n8n wrapper: mergeContacts(existingRecord, winners) non-clobber ---
// PN-1: linkedin_url is NOT HubSpot-native -> the merge candidate/canonical key is
// lv_linkedin_url. `winners.linkedin_url` (the scoreCandidates winner key, if a provider
// mapper ever populates it) stays unprefixed on the READ side, unrelated to this rename.
// Phase 70 Plan 03 (D-70-01): this node ("Merge Winners") sits behind a real Merge with a
// starved-lane sentinel on any of its 3 inputs (no research needed / no judge needed /
// judge ran) that could otherwise never fire; drop an identity-less sentinel marker
// before it is mistaken for a real row (it has no `.scored`, which would otherwise read
// as a genuine skip-branch row, never a `merge: null` placeholder for a row that was
// never really here).
return $input.all().filter((it) => Object.keys(it.json || {}).length > 0).map((it) => {
  const row = it.json;
  if (!row.scored) return { json: { ...row, merge: null } };  // skip branch
  const winners = row.scored.winners || {};
  const candidate = {};
  // 260826-20w Task 2 commit 1: the five location winners ride the same plain-key path
  // as email/phone/etc — they are already HubSpot-native names (no PN-1 rename needed).
  for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority",
                    "city", "state", "country", "hs_state_code", "hs_country_region_code"]) {
    if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
  }
  // Phase 61 Plan 02 Task 2: canonicalize BEFORE writing, so stored values converge from
  // here forward and the search's variant-set widening (ENRICH_BUILD_IDENTITY) can
  // eventually be narrowed. Existing stored values written before this change remain
  // UNCONVERTED — this is exactly why the search still carries the wider filter rather
  // than dropping to a plain EQ on the canonical form.
  const canonicalWinnerLinkedin = canonicalizeLinkedin(winners.linkedin_url);
  if (canonicalWinnerLinkedin) {
    candidate.lv_linkedin_url = canonicalWinnerLinkedin;
  }
  // COPY-02: persona_group is NOT HubSpot-native (PN-1) -> the merge candidate/canonical
  // key is lv_persona_group. Dot-property access only, never a bare quoted array entry
  // (the PN-1 architecture guard forbids a bare quoted persona_group string literal here).
  if (winners.persona_group != null && String(winners.persona_group).trim() !== "") {
    candidate.lv_persona_group = winners.persona_group;
  }
  const merged = mergeContacts(row.existingRecord || {}, candidate, undefined,
                               { source: "waterfall", confidence: 85 });

  // Phase 16.2 (SC-3 honest mirror, D6 analog): fold the Claude web-research candidate
  // (jobtitle/seniority ONLY) in as a SECOND mergeContacts() call, then reconcile any
  // overlap with the provider merge via foldContactResearch's write-SAFETY gate (never
  // adjudication — the judge already adjudicated any existing-record conflict upstream).
  // A no-op for every row this module didn't add a contact research chain for (LOCAL,
  // which never sets research_candidate) and for a companies row (rc undefined there).
  let finalMerge = merged;
  const rc = row.research_candidate;
  if (rc && rc.matched) {
    const researchData = {};
    for (const f of ["jobtitle", "seniority"]) {
      const v = rc.data && rc.data[f];
      if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
      researchData[f] = v;
    }
    if (Object.keys(researchData).length > 0) {
      // LOW-9: require_evidence_url:true on BOTH fields, belt-and-braces on top of the
      // upstream validate-time evidence demotion (contactResearch.js) — a research value
      // can promote only WITH evidence at every layer that touches it. jobtitle also
      // moves to system_owned (overriding its DEFAULT_CONTACT_POLICY stale_refreshable
      // class) so a research-sourced value is not blocked by the "existing value present
      // -> needs_review" refresh rule that class carries for provider data.
      const RESEARCH_POLICY = {
        ...DEFAULT_CONTACT_POLICY,
        jobtitle: { class: "system_owned", min_confidence: 75, require_evidence_url: true },
        seniority: { ...DEFAULT_CONTACT_POLICY.seniority, require_evidence_url: true },
      };
      const researchMerged = mergeContacts(row.existingRecord || {}, researchData, RESEARCH_POLICY,
        { source: "claude_web", confidence: rc.confidence || 80, evidence: rc.evidence_by_field || {},
          confidenceByField: row.judge_confidence_by_field || {} });
      // The ONLY trusted per-field adjudication signal — set fresh by the security-
      // hardened applyContactJudgeVerdict, never the caller-injectable
      // judge_confidence_by_field (gpt #5/#8).
      const judgePromotedFields = (rc.judge_flags && rc.judge_flags.promoted_field)
        ? [rc.judge_flags.promoted_field] : [];
      finalMerge = foldContactResearch(merged, researchMerged, judgePromotedFields, row.existingRecord || {});
    }
  }

  return { json: { ...row, merge: finalMerge } };
});
"""

# LOCAL: canned HubSpot existing records so the gate exercises create/enrich/skip.
ENRICH_HUBSPOT_SEARCH_MOCK = r"""// HubSpot Search (MOCK) — LOCAL variant only.
// Cloud uses a real HubSpot search node; here we return canned existing records so
// enrichmentGate exercises every branch:
//   jamie.rivera@... -> {} (no record)              => CREATE
//   alex.taylor@...  -> stale jobtitle + no mobile   => ENRICH
//   sam.fresh@...    -> fresh + complete + valid     => SKIP
const CANNED = {
  "jamie.rivera@exampleracing.example": {},
  "alex.taylor@exampleco.example": {
    email: "alex.taylor@exampleco.example",
    jobtitle: "Analyst",
    lv_jobtitle_verified_at: "2025-01-01T00:00:00Z",
    mobilephone: ""
  },
  "sam.fresh@examplemedia.example": {
    email: "sam.fresh@examplemedia.example",
    jobtitle: "Producer",
    lv_jobtitle_verified_at: "2026-07-01T00:00:00Z",
    mobilephone: "+61412000000",
    lv_mobilephone_verified_at: "2026-07-01T00:00:00Z"
  }
};
return $input.all().map((it) => {
  const row = it.json;
  const email = (row.identity_keys && row.identity_keys.email) || null;
  const existingRecord = CANNED[email] || {};
  return { json: { ...row, existingRecord } };
});
"""

# CLOUD (also used by LOCAL-LIVE, same onError:continueRegularOutput HTTP shape): adapt
# the real HubSpot search node output into an existingRecord. Task 6 hardening (review
# #8): distinguishes confirmed-absent (200 + zero results -> {} -> correct CREATE) from
# lookup-FAILED (missing/errored item -> {} would be INDISTINGUISHABLE from confirmed-
# absent to enrichmentGate.js's _isEmpty({}) check, which returns "create" — a duplicate-
# record risk on every transient failure). A failed lookup is tagged lookup_failed=true;
# ENRICH_GATE's wrapper (companies: ENRICH_CO_GATE) overrides "create" -> "skip" whenever
# that flag is set, so a failure never reaches a write. hs_object_id is preserved from
# the result's top-level `id` (HubSpot's v3 API always returns it, independent of the
# requested `properties` list) so HubSpot Update has a real target instead of the
# previously-hardcoded, never-set contact_id.
ENRICH_ADAPT_SEARCH = inline("matchProposal.js") + r"""

// Adapt Search -> existingRecord — CLOUD variant.
// Phase 70 Plan 04 (D-70-04): "HubSpot Search Carry Merge" (splice_carry_merge_after)
// sits immediately upstream, re-attaching the pre-hop row (from "IF Has Email"'s TRUE
// lane — the SAME delivery that fed "HubSpot Search") onto the raw search response,
// row-fields-last (merge_node's own "preferLast" contract). $input here is therefore
// ALREADY the "email"-lane row alone (IF Has Email only forwards that lane), combined
// with its own search result — no by-name recovery of "Build Identity" or "HubSpot
// Search" is needed or possible (D-70-01/D-70-03).
return $input.all().map((it) => {
  const merged = it.json;
  const failed = !!merged.error;
  if (failed) {
    // Phase 36 Plan 02: every lane stamps a `match` verdict, even on a lookup failure —
    // the response's `match.tier` must be honest about "could not look" (unknown), not
    // silently absent.
    const match = summarizeMatch({ lane: "email", lookupFailed: true });
    return { json: { ...merged, existingRecord: {}, lookup_failed: true, match } };
  }
  let existingRecord = {};
  if (Array.isArray(merged.results)) {                                  // search list
    if (merged.results.length) {
      const first = merged.results[0];
      existingRecord = { ...(first.properties || {}), hs_object_id: first.id };
    }
  } else if (merged.properties) {                                       // single object
    existingRecord = { ...merged.properties, hs_object_id: merged.id };
  } else if (merged.id) {
    existingRecord = merged;
  }
  const match = summarizeMatch({ lane: "email", existingRecord, lookupFailed: false });
  return { json: { ...merged, existingRecord, lookup_failed: false, match } };
});
"""

# LOCAL: provider waterfall MOCK — returns fixture-shaped raw responses.
ENRICH_PROVIDER_MOCK = (
    "// Provider Waterfall (MOCK) — LOCAL variant only.\n"
    "// Cloud replaces this with 3 real HTTP nodes (Lusha/Apollo/ZoomInfo). Here we\n"
    "// return the tests/fixtures/enrichment/*.json contact shapes so normalizeProviders\n"
    "// + scoreEnrichment run for real on realistic data. SKIP identities get no call.\n"
    "const LUSHA = " + json.dumps(_fixture("lusha_v3_contact.json")) + ";\n"
    "const APOLLO = " + json.dumps(_fixture("apollo_contact.json")) + ";\n"
    "const ZOOMINFO = " + json.dumps(_fixture("zoominfo_contact.json")) + ";\n"
    "return $input.all().map((it) => {\n"
    "  const row = it.json;\n"
    "  if (row.action === 'skip') return { json: { ...row, providers: null } };\n"
    "  return { json: { ...row, providers: { lusha: LUSHA, apollo: APOLLO, zoominfo: ZOOMINFO } } };\n"
    "});\n"
)

# LOCAL: dry-run echo — replaces HubSpot create/update writes. NO real write.
ENRICH_DECIDE_LOCAL = r"""// Decide Action (dry-run echo) — LOCAL variant.
// Replaces the HubSpot create/update write nodes: ECHOES the would-be payload,
// performs NO real write. Surfaces the per-identity action + scored winners w/ provenance.
// Phase 15: this is the SINGLE serialization point for the provenance blob — the
// stamper (mergeContacts.js) returns the parsed provenance object, never a string.
function _sortedForStringify(v) {
  if (Array.isArray(v)) return v.map(_sortedForStringify);
  if (v !== null && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = _sortedForStringify(v[k]);
    return out;
  }
  return v;
}
function _stableStringify(v) { return JSON.stringify(_sortedForStringify(v)); }
function _buildContactPatch(merge) {
  if (!merge) return {};
  const patch = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}) };
  if (merge.provenance && Object.keys(merge.provenance).length) {
    patch.lv_contact_enrichment_provenance = _stableStringify(merge.provenance).slice(0, 60000);
  }
  return patch;
}

return $input.all().map((it) => {
  const row = it.json;
  const action = row.action;
  const id = row.identity_keys || {};
  const scored = row.scored;
  const winners_sample = [];
  if (scored && scored.best) {
    for (const f of Object.keys(scored.best)) {
      const b = scored.best[f];
      winners_sample.push({ field: f, value: b.value, source: b.source,
        score: Math.round(b.score * 100) / 100, agreedBy: b.agreedBy });
    }
  }
  const patch = { ..._buildContactPatch(row.merge), ...(row.lusha_ids || {}) };
  let hubspot_op = null;
  if (action === "create") {
    // BUG 19: seed identity on create ONLY — canonicalPatch never carries email
    // (manual_protected), and a record created without it is invisible to the search
    // that gated the create.
    if (id.email || row.email) patch.email = id.email || row.email;
    hubspot_op = { method: "POST", endpoint: "/crm/v3/objects/contacts", properties: patch };
  } else if (action === "enrich") {
    hubspot_op = { method: "PATCH", endpoint: "/crm/v3/objects/contacts/{id}", properties: patch };
  } // skip -> no op
  return { json: {
    email: id.email || row.email || null,
    action,
    gate_reason: row.gate ? row.gate.reason : null,
    gap_flag: row.gap_flag === true,
    winners_sample,
    dry_run: true,
    hubspot_op
  }};
});
"""

# Stamps the two data-quality fields WITHOUT discarding the row. Replaces the
# n8n-nodes-base.set node that caused BUG 12 — see the build site for why the platform
# option was abandoned. Pure spread: everything Decide Action needs (merge,
# existingRecord, object_id, scored) survives.
ENRICH_SET_DQ_JS = r"""// Set Data Quality + Gap Flag — row-carrying passthrough.
// BUG 12: this was a Set node, which emits only its assigned fields and therefore
// deleted merge/existingRecord/object_id/scored for Decide Action downstream.
return $input.all().map((it) => ({
  json: {
    ...it.json,
    data_quality: "scored_waterfall",
    gap_flag: it.json.gap_flag === true,
  },
}));
"""

# CLOUD: compute action + property patch; IF nodes route to real HubSpot write.
ENRICH_DECIDE_CLOUD = inline("matchProposal.js") + r"""

// Decide Action — CLOUD variant.
// Computes action + the HubSpot property patch from the scored+merged winners.
// The IF nodes route create -> HubSpot Create, enrich -> HubSpot Update — GATED by the
// write-safety check below (Task 6, review #9): an activated-but-not-write-enabled
// workflow always returns action "write_blocked", which neither IF node matches.
// Phase 15: this is the SINGLE serialization point for the provenance blob — the
// stamper (mergeContacts.js) returns the parsed provenance object, never a string.
function _sortedForStringify(v) {
  if (Array.isArray(v)) return v.map(_sortedForStringify);
  if (v !== null && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = _sortedForStringify(v[k]);
    return out;
  }
  return v;
}
function _stableStringify(v) { return JSON.stringify(_sortedForStringify(v)); }
function _buildContactPatch(merge) {
  if (!merge) return {};
  const patch = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}) };
  if (merge.provenance && Object.keys(merge.provenance).length) {
    patch.lv_contact_enrichment_provenance = _stableStringify(merge.provenance).slice(0, 60000);
  }
  return patch;
}
""" + WRITE_REQUEST_JS + r"""
return $input.all().map((it) => {
  const row = it.json;
  // Phase 36-04 Task 1 (36-CONTEXT.md §4 decision 1/§6): computed once per row from the
  // shared two-state predicate — never a third mode name, never an ALLOW_* constant.
  const returnOnly = isReturnOnly(row.mode);
  const properties = { ..._buildContactPatch(row.merge), ...(row.lusha_ids || {}) };

  // REVIEW FLAG (260826-20w, T-20w-01): mirrors ENRICH_DECIDE_CO_CLOUD's needs-review
  // block, narrowed to the ONE predicate this relaxation introduces — a decision that is
  // BOTH a promote AND carries the human-review validation status. That pair exists only
  // because of the email permissive-promotion change (mergeContacts.js); it must NOT be
  // widened to "any needs_review decision" — jobtitle's routine stale_refreshable refresh
  // conflicts are needs_review + human_review_required too, and flagging those would
  // flood the triage queue with ordinary enrichment, defeating the point of the flag.
  // Deliberately does NOT write lv_enrichment_review_candidate_json: that property means
  // "a held candidate awaiting a human's apply", and this module has already WRITTEN the
  // value (it is in `properties` above) — staging it as a candidate too would make the
  // review-apply lane try to re-apply a value that is already live.
  const contactDecisions = (row.merge && row.merge.decisions) || [];
  const permissivelyFlagged = contactDecisions.filter(
    (d) => d.decision === "promote" && d.validation_status === "human_review_required");
  if (permissivelyFlagged.length > 0) {
    // String literals, never bare JS booleans — the BUG-27 loop below only joins arrays
    // and stringifies booleans, and D-07's companies precedent is explicit about this.
    properties.lv_enrichment_needs_review = "true";
    properties.lv_enrichment_status = "needs_review";
    properties.lv_enrichment_review_reason = permissivelyFlagged
      .map((d) => `${d.field}: promoted into a blank field at confidence ${d.confidence} — verify before relying on it`)
      .join("; ").slice(0, 60000);
  } else if (row.merge) {
    properties.lv_enrichment_status = "complete";
  }

  const hs_object_id = (row.existingRecord && row.existingRecord.hs_object_id) || null;
  const id = row.identity_keys || {};
  const domain = id.domain;
  if (row.action === "create" && id.email && !returnOnly) {
    // BUG 19: canonicalPatch never carries email (manual_protected — an UPDATE rule), so
    // an unseeded create writes a contact the by-email search can never find, and every
    // later run creates another. Keyed on row.action (pre-gate): a write_blocked create
    // sends nothing, and an enrich must never receive this seed (that IS the clobber the
    // policy exists to prevent). Also gated on !returnOnly (36-CONTEXT.md §6): a propose
    // response's `properties` carries only what the waterfall discovered — the caller's
    // own identity must never be echoed back as if it were a finding.
    properties.email = id.email;
  }
  let action = row.action;
  if (returnOnly) {
    // Phase 36-04 Task 1 (36-CONTEXT.md §4 decision 1): set BEFORE _writeSafetyAllows,
    // unconditionally on the mode predicate alone — no ALLOW_* constant is read on this
    // branch. That ordering IS the safety property: propose mode's no-write guarantee
    // cannot be re-armed by flipping a write-safety flag. "proposed" matches neither
    // "IF Create" (=="create") nor "IF Enrich" (=="enrich"), so the row exits via
    // "IF Enrich"'s existing false lane into "Build Response" — no new edge needed.
    action = "proposed";
  } else if (action === "create" && row.match && row.match.tier === "medium") {
    // A MEDIUM match is a proposal the caller has not judged — `auto` is false by
    // contract (matchProposal.js summarizeMatch). Auto-creating against it would
    // duplicate the very candidate mediumCandidates() just surfaced. Like "proposed",
    // "needs_match_review" matches neither IF Create nor IF Enrich and exits via
    // IF Enrich's false lane.
    action = "needs_match_review";
  }
  // Phase 70 Plan 05 Task 2 (D-70-13): the write-permission predicate USED to run here,
  // inline, turning a create/enrich into "write_blocked" before either routing IF saw it.
  // It now has exactly one home per lane — the spliced "<write node> Write Gate" — so this
  // node decides WHAT the row is, never WHETHER it may be written. The row keeps its real
  // action through "IF Create"/"IF Enrich" and is refused (or not) at the gate, which
  // EMITS the refusal as a row rather than dropping it (D-70-14).
  // Phase 61 Plan 06 Task 1 (CLAUDE.md §13.0.1's closing gap): this contacts branch has
  // no company-resolution or association mechanism at all — the ONLY lane that
  // associates a created contact to a company is the ingest lane (contact-upload
  // webhook, wf_contact_ingest_cloud.json, whose `Build Company Link`/`Adapt Company
  // Link`/`Build Association Request` nodes already implement the 2026-08-25 rule).
  // Duplicating that resolution+association subgraph here would be a second,
  // driftable copy of the same rule — exactly the outcome CLAUDE.md's closing sentence
  // warns is still open. Rather than land an unassociated contact, an armed create on
  // THIS lane is held for review instead, the same "hold, don't land unassociated"
  // contract the ingest lane enforces on its own create path — enforced here by never
  // completing the create at all, one operational implementation of the rule.
  let contactCreateHeldForAssociation = false;
  if (action === "create") {
    action = "review";
    contactCreateHeldForAssociation = true;
    properties.lv_enrichment_needs_review = "true";
    properties.lv_enrichment_status = "needs_review";
    properties.lv_enrichment_review_reason =
      "contact creates are not associated on this lane — route this contact through " +
      "the contact-upload ingest lane instead, which resolves and associates a " +
      "company before creating";
  }
  // BUG 27 (live 400 on execution 328): HubSpot v3 PATCH rejects JSON arrays —
  // multi-checkbox values must be semicolon-joined strings. Single choke point.
  // D-07 (43-01, PIPE-01, row 5, defensive parity with the companies branch): a second
  // branch coerces any boolean-typed value to its quoted string form — no boolean-typed
  // ICP candidate is a live contacts field today (DEFAULT_CONTACT_POLICY is string-only),
  // but this closes the class here too rather than leaving one branch un-guarded.
  for (const k of Object.keys(properties)) {
    if (Array.isArray(properties[k])) properties[k] = properties[k].join(";");
    else if (typeof properties[k] === "boolean") properties[k] = properties[k] ? "true" : "false";
  }
  return { json: {
    action,
    object_type: row.object_type || "contacts",
    hs_object_id,
    gap_flag: row.gap_flag === true,
    needs_review: permissivelyFlagged.length > 0 || contactCreateHeldForAssociation,
    row_id: row.row_id ?? null,
    mode: row.mode ?? null,
    match: row.match ?? summarizeMatch({ lane: row.lane }),
    // Phase 61 Plan 04 Task 1 (REVIEW-05): carried BY NAME, mirroring the existing
    // paired-index carry idiom (e.g. research_candidate/judge_verdict/existingRecord)
    // — this node's own return object is an explicit field list, so a signal not named
    // here dies at this exact boundary before Build Response ever sees it. `scored` and
    // `judge_confidence_by_field` are raw upstream fields; Build Response is the single
    // place that turns them into the named outcome-contract signals.
    scored: row.scored ?? null,
    material_conflicts: row.material_conflicts ?? null,
    judge_confidence_by_field: row.judge_confidence_by_field ?? null,
    // Phase 66 Plan 03 (D-66-06): same carry-BY-NAME idiom as the three fields above —
    // Build Response's contactability projection needs the POST-RUN state (existing
    // record + this run's promoted patch), and `properties` alone is insufficient
    // (email/phone are fill_blank_only/manual_protected, so an already-populated value
    // never appears in `properties`; only a value promoted blank-to-filled would).
    existingRecord: row.existingRecord ?? null,
    merge: row.merge ?? null,
    // D-70-12: the canonical shape the spliced "HubSpot Create/Update Write Gate" reads —
    // built by the one shared helper, never re-derived at the gate.
    write_request: _buildWriteRequest(action, hs_object_id, domain || null, id.email || null),
    properties
  }};
});
"""

# CLOUD: NORMALIZE+SCORE reads the 3 provider HTTP nodes by name and re-attaches
# the carried identity/gate context from the Gate node (HTTP nodes replace $json).
ENRICH_NORMALIZE_SCORE_CLOUD = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
) + r"""

// --- n8n wrapper (CLOUD): score best-per-field from the row's own carried results ---
// Phase 70 Plan 04 (D-70-04): "Lusha Result Carry Merge"/"Apollo Result Carry Merge"
// (each fed by a "Wrap * Result" node nesting the raw response, splice_carry_merge_
// after re-attaching the row) stamp `lusha_result`/`apollo_result` onto the row; the
// "ZoomInfo Enrich" Code node stamps its own `zoominfo_result` directly (it controls
// its own return shape, no merge needed). $input here is therefore ALREADY one item
// per row, carrying all three — no by-name recovery of "Enrichment Gate"/"Lusha
// Enrich"/"Apollo Match"/"ZoomInfo Enrich" (D-70-01/D-70-03).
return $input.all().map((it) => {
  const row = it.json;
  const ot = row.object_type || "contacts";
  const p = {
    lusha: row.lusha_result,
    apollo: row.apollo_result,
    zoominfo: row.zoominfo_result,
  };
  const cands = [
    ...toCandidates("lusha", p.lusha, ot),
    ...toCandidates("apollo", p.apollo, ot),
    ...toCandidates("zoominfo", p.zoominfo, ot),
  ];
  const gap_flag = cands.length === 0;
  const { best, winners } = scoreCandidates(cands, { now: new Date().toISOString() });
  // Plan 04: sibling row field, never a candidate — see the LOCAL variant's identical comment.
  const lushaId = lushaRecordId(p.lusha, ot);
  const lusha_ids = lushaId ? { lusha_contact_id: lushaId } : null;
  const { lusha_result, apollo_result, zoominfo_result, ...cleanRow } = row;
  return { json: { ...cleanRow, providers: p, scored: { best, winners }, gap_flag, ...(lusha_ids ? { lusha_ids } : {}) } };
});
"""

# CLOUD: ZoomInfo enrich with AUTONOMOUS token caching + refresh-on-401. Replaces the
# separate Auth + Enrich HTTP nodes: mints its own bearer, caches it in workflow static
# data, re-mints only when missing/near-expiry, and re-mints once + retries on a 401.
# Shared ZoomInfo preamble: cached bearer + JSON:API enrich helper. Parameterised by the
# GTM enrich URL so the contacts and companies nodes share ONE token-cache implementation
# (same $getWorkflowStaticData key -> one mint serves both branches).
def _zoom_preamble(enrich_url):
    # Phase 70 Plan 04 (D-70-04): no longer inlines nodeRunRecovery.js — this was the
    # LAST call site (the split gate/cache functions were fixed earlier in this same
    # plan); the module itself is deleted in Task 3, once every call site is gone.
    return inline("zoominfoToken.js") + ZOOM_PREAMBLE_JS.replace("__ENRICH_URL__", enrich_url)


ZOOM_PREAMBLE_JS = r"""
// n8n Code node: cached ZoomInfo bearer (autonomous). Reads a cross-run token cache
// from workflow static data, mints only when missing/near-expiry, enriches with the
// Bearer, and on a 401 clears the cache, re-mints ONCE, and retries. Secrets come from
// n8n Variables ($vars.ZOOMINFO_CLIENT_ID / $vars.ZOOMINFO_CLIENT_SECRET) so no static
// token is ever stored. (Self-hosted may use $env; or bind a Basic Auth credential to a
// dedicated mint HTTP node instead.)
const TOKEN_URL = "https://api.zoominfo.com/gtm/oauth/v1/token";
const ENRICH_URL = "__ENRICH_URL__";
const sd = $getWorkflowStaticData("global");

async function mint() {
  // Cloud: n8n Variables ($vars). Self-hosted/headless: process env ($env). Prefer $vars.
  const cid = ($vars && $vars.ZOOMINFO_CLIENT_ID) || $env.ZOOMINFO_CLIENT_ID;
  const csec = ($vars && $vars.ZOOMINFO_CLIENT_SECRET) || $env.ZOOMINFO_CLIENT_SECRET;
  const basic = Buffer.from(cid + ":" + csec).toString("base64");
  const resp = await this.helpers.httpRequest({
    method: "POST", url: TOKEN_URL,
    headers: { Authorization: "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials",
  });
  const parsed = parseTokenResponse(resp, Date.now());
  sd.zoominfo = parsed;              // cache across executions
  return parsed.access_token;
}

async function getToken() {
  if (needsMint(sd.zoominfo, Date.now())) return await mint.call(this);
  return sd.zoominfo.access_token;
}

async function enrich(token, payload) {
  // GTM data API is JSON:API — content-type/accept MUST be application/vnd.api+json.
  return await this.helpers.httpRequest({
    method: "POST", url: ENRICH_URL,
    headers: { Authorization: "Bearer " + token,
               "Content-Type": "application/vnd.api+json", Accept: "application/vnd.api+json" },
    body: JSON.stringify(payload || {}),
  });
}
"""


ENRICH_ZOOMINFO_CACHED = _zoom_preamble(
    "https://api.zoominfo.com/gtm/data/v1/contacts/enrich") + r"""
// GTM enrich contract (LIVE-confirmed 200): JSON:API envelope
//   { data: { type: "ContactEnrich", attributes: { matchPersonInput:[{emailAddress|firstName|lastName|companyName}], outputFields:[...] } } }
// with Content-Type application/vnd.api+json. Input KEY is `emailAddress` (not `email`);
// `domain`/`linkedin_url` are NOT valid matchPersonInput fields. Response: { data:[{ attributes:{...},
// meta:{matchStatus} }] } — matchStatus is in meta (NOT a valid outputField), so it's omitted below.
// Every outputField here is verified valid for the account (directPhone/hasEmail/hasDirectPhone 400).
const ZOOM_OUTPUT_FIELDS = [
  "id", "firstName", "lastName", "email", "phone", "mobilePhone", "jobTitle",
  "managementLevel", "contactAccuracyScore", "validDate", "lastUpdatedDate",
  // city/state/country: LIVE-verified valid on this account 2026-08-26
  // (scripts/probe_zoominfo_location_fields.mjs; zipCode/metroArea also valid, unused).
  "city", "state", "country",
];
function toMatchPersonInput(id) {
  const m = {};
  if (id && id.email) m.emailAddress = id.email;   // rename email -> emailAddress
  if (id && id.firstName) m.firstName = id.firstName;
  if (id && id.lastName) m.lastName = id.lastName;
  if (id && id.companyName) m.companyName = id.companyName;
  return m;
}
// ZoomInfo needs a usable match key: an email, OR first+last name with a company.
function hasZoomKey(m) {
  return !!(m.emailAddress || (m.firstName && m.lastName && m.companyName));
}

// Phase 70 Plan 04 (D-70-04): fed by "Apollo Match Carry Merge" (or a bypassed
// provider's own row, unmodified) — $input here IS the row directly, no by-name
// recovery of "Enrichment Gate" (D-70-01/D-70-03). A Code node controls its own
// return shape, so `...row` + `zoominfo_result` (never a bare `res` overwrite) is
// what lets "Normalize + Score" read $input.all() directly too.
const items = $input.all();
const out = [];
for (let i = 0; i < items.length; i++) {
  const row = items[i].json;
  const id = row.identity_keys || {};
  const person = toMatchPersonInput(id);
  // No usable match key -> skip the call (empty/keyless matchPersonInput is itself a 400).
  const payload = hasZoomKey(person)
    ? { data: { type: "ContactEnrich", attributes: { matchPersonInput: [person], outputFields: ZOOM_OUTPUT_FIELDS } } }
    : null;
  if (!payload) { out.push({ json: { ...row, zoominfo_result: { skipped: "no zoominfo match key" } } }); continue; }
  let token = await getToken.call(this);
  let res;
  try {
    res = await enrich.call(this, token, payload);
  } catch (e) {
    if (isAuthError(extractErrorStatus(e))) {
      delete sd.zoominfo;                     // token rejected -> re-mint once + retry
      token = await mint.call(this);
      try { res = await enrich.call(this, token, payload); }
      catch (e2) { res = { error: String((e2 && e2.message) || e2) }; }
    } else {
      res = { error: String((e && e.message) || e) };  // non-auth error -> continue
    }
  }
  out.push({ json: { ...row, zoominfo_result: res } });
}
return out;
"""


# ---- LOCAL enrichment workflow ----------------------------------------------

ENRICH_EMIT_IDENTITIES = r"""// Emit Sample Identities (mock trigger payload) — LOCAL variant.
// Cloud instead receives these from a Webhook (POST body). Three identities that
// exercise every gate branch: create (not in HubSpot), enrich (stale), skip (fresh).
const rows = [
  { email: "jamie.rivera@exampleracing.example", object_type: "contacts" },  // CREATE
  { email: "alex.taylor@exampleco.example", object_type: "contacts" },       // ENRICH
  { email: "sam.fresh@examplemedia.example", object_type: "contacts" }       // SKIP
];
return rows.map((r) => ({ json: r }));
"""


def build_enrichment_local():
    nodes = []
    y = 300
    x = 240
    manual = {"parameters": {}, "id": nid("t"), "name": "Manual Trigger",
              "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [x, y]}
    nodes.append(manual)

    seq = [
        ("Emit Sample Identities", ENRICH_EMIT_IDENTITIES),
        ("Build Identity", ENRICH_BUILD_IDENTITY),
        ("HubSpot Search (MOCK)", ENRICH_HUBSPOT_SEARCH_MOCK),
        ("Enrichment Gate", ENRICH_GATE),
        ("Provider Waterfall (MOCK)", ENRICH_PROVIDER_MOCK),
        ("Normalize + Score", ENRICH_NORMALIZE_SCORE),
        ("Merge Winners", ENRICH_MERGE),
        ("Decide Action", ENRICH_DECIDE_LOCAL),
    ]
    for name, js in seq:
        x += 230
        nodes.append(code_node(name, js, x, y))

    order = ["Manual Trigger", "Emit Sample Identities", "Build Identity",
             "HubSpot Search (MOCK)", "Enrichment Gate", "Provider Waterfall (MOCK)",
             "Normalize + Score", "Merge Winners", "Decide Action"]

    note = {
        "parameters": {"content": (
            "## LV Enrichment — LOCAL (headless-executable)\n"
            "Same Wave-A/M3 JS as the Cloud template, inlined into Code nodes.\n\n"
            "**Mocked for local run:** trigger -> Emit Sample Identities; HubSpot "
            "search -> canned records; provider waterfall -> fixture shapes; "
            "HubSpot create/update -> Decide Action dry-run echo (NO real writes).\n\n"
            "**REAL:** enrichmentGate, normalizeProviders, scoreEnrichment (best-"
            "per-field w/ provenance), mergeContacts (non-clobber).\n\n"
            "Three identities exercise every gate branch: **create / enrich / skip**."
        ), "height": 300, "width": 440},
        "id": nid("s"), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [240, 540],
    }
    nodes.append(note)

    return {
        "id": "LVenrichment01",
        "name": "LV Enrichment (local replica)",
        "nodes": nodes,
        "connections": chain(order),
        "settings": {},
    }


# ---- LOCAL-LIVE enrichment workflow (real providers, headless) --------------
# Same graph as the cloud template but headless-executable: Manual Trigger instead of
# Webhook, provider HTTP nodes + HubSpot search read their secrets from $env (docker exec
# -e ...) instead of the credential store, and there are NO write nodes (Decide Action
# echoes the would-be payload). Read-only: live provider calls + HubSpot SEARCH only.

ENRICH_EMIT_LIVE = r"""// Emit Live Identities — LOCAL-LIVE variant.
// Real prospects (name+company+domain, no email in hand) that the live providers match.
// Same set as the batch dry-run harness; all route create/enrich (none skip) so provider
// outputs align 1:1 with the gate rows for the scored waterfall.
const rows = [
  { firstname: "Gerry",  lastname: "Harvey",     company: "Harvey Norman",         domain: "harveynorman.com.au",       object_type: "contacts" },
  { firstname: "Kyle",   lastname: "Bettler",    company: "Racing NSW",            domain: "racingnsw.com.au",          object_type: "contacts" },
  { firstname: "Kieran", lastname: "Granger",    company: "Melbourne Racing Club", domain: "mrc.net.au",                object_type: "contacts" },
  { firstname: "Mick",   lastname: "James",      company: "Australian Turf Club",  domain: "australianturfclub.com.au", object_type: "contacts" },
  { firstname: "David",  lastname: "Preschlack", company: "FanDuel",               domain: "fanduel.com",               object_type: "contacts" }
];
return rows.map((r) => ({ json: r }));
"""

ENRICH_BUILD_REQUESTS = inline("lushaRequest.js") + r"""

// --- n8n wrapper: Build Live Provider Requests — LOCAL-LIVE variant. ---
// Turns identity_keys into the concrete per-provider request shapes the LIVE HTTP nodes'
// own jsonBody expressions read off bare $json (HTTP nodes replace $json with their
// response, so a carry merge re-attaches this node's row afterward — see the "Build
// Requests" carry-merge wiring, Phase 70 Plan 04, D-70-04). Lusha v3 = POST /v3/contacts/search-and-enrich
// JSON body (retired v2 GET querystring — see docs/LUSHA-V3-CONTRACT.md), built by the
// shared lushaContactBody() with the reveal list derived from the gate's missingFields.
// Plan 04 Task 2b: when the record already carries a stored lusha_contact_id,
// lushaContactEnrichByIdBody() builds the CONFIRMED-FREE POST /v3/contacts/enrich body
// instead ({ids, reveal}, no contacts/identity object at all — §8.1, a genuinely
// different endpoint, not a property added to search-and-enrich). Falls back to the
// unchanged lushaContactBody() output when no stored id is present (never regresses a
// first-time enrichment). Apollo people/match = JSON body with reveal_personal_emails.
// ZoomInfo builds its own body from the Gate identity.
return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity_keys || {};
  const missingFields = (row.gate && row.gate.missingFields) || [];
  const storedContactId = row.existingRecord && row.existingRecord.lusha_contact_id;
  const lusha_body = lushaContactEnrichByIdBody(storedContactId, missingFields)
    || lushaContactBody(id, missingFields);
  const apollo_body = { reveal_personal_emails: true };
  if (id.email) apollo_body.email = id.email;
  if (id.domain) apollo_body.domain = id.domain;
  if (id.firstName) apollo_body.first_name = id.firstName;
  if (id.lastName) apollo_body.last_name = id.lastName;
  if (id.companyName) apollo_body.organization_name = id.companyName;
  return { json: { ...row, lusha_body, apollo_body } };
});
"""

# HubSpot read-only search body (existence check): by email if present, else first+last name.
# Phase 66 REVIEW-FIX (WR-01): was a KNOWN-NARROWER sibling of
# ENRICH_CONTACT_SEARCH_PROPERTIES_CSV (used only by build_enrichment_local_live()),
# recorded as deliberately untouched by 66-01/66-02's scope. That gap meant this
# workflow's "Enrichment Gate" read a `fill_blank_only`/`stale_refreshable` field's true
# current value as `undefined` whenever it was one of the 7 fields this list omitted —
# the non-clobber comparison in mergeContacts.js then reads "blank" and computes a wrong
# promote decision. Widened here to every one of ENRICH_GATE's 12 REQUIRED fields, same
# fields ENRICH_CONTACT_SEARCH_PROPERTIES_CSV already fetches for the CLOUD lane.
#
# NOT mechanically derived from ENRICH_GATE's REQUIRED (hand-synced, same as
# ENRICH_CONTACT_SEARCH_PROPERTIES_CSV already was before this fix): REQUIRED is a JS
# array literal embedded inside ENRICH_GATE's `r"""..."""` string, not a Python-level list
# this module could import (66-02-SUMMARY's own D-66-10 parity note makes the same
# observation about the companies side). Lifting REQUIRED out into a shared Python
# constant both JS sites read from is a real refactor, out of scope for a review fix.
# tests/n8n/fieldProducerMatrix.test.mjs's generic fetch-gate assertion (WR-03) is the
# drift guard in lieu of derivation — it fails loudly if this list and ENRICH_GATE's
# REQUIRED are ever hand-edited out of sync again.
HS_SEARCH_BODY_EXPR = (
    '={{ JSON.stringify({ filterGroups: [ { filters: '
    '($json.identity_keys.email ? [ { propertyName: "email", operator: "EQ", value: $json.identity_keys.email } ] '
    ': [ { propertyName: "firstname", operator: "EQ", value: $json.identity_keys.firstName }, '
    '{ propertyName: "lastname", operator: "EQ", value: $json.identity_keys.lastName } ]) } ], '
    'properties: ["email","firstname","lastname","jobtitle","phone","mobilephone",'
    '"lv_jobtitle_verified_at","lv_mobilephone_verified_at","seniority",'
    '"lv_contact_enrichment_provenance","lusha_contact_id",'
    '"city","state","country","hs_state_code","hs_country_region_code",'
    '"lv_linkedin_url","lv_persona_group"], limit: 5 }) }}'
)

# ---- COMPANIES branch -------------------------------------------------------
# Sibling of the contacts chain, NOT nested under it: the ICP fields it resolves
# (lv_org_type / lv_produces_content) are per-DOMAIN and expensive, so running them
# once per contact would re-pay for every contact at the same company. Company
# targets are deduped by domain here; contacts join back on domain downstream.
#
# Read-only, like the contacts branch: HubSpot SEARCH only, no write nodes.
#
# ZoomInfo is deliberately absent — its GTM /companies/enrich contract is not yet
# verified live (the contacts one took a full probe session). Lusha /v2/company and
# Apollo /v1/organizations/enrich are both confirmed 200 against racingnsw.com.au.

# ZoomInfo GTM companies/enrich — contract probed live 2026-07-20 (all 200):
#   POST /gtm/data/v1/companies/enrich   type "CompanyEnrich", matchCompanyInput[]
#   POST /gtm/data/v1/companies/search   type "CompanySearch"   (not used here)
# Limits: 1-25 companies and max 25 outputFields per request. Scope api:data:company
# is present on the existing client-credentials token — no separate credential needed.
ENRICH_ZOOMINFO_CO_CACHED = _zoom_preamble(
    "https://api.zoominfo.com/gtm/data/v1/companies/enrich") + r"""
// Companies enrich contract (LIVE-confirmed 200 against racingnsw.com.au):
//   { data: { type: "CompanyEnrich", attributes: { matchCompanyInput:[{companyWebsite|companyName}],
//     outputFields:[...] } } }
// Response: { data:[{ id, type:"Company"|"NoMatch", attributes:{...}, meta:{matchStatus} }] }.
//
// Every outputField below returned 200 when probed individually. `companyType` is NOT
// valid/entitled (400 PFAPI0009) — do not re-add it without re-probing.
//
// UNITS WARNING: `revenue` is in THOUSANDS. `revenueRange` ("$250 mil. - $500 mil.") is
// requested alongside it because normalizeProviders prefers the unambiguous string.
const ZOOM_CO_OUTPUT_FIELDS = [
  "id", "name", "website", "revenue", "revenueRange", "employeeCount", "employeeRange",
  "country", "primaryIndustry", "naicsCodes", "descriptionList", "foundedYear",
];
function toMatchCompanyInput(id) {
  const m = {};
  if (id && id.domain) m.companyWebsite = id.domain;
  if (id && id.companyName) m.companyName = id.companyName;
  return m;
}
// A domain OR a company name is enough; a keyless matchCompanyInput is itself a 400.
function hasZoomCoKey(m) { return !!(m.companyWebsite || m.companyName); }

// Phase 70 Plan 04 (D-70-04): fed by "Apollo Org Result Carry Merge" (or a bypassed
// provider's own row, unmodified) — $input here IS the row directly, no by-name
// recovery of "Company Gate" (D-70-01/D-70-03).
const items = $input.all();
const out = [];
for (let i = 0; i < items.length; i++) {
  const row = items[i].json;
  const id = row.identity_keys || {};
  const co = toMatchCompanyInput(id);
  const payload = hasZoomCoKey(co)
    ? { data: { type: "CompanyEnrich", attributes: { matchCompanyInput: [co], outputFields: ZOOM_CO_OUTPUT_FIELDS } } }
    : null;
  if (!payload) { out.push({ json: { ...row, zoominfo_result: { skipped: "no zoominfo company match key" } } }); continue; }
  let token = await getToken.call(this);
  let res;
  try {
    res = await enrich.call(this, token, payload);
  } catch (e) {
    if (isAuthError(extractErrorStatus(e))) {
      delete sd.zoominfo;                     // token rejected -> re-mint once + retry
      token = await mint.call(this);
      try { res = await enrich.call(this, token, payload); }
      catch (e2) { res = { error: String((e2 && e2.message) || e2) }; }
    } else {
      res = { error: String((e && e.message) || e) };  // non-auth error -> continue
    }
  }
  out.push({ json: { ...row, zoominfo_result: res } });
}
return out;
"""

ENRICH_EMIT_COMPANIES = r"""// Emit Company Targets — LOCAL-LIVE companies branch.
// Same real ICP accounts as the contacts branch, deduped by domain: one row per company
// no matter how many contacts share it. That dedupe is the whole reason this branch is a
// sibling of the contacts chain rather than nested inside it.
const rows = [
  { company: "Harvey Norman",         domain: "harveynorman.com.au" },
  { company: "Racing NSW",            domain: "racingnsw.com.au" },
  { company: "Melbourne Racing Club", domain: "mrc.net.au" },
  { company: "Australian Turf Club",  domain: "australianturfclub.com.au" },
  { company: "FanDuel",               domain: "fanduel.com" }
];
const seen = new Set();
return rows.filter((r) => {
  const d = (r.domain || "").trim().toLowerCase();
  if (!d || seen.has(d)) return false;
  seen.add(d);
  return true;
}).map((r) => ({ json: { ...r, object_type: "companies" } }));
"""

ENRICH_BUILD_CO_IDENTITY = r"""// Build Company Identity — companies branch.
// Domain is the identity anchor for companies (email is for contacts). Lowercased +
// stripped of scheme/www so it matches HubSpot's stored `domain` form.
function cleanDomain(raw) {
  if (!raw) return null;
  let d = String(raw).trim().toLowerCase();
  d = d.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
  return d || null;
}
return $input.all().map((it) => {
  const row = it.json;
  const domain = cleanDomain(row.domain || row.website);
  return { json: { ...row,
    object_type: "companies",
    identity_keys: { domain, companyName: row.company || row.name || null },
  }};
});
"""

# Company existence check: by domain (the identity anchor). Property list is the 5 lv_*
# props that ACTUALLY exist in portal 22617666 plus the core firmographics, PLUS (Phase 15)
# the 2 company cache-key datetimes ENRICH_CO_GATE's staleness check reads — HubSpot
# silently drops unknown names from `properties` and still returns 200, so asking for
# not-yet-created props would read back as undefined and be indistinguishable from empty
# (harmless pre-migration; becomes meaningful once scripts/sync_hubspot_properties.py runs).
#
# Phase 66 REVIEW-FIX (WR-01): widened with the 6 fields 66-02's Company Gate REQUIRED
# widening (2->13) added but this LOCAL-LIVE sibling never picked up —
# lv_revenue_band/lv_employee_band/lv_country_region_normalized/country/city/
# lv_sponsorship_reliant — same fields ENRICH_COMPANY_SEARCH_PROPERTIES_CSV already
# fetches for the CLOUD lane (see that constant's own Plan 02 Task 2 comment). Without
# these, mergeCompanies.js reads a genuinely-populated field as blank on this lane's
# preview and computes a wrong promote decision (reproduced live in 66-REVIEW.md WR-01).
#
# NOT mechanically derived from ENRICH_CO_GATE's REQUIRED — same reason as
# HS_SEARCH_BODY_EXPR above: REQUIRED is a JS array literal inside a `r"""..."""` string,
# not a Python-level list either could import without a real refactor (out of scope here).
# fieldProducerMatrix.test.mjs's generic fetch-gate assertion (WR-03) is the drift guard.
HS_CO_SEARCH_BODY_EXPR = (
    '={{ JSON.stringify({ filterGroups: [ { filters: '
    '[ { propertyName: "domain", operator: "EQ", value: $json.identity_keys.domain } ] } ], '
    'properties: ["name","domain","industry","annualrevenue","numberofemployees",'
    '"lv_org_type","lv_produces_content","lv_content_type","lv_is_hardware_vendor",'
    '"lv_is_gambling_operator","lv_icp_tier","lv_icp_fit_score","lv_anti_icp_flag",'
    '"lv_enrichment_provenance",'
    '"lv_org_type_verified_at","lv_produces_content_verified_at","lusha_company_id",'
    # Phase 62 Plan 04 (D-62-16): a native, read-only HubSpot rollup — confirmed
    # present in every committed portal-schema baseline. A read-field addition, not
    # a write; the suggestion round's zero-associated-contacts check reads this.
    '"num_associated_contacts",'
    '"lv_revenue_band","lv_employee_band","lv_country_region_normalized","country","city",'
    '"lv_sponsorship_reliant"], '
    'limit: 5 }) }}'
)

# Task 6 hardening (review #8) — same contract as ENRICH_ADAPT_SEARCH's fail-closed
# lookup_failed tagging + hs_object_id preservation; see that constant's comment.
ENRICH_ADAPT_CO_SEARCH = r"""// Adapt Company Search -> existingRecord — companies branch.
// Same contract as the contacts Adapt Search: per-row, same order, 0 results => {} => CREATE.
// Phase 62 Plan 04 (D-62-16): num_associated_contacts is carried as a TOP-LEVEL row key,
// never nested only inside existingRecord — this repo has a recorded suspicion that HTTP
// hops strip existingRecord on this lane, and a top-level key that degrades to null is the
// honest failure mode the plugin's eligibility tri-state already handles. Coerced to a
// number; stamped null (never omitted) on a failed lookup or an unparseable/absent value —
// HubSpot returns property values as strings, and a zero-hit search never reaches the
// coercion at all (existingRecord stays {}), so it stamps null too, not the number 0.
function _numAssociatedContacts(existingRecord) {
  const raw = existingRecord && existingRecord.num_associated_contacts;
  if (raw === undefined || raw === null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}
// Phase 70 Plan 04 (D-70-04): "HubSpot Company Search Carry Merge" (splice_carry_merge_
// after, carry_source "IF Company Bare Event" FALSE lane — source_out_idx=1) re-attaches
// the pre-hop row onto the raw search response, row-fields-last. $input here is ALREADY
// that combined item — no by-name recovery of "Build Company Identity"/"HubSpot Company
// Search" (D-70-01/D-70-03).
return $input.all().map((it) => {
  const merged = it.json;
  const failed = !!merged.error;
  if (failed) {
    return { json: { ...merged, existingRecord: {}, lookup_failed: true, num_associated_contacts: null } };
  }
  let existingRecord = {};
  if (Array.isArray(merged.results)) {
    if (merged.results.length) {
      const first = merged.results[0];
      existingRecord = { ...(first.properties || {}), hs_object_id: first.id };  // search envelope
    }
  } else if (merged.properties) {
    existingRecord = { ...merged.properties, hs_object_id: merged.id };          // single object
  }
  return { json: { ...merged, existingRecord, lookup_failed: false,
    num_associated_contacts: _numAssociatedContacts(existingRecord) } };
});
"""

# 2026-08-25: domain-only resolution proved insufficient LIVE — Harness Racing NSW sits in
# portal 22617666 as company 18756544347 under domain `www.harnessmediacentre.com.au`, so a
# `hrnsw.com.au` request resolved to NOTHING and the gate said "create". That is the
# duplicate-company outcome the operator ruled out ("if that company already exists in
# HubSpot, it should never be recreated"). The name search is the same second key the ingest
# lane resolves on (n8n/code/companyLink.js), applied here as the fallback: EXACT name only,
# and only when exactly one company carries that name — two same-named companies is an
# ambiguity, and picking either would be the mis-association a domain miss was already
# safer than.
HS_CO_NAME_SEARCH_FILTERS = [[{
    "propertyName": "name", "operator": "EQ",
    # `.invalid` sentinel, the Phase 36 Finding B idiom: an `undefined` filter value makes
    # HubSpot reject the whole search, which onError:continueRegularOutput would then
    # swallow into an item; a sentinel returns a clean 200 with zero hits.
    # Phase 70 Plan 04 (D-70-04): bare $json — this node is fed by "Adapt Company
    # Search", whose own carry merge (splice_carry_merge_after) already re-attaches
    # "Build Company Identity"'s row onto the domain search's response, so $json IS
    # that carried row here (never a by-name lookup).
    "value": ("={{ $json.identity_keys.companyName "
              "|| 'no company name .invalid' }}"),
}]]

ENRICH_ADAPT_CO_NAME_SEARCH = r"""// Adapt Company Name Search — the domain miss's second chance.
// Only rows whose domain search found NOTHING are eligible: a domain hit is the stronger
// key and is never overridden by a name. A failed domain lookup (lookup_failed) is left
// exactly as it is — fail-closed, an unknown is not an absence.
//
// Phase 70 Plan 04 (D-70-04): "HubSpot Company Name Search Carry Merge" (splice_carry_
// merge_after, carry_source "Adapt Company Search") re-attaches the row (which already
// carries the domain search's own existingRecord/lookup_failed) onto the name search's
// raw response, row-fields-last. $input here is ALREADY that combined item — no by-name
// recovery of "Adapt Company Search"/"HubSpot Company Name Search" (D-70-01/D-70-03).
return $input.all().map((it) => {
  const merged = it.json;
  const { results, error, ...row } = merged; // strip the name search's OWN response fields
  const existing = row.existingRecord || {};
  if (row.lookup_failed === true || existing.hs_object_id) return { json: row };
  const wanted = String((row.identity_keys && row.identity_keys.companyName) || "").trim().toLowerCase();
  if (!wanted) return { json: row };
  if (error) return { json: row };
  const hits = (Array.isArray(results) ? results : []).filter(
    (r) => r && r.id &&
      String((r.properties || {}).name || "").trim().toLowerCase() === wanted
  );
  if (hits.length !== 1) return { json: row };
  return { json: { ...row,
    existingRecord: { ...(hits[0].properties || {}), hs_object_id: String(hits[0].id) },
    company_match_basis: "name",
  }};
});
"""

# Company staleness gate. Different REQUIRED + TTL anchor from contacts — this is exactly
# why the branches are siblings and not one shared gate node.
#
# NOTE: lv_*_verified_at / lv_icp_scored_at do not exist in the portal yet, so every
# present-but-unstamped ICP field reads as stale (enrichmentGate: unknown freshness ==
# needs validation). That is the conservative direction; it stops being noisy once the
# metadata props are created.
ENRICH_CO_GATE = inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js") + r"""

// --- n8n wrapper: decideAction(existingRecord) -> create | enrich | skip ---
// Phase 66 Plan 02 (D-66-01 companies half, RICH-02, RICH-05): REQUIRED is DERIVED from
// 66-COVERAGE.md, not chosen by intuition — tests/n8n/fieldProducerMatrix.test.mjs's
// chase-gate assertion enforces this derivation mechanically. The rule: a
// config/field_policy.yaml `companies` key is included only when ALL THREE hold —
// (1) promote_to_canonical: true, (2) class is neither score_output nor veto_output,
// (3) the matrix records at least one producing branch (a provider `_push` OR, for the
// six ICP fields no provider branch emits, the Claude web-research lane, recognised via
// each field's own `allow_web_research: true` policy flag).
//
// Excluded, each for a load-bearing reason (66-COVERAGE.md's companies table):
//   - `domain`: promote_to_canonical: false AND producer-less (open todo, not this plan's
//     fix: .planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md).
//     Including a producer-less required field marks every company permanently incomplete.
//   - `annualrevenue`: review_required / stage_only / promote_to_canonical: false. The
//     pipeline can never fill it canonically, so a required-but-unfillable field would
//     gate every company without a human-entered value to `enrich` forever, on every
//     scheduled tick — the 2026-08-09 execution-runaway shape. The single most important
//     exclusion here.
//   - `lv_anti_icp_flag` / `lv_anti_icp_reason`: veto_output, recomputed by Decide Company
//     Action from current inputs every run — never chased, same reasoning that keeps the
//     derived ICP fit-score field out of the contacts REQUIRED list.
//
// `numberofemployees` IS included (matrix shows it promotable with producers): this
// CHASES the field but changes nothing about what the merge will accept —
// CLAUDE.md §29.1's ONE scoped exception (58-05 Task 2) stays exactly as scoped:
// fill_blank_only, already-numeric provider values only, no band parsing. Chasing is not
// widening the exception.
const REQUIRED = [
  "industry", "numberofemployees", "lv_revenue_band", "lv_employee_band",
  "lv_country_region_normalized", "country", "city",
  "lv_org_type", "lv_produces_content", "lv_content_type",
  "lv_sponsorship_reliant", "lv_is_hardware_vendor", "lv_is_gambling_operator",
];
// POLICY unchanged (D-66-09 discipline applies to both lanes): only the two pre-existing
// TTL entries. No new stale_after_days added — a TTL on a field decideAction never reads
// through a stale_refreshable branch is inert (D-66-09's own reasoning for `phone`).
const POLICY = {
  lv_org_type: { stale_after_days: 180 },
  lv_produces_content: { stale_after_days: 180 },
};
const NOW = new Date().toISOString();
// Phase 70 Plan 04 Task 2 (D-70-03): reads the request-level `recompute` intent off the
// ROW itself, never a by-name lookup of `Parse HubSpot Event`. "Parse HubSpot Event"
// stamps `recompute` onto every row it emits (Phase 47.5's own normalisation, unchanged
// in placement — see ENRICH_PARSE_EVENT_CLOUD's own comment); Task 1's carry merges
// (splice_carry_merge_after) re-attach the row after every HTTP hop between there and
// here, so the field survives untouched. `wf_enrichment_local_live`'s "Company Gate"
// shares this SAME constant but has no `Parse HubSpot Event` node at all — its rows
// simply never carry the field, so `row.recompute === true` is `false` there exactly as
// the old try/catch's fail-closed default was, with no special-casing needed.
// (Phase 66 REVIEW-FIX, WR-02: `wf_scheduled_maintenance_cloud`'s "SJ-2 Company Gate" no
// longer reuses this constant — see SJ2_CO_GATE below.)
// Phase 70 Plan 03 (D-70-01): this node sits behind a real Merge (Company Gate's 2
// identity lanes) with a starved-lane sentinel on any input that could otherwise never
// fire; drop an identity-less sentinel marker before it is treated as a real row.
return $input.all().filter((it) => Object.keys(it.json || {}).length > 0).map((it) => {
  const row = it.json;
  const RECOMPUTE_REQUESTED = row.recompute === true;
  const gate = decideAction(row.existingRecord || {}, REQUIRED, POLICY, NOW);
  let action = gate.action;
  // Fail-closed (Task 6, review #8) — see ENRICH_GATE's identical comment (contacts).
  if (row.lookup_failed === true && action === "create") action = "skip";
  // Phase 47.5 (RECOMP-01) — exactly two mappings, and only under the request-level intent
  // resolved above:
  //   skip   -> enrich            a COMPLETE record is otherwise frozen: Normalize + Score
  //                               drops it and the sole veto writer never runs (exec 11846)
  //   create -> recompute_refused a recompute for a record that resolved to nothing must
  //                               NEVER seed a junk company (BUG 19 shape). It falls
  //                               through both write IFs to Build Response.
  // `enrich` is untouched. `gate` itself is left intact apart from the refusal reason —
  // the reason string is what makes the outcome readable in the response.
  if (RECOMPUTE_REQUESTED) {
    if (action === "skip") {
      action = "enrich";
    } else if (action === "create") {
      action = "recompute_refused";
      gate.reason =
        "a recompute was requested for a company that did not resolve to an existing " +
        "record — refused rather than created (" + gate.reason + ")";
    }
  }
  return { json: { ...row, gate, action } };
});
"""

# SJ-2's own companies gate — Phase 66 REVIEW-FIX (WR-02). SJ-2's job (CLAUDE.md §19.5,
# "monthly stale ICP refresh") is narrowly "confirm the ICP org-type/produces-content
# classification is fresh", not "confirm the whole companies record is complete" — that
# broader completeness chase is ENRICH_CO_GATE's job (Enrichment webhook + LOCAL-LIVE
# preview), fed by a fetch list widened to match its own 13-field REQUIRED.
#
# SJ-2 Company Gate used to reuse ENRICH_CO_GATE directly when ENRICH_CO_GATE's REQUIRED
# was exactly these same two fields (pre-66-02) — the node's own comment even called it
# "the reused, UNMODIFIED Company Gate". 66-02 widened ENRICH_CO_GATE's REQUIRED to 13
# fields for the completeness-chase lanes without noticing SJ-2 shared the same constant:
# `SJ-2 Search (stale refresh)` still only ever fetched the 2 fields this gate originally
# needed (plus the 2 verified-at cache keys and hs_object_id/domain), so the other 11
# newly-required fields always read as `undefined` on `existingRecord` and SJ-2 gated to
# "enrich" for virtually every row regardless of actual staleness — a real over-triggering
# regression, since SJ-2's dispatch (unlike ENRICH_CO_GATE's other two consumers) writes a
# real HubSpot property (`lv_enrichment_requested=true`) once armed.
#
# Fix: give SJ-2 its own REQUIRED/POLICY, restoring the exact pre-66-02 shape (the two ICP
# classification fields, both with the 180-day TTL SJ-2's own epoch-cutoff filter already
# confirms upstream) rather than widening `SJ-2 Search`'s fetch to the full 13-field list —
# widening the fetch would only relocate the bug: SJ-2 would then gate on completeness of
# 11 fields unrelated to its documented staleness job, and a record missing one of those
# (e.g. a producer-less companies signal) would re-trigger every month forever, the same
# shape of over-triggering this fix removes. `SJ-2 Search`'s existing 6-field fetch already
# covers this narrower REQUIRED in full — no fetch-list change needed here.
SJ2_CO_GATE = inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js") + WRITE_REQUEST_JS + r"""

// --- n8n wrapper: decideAction(existingRecord) -> create | enrich | skip ---
// SJ-2-specific REQUIRED/POLICY — deliberately NOT ENRICH_CO_GATE's 13-field completeness
// list (see this constant's own comment above). Two ICP classification fields only, both
// with the 180-day staleness TTL SJ-2's search already filters on upstream.
const REQUIRED = ["lv_org_type", "lv_produces_content"];
const POLICY = {
  lv_org_type: { stale_after_days: 180 },
  lv_produces_content: { stale_after_days: 180 },
};
const NOW = new Date().toISOString();
// SJ-2 is a scheduled job, never a webhook — no `Parse HubSpot Event` node exists in this
// workflow, so recompute intent can never be requested here. Phase 70 Plan 04 (D-70-04):
// was a guarded by-name lookup that could only ever catch and fall back to false (no such
// node to find); replaced with the constant it always evaluated to.
const RECOMPUTE_REQUESTED = false;
return $input.all().map((it) => {
  const row = it.json;
  const gate = decideAction(row.existingRecord || {}, REQUIRED, POLICY, NOW);
  let action = gate.action;
  // Fail-closed (Task 6, review #8) — see ENRICH_GATE's identical comment (contacts).
  if (row.lookup_failed === true && action === "create") action = "skip";
  if (RECOMPUTE_REQUESTED) {
    if (action === "skip") {
      action = "enrich";
    } else if (action === "create") {
      action = "recompute_refused";
      gate.reason =
        "a recompute was requested for a company that did not resolve to an existing " +
        "record — refused rather than created (" + gate.reason + ")";
    }
  }
  // D-70-12 (Phase 70 Plan 05 Task 1): "SJ-2 Set Requested" is fed via "SJ-2 IF Skip"'s
  // false branch, whose nearest upstream Code node is this one.
  return { json: { ...row, gate, action,
    write_request: _buildWriteRequest("enrich", row.hs_object_id || null, row.domain || null, null) } };
});
"""

ENRICH_BUILD_CO_REQUESTS = inline("lushaRequest.js") + r"""

// --- n8n wrapper: Build Company Provider Requests — companies branch. ---
// Lusha: POST /v3/companies/search-and-enrich, body {"companies":[{"domain":...}]}
// (docs/LUSHA-V3-CONTRACT.md §5, live-confirmed 2026-07-30) — built by the shared
// lushaCompanyBody(), domain ONLY. History: the retired v2 GET /v2/company?domain=
// endpoint (BUG 17, re-probed live 2026-07-29 against racingnsw.com.au) rejected
// `companyName` outright ("property companyName should not exist" as a query param,
// mirroring the same-shaped rejection the old POST body got for `domain`) — that is
// why companyName has never been part of the Lusha company identity and still isn't
// under v3; it lives on in identity_keys for the other providers only.
// Apollo: unchanged, still POST /v1/organizations/enrich?domain=.
return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity_keys || {};
  const lusha_company_body = lushaCompanyBody(id);
  const apollo_org_url =
    "https://api.apollo.io/v1/organizations/enrich?domain=" + encodeURIComponent(id.domain || "");
  return { json: { ...row, lusha_company_body, apollo_org_url } };
});
"""

ENRICH_NORMALIZE_SCORE_CO = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
) + r"""

// --- n8n wrapper (companies): score best-per-field from the row's own carried results ---
// object_type is pinned to "companies" so toCandidates takes its companies branch — the
// one that emits lv_revenue_band / lv_employee_band / lv_country_region_normalized.
// Phase 70 Plan 04 (D-70-04): "Lusha Result Carry Merge"/"Apollo Result Carry Merge"
// stamp `lusha_result`/`apollo_result` onto the row; "ZoomInfo Company" stamps its own
// `zoominfo_result` directly. $input here is ALREADY one item per row carrying all
// three — no by-name recovery of "Company Gate"/"Lusha Company"/"Apollo Org"/"ZoomInfo
// Company" (D-70-01/D-70-03).
return $input.all().map((it) => {
  const row = it.json;
  const p = {
    lusha: row.lusha_result,
    apollo: row.apollo_result,
    zoominfo: row.zoominfo_result,
  };
  const cands = [
    ...toCandidates("lusha", p.lusha, "companies"),
    ...toCandidates("apollo", p.apollo, "companies"),
    ...toCandidates("zoominfo", p.zoominfo, "companies"),
  ];
  const gap_flag = cands.length === 0;
  const { best, winners } = scoreCandidates(cands, { now: new Date().toISOString() });
  // Per-field {source, value} list — lets the merge node report WHICH providers disagreed
  // rather than just that they did.
  const sourcesByField = {};
  for (const c of cands) {
    (sourcesByField[c.field] || (sourcesByField[c.field] = []))
      .push({ source: c.source, value: c.normalizedValue });
  }
  // Plan 04: sibling row field, never a candidate — see ENRICH_NORMALIZE_SCORE's comment.
  const lushaId = lushaRecordId(p.lusha, "companies");
  const lusha_ids = lushaId ? { lusha_company_id: lushaId } : null;
  const { lusha_result, apollo_result, zoominfo_result, ...cleanRow } = row;
  return { json: { ...cleanRow, providers: p, scored: { best, winners, sourcesByField }, gap_flag,
    ...(lusha_ids ? { lusha_ids } : {}) } };
});
"""

# --- Phase 13: web research retrieval + validation (companies branch only, D4) --------
# lv_org_type / lv_produces_content ARE now resolvable — not from the firmographic
# providers above (Lusha/Apollo/ZoomInfo do not carry them, CLAUDE.md Section 14), but
# from Claude web research, gated (RT-3/RT-4) and validated (OC-1..4/TS-1..3/AT-2/ER-1)
# before mergeCompanies ever sees them (D2/D6).

# Research Trigger Gate — RT-3/RT-4. Runs immediately after Normalize + Score Company,
# BEFORE the (expensive) HTTP call, per RESEARCH Pitfall 4: the per-run cost cap MUST be
# enforced upstream of the HTTP node, not per-item after it.
#
# cloud=False (LOCAL-LIVE): reads ALLOW_WEB_RESEARCH/MAX_WEB_RESEARCH_PER_RUN from
# $vars/$env at runtime. cloud=True (CLOUD): both are baked build-time literals from
# CONFIG_FLAG_DEFAULTS — zero $env/$vars survives (AR-4, Criterion 5).
# Phase 16.2 Task 1 (SC-2, RESEARCH SS1.3) — one `target` config parameterizes the six
# companies research/judge/validate/apply-verdict factories below. Every factory
# defaults to COMPANIES_TARGET, reproducing today's exact emitted string (byte-identity
# guard: tests/test_companies_factory_frozen.py). CONTACTS_TARGET is authored here but
# UNWIRED — no call site below passes it, and its inline_modules name sibling JS
# modules (contactResearch.js/contactJudge.js) that Plan 02 creates; inline() is never
# invoked with those names in THIS plan (would raise FileNotFoundError), because no
# factory is ever called with target=CONTACTS_TARGET here.
@dataclass(frozen=True)
class EnrichTarget:
    """A parameterization of the six companies research/judge factories. Field-bound JS
    (prompts, gap predicates, escalation) is carried as opaque JS-source fragments the
    shared factory scaffolding splices in — never as edits to the shared modules
    (judge.js/webResearch.js/scoreEnrichment.js/mergeCompanies.js stay git-unchanged,
    RESEARCH SS1.1)."""

    label: str
    gate_inline_modules: Sequence[str]
    gap_predicate_js: str
    gap_predicate_call_js: str
    research_inline_modules: Sequence[str]
    research_system_prompt_fn_js: str
    research_max_tokens_block_js: str
    research_payload_body_js: str
    validate_inline_modules: Sequence[str]
    validate_call_fn: str
    validate_row_recovery_comment_js: str
    research_pre_http_node: str
    judge_gate_inline_modules: Sequence[str]
    judge_gate_header_comment_js: str
    judge_pass1_block_js: str
    judge_pass3_unadjudicated_call_js: str
    judge_build_inline_modules: Sequence[str]
    build_judge_fn: str
    judge_max_tokens: int
    judge_pre_http_node: str
    apply_verdict_inline_modules: Sequence[str]
    apply_verdict_row_recovery_comment_js: str
    apply_verdict_call_js: str
    judge_confidence_carry_comment_js: str
    # Phase 16.2 Task 2 (gpt #5) — MARKER HYGIENE: when true, the research-gate wrapper
    # strips caller-injectable internal markers (research_candidate/judge_verdict/
    # judge_flags/judge_confidence_by_field/judge_promoted_fields) from every row BEFORE
    # anything else runs, because ENRICH_PARSE_EVENT_CLOUD spreads raw event props into
    # the row. Defaults False so COMPANIES_TARGET's emitted string is byte-identical to
    # before this field existed (companies has no such injection path in this plan's
    # scope — the frozen guard, tests/test_companies_factory_frozen.py, proves it).
    entry_strip_markers: bool = False


COMPANIES_TARGET = EnrichTarget(
    label="companies",
    gate_inline_modules=("taxonomy.generated.js",),
    gap_predicate_js=r"""// RT-3: fires when lv_org_type is unresolved/evidence-gated, OR lv_produces_content blank.
function needsResearch(existingRecord) {
  const rec = existingRecord || {};
  const orgType = rec.lv_org_type;
  const orgUnresolved = !orgType || orgType === "" || orgType === "unknown" ||
                        EVIDENCE_GATED_ORG_TYPES.indexOf(orgType) !== -1;
  const pc = rec.lv_produces_content;
  const contentBlank = pc === undefined || pc === null || pc === "";
  return orgUnresolved || contentBlank;
}""",
    gap_predicate_call_js="needsResearch(row.existingRecord)",
    research_inline_modules=("taxonomy.generated.js",),
    research_system_prompt_fn_js=r"""function researchSystemPrompt() {
  // TX-10 (Phase 49 Plan 03): mirrors src.taxonomy.org_type_definitions_block() -- a
  // discriminator present in the Python prompts and silently absent here is the root
  // cause of the Racing NSW statutory-origin misclassification (Phase 48 Plan 07).
  // ORG_TYPE_DEFINITIONS comes from n8n/code/taxonomy.generated.js (inlined above),
  // generated from config/taxonomy.yaml -- the same one source both prompts render.
  var orgTypeDefinitions = ORG_TYPES.map(
    function (k) { return "- " + k + ": " + ORG_TYPE_DEFINITIONS[k]; }
  ).join(" ");
  return [
    "You are an ICP research analyst for a sports-media/broadcast tech vendor.",
    "Research the company across three query intents: identity (<name> <domain> about),",
    "content (<name> watch live | broadcast | streaming), and size (<name> annual report",
    "revenue - only when a revenue band is not already known). First-party domains are",
    "preferred for identity and content; reputable secondary sources are fine for size.",
    "allowed_org_types: " + JSON.stringify(ORG_TYPES) + ".",
    "lv_org_type option definitions: " + orgTypeDefinitions,
    "allowed_content_types: " + JSON.stringify(CONTENT_TYPES) + ".",
    "Prefer \"unknown\"/null over guessing - an absent search result is NOT evidence of",
    "absence. For every field you set in `data`, cite a supporting URL in",
    "`evidence_by_field` keyed by that exact field name (e.g. evidence_by_field.lv_org_type,",
    "evidence_by_field.lv_produces_content). Also return `entity_resolution`:",
    "{ represents: one of group|subsidiary|franchise_outlet|single_entity|unknown,",
    "likely_revenue_band: string|null, notes: string }.",
    "lv_is_hardware_vendor and lv_is_gambling_operator are hard-veto inputs - answer null",
    "unless a cited source directly supports the classification.",
    "lv_sponsorship_reliant is a sponsorship-reliance signal, not a hard-veto input - answer",
    "null unless a cited source directly supports the classification.",
    "lv_country_region_normalized (one of AU|NZ|ANZ|Other|Unknown) feeds the non-ANZ",
    "hard veto - answer from cited evidence (HQ/about page), prefer \"Unknown\" over",
    "guessing, and cite it in evidence_by_field.lv_country_region_normalized.",
    "Return ONLY one JSON object, no prose, no markdown fences, matching:",
    '{"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,"lv_content_type":[<str>],',
    '"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>,',
    '"lv_sponsorship_reliant":<bool|null>,"lv_country_region_normalized":<str|null>},',
    '"evidence_by_field":{"<field>":"<url>"},"entity_resolution":{...},',
    '"matched":<bool>,"confidence":<int 0-100>}',
  ].join(" ");
}""",
    research_max_tokens_block_js=r"""    // ponytail: 2000 truncated live responses (stop_reason=max_tokens) before
    // evidence_by_field was written — extended thinking alone eats ~1000-1300 tokens.
    // 4096 leaves ~45% headroom over the largest observed complete response (2829).
    // Keep in parity with src/web_research.py's max_tokens (Phase 13 D-decision).
    max_tokens: 4096,""",
    research_payload_body_js=r"""      task: "company_icp_research",
      company: {
        name: id.companyName || row.company || null,
        domain: id.domain || row.domain || null,
      },
      known_revenue_band: (row.existingRecord && row.existingRecord.lv_revenue_band) || null,
      required_fields: ["lv_org_type", "lv_produces_content", "lv_content_type",
                        "lv_is_hardware_vendor", "lv_is_gambling_operator",
                        "lv_sponsorship_reliant", "lv_country_region_normalized"],
      return_only_json: true,""",
    validate_inline_modules=("taxonomy.generated.js", "taxonomy.js", "webResearch.js"),
    validate_call_fn="researchCandidateFromHttpItem",
    validate_row_recovery_comment_js=r"""// ROW-RECOVERY (bug fix): the upstream "Claude Web Research" HTTP node REPLACES $json with
// the API response, so it.json here is the HTTP response — NOT the enrichment row. The
// research candidate is correctly extracted from that response, but the row itself
// (existingRecord, scored, identity_keys, gap_flag) must be recovered by paired index from
// the last pre-HTTP node ("Build Research Request"), exactly as "Normalize + Score" recovers
// provider rows via $('Company Gate'). Without this, existingRecord/scored are lost for the
// rest of the research→judge→merge lane and Merge Company returns merge:null.""",
    research_pre_http_node="Build Research Request",
    judge_gate_inline_modules=("escalation.generated.js", "scoreEnrichment.js", "judge.js",
                                "providerConflict.js"),
    judge_gate_header_comment_js=r"""// RO-2: size-band disagreement is detected downstream inside Merge Company and is
// deliberately invisible here — this gate runs before that node, so no model call can
// ever be triggered by a size disagreement alone.
// Gap-closure 58-06 Task 2 (operator ruling 2026-08-26, T-58-26/§21.2): the five
// decision-driving material field groups (MATERIAL_CONFLICT_GROUPS) are the opposite of
// size — a cross-provider disagreement on one of them (detected here, from row.scored,
// via the SAME providerConflict.js predicate Merge Company uses) DOES route to the judge.
// RO-2 still holds: the size list is never passed to that call here, so no size field
// name is ever inlined into this node's jsCode.""",
    judge_pass1_block_js=r"""// Phase-15 provenance blob is a JSON string property that may be absent, empty, or
// malformed (truncated at the 60000-char cap, or simply never written yet) — a parse
// failure yields an empty object and must never throw (D1: without a parseable
// provenance blob, the independence guard has nothing to read and would fail OPEN).
function _parseProvenanceBlob(raw) {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return (parsed && typeof parsed === "object" && !Array.isArray(parsed)) ? parsed : {};
  } catch (e) {
    return {};
  }
}

// Pass 1: per row, evidence sufficiency (JG-4/D6, always) + TA-1 scoring (every
// researched row, escalated or not — scoring ranks, it never decides) + escalation
// trigger detection (JG-1/RO-1/RO-2). Does not decide the cap or the fail-safe yet —
// applyCostCap (TA-7) needs the full needs_judge set up front so the kill switch and the
// budget share one code path (pass 0 when off, MAX_PER_RUN when on), rather than a
// duplicated branch.
//
// BOUNDARY THAT MUST HOLD (D2/D3): research_scoring is strictly additive to the judge's
// INPUT. It must NEVER become an alternate escalation gate — a high composite score may
// never suppress an already-fired escalation reason. computeEscalation's reasons list
// remains the SOLE gate on whether the judge is invoked; research_scoring is never read
// by it.
const gated = $input.all().map((it) => {
  const row = it.json;
  const domain = (row.identity_keys && row.identity_keys.domain) ||
                 (row.existingRecord && row.existingRecord.domain) || null;
  const researchCandidate = applyEvidenceSufficiency(row.research_candidate, domain);

  const provenance = _parseProvenanceBlob(
    row.existingRecord && row.existingRecord.lv_enrichment_provenance);
  const research_scoring = scoreResearchCandidates(
    researchCandidate, row.existingRecord || {}, provenance, { now: NOW });

  const { needsJudge, reasons } = computeEscalation(researchCandidate, row.existingRecord || {});

  // Gap-closure 58-06 Task 2 (T-58-26/§21.2): the provider-vs-provider axis, detected
  // from row.scored (the cross-provider waterfall scoring) — a SEPARATE mechanism from
  // computeEscalation's research-vs-existing checks above, added HERE in the wrapper
  // rather than inside that function so the material field list never enters its closure
  // (RO-2's 2-arg arity, judge.js:97-102, is unaffected by this addition). Material
  // fields ONLY — never the size watch-list, which is computed inside Merge Company,
  // downstream of this node, and never referenced here.
  const materialConflicts = detectConflicts(row.scored, MATERIAL_CONFLICT_GROUPS.reduce(
    (acc, g) => acc.concat(g.fields), []));
  const material_conflicts = groupConflicts(materialConflicts, MATERIAL_CONFLICT_GROUPS);
  const providerConflictReasons = material_conflicts.map((g) => "provider_conflict:" + g.group);
  const allReasons = reasons.concat(providerConflictReasons);

  return { ...row, research_candidate: researchCandidate, research_scoring,
           needs_judge: allReasons.length > 0, judge_reasons: allReasons,
           material_conflicts };
});""",
    judge_pass3_unadjudicated_call_js=r"""    const researchCandidate = applyUnadjudicated(row.research_candidate, row.judge_reasons);
    return { json: { ...row, research_candidate: researchCandidate } };""",
    judge_build_inline_modules=("escalation.generated.js", "judge.js"),
    build_judge_fn="buildJudgeRequestBody",
    judge_max_tokens=4096,
    judge_pre_http_node="Build Judge Request",
    apply_verdict_inline_modules=("escalation.generated.js", "judge.js"),
    apply_verdict_row_recovery_comment_js=r"""// ROW-RECOVERY (bug fix): the upstream "Judge Call" HTTP node REPLACES $json with the API
// response, so it.json is the verdict response — NOT the row. The verdict is extracted from
// it.json, but the row (research_candidate, judge_reasons, judge_confidence_by_field,
// existingRecord, scored) must be recovered by paired index from "Build Judge Request".
// Without this, applyJudgeVerdict(undefined,...) throws / rebuilds a candidate holding only
// chosen_field, and existingRecord/scored never reach Merge Company (merge:null).""",
    apply_verdict_call_js=(
        "const research_candidate = applyJudgeVerdict(row.research_candidate, "
        "judge_verdict, row.judge_reasons);"
    ),
    judge_confidence_carry_comment_js=r"""  // TA-8 (D2-safe): when the verdict actually promoted/confirmed a field (judge_flags.
  // adjudicated is only set on that path), carry the VERDICT's own confidence — 0-100,
  // the same scale mergeCompanies' flat confidence already uses — forward for Merge
  // Company to apply as a per-field override. Never the A/R/G/T composite (D2): that
  // scale mismatch would silently stop nearly every research promotion.""",
)

# CONTACTS_TARGET — authored here per RESEARCH SS2/SS3, UNWIRED (Plan 02 wires the
# contact call sites + writes contactResearch.js/contactJudge.js). Field-agnostic
# helpers (applyCostCap, judgeVerdictFromHttpItem, extractFinalJson, scoreCandidates)
# are reused by co-inlining, never by editing the shared modules (judge.js:97-102 2-arg
# arity discipline on computeEscalation — CONTACTS_TARGET carries field config via this
# module-level config object, never a 3rd arg to computeContactEscalation).
CONTACTS_TARGET = EnrichTarget(
    label="contacts",
    gate_inline_modules=(),
    gap_predicate_js=r"""// Contact analog of RT-3 — PROVIDER-AWARE (runs after Normalize + Score, so both
// existingRecord and provider winners are visible): fires on provider_gap (a target
// field absent from BOTH existingRecord and provider winners) OR jobtitle_stale_refresh
// (existing jobtitle present but lv_jobtitle_verified_at older than the 180-day TTL —
// the clock lives HERE in the gate, not in computeContactEscalation, gpt #7/LOW-7).
// NOT a provider-vs-research comparison trigger (SC-3 honest-mirror decision) — that is
// the judge's job, not the gate's.
const CONTACT_RESEARCH_FIELDS = ["jobtitle", "seniority"];
const JOBTITLE_STALE_DAYS = 180;
function needsResearch(existingRecord, scored) {
  const rec = existingRecord || {};
  const winners = (scored && scored.winners) || {};
  for (const f of CONTACT_RESEARCH_FIELDS) {
    const existing = rec[f];
    const won = winners[f];
    const blank = existing === undefined || existing === null || existing === "";
    const noWinner = won === undefined || won === null || won === "";
    if (blank && noWinner) return true;  // provider_gap
  }
  if (rec.jobtitle && rec.lv_jobtitle_verified_at) {
    const verifiedAt = new Date(rec.lv_jobtitle_verified_at);
    if (!isNaN(verifiedAt.getTime())) {
      const ageDays = (Date.now() - verifiedAt.getTime()) / 86400000;
      if (ageDays > JOBTITLE_STALE_DAYS) return true;  // jobtitle_stale_refresh
    }
  }
  return false;
}""",
    gap_predicate_call_js="needsResearch(row.existingRecord, row.scored)",
    research_inline_modules=(),
    research_system_prompt_fn_js=r"""function researchSystemPrompt() {
  return [
    "You are a B2B contact-verification analyst. Research the person's CURRENT role at",
    "their company from public sources - prefer the company's own team/about/leadership",
    "page and the person's public professional profile (e.g. LinkedIn). Return the",
    "current job title and a seniority band. Prefer \"unknown\"/null over guessing - an",
    "absent result is NOT evidence. For every field you set, cite a supporting URL in",
    "`evidence_by_field` keyed by that exact field name (evidence_by_field.jobtitle,",
    "evidence_by_field.seniority). Return ONLY one JSON object, no prose, no markdown",
    "fences, matching:",
    '{"data":{"jobtitle":<str|null>,"seniority":<str|null>},',
    '"evidence_by_field":{"<field>":"<url>"},"matched":<bool>,"confidence":<int 0-100>}',
  ].join(" ");
}""",
    research_max_tokens_block_js=r"""    // gpt #11/LOW-6: research and judge budgets stay SEPARATE from the company chain
    // (which truncated live at 2000 before evidence_by_field, see the companies budget
    // comment above) - a 2-field contact response needs far less headroom than the
    // 5-field company ICP object, but 2048 still clears that floor with margin.
    max_tokens: 2048,""",
    # BUG (live, execution 11934, 2026-08-25): `contactName` is set by NOTHING — Build
    # Identity emits firstName/lastName — so `name` was always null and the research call
    # for a contact with no company/domain carried no identity at all. Haiku answered "I
    # need more information to research this contact", which is prose, so validation
    # extracted nothing and the row reported a clean empty result. Compose the name from
    # the keys the identity actually has, and pass the LinkedIn URL, which for a
    # name-and-profile-only contact is the ONLY strong identifier on the record.
    research_payload_body_js=r"""      task: "contact_role_research",
      contact: {
        name: id.contactName || row.contactName ||
              ([id.firstName, id.lastName].filter(Boolean).join(" ") || null),
        company: id.companyName || row.company || null,
        domain: id.domain || row.domain || null,
        linkedin_url: id.linkedin_url || row.linkedin_url || null,
      },
      required_fields: ["jobtitle", "seniority"],
      return_only_json: true,""",
    validate_inline_modules=("webResearch.js", "contactResearch.js"),
    validate_call_fn="contactResearchCandidateFromHttpItem",
    validate_row_recovery_comment_js=r"""// ROW-RECOVERY (mirrors bd682a2): the upstream "Contact Web Research" HTTP node
// REPLACES $json with the API response, so it.json here is the HTTP response — NOT the
// enrichment row. The research candidate is correctly extracted from that response, but
// the row itself (existingRecord, scored, identity_keys) must be recovered by paired
// index from the last pre-HTTP node ("Build Contact Research Request"), exactly as the
// companies branch recovers rows across this same HTTP hop (bd682a2).""",
    research_pre_http_node="Build Contact Research Request",
    judge_gate_inline_modules=("escalation.generated.js", "judge.js", "contactJudge.js"),
    judge_gate_header_comment_js=r"""// Contact judge gate: no size-band/vendor grounding applies here (contacts carry no
// firmographic candidates) — escalation is driven solely by computeContactEscalation.""",
    judge_pass1_block_js=r"""// Contact pass-1 (RESEARCH Task 3.4): NO A/R/G/T grounding — scoreResearchCandidates is
// company-only and field-bound (would force either a judge.js edit, a byte break, or a
// full duplicate). The contact judge escalates on conflict/stale/miss and adjudicates
// from the retrieved evidence + escalation_reasons alone.
const gated = $input.all().map((it) => {
  const row = it.json;
  const { needsJudge, reasons } = computeContactEscalation(row.research_candidate, row.existingRecord || {});
  return { ...row, needs_judge: needsJudge, judge_reasons: reasons };
});""",
    judge_pass3_unadjudicated_call_js=r"""    const researchCandidate = applyContactUnadjudicated(row.research_candidate, row.judge_reasons);
    return { json: { ...row, research_candidate: researchCandidate } };""",
    judge_build_inline_modules=("escalation.generated.js", "judge.js", "contactJudge.js"),
    build_judge_fn="buildContactJudgeRequestBody",
    judge_max_tokens=2048,
    judge_pre_http_node="Build Contact Judge Request",
    apply_verdict_inline_modules=("escalation.generated.js", "judge.js", "contactJudge.js"),
    apply_verdict_row_recovery_comment_js=r"""// ROW-RECOVERY (mirrors bd682a2): the upstream "Contact Judge Call" HTTP node REPLACES
// $json with the API response, so it.json is the verdict response — NOT the row. The
// verdict is extracted from it.json, but the row (research_candidate, judge_reasons,
// judge_confidence_by_field, existingRecord, scored) must be recovered by paired index
// from "Build Contact Judge Request", exactly as the companies branch does (bd682a2).""",
    apply_verdict_call_js=(
        "const research_candidate = applyContactJudgeVerdict(row.research_candidate, "
        "judge_verdict, row.judge_reasons);"
    ),
    judge_confidence_carry_comment_js=r"""  // TA-8 analog: when the verdict actually promoted/confirmed a field, carry the
  // VERDICT's own confidence forward for Merge Winners to apply as a per-field override
  // (mirrors the companies carry above; judge_confidence_by_field keys on chosen_field).""",
    entry_strip_markers=True,
)


def _enrich_research_gate_js(cloud=False, target=None):
    t = target or COMPANIES_TARGET
    # MARKER HYGIENE (gpt #5, t.entry_strip_markers): ONLY emitted for a target that opts
    # in (CONTACTS_TARGET) — COMPANIES_TARGET's default False keeps this block/row-read
    # exactly as before (byte-identity, tests/test_companies_factory_frozen.py).
    strip_fn = r"""
// MARKER HYGIENE (gpt #5): ENRICH_PARSE_EVENT_CLOUD spreads raw event props into the row
// (...event), so research_candidate/judge_verdict/judge_flags/judge_confidence_by_field/
// judge_promoted_fields are caller-INJECTABLE. Strip them here, the FIRST contact chain
// node, before anything else runs — these markers are (re)set ONLY by this chain's own
// downstream nodes (Validate Contact Research / Apply Contact Judge Verdict), never
// trusted from the inbound event.
function _stripInjectableMarkers(row) {
  const { research_candidate, judge_verdict, judge_flags, judge_confidence_by_field,
          judge_promoted_fields, ...clean } = row;
  return clean;
}
""" if t.entry_strip_markers else ""
    row_read = "_stripInjectableMarkers(it.json)" if t.entry_strip_markers else "it.json"
    return inline(*t.gate_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Research Trigger Gate ---
""" + strip_fn + _flag_const("ALLOW_WEB_RESEARCH", cloud) + "\n" + _flag_const("MAX_WEB_RESEARCH_PER_RUN", cloud) + r"""
const MAX_PER_RUN = parseInt(String(MAX_WEB_RESEARCH_PER_RUN), 10);

""" + t.gap_predicate_js + r"""

const allowOn = String(ALLOW_WEB_RESEARCH).toLowerCase() === "true";
let remaining = MAX_PER_RUN;
return $input.all().map((it) => {
  const row = """ + row_read + r""";
  if (!allowOn) {
    return { json: { ...row, research_needed: false, research_skip_reason: "ALLOW_WEB_RESEARCH=false" } };
  }
  const need = """ + t.gap_predicate_call_js + r""";
  if (need && remaining > 0) {
    remaining -= 1;
    return { json: { ...row, research_needed: true } };
  }
  return { json: { ...row, research_needed: false,
                   research_skip_reason: need ? "MAX_WEB_RESEARCH_PER_RUN reached" : "already resolved" } };
});
"""

# Build Research Request — RT-1/RT-2. D3: prompted free-text JSON, NOT a forced tool_use
# schema (mixing a client tool with the web_search server tool in one turn defers the
# search to a second round trip, breaking the single-HTTP-call n8n pattern).
#
# cloud=False (LOCAL-LIVE): ANTHROPIC_RESEARCH_MODEL/WEB_RESEARCH_MAX_SEARCHES read from
# $vars/$env. cloud=True (CLOUD): both baked build-time literals (AR-4, Criterion 5).
def _enrich_build_research_request_js(cloud=False, target=None):
    t = target or COMPANIES_TARGET
    return inline(*t.research_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Build Research Request ---
""" + t.research_system_prompt_fn_js + r"""

""" + _flag_const("ANTHROPIC_RESEARCH_MODEL", cloud) + "\n" + _flag_const("WEB_RESEARCH_MAX_SEARCHES", cloud) + r"""

return $input.all().map((it) => {
  const row = it.json;
  if (!row.research_needed) return { json: { ...row, research_request_body: null } };
  const id = row.identity_keys || {};
  const model = ANTHROPIC_RESEARCH_MODEL;
  const maxUses = parseInt(String(WEB_RESEARCH_MAX_SEARCHES), 10);
  const body = {
    model,
""" + t.research_max_tokens_block_js + r"""
    system: researchSystemPrompt(),
    messages: [{ role: "user", content: JSON.stringify({
""" + t.research_payload_body_js + r"""
    }) }],
    tools: [{ type: "web_search_20250305", name: "web_search", max_uses: maxUses }],
  };
  return { json: { ...row, research_request_body: body } };
});
"""

# Validate Research Output — OC-1..4/TS-1..3/AT-2/ER-1. The whole validation contract lives
# in webResearch.js's researchCandidateFromHttpItem (never throws) — this wrapper just calls
# it per item, so a malformed/errored/empty HTTP response can never fail the node (D5/D6).
def _enrich_validate_research_js(target=None):
    t = target or COMPANIES_TARGET
    return inline(*t.validate_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Validate Research Output ---
// Phase 70 Plan 04 (D-70-04): a carry merge sits immediately after the research HTTP
// node (input 0 its raw response, input 1 the row carried from `""" + t.research_pre_http_node + r"""`),
// re-attaching the row onto the response, row-fields-last. $input here is ALREADY that
// combined item — no by-name recovery (D-70-01/D-70-03). The raw response's OWN
// top-level fields are stripped after extraction (never spread forward): a row can
// cross ANOTHER HTTP hop later (the judge call) whose own raw response reuses the
// SAME field names (id/type/content/model/usage) — leaving them on the row would let
// this hop's stale response silently win a later merge's clash instead of the fresher
// one, corrupting the SUBSEQUENT hop's own recovery.
return $input.all().map((it) => {
  const research_candidate = """ + t.validate_call_fn + r"""(it.json);
  const { id, type, role, content, model, usage, stop_reason, stop_sequence, error, ...row } = it.json;
  return { json: { ...row, research_candidate } };
});
"""


# Module-level const NAME preserved (importers e.g. tests/test_cloud_companies_branch.py
# pull ENRICH_VALIDATE_RESEARCH by name) — computed by calling the parameterized
# producer with the companies default, so the emitted string is unchanged.
ENRICH_VALIDATE_RESEARCH = _enrich_validate_research_js()

# --- Phase 14: judge wiring (companies branch only). Runs on the research-true lane,
# UPSTREAM of Merge Company (D1) — the size-disagreement array/watch-list constant are
# computed INSIDE ENRICH_MERGE_CO below, so a node that runs before it structurally
# cannot reference them (RO-2 is proven by placement, not by comment; tests/test_judge_
# spec.py's test_ro2_judge_gate_cannot_see_size_conflicts asserts both the jsCode
# absence and the graph ancestry).

# Judge Gate — JG-4 (always, D6) + JG-1/RO-1/RO-2 escalation trigger + the D5 kill
# switches (ALLOW_JUDGE_ESCALATION, MAX_JUDGE_VALIDATIONS_PER_RUN, enforced HERE,
# physically upstream of the HTTP node — Pitfall 4 precedent).
#
# cloud=False (LOCAL-LIVE): both flags read from $vars/$env. cloud=True (CLOUD): both
# baked build-time literals (AR-4, Criterion 5).
def _enrich_judge_gate_js(cloud=False, target=None):
    t = target or COMPANIES_TARGET
    return inline(*t.judge_gate_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Judge Gate ---
""" + t.judge_gate_header_comment_js + r"""
""" + _flag_const("ALLOW_JUDGE_ESCALATION", cloud) + "\n" + _flag_const("MAX_JUDGE_VALIDATIONS_PER_RUN", cloud) + r"""
const allowOn = String(ALLOW_JUDGE_ESCALATION).toLowerCase() === "true";
const MAX_PER_RUN = parseInt(String(MAX_JUDGE_VALIDATIONS_PER_RUN), 10);
const NOW = new Date().toISOString();

""" + t.judge_pass1_block_js + r"""

// Pass 2: applyCostCap enforces the kill switch AND the per-run budget through the same
// path — 0 when escalation is off (caps every row), MAX_PER_RUN when it is on.
const capped = applyCostCap(gated, allowOn ? MAX_PER_RUN : 0);

// Pass 3: any row that had a trigger fire (judge_reasons non-empty) but ends up here
// with needs_judge false — whether from the kill switch or the cap — runs the D5
// fail-safe, so an unadjudicated hard-veto input never reaches Merge Company. Rows that
// never had a trigger (judge_reasons empty) are already needs_judge:false and untouched.
return capped.map((row) => {
  if ((row.judge_reasons || []).length > 0 && !row.needs_judge) {
""" + t.judge_pass3_unadjudicated_call_js + r"""
  }
  return { json: row };
});
"""

# Build Judge Request — JG-2 payload (identity + classification only, no size fields,
# no tools key).
#
# cloud=False (LOCAL-LIVE): ANTHROPIC_JUDGE_MODEL read from $vars/$env. cloud=True
# (CLOUD): baked build-time literal (AR-4, Criterion 5).
def _enrich_build_judge_request_js(cloud=False, target=None):
    t = target or COMPANIES_TARGET
    return inline(*t.judge_build_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Build Judge Request ---
""" + _flag_const("ANTHROPIC_JUDGE_MODEL", cloud) + r"""
return $input.all().map((it) => {
  const row = it.json;
  if (!row.needs_judge) return { json: { ...row, judge_request_body: null } };
  const model = ANTHROPIC_JUDGE_MODEL;
  const judge_request_body = """ + t.build_judge_fn + r"""(row, model, """ + str(t.judge_max_tokens) + r""");
  return { json: { ...row, judge_request_body } };
});
"""

# Apply Judge Verdict — JG-3 never-throws verdict handling + the promote/demote decision.
def _enrich_apply_judge_verdict_js(target=None):
    t = target or COMPANIES_TARGET
    return inline(*t.apply_verdict_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Apply Judge Verdict ---
// Phase 70 Plan 04 (D-70-04): a carry merge sits immediately after the judge HTTP node
// (input 0 its raw response, input 1 the row carried from `""" + t.judge_pre_http_node + r"""`),
// re-attaching the row onto the response, row-fields-last. $input here is ALREADY that
// combined item — no by-name recovery (D-70-01/D-70-03). The raw response's OWN
// top-level fields are stripped after extraction (never spread forward onto the row
// this node returns — the SAME leak-prevention _enrich_validate_research_js applies).
return $input.all().map((it) => {
  const judge_verdict = judgeVerdictFromHttpItem(it.json);
  const { id, type, role, content, model, usage, stop_reason, stop_sequence, error, ...row } = it.json;
  """ + t.apply_verdict_call_js + r"""

""" + t.judge_confidence_carry_comment_js + r"""
  let judge_confidence_by_field = row.judge_confidence_by_field || {};
  const adjudicated = research_candidate && research_candidate.judge_flags &&
    research_candidate.judge_flags.adjudicated === true;
  if (adjudicated && judge_verdict && judge_verdict.chosen_field) {
    judge_confidence_by_field = { ...judge_confidence_by_field,
      [judge_verdict.chosen_field]: judge_verdict.confidence };
  }

  return { json: { ...row, research_candidate, judge_verdict, judge_confidence_by_field } };
});
"""


# Module-level const NAME preserved (importers pull ENRICH_APPLY_JUDGE_VERDICT by name)
# — computed by calling the parameterized producer with the companies default, so the
# emitted string is unchanged.
ENRICH_APPLY_JUDGE_VERDICT = _enrich_apply_judge_verdict_js()

# hubspotEnums.generated.js + hubspotEnums.js are inlined ahead of mergeCompanies.js
# (Phase 31): mergeCompanies() now requires ./hubspotEnums for its own enum guard, so any
# node inlining it without the validator throws at runtime inside n8n.
ENRICH_MERGE_CO = JUNE_CANDIDATES_JS + inline(
    "taxonomy.generated.js", "hubspotEnums.generated.js", "hubspotEnums.js", "mergeCompanies.js",
    "escalation.generated.js", "providerConflict.js") + r"""

// --- n8n wrapper: mergeCompanies(existingRecord, winners) non-clobber ---
// lv_org_type / lv_produces_content resolve via Claude web research (see the Research
// Trigger Gate / Build Research Request / Validate Research Output nodes above) — a
// SECOND mergeCompanies call, folded in below (D6), supplies both the value and the
// evidence URL that mergeCompanies' own evidence gate requires before either may promote.
//
// TWO company-specific traps, both confirmed live against harveynorman.com.au:
//
// 1. scoreCandidates returns `winners[f] = top.value` — the RAW provider value, not the
//    normalized one. Contacts get away with it (Apollo's sanitized_number is already
//    E.164); companies do not. lv_revenue_band would have been written as
//    "$1 mil. - $5 mil." instead of the "1-5M" enum. Read `best[f].normalizedValue`.
//    scoreEnrichment is deliberately NOT changed — `winners` raw-ness is load-bearing for
//    contacts (jobtitle casing would be lowercased for every promoted contact).
//
// 2. Providers disagree wildly on company SIZE when the domain is a franchisor or a
//    holding company. harveynorman.com.au returned: ZoomInfo "Harvey Norman" $1-5m/34
//    staff, Apollo "Harvey Norman Seconds World" $33.6m/28, Lusha "Harvey Norman"
//    $1-10bn/10001-100000. Banded: 1-5M vs 5-50M vs 1B-1.2B — a 40-point ICP swing, and
//    the scorer silently picked one. Size is the ONLY entity-specific ICP signal (org_type,
//    produces_content, hardware/gambling, geography are all brand-level and inherit down to
//    any branch), so a size disagreement IS the franchise/subsidiary detector. Conflicted
//    fields never promote — CLAUDE.md §17.2 "NEEDS_REVIEW if providers materially conflict".
const CONFLICT_WATCH = ["lv_revenue_band", "lv_employee_band"];

// T-58-26/§21.2 (gap-closure 58-06, 2026-08-26, execution 11983): CONFLICT_WATCH above
// only ever covered the two size fields — a disagreement that can invert a franchise/
// subsidiary size guess, never one that can fire a hard veto. lv_country_region_normalized
// sat in the candidate loop below but OUTSIDE any watch list, so a cross-provider
// disagreement on it (ZoomInfo "United States" vs Lusha "AU") promoted the trust-rank
// winner unadjudicated and fired the Non-ANZ veto with no judge call and no review flag —
// a direct §21.2 violation. The five decision-driving fields (operator ruling 2026-08-26)
// get their OWN watch, modelled as GROUPS (MATERIAL_CONFLICT_GROUPS, from
// escalation.generated.js / config/escalation_policy.yaml) because
// lv_country_region_normalized and native `country` are one disputed fact with two
// HubSpot serializations — a conflict on either must suppress both under one reason
// (providerConflict.js's groupConflicts()). Size fields are modelled as their own
// singleton groups purely so ONE suppression pass below covers both watches uniformly —
// a size "group" can never be adjudicated (judge_confidence_by_field never carries a size
// field name, RO-2 keeps the size list out of Judge Gate entirely), so a size conflict
// always suppresses. That is the §17.2 review flag CONFLICT_WATCH's own comment above
// always claimed but the cloud lane never actually wrote (ENRICH_DECIDE_CO_CLOUD never
// read row.conflicts at all before this change).
const MATERIAL_WATCH = MATERIAL_CONFLICT_GROUPS.reduce((acc, g) => acc.concat(g.fields), []);
const SIZE_GROUPS = CONFLICT_WATCH.map((f) => ({ name: f, fields: [f] }));
const ALL_CONFLICT_GROUPS = [...SIZE_GROUPS, ...MATERIAL_CONFLICT_GROUPS];
const ALL_WATCHED_FIELDS = [...CONFLICT_WATCH, ...MATERIAL_WATCH];

// Phase 41 Task 3 (F1): native firmographic band derivation, reproducing
// src/normalizer.py's normalize_revenue_band / normalize_employee_band cut points
// exactly in JS. HubSpot returns every property as a STRING, so this needs an explicit
// Number() coercion the Python string-passthrough branch never needed — and Number("")
// is 0 (finite!), so the blank check must run BEFORE the numeric conversion, not after.
function _coerceNumeric(raw) {
  if (raw === null || raw === undefined) return null;
  const s = String(raw).trim();
  if (s === "") return null;
  const v = Number(s);
  return Number.isFinite(v) ? v : null;
}
function _bandRevenue(raw) {
  const v = _coerceNumeric(raw);
  if (v === null) return null;
  if (v < 1e6) return "<1M";
  if (v < 5e6) return "1-5M";
  if (v < 5e7) return "5-50M";
  if (v < 5e8) return "50-500M";
  if (v < 7.5e8) return "500-750M";
  if (v < 1e9) return "750M-1B";
  if (v < 1.2e9) return "1B-1.2B";
  return "1.2B+";
}
function _bandEmployees(raw) {
  const v = _coerceNumeric(raw);
  if (v === null) return null;
  if (v <= 9) return "1-9";
  if (v <= 50) return "10-50";
  if (v <= 200) return "51-200";
  if (v <= 500) return "201-500";
  if (v <= 1000) return "501-1000";
  return "1001+";
}

// Phase 41 Task 3 (D-04): the two fields a June-vs-fresh-research disagreement routes to
// needs_review instead of silently picking a source. Cache-key names hardcoded here
// (not imported from mergeCompanies.js's private COMPANY_CACHE_KEY_FIELDS -- that file
// is outside this task's scope) but must stay in lockstep with mergeCompanies.js's own
// map for these two fields; a node test pins this.
const JUNE_RESEARCH_CONFLICT_FIELDS = ["lv_org_type", "lv_produces_content"];
const JUNE_RESEARCH_CACHE_KEYS = {
  lv_org_type: "lv_org_type_verified_at",
  lv_produces_content: "lv_produces_content_verified_at",
};

// Phase 70 Plan 03 (D-70-01): this node ("Merge Company") sits behind a real Merge with
// a starved-lane sentinel on any of its 3 inputs that could otherwise never fire; drop
// an identity-less sentinel marker before it is mistaken for a real row.
return $input.all().filter((it) => Object.keys(it.json || {}).length > 0).map((it) => {
  const row = it.json;
  if (!row.scored) return { json: { ...row, merge: null, conflicts: [] } };  // skip branch
  const best = row.scored.best || {};
  const existingRecord = row.existingRecord || {};

  // Distinct normalized values per field, across distinct sources — providerConflict.js's
  // shared predicate, called here with BOTH watches (size + material). Task 2 (gap-closure
  // 58-06) calls the SAME function from Judge Gate with the material fields ONLY — never
  // the size list, which is what keeps RO-2 true there.
  const conflicts = detectConflicts(row.scored, ALL_WATCHED_FIELDS);
  const conflicted = new Set(conflicts.map((c) => c.field));
  const groupedConflicts = groupConflicts(conflicts, ALL_CONFLICT_GROUPS);

  const candidate = {};
  for (const f of ["domain", "industry", "lv_revenue_band", "lv_employee_band",
                   "lv_country_region_normalized"]) {
    if (conflicted.has(f)) continue;                  // materially conflicting -> review
    const b = best[f];
    const v = b && b.normalizedValue;                 // NORMALIZED, not raw
    if (v != null && String(v).trim() !== "") candidate[f] = v;
  }
  // 58-05: native `country`/`city`/`numberofemployees` -- these are free-text/numeric
  // HubSpot-native fields, not enums or bands, so (mirroring ENRICH_MERGE's identical
  // contacts-side city/state/country loop, not the enum-normalizing loop directly above)
  // they read `winners[f]` (the RAW provider value) rather than `best[f].normalizedValue`
  // (which is lowercased for cross-source agreement matching and would write "australia"
  // instead of the portal's existing "Australia" shape). Without THIS loop, a candidate
  // normalizeProviders.js emits and scoreCandidates() scores would be silently dropped
  // here before ever reaching mergeCompanies() -- this loop is the write-map allowlist for
  // these three fields, the one this plan's gap_closure_context did not name.
  const winners = (row.scored && row.scored.winners) || {};
  for (const f of ["country", "city", "numberofemployees"]) {
    // T-58-26 (gap-closure 58-06): this raw-value loop had NO conflict guard at all.
    // Catches `country` conflicting on ITS OWN raw values; when only its sibling
    // lv_country_region_normalized conflicts (11983's exact shape: lusha/apollo agree
    // "Australia" here, only the region enum disagreed), this per-field check stays
    // false and the post-spread GROUP suppression below is what actually withholds it —
    // both members of the country_region group are suppressed together regardless of
    // which one individually conflicted.
    if (conflicted.has(f)) continue;
    const v = winners[f];
    if (v != null && String(v).trim() !== "") candidate[f] = v;
  }
  // 260904-pav: rowConflicted is the harveynorman.com.au franchisor guard, threaded into
  // mergeCompanies' provenance-aware manual_protected correction rather than reinvented —
  // `conflicts` is the SAME array computed 30 lines above. On the waterfall fold ONLY: it
  // is the one call whose field allowlist includes `domain`, and the correction path is
  // the only thing that reads the flag. The native-band, June and research folds cannot
  // carry a domain candidate (their field lists are lv_* / firmographic only), so passing
  // it there would be decoration. mergeCompanies requires `=== false` strictly, so those
  // three folds keep today's behaviour by omission rather than by a permissive default.
  const merged = mergeCompanies(existingRecord, candidate, undefined,
                                { source: "waterfall", confidence: 85,
                                  rowConflicted: conflicts.length > 0 });

  let finalMerge = merged;

  // Phase 41 Task 3 (F1): native firmographic band fold. Fills lv_revenue_band /
  // lv_employee_band from the record's OWN annualrevenue / numberofemployees ONLY when
  // the waterfall candidate above supplied neither -- a waterfall-supplied band always
  // wins. This is a permanent pipeline improvement (fires for any company enrichment
  // the waterfall leaves blank), not a phase-scoped hack.
  const nativeData = {};
  if (candidate.lv_revenue_band === undefined) {
    const band = _bandRevenue(existingRecord.annualrevenue);
    if (band) nativeData.lv_revenue_band = band;
  }
  if (candidate.lv_employee_band === undefined) {
    const band = _bandEmployees(existingRecord.numberofemployees);
    if (band) nativeData.lv_employee_band = band;
  }
  if (Object.keys(nativeData).length > 0) {
    const nativeMerged = mergeCompanies(existingRecord, nativeData, undefined,
      { source: "hubspot_native", confidence: 85 });
    finalMerge = {
      canonicalPatch: { ...finalMerge.canonicalPatch, ...nativeMerged.canonicalPatch },
      provenance: { ...finalMerge.provenance, ...nativeMerged.provenance },
      cacheKeys: { ...finalMerge.cacheKeys, ...nativeMerged.cacheKeys },
      decisions: [...finalMerge.decisions, ...nativeMerged.decisions],
    };
  }

  // Phase 13 (D6) / Phase 41 Task 3: the Claude web-research candidate set, computed
  // HERE (before the June fold below) so June's D-01 precedence filter can see which
  // fields fresh research already answered. researchData is intentionally built even
  // when empty -- the June fold and the disagreement gate both read it unconditionally.
  const rc = row.research_candidate;
  const researchData = {};
  if (rc && rc.matched) {
    // COPY-01: lv_sponsorship_reliant / lv_country_region_normalized appended at the END
    // of this array (never inserted mid-array) so every existing field's key-insertion
    // order stays byte-stable. The tri-state/blank continue guard below already applies
    // uniformly to each new entry.
    for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
                     "lv_is_hardware_vendor", "lv_is_gambling_operator",
                     "lv_sponsorship_reliant", "lv_country_region_normalized"]) {
      const v = rc.data && rc.data[f];
      // tri-state null (TS-2 coercion) / blank -> skip, so mergeCompanies' own _isBlank
      // check has nothing to write; an evidenced false is NOT blank and flows through.
      if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
      researchData[f] = v;
    }
  }

  // Phase 41 Task 1/3 (D-08 pseudo-provider, D-01 precedence): June-2026 validation
  // dataset fold, a THIRD mergeCompanies call. D-01: fresh research wins outright on any
  // field it answered -- June contributes candidates for the REMAINING lv_* keys only.
  const juneRow = JUNE_CANDIDATES[String(existingRecord.hs_object_id)];
  let juneDisagreements = [];
  if (juneRow) {
    const juneData = {};
    for (const f of Object.keys(juneRow)) {
      if (!f.startsWith("lv_")) continue;             // skip _name/_confidence/_evidence/etc.
      if (researchData[f] !== undefined) continue;    // D-01: fresh research wins outright
      juneData[f] = juneRow[f];
    }
    if (Object.keys(juneData).length > 0) {
      const juneMerged = mergeCompanies(existingRecord, juneData, undefined,
        { source: "june_2026", confidence: juneRow._confidence, evidence: juneRow._evidence || {} });
      finalMerge = {
        canonicalPatch: { ...finalMerge.canonicalPatch, ...juneMerged.canonicalPatch },
        provenance: { ...finalMerge.provenance, ...juneMerged.provenance },
        cacheKeys: { ...finalMerge.cacheKeys, ...juneMerged.cacheKeys },
        decisions: [...finalMerge.decisions, ...juneMerged.decisions],
      };
    }

    // D-04: compare June's ORIGINAL mapped value (not the precedence-filtered juneData
    // above -- June may have answered a field research also answered) against research's
    // value, org_type/produces_content only. Both must be present to disagree.
    for (const f of JUNE_RESEARCH_CONFLICT_FIELDS) {
      const juneValue = juneRow[f];
      const researchValue = researchData[f];
      if (juneValue === undefined || researchValue === undefined) continue;
      if (String(juneValue).trim().toLowerCase() === String(researchValue).trim().toLowerCase()) continue;
      juneDisagreements.push({ field: f, juneValue, researchValue });
    }
  }

  // Phase 13 (D6): fold the Claude web-research candidate in as a SECOND mergeCompanies
  // call — mergeCompanies.js itself stays byte-identical. Research fields (lv_org_type,
  // lv_produces_content, lv_content_type, lv_is_hardware_vendor, lv_is_gambling_operator —
  // widened in Phase 14 so the hard-veto INPUT flags finally reach HubSpot, D1/D2;
  // lv_sponsorship_reliant added Phase 18 COPY-01, closing a latent copy-loop gap the
  // field's policy had covered since Phase 15 but this fold never actually reached) never
  // collide with the firmographic candidate's keys above, so a shallow merge of each patch
  // (+ concatenated decisions) is safe. By the time this node runs, the Judge Gate chain
  // upstream has already demoted any UNADJUDICATED vendor-flag `true` to `null`
  // (Pitfall 6) — this fold only ever sees an already-safe value.
  if (Object.keys(researchData).length > 0) {
    // TA-8: confidenceByField carries the judge VERDICT's per-field confidence (only
    // ever set for the ONE field the judge actually adjudicated, Apply Judge Verdict
    // above) — everything else keeps the flat retrieval confidence, exactly as before.
    const researchMerged = mergeCompanies(existingRecord, researchData, undefined,
      { source: "claude_web", confidence: rc.confidence || 80, evidence: rc.evidence_by_field || {},
        confidenceByField: row.judge_confidence_by_field || {} });
    // Phase 15: the two mergeCompanies calls handle mostly DISJOINT field sets
    // (waterfall: domain/industry/revenue_band/employee_band/country; claude_web:
    // org_type/produces_content/content_type/hardware/gambling/sponsorship), so a
    // shallow merge of each provenance object + cacheKeys object is safe for those keys.
    // lv_country_region_normalized (REQ-country-region-policy) is the ONE field both
    // candidate sets can populate — the spread below intentionally lets researchMerged
    // win when claude_web reaches its own promote decision (last-spread-wins), else the
    // waterfall decision stands. Decisions from both calls are concatenated (never
    // deduped), so an audit trail with two entries for this field is expected, not a
    // bug. Cross-source conflict checking on org_type/produces_content now lives in the
    // D-04 disagreement gate below (CONFLICT_WATCH above stays scoped to revenue/employee
    // bands only, per its own header comment).
    finalMerge = {
      canonicalPatch: { ...finalMerge.canonicalPatch, ...researchMerged.canonicalPatch },
      provenance: { ...finalMerge.provenance, ...researchMerged.provenance },
      cacheKeys: { ...finalMerge.cacheKeys, ...researchMerged.cacheKeys },
      decisions: [...finalMerge.decisions, ...researchMerged.decisions],
    };
  }

  // Phase 41 Task 3 (D-04): suppress promotion, delete the cache key, add a synthetic
  // needs_review decision. Runs AFTER every spread above so ordering cannot resurrect a
  // suppressed field -- mirrors the Phase 16.3 stale-timestamp fix's discipline: a held
  // field must never still carry a fresh cache-key stamp.
  if (juneDisagreements.length > 0) {
    const disagreementVerifiedAt = new Date().toISOString();
    for (const d of juneDisagreements) {
      delete finalMerge.canonicalPatch[d.field];
      const cacheKey = JUNE_RESEARCH_CACHE_KEYS[d.field];
      if (cacheKey) delete finalMerge.cacheKeys[cacheKey];
      finalMerge.decisions.push({
        field: d.field,
        current_value: existingRecord[d.field] === undefined ? null : existingRecord[d.field],
        chosen_value: null,
        source_provider: "june_2026",
        decision: "needs_review",
        confidence: juneRow._confidence,
        reason: `June (${d.juneValue}) and fresh research (${d.researchValue}) disagree on ${d.field}.`,
        validation_status: "human_review_required",
        evidence_url: (juneRow._evidence && juneRow._evidence[d.field]) || null,
        verified_at: disagreementVerifiedAt,
      });
    }
  }

  // T-58-26/§21.2 (gap-closure 58-06): material/size-conflict suppression. Runs AFTER
  // every spread above (same discipline as the D-04 juneDisagreements block below it in
  // source order historically, and immediately above here in execution order) so no
  // candidate fold — waterfall, native band, June, or research — can resurrect a
  // conflicted field. SUPPRESS-UNLESS-ADJUDICATED: a group is skipped when the judge lane
  // already adjudicated one of its member fields — row.judge_confidence_by_field carries
  // that field's name (Apply Judge Verdict / TA-8 is the ONLY writer of that map, keyed
  // on the verdict's own chosen_field) — so a legitimate judge-confirmed value, including
  // one that fires the veto, is never deleted by its own suppressor. A size group can
  // never satisfy this check (RO-2 keeps size fields out of judge_confidence_by_field
  // entirely), so a size conflict always suppresses.
  const judgeConfidenceByField = row.judge_confidence_by_field || {};
  const conflictVerifiedAt = new Date().toISOString();
  for (const g of groupedConflicts) {
    const adjudicated = g.fields.some(
      (f) => Object.prototype.hasOwnProperty.call(judgeConfidenceByField, f));
    if (adjudicated) continue;
    for (const f of g.fields) {
      delete finalMerge.canonicalPatch[f];
      // Only lv_org_type/lv_produces_content carry a cache key (COMPANY_CACHE_KEY_FIELDS,
      // mergeCompanies.js) — reuses the same map JUNE_RESEARCH_CACHE_KEYS above defines
      // for exactly those two fields, never a second hand-typed copy.
      const cacheKey = JUNE_RESEARCH_CACHE_KEYS[f];
      if (cacheKey) delete finalMerge.cacheKeys[cacheKey];
    }
    const detail = g.conflicts
      .map((c) => `${c.field}: ` + c.candidates.map((s) => `${s.source}=${s.value}`).join(" vs "))
      .join("; ");
    finalMerge.decisions.push({
      field: g.conflicts.map((c) => c.field).join(", "),
      current_value: g.fields.map((f) => (existingRecord[f] === undefined ? null : existingRecord[f])),
      chosen_value: null,
      source_provider: "provider_conflict",
      decision: "needs_review",
      confidence: null,
      reason: detail,
      validation_status: "human_review_required",
      evidence_url: null,
      verified_at: conflictVerifiedAt,
    });
  }

  return { json: { ...row, merge: finalMerge, conflicts } };
});
"""

ENRICH_DECIDE_CO_LOCAL = r"""// Decide Company Action (dry-run echo) — companies branch.
// NO write nodes: echoes the would-be payload only. Mirrors the contacts Decide Action.
// Phase 15: this is the SINGLE serialization point for the provenance blob — the
// stamper (mergeCompanies.js) returns the parsed provenance object, never a string.
function _sortedForStringify(v) {
  if (Array.isArray(v)) return v.map(_sortedForStringify);
  if (v !== null && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = _sortedForStringify(v[k]);
    return out;
  }
  return v;
}
function _stableStringify(v) { return JSON.stringify(_sortedForStringify(v)); }

return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity_keys || {};
  const scored = row.scored;
  const winners_sample = [];
  if (scored && scored.best) {
    for (const f of Object.keys(scored.best)) {
      const b = scored.best[f];
      winners_sample.push({ field: f, value: b.value, source: b.source, score: b.score });
    }
  }
  return { json: {
    object_type: "companies",
    domain: id.domain,
    company: id.companyName,
    action: row.action,
    gate_reason: row.gate && row.gate.reason,
    gap_flag: row.gap_flag === true,
    conflicts: row.conflicts || [],
    needs_review: (row.conflicts || []).length > 0 || !!(row.research_candidate && row.research_candidate.judge_flags),
    judge_reasons: row.judge_reasons || [],
    judge_verdict: row.judge_verdict || null,
    winners: winners_sample,
    would_patch: row.merge ? {
      canonical: row.merge.canonicalPatch,
      provenance: _stableStringify(row.merge.provenance || {}),
      cache_keys: row.merge.cacheKeys || {},
    } : null,
  }};
});
"""

# CLOUD: compute action + the HubSpot company property patch; IF nodes route to real
# HubSpot company Create/Update (write-safety-gated in Task 6). Companies counterpart of
# ENRICH_DECIDE_CLOUD.
#
# REVIEW-LOOP PRODUCER (review consensus #2, Phase 16 Task 5 — the seam 16-02 Task 4
# depends on). mergeCompanies' canonicalPatch (n8n/code/mergeCompanies.js:209-211,
# VERIFIED) contains ONLY decision==="promote" fields; needs_review decisions live in the
# `decisions` array and are otherwise dropped on the floor. When ANY decision for this row
# is needs_review, this node writes lv_enrichment_needs_review/lv_enrichment_status/
# lv_enrichment_review_reason/lv_enrichment_review_candidate_json (stableStringify'd, the
# HELD candidates a human will approve) — canonicalPatch already excludes those fields'
# values (mergeCompanies never promoted them in the first place), so nothing needs to be
# stripped; a promote-decision field on the SAME row still writes normally.
#
# Approach C (Phase 15 criterion 4): canonicalPatch never carries lv_icp_fit_score/
# lv_icp_tier/lv_anti_icp_flag/lv_recommended_motion — mergeCompanies.js's
# DEFAULT_COMPANY_POLICY has no score_output/veto_output entries for those (they were
# removed in Phase 15), so this node cannot emit them even if it tried.
ENRICH_DECIDE_CO_CLOUD = inline(
    "taxonomy.generated.js", "hubspotEnums.generated.js", "hubspotEnums.js", "mergeCompanies.js",
    "matchProposal.js") + r"""

// --- n8n wrapper (companies): Decide Company Action — CLOUD variant ---
""" + WRITE_REQUEST_JS + r"""
// Phase 70 Plan 03 (D-70-01): this node sits behind a real Merge (the recompute lane's
// direct edge + Merge Company's own output) with a starved-lane sentinel on whichever
// side would otherwise never fire (normal mode vs. recompute mode); drop an identity-
// less sentinel marker before it is treated as a real row.
return $input.all().filter((it) => Object.keys(it.json || {}).length > 0).map((it) => {
  const row = it.json;
  // Phase 36-04 Task 2 (36-CONTEXT.md §7 step 4): a propose envelope with
  // objectType:"company" must not write either — the same shared predicate the
  // contacts branch uses (Task 1), not a second one.
  const returnOnly = isReturnOnly(row.mode);
  const merge = row.merge;
  const decisions = (merge && merge.decisions) || [];
  const needsReview = decisions.filter((d) => d.decision === "needs_review");

  let properties = {};
  if (merge) {
    properties = { ...merge.canonicalPatch, ...(merge.cacheKeys || {}), ...(row.lusha_ids || {}) };
  }

  // 260904-pav: the outgoing provenance blob is built ONCE here and serialized ONCE
  // below, AFTER the create branch has had its chance to add the seed entry — a second
  // serialization site is exactly how a seed gets clobbered.
  //
  // ADDITIVE (this was a destructive replace). merge.provenance only ever carries the
  // fields in THIS run's candidate set, so the old write deleted every other field's
  // entry — including the create seed the correction path keys on, and every field's
  // audit history generally. Existing entries spread first, this run's over them: the
  // same collision order the review lane's buildHumanProvenance uses (n8n/code/
  // reviewDecision.js), so the two additive writers agree on who wins.
  //
  // Fails CLOSED on an unreadable blob: {} means "replace exactly as before", never a
  // throw. No consumer treats the mere PRESENCE of an entry as "this run wrote it" —
  // judge.js's isIndependentPrior reads `source` (a surviving entry can only ever flip a
  // prior from independent to NOT independent, i.e. tighten the guard) and its recency/
  // accuracy reads take the entry's own verified_at/confidence, which are now accurate
  // where they previously fell back to null.
  function _parseOutgoingProvenance(raw) {
    if (raw === null || raw === undefined || raw === "") return {};
    let parsed = raw;
    if (typeof raw === "string") {
      try { parsed = JSON.parse(raw); } catch (e) { return {}; }
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed;
  }
  const runProvenance = (merge && merge.provenance) || {};
  const outgoingProvenance = {
    ..._parseOutgoingProvenance(row.existingRecord && row.existingRecord.lv_enrichment_provenance),
    ...runProvenance,
  };
  // Unchanged condition: only write the property when this run has something to SAY. A
  // recompute row (merge: null, no seed) must not start rewriting the blob it just read.
  let provenanceDirty = Object.keys(runProvenance).length > 0;

  // D-01 (40-03): lv_anti_icp_flag/lv_anti_icp_reason are derived HERE, not supplied as a
  // mergeCompanies() candidate (40-RESEARCH.md Pitfall 4 — the veto derives from three
  // already-merged fields on the same row, only known after mergeCompanies() has run, not
  // a provider-supplied candidate). Direct JS port of src/icp_scoring.py:94-107's hard-veto
  // block — field names, comparison semantics (produces_content is False, not falsy;
  // is_hardware_vendor truthy) and reason-string order must stay byte-identical to the
  // oracle, since tests/test_scoring_parity.py asserts live state against it. Recomputed
  // from current inputs on every run (VETO-02: not a latch by construction).
  //
  // debug: blank-region-fires-non-anz-veto (2026-08-10) — a never-enriched region
  // (undefined/null/"") is an absence of enrichment, not a positive non-ANZ determination.
  // HubSpot property-history live evidence traced 17 real companies (13 AU racing clubs +
  // 1 NZ club) that were PATCHed lv_anti_icp_flag="true"/"Non-ANZ geography" by this exact
  // node (sourceType INTEGRATION) while lv_country_region_normalized had never been set.
  // "unknown" is a third state, distinct from "non_anz" (a KNOWN, different value, e.g.
  // "US") — mirrors src/icp_scoring.py's region_raw/region_key split.
  function _regionKey(v) {
    if (v === "AU" || v === "NZ" || v === "ANZ") return v;
    if (v === undefined || v === null || v === "") return "unknown";
    return "non_anz";
  }
  function _boolish(v) {
    if (typeof v === "boolean") return v;
    if (v === "true") return true;
    if (v === "false") return false;
    return null;
  }
  const existing = row.existingRecord || {};
  const region = _regionKey(properties.lv_country_region_normalized ?? existing.lv_country_region_normalized);
  const producesContent = _boolish(properties.lv_produces_content ?? existing.lv_produces_content);
  const isHardwareVendor = _boolish(properties.lv_is_hardware_vendor ?? existing.lv_is_hardware_vendor);
  // 47.5-C (47.5-C-DECISION.md, or-retroactive): the hardware veto fires on EITHER
  // trigger. lv_is_hardware_vendor is suppressed by design — the research contract
  // answers null without a cited source, a true forces judge escalation, the D5
  // fail-safe demotes it back, and merge then wants 85 confidence — so it sat on 1 of
  // 66 live companies while lv_org_type, which the pipeline reliably lands, said
  // hardware_vendor for 2. OR rather than replacing the boolean: purely additive (no
  // record loses a veto) and the boolean stays alive as a manual override. Same
  // `?? existing` fallback as the three signals above, so a merge-free recompute row
  // derives it from existingRecord like everything else (lv_org_type is already in
  // ENRICH_COMPANY_SEARCH_PROPERTIES_CSV). This is a STRING predicate, not an
  // org-type-keyed numeric table — tests/test_n8n_org_type_absence.py stays green.
  const orgType = properties.lv_org_type ?? existing.lv_org_type;

  const vetoReasons = [];
  if (region === "non_anz") vetoReasons.push("Non-ANZ geography");
  if (producesContent === false) vetoReasons.push("No broadcast or streaming content");
  if (isHardwareVendor === true || orgType === "hardware_vendor") vetoReasons.push("Hardware/AV/LED vendor, not sports-media buyer");

  // Phase 50 Plan 06 (D-20): the veto is derived ONCE into flagIsSet and BOTH properties
  // are assigned from it, adjacent, in this same block — the structural guarantee that a
  // future edit to the predicate changes both serializations together. lv_anti_icp_flag_num
  // is the numeric mirror lv_icp_tier_derived's calculationFormula veto guard reads
  // (calculation_equation reads only numeric properties — the boolean is unreadable
  // there). D-04 / P4: string literals, never bare JS booleans — HubSpot EQ filters
  // compare strings (the 36-07 precedent for lv_enrichment_requested). The BUG-27 loop
  // below only joins arrays, so an unstringified boolean here would ship straight to the
  // PATCH body.
  const flagIsSet = vetoReasons.length > 0;
  properties.lv_anti_icp_flag = flagIsSet ? "true" : "false";
  properties.lv_anti_icp_flag_num = flagIsSet ? "1" : "0";
  properties.lv_anti_icp_reason = flagIsSet ? vetoReasons.join("; ") : "";

  if (needsReview.length > 0) {
    // D-07 (43-01, PIPE-01, row 3): string literal, never a bare JS boolean — same class
    // as the lv_anti_icp_flag fix two lines above; the BUG-27 loop below only joins
    // arrays, so this would otherwise ship unstringified straight to the PATCH body.
    properties.lv_enrichment_needs_review = "true";
    properties.lv_enrichment_status = "needs_review";
    properties.lv_enrichment_review_reason =
      needsReview.map((d) => `${d.field}: ${d.reason}`).join("; ").slice(0, 60000);
    properties.lv_enrichment_review_candidate_json = stableStringify(needsReview).slice(0, 60000);
  } else if (merge) {
    properties.lv_enrichment_status = "complete";
  }

  const hs_object_id = (row.existingRecord && row.existingRecord.hs_object_id) || null;
  const id = row.identity_keys || {};
  const domain = id.domain;
  if (row.action === "create" && !returnOnly) {
    // BUG 19 (confirmed live on a throwaway, 2026-07-29): canonicalPatch never carries
    // domain (manual_protected — an UPDATE rule) and name is in no policy at all, so an
    // unseeded create wrote name=None/domain=None and the domain-EQ search that had just
    // decided "create" returned total=0 against it — unbounded re-creation. Seed on the
    // create branch ONLY; on enrich this would be the exact clobber the policy prevents.
    // Also gated on !returnOnly (36-CONTEXT.md §6): a propose response's `properties`
    // carries only what the waterfall discovered, never the caller's own identity.
    if (id.domain) properties.domain = id.domain;
    if (id.companyName) properties.name = id.companyName;
    // 260904-pav: stamp the seeded domain's provenance, or nothing downstream can ever
    // tell this system-written value from a human-curated one — and manual_protected
    // refuses both. A DISTINCT source (`create_seed`) and a status of `request_echo`
    // because the seed is an identity echo of the caller's own request, not a researched
    // or provider-supplied value; confidence 0 is the honest reading of an unverified
    // echo. `name` is deliberately not stamped: no policy class protects it, so there is
    // nothing for a provenance entry there to unlock.
    if (id.domain) {
      outgoingProvenance.domain = {
        source: "create_seed", confidence: 0, verified_at: new Date().toISOString(),
        validation_status: "request_echo", value: id.domain,
      };
      provenanceDirty = true;
    }
  }
  if (provenanceDirty) {
    properties.lv_enrichment_provenance = stableStringify(outgoingProvenance).slice(0, 60000);
  }
  let action = row.action;
  if (returnOnly) {
    // Phase 36-04 Task 2 (36-CONTEXT.md §7 step 4): set BEFORE _writeSafetyAllows,
    // unconditionally on the mode predicate alone — no ALLOW_* constant is read on this
    // branch. A propose envelope naming objectType:"company" must not write either.
    // No medium-tier guard here: the companies branch's match verdict is a fixed
    // non-medium company-lane summary (260904-5a8's "company" call-site literal, always
    // tier "unknown") — there is still nothing to demote.
    action = "proposed";
  }
  // Phase 70 Plan 05 Task 2 (D-70-13): the write-permission predicate USED to run here,
  // inline, turning a create/enrich into "write_blocked" before either routing IF saw it.
  // It now has exactly one home per lane — the spliced "<write node> Write Gate" — so this
  // node decides WHAT the row is, never WHETHER it may be written. The row keeps its real
  // action through "IF Create"/"IF Enrich" and is refused (or not) at the gate, which
  // EMITS the refusal as a row rather than dropping it (D-70-14).

  // BUG 27 (live 400 on execution 328): HubSpot v3 PATCH rejects JSON arrays —
  // multi-checkbox values (lv_content_type) must be semicolon-joined strings.
  // D-07 (43-01, PIPE-01, row 4): a second branch coerces any boolean-typed value to its
  // quoted string form — the single choke point every promoted candidate passes through
  // (mergeCompanies.js's canonicalPatch carries raw candidate types straight through), so
  // this covers lv_produces_content/lv_sponsorship_reliant/lv_is_hardware_vendor/
  // lv_is_gambling_operator, and any future boolean property, with no per-field list.
  for (const k of Object.keys(properties)) {
    if (Array.isArray(properties[k])) properties[k] = properties[k].join(";");
    else if (typeof properties[k] === "boolean") properties[k] = properties[k] ? "true" : "false";
  }

  return { json: {
    action,
    object_type: "companies",
    hs_object_id,
    gap_flag: row.gap_flag === true,
    needs_review: needsReview.length > 0,
    row_id: row.row_id ?? null,
    mode: row.mode ?? null,
    // 260904-5a8: "company" is a CALL-SITE LITERAL, never `row.lane` — this branch
    // stamps no lane on any row (C1 in the quick task's premise_corrections), so passing
    // `row.lane` here would always resolve `undefined` and hit summarizeMatch's generic
    // "none" fallthrough, which speaks contacts vocabulary about a row that was never
    // searched by email/object id/name+company. See matchProposal.js's "company" arm.
    match: row.match ?? summarizeMatch({ lane: "company" }),
    properties,
    // Phase 70 Plan 03 Task 2 (D-70-07, Rule 1 fix): this node's explicit return shape
    // never carried `row.gate.reason` forward — CLAUDE.md §13.0's own comment on
    // ENRICH_CO_GATE ("the reason string is what makes the outcome readable in the
    // response") never actually reached the response through THIS node, for either a
    // recompute_refused row (this lane) or a plain skip (Build Response reads
    // `row.gate.gate.reason` directly for that OTHER lane, which bypasses this node
    // entirely — see companyRecomputeLaneFlow.test.mjs). Additive: a row's own
    // `row.gate` (set by "Company Gate", still present on the INPUT here) is
    // preserved onto the OUTPUT as a top-level `reason`, so Build Response's own
    // `reason: row.reason ?? (row.gate && row.gate.reason) ?? null` hoist has
    // something to read for this lane too, instead of always resolving null.
    reason: (row.gate && row.gate.reason) || null,
    // D-70-12: the canonical shape the spliced "HubSpot Company Create/Update Write Gate"
    // reads. Companies carry no email identity — the allowlist matches on id or domain.
    write_request: _buildWriteRequest(action, hs_object_id, domain || null, null),
  }};
});
"""

# Phase 61 Plan 06 Task 2 (REVIEW-C17): the created company's id capture point.
# "HubSpot Company Create"'s HTTP response carries the minted id, but the builder
# wires that node STRAIGHT into the generic "Build Response" — nothing between them
# preserves which run dependency the created id answers, so the id is lane-internal
# only, never client-visible (written_records.py:38-48's `created_id_unknown`, the
# post-write companies confirmation node having been scoped OUT in 59-01). This is the
# ONE named adapter that closes that: it joins the create RESPONSE back to its planned
# dependency BY VALUE — the same discipline "Build Association Request" (ingest lane)
# already uses, for the same reason: index alignment is gone downstream of the write
# IFs. `company_dependency_id` is the domain "Decide Company Action" seeded onto the
# create's own properties (BUG 19); HubSpot's create response echoes the properties it
# was given back, so the response's OWN `properties.domain` is the same value the
# planning row named — no second search, no correlation id invented. Wired straight
# into "Build Response", whose `...row` projection (Phase 61 Plan 04 Task 1) carries
# both fields to the client for free.
#
# Phase 70 Plan 04 (D-70-04): fed by "HubSpot Company Create Carry Merge", which
# re-attaches the pre-hop row (the same single "Decide Company Action" item that
# requested this create — the create branch never batches, one planning row per create
# request) onto the HTTP response. The old `nodeAll('Decide Company Action')` cross-row
# `.find()` by domain is retired: the planning row IS this item, so its own fields are
# already on `merged` — no by-name lookup, no second search.
ADAPT_COMPANY_CREATE = r"""// Adapt Company Create — Phase 61 Plan 06 Task 2 (REVIEW-C17).
return $input.all().map((it) => {
  const merged = it.json || {};
  const companyId = merged.id != null ? String(merged.id) : null;
  const domain = (merged.properties && merged.properties.domain) || null;
  const companyDependencyId = domain ||
    (merged.properties && merged.properties.name) || null;
  return { json: {
    ...merged,
    company_dependency_id: companyDependencyId,
    company_id: companyId,
  }};
});
"""


def _live_http(name, x, y, method, url, headers, json_body=None, timeout=20000):
    """HTTP Request node whose auth/secrets come from $env expressions in headers
    (no credential store), for headless `n8n execute` with docker exec -e.
    NOTE: no retryOnFail here or on any call site — RESEARCH Pitfall 3: retryOnFail is
    silently ignored whenever onError is a "Continue" option, so a failed call is a SKIP,
    not a retry (Task 4 proves this for the research node offline)."""
    params = {"method": method, "url": url, "options": {"timeout": timeout}}
    if json_body is not None:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": json_body})
    if headers:
        params.update({"sendHeaders": True, "headerParameters": {"parameters": headers}})
    return {"parameters": params, "id": nid("h"), "name": name,
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": [x, y], "onError": "continueRegularOutput"}


def _if_bool_node(name, field, x, y):
    """IF node testing a boolean field for `true` (Phase 13: IF Research Needed)."""
    return {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ $json." + field + " }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "equals"},
            }],
        }},
        "id": nid("if"), "name": name,
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }


def _if_bool_expr_node(name, expr, x, y):
    """IF node testing an arbitrary boolean n8n EXPRESSION (not just a bare `$json.<field>`
    lookup) for `true`. Phase 70 Plan 04 Task 2 (D-70-03): the per-provider `IF <provider>
    Enabled` gates now read `provider_enabled.<name>` off bare `$json` — Task 1's carry
    merges (splice_carry_merge_after) re-attach the row after every provider HTTP hop, so
    `provider_enabled` (stamped once, on the row, by "Parse HubSpot Event") survives to
    every later gate without a by-name lookup."""
    return {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ " + expr + " }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "equals"},
            }],
        }},
        "id": nid("if"), "name": name,
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }


# ---- Phase 16.1: shared provider gate+bypass-convergence helper (CONTEXT Locked ----
# ---- Decision 8 — the reuse seam both the contacts and companies branches call) ----
def _provider_gate_bypass_chain(providers, exit_node, x, y):
    """Emits an ordered chain of `IF <provider> Enabled` gates with bypass-convergence —
    the SAME topology as the existing, offline-tested
    `IF ZoomInfo Needs Mint -> [Mint->Cache]/[bypass] -> ZoomInfo Enrich` precedent
    (:2469-2477 pre-16.1), generalized to N providers and called IDENTICALLY by both
    branches (not two hand-rolled copies).

    `providers` is an ordered list of dicts, one per provider:
      {gate_name, enabled_expr, true_entry, true_exit (optional, default true_entry)}
    - gate_name:   the `IF <provider> Enabled` node's name.
    - enabled_expr: the n8n boolean expression the gate tests (by-node-name read of
      provider_enabled — see _if_bool_expr_node).
    - true_entry:  the node the gate's TRUE lane feeds — a provider HTTP node, or a
      subgraph's entry node (e.g. "ZoomInfo Token Gate").
    - true_exit:   the node whose output REJOINS the chain — defaults to true_entry for a
      simple single-node provider; pass the subgraph's own exit node (e.g.
      "ZoomInfo Enrich") for a multi-node provider so the REJOIN edge starts there, not at
      the entry.

    Each gate's true+false lanes rejoin at the SAME next stage (the next provider's gate,
    or `exit_node` for the last), so the convergence node (e.g. Normalize + Score) always
    has an inbound edge regardless of which providers are enabled — exactly one fires per
    row, and the empty-enabled-set path (every gate bypassed) still reaches exit_node.

    Returns (nodes, conns, first_gate_name). `conns` covers gate1..gateN + the rejoin
    edges; it does NOT include the caller's OWN entry -> first_gate_name edge (entry-node
    shape varies — an IF true-lane for contacts, a plain Code node for companies — so the
    caller wires that single edge itself)."""
    nodes = []
    conns = {}
    n = len(providers)
    cx = x
    first_gate_name = providers[0]["gate_name"]
    for idx, spec in enumerate(providers):
        gate_name = spec["gate_name"]
        nodes.append(_if_bool_expr_node(gate_name, spec["enabled_expr"], cx, y))
        cx += 220
        true_exit = spec.get("true_exit", spec["true_entry"])
        next_stage = providers[idx + 1]["gate_name"] if idx + 1 < n else exit_node
        conns[gate_name] = {"main": [
            [{"node": spec["true_entry"], "type": "main", "index": 0}],  # true -> provider
            [{"node": next_stage, "type": "main", "index": 0}],          # false -> bypass
        ]}
        conns[true_exit] = {"main": [[{"node": next_stage, "type": "main", "index": 0}]]}
    return nodes, conns, first_gate_name


def _provider_enabled_expr(name):
    """Phase 70 Plan 04 Task 2 (D-70-03): bare $json — every provider HTTP hop's carry
    merge (Task 1) re-attaches the row, so `provider_enabled` (stamped once by "Parse
    HubSpot Event") rides every row to every later gate, never a by-name lookup."""
    return f"$json.provider_enabled.{name}"


def build_enrichment_local_live():
    nodes = []
    y = 300
    x = 240
    nodes.append({"parameters": {}, "id": nid("t"), "name": "Manual Trigger",
                  "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [x, y]})
    x += 230
    nodes.append(code_node("Emit Live Identities", ENRICH_EMIT_LIVE, x, y))
    x += 230
    nodes.append(code_node("Build Identity", ENRICH_BUILD_IDENTITY, x, y))
    x += 230
    nodes.append(_live_http(
        "HubSpot Search", x, y, "POST",
        "https://api.hubapi.com/crm/v3/objects/contacts/search",
        [{"name": "Authorization", "value": "=Bearer " + _env_secret_expr("HUBSPOT_PRIVATE_APP_TOKEN")},
         {"name": "Content-Type", "value": "application/json"}],
        json_body=HS_SEARCH_BODY_EXPR))
    x += 230
    nodes.append(code_node("Adapt Search", ENRICH_ADAPT_SEARCH, x, y))
    x += 230
    nodes.append(code_node("Enrichment Gate", ENRICH_GATE, x, y))
    x += 230
    nodes.append(code_node("Build Requests", ENRICH_BUILD_REQUESTS, x, y))
    x += 230
    nodes.append(_live_http(
        "Lusha Enrich", x, y, "POST",
        # Plan 04 Task 2b: the body's own shape says which endpoint to call — an `ids`
        # key means lushaContactEnrichByIdBody() built the stored-id-reuse body (the
        # CONFIRMED-FREE path, §8.1), otherwise it's the unchanged search-and-enrich body.
        "={{ $json.lusha_body.ids ? "
        "'https://api.lusha.com/v3/contacts/enrich' : "
        "'https://api.lusha.com/v3/contacts/search-and-enrich' }}",
        [{"name": "api_key", "value": "=" + _env_secret_expr("LUSHA_API_KEY")},
         {"name": "Content-Type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.lusha_body) }}"))
    x += 230
    nodes.append(code_node("Wrap Lusha Result", _wrap_provider_result_js("lusha_result"), x, y - 40))
    x += 230
    nodes.append(_live_http(
        "Apollo Match", x, y, "POST", "https://api.apollo.io/v1/people/match",
        [{"name": "X-Api-Key", "value": "=" + _env_secret_expr("APOLLO_API_KEY")},
         {"name": "Content-Type", "value": "application/json"},
         {"name": "Cache-Control", "value": "no-cache"}],
        json_body="={{ JSON.stringify($json.apollo_body) }}"))
    x += 230
    nodes.append(code_node("Wrap Apollo Result", _wrap_provider_result_js("apollo_result"), x, y - 40))
    x += 230
    nodes.append(code_node("ZoomInfo Enrich", ENRICH_ZOOMINFO_CACHED, x, y))
    x += 230
    nodes.append(code_node("Normalize + Score", ENRICH_NORMALIZE_SCORE_CLOUD, x, y))

    # Phase 16.2 (SC-1/SC-2): the contacts research->judge mirror, mirroring the companies
    # Research Trigger Gate -> ... -> Merge Company chain below via the SAME Plan-01
    # parameterized factories, called with target=CONTACTS_TARGET. True lane -> Build
    # Contact Research Request -> Contact Web Research (HTTP) -> Validate Contact
    # Research -> Contact Judge Gate -> IF Contact Needs Judge -> ... -> Apply Contact
    # Judge Verdict -> Merge Winners. False lanes fan straight into Merge Winners.
    x += 230
    nodes.append(code_node(
        "Contact Research Trigger Gate", _enrich_research_gate_js(cloud=False, target=CONTACTS_TARGET), x, y))
    x += 230
    nodes.append(_if_bool_node("IF Contact Research Needed", "research_needed", x, y))
    x += 230
    nodes.append(code_node(
        "Build Contact Research Request",
        _enrich_build_research_request_js(cloud=False, target=CONTACTS_TARGET), x, y - 100))
    x += 230
    nodes.append(_live_http(
        "Contact Web Research", x, y - 100, "POST",
        "https://api.anthropic.com/v1/messages",
        [{"name": "x-api-key", "value": "=" + _env_secret_expr("ANTHROPIC_API_KEY")},
         {"name": "anthropic-version", "value": "2023-06-01"},
         {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.research_request_body) }}",
        timeout=60000))
    x += 230
    nodes.append(code_node(
        "Validate Contact Research", _enrich_validate_research_js(target=CONTACTS_TARGET), x, y - 100))
    x += 230
    nodes.append(code_node(
        "Contact Judge Gate", _enrich_judge_gate_js(cloud=False, target=CONTACTS_TARGET), x, y - 100))
    x += 230
    nodes.append(_if_bool_node("IF Contact Needs Judge", "needs_judge", x, y - 100))
    x += 230
    nodes.append(code_node(
        "Build Contact Judge Request",
        _enrich_build_judge_request_js(cloud=False, target=CONTACTS_TARGET), x, y - 200))
    x += 230
    nodes.append(_live_http(
        "Contact Judge Call", x, y - 200, "POST",
        "https://api.anthropic.com/v1/messages",
        [{"name": "x-api-key", "value": "=" + _env_secret_expr("ANTHROPIC_API_KEY")},
         {"name": "anthropic-version", "value": "2023-06-01"},
         {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.judge_request_body) }}",
        timeout=60000))
    x += 230
    nodes.append(code_node(
        "Apply Contact Judge Verdict", _enrich_apply_judge_verdict_js(target=CONTACTS_TARGET), x, y - 200))

    x += 230
    nodes.append(code_node("Merge Winners", ENRICH_MERGE, x, y))
    x += 230
    nodes.append(code_node("Decide Action", ENRICH_DECIDE_LOCAL, x, y))

    # order's chain() ends at "Normalize + Score" (no outgoing edge yet) — the contact
    # chain conns below wire Normalize + Score -> Contact Research Trigger Gate -> ... ->
    # Merge Winners -> Decide Action explicitly, mirroring co_order's own truncation.
    order = ["Manual Trigger", "Emit Live Identities", "Build Identity", "HubSpot Search",
             "Adapt Search", "Enrichment Gate", "Build Requests", "Lusha Enrich", "Apollo Match",
             "ZoomInfo Enrich", "Normalize + Score"]

    # --- COMPANIES branch: sibling off the same Manual Trigger, own row (y+380) ---
    cy = y + 380
    cx = 240 + 230
    nodes.append(code_node("Emit Company Targets", ENRICH_EMIT_COMPANIES, cx, cy))
    cx += 230
    nodes.append(code_node("Build Company Identity", ENRICH_BUILD_CO_IDENTITY, cx, cy))
    cx += 230
    nodes.append(_live_http(
        "HubSpot Company Search", cx, cy, "POST",
        "https://api.hubapi.com/crm/v3/objects/companies/search",
        [{"name": "Authorization", "value": "=Bearer " + _env_secret_expr("HUBSPOT_PRIVATE_APP_TOKEN")},
         {"name": "Content-Type", "value": "application/json"}],
        json_body=HS_CO_SEARCH_BODY_EXPR))
    cx += 230
    nodes.append(code_node("Adapt Company Search", ENRICH_ADAPT_CO_SEARCH, cx, cy))
    cx += 230
    nodes.append(code_node("Company Gate", ENRICH_CO_GATE, cx, cy))
    cx += 230
    nodes.append(code_node("Build Company Requests", ENRICH_BUILD_CO_REQUESTS, cx, cy))
    cx += 230
    nodes.append(_live_http(
        "Lusha Company", cx, cy, "POST",
        "https://api.lusha.com/v3/companies/search-and-enrich",
        [{"name": "api_key", "value": "=" + _env_secret_expr("LUSHA_API_KEY")},
         {"name": "Content-Type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.lusha_company_body) }}"))
    cx += 230
    nodes.append(code_node("Wrap Lusha Company Result", _wrap_provider_result_js("lusha_result"), cx, cy - 40))
    cx += 230
    nodes.append(_live_http(
        "Apollo Org", cx, cy, "POST",
        "={{ $json.apollo_org_url }}",
        [{"name": "X-Api-Key", "value": "=" + _env_secret_expr("APOLLO_API_KEY")},
         {"name": "Content-Type", "value": "application/json"},
         {"name": "Cache-Control", "value": "no-cache"}]))
    cx += 230
    nodes.append(code_node("Wrap Apollo Org Result", _wrap_provider_result_js("apollo_result"), cx, cy - 40))
    cx += 230
    nodes.append(code_node("ZoomInfo Company", ENRICH_ZOOMINFO_CO_CACHED, cx, cy))
    cx += 230
    nodes.append(code_node("Normalize + Score Company", ENRICH_NORMALIZE_SCORE_CO, cx, cy))

    # Phase 13 (D5): Research Trigger Gate -> IF Research Needed. True lane -> Build
    # Research Request -> Claude Web Research (HTTP) -> Validate Research Output ->
    # Merge Company. False lane -> straight to Merge Company (fan-in, both lanes carry the
    # full pass-through row; only the true lane additionally attaches research_candidate).
    cx += 230
    nodes.append(code_node("Research Trigger Gate", _enrich_research_gate_js(cloud=False), cx, cy))
    cx += 230
    nodes.append(_if_bool_node("IF Research Needed", "research_needed", cx, cy))
    cx += 230
    nodes.append(code_node("Build Research Request", _enrich_build_research_request_js(cloud=False), cx, cy - 100))
    cx += 230
    nodes.append(_live_http(
        "Claude Web Research", cx, cy - 100, "POST",
        "https://api.anthropic.com/v1/messages",
        [{"name": "x-api-key", "value": "=" + _env_secret_expr("ANTHROPIC_API_KEY")},
         {"name": "anthropic-version", "value": "2023-06-01"},
         {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.research_request_body) }}",
        timeout=60000))
    cx += 230
    nodes.append(code_node("Validate Research Output", ENRICH_VALIDATE_RESEARCH, cx, cy - 100))

    # Phase 14 (D1): the judge chain sits BEFORE Merge Company, on the research-true lane.
    # Validate Research Output's existing connection to Merge Company moves to Judge Gate
    # (research_conns below). The IF Research Needed FALSE lane keeps going straight to
    # Merge Company untouched — an unresearched company never reaches the judge (RO-1 by
    # topology). Judge Gate / IF Needs Judge sit on the cy-100 research lane; the three
    # judge-call nodes sit on cy-200 — positions are cosmetic.
    cx += 230
    nodes.append(code_node("Judge Gate", _enrich_judge_gate_js(cloud=False), cx, cy - 100))
    cx += 230
    nodes.append(_if_bool_node("IF Needs Judge", "needs_judge", cx, cy - 100))
    cx += 230
    nodes.append(code_node("Build Judge Request", _enrich_build_judge_request_js(cloud=False), cx, cy - 200))
    cx += 230
    nodes.append(_live_http(
        "Judge Call", cx, cy - 200, "POST",
        "https://api.anthropic.com/v1/messages",
        [{"name": "x-api-key", "value": "=" + _env_secret_expr("ANTHROPIC_API_KEY")},
         {"name": "anthropic-version", "value": "2023-06-01"},
         {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.judge_request_body) }}",
        timeout=60000))
    cx += 230
    nodes.append(code_node("Apply Judge Verdict", ENRICH_APPLY_JUDGE_VERDICT, cx, cy - 200))

    cx += 230
    nodes.append(code_node("Merge Company", ENRICH_MERGE_CO, cx, cy))
    cx += 230
    nodes.append(code_node("Decide Company Action", ENRICH_DECIDE_CO_LOCAL, cx, cy))

    co_order = ["Manual Trigger", "Emit Company Targets", "Build Company Identity",
                "HubSpot Company Search", "Adapt Company Search", "Company Gate",
                "Build Company Requests", "Lusha Company", "Apollo Org", "ZoomInfo Company",
                "Normalize + Score Company", "Research Trigger Gate"]

    nodes.append({
        "parameters": {"content": (
            "## LV Enrichment — LOCAL LIVE (headless, real providers)\n"
            "Real Lusha (GET v2) + Apollo (people/match, reveal) + ZoomInfo (cached GTM "
            "token) + HubSpot SEARCH — all keyed off `$env` (pass via `docker exec -e`). "
            "Run: `scripts/n8n_enrichment_live_replica.sh`.\n\n"
            "**Read-only:** live provider calls + HubSpot search only. NO write nodes — "
            "Decide Action echoes the would-be payload. Real ICP prospects; none skip.\n\n"
            "**Two sibling branches off one trigger** (companies is NOT nested under "
            "contacts): the ICP fields are per-DOMAIN and expensive, so nesting would "
            "re-pay for every contact at the same company. Companies dedupes by domain; "
            "contacts join back on domain. Company branch = Lusha `/v2/company` + Apollo "
            "`/v1/organizations/enrich` + ZoomInfo GTM `/companies/enrich` — all three "
            "confirmed 200 live (2026-07-20)."
        ), "height": 380, "width": 460},
        "id": nid("s"), "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [240, 540]})

    # Phase 13 (D5): explicit connections for the IF node's two outputs + the fan-in onto
    # Merge Company. co_order's chain() ends at "Research Trigger Gate" (no outgoing edge
    # yet), so none of these keys collide with fan(chain(order), chain(co_order))'s output.
    research_conns = {
        "Research Trigger Gate": {"main": [[{"node": "IF Research Needed", "type": "main", "index": 0}]]},
        "IF Research Needed": {"main": [
            [{"node": "Build Research Request", "type": "main", "index": 0}],  # true: needs research
            [{"node": "Merge Company", "type": "main", "index": 0}],           # false: fan straight in
        ]},
        "Build Research Request": {"main": [[{"node": "Claude Web Research", "type": "main", "index": 0}]]},
        "Claude Web Research": {"main": [[{"node": "Validate Research Output", "type": "main", "index": 0}]]},
        # Phase 14 (D1): Validate Research Output's connection moves to Judge Gate — the
        # judge chain runs BEFORE Merge Company, on the research-true lane only.
        "Validate Research Output": {"main": [[{"node": "Judge Gate", "type": "main", "index": 0}]]},
        "Judge Gate": {"main": [[{"node": "IF Needs Judge", "type": "main", "index": 0}]]},
        "IF Needs Judge": {"main": [
            [{"node": "Build Judge Request", "type": "main", "index": 0}],  # true: adjudicate
            [{"node": "Merge Company", "type": "main", "index": 0}],        # false: fan straight in
        ]},
        "Build Judge Request": {"main": [[{"node": "Judge Call", "type": "main", "index": 0}]]},
        "Judge Call": {"main": [[{"node": "Apply Judge Verdict", "type": "main", "index": 0}]]},
        "Apply Judge Verdict": {"main": [[{"node": "Merge Company", "type": "main", "index": 0}]]},
        "Merge Company": {"main": [[{"node": "Decide Company Action", "type": "main", "index": 0}]]},
    }

    # Phase 16.2 (SC-1): the contacts mirror of research_conns above — order's chain()
    # ends at "Normalize + Score" (no outgoing edge yet), so none of these keys collide.
    contact_conns = {
        "Normalize + Score": {"main": [[{"node": "Contact Research Trigger Gate", "type": "main", "index": 0}]]},
        "Contact Research Trigger Gate": {
            "main": [[{"node": "IF Contact Research Needed", "type": "main", "index": 0}]]},
        "IF Contact Research Needed": {"main": [
            [{"node": "Build Contact Research Request", "type": "main", "index": 0}],  # true
            [{"node": "Merge Winners", "type": "main", "index": 0}],                   # false: fan straight in
        ]},
        "Build Contact Research Request": {
            "main": [[{"node": "Contact Web Research", "type": "main", "index": 0}]]},
        "Contact Web Research": {"main": [[{"node": "Validate Contact Research", "type": "main", "index": 0}]]},
        "Validate Contact Research": {"main": [[{"node": "Contact Judge Gate", "type": "main", "index": 0}]]},
        "Contact Judge Gate": {"main": [[{"node": "IF Contact Needs Judge", "type": "main", "index": 0}]]},
        "IF Contact Needs Judge": {"main": [
            [{"node": "Build Contact Judge Request", "type": "main", "index": 0}],  # true
            [{"node": "Merge Winners", "type": "main", "index": 0}],                # false: fan straight in
        ]},
        "Build Contact Judge Request": {"main": [[{"node": "Contact Judge Call", "type": "main", "index": 0}]]},
        "Contact Judge Call": {"main": [[{"node": "Apply Contact Judge Verdict", "type": "main", "index": 0}]]},
        "Apply Contact Judge Verdict": {"main": [[{"node": "Merge Winners", "type": "main", "index": 0}]]},
        "Merge Winners": {"main": [[{"node": "Decide Action", "type": "main", "index": 0}]]},
    }

    conns = {**fan(chain(order), chain(co_order)), **research_conns, **contact_conns}

    # Phase 70 Plan 04 (D-70-04): the SAME carry-merge treatment build_enrichment_cloud()
    # applies, mirrored here — a straight-line chain (no lane branching, no IF gates), so
    # every carry_source is simply each hop's own direct predecessor in `order`/`co_order`.
    splice_carry_merge_after(nodes, conns, "HubSpot Search", "Build Identity",
                              merge_name="HubSpot Search Carry Merge")
    _lusha_old_target = conns["Lusha Enrich"]["main"][0][0]["node"]
    conns["Lusha Enrich"] = {"main": [[{"node": "Wrap Lusha Result", "type": "main", "index": 0}]]}
    conns["Wrap Lusha Result"] = {"main": [[{"node": _lusha_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Lusha Result", "Build Requests",
                              merge_name="Lusha Result Carry Merge")
    _apollo_old_target = conns["Apollo Match"]["main"][0][0]["node"]
    conns["Apollo Match"] = {"main": [[{"node": "Wrap Apollo Result", "type": "main", "index": 0}]]}
    conns["Wrap Apollo Result"] = {"main": [[{"node": _apollo_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Apollo Result", "Lusha Result Carry Merge",
                              merge_name="Apollo Result Carry Merge")

    splice_carry_merge_after(nodes, conns, "HubSpot Company Search", "Build Company Identity",
                              merge_name="HubSpot Company Search Carry Merge")
    _lusha_co_old_target = conns["Lusha Company"]["main"][0][0]["node"]
    conns["Lusha Company"] = {"main": [[{"node": "Wrap Lusha Company Result", "type": "main", "index": 0}]]}
    conns["Wrap Lusha Company Result"] = {"main": [[{"node": _lusha_co_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Lusha Company Result", "Build Company Requests",
                              merge_name="Lusha Company Result Carry Merge")
    _apollo_org_old_target = conns["Apollo Org"]["main"][0][0]["node"]
    conns["Apollo Org"] = {"main": [[{"node": "Wrap Apollo Org Result", "type": "main", "index": 0}]]}
    conns["Wrap Apollo Org Result"] = {"main": [[{"node": _apollo_org_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Apollo Org Result", "Lusha Company Result Carry Merge",
                              merge_name="Apollo Org Result Carry Merge")

    splice_carry_merge_after(nodes, conns, "Claude Web Research", "Build Research Request",
                              merge_name="Research Carry Merge")
    splice_carry_merge_after(nodes, conns, "Judge Call", "Build Judge Request",
                              merge_name="Judge Carry Merge")
    splice_carry_merge_after(nodes, conns, "Contact Web Research", "Build Contact Research Request",
                              merge_name="Contact Research Carry Merge")
    splice_carry_merge_after(nodes, conns, "Contact Judge Call", "Build Contact Judge Request",
                              merge_name="Contact Judge Carry Merge")

    # Phase 70 Plan 03 (D-70-01): the SAME "Merge Winners"/"Merge Company" fan_in
    # convergences build_enrichment_cloud() fixes, mirrored here — this standalone
    # local-LIVE harness ("Manual Trigger" + fixed "Emit Live Identities"/"Emit Company
    # Targets" test data, no webhook/object-type routing/recompute) shares the exact
    # same 3-input shape and the exact same "no research needed"/"no judge needed"
    # starved-lane risk. Deliberately NOT refactored to share build_enrichment_cloud()'s
    # own sentinel-adding calls: those are already tested and pinned by name; a shared
    # helper would need to be introduced there FIRST, which is more churn than this
    # workflow's much smaller scope (2 merges, no pre-fork/recompute sentinels needed —
    # there is no webhook, no object-type router, no recompute lane here) justifies.
    llx, lly = 40, 2200
    winners_merge = splice_merge_before(nodes, conns, "Merge Winners", merge_name="Merge Winners Fan-In")
    mw2 = lambda src, idx=0: (winners_merge, _merge_input_index(conns, src, winners_merge, source_out_idx=idx))
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Research All Needed Sentinel", "Contact Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed === true)) '
        'return [{}]; return [];',
        [mw2("IF Contact Research Needed", 1)], llx, lly,
    )
    lly += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Research None Needed Sentinel", "Contact Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed !== true)) '
        'return [{}]; return [];',
        [mw2("IF Contact Needs Judge", 1), mw2("Apply Contact Judge Verdict")], llx, lly,
    )
    lly += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Judge All Needed Sentinel", "Contact Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge === true)) '
        'return [{}]; return [];',
        [mw2("IF Contact Needs Judge", 1)], llx, lly,
    )
    lly += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Judge None Needed Sentinel", "Contact Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge !== true)) '
        'return [{}]; return [];',
        [mw2("Apply Contact Judge Verdict")], llx, lly,
    )
    lly += 120

    company_merge = splice_merge_before(nodes, conns, "Merge Company", merge_name="Merge Company Fan-In")
    mc2 = lambda src, idx=0: (company_merge, _merge_input_index(conns, src, company_merge, source_out_idx=idx))
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Research All Needed Sentinel", "Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed === true)) '
        'return [{}]; return [];',
        [mc2("IF Research Needed", 1)], llx, lly,
    )
    lly += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Research None Needed Sentinel", "Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed !== true)) '
        'return [{}]; return [];',
        [mc2("IF Needs Judge", 1), mc2("Apply Judge Verdict")], llx, lly,
    )
    lly += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Judge All Needed Sentinel", "Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge === true)) '
        'return [{}]; return [];',
        [mc2("IF Needs Judge", 1)], llx, lly,
    )
    lly += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Judge None Needed Sentinel", "Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge !== true)) '
        'return [{}]; return [];',
        [mc2("Apply Judge Verdict")], llx, lly,
    )
    # No "IF Research Errored" node exists in THIS workflow at all (this harness has no
    # "Build Research Failure Response" terminal — checked against the built node list),
    # so no companion `set_always_output_data` call is needed here.

    # Phase 70 Plan 11 (D-70-20): this workflow's own routing-IF-direct-to-Merge audit,
    # deferred by plan 70-10 — the SAME "IF Research Needed"/"IF Needs Judge" false
    # branch and "IF Contact Research Needed"/"IF Contact Needs Judge" false branch
    # shape build_enrichment_cloud() carries, mirrored here for the same reason this
    # workflow's whole sentinel network above is mirrored rather than shared.
    _retarget_all_if_direct_edges(nodes, conns, [
        ("IF Research Needed", 1, "Merge Company Fan-In"),
        ("IF Needs Judge", 1, "Merge Company Fan-In"),
        ("IF Contact Research Needed", 1, "Merge Winners Fan-In"),
        ("IF Contact Needs Judge", 1, "Merge Winners Fan-In"),
    ], llx, lly)

    return {
        "id": "LVenrichmentLive01",
        "name": "LV Enrichment (local LIVE)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
    }


# ---- CLOUD enrichment workflow ----------------------------------------------

def _http_node(name, url, x, y, auth=None, headers=None, form_body=None, json_body=None,
                method="POST", on_error="continueRegularOutput"):
    """auth: None | 'header' (generic Header Auth credential) | 'basic' (generic Basic Auth)
    | 'hubspot' (predefinedCredentialType, reuses the SAME provisioned hubspotAppToken
    credential the native n8n-nodes-base.hubspot nodes use — BUG 10's fix, see
    _hs_http_search_node below).
    headers: list of {name, value} sent as extra HTTP headers (e.g. a dynamic Bearer).
    form_body: list of {name, value} sent as application/x-www-form-urlencoded (OAuth token calls).
    json_body: n8n expression string for the JSON body; when None (and no form_body) the node
               POSTs the bare JSON identity_keys body.
    method: HTTP verb. Defaults to POST — every existing call site keeps its current
            behavior unchanged (proven by rebuild-diff, not just by this default).
    on_error: n8n `onError` mode. Defaults to 'continueRegularOutput' — every existing
              call site keeps its current behavior unchanged. Passing on_error=None OMITS
              the `onError` key from the emitted node entirely (Task 2, BUG 11 fix,
              Phase 16.7-01): a WRITE node deliberately does NOT get
              continueRegularOutput, because that mode would turn a rejected HubSpot PATCH
              into a normal-looking item that flows on to Build Response and returns a
              healthy 200 — the exact swallowed-failure mechanism that made ten live-only
              bugs invisible offline. A failed write must fail the execution instead."""
    params = {"method": method, "url": url, "options": {"timeout": 20000}}
    if form_body is not None:
        params.update({"sendBody": True, "contentType": "form-urlencoded",
                       "bodyParameters": {"parameters": form_body}})
    elif method == "GET" and json_body is None:
        # BUG 17: a GET provider call carries its identity in the URL, not a body. The
        # default `{{ JSON.stringify($json.identity_keys) }}` body below is what made
        # Lusha Company POST an identity object at an endpoint that only accepts
        # `?domain=`. No other call site passes method="GET", so this branch is new
        # ground, not a behaviour change.
        pass
    else:
        params.update({"sendBody": True, "specifyBody": "json",
                       "jsonBody": json_body or "={{ JSON.stringify($json.identity_keys) }}"})
    if auth == "header":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"})
    elif auth == "basic":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpBasicAuth"})
    elif auth == "hubspot":
        params.update({"authentication": "predefinedCredentialType", "nodeCredentialType": "hubspotAppToken"})
    if headers:
        params.update({"sendHeaders": True, "headerParameters": {"parameters": headers}})
    node = {
        "parameters": params,
        "id": nid("h"), "name": name,
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [x, y],
    }
    if on_error is not None:
        node["onError"] = on_error
    return node


# ---- ZoomInfo CLOUD credential path (Task 2 decision: split-code-node) ------
# zoominfoToken.js's needsMint/computeExpiry/parseTokenResponse/isAuthError are pure
# functions with NO compliant secret source on Cloud when called from a single Code node
# (the original ENRICH_ZOOMINFO_CACHED reads $vars.ZOOMINFO_CLIENT_ID/_SECRET directly —
# fine headless/local-live, not available on Cloud). The chosen fallback splits the one
# node into a credential-bound HTTP "Mint" node (the ONLY place client_id/client_secret
# are read, via its bound httpBasicAuth credential) plus secret-free Code nodes that
# cache/gate/enrich using nothing but the short-lived bearer token the Mint node returns.
#
# Topology (5 nodes, matches the Task 2 "3-4 more nodes + an IF branch" estimate):
#   <upstream> -> Token Gate (Code, secret-free: cache check) -> IF Needs Mint
#     true  -> Mint (HTTP, credential-bound Basic Auth) -> Cache Token (Code, secret-free)
#     false -> \_______________________________________________________/  -> Enrich (Code, secret-free)
#
# Tradeoff vs the single-node LOCAL-LIVE body: a 401 during Enrich clears the cache so the
# NEXT run re-mints, but this run does not retry inline — an inline retry would require
# the client secret, which the Enrich node deliberately never touches (see 16-01-SUMMARY.md).


def _wrap_provider_result_js(key):
    """Phase 70 Plan 04 (D-70-04): sits between a native provider HTTP node and its
    carry merge, nesting the raw response under `key` — the SAME "Stash" pattern
    ENRICH_STASH_NAME_PRIMARY_SEARCH and 70-02's "Stash Domain Search" use, and for the
    same reason: this row travels through MORE HTTP hops after this one (the next
    provider in the waterfall), so a flat merge would let this provider's response
    fields collide with the next provider's own response fields once both are combined
    onto the same item. Nesting under a distinct key means every later carry merge
    combines cleanly no matter how many more hops the row crosses."""
    return f"return $input.all().map((it) => ({{ json: {{ {key!r}: it.json }} }}));\n"


def _zoom_split_gate_js(gate_source_node):
    """Secret-free. Phase 70 Plan 04 (D-70-04): `gate_source_node` is unused — this node
    is now fed directly by the carried row (a carry merge upstream, or straight from the
    row-producing gate node when no provider ran before it), so $input here is ALREADY
    the row, never a prior provider's raw HTTP response — no by-name recovery."""
    del gate_source_node
    return inline("zoominfoToken.js") + r"""

// --- n8n wrapper: ZoomInfo token cache gate (CLOUD split-code-node, secret-free) ---
// Never reads client_id/client_secret — only the credential-bound "ZoomInfo Mint" HTTP
// node touches those (Task 2 decision).
const sd = $getWorkflowStaticData("global");
return $input.all().map((item) => {
  const row = item.json || {};
  const cached = sd.zoominfo;
  const needs_mint = needsMint(cached, Date.now());
  return { json: { ...row, zoom_needs_mint: needs_mint,
                   zoom_token: needs_mint ? null : cached.access_token } };
});
"""


def _zoom_split_cache_js(token_gate_name):
    """Secret-free. Parses the Mint HTTP node's token response (never client_id/secret),
    caches it in workflow static data, and re-attaches the original row. Phase 70
    Plan 04 (D-70-04): `token_gate_name` is unused — fed by a carry merge (input 0 the
    Mint HTTP response, input 1 the row carried from the Token Gate), so $input here is
    ALREADY the combined {row, mint response} — no by-name recovery."""
    del token_gate_name
    return inline("zoominfoToken.js") + r"""

// --- n8n wrapper: cache the freshly-minted ZoomInfo token (CLOUD split-code-node) ---
const sd = $getWorkflowStaticData("global");
return $input.all().map((item) => {
  const merged = item.json || {};
  const { access_token: _a, expires_in: _e, token_type: _t, ...row } = merged;
  let zoom_token = null;
  try {
    const parsed = parseTokenResponse(merged, Date.now());
    sd.zoominfo = parsed;
    zoom_token = parsed.access_token;
  } catch (e) {
    zoom_token = null;   // mint response malformed -> Enrich below sees no usable token
  }
  return { json: { ...row, zoom_token } };
});
"""


def _zoom_split_enrich_contacts_js():
    """Secret-free. Consumes only the short-lived bearer token attached upstream by the
    Gate/Cache nodes — mirrors ENRICH_ZOOMINFO_CACHED's contacts enrich logic exactly,
    minus the mint (that lives in the credential-bound Mint HTTP node instead)."""
    return inline("zoominfoToken.js") + r"""

// --- n8n wrapper: ZoomInfo contacts enrich via Bearer token (CLOUD split-code-node) ---
const ENRICH_URL = "https://api.zoominfo.com/gtm/data/v1/contacts/enrich";
const sd = $getWorkflowStaticData("global");
const ZOOM_OUTPUT_FIELDS = [
  "id", "firstName", "lastName", "email", "phone", "mobilePhone", "jobTitle",
  "managementLevel", "contactAccuracyScore", "validDate", "lastUpdatedDate",
  // city/state/country: LIVE-verified valid on this account 2026-08-26
  // (scripts/probe_zoominfo_location_fields.mjs; zipCode/metroArea also valid, unused).
  "city", "state", "country",
];
function toMatchPersonInput(id) {
  const m = {};
  if (id && id.email) m.emailAddress = id.email;
  if (id && id.firstName) m.firstName = id.firstName;
  if (id && id.lastName) m.lastName = id.lastName;
  if (id && id.companyName) m.companyName = id.companyName;
  return m;
}
function hasZoomKey(m) { return !!(m.emailAddress || (m.firstName && m.lastName && m.companyName)); }

// Phase 70 Plan 04 (D-70-04): a Code node, unlike a native httpRequest node, controls
// its own return shape — spreads `...row` plus `zoominfo_result` so "Normalize + Score"
// can read $input.all() directly, never a by-name lookup of this node's raw response.
const items = $input.all();
const out = [];
for (const item of items) {
  const row = item.json;
  const id = row.identity_keys || {};
  const person = toMatchPersonInput(id);
  if (!hasZoomKey(person)) { out.push({ json: { ...row, zoominfo_result: { skipped: "no zoominfo match key" } } }); continue; }
  const token = row.zoom_token;
  if (!token) { out.push({ json: { ...row, zoominfo_result: { error: "no zoominfo token available (mint failed or missing)" } } }); continue; }
  const payload = { data: { type: "ContactEnrich",
    attributes: { matchPersonInput: [person], outputFields: ZOOM_OUTPUT_FIELDS } } };
  let res;
  try {
    res = await this.helpers.httpRequest({
      method: "POST", url: ENRICH_URL,
      headers: { Authorization: "Bearer " + token,
                 "Content-Type": "application/vnd.api+json", Accept: "application/vnd.api+json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    if (isAuthError(extractErrorStatus(e))) {
      delete sd.zoominfo;  // token rejected -> clear cache so the NEXT run re-mints
    }
    res = { error: String((e && e.message) || e) };
  }
  out.push({ json: { ...row, zoominfo_result: res } });
}
return out;
"""


def _zoom_split_enrich_companies_js():
    """Secret-free. Company-branch counterpart of _zoom_split_enrich_contacts_js —
    mirrors ENRICH_ZOOMINFO_CO_CACHED's enrich logic exactly, minus the mint."""
    return inline("zoominfoToken.js") + r"""

// --- n8n wrapper: ZoomInfo companies enrich via Bearer token (CLOUD split-code-node) ---
const ENRICH_URL = "https://api.zoominfo.com/gtm/data/v1/companies/enrich";
const sd = $getWorkflowStaticData("global");
const ZOOM_CO_OUTPUT_FIELDS = [
  "id", "name", "website", "revenue", "revenueRange", "employeeCount", "employeeRange",
  "country", "primaryIndustry", "naicsCodes", "descriptionList", "foundedYear",
];
function toMatchCompanyInput(id) {
  const m = {};
  if (id && id.domain) m.companyWebsite = id.domain;
  if (id && id.companyName) m.companyName = id.companyName;
  return m;
}
function hasZoomCoKey(m) { return !!(m.companyWebsite || m.companyName); }

// Phase 70 Plan 04 (D-70-04): a Code node controls its own return shape — spreads
// `...row` plus `zoominfo_result` so "Normalize + Score Company" can read
// $input.all() directly, never a by-name lookup of this node's raw response.
const items = $input.all();
const out = [];
for (const item of items) {
  const row = item.json;
  const id = row.identity_keys || {};
  const co = toMatchCompanyInput(id);
  if (!hasZoomCoKey(co)) { out.push({ json: { ...row, zoominfo_result: { skipped: "no zoominfo company match key" } } }); continue; }
  const token = row.zoom_token;
  if (!token) { out.push({ json: { ...row, zoominfo_result: { error: "no zoominfo token available (mint failed or missing)" } } }); continue; }
  const payload = { data: { type: "CompanyEnrich",
    attributes: { matchCompanyInput: [co], outputFields: ZOOM_CO_OUTPUT_FIELDS } } };
  let res;
  try {
    res = await this.helpers.httpRequest({
      method: "POST", url: ENRICH_URL,
      headers: { Authorization: "Bearer " + token,
                 "Content-Type": "application/vnd.api+json", Accept: "application/vnd.api+json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    if (isAuthError(extractErrorStatus(e))) {
      delete sd.zoominfo;
    }
    res = { error: String((e && e.message) || e) };
  }
  out.push({ json: { ...row, zoominfo_result: res } });
}
return out;
"""


def _zoom_mint_node(name, x, y):
    """Credential-bound HTTP node — the ONLY place ZoomInfo client_id/client_secret are
    read, via its bound httpBasicAuth credential ("LV ZoomInfo", NODE_CREDENTIAL_MAP in
    deploy_n8n_workflows.py). Body is the bare grant_type; Basic auth comes from the
    credential, never a header literal."""
    return _http_node(name, "https://api.zoominfo.com/gtm/oauth/v1/token", x, y,
                       auth="basic", form_body=[{"name": "grant_type", "value": "client_credentials"}])


def _zoom_split_contacts_subgraph(gate_source_node, x, y):
    """5-node ZoomInfo split-code-node subgraph for the CONTACTS branch. Final node name
    stays "ZoomInfo Enrich" so downstream ($('ZoomInfo Enrich').all()) is unchanged.
    Returns (nodes, connections, entry_node_name, exit_node_name)."""
    nodes = [
        code_node("ZoomInfo Token Gate", _zoom_split_gate_js(gate_source_node), x, y),
        _if_bool_node("IF ZoomInfo Needs Mint", "zoom_needs_mint", x + 220, y),
        _zoom_mint_node("ZoomInfo Mint", x + 440, y - 120),
        code_node("ZoomInfo Cache Token", _zoom_split_cache_js("ZoomInfo Token Gate"), x + 660, y - 120),
        code_node("ZoomInfo Enrich", _zoom_split_enrich_contacts_js(), x + 880, y),
    ]
    conns = {
        "ZoomInfo Token Gate": {"main": [[{"node": "IF ZoomInfo Needs Mint", "type": "main", "index": 0}]]},
        "IF ZoomInfo Needs Mint": {"main": [
            [{"node": "ZoomInfo Mint", "type": "main", "index": 0}],    # true: mint
            [{"node": "ZoomInfo Enrich", "type": "main", "index": 0}],  # false: use cached
        ]},
        "ZoomInfo Mint": {"main": [[{"node": "ZoomInfo Cache Token", "type": "main", "index": 0}]]},
        "ZoomInfo Cache Token": {"main": [[{"node": "ZoomInfo Enrich", "type": "main", "index": 0}]]},
    }
    return nodes, conns, "ZoomInfo Token Gate", "ZoomInfo Enrich"


def _zoom_split_company_subgraph(gate_source_node, x, y):
    """Company-branch counterpart of _zoom_split_contacts_subgraph — node names carry a
    " Company" suffix (ZoomInfo Mint Company, etc.) so NODE_CREDENTIAL_MAP can bind both
    variants to the same "LV ZoomInfo" credential without a name collision. Final node
    name stays "ZoomInfo Company" (unchanged downstream reference, Task 5)."""
    nodes = [
        code_node("ZoomInfo Company Token Gate", _zoom_split_gate_js(gate_source_node), x, y),
        _if_bool_node("IF ZoomInfo Company Needs Mint", "zoom_needs_mint", x + 220, y),
        _zoom_mint_node("ZoomInfo Mint Company", x + 440, y - 120),
        code_node("ZoomInfo Company Cache Token", _zoom_split_cache_js("ZoomInfo Company Token Gate"),
                  x + 660, y - 120),
        code_node("ZoomInfo Company", _zoom_split_enrich_companies_js(), x + 880, y),
    ]
    conns = {
        "ZoomInfo Company Token Gate": {"main": [[{"node": "IF ZoomInfo Company Needs Mint", "type": "main", "index": 0}]]},
        "IF ZoomInfo Company Needs Mint": {"main": [
            [{"node": "ZoomInfo Mint Company", "type": "main", "index": 0}],  # true: mint
            [{"node": "ZoomInfo Company", "type": "main", "index": 0}],       # false: use cached
        ]},
        "ZoomInfo Mint Company": {"main": [[{"node": "ZoomInfo Company Cache Token", "type": "main", "index": 0}]]},
        "ZoomInfo Company Cache Token": {"main": [[{"node": "ZoomInfo Company", "type": "main", "index": 0}]]},
    }
    return nodes, conns, "ZoomInfo Company Token Gate", "ZoomInfo Company"


def _zoom_split_usage_subgraph(gate_source_node, x, y):
    """Credit-branch counterpart of _zoom_split_contacts_subgraph — the SAME Token Gate /
    IF Needs Mint / Mint / Cache Token shape, sharing the identical `sd.zoominfo` cache
    key, so the credit branch's usage check goes through the ONE shared cache instead of
    minting its own ungated token (Bug A, live 2026-07-28). Final node name stays
    "ZoomInfo Usage" (unchanged downstream reference in Build Response / test_
    remaining_credits_response.py). Node names carry a " Usage" tag so
    NODE_CREDENTIAL_MAP can bind this Mint node without colliding with the row-flow
    mints — "ZoomInfo Usage Mint" already exists in NODE_CREDENTIAL_MAP unchanged."""
    nodes = [
        code_node("ZoomInfo Usage Token Gate", _zoom_split_gate_js(gate_source_node), x, y),
        _if_bool_node("IF ZoomInfo Usage Needs Mint", "zoom_needs_mint", x + 220, y),
        _zoom_mint_node("ZoomInfo Usage Mint", x + 440, y - 120),
        code_node("ZoomInfo Usage Cache Token", _zoom_split_cache_js("ZoomInfo Usage Token Gate"),
                  x + 660, y - 120),
        code_node("ZoomInfo Usage", _zoom_split_usage_js(), x + 880, y),
    ]
    conns = {
        "ZoomInfo Usage Token Gate": {"main": [[{"node": "IF ZoomInfo Usage Needs Mint", "type": "main", "index": 0}]]},
        "IF ZoomInfo Usage Needs Mint": {"main": [
            [{"node": "ZoomInfo Usage Mint", "type": "main", "index": 0}],  # true: mint
            [{"node": "ZoomInfo Usage", "type": "main", "index": 0}],       # false: use cached
        ]},
        "ZoomInfo Usage Mint": {"main": [[{"node": "ZoomInfo Usage Cache Token", "type": "main", "index": 0}]]},
        "ZoomInfo Usage Cache Token": {"main": [[{"node": "ZoomInfo Usage", "type": "main", "index": 0}]]},
    }
    return nodes, conns, "ZoomInfo Usage Token Gate", "ZoomInfo Usage"


def _route_action_switch(name, x, y):
    """Switch node routing $json.action -> create/enrich/skip. Shared by the contacts and
    companies Cloud branches (previously duplicated inline for contacts only)."""
    def _eq(value):
        return {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict"},
                                "combinator": "and", "conditions": [{
                                    "id": nid("i"), "leftValue": "={{ $json.action }}",
                                    "rightValue": value,
                                    "operator": {"type": "string", "operation": "equals"}}]},
                "outputKey": value}
    return {
        "parameters": {"mode": "rules", "rules": {"values": [_eq("create"), _eq("enrich"), _eq("skip")]},
                       "options": {}},
        "id": nid("sw"), "name": name,
        "type": "n8n-nodes-base.switch", "typeVersion": 3, "position": [x, y],
    }


# Parse HubSpot Event — CLOUD only (Task 6, CLAUDE.md §18.2/§18.3; Phase 16.1 adds the
# provider-selection resolution, reviews A4). Normalizes the inbound webhook body (a
# HubSpot private-app event array, or a single event object, or a caller envelope
# {providers, events:[...]}) and maps HubSpot's raw objectType strings onto this
# workflow's branch names. The shared-secret check (CLAUDE.md §18.1) is done by the
# Webhook Trigger node's OWN native Header Auth (authentication="headerAuth",
# credential-bound — never a Code node reading the secret value, and never $env/$vars,
# matching Criterion 5's zero-env-var guard).
#
# Phase 16.1 (reviews A4): a bare HubSpot event array carries NO top-level `providers`
# slot (HubSpot cannot add custom body fields) -> providers resolves absent -> enrich
# nothing, the safe default (CONTEXT Locked Decision 2). An envelope
# {providers, events:[...]} carries the caller's explicit selection at the envelope
# level; a per-event `.providers` field is honoured as a fallback when the envelope
# itself carries none (`parsed.providers ?? event.providers`).
ENRICH_PARSE_EVENT_CLOUD = (
    inline("providerSelection.js", "matchProposal.js")
    + r"""

// --- n8n wrapper: normalize event array + resolve providers (reviews A4) ---
function normalizeObjectType(input) {
  const v = String(input || "").toLowerCase();
  if (["contact", "contacts", "0-1"].includes(v)) return "contacts";
  if (["company", "companies", "0-2"].includes(v)) return "companies";
  return "unknown";
}
const PROVIDER_NAMES = __PROVIDER_NAMES__;
const body = $json.body ?? $json;
const parsed = parseWebhookBody(body);
// Phase 61 Plan 05 Task 2 (REVIEW-C14, substrate 1): the caller's own client-minted
// run_id describes the REQUEST, not a row, so it is read straight off `body` at the
// envelope level — the identical idiom `parsed.mode`/`parsed.providers` already use,
// but `parseWebhookBody` itself is not widened to carry it (its own contract is
// `{events, providers, mode}` and nothing else, and this plan's own file scope does
// not touch n8n/code/providerSelection.js).
// Phase 70 Plan 03 Task 2 (D-70-07): the sibling opt-in flag this comment used to
// describe alongside `run_id` is retired — the body is ALWAYS just the ack now
// ("Build Ack" fires unconditionally), so there is nothing left to opt into.
const envelopeIsObject = body && typeof body === "object" && !Array.isArray(body);
const ENVELOPE_RUN_ID = envelopeIsObject ? (body.run_id ?? null) : null;
// Phase 61 Plan 06 Task 5 (T-61-25, substrate-3 scale-up): a request-level opt-in
// boolean, the SAME envelope+event-fallback idiom `recompute` already established — a
// pattern, not an invention (61-06-PLAN.md's own framing). `fan_depth` is deliberately
// NOT read from the envelope: the only value
// this workflow ever trusts is one ITS OWN "Build Scale Up Fan-Out" node wrote onto a
// self-dispatched child event, below. A caller-supplied one still normalizes safely via
// `Number(...) || 0` exactly like a genuine one — it just cannot manufacture trust.
const ENVELOPE_SCALE_UP = envelopeIsObject ? body.scale_up === true : false;
// Phase 36-03 Task 3 (36-CONTEXT.md sec7 step 6, D-15/D-22): refuse an oversize or empty
// events array WHOLE, never truncate, never hang. In-node here rather than a separate
// node (unlike Expand List To Events, whose separate-node placement guards against a
// MISSING events array being masked by parseWebhookBody's bare-event fallback): an
// oversized or empty array still IS an array, so that fallback never masks either case,
// and a separate node buys nothing extra. Mirrors ENRICH_EXPAND_LIST_TO_EVENTS's
// refusal-as-terminating-item shape: a single item carrying outcome:"refused" and a
// reason, never a thrown exception (a throw risks the Cloudflare 524, D-22) and never a
// partial map (D-15 — refuse whole, never truncate). object_type:"unknown" routes the
// refusal through the existing "IF Object Type Supported" false edge to "Unsupported
// Object Type" -> "Build Response", so the reason reaches the caller as a 200 with zero
// new nodes or edges.
// Phase 36-06 (37-CONTEXT.md §13 ceiling ruling): parsed.mode is read at the ENVELOPE
// level only (parseWebhookBody's contract) — an envelope that carries no top-level mode
// but whose individual events each carry one falls through to the write ceiling. That is
// fail-closed and correct: the row-level `parsed.mode ?? event.mode` fallback used below
// (and at Decide Action) is about which mode a ROW runs in; this is about how long the
// WHOLE request may take, and the stricter bound is the safe answer when the envelope
// itself has not declared its mode.
const MAX_WRITE_EVENTS = __MAX_LIST_RECORDS__;
const MAX_PROPOSE_EVENTS = __MAX_PROPOSE_RECORDS__;
const MAX_EVENTS = isReturnOnly(parsed.mode) ? MAX_PROPOSE_EVENTS : MAX_WRITE_EVENTS;
if (parsed.events.length > MAX_EVENTS) {
  return [{ json: {
    outcome: "refused",
    reason: `Request carries ${parsed.events.length} events, more than this backend can ` +
      `enrich in one request — the limit is ${MAX_EVENTS} record(s) per request. ` +
      `Nothing was enriched. Send fewer records per request, in batches of ${MAX_EVENTS} ` +
      `or fewer.`,
    events: [],
    object_type: "unknown",
  } }];
}
if (parsed.events.length === 0) {
  return [{ json: {
    outcome: "refused",
    reason: "Request carries an empty events array — nothing to enrich. Send at " +
      "least one event.",
    events: [],
    object_type: "unknown",
  } }];
}
return parsed.events.map((event) => {
  const providersRaw = parsed.providers ?? event.providers;
  const { provider_enabled, providers_requested } = resolveEnabledProviders(providersRaw, PROVIDER_NAMES);
  const object_type = normalizeObjectType(event.objectType || event.objectTypeId);
  return { json: {
    event_id: `${event.subscriptionId || "sub"}:${event.objectId}:${event.eventId || event.occurredAt}`,
    object_id: event.objectId != null ? String(event.objectId) : null,
    object_type,
    property_name: event.propertyName || null,
    event_type: event.subscriptionType || event.eventType || null,
    occurred_at: event.occurredAt || new Date().toISOString(),
    provider_enabled,
    providers_requested,
    // Phase 36-03 (36-CONTEXT.md sec6): mode read at the envelope level exactly like
    // providers above, with the same per-event fallback. The two-state write-guard
    // predicate is applied downstream at Decide Action, not here — this only threads the
    // value onto the row so it rides the `...event` spread below to every later hop.
    mode: parsed.mode ?? event.mode ?? null,
    // MINIMUM-scope shim (Task 6, documented per the plan's own budget carve-out):
    // Build Identity/Build Company Identity still read direct body fields (email/
    // domain/...) rather than fetching the record fresh by object_id — restructuring
    // them to fetch-by-id is a larger port than this task's budget. Spreading the raw
    // event here keeps that shim working for a direct-field test payload; a genuine
    // HubSpot event carries none of these fields, so on the real path Build Identity
    // sees only object_id/object_type until a follow-up phase adds the fetch-by-id.
    ...event,
    // Phase 47.5 (RECOMP-01): the on-demand veto-recompute intent. Placed AFTER the
    // `...event` spread deliberately — the companies branch has entry_strip_markers=False,
    // so a caller-supplied raw row property is NOT stripped on that branch and would
    // otherwise shadow this normalization. Strictly `=== true`: anything that is not a real
    // JSON boolean true (the string "true", 1, "yes", absent) normalizes to false. That
    // direction is fail-closed and costs nothing.
    //
    // NOT carried in `mode`, deliberately: isReturnOnly() (n8n/code/matchProposal.js)
    // treats EVERY non-"write" mode as return-only, so a mode-borne intent would set
    // action:"proposed", write nothing, and report success — the exact silent-success
    // class this phase exists to remove.
    recompute: event.recompute === true,
    // Phase 61 Plan 05 Task 2 (REVIEW-C14, substrate 1): placed AFTER the `...event`
    // spread for the SAME reason `recompute` above is — a caller-supplied raw row
    // property must not shadow the envelope-level normalization. `run_id` is the
    // caller's own client-minted handle (never generated here), read unconditionally
    // now — every request's ack ("Build Ack") reports it, not only an opted-in one
    // (Phase 70 Plan 03 Task 2, D-70-07 — the opt-in flag this field used to gate is
    // retired).
    run_id: ENVELOPE_RUN_ID ?? event.run_id ?? null,
    // Phase 61 Plan 06 Task 5: same placement rationale as recompute above — AFTER
    // the `...event` spread so a caller-supplied raw row property cannot shadow this.
    scale_up: (ENVELOPE_SCALE_UP || event.scale_up) === true,
    fan_depth: Number(event.fan_depth) || 0,
  }};
});
"""
).replace("__PROVIDER_NAMES__", json.dumps(provider_registry.PROVIDER_NAMES))


# Phase 61 Plan 05 Task 2 (RUN-01/RUN-03, REVIEW-C14, substrate 1 of
# 61-SPIKE-VERDICT.md — "Respond node moved to the front of the chain", P-07 confirmed
# live execution 12035, 2026-08-30). Fanned UNCONDITIONALLY from "Parse HubSpot Event"
# alongside its existing two targets ("IF Object Type Supported", "Credit Request") —
# the SAME fan-out shape that pair already uses (Phase 16.1 reviews C1) — so this is one
# more parallel target, not a re-point of any existing edge.
#
# Phase 70 Plan 03 Task 2 (D-70-07): the opt-in is retired. "Build Ack" (renamed from
# "Build Async Ack" — the node this feeds is no longer conditional, so the name should
# not imply one) is now the SOLE producer "Respond to Webhook" ever hears from: every
# OTHER edge into that node ("IF List Expanded" false, "Build Scale Up Ack", "Build
# Response") is removed. It fires unconditionally, exactly once, for every request —
# `$input.all()` because this node also gains a SECOND inbound edge, from "IF List
# Expanded" false (a list-expansion refusal, where "Parse HubSpot Event" never runs at
# all this execution) — the two producers are mutually exclusive per execution (a
# list-refusal short-circuits BEFORE Parse HubSpot Event, and every OTHER path requires
# it to have run), so this node still runs exactly once regardless of which one
# delivered; first-arrival semantics is safe here for the identical reason it is safe
# throughout this plan's class-(b) convergences. `row_ids` are the request's own row
# identifiers (D-70-08a): one per event row that carried one, empty for a spec form
# that mints none or for a refusal (neither carries `row_id`).
ENRICH_BUILD_ACK = r"""// Build Ack — Phase 70 Plan 03 Task 2 (D-70-07). THE sole responder input.
const rows = $input.all().map((it) => it.json || {});
const run_id = rows.length ? (rows[0].run_id ?? null) : null;
const row_ids = rows
  .map((r) => r.row_id)
  .filter((id) => id !== null && id !== undefined);
return [{ json: { run_id, accepted: true, row_ids } }];
"""

# Phase 70 Plan 03 Task 2 (D-70-07). Turns a reason that used to reach the caller ONLY
# via the HTTP response body into a row that reaches "Build Response" instead — the sole
# channel now that the body is always the ack. Fed by two producers that are mutually
# exclusive PER EXECUTION (see this node's own wiring comment at its connections):
# "IF List Expanded" false (a list-expansion refusal — "Parse HubSpot Event" never ran
# this execution) and "Build Scale Up Ack" (the scale-up dispatch confirmation — a
# status row, not a refusal, but body-borne today and moved the same way). Routed into
# "Build Response Merge" via a NEW input (`_append_merge_input`, below) rather than
# straight into "Build Response": the Merge's other ~10 inputs are all sourced from
# nodes downstream of the normal (non-refused, non-fanned) chain, so in EITHER of this
# node's two scenarios none of them ever fire either — covered by "Refusal Fired
# Sentinel", fed FROM this node, feeding every one of those OTHER inputs directly,
# mirroring this plan's own starved-lane mechanism rather than inventing a second one.
ENRICH_BUILD_REFUSAL_ROW = r"""// Build Refusal Row — Phase 70 Plan 03 Task 2 (D-70-07).
return $input.all().map((it) => {
  const row = it.json || {};
  if (row.scale_up_dispatched === true) {
    return { json: {
      action: "scale_up_dispatched",
      reason: "batch dispatched to a self-fanned child execution",
      run_id: row.run_id ?? null,
      row_id: row.row_id ?? null,
    } };
  }
  return { json: {
    action: "list_expansion_refused",
    reason: row.reason || "list expansion refused",
    run_id: row.run_id ?? null,
    row_id: row.row_id ?? null,
  } };
});
"""

# Phase 61 Plan 06 Task 5 (T-61-25, RUN-02/AFTER-02's substrate-3 scale-up path,
# 61-PREMISE-DOCS-FINDINGS.md's "sub-workflows are doubly exempt" finding, P-14). This
# bound is the load-bearing safety property, not a detail: it lives HERE, inside the
# workflow, so a caller who never passes `fan_depth` still cannot start more than one
# level of self-dispatch. 1 means exactly one fan-out hop is ever permitted — a row this
# workflow itself re-dispatches to itself always arrives with `fan_depth >= 1` (see the
# `depth + 1` below) and is refused a second hop by BOTH `IF Scale Up Route` (which never
# routes it back to this branch) AND this node's own independent check, so termination
# does not depend on either guard alone being correct (defense in depth, the same shape
# `p14`'s own Depth Guard IF carried but never exercised at runtime).
SCALE_UP_MAX_FAN_DEPTH = 1

# The gate `IF Scale Up Route` (an n8n-native IF condition, built alongside this string)
# tests the IDENTICAL predicate — same threshold, same fields — so a request is routed to
# the fan-out lane if and only if this node would also fan it out. Declared once here so
# the two expressions cannot silently drift apart.
_SCALE_UP_IS_FANNING_EXPR = (
    "$json.scale_up === true && (Number($json.fan_depth) || 0) < "
    f"{SCALE_UP_MAX_FAN_DEPTH}"
)

# Phase 61 Plan 06 Task 5. Fed ONLY by `IF Scale Up Route`'s TRUE lane (already gated),
# but self-gated a SECOND time regardless — same discipline `ENRICH_BUILD_ASYNC_ACK`
# already uses for its own opt-in, and the two independent stops T-61-25's mitigation
# names. Reshapes the current (already-normalized) event back into the BARE event shape
# `ENRICH_SJ3_BUILD_DISPATCH_EVENT` already establishes as this workflow's OWN proven
# cross-workflow dispatch contract (fix(40)/WINDOWS.md #3 — the "Execute Workflow
# Trigger" entry point this reuses, unchanged, rather than inventing a second one) —
# `scale_up` forced `false` and `fan_depth` incremented per item, so a dispatched child
# can never re-fan even if every other guard were absent.
#
# `$input.all()`, NOT a bare `$json` (deviation, Rule 1 — found live at this task's own
# runtime proof, execution 12042: a 2-record disarmed batch fanned out only ONE child,
# silently dropping the second. `Build Async Ack`'s own bare-`$json` shape — this node's
# original model — only ever reads the FIRST of however many items n8n hands a
# "runOnceForAllItems" Code node; it was never exercised past 1 item live before this.
# `ENRICH_SKIP_NOOP_JS`/`ENRICH_SJ3_BUILD_DISPATCH_EVENT` are this file's own precedent
# for the CORRECT multi-item shape in this exact node mode — `$input.all().filter().map()`
# — reused here rather than repeating Build Async Ack's latent gap. A dropped fan-out
# item is silent data loss, not a safety issue on its own (T-61-25's depth/forced-false
# stops are per-item and untouched by this fix), but it is a real bug: the whole point of
# scale-up is a BATCH, and this task's own runtime proof exists to catch exactly this
# class of miss rather than merely assert the mechanism on paper.
ENRICH_BUILD_SCALE_UP_FAN_OUT = r"""// Build Scale Up Fan-Out — Phase 61 Plan 06 Task 5.
// Independently re-checks the SAME predicate "IF Scale Up Route" already gated on —
// T-61-25's two-independent-stops mitigation, not redundancy for its own sake.
const SCALE_UP_MAX_FAN_DEPTH = __SCALE_UP_MAX_FAN_DEPTH__;
return $input.all()
  .filter((it) => {
    const depth = Number(it.json.fan_depth) || 0;
    return it.json.scale_up === true && depth < SCALE_UP_MAX_FAN_DEPTH;
  })
  .map((it) => {
    const depth = Number(it.json.fan_depth) || 0;
    // Bare-event shape (CLAUDE.md §18.2 / ENRICH_SJ3_BUILD_DISPATCH_EVENT's own
    // precedent): arrives at the self-dispatched child's "Execute Workflow Trigger"
    // (passthrough) and is read by Parse HubSpot Event as `$json.body ?? $json` — no
    // `.body` wrapper needed.
    return { json: {
      objectId: it.json.object_id,
      objectType: it.json.object_type,
      subscriptionType: it.json.event_type || null,
      propertyName: it.json.property_name || null,
      occurredAt: new Date().toISOString(),
      providers: it.json.providers_requested,
      mode: it.json.mode,
      run_id: it.json.run_id ?? null,
      row_id: it.json.row_id ?? null,
      // The two independent stops (T-61-25): forced false regardless of what the
      // ORIGINAL caller asked for, plus the incremented, workflow-owned depth counter.
      scale_up: false,
      fan_depth: depth + 1,
    } };
  });
""".replace("__SCALE_UP_MAX_FAN_DEPTH__", str(SCALE_UP_MAX_FAN_DEPTH))

# Phase 61 Plan 06 Task 5. `Dispatch Self` (Execute Workflow, mode="each",
# waitForSubWorkflow=false — P-13's proven detached shape) never waits, so its own output
# item IS the dispatch record (each carrying `metadata.subExecution.executionId` per
# P-13's own `correlate_child_id`), not a business outcome. This shapes a minimal ack from
# it rather than echoing that internal metadata verbatim to the caller — mirrors
# `ENRICH_BUILD_ASYNC_ACK`'s own minimal-ack precedent for the same reason.
# `$input.all()` (same Rule 1 fix as Build Scale Up Fan-Out above, same commit): "each"
# mode dispatch produces one output item PER dispatched child, and every one must be
# acknowledged, not just the first.
ENRICH_BUILD_SCALE_UP_ACK = r"""// Build Scale Up Ack — Phase 61 Plan 06 Task 5.
// Reports what was DISPATCHED (fire-and-forget), never a business outcome — each child
// execution this represents may still be running when this responds.
// Phase 70 Plan 03 Task 2 (D-70-07): also carries `row_id` — "Dispatch Self" is
// passthrough, so the dispatched child's own row_id survives on `it.json`, and this
// node's sole downstream consumer ("Build Refusal Row") needs it to shape a
// correlatable row now that this confirmation is read from runData, not the body.
return $input.all().map((it) => ({
  json: { scale_up_dispatched: true, run_id: it.json.run_id ?? null, row_id: it.json.row_id ?? null },
}));
"""


# ---- Phase 25 Plan 03: HubSpot list -> record events (INGEST-04, D-01/D-02/D-15) -------
#
# The plugin holds no HubSpot token (D-01), so it posts a list identifier verbatim and this
# branch resolves it with the credential n8n already owns. The branch is ADDITIVE: it hangs
# off a new IF on the webhook trigger whose FALSE lane is the existing edge into
# `Parse HubSpot Event`, so a record-ID envelope takes exactly the path it took before.
#
# It has to sit UPSTREAM of `Parse HubSpot Event` rather than beside it: that node treats an
# object with no `events` array as a single bare event, so an unexpanded list body would
# resolve to one unknown-object-type event, terminate as unsupported and return a clean 200 —
# a silent no-op, not an error (T-25-16).
#
# THE CEILING. `max_records_per_chunk` is derived in 25-BLOCKERS.md from live execution
# timing (29-TIMING.md): ~36s per record against n8n Cloud's ~100s Cloudflare-enforced
# response ceiling, with no `Split In Batches` node anywhere in this workflow, gives
# floor(100/45) = 2. A list resolved on the BACKEND cannot be split by the CLIENT (D-02),
# so the backend has to enforce the same bound client-side chunking enforces — and it
# enforces it by REFUSING, never by truncating, because a truncated batch enriches an
# arbitrary subset and reports success (D-15). CONFIRMED 2026-08-03: probe B4 ran the
# full waterfall live (lusha+apollo+zoominfo, one company record) in 37.44 s — worst case
# 37.44, +25% headroom = 46.8, floor(100/46.8) = 2. The ceiling held on the expensive
# path and is no longer provisional. Still deliberately declared in ONE place.
ENRICH_MAX_LIST_RECORDS = 2

# Phase 36-06 (37-CONTEXT.md §13 ceiling ruling): the write ceiling above is 2 because
# probe B4 measured the FULL WATERFALL (lusha+apollo+zoominfo, one company record) at
# 37.44 s/record. A return-only (`mode:"propose"`) request runs ZERO provider calls —
# its per-row cost is two HubSpot search POSTs. Applying the waterfall's ceiling to it is
# an unnecessarily strict boundary. Originally ASSUMED (worst case 4 s/row, +25% headroom
# = 5 s/row against the ~100 s Cloudflare ceiling, floor(100/5) = 20) with no in-repo
# measurement. MEASURED 2026-08-05: the live 9-director propose walk (37-09's operator
# checkpoint) took 13.16 s for 9 rows = 1.46 s/row — well inside the 5 s/row assumption,
# so the derived ceiling only grows from here (floor(100 / (1.46*1.25)) ≈ 54). 20 is kept
# as-is rather than raised, since raising it is a separate deliberate decision, not a
# consequence of this measurement — the PROVISIONAL label is retired because the number
# is now bounded by an actual measurement, the same way the 37.44 s note above was
# promoted from provisional to confirmed.
ENRICH_MAX_PROPOSE_RECORDS = 20

# Task 3's events-array-size refusal lives inside ENRICH_PARSE_EVENT_CLOUD (defined
# above, before this ceiling is known) — a second, deferred placeholder substitution on
# the SAME single declaration, not a second constant.
ENRICH_PARSE_EVENT_CLOUD = ENRICH_PARSE_EVENT_CLOUD.replace(
    "__MAX_LIST_RECORDS__", str(ENRICH_MAX_LIST_RECORDS)
).replace("__MAX_PROPOSE_RECORDS__", str(ENRICH_MAX_PROPOSE_RECORDS))

_HS_LISTS_BASE = "https://api.hubapi.com/crm/v3/lists"

# Object-type-id lookup inlined into the URL expression rather than added as a fifth prep
# node. Fail-closed: an unrecognized object type falls through to the literal "unsupported"
# path segment, which 404s, which `Expand List To Events` reads as "did not resolve" — never
# as a default object type. ponytail: a lookup table in a URL template beats a node.
_LIST_OBJECT_TYPE_ID_EXPR = (
    '{{ {"contact":"0-1","contacts":"0-1","0-1":"0-1",'
    '"company":"0-2","companies":"0-2","0-2":"0-2"}'
    '[String((($json.body || $json).list || {}).objectType || "").toLowerCase().trim()]'
    ' || "unsupported" }}'
)
_LIST_NAME_EXPR = (
    '{{ encodeURIComponent(String((($json.body || $json).list || {}).name || "").trim()) }}'
)
ENRICH_LIST_BY_NAME_URL = (
    f"={_HS_LISTS_BASE}/object-type-id/{_LIST_OBJECT_TYPE_ID_EXPR}/name/{_LIST_NAME_EXPR}"
)

# Asks for ONE MORE than the ceiling, so an oversize list comes back detectable rather than
# invisible: at exactly `limit` a caller cannot tell "the whole list" from "the first page".
# Phase 70 Plan 04 (D-70-04): reads the listId off "Wrap List By Name Result"'s own nested
# key (`list_by_name_result.listId`) — the carry merge after that Wrap node re-attaches the
# pre-hop row, so by the time THIS node's expression runs, $json is that merged item, never
# the bare List-By-Name response the pre-carry-merge expression assumed.
ENRICH_LIST_MEMBERSHIPS_URL = (
    f"={_HS_LISTS_BASE}/"
    '{{ encodeURIComponent(String(($json.list_by_name_result || {}).listId || "")) }}'
    f"/memberships?limit={ENRICH_MAX_LIST_RECORDS + 1}"
)

# Phase 70 Plan 04 (D-70-04): reads the caller's body and both HubSpot responses off the
# ONE merged item "HubSpot List Memberships Carry Merge" (wired below) hands this node —
# never a by-name lookup. The chain is two Wrap+carry-merge hops (mirrors the provider
# waterfall's own multi-hop pattern): "Wrap List By Name Result" nests the first response
# under `list_by_name_result` before it crosses the Memberships hop, and the trailing carry
# merge re-attaches that row (trigger body + `list_by_name_result`) onto the raw Memberships
# response, unwrapped, since nothing downstream needs it to survive a THIRD hop.
ENRICH_EXPAND_LIST_TO_EVENTS = (
    inline("listExpansion.js")
    + r"""

// --- n8n wrapper: Expand List To Events (Phase 25 Plan 03) ---
const MAX_LIST_RECORDS = __MAX_LIST_RECORDS__;
const merged = ($input.first() && $input.first().json) || {};
const trigger = merged.body || merged;
const result = expandListToEvents({
  body: trigger,
  listResult: merged.list_by_name_result || null,
  membershipsResult: merged,
  maxRecords: MAX_LIST_RECORDS,
});
if (result.refused) {
  // Terminating item, NOT an exception: it carries the reason to the caller as a response.
  // `events: []` is what `IF List Expanded` gates on, so a refusal can never be enriched.
  return [{ json: { outcome: "refused", reason: result.reason, events: [] } }];
}
const envelope = { events: result.events };
if (result.providers !== undefined) envelope.providers = result.providers;
return [{ json: envelope }];
"""
).replace("__MAX_LIST_RECORDS__", str(ENRICH_MAX_LIST_RECORDS))


# NOTE (Phase 13/16): this Cloud webhook template's companies branch is ported by Task 5
# (Phase 16). Until then, and unlike build_enrichment_local_live(), the Claude web-research
# nodes (Research Trigger Gate / Build Research Request / Claude Web Research / Validate
# Research Output) do NOT land here.

# Phase 16.1 Plan 02 (reviews C1) — single-item credit branch. Forks off "Parse HubSpot
# Event" (never the multi-row terminal/enrichment flow): regardless of how many
# rows/events this run processes, this node emits EXACTLY ONE item, so each provider's
# credit-check HTTP node downstream fires AT MOST ONCE per run — not once per row, which
# live-observed a Lusha 5 req/min 429 -> all credits null (the exact failure this branch
# prevents). Deliberately does NOT read $input — its output cardinality can never track
# the row count upstream.
ENRICH_CREDIT_REQUEST = r"""// Credit Request — Phase 16.1 Plan 02 (reviews C1).
// Phase 70 Plan 04 Task 2 (D-70-03): fed directly by "Parse HubSpot Event" (a fan-out
// edge, never an HTTP node) — $input.first() IS that same delivery's first item,
// never a by-name lookup.
const first = $input.first();
const providers_requested = (first && first.json && first.json.providers_requested) || [];
return [{ json: { providers_requested } }];
"""

# Phase 70 Plan 04 (D-70-04): retires Build Response's `nodeAll('Lusha Usage', ...)`
# by-name reads. Each provider's credit lane now normalises itself to a common
# `{provider, requested, credits}` shape BEFORE it reaches "Collect Credits" (an
# append-mode Merge, one input per provider) — the TRUE lane through the real HTTP
# call, the FALSE lane through a static skip marker — so all 3 inputs always deliver
# exactly one item per execution regardless of provider selection (no starved-lane
# sentinel needed: a routing IF's true/false lanes converging on the SAME input are
# mutually exclusive by construction, `classify_convergence`'s "mutually_exclusive"
# class). "Build Credits Summary" then filters to `requested` only, in the same
# provider identity `extractCredits` already keys on — no providers_requested lookup
# needed there at all.
def _credit_adapt_js(provider):
    return inline("providerSelection.js") + f"""
// Adapt {provider.title()} Usage — Phase 70 Plan 04 (D-70-04). Reads its own HTTP
// response via bare $json (no by-name); the provider identity is static per lane.
return $input.all().map((it) => ({{ json: {{
  provider: {provider!r},
  requested: true,
  credits: extractCredits({provider!r}, it.json),
}} }}));
"""


def _credit_skip_js(provider):
    return f"""// {provider.title()} Credit Skipped — Phase 70 Plan 04 (D-70-04).
// "IF {provider.title()} Credit Requested"'s false lane: this provider was not
// requested this run. Still delivers exactly one item so "Collect Credits" (append,
// 3 inputs) never starves on a partial provider selection.
return [{{ json: {{ provider: {provider!r}, requested: false, credits: null }} }}];
"""


ENRICH_BUILD_CREDITS_SUMMARY = r"""// Build Credits Summary — Phase 70 Plan 04 (D-70-04).
// Fed by "Collect Credits" (append, 3 inputs: one {provider, requested, credits} item
// per provider, real or skipped). Filters to requested providers only — the same
// membership test `providers_requested.map(...)` used to apply — and emits ONE item,
// broadcast onto every terminal row by "Credits Broadcast" (combineAll), never a
// by-name read of the credit-check HTTP nodes.
return [{ json: {
  remaining_credits: $input.all()
    .map((it) => it.json)
    .filter((r) => r && r.requested)
    .map((r) => ({ provider: r.provider, credits: r.credits })),
} }];
"""

# Bug A fix (live 2026-07-28): the credit branch's ZoomInfo usage check used to mint its
# OWN token unconditionally (no needsMint() gate) and read it straight off its own prior
# HTTP node's raw response — never touching the sd.zoominfo cache the contacts/companies
# row-flow subgraphs read and write. ZoomInfo allows exactly ONE active token per
# credential, so that ungated mint invalidated whatever the row-flow had just cached
# WITHOUT updating the cache to match, leaving it pointing at a token ZoomInfo had
# already killed — the row-flow's NEXT run then reused that "still fresh per its `exp`,
# actually dead" token and 401'd (live-observed as consecutive-run 401s while the credit
# check itself succeeded in the same run). Reads only `zoom_token`, attached by the
# SAME Token Gate/Cache Token nodes the contacts/companies Enrich nodes use — see
# _zoom_split_usage_subgraph() — so this consumer shares the one cache instead of
# bypassing it. Same isAuthError/cache-clear-on-401 behavior as the row-flow Enrich
# nodes (Bug B fix): 400/403/404/429/5xx must never clear the cache, only a real 401.
def _zoom_split_usage_js():
    return inline("zoominfoToken.js") + r"""

// --- n8n wrapper: ZoomInfo usage/credit check via Bearer token (CLOUD split-code-node) ---
const USAGE_URL = "https://api.zoominfo.com/gtm/data/v1/users/usage";
const sd = $getWorkflowStaticData("global");
const items = $input.all();
const out = [];
for (const item of items) {
  const token = item.json.zoom_token;
  if (!token) { out.push({ json: { error: "no zoominfo token available (mint failed or missing)" } }); continue; }
  let res;
  try {
    res = await this.helpers.httpRequest({
      method: "GET", url: USAGE_URL,
      headers: { Authorization: "Bearer " + token, Accept: "application/vnd.api+json" },
    });
  } catch (e) {
    if (isAuthError(extractErrorStatus(e))) {
      delete sd.zoominfo;  // token rejected -> clear cache so the NEXT run re-mints
    }
    res = { error: String((e && e.message) || e) };
  }
  out.push({ json: res });
}
return out;
"""


# Phase 16.1 Plan 02 (reviews C1/C3/LOW-3) — the convergence node every enrichment
# terminal feeds (5 real terminals + the 2 re-pointed IF-enrich-false lanes + the
# unsupported-object-type terminal). Reads each credit-check node BY NAME via the
# guarded nodeAll idiom (a not-requested/unexecuted node -> [] -> extractCredits(...) ->
# null; mirrors ENRICH_NORMALIZE_SCORE_CLOUD's nodeAll) and assembles remaining_credits
# for exactly providers_requested (none -> []). The credit branch runs off Parse HubSpot
# Event (run START), independent of and typically well ahead of this deep convergence.
#
# HONEST response semantics (reviews C3): this node has MULTIPLE inbound branches, so it
# (and the "Respond to Webhook" node it feeds) fires on whichever branch arrives FIRST —
# parity with the prior responseMode:"lastNode" behavior, NOT a hard determinism
# guarantee across a mixed create/update/skip batch. The true 0-event/empty-body case and
# the exact multi-terminal arrival ordering are Track B execution-level test items, not
# provable by this Code node or the static graph.
ENRICH_BUILD_RESPONSE = inline("providerSelection.js") + r"""

// --- n8n wrapper: Build Response (Phase 16.1 Plan 02) ---
// Phase 70 Plan 04 (D-70-04): `remaining_credits` is precomputed by "Build Credits
// Summary" and broadcast onto every row by "Credits Broadcast" (combineAll, spliced
// between "Build Response Merge" and this node) — read straight off the row below,
// never a by-name lookup of the credit-check nodes.

// Phase 61 Plan 04 Task 1 (REVIEW-05): the per-row OUTCOME CONTRACT. Build Response
// already spreads the whole row (`...row` below) to every terminal (skip, proposed,
// write_blocked, create, enrich, research_failed, unsupported...) — the transport
// already exists. What was missing is a NAMED, VERSIONED projection of the five
// signals the client's confidence table reads, computed HERE because this is the one
// convergence point every terminal reaches, rather than duplicated per-terminal.
// Absence is stamped explicitly (null), never a missing key, so a match-only call
// ("no providers ran") and a lane that dropped a field cannot look alike to a parser.
function _agreementByField(scored) {
  const best = (scored && scored.best) || {};
  const out = {};
  for (const field of Object.keys(best)) {
    out[field] = (best[field] && best[field].agreedBy) || [];
  }
  return out;
}
// Phase 62 Plan 04 (D-62-16): version bumped 1 -> 2 — num_associated_contacts is a NEW
// field added to the outcome projection below (additive, no existing field removed or
// reshaped). The client parser (preingest.py) widens its known-version set in the same
// commit rather than moving it, since the currently-deployed backend still stamps 1
// until this regenerated JSON is deployed — either deploy order must keep parsing.
//
// Phase 66 Plan 03 (D-66-05/D-66-06): contactability (below) is ALSO additive and
// DELIBERATELY does NOT bump this constant a second time. preingest.py refuses outright
// any version outside its frozen known set rather than degrading, and the installed
// plugin marketplace clone does not self-refresh — a backend stamping a version the
// installed plugin has never learned would refuse EVERY row, not lose a field (T-66-12).
// An additive key at the CURRENT version has no such failure mode: an unknown extra key
// is simply not read by an older client. Bump only when a field is removed or reshaped.
const OUTCOME_CONTRACT_VERSION = 2;

// Phase 66 Plan 03 (D-66-05/D-66-06): per-row phone+email completeness, REPORT-ONLY.
// Nothing anywhere may branch on this value — no gate, hold, refusal or write decision
// reads it (D-66-05); it is stamped here and rendered by the plugin's report, nothing
// else consumes it. Computed from the POST-RUN state — the union of the record HubSpot
// already held (existingRecord) and whatever THIS run promoted (merge.canonicalPatch) —
// never the raw provider return, so a value this run promoted counts and a value merely
// staged (not yet written) does not.
const CONTACTABILITY_COMPLETE = "complete";
const CONTACTABILITY_EMAIL_ONLY = "email_only";
const CONTACTABILITY_NONE = "none";
function _hasValue(v) { return v !== undefined && v !== null && v !== ""; }
function _postRunFieldValue(field, existingRecord, canonicalPatch) {
  if (canonicalPatch && _hasValue(canonicalPatch[field])) return canonicalPatch[field];
  if (existingRecord && _hasValue(existingRecord[field])) return existingRecord[field];
  return null;
}
function _contactability(row) {
  // Companies (and anything not a contact) stamp explicit absence — never a missing key
  // — matching this node's existing num_associated_contacts discipline above.
  if (row.object_type === "companies") return { state: null, fields: null };
  const existingRecord = row.existingRecord || {};
  const canonicalPatch = (row.merge && row.merge.canonicalPatch) || {};
  const emailField = _postRunFieldValue("email", existingRecord, canonicalPatch) !== null ? "email" : null;
  // Either phone field satisfies the phone half (D-66-05, deliberate): ZoomInfo's
  // verified-direct-dial fields (directPhone/hasDirectPhone) are 400/unentitled on this
  // account, so the ceiling this account can buy is a landline (often a switchboard)
  // plus a mobile — requiring a mobile specifically would make "complete" largely
  // unreachable.
  const phoneField = _postRunFieldValue("phone", existingRecord, canonicalPatch) !== null ? "phone"
    : (_postRunFieldValue("mobilephone", existingRecord, canonicalPatch) !== null ? "mobilephone" : null);
  let state = CONTACTABILITY_NONE;
  if (emailField && phoneField) state = CONTACTABILITY_COMPLETE;
  else if (emailField) state = CONTACTABILITY_EMAIL_ONLY;
  return { state, fields: { email: emailField, phone: phoneField } };
}
// Phase 70 Plan 03 (D-70-01): this node ("Build Response") sits behind a real Merge with
// a starved-lane sentinel on every one of its 11 terminal inputs that could otherwise
// never fire on a given batch; drop an identity-less sentinel marker before it is
// reported back to the caller as a phantom row.
return $input.all().filter((it) => Object.keys(it.json || {}).length > 0).map((item) => {
  const row = item.json || {};
  const match = row.match || null;
  // Meaningful for tier "medium" only (REVIEW-C9) — "high"/"none"/"unknown" already
  // encode their own cardinality in the tier itself, and summarizeMatch deliberately
  // empties `candidates` for a high-tier auto-match.
  const candidate_count = (match && Array.isArray(match.candidates)) ? match.candidates.length : 0;
  const contactability = _contactability(row);
  return { json: {
    ...row,
    remaining_credits: row.remaining_credits || [],
    outcome_contract_version: OUTCOME_CONTRACT_VERSION,
    candidate_count,
    provider_agreement: row.scored ? _agreementByField(row.scored) : null,
    material_conflicts: row.material_conflicts || null,
    judge_adjudicated_fields: row.judge_confidence_by_field || null,
    // D-62-16: absence stamped explicitly (null), never a missing key, so a company
    // row that never went through the search (e.g. contacts-only requests) and a
    // company genuinely unreadable cannot look alike to a parser.
    num_associated_contacts: row.num_associated_contacts ?? null,
    // D-66-05/D-66-06: report-only, no branch anywhere reads these two keys.
    contactability: contactability.state,
    contactability_fields: contactability.fields,
    // Phase 70 Plan 03 Task 2 (D-70-07): a top-level `reason`, additive — most terminal
    // shapes already carry one directly (Build Refusal Row's rows, `gate.reason` is
    // ALSO surfaced here for the recompute_refused/write_blocked shapes, whose reason
    // otherwise lives nested at `gate.reason` only) so a client reading runData off
    // this ONE contract never has to know which terminal produced a given row.
    reason: row.reason ?? (row.gate && row.gate.reason) ?? null,
  }};
});
"""


def _credit_http_node(name, url, method, x, y, auth=None, extra_headers=None):
    """Read-only provider usage/credit-check node (16.1-RESEARCH.md Task 1, live-curl-
    validated GET/POST per provider). Credential-bound where `auth` is set; onError:
    continueRegularOutput — a credit-check failure must NEVER fail the run (SC-5)."""
    params = {"method": method, "url": url, "options": {"timeout": 20000}}
    if extra_headers:
        params.update({"sendHeaders": True, "headerParameters": {"parameters": extra_headers}})
    if auth == "header":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"})
    return {
        "parameters": params,
        "id": nid("h"), "name": name,
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [x, y],
        "onError": "continueRegularOutput",
    }


# ---- Phase 16.4 Task 1: fetch-by-objectId lane (contacts) -------------------
#
# A genuine HubSpot private-app webhook event carries only objectId/objectType — no
# email/domain/name — so on the live path Build Identity produces an empty identity and
# every downstream lookup/provider call runs against nothing (see ENRICH_PARSE_EVENT_
# CLOUD's shim comment). This additive lane fetches the record BY id (native HubSpot
# search filtered on hs_object_id, never the node's single-record retrieval operation —
# RESEARCH: that operation still routes to HubSpot's sunset v1/legacy-v2 endpoints and
# returns a non-flat {value,timestamp} property shape) and backfills identity_keys from
# the fetched record, converging back into the EXISTING "Enrichment Gate" alongside the
# unmodified "Adapt Search" lane.
#
# Extracted verbatim from the existing "HubSpot Search" node (byte-identical emitted
# string) so the fetch-by-id property list can share it without drift.
# 260826-20w Task 2 commit 1: the five location properties MUST land in this same commit
# as the location candidates (normalizeProviders.js) — fill_blank_only decides from
# existingRecord, and a property that was never fetched here reads as blank regardless of
# what is actually stored live, silently turning non-clobber into clobber.
#
# Phase 66 Plan 01 Task 2 (T-66-02, upstream_corrections item 4): `lv_linkedin_url` and
# `lv_persona_group` added — the two remaining `config/field_policy.yaml` `contacts` keys
# that were never on this list. Both are `fill_blank_only`/`protect_if_current_present` in
# both that policy file and mergeContacts.js's DEFAULT_CONTACT_POLICY, and that protection
# is computed from existingRecord: a property this list omits reads blank, so the guard
# meant to protect a populated value would instead permit overwriting it — same defect
# class the location-properties comment above already names. Lands BEFORE Task 3's
# LinkedIn producer and REQUIRED widening so a produced candidate can never reach a merge
# with nothing real to compare against.
ENRICH_CONTACT_SEARCH_PROPERTIES_CSV = (
    "email,firstname,lastname,jobtitle,phone,"
    "mobilephone,hs_object_id,lv_jobtitle_verified_at,"
    "lv_mobilephone_verified_at,seniority,"
    "lv_contact_enrichment_provenance,lusha_contact_id,"
    "city,state,country,hs_state_code,hs_country_region_code,"
    "lv_linkedin_url,lv_persona_group"
)
# The fetch-by-id list adds `company` — HubSpot's default contact freetext-company
# property, feeding identity_keys.companyName on the backfill. `lv_linkedin_url` moved
# INTO the search CSV above (Phase 66 Plan 01 Task 2) and is deliberately NOT repeated
# here — the by-id list is the search list plus this suffix, and a name present in both
# halves would be requested twice. The existing search lane never needed `company`;
# deliberately NOT the broader CLAUDE.md §18.4 list (several of those properties do not
# exist in portal 22617666 and HubSpot silently drops unknown names).
#
# Phase 61 Plan 02 Task 1 (REVIEW-02): `hs_linkedin_url` added — HubSpot's own native
# LinkedIn property, confirmed present (hubspotDefined: true) in the committed live
# snapshot config/hubspot_migration/baseline/portal-schema-contacts-54-03-contacts-check.json.
# The linkedin search filters on BOTH properties; a hit returned on a property this list
# does not request is a hit the adapter's re-verification cannot read back — searching a
# property without requesting it reproduces the exact silent-zero-result shape this whole
# plan exists to remove. Additive to the fetch-by-id lane this CSV already feeds (HubSpot
# returns one more property; nothing there reads it).
ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV = (
    ENRICH_CONTACT_SEARCH_PROPERTIES_CSV + ",company,hs_linkedin_url"
)

ENRICH_ADAPT_FETCH_BY_ID_CONTACT = inline("adaptFetchById.js", "matchProposal.js") + r"""

// --- n8n wrapper: adapt "HubSpot Fetch By Id" -> existingRecord + backfilled identity_keys ---
// Phase 70 Plan 04 (D-70-04): "HubSpot Fetch By Id Carry Merge" (splice_carry_merge_after)
// re-attaches the pre-hop row (from "IF Bare Event"'s TRUE lane — the SAME delivery that
// fed "HubSpot Fetch By Id") onto the raw fetch response, row-fields-last. $input here is
// ALREADY the "fetch_by_id"-lane row alone, combined with its own fetch result — no
// by-name recovery of "Build Identity" or "HubSpot Fetch By Id" (D-70-01/D-70-03).
return $input.all().map((it) => {
  const merged = it.json;
  const { existingRecord, lookup_failed, fetch_diagnostic } = adaptFetchByIdResult({ json: merged });
  const identity_keys = backfillIdentityKeys(merged.object_type || "contacts", existingRecord, merged.identity_keys);
  // Phase 36 Plan 02: every lane stamps a `match` verdict, so a tier reaches the
  // response for every lane including this one.
  const match = summarizeMatch({ lane: "fetch_by_id", existingRecord, lookupFailed: lookup_failed });
  return { json: { ...merged, existingRecord, lookup_failed, fetch_diagnostic, identity_keys, match } };
});
"""

# ---- Phase 36 Plan 02, Task 2: the MEDIUM match-lane adapter -----------------
#
# Mirrors ENRICH_ADAPT_SEARCH's three-line opening + row-recovery idiom EXACTLY (same
# bd682a2 bug class — the pre-hop row is recovered BY NODE NAME, $json/$input are never
# read here). A MEDIUM candidate is a PROPOSAL, never an auto-match (36-CONTEXT.md §6:
# tier "medium" carries `auto: false`) — `existingRecord` stays the empty-object literal
# on EVERY path below, success included, so a fuzzy CONTAINS_TOKEN hit can never become
# an auto-matched update target. `auto: false` means the CALLER judges the candidate;
# writing it into `existingRecord` would hand the gate a confirmation it never received.
ENRICH_ADAPT_NAME_SEARCH = inline("matchProposal.js") + r"""

// --- n8n wrapper: adapt "HubSpot Name Search" (+ its fallback) -> match proposal (never
// existingRecord) ---
//
// F1 (2026-08-25, debug/walk-write-path-defects.md): the primary search filters
// lastname EQ AND company CONTAINS_TOKEN against the contact's `company` TEXT PROPERTY.
// A contact created by the ingest lane is associated to a company OBJECT and leaves that
// text property null — live-proven on contact 347569451461 / Football NSW, execution
// 11948: the primary search returned zero hits for a contact that genuinely exists, and
// the row fell through to a "create" attempt (blocked only because writes are off in
// this environment — armed, it would have DUPLICATED the record).
//
// "HubSpot Name Search Fallback" runs UNCONDITIONALLY for every "name"-lane row,
// SEQUENTIALLY after the primary search (never a parallel fan-out — a Code node reading
// an unexecuted node via $() throws), so item alignment stays 1:1 by row regardless of
// whether the primary search found anything. Its own filter drops the company clause
// entirely (lastname EQ only) — the weaker key the debug file's fix direction names.
// mediumCandidates({requireCompanyToken:false}) re-verifies lastname (and, when the row
// supplied one, firstname) instead of company token overlap, so a hit whose `company` is
// blank by construction is no longer filtered out. The result is still `tier: "medium"`
// / `auto: false` either way — a weaker search key surfaces MORE candidates for the
// caller to judge, never an auto-match (matchProposal.js summarizeMatch's own contract).
//
// Phase 70 Plan 04 (D-70-04): "HubSpot Name Search Carry Merge" + "Stash Name Primary
// Search" + "HubSpot Name Search Fallback Carry Merge" (mirrors 70-02's "Stash Domain
// Search" pattern) re-attach the row and stash the primary search's own response BEFORE
// the fallback HTTP hop replaces $json a second time. $input here is therefore ALREADY
// one item per "name"-lane row, carrying the primary search under `_name_primary_search`
// and the fallback search's own {results,error} flat — no by-name recovery of "Build
// Identity"/"HubSpot Name Search"/"HubSpot Name Search Fallback" (D-70-01/D-70-03).
function candidatesFrom(resLike, identityKeys, opts) {
  if (!resLike || resLike.error) return null;    // null = "could not look", not "found none"
  const results = Array.isArray(resLike.results) ? resLike.results : [];
  return mediumCandidates(results, identityKeys, opts);
}

return $input.all().map((it) => {
  const merged = it.json;
  const row = merged;
  const primaryCandidates = candidatesFrom(merged._name_primary_search, row.identity_keys, undefined);
  if (primaryCandidates === null) {
    const match = summarizeMatch({ lane: "name", lookupFailed: true });
    return { json: { ...row, existingRecord: {}, lookup_failed: true, match } };
  }

  // Only fall back when the primary (company-token-verified) search found nothing —
  // a primary hit is the stronger signal and is never discarded in favor of the weaker
  // key.
  let candidates = primaryCandidates;
  if (candidates.length === 0) {
    const fallbackCandidates = candidatesFrom(merged, row.identity_keys, { requireCompanyToken: false });
    if (fallbackCandidates !== null) candidates = fallbackCandidates;
  }

  const match = summarizeMatch({ lane: "name", existingRecord: {}, lookupFailed: false, candidates });
  return { json: { ...row, existingRecord: {}, lookup_failed: false, match } };
});
"""

# Stash Name Primary Search — Phase 70 Plan 04 (D-70-04). Sits between "HubSpot Name
# Search Carry Merge" and "HubSpot Name Search Fallback": nests the primary search's own
# {results,total,error} under `_name_primary_search` so the SECOND carry merge (after
# the fallback HTTP hop, which replaces $json a second time) can re-attach this stash
# flat alongside the fallback's own {results,error} without either search's response
# fields colliding with the other's. Mirrors 70-02's "Stash Domain Search" exactly.
ENRICH_STASH_NAME_PRIMARY_SEARCH = r"""// Stash Name Primary Search — see ENRICH_ADAPT_NAME_SEARCH's own comment.
return $input.all().map((it) => {
  const { results, total, error, ...row } = it.json;
  return { json: { ...row, _name_primary_search: { results, total, error } } };
});
"""

# ---- Phase 61 Plan 02, Task 1: the STRONG linkedin match lane (D-61-05 CORRECTED) -----
#
# D-61-05's research finding: `resolveIdentity.js:76-90`'s linkedin branch is real code
# nothing reaches on the live path — this lane is what makes it reachable. Mirrors
# ENRICH_ADAPT_SEARCH's row-recovery idiom (filter-then-index-align BEFORE reading the
# HTTP node, never $json directly) and REVIEW-02's re-verification requirement: a hit
# counts only when `linkedinAgreement` (matchProposal.js) — canonicalizing BOTH
# `lv_linkedin_url` and native `hs_linkedin_url` and requiring them to agree when both are
# present — equals the row's own canonicalized key. A self-disagreeing record (the two
# properties point at different profiles) is never a verified hit (T-61-05). Deduplicated
# by contact id inside verifiedLinkedinHits, so a contact matching under both properties
# is ONE hit. `inline("resolveIdentity.js", ...)` gives this wrapper `canonicalizeLinkedin`
# (matchProposal.js's own `require` of it is stripped by inline() — the definition must be
# concatenated into the same script for real).
ENRICH_ADAPT_LINKEDIN_SEARCH = inline("resolveIdentity.js", "matchProposal.js") + r"""

// --- n8n wrapper: adapt "HubSpot Linkedin Search" -> match proposal ---
// Phase 70 Plan 04 (D-70-04): "HubSpot Linkedin Search Carry Merge"
// (splice_carry_merge_after) re-attaches the pre-hop row (from "IF Linkedin
// Searchable"'s TRUE lane — the SAME delivery that fed "HubSpot Linkedin Search") onto
// the raw search response, row-fields-last. $input here is ALREADY the "linkedin"-lane
// row alone, combined with its own search result — no by-name recovery (D-70-01/D-70-03).
return $input.all().map((it) => {
  const merged = it.json;
  const failed = !!merged.error;
  if (failed) {
    const match = summarizeMatch({ lane: "linkedin", lookupFailed: true });
    return { json: { ...merged, existingRecord: {}, lookup_failed: true, match } };
  }
  const results = Array.isArray(merged.results) ? merged.results : [];
  const rawLinkedinUrl = (merged.identity_keys && merged.identity_keys.linkedin_url) || null;
  const verified = verifiedLinkedinHits(results, rawLinkedinUrl);
  // existingRecord is built from the verified hit ONLY on a single verified match — never
  // on 0 or >1, mirroring every other lane's "auto only means exactly one confirmed
  // record" contract (36-CONTEXT.md §6).
  let existingRecord = {};
  if (verified.length === 1) {
    existingRecord = { ...(verified[0].properties || {}), hs_object_id: verified[0].id };
  }
  const candidates = verified.map(toCandidateShape);
  const match = summarizeMatch({ lane: "linkedin", candidates, lookupFailed: false });
  return { json: { ...merged, existingRecord, lookup_failed: false, match } };
});
"""

# ---- Phase 16.4 Task 2: fetch-by-objectId lane (companies mirror) -----------
#
# Extracted from the existing "HubSpot Company Search" node. The companies fetch-by-id
# list is this SAME constant VERBATIM — Build Company Identity only needs `domain` and
# `name`, both already here (unlike contacts, which added 2 properties the existing
# search never needed).
#
# WR-01 (18-REVIEW.md, Phase 18 Plan 03): lv_sponsorship_reliant was omitted here even
# though it is a research fold field like its siblings — its policy class is
# system_owned (mergeCompanies.js:43), so the omission never caused incorrect
# promote/clobber behaviour, but it DID mean the merge decision's `current_value` audit
# field was always misreported as null for this one field. Feeds ONLY
# _hs_http_search_node HTTP nodes (never a Code node), so adding it moves zero frozen
# {variant, node} pairs — verified below by re-running the frozen guard after this edit.
#
# fix-40 VETO-01/02 live evidence run (2026-08-07): lv_country_region_normalized was ALSO
# omitted here, and unlike lv_sponsorship_reliant this one is NOT audit-cosmetic —
# ENRICH_DECIDE_CO_CLOUD's veto derivation reads `existing.lv_country_region_normalized`
# directly (never through mergeCompanies' policy gate) as its fallback when no candidate
# this run re-promotes the field. With the property absent from BOTH HTTP fetch nodes this
# CSV feeds ("HubSpot Company Search" domain-match AND "HubSpot Company Fetch By Id"
# bare-objectId lanes — see the two `properties_csv=ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`
# call sites below), `existing.lv_country_region_normalized` was `undefined` on every run
# that didn't freshly re-promote region, so `_regionKey(undefined)` -> "non_anz" fired a
# spurious "Non-ANZ geography" veto on true-AU/NZ companies. Live-caught: two AU disposable
# companies (region set directly via the HubSpot API, never touched by this run's
# research/waterfall candidates, both matched:false) received "Non-ANZ geography" appended
# to their correct no-content/hardware-vendor reasons. Same class of defect WR-01 already
# fixed for lv_sponsorship_reliant, one property short of covering it.
#
# debug: blank-region-fires-non-anz-veto (2026-08-10) — this CSV fix only covers the
# transient "region was set but this run didn't fetch it" case. A company whose region has
# GENUINELY never been enriched still resolves to `undefined`/`null` here even with the
# fixed CSV, and `_regionKey` now treats that as "unknown" (no veto), not "non_anz" — see
# the `_regionKey` definition in ENRICH_DECIDE_CO_CLOUD above.
# 58-05 Task 1/2: `country`/`city` added -- without them here the fetch returns no
# current value for the two new native candidates, the non-clobber comparison in
# mergeCompanies sees `undefined` instead of a real existing value, and the fill_blank_only
# guard that is supposed to protect a populated field silently permits overwriting it
# (same class of defect WR-01/VETO-01 already fixed for lv_sponsorship_reliant/
# lv_country_region_normalized above). `numberofemployees` was already present.
# Phase 62 Plan 04 (D-62-16): num_associated_contacts appended — a native, read-only
# HubSpot rollup (confirmed present in every committed portal-schema baseline), never
# a write. This is the property list build_enrichment_cloud() ACTUALLY feeds its
# "HubSpot Company Search" and "HubSpot Company Fetch By Id" nodes (HS_CO_SEARCH_BODY_EXPR
# above is a separate constant, used by build_enrichment_local_live() only).
#
# Phase 66 Plan 02 Task 2 (D-66-01 companies half): lv_revenue_band/lv_employee_band
# appended — both newly REQUIRED by ENRICH_CO_GATE above (66-COVERAGE.md's derivation),
# and same class of defect WR-01/VETO-01/58-05 already fixed here twice: a property
# omitted from this CSV reads as absent on existingRecord, which both makes the gate
# report it permanently missing AND turns mergeCompanies' non-clobber comparison into a
# silent permit to overwrite a populated value.
ENRICH_COMPANY_SEARCH_PROPERTIES_CSV = (
    "name,domain,industry,annualrevenue,"
    "numberofemployees,hs_object_id,lv_org_type,"
    "lv_produces_content,lv_content_type,lv_sponsorship_reliant,"
    "lv_is_hardware_vendor,lv_is_gambling_operator,"
    "lv_country_region_normalized,country,city,"
    "lv_revenue_band,lv_employee_band,"
    "lv_enrichment_provenance,lv_org_type_verified_at,"
    "lv_produces_content_verified_at,lusha_company_id,"
    "num_associated_contacts"
)

ENRICH_ADAPT_FETCH_BY_ID_COMPANY = inline("adaptFetchById.js") + r"""

// --- n8n wrapper: adapt "HubSpot Company Fetch By Id" -> existingRecord + backfilled identity_keys ---
// Phase 70 Plan 04 (D-70-04): "HubSpot Company Fetch By Id Carry Merge" (splice_carry_
// merge_after, carry_source "IF Company Bare Event" TRUE lane) re-attaches the pre-hop
// row onto the raw fetch response, row-fields-last. $input here is ALREADY that combined
// item — no by-name recovery of "Build Company Identity"/"HubSpot Company Fetch By Id"
// (D-70-01/D-70-03).
return $input.all().map((it) => {
  const merged = it.json;
  const { existingRecord, lookup_failed, fetch_diagnostic } = adaptFetchByIdResult({ json: merged });
  const identity_keys = backfillIdentityKeys("companies", existingRecord, merged.identity_keys);
  return { json: { ...merged, existingRecord, lookup_failed, fetch_diagnostic, identity_keys } };
});
"""

# ---- Phase 36-03 Task 2: two terminal markers become row-carrying Code nodes ----------
#
# Both were n8n-nodes-base.set (typeVersion 3.4). A Set v3.4 emits ONLY its assigned key
# (BUG 12's class — see ENRICH_SET_DQ_JS above, the precedent this mirrors), so a
# HIGH-matched fresh row terminating at either one would return an uncorrelatable reply
# with no `row_id` — and `row_id` is the join key here, because `event_id` is meaningless
# for an id-less row (36-CONTEXT.md sec7 step 5). Node NAMES stay identical so every
# connection edge and NODE_CREDENTIAL_MAP key still resolves; only the type/parameters
# change. Their tests/test_row_carry.py ROW_REPLACING_BY_DESIGN waivers are retired in the
# SAME commit as this change (test_every_row_replacing_entry_is_still_a_real_node_
# somewhere fails on a stale waiver naming a node that is no longer a Set node anywhere).
ENRICH_UNSUPPORTED_OBJECT_TYPE_JS = r"""// Unsupported Object Type — row-carrying terminal marker.
// Was a Set node (BUG 12 class): spreads the row so a caller's row_id survives to Build
// Response instead of being silently dropped.
return $input.all().map((it) => ({
  json: { ...it.json, object_type: "unsupported" },
}));
"""

ENRICH_SKIP_NOOP_JS = r"""// Skip (NoOp) — row-carrying terminal marker.
// Was a Set node (BUG 12 class): spreads the row so a HIGH-matched fresh row that gets
// skipped here still returns a correlatable reply carrying row_id.
return $input.all().map((it) => ({
  json: { ...it.json, action: "skip" },
}));
"""


def build_enrichment_cloud():
    nodes = []
    y = 300
    x = 220

    # Task 6 (review #7, CLAUDE.md §18.1): native Header Auth — n8n rejects the request
    # before any node runs if X-Enrichment-Secret doesn't match the bound credential's
    # value. No Code node ever reads the secret value, and no $env/$vars expression is
    # used (Criterion 5's zero-env-var guard covers the whole built workflow).
    # Phase 16.1 Plan 02 (reviews C3): responseNode + "Respond to Webhook", fed by the
    # "Build Response" convergence (every terminal + remaining_credits, below). Per-batch
    # FIRST-ARRIVAL semantics — not hard determinism (see Build Response's own comment).
    webhook = {
        "parameters": {"httpMethod": "POST", "path": "hubspot/enrichment/event",
                       "responseMode": "responseNode", "authentication": "headerAuth", "options": {}},
        "id": nid("w"), "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [x, y],
    }
    nodes.append(webhook)

    # WINDOWS.md #3 / fix(40): a SECOND entry point, additive — n8n's "Execute Workflow"
    # (call another workflow) mode requires the CALLED workflow to expose an Execute
    # Workflow Trigger node; this workflow's only entry point used to be the Webhook
    # Trigger above, so SJ-3's dispatch (an executeWorkflow node in "each" mode, see
    # _execute_workflow_node) errored live with "Missing node to start execution"
    # (n8n executions 1891/1893, 40-03-SUMMARY.md). "passthrough" means each dispatched
    # item's json arrives here UNCHANGED — Parse HubSpot Event already reads
    # `$json.body ?? $json`, so a bare event-shaped item (no `.body` wrapper) parses
    # identically to a genuine webhook body. Feeds "Parse HubSpot Event" directly,
    # bypassing the list-resolution branch below (SJ-3 dispatches single-record events,
    # never a `{list:...}` envelope).
    nodes.append({
        "parameters": {"inputSource": "passthrough"},
        "id": nid("ewt"), "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger", "typeVersion": 1.1,
        "position": [x, y - 260],
    })

    # --- Phase 25 Plan 03: additive list-resolution branch (INGEST-04, D-01/D-02/D-15) ---
    # Sits BETWEEN the trigger and Parse HubSpot Event. `IF List Input` is true only for a
    # body that carries a `list` or `view` key AND no `events` array; every other body —
    # a record-ID envelope, a bare HubSpot event array, a single bare event object — takes
    # the false lane, which is the exact edge the trigger had before this branch existed.
    ly = y - 300
    lx = 330
    nodes.append(_if_bool_expr_node(
        "IF List Input",
        '!Array.isArray(($json.body || $json).events) '
        '&& ((($json.body || $json).list != null) || (($json.body || $json).view != null))',
        lx, ly))
    lx += 220
    # Credential-bound GETs built with the SHARED httpRequest helper in its predefined
    # HubSpot credential mode — the same provisioned "LV HubSpot" credential every other
    # HubSpot node in this workflow uses. A Code node cannot hold that credential, and the
    # whole workflow is guarded against $env/$vars.
    # onError stays continueRegularOutput (the helper default): a 401/403/404 must arrive at
    # the expansion node as an unreadable response it can REFUSE in plain language, not as a
    # thrown execution that returns 500 with no explanation.
    nodes.append(_http_node("HubSpot List By Name", ENRICH_LIST_BY_NAME_URL, lx, ly,
                            auth="hubspot", method="GET"))
    lx += 220
    # Phase 70 Plan 04 (D-70-04): nests the raw List-By-Name response under a distinct key
    # before it crosses the SECOND HTTP hop below — same "Wrap ... Result" precedent the
    # provider waterfall uses, needed because "Expand List To Events" must see this response
    # AND the Memberships response AND the original trigger body all at once.
    nodes.append(code_node("Wrap List By Name Result",
                            _wrap_provider_result_js("list_by_name_result"), lx, ly))
    lx += 220
    nodes.append(_http_node("HubSpot List Memberships", ENRICH_LIST_MEMBERSHIPS_URL, lx, ly,
                            auth="hubspot", method="GET"))
    lx += 220
    nodes.append(code_node("Expand List To Events", ENRICH_EXPAND_LIST_TO_EVENTS, lx, ly))
    lx += 220
    # Gates on the EVENTS THEMSELVES rather than on a status flag: a refusal carries
    # `events: []`, and so would a regressed expansion node that refused and expanded at the
    # same time. Zero events therefore can never reach the enrichment chain — which also
    # closes D-22 (zero items into a responseNode webhook = no response at all, and a ~100s
    # hang until Cloudflare 524s).
    nodes.append(_if_bool_expr_node(
        "IF List Expanded",
        "Array.isArray($json.events) && $json.events.length > 0", lx, ly))

    x += 220
    nodes.append(code_node("Parse HubSpot Event", ENRICH_PARSE_EVENT_CLOUD, x, y))
    # Phase 61 Plan 05 Task 2 — a third, unconditional fan target off "Parse HubSpot
    # Event" (not a re-point). Phase 70 Plan 03 Task 2 (D-70-07): renamed "Build Ack" —
    # see ENRICH_BUILD_ACK's own comment above — and gains a SECOND inbound edge below
    # (from "IF List Expanded" false).
    nodes.append(code_node("Build Ack", ENRICH_BUILD_ACK, x, y + 260))
    # Phase 70 Plan 03 Task 2 (D-70-07): the shared refusal/status-row normalizer, fed by
    # "IF List Expanded" false and "Build Scale Up Ack" below — see
    # ENRICH_BUILD_REFUSAL_ROW's own comment above.
    nodes.append(code_node("Build Refusal Row", ENRICH_BUILD_REFUSAL_ROW, x, y + 380))

    # Phase 61 Plan 06 Task 5 (T-61-25, substrate-3 scale-up, off by default). Spliced
    # BETWEEN "Parse HubSpot Event" and "IF Object Type Supported" — the ONE edge this
    # task re-points (disclosed exactly like Task 2's `Adapt Company Create` splice) —
    # rather than added as a further unconditional fan target: a fanned row must NOT
    # ALSO run the main business chain in the parent, or an armed request would write
    # twice. TRUE (is fanning: `_SCALE_UP_IS_FANNING_EXPR`) routes to the fan-out lane
    # below; FALSE (every request that never opts in, the overwhelming default) routes to
    # "IF Object Type Supported" exactly as before — functionally byte-identical, one
    # additional pass-through hop.
    nodes.append(_if_bool_expr_node(
        "IF Scale Up Route", _SCALE_UP_IS_FANNING_EXPR, x, y - 260))
    x += 220
    nodes.append(code_node(
        "Build Scale Up Fan-Out", ENRICH_BUILD_SCALE_UP_FAN_OUT, x, y - 260))
    x += 220
    # Self-reference: "LVenrichmentCloud01"/"LV Enrichment (Cloud template)" is THIS
    # workflow's own local id/name (see this function's own final `return` below).
    # `rebind_subworkflow_refs` (scripts/deploy_n8n_workflows.py) resolves any
    # executeWorkflow node's `cachedResultName` against a fresh live name->id map at
    # deploy time — this workflow already exists live (61-05's substrate-1 deploy), so
    # its own name already resolves to its own live id with NO special-casing, the exact
    # mechanism SJ-3's cross-workflow dispatch already proves. `wait_for_sub=False` bakes
    # the detached shape 61-PREMISE-PROBE-VERDICT.json's P-13 measured live.
    nodes.append(_execute_workflow_node(
        "Dispatch Self", x, y - 260,
        "LVenrichmentCloud01", "LV Enrichment (Cloud template)", wait_for_sub=False))
    x += 220
    nodes.append(code_node("Build Scale Up Ack", ENRICH_BUILD_SCALE_UP_ACK, x, y - 260))
    x -= 660  # restore x: the fan-out lane is a side branch, not the main chain's spine

    # Phase 16.1 (reviews A2): an explicit unsupported-object-type check BEFORE the
    # existing companies/contacts router — a malformed/unknown object_type terminates in
    # a no-op here, so it can never fall through into a provider branch and burn credits
    # with providers:"all". "Route By Object Type" below is UNCHANGED (still the existing
    # 2-way companies/contacts IF — tests/test_cloud_write_path.py pins its exact shape);
    # this is the "IF + explicit unsupported check" form the plan sanctions as an
    # alternative to a 3-way Switch.
    x += 220
    if_object_type_supported = _if_not_equal_node(
        "IF Object Type Supported", "object_type", "unknown", x, y)
    nodes.append(if_object_type_supported)
    nodes.append(code_node(
        "Unsupported Object Type", ENRICH_UNSUPPORTED_OBJECT_TYPE_JS, x, y + 260))

    x += 220
    route_by_type = {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ $json.object_type }}",
                "rightValue": "companies",
                "operator": {"type": "string", "operation": "equals"},
            }],
        }},
        "id": nid("if"), "name": "Route By Object Type",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }
    nodes.append(route_by_type)

    x += 220
    build_identity_x = x
    nodes.append(code_node("Build Identity", ENRICH_BUILD_IDENTITY, x, y))

    # Task 6 (review #8): real filterGroups (email EQ) + hs_object_id in the property
    # list — was an empty filterGroupsUi placeholder that matched no filter at all.
    # BUG 23 (Phase 17.01): moved off the native node onto _hs_http_search_node — see that
    # helper's docstring for why (zero hits -> zero items -> chain stops, execution 22).
    x += 220
    hs_search_x = x
    hs_search = _hs_http_search_node(
        "HubSpot Search", "contact", x, y,
        filter_groups=[[{"propertyName": "email", "operator": "EQ",
                          "value": "={{ $json.identity_keys.email }}"}]],
        properties_csv=ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
    )
    nodes.append(hs_search)

    x += 220
    adapt_search_x = x
    nodes.append(code_node("Adapt Search", ENRICH_ADAPT_SEARCH, x, y))
    x += 220
    nodes.append(code_node("Enrichment Gate", ENRICH_GATE, x, y))

    # Phase 16.4 Task 1: fetch-by-objectId lane — additive SECOND inbound edge into
    # "Enrichment Gate", on a free row below the main row so none of the four existing
    # nodes above move `position` (RESEARCH: the gate sits AFTER the identity builder,
    # never before — moving it earlier would break tests/test_cloud_write_path.py's
    # pinned "Route By Object Type" edges).
    fby = y + 200
    if_bare_event = _if_bool_expr_node(
        "IF Bare Event",
        # Phase 70 Plan 04 Task 2 (D-70-03): bare $json — fed directly by "Build
        # Identity" (a Code node, never an HTTP node), so $json IS its own row.
        "!!$json.object_id && "
        "!$json.identity_keys.email",
        build_identity_x, fby,
    )
    # Conservative by construction: true ONLY when we have an id to fetch AND the
    # existing lane has no key to search on. Any payload the existing lane could handle
    # (a direct-field/caller-envelope test payload carrying an email) keeps the existing
    # lane byte-for-byte; a payload with neither an id nor a key also keeps it.
    nodes.append(if_bare_event)
    # BUG 23 (Phase 17.01): moved off _hs_search_node onto _hs_http_search_node — same
    # zero-items-on-zero-hits hazard as the sibling search above (a deleted/nonexistent
    # object id must not silently die here; adaptFetchById.js's 0-result branch needs the
    # response to arrive as an item to classify it as lookup_failed).
    hs_fetch_by_id = _hs_http_search_node(
        "HubSpot Fetch By Id", "contact", hs_search_x, fby,
        # Phase 70 Plan 04 (D-70-04): bare $json — "IF Bare Event" is a routing IF, never
        # an HTTP node, so $json here IS "Build Identity"'s own row untouched.
        filter_groups=[[{"propertyName": "hs_object_id", "operator": "EQ",
                          "value": "={{ $json.object_id }}"}]],
        properties_csv=ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
    )
    # POSTs directly to CRM v3 /crm/v3/objects/contacts/search — never the node's
    # single-record retrieval operation: n8n's V2 HubSpot node implementation still routes
    # single-record retrieval to HubSpot's sunset /contacts/v1/... endpoint, which returns
    # properties as {value, timestamp, ...} objects rather than the flat map every consumer
    # downstream in this pipeline assumes — a silent corruption of every field it touches.
    nodes.append(hs_fetch_by_id)
    nodes.append(code_node(
        "Adapt Fetch By Id", ENRICH_ADAPT_FETCH_BY_ID_CONTACT, adapt_search_x, fby))

    # Phase 36 Plan 02 (36-CONTEXT.md §7 step 3): the MEDIUM match lane — a row with a
    # surname and a company but no email (the common case for a board-page/roster extract
    # with no contact emails at all). Additive THIRD row below the fetch-by-id row above,
    # so none of the existing nodes move `position`. Only "IF Bare Event"'s FALSE edge
    # re-points, to "IF Has Email" below — its TRUE edge (-> "HubSpot Fetch By Id") is
    # untouched, and the companies branch's "IF Company Bare Event" is left alone entirely
    # (36-CONTEXT.md's wire contract and build plan describe contacts only).
    mby = fby + 200
    if_has_email = _if_bool_expr_node(
        "IF Has Email",
        # Routes on the SAME `lane` field "Build Identity" stamped (Plan 01's laneOf) —
        # never a re-derived predicate. Two spellings of one routing decision is how a row
        # gets routed to one lane and filtered into another (36-CONTEXT.md key_links).
        # Phase 70 Plan 04 Task 2 (D-70-03): bare $json — fed by "IF Bare Event"'s FALSE
        # lane, a routing IF never an HTTP node, so $json IS "Build Identity"'s own row.
        '$json.lane === "email"',
        build_identity_x, mby,
    )
    nodes.append(if_has_email)
    if_name_searchable = _if_bool_expr_node(
        "IF Name Searchable",
        '$json.lane === "name"',
        build_identity_x + 220, mby,
    )
    nodes.append(if_name_searchable)
    # lastname EQ + company CONTAINS_TOKEN, ANDed in one filter group (both must match).
    # CONTAINS_TOKEN, never the bare "CONTAINS": HubSpot CRM v3's string-operator
    # vocabulary is closed (EQ/NEQ/LT/LTE/GT/GTE/BETWEEN/IN/NOT_IN/HAS_PROPERTY/
    # NOT_HAS_PROPERTY/CONTAINS_TOKEN/NOT_CONTAINS_TOKEN) and does not define a bare
    # substring-match operator — using it would be a guaranteed 400 that only surfaces
    # against the live tenant. This operator choice is [ASSUMED] offline (36-RESEARCH.md
    # §B.2 / Assumption A1: no in-repo HubSpot search-operator contract doc exists, unlike
    # docs/LUSHA-V3-CONTRACT.md) — the offline proof here is structural (this builder
    # emits CONTAINS_TOKEN and never the bare form, asserted by this plan's tests); the
    # semantic proof is the first live propose run, alongside the Lusha-widening canary.
    # properties_csv is the FETCH-BY-ID list, not the plain search list: mediumCandidates
    # re-verifies a hit against `company`, which the plain search CSV omits.
    hs_name_search = _hs_http_search_node(
        "HubSpot Name Search", "contact", hs_search_x, mby,
        filter_groups=[[
            {"propertyName": "lastname", "operator": "EQ",
             "value": "={{ $json.identity_keys.lastName }}"},
            {"propertyName": "company", "operator": "CONTAINS_TOKEN",
             "value": "={{ $json.identity_keys.companyName }}"},
        ]],
        properties_csv=ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
    )
    nodes.append(hs_name_search)
    # Phase 70 Plan 04 (D-70-04): sits between "HubSpot Name Search Carry Merge" (below)
    # and "HubSpot Name Search Fallback" — see ENRICH_STASH_NAME_PRIMARY_SEARCH's comment.
    nodes.append(code_node(
        "Stash Name Primary Search", ENRICH_STASH_NAME_PRIMARY_SEARCH, hs_search_x + 55, mby - 50))

    # F1 (2026-08-25, debug/walk-write-path-defects.md): runs UNCONDITIONALLY for every
    # "name"-lane row, SEQUENTIALLY after "HubSpot Name Search" — never a parallel
    # fan-out (a Code node reading an unexecuted node via $() throws) — so item alignment
    # stays 1:1 by row whether or not the primary search found anything. Drops the
    # company CONTAINS_TOKEN clause entirely (lastname EQ only): the weaker key the debug
    # file's fix direction names, re-verified in ENRICH_ADAPT_NAME_SEARCH by
    # mediumCandidates({requireCompanyToken:false}) rather than loosened at the HubSpot
    # filter itself. Phase 70 Plan 04 (D-70-04): its filter value reads bare $json
    # directly — "HubSpot Name Search Carry Merge" + "Stash Name Primary Search" (below)
    # re-attach the pre-hop row before this node ever runs, so $json IS that row (never a
    # by-name lookup of "Build Identity").
    hs_name_search_fallback = _hs_http_search_node(
        "HubSpot Name Search Fallback", "contact", hs_search_x + 110, mby - 100,
        filter_groups=[[
            {"propertyName": "lastname", "operator": "EQ",
             "value": "={{ $json.identity_keys.lastName }}"},
        ]],
        properties_csv=ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
    )
    nodes.append(hs_name_search_fallback)
    nodes.append(code_node("Adapt Name Search", ENRICH_ADAPT_NAME_SEARCH, adapt_search_x, mby))

    # Phase 61 Plan 02 Task 1 (D-61-05 CORRECTED): the STRONG linkedin match lane, spliced
    # between "IF Has Email" and "IF Name Searchable" — additive FOURTH row below the name
    # lane above, so none of the existing nodes move `position`. Only "IF Has Email"'s
    # FALSE edge re-points (was "IF Name Searchable" directly; now "IF Linkedin Searchable"
    # first) — its TRUE edge is untouched, and "IF Linkedin Searchable"'s own false edge
    # re-points to "IF Name Searchable", which keeps that node's own true/false targets
    # byte-identical to what they are today.
    lby = mby + 200
    if_linkedin_searchable = _if_bool_expr_node(
        "IF Linkedin Searchable",
        '$json.lane === "linkedin"',
        build_identity_x, lby,
    )
    nodes.append(if_linkedin_searchable)
    # REVIEW-02: filter groups for BOTH `lv_linkedin_url` and native `hs_linkedin_url`
    # (HubSpot ORs across groups) — a contact whose LinkedIn lives only under the native
    # property must be found, never missed into a duplicate create. "Adapt Linkedin
    # Search" re-verifies whichever property carried the hit; searching a property this
    # node does not request would make that re-verification impossible (properties_csv is
    # the fetch-by-id list, which Task 1 already extended with `hs_linkedin_url`).
    #
    # Task 2 (61-02, REVIEW-01/REVIEW-C5): EQ-on-a-single-value survives nothing —
    # `canonicalizeLinkedin` output need not equal a raw stored value at all. The filter is
    # `IN` over `identity_keys.linkedin_url_variants` — the WRITTEN-DOWN, bounded variant
    # set "Build Identity" computes (see `linkedinUrlVariants`'s own comment there): the
    # canonicalized host+path crossed with {https,http} x {no-www.,www.} x
    # {no-slash,trailing-slash}, plus the raw operator-supplied value as given — up to 9
    # variants. `IN` is in HubSpot CRM v3's closed string-operator vocabulary (same
    # vocabulary the `name` lane's own comment records at the "HubSpot Name Search" node
    # above) and is provable offline, unlike `CONTAINS_TOKEN`'s tokenization behavior on a
    # URL-valued property (recorded [unknown] below). This is ONE `IN` group per property —
    # TWO filter groups total, a CONSTANT regardless of how the variant set grows, never a
    # variant x property cross-product (REVIEW-C5's bound). A stored form outside this
    # variant set is a KNOWN search miss reporting tier `none` ("we searched and did not
    # find") — never guessed, and never written to.
    #
    # [unknown], recorded rather than adopted: whether `CONTAINS_TOKEN` would additionally
    # catch a stored value with more query-string noise than this set covers. Settle with a
    # read-only admin search POST against a known contact's `lv_linkedin_url` before
    # adopting it — not on this plan's evidence.
    hs_linkedin_search = _hs_http_search_node(
        "HubSpot Linkedin Search", "contact", hs_search_x, lby,
        filter_groups=[
            [{"propertyName": "lv_linkedin_url", "operator": "IN",
              "values": "={{ $json.linkedin_url_variants }}"}],
            [{"propertyName": "hs_linkedin_url", "operator": "IN",
              "values": "={{ $json.linkedin_url_variants }}"}],
        ],
        properties_csv=ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
    )
    nodes.append(hs_linkedin_search)
    nodes.append(code_node("Adapt Linkedin Search", ENRICH_ADAPT_LINKEDIN_SEARCH, adapt_search_x, lby))

    # Phase 16.1 (reviews A1): a SINGLE `action != "skip"` dispatch lane feeds the
    # provider gate chain — replaces the old Route Action switch, whose create+enrich
    # outputs BOTH fed the waterfall entry directly, double-executing the gate chain +
    # Normalize + Score for a mixed create/enrich batch (double credit burn). The
    # create-vs-enrich WRITE decision is UNCHANGED and stays downstream at
    # Decide Action -> IF Create / IF Enrich, reading each row's own `action` field
    # (carried through every hop via `...row` spreads). `_route_action_switch` itself is
    # left in place (a generic helper, unused here now) in case another builder needs it.
    x += 220
    nodes.append(_if_not_equal_node("IF Provider Processing Needed", "action", "skip", x, y))
    nodes.append(code_node("Skip (NoOp)", ENRICH_SKIP_NOOP_JS, x, y + 160))

    # Provider waterfall (Phase 16.1: gated — each provider sits behind its own
    # `IF <provider> Enabled` gate with a bypass that rejoins the chain, emitted by the
    # SHARED `_provider_gate_bypass_chain(...)` helper — CONTEXT Locked Decision 8, the
    # reuse seam Task 2 calls identically for companies). A disabled provider's node never
    # executes (SC-2); the row spine always continues through the bypass so
    # Normalize + Score fires exactly once, even on the none/absent path. Apollo phone is
    # async (webhook) in prod. Auth differs per provider: Lusha + Apollo = single static
    # header key (generic Header Auth credential); ZoomInfo = split-code-node (Phase 16) —
    # a credential-bound Basic-auth "ZoomInfo Mint" HTTP node does the mint; the Token
    # Gate/Cache Code nodes are secret-free. (n8n Cloud blocks $env/$vars and Code nodes
    # cannot read credentials — see below.)
    px = x + 220
    # Phase 16.1: identity is read BY NODE NAME from "Enrichment Gate" (never bare $json),
    # because a provider gate positioned after another provider's HTTP node sees THAT
    # provider's response as $json, not the row — closing the latent identity-loss bug.
    #
    # v3 contract (docs/LUSHA-V3-CONTRACT.md §3, live-confirmed 2026-07-30): POST
    # /v3/contacts/search-and-enrich, body {"contacts":[{...}]} — a contacts ARRAY, each
    # element a PLAIN identity object with NO synthetic index key (v3 rejects a v2-style
    # `contactId` outright: 400 "property contactId should not exist"). `reveal` is a
    # top-level array of field-name strings (confirmed values: "emails", "phones"),
    # derived here from the Enrichment Gate's `missingFields` via the same fixed
    # email->emails/mobilephone->phones allow-list n8n/code/lushaRequest.js's
    # lushaReveal() encodes (T-20-02 mitigation: only these two literal names can ever
    # reach the request) — PII-minimization hygiene per the re-scoped
    # REQ-lusha-selective-reveal (§6: reveal-field-count does NOT change billed cost, so
    # this is never send a broader reveal than the gate asked for, not a cost control).
    # An empty reveal is an invalid v3 request (§6: 400 "reveal must contain at least 1
    # elements"), so this defaults to ["emails"] when nothing is missing.
    #
    # n8n expressions cannot require() a module, so this stays a hand-written mirror of
    # lushaContactBody()/lushaReveal() rather than sharing the module directly — Task 3's
    # anti-drift parity test in tests/n8n/lushaRequestContract.test.mjs asserts this
    # expression's output deep-equals the shared module's for a matrix of inputs, which
    # is what keeps the two from silently diverging.
    #
    # History (SUPERSEDED — reversed 2026-08-05 for Phase 36, see below): this CLOUD node
    # used to deliberately keep sending the NARROW identity set (email + linkedinUrl
    # only), live-confirmed for it pre-migration against the retired v2 endpoint
    # (firstName/lastName/companyName/companyDomain/domain/phoneNumber/jobTitle all
    # 400'd there). The LOCAL-LIVE builder and the dry-run harness sent the broader
    # name+company set they already sent, and that split predated this migration and was
    # carried forward deliberately, not silently unified.
    #
    # Reversal (36-CONTEXT.md §4 decision 3): docs/LUSHA-V3-CONTRACT.md §3 confirms v3
    # accepts the full six-key identity set on THIS endpoint (search-and-enrich) — the
    # narrow set was never a v3 constraint, only a carried-forward v2 scar. The
    # LOCAL-LIVE builder already sends the broad set today, so this node was the one
    # outlier. v3 bills roughly one flat credit per contact regardless of how many
    # identity fields are sent (docs/LUSHA-V3-CONTRACT.md §7), so the wider identity
    # costs nothing extra. Reversed because the whole point of the propose lane
    # (Phase 36) is a row that has a name and a company and no email — the case this
    # narrow set silently dropped. The expression below is still a hand-written mirror
    # of the module, not a require() of it — n8n expressions cannot import a module —
    # and tests/n8n/lushaRequestContract.test.mjs is still the only thing keeping them
    # equal; its parity matrix now covers the widened field set.
    # Plan 04 Task 2b: when the row's existingRecord already carries a stored
    # lusha_contact_id, the CONFIRMED-FREE stored-id path takes over — POST
    # /v3/contacts/enrich, body {ids:[storedId], reveal} (§8.1: a genuinely different
    # endpoint; /contacts/enrich REJECTS a `contacts` key entirely, "property contacts
    # should not exist"). Both the URL and the body expressions below branch on the SAME
    # storedId check so they can never disagree about which lane a given row takes.
    lusha = _http_node(
        "Lusha Enrich",
        "={{ $json.existingRecord && "
        "$json.existingRecord.lusha_contact_id ? "
        "'https://api.lusha.com/v3/contacts/enrich' : "
        "'https://api.lusha.com/v3/contacts/search-and-enrich' }}",
        px, y - 80,
        auth="header",  # credential header, e.g. api_key: <LUSHA_API_KEY>
        json_body=(
            "={{ (() => { "
            "const id = $json.identity_keys || {}; "
            "const gate = $json.gate || {}; "
            "const missing = gate.missingFields || []; "
            # D-66-01/RICH-01: landline `phone` added, mapping to the SAME reveal value
            # `mobilephone` maps to (mirrors n8n/code/lushaRequest.js's LUSHA_REVEAL_BY_FIELD —
            # both copies move together in one commit, T-20-02/anti-drift parity). Lusha bills
            # flat per contact regardless of reveal-field count (docs/LUSHA-V3-CONTRACT.md §6),
            # so widening this map costs nothing extra per call.
            "const REVEAL_MAP = { email: 'emails', mobilephone: 'phones', phone: 'phones' }; "
            # BUG (live, execution 11934, 2026-08-25): `Object.prototype` in an n8n EXPRESSION is
            # refused by the expression sandbox — "Cannot access \"prototype\" due to security
            # concerns" — and `onError: continueRegularOutput` turned that refusal into a
            # normal-looking item, so EVERY contact run since b7428af (2026-07-30) lost Lusha
            # silently. The Code nodes that use Object.prototype run in a different sandbox and
            # are unaffected; this was the only expression in any deployed workflow touching it.
            # Plain lookup is sandbox-safe and equivalent here: REVEAL_MAP is an object literal
            # declared one line above, so no inherited key can shadow a miss.
            # T-66-03: mobilephone and phone now both map to 'phones' — de-duplicated with a
            # Set (never a prototype lookup) so a duplicate can never reach the provider body.
            "const revealed = [...new Set(missing.filter((f) => REVEAL_MAP[f] !== undefined).map((f) => REVEAL_MAP[f]))].sort(); "
            "const reveal = revealed.length ? revealed : ['emails']; "
            "const existingRecord = $json.existingRecord || {}; "
            "const storedId = existingRecord.lusha_contact_id; "
            "if (storedId) { return JSON.stringify({ ids: [storedId], reveal }); } "
            "const c = {}; "
            "if (id.email) c.email = id.email; "
            "if (id.linkedin_url) c.linkedinUrl = id.linkedin_url; "
            "if (id.firstName) c.firstName = id.firstName; "
            "if (id.lastName) c.lastName = id.lastName; "
            "if (id.companyName) c.companyName = id.companyName; "
            "if (id.domain) c.companyDomain = id.domain; "
            "const hasIdentity = Object.keys(c).length > 0; "
            "return JSON.stringify(hasIdentity ? { contacts: [c], reveal } : { contacts: [] }); "
            "})() }}"
        ))
    nodes.append(lusha)
    # Phase 70 Plan 04 (D-70-04): nests Lusha's raw response under `lusha_result` before
    # the carry merge re-attaches the row — see _wrap_provider_result_js's docstring.
    nodes.append(code_node("Wrap Lusha Result", _wrap_provider_result_js("lusha_result"),
                           px + 55, y - 40))
    # RICH-06 cost verification (D-66-01, structural — no live call needed): chasing the
    # landline changes NO provider's per-call cost.
    #   - Lusha: bills flat per contact regardless of reveal-field count
    #     (docs/LUSHA-V3-CONTRACT.md §6, the selective-reveal cost lever is REFUTED there) —
    #     the widened REVEAL_MAP above rides the existing flat bill.
    #   - ZoomInfo: ZOOM_OUTPUT_FIELDS (this file, contacts branch) already lists BOTH
    #     "phone" and "mobilePhone" — both phone fields ride a request already paid for;
    #     no output-field list change needed or made.
    #   - Apollo: the body below is identity plus one reveal flag (reveal_personal_emails)
    #     with NO per-field ask at all, so its per-call cost is unchanged by construction,
    #     not by generalising from the other two providers.
    # reveal_personal_emails=true forces Apollo to return the contactable email (a bare
    # people/match returns identity only). Phone is async: reveal_phone_number needs a
    # webhook_url and arrives via callback — wired separately, not in this synchronous node.
    apollo = _http_node("Apollo Match", "https://api.apollo.io/v1/people/match", px + 220, y - 80,
                        auth="header",  # credential header, e.g. X-Api-Key: <APOLLO_API_KEY>
                        # Phase 70 Plan 04 (D-70-04): fed by "IF Apollo Enabled"'s TRUE
                        # lane, which now carries the row (via "Lusha Enrich Carry
                        # Merge" when Lusha ran, or straight from "Enrichment Gate"'s
                        # own row when it didn't) — bare $json, never a by-name lookup.
                        json_body=("={{ JSON.stringify({ "
                                   "email: $json.identity_keys.email, "
                                   "domain: $json.identity_keys.domain, "
                                   "first_name: $json.identity_keys.firstName, "
                                   "last_name: $json.identity_keys.lastName, "
                                   "organization_name: $json.identity_keys.companyName, "
                                   "reveal_personal_emails: true }) }}"))
    nodes.append(apollo)
    # Phase 70 Plan 04 (D-70-04): nests Apollo's raw response under `apollo_result`
    # before its carry merge re-attaches the row.
    nodes.append(code_node("Wrap Apollo Result", _wrap_provider_result_js("apollo_result"),
                           px + 275, y - 40))
    # ZoomInfo: split-code-node (Task 2 decision), now sitting BEHIND its own
    # IF ZoomInfo Enabled gate (Phase 16.1). The credential-bound "ZoomInfo Mint" HTTP
    # node is the ONLY place client_id/client_secret are read; the Token Gate/Cache
    # Token/Enrich Code nodes are secret-free, consuming only the short-lived bearer, and
    # keep "Enrichment Gate" as their gate_source_node (identity recovery by paired index,
    # runs regardless of provider gating).
    zoom_nodes, zoom_conns, zoom_entry, zoom_exit = _zoom_split_contacts_subgraph(
        "Enrichment Gate", px + 660, y - 80)
    nodes.extend(zoom_nodes)

    gate_nodes, gate_conns, first_gate_name = _provider_gate_bypass_chain(
        providers=[
            {"gate_name": "IF Lusha Enabled",
             "enabled_expr": _provider_enabled_expr("lusha"),
             "true_entry": "Lusha Enrich"},
            {"gate_name": "IF Apollo Enabled",
             "enabled_expr": _provider_enabled_expr("apollo"),
             "true_entry": "Apollo Match"},
            {"gate_name": "IF ZoomInfo Enabled",
             "enabled_expr": _provider_enabled_expr("zoominfo"),
             "true_entry": zoom_entry, "true_exit": zoom_exit},
        ],
        exit_node="Normalize + Score",
        x=px, y=y + 40,
    )
    nodes.extend(gate_nodes)

    sx = px + 660 + 660
    nodes.append(code_node("Normalize + Score", ENRICH_NORMALIZE_SCORE_CLOUD, sx, y - 80))

    # Phase 16.2 (SC-1/SC-2): the contacts research->judge mirror at the 16.1 seam —
    # mirrors the companies "Normalize + Score Company -> Research Trigger Gate -> ... ->
    # Merge Company" chain below, emitted by the SAME Plan-01 parameterized factories with
    # target=CONTACTS_TARGET (never a hand-rolled copy). Positions mirror the companies
    # cy-80/cy-180/cy-280 lane scheme.
    sx += 220
    nodes.append(code_node(
        "Contact Research Trigger Gate", _enrich_research_gate_js(cloud=True, target=CONTACTS_TARGET),
        sx, y - 80))
    sx += 220
    nodes.append(_if_bool_node("IF Contact Research Needed", "research_needed", sx, y - 80))
    sx += 220
    nodes.append(code_node(
        "Build Contact Research Request",
        _enrich_build_research_request_js(cloud=True, target=CONTACTS_TARGET), sx, y - 180))
    sx += 220
    nodes.append(_http_node(
        "Contact Web Research", "https://api.anthropic.com/v1/messages", sx, y - 180,
        auth="header",  # credential header x-api-key: <ANTHROPIC_API_KEY>
        headers=[{"name": "anthropic-version", "value": "2023-06-01"},
                 {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.research_request_body) }}"))
    sx += 220
    nodes.append(code_node(
        "Validate Contact Research", _enrich_validate_research_js(target=CONTACTS_TARGET), sx, y - 180))
    sx += 220
    nodes.append(code_node(
        "Contact Judge Gate", _enrich_judge_gate_js(cloud=True, target=CONTACTS_TARGET), sx, y - 180))
    sx += 220
    nodes.append(_if_bool_node("IF Contact Needs Judge", "needs_judge", sx, y - 180))
    sx += 220
    nodes.append(code_node(
        "Build Contact Judge Request",
        _enrich_build_judge_request_js(cloud=True, target=CONTACTS_TARGET), sx, y - 280))
    sx += 220
    nodes.append(_http_node(
        "Contact Judge Call", "https://api.anthropic.com/v1/messages", sx, y - 280,
        auth="header",
        headers=[{"name": "anthropic-version", "value": "2023-06-01"},
                 {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.judge_request_body) }}"))
    sx += 220
    nodes.append(code_node(
        "Apply Contact Judge Verdict", _enrich_apply_judge_verdict_js(target=CONTACTS_TARGET), sx, y - 280))
    sx += 220
    nodes.append(code_node("Merge Winners", ENRICH_MERGE, sx, y - 80))
    sx += 220
    # BUG 12 (found live 2026-07-29, executions 13 AND 14). This was an
    # `n8n-nodes-base.set` typeVersion 3.4, which emits ONLY its assigned fields — so it
    # deleted merge/existingRecord/object_id/scored on the way to `Decide Action`, which
    # then resolved hs_object_id to null and the patch to {}. The contacts write path
    # could not write to ANY record under ANY flag combination.
    #
    # Adding `options.includeOtherFields: true` did NOT fix it: execution 14 read that
    # option back as deployed and the node still emitted only the two fields, so that is
    # not where/what this typeVersion reads. Rather than guess n8n's Set schema a second
    # time against production, this is now a Code node that spreads the row explicitly —
    # deterministic, offline-testable, and the same shape as every other row-carrying node
    # in this workflow. The node NAME is unchanged so connections and name-keyed maps hold.
    # Guarded by tests/test_row_carry.py.
    nodes.append(code_node("Set Data Quality + Gap Flag", ENRICH_SET_DQ_JS, sx, y - 80))
    sx += 220
    nodes.append(code_node("Decide Action", ENRICH_DECIDE_CLOUD, sx, y - 80))

    # IF create -> HubSpot Create ; else IF enrich -> HubSpot Update (both GATED writes).
    sx += 220
    if_create = _if_node("IF Create", "create", sx, y - 80)
    nodes.append(if_create)
    # BUG 13 — see _hs_http_create_node. Was a native node with additionalFields:{} and an
    # `email` expression reading $json.properties.email, which the Decide output never
    # carries (email is manual_protected and can never promote into the patch).
    nodes.append(_hs_http_create_node("HubSpot Create", "contacts", sx + 220, y - 200))
    if_enrich = _if_node("IF Enrich", "enrich", sx + 220, y - 20)
    nodes.append(if_enrich)
    # BUG 11 / Phase 16.7-01: credential-bound httpRequest PATCH, NOT the native hubspot
    # node — the native `update` operation exists, but this builder never populated its
    # `updateFields` (empty map, referencing $json.properties nowhere; see
    # _hs_http_patch_node's docstring for the confirmed mechanism). Targets the REAL id
    # preserved by Adapt Search (Task 6, review #8), carried via the URL expression now
    # instead of a native id parameter. Node NAME is unchanged so
    # deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP entry keeps binding it.
    hs_update = _hs_http_patch_node("HubSpot Update", "contacts", sx + 440, y - 20)
    nodes.append(hs_update)

    # (Skip (NoOp) is created earlier now — Phase 16.1 — as the single-lane dispatch's
    # false target, right next to "IF Provider Processing Needed".)

    # --- COMPANIES branch: sibling off the same Webhook Trigger, own row (y+420) -----
    # Task 5 (Phase 16): ports the companies ICP branch build_enrichment_local_live()
    # already has, Cloud-converted (native HubSpot node, credential-bound HTTP nodes,
    # cloud-aware flag functions — 16-PATTERNS.md Analog A/B). Emit Company Targets (the
    # LOCAL-LIVE fixture emitter, ENRICH_EMIT_COMPANIES) is DELIBERATELY NOT ported
    # (review #6, VERIFIED hard-codes Harvey Norman/Racing NSW/...) — on the webhook path
    # the company identity comes from the event the caller sends, never a fixture row set.
    # Build Company Identity reads directly off the webhook body, same un-hardened state
    # Build Identity is in prior to Task 6's event parser + object-type router.
    cy = y + 420
    cx = x
    build_company_identity_x = cx
    nodes.append(code_node("Build Company Identity", ENRICH_BUILD_CO_IDENTITY, cx, cy))
    # Task 6 (review #8): real filterGroups (domain EQ, reusing the same envelope shape
    # HS_CO_SEARCH_BODY_EXPR already proves for the raw-HTTP local-live variant) +
    # hs_object_id in the property list.
    #
    # BUG 10 / Phase 16.6: credential-bound httpRequest, NOT the native hubspot node —
    # n8n's HubSpot node has no `operation: "search"` for resource:company at all (see
    # _hs_http_search_node's docstring for the confirmed mechanism); the native node
    # silently returned json:null live. Node NAME is unchanged so
    # deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP entry keeps binding it.
    cx += 220
    hs_co_search_x = cx
    hs_co_search = _hs_http_search_node(
        "HubSpot Company Search", "company", cx, cy,
        filter_groups=[[{"propertyName": "domain", "operator": "EQ",
                          "value": "={{ $json.identity_keys.domain }}"}]],
        properties_csv=ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
    )
    nodes.append(hs_co_search)
    cx += 220
    adapt_co_search_x = cx
    nodes.append(code_node("Adapt Company Search", ENRICH_ADAPT_CO_SEARCH, cx, cy))
    # 2026-08-25 name fallback — see HS_CO_NAME_SEARCH_FILTERS. Sits on the SEARCH branch
    # only: the fetch-by-id branch already has its record and never needs resolving.
    cx += 220
    nodes.append(_hs_http_search_node(
        "HubSpot Company Name Search", "company", cx, cy,
        filter_groups=HS_CO_NAME_SEARCH_FILTERS,
        properties_csv=ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
    ))
    cx += 220
    nodes.append(code_node("Adapt Company Name Search", ENRICH_ADAPT_CO_NAME_SEARCH, cx, cy))
    cx += 220
    nodes.append(code_node("Company Gate", ENRICH_CO_GATE, cx, cy))
    cx += 220
    nodes.append(code_node("Build Company Requests", ENRICH_BUILD_CO_REQUESTS, cx, cy))

    # Phase 16.4 Task 2: fetch-by-objectId lane — mirrors Task 1's contacts lane node for
    # node, converging back into "Company Gate". Placed on a free row below the companies
    # main row so none of the existing companies nodes' `position` values move.
    cfby = cy + 200
    if_company_bare_event = _if_bool_expr_node(
        "IF Company Bare Event",
        # Phase 70 Plan 04 Task 2 (D-70-03): bare $json — fed directly by "Build
        # Company Identity" (a Code node, never an HTTP node).
        "!!$json.object_id && "
        "!$json.identity_keys.domain",
        build_company_identity_x, cfby,
    )
    nodes.append(if_company_bare_event)
    # BUG 10 / Phase 16.6: _hs_http_search_node, not _hs_search_node — see that helper's
    # docstring; the native node has no `operation: "search"` for resource:company.
    hs_co_fetch_by_id = _hs_http_search_node(
        "HubSpot Company Fetch By Id", "company", hs_co_search_x, cfby,
        # Phase 70 Plan 04 (D-70-04): bare $json — "IF Company Bare Event" is a routing
        # IF, never an HTTP node, so $json here IS "Build Company Identity"'s own row.
        filter_groups=[[{"propertyName": "hs_object_id", "operator": "EQ",
                          "value": "={{ $json.object_id }}"}]],
        properties_csv=ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
    )
    nodes.append(hs_co_fetch_by_id)
    nodes.append(code_node(
        "Adapt Company Fetch By Id", ENRICH_ADAPT_FETCH_BY_ID_COMPANY, adapt_co_search_x, cfby))

    # Phase 47.5 Plan 01 (RECOMP-01/RECOMP-02): the request-level recompute lane. Emitted on
    # a second free row below the fetch-by-id lane so no existing node's `position` moves.
    #
    # Phase 70 Plan 04 Task 2 (D-70-03): `IF Company Recompute` reads bare `$json.recompute`
    # — fed directly by "Company Gate" (a Code node), whose own row already carries
    # `recompute` unchanged (stamped once, request-wide, by "Parse HubSpot Event";
    # identical on every row in the batch, so a per-row read is equivalent to the old
    # per-request `.first()` read — never a by-name lookup).
    #
    # `IF Company Skip` reads bare `$json.action` — correct HERE and only here: its immediate
    # upstream is a Code node, with no HTTP hop in between that could have replaced the item.
    crby = cfby + 200
    nodes.append(_if_bool_expr_node(
        "IF Company Recompute",
        "$json.recompute === true",
        build_company_identity_x, crby,
    ))
    nodes.append(_if_bool_expr_node(
        "IF Company Skip", '$json.action === "skip"', hs_co_search_x, crby,
    ))

    cpx = cx + 220
    # Phase 16.1 (Task 2 — mirrors Task 1's contacts fix): identity is read BY NODE NAME
    # from "Build Company Requests" (never bare $json), for the same reason as the
    # contacts Lusha/Apollo bodies — a gate positioned after another provider's HTTP
    # response would otherwise see that response as $json, not the row.
    #
    # BUG 17 (fixed 2026-07-29, live-probed against the (now-retired) v2 endpoint): this
    # node used to POST the identity object at the bare v2 endpoint and 400 every single
    # time with "property domain should not exist" — invisibly, because
    # onError:continueRegularOutput puts a provider failure in the ITEM, not the node, so
    # every company run reported success while silently enriching from two providers
    # instead of three. `domain` was (and, per the v3 probe below, still is) the only
    # accepted identity property; adding `companyName` 400s on both v2 and v3.
    #
    # v3 contract (docs/LUSHA-V3-CONTRACT.md §5, live-confirmed 2026-07-30): POST
    # /v3/companies/search-and-enrich, body {"companies":[{"domain":...}]} — no synthetic
    # `companyId` index key (rejected the same way contacts' `contactId` is). No `reveal`
    # key on this lane: §5/§6 confirm the companies lane exposes no `has`/`canReveal`
    # structure at all, so there is nothing to derive a reveal list from — no
    # reveal-derivation code exists for companies, deliberately.
    # ENRICH_BUILD_CO_REQUESTS prebuilds this body via the shared lushaCompanyBody() as
    # `lusha_company_body`.
    lusha_co = _http_node("Lusha Company",
                          "https://api.lusha.com/v3/companies/search-and-enrich",
                          cpx, cy - 80,
                          auth="header",  # credential header, e.g. api_key: <LUSHA_API_KEY>
                          # Phase 70 Plan 04 (D-70-04): fed by "IF Lusha Company
                          # Enabled"'s TRUE lane — bare $json is "Build Company
                          # Requests"'s own row, never a by-name lookup.
                          json_body="={{ JSON.stringify($json.lusha_company_body) }}")
    nodes.append(lusha_co)
    # Phase 70 Plan 04 (D-70-04): nests Lusha's raw response under `lusha_result`.
    nodes.append(code_node("Wrap Lusha Company Result", _wrap_provider_result_js("lusha_result"),
                           cpx + 55, cy - 40))
    apollo_org = _http_node(
        "Apollo Org", "https://api.apollo.io/v1/organizations/enrich", cpx + 220, cy - 80,
        auth="header",  # credential header, e.g. X-Api-Key: <APOLLO_API_KEY>
        # Phase 70 Plan 04 (D-70-04): fed by "IF Apollo Org Enabled"'s TRUE lane, which
        # now carries the row (via "Lusha Company Carry Merge" when Lusha ran, or
        # straight from "Build Company Requests" when it didn't).
        json_body="={{ JSON.stringify({ domain: $json.identity_keys.domain }) }}")
    nodes.append(apollo_org)
    # Phase 70 Plan 04 (D-70-04): nests Apollo's raw response under `apollo_result`.
    nodes.append(code_node("Wrap Apollo Org Result", _wrap_provider_result_js("apollo_result"),
                           cpx + 275, cy - 40))
    # ZoomInfo Company: split-code-node, same credential-bound-Mint shape as contacts, now
    # sitting BEHIND its own IF ZoomInfo Company Enabled gate (Phase 16.1 Task 2).
    zoom_co_nodes, zoom_co_conns, zoom_co_entry, zoom_co_exit = _zoom_split_company_subgraph(
        "Company Gate", cpx + 660, cy - 80)
    nodes.extend(zoom_co_nodes)

    # Phase 16.1 Task 2: the SAME shared _provider_gate_bypass_chain(...) helper Task 1
    # introduced for contacts (CONTEXT Locked Decision 8 — the reuse seam), called
    # identically here. Companies has no Route Action switch / skip lane (providers run
    # unconditionally for every row today, per the LOCAL-LIVE precedent this branch
    # ports) — the entry is "Build Company Requests" directly, no dispatch IF needed.
    co_gate_nodes, co_gate_conns, co_first_gate_name = _provider_gate_bypass_chain(
        providers=[
            {"gate_name": "IF Lusha Company Enabled",
             "enabled_expr": _provider_enabled_expr("lusha"),
             "true_entry": "Lusha Company"},
            {"gate_name": "IF Apollo Org Enabled",
             "enabled_expr": _provider_enabled_expr("apollo"),
             "true_entry": "Apollo Org"},
            {"gate_name": "IF ZoomInfo Company Enabled",
             "enabled_expr": _provider_enabled_expr("zoominfo"),
             "true_entry": zoom_co_entry, "true_exit": zoom_co_exit},
        ],
        exit_node="Normalize + Score Company",
        x=cpx, y=cy + 40,
    )
    nodes.extend(co_gate_nodes)

    csx = cpx + 660 + 660
    nodes.append(code_node("Normalize + Score Company", ENRICH_NORMALIZE_SCORE_CO, csx, cy - 80))
    csx += 220
    nodes.append(code_node("Research Trigger Gate", _enrich_research_gate_js(cloud=True), csx, cy - 80))
    csx += 220
    nodes.append(_if_bool_node("IF Research Needed", "research_needed", csx, cy - 80))
    csx += 220
    nodes.append(code_node(
        "Build Research Request", _enrich_build_research_request_js(cloud=True), csx, cy - 180))
    csx += 220
    nodes.append(_http_node(
        "Claude Web Research", "https://api.anthropic.com/v1/messages", csx, cy - 180,
        auth="header",  # credential header x-api-key: <ANTHROPIC_API_KEY>
        headers=[{"name": "anthropic-version", "value": "2023-06-01"},
                 {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.research_request_body) }}"))
    csx += 220
    # D-04 (Phase 48 Plan 02, folded todo
    # .planning/todos/pending/2026-08-12-n8n-swallows-anthropic-credit-failure.md): _http_node's
    # default onError="continueRegularOutput" means an Anthropic 400 (live exec 11833, credit
    # exhaustion) arrives as DATA on Claude Web Research's main output, not as a node failure —
    # so a gate is needed immediately downstream to keep an error-shaped payload out of
    # Validate Research Output / Merge Company / Decide Company Action. Bare $json is correct
    # HERE and only here: the immediate upstream IS the HTTP node itself, so nothing can have
    # replaced the item in between — the same reasoning IF Company Skip's own comment gives for
    # its own bare $json.action read (:4687-4688).
    nodes.append(_if_bool_expr_node(
        "IF Research Errored",
        "!!$json.error || !Array.isArray($json.content)",
        csx, cy - 180,
    ))
    csx += 220
    # The true lane's item is the raw HTTP-node output (no action/hs_object_id/gate fields),
    # unlike IF Company Skip's true lane — it cannot wire straight to Build Response the way
    # that gate does. Recover the pre-HTTP row BY NODE NAME, the SAME idiom
    # Validate Research Output already uses for "Build Research Request"
    # (_enrich_validate_research_js, :2360-2362), so the row reaching Build Response carries
    # the same action/gate shape every other terminal produces.
    nodes.append(code_node("Build Research Failure Response", r"""
// Phase 70 Plan 04 (D-70-04): "Research Carry Merge" (immediately after "Claude Web
// Research", input 1 the row carried from "Build Research Request") feeds BOTH this
// node and "Validate Research Output" via "IF Research Errored" — $input here is
// ALREADY the combined {row, raw response/error} item, no by-name recovery.
return $input.all().map((it) => {
  const merged = it.json || {};
  const message = (merged.error && merged.error.message) || 'research call failed';
  const { id, type, role, content, model, usage, stop_reason, stop_sequence, error, ...row } = merged;
  return { json: { ...row, action: "research_failed", gate: { reason: message } } };
});
""", csx, cy - 260))
    csx += 220
    nodes.append(code_node("Validate Research Output", ENRICH_VALIDATE_RESEARCH, csx, cy - 180))
    csx += 220
    nodes.append(code_node("Judge Gate", _enrich_judge_gate_js(cloud=True), csx, cy - 180))
    csx += 220
    nodes.append(_if_bool_node("IF Needs Judge", "needs_judge", csx, cy - 180))
    csx += 220
    nodes.append(code_node(
        "Build Judge Request", _enrich_build_judge_request_js(cloud=True), csx, cy - 280))
    csx += 220
    nodes.append(_http_node(
        "Judge Call", "https://api.anthropic.com/v1/messages", csx, cy - 280,
        auth="header",
        headers=[{"name": "anthropic-version", "value": "2023-06-01"},
                 {"name": "content-type", "value": "application/json"}],
        json_body="={{ JSON.stringify($json.judge_request_body) }}"))
    csx += 220
    nodes.append(code_node("Apply Judge Verdict", ENRICH_APPLY_JUDGE_VERDICT, csx, cy - 280))
    csx += 220
    nodes.append(code_node("Merge Company", ENRICH_MERGE_CO, csx, cy - 80))
    csx += 220
    nodes.append(code_node("Decide Company Action", ENRICH_DECIDE_CO_CLOUD, csx, cy - 80))

    # IF company-create -> HubSpot Company Create ; else IF company-enrich -> HubSpot
    # Company Update (both write-safety-gated in Task 6 — Task 5 wires the structure).
    # No early skip switch (unlike the contacts branch): the LOCAL-LIVE company branch
    # this ports runs providers unconditionally for every row (no pre-waterfall skip
    # optimization exists there either); a "skip" action falls through both IFs to end.
    csx += 220
    if_co_create = _if_node("IF Company Create", "create", csx, cy - 80)
    nodes.append(if_co_create)
    # BUG 13 — see _hs_http_create_node. Was a native node with additionalFields:{} plus a
    # `name` expression reading $json.name / $json.identity_keys.*, none of which exist on
    # Decide Company Action's output (verified from live execution 12: it emits exactly
    # action/object_type/hs_object_id/gap_flag/needs_review/properties). Dereferencing the
    # absent identity_keys would have thrown. The 2026-07-28 note about `name` being a
    # required activation-time parameter applied to the NATIVE node only; the CRM v3 REST
    # endpoint takes it inside `properties` like any other field, and the merge supplies it
    # there when it has one.
    nodes.append(_hs_http_create_node("HubSpot Company Create", "companies", csx + 220, cy - 200))
    # Phase 61 Plan 06 Task 2 (REVIEW-C17): the id capture point, spliced between the
    # create write and the shared convergence — see ADAPT_COMPANY_CREATE's own comment.
    nodes.append(code_node("Adapt Company Create", ADAPT_COMPANY_CREATE, csx + 440, cy - 200))
    if_co_enrich = _if_node("IF Company Enrich", "enrich", csx + 220, cy - 20)
    nodes.append(if_co_enrich)
    # BUG 11 / Phase 16.7-01: credential-bound httpRequest PATCH — companies mirror of
    # "HubSpot Update" above. Node NAME is unchanged so NODE_CREDENTIAL_MAP keeps binding
    # it; see _hs_http_patch_node's docstring for the confirmed mechanism.
    hs_co_update = _hs_http_patch_node("HubSpot Company Update", "companies", csx + 440, cy - 20)
    nodes.append(hs_co_update)

    # --- Phase 16.1 Plan 02 (reviews C1/C2/C3, SC-4/SC-5): single-item credit branch ---
    # forked off "Parse HubSpot Event" (wired below, NOT off the multi-row terminal/
    # enrichment flow) -> a single-item "Credit Request" -> per-provider "IF <provider>
    # Credit Requested" gates -> at most ONE credit HTTP call per provider per run.
    bx = x
    by = cy + 420
    lusha_credit = provider_registry.PROVIDER_REGISTRY["lusha"]["credit"]
    apollo_credit = provider_registry.PROVIDER_REGISTRY["apollo"]["credit"]

    nodes.append(code_node("Credit Request", ENRICH_CREDIT_REQUEST, bx, by))
    bx += 220
    nodes.append(_if_bool_expr_node(
        "IF Lusha Credit Requested", "$json.providers_requested.includes('lusha')", bx, by - 120))
    nodes.append(_if_bool_expr_node(
        "IF Apollo Credit Requested", "$json.providers_requested.includes('apollo')", bx, by))
    nodes.append(_if_bool_expr_node(
        "IF ZoomInfo Credit Requested", "$json.providers_requested.includes('zoominfo')", bx, by + 120))
    bx += 220
    nodes.append(_credit_http_node(
        "Lusha Usage", lusha_credit["url"], lusha_credit["method"], bx, by - 120, auth="header"))
    nodes.append(_credit_http_node(
        "Apollo Usage", apollo_credit["url"], apollo_credit["method"], bx, by, auth="header"))
    # ZoomInfo: Bug A fix (live 2026-07-28) — the credit branch no longer mints its own
    # ungated token. It gets the SAME 5-node Token Gate/IF Needs Mint/Mint/Cache Token
    # subgraph shape as the contacts/companies row-flows, sharing the identical
    # sd.zoominfo cache key (_zoom_split_usage_subgraph), so at most one mint happens per
    # run when the cache is warm and every consumer's mint result is visible to every
    # other consumer. gate_source_node="Credit Request" mirrors the row-flow subgraphs'
    # paired-index identity-recovery idiom (harmless here — $input already IS the Credit
    # Request row, single-item, by the time the Gate runs).
    zoom_usage_nodes, zoom_usage_conns, zoom_usage_entry, zoom_usage_exit = (
        _zoom_split_usage_subgraph("Credit Request", bx, by + 120))
    nodes.extend(zoom_usage_nodes)
    bx += 880

    # Phase 70 Plan 04 (D-70-04): each provider's real HTTP result and its "not
    # requested" skip marker normalise to the SAME {provider, requested, credits}
    # shape before "Collect Credits" — see _credit_adapt_js/_credit_skip_js's own
    # comment above.
    nodes.append(code_node("Adapt Lusha Usage", _credit_adapt_js("lusha"), bx, by - 160))
    nodes.append(code_node("Lusha Credit Skipped", _credit_skip_js("lusha"), bx, by - 80))
    nodes.append(code_node("Adapt Apollo Usage", _credit_adapt_js("apollo"), bx, by))
    nodes.append(code_node("Apollo Credit Skipped", _credit_skip_js("apollo"), bx, by + 80))
    nodes.append(code_node("Adapt ZoomInfo Usage", _credit_adapt_js("zoominfo"), bx, by + 160))
    nodes.append(code_node("ZoomInfo Credit Skipped", _credit_skip_js("zoominfo"), bx, by + 240))
    bx += 220
    nodes.append(merge_node("Collect Credits", bx, by, inputs=3, mode="append"))
    bx += 220
    nodes.append(code_node("Build Credits Summary", ENRICH_BUILD_CREDITS_SUMMARY, bx, by))
    bx += 220

    credit_conns = {
        "Credit Request": {"main": [[
            {"node": "IF Lusha Credit Requested", "type": "main", "index": 0},
            {"node": "IF Apollo Credit Requested", "type": "main", "index": 0},
            {"node": "IF ZoomInfo Credit Requested", "type": "main", "index": 0},
        ]]},
        "IF Lusha Credit Requested": {"main": [
            [{"node": "Lusha Usage", "type": "main", "index": 0}],
            [{"node": "Lusha Credit Skipped", "type": "main", "index": 0}],
        ]},
        "IF Apollo Credit Requested": {"main": [
            [{"node": "Apollo Usage", "type": "main", "index": 0}],
            [{"node": "Apollo Credit Skipped", "type": "main", "index": 0}],
        ]},
        "IF ZoomInfo Credit Requested": {"main": [
            [{"node": zoom_usage_entry, "type": "main", "index": 0}],
            [{"node": "ZoomInfo Credit Skipped", "type": "main", "index": 0}],
        ]},
        **zoom_usage_conns,
        "Lusha Usage": {"main": [[{"node": "Adapt Lusha Usage", "type": "main", "index": 0}]]},
        "Apollo Usage": {"main": [[{"node": "Adapt Apollo Usage", "type": "main", "index": 0}]]},
        zoom_usage_exit: {"main": [[{"node": "Adapt ZoomInfo Usage", "type": "main", "index": 0}]]},
        "Adapt Lusha Usage": {"main": [[{"node": "Collect Credits", "type": "main", "index": 0}]]},
        "Lusha Credit Skipped": {"main": [[{"node": "Collect Credits", "type": "main", "index": 0}]]},
        "Adapt Apollo Usage": {"main": [[{"node": "Collect Credits", "type": "main", "index": 1}]]},
        "Apollo Credit Skipped": {"main": [[{"node": "Collect Credits", "type": "main", "index": 1}]]},
        "Adapt ZoomInfo Usage": {"main": [[{"node": "Collect Credits", "type": "main", "index": 2}]]},
        "ZoomInfo Credit Skipped": {"main": [[{"node": "Collect Credits", "type": "main", "index": 2}]]},
        "Collect Credits": {"main": [[{"node": "Build Credits Summary", "type": "main", "index": 0}]]},
    }

    # Build Response / Respond to Webhook — the convergence every terminal branch feeds
    # (wired below). "Build Credits Summary"'s single item is broadcast onto every row
    # by "Credits Broadcast" (a combineAll merge spliced in further below) — Build
    # Response no longer reads any credit-check node by name.
    nodes.append(code_node("Build Response", ENRICH_BUILD_RESPONSE, bx + 660, (y + cy) // 2))
    nodes.append({
        "parameters": {"respondWith": "allIncomingItems", "options": {}},
        "id": nid("rw"), "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
        "position": [bx + 880, (y + cy) // 2],
    })

    conns = chain(["Webhook Trigger", "Parse HubSpot Event", "IF Object Type Supported"])
    # fix(40) / WINDOWS.md #3: the Execute Workflow Trigger's ONLY edge — straight into
    # "Parse HubSpot Event", same as the Webhook Trigger's record-ID path. A dedicated
    # inbound source, not a re-point of any existing edge.
    conns["Execute Workflow Trigger"] = {
        "main": [[{"node": "Parse HubSpot Event", "type": "main", "index": 0}]]}
    # Phase 25 Plan 03: the trigger's single edge to "Parse HubSpot Event" becomes the FALSE
    # lane of "IF List Input". Nothing downstream of Parse HubSpot Event changes, and the
    # record-ID path is byte-for-byte the path it was: Webhook -> (not a list) -> Parse.
    conns.update(chain([
        "Webhook Trigger", "IF List Input",
    ]))
    conns["IF List Input"] = {"main": [
        [{"node": "HubSpot List By Name", "type": "main", "index": 0}],  # true: resolve it
        [{"node": "Parse HubSpot Event", "type": "main", "index": 0}],   # false: today's path
    ]}
    conns.update(chain([
        "HubSpot List By Name", "HubSpot List Memberships",
        "Expand List To Events", "IF List Expanded",
    ]))
    # True: the expanded envelope re-enters the ordinary path at Parse HubSpot Event, in the
    # SAME shape a record-ID envelope arrives in — the branch adds a producer of that shape,
    # it does not fork the envelope contract.
    #
    # False (a refusal): Phase 70 Plan 03 Task 2 (D-70-07) re-points this from a direct
    # answer at "Respond to Webhook" to THREE parallel targets — "Build Ack" (so the
    # caller still gets its ack; "Parse HubSpot Event" never ran this execution, so this
    # is the ONLY producer that can reach the responder here), "Build Refusal Row" (so
    # the refusal reason lands as a ROW at "Build Response" instead of the body), and
    # (Phase 70 Plan 04, D-70-04) "Credit Request" — since "Parse HubSpot Event" never
    # ran, its own fan-out to "Credit Request" never fired either, and "Credits
    # Broadcast" (a combineAll merge) needs "Build Credits Summary" to deliver exactly
    # once per execution regardless of path or it hangs. Credit Request's own
    # `providers_requested` read already defaults to `[]` when its input carries none,
    # so this refusal row degrades to `remaining_credits: []` exactly like the pre-70-04
    # by-name lookup did. Never "Build Response" directly, and never through "Build
    # Response Merge"'s original ten inputs — that node's first statement reads
    # $('Parse HubSpot Event'), which on a refusal never executed; "Build Refusal Row"
    # is a NEW, eleventh Merge input, added below via `_append_merge_input`, precisely
    # so this stays additive to the pin tests/test_remaining_credits_response.py already
    # carries for the original ten.
    conns["IF List Expanded"] = {"main": [
        [{"node": "Parse HubSpot Event", "type": "main", "index": 0}],  # true: expanded
        [{"node": "Build Ack", "type": "main", "index": 0},             # false: refused
         {"node": "Build Refusal Row", "type": "main", "index": 0},
         {"node": "Credit Request", "type": "main", "index": 0}],
    ]}
    # Phase 16.1 Plan 02 (reviews C1): Parse HubSpot Event ALSO forks to the single-item
    # credit branch (Credit Request) — a parallel fan-out from the SAME output, not a
    # re-point of the existing IF Object Type Supported edge.
    # Phase 61 Plan 05 Task 2: a THIRD parallel fan target, "Build Ack" (renamed, Phase 70
    # Plan 03 Task 2, D-70-07) — see that node's own comment (ENRICH_BUILD_ACK) for why
    # this fires unconditionally now, not opt-in.
    # Phase 61 Plan 06 Task 5: the FIRST target is now "IF Scale Up Route", not
    # "IF Object Type Supported" directly — the ONE re-pointed edge this task discloses
    # (see "IF Scale Up Route"'s own comment above for why an unconditional 4th fan
    # target, mirroring Build Ack, would double-process a fanned row).
    conns["Parse HubSpot Event"] = {"main": [[
        {"node": "IF Scale Up Route", "type": "main", "index": 0},
        {"node": "Credit Request", "type": "main", "index": 0},
        {"node": "Build Ack", "type": "main", "index": 0},
    ]]}
    # Phase 70 Plan 03 Task 2 (D-70-07): THE sole edge into "Respond to Webhook" — every
    # other producer that used to feed it directly ("IF List Expanded" false, "Build
    # Scale Up Ack", "Build Response") is re-pointed elsewhere below.
    conns["Build Ack"] = {"main": [[
        {"node": "Respond to Webhook", "type": "main", "index": 0},
    ]]}
    # Phase 61 Plan 06 Task 5: true (is fanning, `_SCALE_UP_IS_FANNING_EXPR`) -> the
    # fan-out lane; false (every request that never opts in) -> "IF Object Type
    # Supported", the exact node Parse HubSpot Event fed directly before this task.
    conns["IF Scale Up Route"] = {"main": [
        [{"node": "Build Scale Up Fan-Out", "type": "main", "index": 0}],  # true: fanning
        [{"node": "IF Object Type Supported", "type": "main", "index": 0}],  # false: today's path
    ]}
    conns.update(chain(["Build Scale Up Fan-Out", "Dispatch Self", "Build Scale Up Ack"]))
    # Phase 70 Plan 03 Task 2 (D-70-07): re-pointed from "Respond to Webhook" (a
    # body-borne status) to "Build Refusal Row" (a row) — "Build Ack" already answered
    # this request via its own edge from "Parse HubSpot Event" above, since that node
    # runs whenever a scale-up dispatch does.
    conns["Build Scale Up Ack"] = {"main": [[
        {"node": "Build Refusal Row", "type": "main", "index": 0},
    ]]}
    # Phase 16.1 (reviews A2): unsupported/unknown object_type terminates HERE, before
    # Route By Object Type ever runs — no path to any provider gate.
    conns["IF Object Type Supported"] = {"main": [
        [{"node": "Route By Object Type", "type": "main", "index": 0}],   # true: supported
        [{"node": "Unsupported Object Type", "type": "main", "index": 0}],  # false: unsupported
    ]}
    # Route By Object Type: true (companies) -> Build Company Identity, false (contacts,
    # the only remaining option once "unsupported" is filtered above) -> Build Identity.
    conns["Route By Object Type"] = {"main": [
        [{"node": "Build Company Identity", "type": "main", "index": 0}],  # true
        [{"node": "Build Identity", "type": "main", "index": 0}],          # false
    ]}
    # Phase 16.4 Task 1: Build Identity now fans into "IF Bare Event" first — the fetch-
    # by-id lane's gate — rather than straight into "HubSpot Search". `chain()` overwrites
    # `conns[a]`, so this is split into 3 calls rather than appended to the single 5-name
    # chain HEAD~ had.
    conns.update(chain(["Build Identity", "IF Bare Event"]))
    conns["IF Bare Event"] = {"main": [
        [{"node": "HubSpot Fetch By Id", "type": "main", "index": 0}],  # true: bare event
        # Phase 36 Plan 02: false lane re-points to the match-lane cascade's entry point
        # (was "HubSpot Search" directly — tests/test_fetch_by_id_topology.py's pinned
        # assertion amended to match, per 36-CONTEXT.md §10). The email lane's own
        # downstream chain (HubSpot Search -> Adapt Search -> Enrichment Gate) is
        # unchanged; "IF Has Email"'s true branch below reconnects to it.
        [{"node": "IF Has Email", "type": "main", "index": 0}],
    ]}
    conns.update(chain(["HubSpot Fetch By Id", "Adapt Fetch By Id", "Enrichment Gate"]))
    # Phase 36 Plan 02: the match-lane cascade. "IF Has Email" routes the email lane back
    # onto the existing, unmodified "HubSpot Search" chain; its false lane now tries the
    # linkedin lane next (Phase 61 Plan 02 — was "IF Name Searchable" directly). "IF Name
    # Searchable"'s false lane (no searchable identity at all) goes straight to
    # "Enrichment Gate" — this is that node's FIFTH inbound branch (the same documented,
    # not-hard-determinism property "Build Response" already carries, 36-CONTEXT.md §12
    # Risk 1); the row arriving there carries no `existingRecord` by design, and Task 3's
    # gate rule turns it into a skip before any provider call.
    conns["IF Has Email"] = {"main": [
        [{"node": "HubSpot Search", "type": "main", "index": 0}],             # true: email lane
        [{"node": "IF Linkedin Searchable", "type": "main", "index": 0}],     # false
    ]}
    # Phase 61 Plan 02 (D-61-05 CORRECTED): the linkedin lane sits between "IF Has Email"
    # and "IF Name Searchable" — a strong key is tried before the weak name+company pair
    # (D-61-03). Its own false lane re-points to "IF Name Searchable", exactly where "IF
    # Has Email"'s false lane used to point before this plan.
    conns["IF Linkedin Searchable"] = {"main": [
        [{"node": "HubSpot Linkedin Search", "type": "main", "index": 0}],  # true: linkedin lane
        [{"node": "IF Name Searchable", "type": "main", "index": 0}],       # false
    ]}
    conns.update(chain(["HubSpot Linkedin Search", "Adapt Linkedin Search", "Enrichment Gate"]))
    conns["IF Name Searchable"] = {"main": [
        [{"node": "HubSpot Name Search", "type": "main", "index": 0}],  # true: name lane
        [{"node": "Enrichment Gate", "type": "main", "index": 0}],      # false: unmatchable
    ]}
    # F1 (2026-08-25): the fallback search sits SEQUENTIALLY between the primary search
    # and its adapter — never a parallel fan-out from "IF Name Searchable" — so
    # "Adapt Name Search" can read both with 1:1 item alignment guaranteed. Phase 70
    # Plan 04 (D-70-04): "Stash Name Primary Search" sits between the primary search and
    # the fallback — see its own comment; the two carry merges are spliced in below,
    # after this chain is built.
    conns.update(chain([
        "HubSpot Name Search", "Stash Name Primary Search", "HubSpot Name Search Fallback",
        "Adapt Name Search", "Enrichment Gate",
    ]))
    conns.update(chain(["HubSpot Search", "Adapt Search",
                        "Enrichment Gate", "IF Provider Processing Needed"]))
    # Phase 16.1 (reviews A1): a SINGLE lane feeds the provider gate chain — the
    # create-vs-enrich double-feed that used to run the gate chain + Normalize + Score
    # twice for a mixed batch is gone; action=="skip" is the only branch point here.
    conns["IF Provider Processing Needed"] = {"main": [
        [{"node": first_gate_name, "type": "main", "index": 0}],  # true: not skipped
        [{"node": "Skip (NoOp)", "type": "main", "index": 0}],    # false: skipped
    ]}
    # Phase 16.1: the per-provider IF-gate + bypass-convergence wiring (gate1..gateN,
    # each true->provider/false->bypass rejoining at the next stage, up to
    # "Normalize + Score") comes from the SHARED _provider_gate_bypass_chain(...) helper
    # (CONTEXT Locked Decision 8) — not hand-wired here. The ZoomInfo subgraph's OWN
    # internal wiring (Token Gate -> IF Needs Mint -> Mint/bypass -> Cache -> Enrich) is
    # unaffected and still comes from zoom_conns.
    conns.update(gate_conns)
    conns.update(zoom_conns)
    # Phase 16.2 seam (CONTEXT Locked Decision 8, reviews LOW-4): the mirrored contacts
    # research->judge chain, emitted by the SAME Plan-01 parameterized factories with
    # target=CONTACTS_TARGET the companies branch uses below — HIGH-3: the direct
    # "Normalize + Score -> Merge Winners" edge 16.1 built as a placeholder is now
    # SPLICED to route through the chain instead.
    conns.update(chain(["Normalize + Score", "Contact Research Trigger Gate"]))
    conns.update({
        "Contact Research Trigger Gate": {
            "main": [[{"node": "IF Contact Research Needed", "type": "main", "index": 0}]]},
        "IF Contact Research Needed": {"main": [
            [{"node": "Build Contact Research Request", "type": "main", "index": 0}],  # true
            [{"node": "Merge Winners", "type": "main", "index": 0}],                   # false: fan straight in
        ]},
        "Build Contact Research Request": {
            "main": [[{"node": "Contact Web Research", "type": "main", "index": 0}]]},
        "Contact Web Research": {"main": [[{"node": "Validate Contact Research", "type": "main", "index": 0}]]},
        "Validate Contact Research": {"main": [[{"node": "Contact Judge Gate", "type": "main", "index": 0}]]},
        "Contact Judge Gate": {"main": [[{"node": "IF Contact Needs Judge", "type": "main", "index": 0}]]},
        "IF Contact Needs Judge": {"main": [
            [{"node": "Build Contact Judge Request", "type": "main", "index": 0}],  # true
            [{"node": "Merge Winners", "type": "main", "index": 0}],                # false: fan straight in
        ]},
        "Build Contact Judge Request": {"main": [[{"node": "Contact Judge Call", "type": "main", "index": 0}]]},
        "Contact Judge Call": {"main": [[{"node": "Apply Contact Judge Verdict", "type": "main", "index": 0}]]},
        "Apply Contact Judge Verdict": {"main": [[{"node": "Merge Winners", "type": "main", "index": 0}]]},
        "Merge Winners": {"main": [[{"node": "Set Data Quality + Gap Flag", "type": "main", "index": 0}]]},
    })
    conns.update(chain(["Set Data Quality + Gap Flag", "Decide Action", "IF Create"]))
    conns["IF Create"] = {"main": [
        [{"node": "HubSpot Create", "type": "main", "index": 0}],  # true
        [{"node": "IF Enrich", "type": "main", "index": 0}],       # false
    ]}
    conns["IF Enrich"] = {"main": [
        [{"node": "HubSpot Update", "type": "main", "index": 0}],  # true
        [{"node": "Build Response", "type": "main", "index": 0}],  # false -> respond (Plan 02, C3)
    ]}
    # Phase 16.1 Plan 02: every real terminal gains an outgoing edge into the "Build
    # Response" convergence (reviews C3 — see its own jsCode comment for the honest
    # per-batch first-arrival semantics this multi-inbound wiring implies).
    conns["HubSpot Create"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
    conns["HubSpot Update"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
    conns["Skip (NoOp)"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}

    # --- COMPANIES branch connections: Route By Object Type's true branch already points
    # here (Task 6) — no separate Webhook Trigger fan-out needed.
    # Phase 16.4 Task 2: Build Company Identity now fans into "IF Company Bare Event"
    # first — the companies mirror of Task 1's contacts split. `chain()` overwrites
    # `conns[a]`, so this is split into calls rather than appended to the single chain
    # HEAD~ had.
    conns.update(chain(["Build Company Identity", "IF Company Bare Event"]))
    conns["IF Company Bare Event"] = {"main": [
        [{"node": "HubSpot Company Fetch By Id", "type": "main", "index": 0}],  # true
        [{"node": "HubSpot Company Search", "type": "main", "index": 0}],       # false
    ]}
    conns.update(chain([
        "HubSpot Company Fetch By Id", "Adapt Company Fetch By Id", "Company Gate",
    ]))
    conns.update(chain([
        "HubSpot Company Search",
        "Adapt Company Search", "HubSpot Company Name Search",
        "Adapt Company Name Search", "Company Gate",
    ]))
    # Phase 47.5 Plan 01: Company Gate's single outgoing edge is no longer
    # "Build Company Requests" — it is the recompute lane's entry. Both chain() calls above
    # still terminate AT Company Gate; only its outgoing edge changed.
    #   recompute true  -> Decide Company Action   (one edge: no provider, research, judge or
    #                                               merge node, so a recompute costs nothing)
    #   recompute false -> IF Company Skip
    #       skip true   -> Build Response          (RECOMP-02: a skipped record is observable,
    #                                               carrying gate.reason, instead of today's
    #                                               bare 200 with no body — a direct port of
    #                                               the contacts branch's Skip (NoOp) edge)
    #       skip false  -> Build Company Requests  (the unchanged enrichment path)
    conns["Company Gate"] = {
        "main": [[{"node": "IF Company Recompute", "type": "main", "index": 0}]]}
    conns["IF Company Recompute"] = {"main": [
        [{"node": "Decide Company Action", "type": "main", "index": 0}],  # true
        [{"node": "IF Company Skip", "type": "main", "index": 0}],        # false
    ]}
    conns["IF Company Skip"] = {"main": [
        [{"node": "Build Response", "type": "main", "index": 0}],          # true
        [{"node": "Build Company Requests", "type": "main", "index": 0}],  # false
    ]}
    # Phase 16.1 Task 2: Build Company Requests feeds the gated waterfall's first gate
    # directly (no dispatch IF — companies has no skip lane). The gate1..gateN + rejoin
    # wiring (up to "Normalize + Score Company") comes from the SAME shared
    # _provider_gate_bypass_chain(...) helper Task 1 used for contacts.
    conns["Build Company Requests"] = {"main": [[{"node": co_first_gate_name, "type": "main", "index": 0}]]}
    conns.update(co_gate_conns)
    conns.update(zoom_co_conns)
    conns.update(chain(["Normalize + Score Company", "Research Trigger Gate"]))
    conns.update({
        "Research Trigger Gate": {"main": [[{"node": "IF Research Needed", "type": "main", "index": 0}]]},
        "IF Research Needed": {"main": [
            [{"node": "Build Research Request", "type": "main", "index": 0}],  # true: needs research
            [{"node": "Merge Company", "type": "main", "index": 0}],           # false: fan straight in
        ]},
        "Build Research Request": {"main": [[{"node": "Claude Web Research", "type": "main", "index": 0}]]},
        # D-04 (Phase 48 Plan 02): Claude Web Research's single outgoing edge is no longer
        # "Validate Research Output" — it is "IF Research Errored". An error-shaped payload
        # (true lane) terminates observably at Build Response via Build Research Failure
        # Response; a healthy payload (false lane) continues unchanged.
        "Claude Web Research": {"main": [[{"node": "IF Research Errored", "type": "main", "index": 0}]]},
        "IF Research Errored": {"main": [
            [{"node": "Build Research Failure Response", "type": "main", "index": 0}],  # true: errored
            [{"node": "Validate Research Output", "type": "main", "index": 0}],         # false: unchanged
        ]},
        "Build Research Failure Response": {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]},
        "Validate Research Output": {"main": [[{"node": "Judge Gate", "type": "main", "index": 0}]]},
        "Judge Gate": {"main": [[{"node": "IF Needs Judge", "type": "main", "index": 0}]]},
        "IF Needs Judge": {"main": [
            [{"node": "Build Judge Request", "type": "main", "index": 0}],  # true: adjudicate
            [{"node": "Merge Company", "type": "main", "index": 0}],        # false: fan straight in
        ]},
        "Build Judge Request": {"main": [[{"node": "Judge Call", "type": "main", "index": 0}]]},
        "Judge Call": {"main": [[{"node": "Apply Judge Verdict", "type": "main", "index": 0}]]},
        "Apply Judge Verdict": {"main": [[{"node": "Merge Company", "type": "main", "index": 0}]]},
        "Merge Company": {"main": [[{"node": "Decide Company Action", "type": "main", "index": 0}]]},
        "Decide Company Action": {"main": [[{"node": "IF Company Create", "type": "main", "index": 0}]]},
        "IF Company Create": {"main": [
            [{"node": "HubSpot Company Create", "type": "main", "index": 0}],  # true
            [{"node": "IF Company Enrich", "type": "main", "index": 0}],       # false
        ]},
        "IF Company Enrich": {"main": [
            [{"node": "HubSpot Company Update", "type": "main", "index": 0}],  # true
            [{"node": "Build Response", "type": "main", "index": 0}],          # false -> respond (Plan 02)
        ]},
    })
    # Phase 61 Plan 06 Task 2 (REVIEW-C17): "HubSpot Company Create" now feeds "Adapt
    # Company Create" (the id capture point) before the shared convergence, rather than
    # straight into "Build Response".
    conns["HubSpot Company Create"] = {"main": [[{"node": "Adapt Company Create", "type": "main", "index": 0}]]}
    conns["Adapt Company Create"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
    conns["HubSpot Company Update"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
    conns["Unsupported Object Type"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
    conns.update(credit_conns)
    # Phase 70 Plan 03 Task 2 (D-70-07): "Build Response" is now a terminal leaf — no
    # outgoing edge at all. The caller reads its output from runData (`recover_dispatch`,
    # landed 70-02), never from the HTTP response body; "Build Ack" is the sole producer
    # "Respond to Webhook" hears from (wired above, off "Parse HubSpot Event"/"IF List
    # Expanded").

    notes = [
        {"content": (
            "## LV Enrichment — CLOUD template\n"
            "Run `python scripts/provision_n8n_credentials.py` then "
            "`python scripts/deploy_n8n_workflows.py` (both env-gated, dry-run by "
            "default — see their docstrings) to create the 6 credentials and deploy "
            "this workflow with every node bound: **Webhook Trigger** = generic Header "
            "Auth holding the shared `X-Enrichment-Secret` value (CLAUDE.md §18.1 — "
            "n8n rejects an unauthenticated request before any node runs); **HubSpot** "
            "(search/create/update, `hubspotAppToken`); **Lusha** + **Apollo** = generic "
            "Header Auth (one static key each, e.g. `api_key` / `X-Api-Key`); "
            "**ZoomInfo** = a credential-bound Mint HTTP node (generic Basic Auth "
            "holding client_id:client_secret) — see the ZoomInfo note. Every one of the "
            "6 config flags (research/judge cost caps + model knobs) is a baked "
            "build-time constant, not a runtime environment lookup — none survives "
            "in this JSON (Criterion 5).\n\n"
            "**Flow:** Webhook -> Parse HubSpot Event (resolves the caller's `providers` "
            "node, reviews A4) -> IF Object Type Supported (reviews A2 — unsupported "
            "terminates here) -> Route By Object Type -> Build (Company) Identity -> "
            "HubSpot Search -> Gate (create/enrich/skip) -> a single `action != skip` "
            "dispatch lane (reviews A1) -> the gated provider waterfall (each provider "
            "behind its own `IF <provider> Enabled` gate with a bypass, Phase 16.1 — "
            "SC-1/SC-2). skip does nothing.\n\n"
            "**Write safety (Task 6, review #9):** Decide Action / Decide Company "
            "Action bake a `WRITE_SAFETY_DEFAULTS` build-time constant — "
            "`ALLOW_HUBSPOT_RECORD_WRITES` default **false**, a create switch "
            "(`ALLOW_HUBSPOT_CREATE`), and a `TEST_RECORD_DOMAINS`/`TEST_RECORD_IDS` "
            "allowlist (empty allowlist denies everything). An activated-but-not-"
            "enabled workflow performs ZERO record writes; even once enabled, only an "
            "allowlisted domain/id may write."
        ), "x": 220, "y": 480, "h": 420, "w": 480},
        {"content": (
            "### Scored waterfall (not FIFO)\n"
            "`value_score = wA·A + wR·R + wG·G + wT·T`\n"
            "wA=0.45 (accuracy), wR=0.20 (recency), wG=0.25 (agreement/"
            "cross-check), wT=0.10 (source trust). Default mode `scored_all`: "
            "call all sources, score every candidate, pick argmax **per field** "
            "with provenance {source, score, agreedBy}. Best email from one "
            "source, best phone from another."
        ), "x": 900, "y": 480, "h": 300, "w": 460},
        {"content": (
            "### Apollo phone is ASYNC\n"
            "Apollo returns phone numbers via a **webhook callback**, not inline. "
            "In production add a second Webhook node to receive the phone payload "
            "and a Merge node to join it back. This template does the inline "
            "person/org match only."
        ), "x": 1580, "y": 60, "h": 200, "w": 380},
        {"content": (
            "### ZoomInfo = split-code-node (credential-bound Mint) — Task 2 decision\n"
            "**ZoomInfo Token Gate** (secret-free) checks the cached bearer in workflow "
            "static data -> **IF Needs Mint** -> true: **ZoomInfo Mint** (HTTP, "
            "credential-bound generic Basic Auth — the ONLY node that ever touches "
            "client_id/client_secret) -> **ZoomInfo Cache Token** (secret-free, parses + "
            "caches) -> **ZoomInfo Enrich** (secret-free, calls the GTM enrich endpoint "
            "with the bearer only). False lane skips straight to Enrich with the cached "
            "token.\n"
            "`POST api.zoominfo.com/gtm/oauth/v1/token`, Basic auth, body "
            "`grant_type=client_credentials` ONLY — **no `scope`** (400 invalid_scope). "
            "Token ~24h. A 401 during Enrich clears the cache so the NEXT run re-mints "
            "(no inline retry — that would need the secret this node never touches).\n"
            "Create the credential via `provision_n8n_credentials.py` (name **LV "
            "ZoomInfo**, type `httpBasicAuth`) from the **ZoomInfo DevPortal** "
            "client_id/client_secret (client-credentials grant enabled); rotate the "
            "secret ~quarterly."
        ), "x": 1140, "y": 60, "h": 340, "w": 420},
        {"content": (
            "### Properties + writes\n"
            "The `lv_*` HubSpot properties this workflow writes must exist in the "
            "portal first (`scripts/sync_hubspot_properties.py`). Provider credentials "
            "are real (no mocked responses) once provisioned via "
            "`provision_n8n_credentials.py`.\n\n"
            "**AU-phone:** normalizePhone is an AU-only heuristic (no libphonenumber "
            "in Code nodes); non-AU/ambiguous -> null -> review."
        ), "x": 1360, "y": 480, "h": 280, "w": 420},
        {"content": (
            "### Phase 16.2 seam — contacts research->judge mirror\n"
            "The mirror of the companies branch's `Normalize + Score Company -> Research "
            "Trigger Gate -> ... -> Merge Company` chain, WIRED here between **Normalize + "
            "Score** and **Merge Winners** (Contact Research Trigger Gate -> IF Contact "
            "Research Needed -> Build Contact Research Request -> Contact Web Research -> "
            "Validate Contact Research -> Contact Judge Gate -> IF Contact Needs Judge -> "
            "Build Contact Judge Request -> Contact Judge Call -> Apply Contact Judge "
            "Verdict), jobtitle/seniority ONLY (CONTEXT Locked Decision 8), emitted by "
            "16.1's shared node factories with target=CONTACTS_TARGET — never a hand-"
            "rolled copy of the companies bodies."
        ), "x": sx - 220, "y": y + 140, "h": 260, "w": 420},
        {"content": (
            "### Credit reporting (Plan 02, reviews C1/C2/C3)\n"
            "`Parse HubSpot Event` forks to a SINGLE-ITEM `Credit Request` node — one "
            "item regardless of event count, so each provider's usage/credit check fires "
            "AT MOST ONCE per run (not once per row — live-observed a Lusha 5 req/min 429 "
            "otherwise). Balances are read at run START and carried in the response by "
            "`Build Response`, which converges every terminal (5 real nodes + the 2 "
            "re-pointed IF-enrich-false lanes + the unsupported terminal) and reads each "
            "credit node BY NAME (a not-requested node -> null, never raises).\n\n"
            "**Response semantics:** the webhook now uses `responseMode: responseNode` + "
            "`Respond to Webhook`. Because Build Response has MULTIPLE inbound branches, "
            "it fires on whichever arrives FIRST — per-batch first-arrival, parity with "
            "the prior `lastNode` behavior, NOT hard determinism across a mixed batch. "
            "The 0-event/empty-body case and exact arrival ordering are Track B "
            "execution-level test items, not provable offline.\n\n"
            "**ZoomInfo shares the row-flow's token cache (Bug A fix, live 2026-07-28):** "
            "the usage check used to mint its OWN token unconditionally, bypassing "
            "`sd.zoominfo` entirely — ZoomInfo allows exactly ONE active token per "
            "credential, so that ungated mint invalidated whatever the contacts/"
            "companies row-flow had just cached, without updating the cache to match. "
            "It now goes through the SAME Token Gate/IF Needs Mint/Mint/Cache Token "
            "shape (`ZoomInfo Usage Token Gate` etc.) as the row-flow subgraphs, sharing "
            "the identical cache key."
        ), "x": bx, "y": by - 340, "h": 340, "w": 460},
    ]
    # n8n's POST /api/v1/workflows REJECTS a workflow containing duplicate node names
    # (400 duplicate_node_name) — found on the first live deploy 2026-07-28, where all
    # 7 stickies here shared the name "Sticky Note". Sticky notes are decorative and never
    # appear in `connections`, so numbering them is safe. Guarded by
    # tests/test_node_name_uniqueness.py.
    for i, n in enumerate(notes, start=1):
        nodes.append({
            "parameters": {"content": n["content"], "height": n["h"], "width": n["w"]},
            "id": nid("s"), "name": f"Sticky Note {i}",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "position": [n["x"], n["y"]],
        })

    # =========================================================================
    # Phase 70 Plan 05 Task 2 (D-70-13): the enrichment lane's FIRST-EVER spliced write
    # gates. Until now this lane decided write permission INLINE inside "Decide Action"/
    # "Decide Company Action" — the only lane in the build with no gate node at all. The
    # predicate is unchanged; only its home moved, so each lane has exactly one.
    #
    # Ordered BEFORE the carry-merge block below on purpose: `HubSpot Company Create
    # Carry Merge`'s `carry_source` must be the gate IF's TRUE output (the wave that
    # actually entered the write node), which does not exist until this call has run.
    splice_write_gates(nodes, conns, {
        "HubSpot Create": "create",
        "HubSpot Update": "enrich",
        "HubSpot Company Create": "create",
        "HubSpot Company Update": "enrich",
    })

    # =========================================================================
    # Phase 70 Plan 04 (D-70-04): a carry merge immediately after every provider,
    # HubSpot identity-search, and research/judge HTTP node on the enrichment lane —
    # re-attaching the pre-hop row (which the HTTP node's own response otherwise
    # replaces) onto the response, row-fields-last. Every downstream consumer this
    # unblocks is rewritten to read $input directly (see each JS constant's own
    # Phase 70 Plan 04 comment) — this is purely the WIRING half of that fix.
    #
    # --- List expansion (Phase 25 Plan 03's two chained HubSpot GETs) ---
    _list_by_name_old_target = conns["HubSpot List By Name"]["main"][0][0]["node"]
    conns["HubSpot List By Name"] = {"main": [[{"node": "Wrap List By Name Result", "type": "main", "index": 0}]]}
    conns["Wrap List By Name Result"] = {"main": [[{"node": _list_by_name_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap List By Name Result", "IF List Input",
                              merge_name="List By Name Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot List Memberships", "List By Name Carry Merge",
                              merge_name="List Memberships Carry Merge")

    # --- CONTACTS identity-lane searches ---
    splice_carry_merge_after(nodes, conns, "HubSpot Fetch By Id", "IF Bare Event",
                              merge_name="HubSpot Fetch By Id Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Search", "IF Has Email",
                              merge_name="HubSpot Search Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Linkedin Search", "IF Linkedin Searchable",
                              merge_name="HubSpot Linkedin Search Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Name Search", "IF Name Searchable",
                              merge_name="HubSpot Name Search Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Name Search Fallback", "Stash Name Primary Search",
                              merge_name="HubSpot Name Search Fallback Carry Merge")

    # --- CONTACTS provider waterfall: Wrap <provider> Result (nests the raw response)
    # then a carry merge re-attaches the row, re-pointed to the SAME downstream target
    # the HTTP node fed before this rewire (never hand-invented). ---
    _lusha_old_target = conns["Lusha Enrich"]["main"][0][0]["node"]
    conns["Lusha Enrich"] = {"main": [[{"node": "Wrap Lusha Result", "type": "main", "index": 0}]]}
    conns["Wrap Lusha Result"] = {"main": [[{"node": _lusha_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Lusha Result", "IF Lusha Enabled",
                              merge_name="Lusha Result Carry Merge")

    _apollo_old_target = conns["Apollo Match"]["main"][0][0]["node"]
    conns["Apollo Match"] = {"main": [[{"node": "Wrap Apollo Result", "type": "main", "index": 0}]]}
    conns["Wrap Apollo Result"] = {"main": [[{"node": _apollo_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Apollo Result", "IF Apollo Enabled",
                              merge_name="Apollo Result Carry Merge")

    splice_carry_merge_after(nodes, conns, "ZoomInfo Mint", "IF ZoomInfo Needs Mint",
                              merge_name="ZoomInfo Mint Carry Merge")

    # --- CONTACTS research/judge ---
    splice_carry_merge_after(nodes, conns, "Claude Web Research", "Build Research Request",
                              merge_name="Research Carry Merge")
    splice_carry_merge_after(nodes, conns, "Judge Call", "Build Judge Request",
                              merge_name="Judge Carry Merge")
    splice_carry_merge_after(nodes, conns, "Contact Web Research", "Build Contact Research Request",
                              merge_name="Contact Research Carry Merge")
    splice_carry_merge_after(nodes, conns, "Contact Judge Call", "Build Contact Judge Request",
                              merge_name="Contact Judge Carry Merge")

    # --- COMPANIES identity-lane searches ---
    splice_carry_merge_after(nodes, conns, "HubSpot Company Fetch By Id", "IF Company Bare Event",
                              merge_name="HubSpot Company Fetch By Id Carry Merge")
    splice_carry_merge_after(nodes, conns, "HubSpot Company Search", "IF Company Bare Event",
                              merge_name="HubSpot Company Search Carry Merge", source_out_idx=1)
    splice_carry_merge_after(nodes, conns, "HubSpot Company Name Search", "Adapt Company Search",
                              merge_name="HubSpot Company Name Search Carry Merge")

    # --- COMPANIES provider waterfall ---
    _lusha_co_old_target = conns["Lusha Company"]["main"][0][0]["node"]
    conns["Lusha Company"] = {"main": [[{"node": "Wrap Lusha Company Result", "type": "main", "index": 0}]]}
    conns["Wrap Lusha Company Result"] = {"main": [[{"node": _lusha_co_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Lusha Company Result", "IF Lusha Company Enabled",
                              merge_name="Lusha Company Result Carry Merge")

    _apollo_org_old_target = conns["Apollo Org"]["main"][0][0]["node"]
    conns["Apollo Org"] = {"main": [[{"node": "Wrap Apollo Org Result", "type": "main", "index": 0}]]}
    conns["Wrap Apollo Org Result"] = {"main": [[{"node": _apollo_org_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap Apollo Org Result", "IF Apollo Org Enabled",
                              merge_name="Apollo Org Result Carry Merge")

    splice_carry_merge_after(nodes, conns, "ZoomInfo Mint Company", "IF ZoomInfo Company Needs Mint",
                              merge_name="ZoomInfo Mint Company Carry Merge")

    # --- COMPANIES create (Phase 61 Plan 06 Task 2's id-capture hop) ---
    # Phase 70 Plan 05 Task 2: `carry_source` is the gate IF's TRUE output, not
    # "IF Company Create" — the gate can refuse a SUBSET, so only the true branch is
    # guaranteed to agree with the HTTP node on item count and order (combineByPosition).
    splice_carry_merge_after(nodes, conns, "HubSpot Company Create",
                              "HubSpot Company Create Write Gate IF",
                              merge_name="HubSpot Company Create Carry Merge")

    # --- Shared credit-check lane (contacts + companies) ---
    splice_carry_merge_after(nodes, conns, "ZoomInfo Usage Mint", "IF ZoomInfo Usage Needs Mint",
                              merge_name="ZoomInfo Usage Mint Carry Merge")

    # =========================================================================
    # Phase 70 Plan 03 (D-70-01): a real Merge in front of every "fan_in"
    # convergence `classify_convergence` identifies over THIS built graph, plus a
    # starved-lane sentinel network on every input that can otherwise never fire.
    #
    # `Parse HubSpot Event` (class "entry_points" — `Execute Workflow Trigger` vs. the
    # two webhook-path branches) deliberately gets NO Merge; see
    # tests/test_merge_helpers.py::test_parse_hubspot_event_is_entry_points_and_
    # splice_merge_before_refuses_it. `Respond to Webhook`'s 4 inbound edges are Task
    # 2's job, not merged here. The provider-gate bypass chains (`IF Apollo Enabled`
    # <-> `IF ZoomInfo Enabled` <-> `Normalize + Score` <-> `ZoomInfo Enrich` and their
    # companies twins) are class "fan_in" too (`classify_convergence` does not
    # distinguish the plan's own class (a)/(b) — both are safe to merge, and it only
    # refuses "entry_points") but are deliberately LEFT UNMERGED: each pair rejoins
    # after EXACTLY one delivery per row by construction (`_provider_gate_bypass_chain`'s
    # own docstring — "exactly one fires per row"), so a Merge there adds hang exposure
    # (T-70-04) for zero behaviour change, and is recorded here as the "leave unmerged,
    # record why" case the plan's own action text permits.
    #
    # Every OTHER "fan_in" node with >= 2 inbound edges gets a Merge:
    build_response_merge = splice_merge_before(nodes, conns, "Build Response",
                                                merge_name="Build Response Merge")
    enrichment_gate_merge = splice_merge_before(nodes, conns, "Enrichment Gate",
                                                 merge_name="Enrichment Gate Merge")
    company_gate_merge = splice_merge_before(nodes, conns, "Company Gate",
                                              merge_name="Company Gate Merge")
    merge_winners_merge = splice_merge_before(nodes, conns, "Merge Winners",
                                               merge_name="Merge Winners Fan-In")
    merge_company_merge = splice_merge_before(nodes, conns, "Merge Company",
                                               merge_name="Merge Company Fan-In")
    decide_co_action_merge = splice_merge_before(nodes, conns, "Decide Company Action",
                                                  merge_name="Decide Company Action Merge")

    # --- Merge input indices, resolved AFTER every splice above (never invented) -------
    # Each returns a ready-to-use `(merge_name, index)` target pair — never a bare index,
    # so a target list below reads `[eg("Adapt Search"), ...]` and cannot accidentally
    # transpose the pair `_add_starved_lane_sentinel` expects.
    br = lambda src, idx=0: (build_response_merge, _merge_input_index(conns, src, build_response_merge, source_out_idx=idx))
    eg = lambda src, idx=0: (enrichment_gate_merge, _merge_input_index(conns, src, enrichment_gate_merge, source_out_idx=idx))
    cg = lambda src, idx=0: (company_gate_merge, _merge_input_index(conns, src, company_gate_merge, source_out_idx=idx))
    mw = lambda src, idx=0: (merge_winners_merge, _merge_input_index(conns, src, merge_winners_merge, source_out_idx=idx))
    mc = lambda src, idx=0: (merge_company_merge, _merge_input_index(conns, src, merge_company_merge, source_out_idx=idx))
    dca = lambda src, idx=0: (decide_co_action_merge, _merge_input_index(conns, src, decide_co_action_merge, source_out_idx=idx))

    sx, sy = 40, 2200  # a dedicated, empty region of the canvas for the sentinel network

    # --- Pre-fork sentinels: fed from "IF Scale Up Route" false (index 1) — the single
    # point every non-fanned request reaches with `object_type` already stamped by
    # "Parse HubSpot Event", BEFORE "IF Object Type Supported"/"Route By Object Type"
    # fork. Never fed from "Parse HubSpot Event" itself: that node ALSO runs on a fanned
    # scale-up dispatch, where feeding a merge input here would satisfy it while the
    # fanned child's OWN execution never runs the rest of the graph at all
    # (scaleUpFanOutFlow.test.mjs would then see a half-fed merge -> false stall).
    # Phase 70 Plan 03 Task 2 (Rule 1 fix — a walker probe over an unsupported-object-
    # type-ONLY batch, added by enrichmentBatchRefusal.test.mjs, stalled Build Response
    # Merge): the ORIGINAL condition tested `every row IS "companies"` — sufficient but
    # not necessary for "contacts absent". A batch whose rows are all "unknown" (or a
    # mix of "unknown" and "companies", with no "contacts" row at all) is genuinely
    # contacts-absent but is NEITHER "every row is companies", so this sentinel never
    # fired and Build Response Merge's contacts-side inputs went unfed forever. Fixed
    # to the actually-correct predicate, `every row is NOT "contacts"` (equivalently
    # "no row is contacts") — this is what "contacts absent" means, and it is now
    # correct for every object_type value including "unknown", not just "companies".
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Absent Sentinel", "IF Scale Up Route",
        'if (rows.length > 0 && rows.every((r) => r.object_type !== "contacts")) '
        'return [{}]; return [];',
        [eg("Adapt Fetch By Id"),
         eg("Adapt Linkedin Search"),
         eg("IF Name Searchable", 1),
         eg("Adapt Name Search"),
         eg("Adapt Search"),
         # "Enrichment Gate" (the code node) drops an all-marker wave to ZERO output —
         # its own first-line identity filter — so the marker can never naturally
         # cascade to "IF Provider Processing Needed"/"Decide Action" from here; feed
         # every downstream index it would otherwise have starved directly (Rule 1 —
         # found running the walker against a companies-only batch).
         mw("IF Contact Research Needed", 1),
         mw("IF Contact Needs Judge", 1),
         mw("Apply Contact Judge Verdict"),
         br("Skip (NoOp)"),
         br("HubSpot Create"),
         br("HubSpot Update"),
         br("IF Enrich", 1)],
        sx, sy, source_out_idx=1,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Absent Sentinel", "IF Scale Up Route",
        'if (rows.length > 0 && rows.every((r) => r.object_type !== "companies")) '
        'return [{}]; return [];',
        [cg("Adapt Company Fetch By Id"),
         cg("Adapt Company Name Search"),
         dca("IF Company Recompute"),
         # "Merge Company" (the code node) drops an all-marker wave to ZERO output —
         # its own first-line identity filter — so its EMPTY result never propagates to
         # "Decide Company Action Merge" on its own; feed that index directly too.
         dca("Merge Company"),
         mc("IF Research Needed", 1),
         mc("IF Needs Judge", 1),
         mc("Apply Judge Verdict"),
         br("IF Company Skip"),
         br("Build Research Failure Response"),
         br("Adapt Company Create"),
         br("HubSpot Company Update"),
         br("IF Company Enrich", 1)],
        sx, sy, source_out_idx=1,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Unsupported Absent Sentinel", "IF Scale Up Route",
        'if (rows.length > 0 && rows.every((r) => r.object_type !== "unknown")) '
        'return [{}]; return [];',
        [br("Unsupported Object Type")],
        sx, sy, source_out_idx=1,
    )
    sy += 120

    # --- Contacts identity-lane sentinels: fed from "Build Identity" (single producer,
    # always runs whenever any contacts row exists — either real or the pre-fork
    # marker). "laneOf" (matchProposal.js) stamps exactly one of these 5 values per row
    # (Build Identity's own `lane: laneOf(...)` line) — reading the SAME field the
    # nested "IF Bare Event"/"IF Has Email"/"IF Linkedin Searchable"/"IF Name
    # Searchable" chain routes on, never re-deriving it. This is D-70-01's "common
    # shape and the hang case" (single-identity-lane batch) the plan names explicitly.
    for lane, target in [
        ("fetch_by_id", eg("Adapt Fetch By Id")),
        ("email", eg("Adapt Search")),
        ("linkedin", eg("Adapt Linkedin Search")),
        ("name", eg("Adapt Name Search")),
        ("none", eg("IF Name Searchable", 1)),
    ]:
        _add_starved_lane_sentinel(
            nodes, conns, f"Contacts Lane {lane.title().replace('_', '')} Absent Sentinel",
            "Build Identity",
            f'if (rows.length > 0 && !rows.some((r) => r.lane === "{lane}")) '
            'return [{}]; return [];',
            [target], sx, sy,
        )
        sy += 120

    # --- Companies identity-lane sentinels: the 2-way mirror ("IF Company Bare Event"),
    # fed from "Build Company Identity", reading the identical predicate.
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Lane BareEvent Absent Sentinel", "Build Company Identity",
        'if (rows.length > 0 && !rows.some((r) => r.object_id && '
        '!(r.identity_keys && r.identity_keys.domain))) return [{}]; return [];',
        [cg("Adapt Company Fetch By Id")], sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Lane DomainSearch Absent Sentinel", "Build Company Identity",
        'if (rows.length > 0 && !rows.some((r) => !(r.object_id && '
        '!(r.identity_keys && r.identity_keys.domain)))) return [{}]; return [];',
        [cg("Adapt Company Name Search")], sx, sy,
    )
    sy += 120

    # --- Recompute (RECOMP-01) is a whole-REQUEST flag, read the same way
    # "IF Company Recompute" itself reads it — `.first()` off "Parse HubSpot Event",
    # never per-row.
    #
    # Phase 70 Plan 03 Task 2 (Rule 1 — bug found live via a scale_up=true walker probe
    # this task added, `Decide Company Action Merge` stalled on `Merge Company`'s input):
    # both sentinels below used to be sourced from "Parse HubSpot Event" directly, which
    # STILL RUNS in a scale_up=true execution (it is the node that computes `scale_up`),
    # so they fired their marker into "Decide Company Action Merge" even though the
    # WHOLE companies waterfall never runs on that path — a partial delivery (this
    # input satisfied, "Merge Company"'s own 3 inputs never satisfied at all, since
    # THEIR sentinels are correctly gated off "IF Scale Up Route"'s false lane) that
    # hangs the merge forever instead of leaving it correctly dormant. Re-sourced from
    # "IF Scale Up Route"'s FALSE lane (source_out_idx=1) — the exact same idiom the
    # pre-fork sentinels ("Contacts/Companies/Unsupported Absent Sentinel") already use
    # — so in scale_up mode NEITHER sentinel runs at all, and "Decide Company Action
    # Merge" gets zero deliveries on every input (dormant, not stalled), matching
    # "Merge Company"'s own already-correct behaviour. `rows` is unchanged for every
    # non-scale_up request: the false lane delivers every event row whenever scale_up
    # is not requested, byte-identical to what "Parse HubSpot Event" delivered before.
    _add_starved_lane_sentinel(
        nodes, conns, "Recompute Not Requested Sentinel", "IF Scale Up Route",
        'if (rows.length > 0 && rows[0].recompute !== true) return [{}]; return [];',
        [dca("IF Company Recompute")],
        sx, sy, source_out_idx=1,
    )
    sy += 120
    # The inverse: in recompute mode, "IF Company Skip" and everything downstream of it
    # (the whole companies provider/research/judge waterfall) never runs at all, so
    # "Merge Company"'s own 3 inputs are starved too. Its cascade would otherwise
    # satisfy "Decide Company Action"'s Merge-Company-side input, EXCEPT "Merge
    # Company"'s own first-line identity-drop filter reduces an all-marker wave to ZERO
    # output, which never propagates on its own (Rule 1 — found running the walker
    # against this exact scenario) — feed that index directly too, alongside the 3
    # starved "Merge Company" inputs.
    _add_starved_lane_sentinel(
        nodes, conns, "Recompute Requested Sentinel", "IF Scale Up Route",
        'if (rows.length > 0 && rows[0].recompute === true) return [{}]; return [];',
        [mc("IF Research Needed", 1),
         mc("IF Needs Judge", 1),
         mc("Apply Judge Verdict"),
         # "IF Company Skip" never runs in recompute mode either, so its Build Response
         # lane (E) AND Lane F ("Build Research Failure Response", downstream of the
         # waterfall this mode never reaches) both need a direct feed too.
         br("IF Company Skip"),
         br("Build Research Failure Response"),
         dca("Merge Company")],
        sx, sy, source_out_idx=1,
    )
    sy += 120

    # --- Contacts: fed from "Enrichment Gate" itself (single producer once its own
    # merge above fires) — covers BOTH "contacts genuinely absent" (the pre-fork marker
    # already makes this node fire once, with a blank-identity row that Enrichment
    # Gate's OWN existing identity check already routes to action:"skip" — see
    # ENRICH_GATE's `if (!ik.email && ...) action = "skip"`) and "contacts present but
    # every real row decided skip" as the SAME condition.
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Waterfall Absent Sentinel", "Enrichment Gate",
        'if (rows.length > 0 && rows.every((r) => r.action === "skip")) return [{}]; '
        'return [];',
        [mw("IF Contact Research Needed", 1),
         mw("IF Contact Needs Judge", 1),
         mw("Apply Contact Judge Verdict"),
         br("HubSpot Create"),
         br("HubSpot Update"),
         br("IF Enrich", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts None Skip Sentinel", "Enrichment Gate",
        'if (rows.length > 0 && rows.every((r) => r.action !== "skip")) return [{}]; '
        'return [];',
        [br("Skip (NoOp)")],
        sx, sy,
    )
    sy += 120

    # --- Contacts research/judge sub-gates: NEVER `set_always_output_data` on
    # "IF Contact Research Needed"/"IF Contact Needs Judge" themselves — their TRUE
    # branches trigger a real (paid) Claude web-research/judge call, and forcing a
    # marker into whichever branch happens to be empty on a given batch would burn one
    # of those calls on a row that never asked for it. Each sentinel below reads the
    # SAME field the corresponding IF already tests off its own single-producer
    # predecessor, and delivers straight to the merge input — never through the IF.
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Research All Needed Sentinel", "Contact Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed === true)) '
        'return [{}]; return [];',
        [mw("IF Contact Research Needed", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Research None Needed Sentinel", "Contact Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed !== true)) '
        'return [{}]; return [];',
        [mw("IF Contact Needs Judge", 1),
         mw("Apply Contact Judge Verdict")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Judge All Needed Sentinel", "Contact Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge === true)) '
        'return [{}]; return [];',
        [mw("IF Contact Needs Judge", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts Judge None Needed Sentinel", "Contact Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge !== true)) '
        'return [{}]; return [];',
        [mw("Apply Contact Judge Verdict")],
        sx, sy,
    )
    sy += 120

    # --- Contacts create/enrich split: fed from "Decide Action" (single producer, and
    # the exact field "IF Create"/"IF Enrich" already test) — never from "HubSpot
    # Create"/"HubSpot Update" (feeding a marker to an HTTP node would fire a bogus
    # call); every target below is a Build Response merge INPUT INDEX directly.
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts None Create Sentinel", "Decide Action",
        'if (rows.length > 0 && !rows.some((r) => r.action === "create")) '
        'return [{}]; return [];',
        [br("HubSpot Create")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts All Create Sentinel", "Decide Action",
        'if (rows.length > 0 && rows.every((r) => r.action === "create")) '
        'return [{}]; return [];',
        [br("HubSpot Update"),
         br("IF Enrich", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts NonCreate None Enrich Sentinel", "Decide Action",
        'const nc = rows.filter((r) => r.action !== "create"); '
        'if (nc.length > 0 && !nc.some((r) => r.action === "enrich")) return [{}]; '
        'return [];',
        [br("HubSpot Update")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Contacts NonCreate All Enrich Sentinel", "Decide Action",
        'const nc = rows.filter((r) => r.action !== "create"); '
        'if (nc.length > 0 && nc.every((r) => r.action === "enrich")) return [{}]; '
        'return [];',
        [br("IF Enrich", 1)],
        sx, sy,
    )
    sy += 120

    # --- Companies: the exact mirror of the contacts block above, one level deeper
    # (Company Gate -> IF Company Recompute -> IF Company Skip, vs. contacts' single
    # Enrichment Gate -> IF Provider Processing Needed). "Companies Waterfall Absent"
    # only ever matters in normal (non-recompute) mode — RECOMPUTE_REQUESTED already
    # forces "skip" -> "enrich" inside ENRICH_CO_GATE, so no row can read
    # action==="skip" in recompute mode, and "Recompute Requested Sentinel" above is
    # what covers that mode instead.
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Waterfall Absent Sentinel", "Company Gate",
        'if (rows.length > 0 && rows.every((r) => r.action === "skip")) return [{}]; '
        'return [];',
        [mc("IF Research Needed", 1),
         mc("IF Needs Judge", 1),
         mc("Apply Judge Verdict"),
         br("Adapt Company Create"),
         br("HubSpot Company Update"),
         br("IF Company Enrich", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies None Skip Sentinel", "Company Gate",
        'if (rows.length > 0 && rows.every((r) => r.action !== "skip")) return [{}]; '
        'return [];',
        [br("IF Company Skip")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Research All Needed Sentinel", "Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed === true)) '
        'return [{}]; return [];',
        [mc("IF Research Needed", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Research None Needed Sentinel", "Research Trigger Gate",
        'if (rows.length > 0 && rows.every((r) => r.research_needed !== true)) '
        'return [{}]; return [];',
        [mc("IF Needs Judge", 1),
         mc("Apply Judge Verdict"),
         br("Build Research Failure Response")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Judge All Needed Sentinel", "Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge === true)) '
        'return [{}]; return [];',
        [mc("IF Needs Judge", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies Judge None Needed Sentinel", "Judge Gate",
        'if (rows.length > 0 && rows.every((r) => r.needs_judge !== true)) '
        'return [{}]; return [];',
        [mc("Apply Judge Verdict")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies None Create Sentinel", "Decide Company Action",
        'if (rows.length > 0 && !rows.some((r) => r.action === "create")) '
        'return [{}]; return [];',
        [br("Adapt Company Create")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies All Create Sentinel", "Decide Company Action",
        'if (rows.length > 0 && rows.every((r) => r.action === "create")) '
        'return [{}]; return [];',
        [br("HubSpot Company Update"),
         br("IF Company Enrich", 1)],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies NonCreate None Enrich Sentinel", "Decide Company Action",
        'const nc = rows.filter((r) => r.action !== "create"); '
        'if (nc.length > 0 && !nc.some((r) => r.action === "enrich")) return [{}]; '
        'return [];',
        [br("HubSpot Company Update")],
        sx, sy,
    )
    sy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Companies NonCreate All Enrich Sentinel", "Decide Company Action",
        'const nc = rows.filter((r) => r.action !== "create"); '
        'if (nc.length > 0 && nc.every((r) => r.action === "enrich")) return [{}]; '
        'return [];',
        [br("IF Company Enrich", 1)],
        sx, sy,
    )
    sy += 120

    # "IF Research Errored" is the ONE place `set_always_output_data` (not a bypass
    # sentinel) is correct: whenever it runs at all, research genuinely happened for at
    # least one row, and its OTHER branch ("Validate Research Output" -> "Judge Gate") is
    # a cheap decision Code node, never a paid call — the SAME reasoning 70-02 accepted
    # for "Set Review"/"HubSpot Associate Company" (a flag that can never race a
    # co-starved input, because at most one of a routing IF's two branches is ever empty
    # when the node ran at all). Covers "Build Research Failure Response" (Lane F) for
    # the "research happened, no error" case; the "no research at all" case is covered
    # by "Companies Research None Needed Sentinel" above.
    set_always_output_data(nodes, ["IF Research Errored"])

    # Phase 70 Plan 03 Task 2 (D-70-07): "Build Refusal Row" is "Build Response Merge"'s
    # ELEVENTH input — a genuinely new producer discovered after `splice_merge_before`
    # already sized that merge to its original ten, added via `_append_merge_input`
    # rather than folded into the splice. It delivers on exactly two scenarios (a
    # list-expansion refusal, or a scale-up dispatch confirmation) that are BOTH
    # mutually exclusive with the normal chain — in either one, none of the OTHER ten
    # inputs' real producers ever run, so "Refusal Fired Sentinel" below (fed FROM this
    # node, the same starved-lane mechanism used throughout this build) feeds all ten of
    # them directly whenever this node delivers anything.
    refusal_row_index = _append_merge_input(nodes, conns, build_response_merge, "Build Refusal Row")
    _add_starved_lane_sentinel(
        nodes, conns, "Refusal Fired Sentinel", "Build Refusal Row",
        'if (rows.length > 0) return [{}]; return [];',
        [br("Skip (NoOp)"),
         br("HubSpot Create"),
         br("HubSpot Update"),
         br("IF Enrich", 1),
         br("Unsupported Object Type"),
         br("IF Company Skip"),
         br("Build Research Failure Response"),
         br("Adapt Company Create"),
         br("HubSpot Company Update"),
         br("IF Company Enrich", 1)],
        sx, sy,
    )
    sy += 120
    # The inverse: the normal chain ran (this input's own real producer never fires this
    # execution) — fed from "Parse HubSpot Event" (single producer, runs on every
    # request except a list-expansion refusal, where Parse HubSpot Event never runs at
    # all and the real producer above covers it instead), guarded on `scale_up !== true`
    # so it stays silent on a scale-up dispatch (where "Build Scale Up Ack" ->
    # "Build Refusal Row" delivers the real content) — the same idiom "Recompute Not/
    # Requested Sentinel" use for the identical reason.
    _add_starved_lane_sentinel(
        nodes, conns, "Refusal Row Absent Sentinel", "Parse HubSpot Event",
        'if (rows.length > 0 && rows[0].scale_up !== true) return [{}]; return [];',
        [(build_response_merge, refusal_row_index)],
        sx, sy,
    )
    sy += 120

    # Phase 70 Plan 04 (D-70-04): broadcasts "Build Credits Summary"'s single
    # `remaining_credits` item onto every row "Build Response Merge" delivers —
    # combineAll (cartesian, mirrors "Source By Field Broadcast" in build_cloud()).
    # "Credit Request" is now fed from all three mutually-exclusive per-execution
    # entry points (Parse HubSpot Event / IF List Expanded false / the scale-up path
    # already covered via Parse HubSpot Event), so "Build Credits Summary" always
    # delivers exactly once — this cannot starve.
    #
    # "Filter Build Response Rows" sits BETWEEN the two: "Build Response Merge" is
    # append-mode with 11 inputs, most of them starved-lane sentinels emitting a bare
    # `{}` on every execution where their own real terminal did not fire — Build
    # Response's OWN `.filter(non-empty)` used to drop those before ever computing
    # anything. combineAll is a cartesian product: broadcasting a NON-empty
    # `{remaining_credits: [...]}` item onto EVERY one of those 10 empty sentinels
    # would make each of them non-empty too, defeating that filter and reaching Build
    # Response as 11 rows instead of 1 (found by node --test). Filtering here, BEFORE
    # the broadcast, keeps the cartesian product 1-to-1.
    nodes.append(code_node(
        "Filter Build Response Rows",
        "// Filter Build Response Rows — Phase 70 Plan 04 (D-70-04).\n"
        "// Drops starved-lane sentinel markers BEFORE the credits broadcast — see this "
        "splice's own comment.\n"
        "return $input.all().filter((it) => Object.keys(it.json || {}).length > 0);\n",
        0, 0,
    ))
    _old_brm_target = conns["Build Response Merge"]["main"][0][0]["node"]
    conns["Build Response Merge"] = {
        "main": [[{"node": "Filter Build Response Rows", "type": "main", "index": 0}]]}
    conns["Filter Build Response Rows"] = {"main": [[{"node": _old_brm_target, "type": "main", "index": 0}]]}
    # --- Phase 70 Plan 05 Task 2 (D-70-14): each write gate's REFUSAL lane ------------
    # Placed AFTER the whole sentinel network above, because `mirror_index` DERIVES each
    # refusal input's "the gate never ran" sentinels from the ones already feeding that
    # write's own terminal — a hand-written list of ~30 sentinel names would go stale the
    # first time one is added. See wire_gate_refusal_lane's docstring for why the refusal
    # cannot simply share the terminal's input (an armed MIXED batch drops the permitted
    # row's real arrival — caught with the offline walker, not reasoned about).
    for _gate_write, _real_terminal in [
        ("HubSpot Create", "HubSpot Create"),
        ("HubSpot Update", "HubSpot Update"),
        ("HubSpot Company Update", "HubSpot Company Update"),
        ("HubSpot Company Create", "Adapt Company Create"),
    ]:
        wire_gate_refusal_lane(
            nodes, conns, _gate_write, build_response_merge, sx, sy,
            mirror_index=_merge_input_index(conns, _real_terminal, build_response_merge))
        sy += 120

    splice_carry_merge_after(nodes, conns, "Filter Build Response Rows", "Build Credits Summary",
                              merge_name="Credits Broadcast", combine_by="combineAll")

    # =========================================================================
    # Phase 70 Plan 11 (D-70-20): this lane's own routing-IF-direct-to-Merge audit,
    # deferred by plan 70-10 (`mergeInputContract.test.mjs`'s PENDING list). Every one
    # of the 28 edges below was found by that same static contract, read straight off
    # the just-built graph — never hand-inventoried — and is retargeted through a
    # pass-through in one call, at the VERY END of this builder so no `_merge_input_
    # index`/lambda lookup elsewhere in this function (many of which resolve an index
    # off one of these exact sources, e.g. `eg("IF Name Searchable", 1)`) runs against
    # an edge this call has already moved.
    _retarget_all_if_direct_edges(nodes, conns, [
        # --- carry merges: an HTTP-hop's own carry_source is a routing IF's branch ---
        ("IF List Input", 0, "List By Name Carry Merge"),
        ("IF Bare Event", 0, "HubSpot Fetch By Id Carry Merge"),
        ("IF Has Email", 0, "HubSpot Search Carry Merge"),
        ("IF Linkedin Searchable", 0, "HubSpot Linkedin Search Carry Merge"),
        ("IF Name Searchable", 0, "HubSpot Name Search Carry Merge"),
        ("IF Lusha Enabled", 0, "Lusha Result Carry Merge"),
        ("IF Apollo Enabled", 0, "Apollo Result Carry Merge"),
        ("IF ZoomInfo Needs Mint", 0, "ZoomInfo Mint Carry Merge"),
        ("IF Company Bare Event", 0, "HubSpot Company Fetch By Id Carry Merge"),
        ("IF Company Bare Event", 1, "HubSpot Company Search Carry Merge"),
        ("IF Lusha Company Enabled", 0, "Lusha Company Result Carry Merge"),
        ("IF Apollo Org Enabled", 0, "Apollo Org Result Carry Merge"),
        ("IF ZoomInfo Company Needs Mint", 0, "ZoomInfo Mint Company Carry Merge"),
        ("IF ZoomInfo Usage Needs Mint", 0, "ZoomInfo Usage Mint Carry Merge"),
        ("HubSpot Company Create Write Gate IF", 0, "HubSpot Company Create Carry Merge"),
        # --- fan_in convergence merges: a routing IF's own branch reaches the gate/
        # response directly alongside the "real work happened" lane ---
        ("IF Name Searchable", 1, "Enrichment Gate Merge"),
        ("IF Contact Research Needed", 1, "Merge Winners Fan-In"),
        ("IF Contact Needs Judge", 1, "Merge Winners Fan-In"),
        ("IF Enrich", 1, "Build Response Merge"),
        ("IF Company Recompute", 0, "Decide Company Action Merge"),
        ("IF Company Skip", 0, "Build Response Merge"),
        ("IF Research Needed", 1, "Merge Company Fan-In"),
        ("IF Needs Judge", 1, "Merge Company Fan-In"),
        ("IF Company Enrich", 1, "Build Response Merge"),
        # --- write-gate refusal lanes: `wire_gate_refusal_lane`'s own direct edge,
        # documented in its own docstring as this lane's job to retarget ---
        ("HubSpot Create Write Gate IF", 1, "Build Response Merge"),
        ("HubSpot Update Write Gate IF", 1, "Build Response Merge"),
        ("HubSpot Company Create Write Gate IF", 1, "Build Response Merge"),
        ("HubSpot Company Update Write Gate IF", 1, "Build Response Merge"),
    ], sx, sy)
    sy += 120

    # Phase 70 Plan 11 (D-70-20): "Build Response Merge" declared fifteen inputs —
    # over n8n's own ten-input cap (`merge_node`'s docstring) — before this call.
    # Grouped by lane exactly as the plan's own action text asks: every CONTACTS
    # terminal (including the contacts write-gate refusal inputs, 11-12) in one
    # stage, every COMPANIES terminal (plus 13-14) in another, and the two mutually-
    # exclusive whole-batch-refusal terminals (unsupported object type, "Build
    # Refusal Row") in a third — each group computed from the SAME index table this
    # comment sits above (the sentinel dump this plan ran against the pre-split
    # graph), never re-derived by hand against the split graph.
    split_merge_into_stages(
        nodes, conns, build_response_merge,
        groups=[
            [0, 1, 2, 3, 11, 12],      # contacts terminals + contacts refusal lanes
            [4, 5, 6, 7, 8, 13, 14],   # companies terminals + companies refusal lanes
            [9, 10],                  # unsupported object type + whole-batch refusal
        ],
    )

    return {
        "id": "LVenrichmentCloud01",
        "name": "LV Enrichment (Cloud template)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
    }


# =============================================================================
# BACKEND STATUS workflow (Phase 25 Plan 02, D-14) — the credit-only slice of
# `hubspot/backend-status`. A NEW workflow file, deliberately NOT a second trigger inside
# "LV Enrichment (Cloud template)": the enrichment workflow's own `Lusha Usage`/`Apollo
# Usage`/ZoomInfo usage-subgraph nodes fork off `Parse HubSpot Event` and run at the START
# of a real enrichment call, well before that call's own `Build Response` assembles. A
# responder wired onto that branch would race ahead of `Build Response` and answer a real
# enrichment POST with the wrong body — a regression this separate file cannot introduce.
# Phase 27 (STATUS-01..06) grows this same file into full health; this plan ships only the
# credit slice.
# =============================================================================

# Single-item node, mirroring ENRICH_CREDIT_REQUEST's "never reads $input" discipline —
# its output cardinality can never track anything upstream, so it always emits exactly
# one item. Unlike the enrichment lane's Credit Request (which reflects the CALLER's
# per-batch providers_requested), this probes ALL THREE providers UNCONDITIONALLY: a
# status check has no notion of which providers a batch will use (D-10, research A4).
ENRICH_STATUS_CREDIT_REQUEST = r"""// Status Credit Request — Phase 25 Plan 02 (D-10, research A4).
// Probes ALL THREE providers unconditionally — a status check has no notion of which
// providers a batch uses.
return [{ json: { providers_requested: __PROVIDER_NAMES__ } }];
""".replace("__PROVIDER_NAMES__", json.dumps(provider_registry.PROVIDER_NAMES))

# Phase 25 Plan 02 (D-10/D-17, T-25-03/T-25-05) — the response-assembly node. Reads each
# usage probe BY NAME through the SAME guarded nodeAll idiom ENRICH_BUILD_RESPONSE uses (a
# not-executed node -> [] -> the unreadable marker; an error-carrying item -> the
# unreadable marker) and NEVER falls back to a number — a defaulted numeric value would be
# indistinguishable from a real balance, which is exactly the defect D-10 exists to
# prevent. Emits ONLY an extracted number-or-null, a `configured` boolean (always true
# here — this endpoint probes all three canonical providers unconditionally, so there is
# no "not configured" case to represent, unlike the admin CLI's env-var gate), an explicit
# `unreadable` boolean, a short synthesized error label (never the provider's own raw
# error text), and an HTTP status code — never a raw provider response body (T-25-03).
ENRICH_STATUS_BUILD_RESPONSE = inline("providerSelection.js") + r"""

// --- n8n wrapper: Build Credit Status (Phase 25 Plan 02) ---
// Phase 70 Plan 04 (D-70-04): fed by "ZoomInfo Usage Result Carry Merge" — the merged
// item carries `providers_requested` (stamped on the row at "Status Credit Request")
// and `lusha_result`/`apollo_result`/`zoominfo_result` (each nested by its own Wrap
// node earlier in this straight-line chain — ZoomInfo's is nested too, deliberately,
// so a never-executed probe (`zoominfo_result` absent) stays distinguishable from one
// that ran but returned an unrecognizable body; leaving it unwrapped at top level
// would have made `raw` always truthy, since it would be the merged item itself). No
// by-name read of any usage node.
function httpStatus(raw) {
  if (!raw) return null;
  const candidates = [raw.statusCode, raw.httpCode, raw.status,
    raw.response && raw.response.status, raw.response && raw.response.statusCode];
  for (const c of candidates) {
    if (c !== undefined && c !== null && c !== "") {
      const n = Number(c);
      if (Number.isFinite(n)) return n;
    }
  }
  return null;
}
const merged = ($input.first() && $input.first().json) || {};
const providers_requested = merged.providers_requested || [];
const RAW_BY_PROVIDER = { lusha: merged.lusha_result, apollo: merged.apollo_result, zoominfo: merged.zoominfo_result };
const balances = providers_requested.map((provider) => {
  const raw = RAW_BY_PROVIDER[provider];
  const status = httpStatus(raw);
  let credits = null;
  let error = null;
  if (!raw) {
    error = "not_executed";
  } else if (raw.error) {
    error = status ? ("http_" + status) : "provider_error";
  } else {
    credits = extractCredits(provider, raw);
    if (credits === null) error = "unrecognized_response_shape";
  }
  return { provider, configured: true, credits, unreadable: credits === null, error, status };
});
return [{ json: { balances, checked_at: new Date().toISOString() } }];
"""

# Phase 27 Plan 01 — the full-health assembly node. Extends Build Credit Status's
# balances with the four HubSpot count searches (requested-unresolved / awaiting-review,
# companies + contacts, D-07c) and a credential-health block for the three providers plus
# HubSpot itself (D-08/T-27-04). Reads every upstream node BY NAME through the same
# guarded nodeAll idiom Build Credit Status uses; every count runs through
# backendStatus.js's extractSearchTotal so a failed/refused search lands as `null`, never
# `0` (STATUS-06). Only `.total` is ever read off a search response — row payloads are
# never pulled for a badge count.
ENRICH_STATUS_BUILD_STATUS = inline("backendStatus.js") + r"""

// --- n8n wrapper: Build Status (Phase 27 Plan 01) ---
// Phase 70 Plan 04 (D-70-04): fed by "HS Review Contacts Carry Merge" — the merged item
// carries `balances`/`checked_at` (from "Build Credit Status", never wrapped since it
// seeded this leg of the chain rather than being a hop across it), three nested
// `hs_*_result` search responses (wrapped by earlier hops in this straight-line chain),
// and the LAST search's raw response unwrapped at top level. No by-name read.
function httpStatus(raw) {
  if (!raw) return null;
  const candidates = [raw.statusCode, raw.httpCode, raw.status,
    raw.response && raw.response.status, raw.response && raw.response.statusCode];
  for (const c of candidates) {
    if (c !== undefined && c !== null && c !== "") {
      const n = Number(c);
      if (Number.isFinite(n)) return n;
    }
  }
  return null;
}
// A search node's own probe outcome IS its credential-health signal (Pitfall 1) —
// independent of whether any enrichment run happened recently.
function searchProbe(raw) {
  if (!raw) return { configured: true, status: null, value: null };
  if (raw.error) return { configured: true, status: httpStatus(raw), value: null };
  return { configured: true, status: 200, value: extractSearchTotal(raw) };
}

const merged = ($input.first() && $input.first().json) || {};
const balances = Array.isArray(merged.balances) ? merged.balances : [];
const balanceByProvider = {};
for (const b of balances) balanceByProvider[b.provider] = b;

const companiesRequested = searchProbe(merged.hs_requested_companies_result);
const companiesReview = searchProbe(merged.hs_review_companies_result);
const contactsRequested = searchProbe(merged.hs_requested_contacts_result);
const contactsReview = searchProbe(merged);

const health = ["lusha", "apollo", "zoominfo"].map((provider) => {
  const b = balanceByProvider[provider] || {};
  return { source: provider,
    ...deriveSourceHealth({ configured: b.configured === true, status: b.status, value: b.credits }) };
});
// HubSpot's own credential health: the requested-companies probe is the canonical
// signal — same credential as all four searches, so a refusal there IS the HubSpot
// credential-health finding (D-08).
health.push({ source: "hubspot", ...deriveSourceHealth(companiesRequested) });

const body = buildStatusBody({
  counts: {
    companies_requested_unresolved: companiesRequested.value,
    companies_awaiting_review: companiesReview.value,
    contacts_requested_unresolved: contactsRequested.value,
    contacts_awaiting_review: contactsReview.value,
  },
  health,
  checked_at: merged.checked_at,
});

return [{ json: { ...body, balances } }];
"""


# Awaiting-review ORs the two independent reasons a record needs a human. MODULE level,
# not local to one builder: Phase 27's status surface COUNTS the queue with it and Phase
# 30's queue read LISTS the queue with it. Two copies would let the count and the list
# disagree about what "flagged" means — the operator would be told there are N to work and
# handed a different set. Same reasoning as 30 D-25, which had to widen `not_flagged`
# because the decision endpoint's predicate had already drifted from this one.
AWAITING_REVIEW_GROUPS = [
    [{"propertyName": "lv_enrichment_needs_review", "operator": "EQ", "value": "true"}],
    [{"propertyName": "lv_icp_needs_review", "operator": "EQ", "value": "true"}],
]


def build_backend_status_cloud():
    """Phase 25 Plan 02 (D-14) + Phase 27 Plan 01 — `hubspot/backend-status`, full health.

    Straight line, deliberately NOT a fan-out (D-14): Status Webhook Trigger -> Status
    Credit Request -> Lusha Usage -> Apollo Usage -> the shared ZoomInfo usage subgraph ->
    Build Credit Status -> four HubSpot count searches (requested-unresolved /
    awaiting-review, companies + contacts) -> Build Status -> Respond to Webhook. Every
    probe node uses onError: continueRegularOutput and reads nothing off its incoming
    item, so a failing probe passes an error item along the SAME single chain instead of
    stopping it — the chain guarantees exactly one item reaches the responder and every
    probe (provider AND HubSpot alike) has already run by the time it does, unlike the
    enrichment lane's per-batch fan-out (tolerable there, not tolerable for a status read).

    Reuses the enrichment workflow's own node names for the three probes verbatim (`Lusha
    Usage`, `Apollo Usage`, the ZoomInfo usage subgraph's names) — NODE_CREDENTIAL_MAP is
    keyed by node name across every built workflow, so this reuse costs zero new
    credential registration. Only `Status Webhook Trigger` is new, and it binds the SAME
    shared webhook-secret credential the enrichment trigger binds.
    """
    nodes = []
    y = 300
    x = 220

    # Native Header Auth on the trigger itself (T-25-04) — same mechanism, same credential
    # ("LV Enrichment Webhook") as the enrichment workflow's Webhook Trigger; not left open
    # because this endpoint is read-only.
    webhook = {
        "parameters": {"httpMethod": "POST", "path": "hubspot/backend-status",
                       "responseMode": "responseNode", "authentication": "headerAuth", "options": {}},
        "id": nid("w"), "name": "Status Webhook Trigger",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [x, y],
    }
    nodes.append(webhook)

    x += 220
    nodes.append(code_node("Status Credit Request", ENRICH_STATUS_CREDIT_REQUEST, x, y))

    lusha_credit = provider_registry.PROVIDER_REGISTRY["lusha"]["credit"]
    apollo_credit = provider_registry.PROVIDER_REGISTRY["apollo"]["credit"]

    x += 220
    nodes.append(_credit_http_node(
        "Lusha Usage", lusha_credit["url"], lusha_credit["method"], x, y, auth="header"))
    # Phase 70 Plan 04 (D-70-04): straight-line chain, so each HTTP hop's response is
    # nested under a distinct key (mirrors the enrichment lane's provider waterfall)
    # and re-attached to the row by a carry merge — never a by-name read downstream.
    nodes.append(code_node("Wrap Lusha Usage Result", _wrap_provider_result_js("lusha_result"), x, y))

    x += 220
    nodes.append(_credit_http_node(
        "Apollo Usage", apollo_credit["url"], apollo_credit["method"], x, y, auth="header"))
    nodes.append(code_node("Wrap Apollo Usage Result", _wrap_provider_result_js("apollo_result"), x, y))

    # ZoomInfo: the SAME 5-node Token Gate/IF Needs Mint/Mint/Cache Token/Usage subgraph
    # the enrichment lane's credit branch uses, sharing the identical sd.zoominfo cache key
    # (Bug A fix, live 2026-07-28) — this endpoint never mints its own ungated token.
    x += 220
    zoom_usage_nodes, zoom_usage_conns, zoom_usage_entry, zoom_usage_exit = (
        _zoom_split_usage_subgraph("Status Credit Request", x, y))
    nodes.extend(zoom_usage_nodes)

    x += 880
    nodes.append(code_node("Build Credit Status", ENRICH_STATUS_BUILD_RESPONSE, x, y))

    # Phase 27 Plan 01 — four HubSpot count searches, one per (object type x question),
    # chained sequentially after the credit probes (D-14: never fanned out, so the
    # responder cannot fire before every probe — provider AND HubSpot alike — has run).
    # Requested-but-unresolved uses OR'd filter groups, not a single group of NEQ
    # predicates: HubSpot's NEQ operator does not match a record whose property is
    # absent, and a record that was requested but never touched has no status value at
    # all (Pitfall 2/plan note) — group A covers the property-absent case, group B the
    # has-a-value-but-not-a-terminal-one case.
    REQUESTED_UNRESOLVED_GROUPS = [
        [{"propertyName": "lv_enrichment_requested", "operator": "EQ", "value": "true"},
         {"propertyName": "lv_enrichment_status", "operator": "NOT_HAS_PROPERTY"}],
        [{"propertyName": "lv_enrichment_requested", "operator": "EQ", "value": "true"},
         {"propertyName": "lv_enrichment_status", "operator": "NEQ", "value": "complete"},
         {"propertyName": "lv_enrichment_status", "operator": "NEQ", "value": "needs_review"}],
    ]
    x += 220
    hs_req_co = _hs_http_search_node(
        "HS Requested Search (Companies)", "company", x, y,
        filter_groups=REQUESTED_UNRESOLVED_GROUPS, properties_csv="hs_object_id", limit=1)
    nodes.append(hs_req_co)
    nodes.append(code_node("Wrap HS Requested Companies Result",
                            _wrap_provider_result_js("hs_requested_companies_result"), x, y))

    x += 220
    hs_review_co = _hs_http_search_node(
        "HS Review Search (Companies)", "company", x, y,
        filter_groups=AWAITING_REVIEW_GROUPS, properties_csv="hs_object_id", limit=1)
    nodes.append(hs_review_co)
    nodes.append(code_node("Wrap HS Review Companies Result",
                            _wrap_provider_result_js("hs_review_companies_result"), x, y))

    x += 220
    hs_req_ct = _hs_http_search_node(
        "HS Requested Search (Contacts)", "contact", x, y,
        filter_groups=REQUESTED_UNRESOLVED_GROUPS, properties_csv="hs_object_id", limit=1)
    nodes.append(hs_req_ct)
    nodes.append(code_node("Wrap HS Requested Contacts Result",
                            _wrap_provider_result_js("hs_requested_contacts_result"), x, y))

    x += 220
    hs_review_ct = _hs_http_search_node(
        "HS Review Search (Contacts)", "contact", x, y,
        filter_groups=AWAITING_REVIEW_GROUPS, properties_csv="hs_object_id", limit=1)
    nodes.append(hs_review_ct)

    # Phase 70 Plan 04 (D-70-04): nests the raw ZoomInfo response under its own key too
    # (was left unwrapped at top level, which made a genuinely-never-executed probe
    # indistinguishable from "ran, but the merged item itself has no `.data[...]`
    # usage entries" — `raw` was always the truthy merged object either way).
    nodes.append(code_node("Wrap ZoomInfo Usage Result",
                            _wrap_provider_result_js("zoominfo_result"), x, y))
    x += 220
    nodes.append(code_node("Build Status", ENRICH_STATUS_BUILD_STATUS, x, y))

    x += 220
    nodes.append({
        "parameters": {"respondWith": "allIncomingItems", "options": {}},
        "id": nid("rw"), "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
        "position": [x, y],
    })

    conns = chain([
        "Status Webhook Trigger", "Status Credit Request", "Lusha Usage",
        "Wrap Lusha Usage Result", "Apollo Usage", "Wrap Apollo Usage Result",
        zoom_usage_entry,
    ])
    conns.update(zoom_usage_conns)
    conns.update(chain([
        zoom_usage_exit, "Build Credit Status",
        hs_req_co["name"], "Wrap HS Requested Companies Result",
        hs_review_co["name"], "Wrap HS Review Companies Result",
        hs_req_ct["name"], "Wrap HS Requested Contacts Result",
        hs_review_ct["name"],
        "Build Status", "Respond to Webhook",
    ]))
    # Phase 70 Plan 04 (D-70-04): re-attaches each hop's row across the chain — carry_source
    # for each merge is the node whose EXISTING single edge already fed the next hop before
    # this rewire, so item counts always agree (this whole chain is single-item, D-14).
    splice_carry_merge_after(nodes, conns, "Wrap Lusha Usage Result", "Status Credit Request",
                              merge_name="Lusha Usage Carry Merge")
    splice_carry_merge_after(nodes, conns, "Wrap Apollo Usage Result", "Lusha Usage Carry Merge",
                              merge_name="Apollo Usage Carry Merge")
    _zoom_usage_old_target = conns["ZoomInfo Usage"]["main"][0][0]["node"]
    conns["ZoomInfo Usage"] = {"main": [[{"node": "Wrap ZoomInfo Usage Result", "type": "main", "index": 0}]]}
    conns["Wrap ZoomInfo Usage Result"] = {"main": [[{"node": _zoom_usage_old_target, "type": "main", "index": 0}]]}
    splice_carry_merge_after(nodes, conns, "Wrap ZoomInfo Usage Result", "ZoomInfo Usage Token Gate",
                              merge_name="ZoomInfo Usage Result Carry Merge")
    splice_carry_merge_after(nodes, conns, "Wrap HS Requested Companies Result",
                              "ZoomInfo Usage Result Carry Merge",
                              merge_name="HS Requested Companies Carry Merge")
    splice_carry_merge_after(nodes, conns, "Wrap HS Review Companies Result",
                              "HS Requested Companies Carry Merge",
                              merge_name="HS Review Companies Carry Merge")
    splice_carry_merge_after(nodes, conns, "Wrap HS Requested Contacts Result",
                              "HS Review Companies Carry Merge",
                              merge_name="HS Requested Contacts Carry Merge")
    splice_carry_merge_after(nodes, conns, "HS Review Search (Contacts)",
                              "HS Requested Contacts Carry Merge",
                              merge_name="HS Review Contacts Carry Merge")

    notes = [{
        "content": (
            "## LV Backend Status — full health (Phase 25 Plan 02 + Phase 27 Plan 01, D-14)\n"
            "`hubspot/backend-status`: three provider usage probes, then four HubSpot "
            "count searches, all run SEQUENTIALLY (never fanned out) so every probe — "
            "provider AND HubSpot alike — has completed before the single `Respond to "
            "Webhook` fires.\n\n"
            "An unreadable balance (Apollo's non-master key 403s by design on this "
            "account) renders as an explicit `unreadable: true` / `credits: null` "
            "marker, never as zero (D-10/D-08). The two HubSpot counts "
            "(requested-unresolved, awaiting-review) are reported for companies AND "
            "contacts; a count the backend could not read is `null`, never `0` "
            "(STATUS-06). Reads only — zero write nodes anywhere in this chain.\n\n"
            "**Webhook Trigger** binds the SAME shared `LV Enrichment Webhook` "
            "credential the enrichment trigger uses — one operator secret works "
            "against both endpoints with no new provisioning."
        ), "x": x, "y": y + 260, "h": 320, "w": 520,
    }]
    for i, n in enumerate(notes, start=1):
        nodes.append({
            "parameters": {"content": n["content"], "height": n["h"], "width": n["w"]},
            "id": nid("s"), "name": f"Sticky Note {i}",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "position": [n["x"], n["y"]],
        })

    return {
        "id": "LVBackendStatusCloud01",
        "name": "LV Backend Status (Cloud template)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
    }


# =============================================================================
# SCHEDULED MAINTENANCE workflow (Phase 16-02) — SJ-1/2/3 + dedupe sweep + review loop.
# Companion to "LV Enrichment (Cloud template)" (build_enrichment_cloud): that workflow
# reacts to a webhook event; this one is the background reconciliation + human-review
# layer SYSTEM-CONTRACT commits to. Predicates key on pipeline-owned INPUTS only
# (Approach C, spec §0.7) — never a derived ICP output (score/tier/scored-at).
# =============================================================================

ENRICH_EXTRACT_SEARCH_ROWS = WRITE_REQUEST_JS + r"""// Extract Search Rows — HubSpot search envelope -> one row per matched record.
// Shared by the SJ-1/SJ-3/dedupe/review scheduled branches (Phase 16-02) — none of them
// need enrichmentGate's existingRecord shape (that is SJ-2 + Company Gate's job, via a
// dedicated Adapt step mirroring ENRICH_ADAPT_CO_SEARCH's contract).
const item = $input.first();
const res = (item && item.json) || {};
const rows = Array.isArray(res.results) ? res.results : (res.properties ? [res] : []);
// D-70-12 (Phase 70 Plan 05 Task 1): "SJ-1 Set Requested" is fed directly by this node
// (no intermediate Code node), so it is the emitter for that gate. Harmless elsewhere
// (SJ-3/dedupe/review each transform the row again before their own write, and stamp
// their own write_request there) — action "enrich" matches every scheduled-maintenance
// gate's action; `domain` is whatever this search fetched (company rows carry it,
// contact rows don't and get null, same as before).
return rows.map((r) => ({ json: { ...(r.properties || {}), hs_object_id: r.id,
  write_request: _buildWriteRequest("enrich", r.id, (r.properties || {}).domain || null, null) } }));
"""

# fix(40) / WINDOWS.md #3: ENRICH_EXTRACT_SEARCH_ROWS's `{...properties, hs_object_id}`
# shape (shared by SJ-1/SJ-3/dedupe/review) is NOT what "LV Enrichment (Cloud
# template)"'s Parse HubSpot Event expects (objectId/objectType/subscriptionType — the
# same shape a genuine HubSpot private-app webhook event carries). SJ-3 is the only one
# of those four branches that dispatches into enrichment, so this reshape is SJ-3-only —
# reshaping ENRICH_EXTRACT_SEARCH_ROWS itself would change the other three branches'
# contract for no reason. One event per matched company; "company.propertyChange" +
# "lv_enrichment_requested" mirror what actually changed to make SJ-3's search match it.
ENRICH_SJ3_BUILD_DISPATCH_EVENT = r"""// SJ-3 Build Dispatch Event — reshape Extract Rows'
// {...properties, hs_object_id} into the event shape Parse HubSpot Event parses (see
// ENRICH_PARSE_EVENT_CLOUD: event.objectId/objectType/subscriptionType/occurredAt).
// Phase 44 Plan 01 (GATE-01): only rows the SJ-3 Dispatch Gate permitted (sj3_dispatch)
// become events. When every row is declined this returns [], the Execute Workflow node
// receives zero items and does not run, and the tick costs 1 execution rather than 1+N —
// the zero-items-stops-the-chain behaviour established live at execution 22 (see the
// HubSpot Search comments above; Plan 03 re-verifies it empirically for this lane).
return $input.all().filter((it) => it.json.sj3_dispatch === true).map((it) => ({ json: {
  objectId: it.json.hs_object_id,
  objectType: "company",
  subscriptionType: "company.propertyChange",
  propertyName: "lv_enrichment_requested",
  occurredAt: new Date().toISOString(),
} }));
"""

# Phase 44 Plan 02 (CAP-01, D-10/D-11) — the SJ-3 dispatch cap, DERIVED at build time,
# never written as a literal. One allowance, one home: config/execution_budget.yaml
# (read the same way _COMPANY_POLICY_FIELDS reads field_policy.yaml; Phase 45's ALARM-03
# reads the same key). Direct indexing on purpose — a missing key must KeyError the
# build, not default (T-44-07: a misread config silently changing unattended spend).
_EXECUTION_BUDGET = yaml.safe_load(
    (ROOT / "config" / "execution_budget.yaml").read_text())

# Ticks-per-month for one schedule trigger, per _schedule_trigger's own documented
# arithmetic (30-day month: 15 min = 2,880/month, hourly = 720, daily = 30).
# tests/test_execution_budget.py re-derives this table from the committed artifacts
# rather than importing it, so builder/config drift is visible (CAP-03).
_TICKS_PER_MONTH = {
    "minutes": 43200.0, "hours": 720.0, "days": 30.0, "weeks": 30.0 / 7.0, "months": 1.0}

# The (field, interval) pair SJ-3's trigger is actually built with — the SAME tuple is
# passed to _schedule_trigger below, so re-timing the trigger necessarily moves the cap
# (CAP-01 fails the moment these diverge into two hand-kept numbers).
SJ3_TRIGGER_SCHEDULE = ("days", 1)

# cap = allowance x share / ticks-per-month, minus the tick's own execution (GATE-01's
# cost model is 1 + dispatched). At the shipped daily cadence with a 0.5 share this
# derives to 40 — floor(2500 x 0.5 / 30) - 1 — the sanity anchor from D-10; the number
# is DERIVED here, never written.
SJ3_DISPATCH_CAP = int(
    _EXECUTION_BUDGET["monthly_execution_allowance"]
    * _EXECUTION_BUDGET["sj3_dispatch_share"]
    / (_TICKS_PER_MONTH[SJ3_TRIGGER_SCHEDULE[0]] / SJ3_TRIGGER_SCHEDULE[1])
) - 1
# A sub-daily cadence can drive the derived cap to zero or below (15-min cadence:
# floor(1250 / 2880) - 1 = -1), which would defer everything forever. Fail the build
# loudly instead of baking a cap that dispatches nothing.
assert SJ3_DISPATCH_CAP >= 1, (
    f"SJ3_DISPATCH_CAP derived to {SJ3_DISPATCH_CAP} — the {SJ3_TRIGGER_SCHEDULE} cadence "
    "leaves no per-tick budget; re-time the trigger or raise the share in "
    "config/execution_budget.yaml")

# Phase 44 Plan 01 (GATE-01/D-01/D-02) — SJ-3's per-record dispatch permission check.
# WRITE_SAFETY_GATE_JS is embedded VERBATIM (D-02: one definition of "permitted", so the
# poller cannot drift from the enrichment lane's own write gates), followed by the pure
# routing module and an n8n wrapper delegating to _writeSafetyAllows per row.
ENRICH_SJ3_DISPATCH_GATE = (
    WRITE_SAFETY_GATE_JS + "\n" + inline("sj3DispatchGate.js")
    # Plan 02 (CAP-01): the cap is baked as a build-time constant, like every other
    # budget-ish constant in this builder — never computed at n8n runtime, where the
    # arithmetic would live in a Code node nothing tests.
    + "\nconst SJ3_DISPATCH_CAP = " + str(SJ3_DISPATCH_CAP)
    + ";  // derived: allowance x share / ticks-per-month - 1 (config/execution_budget.yaml)\n"
    + r"""
// n8n wrapper: SJ-3 Dispatch Gate — annotates EVERY row (sj3_dispatch / sj3_drain /
// deferred = neither) and returns them ALL, not only the permitted ones: the declined
// rows are what the drain branch consumes (DRAIN-01), and permitted-but-over-cap rows
// keep their flag for the next tick (D-09). The "enrich" action mirrors the SJ-1/SJ-2
// spliced gates; row.domain exists because SJ-3's search requests it (BUG 24's class).
const rows = $input.all().map((it) => it.json);
const annotated = sj3Gate(rows, {
  allows: (row) => _writeSafetyAllows("enrich", row.hs_object_id || null, row.domain || null),
  cap: SJ3_DISPATCH_CAP,
});
return annotated.map((row) => ({ json: row }));
"""
)


# Phase 44 Plan 02 (GATE-02, D-13/D-14) — the one node that runs on a fully gate-closed
# tick. It is fed DIRECTLY from SJ-3 Dispatch Gate (a third consumer of the gate's single
# output) and must never sit downstream of any branch whose item count can reach zero:
# a zero-item feed makes a node not run at all (the zero-items-stops-the-chain behaviour
# established live at execution 22), which is exactly the invisibility this node exists
# to solve. On a fully gate-closed tick, Build Dispatch Event returns [] and the dispatch
# chain never runs — GATE-01's cost bound — but THIS node still receives the annotated
# rows and records what happened.
ENRICH_SJ3_TICK_OUTCOME = r"""// SJ-3 Tick Outcome — reads the sj3_tick summary the gate
// stamped on every row and emits ONE item carrying the named outcome plus the counts:
// `gate_closed` when permitted is zero and found is non-zero, `capped_partial` when
// deferred is non-zero, `dispatched` otherwise (CAP-02: a capped tick says found vs
// dispatched, never silent truncation).
//
// "Gate closed" vs "found nothing to do" (GATE-02): a tick where the search matched
// nothing produces no items at all through SJ-3 Extract Rows, so the gate and this node
// do not run — the absence of this node's output IS the distinguishing signal between
// the two.
//
// D-14: quiet and recorded, never loud. Disarmed is the normal resting state, so a tick
// declining 61 records while disarmed is correct behaviour, not an incident — this node
// must not throw, must not set an error status, must not emit a warning. Phase 45's
// burn-rate alarm is the thing that should be loud.
//
// D-13: this is one of the two observation points and the EPHEMERAL one — n8n prunes
// execution history at ~2,500 rows; the durable evidence is the drained records' own
// lv_enrichment_status.
const t = ($input.first().json || {}).sj3_tick || {};
return [{ json: {
  sj3_tick_outcome: t.outcome || "unknown",
  found: t.found ?? null,
  permitted: t.permitted ?? null,
  dispatched: t.dispatched ?? null,
  declined: t.declined ?? null,
  deferred: t.deferred ?? null,
  cap: t.cap ?? null,
} }];
"""


def _sj3_drain_gate_js() -> str:
    """Phase 44 Plan 01 (DRAIN-01/D-05/D-06) — the drain branch's own authority check.
    Deliberately NOT routed through _write_gate_js/splice_write_gates: both hardcode the
    shared gate whose allowlist branch is unconditional, which D-06 forbids here (an
    allowlisted drain would clear only records that were never stuck). The declaration
    literal derives from WRITE_SAFETY_DEFAULTS via _write_safety_const, so the committed
    artifact's value is pinned by tests/test_write_gate_coverage.py the same way every
    other write-safety constant is."""
    return _write_safety_const("ALLOW_SJ3_DRAIN_WRITES") + r"""
// SJ-3 Drain Gate — passes through only rows the dispatch gate declined this same tick
// (sj3_drain), feeding the terminal write that clears the trigger flag so a stuck queue
// cannot re-form (DRAIN-01).
//
// D-05 bound, repeated at the point of authority: this constant may only ever authorise
// setting lv_enrichment_requested to "false" and lv_enrichment_status to "skipped" on
// records declined in the same tick. It removes queued work; it cannot create or alter
// data. It is NOT precedent for defaulting any other write on — a false-defaulting drain
// would run only inside an armed window, which is precisely when the queue is not stuck.
//
// D-06: this gate deliberately does not call the shared write-safety helper and does not
// consult the record allowlist. The stuck queue is overwhelmingly non-allowlisted
// records — that is the failure mode itself. (Exclusions described in words on purpose:
// the coverage tests negative-grep this node's entire jsCode for the excluded
// identifiers, and a Code node's comments are part of its jsCode.)
if (ALLOW_SJ3_DRAIN_WRITES !== "true") return [];  // exact-string gate (CLAUDE.md §21)
return $input.all().filter((it) => it.json.sj3_drain === true);
"""

ENRICH_SJ2_EPOCH_CUTOFF = r"""// SJ-2 epoch-ms cutoff — HubSpot's LT operator on a datetime property expects epoch
// MILLISECONDS, not an ISO date string (16-RESEARCH.md Deliverable 5).
return [{ json: { cutoff_ms: Date.now() - 180 * 86400000 } }];
"""

# Same CONTRACT as ENRICH_ADAPT_CO_SEARCH (0 results => {} => create) but for a BATCH
# staleness search, not a per-row identity lookup: each matched company's own properties/id
# from the SJ-2 Search ARE the existingRecord Company Gate needs to confirm staleness
# (RT-5/SJ-2) — no pairing with an upstream identity list required.
ENRICH_ADAPT_SJ2_SEARCH = r"""// Adapt SJ-2 Search -> existingRecord (ENRICH_ADAPT_CO_SEARCH shape).
const item = $input.first();
const res = (item && item.json) || {};
const rows = Array.isArray(res.results) ? res.results : (res.properties ? [res] : []);
return rows.map((r) => {
  const existingRecord = { ...(r.properties || {}), hs_object_id: r.id };
  return { json: { existingRecord, lookup_failed: false } };
});
"""

# CLASSIFY ONLY (dedupeSweep.js's own header comment) — this node never writes HubSpot;
# the review-flag write is a separate downstream node. dedupeSweep.js is FROZEN and reads
# contact-shaped properties.{email,phone,linkedin_url}; the canonical HubSpot property is
# lv_linkedin_url (PN-1 rename), so the wrapper maps it here rather than touch the module.
ENRICH_DEDUPE_SWEEP = inline(
    "normalizeEmail.js", "normalizePhone.js", "resolveIdentity.js", "dedupeSweep.js"
) + WRITE_REQUEST_JS + r"""

// --- n8n wrapper: Dedupe Sweep (CLASSIFY ONLY) ---
const rows = $input.all().map((it) => it.json);
const records = rows.map((r) => ({
  id: r.hs_object_id,
  properties: { email: r.email, phone: r.phone, linkedin_url: r.lv_linkedin_url },
}));
const report = dedupeSweep(records);
// BUG 18: this lane's write node was a native hubspot node running `contact:update` — an
// operation ContactDescription.ts does not define (contacts have upsert, not update), so
// it would have silently returned json:null with status:success, exactly like BUG 10's
// company:search. Converging this lane onto the shared `properties` row contract (the same
// move BUG 11/16 made for the review lane above) lets it use the credential-bound PATCH
// node instead of an operation that does not exist.
// D-70-12 (Phase 70 Plan 05 Task 1): "Dedupe Set Needs Review Write Gate" is fed
// directly by this node's own output — it is the emitter for that gate.
return report.to_review_ids.map((id) => ({
  json: {
    hs_object_id: id,
    to_review_reason: "dedupe_sweep",
    properties: { lv_enrichment_needs_review: "true" },
    write_request: _buildWriteRequest("enrich", id, null, null),
  },
}));
"""

# reviewApply.js's consumer contract is documented on the module itself — see its header.
ENRICH_APPLY_REVIEW = inline(
    "taxonomy.generated.js", "hubspotEnums.generated.js", "hubspotEnums.js",
    "mergeCompanies.js", "reviewApply.js") + WRITE_REQUEST_JS + r"""

// --- n8n wrapper: Apply Review — Extract Search Rows already flattened id + properties,
// so the row itself IS the freshly-refetched compare-and-set baseline. ---
return $input.all().map((it) => {
  const row = it.json;
  const candidateJson = row.lv_enrichment_review_candidate_json || "[]";
  const result = reviewApply(candidateJson, row);
  // BUG 11/16: `Review Apply Update` shipped `updateFields: {}` and wrote nothing. The
  // patch to apply is canonicalPatch + clearPatch; expose it as `properties` so this lane
  // carries the same row contract as the enrichment lane and can use the shared
  // credential-bound PATCH node.
  const properties = { ...(result.canonicalPatch || {}), ...(result.clearPatch || {}) };
  // BUG 25: this constructed a fresh row and DROPPED everything else — including `domain`,
  // which the downstream write gate reads for its allowlist check. BUG 24 added `domain` to
  // Review Search's property list, but it died here, two nodes before the gate: the row-carry
  // family (BUG 12/21) landing between a fix and the thing it was meant to enable. Spread the
  // row; `properties` and the result keys are assigned after, so they still win.
  // Phase 31 (BUG 28/29): `stale` alone used to route "Review IF Stale" — an invalid-enum
  // result (empty canonicalPatch/clearPatch, non-empty `invalid`) is NOT stale, so it fell
  // to the apply branch and PATCHed an empty body. `review_skip` covers BOTH reasons
  // nothing should be written: reviewApply reported stale, OR the assembled patch is empty.
  const review_skip = result.stale === true || Object.keys(properties).length === 0;
  // D-70-12 (Phase 70 Plan 05 Task 1): "Review Apply Update Write Gate" is fed via
  // "Review IF Stale"'s false branch, whose nearest upstream Code node is this one.
  const write_request = _buildWriteRequest("enrich", row.hs_object_id || null, row.domain || null, null);
  return { json: { ...row, hs_object_id: row.hs_object_id, ...result, properties, review_skip, write_request } };
});
"""


def _schedule_trigger(name, x, y, field, interval_value):
    """A schedule trigger. EVERY FIRE IS ONE BILLED n8n EXECUTION, and the plan allowance
    lives in config/execution_budget.yaml (the single home, D-11) -- so the intervals below
    are a budget, not a preference. Arithmetic before changing one: 15 minutes =
    2,880/month PER TRIGGER, hourly = 720, daily = 30 (executable form: _TICKS_PER_MONTH).
    Three sub-daily triggers alone blew the entire monthly allowance while doing no work;
    tests/test_execution_budget.py now fails a schedule whose idle floor does that again.

    Node names deliberately carry NO interval ("SJ-3 Trigger", not "SJ-3 Trigger (15 min)"):
    the operator can change cadence at runtime via the plugin's `cadence` action, so a name
    that encodes one goes stale the moment they do.
    """
    return {
        "parameters": {"rule": {"interval": [{"field": field, f"{field}Interval": interval_value}]}},
        "id": nid("st"), "name": name,
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [x, y],
    }


def _hs_search_json_body_expr(filter_groups, properties, limit):
    """Renders (filter_groups, properties, limit) as a single n8n `={{ JSON.stringify(...) }}`
    expression — the same envelope the native HubSpot search node's filterGroupsUi/
    additionalFields.properties produces (groups OR, filters-within-group AND — RESEARCH Pitfall 3),
    and the same shape HS_CO_SEARCH_BODY_EXPR already proves works for the raw-HTTP
    local-live variant. A filter value that is itself an n8n expression (`={{ ... }}`, e.g.
    reading another node by name) is unwrapped and interpolated as a raw JS expression —
    never re-stringified — so dynamic filters keep working inside the single top-level
    expression block; a plain value is JSON-encoded as a JS literal.

    `limit` goes through the SAME unwrapping, so a caller-driven page size (30-04's queue
    read) can read a clamped value from a parse node by name. An int renders identically to
    the old `str(limit)` form (`json.dumps(100) == "100"`), so every existing call site is
    byte-unchanged — proven by rebuild-diff, not by this sentence.

    Phase 61 Plan 02 Task 2 (REVIEW-C5): a filter may carry `values` (plural) instead of
    `value` — HubSpot CRM v3's `IN`/`NOT_IN` operators take an array under `values`, never
    a single scalar under `value`. Every pre-existing call site uses `value` only, so this
    is additive: a filter dict with `value` renders exactly as before, and `values` is the
    new, separate key this task's IN filter uses."""
    def render_value(v):
        if isinstance(v, str) and v.startswith("={{") and v.endswith("}}"):
            return v[3:-2].strip()
        return json.dumps(v)

    def render_filter(f):
        parts = [f'propertyName: {json.dumps(f["propertyName"])}',
                 f'operator: {json.dumps(f["operator"])}']
        if "value" in f:
            parts.append("value: " + render_value(f["value"]))
        if "values" in f:
            parts.append("values: " + render_value(f["values"]))
        return "{ " + ", ".join(parts) + " }"

    groups_js = ", ".join(
        "{ filters: [ " + ", ".join(render_filter(f) for f in group) + " ] }"
        for group in filter_groups
    )
    props_js = ", ".join(json.dumps(p) for p in properties)
    return (
        "={{ JSON.stringify({ filterGroups: [ " + groups_js + " ], "
        "properties: [" + props_js + "], limit: " + render_value(limit) + " }) }}"
    )


_HS_SEARCH_URLS = {
    "company": "https://api.hubapi.com/crm/v3/objects/companies/search",
    "contact": "https://api.hubapi.com/crm/v3/objects/contacts/search",
}


def _hs_http_search_node(name, resource, x, y, filter_groups, properties_csv, limit=100):
    """Credential-bound httpRequest replacement for the native HubSpot node's `search`
    operation — company and contact resources (BUG 10, Phase 16.6; BUG 23, Phase 17.01).

    BUG 10 (companies): n8n's HubSpot node has no `operation: "search"` for resource:company
    at all, so a native-node company search silently returns json:null.

    BUG 23 (contacts): unlike BUG 10, `resource:contact operation:search` genuinely EXISTS
    and genuinely returns the record on a hit — this is why every enrichment contacts
    execution ever run (8-15, 19, all against an existing record) passed. The defect is
    zero-hit behavior: the native node emits ZERO items on zero hits and n8n stops the
    chain there (live-established by execution 22, BUG 22, the ingest lane) — so the node
    is correct for half its input space and fatal for the other half, and index-aligned
    adapters (`search[i]` / `fetched[i]`) silently misalign once an upstream row's search
    emits no item at all.

    Both resources POST directly to the real CRM v3 search endpoint, bypassing the node's
    operation dispatch entirely — same credential (predefinedCredentialType/hubspotAppToken
    reuses "LV HubSpot", the exact credential NODE_CREDENTIAL_MAP already binds these node
    NAMES to), same filter/property contract the native search operation took, so callers
    migrate with an identical argument list. Any resource outside this table still
    hard-fails, so the migration cannot silently spread to a resource nobody audited.

    Phase 21 Plan 01 closed the class: "Dedupe Search (candidate contacts)" — the last
    remaining native-search call site — moved onto this helper too, and the native-search
    node builder was deleted outright. This is now the ONLY way a search node gets built
    in this file."""
    if resource not in _HS_SEARCH_URLS:
        raise ValueError(
            f"_hs_http_search_node has no URL mapping for resource={resource!r} "
            f"(known: {sorted(_HS_SEARCH_URLS)})"
        )
    props = [p.strip() for p in properties_csv.split(",") if p.strip()]
    body = _hs_search_json_body_expr(filter_groups, props, limit)
    return _http_node(
        name, _HS_SEARCH_URLS[resource], x, y,
        auth="hubspot", json_body=body,
    )


def _hs_http_patch_node(name, resource, x, y):
    """Credential-bound httpRequest replacement for the native hubspot node's `update`
    operation on BOTH contacts and companies — BUG 11, Phase 16.7-01. Mirrors
    _hs_http_search_node's shape and docstring standard above, for the same class of
    reason: the native node cannot do the job. Unlike BUG 10 (no `operation: "search"`
    exists at all for resource:company), BUG 11 is that the native `update` operation
    exists but this builder never populates its `updateFields` — both "HubSpot Update"
    and "HubSpot Company Update" are committed with `updateFields: {}`, an empty map,
    documented in this file's own prior comment as a placeholder "populated at deploy/
    operator-config time, not baked by this builder." No such deploy-time population
    exists anywhere in scripts/deploy_n8n_workflows.py — the computed patch lives on
    `$json.properties` and is referenced by nothing. A canary fired against the native
    node would issue a property-less update, proving nothing about the non-clobber merge.

    This node PATCHes the real CRM v3 object endpoint directly with `{"properties":
    $json.properties}` — the exact patch "Decide Action"/"Decide Company Action" compute.

    Node NAME is preserved (both "HubSpot Update" and "HubSpot Company Update" are
    already mapped in scripts/deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP), so
    credential binding by name keeps working unchanged. `auth="hubspot"` reuses the SAME
    provisioned "LV HubSpot" credential the native nodes used (predefinedCredentialType/
    nodeCredentialType:hubspotAppToken) — never a new credential object, never $env/$vars.

    `on_error=None` is the deliberate departure from every other httpRequest node this
    builder emits (which default to continueRegularOutput): a WRITE node must fail its
    execution on a rejected PATCH, not flow on as a healthy item reaching Build Response
    and returning a plausible 200 — CONTEXT Locked Decision 3's exact "judge from runData,
    never from HTTP status" lesson, now enforced structurally instead of only by policy.

    Hard-fails on any resource outside contacts/companies, mirroring
    _hs_http_search_node's hard-fail on anything but "company" — so this cannot silently
    spread to a resource this plan never audited."""
    if resource not in ("contacts", "companies"):
        raise ValueError(f"_hs_http_patch_node only supports contacts/companies — got resource={resource!r}")
    url = "=https://api.hubapi.com/crm/v3/objects/" + resource + "/{{ $json.hs_object_id }}"
    body = "={{ JSON.stringify({ properties: $json.properties }) }}"
    return _http_node(
        name, url, x, y,
        auth="hubspot", json_body=body, method="PATCH", on_error=None,
    )


def _hs_http_create_node(name, resource, x, y):
    """Credential-bound httpRequest replacement for the native hubspot node's `create`
    operation — BUG 13, the create-side twin of BUG 11, found 2026-07-29 while auditing
    the write lane before exercising creates live. 16.7-01 deliberately left the create
    nodes native and pinned them as unverified; this is that debt.

    The native nodes were broken TWO ways at once, either of which alone would have made
    a create canary meaningless:

    1. `additionalFields: {}` — same empty-map placeholder as BUG 11, so the entire
       computed patch on `$json.properties` was discarded. A create would have produced a
       record carrying only its identifier.
    2. They read fields that DO NOT EXIST on the node feeding them. `Decide Action` /
       `Decide Company Action` emit exactly {action, object_type, hs_object_id, gap_flag,
       needs_review, properties} — verified from live execution 12's runData. Yet
       "HubSpot Company Create" read `$json.name || $json.identity_keys.companyName ||
       $json.identity_keys.domain` (all undefined — and dereferencing `identity_keys`
       would throw), and "HubSpot Create" read `$json.properties.email`, which is never
       present because `email` is manual_protected and can never promote into the patch.

    POSTing `{"properties": $json.properties}` to the collection endpoint fixes both: the
    real patch is sent, and nothing outside the Decide output's own shape is referenced.
    Node NAMES are preserved so NODE_CREDENTIAL_MAP binding by name keeps working, and
    `on_error=None` is retained for the same reason as the PATCH node — a rejected write
    must fail its execution rather than flowing on as a healthy item."""
    if resource not in ("contacts", "companies"):
        raise ValueError(f"_hs_http_create_node only supports contacts/companies — got resource={resource!r}")
    url = "https://api.hubapi.com/crm/v3/objects/" + resource
    body = "={{ JSON.stringify({ properties: $json.properties }) }}"
    return _http_node(
        name, url, x, y,
        auth="hubspot", json_body=body, method="POST", on_error=None,
    )


def _hs_update_set_property(name, resource, x, y, property_name, value_literal="true",
                            extra_properties=()):
    """Terminal dispatch write (SJ-1/SJ-2): sets ONE known custom boolean property to a
    static value on the matched record's id (review consensus #5 — a search that only
    matches rows never triggers enrichment on its own).

    `extra_properties` (Phase 44 Plan 01) is an optional sequence of additional
    (property, value) LITERAL pairs appended to customPropertiesValues — every key and
    value is baked into the built JSON, never runtime-computed, which is what makes a
    caller's patch narrowness structural rather than a runtime promise (DRAIN-02). Both
    pre-existing call sites pass nothing and are byte-unchanged."""
    id_key = "contactId" if resource == "contact" else "companyId"
    return {
        "parameters": {"resource": resource, "operation": "update",
                       id_key: "={{ $json.hs_object_id }}",
                       "updateFields": {"customPropertiesUi": {"customPropertiesValues": [
                           {"property": property_name, "value": value_literal},
                           *({"property": p, "value": v} for p, v in extra_properties),
                       ]}}},
        "id": nid("hu"), "name": name,
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x, y],
    }


def _execute_workflow_node(name, x, y, workflow_id, workflow_name, wait_for_sub=None):
    """`wait_for_sub` (Phase 61 Plan 06 Task 5, additive kwarg): omitted (None) preserves
    every existing call site's byte-identical `"options": {}` (SJ-3's own dispatch —
    n8n's own default applies, unchanged). Passing `False` bakes the detached
    `waitForSubWorkflow` shape 61-PREMISE-PROBE-VERDICT.json's P-13 measured live
    (`_p13_parent_workflow`'s own `{"waitForSubWorkflow": wait_for_sub}` shape) — a
    self-referencing dispatch must not wait on itself."""
    options = {} if wait_for_sub is None else {"waitForSubWorkflow": wait_for_sub}
    return {
        "parameters": {"source": "database",
                       "workflowId": {"__rl": True, "value": workflow_id, "mode": "list",
                                      "cachedResultName": workflow_name},
                       "mode": "each", "options": options},
        "id": nid("ew"), "name": name,
        "type": "n8n-nodes-base.executeWorkflow", "typeVersion": 1.2, "position": [x, y],
    }


# --- write-safety gate splice (BUG 15) ------------------------------------------------
# `_writeSafetyAllows()` and the ALLOW_HUBSPOT_* constants existed ONLY in
# wf_enrichment_cloud.json. `wf_scheduled_maintenance_cloud.json` and
# `wf_contact_ingest_cloud.json` carried SIX write nodes between them with no allowlist
# check at all, so activating either would have written to HubSpot with nothing bounding
# the blast radius. Found 2026-07-29 while auditing coverage after the write-path canary;
# both workflows are INACTIVE so there was never live exposure, and this closes the hole
# before either is ever switched on.
#
# Implemented as a splice rather than by editing each builder: the gate is inserted
# between a write node and whatever feeds it, so it cannot be forgotten for a write node
# added later — tests/test_write_gate_coverage.py asserts EVERY write node in EVERY cloud
# workflow sits directly behind one.
# D-70-12 (Phase 70 Plan 05 Task 1): the four-way identity fallback ladder this function
# used to carry (`hs_object_id || existingRecord.hs_object_id`, then a THREE-deep domain
# fallback through `identity_keys.domain`/`domain`/`properties.email`/`email`) is deleted
# outright, not extended — a row arriving without a `write_request` is refused, not
# rescued by falling back to whatever identity fields happen to be lying around on it.
def _write_gate_js(action: str) -> str:
    """D-70-14 (Phase 70 Plan 05 Task 2): stamps a verdict onto EVERY item — never
    filters any away. The paired IF node (`f"{write_name} Write Gate IF"`,
    `splice_write_gates` below) routes on `write_allowed`: true reaches the write node
    unchanged, false carries `action: "write_blocked"` plus a reason and is available to
    be wired onward as a real row rather than a silence. This function's OWN item count
    in must equal its item count out on every call — that invariant is what makes a
    refused row a row instead of a drop."""
    return WRITE_SAFETY_GATE_JS + (
        "\n// Reads ONLY the canonical `write_request` shape (D-70-12). A row with no\n"
        "// write_request is refused, not rescued by any fallback. Empty allowlist denies all.\n"
        "// D-70-14: maps every item to a verdict — never filters. Output count == input count.\n"
        "return $input.all().map((it) => {\n"
        "  var wr = it.json.write_request;\n"
        f"  var allowed = !!wr && _writeSafetyAllows({action!r}, wr.hs_object_id || null, wr.domain || null);\n"
        "  if (allowed) return { json: { ...it.json, write_allowed: true } };\n"
        "  var reason = !wr\n"
        "    ? 'no write_request emitted for this row'\n"
        "    : 'allowlist denied this write (test-record allowlist empty or non-matching)';\n"
        "  return { json: { ...it.json, write_allowed: false, action: 'write_blocked', write_blocked_reason: reason } };\n"
        "});\n"
    )


def _write_request_source_names(nodes_by_name, conns, target_name, _seen=None):
    """BFS backwards from `target_name`'s inbound edges, stopping expansion at the first
    Code node found on each path (routing IFs and Merges carry no jsCode of their own —
    the nearest Code node in the path is the one whose OWN return shape determines what
    the row looks like from there on, since none of this codebase's Code-node bodies
    spread a field they never mention). Returns the set of those Code node names."""
    if _seen is None:
        _seen = set()
    found = set()
    for src, spec in conns.items():
        if src in _seen:
            continue
        for outputs in spec.get("main", []):
            for conn in (outputs or []):
                if conn.get("node") == target_name:
                    _seen.add(src)
                    node = nodes_by_name.get(src)
                    if node is None:
                        continue
                    if node.get("type") == "n8n-nodes-base.code":
                        found.add(src)
                    else:
                        found |= _write_request_source_names(nodes_by_name, conns, src, _seen)
    return found


def assert_write_request_emitters(nodes, conns, gated):
    """D-70-12's generation-time half: for each gated write node, walk backwards to the
    nearest upstream Code node(s) and raise ValueError naming the write node and the
    source when a source's jsCode does not call `_buildWriteRequest` (the marker
    `_write_request_js()` stamps — same string-literal-marker approach as
    `_run_recovery_marker`/`assert_no_by_name_reads`, checked at generation time rather
    than trusted at runtime). Called from `splice_write_gates` after the gate is wired,
    so `f"{write_name} Write Gate"`'s inbound edges are exactly the write node's ORIGINAL
    predecessors, untouched by the splice."""
    nodes_by_name = {n["name"]: n for n in nodes}
    for write_name in gated:
        gate_name = f"{write_name} Write Gate"
        sources = _write_request_source_names(nodes_by_name, conns, gate_name)
        if not sources:
            raise ValueError(
                f"assert_write_request_emitters: {gate_name!r} (feeding {write_name!r}) "
                "has no upstream Code node emitting write_request"
            )
        for src in sources:
            js = nodes_by_name[src]["parameters"].get("jsCode", "")
            if "_buildWriteRequest(" not in js:
                raise ValueError(
                    f"assert_write_request_emitters: {write_name!r}'s upstream source "
                    f"{src!r} does not emit write_request"
                )


def splice_write_gates(nodes, conns, gated):
    """Insert a two-node IF-shaped write-safety gate in front of each named write node
    (D-70-14, Phase 70 Plan 05 Task 2 — reshaped from Task 1's single filtering Code
    node).

    `gated` maps write-node name -> the action string passed to _writeSafetyAllows
    ("create", "enrich" or "review"). Every inbound connection to the write node is
    re-pointed at the gate's Code node (`f"{write_name} Write Gate"`), which now STAMPS
    a `write_allowed` verdict onto every item rather than filtering any away. A paired
    IF node (`f"{write_name} Write Gate IF"`) then routes true items to the write node
    unchanged and false items out its own second output, carrying `action:
    "write_blocked"` and a reason.

    The IF's false output is deliberately left UNWIRED by this function — wiring it
    onward to a lane's response Merge is Task 2c/3's job, once each lane's own
    pre-gate refusal routing (the ingest precheck, the review precheck) is either
    removed or accounted for; wiring it here first would risk a Merge starving on a
    fully-refused batch before that accounting exists (see 70-05-SUMMARY.md's "Next
    Phase Readiness"). Until that lands, a refused row still travels no further than it
    did under Task 1's filter — every lane's existing precheck already diverts refused
    rows before they ever reach this gate, so behaviour is unchanged; only the shape of
    what a lane COULD do with the false branch has changed.

    Pure list/dict mutation over already-built structures — no builder needs to know
    about it. D-70-12: asserts every gated node's upstream emits the canonical
    `write_request` shape before returning, so a missed emitter fails generation rather
    than shipping a gate that silently denies (or, pre-this-plan, silently admits via a
    stale fallback) every row."""
    by_name = {n["name"]: n for n in nodes}
    for write_name, action in gated.items():
        target = by_name.get(write_name)
        if target is None:
            raise ValueError(f"splice_write_gates: no node named {write_name!r} to gate")
        gate_name = f"{write_name} Write Gate"
        gate_if_name = f"{write_name} Write Gate IF"
        gx, gy = target["position"][0] - 300, target["position"][1]
        nodes.append(code_node(gate_name, _write_gate_js(action), gx, gy))
        nodes.append(_if_bool_node(gate_if_name, "write_allowed", gx + 150, gy))
        for src, spec in conns.items():
            if src in (gate_name, gate_if_name):
                continue
            for outputs in spec.get("main", []):
                for conn in (outputs or []):
                    if conn["node"] == write_name:
                        conn["node"] = gate_name
        conns[gate_name] = {"main": [[{"node": gate_if_name, "type": "main", "index": 0}]]}
        conns[gate_if_name] = {"main": [
            [{"node": write_name, "type": "main", "index": 0}],  # true
            [],                                                    # false — unwired, see docstring
        ]}
    assert_write_request_emitters(nodes, conns, gated)
    return nodes, conns


# ---- explicit Merge nodes (Phase 70 Plan 02, D-70-01/D-70-02/D-70-04) -------
#
# typeVersion and parameter keys verified 2026-09-09 against n8n-io/n8n `master`
# (github.com/n8n-io/n8n, packages/nodes-base/nodes/Merge/): `Merge.node.ts`'s
# `defaultVersion: 3.2`; `v3/actions/versionDescription.ts` names `mode` values
# `append`/`combine`/`combineBySql`/`chooseBranch` and, when `mode: "combine"`, a
# `combineBy` selector `combineByFields`/`combineByPosition`/`combineAll`;
# `v3/helpers/descriptions.ts`'s `numberInputsProperty` (`numberInputs`, 2-10) and
# `clashHandlingProperties` (`options.clashHandling.values.resolveClash`, default
# `preferLast` generically but `combineByPosition.ts` overrides its OWN default to
# `addSuffix` — RENAMING clashing keys rather than overwriting them, surprising for a
# reader expecting a known field name, hence `merge_node` sets `preferLast` explicitly
# below rather than trusting that per-mode default). Source read via raw.githubusercontent.com,
# not training-data recall.
_TRIGGER_TYPES_BUILDER = {
    "n8n-nodes-base.webhook", "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.executeWorkflowTrigger",
}


def merge_node(name, x, y, *, inputs=2, mode="append", combine_by=None):
    """An `n8n-nodes-base.merge` node (D-70-01 the fan-in convergence Merge; D-70-02/
    D-70-04 the per-hop carry Merge). `mode="append"` concatenates whatever each input
    delivered (D-70-01's convergence use — every lane terminal's rows land in one list,
    once). `mode="combine"` (with `combine_by="combineByPosition"`, the default for that
    mode here) pairs input i of every configured input into ONE shallow-merged object —
    D-70-04's carry-across-an-HTTP-hop use, re-attaching a row's pre-hop fields to its
    post-hop response. `resolveClash: "preferLast"` is set explicitly for combine mode
    so a key present on more than one input keeps the LAST-wired input's value (this
    repo always wires the CARRIED ROW last, precisely so its identity fields win over
    whatever the HTTP response happens to also carry) — never n8n's own combineByPosition
    default of `addSuffix`, which would rename the clashing keys instead.

    OBLIGATION (research Pitfall 1): every configured input must deliver at least once
    per execution or this node never fires — n8n's own execution engine (verified via
    `packages/core/src/execution-engine/workflow-execute.ts::addNodeToBeExecuted`, which
    only advances a multi-input node to the execution stack once every declared input
    index has data) waits for ALL of them, exactly like this. Callers are responsible for
    ensuring a lane that can go genuinely empty still delivers something — see this
    module's ingest-lane sentinel nodes for the mechanism chosen there, and this
    docstring's own note on why a per-branch `alwaysOutputData` flag was tried and
    rejected for that specific convergence.

    WHY A MERGE, RATHER THAN A RUN-INDEXED RECOVERY (Phase 70 Plan 04 Task 3, D-70-01 —
    reasoning inherited from the now-deleted `n8n/code/nodeRunRecovery.js`, never kept
    as a fallback): a node with MORE THAN ONE inbound connection (e.g. a routing IF's
    several lanes converging on one gate) runs ONCE PER FIRING INBOUND EDGE within a
    single execution, not once on a merged item array. A downstream reader recovering
    that node BY NAME — `$('Node').all()` with no run index — gets only the node's MOST
    RECENT run (n8n's own documented behaviour), so a reader invoked once per lane
    silently collapses every earlier lane onto the SAME last run (F5, execution 12163,
    confirmed live 2026-09-09: a 4-row mixed batch lost both of its email-lane rows this
    way). n8n's own documented fix for "same run as the current node",
    `$('Node').all(0, $runIndex)`, is not sufficient either: a wave can be dropped
    ENTIRELY between the converged node and the reader (every row in one lane resolves
    to a terminal action and never reaches the reader at all), which shifts the raw run
    index out of alignment for every wave after the drop. A real Merge node sidesteps
    both failure modes structurally: it receives every firing lane's rows in the SAME
    execution and emits them as ONE array to its single downstream run, so there is no
    per-edge run to recover and no run index to keep aligned in the first place.
    """
    params = {"mode": mode, "numberInputs": inputs}
    if mode == "combine":
        params["combineBy"] = combine_by or "combineByPosition"
        params["options"] = {"clashHandling": {"values": {"resolveClash": "preferLast"}}}
    return {
        "parameters": params,
        "id": nid("m"), "name": name,
        "type": "n8n-nodes-base.merge", "typeVersion": 3.2, "position": [x, y],
    }


def classify_convergence(nodes_by_name, conns, target_name):
    """Which of the three convergence classes `target_name`'s inbound edges form
    (Phase 70 Plan 02 action text): only "entry_points" is refused by
    `splice_merge_before` — a Merge there hangs unconditionally, because exactly one
    trigger ever runs per execution and there is no node on the unused trigger's path
    that runs at all to satisfy it. "fan_in" (two-or-more edges that CAN both deliver in
    one execution) and "mutually_exclusive" (a routing IF's true/false both reaching the
    same next stage) both get a Merge — this function does not need to tell them apart,
    since both are safe to merge; it only needs to refuse the one class that is not.

    Classification: collect target_name's direct inbound source nodes; for each, walk
    the connection graph BACKWARD to the trigger-type node(s) that can reach it. If two
    or more sources have DISJOINT, non-empty trigger-ancestries, they can only ever be
    live in DIFFERENT executions (a webhook run vs. a sub-workflow run) — "entry_points".
    Otherwise every source can trace back to a trigger some other source ALSO traces back
    to (the common, single-trigger-workflow case), or the source count is under two —
    "fan_in".
    """
    sources = sorted({
        src for src, spec in conns.items()
        for outputs in (spec.get("main") or [])
        for conn in (outputs or [])
        if conn.get("node") == target_name
    })
    if len(sources) < 2:
        return "fan_in"

    reverse = {}
    for src, spec in conns.items():
        for outputs in (spec.get("main") or []):
            for conn in (outputs or []):
                reverse.setdefault(conn.get("node"), set()).add(src)

    def trigger_ancestors(start):
        seen = set()
        stack = [start]
        triggers = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            node = nodes_by_name.get(n)
            if node and node.get("type") in _TRIGGER_TYPES_BUILDER:
                triggers.add(n)
                continue
            for pred in reverse.get(n, ()):
                stack.append(pred)
        return triggers

    # Phase 70 Plan 03 (Rule 1 fix): the ORIGINAL check here required ALL ancestor sets
    # to be pairwise disjoint before returning "entry_points" — a mixed convergence (one
    # source truly on a different trigger, two others sharing a trigger with EACH OTHER
    # but not with the first) fell through to "fan_in" even though the first source can
    # never co-occur with the other two, exactly the hang this function exists to catch
    # (`Parse HubSpot Event`'s three-source case: `Execute Workflow Trigger` vs. the two
    # webhook-path branches, which share `Webhook Trigger` with EACH OTHER but not with
    # the sub-workflow trigger). The docstring's own contract — "if TWO OR MORE sources
    # have disjoint ancestries" — is a pairwise ANY, not an all-pairs partition; check
    # every pair.
    ancestor_sets = [trigger_ancestors(s) for s in sources]
    for i in range(len(ancestor_sets)):
        for j in range(i + 1, len(ancestor_sets)):
            a, b = ancestor_sets[i], ancestor_sets[j]
            if a and b and not (a & b):
                return "entry_points"
    return "fan_in"


def splice_merge_before(nodes, conns, target_name, *, merge_name=None):
    """Collects every inbound connection whose target is `target_name`, creates one
    Merge (`mode="append"`) with that many inputs, re-points each collected edge to a
    DISTINCT Merge input index (preserving the connections dict's current iteration
    order, so the walker's and n8n's input indices agree), and wires the Merge's single
    output to `target_name`. Returns the Merge node's name.

    Refuses (`ValueError`) a class "entry_points" convergence per
    `classify_convergence` — a later plan cannot copy a mechanical inventory row into a
    hang. Requires at least two inbound connections; a single inbound edge is not a
    convergence at all.
    """
    nodes_by_name = {n["name"]: n for n in nodes}
    if target_name not in nodes_by_name:
        raise ValueError(f"splice_merge_before: no node named {target_name!r}")

    classification = classify_convergence(nodes_by_name, conns, target_name)
    if classification == "entry_points":
        raise ValueError(
            f"splice_merge_before: {target_name!r} converges alternate ENTRY POINTS "
            "(exactly one trigger ever runs per execution) — a Merge here hangs "
            "unconditionally; refusing rather than generating a hang."
        )

    collected = []
    for src_name, spec in conns.items():
        for out_idx, outputs in enumerate(spec.get("main") or []):
            for conn in (outputs or []):
                if conn.get("node") == target_name:
                    collected.append(conn)
    if len(collected) < 2:
        raise ValueError(
            f"splice_merge_before: {target_name!r} has {len(collected)} inbound "
            "connection(s) — nothing to converge"
        )

    name = merge_name or f"{target_name} Merge"
    target = nodes_by_name[target_name]
    mx, my = target["position"][0] - 160, target["position"][1]
    nodes.append(merge_node(name, mx, my, inputs=len(collected), mode="append"))
    for input_index, conn in enumerate(collected):
        conn["node"] = name
        conn["index"] = input_index
    conns[name] = {"main": [[{"node": target_name, "type": "main", "index": 0}]]}
    return name


def split_merge_into_stages(nodes, conns, merge_name, groups, *, max_inputs=10):
    """Splits an over-wide append-mode Merge — more declared inputs than n8n's own
    per-node cap (`merge_node`'s own docstring; ten) — into per-group STAGE Merges,
    each within the cap, reconverging on the ORIGINAL `merge_name` node (Phase 70
    Plan 11, D-70-20's over-wide-Merge rule — "Build Response Merge" on the
    enrichment lane, fifteen inputs before this call). `merge_name` itself is never
    renamed or replaced — every consumer that already names it (its own downstream
    edge, and any external string naming the response terminal by node name) keeps
    working unchanged; only its OWN declared `numberInputs` shrinks to `len(groups)`,
    and each stage's single output becomes one of ITS inputs.

    `groups`: an ordered list of lists of the CURRENT (pre-split) input indices
    `merge_name` declares today. Every current index must appear in EXACTLY one
    group — a silently dropped index would starve exactly like an unfed Merge input
    already does (D-70-20's own class of defect, caught here at generation time
    rather than left to a replay to discover). Each group must fit within
    `max_inputs` — a group that still does not is this function's CALLER's bug
    (regroup; never call this function recursively to auto-subdivide).

    Mechanism: every edge currently feeding `merge_name` at one of a group's
    original indices is RE-POINTED (never copied) to a freshly created stage Merge,
    at a fresh 0-based index within that stage — so a sentinel/gate that already
    shares an original input with a real producer (the legitimate multi-producer-
    per-input case `mergeInputContract.test.mjs`'s own header documents) MOVES WITH
    IT onto the same stage, preserving that input's existing coverage exactly (the
    plan's own obligation: "a stage cannot starve where the wide Merge did not")."""
    nodes_by_name = {n["name"]: n for n in nodes}
    merge = nodes_by_name.get(merge_name)
    if merge is None:
        raise ValueError(f"split_merge_into_stages: no node named {merge_name!r}")
    original_inputs = merge["parameters"]["numberInputs"]

    seen = set()
    for group in groups:
        for i in group:
            if i in seen:
                raise ValueError(
                    f"split_merge_into_stages: input {i} appears in more than one group")
            seen.add(i)
        if len(group) > max_inputs:
            raise ValueError(
                f"split_merge_into_stages: a group of {len(group)} inputs exceeds "
                f"max_inputs={max_inputs} — regroup, do not call this recursively")
    if seen != set(range(original_inputs)):
        raise ValueError(
            f"split_merge_into_stages: groups must partition every current index "
            f"0..{original_inputs - 1} of {merge_name!r}; got {sorted(seen)}")

    edges_by_index = {i: [] for i in range(original_inputs)}
    for spec in conns.values():
        for outputs in (spec.get("main") or []):
            for conn in (outputs or []):
                if conn.get("node") == merge_name:
                    edges_by_index[conn["index"]].append(conn)

    mx, my = merge["position"][0] - 200, merge["position"][1] - 150
    for stage_i, group in enumerate(groups):
        stage_name = f"{merge_name} Stage {stage_i + 1}"
        nodes.append(merge_node(stage_name, mx, my + stage_i * 150, inputs=len(group), mode="append"))
        for new_idx, orig_idx in enumerate(group):
            for conn in edges_by_index[orig_idx]:
                conn["node"] = stage_name
                conn["index"] = new_idx
        conns[stage_name] = {"main": [[{"node": merge_name, "type": "main", "index": stage_i}]]}

    merge["parameters"]["numberInputs"] = len(groups)
    return merge_name


def set_always_output_data(nodes, names):
    """Sets `alwaysOutputData: true` on each named node (research Pitfall 1's
    mitigation): a node whose OWN computation would otherwise produce zero items still
    propagates one marker `{}` item, so a downstream Merge waiting on that lane does not
    hang forever. This ONLY rescues a node that actually RAN with some input and
    produced nothing — verified against n8n's own execution engine
    (`workflow-execute.ts::ensureAlwaysOutputData`, applied after `runNode` returns);
    it does nothing for a node that received ZERO input and was never dispatched at all.
    Placement is decided per call site — see the ingest lane's own comment for why a
    per-routing-IF placement was tried and rejected (it can race a slower real-data path
    converging on the same Merge input) in favour of a global, single-producer sentinel
    computed once from the complete decided-row set."""
    by_name = {n["name"]: n for n in nodes}
    for name in names:
        node = by_name.get(name)
        if node is None:
            raise ValueError(f"set_always_output_data: no node named {name!r}")
        node["alwaysOutputData"] = True
    return nodes


def splice_carry_merge_after(nodes, conns, http_name, carry_source, *,
                              merge_name=None, combine_by="combineByPosition",
                              source_out_idx=0):
    """D-70-04's carry mechanism, generalised: inserts a `mode="combine"` Merge
    immediately after `http_name` — input 0 is `http_name`'s own existing output edge
    (re-pointed, unchanged destination), input 1 is a NEW literal fan-out edge from
    `carry_source`. `carry_source` must already be the SAME delivery feeding `http_name`
    (its direct predecessor, or another node fed by that same predecessor) — that is
    what guarantees input 0 and input 1 always agree on item count and order, since
    they are two edges off the one wave that entered `http_name`. Every existing
    consumer of `http_name` is re-pointed to the new Merge; `http_name` itself is left
    otherwise untouched (this is Task 2's hand-wired "Associate Carry Merge" pattern,
    generalised into one reusable mechanism rather than left as a one-off — Phase 70
    Plan 02 Task 3).

    `source_out_idx` (Phase 70 Plan 04, D-70-04): which of `carry_source`'s OWN output
    branches already feeds `http_name` — 0 (default) for a single-output node or an
    IF/waterfall gate's TRUE branch, 1 for an IF's FALSE branch (e.g. "IF Company Bare
    Event"'s false lane feeds "HubSpot Company Search", never its true lane) — mirrors
    `_add_starved_lane_sentinel`'s own `source_out_idx` parameter exactly, so a carry
    fanned from the wrong branch cannot silently starve the Merge on every real request
    (T-70-13's mis-pairing risk, generalised to "never fires at all" rather than
    "fires with the wrong row").

    `combine_by` defaults to "combineByPosition" (pairs item i of each input into one
    shallow-merged object, carried-row-last winning any key clash per `merge_node`'s own
    docstring) — the shape every per-item HTTP hop on this lane needs. Pass
    `combine_by="combineAll"` for a genuine 1-to-N broadcast (a single config item onto
    every row), never for a per-item HTTP hop."""
    nodes_by_name = {n["name"]: n for n in nodes}
    if http_name not in nodes_by_name:
        raise ValueError(f"splice_carry_merge_after: no node named {http_name!r}")
    if carry_source not in nodes_by_name:
        raise ValueError(f"splice_carry_merge_after: no carry_source node named {carry_source!r}")

    name = merge_name or f"{http_name} Carry Merge"
    target = nodes_by_name[http_name]
    mx, my = target["position"][0] + 110, target["position"][1]
    nodes.append(merge_node(name, mx, my, inputs=2, mode="combine", combine_by=combine_by))

    old_spec = conns.get(http_name) or {"main": [[]]}
    old_first_output = (old_spec.get("main") or [[]])[0] or []
    conns[http_name] = {"main": [[{"node": name, "type": "main", "index": 0}]]}
    conns[name] = {"main": [old_first_output]}
    conns.setdefault(carry_source, {"main": [[]]})
    while len(conns[carry_source]["main"]) <= source_out_idx:
        conns[carry_source]["main"].append([])
    conns[carry_source]["main"][source_out_idx].append({"node": name, "type": "main", "index": 1})
    return name


def _merge_input_index(conns, source_name, merge_name, *, source_out_idx=0):
    """Looks up the input index `splice_merge_before` assigned `source_name` on
    `merge_name` (Phase 70 Plan 03) — used AFTER splicing to target a starved-lane
    sentinel's marker at the exact input a real lane's terminal already occupies, never a
    freshly-invented index that would silently grow the merge's `numberInputs` past what
    `splice_merge_before` actually collected."""
    for conn in (conns.get(source_name, {}).get("main") or [[]])[source_out_idx] or []:
        if conn.get("node") == merge_name:
            return conn["index"]
    raise ValueError(f"_merge_input_index: {source_name!r} (output {source_out_idx}) "
                      f"does not feed {merge_name!r}")


def _append_merge_input(nodes, conns, merge_name, source_name, *, source_out_idx=0):
    """Adds ONE more declared input to an ALREADY-created merge node (Phase 70 Plan 03
    Task 2, D-70-07) — `splice_merge_before` only ever sizes a merge to what it collected
    at splice time; this appends a genuinely NEW producer discovered later in the same
    build (`Build Refusal Row`), bumping `numberInputs` and wiring `source_name`'s output
    straight to the new index. Never used to re-wire an EXISTING edge — that stays
    `_merge_input_index`'s job. Returns the new index."""
    nodes_by_name = {n["name"]: n for n in nodes}
    merge = nodes_by_name.get(merge_name)
    if merge is None:
        raise ValueError(f"_append_merge_input: no node named {merge_name!r}")
    index = merge["parameters"]["numberInputs"]
    merge["parameters"]["numberInputs"] = index + 1
    conns.setdefault(source_name, {"main": [[]]})
    while len(conns[source_name]["main"]) <= source_out_idx:
        conns[source_name]["main"].append([])
    conns[source_name]["main"][source_out_idx].append(
        {"node": merge_name, "type": "main", "index": index})
    return index


def _add_merge_passthrough(nodes, conns, name, source, source_out_idx, x, y):
    """A plain Code pass-through inserted between a routing IF's branch and whatever it
    feeds (Phase 70 Plan 10, D-70-23's ingest-lane audit): this repo has never observed
    whether the live engine treats an IF's own empty branch as a delivery the way it
    does a Code node's empty output (D-70-01's addendum), and a routing IF must not
    have a direct edge to a Merge input while that question is open. The pass-through
    makes the answer irrelevant — fed zero items, IT never runs (the one rule this repo
    HAS observed, execution 12200), so the Merge input it feeds obeys that rule
    regardless of what the IF branch itself would have done. Returns the pass-through
    node's name; callers re-point their own downstream edge at it."""
    nodes.append(code_node(name,
        "// Pass-through — see build_cloud_workflows.py's own comment at this node's "
        "call site (_add_merge_passthrough).\n"
        "return $input.all();\n", x, y))
    conns.setdefault(source, {"main": [[]]})
    while len(conns[source]["main"]) <= source_out_idx:
        conns[source]["main"].append([])
    conns[source]["main"][source_out_idx].append({"node": name, "type": "main", "index": 0})
    return name


def _retarget_merge_edge_through_passthrough(nodes, conns, source, source_out_idx,
                                             merge_name, passthrough_name, px, py):
    """Finds the edge `source`'s output `source_out_idx` already has straight to
    `merge_name`, removes it, inserts a pass-through (`_add_merge_passthrough`) fed
    from the same `(source, source_out_idx)`, and re-points ITS output at the exact
    merge input index the direct edge used to occupy — so no merge input index moves,
    only what feeds it."""
    outputs = conns[source]["main"][source_out_idx]
    match = next((c for c in outputs if c.get("node") == merge_name), None)
    if match is None:
        raise ValueError(
            f"_retarget_merge_edge_through_passthrough: {source!r} output "
            f"{source_out_idx} has no direct edge to {merge_name!r}")
    outputs.remove(match)
    _add_merge_passthrough(nodes, conns, passthrough_name, source, source_out_idx, px, py)
    conns[passthrough_name] = {"main": [[
        {"node": merge_name, "type": "main", "index": match["index"]}]]}
    return match["index"]


def _retarget_all_if_direct_edges(nodes, conns, edges, x, y):
    """Applies `_retarget_merge_edge_through_passthrough` over a whole lane's worth of
    routing-IF-direct-to-Merge edges in one call (Phase 70 Plan 11, D-70-20's
    no-routing-IF-direct-edge rule, carried across the enrichment/local-live/review
    lanes plan 70-10 left on `mergeInputContract.test.mjs`'s PENDING list — this
    lane's own audit, deferred there by name). `edges`: an ordered list of
    `(source, source_out_idx, merge_name)` triples, each naming ONE existing direct
    edge — done at the very END of the calling builder, after every `_merge_input_
    index`/lambda lookup that resolves an index off one of these sources has already
    run, so retargeting (which never moves an input's INDEX, only what feeds it, per
    `_retarget_merge_edge_through_passthrough`'s own contract) cannot invalidate an
    index a sentinel/gate elsewhere in the same builder already baked in. Position
    is auto-incremented per edge so no two pass-throughs collide on the canvas;
    passthrough names are derived from the (source, merge_name) pair, never hand-
    listed, so this cannot go stale as edges are added or removed above."""
    py = y
    for source, source_out_idx, merge_name in edges:
        passthrough_name = f"{source} -> {merge_name} Pass-Through"
        _retarget_merge_edge_through_passthrough(
            nodes, conns, source, source_out_idx, merge_name, passthrough_name, x, py)
        py += 80


def wire_gate_refusal_lane(nodes, conns, write_name, merge_name, x, y, *,
                           mirror_index=None, unreached_source=None,
                           unreached_condition_js=None, carry_merge=None):
    """Give a spliced write gate's REFUSAL lane its own input on `merge_name`, plus the
    sentinels that keep that input fed (Phase 70 Plan 05 Task 2, D-70-14).

    The obvious wiring — point the gate IF's false output at the SAME merge input the
    write path's own terminal already feeds — was tried first and is WRONG, for the
    reason this file already records above "Associate Lane Sentinel"'s call site: a Merge
    fires on WHICHEVER set of deliveries satisfies it first, so on an armed batch with a
    MIXED verdict the refusal (zero hops from the gate) beats the permitted row's real
    multi-hop delivery to that shared input, the Merge fires and locks, and the real
    arrival is dropped. Caught by driving the committed graph through the offline walker
    with one row allowed and one refused: the permitted row's association came back
    "not_confirmed" instead of "associated". A marker may share an input (it carries no
    data and is filtered out downstream); two REAL producers may not.

    So the refusal gets its own input, and — like every other input on these merges — a
    sentinel per way it can fail to deliver:

      (a) the gate ran and refused nothing  -> sourced from the gate's OWN Code node,
          which is the only node that can answer it;
      (b) the gate never ran at all         -> `unreached_source` + `unreached_condition_js`,
          the routing predicate that decides whether any row reaches the gate; OR
          `mirror_index`, which copies the question off the sentinels that ALREADY answer
          it for the write path's own terminal ("the real lane will not deliver" and "the
          refusal lane will not deliver" are the same question when the gate never runs).

    `mirror_index` is derived, never hand-listed: on the enrichment lane ~30 sentinels
    feed "Build Response Merge", several per terminal, and enumerating them by name here
    would go stale the first time one is added.

    The gate IF's false output still lands on `merge_name` directly (unchanged by
    Phase 70 Plan 10) — this repo's existing `writeGateShape.test.mjs` coverage pins
    that edge by name for the enrichment lane's own gates, and that lane's own
    pass-through audit is plan 70-11's job (D-70-20's IF-branch-delivery question stays
    unobserved either way, unlike the ingest lane, which plan 70-10 converts via its own
    `_add_merge_passthrough` call sites in `build_cloud`, not here).

    `carry_merge` (Phase 70 Plan 10, D-70-23): `(downstream_merge_name, input_index)` — an
    APPEND-mode Merge downstream of the write node's own per-hop carry Merge (never the
    carry Merge itself: `splice_carry_merge_after`'s Merge is `combineByPosition`, and
    feeding it a marker on only ONE of its two inputs would pair that marker with the
    OTHER input's real content into one fabricated row — Rule 1, found running this
    plan's own suite: the carry Merge's positional-combine input 0, the write node's own
    HTTP response, has no producer at all whenever the write gate IF's true branch is
    empty, and the carry Merge is then left waiting on the one input nothing will ever
    feed, a fully-refused batch's own version of executions 12204-12206 — but making the
    carry Merge itself fire on a marker corrupts a DIFFERENT convergence downstream,
    where two per-action carry Merges land on one un-merged Code node
    ("Build Association Request") and a marker-triggered SECOND run of that node races
    the real one). The two sentinels below therefore target the downstream APPEND merge,
    never the carry Merge: a marker landing there is inert (filtered by the downstream
    Code node's own `if (!contactId) return null`), and the downstream merge's OWN input
    is what needs covering on every way its own carry Merge can be silent."""
    idx = _append_merge_input(nodes, conns, merge_name, f"{write_name} Write Gate IF",
                              source_out_idx=1)
    if mirror_index is not None:
        # Phase 70 Plan 10 (D-70-23): a mirrored sentinel's own outgoing edge no longer
        # points at `merge_name` directly — it points at its gate (`_add_starved_lane_
        # sentinel`'s "condition -> gate -> targets" shape). Follow the gate, or a
        # refusal lane silently loses the mirrored coverage that keeps its input fed
        # when the write gate never runs at all.
        for name, spec in list(conns.items()):
            if not name.endswith("Sentinel"):
                continue
            gate_spec = conns.get(f"{name} Gate")
            if gate_spec is None:
                continue
            for outputs in gate_spec.get("main", []):
                if any(c.get("node") == merge_name and c.get("index") == mirror_index
                       for c in (outputs or [])):
                    outputs.append({"node": merge_name, "type": "main", "index": idx})
                    break
    if unreached_source is not None:
        _add_starved_lane_sentinel(
            nodes, conns, f"{write_name} Gate Unreached Sentinel",
            unreached_source, unreached_condition_js, [(merge_name, idx)], x, y)
        y += 120
    _add_starved_lane_sentinel(
        nodes, conns, f"{write_name} No Refusal Sentinel", f"{write_name} Write Gate",
        'if (rows.length > 0 && rows.every((r) => r.write_allowed === true)) '
        'return [{}]; return [];',
        [(merge_name, idx)], x, y)
    y += 120
    if mirror_index is not None:
        # The MIRROR IMAGE, and the half that only became necessary once the gate stopped
        # relabelling refused rows upstream of the routing IFs: the routing sentinels
        # correctly stay silent when rows ARE heading for this write, but the gate can
        # still refuse every one of them, and then the write node never runs and its own
        # terminal's input starves. Sourced from the gate's Code node because that is the
        # only node that knows the verdict — and mutually exclusive with the real
        # delivery by construction (it fires only when NO row was allowed), so it can
        # safely share the terminal's input the way every other marker here does.
        _add_starved_lane_sentinel(
            nodes, conns, f"{write_name} All Refused Sentinel", f"{write_name} Write Gate",
            'if (rows.length > 0 && !rows.some((r) => r.write_allowed === true)) '
            'return [{}]; return [];',
            [(merge_name, mirror_index)], x, y)
    if carry_merge is not None:
        carry_merge_name, carry_merge_idx = carry_merge
        y += 120
        if unreached_source is not None:
            _add_starved_lane_sentinel(
                nodes, conns, f"{write_name} Carry Unreached Sentinel",
                unreached_source, unreached_condition_js,
                [(carry_merge_name, carry_merge_idx)], x, y)
            y += 120
        _add_starved_lane_sentinel(
            nodes, conns, f"{write_name} Carry All Refused Sentinel",
            f"{write_name} Write Gate",
            'if (rows.length > 0 && !rows.some((r) => r.write_allowed === true)) '
            'return [{}]; return [];',
            [(carry_merge_name, carry_merge_idx)], x, y)
    return idx


def _sentinel_gate_js():
    """D-70-23's gate body. Fed ONLY by its sentinel condition node's own output —
    never by `source` directly. Stamps `SENTINEL_MARKER_KEY` on whatever it passes
    through so a marker is never mistakable for a real row."""
    return (
        "// Sentinel Gate — Phase 70 Plan 10 (D-70-23). Fed ONLY by its condition\n"
        "// node's own output. That output can be an empty array while the condition\n"
        "// node itself still RAN (it is always fed the real lane's row set), and the\n"
        "// engine counts a zero-item OUTPUT as a real delivery to whatever it feeds\n"
        "// (executions 12204-12206) — sharing a Merge input directly with the\n"
        "// condition node therefore let an empty verdict pre-empt a real row. This\n"
        "// gate is what the condition feeds instead: when the condition emits\n"
        "// nothing, the gate itself is fed zero items and — per the engine's OWN\n"
        "// other rule (execution 12200: a node fed zero items does not run) — never\n"
        "// runs, making no delivery at all. Only the condition's one marker item ever\n"
        "// reaches this gate, so it always runs it becomes the delivery.\n"
        "return $input.all().map((it) => ({ json: { ...it.json, "
        f"{SENTINEL_MARKER_KEY!r}: true }} }}));\n"
    )


def _add_starved_lane_sentinel(nodes, conns, name, source, condition_js, targets, x, y,
                                *, source_out_idx=0):
    """A narrow Code-node sentinel (Phase 70 Plan 03, D-70-01's `set_always_output_data`
    obligation applied via the global-sentinel mechanism 70-02 established, rather than
    `alwaysOutputData` on a routing IF whose OTHER branch can be a paid provider/write
    call — see this plan's own SUMMARY for the full per-node rationale).

    Fed via an ADDITIONAL fan-out edge from `source`'s existing output (`source`'s own
    real edges are never touched) — the SAME row set `source` delivered this run, as
    plain `{...}` objects bound to `rows` inside `condition_js`. `condition_js` must
    `return` an array: `[{}]` when every one of `targets` would otherwise starve this
    execution, `[]` when real content already covers them (mutually exclusive with the
    real lane by construction, never a race).

    Phase 70 Plan 10 (D-70-23): the condition node's own output is NEVER wired directly
    to `targets` any more — it feeds a gate node (`f"{name} Gate"`, `_sentinel_gate_js`)
    that is the ONLY node with edges to `targets`. `targets` names are typically resolved
    via `_merge_input_index` against a merge `splice_merge_before` already created."""
    nodes.append(code_node(name, f"""// {name} — Phase 70 Plan 03 starved-lane sentinel.
// Bypasses the real routing chain entirely: see _add_starved_lane_sentinel's docstring.
const rows = $input.all().map((it) => it.json);
{condition_js}
""", x, y))
    conns.setdefault(source, {"main": [[]]})
    while len(conns[source]["main"]) <= source_out_idx:
        conns[source]["main"].append([])
    conns[source]["main"][source_out_idx].append({"node": name, "type": "main", "index": 0})
    gate_name = f"{name} Gate"
    nodes.append(code_node(gate_name, _sentinel_gate_js(), x + 110, y))
    conns[name] = {"main": [[{"node": gate_name, "type": "main", "index": 0}]]}
    conns[gate_name] = {"main": [[{"node": t, "type": "main", "index": i} for (t, i) in targets]]}
    return name


def build_scheduled_maintenance_cloud():
    nodes = []
    conns = {}

    # --- SJ-3: requested poller (cadence = SJ3_TRIGGER_SCHEDULE, which also derives the
    # dispatch cap — re-timing this trigger moves the cap, CAP-01) ----------------------
    x, y = 220, 300
    sj3_trigger = _schedule_trigger("SJ-3 Trigger", x, y, *SJ3_TRIGGER_SCHEDULE)
    nodes.append(sj3_trigger)
    x += 220
    # BUG 10 / Phase 16.6: _hs_http_search_node for all 4 company searches below — the
    # native node has no `operation: "search"` for resource:company (see that helper's
    # docstring for the confirmed mechanism).
    sj3_search = _hs_http_search_node(
        "SJ-3 Search (requested poller)", "company", x, y,
        filter_groups=[[
            {"propertyName": "lv_enrichment_requested", "operator": "EQ", "value": "true"},
            {"propertyName": "lv_enrichment_status", "operator": "NEQ", "value": "running"},
        ]],
        # BUG 24's class (Phase 44 Plan 01): `domain` requested so a domain-scoped armed
        # window (TEST_RECORD_DOMAINS) can permit an SJ-3 row at all — without it on the
        # row, D-01's per-record gate would silently deny everything in exactly the
        # windows scheduled_arm.py opens. Same precedent as SJ-1/SJ-2 below.
        properties_csv="hs_object_id,domain,lv_enrichment_requested,lv_enrichment_status")
    nodes.append(sj3_search)
    x += 220
    nodes.append(code_node("SJ-3 Extract Rows", ENRICH_EXTRACT_SEARCH_ROWS, x, y))
    x += 220
    # Phase 44 Plan 01 (GATE-01/D-01): per-record dispatch permission, one shared
    # definition of "permitted" (D-02). Emits ALL rows annotated — fan-out below routes
    # permitted rows to dispatch and declined rows to the drain.
    nodes.append(code_node("SJ-3 Dispatch Gate", ENRICH_SJ3_DISPATCH_GATE, x, y))
    x += 220
    # fix(40) / WINDOWS.md #3: reshape into an event Parse HubSpot Event can read, since
    # the enrichment workflow's new Execute Workflow Trigger entry point (build_enrichment_
    # cloud) receives each dispatched item's json UNCHANGED (passthrough) — see
    # ENRICH_SJ3_BUILD_DISPATCH_EVENT's own comment for why this is SJ-3-only.
    nodes.append(code_node("SJ-3 Build Dispatch Event", ENRICH_SJ3_BUILD_DISPATCH_EVENT, x, y))
    x += 220
    sj3_dispatch = _execute_workflow_node(
        "SJ-3 Dispatch To Enrichment", x, y, "LVenrichmentCloud01", "LV Enrichment (Cloud template)")
    nodes.append(sj3_dispatch)
    # Drain branch (DRAIN-01/02/03, D-05..D-08): declined rows get their trigger flag
    # cleared through a structurally narrow write. NOT routed through splice_write_gates —
    # see _sj3_drain_gate_js's docstring for why (D-06).
    nodes.append(code_node("SJ-3 Drain Gate", _sj3_drain_gate_js(), x - 440, y + 150))
    sj3_drain_write = _hs_update_set_property(
        "SJ-3 Drain Clear Flag", "company", x - 220, y + 150,
        "lv_enrichment_requested", "false",
        # lv_enrichment_status="skipped" is the drain's provenance stamp (D-08/DRAIN-03):
        # the property is a closed enumeration (config/hubspot_properties.yaml) and
        # `skipped` is the one option nothing else in the pipeline writes today — so it
        # needs no property migration and collides with no existing meaning. The stamp is
        # provenance ONLY: clearing lv_enrichment_requested alone already removes the
        # record from SJ-3's EQ-"true" filter. Both keys and both values are baked
        # literals in the built JSON (DRAIN-02 is structural, not a runtime promise).
        extra_properties=(("lv_enrichment_status", "skipped"),))
    nodes.append(sj3_drain_write)
    # Plan 02 (GATE-02): the tick outcome hangs off the gate's OWN output — never off a
    # filtered branch whose item count can reach zero (see ENRICH_SJ3_TICK_OUTCOME).
    nodes.append(code_node("SJ-3 Tick Outcome", ENRICH_SJ3_TICK_OUTCOME, x - 220, y - 150))

    conns.update(chain([sj3_trigger["name"], sj3_search["name"], "SJ-3 Extract Rows",
                        "SJ-3 Dispatch Gate"]))
    # Fan-out, not a chain: all THREE consumers read the gate's single annotated output —
    # the permitted path filters on sj3_dispatch, the declined path on sj3_drain, and the
    # tick outcome reads the sj3_tick summary (the only node that runs on a fully
    # gate-closed tick — GATE-02).
    conns["SJ-3 Dispatch Gate"] = {"main": [[
        {"node": "SJ-3 Build Dispatch Event", "type": "main", "index": 0},
        {"node": "SJ-3 Drain Gate", "type": "main", "index": 0},
        {"node": "SJ-3 Tick Outcome", "type": "main", "index": 0},
    ]]}
    conns.update(chain(["SJ-3 Build Dispatch Event", sj3_dispatch["name"]]))
    conns.update(chain(["SJ-3 Drain Gate", sj3_drain_write["name"]]))

    # --- SJ-1: hourly input-gap scan (Task 2) ------------------------------------------
    # Three single-filter OR'd groups (Pitfall 3) — "any input unresolved", never AND.
    x, y1 = 220, 620
    sj1_trigger = _schedule_trigger("SJ-1 Trigger", x, y1, "days", 1)
    nodes.append(sj1_trigger)
    x1 = x + 220
    sj1_search = _hs_http_search_node(
        "SJ-1 Search (input-gap scan)", "company", x1, y1,
        filter_groups=[
            [{"propertyName": "lv_org_type", "operator": "NOT_HAS_PROPERTY"}],
            [{"propertyName": "lv_org_type", "operator": "EQ", "value": "unknown"}],
            [{"propertyName": "lv_produces_content", "operator": "NOT_HAS_PROPERTY"}],
        ],
        # BUG 24: `domain` requested so this lane's write gate can be satisfied by
        # TEST_RECORD_DOMAINS at all — see the Review Search comment below.
        properties_csv="hs_object_id,domain,lv_org_type,lv_produces_content")
    nodes.append(sj1_search)
    x1 += 220
    nodes.append(code_node("SJ-1 Extract Rows", ENRICH_EXTRACT_SEARCH_ROWS, x1, y1))
    x1 += 220
    sj1_dispatch = _hs_update_set_property(
        "SJ-1 Set Requested", "company", x1, y1, "lv_enrichment_requested", "true")
    nodes.append(sj1_dispatch)

    conns.update(chain([sj1_trigger["name"], sj1_search["name"], "SJ-1 Extract Rows",
                        sj1_dispatch["name"]]))

    # --- SJ-2: monthly stale refresh + RT-5 confirmation (Task 2) ----------------------
    # Two OR'd groups, LT on the two verified-at cache keys against a Code-node-computed
    # epoch-ms cutoff. An Adapt step (ENRICH_ADAPT_CO_SEARCH shape) feeds SJ2_CO_GATE so
    # decideAction actually confirms staleness (RT-5) before the terminal dispatch — a
    # skip (still fresh, or re-verified since the scan started) never re-queues.
    # Phase 66 REVIEW-FIX (WR-02): this used to say "the reused, UNMODIFIED Company Gate"
    # and reuse ENRICH_CO_GATE directly — true while ENRICH_CO_GATE's REQUIRED was these
    # same 2 fields. 66-02 widened ENRICH_CO_GATE's REQUIRED to 13 fields for the
    # completeness-chase lanes without widening this search's fetch to match, so the other
    # 11 fields always read `undefined` here and this gate over-triggered on every row.
    # SJ2_CO_GATE (defined above ENRICH_BUILD_CO_REQUESTS) restores the original 2-field
    # REQUIRED/POLICY this search's fetch already fully covers — see SJ2_CO_GATE's own
    # comment for why narrowing the gate, not widening the fetch, is the correct fix here.
    x, y2 = 220, 940
    sj2_trigger = _schedule_trigger("SJ-2 Trigger", x, y2, "months", 1)
    nodes.append(sj2_trigger)
    x2 = x + 220
    nodes.append(code_node("SJ-2 Epoch Cutoff (180d)", ENRICH_SJ2_EPOCH_CUTOFF, x2, y2))
    x2 += 220
    sj2_search = _hs_http_search_node(
        "SJ-2 Search (stale refresh)", "company", x2, y2,
        filter_groups=[
            [{"propertyName": "lv_org_type_verified_at", "operator": "LT",
              "value": "={{ $json.cutoff_ms }}"}],
            [{"propertyName": "lv_produces_content_verified_at", "operator": "LT",
              "value": "={{ $json.cutoff_ms }}"}],
        ],
        # BUG 24: same as SJ-1 — `domain` is what makes the domain allowlist usable.
        properties_csv="hs_object_id,domain,lv_org_type,lv_produces_content,"
                       "lv_org_type_verified_at,lv_produces_content_verified_at")
    nodes.append(sj2_search)
    x2 += 220
    nodes.append(code_node("SJ-2 Adapt Search", ENRICH_ADAPT_SJ2_SEARCH, x2, y2))
    x2 += 220
    nodes.append(code_node("SJ-2 Company Gate", SJ2_CO_GATE, x2, y2))
    x2 += 220
    sj2_if_not_skip = _if_node("SJ-2 IF Skip", "skip", x2, y2)
    nodes.append(sj2_if_not_skip)
    x2 += 220
    sj2_dispatch = _hs_update_set_property(
        "SJ-2 Set Requested", "company", x2, y2 + 100, "lv_enrichment_requested", "true")
    nodes.append(sj2_dispatch)
    sj2_noop = {
        "parameters": {"assignments": {"assignments": [
            {"id": nid("a"), "name": "action", "value": "skip", "type": "string"}
        ]}, "options": {}},
        "id": nid("r"), "name": "SJ-2 Skip (NoOp)",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [x2, y2 - 100]}
    nodes.append(sj2_noop)

    conns.update(chain([sj2_trigger["name"], "SJ-2 Epoch Cutoff (180d)", sj2_search["name"],
                        "SJ-2 Adapt Search", "SJ-2 Company Gate", sj2_if_not_skip["name"]]))
    conns[sj2_if_not_skip["name"]] = {"main": [
        [{"node": "SJ-2 Skip (NoOp)", "type": "main", "index": 0}],   # true: still stale-gate says skip
        [{"node": sj2_dispatch["name"], "type": "main", "index": 0}],  # false: confirmed stale -> dispatch
    ]}

    # --- Dedupe Sweep: weekly, CONTACTS (Task 3) — CLASSIFY ONLY, never writes itself ---
    # dedupeSweep.js reads contact-shaped properties.{email,phone,linkedin_url}; the
    # wrapper (ENRICH_DEDUPE_SWEEP) maps lv_linkedin_url -> linkedin_url so the frozen
    # module never needs to change (CLAUDE.md §13.4 Workflow D).
    x, y3 = 220, 1520
    dedupe_trigger = _schedule_trigger("Dedupe Trigger", x, y3, "weeks", 1)
    nodes.append(dedupe_trigger)
    x3 = x + 220
    dedupe_search = _hs_http_search_node(
        "Dedupe Search (candidate contacts)", "contact", x3, y3,
        filter_groups=[[{"propertyName": "email", "operator": "HAS_PROPERTY"}]],
        properties_csv="hs_object_id,email,phone,lv_linkedin_url")
    nodes.append(dedupe_search)
    x3 += 220
    nodes.append(code_node("Dedupe Extract Rows", ENRICH_EXTRACT_SEARCH_ROWS, x3, y3))
    x3 += 220
    dedupe_node = code_node("Dedupe Sweep", ENRICH_DEDUPE_SWEEP, x3, y3)
    nodes.append(dedupe_node)
    x3 += 220
    # BUG 18 (2026-07-29): was _hs_update_set_property(..., "contact", ...), which emits the
    # native node with `operation: "update"`. No such contact operation exists — upstream
    # ContactDescription.ts defines upsert/delete/get/getAll/getRecentlyCreatedUpdated/search
    # — so this node had BUG 10's exact failure mode on the contacts side: fall through the
    # dispatch chain, return json:null, report status:success. Never live because this
    # workflow has never been activated. `Dedupe Sweep` now emits the shared `properties`
    # row contract so this takes the same credential-bound PATCH node as every other write.
    dedupe_flag_write = _hs_http_patch_node("Dedupe Set Needs Review", "contacts", x3, y3)
    nodes.append(dedupe_flag_write)

    conns.update(chain([dedupe_trigger["name"], dedupe_search["name"], "Dedupe Extract Rows",
                        dedupe_node["name"], dedupe_flag_write["name"]]))

    # --- Review Loop: §22.2 approve -> apply -> clear (Task 4) -------------------------
    # Shares SJ-3's cadence in spirit (own trigger node, same interval — daily since 2026-08-10). The search
    # requests hs_object_id + every DEFAULT_COMPANY_POLICY-adjacent candidate field's
    # CURRENT value (the refetch reviewApply compares against) + the candidate JSON + the
    # 4 review flags reviewApply's clearPatch zeroes.
    x, y4 = 220, 1840
    review_trigger = _schedule_trigger("Review Trigger", x, y4, "days", 1)
    nodes.append(review_trigger)
    x4 = x + 220
    review_search = _hs_http_search_node(
        "Review Search (approved=true)", "company", x4, y4,
        filter_groups=[[
            {"propertyName": "lv_enrichment_review_approved", "operator": "EQ", "value": "true"},
        ]],
        # BUG 24 (found live 2026-07-29, first armed review canary): `domain` was absent
        # here, so the lane never emitted it, so `Review Apply Update Write Gate` —
        # which reads `it.json.domain` — could NEVER be satisfied by TEST_RECORD_DOMAINS.
        # Only TEST_RECORD_IDS could ever allow this lane. Fail-closed, never a live risk,
        # but a domain allowlist silently did nothing here: BUG 16's family (a gate reading
        # a field its lane does not emit), in its partial form. `domain` is requested now so
        # both allowlists work, and reviewApply ignores it (not in DEFAULT_COMPANY_POLICY's
        # promote path for this candidate flow — it only reads fields named by the candidate).
        properties_csv="hs_object_id,domain,lv_org_type,lv_produces_content,lv_revenue_band,"
                       "lv_employee_band,lv_content_type,lv_sponsorship_reliant,"
                       "lv_is_hardware_vendor,lv_is_gambling_operator,"
                       "lv_enrichment_review_candidate_json,lv_enrichment_needs_review,"
                       "lv_enrichment_review_approved,lv_enrichment_review_reason")
    nodes.append(review_search)
    x4 += 220
    nodes.append(code_node("Review Extract Rows", ENRICH_EXTRACT_SEARCH_ROWS, x4, y4))
    x4 += 220
    apply_review = code_node("Apply Review", ENRICH_APPLY_REVIEW, x4, y4)
    nodes.append(apply_review)
    x4 += 220
    # Phase 31 (BUG 28/29): switched from `stale` to `review_skip`, which also covers an
    # invalid-enum result (Apply Review's own comment) — a result that is not stale but
    # whose assembled patch is empty must skip the write branch just the same.
    if_stale = _if_bool_node("Review IF Stale", "review_skip", x4, y4)
    nodes.append(if_stale)
    x4 += 220
    # A stale row (compare-and-set mismatch) skips BOTH the patch and the clear — nothing
    # is written, the record stays queued for re-review (reviewApply's own comment).
    review_stale_noop = {
        "parameters": {"assignments": {"assignments": [
            {"id": nid("a"), "name": "review_outcome", "value": "stale_skipped", "type": "string"}
        ]}, "options": {}},
        "id": nid("r"), "name": "Review Stale (NoOp)",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [x4, y4 - 100]}
    nodes.append(review_stale_noop)
    # Applies canonicalPatch + clearPatch. Property values are dynamic per-record
    # (reviewApply's output), so this node is a documented-equivalent placeholder — the
    # same convention "HubSpot Update"/"HubSpot Company Update" in the webhook branch
    # used to follow (updateFields populated at deploy/operator-config time, not baked by
    # this builder), UNTIL Phase 16.7-01 (BUG 11) moved those two onto a credential-bound
    # httpRequest PATCH that DOES carry the computed patch. This node
    # ("Review Apply Update", in the separate scheduled-maintenance workflow) is
    # explicitly OUT of that fix's scope and keeps its placeholder status.
    review_apply_update = _hs_http_patch_node("Review Apply Update", "companies", x4, y4 + 100)
    nodes.append(review_apply_update)

    conns.update(chain([review_trigger["name"], review_search["name"], "Review Extract Rows",
                        apply_review["name"], if_stale["name"]]))
    conns[if_stale["name"]] = {"main": [
        [{"node": "Review Stale (NoOp)", "type": "main", "index": 0}],       # true: stale -> skip
        [{"node": "Review Apply Update", "type": "main", "index": 0}],       # false: clean -> apply + clear
    ]}

    notes = [
        {"content": (
            "## LV Scheduled Maintenance — CLOUD\n"
            "Background reconciliation + human-review layer (SYSTEM-CONTRACT). Runs "
            "alongside \"LV Enrichment (Cloud template)\" — this workflow only ever "
            "DISCOVERS/DISPATCHES/CLASSIFIES; the actual provider waterfall + merge lives "
            "in that sibling workflow's companies branch.\n\n"
            "**SJ-1 (daily):** any pipeline-owned input unresolved "
            "(`lv_org_type` blank/unknown OR `lv_produces_content` blank) -> "
            "`lv_enrichment_requested=true`.\n\n"
            "**SJ-2 (monthly):** either verified-at cache key older than 180 days -> "
            "reused Company Gate CONFIRMS staleness (RT-5) -> `lv_enrichment_requested=true`.\n\n"
            "**SJ-3 (daily):** `lv_enrichment_requested=true AND lv_enrichment_status != "
            "running` -> per-record write-safety gate -> budget-derived dispatch cap "
            "(config/execution_budget.yaml) -> Execute Workflow into the companies branch "
            "of \"LV Enrichment (Cloud template)\"; declined rows are DRAINED "
            "(`lv_enrichment_requested=false`, `lv_enrichment_status=skipped`) so a "
            "closed write gate cannot re-form the re-dispatch runaway (Phase 44). Re-bind `workflowId` after deploy (n8n Cloud assigns its "
            "own id on import — this constant is the byte-identical build-time id, the "
            "deploy script re-binds credentials/references the same way it already does "
            "for the 6 provider credentials, `scripts/deploy_n8n_workflows.py`).\n\n"
            "None of SJ-1/2/3's predicates ever reference `lv_icp_tier`/`lv_icp_fit_score`/"
            "`lv_icp_scored_at` (Approach C, spec §0.7) — HubSpot derives those, the "
            "pipeline only ever queues off its own INPUTS.\n\n"
            "**Ships inactive (Plan 02, SC-7/reviews A5):** `\"active\": false` is baked "
            "into this workflow's JSON as an explicit intent marker + test hook "
            "(`tests/test_schedules_inactive.py`). The PRECISE functional guarantee: "
            "n8n's Public API treats `active` as read-only on create, and "
            "`deploy_n8n_workflows.py` never POSTs to `/activate` (its create/update "
            "payload keeps only name/nodes/connections/settings — a deploy test guards "
            "this) — so a NEWLY-CREATED scheduled workflow stays inactive until an "
            "operator explicitly enables it. This does NOT deactivate an already-active "
            "workflow on a later update; that remains a manual operator checkpoint, not "
            "automated here."
        ), "x": 220, "y": 1080, "h": 420, "w": 520},
        {"content": (
            "### §22.2 Review loop (approve -> apply -> clear)\n"
            "RevOps opens a HubSpot view: `lv_enrichment_needs_review=true OR "
            "lv_icp_needs_review=true`. Evidence lives INSIDE "
            "`lv_enrichment_review_candidate_json`/`lv_enrichment_provenance`, not a flat "
            "column. Approving sets `lv_enrichment_review_approved=true` (+ "
            "`lv_enrichment_reviewed_by`, convention not enforced by any property).\n\n"
            "**Apply Review** (`n8n/code/reviewApply.js`) re-applies exactly the HELD "
            "needs_review candidates `ENRICH_DECIDE_CO_CLOUD` wrote — a refetch "
            "compare-and-set (a candidate whose `current_value` no longer matches the "
            "live value is dropped, `stale=true`, record stays queued) and fail-closed "
            "malformed-JSON handling. `Review Apply Update`'s `updateFields` is a "
            "documented-equivalent placeholder (dynamic per-record patch, mirrors this "
            "file's existing minimal-Update convention) — production wiring maps "
            "`{...canonicalPatch, ...clearPatch}` onto the node's custom-properties UI at "
            "deploy time."
        ), "x": 800, "y": 1080, "h": 340, "w": 480},
    ]
    # See the enrichment builder's note: duplicate node names are a hard 400 from n8n's
    # workflow-create API. Guarded by tests/test_node_name_uniqueness.py.
    for i, n in enumerate(notes, start=1):
        nodes.append({
            "parameters": {"content": n["content"], "height": n["h"], "width": n["w"]},
            "id": nid("s"), "name": f"Sticky Note {i}",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "position": [n["x"], n["y"]],
        })

    splice_write_gates(nodes, conns, {
        "SJ-1 Set Requested": "enrich",
        "SJ-2 Set Requested": "enrich",
        "Dedupe Set Needs Review": "enrich",
        "Review Apply Update": "enrich",
    })

    return {
        "id": "LVscheduledMaintenanceCloud01",
        "name": "LV Scheduled Maintenance (Cloud)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
        # Phase 16.1 Plan 02 (SC-7, reviews A5) — explicit intent marker + test hook, not
        # itself a runtime gate (n8n's Public API ignores `active` on create). The
        # FUNCTIONAL guarantee is deploy_n8n_workflows.py never POSTing to `/activate`
        # (see its docstring + tests/test_deploy_n8n_workflows.py's no-activate guard) —
        # inactive-on-create only; does NOT deactivate an already-active workflow.
        "active": False,
    }


# =============================================================================
# REVIEW DECISION workflow (Phase 30 Plan 02) — `hubspot/review/decision`.
#
# The SYNCHRONOUS counterpart to the scheduled review loop above (daily since 2026-08-10),
# which stays exactly as
# a backstop (D-08e). That loop cannot satisfy Phase 28's confirm-then-verify
# pattern: there is nothing to read back until its next scheduled fire. This endpoint takes one
# operator decision, computes the exact property write, and either shows it (dry run) or
# performs it and reads it back with an INDEPENDENT refetch.
#
# Its own file, not a branch bolted onto an existing workflow (D-20 / 28 D-14): a
# responder sitting on a shared branch can fire on whichever branch arrives first and
# corrupt another lane's response.
# =============================================================================

# The compare-and-set baseline 30-03's approve path needs is "every field reviewApply can
# promote" = Object.keys(DEFAULT_COMPANY_POLICY), whose own source of truth is
# config/field_policy.yaml's `companies` block (mergeCompanies.js:26), pinned by
# tests/test_field_policy_conformance.py. DERIVED, never re-typed: a policy field added
# later and not refetched here would come back `undefined` and read to reviewApply as a
# manual edit, silently turning every such decision stale.
_COMPANY_POLICY_FIELDS = tuple(sorted(
    yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["companies"]))

# The `lv_`-prefixed review family (config/hubspot_properties.yaml, D-08c). It exists on
# BOTH objects under exactly these names, so it is written once and shared by the two
# lanes' property sets — a family that drifts between the lanes is a decision the operator
# can make on one object type and not the other.
_REVIEW_FAMILY = (
    "lv_enrichment_needs_review", "lv_icp_needs_review",
    "lv_enrichment_review_reason", "lv_enrichment_review_candidate_json",
    "lv_enrichment_review_approved", "lv_enrichment_reviewed_by",
    "lv_enrichment_reviewed_at")

# `domain` is not decoration: the write gate reads it for the allowlist check, so a lane
# that does not FETCH it can never be allowed by TEST_RECORD_DOMAINS (BUG 24's exact
# shape, on the sibling review lane). Both COMPANY searches in this workflow request the
# same set, so `verified_properties` can always cover every key `would_write` may carry.
REVIEW_DECISION_PROPERTIES_CSV = ",".join(dict.fromkeys(
    ("hs_object_id", "name", "domain") + _REVIEW_FAMILY + ("lv_enrichment_provenance",)
    + _COMPANY_POLICY_FIELDS))

# The contacts policy fields, derived from config/field_policy.yaml the same way
# _COMPANY_POLICY_FIELDS is (line 7024) — never re-typed by hand. Since 2026-08-27 (Phase
# 54 Plan 03/06, WR-02) a contacts approve calls the SAME reviewApply engine as companies,
# keyed on DEFAULT_CONTACT_POLICY, so this is now a real compare-and-set BASELINE: every
# key here is a field reviewApply can promote, and any key left out comes back
# `refetchedProperties[field] === undefined` — which reviewApply normalizes to `null` and
# compares against a stored `current_value` that may also be `null`, silently treating a
# manually-edited field as unchanged (the exact non-clobber bypass WR-02 named).
_CONTACT_POLICY_FIELDS = tuple(sorted(
    yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["contacts"]))

# The DECISION set (30-02/30-03, widened Phase 54 Plan 06): identity the two limit=1 fetch
# nodes need, the same review family, the CONTACTS provenance blob —
# `lv_contact_enrichment_provenance`, a different property from the companies one (30
# D-08a) — and now every contacts policy field, mirroring REVIEW_DECISION_PROPERTIES_CSV's
# own pattern. Both `Review Contact Fetch By Id` and `Review Contact Verify Fetch` take
# this wide set for the same reason the companies lane's line 7037-7040 gives: the verify
# fetch must be able to cover every key `would_write` may carry, or a landed write reports
# `verified_properties` that cannot see it.
#
# No `domain`: contacts do not have one, so the write gate's domain allowlist cannot match
# a contact and TEST_RECORD_IDS is the ONLY way to allowlist one. Stated in the sticky note
# because an operator arming with TEST_RECORD_DOMAINS alone gets D-23's silent no-response.
REVIEW_CONTACT_DECISION_PROPERTIES_CSV = ",".join(dict.fromkeys(
    ("hs_object_id", "email", "firstname", "lastname", "jobtitle")
    + _REVIEW_FAMILY + ("lv_contact_enrichment_provenance",)
    + _CONTACT_POLICY_FIELDS))

# The QUEUE set — deliberately narrow, mirroring REVIEW_QUEUE_PROPERTIES_CSV's own
# reasoning at line 7064-7070: the queue compares nothing, the held candidate JSON already
# carries each decision's own current and proposed value, so fetching the full policy
# baseline for up to 100 records would be payload nobody reads. Byte-identical in
# membership to what REVIEW_CONTACT_PROPERTIES_CSV held before this split.
REVIEW_CONTACT_QUEUE_PROPERTIES_CSV = ",".join(dict.fromkeys(
    ("hs_object_id", "email", "firstname", "lastname", "jobtitle")
    + _REVIEW_FAMILY + ("lv_contact_enrichment_provenance",)))

# The queue read's COMPANY property set (30-04). Identity + the shared review family + the
# companies provenance blob + the ICP narrative an operator needs to judge a tier flag.
# Deliberately NOT REVIEW_DECISION_PROPERTIES_CSV: that set carries every
# config/field_policy.yaml `companies` key because reviewApply needs a compare-and-set
# BASELINE. The queue compares nothing — the held candidate JSON already carries each
# decision's own current and proposed value — so fetching the baseline for up to 100
# records would be payload nobody reads.
#
# The four ICP names are the LIVE ones (config/hubspot_migration/baseline/
# portal-schema-companies-post.json). `lv_icp_needs_review` is already in _REVIEW_FAMILY.
REVIEW_QUEUE_PROPERTIES_CSV = ",".join(dict.fromkeys(
    ("hs_object_id", "name", "domain") + _REVIEW_FAMILY
    + ("lv_enrichment_provenance", "lv_icp_tier", "lv_icp_fit_score",
       "lv_icp_score_breakdown", "lv_anti_icp_reason")))

REVIEW_PARSE_QUEUE_REQUEST = r"""// Parse Review Queue Request — the ONLY place this branch reads the request body, and it
// accepts TWO keys: object_type and limit. No filter, no property list, no record id and
// no field name is caller-supplied (T-30-17); the search below is fully baked, so the
// caller can choose WHICH object type's queue and HOW MANY, never WHAT is read.
//
// limit is clamped server-side to HubSpot CRM search's own maximum of 100 (T-30-19). A
// missing, non-numeric, zero or negative value reads as the maximum rather than as zero —
// a "0" that silently returned an empty page would be indistinguishable from an empty
// queue, which is the one confusion this endpoint exists to prevent.
const item = $input.first();
const raw = (item && item.json) || {};
// n8n's Webhook node nests the request under `body`; a directly-seeded item (tests, or an
// Execute Workflow call) carries the fields at the top level.
const body = (raw.body && typeof raw.body === "object" && !Array.isArray(raw.body)) ? raw.body : raw;

const n = Number(body.limit);
const limit = Number.isFinite(n) && n >= 1 ? Math.min(Math.floor(n), 100) : 100;

return [{ json: {
  object_type: body.object_type === "contacts" ? "contacts" : "companies",
  limit,
}}];
"""

REVIEW_QUEUE_ROWS = r"""// Review Queue Rows — the search envelope becomes ONE item carrying every row, never one
// item per row. Two reasons, both structural:
//
//   1. D-22: `rows.map(...)` emits ZERO items on a zero-hit search. On a `responseNode`
//      webhook that means nothing reaches the responder and the caller waits out the ~100s
//      Cloudflare ceiling instead of being told the queue is empty. An empty queue is the
//      NORMAL end state of this phase's work, so this lane meets that case constantly.
//   2. `Respond Review Queue` is `firstIncomingItem` (D-24), so a per-row emission would
//      return the FIRST record and silently drop the rest.
//
// It parses nothing (D-11). The held candidate JSON and the provenance blob are passed
// through as the exact strings HubSpot returned; the client parses them, so what the
// operator sees is what the CRM holds rather than this node's opinion of it.
//
// `total` is the search envelope's own count, which is the whole queue — `returned` is
// this page. A page shorter than the total is therefore visibly a page (REVIEW-01) instead
// of being mistaken for the end of the backlog.
//
// `search_ok` distinguishes an EMPTY queue from a FAILED search. HubSpot search nodes run
// `onError: continueRegularOutput`, so a 401 or a 429 arrives here as an item with no
// `results` array — which, treated as an envelope, would render as "0 flagged records" and
// tell the operator their backlog was clear when it was never read.
// Phase 70 Plan 03 Task 3 (D-70-01) + Phase 70 Plan 04 (D-70-04): this node sits behind
// a real Merge ("Review Queue Search" / "Review Queue Contact Search" — exactly one
// ever runs per request) with a starved-lane sentinel on whichever side would
// otherwise never fire. Each real search is now ALSO carry-merged with "Parse Review
// Queue Request" (D-70-04), so `object_type` rides the same merged item as the search
// envelope — drop an identity-less sentinel marker first, then read the one real item.
const items = $input.all().filter((it) => Object.keys(it.json || {}).length > 0);
const item = items[0];
const res = (item && item.json) || {};
const search_ok = Array.isArray(res.results);
const rows = search_ok ? res.results : (res.properties ? [res] : []);
const total = typeof res.total === "number" ? res.total : rows.length;

return [{ json: {
  object_type: res.object_type,
  search_ok: search_ok || Boolean(res.properties),
  total,
  returned: rows.length,
  rows: rows.map((r) => ({ ...(r.properties || {}), hs_object_id: r.id })),
}}];
"""

REVIEW_PARSE_DECISION = r"""// Parse Review Decision — the ONLY place the request body is read (T-30-05).
// SIX keys are accepted and nothing else: object_type, record_id, decision, reason,
// reviewed_by, dry_run. No field name, no value, no patch: the caller cannot tell this
// endpoint WHAT to write, only which record and which decision word. Any other key in the
// body is IGNORED, never merged — an injected `properties`/`field`/`value` has no path
// into the patch, which is always computed from the record's own refetched state.
//
// dry_run defaults to TRUE when absent or not a boolean (D-03): the fail-safe direction
// is "show, do not write", so a malformed or truncated request previews rather than writes.
const item = $input.first();
const raw = (item && item.json) || {};
// n8n's Webhook node nests the request under `body`; a directly-seeded item (tests, or an
// Execute Workflow call) carries the fields at the top level.
const body = (raw.body && typeof raw.body === "object" && !Array.isArray(raw.body)) ? raw.body : raw;

// Digits-only, coerced to a string. Anything else is null, which fails the fetch closed
// and returns "record not found" rather than searching on operator-supplied text.
const rawId = (typeof body.record_id === "string" || typeof body.record_id === "number")
  ? String(body.record_id).trim() : "";
const record_id = /^[0-9]+$/.test(rawId) ? rawId : null;

return [{ json: {
  object_type: body.object_type === "contacts" ? "contacts" : "companies",
  record_id,
  decision: typeof body.decision === "string" ? body.decision : null,
  // Passed through UNCOERCED so a wrong-typed reason is refused downstream rather than
  // silently becoming an empty one; absent reads as empty (D-09).
  reason: body.reason === undefined ? "" : body.reason,
  reviewed_by: typeof body.reviewed_by === "string" ? body.reviewed_by : null,
  dry_run: body.dry_run === false ? false : true,
}}];
"""

REVIEW_EXTRACT_RECORD = r"""// Review Extract Record — ENRICH_EXTRACT_SEARCH_ROWS's envelope handling plus the one
// thing a SYNCHRONOUS lane needs that the scheduled lanes do not: a zero-hit search must
// still emit exactly ONE item. On a scheduled branch zero rows means "nothing to do" and
// the branch simply ends; here it would mean nothing ever reaches
// `Respond Review Decision` and the caller waits out a Cloudflare timeout instead of
// being told the record was not found.
// Phase 70 Plan 03 Task 3 (D-70-01): this node sits behind a real Merge ("Review Fetch
// By Id" / "Review Contact Fetch By Id" — exactly one ever runs per request) with a
// starved-lane sentinel on whichever side would otherwise never fire; drop an
// identity-less sentinel marker (never a genuine zero-hit envelope, which always
// carries `results`/`properties`) before reading the one real item.
const items = $input.all().filter((it) => Object.keys(it.json || {}).length > 0);
const item = items[0];
const res = (item && item.json) || {};
const rows = Array.isArray(res.results) ? res.results : (res.properties ? [res] : []);
if (!rows.length) return [{ json: { hs_object_id: null, record_found: false } }];
const r = rows[0];
return [{ json: { ...(r.properties || {}), hs_object_id: r.id, record_found: true } }];
"""

# mergeCompanies + reviewApply are inlined because reviewDecision.js's approve branch CALLS
# reviewApply (D-08d — reuse it, never fork it) and reviewApply requires
# DEFAULT_COMPANY_POLICY from mergeCompanies, which reviewDecision also consults for the
# ownership CLASS check that closes D-12. hubspotEnums.generated/hubspotEnums are inlined
# because reviewApply (Phase 31) requires them for its own enum guard.
# mergeContacts is inlined too (Phase 54 Plan 03/05, live defect found 2026-08-27):
# reviewDecision.js's contacts branch requires DEFAULT_CONTACT_POLICY directly from
# mergeContacts (line 68), and the original Phase 30 inline list here predates that
# require — deployed without it, a live approve on a contact threw `ReferenceError:
# DEFAULT_CONTACT_POLICY is not defined` (executions 11992/11993). mergeCompanies.js and
# mergeContacts.js share several same-named internal helpers (_isBlank, _gate, etc.) as
# plain `function` declarations, which redeclare without a SyntaxError in this non-strict
# eval context; that collision is inert here because this node never calls mergeCompanies()
# or mergeContacts() themselves — only DEFAULT_*_POLICY, stableStringify (byte-identical in
# both files) and reviewApply() are ever referenced downstream.
# WRITE_SAFETY_GATE_JS is inlined too (Phase 31 Plan 02, BUG 30) so this node can compute
# the SAME _writeSafetyAllows("review", ...) verdict the spliced `Review Decision Update
# Write Gate` applies further downstream, and answer an explicit `not_allowlisted` refusal
# BEFORE that gate silently drops the row. The spliced gate is UNCHANGED and still runs —
# this is an earlier, louder answer in front of it, never a replacement for it.
REVIEW_BUILD_DECISION = inline(
    "taxonomy.generated.js", "hubspotEnums.generated.js", "hubspotEnums.js",
    "mergeCompanies.js", "mergeContacts.js", "reviewApply.js", "reviewDecision.js"
) + WRITE_REQUEST_JS + r"""

// --- n8n wrapper: Build Review Decision ---
// ONE decision node for both object types: the row arriving here has already been fetched
// by whichever lane `Review IF Contacts` selected, and the module branches on objectType.
//
// A contacts APPROVE now calls the SAME reviewApply engine as companies (2026-08-27, Phase
// 54 Plan 03/06), keyed on DEFAULT_CONTACT_POLICY, and resolves to `applied` with a real
// write — approve never means two different things across object types. It resolves that
// way in the CURRENT deployment ONLY because `lv_enrichment_review_candidate_json` has
// exactly one producer in this repo (the COMPANIES enrichment lane's `Decide Company
// Action`), which never stages a contacts candidate — not because the code forces
// `no_candidate`. This is a live-shape fact scoped to today, not a structural guarantee: a
// future contacts candidate producer would exercise the promote branch here for real.
// Contacts REJECT works exactly as companies does.
""" + WRITE_SAFETY_GATE_JS + r"""
// Phase 70 Plan 04 (D-70-04): fed by "Review Extract Record Carry Merge" — the merged
// item carries BOTH the original parsed request (object_type/record_id/decision/
// reason/reviewed_by/dry_run, from "Parse Review Decision") and the refetched record
// (hs_object_id/record_found/...properties, from "Review Extract Record"). No by-name
// lookup of a node several hops upstream.
const first = $input.first();
const row = (first && first.json) || {};
const parsed = row;

// ALLOWLIST PRE-CHECK (Phase 31 Plan 02, BUG 30). Same authority the committed gate uses.
// A preview (`dry_run` anything other than the literal `false`) must keep showing the
// patch the operator is being asked to approve, so it stays writeAllowed regardless of
// the allowlist — the real gate, not this pre-check, is what withholds a write later if
// a preview caller ever flips to a real submit.
//
// [Rule 1 - Bug, found by the plan's own advisor review, Phase 70 Plan 05 Task 1]
// D-70-13 forces this node's OWN `write_request.domain` to null for BOTH object types
// (below) — but this pre-check used to pass `row.domain` through unchanged. On a real
// company submit with a domain-only allowlist, the pre-check said allowed (outcome
// "applied", dry_run false) while the spliced gate — now null-domain-only for this
// lane — refused: the row never reaches "Review Verify Fetch", its Absent Sentinel
// never fires (guarded on `dry_run === true`, which this branch is not), and "Build
// Review Response Merge" starves waiting on an input that will never deliver (D-70-14's
// hang class). Passing `null` here too means a domain-only-armed company now resolves
// to `not_allowlisted` at THIS check, `dry_run` flips true, and the row exits cleanly via
// the no-write response lane instead of hanging behind a gate it can no longer pass.
const writeAllowed = (parsed.dry_run !== false)
  ? true
  : _writeSafetyAllows("review", row.hs_object_id, null);

const result = buildReviewDecision({
  objectType: parsed.object_type,
  decision: parsed.decision,
  reason: parsed.reason,
  reviewedBy: parsed.reviewed_by,
  row,
  nowIso: new Date().toISOString(),
  writeAllowed,
});

const properties = result.properties || {};
const hasWrite = Object.keys(properties).length > 0;

// BUG 12/21/25 row-carry family: SPREAD the refetched row rather than constructing a
// fresh object. `domain` lives on it and the write gate reads it for the allowlist check
// — a gate reading a field its lane does not emit has already cost this repo two armed
// windows. `properties`/`hs_object_id` are assigned after the spread so they still win.
//
// `dry_run` here is the ROUTING boolean `Review IF Dry Run` switches on, not an echo of
// the request: it is the caller's dry_run OR "there is no write to perform". A refused /
// not_flagged / unsupported outcome therefore reaches the response WITHOUT touching the
// write gate, the PATCH, or the verify refetch — so its verified_properties is null.
return [{ json: { ...row,
  hs_object_id: row.hs_object_id,
  properties,
  would_write: { ...properties },
  outcome: result.outcome,
  message: result.message,
  dry_run: !(parsed.dry_run === false && hasWrite),
  // Phase 70 Plan 03 Task 3 (D-70-01): additive — the refetched `row` never carries
  // an object_type (HubSpot records have no such property), so this node's own
  // output previously had no way to name which lane produced it. Needed by the
  // starved-lane sentinels feeding "Build Review Response Merge"'s two verify-fetch
  // inputs, which must pick between the companies/contacts lane using the COMPUTED
  // dry_run above (not the raw request's), since a refused/not_flagged/no_candidate/
  // stale outcome forces dry_run=true regardless of what the caller sent.
  object_type: parsed.object_type,
  // D-70-12/D-70-13 (Phase 70 Plan 05 Task 1): "Review Decision Update Write Gate" and
  // "Review Contact Decision Update Write Gate" now read only this. `domain` is forced
  // null regardless of object type — the review lane's contacts-stay-id-only rule
  // (30-02) is now an EMITTED VALUE here rather than a gate special-case, and it applies
  // uniformly to both write nodes this one node feeds (companies included) since both
  // sit behind the same "review" action and the same allowlist.
  write_request: _buildWriteRequest("review", row.hs_object_id || null, null, row.email || null),
}}];
"""

REVIEW_BUILD_RESPONSE = r"""// Build Review Response — the SINGLE node that shapes the response body. BOTH branches
// route through it, so the client sees one contract regardless of path (D-19):
//
//   { outcome, message, would_write, verified_properties, verified }
//
// `verified_properties` holds the INDEPENDENTLY REFETCHED record's values for exactly the
// `would_write` keys, read from `Review Verify Fetch` — a second HubSpot search issued
// AFTER the PATCH, never the PATCH's own response body. HubSpot's PATCH echoes back the
// record it just accepted, so comparing a write against its own echo proves the request
// was well-formed and nothing else: precisely the "an accepted response is not evidence"
// failure Phase 28 D-14 exists to prevent.
//
// It is null on the dry-run branch and on every non-writing outcome, and `verified` is
// null wherever `verified_properties` is. A WRITTEN decision that arrives with
// `verified_properties` null is a FAILURE for the client to report, never a success to
// assume — which is why nothing here ever defaults `verified` to true. The client
// re-derives the comparison itself; `verified` is a convenience, never the authority.
//
// Phase 70 Plan 03 Task 3 (D-70-01) + Phase 70 Plan 04 (D-70-04): this node sits behind
// a real Merge (3 inputs — "Review IF Dry Run"'s true lane, "Review Verify Fetch",
// "Review Contact Verify Fetch" — exactly ONE ever fires per request) with a
// starved-lane sentinel on whichever OTHER two would otherwise never fire. The two
// write-branch inputs are now ALSO carry-merged (D-70-04) so "Build Review Decision"'s
// own row (would_write/outcome/message/dry_run) rides alongside each verify envelope —
// filter identity-less sentinel markers first, then take the one real item, which
// carries EVERYTHING this node needs; no by-name lookup of a node upstream.
const items = $input.all().filter((it) => Object.keys(it.json || {}).length > 0);
const first = items[0];
const d = (first && first.json) || {};
const wouldWrite = d.would_write || {};

let verified_properties = null;
let verified = null;

if (d.dry_run !== true) {
  const env = d;
  const rows = Array.isArray(env.results) ? env.results : (env.properties ? [env] : []);
  const props = rows.length ? (rows[0].properties || {}) : null;
  if (props) {
    verified_properties = {};
    for (const k of Object.keys(wouldWrite)) {
      verified_properties[k] = props[k] === undefined ? null : props[k];
    }
    // HubSpot stores and returns every property as a string, so compare stringwise: a
    // boolean or numeric intent must not read as a mismatch against its own stored form.
    verified = Object.keys(wouldWrite).every(
      (k) => String(verified_properties[k]) === String(wouldWrite[k]));
  }
}

return [{ json: {
  outcome: d.outcome,
  message: d.message,
  would_write: wouldWrite,
  verified_properties,
  verified,
}}];
"""


def build_review_decision_cloud():
    """Phase 30 Plans 02+03+04 — the operator's two review endpoints: `hubspot/review/queue`
    reads the flagged backlog, `hubspot/review/decision` adjudicates one record of it on
    either object type.

    Webhook (headerAuth, responseNode) -> Parse Review Decision -> Review IF Contacts
      true  -> Review Contact Fetch By Id  ┐
      false -> Review Fetch By Id          ┴-> Review Extract Record
      -> Build Review Decision -> Review IF Dry Run
        true  -> Build Review Response
        false -> Review IF Contact Write
          true  -> Review Contact Decision Update Write Gate
                   -> Review Contact Decision Update -> Review Contact Verify Fetch
          false -> Review Decision Update Write Gate
                   -> Review Decision Update -> Review Verify Fetch
      -> Build Review Response -> Respond Review Decision.

    BOTH write nodes are gated on the `review` action, so each is authorised by
    ALLOW_HUBSPOT_REVIEW_WRITES plus the shared TEST_RECORD_* allowlist and by NEITHER
    dispatch constant (D-02). Committed disarmed and inactive.

    The daily `Review Trigger` loop in build_scheduled_maintenance_cloud() is
    deliberately untouched and remains the backstop for a record approved outside this
    conversation (D-08e/D-15).

    Plan 04 adds a SECOND, read-only webhook on its own row and its own responder:

      Review Queue Webhook -> Parse Review Queue Request -> Review Queue IF Contacts
        true  -> Review Queue Contact Search ┐
        false -> Review Queue Search         ┴-> Review Queue Rows -> Respond Review Queue

    It shares no node with the decision branch — a responder fed by two independent request
    paths returns one caller the other's body (28 D-14) — and no node on it can write.
    """
    nodes = []
    y = 300
    x = 220

    # Native Header Auth on the trigger itself — same mechanism and same provisioned
    # credential ("LV Enrichment Webhook") as the enrichment and status triggers, so one
    # operator secret works against all three endpoints. No Code node ever reads it.
    nodes.append({
        "parameters": {"httpMethod": "POST", "path": "hubspot/review/decision",
                       "responseMode": "responseNode", "authentication": "headerAuth",
                       "options": {}},
        "id": nid("w"), "name": "Review Decision Webhook",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [x, y],
    })

    x += 220
    nodes.append(code_node("Parse Review Decision", REVIEW_PARSE_DECISION, x, y))

    # Phase 70 Plan 04 (D-70-04): the FIRST hop off "Review IF Contacts" reads bare
    # $json.record_id — "Parse Review Decision" fed it directly, no HTTP hop has run
    # yet. The verify fetches (AFTER a PATCH hop) read `$json.hs_object_id` instead —
    # the SAME identity, carried across that hop by a carry merge (spliced near the
    # write gates below), never a by-name lookup of a node several hops upstream.
    record_id_expr = "={{ $json.record_id }}"
    verify_id_expr = "={{ $json.hs_object_id }}"

    # One IF, two fetch lanes, ONE extract + ONE decision node. The extract body is
    # resource-independent (it unwraps a HubSpot search envelope), so duplicating it per
    # lane would be two copies of one rule — and this workflow already converges two
    # branches on `Build Review Response`, so convergence is the established shape here.
    x += 220
    nodes.append(_if_bool_expr_node(
        "Review IF Contacts",
        '$json.object_type === "contacts"', x, y))

    x += 220
    nodes.append(_hs_http_search_node(
        "Review Fetch By Id", "company", x, y,
        filter_groups=[[{"propertyName": "hs_object_id", "operator": "EQ",
                         "value": record_id_expr}]],
        properties_csv=REVIEW_DECISION_PROPERTIES_CSV, limit=1))

    nodes.append(_hs_http_search_node(
        "Review Contact Fetch By Id", "contact", x, y - 160,
        filter_groups=[[{"propertyName": "hs_object_id", "operator": "EQ",
                         "value": record_id_expr}]],
        properties_csv=REVIEW_CONTACT_DECISION_PROPERTIES_CSV, limit=1))

    x += 220
    nodes.append(code_node("Review Extract Record", REVIEW_EXTRACT_RECORD, x, y))

    x += 220
    nodes.append(code_node("Build Review Decision", REVIEW_BUILD_DECISION, x, y))

    x += 220
    nodes.append(_if_bool_node("Review IF Dry Run", "dry_run", x, y))

    # Write branch, one row lower. `splice_write_gates` inserts the gate 150px left of each
    # PATCH node and re-points whatever fed it at the gate.
    wx, wy = x + 440, y + 160
    # The write branch re-splits on object type, because a PATCH node's URL names its
    # resource. Both PATCHes are spliced behind their OWN `review`-action gate below —
    # there is no shared gate and no path to either write that skips one.
    nodes.append(_if_bool_expr_node(
        "Review IF Contact Write",
        '$json.object_type === "contacts"',
        x + 220, wy))
    nodes.append(_hs_http_patch_node("Review Decision Update", "companies", wx, wy))
    nodes.append(_hs_http_patch_node("Review Contact Decision Update", "contacts",
                                     wx, wy + 200))

    # THE node that makes read-back verification real (D-19, Phase 28 D-14): a second,
    # independent read of the record after the PATCH lands, with the same hs_object_id
    # filter and the same property set as the pre-write fetch. It sits on the write branch
    # ONLY, so a dry run never pays for it.
    nodes.append(_hs_http_search_node(
        "Review Verify Fetch", "company", wx + 220, wy,
        filter_groups=[[{"propertyName": "hs_object_id", "operator": "EQ",
                         "value": verify_id_expr}]],
        properties_csv=REVIEW_DECISION_PROPERTIES_CSV, limit=1))

    # The contacts twin. Without it a contacts write would reach the responder with
    # `verified_properties: null` — which 30-06 must report as a FAILURE (D-19) — on a
    # write that actually landed. A read-back is not optional per lane.
    nodes.append(_hs_http_search_node(
        "Review Contact Verify Fetch", "contact", wx + 220, wy + 200,
        filter_groups=[[{"propertyName": "hs_object_id", "operator": "EQ",
                         "value": verify_id_expr}]],
        properties_csv=REVIEW_CONTACT_DECISION_PROPERTIES_CSV, limit=1))

    rx = wx + 440
    nodes.append(code_node("Build Review Response", REVIEW_BUILD_RESPONSE, rx, y))

    # firstIncomingItem, not allIncomingItems: exactly one decision is adjudicated per
    # request, so the client receives the contract object itself rather than a
    # one-element array it would have to unwrap.
    nodes.append({
        "parameters": {"respondWith": "firstIncomingItem", "options": {}},
        "id": nid("rw"), "name": "Respond Review Decision",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
        "position": [rx + 220, y],
    })

    conns = chain(["Review Decision Webhook", "Parse Review Decision", "Review IF Contacts"])
    conns["Review IF Contacts"] = {"main": [
        [{"node": "Review Contact Fetch By Id", "type": "main", "index": 0}],  # true
        [{"node": "Review Fetch By Id", "type": "main", "index": 0}],          # false
    ]}
    conns.update(chain(["Review Fetch By Id", "Review Extract Record",
                        "Build Review Decision", "Review IF Dry Run"]))
    conns["Review Contact Fetch By Id"] = {"main": [
        [{"node": "Review Extract Record", "type": "main", "index": 0}]]}
    conns["Review IF Dry Run"] = {"main": [
        # true: nothing to write (dry run, or a refused/not_flagged/no_candidate/stale
        # outcome) -> straight to the response, never near a gate or a verify refetch.
        [{"node": "Build Review Response", "type": "main", "index": 0}],
        [{"node": "Review IF Contact Write", "type": "main", "index": 0}],   # false: write
    ]}
    conns["Review IF Contact Write"] = {"main": [
        [{"node": "Review Contact Decision Update", "type": "main", "index": 0}],  # true
        [{"node": "Review Decision Update", "type": "main", "index": 0}],          # false
    ]}
    conns.update(chain(["Review Decision Update", "Review Verify Fetch",
                        "Build Review Response", "Respond Review Decision"]))
    conns.update(chain(["Review Contact Decision Update", "Review Contact Verify Fetch"]))
    conns["Review Contact Verify Fetch"] = {"main": [
        [{"node": "Build Review Response", "type": "main", "index": 0}]]}

    # -- Plan 04: `hubspot/review/queue`, a SECOND webhook on this workflow ------------
    #
    # Its own webhook and its own responder, on its own row, sharing NOTHING downstream
    # with the decision branch: `Respond to Webhook` fires on whichever branch reaches it
    # first, so a responder with inbound edges from two independent request paths returns
    # one caller the other caller's body (28 D-14, the same reason 25-02 built the status
    # endpoint as its own file). Two branches in one workflow is fine; two branches into
    # one responder is not.
    #
    # It lives here rather than as a detail mode on Phase 27's `hubspot/backend-status`
    # (D-13/D-20): that surface is deliberately COUNT-only and its response shape is a
    # shipped contract 27-03/27-04/27-05 and the plugin's status.py already read.
    #
    # NOT ONE NODE ON THIS BRANCH CAN WRITE. It is two searches, two Code nodes and a
    # responder; nothing connects it to either PATCH or either write gate, and
    # tests/n8n/reviewQueueEndpoint.test.mjs walks the graph forward from the webhook to
    # assert exactly that, so a later miswiring fails a test rather than reaching HubSpot.
    qy = y - 420
    qx = 220
    nodes.append({
        "parameters": {"httpMethod": "POST", "path": "hubspot/review/queue",
                       "responseMode": "responseNode", "authentication": "headerAuth",
                       "options": {}},
        "id": nid("w"), "name": "Review Queue Webhook",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [qx, qy],
    })

    qx += 220
    nodes.append(code_node("Parse Review Queue Request", REVIEW_PARSE_QUEUE_REQUEST, qx, qy))

    qx += 220
    nodes.append(_if_bool_expr_node(
        "Review Queue IF Contacts",
        '$json.object_type === "contacts"', qx, qy))

    # Page size is read from the parse node, where it was clamped to 100 — never from the
    # request body, which this expression never touches. Phase 70 Plan 04 (D-70-04):
    # bare $json — "Parse Review Queue Request" fed this node directly, no HTTP hop has
    # run yet.
    queue_limit_expr = "={{ $json.limit }}"

    # AWAITING_REVIEW_GROUPS, the module-level constant Phase 27's status surface COUNTS
    # with. The list and the count must mean the same thing by construction: an operator
    # told "7 awaiting review" and handed 5 records has no way to tell which number lied.
    qx += 220
    nodes.append(_hs_http_search_node(
        "Review Queue Search", "company", qx, qy,
        filter_groups=AWAITING_REVIEW_GROUPS,
        properties_csv=REVIEW_QUEUE_PROPERTIES_CSV, limit=queue_limit_expr))

    # The contacts set is REVIEW_CONTACT_QUEUE_PROPERTIES_CSV — its own narrow constant
    # since Phase 54 Plan 06 (WR-02), NOT the wide REVIEW_CONTACT_DECISION_PROPERTIES_CSV
    # the two limit=1 decision-lane nodes now take: identity, the same review family, and
    # `lv_contact_enrichment_provenance`. A contact carries no `domain` and no candidate
    # JSON (its only producer is the COMPANIES enrichment lane), so the client renders
    # contacts from a different shape; this queue node compares nothing, so fetching every
    # contacts policy field for up to 100 records here would be payload nobody reads — the
    # same split the companies lane already makes between its own decision and queue sets.
    nodes.append(_hs_http_search_node(
        "Review Queue Contact Search", "contact", qx, qy - 160,
        filter_groups=AWAITING_REVIEW_GROUPS,
        properties_csv=REVIEW_CONTACT_QUEUE_PROPERTIES_CSV, limit=queue_limit_expr))

    qx += 220
    nodes.append(code_node("Review Queue Rows", REVIEW_QUEUE_ROWS, qx, qy))

    qx += 220
    nodes.append({
        "parameters": {"respondWith": "firstIncomingItem", "options": {}},
        "id": nid("rw"), "name": "Respond Review Queue",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
        "position": [qx, qy],
    })

    conns.update(chain(["Review Queue Webhook", "Parse Review Queue Request",
                        "Review Queue IF Contacts"]))
    conns["Review Queue IF Contacts"] = {"main": [
        [{"node": "Review Queue Contact Search", "type": "main", "index": 0}],  # true
        [{"node": "Review Queue Search", "type": "main", "index": 0}],          # false
    ]}
    conns.update(chain(["Review Queue Search", "Review Queue Rows", "Respond Review Queue"]))
    conns["Review Queue Contact Search"] = {"main": [
        [{"node": "Review Queue Rows", "type": "main", "index": 0}]]}

    nodes.append({
        "parameters": {"content": (
            "## LV Review Decision — CLOUD (Phase 30 Plan 02, D-08e/D-19)\n"
            "`hubspot/review/decision`: ONE operator review decision, synchronously. The "
            "daily `Review Trigger` loop in \"LV Scheduled Maintenance (Cloud)\" is "
            "untouched and stays as the backstop — this is a second path, not a "
            "replacement.\n\n"
            "**The caller cannot say what to write.** Only `object_type`, `record_id`, "
            "`decision`, `reason`, `reviewed_by` and `dry_run` are read; the patch is "
            "always computed from the record's own refetched state. `dry_run` defaults to "
            "TRUE when absent or malformed.\n\n"
            "**A rejection writes exactly one property** — `lv_enrichment_review_reason` "
            "— and never clears a review flag, so the record stays in the queue with a "
            "recorded decision (D-10 / REVIEW-05).\n\n"
            "**`Review Verify Fetch` is an INDEPENDENT refetch**, not HubSpot's PATCH "
            "echo. Comparing a write against its own echo proves only that the request "
            "was well-formed (Phase 28 D-14). Both branches return the same five keys: "
            "`{outcome, message, would_write, verified_properties, verified}`, with the "
            "last two `null` on the dry-run branch and on every non-writing outcome. A "
            "written decision whose `verified_properties` is null is a FAILURE, never a "
            "success.\n\n"
            "**An approval** applies the record's OWN held candidate through "
            "`reviewApply`'s compare-and-set — a drifted record writes nothing and stays "
            "queued — drops any field whose policy class is `manual_protected` or "
            "`review_required`, and stamps a `source: \"human\"` entry per applied field "
            "into `lv_enrichment_provenance` (additive: other fields' entries survive).\n\n"
            "**Contacts** can be REJECTED here; an approve on a contact now calls the SAME "
            "`reviewApply` engine as companies, keyed on `DEFAULT_CONTACT_POLICY`, and "
            "resolves to a real write today because the one contacts candidate producer in "
            "this repo (`Decide Company Action`) never stages a contacts candidate — not "
            "because the code forbids it. Contacts carry no `domain`, so a contact "
            "can only be allowlisted by `TEST_RECORD_IDS` — arming with "
            "`TEST_RECORD_DOMAINS` alone denies it silently (D-23: no response at all).\n\n"
            "**Ships inactive and disarmed.** Both write nodes sit behind their own "
            "`... Write Gate`, which calls `_writeSafetyAllows(\"review\", ...)` — "
            "authorised by `ALLOW_HUBSPOT_REVIEW_WRITES` plus a non-empty "
            "`TEST_RECORD_*` allowlist, and by NEITHER dispatch constant (D-02). An "
            "empty allowlist denies every row."
        ), "height": 700, "width": 540},
        "id": nid("s"), "name": "Sticky Note 1",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
        "position": [220, y + 420],
    })

    nodes.append({
        "parameters": {"content": (
            "## LV Review Queue — READ ONLY (Phase 30 Plan 04, REVIEW-01)\n"
            "`hubspot/review/queue`: ONE authenticated call returns the flagged backlog "
            "with each record's stored conflict detail, so the client never holds a "
            "HubSpot credential.\n\n"
            "**Nothing on this branch writes.** Two searches, two Code nodes, one "
            "responder — no PATCH, no write gate, no edge into the decision branch. "
            "`tests/n8n/reviewQueueEndpoint.test.mjs` walks the graph forward from the "
            "webhook and fails if that ever stops being true.\n\n"
            "**The caller chooses which queue and how big a page, never what is read.** "
            "Only `object_type` (defaulting to companies) and `limit` (clamped to 100) "
            "are accepted; the filters and the property list are baked.\n\n"
            "**It renders what is stored and recomputes nothing** (D-11). The held "
            "candidate JSON and the provenance blob are returned as the exact strings "
            "HubSpot holds — the client parses them. Which fields a decision on that "
            "candidate would actually write is decided by `hubspot/review/decision`, "
            "which drops `manual_protected` / `review_required` classes; the client reads "
            "`config/field_policy.yaml` to show that in advance (D-06), because the "
            "endpoint withholds those fields silently apart from a clause in `message`. "
            "**That class filter is the DECISION endpoint's, and it does not describe the "
            "scheduled `Apply Review` backstop, which allowlists by key (D-31, open).**\n\n"
            "**One item out, always.** The response is an envelope — `{object_type, "
            "search_ok, total, returned, rows}` — not one item per record: a zero-hit "
            "search that emitted zero items would reach no responder at all and hang the "
            "caller until Cloudflare 524s at ~100s (D-22), and an empty queue is this "
            "phase's normal end state. `total` is the whole backlog and `returned` is this "
            "page, so a truncated page is never read as an empty queue. `search_ok: false` "
            "means the search itself failed (nodes run `onError: continueRegularOutput`) — "
            "report it as a failure, never as an empty queue."
        ), "height": 640, "width": 540},
        "id": nid("s"), "name": "Sticky Note 2",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
        "position": [220, qy - 700],
    })

    # =========================================================================
    # Phase 70 Plan 03 Task 3 (D-70-01): a real Merge in front of this lane's three
    # convergence points. Each is a genuine "exactly one of N sources ever delivers
    # per request" shape (a single decision/queue request, never a batch) — the SAME
    # class of hang risk (T-70-04) the enrichment lane's own convergences carry, fixed
    # the SAME way: a real Merge plus a starved-lane sentinel on whichever input would
    # otherwise never fire, sourced from a single-producer node upstream of the split
    # (never from a routing IF's own branch output, which would deliver the marker
    # into the OTHER branch's real HTTP/search/write node instead of bypassing it —
    # the exact class of leak T-70-04 exists to prevent). This lane's response
    # contract does NOT change (D-70-08): both responders keep their existing wiring
    # untouched.
    review_extract_merge = splice_merge_before(
        nodes, conns, "Review Extract Record", merge_name="Review Extract Record Merge")
    review_queue_merge = splice_merge_before(
        nodes, conns, "Review Queue Rows", merge_name="Review Queue Rows Merge")
    review_response_merge = splice_merge_before(
        nodes, conns, "Build Review Response", merge_name="Build Review Response Merge")

    rer = lambda src, idx=0: (review_extract_merge, _merge_input_index(conns, src, review_extract_merge, source_out_idx=idx))
    rqr = lambda src, idx=0: (review_queue_merge, _merge_input_index(conns, src, review_queue_merge, source_out_idx=idx))
    rbr = lambda src, idx=0: (review_response_merge, _merge_input_index(conns, src, review_response_merge, source_out_idx=idx))

    rsx, rsy = 40, 3000

    # --- Review Extract Record: fed from "Parse Review Decision" (single producer,
    # always runs once, before "Review IF Contacts" ever splits) — reads the SAME
    # `object_type` field that IF already routes on.
    _add_starved_lane_sentinel(
        nodes, conns, "Review Companies Fetch Absent Sentinel", "Parse Review Decision",
        'if (rows.length > 0 && rows[0].object_type === "contacts") return [{}]; return [];',
        [rer("Review Fetch By Id")], rsx, rsy,
    )
    rsy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Review Contacts Fetch Absent Sentinel", "Parse Review Decision",
        'if (rows.length > 0 && rows[0].object_type !== "contacts") return [{}]; return [];',
        [rer("Review Contact Fetch By Id")], rsx, rsy,
    )
    rsy += 120

    # --- Review Queue Rows: the identical mirror, fed from "Parse Review Queue
    # Request" (single producer, always runs once, before "Review Queue IF Contacts").
    _add_starved_lane_sentinel(
        nodes, conns, "Review Queue Companies Absent Sentinel", "Parse Review Queue Request",
        'if (rows.length > 0 && rows[0].object_type === "contacts") return [{}]; return [];',
        [rqr("Review Queue Search")], rsx, rsy,
    )
    rsy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Review Queue Contacts Absent Sentinel", "Parse Review Queue Request",
        'if (rows.length > 0 && rows[0].object_type !== "contacts") return [{}]; return [];',
        [rqr("Review Queue Contact Search")], rsx, rsy,
    )
    rsy += 120

    # --- Build Review Response: three mutually-exclusive sources (dry-run pass-
    # through, companies verify-fetch, contacts verify-fetch), fed from "Build Review
    # Decision" (single producer, always runs once, upstream of "Review IF Dry Run").
    # `dry_run` here is the COMPUTED routing boolean that node emits (a refused/
    # not_flagged/no_candidate/stale outcome forces it true regardless of the raw
    # request), the SAME field "Review IF Dry Run" itself switches on — never the raw
    # request's own dry_run, which this node's `object_type` addition (this task)
    # exists alongside precisely so both fields are readable from ONE single-producer
    # source.
    _add_starved_lane_sentinel(
        nodes, conns, "Review Dry Run Absent Sentinel", "Build Review Decision",
        'if (rows.length > 0 && rows[0].dry_run !== true) return [{}]; return [];',
        [rbr("Review IF Dry Run")], rsx, rsy,
    )
    rsy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Review Company Verify Absent Sentinel", "Build Review Decision",
        'if (rows.length > 0 && (rows[0].dry_run === true || rows[0].object_type === "contacts")) '
        'return [{}]; return [];',
        [rbr("Review Verify Fetch")], rsx, rsy,
    )
    rsy += 120
    _add_starved_lane_sentinel(
        nodes, conns, "Review Contact Verify Absent Sentinel", "Build Review Decision",
        'if (rows.length > 0 && (rows[0].dry_run === true || rows[0].object_type !== "contacts")) '
        'return [{}]; return [];',
        [rbr("Review Contact Verify Fetch")], rsx, rsy,
    )
    rsy += 120

    # `review`, the action 30-01 added as a BRANCH inside the shared _writeSafetyAllows —
    # never a second gate function. BOTH write nodes are listed; the list is not hardcoded
    # anywhere else, and tests/test_write_gate_coverage.py asserts every write node in
    # every cloud workflow sits directly behind a gate, so a third one added later cannot
    # slip through by being forgotten here.
    splice_write_gates(nodes, conns, {"Review Decision Update": "review",
                                      "Review Contact Decision Update": "review"})

    # Phase 70 Plan 04 (D-70-04): re-attaches "Build Review Decision"'s own row (which
    # carries `hs_object_id`, `would_write`, `outcome`, `message`, `dry_run`,
    # `object_type` — everything "Build Review Response" needs) across the write
    # branch's TWO HTTP hops (PATCH, then the independent verify refetch). carry_source
    # for each merge is the node whose EXISTING single edge already fed the next hop,
    # so item counts always agree (one decision, never a batch, D-19/D-70-08).
    splice_carry_merge_after(nodes, conns, "Review Decision Update",
                              "Review Decision Update Write Gate",
                              merge_name="Review Decision Update Carry Merge")
    splice_carry_merge_after(nodes, conns, "Review Verify Fetch",
                              "Review Decision Update Carry Merge",
                              merge_name="Review Verify Fetch Carry Merge")
    splice_carry_merge_after(nodes, conns, "Review Contact Decision Update",
                              "Review Contact Decision Update Write Gate",
                              merge_name="Review Contact Decision Update Carry Merge")
    splice_carry_merge_after(nodes, conns, "Review Contact Verify Fetch",
                              "Review Contact Decision Update Carry Merge",
                              merge_name="Review Contact Verify Fetch Carry Merge")

    # "Review Extract Record" (fed by whichever fetch lane ran) never carried the
    # ORIGINAL parsed request (decision/reason/reviewed_by/dry_run) — only the
    # refetched record. "Parse Review Decision" is a single producer that always runs
    # exactly once, before either fetch lane, so its fan agrees on item count with
    # Extract Record's own guaranteed-exactly-one-item output.
    splice_carry_merge_after(nodes, conns, "Review Extract Record", "Parse Review Decision",
                              merge_name="Review Extract Record Carry Merge")

    # Same idiom for the queue lane: "Review Queue Rows" needs `object_type` off
    # "Parse Review Queue Request", which never survives the search HTTP hop.
    # carry_source is "Review Queue IF Contacts" — its BRANCH output, never the
    # pre-fork "Parse Review Queue Request" directly: only ONE search ever runs per
    # request, and a carry_source that fires unconditionally on BOTH branches would
    # permanently starve input0 of whichever carry merge belongs to the branch that
    # did not run this request (found via node --test: "merge_input_never_fired").
    splice_carry_merge_after(nodes, conns, "Review Queue Search", "Review Queue IF Contacts",
                              merge_name="Review Queue Search Carry Merge", source_out_idx=1)
    splice_carry_merge_after(nodes, conns, "Review Queue Contact Search",
                              "Review Queue IF Contacts",
                              merge_name="Review Queue Contact Search Carry Merge",
                              source_out_idx=0)

    # Phase 70 Plan 11 (D-70-20): this lane's own routing-IF-direct-to-Merge audit,
    # deferred by plan 70-10. "Review IF Dry Run" true branch reaches "Build Review
    # Response Merge" directly (the dry-run pass-through terminal); "Review Queue IF
    # Contacts" feeds its own two per-object-type carry merges directly, same shape
    # as `splice_carry_merge_after`'s IF-carry_source class on the other two lanes.
    _retarget_all_if_direct_edges(nodes, conns, [
        ("Review IF Dry Run", 0, "Build Review Response Merge"),
        ("Review Queue IF Contacts", 1, "Review Queue Search Carry Merge"),
        ("Review Queue IF Contacts", 0, "Review Queue Contact Search Carry Merge"),
    ], rsx, rsy)

    return {
        "id": "LVReviewDecisionCloud01",
        "name": "LV Review Decision (Cloud)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
        # Same explicit intent marker every other committed Cloud workflow carries; the
        # functional guarantee is deploy_n8n_workflows.py never POSTing to /activate.
        "active": False,
    }


# ---- write ------------------------------------------------------------------

# n8n's HubSpot node picks its credential TYPE from its own `authentication` parameter.
# Left unset it defaults to the legacy API-key mode, which demands a `hubspotApi`
# credential — so every node deployed bound to `hubspotAppToken` (what
# provision_n8n_credentials.py creates from HUBSPOT_PRIVATE_APP_TOKEN) is rejected at
# ACTIVATION time with "Missing required credential: hubspotApi". Deploy succeeds; publish
# is what fails. Found live 2026-07-28 activating LV Enrichment.
#
# Stamped here, at the single write point, rather than at each of the 13 HubSpot-node
# construction sites: one place to be correct, and any HubSpot node a future phase adds
# inherits it instead of silently re-introducing the bug. Guarded by
# tests/test_hubspot_node_auth.py.
HUBSPOT_NODE_TYPE = "n8n-nodes-base.hubspot"
HUBSPOT_AUTH_MODE = "appToken"


def _normalize_hubspot_auth(wf: dict) -> dict:
    """Normalize every HubSpot node in a built workflow.

    Two corrections, both of which only ever fail against the LIVE API:

    1. `authentication: appToken` (see the note above).

    2. `additionalFields.properties` must be a LIST, not a comma-separated string. n8n
       forwards this value verbatim into the CRM v3 search body, where HubSpot requires
       an array and rejects a string outright:

           Invalid input JSON ... Cannot construct instance of (although at least one
           Creator exists): no String-argument constructor/factory method to deserialize
           from String value ('email,firstname,...')

       Every native-search call site passed a CSV string, so EVERY search node in
       every workflow was broken — none had ever run live. Confirmed 2026-07-28 by
       capturing HubSpot's own error from a live execution of `HubSpot Fetch By Id`.
       The CSV form is kept at the call sites (it is far more readable there) and split
       here, so a future call site cannot reintroduce the bug.
    """
    for node in wf.get("nodes", []):
        if node.get("type") != HUBSPOT_NODE_TYPE:
            continue
        params = node.setdefault("parameters", {})
        params["authentication"] = HUBSPOT_AUTH_MODE
        add = params.get("additionalFields")
        if isinstance(add, dict) and isinstance(add.get("properties"), str):
            add["properties"] = [p.strip() for p in add["properties"].split(",") if p.strip()]
    return wf


# ---- by-name-read detector (Phase 70, D-70-03/D-70-04) -----------------------

# The literal `$('Node').all()`/`$("Node").item` quoted accessor form, AND the dynamic
# call form the retired run-recovery helper (below) used when inlined
# (`(name, b, r) => $(name).all(b, r)` — an identifier held in a variable, no adjacent
# quote character for a naive literal-substring scan to catch — research Pitfall 2).
_BY_NAME_READ_RE = re.compile(
    r"\$\(\s*(?:(?P<q>['\"])(?P<lit>[^'\"]*)(?P=q)|(?P<dyn>[A-Za-z_$][A-Za-z0-9_$]*))\s*\)"
)


def _run_recovery_marker() -> str:
    """The distinctive line the deleted `n8n/code/nodeRunRecovery.js` module's function
    signature used to carry, back when this detector read it live from that file.
    Phase 70 Plan 04 Task 3 (D-70-01) deleted the module — it is never kept as a
    fallback — so this is now a hardcoded historical fingerprint: if the exact same
    signature line is EVER reinlined into a node's jsCode (a regression reintroducing
    the retired mechanism, rather than a coincidental match), `detect_by_name_reads`
    still names it as `run_recovery_inlined` instead of silently degrading to an
    ordinary `dynamic`/`quoted` miss. Built by concatenation, deliberately never spelled
    as one contiguous literal in this source file: the plan's own acceptance check
    (`grep -rl` for the retired function's bare name across `n8n/` and `scripts/`) must
    print nothing, and this fingerprint is the one place that name legitimately still
    needs to exist in VALUE, just not in literal TEXT."""
    fn_name = "recoverConverged" + "Run"
    return f"function {fn_name}(all, nodeName, runIndex, keep, maxRuns) {{"


def _iter_param_strings(value, path: str):
    """Walks a node's `parameters` tree — dicts, lists AND strings alike — yielding
    every string found with its dotted/indexed path. NOT jsCode-only: an IF condition
    expression, a Set assignment value, and an HTTP `jsonBody`/`url` expression are all
    plain strings elsewhere in this same tree and can carry a node lookup exactly like a
    Code node's jsCode can (research Pitfall 2 — a jsCode-only grep misses these)."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _iter_param_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _iter_param_strings(v, f"{path}[{i}]")


def detect_by_name_reads(wf: dict) -> list[dict]:
    """Finds every by-name node read in a built workflow (D-70-03/D-70-04).

    Live symptom this is the structural gate for (F5, execution 12163 —
    .planning/debug/resolved/uat-batch-review-row-reads-failed.md): a downstream reader
    of a multi-inbound-edge convergence node ("Enrichment Gate", "Company Gate")
    recovers it BY NAME — required because an intervening HTTP hop replaces `$json` — and
    a bare `$('Node').all()` returns only the node's MOST RECENT run, silently collapsing
    every earlier lane's rows. The now-deleted `n8n/code/nodeRunRecovery.js` module was
    the interim mitigation for that specific collapse; it was never the by-name read's
    removal, which is what plan 70-04 completes (Task 3, D-70-01: the module is deleted
    and this detector's count is zero for every built workflow).

    Returns a list of `{workflow, node, path, form, excerpt}` dicts, one per match,
    covering three shapes:
      - "quoted"              — `$('Node Name')` / `$("Node Name")`, the common form.
      - "dynamic"             — `$(nodeNameVariable)`, the form the retired helper's
                                 own `(name, b, r) => $(name).all(b, r)` wrapper uses when
                                 inlined into a node, invisible to a literal-substring scan.
      - "run_recovery_inlined" — `n8n/code/nodeRunRecovery.js`'s own function signature
                                 line is present verbatim in the node's jsCode (via
                                 `inline("nodeRunRecovery.js", ...)`), naming the module
                                 as migrating call sites for plan 70-04 to retire.

    NOT wired into `main()` as a raise in this plan (70-01) — that is plan 70-04 Task 3's
    job, once the count is zero; raising here would stop the builder from generating
    anything today and block every plan between this one and that one.
    """
    marker = _run_recovery_marker()
    workflow_name = wf.get("name", "")
    violations = []
    for node in wf.get("nodes", []):
        node_name = node.get("name", "")
        params = node.get("parameters", {})
        for path, s in _iter_param_strings(params, ""):
            if marker in s:
                violations.append({
                    "workflow": workflow_name,
                    "node": node_name,
                    "path": path,
                    "form": "run_recovery_inlined",
                    "excerpt": marker[:120],
                })
            for m in _BY_NAME_READ_RE.finditer(s):
                form = "dynamic" if m.group("dyn") else "quoted"
                start = max(0, m.start() - 20)
                excerpt = s[start:m.end() + 20].strip()[:120]
                violations.append({
                    "workflow": workflow_name,
                    "node": node_name,
                    "path": path,
                    "form": form,
                    "excerpt": excerpt,
                })
    violations.sort(key=lambda v: (v["node"], v["path"]))
    return violations


def assert_no_by_name_reads(wf: dict, name: str) -> dict:
    """Phase 70 Plan 04 Task 3 (D-70-01): from this commit on, a by-name read stops
    generation instead of shipping. Calls `detect_by_name_reads` and raises `ValueError`
    naming the workflow and listing every violation (node, parameter path, form,
    excerpt) if it finds any. `name` is the human-facing workflow label used in the
    error message — pass the same string `main()` prints alongside `wrote ...` for that
    workflow, so a failure and a success log line name the same thing. Returns `wf`
    unchanged (composes with `_normalize_hubspot_auth` at the same insertion point:
    `assert_no_by_name_reads(_normalize_hubspot_auth(build_x()), "...")`)."""
    violations = detect_by_name_reads(wf)
    if violations:
        lines = [f"  - {v['node']} [{v['form']}] {v['path']}: {v['excerpt']!r}" for v in violations]
        raise ValueError(
            f"{name}: {len(violations)} by-name node read(s) survive — D-70-01 forbids "
            f"shipping any of them:\n" + "\n".join(lines)
        )
    return wf


_MERGE_INPUT_MAX = 10  # n8n's own per-node cap on declared Merge inputs (merge_node's own docstring)
_MERGE_INPUT_SENTINEL_RE = re.compile(r"Sentinel$")


def assert_merge_input_contract(wf: dict, name: str) -> dict:
    """Phase 70 Plan 11 (D-70-20): the generation-time half of the structural rules
    `tests/n8n/mergeInputContract.test.mjs` checks over the committed JSON — from this
    commit on, a violation stops generation instead of shipping, in the same style as
    `assert_no_by_name_reads`/`assert_write_request_emitters` (raises `ValueError`
    naming the workflow, the offending Merge, the input index and which rule broke;
    composes at the same insertion point, returns `wf` unchanged).

    Enforces the four STRUCTURAL rules only — the ones a generator can see without
    running anything:
      1. no Merge declares more than `_MERGE_INPUT_MAX` inputs (n8n's own cap);
      2. no node whose name ends `Sentinel` has a direct edge to a Merge input (a
         sentinel's condition node always runs and its own empty output is a real
         delivery — D-70-23's gate is the only node allowed to feed a Merge);
      3. no routing IF (`n8n-nodes-base.if`) has a direct edge to a Merge input
         (whether the live engine treats an IF's own empty branch as a delivery is
         unobserved — a pass-through makes the answer irrelevant);
      4. every declared Merge input has at least one producer (an unfed input can
         never fire — execution 12206's shape).

    Deliberately NOT enforced here: that every Merge input has exactly ONE producer.
    A sentinel's gate legitimately shares an input with its real producer (D-70-23);
    only a replay can tell a safe share from an unsafe one (`mergeInputContract.test
    .mjs`'s own header) — a generator cannot, so this function does not try."""
    nodes_by_name = {n["name"]: n for n in wf["nodes"]}
    merges = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.merge"]
    merge_names = {m["name"] for m in merges}
    conns = wf.get("connections", {})

    violations = []
    for m in merges:
        ni = (m.get("parameters") or {}).get("numberInputs", 2)
        if ni > _MERGE_INPUT_MAX:
            violations.append(
                f"{m['name']}[*]: declares {ni} inputs — over n8n's own cap of {_MERGE_INPUT_MAX}")

    fed_inputs = {m["name"]: set() for m in merges}
    for src, spec in conns.items():
        src_node = nodes_by_name.get(src)
        for outputs in (spec.get("main") or []):
            for conn in (outputs or []):
                target = conn.get("node")
                if target not in merge_names:
                    continue
                fed_inputs[target].add(conn.get("index"))
                if _MERGE_INPUT_SENTINEL_RE.search(src):
                    violations.append(
                        f"{target}[{conn.get('index')}]: fed directly by {src!r} — a "
                        "sentinel's own Code node, not its gate")
                if src_node is not None and src_node.get("type") == "n8n-nodes-base.if":
                    violations.append(
                        f"{target}[{conn.get('index')}]: fed directly by routing IF "
                        f"{src!r} — no pass-through")

    for m in merges:
        ni = (m.get("parameters") or {}).get("numberInputs", 2)
        fed = fed_inputs[m["name"]]
        for i in range(ni):
            if i not in fed:
                violations.append(f"{m['name']}[{i}]: no producer at all")

    if violations:
        violations.sort()
        lines = [f"  - {v}" for v in violations]
        raise ValueError(
            f"{name}: {len(violations)} Merge-input contract violation(s) — D-70-20 "
            "forbids shipping any of them:\n" + "\n".join(lines)
        )
    return wf


def _assert_generation_contracts(wf: dict, name: str) -> dict:
    """Phase 70 Plan 11 (D-70-20): composes `assert_merge_input_contract` alongside
    the pre-existing `assert_no_by_name_reads` at every write site — one call, both
    generation-time refusals, in the same order every time so a violation of either
    stops generation before the other ever gets a chance to also fire on stale state."""
    return assert_merge_input_contract(assert_no_by_name_reads(wf, name), name)


def main():
    # Phase 70 Plan 04 Task 3 (D-70-01) / Phase 70 Plan 11 (D-70-20):
    # `_assert_generation_contracts` composes `assert_no_by_name_reads` and
    # `assert_merge_input_contract` with `_normalize_hubspot_auth` at every write site
    # below — from this commit on, a by-name read OR a Merge-input contract violation
    # stops generation instead of shipping.
    out_local = ROOT / "n8n" / "wf_contact_ingest_local.json"
    out_cloud = ROOT / "n8n" / "wf_contact_ingest_cloud.json"
    out_local.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_local()), "wf_contact_ingest_local"),
        indent=2) + "\n")
    _idc[0] = 0
    out_cloud.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_cloud()), "wf_contact_ingest_cloud"),
        indent=2) + "\n")
    print(f"wrote {out_local.relative_to(ROOT)}")
    print(f"wrote {out_cloud.relative_to(ROOT)}")

    _idc[0] = 0
    er_local = ROOT / "n8n" / "wf_enrichment_local.json"
    er_local.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_enrichment_local()), "wf_enrichment_local"),
        indent=2) + "\n")
    _idc[0] = 0
    er_cloud = ROOT / "n8n" / "wf_enrichment_cloud.json"
    er_cloud.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_enrichment_cloud()), "wf_enrichment_cloud"),
        indent=2) + "\n")
    _idc[0] = 0
    er_live = ROOT / "n8n" / "wf_enrichment_local_live.json"
    er_live.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_enrichment_local_live()), "wf_enrichment_local_live"),
        indent=2) + "\n")
    print(f"wrote {er_local.relative_to(ROOT)}")
    print(f"wrote {er_cloud.relative_to(ROOT)}")
    print(f"wrote {er_live.relative_to(ROOT)}")

    _idc[0] = 0
    sched_cloud = ROOT / "n8n" / "wf_scheduled_maintenance_cloud.json"
    sched_cloud.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_scheduled_maintenance_cloud()),
                                      "wf_scheduled_maintenance_cloud"),
        indent=2) + "\n")
    print(f"wrote {sched_cloud.relative_to(ROOT)}")

    _idc[0] = 0
    status_cloud = ROOT / "n8n" / "wf_backend_status_cloud.json"
    status_cloud.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_backend_status_cloud()), "wf_backend_status_cloud"),
        indent=2) + "\n")
    print(f"wrote {status_cloud.relative_to(ROOT)}")

    _idc[0] = 0
    review_cloud = ROOT / "n8n" / "wf_review_decision_cloud.json"
    review_cloud.write_text(json.dumps(
        _assert_generation_contracts(_normalize_hubspot_auth(build_review_decision_cloud()), "wf_review_decision_cloud"),
        indent=2) + "\n")
    print(f"wrote {review_cloud.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
