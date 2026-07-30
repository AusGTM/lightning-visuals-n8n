---
phase: 23
slug: walking-skeleton-plugin-shell-tabular-dispatch
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `23-RESEARCH.md` §"Validation Architecture". The planner fills the
> per-task map; `/gsd-validate-phase` sets `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo already uses it; plugin carries its own `requirements.txt`) |
| **Config file** | repo root pytest config — plugin tests live under `operator-claude-plugin/tests/` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~30–60 seconds quick; full suite longer |

**Note:** the repo's established invocation is `.venv/bin/python -m pytest` (system python lacks
deps) and `node --test tests/n8n/*.test.mjs` in file form — the directory form is broken on the
installed node version. Do not substitute a bare `pytest`.

---

## Sampling Rate

- **After every task commit:** run the quick command
- **After every plan wave:** run the full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

*Planner fills this from the PLAN.md task IDs. Every requirement below must appear at least once.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 23-XX-XX | — | — | INGEST-02 | — | — | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | STRUCT-01 | — | canonical props only reach the wire | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | PREVIEW-01 | — | — | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | PREVIEW-04 | — | decline sends nothing | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | DISPATCH-01 | — | correct auth header + body encoding | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | DISPATCH-03 | T-23-01 | disarmed by default; approved batch still not sent | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | PLUGIN-01 | — | — | manual | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | PLUGIN-02 | T-23-02 | no secret in source, none shown to operator | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | PLUGIN-03 | T-23-03 | refuses before any network call when unconfigured | unit | — | ❌ W0 | ⬜ pending |
| 23-XX-XX | — | — | PLUGIN-04 | — | no backend file modified by the client | unit | — | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `operator-claude-plugin/tests/` — test package root with stubs for the ten requirement IDs
- [ ] `operator-claude-plugin/tests/conftest.py` — shared fixtures: a sample CSV, a sample XLSX,
      a fake config, and a stub HTTP transport so no test ever reaches the network
- [ ] `operator-claude-plugin/requirements.txt` — plugin-local deps (research confirmed `openpyxl`,
      `requests`, `PyYAML` are already pinned and proven in this repo for these exact jobs)

**Critical Wave 0 constraint:** the dispatch tests must never perform a real POST. The arming
guard is the thing under test — a test that accidentally arms and sends is worse than no test.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Plugin installs and is invocable conversationally in the Claude Desktop Code tab | PLUGIN-01 | Requires the actual Desktop GUI install flow; no automated harness exists | Install the plugin from the Desktop app, start a session, confirm the skill auto-triggers on a natural request and is also reachable as `/plugin-name:skill-name` |
| Operator-attached file resolves to a readable path | INGEST-02 (D-14a) | Unconfirmed by documentation; an open upstream issue describes this gap | **Early smoke test, before any attachment plumbing is built.** Attach a CSV in a Code-tab session and confirm whether a script can read it by path. If not, the `@mention` path is the only mechanism and no attachment code is written |
| Armed end-to-end dispatch lands rows in HubSpot | DISPATCH-01, and D-16's `allow_create` fix | Requires live n8n + HubSpot and burns real writes | Run one armed canary against a test record after the `allow_create` overlay fix lands; confirm a net-new row actually creates rather than falling to `needs_review` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
