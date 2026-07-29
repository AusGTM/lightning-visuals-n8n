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

## v4 Requirements (Milestone v0.4 — Reachability & Verification Debt)

**Defined:** 2026-07-29
Source: `.planning/debug/bug-23-enrichment-contact-nomatch-chain-stop.md` (fix plan §"What the
fix's plan must include") + v0.3 deferred items (STATE.md Deferred Items, v0.3-ROADMAP.md
"Issues deferred" / "Technical debt incurred").
The v3 section formerly here is archived verbatim in `.planning/milestones/v0.3-REQUIREMENTS.md`.

### Reachability (BUG 23)

- [x] **REACH-01**: The enrichment lane's `HubSpot Search` and `HubSpot Fetch By Id` run on the credential-bound httpRequest envelope transport (mirroring BUG 22's change, including the `lookup_failed` item-error mapping), so a no-match search emits exactly one classifiable item instead of stopping the chain — `adaptFetchById`'s 0-result handling stops being dead code and `contact:create` becomes reachable.
- [x] **REACH-02**: Both nodes are dropped from the byte-identical pin in `tests/test_bug10_company_search_transport.py` with the same documented rationale as the prior two removals — the guard was pinning a node broken for half its input space.
- [x] **REACH-03**: Live canary of BOTH cases — contact 201 still matches and enriches (regression check on the single most live-proven path in the system), and a nonexistent email reaches `Decide Action` as `create`, write-gated.
- [x] **REACH-04**: The harness gap is closed — `bareEventChainFlow`'s http mocks model the native node's 0-item behavior, or (better) the lane asserts no native search nodes remain.

### Normalization

- [ ] **NORM-01**: A numeric provider industry code (ZoomInfo's `"71"`) never survives normalization unchanged and never wins the waterfall over provider text (Apollo's `"media production"` lost to `"71"` in execution 19).

### Copy-loops

- [ ] **COPY-01**: `lv_sponsorship_reliant` is copied from its candidate source (`build_cloud_workflows.py` ENRICH_MERGE_CO researchData loop) into the companies merge call — the property stops being permanently empty.
- [ ] **COPY-02**: `persona_group`/`lv_persona_group` is copied from its candidate source (ENRICH_MERGE winners loop) into the contacts merge call — the property stops being permanently empty.

### Verification debt

- [ ] **VERIFY-01**: The six `/gsd-verify-work` re-runs carried from the v0.3 goal ledger are executed and their outcomes recorded.

### v4 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REACH-01 | Phase 17 | Complete |
| REACH-02 | Phase 17 | Complete |
| REACH-03 | Phase 17 | Complete |
| REACH-04 | Phase 17 | Complete |
| NORM-01 | Phase 18 | Pending |
| COPY-01 | Phase 18 | Pending |
| COPY-02 | Phase 18 | Pending |
| VERIFY-01 | Phase 19 | Pending |

**Coverage:**

- v4 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0 ✓

### Out of Scope (v0.4)

- **HubSpot-side score/tier calculation** — still the `1 + 1` placeholder; authoring it remains downstream work (Approach C scope fence).
- **`lv_org_type` text→enumeration** — one-way door, deliberately not performed.
- **`lv_country_region_normalized` field-policy entry** — flagged, decision not forced this milestone.
- **`src/merge_policy.py:279-287` unconditional cache-write** — Python-harness lane only; needs its own decision before any stale-refresh reliance.

---
*v4 requirements defined: 2026-07-29*
