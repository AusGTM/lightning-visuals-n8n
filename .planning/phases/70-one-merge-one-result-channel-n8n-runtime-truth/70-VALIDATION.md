---
phase: "70"
slug: "one-merge-one-result-channel-n8n-runtime-truth"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: true) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true  # 70-01 landed it 2026-09-09
created: "2026-09-09"
validated: "2026-09-11"
---

# Phase 70 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node built-in `node:test` (`tests/n8n/`, ESM `.test.mjs`); `pytest` (`operator-claude-plugin/tests/`, root `tests/`) |
| **Config file** | none — bare `node --test`; pytest defaults via `.venv` |
| **Quick run command** | `node --test tests/n8n/*.test.mjs` (glob form — the directory form is broken on node 24) |
| **Full suite command** | `.venv/bin/python -m pytest -q --tb=short` (root, ~4600 tests) and `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (plugin, ~2850) |
| **Estimated runtime** | node suite ~60 s; plugin suite ~120 s; root suite ~300 s |

---

## Sampling Rate

- **After every task commit:** Run `node --test tests/n8n/*.test.mjs` for any builder / `n8n/code` / JSON change; `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` for any client change
- **After every plan wave:** Run `.venv/bin/python -m pytest -q --tb=short` plus the node suite
- **Before `/gsd-verify-work`:** Full suite must be green on both sides; D-70-19's disarmed live run recorded as a verdict JSON in the phase dir
- **Max feedback latency:** 300 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 70-01-01 | 01 | 0 | D-70-16 | T-70-07 | walker replays committed JSON per executionOrder; unhandled node types surfaced, unstubbed HTTP throws | unit | `node tests/n8n/lib/walkWorkflow.mjs --workflow n8n/wf_contact_ingest_cloud.json --rows tests/n8n/fixtures/walkerSmoke.json --node "Build Ingest Response"` | ✅ | ✅ green |
| 70-01-02 | 01 | 0 | D-70-18 | T-70-07 | walker detects F5 collapse, Merge-input hang, double-Respond first-only — this phase's RED evidence | unit | `node --test tests/n8n/walkWorkflow.test.mjs` | ✅ | ✅ green |
| 70-01-03 | 01 | 0 | D-70-03 / D-70-04 | T-70-08 | detector finds quoted form, dynamic call form and parameter-expression reads; proven non-zero against today's JSON | unit | `.venv/bin/python -m pytest tests/test_no_by_name_reads.py -q` | ✅ | ✅ green |
| 70-02-01 | 02 | 1 | D-70-05 / D-70-07 | T-70-02 | one-way contract confirmed before publication | checkpoint:decision | human (`gate="blocking-human"`) | n/a | ✅ human (recorded, 70-02-SUMMARY) |
| 70-02-02 | 02 | 1 | D-70-01 / D-70-05 / D-70-06 / D-70-07 | T-70-02, T-70-04, T-70-05 | tracer: Merge at convergence, ack-only respond, runData channel; convergence classification refuses a Merge at alternate entry points | integration (walker) + **live disarmed probe** (`gate="blocking-human"`) | `node --test tests/n8n/ingestTracerFlow.test.mjs` plus the Merge-semantics probe in its `<human-check>` | ✅ | ✅ green |
| 70-02-03 | 02 | 1 | D-70-03 / D-70-04 | T-70-13 | carry Merge across ingest HTTP hops; zero by-name reads on that lane | integration (walker) | `node --test tests/n8n/ingestCarryMerge.test.mjs` | ✅ | ✅ green |
| 70-03-01 | 03 | 2 | D-70-01 / D-70-02 | T-70-04, T-70-05 | Merge at all 17 enrichment convergence points; every input always fires; no executionOrder flip | integration (walker) | `node --test tests/n8n/enrichmentConvergenceMerge.test.mjs` | ✅ | ✅ green |
| 70-03-02 | 03 | 2 | D-70-07 | T-70-02, T-70-11 | responder has one inbound edge; four body-borne refusals become rows; retired flag gone both sides | unit + integration | `node --test tests/n8n/asyncAck.test.mjs tests/n8n/enrichmentBatchRefusal.test.mjs` | ✅ | ✅ green |
| 70-03-03 | 03 | 2 | D-70-01 / D-70-08 | T-70-12 | review lane Merges; body response preserved | integration (walker) | `node --test tests/n8n/reviewConvergenceMerge.test.mjs` | ✅ | ✅ green |
| 70-04-01 | 04 | 3 | D-70-04 | T-70-13, T-70-05 | carry Merge at every provider/HubSpot hop; research+judge bodies row-correct with providers enabled | integration (walker) | `node --test tests/n8n/providerCarryMerge.test.mjs` | ✅ | ✅ green |
| 70-04-02 | 04 | 3 | D-70-03 | T-70-08, T-70-11 | parameter expressions and single-run request reads retired; flags ride the row with semantics intact | unit | `.venv/bin/python -m pytest tests/test_no_by_name_reads.py -q` | ✅ | ✅ green |
| 70-04-03 | 04 | 3 | D-70-01 / D-70-04 | T-70-08 | run-recovery module deleted; generation raises on a by-name read — demonstrated, not assumed | unit | `node --test tests/n8n/nodeRunRecovery.test.mjs tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` | ✅ | ✅ green |
| 70-05-01 | 05 | 4 | D-70-12 | T-70-01, T-70-14, T-70-15 | canonical `write_request`; ladder deleted; emitter asserted at generation; review lane domain null | unit + integration | `node --test tests/n8n/writeGateShape.test.mjs` | ✅ | ✅ green |
| 70-05-02 | 05 | 4 | D-70-13 / D-70-14 / D-70-06 | T-70-06 | IF-shaped gate; refusals emitted; enrichment lane gains a gate; precheck removed | integration (walker) | `node --test tests/n8n/companyRecomputeLaneFlow.test.mjs tests/n8n/ingestUpdateWriteBlockedFlow.test.mjs` | ✅ | ✅ green |
| 70-05-03 | 05 | 4 | D-70-15 | T-70-01 | one verdict covers update + association; update never held for lack of a company; maintenance adopts the shape | integration (walker) | `node --test tests/n8n/companyAssociationFlow.test.mjs tests/n8n/sjPredicates.test.mjs` | ✅ | ✅ green |
| 70-06-01 | 06 | 4 | D-70-05 / D-70-08 / D-70-08a / D-70-10 | T-70-02, T-70-03, T-70-16, T-70-18 | runData sole channel incl. scale-up children; refusal before start on missing API key; no time-proximity fallback; one poll site | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_watch_settle_reporting.py operator-claude-plugin/tests/test_report_sufficiency.py -q` | ✅ | ✅ green |
| 70-06-02 | 06 | 4 | D-70-09 / D-70-11 | T-70-17 | no-write legs never appended to the ledger; preview verdict = `confidence.assess`, pinned as an equality | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_preingest_preview.py -q` | ✅ | ✅ green |
| 70-06-03 | 06 | 4 | D-70-08 | T-70-02, T-70-03 | repo scripts migrated through their one shared poster; spent probes deleted; none reads the ack for a row outcome | unit | `.venv/bin/python -m pytest tests/test_enrich_coverage_companies.py -q` | ✅ | ✅ green |
| 70-07-01 | 07 | 5 | D-70-17 | T-70-05 | 2 lanes x 2 actions per lane, every row returns once; plus single-lane and fully-refused cases | integration (walker) | `node --test tests/n8n/enrichmentMixedBatch.test.mjs tests/n8n/ingestMixedBatch.test.mjs` | ✅ | ✅ green |
| 70-07-02 | 07 | 5 | D-70-07 / D-70-11 / D-70-08a | T-70-02 | operator-facing docs state the new contract; moved pins updated; plugin version bumped with its CHANGELOG entry | unit (full suites) | `.venv/bin/python -m pytest -q --tb=short` | ✅ | ✅ green |
| 70-07-03 | 07 | 5 | D-70-19 / D-70-02 | T-70-19, T-70-03, T-70-04, T-70-20 | disarmed live run; runData shape-equal to walker prediction; live `settings.executionOrder` logged; zero writes | live (disarmed, `gate="blocking-human"`) | `scripts/prove_phase70_runtime.py` → `70-RUNTIME-VERDICT.json` | ✅ | ✅ live PASS — Gate 11 (12354-12358), `execution_order_all_v1: true`, `shapes_equal: true`, 0 writes; re-run under v1 after the legacy-order Gate 3/8 runs |
| 70-08-01 | 08 | R1-0 | D-70-21 | — | pre-Phase-70 `59812be` rollback bundle pinned by test; `n8n/` untouched | unit | `.venv/bin/python -m pytest tests/test_phase70_rollback_bundle.py -q` | ✅ | ✅ green |
| 70-08-02 | 08 | R1-0 | D-70-21 | — | rollback dry-run output + runbook committed | artifact | `test -s 70-ROLLBACK-DRYRUN.txt && test -s 70-ROLLBACK-RUNBOOK.md` | ✅ | ✅ green |
| 70-08-03 | 08 | R1-0 | D-70-21 | — | Gate 4 recorded and deferred (back-load ruling) | checkpoint:human-verify | `grep "Gate 4" 70-DEFERRED-GATES.md` | ✅ | ✅ recorded — rollback never exercised; live went forward to v1 (Gate 10) |
| 70-09-01 | 09 | R1-1 | D-70-20 / D-70-19 / D-70-18 | — | walker fidelity RED first against frozen 12203/12206 | unit (tdd) | `node --test tests/n8n/walkerEngineFidelity.test.mjs` | ✅ | ✅ green (RED seen 70-09-SUMMARY) |
| 70-09-02 | 09 | R1-1 | D-70-20 / D-70-19 | — | walker delivers zero-item waves; graph untouched | unit (tdd) | `node --test tests/n8n/walkerEngineFidelity.test.mjs tests/n8n/walkWorkflow.test.mjs` | ✅ | ✅ green |
| 70-09-03 | 09 | R1-1 | D-70-18 | — | every suite result matches `70-WALKER-RED-INVENTORY.md` | unit | `node --test tests/n8n/*.test.mjs` vs inventory | ✅ | ✅ green |
| 70-10-01 | 10 | R1-2 | D-70-23 | — | gated-sentinel decision recorded in CONTEXT | checkpoint:decision | `grep "D-70-23" 70-CONTEXT.md` | ✅ | ✅ recorded |
| 70-10-02 | 10 | R1-2 | D-70-20 / D-70-19 / D-70-01 / D-70-14 / D-70-15 | — | ingest gated sentinels; regenerate is idempotent | integration (walker, tdd) | `node --test tests/n8n/writeGateShape.test.mjs tests/n8n/ingestMixedBatch.test.mjs tests/n8n/ingestCarryMerge.test.mjs tests/n8n/companyAssociationFlow.test.mjs tests/n8n/pairPipelineAssociationFlow.test.mjs tests/n8n/ingestTracerFlow.test.mjs` | ✅ | ✅ green |
| 70-10-03 | 10 | R1-2 | D-70-20 | — | Merge-input contract asserted at generation | unit (tdd) | `node --test tests/n8n/mergeInputContract.test.mjs` | ✅ | ✅ green |
| 70-11-01 | 11 | R1-3 | D-70-20 / D-70-19 / D-70-01 / D-70-14 | — | enrichment gated sentinels; 15-input Merge split into 3 stage Merges ≤10 | integration (walker, tdd) | `node --test tests/n8n/enrichmentMixedBatch.test.mjs tests/n8n/enrichmentConvergenceMerge.test.mjs tests/n8n/enrichmentBatchRefusal.test.mjs tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs tests/n8n/companyRecomputeLaneFlow.test.mjs tests/n8n/bareEventChainFlow.test.mjs tests/n8n/linkedinLaneFlow.test.mjs` | ✅ | ✅ green — `scaleUpFanOutFlow.test.mjs` from the plan's list was DELETED with the lane (70-13, D-70-24); `scaleUpRefused.test.mjs` replaces it |
| 70-11-02 | 11 | R1-3 | D-70-01 / D-70-14 | — | review lane gated sentinels + contract | integration (walker, tdd) | `node --test tests/n8n/mergeInputContract.test.mjs tests/n8n/reviewConvergenceMerge.test.mjs tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/reviewAllowlistRefusal.test.mjs` | ✅ | ✅ green |
| 70-11-03 | 11 | R1-3 | D-70-19 | — | full suites green on regenerated JSON | unit (full suites) | node + root pytest + plugin pytest | ✅ | ✅ green |
| 70-12-01 | 12 | R1-4 | D-70-22 / D-70-19 | — | proof driver refuses before start, records verdict fields | unit (tdd) | `.venv/bin/python -m pytest tests/test_prove_phase70_runtime.py -q` | ✅ | ✅ green |
| 70-12-02 | 12 | R1-4 | D-70-21 / D-70-02 | — | deploy dry-run of gap-closure JSON | inline check | python inline (plan 70-12 Task 2) | ✅ | ✅ green (70-12-SUMMARY) |
| 70-12-03 | 12 | R1-4 | D-70-19 / D-70-02 | — | Gates 5/6 recorded and deferred | checkpoint:human-verify | `grep "Gate 5\|Gate 6" 70-DEFERRED-GATES.md` | ✅ | ✅ recorded — superseded by Gates 10/11/12, all PASS (70-UAT.md) |
| 70-13-01 | 13 | R2-1 | D-70-24 | — | zero `executeWorkflow` in enrichment, exactly 1 in maintenance; `assert_no_self_dispatch` | integration (tdd) | `grep -c executeWorkflow n8n/wf_enrichment_cloud.json` = 0 and maintenance = 1 | ✅ | ✅ green |
| 70-13-02 | 13 | R2-1 | D-70-26 | — | sub-workflow ref rebinding pinned | unit (tdd) | `.venv/bin/python -m pytest tests/test_subworkflow_ref_rebinding.py -q` | ✅ | ✅ green |
| 70-13-03 | 13 | R2-1 | D-70-24 | — | plugin has no `scale_up` parameter; legacy kwarg ignored | unit (tdd) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_scale_up_retired.py -q` | ✅ | ✅ green |
| 70-14-01 | 14 | R2-2 | D-70-25 | — | `_gsd_sentinel_marker` rows never reach the wire | unit (tdd) | `node --test tests/n8n/buildResponseMarkerFilter.test.mjs` | ✅ | ✅ green |
| 70-14-02 | 14 | R2-2 | D-70-26 | — | 12316 pinned as a divergence the walker does NOT reproduce; walker untouched since 70-13 | unit | `node --test tests/n8n/walkerEngineFidelity.test.mjs` | ✅ | ✅ green |
| 70-15-01 | 15 | R2-3 | D-70-27 | — | CLAUDE.md carries 12316/12348 `[observed live]` rows | docs check | `grep 12316 CLAUDE.md && grep 12348 CLAUDE.md` | ✅ | ✅ green |
| 70-15-02 | 15 | R2-3 | D-70-27 | — | runbook: deactivate-first stop, burst watch | docs check | `grep deactivate 70-ROLLBACK-RUNBOOK.md` | ✅ | ✅ green |
| 70-15-03 | 15 | R2-3 | D-70-24 / D-70-27 | — | Gates 7/8/9 recorded | docs check | `grep "^## Gate [789]" 70-DEFERRED-GATES.md` | ✅ | ✅ green |
| 70-16-01 | 16 | R3-1 | D-70-28 | — | executionOrder v1 RED first on every generated body | unit (tdd) | `node --test tests/n8n/executionOrderV1.test.mjs` | ✅ | ✅ green (RED seen 70-16-SUMMARY) |
| 70-16-02 | 16 | R3-1 | D-70-28 | — | one generator constant; regenerate flips settings only, node counts unchanged | unit | `.venv/bin/python scripts/build_cloud_workflows.py && node --test tests/n8n/executionOrderV1.test.mjs` | ✅ | ✅ green |
| 70-16-03 | 16 | R3-1 | D-70-30 | — | walker refuses non-v1 except `allowLegacy` (one caller); full suites green | unit (full suites) | `node --test tests/n8n/*.test.mjs && pytest root && pytest plugin` | ✅ | ✅ green |
| 70-17-01 | 17 | R3-2 | D-70-29 | — | deploy PUT/POST and plugin arming PUT preserve `executionOrder: v1` | unit | `.venv/bin/python -m pytest tests/test_deploy_n8n_workflows.py operator-claude-plugin/tests/test_control_allowlist_diff.py -q` | ✅ | ✅ green |
| 70-17-02 | 17 | R3-2 | D-70-29 | — | bounce read-back fails loudly on a legacy-order live body | unit | `.venv/bin/python -m pytest tests/test_bounce_n8n_workflows.py -q` | ✅ | ✅ green |
| 70-17-03 | 17 | R3-2 | D-70-29 | — | proof driver `execution_order_all_v1` verdict field; null = failure | unit | `.venv/bin/python -m pytest tests/test_prove_phase70_runtime.py -q` | ✅ | ✅ green |
| 70-18-01 | 18 | R3-3 | D-70-31 | — | CLAUDE.md §13.0.3 legacy rows tagged, Gate 8 row added | docs check | `grep -c "addEmptyItem" CLAUDE.md` | ✅ | ✅ green |
| 70-18-02 | 18 | R3-3 | D-70-31 | — | Gates 10/11/12 written | docs check | `grep "^## Gate 1[012]" 70-DEFERRED-GATES.md` | ✅ | ✅ green — all three PASS live 2026-09-10 |
| 70-18-03 | 18 | R3-3 | D-70-31 | — | ROADMAP/UAT carry round 3 | docs check | `grep "D-70-28" .planning/ROADMAP.md` | ✅ | ✅ green |
| 70-post-01 | follow-on | — | D-70-31 (Gate 11 follow-on) | — | five Gate 11 v1 recordings frozen; Merge-fires-twice and zero-item-output-not-a-delivery pinned | unit (reader) | `node --test tests/n8n/v1RuntimeRecordings.test.mjs` | ✅ | ✅ green (added 2026-09-11, commit `92751ef`) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is plan **70-01**. It lands the instrument and the detector; the acceptance tests are
built on that instrument in 70-07 against the finished JSON.

- [x] `tests/n8n/lib/walkWorkflow.mjs` + `tests/n8n/walkWorkflow.test.mjs` — the D-70-16 graph walker and its own unit tests (F5 collapse, Respond-fires-once, Merge input never fires, always-output-data satisfies a Merge, paired-item resolution, synthetic 2x2 mixed batch)
- [x] `detect_by_name_reads` in `scripts/build_cloud_workflows.py` and `tests/test_no_by_name_reads.py`, proven by a non-zero count against today's committed JSON (D-70-03/04; covers the quoted form, the dynamic call form, node `parameters` expressions, and an inlined run-recovery module — research Pitfall 2)
- [x] `tests/n8n/fixtures/walkerSmoke.json` — the two-row ingest fixture the walker CLI consumes

**Deliberate deviation, recorded:** the two D-70-17 mixed-batch acceptance tests are NOT stubbed in
Wave 0. They assert behaviour that does not exist until 70-05 completes, and D-70-18 explicitly
permits GREEN-on-the-refactored-JSON with no historical RED. Wave 0 de-risks them instead by
proving the walker they run on, including a synthetic 2x2 mixed-batch case. The real ones land in
70-07 Task 1.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Outcome |
|----------|-------------|------------|-------------------|---------|
| **EARLY probe (70-02 T2, `gate="blocking-human"`): does a Merge with an un-fired input settle, and which `alwaysOutputData` placement satisfies it?** | D-70-01 / D-70-02 | The walker models only what it is told; no committed workflow has ever contained a native Merge. This is the architectural dead-end check and must run BEFORE 70-03 rewrites 123 nodes | operator deploys + bounces the ingest workflow disarmed; ONE single-lane send (association rows only, review path empty); report settled-vs-stuck, the working flag placement, live `settings.executionOrder`, and zero writes. A stuck execution stops the phase as a finding | **DONE** 2026-09-10: executions `12200`/`12202` (Gate 1, disarmed, legacy order) — settled, `alwaysOutputData` placement established, G-70-1 multipart defect found and fixed `576fe7c` |
| Closing run: the finished graph behaves as the walker predicts | D-70-01 / D-70-02 / D-70-19 | confirms on the finished graph what the early probe established on the tracer | operator deploys + bounces disarmed; one disarmed 2-lane × 2-action send per lane AND one single-lane send; execution settles (not stuck `running`); runData rows shape-equal to walker prediction; log `settings.executionOrder` from the live body | **DONE** — first under legacy order (Gate 3, `12203`-`12208`: settled but rows dropped, G-70-2/3), again after gap closure (Gate 8, `12349`-`12353`: FAIL, legacy `addEmptyItem` push), finally under v1 (Gate 11, `12354`-`12358`: PASS, `shapes_equal: true`, 0 writes) and armed (Gate 12, `12363`: PASS). Recordings frozen at `tests/n8n/fixtures/frozen/exec_1235{4..8}.runData.json` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (deviation for the two acceptance tests recorded above)
- [x] No watch-mode flags
- [x] Feedback latency < 300s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner sign-off 2026-09-09 — every task carries an `<automated>` verify with a
stated failing direction except the two checkpoints (70-02-01 `checkpoint:decision`, 70-07-03
`checkpoint:human-verify`, both `gate="blocking-human"`), which are human by design. No three
consecutive tasks lack an automated verify. No watch-mode flags. Feedback latency under 300s for
the per-task commands.

---

## Validation Audit 2026-09-11

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

Audit scope: the 21 planning-time rows (plans 70-01..70-07) plus the 33 gap-closure tasks
(plans 70-08..70-18, rounds 1-3) and the Gate 11 follow-on. Every automated command's test file
exists and is green as of commit `bf10c7e`: `node --test tests/n8n/*.test.mjs` 1082/1082; targeted
root pytest (7 files) 155/155; targeted plugin pytest (6 files) 165/165. Every `blocking-human`
gate the plans deferred was run at end-of-phase UAT (`70-UAT.md`, 12/12) — Gates 10/11/12 PASS
live, Gates 4-9 superseded with evidence kept. One planned test file, `scaleUpFanOutFlow.test.mjs`,
no longer exists: the lane it tested was deleted by D-70-24 and `scaleUpRefused.test.mjs` pins the
refusal that replaced it — a retirement, not a gap. No auditor spawned; nothing to fill.

Open, deliberately NOT a Nyquist gap: the walker's D-70-30 rule (c) is now known to model the
legacy engine, not v1 (`.planning/todos/pending/2026-09-11-walker-rule-c-zero-item-output-not-a-delivery-under-v1.md`).
The observation is pinned by `tests/n8n/v1RuntimeRecordings.test.mjs`; the modelling change is
a later gap-closure task with its own fidelity case, not a missing test for any phase 70
requirement.
