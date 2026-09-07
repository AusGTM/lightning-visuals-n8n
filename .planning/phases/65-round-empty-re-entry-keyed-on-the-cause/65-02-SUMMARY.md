---
phase: 65-round-empty-re-entry-keyed-on-the-cause
plan: 02
subsystem: operator-plugin
tags: [preingest, merge_enriched, field-policy, python, pytest, RICH-04]

# Dependency graph
requires:
  - phase: 65-01 (round-empty re-entry, keyed on the cause)
    provides: no functional dependency (depends_on is declared for phase-plan
      ordering only) -- this plan touches an entirely disjoint set of files from
      65-01's round_outcome work
provides:
  - preingest.promotable_contact_props()/resolve_policy_path() -- the one rule for
    reading config/field_policy.yaml's `contacts:` promotable keys, mirroring
    preview.resolve_mapping_path's three-step resolution order
  - preingest.strip_enrichment_extras() -- the dispatch-boundary strip that keeps
    field-policy-widened keys out of the dispatch CSV
  - merge_enriched's allowlist widened to the UNION of extraction.canonical_props()
    and promotable_contact_props(), so nine previously-dropped policy-promotable
    contact keys now survive onto a blank CREATE row
  - operator-claude-plugin/config/field_policy.yaml -- the plugin's own shipped copy
    of config/field_policy.yaml, pinned byte-identical by test
affects: [69-decline-store]

# Actuals (#2632)
actuals:
  tokens: 11444
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Widening-only client read: promotable_contact_props() mirrors review_queue.py's
      D-06/D-07 display-only discipline for its own field_policy.yaml read -- it may
      add a key to an allowlist and may never refuse, filter or reorder a write the
      backend would accept, so an absent/malformed policy degrades to '[]' (a smaller,
      stricter allowlist) rather than raising, the opposite direction from
      extraction._load_mapping's hard error on an unresolvable column mapping"
    - "Named, closed strip at the dispatch boundary (strip_enrichment_extras mirrors
      extraction.strip_row_id's shape exactly): a widened key rides every upstream
      stage untouched and is removed only at the one boundary that cannot accept it,
      never by a blanket 'drop anything unknown' filter"
    - "Plugin-shipped config copy pinned byte-identical to its repo source by test
      (same shape column_mapping.yaml already uses) -- required because the
      marketplace ships operator-claude-plugin/ alone, so a repo-root-only lookup
      resolves to nothing in an installed plugin tree"

key-files:
  created:
    - operator-claude-plugin/config/field_policy.yaml
    - .planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md
  modified:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "The plugin now ships its own operator-claude-plugin/config/field_policy.yaml
    copy, byte-identical to config/field_policy.yaml, pinned by test. Without it the
    whole RICH-04 fix is INERT in an installed plugin tree: the marketplace's
    .claude-plugin/marketplace.json ships operator-claude-plugin/ alone, so an
    operator's installed tree has no repo root beside it, and a repo-root-only
    lookup for the policy would resolve to nothing."
  - "The widened keys (seniority, lv_linkedin_url, mobilephone, city, state, country,
    hs_state_code, hs_country_region_code, lv_persona_group) are stripped at the
    dispatch-CSV boundary by strip_enrichment_extras and therefore do NOT reach
    HubSpot through that CSV -- the deployed ingest lane's own column map has no
    header for any of them. They serve the merge report, the held-row path, and
    Phase 69's future decline-store entries."
  - "RICH-04 is closed as an audit plus the seniority half only. The richer-jobtitle
    half of the live evidence (merge_enriched's blanket fill-not-overwrite ignoring
    jobtitle's own field_policy.yaml protect_if_current_present: false) is
    deliberately deferred to a named pending todo carrying no resolves_phase key --
    per the plan's own prohibition, no per-field protect_if_current_present branch
    was added to merge_enriched in this phase."
  - "[Plan finding correction] 65-02-PLAN.md's Finding 8 and Task 2's acceptance
    criterion claimed a widened key rides through held_queue.build_entry
    'untouched'. Verified empirically (direct interpreter check) that this is
    FALSE for held_queue specifically: held_queue.ROW_FIELD_ALLOWLIST (row_id +
    enrichment.MATCH_LOOKUP_KEYS) is a pre-existing, deliberate allowlist
    (module docstring, REVIEW-A7: 'only the identity keys and the columns the
    envelope projects, never whatever else happened to be in the operator's
    spreadsheet') that strips a widened key before it reaches the stored entry.
    Finding 8's grep pattern (canonical_props|set\\(row|row\\.keys) missed this
    because ROW_FIELD_ALLOWLIST is a named tuple, not one of those three literal
    shapes. remainder_queue.build_entry DOES carry a widened key through untouched
    (its spec is stored verbatim, only a forbidden-name scan runs). The test file
    asserts the TRUE behaviour for both: held_queue.build_entry does not raise and
    correctly omits the widened key; remainder_queue.build_entry does not raise and
    correctly carries it. No production code was changed for either -- held_queue's
    allowlist is out of scope to widen here (not in files_modified, and widening a
    security allowlist would be a Rule 4 architectural change)."
  - "Task 2 (tdd=\"true\") required no production code change: every behaviour its
    tests pin was already implemented by Task 1's GREEN commit. Each new test was
    run before being committed and passed immediately (0 failures) -- confirmed via
    tdd.md's own 'test doesn't fail in RED: investigate' guidance that this reflects
    the feature already existing (by design, since Task 1 shipped it), not a masked
    gap. A single test(65-02) commit was made for Task 2, with no paired feat
    commit, matching the test-only pattern 65-01 Task 3 established."

requirements-completed: [RICH-04]

coverage:
  - id: D1
    description: "merge_enriched's allowlist widens to the union of
      extraction.canonical_props() and field_policy.yaml's promotable contact keys,
      so nine previously-dropped keys (seniority, lv_linkedin_url, mobilephone, and
      five location fields, lv_persona_group) survive onto a blank CREATE row"
    requirement: RICH-04
    verification:
      - kind: unit
        ref: "test_preingest_merge.py::test_a_policy_promotable_key_fills_a_blank_row_field_instead_of_being_dropped"
        status: pass
      - kind: unit
        ref: "test_preingest_merge.py::test_promotable_contact_props_names_the_twelve_promotable_contact_keys"
        status: pass
    human_judgment: false
  - id: D2
    description: "A key in neither set (lastmodifieddate) is still dropped and
      reported; the union is a set union (a shared key like jobtitle behaves
      byte-identically to before)"
    verification:
      - kind: unit
        ref: "test_preingest_merge.py::test_a_key_in_neither_set_is_still_dropped_and_reported"
        status: pass
      - kind: unit
        ref: "test_preingest_merge.py::test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before"
        status: pass
    human_judgment: false
  - id: D3
    description: "A widened key never reaches the dispatch CSV: strip_enrichment_extras
      removes it immediately before strip_row_id, and write_dispatch_csv still raises
      non_canonical_key_in_row on a genuinely unknown key after the strip, and (the
      negative half) without the strip the documented chain raises"
    verification:
      - kind: unit
        ref: "test_preingest_merge.py::test_the_documented_step_7_sequence_reaches_a_written_dispatch_csv"
        status: pass
      - kind: unit
        ref: "test_preingest_merge.py::test_write_dispatch_csv_still_raises_on_a_genuinely_unknown_key_after_the_strip"
        status: pass
      - kind: unit
        ref: "test_preingest_merge.py::test_without_the_new_strip_the_step_7_chain_raises_non_canonical_key_in_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both merge_enriched callers are traced and asserted end to end:
      enrich-before-ingest's dispatch-CSV path, and suggest-contacts' validate-only
      path (widened key accepted, reported in dropped_keys, never rejected)"
    verification:
      - kind: unit
        ref: "test_preingest_merge.py::test_the_suggest_contacts_path_tolerates_a_widened_key_through_validate"
        status: pass
      - kind: unit
        ref: "test_preingest_merge.py::test_a_rerequest_response_carrying_a_widened_key_keeps_it_on_the_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "SAFE-01: no threshold lowered (every contacts: min_confidence pinned
      to this plan's own Findings), no present value overwritten for a widened key,
      column_mapping.yaml/review_queue.py/extraction.py untouched, no n8n file touched"
    requirement: RICH-04
    verification:
      - kind: unit
        ref: "test_preingest_merge.py::test_the_shipped_field_policy_copy_is_byte_identical_to_the_repo_source"
        status: pass
      - kind: unit
        ref: "test_preingest_merge.py::test_a_present_widened_key_is_never_overwritten_and_records_a_conflict"
        status: pass
      - kind: other
        ref: "git diff --stat -- operator-claude-plugin/config/column_mapping.yaml operator-claude-plugin/scripts/review_queue.py operator-claude-plugin/scripts/extraction.py"
        status: pass
      - kind: other
        ref: "git status --porcelain -- n8n/ scripts/build_cloud_workflows.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "The plugin ships its own byte-identical config/field_policy.yaml
      copy -- required for the fix to be live in an installed plugin tree"
    verification:
      - kind: unit
        ref: "test_preingest_merge.py::test_the_shipped_field_policy_copy_is_byte_identical_to_the_repo_source"
        status: pass
    human_judgment: false
  - id: D7
    description: "The second root cause (merge_enriched ignoring jobtitle's own
      protect_if_current_present: false) is recorded as a named pending todo carrying
      no resolves_phase key, never auto-closed by the phase-completion helper"
    verification:
      - kind: other
        ref: "grep -c resolves_phase .planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md"
        status: pass
    human_judgment: false

# Metrics
duration: 24min
completed: 2026-09-07
status: complete
---

# Phase 65 Plan 02: RICH-04 -- merge_enriched's field-policy-widened allowlist Summary

**`merge_enriched`'s allowlist is now the union of the CSV-header alias set and
`field_policy.yaml`'s 12 promotable contact keys, so `seniority` and eight other
provider-returned fields survive onto a blank CREATE row instead of being silently
dropped before the keep/replace rule ever runs -- and are stripped back off at the
dispatch-CSV boundary, since HubSpot's own ingest lane has no column for them.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-09-07T00:14:25Z (immediately following 65-01)
- **Completed:** 2026-09-07T00:38:46Z
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `preingest.promotable_contact_props()` reads `config/field_policy.yaml`'s
  `contacts:` section (the plugin's own shipped copy first, then the repo's, via
  `resolve_policy_path()` -- the same three-step rule `preview.resolve_mapping_path`
  uses for `column_mapping.yaml`) and returns the sorted keys whose entry carries
  `promote_to_canonical: true`. Re-reads fresh per call, exactly like
  `extraction.canonical_props()`, so two merges cannot interfere through a shared
  cache.
- `merge_enriched`'s `allowed_keys` is now `set(extraction.canonical_props()) |
  set(promotable_contact_props())` and nothing else changed: the fill-versus-conflict
  branch, `dropped_property_keys` reporting, the row-id join, and duplicate-id
  refusal are byte-identical to before. Nine previously-dropped keys (`seniority`,
  `lv_linkedin_url`, `mobilephone`, `city`, `state`, `country`, `hs_state_code`,
  `hs_country_region_code`, `lv_persona_group`) now survive onto a blank CREATE row's
  field instead of being reported as `dropped_property_keys`.
- `preingest.strip_enrichment_extras()` drops exactly `promotable_contact_props() -
  extraction.canonical_props()` -- a closed, named set, never "everything unknown" --
  immediately before `extraction.strip_row_id` in `enrich-before-ingest/SKILL.md`
  step 7. **The widened keys never reach HubSpot through the dispatch CSV**: the
  deployed ingest lane's own column map has no header for any of them, so they serve
  the merge report, the held-row path, and Phase 69's future decline-store entries
  instead.
- **The plugin now ships its own `operator-claude-plugin/config/field_policy.yaml`**,
  byte-identical to `config/field_policy.yaml`, pinned by test. Without this copy the
  whole fix is inert in an installed plugin tree: the marketplace ships
  `operator-claude-plugin/` alone, so a repo-root-only lookup resolves to nothing.
- Both `merge_enriched` callers are traced end to end and asserted by tests:
  `enrich-before-ingest`'s dispatch-CSV path (with a negative-half test proving the
  strip is load-bearing, not decorative) and `suggest-contacts`' validate-only path
  (a widened key is accepted and reported in `dropped_keys`, never rejected).
  `rerequest_unanswered` inherits the union with no separate change.
- SAFE-01 is pinned: no `min_confidence` lowered (every `contacts:` entry's
  threshold is asserted against this plan's own Findings), a present widened-key
  value is never overwritten (recorded in `conflicts` instead), and
  `column_mapping.yaml`/`review_queue.py`/`extraction.py`/every `n8n/` file are
  untouched.
- The second root cause -- `merge_enriched`'s blanket fill-not-overwrite ignoring
  `jobtitle`'s own `protect_if_current_present: false` -- is recorded as a named
  pending todo carrying no `resolves_phase` key, so it will not close itself.

## Task Commits

Each task was committed atomically, following RED-GREEN for the `tdd="true"` tasks:

1. **Task 1: End-to-end "an enriched `seniority` survives the merge and the dispatch
   CSV still writes"** (tracer, tdd)
   - `a3765d3` (test) - add failing tests for merge_enriched's field-policy-widened allowlist
   - `46836c6` (feat) - merge_enriched's allowlist widens to the field-policy union (RICH-04)
2. **Task 2: Trace both callers and pin the edges the widening moves** (auto, tdd)
   - `fad7f6c` (test) - trace both merge_enriched callers and pin the widening's edges
     -- no paired feat commit; see Decisions Made (no production code change was
     needed, every behaviour was already correctly implemented by Task 1)
3. **Task 3: Pin SAFE-01 and record the deferred second root cause** (auto, not tdd)
   - `d5145d4` (test) - pin SAFE-01 for widened keys and defer jobtitle's own
     protection rule

No REFACTOR commits were needed for Task 1 -- the GREEN implementation was already
the shape a cleanup pass would have produced.

## Files Created/Modified

- `operator-claude-plugin/scripts/preingest.py` - `PLUGIN_POLICY_PATH`,
  `REPO_POLICY_PATH`, `resolve_policy_path`, `promotable_contact_props`,
  `strip_enrichment_extras`; `merge_enriched`'s `allowed_keys` and docstring
- `operator-claude-plugin/config/field_policy.yaml` - new, byte-identical shipped
  copy of `config/field_policy.yaml`
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` - step 7 gains
  `import preingest` and the `strip_enrichment_extras` call, plus a new prose
  paragraph naming it
- `operator-claude-plugin/tests/test_preingest_merge.py` - 22 new/renamed test
  functions across the three tasks (57 total in file, up from 35 baseline)
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` - the
  `enrich-before-ingest` step-7 `COVERED` tuple gains `preingest.
  strip_enrichment_extras`; sink (`extraction.write_dispatch_csv`) unchanged
- `.planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md` -
  new, the deferred second root cause

## Decisions Made

See the frontmatter `key-decisions` block above for full detail. In brief: the
plugin now ships its own `field_policy.yaml` copy (required for production
correctness); the widened keys are dispatch-CSV-boundary-only (never reach
HubSpot through that CSV); RICH-04 is closed as an audit plus the `seniority` half
only, with the richer-`jobtitle` half deferred to a named todo; a genuine factual
correction was made to the plan's Finding 8 regarding `held_queue.build_entry`
(documented as a deviation below); and Task 2 required no production code change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Plan finding correction] Finding 8 / Task 2's held_queue acceptance criterion
does not hold as literally stated**
- **Found during:** Task 2, while writing the held_queue/remainder_queue tracing tests
- **Issue:** 65-02-PLAN.md's Finding 8 (backed by a grep for
  `canonical_props|set\(row|row\.keys` across `held_queue.py`, `remainder_queue.py`,
  `run_manifest.py`, `confidence.py`, `chunking.py`) concluded "NONE of those five
  modules validates a row's key set... so a widened key rides through them
  untouched." Task 2's own acceptance criteria then asked for a test proving "a
  merged row carrying a widened key builds a `held_queue` entry and a
  `remainder_queue` entry without raising, and the key is present on the built
  entry." Verified empirically (direct interpreter call:
  `held_queue.build_entry({"row_id": ..., "email": ..., "seniority": "Director"},
  ...)`) that `held_queue.build_entry`'s stored `row` does NOT carry `seniority` --
  `held_queue.ROW_FIELD_ALLOWLIST = ("row_id",) + enrichment.MATCH_LOOKUP_KEYS` is a
  pre-existing, deliberate allowlist (module docstring, REVIEW-A7: "only the
  identity keys and the columns the envelope projects, never whatever else happened
  to be in the operator's spreadsheet"). The grep pattern used to write Finding 8
  missed this because `_allowlisted_row`'s filter is a dict comprehension over a
  named tuple, not a literal `canonical_props`/`set(row`/`row.keys` shape.
- **Fix:** Consulted the advisor before writing the test to confirm the correct
  disposition (do not widen `held_queue.ROW_FIELD_ALLOWLIST` -- it is a security
  allowlist, out of scope for this plan, and widening it would be a Rule 4
  architectural change). Wrote the test to assert the TRUE, verified behaviour:
  `held_queue.build_entry` does not raise, and the widened key is correctly ABSENT
  from the stored entry (with a comment citing `ROW_FIELD_ALLOWLIST`/REVIEW-A7 as the
  pre-existing, deliberate reason). Wrote a separate test confirming
  `remainder_queue.build_entry` DOES carry the widened key through untouched (its
  `spec` is stored verbatim, gated only by a forbidden-name scan for secrets/grants)
  -- so the underlying intent behind Finding 8 ("the operator seeing `seniority` on
  a held row is the point") is satisfied via the remainder-queue path, which is where
  it is actually true.
- **Files modified:** `operator-claude-plugin/tests/test_preingest_merge.py` only --
  no production code change
- **Verification:** `test_a_merged_row_with_a_widened_key_builds_a_held_queue_entry_without_raising`
  and `test_a_merged_row_with_a_widened_key_builds_a_remainder_queue_entry_untouched`
  both pass
- **Commit:** `fad7f6c`

---

**Total deviations:** 1 (plan finding correction, no rule-1/2/3 bug-fix or
missing-functionality auto-fix was needed -- the codebase behaved correctly
throughout; only the plan's own research needed correcting)
**Impact on plan:** No production behaviour changed as a result. The test suite
documents the real behaviour instead of a factually incorrect claim, which is the
more valuable outcome for future readers of this test file.

## Issues Encountered

- Task 2 (`tdd="true"`) turned out to require zero production code changes: every
  behaviour its tests pin was already correctly implemented by Task 1's GREEN
  commit. Investigated per `tdd.md`'s own "test doesn't fail in RED: the feature may
  already exist" guidance -- confirmed this is the expected, correct outcome (Task 2
  is explicitly a tracing/pinning task over Task 1's already-shipped implementation,
  not new feature work) rather than a masked implementation gap. A single
  `test(65-02):` commit was made for Task 2 with no paired `feat` commit, matching
  the test-only pattern 65-01 Task 3 established for a non-tdd task; see Decisions
  Made for the full reasoning.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- RICH-04 is closed for the `seniority` half. The richer-`jobtitle` half (the
  live evidence's "Head of Marketing and Content" example) is carried forward as
  `.planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md`,
  which names exactly what closing it would require (a per-field
  `protect_if_current_present` read, an operator ruling on whether
  `enrich-before-ingest` and `suggest-contacts` should follow the same rule, and new
  tests for both directions).
- This plan is the last plan in Phase 65 (its own frontmatter names it `wave: 2`,
  the phase's second and final wave; 65-01 was wave 1). No further plans are
  pending in this phase.
- No blockers.

---
*Phase: 65-round-empty-re-entry-keyed-on-the-cause*
*Completed: 2026-09-07*

## Self-Check: PASSED

- All 6 key files found on disk (`preingest.py`, `field_policy.yaml`,
  `enrich-before-ingest/SKILL.md`, `test_preingest_merge.py`,
  `test_skill_sequence_coverage.py`, the pending todo).
- All 4 commit hashes (`a3765d3`, `46836c6`, `fad7f6c`, `d5145d4`) resolve in
  `git log --oneline --all`.
- Re-ran all plan-level `<verification>` commands: full plugin suite `2564 passed,
  5 skipped` (baseline 2492 + 72 new); `cmp -s config/field_policy.yaml
  operator-claude-plugin/config/field_policy.yaml` exits 0; `git status --porcelain
  -- n8n/ scripts/build_cloud_workflows.py` empty; `git diff --stat --
  operator-claude-plugin/config/column_mapping.yaml
  operator-claude-plugin/scripts/review_queue.py operator-claude-plugin/scripts/
  extraction.py` empty; `grep -c resolves_phase` on the pending todo prints `0`.
- TDD gate compliance: `test(65-02):` precedes `feat(65-02):` for Task 1
  (`a3765d3` -> `46836c6`). Task 2 is `tdd="true"` but produced only a `test(65-02):`
  commit with no paired `feat` -- documented above as expected (no production code
  change was needed). Task 3 is not `tdd="true"`, one `test(65-02):` commit, no
  `feat` needed.
