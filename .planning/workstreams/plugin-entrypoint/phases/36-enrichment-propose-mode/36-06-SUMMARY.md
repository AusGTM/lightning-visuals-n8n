---
phase: 36-enrichment-propose-mode
plan: "06"
subsystem: infra
tags: [n8n, hubspot, code-node, workflow-builder, propose-mode, dos-guard]

# Dependency graph
requires:
  - phase: 36-enrichment-propose-mode
    plan: "04"
    provides: "isReturnOnly(mode) — the shared two-state propose-mode write-guard predicate"
provides:
  - "ENRICH_MAX_PROPOSE_RECORDS = 20 (provisional) declared beside ENRICH_MAX_LIST_RECORDS = 2, same B4 derivation discipline"
  - "Parse HubSpot Event's batch-size guard is mode-aware: isReturnOnly(parsed.mode) selects MAX_PROPOSE_EVENTS vs MAX_WRITE_EVENTS, reusing the single isReturnOnly() predicate, before the size comparison"
  - "Boundary matrix pinning both ceilings at their exact edges, empty-array refusal in both modes, typo-mode fail-safe"
provides_downstream: [37-client-chunking]

# Actuals (#2632)
actuals:
  tokens: 9083
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Chained deferred placeholder substitution: __MAX_PROPOSE_RECORDS__ is a SECOND .replace() chained onto the existing __MAX_LIST_RECORDS__ substitution on ENRICH_PARSE_EVENT_CLOUD — no reordering of either declaration, no third constant"
    - "Ceiling selection by the SAME shared predicate that gates the write path: isReturnOnly(parsed.mode) selects the ceiling exactly as it selects action:\"proposed\" at Decide Action — a mode value can never mean return-only for one and write for the other"

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - tests/n8n/enrichmentBatchRefusal.test.mjs
    - tests/test_enrichment_lane_dedup.py

key-decisions:
  - "isReturnOnly's typo-mode fail-safe asymmetry extends to the ceiling: an unrecognised mode value gets the return-only (propose) ceiling, never the writer's — same direction of fail-safety 36-04 established for action:\"proposed\", now proven to reach resource limits too"
  - "parsed.mode is read at the ENVELOPE level only for ceiling selection (not the row-level parsed.mode ?? event.mode fallback used elsewhere) — an envelope with no top-level mode falls through to the stricter write ceiling even if individual events carry a mode, since this guard bounds how long the WHOLE request may take, not which mode a single row runs in"
  - "The pinned test test_parse_hubspot_event_ceiling_literal_matches_the_single_builder_declaration was amended in place (renamed, docstring records the 37-CONTEXT.md §13 reasoning) rather than deleted or silently reworded — its premise (one ceiling literal) was made false by design in Task 1"

patterns-established:
  - "Two-ceiling structural pin: a test asserting BOTH new-literal presence AND the old constant's unchanged value (ENRICH_MAX_LIST_RECORDS == 2) catches the specific accident a mode-aware split invites — widening the write path alongside the new path"

requirements-completed: [PREVIEW-03, DISPATCH-02]

coverage:
  - id: D19
    description: "A mode:\"propose\" request of 3..20 events passes the size guard and is enriched (today refused at 3); 21 is refused whole quoting its OWN ceiling (20), never 2"
    requirement: PREVIEW-03
    verification:
      - kind: unit
        ref: "tests/n8n/enrichmentBatchRefusal.test.mjs (mode:propose 3/20/21-event cases)"
        status: pass
    human_judgment: false
  - id: D20
    description: "mode absent or mode:\"write\", 3 events is refused exactly as before this plan — same branch, same message text, quoting 2; exactly-at-the-limit (2) is accepted"
    requirement: PREVIEW-03
    verification:
      - kind: unit
        ref: "tests/n8n/enrichmentBatchRefusal.test.mjs (mode absent / mode:write 2/3-event cases)"
        status: pass
    human_judgment: false
  - id: D21
    description: "Exactly one isReturnOnly() predicate exists in the built node; the mode-driven ceiling selection sits before the size comparison in source order; a typo mode gets the return-only ceiling"
    requirement: DISPATCH-02
    verification:
      - kind: structural
        ref: "tests/test_enrichment_lane_dedup.py (declares_exactly_one_return_only_predicate, selects_ceiling_by_mode_before_the_size_comparison)"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichmentBatchRefusal.test.mjs (typo mode \"proprose\" case)"
        status: pass
    human_judgment: false
  - id: D22
    description: "ENRICH_MAX_LIST_RECORDS is still literally 2 with its 37.44s derivation comment byte-untouched; ENRICH_MAX_PROPOSE_RECORDS = 20 is declared once, marked PROVISIONAL, with a B4-discipline derivation comment"
    requirement: PREVIEW-03
    verification:
      - kind: structural
        ref: "tests/test_enrichment_lane_dedup.py::test_parse_hubspot_event_ceiling_literals_match_the_two_builder_declarations"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-05
status: complete
---

# Phase 36 Plan 06: Mode-Aware Batch-Size Ceiling Summary

**`Parse HubSpot Event`'s batch-size refusal now selects between two ceilings by `mode` —
`MAX_PROPOSE_EVENTS = 20` (provisional) for return-only requests, `MAX_WRITE_EVENTS = 2`
(unchanged) for everything else — via the same `isReturnOnly()` predicate that already
gates the no-write guarantee, so a propose request of 3..20 events is enriched instead of
refused at 3.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3/3 completed
- **Files modified:** 4 (0 new; 1 `n8n/*.json` regenerated via the builder, never hand-edited)

## Accomplishments

- **Task 1 — mode-aware ceiling, end to end:** `ENRICH_PARSE_EVENT_CLOUD` now inlines
  `matchProposal.js` alongside `providerSelection.js` so `isReturnOnly` resolves inside
  the Code node. `ENRICH_MAX_PROPOSE_RECORDS = 20` is declared immediately below
  `ENRICH_MAX_LIST_RECORDS = 2` (left byte-untouched), carrying a derivation comment in
  the same B4 discipline — write ceiling's 37.44 s full-waterfall basis, zero-provider-call
  propose cost, the assumed 5 s/row (25% headroom over a 4 s worst case) against the
  ~100 s Cloudflare bound giving floor(100/5) = 20, and an explicit
  `# PROVISIONAL — replace with measured value` marker. The single `MAX_EVENTS` constant
  became three lines: `MAX_WRITE_EVENTS`, `MAX_PROPOSE_EVENTS`, and `MAX_EVENTS` selected
  by `isReturnOnly(parsed.mode) ? MAX_PROPOSE_EVENTS : MAX_WRITE_EVENTS`, placed after
  `parseWebhookBody(body)` and before the size comparison. The refusal message template
  was left untouched — it already interpolates `MAX_EVENTS`, so quoting the correct
  ceiling falls out of the selection.
- **Task 2 — the boundary matrix:** six new node-behavioral test cases pin both ceilings
  at their exact edges — propose at 20 (accepted) and 21 (refused, reason names both 21
  and "the limit is 20 record"), explicit `mode:"write"` at 2 (accepted) and 3 (refused,
  "the limit is 2 record"), an empty array in propose mode (refused with the empty-array
  reason, not swallowed by the size branch), and a typo mode `"proprose"` at 3 (accepted
  — the return-only ceiling, never the writer's).
- **Task 3 — structural two-ceiling guard:** the pinned test
  `test_parse_hubspot_event_ceiling_literal_matches_the_single_builder_declaration` was
  amended in place (not deleted, not silently reworded) — its premise, one ceiling
  literal, was made false by design in Task 1. Renamed to
  `..._ceiling_literals_match_the_two_builder_declarations`, its docstring records the
  37-CONTEXT.md §13 reasoning, and it now asserts both `MAX_WRITE_EVENTS` and
  `MAX_PROPOSE_EVENTS` trace to their single Python declarations plus
  `ENRICH_MAX_LIST_RECORDS == 2` explicitly — the assertion that catches the specific
  accident this plan must not commit (widening the write path alongside the propose
  path). Two further structural tests: the selection genuinely precedes the size
  comparison in source-character order, and exactly one `isReturnOnly()` declaration
  exists in the node (comment-only occurrences excluded via the existing
  `_strip_comments` helper).
- Every new/amended assertion red-checked individually: Task 1's Test A (propose 3 events)
  reverted-and-restored via manual re-edit (git `stash`/`apply` avoided per the destructive-git
  prohibition; edits were captured as an RTK pretty-diff, discovered non-patchable, and
  reapplied directly with `Edit`); Task 2's 21-refused and write-path-3 cases both
  confirmed failing (plus several collateral failures) by flipping the selection
  ternary's two arms, then restored; Task 3's three assertions each confirmed failing
  independently by hand-patching the built JSON (renamed constant, moved selection below
  the comparison, pasted a duplicate predicate), then regenerated to restore.
- No deviations from the plan's task structure.

## Task Commits

Each task was committed atomically:

1. **Task 1: mode-aware ceiling, constant + guard + regenerated artifact** — `4c572e4`
   (feat: MAX_WRITE_EVENTS/MAX_PROPOSE_EVENTS selection, 2 new node tests)
2. **Task 2: the boundary matrix** — `0a89a47` (test: 6 new node-behavioral boundary cases)
3. **Task 3: structural two-ceiling guard** — `8d3fac8` (test: pinned test amended in
   place, 2 new structural tests)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `ENRICH_PARSE_EVENT_CLOUD` inlines
  `matchProposal.js`; `ENRICH_MAX_PROPOSE_RECORDS = 20` declared with its derivation
  comment; the ceiling-selection block replaces the single `MAX_EVENTS` line
- `n8n/wf_enrichment_cloud.json` — regenerated via the builder (never hand-edited); the
  ONLY `n8n/*.json` that moved
- `tests/n8n/enrichmentBatchRefusal.test.mjs` — 8 new cases: Test A/B (Task 1) + the
  6-case boundary matrix (Task 2)
- `tests/test_enrichment_lane_dedup.py` — the single-ceiling pin amended in place (Task
  3), plus two new structural tests

## Decisions Made

- `parsed.mode` is read at the ENVELOPE level only for ceiling selection — not the
  row-level `parsed.mode ?? event.mode` fallback used elsewhere. An envelope with no
  top-level mode falls through to the stricter write ceiling even if individual events
  carry a mode, since this guard is about how long the WHOLE request may take, not which
  mode a single row runs in.
- `isReturnOnly`'s fail-safe asymmetry (36-04) now demonstrably reaches resource limits,
  not just the write gate: a typo mode value selects the return-only ceiling, never the
  writer's.
- The one deliberately-changed pinned test was amended in place with the reason inline
  (phase_hard_rules #5) — never deleted, never silently reworded to pass.

## Deviations from Plan

None — plan executed exactly as written. One process note: the plan's suggested
red-check mechanism for Task 1 ("stashing the builder edit") was not used verbatim — this
repo's `destructive_git_prohibition` forbids `git stash` inside any git working context
because the stash ref is shared and can leak state across concurrent sessions. Used
`git checkout -- <file>` (a targeted, single-file discard, explicitly permitted) followed
by manual re-application of the same edits via `Edit`, achieving the identical
red-then-green proof without the prohibited command.

## Issues Encountered

None blocking. `git diff` piped through this environment's `rtk` proxy pretty-prints
rather than emitting a raw unified diff, so a captured "diff" was not `git apply`-able;
discovered during the Task 1 red-check and worked around by reapplying the known edits
directly rather than via patch.

## User Setup Required

None — no external service configuration required. This plan makes zero live/deploy
changes; `scripts/deploy_n8n_workflows.py` was not run (denied to agents per this phase's
constraints). The tenant remains disarmed and untouched by this plan.

## Next Phase Readiness

- A `mode:"propose"` request of 3..20 events is now bounded by its own cost (20, a
  provisional bound pending a live B4-shaped probe) rather than the full-waterfall write
  ceiling (2) — Phase 37's client no longer needs to chunk propose calls into 2-row
  batches.
- The write path is provably unchanged: `ENRICH_MAX_LIST_RECORDS == 2` is asserted
  directly, its derivation comment is untouched, and the write-path refusal message is
  pinned to the literal phrase "the limit is 2 record".
- **Open proof point carried forward:** the propose ceiling (20) is provisional. It must
  be earned by a live B4-shaped probe (measured latency + 25% headroom against the
  ~100 s Cloudflare bound) at the first live propose run, and the derivation comment
  rewritten with the measurement and its date — the same promotion the 37.44 s write-path
  note underwent.
- Verification suites green against baselines: `.venv/bin/python -m pytest -q` -> 1962
  passed / 6 skipped (baseline 1960/6). `node --test tests/n8n/*.test.mjs` -> 617 passing
  (baseline 609, +8: 2 from Task 1, 6 from Task 2). `.venv/bin/python -m pytest
  operator-claude-plugin/tests/ -q` -> 1052 passed / 5 skipped (unchanged). `grep -c
  'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` -> 0 for every file. Builder idempotent —
  a second `scripts/build_cloud_workflows.py` run leaves `git diff --stat n8n/` empty.
  `scripts/deploy_n8n_workflows.py` was NOT run. No blockers for 36-05's operator-run
  checkpoint (this plan lands ahead of it, per the phase's "one deploy, not two" rule).

## Self-Check: PASSED

- FOUND: `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-06-SUMMARY.md`
- FOUND: `n8n/wf_enrichment_cloud.json` (Parse HubSpot Event carries the mode-aware ceiling)
- FOUND commit: `4c572e4`
- FOUND commit: `0a89a47`
- FOUND commit: `8d3fac8`

---
*Phase: 36-enrichment-propose-mode*
*Completed: 2026-08-05*
