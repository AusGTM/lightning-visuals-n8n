# Phase 51 Sizing -- Credit Balance, Population and Sample Cap

**Run at (UTC):** 2026-08-19T03:23:31.069355+00:00
**Verified portal id:** 22617666

## Figures

| Figure | Value |
|---|---|
| Population total (`NOT_HAS_PROPERTY(lv_icp_fit_score)` company search, live) | 646 |
| ZoomInfo credit balance (live, `users/usage`) | 9396 |
| Credits per match, hundredths (measured, floored at fallback) | 108 |
| Credit cap | 8700 |
| Sample size (chosen) | 10 |
| Credits projected for sample | 11 |
| Research calls projected (bounded by MAX_WEB_RESEARCH_PER_RUN) | 10 |
| Anthropic research-cost estimate (hundredths of a US cent) | 6860 |

## Credit arithmetic

`credit_cap = (credit_balance * 100) // credits_per_match_hundredths = (9396 * 100) // 108 = 8700`

The Phase 51 Plan 01 tracer already spent **1** ZoomInfo credit on one live `companies/enrich` call. This sample is projected to spend **11** more, for a phase total of **12** credits -- inside the 8700-credit cap.

## Relationship to the already-scored population (Plan 03)

`51-BEFORE-SNAPSHOT.json` (Plan 03, captured 2026-08-19) recorded **66** already-scored
companies via `HAS_PROPERTY(lv_icp_fit_score)`. This sizing document's population figure
above (**646**, `NOT_HAS_PROPERTY(lv_icp_fit_score)`) is the complementary set. The two
populations are disjoint by construction — a company either has the fit score or does not,
never both — and 66 + 646 = 712, matching this portal's total company count independently
confirmed by prior phases (`scripts/check_tier_derived_parity.py::_count_total_companies`).
Stating both counts together here makes an accidental overlap between the two populations
visible immediately, rather than something that would only surface as a silent double-write
in Phase 52.

## Assumptions (labelled)

- **A1 (retired):** the ZoomInfo per-match cost is now measured live by the Phase 51 Plan 01 tracer (100 hundredths-of-a-credit/match), not the previously inferred pre-v3 1.08 credits/match figure. This sizing uses the LARGER of that measured figure and the documented CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK=108, so a zero or free-cached measurement can never produce an unbounded cap.
- **A2 (still open):** the Anthropic research-cost estimate ($0.0686/record, ~6860 hundredths-of-a-US-cent per projected research call) is a **prior-pipeline estimate, NOT measured for this call pattern** -- it was measured under a combined n8n Haiku-research plus Sonnet-judge pipeline, which this milestone's design does not use (no judge/validator step at all). Treat it as a rough estimate, not a precise per-record cost.
