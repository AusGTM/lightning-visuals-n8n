---
phase: 43-pipeline-scoring-hygiene-explainability
plan: 02
subsystem: scoring-explainability
tags: [python, hubspot, icp-scoring, parity-harness, json-serialization]

requires:
  - phase: 40-scoring-engine-remediation-notes
    provides: "the read-only scheduled parity harness (scripts/run_scoring_parity.py, tests/scoring_fixtures.py) this plan extends, plus D-12's read-only-scheduled-sweep guarantee this plan is required to preserve"
provides:
  - "serialize_breakdown(result) -- the first producer of lv_icp_score_breakdown"
  - "--write-breakdown, the first custom CLI flag scripts/run_scoring_parity.py has ever had, strictly opt-in and read-only by default"
affects: [43-04-plan-scoring-consolidation, phase-40-scoring-parity]

actuals:
  tokens: 4830
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Shed-detail-before-bytes JSON truncation: strip the least-essential fields first, dump, check length, repeat; only ever return an assembled json.dumps() string, never a slice of one."
    - "Injectable write_fn parameter (mirrors the existing fetch_fn injection) so a write path can be proven inert offline via a stub that raises if called."

key-files:
  created: []
  modified:
    - scripts/run_scoring_parity.py
    - tests/test_scoring_parity.py

key-decisions:
  - "Shed order: (1) drop each component's `value`, keep signal+points; (2) bound each hard_veto reason string's length; (3) pathological fallback to counts-only. A real breakdown (417 bytes measured) never reaches step 1."
  - "write_fn defaults to patch_record (module-level import), mirroring fetch_fn's existing default -- the docstring's read-only guarantee now rests on write_breakdown's False default and the D-12 sweep never passing the flag, not on the absence of a patch_record import."
  - "breakdowns_written is recorded on the report dict and appended to the verdict string only when --write-breakdown was passed, so a read-only run's verdict text is byte-identical to before this plan."

requirements-completed: [PIPE-03]

coverage:
  - id: D1
    description: "serialize_breakdown(result) adds the score total (absent from the source breakdown dict), sheds per-component detail before bytes when over the 60k HubSpot property limit, then bounds hard-veto strings, then falls back to counts-only -- always valid JSON, never a byte slice."
    requirement: "PIPE-03"
    verification:
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_serialize_breakdown_round_trips_a_real_result"
        status: pass
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_serialize_breakdown_sheds_component_detail_before_bytes"
        status: pass
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_serialize_breakdown_falls_back_to_counts_when_shedding_detail_is_not_enough"
        status: pass
    human_judgment: false
  - id: D2
    description: "--write-breakdown is off by default (no write call reachable without it, proven by a raising stub), and when passed writes lv_icp_score_breakdown once per successfully-compared company, skipping any company whose fetch raised."
    requirement: "PIPE-03"
    verification:
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_write_breakdown_default_off_never_calls_write_fn"
        status: pass
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_write_breakdown_flag_writes_once_per_compared_company"
        status: pass
      - kind: unit
        ref: "tests/test_scoring_parity.py::test_write_breakdown_skips_a_company_whose_fetch_raised"
        status: pass
    human_judgment: false
  - id: D3
    description: "Live round-trip: --write-breakdown against a real disposable HubSpot company, reading the property back and confirming it parses and its total matches the oracle."
    verification:
      - kind: integration
        ref: "tests/test_scoring_parity.py::test_write_breakdown_live_round_trips_through_hubspot (RUN_LIVE_PARITY=true, skipped this session -- .env is Read/Bash permission-blocked)"
        status: unknown
    human_judgment: true
    rationale: "Authored here per the plan's explicit instruction ('Authored here, executed by the operator in 43-04') -- this session has no HubSpot credentials to run it. 43-04 is the designated execution point."

duration: 25min
completed: 2026-08-07
status: complete
---

# Phase 43 Plan 02: Pipeline Scoring Hygiene & Explainability Summary

**First producer for `lv_icp_score_breakdown`: an opt-in `--write-breakdown` mode on the Phase 40 parity harness that serializes `compute_icp_score`'s breakdown with a shed-detail-before-bytes truncation contract, adding the score total the breakdown dict itself never carried.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-07T08:05:00Z (approx, session start)
- **Completed:** 2026-08-07T08:30:46Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `serialize_breakdown(result)` in `scripts/run_scoring_parity.py`: adds the `total` (C4 -- lives only on the sibling `ICPScoreResult.score`, never inside the `breakdown` dict), sheds per-component `value` detail first, then bounds hard-veto reason strings, then falls back to counts-only if still oversized -- always valid JSON, always within `BREAKDOWN_PROPERTY_LIMIT` (60000), never a byte slice.
- `--write-breakdown`, the first custom CLI flag this script has ever had, threaded through `build_report(sample_ids, fetch_fn=..., write_breakdown=False, write_fn=patch_record)`. Off by default; the standing unattended sweep (Phase 40 D-12) never passes it and therefore never writes -- proven by a guard test whose write stub raises if called.
- Coverage confined to exactly the companies the invocation successfully compared (D-03): a company whose fetch raised gets no write, no portfolio backfill exists.
- Module docstring amended: the now-false unconditional "never creates, patches, or deletes" claim is replaced with an accurate description of the flag-gated write path and where the read-only guarantee actually lives (the flag's False default + D-12 never passing it).

## Task Commits

Each task was committed atomically:

1. **Task 1: Breakdown serializer** - `a1230d4` (feat) -- `serialize_breakdown`, `BREAKDOWN_PROPERTY_LIMIT`, three offline tests (round-trip, synthetic-oversized shedding, pathological fallback).
2. **Task 2: Wire --write-breakdown** - `859bb6a` (feat) -- CLI flag, `build_report` wiring, `breakdowns_written` report field, docstring amendment, three offline tests + one live-gated round-trip test.

_Note: Task 2's commit landed under hash `859bb6a` rather than immediately after Task 1's staging, due to a shared-index collision with a concurrently-running sibling executor (43-03) on the same checkout -- see Issues Encountered below. Content and file scope are exactly as planned; no files outside `scripts/run_scoring_parity.py` / `tests/test_scoring_parity.py` are in either commit._

## Files Created/Modified
- `scripts/run_scoring_parity.py` - `serialize_breakdown`, `BREAKDOWN_PROPERTY_LIMIT`, `_HARD_VETO_REASON_MAX_LEN`, `--write-breakdown` flag, `build_report`'s `write_breakdown`/`write_fn` params + write branch + `breakdowns_written` report field, amended module docstring.
- `tests/test_scoring_parity.py` - 6 new offline tests (serializer round-trip, synthetic-oversized shedding, pathological fallback, write-off guard, write-on per-company count, skip-on-fetch-failure) + 1 live-gated round-trip test.

## Decisions Made
- Shed order implemented exactly as D-02 specifies: drop component `value` -> bound hard-veto strings -> counts-only fallback. A real breakdown measured at 417 bytes (governing_body_league + gambling deduction, the densest realistic case) confirms shedding never fires naturally, matching fact 3 in the plan.
- The docstring sentence that replaced the unconditional read-only claim: *"Read-only by default. GET and search calls only, UNLESS the operator explicitly passes --write-breakdown (Phase 43 Plan 02, D-01), which patches exactly one property (lv_icp_score_breakdown) on each company this invocation successfully compared -- no create-record or delete-record call exists anywhere in this file, live or otherwise, so even the flagged path cannot create or destroy a record. Phase 40 D-12's scheduled unattended pass never passes --write-breakdown and therefore never writes; that guarantee, not the absence of a patch import, is what keeps the standing sweep safe to run unattended on a cadence."*

## Deviations from Plan

None - plan executed exactly as written. `serialize_breakdown` uses the exact name pinned by the acceptance criteria; the shed order, truncation marker, and injectable `write_fn` all match the plan's contract verbatim.

## Issues Encountered

**Shared-index commit collision with a concurrent sibling executor.** This wave runs 43-02, 43-03, and 42-01 concurrently against the same working tree (not isolated git worktrees). After staging Task 2's changes with `git add`, a concurrently-running 43-03 executor ran a bare `git commit` (no pathspec) that swept my already-staged `scripts/run_scoring_parity.py` / `tests/test_scoring_parity.py` changes into its own commit message. That sibling process subsequently amended/re-committed its own work to exclude my files (visible as a HEAD rewrite from `00e95c5` to `7435d0f` mid-session), which correctly restored my Task 2 changes to the working tree as uncommitted modifications. I then re-committed them under an accurate `43-02` message using a pathspec-limited `git commit -F <file> -- <paths>` (never a bare `git commit`) to guard against a repeat collision. No content was lost; final `git show --stat` on both my commits (`a1230d4`, `859bb6a`) confirms each touches only my two files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `serialize_breakdown` and `--write-breakdown` are ready for the operator to exercise live in 43-04, where `test_write_breakdown_live_round_trips_through_hubspot` (authored here, gated on `RUN_LIVE_PARITY=true`) should be run to confirm the property round-trips correctly against the real portal.
- Full offline suite: `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` -> 45 passed, 34 skipped. Full repo suite: `.venv/bin/python -m pytest -q` -> 2390 passed, 120 skipped (above the 2362-passed baseline; the +28 relative to my own +7 new tests reflects sibling waves' concurrent additions in the same session). `node --test tests/n8n/*.test.mjs` -> 636 passed, 0 failed (untouched, as expected -- this plan touches no n8n files).
- Two unrelated failures observed in `operator-claude-plugin/tests/` (`test_plugin_manifest.py`, `test_report_enrichment.py`, both referencing `loss-reason-report`) belong to a concurrent sibling's in-progress plugin skill (43-04/D-06 surface, `operator-claude-plugin/skills/loss-reason-report/`, untracked at time of writing) -- outside this plan's file scope (`scripts/run_scoring_parity.py`, `tests/test_scoring_parity.py` only) and not investigated or touched here.

## Self-Check: PASSED

- FOUND: `scripts/run_scoring_parity.py`
- FOUND: `tests/test_scoring_parity.py`
- FOUND: `.planning/phases/43-pipeline-scoring-hygiene-explainability/43-02-SUMMARY.md`
- FOUND commit: `a1230d4` (Task 1)
- FOUND commit: `859bb6a` (Task 2)

---
*Phase: 43-pipeline-scoring-hygiene-explainability*
*Completed: 2026-08-07*
