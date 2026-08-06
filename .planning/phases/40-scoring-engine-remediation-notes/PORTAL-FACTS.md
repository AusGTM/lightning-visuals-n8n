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

**PROVEN: `PUT /automation/v4/flows/{flowId}` accepts a `STATIC_BRANCH` action-content edit
and it takes effect live.** Executed against flow `4626124224` (Update Score Based on Org
Type), per D-07's protocol:

1. **Disable** — PUT the archived `.before.json` body with `isEnabled: false`. Accepted
   (200); re-GET confirmed `isEnabled: false`.
2. **Edit** — mutated the two `SINGLE_CONNECTION` target actions the `lv_org_type`
   `STATIC_BRANCH` action points `regulator` and `gambling_operator` at:
   `fields.value.staticValue` `"0"` -> `"5"` (regulator, F10/ENGINE-06) and `"-20"` -> `"0"`
   (gambling_operator, F9/ENGINE-05's org-type half). No other action, branch, or
   `enrollmentCriteria` block touched.
3. **PUT while disabled** — accepted (200); re-GET showed the new `staticValue`s live.
4. **Enable, then validate on disposables** — a `ZZ-SCORING-TEST-DELETE-ME-*` company with
   `lv_org_type=regulator` reached `org_type_score=5` (settled ~4-6s after the PATCH that
   set `lv_org_type`, property-history `sourceType: AUTOMATION_PLATFORM` confirmed on a
   dedicated debug run); a second with `lv_org_type=gambling_operator` reached
   `org_type_score=0`. Both disposables deleted (204) in the same run.
5. **Confirmed enabled** — final re-GET: `isEnabled: true`.

**Deviation from the plan's literal step order (Rule 1 — correctness fix):** the task body
lists "validate on disposables" (step 4) before "re-enable" (step 5), but a *disabled* flow
does not fire on property-change events — validating against a disabled flow would prove
nothing. The actual sequence run was disable -> edit+PUT(disabled) -> **enable** -> validate
on disposables (now genuinely live) -> confirm still enabled. This is the only ordering
under which "validate on disposables" can produce a real signal; the disabled window (during
steps 1-3) still fully satisfies D-07's intent (no half-fixed flow ever fires on a real
record while the edit itself is in flight).

**Operational findings for 40-04/40-05/40-06 (not previously documented):**
- **Optimistic concurrency**: every successful PUT bumps `revisionId`. A second PUT built
  from a stale local body (e.g. the original `.before.json` re-read after an earlier PUT
  already landed) 400s with `INVALID_REVISION_ID_IN_PUT_REQUEST`. Always re-fetch fresh
  (`fetch_hubspot_flow.fetch_flow()`) immediately before building each subsequent edit in a
  multi-PUT sequence, never reuse an already-PUTted snapshot.
- **Enrollment requires a genuine property-change event**, not a value present at row
  creation. Setting `lv_org_type=regulator` in the same `POST` that creates the company did
  **not** enroll the flow (org_type_score stayed at its `PROPERTY_DEFAULT_VALUE` of `0` for
  the full 120s poll window in two separate attempts). Creating with a neutral value
  (`lv_org_type=unknown`) and then `PATCH`ing to the target value in a second call reliably
  enrolls it — this matches `scripts/probe_scoring_recalc_latency.py`'s existing
  create-then-flip pattern; every disposable-validation script in this phase should follow
  it, not create-with-target-value-already-set.
- **A brief post-`isEnabled:true` activation lag was observed once**: the very first
  validation attempt immediately after re-enabling saw no change within 120s; a debug run
  several minutes later against the same live flow settled in ~4s. Not reproduced a third
  time and not confirmed as a real HubSpot platform behavior vs. this session's own
  sequencing — flagged as an open risk for 40-04/40-05/40-06 to budget slack around their
  first disposable check after any `isEnabled:true` PUT, rather than treating a single
  120s no-fire as conclusive.

**Conclusion for 40-04/40-05/40-06:** the API-only path (D-05) is viable for this portal's
`STATIC_BRANCH` action-content edits (branch-target `staticValue` mutation). The portal-UI
fallback was not needed for this edit shape. Pitfall 2's open risk — whether `IS_BETWEEN`
revenue-boundary edits (needed for F10's revenue-branch fix in 40-05) are equally
API-editable — remains genuinely open; this verdict covers `STATIC_BRANCH`/static-value
edits only. 40-05 should still treat its first `IS_BETWEEN` edit as its own early
validation gate, not assume this verdict extends to it.
