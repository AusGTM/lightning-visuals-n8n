---
phase: 40
slug: scoring-engine-remediation-notes
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-06
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (`.venv/bin/python -m pytest`) + node:test (`node --test tests/n8n/*.test.mjs`) |
| **Config file** | none — existing conventions |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_icp_scoring.py tests/test_cloud_companies_branch.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && for f in tests/n8n/*.test.mjs; do node --test "$f"; done` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01 T1 | 01 | 1 | ENGINE-06 | T-40-02 | No token in archived JSON; portal guard before any GET | unit (offline, glob-driven) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ❌ created by this task | ⬜ pending |
| 40-01 T2 (tracer) | 01 | 1 | ENGINE-05, ENGINE-06 | T-40-01, T-40-03, T-40-04 | Disposable-only writes; snapshot-before-PUT; paired re-enable | unit + live disposable | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ (T1) | ⬜ pending |
| 40-02 T1 | 02 | 1 | PARITY-01 | T-40-01 | Teardown in `finally`; portal guard | unit (offline oracle vs config) | `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` | ❌ created by this task | ⬜ pending |
| 40-02 T2 | 02 | 1 | PARITY-02 | T-40-05, T-40-07 | Live cases gated by `RUN_LIVE_PARITY`; cost-bearing veto cases off the scheduled tier | collection guard (offline) + live | `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` | ✅ (T1) | ⬜ pending |
| 40-02 T3 | 02 | 1 | PARITY-01 | T-40-05, T-40-06 | Zero-assertion run exits non-zero; wrapper imports no write helper | unit (offline guard test) | `.venv/bin/python -m pytest tests/test_scoring_parity.py -q` | ✅ (T1) | ⬜ pending |
| 40-03 T1 | 03 | 1 | VETO-01 | T-40-08 | `min_confidence` 80 on veto policy entries, test-locked | unit | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py -q` | ✅ | ⬜ pending |
| 40-03 T2 | 03 | 1 | VETO-01, VETO-02 | T-40-09, T-40-10 | String literal flag write; reason strings asserted equal to rubric | unit (build-artifact assertions) | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py tests/test_enabled_build_invariants.py -q` | ✅ | ⬜ pending |
| 40-03 T3 (checkpoint) | 03 | 1 | VETO-02 | T-40-11, T-40-12 | Disarmed deploy verified; operator arms; bounce required | manual (blocking human-verify) | disarmed `scripts/deploy_n8n_workflows.py` run + operator arm | n/a | ⬜ pending |
| 40-04 T1 | 04 | 2 | ENGINE-02, ENGINE-05 | T-40-01 | Disposable-only default-stamp check | unit | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |
| 40-04 T2 | 04 | 2 | ENGINE-02, ENGINE-05 | T-40-14, T-40-15 | Flows created disabled; gambling flow writes only its own component | unit + live disposable | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |
| 40-04 T3 | 04 | 2 | ENGINE-02 | T-40-13 | Property snapshot before formula PATCH; portal-UI fallback pre-committed | unit + live disposable | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |
| 40-05 T1 | 05 | 3 | ENGINE-03 | T-40-03, T-40-16, T-40-11 | Exact-match enum branches (no spelling variants); veto branch deleted only after 40-03 is live | unit + live (`f4_au_string`) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |
| 40-05 T2 | 05 | 3 | ENGINE-03, ENGINE-04 | T-40-03, T-40-04 | Nine-key band table asserted complete; boundary contract asserted offline | unit + live (`revenue_boundary`, `f10`) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py tests/test_icp_scoring.py -q` | ✅ | ⬜ pending |
| 40-05 T3 (checkpoint) | 05 | 3 | ENGINE-03 | T-40-17 | Stale-flag population measured and recorded; operator confirms D-02 path | manual (blocking human-verify) | portal review + one real-record refresh | n/a | ⬜ pending |
| 40-06 T1 | 06 | 4 | ENGINE-07 | T-40-18 | Enum option proven writable on a disposable before the flow writes it | unit + live disposable | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |
| 40-06 T2 | 06 | 4 | ENGINE-07, VETO-03 | T-40-03, T-40-19, T-40-04 | Veto compared as string; ladder PUT as full body; paired re-enable | unit + live (`f8_sub15`, `tier_on_flag_change`) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |
| 40-06 T3 | 06 | 4 | ENGINE-07, VETO-03 | T-40-20 | D reachable only via a veto-guarded branch, test-locked | unit | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py tests/test_scoring_parity.py -q` | ✅ | ⬜ pending |
| 40-07 T1 | 07 | 5 | PARITY-01 | T-40-02 | `dry_run=True` default; no token in output; over-100 batch rejected | unit | `.venv/bin/python -m pytest tests/test_backfill_seed_company_scores.py -q` | ❌ created by this task | ⬜ pending |
| 40-07 T2 | 07 | 5 | ENGINE-01 | T-40-21, T-40-22, T-40-23 | Sample cap enforced in code; derived fields never written; single point table | unit + live capped sample | `.venv/bin/python -m pytest tests/test_backfill_seed_company_scores.py -q` | ✅ (T1) | ⬜ pending |
| 40-07 T3 | 07 | 5 | ENGINE-01, PARITY-01 | T-40-05 | Committed verdict carries a non-zero executed-assertion count | live full sweep + committed report | `.venv/bin/python -m pytest tests/test_scoring_parity.py tests/test_flow_rubric_conformance.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 1 carries all three scaffolds; nothing in waves 2 to 5 lacks an existing test file.

- [ ] `tests/test_flow_rubric_conformance.py` — 40-01 Task 1. Glob-driven over `config/hubspot_flows/*.after.json`; the offline verify for every flow edit in waves 1 to 4.
- [ ] `tests/scoring_fixtures.py` + `tests/test_scoring_parity.py` — 40-02 Tasks 1 to 3. PARITY-01/02, the live selectors later plans use as their verify.
- [ ] `tests/test_backfill_seed_company_scores.py` — 40-07 Task 1 (created in the same task that needs it; the batch helper has no earlier consumer).

Decision recorded (40-RESEARCH.md A3): live gating uses an env-var `skipif` on `RUN_LIVE_PARITY`,
not a registered pytest marker. This repo has no pytest config and every existing gated script is
env-var gated; adding a marker would mean adding config for no ergonomic gain.

*Existing infrastructure (pytest + node:test) covers unit-level phase requirements; live HubSpot assertions gated behind env-var skipif.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live flow behavior after PUT (disposable-company chain fire) | ENGINE-01..07, VETO-01..03 | Requires live portal + timing waits | Disposable-company create/exercise/delete probes; see plan tasks |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — 18 of 20 tasks carry `<automated>`; the two exceptions are `checkpoint:human-verify` tasks (40-03 T3, 40-05 T3), which are exempt
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — the longest run without one is 1
- [x] Wave 0 covers all MISSING references — all three scaffolds land in the task that first needs them
- [x] No watch-mode flags — every command is a single-shot `pytest -q` or `node --test`
- [x] Feedback latency < 90s — offline suite is ~60s; live disposable assertions are gated behind `RUN_LIVE_PARITY` and excluded from the per-commit loop
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner, 2026-08-06
