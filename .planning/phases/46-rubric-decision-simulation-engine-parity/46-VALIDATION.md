---
phase: 46
slug: rubric-decision-simulation-engine-parity
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-11
---

# Phase 46 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `46-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | none dedicated — repo-root `tests/` package |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_icp_scoring.py tests/test_scoring_parity.py tests/test_flow_rubric_conformance.py -k "not live" -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` (whole repo, offline; `RUN_LIVE_PARITY=true` adds the live tier) |
| **Estimated runtime** | ~15s quick / ~180s full offline (baseline 2498 passed, 121 skipped) |

> Use `.venv/bin/python -m pytest` — the system Python lacks this repo's deps.

---

## Sampling Rate

- **After every task commit:** Run the quick run command above
- **After every plan wave:** Run `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** Full offline suite must be green
- **Live tier** (`RUN_LIVE_PARITY=true`): run manually only in a session where the operator's HubSpot credentials are reachable
- **Max feedback latency:** 15 seconds (quick), 180 seconds (full)

---

## Per-Task Verification Map

*Populated by `/gsd-validate-phase` once PLAN.md task IDs exist.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | RUBRIC-01 | — | N/A (decision doc, not code) | manual | n/a | n/a | ⬜ pending |
| TBD | TBD | TBD | RUBRIC-02 | T-46-01 | Simulation performs no HubSpot write | unit | `.venv/bin/python -m pytest tests/test_simulation_no_write.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RUBRIC-03 | — | Org-type + deduction weights identical in Python oracle and HubSpot flow | offline | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -q` | ✅ needs edit | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] A **no-write assertion** for the new simulation script — RUBRIC-02's zero-write bar (D-08) needs a positive test, not a docstring claim. Assert the simulation's HTTP layer is GET-only and that no `patch_record` / `batch_update_companies` path is reachable from it.
- [ ] `src/icp_scoring.py::compute_icp_score` needs a `cfg=None` parameter before any simulation code can call it twice with different weight tables (current signature loads the YAML internally).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The weight decision is recorded with traceable evidence and, where it overrides the evidence, records the override | RUBRIC-01 | A decision record is a document, not a behavior — no automated assertion can judge whether the reasoning is sound | Read `46-DECISION.md`; confirm each changed weight cites `docs/business/icp-scoring.md` and that GTM overrides are stated as overrides, with the underlying evidence left intact (D-14) |
| Operator sign-off on the simulation before the phase seals | RUBRIC-01 / D-05 | Blocking human checkpoint by design | Present `46-DECISION.md` + the simulation report; operator accepts or overrides |
| Live-tier parity against the running HubSpot flow | RUBRIC-03 | Requires live portal credentials not present in every session | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py -q`, plus a live read-back of flow `4626124224` |
| Live re-verification of the 66-record population and the 18 blank `lv_org_type` rows | RUBRIC-02 | Requires a live HubSpot query; the committed snapshot is 3 days stale | Run the search query specified in `46-RESEARCH.md` Open Question 1 before the simulation locks its row set |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
