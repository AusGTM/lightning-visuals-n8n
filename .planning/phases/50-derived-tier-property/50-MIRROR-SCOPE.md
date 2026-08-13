# Phase 50 Plan 06 Task 01: Mirror Backfill Blast Radius (D-20)

**Read-only report.** No HubSpot company record was read-modified or written by this
task or by the search below -- the property create in this same task's Step 1
(`lv_anti_icp_flag_num`) is a **portal-schema** operation (a `POST
/crm/v3/properties/companies`), not a company-record write; it touches zero company
objects. The search below is a plain `POST /crm/v3/objects/companies/search`, a read.

## Live search

`lv_anti_icp_flag EQ "true"` against the live company population, run
**2026-08-13T23:08:24.765259+00:00**, portal `22617666`. `total` and `len(results)`
agreed exactly (6 == 6) -- no pagination truncation.

**Count: 6.** This is not assumed from 50-03's evidence (which found 6 within the
66-company *scored* population) -- it is the live, authoritative result of a search
over the wider live company population with no scored-only restriction.
`docs/OPERATOR-VETO-REFRESH.md` §"Pre-existing stale flags on the 712 (F4)" warns that
an unknown subset of the wider 712 may carry a stale `lv_anti_icp_flag=true` from a
past Geography-flow bug -- this search would have surfaced any such record too, and it
did not: all 6 hits are within the known 66-scored population, and none is a novel
F4-era stale flag outside it.

## The 6 companies

| Record ID | Name | `lv_icp_tier` | `lv_icp_fit_score` | `lv_icp_tier_derived` |
|---|---|---|---|---|
| 15274105699 | Supertech Electronics | D | 10 | Unscored |
| 16047156820 | Queensland Racing Integrity Commission | D | 0 | Unscored |
| 17317850381 | Jam TV | D | 40 | B |
| 17791151956 | Big Screen Video | D | 20 | C |
| 17861423879 | Sportsbet | D | 20 | C |
| 18047161864 | Simtech LED | D | 40 | B |

Every one of the 6 currently reads a workable (or blank) tier on
`lv_icp_tier_derived` instead of the correct hard exclusion `D` -- this is
`50-TIER-PARITY-EVIDENCE.md`'s SEVERITY finding, unchanged by this task (a read-only
report never fixes anything).

## What the next checkpoint would authorise

If Task 50-06-02's checkpoint selects `backfill-scoped` or `backfill-plus-recompute`,
Task 50-06-03's backfill script will write **exactly one property**,
`lv_anti_icp_flag_num = 1`, to **exactly these 6 record ids** -- copied from
`lv_anti_icp_flag`, a property each of these 6 records already carries as `true`; not a
re-derivation, so no record's veto status can change as a *result* of the write itself.

Records whose `lv_anti_icp_flag` is `false` or unset are **deliberately NOT** in this
list and will not be written: a null mirror and a `0` mirror are indistinguishable to
the veto guard (`coalesce(lv_anti_icp_flag_num, 0) = 1` reads both as "not vetoed"), so
writing them would spend company writes for no behavioural change.

6 is below `MAX_BACKFILL_RECORDS = 10` (Task 50-06-03), so no cap refusal is expected
at execution time -- Task 03's own live re-derivation of this same search is the
authoritative gate, not this snapshot.
