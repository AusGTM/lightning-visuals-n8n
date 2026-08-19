---
phase: 51
slug: backfill-pipeline-credit-sizing-dry-run
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-08-19
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + `node --test` (JS regression only — this phase writes no JS) |
| **Config file** | none dedicated — plain pytest discovery over `tests/test_*.py` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_zoominfo_company_client.py tests/test_backfill_dry_run.py tests/test_scored_population_snapshot.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~25 seconds quick, ~180 seconds full |

**Two hard invocation rules for this repo.** Use `.venv/bin/python -m pytest` — the system Python
lacks the dependencies. Use the **glob** form `node --test tests/n8n/*.test.mjs` — the directory
form is broken on the installed Node 24.

**Offline by default.** Every test in this phase is offline: provider HTTP, HubSpot search/read and
the Anthropic research call are all monkeypatched. No test spends a credit or contacts a live API.

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run `.venv/bin/python -m pytest` (full Python suite)
- **Before `/gsd-verify-work`:** Full Python suite green, plus `node --test tests/n8n/*.test.mjs`
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 51-01-01 | 01 | 1 | FILL-03, SAFE-01 | T-51-01 / T-51-05 | Malformed provider response degrades to an unmatched skip, never a crash or a guessed input; no credential enters a returned dict | unit (tracer, mocked) | `.venv/bin/python -m pytest tests/test_backfill_dry_run.py::test_end_to_end_one_record_dry_run -x` | ✅ created by this task | ⬜ pending |
| 51-01-02 | 01 | 1 | FILL-01, FILL-03, SAFE-01 | T-51-04 / T-51-06 | Cap arithmetic is integer-only so no rounding inflates permitted spend; prediction cannot carry a label the live formula lacks | unit | `.venv/bin/python -m pytest tests/test_zoominfo_company_client.py tests/test_backfill_dry_run.py -x` | ✅ created by this task | ⬜ pending |
| 51-01-03 | 01 | 1 | FILL-01 | T-51-01 / T-51-02 / T-51-04 | Portal asserted before any call; artifact carries no token; spend bounded to one credit | integration (live read + 1 enrich) | `.venv/bin/python -m pytest tests/test_backfill_dry_run.py -x` then artifact JSON assertions in the plan's acceptance criteria | ✅ | ⬜ pending |
| 51-02-01 | 02 | 2 | FILL-04 | T-51-07 / T-51-08 | Research is structurally unreachable for unmatched records; out-of-vocabulary org_type cannot reach the oracle; null answers leave keys absent | unit (mocked research) | `.venv/bin/python -m pytest tests/test_backfill_dry_run.py -x` | ✅ | ⬜ pending |
| 51-02-02 | 02 | 2 | FILL-01 | T-51-04 | Sample above cap refuses before the first enrich request is issued | unit + live read-only | `.venv/bin/python -m pytest tests/test_backfill_dry_run.py::test_sizing_plan_recorded_before_enrich tests/test_backfill_dry_run.py::test_sample_above_cap_refused -x` | ✅ | ⬜ pending |
| 51-02-03 | 02 | 2 | SAFE-01, FILL-04 | T-51-09 / T-51-10 / T-51-11 | Predictions committed before any write path exists; partition assertion makes a dropped record impossible; artifacts carry no credential | unit + integration (capped live sample) | `.venv/bin/python -m pytest tests/test_backfill_dry_run.py::test_empty_sample_writes_valid_artifacts tests/test_backfill_dry_run.py::test_sample_order_is_ascending_id_stable -x` | ✅ | ⬜ pending |
| 51-03-01 | 03 | 3 | SAFE-01 | T-51-12 / T-51-13 / T-51-15 | Baseline module proven write-free by source inspection; truncated population refuses rather than writing a partial baseline | unit + live read-only | `.venv/bin/python -m pytest tests/test_scored_population_snapshot.py -x` | ✅ created by this task | ⬜ pending |
| 51-03-02 | 03 | 3 | SAFE-01 | — | N/A (documentation) | doc gate | `test -f .planning/phases/51-backfill-pipeline-credit-sizing-dry-run/COVERAGE.md && grep -c 'OPT-OUT' .planning/phases/51-backfill-pipeline-credit-sizing-dry-run/COVERAGE.md` | ✅ | ⬜ pending |
| 51-03-03 | 03 | 3 | SAFE-01 | T-51-14 | Phase cannot advance to a write-capable phase without a recorded operator go-ahead | manual (blocking checkpoint) | none — see Manual-Only Verifications | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All three new test files are created inside this phase's own plans, in the same task as the code
they pin — there is no pre-wave scaffolding gap:

- [x] `tests/test_backfill_dry_run.py` — created in 51-01 task 1 (end-to-end tracer test), extended
      in 51-01 task 2 and 51-02 tasks 1-3
- [x] `tests/test_zoominfo_company_client.py` — created in 51-01 task 2
- [x] `tests/test_scored_population_snapshot.py` — created in 51-03 task 1
- [x] No new conftest or fixture module needed — `tests/scoring_fixtures.py` already supplies the
      shared constants and helpers, and `tests/test_icp_scoring.py` supplies the style

Existing infrastructure covers everything else. No framework install is required.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator approval of the dry-run artifacts | SAFE-01 (and the ROADMAP's criterion 7 exit gate) | A judgement about whether the sample's payloads, bands, regions and predicted tiers are plausible for accounts the operator knows. No automated check can decide whether a Tier B prediction for a known account is right — that is exactly the judgement the gate exists to capture | Follow 51-03 task 3's `<how-to-verify>`: read `51-SIZING.md`, spot-check three rows of `51-DRYRUN-PREDICTIONS.json` for revenue band in dollars, region present-or-absent, and tier plausibility; read `51-SKIP-LOG.json` reasons; rule on the third-disposition question; then approve or describe what must change |
| Revenue band sanity against known accounts | FILL-03 | The unit test pins the conversion arithmetic; only a human who knows the account can confirm the *result* is the right band for that company | Step 2 of the checkpoint's verification steps |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the one exception is the blocking
      checkpoint, recorded under Manual-Only Verifications)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — every test file is created in-phase alongside its code
- [x] No watch-mode flags
- [x] Feedback latency < 25s (quick command)
- [ ] `nyquist_compliant: true` set in frontmatter — left for `/gsd-validate-phase` §6

**Approval:** pending
