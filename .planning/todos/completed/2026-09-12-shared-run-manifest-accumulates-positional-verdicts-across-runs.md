---
created: 2026-09-12T01:30:00.000Z
updated: 2026-09-12
title: "Shared run_manifest.json accumulates positional row-N verdicts across runs, so the end-of-run report lists prior runs' held rows as this run's"
area: "operator-plugin"
severity: minor
kind: defect
evidence: ".planning/phases/71-a-held-new-person-lands-in-hubspot-with-one-reply/71-UAT.md F71-1 (run 5731da4d0d4b4ae195bda2caf6f9ca8c reported 4 held rows for a run that held 2); operator-claude-plugin/skills/enrich-before-ingest/SKILL.md step 5 `verdicts = run_manifest.load()` (shared path, no run scoping); operator-claude-plugin/scripts/run_manifest.py load()/save()"
files:
  - operator-claude-plugin/scripts/run_manifest.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/scripts/run_report.py
---

## Observed (live, D-71-06 gate, 2026-09-12)

Step 5 loads the SHARED `run_manifest.json` (`run_manifest.load()` with no path), which still
held run `a254d1e…`'s `row-1..row-4 = confidence_held`. This run held row-1 and row-4, wrote
the whole merged map back under its own run_id, and `run_report.build_run_report` then listed
**row-2 and row-3 as HELD** — positions that in this run were the auto-MATCHED Colin Telfer
(1251) and Grant Dewsbury (7101). Same defect class Phase 71 closed for `held_queue`
(D-69-04: `row_id` is minted per batch and is never a cross-run key) — on the manifest.

## Fix shape (one of)

- Step 5 starts from `{}` for the shared write (or from `run_manifest.load(path=run_manifest_path(run_id))`),
  never from the accumulated shared file; or
- key the shared manifest on `held_queue.stable_key(row)` like the held queue, with `row_id`
  carried as source position only.

Either way the run report must only count verdicts whose entry carries THIS run_id.
