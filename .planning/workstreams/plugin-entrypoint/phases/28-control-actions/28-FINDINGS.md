# 28-FINDINGS — n8n semantics live gate (plan 28-02, RB-5)

**Run:** 2026-07-31 · **Operator:** Robert · **Tenant:** `alexherman.app.n8n.cloud`
**Target:** `LV Scheduled Maintenance (Cloud)`, workflow id `1fXPuIabz3RsAHgn`, `active: true`
**Probe:** `operator-claude-plugin/scripts/probe_n8n_semantics.py`

**All three questions are answered.** Q3 took two runs — the first exposed a real defect in the
probe, now fixed. Read Q3's caveat before building on it: the *load* question is answered YES, the
*cadence precision* question is not.

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

**Status: ANSWERED YES on the load question — with one bounded caveat on cadence precision.**
Answered on the second attempt, in a real terminal, 2026-07-31. The first attempt is kept below
because the defect it exposed is the reason the probe is now safe to run.

### The answer

**Run:** `cadence_reload 1fXPuIabz3RsAHgn "Review Trigger (15 min)"`, TTY, ~10 minute wait.
`change_verdict: verified`, `restore_verdict: verified`, `prior_interval` restored to 15.

**Observed execution starts** (20 returned against a page limit of 20 — the page is **saturated**,
so truncation drops the OLDEST; everything after the change is present):

Steady state is *pairs* on the quarter hour — `02:45:11.062/.098`, `03:00:11.062/.111`,
`03:15:11.061/.099` — because **two** Schedule Triggers run at 15 minutes (`Review Trigger (15 min)`
and `SJ-3 Trigger (15 min)`), firing ~40 ms apart. Those are the `0.0` entries in
`spacing_minutes`. The hourly `SJ-1 Trigger` adds the `:00:01` fires, the `0.17` gaps.

After the change, two **single** fires appear:

| Start | Gap from previous |
|---|---|
| `2026-07-31T03:22:11.043Z` | **7.0 min** |
| `2026-07-31T03:26:11.040Z` | **4.0 min** |

**Both are off the 15-minute grid, and both are single rather than paired** — precisely the
signature of one retimed trigger while its 15-minute sibling stayed put. `SJ-3`'s next grid fire
(`03:30:11`) falls after the read, so its absence is consistent too.

**Conclusion: the deactivate → PUT → activate bracket DOES make a Schedule Trigger change effective
on a running instance.** D-18 / A1 answered. Confidence **HIGH** — a 15-minute schedule cannot
produce a fire at `03:22` or `03:26`.

### The caveat — do not overstate this into cadence precision

The commanded interval was **2 minutes**; observed gaps were **7 and 4**, and a fire expected around
`03:24` is absent. Page saturation does not explain it (truncation removes the oldest, and these are
the newest). Whatever the cause — scheduler re-basing after reactivation, a skipped tick, Cloud-side
queueing — **the exact post-change cadence is not established.**

- ✅ **Safe to rely on (28-03):** a re-timed trigger takes effect without a redeploy.
- ⚠️ **Not established (28-04):** that the new cadence matches the requested interval exactly. If
  28-04 shows the operator a "next run" time or promises a precise new spacing, that claim is
  **unverified** and should be worded as requested-not-guaranteed, or evidenced separately.

### First attempt (2026-07-31, non-TTY) — kept for the defect it found

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

**Resolved by the second run above.** The probe now refuses without a TTY, so this failure cannot
repeat.

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
| 28-03 | ✅ | Q1 settles the PUT filter; Q3 confirms the bracket forces a reload on a running instance |
| 28-04 | ✅ **with one wording constraint** | Q2 confirms the amendment it is built on. Per Q3's caveat, it must not promise an exact post-change cadence or a precise "next run" time — requested ≠ guaranteed |
| 28-05 | ⛔ | chains behind 28-03/04, and is separately serialized behind the operator committing `test_plugin_manifest.py` |
| 28-06 | ⛔ | armed canary, behind 28-05, needs `ALLOW_N8N_ARM` |
