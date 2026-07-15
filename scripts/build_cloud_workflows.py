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

# ---- module inliner ---------------------------------------------------------

_REQUIRE_RE = re.compile(r"^\s*const\s*\{[^}]*\}\s*=\s*require\(")
_EXPORTS_RE = re.compile(r"^\s*module\.exports")


def strip_module(name: str) -> str:
    """Load a Wave-A module, drop require() lines and everything from the first
    `module.exports` onward (exports are always the module's trailing statement,
    and may span multiple lines — truncating avoids orphaning the export body)."""
    src = (CODE / name).read_text()
    kept = []
    for ln in src.splitlines():
        if _EXPORTS_RE.match(ln):
            break
        if _REQUIRE_RE.match(ln):
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
return $input.all().map((it) => {
  const row = it.json;
  const candidate = {};
  for (const f of ["email", "firstname", "lastname", "jobtitle", "linkedin_url", "company"]) {
    if (row[f] != null && String(row[f]).trim() !== "") candidate[f] = row[f];
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
return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity || {};
  const outcome = id.outcome || "rejected";
  const allow_create = row.allow_create === true;
  const patch = row.merge
    ? { ...row.merge.canonicalPatch, ...row.merge.stagingPatch, ...row.merge.metadataPatch }
    : {};
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
return $input.all().map((it) => {
  const row = it.json;
  const id = row.identity || {};
  const outcome = id.outcome || "rejected";
  const allow_create = row.allow_create === true;
  const properties = row.merge
    ? { ...row.merge.canonicalPatch, ...row.merge.stagingPatch, ...row.merge.metadataPatch }
    : {};
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
return $input.all().map((it) => {
  const row = it.json;
  if (!row.scored) return { json: { ...row, merge: null } };  // skip branch
  const winners = row.scored.winners || {};
  const candidate = {};
  for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority", "linkedin_url"]) {
    if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
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
    jobtitle_verified_at: "2025-01-01T00:00:00Z",
    mobilephone: ""
  },
  "sam.fresh@examplemedia.example": {
    email: "sam.fresh@examplemedia.example",
    jobtitle: "Producer",
    jobtitle_verified_at: "2026-07-01T00:00:00Z",
    mobilephone: "+61412000000",
    mobilephone_verified_at: "2026-07-01T00:00:00Z"
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
  const patch = row.merge
    ? { ...row.merge.canonicalPatch, ...row.merge.stagingPatch, ...row.merge.metadataPatch }
    : {};
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
return $input.all().map((it) => {
  const row = it.json;
  const action = row.action;
  const properties = row.merge
    ? { ...row.merge.canonicalPatch, ...row.merge.stagingPatch, ...row.merge.metadataPatch }
    : {};
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
ENRICH_ZOOMINFO_CACHED = inline("zoominfoToken.js") + r"""
// n8n Code node: cached ZoomInfo bearer (autonomous). Reads a cross-run token cache
// from workflow static data, mints only when missing/near-expiry, enriches with the
// Bearer, and on a 401 clears the cache, re-mints ONCE, and retries. Secrets come from
// n8n Variables ($vars.ZOOMINFO_CLIENT_ID / $vars.ZOOMINFO_CLIENT_SECRET) so no static
// token is ever stored. (Self-hosted may use $env; or bind a Basic Auth credential to a
// dedicated mint HTTP node instead.)
const TOKEN_URL = "https://api.zoominfo.com/gtm/oauth/v1/token";
const ENRICH_URL = "https://api.zoominfo.com/gtm/data/v1/contacts/enrich";
const sd = $getWorkflowStaticData("global");

async function mint() {
  const cid = $vars.ZOOMINFO_CLIENT_ID;
  const csec = $vars.ZOOMINFO_CLIENT_SECRET;
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
  return await this.helpers.httpRequest({
    method: "POST", url: ENRICH_URL,
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

// GTM enrich contract: { matchPersonInput: [ {emailAddress, ...} ], outputFields: [...] }.
// The input KEY is `emailAddress` (not `email`); `domain`/`linkedin_url` are NOT valid
// matchPersonInput fields — sending the bare identity_keys 400s (PFAPI0005, /matchPersonInput).
// outputFields must name every field the normalizer reads (see normalizeProviders.zoominfoCandidates).
const ZOOM_OUTPUT_FIELDS = [
  "id", "firstName", "lastName", "email", "phone", "mobilePhone", "jobTitle",
  "managementLevel", "contactAccuracyScore", "matchStatus", "validDate", "lastUpdatedDate",
];
function toMatchPersonInput(id) {
  const m = {};
  if (id && id.email) m.emailAddress = id.email;   // rename email -> emailAddress
  if (id && id.companyName) m.companyName = id.companyName;
  return m;
}

const out = [];
for (const item of $input.all()) {
  const id = item.json.identity_keys || {};
  const person = toMatchPersonInput(id);
  // No usable match key -> skip the call (empty matchPersonInput is itself a 400).
  const payload = person.emailAddress
    ? { matchPersonInput: [person], outputFields: ZOOM_OUTPUT_FIELDS }
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
    switch = {
        "parameters": {"mode": "rules", "rules": {"values": [
            {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict"},
                            "combinator": "and", "conditions": [{
                                "id": nid("i"), "leftValue": "={{ $json.action }}",
                                "rightValue": "create",
                                "operator": {"type": "string", "operation": "equals"}}]},
             "outputKey": "create"},
            {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict"},
                            "combinator": "and", "conditions": [{
                                "id": nid("i"), "leftValue": "={{ $json.action }}",
                                "rightValue": "enrich",
                                "operator": {"type": "string", "operation": "equals"}}]},
             "outputKey": "enrich"},
            {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict"},
                            "combinator": "and", "conditions": [{
                                "id": nid("i"), "leftValue": "={{ $json.action }}",
                                "rightValue": "skip",
                                "operator": {"type": "string", "operation": "equals"}}]},
             "outputKey": "skip"},
        ]}, "options": {}},
        "id": nid("sw"), "name": "Route Action",
        "type": "n8n-nodes-base.switch", "typeVersion": 3, "position": [x, y],
    }
    nodes.append(switch)

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
                        json_body="={{ JSON.stringify({ ...$json.identity_keys, reveal_personal_emails: true }) }}")
    nodes.append(apollo)
    # ZoomInfo: autonomous cached-token enrich. The Code node caches the bearer in workflow
    # static data, re-mints only when missing/near-expiry, and re-mints once + retries on 401.
    zoom = code_node("ZoomInfo Enrich", ENRICH_ZOOMINFO_CACHED, px + 440, y - 80)
    nodes.append(zoom)

    sx = px + 660
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
    # Lusha -> Apollo -> ZoomInfo Enrich (autonomous cached token) -> Normalize...
    conns.update(chain(["Lusha Enrich", "Apollo Match", "ZoomInfo Enrich",
                        "Normalize + Score", "Merge Winners",
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
            "Import to n8n Cloud, then add **credentials**: HubSpot (search/create/"
            "update); **Lusha** + **Apollo** = generic Header Auth (single static key, "
            "e.g. `api_key` / `X-Api-Key`); **ZoomInfo** = autonomous — set "
            "`ZOOMINFO_CLIENT_ID`/`ZOOMINFO_CLIENT_SECRET` in n8n Variables ($vars); "
            "the ZoomInfo Enrich node mints + caches its own token — see the ZoomInfo note.\n\n"
            "**Flow:** Webhook -> Build Identity -> HubSpot Search -> Gate "
            "(create/enrich/skip) -> Switch. create+enrich share the scored "
            "waterfall; skip does nothing. Writes are GATED."
        ), "x": 220, "y": 480, "h": 300, "w": 460},
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
            "### ZoomInfo = autonomous OAuth2 (cached) — VERIFIED\n"
            "The **ZoomInfo Enrich** Code node mints its own Okta token: caches the "
            "bearer in workflow **static data**, re-mints when missing/near-expiry, "
            "and on a **401** clears the cache, re-mints once, retries.\n"
            "Confirmed working: `POST api.zoominfo.com/gtm/oauth/v1/token`, Basic "
            "auth (client_id:client_secret), body `grant_type=client_credentials` "
            "ONLY — **do NOT send a `scope`** (any scope => 400 invalid_scope). "
            "Token ~24h; GTM API (`gtm/data/v1/...`) accepts it.\n"
            "Creds = long-lived `client_id`/`client_secret` in **n8n Variables** "
            "($vars) — never a stored token. Get them from the **ZoomInfo DevPortal** "
            "(create app → click the app link to reveal Client ID + Client Secret; "
            "enable the **client-credentials** grant). Rotate the secret ~quarterly; "
            "everything else is unattended."
        ), "x": 1140, "y": 60, "h": 300, "w": 420},
        {"content": (
            "### Dependencies (awaited)\n"
            "**`lv_*` HubSpot properties** are not yet created — the merge writes "
            "them by name; create them in the portal first. **Provider keys** are "
            "empty — POC mocks the responses (see the local workflow). Swap in real "
            "keys + properties to go live.\n\n"
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
    print(f"wrote {er_local.relative_to(ROOT)}")
    print(f"wrote {er_cloud.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
