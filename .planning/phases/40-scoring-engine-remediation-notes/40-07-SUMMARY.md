---
phase: 40-scoring-engine-remediation-notes
plan: 07
subsystem: crm-automation
tags: [hubspot, batch-api, backfill, icp-scoring, parity-harness, pytest]

requires:
  - phase: 40-scoring-engine-remediation-notes/40-02
    provides: tests/scoring_fixtures.py (disposable-company lifecycle, settle(),
      fetch_for_parity()/expected_for()), tests/test_scoring_parity.py's live tier and
      PARITY-02 named cases, scripts/run_scoring_parity.py's read-only sweep + false-green
      guard
  - phase: 40-scoring-engine-remediation-notes/40-04
    provides: five-term lv_icp_fit_score formula and its two new component properties
      (produces_content_score, gambling_score)
  - phase: 40-scoring-engine-remediation-notes/40-05
    provides: geography/revenue flows retargeted to canonical lv_* inputs; D-01's veto
      handover complete (n8n pipeline is the sole writer of lv_anti_icp_flag)
  - phase: 40-scoring-engine-remediation-notes/40-06
    provides: WF1's corrected tier ladder (sub-15 grades Unscored, not D) and its second
      enrollment trigger on lv_anti_icp_flag
provides:
  - batch_update_companies() in src/hubspot_client.py -- POST
    /crm/v3/objects/companies/batch/update, dry_run-first, chunking-caller-owned
  - scripts/backfill_seed_company_scores.py -- D-10's component-seeding backfill
    mechanism, two-key gated (DRY_RUN=false + ALLOW_SCORE_BACKFILL=true), hard sample cap
    enforced in-script (BACKFILL_MAX_RECORDS, default 10, hard ceiling 25)
  - ENGINE-01 closed: live-proven, entirely inside HubSpot, off canonical inputs only
  - PARITY-01's committed verdict artifact: parity-report-final.json, with a
    documented-divergence classifier distinguishing the accepted 40-02 Needs Review case
    from a real finding
  - Portfolio-wide measurement: exactly one real company (of 711) carries any canonical
    lv_* scoring input -- confirms the 712-population backfill is genuinely Phase 41's job
  - Empirical confirmation that VETO-01/VETO-02 remain open (pipeline write-gate arming
    gate), not fixed by this plan and not a regression it introduces
affects: [41-portfolio-backfill-and-data-import]

actuals:
  tokens: 62000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "compute_components() in the backfill script calls compute_icp_score() and reads
      result.breakdown rather than re-implementing a point lookup -- guarantees points
      route through src/icp_scoring.py's loaded config/icp_scoring.yaml with zero
      duplication, and the config-mutation test (proving no second table) falls out for
      free"
    - "Sample-cap enforcement lives inside the script itself (enforce_sample_cap()), not
      trusted to the caller or an env-var convention alone -- an operator-supplied
      BACKFILL_MAX_RECORDS above the hard ceiling is clamped, not honored"
    - "run_scoring_parity.py's build_report() now separates 'mismatch' (raw
      triple-inequality) from 'real_finding' (a mismatch that isn't the accepted,
      documented Needs Review divergence) -- the committed verdict can PASS with
      classified divergences on record, never silently hiding a real disagreement inside
      a blanket FAIL or a blanket PASS"

key-files:
  created:
    - scripts/backfill_seed_company_scores.py
    - tests/test_backfill_seed_company_scores.py
    - .planning/phases/40-scoring-engine-remediation-notes/parity-report-final.json
    - .planning/phases/40-scoring-engine-remediation-notes/parity-report-20260806.json
  modified:
    - src/hubspot_client.py
    - scripts/run_scoring_parity.py
    - tests/test_scoring_parity.py
    - .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "compute_components() restricts the props it hands to HubSpotRecord to exactly the
    five canonical inputs (never native `country`/`annualrevenue`) so the backfill
    mirrors the flows' own lv_*-only triggers (40-05's retarget), not the oracle's
    broader native-field fallback path."
  - "Default sample selection is the union (deduped) of HAS_PROPERTY searches across the
    five canonical inputs -- the plan's literal 'at least one populated' rule. This
    returned exactly one real company portfolio-wide (Melbourne Racing Club, id
    9604614548), which became both Task 2's proving sample and Task 3's PARITY-01
    real-record sample per D-09's stated overlap."
  - "VETO-01/VETO-02 left open, not force-closed. The plan's Task 3 text says any live
    failure is 'a real gap ... fix the flow or the pipeline, never the assertion,' but
    the 5 failing veto_set/veto_clear cases are blocked on a deliberate security
    decision (ALLOW_HUBSPOT_RECORD_WRITES baked false, armed only via a bounded,
    operator-invoked scheduled_arm.py companion per VETO-WRITE-EVIDENCE.md) -- not a
    bug in the flow or pipeline. Arming that companion is outside this plan's <action>
    text and outside 40-03/40-05/40-06's own stated scope boundary for these same two
    requirements. Confirmed empirically (not theorized) and documented in full rather
    than silently retried or weakened."
  - "scripts/run_scoring_parity.py's flag comparison corrected to boolean-equivalence
    (Rule 1, third instance of the None-vs-'false' defect class 40-05/40-06 each fixed
    once in the pytest live tier) -- a never-enriched real record reads
    lv_anti_icp_flag=None, not 'false', since D-01's handover means only the n8n
    pipeline writes it. This is a harness-semantics fix in the read-only sweep script,
    not a weakened pytest assertion (the plan's prohibition targets the latter)."
  - "WINDOWS.md #4 fixed in the same commit (Rule 1): test_veto_clear_after_correction
    patched the wrong poller-search property name (enrichment_requested instead of
    lv_enrichment_requested), a pre-existing, already-logged, open bug in this exact
    file. Fixing it does not flip the test green -- it fails earlier, at its own first
    veto-setting assertion, for the same structural write-gate reason as the other four
    -- but it is a real, independently-verifiable defect and Rule 1 applies regardless
    of whether the fix changes the test's pass/fail outcome."

patterns-established:
  - "batch_update_companies()'s dry_run-first discipline (never hs_headers()/token
    printed, sentinel-return short-circuit) as the template for any future batch-write
    helper in src/hubspot_client.py."
  - "compute_icp_score()'s breakdown as the canonical points source for any future
    script that needs component-level scoring outside the pipeline itself."

requirements-completed: [ENGINE-01, PARITY-01]

coverage:
  - id: D1
    description: "batch_update_companies() added to src/hubspot_client.py, mirroring
      create_record/patch_record's dry_run-first discipline. Two deviations from
      create_record's shape, both load-bearing for the backfill caller: an empty
      updates list short-circuits in both dry_run and live mode, and a >100-entry list
      raises rather than being silently truncated."
    requirement: "ENGINE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py (7 tests): dry-run makes no
          network call, payload envelope is exactly {\"inputs\": [...]}, no
          Authorization/Bearer in printed output, 101-entry list raises, empty list
          short-circuits in both modes, live mode calls requests.post with the expected
          shape"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/backfill_seed_company_scores.py: D-10's component-seeding
      mechanism. compute_components() reads points via src/icp_scoring.py's loaded
      config/icp_scoring.yaml (never a second table); writes all five components
      together (never a subset -- a missing term blanks the calculated sum, per
      PORTAL-FACTS.md's Task 1 finding); never writes lv_icp_fit_score/_tier/_flag/
      _reason. Two-key arm (DRY_RUN=false AND ALLOW_SCORE_BACKFILL=true), portal guard,
      hard sample cap enforced in-script (default 10, hard ceiling 25, never trusted to
      the caller)."
    requirement: "ENGINE-01"
    verification:
      - kind: unit
        ref: "tests/test_backfill_seed_company_scores.py (13 tests): component
          computation across every org type/region case/all nine revenue bands/both
          gambling values, missing-input zeroing, the config-mutation proof that points
          route through src/icp_scoring.py (not a second table), the sample-cap and
          arming gates, the never-writes-derived-fields guard"
        status: pass
      - kind: e2e
        ref: "live armed run against the real-record sample (Melbourne Racing Club, id
          9604614548): seeded org_type_score=5, geography_score=10,
          annual_revenue_score=0, produces_content_score=0, gambling_score=0; settled
          live in ~11s to lv_icp_fit_score=15, lv_icp_tier=C, lv_anti_icp_flag stayed
          null (no veto fired, no HubSpot workflow writes the flag post-D-01)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Portfolio-wide canonical-input population measured live (read-only
      HAS_PROPERTY search per field): exactly one company anywhere in the 711-company
      portal carries any canonical lv_* input at all. Confirms the 712-population
      backfill genuinely belongs to Phase 41 (per D-09), not deferred prematurely by
      this plan's scope."
    requirement: "ENGINE-01"
    verification:
      - kind: other
        ref: "read-only search_records HAS_PROPERTY per canonical field, portal 22617666,
          2026-08-07: lv_org_type=1, lv_country_region_normalized=1 (same record),
          lv_produces_content=0, lv_revenue_band=0, lv_is_gambling_operator=0,
          lv_is_hardware_vendor=0 -- recorded in PORTAL-FACTS.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "ENGINE-01 proven live end to end: the flagship case (governing body +
      content + AU + 50-500M) reaches lv_icp_fit_score=80 and lv_icp_tier=A entirely
      inside HubSpot, off canonical inputs only, with the exact five-component
      breakdown the requirement names."
    requirement: "ENGINE-01"
    verification:
      - kind: e2e
        ref: "live disposable (auto-deleted): org_type_score=40,
          produces_content_score=20, geography_score=10, annual_revenue_score=10,
          gambling_score=0 -> lv_icp_fit_score=80, lv_icp_tier=A"
        status: pass
      - kind: e2e
        ref: "RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k engine_01
          (included in the 56/56 full-tier pass)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full live fixture tier run, excluding the 5 pipeline-write-gate-arming
      cases: 56/56 passed, covering every named ENGINE-01..07/F4/F7/F8/F9/F10 selector
      not dependent on an armed n8n pipeline write."
    requirement: "PARITY-01"
    verification:
      - kind: e2e
        ref: "RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k \"not
          (veto_set or veto_clear or multiple_reasons)\" -- 56 passed, 5 deselected"
        status: pass
    human_judgment: false
  - id: D6
    description: "The 5 excluded cases (veto_set x3, multiple_reasons, veto_clear)
      confirmed empirically -- not theorized -- to fail because setting veto-input
      properties alone never dispatches the n8n pipeline under this portal's actually-
      configured webhook subscriptions. This is the pre-existing VETO-01/VETO-02
      operational gate, out of this plan's scope per 40-03/40-05/40-06 precedent, not a
      regression this plan introduces."
    requirement: "PARITY-01"
    verification:
      - kind: e2e
        ref: "individual live runs of all 5 cases: lv_anti_icp_flag reads None (not
          \"true\") after a raw patch of veto-input properties with no pipeline
          dispatch trigger set; fast-fails (~8-40s, well under settle()'s 120s timeout)
          since the value genuinely never changes"
        status: pass
      - kind: other
        ref: "WINDOWS.md id 5 (open) records the gate for Phase 41/future-phase
          visibility"
        status: pass
    human_judgment: true
    rationale: "Confirming these tests are structurally blocked (not flaky, not a bug
      this plan can fix) required judgment about which layer owns the gap (deliberate
      security posture vs. defect) -- flagged for the record per the plan's own
      instruction that any live failure needs explicit classification, not silent
      absorption."
  - id: D7
    description: "PARITY-01's committed verdict: parity-report-final.json,
      assertions_executed=1 > 0, rubric_version=lv-icp-v0.1, real-record sample =
      [9604614548] (same as Task 2's backfill sample, per D-09's stated overlap), PASS
      with 1 documented Needs Review divergence and 0 real findings. The flag-comparison
      Rule 1 fix and the divergence classifier (_classify_mismatch) both added to
      scripts/run_scoring_parity.py so the verdict distinguishes the accepted 40-02
      divergence from a genuine disagreement, never absorbing the latter silently."
    requirement: "PARITY-01"
    verification:
      - kind: unit
        ref: "tests/test_scoring_parity.py: test_run_scoring_parity_flag_matches_treats_none_as_not_vetoed,
          test_run_scoring_parity_classifies_needs_review_as_documented_divergence,
          test_run_scoring_parity_real_score_mismatch_is_never_absorbed_as_divergence"
        status: pass
      - kind: e2e
        ref: "PARITY_SAMPLE_IDS=9604614548 python scripts/run_scoring_parity.py -- wrote
          parity-report-final.json, exit code 0, verdict 'PASS (with 1 documented Needs
          Review divergence(s))'"
        status: pass
    human_judgment: false

duration: ~110min
completed: 2026-08-07
status: complete
---

# Phase 40 Plan 07: Backfill Mechanism & Committed Parity Verdict Summary

**Closed Phase 40: ENGINE-01 proven live end to end (80/A, entirely inside HubSpot, off canonical inputs), D-10's component-seeding backfill built and proven on the portal's entire canonical-input-populated real-record population (n=1), and PARITY-01's committed verdict lands with a divergence classifier that tells a documented oracle-vs-live-enum gap apart from a real finding — while VETO-01/VETO-02 are confirmed, empirically, to remain a genuine open operational gate outside this plan's scope.**

## Performance

- **Duration:** ~110 min (most of it live: two full parity sweeps, one ~6-minute and
  one ~3-minute chunk, plus individual veto-case verification and the armed backfill run)
- **Tasks:** 3
- **Files modified:** 7 (3 created, 4 modified — plus STATE.md/ROADMAP.md/REQUIREMENTS.md metadata)

## Accomplishments

- `batch_update_companies()` added to `src/hubspot_client.py` — `POST
  /crm/v3/objects/companies/batch/update`, mirroring the file's existing dry_run-first
  discipline, with two deviations load-bearing for the backfill caller: an empty list
  short-circuits in both dry_run and live mode, and a >100-entry list raises rather than
  being silently truncated
- `scripts/backfill_seed_company_scores.py` built: computes the five `lv_icp_fit_score`
  component scores from a company's own current canonical `lv_*` inputs via
  `src/icp_scoring.py`'s loaded `config/icp_scoring.yaml` (never a second point table),
  writes all five together (never a subset — one null term blanks the calculated sum,
  per `PORTAL-FACTS.md`'s Task 1 finding), and never writes the four derived output
  fields those already have a producer for
- Portfolio-wide measurement: exactly **one** company anywhere in the 711-company
  portal carries any canonical `lv_*` scoring input — Melbourne Racing Club, id
  `9604614548`. This became both Task 2's proving sample and Task 3's PARITY-01
  real-record sample, per D-09's stated overlap. Armed run seeded its components,
  settled live in ~11s to `lv_icp_fit_score=15`, `lv_icp_tier=C`
- ENGINE-01 live-proven: a disposable with the flagship input combination reads
  `org_type_score=40`, `produces_content_score=20`, `geography_score=10`,
  `annual_revenue_score=10`, `gambling_score=0`, summing to `lv_icp_fit_score=80`,
  `lv_icp_tier=A` — entirely inside HubSpot, off canonical inputs only
- Full live fixture tier: 56/56 passed, covering every named
  ENGINE-01..07/F4/F7/F8/F9/F10 selector not dependent on an armed n8n pipeline write
- The 5 excluded veto-dispatch cases confirmed empirically (individual live runs, not
  theorized) to fail because setting veto-input properties alone never dispatches the
  pipeline under this portal's actually-configured webhook subscriptions — the
  pre-existing VETO-01/VETO-02 operational gate, not a regression this plan introduces
- `parity-report-final.json` committed: `assertions_executed=1`,
  `rubric_version=lv-icp-v0.1`, PASS with 1 documented `Needs Review` divergence
  (40-02's flagged assumption) and 0 real findings
- `scripts/run_scoring_parity.py`'s flag comparison corrected (Rule 1, third instance)
  to boolean-equivalence, and a `_classify_mismatch()` divergence classifier added so
  the committed verdict never silently absorbs a genuine disagreement
- `WINDOWS.md` #4 fixed (Rule 1, pre-existing open bug in this exact file):
  `test_veto_clear_after_correction`'s wrong poller-search property name corrected
- Full offline suite green (2300 passed, 111 skipped); zero
  `ZZ-SCORING-TEST-DELETE-ME-*` companies survive after every live run in this plan

## Task Commits

1. **Task 1: batch_update_companies (TDD)** - `test:` RED + `feat:` GREEN, 2 commits
2. **Task 2: Build and prove the component-seeding backfill** - 1 commit (`feat`)
3. **Task 3: Prove ENGINE-01 end to end and commit the PARITY-01 verdict** - 1 commit (`test`)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `src/hubspot_client.py` — `batch_update_companies()`
- `scripts/backfill_seed_company_scores.py` — D-10's backfill mechanism
- `tests/test_backfill_seed_company_scores.py` — 20 offline tests (Task 1 + Task 2)
- `scripts/run_scoring_parity.py` — flag-comparison Rule 1 fix, `_classify_mismatch()`
- `tests/test_scoring_parity.py` — WINDOWS.md #4 property-name fix, 3 new offline tests
  for the parity-script fix
- `.planning/phases/40-scoring-engine-remediation-notes/parity-report-final.json` —
  PARITY-01's committed verdict
- `.planning/phases/40-scoring-engine-remediation-notes/parity-report-20260806.json` —
  the dated report the script wrote (identical content, kept alongside `-final` per the
  script's own naming convention)
- `.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` — Plan 07
  Task 2 section: the portfolio-wide population measurement and the sample's before/after
  state
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — metadata

## Decisions Made

- **compute_components() reuses the oracle, doesn't reimplement it.** Calls
  `compute_icp_score()` and reads `result.breakdown` rather than a second lookup table —
  the strongest possible form of "never a second table," and the config-mutation proof
  test falls out for free.
- **Default sample selection is the plan's literal rule** (union of `HAS_PROPERTY`
  across the five canonical inputs), which happened to return exactly one real company.
  No tightening was needed or applied — the population is small enough that the literal
  rule and a stricter one would have selected the same single record.
- **VETO-01/VETO-02 left open, not force-closed.** Confirmed empirically (5 individual
  live test runs, not theorized) that the failures are a deliberate security gate
  (`ALLOW_HUBSPOT_RECORD_WRITES` baked false, armed only via a bounded, operator-invoked
  companion), not a bug in the flow or pipeline — outside this plan's `<action>` text
  and 40-03/40-05/40-06's own stated scope boundary for these two requirements.
- **`run_scoring_parity.py`'s flag comparison corrected, not weakened.** This is a
  harness-semantics fix in the read-only sweep script (the plan's "never weaken the
  assertion" prohibition targets the pytest module's own live assertions, which were
  not touched for this reason). Boolean-equivalence comparison is the third instance of
  a defect class 40-05 and 40-06 each already fixed once elsewhere in this codebase.
- **WINDOWS.md #4 fixed even though it doesn't flip the test green.** It's a real,
  independently-verifiable defect (wrong property name) in the exact file this plan
  works with; Rule 1 applies regardless of whether the fix changes the pass/fail
  outcome (it doesn't — the test now fails earlier, at its own first veto-setting
  assertion, for the same structural reason as the other four).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] WINDOWS.md #4: wrong poller-search property name**
- **Found during:** Task 3, running the full live parity suite
- **Issue:** `test_veto_clear_after_correction` patched `enrichment_requested` instead
  of `lv_enrichment_requested` (the real SJ-3 poller-search property, per
  `VETO-WRITE-EVIDENCE.md`'s live-proven trigger) — a pre-existing, already-logged
  (`WINDOWS.md` id 4, open) bug, not caused by this plan.
- **Fix:** Corrected the property name.
- **Files modified:** `tests/test_scoring_parity.py`
- **Verification:** The test now fails at its own earlier veto-setting assertion (line
  375, before the corrected line is even reached) for the same structural write-gate
  reason as the other four excluded cases — the fix is real but does not flip this
  particular test green, since the deeper VETO-01/VETO-02 gate is a separate,
  independently-confirmed blocker.
- **Committed in:** Task 3 commit

**2. [Rule 1 - Bug] `scripts/run_scoring_parity.py`'s flag comparison, third instance of
a known defect class**
- **Found during:** Task 3, generating the first parity report against the real-record
  sample
- **Issue:** The comparison used raw string equality (`str(live) == str(expected)`),
  which reports a mismatch on every never-enriched real record's
  `lv_anti_icp_flag=None` against the oracle's `"false"` — the same architectural
  consequence 40-05 and 40-06 each already fixed once in the pytest live tier's own
  assertions (`!= "true"` instead of `== "false"`).
- **Fix:** Added `_flag_matches()` (boolean-equivalence comparison) and used it in
  `build_report()` instead of raw string equality.
- **Files modified:** `scripts/run_scoring_parity.py`
- **Verification:** 3 new offline tests; the real-record report now correctly shows
  `flag_match=True` for the sample record, isolating the remaining divergence to the
  tier label only.
- **Committed in:** Task 3 commit

---

**Total deviations:** 2 auto-fixed (Rule 1 — both bug fixes; the first pre-existing and
independently logged before this plan started, the second a direct in-scope consequence
of D-01's completion surfacing for the first time against real (not disposable) data).

## Issues Encountered

- **VETO-01/VETO-02 remain open** — the 5 veto-dispatch-dependent live test cases
  (`test_veto_set_all_three_hard_vetoes` ×3, `test_veto_set_multiple_reasons_join`,
  `test_veto_clear_after_correction`) cannot pass without arming
  `operator-claude-plugin/scripts/scheduled_arm.py`'s bounded write-gate window — a
  deliberate security decision, not a code defect, and outside this plan's `<action>`
  text. This is not a new finding; 40-03/40-05/40-06's own summaries already documented
  these two requirements as blocked on "the live-PATCH-to-a-real-record bar, not this
  plan's scope." This plan adds the first *individually-run, per-case* empirical
  confirmation (rather than a batch-run inference) and records it in `WINDOWS.md` (id
  5, open) for Phase 41/future-phase visibility.
- Background-vs-foreground Bash execution for the long-running live suite runs behaved
  inconsistently in this session (a backgrounded run's output file initially read as
  unchanged/empty across several checks, then both the backgrounded run and a
  subsequently-launched foreground chunk completed successfully with correct,
  consistent results) — no impact on correctness, all live evidence was independently
  re-derivable from the completed output.

## User Setup Required

None — no external service configuration. `HUBSPOT_PRIVATE_APP_TOKEN` and the
`automation` scope were already provisioned; portal 22617666 confirmed before every
write (backfill's armed run, and every disposable-company test).

## Next Phase Readiness

- Phase 40 is complete: all 7 plans done, ENGINE-01..07 and PARITY-01/PARITY-02 closed;
  VETO-03 closed (40-06); VETO-01/VETO-02 remain open, tracked in `REQUIREMENTS.md` and
  `WINDOWS.md` (id 5), explicitly out of Phase 40's own scope per three plans'
  consistent documentation.
- Phase 41 (portfolio-wide backfill + data import, DATA-01/DATA-02) inherits: a fully
  correct, live-proven scoring chain (ENGINE-01..07); the backfill mechanism
  (`scripts/backfill_seed_company_scores.py`) proven and ready to run at scale once
  enrichment populates the other 710 companies' canonical inputs; the measured fact that
  only 1/711 companies currently carry any canonical input, meaning the 66
  web-researched companies DATA-01/DATA-02 import IS the population the backfill will
  need to seed, not a redundant step.
- The committed `parity-report-final.json` and its divergence-classifying comparison
  logic in `scripts/run_scoring_parity.py` are ready for Phase 41's larger real-record
  sample without further harness changes.
- `BACKFILL_MAX_RECORDS`'s hard ceiling (25) deliberately blocks a portfolio-wide run
  from this script as-is — Phase 41's own plan should decide whether to raise the
  ceiling (a documented, deliberate code change) or introduce a separate, explicitly
  portfolio-scoped mechanism.

---
*Phase: 40-scoring-engine-remediation-notes*
*Completed: 2026-08-07*

## Self-Check: PASSED

All key files confirmed present on disk (`src/hubspot_client.py`,
`scripts/backfill_seed_company_scores.py`, `tests/test_backfill_seed_company_scores.py`,
`scripts/run_scoring_parity.py`, `tests/test_scoring_parity.py`,
`.planning/phases/40-scoring-engine-remediation-notes/parity-report-final.json`,
`.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`, this SUMMARY).
All 4 task commits confirmed present in `git log --oneline --all`.
