# Phase 11: Company Branch & Provider Contract Hardening

**Status**: Complete
**Completed**: 2026-07-20
**Plan**: RETROACTIVE — reconstructed 2026-07-20 from the session record

> ## Provenance
>
> This phase was executed **outside GSD** between 2026-07-08 and 2026-07-20. No plan was
> written in advance; the work was driven conversationally (probe → decide → implement →
> test). This file exists so the phase registers correctly with GSD tooling and so the
> executed scope is auditable. It is a record of what was done, **not** a plan that was
> followed. Outcomes live in `phase-11-01-SUMMARY.md`.
>
> Note for future phases: `docs/WEB-RESEARCH-SPEC.md` was produced at the end of this
> phase and IS a real forward contract — Phases 13–14 plan against it.

**Goal**: Companies enrich from live providers with correct units and no silent
wrong-entity data.

## Tasks (as executed)

### Task 1 — Company enrichment branch in n8n
Sibling branch off the same Manual Trigger; explicitly NOT nested under contacts.
- Files: `scripts/build_cloud_workflows.py`, `n8n/wf_enrichment_local_live.json`
- Added a `fan()` builder helper — `chain()` overwrote on node-name collision.
- Acceptance: 12 nodes wired, read-only, no write nodes. ✅

### Task 2 — mergeCompanies.js
Separate module (user decision: zero regression risk vs parameterising `mergeContacts`).
- Files: `n8n/code/mergeCompanies.js`, `tests/n8n/parity.test.mjs`
- `domain` hard guard + evidence-URL gate ahead of the ownership-class branches.
- Acceptance: 3 tests covering promote / evidence-gated / value-scoped gating. ✅

### Task 3 — ZoomInfo GTM companies contract
- Probed `companies/enrich` + `companies/search` live; both 200.
- 27 valid outputFields enumerated individually; `companyType` → 400 `PFAPI0009`.
- Files: `tests/fixtures/enrichment/zoominfo_live_company.json` (real response)
- Acceptance: contract documented, fixture captured. ✅

### Task 4 — Provider unit + live-shape defects
- Files: `n8n/code/normalizeProviders.js`, `tests/n8n/enrichment.test.mjs`
- ZoomInfo `revenue` is THOUSANDS → every company banded 1000x low (FanDuel's $14b read
  as `5-50M`: **+10** instead of **−50**, an inverted ICP signal).
- Lusha `/v2/company` wraps in `data` → live response yielded ZERO candidates.
- ZoomInfo `naicsCodes` are objects → `"[object Object]"` staged as industry.
- Acceptance: 4 regression tests, all green. ✅

### Task 5 — Cross-provider conflict detector
- Files: `scripts/build_cloud_workflows.py` (Merge Company / Normalize + Score Company)
- Conflicting size fields withhold promotion, surface `conflicts` + `needs_review`.
- Also fixed: company branch reads `best[f].normalizedValue`, not raw `winners[f]`.
- Acceptance: Harvey Norman 3-way conflict caught end-to-end; band withheld. ✅

### Task 6 — Taxonomy + spec
- Files: `config/taxonomy.yaml`, `docs/WEB-RESEARCH-SPEC.md`,
  `tests/test_taxonomy_conformance.py`, `tests/test_web_research_spec.py`
- Acceptance: 30 numbered requirements; 14 drift guards; 22 acceptance tests. ✅

## Verification

```bash
node --test tests/n8n/parity.test.mjs tests/n8n/enrichment.test.mjs tests/n8n/zoominfoToken.test.mjs
.venv/bin/python -m pytest tests -q
```

Result: 45 JS pass; 100 Python pass, 20 xfailed, **1 intentional red** —
`test_tx4_mergecompanies_has_no_handmaintained_enum`, tracking debt this phase introduced.
Phase 12 retires it.
