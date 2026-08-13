---
phase: 49-re-score-strategy-reporting
plan: 02
subsystem: docs-and-testing
tags: [operator-runbook, pytest, pyyaml, hubspot-crm-v3-search, icp-scoring]

# Dependency graph
requires:
  - phase: 49-re-score-strategy-reporting plan 01
    provides: scripts/rescore_population.py's --plan mode (ids/population_count/derived_at/chunk_size/chunks/max_records/window/arm_keys/arms_n8n_allowlist/cost key contract)
provides:
  - docs/OPERATOR-RESCORE.md (both branches, decision-rule-first runbook, numbers copied from a committed capture)
  - .planning/phases/49-re-score-strategy-reporting/49-PLAN-OUTPUT.json (the committed --plan capture the runbook cites, plus an offline veto-branch cost figure)
  - tests/test_rubric_change_guard.py (assert_rubric_pinned() -- D-09's permanent guard against an unaccompanied rubric weight change)
affects: [49-05, 49-07]

actuals:
  tokens: 5175
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Runbook numbers copied verbatim from a committed machine capture, never hand-typed (D-07) -- enforced here by a verify script that string-matches the JSON's population_count/chunk_size/chunks/max_records against the doc text"
    - "Guard logic lives inside the test file itself (no separate production module) -- same shape as tests/test_companies_factory_frozen.py; assert_rubric_pinned() is both the pin and the thing under test"
    - "TDD RED/GREEN on a self-contained guard: RED = a stub assert_rubric_pinned() that never raises (4 mutation tests + the message test fail); GREEN = the real per-key diff comparison"

key-files:
  created:
    - docs/OPERATOR-RESCORE.md
    - tests/test_rubric_change_guard.py
    - .planning/phases/49-re-score-strategy-reporting/49-PLAN-OUTPUT.json
  modified: []

key-decisions:
  - "Captured --plan live against portal 22617666 through the absolute-path dotenv wrapper rather than reusing 49-01's committed test fixtures -- D-07 requires the runbook's own numbers to trace to a live capture, not a unit-test stub"
  - "Added a second, clearly-labeled block to the committed capture (veto_branch_cost_documented_not_exercised) computed offline via estimate_rescore_cost(ids, branch='veto') against the same 66-id population, rather than inventing a hand-typed veto-branch total -- keeps D-07's 'no hand-typed number' rule extending to the veto branch's total too, while the field name and an inline note make explicit that no live recompute POST was sent"
  - "Guard test pins base_score's four component tables plus graduated_deductions as a Python dict literal compared key-by-key (not a whole-file digest) -- the mismatch message can then name exactly which keys moved, which a digest comparison could not do"

patterns-established:
  - "Verify-script JSON<->doc cross-check: a plan task's <verify> block parses the committed JSON capture and asserts each cited figure appears verbatim in the doc's prose, catching drift mechanically rather than by review"

requirements-completed: [RESCORE-01, RESCORE-02]

coverage:
  - id: D1
    description: "docs/OPERATOR-RESCORE.md leads with the veto-predicate classifier (Step 1) before any procedural/write content, covering both the weight branch (0 n8n/Anthropic/provider cost) and the veto branch (documented-not-exercised, cost attributed to Phase 47.5's measured executions 11858-11861)"
    requirement: RESCORE-01
    verification:
      - kind: manual_procedural
        ref: "docs/OPERATOR-RESCORE.md -- Step 1 section precedes 'Which records'/'Invocation'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every population/chunk/cost figure quoted in the runbook is copied from the committed 49-PLAN-OUTPUT.json, captured live via scripts/rescore_population.py --plan (population_count=66, chunk_size=100, chunks=1, max_records=100, arms_n8n_allowlist=false)"
    requirement: RESCORE-02
    verification:
      - kind: other
        ref: "task 49-02-01's <verify> one-liner: json.loads the capture, assert population_count/chunk_size/chunks/max_records each appear (str-cast) in docs/OPERATOR-RESCORE.md's text -- exit 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "assert_rubric_pinned() fails an unaccompanied config/icp_scoring.yaml weight change (org_type, revenue_band, geography, and a re-introduced graduated_deductions key), with a failure message naming docs/OPERATOR-RESCORE.md and the re-score obligation"
    requirement: RESCORE-02
    verification:
      - kind: unit
        ref: "tests/test_rubric_change_guard.py::test_mutated_rubric_fails_the_guard[org_type_weight_changed]"
        status: pass
      - kind: unit
        ref: "tests/test_rubric_change_guard.py::test_mutated_rubric_fails_the_guard[revenue_band_weight_changed]"
        status: pass
      - kind: unit
        ref: "tests/test_rubric_change_guard.py::test_mutated_rubric_fails_the_guard[geography_weight_changed]"
        status: pass
      - kind: unit
        ref: "tests/test_rubric_change_guard.py::test_mutated_rubric_fails_the_guard[graduated_deduction_reintroduced]"
        status: pass
      - kind: unit
        ref: "tests/test_rubric_change_guard.py::test_failure_message_names_runbook_and_rescore_obligation"
        status: pass
      - kind: unit
        ref: "tests/test_rubric_change_guard.py::test_pinned_rubric_matches_current_config"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-08-13
status: complete
---

# Phase 49 Plan 02: Operator Re-score Runbook + D-09 Rubric-Change Guard Summary

**`docs/OPERATOR-RESCORE.md` (decision-rule-first, both branches, every figure copied from a committed live `--plan` capture) plus `tests/test_rubric_change_guard.py`, an offline pytest that fails an unaccompanied `config/icp_scoring.yaml` weight change with a message naming the runbook.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-08-13T04:01:11Z
- **Completed:** 2026-08-13T04:23:00Z
- **Tasks:** 2
- **Files modified:** 3 (all new)

## Accomplishments
- `docs/OPERATOR-RESCORE.md`: Step 1 is the veto-predicate classifier (non-ANZ / no-content / hardware-vendor), answered before any procedural step; the weight branch (this phase's own change) and the documented-not-exercised veto branch each carry a distinct, sourced cost line.
- `.planning/phases/49-re-score-strategy-reporting/49-PLAN-OUTPUT.json`: a live `scripts/rescore_population.py --plan` capture against portal `22617666` (66-record population, `derived_at 2026-08-13T04:01:11.038812+00:00`), the only source the runbook's numeric claims cite. A second offline block (`veto_branch_cost_documented_not_exercised`) applies the measured Phase 47.5 per-record unit cost to this population without sending any live recompute POST.
- `tests/test_rubric_change_guard.py::assert_rubric_pinned()`: pins `base_score` (org_type/produces_content/geography/revenue_band) and `graduated_deductions` (pinned empty on purpose) as a literal, diffs key-by-key against the loaded live config, and raises one `AssertionError` naming every offending key plus `docs/OPERATOR-RESCORE.md` and the re-score obligation.
- Runbook states the engines-first-then-re-score sequencing rule by name (`config/icp_scoring.yaml` and HubSpot flow `4626124224`), the exact-set-gate-is-stronger-than-a-ceiling point, and the canary rationale (HubSpot's default-value stamp is API-unreadable, so the batch write is proven on one record first).

## Task Commits

Each task was committed atomically:

1. **Task 1: docs/OPERATOR-RESCORE.md + committed `--plan` capture** - `b303d21` (docs)
2. **Task 2: D-09 guard test (TDD)** - `e9b4d09` (test, RED) / `76757bd` (feat, GREEN)

_Task 2's RED commit ships a stub `assert_rubric_pinned()` that never raises, so all four mutation tests and the message-content test fail (5 failed, 1 passed) while the pass-through test trivially passes; GREEN replaces the stub with the real per-key diff comparison (6/6 pass)._

## Files Created/Modified
- `docs/OPERATOR-RESCORE.md` - Operator runbook: decision-rule classifier, population/chunk/cost figures, exact-set-gate rationale, engines-first sequencing, canary rationale, four literal invocation commands, acceptance criterion, AMENDMENT-block convention
- `.planning/phases/49-re-score-strategy-reporting/49-PLAN-OUTPUT.json` - Committed live `--plan` capture (66 ids, cost, chunking) plus an offline veto-branch cost projection over the same population
- `tests/test_rubric_change_guard.py` - New offline guard test: pinned rubric literal, `assert_rubric_pinned()`, 6 tests (1 pass-through, 4 mutation cases, 1 message-content assertion)

## Decisions Made
- Captured `--plan` live rather than reusing any fixture, since D-07 requires the runbook's cited numbers to trace to a live capture, not a stubbed test.
- Added the veto-branch total to the committed JSON as a separately-labeled, explicitly-noted-as-offline field rather than a hand-typed number in the doc — keeps every runbook figure sourced from the committed capture, including the one branch this phase does not exercise live.
- Pinned the rubric as a Python dict literal compared key-by-key rather than a whole-file digest, so the guard's failure message can name exactly which keys changed.

## Deviations from Plan

None - plan executed exactly as written. Both tasks, their `<action>`/`<behavior>`/`<acceptance_criteria>` blocks, and the plan's `must_haves.truths` were implemented literally, cross-checked against 49-PATTERNS.md's cited analogs (`docs/OPERATOR-VETO-REFRESH.md` voice/structure, `tests/test_companies_factory_frozen.py`'s explicit-reviewed-re-baseline header idiom).

## Issues Encountered
- Inline heredoc commit messages (`git commit -m "$(cat <<'EOF' ... EOF)"`) failed with an unrelated shell parse error, same as noted in 49-01's summary — worked around by writing each message to a scratch file and using `git commit -F <file>`.

## User Setup Required

None - no external service configuration required. The one live network call this plan made (`scripts/rescore_population.py --plan`'s HubSpot search) was read-only, made once, and its output is now committed; no further live access is needed to read or reason about this plan's deliverables.

## Next Phase Readiness
- `docs/OPERATOR-RESCORE.md` and its committed capture are ready for plan 49-05 to follow when W1 opens live (the runbook's four invocation commands are exactly the ones 49-05 will run).
- `tests/test_rubric_change_guard.py` is a permanent, always-on guard from this commit forward — it runs in every future offline suite invocation with zero setup.
- No blockers. Plan 49-05 (execute W1) and plan 49-07 (the three-point RESCORE-03 report) remain out of this plan's scope, per the pattern map.

---
*Phase: 49-re-score-strategy-reporting*
*Completed: 2026-08-13*

## Self-Check: PASSED
