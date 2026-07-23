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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "n8n" / "code"

# Regenerate the taxonomy data module FIRST — before any inline() call below reads
# n8n/code/taxonomy.generated.js — so this builder can never emit a workflow carrying
# a stale vocabulary (spec TX-4/AR-4). gen_taxonomy_js.py is a sibling script; running
# this file directly (`python scripts/build_cloud_workflows.py`) puts scripts/ on
# sys.path[0], so the plain import resolves.
import gen_taxonomy_js  # noqa: E402
import gen_escalation_js  # noqa: E402

(CODE / "taxonomy.generated.js").write_text(gen_taxonomy_js.render())
(CODE / "escalation.generated.js").write_text(gen_escalation_js.render())

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
const rows = $input.all();
const emails = [];
const seen = new Set();
for (const it of rows) {
  const e = normalizeEmailBasic(it.json.email);
  if (e && !seen.has(e)) { seen.add(e); emails.push(e); }
}
return [{ json: { emails } }];
"""

APPLY_EMAIL = inline("normalizeEmail.js") + r"""

// --- n8n wrapper: merge the batch verifier response back onto every row ---
// Rebuilds N rows from the pre-batch node (Normalize Phone) and matches each
// row's email to the verifier result by address. If the verifier is
// unreachable / dropped an entry, fall NON-GATING to PROBABLY_VALID + review.
const rows = $('Normalize Phone').all();
let results = [];
try { results = ($('Verify Emails (batch)').first().json.results) || []; } catch (e) { results = []; }
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
// Maps the real HubSpot "Search by Email" node output (per row, same order)
// into the searchResultsByKey shape resolveIdentity expects. A HubSpot search
// with 0 results yields an empty id list => net_new/ambiguous downstream.
const rows = $('Normalize Phone').all();
const search = $('HubSpot Search by Email').all();
return rows.map((it, i) => {
  const row = it.json;
  const hits = [];
  const res = search[i] && search[i].json;
  if (res && res.id) hits.push(String(res.id));            // single-object result
  if (res && Array.isArray(res.results)) {                 // search list result
    for (const c of res.results) if (c && c.id) hits.push(String(c.id));
  }
  const srk = {};
  if (normalizeEmailBasicSafe(row.email) && hits.length) srk.email = hits;
  return { json: { ...row, searchResultsByKey: srk } };
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
return $input.all().map((it) => {
  const row = it.json;
  const candidate = {};
  for (const f of ["email", "firstname", "lastname", "jobtitle", "company"]) {
    if (row[f] != null && String(row[f]).trim() !== "") candidate[f] = row[f];
  }
  if (row.linkedin_url != null && String(row.linkedin_url).trim() !== "") {
    candidate.lv_linkedin_url = row.linkedin_url;
  }
  if (row.phone_normalized) candidate.phone = row.phone_normalized;
  // LOCAL/template: no existing HubSpot props fetched here => {} (blanks promote per policy).
  const merged = mergeContacts({}, candidate, undefined, { source: "csv", confidence: 80 });
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
  const allow_create = row.allow_create === true;
  const properties = _buildContactPatch(row.merge);
  let action;
  if (outcome === "match") action = "update";
  else if (outcome === "net_new") action = allow_create ? "create" : "review";
  else if (outcome === "ambiguous") action = "review";
  else action = "skip";
  return { json: {
    action,
    outcome,
    contact_id: id.contact_id || null,
    reason: id.reason || row.reject_reason || null,
    email_status: row.email_status || null,
    properties
  }};
});
"""

# ---- workflow assembly helpers ---------------------------------------------

_idc = [0]


def nid(prefix="n"):
    _idc[0] += 1
    return f"{prefix}{_idc[0]:04d}0000-0000-4000-8000-000000000000"


def code_node(name, js, x, y):
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

    return {
        "id": "LVcontactIngest01",
        "name": "LV Contact Ingest (local replica)",
        "nodes": nodes,
        "connections": chain(order),
        "settings": {},
    }


# ---- CLOUD workflow ---------------------------------------------------------

def build_cloud():
    nodes = []
    y = 300
    x = 220

    webhook = {
        "parameters": {"httpMethod": "POST", "path": "hubspot/contact-upload",
                       "responseMode": "lastNode", "options": {}},
        "id": nid("w"), "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [x, y],
    }
    nodes.append(webhook)

    x += 220
    set_cfg = {
        "parameters": {"assignments": {"assignments": [
            {"id": nid("a"), "name": "allow_create", "value": False, "type": "boolean"}
        ]}, "options": {}},
        "id": nid("g"), "name": "Set Config",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [x, y],
    }
    nodes.append(set_cfg)

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
    hs_search = {
        "parameters": {"resource": "contact", "operation": "search",
                       "filterGroupsUi": {"filterGroupsValues": []}, "additionalFields": {}},
        "id": nid("hs"), "name": "HubSpot Search by Email",
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x, y],
        "onError": "continueRegularOutput",
    }
    nodes.append(hs_search)

    for name, js in [("Adapt Search Results", ADAPT_SEARCH_RESULTS),
                     ("Resolve Identity", RESOLVE_IDENTITY),
                     ("Merge Contacts", MERGE_CONTACTS),
                     ("Decide Action", DECIDE_CLOUD)]:
        x += 220
        nodes.append(code_node(name, js, x, y))

    # IF Update -> HubSpot Update ; else IF Create -> HubSpot Create ; else Set Review
    x += 220
    if_update = _if_node("IF Update", "update", x, y)
    nodes.append(if_update)
    hs_update = {
        "parameters": {"resource": "contact", "operation": "update",
                       "contactId": "={{ $json.contact_id }}", "updateFields": {}},
        "id": nid("hu"), "name": "HubSpot Update",
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x + 220, y - 120],
    }
    nodes.append(hs_update)

    if_create = _if_node("IF Create", "create", x + 220, y + 60)
    nodes.append(if_create)
    hs_create = {
        "parameters": {"resource": "contact", "operation": "create",
                       "email": "={{ $json.properties.email }}", "additionalFields": {}},
        "id": nid("hc"), "name": "HubSpot Create",
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x + 440, y - 20],
    }
    nodes.append(hs_create)

    set_review = {
        "parameters": {"assignments": {"assignments": [
            {"id": nid("a"), "name": "queue", "value": "needs_review", "type": "string"}
        ]}, "options": {}},
        "id": nid("r"), "name": "Set Review",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [x + 440, y + 140],
    }
    nodes.append(set_review)

    conns = chain([
        "Webhook Trigger", "Set Config", "Extract From File", "Map Columns",
        "Normalize Phone", "Build Verify Batch", "Verify Emails (batch)", "Apply Email",
        "HubSpot Search by Email", "Adapt Search Results", "Resolve Identity",
        "Merge Contacts", "Decide Action", "IF Update",
    ])
    # IF branches
    conns["IF Update"] = {"main": [
        [{"node": "HubSpot Update", "type": "main", "index": 0}],   # true
        [{"node": "IF Create", "type": "main", "index": 0}],        # false
    ]}
    conns["IF Create"] = {"main": [
        [{"node": "HubSpot Create", "type": "main", "index": 0}],   # true (gated)
        [{"node": "Set Review", "type": "main", "index": 0}],       # false
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
# The 6 config flags (research/judge cost caps + model knobs) and 6 secrets both
# enrichment builders (local-live docker replica + Cloud webhook) consume. ONE dict/list
# each — every call site below reads THESE, never a builder-local literal, so a flag or
# secret added/dropped/renamed in one builder but not the other is structurally
# impossible (tests/test_builder_flag_parity.py proves it once the Cloud companies
# branch lands, Task 5).
CONFIG_FLAG_DEFAULTS = {
    "ALLOW_WEB_RESEARCH": "false",
    "MAX_WEB_RESEARCH_PER_RUN": "10",
    "ANTHROPIC_SONNET_MODEL": "claude-sonnet-5",
    "WEB_RESEARCH_MAX_SEARCHES": "5",
    "ALLOW_SONNET_ESCALATION": "false",
    "MAX_SONNET_VALIDATIONS_PER_RUN": "10",
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


# ---- shared inlined Code-node bodies (Cloud + local both use these) ----------

# Build identity search keys from the trigger payload (email/domain/linkedin).
ENRICH_BUILD_IDENTITY = inline("normalizeEmail.js") + r"""

// --- n8n wrapper: normalise the incoming identity into HubSpot search keys ---
return $input.all().map((it) => {
  const row = it.json;
  const email = normalizeEmailBasic(row.email);
  return { json: { ...row,
    object_type: row.object_type || "contacts",
    identity_keys: {
      email,
      domain: row.domain || (email ? email.split("@")[1] : null),
      linkedin_url: row.linkedin_url || null,
      // Name+company let the providers match when no email is in hand (the common
      // pre-enrichment case). ZoomInfo/Apollo accept firstName+lastName+companyName.
      firstName: row.firstname || row.first_name || null,
      lastName: row.lastname || row.last_name || null,
      companyName: row.company || row.companyName || null,
    },
  }};
});
"""

# Required-field set + policy for the staleness gate (contacts working set from
# ENRICHMENT-WORKFLOW-PLAN.md §3 + CLAUDE.md field_policy).
ENRICH_GATE = inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js") + r"""

// --- n8n wrapper: decideAction(existingRecord) -> create | enrich | skip ---
const REQUIRED = ["email", "jobtitle", "mobilephone"];
const POLICY = { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } };
const NOW = new Date().toISOString();
return $input.all().map((it) => {
  const row = it.json;
  const gate = decideAction(row.existingRecord || {}, REQUIRED, POLICY, NOW);
  return { json: { ...row, gate, action: gate.action } };
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
  return { json: { ...row, scored: { best, winners }, gap_flag } };
});
"""

# Hand scored winners to the non-clobber merge (email never promotes to canonical).
ENRICH_MERGE = inline("mergeContacts.js") + r"""

// --- n8n wrapper: mergeContacts(existingRecord, winners) non-clobber ---
// PN-1: linkedin_url is NOT HubSpot-native -> the merge candidate/canonical key is
// lv_linkedin_url. `winners.linkedin_url` (the scoreCandidates winner key, if a provider
// mapper ever populates it) stays unprefixed on the READ side, unrelated to this rename.
return $input.all().map((it) => {
  const row = it.json;
  if (!row.scored) return { json: { ...row, merge: null } };  // skip branch
  const winners = row.scored.winners || {};
  const candidate = {};
  for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority"]) {
    if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
  }
  if (winners.linkedin_url != null && String(winners.linkedin_url).trim() !== "") {
    candidate.lv_linkedin_url = winners.linkedin_url;
  }
  const merged = mergeContacts(row.existingRecord || {}, candidate, undefined,
                               { source: "waterfall", confidence: 85 });
  return { json: { ...row, merge: merged } };
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

# CLOUD: adapt the real HubSpot search node output into an existingRecord.
ENRICH_ADAPT_SEARCH = r"""// Adapt Search -> existingRecord — CLOUD variant.
// Maps the real HubSpot search node output (per row, same order) into the
// existingRecord shape enrichmentGate expects. 0 results => {} => CREATE.
const rows = $('Build Identity').all();
const search = $('HubSpot Search').all();
return rows.map((it, i) => {
  const row = it.json;
  const res = search[i] && search[i].json;
  let existingRecord = {};
  if (res) {
    if (res.properties) existingRecord = res.properties;                 // single object
    else if (Array.isArray(res.results) && res.results[0]) {             // search list
      existingRecord = res.results[0].properties || res.results[0] || {};
    } else if (res.id) existingRecord = res;
  }
  return { json: { ...row, existingRecord } };
});
"""

# LOCAL: provider waterfall MOCK — returns fixture-shaped raw responses.
ENRICH_PROVIDER_MOCK = (
    "// Provider Waterfall (MOCK) — LOCAL variant only.\n"
    "// Cloud replaces this with 3 real HTTP nodes (Lusha/Apollo/ZoomInfo). Here we\n"
    "// return the tests/fixtures/enrichment/*.json contact shapes so normalizeProviders\n"
    "// + scoreEnrichment run for real on realistic data. SKIP identities get no call.\n"
    "const LUSHA = " + json.dumps(_fixture("lusha_contact.json")) + ";\n"
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
  const patch = _buildContactPatch(row.merge);
  let hubspot_op = null;
  if (action === "create") {
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

# CLOUD: compute action + property patch; IF nodes route to real HubSpot write.
ENRICH_DECIDE_CLOUD = r"""// Decide Action — CLOUD variant.
// Computes action + the HubSpot property patch from the scored+merged winners.
// The IF nodes route create -> HubSpot Create, enrich -> HubSpot Update (GATED).
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
  const properties = _buildContactPatch(row.merge);
  return { json: {
    action,
    object_type: row.object_type || "contacts",
    contact_id: (row.existingRecord && row.existingRecord.hs_object_id) || null,
    gap_flag: row.gap_flag === true,
    properties
  }};
});
"""

# CLOUD: NORMALIZE+SCORE reads the 3 provider HTTP nodes by name and re-attaches
# the carried identity/gate context from the Gate node (HTTP nodes replace $json).
ENRICH_NORMALIZE_SCORE_CLOUD = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
) + r"""

// --- n8n wrapper (CLOUD): pull provider responses by node name, score best-per-field ---
function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }
const rows = $('Enrichment Gate').all().filter((it) => it.json.action !== "skip");
const lusha = nodeAll('Lusha Enrich');
const apollo = nodeAll('Apollo Match');
const zoominfo = nodeAll('ZoomInfo Enrich');
return rows.map((it, i) => {
  const row = it.json;
  const ot = row.object_type || "contacts";
  const p = {
    lusha: lusha[i] && lusha[i].json,
    apollo: apollo[i] && apollo[i].json,
    zoominfo: zoominfo[i] && zoominfo[i].json,
  };
  const cands = [
    ...toCandidates("lusha", p.lusha, ot),
    ...toCandidates("apollo", p.apollo, ot),
    ...toCandidates("zoominfo", p.zoominfo, ot),
  ];
  const gap_flag = cands.length === 0;
  const { best, winners } = scoreCandidates(cands, { now: new Date().toISOString() });
  return { json: { ...row, providers: p, scored: { best, winners }, gap_flag } };
});
"""

# CLOUD: ZoomInfo enrich with AUTONOMOUS token caching + refresh-on-401. Replaces the
# separate Auth + Enrich HTTP nodes: mints its own bearer, caches it in workflow static
# data, re-mints only when missing/near-expiry, and re-mints once + retries on a 401.
# Shared ZoomInfo preamble: cached bearer + JSON:API enrich helper. Parameterised by the
# GTM enrich URL so the contacts and companies nodes share ONE token-cache implementation
# (same $getWorkflowStaticData key -> one mint serves both branches).
def _zoom_preamble(enrich_url):
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

// identity_keys lives on the Enrichment Gate rows; $input here is the Apollo HTTP
// response (which has replaced $json), so pull identity by paired index from the Gate.
const gateRows = (function () { try { return $('Enrichment Gate').all(); } catch (e) { return []; } })();
const items = $input.all();
const out = [];
for (let i = 0; i < items.length; i++) {
  const item = items[i];
  const id = (gateRows[i] && gateRows[i].json && gateRows[i].json.identity_keys) || item.json.identity_keys || {};
  const person = toMatchPersonInput(id);
  // No usable match key -> skip the call (empty/keyless matchPersonInput is itself a 400).
  const payload = hasZoomKey(person)
    ? { data: { type: "ContactEnrich", attributes: { matchPersonInput: [person], outputFields: ZOOM_OUTPUT_FIELDS } } }
    : null;
  if (!payload) { out.push({ json: { skipped: "no zoominfo match key" } }); continue; }
  let token = await getToken.call(this);
  let res;
  try {
    res = await enrich.call(this, token, payload);
  } catch (e) {
    if (isAuthError(e.statusCode || e.httpCode || (e.response && e.response.statusCode))) {
      delete sd.zoominfo;                     // token rejected -> re-mint once + retry
      token = await mint.call(this);
      try { res = await enrich.call(this, token, payload); }
      catch (e2) { res = { error: String((e2 && e2.message) || e2) }; }
    } else {
      res = { error: String((e && e.message) || e) };  // non-auth error -> continue
    }
  }
  out.push({ json: res });
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

ENRICH_BUILD_REQUESTS = r"""// Build Live Provider Requests — LOCAL-LIVE variant.
// Turns identity_keys into the concrete per-provider request shapes the LIVE HTTP nodes
// reference by name (HTTP nodes replace $json with their response, so downstream nodes read
// requests via $('Build Requests').item). Lusha v2 = GET querystring; Apollo people/match =
// JSON body with reveal_personal_emails. ZoomInfo builds its own body from the Gate identity.
return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity_keys || {};
  const enc = encodeURIComponent;
  const q = [];
  const add = (k, v) => { if (v) q.push(enc(k) + "=" + enc(v)); };
  add("firstName", id.firstName); add("lastName", id.lastName);
  add("companyName", id.companyName); add("companyDomain", id.domain);
  add("email", id.email); add("linkedinUrl", id.linkedin_url);
  const lusha_url = "https://api.lusha.com/v2/person?" + q.join("&");
  const apollo_body = { reveal_personal_emails: true };
  if (id.email) apollo_body.email = id.email;
  if (id.domain) apollo_body.domain = id.domain;
  if (id.firstName) apollo_body.first_name = id.firstName;
  if (id.lastName) apollo_body.last_name = id.lastName;
  if (id.companyName) apollo_body.organization_name = id.companyName;
  return { json: { ...row, lusha_url, apollo_body } };
});
"""

# HubSpot read-only search body (existence check): by email if present, else first+last name.
HS_SEARCH_BODY_EXPR = (
    '={{ JSON.stringify({ filterGroups: [ { filters: '
    '($json.identity_keys.email ? [ { propertyName: "email", operator: "EQ", value: $json.identity_keys.email } ] '
    ': [ { propertyName: "firstname", operator: "EQ", value: $json.identity_keys.firstName }, '
    '{ propertyName: "lastname", operator: "EQ", value: $json.identity_keys.lastName } ]) } ], '
    'properties: ["email","firstname","lastname","jobtitle","phone","mobilephone",'
    '"lv_jobtitle_verified_at","lv_mobilephone_verified_at"], limit: 5 }) }}'
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

// identity_keys lives on the Company Gate rows; $input here is the Apollo Org HTTP
// response (which has replaced $json), so pull identity by paired index from the Gate.
const gateRows = (function () { try { return $('Company Gate').all(); } catch (e) { return []; } })();
const items = $input.all();
const out = [];
for (let i = 0; i < items.length; i++) {
  const item = items[i];
  const id = (gateRows[i] && gateRows[i].json && gateRows[i].json.identity_keys) || item.json.identity_keys || {};
  const co = toMatchCompanyInput(id);
  const payload = hasZoomCoKey(co)
    ? { data: { type: "CompanyEnrich", attributes: { matchCompanyInput: [co], outputFields: ZOOM_CO_OUTPUT_FIELDS } } }
    : null;
  if (!payload) { out.push({ json: { skipped: "no zoominfo company match key" } }); continue; }
  let token = await getToken.call(this);
  let res;
  try {
    res = await enrich.call(this, token, payload);
  } catch (e) {
    if (isAuthError(e.statusCode || e.httpCode || (e.response && e.response.statusCode))) {
      delete sd.zoominfo;                     // token rejected -> re-mint once + retry
      token = await mint.call(this);
      try { res = await enrich.call(this, token, payload); }
      catch (e2) { res = { error: String((e2 && e2.message) || e2) }; }
    } else {
      res = { error: String((e && e.message) || e) };  // non-auth error -> continue
    }
  }
  out.push({ json: res });
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
HS_CO_SEARCH_BODY_EXPR = (
    '={{ JSON.stringify({ filterGroups: [ { filters: '
    '[ { propertyName: "domain", operator: "EQ", value: $json.identity_keys.domain } ] } ], '
    'properties: ["name","domain","industry","annualrevenue","numberofemployees",'
    '"lv_org_type","lv_produces_content","lv_content_type","lv_is_hardware_vendor",'
    '"lv_is_gambling_operator","lv_icp_tier","lv_icp_fit_score","lv_anti_icp_flag",'
    '"lv_enrichment_provenance",'
    '"lv_org_type_verified_at","lv_produces_content_verified_at"], '
    'limit: 5 }) }}'
)

ENRICH_ADAPT_CO_SEARCH = r"""// Adapt Company Search -> existingRecord — companies branch.
// Same contract as the contacts Adapt Search: per-row, same order, 0 results => {} => CREATE.
const rows = $('Build Company Identity').all();
const search = $('HubSpot Company Search').all();
return rows.map((it, i) => {
  const row = it.json;
  const res = search[i] && search[i].json;
  let existingRecord = {};
  if (res) {
    if (res.properties) existingRecord = res.properties;                 // single object
    else if (Array.isArray(res.results) && res.results.length) {
      existingRecord = res.results[0].properties || {};                  // search envelope
    }
  }
  return { json: { ...row, existingRecord } };
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
const REQUIRED = ["lv_org_type", "lv_produces_content"];
const POLICY = {
  lv_org_type: { stale_after_days: 180 },
  lv_produces_content: { stale_after_days: 180 },
};
const NOW = new Date().toISOString();
return $input.all().map((it) => {
  const row = it.json;
  const gate = decideAction(row.existingRecord || {}, REQUIRED, POLICY, NOW);
  return { json: { ...row, gate, action: gate.action } };
});
"""

ENRICH_BUILD_CO_REQUESTS = r"""// Build Company Provider Requests — companies branch.
// Both contracts confirmed 200 live against racingnsw.com.au:
//   Lusha  GET  /v2/company?domain=            -> { data:{...}, meta:{} }
//   Apollo POST /v1/organizations/enrich?domain= -> { organization:{...} }
return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity_keys || {};
  const enc = encodeURIComponent;
  const q = [];
  const add = (k, v) => { if (v) q.push(enc(k) + "=" + enc(v)); };
  add("domain", id.domain);
  add("companyName", id.companyName);
  const lusha_company_url = "https://api.lusha.com/v2/company?" + q.join("&");
  const apollo_org_url =
    "https://api.apollo.io/v1/organizations/enrich?domain=" + enc(id.domain || "");
  return { json: { ...row, lusha_company_url, apollo_org_url } };
});
"""

ENRICH_NORMALIZE_SCORE_CO = inline(
    "normalizePhone.js", "normalizeEmail.js", "normalizeProviders.js", "scoreEnrichment.js"
) + r"""

// --- n8n wrapper (companies): score best-per-field from the company provider responses ---
// object_type is pinned to "companies" so toCandidates takes its companies branch — the
// one that emits lv_revenue_band / lv_employee_band / lv_country_region_normalized.
function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }
const rows = $('Company Gate').all().filter((it) => it.json.action !== "skip");
const lusha = nodeAll('Lusha Company');
const apollo = nodeAll('Apollo Org');
const zoominfo = nodeAll('ZoomInfo Company');
return rows.map((it, i) => {
  const row = it.json;
  const p = {
    lusha: lusha[i] && lusha[i].json,
    apollo: apollo[i] && apollo[i].json,
    zoominfo: zoominfo[i] && zoominfo[i].json,
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
  return { json: { ...row, providers: p, scored: { best, winners, sourcesByField }, gap_flag } };
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
def _enrich_research_gate_js(cloud=False):
    return inline("taxonomy.generated.js") + r"""

// --- n8n wrapper (companies): Research Trigger Gate ---
""" + _flag_const("ALLOW_WEB_RESEARCH", cloud) + "\n" + _flag_const("MAX_WEB_RESEARCH_PER_RUN", cloud) + r"""
const MAX_PER_RUN = parseInt(String(MAX_WEB_RESEARCH_PER_RUN), 10);

// RT-3: fires when lv_org_type is unresolved/evidence-gated, OR lv_produces_content blank.
function needsResearch(existingRecord) {
  const rec = existingRecord || {};
  const orgType = rec.lv_org_type;
  const orgUnresolved = !orgType || orgType === "" || orgType === "unknown" ||
                        EVIDENCE_GATED_ORG_TYPES.indexOf(orgType) !== -1;
  const pc = rec.lv_produces_content;
  const contentBlank = pc === undefined || pc === null || pc === "";
  return orgUnresolved || contentBlank;
}

const allowOn = String(ALLOW_WEB_RESEARCH).toLowerCase() === "true";
let remaining = MAX_PER_RUN;
return $input.all().map((it) => {
  const row = it.json;
  if (!allowOn) {
    return { json: { ...row, research_needed: false, research_skip_reason: "ALLOW_WEB_RESEARCH=false" } };
  }
  const need = needsResearch(row.existingRecord);
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
# cloud=False (LOCAL-LIVE): ANTHROPIC_SONNET_MODEL/WEB_RESEARCH_MAX_SEARCHES read from
# $vars/$env. cloud=True (CLOUD): both baked build-time literals (AR-4, Criterion 5).
def _enrich_build_research_request_js(cloud=False):
    return inline("taxonomy.generated.js") + r"""

// --- n8n wrapper (companies): Build Research Request ---
function researchSystemPrompt() {
  return [
    "You are an ICP research analyst for a sports-media/broadcast tech vendor.",
    "Research the company across three query intents: identity (<name> <domain> about),",
    "content (<name> watch live | broadcast | streaming), and size (<name> annual report",
    "revenue - only when a revenue band is not already known). First-party domains are",
    "preferred for identity and content; reputable secondary sources are fine for size.",
    "allowed_org_types: " + JSON.stringify(ORG_TYPES) + ".",
    "allowed_content_types: " + JSON.stringify(CONTENT_TYPES) + ".",
    "Prefer \"unknown\"/null over guessing - an absent search result is NOT evidence of",
    "absence. For every field you set in `data`, cite a supporting URL in",
    "`evidence_by_field` keyed by that exact field name (e.g. evidence_by_field.lv_org_type,",
    "evidence_by_field.lv_produces_content). Also return `entity_resolution`:",
    "{ represents: one of group|subsidiary|franchise_outlet|single_entity|unknown,",
    "likely_revenue_band: string|null, notes: string }.",
    "lv_is_hardware_vendor and lv_is_gambling_operator are hard-veto inputs - answer null",
    "unless a cited source directly supports the classification.",
    "Return ONLY one JSON object, no prose, no markdown fences, matching:",
    '{"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,"lv_content_type":[<str>],',
    '"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>},',
    '"evidence_by_field":{"<field>":"<url>"},"entity_resolution":{...},',
    '"matched":<bool>,"confidence":<int 0-100>}',
  ].join(" ");
}

""" + _flag_const("ANTHROPIC_SONNET_MODEL", cloud) + "\n" + _flag_const("WEB_RESEARCH_MAX_SEARCHES", cloud) + r"""

return $input.all().map((it) => {
  const row = it.json;
  if (!row.research_needed) return { json: { ...row, research_request_body: null } };
  const id = row.identity_keys || {};
  const model = ANTHROPIC_SONNET_MODEL;
  const maxUses = parseInt(String(WEB_RESEARCH_MAX_SEARCHES), 10);
  const body = {
    model,
    // ponytail: 2000 truncated live responses (stop_reason=max_tokens) before
    // evidence_by_field was written — extended thinking alone eats ~1000-1300 tokens.
    // 4096 leaves ~45% headroom over the largest observed complete response (2829).
    // Keep in parity with src/web_research.py's max_tokens (Phase 13 D-decision).
    max_tokens: 4096,
    system: researchSystemPrompt(),
    messages: [{ role: "user", content: JSON.stringify({
      task: "company_icp_research",
      company: {
        name: id.companyName || row.company || null,
        domain: id.domain || row.domain || null,
      },
      known_revenue_band: (row.existingRecord && row.existingRecord.lv_revenue_band) || null,
      required_fields: ["lv_org_type", "lv_produces_content", "lv_content_type",
                        "lv_is_hardware_vendor", "lv_is_gambling_operator"],
      return_only_json: true,
    }) }],
    tools: [{ type: "web_search_20250305", name: "web_search", max_uses: maxUses }],
  };
  return { json: { ...row, research_request_body: body } };
});
"""

# Validate Research Output — OC-1..4/TS-1..3/AT-2/ER-1. The whole validation contract lives
# in webResearch.js's researchCandidateFromHttpItem (never throws) — this wrapper just calls
# it per item, so a malformed/errored/empty HTTP response can never fail the node (D5/D6).
ENRICH_VALIDATE_RESEARCH = inline("taxonomy.generated.js", "taxonomy.js", "webResearch.js") + r"""

// --- n8n wrapper (companies): Validate Research Output ---
return $input.all().map((it) => {
  const row = it.json;
  const research_candidate = researchCandidateFromHttpItem(row);
  return { json: { ...row, research_candidate } };
});
"""

# --- Phase 14: judge wiring (companies branch only). Runs on the research-true lane,
# UPSTREAM of Merge Company (D1) — the size-disagreement array/watch-list constant are
# computed INSIDE ENRICH_MERGE_CO below, so a node that runs before it structurally
# cannot reference them (RO-2 is proven by placement, not by comment; tests/test_judge_
# spec.py's test_ro2_judge_gate_cannot_see_size_conflicts asserts both the jsCode
# absence and the graph ancestry).

# Judge Gate — JG-4 (always, D6) + JG-1/RO-1/RO-2 escalation trigger + the D5 kill
# switches (ALLOW_SONNET_ESCALATION, MAX_SONNET_VALIDATIONS_PER_RUN, enforced HERE,
# physically upstream of the HTTP node — Pitfall 4 precedent).
#
# cloud=False (LOCAL-LIVE): both flags read from $vars/$env. cloud=True (CLOUD): both
# baked build-time literals (AR-4, Criterion 5).
def _enrich_judge_gate_js(cloud=False):
    return inline("escalation.generated.js", "scoreEnrichment.js", "judge.js") + r"""

// --- n8n wrapper (companies): Judge Gate ---
// RO-2: size-band disagreement is detected downstream inside Merge Company and is
// deliberately invisible here — this gate runs before that node, so no model call can
// ever be triggered by a size disagreement alone.
""" + _flag_const("ALLOW_SONNET_ESCALATION", cloud) + "\n" + _flag_const("MAX_SONNET_VALIDATIONS_PER_RUN", cloud) + r"""
const allowOn = String(ALLOW_SONNET_ESCALATION).toLowerCase() === "true";
const MAX_PER_RUN = parseInt(String(MAX_SONNET_VALIDATIONS_PER_RUN), 10);
const NOW = new Date().toISOString();

// Phase-15 provenance blob is a JSON string property that may be absent, empty, or
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
  return { ...row, research_candidate: researchCandidate, research_scoring,
           needs_judge: needsJudge, judge_reasons: reasons };
});

// Pass 2: applyCostCap enforces the kill switch AND the per-run budget through the same
// path — 0 when escalation is off (caps every row), MAX_PER_RUN when it is on.
const capped = applyCostCap(gated, allowOn ? MAX_PER_RUN : 0);

// Pass 3: any row that had a trigger fire (judge_reasons non-empty) but ends up here
// with needs_judge false — whether from the kill switch or the cap — runs the D5
// fail-safe, so an unadjudicated hard-veto input never reaches Merge Company. Rows that
// never had a trigger (judge_reasons empty) are already needs_judge:false and untouched.
return capped.map((row) => {
  if ((row.judge_reasons || []).length > 0 && !row.needs_judge) {
    const researchCandidate = applyUnadjudicated(row.research_candidate, row.judge_reasons);
    return { json: { ...row, research_candidate: researchCandidate } };
  }
  return { json: row };
});
"""

# Build Judge Request — JG-2 payload (identity + classification only, no size fields,
# no tools key).
#
# cloud=False (LOCAL-LIVE): ANTHROPIC_SONNET_MODEL read from $vars/$env. cloud=True
# (CLOUD): baked build-time literal (AR-4, Criterion 5).
def _enrich_build_judge_request_js(cloud=False):
    return inline("escalation.generated.js", "judge.js") + r"""

// --- n8n wrapper (companies): Build Judge Request ---
""" + _flag_const("ANTHROPIC_SONNET_MODEL", cloud) + r"""
return $input.all().map((it) => {
  const row = it.json;
  if (!row.needs_judge) return { json: { ...row, judge_request_body: null } };
  const model = ANTHROPIC_SONNET_MODEL;
  const judge_request_body = buildJudgeRequestBody(row, model, 4096);
  return { json: { ...row, judge_request_body } };
});
"""

# Apply Judge Verdict — JG-3 never-throws verdict handling + the promote/demote decision.
ENRICH_APPLY_JUDGE_VERDICT = inline("escalation.generated.js", "judge.js") + r"""

// --- n8n wrapper (companies): Apply Judge Verdict ---
return $input.all().map((it) => {
  const row = it.json;
  const judge_verdict = judgeVerdictFromHttpItem(row);
  const research_candidate = applyJudgeVerdict(row.research_candidate, judge_verdict, row.judge_reasons);

  // TA-8 (D2-safe): when the verdict actually promoted/confirmed a field (judge_flags.
  // adjudicated is only set on that path), carry the VERDICT's own confidence — 0-100,
  // the same scale mergeCompanies' flat confidence already uses — forward for Merge
  // Company to apply as a per-field override. Never the A/R/G/T composite (D2): that
  // scale mismatch would silently stop nearly every research promotion.
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

ENRICH_MERGE_CO = inline("taxonomy.generated.js", "mergeCompanies.js") + r"""

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

return $input.all().map((it) => {
  const row = it.json;
  if (!row.scored) return { json: { ...row, merge: null, conflicts: [] } };  // skip branch
  const best = row.scored.best || {};

  // Distinct normalized values per field, across distinct sources.
  const conflicts = [];
  for (const f of CONFLICT_WATCH) {
    const b = best[f];
    if (!b) continue;
    const others = (b.agreedBy || []).length;
    const sources = row.scored.sourcesByField && row.scored.sourcesByField[f];
    if (sources && sources.length > 1 && others === 0) {
      conflicts.push({ field: f, chosen: b.normalizedValue, chosen_source: b.source,
                       candidates: sources });
    }
  }
  const conflicted = new Set(conflicts.map((c) => c.field));

  const candidate = {};
  for (const f of ["domain", "industry", "lv_revenue_band", "lv_employee_band",
                   "lv_country_region_normalized"]) {
    if (conflicted.has(f)) continue;                  // materially conflicting -> review
    const b = best[f];
    const v = b && b.normalizedValue;                 // NORMALIZED, not raw
    if (v != null && String(v).trim() !== "") candidate[f] = v;
  }
  const merged = mergeCompanies(row.existingRecord || {}, candidate, undefined,
                                { source: "waterfall", confidence: 85 });

  // Phase 13 (D6): fold the Claude web-research candidate in as a SECOND mergeCompanies
  // call — mergeCompanies.js itself stays byte-identical. Research fields (lv_org_type,
  // lv_produces_content, lv_content_type, lv_is_hardware_vendor, lv_is_gambling_operator —
  // widened in Phase 14 so the hard-veto INPUT flags finally reach HubSpot, D1/D2) never
  // collide with the firmographic candidate's keys above, so a shallow merge of each patch
  // (+ concatenated decisions) is safe. By the time this node runs, the Judge Gate chain
  // upstream has already demoted any UNADJUDICATED vendor-flag `true` to `null`
  // (Pitfall 6) — this fold only ever sees an already-safe value.
  let finalMerge = merged;
  const rc = row.research_candidate;
  if (rc && rc.matched) {
    const researchData = {};
    for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
                     "lv_is_hardware_vendor", "lv_is_gambling_operator"]) {
      const v = rc.data && rc.data[f];
      // tri-state null (TS-2 coercion) / blank -> skip, so mergeCompanies' own _isBlank
      // check has nothing to write; an evidenced false is NOT blank and flows through.
      if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
      researchData[f] = v;
    }
    if (Object.keys(researchData).length > 0) {
      // TA-8: confidenceByField carries the judge VERDICT's per-field confidence (only
      // ever set for the ONE field the judge actually adjudicated, Apply Judge Verdict
      // above) — everything else keeps the flat retrieval confidence, exactly as before.
      const researchMerged = mergeCompanies(row.existingRecord || {}, researchData, undefined,
        { source: "claude_web", confidence: rc.confidence || 80, evidence: rc.evidence_by_field || {},
          confidenceByField: row.judge_confidence_by_field || {} });
      // Phase 15: the two mergeCompanies calls handle DISJOINT field sets (waterfall:
      // domain/industry/revenue_band/employee_band/country; claude_web: org_type/
      // produces_content/content_type/hardware/gambling), so a shallow merge of each
      // provenance object + cacheKeys object is safe — no key collision.
      finalMerge = {
        canonicalPatch: { ...merged.canonicalPatch, ...researchMerged.canonicalPatch },
        provenance: { ...merged.provenance, ...researchMerged.provenance },
        cacheKeys: { ...merged.cacheKeys, ...researchMerged.cacheKeys },
        decisions: [...merged.decisions, ...researchMerged.decisions],
      };
    }
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
        "Lusha Enrich", x, y, "GET",
        "={{ $('Build Requests').item.json.lusha_url }}",
        [{"name": "api_key", "value": "=" + _env_secret_expr("LUSHA_API_KEY")}]))
    x += 230
    nodes.append(_live_http(
        "Apollo Match", x, y, "POST", "https://api.apollo.io/v1/people/match",
        [{"name": "X-Api-Key", "value": "=" + _env_secret_expr("APOLLO_API_KEY")},
         {"name": "Content-Type", "value": "application/json"},
         {"name": "Cache-Control", "value": "no-cache"}],
        json_body="={{ JSON.stringify($('Build Requests').item.json.apollo_body) }}"))
    x += 230
    nodes.append(code_node("ZoomInfo Enrich", ENRICH_ZOOMINFO_CACHED, x, y))
    x += 230
    nodes.append(code_node("Normalize + Score", ENRICH_NORMALIZE_SCORE_CLOUD, x, y))
    x += 230
    nodes.append(code_node("Merge Winners", ENRICH_MERGE, x, y))
    x += 230
    nodes.append(code_node("Decide Action", ENRICH_DECIDE_LOCAL, x, y))

    order = ["Manual Trigger", "Emit Live Identities", "Build Identity", "HubSpot Search",
             "Adapt Search", "Enrichment Gate", "Build Requests", "Lusha Enrich", "Apollo Match",
             "ZoomInfo Enrich", "Normalize + Score", "Merge Winners", "Decide Action"]

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
        "Lusha Company", cx, cy, "GET",
        "={{ $('Build Company Requests').item.json.lusha_company_url }}",
        [{"name": "api_key", "value": "=" + _env_secret_expr("LUSHA_API_KEY")}]))
    cx += 230
    nodes.append(_live_http(
        "Apollo Org", cx, cy, "POST",
        "={{ $('Build Company Requests').item.json.apollo_org_url }}",
        [{"name": "X-Api-Key", "value": "=" + _env_secret_expr("APOLLO_API_KEY")},
         {"name": "Content-Type", "value": "application/json"},
         {"name": "Cache-Control", "value": "no-cache"}]))
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

    return {
        "id": "LVenrichmentLive01",
        "name": "LV Enrichment (local LIVE)",
        "nodes": nodes,
        "connections": {**fan(chain(order), chain(co_order)), **research_conns},
        "settings": {},
    }


# ---- CLOUD enrichment workflow ----------------------------------------------

def _http_node(name, url, x, y, auth=None, headers=None, form_body=None, json_body=None):
    """auth: None | 'header' (generic Header Auth credential) | 'basic' (generic Basic Auth).
    headers: list of {name, value} sent as extra HTTP headers (e.g. a dynamic Bearer).
    form_body: list of {name, value} sent as application/x-www-form-urlencoded (OAuth token calls).
    json_body: n8n expression string for the JSON body; when None (and no form_body) the node
               POSTs the bare JSON identity_keys body."""
    params = {"method": "POST", "url": url, "options": {"timeout": 20000}}
    if form_body is not None:
        params.update({"sendBody": True, "contentType": "form-urlencoded",
                       "bodyParameters": {"parameters": form_body}})
    else:
        params.update({"sendBody": True, "specifyBody": "json",
                       "jsonBody": json_body or "={{ JSON.stringify($json.identity_keys) }}"})
    if auth == "header":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"})
    elif auth == "basic":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpBasicAuth"})
    if headers:
        params.update({"sendHeaders": True, "headerParameters": {"parameters": headers}})
    return {
        "parameters": params,
        "id": nid("h"), "name": name,
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [x, y],
        "onError": "continueRegularOutput",
    }


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
def _zoom_split_gate_js(gate_source_node):
    """Secret-free. $input here is the prior HTTP node's response (Apollo/Apollo Org),
    which replaced $json — identity_keys is recovered by paired index from
    `gate_source_node`, same lookup pattern the single-node cached body already used."""
    return inline("zoominfoToken.js") + f"""

// --- n8n wrapper: ZoomInfo token cache gate (CLOUD split-code-node, secret-free) ---
// Never reads client_id/client_secret — only the credential-bound "ZoomInfo Mint" HTTP
// node touches those (Task 2 decision).
const sd = $getWorkflowStaticData("global");
const gateRows = (function () {{ try {{ return $('{gate_source_node}').all(); }} catch (e) {{ return []; }} }})();
const items = $input.all();
return items.map((item, i) => {{
  const row = (gateRows[i] && gateRows[i].json) || item.json || {{}};
  const cached = sd.zoominfo;
  const needs_mint = needsMint(cached, Date.now());
  return {{ json: {{ ...row, zoom_needs_mint: needs_mint,
                   zoom_token: needs_mint ? null : cached.access_token }} }};
}});
"""


def _zoom_split_cache_js(token_gate_name):
    """Secret-free. Parses the Mint HTTP node's token response (never client_id/secret),
    caches it in workflow static data, and re-attaches the original row read back from
    the Token Gate node by paired index (the Mint response has replaced $json)."""
    return inline("zoominfoToken.js") + f"""

// --- n8n wrapper: cache the freshly-minted ZoomInfo token (CLOUD split-code-node) ---
const sd = $getWorkflowStaticData("global");
const gateRows = (function () {{ try {{ return $('{token_gate_name}').all(); }} catch (e) {{ return []; }} }})();
const items = $input.all();
return items.map((item, i) => {{
  const row = (gateRows[i] && gateRows[i].json) || {{}};
  let zoom_token = null;
  try {{
    const parsed = parseTokenResponse(item.json, Date.now());
    sd.zoominfo = parsed;
    zoom_token = parsed.access_token;
  }} catch (e) {{
    zoom_token = null;   // mint response malformed -> Enrich below sees no usable token
  }}
  return {{ json: {{ ...row, zoom_token }} }};
}});
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

const items = $input.all();
const out = [];
for (const item of items) {
  const row = item.json;
  const id = row.identity_keys || {};
  const person = toMatchPersonInput(id);
  if (!hasZoomKey(person)) { out.push({ json: { skipped: "no zoominfo match key" } }); continue; }
  const token = row.zoom_token;
  if (!token) { out.push({ json: { error: "no zoominfo token available (mint failed or missing)" } }); continue; }
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
    if (isAuthError(e.statusCode || e.httpCode || (e.response && e.response.statusCode))) {
      delete sd.zoominfo;  // token rejected -> clear cache so the NEXT run re-mints
    }
    res = { error: String((e && e.message) || e) };
  }
  out.push({ json: res });
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

const items = $input.all();
const out = [];
for (const item of items) {
  const row = item.json;
  const id = row.identity_keys || {};
  const co = toMatchCompanyInput(id);
  if (!hasZoomCoKey(co)) { out.push({ json: { skipped: "no zoominfo company match key" } }); continue; }
  const token = row.zoom_token;
  if (!token) { out.push({ json: { error: "no zoominfo token available (mint failed or missing)" } }); continue; }
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
    if (isAuthError(e.statusCode || e.httpCode || (e.response && e.response.statusCode))) {
      delete sd.zoominfo;
    }
    res = { error: String((e && e.message) || e) };
  }
  out.push({ json: res });
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


# NOTE (Phase 13/16): this Cloud webhook template's companies branch is ported by Task 5
# (Phase 16). Until then, and unlike build_enrichment_local_live(), the Claude web-research
# nodes (Research Trigger Gate / Build Research Request / Claude Web Research / Validate
# Research Output) do NOT land here.
def build_enrichment_cloud():
    nodes = []
    y = 300
    x = 220

    webhook = {
        "parameters": {"httpMethod": "POST", "path": "hubspot/enrichment/event",
                       "responseMode": "lastNode", "options": {}},
        "id": nid("w"), "name": "Webhook Trigger",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [x, y],
    }
    nodes.append(webhook)

    x += 220
    nodes.append(code_node("Build Identity", ENRICH_BUILD_IDENTITY, x, y))

    x += 220
    hs_search = {
        "parameters": {"resource": "contact", "operation": "search",
                       "filterGroupsUi": {"filterGroupsValues": []}, "additionalFields": {}},
        "id": nid("hs"), "name": "HubSpot Search",
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x, y],
        "onError": "continueRegularOutput",
    }
    nodes.append(hs_search)

    x += 220
    nodes.append(code_node("Adapt Search", ENRICH_ADAPT_SEARCH, x, y))
    x += 220
    nodes.append(code_node("Enrichment Gate", ENRICH_GATE, x, y))

    # Switch: create / enrich / skip
    x += 220
    nodes.append(_route_action_switch("Route Action", x, y))

    # Provider waterfall (create+enrich share it). Apollo phone is async (webhook) in prod.
    # Auth differs per provider: Lusha + Apollo = single static header key (generic Header
    # Auth credential); ZoomInfo = autonomous OAuth2 — the ZoomInfo Enrich Code node mints
    # and caches its own short-lived Bearer (no static token, no separate Auth node).
    px = x + 220
    lusha = _http_node("Lusha Enrich", "https://api.lusha.com/v2/person", px, y - 80,
                       auth="header")  # credential header, e.g. api_key: <LUSHA_API_KEY>
    nodes.append(lusha)
    # reveal_personal_emails=true forces Apollo to return the contactable email (a bare
    # people/match returns identity only). Phone is async: reveal_phone_number needs a
    # webhook_url and arrives via callback — wired separately, not in this synchronous node.
    apollo = _http_node("Apollo Match", "https://api.apollo.io/v1/people/match", px + 220, y - 80,
                        auth="header",  # credential header, e.g. X-Api-Key: <APOLLO_API_KEY>
                        json_body=("={{ JSON.stringify({ "
                                   "email: $json.identity_keys.email, "
                                   "domain: $json.identity_keys.domain, "
                                   "first_name: $json.identity_keys.firstName, "
                                   "last_name: $json.identity_keys.lastName, "
                                   "organization_name: $json.identity_keys.companyName, "
                                   "reveal_personal_emails: true }) }}"))
    nodes.append(apollo)
    # ZoomInfo: split-code-node (Task 2 decision). The credential-bound "ZoomInfo Mint"
    # HTTP node is the ONLY place client_id/client_secret are read; the Token Gate/Cache
    # Token/Enrich Code nodes are secret-free, consuming only the short-lived bearer.
    zoom_nodes, zoom_conns, zoom_entry, zoom_exit = _zoom_split_contacts_subgraph(
        "Enrichment Gate", px + 440, y - 80)
    nodes.extend(zoom_nodes)

    sx = px + 660 + 440
    nodes.append(code_node("Normalize + Score", ENRICH_NORMALIZE_SCORE_CLOUD, sx, y - 80))
    sx += 220
    nodes.append(code_node("Merge Winners", ENRICH_MERGE, sx, y - 80))
    sx += 220
    set_dq = {
        "parameters": {"assignments": {"assignments": [
            {"id": nid("a"), "name": "data_quality", "value": "scored_waterfall", "type": "string"},
            {"id": nid("a"), "name": "gap_flag", "value": "={{ $json.gap_flag }}", "type": "boolean"},
        ]}, "options": {}},
        "id": nid("g"), "name": "Set Data Quality + Gap Flag",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [sx, y - 80],
    }
    nodes.append(set_dq)
    sx += 220
    nodes.append(code_node("Decide Action", ENRICH_DECIDE_CLOUD, sx, y - 80))

    # IF create -> HubSpot Create ; else IF enrich -> HubSpot Update (both GATED writes).
    sx += 220
    if_create = _if_node("IF Create", "create", sx, y - 80)
    nodes.append(if_create)
    hs_create = {
        "parameters": {"resource": "contact", "operation": "create",
                       "email": "={{ $json.properties.email }}", "additionalFields": {}},
        "id": nid("hc"), "name": "HubSpot Create",
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [sx + 220, y - 200]}
    nodes.append(hs_create)
    if_enrich = _if_node("IF Enrich", "enrich", sx + 220, y - 20)
    nodes.append(if_enrich)
    hs_update = {
        "parameters": {"resource": "contact", "operation": "update",
                       "contactId": "={{ $json.contact_id }}", "updateFields": {}},
        "id": nid("hu"), "name": "HubSpot Update",
        "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [sx + 440, y - 20]}
    nodes.append(hs_update)

    # skip branch -> NoOp Set (do nothing)
    set_skip = {
        "parameters": {"assignments": {"assignments": [
            {"id": nid("a"), "name": "action", "value": "skip", "type": "string"}
        ]}, "options": {}},
        "id": nid("r"), "name": "Skip (NoOp)",
        "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [px, y + 160]}
    nodes.append(set_skip)

    conns = chain(["Webhook Trigger", "Build Identity", "HubSpot Search",
                   "Adapt Search", "Enrichment Gate", "Route Action"])
    # Switch outputs: 0=create, 1=enrich, 2=skip. create+enrich -> shared waterfall.
    conns["Route Action"] = {"main": [
        [{"node": "Lusha Enrich", "type": "main", "index": 0}],   # create
        [{"node": "Lusha Enrich", "type": "main", "index": 0}],   # enrich
        [{"node": "Skip (NoOp)", "type": "main", "index": 0}],    # skip
    ]}
    # Lusha -> Apollo -> ZoomInfo split subgraph (credential-bound Mint + secret-free
    # Gate/Cache/Enrich, Task 2 decision) -> Normalize...
    conns.update(chain(["Lusha Enrich", "Apollo Match"]))
    conns["Apollo Match"] = {"main": [[{"node": zoom_entry, "type": "main", "index": 0}]]}
    conns.update(zoom_conns)
    conns.update(chain([zoom_exit, "Normalize + Score", "Merge Winners",
                        "Set Data Quality + Gap Flag", "Decide Action", "IF Create"]))
    conns["IF Create"] = {"main": [
        [{"node": "HubSpot Create", "type": "main", "index": 0}],  # true
        [{"node": "IF Enrich", "type": "main", "index": 0}],       # false
    ]}
    conns["IF Enrich"] = {"main": [
        [{"node": "HubSpot Update", "type": "main", "index": 0}],  # true
        [],                                                        # false -> end
    ]}

    notes = [
        {"content": (
            "## LV Enrichment — CLOUD template\n"
            "Run `python scripts/provision_n8n_credentials.py` then "
            "`python scripts/deploy_n8n_workflows.py` (both env-gated, dry-run by "
            "default — see their docstrings) to create the 5 credentials and deploy "
            "this workflow with every node bound: **HubSpot** (search/create/update, "
            "`hubspotAppToken`); **Lusha** + **Apollo** = generic Header Auth (one "
            "static key each, e.g. `api_key` / `X-Api-Key`); **ZoomInfo** = a "
            "credential-bound Mint HTTP node (generic Basic Auth holding "
            "client_id:client_secret) — see the ZoomInfo note. Every one of the 6 "
            "config flags (research/judge cost caps + model knobs) is a baked "
            "build-time constant, not a runtime environment lookup — none survives "
            "in this JSON (Criterion 5).\n\n"
            "**Flow:** Webhook -> Build Identity -> HubSpot Search -> Gate "
            "(create/enrich/skip) -> Switch. create+enrich share the scored "
            "waterfall; skip does nothing. Writes are GATED."
        ), "x": 220, "y": 480, "h": 320, "w": 460},
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
    ]
    for n in notes:
        nodes.append({
            "parameters": {"content": n["content"], "height": n["h"], "width": n["w"]},
            "id": nid("s"), "name": "Sticky Note",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "position": [n["x"], n["y"]],
        })

    return {
        "id": "LVenrichmentCloud01",
        "name": "LV Enrichment (Cloud template)",
        "nodes": nodes,
        "connections": conns,
        "settings": {},
    }


# ---- write ------------------------------------------------------------------

def main():
    out_local = ROOT / "n8n" / "wf_contact_ingest_local.json"
    out_cloud = ROOT / "n8n" / "wf_contact_ingest_cloud.json"
    out_local.write_text(json.dumps(build_local(), indent=2) + "\n")
    _idc[0] = 0
    out_cloud.write_text(json.dumps(build_cloud(), indent=2) + "\n")
    print(f"wrote {out_local.relative_to(ROOT)}")
    print(f"wrote {out_cloud.relative_to(ROOT)}")

    _idc[0] = 0
    er_local = ROOT / "n8n" / "wf_enrichment_local.json"
    er_local.write_text(json.dumps(build_enrichment_local(), indent=2) + "\n")
    _idc[0] = 0
    er_cloud = ROOT / "n8n" / "wf_enrichment_cloud.json"
    er_cloud.write_text(json.dumps(build_enrichment_cloud(), indent=2) + "\n")
    _idc[0] = 0
    er_live = ROOT / "n8n" / "wf_enrichment_local_live.json"
    er_live.write_text(json.dumps(build_enrichment_local_live(), indent=2) + "\n")
    print(f"wrote {er_local.relative_to(ROOT)}")
    print(f"wrote {er_cloud.relative_to(ROOT)}")
    print(f"wrote {er_live.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
