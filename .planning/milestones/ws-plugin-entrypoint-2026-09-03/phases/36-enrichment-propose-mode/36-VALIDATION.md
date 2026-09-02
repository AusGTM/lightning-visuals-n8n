---
phase: 36
slug: enrichment-propose-mode
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `36-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo `tests/`, plugin `operator-claude-plugin/tests/`) + Node built-in `node:test` (`tests/n8n/*.test.mjs`) |
| **Config file** | none — default discovery (no `pytest.ini` / `pyproject.toml` / `setup.cfg` / root `conftest.py`) |
| **Quick run command** | `.venv/bin/python -m pytest <touched_test_file> -q` · `node --test tests/n8n/<touched>.test.mjs` |
| **Full suite command** | `.venv/bin/python -m pytest -q` · `node --test tests/n8n/*.test.mjs` · `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Estimated runtime** | ~120 seconds for all three suites |

**Baselines to beat:** repo pytest `1933 passed / 6 skipped` · plugin pytest `1052 passed / 5 skipped` ·
node `553 pass` · `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → `0`.

**Command forms are exact.** System python lacks the deps; the `node --test` directory form is broken
on node 24 — FILE glob only.

---

## Sampling Rate

- **After every task commit:** targeted file re-run — `.venv/bin/python -m pytest <touched_test_file> -q`
  and/or `node --test tests/n8n/<touched>.test.mjs`
- **After every plan wave:** `.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs`
- **Before `/gsd-verify-work`:** all three suites green AND arming grep `0`
- **Max feedback latency:** 30 seconds (targeted run)

---

## Per-Task Verification Map

Seeded from the nine Definition-of-Done items in `36-CONTEXT.md` §8. Task IDs are filled by the
planner; the criterion → command mapping below is the contract each task must satisfy.

| DoD | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| 1 | `mode:"propose"` returns `properties`+`match`, `row_id` echoed, writes nothing regardless of `WRITE_SAFETY_DEFAULTS` | unit (structural, Decide Action jsCode) | `.venv/bin/python -m pytest tests/test_cloud_write_path.py -q` | ✅ extend | ⬜ pending |
| 2 | `mode` absent behaves byte-identically to today | regression (absence of new failures) | `.venv/bin/python -m pytest -q` | ✅ existing | ⬜ pending |
| 3 | Mixed-lane batch emits each row exactly once | unit (structural, `lane` filter) | new/extended enrichment lane-dedup assertion | ❌ W0 | ⬜ pending |
| 4 | `CONTAINS_TOKEN` hit on wrong surname yields zero candidates | unit (pure fn `mediumCandidates`) | `node --test tests/n8n/matchProposal.test.mjs` | ❌ W0 | ⬜ pending |
| 5 | Oversize `events` array refused whole, nothing enriched | unit (pure fn + structural) | `node --test tests/n8n/providerSelection.test.mjs` | ✅ extend | ⬜ pending |
| 6 | Emailless INGEST row no longer sets `lookup_failed`; siblings keep `create` | unit (structural, ingest lane) | `.venv/bin/python -m pytest tests/test_ingest_search_contract.py -q` | ✅ extend | ⬜ pending |
| 7 | No arming anywhere | smoke (shell) | `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → `0` | ✅ existing | ⬜ pending |
| 8 | Suites green vs baselines (~+30 node, ~+15 pytest) | full suite | all three commands above | ✅ existing | ⬜ pending |
| 9 | Rebuilt, deployed disarmed, active workflows bounced, read back | **backstop — live/manual** | operator-executed via `!`; `scripts/deploy_n8n_workflows.py` is denied to agents in every form | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/n8n/matchProposal.test.mjs` — new file; covers DoD 4 plus `laneOf()` / `summarizeMatch()`
- [ ] Mixed-lane emit-once assertion (new or extended topology test) — covers DoD 3
- [ ] `tests/n8n/providerSelection.test.mjs` extension — `mode` envelope field + events-array refusal (DoD 5)
- [ ] `tests/test_row_carry.py` — remove the two `ROW_REPLACING_BY_DESIGN` waivers in the SAME commit as
      the `Skip (NoOp)` / `Unsupported Object Type` Code-node conversion, else
      `test_every_row_replacing_entry_is_still_a_real_node_somewhere` fails
- [ ] `tests/test_fetch_by_id_topology.py` — amend the pinned `IF Bare Event` false-lane assertion
      (now targets `IF Has Email`), with the reason inline

*Framework itself is fully present — no install needed.*

---

## Manual-Only Verifications

| Behavior | DoD | Why Manual | Test Instructions |
|----------|-----|------------|-------------------|
| Rebuild → deploy disarmed → bounce every active workflow → read back `--expectation disarmed` | 9 | `scripts/deploy_n8n_workflows.py` is denied to agents by the permission classifier in every form | Hand the operator the one-liner from `35-CONTEXT.md` §6; they run it via `!`. The bounce (`n8n_control.set_active`) and the read-back DO pass and may be run by the agent. |
| First live `mode:"propose"` run — proves Lusha name+company on the cloud endpoint and the `CONTAINS_TOKEN` operator, both `[ASSUMED]` offline | 1, 3 | Requires the live tenant + provider credits | Operator walk after the disarmed deploy; per-provider errors already surface in the response body. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
