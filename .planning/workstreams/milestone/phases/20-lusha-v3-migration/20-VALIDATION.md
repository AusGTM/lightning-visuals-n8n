---
phase: 20
slug: lusha-v3-migration
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 20 — Validation Strategy

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
| 20-01-T1 | 01 | 1 | REQ-lusha-v3-contract-probe | T-20-01, T-20-02, T-20-04 | Probe disarmed by default; key never printed; credit cap enforced before each billable call | manual (live probe) + offline dry-print | `.venv/bin/python scripts/probe_lusha_v3.py` (disarmed: zero HTTP, prints v3 request ladder) | ❌ new | ⬜ pending |
| 20-01-T2 | 01 | 1 | REQ-lusha-v3-contract-probe | T-20-01, T-20-02, T-20-03 | Contract doc records header names not values; revealed PII replaced with synthetic values | manual (live probe) + unit | `.venv/bin/python -m pytest tests/test_check_provider_credits.py tests/test_provider_registry_parity.py -q` | ✅ exists | ⬜ pending |
| 20-01-T3 | 01 | 1 | REQ-lusha-v3-contract-probe | T-20-04 | Blocking gate: a refuted A3/A7 stops the phase instead of building on a false premise | checkpoint | n/a — blocking human-verify | n/a | ⬜ pending |
| 20-02-T1 | 02 | 2 | REQ-lusha-selective-reveal | T-20-02 | Reveal list built from a frozen literal map with own-property lookups; hostile-input case asserted | unit | `node --test tests/n8n/lushaRequest.test.mjs` | ❌ new | ⬜ pending |
| 20-02-T2 | 02 | 2 | REQ-lusha-v3-request-builders, REQ-lusha-selective-reveal | T-20-01, T-20-04, T-20-05 | Key stays in credential/`$env`; body never carries it; contract test evaluates the real committed expression | unit | `.venv/bin/python -m pytest tests/test_cloud_contacts_branch.py tests/test_builder_flag_parity.py tests/test_enabled_build_invariants.py -q` | ✅ exists | ⬜ pending |
| 20-02-T3 | 02 | 2 | REQ-lusha-v3-request-builders | T-20-04, T-20-05 | Parity test deep-equals the CLOUD expression against the shared module across 4+ inputs | unit | `.venv/bin/python -m pytest -q` ; `node --test tests/n8n/*.test.mjs` | ✅ exists | ⬜ pending |
| 20-03-T1 | 03 | 3 | REQ-lusha-v3-normalize | T-20-03 | Fixture personal values synthetic; no real revealed email or phone committed | unit (fixture parse) | `node --test tests/n8n/enrichment.test.mjs` | ❌ new fixtures | ⬜ pending |
| 20-03-T2 | 03 | 3 | REQ-lusha-v3-normalize | T-20-06, T-20-07 | Adapter never throws on no-match/error/missing/`{}`/`null`; diff confined to the envelope block | unit | `node --test tests/n8n/enrichment.test.mjs tests/n8n/parity.test.mjs` | ✅ exists | ⬜ pending |
| 20-03-T3 | 03 | 3 | REQ-lusha-v3-normalize | T-20-07, T-20-08 | v2 assertions migrated not dropped; no unreachable retired branch left behind | unit | `.venv/bin/python -m pytest -q` ; `node --test tests/n8n/*.test.mjs` | ✅ exists | ⬜ pending |
| 20-04-T1 | 04 | 4 | REQ-lusha-id-staging | T-20-10 | Dry-run diff must show exactly 2 creates, 0 updates, 0 deletes before anything is armed | unit | `.venv/bin/python -m pytest tests/test_hubspot_properties_config.py tests/test_sync_hubspot_properties.py tests/test_hubspot_schema_coverage.py -q` | ✅ exists | ⬜ pending |
| 20-04-T2 | 04 | 4 | REQ-lusha-id-staging | T-20-03, T-20-09, T-20-02 | Only the opaque id is written; blank/null id treated as absent; candidate field set asserted unchanged | unit | `node --test tests/n8n/*.test.mjs` ; `.venv/bin/python -m pytest -q` | ✅ exists | ⬜ pending |
| 20-04-T3 | 04 | 4 | REQ-lusha-id-staging | T-20-10, T-20-01 | Two-key gate + undo manifest + operator-run, not executor-armed; independent schema read-back | checkpoint | n/a — blocking human-verify | n/a | ⬜ pending |
| 20-05-T1 | 05 | 5 | REQ-lusha-v3-verification | T-20-12 | Negative URL assertion paired with positive endpoint assertions; in-process build catches an unrebuilt edit | unit | `.venv/bin/python -m pytest -q` ; `node --test tests/n8n/*.test.mjs` | ✅ exists | ⬜ pending |
| 20-05-T2 | 05 | 5 | REQ-lusha-v3-verification | T-20-12 | Frozen fixture re-baselined only with a named cause; unexplained drift treated as a bug | unit | `.venv/bin/python -m pytest tests/test_companies_factory_frozen.py -q` ; two builder runs leave `git status --porcelain n8n/` empty | ✅ exists | ⬜ pending |
| 20-05-T3 | 05 | 5 | REQ-lusha-v3-verification | T-20-11, T-20-13, T-20-01 | Read-back is a separate step from the deploy; no flag overlay passed; verifier prints no secret | integration (live read-back) | `.venv/bin/python scripts/verify_live_lusha_urls.py` | ❌ new | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None — test infrastructure already exists (603 pytest / 309 node tests green at phase start).
