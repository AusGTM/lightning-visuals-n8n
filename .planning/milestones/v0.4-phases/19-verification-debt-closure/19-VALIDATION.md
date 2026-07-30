---
phase: 19
slug: verification-debt-closure
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-29
---

# Phase 19 — Validation Strategy

> Per-phase validation contract. This phase builds nothing — it discharges verification debt; "validation" here means each re-run's outcome is proven and recorded, not new test coverage.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (`.venv/bin/python -m pytest`) + node:test (`node --test tests/n8n/*.test.mjs`) |
| **Config file** | pytest.ini / none for node (file-glob form; dir form broken on node 24) |
| **Quick run command** | targeted test files per re-run item |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After each re-run item:** record outcome (passed / human_needed / failed) in the phase ledger doc before moving on
- **After the plan completes:** full suite green (596 pytest / 309 node floor, zero regressions)
- **Before `/gsd-verify-work`:** all six outcomes on record; any surfaced defect captured as debug brief or backlog item
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-XX | 01 | 1 | VERIFY-01 | — | offline re-runs (11, 15.5): existing suites re-executed against current source | re-run | `.venv/bin/python -m pytest -q` + targeted node tests | ✅ | ⬜ pending |
| 19-01-XX | 01 | 1 | VERIFY-01 | — | live read-only re-runs (16, 16.4, 16.6): DRY_RUN deploy diff + read-only HubSpot/n8n reads via python-dotenv driver — never arms writes | script (read-only) | `DRY_RUN=true` driver invocations | ✅ | ⬜ pending |
| 19-01-XX | 01 | 1 | VERIFY-01 | — | live write re-run (16.9 company:update): checkpoint:human-verify — recorded as human_needed if operator absent | manual | UAT record | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — no new test scaffolding; the deliverable is the recorded ledger.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 16.9 `company:update` armed canary | VERIFY-01 | Arming HubSpot writes is operator-only (session write-gate policy) | Operator runbook step; outcome recorded as human_needed until run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or an explicit human_needed record
- [ ] Six outcomes recorded against their items
- [ ] Surfaced defects captured (debug brief / backlog), none absorbed
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
