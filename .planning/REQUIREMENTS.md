# Requirements — v1.0 Direct Backfill & Scoring Coverage

**Defined:** 2026-08-19. Source: `.planning/MILESTONE-CONTEXT.md` (operator decisions D-01..D-06).

> **Scope note, 2026-08-30 — this file is v1.0's, and only v1.0's.** The active milestone is
> **v1.1 Unattended Session Runs**, whose requirements live in
> `.planning/milestones/v1.1-REQUIREMENTS.md`. Nothing from v1.1 (GRANT-*, RUN-*, AFTER-*,
> INPUT-*, VOCAB-*, SUGGEST-*) is tracked here, and closures from v1.1 phases must never be
> recorded in this file.
>
> **v1.0's own status:** Phase 51 complete; **Phase 52 deferred by the operator 2026-08-25** in
> favour of v1.1, so FILL-02 and SAFE-02/03/04 are deferred rather than merely "not started". The
> `.planning/ROADMAP.md` § Phase 52 entry carries the resume conditions and the gate.

Scope: backfill the ~646 never-scored HubSpot companies with ZoomInfo firmographics plus targeted
research, writing the inputs and the six numeric properties HubSpot's calculation engine needs, so
those records acquire a real `lv_icp_fit_score` and `lv_icp_tier_derived`. Executed in-session —
**zero n8n executions** — because the operator has no n8n credits for it.

## Backfill Coverage (FILL)

- [x] **FILL-01**: The run is sized to the ZoomInfo credit balance BEFORE it starts. The balance is
      queried live, the population is capped to what it actually supports, and the cap is recorded.
      Discovering exhaustion partway through a run is a failure of this requirement, not bad luck.

- [ ] **FILL-02**: Never-scored companies that ZoomInfo can match acquire their scoring inputs
      (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`, `lv_revenue_band`,
      `lv_is_gambling_operator`, `lv_is_hardware_vendor`) plus the six numeric properties the
      calculation engine reads (`org_type_score`, `geography_score`, `annual_revenue_score`,
      `produces_content_score`, `gambling_score`, `lv_anti_icp_flag_num`). The six numbers come
      from `src/icp_scoring.py` — the existing oracle — never a reimplementation.

- [x] **FILL-03**: ZoomInfo revenue is converted from THOUSANDS to dollars before banding, pinned
      by a test. Raw pass-through puts every company one band too low and inverts the scoring; this
      is a known landmine from prior provider work, not a hypothetical.

- [x] **FILL-04**: Research is used only to fill specific fields ZoomInfo cannot answer, on records
      ZoomInfo already matched. A record ZoomInfo cannot match is **skipped and logged unenriched**,
      never rescued by whole-record research (operator: too expensive) and never scored on guessed
      data. "Not yet enriched" stays distinguishable from "enriched and genuinely low-fit".

## Evidence and Safety (SAFE)

- [x] **SAFE-01**: A dry run over the sample produces every exact PATCH payload for review, and
      commits a **pre-registered prediction artifact** naming each record's expected
      `lv_icp_tier_derived` BEFORE any live write. Post-write reads are compared against it, so a
      surprising tier is a defect — bad provider value or wrong normalisation — not a result
      narrated afterwards.

- [ ] **SAFE-02**: Execution is staged 1 → 5 → 25 → chunked remainder, with an operator gate at
      each boundary and a checkpoint between remainder batches. Every stage writes inside a
      deliberately armed, record-scoped window and disarms afterwards with the disarmed state read
      back and confirmed, under the Phase 47-50 discipline.

- [ ] **SAFE-03**: No write occurs before explicit operator approval of the dry run. Tier values
      are confirmed by **polling** (calculated properties backfill ~70-130s); a single immediate
      read-back is not evidence and has already produced one wrong decision in this project.

- [ ] **SAFE-04**: The 66 already-scored companies are not touched. The committed D-07 parity
      evidence and Phase 49's settled tiers must still hold after the backfill, re-verified at the
      end rather than assumed.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FILL-01 | Phase 51 | Complete |
| FILL-02 | Phase 52 | Deferred (operator, 2026-08-25) |
| FILL-03 | Phase 51 | Complete |
| FILL-04 | Phase 51 | Complete |
| SAFE-01 | Phase 51 | Complete |
| SAFE-02 | Phase 52 | Deferred (operator, 2026-08-25) |
| SAFE-03 | Phase 52 | Deferred (operator, 2026-08-25) |
| SAFE-04 | Phase 52 | Deferred (operator, 2026-08-25) |

## Out of Scope

- **n8n execution of any kind.** The entire premise is that n8n credits are unavailable. Any design
  requiring an n8n run fails the milestone's core constraint.

- **The 66 already-scored companies** (SAFE-04).
- **Contacts.** Companies only.
- **Rubric weight changes.** The rubric settled in Phase 46 is applied as-is; this milestone changes
  coverage, not scoring.

## Carried forward, still deferred

- **EVID-01/02/03** (outcome evidence: closed-lost reasons, testing revenue/gambling deductions
  against won-lost outcomes, the three CLAUDE.md §5.3 fields) were earmarked "v1.0" when deferred
  from v0.9 on 2026-08-11. They are **not** this milestone — the operator's stated next goal is
  backfill coverage. Re-earmarked to the milestone after this one. Flagged rather than silently
  re-labelled, since the v0.9 archive names v1.0 as their destination.

- **WINDOWS.md ids 17 and 18** — stale `lv_icp_tier` readers. Fixable, and they block `/gsd-ship`
  while open.

- **Nyquist NOT-VALIDATED** across all v0.9 phases (`VALIDATION.md` files still `status: draft`).
