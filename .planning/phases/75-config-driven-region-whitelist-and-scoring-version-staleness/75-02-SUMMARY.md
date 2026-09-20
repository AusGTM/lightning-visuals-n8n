---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
plan: 02
subsystem: scoring-engine
tags: [icp-scoring, region-whitelist, normalisers, hubspot-schema, tdd]

# Dependency graph
requires:
  - phase: 75-01
    provides: config/icp_scoring.yaml's regions.home/regions.aliases scaffold,
      scripts/gen_icp_scoring_js.py, n8n/code/icpScoring.generated.js, the
      lv_icp_scoring_version write-side stamp
provides:
  - config/icp_scoring.yaml regions.aliases as the SINGLE country-name/ISO2 -> region-code
    table, replacing n8n/code/normalizeProviders.js's hand-typed _COUNTRY_ISO2
  - src/icp_scoring.py::regions_home()/region_aliases() cached accessors, reused by
    src/normalizer.py and scripts/zoominfo_company_client.py (one loader, no second parser)
  - tests/n8n/regionAliasParity.test.mjs -- yaml-vs-JS alias superset guard
  - config/hubspot_properties.yaml declarations for the eight new
    lv_country_region_normalized options, UK hidden, and the new lv_icp_scoring_version
    company property (declared, not yet live -- Plan 05's job)
affects: [75-03, 75-04, 75-05, 75-06]

# Actuals (#2632)
actuals:
  tokens: 191033
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One alias table serving three independent normalisers (JS/Python/ZoomInfo) plus
      the phone-normalisation lane, each preserving its own per-lane blank sentinel"
    - "yaml-vs-generated-JS parity test hard-coded against a frozen historical key list,
      not re-derived from the yaml it guards (tests/n8n/regionAliasParity.test.mjs,
      mirrors tests/n8n/columnMapIdentityParity.test.mjs)"
    - "Declare-now/create-later for a new HubSpot property (lv_icp_scoring_version) and a
      widened enum (lv_country_region_normalized) -- D-72-23 precedent, live push
      deferred to a later plan"

key-files:
  created:
    - tests/n8n/regionAliasParity.test.mjs
    - tests/test_normalizer.py
  modified:
    - config/icp_scoring.yaml
    - n8n/code/icpScoring.generated.js
    - n8n/code/normalizeProviders.js
    - src/icp_scoring.py
    - src/normalizer.py
    - scripts/zoominfo_company_client.py
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - tests/n8n/enrichment.test.mjs
    - tests/test_zoominfo_company_client.py
    - config/hubspot_properties.yaml
    - tests/test_hubspot_properties_config.py

key-decisions:
  - "tests/test_normalizer.py did not exist before this plan despite the plan's own
    read_first citing it as 'the existing Python normaliser tests whose expectations
    move' -- grep found no such file anywhere in the repo. Created new rather than
    treating this as a blocker; tests/test_merge_policy.py's two pre-existing
    normalize_country_region cases were left untouched."
  - "Two pre-existing test assertions (tests/n8n/enrichment.test.mjs,
    tests/test_zoominfo_company_client.py) used \"United States\" as their canonical
    outside-home-regions example -- factually wrong once D-75-05 added US to
    regions.home. Same deviation class Plan 01 already fixed in six other files, not
    caught there because Plan 01 never touched normalizeCountryRegion/
    zoominfo_country_region. Swapped to Germany (the plan's own non-home example) in
    both; tests/n8n/judge.test.mjs and materialConflictNoVetoFlip.test.mjs also
    literal-match \"United States\" but hand-construct their normalizedValue in the
    fixture rather than calling the real normaliser -- confirmed unaffected, left
    untouched."
  - "Followed the plan's explicit tdd=\"true\" RED/GREEN structure for Tasks 1 and 2.
    For Task 2, the persisted regionAliasParity.test.mjs test commit does not itself
    fail before the GREEN commit (Task 1 already delivers a correct REGION_ALIASES) --
    the task's REAL new-behaviour RED is the inline-order defect RESEARCH.md's Pitfall
    6 predicts (REGION_ALIASES absent from the concatenated Code-node body). That RED
    was demonstrated manually (reverting the three inline() call sites to their
    pre-plan state, regenerating, and confirming the exact predicted failure on 5
    nodes across 3 workflow files), documented in the test commit message rather than
    captured by a second persisted test file, mirroring Plan 01's own precedent for
    reconciling multi-file TDD structure with gsd_run check tdd-red-evidence's narrow
    TAP-only parser."

requirements-completed: []

coverage:
  - id: D1
    description: "config/icp_scoring.yaml regions.aliases is the single country-name/
      ISO2 -> region-code table; all three region normalisers (JS normalizeProviders.js,
      Python src/normalizer.py, ZoomInfo scripts/zoominfo_company_client.py) and the
      phone-normalisation lane (_iso2) read it, with _COUNTRY_ISO2 deleted"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/n8n/regionAliasParity.test.mjs (3 assertions: exact yaml equality,
          frozen historical superset, REGIONS_HOME/Other closure)"
        status: pass
      - kind: unit
        ref: "tests/test_normalizer.py (4 cases: whitelisted name, whitelisted ISO2,
          unmapped country, blank sentinel)"
        status: pass
      - kind: integration
        ref: "node -e \"...\" grep-equivalent asserting zero _COUNTRY_ISO2 references
          and REGION_ALIASES presence in all 3 generated workflow files"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every generated Code node that calls normalizeCountryRegion/_iso2
      carries REGION_ALIASES declared ahead of it in the same concatenated Code-node
      string (the inline-order fix for RESEARCH.md's Pitfall 6)"
    requirement: null
    verification:
      - kind: integration
        ref: "node -e \"...\" walking all n8n/wf_*.json nodes and asserting declaration
          order; RED manually demonstrated against the pre-fix inline() registration
          (5 affected nodes across wf_enrichment_cloud.json, wf_enrichment_local.json,
          wf_enrichment_local_live.json), then restored to GREEN"
        status: pass
    human_judgment: false
  - id: D3
    description: "config/hubspot_properties.yaml declares the eight new
      lv_country_region_normalized options (GB/IE/CA/ZA/HK/SG/AE/IN), the existing UK
      option is hidden (never deleted), EU is byte-identical, and a new company
      property lv_icp_scoring_version is declared -- all SHIPPED INERT until Plan 05
      pushes them live"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/test_hubspot_properties_config.py (full suite, plus the
          region/scoring_version/counts -k subset)"
        status: pass
      - kind: other
        ref: "grep -c lv_icp_scoring_version config/hubspot_properties.yaml (1); grep -A2
          'value: UK' config/hubspot_properties.yaml | grep -c 'hidden: true' (1)"
        status: pass
    human_judgment: true
    rationale: "Nothing in this plan pushes the schema live or proves the inert-until-
      live window empirically -- that is Plan 05's job. The verifier should read this
      deliverable as declare-only, cross-checking that the 'shipped inert' consequence
      paragraph in this SUMMARY and the commit message match, not expect any live
      HubSpot state to have changed."

duration: 16min
completed: 2026-09-20
status: complete
---

# Phase 75 Plan 02: Config-Driven Region Whitelist Summary

**`regions.aliases` in `config/icp_scoring.yaml` is now the single country-name/ISO2 →
region-code table read by all three region normalisers and the phone lane,
`_COUNTRY_ISO2` is deleted, and `config/hubspot_properties.yaml` declares the eight new
target-region enum options (with UK hidden, never deleted) and the
`lv_icp_scoring_version` property — both shipped inert until a later plan pushes them
live.**

## Performance

- **Duration:** 16 min (commit span; full session including context loading longer)
- **Started:** 2026-09-20T16:01:42+10:00 (approx, Plan 01's closing commit)
- **Completed:** 2026-09-20T16:17:44+10:00
- **Tasks:** 3
- **Files modified:** 16 (2 created, 14 modified)

## Accomplishments

- `config/icp_scoring.yaml`'s `regions.aliases` grew from 8 to 30 keys — a superset of
  the union of `n8n/code/normalizeProviders.js::_COUNTRY_ISO2`'s 11 keys, the three
  normalisers' own `au`/`aus`/`nz` literals, self-aliases for every `regions.home` code,
  and the obvious country names for the eight new codes. `n8n/code/icpScoring.generated.js`
  regenerated.
- `n8n/code/normalizeProviders.js`: `_COUNTRY_ISO2` deleted; `_iso2()` and
  `normalizeCountryRegion()` both now read `REGION_ALIASES`; the module now
  `require()`s `./icpScoring.generated` so the standalone `.js` (and every offline test
  that imports it directly) resolves correctly.
- `src/icp_scoring.py` gained `lru_cache`-wrapped `regions_home()`/`region_aliases()`
  accessors; `src/normalizer.py::normalize_country_region` and
  `scripts/zoominfo_company_client.py::zoominfo_country_region` both now read
  `region_aliases()` instead of their own hand-typed literal lists — each lane's own
  blank-value sentinel (JS `null`, Python `"Unknown"`, ZoomInfo `None`) is unchanged.
- `scripts/build_cloud_workflows.py`: all three `ENRICH_NORMALIZE_SCORE*` `inline()`
  calls now list `"icpScoring.generated.js"` first, ahead of `"normalizeProviders.js"` —
  the fix for the RESEARCH.md Pitfall 6 defect (`REGION_ALIASES is not defined` inside
  the concatenated Code-node body). Regenerated `n8n/wf_enrichment_cloud.json`,
  `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json` — the only three
  workflows that carry this Code node.
- New `tests/n8n/regionAliasParity.test.mjs` pins yaml-vs-JS exactness, a frozen
  historical-key superset (independent of the yaml under test), and
  `REGIONS_HOME`/`"Other"` closure over every alias value.
- `config/hubspot_properties.yaml`: `lv_country_region_normalized` gained 8 new options
  (`GB`, `IE`, `CA`, `ZA`, `HK`, `SG`, `AE`, `IN`); `UK` set `hidden: true` (never
  deleted); `EU` untouched; new company property `lv_icp_scoring_version` declared
  (`string`/`text`, `lv_enrichment` group).

## Task Commits

1. **Task 1 RED:** `7dc3025a` (test) — `tests/test_normalizer.py` (new file), 2 of 4
   assertions failed against pre-Phase-75-02 code (`normalize_country_region("United
   States")` and `("gb")` both returned `"Other"` instead of `US`/`GB`).
2. **Task 1 GREEN:** `100c9fb2` (feat) — the one-alias-table implementation across all
   6 files; all 4 `tests/test_normalizer.py` assertions pass.
3. **Task 2 RED (test commit):** `e1559cbd` (test) — `tests/n8n/regionAliasParity.test.mjs`
   (new file); RED demonstrated for the superset assertion by deleting `canada` from
   the yaml (restored, zero diff after); the task's own real RED (the inline-order
   defect) demonstrated manually and documented in the commit message rather than
   captured as a second persisted test.
4. **Task 2 GREEN:** `53bcd945` (feat) — the `inline()` registration fix, regenerated
   workflow JSON, and 2 stale non-home assertion fixes (Rule 1 deviation, see below).
5. **Task 3:** `87c6a08d` (feat) — `config/hubspot_properties.yaml` schema
   declarations + the exact-counts guard bump.

**Plan metadata:** this SUMMARY's own commit (below).

## Files Created/Modified

- `config/icp_scoring.yaml` - `regions.aliases` completed to the full superset table
- `n8n/code/icpScoring.generated.js` - regenerated
- `n8n/code/normalizeProviders.js` - `_COUNTRY_ISO2` deleted; `_iso2`/
  `normalizeCountryRegion` read `REGION_ALIASES`; new `require`
- `src/icp_scoring.py` - `regions_home()`/`region_aliases()` cached accessors
- `src/normalizer.py` - `normalize_country_region` reads `region_aliases()`
- `scripts/zoominfo_company_client.py` - `zoominfo_country_region` reads
  `region_aliases()`
- `scripts/build_cloud_workflows.py` - 3 `inline()` call sites gain
  `"icpScoring.generated.js"` as their first argument
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`,
  `n8n/wf_enrichment_local_live.json` - regenerated (no hand-edit)
- `tests/n8n/regionAliasParity.test.mjs` - new yaml-vs-JS alias parity guard
- `tests/test_normalizer.py` - new (see Deviations)
- `tests/n8n/enrichment.test.mjs`, `tests/test_zoominfo_company_client.py` - stale
  non-home assertion fixes (Deviations)
- `config/hubspot_properties.yaml` - 8 new enum options, `UK` hidden, new
  `lv_icp_scoring_version` property
- `tests/test_hubspot_properties_config.py` - exact-counts guard bumped 35 → 36

## Decisions Made

See `key-decisions` in the frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/test_normalizer.py` did not exist**
- **Found during:** Task 1, attempting to follow the plan's RED-phase instruction to
  extend the file
- **Issue:** The plan's Task 1 `<read_first>` and Task 2 `<action>` both cite
  `tests/test_normalizer.py` as "the existing Python normaliser tests whose
  expectations move." A repo-wide grep (including a dedicated `find -iname`) found no
  such file anywhere. `tests/test_merge_policy.py` carries two pre-existing
  `normalize_country_region` assertions (`"Australia"` → `AU`, `"Germany"` → `Other`),
  neither of which needed to change.
- **Fix:** Created `tests/test_normalizer.py` new, with the four cases Task 2's
  `<action>` specifies verbatim (whitelisted name, whitelisted ISO2, unmapped country,
  blank sentinel). Documented the discrepancy in the file's own header comment.
- **Files modified:** `tests/test_normalizer.py` (new)
- **Verification:** RED demonstrated before Task 1's GREEN commit (2 of 4 assertions
  failed); GREEN after
- **Committed in:** `7dc3025a` (RED), `100c9fb2` (GREEN)

**2. [Rule 1 - Bug] Two more files used "United States" as the canonical
outside-home-regions example, broken by D-75-05's whitelist addition**
- **Found during:** the full-suite run after Task 2's GREEN commit
- **Issue:** `tests/n8n/enrichment.test.mjs`'s `toCandidates: ZoomInfo revenue falls
  back to revenue*1000 with no revenueRange` test used a FanDuel fixture with
  `country: "United States"`, asserting the resulting `lv_country_region_normalized`
  candidate normalizes to `"Other"` (the "non-ANZ → hard veto input" comment).
  `tests/test_zoominfo_company_client.py::test_country_region_blank_is_none` asserted
  `zoominfo_country_region("United States") == "Other"`. Both became factually wrong
  the moment `regions.aliases` started resolving `"united states"` → `US`, a
  `regions.home` member. This is the SAME deviation class Plan 01 documented fixing in
  six other files ("US was the repo's canonical non-home veto example") — not caught
  there because Plan 01 never touched `normalizeCountryRegion`/`zoominfo_country_region`,
  only the two scoring engines.
- **Fix:** Swapped the country literal from `"United States"` to `"Germany"` (the
  plan's own non-home example) in both files; both still assert the `"Other"` branch
  each test targets. Updated `enrichment.test.mjs`'s stale `// non-ANZ` comment to `//
  outside target regions`, matching D-75-01's renamed reason.
  `tests/n8n/judge.test.mjs` and `tests/n8n/materialConflictNoVetoFlip.test.mjs` also
  literal-match `"United States"`, but both hand-construct their `normalizedValue` in
  the test fixture rather than calling the real normaliser — confirmed unaffected by
  reading both files, left untouched.
- **Files modified:** `tests/n8n/enrichment.test.mjs`, `tests/test_zoominfo_company_client.py`
- **Verification:** full `node --test tests/n8n/*.test.mjs` (1324 passed / 0 failed);
  full `pytest` suite (5180 passed / 160 skipped / 1 known-red)
- **Committed in:** `53bcd945`

---

**Total deviations:** 2 auto-fixed groups (1 Rule 3 blocking-issue group covering 1
new file, 1 Rule 1 bug-fix group covering 2 files).
**Impact on plan:** both were necessary consequences of the region-alias/whitelist
change the plan's own scope did not fully anticipate; neither represents scope creep
beyond making the plan's stated goal actually true end-to-end. No frozen fixture or
stress-test file was touched.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The `lv_icp_scoring_version` property and the eight new
  `lv_country_region_normalized` options are declared but SHIPPED INERT — see this
  plan's Task 3 commit message for the full consequence paragraph. Plan 05's job to
  push both live, refresh `n8n/code/hubspotEnums.generated.js`'s pinned snapshot, and
  regenerate.
- `tests/test_hubspot_schema_coverage.py`'s one red test (unchanged from Plan 01, NOT
  fixed here per this executor's explicit instructions) remains the tracked blocker
  for **deploy** — resolves when a later plan runs `sync_hubspot_properties.py` live.
  Tracked in `.planning/WINDOWS.md` (from Plan 01).
- `regions.aliases`, `regions_home()`/`region_aliases()`, and
  `tests/n8n/regionAliasParity.test.mjs` are all in place for any later plan (03-06)
  that needs to read the whitelist or aliases.

---
*Phase: 75-config-driven-region-whitelist-and-scoring-version-staleness*
*Plan: 02*
*Completed: 2026-09-20*

## Self-Check: PASSED

- `tests/n8n/regionAliasParity.test.mjs` — FOUND
- `tests/test_normalizer.py` — FOUND
- `config/icp_scoring.yaml` `regions.aliases` — 30 keys, verified via python yaml load
- `n8n/code/normalizeProviders.js` — 0 occurrences of `_COUNTRY_ISO2`
- Commit `7dc3025a` (test, RED) — FOUND in `git log`
- Commit `100c9fb2` (feat, GREEN) — FOUND in `git log`
- Commit `e1559cbd` (test) — FOUND in `git log`
- Commit `53bcd945` (feat) — FOUND in `git log`
- Commit `87c6a08d` (feat) — FOUND in `git log`
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider`: 5180 passed / 160
  skipped / 1 known-red (`test_hubspot_schema_coverage.py`, pre-existing, unfixed by
  instruction)
- `node --test tests/n8n/*.test.mjs`: 1324 passed / 0 failed
- `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/`:
  exits 0 (n8n/ clean after regeneration)
