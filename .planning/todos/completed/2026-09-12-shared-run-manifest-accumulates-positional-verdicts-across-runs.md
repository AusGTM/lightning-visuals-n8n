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

## Resolved (Phase 73 Plan 01, 2026-09-15, D-73-14)

Took the first fix shape named above: `enrich-before-ingest` SKILL.md step 5's
`verdicts = run_manifest.load()` (shared, unscoped) is now
`run_manifest.load(path=run_manifest.run_manifest_path(run_id))` — a run's held-row
loop starts from `{}` (or its own prior scoped state), never another run's
accumulated verdicts. The dual-write two lines below (shared `save` + scoped `save`)
was already correct and is untouched. `chunking.merge_chunk_verdicts`'s own shared
default is deliberate (same-run crash resume) and was left alone, per this plan's own
scope line.

Regression: `operator-claude-plugin/tests/test_run_manifest.py`'s two new tests prove
(1) a scoped read of run B never returns run A's verdicts even though both share the
same shared-file write, and (2) a brand-new run_id with no scoped manifest yet reads
`{}`, not the shared file's accumulated state. `operator-claude-plugin/tests/
test_mandatory_report_call_sites.py` (unaffected — it does not scan for this literal
call) and the full plugin suite stayed green.
