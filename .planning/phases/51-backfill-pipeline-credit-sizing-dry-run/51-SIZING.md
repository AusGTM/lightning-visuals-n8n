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

**CORRECTION (operator checkpoint round 2, 2026-08-19):** the paragraph originally here
claimed Gold Coast's D → B was "directly attributable to the country guard." A per-record
diff of Run 1 vs Run 2 by the operator showed that claim is wrong. Corrected below.

**What changed the tier outcomes, stated plainly:**
- Gold Coast Turf Club (`9604630690`): D → **B**. The country guard fired and is real --
  `lv_country_region_normalized` now resolves `AU` (was `Other`), `row["country_conflict"]`
  records the disagreement, and it added **+10 geography points (25 → 35)**. That alone
  is NOT sufficient to clear the no-content hard veto (D is forced whenever
  `lv_produces_content` is false, regardless of score). What actually lifted the tier is
  `lv_produces_content` flipping `false` (Run 1) → `true` (Run 2) on the SAME company
  across two live Claude web research calls -- the same run-to-run variance documented
  below for Warwick, not a code change. The guard and the content flip are both real and
  both present on this record; only the content flip moved the tier.
- Warwick Turf Club (`9604732796`): D → **B**. NOT attributable to the guard or the
  diversification rule -- this company was also research-filled in Run 1 and scored D
  there (`lv_produces_content: false`, no YouTube evidence found). Run 2's live Claude
  web research call returned `lv_produces_content: true` with a YouTube evidence URL this
  time. This is genuine run-to-run variance in the live research call for the SAME
  company, not a code change -- disclosed here rather than presented as a diversification
  win.
- Both records moving on the same field is not a coincidence: `lv_produces_content` is a
  20-point base-score component AND the sole trigger of the no-content hard veto -- the
  single highest-leverage field in the ICP rubric (CLAUDE.md SS10.1). This run-to-run
  instability is why the operator held the gate a second time and required a measurement
  of the underlying research call's reproducibility before any further tier claims are
  trusted -- see `51-RESEARCH-REPRODUCIBILITY.json` and the "Research reproducibility"
  section below.

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
tune the selection until it produces a Tier A"): this run initially appeared to produce two
Tier B outcomes, so the selection was not re-tuned further this session -- **but the
Research reproducibility section below shows both B's rest on a minority draw of an
unstable field and revert to D under the majority-of-5-observations answer.** A real Tier
A/B org type (governing body, league, broadcaster) has NOT been genuinely observed in this
population's first page under either rule. Flagged for Phase 52.

Live-observed `industry` distribution over the never-scored population's first 100 rows
(read this session, for context): `Amusement Parks, Arcades & Attractions` (26), `SPORTS`
(16), `GAMBLING_CASINOS` (15), blank (9), `Hospitality` (5), `SPORTING_GOODS` (4),
`BROADCAST_MEDIA` (4), `ENTERTAINMENT` (3), `Broadcasting` (3), and 13 other single-count
values.

## Research reproducibility (operator ruling, checkpoint round 2, 2026-08-19)

**Why this section exists.** The Run 2 diff above states Gold Coast's and Warwick's D -> B
moves trace to `lv_produces_content` flipping across two live research calls on the same
company, not to the country guard. That raised the obvious next question: how often does
this happen, and does it change anything else? Two live measurements answer it, both via
`scripts/measure_research_reproducibility.py`
(`.planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-RESEARCH-REPRODUCIBILITY.json`),
zero ZoomInfo cost throughout (HubSpot-search-only company selection; no `enrich_company()`
call anywhere in that tool).

**"Before" -- raw `claude_web_research()`, all 8 matched Run 2 companies x 3 repetitions =
24 calls:**

| Field | Companies flipped / 8 |
|---|---|
| `lv_org_type` | 0 |
| `lv_produces_content` | 3 (Warwick, Gold Coast, Ipswich) |
| `lv_is_hardware_vendor` | 3 (Warwick, Clare Valley, Bairnsdale) |
| `lv_is_gambling_operator` | 5 (Warwick, Clare Valley, Bairnsdale, Shoalhaven, Ipswich) |

Only Mudgee Race Club and Tasmanian Turf Club showed zero flips on every field.

**Root cause tested and exonerated, not assumed.** The operator's own lead pointed at
`config/field_policy.yaml`'s `min_confidence`/`require_evidence_url(_for)` gates
(CLAUDE.md SS9.2) as the strongest candidate. Checked directly against the "before" data:
**every single `lv_produces_content` flip observation (all 3 flipped companies, all 3
repetitions each) already carries confidence >=85 and a cited evidence URL** -- i.e.
already clears the gate that was missing from `scripts/backfill_dry_run.py` before this
session. The gate fix (commit `e622e53`) is real, correct, and now shipped -- it stops a
genuinely low-confidence or uncited guess from being promoted -- but it provably cannot be
the fix for `lv_produces_content` reproducibility, because nothing in the observed flip set
was ever a low-confidence guess. On `lv_is_hardware_vendor`/`lv_is_gambling_operator` the
flip pattern is different again: almost every flip is `False`-with-evidence on one call
versus `None`/no-answer on another (never a wrongly-promoted high-confidence `True`) --
`None` was never eligible for promotion regardless of confidence, so the gate has
essentially no observable effect on those flips either. State this precisely rather than
rounding up to "the gate filters noise": in this measurement, the gate changed zero of the
observed flip outcomes.

**The fix: majority-of-3 vote, not temperature.** `claude-sonnet-5` (this project's
`ANTHROPIC_RESEARCH_MODEL` default) rejects any explicit `temperature` parameter with a
400 -- confirmed via the claude-api skill's model migration notes. Deterministic decoding
is not an available lever on this model; a later reader should not "simplify" this fix back
to a temperature setting, because that setting cannot be applied to this model at all.
`research_with_majority_vote()` (commit `e622e53`) instead issues
`RESEARCH_VOTE_REPETITIONS=3` live calls and folds them into one answer per
`GAP_FILL_FIELDS` name by majority; ties/all-abstain resolve to absent, never a defaulted
`False`.

**"After" -- `research_with_majority_vote()`, 4 of 8 companies x 3 repetitions = 36 raw
calls (9 raw calls/company: one company per invocation, respecting
`MAX_WEB_RESEARCH_PER_RUN=10`).** A first attempt at all 8 companies was backgrounded and
was killed by a session boundary partway through company 3 of 8; two companies' results
(Warwick, Mudgee) survived and were kept rather than re-spent. The remaining budget was
capped at the two other companies whose "before" flip touched the tier-relevant
`lv_produces_content` field (Gold Coast, Ipswich), run in the foreground one at a time so a
dropped session could not silently strand the run again. **This is 4 of 8 companies, NOT a
like-for-like sweep of the same population as "before" -- the two rates below are shown
over their own denominators, never blended into one percentage:**

| Field | Companies flipped / 4 (targeted) |
|---|---|
| `lv_org_type` | 0 |
| `lv_produces_content` | 1 (Gold Coast) |
| `lv_is_hardware_vendor` | 1 (Mudgee) |
| `lv_is_gambling_operator` | 3 (Mudgee, Gold Coast, Ipswich) |

**Correction to the selection rationale I was given:** the instruction to skip Shoalhaven,
Tasmanian, Clare Valley and Bairnsdale stated they "showed no flips before the fix." Checked
against the actual before-measurement data: only Mudgee and Tasmanian were genuinely
zero-flip. Clare Valley, Bairnsdale and Shoalhaven DID flip before the fix (on
`lv_is_hardware_vendor`/`lv_is_gambling_operator` only, never `lv_produces_content`). The
decision to leave those 3 unmeasured is still correct under the same cost cap (their flips
are the score-inert None-vs-False pattern described above, on non-tier-relevant fields,
lower priority than the two remaining `lv_produces_content` flippers that were measured) --
only the stated reason was wrong, and is corrected here rather than repeated.

**Per-company detail:**
- **Warwick Turf Club** -- 0 of 4 fields flipped across 3 wrapper-level repetitions.
  Majority-of-3 fully stabilized this company, which was flipping on 3 of 4 fields before
  the fix.
- **Mudgee Race Club** -- 0 flips before the fix; after re-measurement shows
  `lv_is_hardware_vendor`/`lv_is_gambling_operator` flipping `False`/`None`/`False` -- the
  same score-inert evidence-presence pattern seen elsewhere, not a new regression, and not
  score-relevant (see `graduated_deductions` note below).
- **Gold Coast Turf Club -- majority vote did NOT fully stabilize this company.**
  `lv_produces_content` across 3 wrapper-level repetitions: `False`, `True`, `True` -- still
  2 distinct values, `flipped: true`. This specific draw's own majority (2 True, 1 False)
  matches the committed Run 2 `True`/Tier-B value, but is not guaranteed reproducible on a
  different draw -- and per the minority-draw finding below, the accumulated evidence across
  all runs actually leans the other way.
- **Ipswich Turf Club** -- `lv_produces_content` is now stable `False` across all 3
  repetitions (the fix worked here: before-measurement had 2 False/1 True).
  `lv_is_gambling_operator` still flips `True`/`False`/`False`, evidence cited on every
  observation -- see Ipswich note below.

**The minority-draw finding -- the headline, not a footnote.** Both Gold Coast Turf Club
and Warwick Turf Club read `lv_produces_content: False` on 3 of the 5 total observations
collected across this phase (Run 1 + Run 2 + the 3 "before" repetitions):

| Company | Run 1 | Run 2 (committed) | Before-rep 1 | Before-rep 2 | Before-rep 3 | Majority |
|---|---|---|---|---|---|---|
| Gold Coast Turf Club | False | **True** | False | True | False | **False (3/5)** |
| Warwick Turf Club | False | **True** | True | False | False | **False (3/5)** |

**The committed `51-DRYRUN-PREDICTIONS.json` Tier B rows for both companies rest on the
minority answer.** Under the majority of those 5 observations, both companies'
`lv_produces_content` resolves to `False`, the no-content hard veto fires, and both revert
to Tier D. Warwick's independent 3-repetition majority-vote re-measurement agrees with this
(stable `False`). Gold Coast's re-measurement does not yet agree (2-of-3 `True` in this
specific draw) -- a genuinely unresolved case, disclosed as such, not smoothed over. **No
Tier A or Tier B record has been genuinely, reproducibly observed anywhere in this
population.** The earlier framing (this document's own Run 2 section, and
`51-03-SUMMARY.md`) that the diversified re-run "found a Tier B" does not survive this
measurement and is corrected here.

**Regenerate or not -- operator decision, not made here.** The committed Run 2 predictions
were produced by single-call research; at least these 2 of 8 matched rows are now known to
rest on an unstable field. Options:
- **Regenerate `51-DRYRUN-PREDICTIONS.json` under `research_with_majority_vote()`** before
  Phase 52 reads it: 8 companies x `RESEARCH_VOTE_REPETITIONS=3` = 24 additional live calls,
  zero additional ZoomInfo credits (same already-matched companies). Produces a predictions
  artifact whose research-derived fields are majority-voted rather than single-draw --
  though Gold Coast's own case above shows majority-of-3 is a large improvement, not a
  guarantee, for a company sitting near a genuine split.
- **Leave Run 2 as committed** and let Phase 52 read predictions two of whose rows are now
  documented as resting on a minority/unstable answer -- cheaper (0 further calls) but ships
  a known-unreliable Tier B classification into the next phase's write path unless Phase 52
  re-derives it itself.

**Ipswich Turf Club's `lv_is_gambling_operator`** flips `True`/`False`/`False` in BOTH the
before-measurement and the after (majority-vote) re-measurement -- every observation carries
a cited evidence URL and passes the confidence gate in every case, so this is a genuine,
persistent model disagreement, not a low-confidence guess, and majority-of-3 reduces but
does not guarantee resolving it (a different 3-call draw could still split 2-1 the other
way). This is score-inert TODAY only because `graduated_deductions` is `{}` in
`config/icp_scoring.yaml` since Phase 46 D-03 -- gambling-operator status currently has zero
effect on `lv_icp_fit_score`/`lv_icp_tier`. A future rubric change that reactivates that
deduction would make this instability live and score-relevant; flagged for whoever next
edits `graduated_deductions`.

**Running totals, phase-to-date (actual, not projected):** 13 ZoomInfo credits (1 tracer +
10 Run 1 + 2 Run 2, live balance deltas). Anthropic research calls: 16 (Run 1 + Run 2 dry
runs) + 24 (before-measurement) + 36 (after-measurement, capped at 4 of 8 companies per
operator cost-discipline ruling) = **76 calls**. The phase's originally sized research
budget was <=12 calls for the dry-run sample itself; this reproducibility investigation
(triggered by the checkpoint hold, not part of the original sizing) added 60 calls on top
of that, disclosed here in full rather than absorbed silently into `research_calls_made`.

## Assumptions (labelled)

- **A1 (retired):** the ZoomInfo per-match cost is now measured live by the Phase 51 Plan 01 tracer (100 hundredths-of-a-credit/match), not the previously inferred pre-v3 1.08 credits/match figure. This sizing uses the LARGER of that measured figure and the documented CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK=108, so a zero or free-cached measurement can never produce an unbounded cap.
- **A2 (still open):** the Anthropic research-cost estimate ($0.0686/record, ~6860 hundredths-of-a-US-cent per projected research call) is a **prior-pipeline estimate, NOT measured for this call pattern** -- it was measured under a combined n8n Haiku-research plus Sonnet-judge pipeline, which this milestone's design does not use (no judge/validator step at all). Treat it as a rough estimate, not a precise per-record cost.
