---
created: 2026-09-20T12:00:00.000Z
updated: 2026-09-20
title: "Five live companies are stamped lv_country_region_normalized = Other; four have a native country now inside regions.home (US x3, ZA x1) but the whitelist cannot rescue them by recompute -- when, if ever, to run a targeted re-enrichment pass"
area: "icp-scoring, hubspot-data"
severity: low
kind: design
decision_needed: "whether and when to run a targeted re-enrichment pass over the four Other-stamped companies whose native country is a regions.home market (17663335094 Daktronics US, 22798600364 New York Racing Association US, 288078696952 Megapro Holdings ZA, 288763144650 NFHS US) so their stored region is rewritten -- versus leaving them vetoed until their next natural enrichment"
owner: operator
files:
  - config/icp_scoring.yaml
  - scripts/build_cloud_workflows.py
---

## Found during

Phase 75 plan 06 Task 2 (D-75-05 sizing, 2026-09-20), read-only HubSpot search.

## Measured (2026-09-20)

- `lv_country_region_normalized = Other`: **5** companies. Native `country`: United States x3,
  South Africa x1, Italy x1. Four resolve into `regions.home` (US, ZA); Jam TV (Italy) does not.
- `lv_anti_icp_flag = true AND lv_anti_icp_reason CONTAINS_TOKEN "Non-ANZ"`: **5** — the same
  five records. All vetoed companies: 20.
- D-75-05 flip count by recompute alone: **0**. The recompute lane reads the STORED region
  (`Other` → known non-home → `Outside target regions`), so the bump sweep refreshes the reason
  string on all five and clears the geography veto on none.

## Fork resolved: RE-ENRICH, not re-derive (plan 06 Task 2)

The alternative — teach the recompute path to re-derive region from native `country` through
`REGION_ALIASES` when the stored region reads `Other` — is refused. It would put two different
answers to "what region is this company" on one record (the derived veto disagreeing with the
stored `lv_country_region_normalized`), and HubSpot flow `4626722240 Geography Score` reads the
STORED property, so the record would still score 0 there while the pipeline's veto said
otherwise. A wrong region needs the region rewritten, which is enrichment, not recompute.

Note: Daktronics (`17663335094`) keeps its veto regardless (hardware vendor, no content).
