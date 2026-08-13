# Phase 50 — API Coverage Matrix

External APIs integrated by this phase: **HubSpot CRM v3 Properties**, **HubSpot Automation v4
Flows**, **HubSpot CRM v3 Lists**. No new libraries; all three surfaces are already reached by
existing `scripts/`.

`INTEGRATE` is the default. Every `OPT-OUT` carries a one-line reason.

## HubSpot CRM v3 Properties (`/crm/v3/properties/companies`)

| capability | decision | reason |
|---|---|---|
| `POST /crm/v3/properties/companies` (create property) | INTEGRATE | creates `lv_icp_tier_derived` (D-01, D-14) via `scripts/sync_hubspot_properties.py` |
| `GET /crm/v3/properties/companies` (list) | INTEGRATE | drift comparator + create-diff already read this |
| `GET /crm/v3/properties/companies/{name}` (read one) | INTEGRATE | formula read-back verification, 404 teardown check |
| `GET /crm/v3/properties/companies?archived=true` (list archived) | INTEGRATE | answers RESEARCH Q6 — confirms DELETE is a soft archive before D-06 runs |
| `PATCH /crm/v3/properties/companies/{name}` (update, incl. `calculationFormula`) | INTEGRATE | D-04's fallback path re-points the formula without re-creating the property |
| `DELETE /crm/v3/properties/companies/{name}` (archive) | INTEGRATE | D-06's gated retirement of `lv_icp_tier`; also the probe's `finally` teardown |
| `POST /crm/v3/properties/companies/batch/create` | OPT-OUT | not needed — one property is created; `sync_hubspot_properties.py` deliberately avoids batch for unambiguous per-item status |
| `POST /crm/v3/properties/companies/batch/read` | OPT-OUT | not needed — the full list read covers every consumer here |
| `POST /crm/v3/properties/companies/batch/archive` | OPT-OUT | not needed — exactly one property is archived, under a one-way decision gate |
| Property **groups** endpoints (`/groups` create/read/update/delete) | OPT-OUT | not needed — `companyinformation` already exists and is reused |

## HubSpot Automation v4 Flows (`/automation/v4/flows`)

| capability | decision | reason |
|---|---|---|
| `GET /automation/v4/flows` (list) | INTEGRATE | D-13's dependent sweep greps flow bodies for tier references |
| `GET /automation/v4/flows/{id}` (read one) | INTEGRATE | WF1 before/after snapshot, `isEnabled` read-back |
| `PUT /automation/v4/flows/{id}` (update — `isEnabled: false`) | INTEGRATE | D-08's switch-off, and D-18's rollback step 1 (`isEnabled: true`) |
| `POST /automation/v4/flows` (create) | OPT-OUT | explicitly out of scope — this phase retires a flow, it creates none |
| `DELETE /automation/v4/flows/{id}` | OPT-OUT | forbidden by D-08 — WF1's definition is kept, not deleted |
| `POST /automation/v4/flows/batch/read` | OPT-OUT | not needed — the list endpoint returns every flow body the sweep greps |
| Flow **enrolment** endpoints | OPT-OUT | none exist — RESEARCH Q1 resolves to a documented negative; v4 exposes no enrolment call and the legacy v2 one is contacts-only |

## HubSpot CRM v3 Lists (`/crm/v3/lists`)

| capability | decision | reason |
|---|---|---|
| `GET /crm/v3/lists` (enumerate lists) | INTEGRATE | D-13's dependent sweep, company object type |
| list filter-branch read | INTEGRATE | the sweep greps filter definitions for tier references |
| `GET /crm/v3/lists/{id}/memberships` | OPT-OUT | not needed — filter *definitions* answer "does this list depend on the tier"; membership rosters do not |
| list create / update / delete | OPT-OUT | explicitly out of scope — D-11 escalates an unmigratable dependent to the operator rather than mutating lists here |

## API-blind surfaces (no capability to decide on)

Saved views / saved filters and reports / dashboards have **no documented public HubSpot API**
(RESEARCH Q3). They are not opt-outs — there is nothing to integrate. They are covered by a
logged manual UI check recorded in `50-DEPENDENTS-SWEEP.md`.
