---
phase: 40-scoring-engine-remediation-notes
plan: 01
subsystem: crm-automation
tags: [hubspot, automation-v4, flows, icp-scoring, pytest]

requires:
  - phase: 39-path-decision-fit-score-verification
    provides: fix-in-place path decision (39-DECISION.md), automation scope granted
provides:
  - scripts/fetch_hubspot_flow.py — GET+strip+archive one or many HubSpot flow definitions
  - scripts/put_hubspot_flow.py — PUT a stripped flow body, isEnabled toggle, two-key gate
  - config/hubspot_flows/*.before.json — all four company scoring flows archived
  - config/hubspot_flows/4626124224-org-type-score.after.json — live-fixed org-type mapper
  - tests/test_flow_rubric_conformance.py — glob-driven offline conformance guard
  - PORTAL-FACTS.md — Open Questions 1/2 answered, D-05 round-trip verdict PROVEN
affects: [40-04-scoring-formula-and-content-term, 40-05-revenue-boundary-fix, 40-06-tier-and-veto-workflow]

actuals:
  tokens: 14300
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "GET + strip(createdAt/updatedAt/dataSources) + archive with sorted-keys JSON for HubSpot Automation v4 flow definitions"
    - "disable -> edit -> PUT(disabled) -> enable -> validate-on-disposable -> confirm-enabled for live flow edits (corrected D-07 ordering)"
    - "glob-driven pytest parametrization over config/hubspot_flows/*.after.json so the conformance guard stays green as later plans add their own snapshots"

key-files:
  created:
    - scripts/fetch_hubspot_flow.py
    - scripts/put_hubspot_flow.py
    - config/hubspot_flows/4626124224-org-type-score.before.json
    - config/hubspot_flows/4626124224-org-type-score.after.json
    - config/hubspot_flows/4626722240-geography-score.before.json
    - config/hubspot_flows/4626722237-annual-revenue-score.before.json
    - config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json
    - tests/test_flow_rubric_conformance.py
    - .planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md
  modified: []

key-decisions:
  - "D-05 round-trip verdict: PUT /automation/v4/flows/{id} accepts STATIC_BRANCH action-content edits (branch-target staticValue mutation) and they take effect live — no portal-UI fallback needed for this edit shape. IS_BETWEEN branch-condition edits (40-05's revenue-boundary fix) remain unverified and should still be treated as their own early validation gate."
  - "Corrected D-07's literal step order: 'validate on disposables' must run while the flow is ENABLED, not disabled — a disabled flow cannot fire on property-change events. Ran disable -> edit+PUT(disabled) -> enable -> validate -> confirm-enabled instead of the plan's literal disable/edit/PUT/validate/enable sequence (Rule 1 auto-fix, documented in PORTAL-FACTS.md)."
  - "Disposable-validation companies must be created with a neutral lv_org_type and then PATCHed to the target value in a separate call — setting the target value at row creation does not fire the property-change enrollment event. Matches scripts/probe_scoring_recalc_latency.py's existing create-then-flip pattern; flagged for 40-04/40-05/40-06's own disposable scripts."

patterns-established:
  - "config/hubspot_flows/{flow_id}-{slug}.{before|after}.json as the repo-committed archive location for every HubSpot Automation v4 flow this milestone touches."
  - "Two-key write gate (DRY_RUN=false + ALLOW_HUBSPOT_FLOW_WRITE=true) for scripts/put_hubspot_flow.py, mirroring src/hubspot_client.py's dry_run-first convention even though D-08 permits in-session PUTs without a script-level arming ceremony."

requirements-completed: [ENGINE-06]

coverage:
  - id: D1
    description: "All four company scoring flows archived as stripped, re-parseable JSON; no fifth company scoring flow exists"
    verification:
      - kind: unit
        ref: "ls config/hubspot_flows/*.before.json (4 files) + JSON parse + key-absence assertions run inline during execution"
        status: pass
    human_judgment: false
  - id: D2
    description: "PORTAL-FACTS.md answers both Open Questions from live reads: lv_icp_tier enum is A/B/C/D only (Unscored absent), lv_icp_fit_score's calculationFormula is the 3-term sum org_type_score + geography_score + annual_revenue_score"
    verification:
      - kind: integration
        ref: "GET /crm/v3/properties/companies/lv_icp_tier and /lv_icp_fit_score, live portal 22617666, results recorded verbatim in PORTAL-FACTS.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "Org-type mapper flow (4626124224) fixed live: regulator scores 5 (was 0), gambling_operator scores 0 (was -20), all other seven org-type branches unchanged"
    verification:
      - kind: e2e
        ref: "live disposable companies ZZ-SCORING-TEST-DELETE-ME-* — regulator reached org_type_score=5, gambling_operator reached org_type_score=0, both deleted (204)"
        status: pass
      - kind: unit
        ref: "tests/test_flow_rubric_conformance.py::test_org_type_flow_matches_rubric[...4626124224-org-type-score.after.json]"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-05 API-only round-trip path proven in writing (STATIC_BRANCH edits), not just assumed, before 40-04/40-05/40-06 commit to it"
    verification:
      - kind: manual_procedural
        ref: "PORTAL-FACTS.md 'D-05 round-trip verdict' section — proven live, includes operational findings (revisionId staleness, enrollment-event requirement)"
        status: pass
    human_judgment: false

duration: 27min
completed: 2026-08-06
status: complete
---

# Phase 40 Plan 01: Flow Archive Tooling & Org-Type Tracer Fix Summary

**GET/PUT tooling for HubSpot Automation v4 flows, all four company scoring flows archived, and the org-type mapper live-fixed (regulator 0→5, gambling_operator -20→0) — proving the API-only D-05 edit path before four dependent plans commit to it.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-08-06T05:54:00Z (approx, following prior planning commit)
- **Completed:** 2026-08-06T06:21:00Z
- **Tasks:** 2
- **Files modified:** 9 (7 created in Task 1, 2 created + 1 modified in Task 2 — `PORTAL-FACTS.md` touched in both)

## Accomplishments
- `scripts/fetch_hubspot_flow.py` and `scripts/put_hubspot_flow.py`: reusable GET+strip+archive and PUT+toggle tooling for every remaining flow edit in this phase (40-04, 40-05, 40-06)
- All four company scoring flows (4626124224, 4626722240, 4626722237, 4625147345) archived as stripped, sorted-key JSON — the repo's first-ever committed copy of these definitions
- Both of 40-RESEARCH.md's Open Questions answered from live reads: `lv_icp_tier` has only `A/B/C/D` (no `Unscored` — a real prerequisite for 40-06), and `lv_icp_fit_score`'s formula is the exact 3-term sum `org_type_score + geography_score + annual_revenue_score`
- The org-type mapper flow's `regulator` and `gambling_operator` branches fixed live and validated on disposable companies — closes ENGINE-06 entirely and ENGINE-05's org-type half (F9/F10)
- The D-05 assumption (can `PUT /automation/v4/flows/{id}` safely edit action content?) is now a proven fact, not an assumption, for `STATIC_BRANCH` edits — unblocking 40-04/40-05/40-06's planning

## Task Commits

1. **Task 1: Archive all four flow definitions and record the two portal facts the phase depends on** - `7c32c39` (feat)
2. **Task 2: End-to-end org-type point-table fix — one flow, fetch to re-enable** - `8705ad1` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `scripts/fetch_hubspot_flow.py` - GET + strip(createdAt/updatedAt/dataSources) + archive one or many `/automation/v4/flows/{id}` bodies
- `scripts/put_hubspot_flow.py` - PUT a stripped flow body, `--disable`/`--enable`, two-key write gate
- `config/hubspot_flows/4626124224-org-type-score.before.json` / `.after.json` - pre/post-edit org-type mapper flow
- `config/hubspot_flows/4626722240-geography-score.before.json` - pre-edit geography mapper flow (40-05 input)
- `config/hubspot_flows/4626722237-annual-revenue-score.before.json` - pre-edit revenue mapper flow (40-05 input)
- `config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json` - pre-edit tier workflow (40-06 input)
- `tests/test_flow_rubric_conformance.py` - offline conformance guard, glob-driven over `*.after.json`
- `.planning/phases/40-scoring-engine-remediation-notes/PORTAL-FACTS.md` - Open Questions 1/2, `*_score` property inventory, D-05 verdict

## Decisions Made
- **D-05 round-trip verdict: PROVEN.** `PUT /automation/v4/flows/{id}` accepts `STATIC_BRANCH` action-content edits (branch-target `staticValue` mutation) and they take effect live — confirmed by structural diff (only the two intended values changed, 11 actions unchanged, `isEnabled` restored true) and by live disposable-company validation. No portal-UI fallback was needed for this edit shape. 40-05's `IS_BETWEEN` revenue-boundary edit remains a genuinely open question (Pitfall 2) and should still be treated as its own early validation gate.
- **Corrected D-07's literal task-text ordering** (Rule 1 auto-fix): the plan listed "validate on disposables" before "re-enable," but a disabled flow cannot fire on property-change events, so validating in that order would prove nothing. Ran disable → edit+PUT(while disabled) → enable → validate on disposables (now genuinely live) → confirm still enabled. Documented explicitly in PORTAL-FACTS.md so 40-04/40-05/40-06 don't repeat the ordering mistake.
- **Disposable-company validation pattern refined**: creating a company with the target `lv_org_type` value already set at creation time did NOT fire the flow (org_type_score stayed at its `PROPERTY_DEFAULT_VALUE` of `0` for the full 120s poll, twice). Creating with a neutral value (`lv_org_type=unknown`) and then `PATCH`ing to the target value in a second call reliably enrolls the flow within ~4-6s. This matches `scripts/probe_scoring_recalc_latency.py`'s existing create-then-flip convention; every later plan's disposable-validation code should follow it.
- **`ENGINE-05` marked complete only for its org-type half in this SUMMARY, not the full requirement.** The org-type branch no longer carries the -20 gambling deduction (F9 fixed), but the actual `lv_is_gambling_operator`-driven `-20` component is 40-04's job (D-06's `gambling_score` property + mapper flow). `requirements-completed` above lists only `ENGINE-06`, which this plan fully closes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] D-07 validation step reordered — validate-on-disposable requires the flow to be enabled**
- **Found during:** Task 2, first live validation attempt
- **Issue:** The plan's literal step order runs "validate on disposables" (step 4) before "re-enable" (step 5). A disabled HubSpot flow does not fire on property-change events, so validating against a disabled flow produces no signal at all — the first attempt (run while still disabled from step 3) showed neither disposable's `org_type_score` changing within the 120s poll window, which would have been misreported as "the fix doesn't work" rather than "the flow was never live to test."
- **Fix:** Re-enabled the flow before running validation (enable → validate → confirm-still-enabled), collapsing the plan's separate steps 4/5 into the only order that can actually produce a result. Re-ran validation after enabling; both disposables reached the correct scores.
- **Files modified:** none (execution-order fix, not a code change); documented in PORTAL-FACTS.md's D-05 round-trip verdict section
- **Verification:** Regulator disposable reached `org_type_score=5` in ~5.9s; gambling_operator disposable reached `org_type_score=0` in ~0.4s; both deleted (204)
- **Committed in:** `8705ad1` (Task 2 commit)

**2. [Rule 3 - Blocking] HubSpot optimistic-concurrency `revisionId` staleness on a multi-PUT sequence**
- **Found during:** Task 2, the edit-and-PUT step
- **Issue:** PUTting a body built from the pre-disable `.before.json` archive after the disable PUT had already bumped `revisionId` (21→22) 400'd with `INVALID_REVISION_ID_IN_PUT_REQUEST`. Undocumented in 40-RESEARCH.md's Pitfalls.
- **Fix:** Re-fetch the flow fresh (`fetch_hubspot_flow.fetch_flow()`) immediately before building each subsequent edit in a multi-PUT sequence, rather than reusing an already-PUTted snapshot.
- **Files modified:** none (execution pattern, not a code change); documented in PORTAL-FACTS.md's "Operational findings" for 40-04/40-05/40-06 to reuse
- **Verification:** The re-fetched body's `revisionId` (23) accepted the edit-PUT without error
- **Committed in:** `8705ad1` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug in the plan's own step order, 1 Rule 3 blocking issue from an undocumented HubSpot API behavior)
**Impact on plan:** Both fixes were necessary to get any real validation signal at all; no scope creep — the fixes are execution-sequencing corrections and a documented API-behavior discovery, not code or requirement changes.

## Issues Encountered
- A background-run debug script initially observed the regulator disposable failing to fire twice in a row immediately after the flow was re-enabled (org_type_score stuck at its default 0 for the full 120s poll on two separate attempts), then succeeded cleanly (~4s) on a third attempt run several minutes later. Not conclusively attributed to a HubSpot post-enable activation lag vs. this session's own sequencing (the first two attempts predate the enable-before-validate ordering fix above, so they may simply have been testing a still-disabled flow). Flagged in PORTAL-FACTS.md as an open risk for 40-04/40-05/40-06 to budget slack around their first disposable check after any `isEnabled:true` PUT, since it was not reproduced a third time under the corrected ordering.
- Running python scripts that make live HubSpot API calls from outside the repo working directory (e.g. a path under `/private/tmp/...`) consistently returned `401 Unauthorized` even with the correct token, while the identical code run from within the repo directory succeeded — this environment's network sandboxing appears scoped to the project directory. Worked around by running all network-touching scratch scripts from inside the repo root and deleting them before commit; no impact on the committed deliverables.

## User Setup Required
None - no external service configuration required. HubSpot credentials and the `automation` scope were already provisioned per 40-CONTEXT.md.

## Next Phase Readiness
- 40-04, 40-05, 40-06 can now plan their own flow edits against a proven API path for `STATIC_BRANCH` static-value edits, the exact `calculationFormula` string to extend, and the confirmed-absent `Unscored` enum option (a real prerequisite, not a maybe).
- `config/hubspot_flows/*.before.json` for geography (4626722240), annual-revenue (4626722237), and WF1 (4625147345) are already archived — 40-05/40-06 start from a live GET-free base if they choose to (though re-fetching fresh immediately before editing is still required per the revisionId-staleness finding above).
- ENGINE-05 is only half-closed: the org-type branch no longer double-deducts gambling, but the real `lv_is_gambling_operator`-driven `-20` component (D-06's `gambling_score` property + mapper flow) is still 40-04's work — do not mark ENGINE-05 complete until that lands.
- 40-05's `IS_BETWEEN` revenue-boundary edit (F10) is the next genuinely untested API-editability question (Pitfall 2) — this plan's `STATIC_BRANCH` proof does not extend to it.

---
*Phase: 40-scoring-engine-remediation-notes*
*Completed: 2026-08-06*

## Self-Check: PASSED

All 10 files listed above (2 scripts, 5 config/hubspot_flows JSON archives, 1 test module,
PORTAL-FACTS.md, this SUMMARY) confirmed present on disk. Both task commits (`7c32c39`,
`8705ad1`) confirmed present in `git log --oneline --all`.
