---
phase: 62-suggest-the-contacts-nobody-named
plan: 08
subsystem: api
tags: [operator-claude-plugin, suggest-contacts, chunking, preingest, row_id, dispatch]

# Dependency graph
requires:
  - phase: 62-suggest-the-contacts-nobody-named
    provides: "suggest_contacts.py's eligibility/discovery_plan/select_people/synthesise_rows/partition_for_dispatch (plans 62-01..62-04), and preingest.build_rows_spec/merge_enriched/chunking.dispatch_plan (Phase 37/57/61 machinery this plan composes, never re-implements)"
provides:
  - "suggest_contacts.mint_row_ids -- the single batch-level row_id mint call site for a suggestion round, wrapping preingest.build_rows_spec"
  - "suggest_contacts.rejoin_enriched -- the merge_enriched-fresh-rows re-join, keyed on row_id"
  - "A corrected suggest-contacts/SKILL.md worked example that actually reaches a dispatched chunk"
  - "The sequence-coverage COVERED registry's suggest-contacts entry, re-registered to the new live identity"
affects: [suggest-contacts, enrich-before-ingest, 62-uat]

actuals:
  tokens: 5819
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Batch-level id minting: build_rows_spec called exactly once, after every eligible company's stage-1 records are accumulated, never per company"
    - "Fresh-row re-join by row_id after a merge/dispatch pass whose own contract is 'returns fresh rows, never mutates input'"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/tests/test_suggest_contacts_composition.py
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py

key-decisions:
  - "Decision 1 (WHERE build_rows_spec is called): implemented exactly as planned -- mint_row_ids is called once, at the head of stage 7, after the per-company accumulation loop and before the first stage-2 call. Never inside synthesise_rows (would falsify its canonical-only assertion) and never inside extraction.validate (Decision 3)."
  - "Decision 2 (provenance sidecar, both re-joins as code): implemented as planned -- mint_row_ids pairs each record with build_rows_spec's own row at the same index; rejoin_enriched indexes merge_enriched's fresh rows by row_id and raises ValueError naming any record whose id is absent, rather than silently leaving it on a stale pre-merge row."
  - "Decision 3 (validate's ordering stays put): confirmed correct and unchanged -- extraction.validate() still runs once per sendable row, after stage 2. SKILL.md step 8 now states explicitly why: validate never minted row_id and never will; row_id is reported in dropped_keys and the record is still accepted; strip_row_id remains the boundary strip before a dispatch CSV, unchanged."
  - "Decision 4 (fenced block documents the handoff, not the send): implemented as planned -- the rewritten worked example resolves the vocabulary and per-company cap once, loops to accumulate records, mints once, builds the chunk plan, then hands `plan` to enrich-before-ingest/SKILL.md step 5's dispatch block by reference (a comment, not forty re-documented lines of grant/arming/ceiling machinery)."
  - "COVERED registry nodeid: kept test_the_documented_round_pipeline_drives_its_real_joins_end_to_end (the sink, suggest_contacts.round_artifact, did not move), per the plan's own explicit conditional -- the comment above the entry now names Task 1's new composition test as the one that actually drives the mint/rejoin/chunking calls end to end."

patterns-established:
  - "A gap-closure composition test drives the WHOLE documented sequence through the real shared machinery (chunking.dispatch_plan with a stub transport, a real preingest.merge_enriched) rather than mocking either boundary -- same discipline as G-62-1's closure."

requirements-completed: [SUGGEST-01, SUGGEST-02, SUGGEST-04, SUGGEST-05]

coverage:
  - id: D1
    description: "A row from synthesise_rows reaches ChunkResult(ok=True) through chunking.dispatch_plan with a stub transport -- closes G-62-4's blocker"
    requirement: "SUGGEST-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts_composition.py#test_the_documented_round_reaches_an_accepted_chunk_and_an_enriched_sendable_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "row_id is minted exactly once across a two-company batch, never per company"
    requirement: "SUGGEST-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts_composition.py#test_the_documented_round_reaches_an_accepted_chunk_and_an_enriched_sendable_row"
        status: pass
    human_judgment: false
  - id: D3
    description: "An enriched row lands sendable and an unenriched one lands held, after a real preingest.merge_enriched and suggest_contacts.rejoin_enriched"
    requirement: "SUGGEST-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts_composition.py#test_the_documented_round_reaches_an_accepted_chunk_and_an_enriched_sendable_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "SKILL.md's fenced worked example, copied verbatim, mints once and dispatches -- and the sequence-coverage registry names its actual live identity with no orphan left behind"
    requirement: "SUGGEST-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py#test_no_new_or_orphaned_sequence_exists_in_the_live_corpus"
        status: pass
    human_judgment: false
  - id: D5
    description: "Zero n8n change and zero live side effect"
    verification:
      - kind: other
        ref: "git status --porcelain n8n/ scripts/build_cloud_workflows.py (silent)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-04
status: complete
---

# Phase 62 Plan 08: Mint the row_id join key once per batch, and re-join the merge Summary

**Two seam functions (`mint_row_ids`, `rejoin_enriched`) close G-62-4's blocker — the documented suggest-contacts round could not dispatch stage 2 at all, because nothing ever called `preingest.build_rows_spec`.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `suggest_contacts.mint_row_ids(records)` — the single call site that mints the whole
  batch's `row_id` join keys once, wrapping `preingest.build_rows_spec` (never
  re-implementing it), pairing each record with its own minted row so provenance stays
  attached to the person it was recorded for.
- `suggest_contacts.rejoin_enriched(records, merged_rows)` — joins `preingest.merge_enriched`'s
  FRESH rows back onto the round's own records by `row_id`, raising `ValueError` naming
  any record whose id is missing from the merged set, rather than silently leaving it
  on a stale pre-merge row.
- A new composition test drives the WHOLE documented sequence — two companies, a real
  `chunking.dispatch_plan` with a stub transport, a real `preingest.merge_enriched` —
  and reaches `ChunkResult(ok=True)`, the assertion the existing part-wise suite could
  never make. Two direct refusal tests pin both new functions' failure modes.
- `skills/suggest-contacts/SKILL.md` steps 6-8 and its fenced worked example rewritten
  so the documented round actually dispatches: the role vocabulary and per-company cap
  are resolved once before the per-company loop, records accumulate across companies,
  the mint happens once after the loop, and the re-join happens before partitioning.
- `test_skill_sequence_coverage.py`'s `COVERED` registry re-registered to the block's
  new live identity (read from the suite's own failure message, never hand-written).

## Task Commits

1. **Task 1: A synthesised row reaches an ACCEPTED chunk — the whole documented sequence, end to end, with a stub transport** - `7fd4432` (fix)
2. **Task 2: Fix the worked example an implementer copies, and re-register the documented sequence** - `5c81304` (docs)

_No separate "plan metadata" commit was made per this plan's `commit_docs` outcome — see Self-Check below for the final-commit step's result._

## Files Created/Modified

- `operator-claude-plugin/scripts/suggest_contacts.py` — added `mint_row_ids` and `rejoin_enriched`, plus an `import preingest`
- `operator-claude-plugin/tests/test_suggest_contacts_composition.py` — added the composition test and two direct refusal tests; the pre-existing `test_the_documented_round_pipeline_drives_its_real_joins_end_to_end` was left byte-unmodified
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — steps 6-8 rewritten, fenced worked example rewritten
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — `COVERED`'s `suggest-contacts` entry replaced with the new 13-call identity and an extended comment

## Decisions Made

All four decisions recorded in `62-08-PLAN.md`'s `<decisions_recorded>` were implemented
exactly as written — see `key-decisions` in the frontmatter above for each one's outcome.
One additional, plan-directed choice was made during Task 2: per the plan's own explicit
conditional ("the covering nodeid stays [the old test] only if that test still mentions
the new sink function's bare name; if the sink moved, point the entry at Task 1's new
test instead"), the `COVERED` nodeid was kept pointed at the pre-existing
`test_the_documented_round_pipeline_drives_its_real_joins_end_to_end` because the sink
(`suggest_contacts.round_artifact`) did not move. The registry comment was extended to
name Task 1's new test as the one that actually drives the new mint/rejoin/chunking
calls end to end — `test_every_covered_nodeid_resolves_to_a_real_test_mentioning_the_sequences_sink`
is a staleness guard by its own documented design, not a coverage-strength proof, so this
does not weaken it.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were needed; both new
functions worked on the first implementation after the RED baseline was captured.

## RED-first evidence (per plan's `<tdd_requirement>` and verification item 5)

**The composition test observed RED before any fix, exactly as required.** Running
`.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py -q`
against the test file with `mint_row_ids`/`rejoin_enriched` calls added but *before*
either function existed in `suggest_contacts.py` produced:

```
E       AttributeError: module 'suggest_contacts' has no attribute 'mint_row_ids'
...
3 failed, 4 passed in 0.11s
```

(The 4 passes are the four pre-existing tests in that file, confirming they were
untouched and still green.) This is a genuine RED, not a green-on-first-run: the test
could not even reach the dispatch assertion without the fix.

**Separately, as concrete documentary evidence of the exact defect G-62-4 names** (not
part of the pytest suite — a standalone repro run against the pre-fix code, matching the
documented sequence with NO mint step, exactly as `suggest-contacts/SKILL.md` read before
this plan):

```
record row (pre-mint): {'company': 'Example Club', 'firstname': 'Jamie', 'lastname': 'Fox', 'jobtitle': 'Head of Broadcast'}
ChunkResult: ChunkResult(index=0, rows=1, ok=False, reason='A row without a `row_id` can never be matched back to its response — `row_id` is the join key every downstream verdict is keyed on.', resolvable=())
```

This reproduces the UAT's own G-62-4 finding verbatim and confirms the composition
test's later `ChunkResult(ok=True)` assertion is exercising the real gap, not a
tautology.

**Post-fix:** the same composition test file passes 7/7; the full plugin suite passes
2328/2328 (5 skipped, pre-existing and unrelated); the node suite passes 867/867;
`git status --porcelain n8n/ scripts/build_cloud_workflows.py` is silent.

## Issues Encountered

None.

## Self-Check

- `operator-claude-plugin/scripts/suggest_contacts.py` — FOUND, contains `mint_row_ids`/`rejoin_enriched`
- `operator-claude-plugin/tests/test_suggest_contacts_composition.py` — FOUND, 7 tests, all pass
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — FOUND, steps 6-8 and fenced block rewritten
- `operator-claude-plugin/tests/test_skill_sequence_coverage.py` — FOUND, `COVERED` re-registered, 11/11 tests pass
- Commit `7fd4432` — FOUND in `git log --oneline`
- Commit `5c81304` — FOUND in `git log --oneline`

**Self-Check: PASSED**

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

G-62-4 (blocker) is closed at the code and SKILL.md level. Per this plan's own
`<hard_constraints>`, no live sitting was run and none was attempted — the operator's
own supervised walk, over `suggest-contacts/SKILL.md` as it now reads, is the remaining
step to move G-62-4's UAT entry from `failed` to `resolved` (mirroring G-62-1's own
"landed, locally verified, NOT yet live-proven" pattern in `62-UAT.md`). Companion gap
closures G-62-1 (resolved), G-62-2, G-62-3, G-62-5 and G-62-4's own sibling plan 62-09
(role vocabulary matcher, committed concurrently in this same wave) are unaffected by
this plan's changes — `git status --porcelain` confirms this plan touched only its own
four `files_modified` paths.

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-04*
