---
phase: 45-burn-rate-alarm
reviewed: 2026-08-10T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/config/operator.local.example.json
  - operator-claude-plugin/scripts/control_actions.py
  - operator-claude-plugin/scripts/error_table.py
  - operator-claude-plugin/scripts/n8n_cadence.py
  - operator-claude-plugin/scripts/n8n_read.py
  - operator-claude-plugin/scripts/sweep_conditions.py
  - operator-claude-plugin/scripts/sweep_read.py
  - operator-claude-plugin/skills/backend-control/SKILL.md
  - operator-claude-plugin/tests/conftest.py
  - operator-claude-plugin/tests/test_burn_rate_alarm.py
  - operator-claude-plugin/tests/test_cadence_budget_floor.py
  - operator-claude-plugin/tests/test_control_cadence.py
  - operator-claude-plugin/tests/test_control_surface.py
  - operator-claude-plugin/tests/test_sweep_attribution.py
  - operator-claude-plugin/tests/test_sweep_conditions.py
  - operator-claude-plugin/tests/test_sweep_tracer.py
  - operator-claude-plugin/USAGE.md
  - tests/test_execution_budget_drift.py
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
status: issues_found
---

# Phase 45: Code Review Report

**Reviewed:** 2026-08-10
**Depth:** standard
**Files Reviewed:** 20 (+ `operator-claude-plugin/scripts/sweep_entry.py` and
`config/execution_budget.yaml` read for cross-file context; not separately counted)
**Status:** issues_found

## Summary

All 2,481 repo-wide tests pass (`.venv/bin/python -m pytest -q`), including the 138 tests
scoped to this phase. The implementation is disciplined and matches the D-01..D-10
decisions closely: anchor-free 30-day projection, condition-level not-configured/unreadable
degradation, the single-shot cadence-floor override, and the time-windowed lookback all
check out against direct code tracing and reproduction.

However, direct reproduction against the real `n8n_read.executions_in_window` +
`sweep_conditions.check_burn_rate` pipeline shows the burn-rate alarm **fires when the
sweep's readable execution history contains nothing older than the 24h window** — a state
that is reachable on an entirely healthy backend (first day after deploying this phase, a
history wipe, or simply a quiet enough system that nothing ran in the last 24h before one
job fires) — because a single recent item with no older item to anchor the span against
gets extrapolated as a sustained rate. The test suite has already worked around one shape
of this once (see `test_the_within_threshold_run_alone_is_silent`'s docstring, which names
the defect and narrows its own assertion rather than fixing the root cause) rather than
closing it. Given this feature exists specifically so an operator can trust the alarm
("silence means healthy," NOTICE-04's "a sweep that speaks when healthy is one the operator
learns to ignore"), a reproducible false positive in a reachable state is a BLOCKER — see
CR-01 for the corrected precondition (an earlier draft of this finding overstated how often
it recurs on a mature, steadily-running backend; that overstatement is fixed below).

The remaining findings are documentation-accuracy and maintainability issues: a factually
incorrect CHANGELOG claim, a config-key literal duplicated with no drift guard (the kind of
gap D-04's own drift test exists to prevent, just one layer over), a runtime allowance/
threshold parser that doesn't guard against the same `bool`-as-`int` gotcha the drift test
explicitly filters out, a `USAGE.md` section that Phase 45's own canonical_refs flagged for
update but which still omits the new condition from its enumerated notice list, and a
proposal field that carries the cadence-floor override's raw phrase-match result rather than
whether the override was actually exercised.

## Critical Issues

### CR-01: The burn-rate alarm fires false positives when no execution older than the window is in retained history (single-sample extrapolation)

**File:** `operator-claude-plugin/scripts/sweep_conditions.py:492-494` (rate/projection
math), consuming `operator-claude-plugin/scripts/n8n_read.py:358-363`
(`observed_span_hours` derivation)

**Issue:** `observed_span_hours` is only pinned to the full 24h window
(`covers_full_window = True`) once the walk has seen at least one item whose `startedAt` is
*strictly older* than the cutoff (`n8n_read.py:347-348`). Until that happens, the span
collapses to "how long ago the oldest item seen so far started," and
`rate_per_hour = count_in_window / observed_span_hours` extrapolates a tiny, recent sample
as a sustained rate. The 30-day projection then clears the default 2,500/month ceiling for
a lone execution observed shortly after it started, with nothing else in the read.

Reproduced directly against the real functions: a single execution that started 10 minutes
before "now," with **no other execution readable at all**, produces:

```
count_in_window: 1, observed_span_hours: 0.1667, covers_full_window: False
fired: [{'condition': 'burn_rate_alarm',
         'reason': 'n8n execution rate sampled at 6.0 per hour over only the last 0.2
                    hours because n8n has pruned older execution history — ...
                    projecting to about 4320 executions over the next 30 days against the
                    2500-execution monthly allowance (1x ceiling 2500) ...'}]
```

**Corrected precondition (verified by control run, per advisor review of an earlier
overstated draft of this finding):** adding one second item started 25 hours ago to the
same fixture defuses it completely — `covers_full_window` flips to `True`,
`observed_span_hours` becomes `24.0`, and `check_burn_rate` returns `[]`. So this is **not**
"any lone execution within ~17 minutes of a sweep, recurring regularly on a mature running
system" — on a backend with any execution history older than 24h (which is the ordinary
steady state once the daily/weekly/monthly maintenance schedule has run for more than a
day), yesterday's runs anchor the span and the false positive does not occur. The real
precondition is narrower but still concretely reachable: **the sweep's readable execution
history contains nothing started more than 24h ago** — true on the first day after this
phase (or any redeploy) is live and the sweep is run to check it, after n8n execution
history has been cleared/rotated, or simply the first time the sweep is ever pointed at a
fresh/low-traffic n8n instance. All three are states an admin is actively watching closely
(exactly when a false alarm does the most damage to trust in the tool), and none require an
actual runaway.

This is worse than a nuisance in that window: the rendered reason also actively
**misattributes the cause** — it claims "n8n has pruned older execution history"
(`_burn_rate_span_clause`'s fallback branch, `sweep_conditions.py:422-425`) when, in this
state, nothing was pruned at all; there simply is no older execution yet.
`covers_full_window=False` and `truncated_by_page_cap=False` are indistinguishable, in the
current code, between "pruning truncated the read" and "the window genuinely has no older
item" — the fallback message picks the pruning narrative unconditionally, which is a second
inaccuracy riding on the first, in a codebase whose central design principle is that a
notice must never claim a cause it cannot support (D-01: "the rate must never pretend to a
window it did not see").

The project's own test suite is already aware of a version of this defect and worked around
it rather than fixing it — `operator-claude-plugin/tests/test_sweep_tracer.py`'s
`test_the_within_threshold_run_alone_is_silent` docstring:

> "Phase 45: a single execution 2 minutes old is also a single-sample burn-rate
> extrapolation (MIN_OBSERVED_SPAN_HOURS's divide-by-zero floor over a near-zero span
> inflates the projected rate) — so this fixture is no longer full-silence by
> construction. The assertion is scoped to what this test actually proves..."

`MIN_OBSERVED_SPAN_HOURS` (1 minute, `n8n_read.py:68`) is a division-by-zero guard only —
it does nothing to prevent a small, unanchored span from being extrapolated as a sustained
rate. No test in this phase's suite exercises "single recent execution, nothing else in
history at all" end to end and asserts silence — the closest fixture
(`test_the_within_threshold_run_alone_is_silent`) deliberately narrows its own assertion to
avoid having to make that claim.

**Fix:** Require a minimum sample before trusting the extrapolation, or require
`covers_full_window` (a genuinely anchored span) before firing on a small sample —
e.g. in `sweep_conditions.check_burn_rate`:

```python
MIN_SAMPLE_SPAN_HOURS = 1.0  # a handful of executions with no anchoring older item
                              # cannot support a 30-day extrapolation; wait for either a
                              # real sampling period or a genuinely anchored window.

...
if not window.get("covers_full_window") and observed_span_hours < MIN_SAMPLE_SPAN_HOURS:
    return []   # or a distinct "sample too small to project" outcome — never a false
                # BURN_RATE fire, and never claim pruning when none occurred
```

Separately, `_burn_rate_span_clause` should not default to the pruning narrative when the
walk never encountered an older item at all — distinguish "no older item exists in
retained history" from "an older item exists but our own read stopped short of it."

## Warnings

### WR-01: CHANGELOG.md overstates the burn-rate condition's non-silence guarantee

**File:** `operator-claude-plugin/CHANGELOG.md:26-27`
**Issue:** "The condition reports one of three outcomes on every sweep, never silence:
`burn_rate_alarm` ..., `burn_rate_not_configured` ..., or `burn_rate_unreadable` ...".
This is factually incorrect against the shipped behavior and the shipped test suite:
`check_burn_rate` returns `[]` (no notice at all) whenever the allowance is configured,
readable, and the projected rate is under ceiling — confirmed by
`test_a_quiet_history_produces_no_notice_at_all` ("3 executions in 24 hours ... must be
silent") and `test_an_all_healthy_input_produces_no_notice_at_all`. The healthy case is,
correctly, silent — matching every other condition in this sweep (D-08/NOTICE-04). Given
this codebase's stated design principle is that notices must never overclaim, a CHANGELOG
entry claiming "never silence" for a condition whose whole design is "silent when healthy"
is a real accuracy defect an admin reading the release notes would be misled by.
**Fix:** Reword to something like "When it has something to report, the condition names
one of three outcomes ...", or "the condition never goes silent about a *problem* it can
see" — whichever the author intended — rather than the current unqualified "never silence."

### WR-02: The allowance config-key literal is duplicated with no drift guard

**File:** `operator-claude-plugin/scripts/n8n_cadence.py:461,464` vs
`operator-claude-plugin/scripts/sweep_read.py:49`
**Issue:** `sweep_read.py` defines `EXECUTION_ALLOWANCE_KEY = "n8n_monthly_execution_allowance"`
as a named constant specifically so the burn-rate alarm's key name has one home. But
`n8n_cadence.check_budget_floor` hardcodes the identical string literal twice
(`"n8n_monthly_execution_allowance"` at both the `_read_positive_float` call and inside the
refusal message) rather than importing/referencing `sweep_read.EXECUTION_ALLOWANCE_KEY`.
Nothing in the test suite asserts these two spellings stay in sync (checked: no test greps
or imports one against the other). This is exactly the class of drift D-04's dedicated
`tests/test_execution_budget_drift.py` was built to prevent for the *value*; the *key name*
itself has the identical two-independent-literals shape with no equivalent guard. A rename
in one module silently breaks the other's config lookup (the cadence floor would refuse
every schedule change citing a key that no longer matches what an admin's config file
actually contains, or vice versa).
**Fix:** Either have `n8n_cadence.py` import `sweep_read.EXECUTION_ALLOWANCE_KEY` (mind the
import-direction/coupling implications — `sweep_read` is I/O-only per its own docstring, so
consider hoisting the constant to a shared location `n8n_read.py` already plays for
`DAYS_PER_MONTH`/`HOURS_PER_MONTH`), or add a small drift test asserting the two string
literals are equal, mirroring `tests/test_execution_budget_drift.py`'s own precedent.

### WR-03: Runtime allowance/threshold parsing doesn't guard against `bool` masquerading as a positive number

**File:** `operator-claude-plugin/scripts/n8n_cadence.py:416-421` (`_read_positive_float`)
and `operator-claude-plugin/scripts/sweep_conditions.py:464-468`
(`check_burn_rate`'s allowance parse) and `:399-407` (`_parsed_burn_rate_threshold`)
**Issue:** `tests/test_execution_budget_drift.py` explicitly guards the *static* config
artifacts against this exact gotcha: `assert isinstance(value, (int, float)) and not
isinstance(value, bool), ("... a quoted number would compare unequal in a confusing way
rather than an obvious one")`. The runtime parsers that consume the same config keys at
sweep/cadence time do not carry the equivalent guard: `float((config or {}).get(key))` and
`float(execution_budget.get("allowance"))` both happily accept `True`/`False` (Python's
`bool` is an `int` subclass), silently coercing a misconfigured
`"n8n_monthly_execution_allowance": true` into an allowance of `1.0` rather than treating it
as "not configured." The failure direction here happens to be safe (an allowance of 1.0
makes every subsequent cadence change and burn-rate comparison refuse/fire far more
aggressively, never less), so this is not exploitable as a silent bypass — but it produces a
badly misleading notice/refusal ("the 1-execution monthly allowance") for what is actually
an operator typo, and it is inconsistent with a defense the codebase's own drift test proves
the authors were aware of.
**Fix:** Add `and not isinstance(value, bool)` (or an equivalent explicit type check before
the `float()` call) to `_read_positive_float` and to the two ad hoc `float(...)` parses in
`sweep_conditions.py`, so a boolean config value degrades to the same
missing/unusable-config refusal as any other unparseable value, with a message that
actually names the problem.

### WR-04: USAGE.md's "unattended sweep" section still doesn't list the burn-rate alarm among the notices it can raise

**File:** `operator-claude-plugin/USAGE.md:144-157`
**Issue:** Phase 45's own `45-CONTEXT.md` canonical_refs explicitly flagged this file:
"the guide's budget note and admin table were written pre-floor ... and must update it."
The cadence-floor half was updated thoroughly (the "Budget note" paragraphs under
"Starting and stopping things," lines 105-124, are accurate and mention the burn-rate
alarm once in passing as the "Boundary" backstop). But the "## The unattended sweep"
section's own enumerated list of what the sweep can notify about — "a failed run, a dead
credential, an exhausted quota, a stuck lock, a review backlog past its threshold, or
live-write permission left switched on with nothing dispatching" — was not updated to
include the new burn-rate condition, even though it is one of the most consequential new
notices this phase ships (the incident-driving feature, per the CHANGELOG). An operator
reading this list top-to-bottom to understand "what could the sweep tell me" would not
learn that it also watches the execution budget.
**Fix:** Add the burn-rate alarm to the enumerated list, e.g. "...or the n8n execution rate
running high enough to blow through the monthly plan," mirroring the wording already used
in the CHANGELOG and `sweep_conditions.py`'s own reason text.

### WR-05: `plan_action`'s cadence proposal carries the raw override phrase-match, not whether the override was actually exercised

**File:** `operator-claude-plugin/scripts/control_actions.py:220`
**Issue:** `plan_action` sets `"budget_floor_override": override` on the returned proposal,
where `override` is `n8n_cadence.budget_floor_override_taken(request.get(...))` — a pure
phrase match, computed and stored *before* `check_budget_floor` is even called
(`control_actions.py:184-192`). It is **not** derived from
`budget_floor.get("overridden")` (whether `check_budget_floor` actually needed and used the
override — see `n8n_cadence.py:495,509`, which only sets `overridden: True` on the
over-budget path). Consequence: if a request happens to already carry the exact override
phrase while the change is still within budget (e.g. the operator says it pre-emptively,
before ever seeing a refusal — against `SKILL.md`'s documented discipline but not
code-enforced), `proposal["budget_floor_override"]` is `True` even though no refusal was
ever shown. That boolean then flows unmodified into `execute_action` →
`n8n_cadence.set_cadence(..., budget_floor_override=True)`, which re-fetches the schedule
fresh at execute time. If the schedule's real cost has grown over budget by execute time
(e.g. another trigger was changed by someone else between plan and execute), the stored
`True` silently authorizes the over-budget change against whatever the *new* numbers turn
out to be — numbers the operator was never shown, which is exactly what D-10 rule 1 exists
to prevent ("the override is never offered before the numbers are on the table"). No test
in this phase's suite covers "override phrase present while the request is already within
budget" (checked: `test_cadence_budget_floor.py`'s override tests all start from an
over-budget request).
**Fix:** Set `"budget_floor_override": budget_floor.get("overridden", False)` instead of
the raw `override` variable, so the proposal only carries the flag forward when
`check_budget_floor` actually exercised it against the numbers shown in that same
`consequence` message.

---

_Reviewed: 2026-08-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
