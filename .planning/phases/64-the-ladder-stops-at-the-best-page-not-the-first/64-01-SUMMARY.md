---
phase: 64-the-ladder-stops-at-the-best-page-not-the-first
plan: 01
subsystem: operator-plugin
tags: [suggest-contacts, python, pytest, sitemap-ladder, role-classify]

# Dependency graph
requires:
  - phase: 62 (suggest-contacts foundation)
    provides: select_people, _name_key, agreed_cap, company_budget, next_candidates,
      url_fallback.filter_candidates -- every primitive walk_pages composes
  - phase: 260904-5sd (search fallback quick task)
    provides: search_fallback's DISPOSITION_REFUSED/DISPOSITION_CAP_EXHAUSTED vocabulary
      shape, mirrored (never imported) by the new WALK_* constants
provides:
  - walk_bar(chosen_families, per_company_cap) and walk_pages(pages, candidates, bar,
    family_list, chosen_families, known_contacts) in suggest_contacts.py
  - the closed WALK_GOOD_ENOUGH / WALK_LADDER_EXHAUSTED / WALK_CAP_EXHAUSTED /
    WALK_REFUSED / WALK_ENDINGS vocabulary
  - SKILL.md step 5/7/9 rewritten to cite the walk instead of "stop at the first page"
affects: [65-fallback-round-empty-reentry]

# Actuals (#2632)
actuals:
  tokens: 9076
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Closed ending vocabulary as named string constants, pinned equal to a sibling
      module's constants by test rather than by import (mirrors search_fallback.py's
      DISPOSITION_* shape without adding a cross-module import)"
    - "Score/select primitive reused verbatim per page (select_people), never
      re-implemented, to let classification run mid-walk instead of after it"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "D-64-01/D-64-02: pages accumulate into one union deduped by normalised first+last
    name; a winner never replaces the rest, and a person missing either name half is
    never deduped away."
  - "D-64-06: the bar is max(len(chosen_families), per_company_cap) -- the cap floor
    stops a one-family round from reproducing the exact defect being fixed."
  - "D-64-10: refusal is checked before a page's people are touched, keyed only on a
    FETCHED page's own disposition -- a pre-fetch off-host refusal from
    url_fallback.filter_candidates can never produce ended=refused."
  - "D-64-08 boundary held: walk_pages emits ended and acts on none of it; the
    if not people: guard gating search_fallback.eligible_after_ladder is untouched."

patterns-established:
  - "Round-level values (the bar) are resolved once alongside the vocabulary/cap they
    depend on, never re-derived per company -- same precedent as step 3's agreed_cap."

requirements-completed: [LADDER-01, LADDER-02, SAFE-02, SAFE-03]

coverage:
  - id: D1
    description: "walk_bar/walk_pages fold every fetched page's people into one
      union deduped by name, scored per page by the role filter, stopping once the
      cumulative hit count clears max(len(chosen_families), per_company_cap) --
      demonstrated on the receptionist+board-page live case (10 people unioned,
      ends good_enough at the board page)"
    requirement: LADDER-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_walk_pages_unions_people_across_pages_in_walk_order"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_walk_pages_end_to_end_into_extraction_validate"
        status: pass
    human_judgment: false
  - id: D2
    description: "the four-value closed ended vocabulary (good_enough,
      ladder_exhausted, cap_exhausted, refused) is fully reachable; a refusal on a
      fetched page is terminal even with candidates left, and cap_exhausted/
      ladder_exhausted are read off next_candidates' own dict, never a counter the
      walk keeps itself"
    requirement: LADDER-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_walk_pages_ends_on_refused_disposition_even_with_candidates_left"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_walk_ending_vocabulary_pins_to_search_fallbacks_disposition_constants"
        status: pass
    human_judgment: false
  - id: D3
    description: "search_fallback.eligible_after_ladder is unchanged, uncalled, and
      unimportable from suggest_contacts.py -- a refusal stays a fence walk_pages
      cannot route around (SAFE-02)"
    requirement: SAFE-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_walk_pages_never_imports_search_fallback"
        status: pass
      - kind: other
        ref: "git diff --stat operator-claude-plugin/scripts/search_fallback.py operator-claude-plugin/scripts/url_fallback.py -- empty"
        status: pass
    human_judgment: false
  - id: D4
    description: "url_fallback.MAX_FOLLOWUP_FETCHES stays 5, walk_pages' body never
      references it, and no plugin script (including the walk) contains a while loop
      -- the walk spends the SAME budget better, never a larger one (SAFE-03)"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_max_followup_fetches_is_still_five"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py::test_walk_pages_source_contains_no_while_loop"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status"
        status: pass
    human_judgment: false
  - id: D5
    description: "SKILL.md step 5 and step 7 cite walk_bar/walk_pages instead of
      carrying 'stopping at the first one that yields people' as prose; step 9's
      report gains the walk's ending reason per company; n8n/ has a zero diff"
    verification:
      - kind: other
        ref: "grep -cE 'first (one )?that yields' operator-claude-plugin/skills/suggest-contacts/SKILL.md -- 0"
        status: pass
      - kind: other
        ref: "git status --porcelain -- n8n/ scripts/build_cloud_workflows.py -- empty"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-09-04
status: complete
---

# Phase 64 Plan 01: The Ladder Stops at the Best Page Summary

**walk_bar/walk_pages fold every fetched page's people into one deduped union scored by the role filter, stopping on a cumulative bar instead of the first page that yields anyone**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-04T06:29:52Z
- **Completed:** 2026-09-04T06:44:58Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- `walk_bar(chosen_families, per_company_cap)` and `walk_pages(pages, candidates, bar,
  family_list, chosen_families, known_contacts)` added to `suggest_contacts.py`: every
  page fetched for a company folds its people into one set deduped by normalised
  first+last name, scored per page by `select_people` (so `role_classify.classify_title`
  runs mid-walk), and the walk stops once the cumulative hit count clears
  `max(len(chosen_families), per_company_cap)` -- never on the mere presence of a person
  on the page just fetched.
- The closed `WALK_GOOD_ENOUGH` / `WALK_LADDER_EXHAUSTED` / `WALK_CAP_EXHAUSTED` /
  `WALK_REFUSED` ending vocabulary is fully reachable and individually tested. A
  refusal on a fetched page is terminal even with unfetched candidates remaining
  (D-64-10, SAFE-02); `cap_exhausted`/`ladder_exhausted` are read straight off
  `next_candidates`'s own dict, never a counter the walk keeps itself (D-64-09,
  D-64-13, SAFE-03).
- `SKILL.md` step 5's "stopping at the first one that yields people" clause is gone,
  replaced by a citation of the two functions; step 7's executable block now drives
  the real per-company walk (fetch, fold into `pages`, re-walk, continue only while
  `ended is None`); step 9's report gains the walk's ending reason per company.

## Task Commits

Each task was committed atomically (Tasks 1 and 2 are `tdd="true"`, RED then GREEN):

1. **Task 1: End-to-end union-and-bar walk** - `fda10c6` (test, RED) -> `4e9f5e2` (feat, GREEN)
2. **Task 2: The closed `ended` vocabulary** - `9b7b299` (test, RED) -> `c2a9167` (feat, GREEN)
3. **Task 3: Finish the SKILL.md caller contract and pin invariants** - `8a4d172` (feat)

_Task 3's commit message was regenerated via `git commit --amend -F <file>` immediately
after the original commit, because unquoted backticks in the first heredoc-authored
message were interpreted by the shell as command substitution, truncating two clauses
and leaving a literal `EOF\n)` in the message body. The diff content was correct and
untouched throughout; only the message text was corrected, on the same, unpushed,
just-created local commit._

## Files Created/Modified
- `operator-claude-plugin/scripts/suggest_contacts.py` - `walk_bar`, `walk_pages`, and
  the `WALK_*` closed vocabulary
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` - step 5/7/9 rewritten to
  cite the walk predicate
- `operator-claude-plugin/tests/test_suggest_contacts.py` - 20 new tests covering
  every `<behavior>` bullet across both tasks plus the Task 3 invariants
- `operator-claude-plugin/tests/test_suggest_contacts_composition.py` - the
  `suggest-contacts` composition test now also drives `walk_bar`/`next_candidates`/
  `walk_pages` for real (see Deviations)
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` - the `suggest-contacts`
  `COVERED` registry tuple updated to the new documented call sequence (see Deviations)

## Decisions Made
- Task 1 and Task 2 implement `walk_pages`'s ending resolution in two passes exactly as
  the plan's action text phases them (Task 1: fold + `good_enough`/`None` only; Task 2:
  add the refused check and the two terminal-budget endings) rather than writing the
  complete four-ending function in one commit -- this keeps each TDD RED/GREEN pair
  scoped to one task's own `<behavior>` bullets, matching the plan's explicit "leave the
  three terminal endings to Task 2" instruction.
- `fetched_url` in the SKILL.md step-7 block is set to the last page appended to `pages`
  (`pages[-1]["url"]`) when the ladder path is taken -- this is always the page that
  either cleared the bar or exhausted the ladder, matching the documented "URL actually
  fetched for the people being synthesised" semantics without inventing a new variable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The pre-existing sequence-coverage ratchet broke as a direct consequence of the required SKILL.md rewrite**
- **Found during:** Task 3, running the full plugin suite per its own `<verify>`
- **Issue:** `test_skill_sequence_coverage.py` statically extracts the documented
  `module.function(...)` call sequence from every `skills/*/SKILL.md` python block and
  fails when a sequence is neither claimed by a named composition test (`COVERED`) nor
  deliberately excluded. Task 3's required step-7 rewrite (adding `walk_bar` and two
  `next_candidates` calls around one `walk_pages` call) changed the extracted sequence,
  orphaning the old `COVERED` registry entry and producing a new, unregistered one.
- **Fix:** Updated the `suggest-contacts` `COVERED` tuple in
  `test_skill_sequence_coverage.py` to the new sequence, and extended
  `test_suggest_contacts_composition.py`'s covering test
  (`test_the_documented_round_pipeline_drives_its_real_joins_end_to_end`) to actually
  call `walk_bar`, `next_candidates` (twice) and `walk_pages` for real, asserting the
  walk's own terminal ending independently of `eligible_after_ladder`'s separate
  question -- not just renaming the registry key.
- **Files modified:** `operator-claude-plugin/tests/test_skill_sequence_coverage.py`,
  `operator-claude-plugin/tests/test_suggest_contacts_composition.py`
- **Verification:** `test_skill_sequence_coverage.py` passes; full plugin suite green.
- **Committed in:** `8a4d172` (Task 3 commit)

**2. [Rule 1 - Bug] A structural invariant test I authored tripped on the docstring it was meant to exempt**
- **Found during:** Task 3, writing the `MAX_FOLLOWUP_FETCHES` non-reference invariant
  test the plan itself requires
- **Issue:** `walk_pages`'s own docstring (written in Task 1) names
  `MAX_FOLLOWUP_FETCHES` in prose to explain the D-64-09 invariant. A naive substring
  scan over the function's full source (docstring included) therefore failed against
  the function's own explanatory text, not its executable body.
- **Fix:** Scoped the structural test to the function's AST body with the docstring
  statement stripped, rather than weakening the docstring's explanation.
- **Files modified:** `operator-claude-plugin/tests/test_suggest_contacts.py`
- **Verification:** `test_walk_pages_source_never_references_max_followup_fetches` passes.
- **Committed in:** `8a4d172` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3/Rule 1 -- blocking test-suite failures
surfaced by the plan's own required edits, not scope creep).
**Impact on plan:** Both fixes were required to satisfy the plan's own `<verify>`
("run the FULL plugin suite and confirm the pre-existing count has only grown"); neither
touched `suggest_contacts.py`, `SKILL.md`'s documented behavior, `search_fallback.py`, or
`url_fallback.py`.

## Issues Encountered
Task 3's initial commit message was corrupted by unquoted backticks inside a
single-quoted heredoc being misinterpreted as command substitution by the shell
wrapper in this environment (two clauses truncated, a literal `EOF\n)` appended).
Corrected via `git commit --amend -F <message-file>` on the same, unpushed, just-created
commit before any further work -- content untouched, message only.

## Next Phase Readiness
`walk_pages`'s `ended` field is live and tested but acted on by nothing (D-64-08's
boundary, deliberately). Phase 65 (round-empty re-entry keyed on cause) consumes it.
No blockers.

---
*Phase: 64-the-ladder-stops-at-the-best-page-not-the-first*
*Completed: 2026-09-04*
