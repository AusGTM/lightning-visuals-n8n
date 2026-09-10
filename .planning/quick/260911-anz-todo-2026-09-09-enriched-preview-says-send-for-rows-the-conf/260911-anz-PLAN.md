---
phase: quick-260911-anz
plan: 01
type: execute
wave: 2
depends_on: ["260911-anx"]
files_modified:
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/tests/test_preingest_preview.py
  - operator-claude-plugin/tests/test_autonomy_switch_prose.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - .planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md
  - .planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md
files_deleted:
  - .planning/todos/pending/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md
autonomous: true

must_haves:
  truths:
    - "The three-row UAT Round B shape (run `2bc3617b`) — two rows the waterfall gave an email, one it did not, all three unmatched — renders `send_count == 0` and three HELD rows, every one carrying `confidence.HOLD_NO_MATCH`, including the row that has no email (confidence is asked first)."
    - "`render_enriched_preview`'s own docstring names `partition_for_ingest` as the source of the SEND/HELD split. No sentence in it claims a second, different sole source."
    - "`test_preingest_preview.py`'s module docstring names the same one source as the code it tests."
    - "`enrich-before-ingest/SKILL.md` states the design fact the incident exposed: under autonomy a new person is never created without the operator's end-of-run approval, because a row with no HubSpot match is by definition unconfident and every create is such a row."
    - "`enrich-before-ingest/SKILL.md` still contains neither of the two substrings `test_autonomy_switch_prose.py` forbids over that file — the new sentence does not smuggle either in."
    - "The pending todo is closed with a `## Resolved` section recording that the code fix landed in Phase 70 Plan 06 (D-70-11, commit `40874cd8`) and this task closed the residuals; a NEW pending todo records the one thing found still missing (no plugin-side path turns an approved held row into a sent row)."
  artifacts:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preingest_preview.py
    - operator-claude-plugin/tests/test_autonomy_switch_prose.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - .planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md
    - .planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md
  key_links:
    - "`render_enriched_preview` -> `partition_for_ingest` -> `confidence.assess` then `extraction.hold_emailless`, in that order — the ONE verdict, already wired by D-70-11. This task changes no line of that chain."
    - "`test_autonomy_switch_prose.py` is the prose home for `enrich-before-ingest/SKILL.md`; its forbidden-substring test already reads the whole file, so the new sentence is checked by a test that exists rather than by a reviewer's eye."
    - "`README.md` L150-154 is the wording template for the SKILL sentence — one design fact, stated in two places, not two differing statements."
---

<objective>
Close the residuals of todo `2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds`.

**Read this before touching `preingest.py`: the behavioural fix ALREADY SHIPPED.** Phase 70
Plan 06 (D-70-11, commit `40874cd8`) folded `confidence.assess` into the preview's row
verdict by routing both the preview and the dispatch step through one new function,
`preingest.partition_for_ingest`. The todo was never moved out of `pending/`, so it reads as
open. Do NOT re-implement the fold, do not add a second predicate, do not touch
`confidence.py`.

What is genuinely left, verified by reading the shipped code and running the suite:

1. **Two stale sentences that still assert the defect.** `render_enriched_preview`'s docstring
   ends by claiming a different function is the sole source of the SEND/HELD split — four
   lines below the D-70-11 paragraph saying the opposite. `test_preingest_preview.py`'s module
   docstring makes the same stale claim about its own weight-bearing assertion. Two verdicts
   for one row, surviving in prose.
2. **The named Round B shape is not pinned.** A single-row version exists
   (`test_a_no_match_row_with_a_found_email_renders_held_never_sendable`); the three-row shape
   the incident actually produced — `send_count: 2` where the gate allowed 0 — is not.
3. **The SKILL does not carry the design fact.** The todo asked for it in "the SKILL and
   README"; `README.md` L150-154 has it, `enrich-before-ingest/SKILL.md` does not.
4. **One thing found missing while tracing.** The todo's Fix presumes SEND when "the operator
   has approved the hold in the end-of-run pass". There is no such path in the plugin:
   `held_queue.py` has no approve function, `partition_for_ingest` has no approved-rows
   input, and the SKILL documents the review vocabulary with no block that applies it and
   sends. Do NOT invent one here — an `approved_row_ids` parameter with no caller is dead
   plumbing. Record it as its own todo and state the current shape honestly in the SKILL.

Purpose: the operator reads one verdict per row, and every sentence around that code says the
same thing the code does.
Output: two corrected docstrings, one regression test pinning the named shape, one SKILL
sentence with a test that bites, one todo closed and one raised.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/todos/pending/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md
@operator-claude-plugin/scripts/preingest.py
@operator-claude-plugin/tests/test_preingest_preview.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: One source named in the code's own prose, and the Round B shape pinned</name>
  <files>operator-claude-plugin/scripts/preingest.py, operator-claude-plugin/tests/test_preingest_preview.py</files>
  <read_first>
    - `operator-claude-plugin/scripts/preingest.py` lines 1031-1078 (`partition_for_ingest`, the
      shipped D-70-11 fold — read it so you can see there is nothing to add) and lines 1079-1105
      (`render_enriched_preview`'s docstring, where the stale sentence lives).
    - `operator-claude-plugin/tests/test_preingest_preview.py` lines 1-10 (the stale module
      docstring) and lines 351-445 (the D-70-11 section, its `_answer` helper, and the
      single-row neighbour your new test sits beside).
    - `.planning/uat/UAT-autonomous-batch-2026-09-09.md` lines 53-75 — the recorded Round B
      observation this test reproduces. Greg and Barry got emails from the waterfall, Nardine
      got seniority only and no email, all three unmatched, `SENDABLE=0`.
  </read_first>
  <behavior>
    - New test, the recorded Round B shape: three rows, none matched in HubSpot (each answer
      carries match tier `none`), two of them given an email by the merge and one not.
      Asserts `send_count == 0`, `held_count == 3`, every held row's `hold_code` is
      `confidence.HOLD_NO_MATCH` — the emailless row included, because the confidence check
      runs before the email check — and that `send_count`/`held_count` equal what
      `partition_for_ingest` returns for the same rows and responses.
    - Every pre-existing test in the file keeps passing unmodified.
  </behavior>
  <action>
    Correct the last sentence of `render_enriched_preview`'s docstring so it names
    `partition_for_ingest` as the source of the SEND/HELD split, matching the D-70-11
    paragraph directly above it. Keep the T-38-01 point it was making — that an unanswered row
    is partitioned out before the gate is ever asked — and keep it one sentence; this is a
    correction, not an expansion. Leave every other line of the docstring alone, and leave the
    two legitimate mentions of `extraction.hold_emailless` inside `partition_for_ingest`
    (its own body and its own docstring) untouched — that call is real and still runs second.

    Correct `test_preingest_preview.py`'s module docstring the same way: its weight-bearing
    assertion is now that the preview renders exactly what `partition_for_ingest` returns, the
    same function the dispatch step calls.

    Add the Round B regression test at the end of the file's D-70-11 section, using the
    section's existing `_answer` helper and `preingest.MergeResult` — no new helper, no new
    fixture. Name the run in the test docstring and name what the operator actually read: a
    send count of two against a gate that allowed none. Use plausible source rows rather than
    the real people's contact details; the shape is what is being pinned, not the person.

    This test is GREEN on arrival — the code is already correct — so prove it bites rather
    than asserting that it does. Temporarily force `partition_for_ingest`'s per-row verdict to
    the confident branch (one line, inside that function, leaving its return shape and the
    email check untouched), which reproduces the incident exactly: two rows sendable, one held
    on the email with no hold code. Run the file, record the observed failure in the summary,
    then restore the line and re-run to green. Do not commit the perturbation.

    Expect several existing tests in the file to go RED under that perturbation too — the
    single-row neighbour and the two `partition_for_ingest` tests all discriminate on it. That
    is fine and expected; do not "fix" them. What this new test adds is the RECORDED shape, as
    the task asked: three rows, a send count of two where the gate allowed none. Worth noting
    in the summary: `test_the_previews_send_count_is_the_dispatch_sendable_count_itself` stays
    GREEN under the perturbation, because both sides of its equality call the same function —
    which is why an equality test alone was never going to pin this incident.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_preview.py operator-claude-plugin/tests/test_preingest_merge.py -q</automated>
    <automated>.venv/bin/python -c "import sys; sys.path.insert(0, 'operator-claude-plugin/scripts'); import preingest; d = preingest.render_enriched_preview.__doc__; assert d.count('partition_for_ingest') >= 2, d"</automated>
  </verify>
  <done>The Round B test passes and was observed failing under the perturbation described above; both docstrings name `partition_for_ingest`; `test_preingest_preview.py` and `test_preingest_merge.py` are fully green with no pre-existing test modified.</done>
</task>

<task type="auto">
  <name>Task 2: The design fact in the SKILL, pinned — and the missing approval path recorded</name>
  <files>operator-claude-plugin/skills/enrich-before-ingest/SKILL.md, operator-claude-plugin/tests/test_autonomy_switch_prose.py, .planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md, .planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md</files>
  <read_first>
    - `operator-claude-plugin/README.md` lines 148-155 — the design fact as already stated
      there. This is the wording template; the SKILL states the same fact, not a second
      differing one.
    - `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` lines 745-760 — the
      paragraph ending "Held rows do not join the `sendable`/`send` set below; they are
      collected, and shown ONCE, in the end-of-run review pass", and the review-vocabulary
      paragraph after it. The new sentence belongs here.
    - `operator-claude-plugin/tests/test_autonomy_switch_prose.py` lines 44-70 (`TARGETS`,
      `PLUGIN_ROOT`, `SKILLS_DIR`) and lines 206-222 (the forbidden-substring test — read it
      to learn the two words this SKILL file may not contain, and note it is parametrized over
      all four batch skills while your new test must not be).
    - `.planning/todos/completed/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md`
      — the closure convention: frontmatter kept as-is, a `## Resolved <date>` section appended.
  </read_first>
  <action>
    Add one short paragraph to `enrich-before-ingest/SKILL.md`, immediately after the
    "Held rows do not join the `sendable`/`send` set" sentence, stating the design fact the
    incident exposed: under autonomy a new person is never created without the operator's
    end-of-run approval — a row with no HubSpot match is by definition a row the system is not
    confident about, so it is held, and every create is such a row. Follow it with one honest
    sentence naming the current shape found while closing this todo, and claim NOTHING beyond
    it: nothing in this flow turns an approved held row into a send today, and how a new person
    reaches HubSpot once approved is open — cite the new todo file by name. Do NOT write that
    the create happens on a later pass; no such path was found, and step 8's resume re-includes
    a held row only when it gains an email, which does not make an unmatched row matched. Do not
    soften either sentence into a promise the code does not keep.

    **Hard constraint on that paragraph's wording.** `test_autonomy_switch_prose.py`'s
    forbidden-substring test reads this whole file and fails on either of two words it names;
    one of them is the word this repo uses for a match's strength, which the surrounding
    machinery is full of. Say "a row with no HubSpot match" and "unconfident" — never that
    word, and never `icp`. Run that test file before you consider the edit done.

    Pin the sentence with ONE new, NON-parametrized test in `test_autonomy_switch_prose.py`
    asserting that both `enrich-before-ingest/SKILL.md` and `README.md` carry the design fact.
    Match on short clauses genuinely common to both files, not a whole paragraph and not a
    clause that only one of them has: the README addresses the operator directly ("without
    **your** end-of-run approval") while the SKILL addresses Claude and will say "the
    operator's", so a possessive in the matched substring passes on one file and fails on the
    other. Two independent `in` checks over each file — the never-created clause and the
    end-of-run-approval clause — is enough. Write the
    assertion FIRST and observe it RED against the unedited SKILL before adding the paragraph
    — the SKILL genuinely lacks the sentence today, so this is a real RED, not a staged one.
    Do not add the assertion to any existing parametrized test: the other three batch skills
    do not create people and must not be required to say this.

    Close the todo: `git mv` the pending file to `.planning/todos/completed/` and append a
    `## Resolved 2026-09-11` section recording that the behavioural fold landed in Phase 70
    Plan 06 (D-70-11, commit `40874cd8`), that this task closed the two stale docstrings, added
    the Round B pin, and stated the design fact in the SKILL, and that the Fix's
    approved-hold branch is NOT implemented and was raised separately rather than invented.

    Raise that separate todo at
    `.planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md`,
    same frontmatter shape as its neighbours (`created`, `updated`, `title`, `area:
    operator-plugin`, `severity: major`, `files:` naming `held_queue.py`, `preingest.py` and
    `enrich-before-ingest/SKILL.md`). Record the evidence exactly as found: `held_queue.py`
    exposes no approve verb, `partition_for_ingest` takes no approved-rows input, the SKILL
    documents the approve/deny/pick vocabulary with no block that applies it and dispatches,
    and the consequence — **in the `enrich-before-ingest` flow specifically** — a row with no
    HubSpot match has no documented route to becoming a create, which the 2026-09-09 UAT
    recorded as "by design" without the design existing in code. Scope the claim to that flow
    and say why: `partition_for_ingest` has exactly one SKILL caller. `suggestion-declines`
    reaches its dispatch through `extraction.hold_emailless` alone and `suggest-contacts`
    through `suggest_contacts.partition_for_dispatch` — neither consults the confidence
    verdict, so neither is described by this todo. Verify that with a grep over
    `operator-claude-plugin/skills/*/SKILL.md` before writing the sentence rather than copying
    this claim on trust. State plainly that this task deliberately did not build the missing
    path.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_autonomy_switch_prose.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q</automated>
    <automated>test -f .planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md && test -f .planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md && test ! -e .planning/todos/pending/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md</automated>
  </verify>
  <done>The SKILL carries the design fact; the new non-parametrized prose test was observed RED before the edit and passes after; the forbidden-substring test still passes over the edited SKILL; the todo is in `completed/` with a `## Resolved` section and the new todo exists in `pending/`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator -> preview -> HubSpot write grant | The preview is the display the operator's yes is given against. A display that overstates what will be written is how consent gets taken for a thing that does not happen — the original incident. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-anz-01 | Repudiation | `render_enriched_preview` docstring / test docstring | medium | mitigate | Correct both to name `partition_for_ingest`; a future reader who trusts the stale sentence is one edit away from restoring the second predicate. |
| T-anz-02 | Information disclosure | new Round B regression test | low | mitigate | Use plausible substitute rows, not the real contacts' names and addresses from the UAT record — the shape is what is pinned. |
| T-anz-03 | Tampering | `partition_for_ingest` / `confidence.py` | high | accept | Not touched by this plan at all. No hold code is added, no threshold moves, `confidence.ALL_HOLD_CODES` stays closed; the perturbation in Task 1 is temporary, uncommitted, and re-verified green after restore. |

No package-manager install runs in this plan, so no package-legitimacy gate applies.
</threat_model>

<verification>
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — full plugin suite green, no
  regression against the pre-task baseline count.
- `git diff --stat` shows no change under `n8n/`, `scripts/build_cloud_workflows.py`, or
  `operator-claude-plugin/scripts/confidence.py`.
- Nothing is deployed, nothing is armed, no live call of any kind is made.
</verification>

<success_criteria>
- The Round B shape (`send_count == 0`, three HELD, all `HOLD_NO_MATCH`) is pinned by a test
  that was observed failing under the pre-D-70-11 predicate.
- No sentence in `preingest.py` or `test_preingest_preview.py` names a source of the SEND/HELD
  split other than `partition_for_ingest`.
- The SKILL states the design fact, a test bites on it, and the forbidden-substring guard still
  passes over the file.
- One todo closed with its record, one todo raised for the approval path this plan deliberately
  did not build.
</success_criteria>

<output>
Create `.planning/quick/260911-anz-todo-2026-09-09-enriched-preview-says-send-for-rows-the-conf/260911-anz-SUMMARY.md` when done.
</output>
