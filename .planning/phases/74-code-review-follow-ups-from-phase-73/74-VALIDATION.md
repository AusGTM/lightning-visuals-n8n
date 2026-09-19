---
phase: "74"
slug: "code-review-follow-ups-from-phase-73"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-19"
---

# Phase 74 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python, `.venv`) + node:test (n8n walker suite) |
| **Config file** | none dedicated — both suites run from repo root |
| **Quick run command** | `node --test tests/n8n/<file>.test.mjs` or `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider <file>` |
| **Full suite command** | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~45 seconds (pytest ~36 s, node ~9 s) |

---

## Sampling Rate

- **After every task commit:** Run the test file just touched (quick run command)
- **After every plan wave:** Run the full suite command, then `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

This phase carries **no REQUIREMENTS.md ids** (spec-less probe visibly skipped — there are no
requirement ids to probe). The Requirement column carries the phase's locked decision ids
(D-74-NN) and the `73-REVIEW.md` finding ids (CR-NN / WR-NN) instead.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 74-01-01 | 01 | 1 | D-74-07, D-74-09 | T-74-01-01 / T-74-01-03 | No secret value shape survives the scrub at any depth of a node run | unit + guard | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider -k freeze_execution && node --test tests/n8n/frozenFixtureSecrets.test.mjs` | ✅ (guard test is new, created in this task) | ⬜ pending |
| 74-01-02 | 01 | 1 | D-74-08, D-74-09 | T-74-01-02 / T-74-01-06 | Committed fixtures carry no JWT body or live shared-secret value | guard + regression | `node --test tests/n8n/frozenFixtureSecrets.test.mjs tests/n8n/v1RuntimeRecordings.test.mjs tests/n8n/walkerEngineFidelity.test.mjs && .venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_run_report_enrich_account.py` | ✅ | ⬜ pending |
| 74-01-03 | 01 | 1 | D-74-03 (fixture) | T-74-01-04 / T-74-01-05 | The raw scratchpad runData never reaches git; only scrubbed bytes do | fixture integrity | `node --test tests/n8n/frozenFixtureSecrets.test.mjs tests/n8n/walkerEngineFidelityV1.test.mjs` | ✅ | ⬜ pending |
| 74-02-01 | 02 | 1 | WR-01, WR-02 | T-74-02-01 / T-74-02-02 | The operator's consent text states the real per-lane cost basis | unit | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_guardrails.py operator-claude-plugin/tests/test_write_grant_surface.py operator-claude-plugin/tests/test_headless_grant_boundary.py` | ✅ | ⬜ pending |
| 74-02-02 | 02 | 1 | WR-05 | T-74-02-03 | No lane's ledger entry silently overwrites another's | unit | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_report_enrichment.py operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_written_records.py` | ✅ | ⬜ pending |
| 74-02-03 | 02 | 1 | WR-06, D-74-13 | T-74-02-04 / T-74-02-05 | Rows excluded from the audit are counted and reported, not dropped | unit | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_chunking.py operator-claude-plugin/tests/test_run_report.py && test -f .planning/todos/pending/2026-09-17-stage-d-match-chunk-unchecked-rate.md` | ✅ | ⬜ pending |
| 74-03-01 | 03 | 1 | WR-11, WR-12 | T-74-03-01 / T-74-03-02 | A ragged operator CSV loses no column; outputs land beside their input | unit | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_dedupe.py` | ✅ | ⬜ pending |
| 74-03-02 | 03 | 1 | WR-03, WR-04 | T-74-03-03 / T-74-03-04 | One canonical config reader; a parse failure is visible, not silent | unit | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_dedupe.py operator-claude-plugin/tests/test_preview_rendering.py operator-claude-plugin/tests/test_preview_enrichment.py operator-claude-plugin/tests/test_preview_empty_input.py` | ✅ | ⬜ pending |
| 74-03-03 | 03 | 1 | WR-09 | T-74-03-05 | An absent key cannot pass as agreement on a review approval | unit | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_review_decision.py` | ✅ | ⬜ pending |
| 74-04-01 | 04 | 2 | D-74-03, WR-08 | T-74-04-01 / T-74-04-06 | The offline model no longer claims a delivery the engine never makes | unit + graph walk | `node --test tests/n8n/walkWorkflow.test.mjs tests/n8n/ingestCreateErrorLane.test.mjs tests/n8n/ingestCarryMerge.test.mjs tests/n8n/ingestWidenedFieldsFlow.test.mjs tests/n8n/mergeInputContract.test.mjs tests/n8n/executionOrderV1.test.mjs` | ✅ | ⬜ pending |
| 74-04-02 | 04 | 2 | D-74-14 | T-74-04-02 / T-74-04-03 | A research error loses no row and adds no double-firing producer | graph walk + regen idempotence | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/ && node --test tests/n8n/zoominfoLaneFlow.test.mjs tests/n8n/enrichmentConvergenceMerge.test.mjs tests/n8n/mergeInputContract.test.mjs tests/n8n/executionOrderV1.test.mjs` | ✅ | ⬜ pending |
| 74-04-03 | 04 | 2 | D-74-03, D-74-12 | T-74-04-04 / T-74-04-05 | A documented claim is never recorded as observed; MN-01 closes only on evidence | fidelity pin | `node --test tests/n8n/walkerEngineFidelityV1.test.mjs tests/n8n/v1RuntimeRecordings.test.mjs tests/n8n/walkerEngineFidelity.test.mjs && node --test tests/n8n/*.test.mjs` | ✅ | ⬜ pending |
| 74-05-01 | 05 | 3 | D-74-04, D-74-05 | T-74-05-01 / T-74-05-03 | Error classification rests on an explicit stamp, not a guessed payload shape | unit + graph walk | `.venv/bin/python scripts/build_cloud_workflows.py && node --test tests/n8n/pairCreateOutcome.test.mjs tests/n8n/ingestCreateErrorLane.test.mjs tests/n8n/ingestCarryMerge.test.mjs` | ✅ | ⬜ pending |
| 74-05-02 | 05 | 3 | D-74-06 | T-74-05-02 | An unconfirmed write is never reported to the operator as a success | graph walk + unit | `.venv/bin/python scripts/build_cloud_workflows.py && node --test tests/n8n/ingestCreateErrorLane.test.mjs tests/n8n/ingestMixedBatch.test.mjs tests/n8n/ingestResponseRowId.test.mjs && .venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_written_records.py operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_run_manifest.py` | ✅ | ⬜ pending |
| 74-05-03 | 05 | 3 | D-74-02, D-74-01, WR-10 | T-74-05-04 / T-74-05-05 | No report input starves on a common batch shape; arming still reaches every gate | graph walk + full suites | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/ && node --test tests/n8n/*.test.mjs && .venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` | ✅ | ⬜ pending |
| 74-06-01 | 06 | 4 | D-74-11 | T-74-06-01 / T-74-06-02 / T-74-06-03 | No armed body is ever deployed; only the two changed workflows ship | committed-body assertion + live read-back | `node -e "const a=require('./n8n/wf_contact_ingest_cloud.json'),b=require('./n8n/wf_enrichment_cloud.json');const bad=[...a.nodes,...b.nodes].filter(n=>/ALLOW_(HUBSPOT\|N8N)/.test(JSON.stringify(n.parameters\|\|{}))&&/=\s*true/.test(JSON.stringify(n.parameters\|\|{})));if(bad.length){console.error(bad.map(n=>n.name));process.exit(1)}console.log('disarmed')"` | ✅ | ⬜ pending |
| 74-06-02 | 06 | 4 | D-74-11 | T-74-06-04 / T-74-06-05 / T-74-06-07 | Proof runData reaches git only through the widened scrubber; the send spends nothing | guard + live read-back | `node --test tests/n8n/frozenFixtureSecrets.test.mjs tests/n8n/walkerEngineFidelityV1.test.mjs tests/n8n/v1RuntimeRecordings.test.mjs` | ✅ | ⬜ pending |
| 74-06-03 | 06 | 4 | D-74-12, D-74-13 | T-74-06-06 | No open question is closed on a phase-id match; the release names every behaviour change | full suites + triage | `.venv/bin/python scripts/todo_triage.py && .venv/bin/python -m pytest -q --tb=short -p no:cacheprovider && node --test tests/n8n/*.test.mjs` | ✅ | ⬜ pending |
| 74-06-04 | 06 | 4 | D-74-11 | T-74-06-01 / T-74-06-03 | Human confirms the execution ceiling held and nothing is armed | manual (checkpoint:human-verify) | manual — see Manual-Only Verifications | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Sampling continuity:** no three consecutive tasks lack an automated verify — 74-06-04 is the
only manual task in the phase and it is the final task of the final plan.

---

## Wave 0 Requirements

Existing infrastructure covers every phase decision. Every test file this phase needs already
exists in the repo, with two exceptions, both created inside the phase's own scope rather than as
a Wave 0 gap:

- [x] `tests/n8n/frozenFixtureSecrets.test.mjs` — the D-74-09 guard, created by task 74-01-01.
- [x] `tests/n8n/fixtures/frozen/exec_12522.runData.json` — data, not infrastructure; created by
      task 74-01-03 and consumed by 74-04-03.

No framework install, no conftest change, no new runner.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Exactly 2 n8n executions consumed by the phase; both live bodies still disarmed after the sends; four cloud workflows untouched; zero HubSpot records written | D-74-11 | The execution ceiling and the armed/disarmed state of a live n8n Cloud instance cannot be asserted by any offline test; the read-back is live and the judgement is the operator's | Task 74-06-04's `<how-to-verify>` block: read the two execution ids and the running total from `74-UAT.md`, compare live node counts against `74-04-SUMMARY.md` / `74-05-SUMMARY.md`, read the post-send write-safety flag table, confirm only two workflows were deployed, confirm no HubSpot record was written, confirm the research-error branch stays documented-only |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (18 of 19 automated; 74-06-04 is
      the single manual checkpoint, recorded above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — the two new artifacts are created in-phase)
- [x] No watch-mode flags
- [x] Feedback latency < 60s (pytest ~36 s, node ~9 s; per-task commands are subsets)
- [ ] `nyquist_compliant: true` set in frontmatter — set by `/gsd-validate-phase`, not by the
      planner

**Approval:** pending
