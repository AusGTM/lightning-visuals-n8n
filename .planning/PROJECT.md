# lv-n8n-poc

## What This Is

A local-first Python MVP that proves Lightning Visuals' HubSpot → n8n waterfall
enrichment + ICP scoring system before any production wiring. It scores companies
against a governing-body-first ICP rubric using mock ZoomInfo/Apollo/Lusha adapters,
mock Claude web research, a Haiku→Sonnet LLM cascade, and a non-clobber merge policy —
emitting dry-run HubSpot PATCH payloads. It is internal RevOps tooling for LV's sales
team, not a customer-facing product.

## Core Value

The ICP scoring engine turns firmographic + enrichment signals into trustworthy,
auditable A/B/C/D prioritization (with hard vetoes) and never clobbers HubSpot data —
proven entirely in dry-run locally, before touching a single production record.

## Business Context

- **Customer**: Lightning Visuals RevOps / sales team (sports-media / broadcast graphics vendor).
- **Revenue model**: Internal GTM tooling — prioritizes a finite best-fit TAM (~100–150 ANZ orgs) rather than high-volume prospecting.
- **Success metric**: Plausible tier distribution, zero false clobbering, and a config-driven rubric ready for JTBD 2 sign-off.
- **Strategy notes**: Governing-body-first targeting derived from 92 closed HubSpot deals (see icp-scoring.md); primary competitor LIGR.live already runs the "buy-once-deploy-league-wide" play.

## Requirements

Full detail and traceability live in `.planning/REQUIREMENTS.md`.

### Validated

(None yet — ship Milestone 1 to validate.)

### Active (Milestone 1 — Local-First MVP)

- [ ] Config-driven ICP scoring: score, tier (A/B/C/D), anti-ICP vetoes, graduated deductions (REQ-icp-scoring-model, REQ-anti-icp-vetoes, REQ-graduated-deductions, REQ-tiering)
- [ ] Governing-body-first targeting encoded in the rubric and demonstrated by tests (REQ-org-type-targeting)
- [ ] Mock enrichment pipeline: provider waterfall + Claude research + Haiku classifier + Sonnet stub (REQ-enrichment-plan)
- [ ] HubSpot ICP property contract exercised through non-clobber merge (REQ-hubspot-icp-properties)
- [ ] MVP foundation, non-clobber merge, source attribution, and dry-run PATCH output (MVP-01…MVP-04)

### Out of Scope (deferred to future milestones)

- **n8n Cloud workflows** (webhook receiver, schedules, subworkflows) — Milestone 1 is local Python only; production orchestration is a later milestone.
- **Live provider APIs** (real ZoomInfo/Apollo/Lusha) — mock adapters only in Milestone 1; live integration is CLAUDE.md Phase 3.
- **HubSpot writeback / property creation / private app** — dry-run PATCH only; test-record writeback is CLAUDE.md Phase 1 (next milestone).
- **Canonical firmographic promotion** — MVP stages firmographics; only `lv_icp_*` outputs are written canonically (SPEC §29 scope cut).
- **Pixel intent scoring** (REQ-intent-scoring) — defined in the PRD but absent from the SPEC's `icp_scoring.yaml`; HubSpot-pixel dependent, deferred.
- **Closed-lost capture** (REQ-closed-lost-capture) — HubSpot-property dependent, deferred to a writeback milestone.
- **Finite-list named-account motion** (REQ-finite-list-motion) — requires real CRM + live enrichment, deferred.

## Context

- **Two source docs, complementary not competing.** `CLAUDE.md` (SPEC) is the authoritative implementation contract; `icp-scoring.md` (PRD) is the validated business rationale. Scoring numbers agree field-by-field across both (INGEST-CONFLICTS.md, 0 blockers / 0 warnings / 3 INFO).
- **Finite best-fit TAM** (~100–150 ANZ orgs; racing core ~25–28) motivates enrich-and-score over programmatic prospecting.
- **Data-quality caveats:** findings measure engaged-deal conversion, not the whole market; small cells (n ≥ 3) are hypotheses, not certainties; pre-HubSpot wins are undercounted; HubSpot native industry tags are unreliable (e.g. Australian Turf Club tagged "Gambling/Casinos") — lead with enriched signals.
- **Competition:** LIGR.live (AU cloud pay-per-use, holds Football Australia gatekeeper deal) is the #1 threat; LV sits between Vizrt (premium) and LIGR (budget). Differentiate on automation/data/price/outbound, not "cloud."

## Constraints

- **Tech stack (Milestone 1)**: Python 3, local-only. anthropic, requests, pydantic, PyYAML, phonenumbers, email-validator, pytest.
- **Platform**: Sales Hub Professional-compatible — no HubSpot workflow "Send webhook", custom-code actions, Data Hub formatting, or native waterfall enrichment. All orchestration lives outside HubSpot.
- **Orchestration (production)**: n8n Cloud (paid, hosted — not self-hosted). Out of scope for Milestone 1.
- **LLM cascade**: deterministic rules → Haiku → Sonnet 5 → human review. Sonnet only on conflict / hard-veto-possible / anti-ICP-flip / canonical-overwrite / low-confidence.
- **Non-clobber merge**: field-ownership governance (manual_protected, system_owned, fill_blank_only, stale_refreshable, review_required, append_only, score_output, veto_output). Manual values authoritative unless blank/stale/system-owned/low-confidence.
- **Source attribution**: every enriched field carries source / confidence / evidence URL+summary / verified_at / verified_by_model / validation_status.
- **Safety**: kill-switch env flags + per-run caps; dry-run prints exact PATCH; MVP canonical writes limited to `lv_icp_*` outputs.
- **Provider adapter contract**: every adapter emits the normalized `{provider, object_type, matched, confidence, data, evidence, cost, model_trace}` schema.

## Key Decisions

<!-- SPEC-level architectural commitments recorded as project decisions (no ADRs in ingest set). -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| HubSpot Sales Hub Pro as CRM + control plane (custom properties, not native automation) | Avoid Data Hub / programmable-automation dependency; keep logic portable | — Pending |
| n8n Cloud as production orchestration layer | Hosted, avoids self-hosting ops; owns webhook/schedule/waterfall/retry | — Pending |
| LLM cascade Haiku → Sonnet 5 → human | Cheap classification by default; escalate only high-risk/conflict decisions to control cost | — Pending |
| Non-clobber merge with field-ownership classes | Protect manually-maintained CRM data; stage before promoting | — Pending |
| Per-field source/evidence attribution | Auditable enrichment; supports human review and rollback | — Pending |
| Safety gates + MVP canonical writes limited to `lv_icp_*` | Prove scoring with zero clobbering risk before enabling firmographic promotion | — Pending |
| Config-driven rubric with illustrative weights (`icp_scoring.yaml` v lv-icp-v0.1) | Weights change after JTBD 2 sign-off without code changes | ⚠️ Revisit (pending sign-off) |
| **(M2)** File upload is a merge *source*, not a new engine — reuse Milestone 1 non-clobber merge | The field-level "don't clobber" is already solved; a CSV row is just another candidate source | — Pending |
| **(M2)** Identity match: auto only on email/LinkedIn; no-email never auto-creates; ambiguous → review | Matching is the real risk; conservative default prevents duplicate-contact explosion in HubSpot | — Pending |
| **(M2)** Net-new + valid email → auto-create, gated (`ALLOW_CONTACT_CREATE`, dry-run first, re-check-by-email guard) | User-chosen; safe because create is flag-gated, dry-run-default, and dedupe-guarded | — Pending |
| **(M2)** Weekly n8n scheduler sweep flags duplicate/mangled contacts as needs_review | Catches dupes and bad data that slipped past ingestion; matches CLAUDE.md §13.4 Workflow D | — Pending |

## Risks & Open Items

- **Point weights are illustrative pending JTBD 2 sign-off** (REQ-signoff-gate). Alex must approve best-fit (governing-bodies-first) and anti-ICP (clubs-direct / non-AU / no-content) before the weighted production rubric is built. The MVP is deliberately config-driven so this can happen without code changes.
- **Pixel intent scoring** (REQ-intent-scoring) is in the PRD but not in the SPEC's `icp_scoring.yaml` — carry as an open item for the JTBD 2 rubric build, not a Milestone-1 deliverable.
- **HubSpot is on Starter ($35) today; Pro tier is required** for production scoring/workflows. Blocks the writeback and n8n milestones, not Milestone 1.
- **Enrich-first reality**: org type verified for only 66 of 712 CRM companies; `closed_lost_reason` is 0% filled. Anti-ICP is currently inferred from firmographics; discovery calls now supply real reasons (price #1, cloud-fear #2).

---
*Last updated: 2026-07-07 after ingest-driven project initialization*
