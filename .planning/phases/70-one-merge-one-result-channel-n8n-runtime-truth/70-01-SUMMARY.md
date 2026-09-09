---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 01
subsystem: testing
tags: [n8n, workflow-execution-model, code-review-instrumentation, python-build-script]

requires: []
provides:
  - "walkWorkflow(wf, opts) — a connections-driven offline interpreter for committed n8n workflow JSON, with its own CLI entry"
  - "walkWorkflow.mjs's own RED-detection unit tests, proving it can see the F5 collapse, a Merge-input hang, and a double-Respond first-only read on synthetic graphs"
  - "detect_by_name_reads(wf) in scripts/build_cloud_workflows.py, proven non-zero against all three committed cloud workflows today"
affects: [70-02, 70-03, 70-04, 70-05, 70-06, 70-07]

actuals:
  tokens: 10988
  tasks: 3
  commits: 3
plan_head_before: af6496d49140cb845b34a942fe55aef6f6982896

tech-stack:
  added: []
  patterns:
    - "Offline n8n graph replay: fire a node once per inbound-edge delivery (not once per node), matching n8n's own documented multi-run semantics — the same model every later Phase 70 plan's acceptance runs through"
    - "Whole-workflow detector as a post-pass function, same insertion convention as _normalize_hubspot_auth, deliberately NOT wired into main() yet"

key-files:
  created:
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/n8n/walkWorkflow.test.mjs
    - tests/n8n/fixtures/walkerSmoke.json
    - tests/test_no_by_name_reads.py
  modified:
    - scripts/build_cloud_workflows.py

key-decisions:
  - "walkerSmoke.json (nominally a Task 2 artifact) was created during Task 1, because Task 1's own <verify> command depends on it — the plan's file listing under-specified this ordering."
  - "n8n-nodes-base.extractFromFile is treated as an explicit identity-passthrough type (alongside noOp), not the generic unhandled-type fallback — real CSV/binary decode is n8n's own well-tested built-in, and modelling it here would prove nothing about the graph. Fixtures seed the trigger with already-extracted row items."
  - "Merge nodes fire exactly ONCE per replay in this walker (buffer until every configured input has delivered, then combine and lock) rather than modelling n8n's real multi-wave re-firing — sufficient for every test this plan requires and documented as a deliberate simplification, not asserted as n8n's full behaviour."
  - "alwaysOutputData is checked per producing node's own zero-item branch, not per downstream consumer — resolved the plan's own 'which placement n8n honours is unverified' note by picking ONE coherent, testable semantic and writing both directions of the mutually-exclusive-branch test against it."

requirements-completed: [D-70-16, D-70-18, D-70-03, D-70-04]

coverage:
  - id: D1
    description: "walkWorkflow.mjs replays n8n/wf_contact_ingest_cloud.json (29 nodes) from its own connections map with zero unhandled node types"
    requirement: D-70-16
    verification:
      - kind: integration
        ref: "node tests/n8n/lib/walkWorkflow.mjs --workflow n8n/wf_contact_ingest_cloud.json --rows tests/n8n/fixtures/walkerSmoke.json --node 'Build Ingest Response'"
        status: pass
    human_judgment: false
  - id: D2
    description: "the walker's own unit tests prove it detects the F5 collapse, the Merge-input hang, and the double-Respond first-only read on synthetic graphs (D-70-18 RED evidence)"
    requirement: D-70-18
    verification:
      - kind: unit
        ref: "node --test tests/n8n/walkWorkflow.test.mjs (9 tests, 0 failures)"
        status: pass
    human_judgment: false
  - id: D3
    description: "detect_by_name_reads finds all three by-name-read shapes (quoted, dynamic, run_recovery_inlined) and reports a non-zero count against build_cloud(), build_enrichment_cloud(), build_review_decision_cloud() today"
    requirement: "D-70-03, D-70-04"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_no_by_name_reads.py -q (7 tests, 0 failures)"
        status: pass
    human_judgment: false
  - id: D4
    description: "generation is byte-identical to the committed n8n/*.json — no graph JSON changed in Wave 0"
    verification:
      - kind: integration
        ref: "git status --porcelain -- n8n/ (empty after running scripts/build_cloud_workflows.py)"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-09
status: complete
---

# Phase 70 Plan 01: Graph walker and by-name-read detector Summary

Built the offline instrument this phase is judged by — a connections-driven n8n graph
replayer that fires nodes once per inbound-edge delivery (proven on synthetic graphs to
detect the F5 row-collapse, a Merge-input hang, and a double-`Respond` first-only read),
plus a builder-side detector that already finds 141 by-name-read violations across the
three committed cloud workflows today (10 + 119 + 12), covering all three shapes the
migration in later plans must retire to zero.

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-09-09
- **Tasks:** 3 completed
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- `tests/n8n/lib/walkWorkflow.mjs` replays `n8n/wf_contact_ingest_cloud.json` end to end
  (29 nodes, all real HTTP/HubSpot/Code/IF/Set/extractFromFile node types handled, zero
  `trace.unhandledTypes`) from a hand-built two-row fixture, with a CLI entry
  (`--workflow --rows --node`) later plans' proof drivers can subprocess.
- The walker's own 9-test suite (`tests/n8n/walkWorkflow.test.mjs`) proves — on
  synthetic graphs, not the real (still-broken) workflows — that it can see: the F5
  collapse (execution 12163's exact shape: a by-name bare `.all()` reader loses the
  first of two upstream lanes entirely), a real Merge fixing that same shape (both rows,
  one run), a Merge whose second input never fires (never fires, `trace.stalled` names
  it and the missing index), `alwaysOutputData` satisfying a starved Merge input only
  when the flag sits on the node that actually ran (not the downstream node that never
  got a delivery), a double-`Respond` recording only the first firing, `.item`
  paired-run resolution, and a 2-lane × 2-row mixed batch through a Merge returning
  exactly 4 rows with no duplicates.
- `detect_by_name_reads` in `scripts/build_cloud_workflows.py` walks every node's
  `parameters` tree (not jsCode-only) and finds the quoted accessor form, the dynamic
  `$(name)` call form, and an inlined `nodeRunRecovery.js` — proven against a
  hand-built clean workflow (zero) and against all three committed cloud builders
  (10/119/12, non-zero) in the same test run.

## Task Commits

1. **Task 1: Graph walker over the committed JSON** — `6c013a8` (feat)
2. **Task 2: The walker's own RED-detection unit tests** — `dd9a166` (test)
3. **Task 3: By-name-read detector in the builder** — `59812be` (feat)

## Files Created/Modified

- `tests/n8n/lib/walkWorkflow.mjs` — the interpreter: `loadWorkflow`, `walkWorkflow`,
  `runNode`, `nodeItems`, plus a CLI entry.
- `tests/n8n/fixtures/walkerSmoke.json` — the two-row ingest fixture (one update-path
  match, one create-path net_new) driving the Task 1 CLI verify.
- `tests/n8n/walkWorkflow.test.mjs` — the walker's own 9-test RED-detection suite.
- `scripts/build_cloud_workflows.py` — added `detect_by_name_reads`,
  `_iter_param_strings`, `_run_recovery_marker`, `_BY_NAME_READ_RE`, placed beside
  `_normalize_hubspot_auth`. NOT called from `main()`.
- `tests/test_no_by_name_reads.py` — the detector's own 7-test proof, including the
  RED-today assertion against all three committed cloud workflows.

## Decisions Made

- `walkerSmoke.json` was authored during Task 1 (not deferred to Task 2 as the plan's
  file listing implied), because Task 1's own `<verify>` command requires it to exist.
- `n8n-nodes-base.extractFromFile` is an explicit passthrough type, not the generic
  "any other type" fallback — real CSV/binary decoding is n8n's own tested built-in;
  modelling it would add complexity that proves nothing about graph execution order.
  Fixtures seed the trigger with already-"extracted" row objects.
- Merge nodes fire exactly once per replay (buffer-until-ready, then lock) rather than
  modelling n8n's real multi-wave Merge re-firing — sufficient for every required test
  and documented in the module's own comments as a deliberate simplification, not
  claimed as n8n's full behaviour.
- Resolved the plan's own "which `alwaysOutputData` placement n8n honours on a real
  build is unverified" note by picking one coherent, testable rule (checked per
  producing node's own zero-item output branch) and writing both directions of the
  mutually-exclusive-branch test against it, rather than leaving the semantic undefined.

## Deviations from Plan

None — plan executed exactly as written. (The `walkerSmoke.json` authoring-order note
above is a scheduling clarification, not a deviation from what was built.)

## Issues Encountered

None. Tracing the real `wf_contact_ingest_cloud.json` node-by-node (Map Columns ->
Normalize Phone -> Build Verify Batch -> Verify Emails -> HubSpot Search by Email ->
Resolve Identity -> Merge Contacts -> Build/Adapt Company Link -> Decide Action) showed
that with the committed disarmed constants (`ALLOW_HUBSPOT_RECORD_WRITES = "false"`,
`ALLOW_HUBSPOT_CREATE = "false"`), every row resolves to `write_blocked` or `review` at
`Decide Action` — so `HubSpot Update`/`HubSpot Create`/`HubSpot Associate Company` are
never reached by the smoke fixture's two rows, and needed no stubs.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`tests/n8n/lib/walkWorkflow.mjs` and `detect_by_name_reads` are ready for 70-02, which
(per the roadmap) probes `alwaysOutputData` placement live and begins introducing real
Merge nodes into the committed workflows — the walker is the offline proof instrument
for that work, and the detector's non-zero baseline (10/119/12) is what 70-04's
flip-to-zero gate will measure against. No blockers.

## Self-Check: PASSED
