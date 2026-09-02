# Phase 36: Enrichment Propose Mode & Match Lane - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** 11 (2 new, 3 modified-source, 6 test files new/extended)
**Analogs found:** 11 / 11

**Critical constraint for every entry below:** `n8n/*.json` is GENERATED. The analog to copy is
always the BUILDER-SIDE pattern in `scripts/build_cloud_workflows.py` (a Python string constant
building JS, or a `_hs_http_search_node`/`_http_node` call), never the emitted JSON. Verify by
rebuilding and diffing, never by hand-editing `n8n/*.json`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `n8n/code/matchProposal.js` | utility (pure module) | transform | `n8n/code/listExpansion.js` | exact (refusal-shape + pure-module precedent) |
| `n8n/code/providerSelection.js` (`parseWebhookBody`) | utility (pure module) | transform | itself — extend `providers` extraction pattern in the same function | exact |
| `scripts/build_cloud_workflows.py` — `ENRICH_BUILD_IDENTITY` (lane stamp) | builder constant → Code node | transform | itself, same constant, extend the returned object | exact |
| `scripts/build_cloud_workflows.py` — `ENRICH_ADAPT_SEARCH` / `ENRICH_ADAPT_FETCH_BY_ID_CONTACT` (lane filter) | builder constant → Code node | request-response (adapts HTTP node output) | itself, same constants | exact |
| `scripts/build_cloud_workflows.py` — `ENRICH_PARSE_EVENT_CLOUD` (mode + size refusal) | builder constant → Code node | request-response | `ENRICH_EXPAND_LIST_TO_EVENTS` (refusal-as-terminating-item shape) | role-match |
| `scripts/build_cloud_workflows.py` — `ENRICH_DECIDE_CLOUD` / `ENRICH_DECIDE_CO_CLOUD` (`action:"proposed"`) | builder constant → Code node | request-response | itself, same constants (already gate on `action` string) | exact |
| `scripts/build_cloud_workflows.py` — `ENRICH_GATE` (unmatchable → skip) | builder constant → Code node | transform | itself, same constant (already has a `lookup_failed` override pattern) | exact |
| `scripts/build_cloud_workflows.py` — new `HubSpot Name Search` node | builder helper call → httpRequest node | request-response (HubSpot CRM v3 search) | `_hs_http_search_node("HubSpot Search", "contact", ...)` at build_cloud_workflows.py:3720-3725 | exact |
| `scripts/build_cloud_workflows.py` — `Skip (NoOp)` / `Unsupported Object Type` Set→Code | builder constant → Code node | transform (row spread) | `ENRICH_ADAPT_SEARCH`'s `{ json: { ...row, ... } }` spread idiom; any `$input.all().map` wrapper in this file | role-match |
| `scripts/build_cloud_workflows.py` — Lusha widening + comment rewrite | builder constant → httpRequest node body expr | request-response | itself, `lusha` node build (`_http_node("Lusha Enrich", ...)`) + `lushaContactBody()` in `n8n/code/lushaRequest.js:79-98` | exact |
| `scripts/build_cloud_workflows.py` — ingest `HubSpot Search by Email` sentinel | builder constant (contact-ingest region, ~line 640-656) | request-response | itself, same filter-value expression | exact |
| `scripts/deploy_n8n_workflows.py` — `NODE_CREDENTIAL_MAP` entry | config | — | any existing HubSpot search entry, e.g. `"HubSpot Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"}` | exact |
| `tests/n8n/matchProposal.test.mjs` | test (Node) | — | `tests/n8n/listExpansion.test.mjs` | exact |
| `tests/n8n/providerSelection.test.mjs` | test (Node) | — | itself, extend | exact |
| `tests/n8n/lushaRequestContract.test.mjs` | test (Node) | — | itself, extend the input matrix | exact |
| `tests/test_row_carry.py` | test (pytest, structural) | — | itself, edit `ROW_REPLACING_BY_DESIGN` dict | exact |
| `tests/test_fetch_by_id_topology.py` | test (pytest, structural) | — | itself, amend one assertion | exact |
| `tests/test_ingest_search_contract.py` | test (pytest, structural) | — | itself, extend | exact |
| `tests/test_cloud_write_path.py` | test (pytest, structural) | — | itself, extend | exact |

## Pattern Assignments

### `n8n/code/matchProposal.js` (new, pure module)

**Analog:** `n8n/code/listExpansion.js` (whole file, 213 lines — read in full this session)

**Module shape** — CommonJS, no `require()` of siblings (builder's `strip_module()` strips any
`require()` line and everything from `module.exports` onward before inlining; a cross-module
import would silently vanish in the Code node), plain function declarations, single
`module.exports` at the bottom:
```js
// n8n/code/listExpansion.js:1-14 (header/contract-comment convention)
// n8n/code/listExpansion.js — pure-JS HubSpot-list -> enrichment-events expansion.
//
// Phase 25 Plan 03 (INGEST-04, D-01/D-02/D-15). ...
// Pure, deterministic, no n8n globals — mirrors providerSelection.js, inlined into the
// Code node by the builder's inline() (Code nodes cannot require() siblings).
```

**Refusal-shape precedent** (`listExpansion.js:81-83`) — `matchProposal.js` doesn't need a refusal
per se, but `summarizeMatch()` should follow the same "plain data object, one field per axis,
never throw" discipline:
```js
function refuse(reason) {
  return { events: [], refused: true, reason };
}
```

**Value re-verification is the load-bearing pattern to copy from this file's DISCIPLINE, not its
code**: `listExpansion.js` never trusts an upstream shape without checking it (`isPlainObject`,
`isNumber` guards throughout, `memberIds()` fails closed on any unusable row). `mediumCandidates()`
must do the equivalent: re-check `lastname` (case-insensitive) and `company` (token overlap) by
VALUE against the row, never trust that `CONTAINS_TOKEN` already filtered correctly (CONTEXT.md
§7 step 1, the BUG 22b lesson).

**Export convention** (`listExpansion.js:213`):
```js
module.exports = { expandListToEvents, normalizeObjectType, objectTypeId, VIEW_REFUSAL };
```
For `matchProposal.js`: `module.exports = { laneOf, mediumCandidates, summarizeMatch };`

**Builder inline call** — mirrors how `listExpansion.js` is inlined (grep `inline("listExpansion.js"` in
`build_cloud_workflows.py`); `matchProposal.js` will be inlined alongside `enrichmentGate.js`-style
constants wherever `ENRICH_GATE`/`ENRICH_BUILD_IDENTITY`/the new match-lane adapter needs it:
```python
inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js")  # ENRICH_GATE, build_cloud_workflows.py:938
```
i.e. `inline(*modules)` takes N module filenames and concatenates their stripped bodies in call
order — order matters only if one module's top-level code depends on another's being defined first
(none of the existing modules do; keep `matchProposal.js` order-independent too).

---

### `n8n/code/providerSelection.js` — `parseWebhookBody()` mode extraction

**Analog:** itself, `n8n/code/providerSelection.js:33-39` — the exact same function already
extracts one envelope-level field (`providers`) with an identical extraction idiom; `mode` is a
second, structurally identical field:
```js
function parseWebhookBody(body) {
  const events = Array.isArray(body)
    ? body
    : (body && Array.isArray(body.events) ? body.events : [body]);
  const providers = (body && !Array.isArray(body)) ? body.providers : undefined;
  return { events, providers };
}
```
Extend to: `const mode = (body && !Array.isArray(body)) ? body.mode : undefined; return { events, providers, mode };`
Per RESEARCH.md §D.1/Pitfall 2: extend this function (option 1), not `ENRICH_PARSE_EVENT_CLOUD`'s
wrapper directly — `providers` is the one other envelope-level field this webhook already
supports, and it's read here, not in the wrapper. Keeps the two fields consistent for future readers.

**Doc-comment convention to extend** (`providerSelection.js:8-17`):
```js
// parseWebhookBody(body)
//   -> { events, providers }
//   Explicit payload contract (reviews A4): ...
```
Add a `mode` line to this contract comment in the same style.

**Test analog:** `tests/n8n/providerSelection.test.mjs` (existing file, extend — not shown here but
confirmed to exist by RESEARCH.md §B.3/Wave 0 list). New case: envelope `{mode:"propose", events:[...]}`
→ `parseWebhookBody(body).mode === "propose"`; absent `mode` → `undefined`.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_BUILD_IDENTITY` (lane stamp)

**Analog:** itself, `scripts/build_cloud_workflows.py:914-934`. Copy the exact wrapper idiom —
`inline(...)` + raw Python string with an n8n-wrapper comment, `$input.all().map` spreading `...row`:
```python
ENRICH_BUILD_IDENTITY = inline("normalizeEmail.js") + r"""

// --- n8n wrapper: normalise the incoming identity into HubSpot search keys ---
return $input.all().map((it) => {
  const row = it.json;
  const email = normalizeEmailBasic(row.email);
  return { json: { ...row,
    object_type: row.object_type || "contacts",
    identity_keys: { ... },
  }};
});
"""
```
Add `lane: laneOf({ email, identity_keys })` (or equivalent call into the new
`matchProposal.js`'s `laneOf`) inside the returned object, alongside `identity_keys`. Requires
adding `matchProposal.js` to this constant's `inline(...)` call.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_ADAPT_SEARCH` / `ENRICH_ADAPT_FETCH_BY_ID_CONTACT` (lane filter)

**Analog:** itself, `scripts/build_cloud_workflows.py:1101-1127` (full text read this session):
```python
ENRICH_ADAPT_SEARCH = r"""// Adapt Search -> existingRecord — CLOUD variant.
// Maps the real HubSpot search node output (per row, same order) into the
// existingRecord shape enrichmentGate expects. 0 results => {} => CREATE.
const rows = $('Build Identity').all();
const search = $('HubSpot Search').all();
return rows.map((it, i) => {
  const row = it.json;
  const item = search[i];
  ...
});
"""
```
Finding A's fix: filter `rows` to `it.json.lane === "email"` (or the search lane's name) **before**
the `.map((it, i) => ...)` index-alignment, so `search[i]` still lines up one-to-one with the
filtered subset, not the full mixed-lane row set. `ENRICH_ADAPT_FETCH_BY_ID_CONTACT`
(`scripts/build_cloud_workflows.py:3557-3573`) needs the identical filter against its own lane and
its own HTTP node (`$('HubSpot Fetch By Id').all()`). Both currently open with the unfiltered
`const rows = $('Build Identity').all();` line — that line is the one to change in both constants,
same fix shape, two call sites.

**New third adapter, `Adapt Name Search`** (§7 step 3) follows this exact same three-line opening
+ `.map((it, i) => ...)` shape, filtered to the name-search lane, reading `$('HubSpot Name Search').all()`.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_PARSE_EVENT_CLOUD` (mode + size refusal)

**Analog (mode threading):** itself, `scripts/build_cloud_workflows.py:3298-3336` — full text read
this session. The `parsed = parseWebhookBody(body)` call already exists; once `parseWebhookBody`
returns `mode` (see above), thread it the same way `providers` already is:
```python
ENRICH_PARSE_EVENT_CLOUD = (
    inline("providerSelection.js")
    + r"""
...
const parsed = parseWebhookBody(body);
return parsed.events.map((event) => {
  const providersRaw = parsed.providers ?? event.providers;
  ...
  return { json: {
    event_id: `...`,
    ...
    provider_enabled,
    providers_requested,
    ...event,
  }};
});
"""
)
```
Add `mode: parsed.mode ?? event.mode ?? null,` to the returned object, mirroring the
`providersRaw = parsed.providers ?? event.providers` fallback idiom exactly.

**Analog (oversize refusal-as-terminating-item shape):** `ENRICH_EXPAND_LIST_TO_EVENTS`
(`scripts/build_cloud_workflows.py:3394-3419`, cited in RESEARCH.md §A9) — the shape to mirror for
"refuse whole, never truncate, terminate as a 200 not a thrown error":
```python
# from ENRICH_EXPAND_LIST_TO_EVENTS's wrapper (paraphrased from RESEARCH.md §A9 citation):
if (result.refused) {
  return [{ json: { outcome: "refused", reason: result.reason, events: [] } }];
}
```
and the downstream gate pattern: `Array.isArray($json.events) && $json.events.length > 0`. Apply
the same terminating-item shape for `events.length > ENRICH_MAX_LIST_RECORDS` — per RESEARCH.md
§F Open Question 2, read `ENRICH_PARSE_EVENT_CLOUD`'s full wrapper immediately before implementing
and decide in-node vs. separate-node; the in-node check is likely safe here (unlike the list-lane's
missing-events-array masking risk) but confirm before writing.

**Ceiling constant to reuse:** `ENRICH_MAX_LIST_RECORDS = 2` at `scripts/build_cloud_workflows.py:3361`
— declared exactly once; read it, do not redeclare a second ceiling.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_DECIDE_CLOUD` / `ENRICH_DECIDE_CO_CLOUD` (`action:"proposed"`)

**Analog:** itself, `scripts/build_cloud_workflows.py:1223-1281` (contacts) and `2499-2561`
(companies) — not fully re-read this session (already large, RESEARCH.md pinned the exact lines),
but the pattern is confirmed by RESEARCH.md §D.2/§B.4: both constants already gate on an `action`
string (`"create"`/`"enrich"`/`"skip"`) computed upstream, and `_writeSafetyAllows` is called
**after** that gate, not before. Add a check: if `row.mode` is present and not `"write"`
(`return_only = mode != null && String(mode).toLowerCase() !== "write"`, exact predicate from
CONTEXT.md §6), set `action = "proposed"` **before** any `_writeSafetyAllows` call and echo
`row_id`/`mode`/`match` into the returned object. `"proposed"` deliberately matches neither `IF
Create` nor `IF Enrich`'s true branch, so it exits via `IF Enrich`'s existing FALSE lane into
`Build Response` — zero new inbound branches, per RESEARCH.md §B.4.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_GATE` (unmatchable → skip)

**Analog:** itself, `scripts/build_cloud_workflows.py:938-957` (full text read this session):
```python
ENRICH_GATE = inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js") + r"""

// --- n8n wrapper: decideAction(existingRecord) -> create | enrich | skip ---
const REQUIRED = ["email", "jobtitle", "mobilephone"];
const POLICY = { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } };
const NOW = new Date().toISOString();
return $input.all().map((it) => {
  const row = it.json;
  const gate = decideAction(row.existingRecord || {}, REQUIRED, POLICY, NOW);
  let action = gate.action;
  // Fail-closed (Task 6, review #8): a HubSpot lookup FAILURE ... is
  // tagged lookup_failed=true by the Adapt step and MUST NOT be treated as confirmed-
  // absent ...
  if (row.lookup_failed === true && action === "create") action = "skip";
  return { json: { ...row, gate, action } };
});
"""
```
This is the EXACT override idiom to copy for step 8's addition — a second `if` guard in the same
wrapper, same style, same "override lives in the wrapper, never in the frozen module" discipline:
```js
if (!row.identity_keys.email && !row.identity_keys.linkedin_url &&
    !(row.identity_keys.lastName && row.identity_keys.companyName)) {
  action = "skip";
}
```
Place it beside the existing `lookup_failed` override, same function, same comment-block density.

---

### `scripts/build_cloud_workflows.py` — new `HubSpot Name Search` node (match lane)

**Analog:** the existing `HubSpot Search` node build call, `scripts/build_cloud_workflows.py:3720-3725`
(exact text from RESEARCH.md §B.2):
```python
hs_search = _hs_http_search_node(
    "HubSpot Search", "contact", x, y,
    filter_groups=[[{"propertyName": "email", "operator": "EQ",
                      "value": "={{ $json.identity_keys.email }}"}]],
    properties_csv=ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
)
```
New call, per RESEARCH.md §B.2's already-derived signature (AND within one group, `CONTAINS_TOKEN`
needs zero builder special-casing — `_hs_search_json_body_expr` `json.dumps()`s the operator string
literally):
```python
hs_name_search = _hs_http_search_node(
    "HubSpot Name Search", "contact", x, y,
    filter_groups=[[
        {"propertyName": "lastname", "operator": "EQ",
         "value": "={{ $json.identity_keys.lastName }}"},
        {"propertyName": "company", "operator": "CONTAINS_TOKEN",
         "value": "={{ $json.identity_keys.companyName }}"},
    ]],
    properties_csv=ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
)
```
`_hs_http_search_node` signature and both helper functions it calls
(`_hs_search_json_body_expr`, `_HS_SEARCH_URLS`) were read in full this session
(`scripts/build_cloud_workflows.py:4972-5052`) — no ambiguity in call shape. `resource` must be
`"contact"` or `"company"` (KeyError/ValueError otherwise at build time — self-guarding against typos).

**Credential registration analog** (`scripts/deploy_n8n_workflows.py:45-147`, dict shape confirmed
by RESEARCH.md §A5):
```python
NODE_CREDENTIAL_MAP = {
    "HubSpot Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    ...
}
```
Add: `"HubSpot Name Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},` — same
literal dict, exact same value shape as every other HubSpot node. Comments at lines 50-52/95-98/
103-107 already document why this step cannot be skipped (4 prior live 401 incidents from a
missed entry).

---

### `scripts/build_cloud_workflows.py` — `Skip (NoOp)` / `Unsupported Object Type` Set→Code conversion

**Analog:** the row-spread idiom used throughout this file's `$input.all().map` wrappers — e.g.
`ENRICH_ADAPT_SEARCH`'s `return { json: { ...row, existingRecord, lookup_failed: false } };`
(`scripts/build_cloud_workflows.py:1125`) or `ENRICH_GATE`'s `return { json: { ...row, gate, action } };`
(`:955`). The Set→Code conversion should follow the identical shape: a `Code` node (`n8n-nodes-base.code`,
`typeVersion` matching this file's other Code nodes) whose body is `return $input.all().map(it =>
({ json: { ...it.json, /* the marker fields this node previously hard-coded via Set */ } }));`.

**Node-build call site to change:** `Unsupported Object Type` at
`scripts/build_cloud_workflows.py:3685-3691` and `Skip (NoOp)` at `:3780-3786` — currently built as
`n8n-nodes-base.set typeVersion 3.4` (confirmed this session, RESEARCH.md §A4). Change the node
TYPE and PARAMETERS, keep the NODE NAME identical (connections + `NODE_CREDENTIAL_MAP` keys — n/a
here since these aren't HubSpot nodes — depend on the name staying stable).

**Companion test edit (mandatory, same commit):** remove both entries from `ROW_REPLACING_BY_DESIGN`
in `tests/test_row_carry.py:30-47` (full dict read this session):
```python
ROW_REPLACING_BY_DESIGN = {
    "Unsupported Object Type": "terminal marker consumed whole by Build Response",
    "Skip (NoOp)": "terminal marker consumed whole by Build Response",
    ...
    "Set Review": "terminal, no downstream consumer",
    "SJ-2 Skip (NoOp)": "terminal, no downstream consumer",
    "Review Stale (NoOp)": "terminal, no downstream consumer",
}
```
Delete the two `Unsupported Object Type` / `Skip (NoOp)` lines only — the other three stay. Skipping
this edit fails `test_every_row_replacing_entry_is_still_a_real_node_somewhere`
(`tests/test_row_carry.py:107-114`) because the waiver dict would name node names that are no
longer `n8n-nodes-base.set` anywhere.

---

### `scripts/build_cloud_workflows.py` — Lusha widening + comment rewrite

**Analog:** itself — the node build call and its adjacent comment block,
`scripts/build_cloud_workflows.py:3800-3863` (full text read this session). Current narrow body
expression (`:3857-3861`):
```python
"const c = {}; "
"if (id.email) c.email = id.email; "
"if (id.linkedin_url) c.linkedinUrl = id.linkedin_url; "
"const hasIdentity = !!(c.email || c.linkedinUrl); "
"return JSON.stringify(hasIdentity ? { contacts: [c], reveal } : { contacts: [] }); "
```
Widen to match `lushaContactBody()`'s full identity set (`n8n/code/lushaRequest.js:79-98`, the
module RESEARCH.md §A6 confirms already reads `email`/`linkedin_url`/`firstName`/`lastName`/
`companyName`/`domain` — six keys, "deliberately generic" per its own docstring). Mirror that
mapping in the inline expression (n8n expressions can't `require()` the module — this stays a
hand-written mirror per the existing comment at `:3818-3822`), e.g. add
`if (id.firstName) c.firstName = id.firstName;` / `lastName` / `companyName` / `domain` alongside
the existing two, and widen `hasIdentity` to `!!(c.email || c.linkedinUrl || (c.firstName && c.lastName && c.companyName))`.

**Comment to rewrite in place** (`:3824-3831`, opening line quoted): *"History: this CLOUD node
deliberately keeps sending the NARROW identity set (email + linkedinUrl only)..."* — rewrite with
the date (2026-08-05) and reason (v3 confirmed to accept the broad set per
`docs/LUSHA-V3-CONTRACT.md` §3, LOCAL-LIVE already sends it, v3 bills flat ~1 credit regardless).
Do not delete the history — CONTEXT.md calls this a recorded reversal, not a bug fix; the old
reasoning should stay legible, dated, and superseded.

**Test analog to extend:** `tests/n8n/lushaRequestContract.test.mjs` (confirmed this session,
RESEARCH.md §A6 — evaluates the real committed `jsonBody` expression via `new Function` and deep-
equals it against `lushaContactBody()`'s output for a matrix of inputs). Extend the input matrix
with cases carrying `firstName`/`lastName`/`companyName`/`domain` — do not write a new test file.

---

### `scripts/build_cloud_workflows.py` — ingest `HubSpot Search by Email` sentinel (Finding B, independent)

**Analog:** itself, `scripts/build_cloud_workflows.py:645` (a physically distant region of this
same file — the contact-ingest cloud builder, near line 656, not the `ENRICH_*` region starting at
914). Current filter value (RESEARCH.md §A3, exact text):
```python
value: ($json.email_normalized || $json.email)
```
Fix (CONTEXT.md §5B, exact string):
```python
value: ($json.email_normalized || $json.email || "no-email@invalid.invalid")
```
One-expression, one-node change. `tests/test_ingest_search_contract.py:48` asserts the substring
`"$json.email_normalized || $json.email" in body` — still present as a verbatim prefix, so that
pinned assertion survives unchanged; extend the test with one new assertion for the sentinel value
if desired, per RESEARCH.md §B.3 (optional, not required to avoid breaking the existing pin).

---

## Shared Patterns

### Row-carry discipline (`{ json: { ...row, <new fields> } }`)
**Source:** every `$input.all().map` wrapper in `scripts/build_cloud_workflows.py`'s `ENRICH_*`
constants (`ENRICH_BUILD_IDENTITY`, `ENRICH_GATE`, `ENRICH_NORMALIZE_SCORE`, `ENRICH_MERGE`,
`ENRICH_ADAPT_SEARCH`).
**Apply to:** every new/modified Code node in this phase. `tests/test_row_carry.py` enforces this
structurally across all `wf_*_cloud.json` — any node that emits `{fieldA, fieldB}` instead of
`{...row, fieldA, fieldB}` breaks the whole downstream chain (BUG 12, the file's own header).

### Pure-module / Code-node split
**Source:** `n8n/code/*.js` module docstrings (`listExpansion.js:1-46`, `providerSelection.js:1-31`).
**Apply to:** `matchProposal.js`. Pure logic (no `$json`/`$input`/`$(...)`) lives in the module;
n8n-global-touching glue lives in the builder's wrapper string appended via `inline(module) + r"""..."""`.
This split is WHY the module can be both `require()`'d directly by a Node test
(`createRequire`/`require(path.join(ROOT, "n8n/code/matchProposal.js"))`) and separately inlined
(stripped of its `require`/`module.exports` lines) into the generated Code node — the two
consumption paths never conflict.

### Refuse-whole, never-truncate
**Source:** `n8n/code/listExpansion.js`'s `refuse()`/`oversizeRefusal()` (lines 81-122) — D-15 principle.
**Apply to:** `ENRICH_PARSE_EVENT_CLOUD`'s new `events`-array size refusal. A 200 response with a
`refused`/`reason` marker, never a partial silent success and never a thrown exception (which risks
a Cloudflare 524, the D-22 failure mode this file's own comments name).

### `_hs_http_search_node` for every new HubSpot CRM v3 search call
**Source:** `scripts/build_cloud_workflows.py:5015-5052`, and its two existing call sites
(`HubSpot Search` at `:3720-3725`, `Dedupe Search` per the docstring's Phase 21 Plan 01 note).
**Apply to:** the new `HubSpot Name Search` node. Never build a native n8n HubSpot node with
`operation: "search"` (BUG 10/BUG 23, documented in the helper's own docstring) — always this
credential-bound raw-HTTP helper.

### `NODE_CREDENTIAL_MAP` registration is mandatory for every new HubSpot node
**Source:** `scripts/deploy_n8n_workflows.py:45-147`, comments at lines 50-52/95-98/103-107.
**Apply to:** `HubSpot Name Search`. An unmapped HubSpot node deploys unbound and 401s only at
runtime — documented as having happened 4 times in this repo already.

## No Analog Found

None — every file in the build plan (CONTEXT.md §7 + RESEARCH.md §C) has a confirmed, same-file or
same-repo analog. RESEARCH.md's own verification pass (§A) already established this; no gaps
required falling back to external/generic patterns.

## Metadata

**Analog search scope:** `n8n/code/*.js`, `scripts/build_cloud_workflows.py` (targeted reads at the
line ranges RESEARCH.md §C already pinned), `scripts/deploy_n8n_workflows.py` (`NODE_CREDENTIAL_MAP`),
`tests/n8n/*.test.mjs`, `tests/test_row_carry.py`.
**Files scanned:** 2 pure-JS modules read in full (`listExpansion.js`, `providerSelection.js`); 5
non-overlapping targeted reads of `build_cloud_workflows.py` (lines 900-1160, 3290-3380, 3800-3870,
4970-5055); 1 test file read in full (`listExpansion.test.mjs`); 1 test file partially read
(`test_row_carry.py:1-60`, the waiver dict).
**Pattern extraction date:** 2026-08-05
