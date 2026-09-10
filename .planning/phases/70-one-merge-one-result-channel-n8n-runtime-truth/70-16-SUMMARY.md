---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 16
subsystem: n8n-workflow-generator
tags: [n8n, executionOrder, generator, walker, offline-test-harness, G-70-6, D-70-28, D-70-30]

# Dependency graph
requires:
  - phase: 70 (plan 13/14)
    provides: the gap-closure round 2 generator (WORKFLOW settings emission sites, assert_no_self_dispatch, the frozen 12316 fixture)
provides:
  - "settings.executionOrder = v1 on all eight generated n8n workflow bodies, decided once via WORKFLOW_SETTINGS"
  - "a generation-time refusal (assert_execution_order_v1) that keeps every future body on v1"
  - "a walker (walkWorkflow.mjs) that refuses a non-v1 graph and states which v1 rules it does/does not model"
affects: ["70-17", "70-18"]

actuals:
  tokens: 7429
  tasks: 3
  commits: 3
  plan_head_before: 1ea6db841fc56a12e248fbac81321a9bed9c5fc1

tech-stack:
  added: []
  patterns:
    - "Generation-time contract composition: assert_execution_order_v1 joins assert_no_by_name_reads / assert_merge_input_contract / assert_no_self_dispatch in _assert_generation_contracts, outermost, same raise/name style"
    - "Module-level settings constant emitted as dict(WORKFLOW_SETTINGS) fresh copy at every write site, never a shared mutable object"
    - "Walker refusal with one documented, greppably-confined escape (allowLegacy) for frozen legacy-engine fixtures only"

key-files:
  created:
    - tests/n8n/executionOrderV1.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - n8n/wf_backend_status_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_contact_ingest_local.json
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/n8n/walkWorkflow.test.mjs
    - tests/n8n/walkerEngineFidelity.test.mjs
    - tests/n8n/fixtures/frozen/README.md

key-decisions:
  - "D-70-28 implemented exactly as specified: WORKFLOW_SETTINGS is the single module-level constant, emitted as a fresh dict() copy at all 8 sites, backed by a generation-time refusal (assert_execution_order_v1)."
  - "D-70-30 implemented exactly as specified: walkWorkflow throws on a non-v1 graph unless allowLegacy is passed; allowLegacy is confined to exactly walkerEngineFidelity.test.mjs's three frozen-fixture call sites (allowLegacy_callers=1)."
  - "Three walkWorkflow.test.mjs assertions were ordering-dependent (FIFO shift under legacy vs LIFO pop under v1) and were RE-DERIVED, not force-fitted: 'collapse case (F5)' no longer collapses for this exact topology under v1 (kept, renamed, and re-documented rather than deleted, because it still demonstrates the fragility of a bare by-name last-run read — the reason D-70-01 bans that pattern system-wide); 'respond case' and 'paired-item case' had their expected winner/pairing swapped to match the new dequeue direction, with the underlying rule (first-firing-wins, run-index pairing) unchanged."
  - "Comment text containing the literal idiom/identifier under test (dict(WORKFLOW_SETTINGS) in build_cloud_workflows.py's own doc comment; allowLegacy in walkWorkflow.test.mjs's section banner) was reworded to avoid self-inflating the machine-checked counts — the same class of pitfall the plan's own must_haves warned about for the WORKFLOW_SETTINGS bare-identifier count."

requirements-completed: [D-70-28, D-70-30]

coverage:
  - id: D1
    description: "Every committed n8n/wf_*.json carries settings.executionOrder = v1, decided once via WORKFLOW_SETTINGS and enforced by a generation-time refusal"
    requirement: "D-70-28"
    verification:
      - kind: unit
        ref: "tests/n8n/executionOrderV1.test.mjs"
        status: pass
    human_judgment: false
  - id: D2
    description: "Regeneration diff is settings-only: 8 files, +3/-1 each, node counts unchanged (287/69/55/43/30 cloud, 82/10/13 local); a second consecutive generator run is idempotent"
    requirement: "D-70-28"
    verification:
      - kind: unit
        ref: "git diff HEAD --numstat -- n8n/ (measured: 8 lines, all 3+1) and python3 node-count check (measured live)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The walker refuses a graph whose settings do not declare v1, unless the caller passes the one documented allowLegacy escape, confined to exactly one test file"
    requirement: "D-70-30"
    verification:
      - kind: unit
        ref: "tests/n8n/walkWorkflow.test.mjs#walkWorkflow refuses a graph whose settings do not declare n8n's v1 execution order"
      - kind: unit
        ref: "tests/n8n/walkerEngineFidelity.test.mjs (all 5 cases, using allowLegacy)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The walker's own comments state, per rule, which v1 rule is modelled, not modelled, or unobserved, citing D-70-30; the Merge firing predicate, first-delivery-wins, and fires-at-most-once guards are untouched"
    requirement: "D-70-30"
    verification:
      - kind: unit
        ref: "grep -c D-70-30 tests/n8n/lib/walkWorkflow.mjs (measured: 11) and git diff confined to comments/doc-comment/throw block (verified by hand)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The whole offline harness (node suite, python suite, plugin suite) is green"
    verification:
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1078 pass)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest -q --tb=short (4701 passed, 154 skipped)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests/ -q (2864 passed, 5 skipped)"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 16: Flip every generated n8n workflow to v1 execution order Summary

**Every generated n8n workflow now carries `settings.executionOrder = "v1"` from one shared generator constant with a generation-time refusal backstop, and the offline walker refuses to silently model a legacy body it can no longer justify.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-09-10T10:35:00Z (approx)
- **Completed:** 2026-09-10T11:20:27Z
- **Tasks:** 3
- **Files modified:** 14 (1 created, 13 modified)

## Accomplishments

- Added `WORKFLOW_SETTINGS = {"executionOrder": "v1"}` as the single module-level constant in `scripts/build_cloud_workflows.py`, emitted as a fresh `dict()` copy at all eight body-returning builders — no per-workflow settings decision anywhere in the generator.
- Added `assert_execution_order_v1(wf, name)`, composed into `_assert_generation_contracts` alongside the three existing refusals (`assert_no_by_name_reads`, `assert_merge_input_contract`, `assert_no_self_dispatch`) — a body whose `settings.executionOrder` is not `"v1"` now stops generation with a named error. Demonstrated once in-session by calling the function directly with a forced wrong value (reverted, not committed).
- Regenerated all eight `n8n/wf_*.json` bodies. Diff is settings-only: exactly 8 files, each `+3/-1`. Node counts unchanged: `wf_enrichment_cloud` 287, `wf_contact_ingest_cloud` 69, `wf_review_decision_cloud` 55, `wf_scheduled_maintenance_cloud` 43, `wf_backend_status_cloud` 30, `wf_enrichment_local_live` 82, `wf_enrichment_local` 10, `wf_contact_ingest_local` 13. A second consecutive generator run left the tree byte-identical (idempotence confirmed via `diff -rq`).
- `walkWorkflow` (`tests/n8n/lib/walkWorkflow.mjs`) now throws when a graph's `settings.executionOrder` is not `"v1"` unless the caller passes `allowLegacy`, naming the value found and citing D-70-30. The escape is confined to exactly one test file (`allowLegacy_callers=1`), proved by `walkerEngineFidelity.test.mjs`'s three frozen-fixture cases going green under it — never by a second passing case in `walkWorkflow.test.mjs`.
- Relabelled three comment blocks in the walker citing D-70-30, stating each rule's evidentiary status: (a) zero-items-no-run — the ONE v1 rule this walker models, expected to hold a fortiori under v1; (c) the zero-item-delivery rule in `propagate` — UNOBSERVED under v1 (may have been the legacy `addEmptyItem` push, not a genuine delivery); (b) the end-of-run pass over unfired Merges — NOT MODELLED (reports starvation, does not implement the v1 end-of-run drain, because implementing it now would silently answer the same open question rule (c) leaves open, which D-70-19 forbids).
- Whole offline harness green: `node --test tests/n8n/*.test.mjs` (1078 pass), `.venv/bin/python -m pytest -q --tb=short` (4701 passed, 154 skipped), `operator-claude-plugin/tests/` (2864 passed, 5 skipped).

## Task Commits

1. **Task 1: RED — assert every committed workflow is on v1, and watch it fail on all eight** - `96d5ee4` (test)
2. **Task 2: one shared constant, a generation-time refusal, and all eight bodies regenerated** - `b15be01` (feat)
3. **Task 3: the walker refuses a legacy body, and says which v1 rules it does and does not model** - `26b3b83` (feat)

**Plan metadata:** committed as part of this SUMMARY commit (see below).

## Files Created/Modified

- `tests/n8n/executionOrderV1.test.mjs` - new: asserts every committed workflow is on v1, and that the generator decides it exactly once (idiom-counted, not bare-identifier-counted, to avoid the constant's own comment/error-message self-inflating the count)
- `scripts/build_cloud_workflows.py` - `WORKFLOW_SETTINGS` constant, `assert_execution_order_v1`, 8 emission sites flipped from `{}` to `dict(WORKFLOW_SETTINGS)`, composed into `_assert_generation_contracts`
- `n8n/wf_*.json` (8 files) - regenerated, settings-only diff, node counts unchanged
- `tests/n8n/lib/walkWorkflow.mjs` - non-v1 refusal with `allowLegacy` escape, three comment blocks relabelled per D-70-30
- `tests/n8n/walkWorkflow.test.mjs` - `wf()` helper default flipped to v1; one new RED-then-GREEN refusal test; three existing assertions re-derived under v1's pop-order dequeue
- `tests/n8n/walkerEngineFidelity.test.mjs` - `allowLegacy: true` added at all three `walkWorkflow(` call sites; header reframed as recorded legacy-engine divergences
- `tests/n8n/fixtures/frozen/README.md` - new section explaining why these fixtures can never be regenerated from the current (v1) builder

## Decisions Made

- **Task 1 RED evidence (recorded per plan output spec):** `node --test tests/n8n/executionOrderV1.test.mjs` exited 1 with both cases failing — case 1 listed all eight `n8n/wf_*.json` files with `settings.executionOrder = undefined, want "v1"`; case 2 reported `expected exactly one top-level "WORKFLOW_SETTINGS = " definition, found 0`. `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` printed nothing (prod_changes=[]).
- **Task 2 generation-guard RED message (demonstrated in-session, reverted):** calling `assert_execution_order_v1({"settings": {"executionOrder": "legacy"}, ...}, "wf_test_forced_legacy")` raised: `wf_test_forced_legacy: settings.executionOrder = 'legacy', want "v1" — D-70-28 forbids shipping a workflow on n8n's legacy execution order.`
- **Numstat result:** `git diff HEAD --numstat -- n8n/` printed exactly 8 lines, all `3	1` (added/removed).
- **Node counts (final, python3-verified against the live tree):** `wf_backend_status_cloud.json` 30, `wf_contact_ingest_cloud.json` 69, `wf_contact_ingest_local.json` 13, `wf_enrichment_cloud.json` 287, `wf_enrichment_local.json` 10, `wf_enrichment_local_live.json` 82, `wf_review_decision_cloud.json` 55, `wf_scheduled_maintenance_cloud.json` 43 — all match the plan's must-haves exactly.
- **Assertions re-derived under v1 in `walkWorkflow.test.mjs`** (three, all caused by the `wf()` default flipping legacy's FIFO `shift()` dequeue to v1's LIFO `pop()`):
  1. "collapse case (F5)" — under legacy, both Lane nodes and both Gate runs completed before the by-name Reader ever fired, so the Reader's bare `$('Gate').all()` always returned the LAST Gate run and the first lane's row was lost. Under v1's pop-order, LaneB's entire path (LaneB → Gate run 0 → Reader run 0) resolves to completion before LaneA even starts, so the Reader fires once per Gate run and captures both rows distinctly across its two runs — the collapse does not reproduce for this exact topology. The test was renamed and re-documented (not deleted) to record this as a genuine, re-derived finding: a bare by-name last-run read is fragile under EITHER execution order, which is the actual reason D-70-01 bans it system-wide, independent of which order a given workflow happens to run under.
  2. "respond case" — under v1, `Second` (the last-enqueued edge) now fires before `First` and wins `trace.respond`; `First`'s firing is what gets suppressed. The rule itself ("the first firing wins trace.respond, the second is suppressed") is unchanged; only which named node is chronologically first under this dequeue order changed.
  3. "paired-item case" — under v1, `Upstream`'s run 0 now carries `row-B` (LaneB, the last-enqueued edge) instead of `row-A`, so `Reader`'s run 0 pairs against `row-B` and run 1 against `row-A` (swapped from legacy). The pairing RULE itself (`Reader`'s run *i* pairs against `Upstream`'s run *i*) is unchanged.
- **Avoided two self-inflating literal-string pitfalls**, both of the same shape the plan's own must_haves warned about for the `WORKFLOW_SETTINGS` bare-identifier count: (1) `scripts/build_cloud_workflows.py`'s own doc comment for `WORKFLOW_SETTINGS` originally spelled out the literal idiom `dict(WORKFLOW_SETTINGS)`, which inflated `executionOrderV1.test.mjs`'s idiom count to 9 — reworded to describe the emission without the literal idiom text, restoring the count to exactly 8. (2) `walkWorkflow.test.mjs`'s section-banner comment originally spelled out the literal identifier `allowLegacy`, which would have inflated the Task 3 verify command's `grep -rl 'allowLegacy' tests/n8n/*.test.mjs | wc -l` to 2 — reworded to describe the escape without the literal identifier, restoring the count to exactly 1.

## Deviations from Plan

None - plan executed exactly as written. The three ordering-dependent test re-derivations in `walkWorkflow.test.mjs` and the two literal-string rewordings above were explicitly anticipated and instructed by the plan itself (task 3's action text: "If any existing assertion fails under the resulting pop-order dequeue, RE-DERIVE the expected value under v1 and note the change in the SUMMARY"; and the must_haves' own warning about the bare-identifier count applies structurally to the analogous `allowLegacy` case), not unplanned work requiring a deviation rule.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Nothing in this plan deployed, bounced, armed, or sent anything to n8n Cloud or HubSpot — every live step remains a deferred operator gate (Gates 10/11/12, plan 70-18).

## Next Phase Readiness

- G-70-6's generator half is closed offline: the mechanism that produced every Gate 8 symptom (n8n's legacy `addEmptyItem` push) is no longer inherited by any generated workflow, the choice is enforced once at generation time, and the offline walker no longer silently claims to reproduce an engine mode this repo has retired.
- Ready for plan 70-17 and plan 70-18 (Gates 10/11/12 — disarmed deploy + bounce of the v1 bodies, the D-70-19 proof re-run under v1, and the armed mixed-verdict re-run). Nothing in this plan deploys, bounces, or arms anything — those remain the operator's deferred steps.
- All three artifacts named in `artifacts_this_phase_produces` (`WORKFLOW_SETTINGS`, `assert_execution_order_v1`, `tests/n8n/executionOrderV1.test.mjs`, `allowLegacy`, the non-v1 refusal error) exist exactly as specified, for plans 70-17/70-18 to reference by name.

## Self-Check: PASSED

- FOUND: tests/n8n/executionOrderV1.test.mjs
- FOUND: commit 96d5ee4 (Task 1)
- FOUND: commit b15be01 (Task 2)
- FOUND: commit 26b3b83 (Task 3)

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*
