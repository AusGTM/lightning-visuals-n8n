---
phase: 69-held-rows-survive-the-round
plan: 01
subsystem: operator-claude-plugin
tags: [python, durable-storage, tdd, suggest-contacts, held-queue]

requires:
  - phase: 61-68 (various)
    provides: held_queue.py's shape (path resolution, atomic write, validate-before-write,
      forbidden-name refusal, classify_read) as the precedent to copy; suggest_contacts.py's
      partition_for_dispatch/_name_key/rounds[] structure as the caller-side contract
provides:
  - "suggestion_declines.py: a new, accumulating, multi-run durable store for
    suggestion-round declines, keyed by company_id + normalised name, disjoint by
    construction from confidence.ALL_HOLD_CODES"
  - "suggest_contacts.PARTITION_REASON_CODES (closed vocabulary), public name_key,
    company_id_for_index(rounds, index)"
affects: [69-02 (SKILL.md step 8 rewrite + standalone drain skill), 69-03 (send re-entry)]

actuals:
  tokens: 9708
  tasks: 3
  commits: 4
  plan_head_before: 6b16634

tech-stack:
  added: []
  patterns:
    - "Sibling durable store copied from held_queue.py's shape, never imported from it
      (forbidden-name refusal reimplemented verbatim, third instance in this plugin)"
    - "Composite string key for a JSON document (company_id + KEY_SEPARATOR +
      first + NAME_SEPARATOR + last) where the prior precedent used a single string key"
    - "Per-entry run_id instead of a document-level run_id, so the document accumulates
      across runs rather than being overwritten by the next one"

key-files:
  created:
    - operator-claude-plugin/scripts/suggestion_declines.py
    - operator-claude-plugin/tests/test_suggestion_declines.py
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py

key-decisions:
  - "Operator confirmed Task 1's checkpoint: write the accumulating, multi-run
    suggestion_declines.json document now, with its stated one-way and costly
    consequences understood (verbatim answer recorded below)."
  - "Task-level split within Task 2/3's TDD cycles followed the plan's own module-contents
    listing literally: ABSENT/PARSEABLE/ANOMALOUS constants land in Task 2 (GREEN) but the
    classify_read() function that uses them, plus partition_by_run/apply_action/
    DRAIN_ACTIONS, land in Task 3 -- so Task 2's RED->GREEN cycle never referenced those
    three names and Task 3 got its own genuine RED (AttributeError) against them."
  - "gsd-tools check tdd-red-evidence is unavailable in this install; RED evidence was
    read directly from pytest's own failure output at each cycle (ModuleNotFoundError for
    the brand-new module in Task 2's RED, AttributeError naming the three missing
    functions in Task 3's RED) and is reproduced below."

requirements-completed: [HELD-02, HELD-03]

coverage:
  - id: D1
    description: "A person partition_for_dispatch declined to send has a durable home:
      suggestion_declines.json, a sibling of held_queue.json, written 0600, resolved
      through the same durable_paths rule."
    requirement: HELD-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_a_real_held_person_survives_key_build_save_and_load"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_save_writes_at_mode_0600"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_queue_path_shares_a_parent_with_held_queue_but_not_its_name"
        status: pass
    human_judgment: false
  - id: D2
    description: "The store accumulates across runs (each entry carries its own run_id,
      the document carries none); a save validates every entry before writing anything,
      so a refused save leaves the previous file byte-identical."
    requirement: HELD-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_rekeying_the_same_person_from_a_later_run_replaces_the_entry_and_does_not_grow"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_a_refused_save_leaves_the_previous_file_byte_identical"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_saving_the_same_map_twice_produces_byte_identical_file_content"
        status: pass
    human_judgment: false
  - id: D3
    description: "An entry is keyed by company_id + normalised name (never row_id), so
      the same person re-found in a later round updates one entry instead of creating a
      second."
    requirement: HELD-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_entry_key_is_none_when_company_id_is_missing"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_company_id_for_index_returns_the_owning_companys_id"
        status: pass
    human_judgment: false
  - id: D4
    description: "confidence.ALL_HOLD_CODES gains no member and suggestion_declines.py
      neither imports confidence nor names any of its codes; a test asserts the two
      vocabularies are disjoint sets."
    requirement: HELD-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_partition_reason_codes_disjoint_from_all_hold_codes"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_suggestion_declines_module_does_not_import_confidence"
        status: pass
    human_judgment: false
  - id: D5
    description: "defer leaves the map unchanged; delete removes the entry and records
      nothing in its place (no tombstone, no suppression key); send/defer/delete/export
      are the four drain actions."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_apply_action_delete_removes_the_key_and_adds_no_tombstone"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_apply_action_defer_returns_an_equal_map_and_does_not_mutate_the_input"
        status: pass
    human_judgment: false
  - id: D6
    description: "The inherited forbidden-name false positive (the 'arm' marker matching
      inside a real name like 'Armidale Jockey Club') is refused, not silently dropped —
      pinned as known behaviour for plan 02's reporting path to rely on."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggestion_declines.py::test_a_real_company_name_containing_a_forbidden_marker_is_refused_not_dropped"
        status: pass
    human_judgment: false

duration: 47min
completed: 2026-09-08
status: complete
---

# Phase 69 Plan 01: Suggestion-round declines get a durable home Summary

**New `suggestion_declines.py` store — a sibling of `held_queue.json`, accumulating across
runs, keyed by `company_id` + normalised name, disjoint by construction from
`confidence.ALL_HOLD_CODES` — plus the `suggest_contacts.py` half of the contract
(`PARTITION_REASON_CODES`, public `name_key`, `company_id_for_index`).**

## Performance

- **Duration:** 47 min
- **Started:** 2026-09-08T06:11:00Z (orchestrator setup commit 6b16634)
- **Completed:** 2026-09-08T06:57:32Z
- **Tasks:** 3 (Task 1 checkpoint resolved via pre-supplied operator answer; Tasks 2 and
  3 each ran a full RED->GREEN TDD cycle)
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- A correctly-held person now survives a process exit: `suggestion_declines.py` gives
  `partition_for_dispatch`'s held rows a durable, 0600, atomically-written home under the
  same `durable_paths` directory `held_queue.json` already lives in.
- The store's schema deliberately diverges from `held_queue`'s in the two ways D-69-03/
  D-69-04 require: no document-level `run_id`/timestamp (each entry stamps its own
  `run_id`), and a composite `company_id::first|last` key instead of `row_id` (which
  changes every batch and would defeat cross-run dedupe).
- `suggest_contacts.PARTITION_REASON_CODES` is now a named, closed, five-member
  frozenset (`no_email`, `email_domain_freemail`, `email_domain_mismatch`,
  `company_domain_unknown`, `search_source_not_strong`) — pinned disjoint from
  `confidence.ALL_HOLD_CODES` by test, HELD-02's own requirement.
- `partition_for_dispatch`'s closing docstring paragraph, which falsely claimed the
  held-row path still routed through `confidence.assess()` -> `held_queue.build_entry()`,
  is corrected to name `suggestion_declines` instead.
- The store's full lifecycle is under test: `classify_read` (three states, no
  "wrong run"), `partition_by_run` (this-run vs backlog), and `apply_action` (the four
  drain decisions, `send`/`delete` removing the key with no tombstone, `defer`/`export`
  leaving it untouched).

## Task Commits

Each task was committed atomically, with Tasks 2 and 3 each producing a RED test commit
followed by a GREEN implementation commit (TDD, per plan):

1. **Task 1: Confirm the one-way multi-run document shape** — no commit (checkpoint;
   answer recorded below, no file under `operator-claude-plugin/` touched).
2. **Task 2 RED:** `04496ce` — `test(69-01): add failing tests for the
   suggestion-declines store (end-to-end + HELD-02)`
   **Task 2 GREEN:** `1ad349a` — `feat(69-01): give a suggestion-round decline a
   durable home (suggestion_declines.py)`
3. **Task 3 RED:** `410cafc` — `test(69-01): add failing tests for
   classify_read/partition_by_run/apply_action`
   **Task 3 GREEN:** `3f7668f` — `feat(69-01): add classify_read, partition_by_run
   and apply_action to the store`

**Plan metadata:** this commit (SUMMARY + STATE not touched per orchestrator instruction
— STATE.md/ROADMAP.md are updated by the wave orchestrator, not this plan).

## TDD Gate Compliance

Both `tdd="true"` tasks completed RED then GREEN, verified by reading pytest's own
failure output (no `gsd-tools check tdd-red-evidence` in this install):

- **Task 2 RED** (`04496ce`): running the newly-added test file failed at COLLECTION
  with `ModuleNotFoundError: No module named 'suggestion_declines'` — the expected
  failure for a test file exercising a module that does not exist yet. The two other
  behaviors under test in the same file (`suggest_contacts.PARTITION_REASON_CODES`,
  `suggest_contacts.company_id_for_index`) would independently have raised
  `AttributeError` had the module import succeeded; the import failure is the correct,
  earliest-possible RED for a brand-new module.
- **Task 2 GREEN** (`1ad349a`): `.venv/bin/python -m pytest
  operator-claude-plugin/tests/test_suggestion_declines.py
  operator-claude-plugin/tests/test_held_queue.py
  operator-claude-plugin/tests/test_suggest_contacts.py -q` → `201 passed`.
- **Task 3 RED** (`410cafc`): running `test_suggestion_declines.py` produced `15 failed,
  15 passed` — every new failure was `AttributeError: module 'suggestion_declines' has
  no attribute 'classify_read'|'partition_by_run'|'apply_action'`, naming exactly the
  three functions Task 3 adds; the 15 tests from Task 2's GREEN commit stayed green.
- **Task 3 GREEN** (`3f7668f`): `.venv/bin/python -m pytest
  operator-claude-plugin/tests/test_suggestion_declines.py -q` → `30 passed`. Full
  plugin suite: `2780 passed, 5 skipped` (Phase 68 baseline was `2750 passed, 5
  skipped` — this plan added tests only, no regressions). Repo-root suite (`.venv/bin/python
  -m pytest -q --tb=short`): `4538 passed, 154 skipped` (baseline `4508 passed, 154
  skipped`).

No REFACTOR commit was needed for either cycle — the GREEN implementations matched the
plan's own detailed module-contents specification closely enough that no post-GREEN
cleanup pass changed behaviour.

## Files Created/Modified

- `operator-claude-plugin/scripts/suggestion_declines.py` — new module: `queue_path`,
  `entry_key`, `build_entry`, `first_refusal`, `save`, `load`, `classify_read`,
  `partition_by_run`, `apply_action`, `DRAIN_ACTIONS`, `ROW_FIELD_ALLOWLIST`,
  `SuggestionDeclineError`, and the reimplemented `_looks_forbidden`/`_first_forbidden`.
- `operator-claude-plugin/scripts/suggest_contacts.py` — `PARTITION_REASON_CODES` added;
  `_name_key` renamed to public `name_key` (3 internal call sites + docstring updated);
  `company_id_for_index(rounds, index)` added; `partition_for_dispatch`'s closing
  docstring paragraph corrected.
- `operator-claude-plugin/tests/test_suggestion_declines.py` — new test module, 30
  tests, mirroring `test_held_queue.py`'s isolation idiom (explicit `path=` for most
  tests, `CLAUDE_PLUGIN_DATA` for the location test).

## Decisions Made

**Task 1 checkpoint — operator's verbatim answer (relayed to this executor by the
orchestrator, who had already presented and resolved the gate):**

> `proceed (Recommended)`

Selected from the two options `proceed` / `stop` in response to: "Plan 69-01 Task 1
confirm gate: write the accumulating multi-run suggestion_declines.json (D-69-03 as
locked)?" No file under `operator-claude-plugin/` was modified for Task 1 itself; the
first write of the multi-run document happened in Task 2's GREEN commit, as the plan
specifies.

Other decisions: see `key-decisions` in the frontmatter above (the Task 2/Task 3 symbol
split, and the RED-evidence-by-reading-pytest-output substitute for the unavailable
`gsd-tools check tdd-red-evidence`).

## Deviations from Plan

None — plan executed exactly as written. All `must_haves.truths`, `key_links`, and
`prohibitions` from the plan frontmatter were honored:

- `confidence.ALL_HOLD_CODES` is byte-identical to its pre-plan value (`git diff` over
  `operator-claude-plugin/scripts/confidence.py` is empty).
- `held_queue.py` is byte-identical to its pre-plan value.
- `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` prints nothing.
- No `while` loop, `import time`, `import sched`, or `sleep()` call was added anywhere.
- `suggest_contacts.py` gained no `search_fallback` import.
- `ROW_FIELD_ALLOWLIST` equals `set(extraction.canonical_props())` exactly (test-pinned),
  and never includes `row_id`.

## Issues Encountered

None.

## Known Stubs

None. Every function specified in the plan is fully implemented and under test; nothing
is deferred within this plan's own scope. (Plan 02 owns the SKILL.md routing that calls
into this store, and plan 03 owns the `send` drain action's write-path re-entry — neither
is stubbed here, they are simply out of this plan's scope by design.)

## User Setup Required

None — no external service configuration required. This plan is pure Python, no new
dependency, no HubSpot/n8n change.

## Next Phase Readiness

`suggestion_declines.py` and its `suggest_contacts.py` counterpart symbols
(`PARTITION_REASON_CODES`, `name_key`, `company_id_for_index`) are ready for plan
02's SKILL.md step 8 rewrite to call directly. `first_refusal` is exported specifically
so plan 02's per-entry pre-check (the `unstorable` reporting path) can use it before a
batch save. No blockers.

---
*Phase: 69-held-rows-survive-the-round*
*Completed: 2026-09-08*

## Self-Check: PASSED

- FOUND: `operator-claude-plugin/scripts/suggestion_declines.py`
- FOUND: `operator-claude-plugin/tests/test_suggestion_declines.py`
- FOUND commits: `04496ce`, `1ad349a`, `410cafc`, `3f7668f`
