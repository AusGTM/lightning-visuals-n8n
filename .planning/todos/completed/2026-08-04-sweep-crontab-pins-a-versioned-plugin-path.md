---
created: 2026-08-04T08:05:00.000Z
updated: 2026-09-02T18:00:00.000Z
resolves_phase: 63
title: The sweep's crontab entry pins a versioned plugin path, so an update silently stops the unattended sweep
area: operator-claude-plugin
severity: major
files:
  - operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh
  - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
  - operator-claude-plugin/scripts/durable_paths.py
---

## RESOLVED 2026-09-03 — Phase 63 (plans 63-01, 63-02)

Everything below this section was written **before Phase 63 executed** and is preserved verbatim
as the case for the work, not as current state. All three sketched mitigations shipped, and each
was re-confirmed on disk at closure rather than taken from a SUMMARY claim:

| Sketched fix | State 2026-09-03 |
|---|---|
| Stable launcher shim under the durable home | **shipped** — `operator-claude-plugin/scripts/sweep_shim.py` installs `lv-sweep-launcher.sh` at the durable path and resolves the newest install at every fire, reusing `durable_paths.py`'s ordering rather than reimplementing it (D-63-04) |
| Self-check in the wrapper | **shipped** — `lv-sweep-run.sh`'s staleness block stamps both roots and banners when running an old root, and never refuses (D-63-02) |
| Re-point step in the update docs | **shipped** — `SWEEP-CRON-TEMPLATE.md`'s cron line and launchd `ProgramArguments` both name the shim, plus a "Already have a schedule installed under the old shape? Re-point it once." subsection |

Proven under a real scheduler, not asserted: `63-SWEEP-SHIM-SCHEDULER-PROOF.md` (three live
launchd runs resolving the newest install and following a simulated update, no schedule or shim
edit) and `63-SWEEP-SHIM-CONCURRENCY-PROOF.md` (an interrupted fire leaves no partial state; two
genuinely overlapping fires each resolve independently and each stamp a complete, uninterleaved
line). Phase 63 verification: 28/28, `passed`.

**What this closure does NOT claim.** The twelve already-installed version directories on the
operator's machine are untouched, and D-63-03 forbids this project rewriting any crontab. The
schedule on that machine still names whatever path it was written with. Reaching it is the
**one-time admin re-point** the template now documents — an operator action, not something this
phase performed.

---

## Status (rewritten 2026-09-02, superseded by the section above) — still open, and materially worse

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

## Closure (2026-09-02, Phase 63 plans 01 and 02)

All three sketched mitigations landed:

1. **Stable launcher shim under the durable home** — `operator-claude-plugin/scripts/sweep_shim.py`
   (63-01 Task 1). Resolves the newest installed version at every scheduled fire and `exec`s that
   version's `lv-sweep-run.sh`; version ordering is reused from `durable_paths.py`
   (`_VERSION_DIR_RE` / `_version_key`), never reimplemented (D-63-04).
2. **Self-check in the wrapper** — `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh`
   (63-01 Task 2). Compares its own resolved root against the newest installed version, stamps a
   log line naming both and posts a banner when they differ, and never refuses the sweep (D-63-02).
3. **Re-point step in the update docs** —
   `operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` (63-01 Task 3). New Step 2
   installs the shim; both the cron and launchd examples now pin the shim path; a new subsection
   ("Already have a schedule installed under the old shape? Re-point it once.") documents the
   one-time admin action for the twelve already-installed directories this todo's 2026-09-02
   re-verification counted.

**Real-scheduler proof (63-02, not an interactive approximation):**
`.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-SWEEP-SHIM-SCHEDULER-PROOF.md`
— a temporary launchd agent (never cron, per D-63-03's prohibition on touching any crontab)
observed a genuine scheduled fire resolve to the newest installed version, then observed the NEXT
genuine fire follow a simulated plugin update with no schedule or shim edit. Zero network calls,
zero provider credits, zero n8n executions, zero HubSpot writes, zero crontab contact. Run three
times; every run exited 0 with the temporary launchd registration independently confirmed absent
afterward.

**What remains explicitly open, stated by the proof record itself:** the twelve already-installed
directories on this machine are untouched (D-63-03 forbids it), and the self-check only reaches a
schedule once it is re-pointed to the shim or freshly installed against a plugin version that
already carries the check — a schedule still pinned to `0.33.0` or earlier runs that version's
older wrapper, which has no self-check at all. This todo stays in `pending/`; moving it is the
phase seal's job, not this closure note's.
