---
phase: 57
slug: ceilings-refusal-before-start-and-post-run-proof
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-31
---

# Phase 57 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `57-RESEARCH.md` § Validation Architecture (lines 686-726).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`operator-claude-plugin/tests/` and root `tests/`) + Node built-in `node --test` (`tests/n8n/*.test.mjs`) |
| **Config file** | none committed — `tests/conftest.py` documents there is no `pytest.ini` / `pyproject.toml` / `setup.cfg` `[pytest]` block |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` **and** `node --test tests/n8n/*.test.mjs` (glob form only — directory form is broken on node 24) |
| **Estimated runtime** | ~30s quick / ~4–6 min full |

**Baseline at phase start:** root 3539 passed / 154 skipped (STATE.md, Phase 61 close).

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q`
- **After every plan wave:** `.venv/bin/python -m pytest -q` AND `node --test tests/n8n/*.test.mjs`
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~30 seconds (quick command)
- **Phase gate:** the ZoomInfo live-probe result (pass / fail / inconclusive) is reported in the phase summary **regardless of outcome** — it may not be resolvable from this repo alone (RESEARCH Assumption A3).

---

## Per-Task Verification Map

> Populated per task by the planner. The **Caller Path** column is not optional — Phase 59's
> defining lesson (ROADMAP.md:168-180) is that four gaps shipped past three green suites
> because every test drove a unit boundary rather than the integration path.

| Req ID | Behavior | Test Type | Automated Command | Caller path the test MUST drive |
|--------|----------|-----------|-------------------|----------------------------------|
| RUN-05 | A batch that would exhaust the allowance refuses BEFORE starting, with arithmetic, offering a smaller batch | unit + integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k ceiling -x` | `write_grant.plan_grant()` / `envelope()` themselves — the real path an operator's request reaches. NOT a bare arithmetic-comparison helper in isolation. |
| D-57-01 | Spending stops mid-batch; remainder held; run completes; grant closes `ceiling_breach` | integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k breach -x` | A REAL multi-chunk `chunking.dispatch_plan()` call with `stub_module_transport_factory` (mirroring `test_a_revocation_midway_does_not_stop_a_running_dispatch`'s 3-chunk idiom). Must assert `write_grant.record_send_outcome(...)` is **actually called as a consequence of that dispatch** — not merely that it accepts the right shape when called directly (Pitfall 1). |
| D-57-03 | Every backend `action` maps to the correct widened outcome, **including `enrich`** | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x` | `classify_item` direct unit test is appropriate (pure function). ALSO cover `report_enrichment.py`'s `_ACTION_TO_OUTCOME` for the 4 currently-unmapped actions (`update`, `review`, `research_failed`, `recompute_refused`) — verified drift between two vocabulary surfaces (Pitfall 3). |
| AFTER-01 | One report joining per-record outcome, held rows named individually, spend vs ceiling, disarm verdict | integration | new test driving the join against fixture `written_records` / `run_state` / `held_queue` artifacts on disk (`tmp_path` + `_patch_durable_dir` idiom) | Must assert the join **finds held rows by name** — a fixture entry with `hs_object_id: None` must still appear keyed by `row_id`, proving the `row_id` gap is closed, not merely that the function runs. |
| AFTER-03 | A gated (`write_blocked`) record must never read as completed | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -k gated` | Assert `classify_item({"action": "write_blocked", ...})` yields the NEW `gated` word (not the old `not_written` collapse) **and** that the operator-facing render uses distinct text for `gated` vs `written`. |
| G-4 | Report names which balances were readable / unreadable, and improves what is fixable | unit (Apollo/Lusha) + disarmed live probe (ZoomInfo) | `.venv/bin/python -m pytest operator-claude-plugin/tests -k backend_status_unknown_balance`; new disarmed probe script following `prove_async_recovery.py`'s gate idiom | Disclosure half already covered by `conftest.py:532-547`. The live-probe half must hit the REAL `Status Credit Request` → `ZoomInfo Usage` chain on the deployed instance, disarmed — the balance check never writes, so no `mode: propose` gate is needed. |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Integration-shaped test driving `write_grant.record_send_outcome` **from a real dispatch path** — today only the direct-call unit test exists (`test_write_grant.py:1507`). Land it red before any implementation task.
- [ ] Characterization test confirming `chunking.dispatch_plan`'s current `for` loop always completes all chunks — makes the later "stops early on breach" diff legible against a known baseline.
- [ ] ZoomInfo-specific `provider_error` response fixture — `conftest.py`'s existing `_balance()` / `backend_status_*` fixtures cover Apollo's 403 but not a ZoomInfo shape. Add only if G-4's fix needs a regression test.

*Framework and most fixtures already exist; these gaps are additive test cases, not new infrastructure.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ZoomInfo live balance behaviour | G-4 | Requires a live credentialled call to the deployed n8n instance; the 2026-08-25 `provider_error` observation predates the current (correct) `Accept` header code, so only a re-probe can say whether it persists | Run the new disarmed probe script against the deployed instance; record pass / fail / inconclusive in the phase summary either way. Read-only — never arms a write. |
| Apollo balance read | G-4 | Structurally unfixable in code — non-master API key, 403 by design | No test. Disclosed as a permanent blind spot per D-57-02; assert only that the disclosure text names it. |

---

## Prohibitions (validation-side)

- **No task in this phase may arm a write or spend a provider credit.** Every proof must be performable disarmed (`prove_scale_up_runtime.py` / `prove_async_recovery.py` are the templates).
- **No test may assert a ceiling behaviour by calling a helper the production path never calls.** That is the exact Phase 59 failure mode this map exists to prevent.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] Every ceiling/report behaviour's test drives the real caller path (Phase 59 lesson)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
