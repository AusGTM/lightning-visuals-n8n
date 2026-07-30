# Requirements — v0.6 Claude Plugin Entrypoint

**Milestone goal:** Give operators a conversational front door **and control plane** for the
existing n8n enrichment backend. Two jobs, one surface:

1. **Ingestion front door** — accept messy input in whatever shape it arrives, turn it into the
   payload the n8n webhooks already expect, preview cost and content before sending, POST it,
   and report what actually happened to each record.

2. **Control plane** — run, observe, schedule, and gate the backend from the conversation.
   Anything n8n would surface in its own UI (failed executions, credential errors, exhausted
   quotas, stuck locks, records awaiting review) surfaces here instead.

**The operator is non-technical and never opens n8n.** They work in Claude Desktop, not a
terminal. They will not run a command, edit a config file, or handle a secret. Any instruction
of the form "run this script" is a failed requirement, not a workaround: if the plugin cannot
do a thing itself, it must say so in plain language and name the person who can. n8n's UI,
this repo's scripts, and the operator runbooks are **admin** surfaces, not operator ones.

## Scope anchor — what already exists (do NOT rebuild)

The `hubspot/contact-upload` n8n workflow already performs, server-side:

- **Column mapping** — `Map Columns` node, alias table mirroring `config/column_mapping.yaml`
  (arbitrary source headers → canonical props; unmapped columns dropped)

- **Phone normalization** — `Normalize Phone`, AU-only heuristic, null → review
- **Email normalization + verification** — `Build Verify Batch` / `Verify Emails (batch)` /
  `Apply Email` against the rapid-email-verifier API

- **Identity resolution, dedupe, create/update routing** — `HubSpot Search by Email`,
  `Resolve Identity`, `Merge Contacts`, `Decide Action`, write gates

Canonical contact props: `email, firstname, lastname, jobtitle, linkedin_url, phone, company`.
Identity rule: `email` OR (`firstname` + `lastname` + `company`).

**Therefore the plugin's structuring job is narrow:** produce well-formed tabular rows over
those canonical props from inputs that are *not already tabular*. Tabular inputs pass through
to the existing mapper. Duplicating mapping/normalization/verification in the plugin is
explicitly out of scope — it would fork a second source of truth.

## Endpoints (targets)

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `hubspot/contact-upload` | POST | headerAuth | Net-new / bulk rows, binary CSV body |
| `hubspot/enrichment/event` | POST | headerAuth | Trigger enrichment on existing HubSpot records |
| `/api/v1/workflows`, `/api/v1/executions` | GET | `X-N8N-API-KEY` | Read workflow/run state (same client as `scripts/deploy_n8n_workflows.py`) |
| `/api/v1/workflows/{id}/activate`, `/deactivate` | POST | `X-N8N-API-KEY` | Turn a workflow on/off — no JSON write |
| `/api/v1/workflows/{id}` | PUT | `X-N8N-API-KEY` | **Allowlisted mutations only** — write-safety flag overlay, Schedule Trigger cadence |
| `hubspot/backend-status` (new) | POST | headerAuth | n8n-side health: provider credit balances, queue counts, credential state |

**Credential boundary.** Provider (ZoomInfo / Apollo / Lusha) and HubSpot credentials live in
n8n and are managed there by an admin. The plugin holds only the n8n base URL, an n8n API key,
and the webhook auth secret. It therefore **cannot** read provider credits directly the way
`scripts/check_provider_credits.py` does — those come back through the n8n-side status endpoint
above. This is why that endpoint has to exist.

---

## v0.6 Requirements

### Input adapters (INGEST)

- [ ] **INGEST-01**: Operator can paste freeform text (prose, email signatures, a typed list of
      names/companies) and have contact rows extracted from it

- [x] **INGEST-02**: Operator can point the plugin at a CSV or XLSX file and have its rows read
      without pre-cleaning the headers

- [ ] **INGEST-03**: Operator can supply already-structured JSON in a foreign shape and have it
      translated to canonical rows

- [ ] **INGEST-04**: Operator can name existing HubSpot records (list, view, or record IDs) to
      enrich, with no row structuring involved

- [ ] **INGEST-05**: Operator can supply a public URL and have contact/company data extracted
      from the page content

- [ ] **INGEST-06**: Operator gets a clear, actionable error when an input is unreadable,
      empty, or unsupported — never a silent drop

- [ ] **INGEST-07**: Operator can supply screenshots of a web page (one or many) and have
      contact/company rows extracted from the rendered image, under the same provenance and
      no-invention guarantees as text sources. Screenshots are operator-supplied only — the
      plugin never automates capture

### Structuring and validation (STRUCT)

- [x] **STRUCT-01**: Extracted rows are emitted over the canonical contact props only, so the
      existing n8n `Map Columns` node accepts them unchanged

- [ ] **STRUCT-02**: Rows failing the identity rule (email OR firstname+lastname+company) are
      separated and reported rather than sent

- [ ] **STRUCT-03**: Extraction from unstructured sources records provenance per row (which
      input, which span/URL) so an operator can audit a questionable row

- [ ] **STRUCT-04**: Extraction never invents field values — absent data stays absent. A value
      the source renders ambiguously (truncated text, an unreadable character in a screenshot)
      is flagged for operator confirmation, not resolved by guessing

### Preview and cost guard (PREVIEW)

- [x] **PREVIEW-01**: Operator sees the exact structured payload and row count before anything
      is sent, and must approve it

- [ ] **PREVIEW-02**: Operator sees an estimated provider-credit and Anthropic-token cost for
      the batch before approving, derived from measured per-record rates, and is warned when the
      estimate exceeds remaining credits — balances sourced from the n8n-side status endpoint,
      never by the client calling a provider directly

- [ ] **PREVIEW-03**: Batches above a configured size are chunked, with the chunking plan shown
      in the preview

- [x] **PREVIEW-04**: Operator can abort at the preview with nothing sent and no cost incurred
      beyond extraction

### Dispatch (DISPATCH)

- [x] **DISPATCH-01**: Approved row batches POST to `hubspot/contact-upload` with the correct
      header auth and body encoding

- [ ] **DISPATCH-02**: Enrichment of existing HubSpot records POSTs to `hubspot/enrichment/event`
- [x] **DISPATCH-03**: Dispatch is disarmed by default — a live send requires the operator to
      explicitly enable live writes, consistent with the repo's two-key write-gate convention.
      That permission is conversation-scoped (see CONTROL-04) and granted in chat, never by
      running a command

- [ ] **DISPATCH-04**: A failed or partial dispatch is reported with the failing rows identified,
      and is safe to retry without duplicating already-accepted rows

### Outcome reporting (REPORT)

- [ ] **REPORT-01**: After dispatch, operator sees per-record outcome (accepted, matched,
      created, needs_review, rejected) rather than a bare HTTP status

- [ ] **REPORT-02**: Operator sees enrichment results for dispatched records — at minimum ICP
      tier and needs-review flag — without leaving the session, with remaining credits taken from
      the enrichment response or the n8n-side status endpoint

- [ ] **REPORT-03**: Reporting degrades gracefully when the n8n run is still in flight, showing
      partial state and how to re-check

### Backend status and observability (STATUS)

- [ ] **STATUS-01**: Operator can ask what the backend is doing and get one plain-language
      answer — per workflow: on or off, whether live writes are currently enabled, when it last
      ran and whether that run succeeded, and anything in flight right now

- [ ] **STATUS-02**: A failed run is reported with its real cause translated into plain language
      (expired credential, rate limit, exhausted quota, malformed record) and states whether the
      operator or an admin can fix it — never a bare status code or stack trace

- [ ] **STATUS-03**: Provider credit balances and remaining headroom are visible to the operator,
      retrieved through the n8n-side status endpoint rather than by the plugin holding provider
      credentials

- [ ] **STATUS-04**: Runtime states that need a human are surfaced with counts: wedged runs (an
      execution still in `status = running` past a configured threshold, read from the n8n
      executions API), records queued but never processed, and records awaiting review.
      *Amended per 27-CONTEXT.md D-07a/D-07b/D-07d: the original wording
      (`enrichment_status = running` past `enrichment_lock_until`) is unbuildable — that property
      does not exist in this portal's schema, and nothing in the pipeline ever writes the `running`
      status value. "Queued" is a bare count; no request timestamp is stored, so it can never be
      age-based (D-07c). Third accepted requirement amendment in this milestone.*

- [ ] **STATUS-05**: Status appears as conversational text by default; on request the plugin
      publishes a dashboard Artifact carrying the same data, stamped with when it was fetched,
      and re-publishes to the same URL on refresh

- [ ] **STATUS-06**: Data the backend cannot supply is shown as explicitly unknown, never as zero
      or healthy — a provider whose balance endpoint refuses access reads "unknown", not "0"

### Backend control actions (CONTROL)

- [ ] **CONTROL-01**: Operator can start a run now — either ingestion lane, or a scheduled scan
      off-cycle — and is told it started and how its outcome will reach them

- [ ] **CONTROL-02**: Operator can turn a workflow on or off
- [ ] **CONTROL-03**: Operator can enable or disable a scheduled job and change its cadence,
      expressed in plain terms ("check every 15 minutes" → "hourly"), not cron syntax

- [ ] **CONTROL-04**: Operator can enable live writes for the current conversation only. The
      permission lapses when the conversation ends and is never inherited by a later session;
      status always states whether it is currently on

- [ ] **CONTROL-05**: Every backend-mutating action states its consequence in plain language,
      shows what will change, and requires explicit confirmation. Mutations are restricted to an
      allowlist — write-safety flag overlay, schedule cadence, workflow active state — and any
      other workflow-JSON change is refused

- [ ] **CONTROL-06**: After any mutation the plugin re-reads the backend and reports verified or
      failed. A `200` alone is never reported as success

- [ ] **CONTROL-07**: Every mutation is reversible in one step, and the plugin states how to
      reverse it at the moment it is applied

### Notices and unattended monitoring (NOTICE)

- [ ] **NOTICE-01**: After a dispatch, the plugin keeps watching until the run settles and reports
      back unprompted with per-record outcomes and the cost actually incurred

- [ ] **NOTICE-02**: The in-session watch is bounded; a run that has not settled by then is
      reported as still running with how to re-check — the watch never simply goes quiet

- [ ] **NOTICE-03**: A scheduled sweep runs with no session open and pushes a notification when
      something needs a human: failed scheduled runs, credential or auth failure, exhausted
      quota, stuck locks, or a review backlog over a configured threshold

- [ ] **NOTICE-04**: The sweep is silent when the backend is healthy, and every notice it does
      send states whether the operator or an admin can act on it

- [ ] **NOTICE-05**: The sweep is read-only by construction — it burns no provider credits, enables
      no writes, and dispatches nothing

### Review-queue triage (REVIEW)

- [ ] **REVIEW-01**: Operator sees the needs-review queue with each record's conflict in plain
      language: the competing values, which source said what, evidence links, and a link to the
      HubSpot record

- [ ] **REVIEW-02**: Operator can resolve a review conversationally and the plugin writes the
      decision back, honoring the existing field-policy ownership classes — a `manual_protected`
      value is never overwritten by a review decision

- [ ] **REVIEW-03**: Review writeback is gated by its own session-scoped confirmation, separate
      from dispatch arming; while ungated it shows exactly what it would write and writes nothing

- [ ] **REVIEW-04**: Every review decision stamps human source, timestamp, and the operator's
      stated reason into the existing source-metadata fields, so the audit trail shows a person
      decided it

- [ ] **REVIEW-05**: Rejecting a record records the rejection reason and leaves it in the queue —
      review flags are never silently cleared

### Plugin packaging (PLUGIN)

- [x] **PLUGIN-01**: The entrypoint installs and runs as a Claude plugin, invoked conversationally
      rather than by hand-running a script

- [x] **PLUGIN-02**: Endpoint URL and webhook secret live in a plugin-local config file that is
      never committed. The operator performs setup once, copying the tracked example file and
      filling in the two values obtained from the n8n admin. Nothing is committed, the plugin
      never displays a secret back or asks for one in the conversation, and provider and HubSpot
      credentials stay in n8n entirely (amended per D-05, `23-CONTEXT.md`, from the original
      admin-provisioned wording)

- [x] **PLUGIN-03**: The plugin refuses to run against a live endpoint when required configuration
      is missing or rejected, naming in plain language what is broken and who can fix it, and
      stating what still works — a dead provider credential does not present as total failure

- [x] **PLUGIN-04**: All client code lives under `operator-claude-plugin/`, carries its own README
      and CHANGELOG, and touches no backend file. It reaches the backend only over the documented
      HTTP contract, so it can be replaced by a different front end without backend changes

---

## Future Requirements (deferred)

- Company-object ingestion (this milestone is contacts + enrichment triggers only)
- Unattended *ingestion* — the sweep (NOTICE-03) watches and reports, but never dispatches a
  batch on its own; sending stays operator-initiated by design

- Write-back of corrections from the plugin into HubSpot
- Non-AU phone handling (blocked on the existing AU-only normalizer, tracked upstream)

## Out of Scope (explicit exclusions)

- **Re-implementing column mapping, phone/email normalization, verification, or dedupe** —
  these live in n8n and must stay single-source-of-truth

- **User-agent obfuscation, viewport emulation, or any anti-bot-detection technique for URL
  ingestion.** URL support fetches public pages with an honest client and respects robots.txt.
  LinkedIn profile data is obtained through the licensed provider waterfall (ZoomInfo, Apollo,
  Lusha), which already returns LinkedIn URLs and profile fields, not by scraping the site.

- Authenticated or paywalled page scraping
- **Arbitrary workflow deployment from the plugin.** Mutations are allowlisted (CONTROL-05).
  Editing nodes, credentials, or workflow structure stays an admin task run from this repo —
  the plugin is a control panel over the deployed backend, not a deploy pipeline

- **Operator-run commands, scripts, or config files.** If the plugin cannot do it, it names who
  can. Terminal instructions to the operator are a requirement failure

- **Automated screenshot capture.** INGEST-07 reads images the operator already has and hands
  over; the plugin does not drive a browser, log in, or capture pages itself. A screenshot is
  not a route around the scraping exclusions above — LinkedIn profile fields still come from
  the licensed provider waterfall, not from a picture of the page

- Replacing the HubSpot UI as a record-editing surface

## Traceability

Every v0.6 requirement maps to exactly one phase. Coverage: **49 / 49**, no orphans, no
duplicates. Phase numbering continues from the archived v0.5 milestone (ended at 22).

| Requirement | Phase | Status |
| --- | --- | --- |
| INGEST-01 | Phase 24 | Pending |
| INGEST-02 | Phase 23 | Complete |
| INGEST-03 | Phase 24 | Pending |
| INGEST-04 | Phase 25 | Pending |
| INGEST-05 | Phase 24 | Pending |
| INGEST-06 | Phase 24 | Pending |
| INGEST-07 | Phase 24 | Pending |
| STRUCT-01 | Phase 23 | Complete |
| STRUCT-02 | Phase 24 | Pending |
| STRUCT-03 | Phase 24 | Pending |
| STRUCT-04 | Phase 24 | Pending |
| PREVIEW-01 | Phase 23 | Complete |
| PREVIEW-02 | Phase 25 | Pending |
| PREVIEW-03 | Phase 25 | Pending |
| PREVIEW-04 | Phase 23 | Complete |
| DISPATCH-01 | Phase 23 | Complete |
| DISPATCH-02 | Phase 25 | Pending |
| DISPATCH-03 | Phase 23 | Complete |
| DISPATCH-04 | Phase 26 | Pending |
| REPORT-01 | Phase 26 | Pending |
| REPORT-02 | Phase 26 | Pending |
| REPORT-03 | Phase 26 | Pending |
| STATUS-01 | Phase 27 | Pending |
| STATUS-02 | Phase 27 | Pending |
| STATUS-03 | Phase 27 | Pending |
| STATUS-04 | Phase 27 | Pending |
| STATUS-05 | Phase 27 | Pending |
| STATUS-06 | Phase 27 | Pending |
| CONTROL-01 | Phase 28 | Pending |
| CONTROL-02 | Phase 28 | Pending |
| CONTROL-03 | Phase 28 | Pending |
| CONTROL-04 | Phase 28 | Pending |
| CONTROL-05 | Phase 28 | Pending |
| CONTROL-06 | Phase 28 | Pending |
| CONTROL-07 | Phase 28 | Pending |
| NOTICE-01 | Phase 29 | Pending |
| NOTICE-02 | Phase 29 | Pending |
| NOTICE-03 | Phase 29 | Pending |
| NOTICE-04 | Phase 29 | Pending |
| NOTICE-05 | Phase 29 | Pending |
| REVIEW-01 | Phase 30 | Pending |
| REVIEW-02 | Phase 30 | Pending |
| REVIEW-03 | Phase 30 | Pending |
| REVIEW-04 | Phase 30 | Pending |
| REVIEW-05 | Phase 30 | Pending |
| PLUGIN-01 | Phase 23 | Complete |
| PLUGIN-02 | Phase 23 | Complete |
| PLUGIN-03 | Phase 23 | Complete |
| PLUGIN-04 | Phase 23 | Complete |

**Per-phase counts:** Phase 23 → 10, Phase 24 → 8, Phase 25 → 4, Phase 26 → 4, Phase 27 → 6,
Phase 28 → 7, Phase 29 → 5, Phase 30 → 5.
