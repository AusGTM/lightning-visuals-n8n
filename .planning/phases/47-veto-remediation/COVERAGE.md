# Phase 47 — API Coverage Matrix

The API-coverage detector fires on this phase from a weak signal — a mention of "HubSpot API
constraints" in a canonical-references list. This phase *consumes* surfaces that earlier phases
already integrated (HubSpot CRM v3, the n8n enrichment webhook, the Anthropic web-research
adapter) rather than integrating a new one. This matrix is therefore deliberately scoped to
exactly the surfaces this phase's own code touches — a capability list keyed to
`scripts/remediate_veto_companies.py`, `scripts/check_schema_drift.py`,
`operator-claude-plugin/scripts/enrichment.py`, `operator-claude-plugin/scripts/n8n_arming.py`
and `src/web_research.py` — not a re-enumeration of the full HubSpot or n8n API surface. Every
capability below carries a decision; INTEGRATE is the default, and every OPT-OUT names its
one-line reason.

| capability | decision | reason |
|------------|----------|--------|
| HubSpot CRM v3 single-record read (`get_record`, `src/hubspot_client.py`) | INTEGRATE | Already wrapped; used to fetch each pinned record's current state before and during the run. |
| HubSpot CRM v3 batch update (`batch_update_companies`, `src/hubspot_client.py`) | INTEGRATE | The input/metadata/component write path — the mechanism the armed window actually writes through. |
| HubSpot CRM v3 object search (`search_records`, `src/hubspot_client.py`) | INTEGRATE | Used by the before/after report (`scripts/veto_remediation_report.py`, Plan 03). |
| HubSpot CRM v3 properties listing (`check_schema_drift._get_live_properties`) | INTEGRATE | The Plan 03 pre-arm existence check confirming every property this phase writes actually exists live before any PATCH is attempted. |
| HubSpot CRM v3 property creation | OPT-OUT | Standing v0.9 no-new-properties constraint. |
| HubSpot Automation v4 flows | OPT-OUT | The derived chain (calculated property → WF1 → n8n) is read-only to this phase; WF1 and the calculated property are consumed as-is, never edited or redeployed. |
| HubSpot webhook subscription management | OPT-OUT | D-18 chose a direct webhook POST precisely to avoid depending on a portal subscription this repo has never confirmed live (research Assumption A1 — CLAUDE.md §20.2 lists only `lv_enrichment_requested` as subscribed). |
| n8n enrichment webhook POST (`webhook/hubspot/enrichment/event`, `operator-claude-plugin/scripts/enrichment.py`) | INTEGRATE | The D-18 trigger mechanism that fires the `Decide Company Action` node so the veto fields actually clear. |
| n8n workflow arm/disarm config API (`n8n_arming.arm_for_dispatch` / `disarm`) | INTEGRATE | The second VETO-02 write surface per D-19 — `ALLOW_HUBSPOT_RECORD_WRITES` plus the `TEST_RECORD_IDS` allowlist gate the n8n side of the armed window. |
| n8n workflow deploy (`scripts/deploy_n8n_workflows.py`) | OPT-OUT | D-20 accepts the redundant second-pass research call rather than editing and redeploying the workflow to suppress it. |
| n8n executions/usage API | OPT-OUT | No usage endpoint exists on this plan (project memory `n8n-execution-budget.md`); month-to-date budget headroom is an operator confirmation at the arming checkpoint, not an API read. |
| Anthropic Messages API with the native `web_search` server tool (`src/web_research.py`) | INTEGRATE | D-08's chosen enrichment source for `lv_org_type` / `lv_produces_content` / region on all 17 records. |
| Provider APIs (ZoomInfo, Apollo, Lusha) | OPT-OUT | D-08 routes all enrichment through Claude web research; zero provider credits are drawn, so no provider integration is exercised by this phase. |
