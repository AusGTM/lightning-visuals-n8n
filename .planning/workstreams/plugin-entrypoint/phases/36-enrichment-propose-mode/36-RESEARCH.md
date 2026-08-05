# Phase 36: Enrichment Propose Mode & Match Lane - Research

**Researched:** 2026-08-05
**Domain:** n8n Cloud workflow generation (`scripts/build_cloud_workflows.py` Python builder →
committed `n8n/*.json`), HubSpot CRM v3 Search API, this repo's pure-JS Code-node module
convention (`n8n/code/*.js`).
**Confidence:** HIGH — every claim below that carries a `[VERIFIED: path:lines]` tag was read
this session with `Read`/`Bash` against the current worktree (`feat/v0.6-plugin-entrypoint`,
clean except `.DS_Store`, `1939` tests collected matching the `1933 passed / 6 skipped` baseline
exactly, arming grep `0`).

This is a **source-verification pass**, not an exploratory one. 36-CONTEXT.md is the locked
decision record (§4's four decisions, §7's nine-step build plan, §8's definition of done). This
document does not revisit any of those decisions — it either confirms the concrete symbols
CONTEXT.md cites still match the source, or says loudly where they don't, and fills the gaps
CONTEXT.md explicitly leaves to the planner (§B below).

**Primary recommendation:** Every constant/node/test CONTEXT.md names in §7's build plan was
found at the cited (or a nearby, now-pinned) location and matches its described shape. **Nothing
in §5's two findings, §6's wire contract, or §10's pinned-test claim failed verification.** The
planner can write tasks against the exact identifiers in §C below without re-deriving them.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Match-tier search (email EQ / lastname EQ + company CONTAINS_TOKEN) | API/Backend — n8n Cloud workflow, HubSpot CRM v3 Search via `_hs_http_search_node` | — | Search executes server-side against HubSpot's API through an n8n `httpRequest` node; no client-side search exists |
| Mode dispatch (`propose` vs `write` vs absent) | API/Backend — n8n Code nodes (`Parse HubSpot Event` → row-carried `mode` → `Decide Action`/`Decide Company Action`) | — | Pure business logic, no external call |
| Match re-verification (`mediumCandidates`, value-check over search-filter trust) | API/Backend — new pure JS module `n8n/code/matchProposal.js`, inlined into a Code node | — | Mirrors this repo's `listExpansion.js`/`providerSelection.js` pattern: pure function, no n8n globals, unit-tested directly via `node --test` |
| Batch-size refusal (`events.length > ENRICH_MAX_LIST_RECORDS`) | API/Backend — `Parse HubSpot Event` (or a preceding Code node) | Client (Phase 37) mirrors by chunking, deferred | Server refuses whole; the client's chunking is the *other* half of the same D-15 principle, built in Phase 37 |
| Lusha identity widening | API/Backend (n8n Code node → Lusha HTTP request body) | External provider (Lusha v3 API) | Body shape only; no new service |
| `Skip (NoOp)` / `Unsupported Object Type` row-carry fix | API/Backend — n8n Code nodes replacing `Set` nodes | — | Row-carry is a property of the generated JSON, proven offline by `tests/test_row_carry.py` |

No browser/CDN/database tier is touched by this phase — it is entirely inside the generated n8n
Cloud workflow JSON and its Python builder.

<user_constraints>
## User Constraints (from 36-CONTEXT.md)

### Locked Decisions (36-CONTEXT.md §4 — do not redesign)

1. **Explicit `mode:"propose"`** — runs the waterfall, returns merged `properties`, never enters
   the write path. Must NOT be implemented by reading properties off a `write_blocked` response
   (that would couple the feature to `ALLOW_HUBSPOT_CREATE` staying false).
2. **Match tiers.** `email EQ` → HIGH, auto-matched. Else `lastname EQ` + `company
   CONTAINS_TOKEN` → MEDIUM, returned as a proposal with enough of the candidate to judge it. No
   hit → enrich.
3. **Widen `Lusha Enrich` on cloud** to the name+company+domain identity set — a recorded
   decision *reversal*, not a bug fix. Rewrite the "deliberately narrow" comment in place with
   date and reason.
4. **Chunking stays client-side** (Phase 37). This phase ships only the refusal half: an oversize
   `events` array is refused whole, never truncated (the D-15 principle the list lane already
   honours).

### Claude's Discretion

CONTEXT.md leaves no strategic discretion — §7's nine steps are prescriptive. The only open
choices are **implementation mechanics** CONTEXT.md does not spell out, filled in §B/§D below:
- How `mode` physically threads from the webhook body onto every row (§D "mode threading").
- The exact internal shape of `matchProposal.js`'s three functions.
- Which existing pytest file gets which new assertion (§B.4 file→pin map).

### Deferred Ideas (OUT OF SCOPE)

- **Phase 37** — the client-side chunking half and the propose→approve→ingest UI flow. This
  phase is backend-only, no plugin file changes, no plugin release (36-CONTEXT.md line 4).
- **Risk 1's upgrade path** — routing propose-mode skip rows through the waterfall with all
  providers disabled. Explicitly: "Do not build it until it bites" (36-CONTEXT.md §12.1).
- **Rewriting the batch-wide `lookup_failed` scope itself** — Finding B's fix removes the only
  way that flag was ever falsely manufactured; the scope becoming genuinely batch-wide-on-real-
  failure is now correct and is explicitly out of scope to change further (36-CONTEXT.md §5B).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISPATCH-02 | Enrichment of existing HubSpot records POSTs to `hubspot/enrichment/event` | Confirmed this is the SAME webhook/workflow (`wf_enrichment_cloud.json`, path `hubspot/enrichment/event` — `scripts/build_cloud_workflows.py:3626`) this phase extends; no new endpoint. `mode` is an added field on the existing wire contract, not a new route. |
| STRUCT-02 | Rows failing the identity rule (email OR firstname+lastname+company) are separated and reported rather than sent | This phase's `ENRICH_GATE` step 8 addition (no email, no linkedin, no lastName+companyName → `action="skip"`) is the enrichment-lane analog for unmatchable rows — confirmed `ENRICH_GATE` (contacts) currently has no such check (`scripts/build_cloud_workflows.py:938-957`), so this is a genuine new branch, not already covered. |
| STRUCT-04 | Extraction never invents field values — absent data stays absent | Confirmed by the wire contract (36-CONTEXT.md §6): `properties` carries only what the waterfall discovered; `firstname/lastname/company` are deliberately absent from the response since the client already holds them. `mediumCandidates`'s value re-verification (§7 step 1) is the mechanism that stops a fuzzy `CONTAINS_TOKEN` hit from being reported as a confident match it isn't. |
| PREVIEW-03 | Batches above a configured size are chunked, with the chunking plan shown in the preview | This phase ships the **refusal half only** (client chunking is Phase 37). `ENRICH_MAX_LIST_RECORDS = 2` (`scripts/build_cloud_workflows.py:3361`) is the existing ceiling constant to reuse for the new `events`-array refusal — confirmed it is declared in exactly one place and the list lane's `expandListToEvents`/`refuse()` shape (`n8n/code/listExpansion.js:81-83, 115-122, 188-191`) is the precedent to mirror, not reinvent. |
</phase_requirements>

## §A — Verification of 36-CONTEXT.md's Claims

Every row below was checked against the current worktree this session.

### A1 — Named constants/helper in `scripts/build_cloud_workflows.py`

| Symbol | Verdict | Location |
|---|---|---|
| `ENRICH_BUILD_IDENTITY` | **CONFIRMED** | `scripts/build_cloud_workflows.py:914-934` |
| `ENRICH_ADAPT_SEARCH` | **CONFIRMED** | `scripts/build_cloud_workflows.py:1101-1127` |
| `ENRICH_ADAPT_FETCH_BY_ID_CONTACT` | **CONFIRMED** | `scripts/build_cloud_workflows.py:3557-3573` |
| `ENRICH_PARSE_EVENT_CLOUD` | **CONFIRMED** | `scripts/build_cloud_workflows.py:3298-3336` |
| `ENRICH_DECIDE_CLOUD` | **CONFIRMED** | `scripts/build_cloud_workflows.py:1223-1281` |
| `ENRICH_DECIDE_CO_CLOUD` | **CONFIRMED** | `scripts/build_cloud_workflows.py:2499-2561` |
| `ENRICH_GATE` | **CONFIRMED** | `scripts/build_cloud_workflows.py:938-957` |
| `_hs_http_search_node` helper | **CONFIRMED** | `scripts/build_cloud_workflows.py:5015-5052` |

`_hs_http_search_node` signature `[VERIFIED: scripts/build_cloud_workflows.py:5015]`:
```python
def _hs_http_search_node(name, resource, x, y, filter_groups, properties_csv, limit=100):
```
`resource` must be a key in `_HS_SEARCH_URLS = {"company": ".../companies/search", "contact":
".../contacts/search"}` (`scripts/build_cloud_workflows.py:5009-5012`) or the call raises
`ValueError` at build time — a typo'd resource name cannot silently deploy. `filter_groups` is a
list of filter-group lists, each filter a dict `{propertyName, operator, value?}`; the operator
string is passed through untouched by `_hs_search_json_body_expr`
(`scripts/build_cloud_workflows.py:4972-5006`) — **no special-casing exists for any operator
name**, so `"CONTAINS_TOKEN"` needs zero builder changes to use, only a correct filter-group
literal at the call site (see §B.2).

### A2 — Finding A: mixed-lane duplication (both adapters read `Build Identity`)

**CONFIRMED, exactly as described.**
- `ENRICH_ADAPT_SEARCH` opens `const rows = $('Build Identity').all();`
  `[VERIFIED: scripts/build_cloud_workflows.py:1104]`
- `ENRICH_ADAPT_FETCH_BY_ID_CONTACT` opens `const rows = $('Build Identity').all();`
  `[VERIFIED: scripts/build_cloud_workflows.py:3565]`

Both then index-align against their own HTTP node (`$('HubSpot Search').all()` /
`$('HubSpot Fetch By Id').all()`). Today only one lane's rows exist per execution (every batch is
homogeneous), so the duplication is latent. CONTEXT.md's §7 step 2 fix — stamp `lane` once in
`ENRICH_BUILD_IDENTITY`, filter to it in each adapter — is the correct fix location: both readers
already share the identical row source, so a `lane` field on that one row object propagates to
both filters for free (see §D for the row-carry mechanism this depends on).

### A3 — Finding B: ingest lane's manufactured batch-wide failure

**CONFIRMED, exactly as described** — and in a **different workflow** than A1/A2 (the ingest
lane, `wf_contact_ingest_cloud.json`, not the enrichment lane). This matters for planning: the
fix touches a different builder function than steps 1-8.

- `HubSpot Search by Email` filter value:
  `value: ($json.email_normalized || $json.email)`
  `[VERIFIED: scripts/build_cloud_workflows.py:645]` (inside the contact-ingest cloud builder;
  node registered in `NODE_CREDENTIAL_MAP` at `scripts/deploy_n8n_workflows.py:107`)
- `ADAPT_SEARCH_RESULTS` declares `let lookup_failed = false;` **before** (outside) the
  `for (const s of search)` loop that follows it:
  `[VERIFIED: scripts/build_cloud_workflows.py:201-215]`
  ```js
  const rows = $('Normalize Phone').all();
  const search = $('HubSpot Search by Email').all();
  const candidates = [];
  let lookup_failed = false;
  for (const s of search) {
    ...
    if (s.error || res.error || res.status === "error") { lookup_failed = true; continue; }
    ...
  }
  ```
  A single failed item in the loop sets the flag for the whole batch, then every row in the
  `rows.map(...)` below (line 219+) receives the same `lookup_failed` value — confirming
  CONTEXT.md's "one emailless row marks the whole upload lookup-failed" mechanism exactly.

**The proposed fix does not break the pinned test.** `tests/test_ingest_search_contract.py:48`
asserts `"$json.email_normalized || $json.email" in body` (a Python substring check, not an
equality). CONTEXT.md's fix appends ` || "no-email@invalid.invalid"` to the same expression —
the substring `$json.email_normalized || $json.email` still occurs verbatim as a prefix, so this
specific assertion survives unchanged. The `search[i]` prohibition
(`tests/test_ingest_search_contract.py:60`, `assert not re.search(r"search\[\s*i\s*\]", ...)`) is
also untouched — the fix is a filter-value expression edit only, not a rewrite of the
value-matching adapter logic.

### A4 — `Skip (NoOp)` / `Unsupported Object Type` are `Set` nodes; `test_row_carry.py` exempts them

**CONFIRMED.**
- `Unsupported Object Type`: `"type": "n8n-nodes-base.set", "typeVersion": 3.4`
  `[VERIFIED: scripts/build_cloud_workflows.py:3685-3691]`
- `Skip (NoOp)`: `"type": "n8n-nodes-base.set", "typeVersion": 3.4`
  `[VERIFIED: scripts/build_cloud_workflows.py:3780-3786]`
- Both are exempted in `ROW_REPLACING_BY_DESIGN` in `tests/test_row_carry.py:30-47`, with the
  identical reason string `"terminal marker consumed whole by Build Response"` for both entries
  (lines 34 and 36).

**Planner note not spelled out in CONTEXT.md's §7 step 5:** `tests/test_row_carry.py` also has
`test_every_row_replacing_entry_is_still_a_real_node_somewhere`
(`tests/test_row_carry.py:107-114`), which collects every live `n8n-nodes-base.set` node name
across all `wf_*_cloud.json` files and fails if a `ROW_REPLACING_BY_DESIGN` entry names a node
that is no longer a `Set` node anywhere. **Converting these two nodes to Code nodes without also
deleting their two dict entries will fail this test** (the names become "stale waivers"). The
plan must include removing both lines from `ROW_REPLACING_BY_DESIGN`, not just changing the node
type — this is the "retire their exemptions" CONTEXT.md's §7 step 5 already names, but the exact
mechanism (which test, which failure mode) is this finding.

### A5 — `NODE_CREDENTIAL_MAP` shape

**CONFIRMED.** `scripts/deploy_n8n_workflows.py:45-147` — a flat dict:
```python
NODE_CREDENTIAL_MAP = {
    "HubSpot Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    ...
}
```
Every existing HubSpot search/fetch/create/update node in `wf_enrichment_cloud.json` uses
`{"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"}`. A new `HubSpot Name Search` entry
must be added in this exact shape:
```python
"HubSpot Name Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
```
Comments at lines 50-52, 95-98, and 103-107 document the repeated failure mode CONTEXT.md warns
about ("an unmapped HubSpot node deploys unbound and 401s only at runtime") — this repo's own
history shows it has happened at least 4 times, cross-referenced in the map's own comments.

### A6 — `lushaContactBody()` supports the wider identity set; narrow comment location

**CONFIRMED on both counts.**
- `lushaContactBody(identityKeys, missingFields)` in `n8n/code/lushaRequest.js:79-98` reads
  `id.email`, `id.linkedin_url`, `id.firstName`, `id.lastName`, `id.companyName`, `id.domain` —
  all six identity keys, already generic (module docstring at lines 66-73 explicitly says this is
  "deliberately generic" and names the CLOUD emission site as the one caller that narrows it).
- The Cloud `Lusha Enrich` node's inline request-body expression sends **only** `email` and
  `linkedinUrl`:
  `[VERIFIED: scripts/build_cloud_workflows.py:3857-3862]`
  ```js
  const c = {};
  if (id.email) c.email = id.email;
  if (id.linkedin_url) c.linkedinUrl = id.linkedin_url;
  ```
- The "deliberately narrow" comment block to rewrite is
  `[VERIFIED: scripts/build_cloud_workflows.py:3824-3831]`, opening: *"History: this CLOUD node
  deliberately keeps sending the NARROW identity set (email + linkedinUrl only) that was
  live-confirmed for it pre-migration against the retired v2 endpoint..."*
- `tests/n8n/lushaRequestContract.test.mjs` exists and does exactly what CONTEXT.md claims: it
  evaluates the REAL committed `jsonBody` n8n-expression string from `n8n/wf_enrichment_cloud.json`
  via `new Function`, and asserts it deep-equals `lushaContactBody()`'s output for a matrix of
  inputs `[VERIFIED: tests/n8n/lushaRequestContract.test.mjs:1-60]`. Extending its input matrix
  (rather than writing a new test file) is the correct anti-drift-guard action.

### A7 — Pinned test to amend: `test_gate_exists_and_true_false_lanes_target_fetch_and_search_respectively`

**CONFIRMED.** `tests/test_fetch_by_id_topology.py:107-118`:
```python
def test_gate_exists_and_true_false_lanes_target_fetch_and_search_respectively(branch):
    ...
    true_branch, false_branch = doc["connections"][cfg["gate_if"]]["main"]
    assert true_branch[0]["node"] == cfg["fetch_node"], (...)
    assert false_branch[0]["node"] == cfg["search_node"], (...)
```
Independently confirmed against the built JSON: `IF Bare Event`'s current connections are
`true → "HubSpot Fetch By Id"`, `false → "HubSpot Search"`
`[VERIFIED: n8n/wf_enrichment_cloud.json, connections["IF Bare Event"]]`. CONTEXT.md's plan
re-points only the false lane, to `"IF Has Email"` — the true lane and the fetch-by-id branch are
untouched. `BRANCHES` parametrizes this over `["contacts", "companies"]`
(`tests/test_fetch_by_id_topology.py`), so confirm whether the companies branch also needs a
match lane or is genuinely contacts-only before amending both parametrized cases — CONTEXT.md's
wire contract and §7 build plan describe contacts only (`objectType:"contact"` in the example
event); the companies branch's `IF Bare Event`-equivalent (if one exists) was not asked about and
was not checked this session — **flag as an open question for the planner** (§F below).

### A8 — `SJ-3 Dispatch To Enrichment` uses `mode:"each"`; safe for the new refusal

**CONFIRMED**, and the pre-flight conclusion holds. `[VERIFIED: n8n/wf_scheduled_maintenance_cloud.json]`:
```json
{
  "name": "SJ-3 Dispatch To Enrichment",
  "type": "n8n-nodes-base.executeWorkflow",
  "parameters": { "mode": "each", ... }
}
```
`mode:"each"` means this `executeWorkflow` node invokes the enrichment sub-workflow **once per
input item**, and its upstream node (`SJ-3 Extract Rows`) already emits one n8n item per matched
HubSpot record `[VERIFIED: n8n/wf_scheduled_maintenance_cloud.json]`. Each invocation's body is a
bare single-record object, never an `events` array. Tracing `parseWebhookBody`
(`n8n/code/providerSelection.js:33-39`) confirms a bare object (no `.events` array, not an array
itself) is wrapped as `[body]` — a length-1 array. **The new `events.length >
ENRICH_MAX_LIST_RECORDS` refusal can never fire for SJ-3's calls**, since SJ-3 never sends more
than one implicit event per POST. No HubSpot webhook subscription posting to this URL was
independently re-verified this session (CONTEXT.md's other pre-flight condition) — accept
CONTEXT.md's claim as unverified-this-session but plausible given the private-app webhook
subscription list in `CLAUDE.md` §20.2 names only `company.propertyChange.enrichment_requested`
and `contact.propertyChange.enrichment_requested`, both of which HubSpot batches ≤100 events
natively per its own delivery contract, not via this repo's code.

### A9 — `ENRICH_MAX_LIST_RECORDS` and the existing refusal shape to mirror

**CONFIRMED.** `ENRICH_MAX_LIST_RECORDS = 2` is declared exactly once
`[VERIFIED: scripts/build_cloud_workflows.py:3361]`, derived from live timing measurement
(comment block at lines 3351-3360, cites `25-BLOCKERS.md`/`29-TIMING.md`, "CONFIRMED
2026-08-03: probe B4 ran the full waterfall live... 37.44 s... floor(100/46.8) = 2. The ceiling
held on the expensive path and is no longer provisional.").

The list lane's refusal shape to mirror (`n8n/code/listExpansion.js`):
```js
function refuse(reason) {
  return { events: [], refused: true, reason };
}
function oversizeRefusal(name, maxRecords, detail) {
  return (
    `The list "${name}" is larger than this backend can enrich in one request — the ` +
    `limit is ${maxRecords} record(s) per request, measured against the ~100s webhook ` +
    `response ceiling. ${detail} Nothing was enriched. Send record IDs instead, in ` +
    `batches of ${maxRecords} or fewer.`
  );
}
```
`[VERIFIED: n8n/code/listExpansion.js:81-83, 115-122]`. The n8n wrapper around it
(`ENRICH_EXPAND_LIST_TO_EVENTS`, `scripts/build_cloud_workflows.py:3394-3419`) converts a refusal
into a **terminating item**, not a thrown exception:
```js
if (result.refused) {
  return [{ json: { outcome: "refused", reason: result.reason, events: [] } }];
}
```
and downstream `IF List Expanded` gates on `Array.isArray($json.events) && $json.events.length >
0` (`scripts/build_cloud_workflows.py:3667-3669`), so a refusal structurally cannot reach the
enrichment chain. **The new `events`-array-size refusal in `ENRICH_PARSE_EVENT_CLOUD` should copy
this exact shape**: a pure check before `parsed.events.map(...)`, returning a single terminating
item with `outcome:"refused"`/`reason`/`events:[]` rather than throwing, feeding the SAME `Build
Response` convergence point (or an equivalent early exit) so the webhook still answers 200 with a
reason rather than hanging to a Cloudflare 524 (the D-22 failure mode `listExpansion.js`'s own
comments name at lines 24-25).

## §B — Gaps CONTEXT.md Leaves to the Planner

### B.1 — `matchProposal.js` module conventions

Closest existing analog: **`n8n/code/listExpansion.js`** (not `providerSelection.js` — that one
has no "refuse" concept; `listExpansion.js` is the module that already implements "search
result → structured decision, including a refusal branch" for this exact webhook).

Confirmed module shape/conventions all `n8n/code/*.js` files share
`[VERIFIED: scripts/build_cloud_workflows.py:50-77, "strip_module"/"inline"]`:
- CommonJS: plain `function foo() {}` declarations, ending in a single
  `module.exports = { foo, bar, ... };` block.
- **No `require()` of sibling files** — each module is fully self-contained (the builder's
  `strip_module()` strips any `require()` line anyway, single- or multi-line destructuring form,
  and everything from `module.exports` onward; a module that imported a sibling function would
  silently lose it in the inlined Code node body).
- No n8n globals (`$json`, `$input`, `$(...)`) inside the module itself — those are added by the
  **n8n wrapper** appended in `scripts/build_cloud_workflows.py` (e.g.
  `ENRICH_EXPAND_LIST_TO_EVENTS = inline("listExpansion.js") + r"""...wrapper..."""`).
- Builder inlines via `inline(*modules)` (`scripts/build_cloud_workflows.py:75-77`), which
  concatenates `strip_module()` output in call order — dependency order matters if
  `matchProposal.js` is inlined alongside another module in the same Code node.

Test convention `[VERIFIED: tests/n8n/listExpansion.test.mjs:1-40]`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { expandListToEvents, VIEW_REFUSAL } = require(path.join(ROOT, "n8n/code/listExpansion.js"));
```
i.e. the module is `require()`'d directly by its CommonJS `module.exports` — Node can do this
even though the module is *also* stripped/inlined into a Code node by the Python builder; the two
consumption paths (test via `require`, builder via `inline()`) never conflict because the builder
strips the `module.exports` line before inlining. A `matchProposal.test.mjs` in `tests/n8n/`
following this exact pattern is the correct new test file.

### B.2 — HubSpot CRM v3 search-filter shape already emitted by this builder

The existing email-EQ filter (verbatim, `scripts/build_cloud_workflows.py:3720-3725`):
```python
hs_search = _hs_http_search_node(
    "HubSpot Search", "contact", x, y,
    filter_groups=[[{"propertyName": "email", "operator": "EQ",
                      "value": "={{ $json.identity_keys.email }}"}]],
    properties_csv=ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
)
```
The `filter_groups` argument is a list of AND-groups, OR'd together
(`_hs_search_json_body_expr`'s docstring, `scripts/build_cloud_workflows.py:4972-4985`: "groups
OR, filters-within-group AND"). For `lastname EQ` AND `company CONTAINS_TOKEN` in the same group
(both must match), the call would be:
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
No code path in `_hs_search_json_body_expr` special-cases the `operator` string
(`scripts/build_cloud_workflows.py:4991-4996`, `render_filter`) — it is `json.dumps()`'d
literally into the JS object, so `"CONTAINS_TOKEN"` requires zero builder changes to emit.

**CONTEXT.md's claim that "HubSpot CRM v3 has no `CONTAINS` operator and a bare one is a
guaranteed 400" is `[ASSUMED]`** — no prior HubSpot search-operator contract doc (this repo has
one for Lusha, `docs/LUSHA-V3-CONTRACT.md`, but none found for HubSpot's search filter operator
vocabulary) was found in this repo, and no existing filter in this codebase uses either
`CONTAINS` or `CONTAINS_TOKEN`. This is standard, well-documented HubSpot CRM v3 Search API
behavior (the officially supported string-property operators are `EQ`/`NEQ`/`LT`/`LTE`/`GT`/
`GTE`/`BETWEEN`/`IN`/`NOT_IN`/`HAS_PROPERTY`/`NOT_HAS_PROPERTY`/`CONTAINS_TOKEN`/
`NOT_CONTAINS_TOKEN`), but since it was not confirmed against an authoritative source *this
session*, tag it `[ASSUMED]` per the provenance rule and flag: if the planner wants HIGH
confidence here, a one-line live probe (a `CONTAINS_TOKEN` search against a real portal) would
convert this to `[VERIFIED]` — CONTEXT.md's own §12 Risk 4 already anticipates "the first propose
run is the live proof" for the Lusha widening; the same caveat applies to this operator choice.

### B.3 — Pytest files that pin enrichment topology/contract (assignment map for new assertions)

| File | What it pins | Relevant to this phase because |
|---|---|---|
| `tests/test_cloud_write_path.py` | Write-path authentication, real record ids, fail-closed on lookup failure, zero-write-unless-gated — Phase 16 Task 6 | `Route By Object Type` edges are pinned here; propose mode must not disturb this routing |
| `tests/test_fetch_by_id_topology.py` | Fetch-by-id lane structural shape: gate placement, edge targets, node shapes, credential binding, node-name row recovery — Phase 16.4-02 | **Must be amended** per §A7 (`IF Bare Event`'s false-lane target changes) |
| `tests/test_provider_gate_topology.py` | Gated bypass-convergence provider waterfall topology (Phase 16.1) | New match lane sits *before* this chain (per CONTEXT.md §7 step 3, hangs off `IF Bare Event`'s false edge); provider-gate topology itself is unaffected but worth a reachability check post-change |
| `tests/test_write_gate_coverage.py` | Every write node in every cloud workflow sits behind `_writeSafetyAllows` — BUG 15 | Propose mode must never reach a write node at all (CONTEXT.md decision 1) — this file's "every write node is gated" invariant is a good place to add "propose mode never reaches a write node" as a structural companion assertion |
| `tests/test_enrichment_contacts_search_transport.py` | Contacts search transport (BUG 23): the `_hs_http_search_node` httpRequest shape returns a 200 envelope on zero hits rather than zero items | The new `HubSpot Name Search` node must use the same transport — natural home for a shape-parity assertion |
| `tests/test_row_carry.py` | Row-carrying property of mid-chain `Set`/Code nodes (BUG 12) | **Must be amended**: remove `Unsupported Object Type` and `Skip (NoOp)` from `ROW_REPLACING_BY_DESIGN` once converted to Code nodes (§A4) |
| `tests/test_ingest_search_contract.py` | Ingest lane's email-search filter + value-match adapter (BUG 22) | Confirmed NOT broken by Finding B's fix (§A3); no change needed here unless the planner wants an explicit new assertion for the sentinel value |
| `tests/test_phase31_two_sided_contracts.py` | Inventory guard: every two-sided contract this repo has closed, with both pin locations named | CONTEXT.md §5A explicitly names this file as "the existing precedent for exactly this shape" for pinning the client-side "one lane per chunk" rule — that pin is a **client-side (Phase 37) contract**, so this phase's job is only to make sure the *server* half (the `lane` field) exists for Phase 37 to read; adding the actual two-sided row here may be premature until Phase 37 lands the client half |
| `tests/n8n/lushaRequestContract.test.mjs` | Expression-vs-module deep-equality for the Lusha request body (Node test) | **Must be extended**, not replaced — the Lusha widening is a body-shape change and this file already asserts equality against `lushaContactBody()` |

No new test file is needed for the mixed-lane duplication fix, the batch-size refusal, or the
`ENRICH_GATE` unmatchable-row skip — each has an existing home above; only `matchProposal.js`
needs a genuinely new test file (§B.1).

### B.4 — `Build Response` wiring (Risk 1)

**CONFIRMED, 8 inbound branches**, matching `ENRICH_BUILD_RESPONSE`'s own comment ("5 real
terminals + the 2 re-pointed IF-enrich-false lanes + the unsupported-object-type terminal",
`scripts/build_cloud_workflows.py:3482-3495`):
`[VERIFIED: n8n/wf_enrichment_cloud.json connections graph]`
```
IF Enrich, HubSpot Create, HubSpot Update, Skip (NoOp),
IF Company Enrich, HubSpot Company Create, HubSpot Company Update, Unsupported Object Type
```
all feed `Build Response`. Per CONTEXT.md's §7 step 4, a `"proposed"` action exits via `IF
Enrich`'s FALSE lane (since `"proposed" !== "enrich"`) — i.e. it reuses the *existing* `IF
Enrich`→`Build Response` false-lane edge, adding **zero new inbound branches** to `Build
Response`. This confirms Risk 1's exposure is unchanged by this phase (still first-arrival
semantics across the same 8 branches, none of them new) — the risk is inherited, not introduced,
and CONTEXT.md's own mitigation reasoning (chunk ceiling of 2, `row_id` correlation) is the
correct scope, not a gap.

## §C — Concrete Symbol Reference (for the planner's task text)

| Symbol | File:Lines |
|---|---|
| `ENRICH_BUILD_IDENTITY` | `scripts/build_cloud_workflows.py:914-934` |
| `ENRICH_GATE` (contacts) | `scripts/build_cloud_workflows.py:938-957` |
| `ENRICH_CO_GATE` (companies — has no name/company-skip rule, contacts-only per CONTEXT.md §7 step 8) | `scripts/build_cloud_workflows.py:1721-1738` |
| `ENRICH_ADAPT_SEARCH` | `scripts/build_cloud_workflows.py:1101-1127` |
| `ENRICH_DECIDE_CLOUD` | `scripts/build_cloud_workflows.py:1223-1281` |
| `ENRICH_DECIDE_CO_CLOUD` | `scripts/build_cloud_workflows.py:2499-2561` |
| `ENRICH_PARSE_EVENT_CLOUD` | `scripts/build_cloud_workflows.py:3298-3336` |
| `ENRICH_MAX_LIST_RECORDS` | `scripts/build_cloud_workflows.py:3361` (value `2`) |
| `ENRICH_EXPAND_LIST_TO_EVENTS` (refusal-shape precedent) | `scripts/build_cloud_workflows.py:3394-3419` |
| `ENRICH_ADAPT_FETCH_BY_ID_CONTACT` | `scripts/build_cloud_workflows.py:3557-3573` |
| `_hs_http_search_node` | `scripts/build_cloud_workflows.py:5015-5052` |
| `_hs_search_json_body_expr` | `scripts/build_cloud_workflows.py:4972-5006` |
| `_HS_SEARCH_URLS` | `scripts/build_cloud_workflows.py:5009-5012` |
| `IF Bare Event` node build | `scripts/build_cloud_workflows.py:3740-3750` |
| `Skip (NoOp)` node build | `scripts/build_cloud_workflows.py:3780-3786` |
| `Unsupported Object Type` node build | `scripts/build_cloud_workflows.py:3685-3691` |
| `NODE_CREDENTIAL_MAP` | `scripts/deploy_n8n_workflows.py:45-147` |
| `lushaContactBody()` | `n8n/code/lushaRequest.js:79-98` |
| Cloud `Lusha Enrich` node (narrow expression + comment to rewrite) | `scripts/build_cloud_workflows.py:3824-3863` |
| `parseWebhookBody()` | `n8n/code/providerSelection.js:33-39` |
| `listExpansion.js` (refusal-shape/`matchProposal.js` analog) | `n8n/code/listExpansion.js` (whole file, esp. `refuse`/`oversizeRefusal` at 81-122) |
| `ROW_REPLACING_BY_DESIGN` waiver dict | `tests/test_row_carry.py:30-47` |
| `test_gate_exists_and_true_false_lanes_target_fetch_and_search_respectively` | `tests/test_fetch_by_id_topology.py:107-118` |
| `HubSpot Search by Email` filter (ingest lane, Finding B) | `scripts/build_cloud_workflows.py:640-649` |
| `ADAPT_SEARCH_RESULTS` (ingest lane, `lookup_failed` scope) | `scripts/build_cloud_workflows.py:186-238` |
| `SJ-3 Dispatch To Enrichment` (`mode:"each"` pre-flight) | `n8n/wf_scheduled_maintenance_cloud.json` |

## §D — Additional Load-Bearing Findings (not directly asked, discovered while verifying)

### D.1 — How `mode` physically threads onto every row

CONTEXT.md §7 step 4 says "`ENRICH_PARSE_EVENT_CLOUD` reads `mode`" but does not specify the
mechanism. Traced it: `parseWebhookBody()` currently extracts only `events` and `providers` from
the envelope (`n8n/code/providerSelection.js:33-39`) — it has **no `mode` extraction today**.
`ENRICH_PARSE_EVENT_CLOUD`'s wrapper then does `...event` spread per parsed event
(`scripts/build_cloud_workflows.py:3332`), which would only put `mode` on a row if the caller
sent `mode` on the *individual event object*, not at the envelope level CONTEXT.md's wire
contract shows (`{"mode":"propose", "providers":[...], "events":[...]}` — `mode` is a sibling of
`events`, not nested inside each event).

Two ways to close this, both consistent with the codebase's own pattern:
1. **Extend `parseWebhookBody()`** to also extract `body.mode` (mirrors exactly how `providers`
   is already extracted at the envelope level) — the more idiomatic fix, since this module is the
   single place envelope-level fields are read, and it already has a direct unit test
   (`tests/n8n/providerSelection.test.mjs`) that would need one new case.
2. Read `body.mode` directly inside `ENRICH_PARSE_EVENT_CLOUD`'s own wrapper body (the module
   stays untouched) — smaller diff, but breaks the "provider selection module is the one place
   that reads the envelope" convention this file otherwise follows.

Once `mode` lands on the row object emitted by `Parse HubSpot Event`, it rides through every
downstream hop for free — every intervening Code node in this chain spreads `{...row, ...}`
(confirmed for `ENRICH_BUILD_IDENTITY`, `ENRICH_GATE`, `ENRICH_NORMALIZE_SCORE_CLOUD`,
`ENRICH_MERGE`) — which is exactly the row-carry discipline `tests/test_row_carry.py` exists to
enforce structurally. No new "carry mode explicitly" plumbing is needed beyond the initial
extraction; the existing spread pattern already threads it to `Decide Action`.

### D.2 — `IF Provider Processing Needed` still gates on `action` from `Enrichment Gate`, not the later `mode`-derived `"proposed"` action

The provider waterfall entry gate (`IF Provider Processing Needed`, tests
`row.action != "skip"`) reads `action` as computed by `Enrichment Gate`
(`create`/`enrich`/`skip`) — this happens **before** `Decide Action` (which is where CONTEXT.md's
`"proposed"` action gets set, downstream of the whole waterfall). This confirms decision 1's
"runs the waterfall" half is structurally correct as designed: a propose-mode row that would
otherwise be `create` or `enrich` still enters the provider chain and burns credits exactly as a
normal request would; `mode` only changes what `Decide Action` does with the *result* (return
instead of write). No route needs adding to bypass the waterfall for propose mode — the existing
`create`/`enrich`/`skip` gate is unaffected by `mode`.

### D.3 — Pytest discovery has no config file

`[VERIFIED: no pytest.ini / pyproject.toml / setup.cfg / conftest.py at repo root]` — pytest
relies on its default `test_*.py` discovery under `tests/` (and separately under
`operator-claude-plugin/tests/`, run independently per CONTEXT.md §11's two pytest invocations).

## Common Pitfalls (specific to this phase, verified this session)

### Pitfall 1: Converting `Skip (NoOp)`/`Unsupported Object Type` to Code nodes without updating the waiver list
**What goes wrong:** `tests/test_row_carry.py::test_every_row_replacing_entry_is_still_a_real_node_somewhere`
fails because the waiver dict names two node names that no longer exist as `n8n-nodes-base.set`.
**How to avoid:** Remove both entries from `ROW_REPLACING_BY_DESIGN` in the same commit that
converts the node types (§A4).

### Pitfall 2: Threading `mode` through the wrong layer
**What goes wrong:** Putting `mode` handling only inside the per-event spread in
`ENRICH_PARSE_EVENT_CLOUD`'s wrapper (rather than in `parseWebhookBody`) works for the documented
wire contract but silently diverges from where `providers` — the one other envelope-level field
this webhook already supports — is read, making the two fields inconsistent for a future reader.
**How to avoid:** Prefer extending `parseWebhookBody()` (§D.1 option 1) unless there's a reason
not to; either way, add a `tests/n8n/providerSelection.test.mjs` case for the `mode` extraction
regardless of which option is chosen, since that file is the module's existing test home.

### Pitfall 3: Assuming the companies branch needs the same match lane
**What goes wrong:** `test_fetch_by_id_topology.py` parametrizes over `["contacts",
"companies"]` for the pinned `IF Bare Event`-equivalent test (§A7). CONTEXT.md's wire contract
and build plan describe contacts only. Blindly amending both parametrized cases assumes
companies needs the identical treatment, which was not verified this session.
**How to avoid:** Planner should explicitly scope §7 step 3 (match lane) and step 5 (Code-node
conversion) to contacts only unless a companies mirror is separately decided, and should read the
companies branch's `IF Bare Event` analog before touching its pinned test case (see §F Open
Questions).

### Pitfall 4: Believing `HubSpot Search by Email`'s fix touches the same builder region as steps 1-9
**What goes wrong:** Finding B's fix is in the **contact-ingest cloud builder**
(`scripts/build_cloud_workflows.py:640-649`, near line 656's `_write_safety_const` call for that
lane), a physically distant region of the same file from `ENRICH_*` constants (which start around
line 914 and run through line ~5900). A plan that groups all nine build-plan steps as touching
"one region" of the builder will misjudge diff locality.
**How to avoid:** Treat Finding B (step 9) as an independently-scoped, independently-shippable
task against a different function than steps 1-8, exactly as CONTEXT.md §13 already says
("Nothing before step 4 changes any existing caller's behaviour" — and step 9 changes a different
workflow's caller entirely).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python, repo root `tests/` + `operator-claude-plugin/tests/`) and Node's built-in `node:test` (`tests/n8n/*.test.mjs`) |
| Config file | none — default discovery, confirmed no `pytest.ini`/`pyproject.toml`/`setup.cfg`/`conftest.py` at repo root |
| Quick run command | `.venv/bin/python -m pytest tests/test_row_carry.py tests/test_fetch_by_id_topology.py -q` (targeted, per touched file) |
| Full suite command | `.venv/bin/python -m pytest -q` (repo, 1933 passed/6 skipped baseline) · `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (plugin, 1052/5 baseline — unaffected by this backend-only phase, run for regression safety only) · `node --test tests/n8n/*.test.mjs` (553 baseline, FILE glob only — directory form broken on node 24) |

### Phase Requirements → Test Map

| Behavior (from CONTEXT.md §8 Definition of Done, 9 items — no separate ROADMAP-level list exists for this phase) | Test Type | Automated Command | File Exists? |
|---|---|---|---|
| 1. `mode:"propose"` returns `properties`+`match`, `row_id` echoed, writes nothing regardless of `WRITE_SAFETY_DEFAULTS` | unit (structural, Decide Action jsCode) | `.venv/bin/python -m pytest tests/test_cloud_write_path.py -q` (extend) | ✅ extend existing |
| 2. `mode` absent behaves byte-identically to today | unit (regression, existing pinned tests) | `.venv/bin/python -m pytest -q` (full suite, no new test needed — an existing-behavior regression is proven by the *absence* of new failures) | ✅ covered by existing suite |
| 3. Mixed-lane batch emits each row exactly once | unit (structural, `lane` filter logic in Adapt Search/Fetch By Id) | new test in `tests/test_provider_gate_topology.py` or a new `tests/test_enrichment_lane_dedup.py` | ❌ Wave 0 — new assertion needed |
| 4. `CONTAINS_TOKEN` hit on wrong surname yields zero candidates | unit (pure function, `matchProposal.js`'s `mediumCandidates`) | `node --test tests/n8n/matchProposal.test.mjs` | ❌ Wave 0 — new file needed (§B.1) |
| 5. Oversize `events` array refused whole, nothing enriched | unit (structural + pure function) | `node --test tests/n8n/providerSelection.test.mjs` (extend, mirrors `listExpansion.test.mjs`'s oversize-refusal tests) | ✅ extend existing (or new module test if refusal logic moves to its own module) |
| 6. Emailless INGEST row no longer sets `lookup_failed`; siblings keep `create` | unit (structural, ingest lane) | `.venv/bin/python -m pytest tests/test_ingest_search_contract.py -q` (extend) | ✅ extend existing |
| 7. `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0 | smoke (shell grep, no framework) | `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | ✅ existing repo-wide invariant, re-run as-is |
| 8. Suites green against §1's baselines (~+30 node, ~+15 pytest) | full suite | all three commands above | ✅ existing suites, count delta is the acceptance signal |
| 9. Rebuilt, deployed disarmed, every active workflow bounced, read back `--expectation disarmed` | **live/manual — backstop only** | `verify_live_write_safety.py --expectation disarmed` (per 23-06 Finding 1's discovery-based version) — **cannot run from the agent**, `scripts/deploy_n8n_workflows.py` is denied to agents in every form (CLAUDE.md constraint, confirmed by this phase's own instructions) | N/A — human-executed via `!` |

### Sampling Rate
- **Per task commit:** targeted file re-run (`.venv/bin/python -m pytest <touched_test_file> -q`
  and/or `node --test tests/n8n/<touched>.test.mjs`)
- **Per wave merge:** `.venv/bin/python -m pytest -q` (repo) + `node --test tests/n8n/*.test.mjs`
- **Phase gate:** all three suites green (repo pytest, plugin pytest, node) + arming grep `0`
  before the human-executed disarmed deploy/bounce/read-back (criterion 9)

### Wave 0 Gaps
- [ ] `tests/n8n/matchProposal.test.mjs` — new file, covers criterion 4 (and `laneOf`/
      `summarizeMatch` unit coverage generally)
- [ ] A new or extended test asserting mixed-lane emit-once behavior — covers criterion 3
- [ ] `tests/n8n/providerSelection.test.mjs` extension for the `mode` envelope field and the
      events-array-size refusal — covers criterion 5 and D.1's `mode`-threading mechanism
- [ ] `tests/test_row_carry.py` edit (remove two waiver entries) — not a new test, but a required
      edit alongside the Code-node conversion or `test_every_row_replacing_entry_is_still_a_real_node_somewhere`
      fails (§A4 Pitfall 1)
- [ ] `tests/test_fetch_by_id_topology.py` amendment for the re-pointed `IF Bare Event` false
      lane — required per §A7, scope to `contacts` only pending §F's open question

*(Framework itself is fully present — pytest and `node:test` are both already the repo's tooling;
no framework install needed.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | Indirect | The `hubspot/enrichment/event` webhook already requires native n8n Header Auth (`X-Enrichment-Secret`) bound via `NODE_CREDENTIAL_MAP` — unchanged by this phase, no new endpoint |
| V4 Access Control | Yes | Write-safety gate (`_writeSafetyAllows`) must never be reachable on the propose path — this is decision 1's whole point; the plan must verify (not just assert) that no `ALLOW_*` constant is read on the propose branch, matching CONTEXT.md's own claim "the arming grep stays 0" |
| V5 Input Validation | Yes | `mediumCandidates`'s value re-verification (§7 step 1) is the input-validation control preventing a fuzzy `CONTAINS_TOKEN` server-side filter from becoming an over-trusted match; the `events`-array size refusal is itself an input-validation control against oversized/DoS-shaped requests |
| V1 Architecture | Yes | Non-clobber merge policy (existing, unchanged) still governs anything this phase's waterfall discovers — propose mode reuses the same merge/scoring path, never a parallel one |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Feature depends on a currently-false global flag as its safety property | Elevation of Privilege | Decision 1 explicitly rejects reading `write_blocked` as the propose signal, for exactly this reason — a future arming of `ALLOW_HUBSPOT_CREATE` for an unrelated reason must not silently start writing propose-mode rows |
| Search-filter fuzzy match treated as ground truth | Tampering / Spoofing (of match confidence) | `mediumCandidates`'s by-value re-verification (case-insensitive lastname equality AND company token overlap) — never trust that the HubSpot search already filtered correctly (the BUG 22b lesson this repo learned live, cited explicitly in CONTEXT.md §7 step 1) |
| Unbounded batch size as a resource-exhaustion vector | Denial of Service | The `events`-array refusal, mirroring the existing list-lane's oversize refusal — refuse whole rather than truncate, so a malformed/huge request cannot silently partially process and report success |
| Unmapped credential-bound node deploys unbound | Information Disclosure (401 leak) / Spoofing | `NODE_CREDENTIAL_MAP` entry for the new `HubSpot Name Search` node — this repo's own history names this exact failure mode 4 times |

## Package Legitimacy Audit

**Not applicable.** This phase introduces no new npm/PyPI/crates dependency — it is entirely new
Python-generated JS inside the existing `n8n/code/*.js` module set and existing `n8n-nodes-base.*`
node types already used throughout `wf_enrichment_cloud.json`. No `npm install`/`pip install` step
exists in CONTEXT.md's build plan, and none was found necessary during this verification pass.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| `.venv/bin/python` + repo's pytest deps | Running `.venv/bin/python -m pytest -q` | ✓ (confirmed: `1939 tests collected` this session) | — | — |
| Node.js (for `node --test`) | `node --test tests/n8n/*.test.mjs` | Assumed ✓ (baseline count 553 quoted by CONTEXT.md; not re-run this session to save time, no reason to doubt it given pytest matched exactly) | — | — |
| n8n Cloud tenant / deploy credentials | Criterion 9 (disarmed deploy + bounce + read-back) | Not checked this session — **not applicable to the agent regardless**: `scripts/deploy_n8n_workflows.py` is denied to agents in every form (project constraint, CLAUDE.md-adjacent instruction repeated in this phase's own task framing) | — | Operator runs the deploy via `!`, per every prior phase's established pattern (23-06, 28-02, etc.) |

**Missing dependencies with no fallback:** none — everything needed to build and unit-test this
phase is already present in the repo.

**Missing dependencies with fallback:** the live deploy/bounce step (criterion 9) has no agent
fallback by design (project constraint, not a gap) — the fallback is the existing
human-executes-via-`!` pattern this repo has used for every prior phase's armed/deploy step.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | "HubSpot CRM v3 has no `CONTAINS` operator and a bare one is a guaranteed 400" | §B.2 | If wrong, using plain `CONTAINS` instead of `CONTAINS_TOKEN` would still work fine (no risk of breakage) or the reverse — `CONTAINS_TOKEN` itself might not be the operator name HubSpot expects, which would 400 the search node at runtime; low likelihood (this is well-documented, widely-used HubSpot API behavior) but the planner should treat CONTEXT.md's live-proof caveat (§12 Risk 4-adjacent) as applying here too — a canary run against the real tenant is the confirming step, matching the pattern this repo already uses for provider-body shapes |
| A2 | No HubSpot private-app webhook subscription posts to `hubspot/enrichment/event` with a multi-element `events` array | §A8 | If wrong, the new batch-size refusal could reject a legitimate HubSpot-native webhook delivery (HubSpot batches up to 100 events per POST natively). CLAUDE.md §20.2's documented subscription list (2 property-change subscriptions) suggests low likelihood, but this repo's own webhook subscription config was not re-read live from the HubSpot private-app config this session — only the static doc |
| A3 | `node --test tests/n8n/*.test.mjs` still reports 553 passing (not independently re-run this session) | Environment Availability | Low risk — pytest's collection count matched CONTEXT.md's stated baseline exactly (1939 = 1933+6), giving high confidence the repo state matches CONTEXT.md's snapshot generally; if wrong, the planner's Wave 0 diff count expectation (~+30 node) would be off by whatever the true baseline is |

## Open Questions

1. **Does the companies branch need an equivalent match lane / propose-mode handling in this phase?**
   - What we know: `36-CONTEXT.md`'s wire contract, build plan (§7), and definition of done (§8)
     describe contacts only. `ENRICH_DECIDE_CO_CLOUD` would still need the same `mode`/
     `"proposed"` guard per CONTEXT.md's own step 4 text ("a propose envelope with
     `objectType:"company"` must not write either") — so companies DOES get the write-safety
     guard, but not necessarily the match lane (email/lastname+company search) itself.
   - What's unclear: whether `tests/test_fetch_by_id_topology.py`'s `["contacts", "companies"]`
     parametrization of the pinned `IF Bare Event`-equivalent test needs amending for both
     branches or contacts only — the companies branch's exact `IF Bare Event` analog node name
     and its current false-lane target were not read this session.
   - Recommendation: planner should explicitly scope the match-lane build (§7 step 3) to
     contacts, and separately confirm the companies branch's propose-mode write-guard (step 4)
     covers `ENRICH_DECIDE_CO_CLOUD` without touching that branch's search topology — read the
     companies-branch `IF Bare Event` equivalent before deciding whether to amend its
     parametrized pinned test case.

2. **Should the `events`-array refusal live inside `ENRICH_PARSE_EVENT_CLOUD` itself, or as a new preceding node (mirroring `Expand List To Events`'s separate-node pattern)?**
   - What we know: the list-resolution refusal lives in its own dedicated node
     (`Expand List To Events`) upstream of `Parse HubSpot Event`, because that node needs to
     terminate BEFORE `Parse HubSpot Event`'s "no `events` array → treat as one bare event"
     fallback would otherwise mask a refusal as a silent no-op (`scripts/build_cloud_workflows.py`
     comment at lines 3346-3349).
   - What's unclear: whether the same masking risk applies to an *oversized* `events` array (it
     does have an `events` array, just too large one) — `Parse HubSpot Event`'s existing fallback
     logic (`Array.isArray(body) ? body : (body.events ? body.events : [body])`) does not silently
     collapse a too-large array the way it collapses a missing one, so the refusal check may be
     safe to add directly inside `ENRICH_PARSE_EVENT_CLOUD`'s own wrapper without the separate-node
     pattern `Expand List To Events` needed.
   - Recommendation: a plan task should read `ENRICH_PARSE_EVENT_CLOUD`'s full wrapper once more
     immediately before implementing, decide in-node vs. separate-node based on whether the
     refusal needs to happen before or after `mode`/`providers` extraction, and document the
     choice inline (this repo's established practice per every comment block read this session).

## Sources

### Primary (HIGH confidence — read this session, this repo)
- `scripts/build_cloud_workflows.py` — the Python workflow builder, all `ENRICH_*` constants and
  node-build call sites cited above
- `scripts/deploy_n8n_workflows.py` — `NODE_CREDENTIAL_MAP`
- `n8n/code/lushaRequest.js`, `n8n/code/listExpansion.js`, `n8n/code/providerSelection.js` —
  pure-JS module conventions and the refusal-shape precedent
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` — committed generated
  artifacts, read directly for connection-graph and node-parameter ground truth
- `tests/test_row_carry.py`, `tests/test_fetch_by_id_topology.py`, `tests/test_ingest_search_contract.py`,
  `tests/n8n/lushaRequestContract.test.mjs`, `tests/n8n/listExpansion.test.mjs` — existing pinned
  tests read for exact assertion text
- `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-CONTEXT.md` — the
  phase's locked decision record (this document verifies, does not re-derive, its claims)
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md`, `STATE.md` — milestone/phase context

### Secondary (MEDIUM confidence)
- HubSpot CRM v3 Search API's `CONTAINS_TOKEN` operator name — standard, well-documented platform
  behavior, not independently confirmed against HubSpot's own docs or a live probe this session
  (tagged `[ASSUMED]`, Assumption A1)

### Tertiary (LOW confidence)
- None used for factual claims in this document beyond the two items in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- CONTEXT.md claim verification (§A): HIGH — every named symbol/test/node was read directly this
  session with file:line citations
- Gap-fill (§B, §D): HIGH for module conventions and test inventory (read directly); MEDIUM for
  the `CONTAINS_TOKEN` operator name specifically (platform knowledge, not this-session-verified)
- Validation architecture: HIGH for the offline/structural half (existing framework, existing
  files); explicitly backstop-only for criterion 9 (live deploy), consistent with this repo's
  established agent/human split

**Research date:** 2026-08-05
**Valid until:** Effectively permanent for the file:line citations (source-controlled, will only
go stale if the cited files are edited before this phase's plan executes — re-verify any citation
whose surrounding code has changed since this date before trusting it blindly). The `[ASSUMED]`
HubSpot operator-name claim should be confirmed live during the phase's own execution (CONTEXT.md
§12 Risk 4 already anticipates a first-live-run proof for the adjacent Lusha widening; extend that
same live-proof step to cover the `CONTAINS_TOKEN` operator).
