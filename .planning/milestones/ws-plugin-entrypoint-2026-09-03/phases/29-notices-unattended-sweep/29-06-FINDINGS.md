# 29-06 / RB-8 — the live notice gate

**Run 2026-08-03 by the session agent** under the operator's standing autonomous directive.
Read-only throughout: no arming, no deploy, no write to HubSpot or n8n. The only mutations were
machine-local (a prompt file, a temporary crontab line) and both are reverted at the end.

---

## Pre-flight — the installed plugin had to be refreshed first

RB-8 drives the **installed** plugin, and its cache was still at `0580045` — before phases 29 and
31 existed. Refreshed by the documented route (RB-7 step 0's two traps both applied):

1. Pushed to `origin/master` (`300009c`).
2. `git fetch --depth=1` + `reset --hard FETCH_HEAD` on the marketplace clone — it does **not**
   refresh on a plugin reinstall.
3. Synced the cache from the clone with `rsync -a --exclude='config/operator.local.json'`,
   after a `--dry-run`, and with the config backed up first — a reinstall **deletes** it.

**Verified by content, not version** (the version string is still a hand-written `0.1.0`):
`backend-sweep` skill present, `sweep` capability resolves.

**A known open bug died here, proven live.** `backend_status.fetch_backend_status` now returns
`available: True` against the live endpoint; it returned `False / unrecognized_response_shape` for
the whole of the preceding session. 29-05's array-unwrap fix is what closed it — every sweep
condition reads through that path, so without it this gate was impossible.

## Step 1 — install the trigger

Prompt saved verbatim from `SWEEP-CRON-TEMPLATE.md` to `~/.claude/lv-sweep-prompt.txt` (22 lines).
`claude` binary at `/Users/robertli/.local/bin/claude`. Crontab line installed with the template's
exact invocation and `--allowedTools "Skill,Bash,Read,Glob,Grep"`, at a temporary `*/5` cadence for
the gate window rather than the shipped `0 */4`. The crontab was **empty beforehand** — recorded so
the revert is provably clean.

## Step 2 — silence check — **PARTIAL, and the reason is a real finding**

**The sweep did not stay silent, because the backend genuinely is not healthy by its definition.**
It fired exactly one notice, for execution **1173** — the pre-fix review approve that returned
HubSpot 400 during the RB-9 canary, before Phase 31 fixed it.

That is the sweep working correctly, not a defect. But the full silence check **cannot be run
today**, and the reason is worth recording:

- `recent_executions` reads a **fixed page of 100 executions with no time window**
  (`EXECUTIONS_PAGE_LIMIT = 100`, `n8n_read.py:47`).
- Live window at gate time: ids **1125–1224**, containing exactly **one** error — 1173.
- So a failed run keeps firing **until 100 newer executions push it off the page**. At the
  maintenance workflow's observed ~8 executions/hour that is roughly six hours for this one, and
  on a quieter backend it would be days.

**The design question this raises:** a notice whose underlying cause is already fixed keeps
arriving every four hours, and there is no way to acknowledge it. NOTICE-04 exists because "a sweep
that speaks when healthy is one the operator learns to ignore" — an unclearable repeat notice
reaches the same destination by a different road. Not fixed here; recorded for a decision.

**What WAS proven, and it is the stronger half.** Of the six condition families, exactly one fired —
the one that was genuinely true. Five stayed correctly silent on live data, including both cases the
honesty rules single out:

| Live state at gate time | Correct behaviour | Observed |
|---|---|---|
| Apollo balance `unreadable: true` (`unrecognized_response_shape`) | must NEVER read as out of credits | silent ✅ |
| Lusha/Apollo/ZoomInfo `credential_health.state: unknown`, `reason: no_response` | `unknown` must NEVER fire as broken | silent ✅ |
| All four review/queue counters `0` | no backlog notice | silent ✅ |
| No wedged runs | no stuck notice | silent ✅ |
| Backend disarmed | no stuck-armed notice | silent ✅ |
| One real errored execution (1173) | fire | **fired** ✅ |

## Steps 3 & 4 — notice check — **PASS on genuinely real data**

No condition had to be arranged. **The runbook's own prescribed lever was unusable** — it says to
set the review-backlog threshold below the current real backlog, and the live backlog is `0` on all
four counters, so nothing can sit below it (amended in OPERATOR-RUNBOOK RB-8, commit `dfd1178`).
The real failed run made the seeding moot, which is a better result than either the original lever
or the re-seed the amendment proposed.

Notice delivered as designed: JSON detail to the log first, then one `osascript` banner per notice.
Log recorded `1 notice, 1 notification posted`.

**Every step-4 criterion checked and passed:**

| Criterion | Result |
|---|---|
| states the cause in plain language | PASS — "a run of … ended in status 'error' rather than succeeding" |
| states whether operator or admin can act | PASS — "Who can act: your n8n admin." |
| contains NO instruction to run a command or open a terminal | PASS |
| legible at the one-line banner budget | PASS — headline 66 chars |
| declares its own read-only nature | PASS — "This sweep only reads — nothing was changed, stopped, or retried." |
| carries raw evidence | PASS — `raw` + `execution_id: 1173` |
| honest about inference | PASS — `is_interpretation: true`, and the detail says so in words: "does not recognise this failure signature; the above is an interpretation rather than a known fact" |

That last row is the one worth keeping. The sweep did not dress a guess as a fact.

**GAP FOUND — the notice cannot name the workflow.** The headline reads "a run of **an unnamed
workflow** ended in status 'error'". Verified as an honest degradation rather than sloppiness:
n8n's `/executions/{id}` response carries `workflowId` and **no name field of any kind** (keys
confirmed live). But the admin the notice tells to act cannot tell *which* workflow failed, and the
fix is cheap — `n8n_read.list_workflows` already exists, so one extra read could map id → name.
Follow-up, not fixed mid-gate.

## ⛔ THE GATE'S CENTRAL CLAIM FAILS — the sweep does not work under cron

**NOTICE-03 requires a sweep that reaches the operator with no session open. It does not.**

The manual headless invocation at 18:35 succeeded (exit 0, notice rendered, banner posted). The
**cron** fire at 18:40 — the same binary, the same prompt file, the same `--allowedTools` set,
installed verbatim from `SWEEP-CRON-TEMPLATE.md` — produced no sweep at all. The log's only new
content was:

```
API Error: Access token at /Users/robertli/.config/anthropic/credentials/default.json has expired
and no refresh is available (client_id set, refresh_token empty)
SessionEnd hook [node "${CLAUDE_PLUGIN_ROOT}/hooks/session-end-cleanup.mjs"] failed:
/bin/sh: node: command not found
```

Two distinct environment failures, both structural to cron rather than to this plugin:

1. **Credentials.** `claude -p` under cron cannot obtain a usable token. Interactively the same
   command works, so the credential the interactive session uses is not reachable from cron's
   environment — the standard macOS pattern where a launchd/cron job has no user session and so no
   Keychain access. The error text names an expired token with an empty `refresh_token`.
2. **PATH.** `node` is not on cron's PATH (`/bin/sh: node: command not found`), so plugin hooks fail
   even before that.

**The failure mode is the dangerous one: it is SILENT.** No banner fired. The operator sees exactly
what a healthy backend looks like. `SWEEP-CRON-TEMPLATE.md` names this hazard in its own words — "a
sweep that never fires and a healthy backend look identical from the operator's side (this is a
known, accepted gap, tracked separately)". **That gap is no longer hypothetical; it is the observed
state of the shipped artifact.**

**Why 29-01's host probe did not catch this.** `29-HOST-PROBE.md` §A1 recorded "YES — on the host
`headless claude -p` (the thing a macOS cron/launchd job runs)". That probe was run from an
interactive shell, which inherits a live session's credentials and PATH. It proved `claude -p`
works headlessly; it did **not** prove it works *unattended under cron*, which is the actual
NOTICE-03 requirement. The parenthetical did the damage — it asserted equivalence between the host
probed and the host that matters. This is the same class of error as the stored-vs-running reload
gap: a verification performed one layer away from the thing it claimed to verify.

**Consequence:** Phase 29 cannot seal NOTICE-03 on this evidence. NOTICE-01/02 (bounded watch) and
NOTICE-04 (silence discipline, partially) stand; NOTICE-05's two-part install documentation stands.
The trigger needs either an explicit credential mechanism cron can reach (a long-lived API key in
the cron line's environment rather than the interactive OAuth token) plus an absolute `node`/PATH
export, or a different host entirely. That is a design decision, not a patch, and it is left open
rather than guessed at here.

## Step 5 — restore

No threshold was lowered (step 3 needed no lever), so nothing to restore there. The temporary `*/5`
crontab line and the prompt file are reverted in the close-out below.

## Step 6 — no writes, no credits

| Check | Evidence |
|---|---|
| No HubSpot write | Test company `9604614548` `hs_lastmodifieddate` still `2026-08-03T07:48:23.633Z` — before the sweep ran. `needs_review: false`, `industry: SPORTS`, unchanged. |
| No n8n write | Sweep touches only `GET /executions`, `GET /workflows`, and `POST hubspot/backend-status` (a read endpoint). No workflow mutated; artifacts remain disarmed. |
| Structurally read-only | `test_sweep_read_only.py` — **11 passed**. The import-graph guard proves no write path is even reachable from the sweep's module graph; this gate proves none was taken. |
| Provider credits | Balances before **3930 / 9301 / unreadable**, after **3930 / 9301 / unreadable** — **zero credits consumed**. `hubspot/backend-status` probes all three balance endpoints unconditionally per fire — balance reads, not enrich calls, so no enrichment credit is consumed. This is the known cost floor the cron template already documents. |


## Close-out — machine restored

- Temporary `*/5` crontab line removed; `crontab -l` is **empty**, exactly as found (the crontab was
  empty before the gate, recorded at install time so this is provable rather than assumed).
- `~/.claude/lv-sweep-prompt.txt` left in place — harmless, and Step 1 of the template overwrites it.
- No threshold was changed, so none needed restoring.
- HubSpot untouched; n8n artifacts disarmed; no arming at any point.

## Verdict

| RB-8 step | Result |
|---|---|
| 1 — install the trigger | PASS (installed verbatim from the shipped template) |
| 2 — silence check | **PARTIAL** — five of six condition families correctly silent on live data, including both honesty traps; full silence unobservable because one real failed run sits in the fixed 100-execution window |
| 3 — notice check | PASS, on genuinely real data (no lever needed; the runbook's prescribed lever was unusable against a zero backlog) |
| 4 — notice quality | PASS on all seven criteria, including honest self-labelling of inference. One gap: cannot name the failing workflow |
| 5 — restore | PASS |
| 6 — no writes, no credits | PASS — HubSpot unchanged, structurally read-only (11 tests), zero credits consumed |
| **NOTICE-03 — unattended delivery** | **FAIL — the cron fire produced no sweep and no notice, silently** |

**Two follow-ups this gate generates:** the cron credential/PATH failure (blocking NOTICE-03), and
the unclearable repeat notice from the windowless 100-execution lookback. The workflow-naming gap is
a third, smaller one.
