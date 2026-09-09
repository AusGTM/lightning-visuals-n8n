---
phase: "70"
slug: "one-merge-one-result-channel-n8n-runtime-truth"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 70-01-01 | 01 | 0 | D-70-16 / D-70-18 | — | walker replays committed JSON per executionOrder; detects F5 collapse and double-Respond | unit | `node --test tests/n8n/<walker>.test.mjs` | ❌ W0 | ⬜ pending |
| 70-01-02 | 01 | 0 | D-70-03 / D-70-04 | — | build-time assertion: zero by-name reads in generated jsCode AND node parameter expressions; `nodeRunRecovery.js` not inlined | unit | `.venv/bin/python -m pytest tests/test_no_by_name_reads.py -q` (or equivalent) | ❌ W0 | ⬜ pending |
| 70-02-xx | 02 | 1 | D-70-01 / D-70-02 | — | Merge at every convergence; every Merge input always fires (Always Output Data or sentinel row); single-lane batch does not hang | integration (walker) | `node --test tests/n8n/<enrichmentMixedBatch>.test.mjs` | ❌ W0 | ⬜ pending |
| 70-03-xx | 03 | 1 | D-70-12..15 | T-70-01 | canonical `write_request`; gate emits refusal item; review lane `domain: null`; no allowlist widening | unit | `node --test tests/n8n/<writeGateShape>.test.mjs`; `.venv/bin/python -m pytest tests/test_write_gate_coverage.py -q` | extend | ⬜ pending |
| 70-04-xx | 04 | 2 | D-70-05..08a / D-70-10 | T-70-02 | runData sole channel; ack-only body; refusal before start on missing `n8n_api_key`; no time-proximity fallback | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_watch.py operator-claude-plugin/tests/test_report_sufficiency.py -q` | ✅ extend | ⬜ pending |
| 70-04-xx | 04 | 2 | D-70-09 / D-70-11 | — | no-write legs never appended to `written_records`; preview verdict = `confidence.assess` | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_preingest.py -q` | ✅ extend | ⬜ pending |
| 70-05-xx | 05 | 3 | D-70-17 | — | 2 lanes × 2 actions per lane, every row returns once from the write node | integration (walker) | `node --test tests/n8n/<enrichmentMixedBatch>.test.mjs tests/n8n/<ingestMixedBatch>.test.mjs` | ❌ W0 | ⬜ pending |
| 70-05-xx | 05 | 3 | D-70-19 | — | disarmed live run; runData shape-equal to walker prediction; `settings.executionOrder` logged | live (disarmed) | adapted `scripts/prove_async_recovery.py`; verdict JSON in phase dir | ✅ precedent | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

(Task IDs are placeholders until PLAN.md files exist; the planner replaces them.)

---

## Wave 0 Requirements

- [ ] `tests/n8n/<walker>.mjs` + `<walker>.test.mjs` — the D-70-16 graph walker and its own unit tests (F5 collapse, Respond-fires-once, Webhook `responseData`, single-lane-only batch)
- [ ] build-time by-name-read assertion in `scripts/build_cloud_workflows.py` and its pytest (D-70-03/04; covers `$('`, dynamic `$(name)`, and node `parameters` expressions — research Pitfall 2)
- [ ] `tests/n8n/<enrichmentMixedBatch>.test.mjs`, `tests/n8n/<ingestMixedBatch>.test.mjs` — D-70-17 acceptance tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Merge + Always Output Data does not hang on this n8n Cloud build | D-70-01 / D-70-02 / D-70-19 | platform behaviour is `[documented]` only until observed | operator deploys + bounces disarmed; one disarmed 2-lane × 2-action send per lane AND one single-lane send; execution settles (not stuck `running`); runData rows shape-equal to walker prediction; log `settings.executionOrder` from the live body |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 300s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
