# 28-FINDINGS — n8n semantics live gate (plan 28-02, RB-5)

**Run:** 2026-07-31 · **Operator:** Robert · **Tenant:** `alexherman.app.n8n.cloud`
**Target:** `LV Scheduled Maintenance (Cloud)`, workflow id `1fXPuIabz3RsAHgn`, `active: true`
**Probe:** `operator-claude-plugin/scripts/probe_n8n_semantics.py`

Two of the three questions are answered. **A1 is NOT** — see Q3, and do not let its "verified"
sub-results read as an answer to it.

---

## Q1 — Does this instance round-trip `settings` and `connections` through GET → PUT → GET? (D-20, Open Question 3)

**Run:** `roundtrip 1fXPuIabz3RsAHgn`

**Observed:** `"verdict": "verified"`, `"diff": []`. `settings` was `{}` before and `{}` after.
All 24 `connections` entries were byte-identical across the round-trip. The workflow's `active`
state was unchanged.

**Answer: YES — clean round-trip.** Confidence **HIGH**: this is a direct observation on the exact
workflow 28-03/28-05 will mutate, not an inference.

**Consequences:**
- **28-01's four-key PUT filter is correct on this instance.** No schema rejection naming
  additional properties, which was the failure that would have halted Phase 28 here.
- Research Open Question 3's community report of `settings` corruption **does not apply** to this
  tenant. Nothing in 28-03/04/05 needs a workaround for it.

**Incidental, worth keeping:** the `prior` body confirms the live workflow carries all four write
gates — `SJ-1 Set Requested Write Gate`, `SJ-2 Set Requested Write Gate`,
`Dedupe Set Needs Review Write Gate`, `Review Apply Update Write Gate` — matching the documented
maintenance 4/4. Live and committed agree on this workflow's gate topology.

---

## Q2 — Does `POST /workflows/{id}/execute` exist on this Cloud account? (Research A2)

**Run:** `execute_probe 1fXPuIabz3RsAHgn`

**Observed, verbatim:**
```
"verdict": "expected", "status_code": 405, "body": "{\"message\":\"POST method not allowed\"}"
```

**Answer: NO — the endpoint is absent.** Confidence **HIGH**.

**Consequence: amendment #5 / D-05a is confirmed against the live tenant**, not just against
upstream PR #20304 being unmerged. Off-cycle scheduled-scan execution stays dropped from CONTROL-01;
the operator re-times or enables/disables instead. 28-04 builds on this as settled.

---

## Q3 — Does the deactivate → PUT → activate bracket make a Schedule Trigger change effective on a RUNNING instance? (D-18, Research A1)

**Status: UNANSWERED. Do not record this as answered, and do not let 28-03 assume either result.**

**What was run:** `cadence_reload 1fXPuIabz3RsAHgn "Review Trigger (15 min)"`

**What happened:** the probe re-timed the trigger 15 min → 2 min (change **verified** by read-back),
then raised `EOFError` at its operator prompt, because it was run through a harness with **no
interactive stdin**. The executions read and the restore both sit *after* that prompt in
`cadence_reload`, so **neither ran**. The live schedule was left on the 2-minute interval.

**Remediation, completed the same session:** restored to the committed
`[{"field": "minutes", "minutesInterval": 15}]` through the same allowlisted
`n8n_control.apply_mutation` pipeline (not a hand-rolled PUT). Read-back before: `2`. After: `15`.
Restore verdict **verified**. `active: true` throughout — `apply_mutation` restores prior active
state inside each bracket, so no job was left disabled.

**Blast radius while shortened:** roughly ten minutes, so `Review Trigger (15 min)` fired about 5×
instead of about 1×. Its downstream is `Review Apply Update Write Gate`, which is **disarmed** —
reads only. No writes, no provider credits, no HubSpot mutations.

**What this does and does not establish:**
- **Established:** a `parameters.rule.interval` change PUTs cleanly and reads back correct on a
  running workflow, in both directions (15→2 and 2→15). The mutation pipeline itself works.
- **NOT established:** whether the *running scheduler* picks the new interval up — i.e. whether
  execution spacing actually changes. That observation requires the executions read that never ran.
  **A1 is precisely this question**, and stored-config correctness is not evidence for it.

**To answer it:** re-run the same command **in a real terminal**. It now refuses outright without a
TTY (see below), so the failure cannot repeat. Expect: new ~2-minute spacing → the bracket is
effective, 28-03 can rely on it; unchanged 15-minute spacing for the whole window → the bracket is
insufficient and 28-03 needs a different mechanism, which is the entire reason this probe runs
before an armed window depends on it.

---

## Defect found and fixed by this run

`probe_n8n_semantics.py` would **start a mutation bracket it could not close**. `_prompt_operator`
blocks on `input()`; with stdin not a TTY that raises `EOFError` — and the raise lands *after* the
interval change and *before* the restore, which is exactly the D-05c outcome the probe's own docstring
warns against ("a probe that leaves a schedule changed").

**Fix:** `main()` now refuses `cadence_reload` when `sys.stdin.isatty()` is false, **before the config
load and before any network call**. The wait itself is unchanged and still correct — D-07 forbids a
poll loop, and the operator standing at the checkpoint is the intended clock. What was wrong was
beginning a bracket this process cannot finish.

Two regression tests pin it (`tests/test_control_probe.py`): the refusal path asserts config and
network are never touched behind it, and a TTY-present test proves the guard does not break the real
operator path. Plugin suite 654 → **656**.

---

## Readiness of the plans this gate releases

| Plan | Released? | Basis |
|---|---|---|
| 28-03 | ⚠️ **partially** | Q1 settles the PUT filter it depends on. **A1 (Q3) is still open** — if 28-03 relies on the bracket forcing a reload, that assumption is unverified |
| 28-04 | ✅ | Q2 confirms the amendment it is built on |
| 28-05 | ⛔ | chains behind 28-03/04, and is separately serialized behind the operator committing `test_plugin_manifest.py` |
| 28-06 | ⛔ | armed canary, behind 28-05, needs `ALLOW_N8N_ARM` |
