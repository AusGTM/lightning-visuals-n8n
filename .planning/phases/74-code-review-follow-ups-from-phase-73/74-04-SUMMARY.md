---
phase: 74-code-review-follow-ups-from-phase-73
plan: 04
subsystem: offline-tooling
tags: [n8n, walker, merge-drain-order, tdd, python, node-test, enrichment-lane]

# Dependency graph
requires:
  - phase: 74-code-review-follow-ups-from-phase-73 (74-01)
    provides: "tests/n8n/fixtures/frozen/exec_12522.runData.json -- the D-74-03 fidelity fixture, and the widened freezer scrub"
provides:
  - "tests/n8n/lib/walkWorkflow.mjs's corrected alwaysOutputData padding rule (output index 0 only) and topological drain-order preference -- every offline graph proof in this repo now rests on this"
  - "n8n/wf_enrichment_cloud.json's 'Companies Research Errored Sentinel' -- closes the structural gap D-74-14 names on the companies research-error branch"
  - "CLAUDE.md section 13.0.3's two new rows (padding rule, zero-rejection drain order)"
affects: [74-05-PLAN.md, 74-06-PLAN.md]

# Actuals (#2632)
actuals:
  tokens: 9795   # code-only (excludes the regenerated n8n/wf_enrichment_cloud.json): chars/4 = 39182/4
  tasks: 3
  commits: 4
  plan_head_before: fad340e54995ae1f4e9f979b30aac137a9f87acb
  # Full realized diff including the regenerated n8n/wf_enrichment_cloud.json: 81359 chars
  # (~20340 chars/4) -- the code-only figure above is the meaningful one for estimate
  # calibration, same convention 74-01-SUMMARY.md used for its own generated-fixture diffs.

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "propagate()'s alwaysOutputData guard gates on outputIndex === 0, matching n8n's own ensureAlwaysOutputData -- never on 'whichever branch is empty'"
    - "v1 end-of-run drain prefers the most-upstream qualifying Merge (static BFS over connections, cached, insertion order as tiebreak) instead of a plain Object.entries insertion-order scan -- an ordering preference only, MN-01's one-drain-per-Merge cap is unchanged"
    - "_add_starved_lane_sentinel sourced from the node whose delivered row set a routing IF evaluates, firing the universally-quantified form of the IF's own condition -- closes an AOD gap on the IF's non-zero output without a second producer on any input that could double-fire"

key-files:
  created: []
  modified:
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/n8n/walkWorkflow.test.mjs
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - tests/n8n/enrichmentConvergenceMerge.test.mjs
    - tests/n8n/researchErrorGateFlow.test.mjs
    - tests/n8n/walkerEngineFidelityV1.test.mjs
    - CLAUDE.md

key-decisions:
  - "The one-line D-74-03 fix (gate padding on outputIndex === 0) exposed a SECOND, independent defect: with padding removed, Create Carry Merge must drain via the v1 end-of-run mechanism instead of completing in the main loop, and the walker's plain insertion-order drain scan could (and on the committed ingest graph, did) fire a downstream Merge before its upstream producer, using up that Merge's one-drain cap (MN-01) before the real delivery arrived -- a false merge_pending_runs_undrained. Fixed by making the drain prefer the most-upstream qualifying Merge (static BFS over connections), not by relaxing MN-01's cap or reordering anything else. This was NOT anticipated by the plan's own text (which framed the possible fix as 'a merge whose pending run is its FIRST drain is fired rather than reported') -- the actual shape needed a topological preference, not a first-drain exemption. Documented as the finding it is, not forced into the plan's anticipated shape."
  - "D-74-14's actual reproduced defect differs from 74-CONTEXT.md's plan-time prediction (itemCounts {1: 2} on 'Build Response Merge'). The real trace (reproduced offline before writing any fix) shows 'Merge Company Fan-In' -- not 'Build Response Merge' -- left with inputs 1 and 2 unfilled when every row's research errors, and starvedWithData does not flag it as a loss (the row still reaches Build Response correctly via 'Build Research Failure Response'). Fixed anyway, per the plan's own instruction to close the structural gap rather than rely on downstream filtering, with one _add_starved_lane_sentinel call ('Companies Research Errored Sentinel', sourced from 'Research Carry Merge', universally-quantified IF-condition), and the mutual-exclusion argument recorded in the builder comment."
  - "enrichmentConvergenceMerge.test.mjs's pre-existing 'Merge Company... no research/judge need' test asserted the OLD (wrong) walker behaviour: its baseStubs() 'Claude Web Research' stub returns {} (no content array), which the graph's own 'IF Research Errored' condition correctly reads as errored under the corrected walker. Corrected the stub locally (not the shared baseStubs(), to avoid any risk to other tests) to a well-formed non-error response, matching the test's own stated intent."
  - "tests/n8n/researchErrorGateFlow.test.mjs's wiring-snapshot test (not in this plan's own files_modified list, discovered only by running the full suite) needed updating: the new sentinel adds a second, additive fan-out edge from 'Research Carry Merge' output 0, and the old assertion expected exactly one target. Fixed because the graph change is correct and intentional; the old assertion encoded 'exactly one consumer', never a real edge that moved."
  - "The D-74-03 fidelity pin against exec_12522 is two tests, not one full graph replay: reading the raw recording directly for the shape 74-CONTEXT.md cites, plus a small synthetic-batch walk (reusing ingestCreateErrorLane.test.mjs's own arming idiom) proving the walker's own prediction agrees on the three D-74-03 points. A full 46-row replay through 'Webhook Trigger' was attempted first and abandoned: the real 'Map Columns' column-mapping config depends on the webhook's own multipart envelope, not just the extracted CSV rows, and a naive per-row seed produced a genuine identity-routing divergence (the walker reached 'HubSpot Linkedin Search', which the recording shows was never called live) that is out of scope for pinning one padding rule."

requirements-completed: [D-74-03, D-74-14, D-74-12, WR-08, D-74-10]

coverage:
  - id: D1
    description: "D-74-03: propagate()'s alwaysOutputData substitution gates on outputIndex === 0 only, matching n8n's ensureAlwaysOutputData; no per-node exemption anywhere in walkWorkflow.mjs"
    requirement: D-74-03
    verification:
      - kind: unit
        ref: "tests/n8n/walkWorkflow.test.mjs#mutually-exclusive-branch case, RE-DERIVED for D-74-03: alwaysOutputData on the IF itself does NOT rescue output 1"
        status: pass
      - kind: unit
        ref: "tests/n8n/walkWorkflow.test.mjs#D-74-03: alwaysOutputData pads output index 0 only, never a later output"
        status: pass
      - kind: integration
        ref: "tests/n8n/walkerEngineFidelityV1.test.mjs#execution 12522 (ingest lane, D-74-03): the corrected walker's own prediction for this same graph agrees"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-74-03: the v1 end-of-run drain prefers the most-upstream qualifying Merge (topological preference via static connections BFS), fixing a false merge_pending_runs_undrained the padding fix alone exposed on the committed ingest graph"
    requirement: D-74-03
    verification:
      - kind: unit
        ref: "tests/n8n/ingestCreateErrorLane.test.mjs#zero-rejection batch: the response is unchanged in shape and Create Carry Merge does not starve"
        status: pass
      - kind: integration
        ref: "tests/n8n/walkerEngineFidelityV1.test.mjs#execution 12354/12355/12356 (v1, Gate 11) -- drain behaviour unaffected by the ordering preference"
        status: pass
    human_judgment: false
  - id: D3
    description: "WR-08: the stale httpStubs JSDoc sentence corrected to match the stub-normalisation code's actual (always-two-outputs) behaviour"
    requirement: WR-08
    verification:
      - kind: other
        ref: "tests/n8n/lib/walkWorkflow.mjs JSDoc, manual read-back against the code at the HTTP-node stub-normalisation site"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-74-14: 'Companies Research Errored Sentinel' closes the structural gap on the companies research-error branch (Merge Company Fan-In inputs 1/2 unfilled when every row errors), mutually exclusive with every other producer by construction"
    requirement: D-74-14
    verification:
      - kind: integration
        ref: "tests/n8n/enrichmentConvergenceMerge.test.mjs#D-74-14: a companies batch where research genuinely errors reaches Build Response once per row"
        status: pass
      - kind: unit
        ref: "tests/n8n/mergeInputContract.test.mjs (multi-producer-tolerant registry, unchanged -- input already registered)"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-74-12 (MN-01): searched exec_12522/exec_12434/exec_12449 for a Merge-named node with more than one recorded run; found none -- the todo stays open with its trigger unchanged, never closed on a resolves_phase match"
    requirement: D-74-12
    verification:
      - kind: other
        ref: "mechanical search over the three frozen fixtures' runData, this session -- see task 3 body"
        status: pass
    human_judgment: false

duration: 2h 05min
completed: 2026-09-19
status: complete
---

# Phase 74 Plan 04: Walker index-0 padding rule, enrichment research-error sentinel, exec_12522 pin Summary

**Corrected `walkWorkflow.mjs`'s always-output-data padding to gate on output index 0 (matching n8n's real `ensureAlwaysOutputData`), fixed the v1 end-of-run drain's ordering to prefer the most-upstream qualifying Merge (a second defect the padding fix exposed on the committed ingest graph), closed the enrichment lane's companies research-error structural gap with one starved-lane sentinel, and pinned the index-0 rule against live execution 12522.**

## Performance

- **Duration:** 2h 05min
- **Started:** 2026-09-19T08:31:00Z (approx)
- **Completed:** 2026-09-19
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- `propagate()`'s `alwaysOutputData` substitution now gates on `outputIndex === 0`, exactly matching the live n8n engine's `ensureAlwaysOutputData` (guards on `nodeSuccessData?.[0]?.[0]`, writes only `nodeSuccessData[0]`) — no per-node exemption anywhere.
- Found and fixed a second, independent defect the padding fix exposed: the v1 end-of-run drain's plain insertion-order scan could fire a downstream Merge before its upstream producer, using up a one-drain cap before the real delivery arrived. The drain now prefers the most-upstream qualifying Merge (static BFS over `connections`).
- Closed the enrichment lane's companies research-error structural gap (D-74-14) with one `_add_starved_lane_sentinel` call, "Companies Research Errored Sentinel" — mutually exclusive with every other producer of `Merge Company Fan-In` inputs 1/2 by construction, verified offline on all-errored, mixed, and no-error batches.
- Pinned the index-0 rule against live execution 12522 (ingest lane, zero-rejection create batch): `HubSpot Create` outs `[21, 0]`, `Create Carry Merge` drains once with 42 items, matching 74-CONTEXT.md's own citation exactly.
- Corrected the stale WR-08 JSDoc sentence in the same edit as the padding fix.
- Recorded both findings in CLAUDE.md section 13.0.3 with the two-tag `[documented]`/`[observed live]` convention.
- Searched three frozen fixtures for MN-01's open question (a Merge left with two partially-filled pending runs); found nothing — the todo stays open, untouched, per its own instructions.

## Task Commits

1. **Task 1 (RED): add failing cases for D-74-03's index-0-only AOD padding rule** — `c8e51820` (test)
2. **Task 1 (GREEN): walker pads AOD output index 0 only; fix drain order to match 12522** — `3078e744` (feat)
3. **Task 2: sentinel covers Merge Company Fan-In when every research row errors (D-74-14)** — `2810a333` (feat)
4. **Task 3: pin the index-0 rule against exec_12522; CLAUDE.md 13.0.3; MN-01 stays open** — `52b3e402` (feat)

_TDD task (Task 1): RED confirmed via `gsd-tools check tdd-red-evidence` (`RED_EVIDENCE_OK`, `target_test_failed`, 24 pass / 2 fail against the pre-fix walker) before any implementation edit. No REFACTOR commit was needed._

## Files Created/Modified

- `tests/n8n/lib/walkWorkflow.mjs` — `propagate()`'s AOD guard now gates on `outputIndex === 0`; the v1 end-of-run drain prefers the most-upstream qualifying Merge (new `staticReachable` helper, cached BFS over `connections`); corrected the WR-08 JSDoc sentence
- `tests/n8n/walkWorkflow.test.mjs` — corrected one pre-existing test that encoded the old (wrong) padding rule; two new tests for the corrected rule
- `scripts/build_cloud_workflows.py` — new `_add_starved_lane_sentinel` call, "Companies Research Errored Sentinel" (D-74-14), with its mutual-exclusion argument in the builder comment
- `n8n/wf_enrichment_cloud.json` — regenerated; node count 287 → 289 (the sentinel + its gate)
- `tests/n8n/enrichmentConvergenceMerge.test.mjs` — corrected one pre-existing test's stub (locally, not the shared `baseStubs()`); new D-74-14 test driving the research-error branch
- `tests/n8n/researchErrorGateFlow.test.mjs` — wiring-snapshot test updated for the sentinel's additive fan-out edge (discovered via full-suite run, not in this plan's own file list)
- `tests/n8n/walkerEngineFidelityV1.test.mjs` — two new tests pinning the D-74-03 rule against execution 12522 (raw-recording read + synthetic-batch walker prediction)
- `CLAUDE.md` — two new section 13.0.3 rows

## Decisions Made

See `key-decisions` in frontmatter. In short: the padding fix exposed a second, independent drain-order defect not anticipated by the plan's own text, fixed with a topological preference rather than the plan's anticipated "first-drain exemption" shape. D-74-14's real reproduced trace differs from the plan-time prediction (a different Merge, not flagged by `starvedWithData`); fixed anyway per the plan's own instruction. One pre-existing test outside this plan's declared file list (`researchErrorGateFlow.test.mjs`) needed a wiring-snapshot update, found only by running the full suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Drain-order defect exposed by the D-74-03 padding fix**
- **Found during:** Task 1, after applying the one-line padding fix and running the three ingest test files
- **Issue:** With padding no longer masking it, the v1 end-of-run drain's plain `Object.entries(mergeState)` insertion-order scan could fire `Ingest Merge Response`/`Build Association Request Merge` before their upstream producer `Create Carry Merge`, using up their one-drain cap before the real delivery arrived — a false `merge_pending_runs_undrained`. Live execution 12522 shows the real engine completing in one pass with `Create Carry Merge` draining first.
- **Fix:** The drain now prefers a qualifying Merge no OTHER qualifying, not-yet-drained Merge can reach via `connections` (static BFS, cached). `drainedOnce`'s one-run cap and `requiredInputsFor` are unchanged.
- **Files modified:** `tests/n8n/lib/walkWorkflow.mjs`
- **Verification:** `tests/n8n/ingestCreateErrorLane.test.mjs`, `ingestCarryMerge.test.mjs`, `ingestWidenedFieldsFlow.test.mjs` all green; `walkerEngineFidelityV1.test.mjs`'s 12354/12355/12356 pins unaffected.
- **Committed in:** `3078e744` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] `researchErrorGateFlow.test.mjs`'s wiring-snapshot assertion stale after the D-74-14 sentinel landed**
- **Found during:** Task 2, running the full node suite after regenerating the enrichment graph
- **Issue:** `assert.deepEqual(targetsOf(wf, "Research Carry Merge", 0), ["IF Research Errored"])` broke because the new sentinel adds a second, additive fan-out edge from the same output.
- **Fix:** Updated the assertion to expect both targets, with a comment explaining the addition is intentional.
- **Files modified:** `tests/n8n/researchErrorGateFlow.test.mjs`
- **Verification:** `node --test tests/n8n/*.test.mjs` green (1308/0 at that point).
- **Committed in:** `2810a333` (Task 2 commit)

**3. [Rule 1 - Bug] `enrichmentConvergenceMerge.test.mjs`'s pre-existing "Merge Company... no research/judge need" test asserted the old (wrong) walker behaviour**
- **Found during:** Task 2, running the exact `<verify>` command
- **Issue:** `baseStubs()`'s `Claude Web Research` stub returns `{}` (no `content` array), which the graph's own `IF Research Errored` condition correctly reads as errored under the corrected walker — the old walker's whichever-branch-is-empty padding used to mask this.
- **Fix:** Overrode the stub locally within the one test (not the shared `baseStubs()`, to avoid risk to other tests) with a well-formed non-error response, matching the test's own stated intent.
- **Files modified:** `tests/n8n/enrichmentConvergenceMerge.test.mjs`
- **Verification:** Task 2's exact `<verify>` command green.
- **Committed in:** `2810a333` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs exposed by the plan's own intentional changes, not scope creep). **Impact:** all three were necessary for the full suite to stay green after intentional, correct behaviour changes; none touches a locked CONTEXT.md decision.

## Issues Encountered

A full 46-row graph replay of execution 12522 through "Webhook Trigger" (attempting to mirror `walkerEngineFidelityV1.test.mjs`'s existing enrichment-lane reproduction idiom exactly) was attempted and abandoned during Task 3: seeding the walker with the recording's raw extracted CSV rows produced a genuine identity-routing divergence — the walker reached "HubSpot Linkedin Search" (a node the live recording never called, 0 recorded runs), because the real "Map Columns" node's column-mapping behaviour depends on the request's own multipart envelope fields, not just the extracted rows, and bypassing "Webhook Trigger" loses that context. Resolved by pinning against the raw recording directly (no walk needed for that half) plus a small synthetic-batch walk proving the walker's own prediction agrees on the specific D-74-03 points — the acceptance criteria's actual requirement, not a full replay.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- 74-05-PLAN.md (wave 3, depends on 74-04) is unblocked: the corrected walker and its topological drain-order preference are now the ground truth every later graph proof in this phase rests on, including 74-05's own create-error lane changes (D-74-01/02/04/05/06).
- 74-06-PLAN.md (wave 4, the end-of-phase live gate) can proceed once 74-05 lands; nothing in this plan changed `n8n/wf_contact_ingest_cloud.json`, so 74-05's own graph work starts from an unchanged ingest lane.
- The MN-01 question (does the engine drain a second pending Merge run at end of run?) remains genuinely open — no recording in this repo shows the shape. NF-MJ-01, the todo's other open question, was out of this task's search scope and remains unresolved too.
- Full test baseline confirmed green at plan close: `node --test tests/n8n/*.test.mjs` → 1310 pass / 0 fail (was 1305/0 at plan start). `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → 5164 passed / 160 skipped (unchanged — no Python file touched).
- `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` exits 0 (idempotent); only `n8n/wf_enrichment_cloud.json` changed among generated workflows; node count 287 → 289.
- Zero n8n executions consumed; nothing deployed.

## Node counts

`n8n/wf_enrichment_cloud.json`: **287 → 289** (the D-74-14 sentinel + its gate — `_add_starved_lane_sentinel`'s standard two-node shape). No other committed workflow changed.

## MN-01 verdict

**Not resolved.** Searched `exec_12522.runData.json`, `exec_12434.runData.json` and `exec_12449.runData.json` for any node whose name contains "Merge" with more than one recorded run in the raw runData. Found none in any of the three fixtures — the expected outcome per 74-CONTEXT.md's own plan-time probe. `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` is left open, untouched, trigger line byte-identical. The MN-01 drain cap (`drainedOnce`, one drain per Merge) did **not** need adjustment against the frozen fixture — the walker's existing model already correctly represents `Create Carry Merge`'s single end-of-run drain run on 12522 (confirmed by the fidelity test in Task 3); the only change the drain needed was the *ordering* preference (Task 1), not the cap itself.

## Self-Check: PASSED

- `[ -f tests/n8n/lib/walkWorkflow.mjs ]` → FOUND
- `[ -f n8n/wf_enrichment_cloud.json ]` → FOUND
- `[ -f tests/n8n/walkerEngineFidelityV1.test.mjs ]` → FOUND
- `git log --oneline --all | grep -q c8e51820` → FOUND
- `git log --oneline --all | grep -q 3078e744` → FOUND
- `git log --oneline --all | grep -q 2810a333` → FOUND
- `git log --oneline --all | grep -q 52b3e402` → FOUND
- `node --test tests/n8n/*.test.mjs` → 1310 pass / 0 fail
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → 5164 passed / 160 skipped

---
*Phase: 74-code-review-follow-ups-from-phase-73*
*Completed: 2026-09-19*
