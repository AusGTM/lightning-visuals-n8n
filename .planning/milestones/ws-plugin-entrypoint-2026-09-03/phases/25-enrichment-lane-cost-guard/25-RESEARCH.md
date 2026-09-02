# Phase 25: Enrichment Lane & Cost Guard - Research

**Researched:** 2026-07-30
**Domain:** n8n webhook envelope extension (list/view resolution), n8n-side credit-only status
endpoint, plugin-local cost rate table, client-side chunked sequential dispatch
**Confidence:** HIGH for the enrichment envelope and credit-probe contracts (read directly from
deployed workflow JSON and admin scripts); MEDIUM for HubSpot Lists API shape (official docs,
not live-probed against this portal); LOW/flagged for "view" resolution and n8n Cloud webhook
timeout numbers (public docs/community posts, not measured in this repo).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Record naming and resolution**
- **D-01:** The plugin **passes the record identifier through verbatim** — record IDs, a list
  name, or a view — and **n8n resolves it** using its existing HubSpot credential. The credential
  boundary holds: exactly one system knows how to talk to HubSpot.
- **D-02:** Consequence the planner must handle: this requires **n8n-side work in the enrichment
  workflow** to expand a list/view identifier into record IDs. It also means the plugin cannot
  show a resolved record count before dispatch for list/view inputs — only for explicit ID lists.
  The preview must say plainly that the count is backend-resolved rather than displaying a
  fabricated number. — Reversibility: costly (a read-only HubSpot token in the client changes the
  credential boundary the whole milestone is built around).

**Provider selection**
- **D-03:** Provider selection has an **admin-config default that is overridable per batch**. The
  committed example config ships with the default set to the **full waterfall**.
- **D-04:** The example config file must **explicitly document the credit-burn implications** of
  that default, and must state that the valid settings are: the full waterfall, a selected cohort
  of providers, or none — and that any of them can be overridden per batch.
- **D-05:** **This amends success criterion 2 of Phase 25**, which currently reads "with no
  selection stated, no provider is enabled and no credits burn." With a full-waterfall default,
  saying nothing enables everything. ROADMAP.md Phase 25 criterion 2 should be reworded before
  this phase is marked complete (second accepted requirement amendment in this milestone; see
  Phase 23 D-05). — Reversibility: reversible.
- **D-06:** Whatever the resolved selection is, the **preview states it explicitly** before
  approval. The operator always sees which providers this batch will use.

**Cost estimation**
- **D-07:** Cost rates live in a **versioned rate table inside the plugin, stamped with the date
  the rates were measured**. Seeded from this repo's measured actuals rather than vendor list
  prices: Lusha flat 1 credit/contact and 2 credits/company with 0 credits for stored-id
  re-enrich, and roughly $0.0686 Anthropic spend per record from the Phase 22 canary.
- **D-08:** The date stamp exists so **staleness is visible rather than silent**.
- **D-09:** Plugin-local, not read from the repo's cost-ledger docs at runtime.
- **D-10:** Remaining balances come from the **n8n-side status endpoint, never from the client
  calling a provider directly**. A balance that cannot be read renders as **"unknown"**, and the
  warning says so rather than assuming headroom. Unknown is never displayed as zero or as healthy.

**Chunking and dispatch**
- **D-11:** The **client splits** oversized batches. The preview shows the chunk count and rows
  per chunk before approval, and dispatch sends exactly that plan.
- **D-12:** Chunks are sent **sequentially**, and a failing chunk is **skipped rather than
  aborting the run**. Remaining chunks continue.
- **D-13:** Failed chunks are **collected and presented back to the operator as a separate
  batch** — a re-sendable unit, not a list of errors. This is the seam Phase 26's safe retry
  (DISPATCH-04) builds on.

### Claude's Discretion
- The chunk size threshold's default value and where it is configured.
- Rate-table file format and how the measurement date is represented.
- Preview layout for the cost block (per-provider breakdown vs single total).
- The envelope details of the enrichment POST beyond what `Parse HubSpot Event` requires.
- How the credit-only status endpoint is shaped internally, provided it returns balances and
  distinguishes "unknown" from a real zero.

### Deferred Ideas (OUT OF SCOPE)
- ROADMAP Phase 25 criterion 2 rewording — required by D-05 before this phase seals.
- Full backend health surface — Phase 27 / STATUS-01..06. This phase builds only the credit
  slice of that endpoint.
- Per-record outcome parsing and retry execution — Phase 26 / REPORT-01, DISPATCH-04.
- Resolved record count for list/view inputs before dispatch — blocked by D-01/D-02.
- Parallel chunk dispatch — rejected for now; sequential-with-skip gives Phase 26 a clean
  failed set.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-04 | Operator can name existing HubSpot records (list, view, or record IDs) to enrich, with no row structuring involved | §"Record identifier envelope" + §"List/view resolution" below give the exact wire shape and the HubSpot API surface (and its gap) n8n-side resolution needs |
| DISPATCH-02 | Enrichment of existing HubSpot records POSTs to `hubspot/enrichment/event` | §"The `hubspot/enrichment/event` envelope" gives the exact accepted body, header, and path, read directly from the deployed workflow's `Parse HubSpot Event` node |
| PREVIEW-02 | Estimated provider-credit and Anthropic-token cost, warns when it exceeds remaining credits from the n8n-side status endpoint; unreadable balance reads "unknown" | §"Rate table seed data" gives measured, dated figures; §"The credit-only status endpoint" gives the exact per-provider probe contract and its unknown-vs-zero shape (already partially built as dangling nodes in the workflow) |
| PREVIEW-03 | Batches above a configured size are chunked, with the plan shown before approval | §"Chunking and sequential dispatch" gives the Cloudflare/n8n-Cloud constraint that bounds a safe chunk size and defines what "failed" must mean |
</phase_requirements>

## Summary

Phase 25 is two backend extensions (n8n) plus one client extension (plugin), all wiring into
infrastructure that already exists in `n8n/wf_enrichment_cloud.json`. The enrichment webhook
(`POST hubspot/enrichment/event`, `X-Enrichment-Secret` header auth) already has a `Parse HubSpot
Event` node with a documented, tested envelope contract — the plugin must match it exactly,
not guess it. That workflow **already contains** per-provider credit-probe nodes (`Lusha Usage`,
`Apollo Usage`, `ZoomInfo Usage Mint`/`Usage`) gated by the same `providers_requested` field used
for the enrichment burn gate — but those nodes are currently dead ends with no path back to
`Respond to Webhook`. Building the credit-only status endpoint is therefore substantially a wiring
task (merge the existing probe outputs into a response), not new integration work, and the exact
per-provider extraction/failure semantics are already implemented twice (`n8n/code/*.js` inline
JS and `scripts/check_provider_credits.py`) — the credit-only endpoint should be a third, thin
port of that same contract, not a new design.

The one real gap is list/view resolution (D-01/D-02). HubSpot's CRM v3 Lists API can resolve a
**list** name to member record IDs, but requires a scope (`crm.lists.read`) not evidenced
anywhere in this repo's current HubSpot credential — this is a likely early blocker the plan
must surface, not assume away. Worse: HubSpot's **saved views** (the per-user filtered table the
operator sees inside the CRM UI) have no documented public API at all; "view" as an accepted
input in D-01 may not be resolvable server-side by any means short of hand-translating it into an
equivalent list or a manual filter definition. This is flagged as an open question the plan should
either scope down (accept list + record IDs; refuse "view" with a clear message pointing at
turning it into a list) or explicitly budget discovery work for.

Cost rates are already measured and dated in this repo (Phase 22 canary, `docs/LUSHA-V3-CONTRACT.md`,
`scripts/enrichment_cost_ledger.py`'s `ESTIMATES` table) — the plugin's rate table is a copy of
those numbers with their existing dates and citations, not a re-measurement. Chunking must
account for a real constraint found in n8n Cloud's own architecture: Cloudflare enforces a
~100-second cap on a webhook's HTTP response, the enrichment workflow has no internal batching
node (every event in a POST runs the full provider-waterfall + Haiku + Sonnet chain within the
same execution before `Respond to Webhook` fires), and n8n's response mode is `responseNode` —
so a chunk with too many records risks a client-side timeout that is not the same thing as a
rejected or failed chunk. The plan must define "failed chunk" (D-12) in a way that does not
conflate "backend still working" with "backend rejected this."

**Primary recommendation:** Treat this phase as three ports of existing, already-implemented
contracts (enrichment envelope, credit probes, measured cost rates) plus one genuinely new piece
of backend work (list resolution) that has a real scope gap to flag early, and one client-side
design decision (chunk size vs. Cloudflare's timeout ceiling) that needs an explicit, conservative
default rather than a guess.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Record identifier passthrough (IDs/list/view name) | Browser/Client (plugin) | — | Plugin only carries the operator's stated identifier verbatim; it never resolves it (D-01) |
| List/view → record ID expansion | API/Backend (n8n) | — | Requires the HubSpot credential the client is forbidden to hold (credential boundary) |
| Provider selection resolution (`providers_requested`) | API/Backend (n8n) | Browser/Client (states default, shows resolved value) | `Parse HubSpot Event`'s `resolveEnabledProviders` already owns this; client only supplies/overrides the `providers` field and displays the result (D-06) |
| Provider credit balance read | API/Backend (n8n) | — | Provider credentials live only in n8n; new `hubspot/backend-status` endpoint is the sole legal path (D-10) |
| Cost estimate computation (credits + USD) | Browser/Client (plugin) | — | Plugin-local rate table (D-07/D-09); no backend round-trip needed to *estimate*, only to read *remaining balance* |
| Batch chunking | Browser/Client (plugin) | — | D-11: client splits, decides chunk count, and controls sequencing |
| Chunk dispatch sequencing + skip-on-fail | Browser/Client (plugin) | API/Backend (processes each chunk's POST independently, no shared state across chunks) | D-12/D-13: client-side loop; backend has no concept of "this chunk belongs to that batch" — statelessness here is what makes skip-and-continue safe |
| Enrichment execution (provider waterfall, Haiku, Sonnet, ICP scoring) | API/Backend (n8n) | — | Out of scope this phase — pre-existing, do not touch |

## Standard Stack

No new runtime dependency is introduced by this phase. The client-side work extends the Phase 23
Python scripts under `operator-claude-plugin/scripts/` (same `requirements.txt`, same HTTP client
choice made in Phase 23); the backend-side work extends existing n8n Code/HTTP Request nodes in
`n8n/wf_enrichment_cloud.json` using the same JS idioms already present (`n8n/code/*.js` inlined
into Code nodes, HTTP Request nodes with `genericCredentialType` auth). No package to install,
therefore no Package Legitimacy Audit table is needed for this phase.

**Installation:** none — this phase adds no new packages to either the plugin or the backend.

## Architecture Patterns

### System Architecture Diagram

```
Operator (chat)
  │  "enrich this list" / "enrich these 40 record IDs"
  ▼
Plugin: resolve identifier type (record IDs | list name | view name)
  │
  ├─ record IDs ──────────────► preview shows exact resolved count
  └─ list/view name ──────────► preview shows "count resolved by backend"
  │
  ▼
Plugin: resolve provider selection
  (explicit override this batch) ?? (admin-config default = full waterfall)
  │
  ▼
Plugin: cost estimate
  rate table (plugin-local, dated) × record count × enabled providers
  │
  ├─► Plugin: query hubspot/backend-status (credit-only slice)
  │     lusha: {configured, credits|null, error}
  │     apollo: {configured, credits|null, error}     (this account: always null, 403)
  │     zoominfo: {configured, credits|null, error}
  │     any credits === null  → display "unknown", never "0"
  │
  ▼
Plugin: preview block
  - resolved/unresolved record count (per D-02)
  - provider selection, stated explicitly (D-06)
  - cost estimate + warning if estimate > known remaining (skip warning if unknown)
  - chunk plan: N chunks × ~rows/chunk
  │
  ▼ operator approves + arms (Phase 23 gate, reused unchanged)
  │
  ▼
Plugin: chunk loop (sequential)
  for each chunk:
    POST hubspot/enrichment/event  { providers: [...], events: [ {objectId, objectType, ...} ] }
      (OR { list: "<name>" } / { view: "<name>" } envelope shape — see Open Questions)
    │
    ├─ 2xx  → chunk accepted, continue
    └─ non-2xx / timeout / malformed → chunk marked failed, continue to next chunk
                                         (do NOT abort remaining chunks — D-12)
  │
  ▼
Plugin: failed chunks collected into one re-sendable batch object (D-13)
  → handed to Phase 26 (not executed by this phase)

n8n side (existing + extended):
  Webhook Trigger (hubspot/enrichment/event, X-Enrichment-Secret)
    → Parse HubSpot Event (resolves provider_enabled, event_id, object_id/type)
    → [NEW] List/view expansion branch (only for list/view envelope; HubSpot Lists API read)
    → provider waterfall → Haiku research → Sonnet judge → merge → HubSpot writes
    → Respond to Webhook (respondWith: allIncomingItems)

  [NEW] hubspot/backend-status (credit-only slice, Phase 25's scope):
    reuses existing dangling nodes: Lusha Usage / Apollo Usage / ZoomInfo Usage(+Mint+Cache)
    → [NEW] merge node → Respond to Webhook
```

### The `hubspot/enrichment/event` envelope — exact contract (read from deployed workflow)

This is not a guess; it is the literal `Parse HubSpot Event` Code node body from
`n8n/wf_enrichment_cloud.json` (`id: c00020000-...`, `n8n-nodes-base.code`, `runOnceForAllItems`).
[VERIFIED: n8n/wf_enrichment_cloud.json — Parse HubSpot Event node source, read directly]

- **Method/path/auth:** `POST /webhook/hubspot/enrichment/event`, `headerAuth`, header name
  `X-Enrichment-Secret` bound to the `LV Enrichment Webhook` credential.
  [VERIFIED: n8n/README.md §"Import to n8n Cloud" item 3, and the `Webhook Trigger` node's own
  `parameters.path`/`authentication` fields]
- **Body shape**, parsed by the inlined `parseWebhookBody(body)`:
  - `body = $json.body ?? $json` — n8n unwraps the webhook body itself; the Code node reads
    whatever arrives at `.body`.
  - If `body` is a **bare array** → `events = body`, no top-level `providers` (per-event only).
  - If `body` is an **object with an `events` array** → `events = body.events`,
    `providers = body.providers` (envelope-level).
  - Otherwise (a **single bare event object**, neither array nor `{events:[...]}`) → treated as
    `events = [body]`; `body.providers` (if present) becomes the envelope-level value.
  - So the plugin should send: `{ "providers": [...], "events": [ {...}, {...} ] }` — the envelope
    form is the only shape that carries one provider selection for a whole chunk without
    repeating it per event.
- **Per-event fields consumed:**
  - `event.objectId` → `object_id` (stringified)
  - `event.objectType` or `event.objectTypeId` → normalized via `normalizeObjectType()`:
    `"contact"|"contacts"|"0-1"` → `"contacts"`; `"company"|"companies"|"0-2"` → `"companies"`;
    anything else → `"unknown"`.
  - `event.subscriptionId`, `event.eventId`, `event.occurredAt` → used only to build a synthetic
    `event_id` string (`${subscriptionId||"sub"}:${objectId}:${eventId||occurredAt}`) — this is
    HubSpot-native-webhook shaped, not something the plugin needs to fabricate meaningfully; any
    stable per-event string works since these values are not used for anything beyond identity
    of the parsed item.
  - `event.propertyName`, `event.subscriptionType`/`event.eventType` → carried through, unused by
    anything that matters for a plugin-originated (non-HubSpot-native) call.
  - **`event.providers`** (or the envelope-level `providers`) is the burn gate. Resolution
    (`resolveEnabledProviders`): `"all"` → every registered provider enabled; an array →
    intersected (case-insensitive) with `["lusha", "apollo", "zoominfo"]`, unknown names dropped;
    **anything else — `"none"`, `""`, `null`, `undefined`, an unrecognized string — enables
    nothing.** There is no third state; D-05's amendment changes only the plugin's own default,
    not this node's behavior — the node still treats an absent/unrecognized value as zero
    providers. The plugin must therefore *always* send an explicit `providers` value (the
    resolved default or the operator's override), never omit the field and rely on a "default"
    the node does not implement.
  - The wrapper also **spreads the raw `event` object onto the output** (`...event`) — a
    "MINIMUM-scope shim" comment in the node explains that `Build Identity`/`Build Company
    Identity` downstream still read direct body fields (e.g. `email`, `domain`) rather than
    fetching the record fresh by `object_id`, for a **direct-field test payload**. On a genuine
    plugin-originated call (object already exists in HubSpot, no direct fields known), this shim
    does nothing useful — the plugin should NOT rely on spreading extra identity fields into the
    event; it should send `objectId`/`objectType` only and trust `object_id` fetch-by-id
    downstream (`HubSpot Fetch By Id` / `HubSpot Company Fetch By Id` nodes exist in the graph).
- **Where a provider selection could be carried:** envelope-level `providers` array (preferred —
  one value for the whole chunk) or per-event `providers` (only useful if a single POST needs to
  mix different provider selections per record, which no CONTEXT decision calls for).
- **Response shape:** `Respond to Webhook` uses `respondWith: "allIncomingItems"` — the HTTP
  response body is whatever items reach that node, which is a `responseMode: "responseNode"`
  passthrough of the final branch's item set. Full parsing of this for per-record outcomes is
  explicitly Phase 26's job (REPORT-01) — Phase 25 only needs to treat a 2xx as "chunk accepted"
  and anything else as "chunk failed" (see "Chunking" below for what "anything else" should
  include).

### List/view resolution — HubSpot API surface (D-01/D-02)

**Lists** have a documented, scoped v3 API [CITED: developers.hubspot.com/docs/api-reference/crm-lists-v3/guide]:
- `GET /crm/v3/lists/object-type-id/{objectTypeId}/name/{listName}` — resolve a list by name to
  its list ID.
- `GET /crm/v3/lists/{listId}/memberships` — returns all member record IDs, ordered by
  `recordId`.
- **Required scope:** `crm.lists.read` (or `crm.lists.write`). [CITED: same guide]

**Saved views** (the per-user filtered table view inside the HubSpot CRM UI, distinct from
Lists) have **no evidenced public API** for resolving a view name/definition to a set of record
IDs. WebSearch across HubSpot's developer docs and community found only UI-facing "create and
manage saved views" knowledge-base articles and an unrelated legacy Analytics `views` endpoint —
no CRM-record "view" resolution endpoint. [ASSUMED — absence of evidence in public docs/community
search, not a confirmed statement from HubSpot that no such API exists; flagged LOW confidence,
not verified against HubSpot support directly]

**Scope gap:** This repo's current HubSpot private-app credential (`LV HubSpot`,
`hubspotAppToken` type, bound via `scripts/provision_n8n_credentials.py`) is documented nowhere in
this repo as holding `crm.lists.read`/`crm.lists.write`. The only scope statement found is
`n8n/README.md`'s "scopes are the CLAUDE.md minimum (`crm.objects.contacts.read`/`.write`)" —
company object scopes are implied by the fact that company writes already work live (Phase 22
canary), but no Lists scope is evidenced anywhere in `n8n/`, `scripts/`, or `CLAUDE.md`.
[VERIFIED: grep of n8n/README.md, scripts/provision_n8n_credentials.py, scripts/deploy_n8n_workflows.py —
no `crm.lists` string found anywhere in the repo] This is a likely early blocker: **the plan
should surface "confirm/grant `crm.lists.read` on the HubSpot private app" as an explicit early
task**, not assume the existing credential already covers it.

**Recommendation for the plan:** Scope D-01's "view" support down to what has an API — accept
record IDs and list names with the standard Lists API resolution; for a "view" input, either (a)
have the plugin ask the operator to name the equivalent list instead (many HubSpot views can be
saved as a list), or (b) budget an explicit discovery spike inside this phase's plan before
committing to a view-resolution design. Building "view" support against an unconfirmed/nonexistent
API is a real risk to the phase's success criteria.

### The credit-only status endpoint (`hubspot/backend-status`) — reuse, not new design

`n8n/wf_enrichment_cloud.json` **already contains** a complete, tested, per-provider credit-probe
side-path, built for a different purpose (Phase 16.1's cost-gate work) and never wired to a
response:

```
Parse HubSpot Event → Credit Request (reads providers_requested)
  → IF Lusha Credit Requested    → Lusha Usage      (GET https://api.lusha.com/v3/account/usage)
  → IF Apollo Credit Requested   → Apollo Usage     (POST https://api.apollo.io/api/v1/usage_stats/api_usage_stats)
  → IF ZoomInfo Credit Requested → ZoomInfo Usage Token Gate → IF Needs Mint
                                    → ZoomInfo Usage Mint → ZoomInfo Usage Cache Token → ZoomInfo Usage
```
[VERIFIED: n8n/wf_enrichment_cloud.json connections graph, traced directly — `Lusha Usage`,
`Apollo Usage`, `ZoomInfo Usage` currently have no outgoing connection; nothing merges their
output back into `Respond to Webhook`]

The exact same per-provider extraction/failure contract is implemented **twice already** and can
be ported a third time with no new design:
1. `n8n/code/providerSelection.js`'s `extractCredits(provider, raw)` (inlined into Code nodes).
2. `scripts/check_provider_credits.py`'s `_extract_lusha`/`_extract_apollo`/`_extract_zoominfo`
   (admin-side CLI, same shapes).
3. `scripts/provider_registry.py`'s `PROVIDER_REGISTRY[...]["credit"]` config (canonical
   endpoint/auth/path per provider).

**Per-provider probe contract** [VERIFIED: scripts/provider_registry.py + scripts/check_provider_credits.py,
cross-checked against docs/LUSHA-V3-CONTRACT.md's live-probe log]:

| Provider | Method | URL | Auth | Success shape | Known failure |
|---|---|---|---|---|---|
| Lusha | GET | `https://api.lusha.com/v3/account/usage` | header `api_key` | `{credits:{total,used,remaining}}` — read `.credits.remaining` | Any non-2xx/malformed → `credits: null`. Balance is **eventually consistent** — an immediate re-read after a spend can under-report for a few seconds [CITED: docs/LUSHA-V3-CONTRACT.md §1] |
| Apollo | POST | `https://api.apollo.io/api/v1/usage_stats/api_usage_stats` | header `X-Api-Key` | top-level numeric `.remaining` (undocumented shape for a master key) | **This repo's key is non-master → confirmed live 403** [VERIFIED: `credits-pre-arming-...json`/`credits-post-canary-...json` snapshots, both `status:403, credits:null`] → must render "unknown", never "0" |
| ZoomInfo | GET (after POST-minted bearer) | `https://api.zoominfo.com/gtm/data/v1/users/usage` | `Authorization: Bearer <token>`, **`Accept: application/vnd.api+json`** (a 406 results without this header) | JSON:API `data[0].attributes.usage[]`; find entry with `limitType === "uniqueIdLimit"`, else first entry with `totalLimit > 0`, read `.usageRemaining` | Token mint failure (POST `https://api.zoominfo.com/gtm/oauth/v1/token`, Basic auth, `grant_type=client_credentials`, no `scope` param — a `scope` param 400s) → no usage GET issued, `credits: null` |

**Live-observed snapshot** (Phase 22 canary, both pre-arming and post-canary reads) confirms this
exact three-state pattern in production: [VERIFIED: `.planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/snapshots/credits-pre-arming-2026-07-30-20260730T085813Z.json`]
```json
{
  "lusha":    {"configured": true, "credits": 3940, "error": null, "status": 200},
  "zoominfo": {"configured": true, "credits": 9301, "error": null, "status": 200},
  "apollo":   {"configured": true, "credits": null, "error": null, "status": 403}
}
```
This `{configured, credits, error, status}` shape (from `scripts/check_provider_credits.py`'s CLI
output plus `scripts/enrichment_cost_ledger.py`'s snapshot format) is a strong candidate for the
credit-only endpoint's response shape — it already distinguishes `configured: false` (no creds at
all), a real number, and `credits: null` (unreadable — must render "unknown"), which is exactly
D-10's requirement.

**Recommendation for the plan:** Build the credit-only endpoint by (1) adding a merge/format Code
node downstream of the three existing (currently dangling) `*Usage` nodes that assembles the
`{lusha:{...}, apollo:{...}, zoominfo:{...}}` object mirroring `check_provider_credits.py`'s
shape, and (2) deciding whether this is a **new Webhook Trigger node in the same workflow file**
at a different path (`hubspot/backend-status`) sharing the existing probe nodes, or a small
separate workflow — either way, no new provider-integration code is needed, only wiring +
response assembly. The existing nodes are unconditionally gated on `providers_requested`, which
was designed for the enrichment-burn use case; the new status endpoint should probe **all three
providers unconditionally** (a status check has no "which providers does this batch use" concept)
rather than reusing the `providers_requested` gate as-is.

### Rate table seed data (D-07) — measured, dated figures to seed the plugin-local table

From `scripts/enrichment_cost_ledger.py`'s `ESTIMATES` dict [VERIFIED: read directly] and
`.planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/22-LEDGER.md` [VERIFIED:
read directly, this is the Phase 22 canary's live-fired report]:

| Rate | Value | Measured/cited | Confidence |
|---|---|---|---|
| Lusha, first-time contact enrich | 1 credit/contact | `docs/LUSHA-V3-CONTRACT.md` §7-8, live 2026-07-30 probe | measured |
| Lusha, company match | 2 credits/company | `docs/LUSHA-V3-CONTRACT.md` §5, live 2026-07-30 probe | measured |
| Lusha, stored-id re-enrich | 0 credits/contact | `docs/LUSHA-V3-CONTRACT.md` §8, 4/4 live calls billed 0 | measured |
| ZoomInfo, per match | 1.08 credits/match | 22-RESEARCH.md Assumption A3 — v2-era measurement, carried forward (no ZoomInfo pricing change this milestone) | inferred, pre-v3 |
| Apollo, per match | unknown | this account's key is non-master, live 403 on usage endpoint | unknown — no committed figure exists |
| Anthropic (Haiku research model) input | $1.00/MTok | `.planning/milestones/v0.3-phases/14-judge-wiring/RESEARCH.md` | measured (WebSearch-sourced against Anthropic's catalog) |
| Anthropic (Haiku research model) output | $5.00/MTok | same | measured |
| Anthropic (Sonnet judge) input | $2.00/MTok (intro, thru 2026-08-31; $3.00 standard after) | same | measured, **time-bound — re-check after 2026-08-31** |
| Anthropic (Sonnet judge) output | $10.00/MTok (intro, thru 2026-08-31; $15.00 standard after) | same | measured, **time-bound — re-check after 2026-08-31** |
| **Anthropic spend, actual observed per record** | **$0.068624 USD/record** | Phase 22 canary, executions 332 & 337, both 2026-07-30, ≈$0.068/record consistent across both fires | measured — matches CONTEXT D-07's "roughly $0.0686" figure exactly |
| Provider credits, actual observed per record (this canary) | 0 credits (lusha, zoominfo) — repeat-identity record, nothing newly billed | same executions | measured, but **not representative of a first-time enrich** — the canary hit an already-enriched record, so its 0-credit observation does not override the `docs/LUSHA-V3-CONTRACT.md` first-time rates above |

**D-09 reminder for the plan:** these citations (file paths under `.planning/` and `docs/`) are
for **seeding the plugin's rate table at planning/implementation time only**. The rate table
itself, once written into `operator-claude-plugin/`, must be a self-contained plugin-local file
(JSON/YAML — Claude's discretion on format) carrying the numeric values, the measurement date
(2026-07-30 for all rows above), and a short citation string — not a runtime file read of any
`docs/` or `.planning/` path. `.planning/` directories are demonstrably unstable (this exact
milestone's own `MEMORY.md` records a same-day restructuring of planning directories breaking a
runtime coupling) — copy the numbers in, don't reference the path.

### Chunking and sequential dispatch (D-11/D-12/D-13) — what bounds chunk size, what "failed" must mean

- n8n Cloud's webhook responses are constrained by an underlying Cloudflare proxy to roughly
  **100 seconds** before the connection is cut, independent of n8n's own configurable execution
  timeout. [CITED: n8n community forum posts describing "Webhook cut off after 100s on n8n Cloud
  (Cloudflare timeout)" — this is community-sourced, not an official n8n Cloud SLA document, so
  treat the exact number as approximate, not contractual] This is not a bespoke concern for
  ordinary webhooks in this repo — it becomes relevant here specifically because `responseMode`
  is `responseNode`, meaning the HTTP client (the plugin) is held open until `Respond to Webhook`
  fires at the end of the whole per-item chain.
- The enrichment workflow has **no `Split In Batches` node** — confirmed by direct inspection of
  `wf_enrichment_cloud.json`'s node list. [VERIFIED] Every item emitted by `Parse HubSpot Event`
  flows through the full provider-waterfall → Haiku research → Sonnet judge → merge → HubSpot
  write chain within the same execution, so the wall-clock cost of the whole POST scales
  proportionally with the number of records in it (times however many of those steps are
  provider/LLM round-trips per record, which are themselves seconds each).
- **Consequence for chunk size:** the plan should pick a conservative default (small enough that
  even a worst-case per-record path — full waterfall + web research + judge escalation — has a
  low chance of exceeding the ~100s ceiling for the whole chunk) rather than an arbitrary round
  number. This is Claude's discretion per CONTEXT, but the research finding constrains the
  reasoning: a default in the low single digits to ~10 records/chunk is far safer than a "sounds
  fine" number like 50 or 100, given each record can trigger multiple sequential external API
  calls server-side.
- **What "failed chunk" must mean (for D-12's skip condition to be unambiguous):** the plan
  should define at least these as failure:
  - Non-2xx HTTP status from the POST.
  - A client-side network/timeout error (including — importantly — a Cloudflare-imposed
    connection cut around the ~100s mark; this is a timeout, not a rejection, and the backend may
    still be processing or may have already written some records when the client sees it).
  - A malformed/non-JSON response body where a JSON body was expected.
  The plan should **not** attempt to distinguish "backend rejected this chunk" from "backend
  timed out while still working" at this phase — that distinction (and safe re-send without
  duplication) is explicitly Phase 26's job (DISPATCH-04). Phase 25 only needs "chunk did not
  complete cleanly" as its failure signal, and the collected failed-chunk batch (D-13) is handed
  forward as-is.
- n8n Cloud does not impose a documented artificial cross-request concurrency cap that this
  research surfaced; the constraint that matters here is the per-request Cloudflare response
  ceiling described above, not a rate limit on the count of sequential requests. Sequential
  dispatch (D-12, already locked) sidesteps any such concern regardless.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-provider credit extraction/failure handling | A new parser per provider in the plugin or in the new endpoint | Port `scripts/check_provider_credits.py`'s three extractor functions (or the n8n-side `extractCredits` in `n8n/code/providerSelection.js`) verbatim | Both are already live-validated against each provider's actual response shape (200/403/406 cases); a fresh implementation risks silently deviating from the confirmed contract |
| Enrichment envelope parsing | Reverse-engineering the POST shape from the HubSpot native webhook format | Match `Parse HubSpot Event`'s actual `parseWebhookBody`/`resolveEnabledProviders` contract exactly (documented above) | The node is deployed and live; a plugin payload that almost matches will silently resolve to "no providers enabled" (the node's safe-default fallback) rather than erroring loudly |
| List/view → record ID expansion | A client-side HubSpot API call | n8n-side, using the HubSpot credential already bound there, via the CRM v3 Lists API | Credential boundary (D-01) — the plugin holding a read-only HubSpot token to do this itself defeats the entire architecture this milestone is built around |
| Cost rate sourcing | Estimating credit/token costs from vendor list prices | The already-measured, dated figures in `scripts/enrichment_cost_ledger.py`'s `ESTIMATES` and the Phase 22 canary ledger | CONTEXT D-07 explicitly locks this: seeded from measured actuals, not list prices |

**Key insight:** almost everything this phase needs on the backend side already exists in
`wf_enrichment_cloud.json` in some form (envelope parsing, provider-selection gate, per-provider
credit probes) — the actual net-new backend work is smaller than "build a status endpoint" and
"extend the enrichment workflow" suggest; it's mostly wiring dangling nodes to a response and
adding one new resolution branch (list expansion) that doesn't exist anywhere yet.

## Common Pitfalls

### Pitfall 1: Treating "providers" as optional or defaulted client-side only
**What goes wrong:** The plugin resolves a default provider selection in its own config and
assumes it doesn't need to send `providers` explicitly if the default applies.
**Why it happens:** D-03's "admin-config default that is overridable per batch" sounds like the
backend has its own default too.
**How to avoid:** `Parse HubSpot Event` has no server-side default — an absent/unrecognized
`providers` value always resolves to "no providers enabled" (documented above). The plugin must
compute the effective value (override ?? config default) and **always** send it explicitly in
every POST.
**Warning signs:** A batch that silently enriches nothing despite the operator believing the
default (full waterfall) applied.

### Pitfall 2: Confusing "list" (Lists API, real) with "view" (no known public API)
**What goes wrong:** Planning treats "list, view, or record IDs" as three symmetric input types
with equivalent backend resolution paths.
**Why it happens:** CONTEXT D-01/INGEST-04 name both in the same breath; they are not
architecturally equivalent.
**How to avoid:** Confirm before committing task scope whether "view" resolution is truly
achievable server-side (see Open Questions) — do not build a design that silently degrades to
"treat a view name as if it were a list name" without telling the operator that happened.
**Warning signs:** A "view" name that happens to collide with an unrelated list name producing a
wrong record set with no error.

### Pitfall 3: A credit-balance read reporting `null`/absent as `0`
**What goes wrong:** A naive merge of the three provider probe responses renders a missing
`credits` field as `0` (e.g. via a default-value fallback in a template or a `|| 0` in code).
**Why it happens:** `0` is a very natural default for "number I couldn't get."
**How to avoid:** Every provider probe result must carry a tri-state (`configured: false` /
`credits: <number>` / `credits: null`), and the client-side warning logic must branch explicitly
on `null` → "unknown, cannot compare to estimate" rather than `0 < estimate` → false alarm or
`0 >= estimate` (impossible, since 0 is never >= a positive estimate) → false "insufficient
credits" alarm. This is D-10's exact concern and it already has a live-observed real case
(Apollo, 403, always `null` for this account).
**Warning signs:** The preview claims "0 Apollo credits remaining" instead of "Apollo balance
unknown (credential/scope issue — ask an admin)".

### Pitfall 4: Chunk-size default chosen without regard to the Cloudflare/response-node interaction
**What goes wrong:** A chunk size is picked for "reasonable batch size" reasons (e.g. matching
Phase 23's ≤20-row preview threshold) without checking that the *dispatch* path (not just the
*preview* path) has a different constraint — the enrichment POST holds the connection open until
the full per-item chain completes, unlike the contact-upload POST.
**Why it happens:** Phase 23's preview-rendering threshold (≤20 rows shows every row) is an
unrelated, purely cosmetic threshold; it's easy to reuse the same number for a materially
different concern (network timeout risk).
**How to avoid:** Size the enrichment chunk default around the ~100s Cloudflare ceiling and the
observed multi-second-per-record cost of the full provider+LLM chain (Phase 22's canary: two
records' worth of Haiku+Sonnet calls alone took multiple seconds each, before providers).
**Warning signs:** Chunks intermittently "fail" (client sees a timeout) with no HTTP status at
all, and retrying the identical chunk sometimes succeeds — a classic timeout-not-rejection
symptom.

## Code Examples

### Enrichment envelope the plugin must send (derived from the live `Parse HubSpot Event` contract)
```json
// Source: n8n/wf_enrichment_cloud.json — Parse HubSpot Event node, parseWebhookBody/
// resolveEnabledProviders (read directly, this is not a template — field names and behavior
// match the deployed node exactly)
{
  "providers": ["zoominfo", "apollo", "lusha"],
  "events": [
    { "objectId": "789", "objectType": "companies" },
    { "objectId": "790", "objectType": "companies" }
  ]
}
```
`"providers"` may also be `"all"` (every registered provider) or `[]`/`"none"` (no providers —
credits are never burned, only status/ICP-recompute-relevant fields are touched). An absent
`providers` key is equivalent to `"none"` — never omit it and assume a default applies server-side.

### Existing per-provider credit extraction to port for the status endpoint
```python
# Source: scripts/check_provider_credits.py (read directly — already live-validated shapes)
def _extract_lusha(raw):
    if not isinstance(raw, dict):
        return None
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return None
    remaining = credits.get("remaining")
    return remaining if isinstance(remaining, (int, float)) and not isinstance(remaining, bool) else None

# Apollo: this account's key is non-master -> always 403 -> always None (live-confirmed,
# credits-pre-arming-2026-07-30-*.json and credits-post-canary-*.json both show status:403).

# ZoomInfo: requires "Accept: application/vnd.api+json" on the usage GET or it 406s.
# Balance lives at data[0].attributes.usage[limitType="uniqueIdLimit"].usageRemaining.
```

### List resolution endpoints to wire n8n-side (subject to the crm.lists.read scope gap above)
```text
# Source: developers.hubspot.com/docs/api-reference/crm-lists-v3/guide [CITED]
GET /crm/v3/lists/object-type-id/{objectTypeId}/name/{listName}   -> resolve list name to listId
GET /crm/v3/lists/{listId}/memberships                            -> record IDs, ordered by recordId
# Required scope: crm.lists.read (or crm.lists.write) — NOT evidenced as granted in this repo's
# current HubSpot private-app credential.
```

## State of the Art

Not applicable in the usual sense — this phase does not introduce a new technology generation;
it ports contracts that were already built (Phase 16.1's provider-selection/credit-probe work,
Phase 20/22's Lusha v3 migration and canary) into a new surface (the plugin + a new endpoint).
The one "old vs current" distinction worth naming: Lusha v2's bundled-credit pricing (~4.65
credits/reveal, referenced in this repo's own memory notes) is superseded by v3's flat
1cr/contact, 2cr/company, 0cr stored-id-reuse pricing — the rate table must use the v3 figures
(already what D-07 locks), never the v2 figures still floating around in older `.planning/`
documents from before the migration.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot "saved views" have no public API to resolve a view name/definition to record IDs | List/view resolution | If a view-resolution API does exist and was simply not surfaced by public WebSearch, the plan may unnecessarily scope down or spike-budget something that was actually straightforward — low cost if wrong (worst case: extra discovery time), high cost if the plan proceeds assuming an API exists and it does not (a phase success criterion goes unmet) |
| A2 | The current HubSpot private-app credential lacks `crm.lists.read`/`crm.lists.write` scope | List/view resolution | If the scope already exists (undocumented in this repo), the plan may include an unnecessary "grant scope" task; if it's actually missing and the plan skips verifying it, list resolution silently 403s at execution time |
| A3 | n8n Cloud's webhook response ceiling is ~100 seconds (Cloudflare-imposed) | Chunking and sequential dispatch | This number is community-forum-sourced, not from n8n's own SLA docs, and could vary by plan tier or have changed; if the real ceiling is meaningfully different, the recommended conservative chunk-size default could be either too conservative (wasted round-trips) or not conservative enough (occasional Cloudflare timeouts even at the chosen default) |
| A4 | The three existing `*Usage` probe nodes in `wf_enrichment_cloud.json` are safe to reuse unconditionally (probe all three providers, not gated by `providers_requested`) for the new status endpoint | The credit-only status endpoint | If reusing them unconditionally has an unintended side effect (e.g. rate-limiting from an unconditional probe on every status check), the plan should verify with a live low-volume test before assuming it's free |

**If this table is empty:** N/A — see rows above; all four should be confirmed or explicitly
accepted as residual risk before/while planning tasks around them.

## Open Questions

1. **Can HubSpot "views" actually be resolved to record IDs by any documented mechanism?**
   - What we know: Lists (a related but distinct concept) have a full, scoped v3 API. Public
     WebSearch/WebFetch found no equivalent for saved CRM views.
   - What's unclear: Whether an undocumented/internal endpoint exists that HubSpot's own UI uses
     internally, and whether relying on it would be supportable long-term even if found.
   - Recommendation: Scope INGEST-04's "view" support down to "list name and record IDs only" for
     this phase unless a follow-up spike inside the plan confirms a real API, and have the
     refusal message for a "view" input explicitly suggest saving it as a list instead.

2. **Does the current HubSpot private-app credential already carry `crm.lists.read`?**
   - What we know: No document in this repo states the full scope list currently granted; only
     the CLAUDE.md-quoted minimum (`crm.objects.contacts.read`/`.write`) is explicitly named, and
     companies read/write is implied by working company writes.
   - What's unclear: Whether an admin has already broadened the scope beyond what's documented,
     or whether it needs a fresh grant + credential re-provisioning before list resolution can be
     built and tested.
   - Recommendation: Make "confirm/grant `crm.lists.read` scope on the HubSpot private app" an
     early, cheap-to-verify task in the plan (a single live `GET
     /crm/v3/lists/object-type-id/{objectTypeId}/name/{listName}` call against a real list name
     will 403 immediately if the scope is missing) rather than discovering it mid-implementation.

3. **What chunk-size default is actually safe against the ~100s ceiling, empirically?**
   - What we know: No `Split In Batches` node exists, so wall-clock cost scales with chunk size
     times per-record chain latency (multi-second per record, per the Phase 22 canary's own
     token/timing data).
   - What's unclear: The real observed wall-clock time for N records through the full chain in
     one execution — this repo's canary evidence is for single-record fires, not a batch.
   - Recommendation: The plan should either pick a deliberately small conservative default (e.g.
     low single digits) or budget a small live timing test (fire N=5, N=10 through a
     `providers: []` no-op-ish path or a real waterfall path against test records) before locking
     the shipped default.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud instance, `wf_enrichment_cloud.json` deployed | DISPATCH-02, credit endpoint | ✓ (documented live-deployed per n8n/README.md "Live state 2026-07-29") | — | — |
| HubSpot private-app credential (`LV HubSpot`) bound in n8n | List/view resolution, all enrichment writes | ✓ (in use, per canary evidence) but **scope for Lists API unconfirmed** | — | Confirm/grant `crm.lists.read` before building list resolution (Open Question 2) |
| Lusha/Apollo/ZoomInfo credentials bound in n8n | Credit-only status endpoint | ✓ (all three `configured: true` in Phase 22 credit snapshots) | — | Apollo's key is non-master and will always read "unknown" — expected, not a defect to fix here |
| `operator-claude-plugin/` Python runtime (from Phase 23) | Client-side chunking/cost-estimate logic | Not yet built — Phase 23 has not executed in this branch (only README/CHANGELOG exist) | — | This phase's plan should assume Phase 23's scripts exist by the time Phase 25 executes (per ROADMAP dependency), not build around their absence |

**Missing dependencies with no fallback:** none identified — the one real gap (Lists API scope)
has a fallback (confirm/grant before building).

**Missing dependencies with fallback:** Lists API scope (grant before use); Apollo credit read
(always renders "unknown", by design, not a blocker).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (Python/backend logic + plugin scripts) | pytest (existing repo convention — `tests/test_check_provider_credits.py`, `tests/test_enrichment_cost_ledger.py` etc. already mock live calls, no framework install needed) |
| Framework (n8n inline JS Code-node logic) | Node's built-in `node --test`, existing convention (`tests/n8n/*.test.mjs`, e.g. `tests/n8n/enrichmentGate.test.mjs` already tests the sibling `providerSelection.js`-style gate logic) |
| Config file | none dedicated — `pytest.ini`/equivalent already exists repo-root per prior phases; `tests/n8n/*.test.mjs` run via `node --test tests/n8n/*.test.mjs` per this repo's documented convention (see MEMORY.md "Test suite run commands") |
| Quick run command | `.venv/bin/python -m pytest tests/test_check_provider_credits.py -x` (existing file to extend/mirror for the new status-endpoint port); `node --test tests/n8n/<new-file>.test.mjs` for any new n8n-side JS logic |
| Full suite command | `.venv/bin/python -m pytest` + `node --test tests/n8n/*.test.mjs` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-04 | Record-ID envelope passes through verbatim; list/view envelope carries identifier, not resolved rows | unit (plugin) | `pytest tests/test_<new plugin envelope builder>.py -x` | ❌ Wave 0 — new plugin test file |
| DISPATCH-02 | Enrichment POST body matches `Parse HubSpot Event`'s accepted shape exactly (providers + events array) | unit (plugin, mocking HTTP) + existing n8n test | `pytest tests/test_<new plugin dispatch>.py -x`; existing `node --test tests/n8n/enrichmentGate.test.mjs` already covers the resolver this envelope must match | Plugin test ❌ Wave 0; n8n-side resolver test ✅ exists |
| PREVIEW-02 | Cost estimate computed from rate table; unknown balance renders "unknown", never "0"; warning fires only when a real (non-null) balance is below estimate | unit (plugin) | `pytest tests/test_<new cost estimate>.py -x` | ❌ Wave 0 |
| PREVIEW-02 (backend) | Credit-only status endpoint returns `{provider: {configured, credits, error}}` for all three providers, distinguishing null from zero | unit (n8n Code node logic, mirroring `tests/test_check_provider_credits.py`'s mocked-response pattern) | `pytest tests/test_<new status endpoint format>.py -x` (mocked, mirrors existing `_extract_*` tests) | ❌ Wave 0 (mirrors existing test file, not built from scratch) |
| PREVIEW-03 | Chunk plan (count, rows/chunk) computed correctly for boundary cases (exact multiple, remainder, single record) | unit (plugin) | `pytest tests/test_<new chunking>.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant new/extended pytest file(s) above, plus `node --test
  tests/n8n/<touched file>.test.mjs` for any n8n Code-node JS change.
- **Per wave merge:** full `pytest` + `node --test tests/n8n/*.test.mjs`.
- **Phase gate:** full suite green before `/gsd-verify-work`, plus a live (or live-mocked, if no
  armed window is available) exercise of the new `hubspot/backend-status` path against at least
  one real 403 (Apollo) and one real 200 (Lusha/ZoomInfo) to confirm the null-vs-zero distinction
  survives the new endpoint's own response assembly — this is the one behavior no unit test can
  fully substitute for, since the existing snapshots already prove the *probe* behavior; only a
  live call proves the *new endpoint's wiring* preserves it.

### Wave 0 Gaps
- [ ] `tests/test_<enrichment envelope builder>.py` — covers DISPATCH-02/INGEST-04 (plugin-side
      envelope construction)
- [ ] `tests/test_<cost estimate + rate table>.py` — covers PREVIEW-02 (plugin-side)
- [ ] `tests/test_<credit-only status response shape>.py` — covers PREVIEW-02 (n8n-side, mirrors
      `tests/test_check_provider_credits.py`'s mocking pattern)
- [ ] `tests/test_<chunking>.py` — covers PREVIEW-03
- [ ] No new test framework install needed — pytest and `node --test` are both already present
      and already used for structurally identical logic in this repo.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing `X-Enrichment-Secret` header-auth credential (`LV Enrichment Webhook`), reused unchanged; the new `hubspot/backend-status` endpoint should be gated by the same or an equivalent header-auth n8n credential — never left unauthenticated just because it's "read-only" |
| V3 Session Management | no | No session concept in this phase — the plugin's arming state is conversation-scoped per Phase 23's design, unaffected here |
| V4 Access Control | yes | The credential boundary itself (D-01/D-10): the plugin must never be given a HubSpot or provider credential capable of more than what the two documented endpoints (`hubspot/enrichment/event`, `hubspot/backend-status`) already expose |
| V5 Input Validation | yes | The `providers` field and record-identifier fields must be validated client-side before POST (reject malformed/empty identifier lists rather than sending a POST that the backend will silently interpret as "no providers"/no events) |
| V6 Cryptography | no | No new cryptographic surface introduced; existing HTTPS + header-secret pattern is reused |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Silent no-op enrichment (an empty/malformed `providers` value silently enabling nothing) | Repudiation (operator believes a batch ran when it didn't) | Client-side validation that `providers` is always one of `"all"` / a non-empty known-provider array / an explicit empty selection the operator confirmed meant "no providers" — never send an unset/ambiguous value |
| Credential leakage via the new status endpoint's error messages | Information Disclosure | The endpoint must return only `{configured, credits, error, status}`-shaped data (numbers/booleans/short error labels) — never the raw provider response body, which could carry account identifiers or other account metadata beyond a credit figure |
| Chunk-retry duplicate writes (not this phase's job, but a boundary this phase creates) | Tampering (unintended double-enrichment/double-cost) | Out of scope for Phase 25's own success criteria (D-13 only requires collecting the failed batch); flag for Phase 26 that DISPATCH-04 must not simply "retry the same POST" without a duplicate-safety mechanism |

## Sources

### Primary (HIGH confidence)
- `n8n/wf_enrichment_cloud.json` — `Parse HubSpot Event`, `Credit Request`, `IF * Credit
  Requested`, `Lusha Usage`/`Apollo Usage`/`ZoomInfo Usage*`, `Webhook Trigger`, `Respond to
  Webhook` nodes and the full connections graph — read and traced directly.
- `scripts/check_provider_credits.py`, `scripts/provider_registry.py` — read in full.
- `scripts/enrichment_cost_ledger.py` — `ESTIMATES` table read directly.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md`,
  `23-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md` — read in full.
- `.planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/22-LEDGER.md` and its
  `snapshots/credits-*.json` files — read directly, live-fired evidence.
- `n8n/README.md` §"Import to n8n Cloud" — webhook path/auth header, deploy conventions.
- `docs/LUSHA-V3-CONTRACT.md` — credit figures and the eventually-consistent balance caveat.

### Secondary (MEDIUM confidence)
- [HubSpot CRM Lists API guide](https://developers.hubspot.com/docs/api-reference/crm-lists-v3/guide) —
  endpoint shapes and required scopes for list-by-name and membership resolution.

### Tertiary (LOW confidence)
- n8n community forum posts on Cloudflare's ~100-second webhook response ceiling on n8n Cloud —
  not an official n8n Cloud SLA document.
- WebSearch results on HubSpot "saved views" API — absence of evidence, not confirmation of
  absence; flagged as Assumption A1 / Open Question 1.

## Metadata

**Confidence breakdown:**
- Enrichment envelope contract: HIGH — read directly from the deployed workflow's source code,
  not inferred.
- Credit-probe contract: HIGH — read directly, cross-checked against three independent
  implementations (n8n JS, admin Python script, live-observed snapshots) that all agree.
- List/view resolution: MEDIUM (Lists API) / LOW (views) — Lists API is officially documented;
  view resolution is an absence-of-evidence finding, and the scope-grant status of this repo's
  credential is unconfirmed either way.
- Chunking/timeout constraint: MEDIUM — the underlying architectural fact (no batching node,
  `responseNode` mode) is HIGH confidence (read directly); the specific ~100s number is LOW
  confidence (community-sourced).

**Research date:** 2026-07-30
**Valid until:** 30 days for the n8n/HubSpot API surface claims (stable APIs, low churn risk);
re-check the Anthropic Sonnet judge pricing rows specifically before 2026-08-31 (intro pricing
expiry already noted in the source ledger itself).
