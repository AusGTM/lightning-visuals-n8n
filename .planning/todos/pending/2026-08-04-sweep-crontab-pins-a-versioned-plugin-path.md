---
created: 2026-08-04T08:05:00.000Z
updated: 2026-09-02
resolves_phase: 63
title: The sweep's crontab entry pins a versioned plugin path, so an update silently stops the unattended sweep
area: operator-claude-plugin
severity: major
files:
  - operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh
  - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
  - operator-claude-plugin/scripts/durable_paths.py
---

## Status (rewritten 2026-09-02) — still open, and materially worse

Re-verified against the tree and the machine. **Nothing about this has been fixed**, and the
evidence for it is now much stronger than when it was captured.

**Phase 33 landed `durable_paths.py`, and it does not close this.** That was anticipated in the
original capture — Phase 33's boundary is where *operator state* lives; this is where the *code*
lives. Confirmed by reading the module's own docstring: it is the single authority for the
credentials file and the dashboard pointer, resolving through `${CLAUDE_PLUGIN_DATA}` with a
newest-sibling migration. It says nothing about the launcher path, and nothing consumes it for
that purpose.

**All three original mitigations are still absent:**

| Sketched fix | State 2026-09-02 |
|---|---|
| Stable launcher shim under the durable home | **absent** — no shim exists |
| Self-check in the wrapper ("running an old plugin build") | **absent** — no version/staleness check in `lv-sweep-run.sh` |
| Re-point step in the update docs | **absent** — `SWEEP-CRON-TEMPLATE.md` has no mention of version, update, staleness or re-pointing |

`SWEEP-CRON-TEMPLATE.md:56` still hands the admin a line built from `[plugin-root]`:

```
0 */4 * * * /bin/sh "[plugin-root]/skills/backend-sweep/lv-sweep-run.sh" "[plugin-root]" "[venv-python]" "$HOME/Library/Logs/lv-backend-sweep.log"
```

and `lv-sweep-run.sh` still takes the plugin root as `$1` by design ("Three positional arguments,
in order: `$1` the plugin root...").

**The scale of the drift, measured on this machine 2026-09-02.** The original recorded four
versioned directories (`0.1.0`, `0.6.0`, `0.6.1`, `0.6.2`) and three updates in one afternoon.
There are now **twelve**:

```
0.10.0  0.11.1  0.14.0  0.15.0  0.15.1  0.16.1
0.16.2  0.17.0  0.18.0  0.19.0  0.28.6  0.33.0
```

**And the newest cached directory is `0.33.0` while the shipped plugin is now `0.35.0`** (Phase 60,
2026-09-01). So even "pin the newest directory you can see" is already stale against the repo. Any
crontab written during this todo's lifetime points at a directory that is now between 2 and 25
releases behind.

**Why this is urgent rather than tidy.** The milestone in flight is **v1.1 Unattended Session
Runs**. This defect's two failure shapes both attack that goal directly:

1. Old directory still present → the sweep fires **old code** against the live backend
   indefinitely, with no signal it is stale. With twelve directories present, this is the likely
   shape here, not the theoretical one.
2. Old directory cleaned up → cron fires nothing. Phase 32 made a trigger that *cannot run* loud
   (non-zero exit + banner), but that only helps once the wrapper is reached. A crontab pointing at
   a deleted path produces a shell error into cron's mail, not the operator's banner — which is
   precisely the "never fired" vs "healthy" ambiguity NOTICE-03 and Phase 32 exist to eliminate.

## Solution

Unchanged in shape; option 1 is now clearly right because Phase 33 already shipped the durable
home it depends on.

1. **Stable launcher path (preferred).** Install a small version-independent shim under the
   durable home (`${CLAUDE_PLUGIN_DATA}` / `~/.claude/plugins/data/<id>/`) that resolves the
   newest install directory at run time and `exec`s its `lv-sweep-run.sh`. The crontab pins the
   shim, which never moves. **Reuse `durable_paths.py`'s newest-sibling resolution — do not write
   a second version-ordering implementation.** That module already solved this ordering problem
   for state; the shim needs the same answer for code.
2. **Self-check in the wrapper.** Have `lv-sweep-run.sh` compare its own resolved root against the
   newest installed version and emit a notice rather than running stale in silence. Complements
   (1); does not replace it. Worth doing anyway — it is the only fix that helps the twelve
   already-installed crontabs nobody will re-point.
3. **Document only.** Weakest, and REQUIREMENTS.md lists terminal instructions to the operator
   under Out of Scope ("Terminal instructions to the operator are a requirement failure").
   Acceptable only as an interim note.

**Whichever lands, it needs a real-scheduler proof, not an interactive approximation** — see memory
`sweep-trigger-llm-free`: the original host probe passed interactively and still failed under cron,
because it inherited credentials cron never has. Verify by observing an actual fire after a
simulated update (bump a version directory, then wait for a real cron tick).

## Origin

Surfaced by the Phase 33 planner while mapping the versioned-install-directory problem, and
deliberately left OUT of Phase 33's scope.
