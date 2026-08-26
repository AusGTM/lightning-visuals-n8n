---
phase: 58-take-what-the-operator-actually-has
plan: 02
subsystem: n8n-orchestration
tags: [n8n, webhook, probe, spike, decide-company-action, hubspot]

requires:
  - phase: 47.5-veto-recompute-path
    provides: the recompute lane (recompute=true routes a complete company straight to Decide Company Action with zero provider/research/judge nodes)
provides:
  - Confirmed on live runData that a request-level `mode` key survives Parse HubSpot Event onto a company row and is read by Decide Company Action's isReturnOnly, forcing a non-writing "proposed" action before the write-safety allowlist check
  - Documented that the current return-only response body's match/candidates shape is contact-oriented (email/object-id/name+company), not company-oriented -- a caller cannot read a proposed domain out of it today
  - Operator decision (defer-residual) on record for 58-04 to branch on
affects: [58-03, 58-04]

actuals:
  tokens: 4596
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns: ["probe script rides an existing lane (recompute) to reach a target node at zero cost instead of adding a new lane"]

key-files:
  created:
    - scripts/probe_company_propose_mode.py
    - tests/test_company_propose_mode_event.py
    - .planning/phases/58-take-what-the-operator-actually-has/58-SPIKE-VERDICT.md
  modified:
    - scripts/remediate_veto_companies.py

key-decisions:
  - "Task 3 (operator, 2026-08-26): defer-residual -- ship the client-side domain-proposal path this phase, do not extend the backend research node to seek a domain. The backend deploy+bounce+live-Anthropic-call cost isn't justified against the client path already covering most rows."
  - "The propose-mode traced claim from 58-RESEARCH.md is CONFIRMED live (execution 11972), not merely traced from source."
  - "Shape finding: the return-only response's match object is contact-shaped, so extending the backend later will also need a company-shaped match/candidates contract, not just a prompt/schema change -- named for 58-04 to read alongside the deferral."

patterns-established:
  - "Live observation over stored read-back: a probe must read the dispatched execution's own runData, never a re-fetched/stored copy, before a traced claim is treated as proven (project-standing rule, reapplied here)."

requirements-completed: [INPUT-02, INPUT-03]

coverage:
  - id: D1
    description: "Live-confirm that a request-level mode key rides the row spread to Decide Company Action and forces a non-writing proposed action"
    requirement: "INPUT-03"
    verification:
      - kind: manual_procedural
        ref: "operator-run scripts/probe_company_propose_mode.py --execute, execution 11972, verbatim output pasted in the checkpoint response and archived in 58-SPIKE-VERDICT.md"
        status: pass
    human_judgment: true
    rationale: "A live n8n execution against a production webhook cannot be run or independently re-verified by the executor -- the operator holds the only armed shell and pasted the runData-derived output back for the record."
  - id: D2
    description: "Operator decision recorded in writing on whether the backend research node is extended to seek a domain this phase"
    requirement: "INPUT-02"
    verification:
      - kind: manual_procedural
        ref: ".planning/phases/58-take-what-the-operator-actually-has/58-SPIKE-VERDICT.md -- decider, date, and reason recorded"
        status: pass
    human_judgment: true
    rationale: "This is an operator scope decision by design (checkpoint:decision, gate=blocking) -- not something a test can classify pass/fail."

duration: ~10min
completed: 2026-08-26
status: complete
---

# Phase 58 Plan 02: Propose-Mode Observation Spike Summary

**Live execution (11972) confirms `mode: "propose"` rides the recompute lane to `Decide Company Action` and forces a non-writing `"proposed"` action; operator deferred the backend research-node extension to a later phase.**

## Performance

- **Duration:** ~10min (resumed from Task 2 checkpoint)
- **Tasks:** 3 (1 completed in prior session, 2 completed this session)
- **Files modified:** 4 (1 new this session — the verdict file; 3 already committed under Task 1)

## Accomplishments
- Converted the phase's one unproven architectural claim (that an unrecognized `mode` key survives to `Decide Company Action`'s `isReturnOnly`) into observed, live evidence — execution `11972`, read from the execution's own runData.
- Documented a structural finding about the return-only response body: its `match`/`candidates` shape is built for contact identity checks, not companies, so a caller cannot read a proposed domain out of it as it stands today.
- Got the operator's scope decision on the record in writing: defer the backend research-node extension, ship the client-side path this phase, with the residual named explicitly against INPUT-02 for `58-04` to read and branch on.

## Task Commits

Each task was committed atomically:

1. **Task 1: The probe driver — offline, with the event body pinned** - `3f979c6` (feat, prior session)
2. **Task 2 + 3: Live probe evidence + operator decision** - `660cddb` (docs) — human-verify checkpoint and decision checkpoint have no independent code to commit; both are recorded together in the verdict file since Task 3's decision explicitly required "the spike verdict in hand."

**Plan metadata:** (this commit) `docs(58-02): complete propose-mode observation spike plan`

## Files Created/Modified
- `scripts/probe_company_propose_mode.py` - disarmed-by-default probe (`--plan`/`--execute`) that rides the recompute lane to reach `Decide Company Action` at zero cost (Task 1, prior session)
- `scripts/remediate_veto_companies.py` - added optional `mode` keyword to `build_webhook_event`, byte-identical default shape preserved (Task 1, prior session)
- `tests/test_company_propose_mode_event.py` - offline event-body pins (Task 1, prior session)
- `.planning/phases/58-take-what-the-operator-actually-has/58-SPIKE-VERDICT.md` - observed answers, cost actuals, operator decision (Task 2+3, this session)

## Decisions Made
- **Defer-residual selected over extend-now** (operator, 2026-08-26): the client-side domain-proposal path (D-58-01/04/06/07) already covers the common case for free; extending the backend research node would cost a deploy+bounce+live-Anthropic-call proof that isn't justified this phase. See `58-SPIKE-VERDICT.md` for the full reasoning and the INPUT-02 residual statement.

## Deviations from Plan

None — plan executed exactly as written. Task 2's checkpoint was answered by the operator running the probe live and pasting back the verbatim output; Task 3's checkpoint was answered by the operator's explicit decision. Both are recorded in `58-SPIKE-VERDICT.md` rather than as separate commits, since the plan's own artifact list names the verdict file as the single record of both tasks' outcomes.

## Issues Encountered

None. Both automated test suites (`.venv/bin/python -m pytest tests/ -q`: 1585 passed, 149 skipped; `node --test tests/n8n/*.test.mjs`: 727 passed) were green before and remained green — this plan's live-observation tasks touch no code path exercised by either suite. `git diff --stat n8n/` confirmed empty — nothing was deployed or hand-edited.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`58-04` can now read `58-SPIKE-VERDICT.md` and branch on the confirmed defer-residual decision rather than assuming a scope. The contact-shaped `match`/`candidates` finding should inform any future phase that does extend the backend research node — the response contract, not just the prompt/schema, will need a company-shaped variant.

---
*Phase: 58-take-what-the-operator-actually-has*
*Completed: 2026-08-26*
