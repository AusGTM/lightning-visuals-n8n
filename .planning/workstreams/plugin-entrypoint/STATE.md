---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Claude Plugin Entrypoint
current_phase: 23
current_phase_name: walking-skeleton-plugin-shell-tabular-dispatch
current_plan: 05
status: executing
stopped_at: 23-05 complete (wave 3) — adaptive display-only preview (preview.py), skill wording driving it, operator README setup/usage docs, PLUGIN-02 wording reconciled with D-05. 23-01 through 23-04 also complete.
last_updated: "2026-07-31T21:15:00.000Z"
last_activity: 2026-07-31
last_activity_desc: executed 23-05 (adaptive preview, skill/README docs, PLUGIN-02 reconciliation)
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 6
  completed_plans: 4
  percent: 8
---

# Project State

## Current Position

Phase: 23 — Walking Skeleton — Plugin Shell & Tabular Dispatch (executing)
Plan: 23-01, 23-02, 23-03 complete (wave 1); 23-04 complete (wave 2, the tracer); 23-05 complete (wave 3)
Status: 23-01 (contact-lane create gate fix), 23-02 (file-handoff smoke test), 23-03 (test scaffolding + network guard), 23-04 (config gate / tabular / disarmed dispatch / plugin shell), and 23-05 (adaptive preview, skill/README docs, PLUGIN-02 reconciliation) done
Last activity: 2026-07-31 — executed 23-05

## Accepted requirement amendments (reconcile before each phase seals)

Five places where a locked decision or a verified research finding diverges from the written
requirement. Each was surfaced explicitly and chosen deliberately — none is a silent drift.

| # | Requirement | Amendment | Source |
|---|---|---|---|
| 1 | PLUGIN-02 | Operator, not admin, performs config setup from the committed example file | Phase 23 D-05 (wording reconciled in REQUIREMENTS.md by 23-05) |
| 2 | Phase 25 criterion 2 | Provider default ships as full waterfall, so silence enables providers. Mitigated: `Parse HubSpot Event` has no server-side default and fails closed, and the resolved selection is always shown in the preview | Phase 25 D-05 / D-06a |
| 3 | STATUS-04 + Phase 27 criterion 4 | "Stuck lock" redefined as a long-running execution. `enrichment_lock_until` does not exist and `lv_enrichment_status` is never set to `running` | Phase 27 D-07a–d |
| 4 | REPORT-02 | ICP-tier clause removed entirely. HubSpot owns the derived ICP outputs per Phase 15 Approach C; the backend has nothing to read back and a placeholder would imply otherwise | Phase 26 D-10a / D-10b |
| 5 | CONTROL-01 + Phase 28 criterion 1 | Off-cycle scheduled-scan execution dropped. No n8n API endpoint exists (upstream PR #20304 unmerged). Operator controls scans via enable/disable and re-timing instead | Phase 28 D-05a–c |

## Backend changes v0.6 requires (not client-only)

- **Contact-lane create gate** (Phase 23 D-16a/D-16b) — `Set Config` hardcodes `allow_create: false`,
  so the contact lane cannot create a record today. Fix **reuses the existing overlayable
  `ALLOW_HUBSPOT_CREATE`** (no fifth flag — `_OVERLAYABLE_FLAGS` is pinned to four names by
  `tests/test_enabled_build_invariants.py`) and is baked into **`Decide Action`**, not `Set Config`
  — `Extract From File` emits fresh items, so anything seeded upstream is lost (BUG 12 / BUG 21
  row-loss family). Lands first in Phase 23 as plan 23-01.

- **List/view resolution** (Phase 25 D-02) — plus an unresolved feasibility question: HubSpot saved
  views have no public API, and `crm.lists.read` scope is unevidenced in this repo.

- **Credit-only status endpoint** (Phase 25), generalized to full health (Phase 27).
- **`hubspot/review/decision` webhook + `ALLOW_HUBSPOT_REVIEW_WRITES` flag** (Phase 30 D-08e).

## Progress

**Phases Complete:** 0 / 8
**Current Plan:** 23-01, 23-02, 23-03, 23-04, 23-05 (all complete; 5/6 plans)

```
[█░░░░░░░░░░░░░░░░░░░] 8%
```

| Phase | Requirements | Status |
|-------|--------------|--------|
| 23. Walking Skeleton — Plugin Shell & Tabular Dispatch | 10 | Executing (23-01, 23-02, 23-03, 23-04, 23-05 done, 5/6 plans) |
| 24. Non-Tabular Input Adapters | 8 | Executing (24-01 done, 1/3 plans) |
| 25. Enrichment Lane & Cost Guard | 4 | Not started |
| 26. Outcome Reporting & Safe Retry | 4 | Executing (26-01 done, 1/3 plans) |
| 27. Backend Status Surface | 6 | Executing (27-01 done, wave 1) |
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

- **23-01 closed D-15/D-16/D-16a/D-16b.** `Decide Action` (contact-ingest Cloud workflow) now
  derives its create decision from the existing overlayable `ALLOW_HUBSPOT_CREATE` constant
  (composed at the `build_cloud()` build site, not `Set Config`), instead of a hardcoded row
  field — an armed deploy can now actually create a net-new contact, with the same
  `TEST_RECORD_*` allowlist requirement as every other write path. No fifth overlay flag added;
  no file under `operator-claude-plugin/` touched.

- **23-02's live smoke test resolved D-14a with a positive result**, widening 23-04's build: an
  operator attachment in the Code tab resolves to a real filesystem path (not just
  conversation-content), `@mention` also resolves to a real path (workspace-scoped only),
  `python3` is available, and `openpyxl`/`requests`/`PyYAML` import with no install step. 23-04
  built the genuine two-legged file handoff (attachment + `@mention`) rather than the
  single-leg-plus-try/except degradation the plan text originally anticipated.

- **23-04 is the walking skeleton itself.** `config_gate.py` → `tabular.py` → `dispatch.py`
  wired end to end, proven against a stub transport: `armed` has no default (TypeError if
  omitted), the unarmed path leaves the stub's call log empty, and the armed path produces the
  exact `hubspot/contact-upload` multipart contract (header `X-Enrichment-Secret`, file field
  `data`, `text/csv`). Plugin manifest + `skills/contact-upload/SKILL.md` give it one loadable
  entry point (auto-triggered and slash-invocable, no `commands/` duplicate). An AST-based
  guard now makes PLUGIN-04 (no backend import) a test, not a promise. Full repo suite: 741
  passed, no regressions; no file outside `operator-claude-plugin/` touched.

- **23-05 replaced the 23-04 preview placeholder with the real adaptive preview.**
  `preview.py`'s `label_headers()`/`build_preview()` read `config/column_mapping.yaml`
  as a read-only display lookup only (mirroring `Map Columns`' case-insensitive,
  whitespace-collapsed rule exactly rather than improving on it), never transforming a
  row — a byte-identity test proves the source file is untouched. ≤20 rows renders every
  row; above that, first-10/last-3 plus per-column fill rates (including dropped
  columns). SKILL.md, README.md, and CHANGELOG.md now teach setup and usage end to end,
  and PLUGIN-02's wording was reconciled with D-05 (operator self-setup replaces the
  stale admin-provisioned text, in both REQUIREMENTS.md and two stale README passages
  that had drifted the same way). Full repo suite: 749 passed, no regressions; no file
  outside `operator-claude-plugin/` or `.planning/` touched.

- **24-01 built the extraction validator spine** — `operator-claude-plugin/scripts/extraction.py`
  validates (never extracts) a Claude-written JSON artifact: `canonical_props()` and
  `identity_groups()` derive from `config/column_mapping.yaml` rather than being retyped;
  `has_identity()` trims before checking presence, matching the deployed `Map Columns` node's
  `requiredIdentity()` rather than the untrimmed `src/file_loader.py::_has_identity`; a
  non-canonical key is stripped from the row AND reported (record index + key) before the
  identity check runs; every artifact-shape failure raises a distinct `ExtractionError` code
  (never a silent zero-row success); `write_dispatch_csv()` raises on any row key outside the
  canonical set, including a smuggled `provenance` key, so STRUCT-01 is structural, not a
  runtime filter someone can forget. `preview.py` gained `resolve_mapping_path()` (one shared
  mapping-file lookup) and `build_extracted_preview()` (provenance/rejects/dropped-keys/
  ambiguities in one structure, reusing the same adaptive-sample rule). Full repo suite: 774
  passed at completion (749 baseline + 25 new); no file outside `operator-claude-plugin/` or
  `.gitignore` touched. 24-02 (screenshot dedupe, ambiguity aggregation) and 24-03 (the four
  adapters wired into SKILL.md) build on this artifact contract next.

- **26-01 built the contact-upload report tracer** — `operator-claude-plugin/scripts/executions_client.py`
  (read-only `X-N8N-API-KEY` GETs, pure `find_execution_for_dispatch()` time-proximity
  correlator marked `best_effort`) and `report.py` (`contact_row_ledger()` reads `Decide
  Action`'s own output, never `Set Review`'s stripped `{"queue": "needs_review"}`;
  `reconcile()` downgrades a decided update/create to `not_confirmed` when the terminal
  write node produced zero items; `build_contact_report()` treats any non-settled or
  unrecognised execution status as `in_flight`, never finished). `sync_response_is_
  sufficient()` gates the synchronous webhook body, falling through to the executions
  API when it's `Set Review`-shaped. SKILL.md's step 7 renders counts first, the
  failing rows in full, the `NO_EMAIL`/`ambiguous` permanently-stuck case named
  plainly, and a run handle whose re-check is explicitly manual-only — an AST guard
  now makes D-07 (no poll loop) a property the suite enforces. Full repo suite: 869
  passed at completion; no file outside `operator-claude-plugin/` or `.planning/`
  touched. Known artifact: a concurrent-agent git-index race (24-02/24-03 sharing
  the same working tree) misattributed one commit's message to the wrong diff —
  content-correct, cosmetic only, documented in 26-01-SUMMARY.md's Issues Encountered.

- **27-01 grew `hubspot/backend-status` from Phase 25's credit-only slice into full
  health.** `n8n/code/backendStatus.js` (`extractSearchTotal`/`deriveSourceHealth`/
  `buildStatusBody`, 22 unit tests) plus four HubSpot count searches
  (requested-unresolved / awaiting-review, companies + contacts, OR'd filter groups so
  an absent `lv_enrichment_status` isn't silently under-counted by NEQ) and a
  credential-health block for the three providers plus HubSpot. Honored the
  plan-checker retarget: extended `build_backend_status_cloud()` /
  `wf_backend_status_cloud.json` (confirmed the only file serving this endpoint),
  `wf_enrichment_cloud.json` regenerated byte-identical. Full repo suite: 919 passed
  (900 baseline + 19 new), no file outside `n8n/`/`scripts/`/`tests/` touched.

**Todos / carried context:**

- 24-03 must write `extraction.md`'s documented artifact schema example(s) such that a
  contract test (D-13) can parse the fenced examples out of the markdown and run them
  through `extraction.py`'s real `validate()` — this pin was not yet built in 24-01 since
  `extraction.md` itself doesn't exist until 24-03.

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

**Stopped At:** 23-05 (adaptive preview, skill/README docs, PLUGIN-02 reconciliation) complete. 23-01 through 23-04 also complete.
**Resume File:** `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-05-SUMMARY.md`
**Next Action:** Continue executing phase 23's remaining plan (23-06, wave 4 — the final plan closing out the phase)
