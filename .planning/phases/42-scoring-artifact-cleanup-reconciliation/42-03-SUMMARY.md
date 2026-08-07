---
phase: 42-scoring-artifact-cleanup-reconciliation
plan: 03
subsystem: infra
tags: [hubspot, crm-schema, orphan-detection, archival, drift-detection]

requires:
  - phase: 42-01
    provides: phase42-pre snapshot + drift-report-phase42-pre.json (snapshot-first requirement, satisfied) and the live-proven do-not-archive checker
  - phase: 42-02
    provides: config/hubspot_properties.yaml expanded to a full 32-property D-04 mirror, and drift-report-phase42-reconciled.json (exit_code 0, do_not_archive.ok true) as the go/no-go signal for this plan's mutation
provides:
  - scripts/derive_orphan_candidates.py, a read-only-by-default fail-safe orphan classifier + gated archival helper (imports do-not-archive constants from check_schema_drift.py, never restates them)
  - orphan-candidates-phase42.json, the committed live derivation, zero uncontested_orphan, zero ambiguous
  - drift-report-phase42-post.json + portal-schema-{companies,contacts}-phase42-post.json, proving the do-not-archive invariant survived the phase
affects: [any future phase touching HubSpot company property archival or automation flow lifecycle]

actuals:
  tokens: 21000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns: ["fail-safe classifier with an explicit ambiguous default and a coded uncontested-orphan definition, never an executor judgement call", "independent second gate re-checked immediately before a mutation, distinct from the classification gate"]

key-files:
  created:
    - scripts/derive_orphan_candidates.py
    - tests/test_orphan_candidates.py
    - .planning/phases/42-scoring-artifact-cleanup-reconciliation/orphan-candidates-phase42.json
    - config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json
    - config/hubspot_migration/baseline/portal-schema-contacts-phase42-post.json
    - .planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-post.json

key-decisions:
  - "classify_candidate/classify_flow evaluate protected before referenced before uncontested_orphan before ambiguous (the ordering IS the safety property); archive_property raises immediately for anything not classified uncontested_orphan and re-checks the do-not-archive set + live calculationFormula substring set again immediately before the DELETE, independent of the classification gate."
  - "hubspotDefined properties are filtered out of build_candidate_report entirely (never become candidates), rather than classify_candidate taking a fifth hubspotDefined argument -- keeps the 4-arg pure-function signature the plan's acceptance criteria call directly."
  - "DISPOSABLE_PROVENANCE_PATTERNS has exactly 3 entries, each tied to a concrete repo precedent: the double-underscored phase-probe form (scripts/probe_org_type_migration.py PROBE_PROPERTY_NAME), a bare trailing _probe suffix (the same convention's general form), and the ZZ-SCORING-TEST-DELETE-ME- disposable test-record prefix (scripts/probe_scoring_recalc_latency.py)."
  - "Live derivation found zero uncontested_orphan and zero ambiguous candidates -- skipped straight to Task 3 per the plan's explicit zero-candidate branch, without attempting the archival command at all. Confirmed by direct inspection: the live portal carries exactly 32 non-hubspotDefined company properties, and all 32 are already declared in 42-02's full-mirror yaml -- there is nothing left undeclared to classify as anything other than protected."
  - "config/hubspot_flows/archive-2026-08-07/ was never created -- nothing was archived, so D-09's dated archive directory has no contents to hold. Documented here rather than left silently absent."

requirements-completed: [CLEAN-01]

coverage:
  - id: D1
    description: "Orphan candidacy derived from a live portal enumeration cross-referenced against executable repo surfaces (D-02), with per-item evidence (executable_refs/test_refs/protected_by) in a committed report"
    requirement: CLEAN-01
    verification:
      - kind: unit
        ref: "tests/test_orphan_candidates.py -- 23/23 pass"
        status: pass
      - kind: other
        ref: "live derive_orphan_candidates.py run against portal 22617666, orphan-candidates-phase42.json committed"
        status: pass
    human_judgment: false
  - id: D2
    description: "The detector fails safe -- do-not-archive names classify protected against an empty reference set, a name matched only in a calculationFormula classifies protected, and a zero-reference name with no disposable-provenance match classifies ambiguous, never uncontested_orphan"
    requirement: CLEAN-01
    verification:
      - kind: unit
        ref: "tests/test_orphan_candidates.py::test_do_not_archive_properties_classify_protected_even_with_empty_refs, ::test_formula_substring_classifies_protected, ::test_zero_refs_no_disposable_match_is_ambiguous_not_orphan, ::test_archive_property_refuses_protected/referenced/ambiguous"
        status: pass
    human_judgment: false
  - id: D3
    description: "Zero orphans found live is recorded as a satisfying result, not a failure; the do-not-archive invariant is proven intact after the phase via a fresh snapshot and a green drift run"
    requirement: CLEAN-01
    verification:
      - kind: other
        ref: "orphan-candidates-phase42.json summary: {'protected': 38, 'out_of_scope': 4}, 0 uncontested_orphan, 0 ambiguous"
        status: pass
      - kind: other
        ref: "drift-report-phase42-post.json exit_code=0, do_not_archive.ok=true, all 6 flows enabled; test_flow_rubric_conformance.py + test_scoring_parity.py green; git status --porcelain n8n/ empty"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-08-08
status: complete
---

# Phase 42 Plan 03: Scoring Artifact Cleanup & Reconciliation -- Archival Derivation & Post-Mutation Proof Summary

**Built a fail-safe live orphan-candidate derivation tool, ran it against the real portal, found zero orphans and zero ambiguous items (every live custom company property was already covered by 42-02's full-mirror manifest), archived nothing, and proved afterward that the do-not-archive invariant -- the live scoring engine itself -- survived the phase untouched.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files created:** 6

## Accomplishments

- Built `scripts/derive_orphan_candidates.py`: a read-only-by-default classifier importing `DO_NOT_ARCHIVE_COMPANY_PROPERTIES`/`DO_NOT_ARCHIVE_FLOW_IDS` from `scripts/check_schema_drift.py` (never restated), evaluating `protected` -> `referenced` -> `uncontested_orphan` -> `ambiguous` in that exact precedence order. The archival helper (`archive_property`) refuses anything not classified `uncontested_orphan` as its first statement and re-checks the do-not-archive set + live `calculationFormula` substring set again, independently, immediately before the DELETE call.
- Defined `DISPOSABLE_PROVENANCE_PATTERNS` as three explicit, commented regexes, each tied to a concrete repo precedent (Phase 21's `lv__phase21_org_type_probe` double-underscore convention, its general trailing-`_probe` form, and Phase 40's `ZZ-SCORING-TEST-DELETE-ME-` disposable test-record prefix) -- this tuple IS the coded definition of D-03's "uncontested," never an executor's on-the-spot judgement.
- `tests/test_orphan_candidates.py`: 23 pure, offline, network-free tests, including the F4 regression guard (all 11 do-not-archive names classify protected against an *empty* reference set), the formula-substring protection test, three archival-refusal tests, sticky-note stripping, and `.planning`/markdown exclusion from every scanned surface.
- Ran the live derivation against portal 22617666. Result: **32 non-hubspotDefined company properties, all 32 classify `protected`** (11 in the do-not-archive set, the rest already declared in 42-02's expanded yaml manifest); **10 live automation flows, 6 classify `protected`** (the do-not-archive scoring flows) and **4 classify `out_of_scope`** (deal-pipeline and contact automations, `objectTypeId` 0-1/0-3 -- CLEAN-01 is company-scoring scoped). **Zero `uncontested_orphan`, zero `ambiguous`.**
- Directly verified the zero-orphan result is not an artifact of a narrow query: a fresh live GET of every company property confirmed the portal carries exactly 32 non-hubspotDefined properties, and all 32 are already present in `config/hubspot_properties.yaml` -- there is genuinely nothing left in the portal that this repo's manifest does not already know about.
- Skipped the archival command entirely, per the plan's explicit zero-candidate branch: "the archival half of CLEAN-01 is satisfied by a clean live diff finding nothing to archive... this is the outcome the repo's own evidence predicts."
- Captured `phase42-post` snapshot pair and ran `check_schema_drift.py` post-mutation (post-no-op, since nothing was mutated): `exit_code=0`, `do_not_archive.ok=true`, all six scoring flows still enabled, 49 `in_sync`/5 `documented_gap` -- identical shape to 42-02's reconciled report, confirming this plan changed nothing about the schema's drift state.

## Task Commits

1. **Task 1: Fail-safe orphan derivation tool and offline safety tests** - `9ded97d` (feat)
2. **Task 2: Live derivation, committed with zero orphans/zero ambiguous** - `155c9a7` (docs)
3. **Task 3: Post-mutation snapshot and invariant re-check** - `f444701` (docs)

## Files Created

- `scripts/derive_orphan_candidates.py` -- the classifier/archival tool
- `tests/test_orphan_candidates.py` -- 23 offline tests
- `.planning/phases/42-scoring-artifact-cleanup-reconciliation/orphan-candidates-phase42.json` -- live derivation, committed
- `config/hubspot_migration/baseline/portal-schema-companies-phase42-post.json`
- `config/hubspot_migration/baseline/portal-schema-contacts-phase42-post.json`
- `.planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-post.json`

`config/hubspot_flows/archive-2026-08-07/` was **not created** -- there was nothing to archive.

## Live Command Output (verbatim)

**Derivation:**
```
wrote .planning/phases/42-scoring-artifact-cleanup-reconciliation/orphan-candidates-phase42.json
classification counts: {'protected': 38, 'out_of_scope': 4}
```

**Post-mutation drift check:**
```
wrote .planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-post.json
summary: {'in_sync': 49, 'documented_gap': 5} | do_not_archive.ok=True | exit_code=0
```

## Decisions Made

- Did not attempt the archival command (`--archive`) at all, since the derivation report showed zero `uncontested_orphan` items -- there was nothing for the two-key gate to act on. This is a valid, fully-satisfying CLEAN-01 outcome per the plan's own framing, not an unfinished task.
- No ambiguous items were surfaced to the operator either, since there were none -- D-03's "ask on doubt" branch never fires when doubt does not exist.
- `hubspotDefined` properties are filtered out of the report entirely in `build_candidate_report`, rather than adding a fifth parameter to `classify_candidate` -- keeps the pure function's signature exactly matching the plan's four-argument acceptance-criteria call shape while still honoring the "never touch a native property" protective intent.

## Deviations from Plan

None -- plan executed exactly as written, including its explicit "zero orphans is success, do not go looking for something to archive" guidance. The one branch (Task 2's ambiguous-items operator checkpoint) that would have required stopping never triggered, because the report contained no ambiguous items.

## Issues Encountered

None.

## CLEAN-01 Closing Evidence

- **Snapshot-first (SC1):** `config/hubspot_migration/baseline/portal-schema-{companies,contacts}-phase42-pre.json` (42-01, commit `b03ddc9`) ran before any mutation in this phase.
- **Archive, never delete (D-07/D-08):** No property or flow was archived this plan -- the live diff found zero orphans. Had any existed, `archive_property` writes the full live definition to `config/hubspot_flows/archive-2026-08-07/` before the DELETE; that path is offline-tested (`tests/test_orphan_candidates.py`) but was never exercised live, since there was nothing to exercise it on.
- **Manifest reconciles clean (D-04/D-06):** `config/hubspot_properties.yaml` (42-02) is a full 32-property mirror; `drift-report-phase42-post.json` (this plan) confirms `exit_code=0` with only the 5 documented design-only gaps and the accepted `PARITY-01-tier-label` divergence remaining.
- **Engine intact (F1):** `drift-report-phase42-post.json`'s `do_not_archive.ok=true`, all 11 company properties present, all 6 scoring flows enabled. `tests/test_flow_rubric_conformance.py` + `tests/test_scoring_parity.py` green (66 passed, 113 skipped -- skips are the live-gated tier, expected offline).

## User Setup Required

None -- all live commands (derivation, snapshot, drift check) were run directly in-session via `dotenv`-loaded operator-shaped invocations, per this session's credential-access instructions (`.env` never read directly).

## Next Phase Readiness

- Phase 42 is now fully closed: 42-01 (snapshot + drift checker), 42-02 (manifest reconciliation), 42-03 (archival derivation -- zero orphans, engine proven intact after).
- `git status --porcelain n8n/` confirmed empty throughout this plan -- Phase 41's live arm window was never touched by any command in this plan.
- No blockers for any downstream phase.

---
*Phase: 42-scoring-artifact-cleanup-reconciliation*
*Completed: 2026-08-08*

## Self-Check: PASSED
