# Task #3 — null-safe `lv_icp_fit_score` + blank-score detector (options 1 + 4)

**Date:** 2026-08-08. **Portal:** 22617666. **Status: APPLIED AND VERIFIED LIVE.**

Operator selected **option 1 + option 4**, and — after the blast-radius check below —
the **four-guarded / bare-`org_type_score`** variant of option 1.

## The defect

`lv_icp_fit_score` is a `calculation_equation`. HubSpot blanks the result entirely when any
one referenced term is null. `gambling_score` is null on ~95% of companies (research
correctly answers null without a citing source), so the bare five-term sum left **63 of 66
records with no score at all** through a full phase, and the parity sweep still reported
PASS — because it only ever sampled records that already had a score.

## What was applied

```
org_type_score
+ coalesce(geography_score, 0)
+ coalesce(annual_revenue_score, 0)
+ coalesce(produces_content_score, 0)
+ coalesce(gambling_score, 0)
```

**`org_type_score` is unguarded on purpose.** It is the sentinel for "this record has been
through the pipeline": the org-type mapper writes it for every enriched company (`unknown`
maps to 0 in the rubric, so it is never skipped), while `gambling_score` is the term
research legitimately leaves null.

Blast-radius check that produced this variant — guarding all five would have scored the
**646 never-enriched companies as `0`**, and the tier flow keys off `lv_icp_fit_score`
changing, so all 646 would have enrolled and been written a tier. Blank must keep meaning
"never scored".

| | before | after |
|---|---|---|
| companies in portal | 712 | 712 |
| have `lv_icp_fit_score` | 66 | **66** |
| have `org_type_score` | 66 | 66 |
| have inputs but blank score | 0 | **0** |

## Live verification

`verify_null_safe_formula.py` → `41-null-safe-formula-verification.json`. **PASS.**

- Sentinel holds: still 66 scored of 712, not 712 of 712.
- Disposable, all five components cleared → score **blank** (unscored still means unscored).
- Disposable, four of five with `gambling_score` null → score **80** (the defect is fixed;
  it read blank before).
- Disposable deleted; 0 leaked `ZZ-SCORING-TEST-DELETE-ME-*` companies.

Live parity sweep after the change: **PASS, 67 assertions, 0 real findings**, 2 documented
Needs-Review divergences (the accepted 40-02 oracle-vs-live-enum case).
Report: `post-formula-fix/parity-report-20260808.json`.

## Option 4 — the detector

`scripts/run_scoring_parity.py::_find_blank_score_with_inputs()` searches the complement of
the comparison sample: `org_type_score` HAS_PROPERTY **and** `lv_icp_fit_score`
NOT_HAS_PROPERTY. That set is empty under a working formula; anything in it is a real
finding, never a documented divergence.

This closes the structural hole, not just the one instance. `_select_sample_ids()` searches
`HAS_PROPERTY` on `lv_icp_fit_score`, so a blank-scored company was **invisible to the
entire harness** — which is exactly how 63 records shipped as apparent success. The detector
also counts as one executed assertion, so a clean detector run is not mistaken by the
false-green guard for a run that checked nothing.

## Guard against recurrence

- `tests/test_flow_rubric_conformance.py::test_fit_score_formula_guards_every_nullable_component`
  — fails if any `coalesce()` guard is dropped. **Proven to fail on revert** (reverted the
  archive to the bare sum, ran the test, watched it fail, restored).
- `...::test_fit_score_formula_leaves_org_type_score_unguarded_as_the_sentinel` — fails if
  someone "completes" the fix by guarding the fifth term, which would enroll all 646.
- `tests/test_scoring_parity.py` — four offline tests covering the detector: findings are
  real, a clean run counts as an assertion, a run where the detector never ran still fails
  the zero-assertion guard, and detector findings stay out of the "N of M sampled" numerator.

`scripts/apply_fit_score_formula.py` pushes the archived formula to the portal behind
`ALLOW_FORMULA_WRITE=true` (dry-run by default), so the repo archive is the source of truth
and portal drift is one command to correct.

## Suites

2427 pytest / 636 node, all passing.

## Still outstanding (unrelated, needs the operator's shell)

`.env` has `HUBSPOT_PORTAL_ID='!'`, so the standing scheduled drift guard refuses on every
invocation (manual runs work with an inline override, which is how everything above was
run). Fix:

```
! sed -i '' "s/^HUBSPOT_PORTAL_ID=.*/HUBSPOT_PORTAL_ID='22617666'/" .env
```
