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

---

## Gate 5 — redeploy the gap-closure JSON and re-run the phase-closing proof (disarmed)

**Deferred by:** Phase 70 Plan 12 Task 3 (`type="checkpoint:human-verify"`,
`gate="blocking-human"` — the operator's standing 2026-09-09 ruling to back-load
`blocking-human` live gates to end-of-phase UAT). Nothing was deployed, bounced or armed by
the executor. Answered per the standing ruling exactly as Gates 1, 70-05-A, 3 and 4 were:
recorded here and the plan continued to completion, not waited on mid-flight.

**Reached:** 2026-09-10, plan 70-12. The offline half is DONE: the walker reproduces
executions 12203 and 12206 (D-70-20/D-70-23, plans 70-09/70-10), the Merge-input contract is
enforced at generation time and empty (plan 70-11), the ingest-lane comparator now compares
like with like (D-70-22, plan 70-12 Task 1), and the whole offline harness is green (node
1064/1064, root Python 4690 passed/154 skipped, plugin Python 2865 passed/5 skipped).

**Why this gate exists.** Gate 3's disarmed run (2026-09-10, executions `12204`–`12208`)
found the graph itself wrong — G-70-2/G-70-3, a live engine rule (a zero-item Code output IS a
Merge-input delivery) the walker did not model, causing `Enrichment Gate Merge` and
`Associate Carry Merge`/`Ingest Merge Response` to fire on a starved-lane sentinel's empty
output before the real row arrived. That defect is fixed in the COMMITTED JSON only — the
LIVE instance still runs the pre-gap-closure Phase 70 bodies (node counts 218/50/45/43/30,
deployed and bounced disarmed on 2026-09-10 for Gates 1 and 3) and still has the defect. Gate
5 is the redeploy that puts the fix live, and the disarmed re-run of exactly the same D-70-19
proof Gate 3 ran, against the fixed graph, so the phase's own closing question — "is the
walker now a faithful model of what the live engine does?" — gets answered a second time,
after the fix, not assumed from the offline suite alone.

**Node counts this gate deploys** (committed now, gap closure): `wf_enrichment_cloud.json`
**291**, `wf_contact_ingest_cloud.json` **69**, `wf_review_decision_cloud.json` **55**,
`wf_scheduled_maintenance_cloud.json` **43** (unchanged), `wf_backend_status_cloud.json`
**30** (unchanged), `wf_enrichment_local_live.json` **82**, `wf_enrichment_local.json` **10**
(unchanged), `wf_contact_ingest_local.json` **13** (unchanged).

**Steps (operator), reusing the SAME deploy/bounce sequence `70-ROLLBACK-RUNBOOK.md` uses,
pointed at the committed HEAD instead of a checked-out historical commit:**
1. Confirm the working tree is on HEAD with the gap-closure JSON (no `git checkout` to a
   historical commit needed here — unlike Gate 4, this gate deploys what is already
   committed).
2. Dry-run first: `.venv/bin/python scripts/deploy_n8n_workflows.py` (no write; sanity-checks
   the diff against what is live).
3. The armed deploy: `DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python
   scripts/deploy_n8n_workflows.py`.
4. Bounce (mandatory — a stored update never reloads a running workflow):
   `.venv/bin/python scripts/bounce_n8n_workflows.py`.
5. Read back all five live node counts (expect 291/69/55/43/30) and both write flags
   (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`) on every node that declares them —
   expect the disarmed `"false"` literal everywhere.
6. Run the proof driver, disarmed, with its permission variable set:
   ```bash
   set -a; source .env; set +a
   ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py
   ```
   Same four sends as Gate 3 (`enrichment_2x2`, `enrichment_single_lane`, `ingest_2x2`,
   `ingest_single_lane`), same refusal gates (T-70-19: refuses before sending if any live
   write flag reads anything but `"false"`), same verdict shape written to
   `70-RUNTIME-VERDICT.json`.

**Pass criteria:**
- `70-RUNTIME-VERDICT.json` records `shapes_equal: true` on all four sends.
- All four executions `settled: true` — no execution stuck `running`, on either lane.
- `writes_performed: 0`, every write flag in `write_flags_read_from_live_bodies` reads
  `"false"`, HubSpot shows no write.
- `live_settings_execution_order` recorded again from the running bodies (expected `null` /
  absent on both workflows, matching the committed JSON and Gate 3's own reading — the
  gap-closure regeneration did not touch `settings`).
- The three stage Merges that replaced the 15-input `Build Response Merge` (plan 70-11) all
  fire and `Build Response` runs — answering the question the 15-input Merge's live behaviour
  was never observed to settle (§13.0.3's CONFOUNDED row): this gate proves the split design,
  not the un-split one.

**If this gate fails** — a shape mismatch, an unsettled execution, or a Merge that hangs on a
single-lane batch — STOP and report it as a finding. Per the standing discipline this whole
phase has followed (Gate 3's own instructions, unchanged here): do not adjust the walker to
match and call it passed; a mismatch here means the offline suite that gap closure turned
green is not yet a faithful model, and the correct response is another debug round, not a
patched assertion.

**Resume signal:** "gate 5 passed" with the verdict's `shapes_equal` result and the four
execution ids, or a description of what the run showed instead.

---

## Gate 6 — the first ARMED mixed-verdict batch against the fixed graph — SUPERSEDED

**SUPERSEDED by Gate 9 (D-70-27, gap closure round 2, 2026-09-10).** Gate 5 never passed on
the enrichment lane (G-70-5 — the 135-child-execution runaway) so this gate was never reached;
the graph it was written against has since changed again (the scale-up fan-out that caused the
runaway is deleted, D-70-24). Gate 9 is the same armed mixed-verdict re-run, re-pointed at the
fixed body, with Gate 8 (not Gate 5) as its precondition. **Do not run the steps below** — they
are kept verbatim for history and for Gate 9 to reference, not as a live procedure. Go to
Gate 9.

**Deferred by:** Phase 70 Plan 12 Task 3 (`type="checkpoint:human-verify"`,
`gate="blocking-human"`). Nothing is armed today. **Runs only after Gate 5 passes** — this
gate is the armed re-run of the exact shape Gate 70-05-A already ran once (2026-09-10,
execution `12203`) and found wrong: the permitted row and the refused row both came back
`action: "update"` / `association: "not_confirmed"` instead of reporting what actually
happened, because the starved-lane sentinel's empty output beat the real row to a shared
Merge input. That defect is what plans 70-09/70-10/70-11 fixed in the graph Gate 5 deploys.
Gate 6 is the proof the fix holds on a REAL armed write, not only offline.

**Why the ordering rule is absolute.** Arming a window and sending a real mixed batch against
a graph that has not itself been proven disarmed first (Gate 5) would repeat exactly the
mistake this phase's own thesis warns against: trusting the offline harness's GREEN over an
observation of the real engine. Gate 5 must read `shapes_equal: true` before Gate 6 is run.

**Steps (operator), reusing the SAME arming and send shape Gate 70-05-A used:**
1. Confirm Gate 5 passed (`shapes_equal: true`, all four executions settled, live instance
   running the 291/69/55/43/30 JSON) before touching anything below.
2. Pick a pair of contacts that resolve the SAME company, exactly as Gate 70-05-A did
   (Darwin Turf Club `9605267534`, contacts `7101` Grant Dewsbury and `2751` Steve Taylor, is
   the precedent pair and may be reused if still in that state, or any equivalent pair).
3. Arm ONE window with `TEST_RECORD_IDS` naming exactly ONE of the two contacts
   (`june_run_arm.py --ids <one-id>` is the precedent tool). Read back: all THREE declaring
   nodes on the ingest lane (`HubSpot Update Write Gate`, `HubSpot Create Write Gate`,
   `Associate Lane Sentinel`) show `ALLOW_HUBSPOT_RECORD_WRITES="true"`, `TEST_RECORD_IDS`
   naming only that one contact.
4. Send both contacts in ONE ingest batch.
5. Record:
   - `Build Ingest Response` row count — must be exactly **2**, never 4 (a second Merge run
     would double every reported row).
   - the permitted row: `action: "update"`, `association: "associated"` (NOT
     `"not_confirmed"` — this is the exact field Gate 70-05-A found wrong).
   - the refused row: `action: "write_blocked"` with a reason, `association` NOT
     `"associated"`.
   - the execution `settled: true` (not stuck `running`).
   - HubSpot itself shows exactly one contact updated and one association created; the other
     contact untouched.
6. Disarm afterward and read every flag back at its disarmed literal: `ALLOW_HUBSPOT_RECORD_
   WRITES="false"` and `TEST_RECORD_IDS=""` on all three declaring nodes.

**Pass criteria:** every point in step 5 holds as stated, and step 6's disarm-and-read-back
confirms the window is closed. Any row still reporting `"not_confirmed"` where the fix
predicts `"associated"`/`"write_blocked"` is the SAME finding Gate 70-05-A raised, now against
the graph that was supposed to fix it — report it, do not re-interpret the result to fit.

**Resume signal:** "gate 6 passed" with the two row outcomes and the HubSpot read-back, or a
description of what the run showed instead.

---

### Ordering rule, stated once for both (historical — see Gates 7/8/9 below for the current rule)

**Gate 5 before Gate 6, always.** Gate 5 is the disarmed proof that the fixed graph behaves
the way the offline suite now predicts; Gate 6 is the one armed write this phase's close makes,
and it is never run against a graph that has not itself been proven disarmed first. If Gate 4
was already run (the pre-Phase-70 rollback to commit `59812be`), Gate 5 supersedes it: Gate 5
deploys the gap-closure JSON — forward of both the pre-Phase-70 bodies Gate 4 rolled back to
and the pre-gap-closure Phase 70 JSON currently live — over whatever Gate 4 left running.

**Superseded 2026-09-10 (D-70-27, gap closure round 2).** Gate 5 did not pass on the
enrichment lane (G-70-5, the 135-child-execution runaway) so Gate 6 was never reached. The
graph has changed again since (the scale-up fan-out that caused the runaway is deleted,
D-70-24). Gates 7, 8 and 9 below are the current gates; Gate 6 is kept above verbatim for
history and for Gate 9 to reference, not as a live procedure.

---

## Gate 7 — disarmed deploy + bounce of the loop-free body, then the two-minute burst watch, nothing sent

**Deferred by:** Phase 70 Plan 15 (D-70-27, the operator's standing 2026-09-09 ruling to
back-load `blocking-human` live gates to end-of-phase UAT). Nothing is deployed, bounced,
armed or sent by any executor.

**Reached:** 2026-09-10, plan 70-15. The offline half is DONE: the fan-out lane that caused
the 2026-09-10 runaway is deleted from the enrichment graph (D-70-24, plan 70-13; zero
`executeWorkflow` nodes remain, enforced at generation time by `assert_no_self_dispatch`), a
positive row-identity filter drops any marker item before either response builder projects a
row (D-70-25, plan 70-14), and the two-minute burst watch this incident made a standing rule is
written into `70-ROLLBACK-RUNBOOK.md` Step 6.

**Why this gate exists.** Gate 4/5's deploy attempt (2026-09-10T07:03Z–07:10Z) put a graph with
a self-referencing `Execute Workflow` node live and it began self-dispatching within a minute
of the first disarmed proof send — 135 child executions in six minutes, none of them requested.
That graph no longer exists (it is deleted, not patched), but this gate is the first time the
**loop-free** body is deployed live, and the whole reason the phase's own thesis exists — trust
the live engine's observation over the offline model — means the redeploy itself needs to be
watched, not assumed safe because the offline suite is green.

**Nothing is sent in this gate. No proof driver, no client request.** Gate 7 is deploy, bounce,
watch, read-back — nothing else.

**Steps (operator):**
1. Confirm the working tree is on HEAD with the current committed JSON (no `git checkout` to a
   historical commit — this deploys what is already committed, the same pattern Gate 5 used
   against Gate 4's checked-out-commit pattern). Expected node counts: `wf_enrichment_cloud.json`
   **287** (zero `executeWorkflow`), `wf_contact_ingest_cloud.json` **69**,
   `wf_review_decision_cloud.json` **55**, `wf_scheduled_maintenance_cloud.json` **43**
   (unchanged), `wf_backend_status_cloud.json` **30** (unchanged).
2. Dry-run first: `.venv/bin/python scripts/deploy_n8n_workflows.py` (no write; sanity-checks
   the diff against what is live — the enrichment lane's diff will be large, since live is
   still the pre-Phase-70 123-node body).
3. The armed deploy: `DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python
   scripts/deploy_n8n_workflows.py`.
4. Bounce (mandatory — a stored update never reloads a running workflow):
   `.venv/bin/python scripts/bounce_n8n_workflows.py`.
5. Read back all five live node counts (expect 287/69/55/43/30, matching the printed
   "committed nodes" column) and both write flags (`ALLOW_HUBSPOT_RECORD_WRITES`,
   `ALLOW_HUBSPOT_CREATE`) on every node that declares them — expect the disarmed `"false"`
   literal everywhere. The bounce script's own `OK — all active, node counts match, write flags
   false.` line and exit 0 is the read-back passing.
6. **Immediately after the bounce, run the two-minute burst watch** — `70-ROLLBACK-RUNBOOK.md`
   Step 6, verbatim: list the enrichment workflow's executions, note the ids, wait two minutes
   with **nothing sent**, list again. Zero new execution ids is the pass condition, with
   particular attention to `mode: integrated` (the field that marks an `Execute Workflow`
   child — the exact signature the 2026-09-10 runaway carried).

**Pass criteria:**
- All five workflows read `active = True`.
- Live node counts read exactly `287 / 69 / 55 / 43 / 30` and match the committed JSON.
- Both write flags read `"false"` everywhere either is declared.
- The two-minute watch shows **zero** new execution ids appearing — no execution the operator
  did not request, and in particular none with `mode: integrated`.

**If the watch shows a new execution appearing on its own:** STOP. Do not proceed to Gate 8.
Run the stop procedure in `70-ROLLBACK-RUNBOOK.md` Step 6 (deactivate first, then PUT the
previous known-good body, then confirm no further executions), and report it as a finding —
the loop-free graph produced a loop that was supposed to be impossible by the node's absence,
which would mean the mechanism behind G-70-5 is not what the removal assumed it was.

**Resume signal:** "gate 7 passed" with the five node counts, the two write-flag reads, and the
two-minute watch's before/after execution id lists, or a description of what the read-back or
the watch showed instead.

---

## Gate 8 — disarmed live re-proof on the loop-free graph (D-70-19 proof re-run)

**Deferred by:** Phase 70 Plan 15 (D-70-27, standing ruling). **Runs only after Gate 7
passes** — sending the proof driver's four batches before the burst watch has confirmed the
freshly deployed graph is not self-dispatching would repeat the exact sequence that produced
the 2026-09-10 runaway (deploy, bounce, then send).

**Why this gate exists.** Gate 5 (the previous attempt at this exact proof, against the
pre-deletion gap-closure graph) never passed on the enrichment lane: `enrichment_2x2` recovered
8 rows against 4 predicted, `enrichment_single_lane` recovered 4 against 2 predicted, and —
this is the fact this gate exists to re-check, not assume fixed — **every recovered row on the
enrichment lane had `row_id: null`.** None of the rows Gate 5 got back could be matched to a
specific input row at all; the 8-vs-4 and 4-vs-2 overcounts came from runaway children whose
executions were swept in by matching the same client-minted `run_id` (`70-RUNTIME-VERDICT.json`
`sends[].execution_ids` for `enrichment_2x2` lists FOUR execution ids — `12209`, `12210`, and
the first two runaway children, `12211`/`12212` — behind what the driver reports as ONE
`settled: true` send). The driver's `settled` flag is read from the send's primary execution
only; the additional matched executions swept in by the run_id echo were never individually
checked for their own run status, and the runaway's own tail (`12346`–`12348`) is independently
known to have errored rather than executed. **Removing the phantom rows (the scale-up deletion)
does not by itself prove the four real rows will now come back with real row ids — it only
removes the mechanism that was polluting the count.** A marker-free but EMPTY result on this
lane is still a FAILURE of this gate, not progress toward passing it — do not read "no more
phantom rows" as "the real rows are now present" without checking.

**Steps (operator), reusing the SAME driver Gate 3 and Gate 5 used, against the graph Gate 7
just deployed:**
1. Confirm Gate 7 passed (all five workflows active, node counts 287/69/55/43/30, both write
   flags `"false"` everywhere, the two-minute watch clean) before sending anything.
2. Read `settings.executionOrder` from each live workflow body again and record it (expected
   `null`/absent on both lanes, matching every prior reading — this gap-closure round did not
   touch `settings`).
3. Run the proof driver, disarmed, with its permission variable set:
   ```bash
   set -a; source .env; set +a
   ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py
   ```
   Same four sends as Gates 3 and 5: `enrichment_2x2`, `enrichment_single_lane`, `ingest_2x2`,
   `ingest_single_lane`. Same refusal gates (refuses before sending if any live write flag
   reads anything but `"false"`). `70-RUNTIME-VERDICT.json` is overwritten with this run's
   result.
4. **New step, added by this round — for each of the four executions the driver used (its
   primary execution id, not only the send-level result), fetch the execution's full runData
   via `executions_client.get_execution(config, execution_id)` (`includeData=true`) and
   compare every node's runData `source` field against that workflow's own declared
   `connections` map.** Reuse the exact producer-computation pattern
   `tests/n8n/walkerEngineFidelity.test.mjs`'s `declaredProducersOf(wf, targetName)` already
   implements (walk `wf.connections`, collect every `srcName` whose `main` branch edges name
   `targetName`) — write a short one-off script following that pattern rather than reinventing
   the walk, and read `wf` from the SAME committed JSON Gate 7 just deployed. Report any node
   whose runData `source` names a node not in its own declared-producers set. This is the exact
   detector for the mechanism execution `12316` exhibited (a node ran with an item no declared
   connection delivered) — the mechanism was never isolated, only the node that could act on it
   was removed, so this check must be run and reported, not assumed clean because the fan-out
   node no longer exists.

**Pass criteria — ALL of the following, not a subset:**
- `70-RUNTIME-VERDICT.json` records `shapes_equal: true` on **all four** sends, including both
  enrichment sends this time (Gate 5 passed only the two ingest sends).
- Every recovered row on the enrichment lane carries a non-null `row_id` matching its input row
  — an empty or marker-shaped recovery is a failure of this gate even if the row COUNT happens
  to look right.
- All four (primary) executions `settled: true` — no execution stuck `running`, on either lane.
- The runData-source-vs-declared-connections check (step 4) finds nothing — no node ran with a
  source its own workflow's `connections` map does not declare.
- `writes_performed: 0`, every write flag in `write_flags_read_from_live_bodies` reads
  `"false"`, HubSpot shows no write.
- `live_settings_execution_order` recorded again (expected `null`/absent on both workflows).

**If this gate fails** — any of the above, including a clean row count with a null row_id, or
the connections check finding an unexplained node run — STOP and report it as a finding, exactly
as Gates 3 and 5 required. Do not adjust the walker or the driver to match and call it passed.

**Resume signal:** "gate 8 passed" with the verdict's `shapes_equal` result, the four execution
ids, and the connections-check result, or a description of what the run showed instead.

### Follow-on, once this gate passes

Upgrade CLAUDE.md's Merge-behaviour statements and §13.0.3's platform-facts table for whatever
this run newly observes, citing this verdict file and its execution ids — the same follow-on
Gate 3 already names, now actually exercised on the loop-free graph. This is the first Merge
observation since 2026-09-10's Gate 1/Gate 3 UAT session; nothing about Merge was touched by
plan 70-15's CLAUDE.md edits (see CLAUDE.md §13.0.3's note next to the Merge rows).

---

## Gate 9 — the armed mixed-verdict re-run, against the fixed graph (formerly Gate 6) — SUPERSEDED

**SUPERSEDED by Gate 12 (D-70-31, gap closure round 3, 2026-09-10).** Gate 8 failed on the
enrichment lane (G-70-6 — the legacy `addEmptyItem` symptoms) so this gate was never reached;
the graph it was written against predates the v1 flip (D-70-28). Gate 12 is the same armed
mixed-verdict re-run, re-pointed at the v1 body, with Gate 11 (not Gate 8) as its precondition.
**Do not run the steps below** — they are kept verbatim for history and for Gate 12 to
reference, not as a live procedure. Go to Gate 12.

**Deferred by:** Phase 70 Plan 15 (D-70-27, standing ruling). **Runs only after Gate 8
passes.** This is Gate 6 above, re-pointed at the graph Gate 7 deployed and Gate 8 proved,
with two things changed from Gate 6's text and nothing else: the body it runs against (the
current committed JSON, not the pre-runaway gap-closure JSON Gate 6 was written for), and its
precondition (Gate 8, not Gate 5).

**Do not restate Gate 6's procedure here.** Follow Gate 6's steps 1–6 verbatim, above, with
these two substitutions:
- Wherever Gate 6's text says "Gate 5 passed" or "the 291/69/55/43/30 JSON", read "Gate 8
  passed" and "the current committed JSON (the loop-free 287/69/55/43/30 body)".
- Wherever Gate 6's text says "Confirm Gate 5 passed... before touching anything below", the
  precondition is Gate 8, not Gate 5.

Everything else — the pair (Darwin Turf Club `9605267534`, contacts `7101`/`2751`, or an
equivalent pair), the arming tool (`june_run_arm.py --ids <one-id>`), the three declaring nodes
to read back (`HubSpot Update Write Gate`, `HubSpot Create Write Gate`, `Associate Lane
Sentinel`), the exact row count (2, never 4), the exact field values (`action: "update"` /
`association: "associated"` for the permitted row, `action: "write_blocked"` for the refused
row), and the disarm-and-read-back at the end — is Gate 6's text, unchanged.

**Resume signal:** "gate 9 passed" with the two row outcomes and the HubSpot read-back, or a
description of what the run showed instead.

---

### Ordering rule for Gates 7, 8 and 9, stated once for all three

**7 before 8, 8 before 9 — no exceptions, and nothing is armed until 8 has passed.**

- Gate 7 proves the redeploy itself is safe — that a freshly deployed, loop-free graph does not
  start running on its own. It sends nothing.
- Gate 8 proves the graph behaves the way the offline suite predicts, on a real disarmed
  batch, including the specific check (runData source vs. declared connections) for the
  mechanism the 2026-09-10 runaway exhibited. It writes nothing to HubSpot.
- Gate 9 is the one armed write this phase's close makes. It is never run against a graph that
  has not itself been proven both non-self-dispatching (Gate 7) and disarmed-correct (Gate 8).

**The operator alone opens the armed window.** No step in Gates 7 or 8 arms anything; arming
happens only inside Gate 9, only after Gate 8's pass criteria are all met, and is closed again
(disarmed, read back) before the gate is signed off.

---

## Gate 10 — disarmed deploy + bounce of the v1 bodies, then the two-minute burst watch, nothing sent

**Deferred by:** Phase 70 Plan 18 (D-70-31, the operator's standing 2026-09-09 ruling to
back-load `blocking-human` live gates to end-of-phase UAT). Nothing is deployed, bounced,
armed or sent by any executor.

**Precondition:** the committed JSON is the v1 generation — `scripts/build_cloud_workflows.py`
emits `"settings": {"executionOrder": "v1"}` on all eight `n8n/wf_*.json` bodies (D-70-28,
plan 70-16), and both live-write paths that could revert it are pinned value-level to preserve
it (D-70-29, plan 70-17). No `git checkout` to a historical commit is needed — this deploys
what is already committed, the same pattern Gate 7 used.

**Why this gate exists.** Gate 8 (executions `12349`-`12353`) reproduced n8n's legacy
`addEmptyItem` push end to end on a live body whose `settings.executionOrder` was absent
throughout, and the live instance was rolled back past that body to the pre-Phase-70
`59812be` bundle (see CLAUDE.md §13.0.2). This gate is the first time the v1 bodies are
deployed live — nothing about the v1 flip has been observed yet; it is `[documented]` only
(CLAUDE.md §13.0.3). Per this whole phase's own thesis, the redeploy needs to be watched, not
assumed safe because the offline suite (D-70-28/D-70-29/D-70-30) is green.

**Nothing is sent in this gate. No proof driver, no client request.** Gate 10 is deploy,
bounce, watch, read-back — nothing else, exactly as Gate 7 was.

**Steps (operator):**
1. Confirm the working tree is on HEAD with the v1-generation committed JSON. Expected node
   counts (unchanged by the flip — settings only): `wf_enrichment_cloud.json` **287**,
   `wf_contact_ingest_cloud.json` **69**, `wf_review_decision_cloud.json` **55**,
   `wf_scheduled_maintenance_cloud.json` **43**, `wf_backend_status_cloud.json` **30**. An
   unchanged count here is the EXPECTED reading, not a sign the deploy did nothing — the
   settings differ, the nodes do not.
2. Dry-run first: `.venv/bin/python scripts/deploy_n8n_workflows.py` (no write; sanity-checks
   the diff against what is live — the live instance is currently the pre-Phase-70 `59812be`
   bundle on all five workflows, so every diff will be large).
3. The armed deploy: `DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python
   scripts/deploy_n8n_workflows.py`.
4. Bounce (mandatory — a stored update never reloads a running workflow):
   `.venv/bin/python scripts/bounce_n8n_workflows.py`. The bounce script now reads back and
   exits non-zero BY ITSELF on a non-v1 `settings.executionOrder` reading (D-70-29) — a zero
   exit code is therefore part of the evidence, not merely a courtesy.
5. Read back all five live node counts (expect 287/69/55/43/30, matching the committed JSON),
   both write flags (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`) on every node that
   declares them (expect the disarmed `"false"` literal everywhere), and the bounce table's
   execution-order column (expect `v1` on all five).
6. **Immediately after the bounce, run the two-minute burst watch** —
   `70-ROLLBACK-RUNBOOK.md` Step 6, verbatim: list the enrichment workflow's executions, note
   the ids, wait two minutes with **nothing sent**, list again. Zero new execution ids is the
   pass condition, with particular attention to `mode: integrated` — the enrichment lane is
   going from the pre-Phase-70 123-node body (no Merge nodes, no v1 setting) to the 287-node
   v1 body in one deploy, the same magnitude of jump Gate 7 watched for.

**Pass criteria:**
- All five workflows read `active = True`.
- Live node counts read exactly `287 / 69 / 55 / 43 / 30` and match the committed JSON —
  UNCHANGED by the flip, as expected.
- Both write flags read `"false"` everywhere either is declared.
- The bounce script's read-back table (and its own non-zero-on-non-v1 exit check) reads
  `settings.executionOrder == "v1"` on all five workflows.
- The two-minute watch shows **zero** new execution ids appearing — no execution the operator
  did not request, and in particular none with `mode: integrated`.

**If the watch shows a new execution appearing on its own:** STOP. Do not proceed to Gate 11.
Run the stop procedure in `70-ROLLBACK-RUNBOOK.md` Step 6 (deactivate first, then PUT the
previous known-good body, then confirm no further executions), and report it as a finding —
the v1 flip was not expected to change self-dispatch behaviour at all, so a burst here would
mean the mechanism behind G-70-5 is not what the fan-out deletion assumed it was.

**Resume signal:** "gate 10 passed" with the five node counts, the two write-flag reads, the
execution-order read-back, and the two-minute watch's before/after execution id lists, or a
description of what the read-back or the watch showed instead.

---

## Gate 11 — the D-70-19 proof re-run under v1

**Deferred by:** Phase 70 Plan 18 (D-70-31, standing ruling). **Runs only after Gate 10
passes** — sending the proof driver's four batches before the burst watch has confirmed the
freshly deployed v1 graph is not self-dispatching would repeat the exact sequence that
produced the 2026-09-10 runaway (deploy, bounce, then send).

**Why this gate exists.** Gate 8 found that with `settings.executionOrder` ABSENT (legacy
order), a node executes once its predecessor has run even when it received zero items — the
`addNodeToBeExecuted`/`addEmptyItem` mechanism now on record in CLAUDE.md §13.0.3. D-70-28
flips every generated body to `"v1"` on the strength of that source citation alone; **nothing
about v1 has been observed on this instance.** This gate is the observation — the same D-70-19
proof Gates 3, 5 and 8 ran, against the v1 bodies Gate 10 just deployed, with one expectation
inverted from Gate 8's.

**Steps (operator), reusing the SAME driver Gates 3, 5 and 8 used, against the graph Gate 10
just deployed, with two changes from Gate 8's steps and nothing else:**
1. Confirm Gate 10 passed (all five workflows active, node counts 287/69/55/43/30, both write
   flags `"false"` everywhere, `settings.executionOrder == "v1"` on all five, the two-minute
   watch clean) before sending anything.
2. **INVERTED from Gate 8.** Read `settings.executionOrder` from each live workflow body again
   and record it — expect `"v1"` on every one this time. **A `null` or absent reading is a
   FAILURE of this gate** — the exact opposite of Gate 8, where `null` was the expected
   observation. This inversion is the whole point of the round: if the flip did not take, or
   did not survive the deploy, nothing else this gate checks can be trusted as a v1
   observation.
3. Run the proof driver, disarmed, with its permission variable set:
   ```bash
   set -a; source .env; set +a
   ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py
   ```
   Same four sends as Gates 3, 5 and 8: `enrichment_2x2`, `enrichment_single_lane`,
   `ingest_2x2`, `ingest_single_lane`. Same refusal gates (refuses before sending if any live
   write flag reads anything but `"false"`). `70-RUNTIME-VERDICT.json` is overwritten with this
   run's result, now carrying the `execution_order_all_v1` field plan 70-17 added.
4. **RETAINED unchanged from Gate 8 — for each of the four executions the driver used (its
   primary execution id, not only the send-level result), fetch the execution's full runData
   via `executions_client.get_execution(config, execution_id)` (`includeData=true`) and compare
   every node's runData `source` field against that workflow's own declared `connections`
   map.** Reuse the exact producer-computation pattern
   `tests/n8n/walkerEngineFidelity.test.mjs`'s `declaredProducersOf(wf, targetName)` already
   implements (walk `wf.connections`, collect every `srcName` whose `main` branch edges name
   `targetName`) — write a short one-off script following that pattern rather than reinventing
   the walk, and read `wf` from the SAME committed JSON Gate 10 just deployed. Report any node
   whose runData `source` names a node not in its own declared-producers set. The mechanism
   execution `12316` exhibited (a node ran with an item no declared connection delivered) was
   never isolated, and the v1 flip does not explain it and does not excuse skipping this check
   — run it and report it, exactly as Gate 8 did, whether or not it finds anything.

**Pass criteria — ALL of the following, not a subset:**
- `70-RUNTIME-VERDICT.json` records `shapes_equal: true` on **all four** sends, including both
  enrichment sends.
- Every recovered row on the enrichment lane carries a non-null `row_id` matching its input row
  — an empty or marker-shaped recovery is a failure of this gate even if the row COUNT happens
  to look right (carried verbatim from Gate 8: a marker-free but EMPTY result is a FAILURE, not
  progress toward passing it).
- All four (primary) executions `settled: true` — no execution stuck `running`, on either lane.
- The runData-source-vs-declared-connections check (step 4) finds nothing — no node ran with a
  source its own workflow's `connections` map does not declare.
- `writes_performed: 0`, every write flag in `write_flags_read_from_live_bodies` reads
  `"false"`, HubSpot shows no write.
- The verdict's **`execution_order_all_v1` field reads `true`**, and
  `live_settings_execution_order` records `"v1"` per workflow — a `null` or non-`"v1"` reading
  here is a FAILURE of this gate.

**If the legacy symptoms persist under v1** — `HubSpot Update` firing on an empty lane, a
refusal stamped on a starved input, a Merge firing on an empty delivery, or any other Gate 8
symptom, even with `execution_order_all_v1: true` — **STOP and report. Do not adjust the
walker or the driver to match.** This is D-70-31's explicit instruction, stated once here in
full: a pass that required bending the model to fit the observation would not be a pass.

**If this gate fails for any other reason** — a shape mismatch, an unsettled execution, or a
`null`/non-`"v1"` order reading — STOP and report it as a finding, exactly as Gates 3, 5 and 8
required.

**Resume signal:** "gate 11 passed" with the verdict's `shapes_equal` and
`execution_order_all_v1` results, the four execution ids, and the connections-check result, or
a description of what the run showed instead.

### Follow-on, once this gate passes

A pass upgrades this round's `[documented]`-only v1 rows in CLAUDE.md §13.0.3 (the
`addNodeToBeExecuted`/`addEmptyItem` row and the `requiredInputs` row) to `[observed live]`,
citing this gate's verdict file and its execution ids — the tagging discipline this whole
phase exists to enforce. A pass also makes it safe to CONSIDER modelling the walker's rule (b)
— the v1 end-of-run Merge drain, deliberately left unmodelled by plan 70-16 (D-70-30) —
because only after this gate is there a live observation to model against, rather than a
second unobserved guess replacing the first.

---

## Gate 12 — the armed mixed-verdict re-run, against the v1 graph (formerly Gate 9, formerly Gate 6)

**Deferred by:** Phase 70 Plan 18 (D-70-31, standing ruling). **Runs only after Gate 11
passes.** Follow Gate 9's own pattern of pointing at an earlier gate's steps with named
substitutions rather than restating them.

**Do not restate Gate 6's procedure here.** Follow Gate 6's steps 1–6 verbatim, above (the
text Gate 9 already pointed at unchanged), with these substitutions:
- Wherever Gate 6's text says "Gate 5 passed" or "the 291/69/55/43/30 JSON", read "Gate 11
  passed" and "the current committed JSON (the v1 generation, 287/69/55/43/30, with
  `settings.executionOrder: "v1"` on all five)".
- Wherever Gate 6's text says "Confirm Gate 5 passed... before touching anything below", the
  precondition is Gate 11, not Gate 5, not Gate 8.

Everything else — the pair (Darwin Turf Club `9605267534`, contacts `7101`/`2751`, or an
equivalent pair), the arming tool (`june_run_arm.py --ids <one-id>`), the three declaring nodes
to read back (`HubSpot Update Write Gate`, `HubSpot Create Write Gate`, `Associate Lane
Sentinel`), the exact row count (2, never 4), the exact field values (`action: "update"` /
`association: "associated"` for the permitted row, `action: "write_blocked"` for the refused
row), and the disarm-and-read-back at the end — is Gate 6's text, unchanged.

**Resume signal:** "gate 12 passed" with the two row outcomes and the HubSpot read-back, or a
description of what the run showed instead.

---

### Ordering rule for Gates 10, 11 and 12, stated once for all three

**10 before 11, 11 before 12 — no exceptions, and nothing is armed until 11 has passed.**

- Gate 10 proves the v1 redeploy itself is safe — that a freshly deployed, v1-flipped graph
  does not start running on its own. It sends nothing.
- Gate 11 proves the graph behaves the way the offline suite predicts UNDER v1, on a real
  disarmed batch, inverting Gate 8's one expectation (a `null` order reading is now a failure)
  while keeping every other check, including the runData-source-vs-declared-connections check.
  It writes nothing to HubSpot.
- Gate 12 is the one armed write this round's close makes. It is never run against a graph that
  has not itself been proven both non-self-dispatching (Gate 10) and v1-observed-correct
  (Gate 11).

**The operator alone opens the armed window.** No step in Gates 10 or 11 arms anything; arming
happens only inside Gate 12, only after Gate 11's pass criteria are all met, and is closed
again (disarmed, read back) before the gate is signed off.

**Gates 7 and 8 stay in the record as run and failed, respectively — they are evidence, not
history to erase.** Gate 9 stays in the record as superseded, the same way Gate 6 does.
