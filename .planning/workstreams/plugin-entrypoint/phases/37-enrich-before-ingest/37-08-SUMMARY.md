---
phase: 37-enrich-before-ingest
plan: 08
subsystem: skill
tags: [skill-contract, arming, ordering-test, checkpoint-pending]

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
  - "skills/enrich-before-ingest/SKILL.md — the seven-turn operator entry point rendering 37-CONTEXT.md sec 5"
  - "tests/test_enrich_before_ingest_skill_contract.py — the character-offset ordering pin and the same-step phrase-separation pin, both red-checked"
affects: [37-09]

actuals:
  tokens: 6045
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Character-offset heading-order pin: two literal, line-anchored heading substrings located by text.find(), non-negativity asserted before comparison, failure message names both offsets"
    - "Numbered-step-span split (regex on `^N. **`) + per-span phrase containment check, reusing the analog file's _normalized() idiom so a markdown reflow cannot hide or fabricate a phrase collision"

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

requirements-completed: [DISPATCH-03, PREVIEW-01]

coverage:
  - id: D1
    description: "skills/enrich-before-ingest/SKILL.md exists with parseable frontmatter (name=enrich-before-ingest, non-empty description naming the slash form and firing on natural phrasing), renders the seven-turn sequence from 37-CONTEXT.md sec 5 end to end, states the two-arm warning up front in step 1, names all four match groups, references contact-upload/SKILL.md steps 6-10 by heading text without reproducing their bodies, and contains no `lastmodifieddate` string anywhere."
    requirement: PREVIEW-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_the_skill_exists_with_parseable_frontmatter_carrying_name_and_description, ::test_the_description_fires_on_natural_operator_phrasing_and_names_the_slash_form, ::test_the_skill_names_all_four_match_groups, ::test_the_skill_references_contact_upload_steps_six_through_ten_by_heading_text, ::test_the_skill_does_not_reproduce_contact_upload_step_bodies, ::test_no_last_modified_field_is_implied_on_the_match_candidate_endpoint"
        status: pass
    human_judgment: false
  - id: D2
    description: "The two arming phrases (\"arm the enrichment\", \"arm the upload\") both appear, no combined or third phrase appears against a checked list of plausible spellings, the ingest-arm heading's character offset is strictly greater than the enriched-preview heading's, and no single numbered step contains both phrases. All four pins were red-checked by physically breaking the property they guard: swapping the step-6/step-7 blocks made the ordering test fail naming both offsets (ingest 8691 vs preview 12087); injecting the upload phrase into step 5's span made the same-step test fail naming step 5. Both mutations were reverted via `git checkout --` (the file was already committed) and full suites re-verified green."
    requirement: DISPATCH-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py::test_both_arming_phrases_appear, ::test_no_combined_or_third_arming_phrase_appears, ::test_the_ingest_arm_heading_is_strictly_after_the_enriched_preview_heading, ::test_the_two_arming_phrases_never_share_a_numbered_step"
        status: pass
    human_judgment: false
  - id: D3
    description: "An operator reading skills/enrich-before-ingest/SKILL.md top to bottom experiences the two-arm warning as a reason (not boilerplate), the enriched preview as a genuine decision point, held rows named as people rather than a count, and the contact-upload steps 6-10 handoff as findable against the real file. This is Task 3's own checkpoint and is not machine-verifiable."
    verification: []
    human_judgment: true
    rationale: "The plan's own Task 3 is a checkpoint:human-verify with gate=\"blocking\" specifically because prose quality — does the warning read as a reason, does the preview feel like a decision point, are held rows nameable — is a judgment the automated contract tests cannot make. This plan is autonomous: false; per explicit instruction the executor stops here rather than self-approving."

duration: ~30min (Tasks 1-2)
completed: 2026-08-05
status: checkpoint-pending
---

# Phase 37 Plan 08: The Enrich-Before-Ingest Skill — Two Arms, Pinned by Offset Summary

**`skills/enrich-before-ingest/SKILL.md` renders the seven-turn flow from 37-CONTEXT.md §5 (target, unarmed match, one-proposal-per-turn confirmation, cost preview, "arm the enrichment", the enriched preview, "arm the upload", plus a resume turn), and its contract test pins the two arming phrases' separation as a character-offset comparison and a numbered-step-span exclusion — both observed failing before being trusted green. Task 3's human-verify checkpoint is open; this plan stops here per its own `autonomous: false`.**

## Performance

- **Duration:** ~30 min (Tasks 1-2)
- **Completed:** 2026-08-05
- **Tasks:** 2/3 (Task 3 is an open checkpoint, not executed by this agent)
- **Files modified:** 2 (both created)

## Accomplishments

- `skills/enrich-before-ingest/SKILL.md` (14.3 KB, 8 numbered steps) built on the exact
  function signatures 37-01 through 37-07 shipped — read directly from source, not
  reconstructed from the plan text: `preingest.rows_from_table`, `build_rows_spec`,
  `match_batch`, `classify_matches`, `apply_match_decisions`, `DECLINE_MATCH`,
  `merge_enriched`, `render_enriched_preview`; `chunking.chunk_ceiling(key=)`,
  `plan_chunks`, `dispatch_plan`; `extraction.hold_emailless`, `write_dispatch_csv`;
  `run_manifest.save/load/rows_to_resume`.
- Step 1 states the target and previews the two-arm design generically, without
  quoting either literal phrase — the phrases are named only inside their own arming
  steps (5 and 7), which is what keeps the contract's same-step exclusion a real
  property of the document.
- Step 2 reports exactly four match groups by name (auto-matched, proposed, unmatched,
  unchecked) and states the search itself needs no arming — it spends no credit and
  writes nothing.
- Step 3 shows the six `CANDIDATE_KEYS` fields per proposed candidate
  (`hs_object_id`, `firstname`, `lastname`, `email`, `jobtitle`, `company`) and states
  there is no modification-timestamp field on this endpoint at all — the literal
  string `lastmodifieddate` appears nowhere in the file.
- Step 6 (the enriched preview) states explicitly that nothing has reached HubSpot
  yet, names every held row individually regardless of batch size, and reads as the
  actual decision point rather than a status update — this is the read Task 3's
  checkpoint exists to verify against a real human.
- Step 7 references `contact-upload/SKILL.md`'s own steps 6-10 by their exact heading
  text (confirmed against 37-RESEARCH.md §C.13) rather than duplicating their
  dispatch/report/retry/cleanup mechanics, restates the held rows from step 6 *after*
  the backend's own report (they never entered this dispatch, so nothing in that
  report mentions them), and hands `classified["auto_matched"]`'s object ids to
  `enrich-records` — covering the confirmed-MEDIUM-with-no-email bucket outcome
  explicitly.
- Step 8 renders the idempotent resume turn from §13(a): persist a `row_id → verdict`
  manifest as the batch proceeds, and on a later run report what was **skipped**
  rather than silently starting a smaller batch.
- `tests/test_enrich_before_ingest_skill_contract.py` (15 tests) mirrors
  `test_enrich_skill_contract.py`'s structure and its `_normalized()` idiom. The two
  load-bearing pins:
  - A character-offset comparison locates the enriched-preview heading and the
    ingest-arm heading by literal substring, asserts neither `find()` returned `-1`
    before comparing, and asserts the ingest-arm offset is strictly greater.
  - A numbered-step-span split (regex on `^N. **`, normalized per-span text) asserts
    no single step's span contains both quoted arming phrases.
- `test_plugin_manifest.py` already globs `skills/*/SKILL.md` (widened by 28-05) —
  confirmed by reading it before touching anything, and it picks up
  `enrich-before-ingest` automatically. Left unmodified, per the plan's own
  instruction to check first rather than widen a file another workstream might hold.

## Task Commits

1. **Task 1: the skill — seven turns, two arms, one handoff** - `897f091` (feat)
2. **Task 2: pin the ordering and the two phrases as tests over the document** - `f7daecd` (test)

_No plan-metadata commit yet — Task 3's checkpoint is open; the orchestrator resolves
STATE.md/ROADMAP.md/REQUIREMENTS.md and the final metadata commit once it is answered._

## Files Created/Modified

- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — new skill, 8 numbered
  steps
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — new
  contract test file, 15 tests

## Decisions Made

See `key-decisions` in the frontmatter — step 1's phrase-free two-arm preview, the
three-consequences paragraph's placement inside step 7 (not a trailing unnumbered
section), the resume turn as its own numbered step 8, and `queue_handoff_ids` staying
uncalled per 37-07's explicit instruction.

## Deviations from Plan

None — both tasks executed exactly as written. One correction made during Task 2's own
build, not a deviation from the plan's intent: the first draft of
`test_both_arming_phrases_appear` and the same-step test searched raw (unnormalized)
text, which failed against `"arm the enrichment"` because that phrase wraps across a
markdown line break inside its bold marker (`**"arm the\n   enrichment"**`). Fixed by
normalizing before the substring check — mirroring exactly why
`test_enrich_skill_contract.py`'s own `_normalized()` helper exists in the first place
(a reflow must not fail a wording assertion). Not logged as a Rule 1/2/3 deviation
because it surfaced and was corrected before the task's own commit, not after.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 2, ordering test** — physically swapped the step-6 and step-7 blocks (body
text, including their own numbered headings) via a scripted string swap, leaving step
8 untouched:

```
AssertionError: the ingest-arm heading (character offset 8691) must appear strictly
after the enriched-preview heading (character offset 12087) -- the enriched preview
must land in the operator's turn before the ingest arm can be spoken
assert 8691 > 12087
```

Restored via `git checkout -- operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`
(the file was already committed in Task 1); full 15-test file re-verified green
immediately after.

**Task 2, same-step test** — inserted `Also say "arm the upload" right here, in this
same step.` immediately after step 5's own heading, putting both phrases inside step
5's span:

```
AssertionError: numbered step 5 contains both arming phrases -- they must be spoken in
different turns, never both granted by one step's own text
assert not (True and True)
```

Restored the same way; full 15-test file re-verified green immediately after.

## Issues Encountered

None beyond the wrap-related normalization fix documented above under Deviations.

## User Setup Required

None — no external service configuration required.

## Suite Counts (Tasks 1-2, before Task 3's checkpoint)

- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
  operator-claude-plugin/tests/test_enrich_skill_contract.py
  operator-claude-plugin/tests/test_plugin_manifest.py -q` → **45 passed** (15 new +
  8 existing enrich-records + 22 plugin-manifest, the latter's parametrized cases
  including the new skill via its existing glob).
- `operator-claude-plugin/tests/ -q` → **1232 passed, 5 skipped** (baseline post-37-07:
  1215/5; +17 = 15 new file + 2 new parametrized `test_plugin_manifest.py` cases for
  the new skill).
- repo-root `-q` → **2151 passed, 6 skipped** (baseline: 2134/6; +17, unaffected
  elsewhere).
- `node --test tests/n8n/*.test.mjs` → **621 pass**, unchanged.
- `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0** for every file.
- `ls operator-claude-plugin/commands` → does not exist, as required.

## Next Phase Readiness

**Blocked on Task 3's checkpoint** — `checkpoint:human-verify`, `gate="blocking"`. This
plan is `autonomous: false`; per explicit instruction this executor stops here and
returns the structured checkpoint state rather than self-approving, even though
`AUTO_CFG`/`AUTO_CHAIN` may otherwise auto-approve a plain `human-verify` checkpoint.

A human needs to read `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` top
to bottom and judge the four things the automated tests cannot: whether the step-1
two-arm warning reads as a reason rather than boilerplate, whether step 6's enriched
preview feels like the actual decision point, whether the held-row wording names people
rather than counts, and whether the step-7 handoff to `contact-upload/SKILL.md`'s steps
6-10 is findable against the real file. Then re-run:

```
.venv/bin/python -m pytest operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q
```

Once approved, the orchestrator (or a continuation agent) should run the state/roadmap
updates and final metadata commit this executor deliberately skipped.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05 (Tasks 1-2; Task 3 checkpoint open)*

## Self-Check: PASSED

`operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` and
`operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` verified
present on disk; commit hashes `897f091` and `f7daecd` verified present in
`git log --oneline --all`.
