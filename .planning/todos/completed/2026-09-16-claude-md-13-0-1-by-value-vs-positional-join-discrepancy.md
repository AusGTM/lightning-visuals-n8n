---
created: 2026-09-16T00:00:00.000Z
updated: 2026-09-16
title: "CLAUDE.md §13.0.1 describes Build Association Request joining write responses to rows BY VALUE, while the code joined positionally (by construction, via a combineByPosition carry merge)"
area: n8n-docs
severity: minor
kind: question
trigger: "the F-A6 lane design (Phase 73 Plan 06) — it must decide the pairing rule anyway, since a rejected create's error output breaks the positional assumption combineByPosition depended on"
owner: operator
files:
  - CLAUDE.md
  - scripts/build_cloud_workflows.py
  - n8n/code/pairCreateOutcome.js
---

## Open question (73-RESEARCH.md Pitfall 0, filed at plan time per CONTEXT.md's Step-0
## rulings, §31 rule 3)

CLAUDE.md §13.0.1 stated: `Build Association Request` "joins each write RESPONSE back to
its row BY VALUE (update by `id`, create by `properties.email`)". The code this session
read (`scripts/build_cloud_workflows.py`'s `BUILD_ASSOCIATION_REQUEST` jsCode, and its own
comment) did no by-value join at all — it read `row.id`/`row.email` straight off the single
item a `combineByPosition` carry merge had already paired, relying on item count and order
agreeing BY CONSTRUCTION (the carried row and the HTTP response are two edges off the one
wave that entered the write node). Either §13.0.1 was stale prose describing a mechanism
Phase 70's positional-merge refactor superseded, or a by-value join existed elsewhere that
session's reading did not find. Flagged rather than assumed, per the research task's own
instruction — Phase 73 Plan 06's own F-A6 design had to settle the pairing rule anyway (a
rejected create's error output shrinks the response array, breaking the positional
assumption `combineByPosition` needed), so its own lane design is the observation that
answers this question.

## Resolved (Phase 73 Plan 06 Task 1/4, 2026-09-16, D-73-01)

§13.0.1 was stale prose — the trigger fired inside the SAME plan that opened this todo.
`Create Carry Merge` is now `append` mode (not `combine`), and a new node, `Pair Create
Outcome To Row` (`n8n/code/pairCreateOutcome.js::pairCreateOutcome`), performs the ACTUAL
by-value join CLAUDE.md's prose had always described, just not the way it described it:
not `id`/`properties.email` read off an already-paired item, but an explicit identity-key
join computed on both sides (the ladder `columnMap.js`'s `requiredIdentity` already encodes
for CSV completeness — email, then firstname+lastname+company, then linkedin_url),
proven with a short-return test (RED before the change: `Create Carry Merge` reported
`merge_dropped_rows`, itemCounts 2/3 — a shrinking response array mis-paired a later row's
company; GREEN after). CLAUDE.md §13.0.1 is corrected in the same commit series (Phase 73
Plan 06 Task 4) to name the pair node and the identity ladder instead of the retired
positional construction. The `Build Association Request` row in that section's node table
now points to the amendment rather than repeating the stale "by value" sentence verbatim.

No live-observation tag was added for this lane — per D-73-19 it stays proven offline only,
until a real race occurs.
