---
status: testing
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
source: [70-VERIFICATION.md]
started: 2026-09-10T00:00:00Z
updated: 2026-09-10T00:00:00Z
---

## Current Test

number: 1
name: Gate 1 — disarmed Merge-semantics probe (ingest lane)
expected: |
  Deploy + bounce the ingest workflow disarmed (`scripts/deploy_n8n_workflows.py`, then
  `scripts/bounce_n8n_workflows.py`). Send ONE single-lane batch (association path only, review
  path starved). The execution SETTLES (not stuck `running`); live `settings.executionOrder`
  is read from the workflow body; HubSpot shows zero writes. Record whether `alwaysOutputData`
  on `Set Review` / `HubSpot Associate Company` mattered versus the lane sentinels.
awaiting: user response

## Tests

### 1. Gate 1 — disarmed Merge-semantics probe (ingest lane)
expected: Execution settles (not stuck `running`); a Merge whose second input never fires does not hang on this n8n Cloud build; live `settings.executionOrder` recorded; zero writes. Steps in `70-DEFERRED-GATES.md` § Gate 1.
result: [pending]

### 2. Gate 70-05-A — first ARMED batch with a mixed verdict on one write gate
expected: Arm one window with `TEST_RECORD_IDS` naming exactly one of two contacts that resolve the same company; send both in one ingest batch. `Build Ingest Response` returns exactly 2 rows (never 4); permitted row `action: "update"`, `association: "associated"`; refused row `action: "write_blocked"` with a reason; execution settled; HubSpot shows one contact updated and one association created; `n8n_arming.set_write_safety` rewrote all THREE `ALLOW_HUBSPOT_RECORD_WRITES` nodes on the ingest lane (two gates + `Associate Lane Sentinel`). Steps in `70-DEFERRED-GATES.md` § Gate 70-05-A.
result: [pending]

### 3. Gate 3 / D-70-19 — disarmed live mixed-batch proof (phase-closing gate)
expected: Deploy + bounce disarmed; read live `settings.executionOrder`; run `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` (4 sends: enrichment_2x2, enrichment_single_lane, ingest_2x2, ingest_single_lane). `70-RUNTIME-VERDICT.json` shows `shapes_equal: true`, all four executions settled, zero writes, and the 15-input `Build Response Merge` accepted by the live engine (n8n docs describe 2–10 inputs — flagged). Then apply the follow-on CLAUDE.md `[observed live]` edits written at the end of `70-DEFERRED-GATES.md` § Gate 3. Steps in `70-DEFERRED-GATES.md` § Gate 3.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
