---
phase: 61-autonomous-batch-runs
plan: "01"
subsystem: infra
tags: [n8n, hubspot, async-execution, spike, run-state]

requires: []
provides:
  - "61-SPIKE-VERDICT.md — decided run-state store (HubSpot object + run_manifest.py) and per-question verdicts on all four async dispatch substrates"
  - "All six previously-`[unknown]` premises (P-05, P-07, P-08, P-09, P-10, P-13) answered and recorded with basis tokens"
  - "Sub-workflow dispatch (Execute Workflow, wait-for-completion off) identified as the strongest dispatch candidate for 61-05, unmetered and uncapped on this Starter plan"
  - "operator-claude-plugin/tests/test_spike_verdict_61.py — completeness lint over the verdict doc, now asserting zero remaining unknowns"
affects: [61-05, 61-06]

actuals:
  tokens: 10994
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Basis-token discipline ([measured]/[derived]/[documented]/[unknown]) on every claim line in a decision document, enforced by a text-only completeness test"
    - "Premises-with-dependents table so a later plan's halt gate is a lookup, not a judgement call"

key-files:
  created: []
  modified:
    - .planning/phases/61-autonomous-batch-runs/61-SPIKE-VERDICT.md
    - operator-claude-plugin/tests/test_spike_verdict_61.py

key-decisions:
  - "Operator selected run-state store: a HubSpot object (run handle + progress) plus the existing run_manifest.py (per-row verdicts) — not n8n staticData, not the executions API alone."
  - "All six unresolved premises closed by evidence (three from n8n's own published docs, three from a live disarmed probe costing 5 n8n executions) rather than deferred or proceeded-under-unknown."
  - "Sub-workflow dispatch (substrate 3) flagged for 61-05 as the strongest dispatch candidate — a separate axis from the run-state store decided here — because it is unmetered, uncapped, and its detached child's execution id is correlatable."

patterns-established:
  - "Claim-line basis-token lint: every bullet/numbered line in a decision doc's load-bearing sections must carry exactly one of [measured]/[derived]/[documented]/[unknown], text-only, no import/execution of what it checks."

requirements-completed: [RUN-03]

coverage:
  - id: D1
    description: "Operator decided where async run state lives (HubSpot object + client manifest) at the Task 4 checkpoint"
    requirement: RUN-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_spike_verdict_61.py::test_premises_section_non_empty_with_id_basis_and_dependents"
        status: pass
    human_judgment: false
  - id: D2
    description: "All six previously-unresolved premises (P-05, P-07, P-08, P-09, P-10, P-13) now carry a resolved basis token and are documented in ## Unresolved"
    requirement: RUN-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_spike_verdict_61.py::test_previously_unknown_premises_now_carry_a_non_unknown_basis"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_spike_verdict_61.py::test_premises_unknowns_appear_in_unresolved_with_a_command"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-30
status: complete
---

# Phase 61 Plan 01: Async Run Substrate Spike Verdict Summary

**Operator chose HubSpot-object-plus-client-manifest for async run state; all six previously-open premises closed by n8n docs and a live disarmed probe, with sub-workflow dispatch surfacing as 61-05's strongest candidate.**

## Performance

- **Duration:** 45min (this continuation session; Tasks 1-3 ran in a prior session)
- **Started:** 2026-08-30 (continuation)
- **Completed:** 2026-08-30
- **Tasks:** 4/4 (Tasks 1-3 completed in a prior session; Task 4, the checkpoint, completed this session)
- **Files modified:** 2 (owned by this plan) + 4 committed evidentiary files (owned by other work, committed here per `<task_4_scope>`)

## Accomplishments

- Recorded the operator's Task 4 decision: run state for an async batch run lives in a HubSpot
  object (run handle + progress) plus the existing `run_manifest.py` (per-row verdicts) — a
  combination of two of the four options the checkpoint offered.
- Closed all six previously-`[unknown]` premises (P-05, P-07, P-08, P-09, P-10, P-13) in
  `61-SPIKE-VERDICT.md`, updating their basis tokens in place across `## Substrates`,
  `## Execution arithmetic`, `## Premises`, and `## Unresolved` — three answered from n8n's own
  published documentation, three from a live disarmed probe the operator authorised.
- Added a `## Operator Decision (Task 4)` section to the verdict doc recording the decision, its
  stated basis, the disposition of every `## Unresolved` entry, and the two architecture findings
  below.
- Updated `test_spike_verdict_61.py`'s premises-completeness assertion to match the new honest
  state (zero open unknowns) without weakening the contract: it now requires `## Unresolved` to
  say explicitly that everything was resolved, and a new test pins all six formerly-unknown
  premise ids to a resolved basis token by name.
- Committed the evidentiary write-up (`61-PREMISE-DOCS-FINDINGS.md`), the machine-readable probe
  results (`61-PREMISE-PROBE-VERDICT.json`), and the probe script + its offline tests
  (`scripts/probe_n8n_async_semantics.py`, `tests/test_probe_n8n_async_semantics.py`) — produced
  outside this plan's own tasks, staged by explicit path, unmodified.

## Architecture findings carried forward to 61-05 (not decided by this checkpoint)

Task 4's decision scope was the run-state **store** only. Two findings about the dispatch
**mechanism** — a separate axis — surfaced during premise resolution and must inform 61-05:

1. **Sub-workflows are doubly exempt.** n8n's own published documentation states a parent
   `Execute Workflow` node fanning out to N children costs one billable execution, not `1 + N`
   (only the parent counts toward the 2,500/month allowance), and that sub-workflow executions do
   not count against the Starter plan's 5-concurrent cap either. Combined with the live probe
   confirming (P-13) that a detached child's execution id is correlatable from the parent's own
   `runData` — true both with `waitForSubWorkflow` off and on — substrate 3 (sub-workflow
   dispatch, wait-for-completion off) is now the strongest dispatch candidate on this Starter
   plan: unmetered, uncapped, and observable. It is also a confirmed candidate explanation for the
   P-10 formula-over-count anomaly (a real 2-record chunk, execution `11950`, projected 3
   executions but listed only 1).
2. **A deployment-ordering constraint, discovered by a probe failure.** n8n refuses to activate a
   parent whose `Execute Workflow` node references an unpublished child workflow
   ("Cannot publish workflow: Node ... references workflow \<id\> which is not published. Please
   publish all referenced sub-workflows first."). Any sub-workflow architecture 61-05 builds must
   publish children before the parent.

## Task Commits

Tasks 1-3 were completed and committed in a prior session:

1. **Task 1: Enumerate the candidate async substrates from repo evidence, with a verdict each** - `118fefb` (feat)
2. **Task 2: Cost a 40-record and a 300-record batch in executions, per substrate, offline** - `8f43b8e` (feat)
3. **Task 3: Write the machine-readable premises block and its completeness test** - `dc42c5b` (docs)

This session:

4. **Task 4: Operator decides where run state lives (checkpoint:decision)** - `8ab0f22` (docs) —
   records the operator's run-state decision, closes all six premises, and commits the
   evidentiary files that supported the decision.

_No TDD tasks in this plan; the deliverable is a decision document, not production code._

## Files Created/Modified

- `.planning/phases/61-autonomous-batch-runs/61-SPIKE-VERDICT.md` - all six formerly-`[unknown]`
  premises updated with resolved basis tokens across `## Substrates`, `## Execution arithmetic`,
  `## Premises`, `## Unresolved`; new `## Operator Decision (Task 4)` section recording the choice
- `operator-claude-plugin/tests/test_spike_verdict_61.py` -
  `test_premises_unknowns_appear_in_unresolved_with_a_command` updated to require `## Unresolved`
  to state explicitly that everything was resolved when zero `[unknown]` premises remain; new
  `test_previously_unknown_premises_now_carry_a_non_unknown_basis` pins the six formerly-open
  premise ids to a resolved basis token by name

Committed alongside (produced outside this plan's own tasks, per `<task_4_scope>`, unmodified,
staged by explicit path — evidence for the decision recorded above):

- `.planning/phases/61-autonomous-batch-runs/61-PREMISE-DOCS-FINDINGS.md` - documentation-sourced
  answers to P-05, P-08, P-09, plus the sub-workflow-exemption and deployment-ordering findings
- `.planning/phases/61-autonomous-batch-runs/61-PREMISE-PROBE-VERDICT.json` - machine-readable
  results of the live disarmed probe for P-07, P-10, P-13
- `scripts/probe_n8n_async_semantics.py` - the disarmed probe script used to answer P-07/P-10/P-13
- `tests/test_probe_n8n_async_semantics.py` - offline unit tests for the probe script (18 tests)

## Decisions Made

- **Run-state store: HubSpot object + `run_manifest.py`.** Operator's stated basis: depends on
  none of n8n's remaining unknowns, costs zero n8n executions and zero concurrency slots per
  progress read, survives both an n8n restart and the end of the session that started the run.
  The executions-API option was weakened by the sub-workflow findings, since it depends on
  correlating executions across a system boundary the store doesn't need to touch.
- **All six premises closed, none deferred.** The operator explicitly ruled: "All six
  previously-unresolved premises are now ANSWERED. None is deferred. 61-05 must NOT halt on any
  of them." This is recorded verbatim in the verdict doc's `## Operator Decision (Task 4)`
  section so 61-05's premise re-assertion at execution time reads a closed state, not a judgment
  call.
- **Basis-token mapping for the six resolved premises:** the three doc-sourced answers (P-05,
  P-08, P-09) use `[documented]` (matching the verdict doc's own controlled vocabulary — "an n8n
  behaviour stated in ... a cited n8n doc URL"); the three probe-sourced answers (P-07, P-10,
  P-13) use `[measured]` (matching "read out of live execution history"), even though
  `61-PREMISE-DOCS-FINDINGS.md` itself uses the word "observed" for the probes — the verdict
  doc's basis-token set is a closed four-word vocabulary (`measured`/`derived`/`documented`/
  `unknown`) enforced by the completeness test, so "observed" was mapped onto the nearest fit
  rather than introduced as a fifth token.
- **P-08's two sub-cases (Wait-node parking vs. detached-child dispatch) both closed under one
  documented citation**, per explicit operator instruction not to re-litigate. The residual scope
  caveat from `61-PREMISE-DOCS-FINDINGS.md` ("persisting a Wait execution does not imply recovery
  ... it is a guarantee about parked executions, not about executions generally") is recorded
  inline rather than reopened as a new unknown.
- **One residual, substrate-specific `[unknown]` claim was deliberately left untouched:**
  substrate 1's Q-03 ("does an ACTIVELY RUNNING, non-parked execution survive a platform restart")
  was never elevated to a numbered premise in Task 3's original pass and is not one of the six the
  operator was asked to close. It genuinely remains open — the docs findings' own scope caveat
  ("not about executions generally") applies directly to it — and it carries no dependents that
  would block 61-05, since 61-05's dispatch axis now favors substrate 3 over substrate 1.

## Deviations from Plan

None (Rules 1-3) — this was a documentation-only continuation completing the plan's own Task 4 as
scoped. One item worth flagging as a scope note rather than a deviation:

**Extra section added beyond the plan's literal spec.** The plan's Task 4 `<action>`/`<context>`
describes the checkpoint's *dialogue* (what to present, what the operator answers) but does not
explicitly require a new heading in the verdict doc recording the outcome. A `## Operator Decision
(Task 4)` section was added so the decision, its basis, and the two carried-forward architecture
findings are durably recorded in the machine-read contract document itself, not only in this
SUMMARY — consistent with the plan's own framing of the verdict doc as "a decision document" and
the `must_haves` truth that "the run-state location is DECIDED by the operator at a checkpoint."
This section is additive and is not covered by the existing completeness tests (which only
validate `## Substrates`, `## Execution arithmetic`, `## Premises`, `## Unresolved`); no test was
written against it because it is prose narration of a decision already fully captured, in
machine-checkable form, by the premises/basis-token updates the tests do cover.

## Issues Encountered

None. The six premises' resolutions were already fully specified in the operator's
`<operator_decision>` and `<premise_answers>` briefing plus the two source documents
(`61-PREMISE-DOCS-FINDINGS.md`, `61-PREMISE-PROBE-VERDICT.json`); this session's work was
transcription, cross-referencing, and test-contract maintenance rather than new investigation.

## User Setup Required

None - no external service configuration required. (This plan writes no production code; the
run-state HubSpot property itself is 61-05's own task, not this plan's.)

## Next Phase Readiness

61-05 can now be planned and executed against a `## Premises` block that:
- carries zero remaining `[unknown]` entries among the six the operator was asked to close,
- names the run-state store to build against (HubSpot object + `run_manifest.py`),
- names sub-workflow dispatch as the informed starting point for the dispatch-mechanism decision
  (a separate axis 61-05 still owns), with its deployment-ordering constraint recorded, and
- is proven complete and placeholder-free by `test_spike_verdict_61.py` (13 tests, all passing).

No blockers. Full test suites confirmed green post-change: root suite 3482 passed / 154 skipped
(baseline 3481/154, +1 for the new premises test); plugin suite 1819 passed / 5 skipped; node
suite 816/816; probe offline tests 18/18.

Zero n8n executions, zero HubSpot calls, zero provider credits, and zero Anthropic calls were
spent by this session's own work — the 5 n8n executions referenced above were spent by the prior,
operator-authorised probe run and are recorded in `61-PREMISE-PROBE-VERDICT.json`, not by this
plan's own tasks.

---
*Phase: 61-autonomous-batch-runs*
*Completed: 2026-08-30*
