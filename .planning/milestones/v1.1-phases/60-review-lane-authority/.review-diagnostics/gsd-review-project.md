# lv-n8n-poc

## What This Is

A local-first Python MVP that proves Lightning Visuals' HubSpot → n8n waterfall
enrichment + ICP scoring system before any production wiring. It scores companies
against a governing-body-first ICP rubric using mock ZoomInfo/Apollo/Lusha adapters,
mock Claude web research, a Haiku→Sonnet LLM cascade, and a non-clobber merge policy —
emitting dry-run HubSpot PATCH payloads. It is internal RevOps tooling for LV's sales
team, not a customer-facing product.

## Current State (as of 2026-08-30)

**In flight: v1.1 — Unattended Session Runs (phases 53–61).** Complete: 53, 54, 58, 59, 61.
Absorbed into 61 by operator decision D-61-08: 55 (async run) and 56 (unattended pair pipeline).
Open: **Phase 57 — the next phase** (ceilings, refusal-before-start, post-run proof) and Phase 60
(review-lane authority). Phase 61 closed 2026-08-30 with 6/6 plans and 12/12 verification; all
five cloud workflows are deployed and bounced but were exercised by **disarmed** runs only.
**The first live unattended, credit-spending batch has NOT run — it is gated on Phase 57.**
Detail: `.planning/ROADMAP.md`, `.planning/milestones/v1.1-ROADMAP.md`.

**v1.0 Direct Backfill & Scoring Coverage is paused:** Phase 51 complete, **Phase 52 deferred by
the operator 2026-08-25** in favour of v1.1. The v1.0 requirements are the root
`.planning/REQUIREMENTS.md`; v1.1's live in `.planning/milestones/v1.1-REQUIREMENTS.md`.

### Prior state (as of 2026-08-19), retained

**Shipped: v0.9 — ICP Rubric Calibration & Veto Remediation.** 6 phases, 35 plans, 18
requirements, all verified `passed`. Archived at `.planning/milestones/v0.9-ROADMAP.md`.

The ICP tier is no longer written by a workflow. `lv_icp_tier_derived` is a HubSpot calculated
property computed server-side from `lv_icp_fit_score` and `lv_anti_icp_flag_num`, both written
by the n8n pipeline as plain numerics. There is no property-change event anywhere in the path,
which is what retired the stale-tier bug class rather than its instances. The old `lv_icp_tier`
enum is archived and the workflow that wrote it (`4625147345`) is deleted.

Load-bearing constraint discovered this milestone, worth carrying forward: HubSpot's
`calculation_equation` reads **only numeric properties** — booleans evaluate as null even when
set, enumerations are rejected at create. Anything a formula needs must be written as a number
first. And calculated values backfill ~70–130s after their inputs change, so a read issued
immediately after a write returns null for a property that will compute correctly.

**Next milestone — v1.0 Direct Backfill & Scoring Coverage.** Backfill the ~646 never-scored
companies with ZoomInfo firmographics plus targeted research, in-session, writing the scoring
inputs and the six numeric properties HubSpot's calculation engine reads. No n8n executions — the
operator has no credits for it, and none are needed: HubSpot already derives score and tier from
those six numbers on its own. Decisions in `.planning/MILESTONE-CONTEXT.md`.


## Shipped Milestone: v0.9 ICP Rubric Calibration & Veto Remediation (2026-08-19)

*(Was headed "Current Milestone" — corrected 2026-08-30; v0.9 shipped, the current milestone is
v1.1. The goal/feature text below is the v0.9 record as written at the time.)*

**Goal:** The ICP rubric reflects who Lightning Visuals actually wins, and every scored company
carries a score derived from that rubric rather than from a stale or false one.

**Target features:**
- **Rubric recalibration** — resolve whether `individual_club_team: 5` inverts GTM priority.
  Racing clubs cap at tier C (35–45) while governing bodies reach tier A (80) on org_type alone.
  If clubs are the core market the weighting is backwards. This is the question that triggered
  the blank-region investigation and is still unanswered.
- **Veto remediation** — clear the 17 false non-ANZ vetoes. The code fix is deployed, bounced and
  live-proven; the records need a deliberate armed write window, because SJ-3 correctly declined
  to dispatch through a closed gate and self-drained their flags.
- **Enrichment coverage** — 18 of 66 scored companies have no `lv_org_type` at all. The rubric
  cannot outperform its inputs, so coverage is a scoring-quality ceiling, not a separate concern.
- **Weight validation against outcomes** — the revenue-band deductions (−5 at 500–750M, −50 at
  1.2B+) and the gambling −20 were set by judgement and have never been checked against won/lost
  deals.
- **Loss-reason capture** — start filling `lv_closed_lost_reason` (exists on Deals, 0% filled
  across 59 examined closed-lost deals). This is the evidence that makes future recalibration
  empirical rather than intuitive.
- **Re-score strategy** — with no `lv_icp_scoring_version`, any rubric change implies re-scoring
  the whole population. Plan that against the 2,500/month execution budget deliberately.

**Key context:**
- The pipeline is **disarmed at rest** — `ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`
  and `ALLOW_HUBSPOT_REVIEW_WRITES` are baked `"false"` in the deployed workflow. No re-score of
  any kind lands until a window is opened deliberately. Every write item in this milestone
