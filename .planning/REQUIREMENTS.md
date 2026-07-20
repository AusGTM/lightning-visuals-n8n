# Requirements: lv-n8n-poc

**Defined:** 2026-07-07
**Core Value:** The ICP scoring engine turns firmographic + enrichment signals into trustworthy, auditable A/B/C/D prioritization (with hard vetoes) and never clobbers HubSpot data — proven in dry-run locally.

Sources: `icp-scoring.md` (PRD, business rationale) and `CLAUDE.md` (SPEC, implementation contract).
v1 = Milestone 1 (local-first MVP). v2 = later HubSpot/n8n-dependent milestones.

## v1 Requirements

Milestone 1 scope. Each maps to exactly one roadmap phase.

### ICP Scoring

- [ ] **REQ-icp-scoring-model**: Compute a numeric ICP fit score from firmographic + enrichment signals available at scoring time (deal value excluded). Org type gov-body/league +40, content producer/broadcaster +20, individual club +5, other 0; produces content +20; ANZ geography +10; revenue $5–500M +10. (icp-scoring.md §5; CLAUDE.md §10)
- [ ] **REQ-anti-icp-vetoes**: Hard vetoes (non-ANZ geography, no broadcast/streaming content, AV/LED hardware vendor) set `lv_anti_icp_flag = true` and force tier D. Gambling operators and >$500M revenue are NOT vetoes. (icp-scoring.md §4–5; CLAUDE.md §10)
- [ ] **REQ-graduated-deductions**: Post-base negative-decay deductions that never disqualify: revenue $500–750M −5, $750M–1B −15, $1B–1.2B −30, $1.2B+ −50; gambling operator −20. None set the anti-ICP flag. (icp-scoring.md §5; CLAUDE.md §10)
- [ ] **REQ-tiering**: Map score + veto rules to A/B/C/D: A ≥ 70 (priority direct), B 40–69 (work if context strong), C 15–39 (nurture via league), D any hard veto (disqualify). SPEC additionally emits Unscored / Needs Review for missing/conflicting inputs. (icp-scoring.md §5; CLAUDE.md §10, §12.7)
- [ ] **REQ-org-type-targeting**: Encode the shift from individual-club targeting to governing-bodies/leagues in the rubric. Best-fit = AU governing-body/league (or content producer) producing live/near-live content at mid-market revenue; individual clubs are anti-ICP as a direct target. (icp-scoring.md §1, §4)

### Enrichment Pipeline (mock)

- [ ] **REQ-enrichment-plan**: Enrich ICP-decisive signals HubSpot does not natively hold, via the provider/research stack. Milestone 1 delivers the pipeline abstraction in mock form: provider waterfall adapters (ZoomInfo/Apollo/Lusha), Claude web-research adapter, Haiku classifier for org-type/content, and a Sonnet validator stub. Live provider wiring is deferred. (icp-scoring.md §6; CLAUDE.md §11, §16)

### HubSpot Property Contract

- [ ] **REQ-hubspot-icp-properties**: Define and exercise the ICP property schema in three roles — inputs (`lv_org_type`, `lv_produces_content`, country, annualrevenue), outputs (`lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`), hygiene (`lv_closed_lost_reason`, `deal_source`) — through the non-clobber merge and dry-run PATCH. Property creation in HubSpot is deferred to the writeback milestone. (icp-scoring.md §5–6; CLAUDE.md §4–8)

### MVP Foundation & Safety

<!-- Derived from CLAUDE.md §11 (Local MVP objectives) and §29 (scope cut): the SPEC-mandated infrastructure the business PRD does not enumerate. -->

- [ ] **MVP-01**: Config-driven scaffolding — `icp_scoring.yaml`, `field_policy.yaml`, `provider_priority.yaml`, `source_registry.yaml`, `escalation_policy.yaml`, pydantic schemas, and test fixtures all exist, load, and validate. (CLAUDE.md §11, §12.1)
- [ ] **MVP-02**: Non-clobber merge engine enforces field-ownership governance (manual_protected / system_owned / fill_blank_only / stale_refreshable / review_required / score_output / veto_output) with promote / stage / reject / needs_review decisions. (CLAUDE.md §9, §17)
- [ ] **MVP-03**: Every enriched field is stamped with source, confidence, evidence URL + summary, verified_at, verified_by_model, and validation_status. (CLAUDE.md §6)
- [ ] **MVP-04**: Dry-run mode prints the exact HubSpot PATCH payload; canonical writes are limited to `lv_icp_*` outputs (firmographics staged only, manual fields never touched); safety-gate env flags change the emitted payload as documented. (CLAUDE.md §11.2, §21, §29)

## v2 Requirements

Deferred to later HubSpot/n8n-dependent milestones. Tracked, not in the Milestone 1 roadmap.

### Enrichment & GTM Motion

- **REQ-finite-list-motion**: Prefer enrich+score of a named best-fit list (~100–150 ANZ orgs; racing core ~25–28) over high-volume prospecting. Requires real CRM + live enrichment. (icp-scoring.md §8)
- **REQ-intent-scoring**: Forward-looking HubSpot-pixel intent scoring (+3 any visit / +7 pricing-product-demo / +5 return within 14d / +10 ≥3 sessions or multi-contact). Not present in the SPEC's `icp_scoring.yaml`; HubSpot-pixel dependent. (icp-scoring.md §5)

### HubSpot Hygiene

- **REQ-closed-lost-capture**: Introduce `lv_closed_lost_reason` picklist and begin capturing loss reasons (0% filled today — the single biggest blocker to evidence-based anti-ICP). HubSpot-property dependent. (icp-scoring.md §4, §6)

### Process Gate

- **REQ-signoff-gate**: Alex sign-off on best-fit (governing-bodies-first) and anti-ICP (clubs-direct / non-AU / no-content) before the JTBD 2 weighted rubric build. Point weights in §5 are illustrative and are themselves the sign-off item. HubSpot Starter → Pro required for production. (icp-scoring.md §9)

## Out of Scope

Explicitly excluded from the current roadmap.

| Feature | Reason |
|---------|--------|
| n8n Cloud workflows (webhook/schedule/subworkflows) | Milestone 1 is local Python only; production orchestration is a later milestone |
| Live provider APIs (real ZoomInfo/Apollo/Lusha) | Mock adapters prove the abstraction first; live wiring is CLAUDE.md Phase 3 |
| HubSpot writeback / property creation / private app | Dry-run PATCH only in Milestone 1; test-record writeback is CLAUDE.md Phase 1 |
| Canonical firmographic promotion | SPEC §29 scope cut — only `lv_icp_*` outputs written canonically in the MVP |
| Contact enrichment/scoring | MVP scope cut — score companies only first (CLAUDE.md §29) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MVP-01 | Phase 1 | Pending |
| REQ-icp-scoring-model | Phase 2 | Pending |
| REQ-anti-icp-vetoes | Phase 2 | Pending |
| REQ-graduated-deductions | Phase 2 | Pending |
| REQ-tiering | Phase 2 | Pending |
| REQ-org-type-targeting | Phase 2 | Pending |
| REQ-enrichment-plan | Phase 3 | Pending |
| REQ-hubspot-icp-properties | Phase 3 | Pending |
| MVP-02 | Phase 3 | Pending |
| MVP-03 | Phase 3 | Pending |
| MVP-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-07*
*Last updated: 2026-07-07 after ingest-driven project initialization*

---

## v3 Requirements (Milestone 3 — Company Enrichment & ICP Research)

**Defined:** 2026-07-20
Source: `docs/WEB-RESEARCH-SPEC.md` (30 numbered requirements, cited by ID in the test suites).
These REQ-IDs group that spec into phase-mappable units; the spec IDs are the testable contract.

### Company Enrichment

- [x] **REQ-company-branch**: Companies enrich via a sibling n8n branch off the same trigger — NOT nested under contacts. The ICP fields are per-domain and expensive; nesting re-pays for every contact at the same company. Read-only, no write nodes. (Phase 11)
- [x] **REQ-company-merge**: Company non-clobber merge with a `domain` hard guard and an evidence-URL gate that runs before the ownership-class branches, so an unevidenced ICP claim cannot promote. (Phase 11)
- [x] **REQ-provider-contracts**: Every provider contract confirmed against the live API before wiring, with units verified. ZoomInfo GTM `revenue` is THOUSANDS; treating it as dollars banded every company 1000x low and inverted the ICP signal. (Phase 11)
- [x] **REQ-conflict-withhold**: Cross-provider disagreement on entity-specific signals (size) withholds promotion and routes to review rather than silently selecting one candidate. This is also the franchise/subsidiary detector — no hierarchy modelling required. (Phase 11)

### Taxonomy & Extensibility

- [ ] **REQ-taxonomy-single-source**: `config/taxonomy.yaml` is the only hand-edited vocabulary for `lv_org_type` and `lv_content_type`. Scoring config, field policy, n8n node literals, research prompt and normalizers all derive from it. Adding a value is a one-file edit; drift is a test failure, not a silent 0-score. (Spec TX-1…TX-9; Phase 12)
- [ ] **REQ-enum-normalization**: Normalizers never emit an off-vocabulary value. `lv_org_type` is free text in HubSpot, so there is no CRM-level guard — the normalizer is the only barrier. Python and JS agree on every shared case. (Spec NM-1…NM-6; Phase 12)

### Research & Judgement

- [ ] **REQ-web-retrieval**: `lv_produces_content` and `lv_org_type` resolve from citable first-party sources via native web search, within existing cost kill-switches. Measured: providers resolve org_type for 3/5 accounts and produces_content for 0/5. (Spec RT-1…RT-5; Phase 13)
- [ ] **REQ-evidence-by-field**: Research output carries per-field evidence URLs — the shape the merge gate already requires. A flat URL array does not satisfy it. (Spec OC-1; Phase 13)
- [ ] **REQ-tristate-content**: `lv_produces_content` honors true/false/null as distinct. `false` fires a hard veto; thin or absent evidence MUST yield `null`. A failed search is not evidence of absence, and thin-web-presence ANZ clubs are the ICP core. (Spec TS-1…TS-5; Phase 13)
- [ ] **REQ-evidence-before-judgement**: Judgement never runs without retrieval. Size conflicts never trigger a model call alone — revenue band drives only graduated deductions, never a veto. (Spec RO-1, RO-2, JG-1…JG-3; Phase 14)

### Scoring Ownership

- [ ] **REQ-inputs-only-writeback**: The pipeline writes ICP **inputs** and their source metadata, never the derived outputs. `lv_icp_fit_score`, `lv_icp_tier`, `lv_anti_icp_flag`, `lv_anti_icp_reason` and `lv_recommended_motion` are computed in HubSpot. `src/icp_scoring.py` still computes score/tier internally for routing and audit, but its results do not reach a PATCH. Supersedes CLAUDE.md §29. (Phase 15)

### CRM Migration

- [ ] **REQ-property-migration**: Missing metadata properties created via a dry-run-by-default sync emitting an undo manifest. Two known irreversible mutations require explicit sign-off and are NOT bundled: `lv_org_type` text→enumeration, and `lv_icp_fit_score` calculated→writable (destroys its formula). (Spec RT-5; Phase 15)

### v3 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-company-branch | Phase 11 | Complete |
| REQ-company-merge | Phase 11 | Complete |
| REQ-provider-contracts | Phase 11 | Complete |
| REQ-conflict-withhold | Phase 11 | Complete |
| REQ-taxonomy-single-source | Phase 12 | Pending |
| REQ-enum-normalization | Phase 12 | Pending |
| REQ-web-retrieval | Phase 13 | Pending |
| REQ-evidence-by-field | Phase 13 | Pending |
| REQ-tristate-content | Phase 13 | Pending |
| REQ-evidence-before-judgement | Phase 14 | Pending |
| REQ-inputs-only-writeback | Phase 15 | Pending |
| REQ-property-migration | Phase 15 | Pending |

**Coverage:** v3 requirements: 12 total — mapped to phases: 12 — unmapped: 0 ✓

**Deferred beyond Milestone 3:** authoring the HubSpot-side calculation for score/tier/veto/motion (downstream; the rubric must be re-expressed in HubSpot calculation syntax against the `lv_*` inputs).

---
*v3 requirements defined: 2026-07-20*
