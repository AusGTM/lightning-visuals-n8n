---
phase: 49-re-score-strategy-reporting
plan: 05
subsystem: infra
tags: [hubspot, icp-scoring, batch-write, calculation_equation, workflow-enrollment]

requires:
  - phase: 49-01
    provides: "scripts/rescore_population.py — the W1 driver (plan/canary/execute/snapshot modes)"
  - phase: 49-02
    provides: "the runbook (docs/OPERATOR-RESCORE.md) and the pre-registered id-set capture (49-PLAN-OUTPUT.json)"
  - phase: 46
    provides: "the rubric weight change (commit caae5d6) that opened the parity red window and the pre-registered 14-row C->B simulation forecast"
provides:
  - "The full-population weight re-score, W1, run exactly once (canary + remainder in one window)"
  - "P2/P3 census snapshots proving the observed movement matched the pre-registered forecast"
  - "A committed parity verdict recording the true, undoctored post-re-score state (4 real findings, disclosed and diagnosed, not suppressed)"
  - "4 unmet-truth entries in WINDOWS.md (ids 9-12) naming the stuck-tier records and pointing at their scoped fix"
  - "TIER-DERIVATION-SPIKE-2026-08-13.md — grammar proof that lv_icp_tier can become a calculation_equation property, scoped as future Phase 50 work"
affects: [phase-50-tier-derivation, hubspot-icp-scoring-workflows]

actuals:
  tokens: 30000
  tasks: 1
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Component-only batch PATCH (five *_score properties) as the sole W1 write surface; lv_icp_fit_score/lv_icp_tier/lv_anti_icp_flag/lv_anti_icp_reason are always derived, never PATCHed directly"
    - "unmet-truth WINDOWS.md entries as the durable record for a diagnosed-but-not-fixed live-data divergence, pointing at the scoped future fix rather than the phase that found it"

key-files:
  created:
    - .planning/phases/49-re-score-strategy-reporting/49-P3-SNAPSHOT.json
    - .planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json
  modified:
    - .planning/phases/49-re-score-strategy-reporting/49-W1-ARM-RECORD.md
    - .planning/WINDOWS.md
    - .planning/STATE.md

key-decisions:
  - "Operator resolved the Task 3 checkpoint as ACCEPT AND DISCLOSE: the 4 stuck-tier records are logged, diagnosed, and pointed at a scoped future fix rather than force-corrected through a prohibited mechanism (no lv_icp_tier PATCH, no n8n allowlist arm, no blank-then-rewrite)."
  - "The parity verdict is committed RED (4 real findings) on purpose. scripts/run_scoring_parity.py was not edited (git diff confirms) and the plan's own <verify> for this task is expected to exit non-zero — recorded here as an accepted, disclosed outcome, not a silent failure."
  - "The durable fix (lv_icp_tier as a calculation_equation, removing WF1's enrollment-event dependency) is deliberately deferred to a future phase (tentatively Phase 50) because it requires a new HubSpot property, which v0.9's REQUIREMENTS.md Out of Scope forbids by the 2026-08-11 operator decision."

patterns-established:
  - "A same-value HubSpot batch PATCH is a true no-op: no hs_lastmodifieddate bump, no workflow-enrollment event, even with shouldReEnroll: true. A component-only write mechanism cannot reach a record whose components are already correct but whose derived tier is stale."

requirements-completed: [RESCORE-02, RESCORE-03]

coverage:
  - id: D1
    description: "Full live-derived population (66 companies) re-scored under the current rubric via one W1 window (canary + remainder); 66/66 component writes independently verified against the compute_components() oracle"
    requirement: RESCORE-02
    verification:
      - kind: other
        ref: "independent full-population read-back recorded in 49-W1-ARM-RECORD.md (66/66 components match oracle, lv_icp_fit_score equals component sum on every record)"
        status: pass
    human_judgment: false
  - id: D2
    description: "P2/P3 census snapshots committed, each with a derivation timestamp and a tier distribution summing to the population count; observed movement (14 rows C->B, all individual_club_team) matches the pre-registered Phase 46 forecast exactly"
    requirement: RESCORE-03
    verification:
      - kind: other
        ref: "49-P2-SNAPSHOT.json / 49-P3-SNAPSHOT.json diff, quoted in 49-W1-ARM-RECORD.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "Parity sweep acceptance anchor: run genuinely, script unedited, and the true result (4 of 66 real findings, a diagnosed and disclosed live-data divergence) committed rather than forced green"
    verification: []
    human_judgment: true
    rationale: "The sweep exits non-zero by design in this outcome; a human must confirm the RED result is the correct, honest state rather than a defect in this session's work. The plan's automated <verify> for Task 3 will itself report failure on this deliverable — that is expected, not a bug."

duration: 45min
completed: 2026-08-13
status: complete
---

# Phase 49 Plan 05: W1 Population Re-Score Summary

**Full-population HubSpot ICP re-score under the Phase 46 rubric weights, closing the parity red window with genuine data — 66/66 components correct, the pre-registered 14-row C→B forecast matched exactly — while 4 records' `lv_icp_tier` stayed stale for a diagnosed, disclosed, and now-documented reason outside this window's declared write mechanism.**

## Performance

- **Duration:** 45 min (this continuation; total plan across both sessions was longer)
- **Started:** 2026-08-13T05:00:24Z (Task 1 pre-flight)
- **Completed:** 2026-08-13T06:19:00Z (this continuation)
- **Tasks:** 3/3 (Task 3 completed across two sessions — halted mid-task at a `checkpoint:decision`, resumed and finished here)
- **Files modified:** 6

## Accomplishments

- **The re-score succeeded.** Every one of the 66 live-derived scored companies received all five component properties in one armed window (canary + remainder, no disarm between legs); an independent full-population read-back — stronger evidence than the driver's own settle loop, which a harness timeout killed mid-run — confirmed 66/66 components equal the freshly-computed oracle and every `lv_icp_fit_score` equals the sum of its own five components.
- **The forecast landed exactly.** Post-write census shows exactly 14 rows moved C→B, all `individual_club_team`, matching `46-SIMULATION-REPORT.md`'s pre-registered prediction in both count and shape. A/D/Unscored tier counts held, also as forecast.
- **The acceptance anchor did NOT fully close.** `scripts/run_scoring_parity.py`'s live population sweep exits RED: 4 of 66 companies (all `individual_club_team`) show `lv_icp_fit_score` correctly `45` but `lv_icp_tier` stuck at stale `C` (oracle expects `B`). Root cause diagnosed and disclosed, not fixed: their components were already correct before W1 opened (`hs_lastmodifieddate` 2026-08-12), so W1's write was value-identical for them — HubSpot fires no property-change event on a same-value PATCH, so WF1 (the sole writer of `lv_icp_tier`) never re-enrolled to re-grade them.
- Both findings stand side by side, deliberately: the re-score is proven correct at the data level (components, sums, movement shape), and the acceptance gate is honestly RED because of a structural limitation this window's declared mechanism cannot reach — not because of any defect in this session's write.
- Operator resolved the Task 3 checkpoint as **ACCEPT AND DISCLOSE**: the 4 records are logged as `unmet-truth` entries in `.planning/WINDOWS.md` (ids 9–12), each naming the record, the expected-vs-actual tier, the root cause, and the pointer to `.planning/TIER-DERIVATION-SPIKE-2026-08-13.md` — a grammar spike (this session, prior commit `08d7f61`) that proved `lv_icp_tier` can become a `calculation_equation` property, which removes the enrollment-event dependency entirely and fixes this class of gap as a side effect. That fix is scoped to a future phase (a new HubSpot property is out of v0.9 scope per the 2026-08-11 operator decision), not this plan.

## Task Commits

1. **Task 1: Pre-flight — re-derive population, capture P2** - `f66f215` (docs)
2. **Task 2: Authorise W1 (checkpoint, resolved `arm-w1`)** - checkpoint, no code commit
3. **Task 3: W1 run — canary, remainder, settle, disarm, finding surfaced** - `b4d64ea` (docs)
4. **Task 3 (continuation): P3 snapshot, parity verdict, WINDOWS.md entries, plan close** - *(this commit, see below)*

**Plan metadata:** *(final docs commit, see below)*

## Files Created/Modified

- `.planning/phases/49-re-score-strategy-reporting/49-P3-SNAPSHOT.json` - post-window census, live read, `A:9 B:41 C:7 D:7 Unscored:2`
- `.planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json` - the true post-window sweep result: FAIL, `assertions_executed=67`, 4 real findings, script unedited (`git diff HEAD~1` empty)
- `.planning/phases/49-re-score-strategy-reporting/49-W1-ARM-RECORD.md` - extended with the operator's resolution, the P3/parity results, and the final closed-window accounting
- `.planning/WINDOWS.md` - 4 new `unmet-truth` entries (ids 9–12), one per stuck-tier record
- `.planning/STATE.md` - position, decisions, session updated

## Decisions Made

- **ACCEPT AND DISCLOSE** the 4-record finding rather than fix it in-plan (operator decision, this continuation). Every mechanism that could force the tier to move was explicitly ruled out: no `lv_icp_tier` PATCH (absolute project rule, WF1 is its sole writer), no blank-then-rewrite, no n8n allowlist arm for a weight-only re-score.
- The durable fix — `lv_icp_tier` as a derived `calculation_equation` property — is deliberately Phase 50 / v1.0, not Phase 49, because it needs a new HubSpot property, which `.planning/REQUIREMENTS.md`'s Out of Scope section forbids for v0.9.
- `scripts/run_scoring_parity.py` was not edited to reach a green verdict. The RED result is recorded as the honest data outcome (confirmed via `git diff HEAD~1 -- scripts/run_scoring_parity.py` showing no change).

## Deviations from Plan

### Auto-fixed Issues

None in this continuation — the deviations (harness timeout on the settle loop, the diagnostic gate-bypass batch call) were already disclosed in the prior session's commit `b4d64ea` and `49-W1-ARM-RECORD.md`; nothing new was auto-fixed here.

### Accepted, disclosed, not fixed

**1. [Rule 4 — architectural, resolved by operator] 4 records' `lv_icp_tier` stuck stale after a value-identical PATCH**
- **Found during:** Task 3, first pass (prior session)
- **Issue:** `9605273630`, `9604738976`, `17696004613`, `19100977027` (all `individual_club_team`) already carried correct new-weight components and a correct `lv_icp_fit_score` of 45 before W1 opened. W1's PATCH to these four ids sent byte-identical values, so HubSpot bumped nothing and fired no workflow-enrollment event; WF1 never re-graded their tier.
- **Resolution:** Operator selected ACCEPT AND DISCLOSE. Logged as `unmet-truth` WINDOWS.md entries (ids 9–12) with root cause and the pointer to the scoped fix (`.planning/TIER-DERIVATION-SPIKE-2026-08-13.md`, future Phase 50).
- **Files modified:** `.planning/WINDOWS.md`, `.planning/phases/49-re-score-strategy-reporting/49-W1-ARM-RECORD.md`, `PORTAL-FACTS.md` (root, prior session)
- **Verification:** `49-PARITY-VERDICT.json` records exactly these 4 as real findings, no others; independent full-population read-back confirms all other 62 records match the oracle on all three of score/tier/veto-flag.
- **Committed in:** this continuation's plan-close commit

---

**Total deviations:** 1 accepted-and-disclosed (Rule 4, resolved by operator decision, no code change)
**Impact on plan:** The re-score itself is fully correct and verified. The acceptance anchor (parity sweep) is honestly RED for a diagnosed, scoped-elsewhere reason. No scope creep; no gate loosened.

## Issues Encountered

Same-value HubSpot batch PATCH behavior (no `hs_lastmodifieddate` bump, no workflow-enrollment event even with `shouldReEnroll: true`) was previously unknown and is now documented in `PORTAL-FACTS.md`. It structurally limits any component-only write mechanism's ability to correct a stale tier once the underlying score value is already right — the exact failure mode the Phase 50 tier-derivation spike (this session) targets.

## Known Stubs

None. No hardcoded empty values or placeholder UI/data were introduced by this plan.

## Threat Flags

None. No new network endpoints, auth paths, or trust-boundary changes — this plan reused the exact write surface built and threat-modeled in plan 49-01/49-02 (component-only batch PATCH, two-key env gate).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 49's other declared artifacts (P2/P3 snapshots, arm record, parity verdict) are all committed and internally consistent; nothing is armed.
- A future phase (tentatively 50) can pick up `.planning/TIER-DERIVATION-SPIKE-2026-08-13.md` directly — the grammar is proven, the blast radius is small (WF1 is the sole current writer, ~35 repo touch-points are all reads/guards/tests), and it fixes WINDOWS.md ids 9–12 as a side effect.
- Two open items remain for that future phase to resolve before it can decide a rollout: (1) whether HubSpot's null-propagation-in-conditional behavior differs from the flat-sum blanking rule already proven for `lv_icp_fit_score`, and (2) enumerating portal-side dependents (lists/views/filters) keyed on the `lv_icp_tier` select before any cutover.

---
*Phase: 49-re-score-strategy-reporting*
*Completed: 2026-08-13*
