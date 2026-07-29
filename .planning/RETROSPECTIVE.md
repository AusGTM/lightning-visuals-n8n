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

## Cross-Milestone Trends

| Milestone | Phases | Plans | Notable |
|-----------|--------|-------|---------|
| v0.3 Company Enrichment & ICP Research | 16 (10 inserted) | 22 | First live HubSpot writes; 25 numbered bugs; non-clobber live-proven |
| v0.4 Reachability & Verification Debt | 3 | 6 | Debt-clearance only; 6/6 ledger; single-day ship; zero residual operator debt |
