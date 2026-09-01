---
phase: 62-suggest-the-contacts-nobody-named
plan: 01
subsystem: enrichment
tags: [suggest-contacts, discovery, sitemap-ladder, role-classification, dedupe, python]

requires:
  - phase: 61-06
    provides: contact->company association contract (CLAUDE.md §13.0.1), never duplicated
provides:
  - "suggest_contacts.py: eligibility(), discovery_plan(), select_people(), synthesise_rows(), round_artifact(), company_budget(), next_candidates(), no_candidates(), partition_for_dispatch()"
  - "role_classify.py: classify_title() pure title-to-family matcher"
  - "a company-with-nobody-at-it -> person-read-from-its-own-page -> extraction.validate()-accepted proposal chain, proved offline end to end"
affects: [62-02, 62-03, 62-04, 62-05]

actuals:
  tokens: 6414
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "validate-then-apply discipline for eligibility() (company_domain.apply_domain_decisions precedent)"
    - "readability-before-magnitude tri-state (cost_guard.compare precedent) for the D-62-16 verdict"
    - "library-not-reimplementation: url_fallback.plan_ladder/filter_candidates/give_up_message called verbatim"
    - "name-based dedupe pre-filter, backstopped by the ingest lane's own match (D-62-18)"

key-files:
  created:
    - operator-claude-plugin/scripts/suggest_contacts.py
    - operator-claude-plugin/scripts/role_classify.py
    - operator-claude-plugin/tests/test_suggest_contacts.py
  modified: []

key-decisions:
  - "select_people's dedupe pre-filter runs BEFORE the role filter, so an already-associated person never even reaches role classification"
  - "synthesise_rows only ever copies firstname/lastname/jobtitle/company onto the row — a caller cannot smuggle a stray key (e.g. role_family) through onto the canonical row"
  - "eligibility() coerces a string HubSpot count via int() before comparing to 0, falling to UNKNOWN on anything unparseable rather than guessing"

patterns-established:
  - "Pattern 1: a company row carries an optional just_created flag so a company the batch just created is ELIGIBLE by construction rather than reading a count it cannot have"

requirements-completed: []

coverage:
  - id: D1
    description: "eligibility() returns a tri-state D-62-16 verdict per company (eligible/has_contacts/unknown), branching on readability before magnitude, validate-then-apply over the whole batch"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_eligibility_zero_contacts_is_eligible"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_eligibility_missing_count_is_unknown_never_eligible"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_eligibility_just_created_company_is_eligible_by_construction"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_eligibility_raises_before_returning_any_verdict_on_a_malformed_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "the whole tracer chain — one company with nobody at it, discovered via the sitemap ladder, filtered by role, synthesised into a row, and accepted by extraction.validate() on identity group 2 — runs offline end to end"
    requirement: "SUGGEST-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_tracer_one_company_one_person_one_validated_proposal"
        status: pass
    human_judgment: false
  - id: D3
    description: "the give-up path records url_fallback.give_up_message's own text and the round moves on — no second search-engine fallback; the per-company fetch budget resets between companies"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_no_candidates_records_give_up_messages_own_text"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_company_budget_resets_between_two_companies_in_one_round"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_suggest_contacts_never_falls_through_to_a_second_search_provider"
        status: pass
    human_judgment: false
  - id: D4
    description: "a person already associated with the company is dropped before any per-company-cap spend; an emailless suggestion is held by the existing extraction.hold_emailless gate, no special-casing for suggested rows"
    requirement: "SUGGEST-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_select_people_drops_already_associated_person_with_reason_before_the_cap"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_partition_for_dispatch_is_a_thin_call_to_hold_emailless"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_suggest_contacts.py#test_suggest_contacts_has_no_branch_keyed_on_a_suggestion_origin_flag"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-09-02
status: complete
---

# Phase 62 Plan 01: The suggestion round's engine Summary

**`suggest_contacts.py` + `role_classify.py`: a company with zero associated contacts, discovered via the existing sitemap ladder, role-filtered, deduped against known contacts, and synthesised into a row `extraction.validate()` accepts on identity group 2 — proved end to end in one offline tracer test.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-09-02T00:00:00Z (approx)
- **Completed:** 2026-09-02T00:35:00Z (approx)
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `eligibility(company_rows)`: D-62-16's tri-state verdict (`eligible`/`has_contacts`/`unknown`), validate-then-apply so a malformed row raises before any partial result is emitted, and a company the batch just created is `eligible` by construction.
- `discovery_plan`, `company_budget`, `next_candidates`, `no_candidates`: the sitemap ladder (`url_fallback.plan_ladder`/`filter_candidates`/`give_up_message`) called as a library, never re-implemented, with the per-company fetch budget threaded and reset per company and no second-source fallback on a give-up.
- `select_people`: the role filter (via `role_classify.classify_title`) plus the D-62-18 name-based dedupe pre-filter, run before the per-company cap, with an ambiguous near-match deliberately left for the ingest lane's own match to resolve.
- `synthesise_rows`/`round_artifact`: canonical-prop-only rows (asserted, not just documented) landing through `extraction.py` unmodified — the tracer test proves the whole chain accepts a proposal on identity group 2 with the fetched URL as provenance and zero dropped keys.
- `partition_for_dispatch`: a thin, unmodified call to `extraction.hold_emailless` — a suggested row with no email is held exactly like any CSV row, no suggestion-origin branch anywhere in the module.

## Task Commits

Each task followed RED (failing test) then GREEN (implementation):

1. **Task 1: End-to-end tracer** — `578a008` (test) → `0a0b381` (feat)
2. **Task 2: Give-up path and per-company fetch budget** — `a60fb2b` (test) → `0a75d79` (feat)
3. **Task 3: Dedupe pre-filter and the emailless hold** — `72a92a3` (test) → `0671989` (feat)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `operator-claude-plugin/scripts/suggest_contacts.py` — the suggestion round's engine: eligibility, discovery-plan wiring, per-company fetch budget, role/dedupe filtering, row synthesis, dispatch partition, `__main__` CLI
- `operator-claude-plugin/scripts/role_classify.py` — pure title-to-family classifier, no I/O, family list always a parameter
- `operator-claude-plugin/tests/test_suggest_contacts.py` — 24 tests covering the tracer chain, the give-up path, the dedupe pre-filter, and structural purity guards (no HTTP client, no second search-engine fallback, no suggestion-origin branch)

## Decisions Made
- **Dedupe check runs before the role check** inside `select_people` — matches D-62-18's "the saving is in what is never spent" framing; an already-associated person is dropped without even reaching `role_classify.classify_title`.
- **`synthesise_rows` only ever copies four known keys onto the row** (`company`/`firstname`/`lastname`/`jobtitle`), rather than passing a `person` dict through wholesale — this is what keeps a caller-added key (e.g. `select_people`'s own `role_family` annotation) from ever reaching the canonical-key assert, and is why the assert inside the function is a safety net rather than something a normal call path can trip.
- **`company_budget`/`next_candidates`/`no_candidates` were staged in Task 2, not Task 1** — Task 1's tracer only needed `discovery_plan` (a single `plan_ladder` call); the budget-threading and refusal machinery belongs to the multi-fetch, multi-company round Task 2 actually specifies.

## Deviations from Plan

None - plan executed exactly as written. `select_people`'s signature already included `known_contacts` from Task 1 (per the plan's own Task 1 action block), but the dedupe filtering logic itself was deliberately deferred to Task 3's GREEN commit to keep Task 3's RED phase genuinely red (Task 1 accepted the parameter but did not yet filter on it) rather than pre-satisfying Task 3's own tests.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. This plan introduces no HubSpot credentials, no provider credentials, and no network calls of any kind (verified structurally: no `import requests`, no `urllib.request`, no literal `http` substring anywhere in `suggest_contacts.py`).

## Next Phase Readiness
- `suggest_contacts.py` and `role_classify.py` are ready for 62-02 (role vocabulary, which supplies the `family_list` and `chosen_families` these functions already accept as parameters) and 62-03/62-04/62-05 (pricing, provenance, and the sitting itself).
- No blockers. The row shape (`{"record_type": "contacts", "row": {...}, "provenance": {...}}`) and the `eligibility`/`select_people`/`synthesise_rows`/`round_artifact`/`partition_for_dispatch` seams are the load-bearing contract the rest of Phase 62 hangs off, per this plan's own objective.

---
*Phase: 62-suggest-the-contacts-nobody-named*
*Completed: 2026-09-02*

## Self-Check: PASSED
- FOUND: operator-claude-plugin/scripts/suggest_contacts.py
- FOUND: operator-claude-plugin/scripts/role_classify.py
- FOUND: operator-claude-plugin/tests/test_suggest_contacts.py
- FOUND commit 578a008, 0a0b381, a60fb2b, 0a75d79, 72a92a3, 0671989 (all present in `git log --oneline`)
- Re-ran `.venv/bin/python -m pytest operator-claude-plugin/tests -q`: 2206 passed, 5 skipped (>= 2182 baseline, 0 failed)
- Re-ran `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_contract.py -q`: unchanged, green
- Re-ran the no-while-loop/no-sleep/no-poll AST guard (`test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status`): passed, covering both new files
