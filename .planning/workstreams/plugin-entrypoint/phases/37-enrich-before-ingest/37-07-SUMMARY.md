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
  tasks: 2
  commits: 2

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

duration: ~25min (Task 1) + checkpoint resolution
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 07: queue_handoff_ids -- Landed Ids Off the Ledger, Never the Report Rows Summary

**`report.queue_handoff_ids` reads the reconciled ledger plus HubSpot Create's own write-node output to return every id a contact-upload run actually landed, at any batch size, never guessing a placeholder id. Task 2's transport decision resolved to option-b, delegated to and already landed in Phase 36 plan 36-07: the poller handoff is automatic at create time, no client code and no third arming phrase.**

## Performance

- **Duration:** ~25 min (Task 1) + checkpoint resolution (Task 2 resolved by delegation, no additional client execution time)
- **Completed:** 2026-08-05
- **Tasks:** 2/2 (Task 2 resolved as a decision + delegation, not a code task in this plan)
- **Files modified:** 2 (1 created, 1 modified) -- Task 2 touched no file in this plan; its resolution landed entirely in 36-07

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
2. **Task 2: choose the transport that sets `lv_enrichment_requested`** - decision only,
   no commit in THIS plan. Resolved to **option-b**, delegated to and landed in Phase 36
   plan 36-07: `bed5ee4` (feat, the stamp itself), `2455e70` (test, the two negative
   pins), `fef4bf4` (docs, 36-07's own SUMMARY).

_No separate plan-metadata commit for Task 1 alone -- this SUMMARY carries both tasks'
resolution, committed once, per `final_commit`._

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

None.

## User Setup Required

None -- no external service configuration required. The poller handoff is
automatic at create time (see Task 2 resolution below); no operator action, no
arming phrase.

## Task 2 Resolution: `lv_enrichment_requested` transport -- option-b, delegated and landed

The operator selected **option-b**: stamp `lv_enrichment_requested = "true"` in the
ingest lane's own create payload (backend, `scripts/build_cloud_workflows.py`),
rather than option-a (hand created ids to `enrich-records`, spending credits
immediately behind a third arming phrase) or option-c (report ids, operator
flags them in HubSpot by hand).

**Rationale (recorded verbatim from the operator's decision):**
- **Zero run-time credits.** The stamp costs nothing when the row is created --
  it queues a flag, it does not enrich. The existing 15-minute scheduled poller
  (already deployed, already sweeping `lv_org_type`/`lv_produces_content` gaps)
  picks the flag up on its own schedule.
- **No third arming phrase.** Option-a would have added a third grant in the
  same conversation turn right after the arming and preview grants, weakening
  §6's two-phrase design (each phrase should guard one distinct irreversible
  action at the moment it happens). Option-b needs no grant at all -- the
  operator never says a word about it.
- **Matches §13(b)'s stated mechanism exactly.** 37-CONTEXT.md's governing
  amendment names "set `enrichment_requested = true` on the created records ...
  so the existing scheduled poller sweeps" as the intended fix -- option-b IS
  that fix, not an approximation of it.

**This is backend work in a client-scoped phase**, so per the checkpoint's own
`resume-signal` it was handed to the Phase 36 amendment riding its
already-scheduled deploy, not executed inside this plan. It has since **landed**:

- `bed5ee4` (feat, 36-07) -- `DECIDE_CLOUD`'s create-only branch now stamps
  `properties.lv_enrichment_requested = "true"` on a created contact's payload
  (string `"true"`, matching the poller's `EQ` filter). Lives inside the branch
  already gated by `ALLOW_HUBSPOT_CREATE` -- a work-queue flag, not a second
  write gate. Regenerated `n8n/wf_contact_ingest_cloud.json` (only artifact
  that moved).
- `2455e70` (test, 36-07) -- two negative pins beside 36-07 Task 1's own tests:
  exactly one `lv_enrichment_requested = "true"` assignment (a second, hoisted
  above the create branch, would re-queue already-enriched records on every
  update), and the unprefixed `enrichment_requested` spelling is never assigned
  onto the payload -- the same trap this plan's own Task 1 guarded against
  client-side (T-37-31), now pinned backend-side too.
- `fef4bf4` (docs, 36-07) -- 36-07's own SUMMARY.md.

**Standing backstop:** 36-07's cons (every created contact gets queued,
including ones pre-ingest already fully enriched, relying on the poller's own
staleness gate to decide whether to act) is accepted per the checkpoint's own
threat register (T-37-30, disposition `accept`) -- the poller already applies
that same staleness gate to every other queued record. Live verification of
that gating behavior is deferred to 37-09's operator walk-through, not this
plan.

**For 37-08 (skill wording), explicitly:** the poller handoff is **automatic**
at create time. The skill text must say so plainly and must NOT describe a
third arming phrase, a confirmation step, or any operator action for the
handoff itself -- none exists. `queue_handoff_ids` (this plan's Task 1) remains
available for a future direct-enrichment path (option-a's lane) should that
ever be revisited, but nothing in the current skill flow calls it.

## Next Phase Readiness

- Quick gates re-run after the 36-07 delegation landed:
  `.venv/bin/python -m pytest operator-claude-plugin/tests/test_queue_handoff.py -q`
  -> 8 passed; `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` -> 0 for
  every file.
- Full suite counts as of Task 1's own commit (unaffected by 36-07, which
  touched no file this plan owns): `operator-claude-plugin/tests/ -q` -> 1215
  passed, 5 skipped (baseline post-37-05: 1207/5); repo-root
  `.venv/bin/python -m pytest -q` -> 2130 passed, 6 skipped at Task 1's commit,
  2134/6 after 36-07's own +4 tests landed on top (per the coordinator's
  reported current baseline); `node --test tests/n8n/*.test.mjs` -> 621 pass,
  unchanged throughout.
- `queue_handoff_ids` and the now-automatic poller handoff are both ready for
  37-08's skill wording.
- No blockers. Plan complete.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

`operator-claude-plugin/tests/test_queue_handoff.py` verified present on disk;
commit hashes `7d6fa28` (this plan's Task 1), `bed5ee4`/`2455e70`/`fef4bf4`
(36-07's delegated Task 2 resolution) all verified present in
`git log --oneline --all`.
