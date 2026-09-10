# Phase 70 — Deferred human gates

Operator ruling 2026-09-09: "back load human gates to end of phase, run autonomously where
possible." Every `gate="blocking-human"` checkpoint below was NOT waited on mid-flight. Each is
recorded here verbatim from the executor's checkpoint return and must be exercised in the
end-of-phase UAT (`/gsd-verify-work 70`) before the phase can close. Nothing is armed at any
point; every step is disarmed and operator-driven.

## Gate 1 — 70-02 Task 2: disarmed Merge-semantics probe (ingest lane)

**Reached:** 2026-09-09, executor commit `ec247f8` (Task 2 automated verify green: node 974/0,
root pytest 1774 pass, plugin pytest 2850 pass).

**Risk accepted by deferring:** the plan intended this probe to run BEFORE 70-03 rewrites the
123-node enrichment lane, so a Merge that hangs on this n8n Cloud build would be found on the
29-node ingest lane first. Deferred, the first live observation happens after every lane
carries Merges; a hang then is a phase-level finding, not a tracer-level one. Offline guard
until then: the walker's Merge model (`tests/n8n/lib/walkWorkflow.mjs`) and
`tests/n8n/ingestTracerFlow.test.mjs`.

**Steps (operator):**
1. Deploy the ingest workflow disarmed (`scripts/deploy_n8n_workflows.py`, then
   `scripts/bounce_n8n_workflows.py` — a stored update never reloads a running workflow).
2. Send ONE single-lane batch: rows on the association path only, none on the review path, so
   the Merge's second input has nothing to contribute. Zero writes, both write flags false, one
   execution.
3. Report:
   - Did the execution SETTLE, or is it stuck `running`? A stuck execution means the Merge
     design does not hold on this build — a finding, never a workaround.
   - `settings.executionOrder` read from the LIVE workflow body.
   - HubSpot shows no write.
4. Confirm whether `alwaysOutputData` on `Set Review` / `HubSpot Associate Company` mattered
   live, versus the two global sentinel nodes (`Associate Lane Sentinel`,
   `Review Lane Sentinel`, computed once from `Decide Action`'s full row set) which the
   executor's hand-trace found to be the mechanism that actually satisfies both Merge inputs
   (per-routing-IF `alwaysOutputData` was rejected in design as racy against a slower real
   write path).

**Findings to record in `70-02-SUMMARY.md` (Decisions Made / Issues Encountered) when run:**
settled vs stuck; live `executionOrder`; zero writes confirmed; whether the IF-based flags
contributed anything; Merge `typeVersion 3.2` / `mode` / `combineBy` / `numberInputs` /
`options.clashHandling` verified against `merge_node`'s docstring sources.

**Resume signal (original):** "verified" with the four findings, or a description of what the
probe showed.

---

## Gate 70-05-A — the FIRST ARMED batch with a MIXED verdict on one write gate

**Deferred by:** Phase 70 Plan 05 Task 2 (`gate="blocking-human"`, LIVE probe — the operator's
standing ruling defers live probes to end-of-phase UAT). Nothing is armed today.

**Why this gate exists.** Plan 05 gave every gated write an IF-shaped gate whose refusals are
EMITTED rows. The refusal lane's first design shared the write path's own `Build Response
Merge` / `Ingest Merge Response` input; an offline walker run over the committed graph with ONE
row on the allowlist and one not showed the zero-hop refusal beating the permitted row's real
multi-hop delivery to that shared input — the Merge fired and locked, and the permitted row came
back `association: "not_confirmed"` when HubSpot had in fact associated it. Fixed (commit
`3fdf413`): each refusal lane now has its OWN merge input, with sentinels for each way its
producer can be silent, and the mixed case is pinned in
`tests/n8n/writeGateShape.test.mjs`.

**But the proof is the walker, not n8n.** `tests/n8n/lib/walkWorkflow.mjs` models a Merge as
fire-once-when-every-input-has-data; its own comment says that is a spec, "not n8n's real
multi-wave behaviour". This phase's thesis is n8n runtime truth, so the fix must be observed on
the real engine before an unattended armed batch is trusted.

**Steps (operator), at the first supervised armed window:**
1. Deploy + bounce (a stored update never reloads a running workflow).
2. Arm ONE window with `TEST_RECORD_IDS` naming exactly ONE of two contacts, both of which
   resolve the SAME company, and send both in one ingest batch.
3. Record:
   - `Build Ingest Response` row count — must be exactly 2, never 4 (a second Merge run would
     double every reported row).
   - the permitted row: `action: "update"`, `association: "associated"`.
   - the refused row: `action: "write_blocked"` with a reason, `association` NOT `"associated"`.
   - the execution SETTLED (not stuck `running`).
   - HubSpot shows exactly one contact updated and one association created.
4. Confirm `n8n_arming.set_write_safety` rewrote all THREE `ALLOW_HUBSPOT_RECORD_WRITES`
   declaring nodes on the ingest lane — the two gates AND `Associate Lane Sentinel`, which
   duplicates the predicate for Merge plumbing. An arming run that misses the sentinel
   reproduces the dropped-association bug on a real batch.

**Resume signal:** "verified" with the six observations, or a description of what the run showed.

---

## Gate 3 — 70-07 Task 3: D-70-19 disarmed live proof

**Deferred by:** Phase 70 Plan 07 Task 3 (`type="checkpoint:human-verify"`,
`gate="blocking-human"`, LIVE probe — the operator's standing ruling of 2026-09-09 defers live
probes to end-of-phase UAT). Nothing is armed today, and nothing has been deployed.

**Reached:** 2026-09-09. The automatable half is DONE and committed:
`scripts/prove_phase70_runtime.py` (the driver, with its refusal gates, its prediction half and
its comparison), `tests/test_prove_phase70_runtime.py` (17 offline tests, including a refusal on
an armed live body and a comparator proven able to FAIL), and
`70-RUNTIME-VERDICT.json` written in `--predict-only` mode with `shapes_equal: null` and
`status: "predicted_only_awaiting_gate_3"`. **An offline run never writes
`shapes_equal: true`** — that field is the live observation and nothing else.

**Risk accepted by deferring:** the same risk Gate 1 carries, now phase-wide. The whole of
Phase 70's design rests on a native `Merge` node settling when one of its inputs never fires,
and **no committed workflow in this repo has ever contained a native Merge node before this
phase**. Every GREEN produced was produced by `tests/n8n/lib/walkWorkflow.mjs`, whose own header
says its Merge model is a spec, "not n8n's real multi-wave behaviour". Until this gate runs, the
offline harness is an unvalidated model of a mechanism the repo has never run, and CLAUDE.md's
Merge claims stay `[documented]` under §13.0.3's tagging rule.

**Carried caveat to observe FIRST:** `Build Response Merge` on the enrichment lane has **15
inputs**, and n8n's own published documentation describes 2–10 for the Merge node. Flagged in
70-05's Next Phase Readiness, deliberately not resolved offline. If the live engine refuses a
15-input Merge, that is a finding and this gate stops there.

### `<how-to-verify>` — verbatim from the executor's checkpoint return

> 1. **Operator deploys and bounces.** Run `scripts/deploy_n8n_workflows.py`, then
>    `scripts/bounce_n8n_workflows.py`. Both disarmed. Confirm each workflow is active and that its
>    node count matches the committed JSON. Confirm both write flags read false in each live body. A
>    stored update alone never reloads a running workflow, so a deploy without a bounce proves
>    nothing about what ran.
> 2. **Read `settings.executionOrder` from the LIVE workflow body** and record the value. This is
>    the observed-live upgrade for the platform fact this phase has only documented evidence for.
>    Record what it actually is, not what it was expected to be.
> 3. **Send, disarmed:** one 2-identity-lane by 2-action batch on the enrichment lane, one on the
>    ingest lane, and one single-lane-only batch on each. Four sends. Zero writes: the allowlist is
>    empty, so every row is expected to come back blocked, and that is the intended result rather
>    than a failure.
> 4. **Recover** each run's rows from runData by its own run id, through the same client path the
>    plugin uses.
> 5. **Predict** the same rows offline by subprocessing the walker CLI against the same committed
>    JSON with the same input rows.
> 6. **Compare** the recovered rows against the predicted rows and write
>    `70-RUNTIME-VERDICT.json` in the phase directory with, at minimum: `shapes_equal`, the per-send
>    row counts recovered and predicted, the live `settings.executionOrder` value, each execution
>    id, whether any execution failed to settle, and an explicit confirmation that zero writes
>    occurred.
>
> **The pass criteria the operator is judging:**
> - No execution stayed stuck running — no Merge hung on an input that never fired. This is the
>   single most important observation in the run, because the Merge design rests on documented
>   evidence and multiple dated community reports of exactly this failing, and this repo has never
>   run a native Merge node before.
> - The recovered rows are shape-equal to the walker's prediction on all four sends. A mismatch
>   means the offline harness is not a faithful model of the runtime, which would invalidate every
>   offline GREEN this phase produced — report it as a finding, do not adjust the walker to match
>   and call it passed.
> - Every row came back blocked, and HubSpot shows no write.
>
> If the run reveals that the Merge hangs on a single-lane batch on this n8n build, STOP and report.
> That is the one outcome the whole phase's design rests on, and the correct response is a finding,
> not a workaround improvised at the checkpoint.

### The four sends, and the single-lane send in particular

Steps 3–6 above are already implemented by the committed driver. The **single-lane sends are not
optional**: the 2×2 shape exercises every lane by construction and therefore cannot catch a Merge
waiting on an input that never fires — the common real shape, and the exact failure Gate 1 was
meant to find early on the 29-node ingest lane before 70-03 rewrote 123 nodes. Deferred, the first
live observation happens with every lane already carrying Merges. The driver's four sends are, in
order: `enrichment_2x2`, `enrichment_single_lane`, `ingest_2x2`, `ingest_single_lane`.

### The `settings.executionOrder` read (D-70-02)

The driver reads `settings.executionOrder` from **each live workflow body** before it sends
anything, and records the value per workflow in the verdict's
`live_settings_execution_order`. Note that the COMMITTED JSON currently sets no
`settings.executionOrder` at all on any workflow (verified 2026-09-09 by reading all eight
`n8n/wf_*.json`), so the live value is whatever the n8n instance defaults to — **record what it
actually is, never what it was expected to be**. This is the `[observed live]` upgrade for the
platform fact this phase has only documented evidence for.

### Live invocation

```bash
# 1. operator deploys and bounces, DISARMED — the executor never does either
.venv/bin/python scripts/deploy_n8n_workflows.py
.venv/bin/python scripts/bounce_n8n_workflows.py

# 2. the proof, disarmed. It refuses BEFORE constructing any transport if the opt-in is
#    not exactly "true", if the instance guard fails, if there is no executions API key,
#    or if ANY write flag in ANY live body reads anything other than "false".
set -a; source .env; set +a
ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py
```

Exit 0 prints `PROVEN: the live rows match the walker's prediction on every send.` Exit 1 means a
mismatch or an unsettled execution — a FINDING to report, never a prompt to adjust the walker.

### What the verdict must show before this gate is signed off

- `shapes_equal: true`
- four execution ids, each `settled: true`
- `live_settings_execution_order` recording the real value per workflow
- `writes_performed: 0`, and every flag in `write_flags_read_from_live_bodies` reading `"false"`
- HubSpot shows no write

**Resume signal (original):** "approved" once `70-RUNTIME-VERDICT.json` shows `shapes_equal: true`,
all four executions settled, and HubSpot shows zero writes — or a description of what the run
observed instead.

### Follow-on, once this gate passes

Upgrade CLAUDE.md's Merge-behaviour statement from `[documented]` to `[observed live]`, citing
this verdict file and its execution ids, and add the live `settings.executionOrder` value to
§13.0.3's platform-facts table with the same tag. Neither edit may be made before the run.

---

## Gate 4 — pre-Phase-70 live rollback (D-70-21)

**Deferred by:** Phase 70 Plan 08 Task 3 (`type="checkpoint:human-verify"`,
`gate="blocking-human"` — the operator's standing ruling of 2026-09-09 defers live probes and
live-write gates to end-of-phase UAT). Nothing was deployed and nothing was bounced by the
executor.

**Reached:** 2026-09-10. The preparation half is DONE and committed: `70-ROLLBACK-RUNBOOK.md`
(a standalone operator procedure — checkout, dry-run, armed deploy, bounce, read-back, restore),
`70-ROLLBACK-DRYRUN.txt` (a real zero-write dry-run diff captured against the live instance —
credentials resolved, one live GET was made to compute the diff, all five workflows reported
`update`, no write occurred), and `tests/test_phase70_rollback_bundle.py` (15 tests, pinning
commit `59812be` and the five node counts 17/29/123/26/39 against git history, and asserting the
bundle is disarmed at rest — both write flags read `"false"` and the allowlist reads empty
everywhere they are declared).

**Why this gate exists.** The live n8n Cloud instance is currently running the Phase 70 JSON
(node counts 218/50/45/43/30, deployed and bounced disarmed 2026-09-09), and its enrichment
lane's response builder is dead: `Build Response Merge` never fires and `Build Response` never
runs, so an enrichment request finishes `success` with zero rows and nothing alerts on it
(n8n Cloud executions `12204`, `12205`, `12206`, 2026-09-10). The pre-Phase-70 bodies at commit
`59812be` are the last known-working live state. Until the operator runs the rollback (or the
fixed Phase 70 JSON is redeployed at its own later gate), the live enrichment lane returns
empty results for every request.

**Risk accepted by deferring.** The offline gap-closure waves (regenerating the graph, turning
the RED suite green) proceed on the committed JSON regardless of what is live — they do not
need the rollback to make progress. The risk deferred here is operational, not planning: any
live enrichment request sent before the operator runs this gate silently returns zero rows.

**Steps (operator):**
1. Open `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md`
   and follow it top to bottom. It is self-contained — no other plan or gate needs to be read
   first. It refuses immediately if the working tree is not clean.
2. It checks the five pre-Phase-70 bodies out of commit `59812be`, dry-runs the diff, deploys
   them live with both write-gate variables set (`DRY_RUN=false ALLOW_N8N_DEPLOY=true`), bounces
   all five workflows (mandatory — a stored update alone never reloads a running workflow), reads
   back the five live node counts and both write flags, and restores the working tree from
   `HEAD`.
3. Report the four facts back:
   - the five live node counts after the bounce (expected `17, 29, 123, 26, 39`, in the order
     backend_status / contact_ingest / enrichment / review_decision / scheduled_maintenance);
   - both write flags (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`) read from the live
     bodies (expected the disarmed `"false"` literal everywhere either is declared);
   - all five workflows active;
   - one disarmed enrichment (or ingest) request returning a non-empty row set again.
4. Nothing is armed at any point: the allowlist (`TEST_RECORD_IDS`, `TEST_RECORD_DOMAINS`) stays
   empty and no HubSpot record is written by the rollback itself.

**Resume signal:** "rolled back" with the four facts, "deferred" to leave the live instance on
the Phase 70 JSON for now (accepting the zero-row enrichment behaviour until the fix lands and
is redeployed), or a description of what the deploy/bounce read-back showed if it did not match
expectations.

### What this gate does NOT do

It does not fix the Phase 70 graph defect (D-70-20 does that, offline, across the gap-closure
waves) — it reverts the live instance PAST the defect to the last known-working graph. The
fixed Phase 70 JSON is redeployed later, at a separate gate, once the offline suite is green
and this phase's own live-observation gates (1, 70-05-A, 3) are exercised at end-of-phase UAT.
