---
phase: "68"
slug: "state-the-price-and-keep-moving"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-07"
validated: "2026-09-07"
---

# Phase 68 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (`.venv/bin/python -m pytest`); `node --test` for the n8n harness (unaffected by this phase) |
| **Config file** | `pytest.ini` (repo root); `operator-claude-plugin/tests/conftest.py` fixtures |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_pre_spend_pause.py operator-claude-plugin/tests/test_headless_grant_boundary.py operator-claude-plugin/tests/test_implicit_approval_contract.py operator-claude-plugin/tests/test_interrupt_semantics.py operator-claude-plugin/tests/test_disclosure_audit.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py operator-claude-plugin/tests/test_enrich_skill_contract.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (2646 passed, 5 skipped) and `node --test tests/n8n/*.test.mjs` (940 pass) |
| **Estimated runtime** | quick ~1s; full plugin suite ~60s |

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
| 68-01-01 | 01 | 1 | FLOW-01 | — | pause is DI'd; no test performs a real wait; `watch.py` sole `time` importer | unit + static scan | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_pre_spend_pause.py -q` (5) + `test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` | ✅ | ✅ green |
| 68-01-02 | 01 | 1 | FLOW-01 | — | operator decision gate (`prose-and-pin`), not a test target | checkpoint:decision | n/a — resolved by operator 2026-09-07, recorded in 68-01-SUMMARY | — | ✅ resolved |
| 68-01-03 | 01 | 1 | FLOW-01 | — | implicit-open path unreachable from headless/cron lane | structural (AST/source scan) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_headless_grant_boundary.py -q` (3) + `git diff --quiet f0ab716 -- operator-claude-plugin/scripts/scheduled_arm.py operator-claude-plugin/scripts/n8n_arming.py` | ✅ | ✅ green |
| 68-02-01 | 02 | 2 | FLOW-02 | — | operator decision gate (`price-state-pause-open`) | checkpoint:decision | n/a — resolved by operator 2026-09-07, recorded in 68-02-SUMMARY | — | ✅ resolved |
| 68-02-02 | 02 | 2 | FLOW-01, FLOW-02 | — | `plan_grant → state → pause → open_grant` order pinned; two-phase ask literal byte-identical; `CEILING_OVER`/`CapRefused` stay refusals | prose contract | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_implicit_approval_contract.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -q` | ✅ | ✅ green |
| 68-02-03 | 02 | 2 | FLOW-01, FLOW-03 | — | same order at all four sites; inline grant offer everywhere; `send_domains` reused at open and dispatch (WR-01) | prose contract | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_implicit_approval_contract.py operator-claude-plugin/tests/test_enrich_skill_contract.py -q` (34) | ✅ | ✅ green |
| 68-03-01 | 03 | 3 | FLOW-05 | — | interrupt refuses NEXT send; running dispatch finishes its chunks (D-59-06) stated at contact-upload | prose contract | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_interrupt_semantics.py -q` | ✅ | ✅ green |
| 68-03-02 | 03 | 3 | FLOW-05 | — | same statement at the three remaining sites | prose contract | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_interrupt_semantics.py -q` (18) | ✅ | ✅ green |
| 68-03-03 | 03 | 3 | FLOW-04 | — | 10-skill audit table pinned; preserved decision points (review-triage per-record, backend-control mutations) still present; `pre_spend_pause`/`open_grant` absent from read-only skills | ratchet | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_disclosure_audit.py -q` (21) | ✅ | ✅ green |
| 68-CR-01..03 | review fix | — | FLOW-01, FLOW-03, FLOW-04 | — | WR-01 named `send_domains`; WR-02 specific `CapRefused` cause + next step; WR-03 honest docstring | prose contract | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_implicit_approval_contract.py operator-claude-plugin/tests/test_disclosure_audit.py -q` | ✅ | ✅ green |
| 68-* (parity) | all | all | — | — | no n8n / builder drift; `write_grant.py`, `suggest_contacts.py`, `scheduled_arm.py`, `n8n_arming.py` byte-identical to `f0ab716` | git | `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` (empty); `git diff --quiet f0ab716 -- <the four scripts>` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Run 2026-09-07 (validate-phase): 149 passed across the nine plan-declared targets; pinned scripts identical to `f0ab716`; n8n drift empty; `import time` present only in `watch.py`.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The five new test files RESEARCH § Wave 0 Gaps asked for were created inside the plans' own RED commits (`test_pre_spend_pause.py`, `test_headless_grant_boundary.py`, `test_implicit_approval_contract.py`, `test_interrupt_semantics.py`, `test_disclosure_audit.py`); no separate Wave 0 was needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A LIVE round with no grant open prices, states, pauses ~7s, opens the grant and proceeds without a question; the operator can interrupt inside the pause | FLOW-01, FLOW-02, FLOW-03 | The deliverable is SKILL.md prose that Claude executes step by step; the tests pin the prose and the call order, but no automated harness executes a SKILL.md end to end. Also gated on a plugin release: `plugin.json` is still `0.40.0`, so the installed marketplace clone carries the old two-phase ask. | After the release lands: run `/suggest-contacts` (or `/enrich-before-ingest`) on a small batch with `allow_write_grants: true` and no grant open. Expect the stated line (incl. the unsampled-ceiling sentence if the verdict is `unknown`), a visible ~7s pause, then the grant opening and the round proceeding. Interrupt once inside the pause and confirm the next send is refused while nothing already dispatched is cut short. |
| A newly introduced halting question in an already-converted skill is caught | FLOW-04 | `test_disclosure_audit.py` pins known-good text and skill coverage only; it does NOT scan for newly added interrogatives (WR-03, admitted in its docstring). A heuristic scan was tried and rejected as too noisy against preserved decision-point language. | On every future SKILL.md edit to a converted skill (Phase 67 in particular), re-read the edited step against D-68-09's test: a statement the operator cannot act on differently must not end in a question or a wait for a reply. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (checkpoint tasks are operator gates, resolved and recorded)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none outstanding)
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
| Manual-only (by nature of the deliverable) | 2 |
