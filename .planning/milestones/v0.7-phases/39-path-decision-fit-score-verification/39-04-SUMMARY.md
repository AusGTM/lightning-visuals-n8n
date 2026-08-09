---
phase: 39-path-decision-fit-score-verification
plan: 04
subsystem: infra
tags: [hubspot, decision-record, path-decision, icp-scoring]

requires:
  - phase: 39-02
    provides: "evidence/VERIFICATION-NOTE.md — availability verdict (AVAILABLE) and its evidence citations"
  - phase: 39-03
    provides: "scripts/probe_scoring_recalc_latency.py — the D-04 recalc-latency probe, shipped but not armed this plan"
provides:
  - "39-DECISION.md — the standalone D-08 path decision record: fix-the-four-workflow-chain-in-place"
  - "One-line path-decision pointers in ROADMAP.md (Phase 39 block) and STATE.md (Current Position)"
  - "DECIDE-01 marked complete in REQUIREMENTS.md (checkbox + traceability table)"
affects: [40, 41, 42]

actuals:
  tokens: 3250
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Operator hard requirement overrides a pre-committed gate sequence (D-05/D-06) — recorded as an explicit deviation in the decision record itself, not silently absorbed into the verdict"

key-files:
  created:
    - .planning/phases/39-path-decision-fit-score-verification/39-DECISION.md
  modified:
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Path verdict: fix-the-four-workflow-chain-in-place. Deciding factor is an operator hard requirement (2026-08-06) that the score keep landing in the existing lv_icp_fit_score/lv_icp_tier properties — not the D-05 availability+recalc gate sequence, which was resolved AVAILABLE but is not what decided the path (the lead-scoring tool's auto-generated hubspotDefined score property cannot write to lv_icp_fit_score)."
  - "Task 1 (armed recalc-latency probe run) and Task 2 (band-c operator-decision checkpoint) were skipped as moot, per operator instruction, since the D-04 gate they resolve measures the lead-scoring tool's recalc behavior and that mechanism is not the chosen path regardless of the result. Recorded as an explicit deviation in 39-DECISION.md's own 'Process note' section, not silently dropped."
  - "DECIDE-01 marked complete — this decision record is exactly what the requirement specifies."

requirements-completed: [DECIDE-01]

coverage:
  - id: D4
    description: "39-DECISION.md exists, verdict-first, cites HANDOVER §5 by reference (not re-argued), carries forward the pipeline-owned-veto constraint, and links named evidence files"
    requirement: DECIDE-01
    verification:
      - kind: automated
        ref: "test -f 39-DECISION.md; grep -q 'HANDOVER-2026-08-06-icp-scoring.md'; grep -q '§5'; grep -q 'lv_anti_icp_flag'; grep -c 'evidence/VERIFICATION-NOTE.md|evidence/recalc_latency_probe.json|portal_walkthrough_' = 13 (>= 2 required)"
        status: pass
    human_judgment: false
  - id: D5
    description: "ROADMAP.md and STATE.md carry one-line pointers to the decision file; Phase 40/41/42 blocks intact (scoped edit, not whole-file rewrite)"
    requirement: DECIDE-01
    verification:
      - kind: automated
        ref: "grep -q '39-DECISION.md' ROADMAP.md STATE.md; grep -c 'Phase 4[012]' ROADMAP.md unchanged (12) before/after edit"
        status: pass
    human_judgment: false
  - id: D6
    description: "DECIDE-01 marked complete in REQUIREMENTS.md (checkbox + traceability table)"
    requirement: DECIDE-01
    verification:
      - kind: automated
        ref: "gsd-tools requirements.mark-complete DECIDE-01 → marked_complete: [DECIDE-01], write_set_complete: true"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-06
status: complete
---

# Phase 39 Plan 04: Path Decision Record Summary

**The scoring-engine path decision lands as a standalone `39-DECISION.md`: fix-the-four-workflow-chain-in-place, decided on an operator hard requirement to keep the score in the existing `lv_icp_fit_score`/`lv_icp_tier` properties — not on the D-05 availability/recalc gate sequence, which resolved AVAILABLE but was superseded by that requirement before this plan's own checkpoint tasks ever became relevant.**

## Performance

- **Duration:** ~15min
- **Tasks:** 1/3 executed (Task 3 — the decision record); Tasks 1 and 2 skipped as moot per operator override, documented as deviations rather than silently dropped
- **Files created:** 1 (`39-DECISION.md`); 3 modified (ROADMAP.md, STATE.md, REQUIREMENTS.md)

## Accomplishments

- Wrote `39-DECISION.md`, the D-08 standalone decision record a Phase 40 planner can read
  start-to-finish: verdict, how the verdict was reached (availability AVAILABLE, recalc gate
  moot), the latency measurement section explaining why no number exists, rationale citing
  HANDOVER §5 by reference (not re-argued, per D-07), rejected alternatives (custom equation
  properties rejected twice; legacy `calculation_score` recorded unavailable not rejected),
  what this shapes for Phases 40/41/42, the carried-forward assumptions, a re-check procedure,
  a process note explaining the Task 1/2 skips, and a named evidence index.
- Replaced ROADMAP.md's Phase 39 `**Path decision:** pending` line with the verdict and a
  pointer, using a scoped edit (verified Phase 40/41/42 block count unchanged: 12 before and
  after).
- Added one line to STATE.md's Current Position naming the verdict and linking the decision
  file.
- Marked `DECIDE-01` complete in `REQUIREMENTS.md` (checkbox + traceability table) via
  `gsd-tools query requirements.mark-complete` — this decision record is exactly what the
  requirement specifies.

## Task Commits

1. **Task 3: Write 39-DECISION.md and point ROADMAP.md/STATE.md at it** — `95703af` (feat) —
   bundles the new decision record with the ROADMAP/STATE pointer edits and the REQUIREMENTS.md
   DECIDE-01 completion in one commit.

## Files Created/Modified

- `39-DECISION.md` - The D-08 decision record: verdict, gate status, rationale, rejected
  alternatives, downstream implications, evidence index, and the Task 1/2 skip deviation note.
- `.planning/ROADMAP.md` - Phase 39 block: `Path decision:` line filled in, 39-04 checkbox
  checked, plan count updated to 4/4. Phase 40/41/42 blocks untouched.
- `.planning/STATE.md` - One new line under Current Position pointing at the decision file.
- `.planning/REQUIREMENTS.md` - DECIDE-01 checkbox and traceability row marked complete.

## Decisions Made

- **Path verdict: fix-the-four-workflow-chain-in-place.** See `39-DECISION.md` for the full
  record; the short version is that the operator's architecture-reuse requirement (score must
  land in `lv_icp_fit_score`/`lv_icp_tier`) is decisive regardless of the AVAILABLE availability
  verdict, because the lead-scoring tool cannot write to those existing properties.
- **Tasks 1 and 2 skipped as moot, not executed.** This plan's original Task 1 (build a trivial
  lead-scoring criterion in-portal, run the armed `scripts/probe_scoring_recalc_latency.py`) and
  Task 2 (the conditional band-c operator-decision checkpoint) both exist to resolve the D-04
  recalc gate for the lead-scoring-tool path. Since the operator's architecture-reuse
  requirement closed that path before this plan started (recorded in `39-02-SUMMARY.md` and
  `evidence/VERIFICATION-NOTE.md`'s Gate Status section), running the probe would not change the
  verdict this plan needed to reach. No trivial scoring criterion was built in-portal and no
  probe ran; `evidence/recalc_latency_probe.json` does not exist. This is recorded explicitly in
  `39-DECISION.md`'s "Process note" section per the operator's instruction to document it
  honestly rather than absorb it silently.

## Deviations from Plan

### Operator-Directed Deviations (documented, not silent)

**1. [Operator override] Task 1 (armed latency probe run) skipped — recalc gate moot for the chosen path**
- **Found during:** Plan start (pre-established in 39-02, reaffirmed at 39-04 launch by the
  orchestrator's explicit override context)
- **What the plan specified:** Build one trivial lead-scoring criterion in-portal, run the armed
  `scripts/probe_scoring_recalc_latency.py`, report the band letter and median, then tear down.
- **What happened:** Not executed. The operator's mid-phase architecture-reuse requirement
  closes the lead-scoring-tool path independent of any recalc measurement, so the D-04 gate this
  task resolves never gets consulted for the verdict.
- **Why this is a deviation, not a silent skip:** the plan's own acceptance criteria and threat
  model (T-39-17) treat this task's evidence as load-bearing for the decision; skipping it
  without a written reason would leave a future reader wondering why the probe (built and
  unit-tested in 39-03) was never armed. `39-DECISION.md`'s "Latency measurement" and "Process
  note" sections record the reason.
- **Files affected:** None (no probe run, no evidence file produced).

**2. [Operator override] Task 2 (band-c review checkpoint) skipped — no band exists to evaluate**
- **Found during:** Same as above.
- **What the plan specified:** Evaluate the band recorded by Task 1; auto-proceed silently for
  band a/b/availability-failure, prompt the operator only for band c.
- **What happened:** Not executed — with no probe run, there is no band letter to evaluate, so
  the checkpoint has no grounds to fire in either direction (auto-proceed or prompt).
- **Why this is a deviation, not a silent skip:** distinct from a normal "band a, auto-proceed"
  outcome — recording it as such would misrepresent that a measurement was taken.
  `39-DECISION.md`'s "Process note" section states this explicitly.
- **Files affected:** None.

**Impact on plan:** No scope creep, no code changes beyond the decision record and its
pointers. Both skips are operator-directed and pre-established before this plan's session began
(traceable to `39-02-SUMMARY.md`'s Deviations section and `evidence/VERIFICATION-NOTE.md`'s
Gate Status section) — this plan's job was to formalize the consequence in the canonical D-08
record, which it does.

## Issues Encountered

None.

## User Setup Required

None. The `user_setup` block in the plan frontmatter (build a trivial scoring criterion
in-portal) is moot given the operator override — no criterion was built, and none needs to be
torn down.

## Next Phase Readiness

- Phase 40 planning has exactly one file to read: `39-DECISION.md`. It names the path
  (fix-the-four-workflow-chain-in-place), the F1–F10 defect inventory to fix (HANDOVER §10.2),
  the parity oracle (`src/icp_scoring.py`), and the pipeline-owned-veto constraint that survives
  regardless of path.
- `scripts/probe_scoring_recalc_latency.py` (39-03) remains a shipped, unit-tested, disarmed
  asset — not needed for this milestone's chosen path, but reusable if a lead-scoring-tool path
  is reconsidered later (re-check procedure in `39-DECISION.md`).
- Phase 39 is now fully executed: 4/4 plans complete, DECIDE-01 satisfied.
- No blockers.

---
*Phase: 39-path-decision-fit-score-verification*
*Completed: 2026-08-06*

## Self-Check: PASSED

`39-DECISION.md` found on disk; commit `95703af` found in `git log --oneline`; ROADMAP.md,
STATE.md, REQUIREMENTS.md all carry the expected edits (grep-verified above).
