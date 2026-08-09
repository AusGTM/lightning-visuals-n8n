# Finding: Phase 40's "80/A live-proven" claim is stale (MRC, id 9604614548)

**Found:** 2026-08-08, during Phase 41 canary verification.
**Severity:** documentation-correctness, not a live defect. No data was lost.

## What STATE.md claims

Phase 40 (40-07) records ENGINE-01 as "live-proven (80/A entirely inside HubSpot off
canonical inputs — org_type_score=40, produces_content_score=20, geography_score=10,
annual_revenue_score=10, gambling_score=0)" on Melbourne Racing Club.

## What is actually live

| Field | Phase 40 claim | Before 41 canary | After 41 canary |
|---|---|---|---|
| `lv_org_type` | governing_body_league (implied by score 40) | individual_club_team | individual_club_team |
| `org_type_score` | 40 | 5 | 5 |
| `lv_produces_content` | true (implied by score 20) | None | None |
| `produces_content_score` | 20 | 0 | 0 |
| `geography_score` | 10 | 10 | 10 |
| `lv_revenue_band` | — | None | **50-500M** |
| `annual_revenue_score` | 10 | **0** | **10** |
| `lv_icp_fit_score` | 80 | 15 | **25** |
| `lv_icp_tier` | A | C | C |

`hs_lastmodifieddate` before the Phase 41 canary was 2026-08-06T22:23:53Z — inside Phase
40's own veto evidence run, not Phase 41.

## Reading

1. **The drift predates Phase 41.** MRC was already 15/C before the canary queued. Phase 41
   did not cause it.
2. **The canary improved the record, 15 -> 25.** The F1 native firmographic fold derived
   `lv_revenue_band` = 50-500M from the record's own `annualrevenue` (206,078,000), restoring
   the +10 that Phase 40 had recorded but which was no longer live. The non-clobber test
   case passed: no previously-set canonical value was overwritten or cleared by the fold.
3. **`individual_club_team` is factually correct.** MRC operates Caulfield, Mornington and
   Sandown racecourses — it is a racing club, not a governing body (that is Racing Victoria).
   June's independent research agrees: `Team/Club`, high confidence, with evidence. The
   original `governing_body_league` was a misclassification, and `docs/business/icp-scoring.md`
   explicitly treats clubs-as-direct-target as anti-ICP.
4. **ENGINE-01's engine proof still stands; its headline number does not.** The arithmetic
   Phase 40 demonstrated (40+20+10+10+0=80) was correct given its inputs. The inputs were
   wrong. The engine was never the problem — which is consistent with everything else Phase
   40 proved.

## Consequence

- STATE.md's "80/A live-proven" line should not be quoted as current live state.
- `lv_produces_content` is blank on MRC despite June asserting `produces_broadcast_or_streaming_content: true`
  with two evidence URLs at confidence 85. It did not promote, and the record sits at
  `needs_review`. Whether that is the evidence gate behaving correctly or a promotion defect
  is UNRESOLVED — the canary only completed 2 of its 5 records, so there is not enough
  evidence to tell. This is the first thing the resumed canary should settle.
- Portal-wide: only 1 of 712 companies carries any live ICP score (43-04's finding). The
  population is effectively unscored until the June import completes.
