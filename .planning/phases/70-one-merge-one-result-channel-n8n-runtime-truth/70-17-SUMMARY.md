---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 17
subsystem: n8n-deploy-and-control
tags: [n8n, executionOrder, settings-preservation, bounce, proof-driver, D-70-29, D-70-31, G-70-6]

# Dependency graph
requires:
  - phase: 70 (plan 16)
    provides: settings.executionOrder = v1 on all eight generated n8n workflow bodies (WORKFLOW_SETTINGS, assert_execution_order_v1)
provides:
  - "offline value-level proof that both live-write paths (deploy PUT/POST and the plugin's arming PUT) cannot lose or revert the v1 execution order"
  - "a bounce read-back that reports the live execution order per workflow and exits non-zero on any non-v1 reading"
  - "a proof-driver verdict field (execution_order_all_v1) that fails the D-70-19/Gate 11 verdict on a non-v1 or null live reading, distinct from shapes_equal"
affects: ["70-18"]

actuals:
  tokens: 5272
  tasks: 3
  commits: 3
  plan_head_before: c4ac44c

tech-stack:
  added: []
  patterns:
    - "Value-level round-trip tests alongside the pre-existing key-set tests, both for a payload filter and for a per-transform pipeline — a key-set assertion alone cannot catch a transform that swaps in a different value for a key it never drops."
    - "Row-verdict predicate extracted to module level (_row_ok) so an operator-facing script with no test coverage before this plan gets offline coverage without touching its HTTP path."
    - "A verdict field that folds into the pass/fail signal (answer) while a sibling field (shapes_equal) keeps its narrower, pre-existing meaning — lets a future run distinguish two different kinds of failure from one printed line."

key-files:
  created:
    - tests/test_bounce_n8n_workflows.py
  modified:
    - tests/test_deploy_n8n_workflows.py
    - operator-claude-plugin/tests/test_control_allowlist_diff.py
    - scripts/bounce_n8n_workflows.py
    - scripts/prove_phase70_runtime.py
    - tests/test_prove_phase70_runtime.py

key-decisions:
  - "All four Task 1 pins (update PUT payload, create POST payload, three-transform pipeline, put_body value round-trip) were ALREADY TRUE in the existing code — no production defect was found in either PUT path. Every new test in Task 1 passed on the first run against unmodified scripts/deploy_n8n_workflows.py and operator-claude-plugin/scripts/n8n_control.py. `git status --porcelain -- scripts/` was empty after Task 1, confirming zero production-code changes, as required."
  - "test_changed_settings_are_refused (pre-existing) already covered a v1->v0 VALUE change against a v1 original. Task 1(d) added a second, distinct case for the 'key dropped entirely' shape (settings = {}) rather than treating the existing test as sufficient, per the plan's explicit instruction to name a legacy-shaped object against a v1 original."
  - "D-70-31's verdict shipped as execution_order_all_v1 (the exact spelling plan 70-18 is told to expect). It is derived strictly from live_execution_order: null (predict-only) | false (empty mapping, any null value, or any non-v1 value) | true (non-empty mapping, every value 'v1'). answer now requires shapes_ok AND execution_order_all_v1; shapes_equal's own meaning (shape agreement alone) is untouched — proved by a case where shapes_equal stays True while answer goes False on a null order reading."
  - "main()'s exit condition moved from `verdict[\"shapes_equal\"] is not True` to `verdict[\"answer\"] is not True`, with the branch message distinguishing a shape disagreement from a non-v1 order so an operator reading stderr does not conclude the walker was wrong when the instance was simply off v1. This was a real, if narrow, defect in the pre-existing driver: before this change a disarmed proof run against a legacy-order instance whose row shapes happened to agree would have printed nothing alarming and exited 0."
  - "The superseded D-70-02 comment beside the per-workflow execution_order read now cites D-70-28/D-70-31 and states a null reading is a gate failure, per the plan's instruction."

requirements-completed: [D-70-29]

coverage:
  - id: D1
    description: "Both live-write paths (deploy PUT/POST payload, the three transforms upstream of it, and the plugin's put_body/arming refusal) are pinned value-level to preserve settings.executionOrder = v1 — offline"
    requirement: "D-70-29"
    verification:
      - kind: unit
        ref: "tests/test_deploy_n8n_workflows.py#test_update_put_payload_carries_settings_value_intact"
        status: pass
      - kind: unit
        ref: "tests/test_deploy_n8n_workflows.py#test_create_post_payload_carries_settings_value_intact"
        status: pass
      - kind: unit
        ref: "tests/test_deploy_n8n_workflows.py#test_settings_survive_rebind_bind_and_baked_flag_transforms"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_allowlist_diff.py#test_put_body_value_level_round_trip_preserves_settings_object"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_allowlist_diff.py#test_reverting_settings_to_legacy_shape_is_refused_naming_settings_key"
        status: pass
    human_judgment: false
  - id: D2
    description: "The bounce read-back reports each live workflow's execution order in the printed table and exits non-zero if any workflow reads non-v1, via a module-level _row_ok predicate proved offline"
    requirement: "D-70-29"
    verification:
      - kind: unit
        ref: "tests/test_bounce_n8n_workflows.py (9 cases: _row_ok x7, _flag_values x2)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The proof driver's verdict answers false when any live workflow's execution order reads non-v1 or null, distinguishable from a shape disagreement, and exit code follows answer not shapes_equal alone"
    requirement: "D-70-29"
    verification:
      - kind: unit
        ref: "tests/test_prove_phase70_runtime.py (6 new build_verdict/exit-code cases)"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 17: Settings-Preservation Pins + Execution-Order Reporting Summary

**Value-level proof that neither the deploy PUT/POST nor the plugin's arming rewrite can silently drop the v1 execution order, plus a bounce table and a proof-driver verdict field that both fail loudly on a live legacy-order reading — offline throughout, zero production defects found.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-10T (see git log c4ac44c..7550cbc)
- **Completed:** 2026-09-10
- **Tasks:** 3
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments
- Pinned, value-level, that a deploy `PUT`/`POST` cannot lose `settings.executionOrder`, and that the three transforms between the committed file and the payload (`rebind_subworkflow_refs` → `bind_credentials` → `enable_baked_flags`) preserve it too — none of this was tested before this plan; all four assertions passed against the existing code unmodified.
- Pinned the plugin's `put_body` value-level round-trip and added a "legacy shape (key dropped)" refusal case beside the existing "changed value" refusal case, so an arming/disarming rewrite cannot revert a workflow's execution order by either mechanism.
- Extracted `_row_ok(live_body, expected_nodes)` in `scripts/bounce_n8n_workflows.py` — the sole row-verdict computation, now testable offline — and added an execution-order column to the bounce script's printed table and failure summary.
- Added `execution_order_all_v1` to `scripts/prove_phase70_runtime.py::build_verdict`, folded it into `answer` (keeping `shapes_equal`'s meaning untouched), and moved the driver's exit condition from `shapes_equal` to `answer` so a legacy-order instance with agreeing row shapes can no longer exit 0.

## Task Commits

Each task was committed atomically:

1. **Task 1: pin that a PUT cannot lose or revert the v1 execution order, on both PUT paths** - `4c98669` (test)
2. **Task 2: the bounce read-back reports the execution order and fails on anything but v1** - `0e8416d` (feat)
3. **Task 3: the proof driver's verdict answers false when the live instance is not on v1** - `7550cbc` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `tests/test_deploy_n8n_workflows.py` - added value-level settings pins for `_update_workflow_live`, `_create_workflow_live`, and the three-transform pipeline
- `operator-claude-plugin/tests/test_control_allowlist_diff.py` - added `put_body` value-round-trip test and the legacy-shape settings refusal test
- `scripts/bounce_n8n_workflows.py` - extracted `_row_ok`, added an execution-order column, updated module docstring
- `tests/test_bounce_n8n_workflows.py` - new, 9 offline cases for `_row_ok` and `_flag_values`
- `scripts/prove_phase70_runtime.py` - added `execution_order_all_v1`, folded it into `answer`, moved the exit condition, updated the superseded D-70-02 comment
- `tests/test_prove_phase70_runtime.py` - added 6 direct `build_verdict`/exit-code cases

## Decisions Made

- **All four Task 1 pins were already true** — see key-decisions above. No production code changed in Task 1 (`git status --porcelain -- scripts/` was empty, as required by the plan's own acceptance criterion).
- **`execution_order_all_v1` shipped as spelled in the plan** — `execution_order_all_v1` — because plan 70-18 reads this exact field name from this SUMMARY.
- **`main()`'s exit condition was a real defect fixed by this plan**, not merely a new pin on existing behavior: before this change, a disarmed proof run against a legacy-order live instance whose row shapes happened to agree would have exited 0. This is documented as the one operational consequence Task 3 corrects, distinct from the "already true" pins in Task 1.

## Deviations from Plan

None - plan executed exactly as written. Task 1 confirmed rather than fixed both PUT paths (the plan explicitly allowed for either outcome: "If any of (a)-(d) fails, that is a real defect... surface it in the SUMMARY rather than adjusting the test to pass" — none failed). Task 3's exit-condition change is exactly the behavior the plan's `<action>` prescribed, not an unplanned fix.

## Issues Encountered

None. All `<verify>` commands in the plan passed on first run for Tasks 2 and 3; Task 1 required no iteration since every new test passed against unmodified production code.

## User Setup Required

None - no external service configuration required. Nothing was deployed, bounced, armed, or sent — all six changed files are test-only or offline-tested production code (the bounce script's and proof driver's HTTP paths are unchanged in behavior when credentials are present; only the offline predicate/verdict logic changed).

## Next Phase Readiness

- Ready for 70-18: the verdict field `execution_order_all_v1` is shipped and named exactly as plan 70-18 expects, for Gate 11's pass criteria.
- No blockers. The full python suite (4721 passed, 154 skipped), the operator-claude-plugin suite (2866 passed, 5 skipped), and the full n8n mjs suite (1078 passed) all ran green after this plan's changes.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED
