# Roadmap: lv-n8n-poc

## Overview

Milestone 1 delivers the local-first Python MVP from CLAUDE.md §11 / §29: prove that
ICP scoring, non-clobber merge, source attribution, an LLM cascade, and safe dry-run
HubSpot PATCH output all work before any production wiring. The journey builds bottom-up —
a config-driven skeleton, then the scoring engine (the crown jewel), then the mock
enrichment + merge pipeline that feeds it, then the end-to-end dry-run run under safety
gates. The MVP scores companies only and writes only `lv_icp_*` outputs canonically.

**Future milestones (out of scope here):** HubSpot test-record writeback → n8n Cloud
dry-run → live provider + web-research integration → controlled pilot. These are
sequenced in CLAUDE.md §25 and become their own roadmaps once Milestone 1 ships and
HubSpot is on the Pro tier.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked INSERTED)

- [ ] **Phase 1: Foundation & Configuration** - Config YAMLs, pydantic schemas, and test fixtures that everything else builds on
- [ ] **Phase 2: ICP Scoring Engine** - Config-driven score, tier, anti-ICP vetoes, and graduated deductions with unit tests
- [ ] **Phase 3: Enrichment Pipeline & Non-Clobber Merge** - Mock providers/research + Haiku/Sonnet cascade feeding a non-clobber merge with source attribution
- [ ] **Phase 4: Dry-Run PATCH Output & Safety Gates** - End-to-end MVP run printing the exact HubSpot PATCH under env-flag safety gates

## Phase Details

### Phase 1: Foundation & Configuration
**Goal**: The MVP's config-driven skeleton exists and loads — scoring rubric, field governance, provider priority, source registry, escalation policy, schemas, and fixtures.
**Depends on**: Nothing (first phase)
**Requirements**: MVP-01
**Success Criteria** (what must be TRUE):
  1. Loading the scaffold parses `config/icp_scoring.yaml` (version lv-icp-v0.1) and the four other config YAMLs (field_policy, provider_priority, source_registry, escalation_policy) without error.
  2. Pydantic schemas (HubSpotRecord, ProviderResult, CandidateValue, FieldDecision, ICPScoreResult, MergeResult) validate the provided test fixtures.
  3. Fixtures exist for a current company plus conflicting Apollo/ZoomInfo/Lusha provider results and a Claude web-research result, and each parses into its schema.
**Plans**: TBD

### Phase 2: ICP Scoring Engine
**Goal**: Given firmographic + enrichment signals, the engine computes an ICP fit score, tier, and anti-ICP flag that match the agreed rubric.
**Depends on**: Phase 1
**Requirements**: REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions, REQ-tiering, REQ-org-type-targeting
**Success Criteria** (what must be TRUE):
  1. An AU governing-body/league producing content at $5–500M revenue scores Tier A; an AU content producer scores Tier B; an AU individual club scores Tier C.
  2. Non-ANZ, no-content, or hardware-vendor inputs force Tier D with `lv_anti_icp_flag = true` and a populated anti-ICP reason.
  3. Gambling operator (−20) and >$500M revenue decay (−5 / −15 / −30 / −50) reduce the score without ever setting the anti-ICP flag.
  4. Missing org_type or produces_content yields Needs Review / Unscored (not a false score), and every result emits a breakdown JSON stamped with the scoring version.
**Plans**: TBD

### Phase 3: Enrichment Pipeline & Non-Clobber Merge
**Goal**: Mock providers and Claude research produce normalized candidate signals that flow through the Haiku/Sonnet cascade and a non-clobber merge into promote/stage/reject/review decisions, all with source attribution.
**Depends on**: Phase 2
**Requirements**: REQ-enrichment-plan, REQ-hubspot-icp-properties, MVP-02, MVP-03
**Success Criteria** (what must be TRUE):
  1. Mock Apollo/Lusha/ZoomInfo adapters and mock Claude web research each return the normalized provider contract (provider, matched, confidence, data, evidence, model_trace).
  2. Conflicting provider values (e.g. Apollo 5–50M vs ZoomInfo 50–500M revenue) normalize into candidates and resolve via the deterministic gate, escalating to the Haiku classifier / Sonnet stub only when policy requires.
  3. Field-ownership governance is enforced: manual_protected and fill_blank_only fields are staged (never clobbered); system_owned / score_output fields promote when confidence passes.
  4. Every promoted or staged field carries source, confidence, evidence URL + summary, verified_at, verified_by_model, and validation_status.
**Plans**: TBD

### Phase 4: Dry-Run PATCH Output & Safety Gates
**Goal**: The end-to-end MVP run prints the exact HubSpot PATCH it would send, writing only ICP outputs canonically while staging firmographics, under env-flag safety gates.
**Depends on**: Phase 3
**Requirements**: MVP-04
**Success Criteria** (what must be TRUE):
  1. `python main.py` runs the full pipeline on the fixture company and prints provider results, field decisions, the ICP score, and the exact PATCH payload.
  2. In dry-run mode no HubSpot write occurs; the payload promotes only `lv_icp_*` outputs to canonical and stages firmographic provider fields (never domain, annualrevenue, or manual fields).
  3. Safety-gate env flags (DRY_RUN, ALLOW_CANONICAL_WRITES, ALLOW_ICP_SCORE_WRITES, ALLOW_STAGING_WRITES, ALLOW_SONNET_ESCALATION) change the emitted payload as documented.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Configuration | 0/TBD | Not started | - |
| 2. ICP Scoring Engine | 0/TBD | Not started | - |
| 3. Enrichment Pipeline & Non-Clobber Merge | 0/TBD | Not started | - |
| 4. Dry-Run PATCH Output & Safety Gates | 0/TBD | Not started | - |
