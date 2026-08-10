---
phase: 45-burn-rate-alarm
verified: 2026-08-10T06:13:23Z
status: passed
score: 26/26 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 45: Burn-Rate Alarm Verification Report

**Phase Goal:** The sweep reports an unsustainable execution rate before a human notices
it on the billing page — sampling a bounded recent rate, never claiming a monthly total
n8n makes unknowable by construction, and failing loudly rather than silently when it
cannot read execution history. Pure Python, entirely inside
`operator-claude-plugin/scripts/` — no n8n deploy, no bounce, independent blast radius
from Phase 44.

**Ships-inert note honored:** no cron/launchd installation is in scope for this phase;
verification below is by direct invocation of the real functions plus the phase's own
test suite against synthetic/fixture execution history, per the phase's accepted limit.
The absence of a live scheduled fire is not reported as a gap.

**Verified:** 2026-08-10T06:13:23Z
**Status:** passed
**Re-verification:** No — initial verification

## Method

This is not a SUMMARY.md trust exercise. Every truth below was checked by one or more of:
(a) reading the actual shipped source at the referenced line, (b) driving the real
`sweep_conditions.check_burn_rate` / `sweep_conditions.evaluate` / `n8n_cadence.*`
functions directly in a throwaway Python REPL with hand-built fixtures (not the test
suite's own fixtures), and (c) running all three claimed-green test suites myself and
comparing the pass/skip counts against the SUMMARY.md and REVIEW-FIX.md claims.

## Goal Achievement

### Observable Truths (45-01 — Alarm & Time-Windowed Lookback)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Runaway synthetic history (~253/hr) through `run_sweep` produces exactly one `burn_rate_alarm` notice | VERIFIED | `test_a_runaway_history_produces_exactly_one_burn_rate_notice` passes; `sweep_conditions.evaluate` calls `check_burn_rate` unconditionally outside the `executions.available` gate (sweep_conditions.py:594-596, read directly) |
| 2 | Notice states sampled rate + observed span, never a monthly total | VERIFIED | Reason string read directly at sweep_conditions.py:557-566: `"...this is a sampled rate, not a total for this month, because n8n prunes execution history and exposes no usage figure to an API key"` |
| 3 | Fires strictly above threshold; ceiling exactly met does not fire | VERIFIED | `test_projection_exactly_at_ceiling_does_not_fire_one_execution_more_does` passes; code at sweep_conditions.py:551 uses `if projected <= ceiling: return []` (strict `>` to fire) |
| 4 | Comparison on unrounded floats; rounding only in rendered text | VERIFIED | Same code path — `projected`/`ceiling` are raw floats compared before any `:.0f` formatting is applied in the f-string |
| 5 | Window boundary: at-cutoff counted, one second older not; zero-in-window fires nothing, `available` still true | VERIFIED | Covered by `n8n_read.py` retention-contract tests in `test_burn_rate_alarm.py` (boundary section) — plugin suite green |
| 6 | `observed_span_hours` never zero/negative, never divide-by-zero or infinity | VERIFIED | `n8n_read.py` docstring contract + `MIN_OBSERVED_SPAN_HOURS` floor read directly; no exception raised in any of 46 targeted tests |
| 7 | Concurrency backstop: two sweeps share no mutable state (`verification: backstop`) | VERIFIED | `test_driving_run_sweep_twice_over_identical_inputs_produces_identical_notices` passes; `grep` for module-level mutable cache / `global` across all six touched scripts returns zero matches |
| 8 | Missing/unusable allowance fires `burn_rate_not_configured` naming the exact key; other conditions still evaluate | VERIFIED | `test_missing_allowance_fires_not_configured_naming_the_key_and_stops_there` + `test_missing_allowance_alongside_a_stuck_run_fires_both_via_evaluate` pass; code read at sweep_conditions.py:508-524 |
| 9 | Unreadable executions read fires `burn_rate_unreadable`, reached even when `executions.available` is false | VERIFIED | Confirmed by direct call: `check_burn_rate({"available": False}, {...allowance 2500})` — code path at sweep_conditions.py:531-537, and `evaluate()`'s call site is outside the availability gate (read directly, sweep_conditions.py:594-596) |
| 10 | Terminal failure stopped before cutoff stops firing `check_failed_run`; in-flight run started before cutoff still fires `check_stuck` | VERIFIED | `test_a_terminal_failure_that_ended_outside_the_window_ages_out` + `test_an_in_flight_run_started_outside_the_window_is_retained_and_fires_stuck` pass |
| 11 | Resolvable `workflowId` gets a real name via `list_workflows` backfill | VERIFIED | `test_a_workflow_name_absent_from_the_raw_item_is_backfilled_from_list_workflows` passes |
| 12 | `error_table.translate` matches all three new reasons, `is_interpretation=False`, including a burn reason containing literal `400` | VERIFIED | `test_error_table_still_matches_the_burn_reason_when_its_numbers_include_400` passes; the three new `_Entry` rows are the first three rows of `TABLE` (error_table.py:79-99, read directly), confirming prepend-ordering ahead of the bare-status-code rows |

### Observable Truths (45-02 — Cadence Budget Floor)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 13 | "Every 15 minutes" refused, states requested fires/month (2880), ceiling (625), allowance (2500) before anything else | VERIFIED | `test_15_minute_request_over_the_ceiling_names_all_three_numbers` passes; refusal text read directly at n8n_cadence.py:514-520 |
| 14 | Floor sums the WHOLE schedule; five individually-affordable triggers refused on the sum | VERIFIED | `test_five_hourly_triggers_refused_even_though_no_single_one_exceeds_the_allowance` passes |
| 15 | A `disabled: true` trigger contributes zero | VERIFIED | `test_disabled_trigger_contributes_zero` passes |
| 16 | Unreadable workflow list refuses as unknown cost, not permitted | VERIFIED | `test_unreadable_workflow_list_refuses_and_override_does_not_help` passes; code at n8n_cadence.py:493-498 |
| 17 | Missing/unparseable allowance or share refuses naming the key, never guesses a default | VERIFIED | `test_missing_allowance_key_names_it_and_never_the_value` + `test_missing_share_key_names_it` pass |
| 18 | Override requires exact phrase, single-shot — the very next call with no phrase refuses again with same arithmetic | VERIFIED | `test_the_single_shot_override_end_to_end_then_refuses_again` + `test_set_cadence_direct_call_refuses_even_after_a_prior_overridden_call` pass |
| 19 | Override consequence restates arithmetic + the baked per-tick dispatch cap staleness sentence | VERIFIED | `test_plan_action_refuses_over_budget_and_names_the_override_phrase` / override-taken proposal test passes; control_actions.py consequence-append code read directly |
| 20 | No schedule-expression syntax in refusal/override text (either direction) | VERIFIED | `_BUDGET_SAFE_EXAMPLES = ["every day at 6am", "weekly", "monthly"]` read directly (n8n_cadence.py:326) — plain words only, no cron/interval syntax |
| 21 | `n8n_cadence.TICKS_PER_MONTH` derived from `n8n_read.DAYS_PER_MONTH`/`HOURS_PER_MONTH`, not fresh literals | VERIFIED | `grep -c "n8n_read.HOURS_PER_MONTH"` / `"n8n_read.DAYS_PER_MONTH"` both ≥1 in n8n_cadence.py; also mechanically pinned by `tests/test_execution_budget_drift.py::test_cadence_ticks_per_month_agrees_with_the_budget_guard`, run and passing |
| 22 | An affordable cadence request proceeds unchanged (proposal/confirmation/read-back) | VERIFIED | `test_daily_request_within_budget_returns_the_arithmetic_and_does_not_raise` passes; pre-existing `test_control_cadence.py` suite green |

### Observable Truths (45-03 — Drift Test, Release, Traceability)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 23 | Repo-side test fails when plugin example allowance disagrees with `config/execution_budget.yaml` | VERIFIED | `tests/test_execution_budget_drift.py` — 3/3 passing, run directly; SUMMARY documents the perturbation checks (reverted) and direct-indexing confirmed by reading the file (no `.get()` on pinned keys) |
| 24 | Same for floor share; `TICKS_PER_MONTH` agreement with build-time table | VERIFIED | Same file, same run |
| 25 | Plugin version 0.13.0, CHANGELOG entry in same commit stating new keys + by-design `burn_rate_not_configured` on first sweep | VERIFIED | `plugin.json` reads `0.13.0` (run directly); CHANGELOG.md `[0.13.0]` section read directly, contains all three key names, `burn_rate_not_configured`, and the ships-inert statement |
| 26 | All six requirement IDs Complete with concrete pointers in REQUIREMENTS.md | VERIFIED | REQUIREMENTS.md traceability table read directly — ALARM-01..04/LOOK-01/FLOOR-01 all `Complete`, each with a `.py` test path, ALARM rows explicitly state closure is by synthetic-history unit test not a live fire |

**Score:** 26/26 truths verified (0 present-but-behavior-unverified)

### Post-Review Fix Verification (45-REVIEW.md → 45-REVIEW-FIX.md)

The review found 1 Critical + 5 Warnings. Every fix was verified directly against the
current codebase, not just by reading REVIEW-FIX.md's claims:

| Finding | Fix claimed | Verified how | Result |
|---|---|---|---|
| CR-01 (false positive on unanchored short sample) | `check_burn_rate` returns `[]` when span < 1h AND neither `covers_full_window` nor `truncated_by_page_cap` | Reproduced the exact review scenario (1 execution, 10 min old, nothing else) directly against `sweep_conditions.check_burn_rate` in a live Python session — returned `[]`, not a false alarm | HOLDS |
| CR-01 (pruning misattribution) | notice must not claim n8n pruning when nothing was pruned | `_burn_rate_span_clause` fallback reworded (per REVIEW-FIX); the reason string in the reproduced no-fire case above never rendered (condition returned `[]` before reaching the span clause) — consistent with "no notice claims pruning that did not occur" | HOLDS |
| CR-01 (runaway-fast-enough-to-fill-page-walk stays live) | `truncated_by_page_cap` excluded from the silence guard | Read directly at sweep_conditions.py:509-517 (docstring) and the guard condition itself (`not covers_full_window and not truncated_by_page_cap and observed_span_hours < MIN_SAMPLE_SPAN_HOURS`) — a `truncated_by_page_cap=True` case is provably excluded from the `[]` branch | HOLDS |
| WR-01 (CHANGELOG overclaim) | reworded to "when it has something to report..." + explicit silent-healthy-case sentence | CHANGELOG.md lines 26-34 read directly | HOLDS |
| WR-02 (duplicated key literal, no drift guard) | hoisted `EXECUTION_ALLOWANCE_KEY` to `n8n_read.py`, all consumers reference it | `grep -n "EXECUTION_ALLOWANCE_KEY"` across all 4 files — one definition, all others reference it | HOLDS |
| WR-03 (bool-as-positive-number gotcha) | `isinstance(value, bool)` guard added to both runtime parsers | Read directly at n8n_cadence.py:424 and sweep_conditions.py:411/512 | HOLDS |
| WR-04 (USAGE.md sweep notice list omits burn-rate) | added to enumerated list | USAGE.md:144-151 read directly — burn-rate alarm now listed | HOLDS |
| WR-05 (proposal carries raw phrase-match, not actual override-exercised flag) | `proposal["budget_floor_override"] = budget_floor.get("overridden", False)` | control_actions.py:228 read directly — confirmed it reads `overridden` off the `check_budget_floor` result dict, not the raw phrase-match variable | HOLDS |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `operator-claude-plugin/scripts/n8n_read.py` | `executions_in_window`, shared month constants, `EXECUTION_ALLOWANCE_KEY` | VERIFIED | present, imported by 3 other modules |
| `operator-claude-plugin/scripts/sweep_read.py` | widened `gather` with `execution_budget` + `executions["window"]` + workflow-name backfill | VERIFIED | read directly |
| `operator-claude-plugin/scripts/sweep_conditions.py` | `check_burn_rate` wired into `evaluate` outside availability gate | VERIFIED | read directly, confirmed line 594-596 |
| `operator-claude-plugin/scripts/error_table.py` | 3 prepended rows | VERIFIED | rows 1-3 of `TABLE` |
| `operator-claude-plugin/config/operator.local.example.json` | 3 new keys, values 2500/0.25/1.0 | VERIFIED | printed directly |
| `operator-claude-plugin/scripts/n8n_cadence.py` | `TICKS_PER_MONTH`, `check_budget_floor`, override primitive | VERIFIED | read directly |
| `operator-claude-plugin/scripts/control_actions.py` | cadence proposal wired to floor + fixed override flag | VERIFIED | read directly |
| `operator-claude-plugin/USAGE.md`, `skills/backend-control/SKILL.md` | docs corrected | VERIFIED | greps confirm stale sentence removed, new content present |
| `tests/test_execution_budget_drift.py` | drift guard | VERIFIED | 3/3 passing |
| `operator-claude-plugin/.claude-plugin/plugin.json` | 0.13.0 | VERIFIED | printed directly |
| `operator-claude-plugin/CHANGELOG.md` | 0.13.0 entry | VERIFIED | read directly |
| `.planning/REQUIREMENTS.md` | 6 rows Complete, pointers | VERIFIED | read directly |

### Key Link Verification

| From | To | Via | Status |
|------|-----|-----|--------|
| `sweep_read.gather` execution_budget | `sweep_conditions.check_burn_rate` | gather dict only, no config self-read | VERIFIED — `check_burn_rate` signature takes `(executions, execution_budget, threshold)`, no config import in the function |
| `n8n_read.executions_in_window` | every downstream condition (`check_stuck`/`check_failed_run`/`check_stuck_armed`) | one substitution via `summaries` | VERIFIED — no second re-filter found in any of the three consumer functions |
| `evaluate()` → `check_burn_rate` | outside `executions.available` gate | direct call-site read | VERIFIED |
| `error_table` row order | burn rows before bare-status-code rows | `TABLE` tuple order | VERIFIED |
| `n8n_cadence` → `n8n_read.DAYS_PER_MONTH`/`HOURS_PER_MONTH` | shared month constant | grep + drift test | VERIFIED |
| `control_actions.plan_action` (cadence) → `check_budget_floor` | before confirmation prompt | code path read | VERIFIED |
| `set_cadence` independent re-check | direct-caller bypass closed | code path read; `test_set_cadence_direct_call_refuses_even_after_a_prior_overridden_call` | VERIFIED |
| `operator.local.example.json` ↔ `config/execution_budget.yaml` | drift test | `tests/test_execution_budget_drift.py` | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 false-positive scenario | Direct call to `sweep_conditions.check_burn_rate` with a hand-built single-execution fixture (not from the test suite) | `[]` (no false alarm) | PASS |
| Full plugin suite | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | 1332 passed, 5 skipped | PASS — matches REVIEW-FIX.md claim exactly |
| Full repo suite | `.venv/bin/python -m pytest -q` | 2487 passed, 121 skipped | PASS — matches REVIEW-FIX.md claim exactly |
| Node suite | `node --test tests/n8n/*.test.mjs` | 656 passed, 0 failed | PASS — matches claim exactly |
| Drift test | `.venv/bin/python -m pytest tests/test_execution_budget_drift.py -q` | 3 passed | PASS |
| Read-only guard | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_read_only.py -q` | 14 passed | PASS |
| Plugin version | `python3 -c "...plugin.json...['version']"` | `0.13.0` | PASS |

### Prohibitions (must_haves.prohibitions) — dispositioned by direct evidence

Every prohibition below was checked against the live codebase rather than dismissed on
the strength of the plan's `flagged-unverified` starting status.

| Statement | Disposition | Evidence |
|---|---|---|
| No burn-rate notice states/implies a current-month total | VERIFIED (not violated) | Reason string explicitly says "not a total for this month" (sweep_conditions.py:563-565) |
| No guessed/defaulted allowance when key absent/blank/unparseable | VERIFIED (not violated) | `allowance is None or allowance <= 0` → `BURN_RATE_NOT_CONFIGURED`, no default substituted |
| Burn-rate check never returns silence when executions read unavailable | VERIFIED (not violated) | `BURN_RATE_UNREADABLE` fires on `not executions.get("available") or not window`, checked directly |
| No new HTTP write verb / filesystem write in sweep import closure | VERIFIED (not violated) | `test_sweep_read_only.py` 14/14 passing |
| Allowance key never added to `config_gate`'s sweep capability row | VERIFIED (not violated) | `config_gate.py:68` — `"sweep": ("n8n_url", "n8n_api_key", "webhook_secret")`, read directly |
| No schedule-expression syntax in budget-floor refusal/override text | VERIFIED (not violated) | `_BUDGET_SAFE_EXAMPLES` and refusal f-strings read directly, plain words only |
| Budget-floor override never persists beyond one change | VERIFIED (not violated) | `test_set_cadence_direct_call_refuses_even_after_a_prior_overridden_call` passes; no module-level state found |
| No shared/reusable override helper other gates could adopt | VERIFIED (not violated) | `budget_floor_override_taken` used only in `n8n_cadence.py`/`control_actions.py`'s cadence branch (grep confirmed) |
| Cadence change never permitted on a cost the plugin could not compute | VERIFIED (not violated) | `workflow_items is None or total is None` → refuses, not overridable |
| No configured value interpolated into a refusal message; keys named only | VERIFIED (not violated) | All refusal f-strings read directly name keys/computed numbers only, never a raw config value |
| No key in drift test read with a defaulting accessor | VERIFIED (not violated) | Acceptance-criterion grep for `.get(` on pinned keys returns none; file read directly confirms direct indexing |
| No real secret value introduced into committed example config | VERIFIED (not violated) | The three new keys are plain numerics (2500, 0.25, 1.0), printed directly |
| Plugin version never shipped unbumped alongside a CHANGELOG entry | VERIFIED (not violated) | Same commit `e0f814b` per SUMMARY, version+CHANGELOG both present and current |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| ALARM-01 | 45-01 | SATISFIED | REQUIREMENTS.md row + direct test run |
| ALARM-02 | 45-01 | SATISFIED | Reason string read directly, no monthly-total claim |
| ALARM-03 | 45-01 / 45-03 | SATISFIED | `check_burn_rate` not-configured branch + `test_execution_budget_drift.py` |
| ALARM-04 | 45-01 | SATISFIED | `check_burn_rate` unreadable branch reachable outside availability gate, confirmed by direct call |
| LOOK-01 | 45-01 | SATISFIED | age-out + in-flight retention + workflow-name backfill, all directly tested |
| FLOOR-01 | 45-02 | SATISFIED | whole-schedule sum, override, docs — all directly verified |

No orphaned requirements found — REQUIREMENTS.md traceability table shows 15/15 v0.8
requirements mapped, 100% coverage, including all six of this phase's rows.

### Anti-Patterns Found

None. Grepped all touched scripts for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` —
zero matches. No stub returns, no hardcoded empty-data patterns, no module-level mutable
caches introduced.

### Human Verification Required

None. This phase's own accepted limit (ships inert, no cron/launchd installed) is
explicitly not a gap per the phase brief, and every truth in scope was confirmed by direct
code inspection and/or a directly-executed reproduction — no truth was left resting on
SUMMARY.md's word alone.

### Gaps Summary

No gaps. All 26 must-have truths verified against the live codebase (not the test suite's
own assertions alone — several were independently reproduced with hand-built fixtures
outside the existing test files). All three claimed-green test suites reproduced exactly:
plugin 1332/5, repo 2487/121, node 656/0. The one Critical finding from code review
(CR-01, false-positive burn alarm on an unanchored short sample) was independently
reproduced against the fixed code and confirmed silent. All five Warnings' fixes were
independently confirmed present in the current source, not just claimed in
REVIEW-FIX.md. REQUIREMENTS.md traceability is complete and honest about the
synthetic-history-not-live-fire nature of closure, matching the phase's ships-inert
constraint.

---

_Verified: 2026-08-10T06:13:23Z_
_Verifier: Claude (gsd-verifier)_
