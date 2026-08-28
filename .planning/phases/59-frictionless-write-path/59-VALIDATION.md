---
phase: 59
slug: frictionless-write-path
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-28
---

# Phase 59 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `59-RESEARCH.md` § Validation Architecture (lines 912-959).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 [VERIFIED] |
| **Config file** | none — no `pytest.ini` / `pyproject.toml` / `setup.cfg` `[pytest]` block exists anywhere in this repo [VERIFIED 2026-08-28]. There is therefore **no registered `live` marker**; the only live gating in the repo is a per-file `pytest.mark.skipif(os.getenv("RUN_LIVE_PARITY") != "true", ...)` in two files. |
| **Quick run command** | `.venv/bin/python -m pytest tests/<new_or_touched_test>.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest` (root) **and, separately,** `.venv/bin/python -m pytest operator-claude-plugin/tests` (the plugin suite has its own `conftest.py`) |
| **n8n suite** | `node --test tests/n8n/*.test.mjs` — glob form only (directory form broken on node 24). Not expected this phase. |
| **Estimated runtime** | root suite ~11s post-`89c9871`; plugin suite separate |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the file(s) touched.
- **After every plan wave:** Run BOTH full suites (root + plugin).
- **Before `/gsd-verify-work`:** Both suites green.
- **Live tests** (`RUN_LIVE_PARITY=true`): run **deliberately, never per-commit** — they cost real
  HubSpot / Anthropic calls.
- **Max feedback latency:** ~15 seconds for the quick command.

---

## Per-Task Verification Map

No `phase_req_ids` are mapped to this phase, so the traceability column is by DECISION id rather
than REQ id. The planner fills task ids in against this surface.

| Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|-----------|-------------------|-------------|--------|
| D-59-04 | credentials absent from `os.environ` by default | unit (new) | `.venv/bin/python -m pytest tests/test_conftest_credential_guard.py -x` (name illustrative) | ❌ W0 | ⬜ pending |
| D-59-04 | credentials **present** when `RUN_LIVE_PARITY=true` — the failure mode reproduced live during research | unit (new) | same file, opt-in case | ❌ W0 | ⬜ pending |
| D-59-04 | existing live tests still pass with real credentials when opted in | regression (live) | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py -k live -x` | ✅ `tests/test_scoring_parity.py` | ⬜ pending |
| D-59-06 | session-start note text is present in the shipped hook payload | contract (assert the file/JSON, not host stdout) | a test asserting `operator-claude-plugin/hooks/hooks.json` exists, declares a `SessionStart` matcher, and its payload contains the run-to-completion sentence | ❌ W0 | ⬜ pending |
| D-59-06 | note actually fires at session start | **manual** | one operator/Claude session start | — | ⬜ pending |
| D-59-07 | artifact survives a chunk-7-of-20 interruption | unit (new) | drive `dispatch_plan` with a stub transport, raise after N chunks, assert the durable file already holds N chunks' worth of written ids | ❌ W0 | ⬜ pending |
| D-59-07 | artifact reflects a revoked-but-completing run | integration (extends existing) | extend the file containing `test_a_revocation_midway_does_not_stop_a_running_dispatch` — **locate and read it before planning the extension** | ❌ W0 (extends existing file) | ⬜ pending |
| D-59-08 | `extraction.md` wording rewritten; the verbatim-survival sentence still present | contract (existing pattern) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_no_invention_structural.py -x` | ✅ exists | ⬜ pending |
| D-59-08 | each converted gate proposes rather than refuses, and a declined proposal still refuses | unit, per converted gate | one test per gate in the inventory | ❌ W0 | ⬜ pending |
| D-59-08 | a Claude-resolved value carries provenance saying so, never dressed as source-derived | contract | assert the provenance field on a resolved row | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — does not exist at repo root at all; D-59-04's entire deliverable
- [ ] A test asserting the D-59-04 fixture does **NOT** strip credentials under
      `RUN_LIVE_PARITY=true`. Research proved live that pytest runs autouse fixtures for a test
      whose `skipif` evaluates false, so an unconditional strip breaks the two existing live
      tests. Without this test the regression is silent until someone runs the live suite and
      gets a confusing auth error.
- [ ] A harness for D-59-07's crash-survival requirement — no existing test in this repo
      simulates a mid-loop process interruption. The closest existing pattern
      (`test_a_revocation_midway_does_not_stop_a_running_dispatch`) tests revocation, not
      artifact durability.
- [ ] `operator-claude-plugin/tests/test_no_invention_structural.py` must be read **in full**
      before D-59-08's `extraction.md` rewrite — it likely already asserts adjacent text the
      rewrite must keep passing.
- [ ] `operator-claude-plugin/hooks/` does not exist — D-59-06 is new plugin infrastructure.

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|----------|------------|-------------------|
| The session-start note actually appears | D-59-06 | Hook stdout cannot be asserted by pytest without invoking the Claude Code host | Start one session with the plugin installed; confirm the run-to-completion note appears once, non-blocking, before any send |
| GRANT-01 operator walk | — | **OUT OF SCOPE for Phase 59** (operator ruling 2026-08-28: code only). Remains a Phase 53 checkpoint, run separately, and requires the installed plugin to be updated to ≥0.20.0 first. | See `53-04-PLAN.md` Task 3 / `59-CONTEXT.md` § specifics |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references above
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s on the quick command
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
