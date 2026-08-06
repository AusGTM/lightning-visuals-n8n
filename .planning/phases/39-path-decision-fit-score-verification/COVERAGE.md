# Phase 39 API Coverage Matrix

This is a read-mostly probe phase (D-01/D-02: verify company fit-score availability and, if available,
recalc latency, on a disposable-record basis only). Most HubSpot CRM write surface is honestly opted
out. `Decision` is `INTEGRATE` (this phase calls it, in dry-run-gated or disposable-record form) or
`OPT-OUT` (deliberately not called, with a reason).

| Capability | Endpoint | Decision | Reason |
|---|---|---|---|
| Account info read | `GET /account-info/v3/details` | INTEGRATE | Portal identity/locale probe — establishes portal 22617666, `app-ap1.hubspot.com`, ap1 host for the evidence record (39-01/39-02). |
| Company property list read | `GET /crm/v3/properties/companies` | INTEGRATE | Negative/supporting evidence for the availability verdict — surfaces any `calculation_score`-typed property that may already exist (39-01/39-02). |
| Single property read | `GET /crm/v3/properties/companies/{name}` | INTEGRATE | `find_score_property_name` helper (39-03) reads individual property definitions to locate the score property once the operator builds a scoring model in-portal. |
| Company create | `POST /crm/v3/objects/companies` | INTEGRATE | Disposable `ZZ-SCORING-TEST-DELETE-ME-*` record only, two-key-gated (`DRY_RUN=false` + `ALLOW_HUBSPOT_SCORING_PROBE=true`) — never a real record (39-03). |
| Company read | `GET /crm/v3/objects/companies/{id}` | INTEGRATE | Polls the disposable company's score property during the recalc-latency measurement loop (39-03). |
| Company patch | `PATCH /crm/v3/objects/companies/{id}` | INTEGRATE | Flips the disposable company's criterion property three times to time recalculation (39-03); disposable record only. |
| Company delete | `DELETE /crm/v3/objects/companies/{id}` | INTEGRATE | Teardown of the disposable probe company after the latency measurement, new `delete_record()` primitive added this phase (39-03). |
| Property create | `POST /crm/v3/properties/companies` | OPT-OUT | The `calculation_score` field type the lead-scoring tool creates is `hubspotDefined: true` and read-only for both value and definition on every tier — a `POST` attempt would fail portal-tier-agnostically, carrying no availability signal either way (RESEARCH.md Pitfall 1). |
| Property update / archive | `PATCH`/`DELETE /crm/v3/properties/companies/{name}` | OPT-OUT | No schema mutation is in scope for a probe phase — nothing this phase creates needs updating or archiving beyond the disposable-company lifecycle already covered above. |
| Company search | `POST /crm/v3/objects/companies/search` | OPT-OUT | Single-record probe — the probe targets one known disposable-company id per run; no population query needed. |
| Batch company endpoints | `POST /crm/v3/objects/companies/batch/*` | OPT-OUT | Single-record probe by design (one disposable company per D-03 run) — batching adds no signal and multiplies teardown risk. |
| Flows read | `GET /automation/v4/flows/{id}` | OPT-OUT | Out of phase boundary — the four-workflow chain (fix-in-place path, if chosen) is Phase 40/42 scope, and its workflow definitions are already archived from prior sessions. |
| Contacts object | `GET/POST/PATCH /crm/v3/objects/contacts` | OPT-OUT | Out of phase scope — company fit score only (DECIDE-01), and contact-based scoring is Marketing-Hub-gated per HANDOVER §8, confirmed locked in the portal walkthrough. |
| Deals object | `GET/POST/PATCH /crm/v3/objects/deals` | OPT-OUT | Out of phase scope — company fit score only; deal scoring was not offered as a relevant object for this decision. |
| Lists | `GET/POST /crm/v3/lists/*` | OPT-OUT | No population work — a single-disposable-record probe phase has no list membership to manage. |
| Notes and associations | `POST /crm/v3/objects/notes`, `/crm/v4/associations/*` | OPT-OUT | No audit-note writing — establishing an availability/latency verdict needs no note or cross-object link. |
| Owners and pipelines | `GET /crm/v3/owners`, `/crm/v3/pipelines/*` | OPT-OUT | Unrelated dimension — no owner or pipeline concept enters the D-01/D-03 evidence. |
| Webhooks and subscriptions | `GET/POST /webhooks/v3/*` | OPT-OUT | No event-subscription change — this phase reads and times existing behavior, it does not wire new triggers. |
| Dedicated lead-scoring API | (none published) | OPT-OUT | HubSpot's own "APIs by tier" reference table contains zero entries for scoring — no dedicated endpoint exists to integrate against. That absence is itself recorded evidence for this phase's central finding: the API can only supply negative/supporting evidence, and the in-portal walkthrough is the sole authoritative source (RESEARCH.md Summary; VERIFICATION-NOTE.md). |
