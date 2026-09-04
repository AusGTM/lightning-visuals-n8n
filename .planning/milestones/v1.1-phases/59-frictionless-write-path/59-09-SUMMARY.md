---
phase: 59-frictionless-write-path
plan: 09
subsystem: dispatch
tags: [n8n, hubspot, dispatch, written-records, scheduled-arm, operator-plugin]

# Dependency graph
requires:
  - phase: 59-frictionless-write-path
    provides: "59-07's written-records artifact and resolvable-payload gate closures; 59-08's per-run_id written_records_path signature and universal grant disclosure"
provides:
  - "A written-records bookkeeping failure (raised WrittenRecordsError, or append_chunk's falsey OSError return) never stops chunking.dispatch_plan — one guard catches both, the dispatch keeps sending, and the incomplete condition is surfaced loudly rather than swallowed."
affects: [chunking, scheduled_arm, enrich-records, enrich-before-ingest]

# Actuals (#2632)
actuals:
  tokens: 8955
  tasks: 3
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One guard in a dispatch loop catches both a raised bookkeeping exception and a documented falsey-return degrade path, so neither can silently short an artifact."
    - "An outcome name is never renamed to signal a secondary condition (records_incomplete) — the exit code and a dedicated field carry the page instead, so a genuine success is never mislabeled as a failure."

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/scripts/scheduled_arm.py
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/tests/test_scheduled_arm.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md

key-decisions:
  - "D-59-10 (operator, 2026-08-29): a records-write failure must never stop a dispatch — caught in the loop as DispatchError already is, recorded, and the run keeps sending. Honours D-59-06's shipped promise that once enrichment and writing start, the run continues until done."
  - "Rejected: aborting the dispatch on an unrecordable write — better for auditability in the abstract, but strands a batch mid-run, trading a known reportable gap for an unknown partial write state in HubSpot."
  - "The trade-off (a run can finish with an incomplete written-records list) is surfaced on four surfaces, never silently: chunking.DispatchOutcome.written_records_failures, scheduled_arm's returned outcome (with run_id), a non-zero process exit code without renaming the outcome, and both skills' relay to the operator."

patterns-established:
  - "Pattern: guard a documented degrade-on-I/O-error return value at the SAME call site as its sibling raised exception, rather than only catching the exception — a falsey return is just as capable of silently shorting an artifact."

requirements-completed: []

coverage:
  - id: D1
    description: "chunking.dispatch_plan catches both a raised WrittenRecordsError and append_chunk's falsey OSError return, recording the failure in DispatchOutcome.written_records_failures (empty-tuple default) and continuing the dispatch to completion."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_a_written_records_bookkeeping_failure_does_not_stop_the_dispatch"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_an_io_failure_in_append_chunk_is_caught_by_the_same_guard"
        status: pass
    human_judgment: false
  - id: D2
    description: "The chunk whose bookkeeping failed keeps the ChunkResult it already earned — not reported as a dispatch failure, not added to failed_batch for re-send."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py#test_a_bookkeeping_failure_does_not_flip_the_chunks_result_or_join_failed_batch"
        status: pass
    human_judgment: false
  - id: D3
    description: "scheduled_arm.py's stale 'dispatch_plan only raises NotArmedError' comment corrected in the same commit as the behaviour change; run_scheduled_arm_cycle carries written_records_failures, run_id and records_incomplete into both outcomes reporting a dispatch."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_scheduled_arm.py#test_a_written_records_bookkeeping_failure_still_completes_the_cycle"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_scheduled_arm.py#test_the_incomplete_outcome_carries_the_dispatchs_run_id"
        status: pass
    human_judgment: false
  - id: D4
    description: "The unattended process exit code is non-zero when records_incomplete is true, even for an otherwise-successful dispatched outcome — the outcome name itself is never renamed to hide it."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_scheduled_arm.py#test_an_incomplete_list_exits_non_zero_even_though_the_dispatch_succeeded"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_scheduled_arm.py#test_a_clean_cycles_exit_code_and_outcome_shape_are_unchanged"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both enrich-records and enrich-before-ingest skills lead their reporting instructions with the incomplete written-records condition, citing D-59-10, when it fires."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py#test_the_skill_reports_an_incomplete_written_records_list_loudly"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py#test_the_skill_reports_an_incomplete_written_records_list_loudly"
        status: pass
    human_judgment: false
  - id: D6
    description: "Plugin released at 0.28.0 with a matching CHANGELOG entry, in the same commit as the behaviour change."
    verification:
      - kind: unit
        ref: "grep -c '\"version\": \"0.28.0\"' operator-claude-plugin/.claude-plugin/plugin.json"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-29
status: complete
---

# Phase 59 Plan 09: A Written-Records Bookkeeping Failure Never Stops a Dispatch — Summary

**Closed gap 3 of `59-VERIFICATION.md`: `dispatch_plan` now catches a written-records bookkeeping failure (raised or falsey-returned) in one guard, keeps sending every remaining chunk, and reports an incomplete written-records list loudly across four surfaces instead of letting it crash the dispatch silently.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- `chunking.DispatchOutcome` gained `written_records_failures` (empty-tuple default, never `None`). One guard around the inline `written_records.append_chunk` call in `dispatch_plan`'s loop catches BOTH a raised `WrittenRecordsError` and `append_chunk`'s pre-existing falsey return on an `OSError` — the latter was a live, previously-ignored silent-short-artifact path of exactly the class D-59-10 names. A bookkeeping miss never flips the chunk's own `ChunkResult.ok`, and the chunk is never added to `failed_batch`.
- `scheduled_arm.py`'s comment claiming `dispatch_plan` could only raise `NotArmedError` from inside the armed window — stale since D-59-07's written-records flush landed in that loop — is corrected in the same commit as the behaviour change. `run_scheduled_arm_cycle` now carries `written_records_failures`, `dispatch_outcome.run_id`, and a `records_incomplete` boolean into both outcomes that report a dispatch (`dispatched` and `dispatch_failed`).
- `_exit_code(result)` extracted from `__main__` so it is directly testable: non-zero for anything in `_FAILURE_OUTCOMES`, OR when `records_incomplete` is true even for an otherwise-successful `dispatched` outcome. The outcome name itself is never renamed for this condition — the exit code alone carries the page, keeping a genuine dispatch success from reading as a failure.
- Both `enrich-records` and `enrich-before-ingest` skills' reporting instructions now lead with the incomplete-list disclosure, naming the missing chunk indices and stating plainly that the writes those chunks made may have landed even though they are absent from the artifact.
- Plugin released at 0.28.0 with a CHANGELOG entry documenting the trade-off and the rejected alternative.

## Task Commits

All three tasks landed as ONE commit, per this plan's explicit instruction (Task 3's action: "land as ONE commit carrying the bump and the CHANGELOG entry" — Tasks 1 and 2 were committed individually first, then folded together with `git reset --soft` + recommit, since `git rebase -i` is unavailable in this environment):

1. **Task 1: A bookkeeping failure records itself and the dispatch keeps going** — folded into the squashed commit below (originally `44c6fdf`, superseded)
2. **Task 2: The unattended path reports the incomplete list, names the run, and pages** — folded into the squashed commit below (originally `8444961`, superseded)
3. **Task 3: Both skills relay the incomplete list, and release the plugin at 0.28.0** — squashed with Tasks 1 and 2 into a single commit

**Squashed commit:** `abe05b3` — `feat(59-09): a written-records bookkeeping failure never stops a dispatch` (10 files changed, 445 insertions(+), 12 deletions(-))

## Files Created/Modified

- `operator-claude-plugin/scripts/chunking.py` — `DispatchOutcome.written_records_failures`; one guard in `dispatch_plan`'s loop catching a raised `WrittenRecordsError` and a falsey `append_chunk` return
- `operator-claude-plugin/scripts/scheduled_arm.py` — corrected stale comment; `run_id`/`records_incomplete`/`written_records_failures` carried into both dispatch-reporting outcomes; `_exit_code` extracted and made non-zero on an incomplete list
- `operator-claude-plugin/tests/test_chunking.py` — 5 new integration tests driving the failure through `dispatch_plan` itself
- `operator-claude-plugin/tests/test_scheduled_arm.py` — 4 new tests, including a full `run_scheduled_arm_cycle` integration test
- `operator-claude-plugin/skills/enrich-records/SKILL.md` — step 9 leads with the incomplete-list disclosure
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 5 leads with the incomplete-list disclosure
- `operator-claude-plugin/tests/test_enrich_skill_contract.py` — pin for the new disclosure paragraph
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — pin for the new disclosure paragraph
- `operator-claude-plugin/.claude-plugin/plugin.json` — 0.27.0 -> 0.28.0
- `operator-claude-plugin/CHANGELOG.md` — 0.28.0 entry

## Decisions Made

- **D-59-10** (operator, 2026-08-29): a records-write failure must never stop a dispatch. Caught in the loop as `DispatchError` already is, recorded, and the run keeps sending — honouring D-59-06's shipped promise. Rejected alternative: aborting the dispatch on an unrecordable write, which strands a batch mid-run in exchange for auditability that a loud, after-the-fact disclosure achieves just as well without the strand.
- Extracted `scheduled_arm._exit_code` as a small pure helper rather than leaving the exit logic inline in `__main__`, purely so Test 3/4 could exercise the exit-code contract directly instead of shelling out to the script — no behavioural change, a testability-only refactor.

## Deviations from Plan

None — plan executed exactly as written. The one interpretive call was where in `dispatch_plan` to place the bookkeeping-failure entry's `reason` text for the I/O-failure branch (no existing string to reuse, since `append_chunk` returns `False` rather than raising on `OSError`): a plain sentence ("the written-records artifact could not be saved (an I/O failure)") was authored inline, matching the tone of `_failure_reason`'s existing transport-failure strings.

## Issues Encountered

None. The write-tests needed `written_records.written_records_path` monkeypatched to a `tmp_path` file in every new test (following the precedent already set in `tests/test_write_grant.py::test_a_revoked_run_still_records_every_record_it_wrote`) to avoid leaving stray `written_records-*.json` artifacts in the operator's real durable state directory — confirmed this is the established pattern rather than inventing a new isolation mechanism.

## Next Phase Readiness

This closes the last of the three verification gaps this plan targeted (gap 3 of `59-VERIFICATION.md`) and is the final plan of Phase 59 (frictionless-write-path). Phase 59 is now ready for its overall verification pass / `/gsd-ship` review.

---
*Phase: 59-frictionless-write-path*
*Completed: 2026-08-29*
