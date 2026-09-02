---
phase: 21-transport-schema-hygiene
plan: 02
subsystem: infra
tags: [n8n, hubspot, field-policy, merge-policy, icp-scoring, conformance-test]

# Dependency graph
requires:
  - phase: 21-transport-schema-hygiene
    provides: "Plan 01's dedupe transport swap (no shared files besides the
      generic tests/test_hubspot_node_auth.py change, orthogonal here)"
provides:
  - "lv_country_region_normalized field-policy entry in both
    config/field_policy.yaml (companies) and mergeCompanies.js
    (DEFAULT_COMPANY_POLICY): class system_owned, min_confidence 75, with the
    threshold rationale recorded verbatim in both files"
  - "tests/test_field_policy_conformance.py: a yaml<->JS drift guard for the
    entire companies field-policy table, not just this one field"
  - "Two threshold cases in tests/n8n/mergeCompanies.test.mjs pinning
    promote-at-75 / stage-and-needs_review-at-74 for
    lv_country_region_normalized"
  - "Re-baselined tests/fixtures/companies_jscode_frozen.json with a proven
    bounded diff (Merge Company x 2, nothing else)"
affects: [22-armed-pipeline-activation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-mirrored policy table conformance via node subprocess, not regex:
      the JS table is read by shelling out to node and asking the module for
      its own serialized DEFAULT_COMPANY_POLICY, because the object literal
      carries a computed reference (lv_org_type.require_evidence_url_for ->
      EVIDENCE_GATED_ORG_TYPES) that a text parse of the source would get
      wrong. Mirrors the taxonomy conformance module's existing precedent but
      applies it to a table that has no generator at all."
    - "Bounded-diff proof before a frozen-fixture re-baseline (third instance,
      after 4d87fb3 and its predecessors): build both variants in the
      scratchpad, diff every {variant, node} pair against the committed
      fixture, and only write the new fixture once the diff set is proven to
      be exactly what the causing edit should produce."

key-files:
  created:
    - tests/test_field_policy_conformance.py
  modified:
    - config/field_policy.yaml
    - n8n/code/mergeCompanies.js
    - tests/n8n/mergeCompanies.test.mjs
    - tests/fixtures/companies_jscode_frozen.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_scheduled_maintenance_cloud.json

key-decisions:
  - "Threshold set to 75 (not 70 like lv_employee_band, not 85 like the
    evidence-gated ICP fields): recorded identically in both config files as
    a reviewable judgment, not a derived constant, because the field feeds
    the non-ANZ hard veto (wrong promotion disqualifies a real account) but
    carries no evidence-URL requirement (demanding 85 would leave it
    effectively stage-only forever)."
  - "The conformance test asserts class and min_confidence only for shared
    keys, and only compares min_confidence where the YAML side actually
    declares one -- the two veto_output fields (lv_anti_icp_flag,
    lv_anti_icp_reason) have no YAML min_confidence and are excluded from
    that comparison rather than forcing JS's placeholder 0 into a second
    source of truth."
  - "n8n/wf_scheduled_maintenance_cloud.json, not in this plan's declared
    files_modified, was rebuilt and committed alongside the fixture
    re-baseline: its 'Apply Review' Code node also inlines
    DEFAULT_COMPANY_POLICY (the needs-review scan reads the same table), and
    the rebuild diff was verified byte-identical in content to the two proven
    Merge Company diffs -- the same 7-line comment plus the one policy line,
    nothing else. Investigated per the plan's own caution rather than
    committed over blindly; concluded this is the same edit reaching a third
    Code node that shares the module, not Plan 01 leftover staleness."
  - "n8n/wf_enrichment_local.json was rebuilt (scripts/build_cloud_workflows.py
    always writes all six workflow files) but produced no diff: that
    variant's mock-provider node graph has no node named Merge Company and
    never inlines DEFAULT_COMPANY_POLICY, so it was never a candidate for
    this change despite being named in the plan's files_modified."

patterns-established:
  - "A hand-mirrored policy table with zero generator gets a conformance test
    read via subprocess+JSON, never regex-over-source, whenever a computed
    reference (not a literal) can appear in the JS object."

requirements-completed: [REQ-country-region-policy]

coverage:
  - id: D1
    description: "lv_country_region_normalized at or above 75 confidence
      promotes to canonicalPatch on both the JS (n8n) and Python (offline
      oracle) merge paths instead of falling through to the generic
      fill_blank_only default"
    requirement: "REQ-country-region-policy"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeCompanies.test.mjs::mergeCompanies: lv_country_region_normalized at min_confidence promotes with provenance"
        status: pass
      - kind: unit
        ref: "tests/test_merge_policy.py -q (28 passed, unchanged behavior confirmed with zero Python code change)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The same candidate below 75 confidence does not promote,
      stages with full provenance, and its decision is needs_review"
    requirement: "REQ-country-region-policy"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeCompanies.test.mjs::mergeCompanies: lv_country_region_normalized below min_confidence stages only, still provenanced"
        status: pass
    human_judgment: false
  - id: D3
    description: "config/field_policy.yaml and mergeCompanies.js
      DEFAULT_COMPANY_POLICY cannot drift silently: identical key sets,
      matching class, matching min_confidence where YAML declares one"
    requirement: "REQ-country-region-policy"
    verification:
      - kind: unit
        ref: "tests/test_field_policy_conformance.py -q (3 passed)"
        status: pass
      - kind: manual_procedural
        ref: "Non-vacuity proven both directions in the scratchpad: deleting the YAML entry fails test_key_sets_are_identical; changing the JS min_confidence from 75 to 60 fails test_min_confidence_matches_where_yaml_declares_it with the (75, 60) pair named. Both files restored, git diff clean afterward."
        status: pass
    human_judgment: false
  - id: D4
    description: "The frozen companies jsCode fixture was re-baselined as a
      deliberate named-cause act, diff proven bounded to Merge Company before
      the fixture was written"
    requirement: "REQ-country-region-policy"
    verification:
      - kind: manual_procedural
        ref: "Scratchpad bounded-diff proof: exactly 2 of 14 {variant, node} pairs differed (Merge Company x cloud, Merge Company x local_live), each diff identical (the added comment + policy line, nothing else). See Accomplishments for the captured diff."
        status: pass
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py -q (4 passed, post re-baseline)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both full suites green after the whole plan"
    requirement: "REQ-country-region-policy"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q -> 621 passed"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs -> 354 passed"
        status: pass
    human_judgment: false

# Metrics
duration: ~20min
completed: 2026-07-30
status: complete
---

# Phase 21 Plan 02: Country-Region Field Policy Summary

**`lv_country_region_normalized` now promotes to canonical at 75+ confidence on both the JS and Python merge paths, backed by a new yaml-vs-JS conformance test and a re-baselined, bounded-diff-proven frozen fixture.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-30T17:26:00Z (approx.)
- **Completed:** 2026-07-30T17:36:26Z
- **Tasks:** 3
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- Added `lv_country_region_normalized` (class `system_owned`, `min_confidence: 75`)
  to `config/field_policy.yaml`'s `companies:` block and the matching
  `DEFAULT_COMPANY_POLICY` entry in `n8n/code/mergeCompanies.js`, with the same
  rationale comment recorded verbatim in both files: 75 sits above the flat
  firmographic band (`lv_employee_band` at 70) because this field feeds the
  non-ANZ hard veto, and below the evidence-gated judgment fields (85) because
  it is a normalized enum with no evidence-URL requirement. `src/merge_policy.py`
  needed zero code change to pick up the new YAML key — confirmed by
  `tests/test_merge_policy.py`/`tests/test_icp_scoring.py` staying green
  (28/28) unmodified.
- Two new threshold cases in `tests/n8n/mergeCompanies.test.mjs`, written FIRST
  as a RED/GREEN pair per the task's `tdd="true"` flag: a candidate at exactly
  `min_confidence` promotes with full provenance; the same candidate one point
  below stages only, stays provenanced, and reports `needs_review`. Neither
  hardcodes 75 — both read `DEFAULT_COMPANY_POLICY.lv_country_region_normalized.min_confidence`.
- New `tests/test_field_policy_conformance.py`: reads the JS table via
  `node -e` (never regex, since `lv_org_type.require_evidence_url_for` is a
  reference to the generated taxonomy module, not a literal) and asserts
  identical key sets, matching `class`, and matching `min_confidence` wherever
  YAML declares one. Non-vacuity proven both directions in the scratchpad
  (values restored after each): deleting the YAML entry fails the key-set
  assertion naming `lv_country_region_normalized` as missing from
  `n8n/code/mergeCompanies.js`; changing the JS `min_confidence` to 60 fails
  the threshold assertion with `{'lv_country_region_normalized': (75, 60)}`.
  With `node` excluded from `PATH` (a scoped tmp-dir override), all 3 tests
  skip cleanly with reason `"node not on PATH"` rather than erroring.
- Re-baselined `tests/fixtures/companies_jscode_frozen.json` only after
  proving the bounded diff in the scratchpad: extracted jsCode for all 7
  frozen node names across both `cloud` and `local_live` variants from a
  fresh build (14 {variant, node} pairs total) and diffed each against the
  committed fixture. **Exactly 2 of 14 pairs differed** — `Merge Company` in
  each variant — and each difference was **byte-identical**: the 7-line
  rationale comment plus the single added policy line, nothing else. Ran
  `scripts/build_cloud_workflows.py` only after that proof.
- The rebuild also dirtied `n8n/wf_scheduled_maintenance_cloud.json`, which is
  outside this plan's declared `files_modified`. Investigated per the plan's
  own caution rather than committing over it: its one changed Code node
  (`Apply Review`, the needs-review scan) also inlines
  `DEFAULT_COMPANY_POLICY`, and its diff is content-identical to the two
  proven `Merge Company` diffs — the same comment block and policy line, no
  other change. This is this plan's own edit reaching a third node that
  shares the module, not stale Plan-01 drift, so it was committed alongside
  the fixture. `n8n/wf_enrichment_local.json` was also rebuilt but produced
  no diff — that variant's mock node graph has no `Merge Company` node.
- Both full suites green at the end: `.venv/bin/python -m pytest -q` → 621
  passed (up from 618, the 3 new conformance tests plus the 4 frozen-fixture
  tests flipping back from fail to pass), 0 failed. `node --test
  tests/n8n/*.test.mjs` → 354 passed (352 baseline + the 2 new threshold
  cases), 0 failed.

## Task Commits

Each task was committed atomically (Task 1 used the RED/GREEN TDD flow per
its `tdd="true"` frontmatter flag):

1. **Task 1 RED: failing threshold cases** - `27f8214` (test)
2. **Task 1 GREEN: policy entry on both mirrored surfaces** - `9926b39` (feat)
3. **Task 2: yaml-vs-JS conformance test** - `4ede74e` (test)
4. **Task 3: re-baselined frozen fixture + rebuilt workflows** - `8dfdc31` (test)

**Plan metadata:** committed separately per the final_commit step (this
SUMMARY, STATE.md/ROADMAP.md untouched per the plan's project constraints,
REQUIREMENTS.md checkbox ticked).

## Files Created/Modified

- `config/field_policy.yaml` — new `companies.lv_country_region_normalized`
  entry (system_owned, min_confidence 75) with rationale comment
- `n8n/code/mergeCompanies.js` — matching `DEFAULT_COMPANY_POLICY` entry with
  the same rationale comment (formatting: one space before `{` since the key
  is longer than every existing aligned column, consistent with the pattern
  everywhere else)
- `tests/n8n/mergeCompanies.test.mjs` — two new threshold cases
- `tests/test_field_policy_conformance.py` — new: yaml<->JS drift guard,
  reads JS via `node -e`, skips (not errors) without `node`
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined (`cloud` +
  `local_live`, `Merge Company` entries only)
- `n8n/wf_enrichment_cloud.json` — rebuilt, `Merge Company` node only
- `n8n/wf_enrichment_local_live.json` — rebuilt, `Merge Company` node only
- `n8n/wf_scheduled_maintenance_cloud.json` — rebuilt, `Apply Review` node
  only (see key-decisions for why this is in scope)

## Decisions Made

See `key-decisions` in the frontmatter. In summary: 75 as a recorded judgment
call rather than a derived constant; the conformance test's asserted surface
(class + min_confidence-where-declared, not every key); and including the
scheduled-maintenance workflow's rebuild in this plan's scope because it is
the same edit reaching a shared module, not unrelated drift.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical / scope-adjacent] Rebuilt and committed
`n8n/wf_scheduled_maintenance_cloud.json` alongside the fixture re-baseline**
- **Found during:** Task 3, running `scripts/build_cloud_workflows.py` after
  the bounded-diff proof
- **Issue:** the script rewrites all six workflow files unconditionally;
  `wf_scheduled_maintenance_cloud.json` (not in this plan's `files_modified`)
  came out dirty. The plan explicitly flagged this exact scenario and
  required investigation rather than a blind commit.
- **Fix:** diffed the one changed node (`Apply Review`) against the two
  already-proven `Merge Company` diffs — content-identical (same 7-line
  comment + one policy line). Concluded this is the country-region policy
  edit reaching a second Code node that also inlines
  `DEFAULT_COMPANY_POLICY` (the needs-review scan), not stale Plan-01
  output. Committed it in the same atomic Task 3 commit as the fixture,
  since leaving it dirty would violate the plan's own
  `git status --porcelain n8n/` clean requirement and would leave the live
  scheduled-maintenance workflow's needs-review scan silently running the
  pre-edit policy table forever.
- **Files modified:** `n8n/wf_scheduled_maintenance_cloud.json`
- **Verification:** diff captured and compared line-for-line against the
  Merge Company diffs (identical); full suite green afterward
  (621 Python passed, 354 JS passed); `git status --porcelain n8n/` clean.
- **Committed in:** `8dfdc31` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — a shared-module edit legitimately
reaching a Code node outside the plan's declared `files_modified`, verified
content-identical to the in-scope changes before being committed).
**Impact on plan:** Necessary — without this, the deployed scheduled
needs-review scan would silently keep using the stale policy table, and the
working tree would be left dirty in violation of the plan's own acceptance
criteria. No scope creep: the diff is byte-for-byte the same edit, applied to
a third consumer of the same inlined module.

## Issues Encountered

None beyond the expected, plan-anticipated `tests/test_companies_factory_frozen.py`
failure window between Task 1 and Task 3 (4 tests failed after Task 1's edit,
all 4 confined to that one file, all 4 passed again after Task 3's
re-baseline).

## User Setup Required

None — no external service configuration required. This plan produces only
config/test/artifact edits; per the plan's project constraints, the workflows
rebuilt here are committed but NOT redeployed (the live deployment predates
them). **Pending for Phase 21 close-out:** `n8n/wf_enrichment_cloud.json`,
`n8n/wf_enrichment_local_live.json`, and `n8n/wf_scheduled_maintenance_cloud.json`
need a disarmed redeploy (same pattern as Plan 01's Task 3) before the live
n8n instance serves the new `lv_country_region_normalized` policy entry.

## Next Phase Readiness

- Roadmap SC4 is satisfied: `lv_country_region_normalized` has a real
  governance entry on both merge paths, protected from silent drift by a
  conformance test.
- The frozen-fixture re-baseline discipline (bounded-diff-proof-before-write)
  has now been exercised a third time in this repo with zero unrelated drift
  laundered through it.
- Live deployment of the three rebuilt workflow artifacts is deferred to
  Phase 21 close-out (see User Setup Required) — do not assume the live n8n
  instance already reflects this plan's policy change.
- Plan 21-03 (org_type schema migration) and 21-04 are unaffected by this
  plan's scope; no shared files besides the generic
  `n8n/wf_scheduled_maintenance_cloud.json` rebuild, which only touched the
  `Apply Review` node's inlined policy table.

## Self-Check: PASSED

- FOUND: `config/field_policy.yaml` (lv_country_region_normalized entry present)
- FOUND: `n8n/code/mergeCompanies.js` (DEFAULT_COMPANY_POLICY entry present)
- FOUND: `tests/test_field_policy_conformance.py`
- FOUND: `tests/fixtures/companies_jscode_frozen.json` (re-baselined)
- FOUND commit `27f8214` (Task 1 RED)
- FOUND commit `9926b39` (Task 1 GREEN)
- FOUND commit `4ede74e` (Task 2)
- FOUND commit `8dfdc31` (Task 3)

---
*Phase: 21-transport-schema-hygiene*
*Completed: 2026-07-30*
