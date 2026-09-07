---
phase: 65-round-empty-re-entry-keyed-on-the-cause
plan: 01
subsystem: operator-plugin
tags: [suggest-contacts, python, pytest, cause-classifier, round-empty]

# Dependency graph
requires:
  - phase: 64 (the ladder stops at the best page)
    provides: walk_pages's ended/people/selected/dropped/bar return shape -- one of
      round_outcome's three inputs
  - phase: 260904-5sd (search fallback quick task)
    provides: search_fallback.eligible_after_ladder (the fail-closed gate re-entry
      routes THROUGH, never around) and SOURCE_TIER_HOLD_CODE
provides:
  - suggest_contacts.round_outcome(walk, rows=None, sendable=None, held=None,
    fallback=None) -- the one pure classifier naming a round's cause
  - the closed ROUND_CAUSES (six values, precedence order) and ROUND_REENTRIES (two
    values) vocabularies
  - skills/suggest-contacts/SKILL.md step 7 rewired to route on
    outcome["reentry"] instead of an inline "if not people:" test, plus a
    per-company rounds list carrying each company's own cause/breakdown
affects: [69-decline-store]

# Actuals (#2632)
actuals:
  tokens: 13207
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fixed-precedence cause classification: first-match-wins over a closed
      vocabulary, pinned by a dedicated precedence test that mixes several
      conditions at once (mirrors the walk-ending vocabulary pattern from Phase 64)"
    - "Terminal-call-by-construction: presence of any one of four optional
      parameters (rows/sendable/held/fallback) is itself the signal that a call is
      terminal, making a second route structurally impossible rather than merely
      untested (no boolean flag, no counter)"
    - "Per-company row_id filter over a batch-wide shared list, scoped inside the
      pure function rather than in the orchestrating skill prose, so it is tested
      once instead of drifting from partition_for_dispatch's own name
      normalisation"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "gsd-tools check tdd-red-evidence is not present in this installed gsd-tools
    version (unknown subcommand). RED was verified manually for both TDD tasks:
    every RED-phase failure was an AttributeError/AssertionError on the exact target
    line, never a collection error, syntax error, or unrelated failure."
  - "The search_source_not_strong held-code literal is pinned by a dedicated test
    (test_round_outcome_held_reason_code_pins_to_search_fallbacks_hold_code) that
    imports search_fallback directly and drives round_outcome's real tally, rather
    than adding an unused module-level constant to suggest_contacts.py -- the
    breakdown tally is generic over reason_code strings and needed no constant to
    reference."
  - "LADDER-05 disposition (orchestrator ruling 2, Option A, quoted verbatim below)."

requirements-completed: [LADDER-03, LADDER-04]

coverage:
  - id: D1
    description: "round_outcome names one of six causes, with a full breakdown, for
      every round including a malformed one -- fixed precedence, fail-closed to
      unknown, never raises"
    requirement: LADDER-03
    verification:
      - kind: unit
        ref: "tests/test_suggest_contacts.py -k round_outcome (49 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Exactly one cause (no_people_found) routes anywhere, and only on
      the routing call (all four terminal markers None); any terminal call returns
      reentry: none by construction, structurally closing a second route"
    requirement: LADDER-04
    verification:
      - kind: unit
        ref: "tests/test_suggest_contacts.py::test_round_outcome_terminal_call_never_returns_a_reentry (24 cases)"
        status: pass
      - kind: unit
        ref: "tests/test_skill_sequence_coverage.py (round_outcome registered exactly twice, sink unchanged)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Each company in an interleaved batch carries its own cause and
      breakdown on the round's own rounds structure, filtered from the batch-wide
      sendable/held lists by row_id"
    verification:
      - kind: integration
        ref: "tests/test_suggest_contacts_composition.py::test_two_interleaved_companies_each_get_their_own_cause_and_breakdown"
        status: pass
    human_judgment: false
  - id: D4
    description: "The three hard constraints (a refusal stays terminal by every
      route, no cap reset with cap_exhausted never a trigger, no while loop) each
      have a runnable test"
    verification:
      - kind: integration
        ref: "tests/test_suggest_contacts_composition.py::test_a_refused_ladder_is_routed_by_cause_and_still_refused_at_the_gate"
        status: pass
      - kind: integration
        ref: "tests/test_suggest_contacts_composition.py::test_the_second_pass_spends_from_the_same_company_budget"
        status: pass
      - kind: unit
        ref: "tests/test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status"
        status: pass
    human_judgment: false
  - id: D5
    description: "LADDER-05 (the search fallback becomes reachable in a real
      round) -- wiring proven offline only; live reachability remains opportunistic
      and is NOT claimed complete by this phase"
    requirement: LADDER-05
    verification:
      - kind: unit
        ref: "tests/test_suggest_contacts.py::test_round_outcome_routes_an_empty_walk_to_the_search_fallback"
        status: pass
    human_judgment: true
    rationale: "Both live rounds to date found some people on the ladder, so
      no_people_found has never fired live; the code path is proven correct
      offline but a live zero-people company has not yet occurred. See the LADDER-05
      disposition section below."

# Metrics
duration: 27min
completed: 2026-09-07
status: complete
---

# Phase 65 Plan 01: Round-empty re-entry, keyed on the cause Summary

**round_outcome names one of six causes for a round that finds nothing usable and
routes on it -- three of the six spend nothing, and a second route is structurally
impossible rather than merely untested.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-09-06T23:47:48Z
- **Completed:** 2026-09-07T00:14:25Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `suggest_contacts.round_outcome(walk, rows=None, sendable=None, held=None,
  fallback=None)` is now the ONE place a round's cause is decided: it reads
  Phase 64's walk, `select_people`'s drop reasons, and `partition_for_dispatch`'s
  holds, and returns a fixed-precedence primary cause plus a full breakdown, failing
  closed to `unknown` on any malformed input without ever raising.
- The two closed vocabularies, `ROUND_CAUSES` (six values, precedence order) and
  `ROUND_REENTRIES` (two values), sit below `WALK_ENDINGS` in `suggest_contacts.py`,
  pinned by tests exactly as the existing `WALK_*` constants are.
- `skills/suggest-contacts/SKILL.md`'s step 7 no longer decides the round's cause
  from an inline `if not people:` test -- it calls `round_outcome` at exactly two
  straight-line sites (the routing call before `eligible_after_ladder`, the
  terminal call after `hold_weak_sources`), and step 9's report reads the cause and
  breakdown off each company's own `rounds` entry instead of re-deriving anything.
- `reentry` is `search_fallback` for exactly one of the six causes
  (`no_people_found`), and only on the routing call -- a call carrying any of
  `rows`/`sendable`/`held`/`fallback` is a terminal call by construction and always
  returns `reentry: none`, closing a second route structurally rather than by a
  counter or a flag.
- Two companies interleaved in one batch each get their own cause and breakdown,
  proven by a composition test that mints, merges, and partitions them together and
  then filters the shared `sendable`/`held` lists down to each company's own rows by
  `row_id`.
- The three hard constraints (a refusal stays terminal by every route, no cap reset
  with `cap_exhausted` never a trigger, no `while` loop anywhere in the plugin) each
  have a dedicated runnable test.

## Task Commits

Each task was committed atomically, following RED-GREEN for the two `tdd="true"`
tasks:

1. **Task 1: End-to-end "a company whose ladder found nobody is routed by its named
   cause"** (tracer, tdd)
   - `06feca9` (test) - add failing tests for round_outcome cause classifier
   - `f16def0` (feat) - round_outcome names a round's cause and routes on it
2. **Task 2: The terminal classify -- per-company cause and breakdown** (auto, tdd)
   - `85a5ea5` (test) - add failing tests for the terminal classify rows filter
   - `3075c9c` (feat) - terminal classify -- per-company cause and breakdown
3. **Task 3: Pin the invariants** (auto, test-only)
   - `aaea343` (test) - pin round_outcome invariants -- precedence, no second route,
     purity

No REFACTOR commits were needed for either TDD task -- both GREEN implementations
were already the shape a cleanup pass would have produced.

## Files Created/Modified

- `operator-claude-plugin/scripts/suggest_contacts.py` - `round_outcome`, its two
  closed vocabularies, `_unknown_outcome`, `_tally`
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` - step 7's routing call,
  `rounds` accumulation, terminal classify loop, step 9's cause/breakdown report
  contract
- `operator-claude-plugin/tests/test_suggest_contacts.py` - 49 `round_outcome` unit
  tests (vocabulary, precedence, fail-closed, rows filter, purity, structural)
- `operator-claude-plugin/tests/test_suggest_contacts_composition.py` - extended the
  documented-pipeline test plus 4 new composition tests
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` - the
  suggest-contacts `COVERED` tuple gains `suggest_contacts.round_outcome` twice; the
  sink (`suggest_contacts.round_artifact`) is unchanged

## Decisions Made

- **gsd-tools check tdd-red-evidence unavailable.** This installed gsd-tools version
  does not have that subcommand (`Error: Unknown check subcommand`). RED was
  verified manually for both TDD tasks by reading pytest's own failure output:
  Task 1's 14 failures were all `AttributeError: module 'suggest_contacts' has no
  attribute 'round_outcome'` (or the vocabulary constants); Task 2's 5 unit
  failures and 1 composition failure were real assertion mismatches (`'proposed' ==
  'all_held_on_email'`, `'no_people_found' == 'unknown'`), never a collection error
  or an unrelated failure.
- **The `search_source_not_strong` held-code literal is pinned by a driving test,
  not a module constant.** The plan's action text asked for this literal to be
  "restated" and pinned equal to `search_fallback.SOURCE_TIER_HOLD_CODE` by a test
  mirroring `test_walk_ending_vocabulary_pins_to_search_fallbacks_disposition_
  constants`. Since `round_outcome`'s breakdown tally is generic over whatever
  `reason_code` string a held entry carries (D-65-02: "key on each entry's own
  reason_code literal verbatim"), there was no functional need for a
  `suggest_contacts.py` constant that would sit unused except for a pinning
  assertion. `test_round_outcome_held_reason_code_pins_to_search_fallbacks_
  hold_code` imports `search_fallback` in the test only, drives `round_outcome`
  with a held entry carrying `search_fallback.SOURCE_TIER_HOLD_CODE` as its
  `reason_code`, and asserts the breakdown tallies it verbatim -- this proves the
  same thing (a rename in `search_fallback.py` would break the test) with less
  code and no dead constant.
- **Environment note, not a deviation.** Git commit messages containing backtick
  code-spans or apostrophes occasionally had those characters (and the surrounding
  punctuation) silently stripped when passed via `git commit -m "$(cat <<'EOF' ...
  )"` in this session's Bash tool. One commit (`f16def0`) has a message with a few
  dropped clauses and a stray trailing `EOF)` as a result; the diff itself is
  correct and unaffected. Every commit from `85a5ea5` onward used `git commit -F
  <file>` instead, which was not affected. Per the git safety protocol
  (create-new-commits-not-amend), this commit's message was left as-is rather than
  amended.

## Deviations from Plan

None - plan executed exactly as written. The one substantive implementation choice
(the held-code literal, above) stayed within CONTEXT.md's explicit "Claude's
Discretion" scope ("How the breakdown is rendered in the operator's report" /
signature and internal composition are left open) and changes no must-have truth,
no acceptance criterion, and no prohibition.

## Issues Encountered

- `gsd-tools check tdd-red-evidence` verb not present in this installed gsd-tools
  version -- worked around by manual RED verification (see Decisions Made above).
  Not blocking; noted for whoever next upgrades gsd-tools in this repo.
- A handful of Bash heredoc commit messages had backtick/apostrophe content
  corrupted by an apparent pre-processing pass in this session's tool environment
  (see Decisions Made above). Worked around by writing the message to a temp file
  and using `git commit -F <file>` for every commit after the first.

## LADDER-05 disposition (orchestrator ruling 2, Option A)

Recorded here verbatim, per the plan's own `<output>` instruction, so the verifier
and the milestone audit both see it without re-deriving it:

> LADDER-05's wiring is proven offline by
> `test_round_outcome_routes_an_empty_walk_to_the_search_fallback` plus the
> composition test that shows `eligible_after_ladder` is what is consulted next;
> live reachability in a real round remains opportunistic and is captured by the
> next live UAT sitting; LADDER-05's REQUIREMENTS.md checkbox is NOT ticked as
> fully satisfied by this phase.

Both live rounds to date (Brisbane Roar, The Roma Turf Club) found some people on
the ladder -- their causes were `none_classified` and `all_held_on_email`
respectively, neither of which is `no_people_found`. This plan makes those two
causes legible and reported; it does not create a new occasion for the search
fallback itself to fire. `LADDER-05` is therefore reported as `requirements-
completed` for LADDER-03 and LADDER-04 only -- LADDER-05 is intentionally left off
that list and its REQUIREMENTS.md checkbox untouched by this plan.

**This also makes closable:**
`.planning/todos/pending/2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md`
carries no `resolves_phase` key, so it will not close itself -- flagging here so the
next sweep picks it up.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `round_outcome` and its `rounds` structure are ready for Phase 69's decline store
  to read `cause` as a stable field, per D-65-01's "Reversibility: costly" note --
  Phase 69 builds no store here, but has a field to depend on rather than needing
  to re-derive it from raw stage outputs.
- Plan 65-02 (RICH-04, `merge_enriched`'s keep/replace rule) is next in this phase;
  it depends on 65-01 per its own frontmatter (`depends_on: [65-01]`) but touches
  none of the files this plan modified.
- No blockers. LADDER-05's live-reachability gap (above) is carried forward as an
  opportunistic live-UAT item, not a blocker for phase completion.

---
*Phase: 65-round-empty-re-entry-keyed-on-the-cause*
*Completed: 2026-09-07*
