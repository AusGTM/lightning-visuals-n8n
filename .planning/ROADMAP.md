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

- [x] **Phase 1: Foundation & Configuration** - Config YAMLs, pydantic schemas, and test fixtures that everything else builds on
- [x] **Phase 2: ICP Scoring Engine** - Config-driven score, tier, anti-ICP vetoes, and graduated deductions with unit tests
- [x] **Phase 3: Enrichment Pipeline & Non-Clobber Merge** - Mock providers/research + Haiku/Sonnet cascade feeding a non-clobber merge with source attribution
- [x] **Phase 4: Dry-Run PATCH Output & Safety Gates** - End-to-end MVP run printing the exact HubSpot PATCH under env-flag safety gates

## Phase Details

### Phase 1: Foundation & Configuration
**Goal**: The MVP's config-driven skeleton exists and loads — scoring rubric, field governance, provider priority, source registry, escalation policy, schemas, and fixtures.
**Depends on**: Nothing (first phase)
**Requirements**: MVP-01
**Success Criteria** (what must be TRUE):
  1. Loading the scaffold parses `config/icp_scoring.yaml` (version lv-icp-v0.1) and the four other config YAMLs (field_policy, provider_priority, source_registry, escalation_policy) without error.
  2. Pydantic schemas (HubSpotRecord, ProviderResult, CandidateValue, FieldDecision, ICPScoreResult, MergeResult) validate the provided test fixtures.
  3. Fixtures exist for a current company plus conflicting Apollo/ZoomInfo/Lusha provider results and a Claude web-research result, and each parses into its schema.
**Plans**: 1 plan
- [x] phase-1-01-PLAN.md — Config YAMLs, pydantic schemas, fixtures + runnable scaffold proof

### Phase 2: ICP Scoring Engine
**Goal**: Given firmographic + enrichment signals, the engine computes an ICP fit score, tier, and anti-ICP flag that match the agreed rubric.
**Depends on**: Phase 1
**Requirements**: REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions, REQ-tiering, REQ-org-type-targeting
**Success Criteria** (what must be TRUE):
  1. An AU governing-body/league producing content at $5–500M revenue scores Tier A; an AU content producer scores Tier B; an AU individual club scores Tier C.
  2. Non-ANZ, no-content, or hardware-vendor inputs force Tier D with `lv_anti_icp_flag = true` and a populated anti-ICP reason.
  3. Gambling operator (−20) and >$500M revenue decay (−5 / −15 / −30 / −50) reduce the score without ever setting the anti-ICP flag.
  4. Missing org_type or produces_content yields Needs Review / Unscored (not a false score), and every result emits a breakdown JSON stamped with the scoring version.
**Plans**: 1 plan
- [ ] phase-2-01-PLAN.md — Transcribe the §12.7 ICP scoring engine (with the produces_content fix) + 16-case scoring unit-test proof

### Phase 3: Enrichment Pipeline & Non-Clobber Merge
**Goal**: Mock providers and Claude research produce normalized candidate signals that flow through the Haiku/Sonnet cascade and a non-clobber merge into promote/stage/reject/review decisions, all with source attribution.
**Depends on**: Phase 2
**Requirements**: REQ-enrichment-plan, REQ-hubspot-icp-properties, MVP-02, MVP-03
**Success Criteria** (what must be TRUE):
  1. Mock Apollo/Lusha/ZoomInfo adapters and mock Claude web research each return the normalized provider contract (provider, matched, confidence, data, evidence, model_trace).
  2. Conflicting provider values (e.g. Apollo 5–50M vs ZoomInfo 50–500M revenue) normalize into candidates and resolve via the deterministic gate, escalating to the Haiku classifier / Sonnet stub only when policy requires.
  3. Field-ownership governance is enforced: manual_protected and fill_blank_only fields are staged (never clobbered); system_owned / score_output fields promote when confidence passes.
  4. Every promoted or staged field carries source, confidence, evidence URL + summary, verified_at, verified_by_model, and validation_status.
**Plans**: 1 plan
- [ ] phase-3-01-PLAN.md — Mock providers/web research + normalizer + Haiku/Sonnet cascade + non-clobber merge, proven offline by tests/test_merge_policy.py

### Phase 4: Dry-Run PATCH Output & Safety Gates
**Goal**: The end-to-end MVP run prints the exact HubSpot PATCH it would send, writing only ICP outputs canonically while staging firmographics, under env-flag safety gates.
**Depends on**: Phase 3
**Requirements**: MVP-04
**Success Criteria** (what must be TRUE):
  1. `python main.py` runs the full pipeline on the fixture company and prints provider results, field decisions, the ICP score, and the exact PATCH payload.
  2. In dry-run mode no HubSpot write occurs; the payload promotes only `lv_icp_*` outputs to canonical and stages firmographic provider fields (never domain, annualrevenue, or manual fields).
  3. Safety-gate env flags (DRY_RUN, ALLOW_CANONICAL_WRITES, ALLOW_ICP_SCORE_WRITES, ALLOW_STAGING_WRITES, ALLOW_SONNET_ESCALATION) change the emitted payload as documented.
**Plans**: 1 plan
- [x] phase-4/PLAN.md — hubspot_client + main.py end-to-end dry-run runner + offline SC1/SC2/SC3 proof (with non-gating live smoke)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Configuration | 1/1 | Complete | 2026-07-07 |
| 2. ICP Scoring Engine | 1/1 | Complete | 2026-07-07 |
| 3. Enrichment Pipeline & Non-Clobber Merge | 1/1 | Complete | 2026-07-07 |
| 4. Dry-Run PATCH Output & Safety Gates | 1/1 | Complete | 2026-07-07 |

---

# Milestone 2 — Contact Ingestion, Enrichment & n8n Replica

## Overview

Extend the engine from company-scoring to **contact enrichment from two sources**: (a) non-customer
contacts already in HubSpot, and (b) contacts pulled from uploaded files (CSV/XLSX/JSON). The
field-level non-clobber merge already shipped in Milestone 1 is reused — a file/upload is just
another **source**. The new core is **identity resolution** (match an uploaded row to an existing
HubSpot contact, or decide it is net-new). Locked scope decisions: net-new rows with a valid email
**auto-create** (gated `ALLOW_CONTACT_CREATE`, dry-run first, re-check-by-email guard); everything
ambiguous → review; a **weekly n8n scheduler sweep** flags duplicates and mangled contacts. Final
proof converts the pipeline to an **n8n template** run on a **local n8n server** (Docker) to
replicate the production n8n Cloud environment.

## Phases

- [ ] **Phase 5: Contact Foundation** - Contact normalizer (phone→E.164, email validate/lowercase, title/seniority), contact fixtures, CSV/upload source registered
- [ ] **Phase 6: File Loader & Column Mapper** - CSV/XLSX/JSON → rows; arbitrary columns → HubSpot properties via mapping config; malformed rows rejected with per-row report
- [ ] **Phase 7: Identity / Dedupe Resolver** - Match a row to existing HubSpot contact vs net-new vs ambiguous; conservative (auto only on email/LinkedIn), no-email never auto-creates
- [ ] **Phase 8: Contact Enrichment & Net-New Create** - object_type=contacts wired through main.py; upload row as a candidate source; gated dry-run create with re-check-by-email guard
- [ ] **Phase 9: Functional + E2E Tests & Dedupe Sweep** - Full ingestion matrix (match+enrich, create, ambiguous, conflict→review, no-clobber) + weekly dedupe/mangled-contact sweep function
- [ ] **Phase 10: n8n Template & Local Server Replica** - n8n workflow (upload-ingest + scheduled weekly sweep) calling the decision service, imported and executed on a local Docker n8n

## Phase Details

### Phase 5: Contact Foundation
**Goal**: Contact records normalize cleanly and the upload path is a first-class source.
**Depends on**: Phase 4 (Milestone 1 complete)
**Success Criteria**:
  1. Contact normalizer coerces phone→E.164 (via phonenumbers, region-aware AU default), validates+lowercases email (email-validator), and normalizes jobtitle/seniority; malformed phone/email yield a null + flag, never a crash.
  2. A contact_current fixture plus contact provider fixtures (Apollo/Lusha/ZoomInfo) parse into the existing schemas; provider_priority covers email/linkedin_url/seniority/persona_group; source_registry includes `csv`/`upload` with can_promote_directly:false and a declarable trust level.
  3. Unit tests prove each normalizer branch (valid, malformed, empty) deterministically.
**Plans**: 1 plan
- [ ] phase-5-01-PLAN.md — Contact normalizers (phone/email/seniority) + upload source + contact fixtures + offline test proof

### Phase 6: File Loader & Column Mapper
**Goal**: Any CSV/XLSX/JSON upload becomes normalized candidate rows mapped to HubSpot properties.
**Depends on**: Phase 5
**Success Criteria**:
  1. Loaders read CSV, XLSX, and JSON into a common list-of-dict row shape behind one interface; format is auto-detected by extension.
  2. A column-mapping config maps arbitrary source headers → canonical HubSpot properties (email, firstname, lastname, phone, jobtitle, company, linkedin_url); unmapped columns are ignored, required-key-missing rows are rejected.
  3. Malformed/rejected rows are collected into a structured per-row error report (row index + reason), never silently dropped.

### Phase 7: Identity / Dedupe Resolver
**Goal**: Each uploaded row is confidently classified existing / net-new / ambiguous before any write.
**Depends on**: Phase 6
**Success Criteria**:
  1. Resolution tries email → linkedin_url → phone+lastname → name+company in order; a hit on email or linkedin_url is a confident match, weaker keys alone are ambiguous.
  2. Rows with no email are NEVER classified net-new-create (route to ambiguous/review); confident-match returns the HubSpot contact id via search_records (mockable, offline in tests).
  3. Multiple candidate matches → ambiguous (needs_review); zero matches + valid email → net-new. All outcomes unit-tested with a mocked HubSpot search.

### Phase 8: Contact Enrichment & Net-New Create
**Goal**: The full contact pipeline runs end to end in dry-run: resolve → non-clobber merge → PATCH existing or create net-new.
**Depends on**: Phase 7
**Success Criteria**:
  1. object_type=contacts flows through build_merge_result; an upload row is turned into CandidateValue(s) as source `csv` and merged under the existing field-ownership classes (email manual_protected never written from CSV; fill_blank_only only fills blanks; jobtitle stale_refreshable → needs_review on live conflict).
  2. hubspot_client gains a gated create_record (dry_run + ALLOW_CONTACT_CREATE); net-new create re-checks HubSpot by email immediately before create (guard against dup) and is a no-op when the flag is off.
  3. main.py exposes an ingest-file entrypoint; a functional test drives a CSV through to the emitted dry-run PATCH (existing) and create (net-new) payloads with zero live writes.

### Phase 9: Functional + E2E Tests & Dedupe Sweep
**Goal**: The whole ingestion behavior is proven on realistic multi-row files, plus a maintenance sweep.
**Depends on**: Phase 8
**Success Criteria**:
  1. An E2E test runs a multi-row file covering every path: confident-match+enrich, net-new create, ambiguous→review, field conflict→needs_review, manual_protected/present-fill_blank_only never clobbered, no-email→never create.
  2. A dedupe/cleanup sweep function flags duplicate email/phone/linkedin and mangled contacts (invalid email, unparseable phone) as needs_review, returning a structured report (CLAUDE.md §13.4 Workflow D).
  3. Full suite (Milestone 1 + 2) green offline with no network; a live smoke (real Anthropic, mock providers, DRY_RUN) enriches at least one matched contact.

### Phase 10: n8n Template & Local Server Replica
**Goal**: The pipeline runs as an n8n workflow on a local n8n server, replicating production n8n Cloud.
**Depends on**: Phase 9
**Success Criteria**:
  1. A thin decision service (or CLI-callable entrypoint) exposes the ingest + sweep logic so an n8n node can invoke it without duplicating logic in JS.
  2. An n8n workflow template (upload-ingest trigger + scheduled weekly dedupe sweep) is importable JSON; a local Dockerized n8n instance imports and executes it end to end producing dry-run PATCH/create output.
  3. The local run demonstrates the production-shaped path (trigger → fetch/parse → decision service → dry-run writeback) with all safety gates honored (DRY_RUN, ALLOW_CONTACT_CREATE off by default).

## Milestone 2 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Contact Foundation | 0/1 | Planned | - |
| 6. File Loader & Column Mapper | 0/TBD | Not started | - |
| 7. Identity / Dedupe Resolver | 0/TBD | Not started | - |
| 8. Contact Enrichment & Net-New Create | 0/TBD | Not started | - |
| 9. Functional + E2E Tests & Dedupe Sweep | 0/TBD | Not started | - |
| 10. n8n Template & Local Server Replica | 0/TBD | Not started | - |
