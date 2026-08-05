---
phase: 38-unanswered-rows
plan: 01
subsystem: enrichment-client
tags: [preingest, run-manifest, chunking, dispatch, honesty-guard]

# Dependency graph
requires:
  - phase: 37-post-match-lane
    provides: merge_enriched's row_id join, hold_emailless's held-entry shape, chunking.dispatch_plan / enrichment.dispatch_enrichment
provides:
  - "MergeResult.unanswered — a row no response item named, distinct from held and from a row that gained nothing"
  - "render_enriched_preview's unanswered_rows/unanswered_count group, rendered after held, never sampled"
  - "run_manifest.UNANSWERED as a fifth non-terminal-for-the-row verdict"
  - "preingest.rerequest_unanswered — one automatic re-request pass reusing chunking.dispatch_plan"
affects: [preingest.py, run_manifest.py, any future skill wiring the enrichment preview or the resume flow]

# Actuals (#2632)
actuals:
  tokens: 6662
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Frozen reason constants (UNANSWERED_REASON) shared between the layer that detects a fact and the layer that renders it, so the two can never phrase it differently"
    - "Partition-before-gate: exclude rows the gate has no evidence for BEFORE calling it, rather than post-filtering its output"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/scripts/run_manifest.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_preingest_preview.py
    - operator-claude-plugin/tests/test_run_manifest.py

key-decisions:
  - "unenriched_row_ids renamed to unanswered (not aliased) — entries carry {row_id, row, reason}, mirroring extraction.hold_emailless's held-entry shape"
  - "render_enriched_preview partitions unanswered rows out BEFORE calling extraction.hold_emailless, rather than filtering the gate's output after the fact — this is what stops a held-for-no-email fabrication at the source"
  - "rerequest_unanswered reconstructs a complete MergeResult by running merge_enriched a second time scoped to only the previously-unanswered rows, then stitching those merged rows back into the full original row order by id — never a single call over synthesized 'combined responses' for the whole batch, which would have required inventing response items for already-answered rows"
  - "run_manifest.UNANSWERED lands on the exact same non-terminal branch as UNCHECKED in rows_to_resume, not a new branch, so the two verdicts cannot drift apart in behavior over time"

requirements-completed: [STRUCT-02, STRUCT-04]

coverage:
  - id: D1
    description: "A row no response item names is classified `unanswered` (own group, distinct from SEND/HELD/conflicts), carrying the true reason; render_enriched_preview never reports it as held-for-no-email even when it has no email, and never puts it in the send set even when it has one"
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_an_unanswered_entry_carries_row_id_row_and_the_true_reason"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_preview.py::test_an_unanswered_row_with_no_email_is_never_held_for_it_the_live_bug_pinned"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_preview.py::test_an_unanswered_row_with_a_source_email_is_still_unanswered_not_sent"
        status: pass
    human_judgment: false
  - id: D2
    description: "unanswered_rows is rendered as its own group, in full, after held and before the sampled send rows, and never passes through preview._adaptive_sample"
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_preview.py::test_an_unanswered_batch_larger_than_the_adaptive_threshold_still_names_every_row"
        status: pass
    human_judgment: false
  - id: D3
    description: "run_manifest.ALLOWED_VERDICTS gains unanswered as a fifth word; rows_to_resume treats it as non-terminal on the same branch as unchecked; the three prior terminal verdicts are unchanged; _looks_forbidden('unanswered') is False"
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py::test_the_three_terminal_verdicts_partition_exactly_as_before_a_fifth_word_existed"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py::test_looks_forbidden_is_false_for_unanswered"
        status: pass
    human_judgment: false
  - id: D4
    description: "One automatic re-request pass runs, exactly once, through the existing chunking.dispatch_plan path, preserving original row_id values and threading armed through unchanged; no new send-shaped function is introduced"
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_rerequest_unanswered_dispatches_one_pass_and_narrows_the_unanswered_set"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py::test_rerequest_unanswered_request_bodies_carry_the_original_row_ids"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_retry_reuses_dispatch.py::test_exactly_one_module_defines_the_send_shaped_function"
        status: pass
    human_judgment: false

# Metrics
duration: 45min
completed: 2026-08-05
status: complete
---

# Phase 38 Plan 01: Unanswered Rows Summary

**A row the backend never answered for is now its own `unanswered` group — through merge, preview, and the resume manifest — with one automatic re-request pass that reuses the existing dispatch path instead of a second send.**

## Performance

- **Duration:** 45 min
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `merge_enriched`'s `unenriched_row_ids` renamed (not aliased) to `unanswered`, a tuple of `{row_id, row, reason}` entries carrying `UNANSWERED_REASON` — a frozen constant naming the truth: no verdict was received, never a claim about the row's own data.
- `render_enriched_preview` now partitions unanswered rows out **before** calling `extraction.hold_emailless`, closing the live bug where a two-row chunk answered with one item reported the other row HELD, "no usable email" — a fabricated reason, since the row's email may have been sitting in the response that never arrived. `unanswered_rows` renders as its own group, in full, after held and before the sampled send rows, never sampled (matching the held-row rule).
- `run_manifest.UNANSWERED` joins the four existing verdict words (five total in `ALLOWED_VERDICTS`). `rows_to_resume` treats it as non-terminal on the exact same branch as `unchecked` — a truncated row survives past the end of a session instead of being recorded as done.
- `preingest.rerequest_unanswered(rows, merge_report, providers, armed, config, transport=requests)` runs one re-request pass over exactly the unanswered rows, dispatched through the SAME `chunking.dispatch_plan` → `enrichment.dispatch_enrichment` path the first pass used. Reuses each row's original `row_id` (never `build_rows_spec`, which mints fresh ids). Exactly once — no loop, no counter, no recursion. `armed` is threaded through with no default. A row still unanswered after the pass keeps its true reason, including when its own re-request chunk fails outright.
- Both RED-CHECKs per task reproduced the exact failure mode they exist to prevent (quoted below).

## Task Commits

1. **Task 1: unanswered is its own group, with the true reason, out of the held set** — `640684a` (feat)
2. **Task 2: the manifest treats unanswered as non-terminal** — `0dabe3b` (feat)
3. **Task 3: one re-request pass, through the dispatch path that already exists** — `309239a` (feat)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `operator-claude-plugin/scripts/preingest.py` — `UNANSWERED_REASON` constant, `MergeResult.unanswered` (replaces `unenriched_row_ids`), `render_enriched_preview`'s unanswered partition/group/statement, `rerequest_unanswered`
- `operator-claude-plugin/scripts/run_manifest.py` — `UNANSWERED` verdict word, `ALLOWED_VERDICTS` (now five), `rows_to_resume`'s non-terminal branch, docstring/comment updates from "four" to "five"
- `operator-claude-plugin/tests/test_preingest_merge.py` — retargeted the three `unenriched_row_ids` assertions onto `unanswered`, added entry-shape/source-email/counts-sum cases, added the full `rerequest_unanswered` test section
- `operator-claude-plugin/tests/test_preingest_preview.py` — added the unanswered-group section (never-held-for-no-email, still-unanswered-with-email, never-sampled, both-boundaries statement, no-fabricated-reason)
- `operator-claude-plugin/tests/test_run_manifest.py` — added the five-word/`unanswered`-resume/`_looks_forbidden` section, plus an explicit unchanged-terminal-verdicts test

## Decisions Made

- **Field rename, not alias.** `unenriched_row_ids` → `unanswered` is a hard rename; the three existing test assertions were retargeted in Task 1's own commit rather than left pointing at a shim.
- **Partition-before-gate, not filter-after.** `render_enriched_preview` computes `answered_rows` (merged rows minus unanswered ids) and hands *that* to `extraction.hold_emailless`, rather than calling the gate over everything and then stripping unanswered entries from its `held` output. This is what makes the fabricated no-email reason structurally unreachable rather than merely filtered.
- **`unanswered_rows`' reason always comes from the constant, never from the entry's own `reason` field**, even though `merge_enriched` always sets it to the same constant today. This is a defensive choice: a caller building a `MergeResult` by hand (as every preview test does) cannot smuggle a different reason through the render layer.
- **`rerequest_unanswered` stitches by id rather than reconstructing one combined response list.** The plan's action text describes "calling `merge_enriched` again with the combined response list" over the full row set; since the function has no access to the FIRST pass's raw responses (only the already-joined `merge_report.rows`), synthesizing pseudo-response-items for already-answered rows to feed back through a single `merge_enriched(rows, combined)` call would have worked but added a needless layer of indirection. Instead: `merge_enriched(retry_rows, new_items)` runs scoped to just the unanswered subset, and the result is stitched into the original row order by `row_id` — a fully-equivalent "complete picture" returned to the caller, verified by `test_rerequest_unanswered_dispatches_one_pass_and_narrows_the_unanswered_set`.
- **Corrected Risk-1 analysis** (per the plan's must-haves, backstop-verified): the live truncation from the nine-directors walk was INTRA-BATCH — rows 5 and 6 were both waterfall rows in one two-row chunk, and `Build Response` returned on the first item's arrival, not a skip-vs-waterfall timing skew as originally suspected. That distinct backend fix stays deferred; this phase makes the client honest about the symptom (an unanswered row) rather than papering over it with a fabricated held reason.

## Deviations from Plan

None — plan executed exactly as written. The three RED-CHECKs specified in the plan's task actions were run and reverted as instructed (quoted below); no additional Rule 1/2/3 fixes were needed.

## RED-CHECK Evidence

**Task 1(a) — reverting the unanswered partition (`answered_rows = merged_rows`)** reproduces the live bug: `test_an_unanswered_row_with_no_email_is_never_held_for_it_the_live_bug_pinned` fails with
```
AssertionError: an unanswered row with no email must never land in held — the reason would be a fabricated claim about the row's data standing in for a claim about the response
assert {'row-2'} == set()
```

**Task 1(b) — routing `unanswered_rows` through `preview._adaptive_sample`** collapses the group: `test_an_unanswered_batch_larger_than_the_adaptive_threshold_still_names_every_row` fails with
```
AssertionError: assert 2 == 25
 +  where 2 = len({'leading': [...], 'trailing': [...]})
```

**Task 2 — removing `UNANSWERED` from the `rows_to_resume` resume branch** (leaving it in `ALLOWED_VERDICTS`) abandons the row: `test_a_row_verdicted_unanswered_is_included_on_the_same_branch_as_unchecked` fails with
```
AssertionError: assert () == ({'row_id': 'row-1', 'firstname': 'First', 'lastname': 'Doe', 'company': 'GCTC'},)
```
— the exact failure mode that would abandon a truncated row across sessions.

**Task 3(a) — wrapping the re-request dispatch in a loop** sends the batch twice: `test_rerequest_unanswered_dispatches_one_pass_and_narrows_the_unanswered_set` fails with
```
AssertionError: one re-request pass, and no more
assert 2 == 1
```

**Task 3(b) — re-minting ids via `build_rows_spec` instead of reusing the originals** orphans the join: `test_rerequest_unanswered_request_bodies_carry_the_original_row_ids` fails with
```
AssertionError: the re-request must reuse the ORIGINAL row_id values — a fresh mint would orphan every verdict the first pass recorded
assert {'row-1', 'row-2'} == {'row-2', 'row-3'}
```

## Issues Encountered

None.

## Verification Results

```
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q     # 1258 passed, 5 skipped (baseline: 1238/5)
.venv/bin/python -m pytest -q                                    # 2177 passed, 6 skipped (baseline: 2157/6)
node --test tests/n8n/*.test.mjs                                 # 621 pass (unchanged)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json              # 0 for every file
git status --short operator-claude-plugin/scratch                # empty
git diff --stat n8n/ scripts/                                    # empty — backend untouched
git diff --stat -- operator-claude-plugin/tests/test_retry_reuses_dispatch.py  # no changes; _EXPECTED_SEND_SHAPED unchanged
grep -n 'unenriched_row_ids' operator-claude-plugin/              # nothing outside __pycache__
```

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The unanswered group is now visible end-to-end (merge → preview → manifest → one re-request pass); a truncated batch is honest at every layer instead of only detected at the merge layer.
- The corrected Risk-1 finding (intra-batch truncation, not skip-vs-waterfall skew) is recorded above for whichever future phase takes up the deferred backend-side fix — this plan deliberately made no backend change.
- No blockers for downstream work in this workstream.

---
*Phase: 38-unanswered-rows*
*Completed: 2026-08-05*

## Self-Check: PASSED
