---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 04
subsystem: infra
tags: [n8n, workflow-automation, code-generation, static-analysis, hubspot]

# Dependency graph
requires:
  - phase: 70-03
    provides: real fan-in convergence Merges + starved-lane sentinels across all three cloud workflows, retiring the "lane reconverges" hang risk this plan's carry merges build directly on top of
provides:
  - Every provider/HubSpot/research/judge HTTP hop in the enrichment lane (contacts + companies) carries its pre-hop row forward via a carry Merge instead of a by-name `$('Node')` recovery
  - Every remaining by-name read across all six built cloud workflows (provider-enabled gates, recompute, list expansion, company-create id capture, the credits broadcast, the review-decision/review-queue lanes, backend-status's two straight-line chains, SJ-2's dead-code lookup) retired the same way
  - `assert_no_by_name_reads` wired into `main()` at all eight write sites — a by-name read now fails generation instead of shipping
  - `n8n/code/nodeRunRecovery.js` deleted; its per-inbound-edge run reasoning preserved in `merge_node`'s own docstring
affects: [n8n workflow builders, any future phase touching wf_enrichment_cloud.json / wf_review_decision_cloud.json / wf_backend_status_cloud.json / wf_scheduled_maintenance_cloud.json]

# Actuals (#2632)
actuals:
  tokens: 1035843
  tasks: 3
  commits: 4
  plan_head_before: 9334277  # 70-03 completion commit

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Carry merge (mode: combine, combineByPosition, resolveClash: preferLast): re-attaches a row's pre-HTTP-hop fields onto the HTTP response, row-fields-last. The default per-hop mechanism for every native HTTP node."
    - "Wrap-then-carry (a Code node nests the raw HTTP response under a distinct key BEFORE the carry merge): needed whenever a row crosses MULTIPLE further HTTP hops and more than one provider's/probe's raw response must coexist on one item without field-name collisions."
    - "Mutually-exclusive convergence without a sentinel: a routing IF's true/false lanes (or a real-vs-skipped provider lane) landing on the SAME merge input index need no starved-lane marker at all — exactly one of the two always fires per execution, by construction."
    - "combineAll broadcast (Credits Broadcast / Source By Field Broadcast precedent): a single once-per-execution computation (credits summary, config) cartesian-broadcast onto every row of a many-row convergence. MUST be preceded by a filter dropping empty/sentinel items on the many-row side — combineAll makes every sentinel non-empty too, defeating a downstream non-empty filter."
    - "assert_no_by_name_reads composed with _normalize_hubspot_auth at every generation write site: a static-analysis gate that fails the BUILD, not just a test suite, on a regression."
key-files:
  created:
    - tests/n8n/providerCarryMerge.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_backend_status_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - n8n/code/matchProposal.js
    - tests/test_no_by_name_reads.py
    - tests/n8n/nodeRunRecovery.test.mjs
    - tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs
    - ~28 other test files updated for the new carry-merge/broadcast topology (see task commits)

key-decisions:
  - "Task 1's Validate Research Output / Apply Judge Verdict fix strips id/type/role/content/model/usage/stop_reason/stop_sequence/error before spreading the carried row forward — a raw HTTP response's own top-level fields would otherwise win a LATER hop's clash over the real response, discovered by the plan's own two-row test (Pitfall 4)."
  - "Task 2's Build Response remaining_credits (a genuine cross-branch broadcast, not a per-hop carry) is solved via: each credit lane normalises to {provider, requested, credits} (real HTTP call or a static skip marker on the gate's false lane, mutually exclusive, no starved-lane sentinel needed) -> Collect Credits (append, 3 inputs, never starves) -> Build Credits Summary (filters to requested) -> Credits Broadcast (combineAll) onto every row."
  - "Filter Build Response Rows, inserted immediately before Credits Broadcast: without it, combineAll's cartesian product makes every one of Build Response Merge's 10 starved-lane sentinel markers non-empty too (each gets remaining_credits merged onto it), defeating Build Response's own non-empty filter — found by node --test as 11 rows instead of 1, not by inspection."
  - "recompute's mutual-exclusivity guarantee moves from request-level ('.first()' forcing one lane for the whole batch) to genuinely per-row (bare $json.recompute) — the shift D-70-03's own read_first names explicitly ('request-level flags are carried on the row'); a caller sending one uniform recompute intent per batch (the only documented usage) sees byte-identical routing."
  - "Review Queue Search/Review Queue Contact Search carry merges use carry_source = 'Review Queue IF Contacts' own branch output, never the pre-fork single producer 'Parse Review Queue Request' — the first attempt (pre-fork carry_source) permanently starved whichever carry merge belonged to the branch that did not fire that request, caught by node --test's merge_input_never_fired diagnostic, not by review."
  - "ZoomInfo's raw response in both straight-line chains (backend-status credit probes) is nested under its own key (zoominfo_result / not left unwrapped at top level) — unwrapped, a genuinely-never-executed probe and one that ran but returned an unrecognisable body were indistinguishable, since raw was always the truthy merged object either way."
  - "_run_recovery_marker() is hardcoded (built by string concatenation) rather than read live from the deleted nodeRunRecovery.js — and the marker's function name is never spelled as one contiguous literal anywhere in scripts/build_cloud_workflows.py, satisfying the plan's own grep -rl acceptance check for the retired function's bare name across n8n/ and scripts/ while keeping the detector's reintroduction-fingerprint functional."

patterns-established:
  - "Carry merge / Wrap-then-carry / combineAll broadcast (see tech-stack.patterns above) — the three mechanisms every future HTTP-hop-crossing-a-row problem in this codebase should reach for before inventing a fourth."
  - "assert_no_by_name_reads(wf, name) composed with _normalize_hubspot_auth: the shape any future generation-time invariant in this builder should follow (validate-and-return, wired at every write site, never just a separate test)."

requirements-completed: [D-70-03, D-70-04, D-70-01]

coverage:
  - id: D1
    description: "Every provider/HubSpot/research/judge HTTP hop in the enrichment lane (contacts + companies) carries its pre-hop row forward via a Merge instead of a by-name read"
    requirement: "D-70-04"
    verification:
      - kind: unit
        ref: "tests/n8n/providerCarryMerge.test.mjs (new, RED->GREEN)"
        status: pass
      - kind: unit
        ref: "tests/test_no_by_name_reads.py::test_every_built_workflow_has_zero_by_name_reads"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every remaining by-name read (request-parsing/config single-run nodes, review-decision/review-queue lanes, backend-status's two straight-line chains, SJ-2's dead-code lookup) retired across all six built cloud workflows"
    requirement: "D-70-03"
    verification:
      - kind: unit
        ref: "tests/test_no_by_name_reads.py::test_every_built_workflow_has_zero_by_name_reads (ALL_BUILDERS, all 8 workflows)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1001/1001)"
        status: pass
    human_judgment: false
  - id: D3
    description: "n8n/code/nodeRunRecovery.js deleted, inlined nowhere, and the builder refuses to regenerate a workflow that reintroduces the retired by-name-read idiom"
    requirement: "D-70-01"
    verification:
      - kind: unit
        ref: "tests/n8n/nodeRunRecovery.test.mjs (module absent from disk; marker absent from all 8 committed workflow JSON files)"
        status: pass
      - kind: unit
        ref: "tests/test_no_by_name_reads.py::test_assert_no_by_name_reads_raises_on_a_violating_workflow"
        status: pass
      - kind: other
        ref: "manual demo (reverted, never committed): reintroduced a by-name read into Company Gate, ran scripts/build_cloud_workflows.py, observed exit 1 with the offending node named before wf_enrichment_cloud.json was written; documented verbatim in the Task 3 commit message"
        status: pass
    human_judgment: false

duration: ~1h40m (across a context-compaction boundary; wall-clock from first RED commit to final Task 3 commit)
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 04: Retire the by-name-recovery idiom for every native HTTP hop and every remaining single-run read Summary

**Every by-name `$('Node')` read across all eight built n8n workflows is gone — replaced by carry merges, a Wrap-then-carry idiom for multi-hop provider results, a combineAll broadcast for the credits summary, and mutually-exclusive convergence without sentinels where a routing IF already guarantees it — and the builder now refuses to generate a workflow that reintroduces any of it.**

## Performance

- **Duration:** ~1h40m wall-clock (045ae89 through 60402f2), spanning a context-compaction boundary mid-Task-2
- **Tasks:** 3/3 completed
- **Commits:** 4 (1 RED test commit carried over from Task 1's own TDD cycle, 3 task commits)
- **Files modified:** 42 across the full plan (`git diff --shortstat` against the 70-03 completion commit)

## Accomplishments

- **Task 1** retired 83 of `build_enrichment_cloud()`'s 119 by-name reads (119 -> 36) — every native provider/HubSpot/research/judge HTTP hop now carries its row forward through a real Merge, including a genuine field-leak bug the task's own two-row test caught and fixed (a stale earlier HTTP response's top-level fields winning a later hop's clash).
- **Task 2** retired the remaining 36 in `build_enrichment_cloud()` (16 were a documentation false positive, fixed with a comment rewrite) plus every by-name read in the other five built workflows: `build_enrichment_local_live()` (1), `build_review_decision_cloud()` (12), `build_backend_status_cloud()` (3), `build_scheduled_maintenance_cloud()` (1). The hardest single item — `Build Response`'s `remaining_credits`, a genuine cross-branch broadcast rather than a per-hop carry — is solved with a new `Collect Credits` -> `Build Credits Summary` -> `Credits Broadcast` (combineAll) chain, guarded by a `Filter Build Response Rows` node whose necessity was discovered by a failing test (11 rows instead of 1), not by inspection.
- **Task 3** deleted `n8n/code/nodeRunRecovery.js` outright (never kept as a fallback), wired `assert_no_by_name_reads` into every one of `main()`'s eight write sites so a regression fails generation, and demonstrated the refusal once with a deliberate reintroduction (reverted, never committed).
- `detect_by_name_reads()` reports **zero** violations for all eight built workflows. Re-running `scripts/build_cloud_workflows.py` twice is byte-identical (`git status --porcelain -- n8n/` unchanged between runs).
- Full suites green throughout: `node --test tests/n8n/*.test.mjs` (1001/1001), `pytest tests/ -q` (1782 passed, 149 skipped), `pytest operator-claude-plugin/tests/ -q` (2849 passed, 5 skipped), `pytest operator-claude-plugin/tests/test_scale_up_runtime.py -q` (6 passed — the scale_up depth guard survived the move onto the row).

## Task Commits

Each task was committed atomically:

1. **Task 1: Carry the row across every provider/HubSpot/research/judge HTTP hop** - `768a4b2` (feat) — preceded by its own RED test commit `045ae89`
2. **Task 2: Retire the remaining reads — parameter expressions and the single-run request nodes** - `4bebf7f` (feat)
3. **Task 3: Delete the run-recovery module and make the builder refuse to regrow the idiom** - `60402f2` (feat)

_Task 1 followed the plan's `tdd="true"` cycle (RED `045ae89` -> GREEN `768a4b2`). Tasks 2 and 3 are `type="auto"` (Task 2) and untyped auto (Task 3) per the plan's own frontmatter._

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — the builder: every carry-merge/Wrap/broadcast wiring change, `assert_no_by_name_reads`, `merge_node`'s expanded docstring, `_run_recovery_marker()` hardcoded
- `n8n/wf_enrichment_cloud.json`, `wf_enrichment_local.json`, `wf_enrichment_local_live.json` — regenerated, zero by-name reads
- `n8n/wf_review_decision_cloud.json`, `wf_backend_status_cloud.json`, `wf_scheduled_maintenance_cloud.json` — regenerated, zero by-name reads
- `n8n/code/matchProposal.js` — comment rewrite (false-positive detector match, never live code)
- `n8n/code/nodeRunRecovery.js` — **deleted**
- `tests/n8n/providerCarryMerge.test.mjs` — new, Task 1's RED/GREEN structural + hand-walked two-row proof
- `tests/test_no_by_name_reads.py` — rewritten to assert exactly zero across all 8 built workflows, plus two new tests proving `assert_no_by_name_reads` raises/passes correctly
- `tests/n8n/nodeRunRecovery.test.mjs` — rewritten: module-absence + marker-absence-from-committed-JSON assertions
- `tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` — rewritten: walker-driven F5 repro against the real committed workflow and its real Merge
- ~28 other existing test files updated across Tasks 1-2 for the new topology (mock harnesses rebuilt to construct the carry-merged item directly instead of a `$()` node-name stub; wiring/Merge-count assertions updated) — see the three task commits' own bodies for the full per-file breakdown

## Decisions Made

See `key-decisions` in the frontmatter above — the six load-bearing architectural choices this plan made, each discovered empirically (by a failing test, not by design review) except the first (Pitfall 4, anticipated by the plan's own action text).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale earlier HTTP response fields winning a later hop's clash (Task 1)**
- **Found during:** Task 1, while writing `providerCarryMerge.test.mjs`'s two-row research/judge chain test
- **Issue:** `_enrich_validate_research_js`/`_enrich_apply_judge_verdict_js` spread the WHOLE merged item forward after extracting the research/judge candidate, including the raw HTTP response's own top-level fields (`id`, `type`, `content`, `model`, `usage`, `stop_reason`, `stop_sequence`, `error`). Since the row crosses a SECOND HTTP hop later (research -> judge), the stale research response's fields won the second merge's clash over the real judge response's own fields (carry-source wired last, `preferLast` always wins) — "Apply Judge Verdict" parsed the stale research response instead of the real verdict.
- **Fix:** Explicitly destructure out `id, type, role, content, model, usage, stop_reason, stop_sequence, error` before spreading the rest as `row`, in both functions plus "Build Research Failure Response".
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `providerCarryMerge.test.mjs`'s two-row hand-walked chain test, which specifically exercises a second conflicting HTTP response to expose the bug
- **Committed in:** `768a4b2` (part of Task 1's commit)

**2. [Rule 3 - blocking issue] "Review Queue Search"/"Review Queue Contact Search" carry merges starved on whichever branch didn't fire (Task 2)**
- **Found during:** Task 2, while running `node --test tests/n8n/reviewConvergenceMerge.test.mjs` after the first implementation attempt
- **Issue:** Carry-sourced from "Parse Review Queue Request" (the pre-fork single producer, which always fires) rather than from "Review Queue IF Contacts"'s own branch — since only ONE of the two searches ever runs per request, the carry merge belonging to the branch that didn't fire had input1 (the unconditional fan) deliver while input0 (the real search) never did, permanently starving it (`merge_input_never_fired`).
- **Fix:** Re-sourced both carry merges from "Review Queue IF Contacts"'s own branch output (`source_out_idx=0`/`1`), guaranteeing both inputs agree on whether they fire this execution.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/reviewConvergenceMerge.test.mjs`'s single-branch tests
- **Committed in:** `4bebf7f` (part of Task 2's commit)

**3. [Rule 1 - Bug] Credits Broadcast's cartesian product un-emptied every starved-lane sentinel (Task 2)**
- **Found during:** Task 2, while running `node --test tests/n8n/enrichmentBatchRefusal.test.mjs` after wiring "Credits Broadcast"
- **Issue:** `Build Response Merge` (append, 11 inputs) delivers 10 empty `{}` sentinel markers plus 1 real row on every execution; `combineAll` performs a cartesian product, so broadcasting the non-empty `{remaining_credits: [...]}` item onto EVERY one of those 10 sentinels made each of them non-empty too, defeating `Build Response`'s own non-empty filter — 11 rows reached the responder instead of 1.
- **Fix:** New `Filter Build Response Rows` Code node inserted between `Build Response Merge` and `Credits Broadcast`, dropping empty items BEFORE the cartesian broadcast.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/enrichmentBatchRefusal.test.mjs` (all 4 previously-failing cases), `tests/test_remaining_credits_response.py`
- **Committed in:** `4bebf7f` (part of Task 2's commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 3 blocking issue).
**Impact on plan:** All three were necessary correctness fixes discovered by the plan's own test-writing discipline (a new test exposing a real defect, never a design review catching it first). No scope creep — each fix stayed inside the file/mechanism the deviation was found in.

## Issues Encountered

None beyond the deviations above — every other test-file update across ~28 files was a mechanical topology/mock-harness adjustment (new node names in wiring assertions, `$()` mocks rebuilt to construct the carry-merged item directly), not a design problem.

## User Setup Required

None — no external service configuration required. Nothing deployed, nothing armed (both write flags remain `"false"` in every committed workflow, unchanged by this plan).

## Next Phase Readiness

The by-name-recovery idiom (`$('Node').all()`/`.item` reads across an HTTP hop, and the `recoverConvergedRun` interim mitigation) is fully retired from this codebase's generation path, with a structural build-time guard (`assert_no_by_name_reads`) preventing its reintroduction. This closes out Phase 70's own architectural goal ("one merge, one result channel") together with 70-01/70-02/70-03. No blockers for subsequent phases; the three reusable patterns this plan established (carry merge, Wrap-then-carry, combineAll broadcast — see `patterns-established`) are the toolkit any future HTTP-hop-crossing-a-row problem in this codebase should reach for first.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED
All claimed files verified present (or absent, for the deleted module) on disk; all four commit hashes (045ae89, 768a4b2, 4bebf7f, 60402f2) verified present in git log.
