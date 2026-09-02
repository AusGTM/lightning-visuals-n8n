# Real-scheduler proof: the sweep launcher shim resolves and follows an update under launchd

**Date:** 2026-09-02
**Harness:** `scripts/verify_sweep_shim_scheduler.sh`
**Host:** macOS (Darwin), `launchctl` present and usable for the current user session.

## Why this proof exists

Memory `sweep-trigger-llm-free` records that this project's earlier unattended-trigger design
passed its own host probe **interactively** and still failed **silently** under a real cron tick,
because the interactive run inherited an environment (session credentials, PATH, controlling
terminal) that the scheduler never has. An `sh path/to/shim` invocation from a live session
therefore proves nothing about the case that matters. This harness instead registers a real,
temporary launchd agent and waits for genuine scheduled fires.

## What was run, and the result

The harness was run **three times** across this task (Task 1's own acceptance criterion requires
running it twice in a row; Task 2's `<verify>` block requires a further run). All three runs
passed, and each is independently reproducible — the harness embeds no state between runs beyond
what it creates and removes in its own `mktemp -d` work directory.

| Run | Launchd label | Phase 1 wait | Phase 2 wait | Exit code | Post-run `launchctl list` residue |
|---|---|---|---|---|---|
| 1 | `com.lightningvisuals.sweep-shim-proof.60167` | 60s | 60s | 0 | 0 |
| 2 | `com.lightningvisuals.sweep-shim-proof.63000` | 60s | 60s | 0 | 0 |
| 3 (recorded run) | `com.lightningvisuals.sweep-shim-proof.66254` | 60s | 60s | 0 | 0 |

### Recorded run (run 3) — verbatim evidence

**Launchd label used:** `com.lightningvisuals.sweep-shim-proof.66254`

**The two observed log lines, verbatim, from the harness's temporary log
(`$WORK/sweep.log`, `$WORK` removed by teardown after the run):**

```
[2026-09-02T16:31:07+1000] [{"headline": "SWEEP_PROOF_MARKER_1_1_0"}]
[2026-09-02T16:32:07+1000] [{"headline": "SWEEP_PROOF_MARKER_1_2_0"}]
```

The first line is the genuine scheduled fire that resolved through the installed shim to the
`1.1.0` version directory (the newest install present in the temporary cache root at that
moment — the harness's cache root at that point held only `1.0.0` and `1.1.0`). The second line
is the NEXT genuine scheduled fire, observed after the harness added a `1.2.0` version directory
to the same temporary cache root **with no edit to the launchd plist and no edit to the installed
shim file** — the simulated plugin update. The ISO timestamps embedded by the wrapper's own
`stamp()` call show the two fires **60 seconds apart** (`16:31:07` → `16:32:07`), matching the
plist's `StartInterval` of 60.

**Harness exit code:** `harness_rc=0` (captured immediately after the harness process exited, per
the run's own `echo "harness_rc=$?"` wrapper).

**Teardown / independent read:** the harness's own trap printed
`teardown confirmed: no job carrying prefix 'com.lightningvisuals.sweep-shim-proof' remains`
before exiting. A SEPARATE, independent shell command run immediately after the harness process
exited confirmed the same fact from outside the harness:

```
$ launchctl list | grep -c "com.lightningvisuals.sweep-shim-proof"
0
```

### Cost — explicit statement

This proof made:

- **Zero network calls.** The temporary `sweep_entry.py` stub used in every version directory is
  `print('[{"headline": "<marker>"}]')` — no HTTP client, no socket, no DNS lookup.
- **Zero provider credits.** No ZoomInfo/Apollo/Lusha/Anthropic call of any kind is reachable from
  the stub or from `lv-sweep-run.sh`'s own code path for a stubbed `sweep_entry.py`.
- **Zero n8n executions.** Nothing in the harness or the real wrapper it drives posts to any n8n
  webhook or backend endpoint; `lv-sweep-run.sh`'s only external call
  (`hubspot/backend-status`, per `SWEEP-CRON-TEMPLATE.md`) lives inside the REAL
  `sweep_entry.py`, which every version directory in this harness replaces with the stub above.
- **Zero HubSpot writes.** No HubSpot credential, API key, or portal ID is referenced anywhere in
  the harness or in the temporary world it builds.
- **Zero crontab contact.** The harness contains no `crontab` invocation of any form
  (`grep -v '^\s*#' scripts/verify_sweep_shim_scheduler.sh | grep -c crontab` reads `0`), and
  registers only a uniquely-labelled, temporary launchd agent that it tears down itself.

The one observable side effect on the host machine is a macOS Notification Center banner per
fire (the real `lv-sweep-run.sh`'s own `banner()` helper, invoked because the stub reports one
notice) — this is the trigger's own intended delivery mechanism working end to end, not a defect
of the proof.

## What this proves, and what it does NOT prove

**Proves:** under a genuine scheduler fire — not an interactive invocation, not a load-time
side effect (`RunAtLoad` was absent/false; both observed fires happened only after the
`StartInterval` elapsed) — the installed shim (a) resolves the newest installed plugin version
and execs that version's `lv-sweep-run.sh`, and (b) does so again correctly after a plugin
update, with zero edits to the schedule and zero edits to the shim itself, purely because the
shim re-resolves the newest install at every fire.

**Does NOT prove**, and this record says so explicitly rather than leaving it implied:

- **Nothing about this machine's own twelve already-installed version directories.** This proof
  ran against a synthetic, isolated cache root built fresh for the harness. The schedule this
  project cannot touch (D-63-03 forbids rewriting any crontab) still names whatever path it was
  written with on this machine. The mechanism that reaches that already-installed state is the
  **one-time admin re-point** documented by 63-01 Task 3 (`SWEEP-CRON-TEMPLATE.md`'s
  "Already have a schedule installed under the old shape? Re-point it once." subsection) — an
  admin action, not something this harness or this plan performs.
- **The staleness self-check's reach is version-bound.** The self-check landed by 63-01 lives
  inside the CURRENT `lv-sweep-run.sh` shipped in this plugin version. A schedule pinned to a
  versioned install directory from `0.33.0` or earlier — the newest directory this machine had
  cached as of the 2026-09-02 re-verification in the todo below — runs THAT directory's older
  wrapper, which does not contain the self-check at all. The self-check only starts protecting a
  given install once a schedule is either re-pointed to the shim (which then always runs the
  newest wrapper, self-check included) or freshly installed against a plugin version that already
  carries it.

## Harness re-run instructions

```
./scripts/verify_sweep_shim_scheduler.sh
echo "rc=$?"
```

Takes roughly 2-3 minutes of wall-clock waiting on two scheduled fires (measured: 60s + 60s +
setup/teardown overhead, all three runs). Do not shorten `StartInterval` below 60 in the harness
— a sub-minute interval stops being a representative scheduled fire.
