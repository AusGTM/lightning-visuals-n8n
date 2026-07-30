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

✅ **SHIPPED 2026-07-29** — Phases 11–16.10 (16 phases, 10 inserted), 22 plans. Live company provider
waterfall + web retrieval for the two ICP fields providers cannot supply; first HubSpot writes in
project history with the non-clobber guarantee live-proven; 25 numbered bugs resolved. Full detail:
[`.planning/milestones/v0.3-ROADMAP.md`](milestones/v0.3-ROADMAP.md) ·
requirements: [`.planning/milestones/v0.3-REQUIREMENTS.md`](milestones/v0.3-REQUIREMENTS.md)

---

# Milestone 4 — Reachability & Verification Debt (v0.4)

✅ **SHIPPED 2026-07-29** — Phases 17–19, 6 plans. BUG 23 fixed (`contact:create` structurally
reachable, dual live canary); numeric industry code neutralized in normalization + waterfall;
both copy-loop fields wired with live producers; six-item verification ledger discharged 6/6
(BUG 26 deployment drift found and same-day resolved; armed `company:update` canary passed,
deployment restored disarmed). Full detail:
[`.planning/milestones/v0.4-ROADMAP.md`](milestones/v0.4-ROADMAP.md) ·
requirements: [`.planning/milestones/v0.4-REQUIREMENTS.md`](milestones/v0.4-REQUIREMENTS.md)

---

# Milestone 5 — Lusha v3 & Armed Enrichment (v0.5)

## Overview

Two forcing functions drive this milestone. First, Lusha v2 dies 2026-11-18 and the measured v2
economics are broken anyway — ~4.65 credits/reveal from phone-field bundling means a full sweep
(~12.6k credits) exceeds the current ~3.9k balance. The v3 migration is therefore a cost fix, not
just deadline compliance: `reveal[]` derived from the gate's `missingFields` makes the field policy
the cost control, and staged Lusha IDs make re-enrichment free. Second, the full enrichment pipeline
(providers + Haiku research on `claude-haiku-4-5` + Sonnet judge) has never run end-to-end with
writes armed — every armed canary so far proved a single write path.

Sequencing is deliberate: all autonomous-buildable work (code, tests, disarmed redeploys) lands
first — Lusha v3 migration, then transport/schema hygiene — because arming HubSpot writes is
operator-gated. The armed canary is the final phase, so one audited armed window live-validates
everything at once: v3 + selective reveal, the Haiku research-model swap, and the hygiene changes
(enum-valid `lv_org_type` writes, policy-promoted country region). The cost ledger from that run
calibrates full-sweep planning.

Deferred to v0.6: HubSpot-side ICP formula (the `1 + 1` placeholder) and JTBD 2 rubric sign-off —
downstream-owner decisions.

## Phases

- [ ] **Phase 20: Lusha v3 Migration** - Both lanes swap to POST `/v3/*/search-and-enrich` with selective reveal, ID staging for free re-enrichment, and a verified disarmed redeploy before the 2026-11-18 v2 sunset
- [ ] **Phase 21: Transport & Schema Hygiene** - Retire the last native search node (Dedupe Search), `lv_org_type` text→enumeration one-way door with rollback documented first, `lv_country_region_normalized` field-policy entry
- [ ] **Phase 22: Armed E2E Enrichment Canary** - Final, operator-gated phase: full pipeline (providers + Haiku research + Sonnet judge) end-to-end on allowlisted records with writes armed, live-validating Phases 20–21 in one audited window, with a calibrated cost ledger

## Phase Details

### Phase 20: Lusha v3 Migration

**Goal**: Both Lusha lanes (contacts + companies) run on the v3 API with selective reveal as the cost control and staged IDs for free re-enrichment — verified by both test suites and redeployed disarmed, well ahead of the 2026-11-18 v2 sunset.
**Depends on**: Phase 19 (v0.4 complete; live deployment current and disarmed)
**Requirements**: REQ-lusha-v3-contract-probe, REQ-lusha-v3-request-builders, REQ-lusha-selective-reveal, REQ-lusha-id-staging, REQ-lusha-v3-normalize, REQ-lusha-v3-verification
**Success Criteria** (what must be TRUE):

  1. The v3 contract is documented from live probes with minimal credit spend — `POST /v3/contacts/search-and-enrich`, `POST /v3/companies/search-and-enrich`, and the two-step `search` → `enrich` pair, capturing the envelope, `has`/`canReveal`/`billing` fields, and error shapes (ZoomInfo-GTM-probe precedent) — and `check_provider_credits.py` reads usage correctly against `GET /v3/account/usage`.
  2. Both lanes issue `POST /v3/*/search-and-enrich` with params in the body, identity keys mapped unchanged (email | name+company/domain | domain), and `api_key` header auth retained — exercised by the builders, their local-live variants, and `scripts/dryrun_batch.mjs`.
  3. *(re-scoped 2026-07-30 — probe refuted the cost premise, see docs/LUSHA-V3-CONTRACT.md §6)* A contact record that already holds phone/mobile in HubSpot produces a v3 request whose `reveal[]` (derived from the gate's `missingFields`) omits phones — as PII-minimization hygiene; v3 bills a flat 1 credit per first-time contact enrich regardless of revealed fields, so the projected full-sweep cost (~1 cr/contact + 2 cr/company, id re-enrich free) fits the ~3.9k credit balance with headroom. Companies lane has no reveal mechanism — no reveal code for it.
  4. A matched record persists `lusha_contact_id` / `lusha_company_id` staging properties, and a re-enrichment run passes the stored ID so already-revealed data comes back at `canReveal.credits: 0` (no new spend).
  5. Downstream is untouched: `lushaCandidates` in `normalizeProviders.js` parses the v3 envelope into candidates field-identical to v2 output (merge/score/staging unchanged); v2-pinned tests are migrated, the frozen fixture re-baselined, both suites green; a disarmed redeploy read-back shows v3 URLs live and zero v2 URLs remaining.

**Plans:** 5 plans

Plans:
- [ ] 20-01-PLAN.md — Live v3 contract probe: both lanes + two-step + reveal A/B + id reuse + no-match, credit-capped, with a blocking contract-review gate
- [ ] 20-02-PLAN.md — v3 request builders both lanes (5 emission sites + dry-run harness) with selective reveal from the gate's missingFields
- [ ] 20-03-PLAN.md — `lushaCandidates()` v3 envelope adapter, v3 fixtures, v2 branches and assertions migrated
- [ ] 20-04-PLAN.md — `lusha_contact_id` / `lusha_company_id` staging: write-through, search read-back, request-side reuse
- [ ] 20-05-PLAN.md — Zero-v2-URL guard, frozen fixture accounted for, both suites green, disarmed redeploy + live read-back

### Phase 21: Transport & Schema Hygiene

**Goal**: The last structurally fragile transport and the two known schema debts are cleared — no native search nodes remain, `lv_org_type` is a real enumeration, and the country-region research value can promote under policy — all buildable and verifiable without arming writes.
**Depends on**: Phase 20
**Requirements**: REQ-dedupe-transport-swap, REQ-orgtype-enumeration, REQ-country-region-policy
**Success Criteria** (what must be TRUE):

  1. `Dedupe Search (candidate contacts)` runs through the credential-bound httpRequest envelope (BUG-10/22/23 mechanism) and no native HubSpot search node remains in any deployed workflow; the weekly sweep stays classify-only, writing only the needs-review flag through the existing gated PATCH.
  2. A rollback path for the `lv_org_type` text→enumeration conversion is documented BEFORE the migration runs (one-way door discipline).
  3. `lv_org_type` is a HubSpot enumeration with all existing values preserved, and pipeline writes validate against the enum options (no silent 400s).
  4. `lv_country_region_normalized` has a `config/field_policy.yaml` entry, so the research value the pipeline already produces can promote under policy instead of defaulting to staging-only.

**Plans**: TBD

### Phase 22: Armed E2E Enrichment Canary

**Goal**: The full enrichment pipeline — provider waterfall (now Lusha v3) + Haiku web research + Sonnet judge — is proven live with writes armed on allowlisted records, live-validating the Phase 20–21 changes in one audited operator window, and its true per-record cost is measured for full-sweep planning.
**Depends on**: Phases 20 and 21 (final phase — arming writes is operator-gated; one armed window then validates the v3 migration AND the hygiene changes together)
**Requirements**: REQ-armed-e2e-canary, REQ-canary-cost-ledger
**Success Criteria** (what must be TRUE):

  1. One armed end-to-end enrichment on allowlisted record(s) lands staged fields, source metadata, and promoted canonical writes in HubSpot, produced by the complete chain: provider waterfall + Haiku web research (`claude-haiku-4-5`, first live validation of the research-model swap) + Sonnet judge.
  2. The run live-validates Phases 20–21: Lusha data arrives via v3 selective reveal (no reveal paid for a field the record already holds), and writes succeed against the migrated schema (`lv_org_type` accepted by the enumeration; `lv_country_region_normalized` promoted under its new policy entry).
  3. Neighbor (non-allowlisted) records are byte-untouched after the run.
  4. The run closes disarmed and audited: read-back shows every write flag `"false"` and the allowlist cleared.
  5. A cost ledger records actual spend — provider credit balances before/after and Anthropic tokens per call — against the 2026-07-30 estimates, producing a calibrated per-record cost figure that makes fleet-wide arming an informed operator decision.

**Plans**: TBD

## Milestone 5 Progress

**Execution Order:**
Phases execute in numeric order: 20 → 21 → 22 (autonomous-buildable work first; the operator-gated armed canary is last)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 20. Lusha v3 Migration | 0/5 | Planned | - |
| 21. Transport & Schema Hygiene | 0/? | Not started | - |
| 22. Armed E2E Enrichment Canary | 0/? | Not started | - |
