---
created: 2026-09-11T00:30:00.000Z
updated: 2026-09-11
title: walkWorkflow.mjs D-70-30 rule (c) models the legacy engine — under v1 a zero-item output is NOT a Merge-input delivery, and a Merge can fire twice
area: n8n-tests
severity: major
files:
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
  - tests/n8n/v1RuntimeRecordings.test.mjs
  - scripts/build_cloud_workflows.py
---

## Seen 2026-09-10, Gate 11 (executions 12354/12355/12356, frozen at tests/n8n/fixtures/frozen/exec_1235{4,5,6}.runData.json)

Two v1 behaviours the walker does not model, both now observed live and pinned by
`tests/n8n/v1RuntimeRecordings.test.mjs`:

1. **A node that ran and emitted zero items is NOT a delivery under v1.** `Merge Company` ran
   with 0 items into `Decide Company Action Merge` input 1 and never appears in that Merge's
   `source`. The walker's rule (c) (a zero-item output still delivers) was recorded from the
   legacy engine (12203/12206) and is now known not to hold under v1. Every committed
   `n8n/wf_*.json` runs on v1, so the walker currently models the wrong engine for every graph
   it is allowed to walk.
2. **A Merge can fire twice under v1.** `Decide Company Action Merge` (append, 2 declared
   inputs, SIX producer edges) fired once when both inputs received a marker, then once more
   in the end-of-run drain when a third producer delivered to input 0 alone (input 1 `null`).
   Downstream `Decide Company Action` ran twice, 0 items each — harmless only because it
   filters markers. The walker's report-only Merge pass fires at most once.

## Why it is not fixed in the freeze commit

D-70-19: the walker moves toward the engine, but each move needs its own fidelity case
against a frozen recording, not a freeze-time edit. The recordings now exist; the modelling
change (rule (c) flip + the v1 drain, both deliberately left unmodelled by plan 70-16) is a
gap-closure task with `walkerEngineFidelity.test.mjs` cases over 12354-12356.

## Builder follow-on

Six producer edges into a two-input append Merge is the shape that multi-fires under v1.
`assert_merge_input_contract` (D-70-20) checks at least one producer per input, not at most
one. Decide whether a Merge input with more than one producer is a contract violation, or
whether every consumer of such a Merge must tolerate N runs.
