---
phase: quick-260911-anx
plan: 01
subsystem: operator-plugin
tags: [preingest, merge_enriched, field_policy, jobtitle, RICH-04]
status: complete
dependency-graph:
  requires: []
  provides:
    - preingest.refreshable_contact_props
  affects:
    - operator-claude-plugin/scripts/preingest.py
tech-stack:
  added: []
  patterns:
    - "Per-field policy read via a shared _load_contacts_policy loader, mirroring the RICH-04 promotable_contact_props seam"
key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/tests/test_preingest_preview.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - .planning/todos/completed/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md
decisions:
  - "refreshable_contact_props() degrades to [] (protect everything) on any policy-read failure -- the opposite, safer direction from promotable_contact_props()'s widening degradation to []."
  - "Conflict entry key kept -> source_value, plus a new replaced: bool, so a kept value and a replaced value are both nameable in the same shape."
  - "enriched_values in _row_view now means 'differs from source_values', not 'absent from original' -- so a replaced value is visible in the pre-arm preview."
metrics:
  duration: "~35m"
  completed: 2026-09-11
actuals:
  tokens: 27000
  tasks: 2
  commits: 2
plan_head_before: 901825c1
---

# Quick 260911-anx: per-field protect_if_current_present in merge_enriched Summary

`merge_enriched`'s blanket fill-not-overwrite rule silently overrode `field_policy.yaml`'s
own per-field `protect_if_current_present: false` for `jobtitle`, discarding a richer
waterfall title into `conflicts` instead of writing it. Now `merge_enriched` reads the
per-field rule through the same RICH-04 policy seam `promotable_contact_props` already
uses, for both `enrich-before-ingest` and `suggest-contacts`.

## What was built

**Task 1 — per-field `protect_if_current_present` in `merge_enriched`
(`19a5f357`).** Factored `promotable_contact_props`'s defensive YAML load into a new
private `_load_contacts_policy(policy_path=None)` helper (returns the `contacts:`
mapping, or `{}` on any failure) so exactly one load path exists. Added a sibling public
`refreshable_contact_props(policy_path=None)`, an `is False` identity test on
`protect_if_current_present` (never truthiness), degrading to `[]` — the SAFER direction —
on an unresolvable or malformed policy, the opposite of `promotable_contact_props`'s
widening degradation.

`merge_enriched` now builds that set once beside `allowed_keys` and, in the
`_present(current)` differing-value branch, writes the response value onto the merged row
only when the key is in the refreshable set. Conflict entries rename `kept` ->
`source_value` and add `replaced: bool`, so both the kept and replaced outcomes are
recorded and distinguishable. Updated the docstring to state the per-field rule, name
`field_policy.yaml` as its one source, name the operator ruling (2026-09-11), and state
that both callers share the rule and that per-field `min_confidence` is deliberately not
read here.

RED evidence (recorded before the fix): running the suite against the still-blanket
`merge_enriched` with the renamed conflict-entry tests already updated produced 3
failures —
`test_a_non_empty_source_value_is_never_overwritten_and_is_reported_as_conflict`
(asserting `jobtitle` still held "Director" when the response said "Analyst" — got
"Analyst"), `test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before` (same
assertion), and `test_a_present_widened_key_is_never_overwritten_and_records_a_conflict`
(conflict-entry shape mismatch, `kept` vs `source_value`/`replaced`). All three then
went green once the merge logic and conflict shape were implemented.

Repointed `test_a_non_empty_source_value_is_never_overwritten_and_is_reported_as_conflict`
and `test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before` from `jobtitle`
to `email` (the ruling's canonical "operator-typed value never replaced" example).
Added `test_a_present_jobtitle_is_replaced_by_a_differing_response_value` (new: jobtitle
now refreshes) and `test_a_field_absent_from_policy_entirely_keeps_fill_only_behaviour`
(new: `firstname`, which has no `contacts:` entry at all, still protects). Extended
`test_a_byte_equal_widened_key_records_no_conflict_and_writes_nothing` to also cover a
byte-equal `jobtitle`. Added a fail-safe assertion inside
`test_merge_allowlist_falls_back_to_canonical_props_when_the_policy_is_unreadable`:
with both policy paths monkeypatched to nonexistent files, a present, differing
`jobtitle` is still not replaced.

**Task 2 — pre-arm preview and SKILL prose (`d5d38588`).** `render_enriched_preview`'s
`_row_view` computed `enriched_values` as "present in merged AND absent from original" —
wrong once a replaced value can be present in BOTH. Changed the predicate to "differs
from `source_values`" (comparing against the already-built `source_values` dict one line
above), so a replaced `jobtitle` now shows under `enriched_values` while
`source_values` still shows the operator's own original — not just the superseded value
with nothing new visible. Added
`test_a_replaced_value_shows_in_enriched_values_beside_the_original_in_source_values`;
the three pre-existing `enriched_values` tests stayed green unmodified.

Rewrote `SKILL.md` step 6's conflict sentence, which claimed the source value is always
kept — no longer true for a `protect_if_current_present: false` field. New prose: a
conflict is a source value and a differing provider value, the report says which value
the row now carries, most fields keep the source value, and a field the policy marks
refreshable takes the provider's instead. No YAML key name or policy content pasted into
the skill; no `icp`/`tier` substring introduced (`test_autonomy_switch_prose.py`
guard).

Moved `.planning/todos/pending/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md`
to `.planning/todos/completed/`, appending a `## Resolved 2026-09-11` section naming the
quick task and summarizing the fix.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -q` — 61 passed.
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 2872 passed, 5 skipped (full plugin suite, run after both tasks).
- `/usr/bin/grep -rn '"kept"' operator-claude-plugin/scripts operator-claude-plugin/tests | /usr/bin/grep -v __pycache__` — returns only literal fixture dicts in `test_preingest_preview.py` (lines 333, 340, 362) that are passed straight through untouched code paths and never inspected by production logic; no production code and no `test_preingest_merge.py` test reads the old `kept` key.
- `git diff --stat -- config/ operator-claude-plugin/config/` — empty (no policy YAML edited).
- `git diff --stat -- n8n/ src/ scripts/` — empty (plugin-only change).

## Self-Check: PASSED

- FOUND: `operator-claude-plugin/scripts/preingest.py` (refreshable_contact_props, _load_contacts_policy present)
- FOUND: `.planning/todos/completed/2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md`
- FOUND commit `19a5f357` (`git log --oneline --all | grep 19a5f357`)
- FOUND commit `d5d38588` (`git log --oneline --all | grep d5d38588`)
