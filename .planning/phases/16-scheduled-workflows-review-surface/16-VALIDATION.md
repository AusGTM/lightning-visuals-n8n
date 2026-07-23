---
phase: 16
slug: scheduled-workflows-review-surface
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 16-RESEARCH.md `## Validation Architecture`. The offline discipline of Phases 13–15.5 holds: zero live network calls, zero HubSpot writes — live-shaped behavior proven against fixtures.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python oracle) + node:test (n8n Code-node JS) |
| **Config file** | none required — existing suite layout under tests/ and tests/n8n/ |
| **Quick run command** | `python -m pytest -q` |
| **Full suite command** | `python -m pytest -q && node --test tests/n8n/` |
| **Estimated runtime** | ~30 seconds |

Baseline before this phase: 201 pytest / 123 node passing (Phase 15.5). New tests are additive; zero regressions is the bar.

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest -q` (or the node subset if the task touched only JS)
- **After every plan wave:** Run the full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-XX | 01 | 1 | Criteria 5–8 | T-16-01 / — | secrets never inlined into workflow JSON; deploy/creds scripts skip without two keys; local-replica & Cloud builders share one flag/secret source (parity) | unit | `python -m pytest -q` (incl. `tests/test_builder_flag_parity.py`) | ❌ W0 | ⬜ pending |
| 16-02-XX | 02 | 2 | Criteria 1–4, 9 | — | SJ predicates key on inputs only, never lv_icp_tier | unit | `python -m pytest -q && node --test tests/n8n/` | ❌ W0 | ⬜ pending |

*Filled concretely by the planner per task. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Acceptance-test stubs for SJ-1/SJ-2/SJ-3 schedule predicates (spec §0.7 defers them to this phase)
- [ ] `test_top_level_is_exactly_the_deployable_set` guard for the deploy script's deployable set
- [ ] Parity test (`tests/test_builder_flag_parity.py`, 16-01 Task 4): both enrichment builders source the 6 flags + 6 secrets from one shared constant (`CONFIG_FLAG_DEFAULTS`/`SECRET_ENV_NAMES`), so local-replica ($env via docker) and Cloud (credentials/AR-4 constants) cannot diverge silently
- [ ] Non-clobber-under-live-writes property test (first phase with real record writes)

*Planner authors the exact file paths in each plan.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Cloud deploy + credential provisioning | Criteria 6–7 | Requires the live n8n Cloud instance + real API keys; offline suite proves script logic against stubs | Operator runbook step — dry-run diff first, then run with two keys present |
| §22.2 review-loop human approval step | Criterion 3 | RevOps sets the approve flag by hand in HubSpot | Runbook: flag a record → verify decision JSON written → approve → confirm apply+clear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
