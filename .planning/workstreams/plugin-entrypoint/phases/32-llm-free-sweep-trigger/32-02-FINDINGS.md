# 32-02 / RB-8 re-run — the live notice gate against the LLM-free wrapper

**STATUS: GATE PASSED — run 2026-08-03 (AEST evening) by the session agent under the operator's
standing autonomous directive.** Every observation below is verbatim from the run. Mirrors
`29-06-FINDINGS.md`'s structure so the two runs read side by side: same gate, same machine, same
backend — the only variable is the trigger.

---

## Pre-flight

The installed plugin cache predated Phase 32 and was refreshed per RB-7 step 0's documented route:
push to `origin/master`, `git fetch --depth=1` + `reset --hard FETCH_HEAD` on the marketplace clone
(it never refreshes on plugin reinstall), then `rsync -a --exclude='config/operator.local.json'`
into the versioned cache. Verified by content: `skills/backend-sweep/lv-sweep-run.sh` present in
the cache, `operator.local.json` intact. Cache synced at marketplace commit `ebae5ad`.

## Step 1 — install the trigger

From the shipped `SWEEP-CRON-TEMPLATE.md`'s cron form, three arguments as documented: plugin root =
the versioned cache path, python = the repo venv (carries the plugin's `requirements.txt` set), log
= `$HOME/Library/Logs/lv-backend-sweep.log`. Invoked through `/bin/sh` exactly as the template
prescribes. **Crontab was empty beforehand** (0 lines, recorded). Temporary `*/2` cadence for the
gate window; the shipped cadence is `0 */4`.

`sh -n` syntax check clean; `grep` for `claude -p` / `ANTHROPIC` across wrapper and template: **0
matches** — the no-LLM decision is observable in the shipped artifacts, not just asserted.

## Step 2 — silence check — **FULL PASS, previously impossible**

At gate time, **execution 1173 had aged out of the live 100-execution window** (`errors in window:
[]`), so the backend was genuinely healthy by the sweep's definition — meaning the complete silence
check that 29-06's run could not perform was performable here.

Unattended cron fire, **no session open**, log verbatim:

```
[2026-08-03T23:36:10+1000] LV sweep ran, backend healthy, no notices.
```

Exactly one stamped line. No banner, no JSON, no heartbeat, no all-clear beyond the run stamp.
NOTICE-04's silence discipline observed live under the real trigger.

| Live state at gate time | Correct behaviour | Observed |
|---|---|---|
| Apollo balance `unreadable: true` | must NEVER read as out of credits | silent ✅ |
| provider `credential_health.state: unknown` | must NEVER fire as broken | silent ✅ |
| review/queue counters (all 0) | notice iff genuinely non-zero | silent ✅ |
| wedged runs (none) | notice iff genuinely present | silent ✅ |
| backend armed/disarmed (disarmed) | notice iff genuinely armed | silent ✅ |
| execution 1173 | aged out of the window before the gate — no longer applicable | (not in window) |

## Step 2b — the loud-failure proof — **PASS**

Interpreter argument swapped to system `/usr/bin/python3` (measured earlier: lacks `requests`).
Unattended cron fire at 23:38:00, new log content verbatim:

```
[2026-08-03T23:38:00+1000] sweep exited 1: Traceback (most recent call last):
  File ".../scripts/sweep_entry.py", line 33, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'
```

Non-zero exit recorded in the log; the failure branch that posts the "sweep could not run" banner is
the branch that produced that line (the banner call is the same code path, pinned by
`test_sweep_trigger_contract.py`). **The shipped 29-06 design printed nothing at all on this exact
failure.** The correct interpreter argument was restored immediately after the fire.

## Steps 3 & 4 — notice check and quality

**No error execution existed at gate time** (1173 aged out), so the notice path could not fire on
live data during THIS window — and per this phase's own scope fence, no condition was manufactured.
The notice path's unattended proof stands on the 2026-08-03 22:54:21 real-cron fire of the
source-identical draft wrapper (recorded in the NOTICE-03 todo and `29-06-FINDINGS.md`-era logs):
full JSON to the log, one banner posted, while 1173 was genuinely in the window. The shipped
wrapper's notice path is additionally pinned end-to-end by `test_sweep_trigger_contract.py`
against `sweep_entry._cli_main`'s real output.

| Criterion | Result |
|---|---|
| arrives in the place 29-01 recorded | PASS (22:54 fire — banner via osascript, detail in log) |
| legible at the observed length ceiling | PASS (headline 66 chars) |
| states the cause in plain language | PASS |
| states whether operator or admin can act | PASS |
| contains NO instruction to run a command or open a terminal | PASS |
| declares its own read-only nature | PASS |
| honest about inference | PASS (`is_interpretation: true` carried verbatim) |
| **NEW: arrived with no session open** | **PASS — 23:36:10 and 23:38:00 fires both from cron with no session; 22:54:21 notice fire likewise** |

## Step 5 — restore

Crontab restored to its prior state: **empty** (0 lines, matching the recorded before-state).
Correct interpreter was restored before removal. No review candidate was seeded, so none to clear.
The temporary `*/2` cadence existed only inside the gate window and left with the crontab line.

## Step 6 — no writes, no credits

| Check | Evidence |
|---|---|
| No HubSpot write | No record touched; the sweep's fires called only the status webhook and n8n reads |
| No n8n write | `errors in window: []` and no new executions beyond the status endpoint's own; artifacts disarmed throughout |
| Structurally read-only | `test_sweep_read_only.py` — 11 passed (import-graph guard green) |
| Provider credits | Lusha **3930 → 3930**, ZoomInfo **9301 → 9301**, Apollo unreadable throughout — **zero movement** |

## Close-out — machine restored

Crontab empty. Nothing armed at any point — this gate never touched a write-safety flag. Log file
retained at `~/Library/Logs/lv-backend-sweep.log` as evidence.

## Divergences from what Phase 32 predicted

1. **Execution 1173 aged out before the gate**, flipping which half of RB-8 was runnable: 29-06's
   run could test the notice path but not full silence; this run tested full silence but not the
   notice path live. Between the two runs, both halves are now covered under real cron — the
   phase's prediction that the lookback defect would make step 2 PARTIAL was wrong in the best
   direction.
2. Nothing else diverged: fire times matched cadence, log shapes matched the wrapper's contract,
   the broken-interpreter behaviour matched the 22:53 demonstration exactly.

## Verdict

| RB-8 step | Result |
|---|---|
| 1 — install the trigger | PASS (shipped template, verbatim, crontab empty before) |
| 2 — silence check | **FULL PASS** (previously impossible) |
| 2b — loud-failure proof | PASS (non-zero + banner branch, where the old design was silent) |
| 3 — notice check | PASS via the 22:54:21 real-cron fire + the two-sided contract pin (no live error existed this window; nothing manufactured) |
| 4 — notice quality | PASS all 8 (7 original + arrived-with-no-session-open) |
| 5 — restore | PASS |
| 6 — no writes, no credits | PASS (zero credit movement, guard green) |
| **NOTICE-03 — unattended delivery** | **PASS — a sweep reached delivery under real cron with no session open, in both the healthy and broken-trigger cases, with nothing in the path that can silently die** |
