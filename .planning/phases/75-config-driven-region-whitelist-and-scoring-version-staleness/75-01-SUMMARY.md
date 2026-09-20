---
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
plan: 01
subsystem: scoring-engine
tags: [icp-scoring, region-whitelist, codegen, n8n, hubspot, tdd]

# Dependency graph
requires:
  - phase: 46 (One-Commit Parity)
    provides: the two-engine parity discipline (src/icp_scoring.py + Decide Company
      Action) this plan's config-driven rename follows
provides:
  - config/icp_scoring.yaml as the single source of the geography whitelist and all
    three hard-veto reason strings
  - scripts/gen_icp_scoring_js.py / n8n/code/icpScoring.generated.js codegen pair
  - lv_icp_scoring_version version-staleness STAMP (write side only — no live property,
    no sweep routing yet; those are later plans in this phase)
affects: [75-02, 75-03, 75-04, 75-05, 75-06]

# Actuals (#2632)
actuals:
  tokens: 61335
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Config-driven whitelist with generated-JS mirror (gen_icp_scoring_js.py mirrors
      gen_escalation_js.py exactly) — a second instance of the Phase 12 D3 codegen
      precedent"
    - "region_key three-state resolution (home/other/unknown) replacing a hand-typed
      country-code set, identical shape in both the Python oracle and the n8n Code node"

key-files:
  created:
    - scripts/gen_icp_scoring_js.py
    - n8n/code/icpScoring.generated.js
    - tests/test_icp_scoring_generated_currency.py
  modified:
    - config/icp_scoring.yaml
    - scripts/build_cloud_workflows.py
    - src/icp_scoring.py
    - n8n/wf_enrichment_cloud.json
    - tests/test_icp_scoring.py
    - tests/test_scoring_parity.py
    - tests/test_rubric_change_guard.py
    - tests/test_backfill_seed_company_scores.py
    - tests/test_backfill_dry_run.py
    - tests/test_cloud_companies_branch.py
    - tests/test_flow_rubric_conformance.py
    - tests/test_icp_named_account_floor.py
    - tests/test_loss_reason_report.py
    - tests/test_scaffold.py
    - tests/test_remediate_veto_companies.py
    - tests/test_veto_remediation_report.py
    - tests/test_simulate_rubric_weights.py
    - scripts/remediate_veto_companies.py
    - scripts/veto_remediation_report.py
    - scripts/simulate_rubric_weights.py
    - tests/n8n/antiIcpFlagMirror.test.mjs
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs
    - tests/n8n/materialConflictNoVetoFlip.test.mjs
    - tests/n8n/reviewQueueEndpoint.test.mjs

key-decisions:
  - "Widened scope beyond the plan's files_modified list to five extra source/test files
    (scripts/remediate_veto_companies.py, scripts/veto_remediation_report.py,
    scripts/simulate_rubric_weights.py, tests/test_cloud_companies_branch.py,
    tests/test_flow_rubric_conformance.py) — the yaml key rename would have KeyError'd
    them at call time, breaking tests already in Task 2's own list that import them."
  - "US added to regions.home changed the meaning of every test that used US as the
    canonical 'genuinely non-home' veto example — swapped to DE (the plan's own example
    non-home region) across six files the plan's own grep-based scope did not surface."
  - "Kept the schema-coverage guard (tests/test_hubspot_schema_coverage.py) untouched and
    RED rather than weaken it, fabricate a manifest, or pull Plan 05's live property
    CREATE forward — same D-72-23 declare-now/create-later precedent this repo already
    established. Recorded in .planning/WINDOWS.md (unmet-truth)."
  - "Historical incident comments (5 file locations beyond build_cloud_workflows.py's
    three explicitly-protected ones) left verbatim rather than rewritten to satisfy
    Task 2's literal (comment-unaware) grep — Task 1's own explicit instruction to leave
    its three comments verbatim is the controlling precedent, extended consistently."

requirements-completed: []

coverage:
  - id: D1
    description: "config/icp_scoring.yaml is the single source of the geography
      whitelist (regions.home) and all three hard-veto reason strings, read through a
      generated JS mirror by n8n and directly by the Python oracle"
    verification:
      - kind: unit
        ref: "tests/test_icp_scoring.py#test_case_4b_region_whitelist_au_and_us_are_home_de_vetoes_blank_is_unknown"
        status: pass
      - kind: unit
        ref: "tests/test_icp_scoring_generated_currency.py#test_icp_scoring_generated_js_currency"
        status: pass
      - kind: integration
        ref: "node -e \"...\" reading n8n/wf_enrichment_cloud.json's Decide Company Action jsCode"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/gen_icp_scoring_js.py::render() refuses to generate from an
      empty/malformed regions.home or an empty hard-veto reason (T-75-01, DoS mitigation)"
    verification:
      - kind: unit
        ref: "tests/test_icp_scoring_generated_currency.py#test_render_raises_when_regions_home_is_empty"
        status: pass
      - kind: unit
        ref: "tests/test_icp_scoring_generated_currency.py#test_render_raises_when_regions_home_contains_a_non_string"
        status: pass
      - kind: unit
        ref: "tests/test_icp_scoring_generated_currency.py#test_render_raises_when_a_hard_veto_reason_is_empty"
        status: pass
    human_judgment: false
  - id: D3
    description: "Decide Company Action stamps lv_icp_scoring_version on every company it
      decides (D-75-03/D-75-20 write side); the live property and the sweep routing that
      consumes it are later plans in this phase"
    verification:
      - kind: integration
        ref: "node -e \"...\" asserting lv_icp_scoring_version present in the built jsCode"
        status: pass
    human_judgment: true
    rationale: "The property does not exist live yet (Plan 05's job, D-75-10) — nothing
      in this plan can prove the stamp lands on a real HubSpot record; the verifier
      should read this as write-side-only and cross-check .planning/WINDOWS.md's
      unmet-truth entry rather than expect a live PATCH to have succeeded."
  - id: D4
    description: "Every byte-asserting test site referencing the old geography-veto
      string/key moved in the same commit as the engines that produce it — zero
      non-historical-comment occurrence of 'non_anz' or 'Non-ANZ geography' remains
      outside frozen fixtures"
    verification:
      - kind: unit
        ref: "repo-wide grep sweep, see 'Verification' section below"
        status: pass
    human_judgment: false

duration: 95min
completed: 2026-09-20
status: complete
---

# Phase 75 Plan 01: Config-Driven Region Whitelist Summary

**`config/icp_scoring.yaml` is now the single source of the 12-country target-region
whitelist and all three hard-veto reason strings, read through both scoring engines
(Python oracle + n8n Decide Company Action) from one commit, with a generated-JS mirror,
a fail-closed generator, and a version stamp that gives a future rubric bump a real
segmentation mechanism.**

## Performance

- **Duration:** 95 min
- **Started:** 2026-09-20T05:35:00Z (approx, from STATE.md's phase-start marker)
- **Completed:** 2026-09-20T07:10:00Z
- **Tasks:** 3
- **Files modified:** 29 (3 created, 26 modified)

## Accomplishments

- `config/icp_scoring.yaml` carries `regions.home` (12 codes: AU, NZ, ANZ, US, GB, IE,
  CA, ZA, HK, SG, AE, IN, with the selection-criteria comment recorded verbatim) and
  `regions.aliases`; `base_score.geography` collapsed from five hand-typed country codes
  to three (`home`/`other`/`unknown`); `hard_vetoes.non_anz` renamed to
  `hard_vetoes.outside_home_regions` with reason `"Outside target regions"`; `version`
  bumped `lv-icp-v0.1` → `lv-icp-v0.2`.
- New `scripts/gen_icp_scoring_js.py` (mirrors `scripts/gen_escalation_js.py` exactly)
  emits `n8n/code/icpScoring.generated.js` (`VERSION`, `REGIONS_HOME`, `REGION_ALIASES`,
  `HARD_VETO_REASONS`, `GEOGRAPHY_POINTS`), fail-closed on an empty/malformed
  `regions.home` or an empty hard-veto reason.
- `Decide Company Action` (in `scripts/build_cloud_workflows.py`'s
  `ENRICH_DECIDE_CO_CLOUD`) reads the generated constants instead of hard-typed literals,
  and stamps `properties.lv_icp_scoring_version = VERSION` on every company it decides.
- `src/icp_scoring.py::compute_icp_score` mirrors the same region-key resolution and veto
  lookup against the same yaml keys — byte-identical verdicts from both engines for a
  whitelisted region (AU, US), a known non-whitelisted region (DE), and a blank/unknown
  region, proven by the plan's own acceptance-criteria CLI check.
- Every byte-asserting test site that referenced the old geography-veto string/key moved
  in the same commit — 16 files from the plan's own scope plus 5 more the full-suite run
  exposed (see Deviations).

## Task Commits

Each task's RED/GREEN split into 2-3 atomic commits (Task 1's TDD cycle, Task 2's rename
folded into the same GREEN commit per the plan's explicit "same commit" instruction, Task 3
as its own currency-guard commit):

1. **Task 1 RED:** `9eaadac0` (test) — new/updated assertions in `tests/test_icp_scoring.py`
   demonstrating the Phase 75 end-state (AU/US home, DE vetoes with the renamed reason,
   blank stays unvetoed); confirmed failing against unmodified production code.
2. **Task 1 + Task 2 GREEN:** `89aaceb1` (feat) — yaml, generator + generated artifact,
   `build_cloud_workflows.py`, `src/icp_scoring.py`, regenerated
   `n8n/wf_enrichment_cloud.json`, every Task 2 rename site plus the widened scope, and
   `tests/test_rubric_change_guard.py`'s D-75-20 re-baseline (the version stamp and the
   re-baselined guard message land together, per the plan's own instruction).
3. **Task 3:** `1bde6672` (test) — `tests/test_icp_scoring_generated_currency.py`
   (byte-equality + three fail-closed cases), perturbation RED demonstrated and restored.

**Plan metadata:** this SUMMARY's own commit (below).

## Files Created/Modified

- `config/icp_scoring.yaml` - region whitelist, renamed hard-veto key, version bump
- `scripts/gen_icp_scoring_js.py` - new generator (mirrors `gen_escalation_js.py`)
- `n8n/code/icpScoring.generated.js` - new generated artifact
- `scripts/build_cloud_workflows.py` - generator registration + `Decide Company Action`
  region/veto/version-stamp logic
- `src/icp_scoring.py` - region-key resolution + veto-reason lookup against the renamed
  yaml key
- `n8n/wf_enrichment_cloud.json` - regenerated (no hand-edit)
- `tests/test_icp_scoring_generated_currency.py` - new currency + fail-closed guard
- 22 other test files and 3 other script files - rename blast radius (see Deviations)

## Decisions Made

- **Followed the plan's explicit TDD structure via a RED→GREEN→(GREEN)→test split**
  rather than one commit per task, because Task 2's own text required its changes to land
  "in this same commit as Task 1." Reconciled by treating Tasks 1+2 as one RED/GREEN pair
  and Task 3 as its own commit — matches the plan's `tdd="true"` requirement on all three
  tasks without violating its own same-commit instruction.
- **`gsd_run check tdd-red-evidence` does not recognize pytest output** (its TAP parser
  expects `node --test`'s `# tests N` / `# pass N` / `# fail N` summary lines and
  `ok N - name` / `not ok N - name` test lines; pytest's `-q --tb=short` format has
  neither). Ran it anyway against the RED pytest run — verdict `INVALID_RED` /
  `zero_tests_discovered`, confirming the tooling gap rather than a real RED-phase
  problem. RED is evidenced instead by the actual pytest failure output, captured in the
  `9eaadac0` commit message: 3 failures, all on the target assertions (old
  `"Non-ANZ geography"` string, US still non-ANZ under the pre-Phase-75 rule).
- **The three HISTORICAL INCIDENT comments in `scripts/build_cloud_workflows.py`** (the
  blank-region narrative above `_regionKey`, and two above
  `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`) were left byte-verbatim, per Task 1's explicit
  instruction — they document a real 2026-08-10 production incident and the string they
  quote is the string that actually fired at the time. Task 2's own `<verify>` grep
  command has NO comment filter and would flag these three plus five more pre-existing
  historical comments elsewhere in the repo (see "Plan-text discrepancy" below). Followed
  Task 1's explicit, reasoned instruction over the literal grep; ran my own verification
  with the historical-comment sites excluded and documented the discrepancy here.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Five files outside `files_modified` also indexed the renamed yaml
key and would have KeyError'd or asserted stale values**
- **Found during:** Task 2 (running the full test suite after the rename)
- **Issue:** `scripts/remediate_veto_companies.py` and `scripts/veto_remediation_report.py`
  both did `cfg["hard_vetoes"]["non_anz"]["reason"]` — a yaml-KEY lookup that raises
  `KeyError` at call time once the key is renamed. `scripts/simulate_rubric_weights.py`
  hard-coded `NON_ANZ_VETO_REASON = "Non-ANZ geography"` as a Python literal, no longer
  matching the renamed yaml value. `tests/test_cloud_companies_branch.py` did the same
  yaml-key lookup in a test fixture. `tests/test_flow_rubric_conformance.py`'s
  `test_geography_flow_matches_rubric` indexed `rubric["AU"]`/`rubric["NZ"]`/
  `rubric["ANZ"]`/`rubric["non_anz"]` directly against the now-collapsed
  `base_score.geography` dict (five keys → three), which would `KeyError` immediately.
  None of these five files is in the plan's `files_modified` frontmatter or Task 2's
  `<files>` list, and RESEARCH.md's Pitfall 3 grep was scoped to `tests/` and missed
  `scripts/` entirely and this one sibling test file.
- **Fix:** Renamed all yaml-key lookups to `outside_home_regions`; renamed
  `NON_ANZ_VETO_REASON` → `OUTSIDE_HOME_VETO_REASON` (value `"Outside target regions"`);
  renamed `veto_remediation_report.py`'s classification vocabulary
  `still_non_anz`/`correct_non_anz` → `still_outside_home`/`correct_outside_home`
  (changes the script's CLI/JSON output strings — no test outside this repo consumes
  them); rewrote `test_geography_flow_matches_rubric` to assert SUBSET consistency
  (every branch value the live HubSpot flow names is in `regions.home` and scores
  `geography.home`; the default branch scores `geography.other == geography.unknown`)
  rather than exact equality against the old five-key table — the live flow still only
  names 3 of the 12 whitelisted codes, and widening it to all 12 is
  `scripts/gen_geography_flow.py`, a later plan in this phase (`tests/test_geography_flow_conformance.py`
  is that plan's own currency test).
- **Files modified:** `scripts/remediate_veto_companies.py`,
  `scripts/veto_remediation_report.py`, `scripts/simulate_rubric_weights.py`,
  `tests/test_cloud_companies_branch.py`, `tests/test_flow_rubric_conformance.py`, plus
  their test-file counterparts (`tests/test_remediate_veto_companies.py`,
  `tests/test_veto_remediation_report.py`, `tests/test_simulate_rubric_weights.py`)
- **Verification:** full `pytest` suite green for all seven files
- **Committed in:** `89aaceb1`

**2. [Rule 1 - Bug] "US" was the repo's canonical non-home veto example in six more
files; US moved into `regions.home` and those assertions became factually wrong**
- **Found during:** Task 2 and the full-suite run (an advisor consultation flagged this
  before the full-suite run confirmed it independently)
- **Issue:** `tests/test_icp_scoring.py`, `tests/test_scoring_parity.py`,
  `tests/n8n/antiIcpFlagMirror.test.mjs`, `tests/n8n/companyRecomputeLaneFlow.test.mjs`,
  `tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs`, and
  `tests/test_backfill_seed_company_scores.py` all used `"US"` as the canonical
  "genuinely non-ANZ" / "genuinely outside target regions" region in a test asserting the
  veto DOES fire. Since D-75-05 adds US to `regions.home`, these tests would have kept
  passing with WRONG semantics if only the reason string were renamed — the yaml rename
  alone does not surface this class of break (only running the tests against the real
  new whitelist does).
- **Fix:** Swapped `"US"` → `"DE"` (the plan's own example non-home region) in every
  case that asserts the veto fires; left the one `companyRecomputeLaneFlow.test.mjs`
  case that does not assert on the veto flag unchanged (region value doesn't matter
  there). Renamed
  `test_known_non_anz_region_still_vetoes_offline` →
  `test_known_outside_home_region_still_vetoes_offline` and
  `test_case_4_non_anz_veto` → `test_case_4_outside_home_region_veto` for readability
  (per Task 2's own "test name should be renamed" guidance) and to clear the `non_anz`
  substring grep.
- **Files modified:** the six files named above
- **Verification:** `node --test tests/n8n/*.test.mjs` (1321 passed / 0 failed);
  `pytest` full suite green
- **Committed in:** `89aaceb1`

**3. [Rule 1 - Bug] Three more `lv-icp-v0.1` literal assertions surfaced only by the
full-suite run**
- **Found during:** first full-suite run after the GREEN commit's core changes
- **Issue:** `tests/test_loss_reason_report.py` and `tests/test_scaffold.py` both pinned
  `"lv-icp-v0.1"` against the real `config/icp_scoring.yaml`'s version, now bumped to
  `lv-icp-v0.2`. Neither file is in the plan's `files_modified` list or mentions the
  geography rename at all — these are pure version-literal drift, not part of Pitfall 3.
- **Fix:** Updated both literals to `lv-icp-v0.2`. (Left several `"lv-icp-v0.1"` literals
  in `tests/test_scoring_parity.py` and `tests/test_scaffold.py` untouched — confirmed by
  reading each site that they are self-consistent synthetic fixture values unrelated to
  `CFG["version"]`, not assertions against the real config.)
- **Files modified:** `tests/test_loss_reason_report.py`, `tests/test_scaffold.py`
- **Verification:** full `pytest` suite green
- **Committed in:** `89aaceb1`

**4. [Rule 4-adjacent, resolved by advisor consultation] `tests/test_hubspot_schema_coverage.py`
went RED and stays RED — deliberately, not auto-fixed**
- **Found during:** first full-suite run after the GREEN commit's core changes
- **Issue:** `Decide Company Action` now references `lv_icp_scoring_version`, which the
  live HubSpot portal does not yet hold — no snapshot or migration-undo-manifest
  evidence of its existence. `tests/test_hubspot_schema_coverage.py`'s
  `test_every_property_a_cloud_workflow_references_exists_in_the_portal` correctly
  refuses this as BUG-14's shape (a property reference that would 400 live with
  `PROPERTY_DOESNT_EXIST` on the first execution that reaches the write).
- **Considered and rejected:** weakening/allowlisting the guard (defeats its purpose for
  every future real BUG-14-shaped defect); fabricating an undo-manifest entry (would
  assert a live creation that never happened); pulling Plan 05's live
  `sync_hubspot_properties.py` run forward into this plan (this plan's own `<files>`
  scope has no yaml declaration for the property yet — that is Plan 02's job per the
  phase's artifact table — and an armed live HubSpot write from a subagent needs the
  permission classifier's `human-action` checkpoint, which would halt the `--chain` run
  the operator has ruled should keep moving).
- **Resolution:** left the guard untouched and RED. This is the exact declare-now/
  create-later shape PROJECT.md's Phase 72 D-72-23 decision already named and accepted
  once before in this repo ("The BUG-14 schema-coverage guard correctly refuses JSON that
  references a property the portal does not hold; declare-now/create-later was novel and
  broke plan 06"). Recorded in `.planning/WINDOWS.md` (kind `unmet-truth`, phase 75,
  closes when Plan 05 runs `sync_hubspot_properties.py` live and produces the
  undo-manifest entry this guard reads).
- **Committed in:** `89aaceb1` (the reference itself); the WINDOWS.md entry is part of
  the same commit's staged files.

---

**Total deviations:** 4 auto-fixed groups (3 Rule 1 bug-fix groups covering 14 files
total, plus 1 documented-and-left-red deviation covering the schema-coverage guard).
**Impact on plan:** all four were necessary consequences of the yaml key rename and the
US whitelist addition that the plan's own file-list scope did not fully anticipate; none
represents scope creep beyond making the plan's stated goal actually true end-to-end. No
frozen fixture or stress-test file was touched.

## Plan-text discrepancy (documented, not silently resolved)

Task 1's `<action>` explicitly instructs: "Leave all three comments verbatim... Every
negative grep in this plan filters comment lines for exactly this reason." Task 2's own
first `<verify>` command greps `"Non-ANZ geography"` across `tests/ src/ scripts/ n8n/`
with **no comment filter at all** — it would fail against Task 1's own protected
comments. I followed Task 1's explicit, reasoned instruction (leave the three
HISTORICAL INCIDENT comments in `scripts/build_cloud_workflows.py` verbatim) and ran my
own verification with those comment lines excluded, extending the same treatment to five
more pre-existing historical narrative comments elsewhere that document the same
2026-08-07/2026-08-10 incidents accurately:
`tests/test_hubspot_properties_config.py:275`,
`tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs:4,93`,
`tests/test_scoring_parity.py:211`, `scripts/fix_sfv_region.py:10`.

Ran both greps for the record:
```
$ /usr/bin/grep -rn "non_anz" tests/ src/ scripts/ n8n/code/ | grep -v frozen | grep -v stress-tests | grep -v __pycache__
scripts/build_cloud_workflows.py:7050,7060  # inside the 3 protected historical comments

$ /usr/bin/grep -rn "Non-ANZ geography" tests/ src/ scripts/ n8n/ --include=*.py --include=*.mjs --include=*.js | grep -v frozen | grep -v stress-tests
8 lines, all comment-only, all in the historical-comment exemption list above
```
Every functional/assertion site is fixed; zero non-historical-comment occurrence remains.

## Issues Encountered

None beyond the deviations documented above — all were resolved within this plan's
scope (or, for the schema-coverage guard, deliberately left as a recorded, closable
cross-plan dependency).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can now read `config/icp_scoring.yaml`'s `regions.home`/`regions.aliases` for
  `src/icp_scoring.py::regions_home()`/`::region_aliases()` and the yaml-vs-JS parity
  test — the shape is already in place from this plan.
- **Recommend, not required:** consider moving the `lv_icp_scoring_version` live property
  CREATE from Plan 05 to Plan 02 (alongside its yaml/`config/hubspot_properties.yaml`
  declaration) — the D-72-23 lesson is specifically "create in the plan that first
  references," and this plan's reference already exists three plans ahead of the
  create. Not changed here; flagging for the phase orchestrator's judgment.
- `tests/test_hubspot_schema_coverage.py`'s one red test is a known, tracked blocker for
  **deploy** (not for continuing to plan/execute offline) — resolves when Plan 05 runs
  `sync_hubspot_properties.py` live. Tracked in `.planning/WINDOWS.md`.

---
*Phase: 75-config-driven-region-whitelist-and-scoring-version-staleness*
*Plan: 01*
*Completed: 2026-09-20*

## Self-Check: PASSED

- `scripts/gen_icp_scoring_js.py` — FOUND
- `n8n/code/icpScoring.generated.js` — FOUND
- `tests/test_icp_scoring_generated_currency.py` — FOUND
- `config/icp_scoring.yaml` — FOUND
- Commit `9eaadac0` (test, RED) — FOUND in `git log`
- Commit `89aaceb1` (feat, GREEN) — FOUND in `git log`
- Commit `1bde6672` (test, currency guard) — FOUND in `git log`
- Full `pytest` suite: 5176 passed / 160 skipped / 1 known-red (documented deviation)
- `node --test tests/n8n/*.test.mjs`: 1321 passed / 0 failed
- `git status --porcelain tests/n8n/fixtures/frozen/ tests/stress-tests/`: empty
