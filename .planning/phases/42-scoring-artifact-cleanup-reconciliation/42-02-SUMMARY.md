---
phase: 42-scoring-artifact-cleanup-reconciliation
plan: 02
subsystem: infra
tags: [hubspot, crm-schema, yaml, pytest, drift-detection]

requires:
  - phase: 42-01
    provides: committed live portal snapshot (portal-schema-companies-phase42-pre.json) and drift-report-phase42-pre.json naming exactly which company properties are missing_from_yaml vs documented_gap
provides:
  - config/hubspot_properties.yaml expanded to a full D-04 mirror (32 company properties, was 22; contacts unchanged at 17)
  - tests/test_hubspot_properties_config.py's four create-only-era guards amended to accept a full-mirror manifest without weakening their original protections
  - drift-report-phase42-reconciled.json: live proof the expansion reconciles clean (exit_code 0) and cannot cause a portal write (sync dry-run: 0 creates, 0 group creates)
affects: [42-03-archival, any future phase touching config/hubspot_properties.yaml or scripts/sync_hubspot_properties.py]

actuals:
  tokens: 3160
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns: ["config-file expansion sourced exclusively from a committed live API snapshot, never from design docs", "offline guard amendment with in-file supersession comment instead of silent test relaxation"]

key-files:
  created:
    - .planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-reconciled.json
  modified:
    - config/hubspot_properties.yaml
    - tests/test_hubspot_properties_config.py

key-decisions:
  - "Sourced all 10 new yaml entries exclusively from config/hubspot_migration/baseline/portal-schema-companies-phase42-pre.json (plan-01's committed snapshot) and drift-report-phase42-pre.json's missing_from_yaml list -- never from CLAUDE.md's design list."
  - "The five CLAUDE.md-only names (lv_icp_confidence, lv_recommended_motion, lv_icp_scored_at, lv_icp_scoring_version, lv_named_account_priority) were NOT added -- confirmed absent from both the pre-snapshot and this task's own live re-run; both drift reports classify them documented_gap."
  - "groupName for all 10 new entries is the live native `companyinformation` group, copied verbatim; the yaml's own groups: list stays at exactly one entry (lv_enrichment) so compute_group_diff never proposes creating a native group."
  - "lv_icp_fit_score's yaml entry carries only the six existing manifest keys (name/label/type/fieldType/groupName/options) -- no calculated/calculationFormula key was introduced, matching the plan's explicit scope limit."
  - "Guard 5 (test_lv_org_type_and_lv_produces_content_not_listed_for_creation) was renamed to test_..._are_declared_with_live_matching_shape rather than kept under its old name, since the old name literally asserted the opposite of what it now checks; the docstring documents the D-04 supersession."

requirements-completed: [CLEAN-01]

coverage:
  - id: D1
    description: "config/hubspot_properties.yaml expanded from a 22-property create-only company manifest to a 32-property full mirror, with every new entry's type/fieldType/groupName/options sourced verbatim from the committed live snapshot"
    requirement: CLEAN-01
    verification:
      - kind: unit
        ref: "tests/test_hubspot_properties_config.py -- 15/15 pass, including presence-plus-shape assertions for lv_org_type/lv_produces_content"
        status: pass
      - kind: other
        ref: "Task 1 inline verify script (yaml-vs-snapshot parsed equality assertion, run at commit time)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The four offline guards whose create-only premises D-04 inverts are amended in place (not deleted), each keeping its original protective intent stated in a comment"
    requirement: CLEAN-01
    verification:
      - kind: unit
        ref: "tests/test_hubspot_properties_config.py::test_every_property_name_is_lv_prefixed, ::test_every_type_fieldtype_pair_is_valid, ::test_every_groupname_is_a_declared_group, ::test_exact_counts_guard_against_manifest_drift -- all pass"
        status: pass
    human_judgment: false
  - id: D3
    description: "The expanded manifest reconciles clean against the live portal (drift-report-phase42-reconciled.json, exit_code 0, do_not_archive.ok true) and the expansion is proven incapable of causing a portal write (sync_hubspot_properties.py dry-run: 0 property creates, 0 group creates, both object types)"
    requirement: CLEAN-01
    verification:
      - kind: other
        ref: "live check_schema_drift.py run against portal 22617666, captured verbatim below"
        status: pass
      - kind: other
        ref: "live sync_hubspot_properties.py dry-run against portal 22617666, captured verbatim below"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-07
status: complete
---

# Phase 42 Plan 02: Reconciliation -- Manifest Expansion & Live Proof Summary

**Expanded `config/hubspot_properties.yaml` from a 22-property create-only company manifest to a 32-property full mirror of the live D-04 scope, amended the four offline guards whose create-only premises that inversion broke, and proved live that the expansion both reconciles clean and cannot cause a portal write.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 3
- **Files modified:** 3 (1 yaml, 1 test file, 1 new committed drift report)

## Accomplishments

- Added 10 company properties to the yaml -- `lv_org_type`, `lv_produces_content`, `lv_anti_icp_flag`, `lv_icp_tier`, the calculated `lv_icp_fit_score`, and the five `*_score` component mappers (`org_type_score`, `geography_score`, `annual_revenue_score`, `produces_content_score`, `gambling_score`) -- every field value (type, fieldType, groupName, options) copied verbatim from the committed live snapshot, never guessed or carried from CLAUDE.md's superseded design.
- Confirmed, via a fresh live re-run of `scripts/check_schema_drift.py` in this plan's own Task 3 (not just plan-01's pre-snapshot), that the five design-only names (`lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`, `lv_named_account_priority`) remain absent from the portal. No yaml entry was written for any of them.
- Amended all four broken offline guards (`test_every_property_name_is_lv_prefixed`, `test_every_type_fieldtype_pair_is_valid`, `test_every_groupname_is_a_declared_group`, `test_exact_counts_guard_against_manifest_drift`) plus the fifth test whose absence-assertion premise D-04 directly overturns -- each with an in-file comment naming what the guard was protecting and why the amended form still protects it. Test count in the file held at 15; all pass.
- Live-proved the expansion reconciles clean: `drift-report-phase42-reconciled.json` shows `exit_code: 0`, `do_not_archive.ok: true`, 49 `in_sync`, 5 `documented_gap`, zero `missing_from_yaml`/`fabricated_entry`/`enum_mismatch`/`type_mismatch`.
- Live-proved the expansion cannot cause a portal write: `sync_hubspot_properties.py`'s default dry-run against the expanded manifest reports `Properties to create (0): []` and `Groups to create: []` for both `companies` and `contacts`.

## Task Commits

1. **Task 1: Expand the manifest to a full mirror, sourced only from the committed live snapshot** - `1514449` (feat)
2. **Task 2: Update the four offline guards whose premises D-04 inverts, preserving each guard's intent** - `2917658` (test)
3. **Task 3: Prove the expansion reconciles live and cannot cause a portal write** - `67fcafa` (docs)

_No separate plan-metadata commit was requested by the orchestrator's `commit_docs` config for this run; the reconciled drift report commit (Task 3) doubles as this plan's closing evidence commit._

## Files Created/Modified

- `config/hubspot_properties.yaml` - companies `properties` grew from 22 to 32 entries; `companies.groups` list unchanged (still just `lv_enrichment`)
- `tests/test_hubspot_properties_config.py` - four guards amended in place (`_PN1_EXEMPT_NAMES` extended, `VALID_TYPE_FIELDTYPE_PAIRS` extended, a new `_NATIVE_GROUPS_ACCEPTED_WITHOUT_DECLARATION` frozenset introduced, count guard bumped 22->32); fifth test renamed `test_lv_org_type_and_lv_produces_content_not_listed_for_creation` -> `test_..._are_declared_with_live_matching_shape` with its body replaced
- `.planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-reconciled.json` - new, committed, live-generated

## Live Command Output (verbatim)

**Reconciled drift check:**
```
wrote .planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-reconciled.json
summary: {'in_sync': 49, 'documented_gap': 5} | do_not_archive.ok=True | exit_code=0
```

**Sync dry-run:**
```
DRY RUN (default) -- no writes will be made. Set DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true to create.

=== companies ===
Groups to create: []
Properties to create (0): []

=== contacts ===
Groups to create: []
Properties to create (0): []
```

## Documented Gaps (live evidence)

All five recorded in both `drift-report-phase42-pre.json` (plan 01) and `drift-report-phase42-reconciled.json` (this plan's own live re-run) as `documented_gap` -- `live: null`, never fabricated into the yaml:

| Name | Detail |
|------|--------|
| `lv_icp_confidence` | design-only name (superseded local-MVP design, CLAUDE.md), never implemented live |
| `lv_recommended_motion` | design-only name (superseded local-MVP design, CLAUDE.md), never implemented live |
| `lv_icp_scored_at` | design-only name (superseded local-MVP design, CLAUDE.md), never implemented live -- matches the standalone live-404 evidence already documented in `HANDOVER-2026-08-06-icp-scoring.md` |
| `lv_icp_scoring_version` | design-only name (superseded local-MVP design, CLAUDE.md), never implemented live |
| `lv_named_account_priority` | design-only name (superseded local-MVP design, CLAUDE.md), never implemented live |

## Decisions Made

- Sourced every new yaml entry exclusively from the committed live snapshot and the plan-01 drift report's `missing_from_yaml` list -- never from CLAUDE.md.
- Kept `lv_icp_fit_score`'s yaml entry to the existing six-key shape (no `calculated`/`calculationFormula`/`hubspotDefined`/`description` keys), per the plan's explicit scope limit; formula fidelity is independently pinned by `tests/test_flow_rubric_conformance.py`.
- Renamed the fifth amended test rather than keeping its old, now-inaccurate name (`..._not_listed_for_creation`), since the plan's acceptance criteria only require the other four exact function names to survive and the old name literally asserted the opposite of the new behavior.

## Deviations from Plan

None - plan executed exactly as written. All ten new entries matched the drift report's `missing_from_yaml` classification with no pre-existing entry requiring correction (the pre-snapshot's 22 pre-existing entries were all already `in_sync`).

## Issues Encountered

None.

## Accepted Divergences (unchanged, carried forward)

`PARITY-01-tier-label`: live `lv_icp_tier` enum is exactly `A`/`B`/`C`/`D`/`Unscored` (five values). The yaml entry added in this plan matches that five-value live set exactly -- `Needs Review` was never added to the yaml, per D-05/D-06 and the already-accepted Phase 40 divergence.

## User Setup Required

None - the two live commands this plan needed were operator-pasted `!` commands per the plan's `user_setup` block, executed directly in this session per the execution_context's credential-access instructions (dotenv loaded inside the script invocation; `.env` itself never read directly).

## Next Phase Readiness

- `config/hubspot_properties.yaml` is now the secondary do-not-archive oracle 42-03 needs: any property declared here is by definition not an orphan.
- `git status --porcelain n8n/` confirmed empty throughout this plan -- Phase 41's live arm window was never touched.
- No blockers for 42-03 (archival).

---
*Phase: 42-scoring-artifact-cleanup-reconciliation*
*Completed: 2026-08-07*

## Self-Check: PASSED
- FOUND: config/hubspot_properties.yaml
- FOUND: tests/test_hubspot_properties_config.py
- FOUND: .planning/phases/42-scoring-artifact-cleanup-reconciliation/drift-report-phase42-reconciled.json
- FOUND commit: 1514449 (Task 1)
- FOUND commit: 2917658 (Task 2)
- FOUND commit: 67fcafa (Task 3)
