---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 02
subsystem: [n8n, plugin, testing]
tags: [n8n, workflow-execution-model, merge-node, carry-merge, ingest-lane, result-channel]

requires:
  - phase: 70-01
    provides: "graph walker (walkWorkflow.mjs) + by-name-read detector (detect_by_name_reads)"
provides:
  - "splice_carry_merge_after(nodes, conns, http_name, carry_source, *, merge_name=None, combine_by='combineByPosition') — the reusable D-70-04 carry mechanism"
  - "The ingest lane (n8n/wf_contact_ingest_cloud.json) fully migrated: zero by-name reads, one append Merge (Ingest Merge Response, 3 inputs), 8 combine-mode carry merges"
  - "walkWorkflow.mjs combineAll (cartesian) Merge support"
  - "The ack-only webhook contract (D-70-07) and runData-only result channel (D-70-05) landed and proven end to end"
affects: [70-03, 70-04, 70-05, 70-06, 70-07]

actuals:
  tokens: 103460
  tasks: 3
  commits: 4
plan_head_before: c38a4435738c31b6c78ca88045931b2f6def60f6

tech-stack:
  added: []
  patterns:
    - "Carry merge as ONE reusable helper (splice_carry_merge_after), not a hand-wired one-off per hop — Task 2's own 'Associate Carry Merge' was refactored onto it rather than left as a second mechanism."
    - "A discriminating tag field (_decided_snapshot, _company_domain_search) rather than a by-name read to separate two different roles riding the SAME Merge or the SAME item — the mechanism this whole migration replaces the by-name read WITH."
    - "combineAll (cartesian) for a genuine 1-to-N broadcast (one config item onto every row), distinct from combineByPosition (per-item HTTP hop, count-preserving fan-out of the identical delivery)."

key-files:
  created:
    - tests/n8n/ingestCarryMerge.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/test_no_by_name_reads.py
    - tests/test_merge_helpers.py
    - tests/test_ingest_search_contract.py
    - tests/n8n/companyAssociationFlow.test.mjs
    - tests/n8n/ingestResponseRowId.test.mjs
    - tests/n8n/ingestReviewBranchResponds.test.mjs
    - tests/n8n/ingestUpdateWriteBlockedFlow.test.mjs
    - tests/n8n/pairPipelineAssociationFlow.test.mjs
    - tests/n8n/suggestionProvenanceFlow.test.mjs

key-decisions:
  - "Operator answer to Task 1: \"proceed\" (2026-09-09) — publish the ack-only contract and the runData-only result channel (D-70-05/D-70-07); the two-channel design that produced the F1/F5/F5b/F10/F11/F12 defect class is retired."
  - "Every carry merge on this lane uses combine-by-position, never combine-by-fields — no hop echoes an opaque row-identifying token, and combine_by-position's precondition (the two merge inputs are literal fan-outs of the exact same delivery feeding the HTTP node, so count and order agree by construction) holds at every hop. combine-by-fields stays available on splice_carry_merge_after's signature for a future hop that does echo a token, but none of this lane's 7 HTTP hops needed it."
  - "The one non-HTTP by-name read (Merge Contacts reading 'Set Config' for source_by_field) is closed with combine-by-all (cartesian), not combine-by-position — a genuine 1-to-N broadcast (one parsed config item onto every CSV row), spliced between 'Extract From File' and 'Map Columns'. A new 'Set Config Fields' node does the one-time JSON-string parse (dispatch.py's multipart filename=None shape)."
  - "'Build Association Request'/'Build Ingest Response' no longer read 'Decide Action' by name. A new 'Decide Action Snapshot' node fans Decide Action's full row set into 'Ingest Merge Response' as a THIRD input, tagged _decided_snapshot; 'Build Ingest Response' splits $input into the full ground truth vs a real lane arrival by that tag, never by node identity."
  - "'Build Association Request' is deliberately NOT wrapped in its own Merge (D-70-01 targeted 'Build Ingest Response' only). It keeps its two inbound edges (Update Carry Merge, Create Carry Merge) unmerged and runs once per wave — safe because it reads $input directly (never by name), and a Merge there would starve on any update-only or create-only batch without its own sentinel pair, which nothing downstream needs."
  - "[Rule 1 - Bug, found writing this task's own test] 'Adapt Search Results' read 'Normalize Phone' by name instead of its own literal predecessor 'Apply Email' — silently dropping email_status/email_valid before they ever reached Decide Action (always null in the final response). Fixed as part of retiring the read: carry_source is now 'Apply Email'."
  - "[Rule 1 - Bug, found writing this task's own test] 'Build Ingest Response' treated ANY item carrying an `action` field as a real association attempt (`arrived`) — but 'Set Review' also feeds the same Merge with the row's own ORIGINAL decided action untouched, so a review row that DOES resolve a company self-matched against its own Set-Review contribution by email, misreporting `association: \"associated\"` for a row that never reached a write node. Pre-existing since Task 2's shipped design (confirmed against ec247f8), not introduced by this task. Fixed by tightening `arrived` to `row.action === \"enrich\"` — the literal, unique stamp only 'Build Association Request' emits."

patterns-established:
  - "A carry-merge helper generalized from one proven hand-wired instance, applied uniformly rather than re-invented per hop."
  - "combineAll Merge support added to the walker (the phase's own instrument) rather than modeling it ad hoc in a test."

requirements-completed: [D-70-01, D-70-03, D-70-04, D-70-05, D-70-06, D-70-07]

coverage:
  - id: D1
    description: "detect_by_name_reads(build_cloud()) reports 0 violations (was 10); build_enrichment_cloud()/build_review_decision_cloud() remain non-zero (119/12, plan 70-04's job)"
    requirement: D-70-03
    verification:
      - kind: unit
        ref: "tests/test_no_by_name_reads.py::test_ingest_lane_has_zero_by_name_reads and ::test_detector_finds_todays_violations (7 tests, 0 failures)"
        status: pass
    human_judgment: false
  - id: D2
    description: "splice_carry_merge_after generalizes D-70-04's carry mechanism; applied across all 7 per-item HTTP hops (Update/Create/Associate writes, Verify Emails batch, Search by Email, Company Domain/Name search) plus one combineAll broadcast (source_by_field)"
    requirement: D-70-04
    verification:
      - kind: unit
        ref: "tests/test_merge_helpers.py::test_splice_carry_merge_after_* (4 tests) and ::test_ingest_workflow_carries_exactly_one_append_merge_named_ingest_merge_response"
        status: pass
      - kind: integration
        ref: "tests/n8n/ingestCarryMerge.test.mjs — four-row batch (email match/no-match x company-by-domain/name-only) through the walker, both tests pass"
        status: pass
    human_judgment: false
  - id: D3
    description: "A two-row batch and a review-only batch both reach 'Build Ingest Response' exactly once through 'Ingest Merge Response' (now 3 inputs); the ack-only webhook and runData-only channel (D-70-05/D-70-07) proven end to end"
    requirement: "D-70-01, D-70-05, D-70-06, D-70-07"
    verification:
      - kind: integration
        ref: "tests/n8n/ingestTracerFlow.test.mjs (3 tests, unchanged from Task 2, still green against the widened graph)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Generation is idempotent (two consecutive builder runs byte-identical) and every existing test file coupled to the old carry shape was updated to the new one"
    verification:
      - kind: integration
        ref: "diff of two consecutive `python scripts/build_cloud_workflows.py` runs — byte-identical; full suites: node --test tests/n8n/*.test.mjs (976 pass), pytest -q (4627 passed, 154 skipped), operator-claude-plugin pytest (2850 passed, 5 skipped)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live Merge-semantics observation on this n8n Cloud build (settled vs stuck, live executionOrder, zero writes, alwaysOutputData placement) — Task 2's disarmed probe"
    verification: []
    human_judgment: true
    rationale: "deferred to end-of-phase UAT per operator ruling 2026-09-09 — see 70-DEFERRED-GATES.md Gate 1. Unaffected by Task 3: the probe targets the convergence Merge and alwaysOutputData placement Task 2 already built; Task 3 adds carry merges on top of that same graph."

duration: ~2h (across two dispatches)
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 02: One ingest row end to end, then every carry merge on that lane Summary

**A reusable carry-merge helper retires all ten by-name reads on the ingest lane — the first of Phase 70's three cloud workflows to reach zero — while the ack-only webhook and runData-only result channel it depends on land and prove out end to end.**

## Performance
- **Duration:** ~2h across two dispatches (Task 1/2 committed 2026-09-09 as `ec247f8`; Task 3 committed 2026-09-10 as `87c7cd4`/`e9988b8`)
- **Started:** 2026-09-09 (Task 1) · **Completed:** 2026-09-10 (Task 3)
- **Tasks:** 3 of 3 complete
- **Files modified:** 26 total across the plan (13 in Task 3 alone: 1 created, 12 modified)

## Accomplishments

- **Task 1 (checkpoint:decision).** Operator answer: **"proceed"** — publish the ack-only
  webhook contract (D-70-07) and the runData-only result channel (D-70-05). Recorded
  verbatim, per the plan's own resume-signal.
- **Task 2 (tracer).** The ingest lane's convergence point (`Ingest Merge Response`), one
  carry merge across the association write hop (`Associate Carry Merge`), the ack-only
  responder (`Build Ingest Ack`), and lane-parameterized runData recovery
  (`watch.recover_dispatch(lane="ingest")`) all landed and proved out on a two-row and a
  single-lane batch. Merge `typeVersion 3.2`, `mode`/`combineBy` (`append` |
  `combineByPosition` | `combineAll`) and `options.clashHandling.values.resolveClash`
  verified against `n8n-io/n8n` `master` (source cited in `merge_node`'s own docstring,
  `scripts/build_cloud_workflows.py`). The disarmed live probe (Gate 1) was deferred to
  end-of-phase UAT per operator ruling — recorded in `70-DEFERRED-GATES.md`.
- **Task 3 (auto, tdd).** `splice_carry_merge_after` generalizes Task 2's hand-wired
  mechanism and is applied to every remaining by-name read on the lane:
  - **Write hops:** `Update Carry Merge` / `Create Carry Merge` (new), `Associate Carry
    Merge` (refactored off the same helper) — `carry_source` is each write's own
    `splice_write_gates`-spliced gate.
  - **Verify hop:** `Verify Email Carry Merge` — `Build Verify Batch` now nests the N
    pre-collapse rows as `_rows` inside its one-item batch output; `Apply Email` reads
    `_rows`/`results` off `$input` instead of `$('Normalize Phone')`/`$('Verify Emails
    (batch)')`. Applied to **both** `build_cloud()` and `build_local()` (`Apply Email`'s
    jsCode is shared between them).
  - **Identity search hop:** `Search By Email Carry Merge` — `carry_source` is `Apply
    Email` (the hop's own literal predecessor), not `Normalize Phone` as the old by-name
    read used. This fixes a Rule-1 bug: `email_status`/`email_valid` were silently
    dropped before reaching `Decide Action`.
  - **Company-link chain:** `Company Domain Carry Merge` → new `Stash Domain Search`
    node (nests the domain response under `_company_domain_search` so the two
    `{total, results}` search envelopes never clash) → `Company Name Carry Merge` →
    `Adapt Company Link`, which now reads both search results off one `$input` item.
  - **The one non-HTTP by-name read:** `Merge Contacts`'s `source_by_field` read of
    `Set Config` closed with `combineAll` (cartesian broadcast, not
    `combineByPosition`) via a new `Set Config Fields` node and a `Source By Field
    Broadcast` merge between `Extract From File` and `Map Columns`; `Map Columns`
    explicitly re-adds `source_by_field` (mapRow drops unmapped keys, same reason it
    already re-adds `allow_create`).
  - **`Decide Action Snapshot`** (new): a tagged fan-out of `Decide Action`'s full row
    set into `Ingest Merge Response`'s **third** input, closing `Build Association
    Request`'s and `Build Ingest Response`'s last by-name reads of `Decide Action`.
  - The walker (`walkWorkflow.mjs`) gained `combineAll` support to model the new
    broadcast merge.
  - `detect_by_name_reads(build_cloud())` — **0** (was 10). `build_enrichment_cloud()`
    (119) and `build_review_decision_cloud()` (12) stay non-zero, unaffected — plan
    70-04's job.

## Task Commits

1. **Task 1: Confirm the one-way client contract change** — none (checkpoint, resolved: "proceed")
2. **Task 2: One ingest row end to end** — `ec247f8` (feat)
3. **(interstitial) Record deferred Gate 1** — `dad2a8f` (docs)
4. **Task 3: Carry the row across the ingest lane's HTTP hops** — `87c7cd4` (test, RED) / `e9988b8` (feat, GREEN)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `splice_carry_merge_after` (new, generalized helper); `STASH_DOMAIN_SEARCH`, `SET_CONFIG_FIELDS`, `DECIDE_ACTION_SNAPSHOT` (new JS bodies); `BUILD_VERIFY_BATCH`/`APPLY_EMAIL`/`ADAPT_SEARCH_RESULTS`/`ADAPT_COMPANY_LINK`/`CO_LINK_NAME_SEARCH_BODY`/`BUILD_ASSOCIATION_REQUEST`/`BUILD_INGEST_RESPONSE`/`MERGE_CONTACTS`/`MAP_COLUMNS` rewritten to read `$input` instead of `$(name)`; `build_cloud()`/`build_local()` rewired.
- `n8n/wf_contact_ingest_cloud.json` — regenerated; 45 nodes (was 29 pre-Phase-70, 35 after Task 2), 9 Merge nodes.
- `n8n/wf_contact_ingest_local.json` — regenerated; 13 nodes (was 12 after Task 2), 1 Merge node (`Verify Email Carry Merge`).
- `tests/n8n/lib/walkWorkflow.mjs` — `combineAll` (cartesian product) Merge mode added.
- `tests/n8n/ingestCarryMerge.test.mjs` — new: four-row batch through the walker, plus a structural "every HTTP hop's only consumer is a Merge" assertion.
- `tests/test_no_by_name_reads.py` — ingest assertion split out and flipped to zero-violations.
- `tests/test_merge_helpers.py` — new unit tests for `splice_carry_merge_after`; the ingest-workflow-shape test widened to the full 9-merge inventory.
- `tests/test_ingest_search_contract.py` — `Adapt Search Results`' offline harness updated to the merged-item shape.
- `tests/n8n/companyAssociationFlow.test.mjs`, `ingestResponseRowId.test.mjs`, `ingestReviewBranchResponds.test.mjs`, `ingestUpdateWriteBlockedFlow.test.mjs`, `pairPipelineAssociationFlow.test.mjs`, `suggestionProvenanceFlow.test.mjs` — updated to seed the already-merged `$input` shape instead of a separate `$(name)` mock; `suggestionProvenanceFlow.test.mjs` gained a dedicated test for `Set Config Fields`'s JSON-string parsing.

## Decisions Made

- Operator answer to Task 1: "proceed" (2026-09-09) — publish the ack-only contract and the runData-only channel; recorded verbatim per the plan's resume-signal.
- Merge `typeVersion 3.2`; `mode` values `append`/`combine`/`combineBySql`/`chooseBranch`; `combineBy` values `combineByFields`/`combineByPosition`/`combineAll`; `options.clashHandling.values.resolveClash` — verified against `n8n-io/n8n` `master` source (Task 2, cited in `merge_node`'s docstring).
- Every carry merge on this lane is `combineByPosition` (7 hops) or `combineAll` (1 hop, the `source_by_field` broadcast) — never `combineByFields`. No hop on this lane echoes an opaque row-identifying token; every `carry_source` is a literal fan-out of the exact delivery feeding the HTTP node, so position and count agree by construction. `combine_by="combineByFields"` stays available on `splice_carry_merge_after`'s signature for a future hop that does need it.
- `Build Association Request` stays unmerged (2 inbound edges, runs per wave) — D-70-01 targeted `Build Ingest Response` only; it already reads `$input` directly (never by name), so a second Merge there is unnecessary risk (it would need its own starvation-proof sentinels, which nothing downstream requires).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `Adapt Search Results` read the wrong upstream node, dropping email verification fields**
- **Found during:** Task 3, while designing the `Search By Email Carry Merge`'s `carry_source`.
- **Issue:** The old by-name read recovered `Normalize Phone` (pre-email-verification) instead of `Apply Email` (its own literal predecessor), silently discarding `email_status`/`email_valid`/`email_verify_fallback` before `Decide Action` ever saw them — `email_status` in the final response was always `null`.
- **Fix:** `carry_source` for this hop is `Apply Email`; `ADAPT_SEARCH_RESULTS` rewritten to read the merged item's carried fields instead of a separate `Normalize Phone` list.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/ingestCarryMerge.test.mjs` asserts `email_status === "VALID"` survives to the final report for every row in the batch.
- **Commit:** `e9988b8`

**2. [Rule 1 - Bug] `Build Ingest Response` could self-match a review row against its own contribution**
- **Found during:** Task 3, writing `ingestCarryMerge.test.mjs`'s "resolves by domain / name-only" assertions (a review row with a resolved company).
- **Issue:** `arrived` was built from "any item carrying an `action` field" — but `Set Review` (one of `Ingest Merge Response`'s inputs) contributes the row's own ORIGINAL decided action/email/company_id, untouched. A review row whose company DID resolve therefore matched its own Set-Review contribution by email, misreporting `association: "associated"` for a row that never reached a write node at all. **Pre-existing since Task 2's shipped design** (confirmed by reproducing it against `ec247f8` before this task's own rewrite existed) — not introduced by this task, but exposed by the first test to give a review row a resolved company.
- **Fix:** Tightened `arrived`'s filter to `row.action === "enrich"` — the literal, unique stamp only `Build Association Request` ever emits, never a value `Decide Action` itself produces.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/ingestCarryMerge.test.mjs`'s Row 2/Row 3 assertions (`association: "not_confirmed"` for an unwritten row with a resolved company).
- **Commit:** `e9988b8`

**Total deviations:** 2 (both Rule 1, both fixed inline, both covered by the new test).
**Impact on plan:** None — both are auto-fixable bugs surfaced by the task's own required test coverage; no scope change, no architectural decision needed.

### Test-suite adaptations (not deviations — required to keep existing coverage green)

Six existing `tests/n8n/*.test.mjs` files and two `tests/test_*.py` files constructed their fixtures around the by-name-read mechanism this task retires (`nodeOutputs` mocks keyed by node name). Updated to seed the already-merged `$input` shape instead, preserving every existing assertion's intent. Not in Task 3's own `<files>` list (only `tests/n8n/ingestCarryMerge.test.mjs` was), but required by the plan's own acceptance criteria (`node --test tests/n8n/*.test.mjs` / `pytest tests/ -q` exit 0) — Rule 3 (blocking issue: the implementation change breaks tests coupled to the old mechanism).

## Issues Encountered

None beyond the two Rule-1 bugs above, both auto-fixed and covered by new test assertions.

### Gate 1 — observed live 2026-09-10 (deferred from Task 2, run at end-of-phase UAT)

Deployed + bounced disarmed (five PUTs at 200; live node counts 30/50/218/45/43 equal the
committed JSON; both write flags `"false"` everywhere). One single-lane ingest batch (two
`.invalid` emails, association path starved, review path carrying both rows).

- **Settled, not stuck.** Execution `12200`: `status: success`, 6.1s wall. Re-run through the
  fixed client path, execution `12202`: `success`, 3.7s, recovery settled in 26s.
- **Every Merge fired exactly once**, including `Ingest Merge Response` (7 items in from all
  lanes, `Build Ingest Response` 2 rows out — never 4). No Merge waited on an input that never
  fired.
- **Live `settings.executionOrder`: ABSENT** — `settings: {}` on all five workflows. The engine
  default applies; nothing here can be read as `v1` or `v0`.
- **Zero writes.** HubSpot contact search on both emails: `total: 0`.
- **Mechanism: the lane sentinels, not `alwaysOutputData`.** `Associate Lane Sentinel` emitted 1
  item and satisfied the starved association input; `HubSpot Associate Company` never ran at
  all (absent from runData), so its `alwaysOutputData` contributed nothing. `Set Review` carried
  the 2 review rows; `Review Lane Sentinel` emitted 0. The IF-based flags did nothing observable.
- **Merge node shape accepted by the live engine:** `typeVersion 3.2`, `combineByPosition` carry
  Merges and the `combineAll` broadcast all ran as the committed JSON declares.
- **Finding (client, not n8n):** `dispatch.py` sent `run_id` as a multipart part WITH a
  Content-Type; n8n filed it under `$binary`, `$json.body` was `{}`, `Set Config` echoed
  `run_id: null`, and the recovery poll ran to its 600s bound. The same idiom carried
  `source_by_field` since Phase 62 — never observed live until now. Fixed in-session (2-tuple
  parts, no Content-Type; test pin inverted) — see 70-UAT.md gap `G-70-1`.

## User Setup Required

None — no external service configuration required. Nothing armed; the disarmed Task 2 probe (Gate 1) remains deferred to end-of-phase UAT.

## Next Phase Readiness

- The ingest lane is now the reference implementation for the whole phase: one append-mode convergence Merge (3 inputs), 8 combine-mode carry merges, zero by-name reads, ack-only webhook, runData-only client recovery.
- `splice_carry_merge_after` and the `combineAll` walker support are ready for plan 70-04 (the enrichment lane, 119 remaining violations) and 70-06 (review-decision lane, 12 remaining violations) to reuse directly.
- Open UAT item carried forward: **Gate 1** (Task 2's disarmed Merge-semantics probe) — see `70-DEFERRED-GATES.md`. Not re-scoped by Task 3; the probe targets the same convergence Merge and `alwaysOutputData` placement Task 2 built, now with more carry merges layered on top of the identical graph shape.

## Self-Check: PASSED

- `[ -f tests/n8n/ingestCarryMerge.test.mjs ]` → FOUND
- `[ -f scripts/build_cloud_workflows.py ]` → FOUND (splice_carry_merge_after present)
- `git log --oneline --all --grep="70-02"` → FOUND (`e9988b8`, `87c7cd4`, `ec247f8`, `dad2a8f`, plus this plan's earlier commits)
- Re-ran every Task 3 acceptance criterion: `detect_by_name_reads(build_cloud())` == 0; `node --test tests/n8n/*.test.mjs` exit 0 (976 pass); `.venv/bin/python -m pytest tests/ -q` exit 0 (4627 passed, 154 skipped); `operator-claude-plugin` pytest exit 0 (2850 passed, 5 skipped); two consecutive `build_cloud_workflows.py` runs byte-identical.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*
