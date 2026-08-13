# Phase 50 Dependent Sweep -- lv_icp_tier Portal Dependents (D-13)

**Scripted sweep run:** 2026-08-13T11:09:05.152285+00:00
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

- **Saved views (companies index page):** UNCHECKED
- **Reports / dashboards:** UNCHECKED
- **checked_at:** _(unfilled -- fill in when the manual check is performed)_
- **Findings:** _(none recorded yet)_
