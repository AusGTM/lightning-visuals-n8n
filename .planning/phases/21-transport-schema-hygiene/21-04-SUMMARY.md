---
phase: 21-transport-schema-hygiene
plan: 04
subsystem: infra
tags: [hubspot, migration, taxonomy, org-type, rollback]

# Dependency graph
requires:
  - phase: 21-transport-schema-hygiene
    provides: "Plan 03's live probe verdict (in place, cheap reverse-PATCH rollback
      confirmed) and committed clean inventory (712/712 blank, 0 out-of-vocabulary) --
      the sole legitimate design input for this plan's Tasks 1-2"
provides:
  - "docs/ORG-TYPE-ENUM-MIGRATION.md -- the rollback runbook, carrying the four
    machine-read markers the migration script's arm gate demands, committed BEFORE
    the migration script exists"
  - "scripts/migrate_org_type_enum.py -- the gated, single-shape (in place) migration,
    reusing the runbook + inventory gates, portal guard, two-key write gate, typed
    confirmation, manifest and post-write read-back idiom this repo already established"
  - "tests/test_migrate_org_type_enum.py -- 23 offline cases covering every refusal path"
affects: [22-armed-e2e-enrichment-canary]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runbook-as-executable-policy: a markdown rollback document carrying greppable
      MARKER: value lines that a migration script parses and refuses to arm without --
      the doc is not merely prose, it is load-bearing gate input."
    - "Single-script bidirectional migration: --rollback on the SAME script as the
      forward migration, reusing every gate, instead of a second dedicated rollback
      tool -- appropriate specifically because the reverse direction (enum->text) is a
      permissive widening, not a constraint, so it does not need the forward
      direction's runbook/inventory gates."

key-files:
  created:
    - docs/ORG-TYPE-ENUM-MIGRATION.md
    - scripts/migrate_org_type_enum.py
    - tests/test_migrate_org_type_enum.py
  modified:
    - .planning/phases/21-transport-schema-hygiene/21-03-SUMMARY.md (created in this
      session, as a prerequisite -- see Deviations)

key-decisions:
  - "MIGRATION-SHAPE marker value (docs/ORG-TYPE-ENUM-MIGRATION.md, verbatim): \"in
    place (cheap reverse-PATCH rollback confirmed) -- verbatim `recommended_migration_shape`
    line from 21-03-SUMMARY.md's operator VERDICT block, 2026-07-30\". Plan 03 SUMMARY's
    verdict line (verbatim): \"recommended_migration_shape: in place (cheap
    reverse-PATCH rollback confirmed)\". Side by side: identical wording -- the marker
    is a direct quote, not a paraphrase."
  - "Rollback is a --rollback flag on migrate_org_type_enum.py itself, not a separate
    script: the reverse direction (enum -> text) is a permissive widening that cannot
    itself reject or orphan a value the way the forward conversion can, so it does not
    need the runbook/inventory gates -- only portal + two-key + typed confirmation."
  - "Escalation condition not triggered: the probe verdict chose in place, not a shadow
    property under a new name, so Task 2's ESCALATION CONDITION (stop and hand to the
    orchestrator) never fires."

requirements-completed: []  # REQ-orgtype-enumeration stays open until Task 4 (armed
  # operator run + independent verification) lands -- per this plan's own project
  # constraints, not ticked at build stage.

coverage:
  - id: D1
    description: "Rollback runbook committed before any migration code exists, carrying
      the four machine-read markers the migration script's arm gate demands, each with
      a real (non-placeholder) value"
    verification:
      - kind: unit
        ref: "tests/test_migrate_org_type_enum.py -k runbook (8 cases)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Migration script refuses to arm without the runbook markers and a
      clean (zero out-of-vocabulary, current-taxonomy-version) inventory artifact;
      option set is taxonomy-derived; dry run is the default in both directions and
      makes zero HTTP calls"
    verification:
      - kind: unit
        ref: "tests/test_migrate_org_type_enum.py (23 cases, full file)"
        status: pass
      - kind: integration
        ref: "manual: .venv/bin/python -c \"from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/migrate_org_type_enum.py', run_name='__main__')\" (forward) and the same with --rollback appended -- both ran against the real committed runbook + inventory artifacts, both gates passed, zero HTTP calls, full body + resolved 9-key option set printed"
        status: pass
    human_judgment: false
  - id: D3
    description: "The armed live conversion (Task 3 decision + Task 4 operator-run
      execution and independent verification)"
    verification: []
    human_judgment: true
    rationale: "Armed HubSpot schema writes are classifier-blocked for agents in this
      environment (Phase 20 Plan 04 precedent, reconfirmed here); Task 3 is a
      one-way-door reversibility decision requiring explicit human/orchestrator
      judgment; Task 4 requires an operator to run live commands against production
      HubSpot and paste back independent verification output. Neither can be automated
      or auto-passed."

duration: ~55min
completed: 2026-07-30
status: complete
---

# Phase 21 Plan 04: Org-Type Enum Migration -- Runbook + Gated Script Summary

**Rollback runbook (four machine-read markers) and a gated `lv_org_type` text-to-enumeration migration script, both built and offline-verified; the armed conversion itself remains an operator checkpoint (Tasks 3-4), unresolved by this session.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 2 of 4 (Tasks 1-2, agent-buildable; Tasks 3-4 are operator checkpoints, not run)
- **Files modified:** 4 (3 created for this plan, 1 created as a prerequisite fix -- see Deviations)

## Accomplishments

- Closed a blocking gap discovered at the start of this session: Plan 03's SUMMARY did not yet exist, even though the operator had already run Task 3's armed probe ladder and pasted its verdict directly into this session's execution context. Created `21-03-SUMMARY.md` from that verbatim verdict (with the orchestrator's caveats about the stale `TEST_COMPANY_IDS=789`), so Task 1's precondition ("Plan 03's SUMMARY contains a verbatim operator-pasted VERDICT block") is genuinely satisfied by a committed file, not just by data floating in a chat turn.
- Wrote `docs/ORG-TYPE-ENUM-MIGRATION.md`, leading with rollback: when to roll back and the point it stops being cheap, the exact copy-pasteable rollback command, how to verify a rollback worked, an honest statement of what rollback cannot restore (including the specific gap where the probe's record-value evidence was invalidated by a stale test company id), and a blast-radius section naming every code path that reads `lv_org_type`.
- Wrote `scripts/migrate_org_type_enum.py`: one migration shape (in place), reusing this repo's established gate idioms (`_has_credentials()` skip, portal guard, two-key write gate, typed confirmation, manifest, post-write read-back assertion), plus two new gates unique to this one-way door -- the runbook gate and the pre-flight inventory gate -- both refusing before any HTTP call.
- Wrote `tests/test_migrate_org_type_enum.py`: 23 offline cases, all passing, covering every refusal path plus the taxonomy-derived option set.
- Manually exercised both the forward and `--rollback` dry runs against the real committed runbook and inventory artifacts, through the exact `runpy`/`dotenv` wrapper form the operator runbook uses -- both gates passed, the full request body and resolved 9-key option set printed, zero HTTP calls made.

## Task Commits

1. **Prerequisite: close Plan 03 with the operator's verdict** - `b55fc45` (docs)
2. **Task 1: Rollback runbook** - `ecfad31` (docs)
3. **Task 2: Gated migration script + tests** - `88b2131` (feat)

**Plan metadata:** this SUMMARY (no separate metadata commit -- STATE.md/ROADMAP.md
intentionally not touched per this execution's project constraints; see below)

## Files Created/Modified

- `.planning/phases/21-transport-schema-hygiene/21-03-SUMMARY.md` - closes Plan 03 with the verbatim operator VERDICT block and its caveats (prerequisite fix, not part of Plan 04's own file list)
- `docs/ORG-TYPE-ENUM-MIGRATION.md` - the rollback runbook with four machine-read markers
- `scripts/migrate_org_type_enum.py` - gated forward/`--rollback` migration script
- `tests/test_migrate_org_type_enum.py` - 23 offline gate/refusal tests

## Decisions Made

- **MIGRATION-SHAPE marker vs Plan 03's verdict, side by side:**
  - Runbook marker: `in place (cheap reverse-PATCH rollback confirmed) -- verbatim recommended_migration_shape line from 21-03-SUMMARY.md's operator VERDICT block, 2026-07-30`
  - Plan 03 SUMMARY's verdict line (verbatim): `recommended_migration_shape: in place (cheap reverse-PATCH rollback confirmed)`
  - These match: the marker is a direct quote of the verdict, not a paraphrase.
- Rollback lives as a `--rollback` flag on the same script rather than a dedicated second tool. The reverse direction (enumeration -> text) is a permissive widening that cannot itself reject or orphan a value the way the forward conversion can, so it is exempt from the runbook and inventory gates by design -- it still requires the portal guard, the two-key write gate, and a typed confirmation.
- The plan's ESCALATION CONDITION (shadow property under a new name -> stop and escalate to the orchestrator) never fires: the probe verdict chose "in place," so only that one shape is implemented, per the plan's own instruction not to build an unexercised second branch of a one-way-door migration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created the missing `21-03-SUMMARY.md` before starting Task 1**
- **Found during:** Task 1 precondition check
- **Issue:** Task 1's precondition requires "Plan 03's SUMMARY contains a verbatim operator-pasted VERDICT block"; that file did not exist on disk (Plan 03's Task 3, the operator checkpoint, had been resolved live but its SUMMARY was never written -- the verdict had only been pasted directly into this session's execution context by the orchestrator, with additional caveats about a stale test-company id).
- **Fix:** Wrote `21-03-SUMMARY.md` from the verbatim VERDICT block and orchestrator caveats provided in this session's context, following the same summary conventions used elsewhere in this phase, and independently confirmed the residue-check claims (grepped both post-probe schema snapshots for the probe property name: zero hits; confirmed `lv_org_type` itself unchanged at `string`/`text`/`[]` in the companies snapshot) before committing it.
- **Files modified:** `.planning/phases/21-transport-schema-hygiene/21-03-SUMMARY.md`, plus committing the two already-untracked post-probe schema snapshots (`config/hubspot_migration/baseline/portal-schema-{companies,contacts}-post-probe.json`) as their residue-check evidence.
- **Verification:** Confirmed via direct grep/read of the snapshot files before writing the SUMMARY's claims; Task 1's own precondition then read cleanly against the newly committed file.
- **Committed in:** `b55fc45` (separate commit, before Task 1's own commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to unblock Task 1's stated precondition; no scope creep into Plan 04's own Tasks 1-2 design. Left an out-of-scope, unrelated untracked file alone (`config/hubspot_migration/undo-manifest-f3bf7bc5-....json`, a Phase 20/Operator-Runbook-Section-A artifact from a prior sitting, not part of this plan's file list) and unrelated pre-existing `.env.example`/`.DS_Store` modifications from before this session started.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required for Tasks 1-2. Tasks 3-4 require an
operator to run live, credentialed commands against production HubSpot; see "Next Phase
Readiness" below and the checkpoint state returned alongside this SUMMARY.

## Next Phase Readiness

Tasks 1-2 are complete and offline-verified; both suites remain green (705 pytest / 354
node). Tasks 3 (the one-way-door reversibility decision) and 4 (the operator-armed
conversion + independent verification) are unresolved by this session and are returned
as a checkpoint. Notably, `.planning/phases/22-armed-e2e-enrichment-canary/22-OPERATOR-RUNBOOK.md`
already documents a decision folding this plan's Task 3 into its own Sitting 2 (Section
C, run immediately before the Phase 22 canary in Section D): "Decision recorded (Task 2
of [22-04-PLAN.md], resolved by the orchestrator -- not re-opened here): `migrate-first`"
-- i.e., run the live conversion now, in an operator window, before the canary. This
reads as the same substantive choice as this plan's Task 3 option `proceed-now`, but it
was recorded against a different plan file (22-04, not 21-04) and has not been pasted
back into this plan's own checkpoint history. The checkpoint returned alongside this
SUMMARY surfaces that cross-reference explicitly so the orchestrator can decide whether
it satisfies Task 3 as written or whether Task 3 still needs its own explicit resolution
before Task 4 (Operator Runbook Section C) proceeds.

Also worth operator attention before Task 4 runs: `.env`'s `TEST_COMPANY_IDS` was stale
(`789`, nonexistent) during Plan 03's probe run and should be corrected to `9604614548`
(Melbourne Racing Club, the standing test company named throughout the Operator
Runbook) before any further armed record-level action, including Task 4's C7 smoke test.

## Self-Check: PASSED

All created files confirmed present on disk; all three task commits (`b55fc45`,
`ecfad31`, `88b2131`) confirmed present in `git log`.

## Task 3 Resolution (one-way door gate) — RESOLVED: proceed-now

Resolved by orchestrator 2026-07-30 (same session as the build). Decision: **proceed-now**,
executed as Operator Runbook Section C in the Sitting 2 window immediately before the
Phase 22 canary. This is the same substantive choice as 22-OPERATOR-RUNBOOK.md's recorded
"migrate-first" decision (22-04 Task 2); recorded here so this plan's own gate shows its
resolution. Basis: (a) in-place conversion + cheap reverse-PATCH rollback confirmed by the
live probe; (b) all 712 companies blank on lv_org_type — zero data at risk; (c) the canary's
criterion 2 needs the enum live to prove anything new. Task 4 remains operator-run
(Section C), with the .env TEST_COMPANY_IDS=9604614548 fix required before C7.

---
*Phase: 21-transport-schema-hygiene*
*Completed: 2026-07-30*
