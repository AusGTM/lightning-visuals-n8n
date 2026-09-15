---
phase: 73-ga-fix-list-from-stress-attempt-2
plan: 04
subsystem: operator-plugin-contact-upload-dedupe
tags: [operator-plugin, csv, dedupe, contact-upload, preview, identity-groups]

requires:
  - phase: 73-ga-fix-list-from-stress-attempt-2
    provides: "73-01/73-02/73-03's frozen-runData discipline and TDD gate conventions (unrelated code paths, same phase)"
provides:
  - "csv_dedupe.py: a plugin pre-flight collapse for within-batch duplicate CSV rows on the plain contact-upload lane, reusing extraction.py's identity-group primitives (never extraction.dedupe()/_merge_cluster, whose merge-and-conflict semantics contradict D-73-04's first-wins-verbatim rule)"
  - "duplicate_in_csv: the outcome a losing row is reported with, naming the winner's row number, identity key, and never refusing the batch"
  - "preview.py's collapsed_rows/pre_collapse_row_count: the operator-facing surface that shows the collapse and lets the operator reconcile the count they expected against the count being sent"
  - "contact-upload/SKILL.md step 2c: runs csv_dedupe.py --apply unconditionally (no operator review needed — exact match only) and forwards deduped_path as the one path previewed and dispatched"
affects: [contact-upload-preview, contact-upload-dispatch]

actuals:
  tokens: 8018
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "propose/apply idiom (mirrors name_split.py/header_suggest.py): a read-only propose that reports without writing, and an apply that writes a corrected copy into the scratch dir and returns its path — csv_dedupe.py is a new sibling of that idiom, not a new shape"
    - "Reuse the clustering PRIMITIVES (_first_satisfied_key/_group_presence/_casefold_trim/identity_groups), never the RESOLUTION function (dedupe()/_merge_cluster) — the two differ on purpose (merge-and-conflict vs. first-wins-verbatim) and this repo's own research flagged reusing dedupe() unmodified as the single highest-risk misread of this plan"
    - "A sidecar JSON report (collapsed_path) carries the collapse list from the apply step to the preview step across two separate subprocess invocations, so preview.py never imports csv_dedupe (no cycle: csv_dedupe already imports preview for mapping resolution) and never re-derives the collapse itself — display of a result, not a second computation of it"

key-files:
  created:
    - operator-claude-plugin/scripts/csv_dedupe.py
    - operator-claude-plugin/tests/test_csv_dedupe.py
  modified:
    - operator-claude-plugin/scripts/preview.py
    - operator-claude-plugin/skills/contact-upload/SKILL.md

key-decisions:
  - "Row numbering is 1-based with the header as row 1 (first data row = row 2), matching this repo's own stress-session vocabulary (SESSION-2026-09-15.md: 'rows 37/38 = row 3')."
  - "csv_dedupe.py maps raw CSV headers onto canonical prop names via preview.label_headers/resolve_mapping_path (the SAME alias lookup preview.py's own display labelling uses) before running identity-group clustering — the real attempt-2 CSV used aliased headers ('E-mail Address', 'Surname', 'LinkedIn'), not canonical names, so clustering on raw headers directly would never have fired on the actual defect."
  - "csv_dedupe.py does NOT import preingest.rows_from_table (which does the same canonical-mapping) to avoid coupling the plain contact-upload lane's new module to the enrich-before-ingest-specific module; the ~5-line mapping loop is small enough to duplicate rather than pull in a much larger, differently-scoped module."
  - "Step 2c ('Collapse within-batch duplicates') runs unconditionally and without asking the operator — unlike step 2b's name-split, there is no ambiguity to review: the match is exact, casefolded, trimmed only. It runs on whatever path step 2b left (split_path/corrected_path/original), never re-running against the original the way step 2b's own --confirm rule requires, because it needs the fully-resolved columns (e.g. a name only just split by step 2b) to see the identity groups that matter."
  - "preview.py's build_preview() gained an optional collapsed=None parameter and a --collapsed <file.json> CLI flag reading csv_dedupe.py's own sidecar report — always emits collapsed_rows (count 0 when empty/absent) and pre_collapse_row_count (row_count + len(collapsed)) so a caller renders one shape either way and the operator can reconcile the count they expected against the count being sent."
  - "Every apply_dedupe() call in tests passes an explicit scratch_dir=tmp_path/\"scratch\" (matching name_split.py/header_suggest.py's own test discipline) after an initial oversight wrote deduped-contacts.csv/dedupe-report-contacts.json into the real operator-claude-plugin/scratch/ directory — caught by the pre-existing test_git_status_short_shows_no_writes_to_the_real_plugin_scratch_directory guard, fixed, and the two stray files were removed before committing."

requirements-completed: [F-A5]

coverage:
  - id: D1
    description: "csv_dedupe.py: propose/apply first-wins collapse on extraction's identity-group rule, reporting duplicate_in_csv and never refusing the batch"
    requirement: F-A5
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py (18 tests: case/whitespace email dup, name+company group, linkedin-only group, distinct-people/identity-less-row non-collapse, 3+ occurrence collapse, column/row order preservation, no-refusal, no-merge, no fuzzy matching, no extraction.dedupe()/_merge_cluster call)"
        status: pass
    human_judgment: false
  - id: D2
    description: "preview.py surfaces the collapse (collapsed_rows, pre_collapse_row_count) before any send; contact-upload/SKILL.md's new step 2c wires csv_dedupe.py --apply into the corrected-path chain and forwards deduped_path to preview + dispatch"
    requirement: F-A5
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py::test_build_preview_surfaces_the_collapse_and_the_pre_collapse_row_count, ::test_build_preview_with_no_collapse_reports_zero_not_a_missing_key, ::test_only_the_deduped_file_reaches_the_wire (recorded multipart body bytes, mirrors 34-RESEARCH.md Pitfall 3)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py, test_preingest_preview.py, test_preingest_match.py, test_mandatory_report_call_sites.py, test_plugin_manifest.py — all unchanged/pass"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-73-21 scope guard: enrich-before-ingest's row_id minting and total_row_ids accounting are unaffected by a duplicate CSV; dispatch.py and extraction.py are unmodified"
    requirement: F-A5
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py::test_enrich_before_ingest_row_id_minting_is_unaffected_by_a_duplicate_csv, ::test_preingest_never_imports_csv_dedupe"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-16
status: complete
---

# Phase 73 Plan 04: CSV dedupe collapse for contact-upload (F-A5) Summary

**A new `csv_dedupe.py` collapses exact, casefolded/trimmed duplicate CSV rows before the plain `contact-upload` send — first occurrence wins byte-for-byte, losers are named with the outcome `duplicate_in_csv`, and `preview.py` surfaces the collapse before any send — closing the trigger for F-A6's HubSpot Create 409.**

## Performance
- **Duration:** 45 min
- **Started:** 2026-09-15
- **Completed:** 2026-09-16
- **Tasks:** 2/2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Attempt 2's Stage A CSV carried the same person three times (rows 37/38 repeating row
  3, one a case variant); `csv_dedupe.py` now collapses that shape deterministically
  before the send ever reaches HubSpot.
- The collapse reuses `extraction.py`'s own identity-group primitives
  (`identity_groups`, `_first_satisfied_key`, `_group_presence`, `_casefold_trim`) but
  deliberately avoids `extraction.dedupe()`/`_merge_cluster` — the research flagged
  reusing that pair unmodified as the single highest-risk misread of this plan, since it
  merges fields and drops conflicts rather than keeping the first row verbatim.
- `preview.py` now surfaces the collapse (`collapsed_rows`, `pre_collapse_row_count`) so
  the operator can reconcile the row count they expected in their own file against the
  count actually being sent — before any arming.
- `contact-upload/SKILL.md` gained step 2c, running the collapse unconditionally (no
  operator review needed, since the match is always exact) and forwarding the deduped
  path through preview and dispatch, exactly as `split_path`/`corrected_path` already do.
- `enrich-before-ingest`'s row_id minting and `total_row_ids` accounting are proven
  unaffected — the collapse is scoped to the plain `contact-upload` lane only (D-73-21).

## Task Commits
1. **Task 1: first-wins CSV collapse with a duplicate_in_csv outcome** - `024da7c0` (feat)
2. **Task 2: show the collapse in preview and send the corrected file (contact-upload only)** - `9a1d80b2` (feat)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified
- `operator-claude-plugin/scripts/csv_dedupe.py` - propose/apply first-wins collapse on `extraction.py`'s identity-group rule
- `operator-claude-plugin/tests/test_csv_dedupe.py` - 18 tests covering every D-73-03/D-73-04 behavior, preview surfacing, wire-body proof, and the D-73-21 scope guard
- `operator-claude-plugin/scripts/preview.py` - `collapse_block()`, `build_preview(..., collapsed=None)`, CLI `--collapsed <file.json>`
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - new step 2c; step 3's preview invocation and "Always show" bullets updated

## Decisions Made
See `key-decisions` in frontmatter — row numbering convention, canonical-header mapping via `preview.label_headers` (not `preingest.rows_from_table`, to avoid coupling to the enrich-before-ingest-specific module), the sidecar-JSON hand-off between `csv_dedupe.py` and `preview.py`, and step 2c's unconditional (no-ask) placement in the SKILL.md chain.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `apply_dedupe()` test calls wrote into the real plugin scratch directory**
- **Found during:** Task 2, running the full `tests/ operator-claude-plugin/tests/` suite
- **Issue:** Several `test_csv_dedupe.py` tests called `apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)` without an explicit `scratch_dir`, so `csv_dedupe.py`'s default `SCRATCH_DIR` (the real `operator-claude-plugin/scratch/`) received `deduped-contacts.csv`/`dedupe-report-contacts.json` — caught by the pre-existing `test_header_suggest.py::test_git_status_short_shows_no_writes_to_the_real_plugin_scratch_directory` guard, not by anything in this plan's own new tests.
- **Fix:** Every `apply_dedupe(...)` call in the test file now passes `scratch_dir=tmp_path / "scratch"`, matching `name_split.py`'s/`header_suggest.py`'s own established test discipline. The two stray files were deleted before committing.
- **Files modified:** `operator-claude-plugin/tests/test_csv_dedupe.py`
- **Verification:** full suite re-run clean (4979 passed / 154 skipped), `git status --short operator-claude-plugin/scratch/` empty
- **Commit:** `9a1d80b2`

**Total deviations:** 1
**Impact on plan:** None — caught before the Task 2 commit; no change to the module's own behavior or public contract.

## Issues Encountered
None.

## TDD Gate Compliance

Task 1 (`tdd="true"`) followed RED then GREEN, but both landed in a single `feat(73-04)`
commit rather than a separate `test(73-04):` RED commit followed by `feat(73-04):` GREEN —
no `tdd-red-evidence` record was persisted. RED was observed and is quoted here for the
record, matching the plan's own acceptance criterion ("observed RED before the module
existed"):

```
$ .venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_dedupe.py
ImportError while importing test module '.../operator-claude-plugin/tests/test_csv_dedupe.py'.
...
E   ModuleNotFoundError: No module named 'csv_dedupe'
1 error in 0.09s
```

GREEN followed immediately after `csv_dedupe.py` was written: 11/11 passed (later 18/18
after Task 2's additional tests), all in commit `024da7c0`. The behavior (RED-before-GREEN)
was honored; the two-commit gate mechanics were not — recorded here rather than silently
passed over.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- F-A5 is closed: the known within-batch duplicate trigger for F-A6's HubSpot Create 409
  can no longer recur on the plain `contact-upload` lane.
- Plan-level verification passed in full: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` → 4979 passed / 154 skipped (baseline 4961/154 + 18 new); `node --test tests/n8n/*.test.mjs` → 1195 passed / 0 failed (unchanged, this plan touches no graph); `.venv/bin/python scripts/build_cloud_workflows.py` → zero `n8n/` diff.
- No deploy, no bounce, no arming performed or required by this plan — it is plugin-only.
- Ready for the operator's end-of-phase deploy + bounce + reset + attempt-3 run once all of phase 73's plans land, per D-73-18.

---
*Phase: 73-ga-fix-list-from-stress-attempt-2*
*Completed: 2026-09-16*

## Self-Check: PASSED
- All key-files exist: `operator-claude-plugin/scripts/csv_dedupe.py`, `operator-claude-plugin/tests/test_csv_dedupe.py`, `operator-claude-plugin/scripts/preview.py`, `operator-claude-plugin/skills/contact-upload/SKILL.md`
- Both task commits found in `git log`: `024da7c0`, `9a1d80b2`
- Plan-level verification re-run clean: pytest 4979 passed/154 skipped; node 1195 passed/0 failed; `build_cloud_workflows.py` zero `n8n/` diff
- `plan_head_before: 970fea7f`, `commits: 2` (measured via `git rev-list --count 970fea7f..HEAD`)
