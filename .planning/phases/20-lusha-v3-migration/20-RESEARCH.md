# Phase 20: Lusha v3 Migration - Research

**Researched:** 2026-07-30
**Domain:** Third-party enrichment API migration (Lusha REST v2 → v3) inside an n8n Cloud + Python codegen pipeline
**Confidence:** MEDIUM (codebase findings HIGH; Lusha v3 wire-contract findings MEDIUM/LOW — a live probe is the phase's own first deliverable, not a research-phase substitute)

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase yet (`/gsd-discuss-phase` has not run). The following are
therefore sourced from REQUIREMENTS.md / ROADMAP.md Milestone 5 and are being treated as locked
scope, not open discussion:

### Locked Decisions (from ROADMAP.md Phase 20 goal + success criteria)
- Both Lusha lanes (contacts + companies) move to `POST /v3/*/search-and-enrich`.
- `reveal[]` is derived from the enrichment gate's `missingFields` — never pay for a field
  already present in HubSpot.
- New staging properties `lusha_contact_id` / `lusha_company_id` persist on match; re-enrichment
  passes the stored ID for `canReveal.credits: 0`.
- `lushaCandidates()` in `normalizeProviders.js` must keep emitting field-identical candidates
  downstream (merge/score/staging schema unchanged beyond the two new ID properties).
- `api_key` header auth is retained (not swapped for Bearer/OAuth).
- Verification requires both suites green, frozen fixture re-baselined, and a **disarmed**
  redeploy with a read-back proving zero v2 URLs remain live.
- Deadline: Lusha v2 sunsets 2026-11-18 (headers already carry sunset notices since 2026-05-18).

### Claude's Discretion
- Exact `reveal[]` value strings (e.g. `"emails"` vs `"phones"`) — pending live-probe
  confirmation (REQ-lusha-v3-contract-probe is explicitly the phase's own verification step,
  not something this research session can substitute for, given the primary docs are a
  JS-rendered SPA that could not be fetched byte-exact in this session — see Assumptions Log).
- Whether the two-step `search` → `enrich` pattern or the combined `search-and-enrich` endpoint
  is used for the initial migration (ROADMAP explicitly asks for both to be exercised/documented,
  but the production builders can ship on `search-and-enrich` alone if the two-step buys no
  measurable credit savings for this waterfall's usage pattern).
- Exact shape of the companies-lane `reveal[]`/credit model (docs found describe contacts
  reveal pricing explicitly; companies-lane selective reveal is unconfirmed — flagged as an
  Open Question).

### Deferred Ideas (OUT OF SCOPE)
- Lusha Prospecting / Lookalikes / Tables / Decision Makers APIs (`/prospecting/*`) — a
  **different product line** from the Enrichment API this phase touches. Several web-search
  results returned Prospecting-API details (`POST /prospecting/contact/enrich`,
  `requestId`/`contactIds` two-step) that must NOT be conflated with the Enrichment API's
  `/v3/contacts/search-and-enrich` — see Common Pitfalls.
- Lusha `waterfallReveal` third-party fall-through beta — needs support-enabled account access.
- HubSpot-side ICP formula placeholder, JTBD 2 rubric sign-off — unrelated, deferred to v0.6+.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-lusha-v3-contract-probe | Live-probe `POST /v3/contacts/search-and-enrich` and `POST /v3/companies/search-and-enrich` (+ two-step `search`→`enrich`) with minimal spend; document envelope/`has`/`canReveal`/`billing`/error shapes; verify `check_provider_credits.py` against `GET /v3/account/usage`. | §"Lusha v3 Contract (from web research — verify live)" gives the starting hypothesis to probe against; §"check_provider_credits.py already targets v3" shows this half of the requirement may already be satisfied — verify, don't rebuild. |
| REQ-lusha-v3-request-builders | Both lanes swap GET v2 → POST v3, params to body, identity keys unchanged, `api_key` header retained. Builder + local-live variants + `dryrun_batch.mjs`. | §"Codebase Map: every v2 call site" gives exact line-level touch points in `build_cloud_workflows.py`, `dryrun_batch.mjs`. |
| REQ-lusha-selective-reveal | `reveal[]` derived from `missingFields`; never pay for a field HubSpot already holds; full-sweep cost fits ~3.9k balance. | §"Selective reveal design" maps `enrichmentGate.js` `REQUIRED`/`missingFields` → candidate `reveal[]` values; §"Measured Lusha economics" gives the cost baseline to improve on. |
| REQ-lusha-id-staging | New `lusha_contact_id`/`lusha_company_id` staging props; re-enrichment passes stored ID → `canReveal.credits: 0`. | §"HubSpot staging property pattern" gives the exact YAML shape + sync tooling already in the repo — additive, no new tooling needed. |
| REQ-lusha-v3-normalize | `lushaCandidates()` parses v3 envelope, emits field-identical candidates. | §"normalizeProviders.js: what must not change" walks the exact envelope-unwrap logic that needs a v3 branch added alongside (not replacing) the v2 branch. |
| REQ-lusha-v3-verification | v2-pinned tests migrated, frozen fixture re-baselined, both suites green, disarmed redeploy shows zero v2 URLs. | §"Test surface to touch" enumerates every pinned test file and fixture; §"Frozen fixture: what's actually at risk" scopes how much of the frozen-jsCode guard is actually implicated. |
</phase_requirements>

## Summary

Lusha is called from exactly **two** live HTTP call sites (`Lusha Enrich` for contacts,
`Lusha Company` for companies), each duplicated across three build targets (CLOUD workflow,
LOCAL-LIVE headless workflow, and the standalone `scripts/dryrun_batch.mjs` harness) — six
places emitting a v2 URL/body today. All six are generated from **shared Python string
constants** in `scripts/build_cloud_workflows.py` (`ENRICH_BUILD_REQUESTS`,
`ENRICH_BUILD_CO_REQUESTS`, `_http_node`/`_live_http` call sites), so the migration is a
localized, well-bounded change to those constants plus one new parsing branch in
`n8n/code/normalizeProviders.js`'s `lushaCandidates()`. The `api_key` header auth pattern,
credential-store binding (`genericCredentialType`/`httpHeaderAuth`), and `$env`-based local-live
variant are unaffected by the v2→v3 move — only method (GET→POST), URL, and body shape change.

One important repo fact narrows this phase's scope even more: `scripts/provider_registry.py`
and `scripts/check_provider_credits.py` **already** call `GET https://api.lusha.com/v3/account/usage`
(confirmed live 2026-07-24, memory `provider-credit-check-endpoints`) — the credits/usage half of
REQ-lusha-v3-contract-probe is a verification/documentation task, not new code.

The Lusha v3 wire contract itself (exact `reveal[]` values, two-step `search`/`enrich` request
and response bodies, `canReveal`/`billing` field names) could **not** be confirmed byte-exact in
this research session: `docs.lusha.com` is a JavaScript-rendered SPA and returned only page
titles to the fetch tool. What follows is reconstructed from WebSearch result snippets that
themselves quote the docs (MEDIUM confidence at best) and is explicitly flagged for the live
probe this phase's own first success criterion calls for — mirroring the ZoomInfo GTM contract
session precedent already proven in this codebase (Phase 12-13, `zoominfo-gtm-companies-contract`
memory). **Do not let the planner treat the wire-contract section below as ground truth — treat
it as the probe's starting hypothesis.**

**Primary recommendation:** Sequence the plan as (1) a live-probe task against a single
low-value test identity per lane, spending the minimum credits to confirm the v3 request/response
shape (mirrors the ZoomInfo GTM precedent already in this repo) and writing a
`LUSHA-V3-CONTRACT.md`-style note or code comment block the way `build_cloud_workflows.py`
already documents the GTM contract inline; (2) update the six emission sites plus
`lushaCandidates()`'s v3 branch against the now-confirmed contract; (3) add the two ID
staging properties via the existing `sync_hubspot_properties.py` tooling (additive, no new
tooling); (4) re-baseline fixtures/tests; (5) disarmed redeploy + read-back.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Lusha v3 request construction (URL/body/reveal[]) | API / Backend (n8n Code node, build-time Python) | — | Pure request-shaping logic lives in `build_cloud_workflows.py` string constants that emit n8n Code/HTTP node parameters at build time — no browser or SSR tier involved. |
| Lusha v3 HTTP call execution | API / Backend (n8n HTTP Request node) | — | n8n Cloud's `httpRequest` node with `genericCredentialType`/`httpHeaderAuth` — credential material never touches Code nodes (existing pattern, CLAUDE.md §21). |
| Reveal-field selection from `missingFields` | API / Backend (n8n Code node: Enrichment Gate → Build Requests) | — | Gate output (`gate.missingFields`) already flows row-to-row via `...row` spreads; the new reveal-derivation logic is a pure function added to the existing `Build Requests` Code node, same tier as `decideAction`. |
| `lushaCandidates()` v3 envelope parsing | API / Backend (n8n Code node, shared JS module) | — | `normalizeProviders.js` runs inside n8n Code nodes on both CLOUD and LOCAL-LIVE graphs; no tier change from v2. |
| `lusha_contact_id`/`lusha_company_id` persistence | Database / Storage (HubSpot CRM properties) | API / Backend (merge/staging write) | New properties are CRM schema (Database tier); the pipeline's staging-write step (existing `mergeContacts.js`/`mergeCompanies` pattern) is the Backend tier that populates them — no new tier introduced. |
| Credit/usage check (`GET /v3/account/usage`) | API / Backend (`scripts/check_provider_credits.py`, `Lusha Usage` HTTP node) | — | Already on v3; this phase only needs to verify, not migrate, this call site. |
| Test/fixture re-baseline | API / Backend (offline pytest + node --test) | — | Tests execute the *built* JS/Python artifacts locally; no runtime tier. |

## Codebase Map: every v2 call site

All six emission points, confirmed by `grep -n "lusha" scripts/build_cloud_workflows.py` and
direct reads (2026-07-30):

| # | Build target | Lane | Node/function name | Current v2 shape | File:line |
|---|---------------|------|---------------------|-------------------|-----------|
| 1 | CLOUD workflow | Contacts | `"Lusha Enrich"` (`_http_node`, `auth="header"`) | `POST https://api.lusha.com/v2/person`, body `{"contacts":[{"contactId":"1", email?, linkedinUrl?}]}` | `scripts/build_cloud_workflows.py:3604-3614` |
| 2 | CLOUD workflow | Companies | `"Lusha Company"` (`_http_node`, `method="GET"`, `auth="header"`) | `GET ={{ $('Build Company Requests').item.json.lusha_company_url }}` where `lusha_company_url = "https://api.lusha.com/v2/company?" + q.join("&")` (only `domain=` accepted) | `scripts/build_cloud_workflows.py:3822-3825` (URL built at `1702`/`1685-1707`) |
| 3 | LOCAL-LIVE workflow | Contacts | `"Lusha Enrich"` (`_live_http`, GET, `$env` header) | `GET https://api.lusha.com/v2/person?<querystring>` built in `ENRICH_BUILD_REQUESTS` | `scripts/build_cloud_workflows.py:2621-2624` (URL built at `1466-1489`, specifically `1480`) |
| 4 | LOCAL-LIVE workflow | Companies | `"Lusha Company"` (`_live_http`, GET, `$env` header) | `GET https://api.lusha.com/v2/company?domain=...` built in `ENRICH_BUILD_CO_REQUESTS` | `scripts/build_cloud_workflows.py:2718-2721` (URL built at `1685-1707`, specifically `1702`) |
| 5 | dryrun harness | Contacts | `lusha(id)` function | `GET https://api.lusha.com/v2/person?<querystring>`, header `api_key` | `scripts/dryrun_batch.mjs:64-76` |
| 6 | dryrun harness | Companies | *(not present — harness only exercises contacts today)* | n/a | n/a — `dryrun_batch.mjs` has no company-lane Lusha call; REQ-lusha-v3-request-builders explicitly names `scripts/dryrun_batch.mjs` for the contacts lane only |

**Important asymmetry already in the codebase (do not "fix" it as part of this migration
unless the plan explicitly scopes it):** the CLOUD contacts node (#1) posts a
`{"contacts":[{contactId, email, linkedinUrl}]}` body (confirmed live 2026-07-28 against
portal 22617666 — only `email`/`linkedinUrl` are accepted identity properties; `firstName`,
`lastName`, `companyName`, `companyDomain`, `domain`, `phoneNumber`, `jobTitle` are all
REJECTED with a 400). The LOCAL-LIVE contacts node (#3) and dryrun harness (#5) instead build
a **GET querystring** with `firstName`/`lastName`/`companyName`/`companyDomain` — a **broader,
unconfirmed-live** identity set. This split already exists pre-migration; carry the same
split forward on v3 (or resolve it as a documented decision) rather than silently unifying
behavior that was never verified live in one of the two paths.

`Lusha Company` (companies lane, all three targets) has **no such split** — all three already
build only a `domain=` query parameter (`BUG 17` fix, 2026-07-29, live-probed against
`racingnsw.com.au`). This is the simpler lane to migrate.

**Credit/usage endpoint — already on v3, verify only:**
`scripts/provider_registry.py:16-20` and `scripts/check_provider_credits.py` (`_check_lusha`,
`_extract_lusha`) both target `GET https://api.lusha.com/v3/account/usage`, header `api_key`,
reading `credits.remaining` — confirmed live 2026-07-24 (memory
`provider-credit-check-endpoints`: "Remaining at `credits.remaining` (was 4118). Simple,
works."). The `"Lusha Usage"` node referenced in `ENRICH_BUILD_RESPONSE`'s
`CREDIT_NODE_BY_PROVIDER` map (`build_cloud_workflows.py:3330`) and `_credit_http_node`
(`:3341-3355`) should be grepped and confirmed to already carry this v3 URL — do not assume;
verify with `grep -n "v3/account/usage" scripts/build_cloud_workflows.py` during planning,
since the node-builder call site for `"Lusha Usage"` was not located in this research pass
(only the registry/script side was confirmed).

## Selective reveal design

**`missingFields` production (contacts lane) — `n8n/code/enrichmentGate.js` via the
`ENRICH_GATE` wrapper, `scripts/build_cloud_workflows.py:905-924`:**

```python
REQUIRED = ["email", "jobtitle", "mobilephone"]
POLICY = { jobtitle: {stale_after_days:180}, mobilephone: {stale_after_days:180} }
```

`decideAction()` (`enrichmentGate.js:55-107`) returns `missingFields` as the subset of
`REQUIRED` that is blank on the existing HubSpot record — `staleFields` and `invalidFields`
are separate arrays (present-but-stale/invalid is NOT "missing"). **Only 3 fields are ever
gated this way for contacts** — note `"phone"` (landline) is not in `REQUIRED`, only
`"mobilephone"` is. The companies lane (`ENRICH_CO_GATE`, `:1666-1683`) gates
`["lv_org_type", "lv_produces_content"]` — neither of these is a Lusha-revealable field
(Lusha does not supply org-type/content signals per CLAUDE.md §14), so **selective reveal is
a contacts-lane-only concept** as currently scoped; the companies lane's Lusha call has no
`missingFields`-driven credit-saving lever today (see Open Questions).

**Design implication for `reveal[]`:** the reveal-derivation function belongs in the same
`Build Requests` Code node that already reads `gate.missingFields` off the row (it flows
through via `...row` spreads from `Enrichment Gate` → `Build Requests`). A conservative
mapping, to be confirmed against the live v3 response's actual `canReveal` field-name
vocabulary (Open Question):

```js
// Illustrative only — confirm exact reveal[] string values against a live probe response's
// `canReveal[].field` names before hard-coding.
const revealMap = { email: "emails", mobilephone: "phones" };
const reveal = (row.gate.missingFields || [])
  .map((f) => revealMap[f])
  .filter(Boolean);
// jobtitle is NOT a reveal-gated field: Lusha's docs describe title/seniority/department as
// part of the free non-PII "has" preview, not a billed canReveal field — do not add it here.
```

**Never-pay invariant this must satisfy (REQ-lusha-selective-reveal, `fill_blank_only`
discipline, CLAUDE.md §9.2):** `phone`/`mobilephone` are `fill_blank_only` class in
`config/field_policy.yaml` with `protect_if_current_present: true` — the field policy already
encodes "don't touch it if present" at the merge layer; this phase's job is to stop **paying**
for it earlier, at the request layer, when the gate has already told you the field isn't
missing. If `gate.missingFields` is empty (contact already fully populated + fresh + valid),
the gate itself would route the row to `action: "skip"` before `Build Requests` ever runs — so
in practice `reveal[]` on a called request is only ever a non-empty subset when the row reached
the provider waterfall at all. Sanity-check this in the plan's verification step: a contact
with `phone`/`mobilephone` present-and-fresh should never reach `Build Requests` with a
`reveal` entry for that field, by construction of the existing gate, not by an added guard.

## Measured Lusha economics (baseline to beat)

From `measured-provider-match-rates` memory (live 2026-07-30 sample, 68 Lusha calls):

- Lusha burned **~2.5 credits per call, ~4.65 credits per matched reveal** — phone reveals
  bill extra, not flat 1/match. Measured 172 credits for 68 calls (4093→3921 balance).
- Extrapolated full-portal sweep ≈ **12.6k credits** against a **~3.9k credit balance** —
  currently insufficient by ~3.2x.
- Match rate: 44% of sampled contacts, 75% of sampled companies.

**Why v3 selective reveal should help:** the v2 GET always requested (and was billed for)
whatever Lusha's default field set returns per match; v3's `canReveal`-gated reveal model
means a request that reveals nothing (empty `reveal[]`, relying only on the free `has`
preview + already-known HubSpot fields) should bill only the base search/match charge, not
the phone-reveal surcharge that dominates the measured 4.65-credit figure. **This is the
lever REQ-lusha-selective-reveal is pulling** — confirm the actual delta with the live probe
(request once with `reveal:[]`, once with `reveal:["phones"]`, diff the credit debit) before
assuming a specific percentage improvement.

## HubSpot staging property pattern (for `lusha_contact_id`/`lusha_company_id`)

`config/hubspot_properties.yaml` already has both a `companies:` and `contacts:` top-level
key, each with a `groups:` list (companies uses group `lv_enrichment`; contacts uses
`lv_enrichment_contacts`) and a `properties:` list. A same-shape simple text property already
exists as a precedent (`lv_enrichment_reviewed_by`, both objects, lines ~250-255 companies /
~407-412 contacts):

```yaml
- name: lusha_contact_id      # or lusha_company_id under companies:
  label: Lusha Contact Id     # or Lusha Company Id
  type: string
  fieldType: text
  groupName: lv_enrichment_contacts   # lv_enrichment for companies
  options: []
```

Add one entry to each object's `properties:` list. **No new tooling required** —
`scripts/sync_hubspot_properties.py` already implements: `compute_property_diff()` (desired
vs actual, ignores `hubspotDefined` collisions), dry-run-by-default, two-key live-write gate
(`DRY_RUN=false` AND `ALLOW_HUBSPOT_PROPERTY_WRITES=true`), and an undo manifest written to
`config/hubspot_migration/undo-manifest-<uuid>.json` recording only confirmed creates. Run
`python scripts/sync_hubspot_properties.py` (dry-run diff) first, then the live-gated form,
exactly the way the existing `lv_enrichment_*` properties were created — this is additive
schema, not a one-way-door conversion (contrast with Phase 21's `lv_org_type` enum migration,
which explicitly needs a rollback doc first; this phase's two properties do not).

**Where these get written (merge/staging layer):** the contacts/companies merge Code nodes
(`ENRICH_MERGE` / `ENRICH_MERGE_CO`, mirroring `mergeContacts.js`/`mergeCompanies.js`) already
build a `candidate`/staging patch object from `winners`. The v3 response's `contactId`/
`companyId` (or whatever the live-confirmed field name is) needs to flow from the Lusha HTTP
node's raw response through to this merge step — likely via the existing `providers.lusha`
raw-response carry-through (`p.lusha` in `ENRICH_NORMALIZE_SCORE_CO`/`_CLOUD`) rather than a
new pass-through field, since `p.lusha` (the full raw provider response) already reaches the
merge stage today.

**Re-enrichment path:** "a re-enrichment run passes the stored ID" (success criterion 4) means
`Build Requests`/`Build Company Requests` must read `row.existingRecord.lusha_contact_id` /
`.lusha_company_id` (already available — `existingRecord` is the HubSpot search result already
flowing through the gate) and include it in the v3 request body when present, instead of
re-deriving identity from name/email/domain alone. This is a new `if (id present) use it`
branch in the same request-builder functions already being touched for the URL/method change.

## `normalizeProviders.js`: what must not change

`lushaCandidates(rawResponse, objectType)` (`n8n/code/normalizeProviders.js:169-215`) already
handles **three** distinct v2 envelope shapes defensively (never throws, mirrors
skip-not-retry discipline):

1. `{"contacts": {"<contactId>": {error, isCreditCharged, data: {...}}}}` — the REAL live
   plural, contactId-keyed map (confirmed 2026-07-28, portal 22617666) — **primary path**.
2. `{"contact": {"data": {...}}}` — a singular shape **never actually observed live**, kept
   only for offline back-compat (do not delete per the code's own comment).
3. Bare/flat fixture shape (no `contacts`/`contact` wrapper) — offline-fixture convenience.

Company-side (`objectType !== "contacts"` branch) similarly unwraps `raw.company || raw.data
|| raw`, with array-vs-scalar handling for `revenueRange`/`companySize`/`employees`.

**REQ-lusha-v3-normalize's constraint ("emits candidates field-identical to v2 output") means:
add a v3-shape detection branch that unwraps to the same intermediate `raw` object the
existing field-extraction logic below it already consumes** — do NOT rewrite the
field-extraction logic (email/phone/jobtitle/seniority/persona_group for contacts;
revenue/employee/industry/country for companies), since that logic is what
`tests/n8n/enrichment.test.mjs` and `scoreEnrichment.js` consumers depend on being unchanged.
The safest shape: detect the v3 envelope by a distinguishing key (e.g. a top-level
`contactId`/`companyId` field, or `has`/`canReveal` arrays) at the top of `lushaCandidates()`,
normalize it into the SAME intermediate shape the v2 branches already produce (`raw` object
with `emailAddresses`/`phoneNumbers`/`jobTitle` for contacts, `company`-nested firmographics),
then fall through into the existing unchanged logic. This confines the v3-specific code to a
small envelope-adapter block, mirroring how `_zoomRecord()` already isolates ZoomInfo's own
envelope-unwrap from its field-extraction logic in the same file.

**Do not guess the v3 field names for email/phone/jobtitle inside `data`** — the live probe
(REQ-lusha-v3-contract-probe) must confirm whether v3's per-contact object still nests
`emailAddresses`/`phoneNumbers`/`jobTitle` the same way, or renames them (e.g. flattens to
`emails: [...]`, `phones: [...]` matching the `has`/`canReveal` field-name vocabulary found
in web research). Building the parser before the probe risks a second silent-400-style bug
like BUG 17.

## Test surface to touch (REQ-lusha-v3-verification)

Confirmed by grep (2026-07-30) — every file with a Lusha-specific assertion:

| File | What it pins | Migration impact |
|------|---------------|-------------------|
| `tests/n8n/lushaRequestContract.test.mjs` | The CLOUD contacts node's v2 body shape (`{"contacts":[{contactId,email,linkedinUrl}]}`) by evaluating the node's real committed `jsonBody` expression via `new Function` | **Full rewrite** — pins the exact v2 contract; needs the v3 equivalent test asserting the new body shape |
| `tests/test_cloud_companies_branch.py` (`test_lusha_company_uses_the_live_get_contract_and_sends_no_body`, `test_build_company_requests_never_puts_companyname_in_the_lusha_query`) | GET method + `domain=`-only query for the companies lane | **Full rewrite** — method changes GET→POST, query→body |
| `tests/n8n/enrichment.test.mjs` (~53 Lusha-touching assertions) | `toCandidates("lusha", ...)` output shape across 4 fixture files (`lusha_contact.json`, `lusha_company.json`, `lusha_live_person.json`, `lusha_live_person_v2.json`) | **Additive** — add v3-fixture test cases alongside existing v2 ones (v2 parsing must still work per the code's own "kept for back-compat" precedent, OR be explicitly retired — a plan decision) |
| `tests/test_builder_flag_parity.py` (line 124) | `"LUSHA_API_KEY": {"Lusha Enrich", "Lusha Company"}` node-name-to-env-var mapping | **No change expected** — node names stay the same, only their URL/method/body change |
| `tests/test_provider_gate_topology.py` (~23 Lusha references, incl. `test_track_b_lusha_company_url_method_mismatch_is_flagged_in_builder_source`) | Gate chain topology (node names, edges) + a stale "Track B" docstring assertion referencing the old GET v2 contract | **Mostly no change** (topology/node-names unaffected); the Track B test's docstring is now historical trivia post-BUG-17-fix and will need its own docstring/assertion updated if the plan touches that literal text |
| `tests/test_check_provider_credits.py` | Mocked `GET .../v3/account/usage` response shape | **No change** — already v3; use to *verify*, not migrate |
| `tests/n8n/providerSelection.test.mjs` | `extractCredits("lusha", raw)` reading `credits.remaining` | **No change** — same v3 shape already |
| `tests/test_companies_factory_frozen.py` + `tests/fixtures/companies_jscode_frozen.json` | Byte-identical jsCode guard for 7 named nodes: `Research Trigger Gate`, `Build Research Request`, `Validate Research Output`, `Judge Gate`, `Build Judge Request`, `Apply Judge Verdict`, `Merge Company` | **Likely unaffected** — `"Lusha Company"`/`"Normalize + Score Company"` are NOT in `FROZEN_NODE_NAMES`; only re-baseline this fixture if `inline()`'s shared-module concatenation pulls Lusha-adjacent code into one of the 7 frozen nodes (verify with a diff before assuming no impact) |
| `scripts/dryrun_batch.mjs` (`lusha(id)` function) | v2 GET request, no direct pytest/node-test coverage found (manual harness) | Rewrite to v3 POST; no automated test currently pins this file's Lusha function specifically |

**Test counts from phase description (unverified in this pass, trust but verify at plan
time):** ~603 pytest cases (`.venv/bin/python -m pytest`), ~309 node test cases
(`node --test tests/n8n/*.test.mjs`) — per memory `test-suite-run-commands`, use the venv
python binary directly and the glob node invocation (not directory form — broken on Node 24).

## Frozen fixture: what's actually at risk

`tests/test_companies_factory_frozen.py` guards 7 specific companies-branch Code nodes against
silent drift when a shared JS module (`inline()`-concatenated) changes without a rebuild. The
STATE.md/CLAUDE.md handoff note ("re-baseline frozen companies jsCode fixture") from a prior
session (`4d87fb3`) was triggered by the Haiku research-model swap — a **different** change
than this phase's Lusha migration. Verify whether `Merge Company` or any of the other 6 frozen
nodes actually consume Lusha-specific code via `inline()` before assuming this phase must
re-baseline the fixture again; from the `ENRICH_MERGE_CO`/`inline()` call sites read in this
session, `Merge Company`'s inlined modules are `mergeContacts.js`-equivalent merge logic, not
`normalizeProviders.js` — so a `lushaCandidates()` change alone likely does NOT touch any of
the 7 frozen nodes. **Confirm this with a diff at plan time rather than assuming either way.**

## Common Pitfalls

### Pitfall 1: Conflating the Enrichment API with the Prospecting API
**What goes wrong:** Building the v3 request/response parser against
`POST /prospecting/contact/enrich`'s `requestId`+`contactIds`+`revealEmails`/`revealPhones`
boolean-flag shape, when this phase's actual target is the **Enrichment API**'s
`POST /v3/contacts/search-and-enrich` (a different product line, different request shape,
likely a `reveal: [...]` array rather than boolean flags).
**Why it happens:** Lusha's own docs and third-party integration write-ups (Pipedream, help
articles) frequently describe the Prospecting API's two-step `search`→`enrich` flow, which
LOOKS structurally similar and shares vocabulary (`reveal`, `canReveal`, `contactId`) with the
Enrichment API, but is a CLAUDE.md-declared **out-of-scope** surface ("Lusha Prospecting /
Lookalikes / Tables / Decision Makers APIs — net-new acquisition surfaces, not enrichment of
existing CRM records").
**How to avoid:** During the live probe, hit `POST /v3/contacts/search-and-enrich` specifically
(not `/prospecting/*`) and treat any Prospecting-API-shaped response fields (`requestId` at
the top level tied to a bulk contactIds array) as a signal you've probed the wrong endpoint.
**Warning signs:** A response containing `contactIds` (plural, array) submitted in the SAME
request as identity fields, or a `requestId` used across two separate calls — that's the
Prospecting two-step, not the Enrichment search-and-enrich single call this phase needs.

### Pitfall 2: Repeating BUG 17 (identity-shape mismatch silently swallowed)
**What goes wrong:** BUG 17 (fixed 2026-07-29) was exactly this class of bug: the Lusha
Company node POSTed an identity object at an endpoint that only accepted `?domain=`, 400'd on
every single call, and was invisible because `onError: "continueRegularOutput"` turns a
provider failure into a normal-looking item instead of a node failure — every company run
"succeeded" while silently enriching from 2 providers instead of 3.
**Why it happens:** `onError: "continueRegularOutput"` is the correct choice for provider
calls (a down provider must not fail the whole enrichment run), but it means a malformed
request is invisible in the n8n execution log the same way a legitimate no-match is.
**How to avoid:** After migrating each of the six call sites, live-probe with a real credential
and manually inspect the raw HTTP response status/body — do not trust "the workflow executed
without error" as evidence the v3 request shape is correct. This is exactly what
REQ-lusha-v3-contract-probe is for; do not skip straight to writing the request builders
without first confirming a 200 with a real payload.
**Warning signs:** A provider column that silently drops to `gap_flag: true` or missing
candidates for a specific field across every row, not just unmatched-record rows.

### Pitfall 3: Removing v2 fixture/parsing support the wrong way
**What goes wrong:** Deleting the v2 branch in `lushaCandidates()` (or the v2 fixtures) before
confirming production HubSpot data doesn't have any in-flight or cached v2-shaped raw
responses stored anywhere (e.g. in `providers.lusha` on an in-progress execution, or in a
`enrichment_last_decision` audit JSON blob already written to a HubSpot record).
**Why it happens:** "Both suites green" (REQ-lusha-v3-verification) is satisfiable either by
migrating tests in place (replacing v2 assertions) or by adding v3 assertions alongside v2
ones — the requirement text ("v2-pinned tests migrated") suggests replacement, but the code's
own precedent (`lushaLive`/singular-shape kept "for offline back-compat... do not delete") is
adjacency, not full replacement.
**How to avoid:** Decide explicitly in the plan whether v2-shape parsing in
`lushaCandidates()` is retired entirely (since v2 is sunsetting and no NEW v2 responses will
ever arrive after this migration ships) or kept dead-code-style for defensive backward
compatibility with any already-staged raw responses. Given v2 dies 2026-11-18 and this
migration ships before then, retiring the v2 branches cleanly (not leaving unreachable dead
code) is the more honest choice — but say so in the plan rather than leaving it ambiguous.
**Warning signs:** A v3 branch bolted on top of the v2 branch with no test ever exercising the
v3 path because the fixtures still only cover v2 shapes.

### Pitfall 4: Assuming `reveal[]` semantics apply uniformly to both lanes
**What goes wrong:** Building a `reveal[]`-derivation helper generic enough to be reused
verbatim for the companies lane, when the companies gate (`ENRICH_CO_GATE`) tracks
`lv_org_type`/`lv_produces_content` — fields Lusha has never supplied (CLAUDE.md §14) — so
there is no natural `missingFields → reveal[]` mapping on that lane at all.
**Why it happens:** The requirement text names both lanes for the request-builder swap
(REQ-lusha-v3-request-builders) but only describes the reveal-cost-control mechanism in
contact terms (REQ-lusha-selective-reveal: "a contact record that already holds phone/mobile
...").
**How to avoid:** Scope `reveal[]`-derivation to the contacts lane only; for companies, confirm
via the live probe whether v3 companies/search-and-enrich even has a reveal-gated credit model,
or whether firmographic data is billed as a flat per-match charge with no selective-reveal
lever (see Open Questions).

## Assumptions Log

> The Lusha v3 wire-contract details below could not be verified via direct document fetch in
> this session (docs.lusha.com renders via JavaScript; WebFetch retrieved only page titles).
> All entries are derived from WebSearch result snippets that themselves summarize/quote the
> docs — MEDIUM-at-best confidence, several LOW. **The phase's own first success criterion
> (REQ-lusha-v3-contract-probe) is designed to resolve exactly this gap with a live probe —
> treat every row below as the probe's starting hypothesis, not a locked contract.**

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `POST /v3/contacts/search-and-enrich` and `POST /v3/companies/search-and-enrich` are the correct v2→v3 endpoint mappings (this one is the most solidly sourced — appears verbatim in the official v3-migration-guide search snippet). | Summary, Codebase Map | Low — this specific mapping was independently corroborated by the prior session's memory note (`lusha-v3-migration-deadline`) and a WebFetch of the migration guide page; treat as MEDIUM-HIGH. |
| A2 | The request body moves query params into a JSON body, with identity keys named similarly to v2 (`email`, `linkedinUrl`, possibly `firstName`/`lastName`/`companyName`/`companyDomain` for contacts; `domain`/`name`/`id` for companies). | Codebase Map, Selective reveal design | Medium — if v3 uses different field names (e.g. camelCase differences, nested identifier objects), the request builders will 400 exactly like BUG 17 until re-probed. |
| A3 | `reveal[]` is an array of string field names such as `"emails"`/`"phones"`, and a `canReveal` response array of `{field, credits}` objects describes what's revealable and its cost — with `title`/`seniority`/`department`-style fields available for free in the non-PII `has` preview. | Selective reveal design | High if wrong — this is the exact mechanism REQ-lusha-selective-reveal depends on; if reveal costs work differently (e.g. flat per-call fee regardless of which fields are revealed), the entire cost-savings premise of this requirement needs re-evaluation. |
| A4 | Companies lane has no distinct reveal-gated credit model (firmographic data may be billed as a flat search/enrich charge, not per-field reveal). | Common Pitfalls #4, Open Questions | Medium — if companies DOES have a reveal-gated model, the plan should extend selective-reveal logic there too, which this research did not scope for. |
| A5 | Auth stays `api_key` header (not migrated to OAuth/Bearer) on v3 enrichment endpoints — corroborated independently by the ALREADY-LIVE v3 usage endpoint (`check_provider_credits.py` uses `api_key` header against `/v3/account/usage` today, confirmed 2026-07-24). | User Constraints (Locked Decisions), Codebase Map | Low — cross-validated against a live-confirmed sibling v3 endpoint in the same API family. |
| A6 | Error response shape is roughly `{"error": {"code": N, "message": "..."}}` for general errors and `{"statusCode": N, "message": "...", "errors": [...]}` for validation errors; rate-limit signals arrive via `x-rate-limit-*`/`x-*-requests-left` response headers, and a 429 does not consume a credit. | (not yet in a dedicated section — surface during plan's error-handling task) | Medium — if wrong, the plan's retry/backoff logic (mirroring the existing `onError: continueRegularOutput` + ZoomInfo mint-retry patterns) may misclassify a billable failure as free or vice versa. |
| A7 | v3 contact/company IDs (`contactId`/`companyId`) are permanent, account-scoped identifiers suitable for the new `lusha_contact_id`/`lusha_company_id` staging properties, and passing a stored ID on a later request yields `canReveal.credits: 0` for already-revealed fields (this is the exact mechanism named in REQ-lusha-id-staging's success criterion). | HubSpot staging property pattern | High if wrong — this is REQ-lusha-id-staging's entire premise; if IDs are NOT free-re-enrichment keys (e.g. they're just opaque record identifiers with no billing exemption), the "re-enrichment is free" success criterion cannot be met as specified and needs renegotiation. |

## Open Questions (deferred to Plan 01 probe — Q1→P2, Q2→P3, Q3→P6, Q4→P8; gated by Plan 01 Task 3 checkpoint)

1. **Does the companies lane have a selective-reveal/credit-gated model at all, or is
   company enrichment a flat per-match charge?**
   - What we know: The v3 migration guide snippet and contacts-focused search results
     describe reveal/canReveal explicitly for contacts (`emails`, `phones` fields with
     per-field credit costs). No search result in this session described a companies-lane
     `reveal[]`/`canReveal` mechanism.
   - What's unclear: Whether `POST /v3/companies/search-and-enrich` even exposes a `reveal`
     parameter, or whether all firmographic fields (revenue, employees, industry, country)
     come back in one flat-fee response.
   - Recommendation: Cover this explicitly in the live-probe task (REQ-lusha-v3-contract-probe
     names both `/v3/contacts/search-and-enrich` AND `/v3/companies/search-and-enrich` for
     exactly this reason) — probe the companies endpoint once with a real domain and inspect
     whether the response includes `canReveal`/`has` at all before assuming REQ-lusha-selective-
     reveal applies there.

2. **Does `POST /v3/contacts/search-and-enrich` (the combined single-call endpoint named in
   the migration guide's GET-mapping) actually support/require a `reveal[]` parameter itself,
   or is `reveal[]` only meaningful on the separate two-step `search` then `enrich` flow?**
   - What we know: Web research surfaced `reveal[]` in the context of BOTH the combined
     `search-and-enrich` single call (`"reveal field... controlling what gets revealed"`) and
     the two-step `enrich`-only call (which takes a `contactIds` array + reveal params). The
     migration guide's endpoint MAPPING (v2 GET → v3 `search-and-enrich`) suggests the
     combined endpoint is the direct v2 replacement, but the "recommended for high-volume"
     framing in several snippets pointed at the two-step flow instead.
   - What's unclear: Whether shipping on the combined `search-and-enrich` single call (simpler,
     one HTTP node per lane, matches the existing topology 1:1) forfeits the "search cheaply,
     enrich selectively" cost benefit the two-step flow is marketed for, OR whether
     `search-and-enrich`'s own `reveal[]` parameter achieves the identical selective-cost
     effect in one call.
   - Recommendation: Probe the combined endpoint FIRST (lowest topology-change cost — keeps
     one HTTP node per lane) with an empty `reveal:[]` vs a populated `reveal:["emails"]` call
     and diff the credit debit. If the combined endpoint's `reveal[]` parameter alone achieves
     the selective-cost goal, there is no need to introduce the two-step topology at all,
     which would require adding an extra HTTP node + IF-branch per lane. Only adopt the
     two-step flow if the probe shows the combined endpoint does NOT let you skip a reveal's
     credit charge (i.e. it always bills for everything Lusha has, regardless of `reveal[]`
     content).

3. **What is the v3 response envelope for a NO-MATCH result, and does it change the
   `gap_flag`/`_zoomRecord`-style defensive-unwrap logic `lushaCandidates()` needs?**
   - What we know: v2's no-match behavior is per-contact (`{"contacts": {"1": {"error":
     "NOT_FOUND", "isCreditCharged": false}}}` — confirmed by an existing test case in
     `enrichment.test.mjs`).
   - What's unclear: Whether v3 preserves this per-item error shape inside a batch-style
     response, or returns a top-level 404/empty-array for a clean no-match — this determines
     whether the existing `raw.contacts[key].error` skip-not-throw check needs an equivalent
     v3 branch or a differently-shaped one.
   - Recommendation: Include a deliberate no-match identity in the live probe batch (a
     fabricated name/company unlikely to exist) alongside the real matched identities, to
     capture this shape at zero-to-minimal extra credit cost (no-match calls are typically
     free/uncharged, consistent with the v2 `isCreditCharged: false` pattern).

4. **Does the `"Lusha Usage"` HTTP-node build site (referenced by name in
   `ENRICH_BUILD_RESPONSE`'s `CREDIT_NODE_BY_PROVIDER` map) already emit the v3
   `/v3/account/usage` URL, matching `provider_registry.py`'s already-v3 config?**
   - What we know: `provider_registry.py` (the side-effect-free single source of truth per
     its own docstring) and `check_provider_credits.py` both confirm v3 usage today.
   - What's unclear: Whether the actual n8n node-builder call site that constructs the
     `"Lusha Usage"` HTTP node in `build_cloud_workflows.py` reads its URL FROM
     `provider_registry.py`'s `credit.url` field (in which case it's already correct, zero
     work) or hard-codes a URL independently (in which case it needs the same v3-verification
     pass this research recommends for the enrichment call sites).
   - Recommendation: `grep -n '"Lusha Usage"' scripts/build_cloud_workflows.py` at plan time
     and confirm the URL source before writing a task for this — this research pass located
     the *registry* config but not the specific node-construction call site using it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `LUSHA_API_KEY` env var | Live probe, local-live workflow, `dryrun_batch.mjs` | Unknown — `.env` is agent-permission-blocked in this environment (memory `env-file-permission-blocked`) | — | Execution-phase task must derive/confirm the key is present via a `!` shell command the human runs, per existing project convention; the research/plan phases cannot read `.env` directly |
| n8n Cloud (disarmed redeploy target) | REQ-lusha-v3-verification's disarmed redeploy + read-back | Assumed available (existing deploy tooling: `scripts/deploy_n8n_workflows.py`) | — | — |
| Live network access to `api.lusha.com` | Live contract probe | Cannot be verified from this research session (no network egress available to this agent) | — | The execution phase's live-probe task is the actual verification point, per the phase's own design — this is expected, not a gap to fill now |

**Missing dependencies with no fallback:** none — all of the above are expected to be resolved
in the execution phase, consistent with the phase's own design (a live-probe-first sequencing).

**Missing dependencies with fallback:** `.env` inspection — handled by the existing
project convention of deriving required vars from source and handing the user a `!` command
(memory `env-file-permission-blocked`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, `.venv/bin/python -m pytest`) + Node's built-in `node:test` runner (`node --test tests/n8n/*.test.mjs`) |
| Config file | none dedicated — pytest auto-discovers `tests/test_*.py`; node test files are `tests/n8n/*.test.mjs` |
| Quick run command | `node --test tests/n8n/lushaRequestContract.test.mjs tests/n8n/enrichment.test.mjs` (fast, Lusha-scoped subset) |
| Full suite command | `.venv/bin/python -m pytest && node --test tests/n8n/*.test.mjs` (per memory `test-suite-run-commands` — use the venv binary directly, and the glob form for node, not the directory form which is broken on Node 24) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-lusha-v3-contract-probe | Live v3 request/response contract confirmed | manual (live-probe, not automatable offline) | n/a — a probe script run once against real credentials, output captured as a comment/doc, not a repeatable pytest | n/a by design |
| REQ-lusha-v3-request-builders | Both lanes emit v3 POST with correct body/URL | unit | `node --test tests/n8n/lushaRequestContract.test.mjs` (contacts) + a new/updated `tests/test_cloud_companies_branch.py` case (companies) | ✅ contacts file exists (needs rewrite); ✅ companies file exists (needs new/updated test) |
| REQ-lusha-selective-reveal | `reveal[]` correctly derived from `missingFields`; never reveals a present field | unit | New test in `tests/n8n/enrichmentGate.test.mjs`-adjacent file or a new `tests/n8n/lushaRevealContract.test.mjs` | ❌ Wave 0 — no existing test covers reveal-derivation logic (it doesn't exist yet) |
| REQ-lusha-id-staging | ID persists on match; re-enrichment reuses it | unit + integration | Extend `tests/n8n/enrichment.test.mjs`'s `lushaCandidates()` coverage to assert the ID surfaces in candidates/merge output; property existence via `sync_hubspot_properties.py`'s own dry-run diff | ❌ Wave 0 — no existing test asserts ID extraction/staging |
| REQ-lusha-v3-normalize | v3 envelope parses to field-identical candidates | unit | `tests/n8n/enrichment.test.mjs` — add v3 fixture-driven test cases alongside existing v2 ones | ✅ file exists, needs new test cases + new v3 fixtures |
| REQ-lusha-v3-verification | Both suites green; frozen fixture correct; disarmed redeploy clean | integration + manual | Full suite run + `tests/test_companies_factory_frozen.py` (verify, possibly re-baseline) + a redeploy read-back script (mirrors `scripts/rollback_canary_proof.py`'s read-back idiom) | ✅ suite exists; redeploy read-back tooling precedent exists (`deploy_n8n_workflows.py`, `rollback_canary_proof.py`) but no Lusha-URL-specific "zero v2 URLs remain" assertion yet |

### Sampling Rate
- **Per task commit:** the Lusha-scoped subset (`node --test tests/n8n/lushaRequestContract.test.mjs tests/n8n/enrichment.test.mjs` + `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py tests/test_cloud_contacts_branch.py tests/test_check_provider_credits.py -x`)
- **Per wave merge:** full suite (`.venv/bin/python -m pytest && node --test tests/n8n/*.test.mjs`)
- **Phase gate:** full suite green before `/gsd-verify-work`, plus the disarmed redeploy read-back showing zero `v2` Lusha URLs live

### Wave 0 Gaps
- [ ] A new/updated `tests/n8n/lushaRequestContract.test.mjs` (or its v3 rename) pinning the
      v3 contacts request body shape — covers REQ-lusha-v3-request-builders
- [ ] A new test file (or extension) asserting `reveal[]` derivation from
      `gate.missingFields` — covers REQ-lusha-selective-reveal (does not exist today because
      the reveal-derivation logic itself doesn't exist yet)
- [ ] New v3-shaped fixture files under `tests/fixtures/enrichment/` (e.g.
      `lusha_v3_contact.json`, `lusha_v3_company.json`) to drive the new `lushaCandidates()`
      v3 branch tests — covers REQ-lusha-v3-normalize
- [ ] A test asserting `lusha_contact_id`/`lusha_company_id` extraction into candidates/merge
      output — covers REQ-lusha-id-staging
- [ ] Confirm whether `tests/test_companies_factory_frozen.py`'s fixture needs re-baselining
      (diff-based check, not assumed) — covers REQ-lusha-v3-verification
- [ ] A "zero v2 Lusha URLs in the deployed workflow JSON" assertion for the disarmed-redeploy
      read-back step (grep-based check against `n8n/wf_enrichment_cloud.json` post-build,
      mirroring `test_zero_env_or_vars_expressions_in_the_new_gate_topology`'s pattern in
      `tests/test_provider_gate_topology.py`) — covers REQ-lusha-v3-verification's "zero v2
      URLs remaining" criterion

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not user-facing auth; provider API-key auth already handled |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a — internal pipeline, no new access surface |
| V5 Input Validation | yes | Identity fields (email, domain, name) already pass through `normalizeEmailBasic`/`normalizePhoneAU` before use; the new `reveal[]` array should be built from a fixed allow-list (`{email: "emails", mobilephone: "phones"}`), never from raw user/HubSpot input, to avoid injecting an unexpected field name into the Lusha request |
| V6 Cryptography | yes (existing pattern, not new) | `api_key` header stays bound to n8n's `genericCredentialType`/`httpHeaderAuth` credential store on CLOUD, and `$env`-sourced (never printed) on LOCAL-LIVE — same pattern already audited for the v2 calls; do not regress to inlining the key literal in a Code node or log statement |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret key leaking into n8n execution logs via a malformed request debug print | Information Disclosure | Existing pattern already followed: `check_provider_credits.py`'s own docstring states "NEVER prints a secret value" — carry the same discipline into any new debug/probe script for the v3 contract session |
| A 400/401 from a malformed v3 request silently swallowed by `onError: continueRegularOutput`, masking a broken credential or contract (BUG 17 precedent) | Repudiation / (effectively) Denial of Service on data quality | Manual verification of raw HTTP status/body during the live-probe task, not reliance on "the workflow ran" as success evidence |
| Overly broad `reveal[]` derived from unsanitized input, revealing (and billing for) fields never actually needed | Information Disclosure / Elevation of resource consumption | Fixed allow-list mapping (`missingFields` value → reveal string), never a passthrough of arbitrary field names |

## Sources

### Primary (HIGH confidence)
- This repository's own source, read directly in this session: `scripts/build_cloud_workflows.py`,
  `scripts/check_provider_credits.py`, `scripts/provider_registry.py`, `scripts/dryrun_batch.mjs`,
  `n8n/code/normalizeProviders.js`, `n8n/code/enrichmentGate.js`, `config/hubspot_properties.yaml`,
  `config/field_policy.yaml`, `config/provider_priority.yaml`, `scripts/sync_hubspot_properties.py`,
  `tests/n8n/lushaRequestContract.test.mjs`, `tests/n8n/enrichment.test.mjs`,
  `tests/test_cloud_companies_branch.py`, `tests/test_provider_gate_topology.py`,
  `tests/test_check_provider_credits.py`, `tests/test_companies_factory_frozen.py`,
  `tests/fixtures/enrichment/lusha_*.json`.
- User's private memory (this project, verified against code in this session):
  `provider-credit-check-endpoints` (live-curled 2026-07-24 usage-endpoint contract — already
  v3), `measured-provider-match-rates` (live 2026-07-30 credit-burn measurement),
  `lusha-v3-migration-deadline` (prior session's v2/v3 endpoint mapping, itself sourced from
  a WebFetch of the migration guide).

### Secondary (MEDIUM confidence)
- [Lusha API V3: Transition and Migration Guide](https://docs.lusha.com/tutorials/v3-migration-guide) — WebFetch-confirmed endpoint mapping (`GET /v2/person`→`POST /v3/contacts/search-and-enrich`, `GET /v2/company`→`POST /v3/companies/search-and-enrich`); deeper contract fields explicitly absent from this page per the fetch itself.
- [Lusha API Error Codes Reference](https://info.lusha.com/en/articles/634233-lusha-api-error-codes-reference) — WebSearch-summarized error-shape/rate-limit-header claims.

### Tertiary (LOW confidence — WebSearch snippets only, could not be independently fetched/rendered)
- [Lusha API Documentation (enrichment)](https://docs.lusha.com/apis/openapi/enrichment) — WebFetch returned only a page title (JS-rendered SPA); all "reveal[]"/`canReveal`/`has` field-name claims trace back to WebSearch summaries of this and related pages, not a directly rendered page.
- [Prospecting - Search & Enrich](https://docs.lusha.com/apis/openapi/prospecting-search-and-enrich) — a DIFFERENT, out-of-scope product line; flagged in Common Pitfalls to prevent conflation.
- [Company Search & Enrich](https://docs.lusha.com/apis/openapi/company-search-and-enrich) — WebFetch returned only a page title; no company-lane reveal-model details could be confirmed (see Open Questions #1).
- [Get Account Usage Statistics](https://docs.lusha.com/apis/openapi/account-management/getaccountusagestats) — WebFetch returned only a page title; corroborated instead by the repo's own already-v3, live-curled usage-endpoint code (Primary source, above).
- [How to Migrate from API V2 to V3 | Lusha Help Center](https://info.lusha.com/en/articles/680729-how-to-migrate-from-api-v2-to-v3) — WebFetch blocked with HTTP 403.

## Metadata

**Confidence breakdown:**
- Codebase map / call sites / test surface: HIGH — every claim confirmed by direct file reads and grep in this session.
- HubSpot staging property mechanics: HIGH — existing tooling/pattern read directly, additive change with a clear precedent.
- Lusha v3 wire contract (endpoints, body shape, reveal semantics, error shapes): MEDIUM/LOW — `docs.lusha.com` is a JS-rendered SPA that this session's WebFetch tool could not render; findings are WebSearch-snippet-derived and explicitly flagged for the phase's own live-probe requirement to confirm.
- Selective-reveal cost-savings mechanism: MEDIUM — the mechanism (reveal-gated credits) is corroborated by multiple independent WebSearch snippets, but the exact percentage/dollar improvement over the measured 4.65-credits baseline cannot be estimated without a live probe.

**Research date:** 2026-07-30
**Valid until:** 2026-08-13 (14 days) — shorter than the default 30-day window because this
research explicitly defers wire-contract confirmation to a live probe that should happen early
in phase execution; do not let this document's Lusha v3 contract section go stale relative to
that probe's actual findings.
