---
phase: 50-derived-tier-property
plan: 06
subsystem: hubspot-schema
tags: [hubspot, calculation_equation, icp-tier, veto, n8n, parity-gate, evidence]

requires:
  - phase: 50-derived-tier-property
    provides: "50-03: D-07's live parity gate discovered the veto-guard failure (WINDOWS.md id 13) and the D-04 flip's SEVERITY callout; 50-CONTEXT.md's 2026-08-14 amendment (D-20/D-21/D-22) that this plan implements"
provides:
  - "lv_anti_icp_flag_num -- live numeric (0/1) company property, pipeline-written, the only readable veto signal calculation_equation can consume"
  - "lv_icp_tier_derived's corrected calculationFormula -- veto guard reads the numeric mirror, score comparisons uncoalesced (D-21 reverses D-04)"
  - "scripts/backfill_anti_icp_flag_num.py -- the phase's one D-16 company-write deviation, armed/capped/payload-scope-asserted"
  - "src/icp_scoring.py::anti_icp_flag_properties() + scripts/build_cloud_workflows.py's Decide Company Action flagIsSet local -- one veto derivation, two serializations, in both engines"
  - "tests/n8n/antiIcpFlagMirror.test.mjs + check_tier_derived_parity.py's mirror_disagrees()/render_mirror_section() -- behavioural + population-level drift control"
  - "50-TIER-PARITY-EVIDENCE.md's 2026-08-14 post-correction section -- D-07 re-run matches the pre-registered 61/4/1 expectation exactly; D-19 census matches A9/B45/C4/D6/Unscored2 exactly"
affects: [50-04-retirement-decision, 50-05-wf1-shutdown]

actuals:
  tokens: 38700
  tasks: 5
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One derivation, two serializations: a single computed boolean (compute_icp_score's anti_icp_flag / Decide Company Action's flagIsSet local) is serialized into two HubSpot properties in the same write, never re-derived twice -- the same architecture lv_icp_fit_score already uses for produces_content_score"
    - "Numeric mirror for a calculation_equation veto guard: calculation_equation reads only numeric properties, so a boolean/enum signal a formula needs to branch on must be pipeline-mirrored into a plain number property first -- there is no way to make HubSpot read a booleancheckbox inside a formula"
    - "Deriving 'current' formula behavior from the live/declared config rather than a frozen historical probe: _current_null_variant() replaces a stale probe-file read with a live formula inspection, so operator-facing text tracks what the shipped formula actually does even after a later amendment reverses the probe's original finding"

key-files:
  created:
    - scripts/backfill_anti_icp_flag_num.py
    - tests/test_backfill_anti_icp_flag_num.py
    - tests/n8n/antiIcpFlagMirror.test.mjs
    - .planning/phases/50-derived-tier-property/50-MIRROR-SCOPE.md
    - .planning/phases/50-derived-tier-property/50-MIRROR-BACKFILL.md
  modified:
    - config/hubspot_properties.yaml
    - config/hubspot_flows/lv_anti_icp_flag_num-property.{before,after}.json
    - config/hubspot_flows/lv_icp_tier_derived-property.after.json
    - src/icp_scoring.py
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - scripts/check_tier_derived_parity.py
    - scripts/check_schema_drift.py
    - tests/test_tier_formula_pin.py
    - tests/test_icp_scoring.py
    - tests/test_tier_derived_tools.py
    - tests/test_flow_rubric_conformance.py
    - tests/test_check_schema_drift.py
    - tests/test_cloud_companies_branch.py
    - tests/test_hubspot_properties_config.py
    - .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md
    - .planning/REQUIREMENTS.md
    - .planning/WINDOWS.md

key-decisions:
  - "D-16 deviation authorised and spent exactly once: backfill-scoped selected at the Task 2 checkpoint, writing lv_anti_icp_flag_num=1 to exactly the 6 checkpoint-authorised, live-derived vetoed companies -- no other company write occurred anywhere in this plan."
  - "D-21 (operator, mid-execution): D-04's coalesced fallback is reversed. It fired on a race (an immediate read-back before the calculated property backfilled), not a finding -- re-tested with polling, a null lv_icp_fit_score falls through to its else branch normally. The shipped formula is uncoalesced on the score; the ~646-record blank->\"Unscored\" flip is undone."
  - "TIER-01 left NOT marked complete despite the veto-guard defect it cited now being fixed and verified live (6/6 vetoed companies correctly derive D). The gate's own strict rule (any row outside the 4 pre-registered stuck ids is a defect) still keeps D-06/D-08 gated on one residual, unrelated, opposite-polarity defect (Coffs Harbour, WINDOWS.md id 14) -- whether to extend the exception list is Plan 04/05's decision, not taken here."
  - "KNOWN_STUCK_IDS never extended -- the gate is not made to pass by redefinition. Coffs Harbour stays a named defect and a WINDOWS.md id 14 entry."

requirements-completed: [TIER-02]

coverage:
  - id: D1
    description: "The veto-guard failure (WINDOWS.md id 13) is fixed: a numeric mirror property (lv_anti_icp_flag_num) carries the veto where calculation_equation can read it, backfilled onto the 6 live-vetoed companies under the phase's one D-16 deviation, and the corrected uncoalesced formula is live -- Simtech LED polled to D, the ~646-record Unscored flip un-flipped (confirmed blank via a sustained poll)."
    requirement: TIER-01
    verification:
      - kind: unit
        ref: "tests/test_backfill_anti_icp_flag_num.py, tests/test_tier_formula_pin.py (44 tests, all pass)"
        status: pass
      - kind: other
        ref: "50-MIRROR-BACKFILL.md -- live poll proof: Simtech LED 18047161864 settled to D, Rockhampton 9604732795 stayed B, Newcastle Jockey Club 9604773165 (never-scored) stayed blank across a 190s poll"
        status: pass
    human_judgment: false
  - id: D2
    description: "Both engines (Python oracle, n8n Decide Company Action) emit the numeric mirror from one derivation with drift control that fails loudly in either engine; deployed and bounced, with the RUNNING instance's own execution proven to emit the mirror (not just the stored definition)."
    requirement: TIER-01
    verification:
      - kind: unit
        ref: "tests/test_icp_scoring.py::test_anti_icp_flag_properties_* (4 tests, all pass)"
        status: pass
      - kind: e2e
        ref: "tests/n8n/antiIcpFlagMirror.test.mjs (7 tests, all pass; node --test tests/n8n/*.test.mjs -- 683/683 total)"
        status: pass
      - kind: other
        ref: "live deploy+bounce (LV Enrichment Cloud template 950HPb7a1GgSAIyZ) + unarmed recompute execution 11879's own runData for Decide Company Action showing lv_anti_icp_flag_num=\"1\""
        status: pass
    human_judgment: false
  - id: D3
    description: "D-07's gate and D-19's census re-run live against the corrected property, matching the pre-registered expectation exactly (61 match / 4 expected_mismatch / 1 defect; census A9/B45/C4/D6/Unscored2); appended as a dated section below 50-03's original FAIL, and WINDOWS.md/REQUIREMENTS.md amended to tell the truth about what is fixed and what is not."
    requirement: TIER-01
    verification:
      - kind: other
        ref: "50-TIER-PARITY-EVIDENCE.md's 2026-08-14 post-correction section (gate run twice, byte-identical modulo timestamp)"
        status: pass
    human_judgment: false

duration: ~110min
completed: 2026-08-14
status: complete
---

# Phase 50 Plan 06: Numeric Veto Mirror + Uncoalesced Formula Correction Summary

**Fixed the two live findings D-07's gate exposed on `lv_icp_tier_derived`: added a pipeline-written numeric mirror (`lv_anti_icp_flag_num`) so the veto branch can actually be read by `calculation_equation`, corrected the formula to reference the score bare (reversing D-04's coalesced fallback), backfilled the 6 real vetoed companies under one disclosed company-write deviation, wired both engines to emit the mirror from a single derivation with drift control, deployed and bounced the live n8n instance, and re-ran the gate to confirm the fix matches the pre-registered expectation exactly.**

## Performance

- **Duration:** ~110 min (continuation from Task 3 after an operator checkpoint)
- **Completed:** 2026-08-14T09:36:00+10:00
- **Tasks:** 5 (Task 1 + checkpoint decision by a prior executor; Tasks 3-5 this session)
- **Files modified:** 22 (5 created, 17 modified)

## Accomplishments

- Backfilled `lv_anti_icp_flag_num=1` onto the 6 checkpoint-authorised, live-derived vetoed companies (Supertech Electronics, Queensland Racing Integrity Commission, Jam TV, Big Screen Video, Sportsbet, Simtech LED) via a new armed, capped (`MAX_BACKFILL_RECORDS=10`), payload-scope-asserted script -- the phase's one disclosed D-16 company-write deviation, verified by independent per-record re-read.
- Shipped the corrected `lv_icp_tier_derived` formula live: veto guard reads `coalesce(lv_anti_icp_flag_num, 0) = 1` instead of the unreadable boolean; the three score comparisons are uncoalesced bare `lv_icp_fit_score` references (D-21 reverses D-04). Polled (never single-read, D-22) to confirm: Simtech LED settled to `D` (~2 min after the PATCH), a scored control (Rockhampton Jockey Club) stayed `B`, and a never-scored control (Newcastle Jockey Club) stayed blank across a 190s poll rather than reading `"Unscored"`.
- Wired both engines to emit the mirror from one derivation: `src/icp_scoring.py::anti_icp_flag_properties()` (offline oracle serializer) and `scripts/build_cloud_workflows.py`'s `Decide Company Action` node's new `flagIsSet` local (assigns both `lv_anti_icp_flag` and `lv_anti_icp_flag_num` from the same value, adjacent). `n8n/wf_enrichment_cloud.json` regenerated (never hand-edited), confirmed idempotent on a second rebuild. New `tests/n8n/antiIcpFlagMirror.test.mjs` executes the BUILT node over every veto trigger, several together, and the clean no-veto case, asserting the pair is never half-set.
- Added a population-level mirror-agreement check (`mirror_disagrees()`/`render_mirror_section()` in `check_tier_derived_parity.py`, still zero `requests.{post,patch,delete}` calls in the module) and two permanent guards: `VETO_PROPERTY_NAMES` (no HubSpot-native flow may ever write the mirror) and `DO_NOT_ARCHIVE_COMPANY_PROPERTIES` (archiving the mirror is machine-flagged as damage).
- Deployed (`DRY_RUN=false ALLOW_N8N_DEPLOY=true`) and bounced (deactivate/reactivate, both legs independently re-read) `LV Enrichment (Cloud template)`. Obtained a running-content proof stronger than a stored read-back: an unarmed recompute POST against Simtech LED dispatched execution `11879`, and `Decide Company Action`'s own `runData` in that execution shows `lv_anti_icp_flag_num="1"` -- the live running node, not merely the stored definition.
- Re-ran D-07's gate and D-19's census live (twice, byte-identical modulo the embedded timestamp) against the corrected property. Result matches the pre-registered expectation exactly: **61 match / 4 expected_mismatch / 1 defect**; census **A 9 / B 45 / C 4 / D 6 / Unscored 2**. The 1 residual defect is Coffs Harbour Racing Club (`14752488879`) -- a pre-existing, unrelated WF1-staleness case (WINDOWS.md id 14) of the OPPOSITE polarity (the derived value is correct, the stale enum is wrong), not a veto-guard regression.
- Found and fixed a real bug the formula correction exposed: `render_census_markdown`'s never-scored disclosure was still trusting the frozen `50-NULL-PROBE.json` probe result (`settled_variant=coalesced_minus_one`), which no longer described the shipped, corrected formula. Added `_current_null_variant()`, deriving the CURRENT null-handling shape from the live declared formula instead, and a new `uncoalesced_post_d21` census branch stating the D-21 reversal accurately. `50-NULL-PROBE.json` itself stays byte-unaltered throughout (confirmed by `git diff`).
- Appended the re-run as a dated 2026-08-14 post-correction section to `50-TIER-PARITY-EVIDENCE.md`, below 50-03's original FAIL verdict (both stay visible). Closed `WINDOWS.md` id 13 with a `RESOLVED WITH EVIDENCE` note naming both fix commits and the evidence trail; left id 14 open. Amended `REQUIREMENTS.md`: TIER-01 stays Blocked (the veto-guard defect it cited is fixed, but the gate's own rule keeps it gated on the residual Coffs Harbour defect -- extending the exception list is Plan 04/05's decision, not taken here); TIER-02 marked complete with a correction-of-record note (D-21 reversed its original finding); Out of Scope's D-01 no-new-properties bullet gets a dated D-20 extension.

## Task Commits

Each task was committed atomically:

1. **Task 1: Declare and create `lv_anti_icp_flag_num`, report backfill blast radius (D-20)** - `8f6027b` (feat) -- prior executor, before this session's checkpoint
2. **Task 2: Authorise the D-16 deviation** - (decision checkpoint, no commit) -- resolved `backfill-scoped` by the operator
3. **Task 3: Backfill the mirror, ship the corrected formula, poll one record to D (tracer)** - `b12266a` (feat)
4. **Task 4: Both engines emit the mirror from one derivation, with drift control** - `13fac29` (feat)
5. **Task 5: Re-run D-07's gate and the D-19 census, append the verdict, amend the ledgers** - `80d1552` (docs)

**Plan metadata:** committed with this SUMMARY

## Files Created/Modified

- `scripts/backfill_anti_icp_flag_num.py` - armed, capped, payload-scope-asserted D-16 backfill script (`--plan`/`--execute`)
- `tests/test_backfill_anti_icp_flag_num.py` - offline pins for the payload-scope guard, cap refusal, two-key gate, search-filter exclusion
- `tests/n8n/antiIcpFlagMirror.test.mjs` - behavioural drift test executing the BUILT `Decide Company Action` node
- `.planning/phases/50-derived-tier-property/50-MIRROR-SCOPE.md` - read-only blast-radius report (Task 1)
- `.planning/phases/50-derived-tier-property/50-MIRROR-BACKFILL.md` - the D-16 deviation record: authorisation, PATCH log, D-22 poll proofs
- `config/hubspot_properties.yaml` - declares `lv_anti_icp_flag_num`; corrected `lv_icp_tier_derived` formula
- `config/hubspot_flows/lv_icp_tier_derived-property.after.json` - refreshed from the live read-back after the formula PATCH
- `src/icp_scoring.py` - `anti_icp_flag_properties()`: one derivation, two serializations
- `scripts/build_cloud_workflows.py` - `Decide Company Action`'s `flagIsSet` local assigns both properties
- `n8n/wf_enrichment_cloud.json` - regenerated (never hand-edited); deployed and bounced live
- `scripts/check_tier_derived_parity.py` - `mirror_disagrees()`, `render_mirror_section()`, `_current_null_variant()`
- `scripts/check_schema_drift.py` - `DO_NOT_ARCHIVE_COMPANY_PROPERTIES` learns the mirror (11->12)
- `tests/test_tier_formula_pin.py` - re-pinned against the mirror-guard, uncoalesced-score formula
- `tests/test_icp_scoring.py`, `tests/test_tier_derived_tools.py`, `tests/test_flow_rubric_conformance.py`, `tests/test_check_schema_drift.py`, `tests/test_cloud_companies_branch.py`, `tests/test_hubspot_properties_config.py` - offline pins for all of the above, plus 2 pre-existing tests fixed (string-literal pins, property-count guard)
- `.planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md` - dated 2026-08-14 post-correction D-07 verdict + D-19 census, appended
- `.planning/REQUIREMENTS.md` - TIER-01/TIER-02 traceability rows updated; Out of Scope D-20 extension
- `.planning/WINDOWS.md` - id 13 closed with evidence; id 14 stays open

## Decisions Made

- **D-16's one deviation was spent exactly as scoped.** The operator authorised `backfill-scoped` against the 6-id list `50-MIRROR-SCOPE.md` enumerated; the backfill script's own `--plan` output matched that list exactly before the armed run. No company write occurred anywhere else in this plan.
- **D-21 (operator, mid-execution) reversed D-04.** The original coalesced-fallback finding was a race (an unsettled calculated property read back immediately after create), not a real null-propagation result. Re-tested with polling: null does not propagate. The shipped formula un-flips the ~646-record blank->`"Unscored"` change.
- **TIER-01 is left NOT marked complete**, even though the specific defect it originally cited (the veto guard never firing) is now fixed and live-verified. The gate's own rule (any row outside the 4 pre-registered stuck ids is a defect) keeps D-06/D-08 gated on one residual, differently-caused, opposite-polarity defect. Extending the exception list to absorb it is explicitly Plan 04/05's decision, per this plan's own prohibition against `KNOWN_STUCK_IDS` growing to make the gate pass by redefinition.
- **`_current_null_variant()` was added rather than editing `50-NULL-PROBE.json`.** The frozen probe result is historical evidence of what was believed before D-21; the census renderer now derives the CURRENT formula behavior from the live declared config instead, so operator-facing text never lies about what the shipped formula does.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `render_census_markdown`'s never-scored disclosure trusted a now-stale frozen probe result**
- **Found during:** Task 5 (the live census re-run, before appending the artifact)
- **Issue:** The census's "Never-scored population" section unconditionally read `50-NULL-PROBE.json`'s `settled_variant` (`coalesced_minus_one`) to decide which disclosure text to render. D-21 reversed that probe's finding, but the renderer had no way to know -- it would have rendered "D-04's forced fallback fired ... each now reading `lv_icp_tier_derived="Unscored"`" against a formula that, live, now correctly reads blank. This is a real, user-visible correctness bug the formula fix itself exposed, not a pre-existing issue out of scope.
- **Fix:** Added `_current_null_variant()`, deriving the current null-handling shape from `config/hubspot_properties.yaml`'s live declared formula (0 `coalesce(lv_icp_fit_score` occurrences => uncoalesced) rather than the frozen probe. Added a new `uncoalesced_post_d21` branch to `render_census_markdown` stating the D-21 reversal accurately, including the un-flip and a named sampled record. `main()`'s `--census` mode now calls `_current_null_variant()` instead of `_read_settled_variant()` (kept, docstring-updated, for historical reference only).
- **Files modified:** `scripts/check_tier_derived_parity.py`, `tests/test_tier_derived_tools.py`
- **Verification:** New offline tests (`test_current_null_variant_matches_the_shipped_uncoalesced_formula`, `test_render_census_markdown_uncoalesced_post_d21_states_the_reversal_and_un_flip`) plus a live re-run confirming the artifact's rendered text is now accurate.
- **Committed in:** `80d1552` (Task 5 commit)

**2. [Rule 1 - Bug] Two pre-existing tests broke against the `flagIsSet` refactor and the properties-count guard**
- **Found during:** Task 4 (full `pytest -q` run after the engine wiring change)
- **Issue:** `tests/test_cloud_companies_branch.py`'s `test_decide_company_action_veto_flag_assignment_is_a_quoted_string_literal` and `test_inventory_rows_6_7_8_remain_already_correct` pinned the OLD inline `vetoReasons.length > 0 ? ...` string literal, which the `flagIsSet` refactor legitimately changed. `tests/test_hubspot_properties_config.py`'s `test_exact_counts_guard_against_manifest_drift` pinned the companies-property count at 33, which Task 1's `lv_anti_icp_flag_num` addition (committed earlier in this same plan) correctly bumped to 34.
- **Fix:** Updated both string-literal assertions to the new `flagIsSet`-derived form (still asserting quoted-string-literal, D-04/P4). Bumped the count guard 33->34 with a dated comment.
- **Files modified:** `tests/test_cloud_companies_branch.py`, `tests/test_hubspot_properties_config.py`
- **Verification:** Full `pytest -q` suite green (2817 passed, 154 skipped) after the fix.
- **Committed in:** `13fac29` (Task 4 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 -- bugs directly exposed by this plan's own changes), 0 scope creep.
**Impact on plan:** Both fixes were necessary for correctness of this plan's own deliverables (an accurate evidence artifact, a green test suite); no unrelated work was pulled in.

## Issues Encountered

- `apply_fit_score_formula.py`'s own re-read verification reported a mismatch and exited 1 on the first armed run -- expected per 50-01's disclosed finding (HubSpot canonicalizes stored formula text: `=` -> `equals`, double quotes -> single quotes, inserted line breaks). Refreshed `lv_icp_tier_derived-property.after.json` from the live read-back and re-ran to a clean exit 0, per the plan's own instructions.
- The bash tool's `-c` string interpolation mangled backtick-quoted markdown content when building the evidence-artifact appendix inline; resolved by writing the generation logic to a scratch `.py` file instead (never touching the committed repo).
- `load_dotenv()`'s default search (no explicit path) fails silently when invoked from a script file outside the repo (it walks up from the calling frame's `__file__`, not from cwd) -- differs from this repo's own `-c "...; load_dotenv(); ..."` wrapper idiom, which works because a `-c` frame has no `__file__` and falls back to cwd. Worked around by passing an explicit `dotenv_path` in the one throwaway scratch script that needed it; every armed/live command run directly followed the repo's established wrapper idiom unchanged.

## User Setup Required

None - no external service configuration required. All armed commands were run directly under the standing waiver for this plan's live commands, per the resume instructions.

## Next Phase Readiness

- `lv_icp_tier_derived`'s veto branch is now provably correct for every real vetoed company (6/6), and both engines emit its numeric mirror from one derivation with drift control in both directions.
- D-07's gate has a current, honest verdict: 1 residual defect (Coffs Harbour, `WINDOWS.md` id 14), pre-existing, unrelated to this plan's fix, and of the opposite polarity (evidence FOR the derived property). `KNOWN_STUCK_IDS` is unchanged.
- Plan 04's retirement decision (D-06) and Plan 05's WF1-shutdown decision (D-08) are now materially different in kind than before this plan: the derived property is no longer WORSE than the stale enum for any real record. The one open question those plans inherit is narrow and specific -- whether Coffs Harbour's class of pre-existing WF1-staleness defect should extend the gate's exception list, or be resolved some other way -- not a fundamental correctness question about the derivation mechanism itself.
- `lv_icp_tier` still exists and WF1 (`4625147345`) is still enabled -- untouched by this plan, as required.
- `50-NULL-PROBE.json` is unedited throughout this plan (confirmed via `git diff` at every task boundary).

---
*Phase: 50-derived-tier-property*
*Completed: 2026-08-14*

## Self-Check: PASSED

All 5 files claimed created confirmed present on disk. All 4 commit hashes
(`8f6027b`, `b12266a`, `13fac29`, `80d1552`) confirmed present in git log.
