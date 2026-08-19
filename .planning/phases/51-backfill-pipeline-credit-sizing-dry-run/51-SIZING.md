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

## Run 2 -- diversified re-run (operator ruling, 2026-08-19)

The operator held the approval gate on Run 1's artifacts (archived as
`51-DRYRUN-PREDICTIONS-run1-ascending-id.json` / `51-SKIP-LOG-run1-ascending-id.json`) for
two reasons: (1) a HubSpot/ZoomInfo country conflict on Gold Coast Turf Club fired a
spurious non-ANZ veto (fixed by the country guard, `scripts/backfill_dry_run.py`
`build_candidate_patch`), and (2) the ascending-id sample landed entirely on one org-type
cluster with no Tier A/B observed. Run 2 re-samples with the guard in place, using the new
deterministic `select_diversified_never_scored_sample()` rule (industry-stratified, see
that function's docstring and `DIVERSIFICATION_INDUSTRIES`).

| Figure | Run 1 (archived) | Run 2 (current, `51-DRYRUN-PREDICTIONS.json`) |
|---|---|---|
| Run at (UTC) | 2026-08-19T03:26:18Z | 2026-08-19T04:23:47Z |
| ZoomInfo credit balance before | 9396 | 9390 |
| ZoomInfo credit balance after (live re-read) | ~9386 (not separately re-read) | **9388** |
| Sample selection rule | `ascending_id` | `diversified_industry_stratified` (`media_slots=5`) |
| Sample size | 10 | 10 |
| Rows / skipped | 8 / 2 | 8 / 2 |
| Research calls made | 8 | 8 |
| `credits_spent` (artifact, ceiling projection) | 10 | 10 |
| Credits actually consumed (live balance delta) | ~10 | **2** |
| Tier distribution | D×8 | **B×2, D×6** |

**Real spend was far below the projected ceiling this run** (2 credits, not the
projected 10) -- ZoomInfo's `companies/enrich` appears to cache/discount a re-enrich of a
domain already matched in Run 1 (8 of Run 2's 10 sampled ids were already enriched then).
The artifact's `credits_spent` field is a stated ceiling projection, not a live re-measurement
-- see `scripts/backfill_dry_run.py`'s own comment on that field.

**Phase running total (all three sub-phase runs):** 1 (Plan 01 tracer) + 10 (Plan 02 Run 1
sample, measured) + 2 (Plan 03 Run 2 sample, measured via live balance delta) = **13 ZoomInfo
credits spent phase-to-date**, against a credit cap in the thousands. Well inside budget.

**What changed the tier outcomes, stated plainly (not attributed to the diversification
rule alone):**
- Gold Coast Turf Club (`9604630690`): D → **B**. Directly attributable to the country
  guard -- `lv_country_region_normalized` now resolves `AU` (was `Other`), clearing the
  false non-ANZ veto. `row["country_conflict"]` records the disagreement.
- Warwick Turf Club (`9604732796`): D → **B**. NOT attributable to the guard or the
  diversification rule -- this company was also research-filled in Run 1 and scored D
  there (`lv_produces_content: false`, no YouTube evidence found). Run 2's live Claude
  web research call returned `lv_produces_content: true` with a YouTube evidence URL this
  time. This is genuine run-to-run variance in the live research call for the SAME
  company, not a code change -- disclosed here rather than presented as a diversification
  win.

**Honest finding on the diversification rule itself:** `DIVERSIFICATION_INDUSTRIES`
selected `9604726292` (Narromine Turf Club), `9604732796` (Warwick Turf Club), `9604732798`
(Mudgee Race Club), `9605259523` (Clare Valley Racing Club), `9605259524` (Bairnsdale
Racing Club) as its "media bucket" -- every one is STILL a regional Australian racing/turf
club, just tagged `SPORTS`/`ENTERTAINMENT` in HubSpot's native `industry` field instead of
`GAMBLING_CASINOS`. Native `industry` tagging on this population does **not** reliably
discriminate a governing-body/broadcaster/content-producer org type from an
individual-club-team org type -- both the media bucket and the fill bucket landed on the
same underlying population (racing clubs), just with inconsistent industry labels. No Tier
A was observed. Per the operator's own instruction ("if the diversified sample still comes
back all-Tier-D, that is a legitimate and important result -- report it as such. Do not
tune the selection until it produces a Tier A"): this run did produce two Tier B outcomes,
so the selection was not re-tuned further this session -- but the two B's trace to the
country-guard fix and live research variance, not to genuine org-type diversity in the
sample. A real Tier A/B org type (governing body, league, broadcaster) was never actually
observed in this population's first page under either rule. Flagged for Phase 52.

Live-observed `industry` distribution over the never-scored population's first 100 rows
(read this session, for context): `Amusement Parks, Arcades & Attractions` (26), `SPORTS`
(16), `GAMBLING_CASINOS` (15), blank (9), `Hospitality` (5), `SPORTING_GOODS` (4),
`BROADCAST_MEDIA` (4), `ENTERTAINMENT` (3), `Broadcasting` (3), and 13 other single-count
values.

## Assumptions (labelled)

- **A1 (retired):** the ZoomInfo per-match cost is now measured live by the Phase 51 Plan 01 tracer (100 hundredths-of-a-credit/match), not the previously inferred pre-v3 1.08 credits/match figure. This sizing uses the LARGER of that measured figure and the documented CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK=108, so a zero or free-cached measurement can never produce an unbounded cap.
- **A2 (still open):** the Anthropic research-cost estimate ($0.0686/record, ~6860 hundredths-of-a-US-cent per projected research call) is a **prior-pipeline estimate, NOT measured for this call pattern** -- it was measured under a combined n8n Haiku-research plus Sonnet-judge pipeline, which this milestone's design does not use (no judge/validator step at all). Treat it as a rough estimate, not a precise per-record cost.
