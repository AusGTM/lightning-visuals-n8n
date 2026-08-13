---
phase: 50-derived-tier-property
plan: 01
subsystem: hubspot-schema
tags: [hubspot, calculation_equation, icp-tier, coalesce, properties-api]

requires:
  - phase: 49-re-score-strategy-reporting
    provides: "WINDOWS.md ids 9-12 (the 4 stuck-tier records) and the disclosed root cause -- lv_icp_tier is a property-change-event-driven enum, not derived from lv_icp_fit_score"
provides:
  - "lv_icp_tier_derived, a live calculated string property on companies that re-derives the A/B/C/D/Unscored ladder from lv_icp_fit_score and lv_anti_icp_flag on every read, with no event/enrolment/workflow dependency"
  - "scripts/check_tier_null_propagation.py -- permanent, two-key-gated live probe answering whether a null term inside an untaken calculation_equation branch blanks the whole result"
  - "scripts/check_tier_derived_parity.py -- permanent, read-only comparator between lv_icp_tier and lv_icp_tier_derived, reusable by later phases"
  - "50-NULL-PROBE.json -- committed live evidence settling D-03 vs D-04"
affects: [50-02-veto-recompute-dependents, 50-03-tier-census, 50-04-formula-pin, 50-05-retirement-decision]

actuals:
  tokens: 10434
  tasks: 4
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Two-key write gate (DRY_RUN=false AND a dedicated ALLOW_* key) for a script's own disposable-object probe, distinct from any pre-existing migration's allow-key"
    - "Archive-dependent-before-referenced teardown order for HubSpot calculated properties (a calc property's calculationFormula pins its referenced property; HubSpot 400s an archive of the referenced property while a live calc property still depends on it)"
    - "coalesce(field, sentinel) forced into a calculation_equation formula once a live probe shows a null term inside an untaken conditional branch still blanks the whole result"

key-files:
  created:
    - scripts/check_tier_null_propagation.py
    - scripts/check_tier_derived_parity.py
    - tests/test_tier_derived_tools.py
    - config/hubspot_flows/lv_icp_tier_derived-property.before.json
    - config/hubspot_flows/lv_icp_tier_derived-property.after.json
    - .planning/phases/50-derived-tier-property/50-NULL-PROBE.json
    - .planning/phases/50-derived-tier-property/50-01-TRACER-PARITY.md
  modified:
    - config/hubspot_properties.yaml
    - scripts/apply_fit_score_formula.py

key-decisions:
  - "D-03 -> D-04: the live probe found a null term inside an UNTAKEN conditional branch still blanks the whole calculation_equation result, forcing coalesce(lv_icp_fit_score, -1) into every branch reference (D-04's fallback), closing off D-03's preferred bare-reference ladder."
  - "HubSpot's Properties API canonicalizes the stored calculationFormula text on create (= becomes 'equals', double quotes become single quotes, line breaks inserted) -- the live text is not byte-identical to what was submitted, though functionally equivalent, proven by the tracer's own correct read-back results."

requirements-completed: [TIER-01, TIER-02]

coverage:
  - id: D1
    description: "Live null probe settles TIER-02's coalesce question against a real HubSpot record before any formula variant is committed to a permanent property"
    requirement: TIER-02
    verification:
      - kind: other
        ref: ".planning/phases/50-derived-tier-property/50-NULL-PROBE.json (probe_verdict=null_propagates, settled_variant=coalesced_minus_one)"
        status: pass
    human_judgment: false
  - id: D2
    description: "lv_icp_tier_derived exists live as a calculated string property with the settled formula"
    requirement: TIER-02
    verification:
      - kind: other
        ref: "GET /crm/v3/properties/companies/lv_icp_tier_derived -> 200, calculated=true, type=string, snapshotted to config/hubspot_flows/lv_icp_tier_derived-property.after.json"
        status: pass
    human_judgment: false
  - id: D3
    description: "The 4 stuck records (9605273630, 9604738976, 17696004613, 19100977027) read B on lv_icp_tier_derived while lv_icp_tier stays C, with zero writes to any of them"
    requirement: TIER-02
    verification:
      - kind: other
        ref: "scripts/check_tier_derived_parity.py --ids 9605273630,9604738976,17696004613,19100977027 -> .planning/phases/50-derived-tier-property/50-01-TRACER-PARITY.md, 4/4 expected_mismatch, 0 defects"
        status: pass
    human_judgment: false
  - id: D4
    description: "TIER-01 ladder boundaries (70/69, 40/39, 15/14) and the veto-precedes-score / -1 sentinel cases pinned offline"
    requirement: TIER-01
    verification:
      - kind: unit
        ref: "tests/test_tier_derived_tools.py (32 tests, includes derived_tier boundary and veto cases)"
        status: pass
    human_judgment: false

duration: ~35min (continuation from checkpoint)
completed: 2026-08-13
status: complete
---

# Phase 50 Plan 01: Derived Tier Property Summary

**`lv_icp_tier_derived` is live on HubSpot companies -- a self-recalculating string property that reads `B` for all 4 stuck-tier records the moment it exists, with zero writes to any of them.**

## Performance

- **Duration:** ~35min (this continuation session; full plan across two sessions)
- **Completed:** 2026-08-13T21:37:30Z
- **Tasks:** 4 (1: probe+comparator build, 2: armed null probe, 3: property declaration, 4: live create + tracer proof)
- **Files modified:** 10 (across the full plan)

## Accomplishments

- Built and offline-pinned two permanent scripts (`check_tier_null_propagation.py`, `check_tier_derived_parity.py`) plus a 32-case test module, all disarmed by default.
- Ran the armed live null probe: a null term inside an **untaken** `calculation_equation` branch blanks the whole result. This settles TIER-02 as `coalesced_minus_one` (D-04's forced fallback), not D-03's preferred bare-reference ladder.
- Declared and created `lv_icp_tier_derived` live -- the one property D-01's scope lift authorises, and nothing else (undo manifest names exactly one property).
- Proved the tracer end to end, read-only: all 4 stuck records (`9605273630`, `9604738976`, `17696004613`, `19100977027`) now read `lv_icp_tier_derived=B` while the stale `lv_icp_tier` still reads `C` and `lv_icp_fit_score` is `45` -- the fix required no PATCH, no event, no enrolment, no workflow run.
- Observed the disclosed D-04 side effect directly: a live search for companies missing `lv_icp_fit_score` returns **646** never-enriched companies; three sampled all read `lv_icp_tier_derived="Unscored"`.
- Independently re-confirmed the prior teardown-leak remediation: `lv_tier_probe_score_eb671fb7`, `lv_tier_probe_calc_eb671fb7`, and company `281675219408` are all now `404` live.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the null probe and the parity comparator** - `02f1744` (test)
2. **Task 2: Commit live null-probe evidence — D-04 fires** - `73c3c94` (docs)
2b. **Fix teardown-ordering bug (leaked disposable)** - `6ed1b4e` (fix)
3. **Task 3: Declare `lv_icp_tier_derived` + generalize formula applier** - `3f89fb4` (feat)
4. **Task 4: Create `lv_icp_tier_derived` live and read B off the 4 stuck records** - `078204b` (docs)

**Plan metadata:** committed with this SUMMARY

## Files Created/Modified

- `scripts/check_tier_null_propagation.py` - two-key-gated live probe (D-05); creates/reads/archives its own disposable numeric property, calculated property, and company
- `scripts/check_tier_derived_parity.py` - read-only comparator between `lv_icp_tier` and `lv_icp_tier_derived`; re-derives the scored population live on every run, accepts `--ids` to restrict
- `tests/test_tier_derived_tools.py` - 32 offline tests pinning `derived_tier`, `classify_probe_result`, `classify_row`, `_writes_allowed`, `render_parity_markdown`
- `config/hubspot_properties.yaml` - declares `lv_icp_tier_derived` (string, `calculation_equation`, the settled `coalesced_minus_one` formula)
- `scripts/apply_fit_score_formula.py` - generalized with `--property NAME` (default `lv_icp_fit_score`, existing invocation unchanged byte-for-byte)
- `config/hubspot_flows/lv_icp_tier_derived-property.before.json` - pre-create absence snapshot
- `config/hubspot_flows/lv_icp_tier_derived-property.after.json` - live post-create snapshot, secrets-scrubbed
- `.planning/phases/50-derived-tier-property/50-NULL-PROBE.json` - committed probe evidence
- `.planning/phases/50-derived-tier-property/50-01-TRACER-PARITY.md` - committed tracer parity report over the 4 stuck ids
- `config/hubspot_migration/undo-manifest-4dbbea94-9a2d-4e36-849a-7de126561fa6.json` - rollback anchor for the live create (names `lv_icp_tier_derived` only)

## Decisions Made

- **D-03 -> D-04 (forced, not preferred).** The live probe's disposable calculated property, referencing a disposable numeric stand-in left null (never set), read back blank on the disposable company. That is `null_propagates`: a null term inside an *untaken* conditional branch still blanks the whole `calculation_equation` result. D-04's `coalesce(lv_icp_fit_score, -1)` fallback is the settled variant; D-03's bare-reference ladder is closed off. `-1` and a genuine score of `-1` are indistinguishable and both derive `Unscored`, which is behaviour-preserving (both would have read `Unscored` under D-03 too, had it held).
- **The disclosed ~646-record flip is real and now observed, not merely projected.** A live `NOT_HAS_PROPERTY(lv_icp_fit_score)` search returns `total: 646`. Every sampled record reads `lv_icp_tier_derived="Unscored"` where `lv_icp_tier` was previously blank/`None`. This is the concrete population Plan 03's census will size precisely; this plan confirms the mechanism and order of magnitude match.
- **Teardown leak (2026-08-13, this session's own probe run) is remediated, not rewritten.** `50-NULL-PROBE.json`'s `teardown.all_gone: false` is committed evidence of the state *at probe time* and is correct as historical record -- it was **not** edited. Root cause (fixed in `6ed1b4e`, before this task): teardown archived the numeric stand-in before the calculated property that still referenced it, and HubSpot refuses to archive a property a live calculation depends on. The operator ran the corrected teardown/cleanup out of band; this plan's own independent live re-read (GET on both property names and the company id) confirms all three now `404`. Recorded here, dated, as a separate fact layered on top of the original evidence -- leak-then-remediated, not silently clean.
- **Soft-archive finding confirmed (RESEARCH Q6).** `50-NULL-PROBE.json`'s `archived_listing_finding.calculated_property_reappears: true` shows the calculated disposable reappeared under `GET ...?archived=true` after its `DELETE`. This is direct evidence the Properties API `DELETE` is a soft archive, not a hard delete -- input to D-06's blast-radius accounting and consistent with D-15's rename-infeasibility flag (an archived name is not straightforwardly reusable).
- **HubSpot canonicalizes the stored `calculationFormula` text on create (new finding, this task).** The formula submitted at create time (`config/hubspot_properties.yaml`'s literal, byte-identical to `50-NULL-PROBE.json`'s recorded literal) is **not** what a subsequent `GET` returns. The live-stored text reads `equals 1` instead of `= 1`, single quotes instead of double quotes around string literals, and carries inserted line breaks after some (not all) branches. See "Deviations" below -- this affects the plan's own literal byte-identity acceptance criterion but not the property's function.

## Deviations from Plan

### Auto-fixed / Disclosed Issues

**1. [Discovery, not a bug -- disclosed per project convention] Live `calculationFormula` is not byte-identical to the submitted literal**
- **Found during:** Task 4 (live read-back of the created property)
- **Issue:** The plan's own `<verify>` block asserts `a['calculationFormula'] == n['calculation_formula']` (byte equality between the live GET and `50-NULL-PROBE.json`'s recorded literal). Run literally, this assertion **fails**: HubSpot's Properties API returns a server-canonicalized version of the formula (`=` -> `equals`, `"` -> `'`, and inserted line breaks), even though the exact same literal was submitted at create time (confirmed: `config/hubspot_properties.yaml`'s `calculationFormula` value is byte-identical to `50-NULL-PROBE.json`'s `calculation_formula` value, both pre-creation).
- **Resolution:** Did not attempt to force byte-identity (there is no live write path that changes how HubSpot echoes formula text back -- `scripts/apply_fit_score_formula.py` PATCHes the same textual grammar and would be re-canonicalized identically). Verified functional equivalence instead: the tracer's own live read-backs are exactly correct -- all 4 stuck records read `B`, the never-scored sample reads `Unscored`, matching D-04's semantics precisely. The live-canonicalized text is captured verbatim in the committed `lv_icp_tier_derived-property.after.json` snapshot, which is now the honest source of truth for any future drift check (matching the plan's own Task 4 note that "the property is the formula's source of truth from here").
- **Files affected:** `config/hubspot_flows/lv_icp_tier_derived-property.after.json` (records the true live text)
- **Impact on later plans:** Plan 03's/04's formula-pin test (`tests/test_tier_formula_pin.py`, not yet built) must NOT assert byte-identity against the pre-creation literal in `50-NULL-PROBE.json` or `config/hubspot_properties.yaml` -- it should pin against the live-read canonicalized text captured in this task's `.after.json` snapshot, or normalize both sides (case-insensitive `=`/`equals`, quote-style-insensitive) before comparing.
- **Committed in:** `078204b` (Task 4 commit, with full disclosure in the commit message)

---

**Total deviations:** 1 disclosed discovery (live API canonicalization behavior), 0 scope creep, 0 company writes.
**Impact on plan:** All four `must_haves.truths` and both TIER-01/TIER-02 requirements are met on their functional merits. One of the plan's own literal `<verify>` assertions (byte-for-byte formula equality) cannot be satisfied due to HubSpot's own server-side text canonicalization, which was not knowable before this task's live read-back. Disclosed rather than silently worked around.

## Issues Encountered

None beyond the disclosed formula-canonicalization finding above. All reads (property GET x2, company GET x4 via the parity script, one search over `NOT_HAS_PROPERTY(lv_icp_fit_score)`, three property/company existence GETs for the leak re-check) were read-only. Zero PATCH/POST-mutate/DELETE calls issued against any company record in this task -- D-16 held throughout.

## User Setup Required

None - no external service configuration required. Both armed commands (null probe, live property create) were run by the operator per the checkpoint; this continuation performed only read-only verification and evidence capture.

## Next Phase Readiness

- `lv_icp_tier_derived` is live, correct, and proven against real records. Plan 03's tier census can now size the full ~646-record population precisely and produce the before/after report (D-19).
- Plan 02's dependent sweep already ran (`f27fef3`) in parallel on this tree and is separately paused at its own checkpoint -- untouched by this plan.
- Plan 05's retirement decision (archiving `lv_icp_tier` / WF1) remains gated behind D-06/D-07's operator decision and is explicitly out of this plan's scope.
- Carry forward for any future formula-pin work: compare against the live-canonicalized text (`lv_icp_tier_derived-property.after.json`), not the pre-creation literal.

---
*Phase: 50-derived-tier-property*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 11 files claimed created/modified confirmed present on disk. All 5 commit hashes
(`02f1744`, `73c3c94`, `6ed1b4e`, `3f89fb4`, `078204b`) confirmed present in git log.
