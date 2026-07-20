---
gsd_state_version: 1.0
milestone: v0.3
milestone_name: Company Enrichment & ICP Research
current_phase: 12
current_phase_name: Taxonomy Single-Source
status: planned
stopped_at: "Phase 12 planned and committed (plan-checker PASS WITH CONCERNS). PN-1..PN-5 naming convention adopted after portal audit; SJ-1..SJ-3 scheduled predicates corrected for Approach C (spec §0.7); Phase 16 (Scheduled Workflows & Review Surface) added to roadmap; PN-4 code sites + 4 missing contact properties folded into Phase 15 criteria. Next: /gsd-execute-phase 12."
last_updated: "2026-07-20T05:20:00.000Z"
last_activity: 2026-07-20
last_activity_desc: "Phase 12 planned. Portal 22617666 audited: lv_ naming convention (PN-1..PN-5) written into spec §0.6; scheduled-job predicates rewritten for Approach C as SJ-1..SJ-3 in spec §0.7 (input-keyed, never lv_icp_tier/lv_icp_scored_at); Phase 16 registered on roadmap; Phase 15 criteria extended with PN-4 code changes and 4 missing contact properties (lv_linkedin_url, lv_persona_group, lv_jobtitle_verified_at, lv_mobilephone_verified_at)."
progress:
  total_phases: 16
  completed_phases: 11
  total_plans: 12
  completed_plans: 11
  percent: 69
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-07)

**Core value:** The ICP scoring engine turns firmographic + enrichment signals into trustworthy, auditable A/B/C/D prioritization (with hard vetoes) and never clobbers HubSpot data — proven in dry-run locally.
**Current focus:** Milestone 3 — company enrichment via live provider waterfall, plus the web-research retrieval layer that resolves the two ICP fields providers cannot supply. Phases 11–15.

## Current Position

Phase: 12 of 16 (Taxonomy Single-Source) — PLANNED, not executed
Plan: phases/12-taxonomy-single-source/PLAN.md (committed b143959) — run `/gsd-execute-phase 12`
Status: Milestone 3 in progress — Phase 11 complete; Phase 16 (Scheduled Workflows & Review Surface) added 2026-07-20
Last activity: 2026-07-08 — Phase 10 executed: FastAPI /health /ingest /sweep wrapping run_contact_ingest + dedupe_sweep; two n8n v2.4.4 workflow templates; scripts/n8n_replica_test.sh proves import+execute on the running n8n container (ingest dry-run PATCH, sweep duplicate/mangled). 83 tests green offline, replica PASS exit 0, zero live writes.

Progress: [██████▉▒▒▒] 69% (11/16 phases)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4 | 1 | ~10m | ~10m |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase phase-5 P01 | 5m | 4 tasks | 8 files |
| Phase 9 P01 | ~15m | 3 tasks | 6 files |
| Phase 10 P01 | ~35m | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. SPEC-level architectural commitments captured at init:

- Config-driven rubric (`icp_scoring.yaml` v lv-icp-v0.1) with illustrative weights — changeable after JTBD 2 sign-off without code changes (⚠️ pending sign-off).
- MVP canonical writes limited to `lv_icp_*`; firmographics staged, manual fields never touched.
- LLM cascade Haiku → Sonnet 5 → human; non-clobber merge with field-ownership classes.
- [Phase ?]: Phase 9: dedupe_sweep compares NORMALIZED keys (normalize-before-compare); SweepReport findings are plain JSON dicts for Phase-10 transport
- Phase 11: companies is a SIBLING branch, not nested under contacts (ICP fields are per-domain; nesting re-pays per contact). `mergeCompanies.js` kept separate from `mergeContacts.js` for zero regression risk. NO entity-resolution/hierarchy modelling — granularity only corrupts SIZE signals; provider disagreement already detects it. Name-mismatch detection evaluated and REJECTED (blind to the identical-name case). Resolution order is deterministic → retrieval → judgement; a judge without retrieval is least reliable exactly where the ICP lives.
- Phase 10: n8n replica uses a THIN FastAPI wrapper (no JS logic dup); dry_run hard-True + stubbed HubSpot + allow_create off = structurally no live write. `n8n execute --id` (v2.4.4) rejects schedule-only workflows (needs a manual/execute-workflow start node) and needs a non-colliding task-broker port (5699) when run inside the container.

### Pending Todos

- **TX-4 red (intentional)**: `mergeCompanies.js:27` holds a hand-typed evidence-gated org_type list. Drift guard catches it. Phase 12 retires it.

### Blockers/Concerns

- **RESOLVED 2026-07-20 (user decision): `lv_icp_fit_score` is HubSpot-calculated and MUST NOT be written by this workflow.** Calculation happens in HubSpot programmatically. Supersedes CLAUDE.md §29, which lists it as a permitted canonical write. Write paths to remove: `src/merge_policy.py:303`, `main.py:60`, `config/field_policy.yaml:86` (promote_to_canonical -> false), `n8n/code/mergeCompanies.js:35` (class score_output -> non-promoting), plus inverted assertions in `tests/test_merge_policy.py:196` and `tests/test_main.py:60`. The company SEARCH property list (`build_cloud_workflows.py:1183`) is a READ and stays.
- **RESOLVED 2026-07-20 (user decision): Approach C — HubSpot owns the DERIVED outputs; the pipeline writes only the INPUTS.** `lv_icp_fit_score` and `lv_icp_tier` are placeholders (the formula is literally `1 + 1`, so every company currently scores 2). Authoring the real HubSpot-side calculation is **downstream work, explicitly out of scope for Milestone 3**. This retires the tier/score divergence risk entirely, because the pipeline writes neither.
  - **Pipeline WRITES (inputs):** `lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`, `lv_sponsorship_reliant` + their `_source` / `_confidence` / `_evidence_url` / `_verified_at` metadata.
  - **HubSpot DERIVES (downstream, not now):** `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`, `lv_recommended_motion`.
  - `src/icp_scoring.py` still computes score/tier INTERNALLY — it drives in-pipeline routing (`needs_review`, `Unscored`) and the audit breakdown. It is no longer a write path. Keep the engine and its tests; gate the writes.
  - Write paths to retire when the write gate is next touched: `src/merge_policy.py:303`, `main.py:60`, `config/field_policy.yaml:86`, `n8n/code/mergeCompanies.js:35`, plus inverted assertions in `tests/test_merge_policy.py:196` and `tests/test_main.py:60`. Supersedes CLAUDE.md §29. **Deferred — not Phase 12 scope.**
- **`lv_icp_tier` options are `A,B,C,D` only**, but the scorer also emits `Unscored` and `Needs Review` — writing those fails today. Live bug, predates Milestone 3.
- **`lv_org_type` is `string/text`, not an enumeration** — no CRM-level guard; the normalizer is the only barrier against a hallucinated value.
- **RT-5 blocked**: research caching needs `*_verified_at` / `lv_icp_scored_at`; ZERO metadata properties exist in the portal. Until Phase 15, every run re-researches every company.
- **12 days of untracked work (2026-07-08 → 2026-07-20)** happened outside GSD. Phase 11 reconciles it; not retrofitted as synthetic phases.

- **REQ-signoff-gate**: point weights are illustrative pending Alex's JTBD 2 sign-off. Does not block Milestone 1 (config-driven), but gates the production weighted rubric.
- **HubSpot on Starter** ($35); Pro tier required before any writeback/n8n milestone.
- **Enrich-first reality**: org type verified for only 66/712 companies; `closed_lost_reason` 0% filled.

## Deferred Items

Items carried forward to later milestones:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Enrichment | REQ-finite-list-motion (named-list motion) | Deferred | 2026-07-07 |
| Scoring | REQ-intent-scoring (pixel intent) | Deferred | 2026-07-07 |
| Hygiene | REQ-closed-lost-capture | Deferred | 2026-07-07 |
| Process | REQ-signoff-gate (JTBD 2 weighted rubric) | Deferred | 2026-07-07 |

## Session Continuity

Last session: 2026-07-20T05:20:00.000Z
Stopped at: Roadmap extended to 16 phases; spec §0.6 (PN-1..PN-5) and §0.7 (SJ-1..SJ-3) written; Phase 15 criteria carry PN-4 code sites + 4 missing contact properties. Tree clean at commit time.
Resume file: None
Next command: `/gsd-execute-phase 12`
