---
phase: "70"
slug: "one-merge-one-result-channel-n8n-runtime-truth"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: true) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: false  # 70-01 lands it
created: "2026-09-09"
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
| 70-01-01 | 01 | 0 | D-70-16 | T-70-07 | walker replays committed JSON per executionOrder; unhandled node types surfaced, unstubbed HTTP throws | unit | `node tests/n8n/lib/walkWorkflow.mjs --workflow n8n/wf_contact_ingest_cloud.json --rows tests/n8n/fixtures/walkerSmoke.json --node "Build Ingest Response"` | ❌ W0 | ⬜ pending |
| 70-01-02 | 01 | 0 | D-70-18 | T-70-07 | walker detects F5 collapse, Merge-input hang, double-Respond first-only — this phase's RED evidence | unit | `node --test tests/n8n/walkWorkflow.test.mjs` | ❌ W0 | ⬜ pending |
| 70-01-03 | 01 | 0 | D-70-03 / D-70-04 | T-70-08 | detector finds quoted form, dynamic call form and parameter-expression reads; proven non-zero against today's JSON | unit | `.venv/bin/python -m pytest tests/test_no_by_name_reads.py -q` | ❌ W0 | ⬜ pending |
| 70-02-01 | 02 | 1 | D-70-05 / D-70-07 | T-70-02 | one-way contract confirmed before publication | checkpoint:decision | human (`gate="blocking-human"`) | n/a | ⬜ pending |
| 70-02-02 | 02 | 1 | D-70-01 / D-70-05 / D-70-06 / D-70-07 | T-70-02, T-70-04, T-70-05 | tracer: Merge at convergence, ack-only respond, runData channel, always-output-data on lane terminals | integration (walker) | `node --test tests/n8n/ingestTracerFlow.test.mjs` | ❌ W0 | ⬜ pending |
| 70-02-03 | 02 | 1 | D-70-03 / D-70-04 | T-70-13 | carry Merge across ingest HTTP hops; zero by-name reads on that lane | integration (walker) | `node --test tests/n8n/ingestCarryMerge.test.mjs` | ❌ W0 | ⬜ pending |
| 70-03-01 | 03 | 2 | D-70-01 / D-70-02 | T-70-04, T-70-05 | Merge at all 17 enrichment convergence points; every input always fires; no executionOrder flip | integration (walker) | `node --test tests/n8n/enrichmentConvergenceMerge.test.mjs` | ❌ W0 | ⬜ pending |
| 70-03-02 | 03 | 2 | D-70-07 | T-70-02, T-70-11 | responder has one inbound edge; four body-borne refusals become rows; retired flag gone both sides | unit + integration | `node --test tests/n8n/asyncAck.test.mjs tests/n8n/enrichmentBatchRefusal.test.mjs` | ✅ extend | ⬜ pending |
| 70-03-03 | 03 | 2 | D-70-01 / D-70-08 | T-70-12 | review lane Merges; body response preserved | integration (walker) | `node --test tests/n8n/reviewConvergenceMerge.test.mjs` | ❌ W0 | ⬜ pending |
| 70-04-01 | 04 | 3 | D-70-04 | T-70-13, T-70-05 | carry Merge at every provider/HubSpot hop; research+judge bodies row-correct with providers enabled | integration (walker) | `node --test tests/n8n/providerCarryMerge.test.mjs` | ❌ W0 | ⬜ pending |
| 70-04-02 | 04 | 3 | D-70-03 | T-70-08, T-70-11 | parameter expressions and single-run request reads retired; flags ride the row with semantics intact | unit | `.venv/bin/python -m pytest tests/test_no_by_name_reads.py -q` | ✅ extend | ⬜ pending |
| 70-04-03 | 04 | 3 | D-70-01 / D-70-04 | T-70-08 | run-recovery module deleted; generation raises on a by-name read — demonstrated, not assumed | unit | `node --test tests/n8n/nodeRunRecovery.test.mjs tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` | ✅ rewrite | ⬜ pending |
| 70-05-01 | 05 | 4 | D-70-12 | T-70-01, T-70-14, T-70-15 | canonical `write_request`; ladder deleted; emitter asserted at generation; review lane domain null | unit + integration | `node --test tests/n8n/writeGateShape.test.mjs` | ❌ W0 | ⬜ pending |
| 70-05-02 | 05 | 4 | D-70-13 / D-70-14 / D-70-06 | T-70-06 | IF-shaped gate; refusals emitted; enrichment lane gains a gate; precheck removed | integration (walker) | `node --test tests/n8n/companyRecomputeLaneFlow.test.mjs tests/n8n/ingestUpdateWriteBlockedFlow.test.mjs` | ✅ rewrite | ⬜ pending |
| 70-05-03 | 05 | 4 | D-70-15 | T-70-01 | one verdict covers update + association; update never held for lack of a company; maintenance adopts the shape | integration (walker) | `node --test tests/n8n/companyAssociationFlow.test.mjs tests/n8n/sjPredicates.test.mjs` | ✅ rewrite | ⬜ pending |
| 70-06-01 | 06 | 4 | D-70-05 / D-70-08 / D-70-08a / D-70-10 | T-70-02, T-70-03, T-70-16, T-70-18 | runData sole channel incl. scale-up children; refusal before start on missing API key; no time-proximity fallback; one poll site | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_watch_settle_reporting.py operator-claude-plugin/tests/test_report_sufficiency.py -q` | ✅ extend | ⬜ pending |
| 70-06-02 | 06 | 4 | D-70-09 / D-70-11 | T-70-17 | no-write legs never appended to the ledger; preview verdict = `confidence.assess`, pinned as an equality | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_preingest_preview.py -q` | ✅ extend | ⬜ pending |
| 70-06-03 | 06 | 4 | D-70-08 | T-70-02, T-70-03 | repo scripts migrated through their one shared poster; spent probes deleted; none reads the ack for a row outcome | unit | `.venv/bin/python -m pytest tests/test_enrich_coverage_companies.py -q` | ✅ extend | ⬜ pending |
| 70-07-01 | 07 | 5 | D-70-17 | T-70-05 | 2 lanes x 2 actions per lane, every row returns once; plus single-lane and fully-refused cases | integration (walker) | `node --test tests/n8n/enrichmentMixedBatch.test.mjs tests/n8n/ingestMixedBatch.test.mjs` | ❌ W0 | ⬜ pending |
| 70-07-02 | 07 | 5 | D-70-07 / D-70-11 / D-70-08a | T-70-02 | operator-facing docs state the new contract; moved pins updated; plugin version bumped with its CHANGELOG entry | unit (full suites) | `.venv/bin/python -m pytest -q --tb=short` | ✅ existing | ⬜ pending |
| 70-07-03 | 07 | 5 | D-70-19 / D-70-02 | T-70-19, T-70-03, T-70-04, T-70-20 | disarmed live run; runData shape-equal to walker prediction; live `settings.executionOrder` logged; zero writes | live (disarmed, `gate="blocking-human"`) | `scripts/prove_phase70_runtime.py` → `70-RUNTIME-VERDICT.json` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is plan **70-01**. It lands the instrument and the detector; the acceptance tests are
built on that instrument in 70-07 against the finished JSON.

- [ ] `tests/n8n/lib/walkWorkflow.mjs` + `tests/n8n/walkWorkflow.test.mjs` — the D-70-16 graph walker and its own unit tests (F5 collapse, Respond-fires-once, Merge input never fires, always-output-data satisfies a Merge, paired-item resolution, synthetic 2x2 mixed batch)
- [ ] `detect_by_name_reads` in `scripts/build_cloud_workflows.py` and `tests/test_no_by_name_reads.py`, proven by a non-zero count against today's committed JSON (D-70-03/04; covers the quoted form, the dynamic call form, node `parameters` expressions, and an inlined run-recovery module — research Pitfall 2)
- [ ] `tests/n8n/fixtures/walkerSmoke.json` — the two-row ingest fixture the walker CLI consumes

**Deliberate deviation, recorded:** the two D-70-17 mixed-batch acceptance tests are NOT stubbed in
Wave 0. They assert behaviour that does not exist until 70-05 completes, and D-70-18 explicitly
permits GREEN-on-the-refactored-JSON with no historical RED. Wave 0 de-risks them instead by
proving the walker they run on, including a synthetic 2x2 mixed-batch case. The real ones land in
70-07 Task 1.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Merge + Always Output Data does not hang on this n8n Cloud build | D-70-01 / D-70-02 / D-70-19 | platform behaviour is `[documented]` only until observed | operator deploys + bounces disarmed; one disarmed 2-lane × 2-action send per lane AND one single-lane send; execution settles (not stuck `running`); runData rows shape-equal to walker prediction; log `settings.executionOrder` from the live body |

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
