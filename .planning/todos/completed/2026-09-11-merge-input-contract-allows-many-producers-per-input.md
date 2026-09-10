---
created: 2026-09-11T00:30:00.000Z
updated: 2026-09-11
title: assert_merge_input_contract (D-70-20) checks at least one producer per input, not at most one — a Merge input with MORE than one producer can multi-fire under v1
area: n8n-backend
severity: major
files:
  - scripts/build_cloud_workflows.py
---

## Carried out of the walker todo (quick task 260911-0tz), deliberately NOT closed by it

`.planning/todos/completed/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md`
fixed the WALKER's model of the v1 engine — it made the walker able to SEE and reproduce
`Decide Company Action Merge` firing twice on executions 12354/12355/12356
(`tests/n8n/walkerEngineFidelityV1.test.mjs`). It did not change, and was never meant to
change, anything the BUILDER generates. `Decide Company Action Merge` still has SIX producer
edges into its two declared inputs, live, today, and will keep multi-firing under v1 until
this question is decided and acted on.

Quick task 260911-0tz's Task B checked the ONE other Merge in this graph with more than one
producer per input — `Collect Credits` (append, 3 inputs, two producers each: the real usage
adapter and its skip sentinel) — and found it does NOT multi-fire
(`tests/n8n/creditsSummaryUnderV1.test.mjs`, GREEN): the two producers sharing an input are
mutually exclusive by construction (a provider is either enabled or not; exactly one of the
pair ever runs), so exactly one delivery ever reaches that input. `Decide Company Action
Merge`'s two inputs are NOT mutually exclusive in the same way — both `Companies Absent
Sentinel Gate` deliveries can fill both inputs in one run, and a LATER producer
(`Recompute Not Requested Sentinel Gate`) can still deliver to input 0 alone afterward,
opening a second pending run that the end-of-run drain then fires. So "more than one
producer per input" is not by itself the defect shape — `Collect Credits` proves a
multi-producer input CAN be safe. The open question is what distinguishes the safe shape
from the unsafe one, and whether the builder should enforce it.

## The open decision

`assert_merge_input_contract` (`scripts/build_cloud_workflows.py`, D-70-20) currently checks
only that every Merge input has AT LEAST one producer edge — it says nothing about an input
with MORE than one. Decide one of:

1. **Tighten the contract**: a Merge input with more than one producer edge is a build-time
   violation UNLESS the builder can prove the producers are mutually exclusive (e.g. they
   share a single upstream IF/gate node, as `Collect Credits`'s pairs do) — `Decide Company
   Action Merge`'s six-producer shape would need to be restructured (extra Merge stage, or a
   single upstream gate per input) to pass.
2. **Relax the requirement on consumers instead**: accept that a Merge with a non-exclusive
   multi-producer input can fire more than once per execution, and require every downstream
   consumer of such a Merge to tolerate N runs (as `Decide Company Action` already does today
   — it filters markers and is harmless on either run). Document the tolerance requirement
   next to the Merge, not just discover it by replay.

Either way, `Decide Company Action Merge`'s live shape is what motivates the decision — it
is not a hypothetical.

## Test shape once decided

If (1): a build-time assertion in `scripts/build_cloud_workflows.py` naming the offending
Merge and its non-exclusive producer pairs, plus a regenerated `n8n/wf_enrichment_cloud.json`
that restructures `Decide Company Action Merge`'s inputs to be exclusive (Phase 46 parity:
builder + regenerated JSON in one commit, then deploy — never hand-edit the JSON).
If (2): a `walkerEngineFidelityV1.test.mjs`-style case (or an addition to it) proving every
downstream consumer of a multi-firing Merge stays correct across all its runs, plus a comment
convention on the Merge node itself recording which of its inputs are non-exclusive and why
that is safe.

Out of scope for this todo to resolve unilaterally: this is a builder/architecture decision
(Phase 46 parity rule; never hand-edit `n8n/wf_*.json`), the operator's call, not an
executor's.

## Open question (MN-01, quick task 260911-1z5)

Does the engine drain a SECOND pending run of the same Merge at end of run? 12354-12356 only
ever observed ONE drained run, and CLAUDE.md §13.0.3's `requiredInputs` row says a waiting
node "executes once". The walker now CAPS the drain at one run per Merge and reports any
leftover pending run as `merge_pending_runs_undrained` rather than firing or dropping it.
Resolving this needs a live observation of a Merge left with two partially-filled pending
runs — not available from any recording in this repo.

## Open question (NF-MJ-01, quick task 260911-1z5 review, recorded by the round-3 closure)

The walker's BL-02 grouping rule — one producer node-run's deliveries to several inputs of one
Merge fill ONE pending run atomically — is CONSISTENT WITH recordings 12354-12356 but was not
isolated by them: a per-input FIFO queue model (input i's k-th delivery joins run k) reproduces
the same `source` arrays whenever `Companies Absent Sentinel Gate` reaches input 0 first. The
two models diverge on a Merge where two grouped producers OVERLAP on an input (P -> inputs
0,1 and Q -> inputs 1,2 of a 3-input Merge): grouping opens a second pending run that MN-01's
cap leaves undrained and `starvedWithData` reports as a loss; the per-input-queue model
completes one run (P,P,Q) and loses nothing. Seven Merges in `wf_enrichment_cloud.json` carry a
producer feeding multiple inputs with a second producer on one of those inputs (`Build Response
Merge Stage 1/2`, `Merge Winners Fan-In`, `Merge Company Fan-In`, ...). Pinned as a
KNOWN-UNOBSERVED case in `tests/n8n/walkWorkflow.test.mjs` (NF-MJ-01). Resolving it needs a
live recording of a Merge with overlapping grouped producers both delivering.

## Operator ruling 2026-09-11 (resume session)

**Option A: allowlist + assert.** `assert_merge_input_contract` gains rule 5: a Merge input
with more than one producer edge is a build-time violation unless the Merge is named in an
explicit tolerant-allowlist in `scripts/build_cloud_workflows.py` carrying a reason string
(`Decide Company Action Merge`: consumer filters markers, only marker-only runs multi-fire).
`Collect Credits` is admitted either by the same allowlist or by a shared-upstream-gate
exclusivity check — implementer's choice, must be tested. No graph change, no regenerated
JSON, no redeploy. MN-01 and NF-MJ-01 stay open as recorded.

## Resolved 2026-09-11 (quick task 260911-ao1)

Option A shipped. `assert_merge_input_contract` (`scripts/build_cloud_workflows.py`) gained
rule 5: a Merge input fed by more than one producer edge is a build-time violation unless the
pair `(workflow body name, Merge name)` is listed in a new module-level
`_MERGE_MULTI_PRODUCER_TOLERANT` dict carrying a reason string — keyed on the same
`(wf["name"], node name)` discipline `_SELF_DISPATCH_EXEMPTIONS` uses (WR-08), so a Merge
name borrowed by another workflow does not inherit the tolerance.

Populated with the RED-confirmed 16-entry census (identical output from both the Python
builder loop and the mirrored JS test, quoted verbatim in `260911-ao1-SUMMARY.md`):

- `Decide Company Action Merge` — the operator's own reasoning above (consumer filters
  markers, only marker-only runs multi-fire; executions 12354/12355/12356,
  `walkerEngineFidelityV1.test.mjs`).
- `Collect Credits` — the todo's own mutual-exclusivity finding, proven GREEN by
  `creditsSummaryUnderV1.test.mjs`.
- The other fourteen — admitted by the 2026-09-11 census under this ruling, each stating the
  D-70-23 gated-sentinel structural fact and its lane's evidence status (v1 recordings exist
  for the enrichment-lane entries at `exec_1235{4,5,6}.runData.json` and the ingest-lane
  entries at `exec_1235{7,8}.runData.json` — none shows that specific Merge multi-firing; the
  local-live and review-decision entries have no recording at all). None of the fourteen
  reasons claims "safe", "harmless" or "proven".

Mirrored in `tests/n8n/mergeInputContract.test.mjs`: a new `multiProducer` bucket in
`structuralViolations`, the same 16-pair `MULTI_PRODUCER_TOLERANT` map, and a new census test
asserting the mirrored allowlist is EXACTLY the set of (workflow, Merge) pairs with a
multi-producer input across every committed `n8n/wf_*.json`, in both directions — an entry
with no real multi-producer edge fails as loudly as a real edge missing its entry.

Zero `n8n/` JSON diff (`git diff --quiet -- n8n/` held throughout regeneration) — this is an
assertion-only change, no graph change, nothing deployed, nothing armed. Full
`node --test tests/n8n/*.test.mjs` (1101 tests) passes, `creditsSummaryUnderV1.test.mjs` and
`walkerEngineFidelityV1.test.mjs` unmodified and green.

**MN-01 and NF-MJ-01 are NOT closed by this task.** Both carried forward verbatim into
`.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md`.
