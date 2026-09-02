---
phase: 29-notices-unattended-sweep
plan: 04
subsystem: operator-claude-plugin
tags: [watch, poll-loop, cost-delta, no-third-outcome, D-05, D-07, D-12, unknown-is-not-zero]
requires:
  - report.build_contact_report / report.SETTLED_STATUSES (26-01)
  - report_enrichment.build_enrichment_report / remaining_credits_from_response (26-02)
  - executions_client.get_execution / find_execution_for_dispatch (26-01, D-12's fallible handle)
  - cost_guard.fetch_balances (Phase 25's pre-dispatch balance read)
  - 29-TIMING.md (the MEASURED 600s bound and the 45 s/record headroom rate)
  - 29-HOST-PROBE.md A2 (unprompted follow-up recorded NO)
provides:
  - watch.py — poll_until_settled, resolve_bound_seconds, build_settled_report,
    build_still_running_report, compute_cost_delta, bonus_delivery_available
  - config/operator.local.example.json watch_bound_seconds = 600
affects:
  - 29-06 (the skill body that calls watch.watch() after a dispatch)
tech-stack:
  added: []
  patterns: [injected-clock-poll-loop, two-terminal-outcomes, unknown-propagates-through-a-delta]
key-files:
  created:
    - operator-claude-plugin/scripts/watch.py
    - operator-claude-plugin/tests/test_watch_bound_fallback.py
    - operator-claude-plugin/tests/test_watch_settle_reporting.py
  modified:
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/tests/test_report_sufficiency.py
decisions:
  - "watch.py allowlisted as the ONE exception to test_report_sufficiency.py's D-07 no-poll-loop guard, which predates this plan and would otherwise fail on the module D-07 named for exactly this loop"
  - "the settled report renders through the lane-matched Phase 26 renderer (report_enrichment for enrichment, report.py for contact_upload) rather than a third convention; cost delta only applies to the enrichment lane, since contact-upload burns no provider credits"
  - "the unprompted-delivery bonus (29-HOST-PROBE A2 = NO) changes only a delivery_mode label; build_settled_report is provably identical with the capability on or off"
metrics:
  duration: ~50 min
  completed: 2026-08-03
  actuals:
    tokens: 21000
    tasks: 2
    commits: 2
status: complete
---

# Phase 29 Plan 04: The Bounded In-Session Watch — Summary

`watch.py`: a poll loop that always ends in one of exactly two reports — settled or
still-running — never nothing, bounded by the measured 600s default from 29-TIMING.md,
with the settled path adding the cost actually incurred on top of Phase 26's own
per-record renderer.

## What was built

**Task 1 — the poll loop and the bound (D-05, D-06, D-07, D-12, NOTICE-02).**
`poll_until_settled(read_once, bound_seconds, run_handle, *, now, sleep)` is a pure
function of an injected clock and reader: `now()`/`sleep()` let a test drive the bound
boundary from both sides with a `FakeClock` that only advances when the loop itself calls
`sleep`, so no test ever sleeps for real. Exactly two `return` statements in the whole
function, each producing a full report via `build_settled_report` /
`build_still_running_report` — "returns nothing" is not a reachable branch, it's simply
absent from the code. Backoff widens `(5, 5, 10, 15, 30, 60)` seconds: fast enough to
catch the measured 32-39s single-record run in one or two polls, capped at 60s because
n8n Cloud's own webhook ceiling is ~100s (26-CONTEXT D-13) and slower polling would feel
laggy on an otherwise-fast settle.

`resolve_bound_seconds(config, record_count=None)` reads `watch_bound_seconds` from
config, falling back to the measured `600.0` (29-TIMING.md) on absence or an unparseable/
non-positive value, and scales up (never down) via `max(bound, record_count * 45)` for a
known multi-record dispatch per that doc's headroom rate. Added `watch_bound_seconds:
600` to `operator.local.example.json` with the full measurement provenance in its
`_note` field, matching the file's existing style.

The still-running report always carries the run handle plus a `correlation_basis` string
stating plainly that the match is by timing, not an execution id the backend returned
(26-CONTEXT D-12) — a wrong correlation is visible in the report text rather than
asserted with false confidence.

**Task 2 — the settled report (NOTICE-01, D-10/D-10a/D-10b/D-14).**
`build_settled_report` renders through Phase 26's own renderer, selected by which lane
was dispatched — `report_enrichment.build_enrichment_report` for enrichment,
`report.build_contact_report` for contact-upload — never a third rendering convention.
Every discipline those renderers already hold arrives for free: no ICP field or
placeholder anywhere (D-10a/D-10b, inherited from `report_enrichment`), and a no-email
row is described as needing an email rather than as retryable (D-14, inherited from
`report.py`'s existing `classify_retryability`).

The cost block is new: `compute_cost_delta(pre_balances, post_balances)` normalizes
either balance shape (`cost_guard.fetch_balances`'s `{credits, unreadable}` or
`report_enrichment.remaining_credits_from_response`'s `{provider: number|"unknown"}`)
into `{provider: credits_or_None}`, then computes pre-minus-post per provider. If either
end is unreadable the delta is `unknown` (never a difference against a substituted
zero — the direction that understates spend). The report states `"partial"` when some
providers resolved and some didn't, rather than silently reporting a smaller total.
Falls back to a fresh `cost_guard.fetch_balances` read only when the enrichment
response itself carried no credits block at all — an empty dict, never overriding an
already-meaningful `unknown`. Token usage reads defensively from `Build Response`'s own
output and is `"unknown"` today (no deployed node emits one yet) — read that way on
purpose so a future node adding one needs no code change here.

The bonus delivery layer (29-HOST-PROBE.md A2 recorded NO) is `bonus_delivery_available
(config)`, a single-line verdict with a config override for a future re-probe. It
changes only the report's `delivery_mode` label; a test proves the rest of the report is
byte-identical whether the capability is on or off.

## Deviations from Plan

**1. [Rule 3 — blocking issue] `test_report_sufficiency.py`'s D-07 no-poll-loop guard
predates this plan and fails on exactly the module D-07 named as the intended exception**

- **Found during:** the full-suite verification step after Task 2.
- **Issue:** Phase 26 shipped an AST guard asserting no plugin script imports
  `time`/`sched`, calls `sleep()`, or contains a `while` loop — a structural promise that
  "this phase never grows a watch." `watch.py` legitimately needs all three.
- **Fix:** added a one-line, named allowlist (`_POLL_LOOP_ALLOWED = {"watch.py"}`)
  excluding only that file from the scan, with a docstring note explaining it's the
  deliberate exception D-07 always pointed at — mirrors the existing allowlist idiom
  `test_sweep_read_only.py` and `test_retry_reuses_dispatch.py` already use for their own
  named exceptions.
- **Files:** `operator-claude-plugin/tests/test_report_sufficiency.py`
- **Commit:** `ce7a8c1`

No other deviations. Both tasks' acceptance criteria passed on first run of their own
test files; the guard fix above was the only cross-plan friction.

## Test counts

| Suite | Before this plan | After | Attribution |
|---|---|---|---|
| plugin (`operator-claude-plugin/`) | 811 | **859 passed, 5 skipped** | +16 (`test_watch_bound_fallback.py`) + 12 (`test_watch_settle_reporting.py`) = 28 mine; some additional count beyond 811+28 belongs to the concurrent 29-05 executor's work landing in the same window |
| pytest (repo root) | 1686 | **1740 passed, 6 skipped** | mine plus 29-05's concurrent commits, both included in this run |
| node (`tests/n8n/*.test.mjs`) | 506 (per 29-03) | **550 passed** | not mine — I touched no node code; belongs to sibling plans landing concurrently |

## Self-Check: PASSED

- `operator-claude-plugin/scripts/watch.py` — FOUND
- `operator-claude-plugin/tests/test_watch_bound_fallback.py` — FOUND
- `operator-claude-plugin/tests/test_watch_settle_reporting.py` — FOUND
- `operator-claude-plugin/config/operator.local.example.json` contains `watch_bound_seconds: 600` — FOUND
- Commits `c823c10`, `ce7a8c1` — both FOUND in `git log`
