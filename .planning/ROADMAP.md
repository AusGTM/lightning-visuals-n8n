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

## Overview

No new capability ships this milestone — it clears debt the v0.3 close explicitly deferred rather
than papered over. Three unrelated defects, one genuinely risky: **BUG 23** left the enrichment
contacts lane's `contact:create` path structurally unreachable (a no-match search silently stops
the n8n chain rather than emitting a classifiable item), and the proven fix pattern (BUG 10, BUG 22)
means touching `HubSpot Search` — the single most live-proven node in the system, pinned
byte-identical in `tests/test_bug10_company_search_transport.py` by design to block exactly this
kind of drive-by migration. That risk gets its own phase, with mandatory before/after live-canary
evidence on both the newly-reachable path and the previously-proven one. Two small, independent,
offline-provable fixes follow (a normalization gap that let a numeric provider code win the
waterfall over text, and two known copy-loop gaps that leave properties permanently empty), then the
six `/gsd-verify-work` re-runs carried from the v0.3 goal ledger close the milestone. Phase numbering
continues from 16.10 — this milestone starts at Phase 17.

**Constraints that apply across all of Milestone 4:**

- All work stays on branch `feat/company-enrichment-icp-research`.
- Any live HubSpot canary follows the repo's established armed-window discipline: arm write gates
  via the deploy-time overlay only, target allowlisted test records only (`TEST_RECORD_DOMAINS` /
  `TEST_CONTACT_IDS`), restore the disarmed build afterwards, and read the deployment back to confirm
  disarmed state. Beware HubSpot search eventual consistency (~6s–3min propagation) and
  tick-predates-seed races — see the knowledge-base entry on scheduled-lane canary timing before
  scheduling any canary around a write.
- The contacts match path (`HubSpot Search` returning a hit, e.g. contact 201) is the single
  most live-proven path in the system. Any change to its transport requires explicit before/after
  live evidence — not an assumption that offline-green implies live-safe.
- Baseline offline suite: 587 pytest + node tests, run via `.venv/bin/python -m pytest` and
  `node --test tests/n8n/*.test.mjs` (see knowledge-base `test-suite-run-commands` — the directory
  form of the node test runner is broken on this Node version).

## Phases

- [ ] **Phase 17: Enrichment Contacts Reachability (BUG 23)** - Transport swap on `HubSpot Search` + `HubSpot Fetch By Id` makes `contact:create` reachable, byte-identical pin dropped for both nodes, dual live canary (match regression + no-match reachability) proves it, deployment restored disarmed
- [ ] **Phase 18: Normalization & Copy-Loop Fixes** - Numeric provider industry codes stop winning the waterfall over text; `lv_sponsorship_reliant` and `persona_group`/`lv_persona_group` stop being permanently empty
- [ ] **Phase 19: Verification Debt Closure** - The six `/gsd-verify-work` re-runs carried from the v0.3 goal ledger are executed and their outcomes recorded

## Phase Details

### Phase 17: Enrichment Contacts Reachability (BUG 23)

**Goal**: The enrichment contacts lane's `contact:create` path is live-reachable for a genuine
no-match event, and the existing live-proven match path is regression-checked, not assumed safe.
**Depends on**: Phase 16.10 (Milestone 3 close)
**Requirements**: REACH-01, REACH-02, REACH-03, REACH-04
**Detail**: This is the risky phase in the milestone. `HubSpot Search` is pinned byte-identical in
`tests/test_bug10_company_search_transport.py` by deliberate design — the guard exists specifically
to stop a drive-by migration of the one path in the system with the deepest live track record (the
entire 16.7 non-clobber canary chain runs through it). The plan must carry the same before/after
live-canary discipline BUG 10 and BUG 22 established, not a code-only transport swap. Follows BUG
22's proven pattern: move both nodes to the credential-bound httpRequest envelope transport (which
`ENRICH_ADAPT_SEARCH` and `adaptFetchById.js` already parse), including the `lookup_failed`
item-error mapping on a failed fetch.
**Success Criteria** (what must be TRUE):

  1. `HubSpot Search` and `HubSpot Fetch By Id` in the enrichment contacts lane run on the
     credential-bound httpRequest envelope transport (mirroring BUG 22), so a zero-hit search emits
     exactly one classifiable item instead of silently stopping the chain.
  2. Both nodes are dropped from the byte-identical pin in `tests/test_bug10_company_search_transport.py`
     with the same documented rationale as the prior two removals, and `bareEventChainFlow`'s http
     mocks are updated to model the native node's 0-item behavior (or the lane's test asserts no
     native search nodes remain) — the offline suite is green with zero regressions against the
     587 pytest / node baseline.
  3. Live canary case A (regression): an existing contact (e.g. 201) sent through the enrichment
     webhook still matches and enriches exactly as before the transport swap — before/after evidence
     is recorded, not asserted from the offline suite passing.
  4. Live canary case B (reachability): a nonexistent email sent through the enrichment webhook
     reaches `Decide Action` with `action: "create"`, write-gated — no HubSpot write occurs unless
     the deploy is deliberately armed for that allowlisted record.
  5. After both canaries, the deployment is restored to its disarmed state and read back from the
     live n8n instance to confirm no write gate was left armed.

**Plans**: 2 plans

- [ ] 17-01-PLAN.md — Transport swap + pin removal + harness reachability (offline, no live call)
- [ ] 17-02-PLAN.md — Dual live canary: match-path regression (A) + create-path reachability (B), restored disarmed

### Phase 18: Normalization & Copy-Loop Fixes

**Goal**: Two known, offline-provable data-quality gaps stop silently degrading enrichment output —
a numeric provider code no longer masquerades as a normalized industry value, and two ICP/persona
properties stop being permanently empty.
**Depends on**: Phase 17
**Requirements**: NORM-01, COPY-01, COPY-02
**Detail**: All three fixes are small, localized, and provable without any live call — each gets a
red-before-green test using the real conflict/gap shape already observed live (execution 19 for
NORM-01; the declared-but-never-copied candidate sources for COPY-01/COPY-02). Sequenced after
Phase 17 because both phases touch `scripts/build_cloud_workflows.py` (Phase 17 touches node
transport definitions; this phase touches the merge-call construction for `ENRICH_MERGE_CO` and
`ENRICH_MERGE`) — running them in phase order avoids stacking unrelated diffs in one rebuild.
**Success Criteria** (what must be TRUE):

  1. A numeric provider industry code (ZoomInfo's `"71"`) never survives normalization unchanged —
     reproduced from execution 19's real conflict (Apollo's `"media production"` vs ZoomInfo's
     `"71"`) with a red-before-green test.
  2. That same numeric code never wins the waterfall over provider text by confidence/priority
     ordering alone — the fix is proven against the same execution-19 shape, not just a synthetic case.
  3. `lv_sponsorship_reliant` is copied from its candidate source (`build_cloud_workflows.py`
     `ENRICH_MERGE_CO` researchData loop) into the companies merge call — a test proves the property
     populates from a real candidate instead of staying empty.
  4. `persona_group`/`lv_persona_group` is copied from its candidate source (`ENRICH_MERGE` winners
     loop) into the contacts merge call — a test proves the property populates from a real candidate
     instead of staying empty.
  5. The offline suite (587 pytest + node baseline) is green with zero regressions, and the workflow
     builder is deterministic (rebuild twice, no diff).

**Plans**: TBD

### Phase 19: Verification Debt Closure

**Goal**: The verification backlog carried out of v0.3 is closed — every deferred `/gsd-verify-work`
re-run has actually been executed against current state, with its outcome on record.
**Depends on**: Phase 18
**Requirements**: VERIFY-01
**Detail**: This phase does not build anything; it discharges a debt. The six re-runs are identified
from the v0.3 goal ledger / `STATE.md` Deferred Items at plan time (not enumerated here, since the
ledger is the source of truth and may itself have shifted since 2026-07-29), executed, and any new
defect a re-run surfaces is captured rather than silently absorbed into "passed."
**Success Criteria** (what must be TRUE):

  1. Every one of the six `/gsd-verify-work` re-runs carried from the v0.3 goal ledger is identified
     explicitly and re-executed against the post-v0.3-ship state.
  2. Each run's outcome (passed / human_needed / failed) is recorded against the item it verifies.
  3. Any defect a re-run surfaces is captured as a debug brief or backlog item — nothing is silently
     dropped to close the ledger.

**Plans**: TBD

## Milestone 4 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 17. Enrichment Contacts Reachability (BUG 23) | 0/TBD | Not started | - |
| 18. Normalization & Copy-Loop Fixes | 0/TBD | Not started | - |
| 19. Verification Debt Closure | 0/TBD | Not started | - |
