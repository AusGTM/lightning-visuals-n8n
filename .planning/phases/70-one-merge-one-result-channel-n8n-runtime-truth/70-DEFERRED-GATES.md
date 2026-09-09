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
