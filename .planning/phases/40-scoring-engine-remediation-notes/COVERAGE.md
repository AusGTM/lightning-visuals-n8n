# Phase 40 — External API Coverage Matrix

**Written:** 2026-08-06 (planner, `/gsd-plan-phase 40`)
**Scope:** every external-API capability in play for Phase 40. `INTEGRATE` is the default;
every `OPT-OUT` carries a one-line reason. This file is the seal-gate artifact for the API
Coverage Decision Checkpoint.

**APIs in play:**
1. HubSpot Automation v4 — `/automation/v4/flows` (new usage surface this phase; `automation`
   scope granted 2026-08-06)
2. HubSpot CRM v3 Properties — `/crm/v3/properties/companies` (incl. `calculationFormula` PATCH)
3. HubSpot CRM v3 Objects — `/crm/v3/objects/companies` (incl. `batch/update`)

---

## 1. HubSpot Automation v4 — Flows

| Capability | Endpoint | Decision | Plan | Reason / Notes |
|---|---|---|---|---|
| Read one flow | `GET /automation/v4/flows/{flowId}` | INTEGRATE | 40-01 | D-05 — every flow edit starts from a live GET; four flows archived to `config/hubspot_flows/*.before.json` |
| List flows | `GET /automation/v4/flows` | INTEGRATE | 40-01 | Confirms the four known IDs are the only enabled company scoring flows; catches a fifth nobody knew about |
| Update flow (full replace) | `PUT /automation/v4/flows/{flowId}` | INTEGRATE | 40-01, 40-04, 40-05, 40-06 | D-05 core path. PUT is replace-not-merge — always PUT the full stripped GET body (Pitfall 1) |
| Enable / disable flow | `PUT` with `isEnabled` true/false | INTEGRATE | 40-01, 40-04, 40-05, 40-06 | D-07's safety envelope — disable, edit, validate on disposables, re-enable |
| Create flow | `POST /automation/v4/flows` | INTEGRATE | 40-04 | Required by D-06 — the two new mapper flows (`produces_content_score`, `gambling_score`) are net-new flows, not edits |
| Delete flow | `DELETE /automation/v4/flows/{flowId}` | OPT-OUT | — | D-05/D-06 reject delete-and-recreate; the four existing flows are fixed in place, never destroyed |
| Batch read flows | `POST /automation/v4/flows/batch/read` | OPT-OUT | — | Four IDs; per-flow GET is simpler and gives per-flow archive files directly |
| Flow execution / enrollment history | `GET .../executions` | OPT-OUT | — | Live behaviour is proven by observing the disposable company's property state, not by reading HubSpot's own execution log |

**Fallback (pre-committed, D-05):** if `PUT` rejects or silently no-ops an action-content edit
(branch condition type change, second enrollment trigger), the portal-UI hand-edit absorbs that
specific edit. The `.before.json`/`.after.json` archive and the offline conformance test apply
either way — the fallback changes the *editor*, not the record of what the flow must contain.

---

## 2. HubSpot CRM v3 — Properties (companies)

| Capability | Endpoint | Decision | Plan | Reason / Notes |
|---|---|---|---|---|
| Read one property | `GET /crm/v3/properties/companies/{name}` | INTEGRATE | 40-01 | Open Question 1 (`lv_icp_tier` enum options — is `Unscored` present?) and Open Question 2 (`lv_icp_fit_score` exact `calculationFormula` syntax, Pitfall 3) |
| Read all properties | `GET /crm/v3/properties/companies` | INTEGRATE | 40-01 | Confirms which `*_score` component properties already exist before creating new ones |
| Create property | `POST /crm/v3/properties/companies` | INTEGRATE | 40-04 | D-06 — `produces_content_score` and `gambling_score` (number, default 0, mirroring the existing components' `PROPERTY_DEFAULT_VALUE` stamp) |
| Update property — `calculationFormula` | `PATCH /crm/v3/properties/companies/lv_icp_fit_score` | INTEGRATE | 40-04 | D-06's fifth/sixth sum terms. Highest-uncertainty properties call (Pitfall 3) — extend the fetched syntax, never hand-construct |
| Update property — enum options | `PATCH /crm/v3/properties/companies/lv_icp_tier` | INTEGRATE | 40-06 | Conditional on 40-01's finding: add the `Unscored` option only if absent (Pitfall 5) |
| Archive / delete property | `DELETE /crm/v3/properties/companies/{name}` | OPT-OUT | — | Nothing is retired this phase; superseded-artifact archival is CLEAN-01 / Phase 42 |
| Property groups | `/crm/v3/properties/companies/groups` | OPT-OUT | — | New properties join the existing group the current `*_score` components already sit in; no group is created |

---

## 3. HubSpot CRM v3 — Objects (companies)

| Capability | Endpoint | Decision | Plan | Reason / Notes |
|---|---|---|---|---|
| Read record | `GET /crm/v3/objects/companies/{id}` | INTEGRATE | 40-01..40-07 | `get_record()` — every disposable validation and every parity assertion reads live state here |
| Create record | `POST /crm/v3/objects/companies` | INTEGRATE | 40-01, 40-04, 40-05, 40-06, 40-07 | `create_record()` — disposable `ZZ-SCORING-TEST-DELETE-ME-*` fixtures (D-07, D-13) |
| Update record | `PATCH /crm/v3/objects/companies/{id}` | INTEGRATE | 40-01, 40-04, 40-05, 40-06, 40-07 | `patch_record()` — drives the disposable through each scoring input |
| Batch update | `POST /crm/v3/objects/companies/batch/update` | INTEGRATE | 40-07 | D-10's backfill seed mechanism, 100 records/batch. New `batch_update_companies()` helper |
| Delete record | `DELETE /crm/v3/objects/companies/{id}` | INTEGRATE | 40-01, 40-04, 40-05, 40-06, 40-07 | `delete_record()` — guaranteed teardown of every disposable, even on exception |
| Search records | `POST /crm/v3/objects/companies/search` | INTEGRATE | 40-07 | Selecting the real-record sample for PARITY-01 / the backfill proof (read-only) |
| Batch create | `POST .../batch/create` | OPT-OUT | — | Disposable fixtures are created one at a time so each carries an individually-asserted lifecycle and teardown |
| Batch archive | `POST .../batch/archive` | OPT-OUT | — | Teardown is per-record and paired with its create; a batch archive would blur which record failed |
| Associations | `/crm/v4/associations/...` | OPT-OUT | — | Scoring is company-property-local; no association is read or written |
| Lists / list membership | `/crm/v3/lists/...` | OPT-OUT | — | Review-queue surfacing is out of scope (CLEAN-01 / v0.7 review-queue policy is deferred) |

---

## Authentication & Scope

| Item | Value |
|---|---|
| Auth | HubSpot private-app bearer token, `HUBSPOT_PRIVATE_APP_TOKEN`, injected via `src/hubspot_client.hs_headers()` |
| Scopes required | `automation` (granted 2026-08-06), `crm.objects.companies.read/write`, `crm.schemas.companies.read/write` |
| New scopes this phase | None |
| Portal guard | `22617666` (ap1) asserted before any live call, per `scripts/snapshot_hubspot_schema.py` / `scripts/probe_scoring_recalc_latency.py` convention |
| Secret handling | `.env` is Read/Bash permission-blocked — token-dependent commands are handed to the operator as `!`-prefixed invocations. No write helper ever prints `hs_headers()` |

## Rate limits

HubSpot standard: 100 req / 10 s per portal (Pro). Nothing this phase approaches it — the largest
single call is one 100-record batch update (40-07). No pagination loop, no polling tighter than
the 5 s disposable-settle interval.
