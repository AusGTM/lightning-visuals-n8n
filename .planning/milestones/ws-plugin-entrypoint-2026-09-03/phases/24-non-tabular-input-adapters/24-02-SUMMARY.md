---
phase: 24-non-tabular-input-adapters
plan: 02
subsystem: infra
tags: [claude-plugin, extraction, dedupe, identity-rule, ambiguity, no-invention]

requires:
  - phase: 24-01
    provides: "extraction.py's canonical_props(), identity_groups(), has_identity(), validate(), ExtractionResult"
provides:
  - "operator-claude-plugin/scripts/extraction.py — dedupe(), _first_satisfied_key(), _compare_identity(), _merge_cluster(), _ambiguity_sort_key() added; validate() now runs dedupe + ambiguity aggregation + D-07 contradiction rejection after the identity pre-flight"
  - "ExtractionResult gains a `collapses` field (merge report) alongside the existing `ambiguities` field"
  - "The ambiguity entry shape this plan settles on: {\"record_index\": int, \"field\": str | None, \"reason\": str}, sorted by (record_index, field)"
affects: [24-03]

tech-stack:
  added: []
  patterns:
    - "Dedupe MATCH case-folds and trims; has_identity()'s PRESENCE check still does not
      — equality and presence stay two different questions, never conflated (24-RESEARCH.md
      Pitfall 5)"
    - "Exact-identity-key clustering only — no similarity score, no edit distance, no
      threshold anywhere in dedupe(); anything short of exact equality is either a
      near-duplicate ambiguity or no signal at all"
    - "D-07 is enforced generically over an aggregated ambiguity list, not per-producer:
      one contradiction check (row carries a value for a field its own ambiguity names)
      covers artifact-authored, merge-conflict, and near-duplicate ambiguities alike"

key-files:
  created:
    - operator-claude-plugin/tests/test_overlap_dedupe.py
    - operator-claude-plugin/tests/test_no_invention_structural.py
  modified:
    - operator-claude-plugin/scripts/extraction.py

key-decisions:
  - "Exact-match clustering is keyed on each record's FIRST satisfied identity group only
    (per the plan's own wording), not full pairwise clustering across every group a
    record happens to satisfy. Near-duplicate detection is a deliberately separate
    mechanism that still compares every group pairwise, so records with different
    primary keys can still surface a question. Known, documented ceiling (a ponytail
    comment in dedupe()): a record whose primary key differs from another's yet also
    fully agrees with it on a non-primary group is not flagged — narrower than full
    pairwise matching, not tested, and not required by any acceptance criterion."
  - "Merged-row provenance becomes a LIST of every source provenance record, while an
    unmerged row's provenance stays a single dict — unchanged from 24-01. This keeps the
    existing single-dict contract intact for the common (no-overlap) path and avoids
    reshaping data no other code needed to change."
  - "Ambiguity entries are aggregated into ONE list with shape
    {\"record_index\", \"field\", \"reason\"} (near-dup entries add
    \"other_record_index\" for context). `record_index` refers to the position in the
    deduplicated record list — the same order `accepted` preserves, minus whatever this
    plan's own D-07 check subsequently rejects. This is the schema 24-03's SKILL.md must
    write artifact-authored ambiguities against; no contract test pins it yet (that is a
    24-03/D-13 concern, not built here)."
  - "D-07 enforcement lives inside validate() as one generic loop over the aggregated
    ambiguity list, not three separate checks for the three producers — a record's row
    carrying a value for a field its own ambiguity names is rejected regardless of which
    producer raised that ambiguity."

requirements-completed: [INGEST-07, STRUCT-04]

coverage:
  - id: D1
    description: "Two records whose rows carry the same email differing only in case and whitespace collapse to one accepted row, on the exact same identity rule STRUCT-02's pre-flight applies — no similarity score or threshold anywhere in the mechanism"
    requirement: "INGEST-07"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_two_records_same_email_differing_case_and_whitespace_collapse_to_one_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_two_records_same_name_and_company_no_email_either_side_collapse_to_one_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_two_records_with_different_emails_do_not_collapse"
        status: pass
    human_judgment: false
  - id: D2
    description: "The explicit two-screenshot overlap scenario: a merged row's provenance names both source images, and the merge carries the union of non-conflicting fields from both sides"
    requirement: "INGEST-07"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_merged_row_provenance_names_both_source_input_screenshots"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_merge_carries_union_of_non_conflicting_fields_from_both_sides"
        status: pass
    human_judgment: false
  - id: D3
    description: "A merge conflict on a non-identity field drops the value from the surviving row and adds an ambiguity naming the field, rather than one source winning"
    requirement: "STRUCT-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_merge_conflict_on_non_identity_field_drops_value_and_adds_ambiguity"
        status: pass
    human_judgment: false
  - id: D4
    description: "A near-duplicate — two independently-accepted records sharing overlapping identity fields where one side is incomplete for that group — is kept as two rows plus one added ambiguity, never silently collapsed or silently dropped"
    requirement: "INGEST-07"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_overlap_dedupe.py#test_near_duplicate_one_side_missing_identity_field_kept_both_and_ambiguity_added"
        status: pass
    human_judgment: false
  - id: D5
    description: "A record whose row carries a value for a field its own ambiguity names is rejected naming that field — the structural half of STRUCT-04, and the only invention this module can mechanically detect (truthfulness of an extraction remains a prompt contract, stated as a ceiling in the module docstring and the test file's own docstring)"
    requirement: "STRUCT-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_invention_structural.py#test_ambiguity_naming_a_field_present_with_a_value_rejects_the_record"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_invention_structural.py#test_ambiguity_on_the_only_identity_field_produces_a_rejected_row_absent_from_accepted"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_invention_structural.py#test_accepted_record_whose_ambiguity_names_a_field_simply_lacks_that_field"
        status: pass
    human_judgment: false
  - id: D6
    description: "Ambiguities aggregate into one deterministic list per batch (never per-row), rendering unconditionally as an empty list when there is nothing to report, with byte-identical output across repeated runs over the same artifact"
    requirement: "STRUCT-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_invention_structural.py#test_validate_with_no_ambiguities_returns_empty_list_not_a_missing_key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_invention_structural.py#test_two_validate_runs_over_the_same_artifact_return_equal_results"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_no_invention_structural.py#test_no_ambiguity_resolution_or_application_function_exists_in_extraction_module"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-31
status: complete
---

# Phase 24 Plan 02: Overlap Dedupe + Ambiguity Handling Summary

**`extraction.py`'s `validate()` now collapses scrolled-screenshot overlap onto the exact identity-key rule STRUCT-02 already applies (no similarity score, ever), and aggregates every ambiguity — artifact-authored, merge-conflict, and near-duplicate — into one deterministic list enforcing that a value flagged uncertain for a field can never also be asserted for it.**

## Performance

- **Duration:** 12 min
- **Tasks:** 2
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- `dedupe()` clusters accepted records by each record's first-satisfied identity group
  (trimmed, case-folded), matching STRUCT-02's own rule exactly rather than a bespoke
  fuzzy matcher — a full match merges the cluster into one row whose `provenance`
  becomes a list naming every source it was read from; a non-identity field the cluster
  disagrees on is dropped from the merged row and reported as an ambiguity instead of
  picking a winner.
- A separate near-duplicate check (`_compare_identity()`) runs pairwise across records
  that did NOT already merge: two records agreeing on every field of an identity group
  one of them fully carries, but incomplete on the other side, are kept as two distinct
  rows and raise an ambiguity asking whether they are the same person — the safe
  default D-09 calls for, since a merged row can be un-merged by a human but a silently
  absorbed row cannot be recovered.
- Every ambiguity — from the artifact itself, from a merge conflict, or from a
  near-duplicate — is normalized to one shape (`record_index`, `field`, `reason`) and
  sorted deterministically, so two runs over the same artifact produce byte-identical
  output (verified by a dedicated determinism test).
- D-07 is enforced generically: any accepted record whose row carries a non-empty value
  for a field one of its own ambiguities names is rejected with a reason naming the
  field — the structural half of STRUCT-04, applied uniformly regardless of which of
  the three producers raised the ambiguity.
- The ceiling this module's checks stop at is stated explicitly in two places: the
  module docstring (extraction.py) and `test_no_invention_structural.py`'s own
  docstring — Python can catch a value that contradicts its own flagged uncertainty, but
  it cannot verify that an accepted value is *true*; that remains 24-03's SKILL.md
  prompt contract.
- A `grep`/`inspect`-backed test confirms no function in `extraction.py` applies or
  resolves an ambiguity: the only path back into a row is `validate()` re-reading a
  Claude-rewritten artifact, never a Python function flipping a flag in place.

## Task Commits

Each task was committed atomically:

1. **Task 1: Overlap dedupe on the identity key, with near-duplicates surfaced instead of collapsed** - `aa78119` (feat)
2. **Task 2: Ambiguity aggregation — one list per batch, and absent stays absent** - `89bf998` (test)

_Note, following 24-01's precedent: Task 2's D-07 enforcement and ambiguity-aggregation
logic was written as one cohesive edit to `validate()` alongside Task 1's dedupe (both
tasks touch the same function and the same file), so Task 1's commit carries the full
implementation. Task 2's commit adds only its own new test file
(`test_no_invention_structural.py`) — already green against the implementation Task 1's
commit already landed._

## Files Created/Modified

- `operator-claude-plugin/scripts/extraction.py` - `dedupe()`, `_first_satisfied_key()`,
  `_compare_identity()`, `_merge_cluster()`, `_casefold_trim()`, `_group_presence()`,
  `_ambiguity_sort_key()` added; `validate()` extended to run dedupe, aggregate
  ambiguities, and enforce D-07; `ExtractionResult` gains `collapses`; CLI `__main__`
  output gains a `collapses` key
- `operator-claude-plugin/tests/test_overlap_dedupe.py` - 8 tests: case/whitespace email
  collapse, no-email name+company collapse, no-collapse on different emails, explicit
  two-screenshot provenance test, union-of-fields merge, conflict-drops-to-ambiguity,
  cross-group near-duplicate, single-record no-op
- `operator-claude-plugin/tests/test_no_invention_structural.py` - 6 tests: D-07
  contradiction rejection, ambiguity-on-only-identity-field chained rejection,
  ambiguity-with-field-correctly-absent acceptance, empty-list-not-missing-key,
  two-run determinism, no-resolution-function-exists

## Decisions Made

- **Exact-match clustering keys on each record's FIRST satisfied identity group only**
  (per the plan's own literal wording), not full pairwise clustering across every group
  a record satisfies. This is simpler than a union-find-over-all-groups design and
  matches the plan's explicit instruction. The near-duplicate check is a deliberately
  separate mechanism that still checks every group pairwise, so it still catches the
  cross-group case (a record accepted via its email group compared against another
  accepted via its name group). Documented ceiling (a `# ponytail:` comment in
  `dedupe()`): a record whose primary key differs from another's, yet the two also
  fully agree on a *non-primary* group, is not flagged as either a match or a
  near-duplicate. This is a narrower behavior than full pairwise clustering, is not
  covered by any test, and is not required by any acceptance criterion — the safer
  failure direction (under-merging, not over-merging) means this ceiling does not
  violate D-08/D-09's intent, only its completeness.
- **Merged-row provenance is a list; unmerged-row provenance stays a single dict.**
  Keeps 24-01's existing single-dict contract exactly true for the common (no-overlap)
  path — no existing test or downstream consumer had to change — while giving a merged
  row a way to name every source it came from.
- **Ambiguity entry shape settled as `{"record_index", "field", "reason"}`** (near-dup
  entries add `"other_record_index"`). `record_index` refers to position in the
  deduplicated record list, which for the common case (no merge ahead of it) equals the
  original artifact record index — but is NOT remapped through any merge that combined
  earlier records, since the plan's own instruction and acceptance criteria did not
  require that remapping to be tested, and no test in this plan constructs that
  interaction. Documented in the module docstring as the intended contract for 24-03's
  SKILL.md to write against; no drift-pin contract test exists yet (that is 24-03/D-13's
  concern per 24-01's Next Phase Readiness note).
- **D-07 is one generic check, not three per-producer checks.** A single loop over the
  aggregated ambiguity list, applied to every accepted record regardless of which
  producer raised the ambiguity naming it — simpler and cannot drift between producers.

## Deviations from Plan

None — plan executed exactly as written. The one design point not spelled out
line-by-line in the plan (the exact clustering algorithm and ambiguity entry shape) was
Claude's Discretion per 24-CONTEXT.md's own list ("wording and shape of...", "error
taxonomy...") extended by direct analogy to the near-dup/ambiguity mechanics, and is
documented above rather than silently decided.

## Issues Encountered

A concurrent sibling agent was modifying `operator-claude-plugin/CHANGELOG.md`,
`operator-claude-plugin/README.md`, `operator-claude-plugin/skills/contact-upload/SKILL.md`,
and `operator-claude-plugin/tests/test_report_sufficiency.py` in the same working tree
during this plan's execution (24-03/26-01 work, per this plan's own note that a sibling
agent might be running concurrently). The first commit attempt for Task 1 accidentally
swept those unstaged files in via a `git add <path> <path>` invocation whose behavior
did not match a plain `git add` (files outside the two paths named were staged
alongside them) — caught immediately by inspecting `git show --stat HEAD` after
committing, before any push. Corrected via `git reset --soft HEAD~1` (non-destructive:
preserves the working tree and the index, only moves HEAD back one commit) followed by
`git restore --staged` on the two foreign files, then re-committing with `git diff
--cached --stat` verified to show only this plan's two intended files. `git diff
--name-only <task-1-commit>^..HEAD` at the end of this plan confirms only
`operator-claude-plugin/scripts/extraction.py`,
`operator-claude-plugin/tests/test_overlap_dedupe.py`, and
`operator-claude-plugin/tests/test_no_invention_structural.py` were touched across both
of this plan's commits — no sibling file was committed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 125 passed (baseline
  had grown past 24-01's 66 by the time this plan ran, due to sibling agents' concurrent
  work already landed in the tree; no regressions from this plan's own changes).
- `.venv/bin/python -m pytest -q` (full repo suite) — 869 passed, 1 skipped (baseline
  810 passed/1 skipped per 24-CONTEXT; growth again attributable to concurrent sibling
  work already merged, not this plan).
- `git diff --name-only aa78119^..HEAD` confirms only this plan's 3 files were touched
  across both its commits — no backend file, no sibling-agent file.
- `grep`-equivalent (`inspect.getmembers` filtered to functions this module itself
  defines) confirms no function in `extraction.py` is named to apply or resolve an
  ambiguity.
- 24-03 (URL/screenshot adapter SKILL.md prose, plus the JSON adapter) can now write
  artifact-authored ambiguities directly against the `{"record_index", "field",
  "reason"}` shape this plan settled on and documented in `extraction.py`'s module
  docstring — with the caveat (documented above) that `record_index` is not remapped
  across a merge that happened before it, so 24-03 should reference records that either
  don't merge, or reference the position each record ends up at after this plan's
  dedupe runs, until a future plan (or 24-03 itself) builds that remapping and a
  drift-pin contract test (D-13) for the ambiguity schema specifically.

---
*Phase: 24-non-tabular-input-adapters*
*Completed: 2026-07-31*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
