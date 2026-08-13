---
phase: 50-derived-tier-property
plan: 03
subsystem: hubspot-schema
tags: [hubspot, calculation_equation, icp-tier, veto, parity-gate, evidence]

requires:
  - phase: 50-derived-tier-property
    provides: "50-01: lv_icp_tier_derived live on companies (calculated string, coalesced formula), scripts/check_tier_derived_parity.py's row-level comparator, 50-NULL-PROBE.json settling D-04"
provides:
  - "tests/test_tier_formula_pin.py -- offline pin of the live-canonicalized calculationFormula against config/icp_scoring.yaml's tier_rules, with 8 mutation cases proving the guard has teeth"
  - "scripts/check_tier_derived_parity.py's render_evidence_markdown() -- the D-17 item 4 evidence wrapper (denominator, WINDOWS.md id 9-12 cross-reference, explicit PASS/FAIL verdict, limits block)"
  - "scripts/check_tier_derived_parity.py's --census mode -- the D-19 before/after tier census, reusing scripts/build_rescore_report.py's point machinery, appending to the same evidence artifact"
  - "50-TIER-PARITY-EVIDENCE.md -- the committed D-07 verdict AND D-19 census in one file, both against the real live 66-company scored population"
  - "WINDOWS.md ids 13-14 -- two new broken windows discovered by this plan's own live run"
affects: [50-04-retirement-decision]

actuals:
  tokens: 17500
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Two-point census reuse: build_rescore_report.py's three-point (P1/P2/P3) machinery collapsed to a before/after shape by reusing its _validate_point/_diff_points/_movement_table functions directly, rather than writing a second distribution renderer"
    - "Parsed-meaning formula pin (not byte-identity): a formula pin test that normalizes and parses a calculation_equation string into (veto_tier, veto_guard, score_bounds, else_tier) and diffs by parsed structure, because HubSpot canonicalizes the stored text on create (= -> equals, quote style, inserted line breaks) so byte-identity against the live text fails spuriously on a correct property"

key-files:
  created:
    - tests/test_tier_formula_pin.py
    - .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md
  modified:
    - scripts/check_tier_derived_parity.py
    - tests/test_tier_derived_tools.py
    - .planning/WINDOWS.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "D-07's gate is rendered FAIL, honestly, not softened: 7 of 66 rows are genuine defects (6 from a newly-discovered veto-guard failure, 1 a 5th WF1-staleness instance), so D-06 (retire lv_icp_tier) and D-08 (switch off WF1) stay blocked pending Plan 04's decision."
  - "TIER-01 is left NOT marked complete despite being in this plan's declared requirements list -- the requirement text requires the ladder 'verified against real records,' and the live veto-guard failure directly contradicts that for 6/6 vetoed records. TIER-02 IS marked complete on its own independent merits (the null-propagation question was answered and disclosed by Plan 01)."
  - "Coffs Harbour Racing Club (14752488879) is logged as a NEW WINDOWS.md entry (id 14), not folded into the existing 4 known-stuck ids -- it is evidence FOR the derived property (derived tier C is correct, live tier Unscored is stale), the opposite polarity of the veto-guard defect, and the gate's exception list is pre-registered by id, not extensible after the fact."

requirements-completed: [TIER-02]

coverage:
  - id: D1
    description: "Offline formula pin (tests/test_tier_formula_pin.py) locks the live-canonicalized calculationFormula's per-tier bounds, branch order, and veto guard shape against config/icp_scoring.yaml's tier_rules, with 8 mutation cases proving the guard rejects a moved threshold, a removed branch, a demoted veto, a 6th label, and both live-proven-400 veto-guard variants."
    requirement: TIER-01
    verification:
      - kind: unit
        ref: "tests/test_tier_formula_pin.py (14 tests, all pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-07's parity gate run live across all 66 scored companies, rendered into a committed evidence artifact (denominator, WINDOWS.md id cross-reference, explicit verdict, limits block) -- the deliverable is the evidence being produced and auditable, independent of the verdict's own pass/fail content."
    requirement: TIER-01
    verification:
      - kind: other
        ref: ".planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md (population=66, re-run twice byte-identical)"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-19's before/after tier census (--census mode) rendered into the same artifact, reusing scripts/build_rescore_report.py's point machinery, with the pre-registered expectation stated alongside the actual result and the D-04 never-scored disclosure reported separately."
    requirement: TIER-03
    verification:
      - kind: unit
        ref: "tests/test_tier_derived_tools.py::test_render_census_markdown_* (8 tests, all pass)"
        status: pass
      - kind: other
        ref: ".planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md's census section (live, 66-company population)"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-08-13
status: complete
---

# Phase 50 Plan 03: D-07 Parity Gate + D-19 Census Summary

**D-07's gate rendered FAIL against the live 66-company population -- 6 vetoed companies (including Simtech LED, Phase 47.5's own retroactive-fix poster child) read a workable tier on `lv_icp_tier_derived` instead of the correct hard exclusion, a defect never actually verified against real data before this run.**

## Performance

- **Duration:** ~50 min
- **Completed:** 2026-08-13T22:05:33Z
- **Tasks:** 3 (formula pin, live parity gate, live census)
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- Built `tests/test_tier_formula_pin.py`: pins `lv_icp_tier_derived`'s calculation formula against `config/icp_scoring.yaml`'s `tier_rules` two ways -- the pre-creation literal (byte-identical to `50-NULL-PROBE.json`) and, critically, the LIVE server-canonicalized text HubSpot actually stores (per 50-01's disclosed canonicalization finding), compared by parsed meaning rather than byte-identity so the pin cannot fail spuriously on a correct property. 14 tests, 8 of them parametrized mutation cases proving the guard has teeth (each tier boundary, the veto branch, the else branch, a 6th label, a demoted veto, and two live-proven-400 veto-guard shape variants).
- Ran D-07's parity gate live against the real, re-derived 66-company scored population (matches the recorded expectation exactly). Result: 55 match, 4 expected mismatch (the known stuck records, all correctly reading `B`), **7 defect**. Re-ran the gate twice -- byte-identical both times, ruling out settling lag.
- Discovered, characterized, and disclosed a previously-unverified defect: `lv_icp_tier_derived`'s veto guard (`coalesce(lv_anti_icp_flag, 0) = 1`) never fires live -- **all 6 of the 6** scored companies carrying `lv_anti_icp_flag=true` derive a score-based tier instead of `D`. This was never actually checked against a real true-flag record before this task: the spike's "Round 2 -- 7/7" was formula-grammar acceptance only (HTTP 200 on property create, `TIER-DERIVATION-SPIKE-2026-08-13.md`), and D-05's null probe (Plan 01) never set `lv_anti_icp_flag` on its disposable test company. Independently re-confirmed via a direct single-record re-GET on 3 of the 6 records outside the batch read.
- Discovered a 5th instance of the WF1-staleness class (Coffs Harbour Racing Club, `14752488879`) -- not one of `WINDOWS.md` ids 9-12 -- where the derived property is CORRECT and the stale enum is wrong, the opposite polarity of the veto-guard defect.
- Rendered D-19's before/after tier census (new `--census` mode), reusing `scripts/build_rescore_report.py`'s own point-validation/diff/movement-table machinery collapsed to a two-point shape rather than writing a second renderer. Live result: **DEFECT**, not the pre-registered "identical except 4 records C->B" -- Tier D empties from 6 to 0. Added an explicit SEVERITY callout naming the consequence plainly (Jam TV, Simtech LED) so it is visible to anyone reading only the evidence artifact.
- Logged both new findings to `.planning/WINDOWS.md` (ids 13-14) so they stay visible at ship time.
- Left TIER-01 NOT marked complete (its own text requires the ladder "verified against real records," which the veto-guard failure directly contradicts); marked TIER-02 complete on its independent merits (the null-propagation question was answered and disclosed).

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin the shipped formula against tier_rules (D-17 item 1)** - `c57a6ba` (test)
2. **Task 2: Run D-07's parity gate across all 66 scored companies** - `894ec50` (docs)
3. **Task 3: Render the operator-facing before/after tier census (D-19)** - `d81e67c` (feat)
3b. **WINDOWS.md ledger entries for the 2 new findings** - `a65233f` (docs)

**Plan metadata:** committed with this SUMMARY

## Files Created/Modified

- `tests/test_tier_formula_pin.py` - offline formula pin, D-17 item 1 (14 tests)
- `scripts/check_tier_derived_parity.py` - `render_evidence_markdown()` (denominator/cross-reference/verdict/limits wrapper), `--census` mode, `build_census_points()`, `render_census_markdown()` (with the SEVERITY callout), `_count_total_companies()`, `_count_never_scored_companies()`, `_read_settled_variant()`, `_append_or_write()`
- `tests/test_tier_derived_tools.py` - 15 new offline tests for the evidence/census additions
- `.planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md` - the committed D-07 verdict + D-19 census, live-derived against the real 66-company population
- `.planning/WINDOWS.md` - ids 13 (veto-guard failure) and 14 (Coffs Harbour, 5th staleness instance)
- `.planning/REQUIREMENTS.md` - TIER-02 checkbox + traceability marked complete; TIER-01's traceability row marked Blocked with the specific defect cited

## Decisions Made

- **D-07's gate is decided from evidence, not softened.** 7 defect rows are named explicitly (not summarized as "some mismatches"); the verdict text says FAIL and states plainly that D-06/D-08 stay gated. Re-run twice to rule out a transient/settling-lag explanation before committing the finding.
- **TIER-01 is left open, TIER-02 is marked complete.** These two requirements, though grouped in this plan's frontmatter, do not stand or fall together: TIER-02's own text ("the runtime null question is answered against live records before the choice is committed") is fully satisfied independent of the veto-guard bug, while TIER-01's own text ("verified against real records") is directly falsified by this task's own evidence. Marking both complete because the plan nominally targets both would have been exactly the "explain it away" behavior the phase's own decisions forbid.
- **Coffs Harbour Racing Club is a new WINDOWS.md entry, not an addition to `KNOWN_STUCK_IDS`.** Extending the gate's pre-registered exception list to absorb a newly-discovered case would make the gate pass by redefinition rather than by the derived property actually matching the enum everywhere it should. `KNOWN_STUCK_IDS` stays exactly the 4 ids `WINDOWS.md` already logged.
- **No attempt was made to fix the live formula.** D-16 declares zero company write windows for this plan; fixing the veto guard would be a property-schema change explicitly out of this plan's declared scope (pin/run-gate/render-census only) and is architecturally significant enough (it changes the shipped Plan 01 artifact) to belong to an operator decision, not a same-plan auto-fix.

## Deviations from Plan

### Auto-fixed / Disclosed Issues

**1. [Discovery, not scope creep -- disclosed] The D-07 gate found a real, previously-unverified defect: the veto guard never fires live**
- **Found during:** Task 2 (the live parity gate run)
- **Issue:** All 6 scored companies carrying `lv_anti_icp_flag=true` derive a score-based tier instead of `D` on `lv_icp_tier_derived`. This class of failure was never checked against real data before this task -- neither the spike (grammar-acceptance only) nor D-05's null probe (never set the flag on its disposable) exercised a real true-flag record.
- **Resolution:** Documented, not fixed. Rendered as a FAIL verdict with every offending row named (`render_evidence_markdown`'s verdict line, `render_census_markdown`'s SEVERITY callout), logged to `WINDOWS.md` (id 13), and left for Plan 04's checkpoint. Re-ran the live gate twice (byte-identical) and independently re-GET'd 3 of the 6 records outside the original batch read before treating this as established rather than a fluke.
- **Files affected:** `.planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md`, `.planning/WINDOWS.md`
- **Impact on later plans:** Plan 04's decision checkpoint (D-06/D-08) cannot proceed to retirement/WF1-shutdown while this stands. The fix itself (a `calculationFormula` PATCH) is out of this plan's scope and D-16's declared zero-write posture.
- **Committed in:** `894ec50` (parity gate), `d81e67c` (census SEVERITY callout), `a65233f` (WINDOWS.md)

**2. [Discovery, not scope creep -- disclosed] A 5th WF1-staleness instance not on the known list of 4**
- **Found during:** Task 2 (the live parity gate run)
- **Issue:** Coffs Harbour Racing Club (`14752488879`) reads `lv_icp_tier=Unscored` while `lv_icp_fit_score=25` (correctly `C`) and `lv_icp_tier_derived` correctly reads `C` -- the same root cause as `WINDOWS.md` ids 9-12 (a value-identical PATCH fires no property-change event, so WF1 never re-enrolled), but not previously logged.
- **Resolution:** Logged as `WINDOWS.md` id 14, kept OUT of `KNOWN_STUCK_IDS` (the gate's exception list stays exactly the pre-registered 4). Classified `defect` by the gate as designed -- this is evidence FOR the derived property, but the gate's own rule (any mismatch outside the 4 known ids is a defect) applies uniformly regardless of which side is "right."
- **Files affected:** `.planning/WINDOWS.md`
- **Impact on later plans:** None blocking -- this finding strengthens, rather than weakens, the case for the derived property.
- **Committed in:** `a65233f`

---

**Total deviations:** 2 disclosed discoveries (both genuine live-portal findings, not script bugs), 0 scope creep, 0 company writes.
**Impact on plan:** All 3 tasks' own `<acceptance_criteria>` are met exactly as written -- the plan never required the gate to PASS, only to be evaluated and rendered honestly. The gate FAILING is the correct, evidence-backed outcome of running it against real data for the first time.

## Issues Encountered

None beyond the two disclosed discoveries above. Every HubSpot call made by this plan was a read (`get_record` for the 66-record fetch, `search_records` for the total-portal-count and never-scored-count reads) -- zero `requests.{post,patch,delete}` calls anywhere in `scripts/check_tier_derived_parity.py` (D-16 held throughout, confirmed by reading the module, not merely asserted).

## User Setup Required

None - no external service configuration required. All commands were run using the dotenv-wrapper idiom against already-provisioned credentials, per the operator's standing waiver for this phase's read-only commands.

## Next Phase Readiness

- `50-TIER-PARITY-EVIDENCE.md` carries both the D-07 verdict (FAIL, 7 defects, 4 expected mismatches) and the D-19 census (DEFECT, D bucket empties 6->0) in one committed file -- Plan 04's `checkpoint:decision` is fully answerable from it without needing this SUMMARY.
- Plan 04 (D-06/D-08's retirement decision) is now a **more consequential decision than originally scoped**: the derived property is not a drop-in replacement for the stale enum today -- it is currently WORSE than the enum for vetoed records. The operator needs to decide between (a) fixing the veto guard formula and re-running this gate before any retirement decision, (b) some interim mitigation, or (c) a different path entirely. This plan does not recommend an option; it only makes the evidence and the consequence legible.
- `KNOWN_STUCK_IDS` remains exactly `{9605273630, 9604738976, 17696004613, 19100977027}` -- unchanged, per this plan's own prohibition against extending the gate's exception list to make it pass.
- `WINDOWS.md` now carries 10 open entries (was 8); ids 13-14 are new, both from this plan's own live evidence-gathering, neither from prior phases.

---
*Phase: 50-derived-tier-property*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 6 files claimed created/modified confirmed present on disk. All 4 commit hashes
(`c57a6ba`, `894ec50`, `d81e67c`, `a65233f`) confirmed present in git log.
