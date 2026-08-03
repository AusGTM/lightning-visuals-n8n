---
created: 2026-08-03T08:45:00.000Z
title: Sweep cron trigger cannot authenticate — blocks NOTICE-03
area: planning
severity: blocker
files:
  - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
  - .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-06-FINDINGS.md
  - .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-HOST-PROBE.md
---

## Problem

Found by RB-8 live, 2026-08-03. **NOTICE-03 requires a sweep that reaches the operator with no
session open. The shipped trigger does not deliver.**

Installed verbatim from `SWEEP-CRON-TEMPLATE.md`. The cron fire produced no sweep:

```
API Error: Access token at ~/.config/anthropic/credentials/default.json has expired
and no refresh is available (client_id set, refresh_token empty)
SessionEnd hook [node ...] failed: /bin/sh: node: command not found
```

Two structural cron-environment failures: (1) `claude -p` under cron cannot obtain a usable
credential — the interactive session's token is not reachable without a user session (macOS
Keychain); (2) `node` is absent from cron's minimal PATH.

**The failure is silent.** No banner fires, so the operator sees exactly what a healthy backend
looks like. The template names this hazard itself as "a known, accepted gap"; it is now the
observed state of the shipped artifact.

**Why 29-01's probe missed it:** it ran `claude -p` from an interactive shell, inheriting live
credentials and PATH, then recorded the host as "headless claude -p (the thing a macOS
cron/launchd job runs)". It proved headless, not unattended-under-cron. Same class as the
stored-vs-running reload gap — verification one layer away from the claim.

## Solution

TBD — a design decision, deliberately not guessed at. Candidates:

1. A long-lived API key exported in the cron line's own environment rather than the interactive
   OAuth token, plus absolute paths / an explicit `PATH=` in the crontab so `node` resolves.
2. A launchd agent loaded into the user's GUI session (`launchctl bootstrap gui/$UID`), which may
   retain Keychain access where cron does not — needs probing, not assuming.
3. A different host entirely (the backend schedules itself and pushes, rather than a local poller).

**Whatever is chosen must be probed under the REAL trigger, not an interactive approximation.**
That is the specific mistake this bug exists to stop repeating.

Also fix the silent-failure mode itself: a trigger that cannot run should be detectable, or the
"never fired" and "healthy" states stay indistinguishable.
