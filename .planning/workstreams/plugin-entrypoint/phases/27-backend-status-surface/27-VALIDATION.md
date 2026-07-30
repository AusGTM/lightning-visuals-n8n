---
phase: 27
slug: backend-status-surface
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `27-RESEARCH.md` §"Validation Architecture", corrected for the two
> requirement amendments research forced (D-07a/D-07b stuck redefinition, D-04a/D-04b per-node
> error reading). `/gsd-validate-phase` sets `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest for both halves; `node --test` for the pure JS module the builder inlines |
| **Config file** | repo root pytest config — plugin tests live under `operator-claude-plugin/tests/` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` then `node --test tests/n8n/backendStatus.test.mjs` |
| **Estimated runtime** | ~30–60 seconds quick; full suite longer |

**Note:** the repo's established invocation is `.venv/bin/python -m pytest` (system python lacks
deps) and `node --test <file>.test.mjs` in FILE form — the directory form is broken on the installed
node version. Do not substitute a bare `pytest`.

**Phase-wide constraint:** this phase is strictly read-only. No test, and no code any test exercises,
may mutate n8n, HubSpot, or any workflow JSON. The plugin suite's autouse network guard is widened in
27-03 to cover the GET verb, because every read this phase adds is a GET and the existing guard
covered only the POST-shaped entry points.

---

## Sampling Rate

- **After every task commit:** run the quick command (plus the node file test for 27-01)
- **After every plan wave:** run the full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 27-01 | 1 | STATUS-03, STATUS-06 | T-27-04 | a null count survives serialization as null, never 0; a non-2xx probe can never yield the reachable health state | unit (node) | `node --test tests/n8n/backendStatus.test.mjs` | ❌ created by task | ⬜ pending |
| 27-01-02 | 27-01 | 1 | STATUS-04 | T-27-01, T-27-03, T-27-05 | filter properties are schema-derived; every new node is credential-bound; the chain contains no write node | unit | `.venv/bin/python -m pytest tests/test_backend_status_wiring.py tests/test_hubspot_node_auth.py tests/test_node_name_uniqueness.py tests/test_write_gate_coverage.py -q` | ❌ created by task | ⬜ pending |
| 27-02-01 | 27-02 | 1 | STATUS-02 | T-27-09 | four named causes each reachable, deterministically, as one sentence with no code or stack | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_error_translation.py -q` | ❌ created by task | ⬜ pending |
| 27-02-02 | 27-02 | 1 | STATUS-02 | T-27-06, T-27-07, T-27-08 | unmatched → interpretation label + redacted raw text + admin attribution; operator attribution never returned across a sweep | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_error_guardrail.py -q` | ❌ created by task | ⬜ pending |
| 27-03-01 | 27-03 | 2 | STATUS-01 | T-27-10, T-27-11, T-27-13, T-27-15 | GET-only client; workflow body never returned; neither call carries the other's secret; the network guard bites on GET | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_n8n_read.py operator-claude-plugin/tests/test_status_tracer.py operator-claude-plugin/tests/test_transport_guard.py -q` | ❌ created by task | ⬜ pending |
| 27-03-01 | 27-03 | 2 | STATUS-03 | T-27-13, T-27-14 | balances arrive over the status endpoint; the plugin constructs no provider request; a dead endpoint degrades rather than raising | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_status_tracer.py -q` | ❌ created by task | ⬜ pending |
| 27-03-02 | 27-03 | 2 | STATUS-06 | T-27-12 | null and absent render as unknown; a genuine zero stays 0; refusal messages carry no configured value | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_status_unknown.py operator-claude-plugin/tests/test_config_gate.py -q` | ❌ created by task | ⬜ pending |
| 27-04-01 | 27-04 | 3 | STATUS-01, STATUS-04 | T-27-17, T-27-20 | no allowlist; never-run claimed only after a filtered read; stuck carries its age and threshold | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_status_all_workflows.py -q` | ❌ created by task | ⬜ pending |
| 27-04-02 | 27-04 | 3 | STATUS-02 | T-27-16, T-27-18 | a provider rejection inside a success-status run still surfaces; detail fetched only for a known failure | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_execution_errors.py -q` | ❌ created by task | ⬜ pending |
| 27-04-03 | 27-04 | 3 | STATUS-01, STATUS-04, STATUS-06 | T-27-16, T-27-19 | rendered failures carry no status code or traceback; null counts render unknown; the skill states it reads only | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_status_skill.py operator-claude-plugin/tests/test_plugin_manifest.py -q` | ❌ created by task | ⬜ pending |
| 27-05-01 | 27-05 | 4 | STATUS-05 | T-27-22, T-27-24, T-27-25 | store holds exactly two fields; extras rejected on save and stripped on load; expiry collected; path ignored by git | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_artifact_store.py -q` | ❌ created by task | ⬜ pending |
| 27-05-02 | 27-05 | 4 | STATUS-05, STATUS-06 | T-27-21, T-27-23 | dashboard carries the same data as the text; unknown stays unknown; the stamp comes from the mapping not render time | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_dashboard_parity.py -q` | ❌ created by task | ⬜ pending |
| 27-05-03 | 27-05 | 4 | STATUS-05 | T-27-21, T-27-23 | a refresh in a NEW session lands on the same URL; expiry clears the pointer; nothing was mutated | manual (blocking checkpoint) | n/a — platform Artifact publish (see Manual-Only Verifications) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers this phase's framework needs — `operator-claude-plugin/tests/
conftest.py` (fixtures, recording stub transport, autouse network guard) and the repo's pytest and
`node --test` suites all already exist and are green.

Two infrastructure gaps are closed inside the plans that need them, rather than in a separate Wave 0
plan, because each is a one-file change owned by the first task that depends on it:

- [ ] **The autouse network guard does not cover GET.** `conftest.py` patches the POST-shaped entry
      points only. Every read this phase adds is a GET, so a plugin test that forgot its stub would
      reach the live n8n instance. Widened in **27-03 Task 1**, in the same commit that introduces
      the first GET, alongside a recording GET stub and a stub response carrying a status code.
- [ ] **No status-shaped fixture mapping exists.** Created in **27-04 Task 3** and reused by
      **27-05 Task 2**, so the text and dashboard renderers are compared against one another rather
      than each against its own expectations.

Every other test file listed in the map is created by the task that owns it, in the repo's
established pattern.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A dashboard refresh re-publishes to the same URL, including from a session that did not create it | STATUS-05 (D-09a) | The Artifact publish mechanism is a platform tool call; this repository's suite cannot invoke it, and cross-session sameness is by definition not observable inside one process | Publish the dashboard, refresh it in the same conversation, then ask again in a brand-new conversation and confirm the URL is unchanged — see 27-05 Task 3 for the full seven-step script |
| An expired identifier is garbage-collected on the next plugin open | STATUS-05 (D-09b) | Requires the real skill-start path in a real session; the store's expiry logic itself IS automated in 27-05 Task 1 | Set the expiry key to zero days, open the skill, confirm the state file is gone and the next request mints a fresh identifier |
| An unreadable provider balance shows as unknown on the published dashboard | STATUS-06 | The rendering is automated; only its appearance on the live published surface is not | Confirm the provider whose key is not a master key reads unknown on the dashboard, not zero and not healthy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a documented manual justification
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
