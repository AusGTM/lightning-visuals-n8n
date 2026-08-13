# Spike — can `lv_icp_tier` be mechanically derived from `lv_icp_fit_score`?

**Date:** 2026-08-13 · **Portal:** 22617666 · **Verdict: CONCLUSIVE POSITIVE (grammar)**

Run during Phase 49, prompted by the 4 stuck-tier records that plan 49-05 surfaced. Not part
of Phase 49's scope — this is evidence for a future phase.

---

## Why this was asked

`lv_icp_fit_score` is a `calculation_equation` property: it recomputes itself, no event
required. `lv_icp_tier` is a plain `enumeration` written **only** by workflow WF1
(`4625147345`), which is `type: EVENT_BASED` and enrolls on property-change events for
`lv_anti_icp_flag` and `lv_icp_fit_score`.

Consequence, observed live in Phase 49 W1: four companies already carried correct new-weight
components, so the re-score PATCH was value-identical, so **no property-change event fired**,
so WF1 never re-enrolled and their tier stayed stale at `C` while their score sat correctly at
`45` (tier `B`). `shouldReEnroll: true` does not help — re-enrollment still needs an event to
re-enroll *on*.

A derived tier removes the event dependency entirely and makes that failure mode unreachable.

## Two syntaxes, and why the docs mislead

HubSpot's published docs describe the **UI editor**: `if(condition, a, b)`, `[properties.name]`
bracket refs, `is_known()`, `&&`, `==`.

The **Properties API** `calculationFormula` field stores a different, statement-form grammar:

```
if boolean_expression then statement [elseif expression then statement]* [else statement]
```

Bare property names, `is_present()`, no `endif`. This is why Phase 41's spike recorded
`if(...)`, `ifnull()` and `is_known()` as 400s — it was testing the API, correctly. The live
existence proof is `hs_task_label`, whose stored formula is
`if is_present(string(name)) then string(name) else string(domain)`.

**Do not port syntax from the HubSpot docs into an API call.** They describe different surfaces.

## Method

One disposable string property (`lv_spike_tier_calc`, then `..._calc2`), created with a seed
formula, PATCHed once per candidate, archived in a `finally` block and verified gone by re-read
(404). A 400 mutates nothing and its body enumerates every valid token at the failing parse
position — that body is the authoritative grammar for this portal.

Scripts: `spike_tier_formula.py`, `spike_tier_formula2.py` (session scratchpad).
No company record was read or written. `lv_icp_tier` was never touched.

## Round 1 — 4/9

| Candidate | Result |
|---|---|
| string literal `"D"` | **200** |
| `if … then "A" else "Unscored"` | **200** |
| `if lv_icp_fit_score >= 70 then …` | **200** |
| `elseif` chain (3 branches) | **200** |
| trailing `endif` | 400 — not a token |
| `if lv_anti_icp_flag then …` | 400 — `output type: BigDecimal is not compatible with input type: Boolean` |
| `coalesce(lv_anti_icp_flag, false)` | 400 — `Boolean is not compatible with BigDecimal` |

**The finding that mattered:** a HubSpot *boolean* property arrives in formula-land as
**BigDecimal**, not Boolean. It cannot sit bare in a condition slot, and `coalesce`'s second
argument must then also be numeric — `false` fails, `0` works.

Full token list captured from the 400 body (authoritative grammar reference):

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
validate_when, if, (, NOW, DECIMAL, scientific number literal, string literal, true, false, e,
TARGET, IDENTIFIER, bool, string, timestamp, +, >, <, >=, <=, =, equals, !=, or, and, xor
```

## Round 2 — 7/7

Every veto guard worked once the flag was treated as numeric: `= 1`, `bool(...)`,
`coalesce(..., 0) = 1`, and `is_present(...) and ... = 1`. All three full ladders accepted.

**The formula, mirroring WF1's ladder exactly:**

```
if coalesce(lv_anti_icp_flag, 0) = 1 then "D"
elseif lv_icp_fit_score >= 70 then "A"
elseif lv_icp_fit_score >= 40 then "B"
elseif lv_icp_fit_score >= 15 then "C"
else "Unscored"
```

WF1's live ladder for comparison — `lv_anti_icp_flag = "true"` → `D`; else `>= 70` → `A`;
`40..69` → `B`; `15..39` → `C`; `< 15` → `Unscored`. Ordered cascade collapses the ranges to
lower bounds. Every WF1 branch carries `includeObjectsWithNoValueSet: false`.

## What is NOT yet established

1. **Runtime null propagation inside a conditional.** Phase 41 proved HubSpot blanks a
   calculated property when any referenced term is null — for a bare sum. Whether that still
   holds when the null term sits in an untaken branch is **unknown**, and it decides which
   variant ships: leaving `lv_icp_fit_score` uncoalesced preserves WF1's current
   blank-for-never-scored semantics, while `coalesce(lv_icp_fit_score, -1)` would flip ~646
   never-enriched companies from blank to `"Unscored"`. Syntax cannot answer this — it needs a
   disposable held in place and read against real records.
2. **In-place conversion.** `lv_icp_tier` is `type: enumeration`, `calculated: false`. Zero of
   264 portal properties are calculated enumerations, and HubSpot's KB states enumeration
   outputs are not supported for calculation properties. So this is a **new string property plus
   a migration**, not a formula edit on the existing one.
3. **Portal-side dependents.** Lists, views, saved filters and reports keyed on the tier
   *select* are invisible from the repo and must be enumerated before any cutover.

## Blast radius — smaller than expected

**No code writes `lv_icp_tier`.** All ~35 repo references are reads, forbidden-list guards or
tests; project D-07 already treats it as HubSpot-derived, and
`scripts/remediate_veto_companies.py:17` says so explicitly. WF1 is the sole writer, so
retiring it orphans nothing in code.

Known repo touch-points for a migration: `scripts/check_schema_drift.py:119` pins the
five-value enum; `config/hubspot_properties.yaml:408` declares it;
`config/hubspot_flows/lv_icp_tier-property.*.json` archives it. Calculated properties carry
`readOnlyValue: true`, which is a benefit — the derived tier becomes unclobberable.

## Recommendation

Worth its own phase. It fixes the four stuck records as a side effect — their score is already
correct at `45`, so a derived tier lands them on `B` with no event, no enrollment, no workflow —
and it removes the whole bug class rather than the instance.
