---
phase: quick-260911-ao0
plan: 01
subsystem: operator-claude-plugin/tests
tags: [written-records, run-report, d-70-09, regression-test, todo-closure]
status: complete
dependency-graph:
  requires: [D-70-09 (Phase 70 Plan 06 Task 2)]
  provides: [end-to-end regression proof of the ledger write-gate on the recorded 2bc3617b row shape]
  affects: [operator-claude-plugin/tests/test_written_records.py]
tech-stack:
  added: []
  patterns: [pin a pathological production-observed shape as a module-level constant, reconstruct it from the rendered artifact rather than a missing capture, assert on the rendered report string rather than a ledger-double call count]
key-files:
  created: []
  modified:
    - operator-claude-plugin/tests/test_written_records.py
    - .planning/todos/completed/2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md
  deleted:
    - .planning/todos/pending/2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md
decisions:
  - "No production code changed — D-70-09's gate (chunking.dispatch_and_recover's `if can_write and rows:`) already fixes the todo; this task only proves it end to end on the recorded shape and closes the todo."
  - "The recorded row shape ({\"row_id\": \"row-2\"}) was reconstructed from the rendered report line, not from a captured body — no frozen body of run 2bc3617b's propose leg exists anywhere in the repo."
metrics:
  duration: "~25 min"
  completed: "2026-09-11"
actuals:
  tokens: 2266
  tasks: 2
  commits: 3
  plan_head_before: d5d385886f720d94c81ad91d24829f0b200c0bf4
---

# Quick 260911-ao0: Close written-records propose/enrich-legs-failed todo Summary

Two regression tests pin D-70-09's ledger write-gate against the exact pathological row
shape run `2bc3617b` recorded — proving it renders the todo's quoted failure line when
it reaches the ledger directly, and never reaches the ledger at all from a propose leg
while still landing from a write leg — then close the todo with a resolution record. No
production module changed.

## What Was Built

**Task 1** appended two test functions to the existing D-70-09 block at the end of
`operator-claude-plugin/tests/test_written_records.py`:

- `test_the_recorded_shape_renders_failed_when_it_reaches_the_ledger` — the control.
  Seeds `written_records.append_chunk` directly with the recorded shape
  `_RECORDED_ROW_2BC3617B = {"row_id": "row-2"}` (no `action`, no `object_type`, no
  `hs_object_id`), then asserts `run_report.build_run_report(...)["block"]` contains the
  literal substring `row-2 [contacts:unknown]: None -> failed` — proving the shape is
  genuinely pathological and this harness can genuinely see the ledger.
- `test_the_recorded_shape_reaches_the_ledger_only_from_a_write_capable_leg` —
  parametrized over a contacts `rows` (propose) spec form and a companies `record_ids`
  (write) spec form. Drives the SAME recorded row through
  `watch.recover_dispatch` (via the file's existing `_stub_channel` fixture) and
  `chunking.dispatch_and_recover`. Asserts: on the propose leg, the report's per-record
  section reads `- (no records)` and never mentions `row-2 [contacts:unknown]`; on the
  write leg, the row still lands and still renders `failed` — so the propose-leg pass is
  attributable to the D-70-09 gate, not to a harness blind spot.

Both tests use the block's existing `_patch_durable_dir(monkeypatch, tmp_path)` helper
first, so the real `written_records.append_chunk` write and `run_report`'s
`written_records.load()` glob resolve into one tmp directory.

**Task 2** appended a `## Resolved 2026-09-11` section to
`.planning/todos/pending/2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md`,
bumped its `updated:` frontmatter key, and moved it to
`.planning/todos/completed/` via `git mv`. The resolution names D-70-09 as the fix
already in place, the gate's exact call site
(`chunking.dispatch_and_recover`'s `if can_write and rows:`), both new test function
names, the run id `2bc3617b`, the reconstruction-not-capture caveat, and the two
sibling-surface facts a future reader would otherwise re-investigate
(`report_enrichment._outcome_for_row` reads a different ledger unaffected by this todo;
`run_report.py` needed no change because its per-record section only reads the ledger).

## Verification

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x -q`
  — 86 passed (up from 84; the 2 new functions collect 3 cases: 1 control + 2
  parametrized).
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 2875 passed, 5 skipped
  (full suite, no collateral damage).
- `git diff --stat operator-claude-plugin/scripts/ n8n/ scripts/` — empty throughout.
- `test ! -e .planning/todos/pending/2026-09-09-....md && grep -q "D-70-09" .planning/todos/completed/2026-09-09-....md` — OK.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 2's first commit landed the pre-edit todo body**
- **Found during:** Task 2, immediately after committing.
- **Issue:** `git add -A <pending-path> <completed-path>` was run after `git mv` had
  already staged the rename with the edited content. Because the `pending` path no
  longer existed (already moved), git's multi-pathspec `add` aborted the whole
  invocation with `fatal: pathspec ... did not match any files` before touching either
  path — but the *prior* `git mv` staging turned out not to have carried the edits
  either (root cause not fully isolated; observed effect: the first commit's diff
  against the original pending blob was `0 insertions(+), 0 deletions(-)`, i.e. it
  captured the pre-edit body verbatim under the new path).
- **Fix:** Re-staged the already-correct working-tree file (`git add` on the single
  existing path) and created a second, new commit carrying the Resolved section and the
  `updated:` bump — never amended the first commit, per instructions.
- **Files modified:** `.planning/todos/completed/2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md`
- **Commit:** `a6c2e5fa`

## Known Stubs

None.

## Threat Flags

None — the plan's own threat model (T-260911-ao0-01/02/03/SC) was fully mitigated as
specified: `_patch_durable_dir` used in both new tests, the recorded-row constant
carries only `row_id`, and the gate is proven bidirectionally.

## Self-Check: PASSED

- `operator-claude-plugin/tests/test_written_records.py` — FOUND (contains both new
  test functions, 86 tests collected and passing).
- `.planning/todos/completed/2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md`
  — FOUND, contains `D-70-09`.
- `.planning/todos/pending/2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md`
  — confirmed absent.
- Commit `145527c1` — FOUND in `git log`.
- Commit `580c67f8` — FOUND in `git log`.
- Commit `a6c2e5fa` — FOUND in `git log`.
