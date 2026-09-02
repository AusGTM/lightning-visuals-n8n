---
phase: 37-enrich-before-ingest
plan: 04
subsystem: preingest
tags: [propose-then-confirm, join-by-id, non-clobber-merge, column-mapping, tdd]

requires:
  - phase: 37-enrich-before-ingest
    plan: 03
    provides: "preingest.build_rows_spec, classify_matches(rows, response) — the four-bucket classification apply_match_decisions edits"
provides:
  - "preingest.apply_match_decisions(classified, resolved) — all-or-nothing, refuses an unproposed row or a foreign candidate id"
  - "preingest.merge_enriched(rows, responses) — joins by row_id only, refuses a duplicate, ignores an unknown id, fill-not-overwrite"
  - "preingest.rows_from_table(path, mapping_path=None) — canonical rows via preview.label_headers' exact alias lookup only"
affects: [37-05, 37-06]

actuals:
  tokens: 3593
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Validation-pass-then-apply-pass for all-or-nothing decision sets — every entry checked before any is applied, mirroring header_suggest.apply_confirmed_corrections' guard-before-open rule in a pure-function (no file, still no half-applied set) form"
    - "row_id-indexed join with duplicate refusal at index-build time, walking the caller's own canonical list (not the response) so a missing item is detectable"
    - "Fill-not-overwrite merge: a non-empty source value is never replaced, a differing provider value becomes a reported conflict"

key-files:
  created:
    - operator-claude-plugin/tests/test_preingest_merge.py
  modified:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preingest_match.py

key-decisions:
  - "apply_match_decisions reuses classify_matches' existing top-level keys (auto_matched/proposed/unmatched/unchecked/unknown_response_row_ids) rather than adding a new 'confirmed' bucket — a confirmed row moves into auto_matched carrying hs_object_id plus confirmed:True. This is what makes `apply_match_decisions(classified, {}) == classified` true by construction: no new key means the empty-resolved case is a byte-for-byte pass-through, not an approximation."
  - "DECLINE_MATCH is a plain sentinel string ('decline'), not None — a resolved entry must say something to be a decision, and None reads as 'operator hasn't said' rather than 'operator declined'. Real HubSpot candidate ids are numeric strings, so no collision risk."
  - "merge_enriched returns a MergeResult dataclass (rows + 4 report fields), mirroring MatchOutcome's payload-plus-report shape from 37-03 rather than inventing a third convention or reusing extraction.dedupe's bare-tuple return — the extra named fields (dropped_property_keys, conflicts, unenriched_row_ids) needed labels a tuple position can't carry legibly."
  - "rows_from_table refuses (raises) rather than degrades when the mapping file is unavailable, even though preview.label_headers itself degrades gracefully (available: False) for its own display-only callers — this function's rows feed a real upload path, so an unmapped-headers silent pass-through would surface as a confusing write_dispatch_csv error far downstream instead of a clear one here."

requirements-completed: [INGEST-02, STRUCT-01, STRUCT-04]

coverage:
  - id: D1
    description: "apply_match_decisions validates every entry in `resolved` in a single pass before applying any of them; an unproposed row id or a candidate id outside that row's own candidates raises and nothing is applied. Confirming moves a row to auto_matched with the chosen hs_object_id; declining moves it to unmatched; an unresolved row stays proposed."
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_match.py (37-04 Task 1 section, 9 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "merge_enriched indexes responses by row_id before walking any row, refusing a duplicate id at index-build time; walks the rows so a missing response is detectable and reported; filters properties to extraction.canonical_props(), reporting dropped keys; never overwrites a non-empty source value, reporting a differing provider value as a conflict instead."
    requirement: INGEST-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py (Task 2 section, 12 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "rows_from_table reads a CSV/XLSX via tabular.read_table and maps headers through preview.label_headers' exact alias lookup only — no fuzzy matching, read-only end to end, refuses when the mapping file cannot be resolved, and names every dropped header in the result."
    requirement: STRUCT-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_merge.py (Task 3 section, 7 tests)"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 04: preingest.py — Decisions Applied, Responses Merged, Tables Read Summary

**Proposals become decisions and responses become rows, both joined strictly by id and both refusing rather than guessing — `apply_match_decisions`, `merge_enriched`, `rows_from_table`.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-05T09:29:55Z
- **Tasks:** 3/3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- `preingest.apply_match_decisions(classified, resolved)` validates every entry in
  `resolved` in one pass — an unproposed row id or a candidate id outside that row's
  own proposed candidates raises `MatchDecisionError` naming the offending value(s) —
  BEFORE any of them is applied, so a decision set with one invalid entry applies
  nothing. A confirmed row moves into `auto_matched` carrying the chosen candidate's
  `hs_object_id` (plus `confirmed: True`); a declined row (`DECLINE_MATCH` sentinel)
  moves into `unmatched`; an unresolved row stays in `proposed`, never defaulted.
  `apply_match_decisions(classified, {})` returns a value equal to `classified` by
  construction — no valid entries touch the buckets and no new top-level key is
  introduced.
- `preingest.merge_enriched(rows, responses)` joins by `row_id` only. Responses are
  indexed first, refusing a duplicate id before a single row is walked (nothing is
  merged on refusal). Walking the ROWS (not the responses) makes a row with no
  matching response detectable (`unenriched_row_ids`) and distinguishable from a row
  whose response carried an empty `properties` map. Each response's `properties` is
  filtered to `extraction.canonical_props()`, reporting a dropped key by row and
  name. Fill-not-overwrite: a non-empty source value is never replaced — a differing
  provider value is recorded in `conflicts` instead of applied. Returns a
  `MergeResult` dataclass; input rows are never mutated.
- `preingest.rows_from_table(path, mapping_path=None)` reads a CSV/XLSX via
  `tabular.read_table` (no second parser) and maps headers through
  `preview.label_headers`'s EXACT alias lookup only — no fuzzy matching added at this
  layer. A header the alias table does not recognise is dropped from every row and
  named in `dropped_headers`. Refuses with `RowsFromTableError` when the mapping file
  cannot be resolved, rather than silently degrading to unmapped rows. Read-only:
  source file bytes are identical before and after the call.

## Task Commits

1. **Task 1: apply_match_decisions — all-or-nothing, never a foreign candidate** - `7566d60` (feat)
2. **Task 2: merge_enriched — join by id, refuse a duplicate, ignore an unknown** - `2bf411a` (feat)
3. **Task 3: rows_from_table — one mapping authority, read-only** - `b44d6e2` (feat)

_No separate plan-metadata commit — this SUMMARY and STATE.md updates are committed
together per `final_commit`._

## Files Created/Modified

- `operator-claude-plugin/scripts/preingest.py` — added `MatchDecisionError`,
  `DECLINE_MATCH`, `apply_match_decisions`; `MergeError`, `MergeResult`, `_present`,
  `merge_enriched`; `RowsFromTableError`, `rows_from_table`
- `operator-claude-plugin/tests/test_preingest_match.py` — 9 new tests, "37-04 Task 1"
  section
- `operator-claude-plugin/tests/test_preingest_merge.py` — new file, 19 tests across
  Task 2 (merge_enriched) and Task 3 (rows_from_table)

## Decisions Made

- **`apply_match_decisions` reuses `classify_matches`' own bucket keys rather than
  adding a `confirmed_matched` bucket.** A confirmed row moves into `auto_matched`
  carrying `hs_object_id` and `confirmed: True`, so the returned shape is always the
  same five keys `classify_matches` produces. This is what makes
  `apply_match_decisions(classified, {}) == classified` hold structurally: the
  empty-resolved case introduces no new key and mutates no bucket.
- **`DECLINE_MATCH` is a sentinel string, not `None`.** A resolved entry must say
  something explicit to count as a decision; `None` would read as "no decision made"
  (the same state as the row's absence from `resolved`), collapsing two different
  meanings into one value.
- **`merge_enriched` returns a `MergeResult` dataclass**, mirroring `MatchOutcome`'s
  payload-plus-report shape from 37-03 (`rows` plus four named report fields) rather
  than `extraction.dedupe`'s bare-tuple return — the four report axes
  (`unknown_response_row_ids`, `dropped_property_keys`, `conflicts`,
  `unenriched_row_ids`) need labels a tuple position cannot carry legibly.
- **`rows_from_table` refuses, never degrades, on an unresolved mapping file** —
  stricter than `preview.label_headers`'s own graceful `available: False` for its
  display-only callers, because these rows feed a real upload path and a silent
  unmapped pass-through would surface as a confusing error far downstream at
  `write_dispatch_csv` instead of a clear one here.

## Deviations from Plan

None — plan executed exactly as written. The plan's fixture assumption of 4 data
rows in `clean-uat-contacts.csv` was corrected in the test (the file has 3 data rows
plus its header); this is a test-authoring correction against an existing fixture,
not a deviation from any plan-specified behavior.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 1 — all-or-nothing:**
Moving the candidate-membership check into the apply loop (mutating
`classified["auto_matched"]` in place instead of building a fresh copy) made
`test_all_or_nothing_one_invalid_entry_means_no_valid_entry_takes_effect` fail:
```
AssertionError: assert 1 == 0
 +  where 1 = len([{'row_id': 'row-1', ..., 'hs_object_id': '111', 'confirmed': True}])
```
The valid entry (`row-1`) leaked into the caller's own `classified["auto_matched"]`
before the second, invalid entry raised — exactly the half-applied set the
guard-before-open rule exists to prevent. The two raise-only tests
(`test_a_decision_naming_a_row_that_was_never_proposed_raises_naming_the_row`,
`test_a_decision_naming_a_foreign_candidate_id_raises_naming_row_and_candidate`)
still passed under the broken version, confirming the all-or-nothing test is the one
carrying this specific guarantee.

**Task 2 — positional zip:**
Replacing the `row_id` index with a positional `responses[i]` lookup:
- `test_shuffled_response_order_still_lands_on_the_right_rows` failed —
  `AssertionError: assert 'third@x.com' == 'first@x.com'` — row-1 (`rows[0]`) received
  row-3's (`rows[2]`) email under positional alignment.
- `test_removing_the_middle_response_item_does_not_shift_the_trailing_rows` (added
  specifically to exercise a middle-item removal, since the plan-suggested
  "one-response-item-removed" case needed a non-trailing gap to expose positional
  drift) failed — `AssertionError: assert 'email' not in {..., 'row_id': 'row-2', ...}`
  — `rows[1]` silently picked up `rows[2]`'s response once `rows[1]`'s own item was
  missing.

Removing the duplicate-`row_id` refusal (last-one-wins instead):
`test_two_response_items_sharing_a_row_id_raises_and_merges_nothing` failed —
`Failed: DID NOT RAISE MergeError`.

**Task 3 — fuzzy header matching:**
Swapping the exact `aliases.get(...)` lookup in `preview.label_headers` for a
`difflib.get_close_matches` fallback made
`test_a_header_merely_similar_to_an_alias_does_not_map` fail —
`AssertionError: assert 'Ph.' in []` — `"Ph."` (a real column in
`22-messy-headers.csv`) mapped onto `phone` under the fuzzy matcher despite not being
an exact alias, exactly the smuggled-in second mapping authority this task's design
forbids.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `apply_match_decisions`, `merge_enriched`, and `rows_from_table` are the exact
  primitives 37-05's `render_enriched_preview` is specified to build on — no further
  match/merge/table-read work is needed before that plan starts.
- Suite counts after this plan: `operator-claude-plugin/tests/ -q` → 1151 passed, 5
  skipped (baseline post-37-03: 1123/5); repo-root `.venv/bin/python -m pytest -q` →
  2066 passed, 6 skipped (baseline 2038/6); `node --test tests/n8n/*.test.mjs` → 621
  pass, unchanged; arming grep → 0 for every file; `operator-claude-plugin/scratch`
  clean.
- No blockers for 37-05.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 4 files created/modified by this plan verified present on disk; all 3 commit
hashes (`7566d60`, `2bf411a`, `b44d6e2`) verified present in `git log --oneline --all`.
