---
phase: quick-260911-ao1
plan: 01
subsystem: n8n-backend
tags: [n8n, merge-node, build-time-assertion, static-analysis, test-mirror]

requires:
  - phase: quick-260911-1z5
    provides: MN-01/NF-MJ-01 open questions and the walkWorkflow.mjs v1 model this task's evidence citations rest on
provides:
  - "assert_merge_input_contract rule 5: a Merge input fed by more than one producer edge is a build-time violation unless the (workflow body name, Merge name) pair is on a named, reasoned allowlist"
  - "_MERGE_MULTI_PRODUCER_TOLERANT (16 entries) in scripts/build_cloud_workflows.py"
  - "mirrored MULTI_PRODUCER_TOLERANT + multiProducer bucket + exact-both-directions census test in tests/n8n/mergeInputContract.test.mjs"
  - "merge-input-contract todo closed; MN-01/NF-MJ-01 carried forward into their own pending todo"
affects: [n8n-workflow-generation, merge-node-safety, quick-260911-anv]

actuals:
  tokens: 8388
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Default-refuse, named-exemption allowlist for a statically-unprovable structural property (same idiom as _SELF_DISPATCH_EXEMPTIONS, WR-08)"
    - "Cross-language mirrored constant (Python dict / JS Map) pinned exact-both-directions by a census test, since neither side can import the other"

key-files:
  created:
    - .planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md
  modified:
    - scripts/build_cloud_workflows.py
    - tests/n8n/mergeInputContract.test.mjs
    - .planning/todos/completed/2026-09-11-merge-input-contract-allows-many-producers-per-input.md

key-decisions:
  - "Tolerance is Merge-level (the pair (workflow, Merge name)), not per-input, per the ruling's own wording"
  - "Reason strings for 14 of 16 entries state structural fact + per-lane evidence-recording status only — never 'safe'/'harmless'/'proven' — because census admission is not a safety proof"
  - "MN-01 and NF-MJ-01 explicitly NOT resolved by this task; carried forward verbatim to their own pending todo"

requirements-completed: [MIC-01, MIC-02, MIC-03]

coverage:
  - id: MIC-01
    description: "Rule 5 + 16-entry tolerant allowlist added to assert_merge_input_contract in scripts/build_cloud_workflows.py; RED captured with the allowlist empty; regeneration produces zero n8n/ JSON diff"
    requirement: MIC-01
    verification:
      - kind: unit
        ref: "scripts/build_cloud_workflows.py::assert_merge_input_contract (direct invocation loop over all 8 committed n8n/wf_*.json, allowlist emptied) — RED quoted below"
        status: pass
      - kind: other
        ref: ".venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/"
        status: pass
    human_judgment: false
  - id: MIC-02
    description: "Rule 5 mirrored in tests/n8n/mergeInputContract.test.mjs with a multiProducer bucket and an exact-both-directions census test; RED captured with the mirrored allowlist emptied"
    requirement: MIC-02
    verification:
      - kind: unit
        ref: "tests/n8n/mergeInputContract.test.mjs (19 tests, including the new census test) — RED quoted below"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/*.test.mjs (1101 tests, creditsSummaryUnderV1.test.mjs and walkerEngineFidelityV1.test.mjs unmodified)"
        status: pass
    human_judgment: false
  - id: MIC-03
    description: "merge-input-contract todo moved to completed/ with a Resolved section; MN-01 and NF-MJ-01 carried forward verbatim into a new pending todo, not closed"
    requirement: MIC-03
    verification:
      - kind: other
        ref: "test ! -e .planning/todos/pending/2026-09-11-merge-input-contract-allows-many-producers-per-input.md && grep -q MN-01 and NF-MJ-01 in the new pending todo"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-09-11
status: complete
---

# Quick Task 260911-ao1: Merge-Input Contract Rule 5 Summary

**`assert_merge_input_contract` now refuses any Merge input with more than one producer edge unless the (workflow, Merge) pair carries a named, reasoned exemption — closing the operator's Option A ruling with a RED-confirmed 16-entry census mirrored byte-for-byte between the Python builder and the JS test, and zero graph change.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-09-10T21:51:00Z (approx, from git log of prior commit)
- **Completed:** 2026-09-10T22:26:22Z
- **Tasks:** 3/3 completed
- **Files modified:** 4 (2 code/test, 2 todos — one renamed, one new)

## Accomplishments
- Rule 5 shipped in `assert_merge_input_contract`: default-refuse a multi-producer Merge input, admit only by a named `(workflow body name, Merge name)` pair with a written reason, keyed exactly like `_SELF_DISPATCH_EXEMPTIONS` (WR-08) so a borrowed Merge name never inherits tolerance.
- The exact same 16-pair census verified independently in two languages (Python builder loop, JS test) — RED output for both quoted below, byte-identical set of (workflow, Merge) pairs.
- `tests/n8n/mergeInputContract.test.mjs` gained an exact-both-directions census test so the two mirrored lists cannot silently rot.
- The merge-input-contract todo closed with a Resolved section; MN-01 and NF-MJ-01 explicitly carried forward, not closed, into a new pending todo.
- Zero `n8n/` JSON diff throughout — assertion-only change, nothing deployed, nothing armed.

## RED Evidence (quoted verbatim, per plan requirement)

### Task 1 — Python builder, allowlist emptied, looped over all 8 committed `n8n/wf_*.json`

4 workflows raised, 51 total input-level violations, exactly 16 distinct `(workflow, Merge)` pairs:

```
n8n/wf_contact_ingest_cloud.json: 5 Merge-input contract violation(s)
  - Build Association Request Merge[0]: fed by 3 producers [...]
  - Build Association Request Merge[1]: fed by 3 producers [...]
  - Ingest Merge Response[2]: fed by 2 producers [...]
  - Ingest Merge Response[3]: fed by 3 producers [...]
  - Ingest Merge Response[4]: fed by 3 producers [...]

n8n/wf_enrichment_cloud.json: 33 Merge-input contract violation(s)
  - Build Response Merge Stage 1[0..5]: fed by 4-7 producers each
  - Build Response Merge Stage 2[0..6]: fed by 5-7 producers each
  - Build Response Merge Stage 3[0..1]: fed by 2-3 producers each
  - Collect Credits[0..2]: fed by 2 producers each
  - Company Gate Merge[0..1]: fed by 3 producers each
  - Decide Company Action Merge[0..1]: fed by 3 producers each
  - Enrichment Gate Merge[0..4]: fed by 3 producers each
  - Merge Company Fan-In[0..2]: fed by 5-6 producers each
  - Merge Winners Fan-In[0..2]: fed by 4-5 producers each

n8n/wf_enrichment_local_live.json: 6 Merge-input contract violation(s)
  - Merge Company Fan-In[0..2]: fed by 2-3 producers each
  - Merge Winners Fan-In[0..2]: fed by 2-3 producers each

n8n/wf_review_decision_cloud.json: 7 Merge-input contract violation(s)
  - Build Review Response Merge[0..2]: fed by 2 producers each
  - Review Extract Record Merge[0..1]: fed by 2 producers each
  - Review Queue Rows Merge[0..1]: fed by 2 producers each

---COUNT--- 4 (workflows raising ValueError)
```

Distinct `(workflow, Merge)` pairs recovered from this output: exactly the 16 the plan's own
census listed — 2 in `LV Contact Ingest (Cloud template)`, 9 in `LV Enrichment (Cloud
template)`, 2 in `LV Enrichment (local LIVE)`, 3 in `LV Review Decision (Cloud)`.

### Task 2 — JS test, `MULTI_PRODUCER_TOLERANT` emptied

```
tests 19
pass 13
fail 6
```

Two of the six failures are the decisive ones (per-workflow structural tests also failed for
the 4 affected workflows, expected since they route through the same `structuralViolations`):

```
✖ PENDING names exactly the workflows that violate the contract, in both directions
  AssertionError: the pending list must be exactly the set of workflows currently
  violating the contract — emptying it is plan 70-11's acceptance
  + [ 'wf_contact_ingest_cloud.json', 'wf_enrichment_cloud.json',
      'wf_enrichment_local_live.json', 'wf_review_decision_cloud.json' ]
  - []

✖ MULTI_PRODUCER_TOLERANT names exactly the (workflow, Merge) pairs with a
  multi-producer input, in both directions
  AssertionError: MULTI_PRODUCER_TOLERANT must be exactly the census of
  (workflow, Merge) pairs with a multi-producer input across every committed
  n8n/wf_*.json ...
  + [
  +   'LV Contact Ingest (Cloud template) Build Association Request Merge',
  +   'LV Contact Ingest (Cloud template) Ingest Merge Response',
  +   'LV Enrichment (Cloud template) Build Response Merge Stage 1',
  +   'LV Enrichment (Cloud template) Build Response Merge Stage 2',
  +   'LV Enrichment (Cloud template) Build Response Merge Stage 3',
  +   'LV Enrichment (Cloud template) Collect Credits',
  +   'LV Enrichment (Cloud template) Company Gate Merge',
  +   'LV Enrichment (Cloud template) Decide Company Action Merge',
  +   'LV Enrichment (Cloud template) Enrichment Gate Merge',
  +   'LV Enrichment (Cloud template) Merge Company Fan-In',
  +   'LV Enrichment (Cloud template) Merge Winners Fan-In',
  +   'LV Enrichment (local LIVE) Merge Company Fan-In',
  +   'LV Enrichment (local LIVE) Merge Winners Fan-In',
  +   'LV Review Decision (Cloud) Build Review Response Merge',
  +   'LV Review Decision (Cloud) Review Extract Record Merge',
  +   'LV Review Decision (Cloud) Review Queue Rows Merge'
  + ]
  - []
```

Identical 16-pair set to Task 1's RED, from an independent code path (JS connections walk,
no shared code with the Python builder). This is the cross-language proof the census is real,
not an artifact of one implementation.

After populating both allowlists: `node --test tests/n8n/mergeInputContract.test.mjs` → 19/19
pass; full `node --test tests/n8n/*.test.mjs` → 1101/1101 pass.

## Task Commits

1. **Task 1: rule 5 + tolerant allowlist in the builder, RED first, zero JSON diff (MIC-01)** - `164769e2` (feat)
2. **Task 2: mirror rule 5 in mergeInputContract.test.mjs, RED first (MIC-02)** - `e8f01acc` (test)
3. **Task 3: close the todo, carry MN-01 and NF-MJ-01 forward still open (MIC-03)** - `20f5fbf3` (docs)

_No separate plan-metadata commit — quick-task convention (see prior `quick-260911-*` commits) records everything in the three task commits above; the orchestrator commits this SUMMARY.md separately per the executor contract._

## Files Created/Modified
- `scripts/build_cloud_workflows.py` - added `_MERGE_MULTI_PRODUCER_TOLERANT` (16 entries) and rule 5 inside `assert_merge_input_contract`; docstring rewritten
- `tests/n8n/mergeInputContract.test.mjs` - added mirrored `MULTI_PRODUCER_TOLERANT`, `multiProducer` bucket in `structuralViolations`, new exact-both-directions census test; header paragraph rewritten
- `.planning/todos/completed/2026-09-11-merge-input-contract-allows-many-producers-per-input.md` - `git mv` from `pending/`, appended Resolved section
- `.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` - new, carries MN-01 and NF-MJ-01 verbatim

## Decisions Made
- Tolerance keyed at Merge-level (`(workflow, Merge name)`), not per-input — matches the ruling's own wording ("the Merge is named") and the `_SELF_DISPATCH_EXEMPTIONS` precedent.
- The 14 census-only reason strings state structural fact (D-70-23 gated sentinel sharing an input with its real producer) plus per-lane evidence-recording status (which frozen `exec_1235*.runData.json` recordings exist and that none shows that specific Merge multi-firing), and explicitly avoid "safe"/"harmless"/"proven" — census admission is not a safety proof.
- `Collect Credits`'s reason cites the existing `creditsSummaryUnderV1.test.mjs` mutual-exclusivity proof rather than restating it, per the plan's family (b) instruction.

## Deviations from Plan

None - plan executed exactly as written. One incidental fix: the JS `Edit` insertion for the
`MULTI_PRODUCER_TOLERANT` map briefly introduced literal NUL bytes (`\x00`) in place of the
intended `.join(" ")` separator space (a tool-input rendering artifact, not a logic bug) —
caught immediately by the first post-edit test run (deepEqual failure showing `\x00` in
"expected" vs a real space in "actual"), fixed with a byte-level find/replace before the
RED-first sequence was executed, and does not appear in the final committed file (verified:
`node --test` green, no NUL bytes remain). Not logged as a Rule 1/2/3 deviation since it never
reached a commit — normal edit-and-verify iteration.

## Issues Encountered
None beyond the NUL-byte artifact above, resolved within Task 2 before any commit.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Rule 5 is live and enforced on every future `scripts/build_cloud_workflows.py` regeneration.
Any new multi-producer Merge input introduced by a future builder change (including sibling
batch item 260911-anv, which touches the same file but a different function per the scope
fence) will stop generation until named and reasoned on the allowlist. MN-01 and NF-MJ-01
remain open, tracked in their own pending todo, unblocked for future work whenever a live
recording surfaces the shapes they need.

---
*Phase: quick-260911-ao1*
*Completed: 2026-09-11*
