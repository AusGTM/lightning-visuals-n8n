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

## Plan 05 — geography/revenue retarget and the D-01 veto handover completion

**Precondition confirmed before Task 1 started:** `VETO-WRITE-EVIDENCE.md` (2026-08-06/07)
live-proves both WINDOWS.md #2 and #3 resolved — a real HubSpot PATCH landed
`lv_anti_icp_flag="true"` via the scheduled-arm companion, independently re-verified, and
the write window was disarmed afterward. `STATE.md`'s blocker text predating that evidence
is now stale (the blocker itself is cleared, not the note describing it).

### Task 1 — Geography flow (4626722240) retargeted, veto branch deleted

Enrollment moved from native `country` (`HAS_COMPLETED`) to `lv_country_region_normalized`
known. The branch action stayed `LIST_BRANCH` type (an attempted `LIST_BRANCH` ->
`STATIC_BRANCH` conversion 400'd — see the API-limit note below); only its filter content
changed, to a single `MULTISTRING IS_EQUAL_TO` branch matching exactly `["AU", "NZ",
"ANZ"]` -> `geography_score=10`, default (`Other`/`Unknown`/empty/absent) -> `0`. The old
veto action (`lv_anti_icp_flag="true"` on the default path) is gone from the actions array
entirely — confirmed by a live re-GET (`written props: {'geography_score'}`, no other
property) and by `tests/test_flow_rubric_conformance.py::test_no_archived_flow_writes_veto_properties`.

Live-validated on disposables (all deleted 204): `AU` -> `geography_score=10`,
`lv_anti_icp_flag` stayed `null` (not `"true"` — the F4 regression case); `NZ` -> `10`;
`ANZ` -> `10`; `US` -> `0`; a disposable with only native `country="Australia"` set stayed
at `geography_score=0`, confirming the trigger moved off the native property.

Final `GET /automation/v4/flows/4626722240`: `isEnabled=true`, `revisionId=13`.

### Task 2 — Annual Revenue flow (4626722237) retargeted, nine exact bands

Enrollment moved from native `annualrevenue` to `lv_revenue_band` known. The five
`NUMBER_RANGED IS_BETWEEN` branches (F10's inclusive-overlap defect) are replaced by nine
`MULTISTRING IS_EQUAL_TO` branches, one per rubric band exactly: `<1M` 0, `1-5M` 0, `5-50M`
10, `50-500M` 10, `500-750M` -5, `750M-1B` -15, `1B-1.2B` -30, `1.2B+` -50, `unknown` 0.
Numeric range matching is now structurally impossible on this flow (string equality has no
overlap), and the boundary contract lives entirely upstream in
`src/normalizer.normalize_revenue_band` (unchanged; already correct — 750000000 already
banded to `"750M-1B"` before this plan).

Final `GET /automation/v4/flows/4626722237`: `isEnabled=true`, `revisionId=22`.

**Two API-limit findings, live-discovered this plan (not previously documented):**

1. **`LIST_BRANCH` -> `STATIC_BRANCH` action-type conversion 400s.** Both flows were
   originally `LIST_BRANCH`; the plan's own text anticipated a `STATIC_BRANCH`-shaped
   retarget (mirroring the org-type-score flow), but a direct PUT converting action 1's
   `type` field failed with an opaque `FLOW_UPDATE_BAD_REQUEST` on both flows. Resolution:
   kept the action type `LIST_BRANCH`, and used its filter mechanism (`MULTISTRING
   IS_EQUAL_TO` with an exact value list, one value per branch on the revenue flow, three
   values in one branch on the geography flow) to get exact-match semantics without a
   type conversion. This stays fully within the API-only D-05/D-08 path — no portal-UI
   fallback was needed for either flow, resolving Task 2's flagged A1 risk without
   invoking D-05's fallback clause.
2. **A flow's PUT rejects any `actionId` that existed in an earlier revision of that same
   flow but is absent from the current PUT body**, even if the id is not referenced by
   anything else in the payload and even with unique per-branch targets and no orphans.
   Action ids are apparently tracked server-side across a flow's revision history, not
   just validated within the current request. Every revenue-flow target action in the
   shipped 9-band edit uses a fresh id (`101`-`110`) never previously used by that flow,
   to avoid the collision. This explains several intermediate 400s during isolation
   testing that initially looked like duplicate-target or branch-count limits; those
   turned out not to be real constraints once fresh ids were used.

### Task 3 — veto ownership handover confirmed, stale-flag population measured

**Checkpoint auto-resolved per operator pre-approval (2026-08-07)**, citing
`VETO-WRITE-EVIDENCE.md` as the satisfied handover precondition (veto-write path
live-validated, WINDOWS.md #2/#3 resolved). Per the pre-approval, this plan performed the
read-only stale-flag measurement the checkpoint calls for and did **not** perform the
checkpoint's step 4 (refreshing one real company through the operator path) — that
real-record mutation is explicitly replaced by the measurement under the pre-approval.

**Portal-wide veto-writer scan (code):** `tests/test_flow_rubric_conformance.py`'s
`test_no_archived_flow_writes_veto_properties` passes for every archived `.after.json`
under `config/hubspot_flows/` — zero flows write `lv_anti_icp_flag` or
`lv_anti_icp_reason`. Both retargeted flows (4626722240, 4626722237) confirmed enabled
with their canonical triggers via live `GET` (above).

**Stale-flag population, measured 2026-08-07 (read-only `POST
/crm/v3/objects/companies/search`, portal 22617666):**

| Query | Result |
|---|---|
| `lv_anti_icp_flag` `EQ` `"true"` | **0** |
| `lv_anti_icp_flag` `HAS_PROPERTY` (any value at all, true or false) | **0** |
| `lv_anti_icp_flag` `EQ` `"true"` AND `lv_country_region_normalized` `IN` `["AU","NZ","ANZ"]` (the F4-contradicted subset) | **0** |
| Total companies (sanity check, `name` `HAS_PROPERTY`) | 711 |

**Interpretation:** the accepted D-02 stale population is **zero**, not "unknown" as
40-CONTEXT.md's original framing anticipated. This is consistent with 40-03-SUMMARY.md's
finding that `ALLOW_HUBSPOT_RECORD_WRITES` was baked `"false"` in every build prior to the
one exception in `VETO-WRITE-EVIDENCE.md` (a single disposable company, since deleted) — no
real company in this portal has ever had the veto branch actually fire and land a write.
The old Geography flow's veto branch existed and was live-enabled for the whole phase, but
nothing in this portal's write history ever exercised it against a real record. There is
no F4-contradicted subset to refresh, and no backlog for Phase 41's backfill to inherit on
this specific field — D-02's acceptance is trivially satisfied (there is nothing stale to
accept).

## Plan 06 Task 1 — `lv_icp_tier` enum option added

Re-confirmed live (`GET /crm/v3/properties/companies/lv_icp_tier`, 2026-08-07): `Unscored`
was still **absent**, matching 40-01's original read verbatim — only `A`, `B`, `C`, `D`.

`PATCH /crm/v3/properties/companies/lv_icp_tier` sent with the full existing four-option
array plus one new option (`value`/`label` both `Unscored`, `displayOrder: 4`, continuing
the existing 0-3 sequence, `hidden: false`) — the complete array, not a partial diff, per
the plan's own warning that a partial options PATCH replaces rather than appends. `200` on
the first attempt. Snapshots: `config/hubspot_flows/lv_icp_tier-property.before.json` /
`.after.json`. The after-snapshot's options list confirms `A`, `B`, `C`, `D` survived
verbatim (unchanged label/displayOrder) alongside the new fifth option.

**Live validation:** a disposable `ZZ-SCORING-TEST-DELETE-ME-*` company (id `280246734318`)
had `lv_icp_tier` directly `PATCH`ed to `"Unscored"` and read back as exactly `"Unscored"`,
not empty — the enum change took. Deleted (204) immediately after.

No `Needs Review` option was added (per the plan's explicit prohibition — no HubSpot
workflow in this phase writes it, and REQUIREMENTS.md defers the review-queue policy).

Task 2 (WF1's retarget/rebranch to actually write `Unscored`) is cleared to proceed.

## Plan 06 Task 2 — WF1 (4625147345) retargeted and rebranched

**Went through the API — no portal-UI fallback needed.** Followed D-07's corrected
protocol (PORTAL-FACTS.md's own note above): fetch fresh -> disable+edit in one PUT ->
re-GET confirms disabled -> re-enable via a second PUT -> re-GET confirms enabled ->
validate live on disposables (now genuinely live) -> archive `.after.json`.

Three changes to the archived body, diffed and confirmed minimal (no branch dropped,
T-40-03):

1. **Enrollment** — a second `eventFilterBranches` entry added, identical shape to the
   existing `lv_icp_fit_score` HAS_COMPLETED trigger but filtered on `hs_name =
   "lv_anti_icp_flag"` (the same pattern 40-04's `createdate` second-trigger used).
   `shouldReEnroll` was already `true`. No D-05 portal-UI fallback needed — the API
   accepted a second enrollment criterion on the first PUT.
2. **Veto branch filter (action 2)** — `operationType` changed `BOOL` -> `STRING`,
   `value` changed the JSON boolean `true` -> the string `"true"`, per D-04 (the
   pipeline writes the flag as a quoted string; HubSpot EQ filters compare strings).
   Live-discovered this portal's actual `lv_anti_icp_flag` property is `type: bool`,
   `fieldType: booleancheckbox` with options `value: "true"`/`"false"` (both strings)
   — consistent with a STRING filter comparison being the correct match, not BOOL.
3. **Fall-through branch (action 7, the `<15` branch)** — `staticValue` changed `"D"`
   -> `"Unscored"` (F8/D-03/ENGINE-07). No other branch, action, or `nextActionId`
   touched — the score ladder's structure (>=70/40-69/15-39/<15) and the veto branch's
   structure are otherwise byte-identical to `.before.json`.

Diff against `.before.json`: exactly the three changes above (`+43 -15 ~6` lines,
entirely accounted for by the enrollment-branch addition, the one filter-operation
replacement, and the one staticValue edit) — no branch, action, or `nextActionId`
dropped.

**Live validation, all on disposable `ZZ-SCORING-TEST-DELETE-ME-*` companies (all
deleted 204 in a `finally` block), composing `lv_icp_fit_score` through its five
writable component properties (the calculated property itself can't be set
directly):**

| Component total | `lv_icp_fit_score` | `lv_icp_tier` |
|---|---|---|
| 70 | 70 | A |
| 69 | 69 | B |
| 40 | 40 | B |
| 39 | 39 | C |
| 15 | 15 | C |
| 14 | 14 | **Unscored** |
| -20 (gambling-only deduction, no veto input set) | -20 | **Unscored** (not D — the exact F8 regression case) |

VETO-03 flag-flip, both directions, on one disposable at a fixed B-band total (org 20 +
geo 10 + rev 10 = 40): `lv_anti_icp_flag="true"` -> tier D within settle time,
`lv_icp_fit_score` unchanged (40 before and after); `lv_anti_icp_flag="false"` -> tier
restored to B, `lv_icp_fit_score` still 40. Score never moved either direction — the
flag alone drove the tier both ways.

Final `GET /automation/v4/flows/4625147345`: `isEnabled=true`, `revisionId=22`. All six
company scoring flows (four original + 40-04's two) confirmed `isEnabled=true` on a
final live GET sweep. No `ZZ-SCORING-TEST-DELETE-ME-*` company survived any validation
run in this task.

Live parity selectors named in the plan's Task 2 acceptance criteria
(`RUN_LIVE_PARITY=true pytest tests/test_scoring_parity.py -k "f8_sub15 or
tier_on_flag_change or f7"`) — all 3 pass, unmodified (40-02 had already written
`test_f8_sub15_no_veto_is_unscored` and `test_tier_on_flag_change_without_score_change`
against exactly this shape; `test_f7_tier_lag` is that same test's named alias).

## Plan 07 Task 2 — real-record backfill sample, measured population

**Portfolio-wide canonical-input population, measured live (read-only `HAS_PROPERTY`
search per field, 2026-08-07):** across all 711 companies, exactly **one** carries any
canonical `lv_*` scoring input at all — `lv_produces_content`, `lv_revenue_band`,
`lv_is_gambling_operator` and `lv_is_hardware_vendor` are populated on **zero** real
companies, `lv_org_type` and `lv_country_region_normalized` on **one** (the same record).
This is the expected shape given enrichment writes have been disarmed for essentially the
whole portal history (STATE.md's `ALLOW_HUBSPOT_RECORD_WRITES` note) — Phase 41's
portfolio enrichment is what populates the other 710.

That one record — **Melbourne Racing Club, id `9604614548`** — is the entire real-record
sample this plan's backfill script (`scripts/backfill_seed_company_scores.py`) selects by
default (union of `HAS_PROPERTY` across the five canonical inputs, per D-10's "at least
one populated" selection rule) and the entire sample Task 3's PARITY-01 verdict checks,
per D-09's stated overlap. Before this plan: `lv_org_type=individual_club_team`,
`lv_country_region_normalized=AU`, all five components null, `lv_icp_fit_score=""`
(blank, not 0 — the calculated formula blanks on any null term, per Task 1's earlier
finding). Seeded components: `org_type_score=5`, `geography_score=10`,
`annual_revenue_score=0`, `produces_content_score=0`, `gambling_score=0` (sum 15).
Settled live within ~11s: `lv_icp_fit_score=15`, `lv_icp_tier=C`, `lv_anti_icp_flag`
stayed `null` (never written — no HubSpot workflow writes it post-D-01, and this backfill
run never triggered a pipeline enrollment). No veto fired (produces_content is `null`, not
`false` — the no-content veto only fires on an explicit `false`).

This record's `lv_produces_content` being `null` (unknown, not enriched) puts it squarely
in the oracle's documented `Needs Review` divergence (compute_icp_score downgrades tier
when `lv_org_type` is known but `lv_produces_content` is null and no veto fired) — Task 3
classifies this as the accepted divergence 40-02 flagged, not a defect.

## 40-REVIEW.md WR-02 — WF1 score-ladder action `"3"` has no `defaultBranch` (known, documented edge)

Confirmed by direct read of `config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json`:
action `"2"` (veto check) has a top-level `defaultBranch` key; action `"3"` (the four-way
score ladder, `>=70`/`[40,69]`/`[15,39]`/`<15`) does not. `extract_wf1_score_ladder()` in
`tests/test_flow_rubric_conformance.py` treats the `<15` `listBranches` entry as filling a
"default" role in its own return value, but that is this repo's test-side convenience
label, not HubSpot's actual `defaultBranch` fallback — a genuinely blank
`lv_icp_fit_score` reaching action `3` matches none of the four `IS_GREATER_THAN_OR_EQUAL_
TO`/`IS_BETWEEN`/`IS_LESS_THAN` filters (all require a value) and, with no `defaultBranch`
to fall through to, action `3` writes nothing that pass.

**Why this is a live, reachable state, not just a theoretical one:** WF1 enrolls on
either `lv_anti_icp_flag` OR `lv_icp_fit_score` becoming known
(`test_wf1_enrollment_includes_score_and_veto_flag`), and the n8n pipeline writes
`lv_anti_icp_flag`/`lv_anti_icp_reason` in the same PATCH as the canonical scoring inputs
while the five component-score mapper flows the calculated `lv_icp_fit_score` formula
depends on are separate, asynchronously-triggered flows that can still be settling. A
company enrolled on the flag-known trigger before all five components have landed falls
through action `2`'s `defaultBranch` into action `3` with a blank score.

**Why this is not being live-PUT-fixed in this remediation pass:** the state is
self-correcting — once the five components settle and `lv_icp_fit_score` itself becomes
known, WF1 re-enrolls (`shouldReEnroll: true`) and re-evaluates with a real number, so no
company is left with a stale/wrong tier, only a transient one-pass no-op. This sandbox
also has no live HubSpot credentials available (`HUBSPOT_PRIVATE_APP_TOKEN` unset), so a
D-07 disable-edit-PUT-reenable round-trip cannot be executed or validated on disposables
here — attempting one blind would violate D-07's own "validate live before trusting it"
discipline. Honest deferral: this edge is now machine-documented
(`test_wf1_score_ladder_action_has_no_default_branch_documented_race` in
`tests/test_flow_rubric_conformance.py`) so a future change to this action's shape is a
deliberate, reviewed diff against a named assertion, not a silent regression — and the
live fix (add a `defaultBranch` on action `3` routing to a no-op terminal, or verify the
self-correction empirically on disposables) stays open as a Phase 41+ follow-up, tracked
here rather than attempted without credentials.
