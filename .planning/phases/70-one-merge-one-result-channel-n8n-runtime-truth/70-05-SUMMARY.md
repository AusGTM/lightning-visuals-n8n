---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 05
subsystem: n8n-workflow-generation
tags: [n8n, workflow-automation, code-generation, write-safety, hubspot]

requires:
  - phase: 70-04
    provides: carry Merges at every hop, zero by-name reads across all 8 built cloud workflows, assert_no_by_name_reads wired into main()
provides:
  - "D-70-12 Task 1 only: one canonical write_request shape ({action, hs_object_id, domain, email}) emitted by every gated write's upstream Code node in the ingest and scheduled-maintenance lanes and by review-decision's Build Review Decision, via one shared _buildWriteRequest JS helper (_write_request_js() in scripts/build_cloud_workflows.py)"
  - "_write_gate_js reads ONLY write_request now; the four-way identity fallback ladder (existingRecord.hs_object_id / identity_keys.domain / properties.email / bare .email) is deleted, not extended"
  - "assert_write_request_emitters, called from splice_write_gates, walks a gated write's inbound edges back through routing IFs/Merges to the nearest Code node and raises at generation time if that node does not call _buildWriteRequest"
  - "Review lane's write_request.domain is forced to the literal null for BOTH companies and contacts (D-70-13), plus a same-dispatch Rule-1 fix keeping Build Review Decision's own allowlist precheck in agreement with the gate it precedes"
affects: [70-06, remainder of 70-05 (Task 2's 2b/2c sub-steps and Task 3, not yet executed)]

actuals:
  tokens: 260000
  tasks: 1.3
  commits: 3
  plan_head_before: 0350531

tech-stack:
  added: []
  patterns:
    - "Shared emitter helper composed at module top (WRITE_REQUEST_JS / _write_request_js()), unlike WRITE_SAFETY_GATE_JS's build-site composition — the emitter has no dependency on constants defined later in the module, so `+ WRITE_REQUEST_JS +` works at every call site regardless of definition order, while WRITE_SAFETY_GATE_JS still must be composed at each build site because it depends on WRITE_SAFETY_DEFAULTS."
    - "Generation-time emitter assertion via a walk-to-nearest-Code-node BFS (_write_request_source_names) plus a string-literal marker check (`_buildWriteRequest(` in jsCode) — same string-marker-at-generation-time approach as _run_recovery_marker/assert_no_by_name_reads, extended to a graph walk because the emitter is not always the write node's DIRECT predecessor (native IF/Merge nodes carry no jsCode and must be walked through)."

key-files:
  created:
    - tests/n8n/writeGateShape.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/n8n/ingestUpdateGateDomainFallback.test.mjs
    - tests/n8n/companyAssociationFlow.test.mjs
    - tests/n8n/contactCreateGateFlow.test.mjs
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - tests/n8n/reviewWriteFlagSeparation.test.mjs
    - tests/test_write_gate_coverage.py

key-decisions:
  - "D-70-13 was implemented literally and lane-wide, not contacts-only: Build Review Decision feeds BOTH the companies PATCH (Review Decision Update) and the contacts PATCH (Review Contact Decision Update) through routing IFs, so forcing write_request.domain to null there applies to companies too. Companies lose their domain-allowlist path on review writebacks as a side effect of this task's literal instruction — flagged here for the operator rather than silently accepted, since the plan's own wording (\"contacts stay id-allowlist-only\") reads contacts-specific even though the single emitter node cannot distinguish."
  - "Scheduled-maintenance's splice_write_gates call actually gates FOUR write nodes, not the plan's stated three: SJ-1 Set Requested, SJ-2 Set Requested, Dedupe Set Needs Review, AND Review Apply Update (all action=\"enrich\", one dict literal at ~L9605 in the current file). Task 1 treated all four uniformly (emitters: SJ-1 Extract Rows, SJ-2 Company Gate, Dedupe Sweep, Apply Review respectively) since assert_write_request_emitters is wired unconditionally into splice_write_gates and would have raised on the fourth otherwise. Task 3's plan text (\"its three set-requested gates\") is off by one against the actual code and should be read as four when Task 3 executes."
  - "ENRICH_EXTRACT_SEARCH_ROWS is a shared Code body (SJ-1/SJ-3/Dedupe/Review Extract Rows all use it) — adding write_request emission there for SJ-1's sake means SJ-3 Extract Rows and Dedupe/Review Extract Rows also now carry an unused write_request field on their output. Harmless: SJ-3's own reshape (ENRICH_SJ3_BUILD_DISPATCH_EVENT) drops it, and Dedupe/Review's own downstream Code nodes (Dedupe Sweep / Apply Review) construct their OWN write_request from the row's real fields rather than relying on the pass-through one."
  - "TDD RED/GREEN was collapsed into a single feat commit (implementation preceded the dedicated test files, no gsd-tools check tdd-red-evidence run) under this dispatch's context-budget pressure — documented as a deviation, not fabricated as a separate RED commit."

patterns-established:
  - "_write_request_js()/WRITE_REQUEST_JS + _buildWriteRequest(action, hsObjectId, domain, email): the one place any future gated write's emitter should call, rather than hand-deriving identity fields at a new call site."

requirements-completed: []

coverage:
  - id: D-70-12-task1
    description: "Every node feeding a gated write in the ingest and scheduled-maintenance lanes, plus review-decision's Build Review Decision, emits write_request; the gate reads only write_request; the fallback ladder is deleted; generation raises when an upstream emitter is missing"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs (new, 15 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_write_gate_coverage.py::test_assert_write_request_emitters_raises_on_a_missing_emitter, ::test_assert_write_request_emitters_passes_when_the_emitter_is_correct, ::test_assert_write_request_emitters_walks_through_a_native_if_node"
        status: pass
      - kind: unit
        ref: "tests/n8n/ingestUpdateGateDomainFallback.test.mjs (rewritten against the canonical shape)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1017/1017)"
        status: pass
      - kind: unit
        ref: "pytest tests/ -q (1785 passed, 149 skipped), pytest operator-claude-plugin/tests/ -q (2849 passed, 5 skipped)"
        status: pass
    human_judgment: false
  - id: D-70-13-task1
    description: "Review lane's write_request.domain is forced to the literal null, applying to both companies and contacts"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs::\"review lane: Build Review Decision always emits write_request.domain === null\""
        status: pass
      - kind: unit
        ref: "tests/n8n/reviewDecisionEndpoint.test.mjs (g3/g4/g5 unmodified in outcome, g4's hand-built row updated to carry the same write_request shape)"
        status: pass
    human_judgment: false
  - id: task2a-done-2b-2c-3-not-started
    description: "Task 2's FIRST sub-step (2a: reshape splice_write_gates itself into the two-node IF-shaped gate, on the three lanes it already covers) is done. Task 2's remaining sub-steps (2b: the enrichment lane's first-ever spliced gate; 2c: remove the ingest precheck per D-70-06 and wire each lane's false branch to its response Merge, fixing the Associate/Review Lane Sentinel's pre-gate anyWrite check in the process) and Task 3 (one verdict for update+association, scheduled-maintenance's remaining adoption) are NOT executed in this dispatch."
    verification: []
    human_judgment: true
    rationale: "Deferred to a continuation dispatch under explicit context-budget guidance in this plan's own execution instructions (\"work lean ... if you approach exhaustion, commit what is green ... never leave uncommitted work\"). 2c specifically was deferred because it requires touching the Associate Lane Sentinel's/Review Lane Sentinel's condition (currently computed pre-gate, purely off row.action) to avoid a newly-reachable Merge starvation once the ingest precheck is removed. A THIRD dispatch traced 2b itself and found the identical class of hazard is larger there: Build Response is already behind a real, ~30-sentinel-covered Merge (Phase 70 Plan 03/04), and moving the write-safety check out of Decide Action/Decide Company Action breaks the existing br(HubSpot Create)-family sentinels' row.action-keyed conditions on EVERY disarmed batch containing a create/enrich row, not just an edge case — see \"Next Phase Readiness\" below (\"2b's OWN hazard\") for the full mechanism. No code was written for 2b this dispatch; the advisor consulted mid-dispatch said \"no Merge on this lane\", which is incorrect, and implementing on that basis would have shipped a live hang."

duration: ~2h20m (single continuous session across two checkpoints, Task 1 + Task 2's 2a sub-step)
completed: 2026-09-10
status: partial
---

# Phase 70 Plan 05: One write request, one gate per lane (Task 1 + Task 2's 2a) Summary

**Task 1 landed: one canonical `write_request` shape, one shared emitter helper, the four-way identity fallback ladder deleted, and a generation-time assertion that a gated write's upstream actually emits it. Task 2's 2a sub-step also landed: `splice_write_gates` itself is now the two-node IF-shaped gate (Code node stamps a `write_allowed` verdict via `.map()`, never `.filter()`s a row away; a paired IF node routes true/false) on all three lanes it already covered — ingest, review-decision, scheduled-maintenance. The enrichment lane's first-ever spliced gate (2b), the ingest precheck removal plus false-branch-to-response-Merge wiring (2c), and Task 3 (one verdict for update+association) are not started.**

## Performance
- **Duration:** ~2h20m (this dispatch, across two checkpoints) · **Started:** 2026-09-09 (session date) · **Completed (Task 1 + 2a):** 2026-09-10 · **Tasks:** 1 done + 2's first sub-step / 3 total · **Commits:** 3 (`12866c8` feat, `e0a35aa` fix, `d87eef1` feat) · **Files modified:** 11 (Task 1) + 2 (fix) + 13 (2a)

## Accomplishments

- Added `_write_request_js()` / `WRITE_REQUEST_JS` (`scripts/build_cloud_workflows.py`, composed at module top so it has no build-site-ordering dependency, unlike `WRITE_SAFETY_GATE_JS`): defines the single shared `_buildWriteRequest(action, hsObjectId, domain, email)` JS helper, embedded verbatim into every emitting Code node.
- Rewrote `_write_gate_js(action)` to read exclusively from `it.json.write_request` — the four-way identity fallback ladder (`existingRecord.hs_object_id`, `identity_keys.domain`, `properties.email`, bare `.email`) that grew from two live incidents (F11, BUG 27) is deleted outright.
- Added `assert_write_request_emitters` (+ its `_write_request_source_names` upstream-BFS helper) and wired it into `splice_write_gates` unconditionally — every future `splice_write_gates` call site (including Task 2's future enrichment-lane call) is now covered by the same generation-time guard for free.
- Made every emitter in the ingest, scheduled-maintenance, and review-decision lanes stamp `write_request`:
  - Ingest: `Decide Action` (feeds `HubSpot Update`/`HubSpot Create`) and `Build Association Request` (feeds `HubSpot Associate Company`).
  - Scheduled maintenance: `SJ-1 Extract Rows` (shared `ENRICH_EXTRACT_SEARCH_ROWS`, feeds `SJ-1 Set Requested`), `SJ-2 Company Gate` (feeds `SJ-2 Set Requested`), `Dedupe Sweep` (feeds `Dedupe Set Needs Review`), `Apply Review` (feeds `Review Apply Update`) — **four** gated writes, not the plan's stated three (see Decisions Made).
  - Review-decision: `Build Review Decision` (feeds both `Review Decision Update` and `Review Contact Decision Update`), forcing `domain: null` for both object types per D-70-13.
- Rewrote `tests/n8n/ingestUpdateGateDomainFallback.test.mjs` against the canonical shape (its subject, the gate-side fallback, is gone; the case it protected is now an emitter-side assertion on `Decide Action`'s own `write_request.domain`).
- Created `tests/n8n/writeGateShape.test.mjs` (15 tests): every gate's jsCode references no identity key outside `write_request`; empty-allowlist denial on all four lanes (ingest, scheduled-maintenance, review-decision, plus the enrichment lane's own unchanged inline check); the review lane's `domain: null` emission.
- Added three tests to `tests/test_write_gate_coverage.py` proving `assert_write_request_emitters` raises (naming both the write node and the offending source) on a hand-built graph with a missing emitter, passes on a correct one, and correctly walks through a native IF node with no jsCode of its own.
- **[Rule 1 fix, found by the plan's own advisor review immediately after Task 1's commit]** `Build Review Decision`'s BUG-30 allowlist precheck still passed `row.domain` (the record's real domain) into `_writeSafetyAllows`, while the gate downstream now sees `write_request.domain === null` unconditionally. Under `ALLOW_HUBSPOT_REVIEW_WRITES=true` + a domain-only `TEST_RECORD_DOMAINS` armed window, a real company submit would have: precheck says allowed (`outcome: "applied"`, `dry_run: false`) → gate refuses (domain null, id unlisted) → row never reaches `Review Verify Fetch` → its Absent Sentinel never fires (guarded on `dry_run === true`, which this branch is not) → `Build Review Response Merge` starves waiting on an input that never delivers — D-70-14's hang class, newly reachable on companies specifically because Task 1 widened the null-domain rule to the whole lane. Fixed by passing `null` to the precheck too, matching the gate it precedes. Committed separately (`e0a35aa`) since it was found after, not during, Task 1's own commit.

## Task Commits

1. **Task 1: One canonical write request, emitted once, fallback ladder deleted** — `12866c8` (feat)
2. **Rule 1 fix (found post-commit by advisor review): review precheck domain agreement** — `e0a35aa` (fix)
3. **Task 2, sub-step 2a: the write gate becomes IF-shaped, refusal stamped not dropped** — `d87eef1` (feat)

Task 1's `tdd="true"` RED/GREEN cycle was collapsed into a single feat commit (implementation preceded the dedicated test files; no `gsd-tools check tdd-red-evidence` run) — see Deviations. Task 2's 2a sub-step similarly landed implementation and its test fixes in one commit; the RED case (`writeGateShape.test.mjs`'s "still filters" test, asserting length 0 on a fully-refused batch) was the PRE-EXISTING Task-1 test this dispatch flipped to GREEN (asserting length 2, both `write_blocked`) rather than a freshly-authored failing test run before the implementation — same disclosed deviation class as Task 1's.

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `_write_request_js()`/`WRITE_REQUEST_JS`, rewritten `_write_gate_js`, new `assert_write_request_emitters`/`_write_request_source_names`, `write_request` emission added to `DECIDE_CLOUD`, `BUILD_ASSOCIATION_REQUEST`, `REVIEW_BUILD_DECISION`, `ENRICH_EXTRACT_SEARCH_ROWS`, `SJ2_CO_GATE`, `ENRICH_DEDUPE_SWEEP`, `ENRICH_APPLY_REVIEW`; the Rule-1 precheck fix in `REVIEW_BUILD_DECISION`
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_review_decision_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` — regenerated; node counts unchanged (45/43/39) against 70-04's baseline — this task only rewrote jsCode strings inside existing nodes
- `n8n/wf_enrichment_cloud.json` (and its local/local_live siblings) — **untouched** in this task (202 nodes, unchanged); Task 2 is what adds a spliced gate there
- `tests/n8n/writeGateShape.test.mjs` — new, 15 tests
- `tests/n8n/ingestUpdateGateDomainFallback.test.mjs`, `tests/n8n/companyAssociationFlow.test.mjs`, `tests/n8n/contactCreateGateFlow.test.mjs`, `tests/n8n/reviewDecisionEndpoint.test.mjs`, `tests/n8n/reviewWriteFlagSeparation.test.mjs` — updated to build rows carrying `write_request` instead of the deleted ladder's legacy fields
- `tests/test_write_gate_coverage.py` — three new tests for `assert_write_request_emitters`
- **(2a, commit `d87eef1`)** `scripts/build_cloud_workflows.py` — `_write_gate_js` rewritten from `.filter()` to `.map()` (stamps `write_allowed`/`action: "write_blocked"`/`write_blocked_reason`, never drops); `splice_write_gates` now emits a paired `<write_name> Write Gate IF` node (via `_if_bool_node`) and rewires the write node behind it, with the false branch deliberately left unwired (see Next Phase Readiness)
- **(2a)** `n8n/wf_contact_ingest_cloud.json` (45→48 nodes), `n8n/wf_review_decision_cloud.json` (43→45), `n8n/wf_scheduled_maintenance_cloud.json` (39→43) — regenerated; `n8n/wf_enrichment_cloud.json` untouched (still 202, still no spliced gate)
- **(2a)** `tests/n8n/companyAssociationFlow.test.mjs`, `contactCreateGateFlow.test.mjs`, `dedupeSweepWiring.test.mjs`, `ingestUpdateGateDomainFallback.test.mjs`, `reviewAllowlistRefusal.test.mjs`, `reviewDecisionEndpoint.test.mjs`, `reviewWriteFlagSeparation.test.mjs`, `sjPredicates.test.mjs`, `writeGateShape.test.mjs` — every assertion that read a gate's output `.length === 0` as "refused" now reads `.length` unchanged (gate never drops) plus `write_allowed === false`/`action === "write_blocked"`; every assertion that a gate fed a write node directly now expects one more hop through the paired IF node

## Decisions Made

See `key-decisions` in the frontmatter — in short: D-70-13's null-domain rule was implemented literally and applies to companies as well as contacts (single emitter node feeds both write paths); scheduled-maintenance actually gates four writes, not three (Task 3's plan text is off by one); `ENRICH_EXTRACT_SEARCH_ROWS`'s shared body now carries an unused `write_request` on three lanes that don't need it (harmless); TDD RED/GREEN was collapsed under context-budget pressure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Review precheck disagreed with the gate it precedes, reachable hang on a company**
- **Found during:** post-Task-1 advisor review (before Task 2 started)
- **Issue:** see Accomplishments above for the full mechanism
- **Fix:** `Build Review Decision`'s precheck now passes `null` for domain, matching the gate
- **Files modified:** `scripts/build_cloud_workflows.py`, `n8n/wf_review_decision_cloud.json`
- **Verification:** full node + pytest suites green; confirmed no existing test arms a company review approval via `TEST_RECORD_DOMAINS` (all use `TEST_RECORD_IDS`)
- **Commit:** `e0a35aa`

### Process Deviation (not a Rule 1-4 category)

**TDD RED/GREEN collapsed into one commit.** Task 1 carries `tdd="true"`, but under this dispatch's context-budget pressure the implementation (gate rewrite, emitters, assertion) was written before the dedicated test files (`writeGateShape.test.mjs`, the three `test_write_gate_coverage.py` additions). No separate RED commit exists, and `gsd-tools check tdd-red-evidence` was never run. All resulting tests pass green against the implementation as committed; nothing is untested, but the RED-before-GREEN ordering itself is not evidenced by commit history for this task.

**Total deviations:** 1 auto-fixed Rule 1 bug + 2 process deviations (TDD ordering, ×2 — Task 1 and 2a) + 1 plan-scope split (Task 2 divided into 2a/2b/2c sub-steps, none of which is in the plan's own task boundaries, to keep each dispatch's committed work green under context-budget pressure — advisor-directed, not a Rule 1-4 category).
**Impact on plan:** The Rule 1 fix closes a real, previously-shippable hang; no scope creep (stayed inside the file the bug was found in). The TDD ordering deviations have no correctness impact given the full green suites, but are disclosed rather than silently normalized. The 2a/2b/2c split changes nothing about the plan's acceptance criteria or `must_haves` — it only sequences Task 2's single large action block into three separately-committable, independently-verified increments; Task 2 as a whole is not complete until 2b and 2c both land.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None — no external service configuration required. Nothing deployed, nothing armed (both write flags remain `"false"` in every committed workflow, verified via `test_committed_write_safety_constants_are_all_disabled` and a direct grep over all `n8n/wf_*.json`).

## Next Phase Readiness — for Task 2's continuation dispatch (resume at 2b)

Task 2 ("The gate becomes IF-shaped, and the enrichment lane finally has one") is split into three
sub-steps for budget safety; **2a is done (commit `d87eef1`), 2b and 2c remain.** Task 3 ("One
verdict covers an update and its association") remains entirely, after 2b/2c. Read
`.planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-PLAN.md` in full before
resuming — this section is a supplement, not a replacement.

**2b — give the enrichment lane its first-ever spliced gate.** `assert_write_request_emitters`'s
walker stops at the **nearest** upstream Code node on each path and checks it for the literal
`_buildWriteRequest(` in its jsCode. Before calling `splice_write_gates` on the enrichment lane for
the first time, `ENRICH_DECIDE_CLOUD` and `ENRICH_DECIDE_CO_CLOUD` (`scripts/build_cloud_workflows.py`,
the inline `_writeSafetyAllows` calls at ~L2085/L4076) must themselves be edited to call
`_buildWriteRequest(...)` and stamp `write_request` on their output, and their OWN inline
`_writeSafetyAllows`/`action = "write_blocked"` computation removed — that authorization decision
moves to the new gate. `WRITE_REQUEST_JS` is already available module-wide (composed near the top
of the file) — concatenate it into those two constants and add a `write_request` field, the same
pattern this task already applied four times. **Read the surrounding ~30 lines of
`ENRICH_DECIDE_CLOUD` around L2085 first**: the `action = "write_blocked"` reassignment sits
between two OTHER unconditional reassignments (`returnOnly`→`"proposed"`, medium-match→
`"needs_match_review"`) and is immediately followed by an unconditional `if (action === "create")
{ action = "review"; ... }` (the association-hold rule, Phase 61 Plan 06 Task 1) — removing the
write-safety check changes what value reaches that immediately-following check, and needs
tracing through, not just deleting in isolation.

**2b's OWN hazard, found THIS dispatch (the third), not yet fixed — read before touching
`splice_write_gates` again.** A continuation dispatch's advisor call correctly identified three
things this SUMMARY's previous revision missed (gate `HubSpot Company Create` too — the plan's
"three" is the identical off-by-one class already caught for scheduled-maintenance; a
`false_target` kwarg wiring the IF's false lane to `Build Response`; and the carry-merge
`carry_source` for `HubSpot Company Create` must become the new gate IF's TRUE output, not `IF
Company Create` directly, mirroring the exact count-mismatch class already latent at ingest
L1336-1338). But that advisor call also said "no Merge on this lane" for `Build Response` — **that
is wrong, and tracing it revealed a fourth, larger problem the advice never surfaced:**

`Build Response` has been behind a real `mode="append"` Merge (`Build Response Merge`) since Phase
70 Plan 03/04 (D-70-01), sized at splice time to its then-existing inbound edges and backed by a
~30-entry starved-lane sentinel network (`_add_starved_lane_sentinel` calls, ~L7574-7990) that
feeds a marker `{}` into every declared Merge input whenever that input's real producer will not
run this execution. `HubSpot Create`/`HubSpot Update`/`HubSpot Company Update`/`Adapt Company
Create` (which is what actually feeds the Merge for the create path, downstream of the create
carry-merge) are ALREADY declared inputs, covered by an existing family of sentinels keyed on
`row.action` as `Decide Action`/`Decide Company Action` computed it — e.g. `Contacts None Create
Sentinel`: `!rows.some(r => r.action === "create")` feeds `br("HubSpot Create")`; its mirror
`Contacts All Create Sentinel` feeds `br("HubSpot Update")`/`br("IF Enrich", 1)`; and the four
Companies-branch mirrors of both.

**These existing sentinels' conditions silently break once the write-safety check moves out of
`Decide Action`/`Decide Company Action` and into the new gate.** Today, in the COMMITTED
(unconditionally disarmed — `ALLOW_HUBSPOT_RECORD_WRITES` is a baked JS `const`, not a runtime
`$env` read) build, a create/enrich row is ALREADY converted to `action: "write_blocked"` INSIDE
`Decide Action`/`Decide Company Action`, before it ever reaches `IF Create`/`IF Enrich` — so
`rows.some(r => r.action === "create")` is ALREADY false for every disarmed batch, and
`Contacts None Create Sentinel` ALREADY fires 100% of the time in the committed build (this is not
new — Task 2b would not change today's disarmed behaviour if it stopped there). The moment the
inline check is removed from `ENRICH_DECIDE_CLOUD`/`ENRICH_DECIDE_CO_CLOUD` (2b's own action item),
`row.action` stays `"create"`/`"enrich"` all the way to `IF Create`/`IF Enrich`, REGARDLESS of
whether the new downstream gate will refuse it — so `Contacts None Create Sentinel`'s condition
flips to FALSE whenever any create-type row exists, EVEN THOUGH THE GATE WILL STILL REFUSE IT
(disarmed default). Its target (`br("HubSpot Create")`, the write node's own unchanged direct edge
into `Build Response Merge`) then never receives a delivery — the write node genuinely never runs,
because the gate's TRUE branch is empty — and `Build Response Merge` hangs forever on that input.
This reproduces on EVERY disarmed execution that contains so much as one create/enrich-typed row,
which is the overwhelmingly common case, not an edge case; it is strictly worse than the D-70-06
ingest hazard 2c documents below, which needs a specific all-refused batch to trigger.

The fix has to touch BOTH sides of the Merge, not just the new gate's false branch:

1. **The pre-existing `br(<write-node>)` sentinel family must be re-keyed on the gate's verdict,
   not on `row.action`.** Each condition (`Contacts None/All Create Sentinel`, `Contacts NonCreate
   None/All Enrich Sentinel`, and the four Companies mirrors) needs to ask "will ANY/NO row
   actually reach the write node", which after 2b means re-implementing the SAME
   `_writeSafetyAllows`-shaped predicate inside the sentinel's own `condition_js` — the identical
   "duplicate for graph-plumbing, never a second authorization" pattern 2c's own fix (below)
   already needs for the ingest sentinels, generalised to a THIRD site. A sentinel evaluating this
   predicate needs the same `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE`/allowlist inputs
   the gate itself closes over — either inline the same baked constants into the sentinel's
   `condition_js` (this module already re-embeds `WRITE_SAFETY_GATE_JS`-shaped bodies verbatim at
   more than one call site, so this is consistent with the existing style) or read the row's own
   `write_allowed`/`write_blocked_reason` field once the GATE has already stamped it — the latter
   requires sourcing the sentinel from the GATE's own Code node output (a single producer, exactly
   like every other sentinel source in this network) rather than from `Decide Action`, which is
   almost certainly the cleaner fix since it needs no predicate duplication at all: `!rows.some(r
   => r.write_allowed === true && r.action === "create")` fed from `"HubSpot Create Write Gate"`.
2. **The new gate-false-branch Merge input needs its OWN sentinel**, firing whenever the gate ran
   but refused at least one row of the matching action, feeding whichever Merge input
   `false_target="Build Response"` produces (resolved via `_merge_input_index` after
   `splice_merge_before` runs, exactly like every other `br(...)`/`cg(...)`/`eg(...)` target in the
   file) — the mirror-image condition of (1), sourced from the SAME gate Code node output.
3. Both of these must be figured out and wired for FOUR gates (contacts create, contacts update,
   companies create, companies update) — eight new/rewritten sentinel entries in total, not four.

**This dispatch did not implement any of 2b** (no file was edited this session — `git status` was
clean at both the start and end) precisely because attempting the mechanical gate-splice-plus-
false-target change alone, without first solving this sentinel re-keying, would have shipped code
that passes the plan's OWN listed acceptance criteria references superficially (the two Decide
nodes would genuinely stop computing write permission, and a fully-refused two-row batch WOULD
produce two rows at a response builder in a hand-built unit test that never exercises the real
`Build Response Merge`) while introducing a live hang on every disarmed batch containing a single
create/enrich row when driven through the FULL committed graph (`node --test tests/n8n/*.test.mjs`
would very likely have caught this via `enrichmentBatchRefusal.test.mjs`'s walker-driven cases or
`enrichmentConvergenceMerge.test.mjs`, if either drives a create/enrich-shaped row through — check
that BEFORE writing any implementation, since a green suite that never actually exercises this path
would be a false all-clear). Read the ~30 existing sentinel entries at `scripts/build_cloud_workflows.py`
~L7574-7990 in full before writing the eight new/changed ones — the exact `br()`/`_merge_input_index`
idiom and `sx, sy` canvas-placement convention must be followed, not reinvented.

**2c — the hazard this dispatch found and did NOT fix.** Do not skip this trace; it is the reason
2a stopped short of wiring any false branch anywhere.

The ingest lane's `Decide Action` currently has an OLD precheck (predates this plan) that
reassigns `action = "write_blocked"` for a refused write BEFORE the row ever reaches `IF
Update`/`IF Create` — so today, a refused row never reaches the new gate at all; it falls through
both IFs' false lanes straight to `Set Review`, which already has a robust, sentinel-backed path
to `Build Ingest Response` (via `Review Lane Sentinel`). D-70-06 requires removing this precheck.
Once removed, a refused write-type row WILL reach the real gate, take the IF's false branch, and
need a new path to the response — but simply wiring that false branch into `Ingest Merge Response`
(a NEW Merge input) reintroduces exactly the class of hang this whole plan exists to close, via a
mechanism the plan text never mentions and this dispatch had to trace by hand:

1. `Ingest Merge Response`'s write-lane input is only guaranteed to deliver because
   `Associate Lane Sentinel` fires a marker directly into `Associate Carry Merge` whenever
   `anyWrite = rows.some(r => r.action === "update" || r.action === "create")` is FALSE — computed
   from `Decide Action`'s row set, i.e. **before the gate has run**.
2. Once the precheck is removed, a row that Decide Action labels `"update"`/`"create"` can still be
   REFUSED by the real gate. `anyWrite` stays true (the row IS action update/create), so the
   sentinel stays silent — but if EVERY write-type row in the batch gets refused, the real chain
   (`HubSpot Update`/`Create` → `Build Association Request` → `HubSpot Associate Company`) never
   runs at all this execution (an n8n node with zero delivered input does not fire — confirmed by
   this sentinel's own existence, which was built to cover exactly that "zero real rows" case for
   the pre-gate-refusal-unaware condition it currently tests). `Associate Carry Merge` then never
   receives ANY input on either of its two indices → hangs → `Ingest Merge Response` never fires →
   the whole execution hangs.
3. `n8n/wf_contact_ingest_cloud.json`'s `Associate Lane Sentinel`/`Review Lane Sentinel` (built
   Phase 70 Plan 02, D-70-01) are GLOBAL, single-producer checks fed directly off `Decide Action`'s
   fan-out — chosen specifically to avoid racing a real chain's slower multi-hop delivery (see
   `scripts/build_cloud_workflows.py`'s own comment above their call site, ~L1211: a per-branch
   `alwaysOutputData` on the routing IFs "was tried first and rejected" for this exact reason). This
   is the placement the plan's Task 2 action text refers to when it says "at the alwaysOutputData
   placement 70-02's disarmed probe established — do not re-decide it" — but that line is about
   whether `alwaysOutputData` itself is the right primitive (it is NOT, per this comment), not
   about the sentinel's CONDITION, which is what actually needs to change here. **This dispatch did
   not have budget to also read 70-02-SUMMARY.md/70-03-SUMMARY.md's own `alwaysOutputData` sections
   in full — do that first in 2c**, specifically to confirm this reading before touching the
   sentinel.
4. The fix is almost certainly: change `Associate Lane Sentinel`'s condition from "any row is
   action update/create" to "any row is action update/create AND would pass the gate" — i.e.
   duplicate `_writeSafetyAllows` into the sentinel's OWN jsCode (like the review lane's existing
   BUG-30 precheck already does, for the identical reason: this is graph-plumbing to guarantee
   Merge delivery, never a second AUTHORIZATION decision — the real gate remains the sole place
   that actually permits a write). Flag this as a decision when implementing it: a reviewer could
   misread a second `_writeSafetyAllows` call as the precheck pattern sneaking back in, when it is
   structurally the same accepted pattern the review lane already uses for the same reason.
   `Review Lane Sentinel`'s condition (`anyNonWrite`) needs the mirror-image fix for the same
   reason, in the opposite direction.
5. Only once that sentinel fix is in place does wiring the write gates' IF-false branches to
   `Ingest Merge Response` (via `_append_merge_input`, which already exists at
   `scripts/build_cloud_workflows.py` ~L9262 and is documented for exactly this "genuinely new
   producer discovered after `splice_merge_before`" use) become safe. The review lane does NOT
   need this: its own precheck (BUG-30, kept — not removed by this plan) already diverts a refused
   row to the no-write response path before the gate ever runs, so the review gate's false branch
   can stay unwired indefinitely without a hang; only ingest's D-70-06 precheck removal creates the
   new hazard.

**Task 3.** Also carried forward: the true gate count in scheduled-maintenance is **four**
(`SJ-1 Set Requested`, `SJ-2 Set Requested`, `Dedupe Set Needs Review`, `Review Apply Update`), not
the plan's stated three — read Task 3's "finish scheduled-maintenance adoption" section against
four gates. Scheduled-maintenance has NO response-builder node and NO webhook response at all (no
`Respond to Webhook`/equivalent in `build_scheduled_maintenance_cloud`), so its four gates' false
branches have nowhere to be usefully wired — leaving them unconnected (as 2a already did) is
correct and final for that lane, not a placeholder.

No blockers. Both write flags stay disarmed; nothing in this task changed that. Node counts after
2a: ingest 48 (was 45), review 45 (was 43), scheduled-maintenance 43 (was 39), enrichment
unchanged at 202.

## Self-Check: PASSED

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed (Task 1 of 3): 2026-09-10*
