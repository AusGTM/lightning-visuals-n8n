---
phase: 33
slug: durable-operator-state
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `33-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (no `pytest.ini`/`pyproject.toml` under `operator-claude-plugin/`; `tests/conftest.py` puts `scripts/` on `sys.path` and installs an autouse `no_network` guard) |
| **Config file** | none — `tests/conftest.py` is the shim |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_config_gate.py operator-claude-plugin/tests/test_artifact_store.py operator-claude-plugin/tests/test_durable_paths.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Estimated runtime** | ~2 seconds (plugin suite currently 911 passed / 5 skipped in 1.27s) |

**Do not use a bare `pytest`** — the system Python lacks the deps. Project memory
`test-suite-run-commands` is explicit on this.

---

## Sampling Rate

- **After every task commit:** the quick run command above
- **After every plan wave:** full plugin suite
- **Before `/gsd-verify-work`:** full plugin suite green, plus root suite (`.venv/bin/python -m
  pytest -q`, baseline 1792/6) and node (`node --test tests/n8n/*.test.mjs`, baseline 550) to
  prove no cross-suite regression
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

Task IDs are assigned by the planner; this maps the ROADMAP success criteria to the layer and
command that proves each. Criterion 5 is a **methodology constraint on how the others are
tested**, not a separate behavior — it is satisfied when every row below that says "entrypoint"
actually drives a subprocess.

| Criterion | Behavior | Threat Ref | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|
| 1 — resolution order + free sibling migration | 5-step order resolves at every priority; sibling scan migrates on a simulated update | secret-at-rest | **entrypoint** (subprocess) | `pytest operator-claude-plugin/tests/test_config_gate.py -k durable -x` | ❌ W0 — extend `_run_cli` | ⬜ pending |
| 2 — dashboard pointer, identical treatment | `artifact_store` resolves/migrates through the same `durable_paths` module | — | **entrypoint** (subprocess) | `pytest operator-claude-plugin/tests/test_artifact_store.py -k durable -x` | ❌ W0 — existing tests are unit-level (`path=`) | ⬜ pending |
| 3 — `0600` + verify-then-delete | migrated file mode is `0o600`; old copy removed ONLY after the new one reads back; the CURRENT install's copy is never removed | secret-at-rest | unit + entrypoint | `pytest operator-claude-plugin/tests/test_durable_paths.py -x` | ❌ W0 — new file | ⬜ pending |
| 4 — `initialize` reports the real path | `init_check` names the durable path; a no-op run emits NO migration language | — | unit | `pytest operator-claude-plugin/tests/test_init_check.py -x` | existing file, new cases | ⬜ pending |
| 5 — entrypoint-layer pinning | every assertion above runs through the CLI, not the bare resolver | — | (methodology) | covered by rows 1–3 | — | ⬜ pending |
| 6 — no regression, no secret leak | legacy same-install path still resolves; suites green; no secret in any output or log | secret-at-rest | regression + unit | full suite + a migration-path generalization of `test_no_configerror_message_ever_contains_the_secret_value` | existing pattern — extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `operator-claude-plugin/scripts/durable_paths.py` — the shared resolver; does not exist yet
- [ ] `operator-claude-plugin/tests/test_durable_paths.py` — unit tests for the version-key parser
      and the atomic-write helper, independent of the subprocess tests
- [ ] Extend `tests/test_config_gate.py::_run_cli` to accept an `env=` override and a
      multi-version cache layout — today it takes only `(config_json, tmp_path)`
- [ ] A subprocess-level entrypoint test for `artifact_store.py`'s `__main__` — today's
      `test_artifact_store.py` calls `load()`/`save()` with an explicit `path=`, which is exactly
      the unit-level style criterion 5 warns is insufficient for default-path behavior

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Writing into `~/.claude/plugins/data/<id>/` does not trigger a "sensitive location" permission prompt on this host | Criterion 1/3 (migration must be silent and automatic) | Research Open Question 1 cites anthropics/claude-code#41156 reporting such a prompt at the Bash-tool layer. **Not independently reproduced this session — MEDIUM confidence.** A prompt would defeat the phase's entire purpose (an automatic migration that stops to ask is a terminal step by another name) | After execution, perform one real migration on this host and observe whether any prompt appears. Record what was observed verbatim. **Do not change any permission setting to make it pass** — if a prompt fires, that is a finding about the chosen location, and the env override / legacy fallback is the mitigation |

Consistent with how Phases 27–32 gated on a runbook (RB-4, RB-7, RB-8, RB-9) rather than
automated tests alone for host-boundary behavior.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] Manual verification above observed and recorded
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
