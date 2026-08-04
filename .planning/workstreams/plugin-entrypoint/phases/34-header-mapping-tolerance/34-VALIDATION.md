---
phase: 34
slug: header-mapping-tolerance
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `34-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python, `operator-claude-plugin/`) + `node --test` (JS, `tests/n8n/`) |
| **Config file** | none dedicated — both auto-discovered |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` + `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~60s plugin suite; ~5 min repo-wide |

Baselines to beat: plugin **960 passed / 5 skipped** · full python **1841 / 6** · node **550** ·
disarmed-artifact gate **0**.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
- **After every plan wave:** all four of `34-CONTEXT.md` §7, in order —
  `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`,
  `.venv/bin/python -m pytest -q`,
  `node --test tests/n8n/*.test.mjs`,
  `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` (must print `0`)
- **Before `/gsd-verify-work`:** all four green, PLUS `tests/n8n/columnMapAliasParity.test.mjs`
  re-run specifically after any Half A alias edit, PLUS the disarmed redeploy read-back
  (`verify_live_write_safety.py --expectation disarmed`) after the workflow bounce.
- **Max feedback latency:** ~60s (plugin suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Half A alias widen | TBD | 1 | INGEST-02 | — | Preview cannot claim a mapping the backend will not perform | unit | `node --test tests/n8n/columnMapAliasParity.test.mjs` | ✅ exists | ⬜ pending |
| `Full Name` refusal | TBD | 1 | INGEST-06 | — | Refuses with reason named; never splits a name | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_header_suggest.py -x` | ❌ W0 | ⬜ pending |
| Header-row correction | TBD | 2 | STRUCT-01 | — | Only the header row changes; no row cell value is ever rewritten | unit | same test file | ❌ W0 | ⬜ pending |
| No silent rewrite | TBD | 2 | STRUCT-04 | — | A header is rewritten ONLY when present as a key in the operator's `confirmed` dict; the writer is never auto-invoked from the suggester's own output | unit + CLI subprocess | same test file + `_run_cli` harness | ❌ W0 | ⬜ pending |
| Re-preview after correction | TBD | 3 | PREVIEW-01 | — | The corrected file is what is previewed AND what is sent | integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preview_rendering.py -x` | ❌ W0 (extend existing) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `operator-claude-plugin/scripts/header_suggest.py` — this phase's only new source module
- [ ] `operator-claude-plugin/tests/test_header_suggest.py` — covers INGEST-06, STRUCT-01,
      STRUCT-04 (including the "no header rewritten without confirmation" property)
- [ ] Extension to `operator-claude-plugin/tests/test_preview_rendering.py` — PREVIEW-01's
      re-preview-after-correction case
- [ ] No new `tests/n8n/` file needed — `columnMapAliasParity.test.mjs` already covers any Half A
      widening structurally, because it walks every YAML key through the real `mapRow`
- [ ] Framework install: none

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UAT 2.2 re-walk | INGEST-02 | An observed pass and a verified fix are different claims — the operator marks this, not the implementer | Operator hands the plugin `operator-claude-plugin/tests/samples/22-messy-headers.csv`, confirms the suggested `Ph.` → `phone` mapping, sees `Full Name` refused with its reason, and re-marks 2.2 in the UAT record |
| Disarmed redeploy + bounce | INGEST-02 (Half A reaching the running backend) | A bare PUT never reloads a running workflow; only a deactivate→activate cycle does, and a read-back proves stored content only | `34-CONTEXT.md` §6 ceremony verbatim: build → disarmed deploy → bounce every active workflow (4 active; LV Review Decision stays inactive) → `verify_live_write_safety.py --expectation disarmed` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
