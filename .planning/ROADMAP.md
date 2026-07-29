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
- [x] **Phase 12: Taxonomy Single-Source** - config/taxonomy.yaml becomes the only edit point; node literals generated at build time; retires the known-red TX-4 drift guard (completed 2026-07-20)
- [x] **Phase 13: Web Research Retrieval & Validation** - Native web_search retrieval, output validation, enum normalization, tri-state coercion (completed 2026-07-21)
- [x] **Phase 14: Judge Wiring** - Haiku classify → Sonnet escalate per CLAUDE.md §15, pointed at identity/classification not numeric plausibility (completed 2026-07-21)
- [x] **Phase 15: HubSpot Property Migration** - Create missing metadata properties; unblocks research caching. Fully reversible (archive + recreate-by-name within 90 days), dry-run first (completed 2026-07-22; tooling offline-proven, live operator runbook pending)
- [x] **Phase 15.5: Tiered Candidate Adjudication** (INSERTED 2026-07-22) - Candidates stay parallel + scored through to the judge instead of collapsing to an argmax winner; judge grounds in web search AND the A/R/G/T scoring components. Tiered: deterministic collapse for size/firmographics (JG-2 — LLMs are poorly calibrated on numeric plausibility, RO-2 intent preserved), judge adjudicates ICP-semantic fields (org_type, produces_content, vendor flags) where a wrong answer moves tier or fires a veto. Research candidates gain a recencyDate so recency acts as ordering bias (neutral when unknown), at parity with the provider branch. Completed 2026-07-23.
- [x] **Phase 16: Scheduled Workflows & Review Surface** - Schedule-triggered n8n workflows (SJ-1..SJ-3 predicates), dedupeSweep wiring, §22.2 review loop on the 9 missing review properties (completed 2026-07-23; tooling offline-proven, live operator runbook pending)

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
**Status**: COMPLETE 2026-07-20
**Success Criteria**:

  1. [x] `config/taxonomy.yaml` is the only hand-edited vocabulary; icp_scoring and field_policy stay hand-written but drift-guarded by TX-1/2/3 (per plan decision D3 — codegen is reserved for the node literal, the one artifact that cannot be read at runtime); node literals and normalizers derive from it. Research prompt deferred to Phase 13 by design (documented in PLAN.md's deferral note).
  2. [x] `src/taxonomy.py` provides `normalize_org_type` / `normalize_org_type_result` / `normalize_content_types` satisfying spec NM-1…NM-5 (NM-6 in criterion 4).
  3. [x] The builder generates the JS literal into n8n Code nodes; TX-4 goes green with no hand-maintained list in `mergeCompanies.js`.
  4. [x] Python and JS normalizers agree on every shared case (NM-6 parity test, tests/n8n/parity.test.mjs).

**Plans**: 1 plan

- [x] phase-12/PLAN.md — see 12-01-SUMMARY.md

### Phase 13: Web Research Retrieval & Validation

**Goal**: The two provider-unresolvable ICP fields resolve from citable sources, or not at all.
**Depends on**: Phase 12
**Status**: COMPLETE 2026-07-21
**Success Criteria**:

  1. [x] Retrieval satisfies spec RT-1…RT-4 within existing cost kill-switches.
  2. [x] Output carries `evidence_by_field` keyed per field — the shape `mergeCompanies`' evidence gate already requires (OC-1).
  3. [x] Tri-state honored: thin or absent evidence yields `null`, never `false` (TS-1, TS-2).
  4. [x] Off-vocabulary model output normalizes to `unknown` + needs_review, never reaches HubSpot (AT-2).
  5. [x] The `xfail(strict=True)` acceptance tests in `tests/test_web_research_spec.py` flip to passing and their markers are removed.
  6. [x] (User addition 2026-07-21) Research-failure skip path proven offline; closed-won ground-truth smoke available as a non-gating operator tool.

**Plans**: 1 plan

- [x] 13-01-PLAN.md — see 13-01-SUMMARY.md

### Phase 14: Judge Wiring

**Goal**: Conflicts and high-risk classifications get adjudicated on evidence, not recall.
**Depends on**: Phase 13
**Status**: COMPLETE 2026-07-21
**Success Criteria**:

  1. [x] Escalation triggers match CLAUDE.md §15 / spec JG-1.
  2. [x] Judge never runs without retrieval output (RO-1); size conflicts never trigger a model call alone (RO-2) — proven structurally: the judge chain runs upstream of the node that computes the size-disagreement array (D1), asserted by jsCode-absence + graph-ancestry BFS.
  3. [x] Judge confidence below 80 routes to needs_review, never promotes (JG-3).
  4. [x] Evidence sufficiency enforced (JG-4): a citation that does not substantiate the claim — third-party directory, tourism listing, bare homepage — demotes `lv_produces_content` to `null` + needs_review, never to `false`. Case set from the Phase-13 closed-lost smoke (20 real rows, 19/20 exact, 1 documented accepted false-negative).
  5. [x] (JG-5, scope-corrected 2026-07-21 after research) The Supertech Electronics false positive is caught by the hardware-vendor path independently of JG-4. Under Approach C the pipeline does NOT compute the veto — HubSpot does — so the deliverable is: the research prompt requests `lv_is_hardware_vendor` / `lv_is_gambling_operator` AND the merge fold stops dropping them, so the INPUT reaches HubSpot; the veto itself is proven offline against `src/icp_scoring.py`, not computed in production JS. **Note:** this offline proof surfaced a pre-existing, documented gap in `icp_scoring.py`'s tier-downgrade precedence (unrelated to this phase's scope, not fixed here — see 14-01-SUMMARY.md Deviations); the veto SIGNAL itself is confirmed independent, which is what Approach C's routing relies on.

**Plans**: 1 plan

- [x] 14-01-PLAN.md — see 14-01-SUMMARY.md

### Phase 15: HubSpot Property Migration

**Goal**: The metadata properties the pipeline needs exist, created safely.
**Depends on**: Phase 14
**Status**: EXECUTED 2026-07-22 — tooling built + fully offline-proven (199 pytest / 77 node); live property creation, baseline snapshot, and canary proof are OPERATOR RUNBOOK steps (15-01-SUMMARY.md), not yet run. Portal 22617666 untouched.
**Success Criteria**:

  1. [x] Missing metadata properties created; sync script dry-runs by default and emits an undo manifest. `config/hubspot_properties.yaml` (33 properties/2 groups) + `scripts/sync_hubspot_properties.py` built and offline-proven; live creation is the operator's step.
  2. [x] Research caching by domain with 180-day TTL becomes possible (unblocks RT-5) — the 4 cache-key datetimes are in the manifest.
  3. [x] `lv_org_type` text→enumeration is NOT performed without explicit sign-off (irreversible type change) — not scheduled anywhere in this phase.
  4. [x] `lv_icp_fit_score` and `lv_icp_tier` are left AS calculated/placeholder — per the milestone scope fence, HubSpot owns them. Pipeline write paths retired (`src/merge_policy.py`, `main.py`, `config/field_policy.yaml`, `n8n/code/mergeCompanies.js`), 3 inverted test assertions now assert absence.
  5. [x] PN-1..PN-5 naming convention applied to code-generated property names, under the PROVENANCE MODEL (coordinator decision, supersedes flat-suffix design): metadata/staging collapse into ONE `lv_enrichment_provenance`/`lv_contact_enrichment_provenance` JSON blob per object (Python `src/merge_policy.py` serialize_provenance / JS `mergeCompanies.js`+`mergeContacts.js` stableStringify, byte-identical, parity-tested incl. non-ASCII), `n8n/code/enrichmentGate.js` reads the real cache-key properties, and `scripts/build_cloud_workflows.py`'s decide/echo nodes are the single serialization point.
  6. [x] Four missing contact properties manifested + create-if-missing-scripted alongside the metadata migration: `lv_linkedin_url`, `lv_persona_group`, `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at` — canonical field rename landed in code (PN-1 architecture guard proves it); live creation is the operator's step.

**Plans**: 1/1 plans complete

- [x] 15-01-PLAN.md — Reversibility-first HubSpot property migration: baseline snapshot + dry-run/undo-manifest sync + provenance-JSON stamper model (1 blob + 4 cache keys) + ICP write-path retirement + PN-1..PN-5 renames + rollback script/canary + operator runbook (completed 2026-07-22; see 15-01-SUMMARY.md)

### Phase 15.5: Tiered Candidate Adjudication (INSERTED)

**Goal**: When enrichment sources conflict, the winning value is chosen with the most information available — not by a premature argmax that discards it.
**Depends on**: Phase 15
**Why inserted**: Validation before Phase 16 found the judge decides ICP-critical fields while blind to the provider evidence. `scoreCandidates` computes A/R/G/T then immediately collapses to `winners[field] = top.value`; `best[field]` (components, agreedBy) is retained but never read downstream. The judge sees only the research candidate. Separately, the research branch bypasses `scoreCandidates` entirely, so `lv_org_type`/`lv_produces_content` carry no recency signal at all — evidenced live by Wyong's 2021 stream listing passing the sufficiency gate as current proof. Judge logic must be locked before deployment.
**Status**: EXECUTED 2026-07-23 — 6 tasks, 6 commits, fully offline-proven (201 pytest / 123 node, baseline 200/77 + new, 0 regressions). No live network calls; no HubSpot writes.
**Success Criteria**:

  1. [x] Scoring ranks but does not decide: candidates stay parallel with their A/R/G/T components through to the adjudication point; no information is discarded before the judge. `scoreResearchCandidates` (judge.js) attaches `research_scoring` to every researched row via the unmodified `scoreCandidates` engine, escalated or not.
  2. [x] Tiered routing is explicit and tested: size/firmographic conflicts resolve deterministically (never a model call — RO-2 intent, JG-2 rationale); ICP-semantic fields (`lv_org_type`, `lv_produces_content`, vendor flags) route to the judge when JG-1 triggers fire. `test_ta2_judge_eligible_and_deterministic_fields_are_disjoint` asserts disjointness from the real sources (judge.js + built Merge Company node).
  3. [x] The judge receives the full ranked candidate set + scoring components + web-search grounding, and its verdict cites which it relied on. `buildJudgeRequestBody` gained a `scoring` key restricted to judge-eligible fields (JG-2 preserved); the prompt labels `prior_on_file` as non-independent.
  4. [x] Research candidates carry a `recencyDate`; recency is ordering bias only — unknown age stays neutral 0.5, never a penalty, never a veto (a decades-stable fact is not wrong for being old). Sourced from Anthropic's `page_age` via `extractPageAgeByField` (tolerant URL matching), never a model self-report or URL-slug guess.
  5. [x] TS-1 holds throughout: no recency or scoring path can turn a value `false`; insufficient/aged evidence demotes toward `null` + needs_review. Proven by an identical-canonicalPatch assertion (fresh vs stale page_age) plus a DELIBERATE-BREAK that wires the composite into the promotion gate and shows promotions collapse (D2's arithmetic proof: composite ~67 < both thresholds).
  6. [x] Cost is bounded and proven: judge invocation count per run is capped and asserted, and no size-only disagreement can trigger a model call (structural, as Phase 14 proved for RO-2). `applyCostCap` extracted + unit-tested at 15-into-10 and zero-budget; RO-2's existing structural test extended with a cap-location assertion.

**Plans**: 1/1 plans complete

- [x] 15.5-tiered-candidate-adjudication/PLAN.md — score research candidates with the existing A/R/G/T engine against a prior on file (self-confirmation-guarded), source recencyDate from Anthropic `page_age`, ground the judge in the full ranked set, and cap + assert judge invocations (completed 2026-07-23; see 15.5-01-SUMMARY.md)

### Phase 16: n8n Cloud Deployment, Scheduled Workflows & Review Surface

**Goal**: The pipeline runs live on n8n Cloud, the background reconciliation layer runs on schedule, and needs-review records reach a human who can approve them — held to `docs/SYSTEM-CONTRACT.md`.
**Depends on**: Phase 15.5
**SCOPE EXPANDED 2026-07-23** after the n8n Cloud investigation this session. The original entry (criteria 1–4 below) covered only schedules + review surface. The deployment prerequisites discovered this session (criteria 5–9) are what actually gate going live, and this phase is **large — the planner should split it into "make it deployable" (5–8) and "make it complete" (1–4, 9), likely as separate plans/waves or even a Phase 16 / Phase 17 split.**

**Deployment findings to build on (this session, verified live):**

- n8n Cloud **Public API works** (`X-N8N-API-KEY`, `GET/POST /api/v1/workflows`, `/credentials`) — scripted deploy + credential creation are available. The MCP server (`create_workflow_from_code`, `publish_workflow`, `list_credentials`, version history/restore) is authoring-only (SDK code, not our JSON) — useful for activation/test/rollback, NOT import.
- **`$env` is BLOCKED on Cloud** (`N8N_BLOCK_ENV_ACCESS_IN_NODE` defaults true) and **`$vars` is NOT licensed** (403 `feat:variables`). The 6 secrets (`ANTHROPIC_API_KEY`, `APOLLO_API_KEY`, `LUSHA_API_KEY`, `ZOOMINFO_CLIENT_ID/SECRET`, `HUBSPOT_PRIVATE_APP_TOKEN`) MUST become n8n **credentials** referenced by ID; the 6 config flags (`ALLOW_WEB_RESEARCH`, `ALLOW_SONNET_ESCALATION`, `MAX_WEB_RESEARCH_PER_RUN`, `MAX_SONNET_VALIDATIONS_PER_RUN`, `WEB_RESEARCH_MAX_SEARCHES`, `ANTHROPIC_SONNET_MODEL`) MUST become build-time inlined constants (AR-4 pattern). Enumerated live from the built workflow JSONs.
- The instance is **empty** (0 workflows, 0 credentials) — clean deploy, but credentials must be provisioned first.
- HubSpot side is fully migrated (33 properties live incl. the 9 review-surface on both objects; `_verified_at` cache keys exist → RT-5 unblocked).

**Success Criteria:**

  1. Schedule-triggered n8n workflows exist for the three SJ predicates (spec §0.7): SJ-1 hourly input-gap scan, SJ-2 monthly stale refresh, SJ-3 15-minute requested poller. Predicates key on pipeline-owned inputs only — never `lv_icp_tier` / `lv_icp_scored_at` (Approach C).
  2. `build_cloud_workflows.py` emits scheduleTrigger nodes; `dedupeSweep.js` is wired into an active scheduled workflow (CLAUDE.md §13.4).
  3. The §22.2 review loop closes: flag → decision JSON → RevOps approve → apply → clear, on the 9 review properties (live on both objects from Phase 15).
  4. SJ-1..SJ-3 acceptance tests authored with this phase's plan (spec §0.7 defers them here).
  5. **`$env` → credentials + build-time constants (critical path).** The 6 secrets become n8n credential references; the 6 config flags become inlined constants with the currency drift-guard pattern; local-replica (`$env` via docker) and Cloud (credentials) must not diverge without a parity story.
  6. **Credential-provisioning script** — creates the n8n credentials via the Public API, two-key gated, same idiom as `sync_hubspot_properties.py`, no-creds skip path, never in the offline suite.
  7. **Deploy script** over the guarded deployable set (`test_top_level_is_exactly_the_deployable_set`) — dry-run diff (create-vs-update), `X-N8N-API-KEY`, idempotent.
  8. **Cloud-template companies-branch port** — `build_enrichment_cloud()` has no companies branch today (Phase 13 D4 deferred it here); the webhook production template gains the full ICP pipeline.
  9. **RT-5 research caching** by domain, 180-day TTL keyed on the `_verified_at` properties — freshness-without-churn per SYSTEM-CONTRACT commitment 5.

**Evaluated against `docs/SYSTEM-CONTRACT.md`** — especially: non-clobber absolute *under live writes* (this is the first phase writing real record data), right-sized compute (no capable model on a cheap path), freshness-without-churn (criterion 9), and the closed-won red-flag as a live regression signal.

**Plans**: 2/2 plans executed
**Wave 1**

- [x] 16-01-PLAN.md — Deployable (Criteria 5–8 + SJ-3 property prerequisite): env→credentials + build-time constants, ZoomInfo credential decision, companies-branch port, deploy + credential-provisioning scripts [wave 1]

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 16-02-PLAN.md — Complete (Criteria 1–4, 9): SJ-1/2/3 schedule workflows, dedupeSweep wiring, §22.2 review loop, RT-5 caching test [wave 2, depends_on 16-01]

### Phase 16.1: Per-Request Provider Selection, Credit Reporting & Schedule Safety (INSERTED)

**Goal**: The on-demand enrichment webhook is caller-controlled and cost-safe before going live — the caller chooses which provider adapters run (or none), the response reports remaining provider credits, and scheduled workflows ship disabled. Delivers the original extensibility requirement (pluggable provider adapters) and the pre-live cost-safety gate together.
**Depends on**: Phase 16
**INSERTED 2026-07-24** as "Track A" — the recommended pre-live cost-safety + extensibility gate before the live operator runbook (Track B). Decisions this session: per-request `providers` control is the primary burn gate (**no** global build-time kill-switch); absent/blank/`none` `providers` = enrich nothing; scheduled workflows ship inactive.

**Success Criteria:**

  1. The enrichment webhook payload accepts a `providers` node: an array of provider names, or `"all"`, or `"none"`/`""`/absent. `all` → every registered adapter; `none`/blank/absent → zero provider calls. Parsed in the `Parse HubSpot Event` node, threaded to every row, and honoured by BOTH the contacts and companies waterfalls.
  2. A disabled provider's HTTP node does NOT execute — gating happens BEFORE the paid call, not by discarding the response after. `none`/blank/absent still runs the rest of the pipeline (identity, gate, scoring, research, writeback) with zero provider HTTP calls. This per-request gate is the primary pre-live burn control (no global kill-switch by decision).
  3. Provider adapters are registered in ONE extensible place (an adapter registry) so a future provider is added by a registry entry + its nodes, not by editing parse/gate/normalize/merge individually — the original extensibility requirement (CLAUDE.md provider-adapter contract §16).
  4. Credit-check endpoints validated against REAL provider docs AND live curl (Lusha, Apollo, ZoomInfo GTM) — verified method/URL/auth/response-field, and which of this account's keys actually authorize the call. Non-authorizing keys degrade gracefully (reported unknown, never fail the run).
  5. The webhook response carries a `remaining_credits` node — remaining credits per provider, e.g. `[{ "provider": "zoominfo", "credits": 4156 }]` — reported POST-enrichment. A credit-check failure never fails enrichment.
  6. `scripts/check_provider_credits.py` — read-only, `.env`-keyed provider balance check, two-key/no-creds skip path, never in the offline suite (mirrors `provision_n8n_credentials.py` idiom).
  7. Scheduled workflows (scheduled-maintenance + SJ-1/SJ-2/SJ-3) emit `active: false`; deploy leaves them inactive; an operator enables each with one n8n toggle. Documented in the runbook.
  8. Acceptance tests (offline, no live calls): `providers` parsing (all/none/list/absent), per-provider gate skip, `remaining_credits` response shape, and the schedules-inactive invariant. Full offline suite stays green; builder rebuild deterministic.

**Evaluated against `docs/SYSTEM-CONTRACT.md`** — cost-safety (no unattended burn), extensibility (adapter registry), right-sized compute.

**Plans**: 2/2 plans executed

**Wave 1**

- [x] 16.1-01-PLAN.md — Provider-selection cost gate (SC-1/2/3): `providers` node + `providerSelection.js` + `PROVIDER_REGISTRY`, both waterfalls fanned out into per-provider `IF <provider> Enabled` gates [wave 1]

**Wave 2** *(blocked on Wave 1)*

- [x] 16.1-02-PLAN.md — Credit reporting + schedule safety (SC-4/5/6/7/8): `remaining_credits` convergence response, `check_provider_credits.py`, scheduled-maintenance `active: false` [wave 2, depends_on 16.1-01]

### Phase 16.2: Contacts Research + Judge Mirror (INSERTED)

**Goal**: The contacts enrichment path mirrors the companies path — the same web-research → judge → verdict chain runs on contacts, reusing Phase 16.1's node factories, so both object types share parameterized components (different targets, one set of building blocks). Delivers the symmetric, adapter-driven pipeline the project's extensibility requirement calls for.
**Depends on**: Phase 16.1
**INSERTED 2026-07-24** (decision: "16.1 symmetric, judge in 16.2"). 16.1 builds the fan-out/convergence symmetrically and leaves a documented insertion seam on the contacts branch (after `Normalize + Score`, before `Merge Winners`); this phase fills that seam. NOT free reuse — the research/judge JS is company-ICP-specific today (`computeEscalation`/`scoreResearchCandidates`/research prompt all bind company fields), so this phase must define the contact research prompt, contact-specific escalation reasons (which contact fields warrant adjudication — e.g. jobtitle/seniority conflicts), and contact verdict application, while reusing 16.1's `_if_bool_node`/Research-Trigger/Judge-Gate node factories.

**Success Criteria (draft — refine at plan time):**

  1. The contacts branch gains `Research Trigger Gate → IF Research Needed → Build Research Request → Claude Web Research → Validate Research Output → Judge Gate → IF Needs Judge → Build Judge Request → Judge Call → Apply Judge Verdict`, wired at the 16.1 seam, feeding `Merge Winners`.
  2. The research/judge node factories are shared with the companies branch (parameterized by target), not duplicated — altering the chain touches one factory.
  3. Contact research prompt + escalation reasons + verdict application are contact-appropriate (not company-ICP fields); off/none/absent providers still degrade gracefully (research-only path works).
  4. Offline tests mirror the companies research/judge coverage; full suite green; builder deterministic. No live calls in the suite.

**Plans**: 2/2 plans executed

**Wave 1**

- [x] 16.2-01-PLAN.md — Parameterize the 6 research/judge factories by target (default companies, byte-identical guard) + additive mergeContacts evidence/confidenceByField port (SC-2, SC-4 partial) [wave 1]

**Wave 2** *(blocked on Wave 1)*

- [x] 16.2-02-PLAN.md — Contact research→judge chain: contactResearch.js + contactJudge.js + mergeContacts.foldContactResearch siblings, wire the 10-node chain at the seam with row-recovery across HTTP hops (mirror bd682a2) + entry marker-strip + chosen_field allowlist, ENRICH_MERGE write-safety fold, seniority fetch, anthropic credential + deploy binding, mirrored tests incl. the item-flow row-recovery regression (SC-1, SC-3 honest-mirror, SC-4) [wave 2, depends_on 16.2-01]

**Follow-ups (Track B / deferred, not blocking 16.2):**
- **fetch-by-objectId** — PROMOTED 2026-07-28 to **Phase 16.4**. Genuine HubSpot private-app events carry only `objectId`/`objectType`; both the contacts and companies chains are verified against synthetic/direct-field (caller-envelope) payloads only. Blocks live Track B for real HubSpot events.
- **companies stale-timestamp** — PROMOTED 2026-07-28 to **Phase 16.3**. `lv_*_verified_at` refresh-on-non-promote (gpt #6) was fixed on the CONTACTS path; the companies path has the same latent issue.
- **E2E conflict lane** — the row-flow harness seeds a gap, so the full conflict→escalation→judge→cap-demote lane is exercised only by pure-function unit tests, never end-to-end through compiled node bodies. A live/simulated conflict-seed run would close this.
- **X1 companies row-loss** was found + FIXED this session (bd682a2) — but neither research/judge chain has run LIVE yet; verify on the first Track B run.

### Phase 16.3: Companies Stale Timestamp Fix

**Goal**: The companies path stamps its `lv_*_verified_at` cache-key datetimes ONLY when a field is actually promoted, so a `needs_review`/stale-but-unpromoted candidate can never mark itself fresh and suppress the next stale-refresh forever — mirroring the fix already shipped on the contacts path (Phase 16.2, gpt #6).
**Depends on**: Phase 16.2
**INSERTED 2026-07-28** (promoted from the Phase 16.2 "companies stale-timestamp" Track-B follow-up). `mergeContacts.js:183-194` moved the `cacheKeys[...]` write inside the `decision === "promote"` branch and left an explicit NOTE that `mergeCompanies.js` has the same latent issue, deliberately unfixed there to keep Plan 16.2-01's frozen companies byte-identity guard green. That guard has now discharged its purpose (the 16.2 mirror shipped), so this phase performs the fix plus the deliberate, reviewed re-baseline of the frozen fixture.

**Success Criteria (draft — refine at plan time):**

  1. `mergeCompanies.js` stamps `cacheKeys[COMPANY_CACHE_KEY_FIELDS[field]]` only inside the `decision === "promote"` branch — a structural mirror of `mergeContacts.js`, verified by reading both.
  2. Unit tests mirror `tests/n8n/mergeContacts.test.mjs:126-144`: a stale-but-unpromoted `lv_org_type`/`lv_produces_content` emits NO `lv_*_verified_at`; a promoted one still does.
  3. END-TO-END FUNCTIONAL validation (not just the pure function): the bug and its fix are demonstrated through the COMPILED `Merge Company` Code-node body as emitted by `build_enrichment_cloud()` — a stale-unpromoted companies row driven through the real chain emits no cache-key stamp, and the same row on the pre-fix build does. Red-before-green is required evidence, not an assertion of intent.
  4. `tests/fixtures/companies_jscode_frozen.json` is re-baselined as an EXPLICIT, reviewed act in its own commit; the diff is confined to the `Merge Company` node — the other six frozen nodes stay byte-identical.
  5. `wf_enrichment_cloud.json` / `wf_enrichment_local_live.json` regenerated; builder deterministic (rebuild twice, no diff).
  6. Full offline suite green with zero regressions vs the 346 pytest / 228 node baseline. No live calls.

**Plans**: 1 plan

Plans:
- [x] 16.3-01-PLAN.md — Red-before-green compiled-node proof, the promote-branch cache-key fix + retired contacts NOTE, and the bounded reviewed re-baseline of the frozen companies fixture

### Phase 16.4: Fetch By ObjectId

**Goal**: A genuine HubSpot private-app webhook event — which carries only `objectId`/`objectType` and none of the identity fields — drives a complete enrichment run, because the workflow fetches the current record from HubSpot by id instead of reading identity fields off the event body. Unblocks every meaningful live Track-B verification.
**Depends on**: Phase 16.3
**INSERTED 2026-07-28** (promoted from the Phase 16.2 "fetch-by-objectId" Track-B follow-up; originally deferred in Phase 16 Task 6 as a documented budget carve-out). `ENRICH_PARSE_EVENT_CLOUD` (`build_cloud_workflows.py:3040-3046`) spreads the raw event (`...event`) so that Build Identity / Build Company Identity keep working against a direct-field TEST payload; its own comment states a real HubSpot event carries none of those fields, so on the live path both identity builders see only `object_id`/`object_type`. Until this lands, a live run exercises only the synthetic caller-envelope path and therefore cannot verify the bd682a2 row-loss fix under real conditions.

**Success Criteria (draft — refine at plan time):**

  1. A fetch-by-id node (HubSpot credential-bound, per object type) sits between `Parse HubSpot Event` and the identity builders; Build Identity / Build Company Identity read the FETCHED record by node name, never the raw spread event.
  2. A bare HubSpot event payload — `{objectId, objectType, subscriptionType, propertyName, occurredAt}` with NO email/domain — produces populated `identity_keys` for both the contacts and companies branches.
  3. The existing direct-field / caller-envelope payload path keeps working (back-compat), including the per-request `providers` selection resolution.
  4. Row-flow integrity across the new HTTP hop is proven the bd682a2 way — node-name recovery, not `$json` — by an item-flow regression test mirroring `tests/n8n/researchChainRowFlow.test.mjs`.
  5. Test coverage at three levels: UNIT (identity extraction from a fetched record), INTEGRATION (Parse Event → fetch → identity builder chain over compiled node bodies), and END-TO-END FUNCTIONAL (a bare-objectId event driven through the full compiled contacts AND companies chains to a patch payload).
  6. A fetch failure (404/401/5xx) degrades safely — no create, no clobber — consistent with the `lookup_failed` create→skip precedent from Phase 16-01.
  7. Full offline suite green, zero regressions; builder deterministic. No live calls in the suite.

**Note (planning, 2026-07-28):** criterion 1's literal wording ("between `Parse HubSpot Event` and the identity builders") was CORRECTED at plan time by 16.4-RESEARCH.md. Placing a gate on the `Route By Object Type` -> identity-builder edge breaks `tests/test_cloud_write_path.py::test_object_type_router_sends_companies_events_to_the_company_branch`, which pins those exact edge targets — and bare-event-ness is not computable there anyway, since `identity_keys` does not exist until the identity builder runs. The lane is therefore placed immediately AFTER each identity builder (`Build (Company) Identity -> IF (Company) Bare Event -> HubSpot (Company) Fetch By Id -> Adapt (Company) Fetch By Id -> Enrichment Gate / Company Gate`), which reuses the `identity_keys` already computed, converges back into the existing gate, and leaves the pinned router edges untouched. Fetch-by-id uses the native HubSpot node's `search` operation filtered on `hs_object_id EQ` — n8n's V2 single-record retrieval operation still routes to HubSpot's sunset Contacts v1 / legacy Companies v2 endpoints and returns a non-flat property shape incompatible with every downstream consumer.

**Track-B dependency (MEDIUM confidence, unproven against portal 22617666):** the whole design rests on HubSpot's CRM v3 Search API accepting `hs_object_id` as a filterable property with `EQ`. Corroborated by practitioner usage; not confirmed by HubSpot's own Search guide and not testable within this phase's offline-only fence. Recorded as an explicit live checkpoint with a one-call verification and a bounded fallback (credential-bound raw HTTP GET to `/crm/v3/objects/{type}/{id}?properties=`, which changes only the two fetch nodes).

**Plans**: 2 plans

Plans:
- [x] 16.4-01-PLAN.md — Tracer: the fetch-by-objectId lane wired end-to-end on contacts (pure adapter module, credential-bound search-by-`hs_object_id` node, node-name row recovery, identity_keys backfill) plus the new bare-event e2e harness, then mirrored onto companies
- [x] 16.4-02-PLAN.md — Unit tier on the pure adapter, integration/row-flow regression across the new hop, caller-envelope back-compat, safe-degradation cases, pytest topology + generic credential guard, and the recorded Track-B live checkpoint

### Phase 16.5: Deliberate Research/Escalation Enablement

**Goal**: An operator can deploy a research- and escalation-enabled build of the enrichment workflow as an explicit, auditable act, WITHOUT the committed workflow JSON ever carrying those flags on — and the live run that follows finally exercises the web-research → judge lane against real HubSpot, verifying the `bd682a2` row-loss fix that has never executed live.
**Depends on**: Phase 16.4
**INSERTED 2026-07-28** (user directive: "rebuild with research + escalation enabled and fire the final run"). `ALLOW_WEB_RESEARCH` and `ALLOW_SONNET_ESCALATION` are baked as literal `false` into every Cloud Code node by `_flag_const(..., cloud=True)` — deliberately, per Phase 16's Criterion 5 (zero `$env`/`$vars` may survive in a built Cloud workflow), so there is no runtime toggle by design. Enabling therefore requires a build- or deploy-time decision, and the naive fix (flipping `CONFIG_FLAG_DEFAULTS`) is unacceptable: it would make EVERY future build ship LLM-spending paths on by default, and a rebuild-and-commit by anyone would silently arm production.

**Success Criteria (draft — refine at plan time):**

  1. The committed `n8n/wf_*.json` continue to carry `ALLOW_WEB_RESEARCH = false` and `ALLOW_SONNET_ESCALATION = false`. This is asserted by a test, so an enabled build can never be committed by accident.
  2. Enablement is an explicit, visible operator act (a deploy-time flag or equivalent), never an ambient environment variable that could silently change what a plain rebuild produces. The deterministic-rebuild invariant is preserved: the same source always yields the same committed JSON.
  3. The enablement mechanism is a pure, offline-testable transformation over a workflow dict — mirroring `bind_credentials()`'s existing precedent — and FAILS CLOSED if it does not find exactly the flag constants it expects to change (a silent no-op that deploys a disabled workflow while reporting success is the failure mode to prevent).
  4. Criterion 5 still holds on the enabled build: zero `$env`/`$vars` anywhere, no secret literal committed, `tests/test_architecture_guard.py` green.
  5. Cost controls remain intact and provably so: `MAX_WEB_RESEARCH_PER_RUN` and `MAX_SONNET_VALIDATIONS_PER_RUN` still bound the run, and enabling research does NOT enable HubSpot record writes (`ALLOW_HUBSPOT_RECORD_WRITES` stays false).
  6. Full offline suite green, zero regressions vs the 422 pytest / 272 node baseline; builder deterministic.
  7. **Live**: one enabled run fires against contact 201, the research→judge lane executes, and the row survives every HTTP hop to `Merge Winners` — verifying `bd682a2` live for the first time. Zero HubSpot writes; the run is inspected node-by-node, not judged by its response body alone.
     - *Planning note (2026-07-28):* `bd682a2` is titled "recover row across HTTP hops in **companies** research/judge chain" — its fix sites are `Validate Research Output`/`Apply Judge Verdict` and its symptom is a null merge at `Merge Company`. Contact 201 drives the CONTACTS branch, whose row-recovery is the 16.2-02 mirror of that fix. Plan 02 therefore satisfies criterion 7 as written and verifies the contacts mirror at `Merge Winners`; Plan 03 fires the same enabled build at a real company record to verify the LITERAL `bd682a2` at `Merge Company`. If Plan 03 is declined, the phase record must state that the literal companies fix remains live-unverified.

**Plans**: 3 plans

Plans:
- [x] 16.5-01-PLAN.md — deploy-time research/escalation overlay (pure, fail-closed), enabled-build invariants, and the offline oracle predicting both live lanes (COMPLETE 2026-07-28, see 16.5-01-SUMMARY.md)
- [x] 16.5-02-PLAN.md — LIVE: contact 201, research→judge lane executed, row survived every HTTP hop to a non-null `Merge Winners` (COMPLETE 2026-07-28, criterion 7 MET for contacts)
- [x] 16.5-03-PLAN.md — LIVE: BLOCKED on the night by BUG 10; the literal `bd682a2` at `Merge Company` was subsequently verified live on 2026-07-29 in the Phase 16.7 armed window (execution 12) once BUG 10 was fixed. See `.planning/phases/16.7-write-path-canary/16.7-02-SUMMARY.md`.

**CLOSED 2026-07-29. Outcome against the seven criteria:**

  1. **MET** — committed JSON still carries both flags `false`, asserted by `tests/test_enabled_build_invariants.py`.
  2. **MET** — `ENABLE_BAKED_FLAGS` is an explicit operator act with a name deliberately distinct from the `.env`-resident `ALLOW_WEB_RESEARCH`/`ALLOW_SONNET_ESCALATION`, so a routine rebuild from a developer machine cannot arm production. Deterministic rebuild preserved.
  3. **MET** — `enable_baked_flags()` is pure and deep-copying, and fails closed via a post-rewrite re-scan. Widened on 2026-07-29 (`7f0dce4`) to cover the write-safety and value-bearing allowlist flags, with the same contract.
  4. **MET** — zero `$env`/`$vars` in every deployed body, re-verified by API read-back on 2026-07-29.
  5. **MET** — cost caps unchanged at 10/10 through every armed window, and arming research provably did not arm writes (they are separate overlay entries, and enabling writes without an allowlist is now refused outright).
  6. **MET** — suite has grown 422 → 533 pytest and 272 → 278 node with zero regressions.
  7. **MET, both branches.** Contacts mirror verified live 2026-07-28 (`Merge Winners` non-null). The LITERAL companies `bd682a2` verified live 2026-07-29, execution 12 — `Merge Company` merge non-null after BUG 10's transport fix. The planning note's caveat is discharged: the literal fix is no longer live-unverified.

### Phase 16.6: Companies Search Transport Fix

**Goal**: Every `company:search` in the system returns real records live, so the companies enrichment branch, all three schedule predicates, and the review loop can actually run — unblocking the literal `bd682a2` verification and the companies half of the pipeline.
**Depends on**: Phase 16.5
**INSERTED 2026-07-28** (BUG 10, found live during the 16.5 companies canary). n8n's HubSpot node returns an item with **`json: null`** for `resource: company, operation: search`, while the byte-identical request succeeds directly against the CRM v3 API (HTTP 200, `total:1`, real record). It does not throw even with `onError` cleared, so nothing surfaces as an error — the null simply propagates. The `resource: contact` twin, with structurally identical configuration, works correctly. Downstream this reads as `unrecognized response shape` -> `lookup_failed` -> gate `skip` -> `Normalize + Score Company` emits zero rows -> the companies research/judge lane never executes.

**Blast radius (verified by enumeration, not assumed): SIX nodes across TWO workflows** — `HubSpot Company Search` and `HubSpot Company Fetch By Id` in `wf_enrichment_cloud.json`; `SJ-1 Search (input-gap scan)`, `SJ-2 Search (stale refresh)`, `SJ-3 Search (requested poller)` and `Review Search (approved=true)` in `wf_scheduled_maintenance_cloud.json`. None had ever run live. Every contact-resource search is unaffected and must stay untouched.

**Success Criteria (draft — refine at plan time):**

  1. All six `company:search` nodes retrieve real records live, verified by read-back of an actual execution — not by a green offline suite.
  2. The transport change is confined to company searches. Every `contact:search` node keeps its current type and parameters byte-identical, proven by diff — contacts is the one path known to work live and must not regress.
  3. Whatever replaces the node stays credential-bound: zero `$env`/`$vars` in any built Cloud workflow, no secret literal committed, and the node appears in `NODE_CREDENTIAL_MAP` so `bind_credentials()` fails closed if it is ever unmapped.
  4. The response reaches the existing adapters in a shape they already parse (`ENRICH_ADAPT_CO_SEARCH`, `adaptFetchById.js`) — if an adapter must change, that is called out explicitly rather than absorbed.
  5. `company:create` and `company:update` are ALSO never-run-live; state explicitly whether they share the defect, and if they are left unfixed say so rather than implying coverage.
  6. Full offline suite green, zero regressions vs the 459 pytest / 275 node baseline; builder deterministic; the 7 frozen companies node bodies unmoved.
  7. **Live**: a companies bare-event run reaches `Merge Company` with a NON-NULL merge — the literal `bd682a2`, still unverified — with zero HubSpot writes.

**Plans**: 16.6-01 (transport migration, code-complete 2026-07-28 — commits `8a30cc2`, `9e60181`, `c704865`). Criteria 2-6 met offline; criteria 1 and 7 are LIVE-UNVERIFIED and remain open — the deployed build is still the pre-fix one.

### Phase 16.7: Write-Path Canary

**Goal**: The first HubSpot write in the project's history, bounded to one allowlisted test record, proving live that the non-clobber merge writes what policy permits and protects what it does not — the core value claim (`never clobbers HubSpot data`) has zero live evidence today because nothing has ever been written.

**Depends on**: Phase 16.6 (its live verification runs in the same armed window)
**INSERTED 2026-07-29.**

Current live posture: `ALLOW_HUBSPOT_RECORD_WRITES="false"`, `ALLOW_HUBSPOT_CREATE="false"`, `TEST_RECORD_IDS=""` — an empty allowlist that denies everything (`_writeSafetyAllows()` returns false with no allowlist entries). Nothing has ever been written to HubSpot. Zero-write oracles: contact **201** `lastmodifieddate` `2026-07-18T01:14:03.751Z`, company **9604614548** `hs_lastmodifieddate` `2026-07-28T03:42:15.843Z`.

Enablement mechanism is in place as of `7f0dce4`: `ENABLE_BAKED_FLAGS` now carries the write-safety constants and value-bearing allowlist flags, refusing to arm writes without a non-empty allowlist in the same request. No rebuild is needed to run the canary.

**Success Criteria (draft — refine at plan time):**

  1. Exactly one HubSpot record is modified — contact `201` — proven by a before/after read of BOTH oracles: 201's `lastmodifieddate` advances, company `9604614548`'s `hs_lastmodifieddate` is byte-identical.
  2. `ALLOW_HUBSPOT_CREATE` stays `"false"` throughout; no create node executes; no new record appears in the portal.
  3. A field the policy protects (a `manual_protected` / `fill_blank_only` property with an existing value) is provably NOT overwritten — quoted before and after. This, not the write itself, is the core-value proof.
  4. A field the policy permits is written with its full source-metadata set (`_source`, `_confidence`, `_verified_at`, `_verified_by_model`, `_validation_status`), quoted from the record after the run.
  5. The run is judged node-by-node from the execution API's `runData`, never from the webhook's HTTP status or body.
  6. The deployment is restored to the disabled build afterwards, verified by API read-back: both write-safety constants back to `"false"` and the allowlist back to empty.
  7. Every change to record `201` is reversible, and the rollback is exercised rather than assumed (`scripts/rollback_canary_proof.py` exists for this).

**Plans**: 2 plans

Plans:
- [x] 16.7-01-PLAN.md — OFFLINE (COMPLETE 2026-07-29, commits 5cab661/38f3ebb/1e1a51c): BUG 11 — both HubSpot UPDATE nodes ship as native nodes with an EMPTY field map and reference the computed patch nowhere (documented in `build_cloud_workflows.py` as placeholders "populated at deploy/operator-config time", and no such deploy-time population exists). Capture it red, move both onto a credential-bound `httpRequest` PATCH that fails hard on rejection, leave creates native and pinned as unverified, and emit the exact live PATCH Plan 02 must confirm. Without this, criteria 3 and 4 are unreachable and criterion 3 would pass vacuously.
- [~] 16.7-02-PLAN.md — LIVE (EXECUTED 2026-07-29, PARTIAL — see 16.7-02-SUMMARY.md): arm `ALLOW_HUBSPOT_RECORD_WRITES` with `TEST_RECORD_IDS=201` only, gate on API read-back, fire the companies event FIRST (closes 16.6 criteria 1 and 7 and tests the allowlist empirically at zero LLM cost) then the contacts event, prove a protected field unchanged and a permitted field written from fresh record reads, roll contact 201 back and verify by re-read, and restore the disabled build unconditionally.

**Sequencing decision**: the BUG 10 companies verification runs in the SAME armed window, fired first. The companies record is deliberately NOT allowlisted, so that run is simultaneously the containment test — proving `TEST_RECORD_IDS` bounds the blast radius empirically rather than by reading `_writeSafetyAllows()`.

**Criterion 4 restated**: Phase 15 retired flat per-field metadata properties for one provenance JSON blob, and that blob carries no `_verified_by_model` key. Criterion 4 is satisfied in its Phase-15 form (written field + provenance entry + cache-key datetime, quoted from a post-run read), stated explicitly rather than silently reinterpreted.

### Phase 16.8: Row-Carry Fix (BUG 12)

**Goal**: The contacts write path can actually reach HubSpot. Today it cannot, for any record, under any flag combination.

**Depends on**: Phase 16.7
**INSERTED 2026-07-29** — found live in the 16.7 armed window, execution 13.

`Merge Winners → Set Data Quality + Gap Flag → Decide Action`. `Set Data Quality + Gap Flag` is `n8n-nodes-base.set` typeVersion `3.4` with `"options": {}`; `includeOtherFields` is unset and defaults to **false** in Set v3.x, so the node emits ONLY `{data_quality, gap_flag}` and discards `merge`, `existingRecord`, `object_id` and `scored`. `Decide Action` then resolves `row.existingRecord.hs_object_id` to `null` and `_buildContactPatch(undefined)` to `{}`, so `_writeSafetyAllows()` denies regardless of the allowlist, no `action` key is emitted, `IF Enrich` receives zero items and `HubSpot Update` never runs. Present in execution 8 (2026-07-28) too — pre-existing, invisible while writes were disabled because the webhook still returned a plausible 200.

**Success Criteria (draft — refine at plan time):**

  1. A red test, run against the committed artifact, asserts `Decide Action`'s input carries `existingRecord`, `merge`, `object_id` and `scored` — failing today.
  2. The fix is the node's own `includeOtherFields` option, not a hand-rolled spread in a Code node — the platform feature that exists for exactly this.
  3. Every OTHER `n8n-nodes-base.set` node in a row-carrying position across all three workflows is swept for the same defect and each is either fixed or explicitly recorded as terminal-by-design.
  4. Offline suite green with zero regressions; builder rebuild deterministic.
  5. **Live**: the 16.7 armed window re-run unchanged reaches `HubSpot Update` with a real `hs_object_id` and a non-empty properties patch — closing 16.7's SC-1, SC-3 (at write time), SC-4 and SC-7.

**Plans**: 16.8-01 (COMPLETE 2026-07-29, commits `fb87cb5` + the Code-node follow-up). Criterion 2 deviated deliberately: n8n's `options.includeOtherFields` was tried and deployed and did NOT work (execution 14 read it back live while the node still dropped the row), so the node became a Code node that spreads explicitly — recorded rather than silently substituted.

### Phase 16.9: Create-Path Fix (BUG 13) and Company Write Verification

**Goal**: `company:update` and `company:create` — neither of which had ever run live — write correctly, or their blockers are on the record.

**Depends on**: Phase 16.8
**INSERTED 2026-07-29.**

**BUG 13 — FIXED (commit `c6462e9`).** Both create nodes were broken two ways at once: `additionalFields: {}` discarded the computed patch (BUG 11's twin), AND they read fields absent from their own input — `HubSpot Company Create` read `$json.name || $json.identity_keys.companyName || $json.identity_keys.domain` and `HubSpot Create` read `$json.properties.email`, while `Decide Action`/`Decide Company Action` emit exactly `{action, object_type, hs_object_id, gap_flag, needs_review, properties}` (verified from live execution 12). Dereferencing the absent `identity_keys` would have thrown. Both now POST `{"properties": $json.properties}` to the CRM v3 collection endpoint, credential-bound, error-swallowing off. Five stale native-node pins retargeted rather than deleted.

**BUG 14 — OPEN, blocks the company write path.** Live, execution 16, against a throwaway company created and deleted for the purpose: `HubSpot Company Update` issued `PATCH {"properties":{"lv_enrichment_status":"complete"}}` and HubSpot rejected it —

```
Property "lv_enrichment_status" does not exist   (PROPERTY_DOESNT_EXIST, portal 22617666)
```

The execution failed loudly rather than returning a plausible 200 — the no-`onError` decision from 16.7-01 working exactly as intended.

Enumerated against the live portal schema, exactly **two** company properties the pipeline depends on do not exist:

| property | used by |
|---|---|
| `lv_enrichment_status` | `ENRICH_DECIDE_CO_CLOUD` writes it on every companies run (`"complete"` / `"needs_review"`); SJ-3's 15-minute poller filters on it |
| `lv_enrichment_requested` | SJ-3's poller filters on it |

Everything else the write path touches exists (`lv_enrichment_needs_review`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json`, `lv_enrichment_provenance`, `lv_org_type`, `lv_produces_content`, `lv_icp_tier`, `lv_icp_fit_score`). `scripts/sync_hubspot_properties.py` does not define either name.

**Consequence**: EVERY companies write fails, and `company:create` cannot be exercised either since it emits the same property. This also means SJ-3's poller could never have matched anything.

**Decision required (operator)**: creating two custom properties in the production portal is a schema change to the user's CRM and was deliberately not performed unilaterally. The alternative — stop emitting `lv_enrichment_status` — would silently drop a documented control property and break SJ-3's design.

**Success Criteria (draft — refine at plan time):**

  1. The two missing properties either exist in the portal (created through the repo's migration tooling, with an undo manifest) or the pipeline stops depending on them — decided explicitly, not defaulted.
  2. A guard asserts every property name the Cloud workflows write or filter on exists in the snapshotted portal schema, so this class cannot recur silently.
  3. **Live**: a companies run against a throwaway record reaches `HubSpot Company Update` with HTTP 2xx and the patch lands, verified by re-read.
  4. **Live**: `company:create` runs once against a domain with no existing record, and whatever it creates is deleted afterwards.

**Plans**: TBD

## Milestone 3 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 11. Company Branch & Provider Contract Hardening | 1/1 | Complete | 2026-07-20 |
| 12. Taxonomy Single-Source | 1/1 | Complete | 2026-07-20 |
| 13. Web Research Retrieval & Validation | 1/1 | Complete | 2026-07-21 |
| 14. Judge Wiring | 1/1 | Complete | 2026-07-21 |
| 15. HubSpot Property Migration | 1/1 | Complete | 2026-07-22 |
| 15.5. Tiered Candidate Adjudication (INSERTED) | 1/1 | Complete | 2026-07-23 |
| 16. Scheduled Workflows & Review Surface | 2/2 | Complete | 2026-07-23 |
| 16.1. Provider Selection, Credit Reporting & Schedule Safety (INSERTED) | 2/2 | Complete | 2026-07-24 |
| 16.2. Contacts Research + Judge Mirror (INSERTED) | 2/2 | Complete | 2026-07-24 |
| 16.3. Companies Stale-Timestamp Fix (INSERTED) | 1/1 | Complete | 2026-07-28 |
| 16.4. Fetch-By-ObjectId (INSERTED) | 2/2 | Complete | 2026-07-28 |
| 16.5. Deliberate Research/Escalation Enablement (INSERTED) | 3/3 | **Complete** — all 7 criteria met; criterion 7 verified on BOTH branches (companies closed 2026-07-29 via 16.7) | 2026-07-29 |
| 16.6. Companies Search Transport Fix (INSERTED) | 1/1 | **Complete** — criteria 1 & 7 VERIFIED LIVE (execution 12, non-null Merge Company) | 2026-07-29 |
| 16.7. Write-Path Canary (INSERTED) | 2/2 | **Complete** — first HubSpot write in project history; protected fields provably survived it; rolled back | 2026-07-29 |
| 16.8. Row-Carry Fix (BUG 12) (INSERTED) | 1/1 | **Complete** — Set node replaced with a row-spreading Code node; verified live (execution 15) | 2026-07-29 |
| 16.9. Create-Path Fix (BUG 13) + Company Writes (INSERTED) | 0/? | BUG 13 fixed (`c6462e9`); **BUG 14 OPEN** — `lv_enrichment_status` / `lv_enrichment_requested` do not exist in the portal, so every companies write fails | — |
