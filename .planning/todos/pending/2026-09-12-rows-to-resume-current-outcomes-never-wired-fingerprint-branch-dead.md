---
created: 2026-09-12T00:00:00.000Z
updated: 2026-09-12
title: rows_to_resume's current_outcomes fingerprint branch is never wired, so a settled row's fingerprint comparison never runs
area: operator-plugin
severity: minor
kind: defect
evidence: operator-claude-plugin/scripts/run_manifest.py:463 (the `current is None` re-include path); operator-claude-plugin/skills/enrich-before-ingest/SKILL.md step 8 passes held_entries= but not current_outcomes=
files:
  - operator-claude-plugin/scripts/run_manifest.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
---

## Found closing quick batch 260911-w6n / decided in Phase 71 plan 02 Task 1 (Open Question 1)

`run_manifest.rows_to_resume`'s `CONFIDENCE_HELD` branch has two short-circuits ahead of its
fingerprint comparison — `held_queue.is_settled(entry)` and
`held_queue.entry_verb(entry) == held_queue.VERB_RETRY` — both wired live by Phase 71 (plan 02
Task 1: `enrich-before-ingest` step 8 now calls
`watch.resume_or_disclose(rows, held_entries=held_queue.load())`). Below those two, the branch
falls through to:

```python
current = current_outcomes.get(row_id)
if entry is None or current is None:
    to_resume.append(row)
    continue
recorded_fp = entry.get("resume_fingerprint")
current_fp = held_queue.fingerprint(entry.get("hold_code"), current)
if recorded_fp == current_fp:
    still_held.append({"row_id": row_id, "verdict": verdict})
else:
    to_resume.append(row)
```

`current_outcomes` is the SECOND keyword argument `resume_or_disclose` accepts, and it is never
passed at the one live call site — `enrich-before-ingest` step 8 passes `held_entries=` only.
With `current_outcomes` always an empty dict (its default), `current_outcomes.get(row_id)` is
always `None`, so `entry is None or current is None` is always true for every row that reaches
this point, and the whole fingerprint-comparison branch below it (the "has this row's situation
actually changed since it was held?" check) is dead code in production — every non-settled,
non-retry `CONFIDENCE_HELD` row falls through to `to_resume` unconditionally, same as if the
branch did not exist at all.

## What the fingerprint comparison would buy

Without it, a resumed row that was held with the SAME situation as last time (nothing about the
row or the world changed) still gets fully re-processed — re-matched, and if it reaches the
provider waterfall again, re-spends a credit — purely because its held entry didn't happen to
be `settled`/`retry`. The fingerprint check exists precisely to let a genuinely-unchanged held
row skip that re-spend and stay `still_held` cheaply, rather than paying for the same answer
twice.

## Why it is not wired in this phase

Wiring `current_outcomes` requires a caller to have already produced this run's own *current*
per-row outcome (email found/not found, company resolved/not) BEFORE the resume decision is
made — i.e. a fresh, zero-credit match pass over the row, so the fingerprint has something
current to compare the recorded one against. That is its own scope: a new match-only pass
threaded into step 8 ahead of `resume_or_disclose`, not a two-line wiring change like
`held_entries=` was. Phase 71's own boundary is the stable-identity rekey and the
`company_known` stamp; building a new zero-credit pre-resume match pass is a different, larger
piece of work.

## Fix

Not designed here. A candidate direction: before calling `resume_or_disclose`, run the
resuming rows through the same zero-credit classification `preingest.match_batch` already does
at step 2 (email presence, company resolution) to produce a `current_outcomes` dict keyed by
`row_id`, then pass it through. Whatever ships needs its own test proving a same-situation
resumed row lands in `still_held` (not `to_resume`) without spending a provider credit, and a
changed-situation resumed row still lands in `to_resume`.
