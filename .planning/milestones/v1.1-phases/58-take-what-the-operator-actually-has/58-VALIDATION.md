---
phase: 58
slug: take-what-the-operator-actually-has
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-26
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (plugin: `.venv/bin/python -m pytest operator-claude-plugin/tests/`) + node --test (`node --test tests/n8n/*.test.mjs` — glob form, dir form broken on node 24) |
| **Config file** | existing — no Wave 0 framework install |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled by planner) | | | INPUT-01..04 | — | never silently invent a domain | unit | see plan | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — pytest + node --test suites already run; new test files extend existing patterns (`test_extraction_contract.py`, `test_enrichment_envelope.py`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live n8n propose-mode spike (mode key survives webhook parse) | INPUT-03 | Requires live n8n execution; not reproducible offline | Disarmed POST, read execution runData |
| Operator walk of confirm-table wording | INPUT-04 / VOCAB-04 | Wording test is a walk transcript, not a review | Walk with real mixed input |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
