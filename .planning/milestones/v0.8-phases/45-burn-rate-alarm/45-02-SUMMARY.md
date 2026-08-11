---
phase: 45-burn-rate-alarm
plan: 02
subsystem: infra
tags: [n8n, cadence, budget-floor, override, control-surface]

# Dependency graph
requires:
  - phase: 45-01
    provides: n8n_read.DAYS_PER_MONTH / n8n_read.HOURS_PER_MONTH — the one home for the
      30-day month this plan's TICKS_PER_MONTH table is derived from, so the alarm and
      the floor cannot disagree about the length of a month
provides:
  - n8n_cadence.TICKS_PER_MONTH / interval_month_cost / schedule_month_cost — whole-
    schedule monthly execution cost arithmetic, reusable by any future budget-aware gate
  - n8n_cadence.check_budget_floor — the refusal/override decision, called both from
    control_actions.plan_action (proposal time) and independently from set_cadence
    (mutation time)
  - n8n_cadence.BUDGET_FLOOR_OVERRIDE_PHRASE / budget_floor_override_taken — the single-
    shot conversational override primitive (D-10)
  - control_actions proposal keys budget_floor / budget_floor_override on the cadence
    action
affects: []

# Actuals (#2632)
actuals:
  tokens: 10017
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Whole-collection cost summation with one-node substitution: schedule_month_cost
      walks every schedule trigger in every workflow n8n_read.list_workflows returns,
      swapping the requested interval in for the one node being changed and using every
      other node's own committed interval — the shape any future 'what would the whole
      X cost if this one part changed' guard in this plugin should copy."
    - "Fail-closed on an unreadable or partially-uncomputable collection: None propagates
      through interval_month_cost -> schedule_month_cost -> check_budget_floor rather
      than being treated as zero, so an unreadable workflow list or a hand-edited
      cronExpression node can never make a schedule look cheaper than it is (T-45-08/09)."
    - "A gate re-checked independently at both the proposal layer (control_actions) and
      the mutation layer (n8n_cadence.set_cadence itself) — the proposal layer states the
      numbers before confirmation (D-10 point 1), the mutation layer closes the direct-
      caller bypass a proposal-only gate would leave open."
    - "Single-shot conversational override as a plain boolean parameter matched from one
      exact normalised phrase, never stored, never a config key, never a shared helper
      other gates could adopt — deliberately narrow per 45-CONTEXT.md D-10, and the
      narrowness is recorded in-line at the constant's own definition."

key-files:
  created:
    - operator-claude-plugin/tests/test_cadence_budget_floor.py
  modified:
    - operator-claude-plugin/scripts/n8n_cadence.py
    - operator-claude-plugin/scripts/control_actions.py
    - operator-claude-plugin/skills/backend-control/SKILL.md
    - operator-claude-plugin/USAGE.md
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_control_cadence.py
    - operator-claude-plugin/tests/test_control_surface.py

key-decisions:
  - "fake_config (conftest.py) gained n8n_monthly_execution_allowance=2500 and
    n8n_schedule_floor_max_share=1.0 (deliberately permissive, never the real 0.25) so
    pre-existing set_cadence/plan_action plumbing tests keep their original semantics —
    the floor's own strict-config refusal arithmetic lives entirely in
    test_cadence_budget_floor.py's dedicated STRICT_CONFIG/CONFIG dicts (advisor-
    reviewed before implementation)."
  - "schedule_month_cost fails closed (returns None) when the target workflow_id +
    node_name pair is not found anywhere in workflow_items, not just when the list itself
    is unreadable — a list that doesn't contain the workflow being edited is a list that
    could not really be read for this purpose (T-45-08), and this keeps 'unknown cost'
    the only interpretation of a mismatched or stale collection."
  - "A schedule trigger's disabled: true status is checked AFTER marking whether it is
    the target node (so a disabled target node still counts as found, avoiding a false
    unknown-cost refusal) but BEFORE its cost is added to the total (so it always
    contributes zero) — an ordering not spelled out in the plan text, decided here."

patterns-established:
  - "Task 1's TDD RED/GREEN pair for pure arithmetic (interval_month_cost,
    schedule_month_cost, check_budget_floor) versus Task 2's TDD RED/GREEN pair for the
    conversational override wired through control_actions — two independent test/impl
    cycles inside the same file, same shape as 45-01's per-task TDD commits."

requirements-completed: [FLOOR-01]

coverage:
  - id: D1
    description: "An over-budget cadence request is refused stating the requested job's
      own monthly cost, the whole-schedule cost, the ceiling and the allowance, in that
      order, before anything else (D-09)"
    requirement: "FLOOR-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_15_minute_request_over_the_ceiling_names_all_three_numbers"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_plan_action_refuses_over_budget_and_names_the_override_phrase"
        status: pass
    human_judgment: false
  - id: D2
    description: "The floor sums the WHOLE schedule, not just the trigger being changed —
      five individually-affordable triggers that sum past the ceiling are refused"
    requirement: "FLOOR-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_five_hourly_triggers_refused_even_though_no_single_one_exceeds_the_allowance"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_five_daily_triggers_then_target_swapped_to_hourly"
        status: pass
    human_judgment: false
  - id: D3
    description: "A disabled schedule trigger contributes zero to the summed cost, and an
      unreadable workflow list or an uncomputable node (cronExpression) refuses as
      unknown cost rather than being treated as free or skipped"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_disabled_trigger_contributes_zero"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_cron_expression_is_an_unknown_cost"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_unreadable_workflow_list_refuses_and_override_does_not_help"
        status: pass
    human_judgment: false
  - id: D4
    description: "A missing or unparseable allowance/share config key refuses naming the
      key and never the value, and this refusal (like the unreadable-list refusal) is
      NOT overridable even when override=True is passed"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_missing_allowance_key_names_it_and_never_the_value"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_missing_share_key_names_it"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_unreadable_workflow_list_refuses_and_override_does_not_help"
        status: pass
    human_judgment: false
  - id: D5
    description: "The single-shot override: the exact phrase (case/whitespace-normalised,
      never a substring match) lets exactly one over-budget change through, the
      consequence restates the arithmetic plus the baked per-tick dispatch cap staleness
      sentence, and the very next over-budget request with no phrase refuses again"
    requirement: "FLOOR-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_budget_floor_override_taken_matches_the_exact_normalised_phrase_only"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_the_single_shot_override_end_to_end_then_refuses_again"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_set_cadence_direct_call_refuses_even_after_a_prior_overridden_call"
        status: pass
    human_judgment: false
  - id: D6
    description: "TICKS_PER_MONTH is derived from n8n_read.DAYS_PER_MONTH /
      n8n_read.HOURS_PER_MONTH (not fresh literals), and an affordable request proceeds
      exactly as before this plan (proposal/confirmation/read-back unchanged for the
      permitted case)"
    verification:
      - kind: unit
        ref: "grep -c 'n8n_read.HOURS_PER_MONTH' and 'n8n_read.DAYS_PER_MONTH' in operator-claude-plugin/scripts/n8n_cadence.py, each >= 1"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cadence_budget_floor.py#test_daily_request_within_budget_returns_the_arithmetic_and_does_not_raise"
        status: pass
    human_judgment: false

# Metrics
duration: ~55min
completed: 2026-08-10
status: complete
---

# Phase 45 Plan 02: Runtime Cadence Budget Floor Summary

**A whole-schedule monthly-cost computation and refusal in `n8n_cadence`, wired into
`control_actions`' cadence proposal before the confirmation prompt, with a single-shot
conversational override that restates the arithmetic and never persists — closing the
front-door gap the 2026-08-10 USAGE.md fact-check found in the plugin's runtime cadence
action.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-08-10 (this session, after 45-01)
- **Completed:** 2026-08-10
- **Tasks:** 3
- **Files modified:** 6 modified, 1 created

## Accomplishments

- `n8n_cadence.TICKS_PER_MONTH` / `interval_month_cost` / `schedule_month_cost` — a
  whole-schedule monthly execution cost computation, derived entirely from
  `n8n_read.DAYS_PER_MONTH`/`HOURS_PER_MONTH` (45-01's shared constants), that sums every
  ENABLED schedule trigger across every workflow a tenant's `list_workflows` call
  returns, substituting the requested interval for the one node being changed
- `n8n_cadence.check_budget_floor` — refuses an over-budget cadence change naming the
  requested cost, the whole-schedule cost, the ceiling, and the allowance, in that order,
  before any mutation; a missing/unusable config key or an unreadable/uncomputable
  schedule refuses as unknown cost, and neither of those two refusals is overridable
- Wired into TWO independent points: `control_actions.plan_action`'s `cadence` branch
  (so the arithmetic reaches the operator at proposal time, before confirmation — D-10
  point 1) and `n8n_cadence.set_cadence` itself (so a direct caller that skips the
  proposal layer still gets the gate)
- `n8n_cadence.BUDGET_FLOOR_OVERRIDE_PHRASE` / `budget_floor_override_taken` — the
  single-shot override: an exact, normalised phrase (`"override the budget floor"`,
  never a substring match) that lets exactly one over-budget change through, with the
  consequence restating the arithmetic plus a sentence that the deployed build's
  per-tick dispatch cap was derived from the PREVIOUS cadence and does not move with a
  runtime-only edit — and the very next over-budget request with no phrase refuses again
- `USAGE.md` and `skills/backend-control/SKILL.md` corrected: the stale claim that
  nothing stands between a too-fast cadence and the budget is removed and replaced with
  what is now true, including the floor's boundary (it guards only the plugin's own
  cadence action — a trigger re-timed directly in the n8n editor is what 45-01's
  burn-rate alarm backstops instead) and an explicit instruction never to volunteer the
  override before the refusal has been shown

## Task Commits

1. **Task 1: Whole-schedule monthly cost, and a refusal that states the arithmetic** - `e7dde3d` (feat)
2. **Task 2: The single-shot override — arithmetic first, one change, no precedent** - `36b3be4` (feat)
3. **Task 3: Make the two documents that say this guard does not exist true again** - `14087d3` (docs)

**Plan metadata:** _(this commit)_

_Note: both Tasks 1 and 2 were `tdd="true"` — each began with a failing test (RED) made
to pass in the same commit (GREEN)._

## Files Created/Modified

- `operator-claude-plugin/scripts/n8n_cadence.py` — `TICKS_PER_MONTH`,
  `_BUDGET_SAFE_EXAMPLES`, `BUDGET_FLOOR_OVERRIDE_PHRASE`, `interval_month_cost`,
  `schedule_month_cost`, `_read_positive_float`, `_fetch_workflow_items`,
  `check_budget_floor`, `budget_floor_override_taken`; `set_cadence` gained a
  `budget_floor_override=False` keyword parameter and re-checks the floor before any
  mutation
- `operator-claude-plugin/scripts/control_actions.py` — `plan_action`'s `cadence` branch
  fetches the workflow list, checks the floor, and adds `budget_floor` /
  `budget_floor_override` proposal keys (appending the override consequence when
  applicable); `execute_action`'s `cadence` branch threads `budget_floor_override`
  through to `set_cadence`
- `operator-claude-plugin/tests/test_cadence_budget_floor.py` — new module: Task 1's
  arithmetic/refusal coverage and Task 2's override/single-shot coverage
- `operator-claude-plugin/USAGE.md` — the budget-note paragraph rewritten (stale
  "nothing else stands between..." sentence removed), the two config keys named, a new
  boundary sentence, and the admin decision-table row about wanting something faster
  than daily updated to point at the floor
- `operator-claude-plugin/skills/backend-control/SKILL.md` — the cadence section gained
  the budget-refusal shape, the `budget_floor_override_phrase` request field, and the
  never-volunteer-the-override-first instruction
- `operator-claude-plugin/tests/conftest.py`, `test_control_cadence.py`,
  `test_control_surface.py` — Rule 1 fallout (see Deviations)

## Decisions Made

- **`fake_config`'s budget-floor keys are deliberately permissive (share 1.0, not the
  real 0.25).** The mandatory floor check inside `set_cadence`/`plan_action` meant every
  pre-existing cadence plumbing test needed SOME allowance/share configured to avoid a
  blanket missing-key refusal; mirroring the real 0.25 share would have made those tests'
  own hourly-retiming scenarios over-budget by construction, changing what they prove.
  Consulted the advisor before implementing: a permissive fixture keeps the plumbing
  tests' original semantics intact and doubles as coverage of "an affordable request
  proceeds exactly as today," while the floor's own strict-refusal arithmetic lives
  entirely in this plan's dedicated `CONFIG`/`STRICT_CONFIG` dicts.
- **`schedule_month_cost` fails closed on a target node absent from `workflow_items`,**
  not just on an unreadable list — a collection that does not contain the workflow being
  edited cannot really answer "what would the whole schedule cost," so it is treated the
  same as unreadable (T-45-08). This was left to planning discretion by the plan text and
  decided here, following the advisor's recommendation.
- **Disabled-status check ordering:** a node is checked for target-identity BEFORE the
  disabled check (so a disabled target node still counts as "found" rather than
  triggering a false unknown-cost refusal) but the disabled check runs BEFORE its cost is
  summed (so it always contributes zero regardless of target status). Not spelled out in
  the plan text; decided here for internal consistency.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The mandatory floor check broke 3 pre-existing `test_control_cadence.py` plumbing tests**
- **Found during:** Task 1
- **Issue:** `set_cadence` now unconditionally fetches the workflow list and calls
  `check_budget_floor` before mutating. `fake_config` carried neither budget key, so
  every existing `set_cadence` call in `test_control_cadence.py` hit the
  missing-allowance refusal — and even after adding the keys, the new `list_workflows`
  GET consumed the first item of each test's 5-item scripted transport response list,
  meant for `apply_mutation`'s own workflow fetch.
- **Fix:** Added permissive `n8n_monthly_execution_allowance`/`n8n_schedule_floor_max_share`
  keys to `conftest.py`'s `fake_config` fixture, and prepended a scripted
  `list_workflows`-shaped response (`{"data": [...]}`, with the fixture's `id` set to
  match `WORKFLOW_ID`) to the 3 affected tests' transport sequences.
- **Files modified:** `operator-claude-plugin/tests/conftest.py`,
  `operator-claude-plugin/tests/test_control_cadence.py`
- **Verification:** `test_control_cadence.py` + full plugin suite green (1321 passed)
- **Committed in:** `e7dde3d` (Task 1 commit)

**2. [Rule 1 - Bug] `plan_action`'s new workflow-list fetch broke one `test_control_surface.py` cadence test**
- **Found during:** Task 2
- **Issue:** `plan_action`'s `cadence` branch now also fetches the workflow list for the
  floor check. `test_the_cadence_consequence_speaks_plainly_in_both_directions` scripted
  only one transport response (the workflow fetch), so the new `list_workflows` call
  consumed a default empty stub response, read as unreadable, and the proposal came back
  as a refusal instead of the expected before/after values.
- **Fix:** Added a `_workflow_items_response()` helper and appended it as a second
  scripted response in that one test.
- **Files modified:** `operator-claude-plugin/tests/test_control_surface.py`
- **Verification:** `test_control_surface.py` + full plugin suite green (1326 passed)
- **Committed in:** `36b3be4` (Task 2 commit)

**3. [Acceptance-criterion miss, documented rather than silently worked around] "Passes unchanged" could not hold literally**
- **Found during:** advisor consultation before Task 1 implementation
- **Issue:** Task 1 and Task 2's `<verify>`/`acceptance_criteria` both state that
  `test_control_cadence.py` (and, for Task 2, `test_control_surface.py`) must "pass
  unchanged." Given the plan's own binding requirement that the floor run unconditionally
  and independently in both `set_cadence` and `plan_action`, no implementation could
  satisfy that literal wording — every pre-existing test that reaches a successful
  cadence mutation necessarily needed a config value and an extra scripted transport
  response it did not have before. The must_haves truths (the binding contract) are
  fully satisfied; the "unchanged" phrasing in the acceptance criteria is what could not
  hold, and is recorded here rather than silently worked around.
- **Resolution:** Implemented per the must_haves truths and the advisor's explicit
  guidance (advisor-reviewed before implementation began, matching 45-01's precedent for
  the same class of situation). All listed tests pass GREEN after the two Rule 1 fixes
  above; only their fixture data changed, never their assertions' intent.

---

**Total deviations:** 2 auto-fixed (Rule 1 — pre-existing test-fixture assumptions
legitimately invalidated by this plan's own unconditional, independently-re-checked
floor), plus 1 documented acceptance-criterion miss (the literal "passes unchanged"
wording, superseded by the must_haves truths it was meant to serve).
**Impact on plan:** No scope creep — every fix was a direct, necessary consequence of
shipping FLOOR-01's own design (a floor checked at BOTH the proposal layer and the
direct-call layer, per the plan's own "a gate that lives only in the proposal layer is a
gate a direct caller walks around" instruction). No production behavior outside this
plan's stated scope was touched.

## Issues Encountered

None beyond the deviations above — all resolved inline within the owning task's commit,
with an advisor consultation before implementation began given the scale of the expected
fallout.

## User Setup Required

None — no external service configuration required. The floor is inert against the two
config keys 45-01 already added to `operator.local.example.json`
(`n8n_monthly_execution_allowance`, `n8n_schedule_floor_max_share`); an admin's real
`operator.local.json` needs no new key beyond what 45-01 documented.

## Next Phase Readiness

- FLOOR-01 fully closed: the front-door gap (runtime cadence changes reaching a live PUT
  with only a comprehension check standing in the way) is closed, and the back-door path
  (45-01's burn-rate alarm, watching actual execution rate) remains the backstop for a
  trigger re-timed directly in the n8n editor.
- Full plugin suite: 1326 passed / 5 skipped (baseline pre-45-02: 1309 passed / 5
  skipped — this plan adds 17 net new tests after Rule 1 fixture fixes). Repo suite: 2478
  passed / 121 skipped. Node: 656 passed, unchanged.
- No blockers.

---
*Phase: 45-burn-rate-alarm*
*Completed: 2026-08-10*

## Self-Check: PASSED

- FOUND: `.planning/phases/45-burn-rate-alarm/45-02-SUMMARY.md`
- FOUND: `e7dde3d`, `36b3be4`, `14087d3`
