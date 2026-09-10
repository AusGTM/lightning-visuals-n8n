---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 15
subsystem: infra
tags: [n8n, documentation, deployment-record, gap-closure, runbook]

requires:
  - phase: 70-one-merge-one-result-channel-n8n-runtime-truth
    provides: "70-13's node counts (291->287, zero executeWorkflow) and 70-14's marker filter / execution-12316 divergence pin, both needed as source facts for this plan's records"
provides:
  - "CLAUDE.md §13.0.2/§13.0.3: scale_up marked RETIRED with execution ids, request-flag count corrected to two, deployment-parity note reflecting the mixed five-workflow live state after the 2026-09-10 runaway, three new observed-live platform-fact rows"
  - "A standing two-minute mode: integrated burst watch, written as Step 6 of 70-ROLLBACK-RUNBOOK.md and stated to apply to every deploy in this repo"
  - "Gates 7, 8 and 9 in 70-DEFERRED-GATES.md — the phase-closing operator gates, in order, with Gate 6 marked superseded"
affects: [Gate 7/8/9 (operator, next deploy), any future plan touching n8n deploy tooling or CLAUDE.md §13.0]

actuals:
  tokens: 12013
  tasks: 3
  commits: 3
  plan_head_before: 1171cfcdacd54fa25e2d5b628fb7ea7af378e7c3

tech-stack:
  added: []
  patterns:
    - "A retired request-level flag's table row stays, marked RETIRED with its date and execution ids, rather than deleted — precedent from async_ack, reused for scale_up"
    - "A standing safety step (the burst watch) is written once into the most detailed existing runbook and declared universal, rather than duplicated across every deploy doc"
    - "A superseded gate is marked at its own heading and referenced, never deleted or duplicated, when its replacement changes only the target body and the precondition"

key-files:
  created: []
  modified:
    - CLAUDE.md
    - CHANGELOG.md
    - n8n/README.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md

key-decisions:
  - "The scale_up table row in CLAUDE.md §13.0.2 stays rather than being deleted, following the exact precedent that section already set for async_ack -- a reader who meets the name in old code finds the answer."
  - "Gate 8's runData-source-vs-declared-connections check reuses tests/n8n/walkerEngineFidelity.test.mjs's declaredProducersOf pattern rather than inventing a new comparison mechanism, and is scoped to a one-off script an operator writes at gate time, not a new committed tool."
  - "Gate 6 is kept verbatim in the file (not deleted) with a SUPERSEDED banner at its own heading, and Gate 9 references its steps with two named substitutions rather than duplicating them -- per the plan's explicit prohibition on duplicating Gate 6's text."
  - "The 'one execution errored and was never examined' fact in Gate 8 is stated precisely as what is verifiable from 70-RUNTIME-VERDICT.json: the send-level settled:true covers only the primary execution id, while additional executions matched by run_id echo (the runaway children) were never individually checked, and the runaway's own tail (12346-12348) is independently known to have errored -- not a claim about which specific matched execution failed."
  - "n8n/README.md's giant as-built mermaid diagram (already disclaimed as stale since 2026-08-10, predating even Phase 61) was not redrawn. Only the 'Currency of this file' prose section was corrected to name the deleted lane and the corrected flag count -- redrawing 287 nodes of mermaid is out of scope for a retirement-bookkeeping plan and the file already directs readers to the committed JSON as authority."

patterns-established:
  - "A platform incident gets three things recorded, not one: the retirement (what no longer exists), the observed-live facts (what was learned, cause isolated or not), and a standing detector (what makes the next occurrence cheap to catch)."

requirements-completed: [D-70-24, D-70-27]

coverage:
  - id: D1
    description: "CLAUDE.md's request-level flags section records scale_up as RETIRED with the execution ids that retired it (12211-12348), and the flag count is corrected from three to two everywhere it appears in §13.0.2, including the fan-out node list (which now says which of the nine Phase-61 additions no longer exist) and the node-count table (291->287 per 70-13's measurement)."
    requirement: "D-70-24"
    verification:
      - kind: other
        ref: "/usr/bin/grep -q '12316' CLAUDE.md && /usr/bin/grep -q '12348' CLAUDE.md && /usr/bin/grep -q 'observed live' CLAUDE.md"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m pytest -q --tb=short (4700 passed, 154 skipped)"
        status: pass
    human_judgment: false
  - id: D2
    description: "§13.0.3 gains exactly three new observed-live rows, each citing execution ids: the deactivation drain lag with the erroring tail, the unconnected-source node run (execution 12316, cause explicitly NOT isolated), and the runaway's scale (135 children, 138 total executions). A note states no Merge-behaviour row was touched this round."
    requirement: "D-70-24"
    verification:
      - kind: manual_procedural
        ref: "Read CLAUDE.md CLAUDE.md#13.0.3 -- three new rows present, the unconnected-node row states cause NOT isolated, the no-Merge-upgrade note is adjacent to the table"
        status: pass
    human_judgment: false
  - id: D3
    description: "The deployment-parity note in CLAUDE.md §13.0.2 states the truth as of this round: the live enrichment lane is the pre-Phase-70 59812be body restored 2026-09-10, the other four are the gap-closure JSON, and the committed JSON is ahead of live on all five to varying degrees."
    requirement: "D-70-24"
    verification:
      - kind: manual_procedural
        ref: "Read CLAUDE.md's 'Extended 2026-09-10 (Gate 4/Gate 5 deploy attempt...)' addendum -- five-row live-vs-committed table present, nothing-armed statement present"
        status: pass
    human_judgment: false
  - id: D4
    description: "70-ROLLBACK-RUNBOOK.md carries a two-minute mode: integrated burst watch as Step 6, between the mandatory bounce/read-back (Step 5) and the working-tree restore (renumbered Step 7), with a followable stop procedure (deactivate first, observed ~30s drain lag, erroring tail, then a previous-body PUT) and an explicit statement that it applies to every deploy in this repo."
    requirement: "D-70-27"
    verification:
      - kind: other
        ref: "/usr/bin/grep -q 'deactivate' 70-ROLLBACK-RUNBOOK.md && /usr/bin/grep -q '12348' 70-ROLLBACK-RUNBOOK.md && /usr/bin/grep -q 'mode: integrated' 70-ROLLBACK-RUNBOOK.md && /usr/bin/grep -q '^## Step 8' 70-ROLLBACK-RUNBOOK.md && ! /usr/bin/grep -q '^## Step 9' 70-ROLLBACK-RUNBOOK.md"
        status: pass
    human_judgment: false
  - id: D5
    description: "70-DEFERRED-GATES.md carries Gates 7, 8 and 9 in order, in the file's existing shape (what it proves, risk accepted, operator steps, sign-off criteria), with the earlier armed gate (Gate 6) marked superseded at its own heading and Gate 9 referencing its steps rather than duplicating them. A single ordering rule covers all three: 7 before 8, 8 before 9, nothing armed until 8 passes."
    requirement: "D-70-27"
    verification:
      - kind: other
        ref: "/usr/bin/grep -q '^## Gate 7' 70-DEFERRED-GATES.md && /usr/bin/grep -q '^## Gate 8' 70-DEFERRED-GATES.md && /usr/bin/grep -q '^## Gate 9' 70-DEFERRED-GATES.md && ! /usr/bin/grep -q '^## Gate 10' 70-DEFERRED-GATES.md"
        status: pass
      - kind: manual_procedural
        ref: "Operator reads Gates 7, 8, 9 and confirms each is followable: exact commands/files named, unambiguous pass conditions, no step asks to arm before the disarmed proof passes"
        status: unknown
    human_judgment: true
    rationale: "The plan's own <verify> for Task 3 names a <human-check> item (operator confirms the gates are followable without guessing) that no offline check can substitute for -- this is exactly the kind of judgment call the plan's own verify block reserves for a human."

duration: 9 min
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 15: Gap Closure Round 2 — Retirement, Platform Facts, Standing Detector, Deferred Gates Summary

**CLAUDE.md now records `scale_up` as RETIRED (not disabled) with the execution ids that retired it, three new observed-live platform facts from the 2026-09-10 runaway (one explicitly cause-not-isolated), and a corrected five-workflow deployment-parity note; the rollback runbook gained a standing two-minute burst watch before every deploy's first send; and 70-DEFERRED-GATES.md now carries Gates 7, 8 and 9 — the three ordered, disarmed-before-armed gates that close the phase — with the superseded Gate 6 pointing at its replacement.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-10T08:37:48Z
- **Completed:** 2026-09-10T08:47:11Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- CLAUDE.md §13.0.2: the `scale_up` request-level flag is marked RETIRED (2026-09-10, executions `12211`-`12348`), the "THREE, not four" heading and count corrected to "TWO, not three," the original Phase-61 fan-out node list corrected to name which four of nine additions no longer exist, the node-count table updated to 70-13's measured `291 -> 287`, and a new dated addendum records the actual live state: five workflows on three different generations, the enrichment lane a full architecture-generation behind (pre-Phase-70 body, zero Merge nodes) while the other four run the gap-closure JSON.
- CLAUDE.md §13.0.3 gains exactly three new `[observed live]` rows, each with execution ids: deactivation stops further self-dispatch after a ~30s drain lag with the tail erroring; a node (`Dispatch Self`, execution `12316`) ran with an item no declared connection delivered — cause explicitly NOT isolated, distinguished from the retirement (which removed the node, not the explanation); and the runaway's scale (135 children in six minutes, 138 total executions against the Starter budget). A note states plainly that no Merge-behaviour row was touched this round.
- `n8n/README.md`'s currency section and `CHANGELOG.md` record the same removal, the row-level refusal, the `assert_no_self_dispatch` generation-time assertion, the `D-70-25` marker filter, and the recorded facts — the "Not yet done" section corrected to describe the actual mixed five-workflow live state rather than the single-generation state it previously assumed.
- `70-ROLLBACK-RUNBOOK.md` gained Step 6: a two-minute watch of the enrichment workflow's executions list for `mode: integrated` entries, run with nothing sent, zero-new-execution pass condition, explicitly declared to apply to every deploy in this repo. The stop procedure (deactivate first, observed drain lag, erroring tail, then a previous-body PUT) is recorded verbatim from what worked on 2026-09-10. Two stale step-number cross-references elsewhere in the file were corrected for the renumbering.
- `70-DEFERRED-GATES.md` gained Gates 7 (disarmed deploy + bounce + burst watch, nothing sent), 8 (the D-70-19 proof re-run, all four sends required `shapes_equal: true`, plus a new runData-source-vs-declared-connections check, plus the stated fact that Gate 5 recovered no row carrying a row id on the enrichment lane), and 9 (the armed mixed-verdict re-run, referencing Gate 6's steps with two named substitutions rather than duplicating them). Gate 6 is marked SUPERSEDED at its own heading and in the historical ordering-rule section. One ordering rule covers all three: 7 before 8, 8 before 9, nothing armed until 8 passes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Record the retirement and the facts the runaway bought** - `60c3660` (docs)
2. **Task 2: Make the burst watch a standing deploy step** - `95f7358` (docs)
3. **Task 3: Record Gates 7, 8 and 9 for the operator, and supersede Gate 6** - `d9e5c07` (docs)

**Plan metadata:** this file's own commit (docs: complete plan)

_Note: this is a docs-only plan; every commit carries the same `docs(70-15):` type — no code, no tests to add._

## Files Created/Modified
- `CLAUDE.md` - §13.0.2 retirement, corrected flag count/node list/node-count table, corrected deployment-parity addendum; §13.0.3 three new observed-live rows plus a no-Merge-upgrade note
- `CHANGELOG.md` - Removed section corrected (three flags remained at the time -> two now, with the scale_up retirement entry), Fixed section gains the gap-closure round-2 entry, Not yet done corrected to the mixed five-workflow live state
- `n8n/README.md` - Currency-of-this-file section corrected to name the deleted lane, the corrected flag count, and the current live-vs-committed state for the enrichment lane specifically
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md` - new Step 6 (the burst watch), renumbered Steps 7-8, two stale cross-references corrected
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md` - Gate 6 marked SUPERSEDED, Gates 7/8/9 appended, a unified ordering rule for the three new gates

## Decisions Made
See `key-decisions` in frontmatter. The two decisions most likely to matter to a future reader: the scale_up table row stays (marked RETIRED) rather than being deleted, following the section's own async_ack precedent; and Gate 8's new connections-check step reuses the existing `declaredProducersOf` pattern from `tests/n8n/walkerEngineFidelity.test.mjs` rather than inventing new tooling, since this is documentation for a future operator run, not a committed script this plan's `files_modified` scoped in.

## Deviations from Plan

None - plan executed exactly as written. One minor authoring correction is worth recording under Issues Encountered below (not a deviation from the plan's substance): the first `git commit` attempt for Task 3 failed on a shell quoting error (heredoc inside the Bash tool's own command wrapping), with nothing partially committed; re-issued via `git commit -F <scratch file>` and succeeded identically.

## Issues Encountered
- The Task 3 commit message (the longest of the three, with nested backtick-quoted terms like `mode: integrated`) failed on first attempt with a bash "unexpected EOF" error from the heredoc-in-heredoc construction. `git status --short` confirmed nothing was staged-and-lost; the message was written to a scratch file and committed with `git commit -F`, which succeeded on the first try with identical content. No files were affected.

## User Setup Required
None - no external service configuration required. Everything in this plan is documentation; Gates 7, 8 and 9 are the operator's own future steps, not something this plan performs.

## Next Phase Readiness
- The phase's three remaining live gates (7, 8, 9) are fully specified, in order, with an unambiguous ordering rule and no step that arms anything before Gate 8 passes.
- CLAUDE.md and the CHANGELOG are internally consistent with 70-13's and 70-14's actual node counts and with the live state as observed during the 2026-09-10 incident — a future agent reading either file gets the corrected picture, not the pre-incident one.
- The burst watch is now a standing, citable runbook step; any future deploy plan in this repo can point at `70-ROLLBACK-RUNBOOK.md` Step 6 rather than re-deriving the procedure.
- Nothing deployed, bounced, armed or sent by this plan or any prior plan in this phase. The live instance remains exactly as the 2026-09-10 incident left it: enrichment on the pre-Phase-70 `59812be` body (123 nodes), the other four workflows on the gap-closure round-1 JSON (69/55/43/30). Gate 7 is the next operator action.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*

## Self-Check: PASSED

- `CLAUDE.md` — FOUND
- `CHANGELOG.md` — FOUND
- `n8n/README.md` — FOUND
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md` — FOUND
- `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md` — FOUND
- Commits `60c3660`, `95f7358`, `d9e5c07` — all FOUND in `git log`
- Measured commit count from `${PLAN_HEAD_BEFORE}..HEAD` = **3** (base `1171cfcdacd54fa25e2d5b628fb7ea7af378e7c3`)
- All Task 1, Task 2 and Task 3 acceptance-criteria grep checks re-run and PASS
- `.venv/bin/python -m pytest -q --tb=short` — 4700 passed, 154 skipped (unchanged from pre-plan baseline)
