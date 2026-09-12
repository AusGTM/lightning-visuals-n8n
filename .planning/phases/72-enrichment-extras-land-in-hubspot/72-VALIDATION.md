---
phase: "72"
slug: "enrichment-extras-land-in-hubspot"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-12"
---

# Phase 72 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python, `.venv/bin/python -m pytest`) + Node built-in `node:test` |
| **Config file** | none dedicated at repo root; test files run directly |
| **Quick run command** | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py tests/test_merge_policy.py -q` and `node --test tests/n8n/mergeContacts.test.mjs tests/n8n/mergeCompanies.test.mjs tests/n8n/columnMap*.test.mjs` |
| **Full suite command** | `.venv/bin/python -m pytest` (root) and `node --test tests/n8n/*.test.mjs` (glob form — directory form broken on node 24) |
| **Estimated runtime** | ~120 seconds (both full suites) |

---

## Sampling Rate

- **After every task commit:** Run the quick-run subset scoped to the engine(s)/module(s) the task touched
- **After every plan wave:** Run `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` — both green
- **Before `/gsd-verify-work`:** Full suite must be green BEFORE the D-72-17 live gate is attempted
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 72-01-01 | 01 | 1 | D-72-01/02/03 | T-72-01 | STRUCT-01 allowlist widened, never removed | unit | `node --test tests/n8n/columnMapAliasParity.test.mjs tests/n8n/columnMapIdentityParity.test.mjs` | ✅ (new cases) | ⬜ pending |
| 72-01-02 | 01 | 1 | D-72-01 | T-72-01 | ingest `Merge Contacts` candidate includes widened set | unit | `node --test tests/n8n/mergeContacts.test.mjs` | ❌ W0 (wrapper harness) | ⬜ pending |
| 72-01-03 | 01 | 1 | D-72-01 | — | `strip_enrichment_extras` returns rows unchanged | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py -k strip_enrichment_extras` | ✅ | ⬜ pending |
| 72-01-04 | 01 | 1 | D-72-04 | — | LinkedIn lands in BOTH `hs_linkedin_url` + `lv_linkedin_url` | unit | `node --test tests/n8n/mergeContacts.test.mjs` | ❌ (new assertion) | ⬜ pending |
| 72-02-01 | 02 | 1 | D-72-05 | T-72-02 | CREATE: provider wins non-identity; CSV recorded as conflict; identity untouched | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py` | ❌ (new test) | ⬜ pending |
| 72-02-02 | 02 | 1 | D-72-06/07/08/09 | T-72-02 | recency gate all 3 engines; fresh non-blank protected; CSV ranks oldest | unit | `.venv/bin/python -m pytest tests/test_merge_policy.py` + `node --test tests/n8n/mergeContacts.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ W0 (fixtures) | ⬜ pending |
| 72-03-01 | 03 | 2 | D-72-10/11/12/13 | T-72-01 | slot winner/loser by trust_rank; provenance-only stamping | unit | `node --test tests/n8n/mergeContacts.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ W0 | ⬜ pending |
| 72-03-02 | 03 | 2 | D-72-11 | T-72-03 | property script two-key gate (`DRY_RUN` + dedicated `ALLOW_*`) | unit + live | `.venv/bin/python -m pytest tests/ -k phone_2` | ❌ W0 | ⬜ pending |
| 72-04-01 | 04 | 2 | D-72-14/15/16 | — | company geo/phone/domain candidates reach `Merge Company`; contact geo never feeds `lv_country_region_normalized` | unit | `node --test tests/n8n/normalizeProviders.test.mjs tests/n8n/mergeCompanies.test.mjs` | ❌ (new producer + tests) | ⬜ pending |
| 72-05-01 | 05 | 3 | SAFE-01 | T-72-01 | no `fill_blank_only`/`min_confidence` weakened | regression | `.venv/bin/python -m pytest` and `node --test tests/n8n/*.test.mjs` | ✅ | ⬜ pending |
| 72-05-02 | 05 | 3 | D-72-18 | — | 4 non-ingest regenerated JSONs diff clean | integration | `git diff --stat n8n/wf_enrichment_cloud.json n8n/wf_review_decision_cloud.json n8n/wf_scheduled_maintenance_cloud.json n8n/wf_backend_status_cloud.json` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs above are provisional — the planner assigns final plan/task numbering; keep the Requirement → Command mapping.*

---

## Wave 0 Requirements

- [ ] Confirm whether `tests/n8n/mergeContacts.test.mjs` exercises the `MERGE_CONTACTS` wrapper candidate-assembly loop or only `mergeContacts()`; if only the latter, add a harness driving the wrapper's field-loop (mirror `columnMapIdentityParity.test.mjs`'s YAML-oracle idiom)
- [ ] Recency fixtures for all three engines: (a) stale non-blank → overwrite, (b) fresh non-blank → protect, (c) no history at all → conservative (existing "unknown freshness == needs validation" idiom in `enrichmentGate.js`)
- [ ] D-72-12 winner/loser → `_2` slot routing fixtures
- [ ] `config/hubspot_properties.yaml` entries for `lv_phone_2`, `lv_mobilephone_2` (contacts), `lv_phone_2` (companies) before any sync

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One created contact shows `mobilephone`, `hs_linkedin_url` + `lv_linkedin_url`, geo | D-72-17 | live HubSpot write, armed send, backloaded gate (operator ruling 2026-09-09) | `enrich-before-ingest` one absent person at a held company, `create all 1`, read contact back; hand-delete after |
| One UPDATE row: non-blank `fill_blank_only` field NOT overwritten | D-72-17 / SAFE-01 | live HubSpot read-back | same gate run, second row |
| `hs_additional_emails` / `hs_additional_domains` writable on this portal | D-72-10 / D-72-14 | contradicted by 2026-08-26 property export; live-only | write one value, read back; record serialisation in SUMMARY |
| `hs_country_region_code` exists on companies | D-72-15 | live-only property existence | list company properties before writing |
| Deploy + bounce `wf_contact_ingest_cloud` only; others diff clean | D-72-18 | n8n Cloud deploy | `scripts/deploy_n8n_workflows.py` + `scripts/bounce_n8n_workflows.py`, disarmed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
