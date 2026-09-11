---
phase: quick-260911-ss4
plan: 01
subsystem: operator-claude-plugin
tags: [enrichment, hubspot, n8n, budget, match-state, skill-md]

requires: []
provides:
  - "scripts/match_state.py — a per-batch durable store for preingest.classify_matches's
    step-2 output, keyed on the match's own MatchOutcome.run_id"
  - "enrich-before-ingest/SKILL.md rewired so preingest.match_batch is called exactly
    once per batch (step 2); steps 3, 4, 5, 7 read the persisted classification back"
affects: [enrich-before-ingest, contact-upload, suggest-contacts]

actuals:
  tokens: 10988
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "match_state.py mirrors run_state.py's module shape: save/load/classify_read,
      atomic 0600 writes, a fresh per-module forbidden-name guard (D-69-01 anti-DRY)"
    - "forbidden-name guard scans NAMES only (keys, row_ids) never string VALUES —
      lets a contact literally named Grant persist while a webhook_secret-shaped key
      is refused"

key-files:
  created:
    - operator-claude-plugin/scripts/match_state.py
    - operator-claude-plugin/tests/test_match_state.py
  modified:
    - operator-claude-plugin/scripts/run_report.py
    - operator-claude-plugin/tests/test_forbidden_marker_parity.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py
    - operator-claude-plugin/tests/test_linkedin_row_composition.py

key-decisions:
  - "match_state's forbidden-name guard is reimplemented fresh (not imported from
    held_queue/run_state) per the plugin's anti-DRY per-store discipline (D-69-01),
    and deliberately scans names only, never string values (decision 1 in the
    module's own docstring) — a value-scanning guard would refuse a row named Grant
    (recorded UAT batch 2, Grant Dewsbury) and drop the fence back into the re-match
    this store exists to stop."
  - "load() raises MatchStateError on absent, malformed, or another run's file —
    never degrades to an empty classification, which would read as 'no matches' and
    silently skip real rows."
  - "Rows are persisted verbatim with no field allowlist (unlike held_queue's), since
    this store's consumer (extraction.write_dispatch_csv) needs a wider, config-driven
    column set than held_queue's re-send-only projection."

patterns-established:
  - "Per-batch match classification survives across process boundaries via a durable
    JSON file keyed on the match's own correlation id, exactly the pattern
    run_state.py already established for dispatch scope."

requirements-completed: []

coverage:
  - id: D1
    description: "match_state.py store: save/load/classify_read round-trips the
      recorded UAT batch-1 shape; a Grant-named row persists; a webhook_secret-shaped
      row key or grant-shaped row_id is refused; an absent/malformed/other-run file
      raises MatchStateError; match_state-*.json prunes at 7 days; the parity suite
      drives eight matchers."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_match_state.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_forbidden_marker_parity.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_report.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "SKILL.md rewired: exactly one preingest.match_batch call (step 2);
      steps 3/4/5/7 load the persisted classification in a fence; steps 5/6/9 name the
      load as the rebuild path in prose; step 2 prints match_run_id."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_linkedin_row_composition.py"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-11
status: complete
---

# Quick Task 260911-ss4: F1 — enrich-before-ingest persists the step-2 match Summary

**`scripts/match_state.py` now persists step 2's match classification per batch, and
`enrich-before-ingest/SKILL.md` calls `preingest.match_batch` exactly once — closing a
leak that cost the recorded UAT batch SIX propose executions instead of ONE.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 completed
- **Files modified/created:** 10 (2 created, 8 modified)

## Accomplishments

- Built `scripts/match_state.py`, the plugin's next per-run durable artifact,
  mirroring `run_state.py`'s module shape: `save`/`load`/`classify_read` over
  `preingest.classify_matches`'s five-key classification, keyed on the match's own
  `MatchOutcome.run_id`.
- The forbidden-name guard scans names only — top-level classification keys, every
  `row_id`, and every key inside a persisted `row` dict — never a string value, so a
  contact literally named Grant (recorded UAT batch 2, Grant Dewsbury) persists while
  a `webhook_secret`-shaped row key or grant-shaped `row_id` is refused with nothing
  written.
- `load()` raises `MatchStateError` on an absent, unreadable, malformed, or
  other-run's file — never degrading to an empty classification that would read as
  "no matches" and silently skip real rows.
- Registered `match_state-*.json` in `run_report._PRUNE_SHORT_TTL_GLOBS` (the 7-day
  family beside `run_state-*.json`) and `match_state` as the eighth module in
  `test_forbidden_marker_parity._KEY_MATCHER_MODULES`.
- Rewired `skills/enrich-before-ingest/SKILL.md`: step 2 is now the SKILL's only
  `preingest.match_batch` call — it binds `match_run_id = outcome.run_id`, prints it,
  and calls `match_state.save`. Step 3 loads, applies the operator's confirm/deny/pick
  decisions, and saves back under the same `match_run_id`. Steps 4 and 7 load the
  classification before building `unmatched_rows`/`confirmed_ids`. Step 5's linkedin
  fence — which used to rebuild the whole match from `rows_from_table` through
  `classify_matches` purely to reach one unmatched row — now loads the persisted
  classification instead. Steps 5 (main dispatch and confidence fences), 6, and 9 name
  `match_state.load(match_run_id)` in prose as the rebuild path for `unmatched_rows`.
- Updated `test_skill_sequence_coverage.py`'s registry (the step-2 entry gained a
  trailing `match_state.save` and repointed to the new Task 1 composition test; a new
  step-3 entry was added pointing at the same test; the linkedin entry's tuple became
  `("match_state.load", "extraction.validate")`) with `MAX_GRANDFATHERED` left at 0.
- Rewrote `test_linkedin_row_composition.py`'s second test to drive the new
  `match_state.load` -> `extraction.validate` sequence (saving a classification with a
  linkedin-only unmatched row, loading it back, then validating) instead of driving a
  match the SKILL no longer documents there.

## Task Commits

Each task was committed atomically:

1. **Task 1: match_state store — save, load, classify_read, driven end to end on the
   recorded shape** - `9918994c` (feat)
2. **Task 2: rewire every SKILL.md fence to load the persisted outcome, and pin it** -
   `d6f78c1e` (feat)

## TDD Evidence

Task 1's RED, observed before `match_state.py` existed:

```
ModuleNotFoundError: No module named 'match_state'
```

Task 2's RED, observed against the unedited SKILL.md (9 failing assertions, including
the load-bearing one):

```
AssertionError: assert 'classified = match_state.load(match_run_id)' in "5. **Ask for
this waterfall run, then run it..."
```

(`test_step_5s_linkedin_fence_loads_the_persisted_classification_not_a_second_match` —
the second `match_batch` call at the linkedin fence, the exact leak this quick task
closes, failing the span assertion before any prose was edited.)

## Deviations from Plan

None — plan executed exactly as written. `plugin.json` was not bumped and
`CHANGELOG.md` was not touched, per the plan's explicit exclusion (260911-ss7 owns the
version bump).

## Known Stubs

None.

## Threat Flags

None beyond the plan's own threat model (ASVS level 1, nothing `high`) — no new
network endpoint, auth path, or schema change at a trust boundary was introduced
outside what T-ss4-01 through T-ss4-05 already cover.

## Residual Note (CLAUDE.md §31 rule 1 — prose, not a new todo; no test, no recorded hit)

`held_queue._first_forbidden` scans string leaves, so a held row for a contact named
Grant would be refused by the same mechanism this plan deliberately narrowed for
`match_state.py`. Not observed live, not fixed here — out of this plan's scope.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/match_state.py` — FOUND
- `operator-claude-plugin/tests/test_match_state.py` — FOUND
- Commit `9918994c` — FOUND (`git log --oneline --all | grep 9918994c`)
- Commit `d6f78c1e` — FOUND (`git log --oneline --all | grep d6f78c1e`)
- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` — 2923 passed, 5 skipped
- `node --test tests/n8n/*.test.mjs` — 1101 passed, 0 failed (untouched, confirming
  `git diff --stat n8n/` is empty)
- `/usr/bin/grep -c 'preingest.match_batch(' operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — 1
- `plugin.json` version — unchanged at `0.45.0`
