# Roadmap: v0.8 Execution Budget Safety

## Overview

On 2026-08-09 the n8n Cloud backend spent its entire monthly execution allowance (2,500) roughly
73 times over — 253 executions/hour, ~182,000/month — doing work it was structurally incapable
of completing. SJ-3, the `lv_enrichment_requested` poller, fanned out one sub-execution per
flagged record every tick; the step that would have cleared the trigger flag is a HubSpot write,
the write gate was (correctly) closed at rest, so the flag never cleared and the same 61 records
re-dispatched forever. Hand-remediated same day (flags cleared, sub-daily triggers moved to
daily), but the structural hole remains: nothing stops a tick from dispatching work it cannot
finish, nothing drains a stuck flag, nothing bounds a single tick's spend, and nothing reports a
runaway rate before a human reads the billing page. This milestone closes all four. Phase numbers
continue the repo's global sequence — Phase 43 was the last consumed (v0.7) — so this milestone
starts at Phase 44.

## Phases

**Phase Numbering:**

- Continues the repo's global sequence (last consumed: Phase 43). This milestone: Phase 44–45.
- Integer phases (44, 45): Planned milestone work.
- Decimal phases (e.g. 44.1): Reserved for urgent insertions if needed later.

- [x] **Phase 44: SJ-3 Dispatch Gate, Drain & Cap** - The poller refuses to start work the write
  gate can't finish, self-heals the stuck-flag queue instead of accumulating it, and cannot let
  a single tick spend a large share of the monthly allowance (completed 2026-08-10 — live-proven,
  44-LIVE-EVIDENCE.md)

- [ ] **Phase 45: Burn-Rate Alarm** - The sweep detects and reports an execution burn rate that
  would exhaust the plan allowance, without ever fabricating a monthly total

## Phase Details

### Phase 44: SJ-3 Dispatch Gate, Drain & Cap

**Goal**: SJ-3 cannot spend the monthly execution budget on work it cannot complete. A
gate-closed tick dispatches nothing and drains the stuck queue instead of re-accumulating it; a
gate-open tick is unaffected; and no single tick — whatever the cause — can dispatch more than a
budget-derived cap. All three land through `scripts/build_cloud_workflows.py` and deploy in one
build → deploy → bounce, so they ship as a single phase: a half-deployed SJ-3 (e.g. gate check
live, drain not) is worse than either the current runaway or a further delay.
**Depends on**: Nothing (first phase of this milestone)
**Requirements**: GATE-01, GATE-02, GATE-03, DRAIN-01, DRAIN-02, DRAIN-03, CAP-01, CAP-02, CAP-03
**Success Criteria** (what must be TRUE):

  1. A gate-closed SJ-3 tick dispatches zero enrichment sub-executions and costs exactly 1
     execution — never 1 + N. (GATE-01)

  2. That gate-closed tick reports a distinct, named, non-error outcome — not indistinguishable
     from "found nothing to do" or "failed" — because disarmed is the normal resting state, not
     an error condition. (GATE-02)

  3. A test exists and passes proving a gate-open tick's dispatch behavior is unchanged: the gate
     check does not swallow or reorder a single dispatch inside a legitimately armed window.
     (GATE-03)

  4. On a gate-closed tick, SJ-3 clears `lv_enrichment_requested` on every record it declined to
     dispatch, through a write path narrow enough to write only that one flag and nothing else —
     so the queue drains to zero over subsequent ticks instead of accumulating, and a drained
     record stays distinguishable afterward from one that was actually enriched (nothing
     downstream may read the cleared flag as evidence of processing). (DRAIN-01, DRAIN-02,
     DRAIN-03)

  5. A single tick's dispatch count is capped at a value computed inside
     `build_cloud_workflows.py` from the configured plan allowance and the cadence it is baking
     into the trigger — never a hardcoded constant, so the bound can't silently drift when a
     trigger is re-timed. A capped tick always logs how many records it found vs. how many it
     dispatched (silent truncation is forbidden). A test fails if the shipped schedule's computed
     monthly execution floor exceeds a configured share of the plan allowance — the check the
     v0.7 schedule (2.6x over budget doing no work) would have failed. (CAP-01, CAP-02, CAP-03)

**Plans**: 3/3 plans executed

Plans:

- [x] 44-01-PLAN.md — Tracer: SJ-3 dispatch gate + queue drain end-to-end offline (GATE-01, DRAIN-01/02/03)
- [x] 44-02-PLAN.md — Budget-derived dispatch cap + tick outcome (GATE-02/03, CAP-01/02/03)
- [x] 44-03-PLAN.md — One build → deploy → bounce, then live proof of cost bound, outcome and drain

### Phase 45: Burn-Rate Alarm

**UI hint**: no
**Goal**: The sweep reports an unsustainable execution rate before a human notices it on the
billing page — sampling a bounded recent rate, never claiming a monthly total n8n makes
unknowable by construction, and failing loudly rather than silently when it cannot read
execution history. Pure Python, entirely inside `operator-claude-plugin/scripts/` — no n8n
deploy, no bounce, independent blast radius from Phase 44.
**Depends on**: Nothing (pure Python plugin-side sweep condition; no n8n dependency. Sequenced
after Phase 44 by priority — the active runaway fix ships first — not by technical necessity)
**Requirements**: ALARM-01, ALARM-02, ALARM-03, ALARM-04, LOOK-01, FLOOR-01
**Success Criteria** (what must be TRUE):

  1. The sweep fires a notice when a sampled recent execution rate, projected forward at that
     rate over a 30-day month, would exhaust the configured plan allowance. The projection is
     anchor-free — amended 2026-08-10 per 45-CONTEXT.md D-02, because n8n exposes no
     billing-cycle day and an anchored projection would have to invent one. (ALARM-01)

  2. The rate sample is drawn from a bounded recent window, and the notice never states or
     implies a monthly total — n8n prunes execution history (2,500 rows / ~10 hours observed)
     and exposes no usage endpoint to an API key, so a total is unknowable by construction and
     reporting one would be a fabrication. (ALARM-02)

  3. The plan allowance is read from configuration, not a literal; a missing or unreadable
     allowance produces a notice naming the missing key — never silence, never a guessed
     default. (ALARM-03)

  4. If the alarm cannot read execution history, it reports that failure explicitly — inheriting
     the sweep's existing D-15 rule that a check which failed to run must never be
     indistinguishable from a check that found nothing wrong. (ALARM-04)

  5. The sweep's execution lookback is bounded by time rather than by a fixed 100-row page, so a
     failure whose cause was fixed stops being reported once it ages out — while an in-flight run
     is never aged out, because it is current state, not history. (LOOK-01, folded todo
     2026-08-03-sweep-lookback-has-no-time-window)

  6. A runtime cadence change is refused when the resulting schedule's monthly execution floor
     would bust the configured share of the plan allowance, stating the arithmetic first, and
     summing the WHOLE schedule rather than the one trigger being re-timed. (FLOOR-01, folded todo
     2026-08-10-runtime-cadence-has-no-budget-floor)

**Note**: this alarm ships **inert** — no cron/launchd installation is in scope for this phase.
The sweep cron is not installed on this machine (`crontab -l` empty); scheduling it is an admin
action on the operator's machine, stated as an accepted limit, not a gap this phase works around.
Verification is therefore by direct sweep invocation and unit tests against synthetic/fixture
execution history, not by observing a live scheduled fire.

**Plans:** 1/3 plans executed

Plans:

- [x] 45-01-PLAN.md — Time-windowed executions read and the burn-rate alarm (tracer-led): the
  runaway-to-notice path end to end, the branches that must never be silent, and LOOK-01's
  lookback fold

- [ ] 45-02-PLAN.md — Cadence budget floor: whole-schedule monthly cost, a refusal that states
  the arithmetic first, and D-10's single-shot override

- [ ] 45-03-PLAN.md — Drift test pinning the plugin's allowance and floor share to
  config/execution_budget.yaml, plugin release 0.13.0, and requirement closure

## Progress

**Execution Order:**
Phases execute in numeric order: 44 → 45

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 44. SJ-3 Dispatch Gate, Drain & Cap | 2/3 | In Progress|  |
| 45. Burn-Rate Alarm | 1/3 | In Progress|  |
