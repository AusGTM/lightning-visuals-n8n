---
phase: 50-derived-tier-property
plan: 04
subsystem: infra
tags: [hubspot, automation-v4, workflow-enrolment, rollback-runbook, icp-tier]

requires:
  - phase: 50-02
    provides: 50-DEPENDENTS-SWEEP.md's first (post-migration) D-13 run and its manual-check half
  - phase: 50-03
    provides: 50-TIER-PARITY-EVIDENCE.md's match/mismatch classification used to pick the drill subject
  - phase: 50-06
    provides: the numeric veto mirror and D-16's one spent deviation, referenced but not touched here
provides:
  - "docs/OPERATOR-TIER-ROLLBACK.md: operator runbook for D-18's rollback, primary mechanism proven live"
  - ".planning/phases/50-derived-tier-property/50-ROLLBACK-DRILL.md: live evidence artifact for the proof"
  - "a dated pre-cutover re-run of the D-13 dependent sweep (0 lists, 10 flows, no delta)"
affects: [50-05]

actuals:
  tokens: 3600
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "runbook-with-proof: a rollback mechanism is not documented as available until a live drill artifact backs the claim, and the runbook points at that artifact rather than restating the proof inline"

key-files:
  created:
    - docs/OPERATOR-TIER-ROLLBACK.md
    - .planning/phases/50-derived-tier-property/50-ROLLBACK-DRILL.md
  modified:
    - .planning/phases/50-derived-tier-property/50-DEPENDENTS-SWEEP.md

key-decisions:
  - "Drill subject: Melbourne Racing Club 9604614548 (confirmed match, tier C before and after), not one of the 4 D-07 stuck ids and not Coffs Harbour 14752488879 (D-23's pinned Unscored->C transition would have broken if enrolled)."
  - "Drill proves the mechanism runs and completes, not that WF1 re-grades a stale record -- stated explicitly as a limitation rather than left implicit."
  - "docs/OPERATOR-TIER-ROLLBACK.md's primary mechanism is now marked PROVEN LIVE with a pointer to the drill artifact; the WF1-must-be-ON precondition is stated as the rollback's own catch-22."
  - "Fallback (perturb-then-restore) stays documented as an unexercised secondary requiring its own fresh D-16 authorisation if ever used -- not exercised in this plan."

requirements-completed: [TIER-03]

coverage:
  - id: D1
    description: "D-18's rollback runbook names the WF1-re-enable step plus the forced re-grade requirement, records RESEARCH Q1's negative and Phase 47.5's non-transfer finding, and names the two real mechanisms with a chosen primary"
    requirement: TIER-03
    verification:
      - kind: manual_procedural
        ref: "docs/OPERATOR-TIER-ROLLBACK.md content review against 50-04-PLAN.md's acceptance criteria"
        status: pass
    human_judgment: false
  - id: D2
    description: "Portal-UI manual enrolment proven live while WF1 is on, against a non-stuck match subject, before Plan 05 switches WF1 off"
    requirement: TIER-03
    verification:
      - kind: manual_procedural
        ref: ".planning/phases/50-derived-tier-property/50-ROLLBACK-DRILL.md automated verify block (subject-id / stuck-id-exclusion / date assertions)"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-13's dependent sweep re-run immediately before cutover, dated, appended (not overwritten) alongside prior runs"
    requirement: TIER-03
    verification:
      - kind: unit
        ref: "tests/test_sweep_tier_dependents.py"
        status: pass
    human_judgment: false

duration: ~35min (across original executor + this continuation)
completed: 2026-08-14
status: complete
---

# Phase 50 Plan 04: D-18 Rollback Runbook and Live Proof Summary

**D-18's forced re-enrolment mechanism (portal-UI manual enrolment into WF1) is named, its impossible alternatives (Automation v4 has no enrolment endpoint, v2 is contacts-only, Phase 47.5's recompute POST doesn't transfer) are recorded as findings, and the primary mechanism is proven live against a non-stuck record while WF1 is still on — all before Plan 05 can switch WF1 off.**

## Performance

- **Tasks:** 2/2 complete
- **Commits:** 2 (`bf8c82e` runbook + sweep re-run, `7c2c7fc` drill proof + runbook update)
- **Files modified:** 3 (2 created, 1 modified across both commits)

## Accomplishments

- `docs/OPERATOR-TIER-ROLLBACK.md` written matching `docs/OPERATOR-VETO-REFRESH.md`'s conventions: numbered Step 1 (re-enable WF1 via `PUT /automation/v4/flows/4625147345`) and Step 2 (force the re-grade — explicitly rejecting "re-enable and let it converge naturally"), with a what-it-costs and what-it-does-not-change section.
- RESEARCH Q1's negative recorded as a finding: Automation v4 has no enrolment endpoint of any kind; the legacy v2 endpoint is contacts-only and deprecated. Phase 47.5's `recompute: true` POST recorded as non-transferring — it drives n8n's own veto lane, never HubSpot's Automation platform.
- Two real mechanisms named with a chosen primary: portal-UI manual enrolment (primary) and armed/capped/disarm-verified perturb-then-restore double-write (fallback, labelled a D-16 deviation, not exercised).
- **Live drill performed and proven**, operator-executed in HubSpot portal `22617666`: Melbourne Racing Club `9604614548` (a confirmed `match` row, `lv_icp_tier` = `C`) manually enrolled into WF1 `4625147345` while it was confirmed on; execution history confirmed completion; tier read `C` before and `C` after (value-identical, zero company writes). Recorded in `50-ROLLBACK-DRILL.md` with both required limitations stated explicitly: the subject was already correctly tiered (proves the mechanism runs, not that WF1 re-grades a stale record), and Coffs Harbour `14752488879` was deliberately excluded because re-grading it would have broken D-23's pinned `Unscored`→`C` accepted-divergence transition and turned D-07's GREEN parity gate back to RED.
- `docs/OPERATOR-TIER-ROLLBACK.md` updated post-drill: primary mechanism marked **PROVEN LIVE** with a pointer to the drill artifact; the WF1-must-be-ON precondition stated plainly as the rollback's own catch-22 (unavailable once WF1 is off — exactly why the drill had to happen before Plan 05); fallback kept as an unexercised secondary, noting a fresh D-16 authorisation would be required if it were ever used.
- D-13's dependent sweep re-run immediately before cutover: 0 lists, 10 flows, identical 5 findings (all on WF1 itself) to both prior runs — no delta. The reports/dashboards manual-check residual is carried forward as still `UNCONFIRMED`, unresolved.

## Task Commits

Each task was committed atomically:

1. **Task 50-04-01: Write the rollback runbook and refresh the pre-cutover sweep** — `bf8c82e` (docs)
2. **Task 50-04-02: Prove the rollback mechanism live, while WF1 is still on (D-18)** — `7c2c7fc` (docs)

_Task 2 was a `checkpoint:human-action` — a fresh continuation agent finished it after the operator ran the live portal drill and reported results._

## Files Created/Modified

- `docs/OPERATOR-TIER-ROLLBACK.md` — the D-18 rollback runbook: two-step mechanism, both impossible alternatives recorded, primary mechanism now marked proven live with a pointer to the drill evidence
- `.planning/phases/50-derived-tier-property/50-ROLLBACK-DRILL.md` — live drill evidence: subject, before/after tier, WF1 execution-history confirmation, both required limitations stated explicitly
- `.planning/phases/50-derived-tier-property/50-DEPENDENTS-SWEEP.md` — dated pre-cutover D-13 sweep section appended (not overwritten), no delta from prior runs

## Decisions Made

- Drill subject chosen as Melbourne Racing Club `9604614548` — a confirmed `match` row in `50-TIER-PARITY-EVIDENCE.md`, excluded from the 4 D-07 stuck ids per the plan's prohibition, and distinct from the genuinely-stale Coffs Harbour `14752488879` which was deliberately not used (would have broken D-23's pinned transition and D-07's parity gate).
- The drill's automated verify block (`50-04-PLAN.md` Task 2) asserts no stuck ids appear anywhere in the artifact text at all, not just that none is the subject — required rewording the "excluded ids" reference in `50-ROLLBACK-DRILL.md` away from spelling out the literal ids, pointing instead at `50-04-PLAN.md`'s `<prohibitions>` and `50-CONTEXT.md`'s D-07/D-23. No content was lost; the exclusion reasoning is stated in full, just without the literal digit strings that would fail the check.
- The WF1-authored, value-identical `lv_icp_tier` write during the drill is disclosed explicitly in `50-ROLLBACK-DRILL.md`'s "Disclosure — D-16 framing" section, and stated not to count against D-16's zero-company-write-window declaration (which governs this repo's own scripts, not HubSpot's workflow engine acting on a human-triggered enrolment).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Drill artifact initially failed its own automated verify block**
- **Found during:** Task 2, immediately after writing the first draft of `50-ROLLBACK-DRILL.md`
- **Issue:** The plan's automated check (`50-04-PLAN.md` Task 2 `<verification>`) asserts that none of the 4 stuck company ids appear *anywhere* in the drill document text. The first draft's "Subject" table and exclusion-reasoning paragraph spelled out all 4 stuck ids to explain why they were excluded, which tripped the assertion.
- **Fix:** Reworded the affected passages to reference `50-04-PLAN.md`'s `<prohibitions>` list and `50-CONTEXT.md`'s D-07/D-23 sections instead of citing the literal ids, preserving the full reasoning without the digit strings.
- **Files modified:** `.planning/phases/50-derived-tier-property/50-ROLLBACK-DRILL.md`
- **Verification:** Re-ran the plan's exact verify script; passed (`drill evidence ok: ['14752488879', '4625147345', '9604614548']`).
- **Committed in:** `7c2c7fc` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** No scope creep; wording-only correction to satisfy the plan's own automated gate.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- D-18's rollback mechanism is named and proven; Plan 05 can now proceed to its WF1-off decision with a real, evidenced fallback path in hand rather than an asserted one.
- **Carried forward unresolved, by design:** the reports/dashboards half of D-13's dependent sweep remains `UNCONFIRMED` — not "clean," not "found." The operator's 2026-08-14 attestation covers saved views only. Plan 05's one-way retirement decision must confront this residual directly; archiving `lv_icp_tier` while an unconfirmed report still references it is exactly the breakage D-13 exists to prevent, and this plan does not resolve it — it is stated here so it cannot be silently dropped between plans.
- WF1 `4625147345` confirmed still enabled at the end of this plan (live read-only check via `scripts/fetch_hubspot_flow.py`, `isEnabled: True`), and `lv_icp_tier` remains present and unarchived. Neither was touched by this plan, as required.

---
*Phase: 50-derived-tier-property*
*Completed: 2026-08-14*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`bf8c82e`, `7c2c7fc`) verified present in `git log --oneline --all`.
