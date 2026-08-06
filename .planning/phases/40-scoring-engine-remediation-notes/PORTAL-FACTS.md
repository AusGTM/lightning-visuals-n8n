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

## Components after 40-04

All five `lv_icp_fit_score` component properties, confirmed live (portal 22617666,
`GET /crm/v3/properties/companies/{name}`):

| name | type | fieldType | groupName | schema `defaultValue` |
|---|---|---|---|---|
| `org_type_score` | number | number | `companyinformation` | `null` |
| `geography_score` | number | number | `companyinformation` | `null` |
| `annual_revenue_score` | number | number | `companyinformation` | `null` |
| `produces_content_score` | number | number | `companyinformation` | `null` |
| `gambling_score` | number | number | `companyinformation` | `null` |

`produces_content_score` and `gambling_score` were net-new (`404` before this plan's
Task 1); both created via `POST /crm/v3/properties/companies` with a body that
byte-for-byte mirrors `org_type_score`'s `type`/`fieldType`/`groupName` (`name`,
`label`, `type: number`, `fieldType: number`, `groupName: companyinformation`).

### Default-value-generation finding (Task 1 deviation — read before touching this again)

**The `PROPERTY_DEFAULT_VALUE`/`default-value-generation` stamp `org_type_score`,
`geography_score`, and `annual_revenue_score` carry on every freshly created company is
NOT reproducible via the CRM v3 Properties API.** Live-probed this session, in order:

1. `POST /crm/v3/properties/companies` with `defaultValue: "0"` in the create body — `201`,
   but the response (and every subsequent `GET`) omits `defaultValue` entirely. A fresh
   disposable company's `propertiesWithHistory` shows an empty history list for that
   property (no `PROPERTY_DEFAULT_VALUE` entry), not `0`.
2. `PATCH /crm/v3/properties/companies/{name}` with `defaultValue: "0"` on an
   already-created property — same result: `200`, field silently dropped, no stamp.
3. `PATCH` with `numberDisplayHint: "unformatted"` (the one schema-level difference a
   full-key diff of `org_type_score` vs. the newly created properties surfaced) — `200`,
   applied, but still no stamp on a fresh disposable.

**Conclusion:** whatever produced the three original components' default-0 behavior is
either a legacy artifact of how those three were created (HANDOVER's note that a
now-removed `calculation_score`-type mechanism preceded this architecture) or a
portal-UI-only setting with no API-exposed equivalent in this API version. Confirmed
**not** an API create/update-time option for a plain `number`/`number` property in this
portal.

**Why this matters, live-verified (not theoretical):** `lv_icp_fit_score`'s
`calculation_equation` formula does not treat a missing/null referenced property as `0`
— it returns blank. Reversible spike this session: temporarily appended
`+ gambling_score` to the live formula (`gambling_score` was null on every disposable at
that point, nothing else changed), created a disposable with no properties set, and
`lv_icp_fit_score` read back `None` instead of the `0` a 3-term-only formula gives today.
Formula reverted immediately (`PATCH` back to the original 3-term string, re-confirmed
via `GET`) — no net change to the live property. **One null term blanks the entire sum.**
This is exactly the risk Task 1's own acceptance criteria flagged ("An empty component
rather than 0 would break the calculated sum in Task 3, so this check is not ceremony")
— now confirmed as a real, live-reproduced failure mode, not a hypothetical one.

**Resolution (Rule 2 auto-fix, carried into Task 2):** since the property-schema route is
unavailable via API, the default-0 write for `produces_content_score`/`gambling_score` is
achieved the same way every other write in this phase is achieved — an
Automation v4 flow, D-05/D-08's proven mechanism — rather than reaching for portal-UI
hand-editing (D-05's fallback clause exists for API-*rejected* edits; this is an
API-*unsupported schema feature*, and a flow-based equivalent stays fully within the
API-only path). Each of the two new mapper flows (Task 2) carries a **second**
`eventFilterBranches` entry enrolling on `createdate` known (the same
`eventTypeId: "4-655002"` UNIFIED_EVENTS type every other property-keyed enrollment in
this portal already uses, just filtered on `hs_name = "createdate"` instead of the
mapper's own input property), feeding into the same `STATIC_BRANCH` action. At company
creation the driving input (`lv_produces_content` / `lv_is_gambling_operator`) is unset,
so the branch falls to its existing "any other value including empty" default action,
which already writes `0` — no new action, no new branch, only a second way to enroll into
the one that exists. `shouldReEnroll: true` plus HubSpot's confirmed (40-01 D-05 verdict)
"enrollment requires a genuine future property-change event, not existing state" behavior
means this does **not** retroactively fire for any of the 712 pre-existing companies
(`createdate` was set for all of them long before this flow existed) — only future company
creations get the write. 40-07's backfill (D-10) remains the mechanism for the 712;
this closes the same gap for every company created *after* this plan lands.

## Task 2 — new mapper flows

| Flow ID | Name | Trigger property | writes | isEnabled (final GET) |
|---|---|---|---|---|
| `4634822079` | Update Produces Content Score | `lv_produces_content` known, or `createdate` known | `produces_content_score` (true->20, else->0) | `true` |
| `4634822085` | Update Gambling Score | `lv_is_gambling_operator` known, or `createdate` known | `gambling_score` (true->-20, else->0) | `true` |

Both created via `POST /automation/v4/flows` with `isEnabled: false`, validated live, then
enabled via `PUT` (re-GET confirmed `isEnabled: true` at task end). Archived at
`config/hubspot_flows/produces-content-score.after.json` /
`config/hubspot_flows/gambling-score.after.json`.

**Live validation (all on disposable `ZZ-SCORING-TEST-DELETE-ME-*` companies, all deleted
204 in a `finally` block):**
- Brand-new company, nothing set: `produces_content_score=0`, `gambling_score=0` within
  60s of creation (the `createdate`-branch fix from Task 1's finding, confirmed working).
- `lv_produces_content=true` -> `produces_content_score=20` (~5.8s); `=false` -> `0`
  (~5.8s).
- `lv_is_gambling_operator=true` -> `gambling_score=-20` (~5.9s), `lv_anti_icp_flag`
  stayed `null` (never set by this flow); `=false` -> `0` (~5.8s).
- Ordering backstop: on a fourth disposable, `lv_is_gambling_operator`,
  `lv_produces_content`, `lv_org_type` written in that reverse order — all three
  components (`gambling_score=-20`, `produces_content_score=20`, `org_type_score=40`)
  settled to the correct values regardless of write order (sampled observation per the
  must-have's backstop marker, not a guarantee).

The gambling flow's action list writes only `gambling_score` — no other action in either
flow touches any other property (verified by `tests/test_flow_rubric_conformance.py`'s
`written_property_names()` assertion, T-40-15's offline guard).

## Task 3 — lv_icp_fit_score formula extended to five terms

**Went through the API — no portal-UI fallback needed.** `PATCH
/crm/v3/properties/companies/lv_icp_fit_score` with only `calculationFormula` in the
body returned `200` on the first attempt (Pitfall 3's documented 400-error history did
not reproduce in this portal). New formula, the exact fetched 3-term string extended by
two terms, same token/operator style:

```
org_type_score + geography_score + annual_revenue_score + produces_content_score + gambling_score
```

Snapshots: `config/hubspot_flows/lv_icp_fit_score-property.before.json` /
`.after.json`. A `200` alone was not treated as proof (Pitfall 3's warning sign) — live
validation on disposables:
- A brand-new disposable with only `lv_produces_content=true` set reached
  `lv_icp_fit_score=20` in ~6s (the content term alone, isolated from the other four —
  all of which read `0` on a fresh company per Task 2's `createdate`-branch fix).
- A second disposable with the full ENGINE-01 input set
  (`lv_org_type=governing_body_league`, `lv_produces_content=true`,
  `lv_country_region_normalized=AU`, `lv_revenue_band=50-500M`) read
  `org_type_score=40`, `produces_content_score=20`, `geography_score=0`,
  `annual_revenue_score=0` (the geography/revenue flows still read native
  `country`/`annualrevenue`, unset on this disposable — 40-05's retarget, not yet done),
  `gambling_score=0`, summing to `lv_icp_fit_score=60`. Per the plan, the 80/A total is
  40-05/40-07's job, not asserted here — only the individual component values.

Both disposables deleted (204) in a `finally` block. `tests/test_flow_rubric_conformance.py`
now also asserts the archived after-formula names all five component properties
(`test_fit_score_formula_references_all_five_components`), and the flow-branch tests were
hardened with an `_is_flow()` guard so a non-flow snapshot (this property archive) in the
same glob-matched directory doesn't false-fail them.
