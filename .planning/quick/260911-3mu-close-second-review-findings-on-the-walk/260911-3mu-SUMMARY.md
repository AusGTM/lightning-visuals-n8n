---
quick_id: 260911-3mu
type: execute
status: complete
subsystem: n8n-tests
tags: [walker, v1, starvation-detector, review-closure]
commits: [dbb987e5, <docs commit>]
completed: 2026-09-11
---

# Quick task 260911-3mu — summary

Closed every finding of the 260911-1z5 second-pass review except NF-MN-06 (accepted, see the
PLAN) and NF-NT-07 (process: SUMMARY committed by the orchestrator, this file).

| Finding | Closed at | Test that goes RED on regression |
|---|---|---|
| NF-BL-01 annihilation blind spot | `walkWorkflow.mjs` `starvedWithData` annihilation arm; `outputCount` on both fire sites | `walkWorkflow.test.mjs` "NF-BL-01: a combine/combineByPosition Merge fired with an unfilled input ANNIHILATES…" — RED against `7f573285` (observed: `starvedWithData` `[]`), GREEN after |
| NF-MJ-01 grouping rule overclaimed | comment demoted; todo appended | "NF-MJ-01 (KNOWN-UNOBSERVED, pinned)" pins the current choice |
| NF-MJ-02 CLAUDE.md claim without a test | `walkerEngineFidelityV1.test.mjs` asserts `merge_fired_with_unfilled_input` run 1 on each recording and `starvedWithData` empty | that assertion |
| NF-MN-01 near-empty convergence tests | never-delivered snapshot + fired-unfilled list + `Build Response` row count | those assertions |
| NF-MN-02 guard message | `recordV1Fire(name, site)` | existing MN-02 test still matches |
| NF-MN-03 five stale messages | reworded; per-node fire claims on `runData`/`ran()` | — |
| NF-MN-04 digest message | reworded | — |
| NF-MN-05 MJ-01 uncovered | "NF-MN-05 (MJ-01 coverage)" case | that case |
| NF-NT-01/02 | documented in `starvedWithData` | — |
| NF-NT-03 | two `fired === true` → `runData.Merge.length === 1` | — |
| NF-NT-04 Merge-free cycle hang | delivery cap in `processQueue` | "NF-NT-04" case (the old walker OOMs on it — that is its RED) |
| NF-NT-05 README pointer | fixed | — |
| NF-NT-08 CHANGELOG count | 14 → 12 | — |

Suites: `node --test tests/n8n/*.test.mjs` 1098 pass / 0 fail (1093 + 5 new). Python suites
re-run by the orchestrator before push.
