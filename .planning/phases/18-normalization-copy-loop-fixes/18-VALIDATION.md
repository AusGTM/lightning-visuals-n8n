---
phase: 18
slug: normalization-copy-loop-fixes
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-29
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (`.venv/bin/python -m pytest`) + node:test (`node --test tests/n8n/*.test.mjs`) |
| **Config file** | pytest.ini / none for node (file-glob form required — dir form broken on node 24) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_merge_policy.py tests/test_normalizer.py -q` + targeted `node --test tests/n8n/<touched>.test.mjs` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (targeted files for the touched lane)
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green (596 pytest / 285 node baseline, zero regressions)
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-XX | 01 | 1 | NORM-01 | — | numeric provider industry code never normalizes unchanged nor wins waterfall | unit (red-before-green) | `node --test tests/n8n/*.test.mjs` + `.venv/bin/python -m pytest -q` | ❌ W0 | ⬜ pending |
| 18-01-XX | 01 | 1 | COPY-01 | — | `lv_sponsorship_reliant` populates from real candidate in `ENRICH_MERGE_CO` | unit (red-before-green) | `node --test tests/n8n/*.test.mjs` | ❌ W0 | ⬜ pending |
| 18-01-XX | 01 | 1 | COPY-02 | — | `persona_group`/`lv_persona_group` populates from winners loop in `ENRICH_MERGE` | unit (red-before-green) | `node --test tests/n8n/*.test.mjs` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Red tests authored from the execution-19 real conflict shape (Apollo `"media production"` vs ZoomInfo `"71"`) before the NORM-01 fix lands
- [ ] Red tests for COPY-01/COPY-02 constructed candidates before wrapper copy-loop edits
- [ ] Frozen-fixture re-baseline procedure (Phase 16.3 bounded diff) applied if `Merge Company` jsCode changes

*Existing infrastructure (pytest + node:test row-flow harnesses) covers all phase requirements.*

---

## Manual-Only Verifications

*If none: "All phase behaviors have automated verification."*

All phase behaviors have automated verification (offline suite + deterministic rebuild diff).

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
