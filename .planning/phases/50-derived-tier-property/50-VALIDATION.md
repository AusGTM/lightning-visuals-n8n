---
phase: 50
slug: derived-tier-property
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-13
---

# Phase 50 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `50-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python; offline + env-gated live) and `node --test` (n8n JS — untouched by this phase but part of the suite) |
| **Config file** | none dedicated — live tests gated by env vars, not pytest markers |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_tier_formula_pin.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` (glob form — directory form is broken on node 24) |
| **Estimated runtime** | ~30 seconds offline; live parity sweep ~1–2 min (66 companies) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_tier_formula_pin.py -x` (sub-second, no network)
- **After every plan wave:** Run `.venv/bin/python -m pytest` plus `python scripts/check_schema_drift.py` (must be `0`, or a *documented, expected* nonzero from the `DO_NOT_ARCHIVE_*` fix — never an undocumented `2`)
- **Before `/gsd-verify-work`:** Full suite green; the 66-company parity artifact freshly generated against live HubSpot, never reused from a stale capture
- **Max feedback latency:** 30 seconds offline

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 50-W0-01 | TBD | 0 | TIER-01 | — | N/A | unit | `.venv/bin/python -m pytest tests/test_tier_formula_pin.py -x` | ❌ W0 | ⬜ pending |
| 50-W0-02 | TBD | 0 | TIER-02 | T-50-write | Two-key gate blocks unarmed live property writes | live probe | `python scripts/check_tier_null_propagation.py` | ❌ W0 | ⬜ pending |
| 50-W0-03 | TBD | 0 | TIER-03 | — | Read-only sweep, no writes | live read | `python scripts/sweep_tier_dependents.py` | ❌ W0 | ⬜ pending |
| 50-W0-04 | TBD | 0 | TIER-01, TIER-03 | T-50-gate | Parity gate refuses cutover on any unexplained mismatch | live evidence | `python scripts/check_tier_derived_parity.py` | ❌ W0 | ⬜ pending |
| 50-W0-05 | TBD | 0 | TIER-03 | — | Drift comparator stays truthful post-archive | offline comparator | `python scripts/check_schema_drift.py` | ✓ exists (needs edit) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are provisional — the planner rebinds them to real `{phase}-{plan}-{task}` ids.*

---

## Wave 0 Requirements

- [ ] `tests/test_tier_formula_pin.py` — key-by-key pin of the derived `calculationFormula` against `config/icp_scoring.yaml`'s `tier_rules`, in `test_rubric_change_guard.py`'s shape (D-17 item 1)
- [ ] `scripts/check_tier_derived_parity.py` — D-07's gate script; produces the D-17 item 4 evidence artifact across all 66 scored companies
- [ ] `scripts/check_tier_null_propagation.py` — D-05's fresh two-key-gated live probe (repo `DRY_RUN=false` key + its own allow-key; disposable property archived in a `finally` block and verified gone by 404 re-read)
- [ ] `scripts/sweep_tier_dependents.py` — D-13's scripted, re-runnable dependent enumeration (lists + flows via API; saved views and reports/dashboards are API-blind and need a logged manual UI check)
- [ ] `scripts/check_schema_drift.py` — edit the `DO_NOT_ARCHIVE_*` structures that currently return exit `2` the moment `lv_icp_tier` is archived or WF1 `4625147345` is disabled (research Pitfall 2)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Saved views / saved filters referencing `lv_icp_tier` | TIER-03 | No documented public HubSpot API enumerates saved views or filters | Operator opens the companies object views list, filters for any view whose filter set names `lv_icp_tier`; record findings in the sweep artifact as a manual section |
| Reports / dashboards grouping by `lv_icp_tier` | TIER-03 | No documented public HubSpot API enumerates reports or dashboards | Operator checks the reports library for any report grouping or filtering on the tier; record in the same artifact |
| Rollback drill: forced re-enrolment into WF1 | TIER-03 | Automation v4 exposes no enrolment endpoint; only portal-UI "Enroll now" (requires WF1 ON) or an armed perturb-then-restore double-write | Prove the chosen mechanism *before* WF1 is switched off (D-18); record the proof as evidence |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
