---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-11
title: held_queue.json row_id is positional, not a stable identity, and settlement is now keyed on it
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/run_manifest.py
kind: design
decision_needed: >
  held_queue.json is ONE global file across runs while row_id is POSITIONAL
  (row-1, row-2, ... -- the recorded a254d1e queue holds row-1 and row-4 as the
  same person, Barry Milton, twice), so a settled row-2 from one spreadsheet and a
  live row-2 from the next run's spreadsheet are the same key. Quick 260911-w6p's
  create/skip/retry/drop verbs (`held_queue.record_verb`) and run_manifest's
  settled-row short-circuit (`rows_to_resume`'s CONFIDENCE_HELD branch) are both
  keyed on this same row_id. Which stable identity should an entry carry instead
  (email? email plus company? a minted entry id?), and who migrates the entries
  already on disk to it?
---

## Found during quick 260911-w6p (2026-09-11), while adding read-time facets and durable verbs

`held_queue.py`'s own docstring already documents that the queue is ONE GLOBAL FILE
across runs ("held rows collect into ONE review queue, cleared in a single pass",
D-61-07) while `row_id` is assigned POSITIONALLY by each run's own spreadsheet order
(`row-1`, `row-2`, ...). The recorded run `a254d1eda71246a2a964922cdf5c2bd2`
(`.planning/UAT-autonomous-batch-2026-09-09.md` line 65) demonstrates the collision
directly: `row-1` and `row-4` are both Barry Milton, the same person held twice under
two different positional keys in the same queue.

This plan (260911-w6p) added `held_queue.record_verb(row_id, verb, run_id)` and
`run_manifest.rows_to_resume`'s settled-row short-circuit, both of which trust
`row_id` as the entry's identity. A settled `row-2` from one spreadsheet and a live
`row-2` produced by the NEXT run (a different spreadsheet, a different person at that
position) are the same key in `held_queue.json` -- so a verb recorded against one
person's `row-2` could read back against a different person's `row-2` in a later run.

## Why this plan deliberately does NOT fix it

Keying cross-run protection on `row_id` alone (e.g. refusing a duplicate `row_id`
across runs, or auto-migrating positional ids to something stable) would risk
silently DROPPING a different person from the review queue -- worse than the re-hold
it would prevent. That decision needs a ruling on what the stable identity should be
(email is not always present -- see `nothing_found` facet rows; email+company is
closer but two people can share a company; a minted UUID entry id sidesteps the
question but needs a migration story for every entry already on disk today). The
collision pre-dates this plan; 260911-w6p only adds two more consumers that trust the
same positional key.

## Fix

Not proposed here -- the `decision_needed:` above names the open question. A
candidate direction: mint a stable `entry_id` (e.g. a hash of email+company, or a
UUID) at `build_entry` time, use it as the queue's own key instead of the caller's
`row_id`, and keep `row_id` as a field inside the entry for display/re-send purposes
only. Migration of entries already on disk (which have no `entry_id`) is a second
open question the same ruling should answer.
