---
created: 2026-08-03T08:45:00.000Z
title: Sweep re-notifies a fixed failure until 100 executions displace it
area: planning
severity: major
files:
  - operator-claude-plugin/scripts/n8n_read.py:47
  - operator-claude-plugin/scripts/sweep_conditions.py
---

## Problem

Found by RB-8 live, 2026-08-03. `recent_executions` reads a **fixed page of 100 executions with no
time window** (`EXECUTIONS_PAGE_LIMIT = 100`). A failed run therefore keeps firing a notice every
sweep until 100 newer executions push it off the page.

Observed: execution 1173 (the pre-fix review approve that 400'd during the RB-9 canary) still
notifies — its cause was fixed by Phase 31 hours earlier. At the maintenance workflow's ~8
executions/hour that is ~6 hours of repeat notices; on a quieter backend, days. There is no way to
acknowledge a notice.

NOTICE-04 exists because "a sweep that speaks when healthy is one the operator learns to ignore".
An unclearable repeat notice for an already-fixed problem reaches that same destination by a
different road.

Secondary, same area: the notice reads "a run of **an unnamed workflow** ended in status 'error'".
n8n's `/executions/{id}` carries `workflowId` and no name field, so this is an honest degradation —
but the admin the notice tells to act cannot tell which workflow failed. `n8n_read.list_workflows`
already exists; one extra read would map id → name.

## Solution

TBD. Options: bound the lookback by time as well as row count (e.g. only executions started since
the last sweep, or within N hours); and/or a lightweight acknowledged-state so a seen failure stops
repeating. Add the id → name mapping for the notice text at the same time — same file, same read.
