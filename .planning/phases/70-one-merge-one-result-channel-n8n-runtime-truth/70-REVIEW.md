---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
reviewed: 2026-09-09T22:38:47Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - n8n/code/matchProposal.js
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/config_gate.py
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/report.py
  - operator-claude-plugin/scripts/report_enrichment.py
  - operator-claude-plugin/scripts/run_state.py
  - operator-claude-plugin/scripts/scheduled_arm.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/scripts/written_records.py
  - scripts/bounce_n8n_workflows.py
  - scripts/build_cloud_workflows.py
  - scripts/enrich_coverage_companies.py
  - scripts/fix_sfv_region.py
  - scripts/prove_phase70_runtime.py
  - scripts/prove_async_recovery.py
  - scripts/prove_zoominfo_balance.py
  - scripts/remediate_veto_companies.py
  - tests/n8n/lib/walkWorkflow.mjs
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_review_decision_cloud.json
findings:
  critical: 0
  warning: 6
  info: 3
  total: 9
status: issues_found
---

# Phase 70: Code Review Report

**Reviewed:** 2026-09-09T22:38:47Z
**Depth:** standard
**Files Reviewed:** 23 (primary set) — 8 read/diffed in full detail, remaining source files
diffed against the pre-phase commit (`cc182ca`) and cross-checked with grep/targeted reads
for the specific symbols named in the review brief.
**Status:** issues_found

## Summary

This phase retires a real, well-evidenced defect class (by-name `$('Node')` reads across
n8n's per-inbound-edge run model, a two-channel client result path, a fallback-laddered
write gate) and does so with an unusually high density of self-caught Rule-1 bugs, each
with its own regression test — the seven plan SUMMARYs read more like an audit log than
marketing copy, and most of the obvious failure modes an adversarial reviewer would reach
for (starved Merge inputs, refusal-vs-permit race on a shared Merge input, cross-lane
carry-merge misalignment) are already found, fixed, and pinned by the authors themselves.

That said, three of this review's findings are new (not named in any 70-0N-SUMMARY.md or
70-DEFERRED-GATES.md): a cross-execution `runData` merge in `watch.py` that silently
collapses same-named-node data by simple `dict.update()` rather than a true per-execution
union; a `lane="ingest"` code path in `chunking.dispatch_and_recover` that is unreachable
dead code contradicting the 70-06 plan's own narrative of where ingest reconciliation
happens; and a stale live-proof script (`scripts/prove_async_recovery.py`) that would
produce a false verdict if run today, already flagged in prose but left un-deleted and
un-guarded. None of these rise to Critical: the reachable production code paths for the
gated writes (the phase's actual safety-critical surface) are behaviourally sound by my
reading and by the extensive self-documented walker-driven testing. The findings below are
Warnings and Info items — real, but none blocks correctness of what ships disarmed today.

I did not re-derive n8n's own runtime behaviour (settling, `numberInputs` ceilings,
`alwaysOutputData` placement) independently — that is explicitly deferred to Gates 1,
70-05-A and 3 in `70-DEFERRED-GATES.md`, which the phase's own context (`70-CONTEXT.md`)
marks as locked, non-findable ground truth for this review. I restate the one open risk
from that deferred set that most threatens the phase's central claim (`Build Response
Merge`'s 15 inputs vs. n8n's documented 2–10 range) because it is unresolved and
consequential, not because it is undocumented — it already is, in 70-05-SUMMARY.md and
70-07-SUMMARY.md.

## Warnings

### WR-01: Cross-execution `runData` merge in `watch.recover_async_dispatch` uses `dict.update`, not a per-execution union

**File:** `operator-claude-plugin/scripts/watch.py:620-635` (the `merged_run_data.update(rd)` loop inside `recover_async_dispatch`)
**Issue:** When more than one execution contributes to a single recovered batch (a
multi-chunk send where `landed > 1`, or a `scale_up` parent plus its children), the
function folds every execution's `runData` into one dict:
```python
merged_run_data = {}
for execution in list(settled) + children:
    responses.extend(_response_rows(execution, response_node))
    rd = report._run_data(execution)
    if isinstance(rd, dict):
        merged_run_data.update(rd)
```
`runData` is keyed by **node name**, and every execution of the same workflow shares the
same node names. `dict.update()` therefore does not union two executions' output for
"HubSpot Update" — it **replaces** whichever execution's entry was inserted first with
whichever was inserted last, in iteration order. The function's own docstring promises
this merged value to "a caller that needs to cross-reference a write node's own output,
e.g. `report.reconcile`" — i.e. it is explicitly designed to be used for exactly the kind
of per-node truthiness check `report.reconcile`/`_write_node_produced_output` performs.
If execution A's "HubSpot Update" node produced 3 successful items and execution B's same
node produced 0 (ran, but every row was gated), and B is folded in after A, the merged
value for "HubSpot Update" silently becomes A's confirmed success **replaced** by B's
empty result — a downstream `_write_node_produced_output` check would then report `False`
for a write that genuinely happened in execution A. The reverse (B's failure overwritten
by A's success, hiding a real B failure) is equally possible depending on iteration order.
**Why it matters:** This is exactly the class of bug Phase 70 exists to retire —
"the row's outcome of record [not being] the write node's actual output" (D-70-06) — except
one level up, at the execution-merge boundary the phase itself introduced in Plan 06's
`include_children`/multi-chunk generalisation. It is currently *not* reachable by the one
caller that does call `report.reconcile` (`dispatch.dispatch` always sends exactly one
request, so `landed` is always 1 — see WR-02), so no live misreport can occur through
today's call graph. But the function is general-purpose, documented as safe for this use,
untested for `landed > 1` combined with `reconcile`, and one line of a future caller
(or a fix to WR-02) turns this into a live silent misreport.
**Fix:** Key the merge by execution as well as node name (e.g. `merged_run_data[node] =
merged_run_data.get(node, []) + rd[node]`, or keep a list of per-execution `run_data`
dicts and have `report.reconcile` iterate all of them, treating a node's write as
confirmed if *any* execution's copy of that node produced output). Add a test with two
settled executions where only one produced output for the same write node, asserting the
merge does not lose the successful one regardless of iteration order.

### WR-02: `chunking.dispatch_and_recover`'s `lane="ingest"` reconciliation branch is unreachable dead code

**File:** `operator-claude-plugin/scripts/chunking.py:666-675`
**Issue:** `dispatch_and_recover` accepts a `lane` parameter and, when `lane == "ingest"`,
routes the recovered rows through `report.reconcile(rows, run_data)`. Grepping every call
site in the plugin (`preingest.py:904`, `scheduled_arm.py:240`, and the one documented in
`enrich-records/SKILL.md:512`) shows none of them ever pass `lane="ingest"` — they all use
the default (`"enrichment"`). The actual ingest-lane reconciliation happens entirely
through a separate function, `dispatch.dispatch` (`operator-claude-plugin/scripts/
dispatch.py:139-145`), which calls `watch.recover_dispatch(..., lane="ingest")` directly
and then `report.reconcile` itself — never through `dispatch_and_recover` at all. The only
place `lane="ingest"` is ever passed anywhere in the plugin's scripts is that one call
inside `dispatch.py`.
**Why it matters:** 70-06-SUMMARY.md's own Decisions Made narrates this as one shared,
parameterised mechanism ("D-70-06: `report.reconcile` is SHARED... and applied on the
INGEST lane only... `dispatch.dispatch` already routes the ingest lane through it" —
correctly describing `dispatch.py`'s own path, but the `chunking.py` branch reads as if it
were also load-bearing for that same claim). It is not: it is dead code that cannot be
exercised by any current caller, which means it has no test coverage exercising the
`True` branch through `dispatch_and_recover` itself (only through `dispatch.dispatch`'s
own separate call), and a reader tracing "how does the ingest lane get reconciled"
through `chunking.py` will draw an incorrect picture of the actual call graph.
**Fix:** Either delete the `lane` parameter and the dead branch from
`chunking.dispatch_and_recover` (since `dispatch.py` never calls it), or, if a future
ingest caller is meant to route through `dispatch_and_recover`, wire that caller now and
add a test that exercises `lane="ingest"` through this specific function rather than only
through `dispatch.dispatch`.

### WR-03: `scripts/prove_async_recovery.py` is stale against the D-70-07 contract and would produce a false verdict if run

**File:** `scripts/prove_async_recovery.py:134, 151, 203`
**Issue:** The script's whole thesis is a *differential* proof — send the same batch twice,
once without `async_ack` and once with `async_ack=True`, and assert the two recovered row
sets match (`"twice (once sync, once async_ack=true)"`). Under D-70-07 (landed in this
phase), there is no longer a synchronous row-carrying path to differential against: every
send answers with the same ack shape unconditionally, and `chunking.dispatch_plan` silently
swallows `async_ack` as a legacy kwarg (`**_ignored_legacy_kwargs`). The script still calls
`dispatch_plan(..., async_ack=True, ...)` at line 134 and still asserts
`"the synchronous response for the async_ack=true send did not match..."` at line 151 —
a comparison that is now comparing the ack-only response against itself, proving nothing
about what it claims to prove.
**Why it matters:** This is a live-proof driver (the same class of tool `70-DEFERRED-GATES.md`'s
Gate 3 depends on), and 70-07-SUMMARY.md's own "Issues Encountered" section already names
this exact staleness ("it would produce a false STOP verdict if run today... Worth a
follow-up deletion"). It is disclosed but not fixed, not deleted, and not guarded — nothing
stops an operator or a future agent from running it and trusting a misleading result, since
its own refusal gates (`ALLOW_ASYNC_RECOVERY_PROOF`, the wrong-instance guard) say nothing
about the contract it tests being retired.
**Fix:** Delete the script (its supersession is `scripts/prove_phase70_runtime.py`, per the
70-06/70-07 summaries), or, if kept for its historical verdict JSON, add a refusal at the
top of `main()` that raises before constructing any transport, naming D-70-07 and pointing
at the replacement — the same "refuse before spend" discipline this phase applies
everywhere else (`watch.require_executions_api`, `config_gate.CAPABILITY_KEYS`).

### WR-04: `Build Response Merge` (enrichment lane) has 15 inputs against n8n's documented 2–10 `numberInputs` range

**File:** `scripts/build_cloud_workflows.py` (`merge_node`, `Build Response Merge`'s
construction site) / `n8n/wf_enrichment_cloud.json`
**Issue:** `merge_node`'s own comment block cites n8n-io/n8n source for
`numberInputsProperty` documenting a 2–10 range; `Build Response Merge` is built with 15
inputs after this phase's refusal-lane widening (D-70-14's `wire_gate_refusal_lane`, three
sentinel inputs per gate × four enrichment gates, on top of the original 11). No committed
workflow in this repository has ever contained a native Merge node before this phase, and
this is the single largest one shipped.
**Why it matters:** the entire "one merge, one result channel" thesis depends on this node
accepting the graph as built. If the live n8n Cloud engine enforces the documented ceiling
(rejects the node on import, silently drops inputs above 10, or otherwise misbehaves), the
enrichment lane's central convergence point — the node every terminal branch of both
contacts and companies funnels through — fails, and every offline-GREEN test in this phase
that walks the same graph through `tests/n8n/lib/walkWorkflow.mjs` (which models Merge
inputs without any such ceiling) would have validated a graph the real engine refuses.
This is already flagged as a carried risk in 70-05-SUMMARY.md ("Issues Encountered") and as
the "carried caveat to observe FIRST" in `70-DEFERRED-GATES.md` Gate 3 — restated here
because it is the single highest-consequence open item in the whole phase and this review
would be incomplete without naming it directly rather than only by reference.
**Fix:** No code fix within this phase's stated scope — Gate 3 (the deferred live run) is
the correct place to resolve it. If Gate 3 shows the ceiling is real, the fix is structural
(a second, intermediate Merge stage collapsing the ten sentinel inputs to one before they
reach `Build Response Merge`) and should be planned before any live arming, not discovered
by an armed batch failing to converge.

### WR-05: Triplicated write-authorization predicate on the ingest lane's association sentinel is a silent-drift risk on manual arming

**File:** `scripts/build_cloud_workflows.py:1250-1266` (`Associate Lane Sentinel`'s jsCode)
**Issue:** `_writeSafetyAllows` is now evaluated in three places for one association write:
the update's own spliced gate, the (removed) association gate's former location, and —
still present — `Associate Lane Sentinel`'s own copy of the predicate, needed only to keep
`Ingest Merge Response`'s association-lane input correctly starved-or-fed. The comment at
the site is explicit that this is deliberate graph plumbing, not a second authorization,
and 70-05-SUMMARY.md names the consequence plainly: "any arming run (or hand-rolled test
helper) that rewrites the gates but not the sentinel reproduces the dropped-association bug
on a real batch," noting that `n8n_arming.set_write_safety` does cover all three declaring
nodes today.
**Why it matters:** this is a correctly-reasoned design with a correctly-identified single
point of failure (a manual arm, or a future refactor of the arming tool, that touches two
of the three `ALLOW_HUBSPOT_RECORD_WRITES`-declaring nodes and misses the third) that
reproduces exactly the silent-data-loss class this phase spent its whole Plan 05 fixing
(the shared-merge-input race). It is disclosed, not hidden, but the disclosure is prose in
a plan summary, not an enforced invariant in code — nothing raises if a future edit adds a
fourth `ALLOW_HUBSPOT_RECORD_WRITES`-declaring node without updating whatever inventory
`n8n_arming.set_write_safety` uses to find all of them.
**Fix:** Add a generation-time or arming-time assertion (in the same spirit as
`assert_no_by_name_reads`/`assert_write_request_emitters`) that counts the
`ALLOW_HUBSPOT_RECORD_WRITES`-declaring nodes per lane and fails loudly if the count drifts
from a pinned expectation, rather than relying on a human reading three separate places
correctly on every future touch.

### WR-06: `deleted` files/functions still referenced by name only in comments — verify no functional drift, not currently a defect

**File:** `scripts/build_cloud_workflows.py:2263, 9181, 10801-10854`; `tests/test_no_by_name_reads.py:7,25,130`
**Issue:** `n8n/code/nodeRunRecovery.js` is deleted (confirmed absent on disk), but its
exact function-signature string is intentionally reconstructed by string concatenation in
`_run_recovery_marker()` so `detect_by_name_reads`/`assert_no_by_name_reads` can still
recognise a reintroduction of the retired idiom. This is a deliberate, well-reasoned
mechanism (documented in 70-04-SUMMARY.md's key-decisions) and not a bug by itself — listed
here as a Warning only because it is a fragile invariant (a detector whose fingerprint is a
hand-maintained string copy of a deleted file's signature will silently stop detecting the
pattern if the deleted file's original signature is ever misremembered or the marker
constant edited without re-deriving it from a real historical copy). No test pins the
marker string against the actual git history of the deleted file's signature line — only
against itself.
**Fix:** Low priority. Consider a one-time test that checks out the deleted file's blob
from git history (`git show <sha>:n8n/code/nodeRunRecovery.js`) and asserts the marker
matches a substring of it, so the fingerprint can never drift from what was actually
deleted.

## Info

### IN-01: `written_records.append_chunk`'s docstring undercounts its own call sites

**File:** `operator-claude-plugin/scripts/written_records.py:484-489`
**Issue:** The docstring, updated in this phase, states "TWO call sites remain, both at the
write itself" and names `dispatch.dispatch` and `review_decision.submit_decision`. A third
live call site exists: `operator-claude-plugin/scripts/chunking.py:682`, inside
`dispatch_and_recover`, added by this same phase (Plan 06). It is not a functional problem
(`chunk_index=0` is harmless metadata there, same as the other two sites), but the
docstring's own "TWO call sites... never in a caller" invariant claim is now inaccurate and
would mislead a future reader auditing for a fourth, unaccounted-for call site.
**Fix:** Update the docstring to name three call sites, or fold `chunking.py`'s site into
the same sentence as the other two.

### IN-02: Duplicated self-reference in a comment

**File:** `scripts/prove_zoominfo_balance.py:19-20`
**Issue:** "TWO GATES, BOTH BEFORE ANY TRANSPORT IS CONSTRUCTED (mirrors
prove_async_recovery.py and prove_async_recovery.py)" — the same filename is named twice
where two different sibling scripts were clearly intended (the pre-phase-70 text named
`prove_async_recovery.py` and the now-deleted `prove_scale_up_runtime.py`; the edit that
removed the deleted script's name left a duplicate rather than a single reference).
**Fix:** Trivial wording fix; harmless as-is.

### IN-03: Review-context file-disposition note is stale (not a code defect)

**File:** N/A — noted for the record only
**Issue:** The review brief's primary-files list states `scripts/probe_company_propose_mode.py`
was deleted alongside `n8n/code/nodeRunRecovery.js` and `scripts/probe_n8n_async_semantics.py`.
Only the latter two were actually deleted; `probe_company_propose_mode.py` still exists on
disk, migrated (not deleted) per 70-06-SUMMARY.md's own disposition table. This is a
mismatch in the reviewing instructions, not in the codebase, and required no code finding —
recorded here only so the discrepancy isn't silently absorbed as if it were verified true.

---

_Reviewed: 2026-09-09T22:38:47Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
