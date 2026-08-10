---
phase: 45-burn-rate-alarm
plan: 03
subsystem: infra
tags: [n8n, execution-budget, drift-test, release, requirements-traceability]

# Dependency graph
requires:
  - phase: 45-01
    provides: config/execution_budget.yaml's monthly_execution_allowance /
      idle_floor_max_share mirrored into operator.local.example.json
      (n8n_monthly_execution_allowance, n8n_schedule_floor_max_share,
      burn_rate_alarm_threshold) — the two numbers this plan's drift test pins
  - phase: 45-02
    provides: n8n_cadence.TICKS_PER_MONTH — the runtime table this plan's drift test
      compares against tests/test_execution_budget.py's build-time table
provides:
  - tests/test_execution_budget_drift.py — the only thing connecting
    config/execution_budget.yaml to the plugin's example config; a repo-side guard
    against the two silently disagreeing
  - operator-claude-plugin plugin.json 0.13.0 + CHANGELOG entry documenting the
    upgrade step and the ships-inert limit
  - REQUIREMENTS.md traceability rows for ALARM-01..04/LOOK-01/FLOOR-01, each with a
    concrete test pointer
affects: []

# Actuals (#2632)
actuals:
  tokens: 3550
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backend-to-plugin import in a repo-side test (operator-claude-plugin/scripts
      inserted on sys.path, then `import n8n_cadence`) — the unguarded direction,
      already precedented by scripts/june_run_arm.py; test_no_backend_imports.py
      only guards the opposite (plugin-to-backend) direction."
    - "Drift test: direct-index both sides of a duplicated config number, assert
      numeric type, assert equality, name both files/keys/values in the failure
      message — mirrors tests/test_execution_budget.py's own T-44-07 pattern."

key-files:
  created:
    - tests/test_execution_budget_drift.py
  modified:
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "The plan's literal collected-count acceptance criteria (2562 total, 1291+
    plugin) were written against an earlier baseline and no longer match
    post-45-01/45-02 reality (2481 passed/121 skipped repo-wide, 1326/5 plugin) —
    the 0-failures assertions, which are the actual binding contract, all hold.
    Recorded rather than silently worked around, matching 45-02's precedent for
    the same class of stale-literal mismatch."
  - "Traceability rows for all six requirements were already marked Complete (with
    body checkboxes already ticked) by 45-01/45-02's own docs commits, but bare —
    no pointer. This plan's Task 3 work was adding the concrete test-name pointer
    to each row, not flipping Pending to Complete."

patterns-established: []

requirements-completed: [ALARM-01, ALARM-02, ALARM-03, ALARM-04, LOOK-01, FLOOR-01]

coverage:
  - id: D1
    description: "The drift test's three assertions pass on the committed files, and
      each fails with a message naming both files/keys when either allowance value,
      the floor share, or the TICKS_PER_MONTH table is deliberately perturbed"
    requirement: "ALARM-03"
    verification:
      - kind: unit
        ref: "tests/test_execution_budget_drift.py::test_plugin_example_allowance_matches_the_budget_file"
        status: pass
      - kind: unit
        ref: "tests/test_execution_budget_drift.py::test_plugin_example_floor_share_matches_the_budget_file"
        status: pass
      - kind: unit
        ref: "tests/test_execution_budget_drift.py::test_cadence_ticks_per_month_agrees_with_the_budget_guard"
        status: pass
      - kind: manual
        ref: "temporarily set n8n_monthly_execution_allowance to 2000 -> test one fails naming both files; temporarily set n8n_schedule_floor_max_share to 0.5 -> test two fails; deleted monthly_execution_allowance from the YAML -> KeyError, not a pass; all three reverted after checking"
        status: pass
    human_judgment: false
  - id: D2
    description: "Plugin ships at 0.13.0 with a CHANGELOG entry naming all three new
      config keys, the by-design first-sweep burn_rate_not_configured notice, and the
      ships-inert (no cron/launchd installed) limit"
    verification:
      - kind: unit
        ref: "python3 -c \"import json;print(json.load(open('operator-claude-plugin/.claude-plugin/plugin.json'))['version'])\" prints 0.13.0"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py -q"
        status: pass
    human_judgment: false
  - id: D3
    description: "All six Phase 45 requirement rows carry a Complete status with a
      concrete test pointer, ALARM rows stating closure is by unit test against
      synthetic execution history (not a live scheduled fire), on three green suites"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q -> 2481 passed, 121 skipped"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests -q -> 1326 passed, 5 skipped"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs -> 656 passed, 0 failed"
        status: pass
    human_judgment: false

# Metrics
duration: ~20min
completed: 2026-08-10
status: complete
---

# Phase 45 Plan 03: Drift Test, Release, Requirements Closure Summary

**A repo-side test that fails when the plugin's example config's allowance/floor-share
values or its runtime TICKS_PER_MONTH table disagree with `config/execution_budget.yaml`
or the build-time budget guard, the plugin shipped at 0.13.0 with an honest upgrade-step
CHANGELOG entry, and all six Phase 45 requirement rows closed against concrete, currently-
passing test pointers.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-10 (this session, after 45-02)
- **Completed:** 2026-08-10
- **Tasks:** 3
- **Files modified:** 3 modified, 1 created

## Accomplishments

- `tests/test_execution_budget_drift.py` — three assertions, each direct-indexing both
  sides of a duplicated number (never `.get()`, never a default): the plugin example's
  `n8n_monthly_execution_allowance` against the YAML's `monthly_execution_allowance`, the
  plugin example's `n8n_schedule_floor_max_share` against the YAML's
  `idle_floor_max_share`, and `n8n_cadence.TICKS_PER_MONTH` against
  `tests/test_execution_budget.py`'s own table (comparing only shared keys — `n8n_cadence`
  deliberately carries a `seconds` row the build-time guard has no need of)
- The drift test performs the backend-to-plugin import direction
  (`operator-claude-plugin/scripts` inserted on `sys.path`, then `import n8n_cadence`) —
  precedented by `scripts/june_run_arm.py`, unguarded by `test_no_backend_imports.py`
  (which only forbids the opposite direction)
- `operator-claude-plugin` shipped at **0.13.0** (minor bump — new operator-visible sweep
  behaviour and a new cadence refusal, nothing removed/renamed) with a CHANGELOG entry
  naming all three new config keys verbatim, the by-design first-sweep
  `burn_rate_not_configured` notice, and the fact that this release installs no cron or
  launchd schedule
- All six Phase 45 requirement rows (`ALARM-01..04`, `LOOK-01`, `FLOOR-01`) — already
  marked Complete by 45-01/45-02's own docs commits but bare — now carry a concrete test
  file + test name pointer; the four ALARM rows state plainly that closure is by unit test
  against synthetic execution history, never a live scheduled fire (the roadmap's own
  ships-inert note)

## Task Commits

1. **Task 1: The drift test** — `a567764` (test)
2. **Task 2: Ship it — version 0.13.0 and a CHANGELOG entry** — `e0f814b` (docs)
3. **Task 3: Close the six requirement rows against real pointers** — `0d4c8a4` (docs)

_Note: Task 1 was `tdd="true"` — the test was written and immediately passed on the
committed files, then verified to fail correctly under each of the four perturbations
listed in `<behavior>` (allowance edit, floor-share edit, key deletion) before being
reverted; no RED/GREEN commit split was needed since the drift the test guards against
does not exist in the committed tree today._

## Files Created/Modified

- `tests/test_execution_budget_drift.py` — new module: three assertions, `ROOT`
  resolution matching `tests/test_execution_budget.py`, direct-indexing throughout
- `operator-claude-plugin/.claude-plugin/plugin.json` — `version` 0.12.0 → 0.13.0
- `operator-claude-plugin/CHANGELOG.md` — `[0.13.0]` section: burn-rate alarm, time-
  windowed lookback, cadence budget floor, explicit upgrade step, ships-inert statement
- `.planning/REQUIREMENTS.md` — traceability table: six bare "Complete" rows given
  concrete test-name pointers

## Decisions Made

- **Stale literal acceptance-criteria numbers, not re-chased.** The plan's `<verify>`/
  `acceptance_criteria` cite specific collected-test counts (2562 total, 1291+ plugin)
  written against an earlier baseline. Current reality (2481 passed/121 skipped repo-wide,
  1326 passed/5 skipped plugin, 656/0 node) reflects 45-01/45-02's own test additions
  landing since the plan was authored. The counts don't match the plan's literal numbers,
  but the actual binding contract — zero failures on all three suites — holds exactly.
  Recorded here rather than silently adjusted, mirroring 45-02's own precedent for this
  exact class of situation (a plan-time snapshot going stale by the time it executes).
- **Task 3 was pointer-writing, not status-flipping.** All six requirement rows were
  already `Complete` with ticked body checkboxes, written by 45-01/45-02's own completion
  commits — `grep -c "Phase 45 | Pending"` was already 0 before this task started. The
  plan's actual remaining work was the concrete pointer each row lacked; verified this by
  reading the file before touching it rather than assuming the plan's premise ("six rows
  currently Pending") was still literally true.

## Deviations from Plan

None beyond the two decisions above (both are acceptance-criteria interpretation calls
with pre-existing precedent, not code deviations). No auto-fixes were needed — the drift
test passed on the first write, the plugin manifest test passed unmodified after the
version bump, and all three suites were already green before Task 3's edit and remained
green after it.

## Issues Encountered

None.

## User Setup Required

None beyond what 45-01/45-02 already documented. The CHANGELOG's upgrade-step section
restates, for a human reading the release notes rather than the plugin's own example
config, that an existing `operator.local.json` needs the three new keys added and that the
first sweep after upgrading will fire `burn_rate_not_configured` until then — by design.

## Next Phase Readiness

- Phase 45 is fully closed: all six requirement rows Complete with concrete pointers, the
  plugin ships at a bumped, installable version, and the two numbers D-04 deliberately
  duplicated cannot drift unnoticed.
- Full suites at phase close: repo pytest 2481 passed / 121 skipped, plugin pytest 1326
  passed / 5 skipped, node 656 passed / 0 failed.
- No blockers. The alarm and the cadence floor both ship inert per the roadmap's own note
  — no cron/launchd is installed, and scheduling the sweep is an admin action outside this
  phase's and this milestone's scope.

---
*Phase: 45-burn-rate-alarm*
*Completed: 2026-08-10*

## Self-Check: PASSED

- FOUND: `.planning/phases/45-burn-rate-alarm/45-03-SUMMARY.md`
- FOUND: `a567764`, `e0f814b`, `0d4c8a4`
