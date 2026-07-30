---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Claude Plugin Entrypoint
current_phase: 23
current_phase_name: walking-skeleton-plugin-shell-tabular-dispatch
status: planning
stopped_at: "Roadmap re-cut — 8 phases (23-30), 49/49 requirements mapped. v0.6 is now front door + control plane. Next: /gsd-plan-phase 23."
last_updated: "2026-07-30T00:00:00.000Z"
last_activity: 2026-07-30
last_activity_desc: v0.6 scope widened to control plane; phases 27-30 added (status, control, notices, review triage); screenshot adapter INGEST-07 added to Phase 24
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Current Position

Phase: 23 — Walking Skeleton — Plugin Shell & Tabular Dispatch (not started)
Plan: —
Status: Roadmap approved shape, awaiting phase planning
Last activity: 2026-07-30 — ROADMAP.md re-cut for control plane, 49/49 requirements mapped

## Progress

**Phases Complete:** 0 / 8
**Current Plan:** N/A

```
[░░░░░░░░░░░░░░░░░░░░] 0%
```

| Phase | Requirements | Status |
|-------|--------------|--------|
| 23. Walking Skeleton — Plugin Shell & Tabular Dispatch | 10 | Not started |
| 24. Non-Tabular Input Adapters | 8 | Not started |
| 25. Enrichment Lane & Cost Guard | 4 | Not started |
| 26. Outcome Reporting & Safe Retry | 4 | Not started |
| 27. Backend Status Surface | 6 | Not started |
| 28. Control Actions | 7 | Not started |
| 29. Notices & Unattended Sweep | 5 | Not started |
| 30. Review-Queue Triage | 5 | Not started |

## Accumulated Context

**Decisions:**

- Phase numbering starts at 23 — v0.5 ended at phase 22; continuing avoids phase-directory
  collision with the archived `.planning/workstreams/milestone/` phases 20–22.
- The plugin is a front door, not a second pipeline. Column mapping, phone/email
  normalization, verification, identity resolution, dedupe and create/update routing stay
  in n8n. The plugin structures only *non-tabular* input; tabular input passes through.
- Walking skeleton before breadth: one input shape (spreadsheet), one lane
  (`hubspot/contact-upload`), disarmed, end to end in Phase 23 — so something demonstrable
  exists before the other adapters land.
- Dispatch ships disarmed, per the repo's established two-key write gate (phases 19–22).
  Approval at the preview is not arming; arming is a separate deliberate operator step.
- URL ingestion uses the native Anthropic `web_fetch` server tool on the existing client
  and `ANTHROPIC_API_KEY` — no new dependency. Anti-bot-detection is out of scope by
  requirement.
- Screenshot ingestion (INGEST-07) is a fifth adapter into the same Phase 24 choke point, not
  its own phase — it differs from the prose/URL adapters only in the read (vision on an
  attached image) and in needing a legibility signal, not in preview, dispatch, or gating.
- Client code lives in `operator-claude-plugin/` with its own README + CHANGELOG, versioned
  independently. It is documented as a *suggested default thin client*, not the interface: n8n is
  a standalone backend over plain HTTP, so other front ends (Slack, web app, CLI) can be built
  against the same contract, concurrently. Client never imports enrichment logic; the only
  backend edit this milestone makes is the new n8n-side status endpoint.
- **v0.6 is the control plane as well as the front door.** The operator is non-technical, works
  in Claude Desktop, and never opens n8n. Anything n8n would surface in its own UI has to arrive
  in the conversation, and "run this command" is a requirement failure, not a fallback. Phases
  27-30 add read, control, notices, and review triage.
- Control depth stops short of deploy: allowlisted mutations only (write-safety flag overlay,
  schedule cadence, workflow active state). Editing nodes, credentials, or workflow structure
  stays an admin task run from this repo.
- Arming is conversation-scoped. n8n's baked flag is persistent; the plugin's willingness to use
  it lapses with the session. Both facts must show in status — conflating them is how a silent
  live send happens.
- The plugin performs the arming write itself (the operator cannot run a command), via the
  existing `enable_baked_flags()` overlay + `PUT /api/v1/workflows/{id}`, with diff shown,
  explicit confirm, and read-back verification. Standing constraint: agent tooling here is
  blocked from arming writes, so the armed path needs a human executing even though the
  operator-facing design is a yes/no in chat.
- The plugin holds no provider or HubSpot credentials — those stay in n8n, admin-managed. So
  credit balances must come back through a new n8n-side status endpoint;
  `scripts/check_provider_credits.py` is an admin tool, not a model for the plugin. Phase 25
  builds the credit-only slice, Phase 27 grows the same endpoint into full health.
- Status presentation: conversational text by default, dashboard Artifact on request
  (re-published to the same URL, stamped with fetch time).
- Review triage happens in Claude with writeback, gated separately from dispatch and honoring
  the existing field-policy classes — a second CRM write path, not a bypass of the merge policy.
- Screenshots are operator-attached, never plugin-captured. No browser automation, no login,
  no scroll-and-shoot. A screenshot is not a bypass of the scraping exclusions: LinkedIn
  profile fields still come from the licensed provider waterfall.

**Todos / carried context:**

- Phase 26 planning must first verify what `hubspot/contact-upload` actually returns:
  `responseMode: lastNode` over a branching graph may not carry every row's outcome. The
  n8n executions API (`scripts/enrichment_cost_ledger.py`) is the fallback source.
- XLSX must be converted to CSV bytes before POST — the workflow's `Extract From File`
  node runs `operation: csv`. `src/file_loader.py` already reads CSV/TSV/JSON/XLSX.
- Enrichment payloads must set `providers` explicitly; absent/unrecognized means no
  provider is enabled (the primary burn gate in `Parse HubSpot Event`).

**Blockers:** None. Carried risks: (1) agent tooling is blocked from arming writes, so Phase 28's
armed path needs a human in the loop; (2) unattended sweep (NOTICE-03) depends on scheduling
being available in the operator's Claude Desktop environment — verify before planning Phase 29
rather than assuming; (3) the n8n-side status endpoint is new backend work landing inside a
milestone otherwise scoped as plugin-only.

## Session Continuity

**Stopped At:** Roadmap complete
**Resume File:** `.planning/workstreams/plugin-entrypoint/ROADMAP.md`
**Next Action:** `/gsd-plan-phase 23`
