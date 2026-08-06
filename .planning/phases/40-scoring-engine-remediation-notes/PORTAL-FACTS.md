# Phase 40 Plan 01 — Portal Facts

Live reads only, portal 22617666 (ap1), `HUBSPOT_PRIVATE_APP_TOKEN` via `hs_headers()`.
Read-only for all facts below — no writes, no `hs_headers()`/token value ever printed.

## Enabled flow list (companies object, `objectTypeId: 0-2`)

`GET /automation/v4/flows` returned 8 total flows across all object types in this portal.
Filtering to `objectTypeId == "0-2"` (companies) and `isEnabled == true` gives exactly the
four already-known company scoring flows — **no fifth company scoring flow exists**:

| Flow ID | Name | isEnabled | objectTypeId |
|---|---|---|---|
| 4626124224 | Update Score Based on Org Type | true | 0-2 |
| 4626722240 | Geography Score | true | 0-2 |
| 4626722237 | Annual Revenue Score | true | 0-2 |
| 4625147345 | WF1 Set ICP Tier based on ICP Score | true | 0-2 |

The other four flows in the portal are all non-companies objects (deal-pipeline defaults,
a contact form-submission flow) and are out of scope for this phase.

## lv_icp_tier enum options

`GET /crm/v3/properties/companies/lv_icp_tier` (Open Question 1):

| value | label | hidden |
|---|---|---|
| A | A | false |
| B | B | false |
| C | C | false |
| D | D | false |

**`Unscored` is ABSENT from this property's enum options today.** Only `A`, `B`, `C`, `D`
exist. This confirms HANDOVER §9's historical gap is still live as of this read
(2026-08-06) — 40-06 Task 1's conditional `Unscored` enum-option PATCH is required, not
optional, before WF1 can be edited to write `Unscored` for D-03's F8 fix.

## lv_icp_fit_score calculationFormula

`GET /crm/v3/properties/companies/lv_icp_fit_score` (Open Question 2): `type=number`,
`fieldType=calculation_equation`, `calculated=true`. Verbatim current formula string:

```
org_type_score + geography_score + annual_revenue_score
```

Property tokens this formula references: `org_type_score`, `geography_score`,
`annual_revenue_score`. This is a **3-term sum**, not 4 — it confirms HANDOVER F1 exactly:
there is no `produces_content_score` term today. 40-04 Task 3 must extend this exact
string (append `+ produces_content_score`, and per D-06's 5-component note, also
`+ gambling_score` if that becomes a formula term rather than a pure deduction elsewhere) —
never reconstruct calculation-equation syntax from documentation examples alone (Pitfall 3).

## Existing `*_score` company properties

`GET /crm/v3/properties/companies` filtered to names ending in `_score`:

| name | type | fieldType | defaultValue | calculated |
|---|---|---|---|---|
| `annual_revenue_score` | number | number | null | false |
| `geography_score` | number | number | null | false |
| `hs_max_recommendation_score` | number | calculation_rollup | null | false |
| `lv_icp_fit_score` | number | calculation_equation | null | true |
| `org_type_score` | number | number | null | false |

**`produces_content_score` and `gambling_score` do not exist yet** — 40-04 creates both as
net-new properties (D-06), not edits to an existing one. Note: the property *schema*'s
`defaultValue` field reads `null` for all three writable components (`annual_revenue_score`,
`geography_score`, `org_type_score`) — HANDOVER §10.1's "property-level default of 0" claim
refers to a per-record `PROPERTY_DEFAULT_VALUE` stamp observed in a record's value history
on creation, a different mechanism than the property schema's own `defaultValue` field. Not
contradictory, just two different things; noted here so 40-04/40-07 don't conflate them.

## D-05 round-trip verdict

pending — Task 2 of this plan runs the disable -> edit -> PUT -> validate-on-disposable ->
re-enable cycle against flow `4626124224` and records the outcome here.
