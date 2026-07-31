---
phase: 29-notices-unattended-sweep
plan: 02
subsystem: operator-plugin-tests + admin-measurement
tags: [fixtures, timing, read-only, unknown-is-not-zero]
requires:
  - Phase 27's n8n_read.summarize_execution (the tri-state stuck verdict, D-14)
  - scripts/enrichment_cost_ledger.py's _list_executions/_get_execution read helpers
provides:
  - sweep fixtures for 29-03/04/05 (10 fixtures + sweep_now + execution_unreadable_start)
  - scripts/enrichment_cost_ledger.py durations subcommand
  - 29-TIMING.md — the MEASURED watch bound and the 45 s/record headroom rate
affects:
  - 29-04 (ships watch_bound_seconds = 600)
  - 29-05 (D-08b false-success detection, is_quota_exhausted)
  - 25-CONTEXT D-11a (chunk sizing reads the same rate)
tech-stack:
  added: []
  patterns: [unknown-is-never-zero, fixed-reference-time-fixtures, read-only-by-construction]
key-files:
  created:
    - operator-claude-plugin/tests/test_sweep_fixtures.py
    - .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-TIMING.md
  modified:
    - operator-claude-plugin/tests/conftest.py
    - scripts/enrichment_cost_ledger.py
    - tests/test_enrichment_cost_ledger.py
    - .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-CONTEXT.md
decisions:
  - "D-22 folded into 29-CONTEXT: the deployed endpoint's three provider states are numeric / unknown / absent-from-balances — NOT the {configured: bool} shape 29-RESEARCH claimed"
  - "D-23 folded into 29-CONTEXT: the executions collection carries no workflowData on this tenant; filter by workflow name only via the workflow collection"
  - "watch_bound_seconds = 600 (10 min), scaling as max(600, records * 45) — measured, not guessed"
metrics:
  duration: ~35 min
  completed: 2026-07-31
status: complete
---

# Phase 29 Plan 02: Sweep Fixtures + The Measured Watch Bound — Summary

Sweep fixtures covering every payload shape 29-03/04/05 must reason about (including the two
that look healthy and are not), a `durations` subcommand computing per-record enrichment
timing from data the ledger already fetched, and a **genuinely measured** watch bound of
600 s recorded in `29-TIMING.md`.

## What was built

**Task 1 — fixtures (`operator-claude-plugin/tests/conftest.py`, +14 tests).**
Ten fixtures plus `sweep_now` and `execution_unreadable_start`. Execution fixtures mirror the
real `/api/v1/executions` keys (`id`, `workflowId`, `status`, `startedAt`, `stoppedAt`,
`finished`, `workflowData.name`) and are anchored to a fixed `SWEEP_NOW`, passed into
`n8n_read.summarize_execution(..., now=)` — no fixture drifts across the stuck threshold
depending on when the suite runs. The two deceptive shapes:

- `execution_maintenance_falsely_successful` — run status `success` on the maintenance
  workflow while `SJ-1 Search (input-gap scan)` carries an error and zero rows. Keyed on the
  **five deployed node names verbatim (D-21)**, which I re-read out of
  `n8n/wf_scheduled_maintenance_cloud.json` and confirmed unchanged, all five still
  `onError: continueRegularOutput`.
- `backend_status_unknown_balance` — `credits: None`, `unreadable: true`, credential health
  `refused`. Distinct from `backend_status_exhausted` (an explicit `0`) and from
  `backend_status_unconfigured_provider` (absent from `balances` entirely).

The stuck tri-state is exercised on all three sides: past-threshold (`True`),
within-threshold (`False`), and unreadable `startedAt` (`None`, per 27 D-07b(i)). The plan's
`read_first` was right that `is_stuck()` does not exist — everything is built against the
shipped `stuck_threshold_minutes()` + `summarize_execution()`.

**Task 2 — duration computation (`scripts/enrichment_cost_ledger.py`, +13 tests).**
`execution_duration_seconds()`, `execution_record_count()`, `summarize_durations()`,
`print_durations()`, `collect_durations()` and a `durations` subcommand. Reuses
`_list_executions()` and `_get_execution()`; **no new HTTP path, no write path** — T-29-04
preserved. Unknown-is-never-zero throughout: an absent `stoppedAt` yields `None`, an absent
write node yields `None`, and a write node that ran and wrote nothing yields a genuine `0`
that is excluded from the rate rather than counted as an infinitely fast record. The summary
reports `sample_size` and counts unknowns separately, so a bound from 2 executions cannot be
quoted as if it came from 50.

**Task 3 — the measurement (`29-TIMING.md`).** Run through the dotenv wrapper verbatim (D-20).

## The measurement: MEASURED, not provisional

**Credentials were present and the read succeeded.** 5 enrichment-workflow executions,
durations 32.1–38.9 s, 35.6–36.1 s/record on the 2 that carry a recoverable record count.

| Number | Value |
|---|---|
| Observed max single-run duration | 38.9 s (n=5) |
| Observed max s/record | 36.1 s (n=2) |
| Headroom rate — **what Phase 25 D-11a consumes** | **45 s/record** |
| `watch_bound_seconds` — **what 29-04 ships** | **600 s**, scaling `max(600, records * 45)` |

One caveat is labelled as such in the file rather than buried: all five runs are
**single-record company-lane** runs, so linearity at N > 1 is extrapolated (conservatively —
it over-estimates duration, lengthening the bound). Re-measure trigger: the first 10
executions carrying more than one record.

Falls out for Phase 25: at 45 s/record against the ~100 s Cloudflare ceiling,
`max_records_per_chunk` is **2**.

## Deviations from Plan

**1. [Rule 1 — Bug] `collect_durations()` filtered on a field this tenant never populates**

- **Found during:** Task 3, on the first live run — the enrichment filter returned an empty
  table while the unfiltered run showed 50 executions.
- **Issue:** every item in `/api/v1/executions` has no `workflowData` on this tenant, so
  `workflowData.name` is `None` and a name filter matches nothing. The empty table reads
  exactly like "no executions to measure" — **the D-20 failure mode in a second guise**, and
  it would have produced a provisional bound while 5 measurable executions sat in the page.
- **Fix:** resolve `workflowId → name` through `_get_live_workflows()`, exactly as the
  ledger's existing `list` mode already does. Plus a regression test.
- **Files:** `scripts/enrichment_cost_ledger.py`, `tests/test_enrichment_cost_ledger.py`
- **Commit:** `651e139`

**2. [Rule 2 — Missing correctness constraint] The backend-status provider shape in
29-RESEARCH is wrong; fixtures were built to the deployed one**

- **Found during:** Task 1, reading `scripts/build_cloud_workflows.py:4453` and
  `n8n/code/backendStatus.js:37` before writing the fixtures.
- **Issue:** 29-RESEARCH Pitfall 5 states the endpoint returns
  `{configured: bool, credits: int|None}` per provider. It does not. `Build Credit Status`
  maps over the **requested** providers with `configured` hardcoded `true`; a `configured:
  false` balances row does not exist in production. The genuinely-unconfigured provider shows
  up only in `credential_health` as `{state: "unknown", reason: "not_configured"}`.
- **Fix:** fixtures built to the deployed shape, and the correction folded into 29-CONTEXT as
  **D-22** — including the consequence for 29-05 (`is_quota_exhausted` must read
  `credential_health` for state 3, or that state is invisible) and the note that the sweep
  must consume `fetch_backend_status()`'s raw `data`, since `render_backend_status` discards
  `unreadable`/`error`/`configured`.
- Pitfall 5's substance is unchanged — unknown must never fire the exhausted notice.
- **Files:** `29-CONTEXT.md` (D-22), `operator-claude-plugin/tests/conftest.py`
- **Commit:** `0937b05` (fixtures), CONTEXT in the docs commit

**3. [Rule 2] `execution_unreadable_start` added beyond the plan's fixture list** — the plan's
`read_first` requires the `stuck: None` case be reachable, and
`execution_missing_stopped_at` (valid `startedAt`, absent `stoppedAt`) yields `stuck: True`,
not `None`. One extra fixture, rather than muddying the duration-unknown one.

D-23 was also folded into 29-CONTEXT (the `workflowData` finding above), so any later code
filtering executions by workflow name does not rediscover it.

## Test counts

| Suite | Before | After | Attribution |
|---|---|---|---|
| pytest (repo root) | 1165 passed, 1 skipped | **1192 passed, 1 skipped** | +27 mine (14 fixture guards, 13 ledger) |
| plugin (`operator-claude-plugin/`) | 400 | **414** | +14 mine (the fixture guards, counted twice — they live in the plugin suite and the root run collects it) |
| node (`tests/n8n/*.test.mjs`) | 408 | **420** | **+12 NOT mine** — sibling 30-02 commits `224561e` / `9470f03` (reviewDecision.js module tests). I touched no node code. |

`grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0** across every artifact.

## What 29-03 needs from these fixtures

- **`executions_healthy` + `sweep_now`** — the no-notice baseline. Every condition must be
  silent against it; a condition that fires here is noisy by construction.
- **`executions_with_stuck`** — contains both sides of the threshold, so a stuck condition
  that flags every running execution fails rather than passes. Always pass `now=sweep_now`.
- **`execution_unreadable_start`** — the `stuck: None` case. A condition treating `None` as
  `False` reports a possibly-wedged run as fine; treating it as `True` cries wolf. It needs
  its own third branch.
- **`execution_maintenance_falsely_successful`** — the D-08b case. Its `runData` is keyed on
  the five deployed node names, exported as `conftest.MAINTENANCE_SEARCH_NODES`; import that
  constant rather than re-typing the names, and walk `data.main[0]` the way the repo already
  does. A "failed scheduled run" condition reading `execution.status` alone passes every other
  fixture and misses this one — which is the point.
- **The three backend-status provider fixtures** — read D-22 first. The exhausted condition
  may fire **only** on `backend_status_exhausted`'s explicit numeric floor. Both
  `backend_status_unknown_balance` and `backend_status_unconfigured_provider` must route
  elsewhere, and they are two different elsewheres.
- **`backend_status_review_backlog`** — everything else in it is healthy, so a notice firing
  against it is attributable to the backlog alone.

## Not done / carried forward

- **No test pins `MAINTENANCE_SEARCH_NODES` against `n8n/wf_scheduled_maintenance_cloud.json`.**
  The plugin suite is deliberately free of repo-root dependencies (PLUGIN-04's no-backend-import
  guard is about imports, but reading the backend's JSON from a plugin test is the same smell).
  I verified the five names against the deployed JSON by hand this session. A repo-side pin —
  the way `tests/test_enrichment_cost_ledger.py` pins the four Anthropic node names — would
  belong in a repo-root test file, which is outside this plan's `files_modified`. **Worth
  adding in 29-05**, which owns the detection code those names feed.
- `collect_durations()` issues one `_get_execution()` per matched execution. Bounded by
  `--limit` and read-only, but it is N+1 by construction; fine for an occasional admin
  measurement, not for a poll loop.

## Self-Check: PASSED

- `operator-claude-plugin/tests/test_sweep_fixtures.py` — FOUND
- `.planning/.../29-notices-unattended-sweep/29-TIMING.md` — FOUND
- Commits `ac333af`, `0937b05`, `0e7e527`, `bd6b1ca`, `651e139` — all FOUND in `git log`
