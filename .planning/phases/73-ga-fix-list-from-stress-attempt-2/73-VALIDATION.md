---
phase: "73"
slug: "ga-fix-list-from-stress-attempt-2"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-15"
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
| 73-01-01 | 01 | 1 | F-B5 | see plan `<threat_model>` | N/A | tracer | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_r…` | ✅ | ⬜ pending |
| 73-01-02 | 01 | 1 | F-B5 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_r…` | ✅ | ⬜ pending |
| 73-01-03 | 01 | 1 | F-B5 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_m…` | ✅ | ⬜ pending |
| 73-02-01 | 02 | 2 | F-E1, F-A3r | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/reviewLoop.test.mjs tests/n8n/reviewDecisionEndpoint.test.mjs tests/n8n/hubspo…` | ✅ | ⬜ pending |
| 73-02-02 | 02 | 2 | F-E1, F-A3r | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/ingestSearchThrottle.test.mjs tests/n8n/ingestCarryMerge.test.mjs` | ✅ | ⬜ pending |
| 73-03-01 | 03 | 3 | F-B7, F-B4, F-B3 | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/companyDomainVariants.test.mjs tests/n8n/companyAssociationFlow.test.mjs tests…` | ✅ | ⬜ pending |
| 73-03-02 | 03 | 3 | F-B7, F-B4, F-B3 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/companyNameOnlyOutcome.test.mjs tests/n8n/companyNameFallbackFlow.test.mjs tes…` | ✅ | ⬜ pending |
| 73-03-03 | 03 | 3 | F-B7, F-B4, F-B3 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/companyFreemailRefusal.test.mjs tests/n8n/companyLink.test.mjs` | ✅ | ⬜ pending |
| 73-04-01 | 04 | 4 | F-A5 | see plan `<threat_model>` | N/A | tracer | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_d…` | ✅ | ⬜ pending |
| 73-04-02 | 04 | 4 | F-A5 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_d…` | ✅ | ⬜ pending |
| 73-05-01 | 05 | 5 | F-B6, F-A1, F-A2, F-B1 | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/backendStatusCredits.test.mjs tests/n8n/backendStatus.test.mjs tests/n8n/backe…` | ✅ | ⬜ pending |
| 73-05-02 | 05 | 5 | F-B6, F-A1, F-A2, F-B1 | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_write…` | ✅ | ⬜ pending |
| 73-06-01 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | tracer | `node --test tests/n8n/pairCreateOutcome.test.mjs tests/n8n/ingestCarryMerge.test.mjs tests/n8n/compa…` | ✅ | ⬜ pending |
| 73-06-02 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/walkerHttpErrorOutput.test.mjs tests/n8n/walkerEngineFidelityV1.test.mjs tests…` | ✅ | ⬜ pending |
| 73-06-03 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/ingestCreateErrorLane.test.mjs tests/n8n/ingestCarryMerge.test.mjs tests/n8n/i…` | ✅ | ⬜ pending |
| 73-06-04 | 06 | 6 | F-A6 | see plan `<threat_model>` | N/A | auto | `node --test tests/n8n/*.test.mjs 2>&1 \| tail -5 && .venv/bin/python -m pytest -q --tb=short -p no:ca…` | ✅ | ⬜ pending |
| 73-07-01 | 07 | 7 | F-A6, F-A5, F-E1, F-B7, F-B3, F-A3r | see plan `<threat_model>` | N/A | auto | `.venv/bin/python scripts/build_cloud_workflows.py && .venv/bin/python -c "import subprocess,sys; out…` | ✅ | ⬜ pending |
| 73-07-02 | 07 | 7 | F-A6, F-A5, F-E1, F-B7, F-B3, F-A3r | see plan `<threat_model>` | N/A | auto | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_plugi…` | ✅ | ⬜ pending |
| 73-07-03 | 07 | 7 | F-A6, F-A5, F-E1, F-B7, F-B3, F-A3r | see plan `<threat_model>` | N/A | manual (operator gate) | `MISSING` | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/n8n/lib/walkWorkflow.mjs` second HTTP output (73-06 Task 2, RED-first)
- [ ] frozen redacted runData fixture for exec 12434/12449 (73-01 Task 1, RED-first)
- [ ] batchInterval=400 shape test (73-02), first-wins dedupe test (73-04)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| deploy + bounce disarmed, reset, stress attempt 3 A–F | 73-07 gate (D-73-18) | operator-only; never armed from Claude | RUNBOOK.md "Restart procedure" |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 73s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
