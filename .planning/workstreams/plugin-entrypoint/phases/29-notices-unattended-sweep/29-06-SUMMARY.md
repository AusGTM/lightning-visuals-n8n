---
phase: 29-notices-unattended-sweep
plan: 06
subsystem: operator-claude-plugin
tags: [sweep, skill, cron-template, live-gate, notice-03-blocked]
requires:
  - sweep_entry.run_sweep / sweep_conditions (29-05)
  - watch.py (29-04)
  - 29-03's import-graph read-only guard
provides:
  - skills/backend-sweep/SKILL.md
  - skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
  - sweep_entry._cli_main (runnable entrypoint)
affects:
  - NOTICE-03 (BLOCKED — see below), NOTICE-05 (satisfied)
key-files:
  created:
    - operator-claude-plugin/skills/backend-sweep/SKILL.md
    - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
    - .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-06-FINDINGS.md
  modified:
    - operator-claude-plugin/scripts/sweep_entry.py
    - operator-claude-plugin/tests/test_sweep_read_only.py
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
---

# 29-06 — the sweep skill, the trigger template, and the live gate that failed

**Status: TASKS 1–2 COMPLETE. TASK 3 (RB-8) RUN AND FAILED ON ITS CENTRAL CLAIM.**

Suites at completion: **889 plugin / 1770 root pytest / 550 node**, all green. Committed
`eb027d3` (skill + template + guard), `300009c` (README/CHANGELOG two-part install).

## What was built

`skills/backend-sweep/SKILL.md` and `SWEEP-CRON-TEMPLATE.md`, plus a runnable
`sweep_entry._cli_main`. The template reproduces `29-HOST-PROBE.md` §A1's exact invocation and §A5's
delivery mechanics — a one-line `osascript` banner with full detail redirected to a log.

**Deviation (Rule 3, auto-fixed):** `sweep_entry.py` had no CLI entrypoint — it had only ever been
driven from tests — while the skill's whole job is to run `python3 scripts/sweep_entry.py`. Added
`_cli_main()`, failing closed like `run_sweep`'s own `ConfigError` branch: a raised exception in a
cron wrapper prints nothing, and **nothing is indistinguishable from healthy**, so a config failure
now returns an admin-attributed `sweep_not_configured` notice instead of a traceback.

## The live gate — full evidence in `29-06-FINDINGS.md`

**Passed:** notice quality on all seven RB-8 step-4 criteria (plain-language cause, names who can
act, no command/terminal instruction, fits the banner budget, declares its own read-only nature,
carries raw evidence, and honestly self-labels inference via `is_interpretation`); five of six
condition families correctly silent on live data including the two honesty traps (Apollo balance
unreadable, provider credential state unknown); zero HubSpot writes; zero provider credits; and the
import-graph guard's 11 tests proving no write path is reachable.

**Failed — NOTICE-03.** The cron fire produced no sweep. Same binary, same prompt file, same
`--allowedTools`, installed verbatim from the shipped template; it died on an expired credential
with an empty `refresh_token` and on `node: command not found` from cron's minimal PATH. **No banner
fired**, so the operator sees precisely what a healthy backend looks like.

The manual headless invocation minutes earlier succeeded — which is exactly why `29-01`'s host probe
missed this. It ran `claude -p` from an interactive shell (inheriting a live session's credentials
and PATH) and recorded the host as "headless `claude -p` (the thing a macOS cron/launchd job runs)".
It proved *headless*; it did not prove *unattended under cron*, which is what NOTICE-03 requires.
**Same class as the stored-vs-running reload gap: a verification performed one layer away from the
claim it was taken to establish.**

## Requirement status

| Requirement | Status | Basis |
|---|---|---|
| NOTICE-01, NOTICE-02 | Complete | 29-04's bounded watch, two terminal reports, no third outcome |
| NOTICE-04 | Complete (unit) / Partial (live) | Silence discipline is unit-proven; live silence unobservable while one real failed run sits in the fixed 100-execution window |
| NOTICE-05 | Complete | Two-part install documented in README + template, explicitly not a side effect of installing the plugin |
| **NOTICE-03** | **BLOCKED** | The unattended trigger does not deliver. Needs a credential mechanism cron can reach plus an absolute PATH, or a different host. A design decision, not a patch — left open rather than guessed at. |

## Three follow-ups this plan generates

1. **The cron credential/PATH failure** — blocks NOTICE-03 and therefore Phase 29's seal.
2. **The windowless lookback** — `recent_executions` reads a fixed 100 rows with no time bound, so a
   failed run keeps notifying until 100 newer executions displace it. Execution 1173's cause was
   fixed by Phase 31 and it will still fire for hours, with no way to acknowledge it.
3. **The notice cannot name the failing workflow** — n8n's executions API carries no name field, so
   the text reads "an unnamed workflow". `n8n_read.list_workflows` exists; one extra read would fix
   it.
