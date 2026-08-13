# Phase 50 Plan 06 Task 03: Mirror Backfill + Formula Correction Window (D-16, D-20, D-21, D-22)

**This is the phase's ONE authorised company-write deviation.** D-16 declared zero
company write windows for this phase; the write below is a disclosed, justified
exception, not a budgeted allowance.

## Authorisation

Checkpoint (Task 50-06-02) resolved: **`backfill-scoped`**, authorised by the operator
against the exact id list `50-MIRROR-SCOPE.md` enumerated (6 companies, live-derived
`lv_anti_icp_flag EQ "true"` search, run 2026-08-13T23:08:24Z):

| Record ID | Name |
|---|---|
| 15274105699 | Supertech Electronics |
| 16047156820 | Queensland Racing Integrity Commission |
| 17317850381 | Jam TV |
| 17791151956 | Big Screen Video |
| 17861423879 | Sportsbet |
| 18047161864 | Simtech LED |

Scope, as authorised: **one property only** (`lv_anti_icp_flag_num`), value `1`, copied
from `lv_anti_icp_flag` (already `true` on all 6). No canonical field, no score, no tier,
no status, no record outside this list. `backfill-plus-recompute` was explicitly NOT
selected -- no pipeline recompute, n8n execution, or re-enrichment was triggered on these
records by this task.

## Step 1 -- disarmed `--plan`, id-list confirmation

```
$ .venv/bin/python -c "...; sys.argv=['backfill_anti_icp_flag_num.py','--plan']; ..."
{
  "mode": "plan",
  "ids": ["15274105699","16047156820","17317850381","17791151956","17861423879","18047161864"],
  "count": 6,
  "max_backfill_records": 10,
  ...
}
DISARMED -- no write performed.
```

The live-derived `--plan` id list matches the checkpoint-authorised list **exactly** (6
of 6, same ids, same order). This is the authoritative pre-write check -- compared
against the operator's checkpoint message, not merely against the committed
`50-MIRROR-SCOPE.md` snapshot.

## Step 2 -- armed `--execute`

```
$ DRY_RUN=false ALLOW_ANTI_ICP_MIRROR_BACKFILL=true .venv/bin/python -c "...; sys.argv=['backfill_anti_icp_flag_num.py','--execute']; ..."
```

Every PATCH body carried exactly one key (`lv_anti_icp_flag_num`), enforced by
`assert_payload_scope()` before the batch call was made. One `batch_update_companies`
call (HTTP 200) wrote all 6 records in a single request.

**Independent per-record re-read verification** (never from the PATCH response body):

| Record ID | `lv_anti_icp_flag_num` (re-read) | Result |
|---|---|---|
| 15274105699 | `'1'` | ok |
| 16047156820 | `'1'` | ok |
| 17317850381 | `'1'` | ok |
| 17791151956 | `'1'` | ok |
| 17861423879 | `'1'` | ok |
| 18047161864 | `'1'` | ok |

All 6/6 confirmed. This is the only company write of any kind performed by this plan.

## Step 3 -- corrected formula pushed live

`scripts/apply_fit_score_formula.py --property lv_icp_tier_derived`:

- Dry run confirmed the exact diff: archived (submitted literal, uncoalesced score,
  numeric-mirror veto guard) vs. live (previous coalesced/boolean-guard formula).
- Armed run (`ALLOW_FORMULA_WRITE=true`): `PATCH 200`. Independent re-read reported
  `verified by re-read: False` -- **expected**, not a failure: HubSpot canonicalizes
  stored formula text (`=` -> `equals`, double quotes -> single quotes, inserted line
  breaks), per 50-01-SUMMARY.md's disclosed finding. The live text after the PATCH:
  ```
  if coalesce(lv_anti_icp_flag_num, 0) equals 1 then 'D'
  elseif lv_icp_fit_score >= 70 then 'A'
  elseif lv_icp_fit_score >= 40 then 'B'
  elseif lv_icp_fit_score >= 15 then 'C' else 'Unscored'
  ```
- `config/hubspot_flows/lv_icp_tier_derived-property.after.json` refreshed from this live
  read-back (full property document, `_assert_no_secrets` applied before writing).
- Re-run of `apply_fit_score_formula.py --property lv_icp_tier_derived` against the
  refreshed archive: `in sync -- nothing to do.` **Exit 0.**

## Step 4 -- D-22 polling (never a single read)

Applying the formula PATCH triggers a portal-wide recompute. Every verdict below is taken
from a poll, not an immediate read-back.

### Simtech LED `18047161864` (backfilled, vetoed) -- must settle to `D`

Polled every 10s from 09:20:35 to 09:21:38 (local), reading `lv_icp_tier_derived`,
`lv_anti_icp_flag`, `lv_anti_icp_flag_num` on every pass:

| Time | `lv_anti_icp_flag_num` | `lv_icp_tier_derived` |
|---|---|---|
| 09:20:35 | `'1'` | `B` |
| 09:20:46 | `'1'` | `B` |
| 09:20:56 | `'1'` | `B` |
| 09:21:06 | `'1'` | `B` |
| 09:21:17 | `'1'` | `B` |
| 09:21:27 | `'1'` | `B` |
| 09:21:38 | `'1'` | **`D`** |

**Settled to `D` after 7 polls (~63s of polling against a ~120s recompute-propagation
window measured from the PATCH's own `hs_lastmodifieddate` update).** This is the
end-to-end proof: mirror written -> formula corrected -> the derived tier this record
reads is now the correct hard exclusion.

### Rockhampton Jockey Club `9604732795` (a `match` row, D-21 regression control) -- must still read `B`

Polled twice, 11s apart, using the two-consecutive-identical-reads settle rule
(`rescore_population.py::_settle_one`'s idiom):

| Time | `lv_icp_fit_score` | `lv_icp_tier_derived` |
|---|---|---|
| 09:21:48 | `55` | `B` |
| 09:21:59 | `55` | `B` |

Settled at `B`, unchanged. **Proves the D-21 uncoalesce did not disturb a scored
record.**

### Newcastle Jockey Club `9604773165` (never-scored, D-21 un-flip control) -- must read blank, not `"Unscored"`

Picked from the live `NOT_HAS_PROPERTY(lv_icp_fit_score)` search (total: **646**,
matching 50-01's sizing). Polled every 15s for ~190s (>= the 3-minute D-22 ceiling), not
a single read:

| Time | `lv_icp_fit_score` | `lv_icp_tier_derived` |
|---|---|---|
| 09:22:04 | `''` (blank) | `''` (blank) |
| 09:22:20 | `''` | `''` |
| 09:22:35 | `''` | `''` |
| 09:22:50 | `''` | `''` |
| 09:23:06 | `''` | `''` |
| 09:23:21 | `''` | `''` |
| 09:23:37 | `''` | `''` |
| 09:23:52 | `''` | `''` |
| 09:24:07 | `''` | `''` |
| 09:24:23 | `''` | `''` |
| 09:24:38 | `''` | `''` |
| 09:24:54 | `''` | `''` |
| 09:25:09 | `''` | `''` |

HubSpot's GET returns an empty string for an unset property (not omitted, not the
literal word "null") -- `lv_icp_tier_derived` reads blank throughout every one of 13
reads spanning ~185s, at no point reading the literal label `"Unscored"`. **This is
D-21's un-flip, confirmed by a sustained poll, not a race-prone single read** (the exact
process defect D-22 exists to close, per 50-CONTEXT.md's amendment).

## Summary

- Company writes this plan performed: **6**, all to the checkpoint-authorised id list,
  all a single property (`lv_anti_icp_flag_num`), all verified by independent re-read.
- Formula correction: live, verified in-sync by an independent script re-run (exit 0).
- D-22 polling proof: 1 record settled to a new value (`D`), 1 record confirmed
  unchanged (`B`), 1 record confirmed to stay blank (not `"Unscored"`) across a 190s
  window.
- `50-NULL-PROBE.json`: byte-unaltered by this task (confirmed via `git diff`).
