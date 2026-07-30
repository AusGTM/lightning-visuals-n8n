---
phase: 22
slug: armed-e2e-enrichment-canary
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + node:test (node 24) |
| **Config file** | existing — no Wave 0 install |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -q -x` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/ -q -x`
- **After every plan wave:** Run full suite (pytest + node --test)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| T-22-A1 | 22-01 | 1 | REQ-armed-e2e-canary | T-22-01, T-22-04 | Snapshot tool has no HubSpot write path; research-gate prediction imports the live vocabulary | unit | `.venv/bin/python -m pytest tests/test_canary_record_snapshot.py -q` | ❌ new | ⬜ pending |
| T-22-A2 | 22-01 | 1 | REQ-canary-cost-ledger | T-22-02, T-22-05 | Execution fixture is allow-list redacted; extraction never raises on truncated payloads | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q -k "token or redact"` | ❌ new | ⬜ pending |
| T-22-B1 | 22-02 | 1 | REQ-armed-e2e-canary | T-22-06, T-22-07, T-22-08 | Half-disarmed, stale-allowlist and create-also-armed states all fail the read-back | unit | `.venv/bin/python -m pytest tests/test_verify_live_write_safety.py -q` | ❌ new | ⬜ pending |
| T-22-B2 | 22-02 | 1 | REQ-armed-e2e-canary | T-22-06 | Live disarmed baseline proves the closing gate green before any arming | manual_procedural (read-only live) | `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')"` | ✅ after 22-02 T1 | ⬜ pending |
| T-22-C1 | 22-03 | 2 | REQ-canary-cost-ledger | T-22-11, T-22-12, T-22-15 | Unknown balances propagate as unknown; only usage endpoints reachable; Lusha lag settled | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q -k "credit or settle"` | ❌ new | ⬜ pending |
| T-22-C2 | 22-03 | 2 | REQ-canary-cost-ledger | T-22-14 | Every estimate entry carries a citation to a document present in the repo | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q -k estimate` | ❌ new | ⬜ pending |
| T-22-D1 | 22-04 | 3 | REQ-armed-e2e-canary, REQ-canary-cost-ledger | T-22-16..T-22-22 | Runbook: read-back after every arm, mandatory pre-canary branch, abort path | manual_procedural (doc review) | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` (suite guard only) | ❌ new | ⬜ pending |
| T-22-D3 | 22-04 | 3 | REQ-armed-e2e-canary | T-22-16, T-22-17, T-22-21 | The armed window itself: allowlist honoured, neighbours untouched, disarmed close | manual (operator-run, blocking checkpoint) | procedure in `22-OPERATOR-RUNBOOK.md` — no automated command (19-OPERATOR-RUNBOOK bar) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None for test infra (621 pytest / 354 node green at phase start). The armed window itself is operator-run; agent-side validation is runbook completeness + read-only pre/post verification tooling.
