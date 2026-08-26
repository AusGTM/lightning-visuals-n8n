---
phase: 54
slug: single-pass-armed-dispatch
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-27
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + node --test (existing) |
| **Config file** | existing — no Wave 0 framework install |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** quick run command
- **After every plan wave:** full suite
- **Before `/gsd-verify-work`:** full suite green (modulo the 4 known `test_merge_policy.py` failures — pre-existing pydantic/anthropic SDK mismatch, reproduce with the phase diff reverted)
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled by planner) | | | G-3 | — | no write without an armed, record-scoped window | unit | see plan | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — new tests extend `tests/n8n/reviewDecisionEndpoint.test.mjs` and the plugin pytest suites.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live before/after execution + credit count on one record | G-3 | Requires live n8n executions; the saving must be measured, not projected | Disarmed baseline read + one armed send, counted via `executions_client` |
| Contact review approve applies values live | operator ruling 2026-08-27 | Requires a real flagged contact and an operator-authorized window | Approve one flagged contact, independent read-back of the applied fields |
| Anthropic dollar figure | G-3 | No code path captures real `msg.usage` — a true measurement needs new instrumentation | Report as floor, or instrument and say so |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
