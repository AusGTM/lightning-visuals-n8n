---
phase: 51-backfill-pipeline-credit-sizing-dry-run
plan: 02
subsystem: api
tags: [zoominfo, claude-web-research, hubspot, icp-scoring, dry-run, python]

# Dependency graph
requires:
  - phase: 51-backfill-pipeline-credit-sizing-dry-run
    plan: 01
    provides: "scripts/backfill_dry_run.py (tracer path), scripts/zoominfo_company_client.py, 51-TRACER-DRYRUN.json (measured per-match cost)"
  - phase: 40-scoring-engine-remediation
    provides: src/icp_scoring.py::compute_icp_score, anti_icp_flag_properties
provides:
  - "scripts/backfill_dry_run.py: D-02 gap-fill research lane (research_gap_fields/apply_research_to_patch), D-04 skip contract (build_skip_entry), D-03 sizing gate (build_sizing_plan/write_sizing_markdown), exact matched/unmatched partition assertion, numeric sample ordering"
  - "51-SIZING.md: live credit balance, measured per-match cost, derived cap, live never-scored population, chosen sample size, labelled Anthropic estimate -- committed before any sample record was enriched"
  - "51-DRYRUN-PREDICTIONS.json: 8 pre-registered rows (exact PATCH payload + predicted tier) over a live 10-record sample"
  - "51-SKIP-LOG.json: 2 reasoned skip entries, no payload"
affects: [52-backfill-execution]

actuals:
  tokens: 13762
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Structural no-rescue: the skip-and-continue sites sit BEFORE the research call site in run_dry_run's loop body, so an unmatched record can never reach research_gap_fields by construction, not by a conditional a later edit could invert"
    - "Never-guess research merge: apply_research_to_patch only fills GAP_FILL_FIELDS names still absent, never overwrites a ZoomInfo value, and treats a None/non-bool research answer as absence (key omitted) rather than a default -- a defaulted False on lv_produces_content would fire the no-content veto on a record nobody researched"
    - "Sizing gate reused, not duplicated: build_sizing_plan() is the single place that reads the live balance/population and asserts sample_size <= credit_cap; run_dry_run() calls it at its own top so the assertion runs before any enrich request, and the same function independently serves --sizing-out's read-only markdown mode"
    - "Numeric, not lexicographic, sample ordering: select_never_scored_sample sorts by int(id) -- this portal mixes 10- and 11-digit HubSpot ids, and a string sort would both misorder rows and select a different slice"

key-files:
  created: []
  modified:
    - scripts/backfill_dry_run.py
    - tests/test_backfill_dry_run.py
  artifacts:
    - .planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-SIZING.md
    - .planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-DRYRUN-PREDICTIONS.json
    - .planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-SKIP-LOG.json

key-decisions:
  - "Sample size sized to 10, not the research doc's assumed default of 12 -- live .env carries MAX_WEB_RESEARCH_PER_RUN=10, discovered during Task 2's live sizing read. The ZoomInfo credit cap (8700) was nowhere close to binding; the operator's own configured research-call budget was the real constraint, so the sample was sized to respect it rather than overriding the env var for one run."
  - "build_sizing_plan()'s credits_per_match_hundredths defaults to reading 51-TRACER-DRYRUN.json's measured figure (100) floored at CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK (108) ONLY when the caller passes no explicit value. run_dry_run() always passes its own explicit credits_per_match_hundredths parameter (unchanged default 108) so the plan-01 test suite's exact behavior is preserved byte-for-byte; only the standalone --sizing-out CLI path and a bare build_sizing_plan(sample_size) call read the tracer file."
  - "credits_spent in the predictions artifact is a ceiling projection (enrich_calls_issued * credits_per_match_hundredths_used, rounded up), not a second live balance re-read on top of --measure-cost's bracket -- --measure-cost was still passed for Task 3's live run, so credits_per_match_hundredths_used reflects the run's own measured rate, not a stale constant."
  - "matched-but-empty-attributes (the FILL-04 adjacency-probe edge case flagged UNRESOLVED in 51-RESEARCH.md) lands on the predictions side, per the research doc's own resolution: 'that reading has been authored as a truth and a test regardless... the probe row itself is not auto-resolved to a backstop marker.' No third disposition was invented; test_partition_exclusive_and_total pins this as the documented behavior, still open for plan 03's operator checkpoint if a third category is wanted."

patterns-established:
  - "Sizing-then-run split: build_sizing_plan() is callable standalone (via --sizing-out, zero enrich/write/n8n calls) or embedded at the top of a full run (run_dry_run()) -- one function, two call sites, one assertion."

requirements-completed: [FILL-01, FILL-04, SAFE-01]

coverage:
  - id: D9
    description: "select_never_scored_sample sorts by numeric id (int(r['id'])), not lexicographic string order -- this portal mixes 10- and 11-digit HubSpot ids, and a string sort would misorder rows and pick a different sample slice"
    requirement: "SAFE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_sample_order_is_ascending_id_stable"
        status: pass
    human_judgment: false
  - id: D10
    description: "research_gap_fields issues zero calls when every GAP_FILL_FIELDS name is already present, and is structurally unreachable for an unmatched record (skip-and-continue sits before the research call site in the loop)"
    requirement: "FILL-04"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_no_research_for_unmatched_record"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_research_only_fills_missing_fields"
        status: pass
    human_judgment: false
  - id: D11
    description: "apply_research_to_patch never overwrites a ZoomInfo-supplied value, normalizes lv_org_type through src.taxonomy.normalize_org_type only for a non-None raw value (never normalize_org_type(None), which defaults to 'unknown'), and accepts only real booleans for the three boolean gap fields -- a null/non-bool answer leaves the key absent rather than defaulting to a veto-firing False"
    requirement: "FILL-04"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_research_only_fills_missing_fields"
        status: pass
    human_judgment: false
  - id: D12
    description: "build_skip_entry returns exactly {id, name, domain, reason} with no payload key; every skip site in run_dry_run routes through it"
    requirement: "FILL-04"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_unmatched_skip_log"
        status: pass
    human_judgment: false
  - id: D13
    description: "run_dry_run asserts the predictions/skip partition is exact before returning (disjoint ids, union == sample ids), raising RuntimeError naming the offending ids otherwise -- including the exactly-touching matched-but-empty-attributes case landing on exactly one side"
    requirement: "FILL-04"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_partition_exclusive_and_total"
        status: pass
    human_judgment: false
  - id: D14
    description: "build_sizing_plan asserts sample_size <= credit_cap before any enrich request (called at the top of run_dry_run, and independently via --sizing-out); refusal names both numbers"
    requirement: "FILL-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_sizing_plan_recorded_before_enrich"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_sample_above_cap_refused"
        status: pass
    human_judgment: false
  - id: D15
    description: "A run in which every sample record is unmatched still exits 0 and still writes a valid predictions artifact (empty rows, fully populated metadata) plus a complete skip log"
    requirement: "SAFE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_dry_run.py::test_empty_sample_writes_valid_artifacts"
        status: pass
    human_judgment: false
  - id: D16
    description: "Live sizing artifact (51-SIZING.md) committed before any sample record was enriched: population_total=646, credit_balance=9396, credits_per_match_hundredths=108 (max of measured 100 and fallback 108), credit_cap=8700, sample_size=10, Anthropic estimate labelled a prior-pipeline figure not measured for this call pattern (A2)"
    requirement: "FILL-01"
    verification:
      - kind: other
        ref: ".planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-SIZING.md (grep + arithmetic checks run this session, see Task 2 acceptance criteria)"
        status: pass
    human_judgment: false
  - id: D17
    description: "Live 10-record sample dry run with research enabled: 8 matched rows (exact PATCH payload + pre-registered predicted tier), 2 reasoned skip entries (no-domain, no_match), partitioning the sample exactly; zero HubSpot writes, zero n8n executions; no mock-fixture contamination (USE_MOCK_WEB_RESEARCH explicitly overridden false in-process, verified by zero 'exampleracing.example' occurrences in the committed artifact); no false-veto pattern (zero rows with absent region + geography-worded veto reason)"
    requirement: "SAFE-01"
    verification:
      - kind: other
        ref: ".planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-DRYRUN-PREDICTIONS.json + 51-SKIP-LOG.json (schema, partition, payload-key-set, tier-value, credential-leak and false-veto checks run this session, see Task 3 acceptance criteria)"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-19
status: complete
---

# Phase 51 Plan 02: Backfill Pipeline Gap-Fill Research and Live Sample Summary

**D-02 gap-fill research lane, D-04 skip contract, D-03 sizing gate, and a live 10-record capped-sample dry run -- 8 pre-registered predictions plus 2 reasoned skips, zero HubSpot writes, zero n8n executions**

## Performance

- **Duration:** ~25min
- **Started:** 2026-08-19T03:13:00Z (approx, first commit shortly after)
- **Completed:** 2026-08-19T03:26:19Z
- **Tasks:** 3
- **Files modified:** 5 (2 extended scripts/tests, 3 new committed artifacts)

## Accomplishments

- Extended `scripts/backfill_dry_run.py` with the D-02 gap-fill research lane
  (`research_gap_fields`/`apply_research_to_patch`), gated to exactly the four fields
  ZoomInfo cannot answer (`lv_org_type`, `lv_produces_content`, `lv_is_hardware_vendor`,
  `lv_is_gambling_operator`), issued only for records ZoomInfo matched, and structurally
  unreachable for unmatched records (the skip-and-continue sites sit before the research
  call site in the loop body).
- Added the D-04 skip contract (`build_skip_entry`) and an exact partition assertion in
  `run_dry_run` -- the predictions and skip-log id sets are proven disjoint with a union
  equal to the sample before the function returns, making a silently dropped company a
  structural impossibility rather than a hoped-for invariant.
- Fixed a live-data landmine caught during read-first: `select_never_scored_sample` was
  sorting by lexicographic string id, which silently misorders and mis-selects on this
  portal's mixed 10-/11-digit HubSpot ids (`9604614548` vs `10021111653`). Now sorts by
  `int(id)`, pinned by a test using exactly that pair.
- Added the D-03 sizing gate (`build_sizing_plan`/`write_sizing_markdown`), reusing the
  Plan 01 tracer's measured per-match cost (floored at the documented fallback) rather
  than re-deriving it, and asserting `sample_size <= credit_cap` before any enrich request
  -- called both standalone (`--sizing-out`, zero live-effect calls beyond two reads) and
  at the top of the full `run_dry_run` path.
- Ran the sizing computation live: `population_total=646`, `credit_balance=9396`,
  `credit_cap=8700`. Discovered the live `.env` carries `MAX_WEB_RESEARCH_PER_RUN=10` --
  tighter than the research doc's assumed default sample of 12 -- and sized the sample to
  10 to respect the operator's own configured research budget instead of overriding it.
  Committed `51-SIZING.md` before enriching a single record.
- Ran the capped 10-record sample live with the research lane enabled
  (`USE_MOCK_WEB_RESEARCH` explicitly overridden `false` in-process, since the live `.env`
  default of `true` would otherwise silently return fixture data). Result: 8 matched rows,
  2 skipped (one no-domain, one ZoomInfo `no_match`) -- exactly partitioning the sample.
  All 8 matched records were small country racing/turf clubs; live Claude web research
  found no broadcast/streaming presence for any of them, so all 8 landed Tier D on the
  no-content hard veto, each with real, per-record evidence URLs. Verified this is not the
  false-veto pattern (zero rows show an absent region paired with a geography-worded veto
  reason). Committed `51-DRYRUN-PREDICTIONS.json` and `51-SKIP-LOG.json`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Gap-fill research lane and the matched/unmatched partition contract** - `d6e9315` (feat, tdd)
2. **Task 2: Derive and commit 51-SIZING.md before any sample record is enriched** - `0e1c680` (feat)
3. **Task 3: Run the capped sample dry run and commit the predictions and skip-log artifacts** - `2a45e7e` (feat)

## Files Created/Modified
- `scripts/backfill_dry_run.py` - Extended: `GAP_FILL_FIELDS`, `MAX_RESEARCH_CALLS_DEFAULT`, `ANTHROPIC_PER_RECORD_ESTIMATE_USD`, `research_gap_fields`, `apply_research_to_patch`, `build_skip_entry`, `build_sizing_plan`, `write_sizing_markdown`, `--research`/`--sizing-out`/`--skip-out` CLI flags, numeric sample ordering
- `tests/test_backfill_dry_run.py` - 8 new tests (partition, gap-fill, sizing gate, empty-sample, ordering)
- `.planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-SIZING.md` - Committed live sizing artifact
- `.planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-DRYRUN-PREDICTIONS.json` - Committed live 8-row predictions artifact
- `.planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-SKIP-LOG.json` - Committed live 2-entry skip log

## Decisions Made
- Sample size 10 (not the research doc's assumed default 12) -- sized against the live
  `MAX_WEB_RESEARCH_PER_RUN=10` env value discovered during Task 2's live read, which was
  the binding constraint (the ZoomInfo credit cap of 8700 was nowhere close). Documented in
  `51-SIZING.md` and this summary rather than silently deviating from the research doc's
  number.
- `build_sizing_plan()`'s tracer-file read only fires when the caller passes no explicit
  `credits_per_match_hundredths` -- `run_dry_run()` always supplies its own explicit
  parameter (default unchanged at 108) so Plan 01's existing test suite needed zero
  changes to keep passing byte-for-byte.
- The FILL-04 adjacency-probe edge case (a record ZoomInfo matched but returned empty
  attributes) is left on the predictions side, per `51-RESEARCH.md`'s own resolution that
  it should be authored as a truth/test rather than auto-resolved to a new disposition --
  not reopened here; flagged in `51-RESEARCH.md` as still open for plan 03's operator
  checkpoint if a third category is wanted.

## Deviations from Plan

**1. [Rule 1 - discretion already granted] Sample size 10, not 12.** `51-RESEARCH.md`'s
Open Question 2 explicitly left sample size to "planner discretion," defaulting to 12
against the credit cap only. Task 2's live sizing read discovered
`MAX_WEB_RESEARCH_PER_RUN=10` in the live `.env` -- a real, operator-configured research
budget the research doc's arithmetic hadn't checked against. Sizing to 10 stays inside
both the credit cap and this budget without overriding an existing safety setting for one
run. Documented in `51-SIZING.md`'s figures table and this summary; no code or plan change
was needed.

**2. [Rule 1 - bug fix, pre-existing from Plan 01] Numeric sample ordering.**
`select_never_scored_sample`'s sort key was `r["id"]` (lexicographic string), inherited
unchanged from Plan 01. This portal's HubSpot ids mix 10- and 11-digit values
(`9604614548` vs `10021111653`), so a string sort both misorders the predictions rows and
can select a different 12-record slice than a numeric sort would. Fixed to `int(r["id"])`
before any credit was spent (caught during read-first, prior to Task 3's live run) and
pinned by `test_sample_order_is_ascending_id_stable`. Plan 01's own tests never exercised
mixed-digit ids, so this was safe to change with no regression.

No other deviations -- the D-02/D-04/D-03/D-05 mechanics were implemented as specified.

## Issues Encountered
- The live `--research`/`--measure-cost` run (Task 3) exceeded the Bash tool's 120s
  default timeout (10 live Anthropic web-research calls each take several seconds) and
  moved to background automatically; the background task completed with exit code 0
  before this session's next action, no manual intervention needed.
- Heredoc-based `git commit -m "$(cat <<'EOF' ... EOF)"` failed with a shell quoting error
  on the first commit message (same issue Plan 01 hit) -- resolved by writing the message
  to a scratch file under `/tmp` and using `git commit -F`.

## User Setup Required

None -- no external service configuration required. Live credentials
(`HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_PORTAL_ID`, `ZOOMINFO_CLIENT_ID`,
`ZOOMINFO_CLIENT_SECRET`, `ANTHROPIC_API_KEY`) already resolved from the repo-root `.env`
via `load_dotenv()`.

## Next Phase Readiness
- `51-DRYRUN-PREDICTIONS.json` is the artifact Plan 03 (before-snapshot) doesn't consume
  directly, but Phase 52 will: its row ordering, id set, payloads and predicted tiers are
  the contract every later write is compared against.
- Credit spend this phase so far: 1 (Plan 01 tracer) + 10 (this plan's sample, measured) =
  11 ZoomInfo credits, well inside the 13-credit ceiling the research doc estimated and the
  8700-credit cap `51-SIZING.md` derived. Live balance after this plan: 9396 - (measured
  spend); exact post-run balance not re-read a third time (the `--measure-cost` bracket
  already captured it in the raw `run_dry_run()` result, not surfaced separately in the
  committed predictions artifact beyond `credits_spent`).
- Full `after`-cursor pagination for the ~646-record never-scored population remains a
  Phase 52 prerequisite, unchanged from Plan 01's own flag -- this plan's sample stayed at
  10, well under the single-page `SAMPLE_SEARCH_LIMIT` of 100.
- Zero HubSpot writes and zero n8n executions occurred this plan, consistent with Phase
  51's structural constraint -- confirmed via the payload-key-set, tier-value, and
  credential-leak checks recorded above, plus a `post_webhook_event` grep against the
  driver source.

---
*Phase: 51-backfill-pipeline-credit-sizing-dry-run*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 6 files verified present on disk; all 3 commit hashes verified in git log.
