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

## Solution — SETTLED AND PROVEN 2026-08-03, remove the LLM from the trigger

The three candidates first listed here (API key in cron's env / launchd in the GUI session /
a different host) all treated the symptom. **The real finding is upstream: the sweep does not need
an LLM at all**, and the LLM is the sole source of the failure.

**Evidence, measured not argued:**

1. `sweep_entry.py` run under `env -i HOME=... PATH=/usr/bin:/bin` with **no credentials of any
   kind** produced the byte-identical notice JSON, exit 0. The sweep is deterministic Python —
   29-03 built it that way on purpose, behind an import-graph guard.
2. The `claude -p` wrapper's entire contribution is printing JSON Python already printed, and
   shelling `osascript`. In exchange it brings token expiry, Keychain dependence, `node` on PATH,
   per-fire token cost, and nondeterminism in a path that must be deterministic.
3. A ~30-line `sh` wrapper (run the script, one `osascript` per notice, log the JSON) **fired
   successfully under REAL cron with no session open** at 22:54:21 — the same trigger that failed
   at 18:40 with the LLM in it.

**It also closes the more dangerous half.** The shipped design fails SILENTLY: if the trigger cannot
run, no banner fires and the operator sees exactly what health looks like. The wrapper exits
non-zero **and posts a banner saying the sweep itself is broken** — demonstrated by pointing it at a
python without `requests`. That is a requirement the milestone wanted and never wrote down.

**Cost:** the plugin needs its own venv — its `requirements.txt` (requests, PyYAML, openpyxl) already
exists, and system python3 lacks them. That becomes part of the two-part admin install NOTICE-05
already documents. In exchange: no credential management, no per-fire token spend, no silent death.

**Not a violation of "Claude is the only interface"** — that governs the *operator's* surfaces.
NOTICE-03 is by definition the case where nobody is watching, so there is no conversation for
Claude to be the interface to.

### To implement

- Ship the wrapper as `skills/backend-sweep/lv-sweep-run.sh` (or equivalent) alongside the template.
- Rewrite `SWEEP-CRON-TEMPLATE.md`: cron calls the wrapper, not `claude -p`; drop the prompt file;
  document the venv step; keep the cadence reasoning (the balance-probe cost floor is unchanged).
- Amend `29-HOST-PROBE.md` D-01: the host is **cron/launchd → the plugin's own Python**, not
  `claude -p`. Record WHY the original probe misled — it ran `claude -p` interactively and recorded
  it as equivalent to the cron host.
- Two-sided test: the wrapper's contract with `sweep_entry.py`'s output shape, pinned from both ends.
- Re-run RB-8 against the new trigger.
