---
phase: 62-suggest-the-contacts-nobody-named
plan: 03
subsystem: enrichment
tags: [suggest-contacts, write-grant, cost-guard, budget-ceiling, python]

requires:
  - phase: 53-operator-openable-write-grant
    provides: "the opening grant envelope (envelope()/plan_grant()) and the 'one grant, one yes' consent property this plan folds the suggestion allowance into"
  - phase: 57-ceilings-refusal-before-start-and-post-run-proof
    provides: "CEILING_OVER refusal-before-start and its split_offer/_affordable_record_count, reused verbatim rather than reimplemented (D-62-13)"
provides:
  - "cost_guard.suggestion_line(company_count, per_company_cap, rates): a two-component worst-case ceiling (stage-1 page-fetch ceiling, dollar figure tri-state unmeasured; stage-2 contact/credit ceiling at the CONTACTS rate)"
  - "write_grant.envelope(..., suggestion_companies=None, suggestion_cap=None): the suggestion round's cost folded into the SAME opening grant envelope, byte-identical when omitted"
  - "write_grant.plan_grant(..., suggestion_companies=None, suggestion_cap=None): the same two keyword-only arguments threaded through to its single envelope() call"
  - "figures['suggestion_allowance']: a third figures key, never colliding with figures['chunk_ceiling'] (int) or figures['ceiling'] (verdict dict), carrying priced_cap"
affects: [62-05]

actuals:
  tokens: 7624
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "readability-before-magnitude tri-state (cost_guard.research_line precedent), extended to a two-component ceiling"
    - "envelope over-states rather than under-states (write_grant's established direction, D-62-14 keeps it)"
    - "a THIRD figures-dict key for a new figure, never reusing a name a prior CR-01 regression already collided on"

key-files:
  created:
    - operator-claude-plugin/tests/test_cost_guard_suggestion.py
    - operator-claude-plugin/tests/test_write_grant_suggestion.py
  modified:
    - operator-claude-plugin/config/cost_rates.json
    - operator-claude-plugin/scripts/cost_guard.py
    - operator-claude-plugin/scripts/write_grant.py

key-decisions:
  - "Task 2's checkpoint decision: fold the suggestion allowance into the SAME opening grant envelope (one-envelope), not a separate spend confirmation -- the operator's own answer, quoted below."
  - "Stage 2 always prices at the CONTACTS rate (lusha_contacts_first_time_enrich), never the companies rate, even when the batch's own object_type is companies -- stage 2 enriches people, not the companies they work at."
  - "The suggestion allowance's execution weight is folded into projected_executions using the SAME chunk_count + record_count arithmetic already used for the batch's own records (a fresh chunking.plan_chunks call over a dummy record_ids list sized to the stage-2 contact ceiling), so the two projections can never drift apart."
  - "figures['record_count'] is deliberately left untouched by a priced suggestion round -- its disclosure sentence promises records 'named by this grant and by nothing else', and suggested people are not named yet."
  - "priced_cap defaults to PRICED_CAP = 3 (the top of D-62-12's 2-to-3 band) when the caller supplies no cap, because the envelope is built at grant-open, before the sitting has chosen one."

patterns-established:
  - "Pattern 1: a keyword-only pair defaulting to None widens a function's contract with a guaranteed byte-identical path for every existing caller -- pinned by an explicit equality/absence test, not assumed."

requirements-completed: [SUGGEST-05]

coverage:
  - id: D1
    description: "suggestion_line() prices a suggestion round as a two-component ceiling: stage-1 discovery in page fetches (dollar figure tri-state, unmeasured for any non-empty set, never rendered as $0) and stage-2 enrichment in provider credits at the CONTACTS rate, both named in one rendered sentence"
    requirement: SUGGEST-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard_suggestion.py#test_non_empty_set_with_shipped_null_rate_is_unmeasured_not_zero"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard_suggestion.py#test_stage1_fetch_ceiling_equals_companies_times_max_followup_fetches"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard_suggestion.py#test_stage2_uses_contacts_rate_key_even_for_a_companies_object_type_batch"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard_suggestion.py#test_line_never_presents_the_credit_figure_alone"
        status: pass
    human_judgment: false
  - id: D2
    description: "the suggestion allowance is folded into the SAME opening grant envelope as the enrichment cost -- one disclosure, one yes -- per the operator's Task 2 checkpoint answer (one-envelope)"
    requirement: SUGGEST-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_omitting_both_suggestion_args_leaves_figures_identical_to_the_pre_phase_62_call"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_a_priced_suggestion_round_is_a_third_figures_key_never_colliding_with_ceiling"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_record_count_is_unchanged_by_a_suggestion_allowance"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_priced_cap_defaults_to_3_the_top_of_the_2_to_3_band_when_no_cap_supplied"
        status: pass
    human_judgment: false
  - id: D3
    description: "a batch whose suggestion weight alone pushes projected executions over the sampled monthly ceiling is refused before it starts (CEILING_OVER), carrying Phase 57's existing split_offer with an affordable_spec -- D-62-13 reused, not reimplemented"
    requirement: SUGGEST-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_plan_grant_refuses_over_ceiling_when_only_the_suggestion_weight_pushes_it_over"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_projected_executions_with_a_suggestion_allowance_is_strictly_greater"
        status: pass
    human_judgment: false
  - id: D4
    description: "the existing enrichment-only write-grant contract is untouched: envelope()/plan_grant() called without the two new keyword arguments produce a byte-identical figures dict and block text"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py (full suite, unmodified)"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_suggestion.py#test_plan_grant_with_no_suggestion_args_is_unaffected_by_the_new_kwargs"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-02
status: complete
---

# Phase 62 Plan 03: Price the suggestion round inside the grant Summary

**`cost_guard.suggestion_line()` prices a suggestion round as a two-component worst-case ceiling (unmeasured stage-1 page fetches, stage-2 Lusha-contact credits), and `write_grant.envelope()`/`plan_grant()` fold that allowance into the SAME opening grant envelope the operator already opens for enrichment — one disclosure, one yes, and an over-budget round refused before it starts using Phase 57's existing `CEILING_OVER` split offer.**

## Performance

- **Duration (this continuation, Tasks 2-3):** ~25 min
- **Task 1:** completed by a prior executor agent (see commits `bd05a9a`/`40f1c3e`), summarized here for the first time since this is the plan's only SUMMARY
- **Tasks:** 3 (all complete)
- **Files modified:** 5 (2 created, 3 modified)

## Checkpoint Decision (Task 2)

**Decision:** Does the suggestion round's cost go into the SAME opening grant envelope as the enrichment cost (one number, one yes), or does it get its own spend confirmation later in the session?

**Answer: `one-envelope`** — the human operator, at the `gate="blocking-human"` checkpoint. This is D-62-11, rated **one-way** by CONTEXT.md: *"a single grant covers the entire session (this would include suggestions)."* The operator was shown and accepted the disclosed consequences before answering:
- the grant's disclosed number gets bigger on every batch, whether or not a round is later run;
- the allowance is priced worst case (every company in the batch treated as eligible for the full per-company cap);
- a batch that previously fit under the monthly ceiling may now be refused as `CEILING_OVER`, carrying Phase 57's split offer.

`separate-ask` was explicitly not chosen. Task 3 was executed as written.

## Accomplishments
- `cost_guard.suggestion_line(company_count, per_company_cap, rates)` (Task 1, already committed by the prior agent): a tri-state, two-component ceiling — stage 1 in page fetches (`MAX_FETCHES_PER_COMPANY`, imported from `url_fallback.MAX_FOLLOWUP_FETCHES`, never re-declared), stage 2 in Lusha contact credits (always the CONTACTS rate, even for a companies-object-type batch). The new `suggestion_stage1_discovery` rate key ships `null` and the rendered line never shows `$0`.
- `write_grant.envelope()` gained keyword-only `suggestion_companies`/`suggestion_cap`, both defaulting to `None` — a byte-identical path for every existing caller (pinned by an explicit test, not assumed).
- A priced round lands at `figures["suggestion_allowance"]`, a **third** name — deliberately never `ceiling` (the verdict dict) or `chunk_ceiling` (the int cap), the exact CR-01 collision this plan's read_first named. `priced_cap` rides on the same dict so a later sitting can read what was actually priced and refuse a cap above it.
- The round's stage-2 contact ceiling is folded into `projected_executions` **before** `ceiling_verdict` runs, using a fresh `chunking.plan_chunks` call sized to the contact ceiling — the identical `chunk_count + record_count` shape the batch's own records already use, so the two projections can never drift apart.
- `figures["record_count"]` is untouched by a priced round: its disclosure sentence promises records "named by this grant and by nothing else", and suggested people are not named yet.
- `plan_grant()` threads the same two keyword-only arguments straight through to its single `envelope()` call — no change to the frozen call order, no change to the `CEILING_OVER` branch itself. A batch that fits without the allowance can now be refused with it, carrying the existing `split_for_allowance` offer unmodified.
- `_envelope_block()` renders the worst-case disclosure sentence and the round's own two-component line immediately after the provider table and before the execution projection.
- `PRICED_CAP = 3` (D-62-12's band top) is what an omitted `suggestion_cap` prices against at grant-open, before the sitting has chosen a cap.

## Task Commits

1. **Task 1: suggestion_line() — two components, one ceiling** (completed by a prior agent) — `bd05a9a` (test) → `40f1c3e` (feat)
2. **Task 2: checkpoint:decision — one-envelope vs separate-ask** — no code commit; the human operator's answer (`one-envelope`) is recorded above and gates Task 3
3. **Task 3: Fold the allowance into the envelope and the ceiling that already refuses** — `466f99a` (test) → `8ad3e73` (feat)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `operator-claude-plugin/config/cost_rates.json` — new `suggestion_stage1_discovery` rate entry, value `null`, unit `USD/company`, citation stating it must never be scaled from another rate
- `operator-claude-plugin/scripts/cost_guard.py` — `SUGGESTION_RATE_KEY`, `SUGGESTION_STAGE2_RATE_KEY`, `MAX_FETCHES_PER_COMPANY`, `suggestion_line()`
- `operator-claude-plugin/scripts/write_grant.py` — `PRICED_CAP`, `envelope(..., suggestion_companies=None, suggestion_cap=None)`, `plan_grant(..., suggestion_companies=None, suggestion_cap=None)`, `_envelope_block()`'s new suggestion-round lines
- `operator-claude-plugin/tests/test_cost_guard_suggestion.py` — 8 tests for `suggestion_line()`'s no-rows/unmeasured/two-component behaviour
- `operator-claude-plugin/tests/test_write_grant_suggestion.py` — 11 tests: byte-identical omitted path, the new figures key never colliding with the existing two, priced_cap defaulting/honouring, strictly-greater executions, and a `CEILING_OVER` refusal driven by the suggestion weight alone carrying `split_offer`

## Decisions Made
See "Checkpoint Decision (Task 2)" above for the load-bearing one. Implementation decisions:
- Stage 2's provider-credit ceiling always prices at the CONTACTS rate, regardless of the batch's own `object_type` — a companies-rate multiply would mislabel what stage 2 actually enriches (people, not companies).
- The suggestion round's execution weight is computed via a fresh `chunking.plan_chunks` call over a dummy `record_ids` list sized to the stage-2 contact ceiling, reusing the exact chunk-ceiling already resolved for the batch's own records, rather than a second, independently-derived formula that could silently diverge from it.
- `figures["suggestion_allowance"]` and `figures["basis"]["suggestion_allowance"]` are only added to `basis` when a round is actually priced (non-`None` `suggestion_companies`), keeping the omitted-args `basis` dict genuinely unchanged rather than merely "close enough".

## Deviations from Plan

None — plan executed exactly as written, including the checkpoint. Task 1 (already committed before this continuation began) was verified present and untouched; the git-stash / RED / GREEN sequence for Task 3 was re-verified independently in this session (stashed the implementation, confirmed 10 of 11 new tests genuinely failed with `TypeError: unexpected keyword argument`, restored the implementation, confirmed all 11 pass).

## Issues Encountered

One self-corrected test-authoring slip, fixed before any commit: the new test file initially lacked the `executions_client._workflow_id_cache`-clearing autouse fixture that `test_write_grant.py` already carries. Without it, a workflow id resolved and cached by an earlier test in the file caused a later test's scripted transport to be consumed out of order (the cached lookup skipped a GET the test had scripted a response for), surfacing as a `KeyError: 'kind'` on an otherwise-correct call. Added the same fixture `test_write_grant.py` uses; all 11 tests then passed. Caught during this session's own RED/GREEN verification, before either commit was made — not logged as a Rule-N deviation since it was corrected before any commit existed to deviate from.

## User Setup Required

None — no external service configuration required. This plan touches only local Python source and test files; no HubSpot credentials, no provider credentials, no network calls, nothing armed or deployed.

## Next Phase Readiness

- The grant's opening envelope now has a place for a suggestion round's cost (D-62-11), a worst-case ceiling formula for it (D-62-14), and the refusal-before-start wiring (D-62-13) — all ready for 62-05, which wires the actual sitting's company batch and chosen per-company cap into these two functions.
- `figures["suggestion_allowance"]["priced_cap"]` is the number 62-05's sitting must compare an operator-chosen cap against and refuse anything higher (named explicitly in the plan's own read_first for that future step).
- No blockers. Suites at close: `operator-claude-plugin` 2228 passed / 5 skipped (>= 2182 baseline from this plan's own `<verification>` block); `node --test tests/n8n/*.test.mjs` 862 pass / 0 fail (unaffected — this plan touches `operator-claude-plugin/` only).

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-02*

## Self-Check: PASSED
- FOUND: operator-claude-plugin/scripts/cost_guard.py
- FOUND: operator-claude-plugin/scripts/write_grant.py
- FOUND: operator-claude-plugin/config/cost_rates.json
- FOUND: operator-claude-plugin/tests/test_cost_guard_suggestion.py
- FOUND: operator-claude-plugin/tests/test_write_grant_suggestion.py
- FOUND commits bd05a9a, 40f1c3e, 466f99a, 8ad3e73 (all present in `git log --oneline --all`)
- Re-ran `.venv/bin/python -m pytest operator-claude-plugin/tests -q`: 2228 passed, 5 skipped (>= 2182 baseline, 0 failed)
- Re-ran `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_suggestion.py operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_surface.py -q`: 213 passed, 0 failed
- Re-ran `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -q` with the file unmodified: 183 passed
- Re-ran `node --test tests/n8n/*.test.mjs`: 862 pass, 0 fail
- Re-ran the `null-ok` acceptance criterion and the `MAX_FOLLOWUP_FETCHES` import grep: both pass
