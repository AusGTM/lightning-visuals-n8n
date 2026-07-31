---
phase: 28-control-actions
plan: 02
subsystem: operator-claude-plugin
tags: [n8n-api, probe, diagnostic, gating, instance-guard, disarmed]
requires:
  - n8n_control.apply_mutation (28-01)
  - n8n_control.put_body (28-01)
  - n8n_read.get_workflow (27-01)
  - config_gate.require_capability capability "control" (28-01)
  - conftest fixture stub_module_transport_factory (28-01)
provides:
  - probe_n8n_semantics.roundtrip
  - probe_n8n_semantics.execute_probe
  - probe_n8n_semantics.cadence_reload
  - probe_n8n_semantics.interval_of
  - the ALLOW_N8N_PROBE gate shape 28-03's ALLOW_N8N_ARM must match (D-34)
affects:
  - 28-03 (arming lifecycle), 28-04 (cadence surface), 28-05, 28-06
tech-stack:
  added: []
  patterns:
    - an ALLOW_* env gate checked before any transport is constructed, exact-string "true" only
    - the wrong-instance guard applied to config["n8n_url"], the value the request authenticates with
    - an injected no-default wait_fn in place of a poll loop
key-files:
  created:
    - operator-claude-plugin/scripts/probe_n8n_semantics.py
    - operator-claude-plugin/tests/test_control_probe.py
  modified: []
decisions:
  - "The plan's sleep-poll loop is forbidden by Phase 26 D-07's AST guard; the guard was satisfied, not weakened — the wait is the operator's and the observation is one read"
  - "cadence_reload's wait_fn is required with no default, mirroring apply_mutation's verify_fn"
  - "A refusal here leaves an EMPTY call log, which is strictly stronger than 28-01's mutating_calls == [] — the gates run before any transport exists"
metrics:
  duration: ~50 min
  completed: 2026-07-31
status: awaiting-operator
requirements: [CONTROL-03, CONTROL-06]
---

# Phase 28 Plan 02: n8n Semantics Probe Summary

**Task 1 of 3 is built and committed. Tasks 2 and 3 are `blocking-human` live gates and were
not run — no live n8n call was made by this execution at all.** The probe exists so the
operator can now walk RB-5, which is what releases 28-03, 28-04, 28-05 and 28-06.

A disarmed CLI that answers this phase's three MEDIUM-LOW-confidence questions by observation
instead of inference, and that cannot arm anything, cannot run by accident, and cannot run
against the wrong tenant.

## What was built

`operator-claude-plugin/scripts/probe_n8n_semantics.py` — three subcommands, each driving
28-01's pipeline rather than its own HTTP:

| Subcommand | Question | Mechanism |
|---|---|---|
| `roundtrip <id>` | D-20 / Open Question 3: does this instance round-trip `settings` and `connections` through GET→PUT→GET? | `apply_mutation` with a no-op `mutate_fn` and an EMPTY allowed-node set. The body sent is `put_body(fetched)` with nothing changed in between, so the structural pre-flight diff passes trivially — which is itself the thing being proven. Reports `diff` naming which of the two keys failed to survive |
| `execute_probe <id>` | Research A2: does `POST /workflows/{id}/execute` exist on THIS account? | One POST. 404/405 → `expected` (confirms D-05a). 2xx → `finding` that overturns D-05a, reported and acted on nowhere. Anything else → `inconclusive`, which is "unanswered", not "answered negatively" |
| `cadence_reload <id> <node>` | D-18 / research A1: does the deactivate→PUT→activate bracket make a cadence change effective on a RUNNING instance? | Capture the live interval → change ONE node's `parameters.rule.interval` through `apply_mutation` with that node as the only allowed name → the operator's wait → one executions read → restore the CAPTURED interval through the same pipeline, with its own separate verdict |

### The three gates, and why the order matters

All three run **before any transport is constructed**, so a refusal leaves the recorder's
call log completely empty. That is strictly stronger than 28-01's `mutating_calls == []`
carve-out (D-35) — `apply_mutation` must fetch fresh before it can compute a refusal, but
these gates need no network to decide.

1. **`ALLOW_N8N_PROBE` must read exactly `true`.** Not `1`, `yes`, `TRUE`, `True`, `false`,
   `" true"` or unset — all seven refuse, each asserted. D-34 makes gating uniform across the
   repo's `ALLOW_*` switches; **28-03's `ALLOW_N8N_ARM` must use this exact shape**, because
   two gates in one phase that disagree about what counts as "on" teach the operator a rule
   that is false half the time. The refusal names the variable and says an admin sets it.
2. **`config_gate.require_capability(cfg, "control")`** — one credential source. A test spies
   on the call and asserts all three subcommands go through it, so the refusal is
   `config_gate`'s own words rather than a second hand-rolled check that could drift.
3. **The wrong-instance check, against `config["n8n_url"]`.** Shape borrowed from
   `deploy_n8n_workflows.py::_instance_ok()`; reimplemented, not imported (PLUGIN-04). The
   test sets `N8N_URL` in the environment to the *expected* host while the config carries a
   *different* genuine `.n8n.cloud` host — so an implementation that read the shell variable
   would pass the tenant check and this test fails it. `grep -c 'getenv("N8N_URL")'` → **0**.

### What the module cannot do

It contains no code path that writes a write-safety constant — it does not so much as *name*
one, so no later edit reaches for one by autocomplete. `! grep -q "ALLOW_HUBSPOT" <module>`
exits 0 (T-28-07). Arming remains 28-03's job behind its own human gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] The plan's poll-sleep loop is forbidden by a repo-wide AST guard**

- **Found during:** Task 1, on the first full-suite run.
- **Issue:** The plan's `<action>` specifies "wait a bounded number of minutes polling
  `GET /api/v1/executions`". `operator-claude-plugin/tests/test_report_sufficiency.py::
  test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` (Phase 26 **D-07**) forbids
  **every** plugin script from importing `time`, calling anything named `sleep()`, or
  containing a `while` loop — it reserves the bounded watch for Phase 29 so it is built once.
  No Phase 28 plan or context decision mentions this guard; D-28 named only the transport
  guard. This is the class of finding HANDOFF §7b predicts.
- **Fix — the guard was satisfied, not weakened.** Appending an exemption would have been the
  same mistake as appending to `_EXPECTED_SEND_SHAPED`. Instead:
  - `cadence_reload` takes **`wait_fn(message)`, required with no default**, mirroring
    `apply_mutation`'s `verify_fn`. The CLI supplies a prompt that blocks on the human who is
    *already standing at this `blocking-human` checkpoint*; tests inject a recorder.
  - The observation afterwards is **one** read of the workflow-filtered executions page, not a
    loop. n8n retains execution history, so a single read taken after the wait sees everything
    a poll would have accumulated — at one call instead of twenty.
  - Two things improve as a result: no unattended process holds a shortened schedule open, and
    the restore runs in the same process that made the change, so it cannot be orphaned by a
    lost terminal. `--wait-minutes` (default 10) now only shapes the prompt text.
- **Files:** `operator-claude-plugin/scripts/probe_n8n_semantics.py`
- **Commit:** `8a0763b`

**2. [Rule 1 — stale citation] The plan cites `_instance_ok()` at line 163; it is at line 199**

- `scripts/deploy_n8n_workflows.py::_instance_ok()` is at **199–209** (`_has_n8n` 195,
  `_writes_allowed` 212) as of this commit. The plan's 163–173 is stale by ~36 lines — the
  same drift class D-32's mechanical refresh fixed once already. The module's docstring cites
  the current line and flags that citation as a moving target.

### Not deviations, recorded so nobody "fixes" them

- **`cadence_reload` refuses on an inactive workflow.** The committed
  `wf_scheduled_maintenance_cloud.json` has `active: false`; the LIVE workflow may differ. If
  it is live-inactive, the reload question does not apply to it (activation is itself the load
  event by n8n's own model) and that is the finding to record — Task 3 step 1 already says so.
- **The probe uses `n8n_read._get_json` and `n8n_read._headers`** for the executions page,
  rather than opening a second way to read n8n. `n8n_control.py:91,95` set that precedent
  inside the same control family.

## Threat mitigations applied

| Threat | Where |
|---|---|
| T-28-07 EoP via the probe arming something | The module names no write-safety constant; asserted by grep and by a test |
| T-28-09 tampering via the wrong instance | The guard reads `config["n8n_url"]`; the test proves an environment-reading guard would fail it |
| T-28-32 EoP via the probe running unintentionally | Exact-string `true` only; unset and six near-miss values refuse with an EMPTY call log |
| T-28-08 self-inflicted credit burn | One node, one interval, restore through the same verified pipeline, a separate and prominent restore verdict, and a hand-restore instruction naming the committed JSON when it fails |
| T-28-10 repudiation | Every subcommand returns a structured verdict + detail; `28-FINDINGS.md` is Task 3's output and is **not yet written** |

## What is NOT done — the operator's two gates (RB-5)

**Tasks 2 and 3 were not run and must not be run by an agent.** Nothing was armed, deployed,
activated, or PUT; every network path in this plan ran against the in-process recorder.
`28-FINDINGS.md` does not exist yet — it records what the operator observes, and writing it
speculatively would defeat the entire purpose of the plan.

### Command lines, ready to paste

Preconditions, once per shell (do not persist `ALLOW_N8N_PROBE`):

```bash
cd /Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc
export N8N_EXPECTED_URL=https://alexherman.app.n8n.cloud   # the confirmed deploy tenant
export ALLOW_N8N_PROBE=true
```

`operator-claude-plugin/config/operator.local.json` must carry `n8n_url` (equal to
`N8N_EXPECTED_URL`) and `n8n_api_key`. The probe reads credentials from that file only — it
never reads `N8N_URL` / `N8N_API_KEY` from the shell, so the dotenv wrapper the backend
scripts need does not apply here. `N8N_EXPECTED_URL` is the one shell value it does read.

Find the live workflow id (read-only):

```bash
python3 -c "import sys; sys.path.insert(0,'operator-claude-plugin/scripts'); import config_gate, n8n_read; print([(w['id'], w['name'], w['active']) for w in n8n_read.list_workflows(config_gate.load_config()) or []])"
```

**Task 2 — RB-5 step 1: prove the gate is real (cheapest possible check, run it FIRST).**

```bash
env -u ALLOW_N8N_PROBE python3 operator-claude-plugin/scripts/probe_n8n_semantics.py roundtrip <workflow-id>
```
Expect: `"verdict": "refused"` naming `ALLOW_N8N_PROBE`, and no call made.

**Task 2 — the no-op round-trip (D-20).** Recommended target: `LV Scheduled Maintenance
(Cloud)` — its `settings` is `{}` in the committed JSON, so if any workflow round-trips
cleanly it is this one.

```bash
python3 operator-claude-plugin/scripts/probe_n8n_semantics.py roundtrip <workflow-id>
```
Expect `"verdict": "verified"` and `"diff": []`. A schema rejection naming *additional
properties* means the four-key filter is wrong and 28-01 needs a fix before anything else in
this phase proceeds. A `"diff": ["settings"]` means Open Question 3's community report applies
to this instance — record which nested key moved, from the printed `observed`.

**Task 2 — the execute-endpoint check (A2).**

```bash
python3 operator-claude-plugin/scripts/probe_n8n_semantics.py execute_probe <workflow-id>
```
Expect `"verdict": "expected"` with `status_code` 404 or 405, confirming D-05a. Record
`status_code` and `body` verbatim. A `"finding"` (2xx) overturns D-05a's premise — record it,
act on it nowhere in this phase.

**Task 3 — the cadence reload observation (D-18 / A1).** Only after `roundtrip` returned
`verified`. Recommended trigger: `Review Trigger (15 min)` — its downstream write gate is
disarmed, so extra fires perform reads only.

```bash
python3 operator-claude-plugin/scripts/probe_n8n_semantics.py cadence_reload <workflow-id> "Review Trigger (15 min)"
```

It changes the interval to 2 minutes, then **blocks on a prompt**. Let ~10 minutes pass, press
Enter, and it reads the executions and restores in one go. Then read three things:

- `spacing_minutes` at roughly `2.0` → the bracket works; 28-03 can rely on it. Spacing still
  at the old cadence for the whole window → the bracket is insufficient and 28-03 needs a
  different mechanism, which is exactly what this probe exists to find out.
- `restore_verdict` **must** read `verified`. If it does not, `detail` says so loudly and
  names the committed JSON to restore `Review Trigger (15 min)` from by hand
  (`[{"field": "minutes", "minutesInterval": 15}]`). Do not quietly tidy this.
- A `"verdict": "refused"` mentioning `active` means the live workflow is inactive — that
  makes the question unanswerable on this instance rather than answered. Record it as such.

Optional knobs: `--probe-interval-minutes` (default 2), `--wait-minutes` (default 10, prompt
text only).

**Then:** write `28-FINDINGS.md` recording, per question, what was run, what was observed
verbatim, and the resulting confidence — marking each answered, partially answered, or
unanswerable-on-this-instance.

## Test counts, with attribution

| Suite | Baseline (verified at start) | After | Δ mine |
|---|---|---|---|
| `.venv/bin/python -m pytest -q` (repo root) | 1290 passed, 1 skipped | **1350 passed, 1 skipped** | **+31** |
| plugin suite (`operator-claude-plugin/`) | 490 passed | **521 passed** | **+31** |
| `node --test tests/n8n/*.test.mjs` | 474 pass, 0 fail | **474 pass, 0 fail** | 0 |

**The root suite's +60 is not all mine.** 29 of it is `tests/test_check_hubspot_list_scope.py`,
the concurrent 25-01 executor's file, which landed on disk between my baseline run and my final
one (their commit `6d78f88` sits between my two). Confirmed by diffing per-file collection with
and without my module present: my file contributes exactly 31, theirs exactly 29, 31 + 29 = 60.
The plugin suite delta is clean at +31 because their file lives in the repo-root suite.

No flakes observed. No node file was touched.

## Non-vacuity: four mutants, each restored immediately

The RED phase was a collection error (the module did not exist), which fails everything at once
and therefore proves little. Mutation testing supplied the real guarantee:

| Mutant | Result |
|---|---|
| Env gate made case-insensitive (`.lower() == "true"`) | **2 failed** (`TRUE`, `True`) |
| Instance guard reads the shell's `N8N_URL` instead of `config["n8n_url"]` | **17 failed** |
| Restore re-applies the PROBE interval instead of the captured one | **3 failed** |
| `roundtrip`'s no-op mutates `settings` | **6 failed** |

Suite back to 31 passed after each restore.

## Safety posture

- **No live n8n call of any kind was made.** No arm, no deploy, no activation, no live PUT, no
  HubSpot call. Tasks 2 and 3 are untouched and remain `blocking-human`.
- `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → **0** across all 8 artifacts.
- `git diff --stat n8n/` → **empty**. `n8n/` was not opened for writing.
- `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` is **byte-identical**:
  sha256 `26bba4f2a7f71401e095846a81abc39119a5e87e48f254cb4f71721d2e2f97ad`, `git diff --stat`
  empty. `_EXPECTED_SEND_SHAPED` remains exactly two entries; the module takes
  `transport=requests` (bare module) and calls `transport.post` / `transport.get`.
- The operator's four in-flight 23-06 files were not read-modified, staged, or committed, and
  `STATE.md` was deliberately **not** updated (this plan is not complete).

## Verification performed

```
pytest operator-claude-plugin/tests/test_control_probe.py -q            -> 31 passed
! grep -q "ALLOW_HUBSPOT" .../probe_n8n_semantics.py                    -> exit 0
grep -c 'getenv("N8N_URL")\|getenv('N8N_URL')' .../probe_n8n_semantics.py -> 0
shasum -a 256 .../test_retry_reuses_dispatch.py                         -> 26bba4f2… (unchanged)
git diff --stat .../test_retry_reuses_dispatch.py                       -> empty
git diff --stat n8n/                                                    -> empty
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json                      -> 0
node --test tests/n8n/*.test.mjs                                        -> 474 pass, 0 fail
```

## Commits

| Commit | What |
|---|---|
| `7b3fdee` | `test(28-02):` the failing spec (RED — module absent) |
| `8a0763b` | `feat(28-02):` the probe module (GREEN) |

## Self-Check: PASSED

Files verified present: `operator-claude-plugin/scripts/probe_n8n_semantics.py`,
`operator-claude-plugin/tests/test_control_probe.py`.
Commits verified in `git log`: `7b3fdee`, `8a0763b`.
`28-FINDINGS.md` is correctly **absent** — it is Task 3's output, and Task 3 is the operator's.
