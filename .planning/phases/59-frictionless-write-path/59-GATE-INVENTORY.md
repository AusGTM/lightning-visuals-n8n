# Phase 59 — Gate Inventory (D-59-08)

**Built:** 2026-08-28, plan 59-05 Task 1.

Every operator-facing refuse-and-stop gate across the ingest, enrichment, grant and preingest
lanes, decided against D-59-08's ruling: *"instead of immediate refusal, Claude operator side
should try to resolve and propose."* `CONVERT` is the default; `NOT-APPLICABLE` requires the
stated reason to be, specifically, that no legitimate resolution source exists for what the gate
refuses. Difficulty, rarity, effort and perceived payoff are never a reason.

**Legend:** decision is one of `CONVERT` / `ALREADY-CONVERTED` / `NOT-APPLICABLE`. Owner names
the plan that converts it, or `n/a` when the decision is `NOT-APPLICABLE`/`ALREADY-CONVERTED`.

## Gates

| Gate | Site | Lane | What it refuses today | Decision | Legitimate resolution source | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| GATE-01 | `extraction.py:531-540` (identity pre-flight) | ingest | A contact row with no non-blank `email` and no complete `firstname`/`lastname`/`company`; a company row with no non-blank `name`. This is the ruling's own origin — the LinkedIn-sourced row that dead-ended in `53-WALK-RECORD.md`. | **CONVERT** | HubSpot lookup, operator statement, provider result, same-row derivation | **Task 2 of this plan (59-05)** |
| GATE-02 | `enrichment.py:314` (`build_envelope`, people form) | enrichment | A named person with no email, no `linkedin_url`, and no `lastname`+`company` pair — the backend's own match gate would burn three provider calls on a row that can only return nothing, so the client refuses first. | **CONVERT** | HubSpot lookup (name search), operator statement, provider result | **59-06** |
| GATE-03 | `enrichment.py:368` (`build_envelope`, companies form — a profile-page URL with no name) | enrichment | A company row whose only given value is a social/profile-page URL (`_clean_domain` returns `None`) and carries no `name`, so neither a domain nor a name is usable. | **CONVERT** | HubSpot lookup (search on whatever name text accompanied the page), operator statement | **59-06** |
| GATE-04 | `enrichment.py:377` (`build_envelope`, companies form — blank `name`, no domain) | enrichment | A company row's `name` key is present but blank, and there is no website/domain either. | **CONVERT** | Operator statement (ask for the company's actual name) | **59-06** |
| GATE-05 | `enrichment.py:385` (`build_envelope`, companies form — no `name` key at all, no domain) | enrichment | A company row never carried a `name` key at all (e.g. a search-results-screenshot row whose name never rendered), and has no domain either. | **CONVERT** | Operator statement | **59-06** |
| GATE-06 | `write_grant.py:440-444` (`plan_grant`, empty record set) | grant | A grant cannot be planned when neither `record_ids` nor `record_domains` are given. This is **FINDING 1** of the Phase 53 walk (`53-WALK-RECORD.md`) — a create with no HubSpot id and no email domain is unreachable on every armed path. | **CONVERT** | HubSpot lookup for the company's own domain — exactly how the walk resolved it (Series Futsal Victoria, `283816805830`, `seriesfutsal.com`, found read-only) | **59-06** |
| GATE-07 | `company_domain.py` (whole module) | ingest (company lane) | A company row Claude or the backend's research resolved a candidate domain for, used to have no confirm/correct/decline path. | **ALREADY-CONVERTED** | — the precedent every other row in this table follows: propose, never silently write | Phase 58 (shipped) |
| GATE-08 | `preingest.py` `classify_matches`'s `unmatched` bucket (tier `none`) | preingest | A row with no matching HubSpot record. | **ALREADY-CONVERTED** | — already proceeds to create/propose rather than refusing; it was never a refuse-and-stop gate in the first place | shipped |
| GATE-09 | `enrichment.py:152` (`normalize_object_type`) | enrichment | An `object_type` token this lane does not recognize (not `contacts`/`companies`). | **NOT-APPLICABLE** | no legitimate resolution source — this is a caller/API misuse of an internal literal, not a missing value to look up; nothing a HubSpot read, an operator statement, a provider result or a same-row derivation could supply would make an unrecognized token become one of the two valid ones | n/a |
| GATE-10 | `enrichment.py:232,250,258,289,296,344,352,406,417`; `chunking.py:144,164,182,202,218`; `preingest.py:67,74,76`; `write_grant.py:428,433` | enrichment / chunking / preingest / grant | Empty batches (no rows/people/companies/record IDs/lanes given at all) and structurally malformed shapes (a record specification that is not a dict, a row that is not a dict, a row missing its minted `row_id`, an unknown lane name). | **NOT-APPLICABLE** | no legitimate resolution source — there is no partial row or value to look anything up for; the caller supplied nothing at all, or something structurally wrong, which is a caller bug to fix, not a gap a lookup could fill | n/a |
| GATE-11 | `preingest.py:272` (`ClassifyError`, duplicate `row_id` in a backend response) | preingest | A backend response carries two items for the same `row_id`. | **NOT-APPLICABLE** | no legitimate resolution source — a duplicated join key is a defect signal, not a missing value; nothing external tells us which of the two response items is correct, so there is nothing to look up | n/a |
| GATE-12 | `chunking.py:120,127,131` (`chunk_ceiling`) | chunking | The operator config's per-request record ceiling is missing, the wrong type, or below 1. | **NOT-APPLICABLE** | no legitimate resolution source — this is an admin-set deployment value (a timeout bound, per the function's own docstring), and no HubSpot read, operator statement, provider result or same-row derivation can produce it; same reasoning as `config_gate.ConfigError` below | n/a |
| GATE-13 | `config_gate.py:148,154,160,162,195` (`ConfigError`) | config | The plugin's local config file is missing, unparseable, missing `n8n_url`, `n8n_url` is not `https://`, or a capability's required keys (e.g. `webhook_secret`) are absent. | **NOT-APPLICABLE** | no legitimate resolution source — a credentials/config file is missing, and no HubSpot read, operator statement, provider result or same-row derivation can produce a webhook secret or a base URL. **This is the canonical NOT-APPLICABLE case**, per the decision rule this inventory applies uniformly. | n/a |
| GATE-14 | `name_split.py:173,178,184,199,250,270` (`NameSplitError`) | ingest | A name-split write would misalign rows against their resolved names, overwrite an already-populated `firstname`/`lastname` column, target a column that does not exist in the file, or the CLI was invoked with no `--propose`/`--apply` mode. | **NOT-APPLICABLE** | no legitimate resolution source — these are file-integrity and write-safety guards against corrupting the operator's own file, not gaps in a row's identity; nothing external could safely resolve a misalignment or a would-be overwrite except the operator supplying a corrected file, which is not a lookup | n/a |
| GATE-15 | `header_suggest.py:219,226,237` (`HeaderSuggestError`) | ingest | The canonical-prop allowlist could not be resolved, a confirmed header correction targets a value outside the canonical set, or a header name matches a refused PII shape (`firstname`/`lastname` etc — T-34-05's deliberate security refusal). | **NOT-APPLICABLE** | no legitimate resolution source — these are input-validation and security-allowlist controls (the same kind as `write_dispatch_csv`'s STRUCT-01 guard), not missing-identity gaps; nothing legitimately resolves an operator typo or a deliberately-refused header shape except retyping it correctly, which is not a lookup | n/a |
| GATE-16 | `extraction.py:483,488-496,504,513-521` (per-record pre-flight: record not an object, unrecognized `record_type`, row not an object, missing/incomplete provenance) | ingest | A structurally malformed artifact record. | **NOT-APPLICABLE** | no legitimate resolution source — this is malformed input (a caller bug: Claude wrote a bad artifact), not a missing value; there is nothing to look up, only the artifact to rewrite correctly | n/a |

## Resolution sources, restated as the implementable contract

Copied verbatim from `59-CONTEXT.md` § D-59-08, so a later converter reads it in the same file
as the gate list rather than two documents away:

| Legitimate resolution sources | Illegitimate |
| --- | --- |
| HubSpot itself, read-only (the walk resolved `seriesfutsal.com` this way) | Claude's own recall about the person or company from training data |
| The operator's own statements earlier in the conversation | Inference from "companies like this usually…" |
| The enrichment waterfall's provider results | A plausible corporate email pattern (`first@company.com`) |
| Another field of the same row, by stated derivation (a slug, a domain from an email) | Anything the operator would have no way to check |

The right-hand column is still invention and stays forbidden. The left-hand column is lookup, and
lookup was never what the no-invention rule was aimed at.

**Closed source vocabulary Task 2 introduces:** `extraction.RESOLUTION_SOURCES`, a frozenset
holding exactly `hubspot_lookup`, `operator_statement`, `provider_result`,
`same_row_derivation` — the four plain-identifier names for the left-hand column above. 59-06
extends this ONE vocabulary rather than inventing a second.

## Unplanned items

None. Every gate decided `CONVERT` above is owned by either Task 2 of this plan (GATE-01) or by
59-06 (GATE-02 through GATE-06) — no `CONVERT` gate was found without an owning plan in this
phase.
