---
created: 2026-08-04T08:05:00.000Z
title: The sweep's crontab entry pins a versioned plugin path, so an update silently stops the unattended sweep
area: operator-claude-plugin
severity: major
files:
  - operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh
  - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
---

## Problem

Surfaced by the Phase 33 planner while mapping the versioned-install-directory problem, and
deliberately left OUT of Phase 33's scope: that phase's boundary is where *operator state* lives,
and this is where the *code* lives.

`lv-sweep-run.sh` takes the plugin root as `$1`, so the crontab line an admin installs from
`SWEEP-CRON-TEMPLATE.md` contains a path like:

```
~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/0.6.2/skills/backend-sweep/lv-sweep-run.sh
```

Updating the plugin creates a NEW versioned directory. The crontab still points at the old one.
On this machine there are already four such directories (`0.1.0`, `0.6.0`, `0.6.1`, `0.6.2`), and
three plugin updates happened in a single afternoon.

**Two failure shapes, and the second is the dangerous one:**

1. The old directory still exists → the sweep keeps firing **old code** against the live backend,
   indefinitely, with no signal that it is stale.
2. The old directory is cleaned up → the wrapper is gone, cron fires nothing. Phase 32 made a
   trigger that *cannot run* loud (non-zero exit + banner), but that only helps once the wrapper
   is reached. A crontab pointing at a deleted path produces a shell error into cron's mail, not
   the operator's banner — which is exactly the "never fired" vs "healthy" ambiguity NOTICE-03
   and Phase 32 exist to eliminate.

Neither is theoretical: the update path that causes it has now been exercised three times in one
day, and nothing in the install docs tells the admin to re-point the crontab.

## Solution

TBD. Sketch, cheapest first:

1. **Stable launcher path.** Once Phase 33 lands `durable_paths.py` and the plugin has a
   version-independent home under `~/.claude/plugins/data/<id>/`, install a tiny stable shim
   there that resolves the newest install directory at run time and `exec`s its
   `lv-sweep-run.sh`. The crontab then pins the shim, which never moves. Reuses Phase 33's
   newest-sibling resolution — do not write a second version-ordering implementation.
2. **Self-check in the wrapper.** Have the wrapper compare its own resolved plugin root against
   the newest installed version and emit a notice ("the sweep is running an old plugin build")
   rather than failing silently. Complements (1); does not replace it.
3. **Document only.** Add a re-point step to the update instructions. Cheapest, and the weakest —
   it is a terminal instruction to a human on every update, which REQUIREMENTS.md lists under Out
   of Scope ("Terminal instructions to the operator are a requirement failure"). Acceptable only
   as an interim note.

Whichever lands, it needs a real-scheduler proof, not an interactive approximation — see memory
`sweep-trigger-llm-free`: the original host probe passed interactively and still failed under
cron, because it inherited credentials cron never has. Verify by observing an actual fire after a
simulated update.
