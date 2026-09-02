---
phase: 37-enrich-before-ingest
plan: 08
subsystem: skill
tags: [skill-contract, arming, ordering-test, batched-confirmation]

requires:
  - phase: 37-enrich-before-ingest
    plan: 01
    provides: "enrichment.MATCH_LOOKUP_KEYS, build_envelope's rows branch, chunking.chunk_ceiling(key=)"
  - phase: 37-enrich-before-ingest
    plan: 02
    provides: "extraction.hold_emailless, write_dispatch_csv's emailless-row raise"
  - phase: 37-enrich-before-ingest
    plan: 03
    provides: "preingest.build_rows_spec/fetch_matches/match_batch/classify_matches"
  - phase: 37-enrich-before-ingest
    plan: 04
    provides: "preingest.apply_match_decisions/merge_enriched/rows_from_table"
  - phase: 37-enrich-before-ingest
    plan: 05
    provides: "preview_enrichment.records_block's rows branch, preingest.render_enriched_preview"
  - phase: 37-enrich-before-ingest
    plan: 06
    provides: "run_manifest.save/load/rows_to_resume — the idempotent resume this skill's step 8 renders"
  - phase: 37-enrich-before-ingest
    plan: 07
    provides: "the resolved post-ingest handoff: automatic at create time via lv_enrichment_requested, no third arming phrase"
provides:
  - "skills/enrich-before-ingest/SKILL.md — the operator entry point rendering 37-CONTEXT.md sec 5, step 3 amended to a batched numbered table per 37-CONTEXT.md sec 13"
  - "tests/test_enrich_before_ingest_skill_contract.py — 21 pins: the character-offset ordering pin, the same-step phrase-separation pin, and 6 pins over the batched-confirmation vocabulary, every one red-checked"
affects: [37-09]

actuals:
  tokens: 7250
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Character-offset heading-order pin: two literal, line-anchored heading substrings located by text.find(), non-negativity asserted before comparison, failure message names both offsets"
    - "Numbered-step-span split (regex on `^N. **`) + per-span phrase containment check, reusing the analog file's _normalized() idiom so a markdown reflow cannot hide or fabricate a phrase collision"
    - "Regex adjacency pin (no bare occurrence): a phrase is required to appear only when immediately followed by a specific pattern (digit), asserted over every match found rather than the first"

key-files:
  created:
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
  modified: []

key-decisions:
  - "Step 1 previews the two-arm design WITHOUT quoting either literal arming phrase — it describes the shape (\"twice, at two different moments\") generically. This is what keeps the same-step test meaningful: if step 1 quoted both phrases to preview them, the same-step exclusion would either have to special-case step 1 or fail on the very sentence explaining the design. Naming the phrases only inside their own arming step (5 and 7 respectively) is what makes the same-step pin a real property of the document rather than an artifact of where the preview happens to sit."
  - "The three §5 consequences (rewritten CSV, MEDIUM-no-email routes to enrich-records, per-call grant) live inside step 7's own prose rather than a trailing unnumbered section — a trailing section would have been swallowed into step 7's own span by the same-step test's regex split (the last numbered marker's span runs to EOF), so keeping them there was correctness, not a stylistic choice. The invariant sentence (\"arming one lane does not arm any other lane\") deliberately never re-quotes the sibling phrase (`\"arm the enrichment\"`) by name, for the identical reason."
  - "Resume turn (37-CONTEXT sec 13a) is its own numbered step 8, not a subsection under step 7 — giving it a numbered-step span of its own keeps it outside both arming steps' spans and gives the contract test's split a clean anchor, rather than an implicit trailing block whose boundary depends on where step 7's prose happens to end."
  - "queue_handoff_ids (37-07's Task 1 deliverable) is not called anywhere in this skill, on 37-07's own explicit instruction: the poller handoff for created records is automatic via `lv_enrichment_requested`, stamped backend-side at create time. This skill instead hands `classified['auto_matched']`'s ids — matched, not created, records — to `enrich-records`, which is a different id pool queue_handoff_ids was never meant to serve."
  - "Task 3 checkpoint verdict, folded per the operator's own 37-CONTEXT.md sec 13 amendment: one-proposal-per-turn is superseded by a single numbered markdown table per chunk, one line per decision, with a constrained four-verb vocabulary (approve/deny/pick <sub-label>/email: <address>). The literal two-word phrase 'approve all' appears exactly once in the file and is immediately followed by a restated count ('approve all 6') — every other bulk-approve example names an explicit scope ('approve 1-4, 7'); a bare, unscoped 'approve all' is never offered as valid input anywhere in the document, which is the amendment's own hard requirement, not just its test's."
  - "No code change was needed for the amendment: apply_match_decisions was already batch-shaped (resolved is already a dict of every row's decision, applied in one call with an all-or-nothing guard). Only the skill's operator-facing description of HOW those decisions get collected changed, plus the contract test covering that description."

requirements-completed: [DISPATCH-03, PREVIEW-01]

coverage:
  - id: D1
    description: "skills/enrich-before-ingest/SKILL.md exists with parseable frontmatter (name=enrich-before-ingest, non-empty description naming the slash form and firing on natural phrasing), renders the eight-step sequence from 37-CONTEXT.md sec 5 (step 3 per sec 13's amendment) end to end, states the two-arm warning up front in step 1, names all four match groups, references contact-upload/SKILL.md steps 6-10 by heading text without reproducing their bodies, and contains no `lastmodifieddate` string anywhere."
    requirement: PREVIEW-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_skill_exists_with_parseable_frontmatter_carrying_name_and_description, ::test_the_description_fires_on_natural_operator_phrasing_and_names_the_slash_form, ::test_the_skill_names_all_four_match_groups, ::test_the_skill_references_contact_upload_steps_six_through_ten_by_heading_text, ::test_the_skill_does_not_reproduce_contact_upload_step_bodies, ::test_no_last_modified_field_is_implied_on_the_match_candidate_endpoint"
        status: pass
    human_judgment: false
  - id: D2
    description: "The two arming phrases (\"arm the enrichment\", \"arm the upload\") both appear, no combined or third phrase appears against a checked list of plausible spellings, the ingest-arm heading's character offset is strictly greater than the enriched-preview heading's, and no single numbered step contains both phrases. All four pins were red-checked by physically breaking the property they guard: swapping the step-6/step-7 blocks made the ordering test fail naming both offsets (ingest 8691 vs preview 12087); injecting the upload phrase into step 5's span made the same-step test fail naming step 5."
    requirement: DISPATCH-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_both_arming_phrases_appear, ::test_no_combined_or_third_arming_phrase_appears, ::test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading, ::test_the_two_arming_phrases_never_share_a_numbered_step"
        status: pass
    human_judgment: false
  - id: D3
    description: "The batched-table confirmation format (37-CONTEXT.md sec 13 amendment): the four-verb vocabulary is pinned literally, `deny all` is offered, a bare unscoped `approve all` never appears (regex-checked against every match, not just the first), a pending row is stated to be restated and never defaulted, an ambiguous row is stated to take only `pick`, and one bad line is stated to refuse the whole table naming the offending line. All six pins were red-checked individually by mutating the skill text and observing the specific named failure, then restored to a byte-identical file (diff confirmed empty) before committing."
    requirement: DISPATCH-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_confirmation_vocabulary_is_pinned_to_exactly_four_verbs, ::test_deny_all_is_offered, ::test_bare_approve_all_never_appears_without_a_trailing_count_or_scope, ::test_a_pending_row_is_restated_never_defaulted, ::test_ambiguous_rows_are_restricted_to_pick, ::test_one_bad_line_refuses_the_whole_table_naming_the_offending_line"
        status: pass
    human_judgment: false
  - id: D4
    description: "An operator reading skills/enrich-before-ingest/SKILL.md top to bottom: the two-arm warning reads as a reason, the enriched preview reads as a decision point, held rows are named as people, and the contact-upload steps 6-10 handoff is findable. Verdict: three of four passed as written; the fourth (confirmation format) was corrected via the sec 13 amendment folded into D3 above, not reopened as a fresh checkpoint."
    verification: []
    human_judgment: true
    rationale: "Task 3 is a checkpoint:human-verify with gate=\"blocking\" specifically because prose-quality judgment (does the warning read as a reason, does the preview feel like a decision) cannot be automated. The operator's verdict and the resulting design amendment are recorded verbatim in 37-CONTEXT.md sec 13 and commit 9b0ca62."

duration: ~50min total (Tasks 1-2 ~30min, amendment ~20min)
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 08: The Enrich-Before-Ingest Skill — Two Arms, One Batched Table Summary

**`skills/enrich-before-ingest/SKILL.md` renders the eight-step flow from 37-CONTEXT.md §5 — target, unarmed match, a batched one-numbered-table confirmation (amended from one-proposal-per-turn per §13), cost preview, "arm the enrichment", the enriched preview, "arm the upload", and a resume turn — with 21 contract-test pins covering the two arming phrases' separation and the batched table's constrained vocabulary, every pin observed failing before being trusted green.**

## Performance

- **Duration:** ~50 min total (Tasks 1-2 ~30 min; the checkpoint amendment ~20 min)
- **Completed:** 2026-08-05
- **Tasks:** 3/3
- **Files modified:** 2 (both created, both then amended in place)

## Accomplishments

- `skills/enrich-before-ingest/SKILL.md` (8 numbered steps) built on the exact function
  signatures 37-01 through 37-07 shipped — read directly from source, not reconstructed
  from the plan text: `preingest.rows_from_table`, `build_rows_spec`, `match_batch`,
  `classify_matches`, `apply_match_decisions`, `DECLINE_MATCH`, `merge_enriched`,
  `render_enriched_preview`; `chunking.chunk_ceiling(key=)`, `plan_chunks`,
  `dispatch_plan`; `extraction.hold_emailless`, `write_dispatch_csv`;
  `run_manifest.save/load/rows_to_resume`.
- Step 1 states the target and previews the two-arm design generically, without
  quoting either literal phrase — the phrases are named only inside their own arming
  steps (5 and 7), which is what keeps the contract's same-step exclusion a real
  property of the document.
- Step 2 reports exactly four match groups by name (auto-matched, proposed, unmatched,
  unchecked) and states the search itself needs no arming — it spends no credit and
  writes nothing.
- **Step 3, amended (37-CONTEXT.md sec 13):** proposed matches render as one numbered
  markdown table per chunk — row's own firstname/lastname/company/email beside the
  candidate's six fields, ambiguous rows sub-labelled `3a`/`3b`. Answers are per-line
  and constrained to four verbs: `approve` / `deny` / `pick <sub-label>` /
  `email: <address>` (the last a row-data correction, not a match decision). `deny
  all` is accepted; a bare, unscoped `approve all` is refused — bulk approval must
  name its scope (`approve 1-4, 7`, or `approve all 6` restating the count), because a
  wrong bulk approve silently evaporates the true row exactly the way the original
  nine-directors bug did, one row at a time. A pending (unanswered) row is restated
  next turn, never defaulted. One bad line refuses the whole table (reusing
  `apply_match_decisions`' existing all-or-nothing guard) and the refusal names the
  offending line. No code change was required — the applier was already batch-shaped.
- Step 6 (the enriched preview) states explicitly that nothing has reached HubSpot
  yet, names every held row individually regardless of batch size, and reads as the
  actual decision point rather than a status update.
- Step 7 references `contact-upload/SKILL.md`'s own steps 6-10 by their exact heading
  text (confirmed against 37-RESEARCH.md §C.13) rather than duplicating their
  dispatch/report/retry/cleanup mechanics, restates the held rows from step 6 *after*
  the backend's own report, and hands `classified["auto_matched"]`'s object ids to
  `enrich-records` — covering the confirmed-MEDIUM-with-no-email bucket outcome
  explicitly.
- Step 8 renders the idempotent resume turn from §13(a): persist a `row_id → verdict`
  manifest as the batch proceeds, and on a later run report what was **skipped**
  rather than silently starting a smaller batch.
- `tests/test_enrich_before_ingest_skill_contract.py` (21 tests, up from 15) mirrors
  `test_enrich_skill_contract.py`'s structure and its `_normalized()` idiom:
  - The character-offset comparison and same-step-span exclusion for the two arming
    phrases (unchanged by the amendment).
  - Six new pins for the batched-table vocabulary: the four constrained verbs present
    literally; `deny all` offered; a regex adjacency pin asserting every occurrence of
    the literal phrase `approve all` is immediately followed by a digit (no bare
    occurrence anywhere in the file); the pending/restated/never-defaulted sentence
    present; the ambiguous-row-takes-only-`pick` sentence present; the
    whole-table-refusal-names-the-offending-line sentence present.
- `test_plugin_manifest.py` already globs `skills/*/SKILL.md` (widened by 28-05) and
  picks up `enrich-before-ingest` automatically — confirmed by reading it first, left
  unmodified.

## Task Commits

1. **Task 1: the skill — seven turns, two arms, one handoff** - `897f091` (feat)
2. **Task 2: pin the ordering and the two phrases as tests over the document** - `f7daecd` (test)
3. **Task 3 amendment: batched-table confirmation supersedes one-proposal-per-turn** - `6466d83` (fix), folding 37-CONTEXT.md's own amendment commit `9b0ca62` (docs, operator-authored, not this executor's)

## Files Created/Modified

- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — new skill, 8 numbered
  steps; step 3 rewritten in the amendment commit
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — new
  contract test file, 15 tests at Task 2, 21 after the amendment

## Decisions Made

See `key-decisions` in the frontmatter — step 1's phrase-free two-arm preview, the
three-consequences paragraph's placement inside step 7, the resume turn as its own
numbered step 8, `queue_handoff_ids` staying uncalled per 37-07's explicit instruction,
the batched-table amendment's exact vocabulary and scope-naming rule, and why no code
changed.

## Deviations from Plan

None — Tasks 1 and 2 executed exactly as written. Task 3's checkpoint returned a
correction rather than a bare approval; that correction is recorded as its own
37-CONTEXT.md §13 amendment (operator-authored, commit `9b0ca62`) and folded into this
plan's own Task 3 rather than treated as an out-of-plan deviation, since the plan's own
checkpoint protocol is exactly what produced it.

One correction made during Task 2's own build (before that task's commit, so not a
deviation from plan intent): the first draft of `test_both_arming_phrases_appear` and
the same-step test searched raw (unnormalized) text, which failed against `"arm the
enrichment"` because that phrase wraps across a markdown line break inside its bold
marker (`**"arm the\n   enrichment"**`). Fixed by normalizing before the substring
check — mirroring exactly why `test_enrich_skill_contract.py`'s own `_normalized()`
helper exists in the first place.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 2, ordering test** — physically swapped the step-6 and step-7 blocks:

```
AssertionError: the ingest-arm heading (character offset 8691) must appear strictly
after the enriched-preview heading (character offset 12087) -- the enriched preview
must land in the operator's turn before the ingest arm can be spoken
assert 8691 > 12087
```

**Task 2, same-step test** — inserted a second arming phrase into step 5's own span:

```
AssertionError: numbered step 5 contains both arming phrases -- they must be spoken in
different turns, never both granted by one step's own text
assert not (True and True)
```

**Task 3 amendment, six new pins** — each mutated independently, run alone, and
restored before the next:

1. Renamed `pick <sub-label>` to `select <sub-label>`:
   `AssertionError: expected the constrained verb '\`<label>. pick <sub-label>\`' in
   SKILL.md`
2. Renamed `deny all` to `decline all`: `AssertionError: assert '\`deny all\`' in
   ...` (phrase absent).
3. Replaced the scoped `approve all 6` example with an unscoped `approve all`:
   `AssertionError: found a bare 'approve all' with no trailing count/scope at
   character offset 7247: ' can also just say \`approve all\` if that is easier '`
4. Replaced the pending/restated sentence with "is skipped for now":
   `AssertionError: assert 'restated' in ...` (phrase absent).
5. Loosened "takes only `pick`" to "can be answered with pick":
   `AssertionError: assert 'takes only' in ...` (phrase absent).
6. Replaced the whole-table-refusal sentence with "is skipped and everything else is
   applied normally": `AssertionError: assert 'refuses the whole table' in ...`
   (phrase absent).

All six mutations were applied and reverted one at a time via a scratch-directory
backup (not `git checkout --`, since the amendment was still uncommitted at that
point); after all six, `diff` against the scratch backup confirmed the restored file
was byte-identical before this commit.

## Issues Encountered

None beyond the wrap-related normalization fix documented above under Deviations.

## User Setup Required

None — no external service configuration required.

## Suite Counts (final, after the amendment)

- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q` →
  **21 passed** (15 at Task 2, +6 for the amendment).
- `operator-claude-plugin/tests/ -q` → **1238 passed, 5 skipped** (baseline post-37-07:
  1215/5; Task 2 landed at 1232/5; the amendment's 6 new tests bring it to 1238/5).
- repo-root `-q` → **2157 passed, 6 skipped** (baseline: 2134/6; final: +23, all in
  this plan's own test files).
- `node --test tests/n8n/*.test.mjs` → **621 pass**, unchanged throughout.
- `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0** for every file.
- `ls operator-claude-plugin/commands` → does not exist, as required.

## Next Phase Readiness

Plan complete. Task 3's checkpoint returned a design amendment (batched-table
confirmation), which was folded into the skill and its contract test, red-checked, and
committed. All suites are at or above baseline. No blockers for 37-09.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

`operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` and
`operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` verified
present on disk; commit hashes `897f091`, `f7daecd`, and `6466d83` verified present in
`git log --oneline --all`.
