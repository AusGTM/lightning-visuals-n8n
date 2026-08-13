---
phase: 49-re-score-strategy-reporting
plan: 01
subsystem: scoring-backfill
tags: [python, hubspot-crm-v3-batch, icp-scoring, dry-run-cli, pytest]

# Dependency graph
requires:
  - phase: 40-scoring-engine-remediation
    provides: scripts/backfill_seed_company_scores.py (compute_components, build_updates, batch write mechanism)
  - phase: 46-rubric-decision-simulation-engine-parity
    provides: config/icp_scoring.yaml rubric weight change that opened the parity-red window this plan's driver closes
provides:
  - scripts/rescore_population.py with --plan/--snapshot/--canary/--execute modes
  - enforce_exact_population() in scripts/backfill_seed_company_scores.py (raised ceiling 25->100)
  - offline test coverage proving zero live writes possible from any test in this plan
affects: [49-02, 49-05, 49-07]

actuals:
  tokens: 12896
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Add-alongside, never in-place: enforce_exact_population() is a second, independent predicate next to enforce_sample_cap(), both required"
    - "Re-derive-and-confirm: population read twice immediately before any write, refusing on drift (D-03)"
    - "Disarmed write legs skip the transport call entirely (not just its dry_run branch) so a stub records literally zero calls"
    - "Canary selection by rule (sorted first individual_club_team id, falling back to a stored-vs-computed diff), never a hard-coded id"

key-files:
  created:
    - scripts/rescore_population.py
    - tests/test_rescore_population.py
  modified:
    - scripts/backfill_seed_company_scores.py
    - tests/test_backfill_seed_company_scores.py

key-decisions:
  - "HARD_CEILING_RECORDS raised 25->100 as a strengthening (paired with the new exact-set gate), not a relaxation -- documented inline to prevent future misreading"
  - "rescore_population.py is a new thin wrapper importing compute_components/build_updates/_chunked/enforce_sample_cap/enforce_exact_population unchanged, never a fork"
  - "Disarmed --canary/--execute skip calling batch_update_companies entirely rather than relying on that function's own dry_run short-circuit, so stubbed-transport tests can assert zero calls, not just zero network calls"
  - "Population is re-derived TWICE (derive, then re-confirm) immediately before every write leg, refusing on any drift between the two reads -- catches a live race the single-derivation --plan mode cannot"
  - "--snapshot never consults _writes_allowed() -- it has no write code path at all, by construction, not by a runtime check"

patterns-established:
  - "Integer-only cost estimation: estimate_rescore_cost() uses only integer division/multiplication, tests assert isinstance(v, int) on every cost key"
  - "Cross-plan JSON contract: --plan's top-level key set (ids, population_count, derived_at, chunk_size, chunks, max_records, window, arm_keys, arms_n8n_allowlist, cost) is pinned by an explicit key-set test since plan 49-02 parses it by name"

requirements-completed: [RESCORE-01, RESCORE-02]

coverage:
  - id: D1
    description: "Exact-set population gate (enforce_exact_population) refuses any sample that is not exactly the live-derived scored population -- boundary-tested against a permuted copy, a 65-of-66 subset, a 67-id superset, and an empty set"
    requirement: RESCORE-01
    verification:
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py#test_enforce_exact_population_true_for_permuted_copy"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py#test_enforce_exact_population_false_for_subset_missing_one_id"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py#test_enforce_exact_population_false_for_superset_extra_one_id"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py#test_enforce_exact_population_false_for_empty_sample_against_nonempty_live"
        status: pass
    human_judgment: false
  - id: D2
    description: "Count cap (enforce_sample_cap) still accepts a sample at the resolved ceiling and refuses one above it, with HARD_CEILING_RECORDS raised to 100"
    requirement: RESCORE-01
    verification:
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py#test_backfill_sample_cap_at_new_ceiling_still_allowed"
        status: pass
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py#test_backfill_hard_ceiling_is_100_not_25"
        status: pass
    human_judgment: false
  - id: D3
    description: "--plan mode's weight-branch cost figures are integer, budget-bounded, and derived from module constants (n8n_executions/anthropic_calls/provider_credits: 0, hubspot_batch_calls: ceil(n/BATCH_CHUNK_SIZE))"
    requirement: RESCORE-01
    verification:
      - kind: unit
        ref: "tests/test_rescore_population.py#test_estimate_rescore_cost_weight_branch_all_zero_except_batch_calls"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_estimate_rescore_cost_veto_branch_n8n_executions_equals_record_count"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_estimate_rescore_cost_hubspot_batch_calls_is_integer_ceiling"
        status: pass
    human_judgment: false
  - id: D4
    description: "--plan and --snapshot both refuse loudly (non-zero exit, no document printed) on an empty live population read rather than emitting a clean empty report"
    requirement: RESCORE-03
    verification:
      - kind: unit
        ref: "tests/test_rescore_population.py#test_main_plan_mode_refuses_on_empty_population"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_snapshot_empty_population_refuses"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every batch payload the driver builds carries exactly the five COMPONENT_PROPS keys and no others -- catches both an over-broad write and a missing component"
    requirement: RESCORE-01
    verification:
      - kind: unit
        ref: "tests/test_rescore_population.py#test_assert_payload_scope_raises_on_missing_component"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_assert_payload_scope_raises_on_sixth_key"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_execute_payload_component_keys_are_exact"
        status: pass
    human_judgment: false
  - id: D6
    description: "The driver refuses to write when either arm key is absent (DRY_RUN=false alone or ALLOW_SCORE_BACKFILL=true alone are each insufficient), and its default invocation (no flags) is --plan, which is dry by construction"
    requirement: RESCORE-01
    verification:
      - kind: unit
        ref: "tests/test_rescore_population.py#test_execute_disarmed_no_arm_vars_builds_prints_no_write"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_execute_dry_run_false_but_allow_unset_zero_writes"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_main_default_mode_is_plan"
        status: pass
    human_judgment: false
  - id: D7
    description: "The canary write leg selects its one record by rule (lower sorted id whose lv_org_type is individual_club_team, falling back to the first id whose freshly computed components differ from what is stored) -- never a hard-coded id -- writes exactly one record, and --execute --already-written excludes it from the remainder"
    verification:
      - kind: unit
        ref: "tests/test_rescore_population.py#test_canary_selects_lower_sorted_individual_club_team_id"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_canary_selection_changes_when_stub_ids_change"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_canary_fallback_when_no_individual_club_team_record"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_execute_already_written_excludes_canary_sends_65"
        status: pass
    human_judgment: false
  - id: D8
    description: "--snapshot census mode emits a dated, deterministically-ordered JSON census (byte-identical across two runs of the same data apart from derived_at) whose tier_distribution sums to the population count, with a blank tier counted under a distinct key rather than dropped"
    requirement: RESCORE-03
    verification:
      - kind: unit
        ref: "tests/test_rescore_population.py#test_snapshot_population_count_and_tier_sum"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_snapshot_byte_identical_across_two_runs_except_derived_at"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_snapshot_none_tier_counted_as_distinct_key_not_dropped"
        status: pass
      - kind: unit
        ref: "tests/test_rescore_population.py#test_snapshot_makes_zero_writes_even_when_armed"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-08-13
status: complete
---

# Phase 49 Plan 01: Dry Re-score Lane -- Population, Exact-Set Gate, Components, Plan Output Summary

**Built `scripts/rescore_population.py` (four CLI modes: `--plan`/`--snapshot`/`--canary`/`--execute`) plus `enforce_exact_population()` in `scripts/backfill_seed_company_scores.py`, giving the operator a code-derived, budget-bounded re-score plan and census with zero live HubSpot writes possible from any test.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-08-13T03:41:37Z
- **Completed:** 2026-08-13T03:57:42Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `enforce_exact_population(sample_ids, live_ids)` -- a second, independent predicate (D-03) added alongside `enforce_sample_cap`, never replacing it; `HARD_CEILING_RECORDS` raised 25->100 with an inline comment stating the strengthening explicitly.
- `scripts/rescore_population.py --plan`: re-derives the live scored population, emits an integer-only, budget-bounded plan (`ids`, `population_count`, `derived_at`, `chunk_size`, `chunks`, `max_records`, `window`, `arm_keys`, `arms_n8n_allowlist`, `cost`) with zero writes possible on this code path; refuses loudly on a portal mismatch or an empty population read.
- `--canary`/`--execute`: two-key-armed write legs. `_derive_and_confirm_population()` re-derives the population TWICE immediately before any write and refuses on drift. Canary selection is rule-based (never a literal id). Every payload is scope-asserted to exactly the five component properties before ever reaching `batch_update_companies`. Disarmed invocations skip the transport call entirely.
- `settle_population()`: polls until two consecutive reads of a property agree, defaulting `timeout=300` (generous for an untested 66-record simultaneous batch, not the single-record 11s Phase 40-07 figure).
- `--snapshot [--out PATH]`: a dated, deterministically-ordered JSON census of the live scored population plus a tier-distribution roll-up, with no write path at all; refuses on an empty population read.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end dry re-score lane -- population, exact-set gate, components, plan output** - `5df4d3a` (feat)
2. **Task 2: The armed write legs -- canary first, then the remainder, in one window (TDD)** - `b26aee2` (test, RED) / `1a8c5a3` (feat, GREEN)
3. **Task 3: `--snapshot` census mode for the three-point report (TDD)** - `f13e97b` (test, RED) / `2b21f78` (feat, GREEN)

_Task 1 was `type="tracer"`, not TDD -- code and tests landed in one commit, with the plan's own `<verify>` re-run afterward as the tracer feedback gate (autonomous run, gate passed, expansion continued)._

## Files Created/Modified
- `scripts/rescore_population.py` - New driver: `select_scored_population`, `estimate_rescore_cost`, `build_plan`, `assert_payload_scope`, `_derive_and_confirm_population`, `select_canary`, `settle_population`, `build_snapshot`, `run_plan`/`run_canary`/`run_execute`/`run_snapshot`, CLI dispatch
- `scripts/backfill_seed_company_scores.py` - `HARD_CEILING_RECORDS` 25->100; added `enforce_exact_population()`
- `tests/test_rescore_population.py` - New, 37 tests covering all four modes offline, zero network
- `tests/test_backfill_seed_company_scores.py` - Extended with exact-set gate coverage and a ceiling-value pin

## Decisions Made
- Raised `HARD_CEILING_RECORDS` to 100 rather than forking a new constant -- the exact-set gate is the actual enforcement mechanism now; the count cap is defense-in-depth, documented inline so a future reader does not mistake the raise for a relaxation.
- `_derive_and_confirm_population()` re-derives the population a second time immediately before any write and compares via `enforce_exact_population` -- catches a race between "what --plan showed" and "what is live right now" that a single-derivation design would miss, at the cost of one extra read per write invocation.
- Disarmed `--canary`/`--execute` skip calling `batch_update_companies` entirely (rather than always calling it with `dry_run=True` and relying on that function's own short-circuit) so a stubbed-transport test can assert literally zero calls to the transport, not just zero network traffic -- a stricter, more testable guarantee.
- `_apply_max_records_default()` uses `os.environ.setdefault("BACKFILL_MAX_RECORDS", ...)` rather than a local-only resolver, per the plan's explicit instruction; every test exercising `main()` monkeypatches (`delenv`) that key first so pytest's fixture teardown cleans up the mutation regardless of what the production code sets it to.

## Deviations from Plan

None - plan executed exactly as written. All three tasks, their `<behavior>`/`<action>`/`<acceptance_criteria>` blocks, and the `must_haves.truths` were implemented literally per the plan and 49-RESEARCH.md/49-PATTERNS.md's cited analogs.

## Issues Encountered
- Initial commit attempt via inline heredoc (`git commit -m "$(cat <<'EOF' ... EOF)"`) failed with a shell parse error unrelated to the message content; switched to writing the message to a scratch file and using `git commit -F <file>`, which worked cleanly for all five commits.
- One early test (`test_backfill_sample_cap_at_new_ceiling_still_allowed`) was written against the wrong resolved default (assumed the ceiling raise alone would apply at 100 records with `BACKFILL_MAX_RECORDS` unset, when the module's own `DEFAULT_MAX_RECORDS` of 10 still applies unless the env var is set) -- caught immediately by the offline test run, fixed to explicitly set `BACKFILL_MAX_RECORDS=100` before asserting the ceiling behavior.

## User Setup Required

None - no external service configuration required. No live HubSpot credentials were used; every test in this plan runs offline against a stubbed transport.

## Next Phase Readiness
- `scripts/rescore_population.py --plan`/`--snapshot`/`--canary`/`--execute` are ready for plan 49-02's runbook (`docs/OPERATOR-RESCORE.md`) to document and for plan 49-05 to exercise live.
- `--plan`'s top-level key contract (`ids`, `population_count`, `derived_at`, `chunk_size`, `chunks`, `max_records`, `window`, `arm_keys`, `arms_n8n_allowlist`, `cost`) is pinned by an offline test; plan 49-02's runbook verify may parse it by these literal names.
- `--snapshot`'s `derived_at`/`population_count` keys are shared verbatim with `--plan`, ready for plan 49-07's three-point (P1/P2/P3) report to consume committed JSON without a further live read.
- No blockers. The D-09 pinned-rubric guard test and the operator runbook itself remain out of this plan's scope (owned by later plans per the pattern map).

---
*Phase: 49-re-score-strategy-reporting*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 5 created/modified files found on disk; all 5 task commit hashes found in `git log --oneline --all`.
