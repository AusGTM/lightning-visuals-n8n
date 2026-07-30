---
phase: 26
slug: outcome-reporting-safe-retry
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `26-RESEARCH.md` §"Validation Architecture". `/gsd-validate-phase` sets
> `status: validated`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (plugin carries its own `requirements.txt`; no new dependency this phase) |
| **Config file** | repo default discovery — plugin tests live under `operator-claude-plugin/tests/` |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/contactCreateGateFlow.test.mjs` |
| **Estimated runtime** | ~15–30 seconds quick; full suite longer |

**Note:** the repo's established invocation is `.venv/bin/python -m pytest` (system python lacks the
deps) and `node --test tests/n8n/<file>.test.mjs` in **file** form — the directory form is broken on
the installed node version. Do not substitute a bare `pytest`.

**Standing constraint for this phase:** the autouse `no_network` fixture in
`operator-claude-plugin/tests/conftest.py` (landed in 23-03) makes a real HTTP call from any plugin
test impossible. Every new test in this phase drives an injected transport stub. **No automated
verification in Phase 26 performs a live POST, armed or otherwise** — the retry path under test is
the arming gate itself, and a test that accidentally arms and sends is worse than no test.

---

## Sampling Rate

- **After every task commit:** run the quick command
- **After every plan wave:** run the full suite
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 26-01 | 1 | REPORT-01 | T-26-04, T-26-06 | ledger read from the decision node, not the terminal review node; API key never in a message; run handle declared best-effort | unit (fixture + stub transport) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_executions_fallback.py -q` | ❌ W0 | ⬜ pending |
| 26-01-01 | 26-01 | 1 | REPORT-03 | T-26-02, T-26-05 | any non-settled or unrecognised status renders in-flight; exactly one fetch per call | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_executions_fallback.py -q` | ❌ W0 | ⬜ pending |
| 26-01-02 | 26-01 | 1 | REPORT-01 | T-26-01 | a decided write with a zero-item write node is downgraded to not-confirmed, never claimed | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_sufficiency.py -q` | ❌ W0 | ⬜ pending |
| 26-01-02 | 26-01 | 1 | REPORT-03 | T-26-03 | a body carrying only the review queue marker is judged insufficient and never rendered | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_sufficiency.py -q` | ❌ W0 | ⬜ pending |
| 26-01-03 | 26-01 | 1 | REPORT-03 | T-26-03, T-26-05 | fallback-sourced reports say so; no raw payload in chat; AST guard forbids sleep/status-loop constructs | unit (AST scan) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_sufficiency.py operator-claude-plugin/tests/test_plugin_manifest.py -q` | ❌ W0 | ⬜ pending |
| 26-02-01 | 26-02 | 2 | REPORT-02 | T-26-07, T-26-08 | null credits render unknown and are distinguishable from zero; an absent review flag renders unknown, never false | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_enrichment.py -q` | ❌ W0 | ⬜ pending |
| 26-02-02 | 26-02 | 2 | REPORT-02 | T-26-10 | rendered report and every skill body carry no derived scoring output and no placeholder for one | unit (output + skill scan) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report_enrichment.py -q` | ❌ W0 | ⬜ pending |
| 26-03-01 | 26-03 | 2 | DISPATCH-04 | T-26-12 | a no-email row is classified permanently stuck and excluded from the re-sendable set | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_retry_reuses_dispatch.py -q` | ❌ W0 | ⬜ pending |
| 26-03-02 | 26-03 | 2 | DISPATCH-04 | T-26-11, T-26-13, T-26-14 | one send path only; arming parameter keeps no default; no client-side accepted-row store | unit (AST scan) | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_retry_reuses_dispatch.py operator-claude-plugin/tests/test_plugin_manifest.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is **plan 26-01, task 1** (wave 1, autonomous). It creates the fixtures and the first test
file every later task in this phase depends on:

- [ ] `operator-claude-plugin/tests/fixtures/execution_contact_upload.json` — a redacted,
      execution-shaped payload with `data.resultData.runData` carrying a `Decide Action` entry (one
      row per outcome, including a no-email row for 26-03), plus `HubSpot Update`, `HubSpot Create`
      and `Set Review` entries. Allow-list redaction only, mirroring
      `scripts/enrichment_cost_ledger.py`'s `build_redacted_fixture` — synthetic identifiers, no real
      contact data, no secret.
- [ ] `operator-claude-plugin/tests/conftest.py` — one added `contact_execution` fixture exposing the
      payload above. The autouse `no_network` guard and the `stub_transport` seam already exist from
      23-03 and are reused, not re-invented.
- [ ] `operator-claude-plugin/tests/test_executions_fallback.py` — covers REPORT-01, REPORT-03
- [ ] `operator-claude-plugin/tests/test_report_sufficiency.py` — covers REPORT-01, REPORT-03
- [ ] `operator-claude-plugin/tests/fixtures/execution_enrichment.json` and
      `operator-claude-plugin/tests/test_report_enrichment.py` — covers REPORT-02 (created in 26-02)
- [ ] `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` — covers DISPATCH-04 (created in
      26-03)
- [ ] Framework install: **none** — pytest and `requests` are already declared in
      `operator-claude-plugin/requirements.txt`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Re-sending a failed chunk does not duplicate records the earlier attempt already accepted | DISPATCH-04 (criterion 4) | Can only be proven by an armed re-send against a live HubSpot test record; automating it would mean automating an armed write, which this phase forbids | During a human-executed armed window under the repo's two-key convention: dispatch a small batch to a `TEST_RECORD_*` allowlisted record, force a chunk failure, re-send that chunk, then confirm in HubSpot that the record was updated in place rather than duplicated |
| Time-proximity run-handle correlation names the right execution | REPORT-03 (D-12) | The webhook returns no execution id, so correlation accuracy is only observable against a real n8n run | After one live dispatch, compare the handle the report printed against the execution actually visible in the n8n UI. Repeat once with a second dispatch started within a few seconds, which is the case where correlation is most likely to mis-name |
| Execution-data retention is long enough for a same-session re-check | REPORT-03 (Assumption A4) | Retention varies by n8n Cloud plan tier and is not readable from the workflow JSON | One-line confirmation with the n8n admin of this project's plan tier and its execution retention window. If retention is very short, the fallback still serves the same-session re-check D-06 asks for — record the answer rather than designing around a guess |
| Assumptions A1 and A2 — whether an HTTP Request node's output preserves the input fields the report reads | REPORT-01, REPORT-02 | Only observable in a real execution payload | On the first live run, inspect `HubSpot Update` / `HubSpot Company Update` node output in the executions API. The reconciliation logic degrades to not-confirmed rather than crashing either way, so this confirms fidelity rather than gating the build |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] No automated verification performs a live POST, armed or otherwise
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
