---
phase: 59-frictionless-write-path
plan: 02
subsystem: testing
tags: [pytest, conftest, credential-safety, RUN_LIVE_PARITY]

requires: []
provides:
  - "Root tests/conftest.py autouse fixture stripping ANTHROPIC_API_KEY / HUBSPOT_PRIVATE_APP_TOKEN from every test under tests/ by construction"
  - "Proven opt-in branch (RUN_LIVE_PARITY=true) that leaves credentials intact for the two existing live tests"
affects: [tests/, src/web_research.py, src/classifier_haiku.py, src/validator_sonnet.py]

actuals:
  tokens: 2088
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Autouse pytest fixture gated on an existing env-var convention (RUN_LIVE_PARITY), not a pytest marker — mirrors operator-claude-plugin/tests/conftest.py's no_network idiom"
    - "Subprocess-driven fixture probe (leading-underscore module, not test_*.py) to prove a branch an autouse fixture has already decided before any in-process test body runs"

key-files:
  created:
    - tests/conftest.py
    - tests/_credential_guard_probe.py
    - tests/test_conftest_credential_guard.py
  modified: []

key-decisions:
  - "D-59-04 implemented as a deliberate deviation from CONTEXT.md's literal wording: gate on os.getenv(\"RUN_LIVE_PARITY\") == \"true\" (the repo's only real live-test convention) rather than a pytest marker named `live`, because no such marker is registered anywhere in this repo and a marker lookup would silently never match"
  - "The deviation and its full reasoning are written into tests/conftest.py's own module docstring, not only into this SUMMARY, so a future reader does not \"fix\" it back to a marker lookup"
  - "RUN_LIVE_PARITY=true regression check against the two existing live tests is DEFERRED to a deliberate live run (costs real HubSpot/Anthropic calls); collect-only was used instead to prove both files still collect cleanly under the new root conftest"

patterns-established:
  - "Fixture-branch proofs that an autouse fixture has already decided (before any test body) must run as a subprocess, not an in-process assertion"

requirements-completed: [D-59-04]

coverage:
  - id: D1
    description: "Credentials absent from os.environ in every root-suite test, by construction (default branch)"
    requirement: "D-59-04"
    verification:
      - kind: unit
        ref: "tests/test_conftest_credential_guard.py#test_credentials_absent_by_default_in_process"
        status: pass
      - kind: integration
        ref: "tests/test_conftest_credential_guard.py#test_credentials_absent_by_default_via_subprocess"
        status: pass
    human_judgment: false
  - id: D2
    description: "Credentials present when RUN_LIVE_PARITY=true (opt-in branch), proven by subprocess since an in-process assertion cannot observe a decision an autouse fixture already made"
    requirement: "D-59-04"
    verification:
      - kind: integration
        ref: "tests/test_conftest_credential_guard.py#test_credentials_present_when_opted_in_via_subprocess"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full root suite green with the new autouse fixture in place; the two live-gated files still collect cleanly without the opt-in; the plugin suite (its own conftest.py) is unaffected by the new root conftest"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/ -q"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_scoring_parity.py tests/test_review_flag_eq_filter.py --collect-only -q"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests -q"
        status: pass
    human_judgment: false
  - id: D4
    description: "Live-service regression run of the two existing live tests under RUN_LIVE_PARITY=true — DEFERRED, not performed this plan (costs real HubSpot/Anthropic calls, run deliberately per 59-VALIDATION.md, never per-commit)"
    verification: []
    human_judgment: true
    rationale: "Running the live suite spends real HubSpot writes and Anthropic calls; 59-VALIDATION.md's Sampling Rate explicitly scopes live tests to a deliberate, separately-run check, not this plan's automated verification. Collect-only was used instead to prove the mechanism (both files still parse and collect cleanly under the new conftest); the actual live pass/fail is left for a deliberate operator-run session."

duration: 12min
completed: 2026-08-28
status: complete
---

# Phase 59 Plan 02: Ambient-credential test guard Summary

**Root `tests/conftest.py` autouse fixture strips `ANTHROPIC_API_KEY`/`HUBSPOT_PRIVATE_APP_TOKEN` from every test by default, gated on `RUN_LIVE_PARITY` (not a nonexistent pytest marker), with both branches proven — the default strip in-process, the opt-in preserve via subprocess.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-28T13:16:57Z
- **Completed:** 2026-08-28T13:29:00Z
- **Tasks:** 2
- **Files modified:** 3 (all new)

## Accomplishments
- `tests/conftest.py` — the repo's first root-level conftest — added with an autouse `no_ambient_credentials` fixture, a `GUARDED_CREDENTIAL_VARS` constant, and a `live_run_opted_in()` predicate the probe module imports rather than restating.
- The `RUN_LIVE_PARITY`-vs-marker deviation from CONTEXT.md's literal D-59-04 wording is recorded in the conftest's own module docstring (names commit `89c9871` and D-59-04), not just in this SUMMARY.
- Both fixture branches proven by automated commands: the default strip in-process (subject to the fixture itself) and via subprocess; the opt-in preserve via subprocess only, since an autouse fixture has already decided before any in-process test body runs.
- Full root suite (1607 passed, 149 skipped) confirmed green with the new fixture in place; both existing live-gated files (`test_scoring_parity.py`, `test_review_flag_eq_filter.py`) still collect cleanly (89 tests collected, 0 errors) without the opt-in; plugin suite (1654 passed, 5 skipped) confirmed unaffected by the new root conftest.

## Task Commits

Each task was committed atomically:

1. **Task 1: The root credential guard, and a probe that proves both of its branches** - `effd336` (test)
2. **Task 2: Prove the guard broke nothing — full root suite, and the two live-gated files collect clean** - no commit (verification-only task; no files changed)

_Note: Task 2 is a verification task per the plan — it runs the full suites and records the deferred live check, but makes no code changes, so there is nothing to commit beyond the plan-metadata commit._

## Files Created/Modified
- `tests/conftest.py` - New root conftest: `GUARDED_CREDENTIAL_VARS`, `live_run_opted_in()`, `no_ambient_credentials` autouse fixture; docstring records the D-59-04 deviation and its rationale
- `tests/_credential_guard_probe.py` - Fixture probe, deliberately not `test_*.py` so it is excluded from default collection; asserts both branches of `no_ambient_credentials` when driven as its own pytest process
- `tests/test_conftest_credential_guard.py` - Real test file: one in-process default-branch test, two subprocess tests (default and opt-in) driving the probe module

## Decisions Made
- **D-59-04 implemented as a deliberate, recorded deviation from CONTEXT.md's letter.** CONTEXT.md's D-59-04 says the fixture strips credentials "unless a test is `@live`-marked." No pytest marker named `live` is registered anywhere in this repo — no `pytest.ini`/`pyproject.toml`/`setup.cfg` `[pytest]` block exists at all — and the only "live" concept is a locally-defined `pytest.mark.skipif(os.getenv("RUN_LIVE_PARITY") != "true", ...)` object in two files, whose applied mark name is `skipif`, not `live`. A marker lookup would silently never match. Research also proved live that pytest runs autouse fixtures for a test whose skipif evaluates to "do not skip" — so an unconditional strip would break both existing live tests the moment `RUN_LIVE_PARITY=true` is used. The fixture therefore gates on the identical `RUN_LIVE_PARITY` condition those two files already use. This reasoning is written into the conftest's own docstring per the plan's phase-critical constraint.
- **The opt-in branch is proven exclusively by subprocess**, per the plan's constraint: an autouse fixture has already decided by the time any in-process test body runs, so no in-process assertion could observe the opt-in branch.
- **The live regression check is explicitly deferred, not run.** `RUN_LIVE_PARITY=true` costs real HubSpot writes and Anthropic calls; per 59-VALIDATION.md's Sampling Rate, live tests run deliberately, never per-commit. `--collect-only` was used instead to prove both live-gated files still parse and collect cleanly under the new root conftest.

## Deviations from Plan

None beyond the CONTEXT.md-letter deviation the plan itself pre-recorded and mandated (see `<planner_assumptions>` in 59-02-PLAN.md and the "Decisions Made" section above) — no unplanned auto-fixes were needed.

## Issues Encountered
- The initial conftest docstring quoted the literal string `get_closest_marker("live")` as an example of what the fixture must NOT do, which tripped the plan's own acceptance criterion (`grep -c "get_closest_marker" tests/conftest.py` must be 0). Reworded to describe the same idea ("a fixture that looked up a marker named 'live' on the test node") without using the literal API name. Re-verified: grep count is 0, all tests still pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- D-59-04 is fully implemented and verified; the ambient-credential guard applies to every test under `tests/` by construction.
- The deferred live regression check (`RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py tests/test_review_flag_eq_filter.py`) remains outstanding for a deliberate, separately-scheduled live run — not a blocker for this plan or subsequent 59-0x plans, since the mechanism (collection, fixture wiring) is proven and the opt-in branch is proven by subprocess at zero API cost.
- No blockers for other Phase 59 plans (D-59-06/D-59-07/D-59-08), which are independent of this conftest addition.

---
*Phase: 59-frictionless-write-path*
*Completed: 2026-08-28*
