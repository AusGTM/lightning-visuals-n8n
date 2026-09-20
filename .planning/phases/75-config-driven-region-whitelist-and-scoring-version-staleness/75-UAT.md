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

Sends (`scripts/remediate_veto_companies.post_webhook_event(cid, True, cfg, recompute=True)`,
operator shell, cfg = `N8N_URL` + `N8N_ENRICHMENT_WEBHOOK_SECRET`, secret never printed):

| company | status | run_id | ack |
| --- | --- | --- | --- |
| `9604614548` Melbourne Racing Club | 200 | `8e22341377d049dfb172adcae28b42ec` | `{"accepted": true, "row_ids": []}` |
| `17317850381` Jam TV | 200 | `2d591712527e4f789c43f9d6098f59b9` | `{"accepted": true, "row_ids": []}` |

Executions: `12682` (MRC, `2026-09-20T11:06:11.816Z`, success) and `12683` (Jam TV, success) on
`950HPb7a1GgSAIyZ`. Both frozen, redacted, as NEW fixtures
`tests/n8n/fixtures/frozen/exec_12682.runData.json` / `exec_12683.runData.json`
(`freeze_execution_rundata.py`, `freeze_rc=0`; `frozenFixtureSecrets` + walker fidelity +
v1 recordings guards 13/13). No existing frozen file modified.

### (a) `9604614548` — observed vs expected: **MATCH**

From `exec_12682.runData.json` (71 nodes ran): `IF Company Recompute` and its
`-> Decide Company Action Merge Pass-Through` ran; `Decide Company Action` ran once, 1 item:
`properties.lv_anti_icp_flag = "false"`, `properties.lv_anti_icp_reason = ""` (NO geography
reason), `properties.lv_icp_scoring_version = "lv-icp-v0.2"` (the stamp, D-75-03). `HubSpot
Company Update Write Gate` refused → `HubSpot Company Update All Refused Sentinel`; the real
`HubSpot Company Update` node never ran. `Build Response`: 1 item, `action: "write_blocked"`,
`hs_object_id: "9604614548"`. Provider/research/judge nodes that ran: **none** (no `ZoomInfo
Mint`, `Apollo Org`, `Lusha Company`, `Claude Web Research`, `Judge Call`).

### (b) `17317850381` — observed vs expected: **MATCH**

From `exec_12683.runData.json` (71 nodes ran): same lane. `Decide Company Action` 1 item:
`lv_anti_icp_flag = "true"`, `lv_anti_icp_reason = "Outside target regions"` — exactly one
reason, byte-equal to the D-75-01 string; `lv_icp_scoring_version = "lv-icp-v0.2"`. Write
`write_blocked`; provider/research/judge nodes: **none**.

Decide's own row `action`/`reason` reads `enrich` / "missing: lv_sponsorship_reliant,
lv_is_hardware_vendor, lv_is_gambling_operator" (and for MRC "all required fields present,
fresh and valid") — the D-75-12 routing reuses the gate's classification; the veto is derived
regardless and the write is what the flag blocks. Not a finding.

### Both — **MATCH**

Exactly two new executions (`12682`, `12683`; baseline `12677`), none on maintenance (`12681`
before and after). Post-send watch (`sleep 130` inside the operator's command, then re-list):
enrichment max `12683`, maintenance `12681` — no burst. 0 provider credits, 0 Anthropic calls.

### Post-send record re-read

_(pending — operator read-only GET of both records)_

## Summary

total: 3
passed: 3
issues: 0
pending: 0 (record re-read is confirmatory)
skipped: 0
blocked: 0

## Gaps

None. No FINDING raised: every observed verdict equals the expectation written before sending.

