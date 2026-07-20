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

- [x] **Phase 5: Contact Foundation** - Contact normalizer (phone→E.164, email validate/lowercase, title/seniority), contact fixtures, CSV/upload source registered (completed 2026-07-07)
- [x] **Phase 6: File Loader & Column Mapper** - CSV/XLSX/JSON → rows; arbitrary columns → HubSpot properties via mapping config; malformed rows rejected with per-row report
- [x] **Phase 7: Identity / Dedupe Resolver** - Match a row to existing HubSpot contact vs net-new vs ambiguous; conservative (auto only on email/LinkedIn), no-email never auto-creates
- [x] **Phase 8: Contact Enrichment & Net-New Create** - object_type=contacts wired through main.py; upload row as a candidate source; gated dry-run create with re-check-by-email guard
- [x] **Phase 9: Functional + E2E Tests & Dedupe Sweep** - Full ingestion matrix (match+enrich, create, ambiguous, conflict→review, no-clobber) + weekly dedupe/mangled-contact sweep function
- [x] **Phase 10: n8n Template & Local Server Replica** - n8n workflow (upload-ingest + scheduled weekly sweep) calling the decision service, imported and executed on a local Docker n8n (completed 2026-07-08)

## Phase Details

### Phase 5: Contact Foundation

**Goal**: Contact records normalize cleanly and the upload path is a first-class source.
**Depends on**: Phase 4 (Milestone 1 complete)
**Success Criteria**:

  1. Contact normalizer coerces phone→E.164 (via phonenumbers, region-aware AU default), validates+lowercases email (email-validator), and normalizes jobtitle/seniority; malformed phone/email yield a null + flag, never a crash.
  2. A contact_current fixture plus contact provider fixtures (Apollo/Lusha/ZoomInfo) parse into the existing schemas; provider_priority covers email/linkedin_url/seniority/persona_group; source_registry includes `csv`/`upload` with can_promote_directly:false and a declarable trust level.
  3. Unit tests prove each normalizer branch (valid, malformed, empty) deterministically.

**Plans**: 1/1 plans complete

- [ ] PLAN.md
- [x] phase-5-01-PLAN.md — Contact normalizers (phone/email/seniority) + upload source + contact fixtures + offline test proof

### Phase 6: File Loader & Column Mapper

**Goal**: Any CSV/XLSX/JSON upload becomes normalized candidate rows mapped to HubSpot properties.
**Depends on**: Phase 5
**Success Criteria**:

  1. Loaders read CSV, XLSX, and JSON into a common list-of-dict row shape behind one interface; format is auto-detected by extension.
  2. A column-mapping config maps arbitrary source headers → canonical HubSpot properties (email, firstname, lastname, phone, jobtitle, company, linkedin_url); unmapped columns are ignored, required-key-missing rows are rejected.
  3. Malformed/rejected rows are collected into a structured per-row error report (row index + reason), never silently dropped.

**Plans**: 1 plan

- [ ] phase-6-01-PLAN.md — File loader (csv/tsv/json/xlsx behind load_rows) + column mapper + ingest_file→IngestBatch (accepted rows + per-row rejects) + offline fixtures/tests

### Phase 7: Identity / Dedupe Resolver

**Goal**: Each uploaded row is confidently classified existing / net-new / ambiguous before any write.
**Depends on**: Phase 6
**Success Criteria**:

  1. Resolution tries email → linkedin_url → phone+lastname → name+company in order; a hit on email or linkedin_url is a confident match, weaker keys alone are ambiguous.
  2. Rows with no email are NEVER classified net-new-create (route to ambiguous/review); confident-match returns the HubSpot contact id via search_records (mockable, offline in tests).
  3. Multiple candidate matches → ambiguous (needs_review); zero matches + valid email → net-new. All outcomes unit-tested with a mocked HubSpot search.

**Plans**: 1 plan

- [ ] phase-7-01-PLAN.md — IdentityResult schema + src/identity.py (ordered email→linkedin→phone+lastname→name+company resolver, injected/mockable search, no-email-never-net-new hard rule) + tests/test_identity.py offline proof of every outcome

### Phase 8: Contact Enrichment & Net-New Create

**Goal**: The full contact pipeline runs end to end in dry-run: resolve → non-clobber merge → PATCH existing or create net-new.
**Depends on**: Phase 7
**Success Criteria**:

  1. object_type=contacts flows through build_merge_result; an upload row is turned into CandidateValue(s) as source `csv` and merged under the existing field-ownership classes (email manual_protected never written from CSV; fill_blank_only only fills blanks; jobtitle stale_refreshable → needs_review on live conflict).
  2. hubspot_client gains a gated create_record (dry_run + ALLOW_CONTACT_CREATE); net-new create re-checks HubSpot by email immediately before create (guard against dup) and is a no-op when the flag is off.
  3. main.py exposes an ingest-file entrypoint; a functional test drives a CSV through to the emitted dry-run PATCH (existing) and create (net-new) payloads with zero live writes.

**Plans**: 1 plan

- [ ] phase-8/PLAN.md — create_record (gated dry-run) + src/ingest.py (row->csv candidate, recheck guard, run_contact_ingest) + main.py --ingest + offline functional test proving enrich-PATCH vs net-new-create (email both ways)

### Phase 9: Functional + E2E Tests & Dedupe Sweep

**Goal**: The whole ingestion behavior is proven on realistic multi-row files, plus a maintenance sweep.
**Depends on**: Phase 8
**Success Criteria**:

  1. An E2E test runs a multi-row file covering every path: confident-match+enrich, net-new create, ambiguous→review, field conflict→needs_review, manual_protected/present-fill_blank_only never clobbered, no-email→never create.
  2. A dedupe/cleanup sweep function flags duplicate email/phone/linkedin and mangled contacts (invalid email, unparseable phone) as needs_review, returning a structured report (CLAUDE.md §13.4 Workflow D).
  3. Full suite (Milestone 1 + 2) green offline with no network; a live smoke (real Anthropic, mock providers, DRY_RUN) enriches at least one matched contact.

**Plans**: 1 plan

- [ ] phase-9/PLAN.md — dedupe/mangled sweep (src/sweep.py + SweepReport) + multi-row E2E ingestion matrix (test_e2e_ingest.py) + non-gating live-Haiku smoke, all offline

### Phase 10: n8n Template & Local Server Replica

**Goal**: The pipeline runs as an n8n workflow on a local n8n server, replicating production n8n Cloud.
**Depends on**: Phase 9
**Success Criteria**:

  1. A thin decision service (or CLI-callable entrypoint) exposes the ingest + sweep logic so an n8n node can invoke it without duplicating logic in JS.
  2. An n8n workflow template (upload-ingest trigger + scheduled weekly dedupe sweep) is importable JSON; a local Dockerized n8n instance imports and executes it end to end producing dry-run PATCH/create output.
  3. The local run demonstrates the production-shaped path (trigger → fetch/parse → decision service → dry-run writeback) with all safety gates honored (DRY_RUN, ALLOW_CONTACT_CREATE off by default).

**Plans**: 1 plan

- [x] phase-10/PLAN.md — FastAPI decision service (/ingest /sweep /health reusing run_contact_ingest + dedupe_sweep) + two n8n v2.4.4 workflow templates + scripted local-Docker-n8n import/execute replica proof

## Milestone 2 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Contact Foundation | 1/1 | Complete   | 2026-07-07 |
| 6. File Loader & Column Mapper | 1/1 | Complete | 2026-07-08 |
| 7. Identity / Dedupe Resolver | 1/1 | Complete | 2026-07-08 |
| 8. Contact Enrichment & Net-New Create | 1/1 | Complete | 2026-07-08 |
| 9. Functional + E2E Tests & Dedupe Sweep | 1/1 | Complete | 2026-07-08 |
| 10. n8n Template & Local Server Replica | 1/1 | Complete | 2026-07-08 |

---

# Milestone 3 — Company Enrichment & ICP Research

## Overview

Milestones 1–2 proved company scoring locally and moved contact ingestion into n8n. Milestone 3
closes the loop on **companies**: a live provider waterfall for company objects, and the retrieval
layer that resolves the two ICP fields providers cannot supply.

The driving finding, measured against five live prospect accounts on 2026-07-20: `lv_org_type` is
resolvable from provider descriptions for **3 of 5** accounts, but `lv_produces_content` is
resolvable for **0 of 5** — no provider description mentions broadcast or streaming. Since
`lv_produces_content: false` fires a hard veto, retrieval is not an optimisation; it is the only
way to score the field at all.

Two structural decisions are locked. **Companies is a sibling branch, not nested under contacts** —
the ICP fields are per-domain and expensive, so nesting would re-pay for every contact at the same
company. **Resolution is ordered deterministic → retrieval → judgement** — an LLM judging from
parametric recall is least reliable exactly where the ICP lives (it knows Harvey Norman; it
confabulates on obscure ANZ clubs).

**Scope fence (decided 2026-07-20).** The pipeline writes ICP **inputs** only. The derived
outputs — `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason`,
`lv_recommended_motion` — are computed in HubSpot programmatically and are **downstream
work, out of scope for this milestone**. Both score and tier are placeholders today
(`calculationFormula` is literally `1 + 1`). `src/icp_scoring.py` keeps computing score and
tier internally to drive in-pipeline routing and the audit breakdown, but is no longer a
write path. Milestone 3 succeeds by making the inputs trustworthy; encoding a HubSpot
formula against fields the pipeline cannot yet populate would be premature.

Phase 11 was executed outside GSD between 2026-07-08 and 2026-07-20 and is recorded here
retroactively; its artifacts and tests are in the tree.

## Phases

- [x] **Phase 11: Company Branch & Provider Contract Hardening** - Company sibling branch in n8n, mergeCompanies non-clobber merge, ZoomInfo GTM companies contract probed live, three live-shape bugs fixed, cross-provider conflict detector, taxonomy + web-research spec (completed 2026-07-20, outside GSD)
- [ ] **Phase 12: Taxonomy Single-Source** - config/taxonomy.yaml becomes the only edit point; node literals generated at build time; retires the known-red TX-4 drift guard
- [ ] **Phase 13: Web Research Retrieval & Validation** - Native web_search retrieval, output validation, enum normalization, tri-state coercion
- [ ] **Phase 14: Judge Wiring** - Haiku classify → Sonnet escalate per CLAUDE.md §15, pointed at identity/classification not numeric plausibility
- [ ] **Phase 15: HubSpot Property Migration** - Create missing metadata properties; unblocks research caching. IRREVERSIBLE — checkpointed, dry-run first
- [ ] **Phase 16: Scheduled Workflows & Review Surface** - Schedule-triggered n8n workflows (SJ-1..SJ-3 predicates), dedupeSweep wiring, §22.2 review loop on the 9 missing review properties

## Phase Details

### Phase 11: Company Branch & Provider Contract Hardening

**Goal**: Companies enrich from live providers with correct units and no silent wrong-entity data.
**Depends on**: Phase 10
**Status**: COMPLETE 2026-07-20 (executed outside GSD; recorded retroactively)
**Success Criteria**:

  1. Company branch runs as a sibling off the same trigger, read-only, with all three providers.
  2. ZoomInfo GTM `companies/enrich` + `companies/search` contract confirmed live, valid outputFields enumerated.
  3. Provider unit and live-shape defects fixed with regression tests.
  4. Cross-provider size conflicts withhold promotion rather than silently picking one.
  5. A numbered, testable spec exists for the retrieval work that follows.

**Plans**: 1 plan

- [x] phase-11/PLAN.md — see phase-11-01-SUMMARY.md (retroactive)

### Phase 12: Taxonomy Single-Source

**Goal**: Adding an org_type or content_type is a one-file edit that cannot silently drift.
**Depends on**: Phase 11
**Success Criteria**:

  1. `config/taxonomy.yaml` is the only hand-edited vocabulary; icp_scoring, field_policy, node literals, research prompt and normalizers all derive from it.
  2. `src/taxonomy.py` provides `normalize_org_type` / `normalize_content_types` satisfying spec NM-1…NM-6.
  3. The builder generates the JS literal into n8n Code nodes; TX-4 goes green with no hand-maintained list in `mergeCompanies.js`.
  4. Python and JS normalizers agree on every shared case (NM-6 parity test).

**Plans**: TBD — run `/gsd-plan-phase 12`

### Phase 13: Web Research Retrieval & Validation

**Goal**: The two provider-unresolvable ICP fields resolve from citable sources, or not at all.
**Depends on**: Phase 12
**Success Criteria**:

  1. Retrieval satisfies spec RT-1…RT-4 within existing cost kill-switches.
  2. Output carries `evidence_by_field` keyed per field — the shape `mergeCompanies`' evidence gate already requires (OC-1).
  3. Tri-state honored: thin or absent evidence yields `null`, never `false` (TS-1, TS-2).
  4. Off-vocabulary model output normalizes to `unknown` + needs_review, never reaches HubSpot (AT-2).
  5. The `xfail(strict=True)` acceptance tests in `tests/test_web_research_spec.py` flip to passing and their markers are removed.

**Plans**: TBD

### Phase 14: Judge Wiring

**Goal**: Conflicts and high-risk classifications get adjudicated on evidence, not recall.
**Depends on**: Phase 13
**Success Criteria**:

  1. Escalation triggers match CLAUDE.md §15 / spec JG-1.
  2. Judge never runs without retrieval output (RO-1); size conflicts never trigger a model call alone (RO-2).
  3. Judge confidence below 80 routes to needs_review, never promotes (JG-3).

**Plans**: TBD

### Phase 15: HubSpot Property Migration

**Goal**: The metadata properties the pipeline needs exist, created safely.
**Depends on**: Phase 14
**Success Criteria**:

  1. Missing metadata properties created; sync script dry-runs by default and emits an undo manifest.
  2. Research caching by domain with 180-day TTL becomes possible (unblocks RT-5).
  3. `lv_org_type` text→enumeration is NOT performed without explicit sign-off (irreversible type change).
  4. `lv_icp_fit_score` and `lv_icp_tier` are left AS calculated/placeholder — per the milestone scope fence, HubSpot owns them. Retire the pipeline's write paths to those fields (`src/merge_policy.py:303`, `main.py:60`, `config/field_policy.yaml:86`, `n8n/code/mergeCompanies.js:35`, and two inverted test assertions).
  5. PN-1..PN-5 naming convention applied to code-generated property names: metadata stampers emit `lv_`-prefixed names (`n8n/code/mergeCompanies.js:154`, `n8n/code/mergeContacts.js:115`, `src/merge_policy.py:44`), `n8n/code/enrichmentGate.js:76` reads them, and `scripts/build_cloud_workflows.py` hardcoded names updated (`:686`, `:692`, `:694`, `:1059`).
  6. Four missing contact properties created alongside the metadata migration: `lv_linkedin_url`, `lv_persona_group`, `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at`. Until created, HubSpot silently drops the search-list names and staleness checks return undefined for every contact.

**Plans**: TBD

### Phase 16: Scheduled Workflows & Review Surface

**Goal**: The background reconciliation layer runs on schedule, and needs-review records reach a human who can approve them.
**Depends on**: Phase 15
**Success Criteria**:

  1. Schedule-triggered n8n workflows exist for the three SJ predicates (spec §0.7): SJ-1 hourly input-gap scan, SJ-2 monthly stale refresh, SJ-3 15-minute requested poller. Predicates key on pipeline-owned inputs only — never `lv_icp_tier` / `lv_icp_scored_at` (Approach C).
  2. `build_cloud_workflows.py` emits scheduleTrigger nodes; `dedupeSweep.js` is wired into an active scheduled workflow (CLAUDE.md §13.4).
  3. The §22.2 review loop closes: flag → decision JSON → RevOps approve → apply → clear, on the 9 review properties (created in Phase 15 or here, `lv_`-prefixed per PN-5).
  4. SJ-1..SJ-3 acceptance tests authored with this phase's plan (spec §0.7 defers them here).

**Plans**: TBD

## Milestone 3 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 11. Company Branch & Provider Contract Hardening | 1/1 | Complete | 2026-07-20 |
| 12. Taxonomy Single-Source | 0/? | Not started | — |
| 13. Web Research Retrieval & Validation | 0/? | Not started | — |
| 14. Judge Wiring | 0/? | Not started | — |
| 15. HubSpot Property Migration | 0/? | Not started | — |
| 16. Scheduled Workflows & Review Surface | 0/? | Not started | — |
