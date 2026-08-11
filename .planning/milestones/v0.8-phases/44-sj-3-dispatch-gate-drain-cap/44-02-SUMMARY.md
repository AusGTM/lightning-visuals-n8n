---
phase: 44-sj-3-dispatch-gate-drain-cap
plan: 02
subsystem: crm-automation
tags: [n8n, sj3, dispatch-cap, execution-budget, tick-outcome]
status: complete

requires:
  - phase: 44-sj-3-dispatch-gate-drain-cap
    plan: 01
    provides: the SJ-3 gate/drain cluster (sj3DispatchGate.js, SJ-3 Dispatch Gate fan-out,
      drain branch) this plan expands with the cap and the tick outcome
provides:
  - config/execution_budget.yaml — the single home for the 2,500/month allowance,
    sj3_dispatch_share (0.5) and idle_floor_max_share (0.25); Phase 45's ALARM-03 reads
    monthly_execution_allowance from here (D-11)
  - SJ3_DISPATCH_CAP derived at build time from SJ3_TRIGGER_SCHEDULE (the same tuple the
    trigger is built with) — floor(allowance x share / ticks-per-month) - 1 = 40 at daily
    cadence, baked into the gate node, asserted >= 1 at build (CAP-01)
  - sj3Gate opts.cap + the DEFERRED disposition (sj3_dispatch=false AND sj3_drain=false —
    D-09, the drain never touches overflow) + per-row sj3_tick summary
    {found, permitted, dispatched, declined, deferred, cap, outcome}
  - "SJ-3 Tick Outcome" node — third fan-out consumer of the gate's own output, the one
    node that runs on a fully gate-closed tick; emits gate_closed / capped_partial /
    dispatched plus counts (GATE-02, CAP-02, D-13/D-14)
  - tests/test_execution_budget.py — CAP-03 idle-floor guard over every scheduleTrigger
    in the committed n8n/wf_*_cloud.json
affects: [44-03 (deploy + bounce + live proof of gate + drain + cap together), 45 (ALARM-03 reads the allowance key)]

tech-stack:
  added: []
  patterns:
    - "budget config read at builder import time (the _COMPANY_POLICY_FIELDS shape), with
      the test re-deriving from the YAML rather than importing the builder's constant"
    - "tick-summary stamped on every row so a fan-out consumer can report the gate's
      decision without sitting on a branch whose item count can reach zero"

key-files:
  created:
    - config/execution_budget.yaml
    - tests/test_execution_budget.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/code/sj3DispatchGate.js
    - n8n/wf_scheduled_maintenance_cloud.json (regenerated)
    - tests/n8n/sj3DispatchGate.test.mjs
    - tests/n8n/sjPredicates.test.mjs (knock-on — fan-out pin)
    - tests/test_scaffold.py (knock-on — config YAML count)

decisions:
  - "idle_floor_max_share set to 0.25: current schedule idles at ~95/month (~4%), one
    hourly trigger (720/month = 29%) already fails — any sub-daily re-timing is caught"
  - "invalid opts.cap fails CLOSED (behaves as 0: defer everything permitted) — deferral
    preserves the work and stays visible via outcome=capped_partial; sj3_tick echoes the
    EFFECTIVE cap, not the raw invalid opt"
  - "build asserts SJ3_DISPATCH_CAP >= 1: a sub-daily cadence derives the cap to <= 0
    (15-min: floor(1250/2880)-1 = -1), which would defer everything forever — fail the
    build loudly instead"
  - "the three outcome strings live in SJ-3 Tick Outcome's comment (the node reads the
    gate's computed outcome, never recomputes) — comments are part of jsCode, the same
    convention the drain gate's D-06 negative-grep already relies on"

metrics:
  duration: ~20 min
  completed: 2026-08-10

estimate:
  tokens: 80000
  tasks: 3
actuals:
  tokens: 9324   # chars/4 over the realized diff (37,295 chars across 3 commits)
  tasks: 3
  commits: 3
---

# Phase 44 Plan 02: SJ-3 Dispatch Cap + Tick Outcome Summary

One SJ-3 tick now dispatches at most a build-time-derived cap (40 at the shipped daily
cadence, derived from config/execution_budget.yaml x share / SJ-3's own trigger cadence,
never written), overflow defers with its flag intact for the next tick, and every tick
where the gate ran emits a named non-error outcome with found/permitted/dispatched/
declined/deferred counts — still nothing deployed (44-03 ships gate + drain + cap
together).

## Tasks

| Task | Name | Commit | Result |
| ---- | ---- | ------ | ------ |
| 1 | Derive the dispatch cap from configured budget; overflow defers, never drains | `dd677a8` | YAML + builder derivation + gate module cap/summary + 5 new behavior tests + cap wiring test; baked cap 40, moves to 19 at a 12-hourly cadence (CAP-01 verified) |
| 2 | SJ-3 Tick Outcome — the one node that runs on a fully gate-closed tick | `97ee434` | Third fan-out consumer off the gate's own output; sole-feeder + outcome-vocabulary wiring test |
| 3 | Pin GATE-03 and the shipped schedule's budget floor (CAP-03) | `8e50d85` | Interleaved-dispositions order/mutation pin; idle-floor test computing 95.3/month vs 625 ceiling, naming each trigger |

## What was built

- **`config/execution_budget.yaml`** — headed by the measured incident (253 exec/hour flat
  for 10+ hours, ~182,000/month vs 2,500); `monthly_execution_allowance: 2500`,
  `sj3_dispatch_share: 0.5` (headroom reserved for webhook/operator paths, D-12),
  `idle_floor_max_share: 0.25`. Named readers documented in the file: the builder, the
  CAP-03 test, Phase 45's ALARM-03.
- **Builder** — `_EXECUTION_BUDGET` read at import time with direct indexing (a missing
  key KeyErrors the build, T-44-07); `_TICKS_PER_MONTH` as the executable form of
  `_schedule_trigger`'s documented arithmetic; `SJ3_TRIGGER_SCHEDULE = ("days", 1)`
  consumed by BOTH the trigger call site and the cap derivation, so re-timing moves the
  cap; `SJ3_DISPATCH_CAP = 40` baked into the gate node's jsCode and passed to `sj3Gate`;
  build-time `assert >= 1`; `_schedule_trigger`'s docstring repointed at the YAML so the
  allowance appears in exactly one place.
- **`sj3Gate`** — `opts.cap` counts permitted rows only, in input order; overflow rows
  are DEFERRED (`sj3_dispatch: false`, `sj3_drain: false`) with the D-09 rationale as a
  comment on the deferral branch; every row carries the same `sj3_tick` summary; both
  arithmetic invariants (`found === permitted + declined`,
  `permitted === dispatched + deferred`) asserted in the module.
- **`SJ-3 Tick Outcome`** — fed directly from `SJ-3 Dispatch Gate` (never off a filtered
  branch — zero-items-stops-the-chain), reads `sj3_tick` off its first input, returns one
  item; comments carry the GATE-02 distinguishing-signal reasoning ("search matched
  nothing → this node does not run — its absence IS the signal"), D-14 quiet-not-loud,
  and D-13's ephemeral-half note (~2,500-row prune; durable half is
  `lv_enrichment_status`).
- **`tests/test_execution_budget.py`** — reads every `scheduleTrigger` from the committed
  `n8n/wf_*_cloud.json`, re-derives ticks/month (never imports the builder), sums the
  idle floor (currently 95.3/month across 5 triggers) against
  `allowance x idle_floor_max_share` (625), fails naming each trigger's monthly cost,
  asserts non-vacuity (at least one trigger found), and anchors against the v0.7
  three-sub-daily-triggers incident it exists to catch — a single 15-min trigger
  (2,880/month) fails it.

## Deviations from Plan

**1. [Knock-on tests] `tests/n8n/sjPredicates.test.mjs` fan-out pin widened**
- **Found during:** Task 2 preflight (grep before rebuilding)
- **Issue:** the 44-01 test pins the gate's successors with `deepEqual` on exactly two
  terminals; the tick outcome is a third consumer. File not in `files_modified`.
- **Fix:** pin widened to the three consumers with a comment citing this plan.
  Commit: `97ee434`.

**2. [Knock-on tests] `tests/test_scaffold.py` config-YAML count 8 → 9**
- **Found during:** Task 3 full-suite run
- **Issue:** `test_configs_load` asserts exactly 8 `config/*.yaml`;
  `execution_budget.yaml` is the ninth. File not in `files_modified`.
- **Fix:** count bumped with a comment citing this plan. Commit: `8e50d85`.

No other deviations — regeneration touched only `wf_scheduled_maintenance_cloud.json`
(no nid drift into sibling artifacts this time, unlike 44-01).

## Known Stubs

None.

## Verification

- `node --test tests/n8n/*.test.mjs` — **656 pass** (648 baseline + 8 new), 0 fail.
- `.venv/bin/python -m pytest -q` — **2438 passed** (2437 baseline + 1 new), 121 skipped.
- `operator-claude-plugin` suite — **1286 passed**.
- CAP-01 mechanism verified: the same formula derives 40 at `("days", 1)` and 19 at a
  12-hourly cadence — the cap moves with the trigger, it is not a constant wearing a
  formula.
- `git diff --stat n8n/` per task: regenerated JSON only, no hand edits.
- **Nothing deployed**; live n8n and HubSpot untouched (44-03 owns deploy + bounce).

## Threat register outcomes

| Threat | Disposition |
|--------|-------------|
| T-44-07 (DoS, cap drifting on re-timing) | Mitigated — cap derived from `SJ3_TRIGGER_SCHEDULE` at build; floor independently re-checked from committed artifacts by `test_execution_budget.py` |
| T-44-08 (Repudiation, silent truncation) | Mitigated — `SJ-3 Tick Outcome` emits found vs dispatched vs deferred on every tick the gate ran |
| T-44-09 (Tampering, overflow drained) | Mitigated — deferred rows carry `sj3_drain: false`; pinned by three cap tests |
| T-44-10 (Info disclosure, ephemeral outcome) | Accepted per plan — D-13's two-place design; durable half is `lv_enrichment_status` |

## Commits

- `dd677a8` feat(44-02): derive the SJ-3 dispatch cap from configured budget; overflow defers, never drains
- `97ee434` feat(44-02): SJ-3 Tick Outcome — the one node that runs on a fully gate-closed tick
- `8e50d85` test(44-02): pin gate-open dispatch (GATE-03) and the shipped schedule's budget floor (CAP-03)

## Self-Check: PASSED

All created files present; all three commit hashes found in git log.
