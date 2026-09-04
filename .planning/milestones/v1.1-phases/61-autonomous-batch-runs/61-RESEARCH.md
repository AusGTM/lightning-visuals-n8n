# Phase 61: Resolve the identity, don't ask for it - Research

**Researched:** 2026-08-30
**Domain:** operator-claude-plugin extraction/ingest contract + n8n Cloud match/enrichment lanes
**Confidence:** HIGH on what exists in code today (all claims read this session); MEDIUM on the
exact shape of the fix, because the backend gap found in Q3 is materially wider than D-61-05's
"front-end only" framing assumed.

## Summary

The blocking rule from the failed walk lives in at least **five** independent places, not one
(Q1). Three are real code gates (Python, two separate JS reimplementations); two are prose. All
five currently define "identity" as `email` OR `firstname+lastname+company` and none of them
treat `linkedin_url` as its own satisfying group, even though `linkedin_url` is already a
canonical prop everywhere.

The bigger finding is in Q3. D-61-05's claim that "no new backend capability is required" holds
for **Lusha enrichment** (confirmed) but does **not** hold for **HubSpot matching**. Tracing the
actual match path used by the plugin (`preingest.match_batch` -> the enrichment webhook's
`Build Identity` -> `matchProposal.js`'s `laneOf()`), a `linkedin_url`-only row is routed to lane
`"none"` -> tier `"unknown"` ("no searchable identity") -- **no HubSpot search by `linkedin_url`
runs anywhere in the deployed n8n Cloud workflow**, in either the bulk-CSV ingest lane or the
enrichment/match lane. `resolveIdentity.js:76-90`'s linkedin branch, cited in D-61-05 as existing
evidence, is real code but is **unreachable in the deployed Cloud workflow** because nothing
upstream ever populates `searchResultsByKey.linkedin_url` for it to read. Separately,
`enrichment.py`'s client-side envelope builder explicitly **strips `linkedin_url`** before a
"rows" (match/enrich) request ever leaves the plugin (`MATCH_LOOKUP_KEYS`, line 71). This is a
genuine, additional piece of work the plan needs to scope, not just a contract-prose fix.

The D-59-08 resolvable/`resolutions` mechanism (Q4) is a very good fit for reuse: its
`provider_result` source already exists in the closed vocabulary for exactly "a value the
enrichment waterfall already returned for this row," and its `resolutions` validation runs
independently of the identity pre-flight (it applies to any accepted row), so it generalises
cleanly to "propose fields the waterfall found for an already-identified linkedin-only row." No
second proposal surface is needed.

**Primary recommendation:** treat this as two changes, both required, both scoped by strong-key
D-61-03: (1) a front-end contract change (add `[linkedin_url]` as its own identity group in the
three places that gate on it, and reuse D-59-08's `resolutions`/`provider_result` path for
proposing waterfall-found fields), and (2) a small, additive backend change (a `linkedin` lane in
`matchProposal.js`'s `laneOf()`, a HubSpot search-by-`lv_linkedin_url` node in whichever workflow
performs the match, and un-stripping `linkedin_url` from `enrichment.py`'s `MATCH_LOOKUP_KEYS`)
so that "match" is genuinely possible before "enrich" ever runs. Doing only (1) reproduces the
walk failure in a new shape: the row would pass extraction, then dead-end forever in the
`unchecked` bucket at the match step, since nothing there knows how to search HubSpot by
`linkedin_url` today.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Identity pre-flight (row has enough to act on) | Plugin (Python, `extraction.py`) | Plugin prose (`extraction.md`) | Client-side gate before anything reaches n8n; prose instructs the extractor (Claude) what to write |
| Column mapping / identity gate on bulk CSV ingest | n8n Cloud (`Map Columns` node, `columnMap.js`) | Plugin config (`column_mapping.yaml`) | The n8n node is the real deployed gate for the CSV-webhook path; YAML is the plugin's own mirror/preview copy |
| HubSpot match (does this contact already exist) | n8n Cloud (`Build Identity`/`matchProposal.js`/HubSpot Search nodes) | Plugin (`preingest.match_batch`) reads the result | HubSpot's own search API is the source of truth; the plugin only sends the lookup and classifies the response |
| Provider enrichment (Lusha/Apollo/ZoomInfo) | n8n Cloud (`ENRICH_GATE` + provider HTTP nodes) | Plugin (envelope builder) decides what crosses the boundary | Credit-spending calls are server-side; the plugin controls only what identity keys are sent |
| Operator proposal/consent surface | Plugin (Claude in-session, per SKILL.md) | — | No proposal is ever written without an operator yes; this is entirely client-side |

## Q1 - Where the blocking rule actually lives

Five sites, of two real kinds (code gate vs. prose), all currently expressing the same
`email` OR `firstname+lastname+company` rule and none of them recognising `[linkedin_url]` as its
own group.

### Code gates (enforced, not just documented)

1. **`config/column_mapping.yaml:54-57`** and its byte-identical mirror
   **`operator-claude-plugin/config/column_mapping.yaml:54-57`** (confirmed identical via `diff`,
   this session):
   ```yaml
   required_identity:
     any_of:
       - [email]
       - [firstname, lastname, company]
   ```
   This is **data**, consumed by two independent Python readers (below) and never
   auto-synced with the n8n JS reimplementation (#3).

2. **`operator-claude-plugin/scripts/extraction.py:170-192`** — `identity_groups()` reads
   `required_identity.any_of` verbatim from the YAML above; `has_identity()` (line 187) is the
   actual gate: `any(all(_present(row.get(key)) for key in group) for group in groups)`. This is
   the real Python code path `contact-upload`/`enrich-before-ingest` both run every extracted
   record through (`validate()`, line 462, calls `has_identity` at line 638).

3. **`operator-claude-plugin/scripts/extraction.py:638-680`** — on rejection, the reason string
   is **hard-coded prose**, not derived from `identity_groups()`:
   ```python
   reason = (
       "no identity present: needs a non-blank 'email', or all "
       "three of 'firstname'/'lastname'/'company' non-blank"
   )
   ```
   Adding a YAML group does **not** automatically fix this message — it must be edited by hand
   or rewritten to enumerate `record_groups` generically.

4. **`n8n/code/columnMap.js:78-84`** — a **third, independent, hand-written** reimplementation,
   not derived from the YAML at all:
   ```js
   function requiredIdentity(row) {
     if (!row) return false;
     if (_present(row.email)) return true;
     return _present(row.firstname) && _present(row.lastname) && _present(row.company);
   }
   ```
   This is inlined verbatim into the **deployed** n8n Cloud `Map Columns` node by
   `scripts/build_cloud_workflows.py:98-116` (`MAP_COLUMNS`), and is the gate that actually runs
   on the bulk-CSV contact-ingest webhook (`wf_contact_ingest_cloud`), before `Resolve Identity`
   ever executes:
   ```python
   const ok = requiredIdentity(mapped);
   ...
   reject: !ok,
   ...(ok ? {} : { outcome: "rejected",
     reject_reason: "missing required identity (need email OR firstname+lastname+company)" })
   ```
   Node order confirmed at `scripts/build_cloud_workflows.py:942-948`: `"Map Columns"` runs
   before `"HubSpot Search by Email"` / `"Resolve Identity"`. **This means
   `resolveIdentity.js`'s strong-key `linkedin_url` branch (lines 76-90) can never even be
   reached for a `linkedin_url`-only row on the bulk-CSV path — `Map Columns` rejects it first.**

5. **`operator-claude-plugin/tests/test_identity_preflight.py`** currently pins the rejection
   behaviour loosely enough (`assert "identity" in reason`) that it should not need to change,
   but see Q7 for the specific tests that assert exact strings/lists.

6. **`src/file_loader.py:81-118`** — the local Python "oracle" ingest path (`_has_identity`,
   `ingest_file`) reads the **same** repo-root `config/column_mapping.yaml`, so a YAML-only fix
   automatically reaches this fourth reader; it does **not** reach `columnMap.js` (#4), which is
   hand-written and would silently drift if only the YAML is edited.

### Prose (model-followed instruction, no code enforcement)

7. **`operator-claude-plugin/skills/contact-upload/extraction.md:27-28`**:
   > "Never fill a gap to make a row satisfy the identity rule (a non-blank `email`, or all
   > three of `firstname`/`lastname`/`company`)."

   This is the sentence the walk-failure model actually followed. It states the two-group rule
   verbatim and gives no third (`linkedin_url`) option. The **no-invention** rule this sentence
   sits inside (D-61-02, do-not-simplify) is a different, orthogonal sentence a few lines up
   (lines 22-26) and is untouched by adding a group here — the group list and the no-invention
   rule are independently editable.

**Net effect:** fixing only `extraction.md` (prose) fixes nothing structurally — Python's
`has_identity()` and the n8n `Map Columns` node still reject the row. Fixing only the YAML fixes
`extraction.py` and `src/file_loader.py` but not `columnMap.js` (bulk CSV path) or the prose
(which a model reads and could still refuse the row against on its own initiative). **All of
1/2/4/7 need to change together**, and 3 needs a hand-edit since it is not YAML-derived.

## Q2 - What the identity contract currently is, exactly

Quoted from `config/column_mapping.yaml:8-57` (identical in
`operator-claude-plugin/config/column_mapping.yaml`):

```yaml
aliases:
  linkedin_url: linkedin_url
  linkedin: linkedin_url
  "linkedin url": linkedin_url
  li: linkedin_url
  "linkedin profile": linkedin_url
  ...
required_identity:
  any_of:
    - [email]
    - [firstname, lastname, company]
```

`linkedin_url` **is** a first-class canonical prop (`extraction.md:160`: "company, email,
firstname, jobtitle, lastname, linkedin_url, phone" — 7 total) and **is** in the alias table
(`columnMap.js:29-33` mirrors the same 5 aliases byte-for-byte, pinned equal by
`tests/n8n/columnMapAliasParity.test.mjs:32-39`, which pins `ALIASES` only — it does **not** pin
`requiredIdentity`/`identity_groups()` parity, so there is currently no test that would catch the
YAML and `columnMap.js`'s identity-group logic drifting from each other). It is simply not one of
the two `required_identity.any_of` groups.

**Does it survive end to end to a HubSpot write?** Yes, on the bulk-CSV ingest lane, once past
`Map Columns`: `n8n/code/mergeContacts.js`, inlined as `MERGE_CONTACTS`
(`scripts/build_cloud_workflows.py:288-289`):
```js
if (row.linkedin_url != null && String(row.linkedin_url).trim() !== "") {
  candidate.lv_linkedin_url = row.linkedin_url;
}
```
Comment at `scripts/build_cloud_workflows.py:278-279` (PN-1): "`linkedin_url` is NOT
HubSpot-native (absent from the verified-native list) -> the MERGE CANDIDATE / canonical field
key is `lv_linkedin_url`." So the **write** side already handles `linkedin_url` correctly and
writes it to HubSpot's `lv_linkedin_url` custom property — this part needs no change.

**Uncertainty worth flagging (not resolved this session):** `src/identity.py:65` — the local
Python oracle's own HubSpot search — filters on the **literal property name `"linkedin_url"`**,
not `lv_linkedin_url`:
```python
ids = _search_ids(hs_search, [{"propertyName": "linkedin_url", "operator": "EQ", "value": linkedin}])
```
If the live HubSpot portal only has `lv_linkedin_url` (per the PN-1 rename comment above) and no
plain `linkedin_url` property, this oracle search would silently return zero hits always. This is
`[ASSUMED]` risk, not verified against the live portal this session (no live calls were made,
per the hard constraints) — flag for whoever writes the new HubSpot-search-by-linkedin code:
**verify the correct live property name before filtering on it**, do not copy `src/identity.py`'s
filter key without checking.

## Q3 - Whether the enrich lane can already be driven with linkedin_url alone

**Split answer: enrichment yes (Lusha only); matching no (nowhere).**

### Provider enrichment (calling Lusha/Apollo/ZoomInfo)

- **Lusha: yes.** `n8n/code/lushaRequest.js:79-98` (`lushaContactBody`) accepts `linkedin_url`
  alone (`contact.linkedinUrl = id.linkedin_url`, line 83) and only returns the skip form
  (`{contacts: []}`) when the identity object is wholly empty (line 89). The comment at lines
  67-73 states the **Cloud emission site passes only `{email, linkedin_url}`** as the identity
  set for Lusha — i.e. this is exactly the live-confirmed, narrower set D-61-05 cites.
- **Apollo: no.** The deployed `Apollo Match` node body
  (`scripts/build_cloud_workflows.py:5000-5008`) builds its JSON body from
  `email, domain, first_name, last_name, organization_name, reveal_personal_emails` only —
  **no `linkedin_url` field is ever sent to Apollo's `people/match`**, regardless of what the
  Apollo API itself might accept.
- **ZoomInfo: no.** `_zoom_split_enrich_contacts_js`
  (`scripts/build_cloud_workflows.py:3905-3913`), `toMatchPersonInput()` builds
  `emailAddress, firstName, lastName, companyName` only, and `hasZoomKey()` requires
  `emailAddress || (firstName && lastName && companyName)` — **`linkedin_url` is never read at
  all**, so a linkedin-only row is skipped by ZoomInfo with `"no zoominfo match key"`.

**So: D-61-04's framing ("the waterfall, not web search") is accurate specifically because only
one of the three providers — Lusha — can act on a bare `linkedin_url`. Confirmed plainly, as the
research brief asked: only Lusha does.**

The gate that decides whether providers are called at all for a linkedin-only row,
`ENRICH_GATE`'s cost-control override (`scripts/build_cloud_workflows.py:1252`), already permits
it:
```js
if (!ik.email && !ik.linkedin_url && !(ik.lastName && ik.companyName)) action = "skip";
```
A row carrying `linkedin_url` alone does **not** hit this skip, so `Lusha Enrich` will be called.

### HubSpot matching (does the contact already exist)

This is where D-61-05's "no new backend capability" claim does not hold, traced two ways:

**(a) The bulk-CSV ingest lane** (`wf_contact_ingest_cloud`). Node chain confirmed at
`scripts/build_cloud_workflows.py:942-945`: `"Map Columns" -> "Normalize Phone" ->
"Build Verify Batch" -> "Verify Emails (batch)" -> "Apply Email" -> "HubSpot Search by Email" ->
"Adapt Search Results" -> "Resolve Identity" -> ...`. There is exactly **one** HubSpot search
node, `"HubSpot Search by Email"`, and `ADAPT_SEARCH_RESULTS`
(`scripts/build_cloud_workflows.py:199-252`) builds `searchResultsByKey` from it, populating
**only** `srk.email` (line 250: `if (rowEmail && hits.length) srk.email = hits;`). It never
builds `srk.linkedin_url`, `srk.phone_lastname`, or `srk.name_company`. So
`resolveIdentity.js`'s (lines 76-90) `linkedin_url` branch, and its `phone_lastname`/
`name_company` weak-key branches, are **all dead code on this deployed path** — every one of
them always sees zero candidate ids and falls through, ultimately landing on the hard safety
rule ("no email, insufficient identity" -> `ambiguous`, `resolveIdentity.js:107-109`). This
matches `extraction.py`'s own comment (`hold_emailless`, lines 808-813): "the deployed ingest
lane resolves a contact by email only" — that comment is **accurate and current**, not stale.

**(b) The enrichment/match lane** (`wf_enrichment_cloud`, hit by `preingest.match_batch` /
`fetch_matches` via `enrichment.enrichment_target(config)`). `ENRICH_BUILD_IDENTITY`
(`scripts/build_cloud_workflows.py:1196-1222`) builds `identity_keys.linkedin_url` from the row
(line 1205), but **routing** is decided by `matchProposal.js`'s `laneOf()`
(`n8n/code/matchProposal.js:30-42`), which checks only `objectId`, `email`, and
`lastName && companyName` — **`linkedin_url` is never read by `laneOf()` at all.** A
linkedin-only row lands in lane `"none"`. The single HubSpot search node in this workflow,
`"HubSpot Search"` (`scripts/build_cloud_workflows.py:4762-4770`), filters `email EQ` only. There
is no HubSpot-search-by-name-or-linkedin node in this contact branch either — the "name" lane
`laneOf()` defines has no backing HubSpot search node visible in this trace (a further
`[ASSUMED]`/unresolved point — not confirmed further this session, out of scope for D-61-03
anyway since name-only rows are explicitly fenced off). `summarizeMatch()`
(`n8n/code/matchProposal.js:119-146`) reports lane `"none"` as **tier `"unknown"`** ("no
searchable identity... the row has no email, object id, or name+company pair") — pinned by
`tests/n8n/matchProposal.test.mjs:276-281`.

**(c) The plugin's own client-side envelope, one layer above (b).**
`operator-claude-plugin/scripts/enrichment.py:66-71`:
```python
MATCH_LOOKUP_KEYS = ("email", "firstname", "lastname", "company")
```
Explicitly documented as **frozen** ("Widening this tuple widens what leaves the operator's
machine — a row's `phone`, `jobtitle` and `linkedin_url` never cross it"). This is consumed when
`build_envelope` constructs the `"rows"` form (the shape `preingest.match_batch`/`fetch_matches`
and `enrich-before-ingest` step 5's dispatch both send) — **`linkedin_url` is stripped from the
outbound match/enrich request before it ever leaves the operator's machine**, independent of
whatever the backend can or cannot do with it.

**Conclusion for Q3:** `resolveIdentity.js:76-78`'s linkedin_url strong-key logic is real, tested
in isolation (`n8n/tests` — need to verify a dedicated `resolveIdentity` test file; not located
this session, only `dedupeSweepWiring.test.mjs` was seen referencing it), but is **not wired to
any live HubSpot search** in either deployed workflow, and is additionally **blocked from ever
receiving the value** by the plugin's own `MATCH_LOOKUP_KEYS` filter one layer up. Fixing the
front-end identity-group gate (Q1) without also (i) un-freezing/widening `MATCH_LOOKUP_KEYS` to
include `linkedin_url`, (ii) adding a `linkedin` lane to `laneOf()`, and (iii) adding a HubSpot
search-by-`linkedin_url` (confirm the live property name first, see Q2) node to whichever
workflow actually performs the match, reproduces the walk failure in a new form: the row would
pass extraction, then permanently land in the `unchecked` bucket (`preingest.classify_matches`,
tier `"unknown"`) with no path forward — retry does not help, because the search that would
resolve it never runs.

## Q4 - D-59-08's existing resolvable-proposal mechanism

**Shape**, read from `operator-claude-plugin/scripts/extraction.py:62-114, 580-636, 657-680` and
`operator-claude-plugin/skills/contact-upload/extraction.md:31-68` +
`skills/contact-upload/SKILL.md:205-216`:

- A record that **fails** `has_identity()` is rejected as before, and **additionally** classified
  into `ExtractionResult.resolvable` (`extraction.py:135-138`): `{"index", "record_type",
  "missing": [...], "reason"}`, naming whichever identity group came closest (fewest-missing,
  tie-broken toward the group with more fields already present — `extraction.py:657-665`).
- The operator-facing loop lives entirely in prose (`extraction.md:39-68`,
  `contact-upload/SKILL.md:205-216`): Claude proposes a value from one of four closed sources
  (`hubspot_lookup`, `operator_statement`, `provider_result`, `same_row_derivation` —
  `RESOLUTION_SOURCES`, defined once in `operator-claude-plugin/scripts/resolution_sources.py`
  and re-exported by both `extraction.py:114` and `enrichment.py:31`), the operator says yes,
  Claude **rewrites the extraction artifact** adding the value to `row` and an entry to a
  sibling `resolutions` list `{"field", "source", "detail"}`, and re-runs `validate()`.
- `validate()` checks `resolutions` **before** the identity check
  (`extraction.py:580-636`, comment: "the anti-laundering control (T-59-20)") and **for every
  accepted record, not only ones that failed the pre-flight** — an entry naming a source outside
  `RESOLUTION_SOURCES`, or a field the row has no value for, rejects the whole record. There is
  no Python function that fills a value; only the operator's confirmed rewrite does.

**Reuse assessment: reuse, don't duplicate.** Two things make this a clean fit for Phase 61
rather than a forced one:

1. `provider_result` is already in the closed vocabulary and is defined, verbatim, as "a value
   the enrichment waterfall already returned for this row" (`extraction.md:45`) — this is
   *exactly* Phase 61's "propose what the waterfall found, with provenance."
2. The `resolutions` validation is **not** gated on the record having failed `has_identity()`
   first (confirmed by re-reading `validate()`'s ordering, `extraction.py:487-515`: resolutions
   are validated for every record, the identity check runs after). This matters because a
   `linkedin_url`-only row, once `[linkedin_url]` is added as its own group, will **pass** the
   identity pre-flight immediately (it is not `resolvable` in D-59-08's sense — it was never
   rejected). Phase 61 needs to propose *additional* fields (name, company, jobtitle, email) that
   the waterfall found for an already-accepted row, which is a different moment in the flow than
   D-59-08's "resolve a missing identity field" moment, but the **same underlying mechanism**
   (an artifact rewrite carrying a `resolutions` entry, confirmed by the operator, re-validated)
   applies unchanged. No second proposal surface, no second confirmation vocabulary, and no
   second closed-source list are needed — the plan should route Phase 61's proposal through this
   same `resolutions`-carrying rewrite-and-revalidate loop rather than inventing a new one.

## Q5 - The cost/consent seam

Traced through `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` steps 2 and 5
(this is the flow the walk actually exercised, per `53-WALK-RECORD-3.md`):

- **Step 2's match** (`preingest.match_batch`/`fetch_matches`,
  `operator-claude-plugin/scripts/preingest.py:102-158, 181-233`) is **unarmed and free by
  construction**: `fetch_matches` "takes NO `armed` parameter at all" and sends
  `enrichment.build_envelope(chunk, [])` — an explicit empty provider list
  (`preingest.py:110-113`). This holds **regardless of what identity key the row carries** —
  adding `linkedin_url` support to this call changes what gets searched, not whether spending
  is possible. **No new spend-without-consent path opens here.**
- **Step 5's enrich dispatch** is the actual spend, and it is unconditionally gated on either an
  open write grant (`write_grant.authorize_send`) or a fresh, single-use, this-send-only consent
  (`write_grant.authorize_ungranted_send`) — `enrich-before-ingest/SKILL.md:290-334`. This gate
  is keyed on the **call itself** (record ids/domains being sent), not on which identity field
  triggered inclusion in `unmatched`. A linkedin-only row that reaches `unmatched_rows` goes
  through the **identical** consent gate as any other unmatched row — no bypass exists in the
  code read this session.

**Where a real new risk could be introduced, and how to avoid it:** if the plan's fix for Q3's
gap is implemented as some new ad hoc code path that calls a provider directly (bypassing
`chunking.dispatch_plan`/`enrichment.build_envelope`/the armed-window mechanism) rather than
widening the existing `MATCH_LOOKUP_KEYS`/lane/search-node machinery, it would sit outside every
audited gate. **The plan should require that any linkedin-driven match or enrich call is made
through the existing `preingest.match_batch` (free, unarmed) and `chunking.dispatch_plan`
(armed, gated) functions — never a new transport.** This is also the path of least work, since
those functions already handle chunking, retries, and the armed-window discipline correctly.

One gap **is** worth flagging even though it isn't a consent-bypass: today, a linkedin-only row
would land in `unchecked` (Q3), and `enrich-before-ingest/SKILL.md:134-138` step 2's own text
says "offer a retry for this group specifically" for `unchecked` rows — retrying against an
unfixed `laneOf()` would silently do nothing forever, which reads to the operator as "the system
tried and still can't," when in fact the system never tried at all. This is a UX-correctness risk
(a misleading "we could not look" for a case the backend structurally cannot look at yet), not a
cost/consent risk — but it is the mechanism by which the walk-failure experience could recur in a
new shape after only the front-end gate is patched.

## Q6 - Blast radius

**Shared by, and must keep working:**

- `config/column_mapping.yaml` / `operator-claude-plugin/config/column_mapping.yaml` are read by:
  `extraction.py` (contact-upload, enrich-before-ingest), `src/file_loader.py` (local Python
  oracle, `src/ingest.py`), and `preview.py`'s `label_headers` (header-mapping preview, used by
  `preingest.rows_from_table`). Adding a `[linkedin_url]` group here is additive to
  `required_identity.any_of` and does not touch `aliases`, so
  `tests/n8n/columnMapAliasParity.test.mjs` (which pins `ALIASES` only) is unaffected.
- **`n8n/code/columnMap.js`'s `requiredIdentity()` is hand-written, not YAML-derived** — it
  **must** be edited in the same change or the deployed `Map Columns` node drifts from the
  plugin's own preview/extraction gate, silently reproducing exactly the "the client tells the
  operator a header is understood and the backend silently drops it" failure mode
  `columnMapAliasParity.test.mjs`'s own header comment (lines 3-8) warns about for aliases — the
  same risk applies to the identity rule and currently has **no test guarding it** (see Q7).
- **Must NOT touch:** `operator-claude-plugin/config/company_column_mapping.yaml` (D-58-11's
  name-alone company identity rule, a wholly separate file/config) and the `name_company`
  weak-key path inside `resolveIdentity.js`/`columnMap.js` (still requires all three of
  firstname+lastname+company; adding a linkedin group is additive, not a replacement of that
  branch).
- **Must NOT touch:** `extraction.py`'s `hold_emailless`/`write_dispatch_csv` STRUCT-02 email-only
  dispatch gate (lines 808-909). This is a **separate, stricter rule for the bulk-CSV write step**
  only, independent of the identity pre-flight — a linkedin-matched-but-still-emailless row is
  correctly *held* from the CSV dispatch (it has no email to key a HubSpot `contacts` CRUD write
  by on that path) and instead flows to `enrich-records` by object id, which is already the
  documented behaviour for "a confirmed match with no email"
  (`enrich-before-ingest/SKILL.md:491-494`). Phase 61 does not need to, and should not, touch this
  gate — the existing "no-email row keeps its id, nothing else" path already covers a matched
  linkedin-only contact correctly.
- **D-61-03's fence (name-only rows stay on `name_company`/`needs_review`)** is naturally
  preserved by an *additive* group: adding `[linkedin_url]` next to the existing two groups in
  `required_identity.any_of` changes nothing about how a firstname+lastname+company-only row (no
  email, no linkedin) is evaluated — it still only satisfies the second group, and its resulting
  HubSpot match still only ever reaches the weak `name_company`/`ambiguous` path in
  `resolveIdentity.js`/`identity.py`. No code path lets a bare name inherit the new group's
  strength.

## Q7 - Test surface

Enumerated by node id, from tests read this session:

**Will very likely stay green (loose/unrelated assertions), verify by running:**
- `operator-claude-plugin/tests/test_identity_preflight.py::test_record_missing_identity_is_rejected_with_reason_naming_the_rule_and_not_accepted` — asserts only `"identity" in reason`; a jobtitle-only row still fails all three groups after the change.
- `operator-claude-plugin/tests/test_identity_preflight.py::test_whitespace_only_identity_field_is_rejected_diverging_deliberately_from_file_loader_has_identity` — email-only scenario, unaffected.
- `operator-claude-plugin/tests/test_extraction_resolvable.py::test_contact_missing_company_is_rejected_and_also_reported_resolvable` — traced the tie-break arithmetic by hand (`extraction.py:657-665`): a firstname+lastname-no-company row still resolves to the `[firstname,lastname,company]` group as "closest" even with a third `[linkedin_url]` group added (that group ties on missing-count=1 but loses the "-present count" tie-break to the name group's 2-present). Should stay green; **must be run, not just reasoned about**, before relying on this.
- `operator-claude-plugin/tests/test_extraction_email_gate.py` (14 tests) — pins STRUCT-02 (`hold_emailless`/`write_dispatch_csv`), entirely orthogonal to the identity-group change per Q6.

**Will need deliberate, additive updates (new lane/group), not deletions:**
- `tests/n8n/matchProposal.test.mjs` (~30 pinned `laneOf`/`summarizeMatch` cases,
  `tests/n8n/matchProposal.test.mjs:18-354`) — adding a `linkedin` branch to `laneOf()` is
  additive to every existing case (none of them pass `identity_keys.linkedin_url` today), so no
  existing assertion should need to change, but new tests are required for: linkedin present with
  no email/object_id -> lane `"linkedin"`; email takes priority over linkedin when both present
  (mirrors `resolveIdentity.js`'s ordering, email checked before linkedin); a
  `summarizeMatch({lane: "linkedin", ...})` high/none pairing mirroring the existing `email`
  lane's own two tests (lines 244-260).
- `n8n/code/columnMap.js`'s `requiredIdentity()` — no dedicated JS unit test was located this
  session for `requiredIdentity()` specifically (only alias-table parity in
  `columnMapAliasParity.test.mjs`); a new test asserting `requiredIdentity({linkedin_url: "..."})
  === true` should be added alongside the code change, since nothing currently pins this
  function's behaviour at all.
- `operator-claude-plugin/tests/test_extraction_contract.py` — parses and runs the
  `extraction.md` JSON example block (per that file's own docstring, `extraction.md:153-155`, "a
  test in this plugin's suite parses it out of this file and runs it through the real
  validator"); if a linkedin-only example is added to `extraction.md`'s worked examples, this
  test's parse of the fenced block will need to keep working against the new example — check this
  file before editing `extraction.md`'s example JSON.

**Explicitly flagged in CONTEXT.md, reconfirmed this session:**
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` runs a set-equality census over
  every documented `python3 scripts/...` call sequence appearing in a `SKILL.md`. If Phase 61's
  fix adds or changes a documented sequence in `contact-upload/SKILL.md` or
  `enrich-before-ingest/SKILL.md` (for example, a new paragraph showing how to propose a
  waterfall-found value via the D-59-08 loop for a linkedin-only row), that sequence's call tuple
  becomes new and the census will fail closed. `GRANDFATHERED_UNCOVERED` is empty with
  `MAX_GRANDFATHERED = 0` (confirmed present in CONTEXT.md's own reading of this file), so **the
  plan must budget a real composition test for any new documented sequence**, not a grandfather
  entry — this is a planning-time cost, not a follow-up.

**Not found this session (say so explicitly, per the brief's instruction not to guess):**
- No dedicated `n8n/tests`-style unit-test file for `resolveIdentity.js` in isolation was located
  in the `tests/n8n/` directory listing pulled this session (`dedupeSweepWiring.test.mjs` imports
  a piece of `resolveIdentity.js` but was not opened to check whether it exercises the linkedin
  branch). If the plan changes `resolveIdentity.js`'s ordering or adds anything to it, search
  again for a dedicated test before assuming none exists.
- `tests/test_e2e_ingest.py`'s fixture (`contacts_e2e.csv`, 5 canonical paths through
  `src/ingest.py`) was not opened to confirm whether it already includes a linkedin-matched row.
  If the Python oracle (`src/identity.py`) is also brought into scope (it is not required by
  D-61-05's evidence table, which cites only the n8n JS files), this fixture would need a 6th
  path and `test_all_five_paths_have_exact_outcomes_and_actions` would need renaming, not just
  editing.

## Recommended implementation shape

Two coordinated changes, both required for the walk scenario to actually resolve rather than
dead-end differently:

**A. Front-end contract (extraction/ingest gate), strictly scoped to D-61-03's two strong keys:**
1. Add `- [linkedin_url]` as a third `required_identity.any_of` group in **both**
   `config/column_mapping.yaml` and `operator-claude-plugin/config/column_mapping.yaml` (they
   must stay byte-identical — no test currently pins that beyond `diff`, worth a quick check).
2. Hand-edit `n8n/code/columnMap.js:79-84`'s `requiredIdentity()` to add the third `if
   (_present(row.linkedin_url)) return true;` branch, since it is not YAML-derived. Regenerate/
   redeploy the `Map Columns` node via `scripts/build_cloud_workflows.py`.
3. Rewrite the hard-coded rejection reason in `extraction.py:642-645` to mention `linkedin_url`
   (either by hand or by deriving the message from `identity_groups()` generically — the latter
   also fixes future drift for free).
4. Edit `extraction.md:27-28`'s prose to name the third group, and add a worked
   linkedin-url-only example alongside the existing email and name+company examples (respecting
   `test_extraction_contract.py`'s parse of this file, per Q7).
5. Leave the no-invention rule (lines 17-26) and D-61-02's boundary completely untouched — this
   is a pure additive change to the *group list*, not to what counts as inventing a value.

**B. Backend match capability (the part D-61-05 under-scoped), additive only, strong keys only:**
1. Widen `operator-claude-plugin/scripts/enrichment.py:71`'s `MATCH_LOOKUP_KEYS` to include
   `linkedin_url` (it is explicitly documented as the single allowlist controlling what crosses
   the boundary on a rows/match envelope — this is a one-line, well-contained change site).
2. Add a `linkedin` lane to `n8n/code/matchProposal.js:30-42`'s `laneOf()` — checked after
   `email` (mirroring `resolveIdentity.js`'s own strong-key ordering, email first) and before
   `name` — and a matching `summarizeMatch()` high/none pairing for it.
3. Add a HubSpot search node (or extend the existing search's filter groups with an OR branch, if
   the native HubSpot node supports it) filtering on the correct live LinkedIn property name —
   **verify this against the live portal before writing it**; do not assume it is `linkedin_url`
   (see Q2's flagged discrepancy against `lv_linkedin_url`) — in whichever workflow performs the
   match that `preingest.match_batch` calls into.
4. Wire that search's adapter to populate `searchResultsByKey.linkedin_url` /
   `identity_keys`-driven candidate ids the same way `ADAPT_SEARCH_RESULTS` does for email today,
   so `resolveIdentity.js`'s existing strong-key branch (if this path is later also given to the
   bulk-CSV lane) or the new `linkedin` lane (for the match/enrich lane) actually has data to
   read.
5. **Reuse D-59-08's `resolutions`/`provider_result` mechanism (Q4) for the proposal step** —
   route "propose what the waterfall found" through the existing artifact-rewrite-and-revalidate
   loop rather than building a second confirmation surface.
6. Every new call this enables must go through the existing `preingest.match_batch` (free) and
   `chunking.dispatch_plan`/armed-window (gated) functions — never a new transport (Q5).

**Sequencing note for the planner:** A alone reproduces the failure in a new shape (dead-ends in
`unchecked`, Q3/Q5). B alone is unreachable without A (the row never gets past extraction to be
matched at all). They must land together, or A must land with an explicit, honest
`unchecked`-with-reason message ("linkedin matching is not yet available; enrichment still
requires the operator to confirm a resolution") rather than silently offering a "retry" that can
never succeed — if the plan chooses to sequence them across two waves for review-size reasons.

## Risks and unknowns

- **[MEDIUM]** The live HubSpot property name for LinkedIn is unconfirmed this session
  (`linkedin_url` per `src/identity.py:65` vs. `lv_linkedin_url` per the PN-1 rename comment in
  `scripts/build_cloud_workflows.py:278-279`). Whoever writes the new search filter in shape B
  step 3 must verify this against the live portal (read-only property list) before writing the
  filter — writing it wrong produces a search that always returns zero hits, silently
  reproducing "match" failure with no error.
- **[MEDIUM]** The "name" lane (`laneOf()`'s `lastName && companyName` branch) in the
  enrichment/match workflow appears to have no backing HubSpot search node in the trace performed
  this session (only one `"HubSpot Search"` node, filtered `email EQ`, was found in that
  workflow's contact branch). This is out of scope for D-61-03 (name-only rows are explicitly
  fenced off), but if the planner reuses any of this workflow's plumbing for the new `linkedin`
  lane, do not assume the "name" lane's wiring is a working reference pattern to copy — verify it
  independently first.
- **[LOW-MEDIUM]** No test currently pins parity between `config/column_mapping.yaml`'s
  `required_identity.any_of` and `n8n/code/columnMap.js`'s hand-written `requiredIdentity()`
  (only the alias table has such a test). The plan should consider adding one
  (`columnMapAliasParity.test.mjs`-style) as part of this phase, both to catch the immediate
  three-way edit this phase requires and to prevent the same drift recurring later.
- **[LOW]** `tests/test_e2e_ingest.py`'s 5-path fixture and `src/identity.py`/`src/ingest.py`
  (the local-first Python oracle) were read only partially this session. D-61-05's evidence table
  cites only the n8n JS files, so the oracle may be legitimately out of scope for this phase —
  but if the plan touches `src/identity.py` for any reason (e.g., to fix the property-name
  discrepancy above), this fixture and test name will need updating too.
- **[LOW]** This research did not locate a dedicated unit-test file exercising
  `n8n/code/resolveIdentity.js`'s `linkedin_url` branch in isolation (only referenced from
  `dedupeSweepWiring.test.mjs`, not opened). Confirm its actual test coverage before relying on
  "this branch is already tested" as a planning assumption.

## Sources

### Primary (HIGH confidence — all read directly this session)
- `.planning/phases/61-autonomous-batch-runs/61-CONTEXT.md`
- `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD-3.md`
- `n8n/code/resolveIdentity.js`, `n8n/code/columnMap.js`, `n8n/code/matchProposal.js`,
  `n8n/code/lushaRequest.js`
- `config/column_mapping.yaml`, `operator-claude-plugin/config/column_mapping.yaml`
- `operator-claude-plugin/scripts/extraction.py`, `operator-claude-plugin/scripts/preingest.py`,
  `operator-claude-plugin/scripts/enrichment.py`
- `operator-claude-plugin/skills/contact-upload/extraction.md`,
  `operator-claude-plugin/skills/contact-upload/SKILL.md`,
  `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`
- `scripts/build_cloud_workflows.py` (all node-building sections cited above by line)
- `src/file_loader.py`, `src/identity.py`
- `tests/n8n/matchProposal.test.mjs`, `tests/n8n/columnMapAliasParity.test.mjs`,
  `operator-claude-plugin/tests/test_identity_preflight.py`,
  `operator-claude-plugin/tests/test_extraction_resolvable.py`,
  `operator-claude-plugin/tests/test_extraction_email_gate.py`

No web research was performed (out of scope per the research brief). No live n8n, HubSpot,
Anthropic, or provider calls were made.

## Metadata

**Confidence breakdown:**
- Where the rule lives (Q1): HIGH — every site cited was opened and quoted this session.
- Whether the backend can already match/enrich by linkedin_url (Q3): HIGH for what exists (all
  files read directly); MEDIUM for "this contradicts D-61-05" being the *complete* picture, since
  a couple of adjacent nodes (the "name" lane's search, `dedupeSweepWiring.test.mjs`'s coverage)
  were not fully traced.
- D-59-08 reuse assessment (Q4): HIGH — the mechanism's code and prose were read in full and the
  ordering (`resolutions` validated independently of the identity pre-flight) was verified
  directly in `extraction.py`.
- Test surface (Q7): MEDIUM — node ids for existing tests were read directly; the *effect* of the
  proposed change on `test_extraction_resolvable.py`'s tie-break was reasoned by hand from code,
  not confirmed by running pytest (out of scope: this is a research task, not an execution task).

**Research date:** 2026-08-30
**Valid until:** treat as valid until the next edit to any file cited above — this is
internal-codebase archaeology, not a claim about external library behaviour, so there is no
natural expiry beyond "the code changed."
