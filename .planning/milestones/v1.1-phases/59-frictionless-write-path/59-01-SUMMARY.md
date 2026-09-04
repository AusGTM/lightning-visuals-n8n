---
phase: 59-frictionless-write-path
plan: 01
subsystem: enrichment-dispatch
tags: [python, pytest, durable-artifact, hubspot, n8n, chunking]

requires:
  - phase: 53-operator-openable-write-grant
    provides: chunking.dispatch_plan's per-chunk sequential send, write_grant's revoke-at-next-send contract (D-59-06)
provides:
  - "written_records.py: the plugin's third persisted artifact, classifying an n8n response item into written/created_id_unknown/not_written"
  - "chunking.dispatch_plan flushes every chunk's response into that artifact inline, keyed by a run_id"
  - "a proven partial-run guarantee (a mid-loop crash still leaves earlier chunks on disk) and a proven revoked-run guarantee (a revoked-but-completing run is recorded in full)"
affects: [59-02, 59-03, review-lane-authority]

actuals:
  tokens: 4955
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Third durable-artifact module mirroring run_manifest.py's own-schema/own-refusal discipline (never widening artifact_store.py or run_manifest.py itself)"
    - "Inline per-chunk flush inside an existing dispatch loop, never assembled after it, to survive mid-run process death"

key-files:
  created:
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/tests/test_written_records.py
  modified:
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md

key-decisions:
  - "The crash-survival test injects the process-kill RuntimeError by monkeypatching enrichment.dispatch_enrichment itself, not the transport's .post() -- dispatch_enrichment already wraps every transport exception (including a bare RuntimeError) into DispatchError, which dispatch_plan's loop deliberately catches and continues (D-11b). Injecting at the transport layer would never let the exception escape dispatch_plan at all, so the boundary the loop actually calls per chunk is where the plan's intent (a RuntimeError not one of the caught exception types) is achievable."
  - "written_records.append_chunk has no path= plumbing through chunking.dispatch_plan (only a keyword-only run_id was added, per plan). Tests that need an isolated artifact redirect written_records.written_records_path via monkeypatch instead."

patterns-established:
  - "A durable artifact's write path is redirected in tests via monkeypatching the module's own *_path() resolver, when the caller function (dispatch_plan) offers no path= parameter of its own."

requirements-completed: [D-59-07]

coverage:
  - id: D1
    description: "written_records.classify_item classifies an n8n response item into written/created_id_unknown/not_written per the backend's own action, dropping PII, raising on non-dict shape and on a value that looks like a secret/grant"
    requirement: D-59-07
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py (classify_item tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "chunking.dispatch_plan flushes each chunk's response into the artifact inline, immediately after responses.append(body), inside the existing loop"
    requirement: D-59-07
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py::test_a_dispatch_that_crashes_mid_loop_leaves_a_durable_file_holding_earlier_chunks"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py::test_a_clean_five_chunk_run_leaves_all_five_chunks_on_disk"
        status: pass
    human_judgment: false
  - id: D3
    description: "a revoked-but-completing dispatch (D-59-06) still leaves a complete written-records artifact, including chunks sent after the revoke; test_a_revocation_midway_does_not_stop_a_running_dispatch stays byte-identical"
    requirement: D-59-07
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_revoked_run_still_records_every_record_it_wrote"
        status: pass
    human_judgment: false
  - id: D4
    description: "plugin released as 0.21.0 with a matching CHANGELOG entry describing what shipped and what did not (grant-time disclosure text is unchanged, that is 59-03)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-28
status: complete
---

# Phase 59 Plan 01: Durable written-records artifact Summary

**A new `written_records.py` module classifies every n8n dispatch response into written/created_id_unknown/not_written and `chunking.dispatch_plan` flushes it into a durable JSON file per chunk, inline in the loop, so a run that dies mid-way or is revoked-but-completing still shows what actually landed in HubSpot.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-28
- **Completed:** 2026-08-28
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `written_records.py`: the plugin's third persisted artifact, with its own schema (`run_id`, `saved_at`, `entries`) and its own Phase 23 D-11 forbidden-name refusal, mirroring `run_manifest.py`'s own-schema-own-refusal discipline rather than widening either existing artifact module.
- `chunking.dispatch_plan` now flushes every chunk's response into that artifact IMMEDIATELY after `responses.append(body)`, inside the existing loop — proven by a test that raises a bare `RuntimeError` (injected at `enrichment.dispatch_enrichment`, the boundary the loop actually calls per chunk, since `dispatch_enrichment` itself wraps every transport exception into a caught-and-continued `DispatchError`) and asserts the durable file already holds the earlier chunks.
- A new sibling test (`test_a_revoked_run_still_records_every_record_it_wrote`) proves a D-59-06 revoked-but-completing run is recorded in full, including chunks sent after the revoke — with the pinned `test_a_revocation_midway_does_not_stop_a_running_dispatch` left byte-identical.
- Plugin released as 0.21.0 with a CHANGELOG entry naming exactly what shipped (the list) and what did not (the D-53-05 grant-time disclosure text, which is 59-03's job).

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "what got written" — one dispatch run, flushed per chunk** - `e8b6fde` (feat)
2. **Task 2: A revoked-but-completing run appears in the list in full** - `b44437a` (test)
3. **Task 3: Release hygiene — plugin version bump and CHANGELOG entry** - `a155717` (chore)

_No plan metadata commit yet — this SUMMARY + STATE/ROADMAP updates are the final commit for this plan._

## Files Created/Modified
- `operator-claude-plugin/scripts/written_records.py` - New module: `classify_item`, `append_chunk`, `load`, `written_records_path`, `WrittenRecordsError`
- `operator-claude-plugin/scripts/chunking.py` - `dispatch_plan` gained a keyword-only `run_id` and an inline `written_records.append_chunk` call; `DispatchOutcome` gained a `run_id` field
- `operator-claude-plugin/tests/test_written_records.py` - New test file covering `classify_item`, `append_chunk`, `load`, and the crash-survival tracer test
- `operator-claude-plugin/tests/test_write_grant.py` - One new sibling test for the revoked-run guarantee; the pinned D-59-06 test untouched
- `operator-claude-plugin/.claude-plugin/plugin.json` - Version bumped 0.20.0 -> 0.21.0
- `operator-claude-plugin/CHANGELOG.md` - New 0.21.0 entry

## Decisions Made
- The crash-survival test injects the process-kill exception by monkeypatching `enrichment.dispatch_enrichment` rather than the stub transport's `.post()`. Read closely: `dispatch_enrichment` wraps *every* exception a transport raises (including a bare `RuntimeError`) into `DispatchError`, and `chunking.dispatch_plan`'s loop deliberately catches `DispatchError` and continues (D-11b, existing behaviour, unmodified). A `RuntimeError` raised inside the transport's `.post()` would therefore never reach the test the way the plan's acceptance criteria need it to (propagating out of `dispatch_plan`) — it would instead be recorded as an ordinary failed chunk and the loop would carry on. Injecting at the boundary `dispatch_plan`'s loop actually calls per chunk (`enrichment.dispatch_enrichment`) is what makes "a RuntimeError not one of the three exception types the loop catches" (`NotArmedError`/`DispatchError`/`enrichment.RecordSpecError`) achievable in practice, and it still exercises exactly what the plan cares about: that the flush already happened for earlier chunks before the crash.
- `chunking.dispatch_plan` gained no `path=` parameter for the written-records artifact — only the keyword-only `run_id` the plan specified. Tests that need an isolated artifact file redirect `written_records.written_records_path` via `monkeypatch` instead of passing a path through `dispatch_plan`. This is the seam `test_written_records.py`'s crash test and `test_write_grant.py`'s new sibling test both use, and it keeps `dispatch_plan`'s signature exactly as the plan's wiring section specified (no additional plumbing beyond `run_id`).

## Deviations from Plan

None — plan executed exactly as written. The two decisions above are implementation choices within what the plan specified (it named the injection mechanism only loosely — "a stub transport that raises... on the THIRD chunk's post" — and named no `path=` plumbing for `dispatch_plan` at all), not deviations from any specified behavior.

## Issues Encountered

While writing the crash-survival test, the initial approach (raising the `RuntimeError` from a custom transport's `.post()` method) would have been silently absorbed by `enrichment.dispatch_enrichment`'s own `except Exception: raise DispatchError(...)` block and then caught-and-continued by `dispatch_plan`'s loop — never propagating as the plan's acceptance criteria require. Traced the exception-handling chain in `enrichment.py` and `chunking.py` before writing the test, and injected at the correct boundary (`enrichment.dispatch_enrichment` itself) instead. Documented in both the test's own comment block and in `written_records.py`'s test-file module docstring so a future reader does not repeat the same wrong assumption.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `written_records.py` and its `run_id`-keyed artifact are ready for 59-02/59-03 to build an operator-facing "what got written" report on top of.
- `DispatchOutcome.run_id` is now available to any caller (`preingest.py`, `scheduled_arm.py`) that wants to locate the artifact a run just wrote, though neither existing caller was changed in this plan (both stayed at their pre-existing call shapes; `run_id` defaults to a generated one when omitted).
- No blockers. The companies-lane create-confirmation gap (an id-less create staying `created_id_unknown` forever) is explicitly scoped out and named as a candidate for a later phase, per the plan's own `planner_assumptions`.

---
*Phase: 59-frictionless-write-path*
*Completed: 2026-08-28*

## Self-Check: PASSED

All created/modified files found on disk; all three task commit hashes (`e8b6fde`,
`b44437a`, `a155717`) found in git history.
