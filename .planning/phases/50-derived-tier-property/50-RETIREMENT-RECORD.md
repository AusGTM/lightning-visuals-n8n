# Phase 50 Plan 05 — Retirement Record

**Date:** 2026-08-14
**Authorised option (Task 50-05-01, verbatim from the operator):** `retire-and-relabel` — "Proceed:
WF1 off, archive `lv_icp_tier`, relabel the derived property to 'ICP Tier' (D-15's fallback)."
**D-07 verdict this was taken against:** `50-TIER-PARITY-EVIDENCE.md` — "PASS -- zero defect rows;
all 5 known stuck records read the exact expected mismatch."

## Outcome: PARTIAL — WF1 off (complete); archive BLOCKED by a platform constraint not
anticipated in this phase's research; relabel DEFERRED as a consequence

This plan does not close in the fully-authorised `retire-and-relabel` end state. It closes in a
new, previously undocumented intermediate state: **WF1 is off (D-08 satisfied in full), but
`lv_icp_tier` could not be archived** because HubSpot's API refuses to delete a property that is
still referenced by *any* workflow action — including a disabled workflow's action. Deleting or
editing WF1's actions to remove the reference would violate D-08 ("not deleted") and forfeit the
proven one-action rollback mechanism (`50-ROLLBACK-DRILL.md`), so neither was attempted. This is
a D-11 situation: a dependent (WF1's own action definition, not a downstream report) cannot be
migrated within the constraints this plan is allowed to operate under, so the plan stops and
brings it to the operator rather than forcing the archive through or silently leaving the
half-authorised action set unrecorded.

The relabel was **deliberately not performed**, even though it was independently authorised,
because with `lv_icp_tier` still live, relabelling `lv_icp_tier_derived` to "ICP Tier" would put
two live company properties on the portal both displaying "ICP Tier" in every property picker,
view builder, and report editor — a new, avoidable confusion the operator did not sign up for
when relabel was framed as happening alongside a successful archive. `config/hubspot_properties.yaml`
was left declaring `lv_icp_tier` (unarchived, still live) and `lv_icp_tier_derived` labelled
"ICP Tier (Derived)" — this matches live truth exactly.

## Armed live mutation 1 — WF1 off (D-08): COMPLETE

- `scripts/fetch_hubspot_flow.py --flow-id 4625147345 --label after` — fresh GET, `isEnabled: true`
  (pre-mutation state confirmed).
- `ALLOW_HUBSPOT_FLOW_WRITE=true DRY_RUN=false` → `put_hubspot_flow.py --file
  config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json --flow-id 4625147345 --disable` —
  PUT returned 200, response body `isEnabled: false`, `revisionId: "23"`.
- **Independent re-read** (not the PUT's own response): `fetch_hubspot_flow.py --flow-id
  4625147345 --label after` again → `GET /automation/v4/flows/4625147345` → 200, `isEnabled:
  False`. Snapshot `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json` refreshed from
  this read-back.
- WF1's definition (all actions, filter branches, enrollment criteria) is unchanged — only
  `isEnabled` flipped. Re-enabling it is one action, per `docs/OPERATOR-TIER-ROLLBACK.md` step 1.

## Armed live mutation 2 — archive `lv_icp_tier` (D-06): BLOCKED, new discovery

- `DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true` → `rollback_property_migration.py
  --archive-property lv_icp_tier` → `DELETE /crm/v3/properties/companies/lv_icp_tier` returned
  **HTTP 400**, not the expected 204/200.
- Full response body:
  ```json
  {
    "status": "error",
    "message": "Property: lv_icp_tier of object type 0-2 is currently used in 1 places and cannot be deleted",
    "correlationId": "019ffdef-139f-7491-80d0-86cefcd861eb",
    "errors": [
      {
        "subCategory": "PropertyValidationError.PROPERTY_USAGE",
        "message": "Property lv_icp_tier of object type 0-2 in use by AUTOMATION_PLATFORM_FLOW (display type WORKFLOW) ID 4625147345: ",
        "context": {
          "property": ["lv_icp_tier"], "objectTypeId": ["0-2"],
          "parentType": ["AUTOMATION_PLATFORM_FLOW"], "parentDisplayType": ["WORKFLOW"],
          "parentName": ["4625147345"], "link": [""]
        }
      }
    ],
    "context": {"property": ["lv_icp_tier"], "objectTypeId": ["0-2"], "usageCount": ["1"]},
    "category": "VALIDATION_ERROR",
    "subCategory": "PropertyValidationError.CANNOT_DELETE_PROPERTY_IN_USE"
  }
  ```
- **Independent re-read**: `GET /crm/v3/properties/companies/lv_icp_tier` → 200, `archived: false`.
  The property was NOT archived. Nothing was left in an ambiguous state — the DELETE failed
  cleanly and the property is exactly as it was before the attempt.
- **What this means:** HubSpot counts a workflow action's reference to a property as "usage"
  regardless of whether the workflow is enabled. Disabling WF1 (mutation 1, above) did not release
  the reference. This was checked against `50-RESEARCH.md` and `50-NULL-PROBE.json` (RESEARCH Q6,
  which answered whether the DELETE is a soft archive) before the attempt — neither anticipated an
  in-use rejection; this is new information discovered during execution, not a documented risk the
  operator already weighed.
- **Why no auto-fix was attempted:** the only two paths that unblock the archive are (a) deleting
  WF1 entirely — explicitly prohibited by this plan's own prohibitions list ("WF1 4625147345 is
  not deleted") — or (b) editing WF1's actions to strip the `property_name: lv_icp_tier`
  references, which keeps the flow object but destroys the one-action-rollback guarantee D-08 and
  the proven rollback drill depend on. Neither is something this plan, or the operator's
  `retire-and-relabel` selection, authorised. Per D-11, this stops here rather than being forced
  through.

## Relabel `lv_icp_tier_derived`: DEFERRED

Not run. `--label` mode was dry-run verified working correctly (prints the exact PATCH payload)
both before and after this session's guard edits, but was not armed — see rationale above (two
properties both displaying "ICP Tier" while the old one is still live would create a new,
avoidable confusion). `lv_icp_tier_derived` remains labelled "ICP Tier (Derived)" live.

## Guard edits (D-17 item 2): landed regardless, and correctly reflect the mutation that DID happen

`scripts/check_schema_drift.py`:
- `"lv_icp_tier"` removed from `DO_NOT_ARCHIVE_COMPANY_PROPERTIES` (12→11). This is correct
  independent of archive status: WF1 was the property's only writer, and WF1 is now off, so
  `lv_icp_tier` is no longer part of the live scoring engine's do-not-archive invariant — it is an
  orphaned, frozen leftover, not something a future run should protect from archival.
- `"4625147345"` moved from `DO_NOT_ARCHIVE_FLOW_IDS` (6→5) into a new `RETIRED_FLOW_IDS`
  structure with a **live AND disabled** invariant, distinct from the "live and enabled" invariant
  the other five flows still carry. `_compute_do_not_archive` extended to fold this in; damage for
  a retired flow now means deleted OR re-enabled.
- `ACCEPTED_DIVERGENCES`'s `PARITY-01-tier-label` entry restated against `lv_icp_tier_derived`'s
  five-label ladder (D-09) — this documents the calculated property's label semantics and is
  correct going forward regardless of the old enum's archive status, since `lv_icp_tier_derived`
  is already the functional source of truth (D-07 proved parity; WF1, the old enum's only writer,
  is now off).
- `tests/test_check_schema_drift.py` extended with 4 new offline tests pinning
  `RETIRED_FLOW_IDS`/`_compute_do_not_archive`'s live-and-disabled invariant (live+disabled=ok,
  absent=not ok, live+enabled=not ok, `RETIRED_FLOW_IDS` contains `4625147345`), plus updated size
  assertions (11/5/15) and the restated `PARITY-01-tier-label` property name.

`config/hubspot_properties.yaml`: **left unchanged from its pre-session state** — still declares
`lv_icp_tier` (matches live: still present, unarchived) and `lv_icp_tier_derived` labelled
"ICP Tier (Derived)" (matches live: not yet relabelled). An earlier pass in this session removed
the `lv_icp_tier` block and relabelled the derived property in the yaml ahead of the live
mutations succeeding; both edits were reverted before this commit once the archive failed, so the
yaml stays truthful to live state at every commit in this repo's history.

`scripts/rollback_property_migration.py` (`--archive-property` mode) and
`scripts/apply_fit_score_formula.py` (`--label` mode): both built and dry-run verified working
correctly. Neither is at fault for the blocked archive — the tool issued the correct DELETE; the
portal rejected it for a reason outside either tool's control.

## Post-mutation `check_schema_drift.py`: exit 0

```
summary: {'in_sync': 51, 'documented_gap': 5} | do_not_archive.ok=True | exit_code=0
```

`do_not_archive.ok=True` confirms the comparator correctly reads the actual live state: WF1
(`4625147345`) is live and disabled, satisfying `RETIRED_FLOW_IDS`' invariant; the five still-live
scoring flows remain live and enabled; the eleven remaining do-not-archive company properties are
all still live. `lv_icp_tier` itself is out of `D04_COMPANY_PROPERTY_SCOPE` and still declared in
the yaml, so its continued (unarchived) live presence does not register as drift — this is a
known leniency in the comparator's scope, not a defect introduced by this session; the comparator
was never asked to track "declared and live but functionally orphaned."

## Reports/dashboards residual — accepted risk (unchanged from the operator's original disclosure,
## now describing the interim rather than the final state)

**What was confirmed:** Saved views were found and migrated — operator-attested 2026-08-14 (per
`50-DEPENDENTS-SWEEP.md`'s dated pre-cutover re-run).

**What was NOT confirmed:** Reports and dashboards — HubSpot exposes no public API for enumerating
either, so this category was never confirmed clean or dirty. This remains true regardless of
whether the archive completes; it does not become more or less risky because the archive is
currently blocked.

**Recovery path, as originally disclosed:** because the archive did not happen, this recovery path
is currently moot — `lv_icp_tier` is still live, so any report or dashboard still pointed at it
continues to work exactly as before, with no breakage. If a future session resolves the WF1-usage
blocker and archives the property, the original disclosure applies unchanged: the archived
property and its historical data persist under `GET /crm/v3/properties/companies?archived=true`,
so a broken report can be repointed to `lv_icp_tier_derived` after the fact — but it breaks
visibly and without warning first. Do not treat the interim safety (nothing currently breaks) as
evidence the underlying unknown has been resolved; it has not.

## What a future session needs to resolve before re-attempting the archive

The archive cannot proceed until one of the following is authorised at a fresh decision
checkpoint (none is authorised by this record):

1. **Accept the interim state as the phase's closing state.** WF1 stays off with its definition
   intact; `lv_icp_tier` stays live but frozen (no writer — anyone still reading it gets silently
   stale data, since nothing updates it going forward); archive and relabel are deferred to a
   later phase that first resolves the WF1-usage reference. This is the D-06-style coherent
   partial state, just triggered by a platform constraint rather than a failed D-07 gate.
2. **Authorise editing WF1's tier-write actions** (actions 4–8, which each write a static value to
   `lv_icp_tier`) to remove the property reference, keeping the flow object itself. This unblocks
   the archive but forfeits the proven one-action-rollback mechanism: re-enabling WF1 after this
   edit would no longer write anything to `lv_icp_tier` (which no longer exists) or anywhere else
   — it becomes a no-op shell, not a real rollback path. Requires an explicit operator decision;
   not something this plan's `retire-and-relabel` selection authorised.
3. **Authorise deleting WF1 entirely.** Directly overrides D-08 and this plan's own prohibition
   ("WF1 4625147345 is not deleted"). Requires the operator to say so in words, not to be inferred
   from any existing authorisation.

Whichever path is chosen, the relabel of `lv_icp_tier_derived` should ride with it (relabel alone,
with the old enum still live, creates the two-properties-same-label confusion noted above; relabel
alongside a resolved archive is unambiguous).
