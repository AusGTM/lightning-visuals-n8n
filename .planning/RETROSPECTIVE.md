# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.4 — Reachability & Verification Debt

**Shipped:** 2026-07-29
**Phases:** 3 | **Plans:** 6 | **Sessions:** 2 (planned + executed in a single day)

### What Was Built
- BUG 23 fix — enrichment `contact:create` structurally reachable (transport swap + dual live canary, write-gated).
- NORM-01 — `_industryText()` stops a bare NAICS code winning the industry waterfall on source trust alone.
- COPY-01/COPY-02 — `lv_sponsorship_reliant` + `lv_persona_group` wired into merge calls AND given live producers (research contract + provider `departments` mapper).
- VERIFY-01 — six-item verification ledger reconstructed and discharged 6/6; BUG 26 (live deployment behind git) surfaced and same-day resolved; armed `company:update` canary passed with disarm read-back.

### What Worked
- **Verifier over reviewer disagreement.** The code reviewer flagged the producer gap as a BLOCKER, the plan had deliberately scoped wiring-only, and the goal-backward verifier ruled `gaps_found` on the phase's own GOAL prose — the gap-closure loop (18-03) then closed it end-to-end same-session. The three-role separation earned its cost.
- **Content-marker probes over name-only diffs.** `compute_workflow_diff` matches on name only; the `_personaGroup`/`_industryText` substring probe caught real deployment drift (BUG 26) that the diff structurally could not.
- **Runbook-as-artifact.** Encoding the `.env`-loading command form and the arm/fire/disarm/read-back ceremony in `19-OPERATOR-RUNBOOK.md` let the operator execute the whole armed window same-day with zero improvisation.
- **Recorded fixtures as red-test substrate.** Every red-before-green test drove real recorded shapes (execution-19 conflict, live Lusha/Apollo payloads) — no synthetic-only proofs.

### What Was Inefficient
- The "six /gsd-verify-work re-runs" ledger was referenced six times across planning docs but never itemized anywhere — Phase 19 spent its research budget reconstructing what one list at deferral time would have preserved.
- Phase 18 needed a gap-closure round that better GOAL-prose vs success-criteria alignment at roadmap authoring would have avoided (criteria said "wired + tested", goal said "stops being empty" — different bars).
- Summary one-liner extraction pulled deviation lines instead of accomplishments for Phase 17 (frontmatter `one_liner` field quality varies by executor).

### Patterns Established
- Bounded frozen-fixture re-baseline (16.3 procedure) now exercised three times — prove the diff bounded BEFORE re-baselining, isolated commit.
- Armed-window ceremony: overlay-only arming (`ENABLE_BAKED_FLAGS` + allowlist), single fire, neighbor check, disarm redeploy, independent read-back of the disarmed literal count.
- Deployment-currency check = content-marker substring probe against live node bodies.

### Key Lessons
- A phase GOAL that makes an outcome claim ("stops being permanently empty") is a stronger contract than its own success criteria — write criteria to match the goal's bar, or expect the verifier to call the difference.
- Deferred-work ledgers must be itemized at deferral time; a count without a list is debt about debt.
- Field *survival* through the whole pipeline (producer → request → response → merge → write) matters more than any single hop; every v0.4 bug lived between hops.

### Cost Observations
- Model mix: opus for planning (2 planner runs), sonnet for research/execute/verify/review (11 agent runs), orchestration inline.
- Sessions: 1 main working session end-to-end (plan 18 → ship v0.4), plus the operator window.
- Notable: entire milestone planned, executed, verified, canaried, and archived within one calendar day (2026-07-29).

## Milestone: v0.8 — Execution Budget Safety

**Shipped:** 2026-08-11
**Phases:** 2 (44, 45) | **Plans:** 6

### What Was Built

A structural fix for a runaway that had already happened. SJ-3 now refuses to dispatch through a
closed write gate, drains the stuck flags it declines rather than re-accumulating them, and caps
one tick's fan-out at a value derived at build time from the plan allowance and the baked trigger
cadence. A sweep condition samples the execution rate over an honestly-observed window and fires
before the allowance is spent, and a cadence budget floor refuses a re-timing that would breach
the configured share.

### What Worked

- **Fixing the class, not the incident.** The 2026-08-09 runaway was hand-remediated the same day
  (flags cleared, triggers moved to daily). This milestone deliberately treated that as insufficient
  and asked what structurally permitted it — producing four independent guards rather than one patch.
- **Deriving the bound from the same source as the thing it bounds.** The cap reads the identical
  schedule tuple that builds the trigger, so a re-timing cannot silently invalidate it. The drift
  test then fails if the shipped schedule's floor exceeds its configured share — the check that
  would have caught v0.7's 2.6x-over-budget schedule before it ran.
- **Adversarial review of the safety mechanism itself.** The code review found the burn-rate alarm
  could fire a false positive on a single extrapolated sample and then misattribute the cause to n8n
  pruning that never happened. An alarm that cries wolf is worse than no alarm; catching that before
  it shipped mattered more than any of the features.

### What Was Inefficient

- **Phase 44 was sealed at plan level without a VERIFICATION.md**, and nobody noticed until the
  milestone close ran `init.manager` and got `verification_status: missing`. The verification was
  written retroactively and passed 5/5 — so no work was wrong, but the gap was invisible for a day
  and would have silently degraded the close to an override.
- **The milestone itself was never closed.** v0.8 sat complete-but-unrecorded, and the close only
  happened because a new milestone was being started. The same omission had already swallowed v0.5
  and half of v0.6's archive.

### Patterns Established

- A safety gate's *closed* state must report as a named non-error outcome. Disarmed is the resting
  state here; reporting it as failure trains the operator to ignore the channel real failures use.
- Where the platform gives no total, measure a rate. n8n prunes at 2,500 rows and exposes no quota
  endpoint to an API key, so a monthly number is unavailable by construction — the design followed
  the constraint instead of fighting it.
- Verify the running artifact, not the generator. Repeatedly this milestone (and in the same-week
  debug work) the built JSON, the deployed workflow, and the repo copy each told a different story.

### Key Lessons

1. **A drain that requires arming cannot drain a queue that only fills while disarmed.** Making
   `ALLOW_SJ3_DRAIN_WRITES` default `true` — the first write authority enabled at rest — was the
   non-obvious call that made the whole mechanism work, bounded by a key+value patch allowlist.
2. **Run the milestone close when the milestone ends, not when the next one starts.** Two of the
   last four milestones lost ledger entries to this.

### Cost Observations

- Model mix: sonnet for execute/verify/review agents; orchestration inline.
- Notable: Phase 44's live proof needed an operator-fired manual tick — n8n has no run-now API for
  schedule triggers (405) and the natural tick was ~21h out. Recorded honestly rather than implied
  as a scheduled firing.

## Cross-Milestone Trends

| Milestone | Phases | Plans | Notable |
|-----------|--------|-------|---------|
| v0.3 Company Enrichment & ICP Research | 16 (10 inserted) | 22 | First live HubSpot writes; 25 numbered bugs; non-clobber live-proven |
| v0.4 Reachability & Verification Debt | 3 | 6 | Debt-clearance only; 6/6 ledger; single-day ship; zero residual operator debt |
| v0.7 HubSpot Scoring Engine Remediation | 5 (39–43) | 23 | Split-brain rubric found; 10 defects fixed in place; parity harness built |
| v0.8 Execution Budget Safety | 2 (44–45) | 6 | Structural fix for a live runaway; cap derived not hardcoded; alarm's own false-positive caught in review |
