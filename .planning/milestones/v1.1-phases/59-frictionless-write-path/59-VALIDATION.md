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
than REQ id. **Owners filled in by the planner, 2026-08-28** (6 plans, 5 waves — see
`59-0*-PLAN.md`).

| Decision | Behavior | Test Type | Owner | Automated Command | File Exists | Status |
|----------|----------|-----------|-------|-------------------|-------------|--------|
| D-59-04 | credentials absent from `os.environ` by default | unit (new) | **59-02 T1** | `.venv/bin/python -m pytest tests/test_conftest_credential_guard.py -x` | ❌ W0 | ⬜ pending |
| D-59-04 | credentials **present** when `RUN_LIVE_PARITY=true` — the failure mode reproduced live during research | unit (new), **subprocess** | **59-02 T1** | `RUN_LIVE_PARITY=true ANTHROPIC_API_KEY=not-a-real-key .venv/bin/python -m pytest tests/_credential_guard_probe.py -q` — must be a subprocess: the autouse fixture decides before any test body runs | ❌ W0 | ⬜ pending |
| D-59-04 | existing live tests still pass with real credentials when opted in | regression (live) | **59-02 T2 — DEFERRED, not performed** | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py -k live -x` (costs real HubSpot/Anthropic calls). 59-02 T2 runs `--collect-only` on both live-gated files instead and records the deferral explicitly | ✅ `tests/test_scoring_parity.py` | ⬜ pending |
| D-59-06 | session-start note content is present and correct | contract (**subprocess, stronger than a file assertion**) | **59-04 T1** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_session_start_hook.py -x` — runs `bash hooks/session-start.sh` and asserts stdout carries all three facts, plus `hooks.json` shape and a no-question-mark property | ❌ W0 | ⬜ pending |
| D-59-06 | note actually fires at session start (DELIVERY by the host) | **manual** | **59-04 T2 records it as unperformed** | one operator/Claude session start — content is automated above, only host delivery is unverified | — | ⬜ pending |
| D-59-07 | artifact survives a mid-loop interruption (chunk 3 of 5) | unit (new) | **59-01 T1 (TRACER)** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x` — stub transport raises a bare `RuntimeError` (deliberately not a type the loop catches) so it escapes as a process interruption would | ❌ W0 | ⬜ pending |
| D-59-07 | artifact reflects a revoked-but-completing run | integration (extends existing) | **59-01 T2** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -x` — a NEW sibling test; `test_a_revocation_midway_does_not_stop_a_running_dispatch` stays byte-identical | ❌ W0 (extends `test_write_grant.py`) | ⬜ pending |
| D-59-07 | the retired pre-emptive disclosure is gone and cannot return | contract (re-pointed) | **59-03 T1 + T2** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -x` — each re-point adds a NEGATIVE assertion | ✅ both exist | ⬜ pending |
| D-59-08 | every operator-facing refuse-and-stop gate is inventoried and decided | document | **59-05 T1**, closed out by **59-06 T3** | `test -f .planning/phases/59-frictionless-write-path/59-GATE-INVENTORY.md` + the difficulty-dismissal grep at 0 | ❌ W0 | ⬜ pending |
| D-59-08 | the identity gate reports resolvable failures instead of only rejecting | unit (new) | **59-05 T2** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction_resolvable.py -x` | ❌ W0 | ⬜ pending |
| D-59-08 | a Claude-resolved value carries provenance from a CLOSED vocabulary; an unrecognised source rejects | contract (extends existing) | **59-05 T2** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_no_invention_structural.py -x` — the forbidden-name list is EXTENDED, never relaxed | ✅ exists (read in full first) | ⬜ pending |
| D-59-08 | `extraction.md` rewritten; the gap-filling sentence survives verbatim | contract (grep) | **59-05 T3** | `grep -c "Never fill a gap to make a row satisfy the identity rule" operator-claude-plugin/skills/contact-upload/extraction.md` ≥ 1 | ✅ exists | ⬜ pending |
| D-59-08 | enrichment-lane refusals name a legitimate resolution source | unit (extends existing) | **59-06 T1** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_enrichment_envelope.py -x` | ❌ W0 (extends existing file) | ⬜ pending |
| D-59-08 | the grant lane's empty-record-set dead end is resolvable, and the control did not move | unit + structural | **59-06 T2** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -x` — includes a structural test that no HubSpot search call was added to `write_grant.py` | ❌ W0 (extends existing file) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Decisions with no implementing task, by design:** D-59-01 (the walk — run, recorded, and
ruled OUT of this phase), D-59-02 (a scoping statement pointing at Phases 55/56/57), D-59-03
(deferred to Phase 60), D-59-05 (`ALLOW_REVIEW_SUBMIT` already removed). These are records,
completed work and deferrals — not unimplemented scope.

---

## Wave 0 Requirements

Each gap is OWNED by a named plan/task (planner, 2026-08-28) — the quality gate checks this.

- [ ] **OWNER: 59-02 Task 1.** `tests/conftest.py` — does not exist at repo root at all;
      D-59-04's entire deliverable.
- [ ] **OWNER: 59-02 Task 1.** A test asserting the D-59-04 fixture does **NOT** strip
      credentials under `RUN_LIVE_PARITY=true`. Research proved live that pytest runs autouse
      fixtures for a test whose `skipif` evaluates false, so an unconditional strip breaks the
      two existing live tests. Without this test the regression is silent until someone runs
      the live suite and gets a confusing auth error. Implemented as a **subprocess** run of
      `tests/_credential_guard_probe.py`, because the autouse fixture has already decided by
      the time any in-process test body runs.
- [ ] **OWNER: 59-01 Task 1 (the TRACER).** A harness for D-59-07's crash-survival requirement
      — no existing test in this repo simulates a mid-loop process interruption. The closest
      existing pattern (`test_a_revocation_midway_does_not_stop_a_running_dispatch`) tests
      revocation, not artifact durability, and stays byte-identical; 59-01 Task 2 adds a
      sibling test for the revoked-run case rather than editing it.
- [ ] **OWNER: 59-05 Task 2 `read_first`.**
      `operator-claude-plugin/tests/test_no_invention_structural.py` must be read **in full**
      before D-59-08's `extraction.md` rewrite. Confirmed during planning: its final test
      structurally forbids any function in `extraction.py` whose name suggests it resolves or
      fills a value, which is why D-59-08's conversion is CLASSIFICATION rather than filling.
      That test is EXTENDED to cover the new resolution surface, never relaxed.
- [ ] **OWNER: 59-04 Task 1.** `operator-claude-plugin/hooks/` does not exist — D-59-06 is new
      plugin infrastructure. Location confirmed correct by
      `test_plugin_manifest.py:40-45`, whose own assertion message states `hooks/` belongs at
      the plugin root.

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
