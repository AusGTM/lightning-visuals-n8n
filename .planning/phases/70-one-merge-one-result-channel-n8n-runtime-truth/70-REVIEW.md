---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
reviewed: 2026-09-10T08:59:50Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - scripts/build_cloud_workflows.py
  - scripts/prove_phase70_runtime.py
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/report.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/tests/test_chunking.py
  - operator-claude-plugin/tests/test_scale_up_retired.py
  - operator-claude-plugin/tests/test_watch_settle_reporting.py
  - operator-claude-plugin/tests/test_written_records.py
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/buildResponseMarkerFilter.test.mjs
  - tests/n8n/enrichmentBatchRefusal.test.mjs
  - tests/n8n/scaleUpRefused.test.mjs
  - tests/n8n/sj3DispatchGate.test.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
  - tests/n8n/zoominfoLaneFlow.test.mjs
  - tests/test_enrichment_lane_dedup.py
  - tests/test_merge_helpers.py
  - tests/test_no_by_name_reads.py
  - tests/test_subworkflow_ref_rebinding.py
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 70: Code Review Report

**Reviewed:** 2026-09-10T08:59:50Z
**Depth:** standard
**Files Reviewed:** 21 (required-reading set; four additional files —
`scripts/enrich_coverage_companies.py`, `scripts/fix_sfv_region.py`,
`scripts/probe_company_propose_mode.py`, `scripts/prove_zoominfo_balance.py` — spot-checked
per the review brief's instruction to confirm they carry only the WR-03 reference cleanup,
which they do)
**Status:** issues_found (1 Warning, 4 Info, 0 Critical)

## Summary

This is the third review of phase 70, scoped to commits `7a9f1e5..HEAD`: the five WR-fix
commits already reported in `70-REVIEW-FIX.md` (`a1e6ce5..f59010e`), plus gap-closure round
2 (plans 70-13/14/15, `b5bcf33..cb669fe`) responding to the G-70-5 self-dispatch runaway
(135 child executions in six minutes, executions 12211-12348, 2026-09-10).

Round 2's actual work — deleting the self-referencing `Execute Workflow` fan-out lane
(D-70-24), adding a generation-time refusal for any future self-dispatching node
(`assert_no_self_dispatch`, D-70-26a), fixing the marker-identity leak at both response
builders (D-70-25), and pinning execution 12316's still-unexplained walker divergence as a
prohibition guard rather than a modelled mechanism (D-70-26b) — is largely solid. I traced
each piece against the actual diff (not just the commit messages), re-ran every relevant test
suite, and re-derived the headline claims independently rather than trusting the stated
numbers:

- `node --test tests/n8n/*.test.mjs` → **1075/1075** green (confirmed, not just quoted).
- `.venv/bin/python -m pytest -q` (root) → **4700 passed, 154 skipped** (confirmed).
- `operator-claude-plugin` pytest → **2864 passed** (confirmed).
- `scripts/build_cloud_workflows.py` regeneration is idempotent (`git status --porcelain
  n8n/` clean before and after a fresh run).
- `n8n/wf_enrichment_cloud.json` → **287 nodes, 0 `n8n-nodes-base.executeWorkflow` nodes**
  (confirmed by direct JSON inspection, not the commit message).
- `n8n/wf_scheduled_maintenance_cloud.json` → 43 nodes, exactly one `executeWorkflow` node
  (`SJ-3 Dispatch To Enrichment`, the one exempted pair) — confirmed.

Specific things I verified rather than took on faith:

- The five "pre-fork" sentinels the commit message claims were re-sourced from `Parse
  HubSpot Event` (after the deleted `IF Scale Up Route` splice was removed) are exactly the
  five I found sourced from that node: `Contacts Absent Sentinel`, `Companies Absent
  Sentinel`, `Unsupported Absent Sentinel`, `Recompute Not Requested Sentinel`, `Recompute
  Requested Sentinel` (build_cloud_workflows.py:7683-7822). Count matches the claim.
- D-70-25's marker-identity fix: `ROW_IDENTITY_KEYS_JS`/`hasRowIdentity`
  (build_cloud_workflows.py:63-91) is defined once and applied at both `ENRICH_BUILD_
  RESPONSE` (line 5770, positioned after the existing negative filter and before the
  outcome-contract projection — correct order, since the projection is what would otherwise
  make a marker indistinguishable) and `BUILD_INGEST_RESPONSE` (line 692). The eleven
  `buildResponseMarkerFilter.test.mjs` cases — including the two shapes actually recovered
  live in Gate 5 (`70-RUNTIME-VERDICT.json`) — all pass, and the one genuinely load-bearing
  case (a raw HubSpot write response `{id, properties}` with none of the other five identity
  keys) is asserted to survive, not just the marker-drop cases.
- Every symbol the retirement was supposed to remove is actually gone, not just unreferenced
  from the two files the commit touched: repo-wide grep for `scale_up`, `fan_depth`,
  `child_execution_ids`, `include_children`, `SCALE_UP_DISPATCH_NODE`,
  `SCALE_UP_MAX_FAN_DEPTH`, `Dispatch Self`, `Build Scale Up Fan-Out`/`Ack`, `IF Scale Up
  Route` returns nothing outside test/fixture files that document the retired mechanism by
  name (which is correct — those are history, not dead code). No unused imports were left
  behind in `chunking.py`/`watch.py` (checked via AST, not just eyeballing the diff).
- `tests/n8n/lib/walkWorkflow.mjs` is byte-identical to the commit that closed plan 70-13
  (`git diff c6dc8fe..HEAD -- tests/n8n/lib/walkWorkflow.mjs` is empty) — confirms D-70-26b's
  claim that no plan-convenient walker change was smuggled in to make execution 12316's
  divergence look modelled rather than refused.
- WR-01's reshaped test fixtures in `test_watch_settle_reporting.py` (`_execution_with_write_
  node`, lines 404-425) still carry the load-bearing shape: `exec-a` wrote, `exec-b` produced
  a *present-but-empty* `HubSpot Update` run and is folded last. That is exactly the ordering
  that would fail under the pre-fix `dict.update` (the empty run would erase the real write)
  and passes under the union fix — the reshape from a parent/child pair to two top-level
  executions did not accidentally make the test vacuous.
- `CLAUDE.md` §13.0.2/§13.0.3 is internally consistent with the code on the load-bearing
  claims: the retirement narrative, the 291→287 node-count delta, the "nothing armed"
  deployment-gap table, and the `70-DEFERRED-GATES.md` gate renumbering (Gates 7/8/9 added,
  Gate 6 superseded) all line up with what the commits actually did. One phrasing imprecision
  noted below (IN-03).

## Warnings

### WR-08: `assert_no_self_dispatch`'s exemption is keyed on the caller-supplied label, not the workflow body's own name — it can widen without editing `_SELF_DISPATCH_EXEMPTIONS`

**File:** `scripts/build_cloud_workflows.py:11334` (and the docstring's contrary claim at
11303-11309/11336-11340)
**Issue:** The exemption check is `if (name, node_name) in _SELF_DISPATCH_EXEMPTIONS`, where
`name` is the string literal each `main()` call site passes to `_assert_generation_contracts`
(e.g. `"wf_scheduled_maintenance_cloud"`) — never `wf.get("name")`, the workflow body's own
intrinsic display name. Rule 1 (the unconditional self-reference check, lines 11325-11333)
still correctly compares `target_id`/`target_name` against the *actual* `wf_id`/`wf_name` of
the body being checked, so a genuine self-reference is caught regardless of label. But for a
node that dispatches to some *other* workflow (rule 2, the exemption-gated case), the
exemption only ever tests the caller's label string. The docstring states, twice, that
"adding a new dispatch must be a deliberate decision that edits this list" and that "no other
executeWorkflow node may ship unless its (workflow, node) pair is named in
`_SELF_DISPATCH_EXEMPTIONS`" — but a cross-workflow `executeWorkflow` node literally named
`"SJ-3 Dispatch To Enrichment"`, added to any *other* build (say, a future `wf_review_
decision_cloud` that copies SJ-3's dispatch pattern), would pass this check for free the
moment its build's `main()` call site is mislabelled with `name="wf_scheduled_maintenance_
cloud"` (a plausible copy-paste-and-forget-to-rename mistake when adding a ninth `main()`
block) — with `_SELF_DISPATCH_EXEMPTIONS` never touched. None of the six tests in
`tests/test_merge_helpers.py:394-452` — including the two tests explicitly titled "the
exemption cannot widen" — exercise this path; both widening tests vary the *node's* workflow
identity/name, never the *caller's* `name` argument passed into the function under test.
Today's eight `main()` call sites are all correct hardcoded literals, so there is no live
exposure, but the guarantee the docstring makes is not actually enforced by the code as
written — it holds only because every current caller happens to pass the right label, not
because the function verifies it.
**Fix:** Key the exemption tuple on the workflow's own intrinsic name instead of (or in
addition to) the caller-supplied label — `(wf.get("name"), node_name)` — so a mislabelled
`name` argument at a `main()` call site cannot silently confer an exemption that was never
granted to that workflow body. Add a test that passes a *correct* `wf` body but a
*mislabelled* `name` argument and asserts the exemption still does not apply.

## Info

### IN-01: `written_records.append_chunk`'s docstring still undercounts its call sites

**File:** `operator-claude-plugin/scripts/written_records.py:486-503` (docstring),
call site at `operator-claude-plugin/scripts/chunking.py:662`
**Status:** carried forward from the prior review (6be2894), **still present, unchanged by
this round** — re-checked both files against current HEAD rather than trusting the old line
numbers.
**Issue:** The docstring claims "TWO call sites remain, both at the write itself, never in a
caller" and names only `dispatch.dispatch` and `review_decision.submit_decision`. It
separately explains that `chunking.dispatch_plan`'s own former call site was retired by
D-70-07. It never mentions the third, still-live call site inside
`chunking.dispatch_and_recover` (`written_records.append_chunk(outcome.run_id, 0, rows)` at
chunking.py:662) — which is exactly the kind of caller-not-write-site call the docstring's
own framing says doesn't happen. Not a functional bug (`chunk_index=0` is harmless there,
identical to the other two sites), but a future reader auditing "who calls this" for a
fourth, unaccounted-for site would be misled by the "TWO... never in a caller" claim.
**Fix:** Update the docstring to name three call sites, or fold `dispatch_and_recover`'s
site into the same enumeration, noting it is a caller (not "the write itself") by design
(D-70-09's ledger-gate placement).

### IN-02: `split_merge_into_stages` changes `Build Response Merge`'s row concatenation order, undocumented

**File:** `scripts/build_cloud_workflows.py:8189-8196` (line numbers shifted from the prior
review's 8276-8283 due to the scale-up lane deletion earlier in the file; content unchanged —
re-verified against current HEAD)
**Status:** carried forward from the prior review, still present, not touched by this round.
**Issue:** The three groups passed to `split_merge_into_stages` for `Build Response Merge` —
`[0,1,2,3,11,12]`, `[4,5,6,7,8,13,14]`, `[9,10]` — are not a contiguous partition of the
original 0..14 index range. Under append-mode concatenation (both the walker's model and,
per its own docstring, n8n's real behaviour), the output row order is now
stage-1-items-then-stage-2-then-stage-3, not numeric input order — a row that used to arrive
at position 11 now arrives after everything in group 1's indices, changing its relative
position versus a row on indices 4-8. `split_merge_into_stages` makes no contractual claim
about preserving numeric order (only per-input sentinel/producer coverage), so this isn't a
broken contract — but it's an undocumented behavioural change from the pre-split single
Merge.
**Why it still doesn't rise to Warning:** every downstream consumer re-checked this round
(`Filter Build Response Rows`, `Build Ack`, `report.reconcile`, the plugin's
`merge_enriched`) correlates rows by identity (`row_id`/`email`/`hs_object_id`), never array
position, and `prove_phase70_runtime.py`'s own comparator is explicitly order-insensitive by
design. No test in either round's scope asserts order-independence for a batch that
genuinely mixes contacts, companies, and an unsupported-object-type row crossing all three
stage-group boundaries in one execution.
**Fix:** none required functionally. A one-line comment at the `split_merge_into_stages`
call site noting that global row order is not preserved across the split (only
per-stage-group order) would pre-empt a future reader assuming otherwise.

### IN-03: A round-2 comment edit left a stale characterization of `async_ack` as a currently-generalized "invariant" flag

**File:** `tests/n8n/sj3DispatchGate.test.mjs:312-314` (edited this round, by `bfdf1c8`)
**Issue:** The comment reads "§13.0.2 generalizes the same invariant to `async_ack` and
`source_by_field`." `CLAUDE.md` §13.0.2 does not generalize an active invariant to
`async_ack` — it documents `async_ack` as **retired** (D-70-07): the ack is now
unconditional, `async_ack` opts into nothing, and a caller passing it is silently ignored.
Keeping `"async_ack"` in the test's `REQUEST_LEVEL_FLAGS` absence-check array (line 332) is
harmless and arguably still correct (asserting SJ-3 never carries it costs nothing), but the
comment's citation implies §13.0.2 still treats it as a live, generalized flag requiring the
same guard as `recompute`/`source_by_field` — which is the state before D-70-07, not the
current one. This comment was touched in the same commit that correctly removed `scale_up`
from the same line, so the `async_ack` half of the edit was a smaller, missed pass.
**Fix:** Reword to something like "§13.0.2 lists `source_by_field` as the other live
request-level flag; `async_ack` is kept in this check only because a caller silently passing
it must still assert absence-of-effect, not because it remains an active invariant."

### IN-04: `CLAUDE.md`:2423 states `scale_up` "is normalized in `Parse HubSpot Event`" one paragraph before explaining it no longer is

**File:** `CLAUDE.md:2423-2427`
**Issue:** Line 2423 states "`recompute` and `scale_up` are booleans normalized in `Parse
HubSpot Event`... They describe the REQUEST, not a row" — grouping `scale_up` with
`recompute`'s still-current behavior (read, then written onto the per-row event object). Four
lines later, 2427 clarifies `scale_up` is retired and the fan-out lane deleted; per the
generator's actual code (`build_cloud_workflows.py`'s enrichment `Parse HubSpot Event` body),
`scale_up` today is read and checked for refusal but never "normalized" onto anything — the
row-level fields it used to set are explicitly gone ("the two fan-out fields that used to
ride every row from here are gone with the lane that read them"). Read in isolation, 2423
is stale; read with 2427 immediately following, the correction lands before a reader could
act on the stale claim, so this is a wording precision issue, not a claim anyone would be
misled by in practice.
**Fix:** Optional. Reorder or reword 2423 to say `scale_up` "used to be normalized... is now
read only to refuse the request," matching 2427's framing, rather than grouping it with
`recompute`'s still-current behavior.

### Carried forward, resolved or non-issues (from the prior review, not re-classified as new findings)

- **Prior IN-02** (`scripts/prove_zoominfo_balance.py`'s duplicated `prove_async_recovery.py`
  self-reference in a comment) — **resolved**, confirmed on disk: the WR-03 fix commit
  (`6a15a64`) repointed the comment to `prove_phase70_runtime.py` as an incidental side
  effect of the broader reference cleanup. No duplicate reference remains.
- **Prior IN-03** (review-context file-disposition note about
  `scripts/probe_company_propose_mode.py`) — was never a code defect, just a mismatch in a
  prior review brief's instructions; nothing to track in the codebase.

---

_Reviewed: 2026-09-10T08:59:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
