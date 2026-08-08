# Spike verdict: HubSpot `calculation_equation` null-safety

**Task #1. Date:** 2026-08-08. **Portal:** 22617666.

> **SUPERSEDED HEADLINE — see "v2 re-run" at the bottom. Final verdict: CONCLUSIVE
> POSITIVE. A null-safe formula is supported; three constructs verified viable on a record
> with a genuinely null term. Recommended string:**
> ```
> org_type_score + geography_score + annual_revenue_score + produces_content_score + coalesce(gambling_score, 0)
> ```
> The v1 material below is retained for the grammar evidence and to document the confound.

**v1 verdict (superseded): INCONCLUSIVE on the viability of a null-safe formula — but the
grammar is now known, and one candidate is a strong lead.**

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

---

# v2 re-run — CONCLUSIVE POSITIVE

**Date:** 2026-08-08. Script: `spike_null_safe_formula_v2.py`. Raw per-candidate results:
`41-formula-spike-v2-results.json`. Verbatim console log: `41-formula-spike-v2-console.log`.

## The confound is gone — proven, not assumed

v2 created the disposable **bare**, waited for the create-time stamping flow, and observed
it land: all five components read `0`, score `0`. It then cleared all five and confirmed
**score reads blank**. It then set four of five and confirmed **score still reads blank with
`gambling_score` genuinely empty** — the live defect, reproduced on demand. The run gates on
that reproduction and HALTs without it, so no candidate could be measured against a
populated record the way v1's were.

Every read returned all six properties and was re-read until the score **reconciled with the
components seen in the same GET**, with a 150s budget. No fixed-sleep result is load-bearing.

## Results

| Candidate | HTTP | Null term (want 80) | All five (want 60) | Verdict |
|---|---|---|---|---|
| `if is_present(x) then x else 0` | 200 | **80** | **60** | **VIABLE** |
| `if (is_present(x)) { x } else { 0 }` | 400 | — | — | unparseable (brace form not in grammar) |
| `is_present(x) * x` | 400 | — | — | rejected: *"Sub-expression output type: Boolean is not compatible with input type: BigDecimal"* |
| `coalesce(x, 0)` | 200 | **80** | **60** | **VIABLE** |
| `(x + 0)` | 200 | **80** | **60** | **VIABLE** |

Three constructs both stop the blanking **and** compute identically to the plain sum when
all five terms are present. Identity when populated was a hard requirement: the formula edit
is portfolio-wide while the spike runs, and all 66 live records have populated components,
so an identity-preserving candidate causes zero live drift.

## Grammar, now firmly mapped

- Statement-form conditionals **exist**: `if <bool> then <expr> else <expr>` parses.
  Function-form `if(a, b, c)` does not, which is why v1 concluded there was no conditional.
- `is_present` is a real null guard but returns **Boolean**, so it only composes inside an
  `if … then … else`, never in arithmetic.
- `ifnull`, `is_known`, and brace-delimited blocks are not in the grammar.
- The 400 body enumerates valid tokens at the failing position — it is the authoritative
  grammar reference for this portal; captured in full (untruncated, 1394 chars) in the v2
  results JSON. The complete list, for the record:

```
*, -, round_down, round_up, round_nearest, is_present, number_to_string, string_to_number,
concatenate, max, min, coalesce, contains, date, time_between, time_between_skip_weekends,
begins_with, to_lower_case, to_upper_case, has_email_reply, has_plain_text_email_reply,
extract_most_recent_email_reply_html, extract_most_recent_email_reply_text,
extract_most_recent_plain_text_reply, pipeline_probability, is_pipeline_stage_closed, month,
year, period_to_months, period_to_weeks, dated_exchange_rate, currency_decimal_places,
exchange_rate, set_contains_string, is_engagement_type, fetch_single_currency_portal_currency,
fetch_portal_home_currency, is_portal_enabled_currency, is_portal_multicurrency_enabled,
format_full_name, format_phone_number, format_searchable_phone_number, abs, sqrt, power,
string_length, substring, add_time, subtract_time, is_blank, regex_matches,
is_valid_iso_period, is_month_based_iso_period, is_day_based_iso_period, is_multiple_of,
validate_when, if, (, NOW, DECIMAL, scientific number literal, string literal, true, false,
e, TARGET, IDENTIFIER, bool, string, timestamp, +, >, <, >=, <=, =, equals, !=, or, and,
xor or then expected, EOF encountered.
```

  Note `if` **is** in the list — it is the statement form, which is why `if(a,b,c)` 400s
  while `if a then b else c` parses. `is_blank` and `validate_when` also exist and are
  untested alternatives to `is_present`; no need to explore them given three working
  constructs.

## Which string to adopt

`coalesce(gambling_score, 0)` is the recommendation: shortest, states the intent literally
("null means zero here"), and is a documented HubSpot function rather than an arithmetic
side effect. `(x + 0)` works but reads as a no-op and invites a future cleanup that silently
reintroduces the defect. The `if is_present` form is correct but verbose at five terms.

**Open design question for the operator, not settled by this spike:** whether to guard only
`gambling_score` or **all five** terms. Guarding all five makes the score robust to any
component going null, but it also changes the meaning of a fully empty record from *blank
(= "never scored")* to *`0` (= "scored zero")*. Tier flows key off the score, so that is a
semantic change, not a pure bug fix. Raised in Task #2.

## State after the run

- Live formula restored and **independently re-read**: original five-term sum. ✅
- Disposable `280328273386` deleted; a follow-up search returns **0** leaked
  `ZZ-SCORING-TEST-DELETE-ME-*` companies (the run's own trailing count of `1` was
  search-index lag against the record it had just deleted). ✅
- No real record touched at any point. Zero provider spend.
