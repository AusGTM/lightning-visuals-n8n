---
phase: 74-code-review-follow-ups-from-phase-73
plan: 05
subsystem: n8n-workflow-generation
tags: [n8n, ingest-lane, create-error-lane, pairCreateOutcome, written_records, merge-sentinel, tdd, node-test, pytest]

# Dependency graph
requires:
  - phase: 74-code-review-follow-ups-from-phase-73 (74-04)
    provides: "the corrected walkWorkflow.mjs (output-0-only alwaysOutputData padding, topological drain-order preference) -- every walker-driven test in this plan rests on it"
provides:
  - "n8n/wf_contact_ingest_cloud.json's 'Create Error Stamp' node (D-74-04) -- explicit _create_error marker, the ONLY signal pairCreateOutcome.js's classification tests first"
  - "n8n/wf_contact_ingest_cloud.json's 'Create Failure Row Sentinel' (+ its gate) -- covers the one write-gated Ingest Merge Response input that previously had no starved-lane sentinel"
  - "operator-claude-plugin/scripts/written_records.py's create_unconfirmed -> FAILED mapping -- a create the operator can never confirm is never reported as a success"
  - "scripts/build_cloud_workflows.py::extract_js_const's balanced-statement guard (WR-10)"
affects: [74-06-PLAN.md]

# Actuals (#2632)
actuals:
  tokens: 18590   # code-only (excludes the regenerated n8n/wf_contact_ingest_cloud.json): 74360 chars/4
  tasks: 3
  commits: 4
  plan_head_before: 488bef555a661ae690f2bd0979375f2620adbd78
  # Full realized diff including the regenerated JSON: 118270 chars (~29568 chars/4) --
  # the code-only figure above is the meaningful one for estimate calibration, same
  # convention 74-01/74-04-SUMMARY.md used for their own generated-artifact diffs.

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "explicit stamp beats shape guess: a builder-authored Code node marks the branch it sits on (_create_error: true), and the consuming pure function tests that marker FIRST, ahead of every structural inference -- correctness stops depending on an unobserved runtime shape"
    - "gated starved-lane sentinel with a DISJUNCTIVE condition composed inline (WRITE_SAFETY_GATE_JS + a literal predicate) in ONE node, so the marker can only ever emit once per execution and covers every batch shape the real producer's own firing condition does not"
    - "a hand-rolled test arming helper that composes WRITE_SAFETY_GATE_JS must be kept in the SAME arm-list every real write gate is armed from -- an unarmed sentinel disagrees with an armed gate and delivers a second, conflicting marker onto a shared Merge input"

key-files:
  created:
    - tests/test_extract_js_const.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/code/pairCreateOutcome.js
    - n8n/wf_contact_ingest_cloud.json
    - operator-claude-plugin/scripts/written_records.py
    - tests/n8n/pairCreateOutcome.test.mjs
    - tests/n8n/ingestCreateErrorLane.test.mjs
    - tests/n8n/ingestMixedBatch.test.mjs
    - tests/n8n/ingestCarryMerge.test.mjs
    - tests/n8n/walkerEngineFidelityV1.test.mjs
    - operator-claude-plugin/tests/test_written_records.py
    - operator-claude-plugin/tests/test_control_flag_parity.py
    - CLAUDE.md

key-decisions:
  - "D-74-01 as ruled (B') required no NEW producer on Create Carry Merge's error input -- only the D-74-04 stamp node landed there, wired through the SAME edge the plan researched (HubSpot Create output 1 -> stamp -> Create Carry Merge input 2). The comment block describing the retired 'alwaysOutputData rescues the error branch' mechanism was rewritten, not left stale, per the plan's explicit instruction."
  - "The 'stripped invented properties.email' behavior (Task 1's 4th pairCreateOutcome.test.mjs case) needed a DIFFERENT construction than a bare stamped item with zero identity -- a bare item already classified correctly under the OLD code (the else-arm), so it could never be RED. The meaningful RED->GREEN case reconstructs the graph stub's 3-row batch with the invented nested properties.email removed and the request's own top-level fields spread onto the error item instead (ambiguous with a carried row under the old shape-only classifier, unambiguous once the stamp is read first)."
  - "D-74-06's four behaviors split across pairCreateOutcome.test.mjs is NOT how the plan literally grouped them -- Task 2's graph-level cases (none/refused/only-unconfirmed) landed in ingestCreateErrorLane.test.mjs and ingestMixedBatch.test.mjs instead, since create_unconfirmed only exists once BUILD_CREATE_FAILURE_ROW_JS's widened filter runs, one hop past pairCreateOutcome's own output."
  - "mergeInputContract.test.mjs's MULTI_PRODUCER_TOLERANT registry needed NO new entry: the pair (\"LV Contact Ingest (Cloud template)\", \"Ingest Merge Response\") is already tolerated from the pre-existing association-lane sentinel's own registration, keyed by (workflow, merge) name only -- not per input index. Confirmed by running both of that file's own census assertions (structural + derived) against the regenerated graph before concluding no edit was needed."
  - "Deviation (Rule 1 - bug, found running this task's own full suite, not anticipated by the plan): the new sentinel composes WRITE_SAFETY_GATE_JS and therefore carries its own copy of every overlayable write-safety constant. Four hand-rolled test arming helpers that arm CREATE writes on this graph (ingestCarryMerge.test.mjs, ingestCreateErrorLane.test.mjs, walkerEngineFidelityV1.test.mjs, and this plan's own new ingestMixedBatch.test.mjs case) had to add the sentinel to their arm-list, mirroring exactly what n8n_arming.set_write_safety already does by scanning every node. Left unarmed, the sentinel's own unarmed copy disagreed with an armed real gate and delivered a second, conflicting marker onto the same Merge input in the same execution -- confirmed as a real risk, not a hypothetical, via a python-level walk of the generated graph's own producer list for that input."
  - "Deviation (Rule 1 - bug): operator-claude-plugin/tests/test_control_flag_parity.py hardcoded ALLOW_HUBSPOT_RECORD_WRITES/ALLOW_HUBSPOT_CREATE declaration counts (3 and 4) for the ingest workflow went stale the moment the new sentinel became a fourth/fifth declaring node -- updated to 4 and 5 in the three tests that pin the literal count (the fourth, count-deriving test in the same file needed no change, by design)."
  - "Task 3's plan text asked each batch shape be 'asserted by its own walker run, not inferred' -- the initial implementation proved the RESPONSE was correct on each shape but never inspected the sentinel's own gate delivery directly. Closed in a follow-up commit (fd20d725) with three direct assertions against \"Create Failure Row Sentinel Gate\"'s own runData, rather than leaving the mechanism's correctness inferred from the response shape alone."
  - "operator-claude-plugin/.claude-plugin/plugin.json was NOT bumped for the new create_unconfirmed ACTION_TO_OUTCOME entry -- checked via `git log -S` for Phase 73 Plan 06 Task 3's identical create_failed addition, which set no precedent for a version bump/CHANGELOG entry either. Followed that precedent rather than bumping."
  - "Follow-up review pass (advisor-flagged): the 'disarmed batch containing create-routed rows' sentinel test (fd20d725) was vacuous as first written -- the plain disarmed graph routes net_new rows to action:\"review\" (Decide Action bakes ALLOW_HUBSPOT_CREATE=false), never action:\"create\", so the sentinel fired via its OTHER disjunct (zeroCreateRows) and the test never exercised D-74-02's writesNotPermitted-with-create-rows-present disjunct at all despite its own name and comment claiming otherwise. Fixed by arming ONLY Decide Action's ALLOW_HUBSPOT_CREATE (leaving every write gate and the sentinel itself disarmed) and adding a non-vacuity assertion (3 rows actually route to action:create) plus response-shape assertions (all 3 rows reach Build Ingest Response as write_blocked). Re-verified genuinely non-vacuous; full suite still 1321/1321 green."

requirements-completed: [D-74-01, D-74-02, D-74-04, D-74-05, D-74-06, WR-10, D-74-10]

coverage:
  - id: D1
    description: "D-74-01 (ruled B') / D-74-04: 'Create Error Stamp' Code node on HubSpot Create's error edge is the ONLY writer of _create_error; pairCreateOutcome.js tests it FIRST, ahead of the carried-row and success-response shape checks; alwaysOutputData and Create Carry Merge's three declared inputs are unchanged"
    requirement: D-74-01
    verification:
      - kind: unit
        ref: "tests/n8n/pairCreateOutcome.test.mjs -- 5 new cases (stamp beats carried-row, stamp beats success, no-stamp unchanged, invented-shape-stripped graph-stub mirror)"
        status: pass
      - kind: integration
        ref: "tests/n8n/ingestCarryMerge.test.mjs -- HubSpot Create's error output feeds the stamp node, the stamp node feeds the carry merge"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-74-05: the hand-written error stub in ingestCreateErrorLane.test.mjs is tagged UNOBSERVED in the walkWorkflow.mjs D-70-30 register, naming the still-open real-error-item-shape question"
    requirement: D-74-05
    verification:
      - kind: unit
        ref: "n8n/code/pairCreateOutcome.js header + tests/n8n/pairCreateOutcome.test.mjs's mirrored-stub test -- correctness proven independent of the stub's own invented shape"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-74-06: a create outcome of none/refused reaches the response as create_unconfirmed with its own reason (no-response-joined text vs the ambiguity text), a HubSpot rejection is still create_failed, a batch of only unconfirmed outcomes emits rows not the marker, and written_records maps create_unconfirmed to FAILED"
    requirement: D-74-06
    verification:
      - kind: integration
        ref: "tests/n8n/ingestCreateErrorLane.test.mjs -- 3 new graph-level cases; tests/n8n/ingestMixedBatch.test.mjs -- 1 new mixed-batch case"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py::test_create_unconfirmed_is_failed_never_a_success_shaped_outcome"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-74-02: 'Create Failure Row Sentinel' (+gate) delivers a marker exactly when Build Create Failure Row cannot run (zero create-routed rows, OR every create-routed row refused pre-write) and never when a real create is permitted; target index derived, never a literal"
    requirement: D-74-02
    verification:
      - kind: integration
        ref: "tests/n8n/ingestCreateErrorLane.test.mjs -- 3 new cases directly asserting the sentinel gate's own runData delivery on all three batch shapes"
        status: pass
      - kind: unit
        ref: "python walk of the regenerated graph's connections -- Ingest Merge Response input 5 has exactly two producers (Build Create Failure Row, Create Failure Row Sentinel Gate)"
        status: pass
    human_judgment: false
  - id: D5
    description: "WR-10: extract_js_const raises on an unbalanced (silently truncated) extraction instead of splicing broken text into a generated Code node"
    requirement: WR-10
    verification:
      - kind: unit
        ref: "tests/test_extract_js_const.py -- 4 cases (well-formed extraction, semicolon-terminated-comment truncation now raises, missing-constant error, real FREEMAIL_DOMAINS stays balanced)"
        status: pass
    human_judgment: false
  - id: D6
    description: "One regeneration of the ingest workflow for the whole cluster; only wf_contact_ingest_cloud.json changed among generated workflows; node count recorded before/after"
    verification:
      - kind: e2e
        ref: ".venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/ (idempotency, post-commit)"
        status: pass
    human_judgment: false

# Metrics
duration: 95min
completed: 2026-09-19
status: complete
---

# Phase 74 Plan 05: Create-error lane cluster -- explicit stamp, unconfirmed-create outcome, gated sentinel Summary

**A builder-authored Code node stamps HubSpot Create's error branch explicitly so classification stops guessing at an unobserved n8n error-item shape, an unconfirmed create now reaches the operator as `create_unconfirmed` (mapped to FAILED) instead of silently keeping its stale pre-write "create" action, and a new gated sentinel closes the one write-gated Ingest Merge Response input that previously had none -- all landed in one regenerated `wf_contact_ingest_cloud.json` (98 -> 101 nodes).**

## Performance

- **Duration:** 95 min
- **Started:** 2026-09-19T (task 1 plan read)
- **Completed:** 2026-09-19T
- **Tasks:** 3 (+ one follow-up commit closing a gap in Task 3's own acceptance criteria)
- **Files modified:** 12 (+1 created)

## Accomplishments

- **D-74-01 (ruled B') / D-74-04:** `Create Error Stamp`, one Code node on `HubSpot Create`'s error edge, is the ONLY writer of an explicit `_create_error: true` marker. `pairCreateOutcome.js` tests that marker FIRST, ahead of the carried-row (`action` present) and success-response (`id` present) shape guesses -- a stamped item is an error item even if it happens to also carry either. The builder comment describing the retired "`alwaysOutputData` rescues the error branch" mechanism was rewritten to describe what execution `12522` actually showed: output 0 is padded, output 1 (the error branch) is simply absent on a zero-rejection batch, and `Create Carry Merge` completes via the single v1 end-of-run drain.
- **D-74-05:** the hand-written error stub in `ingestCreateErrorLane.test.mjs` is kept and tagged `UNOBSERVED`, in the same register `walkWorkflow.mjs` uses for D-70-30 rule (c), naming the still-open real-shape question (D-73-19). A new unit test proves correctness no longer rests on that stub's own invented `properties.email` shape.
- **D-74-06:** `Build Create Failure Row`'s filter widened from `create_outcome === "error"` to `!== "success"`, admitting `pairCreateOutcome`'s "none" and "refused" outcomes -- both were previously dropped silently by this node's old filter AND by `Build Association Request`'s own contactId check, leaving a row's stale pre-write "create" action to reach the operator unchanged. The emitted row now stamps `action`/`outcome` as `create_failed` (a genuine HubSpot rejection, unchanged) or `create_unconfirmed` otherwise, with `create_outcome_reason` passed through verbatim so the two sub-cases stay distinguishable. `written_records.ACTION_TO_OUTCOME` maps `create_unconfirmed` to the existing `FAILED` constant.
- **D-74-02:** `Create Failure Row Sentinel` (+ its gate), a starved-lane sentinel with a disjunctive condition (writes not permitted for create, composed from `WRITE_SAFETY_GATE_JS` -- OR zero create-routed rows in the batch), covers `Ingest Merge Response` input 5 -- the one write-gated input on this lane that had no sentinel before this plan. Its target index is derived from `_append_merge_input`'s own return value, never a literal.
- **WR-10:** `extract_js_const` now validates balanced brackets/braces/parens on the extracted text, raising instead of silently splicing a truncated statement into a generated Code node.
- **One regeneration:** `wf_contact_ingest_cloud.json` node count moved 98 -> 99 (Task 1's stamp node) -> 101 (Task 3's sentinel + gate). Only this one generated workflow changed; `git diff --quiet -- n8n/` after a fresh regeneration confirms idempotency.

## Task Commits

Each task was committed atomically:

1. **Task 1: An explicit stamp decides the error branch, end to end (D-74-04, D-74-05)** - `8948a8f5` (feat)
2. **Task 2: An unconfirmed create reaches the operator as FAILED (D-74-06)** - `aaf8ab44` (feat)
3. **Task 3: Gated sentinel on the create-failure input, WR-10, one regeneration (D-74-02, WR-10, D-74-01)** - `0dbeaa74` (feat)
4. **Follow-up: assert the sentinel's own firing directly** - `fd20d725` (test)

_TDD note: Task 1 (`type="tracer" tdd="true"`) and Tasks 2-3 (`tdd="true"`) each had their RED evidence captured by temporarily stashing the source-side commit and re-running the target test file(s) before restoring -- see "TDD Gate Compliance" below._

## Files Created/Modified

- `scripts/build_cloud_workflows.py` - `Create Error Stamp` node + wiring, `BUILD_CREATE_FAILURE_ROW_JS` widened, `BUILD_INGEST_RESPONSE`'s unconfirmed join, `Create Failure Row Sentinel`, `extract_js_const`'s balance guard
- `n8n/code/pairCreateOutcome.js` - stamp-first classification, header rewritten
- `n8n/wf_contact_ingest_cloud.json` - regenerated once (98 -> 101 nodes)
- `operator-claude-plugin/scripts/written_records.py` - `create_unconfirmed` -> `FAILED`
- `tests/n8n/pairCreateOutcome.test.mjs` - 5 new unit cases
- `tests/n8n/ingestCreateErrorLane.test.mjs` - 6 new graph-level cases (3 for D-74-06, 3 for the sentinel's own firing)
- `tests/n8n/ingestMixedBatch.test.mjs` - 1 new mixed-batch case
- `tests/n8n/ingestCarryMerge.test.mjs` - structural assertion updated for the stamp node; new sentinel added to its own `armGraphForCreate` arm-list
- `tests/n8n/walkerEngineFidelityV1.test.mjs` - new sentinel added to its own create-arming loop
- `tests/test_extract_js_const.py` - new file, 4 cases for WR-10
- `operator-claude-plugin/tests/test_written_records.py` - new mapping test, parametrize list and builder-extraction docstring updated (12 -> 13 real actions)
- `operator-claude-plugin/tests/test_control_flag_parity.py` - three hardcoded declaration counts updated (3->4, 4->5)
- `CLAUDE.md` - section 13.0.1 corrected and extended (the new stamp node, the new sentinel, the retired "alwaysOutputData rescues the error branch" claim struck)

## Decisions Made

See `key-decisions` in the frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Four hand-rolled test arming helpers needed the new sentinel added to their arm-lists**
- **Found during:** Task 3, before committing (traced through every file arming `ALLOW_HUBSPOT_CREATE=true` on this graph, per the advisor's flagged risk)
- **Issue:** `Create Failure Row Sentinel` composes `WRITE_SAFETY_GATE_JS` and carries its own copy of every overlayable write-safety constant. A hand-rolled test helper that arms the real create write gate but not this sentinel leaves the sentinel's own copy disarmed -- it disagrees with the armed gate and delivers a marker onto `Ingest Merge Response` input 5 in the SAME execution a real, permitted create's `Build Create Failure Row` delivery also lands on.
- **Fix:** Added `"Create Failure Row Sentinel"` to the arm-list in `tests/n8n/ingestCarryMerge.test.mjs`'s `armGraphForCreate`, `tests/n8n/ingestCreateErrorLane.test.mjs`'s `armGraphForCreate`, `tests/n8n/walkerEngineFidelityV1.test.mjs`'s inline loop, and this plan's own new `ingestMixedBatch.test.mjs` case's `armCreateDomains` helper.
- **Files modified:** the four files above
- **Verification:** full `node --test tests/n8n/*.test.mjs` green (1318 -> 1321 after the follow-up commit)
- **Committed in:** `0dbeaa74` (task 3), `fd20d725` (follow-up)

**2. [Rule 1 - Bug] `test_control_flag_parity.py`'s hardcoded declaration counts went stale**
- **Found during:** Task 3, full pytest run
- **Issue:** Three tests pinned `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` declaration counts (3 and 4) for the ingest workflow -- the new sentinel is a fourth/fifth declaring node.
- **Fix:** Updated the three literal counts to 4 and 5, with the reasoning documented in each test's own docstring/comment (mirroring the existing style for prior count changes).
- **Files modified:** `operator-claude-plugin/tests/test_control_flag_parity.py`
- **Verification:** `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` full suite green
- **Committed in:** `0dbeaa74`

**3. [Rule 1 - Bug] Task 3's own acceptance criteria asked for direct assertion, not inference**
- **Found during:** Self-review after Task 3's commit, before declaring the plan complete
- **Issue:** The plan's Task 3 acceptance criteria explicitly requires each batch shape be "asserted by its own walker run, not inferred" -- the initial implementation proved the response was correct on each shape (via the existing behavior tests) but never inspected `Create Failure Row Sentinel Gate`'s own delivery.
- **Fix:** Added three direct tests against `nodeItems(runData, "Create Failure Row Sentinel Gate")` for the all-update, disarmed-with-creates, and permitted-create shapes.
- **Files modified:** `tests/n8n/ingestCreateErrorLane.test.mjs`
- **Verification:** all three pass; `git diff --quiet -- n8n/` idempotency unaffected (test-only change)
- **Committed in:** `fd20d725`

**4. [Rule 1 - Bug] `ingestCarryMerge.test.mjs`'s by-name-reader structural assertion needed updating for the new stamp node**
- **Found during:** Task 1, first run of its own `<verify>` command
- **Issue:** The test asserted `HubSpot Create`'s error output feeds a Merge node directly -- true before this plan, no longer true once the stamp node sits between them.
- **Fix:** Special-cased `HubSpot Create`'s error output (index 1) to expect the `Create Error Stamp` Code node, then separately assert that node's own single output feeds the merge -- preserving the test's real intent (no untracked fan-out, no by-name reader) rather than weakening it.
- **Files modified:** `tests/n8n/ingestCarryMerge.test.mjs`
- **Verification:** all 3 files in Task 1's own `<verify>` command pass (19/19)
- **Committed in:** `8948a8f5`

**5. [Rule 1 - Bug] The 'disarmed batch containing create-routed rows' sentinel test (fd20d725) was vacuous**
- **Found during:** Post-completion advisor review, before returning the final completion report
- **Issue:** The plain disarmed graph routes net_new rows to `action:"review"`, never `action:"create"` (`Decide Action` bakes `ALLOW_HUBSPOT_CREATE="false"`) -- so all three trigger rows carried `action:"review"`, the sentinel fired via its `zeroCreateRows` disjunct, and the test's own name/comment ("containing create-routed rows") described a scenario it never actually constructed. D-74-02's `writesNotPermitted`-with-create-rows-present disjunct -- the case the plan explicitly required be "asserted by its own walker run, not inferred" -- was covered by nothing.
- **Fix:** Armed ONLY `Decide Action`'s `ALLOW_HUBSPOT_CREATE` (leaving `HubSpot Create Write Gate`, `Associate Lane Sentinel`, and `Create Failure Row Sentinel` itself all disarmed), added a non-vacuity assertion (`Decide Action` emits exactly 3 rows with `action==="create"`), and added response-shape assertions (all 3 rows reach `Build Ingest Response` as `write_blocked`, never silently dropped).
- **Files modified:** `tests/n8n/ingestCreateErrorLane.test.mjs`
- **Verification:** the fixed test passes non-vacuously; full `node --test tests/n8n/*.test.mjs` still 1321/1321 green
- **Committed in:** separate follow-up commit after `fd20d725` (see commit list below)

---

**Total deviations:** 5 auto-fixed (all Rule 1 - bugs; 4 found running each task's own or the full suite, 1 found in post-completion advisor review). **Impact on plan:** all five are necessary consequences of the graph/mechanism changes the plan itself specified, or corrections to test fidelity -- no scope creep, no architectural change.

## Issues Encountered

None beyond the deviations documented above. The "stripped invented email field" test construction (Task 1's 4th pairCreateOutcome.test.mjs case) required more care than the plan's literal wording suggested -- a bare stamped item with no identity classifies correctly even under the OLD code (it was never at risk from the guessed shape), so the meaningful RED case had to reconstruct the graph stub's ambiguous-identity scenario instead. Resolved by consulting the advisor before implementation; see key-decisions.

## TDD Gate Compliance

This plan is TDD-applicable (`phase.tdd-applicable: true`; Task 1 carries `type="tracer" tdd="true"`; Tasks 2-3 carry `tdd="true"`).

- **Task 1 (RED evidence):** `git stash push -- n8n/code/pairCreateOutcome.js`, re-ran `node --test tests/n8n/pairCreateOutcome.test.mjs` -- 2 of 14 tests failed (`AssertionError: 2 !== 1` and `'success' !== 'error'`), confirming the stamp-beats-shape behaviors were unimplemented. After rewriting the 4th case to an ambiguous-identity construction (per advisor guidance), re-ran RED -- 3 of 14 failed. Restored the source file (`git stash pop`), re-ran GREEN -- 14/14 pass.
- **Task 2 (RED evidence):** `git stash push -- scripts/build_cloud_workflows.py n8n/wf_contact_ingest_cloud.json n8n/wf_contact_ingest_local.json operator-claude-plugin/scripts/written_records.py`, regenerated, ran `node --test tests/n8n/ingestCreateErrorLane.test.mjs tests/n8n/ingestMixedBatch.test.mjs` -- all 3 new cases failed with `actual: 'create', expected: 'create_unconfirmed'`. Restored, regenerated, re-ran GREEN.
- **Task 3 (RED evidence, WR-10):** reproduced the OLD regex's truncation behavior directly in a scratch Python snippet (confirmed it returns an unbalanced string with no exception, the exact silent-truncation bug), then ran the new `tests/test_extract_js_const.py` against the ALREADY-FIXED code and confirmed all 4 pass, including the truncation case now raising. The sentinel-mechanism tests (Task 3's follow-up commit) were not separately RED-verified via stash (the mechanism's correctness was already established via the git commit itself and the node-name-dependent assertion structure), which is the one TDD gap in this plan -- documented here rather than silently omitted.
- **Fail-fast rule 3 (test-then-source commit shape):** NOT followed as separate `test(...)` -> `feat(...)` commit pairs per task -- each task's RED evidence was captured via a stash/restore cycle within a single working session and committed as one `feat(74-05): ...` commit containing both the source change and its tests together. Checked against `git log --oneline --grep="74-0[1-4]"`: 74-01, 74-03, and 74-04 all DO cut separate `test(74-0N): ...` commits ahead of their `feat(74-0N): ...` commits per task (e.g. `bf83e6ba test` -> `e7caad29`/`bc83d181`/`f3504fa2 feat` for 74-01; `17e3b0bf test` -> `4528b587 feat` for 74-03; `c8e51820 test` -> `3078e744`/`2810a333`/`52b3e402 feat` for 74-04) -- only 74-02 mixes the two shapes across its tasks. So this plan's single-commit-per-task shape is a genuine deviation from the canonical TDD commit-scope contract, not a continuation of an existing phase style as the prior wording of this note claimed. RED evidence itself was still captured for every implemented task (stash/restore, documented above); what was skipped is the commit-ledger visibility of that RED state, not the RED verification itself.

## Broken-Windows Ledger

All 5 deviations documented above were appended to `.planning/WINDOWS.md` (`--kind deviation
--phase 74`, one entry per deviation, entry ids visible via `open_count` moving 19 -> 24).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Nothing deployed; zero n8n executions consumed this plan (per the plan's own `<verification>` requirement -- confirmed, no deploy/bounce/dispatch script was run).
- `wf_contact_ingest_cloud.json` is regenerated and committed but NOT deployed -- plan `74-06` (wave 4) owns the scoped disarmed deploy, bounce, and proof send per D-74-11.
- The create-error lane's real n8n error-item shape stays `[documented]` only, per D-73-19 -- unchanged by this plan, correctly so (D-74-04's whole point is that correctness no longer depends on observing it).
- Full suite green at completion: `node --test tests/n8n/*.test.mjs` 1321/1321 pass; `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` 5170 passed / 160 skipped; `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` confirms idempotency post-commit.

---
*Phase: 74-code-review-follow-ups-from-phase-73*
*Completed: 2026-09-19*

## Self-Check: PASSED

All 13 key files confirmed present on disk; all 4 commit hashes (8948a8f5, aaf8ab44,
0dbeaa74, fd20d725) confirmed in `git log`. Full suite re-run at completion:
`node --test tests/n8n/*.test.mjs` 1321/1321 pass; `.venv/bin/python -m pytest -q
--tb=short -p no:cacheprovider` 5170 passed / 160 skipped; regeneration idempotency
confirmed (`git diff --quiet -- n8n/` exits 0 after a fresh regenerate).
