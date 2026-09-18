# API Coverage — Phase 73.1 provider discovery (Apollo, ZoomInfo GTM, Lusha v3, HubSpot)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

**Detector:** `api-coverage.cjs` returned `detected: false` against the ROADMAP phase text alone
and `detected: true` once the nine PLAN.md bodies existed. This matrix is written against the
plan bodies.

**Standing constraint on every row below:** provider credentials live only in n8n credentials and
the plugin never holds one (CLAUDE.md standing rule, RESEARCH.md Architectural Responsibility
Map). Any INTEGRATE decision therefore means "wired as an n8n node", never "called from the
plugin".

**Confidence marker:** every provider *search* endpoint in this phase is `[ASSUMED]` from vendor
documentation. No search-by-role endpoint has ever been called live in this repository. The D-12
probe (`scripts/probe_provider_discovery.py`, plan 09) resolves each one, and a row's decision may
change on that evidence.

---

## Apollo

| capability | decision | reason |
|---|---|---|
| people search (`/v1/mixed_people/search` or equivalent) | INTEGRATE | `[ASSUMED]` — the discovery lane's rung-1 and rung-2 calls (D-11, D-11a), plan 07 |
| `person_titles` provider-side title filter | INTEGRATE | `[ASSUMED]` (A5) — rung 1 of D-11a's ladder |
| people match (`/v1/people/match`) | OPT-OUT | already wired in the enrichment lane; it requires an already-known identity and cannot answer who works at a company — not a discovery endpoint (RESEARCH.md Pitfall 1) |
| reveal / unlock contact details | OPT-OUT | D-12 unruled — the lane is search-only and stage 2's existing enrich path keeps reveal |
| balance / usage read (`/api/v1/usage_stats/api_usage_stats`) | OPT-OUT (read-only, already wired) | returns per-endpoint RATE LIMITS, not a depleting credit pool — no per-search price is derivable, so Apollo's search is priced from vendor documentation only (`cost_rates.json` `apollo_per_match` citation) |
| org / company search | OPT-OUT | companies are supplied by the plugin from HubSpot; the lane resolves no company |
| sequences, emailer, CRM push | OPT-OUT | outside the phase goal — discovery names people, it does not contact them |

## ZoomInfo GTM Data v1

| capability | decision | reason |
|---|---|---|
| contact search (`/gtm/data/v1/contacts/search`) | INTEGRATE | `[ASSUMED]` (A2) — inferred from the confirmed-live `/companies/search` JSON:API family; first provider in D-11's waterfall |
| OAuth token mint + cache | INTEGRATE | reused verbatim from the enrichment lane's `ZoomInfo Token Gate` / `IF Needs Mint` / `ZoomInfo Mint` / `Cache Token` subgraph, sharing the same `sd.zoominfo` cache key — never a second ungated token |
| balance / usage read (`/gtm/data/v1/users/usage`) | INTEGRATE (probe only) | read before and after each search in the D-12 probe; needs `Accept: application/vnd.api+json` or answers 406 |
| contacts enrich (`/gtm/data/v1/contacts/enrich`) | OPT-OUT | already wired in the enrichment lane; identity-only, not discovery |
| companies search (`/gtm/data/v1/companies/search`) | OPT-OUT | confirmed live but out of scope — this phase discovers people, not companies |
| intent / scoops / technologies | OPT-OUT | no ICP signal in this phase consumes them; adding one is a later decision |

## Lusha v3

| capability | decision | reason |
|---|---|---|
| prospecting / people search | INTEGRATE | `[ASSUMED]` (A3) — third in D-11's waterfall. `docs/LUSHA-V3-CONTRACT.md`, this account's contract of record, does not mention a prospecting product at all; it may not be entitled on this plan, in which case the D-12 probe drops Lusha from the waterfall rather than leaving a node that 404s every round |
| contacts search-and-enrich (`/v3/contacts/search-and-enrich`) | OPT-OUT | already wired in the enrichment lane; despite its name every probed request body requires an identity — it resolves ONE known person, it does not list unknown ones |
| reveal | OPT-OUT | D-12 unruled — search-only; and Lusha's reveal has already been measured at 7 credits worst case (execution 12372), which is exactly the spend this phase is not adding to the lane |
| balance read (`/v3/account/usage`, `credits.remaining`) | INTEGRATE (probe only) | the one provider whose balance delta can actually price a search |
| companies match | OPT-OUT | out of scope; already wired for company enrichment |

## HubSpot

| capability | decision | reason |
|---|---|---|
| contact search by `mobilephone` EQ | INTEGRATE | D-16a's new ingest rung; searchability verified live 2026-09-18 (200, total 0) |
| contact search by `hs_linkedin_url` EQ | INTEGRATE | D-16a's LinkedIn rung, reusing the Phase 61 idiom |
| contact search by `phone` EQ | OPT-OUT | D-16a-i, operator ruling — a landline is often a shared switchboard; `phone` is identity for CREATE only and is never a match rung, even though the property IS EQ-searchable |
| account info (`GET /account-info/v3/details`) | INTEGRATE | D-14c's backend portal proof; endpoint and `portalId` field verified live 2026-09-18 (200, `portalId: 22617666`) |
| contact create / update / associate | OPT-OUT (unchanged) | already wired in the ingest lane; the discovery lane is read-only and contains no write node, asserted at generation time by `assert_no_write_nodes` |
| any HubSpot call from inside the discovery lane | OPT-OUT | D-09 — the plugin sends `num_associated_contacts` and the lane echoes it; the lane never re-reads HubSpot |

---

## Decisions that change on the D-12 probe's evidence

1. If a provider's search endpoint does not exist on this account, that provider's INTEGRATE row
   becomes an OPT-OUT and it is dropped from the waterfall (plan 09 Task 2).
2. If the operator rules reveal-in-lane, the three `reveal` OPT-OUT rows are re-opened — as a
   NEXT phase, not this one: the lane's read-only guarantee is asserted in code and its cost model
   was disclosed to the operator as search-only.
