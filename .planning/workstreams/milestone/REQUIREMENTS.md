# Requirements: lv-n8n-poc — Milestone v0.5 Lusha v3 & Armed Enrichment

**Defined:** 2026-07-30
**Core Value:** The ICP scoring engine turns firmographic + enrichment signals into trustworthy, auditable A/B/C/D prioritization (with hard vetoes) and never clobbers HubSpot data — now proven live, not just in dry-run.

Sources: Lusha v3 migration guide + OpenAPI docs (reviewed 2026-07-30, memory `lusha-v3-migration-deadline`), measured provider economics (memory `measured-provider-match-rates`), Haiku/Sonnet A/B eval (2026-07-30), PROJECT.md deferred-scope ledger.

## v0.5 Requirements

Each maps to exactly one roadmap phase.

### Lusha v3 Migration (deadline: v2 dies 2026-11-18)

- [x] **REQ-lusha-v3-contract-probe**: Live-probe `POST /v3/contacts/search-and-enrich` and `POST /v3/companies/search-and-enrich` (and the two-step `search` → `enrich` pair) with minimal credit spend; document the confirmed request/response contract (envelope, `has`/`canReveal`/`billing` fields, error shapes) the way the ZoomInfo GTM contract was captured. Verify `check_provider_credits.py`'s usage endpoint against `GET /v3/account/usage`.
- [x] **REQ-lusha-v3-request-builders**: Both lanes (contacts + companies) swap `GET /v2/*` → `POST /v3/*/search-and-enrich`: params move to body, identity keys map unchanged (email | name+company/domain | domain), `api_key` header auth retained. Builder + local-live variants + `scripts/dryrun_batch.mjs`.
- [x] **REQ-lusha-selective-reveal** *(re-scoped 2026-07-30 after live probe — A3 REFUTED, see docs/LUSHA-V3-CONTRACT.md §6)*: Contacts requests still derive `reveal[]` from the enrichment gate's `missingFields`, but as **PII-minimization hygiene**, not a cost lever — live A/B showed reveal-1-field vs reveal-2-fields bills identically, and v3 first-time enrich is a flat 1 credit regardless of fields (the v2 ~4.65-credits/reveal phone bundling does not exist in v3). Empty `reveal:[]` is invalid (400) — a minimal non-empty set is always sent. Companies lane has NO reveal mechanism (flat 2 credits/match) — no reveal-derivation code written for it. Cost target already met by flat v3 pricing + id reuse (REQ-lusha-id-staging): full sweep projects ~1 cr/contact + 2 cr/company, well inside the ~3.9k balance.
- [x] **REQ-lusha-id-staging**: New staging properties `lusha_contact_id` / `lusha_company_id` persisted on match; re-enrichment paths pass stored IDs so already-revealed data re-enriches free (`canReveal.credits: 0`).
- [x] **REQ-lusha-v3-normalize**: `lushaCandidates` in `normalizeProviders.js` parses the v3 envelope and emits candidates field-identical to v2 output downstream (merge/score/staging unchanged; HubSpot schema untouched beyond the two ID properties).
- [x] **REQ-lusha-v3-verification**: v2-pinned tests migrated, frozen fixture re-baselined, both suites green, disarmed redeploy with read-back showing v3 URLs live and zero v2 URLs remaining.

### Armed Enrichment Canary

- [x] **REQ-armed-e2e-canary**: One armed end-to-end enrichment on allowlisted record(s): provider waterfall + Haiku web research + Sonnet judge → staged fields, source metadata, and promoted canonical writes land in HubSpot; neighbor records byte-untouched; disarm + read-back (`"false"`×N, allowlist cleared) closes the run.
- [x] **REQ-canary-cost-ledger**: The canary records actual spend — provider credits (before/after balances) and Anthropic tokens per call — against the 2026-07-30 estimates, producing a calibrated per-record cost figure for full-sweep planning.

### Transport Hygiene

- [x] **REQ-dedupe-transport-swap**: `Dedupe Search (candidate contacts)` swaps from the native HubSpot node to the credential-bound httpRequest envelope (BUG-10/22/23 mechanism); weekly sweep remains classify-only (writes only the needs-review flag through the existing gated PATCH).

### Schema Hygiene

- [x] **REQ-orgtype-enumeration**: `lv_org_type` converts text → HubSpot enumeration (the one-way door): property migrated with existing values preserved, pipeline writes validated against the enum options, rollback path documented before flipping.
- [x] **REQ-country-region-policy**: `lv_country_region_normalized` gains a `config/field_policy.yaml` entry so the already-produced research value can promote under policy instead of staging-only by default.

## Future Requirements (deferred to v0.7)

v0.6 is the operator client milestone (front door + control plane) and scopes none of these.
They are backend and business-owner items, carried to v0.7.

- HubSpot-side ICP formula — replace the `1 + 1` calculated-property placeholder (downstream-owner decision).
- JTBD 2 weighted-rubric sign-off (REQ-signoff-gate) — rubric weights need business owner.
- Lusha v3 signals/webhooks (job-change, headcount) as HubSpot staleness triggers.
- Lusha `waterfallReveal` beta (third-party fall-through) — needs support-enabled account access.

## Out of Scope

- Lusha Prospecting / Lookalikes / Tables / Decision Makers APIs — net-new acquisition surfaces, not enrichment of existing CRM records.
- org_type evidence-gate in `computeEscalation` — explicitly rejected 2026-07-30 (plausible-not-observed; YAGNI).
- Scheduled full-portal sweep arming — canary proves the path; fleet-wide arming is an operator decision after the cost ledger lands.

## Traceability

11/11 v0.5 requirements mapped — no orphans, no duplicates.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-lusha-v3-contract-probe | Phase 20 | Complete |
| REQ-lusha-v3-request-builders | Phase 20 | Complete |
| REQ-lusha-selective-reveal | Phase 20 | Complete |
| REQ-lusha-id-staging | Phase 20 | Complete |
| REQ-lusha-v3-normalize | Phase 20 | Complete |
| REQ-lusha-v3-verification | Phase 20 | Complete |
| REQ-dedupe-transport-swap | Phase 21 | Complete |
| REQ-orgtype-enumeration | Phase 21 | Complete |
| REQ-country-region-policy | Phase 21 | Complete |
| REQ-armed-e2e-canary | Phase 22 | Complete |
| REQ-canary-cost-ledger | Phase 22 | Complete |
