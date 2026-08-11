---
phase: 46-rubric-decision-simulation-engine-parity
plan: 05
subsystem: docs
tags: [icp-scoring, documentation-sync, rubric-weights, engine-inventory]

requires:
  - phase: 46-rubric-decision-simulation-engine-parity
    plan: 04
    provides: "config/icp_scoring.yaml and both HubSpot Automation v4 flows carrying the signed-off weights (individual_club_team=15, regulator=-20, gambling deduction removed), live-PUT and read-back-confirmed"
provides:
  - "Five live documents (docs/business/icp-scoring.md, CLAUDE.md, .planning/intel/constraints.md, .planning/intel/requirements.md, docs/WEB-RESEARCH-SPEC.md) agreeing numerically with config/icp_scoring.yaml"
  - "docs/business/icp-scoring.md carrying both the original closed-deal evidence and the recorded GTM override, citing 46-DECISION.md, per D-14"
  - "REQUIREMENTS.md RUBRIC-03 and ROADMAP.md's Phase 46 entry amended with the two-engine finding and criterion 3/4 status"
affects: [49-rescore]

actuals:
  tokens: 5200
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Evidence-preserving override annotation: when a GTM decision overrides closed-deal evidence in a business sign-off doc, the original finding (percentage + sample size) stays verbatim and a 'GTM override, citing <decision-doc>' sentence is appended next to it, rather than the evidence being edited to agree with the new number."

key-files:
  modified:
    - docs/business/icp-scoring.md
    - CLAUDE.md
    - .planning/intel/constraints.md
    - .planning/intel/requirements.md
    - docs/WEB-RESEARCH-SPEC.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "docs/business/icp-scoring.md's qualitative direction markers (the 'Club –' / 'club –' arrows in the Firmographic category row and the lv_org_type property-map row) were also updated to '+', beyond what the plan's action text explicitly named, because leaving them unchanged would have directly contradicted the newly-added override text in the same document stating clubs are no longer suppress/disqualify -- an internal-consistency bug (Rule 1), not scope creep."
  - "docs/WEB-RESEARCH-SPEC.md's FanDuel worked-example row ('deduction and veto') was fixed as the one site beyond D-13's table the plan's action text predicted the grep sweep would find. D-13's own table entry for line 159 ('gambling only drives graduated deductions, never a veto') turned out to be stale in a different way -- that line's text today describes revenue-band size conflicts, not gambling, at all; nothing gambling-related needed fixing there."
  - ".planning/intel/requirements.md's REQ-icp-scoring-model and REQ-graduated-deductions were updated beyond the plan's read_first-cited single line (REQ-anti-icp-vetoes), because they print the superseded +5/+5/-20 literal weight values directly and the plan's must_haves truth requires .planning/intel/requirements.md to 'agree numerically with config/icp_scoring.yaml' as a whole, not just at the one cited line. REQ-org-type-targeting and REQ-tiering were left untouched -- neither prints a numeric weight, both describe unchanged tier-band mechanics or evidence-derived framing outside this plan's declared edit surface."

patterns-established:
  - "Doc-sync verification via targeted grep sweep (excluding .planning/milestones/ and .planning/PROJECT.md) rather than trusting a pre-compiled target list alone -- catches sites a config-supersession event introduces after the target list was written."

requirements-completed: [RUBRIC-01, RUBRIC-03]

coverage:
  - id: D1
    description: "Five live documents no longer print a superseded org-type weight or gambling graduated deduction; all agree numerically with config/icp_scoring.yaml"
    requirement: "RUBRIC-01"
    verification:
      - kind: unit
        ref: "grep -rn \"individual_club_team:5|individual_club_team: 5|regulator:5|regulator: 5\" docs/ CLAUDE.md .planning/intel/ -- no matches"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (2527 passed, 128 skipped, unchanged from baseline)"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/business/icp-scoring.md preserves the Club/Team 19%/n=36 and gambling closed-deal findings verbatim, with the GTM override recorded alongside citing 46-DECISION.md, per D-14"
    requirement: "RUBRIC-01"
    verification:
      - kind: unit
        ref: "grep -n \"19%\\|n=36\\|46-DECISION.md\" docs/business/icp-scoring.md -- evidence and override citations both present"
        status: pass
    human_judgment: true
    rationale: "Whether the evidentiary voice is genuinely preserved (not merely the percentage strings) is a qualitative read of the prose, recorded here for a human reviewer to confirm against the diff rather than asserted by a script."
  - id: D3
    description: "REQUIREMENTS.md RUBRIC-03 and ROADMAP.md's Phase 46 entry carry dated amendment notes recording the two-engine finding, with the original requirement/criteria text left intact above each note"
    requirement: "RUBRIC-03"
    verification:
      - kind: unit
        ref: "grep -c '46-ENGINE-INVENTORY.md' .planning/REQUIREMENTS.md .planning/ROADMAP.md -- 2 and 3 respectively"
        status: pass
      - kind: unit
        ref: "git diff --stat .planning/ROADMAP.md -- 23 insertions, 0 deletions, confined to the Phase 46 section"
        status: pass
    human_judgment: false

duration: ~15min
completed: 2026-08-11
status: complete
---

# Phase 46 Plan 05: Documentation Sync & Engine-Count Amendment Summary

**Synced five live documents to the landed rubric weights (`individual_club_team` 5→15, `regulator` 5→-20, gambling deduction removed), preserving the closed-deal evidence and recording the GTM override alongside it in the business sign-off doc, and appended dated amendment notes to REQUIREMENTS.md and ROADMAP.md correcting the "three engines" claim to the two-engine finding from `46-ENGINE-INVENTORY.md`.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-08-11
- **Tasks:** 2 completed
- **Files modified:** 7

## Accomplishments

- `docs/business/icp-scoring.md`: scoring model table (`individual_club_team` +5→+15, new
  `regulator` −20 row), graduated-deductions table (gambling row removed), property-map table
  (`lv_anti_icp_flag` row no longer names gambling), Anti-ICP-deductions category row, tiers
  illustrative line, and the tier worked-example table (B row gains the club example at 45; C
  row's former club example replaced with an "other org type" example at 30; D row's Sportsbet
  example rewritten so it no longer states gambling produces a deduction) all updated. §4's
  best-fit/anti-ICP bullets restructured so clubs and gambling operators are no longer under
  "suppress/disqualify" or "graduated deduction" headings — each now carries a
  "Closed-deal evidence" statement (win rate and sample size preserved verbatim) immediately
  followed by a "GTM override" sentence citing `46-DECISION.md` D-01/D-02/D-03.
- `CLAUDE.md` §10.1's inline `config/icp_scoring.yaml` copy updated to the two weight values
  and `graduated_deductions: {}`; confirmed byte-identical to the live config file for the
  `base_score`→`graduated_deductions` block. §10.3's "Graduated deductions include" list no
  longer names `gambling_operator`.
- `.planning/intel/constraints.md`'s single-line machine-readable rubric mirror updated:
  `individual_club_team:15`, `regulator:-20`, `graduated_deductions {}`.
- `.planning/intel/requirements.md`: REQ-icp-scoring-model's org-type acceptance criteria
  (+15/−20, with an amendment note), REQ-anti-icp-vetoes' gambling statement (rewritten so the
  "never sets anti-ICP flag" half stays true while the "is a deduction" half no longer is), and
  REQ-graduated-deductions' gambling row (deduction removed, was −20) all updated.
- `docs/WEB-RESEARCH-SPEC.md`'s acceptance-test table: the Australian Turf Club row
  ("low-score path" → "Tier B path") and the FanDuel row ("deduction *and* veto" → veto via
  non-ANZ only, gambling no longer a deduction).
- `.planning/REQUIREMENTS.md` RUBRIC-03: new dated amendment appended below the existing
  2026-08-11 note, stating the two-engine finding and citing `tests/test_n8n_org_type_absence.py`
  as the permanent guard for the n8n leg's absence of a weight table. Original requirement text
  (including the "all three" wording) left intact above it, per the plan's instruction to record
  the correction rather than erase what was originally written.
- `.planning/ROADMAP.md`'s Phase 46 entry: new amendment block after success criterion 5,
  stating criterion 4 as NOT TRIGGERED (with its re-trigger conditions) and qualifying
  criterion 3 as satisfied at engine level while the live record-level parity sweep is expected
  red until Phase 49 closes the window — `git diff --stat` confirms the edit is purely additive
  and confined to the Phase 46 section (23 insertions, 0 deletions, no other phase touched).
- Full offline suite unchanged: **2527 passed, 128 skipped** (identical to the pre-plan
  baseline — this plan is documentation-only and touches no test-covered code path).

## Task Commits

1. **Task 1: Sync every live document that prints the superseded rubric** — `db7440d` (docs)
2. **Task 2: Record the engine-count amendment in REQUIREMENTS.md and ROADMAP.md** — `4484994`
   (docs)

## Files Created/Modified

- `docs/business/icp-scoring.md` — §4 anti-ICP bullets restructured (evidence + override), §5
  scoring model / graduated-deductions / property-map / category / tiers-illustrative / worked
  example tables all updated
- `CLAUDE.md` — §10.1 inline config copy, §10.3 graduated-deductions prose
- `.planning/intel/constraints.md` — CON-icp-scoring-config's rubric mirror line
- `.planning/intel/requirements.md` — REQ-icp-scoring-model, REQ-anti-icp-vetoes,
  REQ-graduated-deductions
- `docs/WEB-RESEARCH-SPEC.md` — §9 acceptance-tests table's Australian Turf Club and FanDuel rows
- `.planning/REQUIREMENTS.md` — RUBRIC-03 amendment note (appended, original text intact)
- `.planning/ROADMAP.md` — Phase 46 entry amendment block (appended after success criterion 5)

## Decisions Made

- **Fixed two additional stale "anti-ICP direction" markers beyond the plan's explicit list**
  (`docs/business/icp-scoring.md`'s Firmographic category row and the `lv_org_type` property-map
  row, both previously reading "club –"). The plan's action text didn't name these specifically,
  but leaving "club –" unedited directly beside the newly-added override text ("individual
  racing/turf clubs are a prime target... not suppress/disqualify") would have made the document
  internally contradictory within the same page — a correctness bug (Rule 1), not scope creep.
  Both changed to "+" (club) and an explicit "– – –" marker with a citation for regulator.
- **The one site beyond D-13's table** the plan's action text predicted the sweep would find was
  confirmed: `docs/WEB-RESEARCH-SPEC.md`'s FanDuel row ("deduction *and* veto"), not listed in
  D-13's own table (which named only the Turf Club row and a line-159 gambling sentence for this
  file). Separately, D-13's own line-159 citation turned out to be stale in a different way —
  that line's current text (`RO-2`) is entirely about revenue-band size conflicts, not gambling;
  no gambling-related text exists there today to fix.
- **`.planning/intel/requirements.md` was edited more broadly than the read_first's single cited
  line.** REQ-icp-scoring-model (org-type acceptance criteria) and REQ-graduated-deductions
  (gambling −20 row) both print literal superseded weight values and are covered by the plan's
  must_haves truth requiring the whole file to "agree numerically with config/icp_scoring.yaml,"
  not just the one line the read_first section named. REQ-org-type-targeting and REQ-tiering were
  deliberately left untouched — neither prints a numeric weight; REQ-org-type-targeting's
  evidence-derived framing sits outside this plan's declared edit surface for this file.

## Deviations from Plan

### Auto-fixed Issues

None — no bugs, blocking issues, or missing critical functionality encountered. The two items
above under "Decisions Made" are discretionary scope extensions within the plan's stated intent
("no live document prints a value the engine no longer computes" / "agree numerically"), not
fixes to broken behavior, and are recorded there rather than as Rule 1-3 deviations.

**Total deviations:** 0.

## Issues Encountered

- `docs/business/icp-scoring.md` contains vertical-tab (`\x0b`) characters inside several table
  cells (a Google-Docs-paste artifact predating this plan), which caused the `Edit` tool's exact
  string match to fail silently on two occurrences. Resolved by reading the file as raw bytes in
  Python, asserting the exact byte sequence before each replacement, and rewriting the file —
  no content was lost or altered beyond the intended edits (verified by `git diff` review below).

## Grep Sweep Confirmation

Beyond D-13's compiled table, the required sweep (excluding `.planning/milestones/` and
`.planning/PROJECT.md`) was run for: the literal weight patterns
(`individual_club_team:5`/`regulator:5`, in both spaced and unspaced form — zero matches
post-edit), and prose asserting gambling as a graduated deduction across `config/*.yaml`,
`docs/reports/*.md`, `.planning/*.md` outside the milestone archive and this phase's own
process artifacts. No further live-mirror site was found beyond the FanDuel row already
identified in the plan's action text. Files that mention "gambling" but are historical/point-in-
time records (`.planning/INGEST-CONFLICTS.md`, `.planning/STATE.md`, `.planning/MILESTONES.md`,
`.planning/debug/*`, `CHANGELOG.md`) were deliberately left alone — they document what was true
at ingestion/decision time, the same class of artifact the milestone archive exclusion protects,
not live rubric mirrors this plan's scope covers.

## Next Phase Readiness

- `RUBRIC-01` and `RUBRIC-03` both closed with documentation now in agreement; `RUBRIC-02`
  remains open (was already outside this plan's scope per `46-03-SUMMARY.md`'s division of
  labor).
- Phase 46 fully executed: 5/5 plans complete.
- Phase 49 inherits: the parity red window opened at Plan 04's commit `caae5d6` and remains open
  until Phase 49's full-population re-score, per the ROADMAP.md amendment note this plan added.
- No blockers.

## Self-Check: PASSED

All 7 modified files confirmed present with the expected content via grep re-checks above.
Both task commit hashes (`db7440d`, `4484994`) confirmed present in `git log --oneline --all`.
`git status --porcelain .planning/milestones/ .planning/PROJECT.md` printed nothing at both
commit points.

---
*Phase: 46-rubric-decision-simulation-engine-parity*
*Completed: 2026-08-11*
