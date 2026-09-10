---
quick_id: 260911-0tz
type: execute
status: complete
subsystem: n8n-tests
tags: [walker, v1, execution-order, merge-semantics, tdd, fidelity]

requires:
  - tests/n8n/lib/walkWorkflow.mjs (the pre-existing legacy-only D-70-30 model)
  - tests/n8n/fixtures/frozen/exec_1235{4,5,6}.runData.json (Gate 11 v1 recordings)
  - tests/n8n/v1RuntimeRecordings.test.mjs (the reader-only pin these recordings already had)
  - n8n/wf_enrichment_cloud.json (frozen for this task, unmodified by it)
provides:
  - "walkWorkflow.mjs: two explicit engine branches keyed on wf.settings.executionOrder — legacy (unchanged) and v1 (new: rule (c) flip + end-of-run drain)"
  - "trace.merges[name].runs — the primary per-fire representation; fired/sources/itemCounts retained as run-0 compat"
  - "tests/n8n/walkerEngineFidelityV1.test.mjs — v1 reproductions of executions 12354/12355/12356 against a frozen v1 graph copy"
  - "tests/n8n/creditsSummaryUnderV1.test.mjs — pins Collect Credits' single-fire behaviour under v1 with all three providers enabled"
  - "tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json — the frozen v1 graph copy the two new files walk"
affects:
  - .planning/todos/pending/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md (closed)
  - .planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md (new, carried out)

tech-stack:
  added: []
  patterns:
    - "two explicit engine branches keyed on one variable (order), never one patched state machine — keeps the legacy fidelity fixtures meaning what they meant when written"
    - "shared maths, divergent state machine: mergeBuffers() extracted once, called by both the legacy arrival state machine and the v1 run-indexed one"
    - "run-indexed pending buffering, not reset-and-discard — makes the v1 model invariant to the walker's own delivery order, matching the engine rather than the walker's queue"
    - "RED before the walker edit, observed as a clean assertion failure (1 !== 2), not a TypeError — the fixture and the fix were separated in time on purpose"

key-files:
  created:
    - tests/n8n/walkerEngineFidelityV1.test.mjs
    - tests/n8n/creditsSummaryUnderV1.test.mjs
    - tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json
    - .planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md
  modified:
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/n8n/walkWorkflow.test.mjs
    - tests/n8n/fixtures/frozen/README.md
    - .planning/todos/completed/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md (moved from pending/)

decisions:
  - "mergeBuffers(node, buffers, numberInputs) extracted as the ONE shared append/combineByPosition/combineAll maths helper — the legacy and v1 branches differ only in their arrival/delivery state machine, never in this maths, per the plan's Step 3b instruction."
  - "v1 pending runs are RUN-INDEXED (a list of {filled, sources} objects per Merge, earliest-unfilled-input-wins), not a reset-after-fire model — this makes the observed [2, 1] item-count split on Decide Company Action Merge hold regardless of which of two sentinel gates happens to arrive at input 0 first, matching the plan's explicit reasoning for why reset-and-discard was rejected."
  - "requiredInputs is hardcoded to 1 for every Merge this repo's builder emits (append/combine), and THROWS by node name if a chooseBranch Merge is ever encountered — no chooseBranch Merge exists today, so this path is untested but load-bearing if the builder ever emits one."
  - "trace.stalled under v1 now only reports a Merge that received literally ZERO deliveries across every input, for the whole execution — any Merge that gets even one delivery drains and fires (requiredInputs is always 1), so the three walkWorkflow.test.mjs cases that used to demonstrate a partial-input stall were re-derived as drain-and-fire cases, not deleted."
  - "The 'zero-item delivery case' in walkWorkflow.test.mjs was converted to legacy-only (settings {} + allowLegacy: true) rather than deleted — it still documents the recorded LEGACY mechanism honestly, it just no longer claims to be the v1 default."
  - "Task B (credits lane) went GREEN, not RED — Collect Credits' two-producers-per-input shape (real adapter vs. skip sentinel) is mutually exclusive by construction, unlike Decide Company Action Merge's six-producer shape. The builder-contract question this raises was carried into its own todo rather than assumed answered."

metrics:
  duration: ~90 min
  completed: 2026-09-11

actuals:
  tokens: 18600    # chars/4 over the realized diff of the authored files (walkWorkflow.mjs,
                    # walkWorkflow.test.mjs, the two new test files, the frozen README, both
                    # todo files) — EXCLUDING the 1.1MB frozen n8n/wf_enrichment_cloud.v1
                    # graph copy, which is a byte-identical `cp` of already-committed JSON,
                    # not authored work
  tasks: 3
  commits: 3
  plan_head_before: 55d26dc0516f60e49b6091870a2768f3da642dc
---

# Quick Task 260911-0tz: Fix the Walker Rule (c) First, Then the Credit-Lane Test Summary

The offline walker (`tests/n8n/lib/walkWorkflow.mjs`) modeled n8n's LEGACY execution
engine on the one rule that decides whether a Merge input is claimed by a real row or an
empty one — even though every committed `n8n/wf_*.json` runs on `executionOrder: "v1"`.
It now models both engines as two explicit branches, proven against Gate 11's own live
recordings (executions 12354/12355/12356), and the fixed walker was then used to check
whether the credit-check lane's Merge shape multi-fires the same way the company-action
one does under v1 (it doesn't).

## What shipped

**Task A — the walker's v1 branch, RED-first (commit `9e3dc2f3`).**

Froze a byte-identical copy of the committed `n8n/wf_enrichment_cloud.json`
(287 nodes, `executionOrder: "v1"`, verified identical to commit `ec102a4` via `git diff`
before copying) at `tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json`.

Wrote `tests/n8n/walkerEngineFidelityV1.test.mjs` against the UNMODIFIED walker first and
observed RED: `Decide Company Action Merge must fire twice` — `1 !== 2` (a clean
assertion failure, not a TypeError on an undefined `.runs`, exactly as the plan required).

Then rewrote `walkWorkflow.mjs`'s Merge handling as two explicit branches keyed on
`wf.settings.executionOrder`:

- **legacy** (`allowLegacy: true` only): byte-identical to the pre-existing arrival state
  machine — first delivery per input wins, a Merge fires at most once, a zero-item output
  still counts as a delivery. Untouched in behavior; only its maths now calls the shared
  `mergeBuffers()` helper instead of inlining append/combineByPosition/combineAll.
- **v1** (the default for every committed graph): a node that RAN and emitted zero items
  makes NO delivery (`propagate()`'s new `if (order === "v1" && outItems.length === 0)
  return;`). Merge inputs are buffered as run-indexed PENDING runs — a delivery to input
  `i` fills the earliest pending run whose `i` is still unfilled, or opens a new one;
  nothing is ever discarded. A pending run with every input filled fires immediately. At
  end-of-run, a new DRAIN pass fires the earliest pending run of any Merge whose
  filled-input count reaches `requiredInputs` (`1` for every append/combine Merge this
  repo emits), repeating and resuming the main queue after each fire until nothing
  qualifies — so a Merge can now fire more than once per execution, with an absent input
  contributing `[]` to the merge maths and `undefined` to that run's `sources`.

`trace.merges[name]` gained `runs: [{sources, itemCounts}, ...]` as the primary
representation, per the plan's `<assumption_delta_decision>`; `fired`/`sources`/
`itemCounts` are retained, carrying run 0's values, for the six existing consumer files
that read the flat shape (none of which were touched).

`walkerEngineFidelityV1.test.mjs` went GREEN on all three recordings, reproducing:
`Decide Company Action Merge` firing twice (`[2, 1]` items, run 1 input 1 unfilled,
claimed by `Recompute Not Requested Sentinel Gate`); `Decide Company Action` running
twice with 0 items each; `Merge Company`'s zero-item output never claiming a Merge
input; `Enrichment Gate Merge` firing once with 6 items; `Build Response` running once
with both real rows in that one run; `HubSpot Update` never running (disarmed propose
batch).

`walkerEngineFidelity.test.mjs`'s three legacy fixtures (12203, 12206, 12316) pass with
**zero diff** to that file — confirmed via `git diff` across every commit in this
history. Four cases in `walkWorkflow.test.mjs` depended on the old default model and were
moved to v1 truth, not toward green (D-70-19):

- the "zero-item delivery case" (LaneB's `return []` claiming a Merge input) — converted
  to **legacy-only** (`settings: {}` + `allowLegacy: true`), since it still accurately
  documents the recorded legacy mechanism, it just isn't the v1 default anymore;
- the "hang case", the "mutually-exclusive-branch...does NOT help" case, and "D-70-20
  mechanism price (1/2)" — all three used to assert `trace.stalled.length === 1` on a
  Merge with exactly ONE arrived input. Under v1, since `requiredInputs` is always `1`,
  any Merge with at least one filled input now DRAINS and fires at end-of-run instead of
  stalling — all three were re-derived to assert the Merge fires via the drain, with the
  never-delivered input absent from `sources` and contributing nothing to the merged
  items.

Full `node --test tests/n8n/*.test.mjs`: **1086/1086 passing** (baseline 1083 + 3 new
cases), zero failures, zero regressions outside the four pre-decided cases.

**Task B — the credit lane under v1, all three providers enabled (commit `f7f98a2f`).**

`tests/n8n/creditsSummaryUnderV1.test.mjs` walks the COMMITTED `n8n/wf_enrichment_cloud
.json` (no `allowLegacy`) with `providers: ["lusha", "apollo", "zoominfo"]`, the 12354
shape (2 contact-by-email rows, `mode: "propose"`). `Collect Credits` (append, 3 inputs,
TWO producer edges per input — the real usage adapter and its skip sentinel) fires
**exactly once**: each disabled-lane skip sentinel is fed zero items when its provider IS
enabled and never runs, so every input is claimed only by its real adapter. Both response
rows share the same `remaining_credits` array by reference (`Credits Broadcast`'s
`combineAll` spreads Build Credits Summary's one item onto both rows without cloning it).
`remaining_credits` turned out to be an ARRAY of `{provider, credits}` (not a keyed
object as initially assumed while planning the stubs) — corrected against the real
`Build Credits Summary` jsCode before asserting. GREEN, no double-fire defect on this
Merge shape — unlike `Decide Company Action Merge`'s six-producer, two-input shape.

Also needed, beyond `enrichmentMixedBatch.test.mjs`'s `baseStubs()`: `codeStubs` for the
two AWAIT-bearing Code nodes this run reaches with zoominfo enabled (`ZoomInfo Enrich`,
the contact-enrichment lane; `ZoomInfo Usage`, the credit lane — both flagged by
`codeNodeAwaits`), and `httpStubs["ZoomInfo Mint"]`/`["ZoomInfo Usage Mint"]` for the
OAuth token endpoints — none of which `enrichmentMixedBatch.test.mjs`'s stubs cover,
since its own tests never enable a provider.

Full suite: **1087/1087 passing**.

**Task C — close the walker todo, open the builder-contract todo (commit `75c611ac`).**

Moved `2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md` to
`completed/` with a resolution note naming this task, the two walker branches, and
`walkerEngineFidelityV1.test.mjs` as fidelity evidence. Its "Builder follow-on" section
was carried OUT into a new pending todo,
`2026-09-11-merge-input-contract-allows-many-producers-per-input.md` — it is **not**
answered by Task B: Task B proved ONE Merge (`Collect Credits`) safe under a
mutually-exclusive-producer-pair shape, while `Decide Company Action Merge`'s six-edge,
non-exclusive shape still multi-fires live and was left untouched (out of scope: no
`scripts/build_cloud_workflows.py` or `n8n/wf_*.json` edit anywhere in this task).

## Deviations from Plan

**None — plan executed as written**, with one clarification worth recording: the plan's
`<action>` for Task B suggested `remaining_credits` might be a keyed object; the real
`Build Credits Summary` jsCode produces an array of `{provider, credits}`. The test
assertions were written against the actual shape (read from the committed node's own
jsCode) rather than the plan's working assumption — this is exactly the "verify before
asserting" the plan's `read_first` instructed, not a deviation from intent.

## Threat Flags

None. `wf_enrichment_cloud.v1.2026-09-10.json` is a byte copy of an already-committed,
disarmed file (`ALLOW_HUBSPOT_RECORD_WRITES` / write-flag literals unchanged, no
credentials block on any node — the same T-0TZ-01 disposition the plan's threat model
already accepted).

## Verification

- `node --test tests/n8n/walkerEngineFidelityV1.test.mjs` — 3/3 passing.
- `node --test tests/n8n/walkerEngineFidelity.test.mjs` — 5/5 passing, zero diff to the file.
- `node --test tests/n8n/creditsSummaryUnderV1.test.mjs` — 1/1 passing.
- `node --test tests/n8n/*.test.mjs` — **1087/1087 passing**, 0 failing.
- `.venv/bin/python -m pytest tests/test_prove_phase70_runtime.py -q` — **25 passed**
  (unaffected — this suite exercises `scripts/prove_phase70_runtime.py`, not the walker
  module changed here; run per this task's orchestrator constraints, not required by the
  plan's own `<verification>`).
- `git diff --stat -- n8n/ scripts/build_cloud_workflows.py` across every commit in this
  task: only a pre-existing, unrelated `n8n/README.md` modification that predates this
  task's session and was never staged or committed by it — no `n8n/wf_*.json` and no
  `scripts/build_cloud_workflows.py` diff in any commit this task made.

## Self-Check: PASSED

- FOUND: tests/n8n/lib/walkWorkflow.mjs
- FOUND: tests/n8n/walkerEngineFidelityV1.test.mjs
- FOUND: tests/n8n/creditsSummaryUnderV1.test.mjs
- FOUND: tests/n8n/fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json
- FOUND: .planning/todos/completed/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md
- FOUND: .planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md
- FOUND commit 9e3dc2f3 (`git log --oneline --all | grep 9e3dc2f3`)
- FOUND commit f7f98a2f (`git log --oneline --all | grep f7f98a2f`)
- FOUND commit 75c611ac (`git log --oneline --all | grep 75c611ac`)
