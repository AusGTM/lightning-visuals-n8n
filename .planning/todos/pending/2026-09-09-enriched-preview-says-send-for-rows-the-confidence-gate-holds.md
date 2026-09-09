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
