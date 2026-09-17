---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-17
title: 17 of 48 Stage D match rows came back unchecked (a match chunk did not settle inside the recovery bound) in stress attempt 3
area: operator-plugin
severity: low
kind: question
trigger: "the next Stage D (enrich-before-ingest) run — does the recovery bound settle every chunk, or does the same fraction land unchecked again"
owner: operator
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage D of stress attempt 3, 2026-09-17/18.

## What happened

Match pass over 48 rows: 18 auto-matched, 2 proposed, 11 unmatched, **17 unchecked** — a
match chunk that did not settle inside the recovery bound. This is safely bucketed (not
misclassified, re-checked on retry), not a data-loss defect, but a ~35% unchecked rate on this
run is worth watching rather than dismissing as noise.

## Question

Does the recovery bound reliably settle every chunk on a typical-sized batch, or does this
run's ~35% unchecked rate recur? If it recurs, the recovery bound or its retry cadence may need
widening. Revisit at the trigger above.
