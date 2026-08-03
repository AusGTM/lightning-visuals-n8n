# 32-02 / RB-8 re-run — the live notice gate against the LLM-free wrapper

**STATUS: SCAFFOLD — awaiting the live gate (Task 2).** This file is seeded ahead of the
checkpoint so its shape is fixed before any observation lands in it. Every `[TO BE OBSERVED]`
slot below must be replaced with what the gate actually saw, verbatim, before this file is
considered the phase's findings record. Nothing in this scaffold is a claim.

Mirrors `29-06-FINDINGS.md`'s structure (step-by-step narrative, an evidence table, a verdict
table with one row per RB-8 step) so the two runs read side by side.

---

## Pre-flight

[TO BE OBSERVED: was the installed plugin cache current, or did it need refreshing per RB-7
step 0's two traps (push to origin, `git fetch --depth=1` + `reset --hard` on the marketplace
clone, `rsync` the cache excluding `config/operator.local.json`)? Record what was found.]

## Step 1 — install the trigger

[TO BE OBSERVED: install source (must be `SWEEP-CRON-TEMPLATE.md` verbatim — plugin root, venv
python path, log path), whether the crontab was empty beforehand, the cadence used for the gate
window (temporary vs. shipped `0 */4`).]

## Step 2 — silence check

[TO BE OBSERVED: log lines from the live fire(s), verbatim. State PASS if a fire produced either
exactly one healthy stamped line or a full notice; state PARTIAL — and only for the ring-fenced
reason — if execution 1173 is still inside the live 100-execution window
(`.planning/todos/pending/2026-08-03-sweep-lookback-has-no-time-window`); state FAIL only if a
fire produced nothing at all.]

| Live state at gate time | Correct behaviour | Observed |
|---|---|---|
| Apollo balance `unreadable: true` | must NEVER read as out of credits | [TO BE OBSERVED] |
| provider `credential_health.state: unknown` | must NEVER fire as broken | [TO BE OBSERVED] |
| review/queue counters | notice iff genuinely non-zero | [TO BE OBSERVED] |
| wedged runs | notice iff genuinely present | [TO BE OBSERVED] |
| backend armed/disarmed | notice iff genuinely armed | [TO BE OBSERVED] |
| execution 1173 (if still in window) | fires — expected, not a defect | [TO BE OBSERVED] |

## Step 2b — the loud-failure proof

[TO BE OBSERVED: interpreter substituted (expect system `python3`), the banner text observed, the
exit code, the failure line appended to the log, and confirmation the correct venv-python
argument was restored immediately afterward.]

## Steps 3 & 4 — notice check and quality

[TO BE OBSERVED: whether a real errored execution was present and preferred over a seeded
condition, or whether the zero-backlog re-seed onto company `9604614548` was used instead. Full
notice JSON and banner text, verbatim.]

| Criterion | Result |
|---|---|
| arrives in the place 29-01 recorded | [TO BE OBSERVED] |
| legible at the observed length ceiling | [TO BE OBSERVED] |
| states the cause in plain language | [TO BE OBSERVED] |
| states whether operator or admin can act | [TO BE OBSERVED] |
| contains NO instruction to run a command or open a terminal | [TO BE OBSERVED] |
| declares its own read-only nature | [TO BE OBSERVED] |
| honest about inference (never dresses a guess as a fact) | [TO BE OBSERVED] |
| **NEW: arrived with no session open** (log timestamp vs. cron fire time) | [TO BE OBSERVED] |

## Step 5 — restore

[TO BE OBSERVED: cadence restored to shipped `0 */4`, interpreter argument confirmed correct,
crontab line/schedule removed if temporary, any seeded review candidate cleared.]

## Step 6 — no writes, no credits

| Check | Evidence |
|---|---|
| No HubSpot write | [TO BE OBSERVED] |
| No n8n write | [TO BE OBSERVED] |
| Structurally read-only | `test_sweep_read_only.py` — [TO BE OBSERVED: pass count] |
| Provider credits | [TO BE OBSERVED: balances before/after] |

## Close-out — machine restored

[TO BE OBSERVED: final crontab/launchd state, confirmation nothing armed.]

## Divergences from what Phase 32 predicted

[TO BE OBSERVED: this section is the most valuable content in the file per the plan's own
instruction — record any surprise here rather than smoothing it. If none occurred, state that
explicitly rather than leaving this section silently empty.]

## Verdict

| RB-8 step | Result |
|---|---|
| 1 — install the trigger | [TO BE OBSERVED] |
| 2 — silence check | [TO BE OBSERVED] |
| 2b — loud-failure proof | [TO BE OBSERVED] |
| 3 — notice check | [TO BE OBSERVED] |
| 4 — notice quality | [TO BE OBSERVED] |
| 5 — restore | [TO BE OBSERVED] |
| 6 — no writes, no credits | [TO BE OBSERVED] |
| **NOTICE-03 — unattended delivery** | [TO BE OBSERVED] |
