---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-12
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

## Resolved by Phase 71 (2026-09-12)

Closed by **D-71-04..05** — the candidate direction sketched above (a stable identity minted
onto the entry, not a positional `row_id`) shipped, with the identity DERIVED rather than
minted, and the migration question answered by refusal rather than a rewrite pass.

- **`held_queue.identity_keys(row)` / `held_queue.stable_key(row)`** (plan 01, Task 1/2) derive
  a group-prefixed key from `config/column_mapping.yaml`'s `required_identity.any_of` —
  `email::<addr>` when present (cleaned, case-folded), else
  `name::<first>|<last>|<company>` through the same name key D-69-04 already trusts
  (`suggest_contacts._name_key`), else `linkedin::<url>`, with a total fallback
  `source-position::row-N` for a row that satisfies none of the three groups. This is the same
  identity D-71-04 specifies and resolves the conflict this todo raised with D-69-04's own
  `company_id` key (a `needs_company` row has none by definition).
- **The SOURCE-row derivation, called from ONE place on each side.** The write side
  (`enrich-before-ingest` step 5's persist fence, plan 01) keys the entries-map on
  `held_queue.stable_key(row)` computed from the loop's own source row, never the merged one.
  The read side (`run_manifest.rows_to_resume`'s `CONFIDENCE_HELD` branch, plan 02 Task 1)
  looks the held entry up by `held_queue.stable_key(row)` computed fresh from the RESUMING
  row — the same derivation, not a second implementation of it. A held entry saved under one
  run's `row_id` is now found by a later run's differently-positioned row. The reported
  `row_id` inside `skipped`/`still_held` stays the source position (D-69-04), unchanged — only
  the lookup key moved.
- **The sharper defect RESEARCH found, not just the resume-lookup miss this todo names:** the
  primary defect this rekey closes is a silent cross-run **overwrite** inside
  `held_queue.save()` — the recorded `a254d1e` queue's `row-1`/`row-4` collision (Barry Milton
  held twice under the same positional key) meant a second run's own `row-1` could silently
  clobber a first run's still-open entry at write time, not merely fail to be found at
  resume time. The stable key fixes both: two different people can no longer share a key, and
  the same person across runs now collapses onto the same entry instead of colliding with
  whoever else last held that position.
- **D-71-05's wipe, not a migration.** `held_queue._LEGACY_KEY` (`^row-\d+$`) makes
  `_validated_entries()` refuse a pre-Phase-71 positional document outright — `load()` returns
  `{}`, `classify_read()` returns `ANOMALOUS` — and `held_queue.legacy_reason()` gives the
  caller a one-sentence instruction naming the wipe, instead of the document silently reading
  as an empty queue. No lazy rekey-on-load code exists; the live `held_queue.json` is deleted
  by hand in the D-71-06 gate's own clean-up step, per D-71-05.

**Covering tests** (by nodeid, from the 71-01/71-02 SUMMARY `coverage:` blocks):
- `operator-claude-plugin/tests/test_held_queue.py#test_a_grant_dewsbury_stable_key_is_a_name_group_key_and_persists`
- `operator-claude-plugin/tests/test_held_queue.py#test_a_linkedin_only_grant_dewsbury_row_persists_under_its_linkedin_key`
- `operator-claude-plugin/tests/test_held_queue.py#test_a_legacy_row_n_keyed_document_classifies_anomalous_with_a_wipe_naming_reason`
- `operator-claude-plugin/tests/test_run_manifest.py#test_a_prior_runs_held_entry_is_found_by_this_runs_differently_positioned_row`
- `operator-claude-plugin/tests/test_run_manifest.py#test_a_prior_runs_retry_verb_re_includes_this_runs_differently_positioned_row`
- `operator-claude-plugin/tests/test_run_manifest.py#test_the_reported_row_id_stays_the_resuming_rows_own_source_position_never_the_stable_key`
- `operator-claude-plugin/tests/test_run_manifest.py#test_a_row_with_no_identity_group_resolves_through_the_total_fallback_without_raising`
