# Phase 50 Plan 05 — Retirement Record

**Date:** 2026-08-14
**Authorised option (Task 50-05-01, verbatim from the operator):** `retire-and-relabel` — "Proceed:
WF1 off, archive `lv_icp_tier`, relabel the derived property to 'ICP Tier' (D-15's fallback)."
**D-07 verdict this was taken against:** `50-TIER-PARITY-EVIDENCE.md` — "PASS -- zero defect rows;
all 5 known stuck records read the exact expected mismatch."

## Outcome: COMPLETE (D-24 override) — WF1 deleted, `lv_icp_tier` archived, derived property
relabelled "ICP Tier"

**This closes the phase.** The session below narrates in order: the first attempt (WF1 switched
off, archive blocked), the blocker, and the operator's D-24 resolution (delete WF1 outright,
overriding D-08) that unblocked and completed everything `retire-and-relabel` originally
authorised. Nothing in the "blocked" narrative below is stale error — it is exactly what
happened, in the order it happened, and the reason a second live window (this one) was needed.

### D-24 resolution (2026-08-14, second live window this same date)

The operator was presented with three options at the blocker (see "What a future session needs
to resolve" below, as it stood at the time): accept the interim state, edit WF1's tier-write
actions to strip the property reference, or delete WF1 entirely. **The operator chose deletion,
explicitly overriding D-08's "not deleted" prohibition**, accepting the stated consequence that
rollback becomes rebuild-from-JSON (`config/hubspot_flows/4625147345-wf1-set-icp-tier.before.json`
→ `POST /automation/v4/flows`) rather than a one-action re-enable.

**Tooling built first, disarmed.** `scripts/put_hubspot_flow.py` gained a `--delete` mode
(`DELETE /automation/v4/flows/{flow_id}`, no body — `--file` made optional for this action only),
reusing the script's existing two-key gate (`DRY_RUN=false` AND `ALLOW_HUBSPOT_FLOW_WRITE=true`)
rather than introducing a third gate idiom. Dry-run verified first.

**Armed live mutation 1 — delete WF1.**
```
ALLOW_HUBSPOT_FLOW_WRITE=true DRY_RUN=false .venv/bin/python -c "... --flow-id 4625147345 --delete ..."
-> {"status_code": 204, "text": ""}
```
**Independent re-read**: `GET /automation/v4/flows/4625147345` → **404**. WF1 no longer exists.
The before/after JSON snapshots committed at the end of the first session (commit `449b306`) were
confirmed present at HEAD before this delete ran — they are now the only copy of WF1's definition,
and the sole rebuild source if it is ever recreated.

**Armed live mutation 2 — archive `lv_icp_tier`, retried.** With WF1 gone, the same tool from the
first session was re-run unchanged:
```
DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true .venv/bin/python -c "... --archive-property lv_icp_tier ..."
-> DELETE /crm/v3/properties/companies/lv_icp_tier -> HTTP 204
-> verified gone by re-read (404): True
```
Succeeded on the **first retry** — no 30-60s settling wait was needed; the `CANNOT_DELETE_
PROPERTY_IN_USE` counter cleared the moment WF1's action reference was gone. **Independent
re-read via the archived-properties listing** (`GET /crm/v3/properties/companies?archived=true`,
not the single-property GET, which would now itself 404): `lv_icp_tier` present, `archived: true`,
`archivedAt: "2026-08-14T02:17:57.731Z"`. That entry was written verbatim to
`config/hubspot_flows/lv_icp_tier-property.after.json`, replacing the pre-archive live snapshot.

**Armed live mutation 3 — relabel `lv_icp_tier_derived` to "ICP Tier" (D-15's fallback).**
```
ALLOW_FORMULA_WRITE=true .venv/bin/python -c "... --property lv_icp_tier_derived --label 'ICP Tier' ..."
-> PATCH 200
-> verified by re-read: True
```
Refreshed `config/hubspot_flows/lv_icp_tier_derived-property.after.json` from the live re-read
(`label: "ICP Tier"`, internal name unchanged, `readOnlyValue: true`, formula unchanged).

**D-22 poll (two reads, ~40s apart) on three known records, confirming the relabel and archive
disturbed nothing else:**

| Record | `lv_icp_tier_derived` | `lv_icp_fit_score` | `lv_anti_icp_flag_num` | Class |
|---|---|---|---|---|
| `9605273630` Port Macquarie Race Club | B (both reads) | 45 | null | known stuck, correctly B |
| `18047161864` Simtech LED | D (both reads) | 40 | 1 | vetoed hardware, correctly D |
| `9604614548` Melbourne Racing Club | C (both reads) | 35 | 0 | match, non-vetoed |

Byte-identical both reads — nothing regressed.

**Config sync verified.** `config/hubspot_properties.yaml`: `lv_icp_tier` declaration removed,
`lv_icp_tier_derived`'s label changed to `ICP Tier`. `scripts/sync_hubspot_properties.py` dry-run
after the edit: `Properties to create (0): []` for both companies and contacts — the yaml does
not propose re-creating the property it just archived.

**`scripts/check_schema_drift.py` re-run live, post-retirement:**
```
summary: {'in_sync': 50, 'documented_gap': 5} | do_not_archive.ok=True | exit_code=0
```
`do_not_archive.ok=True` now asserts the D-24-flipped invariant: `RETIRED_FLOW_IDS`'s healthy
state is **absence** (deleted), not "live and disabled" as originally designed under D-08 — see
the guard-edit section below for the full before/after of that flip, including the three
offline tests rewritten to pin the new semantics.

**D-07's gate re-run live, post-archive — unexpected positive finding.**
`scripts/check_tier_derived_parity.py` was re-run (output to a scratch path, not overwriting the
evidence artifact) expecting `lv_icp_tier` to read null on every record once archived. It did
not: **an archived property's last value is still returned by a normal object GET/search when
the property is explicitly named in `properties=`** — not just present in the
`?archived=true` schema listing (already known), its per-record *values* remain readable the
same way. Re-run result: `population=66 match=61 expected_mismatch=5 defect=0` — byte-identical
classification to the pre-archive gate. Full write-up, including the explicit caveat that this
is a live finding on this date and not asserted as a standing guarantee, appended to
`50-TIER-PARITY-EVIDENCE.md`'s AMENDMENT 2026-08-14 section.

**Second D-16 deviation — the pipeline→calc-engine chain proven end-to-end (recorded here per
the operator's explicit request).** D-16 declares zero company write windows for this phase; two
deviations have now been authorised and BOTH ARE SPENT — no further company record writes remain
available under this phase's authorisation:
1. **50-06's 6-record backfill** (`lv_anti_icp_flag_num` mirror, the vetoed population) —
   already recorded in that plan's summary.
2. **This session's 1-record recompute proof**, subject Melbourne Racing Club `9604614548` — a
   deliberate `match` (`C`/`C`) record, NOT one of the 5 pinned stuck records, so D-07's gate was
   left undisturbed. Armed `scripts/june_run_arm.py --ids 9604614548` (allowlist of exactly one
   id), dispatched an armed recompute POST (`recompute=True` — 0 provider credits, 0 Anthropic
   calls, 1 n8n execution), then disarmed immediately and verified the disarm by read-back
   (`ALLOW_HUBSPOT_RECORD_WRITES: "false"`, empty allowlists). Read-back:
   `lv_anti_icp_flag_num` moved **null → `"0"`**, agreeing with `lv_anti_icp_flag='false'`;
   `lv_icp_fit_score` 35, `lv_icp_tier` C, `lv_icp_tier_derived` C — all unchanged.
   **What this proves, stated precisely:** the pipeline writes the numeric mirror onto a real
   record end-to-end — not just to the node's output (execution `11879`, an earlier UNARMED
   recompute, proved emission but never landed a write). The `"0"` branch is **directly
   observed** on this record. The `"1"` branch (a vetoed record) is **inferred**, not
   independently re-observed here — from the same shared derivation (`Decide Company Action` /
   `src/icp_scoring.py` compute the veto once and serialize it twice) plus the drift tests in
   both engines that assert the boolean and its mirror always agree. Do not overstate this as a
   second direct observation of the `"1"` branch; it is not one.

### Historical narrative below — the first session's blocked attempt

The section immediately below ("Armed live mutation 1/2", "Relabel: DEFERRED", etc.) is the
UNEDITED record of the first live window, before the blocker was discovered. It is kept verbatim
as the accurate account of what was tried and why it stopped; the D-24 resolution above is what
happened next, in a second live window the same date.

## Outcome (as it stood after the FIRST live window): PARTIAL — WF1 off (complete); archive
BLOCKED by a platform constraint not anticipated in this phase's research; relabel DEFERRED as a
consequence

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

## Reports/dashboards residual — accepted risk, STILL UNRESOLVED after the completed archive

This section is not superseded by the D-24 resolution above — it is the one part of the original
disclosure that stays exactly as stated, because archiving the property does not itself resolve
it. Do not read the phase's completion as having closed this risk.

**What was confirmed:** Saved views were found and migrated — operator-attested 2026-08-14 (per
`50-DEPENDENTS-SWEEP.md`'s dated pre-cutover re-run).

**What was NOT confirmed, and remains not confirmed now that the archive has happened:** Reports
and dashboards — HubSpot exposes no public API for enumerating either, so this category was never
confirmed clean or dirty, before or after the archive.

**Recovery path — this is now the live, active path, not a hypothetical.** `lv_icp_tier` is
archived. Any report or dashboard still pointed at it may now be broken. The disclosed recovery
remains: the archived property and its historical data persist under
`GET /crm/v3/properties/companies?archived=true`, so a broken report can be repointed to
`lv_icp_tier_derived` after the fact — but it breaks visibly and without warning first, and this
record contains no evidence either way about whether any report or dashboard actually references
`lv_icp_tier`. **Proceed and accept the risk** was the operator's earlier stated choice for this
residual; nothing in this session narrows or resolves it further.

## Resolution record — how the blocker below was actually resolved (superseded by D-24 above)

The three options originally offered here (kept verbatim below for the historical record) were:
accept the interim state, edit WF1's actions to strip the property reference, or delete WF1
entirely. **The operator selected option 3 — delete WF1 entirely — explicitly overriding D-08.**
See "D-24 resolution" at the top of this document for the full execution record.

1. **Accept the interim state as the phase's closing state.** WF1 stays off with its definition
   intact; `lv_icp_tier` stays live but frozen (no writer — anyone still reading it gets silently
   stale data, since nothing updates it going forward); archive and relabel are deferred to a
   later phase that first resolves the WF1-usage reference. This is the D-06-style coherent
   partial state, just triggered by a platform constraint rather than a failed D-07 gate.
   **NOT SELECTED.**
2. **Authorise editing WF1's tier-write actions** (actions 4–8, which each write a static value to
   `lv_icp_tier`) to remove the property reference, keeping the flow object itself. This unblocks
   the archive but forfeits the proven one-action-rollback mechanism: re-enabling WF1 after this
   edit would no longer write anything to `lv_icp_tier` (which no longer exists) or anywhere else
   — it becomes a no-op shell, not a real rollback path. **NOT SELECTED.**
3. **Authorise deleting WF1 entirely.** Directly overrides D-08 and this plan's own prohibition
   ("WF1 4625147345 is not deleted"). **SELECTED.** Executed as recorded above: WF1 deleted
   (`204`, independently re-read `404`), `lv_icp_tier` archived cleanly on retry, and
   `lv_icp_tier_derived` relabelled "ICP Tier" alongside it in the same live window, per the
   instruction below (kept because it was followed).

Whichever path is chosen, the relabel of `lv_icp_tier_derived` should ride with it (relabel alone,
with the old enum still live, creates the two-properties-same-label confusion noted above; relabel
alongside a resolved archive is unambiguous). — Followed: the relabel rode with the archive in the
same window, per D-24's own resolution above.
