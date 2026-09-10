---
status: testing
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
source: [70-VERIFICATION.md]
started: 2026-09-10T00:00:00Z
updated: 2026-09-10T02:18:25Z
---

## Current Test

number: 3
name: Gate 3 / D-70-19 — disarmed live mixed-batch proof (phase-closing gate)
expected: |
  Deploy + bounce disarmed; read live `settings.executionOrder`; run
  `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` (4 sends).
  `70-RUNTIME-VERDICT.json` shows `shapes_equal: true`, all four executions settled, zero writes,
  and the 15-input `Build Response Merge` accepted by the live engine.
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
result: issue
reported: "operator armed the window and delegated the send; issue observed by the agent on execution 12203 (see observed) — operator to confirm"
severity: major
observed: |
  Pair: Darwin Turf Club `9605267534` (domain `darwinturfclub.org.au`); contact `7101` Grant
  Dewsbury (no association before) on the allowlist; contact `2751` Steve Taylor (already
  associated) off it. Operator armed via `june_run_arm.py --ids 7101`; read-back: all THREE
  declaring nodes (`HubSpot Update Write Gate`, `HubSpot Create Write Gate`, `Associate Lane
  Sentinel`) read `ALLOW_HUBSPOT_RECORD_WRITES="true"`, `TEST_RECORD_IDS="7101"`,
  `TEST_RECORD_DOMAINS=""`. Execution `12203`: SETTLED (`success`), client recovery 27s.
  HubSpot side CORRECT: `7101` PATCHed (lastmodified 02:13:59Z) and association 7101→9605267534
  created (typeId 279 Primary); `2751` untouched (lastmodified unchanged). Disarmed after; all
  flags read `"false"`/`""`. `Build Ingest Response`: exactly 2 rows, never 4.
  FAILED expectations — the reported rows: BOTH came back `action: "update"`,
  `association: "not_confirmed"`. The permitted row did not report `associated`; the refused
  row did not report `write_blocked`, although `HubSpot Update Write Gate IF` out1 DID emit the
  `write_blocked` row for 2751.
  Cause, from runData `source`: `Associate Carry Merge` (combineByPosition) fired with input 1 =
  `Associate Lane Sentinel`'s ZERO-ITEM output (armed → `[]`), not `Build Association Request`'s
  1 item → combined 1×0 = 0 items, the association result dropped. `Ingest Merge Response`
  fired with input 3 = `HubSpot Update Gate Unreached Sentinel`'s ZERO-ITEM output, not the
  gate IF's refusal row → the `write_blocked` row dropped. Both Merges ran exactly once. The
  live engine DELIVERS a zero-item Code output to a Merge input; the walker
  (`tests/n8n/lib/walkWorkflow.mjs:331`) DROPS a zero-item wave (`if (outItems.length === 0)
  return`). `tests/n8n/writeGateShape.test.mjs`'s armed-mixed case is green offline and wrong
  live — the exact "walker is not a faithful model" outcome this phase said to report, not patch.
  Live `settings.executionOrder` absent on every workflow (engine default).

### 3. Gate 3 / D-70-19 — disarmed live mixed-batch proof (phase-closing gate)
expected: Deploy + bounce disarmed; read live `settings.executionOrder`; run `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` (4 sends: enrichment_2x2, enrichment_single_lane, ingest_2x2, ingest_single_lane). `70-RUNTIME-VERDICT.json` shows `shapes_equal: true`, all four executions settled, zero writes, and the 15-input `Build Response Merge` accepted by the live engine (n8n docs describe 2–10 inputs — flagged). Then apply the follow-on CLAUDE.md `[observed live]` edits written at the end of `70-DEFERRED-GATES.md` § Gate 3. Steps in `70-DEFERRED-GATES.md` § Gate 3.
result: [pending]

## Summary

total: 3
passed: 0
issues: 2
pending: 1
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

- gap_id: G-70-2
  truth: "On an armed mixed-verdict ingest batch the permitted row reports association: associated and the refused row reports action: write_blocked"
  status: failed
  reason: "Observed on execution 12203: both rows reported action: update, association: not_confirmed; HubSpot itself was written correctly (one update, one association, blocked row untouched)"
  severity: major
  test: 2
  root_cause: "The live n8n engine delivers a ZERO-ITEM Code-node output to a Merge input as data (runData source names the sentinel), and a Merge fires once with that empty input, so a starved-lane sentinel that emits [] when its lane is NOT starved still claims the input ahead of the lane's real row. The walker drops zero-item waves (walkWorkflow.mjs:331), so every offline GREEN modelled the sentinel as silent. Affected here: Associate Carry Merge (input 1) and Ingest Merge Response (input 3); by construction every Merge input shared between a sentinel and a real producer on every Phase 70 lane."
  artifacts:
    - path: "tests/n8n/lib/walkWorkflow.mjs"
      issue: "line 331 drops a zero-item output instead of delivering it — not n8n's behaviour"
    - path: "scripts/build_cloud_workflows.py"
      issue: "_add_starved_lane_sentinel / wire_gate_refusal_lane: sentinel and real producer share one Merge input; sentinel's [] is a delivery on the live engine"
    - path: "n8n/wf_contact_ingest_cloud.json"
      issue: "Associate Carry Merge input 1 and Ingest Merge Response inputs 2-4 lose the real row when the sentinel fires first"
  missing:
    - "Walker: model a zero-item output as a delivery (empty buffer that satisfies readiness) so the offline harness reproduces execution 12203 RED before any fix"
    - "Design decision (operator): a sentinel must never share a Merge input with a real producer while the engine treats [] as delivery — either per-input separation with append-mode fan-in, or sentinels that emit a marker the response builder filters, or executionOrder v1 re-evaluated with an observed probe"
  debug_session: ""
