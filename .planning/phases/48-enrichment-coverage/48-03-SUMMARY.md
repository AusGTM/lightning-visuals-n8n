---
phase: 48-enrichment-coverage
plan: 03
subsystem: enrichment
tags: [anthropic, web-research, icp-scoring, hubspot, cost-estimation]

requires:
  - phase: 48-01
    provides: "ORG_TYPE_DECISIONS table, VALID_ORG_TYPES import, estimate_phase48_cost(), COVERAGE_COMPANY_ID_ORDER"
  - phase: 47-veto-remediation
    provides: "47-COST-ESTIMATE.md document shape, ANTHROPIC_PER_RECORD_ESTIMATE_USD/N8N_EXECUTION_BUDGET_MONTH constants, refuse_if_over_budget()"
provides:
  - "48-COST-ESTIMATE.md — the ex-ante spend document, code-produced, approved by the operator"
  - "Racing NSW's 5th ORG_TYPE_DECISIONS entry, resolved to 'regulator' with an evidence URL"
  - "48-RESEARCH-RACING-NSW.json — the raw captured research artifact"
  - "RACING_NSW_ORG_TYPE_SYSTEM in src/web_research.py — a reusable one-off enum-constrained prompt pattern"
affects: [48-04, 48-05, 48-06]

actuals:
  tokens: 7608
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "One-off system-prompt override via an optional claude_web_research(record, system_prompt=None) param, keeping the shared production-parity RESEARCH_SYSTEM untouched"
    - "D-03 refusal function (resolve_racing_nsw_decision) separated from the literal ORG_TYPE_DECISIONS table, so the fallback logic is independently testable with synthetic responses"

key-files:
  created:
    - .planning/phases/48-enrichment-coverage/48-COST-ESTIMATE.md
    - .planning/phases/48-enrichment-coverage/48-RESEARCH-RACING-NSW.json
  modified:
    - src/web_research.py
    - scripts/enrich_coverage_companies.py
    - tests/test_enrich_coverage_companies.py

key-decisions:
  - "Operator approved 'approve-as-estimated' at the Task 2 checkpoint, confirming Anthropic account credit was available, authorizing exactly the one Racing NSW call made in Task 3 (and, separately, plans 48-04's deploy+bounce and 48-05's armed write window as their own operator-run gates)."
  - "Racing NSW resolved to 'regulator', not the 'governing_body_league' the plan flagged as the likely outcome — the model cited Wikipedia and the Thoroughbred Racing Act 1996 to classify Racing NSW as the statutory regulator of the sport, not a league that itself administers competition. Recorded as returned and validated, never force-fit to the plan-time guess."
  - "Implemented the enum constraint as a new one-off prompt constant (RACING_NSW_ORG_TYPE_SYSTEM) plus an optional system_prompt override parameter on claude_web_research(), rather than editing the shared RESEARCH_SYSTEM in place — keeps the production-parity prompt untouched for every other caller."

patterns-established:
  - "D-03 fallback (out-of-vocabulary / bare-unknown / no-evidence-URL) as a pure, synthetic-response-testable function, used once to author a literal decision-table entry rather than run at import time — preserves the 'no regex/keyword mapper' invariant while still being test-provable."

requirements-completed: [COVER-01, COVER-02]

coverage:
  - id: D1
    description: "Ex-ante cost estimate produced by a live estimate_phase48_cost() call, covering both the n8n monthly allowance and the current Lusha balance, committed before any paid call."
    requirement: "COVER-02"
    verification:
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_budget_within_budget_returns_ids_unmodified_same_length_and_order"
        status: pass
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_tracer_refuse_if_over_budget_raises_and_never_returns_a_shorter_list"
        status: pass
    human_judgment: false
  - id: D2
    description: "Operator approved the spend and D-06 window declaration as a separable decision before the paid call was made."
    verification: []
    human_judgment: true
    rationale: "Operator approval is a human decision by definition; recorded verbatim below, not something a test can assert."
  - id: D3
    description: "Racing NSW's fresh research is constrained to the 9 live lv_org_type enum options, with a D-03 fallback for out-of-vocabulary/unevidenced results, and folded into ORG_TYPE_DECISIONS as the 5th entry."
    requirement: "COVER-01"
    verification:
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_racing_nsw_prompt_lists_all_9_options_and_the_unknown_instruction"
        status: pass
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_resolve_racing_nsw_decision_out_of_vocabulary_routes_to_d03_marker"
        status: pass
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_resolve_racing_nsw_decision_valid_enum_without_evidence_url_routes_to_d03_marker"
        status: pass
      - kind: unit
        ref: "tests/test_enrich_coverage_companies.py::test_racing_nsw_captured_artifact_exists_and_is_the_fifth_decision"
        status: pass
    human_judgment: false

duration: ~35min (Task 1 + checkpoint wait excluded) across two agent sessions, separated by the operator decision gate
completed: 2026-08-13
status: complete
---

# Phase 48 Plan 03: Ex-Ante Estimate, Operator Approval, Racing NSW Research Summary

**Code-produced cost estimate approved by the operator, then one enum-constrained Anthropic
call resolved Racing NSW to `regulator` (not the flagged-likely `governing_body_league`),
completing all 5 `ORG_TYPE_DECISIONS` entries with zero HubSpot writes and zero provider
credits drawn.**

## Performance

- **Task 1 committed:** 2026-08-12T23:15:24+10:00 (previous agent session)
- **Task 2 (checkpoint) resolved:** operator responded `approve-as-estimated` with Anthropic
  credit confirmed
- **Task 3 committed:** 2026-08-13T05:56:45+10:00 (this session)
- **Tasks:** 3 (1 auto, 1 checkpoint:decision, 1 auto)
- **Files modified this session (Task 3):** 4 (3 source/test files + 1 new artifact)

## Accomplishments

- `48-COST-ESTIMATE.md` produced from a live `estimate_phase48_cost()` call (Task 1, prior
  session): 1 web-research call, 6 n8n executions (5 D-09 recompute POSTs + 1 disarmed
  deploy-proof execution), 0 provider credits, ~$0.0686 order-of-magnitude Anthropic floor,
  Lusha balance 3925 read live at 2026-08-12T13:14:02Z. Both refuse-whole budget tests
  (over-budget raises, within-budget returns the id list unmodified) pass.
- Operator approved `approve-as-estimated` at the Task 2 checkpoint (see below), authorizing
  exactly the one paid call made in Task 3.
- `src/web_research.py` gained `RACING_NSW_ORG_TYPE_SYSTEM`, a one-off system prompt
  enum-constraining `lv_org_type` to the 9 live `VALID_ORG_TYPES`, and `claude_web_research()`
  gained an optional `system_prompt` override parameter (default `RESEARCH_SYSTEM`, unchanged
  for every other caller). `git diff` confirms `RESEARCH_SYSTEM`'s string body is untouched.
- Made the ONE authorized live Anthropic call for Racing NSW `15008671672`
  (`USE_MOCK_WEB_RESEARCH=false`). Raw `ProviderResult` captured verbatim to
  `48-RESEARCH-RACING-NSW.json` before any interpretation.
- `resolve_racing_nsw_decision()` implements the three D-03 refusal conditions
  (out-of-vocabulary value, bare `"unknown"` answer, valid-enum-but-no-evidence-URL), each
  proven by a synthetic-response test — never guesses, never force-fits.
- `ORG_TYPE_DECISIONS` now has all 5 entries. The two stale tests that asserted Racing NSW
  was still `PendingResearch` were updated to assert the resolved decision instead.

## Task Commits

1. **Task 1: Produce 48-COST-ESTIMATE.md from a live estimate_phase48_cost() call** —
   `85bb4cd` (feat) — completed by the prior agent session, verified present before this
   session began work.
2. **Task 2: Operator approves the separable spend and the window declaration** —
   checkpoint, no file changes; resolved by the operator response captured below.
3. **Task 3: One enum-constrained research call for Racing NSW, captured and mapped** —
   `d239258` (feat)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `.planning/phases/48-enrichment-coverage/48-COST-ESTIMATE.md` — ex-ante estimate document (Task 1)
- `.planning/phases/48-enrichment-coverage/48-RESEARCH-RACING-NSW.json` — raw captured research response for Racing NSW (Task 3)
- `src/web_research.py` — added `RACING_NSW_ORG_TYPE_SYSTEM` constant + optional `system_prompt` param on `claude_web_research()`
- `scripts/enrich_coverage_companies.py` — added `research_racing_nsw()`, `resolve_racing_nsw_decision()`, `_fetch_racing_nsw_record()`, and the fifth `ORG_TYPE_DECISIONS` entry (Racing NSW → `regulator`)
- `tests/test_enrich_coverage_companies.py` — 7 new tests for the prompt, the captured artifact, and the three D-03 fallback branches; 2 stale `PendingResearch` tests updated to assert the resolved decision

## Decisions Made

**Operator's checkpoint decision (Task 2), recorded verbatim:**

> **APPROVE-AS-ESTIMATED.** The operator approved the spend exactly as projected: 1 Anthropic
> web-research call for Racing NSW `15008671672` (~$0.0686 order-of-magnitude floor), 6 n8n
> executions against the 2,500/month allowance (5 D-09 recompute POSTs + 1 disarmed
> deploy-proof run), 0 provider credits (Lusha balance 3925, unaffected). The operator
> confirmed Anthropic account credit is available. This authorizes Task 3's single paid
> research call, made immediately. It also pre-authorizes plan 48-04's deploy+bounce and plan
> 48-05's armed write window as their own operator-run gates — not delegated to the executor.

Task 3 ran only after this selection was recorded, per the plan's own acceptance criteria.

**Racing NSW's resolved org type — `regulator`, not `governing_body_league`.** The plan
explicitly flagged `governing_body_league` as the "likely outcome" but required the written
value to be whatever the call actually returned and validated. The live call (matched=true,
confidence=95) cited Wikipedia and the Thoroughbred Racing Act 1996: Racing NSW is a body
corporate established by statute to control, supervise, and regulate thoroughbred racing in
NSW — a regulator, not a league or governing body that itself administers competition.
`regulator` is a valid `VALID_ORG_TYPES` member with an `evidence_by_field["lv_org_type"]`
URL, so it was recorded as-returned. This is reported here, not suppressed or re-guessed —
per the plan's own instruction, if the call returns a value that changes the ICP-scoring
outcome (base_score `regulator: -20` vs `governing_body_league: 40`), that is correct and
must be disclosed, and it is plan 48-05's job to write it, not this plan's.

**One-off prompt over shared-prompt edit.** Implemented via a new module-level constant
(`RACING_NSW_ORG_TYPE_SYSTEM`) plus an optional `system_prompt` parameter on
`claude_web_research()`, rather than editing `RESEARCH_SYSTEM` in place. This matches
48-RESEARCH.md's own recommendation (option (b), lower blast radius) and keeps the
production-parity prompt unchanged for every other caller, including any future n8n-side
port.

## Deviations from Plan

None — plan executed as written. The Racing NSW result differing from the "likely" guess is
not a deviation; it is the outcome the plan explicitly anticipated and required to be honestly
recorded rather than suppressed.

## Issues Encountered

**Actual Anthropic token usage for the Racing NSW call was not separately captured** —
`claude_web_research()` does not currently log `msg.usage`, and this plan's `<files>` scope
did not include adding that instrumentation. The `~$0.0686` Phase-20-canary floor from
`48-COST-ESTIMATE.md` remains the only cost figure available for plan 48-06's Actuals table;
the real cost is very likely in the same order of magnitude (one Sonnet call, up to 5 web
searches) but is not independently measured here. Flagging for 48-06 rather than
re-running the call to capture it (phase hard rule: exactly one paid call, no retry).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `ORG_TYPE_DECISIONS` is complete (5/5 entries) — plan 48-04 (deploy+bounce) and plan 48-05
  (armed write window) are unblocked on this input.
- Plan 48-05's write leg should be aware Racing NSW's veto-relevant score input differs from
  the informal "likely governing_body_league" assumption: `regulator` scores a `-20` base
  component (not `+40`), which may move Racing NSW's tier when the D-09 recompute runs.
  Nothing in this plan wrote that value or recomputed the score — flagging so 48-05/48-06 do
  not treat the tier shift as a surprise.
- Actual Anthropic token/dollar cost for the Racing NSW call is not separately measured (see
  Issues Encountered) — 48-06's Actuals table will carry the estimate-floor figure unless
  instrumentation is added.
- No arming, no deploy, no HubSpot writes occurred in this plan — confirmed by code review of
  every call made (`get_record` read + one `claude_web_research` call only).

---
*Phase: 48-enrichment-coverage*
*Completed: 2026-08-13*
