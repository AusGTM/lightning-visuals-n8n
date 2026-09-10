---
status: testing
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
source: [70-VERIFICATION.md (round 1: Gates 1/70-05-A/3 — run 2026-09-10), 70-VERIFICATION.md (round 2, gap closure 70-08..70-12: Gates 4/5/6)]
started: 2026-09-10T00:00:00Z
updated: 2026-09-10T07:14:46Z
---

## Current Test

[testing paused — Gate 5 enrichment lane blocked on G-70-5; Gate 6 blocked on Gate 5]

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
result: issue
reported: "operator delegated the run; issue observed by the agent (verdict shapes_equal: false) — operator to confirm"
severity: blocker
observed: |
  Driver run 2026-09-10T02:21Z after the G-70-1 fix and the driver's own live-half repairs
  (nonexistent `executions_client.get_workflow`, wrong ingest workflow literal, ingest sends
  routed through the enrichment webhook — all found on first live run). Verdict:
  `shapes_equal: false`, `writes_performed: 0`, every flag `"false"`, executions `12204`+`12205`
  (enrichment_2x2, 2 chunks), `12206`, `12207`, `12208` — ALL settled `success`, no hang.
  `live_settings_execution_order`: null on both workflows (setting absent; engine default).
  INGEST sends (`12207`, `12208`): row-for-row equal to the walker on `action`/`outcome`/
  `email`; the only difference is the client-side `reported_outcome` key `report.reconcile`
  adds — the driver compares client-reconciled rows against raw walker rows (comparator
  artifact, G-70-4), not a runtime divergence.
  ENRICHMENT sends (`12204`/`12205`/`12206`): 0 rows recovered vs 4/2 predicted.
  `Build Response Merge` (15 inputs) NEVER EXECUTED on any of the three executions; `Build
  Response` never ran; the execution finished `success` with the response lane silently
  starved — not a hang, a silent termination. Upstream, `Enrichment Gate Merge` (append, 5
  inputs) fired ONCE with sources `Contacts Lane FetchById Absent Sentinel` (1 marker) on in0
  and `Contacts Absent Sentinel`'s ZERO-ITEM output on in1–in4 (contacts were present, so it
  emitted `[]`), producing 1 marker item; `Enrichment Gate` filtered it to 0; the real rows
  (`Adapt Search` 2 items / `Adapt Linkedin Search` 2 items) reached in4/in1 AFTER the Merge
  had fired and were dropped. Same engine rule as G-70-2: a zero-item output is a delivery,
  first delivery per input wins, the Merge fires once. The 15-input Merge then received only
  zero-item sentinel deliveries on inputs 0–3, 11, 12 and never fired at all, while every
  ≤10-input Merge in the same executions fired — the carried 2–10 caveat is now an
  observation, cause not isolated.
  CLAUDE.md follow-on `[observed live]` edits NOT applied — the gate did not pass.

### 4. Gate 4 / Gate 5 (deploy) — a working graph on the live instance
expected: Live instance no longer runs the defective pre-gap-closure JSON. EITHER Gate 4 rollback to `59812be` (17/29/123/26/39 nodes) OR Gate 5's deploy + bounce of the gap-closure JSON (291/69/55/43/30 nodes), disarmed, both write flags `"false"` read back. Steps in `70-DEFERRED-GATES.md` § Gate 4 / § Gate 5.
result: issue
reported: "agent-driven (disarmed deploy/bounce); issue observed — operator to confirm"
severity: blocker
observed: |
  2026-09-10T07:03Z: gap-closure JSON deployed (five PUTs at 200) and bounced; live 30/69/291/55/43,
  all active, both write flags `"false"` everywhere. Proof driver sent enrichment_2x2 at 07:04Z.
  RUNAWAY: the enrichment workflow began self-dispatching — 135 `integrated` (Execute Workflow)
  child executions 12211–12348 in six minutes, ~3 in flight continuously, each child dispatching
  one more. 138 enrichment executions consumed in total (ids 12209–12348) against the Starter
  2.5K/month budget. Stopped by `POST /workflows/950HPb7a1GgSAIyZ/deactivate` at ~07:09:45Z
  (children queued before it still ran; the last three, 12346–12348, errored
  `Workflow is not active and cannot be executed` at 07:10:15Z) and, belt-and-braces, a PUT of
  the pre-Phase-70 `59812be` enrichment body (123 nodes) at 07:10:50Z. No new execution after
  12348. Enrichment workflow reactivated on the pre-70 body at ~07:14Z. Zero HubSpot writes.
  Mechanism (child 12316, runData): `Dispatch Self` ran ONCE with 1 marker item and dispatched
  a child carrying a bare event (`object_type: "unknown"`, `run_id: null`, `scale_up: false`,
  `fan_depth: 0` — so the depth guard never saw a fan-out it could stop). Its ONLY declared
  producer `Build Scale Up Fan-Out` emitted 0 items; the stored body's connections match the
  committed JSON exactly (no duplicate node names). runData `source` names
  `Recompute Requested Sentinel Gate` (a D-70-23 gate Code node that returned `[]`) as
  `Dispatch Self`'s source, and `Refusal Row Absent Sentinel Gate` as `Build Scale Up Fan-Out`'s.
  On the pre-gap body (Gate 3, 12204–12206) the same declared wiring did NOT run `Dispatch Self`.
  So on this engine (executionOrder absent → legacy) a node can execute with an item that no
  declared connection delivered, apparently when a zero-item Code output is "delivered" onward —
  the same zero-item-delivery rule as G-70-2/3, now shown to reach a single-input node with no
  connection from the sentinel at all. Mechanism NOT isolated; observation only.
  The live instance is now mixed: enrichment = pre-70 `59812be` body (123 nodes, active);
  ingest/review/maintenance/status = gap-closure JSON (69/55/43/30, active, disarmed).

### 5. Gate 5 — disarmed re-proof on the fixed graph (D-70-19)
expected: With the gap-closure JSON live and bounced: `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` → `70-RUNTIME-VERDICT.json` `shapes_equal: true`, four executions settled, `writes_performed: 0`, every `Build Response` / `Build Ingest Response` run reached (no starved Merge), live `settings.executionOrder` recorded. Steps in `70-DEFERRED-GATES.md` § Gate 5.
result: issue
reported: "agent-driven; partial — operator to confirm"
severity: major
observed: |
  Verdict written 07:09Z, `status: observed`, `shapes_equal: false` overall, `writes_performed: 0`,
  `live_settings_execution_order` null on both. INGEST LANE PASSED: `ingest_2x2` (12293) 4/4 and
  `ingest_single_lane` (12309) 2/2 both `shapes_equal: true`, settled — the D-70-23 gated-sentinel
  graph is a faithful match to the engine on the ingest lane. ENRICHMENT LANE FAILED:
  `enrichment_2x2` recovered 8 rows vs 4 predicted (executions 12209/12210 + the first two
  runaway children 12211/12212 matched by run_id echo), `enrichment_single_lane` 4 vs 2
  (12251 + 12254); recovered rows include marker-shaped items (no `action`/`row_id`) — the
  stage Merges/`Build Response` did fire (the 15-input split works) but markers leak into the
  response and the self-dispatch children double the rows. Blocked on G-70-5.

### 6. Gate 6 — armed mixed-verdict re-run on the fixed graph (only after Gate 5 passes)
expected: Same pair as Gate 70-05-A (or equivalent): armed for exactly one contact; `Build Ingest Response` exactly 2 rows; permitted row `action: "update"`, `association: "associated"`; refused row `action: "write_blocked"`; HubSpot shows one update + one association; disarmed and read back after. Steps in `70-DEFERRED-GATES.md` § Gate 6.
result: blocked
blocked_by: prior-phase
reason: "Gate 5 did not pass on the enrichment lane (G-70-5); Gate 6 arms nothing until it does"

## Summary

total: 6
passed: 0
issues: 5
pending: 0
skipped: 0
blocked: 1
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
  status: resolved
  resolved_by: "70-10-PLAN.md (+70-09, 70-11)"
  resolved_at: 2026-09-10
  live_confirmation: "pending Gates 5/6"
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

- gap_id: G-70-3
  truth: "On a disarmed enrichment batch every row reaches Build Response and the recovered rows are shape-equal to the walker's prediction"
  status: resolved
  resolved_by: "70-11-PLAN.md (+70-09)"
  resolved_at: 2026-09-10
  live_confirmation: "pending Gates 5/6"
  reason: "Executions 12204/12205/12206: 0 rows recovered vs 4/2 predicted; Build Response Merge (15 inputs) never executed; Enrichment Gate Merge fired early on Contacts Absent Sentinel's zero-item output and dropped the real rows"
  severity: blocker
  test: 3
  root_cause: "Same engine rule as G-70-2 (zero-item output is a delivery; first delivery per input wins; one fire) applied to the enrichment lane's convergence Merges, where one global sentinel (Contacts Absent Sentinel) feeds many inputs of many Merges with [] whenever contacts are present. Additionally the 15-input Build Response Merge never fired on any execution while every <=10-input Merge did — n8n documents 2-10 inputs; cause not isolated live."
  artifacts:
    - path: "tests/n8n/lib/walkWorkflow.mjs"
      issue: "line 331 drops a zero-item output; the engine delivers it"
    - path: "scripts/build_cloud_workflows.py"
      issue: "starved-lane sentinels share Merge inputs with real producers; Build Response Merge declared with numberInputs 15"
    - path: "n8n/wf_enrichment_cloud.json"
      issue: "Enrichment Gate Merge in1-in4 and Build Response Merge in0-3,11,12 fed by Contacts Absent Sentinel's [] output"
  missing:
    - "Walker RED reproduction of 12206 (zero-item delivery) before any graph change"
    - "Operator design decision on sentinel/Merge separation (see G-70-2) and on splitting Build Response Merge to <=10 inputs or an observed probe of the 15-input node in isolation"
  debug_session: ""

- gap_id: G-70-4
  truth: "prove_phase70_runtime.py compares like with like on the ingest lane"
  status: resolved
  resolved_by: "70-12-PLAN.md"
  resolved_at: 2026-09-10
  live_confirmation: "pending Gates 5/6"
  reason: "Ingest sends differ from the walker only by the client-added reported_outcome key (report.reconcile), so a correct runtime would still read shapes_equal: false"
  severity: minor
  test: 3
  root_cause: "run_live reads rows through dispatch.dispatch (client-reconciled) while predict reads raw Build Ingest Response items from the walker; row_shape keys the comparison on the full key set"
  artifacts:
    - path: "scripts/prove_phase70_runtime.py"
      issue: "row_shape includes every key; recovered ingest rows carry reported_outcome"
  missing:
    - "Compare raw recovery rows (watch.recover_dispatch responses) on the ingest lane, or exclude client-added keys from row_shape — with a test that fails on the 12207 shape first"
  debug_session: ""

- gap_id: G-70-5
  truth: "Deploying the gap-closure enrichment JSON produces no execution the caller did not request; Dispatch Self runs only for a scale_up request with fan_depth < 1"
  status: failed
  reason: "Observed 2026-09-10 07:04–07:10Z: 135 self-dispatched child executions (12211–12348) from four disarmed proof sends; Dispatch Self ran once per execution with a marker item though its only producer emitted 0 items"
  severity: blocker
  test: 4
  root_cause: "NOT isolated. Live facts: stored connections == committed (Dispatch Self <- Build Scale Up Fan-Out only); Build Scale Up Fan-Out emitted 0 items with runData source Refusal Row Absent Sentinel Gate; Dispatch Self emitted 1 item with source Recompute Requested Sentinel Gate; both sources are D-70-23 gate Code nodes that returned []. The pre-gap body (same declared wiring around these nodes) never ran Dispatch Self. Legacy executionOrder (setting absent). A zero-item Code output on this engine can cause a downstream single-input node with NO connection from that node to execute with a marker item."
  artifacts:
    - path: "scripts/build_cloud_workflows.py"
      issue: "Dispatch Self (self-referencing executeWorkflow) has no guard that survives an item arriving outside its declared connection; the gate Code nodes (_sentinel_gate_js) return [] when a lane is live"
    - path: "n8n/wf_enrichment_cloud.json"
      issue: "gap-closure body (291 nodes) loops live; pre-70 59812be body (123 nodes) restored live"
    - path: "tests/n8n/lib/walkWorkflow.mjs"
      issue: "does not model a zero-item output reaching an unconnected node; executeWorkflow node modelled as inert"
  missing:
    - "Remove the self-referencing Dispatch Self / scale_up fan-out from the enrichment graph (feature OFF by default, never used live) until the engine rule is understood — no in-graph guard can be trusted after this observation"
    - "Marker filtering at Build Response: recovered rows on the enrichment lane contained marker-shaped items"
    - "Re-observe the stage-Merge split and Build Response on a loop-free body (Gate 5 re-run) before any armed send"
  debug_session: ""
