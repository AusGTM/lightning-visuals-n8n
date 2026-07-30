# Requirements — v0.6 Claude Plugin Entrypoint

**Milestone goal:** Give operators a conversational front door to the existing n8n
enrichment backend: accept messy input in whatever shape it arrives, turn it into the
payload the n8n webhooks already expect, preview cost and content before sending, POST
it, and report what actually happened to each record.

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

---

## v0.6 Requirements

### Input adapters (INGEST)

- [ ] **INGEST-01**: Operator can paste freeform text (prose, email signatures, a typed list of
      names/companies) and have contact rows extracted from it
- [ ] **INGEST-02**: Operator can point the plugin at a CSV or XLSX file and have its rows read
      without pre-cleaning the headers
- [ ] **INGEST-03**: Operator can supply already-structured JSON in a foreign shape and have it
      translated to canonical rows
- [ ] **INGEST-04**: Operator can name existing HubSpot records (list, view, or record IDs) to
      enrich, with no row structuring involved
- [ ] **INGEST-05**: Operator can supply a public URL and have contact/company data extracted
      from the page content
- [ ] **INGEST-06**: Operator gets a clear, actionable error when an input is unreadable,
      empty, or unsupported — never a silent drop

### Structuring and validation (STRUCT)

- [ ] **STRUCT-01**: Extracted rows are emitted over the canonical contact props only, so the
      existing n8n `Map Columns` node accepts them unchanged
- [ ] **STRUCT-02**: Rows failing the identity rule (email OR firstname+lastname+company) are
      separated and reported rather than sent
- [ ] **STRUCT-03**: Extraction from unstructured sources records provenance per row (which
      input, which span/URL) so an operator can audit a questionable row
- [ ] **STRUCT-04**: Extraction never invents field values — absent data stays absent

### Preview and cost guard (PREVIEW)

- [ ] **PREVIEW-01**: Operator sees the exact structured payload and row count before anything
      is sent, and must approve it
- [ ] **PREVIEW-02**: Operator sees an estimated provider-credit and Anthropic-token cost for
      the batch before approving, derived from measured per-record rates
- [ ] **PREVIEW-03**: Batches above a configured size are chunked, with the chunking plan shown
      in the preview
- [ ] **PREVIEW-04**: Operator can abort at the preview with nothing sent and no cost incurred
      beyond extraction

### Dispatch (DISPATCH)

- [ ] **DISPATCH-01**: Approved row batches POST to `hubspot/contact-upload` with the correct
      header auth and body encoding
- [ ] **DISPATCH-02**: Enrichment of existing HubSpot records POSTs to `hubspot/enrichment/event`
- [ ] **DISPATCH-03**: Dispatch is disarmed by default — a live send requires an explicit
      operator arming step, consistent with the repo's existing two-key write-gate convention
- [ ] **DISPATCH-04**: A failed or partial dispatch is reported with the failing rows identified,
      and is safe to retry without duplicating already-accepted rows

### Outcome reporting (REPORT)

- [ ] **REPORT-01**: After dispatch, operator sees per-record outcome (accepted, matched,
      created, needs_review, rejected) rather than a bare HTTP status
- [ ] **REPORT-02**: Operator sees enrichment results for dispatched records — at minimum ICP
      tier and needs-review flag — without leaving the session
- [ ] **REPORT-03**: Reporting degrades gracefully when the n8n run is still in flight, showing
      partial state and how to re-check

### Plugin packaging (PLUGIN)

- [ ] **PLUGIN-01**: The entrypoint installs and runs as a Claude plugin, invoked conversationally
      rather than by hand-running a script
- [ ] **PLUGIN-02**: Endpoint URLs, auth secrets, and arming state are configured outside the
      plugin source and are never committed
- [ ] **PLUGIN-03**: The plugin refuses to run against a live endpoint when required configuration
      is missing, with a message naming what is absent

---

## Future Requirements (deferred)

- Company-object ingestion (this milestone is contacts + enrichment triggers only)
- Scheduled/unattended ingestion — the entrypoint is operator-driven by design
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
- Replacing the HubSpot UI as a record-editing surface

## Traceability

Every v0.6 requirement maps to exactly one phase. Coverage: **24 / 24**, no orphans, no
duplicates. Phase numbering continues from the archived v0.5 milestone (ended at 22).

| Requirement | Phase | Status |
| --- | --- | --- |
| INGEST-01 | Phase 24 | Pending |
| INGEST-02 | Phase 23 | Pending |
| INGEST-03 | Phase 24 | Pending |
| INGEST-04 | Phase 25 | Pending |
| INGEST-05 | Phase 24 | Pending |
| INGEST-06 | Phase 24 | Pending |
| STRUCT-01 | Phase 23 | Pending |
| STRUCT-02 | Phase 24 | Pending |
| STRUCT-03 | Phase 24 | Pending |
| STRUCT-04 | Phase 24 | Pending |
| PREVIEW-01 | Phase 23 | Pending |
| PREVIEW-02 | Phase 25 | Pending |
| PREVIEW-03 | Phase 25 | Pending |
| PREVIEW-04 | Phase 23 | Pending |
| DISPATCH-01 | Phase 23 | Pending |
| DISPATCH-02 | Phase 25 | Pending |
| DISPATCH-03 | Phase 23 | Pending |
| DISPATCH-04 | Phase 26 | Pending |
| REPORT-01 | Phase 26 | Pending |
| REPORT-02 | Phase 26 | Pending |
| REPORT-03 | Phase 26 | Pending |
| PLUGIN-01 | Phase 23 | Pending |
| PLUGIN-02 | Phase 23 | Pending |
| PLUGIN-03 | Phase 23 | Pending |

**Per-phase counts:** Phase 23 → 9, Phase 24 → 7, Phase 25 → 4, Phase 26 → 4.

