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
kind: design
decision_needed: the approve verb's shape in held_queue and how partition_for_ingest takes approved rows; decide after the first live batch produces real held rows so the path is built against them
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

## Ruling (operator, 2026-09-11) — RESOLVED BY quick batch 260911-w6n (recreated from 260911-w2i)

"F2: no_match holds are faceted at read time (new person / needs company / nothing found);
`review-triage` reads both queues in one table; `create` lands through the ingest lane under
a review-lane grant; the batch renders the ready answer and never asks." Criterion stated:
most frictionless operator experience with relative safety, review over approve. Rejected:
export-to-`contact-upload` (three prompts to land one person) and an in-flow approve
question (UAT F4). Two facts that shaped it: `review-triage` today reads only HubSpot
`lv_enrichment_needs_review` and never opens `held_queue.json`; and `no_match` conflates a
provider `NOT_FOUND` (Katie Poggioli) with a rich reveal of a new person (Jimmy Busteed).
Items: 260911-w6o (enriched row into the held entry), 260911-w6p (facet classifier + verbs),
260911-w6q (review-triage reads both queues, one table, create through the ingest lane),
260911-w6r (batch renders the ready answer, never asks; 0.47.0).

### Resolution — all four items shipped, plugin `0.47.0`

- **260911-w6o** (`3d264b3f`, `3dfbbb44`) — closed the prerequisite: `held_queue.
  ROW_FIELD_ALLOWLIST` widened to 11 names, and `enrich-before-ingest`'s persist fence
  now hands `held_queue.build_entry` the dispatch step's own MERGED row (email, phone,
  mobile, LinkedIn) instead of the loop's bare source row — the enriched reveal this
  whole todo's gap needed to have something to read.
- **260911-w6p** (`15349f77`, `af653e46`, `66de79b8`) — closed the classifier half:
  `held_queue.classify_facet` splits a `no_match` hold into `new_person` /
  `needs_company` / `nothing_found`, and `record_verb`/`entry_verb`/`is_settled`/
  `open_entries` give an entry a durable `create`/`skip`/`retry`/`drop` status —
  the "approve verb" this todo's Fix section named as missing.
- **260911-w6q** (`7e6af271`, `2101b747`) — closed the create-route half:
  `review-triage/SKILL.md` reads `held_queue.json` alongside HubSpot's own review
  queue in one table, and a `new_person` row's `create` reaches HubSpot through
  `contact-upload`'s own dispatch, by heading, confirmed by an independent re-read —
  this todo's own missing "no plugin-side path" link.
- **260911-w6r** (`6de7a55c`, `23fa724a`, this item's own SUMMARY commit) — closed the
  face: `enrich-before-ingest` step 6 renders the facets and a ready answer instead of
  asking (closing UAT F4), step 9 restates them, and the release ships as plugin
  `0.47.0`.

Resolved in full by quick batch `260911-w6n`. This todo's original `Fix` section asked
for either a built approve path or a corrected SKILL claim — the ruling chose neither
literally: `no_match` holds route through the facet classifier and the ready answer
above, never through an `approve` verb on the hold itself.
