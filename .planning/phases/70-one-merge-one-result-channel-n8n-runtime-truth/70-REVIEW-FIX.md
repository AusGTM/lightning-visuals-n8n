---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
fixed_at: 2026-09-10T07:05:00Z
review_path: .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 70: Code Review Fix Report

**Fixed at:** 2026-09-10T07:05:00Z
**Source review:** `.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (WR-01, WR-02, WR-03, WR-06, WR-07)
- Fixed: 5
- Skipped: 0
- Not touched, as instructed: WR-04 (resolved structurally), WR-05 (corrected — no defect),
  IN-01..IN-04 (out of scope)

**Where verification ran:** the MAIN CHECKOUT, on `master`. `.planning/config.json` sets
`workflow.use_worktrees: false`, so per #2825 no worktree was created and no temp branch,
recovery sentinel or cleanup tail applies. Every suite below therefore ran in the same tree
the commits landed in, against the project's real `.venv` — reproducible by re-running the
commands verbatim.

**Suites, all green after the last commit** (counts differ from the stated baseline by
exactly the tests these fixes add — nothing was removed or disabled):

| Suite | Command | Baseline | Now | Delta |
| --- | --- | --- | --- | --- |
| n8n walker | `node --test tests/n8n/*.test.mjs` | 1064 | **1072** | +8 (WR-07's new file) |
| root python | `.venv/bin/python -m pytest -q --tb=short` | 4690 | **4695** | +2 (WR-06) +3 (it also collects the plugin tests below) |
| plugin python | `cd operator-claude-plugin && ../.venv/bin/python -m pytest -q` | 2865 | **2868** | +2 (WR-01) +1 (WR-02) |

`scripts/build_cloud_workflows.py` was NOT modified by any fix, so no workflow JSON was
regenerated; `git status --porcelain -- n8n/` is empty. The committed-vs-live deployment
gap CLAUDE.md §13.0.2 describes is unchanged by this round.

## Fixed Issues

### WR-01: cross-execution `runData` merge was a replacement, not a union

**Files modified:** `operator-claude-plugin/scripts/watch.py`,
`operator-claude-plugin/scripts/report.py`,
`operator-claude-plugin/tests/test_watch_settle_reporting.py`
**Commit:** `a1e6ce5`
**Status:** fixed (test-proven, seen RED first)

`merged_run_data.update(rd)` let whichever execution folded last speak for every node, so a
`scale_up` child that never wrote erased a parent that did. The merge is now a per-node
UNION — run lists concatenated — which is exactly the shape n8n itself produces for a node
that ran more than once, so no consumer needed changing.

One thing the review's fix line did not name, found while tracing the consumer: the union
alone would NOT have fixed it. `report._write_node_items` read `runs[0]` only, so the answer
still depended on which run happened to be first. That is the same latent under-read
`report.all_node_items`' own docstring documents from executions 12096/12098 — one function,
all callers, so it is fixed there rather than worked around at the merge: `_write_node_items`
now reads every run via `all_node_items`. `execution_ids` is unchanged in the return.

One consequence worth recording so it is never misattributed later: the merge changed from
idempotent (replacing a node's runs with identical data) to additive. If the same execution
ever appeared in BOTH `settled` and `children` — P-13 confirms the list API does return child
executions, and a child carries the same `run_id` — `responses` was already duplicated before
this change, and `created_ids` (`report.py:391`) would now double too. Pre-existing, not
introduced here, and not reachable on any lane today; flagged so a future duplicate is
diagnosed at the execution-selection step rather than blamed on the union.

**RED first, both tests:** before the fix,
`test_recovered_run_data_unions_a_write_nodes_runs_across_executions` failed on a single
surviving run, and `test_reconcile_confirms_a_write_any_contributing_execution_actually_made`
returned `['not_confirmed', 'not_confirmed']` against `['update', 'update']` — the silent
misreport itself, reproduced. The child fixture carries a PRESENT-but-empty `HubSpot Update`
key, since an absent one could never have clobbered.

### WR-02: `dispatch_and_recover`'s `lane="ingest"` branch was unreachable dead code

**Files modified:** `operator-claude-plugin/scripts/chunking.py`,
`operator-claude-plugin/tests/test_chunking.py`
**Commit:** `9f0c1af`
**Status:** fixed

Took the review's preferred option — deletion. Confirmed first that no caller passes `lane`
(`preingest.py:904`, `scheduled_arm.py:240`, the enrich-records skill) and, beyond the
review's own check, that no TEST passes it either. Parameter, branch, the `lane=lane` forward
to `watch.recover_dispatch` (whose default is the same `"enrichment"`) and the now-unused
`import report` are all gone. The 15-line comment collapsed to two lines that keep the two
load-bearing facts: reconcile belongs to `dispatch.dispatch` because it names the INGEST
workflow's write nodes, and when the enrichment lane's own write-node map exists it belongs
here as a parameter, never a second copy.

Pinned three ways in one test: `lane` is absent from the signature; `report.reconcile` is
monkeypatched to raise and the call still completes; and a stray `lane="ingest"` is asserted
INERT rather than raising — it falls into `dispatch_plan`'s deliberate legacy-kwarg sink, so
a future reader must not mistake silent acceptance for the branch still being there. (My
first draft asserted `TypeError` and failed, which is how that was found.)

### WR-03: `scripts/prove_async_recovery.py` stale against the landed D-70-07 contract

**Files modified:** `scripts/prove_async_recovery.py` (deleted),
`scripts/probe_company_propose_mode.py`, `scripts/enrich_coverage_companies.py`,
`scripts/fix_sfv_region.py`, `scripts/prove_phase70_runtime.py`,
`scripts/prove_zoominfo_balance.py`
**Commit:** `6a15a64`
**Status:** fixed

Deleted rather than guarded: with `async_ack` retired the script's whole premise is gone, and
a refusal at the top of `main()` would leave a file that can only ever refuse.

Every reference was found and updated first — five comment sites citing it as the
cross-package-import / two-gate precedent now cite `scripts/prove_phase70_runtime.py`, the
live successor that carries the same idiom. The successor's own header names it as history
(with the deletion date and the reason), so the lineage is not lost. Nothing dangles: a
repo-wide grep over `scripts/`, `tests/`, `operator-claude-plugin/`, `n8n/`, `docs/` and
`CHANGELOG.md` returns no code reference, no test targeted the file, and no live gate
procedure in `70-DEFERRED-GATES.md`/`70-UAT.md` invokes it. `.planning/` history from Phase 57
still names it, correctly, as the template it was at the time.

Incidental: `prove_zoominfo_balance.py`'s header said "mirrors prove_async_recovery.py and
prove_async_recovery.py" — the repointing resolves that duplication (IN-02) as a side effect.

### WR-06: hand-maintained deleted-file fingerprint, unpinned

**Files modified:** `tests/test_no_by_name_reads.py`
**Commits:** `08e554d`, plus follow-up `f59010e` (pin the deleting commit by its full 40-char
SHA — a 7-character prefix can go ambiguous as history grows)
**Status:** fixed

Test-only; the mechanism and the assertion it protects are unchanged and unweakened, so no
builder edit and no regeneration. `_run_recovery_marker` is a hardcoded copy of a signature
line from a file that no longer exists — nothing in the working tree could contradict it if
it drifted, and a drifted fingerprint degrades `detect_by_name_reads` SILENTLY: a genuine
reinlining of the retired mechanism would be reported as an ordinary `dynamic`/`quoted` miss
instead of `run_recovery_inlined`, exactly when the distinction matters.

The fingerprint is now derived from git history — `git show <deleting-commit>^:n8n/code/
nodeRunRecovery.js`, selecting the line by its argument list — and compared. Selecting rather
than typing means the test never spells the retired function's bare name, so it cannot drift
along with the marker it checks. A second test asserts the module is still absent at HEAD
(D-70-01: deleted, never kept as a fallback).

**Seen RED:** mutating `fn_name` by one character fails the pin (verified, then reverted with
`git diff` confirming no residue). The `git show` this test depends on needs real history;
this repo has no CI (`.github`/`.gitlab-ci.yml`/`.circleci` all absent), so no shallow-clone
`fetch-depth` caveat applies today — worth remembering if CI is ever added.

### WR-07: the ZoomInfo Merge/sentinel slice had zero walker-replay coverage

**Files modified:** `tests/n8n/lib/walkWorkflow.mjs`, `tests/n8n/zoominfoLaneFlow.test.mjs`
(new)
**Commit:** `c6dc8fe`
**Status:** fixed — option (a), the review's preferred route. Not deferred to Gate 5.

Two things had kept this lane out of every replay, and the review named both: the three
provider-call Code nodes `await` (the walker runs Code bodies synchronously via
`new Function`, so the body is a SyntaxError), and no test ever enabled the provider.

`codeStubs` mirrors `httpStubs` and is justified by the same fact — all three await nodes are
awaiting a provider HTTP call, the exact hop `httpStubs` already stands in for. Under D-70-19
it may only gain fidelity, so it is fenced in BOTH directions: an await-bearing Code node
reached with no stub now throws by name naming the option (previously an opaque SyntaxError
from inside `new Function` — a diagnostic gain), and a stub supplied for a node the walker
CAN run is refused, so real committed jsCode can never be replaced by a test's expectation.
Both fences are themselves tested.

**Two corrections to the review's description of this graph, found by dumping the subgraph
rather than trusting the finding's wording:**

1. The gate condition is `$json.provider_enabled.zoominfo === true`, not
   `providers_requested.includes('zoominfo')`. The lane is enabled from the webhook
   envelope's `providers` field, which `Parse HubSpot Event` turns into both fields.
2. A carry Merge's two inputs are **co-fed on the same IF's TRUE branch** (the Mint HTTP
   response on input 0, the carried row on input 1) — that is what a D-70-20 carry merge IS —
   so "mutually exclusive" does not describe its own two inputs. The genuine
   real-producer-vs-sentinel exclusion on this lane is at `Collect Credits` input 2
   (`Adapt ZoomInfo Usage` vs `ZoomInfo Credit Skipped`).

What the replay honestly proves against the committed `n8n/wf_enrichment_cloud.json`:

- **Lane live, every lane minting** — ALL THREE carry Merges fire, each claimed on input 0 by
  its own real Mint HTTP node and input 1 by its own pass-through, pairing 1:1 (a combine-by-
  position Merge with unequal counts would pair a row against another row's HTTP response).
  This shape needed a lever, and the lane supplied one: `needsMint` treats a token expiring
  within 60 seconds as already gone, so a mint stub returning a lifetime inside that skew
  makes every lane mint its own — the token re-mint the module header says the lane does by
  design, not a contrivance.
- **Lane live, warm cache** — with a normal token lifetime the cache (workflow-global static
  data) means the FIRST lane to need a token mints for all three and the other two take their
  IF's false branch straight past the carry Merge, which starves nothing. Which lane wins is
  an ordering detail and is deliberately not asserted.

  My first draft of this finding had only the second shape, so two of the three carry Merges
  were exercised in their bypass path alone and the "claimed by its own pair" loop was vacuous
  for both — a residual the report would have had to disclose. The expiry lever closed it
  instead, with no walker change; all three are now asserted in their FIRED shape.
- **Lane live, credit slot** — `Collect Credits` input 2 is claimed by the real
  `Adapt ZoomInfo Usage`, while the two providers this run did not request have their slots
  taken by their skip sentinels: the mirror image is what makes it an exclusion rather than a
  coincidence.
- **Lane dead** — no carry Merge fires, no ZoomInfo node runs at all, nothing stalls, and the
  skip sentinel claims input 2 precisely when the real lane cannot.
- **Differential** — enabling the lane changes what enriched a row, never which rows come
  back. Compared on row IDENTITY (id/object_type/action), not row content: ZoomInfo
  legitimately puts ZoomInfo-shaped fields on a row, and a deep-equal assertion (my first
  draft) correctly failed on exactly that.

The walker models `mode: "combine"`/`combineByPosition`, and its "first delivery to an input
wins / a Merge fires at most once" rules are the ones derived from live executions 12203 and
12206 — so a sentinel racing a real producer would surface as the wrong `sources` entry,
which is what these assertions read.

**Scope discipline:** `scripts/build_cloud_workflows.py` was not touched, and no workflow JSON
was regenerated. Option (b) was not needed — nothing is deferred to `70-DEFERRED-GATES.md`
for this finding and no residual slice is left uncovered.

This is offline replay evidence; it does not substitute for Gate 3's live observation that the
real n8n engine honours native Merge nodes at all, which remains deferred and correctly
disclosed. One further honesty note: `codeStubs` means the three ZoomInfo provider-call bodies
themselves are still not executed by any walker test — only the lane's ROUTING around them is.
That is the same standing trade `httpStubs` already makes at every HTTP hop, and the fence
keeps it from spreading to any node the walker could have run.

## Skipped Issues

None.

---

_Fixed: 2026-09-10T07:05:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
