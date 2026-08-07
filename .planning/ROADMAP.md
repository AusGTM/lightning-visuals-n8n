# Roadmap: v0.7 HubSpot Scoring Engine Remediation

## Overview

The ICP rubric is fully implemented twice — once correctly in `src/icp_scoring.py` (parity
oracle only, zero production callers) and once, incorrectly, as four live HubSpot workflows
created 2026-08-04 that nobody knew existed until the `automation` scope was granted
(HANDOVER-2026-08-06-icp-scoring.md §10). Ten validated defects (F1–F10) make the live engine
un-Tier-A-able, veto-asymmetric, and blind to the canonical `lv_*` inputs the pipeline actually
writes. This milestone decides where the engine lives, fixes it there, proves the fix with a
parity harness instead of eyeballing the HubSpot UI, validates it end-to-end against a real
(if small) population, and retires the superseded artifacts cleanly. Phase numbers continue the
repo's global sequence — Phase 38 was the last consumed (plugin-entrypoint workstream) — so this
milestone starts at Phase 39.

## Phases

**Phase Numbering:**

- Continues the repo's global sequence (last consumed: Phase 38). This milestone: Phase 39–42.
- Integer phases (39, 40, 41, 42): Planned milestone work.
- Decimal phases (e.g. 40.1): Reserved for urgent insertions if needed later.

- [x] **Phase 39: Path Decision & Fit-Score Verification** (completed 2026-08-06) - Operator verifies Sales Hub Pro fit-score availability in-portal and records the remediation path (fix-in-place vs lead-scoring-tool rebuild) with rationale
- [ ] **Phase 40: Scoring Engine, Veto & Parity Remediation** - The rubric scores and vetoes correctly inside HubSpot on the chosen path, with a parity harness landing alongside each fix
- [ ] **Phase 41: Validation Data Import & End-to-End Proof** - The 66 web-researched companies land as a real scoreable population and prove the engine fires automatically at small volume
- [ ] **Phase 42: Scoring Artifact Cleanup & Reconciliation** - Superseded scoring artifacts are archived (not deleted) and the property config reconciles clean against the live portal

## Phase Details

### Phase 39: Path Decision & Fit-Score Verification

**Goal**: The operator has an in-portal, evidence-backed verification of company fit-score
availability on Sales Hub Pro, and a recorded decision — fix the existing four-workflow chain
in place vs rebuild via HubSpot's native lead-scoring tool — with rationale. Every downstream
phase is path-shaped by this decision, so it must land before Phase 40 is planned.
**Depends on**: Nothing (first phase of this milestone)
**Requirements**: DECIDE-01
**Success Criteria** (what must be TRUE):

  1. Company fit-score / lead-scoring-tool availability on Sales Hub Pro is checked directly
     in-portal (Settings → Account & Billing → Products & Add-ons, then the lead scoring tool)
     and the result is recorded with evidence — not assumed from documentation.

  2. A path decision (fix-existing-workflow-chain vs lead-scoring-tool rebuild) is recorded
     with rationale in `.planning` (Key Decisions / STATE.md), and it gates how Phase 40 is
     planned.

  3. If the lead-scoring tool is unavailable on this hub tier, the fallback decision is
     explicitly recorded instead of left implicit. **Superseded by 39-CONTEXT.md D-06:** the
     pre-committed fallback is fix-the-four-workflow-chain-in-place, not custom equation
     properties (those stay rejected per HANDOVER §5).
**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 39-01-PLAN.md — Branch setup (D-09) + tracer: end-to-end availability probe with unit-tested classifiers

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 39-02-PLAN.md — Live API evidence + operator in-portal walkthrough + VERIFICATION-NOTE.md + COVERAGE.md
- [x] 39-03-PLAN.md — `delete_record()` primitive + two-key-gated disposable-company recalc-latency probe

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 39-04-PLAN.md — Decision record (D-04/latency gate skipped as moot, operator override) — 39-DECISION.md + ROADMAP/STATE pointers

**Path decision:** fix-the-four-workflow-chain-in-place — see
`.planning/phases/39-path-decision-fit-score-verification/39-DECISION.md`

### Phase 40: Scoring Engine, Veto & Parity Remediation

**Goal**: The ICP rubric executes correctly and symmetrically inside HubSpot on the path
Phase 39 selected — the ten validated defects (F1–F10) are closed — and a parity harness lands
alongside each fix, so future drift is caught by an assertion instead of another manual UI
audit. Success criteria below are path-neutral: they describe observable scoring behavior,
not which mechanism (workflow chain vs lead-scoring tool) produces it.
**Depends on**: Phase 39
**Requirements**: ENGINE-01, ENGINE-02, ENGINE-03, ENGINE-04, ENGINE-05, ENGINE-06, ENGINE-07,
VETO-01, VETO-02, VETO-03, PARITY-01, PARITY-02
**Success Criteria** (what must be TRUE):

  1. A company with `lv_org_type=governing_body_league`, `lv_produces_content=true`, region AU,
     revenue band 50-500M scores **80** and grades **A** entirely inside HubSpot — no pipeline
     scoring code — reading only the canonical `lv_country_region_normalized` /
     `lv_revenue_band` properties the pipeline actually writes, never native `country` /
     `annualrevenue`. (Today: 60/B off native inputs; F1/F2/F3.)

  2. Revenue decay lands in the rubric-correct band at exact boundary values — 750,000,000
     scores **−15**, not −5 — org-type points match `config/icp_scoring.yaml` including
     regulator = 5, and the gambling deduction (−20) is driven by `lv_is_gambling_operator`
     independent of org type and never sets the veto flag. (F5/F9/F10.)

  3. A score below 15 without a veto does not grade D — low fit and disqualify are no longer
     conflated. (F8.)

  4. All three hard vetoes (non-ANZ, no broadcast/streaming content, hardware vendor) set
     `lv_anti_icp_flag=true` AND write `lv_anti_icp_reason`; correcting the veto condition (e.g.
     restoring a company's country to Australia) clears both the flag and the reason with no
     one-way latch; and a flag change updates `lv_icp_tier` without requiring an unrelated score
     change. (F4/F6/F7.)

  5. A parity harness recomputes expected scores via `compute_icp_score` and asserts them
     against HubSpot's live scores for fixtures plus a real-record sample, with the F4/F7/F9/F10
     scratch scenarios (AU-string veto, tier lag, gambling conflation, boundary overlap) encoded
     as named regression cases — this is the standing drift guard, since every defect above was
     invisible in the HubSpot UI.
**Plans**: 7/7 plans executed — Phase 40 COMPLETE

Plans:
**Wave 1**

- [x] 40-01-PLAN.md — Tracer: flow fetch/PUT tooling, four flow definitions archived, portal facts recorded, and the org-type point table fixed end-to-end (ENGINE-05, ENGINE-06)
- [x] 40-02-PLAN.md — Parity harness: offline oracle tier, live-gated fixture tier, F4/F7/F9/F10 named regression cases, read-only sweep wrapper with a false-green guard (PARITY-01, PARITY-02)
- [x] 40-03-PLAN.md — Veto ownership onto the n8n pipeline, with the P2/P4 latent bugs closed first (VETO-01, VETO-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 40-04-PLAN.md — The two missing components: `produces_content_score` and `gambling_score` properties, mapper flows, and the five-term calculated formula (ENGINE-02, ENGINE-05)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 40-05-PLAN.md — Geography and revenue flows retargeted to canonical inputs; the HubSpot veto branch deleted (ENGINE-03, ENGINE-04)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 40-06-PLAN.md — WF1 tier ladder: sub-15 grades Unscored, and a flag change alone moves the tier (ENGINE-07, VETO-03)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 40-07-PLAN.md — Backfill mechanism proven on a capped sample, and the committed end-to-end parity verdict (ENGINE-01, PARITY-01)

### Phase 41: Validation Data Import & End-to-End Proof

**Goal**: The 66 web-researched companies (49 high-confidence) from the ICP validation analysis
land in HubSpot as a real, scoreable population at zero provider spend, and prove — at small,
reviewable volume — that the remediated engine from Phase 40 fires automatically on the write
path enrichment/import actually uses, not just on hand-constructed fixtures.
**Depends on**: Phase 40
**Requirements**: DATA-01, DATA-02
**Success Criteria** (what must be TRUE):

  1. The 66 web-researched companies land in HubSpot with `lv_*` inputs and provenance
     (source, confidence, evidence URL/summary) stamped, at zero provider spend.

  2. Imported companies score automatically on landing — no per-record manual touch — proving
     the trigger chain fires on the actual import/enrichment write path, not only when a human
     pokes a property in the UI.
**Plans**: 4 plans

Plans:
- [ ] 41-01-PLAN.md — June candidate table + three-source merge fold in the enrichment lane (offline)
- [ ] 41-02-PLAN.md — Pre-flight id resolver, provenance assertion in the parity harness, unpaired arm/disarm commands
- [ ] 41-03-PLAN.md — Deploy, arm, and drive 5 real companies end to end (live canary tracer)
- [ ] 41-04-PLAN.md — Release the rest, disarm, parity verdict and run report

### Phase 42: Scoring Artifact Cleanup & Reconciliation

**Goal**: The artifacts superseded by Phase 40's remediation are archived, not deleted, and the
property config file reconciles clean against the live portal — closing the milestone without
leaving orphaned schema behind.
**Depends on**: Phase 41
**Requirements**: CLEAN-01
**Success Criteria** (what must be TRUE):

  1. `scripts/snapshot_hubspot_schema.py` is run before any archival, and the superseded scoring
     artifacts (`org_type_score`, `geography_score`, `annual_revenue_score`, the calculated
     `lv_icp_fit_score` property, and any orphaned workflows per the chosen path) are archived,
     not deleted.

  2. `config/hubspot_properties.yaml` reconciles clean against the live portal — zero drift
     between the config file and HubSpot's actual schema.
**Plans**: TBD

### Phase 43: Pipeline Scoring Hygiene & Explainability

**Goal**: The pipeline-side residue of the 2026-08-06 scoring audit is closed — the one LIVE
defect (lv_enrichment_needs_review written as a boolean the HubSpot filters can never match),
the shared latent veto site, a producer for the score breakdown, and first consumption of the
closed-lost feedback signal. Validated evidence:
.planning/phases/40-scoring-engine-remediation-notes/PIPELINE-DEFECTS-VALIDATION.md
(P1 revenue units and P3 research-lane row loss were exercised and DISPROVEN — already fixed;
they are deliberately absent here.)
**Depends on**: Phase 40 (the parity harness PIPE-03 rides on)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04
**Success Criteria** (what must be TRUE):

  1. Every writer of lv_enrichment_needs_review in the generated JSON emits the string
     "true"/"false" — a structural test pins it (the 36-07 idiom: exactly-string, anchored
     grep, red-checked) and an EQ-filter fixture proves the filter now matches.

  2. mergeCompanies.js veto-class fields carry a non-zero min_confidence and string coercion
     at the single shared fix site; the existing dead-path test is extended to prove the
     hardening without resurrecting the path.

  3. The parity harness writes lv_icp_score_breakdown (rubric-versioned, property-limit
     truncated) for every record it checks — a challenged tier can name its components.

  4. A loss-reason report aggregates lv_closed_lost_reason against the rubric version;
     consumption only, no weight changes (REQ-signoff-gate stands).

  5. Suites green above baselines; arming grep 0; no n8n JSON hand-edits — builder only.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 39 → 40 → 41 → 42 → 43

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 39. Path Decision & Fit-Score Verification | 4/4 | Complete | 2026-08-06 |
| 40. Scoring Engine, Veto & Parity Remediation | 7/7 | Complete | 2026-08-07 |
| 41. Validation Data Import & End-to-End Proof | 0/TBD | Not started | - |
| 42. Scoring Artifact Cleanup & Reconciliation | 0/TBD | Not started | - |
