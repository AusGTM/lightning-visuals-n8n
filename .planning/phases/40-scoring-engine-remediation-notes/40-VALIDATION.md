---
phase: 40
slug: scoring-engine-remediation-notes
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
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
| (populated by planner) | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Parity fixture/oracle test scaffolding per PARITY-01 (planner defines exact files)

*Existing infrastructure (pytest + node:test) covers unit-level phase requirements; live HubSpot assertions gated behind env-var skipif.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live flow behavior after PUT (disposable-company chain fire) | ENGINE-01..07, VETO-01..03 | Requires live portal + timing waits | Disposable-company create/exercise/delete probes; see plan tasks |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
