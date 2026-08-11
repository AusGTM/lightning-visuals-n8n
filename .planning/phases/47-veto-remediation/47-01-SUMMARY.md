---
phase: 47-veto-remediation
plan: 01
subsystem: crm-scoring
tags: [hubspot, icp-scoring, python, pytest, n8n-webhook, web-research]

# Dependency graph
requires:
  - phase: 46-rubric-decision-simulation-engine-parity
    provides: "The settled rubric (config/icp_scoring.yaml), compute_icp_score's cfg=None override, and the 46-SIMULATION-REPORT.md row set the 17 pinned ids are enumerated from."
provides:
  - "scripts/remediate_veto_companies.py -- the single script carrying all four write legs (web research, input+metadata PATCH, component-score PATCH, D-18 webhook POST) for the 17 pinned false-veto companies, fully offline-verified and disarmed by default."
  - "settle_and_assert/settle_tier/settle_veto -- the D-10 'fail loudly' settle wrapper the repo did not have (neither _settle() nor scoring_fixtures.settle() asserts a value, only stability)."
  - "estimate_cost/refuse_if_over_budget -- D-03 static cost projection and refuse-not-truncate budget gate."
  - "verify_post_run -- D-20 clobber detector for the n8n re-research lane re-entering evidence-gated records inside the same armed window."
affects: [47-02-veto-remediation-arming, 47-03-veto-remediation, 47-04-veto-remediation]

actuals:
  tokens: 12413
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Two-key arm (DRY_RUN=false + ALLOW_VETO_REMEDIATION=true), portal-id pin, dry-run-by-default print-exact-payload -- mirrors scripts/backfill_seed_company_scores.py exactly."
    - "Injectable reader/sleeper on every settle function so offline tests control both fake data and fake elapsed time (via a monkeypatched time.monotonic) without ever calling time.sleep."
    - "Strict per-field evidence_by_field gating for build_input_patch (no fallback), vs. a fallback-to-general-evidence_urls rule for build_metadata_patch's stamp -- two different rules for two different purposes (gate vs. stamp), both explicit in the plan text."

key-files:
  created:
    - scripts/remediate_veto_companies.py
    - tests/test_remediate_veto_companies.py
  modified:
    - tests/fixtures/claude_web_research_company.json

key-decisions:
  - "Added evidence_by_field to the shared claude_web_research_company.json mock fixture (Rule 2): the fixture predated the Phase 13/OC-1 evidence_by_field addition and was stale against its own RESEARCH_SYSTEM contract and src/taxonomy.py's existing evidence-gate precedent. Verified no other test asserts its exact shape before editing."
  - "build_input_patch's evidence check is strict evidence_by_field-only (no fallback to the general evidence.evidence_urls list) for both lv_org_type and lv_produces_content, matching src/taxonomy.py's existing produces_content gate precedent. build_metadata_patch's evidence_url STAMP (for fields already cleared to write) uses a fallback to the first general evidence URL, so lv_country_region_normalized -- which is never evidence-gated -- still gets a useful metadata pointer."
  - "settle_tier/settle_veto expose injectable reader/sleeper kwargs beyond what the plan's terse function-signature text listed, mirroring settle_and_assert's own design -- required for settle_veto's offline test (a fake reader must answer both the polled lv_anti_icp_flag prop and the secondary lv_anti_icp_reason lookup its predicate makes)."
  - "estimate_cost/refuse_if_over_budget take the id list itself (not a bare count) so redundant_research_calls can be computed from actual pinned-id membership in the ~4 known-likely-evidence-gated ids (D-20), and so refuse_if_over_budget can return the id list unmodified per its own acceptance criterion."
  - "Confirmed via gsd-tools requirements ready-ids that all four of this plan's frontmatter requirement IDs (VETO-01, VETO-02, COVER-01, COVER-02) are BLOCKED, not ready to mark complete -- sibling plans 02/03/04 also declare them and none has produced a SUMMARY.md yet. requirements mark-complete was correctly skipped this run; a later plan's SUMMARY will mark them once all declaring plans are done."

patterns-established:
  - "Settle wrapper pattern: settle_and_assert(company_id, prop, expected, timeout, interval, reader, sleeper) as the reusable D-10 primitive; settle_tier/settle_veto are thin, differently-timed callers over the same primitive, never sharing one poll loop."
  - "D-20 clobber-verify-inside-the-armed-window: re-check written fields immediately after the derived chain settles, re-stamp once if diverged, raise if it diverges again -- never defer verification to a second ceremony."

requirements-completed: []

coverage:
  - id: D1
    description: "One pinned company runs the full disarmed path (research, input PATCH, metadata PATCH, component PATCH, webhook event body) with all four payloads printed and zero network calls."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_tracer_single_pinned_company_disarmed_prints_all_payloads_no_network"
        status: pass
    human_judgment: false
  - id: D2
    description: "resolve_pinned_ids refuses any id outside the 17 pinned ids, including all 3 structurally-excluded ids (Entain, Gravity Media, Ironman), before any HubSpot or n8n call."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_resolve_pinned_ids_refuses_excluded_ids"
        status: pass
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_resolve_pinned_ids_refuses_arbitrary_unpinned_id"
        status: pass
    human_judgment: false
  - id: D3
    description: "No payload any builder produces ever contains a derived field (lv_icp_fit_score/lv_icp_tier/lv_anti_icp_flag/lv_anti_icp_reason), across 4+ distinct ProviderResult fixture shapes."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_never_writes_a_forbidden_derived_field_key_across_fixtures"
        status: pass
      - kind: unit
        ref: "pytest -k never_write"
        status: pass
    human_judgment: false
  - id: D4
    description: "lv_produces_content is never written false on absent evidence -- it is omitted with a stated unresolved reason instead (D-14)."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_produces_content_false_without_evidence_is_omitted_with_a_reason"
        status: pass
    human_judgment: false
  - id: D5
    description: "The record cap accepts 17 at the default, refuses below 17, clamps above 17 down to 17, and falls back to 17 on a non-integer VETO_MAX_RECORDS."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_enforce_sample_cap_all_17_true_at_default"
        status: pass
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_resolved_max_records_clamps_above_17_and_falls_back_on_non_integer"
        status: pass
    human_judgment: false
  - id: D6
    description: "Two independent settle mechanisms (settle_tier 120s/5s, settle_veto 900s/15s) both raise SettleFailed on a stable-but-wrong value as well as on timeout; settle_veto tolerates a legitimate non-non-ANZ veto surfacing (D-16)."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_settle_and_assert_raises_settle_failed_when_stable_but_wrong_value"
        status: pass
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_settle_veto_passes_when_flag_true_for_a_genuine_non_non_anz_veto"
        status: pass
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_settle_veto_fails_when_flag_true_still_carries_the_non_anz_reason"
        status: pass
    human_judgment: false
  - id: D7
    description: "The two-key arm gate (DRY_RUN=false AND ALLOW_VETO_REMEDIATION=true) refuses writes for every combination except both keys set; an empty-allowlist / package-install concern does not apply here (no new dependency installed)."
    requirement: "VETO-02"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_writes_allowed_false_for_every_non_both_keys_combo"
        status: pass
    human_judgment: false
  - id: D8
    description: "estimate_cost/refuse_if_over_budget: cost is projected before any research call and the run refuses (never truncates) when projected n8n executions exceed the monthly budget."
    requirement: "COVER-02"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_estimate_cost_reports_expected_keys_for_all_17"
        status: pass
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_refuse_if_over_budget_raises_above_budget_and_never_truncates_when_ok"
        status: pass
    human_judgment: false
  - id: D9
    description: "verify_post_run detects a field that diverged from what this script wrote (D-20 clobber check), so main()'s armed loop can re-stamp once and raise if it diverges again."
    requirement: "COVER-01"
    verification:
      - kind: unit
        ref: "tests/test_remediate_veto_companies.py::test_verify_post_run_detects_a_lost_metadata_stamp"
        status: pass
    human_judgment: false
  - id: D10
    description: "The live wiring of arming/dispatch/disarm ceremonies against production HubSpot and n8n, and the actual clearing of the 17 companies' vetoes, is NOT part of this plan -- it is a subsequent plan's job (this plan only builds and offline-verifies the tool)."
    verification: []
    human_judgment: true
    rationale: "Genuinely outside this plan's scope -- Plan 01's own must_haves and success_criteria are explicitly offline/dry-run only. Confirmed via gsd-tools requirements ready-ids that VETO-01/02/COVER-01/02 remain BLOCKED pending sibling plans 02-04."

duration: 20min
completed: 2026-08-11
status: complete
---

# Phase 47 Plan 01: Veto Remediation Script Summary

**Built and offline-verified `scripts/remediate_veto_companies.py` -- the single script carrying all four write legs (Claude web research, input+metadata PATCH, component-score PATCH, D-18 n8n webhook POST) needed to clear the false non-ANZ veto on 17 pinned HubSpot companies, disarmed by default and proven never to write a derived scoring field.**

## Performance

- **Duration:** ~20min
- **Tasks:** 3 completed
- **Files modified:** 3 (2 created, 1 fixture edited)
- **Commits:** 5 (1 tracer + 2 TDD RED/GREEN pairs)

## Accomplishments

- One pinned company runs the whole remediation path end-to-end (research -> build the three payload patches -> print the webhook event body) with zero network calls in the disarmed default, proven by a tracer test that monkeypatches `requests.get`/`requests.post` to raise.
- `resolve_pinned_ids` refuses any company id outside the literal 17 pinned ids -- including all 3 structurally-excluded ids (Entain, Gravity Media, Ironman) -- before any HubSpot or n8n call is ever made.
- Two independent settle mechanisms (`settle_tier` for the pure-HubSpot `lv_icp_tier` chain, `settle_veto` for the n8n-dependent `lv_anti_icp_flag` chain) both raise `SettleFailed` on a stable-but-wrong final value as well as on timeout -- closing the gap neither existing `_settle()`/`settle()` helper in this repo closes (they only detect "stopped changing", never assert a value).
- `estimate_cost`/`refuse_if_over_budget` project research/n8n-execution cost before any call and refuse (never truncate) a run that would exceed the 2,500/month n8n budget.
- `verify_post_run` catches the D-20 clobber risk (the deployed Research Trigger Gate re-entering ~4 evidence-gated pinned records) and `main()`'s armed loop re-stamps once, inside the same armed window, raising rather than continuing silently if it diverges again.
- 28 new offline tests, all green, zero network calls anywhere in the suite; the full repo test suite (1223 passed, 123 skipped) and the `-k never_write` selector (5 collected across 2 files) both stay green.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "remediate one pinned company" — one path only** - `e558a1c` (feat)
2. **Task 2: Settle-and-assert wrappers** - `c7c9a54` (test, RED) then `a593d77` (feat, GREEN)
3. **Task 3: Guard suite — pin, cap, never-write, budget refusal, D-20 clobber verify, full 17-record loop** - `c7dd765` (test, RED) then `a3dea20` (feat, GREEN)

_Task 2 and Task 3 were both `tdd="true"` -- each shows a failing-tests commit before the implementation that makes them pass._

## Files Created/Modified

- `scripts/remediate_veto_companies.py` - the single script: pin/cap/arm guards, research delegation, three payload builders (input, metadata, component), the D-18 webhook event builder + poster, two settle wrappers, cost estimate + budget refusal, D-20 clobber verify, and `main()` wiring all of it into one disarmed-by-default, per-record armed sequence.
- `tests/test_remediate_veto_companies.py` - 28 offline tests: 1 tracer, 7 settle, 20 guard-suite (pin/cap/never-write/budget/clobber-verify).
- `tests/fixtures/claude_web_research_company.json` - added `evidence_by_field` (Rule 2 fix, see Decisions Made).

## Decisions Made

- **Added `evidence_by_field` to the shared mock research fixture (Rule 2).** The fixture predated the Phase 13/OC-1 `evidence_by_field` addition to `ProviderResult` and had drifted stale against `src/web_research.py`'s own `RESEARCH_SYSTEM` prompt contract (which instructs the model to cite a per-field evidence URL for every field it sets) and against `src/taxonomy.py`'s existing `produces_content` evidence gate, which already reads `evidence_by_field` directly. Verified `tests/test_scaffold.py` (the fixture's only other consumer) only checks the file loads as JSON, not its exact key set, before editing. Without this fix the tracer test's mock research result would never clear the evidence gate for `lv_org_type`/`lv_produces_content`, silently degrading the tracer to an empty-patch path and hiding a real bug behind a stale fixture.
- **`build_input_patch`'s evidence check is strict `evidence_by_field`-only, with no fallback** to the general `evidence.evidence_urls` list -- for both `lv_org_type` (when evidence-required) and `lv_produces_content` (always). This mirrors `src/taxonomy.py`'s existing precedent (`if produces_content is False and not evidence_by_field.get("lv_produces_content")`) exactly. `build_metadata_patch`'s evidence-URL *stamp*, in contrast, falls back to the first general evidence URL -- because `lv_country_region_normalized` is never evidence-gated at all, and a field that's already been cleared to write still deserves a useful metadata pointer even with no per-field citation.
- **`settle_tier`/`settle_veto` carry injectable `reader`/`sleeper` keyword arguments** beyond the plan's terse function-signature prose, mirroring `settle_and_assert`'s own design. This was necessary, not optional embellishment: `settle_veto`'s D-16 predicate makes a *second* read (of `lv_anti_icp_reason`) beyond the prop it polls, and an offline test cannot control that second read without the same fake reader being threaded through.
- **`estimate_cost`/`refuse_if_over_budget` operate on the id list itself**, not a bare integer count, so `redundant_research_calls` can be computed from actual membership in the ~4 D-20-documented likely-evidence-gated pinned ids, and so `refuse_if_over_budget` can literally return the id list unmodified (its own acceptance criterion) rather than a derived count.
- **Skipped `requirements mark-complete` for VETO-01/VETO-02/COVER-01/COVER-02.** Ran `gsd-tools query requirements.ready-ids` against this plan's frontmatter requirement IDs before marking anything; all four came back `blocked` because sibling plans 47-02/47-03/47-04 also declare them and none has produced a `SUMMARY.md` yet. Marking them complete now would have been factually wrong -- nothing live has happened yet, this plan is offline/dry-run only by design. A later plan's completion will mark them once every declaring plan is done.

## Deviations from Plan

None — plan executed exactly as written. The two additive design choices above (`evidence_by_field` fixture fix, injectable `reader`/`sleeper` on `settle_tier`/`settle_veto`) are within the plan's own stated discretion ("the polling interval and timeout for `_settle`" is Claude's discretion per 47-CONTEXT.md, and the plan's own text for `settle_veto` already requires a secondary `lv_anti_icp_reason` read that has no offline story without an injectable reader) and were necessary for the acceptance criteria to be genuinely testable, not scope creep.

## Issues Encountered

None. The one design ambiguity worth recording for future plans in this phase: `build_input_patch`'s two evidence-gating sentences in the plan text ("evidence URL... in `result.evidence_by_field`" for `lv_produces_content` vs. the looser "an evidence URL is present for it" for `lv_org_type`) were resolved to the SAME strict rule for both fields, on the strength of `src/taxonomy.py`'s existing precedent. If a later plan in this phase (or a live run) surfaces a case where `lv_org_type` genuinely has a general `evidence.evidence_urls` entry but no `evidence_by_field["lv_org_type"]` citation, that record will correctly land in `unresolved_reasons` rather than being written -- this is the conservative direction per D-14's "prefer unknown over guessing."

## User Setup Required

None. This plan performs no live writes and requires no external service configuration -- `DRY_RUN` defaults true, `USE_MOCK_WEB_RESEARCH` is forced true in every test, and the operator-only arming env vars (`DRY_RUN=false`, `ALLOW_VETO_REMEDIATION=true`) are never set by this plan or its tests.

## Next Phase Readiness

`scripts/remediate_veto_companies.py` and its offline suite are ready for the arming/dispatch plans (47-02/47-03/47-04) to build on. Nothing in this plan performed a live HubSpot or n8n write. `scripts/run_scoring_parity.py`'s population sweep remains red by design (Phase 46 commit `caae5d6`, closed by Phase 49) and was not touched.

---
*Phase: 47-veto-remediation*
*Completed: 2026-08-11*

## Self-Check: PASSED

- FOUND: `scripts/remediate_veto_companies.py`
- FOUND: `tests/test_remediate_veto_companies.py`
- FOUND: `.planning/phases/47-veto-remediation/47-01-SUMMARY.md`
- FOUND commits: `e558a1c`, `c7c9a54`, `a593d77`, `c7dd765`, `a3dea20`
