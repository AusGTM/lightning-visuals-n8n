---
phase: quick-260911-anz
plan: 01
subsystem: operator-claude-plugin
tags: [preingest, confidence, docs-prose, todo-cleanup]
status: complete
dependency-graph:
  requires: ["260911-anx"]
  provides: ["partition_for_ingest docstrings match its D-70-11 behaviour", "Round B regression pin", "enrich-before-ingest design-fact sentence"]
  affects: ["operator-claude-plugin/scripts/preingest.py", "operator-claude-plugin/skills/enrich-before-ingest/SKILL.md"]
tech-stack:
  added: []
  patterns: ["prose corrected to match already-shipped code, not re-implemented"]
key-files:
  created:
    - .planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md
  modified:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preingest_preview.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_autonomy_switch_prose.py
    - .planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md
  deleted:
    - .planning/todos/pending/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md
decisions:
  - "Did not re-implement any fold — D-70-11 (commit 40874cd8) already routes both the preview and dispatch through partition_for_ingest; this task only corrected stale prose and pinned the shape."
  - "Did not build the approved-hold-to-send path the original todo's Fix presumed exists — traced held_queue.py, partition_for_ingest, and the SKILL and found no such path, so raised it as a separate todo instead of inventing an approved_row_ids parameter with no caller."
metrics:
  duration: ~35min
  completed: 2026-09-11
actuals:
  tokens: 42000
  tasks: 2
  commits: 2
plan_head_before: b5136969~1
---

# Quick 260911-anz: Correct stale SEND/HELD prose, pin the Round B incident shape, state the never-created-without-approval design fact

Corrected two docstrings that still claimed `extraction.hold_emailless` was the sole source of
the preview's SEND/HELD split — four lines below the D-70-11 paragraph in the same file saying
the fold already routes through `partition_for_ingest`. Added a regression test pinning the
exact UAT Round B incident shape (run `2bc3617b`: three unmatched rows, two the waterfall gave
an email, one not, all held `HOLD_NO_MATCH`, `send_count == 0`), verified to actually bite by
temporarily forcing `partition_for_ingest`'s confident branch and observing the incident
reproduce (`send_count == 2`) before restoring. Added the design fact — a new person is never
created without the operator's end-of-run approval — to `enrich-before-ingest/SKILL.md`,
pinned by a new non-parametrized prose test. Closed the originating todo with a `## Resolved`
record and raised a new todo for the one thing found genuinely missing while tracing: no
plugin-side path turns an approved held row into a send.

## What Was Built

**Task 1 — one source named in the code's own prose, Round B pinned.**
- `preingest.render_enriched_preview`'s docstring: corrected its closing sentence from
  "`hold_emailless` remains the sole source of the SEND/HELD split" to
  "`partition_for_ingest` remains the sole source..." — matching the D-70-11 paragraph four
  lines above it. The T-38-01 point (an unanswered row is partitioned out before the gate is
  asked) is preserved verbatim.
- `test_preingest_preview.py`'s module docstring: corrected the same way — the weight-bearing
  assertion is now stated as "the preview renders exactly what `partition_for_ingest` returns."
- Added `test_round_b_shape_send_count_zero_all_three_held_no_match`, placed at the end of the
  file's D-70-11 section, reusing the section's existing `_answer` helper and
  `preingest.MergeResult` (no new helper, no new fixture). Uses plausible substitute rows
  rather than the real UAT contacts' details. Asserts `send_count == 0`, `held_count == 3`,
  every held row's `hold_code == confidence.HOLD_NO_MATCH`, and that both counts equal what
  `partition_for_ingest` independently returns for the same rows/responses.
- Proved the test bites: temporarily changed one line inside `partition_for_ingest`
  (`if verdict.verdict == confidence.CONFIDENT:` → `if True:`) to force every row through the
  confident branch, ran the file, and observed 4 failures — the new Round B test failed exactly
  as the incident did (`assert 2 == 0` on send_count), plus three pre-existing tests that also
  discriminate on the same predicate. Restored the line and re-ran: 88/88 passing. The
  perturbation was never committed (verified via `git diff` before staging).

**Task 2 — the design fact in the SKILL, the missing approval path recorded.**
- Added one paragraph to `enrich-before-ingest/SKILL.md`, immediately after the "Held rows do
  not join the `sendable`/`send` set below" sentence: states that a new person is never created
  without the operator's end-of-run approval (because a no-HubSpot-match row is by definition
  unconfident and every create is such a row, D-70-11), then one honest sentence naming the gap
  found while tracing — no plugin path today turns an approved held row into a send — citing
  the new todo by name. Wording avoids the two substrings `test_autonomy_switch_prose.py`
  forbids (`icp`, `tier`) — uses "a row with no HubSpot match" and "unconfident" throughout.
- Added one new, non-parametrized test to `test_autonomy_switch_prose.py`,
  `test_enrich_before_ingest_and_readme_state_the_never_created_without_approval_fact`, matching
  two independent short clauses genuinely common to both `enrich-before-ingest/SKILL.md` and
  `README.md` ("is never created without" and "end-of-run approval") — deliberately not the
  possessive-bearing full sentence, since README says "your" and the SKILL says "the operator's".
  Observed RED against the unedited SKILL first (`AssertionError: SKILL.md must state the
  never-created-without-approval clause`), then green after the paragraph was added. Not added
  to the existing parametrized `TARGETS` loop — the other three batch skills do not create
  people and must not be required to say this.
- Closed `.planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-
  confidence-gate-holds.md` (git mv from `pending/`) with an appended `## Resolved 2026-09-11`
  section recording that the behavioural fold landed in Phase 70 Plan 06 (D-70-11, commit
  `40874cd8`), that this task closed the two stale docstrings and added the Round B pin and
  the SKILL sentence, and that the Fix's approved-hold branch was found unimplemented and
  raised separately rather than invented.
- Raised `.planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-
  sent-row.md`, recording the traced evidence (`held_queue.py` has no approve verb,
  `partition_for_ingest` takes no approved-rows input, the SKILL documents the review
  vocabulary with no block that applies it and dispatches) and scoping the claim to the
  `enrich-before-ingest` flow specifically — verified by grep that `suggestion-declines`
  dispatches through `extraction.hold_emailless` alone and `suggest-contacts` through
  `suggest_contacts.partition_for_dispatch`, neither of which consults the confidence verdict.

## Deviations from Plan

None — plan executed exactly as written. The plan itself flagged one expectation that did not
hold under observation, worth recording here rather than silently: it predicted
`test_the_previews_send_count_is_the_dispatch_sendable_count_itself` would "stay GREEN under
the perturbation, because both sides of its equality call the same function." Observed
otherwise — that test's assertion is a three-way chain
(`preview_data["send_count"] == len(sendable) == 1`), and while both sides of the equality DID
move together (both became `2`), the trailing hardcoded literal (`== 1`) made the whole chain
fail (`assert 2 == 1`). This is within the plan's own explicit allowance ("Expect several
existing tests in the file to go RED under that perturbation too... That is fine and expected;
do not 'fix' them") — recorded as an observation, not treated as a defect, and no test was
modified to "fix" it.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/preingest.py` — FOUND
- `operator-claude-plugin/tests/test_preingest_preview.py` — FOUND
- `operator-claude-plugin/tests/test_autonomy_switch_prose.py` — FOUND
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — FOUND
- `.planning/todos/completed/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md` — FOUND
- `.planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md` — FOUND
- `.planning/todos/pending/2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md` — CONFIRMED ABSENT (git mv)
- commit `b5136969` — FOUND in `git log --oneline`
- commit `228745ef` — FOUND in `git log --oneline`
- `operator-claude-plugin/tests -q` — 2884 passed, 5 skipped (full plugin suite)
- `git diff --stat` against `n8n/`, `scripts/build_cloud_workflows.py`,
  `operator-claude-plugin/scripts/confidence.py` — empty (no changes)
