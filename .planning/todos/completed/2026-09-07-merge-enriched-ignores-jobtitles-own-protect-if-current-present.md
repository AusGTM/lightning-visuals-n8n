---
created: 2026-09-07T00:36:02.000Z
updated: 2026-09-07
title: merge_enriched ignores jobtitle's own protect_if_current_present in field_policy.yaml
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/preingest.py
  - config/field_policy.yaml
---

## The gap

Live evidence: an all-blank CREATE row whose waterfall returned `Head of Marketing and
Content` while stage 1 had already guessed a thinner title for the same person. The
richer, waterfall-supplied title was recorded in `merge_enriched`'s `conflicts` list
(`kept` the thinner value, `provider_value` the richer one) and discarded — never
written to the row.

**The traced cause.** `merge_enriched`'s fill-versus-conflict rule (Phase 37 Plan 04,
unchanged by Phase 65 Plan 02's RICH-04 widening) is ONE blanket rule applied to every
key: a `properties` value only fills a key the row currently holds empty or absent; a
DIFFERING value for a key the row already holds non-empty is never written, only
reported. That rule is correct for most fields — the spreadsheet is the operator's own
assertion about their own data, and silently replacing it with a vendor's guess is a
change they would have no way to notice.

But `jobtitle`'s own entry in `config/field_policy.yaml` (and the plugin's shipped copy)
carries `class: stale_refreshable`, `protect_if_current_present: false`, and
`min_confidence: 75` — the policy's own author decided a present `jobtitle` value is
NOT protected against a confident refresh, unlike `email`
(`protect_if_current_present: true`) or the location fields. `merge_enriched` reads no
per-field `protect_if_current_present` value at all; it applies the SAME
fill-not-overwrite behavior to `jobtitle` that it applies to `email`, silently
overriding the policy's own, more permissive rule for this one field.

## Why this was deferred rather than built alongside RICH-04's widening

Making `merge_enriched` field-policy-aware for `protect_if_current_present` changes
BEHAVIOR for BOTH of its production callers — not just `enrich-before-ingest`, where a
spreadsheet value is the operator's own assertion about their own data, but also
`suggest-contacts`, whose rows are synthesised by this plugin itself and carry no such
operator assertion at all. Whether the SAME per-field protection rule should apply
identically to both callers, or whether `enrich-before-ingest`'s spreadsheet-typed
values deserve a stronger guarantee than `suggest-contacts`' own synthesised rows, is a
policy-semantics decision that deserves its own operator ruling — not a rider silently
folded into an allowlist-widening plan. RICH-04's own scope (65-02-PLAN.md
prohibitions) explicitly excludes it: "`merge_enriched`'s fill-versus-conflict branch is
not modified; no per-field `protect_if_current_present` branch is added in this phase."

## What closing it would require

- A per-field read of `protect_if_current_present` (and probably `class` /
  `min_confidence`) from the same `promotable_contact_props`-adjacent policy lookup
  RICH-04 added, threaded into `merge_enriched`'s fill-versus-conflict branch.
- An explicit operator decision on whether `enrich-before-ingest` (operator-typed
  values) and `suggest-contacts` (plugin-synthesised values) should follow the same
  per-field rule, or two different ones.
- A test proving an operator-typed `jobtitle` (or any other `protect_if_current_present:
  true` field) is still never silently replaced, alongside a test proving a
  `protect_if_current_present: false` field like `jobtitle` DOES accept a
  sufficiently-confident refresh once this is built.
- A decision on whether the merge should also honor `min_confidence` per field, since
  today's fill-versus-conflict rule has no confidence gate at all — a response's
  `properties` map carries no confidence value for `merge_enriched` to read in the
  first place, so that may be its own, separate follow-on.

## Operator ruling 2026-09-11 (resume session)

**Per-field, both callers.** `merge_enriched` reads `protect_if_current_present` per field
from `field_policy.yaml` (plugin's shipped copy) for BOTH `enrich-before-ingest` and
`suggest-contacts`. `jobtitle` (`protect_if_current_present: false`) accepts a refresh;
`email` and the location fields (`true`) stay never-replaced. The policy file is the one
source; the `conflicts` list still records every replaced value. Per-field `min_confidence`
in the merge is NOT part of this ruling — separate follow-on if wanted.

## Resolved 2026-09-11

Fixed in quick task `260911-anx` (`260911-anx-SUMMARY.md`). Added
`preingest.refreshable_contact_props()` (a sibling read on the same RICH-04
`_load_contacts_policy` seam `promotable_contact_props()` uses, degrading in the
OPPOSITE, safer direction on an unresolvable policy). `merge_enriched`'s fill-vs-conflict
branch now writes a differing response value only when the field is in that set;
`jobtitle` is the only member today. Conflict entries rename `kept` -> `source_value`
and add `replaced: bool` so both outcomes are distinguishable. `render_enriched_preview`'s
`_row_view` was fixed to compute `enriched_values` by "differs from the original" rather
than "absent from the original", so a replaced value shows correctly in the pre-arm
preview instead of only the superseded value showing under `source_values`. SKILL.md
step 6's conflict sentence no longer claims the source value is always kept.
