---
phase: 46-rubric-decision-simulation-engine-parity
plan: 02
subsystem: scoring
tags: [icp-scoring, hubspot, simulation, rubric-decision, pytest]

requires:
  - phase: 46-rubric-decision-simulation-engine-parity
    plan: 01
    provides: "compute_icp_score(record, candidate_patch, cfg=None) additive override, scripts/simulate_rubric_weights.py's proven zero-write tracer core (PROPOSED_OVERRIDES with D-01 only, build_proposed_cfg, simulate_row, main), 46-ENGINE-INVENTORY.md's two-engine finding"
provides:
  - "scripts/simulate_rubric_weights.py extended: PROPOSED_OVERRIDES carries all three decided levers (D-01/D-02/D-03), SCENARIOS (club weight 10/15/20), _select_row_ids (live HAS_PROPERTY query), build_simulation (full RUBRIC-02 payload), render_markdown, _write_report, cli_main"
  - ".planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md -- the committed, live, per-company before/after report Plan 03's operator sign-off checkpoint reads"
  - ".planning/phases/46-rubric-decision-simulation-engine-parity/46-simulation-20260811.json -- the JSON twin"
affects: [46-03-decision-signoff, 46-04-weight-commit, 46-05-parity, 49-rescore]

actuals:
  tokens: 22500
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "dotted-path override list with a shared _set_dotted helper, reused unchanged across build_proposed_cfg (fixed value) and build_scenario_cfg (one path's value swapped per call) -- single source of truth for 'every weight this simulation proposes'"
    - "fetch-once-per-id: one live/stub props dict scored under N cfgs (primary + sensitivity), never refetched per scenario"
    - "cross-check-only reference file (41-final-population.json) used both for row-set divergence and for a name lookup the primary fetch path (FIT_SCORE_PROPS) doesn't carry -- read once, never the simulation's source of truth"

key-files:
  created:
    - .planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md
    - .planning/phases/46-rubric-decision-simulation-engine-parity/46-simulation-20260811.json
  modified:
    - scripts/simulate_rubric_weights.py
    - tests/test_simulate_rubric_weights.py

key-decisions:
  - "D-02's regulator weight expressed as a direct base_score.org_type value (-20), not a new graduated_deductions key -- per 46-RESEARCH.md Open Question 5's live-executed finding, superseding 46-CONTEXT.md D-06's 'new engine logic' framing. build_proposed_cfg's graduated_deductions dict is confirmed empty ({}) after all three overrides apply, proving no new key was added."
  - "D-10 flags (blank_org_type, false_veto) computed only from properties already in tests/scoring_fixtures.py::FIT_SCORE_PROPS -- no property added to that shared list. false_veto requires the live string 'true' on lv_anti_icp_flag, 'Non-ANZ geography' present in lv_anti_icp_reason, and lv_country_region_normalized blank -- all three, not any one alone."
  - "Company names for the markdown table are sourced from 41-final-population.json's cross-check snapshot rather than a second live fetch or a FIT_SCORE_PROPS addition -- 'name where available' is satisfied without doubling API calls per row."
  - "Movement summary compares oracle-current -> oracle-proposed (not live -> proposed), isolating the weight change's own effect from pre-existing live-vs-oracle divergence (the 17 false vetoes, 18 blank org types) that Phase 47/48 own, not this phase."
  - "Reworded a docstring passage that named config/june_candidates.json literally in prose, after the grep acceptance criterion caught it failing against its own explanatory comment -- same trap 46-01-SUMMARY.md already documented once for write-function names."

patterns-established: []

requirements-completed: []  # RUBRIC-02 intentionally left unmarked -- see Deviations/Requirements Note below. Plan 03's operator sign-off checkpoint is still owed before the requirement's user-facing bar closes.

coverage:
  - id: D1
    description: "PROPOSED_OVERRIDES carries all three decided levers; no new graduated_deductions key is added by D-02's expression"
    requirement: "RUBRIC-02"
    verification:
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_proposed_overrides_carries_all_three_levers"
        status: pass
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_build_proposed_cfg_adds_no_new_graduated_deductions_key"
        status: pass
    human_judgment: false
  - id: D2
    description: "SCENARIOS defines exactly three scenarios differing only by club weight (10/15/20); club_15 is byte-identical to the primary override set"
    verification:
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_scenarios_differ_only_by_club_weight"
        status: pass
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_build_scenario_cfg_club_15_matches_build_proposed_cfg"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-02/D-03 worked examples (regulator 35->10/Unscored, gambling 60->80) reproduce exactly; false-veto rows keep live and oracle-current tiers distinct; blank-org_type rows are flagged and contribute 0 org-type points under both rubrics"
    verification:
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_regulator_moves_to_10_unscored_under_proposed"
        status: pass
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_gambling_row_gains_20_under_proposed"
        status: pass
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_false_veto_row_keeps_live_and_oracle_columns_distinct"
        status: pass
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_blank_org_type_row_is_flagged_in_build_simulation"
        status: pass
    human_judgment: false
  - id: D4
    description: "An empty row set produces a loud failure verdict and non-zero exit, never a silent 'nothing changed'"
    verification:
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_empty_row_set_yields_failure_verdict_and_nonzero_exit"
        status: pass
    human_judgment: false
  - id: D5
    description: "Row-set divergence against 41-final-population.json is recorded as a finding (both counts and symmetric difference), never silently reconciled -- proven offline against the real committed cross-check file, then confirmed live at symmetric difference 0"
    verification:
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_row_set_divergence_finding_populated_against_cross_check"
        status: pass
      - kind: manual
        ref: "Live run: .planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md header line 6 -- live=66, cross-check=66, symmetric difference=0 (sets match exactly)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The simulation still cannot write to any HubSpot record after Plan 02's growth -- Plan 01 Task 3's zero-write proof (static scan, namespace scan, behavioural stub) passes unchanged"
    verification:
      - kind: unit
        ref: "tests/test_simulate_rubric_weights.py::test_zero_write_static_scan_finds_no_write_import, test_zero_write_namespace_scan_finds_no_write_binding, test_zero_write_behavioural_stub_records_read_only_calls"
        status: pass
    human_judgment: false
  - id: D7
    description: "The committed report shows the operator, per company, what HubSpot says today, what the oracle says today, and what the oracle would say under the proposed weights, with the 17 false-veto and 18 blank-org_type rows visibly flagged and the sensitivity at club weight 10/20 stated alongside the primary 15"
    verification:
      - kind: manual
        ref: "46-SIMULATION-REPORT.md read in full this session -- 66-row per-company table, Tier Distribution + Sensitivity sections, Movement Summary by lv_org_type, every flagged row carries a visible Flags column entry"
        status: pass
    human_judgment: true

duration: ~35min
completed: 2026-08-11
status: complete
---

# Phase 46 Plan 02: Rubric Simulation Expansion & Live Report Summary

**Grew Plan 01's one-record tracer into the full RUBRIC-02 simulation (all three decided
weights, club-weight sensitivity at 10/15/20, D-10 flags, live row selection) and ran it
against the live 66-company scored population, producing the committed before/after
report the operator signs off against in Plan 03.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-11T08:05:00Z
- **Tasks:** 2 completed
- **Files modified:** 4 (2 code/test, 2 new committed report artifacts)

## Accomplishments
- `PROPOSED_OVERRIDES` grew from Plan 01's single D-01 entry to all three decided levers:
  `individual_club_team -> 15`, `regulator -> -20` (a **direct** `base_score.org_type`
  weight per 46-RESEARCH.md's live-executed Open Question 5 finding, not a new
  `graduated_deductions` key -- resolves the CONTEXT.md "Claude's Discretion" bullet and
  supersedes D-06's "new engine logic" framing), and `graduated_deductions.gambling_operator`
  deleted outright.
- `SCENARIOS` adds club-weight sensitivity at 10/15/20 (`build_scenario_cfg`), reported as
  tier-only counts so the operator sees the Tier B floor's proximity without a third full
  score table.
- `_select_row_ids` mirrors `run_scoring_parity.py::_select_sample_ids` exactly -- no
  second definition of "the scored population" -- and `build_simulation` adds the row-set
  cross-check against `41-final-population.json` (reference only, never the source),
  D-10 row flags (`blank_org_type`, `false_veto`), a tier-distribution summary, a
  sensitivity tier-count distribution, and a movement summary broken down by `lv_org_type`.
- `render_markdown`/`_write_report` emit the D-09 deliverable; `main()` is kept as a thin
  wrapper over `build_simulation` so Plan 01 Task 3's zero-write proof needed zero edits.
- Live run against portal `22617666`: **66 rows simulated**, row set matches
  `41-final-population.json` **exactly** (symmetric difference 0) -- the "the 66" claim in
  PROJECT.md/RESEARCH.md is confirmed current, not stale, as of this session.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend the simulation to the full live row set, with annotations and sensitivity** - `e456091` (feat)
2. **Task 2: Run the simulation live and commit the report** - `8d7caa6` (docs)

## Files Created/Modified
- `scripts/simulate_rubric_weights.py` - `PROPOSED_OVERRIDES` (3 entries), `SCENARIOS`,
  `build_scenario_cfg`, `_row_flags`, `_load_cross_check_names`, `_row_set_finding`,
  `_select_row_ids`, `build_simulation`, `render_markdown`, `_write_report`, `cli_main`
- `tests/test_simulate_rubric_weights.py` - 25 tests total (12 new/rewritten, 13 preserved
  from Plan 01 unchanged in assertion content, including all three zero-write tests)
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md` -
  the committed live report
- `.planning/phases/46-rubric-decision-simulation-engine-parity/46-simulation-20260811.json` -
  the JSON twin

## Decisions Made
- **D-02 expressed as a direct weight, not a new engine branch.** `build_proposed_cfg`'s
  `graduated_deductions` dict is empty (`{}`) after all three overrides apply -- proven by
  a dedicated test -- confirming no new key is added anywhere, matching RESEARCH.md's
  finding and CONTEXT.md's own discretion bullet.
- **Movement summary compares oracle-current -> oracle-proposed**, not live -> proposed.
  This isolates the weight change's own effect from the pre-existing 17 false-veto /
  18 blank-org_type divergence between live HubSpot and the oracle -- those belong to
  Phase 47/48, not this phase's movement count. Live result: 14 of 66 rows change tier,
  all `individual_club_team` (C -> B), matching D-01's blast-radius estimate almost exactly
  (37 clubs in the June snapshot, but only 24 carry a live, non-blank `individual_club_team`
  value in the actual scored population -- of those, 14 sit below the B floor today).
- **Company names sourced from the cross-check snapshot**, not a second live fetch or a
  `FIT_SCORE_PROPS` addition -- avoids doubling the live API call count for a purely
  cosmetic table column, while still satisfying "name where available" (rows only in the
  live set and not in the snapshot would show `(name unavailable)`; none did this run).
- **Reworded a docstring passage that named `config/june_candidates.json` literally.** The
  file's own explanatory prose ("this script never reads june_candidates.json") tripped
  the plan's own `grep -c june_candidates` acceptance check. Reworded to describe the
  constraint without the literal filename -- the same class of self-inflicted grep failure
  46-01-SUMMARY.md already documented once for write-function names in comments.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring/comment text tripped the plan's own `june_candidates` grep acceptance check**
- **Found during:** Task 1, immediately after first writing the extended docstring
- **Issue:** Two prose lines explaining that this script never reads
  `config/june_candidates.json` contained the literal string `june_candidates`, so
  `grep june_candidates scripts/simulate_rubric_weights.py` (the plan's own acceptance
  criterion) matched them -- a self-inflicted failure of exactly the shape 46-01-SUMMARY.md
  already recorded once for write-function names in prose.
- **Fix:** Reworded both passages to describe the constraint (the June-dated candidate
  research snapshot is never read, under any name) without spelling out the literal
  filename.
- **Files modified:** scripts/simulate_rubric_weights.py
- **Verification:** `grep -n june_candidates scripts/simulate_rubric_weights.py` returns
  no matches; `.venv/bin/python -m pytest tests/test_simulate_rubric_weights.py -q` still
  25/25 passing
- **Committed in:** e456091 (part of Task 1's commit -- fixed before commit, no separate
  commit needed)

**Total deviations:** 1 auto-fixed (self-inflicted grep failure in prose, caught and fixed
before Task 1's commit). No scope creep, no other issues encountered.

## Issues Encountered
None beyond the one deviation documented above. Live credentials were reachable
throughout the session (`HUBSPOT_PRIVATE_APP_TOKEN` present, `HUBSPOT_PORTAL_ID` ==
`22617666` after `load_dotenv()`), so Task 2's precondition was met without an operator
hand-off -- no credential-blocked halt occurred.

## Live Run Findings (for Plan 03's decision record)

- **Row count:** 66, exact match against `41-final-population.json`'s 66-id snapshot
  (symmetric difference 0 -- the snapshot is confirmed current as of this session, not
  stale as RESEARCH.md's caveat flagged as a possibility).
- **Tier movement (oracle-current -> oracle-proposed, primary club=15 scenario):** 14 of 66
  rows change tier. All 14 are `individual_club_team` moving C -> B. No other org type
  moves under any of the three levers on this live population.
- **D-02 (regulator) live check:** the one live regulator record (Queensland Racing
  Integrity Commission, `16047156820`) already carries a genuine hard veto today (live
  score 25/D, not the CONTEXT.md worked example's hypothetical veto-free 35/C) -- so its
  D-02 effect (score 25 -> 0) does not move its tier; it was D before and stays D after.
- **D-03 (gambling) live check:** both live gambling-flagged records (Entain `10024564084`,
  Sportsbet `17861423879`) already carry genuine hard vetoes independent of gambling status
  -- their D-03 effect is score-only (-70 -> -50, 0 -> 20), neither moves tier. This is a
  materially different outcome from CONTEXT.md D-03's "~1 record actually moves" estimate,
  which was based on the June snapshot's org-type mix, not a live veto check -- worth
  surfacing plainly in `46-DECISION.md` rather than silently reconciling.
- **Sensitivity (club weight 10 vs 20):** identical tier distributions to the primary
  (club=15) scenario across the whole live population -- every affected record's total
  clears the B floor (40) even at club=10, and none crosses into A even at club=20. The
  Tier B floor is not fragile on this specific population, though CONTEXT.md's own
  rejection of club=10 (as a config choice) stands on its own merits regardless of this
  particular population's insensitivity to it.

## Requirements Note

`RUBRIC-02` is listed in this plan's frontmatter but deliberately left **unmarked** in
REQUIREMENTS.md (`requirements-completed: []` above), matching Plan 01's precedent. This
plan produces the simulation artefact RUBRIC-02 requires, but the requirement's full bar
(per CONTEXT.md D-05: "the phase does not close until the operator accepts or overrides")
needs Plan 03's blocking sign-off checkpoint. `46-SIMULATION-REPORT.md` is now the evidence
Plan 03's `46-DECISION.md` cites directly.

## Next Phase Readiness
- `46-SIMULATION-REPORT.md` and its JSON twin are committed and ready for Plan 03 to cite
  in `46-DECISION.md`.
- The three live findings above (QRIC/Entain/Sportsbet already-vetoed, sensitivity
  insensitivity) are new information relative to CONTEXT.md's June-snapshot-derived
  estimates -- Plan 03 should record them plainly rather than silently reconcile them
  against the earlier estimates.
- `config/icp_scoring.yaml` remains byte-identical on disk -- no weight has been committed
  anywhere in this wave, matching the plan's deliberate ordering (config change lives in
  Plan 04, gated behind Plan 03's blocking sign-off).
- No blockers.

## Self-Check: PASSED

Both files confirmed present on disk (`.planning/phases/46-rubric-decision-simulation-engine-parity/46-SIMULATION-REPORT.md`,
`46-simulation-20260811.json`); both task commit hashes (`e456091`, `8d7caa6`) confirmed
present in `git log --oneline --all`.

---
*Phase: 46-rubric-decision-simulation-engine-parity*
*Completed: 2026-08-11*
