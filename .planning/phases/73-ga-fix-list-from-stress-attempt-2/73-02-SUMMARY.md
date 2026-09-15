---
phase: 73-ga-fix-list-from-stress-attempt-2
plan: 02
subsystem: n8n-review-loop-and-ingest-throttle
tags: [n8n, hubspot, review-approve, enum-serialization, rate-limit, node-test]

requires:
  - phase: 73-ga-fix-list-from-stress-attempt-2
    provides: "73-01's frozen-runData proof discipline and D-73-14 run-manifest scoping (unrelated code path, same phase)"
provides:
  - "F-E1 fixed: an array-valued approved review candidate (e.g. lv_content_type: ['unknown']) serializes to a semicolon-joined string at the one choke point both review consumers (operator-triggered endpoint and the scheduled Apply Review backstop) pass through"
  - "F-A3r fixed: the three ingest-lane per-row HubSpot search nodes throttle at 400ms (2.5 req/s, 50% headroom under HubSpot's account-wide 5 req/s search cap), up from 250ms"
  - "tests/n8n/ingestSearchThrottle.test.mjs: the first test in this repo asserting a batching interval, deriving the throttled node set structurally rather than by name"
affects: [review-decision-endpoint, scheduled-maintenance-apply-review, contact-ingest-search-lane]

actuals:
  tokens: 6200
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Array serialization happens strictly AFTER the enum validity check, never before -- an unaccepted element must still be refused into `invalid` rather than hidden inside a joined string"
    - "Structural node-tests derive their target set from the generated JSON's own shape (options.batching.batch), never a hard-coded node-name list, so a future unguarded addition fails the test automatically"

key-files:
  created:
    - tests/n8n/ingestSearchThrottle.test.mjs
  modified:
    - n8n/code/reviewApply.js
    - tests/n8n/reviewLoop.test.mjs
    - scripts/build_cloud_workflows.py
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - n8n/wf_contact_ingest_cloud.json
    - .planning/debug/ingest-search-429-rate-limit.md (moved to .planning/debug/resolved/)

key-decisions:
  - "Fixed reviewApply.js at the single canonicalPatch assignment inside its decision loop, not the two decoy Array.isArray(...).join(';') blocks in ENRICH_DECIDE_CLOUD/ENRICH_DECIDE_CO_CLOUD named by 73-RESEARCH.md Pitfall 1 -- those run on the enrichment lane's own pre-write path, not the review-approve path that actually 400'd in execution 12502."
  - "Committed the RED test fixtures as their own test(73-02) commit before the feat(73-02) fix commit, quoting the observed failure output in this SUMMARY, per the tracer/tdd gate contract -- the fix was already written in the working tree when the commits were split, so RED was captured by running the suite (not by the commit's own tree state) before splitting."
  - "D-73-15's 400ms is a straight constant widen (250 -> 400) with no retryOnFail added, per the debug file's own prior constraint (n8n ignores retryOnFail under continueRegularOutput)."

requirements-completed: [F-E1, F-A3r]

coverage:
  - id: D1
    description: "An array-valued approved review candidate serializes to a semicolon-joined string before the PATCH, at the one choke point both review consumers share"
    requirement: F-E1
    verification:
      - kind: unit
        ref: "tests/n8n/reviewLoop.test.mjs -- three new tests: one-element array, multi-element array, refused-element-stays-invalid"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/reviewLoop.test.mjs tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/hubspotEnumValidation.test.mjs (84 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The three ingest-lane per-row search nodes throttle at 400ms with no retryOnFail, pinned structurally"
    requirement: F-A3r
    verification:
      - kind: unit
        ref: "tests/n8n/ingestSearchThrottle.test.mjs (3 new tests, structural derivation from options.batching)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/ingestSearchThrottle.test.mjs tests/n8n/ingestCarryMerge.test.mjs (5 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Zero regeneration diff and both full suites green at/above baseline"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/build_cloud_workflows.py leaves n8n/ with zero git diff (re-run after every commit)"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/*.test.mjs -> 1176 passed / 0 failed (baseline 1170/0)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/ -> 4957 passed / 154 skipped (baseline 4952/154)"
        status: pass
    human_judgment: false

patterns-established:
  - "Array serialization at reviewApply.js's canonicalPatch assignment: Array.isArray(enumCheck.value) ? enumCheck.value.join(';') : enumCheck.value -- strictly after the enum check."

duration: 20min
completed: 2026-09-15
status: complete
---

# Phase 73 Plan 02: Review-approve array serialization + ingest search throttle widen Summary

**Fixed the Stage E review-approve 400 (array-valued candidates never serialized before the HubSpot PATCH) and widened the ingest lane's per-row search throttle from 250ms to 400ms to close out the one residual 429 from attempt 2's 48-row send.**

## Performance
- **Duration:** ~20 min
- **Started:** 2026-09-15T13:00Z (approx, first commit)
- **Completed:** 2026-09-15T13:03Z
- **Tasks:** 2/2
- **Files modified:** 7 (1 new test file, 2 code files, 4 regenerated workflow JSONs, 1 archived doc)

## Accomplishments
- Traced F-E1 to the actual choke point (`reviewApply()`'s `canonicalPatch` assignment) rather than the two decoy `Array.isArray(...).join(";")` blocks in the enrichment lane's decide nodes, per 73-RESEARCH.md's own Pitfall 1 warning.
- Added three new `reviewLoop.test.mjs` cases (one-element array, multi-element array, refused-element-stays-invalid) and observed the first two RED before the fix.
- Fixed the single assignment: join an array value with `;` strictly after `normalizeEnumValue`'s check, so a refused element still lands in `invalid` rather than being smuggled into an accepted string.
- Regenerated all eight workflow JSONs; only the two that actually inline `reviewApply.js` (`wf_review_decision_cloud.json`, `wf_scheduled_maintenance_cloud.json`) changed — confirmed `wf_enrichment_cloud.json`/`wf_enrichment_local_live.json` merely mention the filename in a comment and were correctly untouched.
- Widened `_INGEST_SEARCH_BATCH_INTERVAL_MS` from 250 to 400 (2.5 req/s, 50% headroom under HubSpot's 5 req/s account-wide search cap) across all three ingest-lane per-row search call sites.
- Added `tests/n8n/ingestSearchThrottle.test.mjs`, the first test in this repo asserting a batching interval — derives the throttled node set from the generated JSON's `options.batching` shape, not a name list, so a future unthrottled fourth search node fails it automatically.
- Archived `.planning/debug/ingest-search-429-rate-limit.md` to `.planning/debug/resolved/` with a closing note naming this plan and D-73-15, per the file's own "Archive it when D-73-15 lands" instruction.

## Task Commits
1. **Task 1 (RED): array-valued candidate fixtures** - `cb2d1bfa` (test)
2. **Task 1 (GREEN): serialize array candidates at reviewApply** - `7057f5e2` (feat)
3. **Task 2: widen ingest search throttle to 400ms** - `21e7342f` (fix)

## RED Evidence (Task 1, quoted per acceptance criteria)

Before the fix, `node --test tests/n8n/reviewLoop.test.mjs` failed exactly the two new
positive-case assertions:

```
✖ reviewApply: a one-element array chosen_value on a multi-select enum serializes to a string, not an array
  actual: [ 'unknown' ]   expected: 'unknown'

✖ reviewApply: a multi-element array chosen_value serializes joined with a semicolon, in order
  actual: [ 'live_broadcast', 'streaming' ]   expected: 'live_broadcast;streaming'

ℹ tests 10
ℹ pass 8
ℹ fail 2
```

The third (refusal) case passed unmodified both before and after — the enum guard's
`invalid` path was never broken, only the accepted-value assignment.

## Files Created/Modified
- `n8n/code/reviewApply.js` - array-valued canonicalPatch values now join on `;` after the enum check
- `tests/n8n/reviewLoop.test.mjs` - three new array-serialization test cases
- `tests/n8n/ingestSearchThrottle.test.mjs` - new structural throttle test (3 cases)
- `scripts/build_cloud_workflows.py` - `_INGEST_SEARCH_BATCH_INTERVAL_MS` 250 -> 400, updated comment with F-A3r reasoning
- `n8n/wf_review_decision_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` - regenerated with the reviewApply fix
- `n8n/wf_contact_ingest_cloud.json` - regenerated with the 400ms throttle
- `.planning/debug/resolved/ingest-search-429-rate-limit.md` - archived from `.planning/debug/`, closing note added

## Decisions Made
See `key-decisions` in frontmatter.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required
None - no external service configuration required. Per D-73-18 and this plan's own
prohibitions, no deploy/bounce/arm was performed or attempted; that remains the
operator's end-of-phase step.

## Next Phase Readiness
Both fixes are regenerated, tested (offline) and committed disarmed. The live proof of
both — a re-run of the 48-row CSV showing zero residual 429s and a clean Stage E
approve on an array-valued candidate — is deferred to the operator's end-of-phase
deploy + bounce + attempt-3 UAT, consistent with D-73-18 and the plan's prohibition on
Claude arming/deploying/bouncing.

## Self-Check: PASSED

- `tests/n8n/ingestSearchThrottle.test.mjs` exists: FOUND
- `git log --oneline -E --grep="^[a-z]+\(0*73-0*2\):"` -> 3 commits found (cb2d1bfa, 7057f5e2, 21e7342f)
- `node --test tests/n8n/reviewLoop.test.mjs tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/hubspotEnumValidation.test.mjs` -> 84 passed, 0 failed
- `node --test tests/n8n/ingestSearchThrottle.test.mjs tests/n8n/ingestCarryMerge.test.mjs` -> 5 passed, 0 failed
- `node --test tests/n8n/*.test.mjs` -> 1176 passed / 0 failed (baseline 1170/0)
- `.venv/bin/python -m pytest -q tests/ operator-claude-plugin/tests/` -> 4957 passed / 154 skipped (baseline 4952/154)
- `.venv/bin/python scripts/build_cloud_workflows.py` -> zero git diff on `n8n/`
- Every regenerated workflow reads disarmed: zero true-valued `ALLOW_*` write flags across all `n8n/wf_*.json`

---
*Phase: 73-ga-fix-list-from-stress-attempt-2*
*Completed: 2026-09-15*
