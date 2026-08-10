---
created: 2026-08-10T02:30:00.000Z
title: Runtime cadence changes bypass every budget guard — no floor, and the baked cap goes stale
area: operator-claude-plugin
severity: major
resolves_phase: 45
files:
  - operator-claude-plugin/scripts/n8n_cadence.py:199
  - operator-claude-plugin/scripts/n8n_cadence.py:439
  - config/execution_budget.yaml
  - scripts/build_cloud_workflows.py:5503
---

## Problem

Found by the 2026-08-10 USAGE.md fact-check, which asked: does the operator's schedule
change actually pass through the build? Answer: no.

Two paths set a trigger's cadence, and only one is protected:

- **Build time** (`_schedule_trigger`, `build_cloud_workflows.py`): Phase 44 added two
  tripwires — the module-level `assert SJ3_DISPATCH_CAP >= 1` (a sub-daily cadence drives
  the derived cap to ≤0 and the build refuses to produce JSON) and
  `tests/test_execution_budget.py` (CAP-03: shipped schedule's monthly idle floor vs a
  configured share of the 2,500/month allowance, offenders named).
- **Runtime** (the plugin's `cadence` control action → `n8n_cadence.set_cadence` → PUT to
  the live workflow): **no build, no regenerated JSON, neither tripwire executes.**
  `parse_cadence` accepts `every N seconds|minutes|hours|days|weeks|months` with a single
  floor of `N >= 1` — "every 30 seconds" is a legal, confirmable request. The only guard is
  the plain-language consequence read-back plus the operator's "yes": a comprehension
  check, not a budget check.

The compounding half: `SJ3_DISPATCH_CAP` is baked from the cadence the **builder** bakes
(`allowance × share / ticks-per-month − 1` → 40/tick at daily). A runtime re-time changes
tick frequency but not the baked cap, so the pair silently unmatches:

```
runtime re-time SJ-3 to 15 min:  2,880 ticks/month × (1 + cap 40) ≈ 118,000/month worst case
empty-queue floor alone:         2,880/month = 115% of the whole plan, doing nothing
```

The 2026-08-09 runaway (182k/month, caught by a human at 80% of the bill) was this exact
budget domain; Phase 44 closed the dispatch side but its boundary stopped at the SJ-3 lane —
the `cadence` action is plugin territory.

## Solution

Two complementary layers; Phase 45 is the natural home (same budget domain, same config
file, pure plugin-side Python like the rest of the phase):

1. **Runtime floor in `n8n_cadence`** — read `config/execution_budget.yaml` (already the
   one shared allowance source, D-11), compute the requested interval's monthly fire count,
   and refuse any cadence whose cost busts the configured share — with the module's
   established named-arithmetic refusal style (D-09/D-10: plain words, no expression
   syntax, a way forward). ~20 lines plus tests. Refusal must name the numbers ("every 15
   minutes is 2,880 fires a month against a 2,500 plan").
2. **The burn-rate alarm (ALARM-01..04, already scoped)** stays the backstop for every path
   the floor never sees — including someone re-timing a trigger directly in the n8n editor,
   which bypasses the plugin entirely. Floor prevents at the front door; alarm detects
   everywhere else.

Note for the fix: the floor should bound ALL five schedule triggers, not just SJ-3 — the
review poller at 15 min was half of the original 6,500/month idle overrun, and it has no
cap node at all.
