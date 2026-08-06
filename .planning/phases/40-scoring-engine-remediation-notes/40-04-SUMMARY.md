---
phase: 40-scoring-engine-remediation-notes
plan: 04
subsystem: crm-automation
tags: [hubspot, automation-v4, calculation-formula, icp-scoring, pytest]

requires:
  - phase: 40-scoring-engine-remediation-notes/40-01
    provides: flow tooling (scripts/fetch_hubspot_flow.py, scripts/put_hubspot_flow.py),
      the D-05 API round-trip verdict, config/hubspot_flows/ archive convention, and
      PORTAL-FACTS.md's verbatim pre-plan calculationFormula string
provides:
  - produces_content_score / gambling_score company properties (D-06's 4th and 5th
    components)
  - two new live Automation v4 flows (4634822079 Update Produces Content Score,
    4634822085 Update Gambling Score) mapping lv_produces_content/lv_is_gambling_operator
    to their components, each also enrolling on createdate known so a fresh company
    reads 0 without either ever being written
  - lv_icp_fit_score's calculationFormula extended from a 3-term to a 5-term sum
  - config/hubspot_flows/{produces-content,gambling}-score.after.json,
    config/hubspot_flows/lv_icp_fit_score-property.{before,after}.json
  - two new tests/test_flow_rubric_conformance.py assertions (branch-table conformance
    for both new flows, five-term formula assertion) plus an _is_flow() guard
affects: [40-05-revenue-boundary-fix, 40-06-tier-and-veto-workflow, 40-07-backfill]

actuals:
  tokens: 6600
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "createdate-known as a second enrollment branch on a per-input mapper flow,
      feeding the same STATIC_BRANCH action's existing default branch — the
      API-only substitute for a schema-level property default HubSpot's Properties
      API does not expose for plain number properties"
    - "_is_flow(doc) guard in tests/test_flow_rubric_conformance.py to distinguish
      Automation v4 flow archives from property-definition snapshots sharing the
      same config/hubspot_flows/*.after.json glob"

key-files:
  created:
    - config/hubspot_flows/produces-content-score.after.json
    - config/hubspot_flows/gambling-score.after.json
    - config/hubspot_flows/lv_icp_fit_score-property.before.json
    - config/hubspot_flows/lv_icp_fit_score-property.after.json
  modified:
    - tests/test_flow_rubric_conformance.py
    - .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md

key-decisions:
  - "The other three components' default-0 stamp on new companies is not reproducible
    via the CRM v3 Properties API (defaultValue/numberDisplayHint both silently
    ignored on POST and PATCH, live-probed three ways) — resolved with a second
    enrollment branch on createdate known, staying inside the API-only D-05/D-08 path
    rather than reaching for a portal-UI fallback for an unsupported schema feature."
  - "Live-proved (reversible spike, formula reverted immediately after) that
    lv_icp_fit_score's calculation_equation formula returns blank, not 0, when any
    one referenced term is null — confirming the plan's own 'not ceremony' framing
    of the default-stamp requirement was load-bearing, not decorative."

patterns-established:
  - "createdate-known second enrollment branch for any future per-input mapper flow
    that needs a guaranteed non-null default on record creation, when the property
    schema itself offers no API-settable default."

requirements-completed: [ENGINE-02, ENGINE-05]

coverage:
  - id: D1
    description: "produces_content_score and gambling_score company properties exist,
      mirror org_type_score's type/fieldType/groupName, and both new components
      (unlike org_type_score/geography_score/annual_revenue_score, which the API
      cannot replicate) still read 0 on a freshly created company without ever being
      written, via a createdate-triggered flow branch."
    requirement: "ENGINE-02"
    verification:
      - kind: e2e
        ref: "live disposable ZZ-SCORING-TEST-DELETE-ME-* company, nothing set:
          produces_content_score=0 and gambling_score=0 within 60s of creation"
        status: pass
    human_judgment: false
  - id: D2
    description: "lv_produces_content=true contributes exactly +20 via
      produces_content_score, closing F1; false/absent contributes 0."
    requirement: "ENGINE-02"
    verification:
      - kind: e2e
        ref: "live disposable: lv_produces_content=true -> produces_content_score=20
          (~5.8s) -> lv_produces_content=false -> 0 (~5.8s); lv_icp_fit_score reaches
          20 on a disposable with only lv_produces_content=true set"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_produces_content_flow_matches_rubric[...produces-content-score.after.json]"
        status: pass
      - kind: e2e
        ref: "RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py::test_produces_content_contributes_20"
        status: pass
    human_judgment: false
  - id: D3
    description: "The -20 gambling deduction is driven by lv_is_gambling_operator via
      its own gambling_score component, independent of lv_org_type, and never sets
      lv_anti_icp_flag (F9)."
    requirement: "ENGINE-05"
    verification:
      - kind: e2e
        ref: "live disposable: lv_is_gambling_operator=true -> gambling_score=-20
          (~5.9s), lv_anti_icp_flag stayed null (not \"true\"); =false -> 0 (~5.8s)"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_gambling_flow_matches_rubric[...gambling-score.after.json] (also asserts the flow writes only gambling_score, T-40-15)"
        status: pass
      - kind: e2e
        ref: "RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py::test_produces_content_contributes_20 tests/test_scoring_parity.py -k org_type_sweep"
        status: pass
    human_judgment: false
  - id: D4
    description: "lv_icp_fit_score sums exactly five components (org_type_score,
      geography_score, annual_revenue_score, produces_content_score, gambling_score),
      reconciling D-06's '5 components total'."
    requirement: "ENGINE-02"
    verification:
      - kind: e2e
        ref: "live disposable with the full ENGINE-01 input set reads
          org_type_score=40, produces_content_score=20 individually (geography/revenue
          still 0, pending 40-05's retarget, so the total is 60 not yet 80 as the plan
          states)"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_fit_score_formula_references_all_five_components"
        status: pass
    human_judgment: false
  - id: D5
    description: "produces_content_score and gambling_score settle to the same values
      regardless of write order (backstop must-have)."
    requirement: "ENGINE-02"
    verification:
      - kind: e2e
        ref: "live disposable: lv_is_gambling_operator, lv_produces_content, lv_org_type
          written in reverse order -> gambling_score=-20, produces_content_score=20,
          org_type_score=40 all settled correctly"
        status: pass
    human_judgment: true
    rationale: "The plan's own must-have carries a backstop marker (sampled
      observation, not a guarantee) — HubSpot flow execution is asynchronous, so a
      single reverse-order sample cannot prove ordering independence in general, only
      that this one sample did not exhibit a race."

duration: ~25min
completed: 2026-08-06
status: complete
---

# Phase 40 Plan 04: Scoring Formula & Content Term Summary

**Added `produces_content_score` (+20/0) and `gambling_score` (-20/0, org-type-independent) as the 4th/5th `lv_icp_fit_score` components — closing F1/ENGINE-02 and F9/ENGINE-05 — after discovering and working around a HubSpot API gap where the existing three components' default-0 stamp on new companies has no Properties-API equivalent.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-06T08:00:00Z (approx)
- **Completed:** 2026-08-06T08:23:00Z
- **Tasks:** 3
- **Files modified:** 6 (4 created in `config/hubspot_flows/`, 2 modified: the test module and `PORTAL-FACTS.md`)

## Accomplishments
- `produces_content_score` and `gambling_score` company properties created, byte-for-byte mirroring `org_type_score`'s `type`/`fieldType`/`groupName`
- Discovered live (not assumed) that the other three components' default-0-on-creation stamp is not reproducible via the CRM v3 Properties API — `defaultValue` is silently dropped on both `POST` and `PATCH` for a plain `number` property in this portal, confirmed three separate ways
- Live-reproduced *why* this matters: a reversible spike (temporarily appended `+ gambling_score` to the live formula, observed `lv_icp_fit_score` go blank on a company where that one term was null, then reverted) proves HubSpot's `calculation_equation` formula does not treat a missing term as 0 — it blanks the whole sum
- Resolved by giving each new mapper flow a second enrollment branch on `createdate` known, feeding the same `STATIC_BRANCH` action's existing default branch — fully within the API-only D-05/D-08 path, no portal-UI needed
- Two new Automation v4 flows created disabled, live-validated, then enabled: `4634822079` (Update Produces Content Score) and `4634822085` (Update Gambling Score) — both confirmed writing only their own component (T-40-15)
- `lv_icp_fit_score`'s `calculationFormula` PATCHed from a 3-term to a 5-term sum on the first attempt (no 400, no portal-UI fallback needed), with live proof the new terms actually compute, not just that the PATCH returned 200
- `tests/test_flow_rubric_conformance.py` extended with 2 new tests plus a five-term formula assertion; all offline tests green; full suite (2241 passed, 48 skipped) green
- Live parity harness (`tests/test_scoring_parity.py`) confirms `test_produces_content_contributes_20` and the `org_type_sweep[gambling_operator-0]` case pass end-to-end against the real portal

## Task Commits

1. **Task 1: Create the produces_content_score and gambling_score company properties** - `64e1860` (feat)
2. **Task 2: Create the two mapper flows and validate them live on disposables** - `28131d2` (feat)
3. **Task 3: Extend the lv_icp_fit_score calculated formula to five component terms** - `58bc891` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `config/hubspot_flows/produces-content-score.after.json` - live-fetched, enabled produces-content mapper flow
- `config/hubspot_flows/gambling-score.after.json` - live-fetched, enabled gambling mapper flow
- `config/hubspot_flows/lv_icp_fit_score-property.before.json` / `.after.json` - pre/post formula-PATCH snapshots
- `tests/test_flow_rubric_conformance.py` - 2 new glob-parametrized branch-table tests, 1 five-term formula assertion, `_is_flow()` guard so the property snapshot doesn't false-fail the flow-branch tests
- `.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` - "Components after 40-04" property inventory, the default-value-generation finding and its resolution, Task 2/3 flow-id and formula records

## Decisions Made
- **Default-0 stamp resolved via a second enrollment branch, not portal UI.** The plan's Task 1 anticipated the property-level default might not transfer cleanly ("not ceremony"); live probing confirmed the API genuinely has no lever for it (three separate attempts: `defaultValue` in the create body, `defaultValue` via PATCH, `numberDisplayHint` via PATCH — all silently no-op). Rather than invoking D-05's portal-UI fallback (reserved for edits the API *rejects*, not schema features the API never exposed), the fix stays inside Automation v4: both new mapper flows also enroll on `createdate` known, which at creation time falls to the existing default branch and writes `0` — no new action, no new branch, just a second way into the one that already exists. Confirmed (per 40-01's D-05 finding) this does not retroactively touch any of the 712 pre-existing companies, only future creations.
- **Formula PATCH went through the API cleanly.** Pitfall 3's documented 400-error history did not reproduce; the single `PATCH` with only `calculationFormula` in the body returned 200 on the first attempt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Default-0 stamp is not API-reproducible; added a createdate enrollment branch to both new mapper flows**
- **Found during:** Task 1, validating the disposable-company default check
- **Issue:** The plan's Task 1 asked to validate that a freshly created disposable company reads `produces_content_score`/`gambling_score` as `0` "without either ever being written." Live testing showed both properties read `None` (empty), not `0`, on a brand-new company — unlike `org_type_score`/`geography_score`/`annual_revenue_score`, which all get a `PROPERTY_DEFAULT_VALUE`/`default-value-generation` stamp of `0`. A live spike confirmed this is load-bearing: `lv_icp_fit_score`'s `calculation_equation` formula blanks entirely when any one referenced term is null, so leaving these two properties genuinely empty on every fresh company would have broken Task 3's own acceptance criteria the moment the formula referenced them.
- **Fix:** Extended both new mapper flows' `enrollmentCriteria` with a second `eventFilterBranches` entry enrolling on `createdate` known (same `eventTypeId: "4-655002"` UNIFIED_EVENTS type as every other property-keyed enrollment in this portal), feeding into the same `STATIC_BRANCH` action's existing default branch. Since the driving input is unset at creation, the branch falls to the default action, which already writes `0`.
- **Files modified:** none beyond the flow bodies themselves (Task 2's `POST`/`PUT`); documented in `PORTAL-FACTS.md`
- **Verification:** A brand-new disposable company (nothing set) reads `produces_content_score=0` and `gambling_score=0` within 60s of creation; confirmed this does not retroactively fire for existing companies (40-01's D-05 enrollment-requires-a-future-event finding)
- **Committed in:** `28131d2` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 2 missing-critical-functionality fix, live-discovered and live-confirmed necessary, not speculative)
**Impact on plan:** The fix was required for Task 3's own acceptance criteria to be achievable at all (a null term blanks the whole formula) — no scope creep, the plan's own text flagged this exact risk ("not ceremony") and this deviation closes it using the same mechanism (Automation v4 flows) every other edit in this plan already uses.

## Issues Encountered
- The one live parity command named in the plan's `<verification>` block
  (`RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k "produces_content or gambling or f9"`)
  has 2 failures out of 9 selected tests: `test_gambling_deducts_20_without_veto` and
  `test_f9_gambling_conflation`, both solely on the assertion
  `lv_anti_icp_flag == "false"`. This is **not** caused by this plan — `lv_anti_icp_flag`
  is pipeline-owned (D-01, 40-03's scope) and 40-03-SUMMARY.md already documents that
  `ALLOW_HUBSPOT_RECORD_WRITES=false` is baked into every current build, so nothing can
  write the flag to any value right now (it reads `None`, not the wrong value). Both
  failing tests' OTHER assertions (`org_type_score=20`, `gambling_score=-20`, i.e. this
  plan's actual deliverable) pass. `test_produces_content_contributes_20` and
  `test_org_type_sweep[gambling_operator-0]` — the two live tests actually scoped to
  this plan's work — both pass outright. Pre-existing blocker, already tracked in
  `WINDOWS.md` id 2 and `STATE.md`'s Blockers section; out of this plan's
  `files_modified` scope to fix.

## User Setup Required
None - no external service configuration required. `HUBSPOT_PRIVATE_APP_TOKEN` and the `automation` scope were already provisioned per 40-CONTEXT.md.

## Next Phase Readiness
- All six company scoring flows (the original four plus this plan's two new ones) confirmed `isEnabled: true` on a final live GET.
- `lv_icp_fit_score` now sums five components; 40-05 can proceed with the geography/revenue retarget (F2/F3/F10) knowing the formula side is already extended and does not need touching again.
- 40-07's backfill (D-10) remains the mechanism for seeding all five components on the 712 pre-existing companies — this plan's `createdate` fix only covers companies created *after* today.
- The `ALLOW_HUBSPOT_RECORD_WRITES=false` blocker from 40-03 is unchanged by this plan and still applies to 40-05's Geography-flow veto-branch deletion decision (see `STATE.md` Blockers).
- Zero `ZZ-SCORING-TEST-DELETE-ME-*` companies survive (confirmed via a final portal-wide search sweep, 0 results).

---
*Phase: 40-scoring-engine-remediation-notes*
*Completed: 2026-08-06*

## Self-Check: PASSED

All 4 created files (`config/hubspot_flows/produces-content-score.after.json`,
`config/hubspot_flows/gambling-score.after.json`,
`config/hubspot_flows/lv_icp_fit_score-property.before.json`,
`config/hubspot_flows/lv_icp_fit_score-property.after.json`) confirmed present on disk.
All 3 task commits (`64e1860`, `28131d2`, `58bc891`) confirmed present in
`git log --oneline --all`.
