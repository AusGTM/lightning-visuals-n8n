---
phase: 42
slug: scoring-artifact-cleanup-reconciliation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-07
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/python -m pytest`) |
| **Config file** | none dedicated — repo-root `tests/` package |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_hubspot_properties_config.py tests/test_hubspot_schema_coverage.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest` (offline tier; live tests opt in via env) |
| **Estimated runtime** | ~10s quick, ~8s full offline |

---

## Sampling Rate

- **After every task commit:** the quick offline pytest command above
- **After every plan wave:** full offline suite, plus a live read-only run of the new D-10
  drift-check script (no mutation risk)
- **Phase gate:** full offline suite green; D-10 drift report committed (even when it shows
  documented, accepted divergences); a fresh post-archival
  `snapshot_hubspot_schema.py --label phase42-post` confirming the do-not-archive set is
  still present and enabled
- **Max feedback latency:** ~10 seconds for the offline tier

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD by planner | — | — | CLEAN-01 | — | Snapshot precedes any archival mutation | smoke (live, credential-gated) | `scripts/snapshot_hubspot_schema.py --label phase42-pre` | ✅ | ⬜ pending |
| TBD by planner | — | — | CLEAN-01 | — | Reconciliation performs zero portal writes | unit + live read-only | new D-10 drift-check script | ❌ Wave 0 | ⬜ pending |
| TBD by planner | — | — | CLEAN-01 | — | Do-not-archive set survives the phase | unit (offline) | `.venv/bin/python -m pytest tests/test_flow_rubric_conformance.py -x` | ✅ | ⬜ pending |

*Populated by the planner.  Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] The D-10 standing drift-check script under `scripts/` — does not exist; this phase's
      primary deliverable.
- [ ] `tests/test_hubspot_properties_config.py` updates for the D-04 expansion: the `lv_`
      prefix rule, the valid type/fieldType pairs (missing `calculation_equation`), the exact
      count assertion, and either deletion or rewrite of
      `test_lv_org_type_and_lv_produces_content_not_listed_for_creation` — which currently
      asserts the *absence* of two properties D-04 requires adding.
- [ ] A committed post-Phase-42 property snapshot — the only way to answer the live
      `groupName`/shape question for the five `*_score` properties. No offline substitute.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ambiguous orphan disposition | CLEAN-01 | D-03 archives uncontested orphans automatically but surfaces ambiguous ones; "ambiguous" is a judgement call | Operator reviews the candidate list with per-item evidence before those items are archived |
| Live existence of the five unevidenced properties | CLEAN-01 | Research found no live-creation evidence for `lv_icp_confidence`, `lv_recommended_motion`, `lv_icp_scored_at`, `lv_icp_scoring_version`, `lv_named_account_priority`; one is a documented 404 | A live property read settles it; entries must never be fabricated from the superseded design list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for the offline tier
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-07 (gsd-plan-checker: PASSED, 0 blockers)
