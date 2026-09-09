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
