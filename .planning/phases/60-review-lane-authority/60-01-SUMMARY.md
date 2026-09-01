---
phase: 60-review-lane-authority
plan: 01
subsystem: auth
tags: [python, pytest, hubspot, n8n, write-grant, review-decision, authorization]

requires:
  - phase: 53-operator-openable-write-grant
    provides: the write_grant module (plan_grant/open_grant/covers/authorize_send) and the n8n_arming arm/dispatch/disarm lifecycle this plan extends to a third lane
  - phase: 30-review-decision-writeback
    provides: review_decision.py's three-gate design (env kill switch, session arm, backend allowlist) this plan retires gate 1 of

provides:
  - "review" as a third grantable lane in write_grant.LANES, resolved by name to "LV Review Decision (Cloud)"
  - n8n_arming.arm_for_review / armed_review_window, sharing arm_for_dispatch's body via a new authority= keyword
  - review_decision.submit_decision gated by write_grant.authorize_send(lane="review") instead of the retired ALLOW_REVIEW_SUBMIT env variable
  - n8n_arming.disarm deriving its mutation targets AND node allowlist from whatever the fetched workflow actually declares, with a fail-closed DISARM_FAILED verdict when the pre-read is unreadable
affects: [60-02-preflight-guardrails, 60-03-written-records, 60-04-skill-docs]

actuals:
  tokens: 17166
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "authority=" keyword-only parameter selecting a flag set (AUTHORITY_DISPATCH/AUTHORITY_REVIEW) shared by one arm/disarm implementation, rather than a second parallel function
    - "derive-from-declared" disarm — mutation targets and the allowed-node list computed from the SAME read of what the workflow actually declares, never a fixed default list
    - dated recorded-edit amendment blocks appended beside a reversed design decision's original comment, never deleting or rewriting the historical record

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/n8n_arming.py
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_review_decision.py
    - operator-claude-plugin/tests/test_control_arming.py

key-decisions:
  - "D-60-01/D-60-02: review is now a third grantable lane; one grant can span enrichment, contacts and review together"
  - "D-60-03: write_grant.covers is the single scope check for review decisions too — no second scope implementation"
  - "D-60-04: submit_decision's gate 1 is grant-authorization (write_grant.authorize_send), replacing the ALLOW_REVIEW_SUBMIT env kill switch"
  - "D-60-05: arm_for_review sets ONLY ALLOW_HUBSPOT_REVIEW_WRITES (+ allowlist), never ALLOW_HUBSPOT_RECORD_WRITES/ALLOW_HUBSPOT_CREATE — pinned by a Python test on the recorded PUT body and by the unmodified reviewWriteFlagSeparation.test.mjs"
  - "D-60-07: a reject still proceeds with no grant open (the is_undoing carve-out survives, re-pointed at the grant check); its docstring records that this guarantees submission, never landing (cross-AI review MEDIUM-3)"
  - "Cross-AI review MEDIUM-2/LOW-5 (folded into this task at build time): disarm's node allowlist and mutation targets are both derived from what the workflow actually declares, and an unreadable pre-read returns DISARM_FAILED immediately instead of falling back to a guessed flag list"

requirements-completed: [D-60-01, D-60-02, D-60-03, D-60-04, D-60-05, D-60-07]

coverage:
  - id: D1
    description: "review is a grantable lane end-to-end — a planned-and-opened grant arms the review workflow, gates submit_decision, bounds it to the grant's records, and disarms, with no shell environment variable read anywhere"
    requirement: D-60-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py#test_a_review_decision_arms_and_authorizes_under_an_opened_review_grant"
        status: pass
    human_judgment: false
  - id: D2
    description: "arming review never sets ALLOW_HUBSPOT_RECORD_WRITES/ALLOW_HUBSPOT_CREATE, asserted against the recorded PUT body"
    requirement: D-60-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py#test_the_review_arm_never_sets_dispatch_write_flags_in_the_recorded_put_body"
        status: pass
      - kind: unit
        ref: "tests/n8n/reviewWriteFlagSeparation.test.mjs"
        status: pass
    human_judgment: false
  - id: D3
    description: "a review decision cannot exceed the grant's record scope; a grant over one record refuses a decision on another and names it"
    requirement: D-60-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py#test_a_review_grant_over_record_a_refuses_a_decision_on_record_b"
        status: pass
    human_judgment: false
  - id: D4
    description: "submit_decision reads no shell environment variable; a reject still proceeds with no grant while an approve refuses"
    requirement: D-60-04
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py#test_submit_decision_with_no_grant_refuses_and_makes_no_call"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py#test_a_reject_proceeds_with_no_grant_but_still_needs_the_session_arm"
        status: pass
    human_judgment: false
  - id: D5
    description: "disarm derives its targets and node allowlist from the same declared-flag list, and refuses loudly rather than guessing when the pre-read is unreadable"
    requirement: D-60-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_arming.py#test_disarm_rewrites_a_node_declaring_only_the_review_constant"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_arming.py#test_disarm_refuses_before_mutating_when_the_pre_read_is_unreadable"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-09-01
status: complete
---

# Phase 60 Plan 01: Review-lane authority tracer Summary

**"review" is now a real grantable lane end to end — one Python arm implementation shared by dispatch and review via an `authority=` keyword, `submit_decision` gated by `write_grant.authorize_send` instead of the retired `ALLOW_REVIEW_SUBMIT` shell variable, and `disarm` rebuilt to derive what it rewrites from what a workflow actually declares.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-09-01T06:52:59Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Reversed Phase 30-01's D-02/D-08e separation: `write_grant.LANES` now has a `"review"` entry resolving to `"LV Review Decision (Cloud)"`, with the original exclusion comment left intact and a dated `D-60-01/D-60-05` amendment appended beside it
- `n8n_arming.arm_for_dispatch`/`armed_window` gained a keyword-only `authority=` parameter (`AUTHORITY_DISPATCH` default, `AUTHORITY_REVIEW`) selecting which flag set (`DISPATCH_FLAGS` vs the new `REVIEW_FLAGS`) an arm targets; `arm_for_review`/`armed_review_window` delegate to the same bodies rather than duplicating them
- `n8n_arming.disarm` rebuilt: its mutation targets and its allowed-node list are now BOTH derived from `n8n_read.read_write_safety` over `OVERLAYABLE_FLAGS` against the freshly-read workflow, closing two gaps the cross-AI review flagged mid-plan (MEDIUM-2: a node declaring only the review constant would previously fall outside a `DISPATCH_FLAGS`-derived allowlist and be refused; LOW-5: an unreadable pre-read now returns `DISARM_FAILED` immediately instead of verifying over a guessed flag list)
- `review_decision.submit_decision` retired `ALLOW_REVIEW_SUBMIT`/`submit_enabled()`/`_ENV_REFUSAL` entirely; gate 1 is now `write_grant.authorize_send(grant, lane=write_grant.REVIEW_LANE, ...)`, checked before `is_undoing`'s carve-out — a `reject` still proceeds with no grant open (D-60-07), documented as guaranteeing submission only, never landing (the deployed gate checks its allowlist before the decision word)
- Rewrote the two `test_write_grant.py` tests that pinned the old exclusion (repointed the unknown-lane refusal at a genuinely unknown name; inverted the not-grantable assertion into a grantable-with-flag-separation-intact one) and added the full tracer walk (plan → open → arm → decision → disarm) plus the scope/no-grant/reject gate tests
- Rewrote all of `test_review_decision.py`'s gate-1 section onto grant fixtures (open/closed/wrong-lane/malformed-shape/empty-dict/wrong-kind/different-record — 7 near-miss cases, matching the pre-rewrite collected test count of 49 exactly) and added the MEDIUM-2/LOW-5 disarm-derivation tests to `test_control_arming.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "a grant approves one flagged record" — one path only** - `8a9dac0` (feat)
2. **Task 2: Rewrite the review-decision suite onto the grant gate** - `7cc5780` (test), widened in `4cb68e2` (test) after the collected-count acceptance criterion caught a shrunk near-miss parametrize (see Deviations)
3. **Task 3: Full-suite sweep and the plan's own commit** - no source changes needed; all three suites were already green after Tasks 1-2 (see below)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `operator-claude-plugin/scripts/n8n_arming.py` — `REVIEW_FLAGS`/`AUTHORITY_*`/`FLAGS_BY_AUTHORITY` constants; `authority=` threaded through `arm_for_dispatch`/`armed_window`; `arm_for_review`/`armed_review_window`; `disarm` rebuilt to derive targets/allowlist from declared flags with a fail-closed unreadable-pre-read path
- `operator-claude-plugin/scripts/write_grant.py` — `REVIEW_LANE`/`REVIEW_WORKFLOW_NAME`, `LANES["review"]`, the dated amendment comment, the unknown-lane refusal's dropped false claim, the multi-lane `_consequence()` sentence generalized to N lanes
- `operator-claude-plugin/scripts/review_decision.py` — retired the env kill switch; `submit_decision` gained `grant=None`; `GRANT_REFUSAL_REASON`/`_GRANT_REFUSAL`; docstring amendment; `__main__` diagnostic rewritten
- `operator-claude-plugin/tests/test_write_grant.py` — rewrote 2 tests, added 5 (tracer, PUT-body flag check, no-grant refusal, reject-proceeds, scope refusal) plus a `_review_workflow`/`_armed_review_workflow` fixture pair
- `operator-claude-plugin/tests/test_review_decision.py` — replaced the env-gate fixtures/tests with grant fixtures and a 7-case near-miss parametrize; every other `submit_decision` call site repointed at a grant fixture
- `operator-claude-plugin/tests/test_control_arming.py` — added the MEDIUM-2 (review-only-node disarm) and LOW-5 (unreadable-pre-read refusal) tests

## Decisions Made
- Followed the plan's D-60-01 through D-60-07 as written; no architectural deviations.
- The multi-lane `_consequence()` sentence was generalized to name however many lanes a grant spans (2 or 3) while preserving the exact trailing clause an existing pinned test asserts on — chosen over rewriting that test, since the plan's action only targeted the "both lanes at once" lead-in.
- Every grant fixture in `test_review_decision.py` uses the minimal literal shape `write_grant.covers` accepts, rather than the full `plan_grant`/`open_grant` round trip — documented in `_open_review_grant`'s own docstring: the grant-planning machinery is already exhaustively covered (including for review) by `test_write_grant.py`'s tracer, so duplicating that transport-stubbing setup here would add no coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_consequence()`'s multi-lane sentence broke an existing pinned test**
- **Found during:** Task 1, first full-suite run after the source edits
- **Issue:** Generalizing "This grant covers both lanes at once: it enables enrichment and writes to HubSpot." to a lane-count-derived sentence dropped the trailing clause `test_a_two_lane_grant_names_both_lanes_and_points_at_the_written_records_list` asserts on verbatim.
- **Fix:** Kept the trailing clause ("it enables enrichment and writes to HubSpot.") verbatim; only the lead-in ("both lanes at once" → "all N lanes at once") is now derived from `len(lane_names)`.
- **Files modified:** `operator-claude-plugin/scripts/write_grant.py`
- **Verification:** `test_write_grant.py` full suite green (180/180) after the fix.
- **Committed in:** `8a9dac0`

**2. [Rule 1 - Bug] The rewritten review-exclusion comment duplicated its own quoted trigger phrase**
- **Found during:** Task 1, running the plan's own acceptance-criteria grep
- **Issue:** `grep -c 'THE REVIEW LANE IS DELIBERATELY NOT GRANTABLE' write_grant.py` printed `2`, not the required `1` — my D-60-01/D-60-05 amendment quoted the original paragraph's own all-caps phrase verbatim, matching the grep a second time.
- **Fix:** Reworded the amendment to reference "the review lane's exclusion it describes" instead of repeating the exact quoted phrase.
- **Files modified:** `operator-claude-plugin/scripts/write_grant.py`
- **Verification:** grep now prints `1`; full suite still green.
- **Committed in:** `8a9dac0`

**3. [Rule 1 - Bug] Task 2's near-miss parametrize shrank the collected test count**
- **Found during:** Task 3's full-suite sweep, checking the plan's own acceptance criterion (collected count no lower than pre-change baseline)
- **Issue:** The plan's behavior list names exactly 4 grant-state near-miss cases (no grant, closed, wrong lane, not-a-grant-shape); the retired env-value near-miss set it replaced had 7 parametrized values. Swapping 7→4 shrank `test_review_decision.py`'s collected count from 49 to 46, and the plan's own acceptance criterion requires the collected count not drop.
- **Fix:** Widened the near-miss parametrize to 7 cases by adding: an empty dict, a grant carrying the wrong `kind`, and an open grant scoped to a different record — each a genuine additional near-miss, not a padding duplicate. Collected count returned to 49, matching the baseline exactly.
- **Files modified:** `operator-claude-plugin/tests/test_review_decision.py`
- **Verification:** `pytest --collect-only -q` reports 49; full suite green.
- **Committed in:** `4cb68e2`

---

**Total deviations:** 3 auto-fixed (3 bugs — all caught by the plan's own acceptance-criteria checks before task completion, none discovered after).
**Impact on plan:** All three were self-inflicted regressions in this task's own edits, caught and fixed within the same task before moving on. No scope creep; no plan behavior was weakened.

## Issues Encountered
None beyond the deviations above.

## User Setup Required
None - no external service configuration required. Nothing was armed, nothing was deployed, no HubSpot request and no provider call was made (per the plan's own `<verification>` requirement).

## Self-Check: PASSED

- `operator-claude-plugin/scripts/n8n_arming.py` — FOUND
- `operator-claude-plugin/scripts/write_grant.py` — FOUND
- `operator-claude-plugin/scripts/review_decision.py` — FOUND
- `operator-claude-plugin/tests/test_write_grant.py` — FOUND
- `operator-claude-plugin/tests/test_review_decision.py` — FOUND
- `operator-claude-plugin/tests/test_control_arming.py` — FOUND
- Commit `8a9dac0` — FOUND in `git log`
- Commit `7cc5780` — FOUND in `git log`
- Commit `4cb68e2` — FOUND in `git log`
- Full suites: root pytest 3815 passed / 154 skipped; `operator-claude-plugin/tests` 2145 passed / 5 skipped; `node --test tests/n8n/*.test.mjs` 848 pass / 0 fail — all at or above the plan's baseline (3539 / 844)
- `git status --porcelain n8n/` — empty (no workflow JSON touched)
- `git diff --stat -- tests/n8n/reviewWriteFlagSeparation.test.mjs` — empty (unmodified)

## Next Phase Readiness
- Ready for 60-02 (preflight guardrails: `WRITE_ENABLING_FLAGS` widened to 3, `read_live_write_state` widened to `OVERLAYABLE_FLAGS`, the batch-window lifecycle).
- The `AUTHORITY_DISPATCH`/`AUTHORITY_REVIEW`/`FLAGS_BY_AUTHORITY` constants and `arm_for_review`/`armed_review_window` are available for 60-02/60-03 to build on without further n8n_arming.py changes to the arm/disarm core.
- No blockers.

---
*Phase: 60-review-lane-authority*
*Completed: 2026-09-01*
