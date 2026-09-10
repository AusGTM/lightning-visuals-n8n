---
created: 2026-09-09T03:40:00.000Z
updated: 2026-09-09
title: The enriched preview labels a row SEND while confidence.assess holds it — two verdicts for one row, the operator reads the wrong one
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/confidence.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
---

## Seen 2026-09-09, UAT Round B, run `2bc3617b094b4c939d57f38ff6704e3f`

`render_enriched_preview` marked Greg Purcell and Barry Milton `SEND` (email present after the
waterfall) while `confidence.assess` held all three unmatched rows `no_match`
(`HOLD_NO_MATCH`, D-61-03: no existing record to confirm against). Result: `send_count: 2`
in the preview, `SENDABLE=0` at dispatch, nothing ingested, and a preview that promised two
writes that were never going to happen. The preview does not consult the confidence verdict.

## Fix

One verdict per row on the preview: fold `confidence.assess` into `render_enriched_preview`'s
row verdict (HELD with the hold code and reason, SEND only when CONFIDENT or when the
operator has approved the hold in the end-of-run pass). Test: a row with tier `none` and a
found email renders HELD `no_match`, never SEND. Also decide and state, in the SKILL and
README, the design fact this exposed: under autonomy a NEW person is never created without
the operator's end-of-run approval, because a no-match row is by definition unconfident.

## Resolved 2026-09-11

The behavioural fold landed in Phase 70 Plan 06 (D-70-11, commit `40874cd8`):
`confidence.assess` is folded into one function, `preingest.partition_for_ingest`, called by
both `render_enriched_preview` and the dispatch step, so the preview's send count is the
dispatch's sendable count by construction. That commit never moved this file out of
`pending/`, so it kept reading as open.

Quick task 260911-anz closed the residuals found by re-reading the shipped code against this
todo:

- Two stale docstring sentences (`render_enriched_preview`'s own docstring and
  `test_preingest_preview.py`'s module docstring) still named `extraction.hold_emailless` as
  the sole source of the SEND/HELD split, four lines below the D-70-11 paragraph saying the
  opposite. Both corrected to name `partition_for_ingest`.
- The recorded Round B shape (run `2bc3617b`: three unmatched rows, two given an email by the
  waterfall, one not, all held `HOLD_NO_MATCH`, `send_count == 0`) was not pinned by any test —
  only a single-row neighbour existed. Added
  `test_round_b_shape_send_count_zero_all_three_held_no_match`, observed failing
  (`send_count == 2`, reproducing the incident) under a temporary, uncommitted perturbation of
  `partition_for_ingest`'s confident branch, then observed green after restore.
- The SKILL did not carry the design fact ("under autonomy a new person is never created
  without the operator's end-of-run approval") — README.md L150-154 had it, the SKILL did not.
  Added the sentence to `enrich-before-ingest/SKILL.md`, pinned by a new non-parametrized test
  in `test_autonomy_switch_prose.py`.

**The Fix's approved-hold branch is NOT implemented, and this task deliberately did not build
it.** The Fix presumed SEND when "the operator has approved the hold in the end-of-run pass".
Tracing the shipped code found no such path: `held_queue.py` exposes no approve verb,
`partition_for_ingest` takes no approved-rows input, and the SKILL documents the
approve/deny/pick review vocabulary with no block that applies it and dispatches. Rather than
invent an `approved_row_ids` parameter with no caller (dead plumbing), this was raised as its
own todo:
`.planning/todos/pending/2026-09-11-no-plugin-path-turns-an-approved-held-row-into-a-sent-row.md`.
