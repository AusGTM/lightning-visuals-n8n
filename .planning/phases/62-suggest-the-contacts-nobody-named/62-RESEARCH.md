# Phase 62: Suggest the contacts nobody named - Research

**Researched:** 2026-09-02
**Domain:** Provider-driven contact discovery, layered onto the existing HubSpot enrichment/ingest pipeline (n8n Cloud + operator-claude-plugin)
**Confidence:** MEDIUM — the ingest-lane and grant-lane mechanics are HIGH confidence (live-probed contracts, read source); the phase's core premise (D-62-01/D-62-02) rests on a provider-capability finding that is itself HIGH confidence but forces the phase's shape to change before a PLAN.md can be written faithfully.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Discovery provider:** D-62-01 (Lusha `/v3/contacts/search-and-enrich` is the discovery provider,
departing from SUGGEST-05's Apollo/ZoomInfo wording) · D-62-02 (one combined search+enrich call,
priced upfront, no find-then-confirm-then-enrich flow) · D-62-03 (no-hits records "no candidates
found," a second-provider fallback is deferred not built) · D-62-04 (candidate company set is the
batch just processed, not the whole portal and not an operator-supplied list).

**Role vocabulary:** D-62-05 (cluster live `jobtitle` values with Haiku, cached, not re-clustered
per run) · D-62-06 (offer the top N roles by recurrence, N fixed) · D-62-07 (sparse-portal fallback
to a disclosed, un-evidenced generic role list — **amends SUGGEST-03**, does not close it as
written).

**How suggestions land:** D-62-08 (proposed people enter as synthesised rows through
`extraction.py`/the contact-upload ingest lane — no new lane) · D-62-09 (a suggested person lands
with whatever identity the provider returns; no special-casing) · D-62-10 (the whole round lands as
proposals, no per-person/per-company confirmation).

**Trigger and scope:** D-62-15 (a round is auto-offered after a batch completes, unprompted, no
suppression setting this phase) · D-62-16 ("no contacts named" means zero associated contacts, not
"no contact matching the chosen roles") · D-62-17 (provenance uses the existing per-field mechanism
with `source=lusha`, not a new `lv_` property) · D-62-18 (dedupe is both a pre-filter and reliance
on the ingest lane's existing match as backstop).

**Pricing and the cap:** D-62-11 (one session grant covers the suggestion round — the allowance
enters `plan_grant`'s opening envelope, not a separate spend confirmation) · D-62-12 (per-company
cap, operator-set, default low 2-3, chosen once for the batch) · D-62-13 (over ceiling reuses Phase
57's `CEILING_OVER` refusal and split offer) · D-62-14 (the estimate is worst case, stated plainly
as a ceiling actuals land at or under).

Full text and reversibility notes: `.planning/phases/62-suggest-the-contacts-nobody-named/62-CONTEXT.md`.

### Claude's Discretion

None — every question in the discussion was answered explicitly. No "you decide" was selected.

### Deferred Ideas (OUT OF SCOPE)

- Apollo and ZoomInfo discovery adapters — the requirement names them; this phase ships Lusha only,
  adapter shaped for later addition (D-62-01).
- No-hits fallback to a second provider — unreachable until a second discovery adapter exists
  (D-62-03).
- Two-step discovery (find, confirm, then enrich) — rejected in favour of Lusha's combined call
  (D-62-02).
- "No contact matching the chosen roles" as the candidate rule — deferred as materially more
  expensive per round (D-62-16).
- A suppression setting for the auto-offer — deferred as unneeded surface until an operator finds
  the prompt noisy (D-62-15).
- A dedicated suggestion-provenance property — deferred in favour of existing provenance fields
  (D-62-17).
- A second discovery provider generally, and any change to how enrichment or the write path
  themselves work, and any new grant lane — per the Phase Boundary in CONTEXT.md.

**Note on this research pass:** § Summary below reports that D-62-01/D-62-02, as literally written,
rest on a provider-capability premise this research found to be false (see Priority 1). This is
surfaced as a finding for the operator to re-decide, per this agent's mandate ("research HOW to
implement [locked decisions] and surface anything that makes one unimplementable") — it is not this
document overriding the lock.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SUGGEST-01 | After companies are ingested/enriched with no contacts named, the system suggests contacts worth enriching rather than stopping. | D-62-15's client-side "batch complete" hook (`run_state.py`'s `done` verdict) names where the unprompted offer fires; D-62-16's zero-associated-contacts check names the read. Both researched below. |
| SUGGEST-02 | For a bulk company list, the suggestion is categorical (roles picked once, applied across the batch), not per-record. | D-62-06/D-62-12 (top-N roles, per-company cap chosen once) reuse `write_grant`'s existing pick-once-apply-across-batch shape — researched under "the rest of the priorities." |
| SUGGEST-03 | **AMENDED, not closed** — see D-62-07 in CONTEXT.md. The role vocabulary is derived from the portal's own `jobtitle` values, with a disclosed generic fallback permitted when the portal is too sparse. Do not tick as originally written ("not invented and not a generic B2B list" — no exception). | `scripts/inventory_org_type_values.py`'s read-only paged-inventory idiom, confirmed reusable for `jobtitle` on contacts; the Haiku-clustering step (D-62-05) is new work with no in-repo precedent. Researched below. |
| SUGGEST-04 | Suggested contacts are proposed, never auto-created — they land through the existing pre-ingest path (match, held rows, association contract). | Priority 3 (this document) confirms `extraction.py`'s real entry point (`validate()` on an in-memory dict) accepts synthesised rows with the identity contract unchanged — no special-casing needed for D-62-08/09/10. |
| SUGGEST-05 | The cost of a suggestion round is shown before it is spent — priced as one decision, not discovered mid-run. | D-62-11/13/14 reuse `write_grant.envelope()`/`plan_grant()`/`_affordable_record_count()` verbatim — confirmed live-in-repo under "the rest of the priorities." **Caveat:** the per-company cap arithmetic these decisions price assumes a search-shaped provider call; Priority 1's finding means this pricing must be re-derived once Open Question 1 is resolved. |

</phase_requirements>

## Summary

The three research-gate unknowns are resolved. The headline: **D-62-01/D-62-02 are unimplementable
as written.** The Lusha endpoint this repo has wired (`POST /v3/contacts/search-and-enrich`) is a
1:1 known-identity **resolution/enrichment** call — you already have to know the person's name,
email, or LinkedIn URL to call it. It has no mechanism to return "the people at company X who hold
title Y" when no such person is named. That capability is a genuinely different Lusha product line
(the **Prospecting API**, `docs.lusha.com/apis/openapi/prospecting-search-and-enrich`), which this
project's own standing decision declares **out of scope** (`.planning/workstreams/milestone/REQUIREMENTS.md`
§ Out of Scope: "Lusha Prospecting / Lookalikes / Tables / Decision Makers APIs — net-new
acquisition surfaces, not enrichment of existing CRM records"; `20-RESEARCH.md` Pitfall 1 names
exactly this conflation as a known trap). This is not a coding problem the planner can route around
inside Phase 62 — it is a premise problem the operator needs to re-decide.

Everything downstream of that premise researches cleanly: the ingest lane
(`extraction.py`/`column_mapping.yaml`/`n8n/code/columnMap.js`) accepts a programmatically
synthesised row with no file-upload assumption baked into its real entry point (`validate()`
takes a plain in-memory dict); the grant/ceiling machinery
(`write_grant.envelope()`/`plan_grant()`/`_affordable_record_count()`) already carries everything
D-62-11/12/13/14 ask for, needing only an added allowance line, not new mechanism; and the
per-field provenance D-62-17 wants to reuse is real and reusable, but is NOT the flat
`{field}_source` properties CLAUDE.md §6/§8 describe — those were never built (§4.0's running
theme). The as-built mechanism is the Phase 15 `lv_contact_enrichment_provenance` JSON blob,
written by `mergeContacts.js`, which already accepts a `source` override — it is hardcoded to
`"csv"` at the one call site (`scripts/build_cloud_workflows.py`'s `MERGE_CONTACTS` constant,
consumed by both `build_local()` and `build_cloud()`), a small, well-scoped change.

**Primary recommendation:** Before writing PLAN.md, take the D-62-01/D-62-02 finding back to the
operator (a `checkpoint:human-verify` or a return to `/gsd-discuss-phase`) with the two forward
options below (§ Open Questions). Everything else in this document — the ingest-lane reuse
contract, the grant/ceiling reuse, the provenance mechanism, the role-vocabulary sampling idiom —
is ready for planning regardless of which option the operator picks, because none of it depends on
which discovery mechanism eventually supplies the candidate people.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Role vocabulary derivation (cluster live `jobtitle` values) | API/Backend (offline script) | — | `scripts/inventory_org_type_values.py`-style read-only paged HubSpot inventory + one cached Haiku call; not a runtime n8n node |
| Company candidate-set selection ("the batch just processed") | Client (operator-claude-plugin) | API/Backend | The batch is already in the client's `run_state`/manifest; no new HubSpot query needed |
| "Zero associated contacts" check | API/Backend (HubSpot v4 associations read) | Client | One read per company; cheapest as a batched read alongside the batch's own company fetch |
| Discovery call (person search by company+role) | **BLOCKED — no tier currently owns this** | — | See Summary: the wired provider has no discovery mode; this is the premise gap |
| Suggested-row intake (match, held rows, association) | API/Backend (n8n Cloud ingest lane) | Client (extraction.py pre-flight) | D-62-08: reuse `extraction.py` + `wf_contact_ingest_cloud`, the ONE implementation of the association rule (CLAUDE.md §13.0.1) |
| Cost disclosure and grant | Client (operator-claude-plugin `write_grant.py`) | — | D-62-11: one session-grant envelope, not a new lane |
| Per-field provenance stamping | API/Backend (n8n `Merge Contacts` node -> `lv_contact_enrichment_provenance`) | — | D-62-17: existing Phase 15 mechanism, `source` override needed |

## Package Legitimacy Audit

Not applicable — this phase installs no new external packages. Every dependency (Lusha API,
`extraction.py`, `write_grant.py`, `mergeContacts.js`) already exists in the codebase.

---

## Research Priority 1 — Does Lusha `/v3/contacts/search-and-enrich` support a title/role filter?

**Verdict: NO. `[VERIFIED: docs/LUSHA-V3-CONTRACT.md §3, live-probed 2026-07-30 and 2026-08-30]`**

The contract of record for this endpoint — every claim in it confirmed against a live
`api.lusha.com` response, not inferred — enumerates the **complete, closed** set of accepted
identity properties for the contacts lane's request body:

> `firstName`, `lastName`, `companyName`, `companyDomain`, `email`, `linkedinUrl` — and nothing
> else. An unrecognised property 400s outright: `contacts.0.property notARealProperty should not
> exist` (§3, "Every attempted property, accepted or rejected" table). The synthetic v2-style
> `contactId` index key is also rejected the same way.

No `title`/`jobTitle`/`role` key was ever probed and accepted. This is an **absence**, not a
tested-and-refused parameter — per the provenance rules, that keeps the specific claim "there is
no title parameter" one notch short of `[VERIFIED]` on its own. Three converging lines of evidence
close the gap to a practical certainty, but the fully rigorous confirmation needs one more probe
(named below, not run — this research is read-only):

1. **`[VERIFIED]` The response shape is 1:1, not 1:many.** §4 of the contract: "v3 is a flat
   `results` array, positionally aligned with the request's `contacts` array (single-item in this
   waterfall's usage pattern...)." One identity object in, at most one result out. A company+role
   discovery call structurally needs the opposite shape — one company in, N candidate people out —
   which this endpoint's own documented response contract cannot produce regardless of what
   request fields it accepted.
2. **`[CITED: docs/LUSHA-V3-CONTRACT.md; 20-RESEARCH.md Pitfall 1]`** This project's own prior
   research (Phase 20, the v3 migration) already named and rejected exactly this conflation:
   *"Conflating the Enrichment API with the Prospecting API... `POST /prospecting/contact/enrich`
   ...LOOKS structurally similar and shares vocabulary (`reveal`, `canReveal`, `contactId`) with
   the Enrichment API, but is a CLAUDE.md-declared **out-of-scope** surface."* The standing
   `.planning/workstreams/milestone/REQUIREMENTS.md` § Out of Scope entry: *"Lusha Prospecting /
   Lookalikes / Tables / Decision Makers APIs — net-new acquisition surfaces, not enrichment of
   existing CRM records."*
3. **`[CITED: WebSearch, docs.lusha.com]`** Lusha's own public documentation places job
   title/seniority/department filtering under a distinct **Prospecting API** product
   (`docs.lusha.com/apis/openapi/prospecting-search-and-enrich`, with its own `Search Contacts`
   sub-page), while the **Contact Search and Enrich** page (`docs.lusha.com/apis/openapi/contact-search-and-enrich`
   — the endpoint this repo actually calls) is described as resolving "identifiers like email,
   LinkedIn URL, name, company name, or domain" — an identity-resolution description, not a filter
   description. (`docs.lusha.com` is a JS-rendered SPA that WebFetch could not render byte-exact;
   this is WebSearch-snippet corroboration, not a fetched page — hence `[CITED]`, not `[VERIFIED]`,
   consistent with how `LUSHA-V3-CONTRACT.md` itself treats WebSearch-only findings.)

**The falsification step that would make this fully `[VERIFIED]`, named for whoever runs the next
live probe (not run in this session — read-only research):** extend
`scripts/probe_lusha_v3.py`'s P9 idiom (a probe that costs 0 credits because a 400/`NOT_FOUND`
never bills) with two more shapes:
- `{"contacts":[{"companyName":"X","companyDomain":"x.example","jobTitle":"CEO"}]}` — expect a 400
  `property jobTitle should not exist`, which would close this to `[VERIFIED]`. A 200 would be the
  refutation this whole finding rests on not having happened.
- `{"contacts":[{"companyName":"X","companyDomain":"x.example"}]}` (company identity only, no
  person name) — never probed either. Expect either a 400 (company-only is not a valid contact
  identity) or a 200 with `resultsReturned: 1` for a SPECIFIC arbitrary match (confirming 1:1, not
  bulk) rather than a list.

**Consequence for D-62-01/D-62-02:** both decisions assume this endpoint "can take company + title
and return people." It cannot take a title at all, and even company-only would return at most one
arbitrarily-matched result, not a candidate list. D-62-01's own reversibility note calls itself
"reversible — a second adapter is additive," but the deeper problem isn't "which adapter" — it's
that **no currently-in-scope adapter can discover an unnamed person by role**, because the one
provider explicitly scoped for this phase does not offer that capability at all, and the provider
line that does (Prospecting) is explicitly out of scope by a decision this phase does not have
authority to reverse on its own (see § Open Questions for the two ways forward).

---

## Research Priority 2 — Credit behaviour when a search returns fewer people than the cap

**Verdict: for the endpoint actually wired, this question is largely moot — but the underlying
billing facts are answered and still needed for D-62-14's estimate wording, and the real open
question moves to the Prospecting API's unknown pricing.**

`[VERIFIED: docs/LUSHA-V3-CONTRACT.md §4, §9]` The contacts `search-and-enrich` endpoint bills
**per request item, not per field revealed, and not on a miss**:

- A match: `billing.creditsCharged: 1` (first-time identity), `0` for a stored-`id` re-enrich
  (§8, 4/4 live calls confirmed free).
- A miss: `billing: {"creditsCharged": 0, "resultsReturned": 0}` inside a `200` — "Every-item error,
  outer 200" — a `results[i].error.code: "NOT_FOUND"` per §9, not a request-level failure and not
  billed.
- Selective `reveal[]` field count does not change the charge (§6, A3 REFUTED) — cost is driven by
  identity-search-vs-stored-id, never by which fields are asked for.

Because this endpoint is called **once per known identity, never once per (company, cap)**, there
is no "search returns fewer than the cap" case to measure for it — you cannot ask it for "up to 3
people at company X"; you can only ask it to resolve a specific person you already named. D-62-14's
"worst case = companies × per-company cap" framing is the right *direction* (over-state, never
under-state, matching the `write_grant` envelope's measured behaviour: a real 2-record chunk
projected 3 executions, never fewer) — but the number it should be pricing is presently unclear,
because it depends entirely on which discovery mechanism the operator picks under § Open
Questions.

**If the operator reopens the Prospecting API decision** (Priority 1's option a): that endpoint's
billing model is **`[ASSUMED]` — genuinely unprobed by this repo.** Lusha's public docs distinguish
"search" credits (returning a preview list) from "reveal" credits (unlocking a specific person's
contact fields) for that product line, structurally similar to but not necessarily priced like the
Enrichment API's two-step flow measured in §7 of the contract. This would need its own live-probe
session (mirroring `probe_lusha_v3.py`'s pattern) before any per-company cap could be priced with
the same confidence D-62-14 currently claims for the wrong endpoint.

## Research Priority 3 — Can `extraction.py` accept synthesised rows without loosening identity?

**Verdict: YES, cleanly. `[VERIFIED: operator-claude-plugin/scripts/extraction.py, read this session]`**

The file-based `__main__` CLI (`load_artifact(path)` -> `validate(artifact)`) is a thin
convenience wrapper, not the module's real contract. `validate(artifact: dict, mapping_path=None)`
operates on a plain in-memory Python dict — `operator-claude-plugin/scripts/preingest.py` already
imports and calls sibling `extraction` functions directly as a library (`extraction.hold_emailless`,
`extraction.canonical_props()`), confirming this is the module's normal consumption pattern, not
just a CLI. A Phase 62 caller can build `{"records": [...]}` in memory from Lusha's response and
call `extraction.validate()` directly — no file upload is structurally required.

**Exact shape each synthesised record must carry**, confirmed by reading `validate()`'s per-record
pre-flight (`operator-claude-plugin/scripts/extraction.py:560-602`):

```json
{
  "record_type": "contacts",
  "row": {
    "firstname": "...", "lastname": "...", "company": "...",
    "jobtitle": "...", "email": "...", "linkedin_url": "..."
  },
  "provenance": {"input": "lusha_search_and_enrich", "locator": "<company id or domain>"}
}
```

- `record_type` is optional, defaults to `"contacts"` — correct for this phase, no explicit value
  needed.
- `row` keys must be in the **canonical prop set** (`extraction.canonical_props()`, derived from
  `config/column_mapping.yaml`'s `aliases` values: `email`, `firstname`, `lastname`, `jobtitle`,
  `linkedin_url`, `phone`, `company`, `company_id`) — anything else is stripped and reported in
  `dropped_keys`, never silently kept.
- `provenance.input` and `provenance.locator` must both be non-blank or the whole record rejects
  with `"record has no provenance, or provenance is missing which input or which span/locator
  produced it"` (line 597) — a suggested row needs SOME locator string; `"lusha:<company_id>"` is a
  reasonable literal.
- `resolutions` (optional) is a **separate, narrower mechanism** — see the Pitfall below.

**Identity contract applies unchanged** — `[VERIFIED: config/column_mapping.yaml:60-64, read this
session]`:

```yaml
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
    - [linkedin_url]
```

D-62-09's "no special-casing for suggested rows" holds structurally: `has_identity()` is called on
the cleaned row with these same three groups regardless of where the row came from. A Lusha match
that returns only `firstName`+`lastName`+`company` (no email/LinkedIn) resolves via group 2 exactly
like a CSV row would; a match with `linkedinUrl` resolves via group 3 (the third identity group,
added Phase 61-03, per CLAUDE.md §13.0.2). A match returning only a job title and no name/email/
LinkedIn — plausible if Lusha's response schema ever supplies a title without personal identifiers,
though the contract's contacts response (§4) always includes `firstName`/`lastName` when it
matches at all — fails identity and routes to the standing weak-key `needs_review` path, same as
any other row.

### Pitfall: two provenance mechanisms, easy to conflate

`extraction.py`'s optional `resolutions` list is validated against a **closed vocabulary**
(`[VERIFIED: operator-claude-plugin/scripts/resolution_sources.py:26-31, read this session]`):

```python
RESOLUTION_SOURCES = frozenset({
    "hubspot_lookup",
    "operator_statement",
    "provider_result",
    "same_row_derivation",
})
```

`"lusha"` is not a member of this set — a `resolutions` entry naming `source: "lusha"` would be
**rejected outright** (`extraction.py:651-664`, `"...names source 'lusha', which is outside the
closed set..."`). This vocabulary answers a different question ("how was a missing IDENTITY field
resolved before the row reached extraction") from D-62-17's question ("what stamps the CRM's
per-field provenance after the row is written"). If Phase 62 needs to record `resolutions` at all
(it does not have to — the field is optional), the correct value is `"provider_result"`, never
`"lusha"`.

---

## The rest of the priorities, researched

### `write_grant.envelope()` / `plan_grant()` — carrying a suggestion allowance (D-62-11)

`[VERIFIED: operator-claude-plugin/scripts/write_grant.py, read this session]`

- `envelope(config, *, object_type, record_ids, record_domains, providers, transport, today,
  headroom)` at line 409 builds the GRANT-02 disclosure block. It already prices a record count ×
  provider set via `cost_guard.estimate_batch()` and folds in the sampled monthly execution
  ceiling. Adding a suggestion allowance means widening the figures this function assembles — e.g.
  treating "companies eligible for a suggestion round" as an additional weighted contributor to
  `record_count` or a sibling figure disclosed alongside it — not a new code path.
- **The CR-01 key-collision fix is confirmed exactly as CONTEXT.md describes** — read live at
  `write_grant.py:455-461`:
  > "CR-01 fix (Phase 60 review): this used to share the name `ceiling` with the sampled-allowance
  > verdict dict assigned below, so `figures["chunk_ceiling"]` ended up holding the verdict dict
  > instead of this int, and the GRANT-02 disclosure rendered a dict repr where a record count
  > belongs. Kept as its own name so the two meanings... can never collide again."

  Confirmed by grep: `figures["chunk_ceiling"]` is read as an int at line 579 (`"at most
  {figures['chunk_ceiling']} record(s)"`); `figures["ceiling"]` is read as the verdict dict at line
  1037 (`ceiling = figures["ceiling"]`). **Do not reuse either key name for a new suggestion
  figure** — pick a third name (e.g. `figures["suggestion_allowance"]`).
- `plan_grant()` (line 892) is the actual refusal/split-offer site — see next section.

### Phase 57's `CEILING_OVER` refusal + `_affordable_record_count()` split offer (D-62-13)

`[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1034-1080, read this session]`

`plan_grant()` already contains the complete mechanism: on `CEILING_OVER`, it calls
`split_for_allowance()` (line 1050), which internally calls `_affordable_record_count(total,
ceiling, remaining)` (line 746) — a linear scan (deliberately not a `while` loop, per this repo's
own AST guard forbidding `while` outside `watch.py`) that finds the largest N whose
`ceil(N/ceiling) + N` execution cost fits under the sampled remaining monthly allowance, pinned by
a monotonicity test (`test_affordable_record_count_cost_is_monotonic_over_a_range_of_n`). The
refusal text at line 1071 ("`{record_count}` record(s) would fit this run, with the
`{record_count - record_ceiling_per_run}` remainder...") is the exact split-offer language D-62-13
wants reused. **Nothing new to build here** — a suggestion round that pushes the batch over ceiling
gets the identical refusal-with-split-offer an enrichment batch gets today, provided the
suggestion allowance is folded into the SAME `record_count`/figures this function already prices
(see previous section) rather than tracked as a second parallel figure that this refusal logic
never sees.

### `scripts/inventory_org_type_values.py` — the read-only sampling idiom (D-62-05)

`[VERIFIED: scripts/inventory_org_type_values.py, read this session]`

The named pattern: `_has_credentials()` (checks `HUBSPOT_PRIVATE_APP_TOKEN`) skip-to-exit-0 ->
`_portal_ok()` (checks `HUBSPOT_PORTAL_ID` against a hardcoded `EXPECTED_PORTAL_ID` env-overridable
guard) -> paged `POST /crm/v3/objects/{object}/search` with an empty filter group and
`properties: [the one property]`, `limit: 100`, following `paging.next.after` -> per-value
classification against a known vocabulary. For `jobtitle` on **contacts** (not companies), the same
skeleton applies with `properties: ["jobtitle"]` against `crm/v3/objects/contacts/search` — the one
structural difference is the classification step: `inventory_org_type_values.py` classifies
against `src/taxonomy.py`'s static 9-key vocabulary (`classify_value()`), but `jobtitle` has no
equivalent static taxonomy to classify against — that's precisely what D-62-05's Haiku clustering
step replaces. **Recommendation, not deep research:** cache the cluster result as a committed
artifact rebuilt by a script invocation, mirroring `config/taxonomy.yaml`'s precedent (a
config file the code reads, not a runtime computation) — this satisfies D-62-05's "cached... not
re-clustered per run" requirement with a pattern this codebase already uses elsewhere.

### Per-field provenance stamping (D-62-17)

`[VERIFIED: n8n/code/mergeContacts.js:1-28, 174; scripts/build_cloud_workflows.py:275-293,
730, 766, 877, read this session]`

CLAUDE.md §6/§8's flat `{field}_source`/`{field}_confidence`/`{field}_evidence_url`/... properties
were **never built for contacts** — this is the same "documented but never created" pattern §4.0
already names for other properties. The actual, live mechanism is Phase 15's single JSON blob:

> "PROVENANCE MODEL (Phase 15): per-field metadata/staging is ONE provenance object keyed by field
> (`{source, confidence, verified_at, validation_status, value}`), not flat
> `{field}_source`/`{provider}_{field}` properties. The caller... serializes it ONCE via
> `stableStringify()` into `lv_contact_enrichment_provenance`..." (`mergeContacts.js:23-27`)

`mergeContacts(existing, candidate, cacheHint, opts)` accepts `opts.source` (line 174: `const
source = (opts && opts.source) || "csv";`) — this IS the reusable hook D-62-17 needs; it already
supports a caller-supplied source string, it is simply never called with one today. The one call
site that matters for this phase is the ingest lane's `MERGE_CONTACTS` n8n-wrapper code
(`scripts/build_cloud_workflows.py:275-293`), which hardcodes:

```js
const merged = mergeContacts({}, candidate, undefined, { source: "csv", confidence: 80 });
```

This exact string constant (`MERGE_CONTACTS`) is registered as the `"Merge Contacts"` node in
**both** `build_local()` (line 730, the offline dry-run template) and `build_cloud()` (line 766
defines the function, line 877 registers the node) — `build_cloud()` is what emits the deployed
`wf_contact_ingest_cloud.json`. **The change D-62-17 needs is narrow and confined to this one
constant:** derive `source` from a value the row itself carries (e.g. a `row.origin` field the
suggestion-synthesiser sets to `"lusha"`, read here instead of the hardcoded literal) rather than
always defaulting to `"csv"`. Both `build_local()` and `build_cloud()` pick up the change
automatically since they share the one constant — consistent with this codebase's "one
implementation" pattern (CLAUDE.md §13.0.1) and this phase's own D-62-08 reasoning.

**`confidence: 80`** is also hardcoded in the same call and would need the same treatment if a
suggested row's confidence should differ from a CSV upload's assumed 80 — not required by any
D-62 decision, flagged for the planner's awareness only.

### "Batch just completed" hook (D-62-15)

`[CITED: operator-claude-plugin/scripts/run_state.py:89, read this session]` — There is no
n8n-side "batch complete" webhook or workflow event; the architecture is async-submit-and-poll
(CLAUDE.md §13.0.2's `async_ack`), so completion is a **client-side** fact, not a backend one.
`run_state.py` derives a `done` status per row from verdicts in `{MATCHED, ENRICHED}`; a batch is
"complete" when every row in the client's manifest reaches one of those terminal verdicts. The
natural hook for D-62-15's unprompted offer is therefore **in the conversational skill layer**
(`operator-claude-plugin/skills/contact-upload/`, `enrich-records/`, or wherever the plugin already
polls run-state to completion) — after the poll loop observes all rows `done`, before ending that
turn, raise the suggestion offer. This is a skill/prompt-flow change, not a new backend mechanism.

### "Zero associated contacts" check (D-62-16)

Not independently probed live this session (read-only constraint). `[ASSUMED — standard HubSpot
CRM v4 associations read, mirrors a write path this repo already uses live.]` CLAUDE.md §13.0.1
confirms the live WRITE path: `PUT /crm/v4/objects/contacts/{id}/associations/default/companies/{id}`.
The read-only mirror in the same API family, `GET
/crm/v4/objects/companies/{company_id}/associations/contacts`, is the standard way to enumerate a
company's associated contacts and would return an empty `results` array for "nobody named." This
needs one read per company in the batch (or a single batch-associations read if HubSpot's v4 API
offers one — not confirmed this session). Flagged for a `checkpoint:human-verify` or a cheap
disarmed live probe before the plan locks this as the mechanism, since it was not independently
confirmed against `api.hubapi.com` in this research pass.

---

## Common Pitfalls

### Pitfall 1: Treating "search" in the endpoint's name as evidence it searches
**What goes wrong:** `POST /v3/contacts/search-and-enrich` reads as a search endpoint from its
name alone, and D-62-01's own text calls it "the discovery provider." The verb in the endpoint
name describes Lusha's own internal two-step process (search their database, then enrich the
match) collapsed into one call — not a capability to search FOR someone you cannot name.
**Why it happens:** the name is genuinely misleading relative to what CLAUDE.md/this repo means by
"discovery" (finding people you don't know exist).
**How to avoid:** read the request/response contract's identity-object shape, not the endpoint
name, before assuming a capability. Priority 1 above is written to make this check reusable.
**Warning signs:** a design that assumes a company-only or role-only request body against this
endpoint.

### Pitfall 2: Conflating `extraction.py`'s two provenance mechanisms
Covered in full under Priority 3 above. `resolutions.source` (closed vocab: `hubspot_lookup`,
`operator_statement`, `provider_result`, `same_row_derivation`) is not the same field as
`mergeContacts.js`'s `opts.source` (free string, feeds `lv_contact_enrichment_provenance`). A
planner reaching for "stamp source=lusha" needs the SECOND mechanism, and must not add `"lusha"`
to the first vocabulary to make it fit.

### Pitfall 3: Assuming CLAUDE.md §6/§8's flat provenance properties exist
They don't, for contacts, per Phase 15's own comment in `mergeContacts.js`. Writing a plan task
that PATCHes `jobtitle_enriched_source` etc. would silently write to a property HubSpot has never
had defined (same failure class as §4.0's `enrichment_requested` vs `lv_enrichment_requested`) —
use `lv_contact_enrichment_provenance` instead.

### Pitfall 4: Pricing the suggestion round against the wrong endpoint's economics
D-62-12/14's "per-company cap" and "companies × cap" ceiling framing was written assuming a
search-shaped call. Whatever mechanism the operator picks under § Open Questions, re-derive the
ceiling formula against THAT mechanism's actual request/response shape (1:1 vs 1:N) before reusing
D-62-14's arithmetic verbatim.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Lusha's Enrichment API request body has no `jobTitle`/`title`/`role` parameter — inferred from a closed, live-confirmed allow-list that never included it, not from a direct probe of that specific key. | Priority 1 | Low — three converging lines of evidence (1:1 response shape, this project's own Phase 20 pitfall writeup, Lusha's own docs placing role filters under a different product) all point the same way; the named falsification probe would close this to `[VERIFIED]` at zero credit cost. |
| A2 | Lusha's Prospecting API billing model (search credits vs. reveal credits, per-result cost) is unknown to this repo. | Priority 2 | Medium — if the operator reopens the Prospecting decision (§ Open Questions option a), D-62-14's cost-ceiling formula cannot be trusted until this is live-probed; a plan that reuses D-62-14's arithmetic for the Prospecting API without re-probing could under-price the round. |
| A3 | `GET /crm/v4/objects/companies/{id}/associations/contacts` is the correct read-only mirror of the write path CLAUDE.md §13.0.1 confirms live; not independently probed this session. | D-62-16 / "the rest of the priorities" | Low-Medium — a wrong endpoint name would surface immediately as a 404 in a disarmed dry run, before any write risk; still worth a `checkpoint:human-verify` before locking it into a task. |
| A4 | A company-only Lusha identity body (`companyName`+`companyDomain`, no person name) either 400s or returns exactly one arbitrarily-matched result — inferred from the 1:1 response-array-alignment description, never directly probed. | Priority 1 | Low — feeds the same falsification probe named in Priority 1; matters only if someone considers "company-only search" as a workaround, which this document already argues against on response-shape grounds alone. |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Which discovery mechanism does Phase 62 actually build against?**
   - What we know: the endpoint named in D-62-01 (`/v3/contacts/search-and-enrich`) cannot do
     company+role discovery, per Priority 1's evidence. No other provider is in scope for this
     phase (Apollo/ZoomInfo discovery deferred by D-62-01 itself; a second discovery provider is
     explicitly out of scope per CONTEXT.md's Phase Boundary).
   - What's unclear: whether the operator wants to (a) reopen the standing "Lusha Prospecting API
     is out of scope" project-level decision — D-62-01 marks itself reversible, but this is a
     decision above this phase's own authority, made in `.planning/workstreams/milestone/REQUIREMENTS.md`,
     not in this phase's CONTEXT.md — which would require its own live-probe session for request
     shape and billing before any plan could price it; or (b) re-scope Phase 62's discovery
     mechanism entirely (e.g. a HubSpot-internal search for contacts who exist somewhere in the
     portal but are not yet associated with the target company — a different, cheaper, but
     narrower capability than "genuinely new people").
   - Recommendation: return this finding to the operator (checkpoint or `/gsd-discuss-phase`
     re-entry) before planning proceeds. Do not let the planner choose silently between (a) and
     (b) — this is exactly the kind of reversal D-62-07 modelled for SUGGEST-03 (an explicit,
     disclosed operator decision, not a planner inference).

2. **Does the v4 associations API support a batched "which of these N companies have zero
   contacts" read, or does it require N individual calls?**
   - What we know: the per-company GET exists and is the standard mechanism (A3 above).
   - What's unclear: whether HubSpot's batch associations read (`POST
     /crm/v4/associations/{fromObjectType}/{toObjectType}/batch/read`) is more efficient for a
     300-company batch than 300 individual GETs — relevant to D-62-11's cost/execution accounting
     if this read happens inside an n8n Cloud execution (counts toward the 2.5K/month budget) vs.
     client-side (does not).
   - Recommendation: a one-line probe question for whoever plans the task, not deep research —
     name both options in the plan and let the plan-checker or the operator pick based on the
     batch-size economics at plan time.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (Python) | pytest |
| Framework (n8n JS) | Node's built-in `node:test` |
| Config file | none dedicated — `pytest.ini`/`pyproject.toml` at repo root; n8n JS tests are plain `.test.mjs` files under `tests/n8n/` |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py operator-claude-plugin/tests/test_write_grant.py -x` |
| Full suite command | `.venv/bin/python -m pytest && node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24, per project memory `test-suite-run-commands.md`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUGGEST-01 | Round offered after batch completes | integration (client-side skill flow) | none yet — depends on which skill hosts the offer | ❌ Wave 0 |
| SUGGEST-02 | Roles chosen once, applied across batch | unit | new test alongside role-vocabulary module | ❌ Wave 0 |
| SUGGEST-03 (amended) | Role vocabulary derived from live `jobtitle`, with disclosed generic fallback | unit + a disarmed live-inventory dry run (mirrors `inventory_org_type_values.py`'s own pattern — no committed automated test for a live HubSpot read) | `.venv/bin/python -m pytest <new role-vocab test file>` | ❌ Wave 0 |
| SUGGEST-04 | Suggestions proposed, never auto-created | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py` (existing identity/hold-row contract, reused not modified) | ✅ exists |
| SUGGEST-05 | Cost shown before spent | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_surface.py` | ✅ exists |
| D-62-17 | `source=lusha` provenance stamped | unit (n8n) | `node --test tests/n8n/mergeContacts.test.mjs` — needs a new case for a non-`"csv"` source once `MERGE_CONTACTS`'s hardcode is parameterised | ✅ file exists, ❌ new case |

### Sampling Rate
- **Per task commit:** the quick run command above (scoped to the files the task touched).
- **Per wave merge:** the full suite command above.
- **Phase gate:** full suite green before `/gsd-verify-work`, plus the disarmed-dry-run discipline
  every prior phase in this repo has used for any n8n redeploy (never arm/deploy inside research or
  planning).

### Wave 0 Gaps
- [ ] A test file for the role-vocabulary clustering module (covers SUGGEST-02/SUGGEST-03) — does
      not exist yet; no clustering module exists yet either.
- [ ] A test case in `tests/n8n/mergeContacts.test.mjs` (or a new file) asserting `MERGE_CONTACTS`'s
      n8n-wrapper reads `source` from the row rather than hardcoding `"csv"`, once that change
      lands (D-62-17).
- [ ] An offline oracle test for the synthesised-row shape entering `extraction.validate()` directly
      (bypassing `load_artifact`) — `operator-claude-plugin/tests/test_extraction_contract.py`
      already exercises `validate()` on hand-built dicts, so this is very likely additive test
      cases in that existing file, not a new file.
- [ ] No test scaffolding needed for the discovery-provider question until § Open Questions #1 is
      resolved — do not build tests against a mechanism that has not been chosen.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Lusha `api_key` header auth already established; no new auth surface |
| V3 Session Management | no | n/a — this phase adds no session concept beyond the existing write-grant session |
| V4 Access Control | yes | The existing write-grant / arming gates (`ALLOW_HUBSPOT_CREATE`, `n8n_arming`) already gate any write this phase's proposals could produce — D-62-10's "no per-record confirmation" relies on the ingest lane's EXISTING held/needs_review gates, not a new access-control surface |
| V5 Input Validation | yes | `extraction.py`'s canonical-prop allowlist + identity-group check (already reused, not built new) |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A synthesised row smuggling a non-canonical key onto a HubSpot write | Tampering | `extraction.py`'s existing `dropped_keys` strip (STRUCT-01, already enforced, reused not rebuilt) |
| A synthesised row bypassing the email gate to reach a silent no-write | Tampering / DoS-on-data-quality | `hold_emailless()`, already enforced |
| Cost blowout from an unbounded suggestion round | Denial of Service (budget) | D-62-12's operator-set per-company cap + D-62-11's folding into the existing session-grant ceiling machinery (`plan_grant`/`CEILING_OVER`), both already researched above as reusable, not new |
| PII in a suggested-row provenance/log trail | Information Disclosure | Follow the same PII-redaction discipline `docs/LUSHA-V3-CONTRACT.md`'s own redaction note establishes (threat T-20-03) for any new fixture or log this phase's tests add |

## Sources

### Primary (HIGH confidence)
- `docs/LUSHA-V3-CONTRACT.md` — live-probed 2026-07-30 / 2026-08-30 contract of record for the
  Lusha v3 Enrichment API (contacts and companies lanes, billing model, error shapes).
- `n8n/code/lushaRequest.js` — the current request-body builders, read this session.
- `operator-claude-plugin/scripts/extraction.py` — read this session, lines 117-950 covering
  `ExtractionResult`, `identity_groups`, `has_identity`, `validate()`'s per-record pre-flight,
  `hold_emailless`, `write_dispatch_csv`, and the `__main__` CLI wrapper.
- `config/column_mapping.yaml` — read this session, `aliases` and `required_identity.any_of`.
- `operator-claude-plugin/scripts/resolution_sources.py` — read this session, `RESOLUTION_SOURCES`.
- `n8n/code/mergeContacts.js` — read this session, lines 1-100+174, the Phase 15 provenance model
  and `opts.source` hook.
- `scripts/build_cloud_workflows.py` — read this session, `MERGE_CONTACTS` constant (lines
  275-293) and its two registration sites (`build_local()` line 730, `build_cloud()` lines
  766/877).
- `operator-claude-plugin/scripts/write_grant.py` — read this session, `envelope()` (409),
  `plan_grant()` (892), `_affordable_record_count()` (746), the CR-01 comment (455-461) and its
  confirmed key usage (579, 1037).
- `scripts/inventory_org_type_values.py` — read this session, the full read-only inventory idiom.
- `operator-claude-plugin/scripts/run_state.py` — read this session, the `done`/verdict status
  model (line 89).

### Secondary (MEDIUM confidence)
- `.planning/workstreams/milestone/phases/20-lusha-v3-migration/20-RESEARCH.md` — Pitfall 1
  (Enrichment vs. Prospecting API conflation), read this session.
- `.planning/workstreams/milestone/REQUIREMENTS.md` § Out of Scope — the standing Prospecting-API
  exclusion, read this session.
- WebSearch results for `docs.lusha.com`'s Contact Search and Enrich vs. Prospecting Search and
  Enrich product pages — corroborating but not independently fetched (the docs site is a
  JS-rendered SPA; WebFetch could not render it, matching `LUSHA-V3-CONTRACT.md`'s own note about
  this limitation).

### Tertiary (LOW confidence)
- A4/A3 in the Assumptions Log (company-only Lusha identity behaviour; the exact v4 associations
  read endpoint) — inferred from adjacent live-confirmed evidence, not independently probed this
  session.

## Metadata

**Confidence breakdown:**
- Provider-capability finding (Priority 1): HIGH — convergent, tool-confirmed, multi-source
  evidence; the one gap (a direct `jobTitle` probe) is named as a zero-cost falsification step for
  whoever runs the next live session.
- Ingest-lane reuse contract (Priority 3, D-62-08/09): HIGH — read directly from source this
  session, including the exact record shape and rejection messages.
- Grant/ceiling reuse (D-62-11/12/13/14): HIGH for the mechanism; MEDIUM for the actual cost
  numbers, since those numbers depend on which discovery mechanism gets chosen (Open Question 1).
- Provenance mechanism (D-62-17): HIGH — read directly from source, including the exact call site
  needing a change.
- Role-vocabulary sampling idiom (D-62-05): HIGH for the pattern; the Haiku-clustering step itself
  is new work with no precedent to verify against.

**Research date:** 2026-09-02
**Valid until:** 14 days — this research is gated on an operator decision (Open Question 1); once
that decision lands, the Lusha billing/shape facts above should be re-checked against whichever
endpoint is actually chosen, since Priority 2's answer is currently "moot for the wrong endpoint,
unknown for the right one."
