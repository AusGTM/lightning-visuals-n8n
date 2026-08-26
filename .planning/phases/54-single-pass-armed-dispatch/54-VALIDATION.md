---
phase: 54
slug: single-pass-armed-dispatch
status: planned
nyquist_compliant: true
wave_0_complete: true
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
| 01-T1 | 54-01 | 1 | G-3 | T-54-01 | measurement module may only read executions; never arms | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_measure_dispatch.py -q` | ❌ created by task | ⬜ pending |
| 01-T2 | 54-01 | 1 | G-3 | T-54-02 | report records ids and counts, no credentials | doc assert | `grep -q "OP-54-05" .../54-MEASUREMENT.md` | ❌ created by task | ⬜ pending |
| 01-T3 | 54-01 | 1 | G-3 | T-54-03, T-54-04 | a computed figure is never labelled measured | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -q` | ✅ | ⬜ pending |
| 02-T1 | 54-02 | 1 | G-3 | T-54-05 | no reachable outcome renders as unknown | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_enrichment.py operator-claude-plugin/tests/test_report_sufficiency.py -q` | ✅ | ⬜ pending |
| 02-T2 | 54-02 | 1 | G-3 | T-54-06 | the second-pass cost is stated before it is incurred | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_enrich_skill_contract.py -q` | ✅ | ⬜ pending |
| 02-T3 | 54-02 | 1 | G-3 | T-54-07 | scoped Edit only; no phase entry lost | doc assert | `test "$(grep -c '^### Phase ' .planning/milestones/v1.1-ROADMAP.md)" -ge 5` | ✅ | ⬜ pending |
| 03-T1 | 54-03 | 1 | G-3 | T-54-09 | read-only property listing; patch names only live properties | doc assert | `grep -qE "lv_enrichment_reviewed_at" .../54-CONTACTS-PROPERTY-CHECK.md` | ❌ created by task | ⬜ pending |
| 03-T2 | 54-03 | 1 | G-3 | T-54-13 | operator decides the mirror's reach with the flood consequence in view | checkpoint | manual (blocking) | — | ⬜ pending |
| 03-T3 | 54-03 | 1 | G-3 | T-54-09, T-54-10, T-54-11, T-54-12 | same write gate, same compare-and-set, policy-correct protected-class filter | unit (node) | `node --test tests/n8n/*.test.mjs` | ✅ | ⬜ pending |
| 03-T4 | 54-03 | 1 | G-3 | T-54-12 | pins rewritten in place with dated reasons, never deleted | unit (node) | `node --test tests/n8n/*.test.mjs` | ✅ | ⬜ pending |
| 04-T1 | 54-04 | 2 | G-3 | T-54-15 | builder-authored JSON only; no node added | unit + build | `python3 scripts/build_cloud_workflows.py && .venv/bin/python -m pytest operator-claude-plugin/tests/test_review_outcome_parity.py -q` | ✅ | ⬜ pending |
| 04-T2 | 54-04 | 2 | G-3 | T-54-14, T-54-16 | disarmed deploy, bounce, fresh-GET read-back | live (recorded) | `grep -qiE "bounce\|deactivat" .../54-DEPLOY-RECORD.md` | ❌ created by task | ⬜ pending |
| 04-T3 | 54-04 | 2 | G-3 | T-54-17 | step 6 consent ceremony untouched | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q -k review` | ✅ | ⬜ pending |
| 05-T1 | 54-05 | 3 | G-3 | T-54-20 | preview only; nothing armed, nothing submitted | doc assert | `grep -qiE "branch" .../54-LIVE-PROOF.md` | ❌ created by task | ⬜ pending |
| 05-T2 | 54-05 | 3 | G-3 | T-54-18, T-54-19 | operator-opened record-scoped window; consent binds to the shown patch | checkpoint (blocking) | manual | — | ⬜ pending |
| 05-T3 | 54-05 | 3 | G-3 | T-54-20, T-54-21 | disarm verified by re-read; unexercised branch not claimed | doc assert | `grep -qiE "disarm" .../54-LIVE-PROOF.md` | ❌ created by task | ⬜ pending |

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

**Approval:** planner-filled 2026-08-27. Every code-producing task carries an `<automated>` verify;
the three checkpoint/live rows are the manual-only verifications already declared above, each with
its own recorded-evidence artifact. No 3 consecutive tasks lack an automated verify.
