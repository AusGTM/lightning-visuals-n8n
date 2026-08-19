# Phase 51 — API Coverage Matrix

External APIs integrated by this phase: **ZoomInfo GTM** (OAuth, usage, company enrich) and
**HubSpot CRM v3** (company search + read). No new library is installed; `requirements.txt` is
unchanged.

`INTEGRATE` is the default. Every `OPT-OUT` carries a one-line reason. This matrix is the
subtraction record for a phase that is deliberately **dry-run only** — every write-side capability
on both surfaces is opted out here and belongs to Phase 52.

## ZoomInfo GTM (`api.zoominfo.com/gtm/...`)

| capability | decision | reason |
|---|---|---|
| `oauth/v1/token` (client_credentials mint) | INTEGRATE | reused via `scripts/check_provider_credits.py::_mint_zoominfo_token`; the only place the client id/secret are read |
| `data/v1/users/usage` (credit balance) | INTEGRATE | D-03 sizes the run against the live balance before it starts |
| `data/v1/companies/enrich` (match by `companyWebsite`) | INTEGRATE | D-02's firmographic source; supplies revenue, country, employees, industry |
| `companies/search` (name/keyword search) | OPT-OUT | domain match is sufficient for this population; name search would spend credits on ambiguous matches |
| `companies/enrich` field `companyType` | OPT-OUT | not entitled on this account — returns 400 PFAPI0009 (probed in Phase 41) |
| `contacts/enrich` | OPT-OUT | companies only — REQUIREMENTS.md "Out of Scope" excludes contacts from this milestone |
| `contacts/search`, contact usage surfaces | OPT-OUT | same — companies only |
| intent signals | OPT-OUT | not an input in the Phase 46 settled rubric; would add cost with no scoring effect |
| technologies / technographics | OPT-OUT | same — not a rubric input |
| bulk / async job endpoints | OPT-OUT | the sample is one page of ≤100 records; the 1-25-companies-per-request sync form covers it |

## HubSpot CRM v3 (`api.hubapi.com/crm/v3/...`)

| capability | decision | reason |
|---|---|---|
| `objects/companies/search` | INTEGRATE | the `NOT_HAS_PROPERTY(lv_icp_fit_score)` population count and the bounded sample, plus the `HAS_PROPERTY` scored-population baseline |
| `objects/companies/{id}` GET | INTEGRATE | the per-record read behind `51-BEFORE-SNAPSHOT.json` |
| `objects/companies/{id}` PATCH | OPT-OUT | Phase 52; Phase 51 is dry-run only |
| `objects/companies/batch/update` | OPT-OUT | Phase 52; Phase 51 is dry-run only |
| `objects/companies` POST (create) | OPT-OUT | this milestone never creates a company — the population already exists in the portal |
| `objects/companies/{id}` DELETE | OPT-OUT | this milestone never removes a company |
| `objects/companies/batch/read` | OPT-OUT | the snapshot population fits a per-record read loop; batching adds a second read shape for no benefit at this size |
| `properties/companies` (schema read/write) | OPT-OUT | the property schema settled in Phase 50; this phase writes no property definition |
| `objects/contacts/*` | OPT-OUT | companies only, per REQUIREMENTS.md "Out of Scope" |
| `objects/notes`, `associations` | OPT-OUT | not reached by this phase's population definition; no audit note is written in a phase that writes nothing |
| `lists` | OPT-OUT | the population is derived by search filter, not by a static list |
| `automation/v4/flows` | OPT-OUT | zero n8n and zero workflow change is the milestone's core constraint |
| webhooks / subscriptions | OPT-OUT | same — a property-change subscription would trigger the n8n lane this milestone has no credits for |

## Pagination note

`src/hubspot_client.py::search_records` has no `after`-cursor loop. Phase 51 needs only a count
(the `limit=1` + `total` trick) and one bounded page, so this is sufficient here. Phase 52's chunked
remainder needs the full ~646-id never-scored list and must add pagination first — recorded as a
Phase 52 prerequisite, not silently ignored.
