# Quick Task 260730-din: Split RESEARCH/JUDGE model switches + arm judge — Context

**Gathered:** 2026-07-30 (decisions locked in operator conversation; discussion phase satisfied — do not re-ask)
**Status:** Ready for planning

<domain>
## Task Boundary

Execute the pre-written spec at `.planning/quick/20260730-judge-research-model-switches/PLAN.md`:
split `ANTHROPIC_SONNET_MODEL` into `ANTHROPIC_RESEARCH_MODEL` + `ANTHROPIC_JUDGE_MODEL`,
rename `ALLOW_SONNET_ESCALATION` → `ALLOW_JUDGE_ESCALATION` (default flips to `true`),
rename `MAX_SONNET_VALIDATIONS_PER_RUN` → `MAX_JUDGE_VALIDATIONS_PER_RUN` (default raises to `50`).
That PLAN.md is the canonical task list (Tasks 1–8) and touchpoint survey — treat it as LOCKED input.

</domain>

<decisions>
## Implementation Decisions (all operator-locked 2026-07-30)

### Model switch defaults
- BOTH new model switches default `claude-sonnet-5`. Behavior-preserving split; flipping
  research to Haiku is a LATER separate change. Do not default anything to Haiku.

### Judge arming
- `ALLOW_JUDGE_ESCALATION` default `true` (was false). `MAX_JUDGE_VALIDATIONS_PER_RUN`
  default `50` (was 10).

### Deploy overlay
- DELETE `ALLOW_SONNET_ESCALATION` from `_OVERLAY_FLAG_SPEC` in scripts/deploy_n8n_workflows.py —
  overlay only widens disabled→enabled; a default-true flag has no entry. Emergency off =
  edit builder default + rebuild + disarmed redeploy.

### Explicitly OUT of scope (operator said do not add)
- NO org_type evidence-gate in computeEscalation (YAGNI — plausible, not observed).
- NO n8n/code/judge.js logic changes (comment renames only, optional).
- NO model default change to claude-haiku-4-5.

### Env files
- `.env.example` updated in-repo (3 lines → 4).
- Live `.env` is permission-blocked to agents: emit the operator `!` sed command from
  PLAN.md Task 4 in the final summary; do NOT attempt to read or write `.env`.

### Safety
- Write-safety flags stay disarmed ("false"). Deploy step is DISARMED redeploy + read-back
  only (proven Phase-19 dotenv-wrapper path). No HubSpot writes anywhere.

### Claude's Discretion
- Exact test-fixture mechanics (frozen-bytes regen per that test's documented procedure —
  never hand-patch bytes), comment wording, doc phrasing.

</decisions>

<specifics>
## Specific Ideas

- Follow PLAN.md Tasks 1–8 ordering and success criteria verbatim.
- Suite commands (memory-verified): `.venv/bin/python -m pytest` and
  `node --test tests/n8n/*.test.mjs` (glob form — dir form broken on node 24).
- Deploy via `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"`.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/quick/20260730-judge-research-model-switches/PLAN.md` (the spec — LOCKED)
- `.planning/milestones/v0.4-phases/19-verification-debt-closure/19-OPERATOR-RUNBOOK.md` (deploy wrapper form)
- Eval evidence driving this change: scratchpad haiku_vs_sonnet_results.json / frontier_obs.json (session-local)

</canonical_refs>
