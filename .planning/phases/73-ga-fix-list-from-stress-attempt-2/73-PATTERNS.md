# Phase 73: GA fix list from stress attempt 2 - Pattern Map

**Mapped:** 2026-09-15
**Files analyzed:** 9 (across builder/JS/plugin/tests)
**Analogs found:** 9 / 9 (all within-repo; RESEARCH.md already pinpointed exact line numbers)

Note: RESEARCH.md for this phase already did exhaustive precedent-hunting with file:line
citations. This file packages those into planner-consumable pattern assignments; excerpts
below are re-verified against the current tree, not re-derived.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog (same file, different site) | Match Quality |
|---|---|---|---|---|
| `scripts/build_cloud_workflows.py` (`_hs_http_create_node` "HubSpot Create" call, ingest lane) | config/graph-builder | event-driven (webhook→write) | `wire_gate_refusal_lane` + `splice_carry_merge_after` (existing refusal-lane idiom) | role-match (structurally different — see Pitfall 0) |
| `scripts/build_cloud_workflows.py` (`ENRICH_BUILD_CO_IDENTITY`, companies search body) | transform/config | request-response | `n8n/code/columnMap.js` linkedin_url_variants + IN-filter search node (lines ~2083, ~6818) | exact |
| `scripts/build_cloud_workflows.py` (`CO_LINK_DOMAIN_SEARCH_BODY`, ingest lane) | config | request-response | same IN-filter pattern + `BUILD_COMPANY_LINK`'s `.invalid` sentinel | exact |
| `scripts/build_cloud_workflows.py` (`ENRICH_DECIDE_CO_CLOUD`, freemail check) | controller/decision | CRUD | `n8n/code/companyLink.js::FREEMAIL_DOMAINS`/`NOT_A_COMPANY_DOMAIN` refusal pattern | role-match |
| `scripts/build_cloud_workflows.py` (`_INGEST_SEARCH_BATCH_INTERVAL_MS`) | config constant | batch | itself (one-line value change) | exact |
| `n8n/code/reviewApply.js` | service (pure fn) | transform | its own existing `canonicalPatch[d.field] = ...` assignment; sibling choke points in `ENRICH_DECIDE_CO_CLOUD`/`ENRICH_DECIDE_CLOUD` (`Array.isArray(...).join(";")`) | exact (same fix shape, different file) |
| `tests/n8n/lib/walkWorkflow.mjs` (`runNode` HTTP_TYPES branch) | test utility | event-driven | its own `n8n-nodes-base.if` two-output branch (lines ~280-287) | exact |
| `operator-claude-plugin/scripts/extraction.py` / `preingest.py` / `preview.py` (contact-upload dedupe) | utility/transform | batch | `extraction.py::_first_satisfied_key`/`_group_presence`/`_casefold_trim` (clustering primitives, reused not `dedupe()` itself) | role-match (semantics differ — see Pitfall 3) |
| `operator-claude-plugin/scripts/run_report.py` | reporting/transform | batch | `_identity_for_entry` (already implements D-73-11's join rule) | exact — likely no code change, fixture-driven diagnosis |
| `operator-claude-plugin/scripts/run_manifest.py` call site in `enrich-before-ingest/SKILL.md` | config/glue | CRUD | `run_manifest.py`'s own `run_manifest_path(run_id)`/`load_scoped` (already-shipped API, wrong arg at call site) | exact |
| `operator-claude-plugin/scripts/write_grant.py` / `cost_guard.py` | service | CRUD | `preview_enrichment.zero_cost_estimate` / `preview.tabular_cost_block` (already-correct sibling estimator for the same lane) | exact |
| `operator-claude-plugin/scripts/backend_status.py` / builder's `build_backend_status_cloud` | diagnostic | request-response | enrichment lane's own credit-probe branch (`ENRICH_STATUS_CREDIT_REQUEST`/`_credit_http_node`, same probe code, working there) | exact |

## Pattern Assignments

### F-A6 — `scripts/build_cloud_workflows.py`, ingest `HubSpot Create` (controller/graph, event-driven)

**Analog:** `wire_gate_refusal_lane` / `splice_carry_merge_after` (same file, lines ~9862-9911,
~10011-10102) — closest existing idiom, but NOT a drop-in (Pitfall 0: `combineByPosition`
breaks under a shrinking success-output array).

**Current call site to change** (`scripts/build_cloud_workflows.py:1474`, `_hs_http_create_node`):
```python
def _hs_http_create_node(name, resource, x, y):
    if resource not in ("contacts", "companies"):
        raise ValueError(f"_hs_http_create_node only supports contacts/companies — got resource={resource!r}")
    url = "https://api.hubapi.com/crm/v3/objects/" + resource
    body = "={{ JSON.stringify({ properties: $json.properties }) }}"
    return _http_node(
        name, url, x, y,
        auth="hubspot", json_body=body, method="POST", on_error=None,   # <-- D-73-01 changes this, ingest "HubSpot Create" call only
    )
```
`_http_node`'s `on_error` param already passes through to the node's `onError` field verbatim
— no change needed there.

**Current wiring that must change** (`scripts/build_cloud_workflows.py:1596-1599`):
```python
for write_node in ("HubSpot Update", "HubSpot Create"):
    conns[write_node] = {"main": [
        [{"node": "Build Association Request", "type": "main", "index": 0}]
    ]}
```
Adding `onError` without wiring `main[1]` drops the error branch silently.

**Carry-merge idiom to copy the SHAPE of (not the semantics)**:
```python
# Source: scripts/build_cloud_workflows.py:1668-1671
splice_carry_merge_after(nodes, conns, "HubSpot Create", "HubSpot Create Write Gate IF",
                         merge_name="Create Carry Merge")
```

**Root-cause fix direction (per Pitfall 0, HIGH-signal, not yet proven live):** switch
`Create Carry Merge` from `combineByPosition` to Merge v3.2 "combine by matching fields" on
`email` (confirmed present both on the create request body via BUG-19's seeding and on
HubSpot's echoed response, `scripts/build_cloud_workflows.py:4665-4666`). Do NOT attempt a
by-name `$('previous node').item` read (Phase 70 D-70-03/04 retired this pattern lane-wide).

**Error handling pattern:** new error-output item → refusal-row Code node → own
carry-merge/sentinel input → `Ingest Merge Response` → `Build Ingest Response`. Defensive
parsing only (`item.json.error?.message`, fallback `JSON.stringify`) — exact error-item shape
is `[ASSUMED]`, confirm against first live disarmed send.

**Walker gap (Pitfall 2):** `tests/n8n/lib/walkWorkflow.mjs` `runNode()` HTTP_TYPES branch
currently:
```javascript
if (HTTP_TYPES.has(type)) {
    const stub = (ctx.httpStubs || {})[node.name];
    if (stub === undefined) { throw new Error(`unstubbed HTTP node: ${node.name}`); }
    const raw = typeof stub === "function" ? stub(items, node) : stub;
    return { outputs: [(raw || []).map(unwrapJson)] };   // <-- always ONE output
}
```
Compare to the two-output `if`-node branch immediately above it (lines ~280-287) — mirror
that shape: add a second `outputs[1]` array when the node's `onError === "continueErrorOutput"`
and the stub is shaped `{success, error}`.

---

### F-B7 — domain IN-variant search (`scripts/build_cloud_workflows.py`, request-response)

**Analog — exact precedent already in this file**, `linkedin_url_variants` (line ~2083 compute
site, line ~6818-6821 IN-filter search node):
```python
# compute upstream
linkedin_url_variants: linkedinUrlVariants(row.linkedin_url),

# IN filter over that variant field
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
```
Apply identically: `ENRICH_BUILD_CO_IDENTITY` gets `domain_variants: [domain, domain ?
"www." + domain : null].filter(Boolean)`; the companies-branch search node (built via
`_hs_http_search_node`, NOT `HS_CO_SEARCH_BODY_EXPR` — that constant belongs to
`build_enrichment_local_live()` only, single call site) changes `operator: "EQ"` → `IN` over
`domain_variants`. Same pair for ingest's `CO_LINK_DOMAIN_SEARCH_BODY`.

**Empty-array guard (folded F-B4, D-73-22) — analog is the ingest lane's own sentinel**:
```python
# Source: scripts/build_cloud_workflows.py:610 (BUILD_COMPANY_LINK)
company_search_domain: companyDomainForRow(row) || "no-company-domain.invalid",
```
Mirror: when `domain` is null, `domain_variants` must be `["no-company-domain.invalid"]`,
never `[]` (HubSpot 400s on empty `values`).

---

### F-B3 — freemail refusal (`scripts/build_cloud_workflows.py` `ENRICH_DECIDE_CO_CLOUD`, CRUD)

**Analog — authoritative set already exists and is exported**, `n8n/code/companyLink.js:25-33`:
```javascript
const FREEMAIL_DOMAINS = new Set([
  "gmail.com", "googlemail.com", "outlook.com", "outlook.com.au", "hotmail.com",
  "hotmail.com.au", "live.com", "live.com.au", "msn.com", "yahoo.com", "yahoo.com.au",
  "ymail.com", "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com", "proton.me",
  "gmx.com", "mail.com", "zoho.com",
  "bigpond.com", "bigpond.net.au", "bigpond.com.au", "optusnet.com.au", "iinet.net.au",
  "tpg.com.au", "internode.on.net", "westnet.com.au", "dodo.com.au", "iprimus.com.au",
  "exemail.com.au", "ozemail.com.au",
]);
```
`Decide Company Action` does not `inline()` this module today — inline just the constant
(companion functions `companyDomainForRow`/`emailDomain` are ingest-lane-specific and make no
sense here). Refusal reason string per D-73-09: `"freemail domain — supply the real
website"`, review outcome (never skip, never create).

---

### F-E1 — array serialization (`n8n/code/reviewApply.js`, transform)

**Root-cause site** (current file, `n8n/code/reviewApply.js` header + body) — the ACTUAL
choke point per Pitfall 1, not the two decoy sites at `ENRICH_DECIDE_CLOUD`/`ENRICH_DECIDE_CO_CLOUD`
(~lines 2582/4610) which never run on the review-approve path:
```javascript
const { DEFAULT_COMPANY_POLICY } = require("./mergeCompanies");
const { normalizeEnumValue } = require("./hubspotEnums");

function reviewApply(candidateJson, refetchedProperties, fieldPolicy) {
  ...
  const allowedFields = Object.keys(policy);
  const canonicalPatch = {};
  const staleFields = [];
  // ... canonicalPatch[d.field] = enumCheck.value  <-- add array.join(";") here
```

**Existing choke point to mirror the SHAPE of** (do not duplicate, D-73-10 mechanical reuse):
```python
# ENRICH_DECIDE_CO_CLOUD / ENRICH_DECIDE_CLOUD, scripts/build_cloud_workflows.py ~2582/~4610
if (Array.isArray(properties[k])) properties[k] = properties[k].join(";");
```
One-line fix inside `reviewApply()`'s `canonicalPatch[d.field] = ...` assignment fixes both
consumers (operator-triggered endpoint + scheduled `Apply Review` backstop) automatically.

**Test analog:** `tests/n8n/reviewLoop.test.mjs` exists, has zero array-valued-candidate
coverage today (confirmed by grep) — extend with an array fixture.

---

### F-A5 — CSV dedupe (`operator-claude-plugin/scripts/extraction.py`/`preingest.py`/`preview.py`)

**Analog — primitives to reuse, NOT the whole function** (Pitfall 3: `dedupe()` field-merges
and conflicts; D-73-04 wants first-wins verbatim + `duplicate_in_csv` tag — incompatible
semantics from the same clustering input):
```python
# extraction.py — REUSE these (module-level, importable):
_first_satisfied_key(...)   # identity-group key selection
_group_presence(...)        # cluster grouping
_casefold_trim(...)         # exact/casefolded/trimmed equality (no fuzzy matching anywhere
                             # in this codebase — deliberate, per 24-RESEARCH.md Pitfall 5)
```
Do NOT reuse `_merge_cluster`/`dedupe()` itself — write a new pass: group via the primitives
above, keep first index per cluster verbatim, tag losers `duplicate_in_csv` naming the
winner's row id.

**Integration point — new code path, not an extension** (plain `contact-upload` skill has NO
identity/dedup logic today; confirmed by reading `preview.py` end to end, no `extraction`
import). Mirror the established "corrected file, path forwarded" idiom already used by
`name_split.py --apply` / `header_suggest.py --confirm`: write a `deduped_path` CSV, that path
becomes what `dispatch.py` sends (`dispatch.py:104`, currently
`tabular.to_csv_bytes(file_path)`).

**Scope guard (Open Question 4, resolved by RESEARCH):** scope to plain `contact-upload`
only. `enrich-before-ingest` mints its own positional `row_id` (`preingest.build_rows_spec`)
and tracks `total_row_ids` — do not touch that flow this phase (D-73-21).

---

### D-73-14 — run_manifest scoping (`operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`)

**One wrong argument at an existing call site** — `run_manifest.py` already ships both APIs:
```python
# SKILL.md:844 — already correct (writes scoped)
run_manifest.save(run_id, verdicts, path=run_manifest.run_manifest_path(run_id))

# SKILL.md:801 — WRONG, reads the unscoped shared file
verdicts = run_manifest.load()
```
Fix: `run_manifest.load(path=run_manifest.run_manifest_path(run_id))`. Do NOT touch
`chunking.py::merge_chunk_verdicts`'s own default (deliberately shared, for crash-resume).

---

### Cost envelope (F-A1/A2/B1) — `operator-claude-plugin/scripts/write_grant.py` / `cost_guard.py`

**Analog — the already-correct sibling estimator for the same lane**, `preview.py`:
```python
# preview_enrichment.zero_cost_estimate / preview.py::tabular_cost_block()
# already prices plain contact-upload at zero provider cost correctly
```
Gap is in `plan_grant`/`envelope()` (`write_grant.py:962-1130`) — already receives a `label`
string but never branches on it. Add a real `lane` parameter: `contact-upload` → zero-provider/
one-execution (reuse `zero_cost_estimate`); `companies` → `lusha_companies_match` rate
(`cost_guard.py::PROVIDER_RATE_KEYS`, lines 51-56, already distinguishes by `object_type` —
confirm it reaches `estimate_batch` un-overridden).

---

### F-B6 — backend status (`operator-claude-plugin/scripts/backend_status.py` / builder)

**Analog — same probe code, working correctly on a sibling lane**: the enrichment lane's own
credit branch (`build_enrichment_cloud()`, `ENRICH_STATUS_CREDIT_REQUEST`/`_credit_http_node`)
reads Lusha/ZoomInfo balances correctly in the same stress session. `build_backend_status_cloud()`
already has "Lusha Usage"/"Apollo Usage"/ZoomInfo probe nodes fully wired — **do not add new
nodes**. First step is diagnostic: read one live disarmed status POST's runData to localize
wiring vs. deploy-parity gap before writing any fix.

## Shared Patterns

### Never hand-wire a new Merge input
**Source:** `splice_carry_merge_after` / `_append_merge_input` / `wire_gate_refusal_lane` /
`_add_starved_lane_sentinel` (`scripts/build_cloud_workflows.py`)
**Apply to:** F-A6's new error-output lane (with the Pitfall 0 caveat that the idiom's
*shape* applies but its `combineByPosition` semantics do not — needs field-matching instead).

### Regenerate, never hand-edit `n8n/wf_*.json`
**Source:** repo-wide standing rule, confirmed zero-diff regen at HEAD this session.
**Apply to:** every builder change in this phase.

### FREEMAIL_DOMAINS / NOT_A_COMPANY_DOMAIN single source of truth
**Source:** `n8n/code/companyLink.js:25-33` (JS authoritative), Python mirror + existing
parity test.
**Apply to:** F-B3 — inline the constant into `Decide Company Action`'s jsCode, never a second
list.

### Array→string serialization before HubSpot PATCH
**Source:** `ENRICH_DECIDE_CO_CLOUD`/`ENRICH_DECIDE_CLOUD`'s `Array.isArray(...).join(";")`.
**Apply to:** F-E1's `reviewApply()` fix (same shape, root-cause location).

## No Analog Found

None — RESEARCH.md confirmed a working precedent exists in-repo for 7 of 8 findings; F-A6 is
the sole exception and is explicitly flagged (Pitfall 0) as needing new design rather than a
copied pattern — the closest analog (`wire_gate_refusal_lane`) is documented above with its
mismatch explained rather than presented as a safe copy.

## Metadata

**Analog search scope:** `scripts/build_cloud_workflows.py`, `n8n/code/*.js`,
`operator-claude-plugin/scripts/*.py`, `tests/n8n/lib/walkWorkflow.mjs` — all read directly
this session (via 73-RESEARCH.md) and re-verified by grep/sed this pass.
**Files scanned:** 9 target files + their in-file sibling call sites (~15 code sites total)
**Pattern extraction date:** 2026-09-15
