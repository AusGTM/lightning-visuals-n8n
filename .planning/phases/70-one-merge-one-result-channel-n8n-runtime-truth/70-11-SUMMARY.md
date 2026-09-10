---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 11
subsystem: infra
tags: [n8n, workflow-generator, merge, sentinel, walker, offline-harness, gap-closure]

requires:
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "70-10's gated-sentinel mechanism (D-70-23), _add_merge_passthrough / _retarget_merge_edge_through_passthrough, and the Merge-input contract test with its exact PENDING list naming the three workflows this plan converts"
provides:
  - "split_merge_into_stages(): a generic builder helper that splits an over-wide append-mode Merge into lane-grouped stage Merges that reconverge on the ORIGINAL node name — Build Response Merge's 15 inputs (over n8n's own 10-input cap) split into 3 stages (contacts, companies, unsupported/refusal)"
  - "_retarget_all_if_direct_edges(): applies 70-10's pass-through retarget over a whole lane's worth of routing-IF-direct-to-Merge edges in one call — 28 edges on the enrichment lane, 4 on the local-live variant, 3 on the review-decision lane"
  - "assert_merge_input_contract(): the generation-time refusal mirroring assert_no_by_name_reads/assert_write_request_emitters — the Merge-input contract can no longer be silently re-violated by a future generator change"
  - "mergeInputContract.test.mjs PENDING list emptied — every committed workflow satisfies the structural contract"
affects: [70-12-plan-and-any-future-generator-change-touching-a-Merge]

actuals:
  tokens: 15972   # chars/4 over scripts/build_cloud_workflows.py + tests/*.test.mjs + tests/*.py diffs (4bae150..HEAD). Excludes the 3 regenerated n8n/wf_*.json (derived, not authored — same convention 70-10-SUMMARY.md established).
  tasks: 3
  commits: 2
  plan_head_before: 4bae150

tech-stack:
  added: []
  patterns:
    - "Stage-merge split: an over-wide append Merge's declared inputs are partitioned into groups, each group's existing edges re-pointed (never copied) to a freshly created stage Merge, and the stages' single outputs feed the ORIGINAL merge node at fresh indices — the original node's own NAME and OUTPUT connection never change, so no downstream consumer or out-of-builder string needs to move."
    - "Lane-wide pass-through retarget: a table of (source, source_out_idx, merge_name) triples, applied in one call at the very END of the builder (after every _merge_input_index/lambda lookup that resolves an index off one of those exact sources has already run) — retargeting never moves an input's INDEX, only what feeds it, so doing it last is always safe regardless of how many earlier lookups depended on the direct edge."
    - "Generation-time contract composition: a new assertion is added to the SAME composition chain as the pre-existing ones (assert_no_by_name_reads -> assert_merge_input_contract, one wrapper function, one call per write site) rather than a parallel check with its own insertion points — a future third assertion has one place to join."

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - tests/n8n/mergeInputContract.test.mjs
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - tests/n8n/enrichmentConvergenceMerge.test.mjs
    - tests/n8n/linkedinLaneFlow.test.mjs
    - tests/n8n/researchErrorGateFlow.test.mjs
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - tests/n8n/writeGateShape.test.mjs
    - tests/test_cloud_companies_branch.py
    - tests/test_cloud_contacts_branch.py
    - tests/test_enrichment_lane_dedup.py
    - tests/test_enrichment_list_branch.py
    - tests/test_remaining_credits_response.py
    - tests/test_merge_helpers.py

key-decisions:
  - "Reconverge on the ORIGINAL merge node name, never a new terminal. split_merge_into_stages() keeps 'Build Response Merge' as the final converging node (its numberInputs shrinks to 3, fed by 3 new stage Merges) rather than replacing it — this sidesteps the plan's own flagged migration risk ('every consumer that reads that node by position ... must be checked against the new terminal name') entirely, since the terminal name never changes."
  - "Grouped Build Response Merge's 15 original inputs by lane exactly as the plan's action text asked: contacts terminals + contacts refusal lanes {0,1,2,3,11,12} (6 inputs), companies terminals + companies refusal lanes {4,5,6,7,8,13,14} (7 inputs), unsupported object type + whole-batch refusal {9,10} (2 inputs) — each well within n8n's 10-input cap, with the final reconverge Merge itself only 3 inputs."
  - "All lane-audit retargets deferred to the very end of each builder function, after every sentinel-network _merge_input_index lookup that resolves an index off one of the retargeted sources — proven safe because _retarget_merge_edge_through_passthrough never moves an input's declared INDEX, only what feeds it, so an index baked into an earlier lambda call stays valid regardless of when the retarget runs."
  - "assert_merge_input_contract enforces the four STRUCTURAL rules only (input-count cap, no sentinel-direct edge, no routing-IF-direct edge, no unfed input) — deliberately NOT the dynamic one-producer-per-input rule the JS test's header explicitly declines to assert either, since a generator cannot statically distinguish a safe multi-producer share (D-70-23's gated sentinel) from an unsafe one; only a replay can."

patterns-established:
  - "A lane's own routing-IF-direct-Merge audit is one call to _retarget_all_if_direct_edges with a literal table of (source, out_idx, merge_name) triples read straight off mergeInputContract.test.mjs's own violation output for that workflow — never hand-derived from reading the graph."

requirements-completed: [D-70-20, D-70-19, D-70-01, D-70-14]

coverage:
  - id: D1
    description: "Build Response Merge (15 inputs, over n8n's 10-input cap) split into 3 lane-grouped stage Merges that reconverge on the original node name"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeInputContract.test.mjs#wf_enrichment_cloud.json: Merge-input structural contract"
        status: pass
      - kind: unit
        ref: "tests/test_merge_helpers.py::test_split_merge_into_stages_reconverges_on_the_original_merge_name"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every routing-IF-direct-to-Merge edge on the enrichment, local-live and review-decision lanes retargeted through a pass-through (35 edges total: 28 + 4 + 3)"
    verification:
      - kind: unit
        ref: "tests/n8n/mergeInputContract.test.mjs#PENDING names exactly the workflows that violate the contract, in both directions"
        status: pass
    human_judgment: false
  - id: D3
    description: "mergeInputContract.test.mjs PENDING list is empty; every committed workflow satisfies the Merge-input contract"
    verification:
      - kind: unit
        ref: "node --test tests/n8n/mergeInputContract.test.mjs (18 tests, all pass)"
        status: pass
    human_judgment: false
  - id: D4
    description: "assert_merge_input_contract refuses generation on any of the 4 structural violations, naming workflow/Merge/input index/rule; composed at all 8 write sites; a unit test has seen it fire"
    verification:
      - kind: unit
        ref: "tests/test_merge_helpers.py::test_assert_merge_input_contract_raises_on_sentinel_direct_edge_naming_the_input_index (+3 sibling refusal tests)"
        status: pass
      - kind: other
        ref: ".venv/bin/python scripts/build_cloud_workflows.py — all 8 workflows regenerate cleanly under the new composed assertion"
        status: pass
    human_judgment: false
  - id: D5
    description: "Whole offline harness green: node suite, root Python suite, plugin Python suite; regeneration idempotent"
    verification:
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1064/1064 pass)"
        status: pass
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (4687 passed, 154 skipped)"
        status: pass
      - kind: unit
        ref: "cd operator-claude-plugin && ../.venv/bin/python -m pytest -q (2864 passed, 5 skipped)"
        status: pass
      - kind: other
        ref: "two consecutive `python scripts/build_cloud_workflows.py` runs produce byte-identical n8n/ trees (diff -rq clean)"
        status: pass
    human_judgment: false

duration: ~2h
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 11: One merge, one result channel — n8n runtime truth (gap closure) Summary

**The enrichment lane's 15-input Build Response Merge is split into 3 lane-grouped stage Merges (each within n8n's own 10-input cap), all 35 remaining routing-IF-direct-to-Merge edges across the enrichment/review/local-live lanes are retargeted through pass-throughs, the Merge-input contract is now enforced at generation time (not only in a test), and the whole offline harness — 1064 node tests, 4687 root Python tests, 2864 plugin tests — is green.**

## Performance

- **Tasks:** 3 (tracer, auto, auto)
- **Files modified:** 16 (1 generator, 3 regenerated workflow JSON, 12 test files)
- **Commits:** 2 task commits + this metadata commit

## Accomplishments

- **`split_merge_into_stages()`** (new, generic): splits an over-wide append-mode Merge into per-group stage Merges, each within n8n's own 10-input cap, reconverging on the ORIGINAL node — its name and its own output connection never change, so no downstream consumer needed migrating. Applied once, to `Build Response Merge`'s 15 original inputs, grouped by lane exactly as the plan's action text specified: contacts (6 inputs, indices 0/1/2/3/11/12), companies (7 inputs, indices 4/5/6/7/8/13/14), unsupported/refusal (2 inputs, indices 9/10).
- **`_retarget_all_if_direct_edges()`** (new, generic): batches 70-10's `_retarget_merge_edge_through_passthrough` over a whole lane's worth of routing-IF-direct-to-Merge edges. Applied to all three remaining lanes on `mergeInputContract.test.mjs`'s PENDING list: 28 edges on `wf_enrichment_cloud.json` (carry-merge `carry_source` fans + fan-in convergence direct edges + write-gate refusal edges), 4 on `wf_enrichment_local_live.json` (the mirrored Merge Winners/Merge Company convergences), 3 on `wf_review_decision_cloud.json` (the dry-run pass-through and the two queue-lane carry merges).
- **The PENDING list is empty.** `mergeInputContract.test.mjs` (18 tests) now asserts every committed workflow satisfies the structural contract, with a new dynamic replay test for `wf_review_decision_cloud.json` added alongside the pre-existing ingest-lane one (every CONVERTED workflow now falls into exactly one of the four accounting buckets: no-merges, no-trigger, awaiting-code, or replayed).
- **`assert_merge_input_contract()`** (new): the generation-time refusal, in the exact style of the two pre-existing generation-time assertions (`assert_no_by_name_reads`, `assert_write_request_emitters`) — raises `ValueError` naming the workflow, the offending Merge, the input index and which of the four structural rules broke. Composed via a new `_assert_generation_contracts()` wrapper alongside `assert_no_by_name_reads` at all 8 committed-workflow write sites in `main()`. Enforces only the STRUCTURAL rules (input-count cap, no sentinel-direct edge, no routing-IF-direct edge, no unfed input) — deliberately not the dynamic one-producer-per-input rule, since only a replay can distinguish a safe multi-producer share from an unsafe one.
- **8 new unit tests** in `tests/test_merge_helpers.py` prove the two new mechanisms on small hand-built graphs: `assert_merge_input_contract` refuses each of the 4 violation classes (naming the input index where one exists), and `split_merge_into_stages` both succeeds correctly and refuses a too-large group / a dropped index.
- **12 pre-existing tests updated** to the new pass-through/stage-merge wiring — every one an "expected consequence" the plan's own action text anticipated ("where a suite asserts the OLD wiring, update the assertion and record why"), never a relaxed assertion.

## Task Commits

1. **Task 1 + Task 2 (generator side): split Build Response Merge into stages, pass-through every routing-IF-direct Merge edge, and refuse the contract at generation time** — `586f203` (feat) — includes the 3 regenerated workflow JSON, the emptied `mergeInputContract.test.mjs` PENDING list, and all 12 moved-pin test updates.
2. **Task 2 (proof side): assert_merge_input_contract / split_merge_into_stages refusal unit tests** — `a83fbdd` (test)

Task 3 ("whole harness green, every moved pin recorded") required no additional code changes: Tasks 1–2 already left the full offline harness green (verified below); its deliverable is this SUMMARY's node-count table and per-suite accounting, not a code commit.

**Plan metadata:** commit created immediately after this SUMMARY is written (see the final `commit` step of execute-plan.md).

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `split_merge_into_stages()`, `_retarget_all_if_direct_edges()`, `assert_merge_input_contract()`, `_assert_generation_contracts()`, plus the three lane-specific retarget/split call sites (end of `build_enrichment_cloud()`, end of `build_enrichment_local_live()`, end of `build_review_decision_cloud()`).
- `n8n/wf_enrichment_cloud.json` (260 → 291 nodes), `n8n/wf_enrichment_local_live.json` (78 → 82 nodes), `n8n/wf_review_decision_cloud.json` (52 → 55 nodes) — regenerated, never hand-edited.
- `tests/n8n/mergeInputContract.test.mjs` — PENDING list emptied; new `wf_review_decision_cloud.json` replay test added to Bucket 4.
- `tests/n8n/companyRecomputeLaneFlow.test.mjs`, `tests/n8n/enrichmentConvergenceMerge.test.mjs`, `tests/n8n/linkedinLaneFlow.test.mjs`, `tests/n8n/researchErrorGateFlow.test.mjs`, `tests/n8n/reviewDecisionEndpoint.test.mjs`, `tests/n8n/writeGateShape.test.mjs` — pinned wiring assertions updated to the new pass-through/stage-merge node names.
- `tests/test_cloud_companies_branch.py`, `tests/test_cloud_contacts_branch.py`, `tests/test_enrichment_lane_dedup.py`, `tests/test_enrichment_list_branch.py`, `tests/test_remaining_credits_response.py` — same, on the Python-side structural assertions (the latter's `BUILD_RESPONSE_SOURCES` set restructured into `BUILD_RESPONSE_STAGE_SOURCES`, keyed per stage).
- `tests/test_merge_helpers.py` — 8 new unit tests proving the two new generator mechanisms.

## Node-count table (before this plan → after)

| Workflow | Before | After | Delta | Reason |
|---|---|---|---|---|
| `wf_enrichment_cloud.json` | 260 | 291 | +31 | 3 new stage Merges + 28 new pass-through Code nodes |
| `wf_enrichment_local_live.json` | 78 | 82 | +4 | 4 new pass-through Code nodes |
| `wf_review_decision_cloud.json` | 52 | 55 | +3 | 3 new pass-through Code nodes |
| `wf_contact_ingest_cloud.json` | 69 | 69 | 0 | untouched by this plan |
| `wf_contact_ingest_local.json` | 13 | 13 | 0 | untouched |
| `wf_enrichment_local.json` | 10 | 10 | 0 | untouched |
| `wf_scheduled_maintenance_cloud.json` | 43 | 43 | 0 | untouched |
| `wf_backend_status_cloud.json` | 30 | 30 | 0 | untouched |

("Before" measured against commit `4bae150`, the tip of plan 70-10 — the same `git show HEAD:<file> | node -e '...'.nodes.length` measurement 70-10-SUMMARY.md used.) These are the moved pins the next plan's CLAUDE.md §13.0.2 update should copy verbatim rather than re-derive.

## WALKER-RED-INVENTORY accounting

`70-WALKER-RED-INVENTORY.md`'s 26 originally-red tests (all pre-70-10) are now **fully accounted for**: 70-10 fixed the ingest lane's Shape B (7 tests), leaving 19 red per its own SUMMARY. This plan's work — the sentinel-gating mechanism already applying universally via `_add_starved_lane_sentinel` (no code change needed here) plus this plan's own pass-through/split fixes for the carry-merge and fan-in-convergence starvation on the enrichment/review/local-live lanes — closed the remaining 19. `node --test tests/n8n/*.test.mjs` now reports **0 failures** (1064/1064 pass), confirmed by two independent full runs at different points in this plan's work (mid-plan: 1064/1055/9 red → 1064/1060/4 red → 1064/1064/0 red as each batch of moved pins was fixed).

None of the 6 additional Python-side failures surfaced by re-running `pytest -q` after regeneration (`test_cloud_companies_branch.py` x2, `test_cloud_contacts_branch.py`, `test_enrichment_lane_dedup.py`, `test_enrichment_list_branch.py`, `test_remaining_credits_response.py`) were in the original WALKER-RED-INVENTORY (that inventory only covered the Node/JS suite) — each was a Python-side mirror of the same moved-pin class, fixed identically (documented above, per file, per the JS-side fix).

## Decisions Made

- **Reconverge on the original merge node name.** `split_merge_into_stages()` keeps `Build Response Merge`'s own name and its own single downstream output connection completely unchanged — only its `numberInputs` shrinks (15 → 3) and its own inputs are now fed by 3 new stage Merges. This was chosen over creating an entirely new terminal specifically to avoid the plan's own flagged migration risk (external strings naming the response terminal by position). Confirmed safe: no string outside the builder (proof driver, recovery client, walker CLI) needed updating.
- **Batch retargets at the very end of each builder, not inline.** Every `_retarget_all_if_direct_edges` call sits after all of that lane's own sentinel-network wiring — proven safe because retargeting an edge through a pass-through never changes which Merge INDEX it feeds, only what node feeds it, so an index an earlier `_merge_input_index` lookup already baked into a sentinel target list stays correct regardless of when the retarget itself runs.
- **`assert_merge_input_contract` enforces structural rules only.** The dynamic "no two real producers share an input" rule is deliberately left unenforced at generation time — `mergeInputContract.test.mjs`'s own header explains why (D-70-23's gated sentinel is a legitimate, safe multi-producer share; only a replay can distinguish it from an unsafe one). A generator-time check that tried to enforce it would falsely refuse every gated sentinel this repo already relies on.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 12 pre-existing tests pinned the OLD direct-edge/single-wide-merge wiring and went red the moment the graph changed underneath them**
- **Found during:** Task 1/2, running the full node and root Python suites after regenerating.
- **Issue:** Tests in `companyRecomputeLaneFlow.test.mjs`, `enrichmentConvergenceMerge.test.mjs`, `linkedinLaneFlow.test.mjs`, `researchErrorGateFlow.test.mjs`, `reviewDecisionEndpoint.test.mjs`, `writeGateShape.test.mjs`, `test_cloud_companies_branch.py`, `test_cloud_contacts_branch.py`, `test_enrichment_lane_dedup.py`, `test_enrichment_list_branch.py`, and `test_remaining_credits_response.py` asserted the exact pre-70-11 node names/indices these two new mechanisms changed by design (the plan's own action text: "where a suite asserts a node count or a merge width this plan moved, re-pin it and record the old and new values").
- **Fix:** Each assertion updated to the new pass-through/stage-merge name, with the reason recorded inline in the test file itself. `test_remaining_credits_response.py`'s `BUILD_RESPONSE_SOURCES` set was restructured into `BUILD_RESPONSE_STAGE_SOURCES`, keyed per stage, since a single flat set against `Build Response Merge` no longer has meaning once that node's own direct inputs are the 3 stages rather than the 15 original terminals.
- **Files modified:** the 11 test files named above.
- **Verification:** full node suite (1064/1064) and full root Python suite (4687 passed, 154 skipped) both green.
- **Committed in:** `586f203`

---

**Total deviations:** 1 (12 test-assertion updates for moved wiring, all foreseen by the plan's own instruction — no scope creep, no relaxed assertion).
**Impact on plan:** Every update strengthens the pin against the new (correct) graph shape rather than loosening it; none deletes or weakens an assertion.

## Issues Encountered

None beyond the expected-consequence pin updates documented above.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required. Nothing deployed, nothing armed (this plan is offline-only, per its own prohibitions).

## Next Phase Readiness

- The Merge-input contract is now enforced BOTH by a test over the committed JSON (`mergeInputContract.test.mjs`, PENDING list empty) AND by the generator itself at write time (`assert_merge_input_contract`, composed into every one of the 8 committed-workflow write sites) — a future generator change that re-creates the defect class fails the build, not just the test suite.
- The node-count table above is the measured source the next plan should copy into CLAUDE.md §13.0.2 — this plan deliberately did not touch CLAUDE.md itself (per the plan's own Task 3 action text: "so the CLAUDE.md update in the next plan copies a measured table rather than a remembered one").
- Nothing is armed live; the committed JSON is still ahead of whatever is deployed (this phase's live deploy/bounce, and the deferred UAT gates named in `70-DEFERRED-GATES.md`, remain the operator's step at end-of-phase per the phase's own "back-load human gates" ruling).
- `_retarget_all_if_direct_edges` and `split_merge_into_stages` are both fully generic — ready for reuse by any future plan that adds a Merge convergence or an over-wide fan-in anywhere in this generator.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED

All claimed files exist on disk (scripts/build_cloud_workflows.py, n8n/wf_enrichment_cloud.json, n8n/wf_enrichment_local_live.json, n8n/wf_review_decision_cloud.json, all 12 modified test files). Both claimed commits exist in git history (586f203, a83fbdd).
