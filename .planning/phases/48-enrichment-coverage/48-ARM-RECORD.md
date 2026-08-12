# Phase 48 Plan 05 -- Arm Record (D-06's one declared armed write window)

Durable pre-arm record for plan 48-05 Task 1, appended to by Task 3. Single home for the
whole window rather than living only in a summary written after the fact.

## Write-time population re-derivation (Task 1, 2026-08-13)

Re-derived live via `derive_population()` / `reconcile_population()` -- the exact
`lv_icp_fit_score HAS_PROPERTY AND lv_org_type NOT_HAS_PROPERTY` filter -- **at write time,
not reused from plan 01's evidence or CONTEXT.md's 2026-08-12 snapshot.**

```json
{
  "expected": ["15008671672", "17317381378", "17317850381", "20538284384", "20943964946"],
  "derived":  ["15008671672", "17317381378", "17317850381", "20538284384", "20943964946"],
  "missing": [],
  "unexpected": [],
  "drift": false
}
```

**Matches plan 01's derivation and CONTEXT.md's 2026-08-12 snapshot exactly** -- same 5
ids, same order, zero drift. Every one of the 5 records' live `lv_org_type` reads `null`
(never_attempted) as of this read, confirmed in `48-BEFORE.json`.

## The five exact dry-run PATCH payloads (Task 1, `--dry-run`, no write, no arm)

Printed verbatim by `scripts/enrich_coverage_companies.py`'s dry-run CLI path
(`decide_org_type` + `build_coverage_patch`) against the current `ORG_TYPE_DECISIONS`
table (Racing NSW corrected to `governing_body_league` by plan 48-07):

```
PATCH[15008671672]: {
  "lv_org_type": "governing_body_league",
  "lv_org_type_verified_at": "<stamped at write time>"
}
PATCH[17317381378]: {
  "lv_org_type": "unknown",
  "lv_org_type_verified_at": "<stamped at write time>",
  "lv_enrichment_review_reason": "Web searches for 'Editix edetrix.com.au', 'Editix broadcast streaming live', and 'edetrix.com.au OR Editix Australia media' returned no results for a company matching this identity (matched=false, confidence=5, every data field null). Near-hits were EditiX (an XML editor), Editrix (an AI book-editing tool) and EditShare (media software) -- none matching the company name+domain. Identity is unresolvable, not merely unresearched."
}
PATCH[17317850381]: {
  "lv_org_type": "broadcaster",
  "lv_org_type_verified_at": "<stamped at write time>"
}
PATCH[20538284384]: {
  "lv_org_type": "individual_club_team",
  "lv_org_type_verified_at": "<stamped at write time>"
}
PATCH[20943964946]: {
  "lv_org_type": "content_producer",
  "lv_org_type_verified_at": "<stamped at write time>"
}
```

None of the five contains a `country_region` key or any of the four forbidden derived
scoring fields (`lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`)
-- confirmed by `test_marker_no_patch_contains_country_region_key` and the module-level
`assert FORBIDDEN_PROPS.isdisjoint(props)` inside `build_coverage_patch` itself.

## Pre-arm baseline: both surfaces confirmed disarmed (Task 1, independent read)

```
workflow_id: 950HPb7a1GgSAIyZ  ("LV Enrichment (Cloud template)")
active: True
ALLOW_HUBSPOT_RECORD_WRITES: "false"
ALLOW_HUBSPOT_CREATE:        "false"
TEST_RECORD_IDS:              ""
TEST_RECORD_DOMAINS:          ""
```

## Both operator arming commands, ready to paste

**Amendment (D-48-01, 2026-08-13, Phase 48 only):** these two commands, and the disarm
below, are executed by **Claude**, not the operator, for this phase only -- delegated in
`48-CONTEXT.md`'s D-48-01. They are still recorded here verbatim, in the per-shell form
the plan requires, so the actual invocation used at run time matches this record.

**Surface 1 -- the driver's own two-key gate** (guards the direct `lv_org_type` PATCH
leg), set in the SAME shell as the run command in Task 3:

```
DRY_RUN=false ALLOW_ENRICH_COVERAGE=true .venv/bin/python -c \
  "from dotenv import load_dotenv; \
   load_dotenv('/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/.env'); \
   import sys; sys.path.insert(0, '.'); \
   import scripts.enrich_coverage_companies as m; \
   result = m.run_coverage_window(armed=True); \
   import json; print(json.dumps(result, indent=2, default=str))"
```

**Surface 2 -- the n8n-side allowlist** (guards `Decide Company Action` ->
`HubSpot Company Update`), armed BEFORE the command above, for exactly the five ids:

```
ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py \
  --ids 15008671672,17317381378,17317850381,20538284384,20943964946
```

**Disarm** (ungated by design, run unconditionally at the end of the window -- also
performed inside `run_coverage_window`'s own `finally`, as a second, redundant close):

```
.venv/bin/python scripts/june_run_arm.py --disarm
```

---

## Task 3 appends below this line: arm-time allowlist assertion, per-record outcomes, disarm evidence
