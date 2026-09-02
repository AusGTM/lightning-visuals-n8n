# Phase 62 — External API Coverage Matrix

Produced 2026-09-02 to satisfy the `api-coverage.verify-pre` gate before UAT.

Phase 62 ("Suggest the contacts nobody named") adds an operator-attended contact-suggestion
round. It introduces **one new external-API consumer** — `scripts/role_vocabulary.py`, an
offline admin script — and threads a request-level flag through an existing dispatch path.
It opens **no new vendor account, no new provider, and no new integration surface**: every
API below was already in use by this project before Phase 62.

## Matrix

| capability | decision | reason |
|---|---|---|
| hubspot.contacts.search | INTEGRATE | role_vocabulary.py:90 pages POST /crm/v3/objects/contacts/search read-only to harvest jobtitle values for role clustering. See note A. |
| hubspot.companies.search | INTEGRATE | Added num_associated_contacts to the company search property set so the round can tell an empty company from a staffed one. Backend n8n lane. |
| hubspot.contacts.write | OPT-OUT | The round produces proposals, never writes. Contact creation stays in the ingest lane. See note B. |
| hubspot.companies.write | OPT-OUT | No company property is written by this phase. Company creation remains in the enrichment lane's companies branch, where dedupe already lives. |
| hubspot.associations | OPT-OUT | Deliberately not reimplemented — association has exactly one operational implementation. See note B. |
| hubspot.webhooks | OPT-OUT | No new subscription. The round is operator-invoked or offered after a batch; it needs no HubSpot-originated event. |
| anthropic.messages | INTEGRATE | role_vocabulary.py:121 makes one cached Haiku clustering call over harvested job titles, gated behind SPARSE_THRESHOLD. See note C. |
| anthropic.web_search | OPT-OUT | Discovery uses the host's plugin-side web_fetch over the existing sitemap ladder, not the server-side web_search tool. Backend web_fetch stays prohibited. |
| anthropic.batch | OPT-OUT | One cached vocabulary call per portal does not justify batch submission; there is no per-record model call in this lane. |
| n8n.webhook.contact-upload | INTEGRATE | dispatch.py gained a request-level source_by_field flag on the existing POST, following the recompute/async_ack/scale_up idiom. No new endpoint. |
| lusha.search-and-enrich | INTEGRATE | Stage 2 fills email/phone for a person named by stage 1, via the existing backend waterfall. No plugin script calls Lusha directly. |
| lusha.prospecting | OPT-OUT | Excluded by standing decision; this was the original design and was re-scoped away. See note D. |
| zoominfo.* | OPT-OUT | Untouched by this phase. The company waterfall's ZoomInfo lane is unchanged; the round adds no ZoomInfo call. |
| apollo.* | OPT-OUT | Untouched by this phase. Unchanged provider lane; no new Apollo call. |

## Notes

**A — credential boundary.** `scripts/role_vocabulary.py` lives at the repo root beside
`inventory_org_type_values.py`, the portal-reading lane. It is portal- and credential-guarded.
No script under `operator-claude-plugin/` holds HubSpot credentials, and Phase 62 does not
change that.

**B — the association rule has one implementation.** Contact creation and contact→company
association live solely in `wf_contact_ingest_cloud` (CLAUDE.md §13.0.1). Phase 61 closed the
enrichment-lane gap by *refusal* rather than duplication, and Phase 62 preserves that: a second
writer or a second copy of the association subgraph would create a driftable duplicate of a
load-bearing rule.

**C — the model call is cached, not per-round.** The Haiku clustering result is committed as
`operator-claude-plugin/config/role_vocabulary.yaml`, so the call is made when the vocabulary
is regenerated, not on every suggestion round. The shipped file records `evidenced: false`
where the generic fallback was used (D-62-07).

**D — the Lusha re-scope defines this phase.** `/v3/contacts/search-and-enrich` is not a
discovery endpoint: `jobTitle` is response-only, not a request filter. Discovery-by-title would
require Lusha Prospecting, which is excluded by standing decision. Phase 62 was therefore
re-scoped to plugin-side web research over the existing sitemap ladder, with the enrich
waterfall filling details afterwards. The two Lusha rows are the substantive pair.

**No new credentials or vendor accounts.** Every INTEGRATE row uses an API and a key this
project already held before Phase 62.

**Nothing armed.** No row above was exercised against live production writes during Phase 62.
The first live unattended credit-spending batch remains gated on Phase 57.
