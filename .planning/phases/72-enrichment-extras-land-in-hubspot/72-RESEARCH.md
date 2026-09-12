# Phase 72: Enrichment extras land in HubSpot - Research

**Researched:** 2026-09-12
**Domain:** n8n Cloud contact-ingest lane + operator-plugin CSV pre-processing (HubSpot CRM
write mapping), config-driven merge-policy engines (JS x2 + Python oracle)
**Confidence:** MEDIUM-HIGH — every code-path claim below is read from the file this session
(cited with line ranges); the one HIGH-risk item (`hs_additional_emails` writability) is
flagged LOW and needs a live re-check before D-72-10 is built on it.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-72-01..18) — copied verbatim from 72-CONTEXT.md, NOT reopened here
- **D-72-01:** Widen the ingest lane; the plugin stops stripping. `config/column_mapping.yaml`
  and `n8n/code/columnMap.js` (YAML/JS parity test) accept the 12 promotable contact keys; the
  ingest lane's candidate assembly (`scripts/build_cloud_workflows.py`, the `email/firstname/
  lastname/jobtitle/company` + linkedin block near line 417) admits them;
  `preingest.strip_enrichment_extras` becomes a no-op by construction. Rejected: create-thin-
  then-enrich-by-id (second provider spend per created contact) and plugin-side-only rename.
  Reversibility: costly — the ingest lane JSON is regenerated and deployed; rollback is the
  pre-72 bundle.
- **D-72-02:** ONE source of truth for "which keys reach HubSpot on create" =
  `config/field_policy.yaml`. `promotable_contact_props()` already derives the 12 keys from
  it; the column map and the lane assembly read the same list, pinned by a parity test. No
  second list.
- **D-72-03:** `mobile` aliases to `mobilephone`, not `phone`. `phone` is the landline/office
  slot.
- **D-72-04:** LinkedIn lands in BOTH `lv_linkedin_url` (canonical, PN-1 unchanged) and native
  `hs_linkedin_url`. The defect was plugin-side: the lane already maps the `linkedin_url`
  header to `lv_linkedin_url` (`build_cloud_workflows.py:398-421`); `strip_enrichment_extras`
  dropped the key before the CSV. No `linkedin_url` contact property exists on the portal.
- **D-72-05:** On CREATE, provider wins; the CSV value is recorded as a conflict (merge
  report + `source_values` on the held row), never silently lost. Identity fields (`email`,
  `firstname`, `lastname`, `company`) are not subject to this — they are the row's identity
  and stay as supplied.
- **D-72-06:** On UPDATE, recency overwrites a non-blank HubSpot value ONLY for
  `stale_refreshable` fields older than their `stale_after_days` (jobtitle 180d; industry
  365d; numberofemployees is fill_blank_only per 58-05 and stays so), and only when the
  provider observation is newer than the existing value. `fill_blank_only` still fills blanks
  only; `manual_protected` never. This is the SAFE-01 line.
- **D-72-07:** Observation times. Provider value = the run's dispatch time; HubSpot existing
  value = the property's own history timestamp (`propertiesWithHistory` `versions[].timestamp`),
  not the record's `lastmodifieddate`; a CSV value carries no time and ranks oldest.
- **D-72-08:** A value the pipeline itself wrote (provenance source apollo/lusha/zoominfo/
  claude_web) is replaceable by a newer provider value at or above the field's
  `min_confidence` — the §17.2.1 "previously written by the enrichment system" clause
  extended to provider sources, with the same four conjuncts (provenance entry must still
  match the current value; no material conflict). Reversibility: reversible (policy keys).
- **D-72-09:** Recency lives in the shared policy layer, both objects, both engines —
  expressed as `field_policy.yaml` classes/TTLs and implemented in `mergeContacts.js`,
  `mergeCompanies.js`, and `src/merge_policy.py` under the Phase 46 parity rule. Companies
  inherit it in this phase with their existing TTLs.
- **D-72-10:** A second email goes to `hs_additional_emails` (native, writable, `;`-separated);
  the primary `email` is never rewritten on an existing record. On create the CSV email is
  primary and the provider's becomes additional.
- **D-72-11:** Fixed-cap overflow: exactly one `_2` slot per kind — `lv_phone_2`,
  `lv_mobilephone_2` on contacts, `lv_phone_2` on companies — created ONCE at setup by a
  property script (schema-level, per object type; never per record, never during a run). A
  third value goes to `lv_enrichment_provenance` only. No `_3`, ever. Reversibility: costly —
  custom properties on the operator's portal.
- **D-72-12:** When providers disagree on the same slot, the `source_registry` trust-rank
  winner takes the slot and the loser takes the `_2` slot — both provenanced. No judge call
  for phone/email disagreements (RO-2 stays: only material fields reach the judge).
- **D-72-13:** Verification stamps = provenance JSON only. `lv_enrichment_provenance` records
  source/confidence/timestamp per landed slot; no new per-field `_source`/`_verified_at`
  properties. `lv_mobilephone_verified_at` keeps its one existing use.
- **D-72-14:** Companies: `phone` (fill_blank_only) + `lv_phone_2` in scope; `hs_additional_
  domains` in scope for extra provider domains; company email is a stated non-goal (no such
  property).
- **D-72-15:** Geo lands as names into `city`/`state`/`country` and as ISO codes into
  `hs_state_code`/`hs_country_region_code` only when the provider supplies a code — nothing
  derived by guessing. Same shape on contacts and companies (companies gain `state` + the two
  code fields beside the shipped `country`/`city`, same fill_blank_only class).
- **D-72-16:** Contact geo never feeds the company's `lv_country_region_normalized`. Region
  stays a company-waterfall + judge-gated ICP input (58-06); a person's location is not
  evidence of the org's region.
- **D-72-17:** One end-of-phase live gate (backloaded, operator ruling 2026-09-09): re-run one
  absent person at a company HubSpot holds through `enrich-before-ingest`, `create all 1`,
  then read the contact back and assert `mobilephone`, `hs_linkedin_url` + `lv_linkedin_url`,
  and geo landed; plus one UPDATE row proving a non-blank `fill_blank_only` field was NOT
  overwritten. Hand-delete after. Nothing armed before it.
- **D-72-18:** Deploy scope = the ingest lane only. Regenerate every JSON from the one
  builder, but deploy + bounce only `wf_contact_ingest_cloud` at the gate; the others must
  diff clean.

### Carried forward — NOT reopened
- CLAUDE.md §13.0.1 — ONE association implementation, server-side; company creation stays in
  the enrichment lane's companies form.
- SAFE-01..05 — no `min_confidence` lowered, no `fill_blank_only` weakened, no drop path
  softened, ceilings stay refusals.
- Phase 66 RICH-01..06 — the 12-key `promotable_contact_props()` set is the widened set.
  58-05 — company `country`/`city` fill_blank_only from the Apollo org record. 58-06 —
  material-conflict judge gate unchanged.
- Phase 46 parity rule — any merge-policy predicate change lands in both engines
  (`mergeContacts.js` + `mergeCompanies.js` + `src/merge_policy.py`) in one commit.
- D-70-11, D-71-01..05 — verdicts, facets, held-entry keys and stamp untouched.

### Claude's Discretion
- Exact parity-test shape for the YAML/JS/policy three-way list.
- Property-creation script shape.
- How `hs_additional_emails` is serialised on write — verify live, record in the SUMMARY.
- Which provider fields map to which geo slot per provider (`normalizeProviders.js` branches).

### Deferred Ideas (OUT OF SCOPE)
- A `_3` overflow slot or a multi-value text property.
- Per-field `_source`/`_verified_at` properties for the new slots.
- Company email (`lv_company_email`) — no property, no source today.
- Any change to `confidence.assess`/hold codes (D-70-11), the held-entry schema (D-71-04/05),
  company creation routes (§13.0.1), the ICP inputs (`lv_country_region_normalized` stays
  judge-gated), a `_3` overflow slot, per-field `_source`/`_verified_at` properties.
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs are mapped for Phase 72 (ROADMAP.md: "**Requirements**: TBD"). Coverage is
verified against CONTEXT.md's D-72-01..18 instead, per the phase's own instruction. The table
below maps each decision to the research that supports planning it.

| Decision | Research Support |
|----------|-------------------|
| D-72-01/02/03 | §"Ingest lane today" — exact widening points in `column_mapping.yaml`, `columnMap.js`, `preingest.py`, `extraction.py`, and the ingest lane's `Merge Contacts` node in `build_cloud_workflows.py`. |
| D-72-04 | §"LinkedIn naming defect" — confirms the mapping already exists; only the strip drops it. |
| D-72-05 | §"preingest.merge_enriched today" — exact current rule and the diff needed. |
| D-72-06/07/08/09 | §"The three merge engines" — confirms NO TTL/recency logic exists today in any of the three `stale_refreshable` branches (a build, not an extension), and that `propertiesWithHistory` is a new fetch requirement HubSpot's search API cannot serve. |
| D-72-10/11/12/13 | §"Multi-value slots" — source_registry trust ranks, the `hs_additional_emails` writability risk, and the property-creation tool to reuse. |
| D-72-14/15/16 | §"normalizeProviders.js coverage" — per-provider producer inventory for contacts and companies, and the company-side gaps (no phone/state/code/domain producers today). |
| D-72-17 | §"Validation Architecture" — the one live gate, restated as a test plan. |
| D-72-18 | §"Deploy scope" — `--only` flag already exists on the deploy script; the bounce script does not. |
</phase_requirements>

## Summary

Phase 72's job is narrower than it first reads. The n8n **enrichment lane** (`wf_enrichment_cloud`,
the webhook/scheduled path that enriches an EXISTING HubSpot record) already carries all 12
`promotable_contact_props()` fields end to end — its `Merge Winners` node (`ENRICH_MERGE` in
`scripts/build_cloud_workflows.py`, ~line 1946-1988) already builds a `mergeContacts()` candidate
from `email, mobilephone, phone, jobtitle, seniority, city, state, country, hs_state_code,
hs_country_region_code, lv_linkedin_url, lv_persona_group` — the exact widened set this phase
asks for. The gap is **only** in the CSV **ingest** lane (`wf_contact_ingest_cloud`, the
create/update-by-CSV path `contact-upload` and `enrich-before-ingest` dispatch to): its `Merge
Contacts` node (`MERGE_CONTACTS`, ~line 395-421, shared verbatim between the cloud and local
workflow builds) restricts its candidate to `email, firstname, lastname, jobtitle, company,
lv_linkedin_url, phone` — seven keys — and the operator-plugin's own CSV boundary
(`extraction.canonical_props()`, 8 headers from `column_mapping.yaml`) is narrower still, so
`preingest.strip_enrichment_extras` throws away everything `merge_enriched` widened in.
Widening `MERGE_CONTACTS`'s candidate loop to mirror `ENRICH_MERGE`'s is a small, low-risk diff
because it calls the identical shared `mergeContacts()` function — no new merge logic, just more
keys reaching a function that already knows what to do with them.

Recency (D-72-06..09), by contrast, is **not** a small diff: none of the three merge engines
(`mergeContacts.js`, `mergeCompanies.js`, `src/merge_policy.py`) implement any TTL/staleness
check inside their `stale_refreshable` gate branch today — all three return a blanket
`needs_review` for any non-blank existing value, ignoring `stale_after_days` entirely (that
config key is read only by the separate `enrichmentGate.js::decideAction`, which gates
enrich-vs-skip on the PIPELINE'S OWN `lv_<field>_verified_at` cache-key property, never on
HubSpot's native property-history). D-72-07's "HubSpot existing value = the property's own
history timestamp" is therefore a genuinely new data-fetch requirement, and — confirmed live
via WebSearch against HubSpot's own docs and community reports — `propertiesWithHistory` is
**not** available on `POST /crm/v3/objects/contacts/search` (the endpoint every existing lookup
in this repo uses); it is only available on the single-object GET and the batch/read endpoint.
The ingest lane will need a new or additional fetch call to get per-property timestamps at all.

Multi-value slots (D-72-10..13) are policy-and-property additions with one real risk: this
session's WebSearch of HubSpot's own community forum returns multiple reports that
`hs_additional_emails` is **read-only via the standard v3 API** — directly conflicting with
CONTEXT.md's "verified live 2026-09-12... writable" claim, and the property does not appear at
all in this repo's own 2026-08-26 live property export. This is flagged, not resolved — do not
build D-72-10 without a live property-metadata check first (see Common Pitfalls).

Geo/phone widening on companies (D-72-14/15) touches ground the contacts side never needed to:
`normalizeProviders.js` has **no producer at all** for company `state`, company
`hs_state_code`/`hs_country_region_code`, company `phone`, or any second/"additional" company
domain — these fields will need new producer code added to the Lusha/Apollo/ZoomInfo company
branches (or a documented accepted gap, mirroring the pre-existing accepted gap for company
`domain` itself, `2026-09-04-company-domain-has-no-candidate-source.md`).

**Primary recommendation:** treat this as four largely-independent, sequenceable changes: (1)
config + candidate-loop widening on the ingest lane (mirror `ENRICH_MERGE`'s pattern into
`MERGE_CONTACTS`) — low risk, config-derived, no-op-by-construction for the plugin side; (2)
build real recency/TTL logic into the shared `_gate` function across all three engines, which
first requires deciding how "the property's own history timestamp" reaches the merge call (new
fetch, or accept a narrower interim signal and flag it) — this is the phase's highest-risk item;
(3) multi-value slot properties + provenance-only stamping — verify `hs_additional_emails`
writability live before committing to it; (4) company geo/phone/domain widening — new producer
code, or an explicit accepted-gap note per field with no producer yet.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSV header -> canonical key mapping | Backend (n8n Code node, `columnMap.js`) | Plugin (Python mirror, `column_mapping.yaml`) | Both read the SAME YAML; n8n is what actually runs on a real send, the plugin's copy is the offline check/preview path — the parity test is what keeps them from disagreeing (existing idiom). |
| "Which 12 keys are promotable" | Config (`config/field_policy.yaml`) | — | Single source of truth (D-72-02); every consumer derives from it, never restates a list. |
| CSV-vs-waterfall CREATE merge | Plugin (Python, `preingest.merge_enriched`) | — | Runs BEFORE the row ever reaches n8n — this is the CSV dispatch pre-processing step, not a HubSpot-record merge. |
| Existing-HubSpot-record merge (fill/stale/promote) | Backend (n8n Code node, shared `mergeContacts.js`/`mergeCompanies.js`) | Python oracle (`src/merge_policy.py`, Phase 46 parity) | This is where a candidate meets an EXISTING HubSpot property value and a promote/stage/needs_review decision is made — the recency logic (D-72-06..09) belongs here, in both JS engines plus the Python mirror. |
| Provider field extraction/normalization | Backend (n8n Code node, `normalizeProviders.js`) | — | Per-provider raw-response -> candidate-list shape; this is where new company geo/phone producers must be added. |
| HubSpot custom-property schema (the `_2` slots) | Operator tooling (Python script against HubSpot Properties API) | — | Schema-level, created once at setup, never per-record (D-72-11). |
| Deploy/bounce of the regenerated workflow | Operator tooling (`scripts/deploy_n8n_workflows.py` / `bounce_n8n_workflows.py`) | — | D-72-18 scopes this to one workflow; the deploy script already supports `--only`, the bounce script does not (see Common Pitfalls). |

## Standard Stack

No new external packages, libraries, or dependencies are introduced by this phase. Every touch
point is either (a) existing repo config (YAML), (b) existing pure-JS modules for n8n Code
nodes, (c) existing Python modules in `operator-claude-plugin/scripts/` and `src/`, or (d) the
HubSpot CRM v3 REST API (already integrated). **Package Legitimacy Audit is N/A** — no packages
to audit.

### Existing modules this phase modifies (not "installs")
| Module | Role | Change needed |
|--------|------|----------------|
| `config/column_mapping.yaml` | CSV header aliases + identity groups | Add aliases for the 9 keys `promotable_contact_props()` carries beyond today's 8 canonical headers (mobile->mobilephone per D-72-03, city, state, country, hs_state_code, hs_country_region_code, seniority already? — check exact diff at plan time against the live 12-key list) |
| `n8n/code/columnMap.js` | JS mirror of the above | Same alias additions, kept byte-parity via `tests/n8n/columnMapAliasParity.test.mjs` (already exists for the alias table; `columnMapIdentityParity.test.mjs` covers `required_identity` only) |
| `n8n/code/mergeContacts.js` | Deterministic per-field gate, contacts | `_gate`'s `stale_refreshable` branch needs real TTL logic; `_isSystemCorrectable`-equivalent extension for D-72-08 |
| `n8n/code/mergeCompanies.js` | Deterministic per-field gate, companies | Same TTL fix; already has `_isSystemCorrectable` (company-only, `manual_protected`-only today) — D-72-08 needs this pattern generalized |
| `src/merge_policy.py` | Python oracle mirror of both JS engines | Same TTL fix, Phase 46 parity (one commit, all three files) |
| `n8n/code/normalizeProviders.js` | Per-provider raw-response normalizer | Add company producers for `state`, `hs_state_code`, `hs_country_region_code`, `phone`; add a second-domain producer if `hs_additional_domains` is to have live data (see Pitfalls) |
| `operator-claude-plugin/scripts/preingest.py` | `merge_enriched`, `strip_enrichment_extras`, `promotable_contact_props` | `merge_enriched`'s fill-not-overwrite rule needs the D-72-05 CREATE-time "provider wins except identity" behaviour; `strip_enrichment_extras` becomes a no-op once column_mapping.yaml widens (no code change needed there — see below) |
| `scripts/build_cloud_workflows.py` | Workflow JSON generator | Widen `MERGE_CONTACTS`'s candidate loop (~line 395-421) to mirror `ENRICH_MERGE`'s (~line 1946-1988); add company candidate-loop fields for state/codes/phone/domain (~line 3796-3850) |
| `scripts/sync_hubspot_properties.py` + `config/hubspot_properties.yaml` | Existing idempotent property-create tool | Reuse for the `_2` slots (D-72-11) rather than writing a new bespoke script — see Don't Hand-Roll |
| `scripts/deploy_n8n_workflows.py` | Deploy one or all workflow JSONs | Already supports `--only <filename>` (line ~575) — no change needed for D-72-18's deploy half |
| `scripts/bounce_n8n_workflows.py` | Deactivate+activate all 5 workflows | Hardcodes all 5 workflow ids (`WORKFLOWS` dict, line ~23) — **no `--only` flag exists**; needs either a small addition or an accepted "bounce all five, harmless because 4 are diff-clean" plan note (see Pitfalls) |

## Package Legitimacy Audit

**N/A — this phase installs no external packages.** Every dependency touched is already
present in the repo (PyYAML, requests, pytest, node's built-in `node:test`).

## Architecture Patterns

### System Architecture Diagram

```
CSV/spreadsheet (operator upload)
        |
        v
[Plugin: extraction.py]  <-- column_mapping.yaml (aliases, identity groups)
  canonical_props() header allowlist (8 headers today, widened to 12-key union)
        |
        v
[Plugin: preingest.py]
  dispatch to n8n ENRICHMENT lane (wf_enrichment_cloud) for provider waterfall
        |
        v  (provider results keyed by row_id)
[Plugin: preingest.merge_enriched]
  CSV row + provider response -> ONE merged row
  ALLOWED KEYS = canonical_props() UNION promotable_contact_props()  (12 keys)
  D-72-05: on CREATE, provider wins except identity fields (email/firstname/lastname/company)
        |
        v
[Plugin: preingest.strip_enrichment_extras]
  drops (promotable_contact_props() - canonical_props()) -- becomes EMPTY SET
  once column_mapping.yaml is widened to the 12-key union == NO-OP BY CONSTRUCTION
        |
        v
[Plugin: extraction.write_dispatch_csv]
  STRUCT-01 guard: header = canonical_props() (now 12 keys, not 8) -- widens automatically
        |
        v  (dispatch.py POST, multipart CSV)
[n8n: wf_contact_ingest_cloud]
  Extract From File -> Map Columns (columnMap.js, widened aliases)
     -> Merge Contacts (MERGE_CONTACTS candidate loop -- WIDEN to mirror ENRICH_MERGE)
        -> mergeContacts(existingProps, candidate, policy, opts)
             _gate() per field: fill_blank_only / stale_refreshable (NEEDS RECENCY LOGIC) /
                                 system_owned / manual_protected (+ system-correctable check)
     -> HubSpot Create / Update (PATCH/POST properties)
     -> Associate Company (server-side, §13.0.1, unchanged)

[n8n: wf_enrichment_cloud]  (separate lane, existing-record enrichment -- ALREADY WIDE)
  Merge Winners (ENRICH_MERGE) already builds all 12 keys as candidates
  -> same shared mergeContacts() -- same recency fix lands here too, automatically,
     because both lanes call the SAME function.
```

### Recommended change sequencing (not a plan, a dependency order)
1. **Config widening** (`column_mapping.yaml`, `columnMap.js`, parity test) — unlocks
   everything downstream; the plugin side (`canonical_props`, `strip_enrichment_extras`)
   needs zero code change once this lands, per their own docstrings (`extraction.canonical_props`
   never hardcodes the header list; `strip_enrichment_extras` computes its drop-set as
   `promotable_contact_props() - canonical_props()`, which becomes `set()` once the two
   converge).
2. **Ingest-lane candidate widening** (`MERGE_CONTACTS` in `build_cloud_workflows.py`) —
   mirrors `ENRICH_MERGE`'s existing pattern; low risk because it feeds the SAME
   `mergeContacts()` function the enrichment lane already exercises in production.
3. **`preingest.merge_enriched` CREATE-time rule** (D-72-05) — a genuine logic change,
   independent of (1)/(2); can be built and tested in isolation (pure Python, existing test
   file `test_preingest_merge.py`).
4. **Recency/TTL in the shared gate** (D-72-06..09) — the highest-risk item; needs a design
   decision on where "the property's own history timestamp" is fetched from (new GET/batch-
   read call vs. an interim proxy) before the gate logic itself can be written. This is
   shared code (Phase 46 parity), touches both lanes at once, and should probably be its own
   plan/wave.
5. **Multi-value slots** (D-72-10..13) — property creation (idempotent, `sync_hubspot_
   properties.py`) must land before the candidate/merge code that writes to `lv_phone_2`
   etc.; `hs_additional_emails` writability needs a live check first (see Pitfalls).
6. **Company geo/phone/domain** (D-72-14/15) — new `normalizeProviders.js` producers +
   `mergeCompanies.js`/`field_policy.yaml`/`merge_policy.py` policy entries + the Merge
   Company candidate loop widening in `build_cloud_workflows.py`.
7. **Deploy + live gate** (D-72-17/18) — end of phase, backloaded per the operator's own
   standing ruling (`backload-human-gates-to-end-of-phase` memory).

### Pattern: config-derived allowlist, never a restated literal
**What:** `extraction.canonical_props()`, `preingest.promotable_contact_props()`,
`preingest.refreshable_contact_props()` all derive their key sets fresh from YAML on every
call — no module ever hardcodes the list. `strip_enrichment_extras` computes its drop-set as
a set difference between two such derived lists, which is why it becomes an inert no-op the
moment the two lists converge, with zero code change to that function itself.
**When to use:** Any new field this phase adds should follow the same rule — add it to
`config/field_policy.yaml` and/or `config/column_mapping.yaml`, never to a Python/JS literal.
**Example (existing code, not to be changed):**
```python
# operator-claude-plugin/scripts/extraction.py:162-167
def canonical_props(mapping_path=None) -> list[str]:
    data = _load_mapping(mapping_path)
    aliases = dict(data.get("aliases") or {})
    return sorted(set(aliases.values()))
```

### Pattern: single shared merge function called from two lanes
**What:** `mergeContacts()` (and `mergeCompanies()`) is called from BOTH the ingest lane's
`MERGE_CONTACTS` wrapper (create/update-by-CSV) and the enrichment lane's `ENRICH_MERGE`
wrapper (enrich-existing-record). A recency fix inside `_gate()` benefits both lanes for free;
widening one wrapper's candidate object does NOT require touching the merge function itself.
**When to use:** Any policy-shape change (a new field class, a new gate branch) belongs in the
shared function; any change to WHICH fields a given lane offers as candidates belongs in that
lane's own wrapper only.

### Anti-Patterns to Avoid
- **A second key list:** Any new hardcoded array of "the widened fields" anywhere outside
  `config/field_policy.yaml` recreates exactly the drift class Phase 66/D-72-02 exists to
  prevent (see the `dropped_property_keys` comment block in `preingest.py` explaining why the
  union of two independently-defined lists caused RICH-04's original bug).
- **Writing to `hs_additional_emails` without a live writability check:** see Common Pitfalls.
- **Bouncing all 5 workflows when only 1 should deploy:** the bounce script bounces
  unconditionally; confirm the other 4 are byte-diff-clean before accepting that as harmless,
  or add a per-workflow bounce path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Creating the `_2` overflow properties on the portal | A new bespoke `--plan/--execute/--verify` script from scratch | `scripts/sync_hubspot_properties.py` + `config/hubspot_properties.yaml` | Already the repo's established idempotent forward-migration tool: env-gated (`ALLOW_HUBSPOT_PROPERTY_WRITES`), diffs live-vs-declared schema, creates only what's missing, one POST per property with individually-confirmed status. Adding 3 property declarations to the YAML and running the existing tool is strictly less code than a new script, and it inherits the tool's existing dry-run/portal-guard/idempotency behaviour for free. |
| Per-field YAML-vs-JS drift checking | A new hand-rolled comparison in each new test file | Extend `tests/n8n/columnMapIdentityParity.test.mjs`'s idiom (drive the test FROM the YAML via a Python-oracle subprocess, never restate values in JS) | The existing test already solved "how do I stop these two files disagreeing" for one dimension (identity groups); the alias table has a sibling test (`columnMapAliasParity.test.mjs`). A third dimension (field_policy's 12-key list vs both) should reuse the same pattern, not invent a fourth. |
| Detecting the winning provider when two disagree on the same slot (D-72-12) | A bespoke tie-break function | `config/source_registry.yaml`'s `trust_rank` (already the field used by `choose_best()`/`priority_order` in all three merge engines) | This is exactly what `choose_best` already does for the SINGLE-slot case; D-72-12 only needs the loser (second-best by the same sort) routed to the `_2` slot instead of discarded, not a new ranking mechanism. |

**Key insight:** almost everything this phase needs already has a working analogue elsewhere in
this repo (the enrichment lane's candidate loop, the property-migration script, the parity-test
idiom, the trust-rank sort). The novel work is genuinely confined to: the recency/TTL gate logic
(nothing like it exists yet), the CREATE-time provider-wins merge rule, and the company-side geo/
phone/domain producers.

## Common Pitfalls

### Pitfall 1: `hs_additional_emails` may not be writable via the standard v3 API
**What goes wrong:** D-72-10 assumes a plain `PATCH .../properties` write with a `;`-joined
string lands in `hs_additional_emails`. Multiple HubSpot Community threads (2024-era, but
recurring) report this property has `modificationMetadata.readOnlyValue = true` and that writes
to it via the standard v3 CRM object endpoints are silently no-ops or rejected; a "legacy v1
endpoint" workaround is cited instead. This directly conflicts with CONTEXT.md's "verified live
2026-09-12... writable" claim, and the property is **absent entirely** from this repo's own
2026-08-26 live property export (`docs/hs_props/.../contact.csv`), which does otherwise include
every other native property this phase touches (`hs_linkedin_url`, `hs_seniority`,
`hs_state_code`, `hs_country_region_code`, `hs_whatsapp_phone_number`, `work_email` — all
present, all `Read only value = false`).
**Why it happens:** HubSpot periodically adds new default properties to portals; the property
may be newer than the Aug-26 export, or may be a portal-tier-gated read-only rollup that reads
as "writable" in the properties LIST but rejects PATCH writes at the object endpoint.
**How to avoid:** Before writing any D-72-10 code, run a live `GET
/crm/v3/properties/contacts/hs_additional_emails` and inspect `modificationMetadata.
readOnlyValue`; then attempt one disarmed-adjacent single-property PATCH on a scratch/test
record and confirm the value actually lands on re-read. If it is genuinely read-only, D-72-10
needs a fallback (`work_email` for a second work address is already confirmed writable; a
custom `lv_email_2` mirroring the `_2` pattern is the fallback shape consistent with D-72-11).
**Warning signs:** A PATCH that returns 200 but a re-read shows the field unchanged or absent —
exactly the failure mode that would pass a naive "the API accepted it" check and fail the
D-72-17 live gate.
[ASSUMED: community reports may not reflect this specific portal or may be stale/wrong;
CONTEXT.md's live-verified claim is not itself wrong until re-checked]

### Pitfall 2: `propertiesWithHistory` is not available on the search endpoint
**What goes wrong:** Every existing "does this contact/company already exist" lookup in this
repo (`crm/v3/objects/contacts/search`, used by `resolveIdentity.js` / the ingest lane's match
step) uses the POST search endpoint. D-72-07 requires a per-property history timestamp, which
this endpoint cannot return — confirmed via WebSearch against HubSpot's own community/GitHub
issue tracker (`propertiesWithHistory` explicitly unsupported on `.../search`; supported on the
single-object GET `.../contacts/{id}?propertiesWithHistory=...` and, with some reported
batch-specific caveats, on `POST .../contacts/batch/read`).
**Why it happens:** The search endpoint is a query/filter endpoint; property-history is scoped
to a specific known object id, which search-before-match does not yet have.
**How to avoid:** The ingest lane's flow already resolves an object id via search BEFORE the
merge step runs (identity resolution happens first) — so a second, targeted `batch/read` (or
single-object GET) call for the resolved id(s), requesting `propertiesWithHistory` for exactly
the `stale_refreshable` field set, is architecturally straightforward: it slots in after
identity resolution and before `Merge Contacts`/`Merge Company`, as one more HTTP node feeding
the existing Merge-node pattern this workflow already uses extensively (per CLAUDE.md §13.0.3).
**Warning signs:** A gate that "just works" in an offline unit test (which can inject any
existing-record shape it likes) but has never actually threaded a live `propertiesWithHistory`
value through the real HTTP call graph.

### Pitfall 3: the three `stale_refreshable` gate branches are IDENTICAL blanket refusals, not a partial implementation
**What goes wrong:** It's tempting to read "extend the recency logic" as if TTL-awareness
already exists and needs a tweak. It does not: `mergeContacts.js:143-145`,
`mergeCompanies.js:217-219`, and `merge_policy.py`'s equivalent branch (~line 240-249) each
read `if (_isBlank(currentValue)) promote; else needs_review` — `stale_after_days` is never
read inside any of the three. The ONLY place `stale_after_days` is consulted today is
`enrichmentGate.js::decideAction` (a completely different function, gating enrich-vs-skip on
the pipeline's OWN `lv_<field>_verified_at` cache-key property, not on the merge decision or on
HubSpot's native property history).
**Why it happens:** The comment literally says `"Refresh candidate requires review in MVP."` —
this was always a placeholder.
**How to avoid:** Budget this as new logic, not a tweak; write it once and mirror it three ways
under the Phase 46 parity rule in one commit, with a shared fixture/test vector exercised
against all three (mirrors how `tests/test_field_policy_conformance.py` already cross-checks
policy shape).

### Pitfall 4: company-side geo/phone/domain candidates don't exist yet
**What goes wrong:** Unlike contacts (where all three providers already push `city`/`state`/
`country`/code fields, mobile, seniority, and persona), the COMPANY branches of
`normalizeProviders.js` push only `country`/`city` (no `state`, no `hs_state_code`/
`hs_country_region_code`, no `phone`) and the `Merge Company` candidate loop in
`build_cloud_workflows.py` (~line 3813-3838) reads only `domain, industry, lv_revenue_band,
lv_employee_band, lv_country_region_normalized, country, city, numberofemployees` — no `state`,
no code fields, no `phone`, no second domain. D-72-14/15 will not "just work" once policy
entries are added; new producer code is required in at least one provider branch per field, or
the field ships with a documented, accepted no-producer gap (the existing precedent is company
`domain` itself: see `.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-
source.md`, reviewed and left open in this very phase's CONTEXT.md).
**Why it happens:** the fields were never asked for on companies before.
**How to avoid:** decide per field, at plan time, whether a real live provider response
(ZoomInfo GTM company enrich, Apollo org record, Lusha company record) actually carries a
usable value before writing normalizer code — `normalizeProviders.js`'s own comments already
note several fields ZoomInfo/Apollo never populate live (e.g. "ZoomInfo company enrich requests
no city outputField" — 58-05), so a blind port risks dead code exercised by no live traffic.
**Warning signs:** a policy entry with `promote_to_canonical: true` and zero producers anywhere
in `normalizeProviders.js` — permanently unreachable, the exact shape the `lv_persona_group`/
`lv_linkedin_url` "single-producer, permanently blank for unmatched contacts" risk already
accepted under T-66-04 for a different field.

**Portal-side correction, checked directly against the live company property export
(`docs/hs_props/.../company.csv`, same 2026-08-26 export used for contacts above) — this
narrows the gap to producer code only, not property existence, for THREE of the four fields,
but leaves `hs_country_region_code` on companies unconfirmed:**
- `phone` — present, writable.
  [VERIFIED: docs/hs_props/hubspot-properties-export-contacts-19-other-objects-2026-08-26/
  company.csv — `"Phone Number","phone","string","Company primary phone number.",
  "companyinformation","true","","false",...` (Read only value = `false`, the 8th field)]
- `state` — present, writable.
  [VERIFIED: same file — `"State/Region","state","string","State or region in which the
  company or organization is located.","companyinformation","true","","false",...`]
- `hs_state_code` — present, writable.
  [VERIFIED: same file — `"State/Region Code","hs_state_code","string","The company's state
  or region code.","companyinformation","false","","false",...`]
- `hs_country_region_code` — **NOT found in this export at all.** CONTEXT.md's own "Portal
  facts (verified live 2026-09-12)" list for companies ("phone, city, state, country,
  hs_state_code, hs_additional_domains, address, zip") also does not name it — the two
  sources agree by omission, which is weak evidence of absence, not proof. **Before building
  the company half of D-72-15's ISO-code requirement, run a live `GET
  /crm/v3/properties/companies/hs_country_region_code` and confirm it exists** — if it does
  not, the company side of D-72-15 has one fewer target than the contact side, and the plan
  should say so rather than write to a property that may 404.
- `hs_additional_domains` — CONTEXT.md's live-2026-09-12 list names it present on companies,
  but it is likewise absent from this repo's own 2026-08-26 export. Same caveat as
  `hs_additional_emails` (Pitfall 1): confirm live before building D-72-14's second-domain
  write, and check its `modificationMetadata.readOnlyValue` the same way.

### Provider x field coverage for contacts (normalizeProviders.js, this session's read)

| Field | Lusha | Apollo | ZoomInfo |
|---|---|---|---|
| `mobilephone` | yes — `phoneType==="mobile"` [VERIFIED: n8n/code/normalizeProviders.js:302-308] | yes — `type==="mobile"` [VERIFIED: :423-431] | yes — dedicated `raw.mobilePhone` field [VERIFIED: :581-582] |
| `linkedin_url` | **no producer** (not present in the contacts branch read this session) | yes — `_linkedinHostOnly(person.linkedin_url)` [VERIFIED: :447-462] | **no producer, deliberate** — comment: "ZoomInfo gets NO linkedin_url push in this plan" [VERIFIED: :566, :604-611] |
| `seniority` | yes — `raw.jobTitle.seniority` [VERIFIED: :312-313] | yes — `person.seniority` [VERIFIED: :421] | yes — `raw.managementLevel[0]` [VERIFIED: :587-588] |
| `persona_group` | yes — `_personaGroup(raw.jobTitle.departments)` [VERIFIED: :319-321] | yes — `_personaGroup(person.departments)` [VERIFIED: :463-464] | **no producer** (no departments field returned) |
| `city`/`state`/`country` (names) | yes, all three [VERIFIED: :330-332] | yes, all three [VERIFIED: :466-468] | yes, all three [VERIFIED: :589-591] |
| `hs_state_code`/`hs_country_region_code` | `hs_country_region_code` yes (dedicated `country_iso2` field); `hs_state_code` only if already code-shaped, never observed live [VERIFIED: :333-338] | both only if already code-shaped; comment notes Apollo's own values are full names, "these two never fire from Apollo today" [VERIFIED: :469-479] | both only if already code-shaped [VERIFIED: :592-598] |

### Provider x field coverage for companies (this session's read — confirms the gap named above)

| Field | Lusha | Apollo | ZoomInfo |
|---|---|---|---|
| `country`/`city` (names) | both [VERIFIED: :371-378] | both [VERIFIED: :482-488] | `country` only — "ZoomInfo GTM company enrich requests no `city` outputField" [VERIFIED: :623-625] |
| `state` | **no producer** | **no producer** | **no producer** |
| `hs_state_code`/`hs_country_region_code` | **no producer** | **no producer** | **no producer** |
| `phone` | **no producer** | **no producer** | **no producer** |
| second/"additional" domain | **no producer** (the single `domain` field itself has no producer either — the pre-existing accepted gap) | **no producer** | **no producer** |

### Pitfall 5: `bounce_n8n_workflows.py` has no per-workflow selector
**What goes wrong:** D-72-18 says deploy AND bounce only `wf_contact_ingest_cloud`; the
existing `bounce_n8n_workflows.py` hardcodes all 5 workflow ids in one dict and bounces every
one unconditionally (deactivate then activate, no PUT). Since bounce does not push new content
(it reloads whatever is CURRENTLY stored), bouncing an untouched workflow is a content no-op —
but it is still a live state transition (brief deactivation) on 4 workflows this phase did not
intend to touch.
**Why it happens:** the script was written when every phase deployed the whole set.
**How to avoid:** either add an `--only` argument to `bounce_n8n_workflows.py` mirroring
`deploy_n8n_workflows.py`'s existing flag (small, low-risk addition — the script's own
docstring already frames bounce as mechanically necessary after any deploy, so a scoped
version is a natural extension), or explicitly accept "bounce all five, confirmed harmless
because content is diff-clean" as the phase's chosen approach and say so in the plan.
**Warning signs:** treating "the other 4 must diff clean" (D-72-18) as satisfied by NOT
running deploy on them, while still bouncing them — bouncing is safe only if their CONTENT is
also unchanged, which requires actually running the regenerate step and diffing, not skipping
it.

## Code Examples

### The ingest lane's current (narrow) candidate assembly — the thing to widen
```javascript
// scripts/build_cloud_workflows.py:395-421 (MERGE_CONTACTS, feeds BOTH cloud and local builds)
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
  const merged = mergeContacts({}, candidate, undefined,
    { source: "csv", confidence: 80, sourceByField });
  return { json: { ...row, merge: merged } };
});
```

### The enrichment lane's already-wide candidate assembly — the pattern to mirror
```javascript
// scripts/build_cloud_workflows.py:1958-1980 (ENRICH_MERGE, "Merge Winners" node)
const winners = row.scored.winners || {};
const candidate = {};
for (const f of ["email", "mobilephone", "phone", "jobtitle", "seniority",
                  "city", "state", "country", "hs_state_code", "hs_country_region_code"]) {
  if (winners[f] != null && String(winners[f]).trim() !== "") candidate[f] = winners[f];
}
const canonicalWinnerLinkedin = canonicalizeLinkedin(winners.linkedin_url);
if (canonicalWinnerLinkedin) candidate.lv_linkedin_url = canonicalWinnerLinkedin;
if (winners.persona_group != null && String(winners.persona_group).trim() !== "") {
  candidate.lv_persona_group = winners.persona_group;
}
const merged = mergeContacts(row.existingRecord || {}, candidate, undefined,
                             { source: "waterfall", confidence: 85 });
```

### The current `stale_refreshable` gap (identical in all three engines) — quote exact, not paraphrase
```javascript
// n8n/code/mergeContacts.js:141-146 (byte-identical shape in mergeCompanies.js:217-222
// and src/merge_policy.py's deterministic_gate, ~line 240-249)
if (fieldClass === "stale_refreshable") {
  if (_isBlank(currentValue)) {
    return { decision: "promote", reason: "Current value blank and candidate passed threshold." };
  }
  return { decision: "needs_review", reason: "Refresh candidate requires review in MVP." };
}
```
[VERIFIED: n8n/code/mergeContacts.js:141-146, n8n/code/mergeCompanies.js:217-222 — both read
this session]

### The company-side manual_protected correction clause to generalize (D-72-08's starting point)
```javascript
// n8n/code/mergeCompanies.js:167-176
function _isSystemCorrectable(policy, entry, currentValue, rowConflicted) {
  const sources = policy && policy.system_correctable_sources;
  if (!Array.isArray(sources) || sources.length === 0) return false;
  if (!entry || typeof entry !== "object") return false;
  if (sources.indexOf(entry.source) === -1) return false;
  if (_isBlank(entry.value) || _isBlank(currentValue)) return false;
  if (String(entry.value) !== String(currentValue)) return false;
  return rowConflicted === false;
}
```
[VERIFIED: n8n/code/mergeCompanies.js:167-176 — read this session]

### `strip_enrichment_extras` — confirms it becomes a no-op by construction, needs zero edit
```python
# operator-claude-plugin/scripts/preingest.py:902-921 (docstring + body)
def strip_enrichment_extras(rows, policy_path=None) -> list[dict]:
    extras = set(promotable_contact_props(policy_path)) - set(extraction.canonical_props())
    return [{k: v for k, v in row.items() if k not in extras} for row in rows]
```
[VERIFIED: operator-claude-plugin/scripts/preingest.py:917-921 — read this session. Once
`config/column_mapping.yaml`'s aliases cover the same 12 keys `promotable_contact_props()`
returns, `extras` is the empty set and this function returns its input unchanged — no code
change to this function is needed, only the YAML.]

## Discrete Values Confirmed This Session

- Contacts enrichment-lane REQUIRED set (12 keys, already includes everything D-72-01 asks
  the ingest lane to widen to):
  `["city", "country", "email", "hs_country_region_code", "hs_state_code", "jobtitle",
  "lv_linkedin_url", "lv_persona_group", "mobilephone", "phone", "seniority", "state"]`
  [VERIFIED: scripts/build_cloud_workflows.py:1880-1883]
- Companies enrichment-lane REQUIRED set (13 keys):
  `["industry", "numberofemployees", "lv_revenue_band", "lv_employee_band",
  "lv_country_region_normalized", "country", "city", "lv_org_type", "lv_produces_content",
  "lv_content_type", "lv_sponsorship_reliant", "lv_is_hardware_vendor",
  "lv_is_gambling_operator"]`
  [VERIFIED: scripts/build_cloud_workflows.py:2950-2953] — note `state`/`hs_state_code`/
  `hs_country_region_code`/`phone` are absent from even this widest existing companies list,
  confirming the Provider x field coverage table below.
- `DEFAULT_CONTACT_POLICY` (the JS engine's own default, mirroring `config/field_policy.yaml`):
  `{ email: {class:"fill_blank_only",min_confidence:80}, phone: {class:"fill_blank_only",
  min_confidence:80}, mobilephone: {class:"fill_blank_only",min_confidence:85}, jobtitle:
  {class:"stale_refreshable",min_confidence:75}, lv_linkedin_url:
  {class:"fill_blank_only",min_confidence:85}, seniority: {class:"system_owned",
  min_confidence:75}, lv_persona_group: {class:"system_owned",min_confidence:75}, city/state/
  country/hs_state_code/hs_country_region_code: {class:"fill_blank_only",min_confidence:80} }`
  [VERIFIED: n8n/code/mergeContacts.js:41-53]
- `hs_seniority`'s native enum vocabulary (confirms it is a DIFFERENT taxonomy from any
  provider's raw `seniority` string, and confirms no D-72 decision asks this phase to populate
  it — see Open Questions #2):
  `"VP (vp); Director (director); Entry (entry); Executive (executive); Manager (manager);
  Owner (owner); Partner (partner); Senior (senior); Employee (employee)"`
  [VERIFIED: docs/hs_props/hubspot-properties-export-contacts-19-other-objects-2026-08-26/
  contact.csv — the `hs_seniority` row's Options column]

## Provenance Shape (existing — D-72-13 builds on this, does not invent it)

**Two DIFFERENT property names, not one** — CONTEXT.md's D-72-13 names `lv_enrichment_
provenance` as the stamp for "source/confidence/timestamp per landed slot," but that is the
COMPANIES key. Contacts use a different property entirely:

- Contacts: `lv_contact_enrichment_provenance`
  [VERIFIED: n8n/code/mergeContacts.js:27 — comment: "the caller ... serializes it ONCE via
  stableStringify() into `lv_contact_enrichment_provenance`"; confirmed at the write site
  `scripts/build_cloud_workflows.py:450` — `patch.lv_contact_enrichment_provenance =
  _stableStringify(merge.provenance).slice(0, 60000);`; confirmed distinct from companies at
  `scripts/build_cloud_workflows.py:10235` — "a different property from the companies one"]
- Companies: `lv_enrichment_provenance`
  [VERIFIED: n8n/code/mergeCompanies.js:13 — comment names it; read site
  `n8n/code/mergeCompanies.js:262` — `_parseProvenanceEntries(existingProps.lv_enrichment_
  provenance)`; write site `scripts/build_cloud_workflows.py:4277` — `properties.lv_
  enrichment_provenance = stableStringify(outgoingProvenance).slice(0, 60000);`]
- Python oracle mirrors both under two named constants:
  [VERIFIED: src/merge_policy.py:40-41 — `COMPANY_PROVENANCE_KEY = "lv_enrichment_
  provenance"` / `CONTACT_PROVENANCE_KEY = "lv_contact_enrichment_provenance"`]

**Per-field entry shape** (identical construction in both JS engines):
```javascript
// n8n/code/mergeContacts.js:220-221 (mergeCompanies.js's entry construction is the same shape)
const entry = { source: resolvedSource, confidence, verified_at: verifiedAt,
                validation_status: validationStatus, value };
if (!_isBlank(evidenceUrl)) entry.evidence_url = evidenceUrl;
```
[VERIFIED: n8n/code/mergeContacts.js:220-224]

**Planner action:** D-72-13's "no new per-field `_source`/`_verified_at` properties, provenance
JSON only" reads correctly against BOTH keys once the name is corrected for contacts — the plan
must write to `lv_contact_enrichment_provenance` for the new contact slots (`lv_phone_2`,
`lv_mobilephone_2`, the multi-value email/phone winner+loser stamps) and to `lv_enrichment_
provenance` for the company slot (`lv_phone_2` on companies). Using the wrong key name for
contacts would silently create a THIRD provenance property nobody reads.

## Integration Points (confirmed call sites)

- `preingest.strip_enrichment_extras` is called at exactly two sites in the plugin, both
  immediately before `strip_row_id`/dispatch, matching the module's own docstring:
  - `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:1025` —
    `sendable_rows = preingest.strip_enrichment_extras(sendable_rows)`
  - `operator-claude-plugin/skills/review-triage/SKILL.md:292` —
    `create_rows = preingest.strip_enrichment_extras(create_rows)`
  [VERIFIED: both lines read this session via grep + context lines 1025/1157 and 292/299 of
  the respective SKILL.md files]
  A repo-wide grep of `operator-claude-plugin/scripts/` for the same symbol found no other
  caller — the function's only production callers are these two SKILL.md sites.
- Current plugin version: `0.48.0`
  [VERIFIED: operator-claude-plugin/.claude-plugin/plugin.json — `"version": "0.48.0"`]
  Per project memory (`plugin-release-requires-version-bump`), a code change to `preingest.py`
  (D-72-05's merge rule) or `extraction.py`/`column_mapping.yaml` without a version bump ships
  as an invisible update in the Claude Desktop plugin marketplace UI — the plan should include
  a bump to `0.49.0`+ with a CHANGELOG entry as its own closing task, not an afterthought.

## Two open forks the planner must resolve, not compute later

### Fork 1: the `linkedin_url` / `lv_linkedin_url` name mismatch is the ACTUAL mechanism of F71-5, and D-72-01's "no-op by construction" claim does not resolve it by itself

The CSV-side canonical name is `linkedin_url` [VERIFIED: config/column_mapping.yaml —
`aliases: ... linkedin_url: linkedin_url` and 4 more headers mapping to it]. The waterfall's
promotable name is `lv_linkedin_url` [VERIFIED: config/field_policy.yaml — `contacts:
lv_linkedin_url: class: fill_blank_only ...`]. These are two DIFFERENT strings, so simply
taking the set union (`promotable_contact_props() | canonical_props()`, which is what
`merge_enriched`'s `allowed_keys` already does today) does not make the strip's drop-set
empty for this field — `lv_linkedin_url` is in `promotable - canonical` regardless of how wide
`canonical_props()` grows, unless `canonical_props()` is made to include the literal string
`lv_linkedin_url` too. Two ways to close this, with different blast radii:

- **Option A — add `lv_linkedin_url` as a second, distinct canonical CSV column.**
  `column_mapping.yaml`'s aliases would map some header (or the same `linkedin_url` family)
  to a NEW canonical value `lv_linkedin_url` alongside the existing `linkedin_url` value. This
  cascades: `required_identity.any_of` currently reads `[linkedin_url]` (not
  `[lv_linkedin_url]`) [VERIFIED: config/column_mapping.yaml:60-64], so `requiredIdentity()`
  in `columnMap.js` and `identity_groups()`/`has_identity()` in `extraction.py` would need to
  decide whether a row carrying only `lv_linkedin_url` (no `linkedin_url`) still satisfies
  identity — almost certainly yes, since it's the same fact under two names, but that is a
  behavior decision, not a mechanical rename. The ingest lane's `MERGE_CONTACTS` wrapper
  currently reads `row.linkedin_url` only [VERIFIED: scripts/build_cloud_workflows.py:414-416]
  — it would need to also read `row.lv_linkedin_url` and decide precedence when a CSV column
  supplies one and the waterfall supplies the other (this is a smaller instance of the
  recency problem, scoped to one field).
- **Option B — `merge_enriched` renames the provider response's `lv_linkedin_url` onto the
  row's existing `linkedin_url` key** before/while merging, treating them as the same logical
  field under the CSV-side name. No column_mapping.yaml or identity-rule change; the existing
  `row.linkedin_url` reads throughout the ingest lane keep working unmodified. The rename is a
  small, local addition to `merge_enriched`'s per-field loop (a one-entry alias table,
  `{"lv_linkedin_url": "linkedin_url"}`, checked before the `allowed_keys` filter).

The folded todo explicitly left this as "pick one" (see 72-CONTEXT.md's canonical_refs quoting
it: "rename the ingest header/alias to `lv_linkedin_url` or map `linkedin_url` -> `hs_linkedin_url`
in the lane; pick one, pin with the YAML/JS parity test"). **Option B is the smaller diff and
the one consistent with D-72-02's "ONE source of truth, no second list" spirit** — it changes
zero config files, only `merge_enriched`'s internal field-name reconciliation. Recorded here as
a recommendation, not a re-opening of a locked decision, since CONTEXT.md does not name this
fork explicitly.

### Fork 2: D-72-05's `source_values` on the held row may collide with "held-entry keys ... untouched"

D-72-05 says the CSV value on a CREATE conflict is "recorded as a conflict (merge report +
`source_values` **on the held row**...)" — but CONTEXT.md's own "Carried forward — NOT
reopened" section states: "D-70-11, D-71-01..05 — verdicts, facets, **held-entry keys** and
stamp untouched." The held-entry schema today is exactly five keys with no `source_values`
member: [VERIFIED: operator-claude-plugin/scripts/held_queue.py:508-513 — `entry = {
"hold_code": ..., "reason": ..., "observed_signals": ..., "resume_fingerprint": ...,
"row": ..., }`, plus an optional `company_known`]. Adding `source_values` as a sixth,
ADDITIVE key would not rename or remove any of the five untouched keys — but it IS a change to
"the held-entry schema," and D-71-04/05 (also carried-forward) is specifically about that
schema. **This is a real tension between two locked decisions, not a research gap** — flagging
it so the plan either (a) reads "held-entry keys ... untouched" as "the existing five keys
keep their meaning," allowing an additive sixth key, or (b) puts `source_values` in the merge
REPORT only (which already has a `conflicts` list, per `preingest.merge_enriched`'s existing
`MergeResult.conflicts` tuple) and never on the persisted held-row entry at all, satisfying
D-71-04/05 literally. Recommend (b) as the lower-risk reading unless the operator says
otherwise at plan time — CONTEXT.md's D-72-05 wording ("merge report + `source_values`") can be
read as one compound requirement (report AND row) or a slight overstatement of what's actually
needed (report is sufficient evidence for "never silently lost").

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase (no string is being renamed
across systems). Omitted per the template's own trigger condition.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `hs_additional_emails` is writable via a standard PATCH to `/crm/v3/objects/contacts/{id}` on this portal, as CONTEXT.md's live-verified note states | Pitfall 1, D-72-10 | If actually read-only (as multiple community reports for other portals claim), D-72-10's whole multi-email mechanism silently no-ops; the D-72-17 live gate would need to catch this via a re-read, not just a 200 response. |
| A2 | `POST /crm/v3/objects/contacts/batch/read` reliably supports `propertiesWithHistory` on this account, despite community reports of intermittent 400s on the batch form | Pitfall 2, D-72-07 | If it does not work reliably, the fallback is the single-object GET per contact — more HTTP calls, but the documented-working path; either way this needs a live probe before the recency gate is built, not after. |
| A3 | At least one of ZoomInfo/Apollo/Lusha's live company response actually carries a company phone number, a company state, or a code-shaped country/state value, given none of the three currently have a producer for these | Pitfall 4, D-72-14/15 | If none of the three ever supply these fields live, the new policy entries are permanently unreachable — same shape as the pre-existing `lv_persona_group`/`lv_linkedin_url` single-producer risk (T-66-04), acceptable if documented, a wasted effort if not checked first. |
| A4 | `bounce_n8n_workflows.py` bouncing all 5 workflows when only 1 changed is operationally harmless (deactivate+activate reloads unchanged stored content) | Pitfall 5, D-72-18 | If a bounce of an unrelated workflow interrupts an in-flight execution on it, this could cause an unrelated failure at exactly the wrong moment (during the phase's own live gate window). |

**If this table is empty:** N/A — see above.

## Open Questions

1. **What exact per-field diff does D-72-01 need in `column_mapping.yaml`?**
   - What we know: `promotable_contact_props()` currently returns the 12 keys from
     `config/field_policy.yaml`'s `contacts:` block (email, city, state, country,
     hs_state_code, hs_country_region_code, phone, mobilephone, jobtitle, lv_linkedin_url,
     seniority, lv_persona_group). `canonical_props()` currently returns 8 (company,
     company_id, email, firstname, jobtitle, lastname, linkedin_url, phone).
   - What's unclear: whether `firstname`/`lastname`/`company`/`company_id` (identity/routing
     keys with no `field_policy.yaml` entry) should remain untouched aliases alongside the
     newly-added 8 (city, state, country, hs_state_code, hs_country_region_code, mobilephone,
     seniority, lv_persona_group) — i.e., is the final canonical set 12 + 4 = 16, or does
     `promotable_contact_props()` need those 4 identity keys folded in too?
   - Recommendation: compute this exact list at plan time with a one-line script
     (`set(promotable_contact_props()) - set(canonical_props())`) rather than hand-counting;
     it is cheap and removes any ambiguity before the YAML is edited.

2. **Does `hs_seniority` (the native enum) need syncing, or does the phase stop at the
   existing custom `seniority` (free text)?**
   - What we know: no D-72 decision mentions `hs_seniority`; the folded todo's superseded
     mapping table flagged it "map only if the vocabulary matches" but that table is
     explicitly superseded by D-72-01..16.
   - What's unclear: whether this is a deliberate scope cut or an oversight.
   - Recommendation: treat as OUT OF SCOPE per the locked decisions (no D-72-* item names
     it) — the existing custom `seniority` property is already `system_owned` and already
     flows through both lanes once D-72-01 lands. Flag to the operator only if asked.

3. **The `linkedin_url`/`lv_linkedin_url` fork (Option A vs Option B) — see "Two open forks"
   above.** Recommend Option B (rename inside `merge_enriched`) but this needs an explicit
   plan-time choice, not a default.

4. **The `source_values`-on-held-row vs. "held-entry keys ... untouched" tension — see "Two
   open forks" above.** Recommend keeping `source_values` in the merge report only, never on
   the persisted held-row entry, unless the operator says otherwise.

5. **Does `hs_country_region_code` exist as a company property on this portal at all?**
   Absent from both this repo's 2026-08-26 company export and CONTEXT.md's 2026-09-12
   company-props list. Confirm with a live `GET /crm/v3/properties/companies/hs_country_
   region_code` before the company half of D-72-15 is built — if absent, the plan should
   scope D-72-15's company side to `state`/`hs_state_code` only, or add the property first.

6. **Does `hs_additional_domains` (companies) or `hs_additional_emails` (contacts) actually
   accept a write via `PATCH .../properties`?** See Pitfall 1 and the company-side note under
   Pitfall 4 — both are absent from this repo's own 2026-08-26 export despite CONTEXT.md's
   later live-verified claim, and `hs_additional_emails` specifically has multiple community
   reports of being read-only via the standard v3 API on other portals. Verify both with a
   live property-metadata GET (`modificationMetadata.readOnlyValue`) plus one scratch-record
   write-then-reread before D-72-10/D-72-14 code is written, not after.

7. **Todo triage (§31):** `.planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-
   enrichment-extras-map-them-instead.md` must move to `completed/` with its resolution when
   this phase closes, and `scripts/todo_triage.py --check` must pass — the plan's closing wave
   should include this move plus the plugin version bump (see Integration Points above) as
   explicit tasks, not implicit phase-close housekeeping.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| HubSpot CRM v3 API (`/crm/v3/properties/*`, `/crm/v3/objects/contacts/*`) | Property creation, live gate | Requires live credentials at execution time; not available in this research session | n/a | none — this is the one hard dependency; D-72-17's gate is explicitly backloaded to the end of the phase for exactly this reason |
| n8n Cloud API (`N8N_URL`/`N8N_API_KEY`) | Deploy/bounce of `wf_contact_ingest_cloud` | Not available in this research session (env-gated scripts print "skipped (no n8n creds)") | n/a | none — deploy is deferred to the operator, per repo convention |
| `.venv/bin/python` (pytest) | Python test suite | Assumed present per project memory (`test-suite-run-commands`) | n/a | n/a |
| `node --test` | JS test suite | Assumed present (repo-standard) | n/a | n/a |

**Missing dependencies with no fallback:** live HubSpot/n8n credentials — expected; every write
in this phase is deliberately deferred to an armed, operator-run window (D-72-17/18).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, `.venv/bin/python -m pytest`) + Node's built-in `node:test` |
| Config file | none dedicated found at repo root; existing test files run directly |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py tests/test_merge_policy.py -q` and `node --test tests/n8n/mergeContacts.test.mjs tests/n8n/mergeCompanies.test.mjs tests/n8n/columnMap*.test.mjs` |
| Full suite command | `.venv/bin/python -m pytest` (root) and `node --test tests/n8n/*.test.mjs` (glob form — directory form broken on node 24, per project memory) |

### Phase Requirements -> Test Map
| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|--------------------|-------------|
| D-72-01/02/03 | Widened alias table accepts mobile->mobilephone, geo, seniority, persona headers | unit | `node --test tests/n8n/columnMapAliasParity.test.mjs tests/n8n/columnMapIdentityParity.test.mjs` | ✅ exists, needs new cases |
| D-72-01 | Ingest lane's `Merge Contacts` candidate includes the widened set | unit | `node --test tests/n8n/mergeContacts.test.mjs` | ✅ exists — needs a new test asserting the CANDIDATE ASSEMBLY (the `MERGE_CONTACTS` wrapper logic), which today's file likely only exercises `mergeContacts()` itself, not the wrapper's field-loop — ⚠️ Wave 0 gap likely (confirm at plan time) |
| D-72-01 | `strip_enrichment_extras` returns rows unchanged once YAML widens | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -k strip_enrichment_extras` | ✅ file exists; confirm the specific test name at plan time |
| D-72-04 | LinkedIn lands as BOTH `hs_linkedin_url` and `lv_linkedin_url` | unit | `node --test tests/n8n/mergeContacts.test.mjs` | ❌ new assertion needed |
| D-72-05 | On CREATE, provider wins over CSV for non-identity fields, recorded as a conflict | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py` | ❌ new test needed |
| D-72-06/07/08/09 | Recency gate: stale non-blank overwritten by newer provider observation; fresh non-blank protected | unit (all 3 engines) | `.venv/bin/python -m pytest tests/test_merge_policy.py` + `node --test tests/n8n/mergeContacts.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ new tests needed, all 3 engines, Phase 46 parity |
| D-72-10/11/12/13 | Multi-value slot routing (winner/loser by trust_rank), provenance-only stamping | unit | `node --test tests/n8n/mergeContacts.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ new tests needed |
| D-72-14/15 | Company geo/phone/domain candidates reach the Merge Company gate | unit | `node --test tests/n8n/normalizeProviders.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ new producer + tests needed |
| SAFE-01 (carried) | No `fill_blank_only`/`min_confidence` weakened anywhere touched | regression | full suites above, both languages | ✅ existing SAFE-01 pins must stay green |
| D-72-18 | Regenerated JSON for the 4 non-ingest workflows diffs clean against live | integration (manual/scripted) | `git diff --stat n8n/wf_enrichment_cloud.json n8n/wf_review_decision_cloud.json n8n/wf_scheduled_maintenance_cloud.json n8n/wf_backend_status_cloud.json` after running `scripts/build_cloud_workflows.py` | n/a — a diff check, not a pytest/node test |

### Sampling Rate
- **Per task commit:** the quick-run subset above, scoped to whichever engine(s)/module(s)
  the task touched.
- **Per wave merge:** full suites — `.venv/bin/python -m pytest` and
  `node --test tests/n8n/*.test.mjs` — both must stay green (existing baseline per STATE.md:
  thousands passing, 0 failing).
- **Phase gate:** full suite green BEFORE the D-72-17 live gate is attempted; the live gate
  itself (`/gsd-verify-work`) is the one Nyquist-exempt manual step, backloaded per operator
  ruling 2026-09-09.

### Wave 0 Gaps
- [ ] Confirm whether `tests/n8n/mergeContacts.test.mjs` exercises `MERGE_CONTACTS`'s WRAPPER
  candidate-assembly loop (the thing D-72-01 widens) or only `mergeContacts()` itself — if
  only the latter, a new test harness that extracts and runs the wrapper's field-loop logic
  is needed (mirrors how `columnMapIdentityParity.test.mjs` drives a JS function from a
  Python-YAML oracle).
- [ ] No existing test exercises `stale_after_days`/recency inside any of the three engines'
  gate — this is the phase's core new behavior and needs fixtures for: (a) stale non-blank ->
  overwrite, (b) fresh non-blank -> protect, (c) no verified_at/history at all -> current
  behavior (treat conservatively per existing "unknown freshness == needs validation" idiom
  in `enrichmentGate.js`).
- [ ] No existing test exercises the D-72-12 winner/loser-to-`_2`-slot routing.
- [ ] `config/hubspot_properties.yaml` has no entries yet for `lv_phone_2`, `lv_mobilephone_2`
  (contacts), `lv_phone_2` (companies) — add before running `sync_hubspot_properties.py`.

*(If no gaps: N/A — gaps listed above.)*

## Security Domain

`security_enforcement: true` in `.planning/config.json` — this section is required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface — HubSpot private-app token and n8n API key are existing, unchanged credentials. |
| V3 Session Management | no | N/A — no session concept in this phase. |
| V4 Access Control | yes | Property writes remain gated behind the existing env-flag pattern (`DRY_RUN`, `ALLOW_HUBSPOT_PROPERTY_WRITES`, `ALLOW_N8N_ARM`) — no new write path should bypass these; the D-72-11 property-creation script must use the SAME two-key gate idiom as `sync_hubspot_properties.py`/`set_named_account_score_floor.py`. |
| V5 Input Validation | yes | `write_dispatch_csv`'s STRUCT-01 allowlist guard (widened, never removed) remains the input-validation control at the plugin/n8n boundary — a row key outside the canonical set must still raise, not silently pass through. |
| V6 Cryptography | no | No cryptographic operation introduced. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A widened candidate set silently promotes a low-confidence/unvalidated value that previously would have been stripped before reaching HubSpot | Tampering | `min_confidence` per field in `config/field_policy.yaml` — unchanged by this phase (SAFE-01); every new field must get an explicit threshold, never a default fallthrough. |
| A recency/TTL mechanism reads a manipulable or spoofable timestamp (e.g. a CSV-supplied "observed_at" the operator could backdate) to justify overwriting a HubSpot value | Tampering/Repudiation | D-72-07 already specifies the ONLY two legitimate timestamp sources (the pipeline's own dispatch clock; HubSpot's own property-history) — a CSV value explicitly "carries no time and ranks oldest", closing this exact injection vector by design. Do not add a third, operator-suppliable timestamp source. |
| A property-creation script left armed (env flags set) outside its intended one-time run | Elevation of Privilege | Same two-key gate as existing scripts (`DRY_RUN=false` AND a dedicated `ALLOW_*` flag) — never reuse a broader existing flag like `ALLOW_N8N_ARM` for a HubSpot schema write, which is a different privilege boundary. |

## Sources

### Primary (HIGH confidence) — read this session
- `.planning/phases/72-enrichment-extras-land-in-hubspot/72-CONTEXT.md` — locked decisions D-72-01..18
- `.planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-UAT.md` — F71-5, the operator rulings verbatim
- `.planning/todos/pending/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md`
- `config/field_policy.yaml`, `config/column_mapping.yaml`, `config/source_registry.yaml`
- `n8n/code/columnMap.js`, `tests/n8n/columnMapIdentityParity.test.mjs`
- `n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `n8n/code/normalizeProviders.js`, `n8n/code/enrichmentGate.js`
- `src/merge_policy.py`
- `operator-claude-plugin/scripts/extraction.py`, `operator-claude-plugin/scripts/preingest.py`
- `scripts/build_cloud_workflows.py` (MERGE_CONTACTS ~L395-421, ENRICH_MERGE ~L1946-1988, ENRICH_GATE/ENRICH_CO_GATE REQUIRED lists ~L1852-1882/2949-2953, Merge Company candidate loop ~L3796-3860)
- `scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py`
- `scripts/sync_hubspot_properties.py`, `config/hubspot_properties.yaml`, `scripts/set_named_account_score_floor.py`
- `docs/hs_props/hubspot-properties-export-contacts-19-other-objects-2026-08-26/contact.csv` (live portal property export)
- `CLAUDE.md` §4.0, §6.1, §9, §13.0.1, §13.0.2, §13.0.3, §17.2.1, §29.1, §31

### Secondary (MEDIUM confidence)
- WebSearch: HubSpot's own developer-docs pages and community threads confirming
  `propertiesWithHistory` support boundary (search endpoint: no; single-object GET: yes;
  batch/read: documented yes, community-reported intermittent issues)

### Tertiary (LOW confidence) — flagged, not relied upon
- WebSearch: HubSpot Community threads reporting `hs_additional_emails` as read-only via
  standard v3 API — contradicts CONTEXT.md's live-verified claim; flagged in Pitfall 1 and
  Assumption A1, not treated as settled either way

## Metadata

**Confidence breakdown:**
- Config/candidate-widening path (D-72-01..04): HIGH — every file and line read this session,
  the enrichment lane already proves the pattern works in production.
- Recency/TTL mechanism (D-72-06..09): MEDIUM — the current-state gap is confirmed HIGH
  confidence (read all three engines), but the propertiesWithHistory fetch design is a new
  build with no existing precedent in this repo to mirror.
- Multi-value slots (D-72-10..13): MEDIUM-LOW — mechanism is clear (property script + trust
  rank + provenance blob, all existing patterns), but `hs_additional_emails` writability is
  an open, contradicted claim (see Pitfall 1).
- Company geo/phone/domain (D-72-14/15): MEDIUM — the gap is confirmed HIGH confidence (no
  producers exist), but whether live provider data will actually populate the new fields is
  unverified without a live probe.

**Research date:** 2026-09-12
**Valid until:** ~14 days (fast-moving repo, active phase-by-phase development; also
contingent on the operator re-verifying the `hs_additional_emails` portal fact live before
D-72-10 is built)
