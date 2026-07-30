---
phase: 21-transport-schema-hygiene
plan: 03
subsystem: infra
tags: [hubspot, migration, taxonomy, org-type, probe]

# Dependency graph
requires:
  - phase: 21-transport-schema-hygiene
    provides: "Plans 01-02's dedupe/field-policy transport work (orthogonal; no shared files)"
provides:
  - "scripts/probe_org_type_migration.py — 9-step disposable-property probe ladder,
    now run live once against the real portal, with a recorded VERDICT block"
  - "scripts/inventory_org_type_values.py — read-only live inventory, run live once:
    712/712 companies scanned, all blank, zero out-of-vocabulary"
  - "config/hubspot_migration/org_type_inventory-20260730T071919Z.json — the committed
    pre-migration reference Plan 04's pre-flight gate reads"
  - "The verbatim operator VERDICT block this SUMMARY records — the sole legitimate
    design input for Plan 04's runbook and migration script"
affects: [21-04-org-type-enum-migration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Disposable-property probe ladder (module-constant target, no CLI override) as
      the way to settle an undocumented HubSpot API behavior before designing a
      one-way-door migration against it — same discipline this project already used
      for ZoomInfo GTM and Lusha v3."

key-files:
  created:
    - scripts/probe_org_type_migration.py
    - scripts/inventory_org_type_values.py
    - tests/test_org_type_probe_gates.py
    - config/hubspot_migration/org_type_inventory-20260730T071919Z.json
    - config/hubspot_migration/baseline/portal-schema-companies-post-probe.json
    - config/hubspot_migration/baseline/portal-schema-contacts-post-probe.json
  modified: []

key-decisions:
  - "Migration shape: IN PLACE (cheap reverse-PATCH rollback confirmed) — chosen from
    the live probe verdict, not assumption."
  - "Out-of-vocab enforcement (`out_of_vocab_write_after_conversion_rejected: yes`) is
    INVALID as evidence — steps 2/4/5 hit stale TEST_COMPANY_IDS company 789, which
    does not exist (404, not enum rejection). Plan 04's C7 smoke test is the real
    enforcement proof, not this probe."
  - "`existing_value_after_conversion` is immaterial for this migration: the live
    inventory shows all 712 companies blank on lv_org_type, so there is no existing
    value to preserve."

requirements-completed: []  # REQ-orgtype-enumeration remains open; closed by Plan 04.

coverage: []

duration: n/a (spans an operator-armed checkpoint across sessions)
completed: 2026-07-30
status: complete
---

# Phase 21 Plan 03: Org-Type Migration Probe + Live Inventory Summary

**Live probe ladder + inventory settle the org-type migration's design inputs: in-place text-to-enum conversion is allowed with a cheap reverse-PATCH rollback, and all 712 live companies are currently blank on `lv_org_type` (zero out-of-vocabulary, zero data at risk).**

## Performance

- **Tasks:** 3 (2 auto + 1 operator checkpoint)
- **Files modified:** 6 created (2 scripts, 1 test file, 1 inventory artifact, 2 post-probe snapshots)

## Accomplishments

- Built and dry-run-verified `scripts/probe_org_type_migration.py` (9-step ladder, taxonomy-derived option set, zero CLI target override) and its offline gate tests (`tests/test_org_type_probe_gates.py`).
- Built and live-ran `scripts/inventory_org_type_values.py`: 712/712 companies scanned (matches portal-reported total exactly), all blank, zero out-of-vocabulary — committed as `config/hubspot_migration/org_type_inventory-20260730T071919Z.json`.
- Operator ran the armed 9-step probe ladder live against the real portal (Task 3) and pasted back the verdict below, plus confirmed residue-free cleanup via an independent `snapshot_hubspot_schema.py --label post-probe` (both companies and contacts snapshots show zero occurrences of the probe property name; `lv_org_type` itself is unchanged: `string`/`text`/empty options).

## Task Commits

1. **Task 1: Disposable-property probe ladder** - `926a57e` (feat)
2. **Task 2: Read-only live inventory** - `6ff09ba` (feat)
3. **Task 3: Operator armed-run checkpoint** - recorded in this SUMMARY (no code commit; see verdict below)

**Plan metadata:** this SUMMARY (docs: close plan 03 with the operator's verdict)

## Verbatim Operator VERDICT Block (2026-07-30)

```
=== VERDICT ===
in_place_type_patch_allowed: yes
existing_value_after_conversion: record now errors (404 Client Error: Not Found for url: https://api.hubapi.com/crm/v3/objects/companies/789?properties=lv__phase21_org_type_probe)
out_of_vocab_write_after_conversion_rejected: yes
reverse_patch_allowed: yes
emptying_lifts_block: not-yet-observed
name_immediately_reusable: yes
recommended_migration_shape: in place (cheap reverse-PATCH rollback confirmed)

=== RESIDUAL STATE ===
Clean — nothing left behind in the portal.
```

**Chosen migration shape (verbatim from the recommendation line above): `in place (cheap reverse-PATCH rollback confirmed)`.**

### Caveats qualifying the verdict above (recorded here, load-bearing for Plan 04)

1. Steps 2/4/5 hit company id `789`, which **does not exist** in the portal (stale
   `TEST_COMPANY_IDS` in `.env` at probe time; the real standing test company is
   `9604614548`, Melbourne Racing Club). Consequences:
   - `out_of_vocab_write_after_conversion_rejected: yes` is **INVALID** as evidence — that
     404 was "resource not found" (missing company record), NOT enum enforcement. Enum
     enforcement remains **UNPROVEN** until Plan 04 Task 4 / Operator Runbook Section C7's
     smoke test against the real migrated `lv_org_type` property. Plan 04's runbook and
     migration script must treat C7 as the enforcement proof, never this probe's line 3.
   - `existing_value_after_conversion` is unanswered by this probe run, but is
     **immaterial** to this migration: the live inventory (Task 2, same day) shows all 712
     companies blank on `lv_org_type` — zero existing values at risk.
2. **Valid property-level verdicts** (real 200/201/204 HTTP responses, no record
   involved): in-place PATCH text→enum **ALLOWED**; reverse PATCH enum→text **ALLOWED**
   (cheap rollback); archived name **immediately reusable**. Migration shape: **IN PLACE**.
3. `emptying_lifts_block` is unobserved (step 7 was skipped because step 3 succeeded) —
   irrelevant to the in-place shape actually chosen.

## Files Created/Modified

- `scripts/probe_org_type_migration.py` - 9-step disposable-property probe ladder (dry-run default, operator-armed)
- `scripts/inventory_org_type_values.py` - read-only paged live inventory, taxonomy-classified
- `tests/test_org_type_probe_gates.py` - offline refusal-path coverage for the probe
- `config/hubspot_migration/org_type_inventory-20260730T071919Z.json` - committed pre-migration reference (712/712 scanned, all blank, 0 out-of-vocab)
- `config/hubspot_migration/baseline/portal-schema-companies-post-probe.json` - independent residue-check snapshot (probe property absent; `lv_org_type` unchanged)
- `config/hubspot_migration/baseline/portal-schema-contacts-post-probe.json` - same, contacts side

## Decisions Made

- Migration shape for Plan 04: **in place**, per the operator's verbatim recommendation line.
- The 404-on-missing-company defect in the probe's steps 2/4/5 does not need a probe re-run: the two facts it would have proven (existing-value handling, enum rejection) are covered by other evidence — the inventory (no existing values) and Plan 04 Task 4's C7 smoke test (the real enforcement proof) respectively. Re-running the probe against a correct test company was assessed as lower value than proceeding straight to Plan 04 with these caveats recorded.

## Deviations from Plan

None - Tasks 1 and 2 executed exactly as written and were already committed prior to this SUMMARY. This SUMMARY closes Task 3 (the operator checkpoint) after the fact, since the operator ran the armed ladder and pasted the verdict directly into the next plan's execution context rather than into a resumed agent turn for this plan. No code changes were required to record it.

## Issues Encountered

- `TEST_COMPANY_IDS` in `.env` was stale (`789`, a non-existent company) at the time the operator armed the probe, which invalidated two of the ladder's record-level observations (see caveats above). `.env`'s `TEST_COMPANY_IDS` should be corrected to `9604614548` before any further armed record-level probes or smoke tests run (Plan 04 Task 4 / Operator Runbook Section C7 depends on this).

## Next Phase Readiness

Plan 04 is unblocked: the verbatim VERDICT block above is the sole legitimate design input for `docs/ORG-TYPE-ENUM-MIGRATION.md` and `scripts/migrate_org_type_enum.py`, and the committed inventory artifact is current (same-day) and clean (0 out-of-vocabulary).

---
*Phase: 21-transport-schema-hygiene*
*Completed: 2026-07-30*
