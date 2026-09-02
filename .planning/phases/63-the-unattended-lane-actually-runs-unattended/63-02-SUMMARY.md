---
phase: 63-the-unattended-lane-actually-runs-unattended
plan: 02
subsystem: infra
tags: [sweep, launchd, real-scheduler-proof, shell, operator-claude-plugin]

requires:
  - phase: 63-01
    provides: "operator-claude-plugin/scripts/sweep_shim.py, the staleness self-check in
      lv-sweep-run.sh, and SWEEP-CRON-TEMPLATE.md's shim-pinned schedule + re-point step"
provides:
  - "scripts/verify_sweep_shim_scheduler.sh — a self-contained, re-runnable harness that
    proves the shim under a real launchd fire, not an interactive invocation"
  - "63-SWEEP-SHIM-SCHEDULER-PROOF.md — the dated record with verbatim observed log lines"
  - "closure of the sweep-crontab todo, all three mitigations recorded as landed"
affects: [any future phase touching operator-claude-plugin/scripts/sweep_shim.py or
  the sweep trigger contract]

actuals:
  tokens: 3550
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "real-scheduler proof pattern: register a uniquely-labelled temporary launchd agent
      under mktemp -d, observe genuine fires by polling a shared log for CONTENT (never
      line count/position), tear down on EXIT/INT/TERM, confirm removal with an
      INDEPENDENT launchctl list read rather than trusting the unload command's own status"
    - "marker-via-notices: since the shim always execs the newest resolved root (the
      wrapper's own staleness self-check therefore never fires under the shim's normal
      flow), a per-version stubbed sweep_entry.py reports one notice whose headline IS a
      distinguishing marker string, giving the wrapper's own stamp() call a
      version-attributable line in the shared log"

key-files:
  created:
    - scripts/verify_sweep_shim_scheduler.sh
    - .planning/phases/63-the-unattended-lane-actually-runs-unattended/63-SWEEP-SHIM-SCHEDULER-PROOF.md
  modified:
    - .planning/todos/pending/2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md

key-decisions:
  - "Launchd, not cron, per the plan's own resolved decision: crontab -e / crontab -
    replaces the WHOLE user crontab, so a temporary cron line risks destroying the
    operator's real sweep entry on restore — exactly the failure this phase removes.
    A temporary launchd agent with a unique per-run label (embedding this run's own
    PID) is additive, removable by label, and touches no other job."
  - "Distinguish the update-follow failure from the never-fired failure by snapshotting
    the pre-update marker line COUNT and comparing after a phase-2 timeout: a count that
    grew means fires continued but stayed stuck on the old version (a real defect); an
    unchanged count means no fire was observed at all (inconclusive). This only decides
    which of two FAILURE messages to print — pass/fail is still decided by marker
    CONTENT, never by count, matching the plan's explicit prohibition."

requirements-completed:
  - 2026-08-04-sweep-crontab-pins-a-versioned-plugin-path

coverage:
  - id: D1
    description: "A genuine scheduled fire (launchd, StartInterval 60s, no RunAtLoad —
      not an interactive sh invocation) resolves through the installed shim to the
      newest install root, proven by a log line the operator's session did not write."
    requirement: 2026-08-04-sweep-crontab-pins-a-versioned-plugin-path
    verification:
      - kind: other
        ref: "3 live runs of scripts/verify_sweep_shim_scheduler.sh (labels .60167,
          .63000, .66254), each observing marker SWEEP_PROOF_MARKER_1_1_0 in the
          harness's temporary log within 60s of a genuine launchd fire"
        status: pass
    human_judgment: false
  - id: D2
    description: "After a newer version directory appears between two scheduled fires,
      the second fire runs the new root with no edit to the schedule and no edit to
      the shim."
    requirement: 2026-08-04-sweep-crontab-pins-a-versioned-plugin-path
    verification:
      - kind: other
        ref: "same 3 live runs: each observed marker SWEEP_PROOF_MARKER_1_2_0 within
          60s of the next fire after a 1.2.0 directory was added mid-run with no
          plist/shim edit"
        status: pass
    human_judgment: false
  - id: D3
    description: "The proof harness removes every scheduler registration it created,
      confirmed by an INDEPENDENT read rather than the removal command's own status,
      and leaves no residue across two runs in a row."
    verification:
      - kind: other
        ref: "post-run `launchctl list | grep -c com.lightningvisuals.sweep-shim-proof`
          returned 0 after each of the 3 live runs, run independently of the harness's
          own teardown trap"
        status: pass
    human_judgment: false
  - id: D4
    description: "The proof runs against an isolated world, spending zero network
      calls, zero provider credits, zero n8n executions, zero HubSpot writes, and
      contains no crontab invocation of any form (D-63-03)."
    verification:
      - kind: other
        ref: "grep -v '^\\s*#' scripts/verify_sweep_shim_scheduler.sh | grep -c crontab
          -> 0; stub sweep_entry.py is a bare print() with no HTTP/socket/credential
          reference in any of the 3 version directories the harness builds"
        status: pass
    human_judgment: false

duration: 26min
completed: 2026-09-02
status: complete
---

# Phase 63 Plan 02: The unattended lane actually runs unattended — sweep launcher real-scheduler proof Summary

**A temporary, uniquely-labelled launchd agent proved the sweep launcher shim resolves and follows a simulated plugin update under a genuine scheduled fire — run three times live, every run exiting 0 with the registration independently confirmed removed — closing the sweep-crontab todo that the shim alone (63-01) could not close on its own.**

## Performance

- **Duration:** ~26 min
- **Started:** 2026-09-02T06:07:00Z (approx)
- **Completed:** 2026-09-02T06:33:34Z
- **Tasks:** 2 (both `type="auto"`)
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- `scripts/verify_sweep_shim_scheduler.sh` — a `/bin/sh`, `set -u` harness that builds
  an isolated `mktemp -d` plugin world (real copies of `sweep_shim.py`,
  `durable_paths.py`, `lv-sweep-run.sh` under `1.0.0`/`1.1.0`, each with a stubbed,
  marker-carrying `sweep_entry.py`), installs the shim via its real CLI pointed only
  at that temp world, registers a real launchd agent whose label embeds a fixed
  prefix plus this run's own PID, and polls the shared log for version-attributable
  marker CONTENT (never line count or position) across two observation phases
  separated by a simulated `1.2.0` update with no plist or shim edit.
- Teardown runs from a `trap` on `EXIT INT TERM` guarded against double-execution,
  unloads the launchd agent, and confirms its absence with an INDEPENDENT
  `launchctl list` read rather than trusting the unload command's own exit status —
  a failed teardown prints the label to remove by hand rather than being swallowed.
- **Live proof, run three times**, all three exiting 0: each observed the first fire
  resolve `1.1.0` at exactly 60s (matching `StartInterval`), then observed the next
  fire resolve `1.2.0` at exactly 60s after the simulated update, with zero residual
  launchd registration confirmed independently after every run.
- `63-SWEEP-SHIM-SCHEDULER-PROOF.md` records the recorded run's verbatim log lines
  (`SWEEP_PROOF_MARKER_1_1_0` at `16:31:07`, `SWEEP_PROOF_MARKER_1_2_0` at `16:32:07`),
  the harness exit code, the independent teardown read, an explicit zero-cost
  statement (network/credits/n8n/HubSpot/crontab), and an honest "what this does NOT
  prove" section naming the twelve already-installed directories on this machine and
  the self-check's version-bound reach (a schedule pinned to `0.33.0` or earlier still
  runs a wrapper carrying no self-check at all).
- The sweep-crontab todo gained a dated Closure section naming all three landed
  mitigations (shim, self-check, re-point docs) with file paths, while its prior
  "Status (rewritten 2026-09-02)" history stays untouched and the file stays in
  `pending/` — moving it is the phase seal's job, not this plan's.

## Task Commits

1. **Task 1: Build the isolated real-scheduler proof harness** - `3cbaf6f` (feat)
2. **Task 2: Run the proof, record it, amend the todo** - `cbac043` (docs)

## Files Created/Modified

- `scripts/verify_sweep_shim_scheduler.sh` - the harness (new)
- `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-SWEEP-SHIM-SCHEDULER-PROOF.md` - dated proof record (new)
- `.planning/todos/pending/2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` - dated Closure section appended, `updated:` bumped

## Decisions Made

- **Launchd over cron** — CONTEXT.md's Specific Idea named a cron tick, but the plan's
  objective resolved this before execution: `crontab -` replaces the whole user
  crontab, and a bad restore would destroy the operator's real sweep entry, exactly
  the failure this phase exists to remove. A temporary, uniquely-labelled launchd
  agent is additive and removable by label — no restore step, no whole-crontab
  mutation, ever.
- **Marker via a stubbed notice, not the wrapper's built-in staleness line** — the
  shim always execs the wrapper with the ALREADY-resolved newest root as `$1`, so the
  wrapper's own "running from X, newest is Y" staleness branch never fires in this
  flow (it only fires when something else invokes the wrapper directly with a stale
  root, which is not what a shim-fronted schedule ever does). Each version directory's
  stub `sweep_entry.py` instead reports one notice whose headline is the version's
  marker, which lands verbatim in the log via the wrapper's own `stamp("$OUT")` call —
  proof by the REAL wrapper's REAL code path, not a bypass of it.
- **Two-count comparison decides which failure message to print, not which run passes**
  — on a phase-2 timeout, comparing the `1.1.0` marker's line count before/after
  distinguishes "fires continued but stuck on the old version" from "no fire observed
  at all," satisfying the plan's requirement for five distinguishable failure messages
  without ever using a count to decide a PASS.

## Deviations from Plan

None - plan executed exactly as written. All three live runs passed on the first
attempt with no debugging cycles required.

## Issues Encountered

None. One incidental note: `git commit -m "$(cat <<'EOF' ... EOF)"` failed to parse
for the Task 2 commit message (an apostrophe inside the heredoc body tripped the
outer shell's quoting when passed through the tool layer) — worked around by writing
the message to a scratch file and using `git commit -F`. Not a plan or code issue.

## User Setup Required

None - no external service configuration required. The harness registers and removes
its own temporary launchd agent entirely within its own run; nothing was left
installed on this machine, and no real plugin cache directory, real schedule, or
crontab was ever touched.

## Next Phase Readiness

- The sweep-crontab todo (`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md`)
  now carries a full closure record and stays in `pending/` awaiting the phase seal
  to move it, per this plan's own instruction not to move it itself.
- 63-A (the sweep launcher half of Phase 63) is now both code-complete (63-01) and
  proven under a real scheduler (63-02). The one remaining path to this machine's
  twelve already-installed stale directories is the admin-facing one-time re-point
  documented by 63-01 Task 3 — explicitly out of scope for any plan in this phase
  (D-63-03).
- 63-B (the judge model routing) was already resolved by 63-03 (verdict DROP — the
  cheaper-model lever does not ship, per D-63-06's own rule). Remaining phase 63 work,
  if any, is deployment (D-63-08) and closing out the phase.

## Self-Check: PASSED

- `scripts/verify_sweep_shim_scheduler.sh` — FOUND, executable
- `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-SWEEP-SHIM-SCHEDULER-PROOF.md` — FOUND
- `.planning/todos/pending/2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — FOUND at original path, prior "Status (rewritten 2026-09-02)" section intact (line 14), new "Closure (2026-09-02, Phase 63 plans 01 and 02)" section appended (line 97)
- Commits `3cbaf6f`, `cbac043` — both present in `git log --oneline`
- `/bin/sh -n scripts/verify_sweep_shim_scheduler.sh` — SYNTAX_OK
- `grep -c crontab` (comments stripped) — 0
- `grep -c launchctl` — 9 (>= 3 required: load, unload, list)
- 3 live harness runs — all `harness_rc=0`, all `launchctl list` residue counts `0`

---
*Phase: 63-the-unattended-lane-actually-runs-unattended*
*Completed: 2026-09-02*
