---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 12
subsystem: infra
tags: [n8n, workflow-generator, merge, sentinel, proof-driver, dispatch, documentation]

requires:
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "70-09/70-10/70-11's fixed graph (walker-fidelity + gated sentinels + Merge-input contract), and the 2026-09-10 disarmed UAT's executions 12200-12208, which this plan closes the comparator on and writes down"
provides:
  - "dispatch.dispatch()'s return dict exposes the RAW pre-reconciliation recovery rows under \"raw_rows\", from the same single recovery call — the reconciled \"rows\" every existing caller reads is unchanged"
  - "prove_phase70_runtime.py's ingest branch (_ingest_recovered_rows) compares the raw recovery against the walker's raw prediction, closing G-70-4 so the driver's own verdict can read shapes_equal: true when the runtime is right"
  - "CLAUDE.md §13.0.2/§13.0.3: the 2026-09-10 UAT's observed-live platform facts, each with its execution id, the corrected deployment-parity state (deployed disarmed 2026-09-10, gap-closure JSON committed ahead again), and the refreshed node-count table (291/69/55/43/30/82/10/13)"
  - "70-DEFERRED-GATES.md § Gate 5 (disarmed redeploy + re-proof) and § Gate 6 (armed mixed-verdict re-run) — the phase's two remaining live proofs, ordered disarmed-before-armed"
affects: [phase-70-close, any-future-phase-reading-CLAUDE.md-13.0.2-or-13.0.3, /gsd-verify-work-70]

actuals:
  tokens: 8333   # chars/4 over the realized diff (dispatch.py, its tests, prove_phase70_runtime.py, its tests, CLAUDE.md, CHANGELOG.md, 70-DEFERRED-GATES.md), dff880d..HEAD
  tasks: 3
  commits: 3
  plan_head_before: dff880d627a9dcd85112500be594d06d971df00f

tech-stack:
  added: []
  patterns:
    - "Additive raw-alongside-reconciled return key: dispatch.dispatch() gained \"raw_rows\" as a sibling of the existing \"rows\", from the SAME recovery call, rather than a second poll or a parameter that changes what \"rows\" means — every existing caller's read of result[\"rows\"] is byte-identical to before this plan."
    - "Comparator selection, not comparator relaxation: G-70-4 was closed by changing WHICH row set prove_phase70_runtime.py's ingest branch feeds into shapes_equal (raw, not reconciled), never by loosening row_shape/shapes_equal themselves — the same comparator that would fail a real Merge regression still would."

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/dispatch.py
    - operator-claude-plugin/tests/test_dispatch_multipart.py
    - scripts/prove_phase70_runtime.py
    - tests/test_prove_phase70_runtime.py
    - CLAUDE.md
    - CHANGELOG.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md

key-decisions:
  - "D-70-22's FIRST option taken, not the fallback. Exposing raw_rows on the dispatch result needed no key-exclusion list to maintain in row_shape, no second poll, and no change to what the operator sees under result[\"rows\"] — the fallback (excluding client-added keys from row_shape) was never reached because the first option held with no caller-invariant conflict."
  - "The RED test targets the row-selection logic, not the comparator. shapes_equal/row_shape are pure functions that already compare correctly given the right inputs; the actual defect was WHICH rows run_live() fed them for the ingest lane. The test therefore asserts against a new named function (_ingest_recovered_rows) that did not exist before this plan, so it fails with AttributeError before the change and passes after — a faithful RED for a fix that lives in row selection, not row comparison."
  - "G-70-1's regression test was already correct when this plan started. test_dispatch_multipart.py already pinned the two-tuple multipart form for both run_id and source_by_field parts (asserted len(part) == 2) — no change was needed there; confirmed by reading, not assumed."
  - "Gates 5 and 6 answered per the standing back-load ruling: recorded in 70-DEFERRED-GATES.md and the plan continued to completion, in the same shape as Gates 1, 70-05-A, 3 and 4 in prior plans of this phase — never waited on mid-flight."
  - "CLAUDE.md's 15-input Merge caveat is recorded as CONFOUNDED, not resolved. Executions 12204-12206 showed the 15-input Build Response Merge never firing, but every one of its inputs also had a starved lane feeding it a sentinel's empty output — the non-firing is fully explained by the same starvation rule observed everywhere else, so the live input-count question was never isolated before the graph was regenerated to 3 stage Merges of <=10 inputs each (plan 70-11). Recording it as settled would have been an evidence-free upgrade the tagging rule forbids."

patterns-established:
  - "A `[documented]` vs `[observed live]` CLAUDE.md fact table row must name the execution id(s) that produced it, and a row whose cause was not isolated from a confound must say so explicitly (CONFOUNDED) rather than being folded into a settled row — precedent for any future live-observation writeup in this repo."

requirements-completed: [D-70-22, D-70-19, D-70-02, D-70-21]

coverage:
  - id: D1
    description: "dispatch.dispatch() exposes raw pre-reconciliation recovery rows under raw_rows, from the same single recovery call; reconciled rows unchanged under rows"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py::test_raw_rows_carries_the_pre_reconciliation_shape_rows_carries_the_reconciled_one"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py::test_armed_dispatch_calls_the_stub_exactly_once_with_the_deployed_contract"
        status: pass
    human_judgment: false
  - id: D2
    description: "prove_phase70_runtime.py's ingest branch compares raw recovery against the walker's raw prediction (G-70-4 closed); the enrichment branch is unchanged"
    verification:
      - kind: unit
        ref: "tests/test_prove_phase70_runtime.py::test_ingest_recovered_rows_reads_the_raw_key_not_the_reconciled_one"
        status: pass
      - kind: unit
        ref: "tests/test_prove_phase70_runtime.py::test_ingest_recovered_rows_defaults_to_empty_when_the_key_is_absent"
        status: pass
    human_judgment: false
  - id: D3
    description: "The RED test built from execution 12207's recorded shape fails before the change (AttributeError on the not-yet-existing helper) and passes after"
    verification:
      - kind: other
        ref: "confirmed live during Task 1: .venv/bin/python -m pytest tests/test_prove_phase70_runtime.py -q -k ingest_recovered_rows failed 2/2 (AttributeError) before the helper was added, passed 2/2 after"
        status: pass
    human_judgment: false
  - id: D4
    description: "G-70-1's regression is pinned: test_dispatch_multipart.py asserts the two-tuple multipart form for both run_id and source_by_field parts"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_dispatch_multipart.py::test_dispatch_with_source_by_field_adds_exactly_one_extra_multipart_part_no_data_kwarg"
        status: pass
    human_judgment: false
  - id: D5
    description: "CLAUDE.md 13.0.3's platform-facts table carries every engine rule the 2026-09-10 UAT observed, each tagged [observed live] with its execution id(s); the 15-input non-firing is recorded as CONFOUNDED, not settled; D-70-02's executionOrder fact is upgraded from documented to observed live"
    verification:
      - kind: other
        ref: "the plan's own Task 2 automated verify (node-count-and-execution-id grep over CLAUDE.md against every n8n/wf_*_cloud.json) — re-run after edits, PASS"
        status: pass
    human_judgment: false
  - id: D6
    description: "13.0.2's deployment-parity note is corrected (deployed disarmed 2026-09-10, gap-closure JSON committed ahead again) and the node-count table refreshed to 291/69/55/43/30/82/10/13"
    verification:
      - kind: other
        ref: "manual read-back against n8n/wf_*.json on disk (291/69/55/43/30/82/10/13) matches the table written into CLAUDE.md"
        status: pass
    human_judgment: false
  - id: D7
    description: "70-DEFERRED-GATES.md carries Gate 5 (disarmed redeploy + re-proof) and Gate 6 (armed mixed-verdict re-run), both naming the proof driver and the disarmed-before-armed ordering rule"
    verification:
      - kind: other
        ref: "grep -q 'Gate 5' && grep -q 'Gate 6' && grep -q 'prove_phase70_runtime.py' 70-DEFERRED-GATES.md — the plan's own Task 3 automated verify, PASS"
        status: pass
    human_judgment: false
  - id: D8
    description: "Gate 5's pass/fail against the live engine and Gate 6's armed mixed-verdict outcome are genuine live observations no test can substitute for"
    verification: []
    human_judgment: true
    rationale: "Both gates require the operator to deploy/bounce/arm the real n8n Cloud instance and observe HubSpot writes — this is exactly the class of proof this phase's own thesis says an offline suite cannot stand in for. Deferred to end-of-phase UAT per the standing 2026-09-09 back-load ruling."

duration: ~35min
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 12: One merge, one result channel — n8n runtime truth (gap closure) Summary

**G-70-4 closed by exposing `dispatch.dispatch()`'s raw pre-reconciliation recovery rows under a new `raw_rows` key and pointing the proof driver's ingest branch at them instead of the client-reconciled rows `report.reconcile` stamps with a `reported_outcome` key the walker never produces; the 2026-09-10 UAT's seven observed-live engine facts (each with its execution id) and the corrected deployment-parity state are written into CLAUDE.md §13.0.2/§13.0.3; Gates 5 and 6 — the disarmed redeploy-and-reprove and the armed mixed-verdict re-run — are recorded in `70-DEFERRED-GATES.md`, ordered disarmed-before-armed.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 7 (2 source, 2 test, 3 docs)

## Accomplishments

- **G-70-4 closed (D-70-22, first option).** `dispatch.dispatch()`'s return dict now carries `raw_rows` — the recovery from `watch.recover_dispatch`, before `report.reconcile` stamps `reported_outcome` — as a sibling of the existing `rows`, from the SAME single recovery call. `prove_phase70_runtime.py` gained `_ingest_recovered_rows(dispatch_result)`, and its `run_live()` ingest branch now reads through it instead of `result.get("rows")`. The comparator functions (`row_shape`, `shapes_equal`) are untouched — the defect was which row set fed them, not how they compared.
- **RED confirmed before GREEN.** A test built from execution 12207's exact recorded shape referenced the not-yet-existing `_ingest_recovered_rows` and failed with `AttributeError` on both new test cases before the helper was added; both passed after. A sanity assertion in the same test proves the OLD source (the reconciled `rows`) is exactly what 12207 showed as unequal — the comparator itself never needed to change.
- **G-70-1's regression was already pinned.** `test_dispatch_multipart.py` already asserted the two-tuple multipart form (`len(part) == 2`, no Content-Type) for both `run_id` and `source_by_field` — read and confirmed, no change needed.
- **CLAUDE.md §13.0.3 gained seven new `[observed live]` platform-fact rows**, each citing its execution id(s): a zero-item Code output IS a Merge-input delivery; the first delivery per input wins; a Merge fires at most once; an unfed input never fires and its downstream terminates silently while the execution still reports `success` (starvation, never a hang); a zero-item node never runs (HTTP form at Gate 1, `12200`; Code/NoOp gate form at Gate 3/70-05-A, `12203`/`12206`, recorded separately per the plan's own instruction not to assume identical behaviour across node types until each is actually seen); the multipart Content-Type defect (`12200` vs `12202`, G-70-1); and the `settings.executionOrder` read — absent on all five live bodies, upgrading D-70-02 from documented to observed live. The 15-input `Build Response Merge`'s non-firing is recorded as **CONFOUNDED** with starvation, not settled as a live input-count ceiling — every one of its inputs also had a starved lane, so the input-count question was never isolated before plan 70-11 split it into 3 stage Merges.
- **§13.0.2's deployment-parity note corrected.** The prior "NOT DEPLOYED. NOTHING ARMED." claim was stale: the operator DID deploy and bounce the pre-gap-closure Phase 70 JSON disarmed on 2026-09-10 for Gates 1 and 3, and it is still live. The node-count table gained a third column (291/69/55/43/30/82/10/13 — the gap-closure JSON, committed but not yet redeployed) alongside the pre-Phase-70 and Phase-70-as-shipped-2026-09-09 columns already there.
- **CHANGELOG.md** gained a `### Fixed` entry naming G-70-1 through G-70-4 and their fixing commits/plans, and the stale "committed, NOT deployed" / "Not yet done" language was corrected to match the actual live state.
- **Gates 5 and 6 recorded in `70-DEFERRED-GATES.md`**, in the same shape as Gates 1, 70-05-A, 3 and 4: Gate 5 (disarmed) redeploys the gap-closure JSON and re-runs the exact D-70-19 proof Gate 3 ran, now against the fixed graph — its pass criteria include the three stage Merges that replaced the 15-input `Build Response Merge` all firing. Gate 6 (armed, Gate 5 must pass first) re-runs the mixed-verdict batch Gate 70-05-A found wrong on execution `12203`, against the fixed graph. Both name the ordering rule (disarmed before armed) and note that if Gate 4 (the pre-Phase-70 rollback) was already run, Gate 5 supersedes it.
- **Whole offline harness stayed green throughout:** `node --test tests/n8n/*.test.mjs` 1064/1064, root `pytest` 4690 passed/154 skipped, plugin `pytest` 2865 passed/5 skipped (up from the 70-11 baseline by exactly the tests this plan added).

## Task Commits

1. **Task 1: G-70-4 — compare like with like on the ingest lane** — `3f35926` (test)
2. **Task 2: Record the platform facts this UAT bought, tagged and cited** — `928ce81` (docs)
3. **Task 3: Gates 5 and 6 — the two live proofs that end the phase** — `3adf02f` (docs)

**Plan metadata:** commit created immediately after this SUMMARY is written (see the final `commit` step of execute-plan.md).

## Files Created/Modified

- `operator-claude-plugin/scripts/dispatch.py` — return dict gains `raw_rows` (pre-reconciliation recovery), documented in the module docstring's Return shape and a D-70-22 comment at the write site.
- `operator-claude-plugin/tests/test_dispatch_multipart.py` — asserts `result["raw_rows"] == []` in the deployed-contract test, plus a dedicated test proving `raw_rows` lacks `reported_outcome` while `rows` carries it (reconciled/downgraded).
- `scripts/prove_phase70_runtime.py` — new `_ingest_recovered_rows(dispatch_result)` helper; `run_live()`'s ingest branch reads through it instead of `result.get("rows")`.
- `tests/test_prove_phase70_runtime.py` — two new tests built from execution 12207's recorded shape, confirmed RED before the helper existed.
- `CLAUDE.md` — §13.0.2's node-count table and deployment-parity paragraph extended and corrected with a 2026-09-10 addendum; §13.0.3's platform-facts table gained seven new `[observed live]` rows.
- `CHANGELOG.md` — `### Fixed` entry for the gap closure; stale deployment-state language in the existing Phase 70 entries corrected.
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md` — Gate 5 and Gate 6 sections appended.

## Decisions Made

- Took D-70-22's first option (expose `raw_rows`) rather than the fallback (exclude client-added keys from `row_shape`) — no caller-invariant conflict was found, so the fallback was never needed. See `key-decisions` in frontmatter for the full rationale, including why the RED test targets the new row-selection function rather than the (unchanged) comparator.
- Recorded the 15-input Merge's live non-firing as CONFOUNDED rather than folding it into the settled starvation rows — the tagging rule (§13.0.3) forbids upgrading a claim past what was actually isolated.
- Answered the Task 3 checkpoint per the standing 2026-09-09 operator ruling: recorded Gates 5 and 6 in `70-DEFERRED-GATES.md` and continued the plan to completion, rather than stopping the executor mid-plan to wait on a live human action — identical to how Gates 1, 70-05-A, 3 and 4 were handled in prior plans of this phase.

## Deviations from Plan

None - plan executed exactly as written. G-70-1's regression test was already correctly pinned when this plan started (confirmed by reading, not a deviation — the plan itself anticipated this: "if it does not [pin the two-tuple form], fix it here").

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required by this plan. Gates 5 and 6 (the live deploy/bounce/arm actions) are the operator's deferred actions, recorded in `70-DEFERRED-GATES.md` for end-of-phase UAT — not a setup step, and nothing was deployed, bounced or armed by this executor.

## Next Phase Readiness

- The phase's own verdict comparator (`prove_phase70_runtime.py`) can now read `shapes_equal: true` when the runtime is right — Gate 5's re-run will no longer trip on the client-added `reported_outcome` key that made execution 12207 look wrong when it wasn't.
- CLAUDE.md and CHANGELOG.md now correctly state that the pre-gap-closure Phase 70 JSON is live and disarmed, and that the gap-closure JSON (this plan's own commits included) is committed but not yet redeployed.
- Gates 5 and 6 join Gates 1, 70-05-A, 3 and 4 in `70-DEFERRED-GATES.md`, all exercised together at end-of-phase UAT (`/gsd-verify-work 70`). Gate 5 must pass before Gate 6 is attempted.
- This is the last plan in Phase 70's gap-closure wave; the offline harness (node/root-Python/plugin-Python) is fully green and no further code changes are anticipated before the operator's live gates run.

## Self-Check: PASSED

- `scripts/prove_phase70_runtime.py` — FOUND
- `operator-claude-plugin/scripts/dispatch.py` — FOUND
- `CLAUDE.md` — FOUND
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md` — FOUND
- Commit `3f35926` — FOUND in `git log --oneline --all`
- Commit `928ce81` — FOUND in `git log --oneline --all`
- Commit `3adf02f` — FOUND in `git log --oneline --all`
- `.venv/bin/python -m pytest tests/test_prove_phase70_runtime.py -q` — 19 passed
- `cd operator-claude-plugin && ../.venv/bin/python -m pytest -q` — 2865 passed, 5 skipped
- `.venv/bin/python -m pytest -q` (root) — 4690 passed, 154 skipped
- `node --test tests/n8n/*.test.mjs` — 1064/1064 pass
- Task 2's automated verify (node-count-and-execution-id grep over CLAUDE.md) — PASS
- Task 3's automated verify (`grep -q "Gate 5"/"Gate 6"/"prove_phase70_runtime.py"` in `70-DEFERRED-GATES.md`) — PASS
- Nothing deployed, nothing bounced, nothing armed — no deploy/bounce/arming script was invoked by this executor.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*
