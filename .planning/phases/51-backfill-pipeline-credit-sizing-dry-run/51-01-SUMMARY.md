---
phase: 51-backfill-pipeline-credit-sizing-dry-run
plan: 01
subsystem: api
tags: [zoominfo, hubspot, icp-scoring, dry-run, python]

# Dependency graph
requires:
  - phase: 40-scoring-engine-remediation
    provides: src/icp_scoring.py::compute_icp_score, anti_icp_flag_properties
  - phase: 40-scoring-engine-remediation
    provides: scripts/backfill_seed_company_scores.py::compute_components, COMPONENT_PROPS
provides:
  - "scripts/zoominfo_company_client.py: read-only ZoomInfo GTM companies/enrich client with THOUSANDS-to-dollars conversion and a blank-safe country mapper"
  - "scripts/backfill_dry_run.py: zero-write backfill dry-run driver -- credit cap, bounded never-scored sample, ZoomInfo enrichment, oracle scoring, pre-registered tier prediction"
  - "51-TRACER-DRYRUN.json: one live-derived dry-run record, measured ZoomInfo per-match cost (100 hundredths, retiring the inferred 108 figure as a floor)"
affects: [52-backfill-execution, dry-run-driver]

actuals:
  tokens: 9119
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Zero-write driver: every patch_record call site passes dry_run=True as a hard-coded literal, never env-driven"
    - "Pre-registered tier prediction derived from (score, anti_icp_flag) directly, never from the oracle's .tier attribute (which carries a Python-only 'Needs Review' label absent from HubSpot's live calculation_equation)"
    - "Integer-only credit cap arithmetic in hundredths-of-a-credit units, guarding against float rounding and division-by-zero on a free/cached cost measurement"
    - "Refuse-rather-than-truncate population reads: count via limit=1/total, bounded single-page sample, RuntimeError on any anomaly"

key-files:
  created:
    - scripts/zoominfo_company_client.py
    - scripts/backfill_dry_run.py
    - tests/test_zoominfo_company_client.py
    - tests/test_backfill_dry_run.py
    - .planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-TRACER-DRYRUN.json
  modified: []

key-decisions:
  - "Portal-id guard (_portal_ok) lives only in main(), not as an internal check inside run_dry_run() -- deliberate, so offline tests can call run_dry_run() directly without setenv ceremony; main() still asserts it before any network call, satisfying the artifact's portal_id_verified claim"
  - "credits_per_match_hundredths_used is the LARGER of the live-measured figure and the CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK=108 floor -- the pre-spend refusal gate always uses the fallback (no measurement exists yet at gate time); the post-measurement artifact recomputes credit_cap against the used figure"
  - "matched_attributes recorded in the artifact are trimmed to the three fields the driver actually consumes (revenue, revenueRange, country) rather than the full ZoomInfo response, keeping marketing-text fields like descriptionList out of the committed artifact"

patterns-established:
  - "Tracer-then-pin: task 1 proves the whole path on one path only; task 2 pins every edge (band cut points, blank inputs, cap boundary, tier cut points, payload key set, import identity) the tracer silently depended on, with zero source changes"

requirements-completed: [FILL-01, FILL-03, SAFE-01]

coverage:
  - id: D1
    description: "derive_credit_cap() is integer-only (no float division, no round, no ceil) and guards a zero/negative/unknown balance to 0"
    requirement: "FILL-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_cap_derivation"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_cap_boundary_refusal"
        status: pass
    human_judgment: false
  - id: D2
    description: "zoominfo_revenue_band() converts ZoomInfo's THOUSANDS-unit revenue to dollars before banding, with inclusive-lower-bound cut points, range precedence over raw revenue, and None (not a false band) for absent/zero/non-numeric input"
    requirement: "FILL-03"
    verification:
      - kind: unit
        ref: "tests/test_zoominfo_company_client.py::test_revenue_thousands_to_dollars"
        status: pass
      - kind: unit
        ref: "tests/test_zoominfo_company_client.py::test_revenue_band_edges_inclusive_lower"
        status: pass
      - kind: unit
        ref: "tests/test_zoominfo_company_client.py::test_revenue_band_empty_and_zero"
        status: pass
      - kind: unit
        ref: "tests/test_zoominfo_company_client.py::test_revenue_range_precedence"
        status: pass
    human_judgment: false
  - id: D3
    description: "zoominfo_country_region() returns None for blank/whitespace/absent country -- never the truthy 'Unknown' sentinel src.normalizer.normalize_country_region emits, which would misfire compute_icp_score's non-ANZ hard veto"
    requirement: "FILL-03"
    verification:
      - kind: unit
        ref: "tests/test_zoominfo_company_client.py::test_country_region_blank_is_none"
        status: pass
    human_judgment: false
  - id: D4
    description: "predict_tier() replicates the live four-branch lv_icp_tier_derived formula from (score, anti_icp_flag) directly -- never reads the oracle's .tier attribute, which carries a Python-only 'Needs Review' label the live calculation cannot produce"
    requirement: "SAFE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_predicted_tier_score_edges"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_predicted_tier_excludes_needs_review"
        status: pass
    human_judgment: false
  - id: D5
    description: "A matched row's payload key set is a subset of exactly the twelve permitted names (six lv_* inputs + five component scores + lv_anti_icp_flag_num), never the four other-producer-owned properties"
    requirement: "SAFE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_payload_key_set"
        status: pass
    human_judgment: false
  - id: D6
    description: "compute_components/compute_icp_score/anti_icp_flag_properties are the imported oracle objects, not local reimplementations"
    requirement: "SAFE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_imports_oracle_functions"
        status: pass
    human_judgment: false
  - id: D7
    description: "End-to-end offline pipeline: mocked ZoomInfo match -> revenue/country conversion -> oracle scoring -> printed dry-run payload, with a blank-domain record skipped before any provider call"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_end_to_end_one_record_dry_run"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_no_domain_skipped_before_provider_call"
        status: pass
    human_judgment: false
  - id: D8
    description: "Live tracer run against portal 22617666: population_total=646, credit balance bracketed 9397->9396 (1 credit spent, 1 enrich call), measured cost 100 hundredths/match, one AU-matched company (score 20, tier C, no veto), zero skipped, committed as 51-TRACER-DRYRUN.json with no credential material"
    requirement: "SAFE-01"
    verification:
      - kind: other
        ref: ".planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-TRACER-DRYRUN.json (schema + cap-formula + credential-leak checks in Task 3's <verify>/<acceptance_criteria>, run this session)"
        status: pass
    human_judgment: false

duration: ~15min
completed: 2026-08-19
status: complete
---

# Phase 51 Plan 01: Backfill Pipeline Tracer Summary

**One-record ZoomInfo-to-HubSpot backfill dry run, live-proven end to end with zero writes and a measured (not inferred) per-match credit cost**

## Performance

- **Duration:** ~15min
- **Started:** 2026-08-19T13:00:00+10:00 (approx, first commit 13:00:27+10:00)
- **Completed:** 2026-08-19T13:08:32+10:00
- **Tasks:** 3
- **Files modified:** 5 (2 new scripts, 2 new test files, 1 committed artifact)

## Accomplishments
- Built `scripts/zoominfo_company_client.py`: the first Python ZoomInfo GTM
  `companies/enrich` client in this repo (previously only generated JS), with
  THOUSANDS-to-dollars revenue conversion, revenue-range precedence, and a
  blank-safe country mapper that returns `None` (never the false-veto-triggering
  `"Unknown"` sentinel `src.normalizer.normalize_country_region` emits).
- Built `scripts/backfill_dry_run.py`: a zero-write driver composing a live
  credit cap, a bounded never-scored sample, ZoomInfo enrichment, and the
  imported `compute_icp_score`/`compute_components` oracle into a printed
  dry-run PATCH payload with a pre-registered tier prediction derived directly
  from score + veto (never the oracle's `.tier`, which carries a Python-only
  "Needs Review" label the live `calculation_equation` cannot produce).
- Pinned every edge the tracer path silently depends on: band cut points
  (inclusive lower bound), empty/zero/non-numeric revenue, range-vs-raw
  precedence, blank country, credit-cap precision and boundary refusal (proven
  by a zero `enrich_company` call count), tier cut points, the excluded
  "Needs Review" label, the twelve-name payload key set, and oracle-import
  identity — 14 tests, zero source changes in this task.
- Ran the tracer live against portal `22617666`: `population_total=646`
  (matches the `MILESTONE-CONTEXT.md` ~646 estimate exactly, no divergence),
  ZoomInfo credit balance 9397 -> 9396 (one credit spent for one enrich call),
  **measured 100 hundredths-of-a-credit per match** (vs. the 108 documented
  floor -- research Assumption A1 retired), one AU-matched company scored
  20/tier C/no veto, zero skipped. Committed as `51-TRACER-DRYRUN.json` with
  no credential material.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end tracer -- one never-scored company gets a predicted tier and a printed PATCH payload** - `9ddaab3` (feat, tdd)
2. **Task 2: Pin the four edge contracts the tracer path silently depends on** - `1699bee` (test, tdd)
3. **Task 3: Run the tracer live on one record, bracketed by two credit-balance reads, and commit the artifact** - `918e385` (feat)

## Files Created/Modified
- `scripts/zoominfo_company_client.py` - Read-only ZoomInfo GTM `companies/enrich` client; revenue/country conversion helpers
- `scripts/backfill_dry_run.py` - Zero-write dry-run driver: credit cap, population count/sample, scoring, `--measure-cost`, `main()` CLI
- `tests/test_zoominfo_company_client.py` - 6 offline tests pinning the client's revenue/country/malformed-response contracts
- `tests/test_backfill_dry_run.py` - 8 offline tests pinning the driver's cap, tier, payload, and import-identity contracts
- `.planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-TRACER-DRYRUN.json` - Committed live one-record dry-run artifact

## Decisions Made
- Portal-id guard (`_portal_ok()`) is checked only in `main()`, not inside `run_dry_run()` itself, so the offline test suite can call `run_dry_run()` directly without `setenv` ceremony. `main()` still asserts the portal before any network call and the artifact records `portal_id_verified` from the live run, so the guard is honored on the only path that ever touches the network.
- `credits_per_match_hundredths_used` is `max(measured, CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK)`. The pre-spend refusal gate always uses the fallback (no measurement exists yet at gate time); the artifact's `credit_cap` is recomputed post-measurement against the used figure, per the research doc's Open Question 1 resolution.
- Committed `matched_attributes` are trimmed to the three fields the driver actually reads (`revenue`, `revenueRange`, `country`), not the full ZoomInfo response, so the artifact doesn't drag in unused marketing-text fields (`descriptionList` etc).

## Deviations from Plan

None — plan executed exactly as written. The two design choices above (portal-guard placement, trimmed `matched_attributes`) are implementation details within the plan's own action text, not scope changes.

## Issues Encountered
- The first Task 3 commit attempt via an inline `git commit -m "$(cat <<'EOF' ... EOF)"` heredoc failed with a shell quoting error (unrelated to file content — files were already staged correctly). Resolved by writing the message to a scratch file and using `git commit -F`.

## User Setup Required

None - no external service configuration required. Live credentials
(`HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_PORTAL_ID`, `ZOOMINFO_CLIENT_ID`,
`ZOOMINFO_CLIENT_SECRET`) already resolved from the repo-root `.env` via
`load_dotenv()`.

## Next Phase Readiness
- The dry-run pipeline is proven end to end on one live record with a measured
  (not assumed) ZoomInfo per-match credit cost — plan 02 can size the full
  D-06 sample against `credit_cap` with confidence.
- `select_never_scored_sample()` deliberately has no `after`-cursor pagination
  (out of scope per the plan and research doc) — flagged as a Phase 52
  prerequisite for the full ~646-record chunked-remainder write, not a blocker
  for plan 02's dry-run-only sample.
- Zero HubSpot writes and zero n8n executions occurred this plan, consistent
  with Phase 51's structural constraint.

---
*Phase: 51-backfill-pipeline-credit-sizing-dry-run*
*Completed: 2026-08-19*
