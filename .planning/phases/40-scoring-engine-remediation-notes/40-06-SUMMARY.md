---
phase: 40-scoring-engine-remediation-notes
plan: 06
subsystem: crm-automation
tags: [hubspot, automation-v4, icp-scoring, tier, veto, list-branch, pytest]

requires:
  - phase: 40-scoring-engine-remediation-notes/40-01
    provides: flow tooling (scripts/fetch_hubspot_flow.py, scripts/put_hubspot_flow.py),
      the D-05/D-07 API round-trip protocol, config/hubspot_flows/ archive convention,
      PORTAL-FACTS.md's confirmation that Unscored was absent from lv_icp_tier's enum
  - phase: 40-scoring-engine-remediation-notes/40-04
    provides: five-term lv_icp_fit_score formula (org_type_score + geography_score +
      annual_revenue_score + produces_content_score + gambling_score) driving the score
      thresholds this plan's tier ladder reads
  - phase: 40-scoring-engine-remediation-notes/40-05
    provides: D-01's veto handover completion (n8n pipeline is the sole writer of
      lv_anti_icp_flag/lv_anti_icp_reason) -- this plan's veto branch reads that field,
      it never writes it
provides:
  - lv_icp_tier enum extended with a fifth option, Unscored (A/B/C/D preserved
    verbatim, no Needs Review option added)
  - Flow 4625147345 (WF1 Set ICP Tier) retargeted and rebranched -- the below-15
    branch writes Unscored instead of D (F8/ENGINE-07 closed), enrollment extended
    with lv_anti_icp_flag known as a second trigger (F7/VETO-03 closed), veto filter
    corrected from BOOL true to STRING "true" (D-04)
  - Permanent offline regression guards in tests/test_flow_rubric_conformance.py: the
    complete writable tier-value set is exactly {A, B, C, D, Unscored}, and D is
    reachable only through the veto-guarded branch (the direct F8 regression assertion)
  - Pre-existing stale assertion in tests/test_scoring_parity.py (a D-01 handover
    consequence, same class 40-05 already fixed once) corrected
affects: [40-07-backfill]

actuals:
  tokens: 9200
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "WF1's LIST_BRANCH shape (single-value STRING/NUMBER/NUMBER_RANGED filters, not
      MULTISTRING) needed its own extractor pair in the conformance test module rather
      than reusing extract_list_branch_multistring_scores -- documented as a deliberate
      non-reuse, not an oversight"
    - "A HubSpot type=bool/fieldType=booleancheckbox property's options are
      string-valued ('true'/'false'), so a workflow filter comparing against it should
      use operationType STRING with a string value, not operationType BOOL with a JSON
      boolean literal -- confirmed live on lv_anti_icp_flag, matching D-04's general
      'HubSpot EQ filters compare strings' principle"

key-files:
  created:
    - config/hubspot_flows/lv_icp_tier-property.before.json
    - config/hubspot_flows/lv_icp_tier-property.after.json
    - config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json
  modified:
    - tests/test_flow_rubric_conformance.py
    - tests/test_scoring_parity.py
    - .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md

key-decisions:
  - "Unscored enum option added via the API on the first PATCH attempt (full existing
    options array plus one appended entry, per the plan's own warning that a partial
    options PATCH replaces rather than appends) -- no portal-UI fallback needed."
  - "Veto branch filter changed from operationType BOOL (comparing to the JSON boolean
    true) to operationType STRING (comparing to the string \"true\") after live-reading
    lv_anti_icp_flag's actual property definition: type=bool, fieldType=booleancheckbox,
    with string-valued options. Matches D-04's stated pipeline-write contract and the
    plan's explicit instruction, and was live-validated working both directions."
  - "Task 2's and Task 3's near-overlapping acceptance criteria were split into
    genuinely distinct test functions rather than duplicated: Task 2 owns the
    enrollment/veto-filter/score-ladder conformance assertions (derived from
    config/icp_scoring.yaml, not hard-coded), Task 3 owns the two permanent regression
    guards (writable-tier-value-set closure, D-only-via-veto) that are the direct
    catch-it-next-time assertions for F7/F8."

patterns-established:
  - "STRING-not-BOOL filter comparison for any future workflow edit touching a
    booleancheckbox-typed property whose value is produced by an external writer (the
    n8n pipeline, not a HubSpot workflow)."

requirements-completed: [ENGINE-07, VETO-03]

coverage:
  - id: D1
    description: "lv_icp_tier's enum accepts Unscored (added via PATCH, A/B/C/D
      preserved verbatim, no Needs Review option added) -- the prerequisite Task 1
      confirmed before WF1 was touched."
    requirement: "ENGINE-07"
    verification:
      - kind: e2e
        ref: "live disposable ZZ-SCORING-TEST-DELETE-ME-* (id 280246734318): direct
          PATCH lv_icp_tier=Unscored read back as exactly 'Unscored', not empty;
          deleted (204)"
        status: pass
      - kind: other
        ref: "config/hubspot_flows/lv_icp_tier-property.after.json options list
          includes Unscored at displayOrder 4, A/B/C/D unchanged"
        status: pass
    human_judgment: false
  - id: D2
    description: "WF1's below-15 branch writes Unscored instead of D -- a low-fit
      score is no longer conflated with disqualify (F8). Boundary precision at 70/69,
      40/39, 15/14 confirmed exact; a negative total with no veto also grades Unscored,
      not D."
    requirement: "ENGINE-07"
    verification:
      - kind: e2e
        ref: "live disposables composed via the five component properties: 70->A,
          69->B, 40->B, 39->C, 15->C, 14->Unscored, -20->Unscored (all deleted 204)"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_wf1_score_ladder_thresholds_match_rubric"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_wf1_d_is_written_only_on_the_veto_guarded_branch"
        status: pass
      - kind: e2e
        ref: "RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k f8_sub15"
        status: pass
    human_judgment: false
  - id: D3
    description: "WF1 enrolls on lv_anti_icp_flag known as a second trigger alongside
      lv_icp_fit_score known, so a veto flip alone re-enrolls and moves the tier
      without an unrelated score change (F7/VETO-03). Verified both directions on one
      disposable at a fixed B-band total with the score held constant."
    requirement: "VETO-03"
    verification:
      - kind: e2e
        ref: "live disposable, fixed total 40 (B): flag true -> tier D (score
          unchanged at 40), flag false -> tier restored to B (score still 40)"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_wf1_enrollment_includes_score_and_veto_flag"
        status: pass
      - kind: e2e
        ref: "RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k \"tier_on_flag_change or f7\""
        status: pass
    human_judgment: false
  - id: D4
    description: "D is written only when lv_anti_icp_flag equals the string 'true'
      (D-04) -- the veto branch filter compares STRING not BOOL, matching what the
      n8n pipeline actually writes."
    requirement: "VETO-03"
    verification:
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_wf1_veto_branch_compares_string_true_and_writes_d"
        status: pass
      - kind: e2e
        ref: "live flag-flip case above -- D landed correctly under the corrected
          STRING comparison"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both defects locked behind offline assertions that run on every
      commit: the complete writable tier-value set is exactly {A, B, C, D, Unscored},
      and D is reachable only through the veto-guarded branch."
    requirement: "ENGINE-07"
    verification:
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_wf1_writable_tier_values_exactly_five"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_wf1_d_is_written_only_on_the_veto_guarded_branch"
        status: pass
    human_judgment: false

duration: ~55min
completed: 2026-08-07
status: complete
---

# Phase 40 Plan 06: Tier & Veto Workflow Summary

**Retargeted and rebranched WF1 (Set ICP Tier) -- the below-15 branch writes `Unscored` instead of `D` closing F8/ENGINE-07, and a second enrollment trigger on `lv_anti_icp_flag` closes F7/VETO-03 so a veto flip alone moves the tier -- plus a fifth `lv_icp_tier` enum option and two permanent offline regression guards.**

## Performance

- **Duration:** ~55 min (most of it live disposable-company validation: seven
  threshold cases, a two-direction flag-flip case, and two full live-parity sweeps of
  50 selected tests, each ~5.5 min)
- **Tasks:** 3
- **Files modified:** 6 (3 created in `config/hubspot_flows/`, 3 modified: two test
  modules and `PORTAL-FACTS.md`)

## Accomplishments
- `lv_icp_tier`'s enum given a fifth option, `Unscored` (A/B/C/D preserved verbatim,
  no `Needs Review` option added per the plan's explicit prohibition), live-validated
  by a direct write/read-back on a disposable before WF1 was touched
- WF1 (flow `4625147345`) retargeted: below-15 branch now writes `Unscored` instead of
  `D` -- live-validated across the full threshold sweep (70/69/40/39/15/14/-20), the
  `-20`-no-veto case landing `Unscored` and never `D` (F8/ENGINE-07's exact regression
  shape)
- WF1's enrollment criteria extended with `lv_anti_icp_flag` known as a second
  trigger -- live-validated both directions on one disposable at a fixed B-band total:
  flag `true` moved the tier to `D`, flag `false` restored `B`, `lv_icp_fit_score`
  identical before and after both flips (F7/VETO-03)
- WF1's veto branch filter corrected from `BOOL true` to `STRING "true"` (D-04) after
  live-reading `lv_anti_icp_flag`'s actual property definition (`type: bool`,
  `fieldType: booleancheckbox`, string-valued options) -- the pipeline's write contract
  and the flag's underlying representation both point at a string comparison
- Diff against `.before.json` confirms exactly the three intended changes landed (`+43
  -15 ~6` lines), no branch or action dropped (T-40-03)
- Two permanent offline regression guards added: the complete set of `lv_icp_tier`
  values WF1 can ever write is exactly `{A, B, C, D, Unscored}`, and `D` is written
  only on the veto-guarded branch -- the direct assertion that would have caught F8
  when it was introduced
- A pre-existing stale assertion (`test_gambling_deducts_20_without_veto` asserting
  `lv_anti_icp_flag == "false"`, unreachable since 40-05's veto-handover completion)
  corrected -- the same fix pattern 40-05 already applied once in this file, surfaced
  by this plan's own `<verification>` selector
- Full offline suite green (2277 passed, 111 skipped); two independent live-parity
  sweeps of the plan's full named selector list (50 tests each) both exit 0; zero
  `ZZ-SCORING-TEST-DELETE-ME-*` companies survive

## Task Commits

1. **Task 1: Ensure lv_icp_tier accepts Unscored before any flow writes it** - `fff574f` (feat)
2. **Task 2: Retarget and rebranch WF1** - `0ddd6d4` (feat)
3. **Task 3: Lock the tier ladder behind offline assertions** - `f7a9842` (test)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `config/hubspot_flows/lv_icp_tier-property.before.json` / `.after.json` - pre/post
  enum-PATCH snapshots
- `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json` - live-fetched,
  enabled WF1 post-retarget
- `tests/test_flow_rubric_conformance.py` - WF1-specific extractors
  (`extract_wf1_veto_branch`, `extract_wf1_score_ladder`, `_wf1_written_tier_values`,
  `_wf1_enrollment_hs_names`) and six new tests covering enrollment, the veto filter's
  string comparison, score-ladder thresholds read from `config/icp_scoring.yaml`, the
  writable tier-value-set closure, and the D-only-via-veto regression guard
- `tests/test_scoring_parity.py` - `test_gambling_deducts_20_without_veto` corrected
  to match D-01's completed architecture
- `.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` - Plan 06
  sections recording the enum-option outcome and WF1's live validation in full

## Decisions Made
- **Veto filter changed BOOL to STRING, not left as-is.** The plan's must-haves and
  D-04 both pointed at a string comparison; live-reading the property confirmed
  `lv_anti_icp_flag` is a `booleancheckbox` with string-valued options, so a STRING
  filter is the structurally correct match, not just a stylistic preference.
  Live-validated working both directions before treating this as settled.
- **Task 2/Task 3 test content split, not duplicated.** Their acceptance criteria
  overlap heavily in prose (both mention D-only-via-veto, both mention the writable
  tier set); rather than write near-identical assertions twice, Task 2's commit owns
  the enrollment/filter/threshold conformance tests and Task 3's commit owns the two
  standing regression guards, matching each task's own stated intent ("conformance"
  vs. "permanent regression guard").
- **Stale `test_gambling_deducts_20_without_veto` assertion corrected in-plan, not
  deferred.** It sits outside this plan's `files_modified` on paper, but it is the
  exact same defect class 40-05 already fixed once in the same file (a bare
  disposable patch can no longer produce `lv_anti_icp_flag == "false"` since D-01's
  handover), and it was blocking this plan's own named `<verification>` selector from
  exiting 0. Rule 1 (auto-fix bugs) applies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_gambling_deducts_20_without_veto` asserted a value D-01's architecture cannot produce**
- **Found during:** running this plan's own `<verification>` live selector
  (`f8_sub15 or tier_on_flag_change or f7 or org_type_sweep or produces_content or
  gambling or revenue_boundary or f4 or f9 or f10`)
- **Issue:** `tests/test_scoring_parity.py::test_gambling_deducts_20_without_veto`
  asserted `lv_anti_icp_flag == "false"`. Since 40-05 completed D-01's veto handover,
  no HubSpot workflow writes the flag at all, and a bare disposable patch (no pipeline
  run triggered) leaves it `None`, not `"false"`.
- **Fix:** Corrected the assertion to `lv_anti_icp_flag != "true"`, the same pattern
  40-05 already applied to `test_f4_au_string_is_not_vetoed`.
- **Files modified:** `tests/test_scoring_parity.py`
- **Verification:** `RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k "gambling or f9"` passes (5/5)
- **Committed in:** `f7a9842` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 -- bug fix, a stale test left over from a
prior plan's architectural change, not caused by this plan's own edits and not scope
creep to fix here).

## Issues Encountered
- One transient live-test failure during the first full-selector confirmation run:
  `test_revenue_boundary_bands[1.2B+--50]` read `annual_revenue_score=0` instead of
  `-50` on its first attempt. This is 40-05's territory (the revenue flow), untouched
  by this plan. Isolated re-run of exactly that case passed cleanly (`2 passed` for
  both `1.2B+` parametrizations), and 40-05-SUMMARY.md already documents this exact
  band was live-validated correctly. Treated as a one-off live-latency flake, not a
  regression -- confirmed by a second full clean run of the entire selector list (50
  passed, 0 failed) immediately after.
- Scripts invoked from paths outside the repo (the session scratchpad directory) hit
  the live HubSpot API with a `401 Unauthorized`, while an identical script run from
  inside the repo (or via `python -c` inline) succeeded with the same credentials --
  consistent with prior plans' notes on the sandbox environment's handling of
  scratchpad-vs-repo script locations. Worked around by running one-off validation
  scripts from the repo root and deleting them before each commit.

## User Setup Required
None - no external service configuration. `HUBSPOT_PRIVATE_APP_TOKEN` and the
`automation` scope were already provisioned; credentials confirmed present via `.env`
(portal 22617666 verified before any write).

## Next Phase Readiness
- All six company scoring flows (four original plus 40-04's two) confirmed
  `isEnabled: true` on a live GET.
- ENGINE-07 and VETO-03 marked complete in `REQUIREMENTS.md`; only VETO-01 and
  VETO-02 remain open in Phase 40 (both blocked on the live-PATCH-to-a-real-record
  bar per 40-03-SUMMARY.md's notes, not this plan's scope).
- Phase 40's remaining plan is 40-07 (backfill mechanism for the 712 pre-existing
  companies) -- unaffected by this plan beyond inheriting a now-fully-correct tier
  ladder to backfill against.
- Zero `ZZ-SCORING-TEST-DELETE-ME-*` companies survive (confirmed via a final portal-
  wide search sweep, 0 results, after every validation run in this plan).

---
*Phase: 40-scoring-engine-remediation-notes*
*Completed: 2026-08-07*

## Self-Check: PASSED

All key files confirmed present on disk (`config/hubspot_flows/lv_icp_tier-property.before.json`,
`.after.json`, `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json`,
`tests/test_flow_rubric_conformance.py`, `tests/test_scoring_parity.py`,
`.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md`, this SUMMARY).
All 3 task commits (`fff574f`, `0ddd6d4`, `f7a9842`) confirmed present in
`git log --oneline --all`.
