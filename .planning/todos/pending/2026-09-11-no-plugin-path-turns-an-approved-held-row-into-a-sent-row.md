---
created: 2026-09-11T00:00:00.000Z
updated: 2026-09-11
title: No plugin-side path turns an approved held row into a sent row
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
---

## Found 2026-09-11, quick task 260911-anz, while closing todo
`2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md`

That todo's Fix presumed SEND when "the operator has approved the hold in the end-of-run
pass" — but no such path exists in code today. Traced, not assumed:

- `held_queue.py` exposes no approve verb — nothing writes a held row's status to
  approved-for-send.
- `preingest.partition_for_ingest` (the ONE per-row SEND/HELD verdict, D-70-11) takes no
  approved-rows input — there is no argument or side channel through which an operator's
  `approve` at the end-of-run review could change its verdict for a row.
- `enrich-before-ingest/SKILL.md` documents the end-of-run review's `approve` / `deny` /
  `pick <sub-label>` / `email: <address>` vocabulary, but no block after it applies an
  `approve` on a `HOLD_NO_MATCH` row and dispatches it. `approve` is documented for
  `HOLD_AMBIGUOUS_CANDIDATES` (proceed with an existing match despite ambiguity) and similar
  cases where a record already exists to write to — never for a no-match row, where "approve"
  would have to mean "create this person now", and nothing in the flow does that.

**Consequence — scoped to the `enrich-before-ingest` flow specifically.** A row with no
HubSpot match has no documented route to becoming a create today, which the 2026-09-09 UAT
recorded as "by design" (a new person is never created without the operator's end-of-run
approval) without the design existing in code: the design fact describes what does NOT
happen (no create without approval); it says nothing about what DOES happen when approval is
given, because nothing does.

**Why this todo is scoped to `enrich-before-ingest` alone, not every batch skill.**
`partition_for_ingest` has exactly one SKILL caller
(`grep -l partition_for_ingest operator-claude-plugin/skills/*/SKILL.md` returns only
`enrich-before-ingest/SKILL.md`). The other two dispatch-bearing skills route through
different, unrelated predicates that this todo does not describe:
- `suggestion-declines/SKILL.md` reaches its dispatch through `extraction.hold_emailless`
  alone — no confidence verdict, no held-row approval semantics comparable to this gap.
- `suggest-contacts/SKILL.md` reaches its dispatch through
  `suggest_contacts.partition_for_dispatch` — a separate function with its own hold codes,
  not `confidence.assess` or `partition_for_ingest`.

Neither consults the confidence verdict this todo is about, so neither is in scope here.

## Fix (not designed here — this todo records the gap, deliberately not the solution)

Decide and build the missing path: either `held_queue.py` gains an approve verb that
`partition_for_ingest` (or a caller-side wrapper) reads as an approved-rows input, moving an
approved `HOLD_NO_MATCH` row into the sendable set on a later pass — or the SKILL is corrected
to state plainly that an approved held row still requires a separate, manual re-run/creation
step outside this flow. Either way, whatever is built needs its own test pinning the approved
row actually reaching the sendable set (or the SKILL's corrected claim actually matching the
code), the same standard this todo's originating defect was closed to.
