---
phase: 29-notices-unattended-sweep
plan: 05
subsystem: infra
tags: [sweep, notices, conditions, attribution, read-only-guard, D-08a, D-08b, D-10, D-16, D-17, D-22]

requires:
  - phase: 29-03
    provides: sweep_read.gather / sweep_conditions.evaluate / sweep_notify.render / sweep_entry.run_sweep, the stuck condition, the import-graph read-only guard
  - phase: 27
    provides: backend_status.fetch_backend_status, error_table.translate, n8n_read (execution/workflow reads, read_write_safety), execution_errors.harvest_errors
  - phase: 28
    provides: status.WRITE_SAFETY_FLAGS and the arm/disarm crash window this plan's stuck-armed condition backstops (D-03)
provides:
  - "PREREQUISITE FIX: backend_status.fetch_backend_status unwraps the live array-wrapped hubspot/backend-status response — closes the long-standing open bug in HANDOFF.md §3"
  - Quota-exhausted and credential-failure conditions (four-way quota outcome, three-way credential outcome)
  - Failed-scheduled-run, review-backlog, and the maintenance workflow's swallowed-failure blind-spot detection (D-08b)
  - Stuck-armed backend condition covering both status.WRITE_SAFETY_FLAGS, including disagreement (D-16)
  - sweep_read.gather widened to fetch the workflow collection and the maintenance workflow's run data (gated per D-17)
  - Structurally-silent healthy path, grouped multi-condition delivery, full attribution (who_can_fix + is_interpretation + raw) on every notice
affects: [29-06]

actuals:
  tokens: 15200
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - "degrade-never-fire: every new condition treats an unreadable half of its input as a distinct outcome, never as zero/healthy/exhausted"
    - "single grouped delivery for simultaneous notices, most-actionable-first, capped with a stated remainder count"
    - "array-wrapped n8n webhook response unwrapped defensively before the dict-shape check, both shapes pinned by regression test"

key-files:
  created:
    - operator-claude-plugin/tests/test_sweep_conditions.py
    - operator-claude-plugin/tests/test_sweep_attribution.py
  modified:
    - operator-claude-plugin/scripts/backend_status.py
    - operator-claude-plugin/scripts/sweep_conditions.py
    - operator-claude-plugin/scripts/sweep_read.py
    - operator-claude-plugin/scripts/sweep_notify.py
    - operator-claude-plugin/scripts/sweep_entry.py
    - operator-claude-plugin/tests/test_status_tracer.py
    - operator-claude-plugin/tests/test_sweep_read_only.py

key-decisions:
  - "Fixed the array-wrapped backend-status bug FIRST, as its own commit, before any plan task — every one of this plan's five conditions reads through that path"
  - "classify_quota/classify_credential return explicit multi-way outcomes (not booleans) so unknown can never quietly become false"
  - "status.WRITE_SAFETY_FLAGS and the maintenance workflow's name are copied verbatim into sweep_conditions.py/sweep_read.py rather than imported, to avoid pulling status.py's requests.post default parameter into the sweep's single-POST-site closure"
  - "sweep_notify groups >1 fired condition into ONE delivery (most-actionable-first, capped, remainder counted) rather than one banner per condition"
  - "test_sweep_read_only.py's allowlist extended to execution_errors (error_table was already present) — read, confirmed pure, then added in one place with a note"

patterns-established:
  - "Every fired-condition dict carries a `reason` string; attribution is derived downstream via error_table.translate rather than hardcoded per condition"
  - "A degraded/unavailable read source contributes zero fired conditions rather than being asked to answer with default values"

requirements-completed: [NOTICE-03, NOTICE-04]

coverage:
  - id: D1
    description: "Prerequisite fix: fetch_backend_status unwraps the live array-wrapped backend-status response, pinned both ways (bare dict and single-element list)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_status_tracer.py#test_fetch_backend_status_accepts_the_bare_dict_shape"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_status_tracer.py#test_fetch_backend_status_unwraps_the_live_array_wrapped_shape"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_status_tracer.py#test_fetch_backend_status_rejects_shapes_that_are_neither"
        status: pass
    human_judgment: false
  - id: D2
    description: "Quota-exhausted and credential-failure conditions, across all four provider fixture states, both attributing to admin"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_sweep_conditions.py (quota/credential section, 9 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Failed-scheduled-run, review-backlog, and the maintenance workflow's swallowed-failure blind spot (D-08b), including the falsely-successful fixture end to end through the real gather wiring"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_sweep_conditions.py (Task 2 section, 8 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Stuck-armed backend condition covering both status.WRITE_SAFETY_FLAGS independently, plus disagreement firing rather than being swallowed as unknown (D-16)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_sweep_conditions.py (stuck-armed section, 6 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Structural silence when healthy, grouped delivery when several conditions fire, and full attribution (who_can_fix, is_interpretation, raw) on every notice, with D-15's cannot-run notices preserved"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_sweep_attribution.py (10 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Full plugin test suite and root repo test suite stay green after all changes"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests -q (882 passed, 5 skipped)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (1763 passed, 6 skipped)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (550 passed)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-03
status: complete
---

# Phase 29 Plan 05: Notices — full condition set, grouping, attribution Summary

**The sweep now answers all five D-08 conditions plus D-10's stuck-armed backstop, after fixing the array-wrapped backend-status response that made every one of them unreadable until today.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 4 (prerequisite fix + 3 plan tasks)
- **Files modified:** 9 (2 new test files, 7 modified — see `key-files`)

## Accomplishments

- **Closed the long-standing open bug from HANDOFF.md §3.** The live `hubspot/backend-status`
  webhook answers array-wrapped (a one-element list — n8n's normal `firstIncomingItem`
  behaviour). `fetch_backend_status` only accepted a bare dict, so every real answer came back
  `unrecognized_response_shape` and every queue count and provider balance read `unknown`
  through the plugin. Fixed by unwrapping a single-element list before the dict check, still
  rejecting an empty list, a multi-element list, or a non-dict element. Pinned both shapes
  (bare dict AND array-wrapped) with regression tests so a future n8n change in either
  direction is caught. The n8n side was not touched — other consumers of the webhook may rely
  on the wrapping.
- **Quota-exhausted and credential-failure** (new judgment over Phase 27's existing
  credit-probe data, D-08a): `classify_quota` returns a four-way outcome
  (`exhausted`/`ok`/`unknown`/`not_configured`) rather than a boolean, so an unreadable balance
  can never become an exhausted-quota notice, and a provider never probed at all (D-22's
  fourth state — absent from `balances`, present only in `credential_health`) is distinct from
  both. `classify_credential` reads the shape of the probe result (`state == "refused"`) rather
  than provider prose, and degrades `no_response` to unknown instead of firing as a broken
  credential.
- **Failed-scheduled-run, review-backlog, and the maintenance workflow's swallowed-failure
  blind spot** (D-08b): `sweep_read.gather` now fetches the maintenance workflow's most recent
  execution's run data (one gated extra GET, per D-17 — never for every execution in the
  page) and walks it with `execution_errors.harvest_errors`, so a run reporting `success` while
  one of its own `onError: continueRegularOutput` search nodes actually failed is caught rather
  than treated as evidence of health.
- **Stuck-armed backend** (D-10, the backstop for Phase 28 D-03's arm/disarm crash window):
  checks both of `status.WRITE_SAFETY_FLAGS` (copied verbatim, not imported — importing
  `status.py` would have pulled a second write-verb site into the sweep's single-POST-site
  closure) and fires on either "armed with nothing dispatching" or a truthy `disagreement`
  (D-16) — a partially-armed workflow is exactly the residue this backstop exists to catch.
- **Silence, grouping, attribution:** a fully healthy backend still produces `[]`; more than
  one fired condition now groups into ONE delivery (most-actionable-first, capped, remainder
  counted) instead of one banner per condition; every notice carries the full `error_table`
  verdict (`who_can_fix`, `is_interpretation`, `raw`), not just the attribution, so an
  unrecognised cause is visibly labelled an interpretation rather than passed off as fact.
  29-03's D-15 cannot-run notices (missing capability, fully blind gather) are unchanged and
  never pass through the grouping path.

## Task Commits

Each task was committed atomically:

0. **Prerequisite: unwrap the array-wrapped backend-status response** - `3c09283` (fix)
1. **Task 1: quota-exhausted and credential-failure conditions** - `7a4219d` (feat)
2. **Task 2: failed-run, review-backlog, swallowed-failure, stuck-armed** - `c10efff` (feat)
3. **Task 3: silence, grouping, full attribution** - absorbed into `dfd1178` (see Deviations — a
   concurrent process committed it as part of its own commit; content verified identical to
   what was authored and tested in this task)

## Files Created/Modified

- `operator-claude-plugin/scripts/backend_status.py` - unwraps a single-element array before the dict-shape check (prerequisite fix)
- `operator-claude-plugin/scripts/sweep_conditions.py` - quota/credential/failed-run/review-backlog/swallowed-failure/stuck-armed conditions
- `operator-claude-plugin/scripts/sweep_read.py` - gather widened: workflow collection + gated maintenance-execution run-data fetch
- `operator-claude-plugin/scripts/sweep_notify.py` - grouping, full attribution verdict on every notice
- `operator-claude-plugin/scripts/sweep_entry.py` - docstring only; D-15 branches unchanged and confirmed to bypass grouping
- `operator-claude-plugin/tests/test_status_tracer.py` - three new regression tests pinning both backend-status response shapes
- `operator-claude-plugin/tests/test_sweep_read_only.py` - allowlist extended to `execution_errors`
- `operator-claude-plugin/tests/test_sweep_conditions.py` - new file, 22 tests across Tasks 1-2
- `operator-claude-plugin/tests/test_sweep_attribution.py` - new file, 10 tests for Task 3

## Decisions Made

- The array-wrap fix was done first, as its own commit, before any plan task — confirmed by
  re-reading `backend_status.py` that every one of this plan's conditions reads through
  `fetch_backend_status`, so the plan could not be meaningfully satisfied without it.
- `classify_quota`/`classify_credential` return explicit string/boolean-or-None outcomes
  rather than a boolean-plus-convention, per the plan's explicit instruction — this is what
  makes "unknown can never become false" checkable by a test rather than an implied contract.
- `status.WRITE_SAFETY_FLAGS` and the maintenance workflow's name are copied verbatim into
  `sweep_conditions.py`/`sweep_read.py` instead of imported from `status.py`/
  `verify_live_no_native_search.py` — both of those modules are outside the sweep's closure
  (one supplies `requests.post` as a default parameter, the other is backend-side per
  PLUGIN-04), and importing either would widen the read-only guard's single-POST-site
  exception for no reason.
- `sweep_read.gather`'s workflow-collection fetch relies on n8n's collection response already
  carrying full node bodies in this tenant (the same shortcut `status.describe_all` takes) —
  no per-workflow GET was added, keeping the sweep's added cost to exactly one extra GET
  (the gated maintenance-execution fetch).

## Deviations from Plan

### Auto-fixed Issues

**1. [Prerequisite, explicitly directed] Array-wrapped backend-status response unwrap**
- **Found during:** Task 0 (explicitly required by the plan before any other task)
- **Issue:** `fetch_backend_status` rejected the live endpoint's array-wrapped answer as `unrecognized_response_shape`
- **Fix:** Unwrap a single-element list to its element before the dict check; still reject empty/multi-element/non-dict shapes
- **Files modified:** `operator-claude-plugin/scripts/backend_status.py`, `operator-claude-plugin/tests/test_status_tracer.py`
- **Verification:** Three new regression tests, both shapes pinned
- **Committed in:** `3c09283`

### Process Deviation (not a code issue)

**2. Task 3's commit was absorbed into a concurrent commit not authored by this executor.**
- **What happened:** After staging Task 3's three files (`sweep_entry.py`, `sweep_notify.py`,
  `tests/test_sweep_attribution.py`) and running `git commit`, git reported "nothing to
  commit, working tree clean" — the staged changes had already been folded into a commit made
  by a different, concurrently-running process in the same (non-worktree-isolated) working
  tree: `dfd1178 docs(RB-8): the prescribed notice lever cannot fire — amend it before the
  gate runs`, whose own message says "no code touched" but whose diffstat shows exactly the
  three files this task staged.
- **Verification performed:** `git show dfd1178:operator-claude-plugin/scripts/sweep_notify.py`
  diffed byte-for-byte identical against the working-tree file authored and tested in this
  session — the content is correct and complete, only the commit boundary/attribution is not
  what this task intended.
- **No corrective action taken:** rewriting or amending someone else's commit is a destructive
  operation on shared history and was avoided per the standing git-safety rules. The working
  tree is clean and every test (plugin suite, root suite, Node suite) is green at `HEAD`.
- **Impact:** None on functionality or test coverage. The per-task atomic-commit convention was
  not honored for Task 3 specifically, due to a concurrent process sharing this working tree
  without worktree isolation — worth flagging to whoever coordinates parallel executors for
  this workstream.

---

**Total deviations:** 1 auto-fixed (prerequisite, explicitly directed by the plan), 1 process
deviation (commit-boundary only, no content impact).
**Impact on plan:** None on scope or correctness — all `<verify>` and acceptance criteria pass.

## Issues Encountered

None beyond the commit-boundary deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All five D-08 conditions plus D-10's stuck-armed backstop are implemented and tested; the
  full condition set 29-06 will wire into the skill/cron template is complete.
- `sweep_read.gather`'s widened shape (`workflows`, `maintenance_errors` keys) is stable for
  29-06 to build against.
- The array-wrap fix means 29-06's live gate (D-12) can now exercise the review-backlog and
  quota/credential conditions against genuine backend data rather than a permanently-404'd
  endpoint.

---
*Phase: 29-notices-unattended-sweep*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 9 key files found on disk; all 4 commit hashes (`3c09283`, `7a4219d`, `c10efff`,
`dfd1178`) found in git history.
