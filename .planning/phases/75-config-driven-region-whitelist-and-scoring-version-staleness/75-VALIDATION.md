---
phase: "75"
slug: "config-driven-region-whitelist-and-scoring-version-staleness"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-20"
validated: "2026-09-20"
---

# Phase 75 — Validation Strategy

> Per-phase validation contract. Reconstructed retroactively by `/gsd-validate-phase 75` on
> 2026-09-20 from the six PLAN/SUMMARY pairs, `75-VERIFICATION.md` (20/20 decisions, 22/22
> prohibitions) and the committed test tree. The plan-phase seed carried only the template.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv`, no `pytest.ini`; `tests/conftest.py`) + node built-in test runner (node 24) |
| **Config file** | none — `tests/conftest.py` only |
| **Quick run command** | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider <phase files> -k "not live" && node --test <phase .test.mjs files>` |
| **Full suite command** | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | quick ~10 s (337 py + 74 node); full ~3 min (5210 py + 1350 node at phase close) |

Notes: glob form for node (`tests/n8n/*.test.mjs`) — the directory form is broken on node 24.
`@live` pytest markers are deselected with `-k "not live"`; they need `.env`, which is
permission-blocked to the executor.

---

## Sampling Rate

- **After every task commit:** the task's own `<automated>` verify block (every task below has one; the plan-05/06 `checkpoint:decision` gates are operator decisions, not tasks)
- **After every plan wave:** full suite — run at the close of waves 1–6 (waves 1–4 carried 1–2 designed-red `tests/test_hubspot_schema_coverage.py` failures until plan 05 created `lv_icp_scoring_version` live; cleared at plan 05 Task 1)
- **Before `/gsd-verify-work`:** full suite green — 5210 passed / 0 failed, node 1350 / 0 (`75-06-SUMMARY.md`)
- **Max feedback latency:** ~10 s quick, ~3 min full

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 75-01-01 | 01 | 1 | D-75-01, D-75-02, D-75-03, D-75-05 | T-75-01, T-75-04 | codegen refuses empty/malformed `regions.home` or blank reason; Decide reads generated constants, no hand-typed reason literal | unit + parity | `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_icp_scoring.py tests/test_scoring_parity.py -k "not live"` + Decide-jsCode node check (PLAN `<automated>`) | ✅ | ✅ green |
| 75-01-02 | 01 | 1 | D-75-01, D-75-04 | — | zero `Non-ANZ geography` literals outside frozen/stress fixtures; frozen fixtures byte-unchanged | unit + grep | `pytest tests/test_veto_remediation_report.py tests/test_simulate_rubric_weights.py tests/test_remediate_veto_companies.py tests/test_backfill_dry_run.py` + `node --test tests/n8n/antiIcpFlagMirror.test.mjs …decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs` + `git status --porcelain tests/n8n/fixtures/frozen/` | ✅ | ✅ green |
| 75-01-03 | 01 | 1 | D-75-20, T-75-02 | T-75-01, T-75-02 | generated JS must match yaml (currency); any unaccompanied weight change is RED and names `lv_icp_scoring_version` | unit | `pytest tests/test_icp_scoring_generated_currency.py tests/test_rubric_change_guard.py` | ✅ | ✅ green |
| 75-02-01 | 02 | 2 | D-75-06, D-75-08 | T-75-05, T-75-06 | one alias table; `_COUNTRY_ISO2` gone; blank sentinels per lane unchanged | unit + parity | `node --test tests/n8n/regionAliasParity.test.mjs && pytest tests/test_normalizer.py` + python normaliser probe | ✅ | ✅ green |
| 75-02-02 | 02 | 2 | D-75-08 | T-75-04 | `REGION_ALIASES` inlined BEFORE its consumer in every normaliser node of every generated body | integration (graph) | inline-order node scan over `n8n/wf_*.json` (PLAN `<automated>`) + `node --test tests/n8n/regionAliasParity.test.mjs` | ✅ | ✅ green |
| 75-02-03 | 02 | 2 | D-75-07 | T-75-07, T-75-08 | `UK` hidden not deleted; `lv_icp_scoring_version` declared | unit | `pytest tests/test_hubspot_properties_config.py` | ✅ | ✅ green |
| 75-03-01 | 03 | 3 | D-75-16, D-75-17, D-75-18 | T-75-09, T-75-13 | fourth flag ships `"false"`; recompute PATCH pinned to exactly four keys; version fetched everywhere it is read | unit | `pytest tests/test_hubspot_properties_config.py tests/test_builder_flag_parity.py tests/test_deploy_flag_overlay.py` + literal grep of 4 bodies | ✅ | ✅ green |
| 75-03-02 | 03 | 3 | D-75-12, D-75-19 | T-75-12, T-75-14 | zero nodes added; reroute is a gate marker with `recompute_reason`; disarmed run is `write_blocked` | graph walk | `node --test tests/n8n/companyVersionStaleRecompute.test.mjs tests/n8n/companyRecomputeLaneFlow.test.mjs` + node-count/edge check | ✅ | ✅ green |
| 75-03-03 | 03 | 3 | D-75-13, D-75-15 | T-75-10, T-75-11 | SJ-2 version filter ANDed with `HAS_PROPERTY lv_org_type`; `enrich` classification kept | graph walk | `node --test tests/n8n/sj2VersionStaleGate.test.mjs` + SJ-2 search body check | ✅ | ✅ green |
| 75-04-01 | 04 | 4 | D-75-09, D-75-11 | T-75-17 | flow body generated from `regions.home`; drift check compares the single-flow body | unit | `pytest tests/test_geography_flow_conformance.py tests/test_check_schema_drift.py` | ✅ | ✅ green (drift LIST-vs-body defect fixed in plan 05: RED `4a73ae7a`, GREEN `0221804a`) |
| 75-04-02 | 04 | 4 | D-75-07 | T-75-16, T-75-19 | option ADD/HIDE only; a desired set omitting a live option is `drift`, never delete; no raw request echoed | unit | `pytest tests/test_sync_hubspot_properties.py` | ✅ | ✅ green |
| 75-04-03 | 04 | 4 | D-75-18a, D-75-18b | T-75-15, T-75-18 | `disarm()` cannot touch the flag; bounce rejects live `true` vs committed `false`; prints the value | unit | `pytest tests/test_recompute_flag_isolation.py tests/test_deploy_flag_overlay.py tests/test_june_run_arm.py` | ✅ | ✅ green |
| 75-05-01 | 05 | 5 | D-75-07, D-75-10 | T-75-20..23 | live schema write via gated script; read-back proves no option lost; token never in record | live (operator) | manual — see Manual-Only | n/a | ✅ done 2026-09-20 (`75-SCHEMA-RECORD.md`) |
| 75-05-02 | 05 | 5 | D-75-07 | T-75-24 | enum module carries all sixteen region values from a FRESH snapshot | unit | `pytest tests/test_hubspot_enums_generated_currency.py` + 16-value node check | ✅ | ✅ green (companies jsCode frozen fixture explicitly re-baselined `b7a6ddde`) |
| 75-05-03 | 05 | 5 | D-75-09, D-75-11 | T-75-17 | live flow == generated body; drift exit 0 | live (operator) | `scripts/check_schema_drift.py --out …` (needs `.env`) | n/a | ✅ done 2026-09-20 (`in_sync`, exit 0) |
| 75-06-01 | 06 | 6 | D-75-17, D-75-19, prohibition 22 | T-75-25..28 | deploy disarmed; every `ALLOW_HUBSPOT_*` `false` after bounce; exactly two executions; both `write_blocked`; fixtures redacted | live (operator) + recording pin | live: `scripts/bounce_n8n_workflows.py` (exit 0); offline: `node --test tests/n8n/phase75RecomputeProofRecordings.test.mjs` (G1) | ✅ | ✅ green — live steps done 2026-09-20 (`75-DEPLOY-RECORD.md`, `75-UAT.md`); recordings pinned by G1 (16 tests) + committed bodies pinned by G2 (37 cases) |
| 75-06-02 | 06 | 6 | D-75-05 sizing, D-75-14, D-75-17 runbook | T-75-29 | todos triaged; runbook names the sweep and the flip | doc + triage | `.venv/bin/python scripts/todo_triage.py` + grep counts on `docs/OPERATOR-RESCORE.md` | ✅ | ✅ green |
| 75-06-03 | 06 | 6 | as-built delta (CLAUDE.md §10.3.3) | — | stale "never created" listing corrected | doc + full suite | grep counts on CLAUDE.md + full suite + `todo_triage.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Re-run 2026-09-20 during this audit: 337 passed / 33 skipped / 21 deselected (`@live`) across the
plan-listed Python files; 74 / 74 across the plan-listed node files.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Retroactive additions by this audit:

- [x] `tests/n8n/phase75RecomputeProofRecordings.test.mjs` — G1: pins `exec_12682`/`exec_12683` (status/v1/71 nodes; explicit `recompute` + `recompute_reason: "requested"`; four-key recompute PATCH with the version read from `config/icp_scoring.yaml`; MRC `AU` → `false`/`0`/`""`, Jam TV `Other` → `true`/`1`/`hard_vetoes.outside_home_regions.reason`; one `write_blocked` row each; no `HubSpot Company Update`, no provider/research/judge node; `headers` redacted). Note: the fixture `graph` block carries only `node_count`, so the no-cost-node check is a name-substring scan over the 71 ran nodes, not a type lookup.
- [x] `tests/test_committed_bodies_ship_disarmed.py` — G2: every committed `n8n/wf_*.json` (9 files) × all four `ALLOW_HUBSPOT_*` flags never bakes `= "true"` (37 cases). The three pre-existing flag tests assert builder constants / synthetic workflows only, never the committed JSON.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `lv_icp_scoring_version` created live; 8 region options added; `UK` hidden | D-75-07, D-75-10 | HubSpot schema write needs `.env` credentials and `ALLOW_HUBSPOT_PROPERTY_WRITES`; executors cannot read `.env` | `set -a; source .env; set +a; .venv/bin/python scripts/sync_hubspot_properties.py --dry-run` must report 0 pending; compare `scripts/snapshot_hubspot_schema.py --label` output with `config/hubspot_migration/baseline/portal-schema-companies-phase75.json` |
| Geography flow `4626722240` PUT == generated body (revision 14) | D-75-09, D-75-11 | live HubSpot automation API | `.venv/bin/python scripts/check_schema_drift.py --out /tmp/drift.json` → `geography_flow_drift.status == in_sync`, exit 0 |
| Four cloud bodies deployed disarmed and bounced; all four `ALLOW_HUBSPOT_*` read `false` live | D-75-17, T-75-25 | live n8n | `.venv/bin/python scripts/bounce_n8n_workflows.py` → exit 0, node counts 289/43/101/55, flag rows `false` |
| Two recompute proofs consume exactly two executions, both `write_blocked`, no burst | D-75-19, T-75-27 | live n8n executions; costs executions | recorded once (`12682`, `12683`, `75-UAT.md`); offline pin is G1 — do not re-send |
| First supervised bump sweep and the D-75-17 flag flip | D-75-14, D-75-17 | deliberately NOT run; operator procedures | `docs/OPERATOR-RESCORE.md` § 2026-09-20 amendment (a)/(b) |
| Version-stale reroute on a REAL stale record (gate-derived marker) | D-75-12 | no record carries a stamp until the first armed sweep; both proofs were explicit `recompute` requests | after the first armed sweep, send a plain enrich for one stamped company after bumping `version`, read `Company Gate.recompute_reason == "version_stale"` from runData |
| SJ-2 monthly tick selects version-stale companies | D-75-13, D-75-15 | monthly schedule; write is allowlist-gated | pending todo `2026-09-20-sj2-version-stale-backstop-is-armed-only.md` names the trigger |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (live-only tasks are Manual-Only by design)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 75s (quick command)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-20 (`/gsd-validate-phase 75`)

## Validation Audit 2026-09-20

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |

Gap fill commit: `9724706b` (`test(phase-75): add Nyquist validation tests`). Post-fill: `node --test tests/n8n/*.test.mjs` 1366 / 0; `pytest tests/test_recompute_flag_isolation.py tests/test_committed_bodies_ship_disarmed.py` 45 / 0. Manual-Only rows are live-only by nature (credentials, executions, schedule), not escalations.
