---
created: 2026-09-11T00:30:00.000Z
updated: 2026-09-11
title: MN-01 (does the engine drain a SECOND pending Merge run at end of run?) and NF-MJ-01 (walker's BL-02 grouping rule not isolated from a per-input FIFO alternative)
area: n8n-tests
severity: major
files:
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkWorkflow.test.mjs
kind: question
trigger: a live execution where one Merge is left with two partially-filled pending runs (MN-01) or two grouped producers overlapping on an input both deliver (NF-MJ-01); freeze its runData (headers redacted) and run tests/n8n/walkerEngineFidelityV1.test.mjs against it
owner: operator (first supervised armed batch, post-run freeze)
---

Carried out of
`.planning/todos/completed/2026-09-11-merge-input-contract-allows-many-producers-per-input.md`
when quick task 260911-ao1 closed that todo (it shipped rule 5 + the tolerant allowlist;
it did not, and was never meant to, resolve either question below). Both are already
pinned as KNOWN-UNOBSERVED in `tests/n8n/walkWorkflow.test.mjs`.

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
