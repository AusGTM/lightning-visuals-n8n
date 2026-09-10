---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
reviewed: 2026-09-10T06:22:45Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/tests/test_dispatch_multipart.py
  - scripts/build_cloud_workflows.py
  - scripts/prove_phase70_runtime.py
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
  - tests/n8n/mergeInputContract.test.mjs
  - tests/n8n/writeGateShape.test.mjs
  - tests/n8n/ingestMixedBatch.test.mjs
  - tests/n8n/ingestTracerFlow.test.mjs
  - tests/n8n/enrichmentConvergenceMerge.test.mjs
  - tests/n8n/companyRecomputeLaneFlow.test.mjs
  - tests/n8n/linkedinLaneFlow.test.mjs
  - tests/n8n/researchErrorGateFlow.test.mjs
  - tests/n8n/reviewDecisionEndpoint.test.mjs
  - tests/test_merge_helpers.py
  - tests/test_phase70_rollback_bundle.py
  - tests/test_prove_phase70_runtime.py
  - tests/test_cloud_companies_branch.py
  - tests/test_cloud_contacts_branch.py
  - tests/test_enrichment_lane_dedup.py
  - tests/test_enrichment_list_branch.py
  - tests/test_remaining_credits_response.py
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 70: Code Review Report (incremental — gap-closure plans 70-08..70-12)

**Reviewed:** 2026-09-10T06:22:45Z
**Depth:** standard
**Files Reviewed:** 24 (commits `6be2894..HEAD`)
**Status:** issues_found (no Critical findings; this REVIEW.md replaces the prior
70-REVIEW.md dated 2026-09-09, which covered plans through the code-review sealed at
`6be2894`)

## Summary

This increment closes the gap the first review's WR-04 named directly: `Build Response
Merge`'s 15 inputs (over n8n's own documented 2-10 cap) is now split into three
lane-grouped stage Merges (≤10 inputs each), enforced from this commit forward by a
generation-time refusal (`assert_merge_input_contract`, composed at all 8 workflow write
sites in `scripts/build_cloud_workflows.py::main()`) and pinned by a structural test that
runs over every committed `n8n/wf_*.json` (`tests/n8n/mergeInputContract.test.mjs`). More
consequentially, this increment also retires a live, observed defect class the authors
found by pointing their own corrected walker at a frozen snapshot of the graph that ran
executions 12203 and 12206: a starved-lane sentinel's zero-item Code-node output was
racing (and sometimes beating) a slower, multi-hop real producer to a shared Merge input,
silently dropping real association/refusal rows while the run still reported success. The
fix (`_add_starved_lane_sentinel`'s "condition → gate → targets" shape, D-70-23) converts
that race into a logic question — a starved-lane sentinel's gate makes literally zero
delivery whenever the real producer would ever deliver, because a node fed zero items
never runs. I verified this is not merely asserted: `tests/n8n/writeGateShape.test.mjs`'s
"ingest, ARMED with a mixed verdict" test reproduces execution 12203's exact shape
(one permitted, one refused row, same company) against the **current** (fixed) committed
graph and asserts the permitted row's association now correctly reads `"associated"`
rather than `"not_confirmed"`. That is a genuine, targeted regression test for the exact
defect class this phase exists to retire, and it passes.

I re-verified the six Warnings carried from the prior review against the current code
(not assumed unchanged) — see "Carried Findings" below. Two of the six have materially
changed status: WR-04 is resolved at the structural level (the remaining risk — whether
the live n8n Cloud engine actually honours this Merge topology at all — is Gate 3, already
tracked and deliberately deferred, not a new finding), and WR-05's stated failure mode
("nothing raises if a future edit adds a fourth [write-flag-declaring] node without
updating whatever inventory `n8n_arming.set_write_safety` uses to find all of them") is
factually incorrect on inspection: that function scans every node's `jsCode` by regex —
there is no fixed inventory to go stale — and its own fail-closed re-scan
(`n8n_read.read_write_safety`) already documents "the declaring set is not stable ... and
both sets have grown." The remaining risk is narrower than WR-05 stated and I've
downgraded it accordingly.

I also found one new, real coverage gap (Warning) and one new, low-severity behavioural
note (Info) that no `70-0N-SUMMARY.md` names: the entire ZoomInfo-touching slice of the
new Merge/sentinel network (three carry Merges and their pass-throughs/gates) has
**zero dynamic (walker-replay) test coverage** — only the static structural contract
checks it — because the walker cannot execute the three ZoomInfo Code nodes' `await`
bodies and no test in the reviewed files ever sets `providers_requested` to include
`"zoominfo"`. And `split_merge_into_stages`'s grouping for `Build Response Merge`
reorders the merged row set relative to the original single-Merge's numeric-index
concatenation order — almost certainly benign (every consumer keys rows by identity, never
position) but an undocumented behavioural change worth a one-line note.

None of this rises to Critical. The reachable, safety-critical write-gate paths behave
correctly by my reading and by the phase's own unusually rigorous self-directed replay
testing (RED-first against the walker's own historical fidelity to two named live
executions, GREEN against the current graph on the exact scenario that broke).

## Carried Findings — re-verified against the current code, not assumed

### WR-01 (carried, STILL OPEN, unchanged): `watch.recover_async_dispatch`'s cross-execution `runData` merge is a plain `dict.update`, not a per-execution union

**File:** `operator-claude-plugin/scripts/watch.py:619-626`
Unchanged from the prior review — `merged_run_data.update(rd)` at line 626 still silently
replaces (never unions) one execution's per-node output with another's when more than one
execution contributes to a single recovery (a multi-chunk enrichment dispatch, or a
`scale_up` parent plus its children). I re-traced every live call path rather than
assuming the prior review's "not reachable" conclusion still holds:
- `dispatch.dispatch` (the ingest lane's only caller of `report.reconcile`) always uses
  `expected_chunk_count=1` and the ingest workflow (`n8n/wf_contact_ingest_cloud.json`)
  has no `Dispatch Self` node — confirmed by direct inspection — so `include_children`
  never actually finds a child execution on this lane, and the merge is never exercised
  with more than one execution's `runData`.
- `chunking.dispatch_and_recover` only calls `report.reconcile` when `lane == "ingest"`
  (chunking.py:672-675), and grepping every call site (`preingest.py:904`,
  `scheduled_arm.py:240`) confirms neither ever passes `lane="ingest"` — this branch is
  WR-02's dead code, so the buggy merge's output never reaches `reconcile` there either.
- `preingest.py`'s own `dispatch_and_recover` caller reads only `dispatched["rows"]` (a
  list, built by `.extend()`, immune to this bug) — never `dispatched["run_data"]`.

So WR-01 remains accurately described: real, present, general-purpose, documented as safe
for exactly the cross-reference use `report.reconcile` performs, and still not reachable
by any live call path today. One line of a future caller (or a fix to WR-02) still turns
it into a live silent misreport.
**Fix:** unchanged from the prior review — key the merge by execution as well as node
name, or keep a list of per-execution `run_data` dicts and have `report.reconcile`
iterate all of them, treating a node's write as confirmed if *any* execution's copy
produced output.

### WR-02 (carried, STILL OPEN, unchanged): `chunking.dispatch_and_recover`'s `lane="ingest"` branch is unreachable dead code

**File:** `operator-claude-plugin/scripts/chunking.py:666-675`
Re-verified: still only `dispatch.py`'s own internal call to
`watch.recover_dispatch(..., lane="ingest")` ever passes that lane name anywhere in the
plugin; `dispatch_and_recover`'s own `lane` parameter and its `if lane == "ingest":
rows = report.reconcile(...)` branch remain dead — no caller in this incremental scope
changed that. Same fix as before: delete the parameter and branch, or wire a real caller
and add a test that exercises it through this function specifically.

### WR-03 (carried, STILL OPEN, now more clearly obsolete): `scripts/prove_async_recovery.py` is stale against the fully-landed D-70-07 contract

**File:** `scripts/prove_async_recovery.py:134, 151, 203` — confirmed unchanged by this
increment (no diff against `6be2894`). The script still dispatches with
`async_ack=True` and still asserts a synchronous/async differential that D-70-07 (now
fully landed in this increment — `async_ack` is retired, not merely optional; per
CLAUDE.md §13.0.2, "the ack is now UNCONDITIONAL on both row-outcome lanes... there is no
longer a row-carrying response body to opt out of") has erased the premise of entirely.
`chunking.dispatch_plan` still silently swallows `async_ack` via
`**_ignored_legacy_kwargs` (chunking.py:404, confirmed present), so a run of this script
today would compare the ack-only response against itself and could report a false PROVEN
verdict. `scripts/prove_phase70_runtime.py` (reviewed above) is its evident, disarmed,
gated successor and already exists — the case for deleting `prove_async_recovery.py`
rather than guarding it is now stronger than it was in the prior review.
**Fix:** unchanged — delete, or add a refusal at the top of `main()` naming D-70-07 and
the replacement, before any transport is constructed.

### WR-04 (carried, RESOLVED at the structural level — not a new finding either way): `Build Response Merge`'s over-wide input count

**File:** `scripts/build_cloud_workflows.py` (`split_merge_into_stages`, called at line
8276) / `n8n/wf_enrichment_cloud.json`
The 15-input Merge this warning named is gone: `split_merge_into_stages` now splits it
into three lane-grouped stage Merges — `[0,1,2,3,11,12]` (contacts, 6 inputs),
`[4,5,6,7,8,13,14]` (companies, 7 inputs), `[9,10]` (whole-batch refusal, 2 inputs) — each
within n8n's documented 10-input cap, reconverging on the unrenamed `Build Response
Merge` (now itself only 3 inputs). This is enforced, not merely asserted in prose:
`assert_merge_input_contract` raises `ValueError` at generation time if any Merge exceeds
10 declared inputs, is composed at all 8 workflow write sites in `main()`, and
`tests/n8n/mergeInputContract.test.mjs` re-derives the same check independently over
every committed `n8n/wf_*.json` with an empty `PENDING` list (asserted exact, in both
directions — a workflow that stops satisfying the contract, or one that starts satisfying
it while still listed, both fail loudly). I confirmed `split_merge_into_stages` itself is
correct: the partition-completeness check (`seen != set(range(original_inputs))`) and the
per-group `max_inputs` check are both real generation-time refusals, tested directly in
`tests/test_merge_helpers.py::test_split_merge_into_stages_reconverges_on_the_original_merge_name`.

What is **not** resolved, and was never in this phase's own stated scope to resolve
offline: whether the live n8n Cloud engine actually honours native Merge nodes at all —
this repo has never observed one running live. That is Gate 3 in
`70-DEFERRED-GATES.md`, already disclosed there and in CLAUDE.md §13.0.2's Phase 70
addendum ("NOT DEPLOYED. NOTHING ARMED... no committed workflow in this repo has ever had
a native Merge node observed on the real engine"). I am not restating it as a new finding
— it is already named, already tracked, and deliberately deferred by the phase's own
design (`gsd-code-review`'s job is to catch what isn't already known, not to re-file a
disclosed and tracked risk).

### WR-05 (carried, CORRECTED — the specific failure mode described does not exist in production tooling): triplicated write-authorization predicate

**File:** `scripts/build_cloud_workflows.py:1250-1266` (`Associate Lane Sentinel`'s
jsCode) / `operator-claude-plugin/scripts/n8n_arming.py:100-150`
The underlying design fact WR-05 named is still accurate: `ALLOW_HUBSPOT_RECORD_WRITES`
is declared in three places on the ingest lane for plumbing reasons (the gate, and the
Merge-feeding sentinel that duplicates the predicate to keep `Ingest Merge Response`'s
association-lane input correctly starved-or-fed), and the comment at the site is explicit
that this is deliberate. But I checked the specific claim in WR-05's own "why it matters"
— "nothing raises if a future edit adds a fourth `ALLOW_HUBSPOT_RECORD_WRITES`-declaring
node without updating whatever inventory `n8n_arming.set_write_safety` uses to find all
of them" — against the actual implementation, and it does not hold:
`n8n_arming.set_write_safety` (unchanged by this phase; predates it) does not use a fixed
inventory at all. It scans every node's `jsCode` by regex
(`const\s+{flag}\s*=\s*[^;]+;`), rewrites every match it finds regardless of count, and
then performs a fail-closed re-scan via `n8n_read.read_write_safety`, whose own docstring
states plainly: "Scans EVERY node's code rather than a fixed node list: the declaring set
is not stable (`ALLOW_HUBSPOT_CREATE` is currently declared in 9 nodes and
`ALLOW_HUBSPOT_RECORD_WRITES` in 8, across three workflows, and both sets have grown)." A
future fourth declaring node would be picked up automatically by production arming, and
`set_write_safety`'s own re-scan would raise `ArmingRefused` rather than silently ship a
partial rewrite if it somehow weren't.
The residual risk is narrower than WR-05 stated: only a **hand-rolled test fixture**
that hardcodes an `ARMING_NODES` list (several test files in this review's scope do this
— `writeGateShape.test.mjs`, `ingestMixedBatch.test.mjs`,
`walkerEngineFidelity.test.mjs`) could drift from a future fourth declaring node and
under-arm a test scenario relative to what production arming would actually do — a
test-fidelity gap, not a production authorization gap.
**Fix:** low priority, and only for the test-fixture risk — consider deriving each
test's `ARMING_NODES` list from the same regex `n8n_arming.py` uses (scan the loaded
workflow for `ALLOW_HUBSPOT_RECORD_WRITES` declarations) rather than a hand-typed list,
so a test's simulated arming can never structurally lag production arming.

### WR-06 (carried, STILL OPEN, unchanged, low priority): hand-maintained deleted-file fingerprint

**File:** `scripts/build_cloud_workflows.py:11178` (`_run_recovery_marker`) — confirmed
unchanged by this increment. Still a deliberate, reasoned mechanism, still not pinned
against the actual git history of the file it fingerprints. No change in status.

## Warnings (new this increment)

### WR-07: the ZoomInfo-touching Merge/sentinel network has zero dynamic (walker-replay) test coverage — structural contract only

**File:** `tests/n8n/enrichmentConvergenceMerge.test.mjs` (and every other
`walkWorkflow`-driven test over `n8n/wf_enrichment_cloud.json` in this review's scope);
the affected graph nodes are `ZoomInfo Mint Carry Merge`, `ZoomInfo Mint Company Carry
Merge`, `ZoomInfo Usage Mint Carry Merge`, and their D-70-23 gated sentinels and D-70-20
pass-throughs in `scripts/build_cloud_workflows.py`.
**Issue:** Three Code nodes on this graph — `ZoomInfo Enrich`, `ZoomInfo Company`,
`ZoomInfo Usage` — contain `await` in their `jsCode`, which `tests/n8n/lib/walkWorkflow.mjs`
cannot execute (it runs Code-node bodies synchronously via `new Function`, and this
limitation is explicitly acknowledged elsewhere in the test suite —
`tests/n8n/mergeInputContract.test.mjs`'s `hasAwaitingCodeNode` bucket exists precisely to
exclude whole workflows from dynamic replay for this reason). Separately, and more
directly: the "IF ZoomInfo Enabled" gate's own condition
(`$json.providers_requested.includes('zoominfo')`, confirmed in
`scripts/build_cloud_workflows.py` around the `IF ZoomInfo Enabled` gate construction)
depends on a per-row `providers_requested` field. I checked every event-building helper
in `tests/n8n/enrichmentConvergenceMerge.test.mjs` (`contactEvent`/`companyEvent`) and
neither ever sets `providers_requested`, so no test in the reviewed suite ever routes a
row down the ZoomInfo lane at all — meaning the three ZoomInfo-adjacent carry Merges and
their gated sentinels (all touched by this phase's Plan 10/11 work — e.g. the
`IF ZoomInfo Needs Mint`/`IF ZoomInfo Company Needs Mint`/`IF ZoomInfo Usage Needs Mint`
pass-through retargets at `scripts/build_cloud_workflows.py:8239-8245`) have **only**
been checked by the static structural contract (`assert_merge_input_contract`: every
input has a producer, no sentinel/IF feeds a Merge directly, no Merge is over-wide) —
never by an actual replay proving the sentinel's condition logic correctly predicts
"will the real ZoomInfo lane deliver."
**Why it matters:** the static contract can prove an input is fed by *something*; only a
replay can prove that a sentinel's gate and its lane's real producer are truly mutually
exclusive (`mergeInputContract.test.mjs`'s own header says exactly this: "Static analysis
cannot tell a safe share from an unsafe one; only a replay can"). The one lane this phase
cannot dynamically replay is also the one lane in this graph that makes a real external
network call from inside a Code node — the shape most likely to have a genuine
timing/ordering subtlety the design elsewhere in this phase was built specifically to
catch. This gap is not named in any `70-0N-SUMMARY.md` or `70-DEFERRED-GATES.md` I read.
**Fix:** either (a) extend `tests/n8n/lib/walkWorkflow.mjs` to stub an `await`-containing
Code node's body behind an injectable async-safe shim (mirroring the existing `httpStubs`
pattern) so it can be driven synchronously in a test, or (b) if that is out of scope,
explicitly document the gap (a short note in `70-DEFERRED-GATES.md` or this phase's own
summary) so a future reader doesn't assume "the whole graph is walker-verified" when one
provider's lane specifically is not — and treat Gate 3's live run as the only real
evidence for that slice until then.

## Info

### IN-04: `split_merge_into_stages`'s lane grouping changes `Build Response Merge`'s row concatenation order

**File:** `scripts/build_cloud_workflows.py:8276-8283` (the `groups=` argument to
`split_merge_into_stages`)
**Issue:** The three groups passed for `Build Response Merge` — `[0,1,2,3,11,12]`,
`[4,5,6,7,8,13,14]`, `[9,10]` — are not a contiguous partition of the original 0..14
index range. Under the walker's (and, per its own docstring, n8n's) append-mode
concatenation (`for i in 0..numberInputs: merged.push(...state.buffers[i])`), the final
row order out of `Build Response Merge` is now stage-1-items, then stage-2-items, then
stage-3-items — e.g. an item that used to arrive at position 11 (before position 4) now
arrives after everything in the first group, changing its relative position versus a row
delivered on input 4-8. `split_merge_into_stages`'s own docstring makes no claim about
preserving the original numeric concatenation order (only about preserving each input's
existing sentinel/producer *coverage*), so this is not a violation of any stated
contract — but it is an undocumented behavioural change from the pre-split single Merge.
**Why it matters:** every downstream consumer I checked (`Filter Build Response Rows`,
`Build Ack`, `report.reconcile`, the plugin's `merge_enriched`) correlates rows by
identity (`row_id`, `email`, `hs_object_id`) rather than array position, and
`prove_phase70_runtime.py`'s own comparator (`shapes_equal`) is explicitly
order-insensitive ("Order-insensitive by design... Row IDENTITY and COUNT are what this
phase asserts, never row order"), so I do not believe this causes an actual defect. It is
recorded because no test in this review's scope asserts order-independence for a batch
that genuinely mixes contacts, companies, and an unsupported-object-type row in one
execution — the closest test (`enrichmentConvergenceMerge.test.mjs`'s "mixed batch"
case) mixes only two contacts, never crossing a group boundary.
**Fix:** none required. Optionally, a one-line comment at the `split_merge_into_stages`
call site noting that global row order is not preserved across the split (only
per-stage-group order) would pre-empt a future reader assuming otherwise.

### IN-01/IN-02/IN-03 (carried from prior review, out of this increment's diffed scope, not re-verified)

`operator-claude-plugin/scripts/written_records.py`'s docstring undercount,
`scripts/prove_zoominfo_balance.py`'s duplicated comment reference, and the prior
review's own file-disposition note were all about files outside this increment's changed
set (`written_records.py` and `prove_zoominfo_balance.py` are not in this review's `files`
list and show no diff against `6be2894`). I did not re-verify their current status; they
are carried forward by reference only, not re-classified.

---

_Reviewed: 2026-09-10T06:22:45Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
