---
phase: "73"
slug: "ga-fix-list-from-stress-attempt-2"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true  # 73-01 T1 (frozen fixtures), 73-02 (throttle shape), 73-04 (first-wins), 73-06 T2 (walker 2nd HTTP output) all landed
created: "2026-09-15"
validated: "2026-09-18"
---

# Phase 73 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (root + operator-claude-plugin/) + node:test (tests/n8n) |
| **Config file** | none dedicated (`.venv/bin/python -m pytest`, `node --test` glob form) |
| **Quick run command** | per-task `<automated>` command (see map) |
| **Full suite command** | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/ && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~73 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's own `<automated>` command
- **After every plan wave:** Run the full suite command above (baseline 4952/154 py, 1170/0 node)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 240 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 73-01-01 | 01 | 1 | F-B5 | see plan `<threat_model>` | N/A | tracer | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_r…` | ✅ | ✅ green |
| 73-01-02 | 01 | 1 | F-B5 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_r…` | ✅ | ✅ green |
| 73-01-03 | 01 | 1 | F-B5 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_m…` | ✅ | ✅ green |
| 73-02-01 | 02 | 2 | F-E1, F-A3r | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/reviewLoop.test.mjs tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/hubspo…` | ✅ | ✅ green |
| 73-02-02 | 02 | 2 | F-E1, F-A3r | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/ingestSearchThrottle.test.mjs tests/n8n/ingestCarryMerge.test.mjs` | ✅ | ✅ green |
| 73-03-01 | 03 | 3 | F-B7, F-B4, F-B3 | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/companyDomainVariants.test.mjs tests/n8n/companyAssociationFlow.test.mjs tests…` | ✅ | ✅ green |
| 73-03-02 | 03 | 3 | F-B7, F-B4, F-B3 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/companyNameOnlyOutcome.test.mjs tests/n8n/companyNameFallbackFlow.test.mjs tes…` | ✅ | ✅ green |
| 73-03-03 | 03 | 3 | F-B7, F-B4, F-B3 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/companyFreemailRefusal.test.mjs tests/n8n/companyLink.test.mjs` | ✅ | ✅ green |
| 73-04-01 | 04 | 4 | F-A5 | see plan `<threat_model>` | N/A | tracer | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_d…` | ✅ | ✅ green |
| 73-04-02 | 04 | 4 | F-A5 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_d…` | ✅ | ✅ green |
| 73-05-01 | 05 | 5 | F-B6, F-A1, F-A2, F-B1 | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/backendStatusCredits.test.mjs tests/n8n/backendStatus.test.mjs tests/n8n/backe…` | ✅ | ✅ green |
| 73-05-02 | 05 | 5 | F-B6, F-A1, F-A2, F-B1 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_write…` | ✅ | ✅ green |
| 73-06-01 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/pairCreateOutcome.test.mjs tests/n8n/ingestCarryMerge.test.mjs tests/n8n/compa…` | ✅ | ✅ green |
| 73-06-02 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/walkerHttpErrorOutput.test.mjs tests/n8n/walkerEngineFidelityV1.test.mjs tests…` | ✅ | ✅ green |
| 73-06-03 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/ingestCreateErrorLane.test.mjs tests/n8n/ingestCarryMerge.test.mjs tests/n8n/i…` | ✅ | ✅ green |
| 73-06-04 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/*.test.mjs 2>&1 \| tail -5 && .venv/bin/python -m pytest -q --tb=short -p no:ca…` | ✅ | ✅ green |
| 73-07-01 | 07 | 7 | F-A6, F-A5, F-E1, F-B7, F-B3, F-A3r | see plan `<threat_model>` | N/A | auto | `.venv/bin/python scripts/build_cloud_workflows.py && .venv/bin/python -c "import subprocess,sys; out…` | ✅ | ✅ green |
| 73-07-02 | 07 | 7 | F-A6, F-A5, F-E1, F-B7, F-B3, F-A3r | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_plugi…` | ✅ | ✅ green |
| 73-07-03 | 07 | 7 | F-A6, F-A5, F-E1, F-B7, F-B3, F-A3r | see plan `<threat_model>` | N/A | manual (operator gate) | operator gate — `73-UAT.md` attempt 3 Stages A–F | — | ✅ done (operator, 2026-09-17/18) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/n8n/lib/walkWorkflow.mjs` second HTTP output (73-06 Task 2, RED-first)
- [x] frozen redacted runData fixture for exec 12434/12449 (73-01 Task 1, RED-first)
- [x] batchInterval=400 shape test (73-02), first-wins dedupe test (73-04)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Outcome |
|----------|-------------|------------|-------------------|---------|
| deploy + bounce disarmed, reset, stress attempt 3 A–F | 73-07 gate (D-73-18) | operator-only; never armed from Claude | RUNBOOK.md "Restart procedure" | **DONE** 2026-09-17/18 — `73-UAT.md` attempt 3: Stages A–F run, A+E PASS (attempt 2's failures), close-out DISARMED PASS at node counts 30/80/287/55/43, reset 3 27/27; findings F-S1..S6 triaged (F-S2 and F-S5 since fixed by quick tasks 260918-32u / 260918-322) |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 73s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-09-18 — every one of the 18 automated rows has its test file on disk and green; the one manual row (73-07-03, `gate="blocking-human"` by D-73-18) was run by the operator and is recorded in `73-UAT.md`.

---

## Validation Audit 2026-09-18

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

Audit scope: the 19 planning-time rows (plans 73-01..73-07) plus the two follow-on quick
tasks (260918-322 F-S5 verify normaliser, 260918-32u F-S2 phantom marker). Full suite green
at commit `759d023b`: `.venv/bin/python -m pytest tests/ operator-claude-plugin/tests/`
4993 passed / 154 skipped; `node --test tests/n8n/*.test.mjs` 1218 / 0. No gap needed a
generated test, so no nyquist auditor was spawned (State A, no gaps → Step 6).
