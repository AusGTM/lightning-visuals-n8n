---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 18
subsystem: infra
tags: [n8n, executionOrder, documentation, deferred-gates, G-70-6, D-70-28, D-70-31]

# Dependency graph
requires:
  - phase: 70 (plan 16)
    provides: "settings.executionOrder = v1 on every generated body, generation-time refusal on non-v1 (D-70-28)"
  - phase: 70 (plan 17)
    provides: "both live-write paths pinned to preserve v1 (D-70-29), the bounce read-back column, and the proof driver's execution_order_all_v1 verdict field"
provides:
  - "CLAUDE.md §13.0.3: two source-cited [documented] rows for n8n's legacy addEmptyItem push and the v1 requiredInputs contract, one [observed live] row for Gate 8's reproduction (executions 12349-12353), and the two pre-existing Merge rows annotated as legacy-order-only observations"
  - "CLAUDE.md §13.0.2: the stale post-runaway live-state table corrected to what Gate 7/Gate 8/the rollback actually left running — all five workflows on the pre-Phase-70 59812be bundle, plus the round-3 v1-flip note"
  - "70-DEFERRED-GATES.md: Gates 10, 11 and 12 written up in the Gate 7/8/9 shape; Gate 9 marked superseded by Gate 12"
  - "70-ROLLBACK-RUNBOOK.md: Step 5's read-back now reports settings.executionOrder and distinguishes the expected reading after a v1 deploy from the expected reading after a rollback"
  - "70-UAT.md: the paused-testing line and the G-70-6 gap block record what closed offline (D-70-28/29/30) and what remains live (Gates 10/11/12), status field unchanged"
affects: ["Gate 10/11/12 (operator, next live session)"]

actuals:
  tokens: 10636
  tasks: 3
  commits: 3
  plan_head_before: 193960cc61c74b258ca394276c5382c5e04a03b9

tech-stack:
  added: []
  patterns:
    - "Table-row annotation instead of row deletion: a claim's observed SCOPE can narrow (legacy-order-only) without losing the claim or its execution ids — the tagging discipline applies to precision, not just presence."
    - "A gate written up before it can be run: Gates 10/11/12 exist as complete operator procedures with no live observation behind any of their v1 claims yet, each tagged accordingly in the adjacent platform-facts table."

key-files:
  created: []
  modified:
    - CLAUDE.md
    - CHANGELOG.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/deferred-items.md

key-decisions:
  - "n8n/README.md needed no change — grepped for any execution-order or settings-content statement and found none; left untouched rather than adding a paragraph for symmetry, per the plan's explicit instruction."
  - "The two documented rows initially failed their own verify grep (addEmptyItem.*\\[documented\\]) because the symbol was cited only in the Basis cell, after the tag, not before it on the line. Fixed by also naming addNodeToBeExecuted's addEmptyItem branch in the Fact cell, so the symbol appears before [documented] as the anchor requires. requiredInputs passed on the first attempt because it was already named in the Fact cell."
  - "CLAUDE.md §13.0.2's stale 'three different generations' table was CORRECTED in place rather than appended-to, per the plan's key_link — the table's own rows now read the Gate 8 rollback's actual outcome (all five on 59812be), with the round-3 v1-flip note added as a new paragraph after it, not folded into the same table."
  - "ROADMAP.md's existing 'Gap closure, round 3' bullets for 70-16 and 70-17 were checked against their SUMMARYs (execution_order_all_v1 spelling, node-count claims, PUT-pin claims) and left untouched — nothing diverged from what was actually built, so no edit was made, satisfying the plan's 'if nothing diverged, leave the roadmap untouched' instruction."
  - "Gates 10/11/12 were appended at the very end of 70-DEFERRED-GATES.md, after the pre-existing 'Ordering rule for Gates 7, 8 and 9' section, rather than spliced in before it — keeps the historical 7/8/9 narrative (including its own ordering-rule trailer) intact and the new 10/11/12 material as a clearly separate, later block with its own ordering-rule trailer."

requirements-completed: [D-70-31]

coverage:
  - id: D1
    description: "CLAUDE.md §13.0.3 gains two source-cited [documented] rows (addEmptyItem legacy push, v1 requiredInputs contract) and one [observed live] row for Gate 8 (executions 12349-12353); the two pre-existing Merge rows are annotated as legacy-order-only, neither deleted"
    requirement: "D-70-31"
    verification:
      - kind: other
        ref: "/usr/bin/grep -c 'addEmptyItem.*\\[documented\\]' CLAUDE.md (1), 'requiredInputs.*\\[documented\\]' CLAUDE.md (1), '12349' CLAUDE.md (3), '12353' CLAUDE.md (3), awk line count (4306, up from 4285), '^### 13.0' count (3)"
        status: pass
    human_judgment: true
    rationale: "The plan's own acceptance criteria require a manual read of the finished table to confirm no row claims v1 has been observed live — no negative regex can safely distinguish a correctly-scoped row from an upgraded one. Performed during execution (see task narrative); still routed to human_judgment per the plan's own instruction that this check is deliberately manual."
  - id: D2
    description: "CLAUDE.md §13.0.2's stale post-runaway live-state table is corrected to the actual current state (all five workflows on the pre-Phase-70 59812be bundle) plus the round-3 v1-flip note"
    requirement: "D-70-31"
    verification:
      - kind: other
        ref: "manual diff read against 70-UAT.md Test 7/Test 8 records and 70-CONTEXT.md's Gap-closure round 3 decisions block"
        status: pass
    human_judgment: false
  - id: D3
    description: "Gates 10, 11 and 12 exist in 70-DEFERRED-GATES.md in the Gate 7/8/9 shape; Gate 11 inverts Gate 8's execution-order expectation and retains its runData-source-vs-declared-connections check; Gate 12 points at Gate 6 with named substitutions; Gate 9 marked superseded; Gates 7/8 untouched"
    requirement: "D-70-31"
    verification:
      - kind: other
        ref: "/usr/bin/grep -c '^## Gate 10\\|^## Gate 11\\|^## Gate 12' (3), 'execution_order_all_v1' (4), 'declaredProducersOf' (2), superseded count (6), '^## Gate 7 \\|^## Gate 8 ' count (2, unchanged)"
        status: pass
    human_judgment: false
  - id: D4
    description: "70-ROLLBACK-RUNBOOK.md's read-back reports execution order alongside node counts and write flags, distinguishing the expected post-v1-deploy reading from the expected post-rollback reading"
    requirement: "D-70-31"
    verification:
      - kind: other
        ref: "/usr/bin/grep -ci 'executionOrder\\|execution order' 70-ROLLBACK-RUNBOOK.md (2)"
        status: pass
    human_judgment: false
  - id: D5
    description: "ROADMAP.md and 70-UAT.md bookkeeping updated to name what round 3 closed offline and what Gates 10/11/12 remain; 70-CONTEXT.md untouched; no gap or requirement marked complete"
    requirement: "D-70-31"
    verification:
      - kind: other
        ref: "/usr/bin/grep -c '70-16-PLAN.md\\|70-17-PLAN.md\\|70-18-PLAN.md' ROADMAP.md (3), 'Gap closure, round 3' (1), 'D-70-28' (1), 'Gate 1[012]' 70-UAT.md (5), git status --porcelain on 70-CONTEXT.md (empty), 'status: failed' 70-UAT.md (1, unchanged)"
        status: pass
    human_judgment: false

# Metrics
duration: 70min
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 18: Gap-closure round 3 bookkeeping — the v1 rule on record, Gates 10/11/12 written up Summary

**Recorded the v1 execution-order engine rule with source citations in CLAUDE.md, corrected the stale post-runaway live-state table, and wrote up the three live gates (10, 11, 12) that alone can close G-70-6 — nothing deployed, bounced, or armed.**

## Performance

- **Duration:** 70 min
- **Started:** 2026-09-10T10:31:48Z (approx, dispatch time)
- **Completed:** 2026-09-10T11:41:48Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- CLAUDE.md §13.0.3 gains two `[documented]` rows citing `packages/core/src/execution-engine/workflow-execute.ts`'s `addNodeToBeExecuted`/`addEmptyItem` branch (the legacy empty-item push) and `packages/nodes-base/nodes/Merge/v3/actions/versionDescription.ts`'s `requiredInputs` (the v1 contract), plus one `[observed live]` row for Gate 8's reproduction of the legacy push (executions `12349`-`12353`). The two pre-existing Merge-behaviour rows are annotated as observed under the legacy order only, neither deleted nor stripped of their execution ids.
- CLAUDE.md §13.0.2's "three different generations" live-state table — stale since it described the state between the 2026-09-10 runaway stop and Gate 7's redeploy — is corrected in place to what actually happened next: Gate 7 passed, Gate 8 failed on the enrichment lane, and the operator rolled all five workflows back to the pre-Phase-70 `59812be` bundle. A new paragraph records this round's v1 flip (node counts unchanged) and names Gate 10 as the pending redeploy.
- Three new gate sections — Gate 10 (disarmed v1 deploy + bounce + burst watch), Gate 11 (the D-70-19 proof re-run under v1, inverting Gate 8's execution-order expectation while retaining its runData-source-vs-declared-connections check verbatim), Gate 12 (the armed mixed-verdict re-run, pointed at Gate 6's steps with named substitutions) — written into `70-DEFERRED-GATES.md` in the established Gate 7/8/9 shape. Gate 9 is marked superseded by Gate 12; Gates 7 and 8 are untouched.
- `70-ROLLBACK-RUNBOOK.md`'s Step 5 read-back now reports `settings.executionOrder`, with an explicit note that a null/absent reading is the CORRECT outcome of this specific rollback (it predates the flip) but a FAILURE after a Gate 10 v1 deploy.
- `70-UAT.md`'s paused-testing line and the G-70-6 gap block record what closed offline (D-70-28/29/30) and what remains (Gates 10/11/12) without touching the gap's `status: failed` field. `deferred-items.md` records the two deliberately unmodelled v1 walker rules (the end-of-run Merge drain, and whether a zero-item Code output is a delivery under v1) so they read as intentional, not an oversight.

## Task Commits

Each task was committed atomically:

1. **Task 1: the platform-facts table records the engine rule, and the deployment note stops being stale** - `317759e` (docs)
2. **Task 2: Gates 10, 11 and 12 written up; Gate 9 superseded; the runbook read-back gains the order** - `6ac57f7` (docs)
3. **Task 3: the roadmap and the UAT record say what this round closed and what it did not** - `08ce454` (docs)

## Files Created/Modified
- `CLAUDE.md` - §13.0.3 gains two documented rows + one observed-live row + two annotated Merge rows; §13.0.2's stale live-state table corrected and extended with the round-3 v1-flip note
- `CHANGELOG.md` - new entry documenting the v1 flip, the PUT-path pins, the walker's legacy refusal, and the outstanding Gates 10/11/12; the stale "Not yet done" bullet corrected to name Gate 7 pass / Gate 8 fail / rollback
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md` - Gate 9 marked superseded; Gates 10, 11, 12 appended with their own ordering-rule trailer
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md` - Step 5 read-back gains the execution-order fact and its two expected-reading cases
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md` - paused-testing line and G-70-6 gap block updated (offline_closure field added, missing list rewritten to name Gates 10/11/12); status field unchanged
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/deferred-items.md` - new entry for the two deliberately unmodelled v1 walker rules

## Decisions Made
See `key-decisions` in frontmatter — n8n/README.md left untouched (no relevant content found), the documented-row verify anchor required naming the symbol in the Fact cell (not only the Basis cell), CLAUDE.md §13.0.2's table corrected in place per the plan's key_link, ROADMAP.md bullets left untouched after confirming no divergence, and Gates 10/11/12 appended after the existing Gate 7/8/9 ordering-rule section rather than spliced before it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed the documented-row verify anchor for the `addEmptyItem` row**
- **Found during:** Task 1, self-check of the automated `<verify>` commands
- **Issue:** The row's first draft cited `addEmptyItem` only in the Basis cell (after the `[documented]` tag), so the anchor `addEmptyItem.*\[documented\]` — which requires the symbol to appear BEFORE the tag on the same line — returned 0 instead of 1.
- **Fix:** Added the symbol name to the Fact cell text ("via `addNodeToBeExecuted`'s `addEmptyItem` branch") so it appears before `[documented]` as the plan's verify anchor requires.
- **Files modified:** CLAUDE.md
- **Verification:** `/usr/bin/grep -c 'addEmptyItem.*\[documented\]' CLAUDE.md` now returns 1
- **Committed in:** `317759e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Caught by the plan's own automated verify step before the task commit; no scope creep, no functional change beyond correcting the row's own wording to satisfy the acceptance criterion it was written to meet.

## Issues Encountered
- Two `git commit -m "$(cat <<'EOF' ... EOF)"` heredoc invocations failed with a shell parse error (`unexpected EOF while looking for matching \`'\``) despite quoted heredoc delimiters. Root cause not fully isolated; worked around by writing the commit message to a scratchpad file and using `git commit -F <file>` for both affected commits (Tasks 2 and 3). No commit content was lost or altered by the workaround.
- The commit-ledger sentinel (`gsd-plan-head-before-70-18`) was created after Task 1's commit rather than before it, so its initial content pointed at the post-Task-1 HEAD instead of the dispatch-time HEAD. Corrected by hand to the dispatch HEAD (`193960c`, taken from the sequential-execution context in the prompt) before computing `commits:` for this SUMMARY — `git rev-list --count` against the corrected base reads `3`, matching the three task commits actually made.

## User Setup Required

None - no external service configuration required. Nothing was deployed, bounced, armed, or sent — this is a docs-only plan; all six changed files are CLAUDE.md, CHANGELOG.md, and planning-phase Markdown.

## Next Phase Readiness
- Gates 10, 11 and 12 are written up precisely enough for the operator to run them without interpretation, per this plan's own success criteria. All three remain unexercised — nothing about v1 execution order has been observed live yet.
- G-70-6 (`70-UAT.md`) stays `status: failed`; it is not closed until Gate 11 observes `execution_order_all_v1: true` live. No requirement or gap was marked complete by this plan.
- Blocker for the phase to actually close: the operator must run Gate 10 → Gate 11 → Gate 12 in order, per the standing back-loaded-live-gates ruling (2026-09-09).

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED

- Files created: none claimed as created (all six are modifications to pre-existing files) — `[ -f ]` confirmed for all six: `CLAUDE.md`, `CHANGELOG.md`, `70-DEFERRED-GATES.md`, `70-ROLLBACK-RUNBOOK.md`, `70-UAT.md`, `deferred-items.md`.
- `git log --oneline --all --grep="70-18"` returns 3 commits (`317759e`, `6ac57f7`, `08ce454`), matching the three task commits recorded above.
- All plan-level `<verify>` automated checks re-run clean at time of this SUMMARY (see coverage block `ref` fields for each result).
- Plan-level `<verification>` bullets confirmed: two documented rows + one observed-live row + two annotated Merge rows present; no observed-live v1 claim anywhere (manual read); §13.0.2 corrected; Gates 10/11/12 present in shape with Gate 11's inversion and retained check; Gate 9 superseded; Gates 7/8 untouched; rollback runbook reads back execution order; roadmap/UAT bookkeeping updated; 70-CONTEXT.md untouched; nothing deployed/bounced/armed/sent.
