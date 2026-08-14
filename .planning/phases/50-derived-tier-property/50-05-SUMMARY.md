---
phase: 50-derived-tier-property
plan: 05
subsystem: crm-schema
tags: [hubspot, automation-flows, calculated-properties, schema-drift]

requires:
  - phase: 50-derived-tier-property
    provides: "lv_icp_tier_derived calculated property, proven live parity against lv_icp_tier (50-04)"
provides:
  - "WF1 (4625147345) switched off, definition kept, verified by independent re-read"
  - "scripts/check_schema_drift.py RETIRED_FLOW_IDS structure with a live-AND-disabled invariant, distinct from the live-AND-enabled invariant for still-active flows"
  - "scripts/rollback_property_migration.py --archive-property mode (dry-run and live-armed, built and proven against a real 400 rejection)"
  - "scripts/apply_fit_score_formula.py --label mode (dry-run verified, not yet armed live)"
  - "50-RETIREMENT-RECORD.md documenting a new platform constraint: HubSpot refuses to archive a property still referenced by any workflow action, even a disabled one"
affects: [any future phase that resumes retirement of lv_icp_tier, any phase touching WF1's action definitions]

actuals:
  tokens: 6000
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Two-tier do-not-archive invariant in check_schema_drift.py: live-AND-enabled for active flows, live-AND-disabled for retired-but-kept flows (RETIRED_FLOW_IDS)"
    - "Every archive/disable verified by an independent re-read, never the mutating call's own response body"

key-files:
  created:
    - .planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md
  modified:
    - scripts/check_schema_drift.py
    - tests/test_check_schema_drift.py
    - scripts/rollback_property_migration.py
    - scripts/apply_fit_score_formula.py
    - config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json

key-decisions:
  - "Executed WF1 shutdown (D-08) live and verified — fully reversible, fully complete."
  - "Discovered mid-execution that HubSpot's DELETE /crm/v3/properties refuses to archive a property still referenced by ANY workflow action, disabled or not (HTTP 400, PropertyValidationError.CANNOT_DELETE_PROPERTY_IN_USE) — not anticipated by 50-RESEARCH.md or the D-06 null-probe research."
  - "Did not delete or edit WF1's actions to unblock the archive: both would violate this plan's explicit prohibition ('WF1 4625147345 is not deleted') or forfeit the proven one-action rollback mechanism. Escalated per D-11 instead of forcing the archive through."
  - "Deferred the relabel of lv_icp_tier_derived to 'ICP Tier' even though independently authorised: with lv_icp_tier still live, relabelling would create two live properties both displaying 'ICP Tier', a new confusion outside what the operator signed up for."
  - "Reverted an in-progress config/hubspot_properties.yaml edit that had prematurely removed the lv_icp_tier declaration and relabelled the derived property ahead of the live archive succeeding — the yaml now matches live truth exactly (both properties present, derived property's label unchanged)."
  - "Committed all completed, correct work (guard edits, offline tests, both new CLI tool modes, refreshed WF1 snapshot, retirement record) in ONE commit rather than holding it pending the blocked archive — the guard edits are what make check_schema_drift.py report the WF1 shutdown as correct rather than as engine damage, and they are true regardless of the archive's outcome."

requirements-completed: [TIER-01]

coverage:
  - id: D1
    description: "WF1 (4625147345) switched off live, definition kept, verified by independent re-read (not the PUT's own response)"
    requirement: "TIER-01"
    verification:
      - kind: other
        ref: "GET /automation/v4/flows/4625147345 -> 200, isEnabled: False (independent re-read, recorded in 50-RETIREMENT-RECORD.md)"
        status: pass
    human_judgment: false
  - id: D2
    description: "check_schema_drift.py's RETIRED_FLOW_IDS live-AND-disabled invariant, offline-pinned"
    requirement: "TIER-01"
    verification:
      - kind: unit
        ref: "tests/test_check_schema_drift.py#test_retired_flow_live_and_disabled_is_ok"
        status: pass
      - kind: unit
        ref: "tests/test_check_schema_drift.py#test_retired_flow_absent_is_not_ok"
        status: pass
      - kind: unit
        ref: "tests/test_check_schema_drift.py#test_retired_flow_live_and_enabled_is_not_ok"
        status: pass
    human_judgment: false
  - id: D3
    description: "Archive lv_icp_tier (D-06) — NOT ACHIEVED, blocked by a newly discovered platform constraint"
    requirement: "TIER-03"
    verification: []
    human_judgment: true
    rationale: "The archive attempt returned HTTP 400 (property in use by WF1's workflow action, even disabled). Resolving this requires an operator decision among three tradeoffs documented in 50-RETIREMENT-RECORD.md (accept the interim state, edit WF1's actions and forfeit rollback, or delete WF1 outright) — none of which this plan is authorised to select on its own."

duration: 55min
completed: 2026-08-14
status: halted
---

# Phase 50 Plan 05: Retirement Attempt (WF1 Off, Archive Blocked) Summary

**WF1 (4625147345) switched off and verified live; `lv_icp_tier` archive blocked by a newly discovered HubSpot constraint (property in use by a disabled workflow's action) that this plan is not authorised to work around, so retirement stops here pending a fresh operator decision.**

## Performance

- **Duration:** 55 min (across two sessions — halted mid-Task-02 by a macOS TCC access loss,
  resumed and completed this session)
- **Started:** 2026-08-14T00:00:00Z (approx., prior session)
- **Completed:** 2026-08-14T02:10:00Z (approx.)
- **Tasks:** 1 of 2 fully executed (Task 50-05-01 decision was authorised in the prior session's
  spawn prompt; Task 50-05-02 executed partially — WF1 shutdown complete, property archive
  blocked)
- **Files modified:** 5 (plus the new retirement record and this summary)

## Accomplishments

- WF1 (`4625147345`) switched off live: `isEnabled` flipped `true` → `false` via
  `put_hubspot_flow.py --disable`, verified by an independent re-read (never the PUT's own
  response body), definition fully intact. Fully reversible per `docs/OPERATOR-TIER-ROLLBACK.md`
  step 1.
- `scripts/check_schema_drift.py` extended with a `RETIRED_FLOW_IDS` structure and a
  live-AND-disabled invariant in `_compute_do_not_archive`, distinct from the live-AND-enabled
  invariant the other five scoring flows still carry. Ran live post-mutation:
  `do_not_archive.ok=True`, `exit_code=0` — the comparator now correctly reports WF1's shutdown
  as the deliberate, correct state it is, not as engine damage.
- Discovered and documented a HubSpot platform constraint not anticipated anywhere in this
  phase's research: `DELETE /crm/v3/properties/companies/{name}` refuses to archive a property
  still referenced by any workflow action, **including a disabled workflow's action**. This
  blocked the `lv_icp_tier` archive outright (HTTP 400,
  `PropertyValidationError.CANNOT_DELETE_PROPERTY_IN_USE`).
- Two new CLI tool modes built and dry-run verified working correctly:
  `rollback_property_migration.py --archive-property NAME` (proven against a real live 400
  rejection, not just a mock) and `apply_fit_score_formula.py --label TEXT` (dry-run only, not
  armed — see Decisions).
- `tests/test_check_schema_drift.py` extended with 4 new offline tests pinning the
  `RETIRED_FLOW_IDS` invariant and updated size assertions (11/5/15).
- Full offline suite green: `.venv/bin/python -m pytest -q` (2821 passed, 154 skipped) and
  `node --test tests/n8n/*.test.mjs` (683 passed).

## Task Commits

Both the decision task (50-05-01) and this execution task (50-05-02) are represented in a single
commit, since Task 02 could not reach its own committed end state (the archive) and the
same-commit rule (guard edits must land with the mutations they accommodate) applied to the
mutation that DID succeed (WF1 shutdown):

1. **Task 50-05-02 (partial): WF1 off + guard edits + new tooling + retirement record** -
   see commit hash in the final PLAN COMPLETE block below.

**Plan metadata:** committed together with the above (single commit; see note in Deviations).

## Files Created/Modified

- `scripts/check_schema_drift.py` - `RETIRED_FLOW_IDS` structure, `_compute_do_not_archive`
  extended with the live-AND-disabled fold, `ACCEPTED_DIVERGENCES`'s `PARITY-01-tier-label`
  entry restated against `lv_icp_tier_derived`
- `tests/test_check_schema_drift.py` - 4 new tests pinning the retired-flow invariant, updated
  size assertions (11/5/15), updated `PARITY-01-tier-label` property-name assertion
- `scripts/rollback_property_migration.py` - `--archive-property NAME` mode (built, dry-run and
  live-armed; the live archive itself failed for a portal-side reason, not a tool defect)
- `scripts/apply_fit_score_formula.py` - `--label TEXT` mode (built, dry-run verified only)
- `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json` - refreshed from a live
  post-disable read-back (`isEnabled: false`)
- `.planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md` - full record of both
  mutation attempts, the blocker discovery, and the accepted-risk disclosure
- `config/hubspot_properties.yaml` - **left unchanged** from its pre-session state (an in-flight
  edit that prematurely removed `lv_icp_tier` and relabelled the derived property was reverted
  once the archive failed — the yaml stays truthful to live state)

## Decisions Made

- Executed WF1 shutdown live and verified it independently — this half of D-08 is complete and
  needed no further authorisation once `retire-and-relabel` was selected.
- On discovering the archive was blocked by a platform constraint that makes it impossible
  without either deleting WF1 (explicitly prohibited by this plan) or editing WF1's actions
  (which forfeits the proven rollback mechanism), stopped rather than forcing the archive through
  or silently improvising a workaround — this is exactly the D-11 escalation path, applied to a
  dependent (WF1's own action reference) that turned out to be un-migratable within this plan's
  authorised means.
- Deferred the relabel even though it was independently authorised and technically unblocked: with
  the old enum still live, relabelling the derived property would put two properties on the portal
  both displaying "ICP Tier" — a new confusion the operator did not sign up for when relabel was
  framed as riding alongside a successful archive.
- Reverted a premature yaml edit made before the live mutations were attempted, so
  `config/hubspot_properties.yaml` matches live truth (`lv_icp_tier` still declared and live,
  `lv_icp_tier_derived` still labelled "ICP Tier (Derived)") rather than describing a desired
  end-state that did not happen.
- Committed the guard edits, new tooling, refreshed snapshot, and retirement record as ONE commit
  now rather than holding them pending a future successful archive — they are all independently
  correct given the mutation that DID happen (WF1 off), and holding them uncommitted would leave
  `check_schema_drift.py` reporting exit code 2 ("engine damaged") for the deliberate, correct
  state WF1's shutdown actually is.

## Deviations from Plan

### Auto-fixed Issues

None — no bugs, missing functionality, or blocking issues in the Rule 1-3 sense were found in
this session's own work; the two prior-session-completed scripts
(`rollback_property_migration.py`, `apply_fit_score_formula.py`) were verified, not modified.

### Rule 4 escalation (architectural / cannot-proceed)

**1. [Rule 4 - Architectural] `lv_icp_tier` archive blocked by an undocumented HubSpot platform
constraint**
- **Found during:** Task 50-05-02, armed live mutation 2 (archive the enum)
- **Issue:** `DELETE /crm/v3/properties/companies/lv_icp_tier` returned HTTP 400
  (`PropertyValidationError.CANNOT_DELETE_PROPERTY_IN_USE`) because WF1's actions still reference
  `lv_icp_tier` as a write target, and HubSpot counts this as "in use" regardless of whether the
  workflow is enabled. Neither `50-RESEARCH.md` nor `50-NULL-PROBE.json` (which answered whether
  the DELETE is a soft archive) anticipated an in-use rejection.
- **Why not auto-fixed:** the only two paths that unblock the archive — deleting WF1 entirely, or
  editing its actions to strip the `lv_icp_tier` reference — either directly violate this plan's
  explicit prohibition ("WF1 4625147345 is not deleted") or destroy the proven one-action-rollback
  guarantee D-08 and `50-ROLLBACK-DRILL.md` are built on. Both are architectural changes to what
  this plan is authorised to touch, squarely Rule 4.
- **Resolution:** documented in full in `50-RETIREMENT-RECORD.md`, including three concrete
  options for a future decision checkpoint. Nothing was forced through; nothing was left in an
  ambiguous or partially-mutated state (the failed DELETE left `lv_icp_tier` exactly as it was
  before the attempt, confirmed by an independent re-read).
- **Files modified:** none as a "fix" — this deviation resulted in NOT making the planned change,
  documented instead.
- **Verification:** `GET /crm/v3/properties/companies/lv_icp_tier` → 200, `archived: false`
  (confirms clean, unmutated failure).

---

**Total deviations:** 1 escalated (Rule 4 — architectural, cannot proceed without a fresh
operator decision).
**Impact on plan:** The plan's fully-authorised end state (`retire-and-relabel`) was NOT reached.
WF1 shutdown (D-08) is complete and correct. Property archive (D-06) and relabel (D-15's fallback)
are both deferred pending a new decision. This is a disclosed, coherent partial state — closer in
spirit to D-06's "gate failed, stop here" outcome than to full completion, except the gate
(D-07) actually passed; it was a platform constraint discovered only at execution time that
stopped the archive, not a data-quality gate.

## Issues Encountered

- **macOS TCC access loss (prior session):** `~/Desktop` became inaccessible mid-session with
  `EPERM`, halting the prior executor with nothing committed and no HubSpot mutation run. Resolved
  by the operator re-granting Full Disk Access; this session resumed cleanly from the durable
  continuation note with all preconditions re-verified as unchanged.
- **HubSpot property-in-use rejection (this session):** see Rule 4 escalation above — the
  substantive issue this plan closes without resolving.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Not ready to close Phase 50 as fully retired.** A future plan or session must:
1. Bring `50-RETIREMENT-RECORD.md`'s three options to the operator (accept the interim state
   permanently, authorise editing WF1's tier-write actions and accept the forfeited rollback
   guarantee, or authorise deleting WF1 outright).
2. Re-attempt the archive only after one of those is explicitly selected.
3. Run the relabel (`apply_fit_score_formula.py --property lv_icp_tier_derived --label "ICP
   Tier"`, already dry-run verified) alongside whichever archive resolution is chosen, not before.

**What IS stable and safe to build on:** `lv_icp_tier_derived` remains live, proven (D-07 PASS),
and is the functional source of truth for ICP tier going forward — WF1 is off, so nothing
competes with it. `lv_icp_tier` is frozen (no writer) but still readable at its last-known value
for anything not yet migrated. `check_schema_drift.py` correctly reports this interim state as
clean (`exit_code=0`).

---
*Phase: 50-derived-tier-property*
*Completed: 2026-08-14*

## Self-Check: PASSED

- FOUND: `.planning/phases/50-derived-tier-property/50-05-SUMMARY.md`
- FOUND: `.planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md`
- FOUND: `scripts/check_schema_drift.py`
- FOUND: `tests/test_check_schema_drift.py`
- FOUND commit: `449b306`
