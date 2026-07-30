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

### Planned

Milestone v0.6, phases 23–30 — see `.planning/workstreams/plugin-entrypoint/ROADMAP.md`:

- **23** Plugin shell, spreadsheet ingestion, preview/approve, dispatch to `hubspot/contact-upload`
- **24** Non-tabular adapters: prose, foreign JSON, public URLs, web-page screenshots, with
  per-row provenance and no invented values
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
