# Phase 11 Summary: Company Branch & Provider Contract Hardening

**Status**: Complete
**Completed**: 2026-07-20
**Recorded**: 2026-07-20 (retroactive — executed outside GSD between 2026-07-08 and 2026-07-20)

## Provenance Note

This phase was not planned through GSD. `.planning/STATE.md` had reported the project
100% complete at Milestone 2 since 2026-07-08 while work continued. This summary is
written from the actual session record, not git archaeology. No PLAN.md was produced;
`docs/WEB-RESEARCH-SPEC.md` (written at the end of this phase) serves as the contract for
Phases 13–14.

## What Shipped

### Company enrichment branch (n8n)

A **sibling** branch off the same Manual Trigger, deliberately NOT nested under contacts.
12 nodes: Emit Company Targets → Build Company Identity → HubSpot Company Search → Adapt →
Company Gate → Build Company Requests → Lusha Company → Apollo Org → ZoomInfo Company →
Normalize + Score Company → Merge Company → Decide Company Action. Read-only; no write nodes.

Rationale for sibling-not-nested: the ICP fields are per-domain and expensive, so nesting
would re-pay for every contact at the same company. Company and contact gates also have
different REQUIRED sets and TTL anchors, and different triggers (`enrichment_requested`
/ ICP scan vs CSV upload).

Added a `fan()` builder helper — `chain()` overwrote on node-name collision, so two
branches sharing a trigger needed fan-out.

### mergeCompanies.js

Separate module rather than parameterising `mergeContacts` (user decision: zero regression
risk on a tested module). Companies field policy from `config/field_policy.yaml`, plus two
rules contacts lack: a `domain` hard guard mirroring the contacts `email` guard, and an
evidence-URL gate that runs BEFORE the class branches so an unevidenced ICP claim cannot
promote regardless of how `system_owned` the field is.

### ZoomInfo GTM companies contract (probed live)

`POST /gtm/data/v1/companies/enrich` (`type: CompanyEnrich`) and `companies/search`
(`type: CompanySearch`) confirmed 200. JSON:API, same shape as contacts. The existing
client-credentials token already carries `api:data:company`. 27 valid outputFields
enumerated by individual probe; `companyType` is 400 `PFAPI0009`. The error names only one
invalid field at a time, so batch bisection does not work.

### Three defects found and fixed

1. **ZoomInfo revenue is in THOUSANDS** — `normalizeRevenueBand` expects dollars, so every
   company banded 1000x low. FanDuel's $14.05b read as `5-50M`, which in the rubric earns
   **+10** instead of the **−50** deduction — an inverted ICP signal. Latent until the
   companies path was first invoked. Fixed by preferring the unambiguous `revenueRange`
   string, falling back to `revenue * 1000`. Apollo (dollars) and Lusha (`[lo,hi]` dollars)
   were already correct.
2. **Lusha `/v2/company` wraps the record in `data`** — the live response produced ZERO
   candidates. Headcount is `employees` ("51 - 200", spaced, not the enum form), not
   `companySize`/`employeeCount`.
3. **ZoomInfo `naicsCodes` are `{id,name}` objects**, not code strings — `String(obj)` was
   staging `"[object Object]"` as industry. `primaryIndustry` is an array.

### Cross-provider conflict detector

`harveynorman.com.au` returns three different entities: ZoomInfo "Harvey Norman" `1-5M`,
Apollo "Harvey Norman Seconds World" `5-50M`, Lusha "Harvey Norman" `1B-1.2B` — a 40-point
ICP swing that the scorer was silently resolving by picking one. Conflicting size fields now
withhold promotion and surface as `conflicts` + `needs_review` (CLAUDE.md §17.2).

Also fixed: `scoreCandidates` returns `winners[f] = top.value`, the RAW value. Contacts get
away with it (Apollo's `sanitized_number` is already E.164); companies would have written
`"$1 mil. - $5 mil."` into `lv_revenue_band`. The company branch reads
`best[f].normalizedValue`; `scoreEnrichment` was deliberately NOT changed, because raw
`winners` is load-bearing for contact jobtitle casing.

### Taxonomy + spec

`config/taxonomy.yaml` (`lv-taxonomy-v1`) as normative vocabulary, and
`docs/WEB-RESEARCH-SPEC.md` with 30 numbered requirements that the test suites cite by ID.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Companies is a sibling branch, not nested under contacts | ICP fields are per-domain; nesting re-pays per contact |
| `mergeCompanies.js` separate from `mergeContacts.js` | Zero regression risk on a module with passing tests |
| No entity-resolution / hierarchy modelling | Granularity only corrupts SIZE signals; every other ICP signal is brand-level and inherits down. Provider disagreement already detects it |
| Name-mismatch detection rejected | Blind to the identical-name case that actually costs (ZoomInfo "Harvey Norman"); its only true positive is already caught by the conflict detector |
| No blanket human gate on `lv_produces_content: false` | The queue self-targets — no-content retailers land `Unscored` (no queue), plausible prospects land `Needs Review` |
| Resolution ordered deterministic → retrieval → judgement | An LLM judging from recall is least reliable exactly where the ICP lives |

## Verification

- JS: 45/45 pass (`parity`, `enrichment`, `zoominfoToken`)
- Python: 100 pass, 20 xfailed (spec acceptance tests, `strict=True`), **1 failed**
- All 11 new Code nodes pass `node --check`
- The contacts `ZoomInfo Enrich` node was proven **byte-identical** before and after the
  `_zoom_preamble()` refactor

**Known red: `test_tx4_mergecompanies_has_no_handmaintained_enum`.** This is intentional and
tracked. `mergeCompanies.js:27` carries a hand-typed copy of the evidence-gated org_type
list — debt introduced in this phase. The drift guard caught it on first run. Phase 12
retires it.

## Files

**New:** `n8n/code/mergeCompanies.js`, `config/taxonomy.yaml`, `docs/WEB-RESEARCH-SPEC.md`,
`tests/test_taxonomy_conformance.py`, `tests/test_web_research_spec.py`,
`tests/fixtures/enrichment/zoominfo_live_company.json`

**Modified:** `n8n/code/normalizeProviders.js`, `scripts/build_cloud_workflows.py`,
`tests/n8n/enrichment.test.mjs`, `tests/n8n/parity.test.mjs`, `tests/test_scaffold.py`,
three regenerated workflow JSONs

## Carried Forward

- TX-4 red until Phase 12
- `RT-5` blocked: research caching needs metadata properties that do not exist in portal 22617666
- **`lv_icp_fit_score` is `calculated: true`, `readOnlyValue: true`** — the pipeline CANNOT
  write it, contradicting CLAUDE.md §29. Needs a product decision (Phase 15)
- **`lv_icp_tier` options are `A,B,C,D` only** but the scorer also emits `Unscored` and
  `Needs Review` — writing those fails today. Live bug, independent of this work
- **`lv_org_type` is `string/text`, not an enumeration** — no CRM-level guard, so the
  normalizer is the only barrier
