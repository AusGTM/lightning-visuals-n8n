---
phase: 54-single-pass-armed-dispatch
plan: 01
subsystem: infra
tags: [n8n, hubspot, cost-measurement, write-grant]

requires: []
provides:
  - "measure_dispatch.py — a read-only module counting real n8n executions for one record out of live execution history"
  - "54-MEASUREMENT.md — G-3's saving traced to real execution ids, with the single-record case measured (and DIFFERING from envelope()'s projection) and the multi-chunk case named as still open"
  - "write_grant.envelope()'s anthropic_usd basis relabelled PROJECTED (was falsely MEASURED)"
  - "WINDOWS.md entry 27 — the SJ-3 scheduled-poller double pass, recorded per OP-54-02"
affects: [54-02, 54-03, 54-04, 54-05]

actuals:
  tokens: 7384
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "measure_dispatch.py mirrors scheduled_arm.find_latest_sj3_batch's list+filter+sort shape for a new read-only client caller"
    - "basis tri-state (measured/projected/unconfigured) extended to a figure that was previously mislabelled, rather than adding a fourth word"

key-files:
  created:
    - operator-claude-plugin/scripts/measure_dispatch.py
    - operator-claude-plugin/tests/test_measure_dispatch.py
    - .planning/phases/54-single-pass-armed-dispatch/54-MEASUREMENT.md
  modified:
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_write_grant.py
    - .planning/WINDOWS.md

key-decisions:
  - "The AFTER measurement is isolated to execution 11960 alone (a bare single-object dispatch) rather than averaged across all three executions that touched contact 347569451461 on 2026-08-25/26 — 11956 and 11960 write disjoint property sets from two separate deploys/asks, and 11958 is a genuinely refused send in between, not a repeat pass of the same ask."
  - "envelope()'s projected_executions formula was checked against 11960 and DIFFERS from the measurement (measured 1, projected 2) — reported as a finding, not silently reconciled; Task 3 relabels the basis map only, it does not correct the formula (out of this plan's scope)."
  - "Provider credits reported unmeasured, not measured or zero — no balance snapshot exists bracketing either send, and a live read taken now would not be attributable to a past send."
  - "WINDOWS.md entry 26 narrowed (not closed): the single-chunk case is now measured; the multi-chunk case — id 26's actual original complaint — stays open."

requirements-completed: [G-3]

coverage:
  - id: D1
    description: "measure_dispatch.py counts real n8n executions for one record from live execution history, read-only, never importing the arming module"
    requirement: G-3
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_measure_dispatch.py (9 tests, all offline via a fake transport)"
        status: pass
    human_judgment: false
  - id: D2
    description: "G-3's saving traced to real n8n execution ids (11934/11935/11937 pre-F2, 11956/11958/11960 post-fix), with the single-record verdict computed against envelope()'s own projection formula"
    requirement: G-3
    verification:
      - kind: integration
        ref: ".planning/phases/54-single-pass-armed-dispatch/54-MEASUREMENT.md — live reads performed and recorded this session"
        status: pass
    human_judgment: true
    rationale: "The measurement's correctness rests on reading and interpreting real n8n execution payloads (which executions belong to which operator ask) — a judgment call best sanity-checked by the operator against their own memory of the 2026-08-25/26 walk, not something a unit test can assert."
  - id: D3
    description: "write_grant.envelope()'s anthropic_usd basis relabelled PROJECTED instead of the previously false MEASURED"
    requirement: G-3
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_anthropic_figure_is_labelled_projected_never_measured"
        status: pass
    human_judgment: false
  - id: D4
    description: "SJ-3 scheduled-poller double pass recorded on the ledger (WINDOWS.md entry 27, OP-54-02) as a deliberate, unfixed residual"
    verification:
      - kind: other
        ref: "python3 -c JSON-parse + uniqueness check on .planning/WINDOWS.md (run this session, entry 27 present, status open)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-27
status: complete
---

# Phase 54 Plan 01: Measure G-3's saving out of live execution history Summary

**Read the real execution cost of one record out of live n8n history (1 execution for a single-record post-fix send, vs. 3 for the pre-F2 double/triple-blocked pass), found that `envelope()`'s own execution-count formula DIFFERS from that measurement, relabelled the Anthropic dollar figure from a false MEASURED to PROJECTED, and put the SJ-3 scheduled-poller's still-open double pass on the ledger.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3 completed
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments

- Built `measure_dispatch.py`, a read-only module that counts n8n executions for one record out of live history via `executions_client.list_executions`/`get_execution` only — never imports the arming module, never arms or dispatches (T-54-01, grep-pinned).
- Ran it against real n8n history: read executions `11934`/`11935`/`11937` directly (the pre-F2 triple-refused pass on contact `347569451461`, all correctly matched, all `write_blocked`) and `11956`/`11958`/`11960` (the post-fix window, where `11960` isolates one bare-object dispatch to exactly one measured execution).
- Compared that measurement against `write_grant.envelope()`'s own `projected_executions` formula for the same record set — the formula projects 2 executions (`chunk_count=1 + record_count=1`), the real count was 1. Recorded as a genuine `differs` verdict, not smoothed away.
- Relabelled `envelope()`'s `anthropic_usd` basis from `MEASURED` to `PROJECTED` (TDD: failing test first, then the code change) — no code path in this repo reads back real Anthropic usage, so this figure was never a measurement (OP-54-05).
- Appended WINDOWS.md entry 27: the SJ-3 scheduled-poller companion's double pass, architecturally the same shape as G-3 but deliberately left unfixed per operator ruling OP-54-02 (out of this milestone's headless-path scope, D-1.1-01). Narrowed entry 26 to reflect what Task 2 actually measured (single-chunk case) vs. what remains open (multi-chunk case).

## Task Commits

1. **Task 1: End-to-end "count the executions one record actually cost"** - `e379cce` (feat)
2. **Task 2: Read the real counts out of history and write the measurement report** - `815edba` (docs)
3. **Task 3: Stop labelling the Anthropic figure MEASURED, and put the SJ-3 residual on the ledger** - `f0f1ef1` (test, RED) → `9990d2f` (feat, GREEN) → `ace8838` (docs, WINDOWS.md)

_Task 3 is `tdd="true"`: the RED commit adds a failing test asserting the new basis word; the GREEN commit flips the constant and the `_envelope_block` wording; the WINDOWS.md update is a separate `docs` commit since it is not test-driven._

## Files Created/Modified

- `operator-claude-plugin/scripts/measure_dispatch.py` - read-only execution counter (`executions_in_window`, `passes_for_record`, `compare_to_projection`, a `__main__` CLI)
- `operator-claude-plugin/tests/test_measure_dispatch.py` - 9 offline tests (fake transport, no socket)
- `.planning/phases/54-single-pass-armed-dispatch/54-MEASUREMENT.md` - the measured saving, execution-id-traceable, with basis words on every figure
- `operator-claude-plugin/scripts/write_grant.py` - `anthropic_usd` basis relabelled `PROJECTED`; `_envelope_block`'s Anthropic line now states it is a floor from the dated rate table
- `operator-claude-plugin/tests/test_write_grant.py` - new pin: `test_the_anthropic_figure_is_labelled_projected_never_measured`
- `.planning/WINDOWS.md` - entry 27 (SJ-3 residual, OP-54-02); entry 26 narrowed per the measurement's verdict

## Decisions Made

- **Isolated the AFTER measurement to execution 11960 alone.** Reading history for contact `347569451461` on 2026-08-25/26 found three executions touching it: `11956` (writes `jobtitle`/`phone`/`mobilephone`/`seniority`), `11958` (`write_blocked`, a genuine refusal), `11960` (writes `email`/`firstname`/`lastname`/`city`/`country`). `11956` predates the permissive-contact-lane location-fields deploy and `11960` postdates it — these are two separate operator asks roughly six hours apart, not three passes of one ask. The single-record, single-ask, post-fix measurement is the narrow window around `11960` alone, whose own `Parse HubSpot Event` output confirms a bare single-object dispatch.
- **Reported the projection/measurement disagreement rather than reconciling it.** `envelope()`'s formula (`chunk_count + record_count`) projects 2 executions for a 1-record send; the measured count for `11960` is 1. This plan's scope is measuring and relabelling, not correcting the formula — the discrepancy is recorded in 54-MEASUREMENT.md as the first real data point for whoever revisits `write_grant.py:120-126`'s "+1 sub-execution per record" assumption.
- **Provider credits: unmeasured, not zero.** No balance snapshot exists bracketing either the BEFORE or AFTER send, so this task does not report a delta it cannot support — reading a balance now would not be attributable to a specific past send.
- **WINDOWS id 26 narrowed, not closed.** The single-chunk (`chunk_count==1`) case is now measured; id 26's actual original complaint — a multi-chunk grant, never counted end to end — stays genuinely open, because this plan's 0-new-execution budget named no multi-chunk send in reachable history.

## Deviations from Plan

None — plan executed exactly as written. The BEFORE and AFTER execution history both existed and were readable (no `Task 2 stops and says so` branch was needed); Task 3 found no existing test pinning `anthropic_usd`'s basis to `MEASURED` (confirmed by grep before editing), so no re-pointing branch applied — only a new test was added.

## Issues Encountered

None requiring problem-solving beyond the live-history investigation itself (identifying which of the three post-fix executions represented the single-record, single-ask case — resolved by reading each execution's `Decide Action`/`Parse HubSpot Event` output directly, documented in 54-MEASUREMENT.md).

`gsd-tools requirements mark-complete G-3` reported `not_found`: `G-3` is this milestone's raw UAT gap id, referenced narratively in `.planning/milestones/v1.1-REQUIREMENTS.md` but not itself a checkbox item there — the checkable items built to close it are `GRANT-01..06`, none of which this plan's tasks target. Not marked; not force-added, since inventing a checkbox this plan does not itself close would misreport progress on a requirement this plan only measures, not completes.

## User Setup Required

None — no external service configuration required. All live reads used the existing durable `operator.local.json` config (`n8n_url`/`n8n_api_key`), already configured.

## Next Phase Readiness

`write_grant.envelope()`'s basis map is now honest end to end (`record_count`/`provider_credits` measured, `projected_executions`/`anthropic_usd` projected, `monthly_execution_allowance` measured-or-unconfigured). The SJ-3 residual is on the ledger for whoever picks it up later. Plans 54-02 through 54-05 (contact review-flag clearing, propose/ambiguous-match cost disclosure) are unblocked by this plan and do not depend on anything it changed beyond the basis map.

---
*Phase: 54-single-pass-armed-dispatch*
*Completed: 2026-08-27*

## Self-Check: PASSED

All 4 created/output files found on disk; all 5 task/gate commit hashes (`e379cce`,
`815edba`, `f0f1ef1`, `9990d2f`, `ace8838`) found in `git log --oneline --all`.
