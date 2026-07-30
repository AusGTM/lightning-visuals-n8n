---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Claude Plugin Entrypoint
current_phase: 23
current_phase_name: walking-skeleton-plugin-shell-tabular-dispatch
status: planning
stopped_at: "Roadmap created — 4 phases (23-26), 24/24 requirements mapped. Next: /gsd-plan-phase 23."
last_updated: "2026-07-30T00:00:00.000Z"
last_activity: 2026-07-30
last_activity_desc: Roadmap created for v0.6; phases 23-26 defined
progress:
  total_phases: 4
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
Last activity: 2026-07-30 — ROADMAP.md written, 24/24 requirements mapped

## Progress

**Phases Complete:** 0 / 4
**Current Plan:** N/A

```
[░░░░░░░░░░░░░░░░░░░░] 0%
```

| Phase | Requirements | Status |
|-------|--------------|--------|
| 23. Walking Skeleton — Plugin Shell & Tabular Dispatch | 9 | Not started |
| 24. Non-Tabular Input Adapters | 7 | Not started |
| 25. Enrichment Lane & Cost Guard | 4 | Not started |
| 26. Outcome Reporting & Safe Retry | 4 | Not started |

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

**Todos / carried context:**

- Phase 26 planning must first verify what `hubspot/contact-upload` actually returns:
  `responseMode: lastNode` over a branching graph may not carry every row's outcome. The
  n8n executions API (`scripts/enrichment_cost_ledger.py`) is the fallback source.
- XLSX must be converted to CSV bytes before POST — the workflow's `Extract From File`
  node runs `operation: csv`. `src/file_loader.py` already reads CSV/TSV/JSON/XLSX.
- Enrichment payloads must set `providers` explicitly; absent/unrecognized means no
  provider is enabled (the primary burn gate in `Parse HubSpot Event`).

**Blockers:** None.

## Session Continuity

**Stopped At:** Roadmap complete
**Resume File:** `.planning/workstreams/plugin-entrypoint/ROADMAP.md`
**Next Action:** `/gsd-plan-phase 23`
