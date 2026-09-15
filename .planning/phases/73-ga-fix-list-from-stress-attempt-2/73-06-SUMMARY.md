---
phase: 73-ga-fix-list-from-stress-attempt-2
plan: 06
subsystem: n8n-ingest-lane, offline-walker
tags: [n8n, carry-merge, identity-join, continueErrorOutput, tdd, walker]
requires:
  - phase: 73-ga-fix-list-from-stress-attempt-2 (plans 01-05)
    provides: the earlier waves' fixes to the ingest/company-match/review/throttle/cost lanes this plan's create-error containment sits beside
provides:
  - a duplicate-email (or any other) create rejection that costs its own row and nothing else — every surviving create in the same batch still associates to its own company
  - an identity join (n8n/code/pairCreateOutcome.js) that replaces the ingest lane's positional create-response pairing, closing the Pitfall 0 mis-association risk
  - a walker extension (continueErrorOutput second output) that makes the create-error lane provable offline, per D-73-19
affects: [73-07, any future onError=continueErrorOutput write node this lane or a sibling lane adds]
actuals:
  tokens: 17100
  tasks: 4
  commits: 4
tech-stack:
  added: []
  patterns:
    - "shape-based classification over an append merge's converged items (carried row has `action`, success response has `id`, anything else is an error item) instead of an added stamp node, when the three sources are already structurally disjoint by construction"
    - "alwaysOutputData on a node's own error branch as the fix for a downstream append-merge premature-drain race, distinct from (and safer than) a starved-lane sentinel: it does not add a second producer"
key-files:
  created:
    - n8n/code/pairCreateOutcome.js
    - tests/n8n/pairCreateOutcome.test.mjs
    - tests/n8n/walkerHttpErrorOutput.test.mjs
    - tests/n8n/ingestCreateErrorLane.test.mjs
    - .planning/todos/completed/2026-09-16-claude-md-13-0-1-by-value-vs-positional-join-discrepancy.md
  modified:
    - scripts/build_cloud_workflows.py
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/n8n/ingestCarryMerge.test.mjs
    - tests/test_merge_helpers.py
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/tests/test_written_records.py
    - n8n/wf_contact_ingest_cloud.json
    - CLAUDE.md
key-decisions:
  - "Classification inside 'Pair Create Outcome To Row' is by NATURAL SHAPE (a carried row always has `action`, a success response always has `id`, an error item has neither), not by an added marker/stamp node — the three sources feeding the merge are already structurally disjoint, and the plan's own Task 3 text permits this ('no intermediate classifier... a trivial stamp node is acceptable if the raw shape does not give one', which it does here)."
  - "[Rule 1 - Bug, found running Task 3's own suite] the plan's must-have that Create Carry Merge's error input needs no sentinel because the v1 drain covers it was correct in isolation but incomplete: never delivering on the common (zero-rejection) batch made that merge itself drain-only, and the resulting timing shift let a DOWNSTREAM append merge (Build Association Request Merge / Ingest Merge Response) drain prematurely off an immediate write-gate sentinel before the real create content ever arrived — silently dropping the association. Caught by three pre-existing, unrelated single-create tracer tests (ingestWidenedFieldsFlow.test.mjs) that went from green to merge_pending_runs_undrained the moment Task 3's third merge input existed."
  - "Fixed with alwaysOutputData on HubSpot Create (an existing, established mechanism this same builder already uses for 'Set Review'/'HubSpot Associate Company'), not a starved-lane sentinel — the plan's prohibition on a sentinel is about NOT adding a second producer; alwaysOutputData adds none, it only rescues the sole existing producer's otherwise-silent empty branch."
  - "walkerHttpErrorOutput.mjs correction (same commit as the AOD fix): a continueErrorOutput node's plain-array stub is now modelled as {success: <array>, error: []} — two outputs, the second literally empty — rather than 'one output, no second branch at all'. Observably identical for every stub that ignores the error branch (an empty array makes no v1 delivery either way, per the pre-existing rule), but it is what gives alwaysOutputData a branch to act on."
  - "The rejected row still resolves its own company in the create-error-lane test fixture — a create with NO resolved company is held for review before it ever reaches HubSpot Create at all (2026-08-25 operator ruling), so the rejection this plan proves is HubSpot's own 409-shaped refusal, never a company-hold."
patterns-established:
  - "When an append merge converges sources whose shapes are already structurally disjoint by construction, classify by shape inside the downstream Code node rather than adding a stamp node before the merge — fewer nodes, same offline provability."
  - "A node whose error branch can structurally never deliver in the common case (an httpRequest with onError=continueErrorOutput and few/no failures) needs alwaysOutputData on itself if ANY downstream append merge shares an input with an immediate/sentinel-driven producer — otherwise the walker's (and, unverified but plausibly the live engine's) one-drain-per-merge cap can silently starve the delayed real content."
requirements-completed: [F-A6]
coverage:
  - id: D1
    description: "Create Carry Merge switched to append mode; Pair Create Outcome To Row performs an identity join (email, then firstname+lastname+company, then linkedin_url) instead of combineByPosition — a shrinking response array can no longer mis-associate a later row's company."
    requirement: F-A6
    verification:
      - kind: unit
        ref: "tests/n8n/pairCreateOutcome.test.mjs"
        status: pass
      - kind: integration
        ref: "tests/n8n/ingestCarryMerge.test.mjs::short-return case: three net-new creates, one response missing — every response pairs with its OWN row's company"
        status: pass
    human_judgment: false
  - id: D2
    description: "The walker can drive an HTTP node's continueErrorOutput second output offline (D-73-19's proof mechanism)."
    requirement: F-A6
    verification:
      - kind: unit
        ref: "tests/n8n/walkerHttpErrorOutput.test.mjs"
        status: pass
    human_judgment: false
  - id: D3
    description: "HubSpot Create gets onError: continueErrorOutput; a rejected create leaves on the error output and becomes a create_failed refusal row carrying HubSpot's message (whitelisted fields only), never dumping the raw error object; every surviving create in the same batch still associates to its own company; a zero-rejection batch is unchanged in shape and loses no row."
    requirement: F-A6
    verification:
      - kind: integration
        ref: "tests/n8n/ingestCreateErrorLane.test.mjs"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py (create_failed -> FAILED)"
        status: pass
    human_judgment: false
  - id: D4
    description: "CLAUDE.md §13.0.1 describes the lane that actually exists (the pair node, the failure-row node, the alwaysOutputData fix) rather than the stale 'by value' positional-join prose; the question todo it raised is opened and resolved in the same plan."
    requirement: F-A6
    verification:
      - kind: manual_procedural
        ref: "CLAUDE.md §13.0.1 amendment + .planning/todos/completed/2026-09-16-claude-md-13-0-1-by-value-vs-positional-join-discrepancy.md"
        status: pass
    human_judgment: false
duration: ~100min
completed: 2026-09-16
status: complete
---

# Phase 73 Plan 06: Ingest create-error containment (F-A6) Summary

**A duplicate-email (or any other) HubSpot rejection of an ingest create now costs its own row — via `onError: "continueErrorOutput"` plus a shape-based identity join that replaces the lane's old positional pairing — instead of throwing and silently landing every other contact in the batch unassociated.**

## Performance
- **Duration:** ~100 min
- **Started:** 2026-09-16
- **Completed:** 2026-09-16
- **Tasks:** 4/4
- **Files modified:** 8 modified, 5 created

## Accomplishments
- Task 1: `n8n/code/pairCreateOutcome.js` — a pure identity join (email, then firstname+lastname+company, then linkedin_url) replacing `Create Carry Merge`'s `combineByPosition` pairing. Fails closed on an ambiguous or uncomputable key. RED observed first on a graph-level short-return case (`Create Carry Merge` reported `merge_dropped_rows`, itemCounts 2/3 — a shrinking response array mis-paired row 3's create with row 2's company under the old scheme); green after switching the merge to append mode and interposing `Pair Create Outcome To Row`.
- Task 2: extended `tests/n8n/lib/walkWorkflow.mjs`'s HTTP branch so a node with `onError: "continueErrorOutput"` yields a second output when its stub is shaped `{success, error}` — mirroring the pre-existing `if`-node two-output handling. RED observed first (`TypeError: (raw || []).map is not a function` on the shaped stub); green after.
- Task 3: `HubSpot Create` gets `onError: "continueErrorOutput"`; `Create Carry Merge` gains a third input straight from the error output (one producer, no intermediate classifier); `Build Create Failure Row` reads the pair node's classification and emits one `create_failed` refusal row per rejection (message/description/status code only, never the raw error object) or a single sentinel marker when the batch had no rejections. RED observed first on both the mixed-rejection and zero-rejection cases; green after.
- Task 3 deviation (Rule 1, found running the task's own suite): the plan's own must-have that the error input needs no sentinel because the v1 drain handles it was true in isolation but incomplete — it made `Create Carry Merge` itself drain-only in the common (zero-rejection) case, and that timing shift let `Build Association Request Merge` drain prematurely off an immediate write-gate sentinel before the delayed real create content ever arrived, silently dropping the association. Three pre-existing, unrelated tracer tests (`ingestWidenedFieldsFlow.test.mjs`) caught this live, going from green to `merge_pending_runs_undrained`. Fixed with `alwaysOutputData` on `HubSpot Create` (an established mechanism, not a new producer) plus a matching walker correction so a plain-array stub's implicit empty error branch can carry that marker too.
- Task 4: opened and closed the §31 question todo on CLAUDE.md §13.0.1's stale "by value" join description in the same commit (the trigger — this plan's own lane design — fired within the plan itself); corrected §13.0.1 to name the pair node, the failure-row node, and the `alwaysOutputData` fix.

## Task Commits
1. **Task 1: identity-join HubSpot Create's outcome, replacing positional pairing** - `fbd275a5` (feat)
2. **Task 2: teach the walker an HTTP node's error output (D-73-19)** - `d887aa60` (feat)
3. **Task 3: the create_failed refusal lane (D-73-01)** - `10e40db6` (feat)
4. **Task 4: settle the §13.0.1 pairing discrepancy** - `0fa4aefc` (docs)

## Files Created/Modified
- `n8n/code/pairCreateOutcome.js` - pure identity join, no n8n global, no by-name read
- `tests/n8n/pairCreateOutcome.test.mjs` - unit coverage for the join
- `tests/n8n/walkerHttpErrorOutput.test.mjs` - the walker's own error-output coverage
- `tests/n8n/ingestCreateErrorLane.test.mjs` - the create_failed lane's graph-level proof
- `scripts/build_cloud_workflows.py` - `_hs_http_create_node`'s new `on_error` param, `PAIR_CREATE_OUTCOME_JS`, `BUILD_CREATE_FAILURE_ROW_JS`, `BUILD_INGEST_RESPONSE`'s `failed` overlay, the ingest lane's new wiring
- `tests/n8n/lib/walkWorkflow.mjs` - HTTP branch's second output + plain-array-stub `{success, error: []}` normalisation
- `tests/n8n/ingestCarryMerge.test.mjs` - short-return case; "exactly one outbound edge" assertion updated for HubSpot Create's two branches
- `tests/test_merge_helpers.py` - merge-inventory assertions updated (Create Carry Merge now append; Ingest Merge Response now 6 inputs)
- `operator-claude-plugin/scripts/written_records.py` - `create_failed` -> `FAILED`
- `operator-claude-plugin/tests/test_written_records.py` - the twelfth action literal
- `n8n/wf_contact_ingest_cloud.json` - regenerated (disarmed)
- `CLAUDE.md` - §13.0.1 amended
- `.planning/todos/completed/2026-09-16-claude-md-13-0-1-by-value-vs-positional-join-discrepancy.md` - opened and closed

## Decisions Made
See `key-decisions` in frontmatter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 3's own must-have about the drain covering the error input was incomplete; a downstream append merge could drain prematurely and silently drop a create's association**
- **Found during:** Task 3, running its own new test suite plus the pre-existing `ingestWidenedFieldsFlow.test.mjs`
- **Issue:** Giving `Create Carry Merge` a third (error) input that structurally never delivers in the zero-rejection case turned it from a normally-completing merge into a drain-only one. `Build Association Request Merge` (fed by an immediate write-gate sentinel on its Update-lane input, and by this merge's delayed real content on its Create-lane input) could complete via the walker's one-drain-per-merge cap using ONLY the sentinel, before the real content ever arrived — the association was silently lost. `Ingest Merge Response` had the identical race for `Build Create Failure Row`'s own contribution.
- **Fix:** `set_always_output_data(nodes, ["HubSpot Create"])` — the node's error branch now delivers an empty marker during normal processing whenever it would otherwise be silent, restoring `Create Carry Merge`'s normal (non-drain) completion in the common case. Paired with a walker correction so a plain-array stub (every pre-existing test's shape) is treated as `{success: <array>, error: []}` rather than "no second branch at all" — observably identical for any test that ignores the error branch, but necessary for `alwaysOutputData` to have a branch to act on.
- **Files modified:** `scripts/build_cloud_workflows.py`, `tests/n8n/lib/walkWorkflow.mjs`
- **Verification:** `ingestWidenedFieldsFlow.test.mjs`'s four previously-broken tests pass again; `ingestCreateErrorLane.test.mjs`'s zero-rejection case explicitly asserts no starvation.
- **Commit:** `10e40db6`

**2. [Rule 1 - Bug] Pre-existing merge-inventory and action-vocabulary tests needed updating for this plan's structural changes**
- **Found during:** Tasks 1 and 3, running the full pytest suite
- **Issue:** `test_merge_helpers.py` asserted `Create Carry Merge` was `combine` mode (now `append`) and `Ingest Merge Response` had 5 inputs (now 6); `test_written_records.py`'s circularity guard failed once `create_failed` became a real action literal the builder emits.
- **Fix:** Updated both tests' assertions to the new, correct values, and added `create_failed -> FAILED` to `written_records.ACTION_TO_OUTCOME`.
- **Files modified:** `tests/test_merge_helpers.py`, `operator-claude-plugin/scripts/written_records.py`, `operator-claude-plugin/tests/test_written_records.py`
- **Verification:** full pytest suite green (4990 passed / 154 skipped, up from the 4989/154 baseline).
- **Commits:** `fbd275a5`, `10e40db6`

**Total deviations:** 2 (both Rule 1 — auto-fixed bugs found while running this task's own and pre-existing tests)
**Impact on plan:** None on scope or design intent; both were bugs the plan's own verification loop was designed to catch, and both are now covered by tests that would fail again if regressed.

## Known Stubs
None.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required. Per CLAUDE.md's project-standing rules, nothing in this plan armed, deployed, or bounced any n8n workflow; every regenerated `n8n/wf_*.json` still reads fully disarmed.

## Next Phase Readiness
- `node --test tests/n8n/*.test.mjs`: 1215 pass / 0 fail (baseline 1170/0 for this plan; 1196/0 measured at plan start).
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/`: 4990 passed / 154 skipped (baseline 4952/154 for this plan; 4989/154 measured at plan start).
- `scripts/build_cloud_workflows.py` regeneration is idempotent — zero `n8n/` diff after this plan's commits.
- Every regenerated workflow body still reads disarmed (`ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` etc. all `"false"`).
- F-A6 is closed. Per D-73-19 the create-error lane stays `[documented]`/offline-proven only — it becomes eligible for a `[observed live]` tag only after the operator's end-of-phase deploy + disarmed proof (and, per the phase's own scope, a real production race, since the operator's own dedupe fix in an earlier plan removes attempt 3's natural 409 trigger).
- Remaining phase work (per `73-CONTEXT.md`'s finding list) is tracked in sibling plans; this plan closes F-A6 only.

---
*Phase: 73-ga-fix-list-from-stress-attempt-2*
*Completed: 2026-09-16*

## Self-Check: PASSED

- All 5 key-files.created exist on disk (verified with `[ -f ]`).
- All 4 task commit hashes (`fbd275a5`, `d887aa60`, `10e40db6`, `0fa4aefc`) found in `git log --oneline --all`.
- `node --test tests/n8n/*.test.mjs`: 1215 pass / 0 fail.
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/`: 4990 passed / 154 skipped.
- `scripts/build_cloud_workflows.py` regeneration: zero `n8n/` diff.
- `HubSpot Create` reads `onError: continueErrorOutput`; `HubSpot Update` reads `onError: None` — verified directly against the committed JSON.
