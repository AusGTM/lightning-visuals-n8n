---
phase: 37-enrich-before-ingest
plan: 07
subsystem: report
tags: [handoff, non-clobber, tdd, checkpoint-pending]

requires:
  - phase: 37-enrich-before-ingest
    plan: 04
    provides: "report.py's contact_row_ledger/reconcile/build_contact_report — the two-pattern read this plan extends"
provides:
  - "report.queue_handoff_ids(execution) -- created/updated_matched HubSpot ids a contact-upload run actually landed, read off the reconciled ledger and HubSpot Create's own write-node output, never build_contact_report's rows field"
affects: [37-08]

actuals:
  tokens: 10800
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "created-bucket ids read from the write node's OWN output items (HubSpot Create's confirmed response), not from Decide Action's pre-write ledger row -- a create action has no HubSpot id at decision time by construction, so _row_identity can never resolve one for it"
    - "updated_matched-bucket ids reuse _row_identity on the reconciled ledger row directly, since an update targets an existing record whose id was already known pre-write; the row-N placeholder fallback is excluded and reported rather than queued"

key-files:
  created:
    - operator-claude-plugin/tests/test_queue_handoff.py
  modified:
    - operator-claude-plugin/scripts/report.py

key-decisions:
  - "created ids are NOT correlated 1:1 back to a specific Decide Action row by position or by any other key -- they are read directly, in full, from HubSpot Create's own confirmed output items. This avoids the positional-zip failure mode 37-CONTEXT §12 already rejected for a different correlation (enrichment responses to rows) and is strictly more precise than the existing reconcile()'s per-action (not per-row) produced/not-produced boolean: every item present in the write node's own output is a HubSpot-confirmed landed id, regardless of how many rows were originally decided create."
  - "_write_node_produced_output was refactored to call a new _write_node_items helper (same node-run-to-items logic, now returning the list instead of a bare bool) rather than duplicating the run-lookup pattern a second time -- one read, two call sites."

requirements-completed: []

coverage:
  - id: D1
    description: "queue_handoff_ids returns the created row's id under created and the updated-matched row's id under updated_matched over the shared contact_execution fixture; ambiguous, rejected and not_confirmed rows appear in neither bucket."
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_queue_handoff.py::test_fixture_returns_the_created_and_updated_matched_ids, ::test_fixture_ambiguous_and_rejected_ids_appear_in_neither_partition, ::test_a_not_confirmed_row_appears_in_neither_partition"
        status: pass
    human_judgment: false
  - id: D2
    description: "Over a 25-row execution, build_contact_report(...)['rows'] is None while queue_handoff_ids still returns every landed id -- both asserted in one test, proving the function does not depend on the report's adaptive field."
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_queue_handoff.py::test_large_batch_returns_every_landed_id_even_though_report_rows_is_none"
        status: pass
    human_judgment: false
  - id: D3
    description: "A row whose identity falls back to the row-N placeholder is excluded and reported, never queued; the deployed lv_-prefixed property name is recorded in the module and the unprefixed spelling appears nowhere in report.py."
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_queue_handoff.py::test_a_row_whose_identity_falls_back_to_the_placeholder_is_excluded_not_queued, ::test_report_module_records_the_prefixed_property_name_only"
        status: pass
    human_judgment: false

duration: ~25min (Task 1 only -- paused at the Task 2 checkpoint)
completed: null
status: partial-checkpoint-pending
---

# Phase 37 Plan 07: queue_handoff_ids -- Landed Ids Off the Ledger, Never the Report Rows Summary

**Task 1 shipped and committed: `report.queue_handoff_ids` reads the reconciled ledger plus HubSpot Create's own write-node output to return every id a contact-upload run actually landed, at any batch size, never guessing a placeholder id. Task 2 is a blocking `checkpoint:decision` on the transport that sets `lv_enrichment_requested` -- execution paused here awaiting the operator's choice.**

## Performance

- **Duration:** ~25 min (Task 1 only)
- **Completed:** in progress -- paused at checkpoint
- **Tasks:** 1/2 (Task 2 is the blocking decision checkpoint, not yet resolved)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `report.queue_handoff_ids(execution)` added to `report.py`, placed immediately
  after `build_contact_report` per the plan's read-order intent. Built on
  `contact_row_ledger` + `reconcile` -- the same two calls `build_contact_report`
  makes -- and never on `build_contact_report(...)["rows"]`, which is `None`
  above `SMALL_BATCH_THRESHOLD` (20 rows) by design.
- `created` ids are read straight from `HubSpot Create`'s own confirmed output
  items (via a new `_write_node_items` helper), never from `Decide Action`'s
  pre-write ledger row -- a `create` action has no HubSpot id at decision time,
  so `_row_identity` can never resolve one for it.
- `updated_matched` ids reuse `_row_identity` on the reconciled row (an update
  targets an existing record whose id was already known pre-write). A row whose
  identity falls back to the `row N` placeholder is excluded and reported, never
  queued.
- Rows labelled `needs_review`, `rejected` or `not_confirmed` are excluded and
  reported in neither bucket.
- A module-level comment beside the function records the deployed, `lv_`-prefixed
  property name `lv_enrichment_requested` (verified live against
  `scripts/build_cloud_workflows.py`'s SJ-1/SJ-2 "Set Requested" nodes and its
  scheduled-jobs search filters) and states plainly that the unprefixed name in
  the repo-root CLAUDE.md is the generic design document, not the deployed
  schema.
- `_write_node_produced_output` refactored to call the new `_write_node_items`
  helper rather than duplicating the node-run-lookup pattern a second time.

## Task Commits

1. **Task 1: queue_handoff_ids -- the ids that actually landed, read off the ledger** - `7d6fa28` (feat)

_No separate plan-metadata commit yet -- this SUMMARY and STATE.md updates are for the orchestrator to commit per `final_commit` once the checkpoint resolves and the phase concludes._

## Files Created/Modified

- `operator-claude-plugin/scripts/report.py` -- added `queue_handoff_ids`,
  refactored `_write_node_produced_output` onto a new `_write_node_items` helper
- `operator-claude-plugin/tests/test_queue_handoff.py` -- new test file, 8 tests

## Decisions Made

- **`created` ids are read directly from the write node's own output, never
  correlated back to a specific Decide Action row.** Every item present in
  `HubSpot Create`'s confirmed output landed; reading it directly is strictly
  more precise than `reconcile()`'s existing per-action (not per-row)
  produced/not-produced boolean, and avoids any positional-zip correlation
  between two separately-shaped node outputs (the failure mode 37-CONTEXT §12
  already rejected for a different correlation).
- **`_write_node_produced_output` reuses a new `_write_node_items` helper**
  rather than a second run-lookup implementation -- one read (the node-run to
  items lookup), two call sites (the existing bool check and the new id read).

## Deviations from Plan

None -- Task 1 executed exactly as written.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 1:**
- (a) Re-implementing `queue_handoff_ids` on top of
  `build_contact_report(...)["rows"]` instead of the reconciled ledger:
  `test_large_batch_returns_every_landed_id_even_though_report_rows_is_none`
  failed -- `assert [] == ['1000', '1001', ..., '1024']` (`Right contains 25
  more items, first extra item: '1000'`) -- the large-batch handoff returned
  nothing, exactly the silent failure mode the plan names.
- (b) Grouping `needs_review` with `created` in the label-skip branch (so a
  review-outcome row silently skips the exclusion path, same as a landed
  create row):
  `test_fixture_ambiguous_and_rejected_ids_appear_in_neither_partition` failed
  -- `assert {'rejected'} == {'needs_review', 'rejected'}` (`Extra items in the
  right set: 'needs_review'`) -- the review row dropped out of `excluded`
  without being queued anywhere, silently vanishing from the accounting.

Both mutations were reverted immediately after confirming the failure; the
restored code and full suites were re-verified green before committing.

## Issues Encountered

None for Task 1.

## User Setup Required

**Task 2's checkpoint is a decision, not a setup step -- see below.**

## CHECKPOINT: Task 2 -- choose the transport that sets `lv_enrichment_requested`

Execution paused here. Task 2 is `type="checkpoint:decision" gate="blocking"` and
is not resolved. The full checkpoint state (options, evidence, awaiting) is
returned in the executor's structured reply to the orchestrator, not restated in
full here to avoid drift between two copies of the same decision -- see the
executor's `CHECKPOINT REACHED` response for this run.

In short: `queue_handoff_ids` (Task 1) produces the created/updated ids. Nothing
in this plan wires them to any transport that sets
`lv_enrichment_requested = true` -- that choice is the operator's, among:

- **option-a** -- hand created ids to the existing `enrich-records` lane (zero
  backend change, spends credits immediately, adds a third arming phrase).
- **option-b** -- set the property in the ingest lane's create payload
  (`scripts/build_cloud_workflows.py`, backend work riding Phase 36's
  already-scheduled deploy, costs nothing at run time, needs no arming).
- **option-c** -- report the ids and let the operator flag them in HubSpot
  manually (no code, but reintroduces the non-technical-operator failure mode
  v0.6 exists to remove).

## Next Phase Readiness

- Suite counts after Task 1 (all baselines held or exceeded by exactly the 8
  new tests): `operator-claude-plugin/tests/ -q` -> 1215 passed, 5 skipped
  (baseline post-37-05: 1207/5); repo-root `.venv/bin/python -m pytest -q` ->
  2130 passed, 6 skipped (baseline 2122/6); `node --test tests/n8n/*.test.mjs`
  -> 621 pass, unchanged; `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json`
  -> 0 for every file.
- `queue_handoff_ids` is ready for 37-08's skill wording once Task 2 resolves
  which transport calls it.
- Blocked on the Task 2 decision -- cannot proceed to a final phase commit or
  STATE.md/ROADMAP.md update until the operator selects a transport.

---
*Phase: 37-enrich-before-ingest*
*Completed: pending Task 2 checkpoint resolution*

## Self-Check: PASSED

`operator-claude-plugin/tests/test_queue_handoff.py` verified present on disk;
commit hash `7d6fa28` verified present in `git log --oneline --all`.
