# Roadmap: v0.6 Claude Plugin Entrypoint

## Overview

v0.6 makes Claude the **only** interface to the n8n backend that v0.2–v0.5 built: both the
ingestion front door and the control panel. The operator is non-technical, works in Claude
Desktop, and never opens n8n — so anything n8n would show in its own UI (failed executions,
dead credentials, exhausted quotas, stuck locks, review queues) has to arrive here instead,
and anything an admin would do with a script has to be either doable in the conversation or
plainly named as someone else's job. "Run this command" is never an acceptable answer to the
operator.

The ingestion half is deliberately narrow, because the backend already maps columns, normalizes AU phones, verifies emails, resolves identity,
dedupes and routes create/update — all server-side inside `hubspot/contact-upload`. The
plugin does **not** re-implement any of it. Its job is narrow and sits either side of
that pipe: turn *non-tabular* input into rows over the canonical contact props, show the
operator exactly what will be sent and what it will cost, POST it, and report what
happened to each record.

The control-plane half is additive, not a replacement: phases 27–30 layer read, control,
notice, and triage over the same plugin shell.

The journey starts with a walking skeleton — one input shape (a spreadsheet), one lane
(contact-upload), disarmed — so something is demonstrable before any breadth. Then the
other input adapters and the extraction guarantees that make an extracted row
trustworthy. Then the second lane (enrichment on records that already exist) with the
cost guard that keeps a batch from burning provider credits blind. Then outcome
reporting and safe retry.

**Safety posture, inherited and non-negotiable:** every write path in this repo is
disarmed by default and requires a deliberate operator arming step (the two-key gate that
phases 19–22 all follow). The plugin ships disarmed. An approved batch still does not
leave the machine until the operator enables live writes — and that permission is
**conversation-scoped**: it lapses when the session ends and is never inherited. Because the
operator cannot run a command, the plugin performs the arming write itself, restricted to an
allowlist and verified by read-back (Phase 28). That is a real widening of what the plugin may
do to n8n, and the allowlist plus the confirm-and-verify loop is what keeps it bounded.

**Phase numbering continues from the archived v0.5 milestone (ended at phase 22), so
phase directories never collide with phases 20–22.**

## Phases

**Phase Numbering:**

- Integer phases (23, 24, …): Planned milestone work
- Decimal phases (23.1, 23.2): Urgent insertions (marked INSERTED)

- [ ] **Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch** - A spreadsheet goes in conversationally, an approved preview goes out to `hubspot/contact-upload`, and nothing sends unless armed
- [ ] **Phase 24: Non-Tabular Input Adapters** - Prose, foreign JSON, public URLs, and web-page screenshots become canonical rows with provenance — or a named error
- [ ] **Phase 25: Enrichment Lane & Cost Guard** - Existing HubSpot records can be enriched, and no batch launches without a cost estimate and a chunking plan
- [ ] **Phase 26: Outcome Reporting & Safe Retry** - Per-record outcomes replace bare HTTP statuses, and a partial failure is re-sendable without duplicates
- [ ] **Phase 27: Backend Status Surface** - An n8n-side health endpoint plus a plain-language read of what the backend is doing, in text or as a dashboard
- [ ] **Phase 28: Control Actions** - Run it, turn it on and off, reschedule it, and enable live writes for one conversation — all confirmed and read-back verified
- [ ] **Phase 29: Notices & Unattended Sweep** - Runs report themselves when they settle, and a sweep speaks up when something needs a human while nobody is watching
- [ ] **Phase 30: Review-Queue Triage** - Conflicts get resolved conversationally, with the decision written back as a human decision

## Phase Details

### Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch

**Goal**: An operator can, inside a Claude session, hand the plugin a contact spreadsheet, approve an exact preview of what would be sent, and — only after explicitly arming — have it land in `hubspot/contact-upload`.
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-02, STRUCT-01, PREVIEW-01, PREVIEW-04, DISPATCH-01, DISPATCH-03, PLUGIN-01, PLUGIN-02, PLUGIN-03, PLUGIN-04
**Success Criteria** (what must be TRUE):

  1. The operator invokes the entrypoint conversationally in a Claude session — installed as a plugin, not a hand-run script — and it states up front which endpoint it targets and whether dispatch is currently armed.
  2. Pointing it at a CSV or XLSX with arbitrary, uncleaned headers produces a preview showing the exact body to be sent (canonical contact props only, the shape the existing `Map Columns` node accepts unchanged) and the row count; declining the preview sends nothing and costs nothing.
  3. With live writes off — the default — an *approved* batch is still not sent: the operator is told plainly that sending is off and how to turn it on for this conversation. With it on, the same batch POSTs to `hubspot/contact-upload` with header auth and a binary CSV body that the workflow's `Extract From File` node parses, and n8n returns per-row items.
  4. Every file the client adds lives under `operator-claude-plugin/`, with its own README and CHANGELOG, and no backend file is modified to make the client work — the client is replaceable without touching `n8n/`, `config/`, or the enrichment `src/` modules.
  5. With the endpoint URL or auth secret missing from admin-provisioned configuration (which lives outside the plugin source and is never committed), the plugin refuses before any network call and says in plain language what is not configured and who can fix it — the operator is never shown a key, asked to paste one, or left staring at a socket error.

**Plans**: TBD

### Phase 24: Non-Tabular Input Adapters

**Goal**: Input that is not already a table — pasted prose, a foreign-shaped JSON blob, a public URL, a screenshot of a web page — becomes canonical rows the operator can audit and trust, or an error they can act on.
**Depends on**: Phase 23 (reuses its preview/approve/dispatch shell; each adapter feeds the same choke point)
**Requirements**: INGEST-01, INGEST-03, INGEST-05, INGEST-06, INGEST-07, STRUCT-02, STRUCT-03, STRUCT-04
**Success Criteria** (what must be TRUE):

  1. Pasting freeform text — an email signature block, a typed list of names and companies — yields rows over the canonical props only, and the preview shows for each row which span of the pasted input produced it.
  2. A JSON array in a shape the alias table has never seen translates into canonical rows, with keys that could not be mapped reported to the operator rather than silently dropped.
  3. A public URL is fetched with the native `web_fetch` tool (honest client, robots.txt respected) and contact/company fields extracted from the page content; a page that yields nothing usable says so instead of producing empty rows.
  4. One or more screenshots of a web page — a speaker list, a staff directory, a search-results page the operator captured themselves — yield canonical rows, with each row's provenance naming the image it came from and where on it. Multiple screenshots of one page (a scrolled sequence) are read as a single source without duplicating rows that appear in the overlap.
  5. A field absent from the source stays absent in the row — never inferred, guessed, or filled from the model's own knowledge. A prose entry with no email address does not acquire one, and a screenshot value the image renders ambiguously (truncated, cut off, unreadable glyph) is surfaced for operator confirmation rather than completed by guessing.
  6. Rows failing the identity rule (`email` OR `firstname`+`lastname`+`company`) appear in a separate rejected list with a per-row reason and are excluded from the dispatch payload; unreadable, empty, or unsupported input produces a named error, never a silent zero-row success.

**Plans**: TBD

### Phase 25: Enrichment Lane & Cost Guard

**Goal**: An operator can trigger enrichment on records that already exist in HubSpot, and cannot launch a batch on either lane without first seeing what it will cost and how it will be split.
**Depends on**: Phase 23 (dispatch shell and arming gate); sequenced after Phase 24 so the cost guard covers every input path that can produce a batch
**Requirements**: INGEST-04, DISPATCH-02, PREVIEW-02, PREVIEW-03
**Success Criteria** (what must be TRUE):

  1. Naming existing HubSpot records — record IDs, a list, or a view — produces an enrichment request with no row structuring involved, previewed and approved through the same gate as any other batch.
  2. An approved enrichment POSTs to `hubspot/enrichment/event` with header auth in the envelope shape `Parse HubSpot Event` accepts, carrying an explicit provider selection; with no selection stated, no provider is enabled and no credits burn.
  3. Every preview — both lanes — shows an estimated provider-credit and Anthropic-token cost for the batch, derived from the repo's measured per-record rates rather than a guess, and warns when the estimate exceeds the credits actually remaining.
  4. A batch above the configured size limit is shown in the preview already split — chunk count and rows per chunk — before approval, and dispatch sends exactly that plan.

**Plans**: TBD

### Phase 26: Outcome Reporting & Safe Retry

**Goal**: After a send, the operator can see what happened to each individual record and can re-send only the part that did not land.
**Depends on**: Phase 25 (both lanes must dispatch before their outcomes can be parsed; retry safety needs the per-record outcome to identify what to re-send)
**Requirements**: REPORT-01, REPORT-02, REPORT-03, DISPATCH-04
**Success Criteria** (what must be TRUE):

  1. After a contact-upload dispatch the operator sees a per-record outcome — created, updated/matched, needs_review, or rejected with its reason — instead of a bare HTTP status.
  2. After an enrichment dispatch the operator sees, per record and without leaving the session, at minimum the ICP tier and the needs-review flag, alongside remaining provider credits.
  3. When the n8n run is still in flight or the response came back partial, the report says so explicitly, shows the state it does know, and tells the operator how to re-check — it never presents an incomplete run as a finished one.
  4. A failed or partially-failed dispatch names the specific rows that did not land, and re-sending exactly those rows does not create duplicates of records the earlier attempt already accepted.

**Plans**: TBD

### Phase 27: Backend Status Surface

**Goal**: The operator can ask what the backend is doing and get a truthful, plain-language answer — without ever opening n8n, and without the plugin holding a provider credential.
**Depends on**: Phase 25 (which builds the first, credit-only slice of the n8n status endpoint for its cost guard; this phase generalizes that endpoint into full health)
**Requirements**: STATUS-01, STATUS-02, STATUS-03, STATUS-04, STATUS-05, STATUS-06
**Success Criteria** (what must be TRUE):

  1. Asking "what's the backend doing?" returns, per workflow: on or off, whether live writes are currently enabled, when it last ran and whether that run succeeded, and what is in flight — read from the n8n API, not asserted from local config.
  2. A failed execution is reported by cause in plain language — expired credential, rate limit, exhausted quota, malformed record — and names whether the operator or an admin can fix it. No status codes, no stack traces, no "check the n8n UI".
  3. Provider credit balances and remaining headroom reach the operator through the n8n-side status endpoint. The plugin never holds a provider or HubSpot credential, and a provider whose balance cannot be read (Apollo's key is not master — it 403s) shows as unknown, never as zero or healthy.
  4. Stuck locks, records queued but never processed, and the review backlog are surfaced with counts, so a silently wedged backend is visible without anyone thinking to look.
  5. Status is conversational text by default; on request a dashboard Artifact carries the same data stamped with its fetch time, and refreshing re-publishes to the same URL rather than minting a second one.

**Plans**: TBD

### Phase 28: Control Actions

**Goal**: The operator can operate the backend — start it, stop it, reschedule it, allow it to write — entirely from the conversation, with every mutation confirmed in advance and verified after.
**Depends on**: Phase 27 (nothing may be flipped that cannot first be read; every mutation's confirmation and read-back verification is built on that read surface)
**Requirements**: CONTROL-01, CONTROL-02, CONTROL-03, CONTROL-04, CONTROL-05, CONTROL-06, CONTROL-07
**Success Criteria** (what must be TRUE):

  1. The operator can start either ingestion lane or run a scheduled scan off-cycle, and is told the run started and how its outcome will come back — no scripts, no terminal, no n8n UI.
  2. The operator can turn a workflow on or off, and enable, disable, or re-time a scheduled job in plain terms ("check every 15 minutes" → "hourly") — cron syntax never appears.
  3. The operator can enable live writes for the current conversation only. It lapses when the conversation ends, is never inherited by a later session, and every status readout states plainly whether it is currently on.
  4. Every mutation states its consequence before it happens ("this lets enrichment overwrite company fields in HubSpot"), shows what will change, and waits for explicit confirmation. The mutation set is allowlisted — write-safety flag overlay, Schedule Trigger cadence, workflow active state — and any other workflow-JSON change is refused rather than attempted.
  5. After every mutation the plugin re-reads the backend and reports verified or failed. A `200` from n8n is never reported as success on its own, and the inverse action is stated at the moment the change lands.

**Plans**: TBD

### Phase 29: Notices & Unattended Sweep

**Goal**: The operator learns that something needs them without having to think to ask — during a session, and while no session is open.
**Depends on**: Phase 28 (a notice is only actionable if the fix is reachable from the conversation; the sweep's messages point at the controls Phase 28 exposes)
**Requirements**: NOTICE-01, NOTICE-02, NOTICE-03, NOTICE-04, NOTICE-05
**Success Criteria** (what must be TRUE):

  1. After a dispatch the plugin keeps watching and reports back unprompted when the run settles, with per-record outcomes and the cost actually incurred — the operator does not have to ask twice.
  2. The watch is bounded, and a run still unsettled at the bound is reported as still running with how to re-check. It never simply stops talking.
  3. A sweep running with no session open pushes a notification when something needs a human: a failed scheduled run, a credential or auth failure, an exhausted quota, a stuck lock, or a review backlog past its threshold.
  4. The sweep is silent when the backend is healthy, and each notice it does send states whether the operator or an admin can act on it.
  5. The sweep is read-only by construction: it burns no provider credits, enables no writes, dispatches nothing. A sweep that fires while live writes are off changes nothing about that.

**Plans**: TBD

### Phase 30: Review-Queue Triage

**Goal**: Records the backend flagged for human judgment get that judgment in the conversation, and the CRM records that a person decided.
**Depends on**: Phase 28 (reuses the confirm-then-verify gate machinery for a second, distinct write path) and Phase 27 (the queue is surfaced there before it can be worked here)
**Requirements**: REVIEW-01, REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05
**Success Criteria** (what must be TRUE):

  1. The queue lists each record's conflict in plain language — the competing values, which source said what, evidence links, and a link to the HubSpot record — so a non-technical operator can actually adjudicate it.
  2. Resolving a review conversationally writes the decision back, honoring the existing field-policy ownership classes: a `manual_protected` value is never overwritten by a review decision, and the non-clobber policy is not re-implemented here.
  3. Review writeback is gated by its own session-scoped confirmation, separate from dispatch arming. Ungated, it shows the exact property write it would make and makes none.
  4. Every decision stamps human source, timestamp, and the operator's stated reason into the existing source-metadata fields, so the audit trail distinguishes a person's call from a model's.
  5. Rejecting a record records the reason and leaves it in the queue. Review flags are never silently cleared, and a record never leaves the queue without a recorded decision.

**Plans**: TBD

## v0.6 Progress

**Execution Order:**
Phases execute in numeric order: 23 → 24 → 25 → 26 → 27 → 28 → 29 → 30.

The first four build the ingestion front door (skeleton, input breadth, second lane + cost
guard, outcome reporting). The last four build the control plane on top of it: read the
backend truthfully, then operate it, then have it speak up unprompted, then work the queue it
surfaces. Read before write, and write before unattended — a notice is only worth sending if
the operator can act on it without leaving the conversation.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 23. Walking Skeleton — Plugin Shell & Tabular Dispatch | 0/? | Not started | - |
| 24. Non-Tabular Input Adapters | 0/? | Not started | - |
| 25. Enrichment Lane & Cost Guard | 0/? | Not started | - |
| 26. Outcome Reporting & Safe Retry | 0/? | Not started | - |
| 27. Backend Status Surface | 0/? | Not started | - |
| 28. Control Actions | 0/? | Not started | - |
| 29. Notices & Unattended Sweep | 0/? | Not started | - |
| 30. Review-Queue Triage | 0/? | Not started | - |

## Coverage

48 / 48 v0.6 requirements mapped to exactly one phase each. No orphans, no duplicates.
Traceability table lives in `REQUIREMENTS.md`.

## Notes for Planning

- **Do not rebuild the backend.** Column mapping, phone/email normalization, verification,
  identity resolution, dedupe and create/update routing are n8n-side and stay there. The
  plugin's only mapping responsibility is producing canonical-prop rows from *non-tabular*
  sources; tabular input passes through to the existing `Map Columns` node.
- **XLSX is not a wire format.** `Extract From File` on the contact-upload workflow runs
  `operation: csv`, so an XLSX input has to be read locally and sent as CSV bytes.
  `src/file_loader.py` already reads CSV/TSV/JSON/XLSX into `list[dict]` — reuse it rather
  than adding a parser.
- **The `providers` field is the burn gate.** `Parse HubSpot Event` treats an absent or
  unrecognized `providers` value as *no providers enabled*. Any enrichment payload the
  plugin builds must set it explicitly and deliberately.
- **Response-shape risk for REPORT-01.** `hubspot/contact-upload` uses
  `responseMode: lastNode` across a branching graph (`HubSpot Update` / `HubSpot Create` /
  `Set Review`), so the HTTP response may not carry every row's outcome. Phase 26 planning
  should verify what actually comes back before assuming a complete per-record ledger is
  available from the response alone; the n8n executions API (already used by
  `scripts/enrichment_cost_ledger.py`) is the fallback source.
- **The client is a separate implementation living in `operator-claude-plugin/`.** Backend
  directories (`n8n/`, `config/`, `scripts/`, and the enrichment modules in `src/`) are not this
  milestone's to edit — the one exception is the new n8n-side status endpoint, which is backend
  work and belongs in `n8n/`. The client talks to the backend over the documented HTTP contract
  only, never by importing enrichment logic, so a Slack bot or web app can replace it later
  without a backend change. `src/file_loader.py` reuse is a co-location convenience (file reading
  is client-side work, not backend logic) and is documented as such — not a licence to import
  merge policy, scoring, or provider code.
- **The plugin holds no provider credentials.** ZoomInfo/Apollo/Lusha and HubSpot creds live in
  n8n, managed by an admin there. So `scripts/check_provider_credits.py`'s direct-to-provider
  reads are an *admin* tool, not a model for the plugin. Credit balances reach the operator
  through a new n8n-side status endpoint. Phase 25 builds the credit-only slice it needs for
  PREVIEW-02; Phase 27 generalizes the same endpoint to full health. Plan them as one endpoint
  grown twice, not two endpoints.
- **Arming is a workflow write, not a runtime setting.** `ALLOW_*` write gates are compiled into
  the workflows' Code nodes by `deploy_n8n_workflows.py` via the `ENABLE_BAKED_FLAGS` overlay,
  and schedule cadence lives in Schedule Trigger parameters — both mean `PUT /api/v1/workflows/{id}`.
  Phase 28 therefore performs a real workflow write, restricted to that allowlist and nothing
  else. `enable_baked_flags()` already fails closed on a flag that did not land; reuse it rather
  than hand-rolling the rewrite. Note the standing constraint: agent tooling in this repo is
  blocked from performing arming writes, so Phase 28's armed path needs a human in the loop to
  execute and verify even though the operator-facing design is a yes/no in chat.
- **Session-scoped arming is the plugin's own state, not n8n's.** n8n's baked flag is persistent
  by nature; the conversation-scoped permission lives in the plugin and gates whether it will
  use it. Both states must appear in status (CONTROL-04, STATUS-01) — "n8n allows writes" and
  "I am willing to write right now" are different facts and conflating them is how a silent
  live send happens.
- **Cost rates already measured.** Per-record provider match rates and Lusha credit burn
  (~4.65 credits/reveal under v2; v3 flat ~1cr/contact) plus the Anthropic token probe live
  in the v0.5 artifacts and `scripts/enrichment_cost_ledger.py` /
  `scripts/check_provider_credits.py`. PREVIEW-02 derives from those, it does not re-measure.
- **Screenshots arrive as attachments, not captures.** INGEST-07 reads images the operator
  hands over in-session; the plugin drives no browser and logs into nothing. Planning must not
  reach for browser automation here — that would recreate the scraping path this milestone
  excludes. Extraction is a vision read on the attached image; the confidence signal it needs
  is "is this glyph legible", not "is this fact true".
- **Out of scope, do not plan phases for:** anti-bot-detection or user-agent spoofing for URL
  ingestion, authenticated/paywalled scraping, automated screenshot capture, company-object
  ingestion, scheduled/unattended runs, and write-back of corrections from the plugin.
