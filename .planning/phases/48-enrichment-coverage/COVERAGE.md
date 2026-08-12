# API Coverage — Phase 48 (Enrichment Coverage)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

No external API integration: Phase 48 consumes four already-integrated, already-sealed
surfaces (HubSpot CRM v3 via `src/hubspot_client.py`, the Anthropic Messages API via
`src/web_research.py`, the n8n Cloud D-18 webhook via
`scripts/remediate_veto_companies.py::post_webhook_event`, and the Lusha balance read via
`scripts/check_provider_credits.py`) and adds no new capability against any of them — the
phase's own code is a data-mapping pass, a cost gate, and one n8n control-flow node.

**Detector result at plan time (2026-08-12):** `{"detected": false, "signals": []}` over the
ROADMAP Phase 48 section. The PLAN bodies name webhooks and endpoints because they *call*
existing seams, which may re-fire the detector at seal time; this declaration is the honest
answer in that case.

**Deliberate non-integration, recorded so it is a decision and not a hole:**

| surface | decision | reason |
|---|---|---|
| Provider waterfall (ZoomInfo / Apollo / Lusha enrichment endpoints) | OPT-OUT | D-01 — providers do not return `lv_org_type` at all; calling them would spend credits for firmographics this phase does not need |
| HubSpot property-options PATCH (`scripts/sync_hubspot_properties.py`) | OPT-OUT | D-02 — `venue` deferred; no record in this population maps to it, and an enum-option PATCH is portal schema work needing its own arming |
| Anthropic billing / credit-balance endpoint | OPT-OUT | 48-RESEARCH.md Open Question 2 — no such check exists in this repo and COVER-01/02 do not mention Anthropic billing; handled as a manual operator pre-check before the one paid call |
