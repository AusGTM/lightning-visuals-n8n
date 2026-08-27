---
phase: 54-single-pass-armed-dispatch
plan: 07
subsystem: operator-claude-plugin
tags: [cost-disclosure, write-grant, pinning-test, gap-closure]

# Dependency graph
requires:
  - phase: 54-single-pass-armed-dispatch (03)
    provides: "the anthropic_usd PROJECTED relabelling (T-54-03/OP-54-05) this plan's
      sentence must stay consistent with"
provides:
  - "write_grant.py's rendered Anthropic-spend sentence states one relationship
    (projection) between the displayed figure and real spend, matching
    cost_rates.json's own citation for anthropic_usd_per_record"
  - "a pinning test scoped to the single Anthropic-spend line that fails on either
    discarded bound-word (worst case / floor), not just on a missing substring"
affects: [any future edit to write_grant.py's cost block; operator consent flow]

# Actuals (#2632)
actuals:
  tokens: 600
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Cite the rate table's own confidence/derivation text before choosing a
      bound-word for an operator-facing disclosure sentence, rather than picking one
      by preference"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_write_grant.py

key-decisions:
  - "Dropped BOTH bound-words (worst case AND floor) rather than keeping one — an
     average of two canary observations is neither an upper bound real spend cannot
     exceed nor a lower bound it is guaranteed to reach. Used the review's own
     suggested replacement: 'a projection from the dated rate table above.'"
  - "Scoped the strengthened test assertion to the single Anthropic-spend line
     (figures['block'].splitlines(), filtered by 'Anthropic model spend'), not the
     whole rendered block — the provider-credits table header a few lines above
     legitimately says 'Worst-case credits' and must not be caught by a block-wide
     negative assertion."

patterns-established: []

requirements-completed: [G-3]

coverage:
  - id: D1
    description: "The rendered Anthropic-spend sentence states one relationship
      between the figure and real spend (WR-04): no more 'worst case ... a floor'
      contradiction"
    requirement: G-3
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_anthropic_figure_is_labelled_projected_never_measured"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pinning test reads only the Anthropic-spend line and fails if
      either discarded bound-word (worst case / floor) returns, without touching the
      provider-credits table's legitimate ceiling wording"
    requirement: G-3
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_anthropic_figure_is_labelled_projected_never_measured"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (full suite: 3223 passed, 154 skipped)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-08-27
status: complete
---

# Phase 54 Plan 07: Anthropic-spend sentence bound-word contradiction (WR-04) Summary

**Replaced the contradictory "worst case ... a floor" Anthropic-spend sentence in
`write_grant.py`'s rendered cost block with a single "projection" framing that matches
`cost_rates.json`'s own citation for `anthropic_usd_per_record`, and re-scoped the
pinning test to the one sentence so it fails on either discarded bound-word.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-08-27T15:10:00+10:00
- **Completed:** 2026-08-27T15:19:26+10:00
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Closed WR-04: `write_grant.py`'s Anthropic-spend sentence no longer calls the same
  dollar figure both "worst case" (a ceiling) and "a floor" (a lower bound). The
  sentence now reads: `Anthropic model spend: **$X** — a projection from the dated rate
  table above, not a measurement (this repo never reads back real Anthropic usage).`
  This matches `config/cost_rates.json`'s citation for `anthropic_usd_per_record`
  (0.068624 USD/record) — an observed all-in average across two Phase 22 canary
  executions (332, 337), not a bound in either direction.
- Strengthened `test_the_anthropic_figure_is_labelled_projected_never_measured`: the
  final assertion no longer pins the substring `"floor"` (which a re-introduced
  contradiction could satisfy alongside "worst case"). It now extracts the single
  Anthropic-spend line from `figures["block"]` and asserts `"projection"` is present
  while both `"worst case"` and `"floor"` are absent — scoped so the provider-credits
  table's legitimate `"Worst-case credits"` header a few lines above is never caught.
  The three `basis` assertions (PROJECTED/MEASURED for `anthropic_usd`,
  `projected_executions`, `record_count`) were left untouched.

## Task Commits

1. **Task 1: State one bound in the Anthropic-spend sentence and make the test check
   the meaning** — `5cafcf0` (fix)

## Files Created/Modified
- `operator-claude-plugin/scripts/write_grant.py` — Anthropic-spend sentence rewritten
  from "worst case — a floor" to "a projection from the dated rate table above"
- `operator-claude-plugin/tests/test_write_grant.py` — final assertion of the pinning
  test rescoped to the single Anthropic-spend line; docstring extended with the WR-04
  reasoning

## Decisions Made
- Dropped both bound-words rather than keeping one, per the plan's evidence-based
  instruction: an average of two observations is neither a true ceiling nor a true
  floor, so neither pre-existing word was correct.
- Test assertion scoped to one line rather than the whole block, to avoid false-failing
  on the provider-credits table's legitimately-worded ceiling language.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

This closes the last of Phase 54's gap-closure findings from `54-REVIEW.md` (WR-01
through WR-04, IN-02 — WR-01/02/03/IN-02 closed by 54-06, WR-04 closed here). Phase 54
is ready to be sealed complete. No functional change: both framings pointed at the
identical, correctly-computed figure, so this closes a clarity defect only.

---
*Phase: 54-single-pass-armed-dispatch*
*Completed: 2026-08-27*

## Self-Check: PASSED

Both claimed files confirmed present on disk; task commit hash `5cafcf0` confirmed
present in `git log`.
