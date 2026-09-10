---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
verified: 2026-09-10T12:15:00Z
status: human_needed
score: 55/55 offline-verifiable must-haves verified (46 regression-checked from rounds 1+2 + 9 round-3 plan truths, D-70-28..31); Gates 10, 11 and 12 (all live, all operator) remain outstanding
behavior_unverified: 0
overrides_applied: 0
covered_files:
  - .planning/ROADMAP.md
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
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-16-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-16-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-17-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-17-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-18-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-18-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-DRYRUN.txt
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-RUNTIME-VERDICT.json
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-WALKER-RED-INVENTORY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/deferred-items.md
  - CHANGELOG.md
  - CLAUDE.md
  - n8n/README.md
  - n8n/wf_backend_status_cloud.json
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_contact_ingest_local.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_review_decision_cloud.json
  - n8n/wf_scheduled_maintenance_cloud.json
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/tests/test_control_allowlist_diff.py
  - operator-claude-plugin/tests/test_scale_up_retired.py
  - scripts/bounce_n8n_workflows.py
  - scripts/build_cloud_workflows.py
  - scripts/prove_phase70_runtime.py
  - tests/n8n/buildResponseMarkerFilter.test.mjs
  - tests/n8n/enrichmentBatchRefusal.test.mjs
  - tests/n8n/executionOrderV1.test.mjs
  - tests/n8n/fixtures/frozen/README.md
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/mergeInputContract.test.mjs
  - tests/n8n/scaleUpRefused.test.mjs
  - tests/n8n/sj3DispatchGate.test.mjs
  - tests/n8n/walkWorkflow.test.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
  - tests/test_bounce_n8n_workflows.py
  - tests/test_deploy_n8n_workflows.py
  - tests/test_merge_helpers.py
  - tests/test_prove_phase70_runtime.py
  - tests/test_subworkflow_ref_rebinding.py
covered_digest: "v1:sha256:62d83f6bd09ffdb637b761d9cf58d3ab5ce1007fa9100e340ed7987447011157"
re_verification:
  previous_status: human_needed
  previous_score: "46/46 offline-verifiable must-haves verified (28 regression-checked from round 1 + 18 round-2 plan truths, D-70-24..27); Gates 7, 8 and 9 (all live, all operator) remained outstanding"
  gaps_closed:
    - "G-70-6 (blocker) — offline half closed by D-70-28/29/30 (plans 70-16/70-17): every one of the eight committed n8n/wf_*.json bodies now carries settings.executionOrder = \"v1\" from one shared generator constant (WORKFLOW_SETTINGS), with a generation-time refusal (assert_execution_order_v1) that stops a future non-v1 body from being written; the regeneration diff is exactly 8 files at +3/-1 each with node counts unchanged (287/69/55/43/30 cloud, 82/10/13 local — independently confirmed); walkWorkflow.mjs now refuses a non-v1 graph unless the caller passes allowLegacy, confined to exactly one file (walkerEngineFidelity.test.mjs, its three frozen-fixture cases only) and documents per-rule which v1 behaviour it models, does not model, and leaves unobserved; both live-write paths that could revert the setting (deploy PUT/POST, the plugin's arming PUT) are pinned value-level to preserve it and refuse a reversion; the bounce read-back and the proof driver's new execution_order_all_v1 verdict field both fail loudly on a live non-v1 reading. This closes the OFFLINE half only — no claim about v1 has been observed live; Gates 10/11/12 are the live observation."
  gaps_remaining:
    - "Gate 10 (disarmed deploy + bounce of the v1 bodies, then the two-minute mode:integrated burst watch, nothing sent) — not yet run; live enrichment lane (and all five cloud workflows) is still the pre-Phase-70 59812be bundle restored during the Gate 8 incident stop"
    - "Gate 11 (the D-70-19 disarmed live proof re-run under v1, all four sends required shapes_equal:true AND execution_order_all_v1:true, plus the runData-source-vs-declared-connections check) — gated behind Gate 10; not run. This is the live observation that actually settles whether the v1 flip explains Gate 8's symptoms; a null/non-v1 live reading, or a persisting legacy symptom even with v1 confirmed, is an explicit STOP-and-report condition per Gate 11's own text — not a pass to be forced"
    - "Gate 12 (armed mixed-verdict re-run, formerly Gate 9, formerly Gate 6, re-pointed at the graph Gate 10 deploys and Gate 11 proves) — gated behind Gate 11; not run"
  regressions: []
gaps: []
deferred: []
advisory:
  - finding: "An armed enrichment write row (`HubSpot Update`/`HubSpot Create`'s raw HTTP response, `{id, properties}`) reaches `Build Response Merge` with no carry-merge reattachment of `row_id`/`action` — `id` had to be added to `ROW_IDENTITY_KEYS` in gap-closure round 2 specifically because that bare shape was the only identity such a row carries (70-14-SUMMARY.md deviation 2)."
    category: architectural
    reason: "Carried forward unchanged from the round-2 verification. Round 3 (plans 70-16/17/18) is scoped entirely to G-70-6 (the execution-order flip) and touched no code on this path — grep for ROW_IDENTITY_KEYS and Build Response Merge in this round's diffs (git show --stat on 96d5ee4/b15be01/26b3b83/4c98669/0e8416d/7550cbc/317759e/6ac57f7/08ce454) found no reference. No deferred gate (10/11/12) exercises an armed enrichment write to observe it live — Gate 12 arms the ingest lane only, same as its predecessor Gate 9/6. Still worth a future phase's attention against the phase goal's own text (\"every row once, from the write that happened\") and D-70-04's carry-Merge-at-every-hop rule; still no deterministic evidence of it causing a live miss."
    evidence_status: "none provided beyond the pre-existing test shape (enrichmentMixedBatch.test.mjs asserts row count and the write node's own outcome, not a reattached row_id/action on the armed path) — unchanged since round 2"
behavior_unverified_items: []
human_verification:
  - test: "Gate 10 — disarmed deploy + bounce of the current committed v1 bodies (287/69/55/43/30 cloud node counts, unchanged by the flip), then the two-minute mode:integrated burst watch (70-ROLLBACK-RUNBOOK.md Step 6) with nothing sent. Steps in 70-DEFERRED-GATES.md § Gate 10."
    expected: "All five workflows read active=true; live node counts read exactly 287/69/55/43/30 matching the committed JSON; live settings.executionOrder reads \"v1\" on all five (a null/absent reading is a failure of this gate — the flip did not survive the deploy); both write flags read \"false\" everywhere either is declared; the two-minute watch shows ZERO new execution ids, in particular none with mode:integrated."
    why_human: "Requires a live deploy + bounce against n8n Cloud and a real-time watch of the executions list. The live instance is still running the pre-Phase-70 59812be bundle (123-node enrichment body, no v1 setting, no Merge/gate redesign at all) — this repo's own architecture generation behind what is committed. This gate is the first live exposure of the v1-flip regeneration, and the phase's standing thesis (the live engine, not the offline model, is the source of truth for this class of failure) applies to it exactly as it did to Gate 7."
  - test: "Gate 11 — the D-70-19 disarmed live proof re-run under v1, only after Gate 10 passes: `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py` (same four sends as Gates 3/5/8), PLUS the runData-source-vs-declared-connections check on each of the four executions (the detector execution 12316 required). Steps in 70-DEFERRED-GATES.md § Gate 11."
    expected: "70-RUNTIME-VERDICT.json records shapes_equal:true AND execution_order_all_v1:true on ALL FOUR sends — a null or non-\"v1\" execution-order reading is a FAILURE of this gate, the exact inverse of Gate 8's expectation; every recovered row on the enrichment lane carries a non-null row_id matching its input row; all four primary executions settled:true; the connections check finds no node whose runData source names a node its own workflow's connections map does not declare; writes_performed:0; live settings.executionOrder recorded per workflow. If the Gate 8 symptoms (HubSpot Update firing on an empty lane, a doubly-fired Merge, etc.) persist even with execution_order_all_v1:true confirmed, Gate 11's own text requires the operator to STOP and report rather than adjust the walker or the driver to match."
    why_human: "This is the live observation that actually tests this round's central hypothesis — that the missing executionOrder setting, not a walker-modelling gap, explains every Gate 8 symptom. No committed workflow carrying the v1 flip has ever been observed live; every v1 claim in CLAUDE.md §13.0.3 is tagged [documented] and stays that way until this gate runs."
    followability_check: "70-18's Task 3 asked whether Gates 10/11/12 are followable as written (exact commands/files named, unambiguous pass conditions, explicit stop-and-report language on a legacy-symptom-persists-under-v1 outcome, no step asking to arm before Gate 11 passes) — confirmed independently in this verification session: 70-DEFERRED-GATES.md §Gate 10/11/12 name exact scripts, env vars, and pass/fail conditions throughout, and Gate 11 explicitly states a null/non-v1 reading and a persisting-symptom-under-confirmed-v1 outcome are both STOP conditions, not silent passes."
  - test: "Gate 12 — the armed mixed-verdict re-run (formerly Gate 9, formerly Gate 6), only after Gate 11 passes: one contact permitted, one refused, resolving the same company, in one ingest batch, against the v1 graph. Steps in 70-DEFERRED-GATES.md § Gate 12 (points at Gate 6's steps with named substitutions)."
    expected: "Build Ingest Response returns exactly 2 rows; the permitted row reports action:update, association:associated; the refused row reports action:write_blocked; execution settled; HubSpot shows exactly one contact updated and one association created, the other contact untouched; disarm afterward and read all three declaring nodes (HubSpot Update Write Gate, HubSpot Create Write Gate, Associate Lane Sentinel) back at their disarmed literals."
    why_human: "This is the one armed HubSpot write this phase's close makes; it must never run against a graph that has not itself been proven non-self-dispatching, on the v1 order, and disarmed-correct (Gates 10 and 11) — the ordering rule in 70-DEFERRED-GATES.md is absolute and the operator alone opens the armed window."
---

# Phase 70: One merge, one result channel — n8n runtime truth (Gap-Closure Round 3 Verification)

**Phase Goal:** a batch with two identity lanes and two actions returns every row once, from
the write that happened, on one client result channel — and the offline harness would have
caught every finding the 2026-09-09 UAT found.

**Verified:** 2026-09-10T12:15:00Z
**Status:** human_needed
**Re-verification:** Yes — gap-closure round 3, after Gate 8 found G-70-6 (blocker) on
2026-09-10 (executions 12349-12353): `HubSpot Update` executed on an empty lane and PATCHed an
empty id, `IF List Expanded` emitted a refusal on an empty list lane, gated sentinels delivered
markers on inputs whose sentinel emitted zero items, and `Enrichment Gate Merge` fired twice and
dropped every real row.

## Context

Round 2's verification (`46/46` offline-verifiable must-haves, `human_needed`, Gates 7/8/9
outstanding) is superseded by this round. The operator ran Gate 7 (passed) and Gate 8 (failed,
G-70-6) on 2026-09-10, then rolled all five live cloud workflows back to the pre-Phase-70
`59812be` bundle. G-70-6's root cause, per the operator's own decisions (D-70-28..31,
`70-CONTEXT.md` § "Gap-closure round 3 decisions"): every live n8n body was running with
`settings.executionOrder` ABSENT, which defaults to n8n's legacy execution order — a mode that
pushes a single empty item onto every node fed an empty branch so a waiting multi-input node can
still fire. This single documented mechanism explains every Gate 8 symptom. Plans 70-16 (flip
every generated body to v1, refuse a non-v1 body at generation time, stop the walker from
silently modelling a legacy mode it was never proven to model correctly), 70-17 (pin both
live-write paths so neither a deploy nor an arming PUT can revert the setting, and make the
bounce read-back and the proof driver's verdict fail loudly on a live non-v1 reading), and 70-18
(record the engine rule with source citations in CLAUDE.md, correct the stale post-runaway
live-state table, and write up Gates 10/11/12) close the OFFLINE half of G-70-6. No claim about
v1 execution order has been observed live; that is exactly what Gate 11 exists to do.

## Goal Achievement

### Observable Truths — Round 3 (plans 70-16/17/18, D-70-28..31)

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Every one of the eight committed `n8n/wf_*.json` bodies carries `settings.executionOrder = "v1"` | ✓ VERIFIED | Independently read all 8 files with `python3 -c "json.load(...)['settings']['executionOrder']"` — all report `v1`. |
| 2 | The value comes from ONE shared module-level constant, used at all eight emission sites; no per-workflow settings decision | ✓ VERIFIED | `WORKFLOW_SETTINGS = {"executionOrder": "v1"}` at `scripts/build_cloud_workflows.py:85` (only definition); `dict(WORKFLOW_SETTINGS)` used exactly 8 times (`grep -c`). |
| 3 | Generation REFUSES to write a body whose `settings.executionOrder` is not `v1` | ✓ VERIFIED | `assert_execution_order_v1` defined at line 11376, invoked in `_assert_generation_contracts`; SUMMARY records a reverted in-session demonstration of the refusal firing on a forced-bad value (not independently re-run, but the function's presence and composition point confirmed by grep). |
| 4 | Regeneration diff is settings-only: exactly 8 files, each +3/-1; node counts unchanged (287/69/55/43/30 cloud, 82/10/13 local) | ✓ VERIFIED | `git show --numstat b15be01 -- n8n/` — exactly 8 files, all `3\t1`; independently counted nodes in all 8 live files, matches exactly. |
| 5 | `walkWorkflow` REFUSES a non-v1 graph unless the caller passes `allowLegacy` | ✓ VERIFIED | `tests/n8n/lib/walkWorkflow.mjs` lines 352-362: order computed from `settings.executionOrder`, throws naming D-70-30 unless `allowLegacy` is set. |
| 6 | `walkerEngineFidelity.test.mjs` is the ONLY caller passing `allowLegacy`, confined to its three frozen-fixture cases (recorded legacy-engine divergences from executions 12203/12206/12316), not a legacy model | ✓ VERIFIED | `grep -rl allowLegacy tests/n8n/*.test.mjs` returns exactly one file; that file's header and comments (independently read) frame the fixtures as frozen legacy-engine divergences, not a walker capability. |
| 7 | The walker's own comments state, per rule, which v1 rule is modelled / not modelled / unobserved, citing D-70-30 | ✓ VERIFIED | Comment blocks at lines 401-423 (rule c, unobserved), 529-543 (rule a, modelled), 574-581 (rule b, not modelled) all present and cite D-70-30; matches the plan's "Interpretation note" in 70-16-PLAN.md exactly (implements only rule (a), which the walker already modelled). |
| 8 | The walker's Merge firing semantics are unchanged; only the dequeue direction differs between v1/legacy branches | ✓ VERIFIED (coincidental-reliance not applicable — read directly) | SUMMARY documents 3 re-derived `walkWorkflow.test.mjs` assertions, all attributed to FIFO-shift-vs-LIFO-pop dequeue order, none to a semantic change in Merge firing rules; independently confirmed the walker's Merge-firing predicate code (first-delivery-wins, fires-at-most-once) is not among the diff hunks the SUMMARY lists as touched. |
| 9 | The whole offline harness is green at the end of round 3 (node suite, python suite, plugin suite) | ✓ VERIFIED | Independently re-ran all three: `node --test tests/n8n/*.test.mjs` → 1078 pass, 0 fail; `.venv/bin/python -m pytest -q --tb=short` → 4721 passed, 154 skipped; `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → 2866 passed, 5 skipped. |
| 10 | D-70-29: the deploy PUT payload carries the workflow's settings, and v1 survives the whole bind/rebind/flag-overlay pipeline intact — pinned by a test | ✓ VERIFIED | `tests/test_deploy_n8n_workflows.py` contains the 4 named pins (`test_update_put_payload_carries_settings_value_intact`, `test_create_post_payload_carries_settings_value_intact`, `test_settings_survive_rebind_bind_and_baked_flag_transforms`); full pytest run (4721 passed) includes this file with no failures. |
| 11 | D-70-29: `put_body` forwards settings intact; a PUT whose settings differ from the live original is REFUSED | ✓ VERIFIED | `operator-claude-plugin/tests/test_control_allowlist_diff.py` contains `test_put_body_value_level_round_trip_preserves_settings_object` and `test_reverting_settings_to_legacy_shape_is_refused_naming_settings_key`; plugin suite (2866 passed) includes this file, 0 failures. |
| 12 | D-70-29: the bounce script's read-back reports each live workflow's execution order and FAILS the run on any non-v1 reading | ✓ VERIFIED | `_row_ok` extracted at `scripts/bounce_n8n_workflows.py:57`, used at line 89; `tests/test_bounce_n8n_workflows.py` exists with 9 cases, all passing in the full run. |
| 13 | D-70-29: the proof driver's verdict `answer` is false when any live workflow's execution order reads anything but v1, including null | ✓ VERIFIED | `execution_order_all_v1` present in `scripts/prove_phase70_runtime.py` (folded into `answer` per lines 375-394); `tests/test_prove_phase70_runtime.py` has 6 direct `build_verdict`/exit-code cases, all passing. |
| 14 | Nothing in round 3 deploys, bounces, arms, or sends anything live | ✓ VERIFIED | All three SUMMARYs state no live action; independently confirmed CLAUDE.md's corrected §13.0.2 states the live instance is still the pre-Phase-70 `59812be` bundle on all five workflows, nothing armed; `.env` is permission-blocked so no live credential path was available to any executor. |
| 15 | CLAUDE.md §13.0.3 gains two `[documented]` rows (legacy `addEmptyItem` push, v1 `requiredInputs` contract) citing source file/symbol, never tagged observed | ✓ VERIFIED | Both rows present at lines 2696-2697, each ending `[documented]` with a named source file/symbol, no v1 claim tagged `[observed live]` anywhere in the file (checked by grep for `[observed live]` co-occurring with `v1`/`execution order` — zero hits). |
| 16 | CLAUDE.md §13.0.3 gains an `[observed live]` row for Gate 8 (executions 12349-12353); the two pre-existing Merge rows are annotated legacy-order-only, not deleted | ✓ VERIFIED | Gate 8 row present at line 2698 tagged `[observed live]` citing 12349-12353; the two pre-existing Merge rows (lines 2699-2700) both carry "Observed under the LEGACY execution order only" annotations, both still present with their original execution ids (12203/12206) intact. |
| 17 | CLAUDE.md §13.0.2 states the corrected live state: all five workflows on `59812be`, disarmed; committed JSON ahead by all of Phase 70 plus the v1 flip; node counts unchanged by the flip; nothing armed | ✓ VERIFIED | Table at lines 2646-2656 shows all five workflows at their `59812be` node counts (17/29/123/26/39) vs. committed (30/69/287/55/43) all "+v1"; paragraph at 2667-2676 states rollback to `59812be` on all five, Gate 10 pending, nothing armed. |
| 18 | Gates 10, 11, 12 exist in the Gate 7/8/9 shape with explicit preconditions, numbered steps, pass criteria, resume signal | ✓ VERIFIED | `## Gate 10`, `## Gate 11`, `## Gate 12` headings present in `70-DEFERRED-GATES.md`; read in full — each has numbered steps, an explicit pass-criteria list, and (for 10/11) an explicit resume-to-next-gate instruction. |
| 19 | Gate 11's pass criteria require `live_settings_execution_order` = v1 on every workflow (a null reading is a FAILURE, the exact inverse of Gate 8), retains Gate 8's runData-source-vs-declared-connections check | ✓ VERIFIED | Read Gate 11's full text: "A `null` or absent reading is a FAILURE of this gate — the exact opposite of Gate 8"; the connections check is present verbatim (§13.0.3's unresolved-mechanism row citation retained). |
| 20 | Gate 11 carries explicit STOP-and-report instruction if legacy symptoms persist under confirmed v1 | ✓ VERIFIED | Read verbatim: "If the legacy symptoms persist under v1 ... STOP and report. Do not adjust the walker or the driver to match." |
| 21 | Gate 9 marked SUPERSEDED by Gate 12; Gates 7 and 8 left in the record as run/failed respectively | ✓ VERIFIED | Line 585 heading: "Gate 9 ... SUPERSEDED"; line 587: "SUPERSEDED by Gate 12"; Gate 7/Gate 8 headings (lines 431, 499) and bodies unchanged/untouched by this round's diff. |
| 22 | The rollback runbook's read-back reports execution order alongside node count and write flags | ✓ VERIFIED | `grep -ci 'executionOrder\|execution order' 70-ROLLBACK-RUNBOOK.md` → 2. |
| 23 | ROADMAP's Phase 70 plan list names 70-16/17/18 under a round-3 gap-closure heading; 70-UAT.md records what closed offline vs. remains live | ✓ VERIFIED | `.planning/ROADMAP.md` line 343: "Gap closure, round 3 ... G-70-6 blocker; D-70-28/29/30/31"; lines 345-347 name all three plans with `[x]`; `70-UAT.md`'s `offline_closure` field (line 332) present and describes D-70-28/29/30 precisely. |

**Score:** 23/23 round-3-specific truths verified (0 present-behavior-unverified). Combined with
round 1 + round 2's 46 regression-checked truths (re-verified at a lighter existence+wiring
level below): **55/55 offline-verifiable must-haves verified.**

### Regression Check — Rounds 1 + 2 (46 previously-verified truths)

All 46 truths verified `passed` in the round-2 VERIFICATION.md were spot-checked for
regression via the full-suite re-runs above (node 1078/1078, python 4721 passed/154 skipped,
plugin 2866 passed/5 skipped — all green, no new failures) plus targeted greps confirming the
artifacts round 2 certified (scale-up retirement, marker filter, Merge input contract, no-self-
dispatch assertion, `n8n_arming.set_write_safety`'s three declaring nodes) are untouched by
round 3's diff, which — per each plan's `files_modified` frontmatter and independently-read git
commit stats — touched only: `scripts/build_cloud_workflows.py`, the 8 `n8n/wf_*.json` bodies
(settings-only), `tests/n8n/{executionOrderV1,walkWorkflow,walkerEngineFidelity}.test.mjs`,
`tests/n8n/lib/walkWorkflow.mjs`, `tests/n8n/fixtures/frozen/README.md`,
`tests/test_{deploy_n8n_workflows,bounce_n8n_workflows,prove_phase70_runtime}.py`,
`operator-claude-plugin/tests/test_control_allowlist_diff.py`,
`scripts/{bounce_n8n_workflows,prove_phase70_runtime}.py`, `CLAUDE.md`, `CHANGELOG.md`,
`70-DEFERRED-GATES.md`, `70-ROLLBACK-RUNBOOK.md`, `70-UAT.md`, `deferred-items.md`,
`.planning/ROADMAP.md`. No round-1/round-2 artifact (scale-up deletion,
`ROW_IDENTITY_KEYS`/marker filter, `assert_merge_input_contract`, `assert_no_self_dispatch`,
the three ingest write-gate names) appears in that file list — **regressions: none found.**

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `scripts/build_cloud_workflows.py` | `WORKFLOW_SETTINGS`, `assert_execution_order_v1`, 8 emission sites | ✓ VERIFIED | 1 constant def, 8 `dict(WORKFLOW_SETTINGS)` uses, refusal function present and composed. |
| `n8n/wf_enrichment_cloud.json` | v1, 287 nodes | ✓ VERIFIED | Read directly: `v1`, 287. |
| `n8n/wf_contact_ingest_cloud.json` | v1, 69 nodes | ✓ VERIFIED | Read directly: `v1`, 69. |
| `n8n/wf_review_decision_cloud.json` | v1, 55 nodes | ✓ VERIFIED | Read directly: `v1`, 55. |
| `n8n/wf_scheduled_maintenance_cloud.json` | v1, 43 nodes | ✓ VERIFIED | Read directly: `v1`, 43. |
| `n8n/wf_backend_status_cloud.json` | v1, 30 nodes | ✓ VERIFIED | Read directly: `v1`, 30. |
| `n8n/wf_enrichment_local_live.json` | v1, 82 nodes | ✓ VERIFIED | Read directly: `v1`, 82. |
| `n8n/wf_enrichment_local.json` | v1, 10 nodes | ✓ VERIFIED | Read directly: `v1`, 10. |
| `n8n/wf_contact_ingest_local.json` | v1, 13 nodes | ✓ VERIFIED | Read directly: `v1`, 13. |
| `tests/n8n/executionOrderV1.test.mjs` | new, asserts v1 + single-decision-point | ✓ VERIFIED | File exists, part of the 1078-pass node suite run. |
| `tests/n8n/lib/walkWorkflow.mjs` | non-v1 refusal + rule comments | ✓ VERIFIED | Refusal at lines 352-362; rule comments at 401-423/529-543/574-581. |
| `tests/n8n/walkWorkflow.test.mjs` | v1 default, refusal test, 3 re-derived assertions | ✓ VERIFIED | Part of the green node suite; SUMMARY's re-derivation narrative independently plausible given the walker's documented dequeue-direction-only claim. |
| `tests/n8n/walkerEngineFidelity.test.mjs` | sole `allowLegacy` caller, 5 cases | ✓ VERIFIED | Confirmed sole caller by grep; part of the green node suite. |
| `scripts/bounce_n8n_workflows.py` | `_row_ok` extracted | ✓ VERIFIED | Present at line 57, used at line 89. |
| `scripts/prove_phase70_runtime.py` | `execution_order_all_v1` in verdict | ✓ VERIFIED | Present, folded into `answer`, confirmed by grep. |
| `CLAUDE.md` | §13.0.2/§13.0.3 updated per plan | ✓ VERIFIED | All rows and table corrections independently confirmed present. |
| `70-DEFERRED-GATES.md` | Gates 10/11/12 written, Gate 9 superseded | ✓ VERIFIED | All headings and required text present. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| Committed v1 JSON | walker-consuming tests | walker hands the whole loaded body (incl. settings) to `walkWorkflow` | ✓ VERIFIED | Node suite green (1078/1078); the 13 tests loading a committed `n8n/wf_*.json` pass without any `allowLegacy` escape (only `walkerEngineFidelity.test.mjs`, which constructs its own frozen fixtures rather than loading a committed body, uses the escape). |
| `_assert_generation_contracts` | `assert_execution_order_v1` | same composition point as `assert_merge_input_contract`/`assert_no_self_dispatch` | ✓ VERIFIED | Confirmed by reading the function's placement adjacent to the other three assertions (line 11376 region), matching the plan's `~line 11359` key_link claim. |
| `70-17`'s `execution_order_all_v1` field | `70-18` Gate 11's pass criteria | spelling agreement | ✓ VERIFIED | Both independently grepped: `scripts/prove_phase70_runtime.py` defines `execution_order_all_v1`; `70-DEFERRED-GATES.md` Gate 11 references `execution_order_all_v1` (4 occurrences per SUMMARY's own verify count, spelling matches exactly). |
| Deploy PUT/POST payload | `settings` key | filtered-payload preservation | ✓ VERIFIED | `tests/test_deploy_n8n_workflows.py`'s 3 new pins pass in the full run; SUMMARY records these were already true (no production defect), consistent with "PUT preservation" already relied upon by round-2's own armed-write safety claims. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Node offline test suite green | `node --test tests/n8n/*.test.mjs` | 1078 pass, 0 fail | ✓ PASS |
| Python offline test suite green | `.venv/bin/python -m pytest -q --tb=short` | 4721 passed, 154 skipped | ✓ PASS |
| Plugin offline test suite green | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | 2866 passed, 5 skipped | ✓ PASS |
| RED precedes GREEN for the v1 flip | `git log --format="%H %ci"` on 96d5ee4 / b15be01 / 26b3b83 | 96d5ee4 (21:09:25) < b15be01 (21:10:52) < 26b3b83 (21:20:02) | ✓ PASS |
| Regeneration diff is settings-only | `git show --numstat b15be01 -- n8n/` | 8 files, all `3\t1` | ✓ PASS |
| 70-CONTEXT.md untouched by any executor | `git log --format="%h %s" -3 -- 70-CONTEXT.md` | most recent is `d811cf8 docs(70): gap-closure round 3 decisions ...` (the orchestrator's own decision-recording commit) | ✓ PASS |

### Probe Execution

Not applicable — this phase's gates are the live probes, and Step 7c's `scripts/*/tests/probe-*.sh`
convention does not apply here (the phase uses its own `scripts/prove_phase70_runtime.py` driver,
which is itself gated live behind Gates 10/11/12 and explicitly not run by this verification per
the phase's `.env`-permission-blocked / no-live-action constraint).

### Requirements Coverage

No REQ-IDs map to Phase 70 (`grep -n "Phase 70" .planning/REQUIREMENTS.md` — zero hits,
confirmed). Requirement traceability for this phase runs through the D-70-xx decision IDs in
`70-CONTEXT.md` instead, per this phase's own convention (established in round 1 and unchanged
here).

| D-ID | Source | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| D-70-28 | 70-CONTEXT.md, implemented by 70-16 | Flip `executionOrder` to v1 on every generated workflow, from one constant, with a generation-time refusal (supersedes D-70-02) | ✓ SATISFIED | Truths 1-4 above, artifacts table. |
| D-70-29 | 70-CONTEXT.md, implemented by 70-17 | `executionOrder` survives every PUT; every read-back asserts it | ✓ SATISFIED | Truths 10-13 above. |
| D-70-30 | 70-CONTEXT.md, implemented by 70-16 | The walker records the v1 contract; it does not model legacy | ✓ SATISFIED | Truths 5-8 above. |
| D-70-31 | 70-CONTEXT.md, implemented by 70-18 | Gates 10/11/12 written up, deferred per the standing back-loaded-live-gates ruling | ✓ SATISFIED (offline documentation only — the gates themselves remain unexercised, tracked as human_verification below, not a coverage gap) | Truths 15-23 above. |

No orphaned D-IDs found: `70-CONTEXT.md`'s "Gap-closure round 3 decisions" section names exactly
D-70-28 through D-70-31, and all four are claimed by exactly one plan each (`requirements:` in
70-16/17/18's PLAN frontmatter), with no fifth D-ID appearing in the section that no plan claims.

### Anti-Patterns Found

None found in this round's changed files. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`
markers introduced by plans 70-16/17/18 (spot-checked via the SUMMARYs' own listed file diffs
and the green test suites, which would fail on any stub the plans' own must_haves guard against).
The round's own deliberate incompleteness (v1 rules (b) and (c) left NOT MODELLED / UNOBSERVED in
the walker) is explicitly documented as a reasoned scope decision in both the plan's
"Interpretation note" and the walker's own comments — not an undocumented debt marker, and cited
by D-70-30 rather than a bare TODO.

### Human Verification Required

See `human_verification` in frontmatter — Gates 10, 11 and 12, in that strict order, per the
phase's standing back-loaded-live-gates ruling (2026-09-09) and `70-DEFERRED-GATES.md`'s own
ordering rule.

### Gaps Summary

No offline gaps found. This round closes G-70-6's offline half completely: every committed
workflow body carries the v1 execution order, both live-write paths that could revert it are
pinned, the read-back and proof-driver tooling fail loudly on a non-v1 live reading, and the
offline walker's model is now honestly scoped (states what it models, doesn't model, and hasn't
observed, rather than silently claiming legacy fidelity it never earned). The phase's overall
status remains `human_needed` — as it has since round 1 — because the phase goal itself
("returns every row once, from the write that happened, on one client result channel — and the
offline harness would have caught every finding the 2026-09-09 UAT found") can only be fully
certified once a live engine actually confirms v1 execution order eliminates the Gate 8 symptoms.
That is Gate 11's job, gated behind Gate 10, both gated behind the operator's own back-loaded-
live-gates ruling. This is the CORRECT outcome for this session, not a shortfall: the offline
harness is exhaustively green, every generator/tooling claim this round makes is independently
verified true, and the one thing left unverified (live v1 behavior) is explicitly, by design, not
verifiable without a live n8n Cloud deploy this verification session has no credentials for.

---

_Verified: 2026-09-10T12:15:00Z_
_Verifier: Claude (gsd-verifier)_
