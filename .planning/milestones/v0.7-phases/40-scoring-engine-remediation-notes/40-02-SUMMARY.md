---
phase: 40-scoring-engine-remediation-notes
plan: 02
subsystem: testing
tags: [pytest, hubspot, icp-scoring, parity-harness, regression-guard]

requires:
  - phase: 40-scoring-engine-remediation-notes/40-01
    provides: flow tooling (scripts/fetch_hubspot_flow.py, scripts/put_hubspot_flow.py),
      config/hubspot_flows/*.before.json archives, PORTAL-FACTS.md (lv_icp_tier enum,
      lv_icp_fit_score calculationFormula, D-05 API round-trip verdict)
provides:
  - tests/scoring_fixtures.py — disposable_company()/settle()/fetch_for_parity()/
    expected_for() shared by the pytest module and the script wrapper
  - tests/test_scoring_parity.py — offline oracle-vs-config tier (green, network-free)
    plus the live tier (RUN_LIVE_PARITY-gated) with every ENGINE-01..07/VETO-01..03
    requirement as a named -k selector, PARITY-02's F4/F7/F9/F10 named regression cases,
    and a collection-time completeness guard
  - scripts/run_scoring_parity.py — D-12 read-only scheduled sweep with a false-green
    guard (assertions_executed=0 always exits non-zero) and a JSON verdict report
affects: [40-03-veto-ownership-pipeline, 40-04-scoring-formula-and-content-term,
  40-05-revenue-boundary-fix, 40-06-tier-and-veto-workflow]

actuals:
  tokens: 7993
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Disposable-company lifecycle as a plain importable module (not a conftest) so a
      pytest test file and a standalone script share one implementation, never two"
    - "Env-var skipif (RUN_LIVE_PARITY) for live-gated pytest tests — no registered
      pytest marker, matching this repo's existing env-var-gated script convention"
    - "monkeypatch icp_scoring.load_yaml with a deep-copied, synthetically-extended
      config to exercise a code path (tier cutoffs) at boundary values the real
      multiples-of-5 rubric can never combine to produce"
    - "Offline-testable core (build_report()) separated from the network-touching CLI
      shell (main()), so a false-green guard can be proven with zero credentials"

key-files:
  created:
    - tests/scoring_fixtures.py
    - tests/test_scoring_parity.py
    - scripts/run_scoring_parity.py
  modified: []

key-decisions:
  - "Tier-boundary offline test (70/69/40/39/15/14/negative -> A/B/B/C/C/Unscored/Unscored)
    cannot be built from real config/icp_scoring.yaml component values -- every base_score
    entry (org_type, produces_content, geography, revenue_band, gambling) is a multiple of
    5, so 69/39/14 are unreachable through any real input combination. Resolved by
    monkeypatching src.icp_scoring.load_yaml to return a deep-copied config with one
    synthetic org_type key set to exactly the offset needed, so compute_icp_score's own
    cutoff branch is what's under test rather than a duplicated >= comparison living only
    in the test file."
  - "veto_clear_after_correction drives the D-02 documented refresh path
    (enrichment_requested=true + the 15-min poller) rather than expecting a HubSpot flow
    to clear the flag directly -- matches D-01/D-02's locked decision that the n8n
    pipeline, not HubSpot, owns lv_anti_icp_flag after remediation. This test is expected
    to fail until 40-03 lands the pipeline-side veto write."
  - "Live tests always create the disposable company with no lv_org_type at creation, then
    PATCH the target values in a separate call -- per 40-01-SUMMARY.md's finding that
    setting the target value at row creation does not fire flow enrollment (a
    property-change event is required)."
  - "F7/F9/F10 are thin aliases that call an already-defined named test (or one of its
    parametrized cases) directly, rather than duplicating assertion bodies -- satisfies
    PARITY-02's 'named, selectable regression case' requirement without a second
    hand-maintained copy of the same live scenario."

patterns-established:
  - "tests/scoring_fixtures.py as the disposable-company + oracle-comparison layer every
    later plan's own live tests and scripts/run_scoring_parity.py both import from."

requirements-completed: [PARITY-01, PARITY-02]

coverage:
  - id: D1
    description: "Offline oracle-vs-rubric tier: org-type sweep (9 keys), produces_content
      contribution, revenue-band table (9 bands incl. the exact 750000000 boundary),
      gambling deduction, and tier-band cutoffs at 70/69/40/39/15/14/negative -- all
      parametrized directly off config/icp_scoring.yaml, zero network, green the moment
      the task landed."
    requirement: "PARITY-01"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_scoring_parity.py -q (offline subset)"
        status: pass
      - kind: unit
        ref: "env -i PATH=\"$PATH\" .venv/bin/python -m pytest tests/test_scoring_parity.py -q (zero env vars, proves no network path)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Live tier + PARITY-02 named regression cases: every ENGINE-01..07/
      VETO-01..03 requirement has a named, selectable -k test; F4/F7/F9/F10 encoded as
      named cases with a collection-time completeness guard that fails if any of the four
      tokens disappears from the module."
    requirement: "PARITY-02"
    verification:
      - kind: unit
        ref: "pytest tests/test_scoring_parity.py --collect-only -q -k \"f4 or f7 or f9 or f10\" (collects 4 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_parity_02_named_case_completeness"
        status: pass
      - kind: unit
        ref: "per-selector --collect-only counts: engine_01=1, produces_content=4, revenue_boundary=19, gambling=5, org_type_sweep=19, f8_sub15=1, veto_set=4, veto_clear=1, tier_on_flag_change=1"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/run_scoring_parity.py: D-12 read-only scheduled tier with a
      false-green guard -- a run with zero executed assertions always exits non-zero and
      names the zero-assertion condition in the written report, never silently reports
      success."
    requirement: "PARITY-01"
    verification:
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_run_scoring_parity_zero_assertion_guard_offline"
        status: pass
      - kind: integration
        ref: "env -i PATH=\"$PATH\" HOME=\"$HOME\" PARITY_REPORT_DIR=/tmp/pr2 .venv/bin/python scripts/run_scoring_parity.py (no credentials, exits 1, writes assertions_executed:0)"
        status: pass
      - kind: unit
        ref: "grep -n \"create_record\\|patch_record\\|delete_record\\|disposable_company\" scripts/run_scoring_parity.py (no matches)"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-08-06
status: complete
---

# Phase 40 Plan 02: Standing Parity Harness Summary

**A two-tier pytest module (`tests/test_scoring_parity.py`) parametrized off `config/icp_scoring.yaml` with every phase requirement as a named `-k` selector, plus a read-only `scripts/run_scoring_parity.py` sweep whose false-green guard makes a zero-assertion run always fail — the standing drift guard every remaining plan in this phase turns green instead of hand-rolling its own check.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-08-06T06:26:00Z (approx, following 40-01's completion commit)
- **Completed:** 2026-08-06T06:48:00Z
- **Tasks:** 3
- **Files modified:** 3 (all created)

## Accomplishments
- `tests/scoring_fixtures.py`: `disposable_company()` context manager (portal-guarded, guaranteed `finally`-block teardown), `settle()` poller, and `fetch_for_parity()`/`expected_for()` — the single implementation both the pytest module and the script wrapper import, so D-11's two layers cannot drift apart
- Offline oracle-vs-rubric tier (26 tests, zero network — confirmed by running with `env -i`, no credentials): org-type sweep over all 9 config keys, `produces_content` (true/false/unset), all 9 revenue bands including the exact 750,000,000 boundary, the gambling deduction, and tier-band cutoffs at 70/69/40/39/15/14/negative (the last three via a monkeypatched config copy, since real rubric values are all multiples of 5)
- Live tier behind `RUN_LIVE_PARITY`: named, `-k`-selectable tests for every ENGINE-01..07/VETO-01..03 requirement, plus PARITY-02's F4/F7/F9/F10 named regression cases and a collection-time completeness guard that runs offline and can never be skipped away
- `scripts/run_scoring_parity.py`: the D-12 read-only scheduled tier, GET/search-only (grep-verified no create/patch/delete-record or disposable-company import), writing a dated JSON verdict report with a false-green guard proven by an offline unit test
- All acceptance criteria from the plan's `<verification>` block confirmed live: offline suite green, full 2232-test suite green, `--collect-only -k "f4 or f7 or f9 or f10"` collects exactly 4, and the wrapper exits non-zero on a zero-assertion run

## Task Commits

1. **Task 1: Disposable-company fixture helper and the offline oracle-vs-rubric tier** - `28a5bf4` (feat)
2. **Task 2: Live parity tier and the PARITY-02 named regression cases** - `433d5f7` (feat)
3. **Task 3: Read-only sweep wrapper with a false-green guard and JSON verdict report** - `9f59886` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `tests/scoring_fixtures.py` - disposable-company lifecycle, poller, and oracle-comparison helpers shared by the test module and the script
- `tests/test_scoring_parity.py` - offline oracle-vs-config tier + live tier + PARITY-02 completeness guard + the zero-assertion-guard unit test
- `scripts/run_scoring_parity.py` - D-12 read-only sweep wrapper with a JSON verdict report and false-green guard

## Decisions Made
- **Tier-boundary offline test via monkeypatched config, not a duplicated comparison.** Real `config/icp_scoring.yaml` component values are all multiples of 5 (org `{0,5,20,40}`, content `{0,20}`, geography `{0,10}`, revenue `{0,10,-5,-15,-30,-50}`), so the boundary scores this plan's `<behavior>` block names (69, 39, 14) are unreachable through any real input combination. Rather than duplicate `src/icp_scoring.py`'s `>=` cutoff expression in the test file (which would test a copy, not the oracle), the test monkeypatches `icp_scoring.load_yaml` to return a deep-copied config with one synthetic org-type key set to the exact offset needed — `compute_icp_score`'s own cutoff branch is what's under test.
- **`test_veto_clear_after_correction` drives the D-02 refresh path**, not a direct HubSpot-side clear: sets `enrichment_requested=true` after correcting the region, matching the locked decision that the n8n pipeline (not a HubSpot workflow) owns `lv_anti_icp_flag` after remediation (D-01/D-02). This test is correctly expected to fail until 40-03 lands the pipeline write.
- **Live tests always create-then-PATCH**, never set the target value at company creation — per 40-01-SUMMARY.md's finding (also recorded in PORTAL-FACTS.md) that flow enrollment requires a genuine property-change event, not a value present at row creation.
- **F7/F9/F10 are thin aliases** that call the already-defined named test (`test_tier_on_flag_change_without_score_change`, `test_gambling_deducts_20_without_veto`, `test_revenue_boundary_bands("750M-1B", ...)`) directly rather than duplicating assertion bodies — satisfies "named, selectable regression case" without a second hand-maintained copy of the same live scenario.

## Deviations from Plan

None — plan executed exactly as written. One addition beyond the plan's literal task text: Task 1 added a single placeholder `@live`-decorated test (`test_live_gate_configured_placeholder`) so Task 1's own verify command already satisfied its acceptance criterion "reports at least one skipped test" before Task 2's real live tests existed. Task 2 removed the placeholder once superseded by the real named cases (Rule 1 — the plan's Task 1 acceptance criteria required a skip that only the live-tier tests, written in Task 2, could otherwise provide).

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. All work in this plan is offline (pytest against `config/icp_scoring.yaml` and `src/icp_scoring.py`) or gated behind `RUN_LIVE_PARITY`/HubSpot credentials that no test in this plan actually exercised live.

## Next Phase Readiness
- The named `-k` selectors this plan defines (`engine_01`, `produces_content`, `revenue_boundary`, `gambling`, `org_type_sweep`, `f8_sub15`, `veto_set`, `veto_clear`, `tier_on_flag_change`, `f4`, `f7`, `f9`, `f10`) are ready for every remaining plan in this phase (40-03 veto ownership, 40-04 content/gambling terms, 40-05 revenue boundary, 40-06 tier/veto workflow) to run as their own `<verify>` command instead of a hand-rolled ad-hoc check.
- All live tests are currently RED by design (skipped when `RUN_LIVE_PARITY` is unset; would fail if run today, since the flow fixes they assert on haven't landed yet except the org-type points 40-01 already fixed). This is the intended state per the plan's own text, not a defect.
- `scripts/run_scoring_parity.py` is ready for the D-12 scheduled cadence once real companies carry `lv_icp_fit_score` values to sample (currently 0/712 outside the 40-01 flow-validation disposables, per PORTAL-FACTS.md) — Phase 41's backfill is what populates a meaningful sample.

---
*Phase: 40-scoring-engine-remediation-notes*
*Completed: 2026-08-06*

## Self-Check: PASSED

All 3 files listed above confirmed present on disk. All 3 task commits (`28a5bf4`,
`433d5f7`, `9f59886`) confirmed present in `git log --oneline --all`.
