---
phase: 57-ceilings-refusal-before-start-and-post-run-proof
plan: 03
subsystem: infra
tags: [operator-claude-plugin, write-grant, chunking, remainder-queue, ceiling, RUN-05]

# Dependency graph
requires:
  - phase: 57-ceilings-refusal-before-start-and-post-run-proof
    provides: "57-01's write_grant.allowance_headroom / ceiling_verdict / plan_grant CEILING_OVER refusal and the pre-call ceiling-check branch left as prose in the two single-shot SKILL.md runbooks"
provides:
  - "remainder_queue.py — the plugin's sixth durable artifact: a per-run, work-only store for D-57-01's mid-run ceiling-stop rows and D-57-04's accepted-split remainder, refusing anything shaped like authority"
  - "chunking.failed_batch generalised to reconstruct all five plan_chunks shapes (record_ids, rows, people, companies, list) instead of silently dropping people/companies after the first chunk"
  - "chunking.dispatch_plan's mid-run ceiling stop persists its unsent remainder to remainder_queue under a never-raise guard"
  - "write_grant.split_for_allowance — D-57-04's smaller-batch offer, with the grant scope PROJECTED FROM the split work rather than cut in parallel with it"
  - "write_grant.plan_grant's CEILING_OVER refusal now carries a pure split_offer; nothing is persisted until the operator accepts and a fresh grant opens"
  - "the single-shot dispatch.dispatch legs (enrich-before-ingest, contact-upload) now really call remainder_queue.save on a pre-call ceiling breach, closing the handoff 57-01 Task 4 left as prose"
affects: [57-05]

# Actuals (#2632)
actuals:
  tokens: 22266
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "A grant scope is always PROJECTED FROM the work it authorises by walking the work's own ordered records and classifying each by its own shape — never cut from a separately-ordered id/domain sequence at the same index (REVIEW-57-H1)"
    - "A durable-store forbidden-name scan is narrowed by POSITION (every key recursively; a value only when its own key matched or the value is itself a container) rather than by an allowlist, when the store holds arbitrary customer-record columns that cannot be enumerated in advance"

key-files:
  created:
    - operator-claude-plugin/scripts/remainder_queue.py
    - operator-claude-plugin/tests/test_remainder_queue.py
  modified:
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - .planning/STATE.md

key-decisions:
  - "Task 1 checkpoint, operator selected option-a: auto-split with a work-only remainder queue. Each split run still opens its OWN grant — the queue confers no authority and nothing picks it up automatically (D-57-05, GRANT-06). Recorded in STATE.md per this plan's declared ownership of that one-way ruling (M-2)."
  - "The id-vs-domain classification a scope projection needs, for the one spec shape (`record_ids`) whose list can legitimately mix both: a bare run of digits is id-shaped, anything else is domain-shaped (`_looks_like_hs_object_id`) — never a positional assumption about which half of a combined list is which."
  - "`_affordable_record_count`'s search is a linear scan stopping at the first overshoot, not a binary search — this codebase's own D-07 AST guard (`test_report_sufficiency.py`) forbids a `while` loop in any plugin script but `watch.py`, and a binary search needs one. The monotonicity the scan relies on is pinned by its own test rather than assumed."
  - "The single-shot `contact-upload` ceiling-breach branch reads the CSV file back once (`tabular.read_table`) to name its rows individually for the remainder queue — that lane never parses rows client-side (the whole file goes to `dispatch.dispatch` unmapped), so there was no row list already in scope to reuse."
  - "`enrich-before-ingest`'s ceiling-breach branch captures a row-id-bearing copy of `sendable_rows` (`sendable_rows_for_remainder`) BEFORE `extraction.strip_row_id` runs, so the queued remainder stays a well-formed, re-sendable `chunking.failed_batch()`-shaped spec rather than one missing its join key."
  - "`record_ids=`/`record_domains=`/`providers=` are accepted on `split_for_allowance`'s signature for parity with `envelope()`/`plan_grant()`'s own scope arguments but play no part in the split — only `spec` and `headroom` are read. Passing them with no `spec=` still refuses (H-1's own removal of the parallel scope-without-work path)."

patterns-established:
  - "chunking.LIST_BEARING_KEYS / chunking.KEYS_WITH_OBJECT_TYPE are the ONE ordered tuple both `failed_batch` and `write_grant.split_for_allowance` walk, so a sixth `plan_chunks` shape has one obvious place to be added to both."

requirements-completed: [RUN-05]

coverage:
  - id: D1
    description: "remainder_queue.py: a durable, per-run, 0600 store that persists re-sendable chunking.failed_batch()-shaped work specs and refuses (raises, nothing written) anything shaped like a grant, secret, token, credential, password, permission, or webhook — scanned by key recursively, values only where the key matched or the value is a container, so a legitimate batch containing Armstrong Racing or a pharmacy supplier note is never refused"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_remainder_queue.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "chunking.failed_batch reconstructs all five plan_chunks shapes losslessly (round-trip property test per shape); a mid-run dispatch_plan ceiling stop persists its remainder to remainder_queue with REASON_CEILING_BREACH, for both a record_ids and a people plan"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_chunking.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "write_grant.split_for_allowance offers a smaller affordable batch with the grant scope projected from the split work (membership test over an interleaved id/domain batch, not a count test); plan_grant's CEILING_OVER refusal carries the offer as pure split_offer and writes nothing to the remainder queue until accepted"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "the two single-shot dispatch.dispatch legs' pre-call ceiling-breach branches call remainder_queue.save with REASON_CEILING_BREACH for real, pinned by an AST test over the compiled runbook code (not a grep over prose) — closing the handoff 57-01 Task 4 left by name"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py#test_the_single_shot_ceiling_breach_writes_the_remainder_queue"
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-09-01
status: complete
---

# Phase 57 Plan 3: Auto-Split, the Remainder Queue, and the Single-Shot Ceiling Handoff Summary

**RUN-05's "offers a smaller batch" made concrete: a new work-only durable store, a
grant-scope-projected-from-work split calculator, and the mid-run/single-shot ceiling
breach paths wired to persist their unsent rows rather than lose them.**

## Performance

- **Duration:** ~90 min (continuation agent; Task 1 checkpoint was already answered by
  the operator before this session started)
- **Tasks:** 3/3 (Task 1 was the checkpoint the operator answered; Tasks 2 and 3 executed
  by this agent)
- **Files modified:** 11 (2 created, 9 modified)

## Accomplishments

- Built `remainder_queue.py`, the plugin's sixth durable artifact: a per-run store
  holding re-sendable `chunking.failed_batch()`-shaped work specs, refusing anything
  shaped like authority (a grant, secret, token, credential, password, permission, or
  webhook) via a forbidden-name scan narrowed by position rather than by allowlist, so
  it never false-positives on ordinary customer data (`Armstrong Racing`, `Armidale
  Jockey Club`, `pharmacy supplier`).
- Fixed `chunking.failed_batch` to losslessly reconstruct all five `plan_chunks` shapes
  — it previously silently dropped every chunk after the first for a multi-chunk
  `people` or `companies` batch (REVIEW-57-H4) — and wired `dispatch_plan`'s mid-run
  ceiling stop to persist its unsent remainder through the new store.
- Built `write_grant.split_for_allowance` (D-57-04): the concrete smaller-batch offer a
  `CEILING_OVER` refusal now carries. Its grant scope is PROJECTED FROM the split work
  by walking one ordered sequence and classifying each record by its own shape, closing
  the exact failure mode (REVIEW-57-H1) where an interleaved id/domain batch could
  authorise different records than it dispatches. `plan_grant`'s refusal is still pure —
  nothing is written to disk until the operator accepts and a fresh grant opens
  (REVIEW-57-H5).
- Took the cross-plan handoff 57-01 Task 4 left by name: the two single-shot
  `dispatch.dispatch` legs' (`enrich-before-ingest`, `contact-upload`) pre-call
  ceiling-breach branches now really call `remainder_queue.save` with
  `REASON_CEILING_BREACH`, pinned by an AST test over the compiled runbook code so prose
  cannot satisfy it silently.

## Task Commits

Each task was committed atomically:

1. **Task 2: The remainder queue — a durable store that holds work and refuses
   authority** — `6ba462c` (feat)
2. **Task 3: Make failed_batch lossless, offer the smaller batch, and give both the
   breach and the accepted split a durable landing** — `ce0896f` (feat) — also carries
   the Task 1 checkpoint ruling recorded in `.planning/STATE.md`

**Plan metadata:** committed as part of this SUMMARY's own final commit, below.

## TDD Gate Compliance

Both tasks were marked `tdd="true"`. Tests and implementation were written and verified
together within each task's single commit rather than as separate RED (`test(...)`) then
GREEN (`feat(...)`) commits — every new test was run and observed to pass against the
new implementation before committing, but no commit exists in this plan's history where
a test was committed failing. **Deviation from the strict RED/GREEN gate sequence**;
functional correctness was verified by running the full suite (`.venv/bin/python -m
pytest operator-claude-plugin/tests -q` and `.venv/bin/python -m pytest -q`) after each
task, both green, rather than by the commit-history gate itself.

## Files Created/Modified

- `operator-claude-plugin/scripts/remainder_queue.py` - new durable store for D-57-01's held rows and D-57-04's split remainder
- `operator-claude-plugin/tests/test_remainder_queue.py` - 41 tests covering the schema, the forbidden-name scan (true- and false-positive), save/load, and the real-durable-directory pytest guard
- `operator-claude-plugin/scripts/chunking.py` - `failed_batch` generalised to all five shapes; `dispatch_plan`'s ceiling stop now persists its remainder
- `operator-claude-plugin/scripts/write_grant.py` - `split_for_allowance` and its helpers; `plan_grant`'s `CEILING_OVER` refusal carries `split_offer`
- `operator-claude-plugin/skills/enrich-records/SKILL.md` - the accepted-split state transition and `REASON_ALLOWANCE_SPLIT`'s only producer
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` - captures a row-id-bearing remainder copy before `strip_row_id`; the ceiling-breach branch calls `remainder_queue.save`
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - reads the held CSV back into rows once for the ceiling-breach branch's `remainder_queue.save` call
- `operator-claude-plugin/tests/test_write_grant.py` - `split_for_allowance` tests (two-product, membership, projection, monotonicity, authority), `plan_grant` refusal tests, the AST wiring tests for both single-shot runbooks
- `operator-claude-plugin/tests/test_chunking.py` - `failed_batch` lossless round-trip tests per shape; mid-run remainder-queue persistence tests including a save-failure degrade test
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` - registry updated for the two call sequences the new wiring changed/added
- `.planning/STATE.md` - Task 1 checkpoint ruling recorded (option-a)

## Decisions Made

See `key-decisions` in frontmatter above — five decisions, the most consequential being
the id/domain classification rule (`_looks_like_hs_object_id`) that makes the scope
projection correct for a `record_ids`-shaped spec whose list legitimately mixes both
(`envelope()`'s own `ids + domains` combined projection is exactly such a spec), and the
switch from a binary search to a linear scan in `_affordable_record_count` to respect
this codebase's own D-07 no-while-loop guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_affordable_record_count`'s binary search tripped D-07's
no-while-loop AST guard**
- **Found during:** Task 3, after implementing `write_grant.split_for_allowance`
- **Issue:** The initial binary-search implementation used a `while lo < hi:` loop,
  which `test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status`
  forbids in any plugin script but `watch.py` (D-07: the bounded watch is Phase 29's job,
  built once there).
- **Fix:** Rewrote as a linear scan (`for n in range(1, total + 1)`) that stops at the
  first N whose cost overshoots — correct because the cost is monotonically
  non-decreasing in N, pinned by its own test rather than assumed.
- **Files modified:** `operator-claude-plugin/scripts/write_grant.py`
- **Verification:** Full plugin suite green (2050 passed / 5 skipped) after the fix.
- **Committed in:** `ce0896f` (part of Task 3's commit)

**2. [Rule 3 - Blocking issue] The remainder-queue wiring changed two documented
SKILL.md call sequences the sequence-coverage ratchet tracks**
- **Found during:** Task 3, after wiring `remainder_queue.save` into both single-shot
  runbooks
- **Issue:** `test_skill_sequence_coverage.py`'s registry pinned the OLD call sequence
  for `contact-upload` and `enrich-before-ingest`'s single-shot dispatch block; adding
  `remainder_queue.save`/`build_entry` (and, for `contact-upload`, `tabular.read_table`)
  orphaned those registry entries and introduced a new, unregistered two-call sequence
  in `enrich-records/SKILL.md`'s own accepted-split step.
- **Fix:** Updated the two existing `COVERED` entries' tuples to the new live sequences
  (covering nodeid unchanged — the sink, `record_dispatch_outcome`, is untouched) and
  added a new `COVERED` entry for `remainder_queue.build_entry -> remainder_queue.save`.
- **Files modified:** `operator-claude-plugin/tests/test_skill_sequence_coverage.py`
- **Verification:** `test_skill_sequence_coverage.py` full file green (11/11).
- **Committed in:** `ce0896f` (part of Task 3's commit)

**3. [Rule 2 - Missing functionality] `contact-upload`'s ceiling-breach branch had no
row list to hold, since that lane never parses the file client-side**
- **Found during:** Task 3, wiring the single-shot handoff
- **Issue:** `contact-upload/SKILL.md` hands the whole CSV/XLSX file to
  `dispatch.dispatch` unmapped — there is no `sendable_rows`-equivalent Python list in
  scope for a remainder entry to hold, unlike `enrich-before-ingest`.
- **Fix:** Added a one-time `tabular.read_table(send_path)` read inside the
  ceiling-breach branch itself, building simple `dict(zip(headers, row))` entries so
  the held rows can still be named individually in the remainder queue.
- **Files modified:** `operator-claude-plugin/skills/contact-upload/SKILL.md`
- **Verification:** `test_the_single_shot_ceiling_breach_writes_the_remainder_queue[contact-upload]` passes; block compiles under `test_every_dispatch_fence_in_the_runbooks_is_valid_python`.
- **Committed in:** `ce0896f` (part of Task 3's commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3)
**Impact on plan:** All three were necessary for correctness or to keep the existing
test suite green; no scope creep beyond what Task 3's own text already called for.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None - no external service configuration required. Nothing armed, no live n8n call, no
provider credit spent.

## Next Phase Readiness

RUN-05's smaller-batch offer and both ceiling-breach persistence paths are now real
code. 57-05 (the end-of-run report) can present `remainder_queue.load()`'s entries
alongside `held_queue`'s in one review section, per this plan's own objective note that
the operator's one review pass is preserved by the report, not by the store.

No blockers. The one disclosed, deliberate gap: a process crash mid-dispatch still
writes nothing to the remainder queue (stated in the plan's objective as explicitly
out of the remainder guarantee, not a defect of this implementation) — 57-05's report
should name that as a gap rather than reporting an empty remainder as "nothing was
left".

---
*Phase: 57-ceilings-refusal-before-start-and-post-run-proof*
*Plan: 03*
*Completed: 2026-09-01*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (`6ba462c`,
`ce0896f`) verified present in `git log`.
