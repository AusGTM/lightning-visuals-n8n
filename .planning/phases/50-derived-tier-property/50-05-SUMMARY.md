---
phase: 50-derived-tier-property
plan: 05
subsystem: crm-schema
tags: [hubspot, automation-flows, calculated-properties, schema-drift]

requires:
  - phase: 50-derived-tier-property
    provides: "lv_icp_tier_derived calculated property, proven live parity against lv_icp_tier (50-04)"
provides:
  - "WF1 (4625147345) DELETED live (D-24, overriding D-08), verified by independent re-read"
  - "lv_icp_tier ARCHIVED live (D-06), verified by independent re-read and the archived-properties listing"
  - "lv_icp_tier_derived relabelled 'ICP Tier' (D-15's fallback), verified by re-read and a D-22 two-point poll"
  - "scripts/check_schema_drift.py RETIRED_FLOW_IDS structure with a must-be-absent invariant (D-24 flip from the original live-AND-disabled design)"
  - "scripts/rollback_property_migration.py --archive-property mode (dry-run and live-armed, proven against both a real 400 rejection AND a real successful archive)"
  - "scripts/apply_fit_score_formula.py --label mode (dry-run and live-armed, proven)"
  - "scripts/put_hubspot_flow.py --delete mode (dry-run and live-armed, proven against a real WF1 deletion)"
  - "50-RETIREMENT-RECORD.md documenting the full arc: the platform constraint, D-24's override, and the completed retirement"
  - "docs/OPERATOR-TIER-ROLLBACK.md amended: rollback is now rebuild-from-JSON, the proven manual-enrolment mechanism no longer exists"
affects: [any future phase touching lv_icp_tier_derived, any phase that would have referenced WF1's flow id 4625147345 (now permanently gone)]

actuals:
  tokens: 15000
  tasks: 1
  commits: 2

tech-stack:
  added: []
  patterns:
    - "RETIRED_FLOW_IDS in check_schema_drift.py: healthy state is ABSENCE (deleted), not live-and-disabled — D-24 flipped this invariant mid-phase when the operator chose deletion over keep-but-off"
    - "Every archive/disable/delete verified by an independent re-read, never the mutating call's own response body"
    - "Two-key write gate (DRY_RUN=false + a dedicated ALLOW_* key) extended uniformly to a third HTTP verb (DELETE on a flow) without introducing a new gate idiom"

key-files:
  created:
    - .planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md
  modified:
    - scripts/check_schema_drift.py
    - tests/test_check_schema_drift.py
    - scripts/rollback_property_migration.py
    - scripts/apply_fit_score_formula.py
    - scripts/put_hubspot_flow.py
    - tests/test_hubspot_properties_config.py
    - config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json
    - config/hubspot_flows/lv_icp_tier-property.after.json
    - config/hubspot_flows/lv_icp_tier_derived-property.after.json
    - config/hubspot_properties.yaml
    - docs/OPERATOR-TIER-ROLLBACK.md
    - .planning/phases/50-derived-tier-property/50-CONTEXT.md
    - .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md
    - .planning/WINDOWS.md

key-decisions:
  - "Session 1 (earlier 2026-08-14): executed WF1 shutdown (D-08 as originally written) and verified live. Archive of lv_icp_tier then rejected live (HTTP 400 CANNOT_DELETE_PROPERTY_IN_USE — WF1's disabled actions still referenced the property). Escalated per D-11 rather than forcing it through; three options documented for the operator."
  - "Session 2 (same date, operator resolved the blocker): the operator selected deleting WF1 entirely, EXPLICITLY OVERRIDING D-08's 'not deleted' prohibition (D-24). Consequence accepted up front: rollback is now rebuild-from-JSON via POST /automation/v4/flows (a new flow id), not a one-action re-enable; the proven manual-enrolment rollback mechanism (proven live in Plan 04) no longer exists once WF1 is deleted."
  - "Built scripts/put_hubspot_flow.py --delete mode (DELETE /automation/v4/flows/{id}, --file made optional for this action only), reusing the script's existing two-key gate rather than a new gate idiom. Dry-run verified, then armed: 204, independently re-read to 404."
  - "Archive retried unchanged (same rollback_property_migration.py --archive-property tool from session 1) and succeeded on the first attempt once WF1's reference was gone: 204, independently re-read to 404, confirmed present under ?archived=true."
  - "Relabelled lv_icp_tier_derived to 'ICP Tier' (D-15's fallback) in the same window as the archive, avoiding the two-properties-same-label confusion session 1 deliberately avoided by deferring it."
  - "Flipped check_schema_drift.py's RETIRED_FLOW_IDS invariant from 'live AND disabled' (D-08's original design) to 'must be absent' (D-24's deletion) — rewrote 3 offline tests to match, added a 4th (test_retired_flow_ids_contains_wf1 unchanged)."
  - "Post-archive re-run of D-07's parity gate (scripts/check_tier_derived_parity.py) unexpectedly still passed byte-identical (population=66 match=61 expected_mismatch=5 defect=0) — an archived property's per-record values remain readable when explicitly named in properties=, a live finding documented as such (not asserted as a standing guarantee) in 50-TIER-PARITY-EVIDENCE.md's amendment, output to a scratch path rather than overwriting the pre-archive evidence artifact."
  - "Second (and final, per D-16) authorised company-record write of this phase: a 1-record armed recompute proof on Melbourne Racing Club (9604614548, a non-vetoed match record, deliberately not one of the 5 pinned stuck records) confirming the pipeline writes lv_anti_icp_flag_num onto a real record end-to-end. The '0' branch is directly observed; the '1' branch is inferred from the shared derivation plus both-engine drift tests, not independently re-observed — stated precisely, not overclaimed."
  - "config/hubspot_properties.yaml: lv_icp_tier declaration removed (matches live archive), lv_icp_tier_derived relabelled to 'ICP Tier' (matches live relabel). scripts/sync_hubspot_properties.py dry-run after the edit proposes zero property creates."

requirements-completed: [TIER-01, TIER-03]

coverage:
  - id: D1
    description: "WF1 (4625147345) DELETED live (D-24), definition preserved only in the committed before/after JSON snapshots, verified by independent re-read (not the DELETE's own response)"
    requirement: "TIER-03"
    verification:
      - kind: other
        ref: "GET /automation/v4/flows/4625147345 -> 404 (independent re-read, recorded in 50-RETIREMENT-RECORD.md's 'D-24 resolution' section)"
        status: pass
    human_judgment: false
  - id: D2
    description: "check_schema_drift.py's RETIRED_FLOW_IDS must-be-absent invariant (D-24 flip), offline-pinned"
    requirement: "TIER-01"
    verification:
      - kind: unit
        ref: "tests/test_check_schema_drift.py#test_retired_flow_deleted_is_ok"
        status: pass
      - kind: unit
        ref: "tests/test_check_schema_drift.py#test_retired_flow_live_and_disabled_is_not_ok"
        status: pass
      - kind: unit
        ref: "tests/test_check_schema_drift.py#test_retired_flow_live_and_enabled_is_not_ok"
        status: pass
    human_judgment: false
  - id: D3
    description: "Archive lv_icp_tier (D-06) — ACHIEVED after D-24's override of D-08 unblocked it"
    requirement: "TIER-03"
    verification:
      - kind: other
        ref: "DELETE /crm/v3/properties/companies/lv_icp_tier -> HTTP 204; independent re-read -> 404; GET /crm/v3/properties/companies?archived=true confirms lv_icp_tier present with archived:true (50-RETIREMENT-RECORD.md 'D-24 resolution')"
        status: pass
    human_judgment: false
  - id: D4
    description: "lv_icp_tier_derived relabelled to 'ICP Tier' (D-15's fallback), values unaffected"
    requirement: "TIER-03"
    verification:
      - kind: other
        ref: "PATCH .../lv_icp_tier_derived {label: 'ICP Tier'} -> 200; independent re-read confirms label; D-22 two-point poll (~40s apart) on 3 known records (9605273630=B, 18047161864=D, 9604614548=C) byte-identical both reads"
        status: pass
    human_judgment: false
  - id: D5
    description: "Post-archive live re-run of check_schema_drift.py and D-07's parity gate confirm the archive did not damage the live scoring engine or disturb the gate's verdict"
    requirement: "TIER-03"
    verification:
      - kind: other
        ref: "check_schema_drift.py: do_not_archive.ok=True, exit_code=0; check_tier_derived_parity.py re-run to scratch path: population=66 match=61 expected_mismatch=5 defect=0 (byte-identical to the pre-archive evidence artifact)"
        status: pass
    human_judgment: false

duration: ~90min (across two live windows the same date, plus this closing session)
completed: 2026-08-14
status: complete
---

# Phase 50 Plan 05: Retirement Complete — D-24 Override (WF1 Deleted, `lv_icp_tier` Archived) Summary

**WF1 (4625147345) DELETED live, explicitly overriding D-08 (D-24), after its disable alone left `lv_icp_tier`'s archive blocked by HubSpot counting a disabled workflow's action as "in use"; `lv_icp_tier` then archived cleanly and `lv_icp_tier_derived` relabelled "ICP Tier" — Phase 50 and the v0.9 milestone's plans are now fully complete.**

## Performance

- **Duration:** ~90 min across two live windows the same date (2026-08-14) plus this closing
  session — session 1 switched WF1 off and hit the archive blocker; session 2 (this one)
  resolved it per the operator's D-24 decision and completed the retirement.
- **Session 1:** ~00:00–02:10 UTC (approx., prior session) — WF1 disabled, archive blocked,
  escalated per D-11.
- **Session 2 (this session):** WF1 deleted, `lv_icp_tier` archived, `lv_icp_tier_derived`
  relabelled, all guard/doc updates landed, phase closed.
- **Tasks:** 1 of 2 (Task 50-05-01's decision was authorised in a prior spawn prompt; Task
  50-05-02 now fully executed across both sessions).
- **Files modified:** 14 (10 code/config + 3 docs + this summary; see `key-files` above).

## Accomplishments

- WF1 (`4625147345`) **DELETED** live via a new `scripts/put_hubspot_flow.py --delete` mode
  (dry-run verified, then armed: `204`, independently re-read to `404`). This is the phase's
  most consequential irreversible act — D-24 explicitly overrode D-08's original "kept, not
  deleted" prohibition after the disable-only state proved insufficient to unblock the archive.
- `lv_icp_tier` **ARCHIVED** live on the first retry once WF1's reference was gone: `204`,
  independently re-read to `404`, confirmed present under `?archived=true` with
  `archived: true`.
- `lv_icp_tier_derived` **relabelled to "ICP Tier"** (D-15's fallback — the internal name stays
  `lv_icp_tier_derived` permanently): `200`, independently re-read, and confirmed unaffected by
  a D-22 two-point poll (~40s apart) on 3 known records (a stuck-B, a vetoed-D, a non-vetoed
  match) — byte-identical both reads.
- `scripts/check_schema_drift.py`'s `RETIRED_FLOW_IDS` invariant **flipped** from D-08's original
  "live AND disabled" to D-24's "must be absent" — 3 offline tests rewritten to match the new
  semantics, run live post-retirement: `do_not_archive.ok=True`, `exit_code=0`.
- D-07's gate (`scripts/check_tier_derived_parity.py`) **re-run live post-archive**, expecting
  degradation and instead finding an archived property's per-record values remain readable when
  explicitly named in `properties=` — byte-identical result (`population=66 match=61
  expected_mismatch=5 defect=0`) to the pre-archive verdict. Documented as a live finding, not a
  standing guarantee, in `50-TIER-PARITY-EVIDENCE.md`'s amendment; output to a scratch path so
  the original evidence artifact was never overwritten.
- Second (and final, per D-16) authorised company-record write of this phase: a 1-record armed
  recompute proof on Melbourne Racing Club (`9604614548`) confirming the pipeline writes
  `lv_anti_icp_flag_num` onto a real record end-to-end (the `"0"` branch directly observed; the
  `"1"` branch inferred from the shared derivation and both-engine drift tests).
- `config/hubspot_properties.yaml` synced to live truth: `lv_icp_tier` declaration removed,
  `lv_icp_tier_derived` relabelled. `sync_hubspot_properties.py` dry-run confirms zero property
  creates proposed.
- `docs/OPERATOR-TIER-ROLLBACK.md` amended: rollback is now rebuild-from-JSON via `POST
  /automation/v4/flows` (a new flow id), and the proven manual-enrolment mechanism no longer
  exists once WF1 is deleted — stated plainly, not softened.
- `.planning/phases/50-derived-tier-property/50-CONTEXT.md` amended with **D-24**, dated,
  recording the `CANNOT_DELETE_PROPERTY_IN_USE` cause, the operator's explicit choice, and the
  rollback consequence.
- `.planning/WINDOWS.md` id 15 (the blocked-archive deviation) marked `fixed` via
  `gsd-tools windows fixed 15`, with a `RESOLVED WITH EVIDENCE` note appended to its description.
- Full offline suite green: `.venv/bin/python -m pytest -q` (2821 passed, 154 skipped) and
  `node --test tests/n8n/*.test.mjs` (683 passed) — one legitimate count-tripwire update
  (`tests/test_hubspot_properties_config.py`, 34 → 33 company properties, matching the archived
  `lv_icp_tier` declaration's removal).

## Task Commits

Both the decision task (50-05-01) and this execution task (50-05-02) span two live windows;
commits are split by window rather than forced into one, since the two windows are genuinely
separate units of work (session 1's WF1-off-plus-guard-edits state was independently correct and
committed on its own before the blocker was even discovered to need a D-24 decision):

1. **Session 1 commit (`449b306`):** WF1 disabled + guard edits + new tooling + retirement
   record (already landed before this session started).
2. **Session 2 commit (this session):** D-24 execution — `put_hubspot_flow.py --delete` mode,
   WF1 deleted, `lv_icp_tier` archived, `lv_icp_tier_derived` relabelled, `RETIRED_FLOW_IDS`
   invariant flipped + tests rewritten, yaml synced, all docs updated (`50-RETIREMENT-RECORD.md`,
   `50-CONTEXT.md`, `50-TIER-PARITY-EVIDENCE.md`, `OPERATOR-TIER-ROLLBACK.md`) — see commit hash
   in the final PLAN COMPLETE block below.
3. **Metadata commit:** this summary + STATE.md + ROADMAP.md + REQUIREMENTS.md + WINDOWS.md.

## Files Created/Modified

See `key-files` in the frontmatter above for the complete list across both sessions.

## Decisions Made

See `key-decisions` in the frontmatter above for the complete, dated list. In summary: session 1
executed WF1's disable and hit the archive blocker; the operator resolved it by explicitly
authorising WF1's deletion (D-24, overriding D-08); session 2 executed that decision end to end
and closed the phase.

## Deviations from Plan

### Auto-fixed Issues

None in the Rule 1-3 sense in this session's own new work. One legitimate, expected fallout
fixed as part of landing the archive: `tests/test_hubspot_properties_config.py`'s manifest-drift
count tripwire (34 → 33 company properties) — not a bug, the direct and anticipated consequence
of removing `lv_icp_tier`'s yaml declaration.

### Rule 4 escalation, RESOLVED this session

**1. [Rule 4 - Architectural] `lv_icp_tier` archive blocked by an undocumented HubSpot platform
constraint — RESOLVED by an explicit operator override (D-24)**
- **Found during (session 1):** Task 50-05-02, armed live mutation 2 (archive the enum).
- **Issue:** `DELETE /crm/v3/properties/companies/lv_icp_tier` returned HTTP 400
  (`PropertyValidationError.CANNOT_DELETE_PROPERTY_IN_USE`) because WF1's actions still
  referenced `lv_icp_tier` as a write target, and HubSpot counts this as "in use" regardless of
  whether the workflow is enabled.
- **Escalated per D-11** rather than forced through in session 1: three options were documented
  in `50-RETIREMENT-RECORD.md` for the operator (accept the interim state; edit WF1's actions
  and forfeit the proven rollback; delete WF1 entirely and override D-08).
- **Resolution (session 2, this session):** the operator **selected deleting WF1 entirely**,
  explicitly overriding D-08's "not deleted" prohibition, accepting the stated consequence that
  rollback becomes rebuild-from-JSON. Executed: WF1 deleted (`204`/`404` re-read), archive
  retried and succeeded (`204`/`404` re-read + `?archived=true` confirmation), relabel completed
  in the same window. Full record in `50-RETIREMENT-RECORD.md`'s "D-24 resolution" section.
- **Files modified:** `scripts/put_hubspot_flow.py` (new `--delete` mode), plus the guard/doc
  updates listed in `key-files`.
- **Verification:** independent re-reads at every step (never a mutating call's own response
  body) — see coverage D1–D5 above.

---

**Total deviations:** 1 escalated in session 1 (Rule 4), resolved this session by an explicit
operator override (D-24) rather than by this plan improvising a workaround.
**Impact on plan:** The plan's fully-authorised end state (`retire-and-relabel`) IS reached, via
a path the plan's own text did not originally authorise (WF1 deletion) but that the operator
explicitly selected when the authorised path proved insufficient. WF1 is gone, `lv_icp_tier` is
archived, `lv_icp_tier_derived` carries the canonical display label. Phase 50 closes complete.

## Issues Encountered

- **macOS TCC access loss (session 1, prior):** `~/Desktop` became inaccessible mid-session with
  `EPERM`, halting the prior executor with nothing committed and no HubSpot mutation run.
  Resolved by the operator re-granting Full Disk Access.
- **HubSpot property-in-use rejection (session 1):** see Rule 4 escalation above — resolved this
  session via D-24.
- **No issues in this session** beyond the expected count-tripwire test update.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Phase 50 is fully complete.** `lv_icp_tier` is archived, WF1 is deleted, `lv_icp_tier_derived`
is the sole, canonically-labelled source of truth for ICP tier, live-proven with zero
dependency on any HubSpot workflow or property-change event. The v0.9 milestone's 6 phases (46,
47, 47.5, 48, 49, 50) are all plan-complete — ready for a `/gsd-ship` review, not shipped by this
session.

**What remains an accepted, disclosed, unresolved residual — not closed by this or any prior
session:** reports/dashboards possibly still referencing `lv_icp_tier` by name. HubSpot exposes
no public API to enumerate either. The recovery path (repoint to `lv_icp_tier_derived` after a
visible break) remains the operator's previously stated accepted risk.

**What changed for future operators:** the rollback runbook (`docs/OPERATOR-TIER-ROLLBACK.md`)
no longer describes a working one-action or even one-mechanism rollback — WF1 no longer exists,
and its 2026-08-14 amendment states this plainly. Any future correction to
`lv_icp_tier_derived` goes through the formula/pipeline, never a WF1-based path.

---
*Phase: 50-derived-tier-property*
*Completed: 2026-08-14*

## Self-Check: PASSED

- FOUND: `.planning/phases/50-derived-tier-property/50-05-SUMMARY.md`
- FOUND: `.planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md`
- FOUND: `scripts/check_schema_drift.py`
- FOUND: `tests/test_check_schema_drift.py`
- FOUND: `scripts/put_hubspot_flow.py` (`--delete` mode present)
- CONFIRMED live: `GET /automation/v4/flows/4625147345` → 404
- CONFIRMED live: `GET /crm/v3/properties/companies/lv_icp_tier` → 404;
  `?archived=true` listing contains it with `archived: true`
- CONFIRMED live: `GET /crm/v3/properties/companies/lv_icp_tier_derived` → `label: "ICP Tier"`
- FOUND commit: `449b306`
