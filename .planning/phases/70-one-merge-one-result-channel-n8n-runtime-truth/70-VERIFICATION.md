---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
verified: 2026-09-10T09:30:00Z
status: human_needed
score: 46/46 offline-verifiable must-haves verified (28 regression-checked from round 1 + 18 round-2 plan truths, D-70-24..27); Gates 7, 8 and 9 (all live, all operator) remain outstanding
behavior_unverified: 0
overrides_applied: 0
covered_files:
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-01-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-01-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-02-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-02-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-03-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-03-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-04-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-04-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-06-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-06-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-07-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-07-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-08-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-08-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-09-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-09-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-10-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-10-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-11-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-11-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-12-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-12-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-13-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-13-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-14-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-14-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-15-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-15-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-DRYRUN.txt
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-RUNTIME-VERDICT.json
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-WALKER-RED-INVENTORY.md
  - CHANGELOG.md
  - CLAUDE.md
  - n8n/README.md
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_review_decision_cloud.json
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/tests/test_scale_up_retired.py
  - scripts/build_cloud_workflows.py
  - scripts/prove_phase70_runtime.py
  - tests/n8n/buildResponseMarkerFilter.test.mjs
  - tests/n8n/enrichmentBatchRefusal.test.mjs
  - tests/n8n/fixtures/frozen/README.md
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/mergeInputContract.test.mjs
  - tests/n8n/scaleUpRefused.test.mjs
  - tests/n8n/sj3DispatchGate.test.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
  - tests/test_merge_helpers.py
  - tests/test_subworkflow_ref_rebinding.py
covered_digest: "v1:sha256:186930e9da7851dac495a080cb161015c74610937f067fab83fc9c89a83cbd62"
re_verification:
  previous_status: human_needed
  previous_score: "28/28 offline-verifiable must-haves verified (gap-closure plans 70-08..70-12); 2 live proof gates remained (Gate 5, Gate 6); Gate 4 recorded but not exercised"
  gaps_closed:
    - "G-70-5 (blocker) — offline half closed by D-70-24/25/26 (plans 70-13/70-14): the self-referencing `Dispatch Self`/`Build Scale Up Fan-Out`/`IF Scale Up Route`/`Build Scale Up Ack` lane is DELETED from `n8n/wf_enrichment_cloud.json` (291 -> 287 nodes, 1 -> 0 executeWorkflow nodes), a `scale_up: true` request (envelope or event) is REFUSED as a row before any dispatch, `assert_no_self_dispatch` makes any future self-referencing executeWorkflow node a generation-time refusal (RED commit 97e254e precedes GREEN 54d43e9), a shared positive row-identity filter (`hasRowIdentity`/`ROW_IDENTITY_KEYS_JS`, one definition, spliced into both `Build Response` and `Build Ingest Response`) drops any marker item before either response builder projects a row (RED commit fa19a23 precedes GREEN 04ca411), and execution 12316's three unconnected-source node runs are pinned as a documented, unmodelled divergence in `tests/n8n/walkerEngineFidelity.test.mjs` (the walker itself confirmed byte-identical since the commit that closed 70-13)."
  gaps_remaining:
    - "Gate 7 (disarmed deploy + bounce of the loop-free 287-node body, then the two-minute mode:integrated burst watch, nothing sent) — not yet run; live enrichment lane is still the pre-Phase-70 59812be body (123 nodes) restored as the 2026-09-10 incident stop"
    - "Gate 8 (D-70-19 disarmed live proof re-run on the loop-free graph, all four sends required shapes_equal:true, plus the new runData-source-vs-declared-connections check) — gated behind Gate 7; not run. Gate 5's prior attempt PASSED only the two ingest sends (12293/12309) against the round-1 ingest body, which predates the D-70-25 marker-filter jsCode change, so it does not stand in for Gate 8 on either lane"
    - "Gate 9 (armed mixed-verdict re-run, formerly Gate 6, re-pointed at the graph Gate 7 deploys and Gate 8 proves) — gated behind Gate 8; not run"
  regressions: []
gaps: []
deferred: []
advisory:
  - finding: "An armed enrichment write row (`HubSpot Update`/`HubSpot Create`'s raw HTTP response, `{id, properties}`) reaches `Build Response Merge` with no carry-merge reattachment of `row_id`/`action` — `id` had to be added to `ROW_IDENTITY_KEYS` in this round specifically because that bare shape was the only identity such a row carries (70-14-SUMMARY.md deviation 2)."
    category: architectural
    reason: "This is pre-existing (round 1's graph already shipped this shape; round 2 only discovered and preserved it while building the marker filter), not a regression introduced by plans 70-13/14/15, and no deferred gate (7/8/9) exercises an armed enrichment write to observe it live — Gate 9 arms the ingest lane only. Worth a future phase's attention against the phase goal's own text (\"every row once, from the write that happened\") and D-70-04's carry-Merge-at-every-hop rule, but no deterministic evidence of it causing a live miss exists in this round's scope."
    evidence_status: "none provided beyond the pre-existing test shape (enrichmentMixedBatch.test.mjs asserts row count and the write node's own outcome, not a reattached row_id/action on the armed path)"
behavior_unverified_items: []
human_verification:
  - test: "Gate 7 — disarmed deploy + bounce of the current committed loop-free enrichment body (287 nodes, zero executeWorkflow), then the two-minute mode:integrated burst watch (70-ROLLBACK-RUNBOOK.md Step 6) with nothing sent. Steps in 70-DEFERRED-GATES.md § Gate 7."
    expected: "All five workflows read active=true; live node counts read exactly 287/69/55/43/30 matching the committed JSON; both write flags read \"false\" everywhere either is declared; the two-minute watch shows ZERO new execution ids, in particular none with mode:integrated."
    why_human: "Requires a live deploy + bounce against n8n Cloud and a real-time watch of the executions list; this is exactly the step the 2026-09-10 runaway (135 child executions, 12211-12348) proved cannot be assumed safe from a green offline suite alone — the phase's own thesis is that the live engine, not the offline model, is the source of truth for this class of failure."
  - test: "Gate 8 — disarmed live re-proof on the loop-free graph (D-70-19 proof re-run), only after Gate 7 passes: `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` (same four sends as Gates 3/5), PLUS the new runData-source-vs-declared-connections check on each of the four executions (the exact detector for the mechanism execution 12316 exhibited). Steps in 70-DEFERRED-GATES.md § Gate 8."
    expected: "70-RUNTIME-VERDICT.json records shapes_equal:true on ALL FOUR sends (Gate 5 passed only the two ingest sends); every recovered row on the enrichment lane carries a non-null row_id matching its input row — an empty or marker-shaped recovery is a FAILURE of this gate even if the row count looks right, per Gate 8's own stated caveat that Gate 5 recovered zero enrichment rows with a row_id at all; all four primary executions settled:true; the connections check finds no node whose runData source names a node its own workflow's connections map does not declare; writes_performed:0; live settings.executionOrder recorded again."
    why_human: "This is the live proof that the offline harness's GREEN (1075/1075 node tests, 4700/4700 pytest, 2864/2864 plugin tests, all confirmed in this verification) actually agrees with the real n8n engine on the regenerated graph — no committed workflow carrying the current Merge/gate redesign has ever completed this proof; Gate 5's own attempt is what surfaced G-70-5 in the first place."
  - test: "Gate 9 — the armed mixed-verdict re-run (formerly Gate 6, superseded), only after Gate 8 passes: one contact permitted, one refused, resolving the same company, in one ingest batch. Steps in 70-DEFERRED-GATES.md § Gate 6 (referenced, not restated, by § Gate 9)."
    expected: "Build Ingest Response returns exactly 2 rows; the permitted row reports action:update, association:associated; the refused row reports action:write_blocked; execution settled; HubSpot shows exactly one contact updated and one association created, the other contact untouched; disarm afterward and read all three declaring nodes (HubSpot Update Write Gate, HubSpot Create Write Gate, Associate Lane Sentinel — independently confirmed in this verification to be the exact three nodes `n8n_arming.set_write_safety` rewrites on the committed ingest JSON) back at their disarmed literals."
    why_human: "This is the one armed HubSpot write this phase's close makes; it must never run against a graph that has not itself been proven both non-self-dispatching (Gate 7) and disarmed-correct (Gate 8) — the ordering rule in 70-DEFERRED-GATES.md is absolute and the operator alone opens the armed window."
    followability_check: "70-15's Task 3 also asked a human to confirm Gates 7/8/9 are followable as written (exact commands/files named, unambiguous pass conditions, no step asking to arm before Gate 8 passes) — folded into the three items above rather than listed separately; reading the gates in this verification session found the same (steps name exact scripts, env vars and pass/fail conditions throughout)."
---

# Phase 70: One merge, one result channel — n8n runtime truth (Gap-Closure Round 2 Verification)

**Phase Goal:** a batch with two identity lanes and two actions returns every row once, from
the write that happened, on one client result channel — and the offline harness would have
caught every finding the 2026-09-09 UAT found.

**Verified:** 2026-09-10T09:30:00Z
**Status:** human_needed
**Re-verification:** Yes — gap-closure round 2, after Gate 5 found gap G-70-5 (blocker) on
2026-09-10.

## Context

Round 1's verification (`e4e95f0`, committed content) recorded `human_needed`, 28/28
offline-verifiable must-haves, with Gates 5 and 6 outstanding. The operator ran Gate 4/5's
deploy: the gap-closure JSON (then 291 nodes on the enrichment lane) went live disarmed, and
within a minute of the first proof send it began self-dispatching — 135 child `Execute Workflow`
executions in six minutes (`12211`-`12348`), stopped by deactivating the workflow and restoring
the pre-Phase-70 `59812be` body. This is gap `G-70-5`, recorded as `failed`/blocker in
`70-UAT.md`. Operator ruling `D-70-24`..`D-70-27` (`70-CONTEXT.md`) directed three gap-closure
plans, executed 2026-09-10: 70-13 (delete the fan-out, refuse the request, generation-time
refusal for any future self-dispatching node, retire the client's ability to ask), 70-14 (marker
filter at both response builders, freeze execution 12316 as a documented walker divergence), and
70-15 (record the retirement and the platform facts, make the burst watch standing, write
Gates 7/8/9).

This verification re-checks every offline claim in plans 70-13/14/15 against the actual
committed code and JSON — not the SUMMARYs' narration of it — and regression-checks round 1's
28 must-haves are still true. It does not run anything live: Gates 7, 8 and 9 are unexercised,
exactly as `D-70-27`'s standing ruling (back-load blocking-human live gates to end-of-phase UAT)
requires.

## Goal Achievement

### Observable Truths (round-2 plan truths, D-70-24..27)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | D-70-24: no committed n8n workflow contains a self-referencing Execute Workflow node | ✓ VERIFIED | `grep -c '"n8n-nodes-base.executeWorkflow"' n8n/wf_enrichment_cloud.json` = 0 (287 nodes total, down from 291); `n8n/wf_scheduled_maintenance_cloud.json` = 1 (SJ-3, targets a different workflow); all other six workflows = 0. Verified by direct node-count script, not by grepping node names. |
| 2 | A request carrying `scale_up: true` (envelope or event) is refused as a row, never fanned | ✓ VERIFIED | `ENRICH_PARSE_EVENT_CLOUD` (build_cloud_workflows.py:5286-5297) reads `ENVELOPE_SCALE_UP`/`ANY_EVENT_SCALE_UP` and returns a refusal item BEFORE the oversize/empty checks; `tests/n8n/scaleUpRefused.test.mjs` and `tests/n8n/enrichmentBatchRefusal.test.mjs` both green (node --test run, 1075/1075 pass overall). |
| 3 | The five pre-fork starved-lane sentinels are re-sourced from `Parse HubSpot Event`, no sentinel condition still reads `scale_up` | ✓ VERIFIED | `grep -n scale_up scripts/build_cloud_workflows.py` shows only the refusal-read block and two historical comments; no sentinel condition body reads it. `tests/n8n/scaleUpRefused.test.mjs`'s "the five pre-fork sentinels are fed from Parse HubSpot Event" case passes. |
| 4 | D-70-26(a): a self-referencing executeWorkflow node in any built workflow stops generation with a named error | ✓ VERIFIED | `assert_no_self_dispatch` (build_cloud_workflows.py:11286) composed into `_assert_generation_contracts` as the third, outermost contract; default-refuse with one `(workflow, node)`-keyed exemption (`_SELF_DISPATCH_EXEMPTIONS`, keyed on the pair, never node name alone); self-reference check runs BEFORE the exemption is consulted (read directly in the source, matches plan text exactly). RED commit `97e254e` precedes GREEN commit `54d43e9` (confirmed in `git log`). |
| 5 | SJ-3's cross-workflow dispatch still builds, still rebinds at deploy time, and is the ONE named exemption | ✓ VERIFIED | `_SELF_DISPATCH_EXEMPTIONS = frozenset({("wf_scheduled_maintenance_cloud", "SJ-3 Dispatch To Enrichment")})`; `wf_scheduled_maintenance_cloud.json` still carries exactly 1 executeWorkflow node; `tests/test_subworkflow_ref_rebinding.py` green. |
| 6 | The plugin can no longer ask for a fan-out: `dispatch_plan` has no `scale_up` parameter, never stamps one on an envelope | ✓ VERIFIED | `dispatch_plan(plan, providers, armed, config, transport=requests, *, run_id=None, execution_ceiling=None, **_ignored_legacy_kwargs)` (chunking.py:402) — no `scale_up` keyword; a caller still passing it is swallowed by `_ignored_legacy_kwargs`. `grep -rn scale_up operator-claude-plugin/scripts/` returns nothing. |
| 7 | No recovery path in the plugin reads a node that no longer exists | ✓ VERIFIED | `grep -n 'Dispatch Self\|SCALE_UP_DISPATCH_NODE\|child_execution_ids\|include_children' operator-claude-plugin/scripts/*.py` returns nothing; `test_report_sufficiency.py` (single-poll-site invariant) unchanged and green. |
| 8 | D-70-25: a marker item is dropped by both `Build Response` and `Build Ingest Response` before either emits | ✓ VERIFIED | `ROW_IDENTITY_KEYS_JS`/`hasRowIdentity` defined ONCE (build_cloud_workflows.py:86-87), spliced into both `BUILD_INGEST_RESPONSE` (line 596) and `ENRICH_BUILD_RESPONSE` (line 5685) — one shared definition, not two hand-copied lists, confirmed by direct grep. `tests/n8n/buildResponseMarkerFilter.test.mjs`'s fixtures traced to `70-RUNTIME-VERDICT.json`'s actual `sends[0].recovered_shapes` (cross-checked directly against the JSON in this verification, not invented) and `exec_12316.runData.json`'s `object_id: null` — not fabricated. |
| 9 | The drop is pinned by a test built from Gate 5's actual recovered shape, seen RED first | ✓ VERIFIED | RED commit `fa19a23` precedes GREEN commit `04ca411` (git log confirmed); SUMMARY's stated RED transcript (2 items returned, marker survived, before the fix) is consistent with the recorded `recovered_shapes[0]` key set independently re-read from `70-RUNTIME-VERDICT.json` in this verification. |
| 10 | A request-level refusal row still reaches the caller (outcome-only identity) | ✓ VERIFIED | `ROW_IDENTITY_KEYS = ["row_id", "action", "outcome", "object_id", "hs_object_id", "id"]` includes `outcome`; `REFUSAL_ROW` fixture (outcome-only, no action/row_id/object_id) is asserted as a survival case in `buildResponseMarkerFilter.test.mjs`, passing. |
| 11 | D-70-26(b): the walker's engine-fidelity suite carries a frozen reproduction of execution 12316 recording a documented divergence | ✓ VERIFIED | `tests/n8n/walkerEngineFidelity.test.mjs` (5 tests, all pass): frozen body verified 291 nodes/empty settings/zero credentials (re-verified directly in this session, NOT regenerated); runData sidecar verified to name exactly 3 unconnected-source nodes (`Build Scale Up Fan-Out`, `Dispatch Self`, `Recompute Requested Sentinel Gate` — re-derived directly from the sidecar JSON in this session, matches). |
| 12 | That divergence case is a prohibition guard — fails if the walker ever starts reproducing any of the three | ✓ VERIFIED | Test title: "the walker does NOT reproduce the three unconnected-source runs — a prohibition guard, not a model"; asserts absence, not presence. `tests/n8n/lib/walkWorkflow.mjs` confirmed byte-identical to the commit that closed plan 70-13 (`git diff --quiet 51e9722..HEAD -- tests/n8n/lib/walkWorkflow.mjs` — clean, re-run in this session). |
| 13 | CLAUDE.md records the retirement, the execution ids, and the corrected flag count | ✓ VERIFIED | §13.0.2 line 2409: `scale_up` row marked "RETIRED 2026-09-10 (executions 12211-12348)"; heading corrected to "TWO, not three"; node-count table shows 291→287; the four-of-nine deleted nodes named explicitly. `grep -q 12316/12348/'observed live'` all present. |
| 14 | §13.0.3 gains three observed-live platform-fact rows, each with execution ids, no Merge row upgraded | ✓ VERIFIED | Three new rows read directly (deactivation drain lag/tail-errors, `12346`-`12348`; unconnected-source run, `12316`, "cause NOT isolated" stated verbatim; runaway scale, `12209`-`12348`). Line "No Merge-behaviour row above was touched by this round." present immediately after the table. |
| 15 | The deployment-parity note states the current MIXED five-workflow live state | ✓ VERIFIED | Table read directly: enrichment lane live = pre-Phase-70 `59812be` (123 nodes), other four = gap-closure round-1 JSON (69/55/43/30); "Nothing is armed anywhere in this chain" stated explicitly. |
| 16 | The rollback runbook carries a standing two-minute burst watch before every send | ✓ VERIFIED | `70-ROLLBACK-RUNBOOK.md` § Step 6 "watch for a burst BEFORE any send (mandatory, every deploy in this repo)"; names `mode: integrated`, cites `12211`-`12348`, gives the deactivate-then-PUT stop procedure with the observed ~30s drain lag. |
| 17 | Gates 7, 8, 9 recorded in the same shape as Gates 1-6, in order, Gate 6 marked superseded | ✓ VERIFIED | `70-DEFERRED-GATES.md` § Gate 6 header reads "— SUPERSEDED"; §§ Gate 7/8/9 present in order, each with what-it-proves / risk-accepted / operator-steps / pass-criteria shape; Gate 9 references Gate 6's steps with two named substitutions rather than duplicating them (read directly, confirmed). Single ordering rule ("7 before 8, 8 before 9, nothing armed until 8 passes") appears once, covers all three. |
| 18 | Gate 8's text states Gate 5 recovered zero real (row-id-bearing) rows on the enrichment lane | ✓ VERIFIED | § Gate 8 states verbatim: "every recovered row on the enrichment lane had `row_id: null`"; "A marker-free but EMPTY result on this lane is still a FAILURE of this gate, not progress toward passing it." |

**Score:** 18/18 round-2 plan truths verified directly against code, JSON, git history and the
recorded verdict/runData — none accepted on SUMMARY narration alone.

### Round-1 Regression Check (28 prior must-haves)

Round 1's 28 offline-verifiable must-haves (plans 70-01..70-12, D-70-01..23) were re-checked at
existence + basic sanity per the re-verification optimization (passed items get a quick
regression check, not a full re-derivation):

- Full offline suites still green: `node --test tests/n8n/*.test.mjs` **1075/1075 pass** (up
  from round 1's baseline of 1063, reflecting round 2's new `scaleUpRefused.test.mjs`,
  `buildResponseMarkerFilter.test.mjs` and the 3 new `walkerEngineFidelity.test.mjs` cases).
  `.venv/bin/python -m pytest -q --tb=short` **4700 passed, 154 skipped** (unchanged count from
  70-13/14/15's own recorded runs). `cd operator-claude-plugin && ../.venv/bin/python -m pytest
  -q` **2864 passed, 5 skipped** (unchanged).
- `.venv/bin/python scripts/build_cloud_workflows.py` runs clean; second run byte-identical
  (`git status --porcelain -- n8n/` empty) — the generator is still idempotent after three more
  rounds of edits.
- The D-70-20/21/22/23 mechanisms (gated sentinels, ≤10-input Merges, carry-Merges at every
  hop, the Merge-input generation-time contract) are untouched by this round's `files_modified`
  lists (70-13/14/15 touch `build_cloud_workflows.py`'s scale-up/refusal/identity-filter regions
  only) and remain covered by the still-green suites above.
- No regression found.

**Combined score:** 46/46 (18 round-2 truths freshly verified + 28 round-1 truths
regression-checked, with round-1's own `previous_score` line carried forward as the basis — 28
was round 1's own reported count, not independently re-derived truth-by-truth here per the
re-verification optimization).

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `n8n/wf_enrichment_cloud.json` | 287 nodes, 0 executeWorkflow | ✓ VERIFIED | Counted directly: 287 nodes, 0 executeWorkflow matches |
| `n8n/wf_scheduled_maintenance_cloud.json` | 43 nodes, 1 executeWorkflow (SJ-3) | ✓ VERIFIED | Counted directly: 43 nodes, 1 executeWorkflow matches |
| `scripts/build_cloud_workflows.py` | carries `assert_no_self_dispatch`, `ROW_IDENTITY_KEYS_JS`, the scale_up refusal | ✓ VERIFIED | All three present, read directly at their line numbers above |
| `tests/n8n/scaleUpRefused.test.mjs` | exists, replaces deleted `scaleUpFanOutFlow.test.mjs` | ✓ VERIFIED | Present; `scaleUpFanOutFlow.test.mjs` confirmed absent |
| `tests/n8n/buildResponseMarkerFilter.test.mjs` | exists, fixtures traced to the verdict | ✓ VERIFIED | Present; fixtures cross-checked against `70-RUNTIME-VERDICT.json` directly |
| `tests/n8n/fixtures/frozen/wf_enrichment_cloud.gap-closure.2026-09-10.json` | 291 nodes, committed at planning time, never regenerated | ✓ VERIFIED | Read directly: 291 nodes, `settings: {}`, 0 nodes with a `credentials` block |
| `tests/n8n/fixtures/frozen/exec_12316.runData.json` | names exactly 3 unconnected-source nodes | ✓ VERIFIED | Read directly and cross-checked: `Build Scale Up Fan-Out`, `Dispatch Self`, `Recompute Requested Sentinel Gate` |
| `.planning/phases/.../70-DEFERRED-GATES.md` | Gates 7/8/9, Gate 6 superseded | ✓ VERIFIED | Read directly, matches plan text |
| `CLAUDE.md` | retirement, platform facts, parity note | ✓ VERIFIED | Read directly, all three present with execution-id citations |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `Parse HubSpot Event` | refusal row | `ENVELOPE_SCALE_UP \|\| ANY_EVENT_SCALE_UP` before oversize/empty checks | ✓ WIRED | Read directly at build_cloud_workflows.py:5286-5297; test-confirmed |
| Five starved-lane sentinels | `Parse HubSpot Event` (single output) | re-sourced from the deleted routing IF's false lane | ✓ WIRED | `scaleUpRefused.test.mjs` sentinel-sourcing case passes; no Merge starved (full node suite green) |
| `assert_no_self_dispatch` | `_assert_generation_contracts` | composed as third, outermost contract | ✓ WIRED | Read directly at build_cloud_workflows.py:11349-11358 |
| `ROW_IDENTITY_KEYS_JS` | `ENRICH_BUILD_RESPONSE`, `BUILD_INGEST_RESPONSE` | string-concatenated at definition site, before each projection | ✓ WIRED | Read directly at lines 596 and 5685 |
| SJ-3 dispatch node | `_SELF_DISPATCH_EXEMPTIONS` | keyed on `(workflow_name, node_name)` pair | ✓ WIRED | Read directly; pair-keying confirmed, not name-only |
| `n8n_arming.set_write_safety` | `HubSpot Update/Create Write Gate`, `Associate Lane Sentinel` | jsCode `const FLAG = ...;` rewrite | ✓ WIRED | Independently executed against the committed `wf_contact_ingest_cloud.json` in this verification session: rewrite count = 3 for both `ALLOW_HUBSPOT_RECORD_WRITES` and `TEST_RECORD_IDS` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Enrichment graph has zero executeWorkflow nodes | `node -e "require('./n8n/wf_enrichment_cloud.json').nodes.length"` + grep count | 287 nodes, 0 executeWorkflow | ✓ PASS |
| Maintenance graph has exactly 1 executeWorkflow (SJ-3) | same, `wf_scheduled_maintenance_cloud.json` | 43 nodes, 1 executeWorkflow | ✓ PASS |
| `set_write_safety` rewrites exactly 3 nodes on the ingest JSON | direct Python invocation against committed JSON (this session) | `{'ALLOW_HUBSPOT_RECORD_WRITES': 3, 'TEST_RECORD_IDS': 3}` | ✓ PASS |
| Walker file unchanged since 70-13's close | `git diff --quiet 51e9722..HEAD -- tests/n8n/lib/walkWorkflow.mjs` | clean, exit 0 | ✓ PASS |
| RED-before-GREEN for `assert_no_self_dispatch` | `git log` for `97e254e`/`54d43e9` order | RED commit precedes GREEN commit | ✓ PASS |
| RED-before-GREEN for the marker filter | `git log` for `fa19a23`/`04ca411` order | RED commit precedes GREEN commit | ✓ PASS |
| Generator idempotent | `.venv/bin/python scripts/build_cloud_workflows.py && git status --porcelain -- n8n/` | clean, no diff | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repo (`find scripts -path '*/tests/probe-*.sh' -type f` returns nothing). N/A.

### Requirements Coverage

Phase requirement IDs: none — `.planning/REQUIREMENTS.md` carries no "Phase 70" mapping
(confirmed by direct grep, no hits). The phase's contract is the locked decisions D-70-01..27
in `70-CONTEXT.md`; this round's are D-70-24, D-70-25, D-70-26, D-70-27, all covered above.

### Anti-Patterns Found

Scanned every file in round 2's `files_modified`/`key-files` lists (generator, plugin scripts,
test files, CLAUDE.md, CHANGELOG.md, n8n/README.md, the runbook, the deferred-gates file, the
frozen fixtures README) for `TBD|FIXME|XXX` (blocker gate) and `TODO|HACK|PLACEHOLDER` (warning):

- One `XXX` match in `n8n/README.md` (`0XXXXXXXXX`, `61XXXXXXXXX`) — a phone-number-format
  placeholder pattern in prose describing AU phone normalization, not a debt marker. Not a
  blocker.
- No other matches in either category.

No blockers found.

### Human Verification Required

See `human_verification` in frontmatter — Gates 7, 8 and 9, all deferred operator live gates per
`D-70-27`. Summary:

1. **Gate 7** — disarmed deploy + bounce of the loop-free 287-node body, then a two-minute
   burst watch with nothing sent. Nothing armed, nothing sent by this gate itself.
2. **Gate 8** — disarmed live proof re-run (all four sends), plus the new runData-source-vs-
   declared-connections check, the exact detector for what execution 12316 exhibited. Gate 8's
   own text names the risk this verification cannot close offline: Gate 5 recovered zero
   enrichment rows carrying a real `row_id`, so a clean row count post-fix is not itself proof
   the real rows are now present — that must be checked live.
3. **Gate 9** — the one armed HubSpot write this phase's close makes, only after Gate 8 passes.

### Gaps Summary

No gaps. `G-70-5` is closed at the offline layer this round can verify (the mechanism is
removed by absence, the request is refused, generation refuses a recurrence, markers cannot
leak, the divergence is recorded rather than guessed at). The phase goal's second clause — "the
offline harness would have caught every finding the 2026-09-09 UAT found" — is provable only by
Gate 8 running clean on the loop-free graph; no committed workflow carrying the current
Merge/gate redesign has completed that proof yet, so `passed` would be premature. This is the
correct honest state per this project's own standing pattern (`backload-human-gates-to-end-of-
phase` memory) and per `D-70-27`'s ordering rule (7 before 8, 8 before 9, nothing armed until 8
passes) — the phase cannot close itself; only the operator, running the gates in order, can.

One advisory item is recorded (not a gap): an armed enrichment write row's bare `{id,
properties}` shape (no carry-merge-reattached `row_id`/`action`) — pre-existing, discovered
rather than introduced by this round, unevidenced as a live problem, and outside the scope of
Gates 7/8/9 (which arm the ingest lane, not enrichment). See `advisory:` in frontmatter.

---

_Verified: 2026-09-10T09:30:00Z_
_Verifier: Claude (gsd-verifier)_
