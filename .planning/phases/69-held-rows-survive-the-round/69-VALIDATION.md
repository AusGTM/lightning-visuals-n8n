---
phase: "69"
slug: "held-rows-survive-the-round"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-07"
validated: "2026-09-08"
---

# Phase 69 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (`.venv/bin/python -m pytest`); `node --test` for the n8n harness (untouched by this phase) |
| **Config file** | `pytest.ini` (repo root); `operator-claude-plugin/tests/conftest.py` (`no_network`, `no_durable_writes`, stub transports) |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py operator-claude-plugin/tests/test_suggestion_declines_skill.py operator-claude-plugin/tests/test_suggest_contacts_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_disclosure_audit.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (2816 passed, 5 skipped) and `.venv/bin/python -m pytest -q --tb=short` (4574 passed, 154 skipped) and `node --test tests/n8n/*.test.mjs` (940 pass) |
| **Estimated runtime** | quick <1s; plugin suite ~14s; repo ~23s |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 69-01-01 | 01 | 1 | HELD-03 | — | operator confirm gate on the one-way multi-run document (D-69-03); no file modified | checkpoint:decision | n/a — operator answered `proceed (Recommended)` 2026-09-08, quoted in 69-01-SUMMARY § Decisions Made | — | ✅ resolved |
| 69-01-02 | 01 | 1 | HELD-02, HELD-03 | T-69-01, T-69-02 | store written 0600 via `_atomic_write_0600`; validate-before-write; forbidden-name refusal; `PARTITION_REASON_CODES` disjoint from `confidence.ALL_HOLD_CODES` | unit (tracer) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py -q` (32) incl. `test_partition_reason_codes_disjoint_from_all_hold_codes` | ✅ | ✅ green |
| 69-01-03 | 01 | 1 | HELD-03 | T-69-04 | `classify_read` honest on malformed/unknown-code files; accumulate-merge; `apply_action` — defer no-op, delete removal only, send removal only | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines.py -q` | ✅ | ✅ green |
| 69-02-01 | 02 | 2 | HELD-01, HELD-03 | T-69-06, T-69-07 | step 8's held fence persists allowlisted row fields only; an unkeyable decline is reported `unstorable`, never dropped silently; no `held_queue.`/`confidence.assess` call | composition (tracer) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py operator-claude-plugin/tests/test_skill_sequence_coverage.py -q` (23 + 11) | ✅ | ✅ green |
| 69-02-02 | 02 | 2 | HELD-03 | T-69-09 | step 9 names this run's declines AND the backlog, including on an empty dispatch; provenance rendered as data | composition | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggest_contacts_composition.py -q` | ✅ | ✅ green |
| 69-03-01 | 03 | 3 | HELD-03 | T-69-11 | drain skill carries NO grant/dispatch/pause fence of its own (fence-parse scan); `AUDIT` row present | composition (tracer) + ratchet | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines_skill.py operator-claude-plugin/tests/test_disclosure_audit.py -q` (23 + 24) | ✅ | ✅ green |
| 69-03-02 | 03 | 3 | HELD-03 | T-69-13 | `export_rows` via stdlib `csv.DictWriter` over `extraction.canonical_props()`, never `write_dispatch_csv`; emailless row exported, store bytes unchanged | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines_skill.py -q` incl. `test_export_writes_an_emailless_row_rather_than_refusing_it` | ✅ | ✅ green |
| 69-03-03 | 03 | 3 | HELD-03 | T-69-11, T-69-12, T-69-14 | drained `send` clears `extraction.validate` → `authorize_ungranted_send` → `dispatch` with a stub transport; ungranted send records zero transport calls; step-5 gates (`autonomy_enabled`, `plan_grant`, injected `pre_spend_pause`) run before the first transport call; removal only after the outcome is recorded | composition | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_suggestion_declines_skill.py -q` | ✅ | ✅ green |
| 69-CR-01 | review fix | — | HELD-03 | T-69-02 | `save()` refuses to overwrite an ANOMALOUS pre-existing file; step 8 catches the refusal into `save_refused`, step 9 reports it | unit + composition | `test_save_refuses_to_overwrite_a_preexisting_anomalous_file`; `test_a_save_refused_by_an_anomalous_preexisting_file_is_caught_not_raised` | ✅ | ✅ green |
| 69-CR-02 | review fix | — | HELD-03 | T-69-14 | `extraction.hold_emailless` runs before `send_domains`; a still-emailless entry is held, not crashed on | composition | `test_a_drained_send_on_a_still_emailless_no_email_entry_holds_it_instead_of_crashing`; `test_the_drain_send_fence_holds_emailless_rows_before_computing_send_domains` | ✅ | ✅ green |
| 69-WR-01 | review fix | — | HELD-03 | T-69-12 | non-send picks apply and save before the send fence; a failed send keeps the sitting's other decisions | composition | `test_non_send_picks_apply_and_save_before_the_send_fence_is_ever_reached`; `test_a_mixed_batch_keeps_non_send_decisions_when_the_send_fails` | ✅ | ✅ green |
| 69-* (guards) | all | all | HELD-02 | — | no n8n / builder drift; `held_queue.py` and `confidence.py` byte-identical to `6b16634`; no plugin script sleeps or loops; headless lane unchanged | git + static | `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` (empty); `git diff --quiet 6b16634 -- operator-claude-plugin/scripts/held_queue.py operator-claude-plugin/scripts/confidence.py`; `test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status` (1); `test_headless_grant_boundary.py` (5) | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Run 2026-09-08 (validate-phase): 32 + 23 + 23 + 11 + 24 + 5 + 1 passed across the named targets; guard files identical to `6b16634`; n8n drift empty.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The files RESEARCH § Wave 0 Gaps asked for were created inside the plans' own RED commits: `test_suggestion_declines.py` (store + HELD-02 disjointness), `test_suggestion_declines_skill.py` (drain skill + send composition), the `AUDIT` row in `test_disclosure_audit.py`, and the `COVERED` entries in `test_skill_sequence_coverage.py`. No separate Wave 0 was needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A LIVE drained `send` reaches HubSpot through the normal grant, ceiling and armed window, and the entry leaves the store only after the outcome is recorded | HELD-03 | Nothing is armed and no live write is permitted in this phase; every send test runs against a stub transport. The deliverable is SKILL.md prose Claude executes step by step; no harness runs a SKILL.md end to end. Also gated on the client release: `0.42.0` is committed and pushed, marketplace clone refreshed, installed copy still `0.40.0`. | After updating the plugin: run `/operator-claude-plugin:suggest-contacts` on one company whose only contact has no public email, confirm the person appears in the end-of-round backlog, then `/operator-claude-plugin:suggestion-declines`, supply the email, choose `send` with `allow_write_grants: true`. Expect the stated price line, a visible ~7s pause, the send, the step-9 account, and the person gone from `suggestion_declines.json`. Then `defer` a second person and confirm they reappear next batch. |
| A real club Secretary or an "Armidale …" company is reported `unstorable` (inherited forbidden-name markers) and the batch continues | HELD-03 | Known yield leak, deliberately out of scope; tracked in `.planning/todos/pending/2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md` | On the next live round that finds a Secretary, confirm the round reports one unstorable decline by name and reason, and every other decline is stored. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the checkpoint task is an operator gate, resolved and recorded)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none outstanding)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-08

## Validation Audit 2026-09-08
| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only (by nature of the deliverable) | 2 |
