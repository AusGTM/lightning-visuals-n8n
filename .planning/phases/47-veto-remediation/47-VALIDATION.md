---
phase: 47
slug: veto-remediation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-11
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `47-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + `node --test` (n8n JS fixtures) |
| **Config file** | none dedicated — invoked directly (see memory `test-suite-run-commands.md`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k veto -x` |
| **Full suite command** | `.venv/bin/python -m pytest` then `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~60s offline; live integration tests are minutes (settle polling) |

**Note:** system `python` lacks deps — always use `.venv/bin/python`. The dir-form
`node --test tests/n8n/` is broken on node 24; use the glob form.

---

## Sampling Rate

- **After every task commit:** Run the quick command.
- **After every plan wave:** Run the full suite.
- **Before `/gsd-verify-work`:** Full suite green *except* the known red-by-design
  `scripts/run_scoring_parity.py` population sweep (red from Phase 46 commit `caae5d6` until
  Phase 49 re-scores — expected, not a new defect).
- **Max feedback latency:** 60s offline.

### Two settle loops, never one

Per research: `lv_icp_fit_score` / `lv_icp_tier` settle via the HubSpot calculated property +
WF1 (seconds). `lv_anti_icp_flag` / `lv_anti_icp_reason` settle only after the n8n
`Decide Company Action` node runs (D-18 webhook POST). These are genuinely different mechanisms
and MUST NOT share one poll loop or one timeout.

---

## Per-Task Verification Map

> Task IDs are filled in by the planner; the requirement/behavior rows below are fixed.

| Behavior | Requirement | Test Type | Automated Command | File Exists | Status |
|----------|-------------|-----------|-------------------|-------------|--------|
| 17 records' inputs populated; component scores computed correctly | VETO-01 | unit (offline) | `.venv/bin/python -m pytest tests/test_backfill_seed_company_scores.py -x` | ✅ | ⬜ pending |
| `lv_anti_icp_flag`/`lv_anti_icp_reason` actually clear on a corrected record | VETO-01 | integration (live, disposable) | `.venv/bin/python -m pytest tests/test_scoring_parity.py::test_veto_clear_after_correction -x` | ✅ (red today) | ⬜ pending |
| Per-ID before/after assertion across the 17 pinned IDs | VETO-01 | integration (live, read-only) | ❌ Wave 0 — must be created | ❌ W0 | ⬜ pending |
| Never-write guard: no payload contains `lv_anti_icp_flag`/`_reason`/`lv_icp_fit_score`/`lv_icp_tier` | VETO-01 / D-07 | unit (offline) | `.venv/bin/python -m pytest -k never_write -x` | ❌ W0 — verify/extend | ⬜ pending |
| Both write surfaces armed with a cap + pinned allowlist, then disarmed and read back | VETO-02 | script exit code + manual | batch-PATCH script's own gate AND `n8n_arming.disarm()` read-back | ❌ W0 | ⬜ pending |
| HubSpot search for non-ANZ veto reason + blank region returns zero | VETO-03 | manual (script-free by design) | operator runs the verbatim search in `47-RESEARCH.md` §"VETO-03 acceptance search" | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Per-ID before/after assertion for the 17 pinned IDs — none exists;
      `run_scoring_parity.py` samples the wider population, not this cohort.
- [ ] A "settled to the *expected value*, not merely stopped changing" wrapper around
      `_settle()` / `settle()` — the existing helper has no expected-value assertion, so D-10's
      "fail loudly" bar is not met by it alone.
- [ ] A second settle path for the veto fields keyed to the D-18 webhook POST, with its own
      (longer) timeout, separate from the calculated-property settle.
- [ ] Confirm/extend the offline guard asserting the never-write field set. Research found
      "T-40-22" is a plan-task label, not a test function name — locate the real assertion or
      create one.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Arming both write surfaces | VETO-02 | Operator-only per-shell env gates (`ALLOW_N8N_ARM`, `ALLOW_HUBSPOT_RECORD_WRITES`) — never set by Claude, by standing project rule | Operator runs the exact armed command the plan hands them; Claude runs the disarmed dry-run before and the disarm + read-back after |
| Zero-result HubSpot search | VETO-03 | Requirement's own text demands it be provable from HubSpot alone with no script | Operator runs the verbatim search from `47-RESEARCH.md` §"VETO-03 acceptance search" |
| Legitimate residual Tier D is correct, not a failure | VETO-01 / D-16 | Requires judgment: a cleared false veto may reveal a genuine one (e.g. Simtech LED as `hardware_vendor`) | For any record still flagged, operator confirms the reason is a *different, correct* veto — never "Non-ANZ geography" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references above
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s offline
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
