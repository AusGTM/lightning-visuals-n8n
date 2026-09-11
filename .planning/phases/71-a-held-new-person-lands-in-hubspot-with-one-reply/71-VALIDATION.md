---
phase: "71"
slug: "a-held-new-person-lands-in-hubspot-with-one-reply"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-12"
---

# Phase 71 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (plugin suite under `operator-claude-plugin/tests/`, `conftest.py` adds `scripts/` to `sys.path`); node `--test` for `tests/n8n/*.test.mjs` |
| **Config file** | none dedicated beyond `operator-claude-plugin/tests/conftest.py` |
| **Quick run command** | `.venv/bin/python -m pytest -q --tb=short -x -p no:cacheprovider operator-claude-plugin/tests/test_held_queue.py operator-claude-plugin/tests/test_held_queue_facets.py operator-claude-plugin/tests/test_review_triage_facets.py operator-claude-plugin/tests/test_held_facet_render_composition.py` |
| **Full suite command** | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/ && .venv/bin/python -m pytest -q tests/test_todo_triage.py` |
| **Estimated runtime** | quick ~5s (66 tests); plugin suite ~60s (3006 passed, 5 skipped baseline 2026-09-12) |

Always `.venv/bin/python`, never system python. Use `/usr/bin/grep` for counts and pipes.

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled by planner from PLAN.md tasks) | | | D-71-01..06 | — | | unit / composition | see RESEARCH.md § Validation Architecture | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `operator-claude-plugin/tests/test_held_queue.py` — new RED-first tests: entries-map KEY containing `grant`/`token` as a whole token persists; legacy `row-N`-keyed document reads `ANOMALOUS`
- [ ] `operator-claude-plugin/tests/test_run_manifest.py` — new test: `rows_to_resume` finds a prior-run held entry by stable key when `row_id` differs
- [ ] `operator-claude-plugin/tests/test_held_queue_facets.py` — new test: a stamped Jimmy-shaped entry reads `FACET_NEW_PERSON` on both surfaces' derivation

Existing infrastructure (pytest, conftest) covers framework needs.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A `new_person` row lands live in HubSpot with one `create all N` reply on the batch surface, then `review-triage` cold-start create on a second such row in a fresh sitting | D-71-06 | Live n8n Cloud + HubSpot, per-send arming, human gate (backloaded to end of phase) | `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` §1d; delete `held_queue.json` (D-71-05 wipe) and hand-delete UAT contacts in clean-up; disarm after |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
