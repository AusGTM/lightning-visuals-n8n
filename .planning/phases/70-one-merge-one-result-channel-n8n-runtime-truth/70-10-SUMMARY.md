---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 10
subsystem: infra
tags: [n8n, workflow-generator, merge, sentinel, walker, offline-harness]

requires:
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "70-09's corrected walker (D-70-19/D-70-20 engine rules) and the synthetic mechanism-pricing pair that priced D-70-23's gated-sentinel design before regeneration"
provides:
  - "D-70-23 recorded: gated sentinel mechanism, amending D-70-20"
  - "Class fix in scripts/build_cloud_workflows.py: _add_starved_lane_sentinel wires condition -> gate -> targets; a sentinel's own empty output can no longer pre-empt a real row on a shared Merge input"
  - "Ingest lane: Associate Lane Sentinel bypasses Associate Carry Merge, targeting Ingest Merge Response directly; two routing-IF-direct-to-Merge edges retargeted through pass-throughs; a new Build Association Request Merge closes a genuine unguarded two-lane convergence"
  - "tests/n8n/mergeInputContract.test.mjs: structural Merge-input contract over every committed workflow, PENDING list exact"
affects: [70-11-plan-enrichment-review-local-live-lanes]

actuals:
  tokens: 16512   # chars/4 over scripts/build_cloud_workflows.py + tests/n8n/*.test.mjs + tests/test_merge_helpers.py + 70-CONTEXT.md diffs. Excludes the 8 generated n8n/wf_*.json (2.4MB of derived JSON, not authored) and the frozen-fixture snapshot (long single-line jsCode strings inflate a byte diff far past the semantic size of the change).
  tasks: 3
  commits: 3
  plan_head_before: c6cd191

tech-stack:
  added: []
  patterns:
    - "Gated sentinel: a starved-lane sentinel's condition node feeds a dedicated gate node, never the target directly — a node fed zero items never runs (engine rule, execution 12200), so the gate makes no delivery when the condition decides the lane is live, closing the race a zero-item OUTPUT (also a real delivery, executions 12204-12206) used to create."
    - "Carry-Merge bypass: a positional (combineByPosition) carry Merge is never padded with a sentinel marker on both its inputs — the sentinel targets the carry Merge's own real CONSUMER instead, leaving the carry Merge itself free to legitimately never fire."
    - "IF-to-Merge pass-through: a routing IF never has a direct edge to a Merge input; a plain Code pass-through sits between them so the input's fed-or-not state depends only on the one rule this repo has observed (a node fed zero items never runs), never on the unobserved question of whether an IF's own empty branch is itself a delivery."

key-files:
  created:
    - tests/n8n/mergeInputContract.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - tests/n8n/writeGateShape.test.mjs
    - tests/n8n/ingestMixedBatch.test.mjs
    - tests/n8n/ingestTracerFlow.test.mjs
    - tests/test_merge_helpers.py
    - tests/fixtures/companies_jscode_frozen.json
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md

key-decisions:
  - "D-70-23: Option B, gated sentinel — the sentinel keeps SHARING the real producer's Merge input, gated so it delivers nothing when the lane is live."
  - "Carry-merge starvation on Update/Create Carry Merge (a fully-refused batch) fixed by inserting a real APPEND Merge (Build Association Request Merge) in front of the previously-unguarded two-lane convergence into Build Association Request, rather than forcing the combineByPosition carry Merges themselves to always fire — the latter fabricates a paired row on one lane's own positional combine when the other lane races it (Rule 1, found running this task's own suite)."
  - "Two routing-IF-direct-to-Merge edges retargeted on the ingest lane only (Update/Create Write Gate IF's true branch into its own carry Merge); the enrichment lane's equivalent edges are left alone this plan, per the plan's own explicit scope and an existing pinned test — deferred to plan 70-11."

patterns-established:
  - "Every pre-existing 'identity-less sentinel marker' filter idiom (`Object.keys(it.json || {}).length > 0`) in the whole generator is rewritten once, in code_node(), to also exclude SENTINEL_MARKER_KEY — never per response-builder site."

requirements-completed: [D-70-20, D-70-19, D-70-01, D-70-14, D-70-15]

coverage:
  - id: D1
    description: "D-70-23 recorded in 70-CONTEXT.md before any regeneration"
    verification:
      - kind: other
        ref: "grep -q D-70-23 .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md"
        status: pass
    human_judgment: false
  - id: D2
    description: "_add_starved_lane_sentinel gates every sentinel; wire_gate_refusal_lane's mirror walk follows the gate; the reserved marker key is filtered by every pre-existing consumer idiom"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeInputContract.test.mjs#PENDING names exactly the workflows that violate the contract, in both directions"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichmentBatchRefusal.test.mjs#list-expansion refusal: the reason reaches Build Response as a row, and the responder still answers with the ack only"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ingest lane: Associate Lane Sentinel bypasses Associate Carry Merge; the armed-mixed-verdict case, the fully-refused case, and the armed-permitted-no-company case all pass"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs#ingest, ARMED with a mixed verdict: the permitted row keeps its association and the refused row reports blocked"
        status: pass
      - kind: unit
        ref: "tests/n8n/ingestMixedBatch.test.mjs#ingest, ARMED with a permitted update that resolves NO company: the association lane input is satisfied by the sentinel, never by a padded carry Merge"
        status: pass
      - kind: unit
        ref: "tests/n8n/ingestMixedBatch.test.mjs#ingest fully-refused batch (disarmed, every row a would-be update): every row returns once carrying its refusal reason"
        status: pass
    human_judgment: false
  - id: D4
    description: "n8n_arming.set_write_safety still rewrites all three declaring nodes on the regenerated ingest lane (T-70-40)"
    verification:
      - kind: other
        ref: "n8n_arming.set_write_safety() against n8n/wf_contact_ingest_cloud.json reports {ALLOW_HUBSPOT_RECORD_WRITES: 3, TEST_RECORD_IDS: 3}"
        status: pass
    human_judgment: false
  - id: D5
    description: "Regeneration is idempotent; zero regressions against the full pre-Plan-10 node suite; pytest green"
    verification:
      - kind: other
        ref: "python scripts/build_cloud_workflows.py twice; git diff --quiet -- n8n/"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1046 tests, 1027 pass, 19 fail — all 19 pre-existing per 70-WALKER-RED-INVENTORY.md, zero new regressions vs the 26-fail pre-Plan-10 baseline)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest (4679 passed, 154 skipped)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The Merge-input contract test (Task 3) — structural rules over every committed workflow, dynamic replay for the ingest lane, exhaustive bucket partition for the rest"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeInputContract.test.mjs (15 tests, all pass)"
        status: pass
    human_judgment: false

duration: ~3h (continuation session, Task 1 already committed at start)
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 10: Gate every sentinel, bypass the starved carry Merge Summary

**A sentinel's own zero-item output can no longer pre-empt a real row on a shared Merge input anywhere in the generator (D-70-23's gated sentinel), and the ingest lane that failed live on 2026-09-10 (execution 12203) is now correct offline under an instrument that reproduces the engine, proven by a new structural contract test over every committed workflow.**

## Performance

- **Tasks:** 3 (checkpoint:decision, tracer, auto)
- **Files modified:** 11 modified, 1 created (across the 3 commits)
- **Commits:** 3 (`51899bb` D-70-23 decision record, `ce78a3b` the generator fix, `2cf161b` the contract test)

## Accomplishments

- **D-70-23 recorded**: the operator's ruling (Option B, gated sentinel) amending D-70-20, with the executions that motivated it and the clauses that stand unchanged.
- **The defect class retired at its one source**: `_add_starved_lane_sentinel` (used by every sentinel on every lane, ~50+ call sites) now wires "condition -> gate -> targets" instead of "condition -> targets" directly. A sentinel's condition node still runs every execution (fed the real lane's row set) and its own output can still be empty — but that empty output now feeds a GATE, and a node fed zero items never runs (the engine's own rule, execution 12200), so the gate makes no delivery at all rather than the zero-item delivery that used to win Merge-input races against a real row (executions 12203, 12206).
- **The ingest lane's carry-Merge bypass**: `Associate Lane Sentinel` no longer pads both inputs of the positional `Associate Carry Merge` (which would fabricate a paired row, T-70-41) — it targets `Ingest Merge Response`'s own association-lane input directly, the same input the carry Merge feeds, mutually exclusive with it by construction.
- **Two more routing-IF-direct-to-Merge edges found and retargeted** on the ingest lane (the write-gate IF's true branch into its own per-hop carry Merge), through a pass-through — the same defensive posture already used for the refusal-lane edge.
- **A genuine D-70-01 gap closed as a side effect of making the fix correct**: `Build Association Request` was converged by two carry Merges with no explicit Merge in front of it. Forcing those two `combineByPosition` carry Merges to never-stall directly (the first attempt) fabricated a paired write response on one lane whenever the other lane raced it — caught by this task's own new test, not by inspection. The fix is a real `Build Association Request Merge` (append-mode), the D-70-01-compliant shape, with the never-stall sentinels targeting it instead.
- **The reserved marker key's consumers, fixed at the one place they're all defined**: every pre-existing "identity-less sentinel marker" filter idiom in the generator (`Object.keys(it.json || {}).length > 0`, used ~10 times across enrichment/review/ingest response builders) is now rewritten once, in `code_node()`, to also exclude `SENTINEL_MARKER_KEY` — because a gated marker now carries a key instead of being a bare `{}`, and this fixed a genuine regression (`list-expansion refusal` on the enrichment lane) discovered by running the full node suite before committing.
- **`tests/n8n/mergeInputContract.test.mjs`**: a new structural test reading every committed `n8n/wf_*.json`'s connections map, asserting the class of rule this defect violated fifty times, with an exact-both-directions pending list naming exactly the three workflows (`wf_enrichment_cloud.json`, `wf_enrichment_local_live.json`, `wf_review_decision_cloud.json`) plan 70-11 still owns.

## Task Commits

1. **Task 1: D-70-23 — the sentinel mechanism, decided on the Wave 1 measurement** — `51899bb` (docs)
2. **Task 2: Gate every sentinel in the generator; bypass the starved carry Merge; prove it on the ingest lane** — `ce78a3b` (feat)
3. **Task 3: The Merge-input contract — a structural test over every committed workflow** — `2cf161b` (test)

No separate plan-metadata commit — `commit_docs` scope for this continuation covers only the SUMMARY/STATE update step below, per the objective's explicit "Do NOT update STATE.md or ROADMAP.md."

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `_add_starved_lane_sentinel` (gated), `_sentinel_gate_js`, `SENTINEL_MARKER_KEY`, `wire_gate_refusal_lane`'s mirror walk (follows the gate) and new `carry_merge` parameter, `_add_merge_passthrough`, `_retarget_merge_edge_through_passthrough`, `code_node`'s global marker-filter rewrite, the ingest lane's `Build Association Request Merge` and the two IF-passthrough retarget call sites.
- `n8n/wf_contact_ingest_cloud.json` (50 -> 69 nodes), `n8n/wf_enrichment_cloud.json` (218 -> 260 nodes), `n8n/wf_enrichment_local_live.json`, `n8n/wf_enrichment_local.json` (marker-filter fix only, 4 lines), `n8n/wf_review_decision_cloud.json` — regenerated, never hand-edited.
- `tests/n8n/writeGateShape.test.mjs` — updated the two structural assertions that pinned the old "sentinel/IF feeds the merge directly" wiring (see Deviations); added the `passthrough` shape branch to the carry-merge feeder test.
- `tests/n8n/ingestMixedBatch.test.mjs` — `assertAckFiredOnce` now excludes the three intentionally-bypassed carry Merges from its stall check; added the armed-permitted-no-resolvable-company acceptance case (D-70-23's own named audit shape).
- `tests/n8n/ingestTracerFlow.test.mjs` — the review-only test's blanket `trace.stalled == []` narrowed to exclude `Associate Carry Merge`, with the reason documented inline.
- `tests/test_merge_helpers.py` — the ingest lane's append-Merge count assertion widened from exactly-one to the two legitimate append Merges (`Ingest Merge Response`, `Build Association Request Merge`).
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined (an explicit, reviewed act per the fixture's own header rule): `Merge Company`'s jsCode changed by exactly one addition, `&& it.json['_gsd_sentinel_marker'] !== true`, on the pre-existing identity-less-marker filter line. No other line in the fixture changed.
- `tests/n8n/mergeInputContract.test.mjs` — new, 297 lines, 15 tests.
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md` — D-70-23 entry.

## Sentinel replay-shape table (ingest lane)

Every sentinel `_add_starved_lane_sentinel` (or `wire_gate_refusal_lane`) creates on the ingest lane, its starved-branch replay shape, and its live-branch replay shape:

| Sentinel | Starved (marker fires) | Live (marker silent) |
|---|---|---|
| Review Lane Sentinel | every decided row is action update/create | at least one row is not update/create |
| Associate Lane Sentinel | no row is (update-or-create AND has company_id AND write-permitted) | at least one row is |
| HubSpot Update Gate Unreached Sentinel | no row has `action === "update"` | at least one row does |
| HubSpot Update No Refusal Sentinel | the gate ran and every row it saw was `write_allowed === true` | the gate ran and refused at least one row |
| HubSpot Update Carry Unreached Sentinel | no row has `action === "update"` (same predicate as Gate Unreached; targets `Build Association Request Merge`'s own input) | at least one row does |
| HubSpot Update Carry All Refused Sentinel | the gate ran and no row was `write_allowed === true` | the gate ran and at least one row was allowed |
| HubSpot Create Gate Unreached Sentinel | no row has `action === "create"` | at least one row does |
| HubSpot Create No Refusal Sentinel | the gate ran and every row it saw was `write_allowed === true` | the gate ran and refused at least one row |
| HubSpot Create Carry Unreached Sentinel | no row has `action === "create"` (targets `Build Association Request Merge`'s own input) | at least one row does |
| HubSpot Create Carry All Refused Sentinel | the gate ran and no row was `write_allowed === true` | the gate ran and at least one row was allowed |

All ten are exercised, starved and live, by the existing/new suites: `ingestMixedBatch.test.mjs`'s three primary cases (2x2 mixed, single-lane, fully-refused) plus its new armed-no-company case, and `writeGateShape.test.mjs`'s armed-mixed-verdict case.

## Decisions Made

- **D-70-23** (recorded, `51899bb`): gated sentinel, amending D-70-20. See `70-CONTEXT.md`.
- **The `Build Association Request Merge` decision** (not named in the plan's own read_first, discovered running the task's own suite): forcing `Update Carry Merge`/`Create Carry Merge` to never stall directly — the initially obvious fix — fabricates a real association-write response on one lane's own positional `combineByPosition` combine whenever a marker satisfies one input while the other lane's real content races it (proven with a debug replay: `Associate Carry Merge` came back `association: "not_confirmed"` for a genuinely associated row). The correct fix inserts a real, append-mode Merge (`Build Association Request Merge`) in front of the previously-unguarded two-lane convergence into `Build Association Request` — the D-70-01-compliant shape this convergence should have had from the start — and targets the never-stall sentinels at THAT merge instead of at either carry Merge's own input.
- **The `carry_merge` parameter on `wire_gate_refusal_lane`** targets `Build Association Request Merge`, never the write node's own carry Merge — documented in the function's own docstring with the Rule 1 citation, so a future call site cannot repeat the mistake.
- **Two ingest-only pass-through retargets** (`_retarget_merge_edge_through_passthrough` on the write-gate IF's true branch into its own carry Merge) — scoped to the ingest lane only, since the enrichment lane has an existing pinned test (`writeGateShape.test.mjs`'s carry-merge feeder test) asserting the DIRECT IF-to-Merge edge for that lane, and the plan explicitly defers the enrichment lane's own pass-through audit to plan 70-11.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `Build Association Request` was a genuine, unguarded two-lane D-70-01 convergence**
- **Found during:** Task 2, running `ingestMixedBatch.test.mjs`'s fully-refused case after the first carry-Merge fix
- **Issue:** `Update Carry Merge` and `Create Carry Merge` both fed `Build Association Request` (a plain Code node) with two separate inbound edges and no explicit Merge — a pre-existing gap this task's own change exposed by making the carry Merges reliably deliver *something* even on a starved lane.
- **Fix:** Added `Build Association Request Merge` (append-mode `splice_merge_before`), targeted the never-stall sentinels at it instead of at either carry Merge's own input.
- **Files modified:** `scripts/build_cloud_workflows.py`, all regenerated ingest workflow JSON.
- **Verification:** `ingestMixedBatch.test.mjs`'s three primary cases plus the new armed-no-company case, all green; debug replay confirmed `association: "associated"` (not `"not_confirmed"`) for the real row.
- **Committed in:** `ce78a3b`

**2. [Rule 1 - Bug] Every pre-existing "identity-less sentinel marker" filter idiom silently admitted a gated marker**
- **Found during:** Task 2, running the full node suite (`node --test tests/n8n/*.test.mjs`) before committing — `enrichmentBatchRefusal.test.mjs`'s `list-expansion refusal` test went from green to red (15 rows instead of 1).
- **Issue:** `_sentinel_gate_js()` stamps a reserved key onto its one marker item (acceptance criterion) — but every pre-existing consumer that filtered "identity-less" markers by checking `Object.keys(it.json).length > 0` no longer excluded the marker, since it was no longer a bare `{}`.
- **Fix:** Rewrote the filter idiom once, in `code_node()`, applied to every Code node's jsCode at generation time — not per response-builder site.
- **Files modified:** `scripts/build_cloud_workflows.py`; every workflow whose response builder used the idiom regenerated.
- **Verification:** `enrichmentBatchRefusal.test.mjs`'s `list-expansion refusal` case green again; full node suite confirmed zero regressions against the pre-Plan-10 baseline (26 red -> 19 red, all 19 pre-existing).
- **Committed in:** `ce78a3b`

**3. [Rule 4 - architectural, resolved by updating pinned assertions] The plan's own acceptance wording "zero Merge inputs fed by both a sentinel chain and a real producer" is superseded by D-70-23.**
- **Context:** Task 2's acceptance criteria (written against D-70-20's original, un-amended mechanism) literally forbids any Merge input from being fed by both a sentinel and a real producer. D-70-23's whole design — the operator's own choice — is the OPPOSITE: the sentinel keeps SHARING the real producer's input, made safe by gating (the gate makes no delivery when the real producer would). `Associate Lane Sentinel Gate` and `Associate Carry Merge` do share `Ingest Merge Response`'s association-lane input, by design.
- **Resolution:** No code change was needed (this is exactly what D-70-23 asked for) — documented here so the tension between the plan's literal wording (pre-dating the operator's Task 1 answer) and the shipped design is explicit, not silently absorbed. `mergeInputContract.test.mjs`'s own header states this is why exactly-one-producer-per-input is deliberately not asserted.
- **Committed in:** `ce78a3b` (no separate commit; documented here per Rule 4's spirit — the ambiguity was in the PLAN text, already resolved by the operator's Task 1 answer, not a fresh architectural question needing a new checkpoint).

**4. Three existing tests updated to assert the NEW (correct) wiring instead of the OLD wiring they pinned**
- `writeGateShape.test.mjs`: two structural assertions checked a sentinel's/IF's own name feeding a Merge directly by name — both now check for the gate/pass-through node instead, with the reason stated inline (the OLD wiring is exactly the shape this task retired).
- `ingestMixedBatch.test.mjs`'s `assertAckFiredOnce` and `ingestTracerFlow.test.mjs`'s review-only case: both asserted a blanket `trace.stalled === []`; both now exclude the intentionally-bypassed carry Merges (`Update Carry Merge`, `Create Carry Merge`, `Associate Carry Merge`) by name, with the reason (nothing downstream reads their own output directly on a batch where the write path never runs) stated inline, and both still assert `Ingest Merge Response` — what every row's response actually rests on — fires.
- **Committed in:** `ce78a3b`

---

**Total deviations:** 4 (2 auto-fixed bugs, 1 documented architectural supersession, 3 test-assertion updates for the new wiring — all foreseen by the plan's own "where a suite asserts the OLD wiring, update the assertion and record why" instruction).
**Impact on plan:** All four necessary for correctness; the two Rule 1 bugs were found and fixed BEFORE the task's own commit, not shipped and patched later. No scope creep — the fix stayed within `_add_starved_lane_sentinel`/`wire_gate_refusal_lane`/`code_node` and the ingest lane's own wiring; the enrichment/review lanes' own remaining violations are untouched, per plan.

## Issues Encountered

- **A naive first fix raced a real row.** The first attempt at "make Update/Create Carry Merge never stall" fed a marker to BOTH indices of those carry Merges' inputs when the write path was entirely unreached, which corrupted `Associate Carry Merge` on a MIXED batch (a real update row's own association came back `"not_confirmed"` instead of `"associated"`) — the exact class of bug this whole plan exists to retire, self-inflicted mid-task. Caught by the task's own `ingestMixedBatch.test.mjs` suite, not by inspection; resolved by the `Build Association Request Merge` fix above.
- **A second fix broke a genuinely unrelated enrichment-lane test** (the marker-key filter regression, deviation #2 above) — caught by running the FULL node suite (not just the six named required suites) before committing, per the advisor's own recommendation.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 70-11 owns the enrichment, review, and local-live lanes' own remaining Merge-input contract violations, all named exactly by `mergeInputContract.test.mjs`'s `PENDING` list: `wf_enrichment_cloud.json` (an over-wide 15-input `Build Response Merge`, and ~24 routing-IF-direct-to-Merge edges its own gates and carry Merges still carry), `wf_enrichment_local_live.json` (4 IF-direct edges), `wf_review_decision_cloud.json` (3 IF-direct edges).
- The `_add_merge_passthrough`/`_retarget_merge_edge_through_passthrough` helpers built here are generic (not ingest-specific) and ready for plan 70-11 to reuse on the enrichment lane's own IF-direct edges.
- `wire_gate_refusal_lane`'s new `carry_merge` parameter is generic and ready for plan 70-11 if the enrichment lane's own per-hop carry Merges turn out to have the same convergence gap `Build Association Request` had here.
- The enrichment lane's `list-expansion refusal` test's TypeError-turned-stall failure (`writeGateShape.test.mjs`'s "fully refused two-row batch" case, `List By Name Carry Merge`/`HubSpot Company Fetch By Id Carry Merge`) is exactly `70-WALKER-RED-INVENTORY.md` line 82's documented, pre-existing, out-of-scope defect — confirmed unchanged in root cause across this plan's work, not newly introduced.
- Nothing is armed live. No workflow was deployed. This plan is offline-only, per its own prohibitions.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED

All claimed files exist on disk (scripts/build_cloud_workflows.py, all modified n8n/wf_*.json, tests/n8n/mergeInputContract.test.mjs, tests/n8n/ingestMixedBatch.test.mjs, tests/n8n/ingestTracerFlow.test.mjs, tests/n8n/writeGateShape.test.mjs, tests/test_merge_helpers.py, tests/fixtures/companies_jscode_frozen.json). All claimed commits exist in git history (51899bb, ce78a3b, 2cf161b).
