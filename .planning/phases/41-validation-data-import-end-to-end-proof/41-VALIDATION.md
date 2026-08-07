---
phase: 41
slug: validation-data-import-end-to-end-proof
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-07
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/python -m pytest`) + node (`node --test tests/n8n/*.test.mjs`) |
| **Config file** | none dedicated — repo-root `tests/` package, existing `tests/scoring_fixtures.py` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k "not live"` |
| **Full suite command** | `RUN_LIVE_PARITY=true .venv/bin/python -m pytest tests/test_scoring_parity.py` |
| **Estimated runtime** | ~30s offline tier; live tier minutes (creates/exercises/deletes disposables) |

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest tests/test_scoring_parity.py -k "not live"` (offline, zero cost)
- **After every plan wave:** `.venv/bin/python -m pytest` (full offline suite, baseline 2308 passing)
- **Per canary (D-10):** live parity check against the ~5 canary IDs before releasing the remaining 61
- **Before `/gsd-verify-work`:** full `scripts/run_scoring_parity.py` sweep over all landed IDs
- **Max feedback latency:** ~30 seconds for the offline tier

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD by planner | — | — | DATA-01 | — | Writes stay disarmed until operator arms | unit | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k "not live"` | ✅ | ⬜ pending |
| TBD by planner | — | — | DATA-02 | — | No per-record manual touch | live integration | `scripts/run_scoring_parity.py` over landed IDs | ✅ | ⬜ pending |

*Populated by the planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Provenance assertion in the parity path — `scripts/run_scoring_parity.py` asserts
      score/tier/veto parity only (`tests/scoring_fixtures.py::expected_for`); it does not
      check `lv_enrichment_provenance` presence/shape. DATA-01's "provenance stamped" bar
      needs this as an automated check, not a manual spot-check. Small addition, not a new
      harness.
- [ ] June-candidate table builder — no existing script maps `enriched_companies.json` into
      the D-02/D-03 candidate shape. Net-new, scoped to this phase.
- [ ] Pre-flight ID resolver — no existing script resolves/re-matches the 66 June-era IDs
      against the live portal (D-09). Net-new, small; `src/hubspot_client.py` primitives
      suffice as building blocks.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Canonical writes armed for the run | DATA-01 | Arming is operator-only by decision D-06 and by the environment's permission boundary — Claude cannot execute it | Operator runs the arm command the plan hands them, confirms the write-safety verifier reports armed, and disarms at run end |
| Canary landed correctly before release of the remaining 61 | DATA-01, DATA-02 | Judgement call on whether mapped enum values are right for the real companies | Operator reviews the ~5 canary records in HubSpot against the run report before authorizing the rest |
| Review-queue triage | DATA-01 | Needs-review routing is expected (D-12); triage is a human decision | Operator reviews the run report's queued-record list via the existing review flow |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for the offline tier
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
