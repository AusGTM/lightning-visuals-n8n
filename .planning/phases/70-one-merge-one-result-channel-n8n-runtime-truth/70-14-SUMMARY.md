---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 14
subsystem: infra
tags: [n8n, workflow-generation, result-channel, walker-fidelity, gap-closure]

requires:
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "Gate 5's live observation (G-70-5) — the enrichment_2x2 phantom-row leak and the execution 12316 self-dispatch divergence"
provides:
  - "A shared `hasRowIdentity` predicate, defined once, applied at both response builders (Build Response, Build Ingest Response) before either projects a row"
  - "A marker item can no longer survive the negative filter by being made non-empty upstream (the Credits Broadcast combineAll mechanism Gate 5 exposed)"
  - "A frozen, verified reproduction of execution 12316 recording — not modelling — the three unconnected-source node runs, as a walker prohibition guard"
affects: [70-15 CLAUDE.md/deploy record, Gate 7 deploy, any future plan touching Build Response or Build Ingest Response]

actuals:
  tokens: 6810
  tasks: 2
  commits: 3
  plan_head_before: 51e97227d28d892ab44188c40476a85dd3695776

tech-stack:
  added: []
  patterns:
    - "A shared row-identity predicate (defined once, imported into both jsCode wrappers via ROW_IDENTITY_KEYS_JS) rather than two hand-copied filter lists"
    - "A positive identity filter placed BEFORE a convergence node's own projection, so a marker never receives the projection's stamped fields at all"
    - "A frozen fixture pair (graph JSON + runData sidecar) verified rather than trusted, with producer sets recomputed from the frozen graph's own connections instead of hand-copied into the sidecar or the test"

key-files:
  created:
    - tests/n8n/buildResponseMarkerFilter.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_contact_ingest_cloud.json
    - tests/n8n/walkerEngineFidelity.test.mjs
    - tests/n8n/fixtures/frozen/README.md

key-decisions:
  - "Identity keys are row_id, action, outcome, object_id, hs_object_id, id — six, not the plan's four (row id, action, outcome, HubSpot object id). `object_id` (the raw webhook field, distinct from the projected `hs_object_id`) was added because 'Unsupported Object Type' rows never resolve an identity match and so never carry `hs_object_id` — without it a real unsupported-type event with a real object id would have been dropped, exactly the class the plan's own `fails_when` text prohibits. `id` was added after three real acceptance tests (enrichmentMixedBatch.test.mjs) actually dropped a real row: the armed write lanes carry the write node's raw HTTP response (`{id, properties}`) straight into Build Response Merge with no carry-merge reattachment of row_id/action, so `id` is the only identity that response ever carries."
  - "null/undefined never counts as identity for any key — this is what lets a genuinely unsupported webhook event (a real, non-null object_id) survive while the phantom raw-parsed-event marker (object_id: null, because it entered via an empty self-dispatch seed, never a real webhook body) does not."
  - "Build Ingest Response's filter is applied at the emit point (after the row is projected), not before — `decided` rows already always carry `action` from Decide Action, so this is expected to be a no-op on every existing suite; verified rather than assumed with a new synthetic starved-lane-sentinel case, since the ingest suites staying green only proves the common path is untouched, not that the filter is reachable."
  - "Task 2 adds zero changes to tests/n8n/lib/walkWorkflow.mjs — the divergence is recorded as a fact about execution 12316, never taught to the walker as a reproducible mechanism (D-70-19/D-70-26)."
  - "The new fidelity case computes each mismatched node's declared producers directly from the frozen graph's own `connections` map (not hand-copied from the sidecar), and cross-checks that against the sidecar's own `declared_producers` field — a second, independent check that the sidecar itself has not drifted from the fixture it describes."

patterns-established:
  - "A response-builder convergence node gets a POSITIVE identity test in front of its projection, not just a negative empty-object test behind it — a negative test alone cannot catch a marker an upstream broadcast has already made non-empty."
  - "A live divergence nobody isolated is pinned as a named, dated `[observed live]` prohibition case in the fidelity suite, asserting the instrument's own absence of the behavior, rather than either ignored or modelled."

requirements-completed: [D-70-25, D-70-26]

coverage:
  - id: D1
    description: "A marker item (no row identity) is dropped by both Build Response and Build Ingest Response before either stamps a projection onto it; a real terminal (a request-level refusal identified by outcome only, an unsupported-type row carrying a real object id, a raw write response carrying only `id`, a row identified only by row_id) survives untouched."
    requirement: "D-70-25"
    verification:
      - kind: unit
        ref: "tests/n8n/buildResponseMarkerFilter.test.mjs (9 tests)"
        status: pass
      - kind: integration
        ref: "tests/n8n/enrichmentMixedBatch.test.mjs (3 tests that caught the `id`-only write-response gap)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The walker's engine-fidelity suite carries a frozen reproduction of execution 12316 recording, as a documented divergence, that three nodes' runData `source` names a node with no declared connection to them — and the walker does not reproduce those three runs."
    requirement: "D-70-26"
    verification:
      - kind: unit
        ref: "tests/n8n/walkerEngineFidelity.test.mjs (3 new tests: fixture verification x2, the prohibition case x1)"
        status: pass
    human_judgment: false

duration: not measured (PLAN_START_TIME was not captured at session start — see Issues Encountered)
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 14: Stop Markers Reaching the Wire, Record What Execution 12316 Cannot Be Explained Summary

**A shared `hasRowIdentity` predicate at both `Build Response` and `Build Ingest Response` drops any item carrying none of six identity keys before it is ever projected into a response row, and a frozen, verified reproduction of execution 12316 pins — as a prohibition, never a model — that the walker does not reproduce the three node runs whose engine source named a node with no declared connection to them.**

## Performance

- **Duration:** not measured
- **Tasks:** 2
- **Files modified:** 6 (2 source, 2 generated JSON, 2 test/doc)

## Accomplishments
- `Build Response` and `Build Ingest Response` now both run a positive row-identity test (`row_id`, `action`, `outcome`, `object_id`, `hs_object_id`, `id`) in front of their own projections, so a marker item — even one an upstream `combineAll` broadcast has already made non-empty — cannot come back to the caller carrying a full outcome projection.
- The RED-first pin (`tests/n8n/buildResponseMarkerFilter.test.mjs`) reproduces Gate 5's exact recovered key sets (70-RUNTIME-VERDICT.json `sends[0].recovered_shapes`) via the walker's single-node `runNode`, confirmed RED against the pre-fix committed JSON by temporarily reverting the generator/JSON changes and re-running the file (transcript captured, not just claimed).
- `walkerEngineFidelity.test.mjs` gains a third live reproduction: execution 12316's three unconnected-source node runs (`Recompute Requested Sentinel Gate`, `Dispatch Self`, `Build Scale Up Fan-Out`) are verified against the frozen gap-closure body and runData sidecar, and asserted ABSENT from the walker's replay — a prohibition that fails the moment the walker ever starts reproducing an unisolated mechanism.
- `tests/n8n/lib/walkWorkflow.mjs` is confirmed byte-identical to the commit that closed plan 70-13 (`git diff --quiet` against `51e9722`).

## Task Commits

1. **Task 1 (RED): pin the marker filter before it exists** - `fa19a23` (test)
2. **Task 1 (GREEN): the shared identity filter at both response builders** - `04ca411` (fix)
3. **Task 2: execution 12316 as a walker prohibition guard** - `b77dcf4` (test)

**Plan metadata:** this file's own commit (docs, see below)

## Files Created/Modified
- `scripts/build_cloud_workflows.py` - `ROW_IDENTITY_KEYS_JS`/`hasRowIdentity` defined once near `SENTINEL_MARKER_KEY`; spliced into `ENRICH_BUILD_RESPONSE` and `BUILD_INGEST_RESPONSE`; applied as a `.filter(hasRowIdentity)` before each node's projection
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_contact_ingest_cloud.json` - regenerated, jsCode-only change, node counts unchanged (287 / 69)
- `tests/n8n/buildResponseMarkerFilter.test.mjs` - new: 9 cases pinning the marker-drop / real-terminal-survival contract at both response builders
- `tests/n8n/walkerEngineFidelity.test.mjs` - +3 cases: frozen-body verification, runData-sidecar mismatch verification, the execution-12316 prohibition guard
- `tests/n8n/fixtures/frozen/README.md` - two new rows naming `wf_enrichment_cloud.gap-closure.2026-09-10.json` and `exec_12316.runData.json`, both already committed at planning time and left untouched by this plan

## Decisions Made
See `key-decisions` in frontmatter — the two-key widening beyond the plan's stated four (`object_id`, `id`) is the load-bearing decision here; both are backed by a specific failure this plan's own tests produced (see Deviations).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, found writing the RED test] `object_id` added to the identity key set**
- **Found during:** Task 1, before regenerating — reasoned from the plan's own `fails_when` clause ("a real terminal — an unsupported row carrying an object id — is dropped") before any test failed on it.
- **Issue:** The plan's stated four identity keys (row id, action, outcome, HubSpot object id) name `hs_object_id` implicitly, but `Unsupported Object Type` rows never resolve an identity match and so never carry `hs_object_id` — only the raw webhook `object_id`. A four-key filter using only `hs_object_id` would have dropped a genuinely unsupported webhook event with a real (non-null) object id.
- **Fix:** Added `object_id` to `ROW_IDENTITY_KEYS`, with the null-check doing the real work: a marker's `object_id` is null (it entered via an empty self-dispatch seed), a real unsupported event's is not.
- **Files modified:** scripts/build_cloud_workflows.py
- **Verification:** `buildResponseMarkerFilter.test.mjs`'s "an unsupported-type event carrying a REAL (non-null) object id survives" case
- **Committed in:** `04ca411`

**2. [Rule 1 - Bug, found by the pre-existing acceptance suite] `id` added to the identity key set**
- **Found during:** Task 1, first full-suite run after the initial (four-key) filter — `enrichmentMixedBatch.test.mjs`'s three armed-write-lane tests failed ("1 !== 2", a real row dropped).
- **Issue:** The armed write lanes wire "HubSpot Update"/"HubSpot Create"'s raw HTTP response straight into `Build Response Merge` with no carry-merge reattachment of `row_id`/`action` — the response arrives as bare `{id, properties}`, which none of the plan's four (nor `object_id`) identify. The filter was dropping the one row a permitted write batch exists to report.
- **Fix:** Added `id` to `ROW_IDENTITY_KEYS`.
- **Files modified:** scripts/build_cloud_workflows.py
- **Verification:** `node --test tests/n8n/*.test.mjs` — all 1063 pre-existing tests green, plus the new `buildResponseMarkerFilter.test.mjs` case pinning this specific shape.
- **Committed in:** `04ca411`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in the plan's stated identity-key list, caught before and by testing respectively)
**Impact on plan:** Both widenings were necessary for correctness — the plan's own `fails_when`/acceptance text names exactly the failure modes these two additions prevent. No scope creep beyond widening one shared constant.

## Issues Encountered
- `PLAN_START_TIME` was not captured at the start of this executor session (the `record_start_time` protocol step was skipped in practice). Duration is therefore reported as "not measured" rather than fabricated from file timestamps.
- An earlier manual key-set comparison (during investigation, not committed) mis-transcribed one of the verdict's recovered shapes and appeared to be missing `outcome_contract_version`; a programmatic diff against the actual JSON showed the two sets match exactly. No test or code was affected — caught before writing anything into the fixtures or the SUMMARY.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The result-channel leak D-70-25 targeted is closed at generation time and pinned by tests built from the live-observed shapes, not invented ones.
- Execution 12316's divergence is now a permanent, named record in the fidelity suite rather than a fact living only in `70-CONTEXT.md`/`70-UAT.md` prose — the next agent who touches the scale-up-adjacent nodes (there are none left after 70-13, but the sentinel/gate PATTERN persists elsewhere in the graph) will hit this guard if the walker ever starts explaining what it still cannot explain.
- Nothing deployed, bounced, armed, or sent. Gates 7/8/9 (CLAUDE.md §13.0.2, D-70-27) remain operator gates, unaffected by this plan.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all three task commit hashes
(`fa19a23`, `04ca411`, `b77dcf4`) confirmed present in `git log`.
