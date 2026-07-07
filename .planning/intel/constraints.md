# Constraints (SPEC intel)

Source SPEC: `/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/CLAUDE.md`
Title: HubSpot Sales Hub Pro → n8n Cloud Waterfall Enrichment + ICP Scoring System

---

## CON-platform-sales-hub-pro
Source: CLAUDE.md §1.1, §1.2
Type: protocol
Content: System must be Sales Hub Professional-compatible. Do NOT rely on: HubSpot workflow "Send webhook" action, workflow custom-code actions, Data Hub data-formatting, programmable automation, or HubSpot-native waterfall enrichment. All orchestration/classification/enrichment/scoring lives outside HubSpot (n8n or a small decision service).

## CON-orchestration-n8n-cloud
Source: CLAUDE.md §1.3, §13
Type: protocol
Content: n8n Cloud (paid, hosted — not self-hosted) is the orchestration layer: webhook receiver, schedules, provider waterfall, retry, routing, writeback. HubSpot is CRM + control plane via custom properties + event source via private-app webhooks + destination + audit surface.

## CON-provider-adapter-contract
Source: CLAUDE.md §16
Type: api-contract
Content: Every provider/research adapter emits a normalized schema: {provider, object_type, matched, confidence, data{}, evidence{last_seen, match_basis, evidence_urls, evidence_summary}, cost{credits_used, billable}, model_trace}. Required behavior: timeout every request; retry only safe transient failures; never retry 400/401/403 without intervention; record credits/match-basis/source/confidence/evidence.

## CON-llm-cascade
Source: CLAUDE.md §15
Type: protocol
Content: Deterministic rules → Haiku (cheap classification, structured extraction, first-pass scoring) → Sonnet 5 (conflict validation, anti-ICP/hard-veto arbitration, high-risk reasoning) → human review. Sonnet triggers only on conflict / hard-veto-possible / anti-ICP-flip / canonical-overwrite / low-confidence. Human review when Sonnet confidence <80, missing evidence URL for required field, or provider vs web-research material conflict.

## CON-non-clobber-merge
Source: CLAUDE.md §9, §17
Type: protocol
Content: Field governance by ownership class: manual_protected (never auto-overwrite), system_owned (overwrite if confidence passes), fill_blank_only, stale_refreshable (refresh after TTL + higher confidence), review_required (stage only), append_only, score_output/veto_output (recompute). Promote/stage/reject/needs_review decision rules per §17.2. Manual values are authoritative unless blank/stale/system-owned/low-confidence.

## CON-source-attribution
Source: CLAUDE.md §6
Type: schema
Content: Every enriched field carries metadata: <field>_source, _source_detail, _confidence, _evidence_url, _evidence_summary, _verified_at, _verified_by_model, _validation_status. Validation statuses: provider_only, web_researched, llm_classified, sonnet_validated, human_review_required, human_approved, conflicting, rejected, stale. Global: enrichment_source_summary/count/primary_source, enrichment_evidence_urls, enrichment_model_trace, enrichment_validation_path.

## CON-hubspot-data-model
Source: CLAUDE.md §4, §5, §7, §8
Type: schema
Content: Control properties (enrichment_requested/mode/status/priority/lock_until, last_enrichment_run_id, last_enriched_at, confidence, needs_review, error, last_sources, last_decision, review_reason) on both companies and contacts. Company ICP inputs (lv_org_type, lv_produces_content, lv_content_type, lv_country_region_normalized, lv_revenue_band, lv_employee_band, etc.) and outputs (lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag, lv_anti_icp_reason, lv_icp_score_breakdown, lv_recommended_motion, ...). Per-provider staging fields (<provider>_<field>).

## CON-icp-scoring-config
Source: CLAUDE.md §10 (config/icp_scoring.yaml, version lv-icp-v0.1)
Type: schema
Content: Operationalized scoring rubric. base_score org_type {governing_body_league:40, content_producer:20, broadcaster:20, individual_club_team:5, regulator:5, gambling_operator:0, hardware_vendor:0, other:0, unknown:0}; produces_content {true:20}; geography {ANZ/AU/NZ:10}; revenue_band {5-50M:10, 50-500M:10, 500-750M:-5, 750M-1B:-15, 1B-1.2B:-30, 1.2B+:-50}. graduated_deductions {gambling_operator:-20}. hard_vetoes {non_anz, no_content, hardware_vendor}. tier_rules {A≥70, B 40-69, C 15-39, D=veto, Unscored=missing inputs}. This is the machine-readable counterpart of PRD REQ-icp-scoring-model and matches it numerically (see INGEST-CONFLICTS.md INFO for the two divergences).

## CON-safety-gates
Source: CLAUDE.md §11.2, §21, §29
Type: protocol
Content: Kill switches: ENRICHMENT_ENABLED, ALLOW_PROVIDER_CALLS, ALLOW_WEB_RESEARCH, ALLOW_SONNET_ESCALATION, ALLOW_CANONICAL_WRITES, ALLOW_ICP_SCORE_WRITES, ALLOW_STAGING_WRITES; per-run caps (credits, web-research, Sonnet, records). Dry-run prints exact PATCH payloads. High-risk writes (anti_icp_flag false→true, tier A/B→D, produces_content true→false, org_type→hardware/gambling, manual overwrite) require Sonnet or human review. MVP: canonical writes limited to ICP score/tier outputs only; firmographic canonical fields staged not written.

## CON-locking-idempotency
Source: CLAUDE.md §13.1, §13.4, §19.3
Type: protocol
Content: Enrichment lock via enrichment_lock_until (TTL, default 15 min) + last_enrichment_run_id for idempotency. Webhook and scheduled poller both acquire/check/release lock. Stuck-lock cleanup job sets status=failed and clears lock when lock expired while status=running.

## CON-rollout-phasing
Source: CLAUDE.md §3, §25, §28
Type: protocol
Content: Phased rollout: Phase 0 local-first MVP (mock providers/research, dry-run PATCH) → Phase 1 HubSpot test writeback (staging + score outputs only) → Phase 2 n8n Cloud dry-run → Phase 3 provider + web-research integration → Phase 4 controlled pilot with promotion ramp. Score companies first (MVP scope cut, §29).
