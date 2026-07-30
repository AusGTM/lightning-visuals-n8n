---
phase: 21
slug: transport-schema-hygiene
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + node:test (node 24) |
| **Config file** | existing — no Wave 0 install |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -q -x` |
| **Full suite command** | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/ -q -x`
- **After every plan wave:** Run full suite (pytest + node --test)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-01-T1 | 01 | 1 | REQ-dedupe-transport-swap | T-21-01, T-21-02 | Zero-hit search returns an empty envelope instead of stopping the chain; credential binding survives the transport change | unit | `.venv/bin/python -m pytest tests/test_hubspot_native_operation_validity.py tests/test_deploy_credential_binding.py -q` | ✅ existing | ⬜ pending |
| 21-01-T2 | 01 | 1 | REQ-dedupe-transport-swap | T-21-01, T-21-05 | No native HubSpot search node in any cloud workflow; dedupe lane writes only the needs-review flag | unit | `.venv/bin/python -m pytest tests/test_hubspot_native_operation_validity.py tests/test_write_gate_coverage.py -q` | ⚠️ new predicates in existing files | ⬜ pending |
| 21-01-T3 | 01 | 1 | REQ-dedupe-transport-swap | T-21-03, T-21-04, T-21-06 | The served workflow (not just the committed artifact) has zero native search nodes; redeploy arms nothing; verifier leaks no credential | live read-back | `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_no_native_search.py', run_name='__main__')"` | ❌ new script | ⬜ pending |
| 21-02-T1 | 02 | 2 | REQ-country-region-policy | T-21-07, T-21-10 | Country/region promotes at 75+, stages below; the veto-feeding threshold is deliberate and recorded | unit (JS + Py) | `node --test tests/n8n/mergeCompanies.test.mjs` · `.venv/bin/python -m pytest tests/test_merge_policy.py tests/test_icp_scoring.py -q` | ⚠️ new cases in existing files | ⬜ pending |
| 21-02-T2 | 02 | 2 | REQ-country-region-policy | T-21-08 | The YAML policy and its JS mirror cannot diverge silently | unit | `.venv/bin/python -m pytest tests/test_field_policy_conformance.py -q` | ❌ new file | ⬜ pending |
| 21-02-T3 | 02 | 2 | REQ-country-region-policy | T-21-09 | The frozen jsCode guard is re-baselined only for a named cause with a proven-bounded diff | unit | `.venv/bin/python -m pytest -q` · `node --test tests/n8n/*.test.mjs` | ✅ existing | ⬜ pending |
| 21-03-T1 | 03 | 1 | REQ-orgtype-enumeration | T-21-12, T-21-14, T-21-16 | The probe can only ever target the disposable property; refuses on portal mismatch, missing keys, non-allowlisted test record; leaves no residue | unit (gates) + live probe (operator) | `.venv/bin/python -m pytest tests/test_org_type_probe_gates.py -q` | ❌ new file | ⬜ pending |
| 21-03-T2 | 03 | 1 | REQ-orgtype-enumeration | T-21-15, T-21-17 | Every distinct live org-type value inventoried and classified; truncation visible; record ids only, no company identity | live read-only | `.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/inventory_org_type_values.py', run_name='__main__')"` | ❌ new script | ⬜ pending |
| 21-03-T3 | 03 | 1 | REQ-orgtype-enumeration | T-21-13, T-21-16 | Armed probe ladder run by the operator; verdicts recorded; migration shape chosen from evidence | manual (blocking checkpoint) | dry-run review, then armed run — commands in 21-03-PLAN.md Task 3 | n/a | ⬜ pending |
| 21-04-T1 | 04 | 2 | REQ-orgtype-enumeration | T-21-20 | Rollback documented, with populated markers, before any migration code exists | unit | `.venv/bin/python -m pytest tests/test_migrate_org_type_enum.py -q -k runbook` | ❌ new file | ⬜ pending |
| 21-04-T2 | 04 | 2 | REQ-orgtype-enumeration | T-21-18, T-21-20, T-21-21, T-21-23, T-21-24 | Cannot arm without a populated runbook and a clean inventory; options derived from the taxonomy; one shape only | unit | `.venv/bin/python -m pytest tests/test_migrate_org_type_enum.py -q` | ❌ new file | ⬜ pending |
| 21-04-T3 | 04 | 2 | REQ-orgtype-enumeration | T-21-18 | The one-way door is an explicit, reasoned decision, not a default | manual (blocking decision checkpoint) | n/a — reversibility gate | n/a | ⬜ pending |
| 21-04-T4 | 04 | 2 | REQ-orgtype-enumeration | T-21-18, T-21-19, T-21-22 | Enumeration lands with values preserved; verified by independent snapshot diff + inventory diff + enforcement smoke, never by the script's exit code | manual/live (blocking checkpoint) | `scripts/snapshot_hubspot_schema.py --label post-orgtype-enum` diff + inventory re-run — full procedure in 21-04-PLAN.md Task 4 | ✅ existing snapshot tooling | ⬜ pending |

**Known red window (deliberate):** `tests/test_companies_factory_frozen.py` fails from 21-02-T1 until 21-02-T3 closes it. That failure is this phase's own doing and is closed by a named-cause re-baseline with a proven-bounded diff — never by a convenience update.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None for test infra (611 pytest / 352 node green at phase start). Research recommends a Wave-0 LIVE PROBE on a disposable HubSpot property to settle in-place type-conversion behavior before the org_type migration is designed — that probe is a plan task, not test infra.
