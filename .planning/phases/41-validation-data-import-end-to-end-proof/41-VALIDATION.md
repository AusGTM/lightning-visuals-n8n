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
| T1 tracer | 41-01 | 1 | DATA-01 | T-41-01/02/03 | June table reproducible from a committed snapshot; evidence URL required before an ICP claim promotes | unit + node | `.venv/bin/python -m pytest tests/test_june_candidates.py -q && node --test tests/n8n/juneCandidateFold.test.mjs` | ❌ Wave 0 | ⬜ pending |
| T2 | 41-01 | 1 | DATA-01 | T-41-03 | Every enum value taxonomy-legal; no unevidenced veto-input negative | unit | `.venv/bin/python -m pytest tests/test_june_candidates.py -q` | ❌ Wave 0 | ⬜ pending |
| T3 | 41-01 | 1 | DATA-01 | T-41-04/05 | Stale June data cannot silently overwrite fresh research; firmographics stay staged-only | node | `node --test tests/n8n/juneCandidateFold.test.mjs tests/n8n/mergeCompanies.test.mjs tests/n8n/parity.test.mjs` | ❌ Wave 0 | ⬜ pending |
| T1 | 41-02 | 1 | DATA-01 | T-41-09/10 | Resolver is read-only by construction; refuses on wrong portal or missing credentials | unit | `.venv/bin/python -m pytest tests/test_resolve_june_ids.py -q` | ❌ Wave 0 | ⬜ pending |
| T2 | 41-02 | 1 | DATA-01, DATA-02 | — | Missing provenance is a failure only when explicitly demanded; standing sweep unchanged | unit | `.venv/bin/python -m pytest tests/test_scoring_parity.py -k "not live" -q` | ✅ extends | ⬜ pending |
| T3 | 41-02 | 1 | DATA-01 | T-41-06/07/08 | Arm gated on `ALLOW_N8N_ARM`; disarm never gated; empty allowlist refused | unit | `.venv/bin/python -m pytest tests/test_june_run_arm.py -q` | ❌ Wave 0 | ⬜ pending |
| T1 | 41-03 | 2 | DATA-01 | T-41-14 | Zero provider spend proven structurally against the shipped workflow | unit | `.venv/bin/python -m pytest tests/test_zero_provider_spend.py -q` | ❌ Wave 0 | ⬜ pending |
| T2 | 41-03 | 2 | DATA-01 | T-41-11/12/13 | Deploy precedes arm; bounce after content change; allowlist scoped to resolved ids only | manual (operator) | see Manual-Only Verifications | n/a | ⬜ pending |
| T3 tracer | 41-03 | 2 | DATA-01, DATA-02 | T-41-14/15 | 5 real records score with no manual touch; credits unchanged | live integration | `PARITY_SAMPLE_IDS=<5 ids> PARITY_REQUIRE_PROVENANCE=true .venv/bin/python -c "…run_scoring_parity…"` | ✅ after 41-02 | ⬜ pending |
| T1 | 41-04 | 3 | DATA-01, DATA-02 | — | Human gate before writing the remaining records | manual (operator) | see Manual-Only Verifications | n/a | ⬜ pending |
| T2 | 41-04 | 3 | DATA-01, DATA-02 | T-41-17/18/21 | Window closed and proven closed; false-green guard on the sweep | live integration | `PARITY_SAMPLE_IDS=<landed ids> PARITY_REQUIRE_PROVENANCE=true .venv/bin/python -c "…run_scoring_parity…"` | ✅ after 41-02 | ⬜ pending |
| T3 | 41-04 | 3 | DATA-01, DATA-02 | T-41-19/20 | No record omitted from the report; three expected-ugly categories counted even at zero | unit (suite gate) | `.venv/bin/python -m pytest -q` | ✅ | ⬜ pending |

*Populated by the planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All three are owned by wave-1 plans and land before any live task runs: the provenance assertion
in 41-02 T2, the candidate-table builder in 41-01 T1/T2, the id resolver in 41-02 T1.

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
