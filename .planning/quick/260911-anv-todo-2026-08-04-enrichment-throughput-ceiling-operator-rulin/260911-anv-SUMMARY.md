---
status: complete
phase: quick-260911-anv
plan: 01
subsystem: n8n-judge-observability
tags: [n8n, judge, escalation, measurement, read-only]
dependency-graph:
  requires: []
  provides:
    - scripts/judge_reason_distribution.py (read-only judge-reason distribution reader)
  affects:
    - .planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md
tech-stack:
  added: []
  patterns:
    - "GET-only n8n reader reusing enrichment_cost_ledger._list_executions/_get_execution/_node_output_items"
key-files:
  created:
    - scripts/judge_reason_distribution.py
    - tests/test_judge_reason_distribution.py
  modified:
    - .planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md
decisions:
  - "No builder or workflow-JSON edit needed for part (a) — judge_reasons was already emitted unconditionally on every row; verified from committed artefacts and frozen live runData rather than assumed."
  - "Filtered the executions list to the enrichment workflow by reusing scripts/bounce_n8n_workflows.py's committed-file -> live-id map, avoiding a third n8n reader (_get_live_workflows)."
  - "Reported the live sample as a genuine zero-escalation result with its cause (retention rolled past every provider-enabled run) rather than treating it as 'not achievable' — the API call itself succeeded."
metrics:
  duration: ~40m
  completed: 2026-09-11
actuals:
  tokens: 21000
  tasks: 3
  commits: 2
  plan_head_before: 3747e14ecabaf3ec6ce93f0d4c86b9f9c81c1e4c
---

# Quick 260911-anv: Judge-reason distribution measurement Summary

Answered the operator's 2026-09-11 "measure first" ruling on the
2026-08-04 enrichment-throughput-ceiling todo by building a read-only distribution reader
and running it, without touching the judge gate, the escalation band, or any generated
n8n workflow.

## What was built

`scripts/judge_reason_distribution.py` — a GET-only CLI (`summarize`/`collect`/`main`)
that folds the `Judge Gate` and `Contact Judge Gate` node output over past n8n executions
into counts: `rows_through_gate`, `rows_research_matched`, `rows_with_reasons`,
`rows_capped`, `by_reason`, `by_reason_set`. It reuses
`enrichment_cost_ledger._list_executions`/`_get_execution`/`_node_output_items` and
`bounce_n8n_workflows.WORKFLOWS` for the enrichment workflow's live id — no new n8n
reader, no third GET path. `summarize()` is pure, folds every run of a node (v1 can fire
a node twice), and never raises on malformed input.

`tests/test_judge_reason_distribution.py` pins `summarize()` against a hand-built runData
fixture covering every case in the plan's `<behavior>` block: two runs on one node both
folded, a two-reason row, a capped row, an unmatched-research row, an empty-reasons row,
an absent-key row, a non-dict item, and a malformed run. Observed RED
(`ModuleNotFoundError`) before the implementation existed.

## Deviations from Plan

None — plan executed exactly as written. Task 1 was read-only (no files changed, no
commit); Task 2 followed TDD RED->GREEN; Task 3 ran the script and recorded all three
answers in the todo.

## Measurement result (todo Task 3, branch (c))

The live sample was reachable (GET succeeded, `.env` credentials via the script's own
`load_dotenv()`) but measured **zero judge escalations** across 89 scanned executions
(ids `12264`-`12356`, the enrichment workflow's entire retained execution history on this
instance as of 2026-09-11). The cause, verified rather than assumed: every retained
execution is either a 2026-09-10 runaway self-dispatch child (`integrated` mode, providers
never called) or a disarmed proof send (`mode: "propose"`, `provider_enabled` all false) —
`research_candidate.matched` is `false` on every item, so `computeEscalation`'s RO-1 guard
never lets a reason fire. The plan's named 2026-08-04 execution ids (`1152`, `1109`,
`443`, `442`, `337`, `332`, `328`, `18`) all 404 (pruned), confirmed by direct probe.
Phase 63's 5-input replay corpus (`63-JUDGE-REPLAY-VERDICT.json`) remains the only
surviving sample of a real escalation distribution and is cited in the todo with its own
denominator limitation noted.

Full detail, evidence, and the (a)/(b)/(c) writeup live in the todo's new
"## Measurement 2026-09-11" section.

## Self-Check: PASSED

- `scripts/judge_reason_distribution.py` — FOUND
- `tests/test_judge_reason_distribution.py` — FOUND
- `.planning/todos/pending/2026-08-04-enrichment-throughput-ceiling.md` — FOUND, contains
  `2026-09-11` and `63-JUDGE-REPLAY-VERDICT.json`
- commit `0fe2003c` (Task 2) — FOUND in `git log --oneline`
- commit `253a75b5` (Task 3) — FOUND in `git log --oneline`
- `git diff --stat -- n8n/ scripts/build_cloud_workflows.py` — empty
- `node --test tests/n8n/*.test.mjs` — 1100 passed, 0 failed
- `.venv/bin/python -m pytest tests/test_judge_reason_distribution.py tests/test_judge_spec.py -q` — 14 passed
