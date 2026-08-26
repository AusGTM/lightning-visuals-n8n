---
phase: 58-take-what-the-operator-actually-has
plan: 05
subsystem: enrichment-pipeline
tags: [n8n, hubspot, native-properties, non-clobber-merge, company-lane]

requires:
  - phase: 58-03-domain-confirm-walk
    provides: "operator ruling authorizing native country/city/numberofemployees writes and lifting CLAUDE.md §29's numberofemployees ban for this lane"
  - phase: 58-04-price-and-decline-domain-research
    provides: "sibling work landed in the same phase; no direct code dependency"
provides:
  - "native `country`/`city`/`numberofemployees` candidates on all three company provider branches of normalizeProviders.js"
  - "fill_blank_only classification for the three fields, mirrored in config/field_policy.yaml and mergeCompanies.js's DEFAULT_COMPANY_POLICY"
  - "the Merge Company candidate-building allowlist fix -- the write-map choke point this plan's own gap_closure_context did not name"
  - "live disarmed proof (exec 11980) that the derived patch carries all three native fields"
  - "the Series Futsal Victoria retro-fix determination: reachable via a plain re-enrich, no gate widening needed"
affects: []

actuals:
  tokens: 9391
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "numeric-only candidate guard (_numericHeadcount) -- admits a value only when already numeric, refusing a spaced range string rather than parsing/rounding/taking an endpoint from it"
    - "raw-value (winners[f]) merge candidate path for free-text native fields, mirrored from ENRICH_MERGE's contacts-side city/state/country loop -- distinct from the normalizedValue path the enum/band fields in the same node use"

key-files:
  created:
    - tests/n8n/companyNativeFields.test.mjs
    - tests/test_company_native_properties.py
    - .planning/phases/58-take-what-the-operator-actually-has/deferred-items.md
  modified:
    - n8n/code/normalizeProviders.js
    - n8n/code/mergeCompanies.js
    - config/field_policy.yaml
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/fixtures/companies_jscode_frozen.json
    - tests/n8n/enrichment.test.mjs
    - CLAUDE.md

key-decisions:
  - "Value shape for `country`: full country NAME (e.g. \"Australia\"), not an ISO2 code -- live evidence (execs 11929/11932/11975/11979) shows all three providers already carry a full-name country field alongside any ISO2 code, and a live portal check of 10 real companies confirmed the existing `country` property already holds full names, never codes."
  - "The Merge Company node's candidate-building loop (`ENRICH_MERGE_CO`, ~line 2894 of scripts/build_cloud_workflows.py) is a SECOND write-map allowlist the plan's gap_closure_context did not identify -- candidates from normalizeProviders.js would have been silently dropped there before ever reaching mergeCompanies(). Found and fixed in Task 1 (deviation, see below)."
  - "numberofemployees reclassified stale_refreshable -> fill_blank_only in both engines (operator ruling 58-03 item (b)); CLAUDE.md §29 amended with a scoped as-built delta rather than left contradicting shipping code."
  - "ZoomInfo's companies branch gets no `city` candidate -- ZOOM_CO_OUTPUT_FIELDS never requests a city outputField and none of 4 sampled live executions carried one. Documented as a correct absence in code comments and tests, not filled with a probe/extension (out of this plan's scope)."
  - "Series Futsal Victoria 283816805830 determination: REACHABLE. Live gate state (lv_org_type present+fresh, lv_produces_content BLANK) already computes decideAction() -> 'enrich', with no recompute flag and no gate-widening needed. Proven empirically by triggering the actual enrichment webhook against this exact record (exec 11980, disarmed) -- not merely predicted from source."

patterns-established:
  - "Live-evidence-first value-shape decisions: before wiring a native field, read the real running executions AND the real portal state so the shape choice reflects what actually flows and what the property already holds, not what the plan's context assumed."

requirements-completed: [INPUT-01]

coverage:
  - id: D1
    description: "country/city/numberofemployees candidates flow from all three provider branches to the HubSpot PATCH body, blank-fill only, proven offline"
    requirement: "INPUT-01"
    verification:
      - kind: unit
        ref: "tests/n8n/companyNativeFields.test.mjs (24 tests covering all three branches, all three fields, the numeric-headcount guard, the fill_blank_only class, and the write-map allowlist pins)"
        status: pass
    human_judgment: false
  - id: D2
    description: "the wiring is live and proven end-to-end on one disarmed execution against a real record, with no write occurring"
    requirement: "INPUT-01"
    verification:
      - kind: integration
        ref: "live execution 11980 (workflow 950HPb7a1GgSAIyZ), read directly from its own runData -- see 'Live Proof' section below"
        status: pass
    human_judgment: false
  - id: D3
    description: "the Series Futsal Victoria retro-fix is either reachable and offered, or a residual with a stated reason -- determined live, not assumed"
    requirement: "INPUT-01"
    verification:
      - kind: integration
        ref: "live gate-state read + decideAction() replay + confirming live-triggered execution 11980 -- see 'Series Futsal Victoria Determination' below"
        status: pass
    human_judgment: false
  - id: D4
    description: "operator decides whether to open a one-record armed write window for Series Futsal Victoria"
    verification: []
    human_judgment: true
    rationale: "An armed write to a real HubSpot record requires explicit, per-record operator authorization (T-58-25) -- this cannot be automated or auto-approved regardless of auto-chain mode."

duration: ~55min
completed: 2026-08-26
status: halted
---

# Phase 58 Plan 05: Native Company Fields (country/city/numberofemployees) Summary

**Native `country`, `city`, and `numberofemployees` now travel from provider payload to the HubSpot PATCH body on the company enrichment lane, blank-fill only, proven live on execution 11980 against Series Futsal Victoria itself -- and Task 4's operator decision on that record's retro-fix is the only thing left before this plan is complete.**

## Performance

- **Duration:** ~55min (Tasks 1-3; Task 4 is the open checkpoint)
- **Tasks:** 3 of 4 complete (Tasks 1-3 committed/executed; Task 4 is a blocking human-verify checkpoint, unresolved)
- **Files modified:** 12 across both commits (2 created test files, 1 created deferred-items.md, 9 modified)

## Accomplishments

- Wired `country` end to end (Task 1, tracer): Lusha `location.country`, Apollo `organization.country`, ZoomInfo GTM `attributes.country` all now produce a native `country` candidate alongside their existing `lv_country_region_normalized` derivation, classified `fill_blank_only` at confidence 75 in both engines.
- Extended to `city` and `numberofemployees` (Task 2): `city` from Lusha/Apollo (ZoomInfo requests no city outputField -- documented absence); `numberofemployees` guarded to admit only already-numeric values, never a spaced range string, on all three branches.
- **Found and fixed a write-map allowlist the plan's own gap_closure_context did not name**: `ENRICH_MERGE_CO`'s ("Merge Company" node) candidate-building loop only ever read a fixed list of fields out of `scoreCandidates()`'s output before calling `mergeCompanies()`. Without extending this loop, every candidate from Task 1/2's normalizeProviders.js changes would have been silently dropped before ever reaching the merge/canonical-patch stage -- upstream of the wholesale spread the plan did correctly identify at `ENRICH_DECIDE_CO_CLOUD`.
- Deployed all 5 live workflows, bounced the enrichment workflow (deactivate -> activate, independently re-read at each step), and proved the wiring live: execution `11980` against Series Futsal Victoria (`283816805830`) returned a fully derived patch carrying `country: "Australia"`, `city: "Brunswick"`, `numberofemployees: 13`, read directly from the execution's own runData -- disarmed, `action: "write_blocked"`, confirmed no write occurred by re-reading the live record afterward (still `null`/`null`/`null`).
- Determined the Series Futsal Victoria retro-fix question empirically rather than predicting it: the record's live gate state already computes `enrich` (missing `lv_produces_content`), so the exact webhook POST that produced the proof above IS the reachable path -- no recompute flag, no gate widening, no field-blanking workaround needed.

## Task Commits

1. **Task 1: One native field, end to end -- `country` from provider to patch body** - `f6327f1` (feat)
2. **Task 2: Expand along the proven path -- `city` and `numberofemployees`** - `e1b7878` (feat)
3. **Task 3: Deploy, bounce, and prove it on a live execution -- plus the retro-fix determination** - no code commit (deploy/bounce/trigger only; the code deployed was already committed in Tasks 1-2, so there was nothing new to commit). Evidence recorded in this SUMMARY.

**Plan metadata:** (this commit, following the SUMMARY)

## Files Created/Modified

- `n8n/code/normalizeProviders.js` - native `country`/`city`/`numberofemployees` candidates + `_numericHeadcount` guard, all three company branches
- `n8n/code/mergeCompanies.js` - `country`/`city` policy entries, `numberofemployees` reclassified
- `config/field_policy.yaml` - mirrored policy entries (Phase 46 parity rule)
- `scripts/build_cloud_workflows.py` - `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` extended (`country`,`city`); `ENRICH_MERGE_CO`'s candidate loop extended (the write-map fix)
- `n8n/wf_enrichment_cloud.json`, `wf_enrichment_local.json`, `wf_enrichment_local_live.json`, `wf_review_decision_cloud.json`, `wf_scheduled_maintenance_cloud.json` - regenerated via `scripts/build_cloud_workflows.py`, never hand-edited
- `tests/fixtures/companies_jscode_frozen.json` - re-baselined (Merge Company node changed; the other 6 frozen nodes byte-identical)
- `tests/n8n/companyNativeFields.test.mjs` (new) - 24 tests covering both tasks' behaviors
- `tests/n8n/enrichment.test.mjs` - 2 pre-existing field-set pins updated (deliberate, expected consequence of the new candidates)
- `tests/test_company_native_properties.py` (new) - live read-only property-existence check
- `CLAUDE.md` §29 - scoped as-built delta amendment
- `.planning/phases/58-take-what-the-operator-actually-has/deferred-items.md` (new) - pre-existing unrelated test flake, logged not fixed

## Per-provider company key-shape table (live evidence)

Pulled via plain `urllib` against workflow `950HPb7a1GgSAIyZ`'s executions API (per project
memory, `executions_client.py`'s `requests` transport fails in this environment). Sampled the
4 live company-branch executions available in the last 24h: `11929`, `11932`, `11975`, `11979`.

| Provider | country | city | numberofemployees source |
|---|---|---|---|
| Lusha (v3 companies) | `location.country` full name, present 2/4 (absent when Lusha found no match); dedicated `location.countryIso2` code also present alongside it | `location.city`, same 2/4 presence | `employeeCount` (already numeric via `_lushaV3Company`'s object reshaping) present 2/4 |
| Apollo (organization) | `organization.country` full name, present 4/4 | `organization.city`, present 4/4 | `organization.estimated_num_employees`, already a plain integer, present 4/4 |
| ZoomInfo (GTM companies/enrich) | `attributes.country` full name, present 4/4 (one execution returned "United States" for an AU company -- an existing provider data-quality issue, not introduced or corrected by this plan) | **never present** -- `ZOOM_CO_OUTPUT_FIELDS` requests no `city` outputField at all | `attributes.employeeCount`, already a plain integer, present 4/4 in this sample (the `employeeRange` spaced-string fallback is guarded off but untested against live traffic, since employeeCount was always present in the sample) |

**Value-shape decision:** write the full country/city NAME as-is (never derive or write an ISO
code) -- confirmed live: 10 real HubSpot companies checked (`GET /crm/v3/objects/companies/search`
filtered on `country HAS_PROPERTY`) all carry full names ("Australia"), never "AU". All three
providers already supply that exact shape for `country`; no derivation needed.

## Live Proof (execution `11980`, disarmed)

**Deploy:** `DRY_RUN=false ALLOW_N8N_DEPLOY=true` (via a scratchpad dotenv-loading runner, per
project convention -- `.env` is Read/Bash-blocked to this agent) updated all 5 live cloud
workflows (200 each): `LV Backend Status (Cloud template)`, `LV Contact Ingest (Cloud
template)`, `LV Enrichment (Cloud template)`, `LV Review Decision (Cloud)`, `LV Scheduled
Maintenance (Cloud)`. `git status --porcelain n8n/wf_*.json` was clean before the deploy
(already committed in Tasks 1-2) and clean after (deploy pushes committed content, no local
regeneration needed in this task).

**Bounce:** `POST /api/v1/workflows/950HPb7a1GgSAIyZ/deactivate` (200, `active: false`,
independently re-confirmed by a fresh `GET`) then `POST .../activate` (200, `active: true`,
independently re-confirmed by a fresh `GET`, `updatedAt: 2026-08-26T08:09:30.539Z` unchanged
across the bounce as expected -- activation toggling never moves `updatedAt`/`versionId`).

**Trigger:** one `POST /webhook/hubspot/enrichment/event` with
`{"providers":["zoominfo","apollo","lusha"],"events":[{"objectId":"283816805830","objectType":"company"}]}`
and the `X-Enrichment-Secret` header the webhook's Header Auth credential requires ->
**execution `11980`**, `success`, started `2026-08-26T08:10:43.761Z` -- AFTER the workflow's
`updatedAt` (08:09:30) and the bounce, so this execution ran the newly-deployed content, not
stale pre-deploy code.

**Read directly from execution 11980's own runData** (`Decide Company Action` node output,
`includeData=true` -- not a stored workflow read-back):

```json
{
  "action": "write_blocked",
  "properties": {
    "country": "Australia",
    "city": "Brunswick",
    "numberofemployees": 13,
    "lv_employee_band": "10-50",
    "lv_country_region_normalized": "AU",
    "lv_content_type": "live_broadcast;streaming",
    "lv_is_hardware_vendor": "false",
    "lv_is_gambling_operator": "false",
    "lv_anti_icp_flag": "false"
  }
}
```

- **All three native keys present**, sourced from the waterfall (confidence 85, `provider_only`
  in the provenance blob) -- `country`/`city` full names, `numberofemployees` a real number (13,
  not a string, not a range).
- **`industry` correctly ABSENT from the top-level patch** even though a candidate existed
  (`"arts, entertainment, and recreation"` from ZoomInfo/Claude web research, confidence 85) --
  the provenance blob shows `validation_status: "rejected"` for it, exactly the Phase 31 enum
  guard working as designed and re-confirmed by the operator. No key allowlist edit, no alias
  table, `git diff --stat n8n/code/hubspotEnums.js tests/n8n/industryNormalization.test.mjs` is
  empty.
- **No native key fired wrong or was fabricated** -- this specific execution did not exercise a
  live "provider carried no key" case for `country`/`city`/`numberofemployees` (Series Futsal
  Victoria happens to have full provider coverage on all three from every provider that supplies
  them). That absence guarantee is proven **offline** instead: `tests/n8n/companyNativeFields.test.mjs`
  pins the no-candidate-when-key-absent behavior per branch per field, and ZoomInfo's `city`
  absence is a structural fact of `ZOOM_CO_OUTPUT_FIELDS` (no outputField requested), confirmed
  by code inspection and the live sample above (4/4 executions, never a city key).
- **Confirmed no write occurred**: re-read the live company record immediately after (read-only
  `GET`) -- `country`/`city`/`numberofemployees` all still `null`, `hs_lastmodifieddate`
  unchanged at `2026-08-26T06:25:28.363Z` (predates the trigger). `action: "write_blocked"`
  was truthful.

**Execution actuals (cap 3, used 1):**
- 1 of 3 executions spent (`11980`).
- Lusha credits: 3903 before, 3903 after -- 0 delta, consistent with the known 0-credit
  stored-id re-enrich pricing (this company's `lusha_company_id` was already cached from an
  earlier execution today).
- Apollo/ZoomInfo credit-check endpoints returned `null`/degraded in this sample (a pre-existing,
  unrelated issue -- Apollo's credit-check key is not master per project memory; not investigated
  further here).
- Anthropic calls: `Claude Web Research`, `Validate Research Output`, `Judge Gate`/`Judge Call`,
  `Apply Judge Verdict` all ran in this execution -- the natural cost of a record with a genuinely
  missing `lv_produces_content`, exactly as the plan anticipated ("whatever the one enrichment
  execution naturally spends").
- No `ALLOW_HUBSPOT_*` or `ALLOW_N8N_ARM` flag was set at any point. Nothing was armed.

## Series Futsal Victoria Determination

**Company `283816805830`, read live (read-only) before Task 3's trigger:**

| Field | Value |
|---|---|
| `lv_org_type` | `"content_producer"` (present) |
| `lv_org_type_verified_at` | `2026-08-26T06:25:23.015Z` (fresh -- well inside the 180-day staleness window) |
| `lv_produces_content` | `null` (**missing**) |
| `lv_produces_content_verified_at` | `null` |
| `country` / `city` / `numberofemployees` | `null` / `null` / `null` |

**Gate verdict, replayed against exactly this state** (`enrichmentGate.js::decideAction`,
`REQUIRED = ["lv_org_type", "lv_produces_content"]`): `lv_produces_content` is blank ->
`missingFields` is non-empty -> **`action: "enrich"`**, reason `"missing: lv_produces_content"`.
The gate does **not** return `skip` for this record today.

**Conclusion: REACHABLE, and proven, not merely predicted.** A plain re-enrichment webhook POST
against this exact company -- no `recompute` flag, no gate-widening, no field-blanking
workaround -- IS enough, because this record already carries a genuine gap the gate itself
would route to `enrich`. Task 3's live proof execution (`11980`) **is** that reachable path: it
used exactly this plain trigger shape, reached the full merge/research pipeline, and derived
`country="Australia"`, `city="Brunswick"`, `numberofemployees=13` as the patch that WOULD write
if armed. Industry stays blank either way, by the upheld Phase 31 decision.

**What Task 4 needs to decide:** whether to open a single, record-scoped ARMED write window for
`283816805830` and re-run this exact same trigger (or an equivalent), so the derived patch above
is actually written to the live record. Nothing has been armed by this plan at any point --
Claude sets no arming flag, ever; that decision belongs to the operator alone (T-58-25).

## Decisions Made

- **Value shape for `country`/`city`: full name, not ISO code** -- see the key-shape table and
  live portal check above.
- **`ENRICH_MERGE_CO`'s candidate loop is a write-map allowlist the plan's own trace missed** --
  found and fixed in Task 1 (see Deviations below).
- **`numberofemployees` reclassified `stale_refreshable` -> `fill_blank_only`** in both engines,
  per operator ruling 58-03 item (b); `CLAUDE.md` §29 amended with a scoped as-built delta.
- **ZoomInfo's companies branch gets no `city` candidate** -- documented absence
  (`ZOOM_CO_OUTPUT_FIELDS` requests none), not a gap to close in this plan.
- **Series Futsal Victoria: reachable, proven live** -- see determination above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ENRICH_MERGE_CO`'s candidate-building loop silently dropped every new candidate**
- **Found during:** Task 1, while tracing the full path from `normalizeProviders.js` to the
  HubSpot PATCH body per the plan's own `key_links`.
- **Issue:** The plan's `gap_closure_context` identified `ENRICH_DECIDE_CO_CLOUD`'s wholesale
  `{ ...merge.canonicalPatch }` spread as having no key allowlist, and concluded "nothing in the
  write map needs editing." That is true for `ENRICH_DECIDE_CO_CLOUD` -- but ONE step earlier, the
  `"Merge Company"` node (`ENRICH_MERGE_CO`) builds its `candidate` object by reading only a
  fixed list of field names (`["domain", "industry", "lv_revenue_band", "lv_employee_band",
  "lv_country_region_normalized"]`) out of `scoreCandidates()`'s `best`/`winners` maps BEFORE
  ever calling `mergeCompanies()`. A `country`/`city`/`numberofemployees` candidate produced by
  Task 1/2's `normalizeProviders.js` changes would score correctly but never reach
  `mergeCompanies()` at all -- the write-map allowlist the plan's trace did not name.
- **Fix:** Added a second loop reading `country`/`city`/`numberofemployees` from
  `row.scored.winners` (the RAW provider value, mirroring `ENRICH_MERGE`'s identical contacts-side
  city/state/country loop -- deliberately NOT `best[f].normalizedValue`, which is lowercased for
  cross-source agreement matching and would have written `"australia"` instead of the portal's
  existing `"Australia"` shape).
- **Files modified:** `scripts/build_cloud_workflows.py` (`ENRICH_MERGE_CO`).
- **Verification:** `tests/n8n/companyNativeFields.test.mjs`'s mergeCompanies-level tests pass
  with real candidates; live execution `11980` proves the fix end to end -- `country`/`city`/
  `numberofemployees` all present in the derived patch.
- **Committed in:** `f6327f1` (Task 1 commit).

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Without this fix, Tasks 1-2's candidate-producer changes would have been
inert on the live path -- correct in unit tests, silently dropped in the real pipeline. No scope
creep: the fix is confined to the exact three fields this plan adds.

## Issues Encountered

- **Pre-existing test flake, not caused by this plan:** `tests/test_merge_policy.py` (4 tests)
  fails with `AttributeError: 'ThinkingBlock' object has no attribute 'text'` when the FULL
  pytest suite runs, but passes in isolation. Confirmed reproducible with this plan's entire
  diff `git stash`ed (clean state at the end of Task 1) -- identical failure, identical count.
  Logged to `deferred-items.md`, not fixed (out of scope).
- Several downstream `wf_*.json` files (`wf_review_decision_cloud.json`,
  `wf_scheduled_maintenance_cloud.json`) changed on regeneration even though this plan never
  touched their generator code directly -- traced to `_COMPANY_POLICY_FIELDS`, which derives
  the review-decision compare-and-set baseline from `config/field_policy.yaml`'s `companies`
  keys sorted. Adding `country`/`city` there is the CORRECT and intended propagation (the
  review-apply engine needs to fetch these two fields as part of its baseline, or a manual edit
  to them would misread as stale) -- not a bug, verified by reading the surrounding code comment
  that documents exactly this derivation.

## Known Stubs

None. Every field this plan wires (`country`, `city`, `numberofemployees`) is connected to real
provider data through the real merge/write pipeline, proven live on execution `11980`.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

Tasks 1-3 are complete, committed, deployed, and live-proven. **Task 4 is the sole remaining
item**: the operator must decide whether to open a one-record armed write window for Series
Futsal Victoria `283816805830`, per the determination above. This plan cannot be marked
`complete` (STATE.md/ROADMAP.md untouched by this SUMMARY) until Task 4 resolves -- a
continuation agent should read this SUMMARY's "Series Futsal Victoria Determination" section
directly rather than re-deriving it.

---
*Phase: 58-take-what-the-operator-actually-has*
*Completed: 2026-08-26 (Tasks 1-3; Task 4 pending)*
