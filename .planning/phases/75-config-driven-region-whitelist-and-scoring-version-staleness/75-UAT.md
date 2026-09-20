---
status: testing
phase: 75-config-driven-region-whitelist-and-scoring-version-staleness
source: [75-06-PLAN.md]
started: 2026-09-20
updated: 2026-09-20
---

# Phase 75 — Exit UAT (plan 75-06 Task 1)

Every live call in this document was run by the OPERATOR from the interactive shell (`!`
prefix, `.env` sourced inline); the orchestrator composed the commands and verified each result
from the artefact it produced. Operator selected `proceed` at the plan 06 Task 0
`checkpoint:decision` (`gate="blocking-human"`).

## Deploy + bounce (DISARMED) — see 75-DEPLOY-RECORD.md

## Proof companies — chosen and stated BEFORE any send

Selected by read-only HubSpot search (`lv_country_region_normalized` EQ code, `lv_org_type`
HAS_PROPERTY). No `EU`, `UK` or `Unknown`-stamped company exists live (totals 0/0/0);
`Other`-stamped total is **5** (input to Task 2's D-75-05 sizing).

### (a) Whitelisted — Melbourne Racing Club, HubSpot id `9604614548`

Pre-send properties (read-only): `lv_country_region_normalized = AU`,
`lv_anti_icp_flag = false`, `lv_anti_icp_reason = null`, `lv_org_type = individual_club_team`,
`lv_produces_content = true`, `lv_icp_fit_score = 60` (named-account floor),
`lv_icp_scoring_version = null`.

**Expected, written before sending:** the row reaches `Decide Company Action` through the
recompute lane (`IF Company Recompute` true branch), the derived veto carries **NO** geography
reason (`AU` ∈ `regions.home`), `lv_anti_icp_flag` derives `false`, and the write returns
`write_blocked` (`ALLOW_HUBSPOT_RECOMPUTE_WRITES` and `ALLOW_HUBSPOT_RECORD_WRITES` both
`"false"`). No provider (`Lusha`/`Apollo`/`ZoomInfo`), research or judge node runs. The record
is byte-unchanged afterwards.

### (b) Non-whitelisted — Jam TV, HubSpot id `17317850381`

Pre-send properties (read-only): `lv_country_region_normalized = Other` (native
`country = Italy`), `lv_anti_icp_flag = true`, `lv_anti_icp_reason = "Non-ANZ geography"`
(the legacy string, stamped before this phase), `lv_org_type = broadcaster`,
`lv_produces_content = true`, `lv_icp_fit_score = 40`, `lv_icp_scoring_version = null`.

**Expected, written before sending:** the derived veto carries **exactly one** geography reason,
byte-equal to `Outside target regions` (D-75-01's renamed string; `Other` is a KNOWN code outside
`regions.home`), `lv_anti_icp_flag` derives `true`, and the write returns `write_blocked`, so the
record keeps its legacy `"Non-ANZ geography"` string until the operator's first armed sweep
(D-75-03/D-75-14). No provider, research or judge node runs.

### Both

Exactly **two** new n8n executions on `LV Enrichment (Cloud template)` `950HPb7a1GgSAIyZ`
(baseline max id `12677`), none on `LV Scheduled Maintenance (Cloud)` `1fXPuIabz3RsAHgn`
(baseline max id `12681`), and no further execution during the two-minute post-send watch.

## Observed

_(pending — filled after the sends)_
