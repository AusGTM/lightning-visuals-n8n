---
phase: 36-enrichment-propose-mode
plan: 01
subsystem: infra
tags: [n8n, hubspot, code-node, tdd, workflow-builder]

# Dependency graph
requires:
  - phase: 35-empty-page-structured-fallback
    provides: plugin 0.10.0 on master, disarmed backend, UAT-verified enrichment lane
provides:
  - "n8n/code/matchProposal.js: laneOf, mediumCandidates, summarizeMatch — pure, tested, no n8n globals"
  - "lane field stamped once per enrichment row by Build Identity"
  - "Adapt Search / Adapt Fetch By Id filtered to their own lane before index-aligning"
  - "HubSpot Search by Email ingest filter falls back to an RFC 2606 .invalid sentinel"
affects: [36-02-match-lane-nodes, 36-03-propose-mode-dispatch, 36-04-response-shape, 37-client-chunking]

# Actuals (#2632)
actuals:
  tokens: 22895
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Pure-module value re-verification: mediumCandidates never trusts a HubSpot CONTAINS_TOKEN server-side filter — it re-checks lastname (case-insensitive) and company (token overlap) by value before reporting a candidate"
    - "Single lane predicate: laneOf is the one place fetch_by_id/email/name/none is decided; both adapters filter to their own lane before index-aligning against their own HTTP node's output array"

key-files:
  created:
    - n8n/code/matchProposal.js
    - tests/n8n/matchProposal.test.mjs
    - tests/test_enrichment_lane_dedup.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_contact_ingest_cloud.json
    - tests/test_ingest_search_contract.py

key-decisions:
  - "laneOf's fetch_by_id branch mirrors IF Bare Event's boolean expression exactly (object_id truthy AND identity_keys.email falsy) rather than deriving a new predicate, so routing and lane-filtering provably cannot disagree"
  - "mediumCandidates re-verifies by value (case-insensitive lastname equality AND company token overlap); a fuzzy CONTAINS_TOKEN hit that fails re-verification yields zero candidates rather than a low-confidence match"
  - "summarizeMatch keeps unknown (search failed or never ran) and none (search ran, no hit) as distinct tiers per 36-CONTEXT.md sec 6 — auto is true for exactly one tier, high"
  - "Ingest sentinel fix leaves the batch-wide lookup_failed scope in ADAPT_SEARCH_RESULTS unchanged (out of scope per 36-CONTEXT.md sec 5B) — only amended its comment to record the scope is now deliberate"

patterns-established:
  - "Extend inline()'d module with more exports without touching the wrapper: adding mediumCandidates/summarizeMatch to matchProposal.js's exports required zero changes to ENRICH_BUILD_IDENTITY's wrapper, since inline() pulls the whole stripped module body"

requirements-completed: [STRUCT-02, STRUCT-04, DISPATCH-02]

coverage:
  - id: D1
    description: "laneOf stamps exactly one lane value per row, mirroring IF Bare Event's predicate for the fetch_by_id branch"
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "node --test tests/n8n/matchProposal.test.mjs (laneOf cases)"
        status: pass
      - kind: integration
        ref: "tests/test_enrichment_lane_dedup.py::test_build_identity_stamps_lane_via_laneof"
        status: pass
    human_judgment: false
  - id: D2
    description: "Adapt Search and Adapt Fetch By Id filter to their own lane before index-aligning, closing the mixed-lane duplication bug"
    requirement: STRUCT-02
    verification:
      - kind: integration
        ref: "tests/test_enrichment_lane_dedup.py (4 tests: lane stamp, email filter x cloud+local-live, fetch_by_id filter)"
        status: pass
    human_judgment: false
  - id: D3
    description: "mediumCandidates re-verifies a CONTAINS_TOKEN hit by value; wrong surname or wrong company yields zero candidates, never a guessed match"
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "node --test tests/n8n/matchProposal.test.mjs (mediumCandidates cases)"
        status: pass
    human_judgment: false
  - id: D4
    description: "summarizeMatch distinguishes unknown (search failed/never ran) from none (search ran, no hit); auto true only for high"
    requirement: STRUCT-04
    verification:
      - kind: unit
        ref: "node --test tests/n8n/matchProposal.test.mjs (summarizeMatch cases)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Ingest lane's HubSpot Search by Email filter falls back to an .invalid sentinel for an emailless row, so lookup_failed is never manufactured by a legitimate row"
    requirement: DISPATCH-02
    verification:
      - kind: integration
        ref: "tests/test_ingest_search_contract.py::test_search_by_email_filter_falls_back_to_an_invalid_sentinel_for_an_emailless_row"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-05
status: complete
---

# Phase 36 Plan 01: Lane Stamp, Value Re-Verification, Ingest Sentinel Summary

**laneOf/mediumCandidates/summarizeMatch land as a pure tested module; both enrichment adapters now filter to their own lane before index-aligning; an emailless ingest row can no longer fail its whole upload.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3/3 completed
- **Files modified:** 9 (1 new module, 2 new test files, 6 existing files touched)

## Accomplishments

- `n8n/code/matchProposal.js` created: `laneOf`, `mediumCandidates`, `summarizeMatch` — pure, no n8n globals, 32/32 tests passing.
- Finding A (mixed-lane duplication) closed: `Build Identity` stamps `lane` once per row; `Adapt Search` and `Adapt Fetch By Id` each filter `$('Build Identity').all()` to their own lane before index-aligning against their own HTTP node's output array. Fixed in the shared `ENRICH_ADAPT_SEARCH`/`ENRICH_ADAPT_FETCH_BY_ID_CONTACT` constants, so both `wf_enrichment_cloud.json` and `wf_enrichment_local_live.json` carry the fix.
- Finding B (ingest lane manufacturing its own batch-wide failure) closed: `HubSpot Search by Email`'s filter value gained an RFC 2606 `.invalid` sentinel fallback, so an emailless row's search returns 200/zero-hits instead of a rejected filter that stamped `lookup_failed` on the whole batch.
- Every new assertion red-checked individually (revert the specific builder edit, confirm the specific assertion fails, restore) — details in Deviations/Issues below.

## Task Commits

Each task was committed atomically:

1. **Task 1: laneOf end-to-end** — `2b38677` (test), `55bf660` (feat: laneOf), `cd99f14` (feat: lane stamp + adapter filters)
2. **Task 2: mediumCandidates + summarizeMatch** — `ff7c1c4` (test), `21adfe5` (feat)
3. **Task 3: ingest sentinel** — `d9b6b2e` (fix)

_TDD tasks (1 and 2) each produced a RED test-only commit followed by a GREEN implementation commit, per this repo's tdd_execution convention._

## Files Created/Modified

- `n8n/code/matchProposal.js` — new pure module: `laneOf`, `mediumCandidates`, `summarizeMatch`
- `tests/n8n/matchProposal.test.mjs` — new, 32 tests
- `tests/test_enrichment_lane_dedup.py` — new, 4 structural tests over the built `n8n/wf_enrichment_cloud.json`/`wf_enrichment_local_live.json`
- `scripts/build_cloud_workflows.py` — `ENRICH_BUILD_IDENTITY` stamps `lane`; `ENRICH_ADAPT_SEARCH`/`ENRICH_ADAPT_FETCH_BY_ID_CONTACT` filter to their lane; `HubSpot Search by Email`'s filter value gained the `.invalid` sentinel; `ADAPT_SEARCH_RESULTS`'s comment amended to record the batch-wide scope is now deliberate
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json` — regenerated via the builder (never hand-edited)
- `n8n/wf_contact_ingest_cloud.json` — regenerated via the builder
- `tests/test_ingest_search_contract.py` — extended with the sentinel assertion, existing pinned assertions untouched

## Decisions Made

- `laneOf`'s `fetch_by_id` branch is a literal mirror of `IF Bare Event`'s boolean expression rather than an independently-derived predicate — the plan's `key_links` explicitly calls out drift risk here, so the module comment quotes the n8n expression verbatim as documentation.
- `mediumCandidates` projects a kept hit to exactly six named keys (`hs_object_id`, `firstname`, `lastname`, `email`, `jobtitle`, `company`) — never the full HubSpot properties object — closing T-36-04 (information disclosure) from the plan's threat register.
- Left `ADAPT_SEARCH_RESULTS`'s batch-wide `lookup_failed` scope unchanged per 36-CONTEXT.md §5B's explicit "out of scope" — only its comment was amended to record why the scope is now correct rather than accidental.

## Deviations from Plan

None — plan executed exactly as written. One clarification worth recording: Task 2's `<files>` list did not include any `n8n/*.json` (correctly — `mediumCandidates`/`summarizeMatch` aren't wired into any wrapper yet), so those functions rode along as inert additions to the `Build Identity` Code node body the next time the builder ran (Task 3's regeneration), since `inline()` pulls a module's entire stripped body regardless of which exports the wrapper actually calls. This is expected `inline()` behavior, not a bug — flagging it here so a future reader isn't surprised that Task 3's `n8n/*.json` diff includes more than the ingest-lane change its own task text describes.

## Issues Encountered

None blocking. One self-correction: my first heredoc-based `git commit` invocations failed on bash heredoc syntax (apostrophes inside a `'EOF'`-quoted heredoc passed through `$(cat <<'EOF' ... EOF)` inside a double-quoted `-m` argument) — switched to plain multi-line `-m` strings for the remainder of the plan, which worked without incident.

## User Setup Required

None — no external service configuration required. This plan makes zero live/deploy changes; `scripts/deploy_n8n_workflows.py` was not run (denied to agents per this phase's constraints, and this plan's own `<verification>` block is entirely offline/structural).

## Next Phase Readiness

- `lane` is available on every enrichment row for plan 36-02's match-lane nodes (`IF Has Email`, `IF Name Searchable`, `HubSpot Name Search`, `Adapt Name Search`) to route on and stamp `match` alongside.
- `mediumCandidates`/`summarizeMatch` are implemented and tested but not yet wired into any Code node — 36-02 is expected to call them from a new `Adapt Name Search`/gate wrapper.
- Verification suites green against baselines: `.venv/bin/python -m pytest -q` → 1938 passed / 6 skipped (baseline 1933/6, +5 new: 4 lane-dedup + 1 ingest sentinel). `node --test tests/n8n/*.test.mjs` → 585 passing (baseline 553, +32 matchProposal). `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0 for every file. No blockers for 36-02.

---
*Phase: 36-enrichment-propose-mode*
*Completed: 2026-08-05*
