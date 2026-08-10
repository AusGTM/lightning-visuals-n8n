---
phase: 45-burn-rate-alarm
fixed_at: 2026-08-10T06:06:39Z
review_path: .planning/phases/45-burn-rate-alarm/45-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 45: Code Review Fix Report

**Fixed at:** 2026-08-10T06:06:39Z
**Source review:** .planning/phases/45-burn-rate-alarm/45-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 Critical, 5 Warning)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: The burn-rate alarm fires false positives when no execution older than the window is in retained history (single-sample extrapolation)

**Files modified:** `operator-claude-plugin/scripts/sweep_conditions.py`,
`operator-claude-plugin/tests/test_burn_rate_alarm.py`,
`operator-claude-plugin/tests/test_sweep_tracer.py`
**Commit:** 356b0eb
**Applied fix:** `check_burn_rate` now returns silently (`[]`) rather than firing when
the observed span is under `MIN_SAMPLE_SPAN_HOURS` (1 hour) AND the window is neither
`covers_full_window` nor `truncated_by_page_cap` — i.e. there genuinely is no older
execution in retained history to anchor the extrapolation against. This intentionally
excludes `truncated_by_page_cap`: a runaway fast enough to fill the whole page walk
(1,000 executions) inside an hour would otherwise be permanently silenced by the same
guard for the entire duration of the burn, which is the exact incident shape D-01
exists to catch — a dedicated test proves this stays live. `_burn_rate_span_clause`'s
fallback branch, which previously asserted "n8n has pruned older execution history"
unconditionally whenever the walk found no older item, now names both possibilities
(pruning or genuinely no older execution yet) rather than asserting a cause it did not
observe, honoring D-01 ("the rate must never pretend to a window it did not see").

The chosen shape (bare `[]` rather than a fourth named condition) was deliberated
against the review's preference for a distinct outcome — see the commit message for the
reasoning: restoring `test_the_within_threshold_run_alone_is_silent`'s full-silence
assertion (as directed) forces it, and on reflection it is also the D-15-consistent
choice, since "not enough sample yet" is a normal transient state (first sweep after a
deploy, a history wipe, a quiet system) that resolves itself within the hour and is
never actionable by an operator or admin, unlike `burn_rate_not_configured` /
`burn_rate_unreadable`.

`test_sweep_tracer.py`'s `test_the_within_threshold_run_alone_is_silent` had its
workaround docstring deleted and its assertion restored to `assert notices == []`.
Added a direct regression test reproducing CR-01 exactly (one execution started ~10
minutes ago, nothing else readable) proving no alarm fires and no notice mentions
pruning, plus a boundary test (just under vs. at `MIN_SAMPLE_SPAN_HOURS`) and a test
proving a page-cap-truncated runaway still fires.

### WR-01: CHANGELOG.md overstates the burn-rate condition's non-silence guarantee

**File modified:** `operator-claude-plugin/CHANGELOG.md`
**Commit:** ce2b4f7
**Applied fix:** Reworded "reports one of three outcomes on every sweep, never
silence" to "when it has something to report, the condition names one of three
outcomes," and added an explicit sentence naming the healthy-silence case (including
the CR-01 sample-too-short silence). Also updated the pruning-related clause in the
same bullet to match CR-01's corrected wording.

### WR-02: The allowance config-key literal is duplicated with no drift guard

**Files modified:** `operator-claude-plugin/scripts/n8n_read.py`,
`operator-claude-plugin/scripts/sweep_read.py`,
`operator-claude-plugin/scripts/sweep_conditions.py`,
`operator-claude-plugin/scripts/n8n_cadence.py`
**Commit:** 3c0692f
**Applied fix:** Hoisted `EXECUTION_ALLOWANCE_KEY = "n8n_monthly_execution_allowance"`
to `n8n_read.py` (mirroring its existing `DAYS_PER_MONTH`/`HOURS_PER_MONTH` precedent).
`sweep_read.py`, `n8n_cadence.py` (both the config read and the refusal message), and
`sweep_conditions.py`'s own fallback literal now all reference the one constant instead
of spelling the string independently — a structural fix (one literal left in the
codebase) rather than a drift test, since there is nothing left to drift.

### WR-03: Runtime allowance/threshold parsing doesn't guard against `bool` masquerading as a positive number

**Files modified:** `operator-claude-plugin/scripts/n8n_cadence.py`,
`operator-claude-plugin/scripts/sweep_conditions.py`,
`operator-claude-plugin/tests/test_burn_rate_alarm.py`,
`operator-claude-plugin/tests/test_cadence_budget_floor.py`
**Commit:** ed40659
**Applied fix:** Added `isinstance(value, bool)` checks ahead of the `float()` call in
`n8n_cadence._read_positive_float`, `sweep_conditions._parsed_burn_rate_threshold`, and
the allowance parse inline in `sweep_conditions.check_burn_rate` — the same guard
`tests/test_execution_budget_drift.py` already applies to the static config artifacts.
A misconfigured `"key": true` now degrades to the same missing/unusable-config handling
as any other unparseable value, rather than silently becoming a real `1.0`.

### WR-04: USAGE.md's "unattended sweep" section still doesn't list the burn-rate alarm among the notices it can raise

**File modified:** `operator-claude-plugin/USAGE.md`
**Commit:** 1a9aab2
**Applied fix:** Added "...or the n8n execution rate running high enough to blow
through the monthly plan" to the enumerated list under "## The unattended sweep".

### WR-05: `plan_action`'s cadence proposal carries the raw override phrase-match, not whether the override was actually exercised

**Files modified:** `operator-claude-plugin/scripts/control_actions.py`,
`operator-claude-plugin/tests/test_cadence_budget_floor.py`
**Commit:** db55537
**Applied fix:** `proposal["budget_floor_override"]` is now set from
`budget_floor.get("overridden", False)` instead of the raw phrase-match `override`
variable, so the flag only carries forward when `check_budget_floor` actually
exercised the override against the numbers shown in the same `consequence` message.
Added a regression test for the exact gap named in the finding: an override phrase
present on an already-within-budget request must not set the flag.

## Skipped Issues

None — all in-scope findings were fixed.

## Verification

All three suites were run from an isolated review-fix worktree (see this repo's
`gsd-code-fixer` worktree protocol) before it was fast-forward-merged and torn down.
A temporary `.venv` symlink into the worktree was used to run the Node suite, since
the worktree has no local virtualenv or `node_modules` by construction (no
`node_modules` exists in this repo at all — the Node suite runs against system
`node`); the symlink was removed before cleanup and no artifact from it was
committed. All commits are now on `master` at `db55537` after the fast-forward.

- `operator-claude-plugin` suite: 1332 passed, 5 skipped (baseline 1326/5 — 6 new tests)
- Repo-wide (`.venv/bin/python -m pytest -q`): 2487 passed, 121 skipped (baseline 2481/121)
- Node (`node --test tests/n8n/*.test.mjs`): 656 passed, 0 failed (baseline 656/0, unchanged)

---

_Fixed: 2026-08-10T06:06:39Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
