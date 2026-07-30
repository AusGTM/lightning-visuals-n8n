# Roadmap: v0.6 Claude Plugin Entrypoint

## Overview

v0.6 puts a conversational front door on the n8n backend that v0.2–v0.5 built. The
backend already maps columns, normalizes AU phones, verifies emails, resolves identity,
dedupes and routes create/update — all server-side inside `hubspot/contact-upload`. The
plugin does **not** re-implement any of it. Its job is narrow and sits either side of
that pipe: turn *non-tabular* input into rows over the canonical contact props, show the
operator exactly what will be sent and what it will cost, POST it, and report what
happened to each record.

The journey starts with a walking skeleton — one input shape (a spreadsheet), one lane
(contact-upload), disarmed — so something is demonstrable before any breadth. Then the
other input adapters and the extraction guarantees that make an extracted row
trustworthy. Then the second lane (enrichment on records that already exist) with the
cost guard that keeps a batch from burning provider credits blind. Then outcome
reporting and safe retry.

**Safety posture, inherited and non-negotiable:** every write path in this repo is
disarmed by default and requires a deliberate operator arming step (the two-key gate that
phases 19–22 all follow). The plugin ships disarmed. An approved batch still does not
leave the machine until the operator arms it.

**Phase numbering continues from the archived v0.5 milestone (ended at phase 22), so
phase directories never collide with phases 20–22.**

## Phases

**Phase Numbering:**

- Integer phases (23, 24, …): Planned milestone work
- Decimal phases (23.1, 23.2): Urgent insertions (marked INSERTED)

- [ ] **Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch** - A spreadsheet goes in conversationally, an approved preview goes out to `hubspot/contact-upload`, and nothing sends unless armed
- [ ] **Phase 24: Non-Tabular Input Adapters** - Prose, foreign JSON, and public URLs become canonical rows with provenance — or a named error
- [ ] **Phase 25: Enrichment Lane & Cost Guard** - Existing HubSpot records can be enriched, and no batch launches without a cost estimate and a chunking plan
- [ ] **Phase 26: Outcome Reporting & Safe Retry** - Per-record outcomes replace bare HTTP statuses, and a partial failure is re-sendable without duplicates

## Phase Details

### Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch

**Goal**: An operator can, inside a Claude session, hand the plugin a contact spreadsheet, approve an exact preview of what would be sent, and — only after explicitly arming — have it land in `hubspot/contact-upload`.
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-02, STRUCT-01, PREVIEW-01, PREVIEW-04, DISPATCH-01, DISPATCH-03, PLUGIN-01, PLUGIN-02, PLUGIN-03
**Success Criteria** (what must be TRUE):

  1. The operator invokes the entrypoint conversationally in a Claude session — installed as a plugin, not a hand-run script — and it states up front which endpoint it targets and whether dispatch is currently armed.
  2. Pointing it at a CSV or XLSX with arbitrary, uncleaned headers produces a preview showing the exact body to be sent (canonical contact props only, the shape the existing `Map Columns` node accepts unchanged) and the row count; declining the preview sends nothing and costs nothing.
  3. With arming absent — the default — an *approved* batch is still not sent: the operator is told it is disarmed and exactly how to arm. With arming explicitly present, the same batch POSTs to `hubspot/contact-upload` with header auth and a binary CSV body that the workflow's `Extract From File` node parses, and n8n returns per-row items.
  4. With the endpoint URL or auth secret missing from configuration (which lives outside the plugin source and is never committed), the plugin refuses before any network call and names each missing key rather than failing at the socket.

**Plans**: TBD

### Phase 24: Non-Tabular Input Adapters

**Goal**: Input that is not already a table — pasted prose, a foreign-shaped JSON blob, a public URL — becomes canonical rows the operator can audit and trust, or an error they can act on.
**Depends on**: Phase 23 (reuses its preview/approve/dispatch shell; each adapter feeds the same choke point)
**Requirements**: INGEST-01, INGEST-03, INGEST-05, INGEST-06, STRUCT-02, STRUCT-03, STRUCT-04
**Success Criteria** (what must be TRUE):

  1. Pasting freeform text — an email signature block, a typed list of names and companies — yields rows over the canonical props only, and the preview shows for each row which span of the pasted input produced it.
  2. A JSON array in a shape the alias table has never seen translates into canonical rows, with keys that could not be mapped reported to the operator rather than silently dropped.
  3. A public URL is fetched with the native `web_fetch` tool (honest client, robots.txt respected) and contact/company fields extracted from the page content; a page that yields nothing usable says so instead of producing empty rows.
  4. A field absent from the source stays absent in the row — never inferred, guessed, or filled from the model's own knowledge. A prose entry with no email address does not acquire one.
  5. Rows failing the identity rule (`email` OR `firstname`+`lastname`+`company`) appear in a separate rejected list with a per-row reason and are excluded from the dispatch payload; unreadable, empty, or unsupported input produces a named error, never a silent zero-row success.

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

## v0.6 Progress

**Execution Order:**
Phases execute in numeric order: 23 → 24 → 25 → 26 (walking skeleton first; breadth of
input adapters second; the second lane and its cost guard third; reporting and retry last,
since it reads the outcomes the first three produce)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 23. Walking Skeleton — Plugin Shell & Tabular Dispatch | 0/? | Not started | - |
| 24. Non-Tabular Input Adapters | 0/? | Not started | - |
| 25. Enrichment Lane & Cost Guard | 0/? | Not started | - |
| 26. Outcome Reporting & Safe Retry | 0/? | Not started | - |

## Coverage

24 / 24 v0.6 requirements mapped to exactly one phase each. No orphans, no duplicates.
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
- **Cost rates already measured.** Per-record provider match rates and Lusha credit burn
  (~4.65 credits/reveal under v2; v3 flat ~1cr/contact) plus the Anthropic token probe live
  in the v0.5 artifacts and `scripts/enrichment_cost_ledger.py` /
  `scripts/check_provider_credits.py`. PREVIEW-02 derives from those, it does not re-measure.
- **Out of scope, do not plan phases for:** anti-bot-detection or user-agent spoofing for URL
  ingestion, authenticated/paywalled scraping, company-object ingestion, scheduled/unattended
  runs, and write-back of corrections from the plugin.
