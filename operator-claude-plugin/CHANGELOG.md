# Changelog — Operator Claude Plugin

Changes to **this client only**. Backend changes (n8n workflows, enrichment logic, HubSpot
schema, provider adapters) are recorded in the repository-root `CHANGELOG.md`.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
client is versioned independently of the backend — it is one of potentially several front ends
over the same n8n system, so its version says nothing about backend capability.

## [Unreleased]

### Added

- Directory established as the home for the operator-facing client, separate from the n8n
  backend. README states the position explicitly: this is a suggested default thin client, not
  the interface — the backend is reachable over plain HTTP and other front ends (Slack, web app,
  CLI, scheduled script) can be built against the same contract, concurrently.
- Documented client contract: the two ingestion webhooks, the new `hubspot/backend-status`
  health endpoint, and the n8n Public API surfaces for read, activate/deactivate, and
  allowlisted workflow mutation — plus a five-point checklist of what a replacement client must
  reimplement.
- Documented operator model (non-technical, Claude Desktop, no terminal, no secrets), safety
  posture (disarmed by default, conversation-scoped live-write permission, confirm-then-verify
  on every mutation, read-only unattended monitoring), and cost posture (previewed estimates
  from measured rates, warn against remaining credits, chunking plan before send).
- **Phase 23 — plugin shell and the contact-upload lane.** A loadable Claude Code plugin
  (`.claude-plugin/plugin.json` + `skills/contact-upload/SKILL.md`, auto-triggered and
  slash-invocable) driving four thin, independently-testable Python modules:
  `config_gate.py` (refuses before any network call on missing/invalid config),
  `tabular.py` (reads CSV/XLSX headers and rows verbatim, converts XLSX to CSV bytes for
  the wire), `preview.py` (adaptive, display-only preview — reads
  `config/column_mapping.yaml` only as a read-only lookup for labelling, never to
  transform a row; ≤20 rows renders every row, larger batches render first-10/last-3 plus
  per-column fill rates), and `dispatch.py` (the one POST to `hubspot/contact-upload`;
  `armed` has no default, so a forgotten argument is a `TypeError`, never a silent send).
  Config setup is a one-time operator step from a tracked example file
  (`config/operator.local.example.json`); see this file's README for the full setup,
  file-handoff, and preview walkthrough.
- **Phase 24 — non-tabular input adapters.** Four new ways to hand the skill contacts without a
  spreadsheet: pasted freeform text, a foreign-shaped JSON blob, a public URL (fetched with the
  native `web_fetch` tool only — no HTTP client, no user-agent choice, no viewport, no
  authenticated fetch), and operator-supplied screenshots (never captured by the plugin itself).
  Extraction is Claude reading the source in-session — no Anthropic API call, no API key anywhere
  in the plugin — governed by one no-invention rule stated once in the new
  `skills/contact-upload/extraction.md` bundled resource: absent data stays absent, an unclear
  value goes to a single per-batch ambiguity list instead of being guessed, and a row is never
  completed just to pass the identity check. `extraction.py` (the validator, not the extractor)
  enforces the checkable half: every accepted row carries provenance, a non-canonical key is
  stripped and reported rather than silently dropped, overlapping screenshot reads of the same
  person collapse on the same identity rule the backend uses, and a value an extraction itself
  flagged as ambiguous cannot also be asserted as a fact. `test_extraction_contract.py` pins
  `extraction.md`'s documented examples to the real validator so the two halves of the contract
  cannot silently drift apart. One preview, one dispatch path, unchanged — this phase adds
  producers in front of Phase 23's choke point, nothing behind it.

### Planned

Milestone v0.6, phases 25–30 — see `.planning/workstreams/plugin-entrypoint/ROADMAP.md`:

- **25** Enrichment lane on existing records + cost guard (credit/token estimate, chunking)
- **26** Per-record outcome reporting and safe retry without duplicates
- **27** Backend status surface: n8n-side health endpoint, plain-language read, dashboard artifact
- **28** Control actions: run now, workflow on/off, schedule cadence, conversation-scoped arming
- **29** Notices: in-session run watch and unattended sweep that speaks up only when needed
- **30** Review-queue triage with gated writeback, stamped as a human decision

### Notes

- No implementation files yet; this directory is documentation-only until phase 23.
- Known constraint carried from planning: agent tooling in this repo is blocked from performing
  arming writes, so the armed path needs a human executing it even though the operator-facing
  design is a yes/no in chat.
- Known dependency: the credit figures the cost guard needs cannot be read by this client
  directly (it holds no provider credentials), so they arrive through the n8n-side status
  endpoint. Phase 25 builds the credit-only slice; phase 27 grows the same endpoint to full
  health.
