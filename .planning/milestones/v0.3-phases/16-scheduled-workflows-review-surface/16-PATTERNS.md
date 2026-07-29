# Phase 16: n8n Cloud Deployment, Scheduled Workflows & Review Surface - Pattern Map

**Mapped:** 2026-07-23
**Files analyzed:** 12 (new + modified, per 16-RESEARCH.md's two-plan structure)
**Analogs found:** 12 / 12

No CONTEXT.md exists for this phase — file list extracted entirely from 16-RESEARCH.md's Deliverables and Validation Architecture sections.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/deploy_n8n_workflows.py` (new) | config/deploy script | batch/idempotent-diff | `scripts/sync_hubspot_properties.py` | exact (same idiom: two-key gate, dry-run default, diff-vs-fresh-GET) |
| `scripts/provision_n8n_credentials.py` (new) | config/deploy script | batch/create-if-missing | `scripts/sync_hubspot_properties.py` | exact |
| `config/hubspot_properties.yaml` (modified — add `lv_enrichment_requested`, `lv_enrichment_status`) | config | CRUD (schema) | itself, existing `lv_enrichment_needs_review`/other bool+enum entries in the same file | exact |
| `scripts/build_cloud_workflows.py::build_enrichment_cloud()` (modified — port companies branch, scheduleTrigger nodes, credential conversion) | workflow builder / route | request-response (webhook) + batch (scheduled) | `scripts/build_cloud_workflows.py::build_enrichment_local_live()` (has the full company branch already) | exact — same file, sibling function |
| ZoomInfo credential-bound HTTP node(s) in `build_enrichment_cloud()` | service adapter | request-response | `_http_node(..., auth="header")` (existing Lusha/Apollo Cloud pattern in same function) + `ENRICH_ZOOMINFO_CACHED`/`_zoom_preamble` (existing Code-node cache pattern to be split) | role-match |
| `n8n/code/dedupeSweep.js` wiring into a new scheduled workflow builder function | Code node wiring | batch/event-driven | how `ENRICH_MERGE`/other Code nodes are wired via `code_node()` + `chain()`/`fan()` in `build_cloud_workflows.py` | exact |
| `tests/n8n/sjPredicates.test.mjs` (new) | test | unit/fixture | `tests/n8n/mergeCompanies.test.mjs`, `tests/n8n/enrichmentGate.test.mjs`-style fixtures (Phase 13-15.5 offline test culture) | role-match |
| `tests/n8n/reviewLoop.test.mjs` (new) | test | unit/fixture | same as above | role-match |
| `tests/n8n/dedupeSweepWiring.test.mjs` (new) | test (graph/architecture) | static | `tests/test_architecture_guard.py` (RO-2-style graph-ancestry BFS test) | role-match |
| `tests/test_deploy_n8n_workflows.py` (new) | test | unit, mocked HTTP | `tests/test_sync_hubspot_properties.py` (existing mocking pattern for the analog script) | exact |
| `tests/test_cloud_companies_branch.py` (new) | test (architecture) | static/graph BFS | `tests/test_judge_spec.py` (RO-2 graph-ancestry precedent) + `tests/test_architecture_guard.py` | exact |
| `tests/test_architecture_guard.py` (modified — add `test_no_env_or_vars_in_cloud_workflows`) | test | static | itself (existing AR-2 host-guard tests in same file) | exact |

## Pattern Assignments

### `scripts/deploy_n8n_workflows.py` / `scripts/provision_n8n_credentials.py` (config/deploy script)

**Analog:** `scripts/sync_hubspot_properties.py` (full file read — 255 lines)

**Guard/skip idiom** (lines 50-61):
```python
def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))

def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID

def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow
```
For the n8n scripts, the equivalent gate names are already anticipated in `.env.example` per RESEARCH.md Deliverable 3: `N8N_URL`/`N8N_API_KEY` (existence check) + `DRY_RUN=false AND ALLOW_N8N_DEPLOY=true` (two-key write gate) — copy this exact three-function shape, swap the env var names.

**main() skip-to-exit-0 + dry-run banner** (lines 216-233):
```python
if not _has_credentials():
    print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this sync.")
    return 0

if not _portal_ok():
    print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
          f"({EXPECTED_PORTAL_ID}). No API call made.")
    return 1

desired = load_desired_config()
live_writes = _writes_allowed()
if not live_writes:
    print("DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND "
          "ALLOW_HUBSPOT_PROPERTY_WRITES=true to create.")
```
This is the pattern to reuse verbatim (skip if no creds → exit 0, never fail the offline suite; print a diff always; only write with both env vars true).

**Idempotent diff, matched by name not internal id** (lines 72-93, already excerpted in RESEARCH.md's Code Examples as `compute_workflow_diff`):
```python
def compute_property_diff(desired_properties: list, actual_properties: list) -> dict:
    actual_by_name = {p["name"]: p for p in actual_properties}
    create, drift = [], []
    for desired in desired_properties:
        name = desired["name"]
        actual = actual_by_name.get(name)
        if actual is None:
            create.append(desired)
            continue
        if actual.get("hubspotDefined"):
            continue
        mismatch = (...)
        if mismatch:
            drift.append({"name": name, "desired": desired, "actual": actual})
    return {"create": create, "drift": drift}
```
For `deploy_n8n_workflows.py`, RESEARCH.md Deliverable 3 already ports this shape to `compute_workflow_diff(local_workflows, live_workflows)` matching on the workflow's `name` field (not the JSON's internal `id`, since n8n assigns IDs server-side) — always re-derived from a fresh `GET /api/v1/workflows`, never local state (same "idempotent after a mid-run failure" property).

**Per-item create + confirmed-write manifest, never a batch call** (lines 188-213):
```python
for prop in prop_diff["create"]:
    status, body = _create_property_live(object_type, prop)
    if status == 201:
        manifest_entries.append({...})
        print(f"created property {object_type}/{prop['name']} (201)")
    else:
        failures.append(("property", f"{object_type}/{prop['name']}", status))
        print(f"FAILED to create property {object_type}/{prop['name']} ({status}) — "
              "not recorded in undo manifest")
...
# Post-write confirmation: re-GET and confirm every manifested name now exists.
fresh_props = {p["name"] for p in _get_live_properties(object_type)}
for entry in manifest_entries:
    if entry["kind"] == "property":
        assert entry["name"] in fresh_props, f"post-write confirmation FAILED for {entry['name']}"
```
`provision_n8n_credentials.py` should follow the credential-specific corollary RESEARCH.md Deliverable 3 already calls out: credentials are **create-if-missing only, never update-in-place** (n8n never returns secret `data` back, so there is nothing to diff against — rotation is manual delete+recreate).

**Partial-failure-is-not-success gate** (lines 243-248):
```python
if all_failures:
    print(f"\nPARTIAL FAILURE — {len(all_failures)} item(s) not created:")
    for kind, name, status in all_failures:
        print(f"  {kind} {name} (HTTP {status})")
    print("Re-run after fixing; creation is create-if-missing so successes are not repeated.")
    return 1
```
Copy directly — a partial n8n deploy/credential run must not exit 0 either.

---

### `config/hubspot_properties.yaml` — add `lv_enrichment_requested`, `lv_enrichment_status`

**Analog:** the file's own existing `lv_enrichment_needs_review` boolean entry (lines 210-217) and its sibling bools (lines 152-161, 166-175, 180-189) — all under `groupName: lv_enrichment`.

**Boolean property shape to copy** (lines 152-161):
```yaml
  - name: lv_enrichment_needs_review
    label: LV Enrichment Needs Review
    type: bool
    fieldType: booleancheckbox
    groupName: lv_enrichment
    options:
    - label: 'Yes'
      value: 'true'
      displayOrder: 0
      hidden: false
    - label: 'No'
      value: 'false'
      displayOrder: 1
      hidden: false
```
`lv_enrichment_requested` copies this exactly (bool needs explicit true/false options — STATE.md's memory note "bools need true/false options" — omitting them fails live). `lv_enrichment_status` needs an `enumeration`/`select` shape instead — copy the `lv_revenue_band` shape (lines 36-70: `type: enumeration`, `fieldType: select`, `options: [{label, value, displayOrder, hidden}, ...]`) with values `queued|running|complete|failed|needs_review` per CLAUDE.md §4.1 (already-referenced enum, not needing re-invention). Both properties are consumed by `sync_hubspot_properties.py::compute_property_diff` unchanged — no script logic changes needed, only the manifest.

---

### `scripts/build_cloud_workflows.py::build_enrichment_cloud()` — companies-branch port + credential conversion

**Analog A (topology to copy):** `build_enrichment_local_live()`, lines 1872-2005 (full company branch + `research_conns`)

**Sibling-branch node sequence** (lines 1872-1962):
```python
# --- COMPANIES branch: sibling off the same Manual Trigger, own row (y+380) ---
cy = y + 380
cx = 240 + 230
nodes.append(code_node("Emit Company Targets", ENRICH_EMIT_COMPANIES, cx, cy))
cx += 230
nodes.append(code_node("Build Company Identity", ENRICH_BUILD_CO_IDENTITY, cx, cy))
cx += 230
nodes.append(_live_http("HubSpot Company Search", cx, cy, "POST", ...))
cx += 230
nodes.append(code_node("Adapt Company Search", ENRICH_ADAPT_CO_SEARCH, cx, cy))
cx += 230
nodes.append(code_node("Company Gate", ENRICH_CO_GATE, cx, cy))
...
nodes.append(code_node("Research Trigger Gate", ENRICH_RESEARCH_GATE, cx, cy))
nodes.append(_if_bool_node("IF Research Needed", "research_needed", cx, cy))
nodes.append(code_node("Build Research Request", ENRICH_BUILD_RESEARCH_REQUEST, cx, cy - 100))
nodes.append(_live_http("Claude Web Research", cx, cy - 100, "POST", ...))
nodes.append(code_node("Validate Research Output", ENRICH_VALIDATE_RESEARCH, cx, cy - 100))
nodes.append(code_node("Judge Gate", ENRICH_JUDGE_GATE, cx, cy - 100))
nodes.append(_if_bool_node("IF Needs Judge", "needs_judge", cx, cy - 100))
nodes.append(code_node("Build Judge Request", ENRICH_BUILD_JUDGE_REQUEST, cx, cy - 200))
nodes.append(_live_http("Judge Call", cx, cy - 200, "POST", ...))
nodes.append(code_node("Apply Judge Verdict", ENRICH_APPLY_JUDGE_VERDICT, cx, cy - 200))
nodes.append(code_node("Merge Company", ENRICH_MERGE_CO, cx, cy))
nodes.append(code_node("Decide Company Action", ENRICH_DECIDE_CO_LOCAL, cx, cy))
```

**Isolated connections dict, safe to fan in without collision** (lines 1985-2005):
```python
research_conns = {
    "Research Trigger Gate": {"main": [[{"node": "IF Research Needed", "type": "main", "index": 0}]]},
    "IF Research Needed": {"main": [
        [{"node": "Build Research Request", "type": "main", "index": 0}],  # true: needs research
        [{"node": "Merge Company", "type": "main", "index": 0}],           # false: fan straight in
    ]},
    ...
    "Merge Company": {"main": [[{"node": "Decide Company Action", "type": "main", "index": 0}]]},
}
return {..., "connections": {**fan(chain(order), chain(co_order)), **research_conns}, ...}
```
Port this dict as-is into `build_enrichment_cloud()`; only the node-creation lines change (per Analog B below), the connection-graph shape does not.

**Analog B (Cloud node conversion pattern, already used for contacts in the same function):** `build_enrichment_cloud()`, lines 2050-2123

**Native HubSpot search node (no raw HTTP, no `$env`)** (lines 2066-2074):
```python
hs_search = {
    "parameters": {"resource": "contact", "operation": "search",
                   "filterGroupsUi": {"filterGroupsValues": []}, "additionalFields": {}},
    "id": nid("hs"), "name": "HubSpot Search",
    "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1, "position": [x, y],
    "onError": "continueRegularOutput",
}
```
Copy for `HubSpot Company Search` with `"resource": "company"` — this is the credential-bound replacement for `build_enrichment_local_live()`'s `_live_http(..., [{"name": "Authorization", "value": "=Bearer {{ $env.HUBSPOT_PRIVATE_APP_TOKEN }}"}], ...)`.

**Generic Header Auth credential-bound HTTP node (Lusha/Apollo/Anthropic pattern)** (lines 2018-2042, `_http_node` helper; call sites lines 2114-2124):
```python
def _http_node(name, url, x, y, auth=None, headers=None, form_body=None, json_body=None):
    params = {"method": "POST", "url": url, "options": {"timeout": 20000}}
    ...
    if auth == "header":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"})
    elif auth == "basic":
        params.update({"authentication": "genericCredentialType", "genericAuthType": "httpBasicAuth"})
    ...

# call site:
lusha = _http_node("Lusha Enrich", "https://api.lusha.com/v2/person", px, y - 80,
                   auth="header")  # credential header, e.g. api_key: <LUSHA_API_KEY>
```
Use `auth="header"` for the company-branch Lusha/Apollo/Anthropic HTTP nodes exactly as the contacts branch already does — no `$env` reference anywhere, the secret lives in the bound credential instead.

---

### `$env` → credentials / build-time constants — exact grounding

**Where `$env` is read today (secrets), `build_enrichment_local_live()` lines 1835-1839, 1848-1851, 1919-1926:**
```python
nodes.append(_live_http(
    "HubSpot Search", x, y, "POST", "https://api.hubapi.com/crm/v3/objects/contacts/search",
    [{"name": "Authorization", "value": "=Bearer {{ $env.HUBSPOT_PRIVATE_APP_TOKEN }}"},
     {"name": "Content-Type", "value": "application/json"}],
    json_body=HS_SEARCH_BODY_EXPR))
...
nodes.append(_live_http(
    "Lusha Enrich", x, y, "GET", "={{ $('Build Requests').item.json.lusha_url }}",
    [{"name": "api_key", "value": "={{ $env.LUSHA_API_KEY }}"}]))
...
nodes.append(_live_http(
    "Claude Web Research", cx, cy - 100, "POST", "https://api.anthropic.com/v1/messages",
    [{"name": "x-api-key", "value": "={{ $vars.ANTHROPIC_API_KEY || $env.ANTHROPIC_API_KEY }}"}, ...],
    json_body="={{ JSON.stringify($json.research_request_body) }}", timeout=60000))
```
Note the `$vars.X || $env.X` defensive fallback already present on the Anthropic calls — per RESEARCH.md Pitfall 1, this does **not** fix Cloud (`$vars` unlicensed on this tier); both branches must be replaced with a bound credential (`auth="header"`), matching the Lusha/Apollo Cloud pattern already proven, not patched with a third `$vars` variant.

**Where `$env` is read today (flags, build-time constants) — `_zoom_preamble` / Research/Judge Gate call sites** (grep confirms 6 flag names: `ALLOW_WEB_RESEARCH`, `MAX_WEB_RESEARCH_PER_RUN`, `ANTHROPIC_SONNET_MODEL`, `WEB_RESEARCH_MAX_SEARCHES`, `ALLOW_SONNET_ESCALATION`, `MAX_SONNET_VALIDATIONS_PER_RUN`). **Analog for the "build-time inlined constant" fix:** the existing generated-data/hand-written split (AR-4) — `n8n/code/taxonomy.generated.js` (regenerated by `scripts/gen_taxonomy_js.py`, called at the top of `build_cloud_workflows.py` before any `inline()`) vs `n8n/code/escalation.generated.js`/`judge.js` (Phase 14, same split). The flags are simpler than taxonomy/escalation (they're scalars, not vocab tables) — RESEARCH.md's recommendation is a plain Python-string-substitution inline at build time (e.g. `MAX_SONNET_VALIDATIONS_PER_RUN = 10` baked directly into the generated jsCode), not a new generated-file module — but the precedent that "nothing not already in the JSON exists at n8n Cloud runtime" (AR-4) is the same one already governing taxonomy/escalation.

---

### `n8n/code/dedupeSweep.js` wiring into a scheduled workflow

**Pure function to wire (unchanged, 79 lines, already read in full):**
```javascript
function dedupeSweep(records) {
  records = records || [];
  const duplicates = [];
  const reviewIds = new Set();
  for (const [keyType, normalizer, prop] of DUP_KEYS) { ... }
  ...
  return {
    duplicates, mangled,
    counts: { duplicates: duplicates.length, mangled: mangled.length },
    duplicate_count: duplicates.length, mangled_count: mangled.length,
    to_review_ids: toReviewIds,
  };
}
module.exports = { dedupeSweep };
```
Currently unused anywhere in `build_cloud_workflows.py` (grep confirms zero `dedupeSweep` references outside the file itself and its test). Wire it the same way every other Code node is wired: `inline("dedupeSweep.js") + r"""..."""` assigned to a new `ENRICH_DEDUPE_SWEEP` constant (mirrors `ENRICH_GATE = inline("normalizeEmail.js", "normalizePhone.js", "enrichmentGate.js") + r"""..."""`, line 687), then `code_node("Dedupe Sweep", ENRICH_DEDUPE_SWEEP, x, y)` appended to `nodes`, chained via `chain([...])` after a HubSpot search node feeding it a record batch — same shape as any other Code node insertion in this file. Sweep only classifies (CLASSIFY ONLY per its own header comment) — the scheduled workflow writes review flags downstream, never lets the sweep node itself touch HubSpot.

---

### RT-5 cache-hit skip — existing call graph (no new merge logic, per RESEARCH.md's own framing)

**`enrichmentGate.js::decideAction`** (full file, 109 lines, already read) — the load-bearing staleness check:
```javascript
const ttl = _staleAfterDays(policy, field);
if (ttl != null) {
  const verifiedAt = existingRecord[_cacheKeyName(field)];
  if (_isBlank(verifiedAt)) {
    staleFields.push(field); // present value, unknown freshness -> validate
  } else {
    const then = Date.parse(verifiedAt);
    const ageDays = Number.isNaN(then) || Number.isNaN(now) ? Infinity : (now - then) / 86400000;
    if (ageDays > ttl) staleFields.push(field);
  }
}
```
and the cache-key naming convention it depends on:
```javascript
function _cacheKeyName(field) {
  const base = String(field).replace(/^lv_/, "");
  return `lv_${base}_verified_at`;
}
```
This is already wired as `ENRICH_CO_GATE` inside `build_enrichment_local_live()` (line 1888: `nodes.append(code_node("Company Gate", ENRICH_CO_GATE, cx, cy))`) — the phase's remaining work per RESEARCH.md Deliverable 5 is (a) a new SJ-2 scheduleTrigger node feeding this same `Company Gate` node on a monthly cadence, and (b) a new direct unit test file for `decideAction` (none exists yet — only exercised indirectly via `mergeCompanies.test.mjs`-adjacent fixtures) proving the fresh/stale/never-verified three-case fixture already given in RESEARCH.md's Code Examples section. No change to `decideAction` or `mergeCompanies.js`'s `cacheKeys` stamping is indicated.

---

## Shared Patterns

### Two-key write gate (deploy/provisioning scripts)
**Source:** `scripts/sync_hubspot_properties.py::_writes_allowed()` (lines 58-61)
**Apply to:** `scripts/deploy_n8n_workflows.py`, `scripts/provision_n8n_credentials.py`
```python
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow
```
Swap the second env var for `ALLOW_N8N_DEPLOY` (already anticipated in `.env.example` per RESEARCH.md).

### No-credentials skip path (never breaks the offline suite)
**Source:** `scripts/sync_hubspot_properties.py::main()` (lines 220-222)
**Apply to:** all new deploy/credential scripts — must return 0 and print "skipped" when `N8N_API_KEY`/`N8N_URL` are absent, exactly like the HubSpot analog, so `pytest`'s full-suite run never makes a live call.

### Code-node wiring via `inline()` + `code_node()` + `chain()`/`fan()`
**Source:** `scripts/build_cloud_workflows.py` lines 67 (`inline`), 361 (`code_node`), 369 (`chain`), 377 (`fan`)
**Apply to:** every new Code node in this phase (dedupe sweep wiring, review-loop apply/clear nodes, SJ predicate epoch-millis helper node) — this is the one mechanism the whole builder file uses; no new node-construction helper should be invented.

### Credential-bound HTTP node (`auth="header"`)
**Source:** `scripts/build_cloud_workflows.py::_http_node()` (lines 2018-2042), already proven live in the contacts branch's Lusha/Apollo calls
**Apply to:** the ported companies-branch Lusha/Apollo/Anthropic HTTP calls (Judge Call, Claude Web Research, Lusha Company, Apollo Org) — same helper, same `auth="header"` argument, no new HTTP-node builder needed.

### HubSpot Search `filterGroups` OR-across-groups shape
**Source:** existing `HS_CO_SEARCH_BODY_EXPR` constant in `scripts/build_cloud_workflows.py` (single-filter-group domain lookup — grep for the name to locate)
**Apply to:** SJ-1/SJ-2/SJ-3 search bodies — RESEARCH.md Deliverable 5 and Pitfall 3 both already give the exact JSON shape (N single-filter `filterGroups` entries for OR, one multi-filter group for AND); mirror the existing constant's top-level shape (`{"filterGroups": [...]}`) rather than reinventing the envelope.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tests/n8n/sjPredicates.test.mjs` predicate-building helper (epoch-ms-180-days-ago Code node) | utility | transform | No existing Code node computes a relative epoch-millis cutoff; small enough (`Date.now() - 180*86400000`) to write inline per RESEARCH.md Deliverable 5 rather than needing an analog |
| Review-loop apply/clear scheduled-workflow nodes (§22.2) | workflow nodes | event-driven/batch | No existing "parse JSON blob, re-apply canonical patch, clear flags" node exists yet — closest partial analog is `mergeCompanies.js`'s `canonicalPatch`-shaped output (reuse the shape, not a node); RESEARCH.md explicitly flags this as new but structurally simple (Deliverable 5, item 5) |

## Metadata

**Analog search scope:** `scripts/`, `n8n/code/`, `n8n/*.json` (grepped), `config/`, `tests/` (structure only, not full read — governed by 16-RESEARCH.md's own "Wave 0 Gaps" list)
**Files scanned (full read):** `scripts/sync_hubspot_properties.py`, `n8n/code/dedupeSweep.js`, `n8n/code/enrichmentGate.js`, `config/hubspot_properties.yaml` (partial, representative entries); `scripts/build_cloud_workflows.py` (targeted sections: lines 1824-2124, plus grep for `_http_node`/`inline`/`code_node`/`chain`/`fan` definitions)
**Pattern extraction date:** 2026-07-23
