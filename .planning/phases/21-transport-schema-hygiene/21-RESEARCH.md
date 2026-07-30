# Phase 21: Transport & Schema Hygiene - Research

**Researched:** 2026-07-30
**Domain:** n8n workflow transport (HubSpot native-node search retirement) + HubSpot CRM property schema migration (text→enumeration) + field-governance policy config
**Confidence:** HIGH (transport swap, policy addition — verified directly against code) / MEDIUM-LOW (org_type schema migration — HubSpot's actual API behavior for in-place type conversion is not authoritatively documented; see Open Questions)

## Summary

This phase closes three independent debts, of very different risk profiles. The transport
swap (REQ-dedupe-transport-swap) and the policy addition (REQ-country-region-policy) are
low-risk, mechanical, fully precedented by existing code and tests — the codebase already
contains the exact fix pattern for both, applied to sibling nodes/fields. The schema
migration (REQ-orgtype-enumeration) is the one genuinely novel, higher-risk piece: this
repo has never mutated an EXISTING HubSpot property's `type`/`fieldType` in place before —
every prior "migration" (Phase 15) only ever CREATED new properties, and the current
`sync_hubspot_properties.py` explicitly reports type/fieldType/options drift but never
acts on it (`prop_diff["drift"]` is report-only). External research surfaced credible,
though non-authoritative (community-forum-sourced), signals that HubSpot blocks in-place
field-type changes on a property once it holds values or is referenced by any asset —
which is exactly `lv_org_type`'s live state. This pushes the design toward a **shadow
property + cutover** pattern rather than a literal in-place PATCH, but the requirement's
literal wording ("property migrated with existing values preserved") is ambiguous between
"same internal name, converted in place" and "same visible field, new backing property."
The plan MUST resolve this with a cheap, disposable live probe (mirroring this project's
own established Lusha-v3/ZoomInfo-GTM "probe-before-build" discipline) before writing the
real migration script, and MUST author the rollback runbook from what the probe shows —
not from assumption.

**Primary recommendation:** Do the transport swap and the policy addition first (one-line
+ one-config-entry changes respectively, both instantly testable); spend the phase's real
planning effort on a Wave-0 live-probe task for the org_type migration that empirically
answers "can HubSpot convert `type` in place on a non-empty property," and branch the
migration design (in-place PATCH vs. shadow-property-and-swap) on that answer, writing the
rollback runbook only after the answer is known.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dedupe candidate-contact search | n8n Cloud (workflow transport) | — | Pure transport-layer swap; no business logic changes, no new tier involved |
| `lv_org_type` schema (text→enumeration) | HubSpot CRM (property definition) | Pipeline code (taxonomy.py / taxonomy.generated.js / hubspot_properties.yaml) | HubSpot owns the property's storage contract; the pipeline already enforces the enum vocabulary in code (taxonomy gate) — schema is catching up to code, not the reverse |
| `lv_country_region_normalized` promotion policy | Config (`config/field_policy.yaml` / `DEFAULT_COMPANY_POLICY` in mergeCompanies.js) | Merge engine (Python `merge_policy.py` + JS `mergeCompanies.js`) | Field governance is a config-tier decision consumed identically by both merge-engine runtimes; no new code path, just a missing table entry |

## Package Legitimacy Audit

No external packages are installed or upgraded in this phase — pure internal code
(Python/JS), YAML config, and one HubSpot CRM schema change via the existing
`requests`-based scripts already vendored in the repo. Skipping the Package Legitimacy
Gate: not applicable.

## Standard Stack

No new libraries. This phase reuses exactly what's already in the repo:

| Component | Where | Purpose |
|-----------|-------|---------|
| `requests` (already a dependency) | `src/hubspot_client.py`, `scripts/sync_hubspot_properties.py` | HubSpot CRM v3 Properties API calls |
| `pyyaml` (already a dependency) | `config/*.yaml` loaders | field_policy / hubspot_properties / taxonomy config |
| n8n `httpRequest` node (built-in, not a package) | `scripts/build_cloud_workflows.py` `_hs_http_search_node` | Credential-bound raw HubSpot search transport — the BUG-10/22/23 fix mechanism |

**Installation:** none.

## Architecture Patterns

### Recommended approach per requirement

**REQ-dedupe-transport-swap — mechanical, ~1 line + 1 test update:**

`scripts/build_cloud_workflows.py` already defines `_hs_http_search_node(name, resource,
x, y, filter_groups, properties_csv, limit=100)` — the credential-bound httpRequest
replacement for the native node's search operation, used everywhere else search happens
(companies always, contacts since BUG 22/23). The ONE remaining native-search call site is:

```python
# scripts/build_cloud_workflows.py:4822 (current)
dedupe_search = _hs_search_node(
    "Dedupe Search (candidate contacts)", "contact", x3, y3,
    filter_groups=[[{"propertyName": "email", "operator": "HAS_PROPERTY"}]],
    properties_csv="hs_object_id,email,phone,lv_linkedin_url")
```

The fix is swapping the function called — same name, same args, `_hs_http_search_node`
already supports `resource="contact"` via `_HS_SEARCH_URLS`:

```python
dedupe_search = _hs_http_search_node(   # was: _hs_search_node
    "Dedupe Search (candidate contacts)", "contact", x3, y3,
    filter_groups=[[{"propertyName": "email", "operator": "HAS_PROPERTY"}]],
    properties_csv="hs_object_id,email,phone,lv_linkedin_url")
```

Downstream is **already agnostic to the swap**: `ENRICH_EXTRACT_SEARCH_ROWS` (the "Dedupe
Extract Rows" node, unconditionally the next node in the chain) already handles BOTH
shapes —

```javascript
// n8n/code — ENRICH_EXTRACT_SEARCH_ROWS, current, unmodified
const rows = Array.isArray(res.results) ? res.results : (res.properties ? [res] : []);
return rows.map((r) => ({ json: { ...(r.properties || {}), hs_object_id: r.id } }));
```

`res.results` (raw httpRequest envelope) is checked first — this is the exact same pattern
SJ-1/SJ-2 already use with `_hs_http_search_node`. **No adapter/wrapper code needs to
change.** Credential binding also needs no change: `scripts/deploy_n8n_workflows.py`'s
`NODE_CREDENTIAL_MAP` already maps `"Dedupe Search (candidate contacts)"` →
`{"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"}`, and `bind_credentials()` is
name-keyed and type-agnostic (`_node_requires_credential()` recognizes both native-hubspot
and httpRequest+predefinedCredentialType shapes) — proven by
`tests/test_deploy_credential_binding.py`'s own comment: *"BUG 22 moved contact ingest's
last native hubspot node onto httpRequest transport... the binding property under test is
unchanged."*

The `_hs_search_node` docstring in the codebase already documents this exact node as the
sole remaining call site and flags it as "a known, unfixed concern" — this phase is
closing that flagged debt, not discovering new scope.

**Test impact:** `tests/test_hubspot_native_operation_validity.py`'s
`test_the_guard_is_actually_looking_at_something()` asserts native hubspot nodes still
exist somewhere (true post-swap: SJ-1/SJ-2 "Set Requested" nodes use native
`company:update`, untouched by this phase) and that a `company` operation is present
(still true) — this test does not need changes. A new guard test analogous to
`test_no_native_hubspot_node_remains_in_enrichment_contacts_lane` /
`test_no_native_hubspot_node_remains_in_the_workflow` (both scoped to
`wf_enrichment_cloud.json`) should be added for `wf_scheduled_maintenance_cloud.json`,
asserting zero nodes with `type=="n8n-nodes-base.hubspot" AND operation=="search"` remain
— NOT a zero-native-hubspot-nodes assertion, because SJ-1/SJ-2's native `company:update`
nodes are legitimately out of this phase's scope (ROADMAP SC1 says "no native HubSpot
**search** node," not "no native HubSpot node").

---

**REQ-country-region-policy — config-only, two files, one frozen-fixture re-baseline:**

`lv_country_region_normalized` is already produced by the pipeline (Lusha company
normalizer, Claude web research — `n8n/code/normalizeProviders.js:280,408`,
`src/normalizer.py:164`) and already consumed by `icp_scoring.py` as a scoring input. It
has **no entry** in `config/field_policy.yaml`'s `companies:` block, so both merge engines
fall back to their generic default:

- Python: `src/merge_policy.py:236` — `policy = object_policy.get(field, {"class":
  "fill_blank_only", "min_confidence": 80})`
- JS: `n8n/code/mergeCompanies.js:182` — `const fieldPol = policy[field] || { class:
  "fill_blank_only", min_confidence: 80 };`

`fill_blank_only` only writes when the current canonical value is blank and never
refreshes an existing (possibly stale/wrong) value — this is the "staging-only by default"
behavior the ROADMAP names as the problem. The fix is a new entry in BOTH places (there is
**no generator/conformance test tying these two together** — unlike the taxonomy vocabulary,
which is enforced by `tests/test_taxonomy_conformance.py` + `scripts/gen_taxonomy_js.py`;
this pair is hand-mirrored and must be edited by hand in both files, matching the
`lv_revenue_band` / `lv_employee_band` sibling entries already present in both:

```yaml
# config/field_policy.yaml  companies:
lv_country_region_normalized:
  class: system_owned
  promote_to_canonical: true
  min_confidence: 70          # match lv_employee_band's threshold — same "flat firmographic,
                               # no evidence-url gate" shape; not a value with judgment risk
                               # the way org_type/produces_content are.
```

```javascript
// n8n/code/mergeCompanies.js  DEFAULT_COMPANY_POLICY
lv_country_region_normalized: { class: "system_owned", min_confidence: 70 },
```

**Test impact (load-bearing, do not skip):** `mergeCompanies.js` is one of the modules
inlined into "Merge Company," a node pinned by
`tests/test_companies_factory_frozen.py`'s byte-identity guard against
`tests/fixtures/companies_jscode_frozen.json`. **Any edit to `DEFAULT_COMPANY_POLICY` WILL
break this frozen-fixture test** — this is not hypothetical, it is exactly what happened in
the prior phase (`git log`: "test(quick-260730-fij): re-baseline frozen companies jsCode
fixture" for an unrelated Haiku model-swap). The plan must include an explicit
re-baseline step (rebuild `wf_enrichment_cloud.json` / `wf_enrichment_local_live.json` via
`scripts/build_cloud_workflows.py`, then dump the freshly-built `FROZEN_NODE_NAMES` jsCode
into `tests/fixtures/companies_jscode_frozen.json`) as its own reviewed act, per the
fixture file's own header comment ("re-baselined ONLY by an explicit, reviewed act").

`min_confidence: 70` is a judgment call with no locked user decision behind it (no
CONTEXT.md exists for this phase) — flag it to the user/planner as a discretion point, not
a fact.

---

**REQ-orgtype-enumeration — the phase's real complexity, novel migration shape:**

Current live state (confirmed via `config/hubspot_migration/baseline/portal-schema-companies-post.json`,
the Phase-15 baseline snapshot):

```json
{"name": "lv_org_type", "label": "Org Type", "type": "string", "fieldType": "text",
 "groupName": "companyinformation", "options": [], "archived": false,
 "modificationMetadata": {"archivable": true, "readOnlyDefinition": false}, "formField": true}
```

The property is NOT declared anywhere in `config/hubspot_properties.yaml` (only its
metadata sibling `lv_org_type_verified_at` is) — it predates the declarative
create-if-missing sync and was hand-created via the Phase 15 raw-API migration.
`sync_hubspot_properties.py` is **strictly additive**: `compute_property_diff()` computes
a `drift` list for type/fieldType/options mismatches but the sync function only ever
prints it — "report only, never auto-fixed" (its own docstring). **There is no existing
PATCH-an-existing-property code path anywhere in this repo.** This phase needs new code,
not a config edit.

The 9-value canonical vocabulary is already fully defined and load-bearing in
`config/taxonomy.yaml` (`org_types:` — `governing_body_league, content_producer,
broadcaster, individual_club_team, regulator, gambling_operator, hardware_vendor, other,
unknown`), matches CLAUDE.md §5.1 exactly, and is cross-checked by
`tests/test_taxonomy_conformance.py` against `icp_scoring.yaml`'s scoring keys and
`field_policy.yaml`'s evidence-gated set. Crucially: **every write of `lv_org_type` since
Phase 13 is ALREADY forced through `normalize_org_type()`/`normalize_org_type_result()`**
(`src/taxonomy.py`), which returns ONLY a canonical key or the `unknown` default — never
an out-of-vocabulary string. This means the "pipeline writes validated against the enum
options" half of REQ-orgtype-enumeration is **already true by construction in code** and
needs no new validation logic — what remains is (a) the HubSpot-side schema change itself,
and (b) an inventory pass confirming no pre-Phase-13 or manually-entered live value on a
real company record falls outside the 9-key vocabulary (a stray legacy value would 400 on
write post-migration where it previously silently succeeded as free text).

**The precedent pattern for a schema-mutating migration in this repo** (Phase 15) is:
baseline snapshot before (`snapshot_hubspot_schema.py`) → forward migration with a
confirmed-only undo manifest (`sync_hubspot_properties.py`) → typed-confirmation rollback
that ARCHIVES manifested creations (`rollback_property_migration.py`). **None of this
tooling handles reverting a TYPE CHANGE on a pre-existing property** — the rollback script
only knows how to archive things IT created. This phase's rollback mechanism is therefore
new and must be authored, not reused verbatim (though the "typed 'yes' confirmation +
dry-run-by-default + baseline diff" idiom should be repeated for consistency).

### System Architecture Diagram (org_type migration data flow)

```
config/taxonomy.yaml (org_types: 9 canonical keys)
        |
        +--> src/taxonomy.py: normalize_org_type() -----> EVERY Python write of lv_org_type
        |         (ALREADY enforces the 9-key vocabulary; unmapped -> "unknown")
        |
        +--> n8n/code/taxonomy.generated.js (generated) -> EVERY n8n Code-node write
        |         (same enforcement, JS side, via scripts/gen_taxonomy_js.py)
        |
        +--> config/hubspot_properties.yaml (MISSING lv_org_type entry today)
        |         |
        |         v
        |   scripts/sync_hubspot_properties.py (CREATE-ONLY; reports drift, never fixes)
        |
        +--> [NEW] migration script (does not exist yet)
                  |
                  v
        HubSpot CRM: PATCH /crm/v3/properties/companies/lv_org_type
                  (type: string -> enumeration; fieldType: text -> select;
                   options: the 9 canonical keys)
                  |
                  v
        Live company records currently holding a string lv_org_type value
                  (must already be one of the 9 keys, or the record's value becomes
                   an orphaned/invalid enum value post-migration — HubSpot's own
                   behavior for THIS case is the open question, see below)
```

### Recommended migration procedure (branches on the Wave-0 probe result)

1. **Inventory pass (read-only, cheap):** `GET /crm/v3/objects/companies/search` (or a
   paged `GET .../companies` sweep) requesting `lv_org_type`, collect the distinct live
   values across all company records. Cross-check every distinct value against
   `taxonomy.yaml`'s 9 keys. Any value NOT in the set is evidence of a stray write that
   bypassed `normalize_org_type()` (e.g., an early Phase pre-13 manual entry) and must be
   remediated (mapped to a canonical key, likely `unknown`) BEFORE the type conversion, or
   the conversion will either reject the whole PATCH or silently orphan those records'
   values (exact behavior unconfirmed — this is why the inventory must run first).
2. **Baseline snapshot:** extend/reuse `scripts/snapshot_hubspot_schema.py`'s pattern to
   capture `lv_org_type`'s pre-migration property definition AND the inventory from step 1
   as the rollback reference — this is the artifact `rollback_property_migration.py`-style
   tooling would diff against.
3. **Wave-0 live probe (new, small, throwaway):** on a DISPOSABLE differently-named test
   property (never `lv_org_type` itself), empirically establish:
   - (a) Does `PATCH /crm/v3/properties/companies/{name}` accept `{type: "enumeration",
     fieldType: "select", options: [...]}` on a property that already holds non-blank
     values on live records?
   - (b) If accepted, what happens to existing record values that are NOT in the new
     `options` list — rejected, preserved verbatim as an invalid/orphaned value, or
     silently blanked?
   - (c) If rejected outright (matching the community-forum signal that type changes
     require the property to be empty/unreferenced), can an archived property's exact
     internal `name` be immediately reused by a newly-created property of a different
     type — this determines whether "archive `lv_org_type` (string) then recreate
     `lv_org_type` (enumeration) then backfill from the step-1 inventory" is even viable,
     vs. needing a genuinely different internal name (`lv_org_type_v2`) with every writer
     (taxonomy.py callers, taxonomy.generated.js, field_policy.yaml key, mergeCompanies.js
     DEFAULT_COMPANY_POLICY key, icp_scoring.py `get_signal` call, hubspot_properties.yaml)
     repointed — a much larger diff.
   This probe is the single highest-leverage task in the phase: its answer determines
   which of the two migration shapes below is buildable, and the rollback runbook can only
   be written correctly once it's known.
4. **Migration script** (new, follows the Phase-15 idiom: env-gated, dry-run-by-default,
   typed-confirmation for the live mutation, manifest/log of what was done):
   - **If in-place PATCH works (probe 3a/3b positive):** one `PATCH` call converting
     `lv_org_type`'s type/fieldType/options, with the step-1 inventory as a pre-flight
     gate (refuse to run if any live value falls outside the 9 keys, until remediated).
     Rollback = a reverse `PATCH` back to `{type: "string", fieldType: "text", options:
     []}` — trivially cheap IF HubSpot allows the reverse direction too (verify this in
     the same probe).
   - **If blocked (probe 3a negative):** shadow property + cutover — add `lv_org_type` to
     `config/hubspot_properties.yaml` as `type: enumeration` under a **new** internal name
     (since the existing name is occupied by the live string property and likely can't be
     reused immediately per the archive-then-recreate uncertainty in 3c), backfill every
     company's normalized value via a batch `PATCH`, repoint every code writer/reader
     listed in 3c, keep the old string property (archived or just abandoned/read-only) as
     the free rollback path — reverting is a pure code revert, zero HubSpot-side action,
     because the old field was never touched.
5. **Rollback path documented BEFORE the migration runs** (the phase's own stated
   precondition) — write it AFTER step 3's probe, not before, since the correct rollback
   command depends entirely on which of step 4's two shapes applies.

### Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Search-node HTTP envelope (filters/properties/limit -> JSON body) | A new httpRequest body builder for the dedupe lane | `_hs_search_json_body_expr` / `_hs_http_search_node` (already exists, already used by every other search site) | Byte-identical envelope contract already proven live for `resource="contact"` (BUG 22/23 fix) |
| Org-type vocabulary validation | A new validator inside the migration script | `src/taxonomy.py normalize_org_type()` / `taxonomy.generated.js` | Already the single source of truth; the migration's inventory pass should call this to classify stray values, not re-derive the vocabulary |
| Property-migration scaffolding (env gate, dry-run default, typed confirmation, manifest) | A bespoke ad-hoc script for the org_type PATCH | The `sync_hubspot_properties.py` / `rollback_property_migration.py` idiom (portal-id guard, `_has_credentials()` skip, dry-run-by-default, manifest-driven) | Established, reviewed pattern in this exact repo; deviating invites a subtly different (and unaudited) safety gate |

**Key insight:** every piece of this phase except the org_type schema mutation itself is
already solved in the codebase — the only genuinely new engineering surface is "PATCH an
existing property's type," which this repo has never done and which HubSpot's public docs
do not clearly document either way.

## Common Pitfalls

### Pitfall 1: Assuming `sync_hubspot_properties.py` can perform the org_type migration
**What goes wrong:** Someone runs the existing sync script expecting it to convert
`lv_org_type` once a new YAML entry is added.
**Why it happens:** The script LOOKS like a general-purpose property-sync tool (it reports
drift), but `compute_property_diff()`'s `drift` list is explicitly never acted on —
by design ("report only, never auto-fixed" — the script's own comment says undo-manifest
correctness for CREATES is safety-critical, and it deliberately does not extend that
guarantee to in-place mutation).
**How to avoid:** Write a distinct migration script (or a clearly-separated new function)
for the type conversion; do not extend `sync_object_type()`'s create loop to also PATCH.
**Warning signs:** A dry-run of `sync_hubspot_properties.py` reports drift for
`lv_org_type` and nothing happens on a "live" run — that's expected, not a bug.

### Pitfall 2: Forgetting the frozen-fixture re-baseline after editing `mergeCompanies.js`
**What goes wrong:** Adding the `lv_country_region_normalized` entry to
`DEFAULT_COMPANY_POLICY` passes locally in isolation but fails
`tests/test_companies_factory_frozen.py` (byte-identity against
`tests/fixtures/companies_jscode_frozen.json`) and/or
`test_committed_wf_enrichment_cloud_json_is_current` (staleness against the committed
workflow JSON).
**Why it happens:** `inline()` concatenates the full JS source verbatim into the "Merge
Company" Code node; any text change to `mergeCompanies.js` changes that node's jsCode
byte-for-byte.
**How to avoid:** After the JS edit, rebuild both cloud workflows
(`scripts/build_cloud_workflows.py`), commit the regenerated `wf_enrichment_*.json`, and
re-baseline the frozen fixture as its own explicit, reviewed step (matches the prior
"re-baseline frozen companies jsCode fixture" commit already in this repo's history).
**Warning signs:** `test_companies_cloud_jscode_is_byte_identical_to_frozen_fixture` /
`test_companies_local_live_jscode_is_byte_identical_to_frozen_fixture` fail with a diff
localized to the "Merge Company" node.

### Pitfall 3: Treating `lv_country_region_normalized`'s missing policy entry as Python-only
**What goes wrong:** Adding the entry only to `config/field_policy.yaml` (the Python-side
config) and assuming the n8n/production path picks it up automatically.
**Why it happens:** `field_policy.yaml` reads like the single source of truth (and its own
header for `lv_org_type` says other representations are "DERIVED"), but there is no
generator for `DEFAULT_COMPANY_POLICY` in `mergeCompanies.js` — unlike `taxonomy.yaml`
(which HAS `scripts/gen_taxonomy_js.py` + a currency test), this policy table is a
hand-maintained mirror with zero drift protection today.
**How to avoid:** Edit both files in the same commit; consider adding a conformance test
(`tests/test_field_policy_conformance.py`, following the `test_taxonomy_conformance.py`
pattern) so future field_policy edits can't silently skip the JS side — this phase is a
natural place to close that gap, though it is not itself one of the three REQ-IDs.
**Warning signs:** `tests/n8n/mergeCompanies.test.mjs` still exercises the OLD default
`fill_blank_only` behavior for this field after the Python-side change ships.

### Pitfall 4: Attempting the org_type conversion directly against `lv_org_type` first
**What goes wrong:** Running the real migration script against the live, data-bearing
`lv_org_type` property as the FIRST empirical test of whether HubSpot even allows the
type/fieldType change.
**Why it happens:** Time pressure to "just try it" instead of spending a cheap cycle on a
disposable test property first.
**How to avoid:** Probe on a throwaway differently-named property (same idiom as
`snapshot_hubspot_schema.py`'s own `--probe` mode, which deliberately uses
`lv__phase15_unknown_property_probe` — a name chosen to never collide with anything real
— for exactly this kind of "learn HubSpot's real behavior before touching production
schema" reconnaissance).
**Warning signs:** No dry-run/probe artifact exists before the "real" PATCH call is made
against `lv_org_type`.

## Code Examples

### Existing httpRequest search node factory (reuse, no new code needed for the dedupe swap)
```python
# Source: scripts/build_cloud_workflows.py:4518 (already in the repo)
def _hs_http_search_node(name, resource, x, y, filter_groups, properties_csv, limit=100):
    if resource not in _HS_SEARCH_URLS:      # {"company": ..., "contact": ...} — "contact" already supported
        raise ValueError(...)
    props = [p.strip() for p in properties_csv.split(",") if p.strip()]
    body = _hs_search_json_body_expr(filter_groups, props, limit)
    return _http_node(name, _HS_SEARCH_URLS[resource], x, y, auth="hubspot", json_body=body)
```

### Existing search-envelope adapter (already dual-shape-safe, no change needed)
```javascript
// Source: scripts/build_cloud_workflows.py — ENRICH_EXTRACT_SEARCH_ROWS (n8n Code node body)
const rows = Array.isArray(res.results) ? res.results : (res.properties ? [res] : []);
return rows.map((r) => ({ json: { ...(r.properties || {}), hs_object_id: r.id } }));
```

### Sibling field_policy entries to mirror for lv_country_region_normalized
```yaml
# Source: config/field_policy.yaml (existing, unmodified)
lv_revenue_band:
  class: system_owned
  promote_to_canonical: true
  min_confidence: 75
  allow_sonnet_escalation: true

lv_employee_band:
  class: system_owned
  promote_to_canonical: true
  min_confidence: 70
```

### Property-migration safety idiom to repeat for the org_type script
```python
# Source: scripts/sync_hubspot_properties.py (existing pattern to follow, not the script to extend)
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Native `n8n-nodes-base.hubspot` search operation | Credential-bound `httpRequest` direct to `/crm/v3/objects/{resource}/search` | Phase 16.6 (companies, BUG 10) / Phase 17.01 (contacts, BUG 23) | Fixes the zero-hit chain-stop hazard; this phase finishes the migration by closing the one remaining call site |
| Property drift silently reported only | N/A (unchanged this phase) | Phase 15 | `sync_hubspot_properties.py` still cannot fix drift — this phase's org_type work is a new, separate script, not an extension |

**Deprecated/outdated:** the native HubSpot node's `search` operation for `resource:contact`
is not deprecated by HubSpot (it works, per `test_hubspot_native_operation_validity.py`'s
own supported-operations table) — its removal here is a deliberate hygiene choice (zero-hit
chain-stop hazard), not a forced API deprecation.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot blocks in-place `type`/`fieldType` conversion on a property once it holds live record values and/or is referenced by any asset (form/workflow/view) | Architecture Patterns — org_type migration, Common Pitfalls #4 | If wrong (HubSpot actually allows it freely), the shadow-property design is unnecessary extra work; if the assumption is directionally right but the exact trigger condition differs, the Wave-0 probe (not this assumption) must be the actual gate before the real migration runs |
| A2 | `min_confidence: 70` is an appropriate threshold for `lv_country_region_normalized`'s new field_policy entry | Architecture Patterns — REQ-country-region-policy | Too low: a wrong provider-guessed country/region could promote to canonical and skew ICP geography scoring (which directly drives hard-veto non-ANZ suppression — CLAUDE.md §10.3); too high: the field stays effectively stage-only, defeating the requirement's purpose. This is a business/config judgment, not a technical fact — needs explicit user sign-off, not silent adoption |
| A3 | No live company record currently holds an `lv_org_type` value outside the 9-key taxonomy vocabulary | Architecture Patterns — recommended migration procedure step 1 | If a stray legacy/manual value exists, the type-conversion PATCH (whichever shape is chosen) either fails outright or silently orphans that record's value — this is exactly why the inventory pass is listed as step 1, not skippable |

## Open Questions

1. **Does HubSpot's Properties API allow converting an existing, non-empty property's
   `type`/`fieldType` via `PATCH /crm/v3/properties/{objectType}/{propertyName}`, and if
   so, what happens to existing values that don't match the new `options` list?**
   - What we know: Official HubSpot developer docs (the properties-v3 guide and the PATCH
     endpoint reference page) document the endpoint's existence and general PATCH
     semantics ("provided fields are overwritten") but do not explicitly address type
     conversion or existing-value handling. Multiple HubSpot Community threads (not
     official docs) report that a property's type/fieldType "can only be changed if the
     property is not referenced anywhere and is empty on every record" — consistent
     with, but not proof of, blocking `lv_org_type`'s conversion given it holds live data.
   - What's unclear: The exact enforcement boundary (does "referenced" include being
     `formField: true` by default, or only active placement on a live form/workflow/view?
     does "empty on every record" get checked per-object-type or portal-wide?), and
     whether a 400 on the type field alone still allows updating `options`/`fieldType`
     independently.
   - Recommendation: Resolve empirically via the Wave-0 disposable-property probe (see
     Architecture Patterns, step 3) before designing the real migration script. Do not
     let the plan hard-code an in-place-PATCH design as the only path.
   - Confidence: LOW (community-forum sourced, not official docs) — tagged `[CITED:
     community.hubspot.com]` at best, several sub-claims `[ASSUMED]`.

2. **Can an archived HubSpot property's internal `name` be immediately reused by a newly
   created property of a different type?**
   - What we know: nothing confirmed this session — not investigated because it's only
     relevant if Open Question 1 resolves toward "blocked," at which point this becomes
     the deciding fact between "archive-then-recreate-same-name" and "genuinely new name +
     repoint every writer."
   - What's unclear: whether HubSpot enforces any grace-period/uniqueness reservation on
     archived-but-not-permanently-deleted property names.
   - Recommendation: Fold into the same Wave-0 probe (test archiving the disposable
     property, then immediately recreating a same-named property of a different type).

3. **What are the actual live values currently populated on `lv_org_type` across existing
   company records?**
   - What we know: The pipeline has enforced the 9-key taxonomy vocabulary on every write
     since Phase 13 via `normalize_org_type()`. The property predates the yaml-driven sync
     and was created directly via a raw API call in Phase 15's migration groundwork.
   - What's unclear: Whether any record predates the taxonomy gate, or was hand-edited in
     the HubSpot UI outside the pipeline, with a value outside the 9 keys.
   - Recommendation: Run the read-only inventory pass (step 1 of the recommended
     procedure) as an early, cheap Wave-0 task — it's a pure `GET`, no write-gate needed,
     and de-risks everything downstream.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `HUBSPOT_PRIVATE_APP_TOKEN` (env, via `hs` CLI projects static app) | All three REQs' live verification steps | Env-gated; scripts skip-to-exit-0 without it (`_has_credentials()`), so unavailable in an agent sandbox is a designed no-op, not a blocker | n/a | Dry-run/offline test paths cover REQ-dedupe-transport-swap and REQ-country-region-policy fully; REQ-orgtype-enumeration's live probe and inventory pass are operator-run steps per the `n8n-deploy-permission-blocked` / `hubspot-projects-app-auth-model` memory notes (arming HubSpot writes needs the human; disarmed reads/dry-runs do not) |
| n8n Cloud deploy (disarmed) | Verifying the dedupe transport swap in the real workflow | Available per prior-phase precedent (disarmed deploys pass for agents) | n/a | — |

**Missing dependencies with no fallback:** none — every live-write step in this phase is
operator-gated by design (consistent with Phase 20's precedent), not by missing tooling.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + Node's built-in `node --test` (JS) |
| Config file | none dedicated — repo-root pytest discovery; `tests/n8n/*.test.mjs` run directly |
| Quick run command | `.venv/bin/python -m pytest tests/test_hubspot_native_operation_validity.py tests/test_companies_factory_frozen.py tests/test_deploy_credential_binding.py -q` |
| Full suite command | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-dedupe-transport-swap | Dedupe Search uses httpRequest, not native search | unit | `.venv/bin/python -m pytest tests/test_hubspot_native_operation_validity.py -q` | ✅ (existing guard; needs a NEW test asserting zero native `contact:search` remains in `wf_scheduled_maintenance_cloud.json` — see Wave 0 Gaps) |
| REQ-dedupe-transport-swap | Credential binding still resolves post-swap | unit | `.venv/bin/python -m pytest tests/test_deploy_credential_binding.py -q` | ✅ |
| REQ-dedupe-transport-swap | Weekly sweep still writes only the needs-review flag | unit | `.venv/bin/python -m pytest tests/test_write_gate_coverage.py -q` | ✅ |
| REQ-country-region-policy | Field promotes under new policy instead of staging-only | unit (JS) | `node --test tests/n8n/mergeCompanies.test.mjs` | ❌ Wave 0 — add a case for `lv_country_region_normalized` promoting at >=70 confidence |
| REQ-country-region-policy | Companies jsCode frozen fixture re-baselined, not silently stale | unit | `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` | ✅ (existing guard; will correctly FAIL until the fixture is re-baselined as part of this phase's work) |
| REQ-orgtype-enumeration | Pipeline never writes an out-of-vocabulary org_type value | unit | `.venv/bin/python -m pytest tests/test_taxonomy_conformance.py -q` (+ `src/taxonomy.py`'s own `__main__` self-check) | ✅ (already proves this by construction — no new test strictly required, though a HubSpot-schema conformance test, e.g. asserting `hubspot_properties.yaml`'s new `lv_org_type` options == `taxonomy.yaml` keys, is Wave 0 new ground) |
| REQ-orgtype-enumeration | Live inventory has no stray out-of-vocabulary value | manual/live (operator) | new read-only inventory script (Wave 0 gap) | ❌ Wave 0 |
| REQ-orgtype-enumeration | Rollback path documented before migration runs | manual/live (operator) | new migration script + runbook doc (Wave 0 gap) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant file's targeted pytest/node-test command above
- **Per wave merge:** `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs`
- **Phase gate:** full suite green before `/gsd-verify-work`; live org_type migration steps
  remain operator-run and are verified via the migration script's own dry-run diff + a
  fresh `snapshot_hubspot_schema.py` post-migration comparison against the pre-migration
  baseline — not part of the automated offline suite.

### Wave 0 Gaps
- [ ] New pytest module (or extend `test_hubspot_native_operation_validity.py`) asserting
      zero `type=="n8n-nodes-base.hubspot" AND operation=="search"` nodes remain in
      `wf_scheduled_maintenance_cloud.json` — the REQ-dedupe-transport-swap acceptance
      guard.
- [ ] `tests/n8n/mergeCompanies.test.mjs` case: `lv_country_region_normalized` promotes to
      canonical at/above its new `min_confidence` threshold (and stays staged below it).
- [ ] `companies_jscode_frozen.json` re-baseline (its own explicit, reviewed commit, per
      the fixture's own header comment) — required the moment `DEFAULT_COMPANY_POLICY`
      changes.
- [ ] Optional but recommended: `tests/test_field_policy_conformance.py` — a drift guard
      between `config/field_policy.yaml` and `mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY`
      (Pitfall 3), following the `test_taxonomy_conformance.py` precedent. Not one of the
      three REQ-IDs, but the natural moment to close a gap this phase's own edit would
      otherwise leave silently unguarded.
- [ ] Read-only org_type live-value inventory (Wave 0, cheap, no write-gate needed) —
      prerequisite fact for the migration design.
- [ ] Wave-0 disposable-property live probe answering Open Questions 1 and 2 — prerequisite
      for choosing the migration shape and authoring a correct rollback runbook.
- [ ] New migration script (does not exist in any form yet) + its rollback runbook,
      authored only after the probe's answer is known.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This is a backend automation pipeline using a static app token, not a user-facing auth surface |
| V3 Session Management | No | N/A — no session concept in this phase's scope |
| V4 Access Control | Partial | HubSpot private-app scoping (already governed by the `hs project install-app` grant model per memory `hubspot-projects-app-auth-model`) — no new scopes needed for this phase (property read/write and CRM object search/update scopes are already granted) |
| V5 Input Validation | Yes | `src/taxonomy.py normalize_org_type()` is the standing control — already enforces the enum vocabulary before any write; this phase's migration must not introduce a second, divergent validation path |
| V6 Cryptography | No | N/A — no new secrets/crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Schema migration silently corrupting or orphaning live CRM data (org_type conversion) | Tampering / Repudiation | Baseline snapshot before + post-migration diff (existing `snapshot_hubspot_schema.py` pattern) + read-only inventory pass + typed-confirmation live gate, mirroring the Phase-15 idiom already in this repo |
| A partial migration reporting false success | Repudiation | Follow `sync_hubspot_properties.py`'s own precedent: a partial-failure run must exit non-zero and itemize failures, never report clean on partial completion (already the established convention here — the new migration script must match it) |
| Arming a HubSpot write inadvertently via an agent session | Elevation of Privilege | Unchanged from established project policy: disarmed deploys/dry-runs/reads proceed without asking; arming any live write (property PATCH, canonical field write) requires explicit operator action, per memory `n8n-deploy-permission-blocked` |

## Sources

### Primary (HIGH confidence)
- Direct code inspection (this session): `scripts/build_cloud_workflows.py`,
  `scripts/deploy_n8n_workflows.py`, `scripts/sync_hubspot_properties.py`,
  `scripts/rollback_property_migration.py`, `scripts/snapshot_hubspot_schema.py`,
  `src/taxonomy.py`, `src/merge_policy.py`, `src/icp_scoring.py`,
  `n8n/code/mergeCompanies.js`, `n8n/code/normalizeProviders.js`,
  `config/taxonomy.yaml`, `config/field_policy.yaml`, `config/hubspot_properties.yaml`,
  `config/hubspot_migration/baseline/portal-schema-companies-post.json`, and the relevant
  `tests/*.py` / `tests/n8n/*.test.mjs` files cited throughout.

### Secondary (MEDIUM confidence)
- `developers.hubspot.com/docs/api-reference/crm-properties-v3/guide` — confirms PATCH
  endpoint exists and general "provide only changed fields" semantics; silent on
  type-conversion behavior.
- `developers.hubspot.com/docs/api-reference/crm-properties-v3/core/patch-crm-v3-properties-objectType-propertyName`
  — the PATCH reference page itself; also silent on type/fieldType mutability.

### Tertiary (LOW confidence)
- HubSpot Community threads (WebSearch-surfaced, not independently verified this
  session): "Unable to change Companies field type," "Custom field type/validation changes
  and existing values failing update" — consistent, uncorroborated-by-official-docs signal
  that in-place type conversion is blocked once a property is referenced/non-empty. Treated
  as `[CITED: community.hubspot.com]` at best; the underlying mechanism claims are
  `[ASSUMED]` pending the Wave-0 probe.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, pure reuse of existing repo code
- Architecture (dedupe transport swap): HIGH — verified against live code, existing
  precedent nodes (SJ-1/SJ-2), and passing test infrastructure
- Architecture (country-region policy): HIGH for the mechanism (config-only change,
  precedent siblings exist); MEDIUM for the specific `min_confidence` value chosen (a
  judgment call flagged in Assumptions Log)
- Architecture (org_type schema migration): MEDIUM-LOW — the migration MECHANISM (need a
  new script, existing tooling can't do it) is HIGH confidence; the exact HubSpot API
  behavior for in-place type conversion is LOW confidence and explicitly deferred to a
  Wave-0 live probe
- Pitfalls: HIGH — all four are drawn from concrete, currently-passing/failing test
  behavior in this exact repo, not speculative

**Research date:** 2026-07-30
**Valid until:** 30 days for the code-derived findings (stable, internal); the HubSpot API
behavior open questions should be considered valid only until the Wave-0 probe runs — at
that point this document's org_type section should be treated as superseded by the probe's
findings, not re-trusted.
