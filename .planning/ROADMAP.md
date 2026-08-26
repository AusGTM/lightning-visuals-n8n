# Roadmap: HubSpot Enrichment + ICP Scoring

## Milestones

- ✅ **v0.3** — archived (`milestones/v0.3-ROADMAP.md`)
- ✅ **v0.4 Reachability & Verification Debt** (shipped 2026-07-29)
- ✅ **v0.5** — shipped (no MILESTONES.md entry; see Ledger gaps below)
- ✅ **v0.6 Claude Plugin Entrypoint** — Phases 23–32, workstream `plugin-entrypoint` (shipped 2026-08-04)
- ✅ **v0.7 HubSpot Scoring Engine Remediation** — Phases 39–43 (shipped 2026-08-08)
- ✅ **v0.8 Execution Budget Safety** — Phases 44–45 (shipped 2026-08-11)
- ✅ **v0.9 ICP Rubric Calibration & Veto Remediation** — Phases 46–50, archived (`milestones/v0.9-ROADMAP.md`, `milestones/v0.9-REQUIREMENTS.md`) (shipped 2026-08-19)
- ⏸️ **v1.0 Direct Backfill & Scoring Coverage** — Phases 51–52 (Phase 51 complete; **Phase 52 deferred by the operator 2026-08-25** in favour of v1.1)
- 🚧 **v1.1 Unattended Session Runs** — Phases 53–57 (`milestones/v1.1-ROADMAP.md`, `milestones/v1.1-REQUIREMENTS.md`)

## Phases

### 🚧 v1.0 Direct Backfill & Scoring Coverage (Phases 51–52)

Backfill the ~646 never-scored HubSpot companies with ZoomInfo firmographics plus targeted
research, in-session, writing the scoring inputs and the six numeric properties HubSpot's
calculation engine reads. Zero n8n executions — the operator has no credits for it, and none are
needed: HubSpot already derives `lv_icp_fit_score` and `lv_icp_tier_derived` from those six
numbers on its own. Decisions in `.planning/MILESTONE-CONTEXT.md`; requirements in
`.planning/REQUIREMENTS.md`.

- [x] **Phase 51: Backfill Pipeline, Credit Sizing & Dry Run** - Size the population and the
      ZoomInfo credit cap live, pin the thousands-to-dollars revenue conversion, and dry-run a
      sample's exact PATCH payloads and pre-registered tier predictions — zero writes

- [ ] **Phase 52: Staged Canary Execution & Safety Verification** — ⏸️ **DEFERRED 2026-08-25**
      (operator, in favour of v1.1 Phase 53 — the client is blocked on the write path). Write the
      credit-capped population in gated stages (1 → 5 → 25 → chunked remainder), polling every
      result against its committed prediction, and close by proving the 66 already-scored
      companies are untouched. **On resume:** re-derive Phase 51's population and credit sizing
      before planning — the dry-run artifacts were finalized 2026-08-19 and drift with every
      enrichment run — and resolve the deferred FILL-04 third-disposition question.

### 🚧 v1.1 Unattended Session Runs (Phases 53–57)

One operator grant at session start carries a batch through ingest → enrichment → HubSpot write,
unattended. Driven by a client UAT on 2026-08-25 that found three arming surfaces for one write,
a write path unreachable from the operator's own surface (`ALLOW_N8N_ARM` is a shell environment
variable), and a design that runs the provider waterfall twice per written record. Full detail:
`milestones/v1.1-ROADMAP.md`; evidence: `quick/260825-contact-company-association/UAT.md`.

- [ ] **Phase 53: Operator-openable write grant** - Replace the interactive path's
      `ALLOW_N8N_ARM` dependency with an admin-enabled capability plus an operator-opened session
      grant that is bounded, expiring and revocable — no terminal, no loss of record scoping
      — **4 plans** (`53-01` .. `53-04`), planned 2026-08-25

- [ ] **Phase 54: Single-pass armed dispatch** - A record is enriched once: no
      derive-then-rearm-then-derive-again, and the measured saving proven live before it is claimed

- [ ] **Phase 55: Async run — submit, poll, resume** - A batch stops being bounded by n8n Cloud's
      ~100s response window; run state survives a restart or fails loudly

- [ ] **Phase 56: The unattended pair pipeline** - One grant carries ingest → enrich → create →
      associate, creates included, held rows queued rather than guessed

- [ ] **Phase 57: Ceilings, refusal-before-start, and post-run proof** - A run cannot spend what
      it does not have, and proves afterwards it wrote only what it was granted

- [ ] **Phase 58: Take what the operator actually has** - Every input an operator holds
      (screenshot, paste, URL, bare name) resolves to a company the backend can act on; missing
      domains researched then confirmed before write; refusal is the last resort — promoted
      ahead of 54–57 by operator decision 2026-08-25

## Phase Details

### Phase 58: Take what the operator actually has

**Goal**: Every input an operator holds resolves to something the backend can act on, and a
refusal is the last resort rather than the first answer. Extend the contact lane's extraction
adapters (pasted text, foreign JSON, public URL, screenshots — Phase 35) to companies; when no
usable domain is present, research one and confirm it before writing (a wrong domain poisons
the dedupe anchor); never silently invent a domain — a profile URL is dropped, not passed
through. Closes INPUT-01..04. Research cost must be priced in the envelope and be declinable.
Full detail: `milestones/v1.1-ROADMAP.md` § Phase 58; decisions:
`phases/58-take-what-the-operator-actually-has/58-CONTEXT.md`.

**Requirements**: INPUT-01, INPUT-02, INPUT-03, INPUT-04

**Plans**: 3/5 plans executed

Plans:
**Wave 1**

- [x] 58-01-PLAN.md — company rows through the extraction machinery: identity config, record-type-aware validator, six source adapters (wave 1, tracer)
- [x] 58-02-PLAN.md — live spike: does a request-level propose mode reach the company decision node; operator decides the backend research node's scope (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 58-03-PLAN.md — propose/confirm/decline/correct: the domain decision lane, its envelope consumption, and the operator-facing confirm table (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 58-04-PLAN.md — the research line priced, named and declinable; backend website-seeking extension or a written INPUT-02 residual (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 58-05-PLAN.md — gap closure: native industry/country/city/employee-count written at landing; curated industry alias table superseding the Phase 31 refusal (wave 4)

### Phase 51: Backfill Pipeline, Credit Sizing & Dry Run

**Goal**: Before any HubSpot write, the operator can see the live-derived population of
never-scored companies, a ZoomInfo-credit-sized cap on how many can be attempted, and — for a
representative sample of that capped population — the exact PATCH payload and predicted
`lv_icp_tier_derived` for every record, computed entirely by reusing `src/icp_scoring.py`
(never a reimplementation), with zero n8n executions and zero live writes.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: FILL-01, FILL-03, FILL-04, SAFE-01

**Success Criteria** (what must be TRUE):

  1. The never-scored population is re-derived live (`NOT_HAS_PROPERTY(lv_icp_fit_score)`, ~646
     expected) and the count is recorded in a committed artifact — never a stale census carried
     over from `.planning/MILESTONE-CONTEXT.md`'s estimate, mirroring the D-01/Phase-48 lesson
     that a population must be re-derived, not trusted from a prior snapshot.

  2. Operator can see the live ZoomInfo credit balance, a population cap derived from it, and an
     Anthropic research-cost estimate for the gap-fill fields, all recorded in a committed
     artifact before any record is enriched. A run whose estimated cost would exceed the balance
     is capped up front — discovering exhaustion partway through a run is a failure of this
     criterion, not bad luck.

  3. A committed unit test pins that ZoomInfo GTM revenue (returned in THOUSANDS, per the landmine
     carried in from prior provider work) is converted to dollars before banding; the dry run's
     revenue-band outputs reflect that conversion, not a raw thousands pass-through that would put
     every company one band too low.

  4. Over a representative sample of the capped population, the dry run separates matched from
     unmatched records: every unmatched sample record appears in a skip log with a stated reason
     and carries no write payload of any kind — no company is scored on guessed data, and "not yet
     enriched" stays distinguishable from "enriched and genuinely low-fit."

  5. For every matched sample record, the dry run prints the exact PATCH payload — the `lv_*`
     scoring inputs (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`,
     `lv_revenue_band`, `lv_is_gambling_operator`, `lv_is_hardware_vendor`) plus the six numeric
     properties (`org_type_score`, `geography_score`, `annual_revenue_score`,
     `produces_content_score`, `gambling_score`, `lv_anti_icp_flag_num`) — alongside its
     pre-registered predicted `lv_icp_tier_derived`, all committed to an artifact before any write.

  6. A before-snapshot of the 66 already-scored companies is committed, read-only, as the SAFE-04
     baseline Phase 52 will diff against at close.

  7. Operator has explicitly approved the dry-run artifacts before Phase 52 opens any write
     window. This approval is the phase's exit gate — structurally, not as a task inside a
     write-capable phase — per the locked sequence: plan → dry run → **operator approval** →
     canary execution.

**Plans**: 3/3 plans executed

- [x] 51-01-PLAN.md — Tracer: one never-scored company, credit-gated, end-to-end dry run (ZoomInfo
      client, revenue thousands→dollars, None-safe region, four-branch tier prediction)

- [x] 51-02-PLAN.md — Gap-fill research lane, skip-log partition, credit/cost sizing artifact, and
      the pre-registered prediction artifact over the capped sample

- [x] 51-03-PLAN.md — Read-only before-snapshot of the already-scored population, API coverage
      matrix, validation contract, and the operator approval exit gate

---

### Phase 52: Staged Canary Execution & Safety Verification

**Goal**: The credit-capped population of never-scored, ZoomInfo-matched companies is written in
operator-gated stages — 1 → 5 → 25 → chunked remainder — with each record's prediction committed
before it is written and its actual tier confirmed by polling against that prediction, and the
milestone closes with proof that the 66 already-scored companies and the D-07/Phase 49 parity
evidence are unchanged.

**Depends on**: Phase 51, gated on explicit operator approval of the dry-run artifacts — no write
in this phase precedes that approval.

**Carried forward from Phase 51 (operator ruling, 2026-08-19, explicitly deferred — not an
oversight):** the FILL-04 third-disposition question is unresolved by design. Today a company
ZoomInfo matches but for which no scoring input at all could be resolved lands in the predictions
side with a mostly-empty payload — there is no separate "matched but unscoreable" disposition
distinct from "predicted" and "skipped". The operator was asked to rule on this at the Phase 51
checkpoint and explicitly declined to decide it there, directing it to be decided during Phase 52
planning instead. This phase's planner must resolve it (either confirm the current two-way
partition is sufficient or add a third disposition) before Phase 52's write path is built — do not
silently inherit Phase 51's placeholder behavior without a decision.

**Requirements**: FILL-02, SAFE-02, SAFE-03, SAFE-04

**Success Criteria** (what must be TRUE):

  1. For every stage, each record's prediction (computed by `src/icp_scoring.py`, identical to
     Phase 51's method) is appended to the prediction artifact BEFORE that record is written — no
     record is ever written before its prediction is committed.

  2. Each matched company written in this phase shows non-blank `lv_org_type`,
     `lv_produces_content`, `lv_country_region_normalized`, `lv_revenue_band`,
     `lv_is_gambling_operator`, `lv_is_hardware_vendor`, and the six numeric properties, matching
     `src/icp_scoring.py`'s computed values for that record — the observable acquisition of
     scoring inputs FILL-02 requires.

  3. Execution proceeded in exactly four stages — 1, then 5, then 25, then the chunked remainder —
     with an explicit operator gate before each stage and a checkpoint between remainder chunks;
     no stage began without a recorded operator go-ahead, and the remainder was never written as
     one ~615-record batch.

  4. Every write happened inside a deliberately armed, record-scoped window — the Python-side
     two-key gate (`DRY_RUN=false` plus a dedicated allow-key), portal-id-guarded, under the same
     discipline as `scripts/rescore_population.py`'s W1 window. This is a zero-n8n write path, so
     there is no second, n8n-side allowlist to arm alongside it (do not carry over Phase 48's
     dual-surface arming rule here). Every window was disarmed afterward, with the disarmed state
     read back and confirmed.

  5. Every written record's `lv_icp_tier_derived` was confirmed by polling (never a single
     immediate read — calculated properties backfill ~70–130s) and compared against its committed
     prediction; any mismatch is surfaced as a defect — a bad provider value or a wrong
     normalization — never narrated after the fact as an expected outcome.

  6. After the run, the 66 already-scored companies read identically to the Phase 51 before-
     snapshot, and re-running `scripts/check_tier_derived_parity.py`'s D-07 gate still passes —
     the committed parity evidence and Phase 49's settled tiers are re-verified, not assumed.

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 44. SJ-3 Dispatch Gate, Drain & Cap | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 45. Burn-Rate Alarm | v0.8 | 3/3 | Complete (verified) | 2026-08-10 |
| 46. Rubric Decision, Simulation & Engine Parity | v0.9 | 5/5 | Complete (verified) | 2026-08-11 |
| 47. Veto Remediation | v0.9 | 4/4 | Complete (verified) | 2026-08-12 |
| 47.5. Veto Recompute Path | v0.9 | 6/6 | Complete (verified) | 2026-08-12 |
| 48. Enrichment Coverage | v0.9 | 7/7 | Complete (verified) | 2026-08-13 |
| 49. Re-score Strategy & Reporting | v0.9 | 7/7 | Complete (verified) | 2026-08-13 |
| 50. Derived Tier Property | v0.9 | 6/6 | Complete (verified) | 2026-08-14 |
| 51. Backfill Pipeline, Credit Sizing & Dry Run | v1.0 | 3/3 | Complete (verified) | 2026-08-19 |
| 52. Staged Canary Execution & Safety Verification | v1.0 | 0/TBD | Not started | - |

## Ledger gaps (known)

- **v0.5 has no MILESTONES.md entry and no roadmap/phase archive.** Found during the v0.8 close
  on 2026-08-11: the ledger jumps v0.4 → v0.6 and `milestones/` holds no `v0.5-*` files, yet
  `v0.5.0` exists as a git release tag. v0.5 appears to have shipped without being run through
  `/gsd-complete-milestone`. Not reconstructed at v0.8 close (out of scope) — recorded so it is
  not mistaken for a numbering skip.

- **v0.6 has a MILESTONES.md entry but no roadmap/phase archive** under `milestones/`. Same
  likely cause, lesser impact: the narrative record survives, the phase artifacts were never
  archived under a `v0.6-*` label.
