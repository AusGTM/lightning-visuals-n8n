---
created: 2026-09-09T00:30:00.000Z
updated: 2026-09-09
title: The operator's durable state directory never prunes — 362 run_state files after one week
area: operator-plugin
severity: minor
files:
  - operator-claude-plugin/scripts/run_state.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/scripts/artifact_store.py
---

## Observed 2026-09-09

`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`: 393 files,
1.5 MB. 362 are `run_state-<run_id>.json` (155 bytes each — every `run_state.new_run_id()`
persists one, including every offline/preview run that never dispatched), 19
`written_records-*.json`, 6 `run_audit-*.json`, 2 `run_manifest-*.json`. Nothing deletes
any of them. The only TTL in the plugin is `artifact_store`'s `dashboard_artifact_ttl_days`
(30), which covers one file.

Growth is ~1-2 KB per run — not a space problem for years, but a listing problem now: the
end-of-run report and any `glob` over the directory walk hundreds of dead run_state files,
and the operator asked whether anything cleans up. Nothing does.

## Proposed

A `prune_durable_state(config, now)` in `durable_paths.py` (one resolution rule, one
pruner), run at the START of a round, never mid-run:
- `run_state-*` older than 7 days: delete (they carry only dispatched row ids for resume,
  and a resume older than that re-runs everything anyway per Phase 61).
- `written_records-*` / `run_audit-*` / `run_manifest-*` older than `dashboard_artifact_ttl_days`
  (reuse the key, default 30): delete — the end-of-run report for a run that old has been
  read or never will be.
- `held_queue.json`, `suggestion_declines.json`, `operator.local.json*`: never.
Print one line naming what was pruned. Retention for the Phase 69 decline store stays
deferred (69-CONTEXT § Deferred).

## Resolved 2026-09-09

Fixed in debug session `.planning/debug/uat-batch-review-row-reads-failed.md` (F2):
`run_report.prune_durable_state(config, now)` implemented — NOT in `durable_paths.py`
as originally proposed above (see the debug file's F2 Resolution for why:
`test_sweep_read_only.py`'s static write-verb confinement over the unattended sweep's
reachable module closure forced the relocation to `run_report.py`, which is outside
that closure). Same TTL design otherwise: `run_state-*` at 7 days, the other four
per-run families (including F3's new `run_report-*.md`) at `dashboard_artifact_ttl_days`
(default 30), `held_queue.json`/`suggestion_declines.json`/`operator.local.json*` never
touched. Wired into `enrich-before-ingest/SKILL.md` step 1 only; the other batch-shaped
skills adopting the same call is a follow-on, not done here.
