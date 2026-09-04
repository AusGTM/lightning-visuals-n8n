---
phase: 62-suggest-the-contacts-nobody-named
plan: 11
subsystem: api
tags: [operator-claude-plugin, watch, report_enrichment, n8n, gap-closure, G-62-6]

requires:
  - phase: 62-suggest-the-contacts-nobody-named
    provides: "wf_enrichment_cloud's contacts-propose lane (62-01..62-09), the async_ack/recover_async_dispatch recovery path (Phase 61), 62-UAT.md's live-proven G-62-6 finding naming executions 12096/12097/12098"
provides:
  - "62-11-DIAGNOSIS.md — Leg A (static graph walk) + Leg B (live, read-only, over 12096/12097/12098) establishing the mechanism BY EVIDENCE: Merge Winners' 3-edge fan-in runs once per branch when a batch's rows diverge (one row needs research, one does not), and every downstream verdict-row reader that took runs[0] alone silently discarded the other branch's row. No node anywhere ever drops an item — verdict: reader_reads_run_0."
  - "report.all_node_items(run_data, node_name) — concatenates every run's items in order, tolerating an absent node/non-list runs/malformed run entry exactly as _node_output_items already does for a single run"
  - "watch._build_response_rows and report_enrichment.enrichment_row_ledger read through it now — a 2-row chunk that splits at Merge Winners yields TWO verdicts, not one, so preingest.merge_enriched never reports a settled row as unanswered again for this reason"
  - "Q3's finding: both lost rows (row-2, row-5) came back from Lusha Enrich's own billing block at creditsCharged: 0 (NOT_FOUND) — contradicting the UAT root-cause note's balance-delta inference that a lost row almost certainly cost credit"
  - "Q4's finding: the synchronous path (preingest.rerequest_unanswered, enrich-records, contact-upload's enrich pass — all call chunking.dispatch_plan with async_ack defaulted False) carries the identical exposure through Respond to Webhook's first-arrival-wins semantics, quantified and NOT fixed here, recorded as a standing UAT item"
affects: [suggest-contacts, enrich-records, contact-upload, enrich-before-ingest, backend-status]

actuals:
  tokens: 7400
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "One shared all-runs traversal (report.all_node_items) sitting beside the existing single-run one (_node_output_items) rather than a second implementation — every verdict-row reader with live-evidenced multi-run exposure points at it; every metadata reader (remaining_credits_from_response, token_usage_from_execution) stays pinned to run 0's first item by design, since that is the correct semantics for a balance snapshot, not a defect"

key-files:
  created:
    - .planning/phases/62-suggest-the-contacts-nobody-named/62-11-DIAGNOSIS.md
  modified:
    - operator-claude-plugin/scripts/report.py
    - operator-claude-plugin/scripts/report_enrichment.py
    - operator-claude-plugin/scripts/watch.py
    - operator-claude-plugin/tests/test_watch_settle_reporting.py

key-decisions:
  - "Diagnosed before fixing, per the plan's gate: Leg A named Merge Winners' 3-edge fan-in as the structural lead; Leg B proved it live by walking all ~53 node names in each of the three fetched executions and showing every summed-across-runs total stays at 2 while watch._build_response_rows itself returns 1 — a reproduction of the shipped reader, not an inference"
  - "Q3 came back NO where the UAT's own arithmetic said 'almost certainly yes' — read from Lusha Enrich's own per-item billing block (creditsCharged: 0 on both lost rows) rather than a balance delta, per Decision 3's instruction to trust the provider node's own report over arithmetic. Also flagged, without over-claiming: the three executions' own billing sums to 3 credits for 6 rows, not the UAT's 7 — a second instance of the balance-delta caution the UAT already raised once, in the opposite direction this time"
  - "Fixed only the two call sites the evidence named (watch._build_response_rows, report_enrichment.enrichment_row_ledger) — report.py's contact-upload-workflow readers (contact_row_ledger, _write_node_items) were left untouched and named in the diagnosis's Remaining exposure section, since 12096/12097/12098 are LV Enrichment executions, not LV Contact Ingest, and carry no evidence either way for that workflow"
  - "Q4's synchronous-path exposure (Respond to Webhook's first-arrival-wins, reached by preingest.rerequest_unanswered) is recorded, not repaired — it needs a workflow-topology change through scripts/build_cloud_workflows.py plus an operator deploy, out of scope for an offline-verifiable plan per Decision 4"

requirements-completed: [SUGGEST-01, SUGGEST-04, SUGGEST-05]

duration: ~55min
completed: 2026-09-04
status: complete
---

# Phase 62 Plan 11: Diagnose and close G-62-6's row-loss reader defect Summary

**Merge Winners' 3-edge fan-in runs once per branch when a 2-row batch's rows diverge (one needs research, one does not); watch._build_response_rows and report_enrichment.enrichment_row_ledger took `runs[0]` only and silently dropped the other branch's row — proven live on executions 12096/12098, fixed with one shared `report.all_node_items` helper, and the synchronous path's identical exposure is named for the operator rather than guessed at.**

## Performance

- **Duration:** ~55 min
- **Completed:** 2026-09-04

## Accomplishments

### Task 1 — Diagnosis (`62-11-DIAGNOSIS.md`)

Two legs, both against the real repo/API, zero writes:

- **Leg A (static):** walked `n8n/wf_enrichment_cloud.json`'s connections and named
  every multi-inbound node on the contacts-propose path. `Merge Winners` (3 inbound:
  `IF Contact Research Needed` false-branch, `IF Contact Needs Judge` false-branch,
  `Apply Contact Judge Verdict`) is the one whose inbound edges are genuinely per-row
  data-dependent — everything downstream to `Build Response`/`Respond to Webhook` is
  single-inbound, so a split there propagates forward unchanged. Classified every
  `runs[0]`-only call site in `report.py`/`report_enrichment.py`/`watch.py` against the
  plan's verdict-row-vs-metadata table.
- **Leg B (live, `GET` only):** fetched `12096`/`12097`/`12098` with `includeData=true`
  and tabulated runs+items for every node present. `12096`/`12098` split into two runs
  of one item each starting at `Merge Winners`, staying split through `Set Data Quality
  + Gap Flag`, `Decide Action`, and `Build Response` — while `12097` (the control, where
  neither row was lost) never splits. No node's summed-across-runs total ever drops
  below its input in any of the three executions. Called the shipped
  `watch._build_response_rows(execution)` directly on `12096`: it returned 1 row against
  a summed `Build Response` total of 2 — the defect reproduced off the real reader with
  no code change, not merely inferred.
- **Q3:** matched `Lusha Enrich`'s own per-item `billing` block to `row_id` via `Build
  Identity`'s item order. Both lost rows (`row-2`, `row-5`) came back `NOT_FOUND` at
  `creditsCharged: 0` — the opposite of the UAT's "almost certainly yes" balance-delta
  inference. Also flagged (without extending scope to explain it): summing all six
  rows' own billing across the three executions gives 3 credits, not the UAT's 7.
- **Q4:** `Respond to Webhook`'s own 3-run trace in `12096`/`12098` demonstrates
  first-arrival-wins live (the builder's own comment on that node states this
  explicitly). `preingest.rerequest_unanswered` — the retry mechanism for exactly this
  gap — calls `chunking.dispatch_plan` with `async_ack` defaulted `False`, so a
  synchronous retry chunk that splits the same way would lose a row on the wire with no
  recovery path at all. Recorded, not implemented, per Decision 4.
- **Verdict:** `reader_reads_run_0`.

### Task 2 — the fix

- Added `report.all_node_items(run_data, node_name)`: concatenates every run's items in
  order, tolerating an absent node, a non-list run collection, and a malformed run entry
  exactly as `_node_output_items` already tolerates for a single run.
- Pointed `watch._build_response_rows` and `report_enrichment.enrichment_row_ledger` at
  it. Left `remaining_credits_from_response`, `token_usage_from_execution` (metadata,
  correctly pinned to run 0's first item), `watch._execution_carries_run_id` (single
  inbound edge, confirmed live), and `report.py`'s contact-upload-workflow readers
  (different workflow, no evidence) untouched.
- Zero change to any n8n workflow file or `scripts/build_cloud_workflows.py`.

## RED observed before the fix

```
FAILED test_build_response_rows_returns_every_run_not_just_run_zero
  AssertionError: a 2-row chunk that split at Merge Winders must yield TWO verdicts, not one
  assert ['row-a'] == ['row-a', 'row-b']

FAILED test_recover_async_dispatch_reports_both_rows_when_build_response_split_across_runs
  AssertionError: a 2-row chunk that split at Merge Winders must yield TWO verdicts, not one
  assert ['row-a'] == ['row-a', 'row-b']

FAILED test_enrichment_row_ledger_reads_every_run_of_decide_action
  AssertionError: assert ['1'] == ['1', '2']
```

(Two more tests failed on `AttributeError: module 'report' has no attribute
'all_node_items'` before the helper existed — the three above are the behavioral red
this plan's discipline requires: a real value mismatch against the shipped code, not a
missing-symbol error.)

All 20 tests in `test_watch_settle_reporting.py` pass after the fix. Full plugin suite:
2347 passed, 5 skipped (was 2339 passed, 5 skipped before this plan's 8 new tests).
`node --test tests/n8n/*.test.mjs`: 867 passed, untouched. `git status --porcelain n8n/
scripts/build_cloud_workflows.py`: silent.

## Cost / safety

Every network call this plan made was a `GET` against the n8n executions API
(`executions_client.get_execution`), reading `12096`/`12097`/`12098` with
`includeData=true`. No dispatch, no arming, no HubSpot write, no execution triggered.
The `Lusha Usage` node's own snapshot embedded inside all three fetched executions
reads `credits.remaining: 3886`, consistently across all three — matching the balance
`62-UAT.md` already recorded for the end of this round; nothing this plan did could move
it, since none of its calls touch Lusha.

## Deviations from Plan

None — plan executed exactly as written. Both legs ran, the verdict was
`reader_reads_run_0` (the lead hypothesis, upgraded by live evidence rather than
assumed), and Task 2 implemented the fix as specified.

## Known Stubs

None.

## Threat Flags

None — this plan added no new network endpoint, auth path, or schema change. The
threat register's five `mitigate` items (redaction discipline in the diagnosis artifact,
never echoing the API key, `GET`-only, the synthetic-fixture rule, the honest-report
property) were all held; see `62-11-DIAGNOSIS.md` for the redaction discipline itself.

## Self-Check: PASSED

- `.planning/phases/62-suggest-the-contacts-nobody-named/62-11-DIAGNOSIS.md` — FOUND, committed (`8437fe2`).
- `operator-claude-plugin/scripts/report.py` — FOUND, `all_node_items` present.
- `operator-claude-plugin/scripts/report_enrichment.py` — FOUND, `enrichment_row_ledger` reads through `all_node_items`.
- `operator-claude-plugin/scripts/watch.py` — FOUND, `_build_response_rows` reads through `report.all_node_items`.
- `operator-claude-plugin/tests/test_watch_settle_reporting.py` — FOUND, 8 new tests, all passing.
- Commit `8437fe2` (Task 1) — FOUND in `git log --oneline`.
- Commit `59dbab8` (Task 2) — FOUND in `git log --oneline`.
