---
status: testing
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
source: [70-VERIFICATION.md]
started: 2026-09-10T00:00:00Z
updated: 2026-09-09T23:39:41Z
---

## Current Test

number: 2
name: Gate 70-05-A — first ARMED batch with a mixed verdict on one write gate
expected: |
  Arm one window with `TEST_RECORD_IDS` naming exactly one of two contacts that resolve the
  same company; send both in one ingest batch. `Build Ingest Response` returns exactly 2 rows
  (never 4); permitted row `action: "update"`, `association: "associated"`; refused row
  `action: "write_blocked"` with a reason; execution settled; HubSpot shows one contact updated
  and one association created; `n8n_arming.set_write_safety` rewrote all THREE
  `ALLOW_HUBSPOT_RECORD_WRITES` nodes on the ingest lane (two gates + `Associate Lane Sentinel`).
awaiting: user response

## Tests

### 1. Gate 1 — disarmed Merge-semantics probe (ingest lane)
expected: Execution settles (not stuck `running`); a Merge whose second input never fires does not hang on this n8n Cloud build; live `settings.executionOrder` recorded; zero writes. Steps in `70-DEFERRED-GATES.md` § Gate 1.
result: issue
reported: "log Test 1 as issue (run_id echo)"
severity: major
observed: |
  Deployed + bounced disarmed 2026-09-10 (five PUTs at 200; live nodes 30/50/218/45/43 = committed;
  write flags false). Execution `12200`: SETTLED (`success`, 6.1s). Every Merge fired once;
  `Ingest Merge Response` 7 in → `Build Ingest Response` 2 rows. Association path starved,
  satisfied by `Associate Lane Sentinel` (1 item); `HubSpot Associate Company` never ran, so its
  `alwaysOutputData` contributed nothing — the sentinels are the mechanism. Live
  `settings.executionOrder`: ABSENT (`settings: {}`) on all five workflows. HubSpot: zero writes.
  ISSUE: `dispatch.py` sent `run_id` as a 3-tuple multipart part with Content-Type; n8n filed it
  under `$binary`, `$json.body` was `{}`, `Set Config` echoed `run_id: null`, and the client-path
  recovery poll ran to its 600s bound (652s wall, `rows: []`). Fixed in-session (2-tuple, no
  Content-Type; same fix to `source_by_field`); re-run execution `12202` through the real client
  path: ack echoes the run id, recovery settles in 26s, 2 rows returned, zero writes.

### 2. Gate 70-05-A — first ARMED batch with a mixed verdict on one write gate
expected: Arm one window with `TEST_RECORD_IDS` naming exactly one of two contacts that resolve the same company; send both in one ingest batch. `Build Ingest Response` returns exactly 2 rows (never 4); permitted row `action: "update"`, `association: "associated"`; refused row `action: "write_blocked"` with a reason; execution settled; HubSpot shows one contact updated and one association created; `n8n_arming.set_write_safety` rewrote all THREE `ALLOW_HUBSPOT_RECORD_WRITES` nodes on the ingest lane (two gates + `Associate Lane Sentinel`). Steps in `70-DEFERRED-GATES.md` § Gate 70-05-A.
result: [pending]

### 3. Gate 3 / D-70-19 — disarmed live mixed-batch proof (phase-closing gate)
expected: Deploy + bounce disarmed; read live `settings.executionOrder`; run `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` (4 sends: enrichment_2x2, enrichment_single_lane, ingest_2x2, ingest_single_lane). `70-RUNTIME-VERDICT.json` shows `shapes_equal: true`, all four executions settled, zero writes, and the 15-input `Build Response Merge` accepted by the live engine (n8n docs describe 2–10 inputs — flagged). Then apply the follow-on CLAUDE.md `[observed live]` edits written at the end of `70-DEFERRED-GATES.md` § Gate 3. Steps in `70-DEFERRED-GATES.md` § Gate 3.
result: [pending]

## Summary

total: 3
passed: 0
issues: 1
pending: 2
skipped: 0
blocked: 0

## Gaps

- gap_id: G-70-1
  truth: "The client-minted run_id is echoed by Set Config so recovery correlates on it"
  status: resolved
  reason: "User reported: log Test 1 as issue (run_id echo)"
  severity: major
  test: 1
  root_cause: "operator-claude-plugin/scripts/dispatch.py sent run_id (and source_by_field) as multipart parts WITH a Content-Type; n8n's multipart parser files any part carrying Content-Type under $binary, so $json.body.run_id was never set. Never observed live before 2026-09-10 — every offline test stubs the transport."
  artifacts:
    - path: "operator-claude-plugin/scripts/dispatch.py"
      issue: "3-tuple (None, value, content_type) for run_id and source_by_field"
    - path: "operator-claude-plugin/tests/test_dispatch_multipart.py"
      issue: "pinned content_type == application/json — pinned the bug"
  missing:
    - "2-tuple (None, value) for both parts; test pins len(part) == 2"
  resolved_by: "in-session fix, verified live on execution 12202"
  resolved_at: 2026-09-10
  debug_session: ""
