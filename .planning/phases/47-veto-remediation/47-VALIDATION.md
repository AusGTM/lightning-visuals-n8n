---
phase: 47
slug: veto-remediation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
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

> Each row is keyed to the concrete plan/task that satisfies it (filled 2026-08-11, Plan 02
> Task 1). The two offline VETO-01 rows and the never-write row are discharged by Plan 01 Tasks
> 1 and 3 (`scripts/remediate_veto_companies.py` tracer + guard suite); the per-ID before/after
> row by Plan 03 Task 1 (`scripts/veto_remediation_report.py`); the VETO-02 armed-then-disarmed
> row by Plan 04 Tasks 1 and 2; the VETO-03 manual search by Plan 04 Task 3.

| Task | Behavior | Requirement | Test Type | Automated Command | File Exists | Status |
|------|----------|-------------|-----------|-------------------|-------------|--------|
| Plan 01 Task 1 / 3 | 17 records' inputs populated; component scores computed correctly | VETO-01 | unit (offline) | `.venv/bin/python -m pytest tests/test_backfill_seed_company_scores.py -x` | ✅ | ⬜ pending |
| Plan 04 Task 2 | `lv_anti_icp_flag`/`lv_anti_icp_reason` actually clear on a corrected record | VETO-01 | integration (live, disposable) | `.venv/bin/python -m pytest tests/test_scoring_parity.py::test_veto_clear_after_correction -x` | ✅ (red today) | ⬜ pending |
| Plan 03 Task 1 | Per-ID before/after assertion across the 17 pinned IDs | VETO-01 | integration (live, read-only) | `.venv/bin/python -m pytest tests/test_veto_remediation_report.py -x` (script: `scripts/veto_remediation_report.py`) | ✅ | ⬜ pending |
| Plan 01 Task 3 | Never-write guard: no payload contains `lv_anti_icp_flag`/`_reason`/`lv_icp_fit_score`/`lv_icp_tier` | VETO-01 / D-07 | unit (offline) | `.venv/bin/python -m pytest -k never_write -x` | ✅ | ⬜ pending |
| Plan 04 Task 1 / 2 | Both write surfaces armed with a cap + pinned allowlist, then disarmed and read back | VETO-02 | script exit code + manual | batch-PATCH script's own gate AND `n8n_arming.disarm()` read-back | ✅ | ⬜ pending |
| Plan 04 Task 3 | HubSpot search for non-ANZ veto reason + blank region returns zero | VETO-03 | manual (script-free by design) | operator runs the verbatim search in `47-RESEARCH.md` §"VETO-03 acceptance search" | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Discharge pointers added 2026-08-11, Plan 02 Task 1.

- [x] Per-ID before/after assertion for the 17 pinned IDs — discharged by
      `scripts/veto_remediation_report.py` (Plan 03 Task 1); `run_scoring_parity.py` still
      samples the wider population, not this cohort, so this new script is additive, not a reuse.
- [x] A "settled to the *expected value*, not merely stopped changing" wrapper around
      `_settle()` / `settle()` — discharged by `settle_and_assert` in
      `scripts/remediate_veto_companies.py` (Plan 01 Task 2), which raises `SettleFailed` on
      both timeout and a stable-but-wrong value.
- [x] A second settle path for the veto fields keyed to the D-18 webhook POST, with its own
      (longer) timeout, separate from the calculated-property settle — discharged by the
      `settle_tier` (timeout 120) / `settle_veto` (timeout 900) split in
      `scripts/remediate_veto_companies.py` (Plan 01 Task 2).
- [x] Confirm/extend the offline guard asserting the never-write field set. Research established
      "T-40-22" is a Phase 40 plan-task label, not a test identifier — the real assertions are
      `test_backfill_never_writes_derived_output_properties` (line 169) and
      `test_backfill_build_updates_payload_never_contains_derived_fields` (line 234) in
      `tests/test_backfill_seed_company_scores.py`, extended by the new sibling assertions in
      `tests/test_remediate_veto_companies.py` (Plan 01 Task 3).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Arming both write surfaces | VETO-02 | Operator-only per-shell env gates (`ALLOW_N8N_ARM`, `ALLOW_HUBSPOT_RECORD_WRITES`) — never set by Claude, by standing project rule | Operator runs the exact armed command the plan hands them; Claude runs the disarmed dry-run before and the disarm + read-back after |
| Zero-result HubSpot search | VETO-03 | Requirement's own text demands it be provable from HubSpot alone with no script | Operator runs the verbatim search from `47-RESEARCH.md` §"VETO-03 acceptance search" |
| Legitimate residual Tier D is correct, not a failure | VETO-01 / D-16 | Requires judgment: a cleared false veto may reveal a genuine one (e.g. Simtech LED as `hardware_vendor`) | For any record still flagged, operator confirms the reason is a *different, correct* veto — never "Non-ANZ geography" |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references above — all four Wave 0 items now name the plan/task
      that discharges them (Plan 02 Task 1, 2026-08-11)
- [x] No watch-mode flags
- [x] Feedback latency < 60s offline
- [x] `nyquist_compliant: true` set in frontmatter — every row in the Per-Task Verification Map
      carries either an automated command (5 of 6 rows) or an explicit manual-only justification
      cross-referenced in the Manual-Only Verifications table below (VETO-03's script-free-by-design
      row)

**Approval:** pending
