---
phase: "65"
slug: "round-empty-re-entry-keyed-on-the-cause"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-07"
validated: "2026-09-07"
---

# Phase 65 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (`.venv/bin/python -m pytest`) |
| **Config file** | `pytest.ini` (repo root); plugin tests under `operator-claude-plugin/tests/` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py operator-claude-plugin/tests/test_suggest_contacts_composition.py operator-claude-plugin/tests/test_preingest_merge.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (2565 passed, 5 skipped) |
| **Estimated runtime** | quick ~2s; full plugin suite ~60s |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 65 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 65-01-01 | 01 | 1 | LADDER-03 | — | fail-closed `cause: "unknown"` spends nothing | unit + composition | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py -k round_outcome -q` (49) | ✅ | ✅ green |
| 65-01-02 | 01 | 1 | LADDER-03 | — | terminal classify never returns a re-entry | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts.py::test_round_outcome_terminal_call_never_returns_a_reentry -q` (24 cases) | ✅ | ✅ green |
| 65-01-03 | 01 | 1 | LADDER-04, LADDER-05 (offline wiring) | — | no `while` in any plugin script; refusal terminal by second route; no cap reset | unit + static scan | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status operator-claude-plugin/tests/test_suggest_contacts_composition.py -q` | ✅ | ✅ green |
| 65-CR-01 | review fix | — | LADDER-03 | — | all-companies-empty round reports cause instead of crashing on `mint_row_ids([])` | composition | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py::test_the_documented_round_pipeline_never_crashes_when_every_company_finds_nobody -q` | ✅ | ✅ green |
| 65-02-01 | 02 | 2 | RICH-04 | — | widened allowlist is policy-derived (`promote_to_canonical: true` only); shipped config byte-identical to repo | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -q` + `cmp -s config/field_policy.yaml operator-claude-plugin/config/field_policy.yaml` | ✅ | ✅ green |
| 65-02-02 | 02 | 2 | RICH-04 | — | `write_dispatch_csv` still raises on a genuinely unknown key after the strip; held/remainder queues unchanged | unit (both callers traced) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -q` | ✅ | ✅ green |
| 65-02-03 | 02 | 2 | RICH-04 (SAFE-01) | — | per-field `min_confidence` gate on widened keys; present value never overwritten | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py::test_a_present_widened_key_is_never_overwritten_and_records_a_conflict -q` | ✅ | ✅ green |
| 65-* (parity) | 01, 02 | 1, 2 | — | — | no n8n JSON or builder drift | git | `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` (empty) | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Run 2026-09-07 (validate-phase): 271 passed across the seven plan-declared test targets; `cmp` OK; n8n drift empty.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No Wave 0 stubs were needed;
every task was TDD (RED commit then GREEN commit) against the existing pytest layout.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Search fallback fires in a REAL round (`cause: no_people_found` on a live company) | LADDER-05 (live reachability) | Needs a live company whose ladder walk finds nobody; both live rounds to date found people (`none_classified`, `all_held_on_email`). Offline wiring is automated (65-01-03). Checkbox deliberately NOT ticked by this phase (65-01-SUMMARY disposition). | Next live UAT sitting: run `260904-QUICK-UAT.md` test 8 against a company with an empty ladder walk; confirm `rounds[].outcome.cause == "no_people_found"` and that `eligible_after_ladder` is consulted next. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none)
- [x] No watch-mode flags
- [x] Feedback latency < 65s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-07

## Validation Audit 2026-09-07
| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only (by disposition) | 1 |
