---
phase: 46-rubric-decision-simulation-engine-parity
plan: 03
subsystem: scoring
tags: [icp-scoring, hubspot, decision-record, rubric-decision, operator-signoff]

requires:
  - phase: 46-rubric-decision-simulation-engine-parity
    plan: 02
    provides: "46-SIMULATION-REPORT.md -- the committed, live, per-company before/after report this plan's decision record cites and the operator signed off against"
provides:
  - "46-DECISION.md -- the RUBRIC-01 decision record: per-lever evidence and override for D-01/D-02/D-03, rejected alternatives, engine-count finding, D-07 tiebreaker, parity red-window decision, Phase 49 re-score recommendation, and a filled operator sign-off block"
  - "Operator sign-off: 'Accept all three (Recommended)' -- individual_club_team=15, regulator=-20, gambling deduction removed, no substitutions"
affects: [46-04-weight-commit, 46-05-doc-sync, 49-rescore]

actuals:
  tokens: 9000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Decision record structure inherited from 39-DECISION.md's nine-section precedent, extended with an explicit unfilled-then-filled operator sign-off block as the phase's authorization boundary (D-05)"

key-files:
  created:
    - .planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md
  modified: []

key-decisions:
  - "Operator accepted all three levers as recommended, no substitutions: individual_club_team=15, regulator=-20, gambling_operator deduction removed."
  - "Parity red-window option (a) recommended and accepted: the window opens at Plan 04's config commit (not the flow PUT), is expected to report every re-tiered live record as a parity real_finding until Phase 49's re-score, and Phase 49 closes it. Option (b) (coordinate the commit with Phase 49 to minimize the gap) was considered and rejected because Plan 04 is scoped to execute inside Phase 46, ahead of Phase 47/48, which do not depend on the org-type weight values."
  - "D-07's standing tiebreaker (keep a weight unchanged if evidence argues it down but simulation shows near-zero tier movement) did not govern D-01/D-02/D-03 -- all three were GTM-directed. Recorded honestly that, read literally, D-07 would have argued against D-02/D-03 specifically (both are score-only, not tier-moving, on live data) -- the operator was shown this tension explicitly before accepting."
  - "D-09's shareable-artifact publish deferred to the orchestrator session (recorded as a deviation, not an unmet requirement) -- this CLI executor has no artifact-publishing capability. The committed 46-SIMULATION-REPORT.md and 46-DECISION.md are the durable substitute; the orchestrator publishes the link after the phase completes."
  - "Operator sign-off was received via the /gsd-execute-phase coordinator relay, not a directly-witnessed human reply in this executor's own session -- provenance recorded explicitly in 46-DECISION.md's sign-off block rather than presented as directly witnessed."

patterns-established: []

requirements-completed: [RUBRIC-01]  # REQUIREMENTS.md's own bar: "the requirement is that the decision is made and evidenced, not that it changes." Met: all three levers decided, evidenced against icp-scoring.md, overrides stated as overrides, operator signed off. RUBRIC-02's simulation-before-commit bar is also now fully closed by this plan's sign-off (Plan 02 built the artifact, this plan closes CONTEXT.md D-05's "phase does not close until the operator accepts or overrides" condition) -- not marked here since RUBRIC-02 is not in this plan's frontmatter requirements list; noted for Plan 05 to close explicitly. RUBRIC-03 remains open, pending Plan 04's weight commit and parity re-proof.

coverage:
  - id: D1
    description: "46-DECISION.md records a decision for each of the three org-type levers, citing docs/business/icp-scoring.md evidence, stating each override as an override with the evidence intact, the post-change rank ordering, rejected club weights (10/20/30), the rejected graduated_deductions shape for the regulator deduction, the D-07 tiebreaker, the engine-count finding and its ROADMAP criterion-4 consequence, the parity red-window decision, and Phase 49's recommended re-score mechanism with the HARD_CEILING_RECORDS gate"
    requirement: "RUBRIC-01"
    verification:
      - kind: manual_procedural
        ref: "grep -c icp-scoring.md 46-DECISION.md returns 11 (>=1 per lever); grep -n override returns 20 hits; all nine 39-DECISION.md section headings present; club weights 10/20/30 and graduated_deductions shape named; HARD_CEILING_RECORDS and scripts/backfill_seed_company_scores.py named; git diff config/icp_scoring.yaml config/hubspot_flows/ empty"
        status: pass
    human_judgment: true
    rationale: "The acceptance criteria are mechanically checkable (grep counts, heading presence), but whether the record's tone honors D-14 (evidence quoted, not silently rewritten to agree with the new weight) and whether the rationale is genuinely audit-quality for a reader with no prior context is a judgment call the plan's own <done> criterion makes explicit -- not reducible to a passing test."
  - id: D2
    description: "The operator has explicitly accepted or overridden the recommendation, recorded verbatim with a date in 46-DECISION.md's sign-off block, before any weight reaches config/icp_scoring.yaml or config/hubspot_flows/"
    requirement: "RUBRIC-01"
    verification:
      - kind: manual_procedural
        ref: "46-DECISION.md Operator Sign-off block: decision='accepted', date=2026-08-11, no substituted values; git diff config/icp_scoring.yaml config/hubspot_flows/ confirmed empty after the sign-off commit"
        status: pass
    human_judgment: true
    rationale: "This deliverable's entire content IS a human decision -- there is no automated proxy for 'did the operator actually decide this,' only the recorded evidence that they did."

duration: ~20min
completed: 2026-08-11
status: complete
---

# Phase 46 Plan 03: Rubric Decision & Operator Sign-off Summary

**Wrote the RUBRIC-01 decision record for all three org-type weight levers (club, regulator,
gambling deduction) with per-lever closed-deal evidence and explicit overrides, then recorded
the operator's "Accept all three" sign-off — no substitutions, no engine touched.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-11
- **Tasks:** 2 completed
- **Files modified:** 1 (created, then amended for sign-off)

## Accomplishments
- `46-DECISION.md` written following `39-DECISION.md`'s nine-section precedent: Verdict; How the
  verdict was reached; Rationale; Rejected alternatives; What this shapes downstream;
  Assumptions carried into the verdict; Re-check procedure; Process note; Evidence index — plus
  an Operator Sign-off block.
- Each of the three levers documented evidence-then-override: D-01 (club 5→15) against the
  19%-over-n=36 win rate and "reach them via their governing body, not directly"; D-02
  (regulator 5→-20) against "QRIC is a regulator, not a content buyer"; D-03 (gambling deduction
  removed) against the deliberate graduated-deduction design that kept operators "targetable
  proactively where other fit signals are strong." All three quotes preserved intact, per D-14.
- Rejected alternatives recorded with reasoning: club weight 10 (fragile B floor), 20 (ties
  broadcaster/producer), 30 (inverts the win-rate ordering into Tier A); the `graduated_deductions`
  key shape for the regulator deduction, superseded by a direct `base_score.org_type.regulator`
  weight per 46-RESEARCH.md's Open Question 5 execution proof.
- Live simulation findings folded in plainly, including the divergence from CONTEXT.md's earlier
  estimate: D-02/D-03 are score-only on live data (QRIC/Entain/Sportsbet already carry
  independent hard vetoes), and the resulting tension with the D-07 tiebreaker — stated as a
  tension, not silently resolved.
- Engine-count finding (two engines, not three) and its consequence for ROADMAP Phase 46 success
  criterion 4 (not triggered) carried into the record, along with the parity red-window decision
  (option (a), bounded, closed by Phase 49) and Phase 49's recommended re-score mechanism
  (`scripts/backfill_seed_company_scores.py`'s `compute_components()` path, `HARD_CEILING_RECORDS
  = 25` chunking gate).
- Operator sign-off recorded: **"Accept all three (Recommended)"** — `individual_club_team=15`,
  `regulator=-20`, gambling deduction removed, no substitutions, dated 2026-08-11, with an
  explicit note on what evidence (D-07 tension, red-window cost) the operator was shown before
  deciding, and the sign-off's provenance (received via the `/gsd-execute-phase` coordinator
  relay).

## Task Commits

Each task was committed atomically:

1. **Task 1: Write 46-DECISION.md** - `a0e80ef` (docs)
2. **Task 2: Record operator sign-off** - `c95fdf6` (docs)

## Files Created/Modified
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md` - the full RUBRIC-01
  decision record and filled operator sign-off block

## Decisions Made
- **Operator accepted all three levers, no substitutions.** Plans 04 (weight commit + live flow
  PUT) and 05 (documentation sync) execute with the values exactly as recorded — no revision
  needed.
- **Parity red-window option (a) chosen and accepted**, over option (b) (coordinating the commit
  with Phase 49's re-score). Plan 04 is scoped to execute inside Phase 46, ahead of Phase 47/48,
  which don't depend on the org-type weight values, so deferring the commit to minimize the gap
  would hold the operator's decision unenacted for no corresponding benefit. The window closes
  when Phase 49 executes the re-score; every `individual_club_team`/`regulator`/gambling-flagged
  `real_finding` on the standing parity sweep in between is expected, not a new defect.
- **D-09's shareable-artifact publish deferred to the orchestrator session.** This CLI executor
  has no artifact-publishing capability — the committed `46-SIMULATION-REPORT.md` and
  `46-DECISION.md` are the durable substitute, and the orchestrator will publish the link after
  the phase completes. Recorded in `46-DECISION.md`'s sign-off block as a deferred step, not an
  unmet requirement.
- **Sign-off provenance recorded explicitly.** The "accepted" reply was relayed through the
  `/gsd-execute-phase` coordinator rather than witnessed directly in this executor's own
  session — this executor has no other channel to the operator. The provenance line in
  `46-DECISION.md`'s sign-off block makes this traceable rather than presenting it as if
  personally witnessed.

## Deviations from Plan

None — plan executed exactly as written. Both tasks (write the decision record; record the
operator's checkpoint resolution) completed per the plan's `<action>` text, including the
blocking checkpoint itself, which genuinely halted and returned control to the orchestrator
before this session resumed with the operator's recorded decision.

## Issues Encountered

**D-09's artifact-publish half could not be executed by this CLI executor** — no
artifact-publishing tool is available in this session's toolset (Read/Write/Bash/Skill/advisor
only). Resolved by deferring the publish to the orchestrator session per the coordinator's
explicit instruction, and recording the deferral (not a silent skip) in `46-DECISION.md`'s
sign-off block. The committed markdown report satisfies D-09's other half (markdown committed
under `.planning/`) in full.

**`gsd-tools requirements mark-complete RUBRIC-01` returned `not_found`** — pre-existing format
mismatch, not caused by this plan. The tool's traceability-row writer only flips a row whose
current `Status` cell reads `Pending` or `Gaps Found`; this repo's `REQUIREMENTS.md` table uses
`Not started` for the same unstarted state, so the row never matched and the checkbox flip was
rolled back to keep the two surfaces consistent (the tool's own `#2788` anti-drift guard).
Resolved by editing `.planning/REQUIREMENTS.md` directly — checkbox `- [x] **RUBRIC-01**` and
traceability row `Status = Complete` — producing the exact end state the tool would have written
had the row read `Pending`. Not fixed at the tool level (out of this plan's scope); flagging here
so a future plan's `mark-complete` call for `RUBRIC-02`/`RUBRIC-03` isn't surprised by the same
`not_found` result against this file's `Not started` rows.

## Requirements Note

`RUBRIC-01` is marked complete in `REQUIREMENTS.md` by this plan — its own bar ("the requirement
is that the decision is made and evidenced, not that it changes") is met: all three levers are
decided, evidenced against `docs/business/icp-scoring.md`, every override stated as an override
with the evidence intact, and the operator has signed off. `RUBRIC-02`'s simulation-before-commit
condition (`CONTEXT.md` D-05: "the phase does not close until the operator accepts or
overrides") is also now satisfied by this plan's sign-off, but `RUBRIC-02` is not in this plan's
frontmatter `requirements` list (it belongs to Plan 02, which built the simulation artifact) —
left unmarked here to avoid a plan claiming a requirement outside its own declared scope; Plan 05
should close it explicitly when it does the documentation sync. `RUBRIC-03` remains open pending
Plan 04's weight commit and its parity re-proof.

## Next Phase Readiness
- `46-DECISION.md` is fully signed off and committed — Plan 04 (weight commit + live flow PUT)
  and Plan 05 (documentation sync) are unblocked and require no revision, since the operator
  accepted all three values as recommended with no substitutions.
- `git diff config/icp_scoring.yaml config/hubspot_flows/` confirmed empty at the end of this
  plan — no engine has been touched.
- Plan 04 should follow `PORTAL-FACTS.md`'s "D-05 round-trip verdict" disable→edit→PUT→enable→
  validate→confirm protocol for the two flows this decision touches (`4626124224`,
  `4634822085`), and should expect (not treat as a bug) the standing parity sweep reporting
  `real_findings` for `individual_club_team`/`regulator`/gambling-flagged live records
  immediately after the config commit, per the accepted red-window decision.
- The orchestrator session owes the D-09 artifact publish after this phase completes — flagged
  above, not blocking Plan 04/05.
- No blockers.

## Self-Check: PASSED

`.planning/phases/46-rubric-decision-simulation-engine-parity/46-DECISION.md` confirmed present
on disk with the filled Operator Sign-off block. Both task commit hashes (`a0e80ef`, `c95fdf6`)
confirmed present in `git log --oneline --all`.

---
*Phase: 46-rubric-decision-simulation-engine-parity*
*Completed: 2026-08-11*
