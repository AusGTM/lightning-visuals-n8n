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
| 23-01-01 | 23-01 | 1 | DISPATCH-01 | T-23-04, T-23-05 | committed artifact stays disarmed; create decision reads the overlayable constant | unit | `.venv/bin/python -m pytest tests/test_write_gate_coverage.py tests/test_enabled_build_invariants.py tests/test_row_carry.py tests/test_create_payload_identity.py tests/test_cloud_write_path.py -q` | ✅ exists | ⬜ pending |
| 23-01-02 | 23-01 | 1 | DISPATCH-01 | T-23-04, T-23-06 | disarmed routes net_new to review; overlay routes it to create; allowlist still bounds the write | unit | `node --test tests/n8n/contactCreateGateFlow.test.mjs && .venv/bin/python -m pytest tests/test_contact_create_overlay.py -q` | ❌ W0 | ⬜ pending |
| 23-02-01 | 23-02 | 1 | INGEST-02 | T-23-07, T-23-08 | file-handoff mechanism confirmed before any plumbing is built | manual | n/a — Code-tab smoke test (see Manual-Only Verifications) | n/a | ⬜ pending |
| 23-03-01 | 23-03 | 1 | PLUGIN-02 | T-23-02 | real config path is un-committable; example carries placeholders only | unit | `git check-ignore -q operator-claude-plugin/config/operator.local.json && python3 -c "import json;d=json.load(open('operator-claude-plugin/config/operator.local.example.json'));assert set(('n8n_url','webhook_secret')) <= set(d)"` | ❌ W0 | ⬜ pending |
| 23-03-02 | 23-03 | 1 | PLUGIN-04 | T-23-01 | every plugin test is network-stubbed by an autouse guard | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ W0 | ⬜ pending |
| 23-04-01 | 23-04 | 2 | INGEST-02 | T-23-10 | headers read verbatim; XLSX re-serialized to CSV without remapping | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_config_gate.py operator-claude-plugin/tests/test_dispatch_multipart.py -q` | ❌ W0 | ⬜ pending |
| 23-04-01 | 23-04 | 2 | STRUCT-01 | T-23-10 | the file goes over the wire as read — no client-side mapping | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_dispatch_multipart.py -q` | ❌ W0 | ⬜ pending |
| 23-04-01 | 23-04 | 2 | DISPATCH-01 | T-23-09 | multipart field `data`, header `X-Enrichment-Secret`, CSV bytes, finite timeout | unit (stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_dispatch_multipart.py -q` | ❌ W0 | ⬜ pending |
| 23-04-01 | 23-04 | 2 | DISPATCH-03 | T-23-01 | `armed` has no default; unarmed path leaves the stub's call log empty | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_dispatch_multipart.py -q` | ❌ W0 | ⬜ pending |
| 23-04-01 | 23-04 | 2 | PLUGIN-03 | T-23-03 | refuses before the transport exists; no key, no raw socket error | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_config_gate.py -q` | ❌ W0 | ⬜ pending |
| 23-04-02 | 23-04 | 2 | PLUGIN-01 | — | manifest + one skill; no duplicate `commands/` entry point | unit (static) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_plugin_manifest.py -q` | ❌ W0 | ⬜ pending |
| 23-04-03 | 23-04 | 2 | PLUGIN-04 | — | no plugin file imports the repo's `src/` or `scripts/` | unit (AST scan) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_no_backend_imports.py -q` | ❌ W0 | ⬜ pending |
| 23-05-01 | 23-05 | 3 | PREVIEW-01 | T-23-11, T-23-12 | exact row count + header→prop labels + dropped columns, computed from the backend's own rule | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_rendering.py -q` | ❌ W0 | ⬜ pending |
| 23-05-01 | 23-05 | 3 | PREVIEW-04 | T-23-11 | preview mutates nothing — source bytes identical before and after | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_rendering.py -q` | ❌ W0 | ⬜ pending |
| 23-05-01 | 23-05 | 3 | INGEST-02 | T-23-12 | messy/uncleaned headers labelled with case-insensitive, whitespace-collapsed matching | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_rendering.py -q` | ❌ W0 | ⬜ pending |
| 23-05-01 | 23-05 | 3 | STRUCT-01 | T-23-11 | mapping table is a display lookup only; no row is transformed by it | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_rendering.py -q` | ❌ W0 | ⬜ pending |
| 23-05-02 | 23-05 | 3 | PLUGIN-02 | T-23-02 | README documents one-time operator setup from the tracked example; no secret in the conversation | unit (suite regression) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` | ❌ W0 | ⬜ pending |
| 23-06-01 | 23-06 | 4 | PLUGIN-01 | — | installs and auto-triggers in the Desktop Code tab; states endpoint + disarmed up front | manual | n/a — GUI install flow (see Manual-Only Verifications) | n/a | ⬜ pending |
| 23-06-02 | 23-06 | 4 | DISPATCH-01, DISPATCH-03 | T-23-14, T-23-15, T-23-16 | one armed canary creates a contact; window closed by a read-back-verified disarming redeploy | manual (human-executed) | n/a — live armed window (see Manual-Only Verifications) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is **plan 23-03** (wave 1, autonomous). It creates:

- [ ] `operator-claude-plugin/tests/conftest.py` — shared fixtures: a sample CSV with messy headers,
      a sample XLSX built at fixture time with openpyxl, a fake config, a recording `stub_transport`,
      and an **autouse** `no_network` guard so no test ever reaches the network
- [ ] `operator-claude-plugin/tests/test_transport_guard.py` — proves the guard bites (a `requests`
      call inside a test raises) and that the stub seam still records calls
- [ ] `operator-claude-plugin/requirements.txt` — plugin-local deps (research confirmed `openpyxl`,
      `requests`, `PyYAML` are already pinned and proven in this repo for these exact jobs)
- [ ] `operator-claude-plugin/config/operator.local.example.json` + the `.gitignore` entry for the
      real config path

No `__init__.py` under `operator-claude-plugin/tests/`, and `conftest.py` puts
`operator-claude-plugin/scripts` on `sys.path` — importing a package named `scripts` from the repo
root would resolve to the **backend's** `scripts/` package, which is the one import this suite exists
to forbid.

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
