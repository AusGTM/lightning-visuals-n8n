# API Coverage — HubSpot CRM v3 Search API + Lusha v3 Contacts

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Produced at plan time (Phase 36), per the API Coverage Decision Checkpoint.

Two external surfaces are touched by this phase: **HubSpot CRM v3 Search** (a new
contacts match lane) and **Lusha v3 `/v3/contacts/search-and-enrich`** (an identity-set
widening). Each is decided from a full-coverage baseline independently — the Lusha rows
are NOT carried over from the HubSpot rows and vice versa.

## HubSpot CRM v3 Search — contacts (`POST /crm/v3/objects/contacts/search`)

| capability | decision | reason |
|---|---|---|
| filter `email EQ` (HIGH tier lane) | INTEGRATE | |
| filter `hs_object_id EQ` (fetch-by-id lane) | INTEGRATE | existing lane, unchanged |
| filter `lastname EQ` + `company CONTAINS_TOKEN` in one AND-group (MEDIUM tier lane) | INTEGRATE | |
| `properties` projection on the search body | INTEGRATE | reuses `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV` so the MEDIUM candidate carries `company` |
| `limit` on the search body | INTEGRATE | `_hs_http_search_node`'s existing default |
| filter `phone` / `mobilephone` as a match key | OPT-OUT | not in the locked tier ladder — 36-CONTEXT.md §4 decision 2 fixes it at email → lastname+company. `resolveIdentity.js`'s `phone_lastname` branch stays dead in this lane |
| filter `lv_linkedin_url` as a match key | OPT-OUT | not in the locked tier ladder (same decision); LinkedIn identity still reaches the *providers*, just not the HubSpot match search |
| operator `NOT_CONTAINS_TOKEN` / `NEQ` / `NOT_IN` (negative/exclusion filters) | OPT-OUT | no exclusion lane in scope this phase |
| operator `IN` (multi-value match) | OPT-OUT | one row is searched per lane per request; a multi-value filter has no caller |
| `sorts` on the search body | OPT-OUT | deliberate — `mediumCandidates` re-verifies by value and returns every verified candidate for the caller to judge. Server-side ordering would imply a ranking this phase explicitly refuses to assert (36-CONTEXT.md §6: MEDIUM is a proposal, `auto:false`) |
| result paging (`after` cursor / `paging.next`) | OPT-OUT | unreachable — `ENRICH_MAX_LIST_RECORDS = 2` caps a request at 2 rows and each lane issues one `limit`-bounded search per row |
| companies search as a *match* lane (`name` / `domain`) | OPT-OUT | 36-CONTEXT.md §7 step 3 scopes the match lane to contacts. The companies branch still receives the propose write-guard (step 4), just not the match search |
| batch read (`POST /batch/read`) | OPT-OUT | not needed — one row per lane per request |
| create / update / batch-write endpoints | OPT-OUT | this phase writes nothing new; the existing write path and its two-key gate are untouched |

## Lusha v3 — `POST /v3/contacts/search-and-enrich`

| capability | decision | reason |
|---|---|---|
| identity `email` | INTEGRATE | existing |
| identity `linkedinUrl` | INTEGRATE | existing |
| identity `firstName` + `lastName` + `companyName` | INTEGRATE | 36-CONTEXT.md §7 step 7 — the widening this phase ships |
| identity `domain` | INTEGRATE | same widening; `lushaContactBody()` (`n8n/code/lushaRequest.js:79-98`) already emits it |
| `reveal` field selection (`emails`, `phones`) | INTEGRATE | existing, derived from the Enrichment Gate's `missingFields` |
| companies enrichment endpoint | OPT-OUT | the companies branch has its own Lusha node and is out of this phase's match/identity scope |
| stored-`contactId` re-enrich (0-credit path, `docs/LUSHA-V3-CONTRACT.md`) | OPT-OUT | not needed yet — a pre-ingest propose row has no stored Lusha id by definition; tracked for a follow-up phase |
| bulk / async job endpoints | OPT-OUT | not needed — request size is capped at 2 rows |

## Anthropic Messages API

No change. The Claude web-research and judge nodes are untouched by this phase.
