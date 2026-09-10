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
