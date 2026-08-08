# Spike verdict: HubSpot `calculation_equation` null-safety

**Task #1. Date:** 2026-08-08. **Portal:** 22617666.
**Verdict: INCONCLUSIVE on the viability of a null-safe formula — but the grammar is now
known, and one candidate is a strong lead.**

## What is definitively established

**The formula grammar is enumerable, and the API tells you it.** Rejected candidates return
a 400 listing valid tokens verbatim:

```
Unable to parse calculation formula in line 1 and column N -
*, -, round_down, round_up, round_nearest, is_present, number_to_st…
```

Confirmed **rejected** (400, unparseable): `if(...)`, `ifnull(...)`, `is_known(...)`.
Confirmed **accepted** (200): `coalesce(...)`, `(gambling_score + 0)`.

**`is_present` exists.** It appears in the API's own token list and was never tested. It is
the most likely purpose-built null guard in this grammar and is the obvious next candidate.

**The live formula is unchanged.** Verified by direct read after the run:
`org_type_score + geography_score + annual_revenue_score + produces_content_score + gambling_score`.
No disposable companies leaked (live search returns 0). Schema snapshotted beforehand as
`portal-schema-companies-pre-formula-spike.json`.

## Why the result is inconclusive rather than positive

The first run reported `zero-add` as VIABLE. **That result should not be trusted**, because
the test never actually created a null-term state:

- The disposable was created with four components set, and read back `60` rather than blank
  — the defect did not reproduce. HubSpot's `PROPERTY_DEFAULT_VALUE` stamps 0 on newly
  created records (Phase 40, PORTAL-FACTS.md), so `gambling_score` was **defaulted to 0, not
  null**. Every candidate was therefore measured against a record that already had all five
  terms present.
- `60` also does not reconcile with the 40+10+10+20 that was written, which points to stale
  reads at an 8-second settle. Calculated-property recomputation after a *formula* change
  appears to need substantially longer.

A confounded positive is worse than no result: adopting a formula on this evidence could
ship a silent mis-scoring across the portfolio.

The corrected re-run (clear all components after creation to defeat the default stamp,
25-second settles, verify component values at each step) hit a transient **401** partway
through and could not complete. The 401 also made its own restore check meaningless — it
compared two failed reads — which is why the formula was independently re-verified
afterwards.

## What a conclusive re-run needs

1. Create the disposable, then **explicitly clear all five components** and confirm the
   score reads blank before testing anything. Do not assume a fresh record has null terms.
2. **Settle ≥25s** after a formula change, and re-read until stable rather than sleeping a
   fixed interval.
3. Test **`is_present`** first — most likely to be the intended null guard.
4. Verify each accepted formula on **both** cases: null term (want 80) and all five terms
   present (want 60). Accepting a formula that stops blanking but computes wrong is the
   failure mode to guard against.
5. Space the PATCHes — the rapid formula-edit cycle appears to have triggered the 401.

Roughly 20–30 minutes, and it is genuinely worth finishing: if `is_present` or
`(term + 0)` holds up, it is a **one-property change that eliminates the failure mode for
every record, forever** — strictly better than any after-the-fact seeding.

## Bearing on the options

- **Option 1 (null-safe formula):** not ruled out, and better positioned than before —
  `coalesce` and `(x + 0)` both parse, and `is_present` is untested. Still unproven.
- **Option 2 (scheduled backfill):** unaffected. Remains the option that works regardless of
  how the formula question resolves.
- **Option 4 (detector):** unaffected, and this spike reinforces it — the confounded first
  run is exactly the kind of plausible-looking false green a detector is meant to catch.

## Artifacts

- `spike_null_safe_formula.py` — first run; keep for the grammar evidence, but its VIABLE
  verdict is superseded by this document.
- `41-formula-spike-results.json` — raw per-candidate results, including verbatim 400 bodies.
- `config/hubspot_migration/baseline/portal-schema-companies-pre-formula-spike.json`.
