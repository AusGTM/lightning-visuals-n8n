---
phase: 43
slug: pipeline-scoring-hygiene-explainability
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-07
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/python -m pytest`) + Node's built-in `node --test` (no jest/mocha) |
| **Config file** | none — this repo has no pytest config; gated scripts use env-var gating, not markers |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py tests/test_scoring_parity.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs` + `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Estimated runtime** | ~10s targeted; ~20s full offline across all three suites |

**Measured baselines (live-run during research, not copied forward):**

| Suite | Baseline |
|---|---|
| `.venv/bin/python -m pytest -q` | 2362 passed, 118 skipped |
| `node --test tests/n8n/*.test.mjs` | 636 passed, 0 failed |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | 1284 passed, 5 skipped |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | 0 across all 8 generated workflows |

---

## Sampling Rate

- **After every task commit:** file-scoped pytest run for the file(s) touched
- **After every plan wave:** full offline suite across all three test packages
- **Phase gate:** all suites green above baseline; arming grep still 0; **no live deploy until Phase 41 has disarmed**
- **Max feedback latency:** ~10 seconds for the targeted tier

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| TBD by planner | — | — | PIPE-01 | All 6 boolean-writer sites emit strings | unit (anchored grep over generated JSON) | `.venv/bin/python -m pytest tests/test_cloud_companies_branch.py -q` | ✅ file exists, new functions | ⬜ pending |
| TBD by planner | — | — | PIPE-01 | HubSpot EQ filter actually matches post-fix | live (gated `RUN_LIVE_PARITY=true`) | new live test using `disposable_company` | ❌ Wave 0 | ⬜ pending |
| TBD by planner | — | — | PIPE-02 | `min_confidence` stays ≥80 | unit — **ALREADY EXISTS AND PASSES** | `pytest tests/test_cloud_companies_branch.py::test_merge_companies_veto_policy_entries_carry_a_real_min_confidence -q` | ✅ no new work | ✅ green |
| TBD by planner | — | — | PIPE-02 | Coercion present, proven statically (D-10) | unit (source-text regex, never drives the dead path) | same file, new function | ❌ Wave 0 | ⬜ pending |
| TBD by planner | — | — | PIPE-02 | Dead-path proof stays untouched and green | unit — **ALREADY EXISTS** | `pytest tests/test_cloud_companies_branch.py::test_company_canonical_patch_never_contains_a_derived_icp_output_field -q` | ✅ must remain green | ✅ green |
| TBD by planner | — | — | PIPE-03 | Truncated breakdown is valid JSON and carries the total | unit (stubbed `fetch_fn`) + live (gated) | `pytest tests/test_scoring_parity.py -q` | ✅ file exists, new functions | ⬜ pending |
| TBD by planner | — | — | PIPE-03 | Read-only default path unaffected (Phase 40 D-12) | unit — assert no write function is called without the flag | new test | ❌ Wave 0 | ⬜ pending |
| TBD by planner | — | — | PIPE-04 | Report is correct over an EMPTY dataset | unit (stubbed fetch returning zero rows) | new `tests/test_loss_reason_report.py` | ❌ Wave 0 | ⬜ pending |
| TBD by planner | — | — | PIPE-04 | Plugin skill never imports backend code | unit — **ALREADY EXISTS**, auto-covers new plugin files | `pytest operator-claude-plugin/tests/test_no_backend_imports.py -q` | ✅ no new work | ✅ green |

*Populated by the planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Offline tests for PIPE-01's four candidate-field coercion sites plus the `reviewApply.js` clearPatch fix
- [ ] A live-gated test proving the HubSpot EQ filter matches post-fix (uses the `disposable_company` fixture)
- [ ] An offline, source-text-only test for PIPE-02's coercion presence — must not drive the dead candidate path (D-10)
- [ ] Offline + live tests for `--write-breakdown`: valid JSON under truncation, total present, read-only-by-default guard
- [ ] `scripts/build_loss_reason_report.py` plus an offline test — **must be correct over an empty dataset**, which is D-04's explicit requirement and the expected first-run outcome, not an edge case
- [ ] A new plugin skill directory under `operator-claude-plugin/skills/` — the existing import guard covers it with no new setup

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live existence of `lv_closed_lost_reason` on Deals | PIPE-04 | Never verified anywhere in this repo — static grep only. Cannot be settled without live credentials | Operator runs a Deal property read; if absent, the report says so with counts rather than failing |
| `hs_primary_associated_company` coverage on closed-lost deals | PIPE-04 | Determines whether the tier cross-tab can join directly or needs the Associations v4 API | Operator runs a sample read; planner's fallback path applies if coverage is partial |
| n8n deploy + bounce after the builder regeneration | PIPE-01, PIPE-02 | Deploy is credential-gated and operator-armed | **Must not run until Phase 41 has disarmed** — a content deploy rebakes write-safety and would close 41's window |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for the offline tier
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-07 (gsd-plan-checker: PASSED, 0 blockers, 0 warnings)
