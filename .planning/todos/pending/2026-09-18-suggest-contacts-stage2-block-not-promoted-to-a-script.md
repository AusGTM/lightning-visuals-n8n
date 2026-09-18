---
created: 2026-09-18T00:00:00.000Z
updated: 2026-09-18
title: suggest-contacts/SKILL.md's Stage 2 block (mint + dispatch + re-join) is still
  free-floating prose+code inside the skill file, not a real Python module a session can
  import and run directly
area: operator-claude-plugin
severity: minor
files:
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
kind: question
trigger: a second session improvises its own stage-2 pipeline (mint_row_ids, chunking,
  dispatch, recover, merge) rather than following the skill's own embedded code block
  step by step -- exactly what happened in the 2026-09-18 pickleball sitting
owner: operator
---

Phase 73.1 Plan 08 read Stage 2's existing embedded block (the "Stage 2 — enrich the
people stage 1 named" step and its share of the "whole documented sequence, in one pass"
fence) and confirmed it is already CORRECT: it reuses
`enrich-before-ingest/SKILL.md`'s own dispatch machinery
(`enrichment.resolve_providers`, `chunking.dispatch_plan`,
`watch.recover_async_dispatch`, `preingest.merge_enriched`) rather than reimplementing
it, exactly as its own prose states. It was NOT rewritten by plan 08 — rewriting a block
that was not broken was explicitly out of scope.

What the 2026-09-18 pickleball sitting actually hit was not a defect in this block's own
logic; it was that a session under time pressure wrote its own ad hoc script instead of
following the skill's block step by step, and that improvisation was where the actual
bugs entered. Promoting this embedded prose+code block into a real, importable
`scripts/suggest_land.py` (mirroring `dispatch.py`'s own module shape) would remove the
temptation to improvise, and would let this whole "whole documented sequence" fence gain
its own direct test coverage the way every other `scripts/*.py` module already has.

Deferred rather than done in plan 08: the block itself needed no fix, module extraction
is a genuine refactor (new file, new tests, a `SKILL.md` rewrite to call it), and doing
it inside a plan whose own scope was the discovery-round wiring would have been exactly
the kind of out-of-scope widening CLAUDE.md §31 rule 3 exists to name explicitly rather
than fold in silently.
