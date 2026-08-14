# Phase 50 Dependent Sweep -- lv_icp_tier Portal Dependents (D-13)

**Scripted sweep run:** 2026-08-14T00:02:26.212403+00:00
**Lists scanned:** 0
**Flows scanned:** 10

Re-runnable (D-13): every invocation derives this report fresh from a live portal read -- it is never diffed against a cached prior run as the source of truth.

## Scripted Findings (Lists API + Flows API)

| Object Type | ID | Name | JSON Path |
|---|---|---|---|
| flow | 4625147345 | WF1 Set ICP Tier based on ICP Score | `$.actions[2].fields.property_name` |
| flow | 4625147345 | WF1 Set ICP Tier based on ICP Score | `$.actions[3].fields.property_name` |
| flow | 4625147345 | WF1 Set ICP Tier based on ICP Score | `$.actions[4].fields.property_name` |
| flow | 4625147345 | WF1 Set ICP Tier based on ICP Score | `$.actions[5].fields.property_name` |
| flow | 4625147345 | WF1 Set ICP Tier based on ICP Score | `$.actions[6].fields.property_name` |

## Manual UI Check (API-blind half -- D-12, D-13)

Saved views (companies index page) and reports/dashboards have no documented public HubSpot API (50-RESEARCH.md Q3) and cannot be enumerated by this script. D-12 confirms these two dependent classes are known to exist; they must be checked by a human in the portal UI, dated, and recorded here -- an unfilled manual half stays visibly UNCHECKED rather than silently passing as clean.

- **Saved views (companies index page):** CHECKED and MIGRATED. Operator confirmed (verbatim, 2026-08-14): "I've switched to derived property for every view using non-derived property previously." Saved views filtering on `lv_icp_tier` did exist -- consistent with D-12's expectation -- and every one has been repointed to `lv_icp_tier_derived`. No blocked dependent was reported, so D-11's stop-and-escalate path was not triggered. **Limitation, disclosed rather than papered over:** exact view names and owners were not enumerated back to us -- the migration is attested by the operator, not captured item-by-item. The scripted half of this sweep stays the auditable, re-runnable evidence; this line is an operator attestation, not an equivalent record.
- **Reports / dashboards:** **UNCONFIRMED -- residual unknown, not a zero finding.** The operator's statement above covers saved views only and is silent on the reports library. This is explicitly NOT closed and must not be inferred either way (not "clean," not "found"). **This residual must not be missed at Plan 05's one-way retirement decision** -- archiving `lv_icp_tier` while a report still groups by, filters on, or displays it is precisely the breakage D-13 exists to prevent, and no evidence either confirms or rules that out today.
- **checked_at:** 2026-08-14 (operator-attested; scripted re-run performed the same date, see below)
- **Findings:** No blocked (non-migratable) dependent reported for saved views. Reports/dashboards: not checked -- open residual carried to Plan 05.

### Post-migration re-run (D-13)

Re-run same date as the manual check above, after the operator's view migration, to confirm the migration did not surface (or leave behind) any scripted dependent. **No delta:** scripted findings are byte-for-byte identical to the pre-migration run committed in `f27fef3` -- still 0 lists / 10 flows scanned, same 5 findings, all on WF1 (`4625147345`) itself, WF1's own known writer role (not an unexpected dependent; D-06/D-08 already cover its disposition). This is expected: the migration touched saved views only, which this script cannot see either before or after -- it is not evidence the view migration happened, only evidence that migrating views did not disturb the scripted (list/flow) surface.
