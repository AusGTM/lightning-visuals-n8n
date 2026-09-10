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

## Builder follow-on — CARRIED OUT, not closed by proximity

This section's question is NOT answered by the fix below — it survives as its own pending
todo, `.planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md`.
See that file.

## Resolved 2026-09-11 (quick task 260911-0tz)

Fixed in `tests/n8n/lib/walkWorkflow.mjs`: `propagate()` and the Merge-handling loop now
carry two EXPLICIT branches keyed on `order` (`wf.settings.executionOrder`), never one
patched state machine — a legacy branch (byte-identical arrival state machine, unchanged)
and a v1 branch (run-indexed pending buffering: nothing is ever discarded, the earliest
pending run with an unfilled input takes a delivery, or a new pending run opens). A new
end-of-run drain (v1 only) fires the earliest pending run of any Merge whose filled-input
count reaches `requiredInputs` (always `1` for the append/combine Merges this repo emits),
repeating — and resuming the main queue after each fire — until nothing qualifies. Both
branches share the append/combineByPosition/combineAll maths via one extracted
`mergeBuffers` helper.

Fidelity evidence: `tests/n8n/walkerEngineFidelityV1.test.mjs` (new) walks a frozen v1 copy
of the committed enrichment graph
(`tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json`) with the recordings'
own trigger items and HTTP responses, and reproduces executions 12354/12355/12356
verbatim: `Decide Company Action Merge` fires twice (`[2, 1]` items, run 1 input 1
unfilled), `Merge Company`'s zero-item output never claims a Merge input,
`Enrichment Gate Merge` fires once with 6 items, `Build Response` returns both rows in one
run, `HubSpot Update` never runs. RED was observed first against the unmodified walker
(`Decide Company Action Merge` fired once, not twice — a clean assertion failure, not a
TypeError). `tests/n8n/walkerEngineFidelity.test.mjs`'s three legacy fixtures
(12203/12206/12316) pass with ZERO diff, proving the legacy branch stayed byte-identical.
Full `tests/n8n` suite: 1087/1087 passing (baseline 1083 + 4 new).

`scripts/build_cloud_workflows.py` and every `n8n/wf_*.json` are untouched — this fix is
walker-only, per the plan's hard scope line.
