# Veto write-path live validation — evidence trail

**Date:** 2026-08-06/07
**Portal:** 22617666 (ap1)
**Purpose:** Live proof, after the fix-40 deploy, that (a) SJ-3's scheduled dispatch now
reaches `LV Enrichment (Cloud template)` (WINDOWS.md #3) and (b) a real HubSpot PATCH
lands `lv_anti_icp_flag` as the string `"true"` via the `scheduled_arm.py` companion
(WINDOWS.md #2). Unlocks 40-05's veto-branch deletion.

## Setup

Both workflows confirmed active via GET `/api/v1/workflows/{id}` (read-only, no writes):

- `LV Enrichment (Cloud template)` (id `950HPb7a1GgSAIyZ`) — `active: true`, carries an
  `Execute Workflow Trigger` node (the fix-40 passthrough entry point).
- `LV Scheduled Maintenance (Cloud)` (id `1fXPuIabz3RsAHgn`) — `active: true`, carries
  `SJ-3 Build Dispatch Event`.

Disposable test company: `ZZ-SCORING-TEST-DELETE-ME-eef8c2cf2c93` (id `280155690475`),
created `2026-08-06T11:00:22.123Z` with veto-firing inputs:

```
lv_country_region_normalized = "US"     (non-AU/NZ -> triggers Non-ANZ geography veto)
lv_produces_content          = "true"
lv_is_hardware_vendor        = "false"
lv_enrichment_requested      = "true"   (poller-search property, NOT `enrichment_requested`)
lv_enrichment_status         = "queued"
```

## Blocker-2 (WINDOWS.md #3) — dispatch reaches enrichment

n8n execution **1931** (SJ-3 tick, started `2026-08-06T11:15:11Z`, ~15 min after the
disposable's creation) matched the record in `SJ-3 Extract Rows`:

```json
{"hs_object_id": "280155690475", "lv_enrichment_requested": "true", "lv_enrichment_status": "queued"}
```

`SJ-3 Build Dispatch Event -> SJ-3 Dispatch To Enrichment` ran with
`executionStatus: "success"`, spawning sub-execution **1932** inside
`LV Enrichment (Cloud template)` — **no "Missing node to start execution" error**
(the exact failure mode WINDOWS.md #3 recorded against executions 1891/1893 pre-fix).
Sub-execution 1932's node trace confirms the full pipeline ran end-to-end:
`Execute Workflow Trigger -> Parse HubSpot Event -> ... -> Decide Company Action`,
`finished: true`, no top-level `resultData.error`.

`Decide Company Action`'s output (execution 1931's dispatch node, item 0):

```json
{
  "action": "write_blocked",
  "hs_object_id": "280155690475",
  "properties": {
    "lv_anti_icp_flag": "true",
    "lv_anti_icp_reason": "Non-ANZ geography",
    "lv_enrichment_status": "complete"
  }
}
```

`write_blocked` is the CORRECT outcome at this stage (gate still closed,
`ALLOW_HUBSPOT_RECORD_WRITES` baked `"false"`) — the veto derivation itself is already
proven correct (computed values match the disposable's US-region input). Confirmed on
two further ticks that kept re-matching the still-queued record: execution **1934**
(`11:30:11Z`) and execution **1937** (`11:45:11Z`), each with `SJ-3 Extract Rows`
matching `hs_object_id: "280155690475"` again.

**Verdict: WINDOWS.md #3 fully resolved — the poller's dispatch chain reaches
enrichment on every tick, with zero infrastructure errors.**

## Blocker-1 (WINDOWS.md #2) — scheduled-arm companion write

Operator ran one companion cycle (`ALLOW_N8N_ARM=true python3
operator-claude-plugin/scripts/scheduled_arm.py`), which discovered the still-matched
disposable off SJ-3's own execution history and re-dispatched it through its own bounded
arm window.

Companion cycle result: `outcome: "dispatched"`, `record_ids: ["280155690475"]`,
`execution_id: 2048` (the SJ-3 tick it read the batch from).

**Arm phase:** `ALLOW_HUBSPOT_RECORD_WRITES` flipped `"false" -> "true"`, scoped via
`TEST_RECORD_IDS = "280155690475"` (exact-match allowlist, no domain grant).

**Dispatch result (companion's own report):** record PATCHed —
`lv_anti_icp_flag="true"`, `lv_anti_icp_reason="Non-ANZ geography"`,
`lv_enrichment_status="complete"`, `updatedAt: 2026-08-06T20:29:44.349Z`.

**Disarm phase (companion's own report):** `ALLOW_HUBSPOT_RECORD_WRITES="false"`,
`ALLOW_HUBSPOT_CREATE="false"`, `TEST_RECORD_IDS=""`, `TEST_RECORD_DOMAINS=""`.

### Independent verification (this session, not trusting the companion's self-report)

GET `companies/280155690475` (fresh HubSpot read):

```json
{
  "lv_anti_icp_flag": "true",
  "lv_anti_icp_reason": "Non-ANZ geography",
  "lv_enrichment_status": "complete",
  "hs_lastmodifieddate": "2026-08-06T20:29:44.349Z"
}
```

Matches the companion's reported PATCH exactly — `lv_anti_icp_flag` landed as the
**literal string `"true"`** (not a boolean), reason string correct, timestamp matches.

GET `LV Enrichment (Cloud template)` and re-scanned every declaring node
(`read_write_safety`, scans all nodes carrying the constant, reports disagreement if any
desync exists):

| Flag | Value | Declaring nodes | Disagreement |
|---|---|---|---|
| `ALLOW_HUBSPOT_RECORD_WRITES` | `"false"` | Decide Action, Decide Company Action | none |
| `ALLOW_HUBSPOT_CREATE` | `"false"` | Decide Action, Decide Company Action | none |
| `ALLOW_HUBSPOT_REVIEW_WRITES` | `"false"` | Decide Action, Decide Company Action | none |
| `TEST_RECORD_IDS` | `""` | Decide Action, Decide Company Action | none |
| `TEST_RECORD_DOMAINS` | `""` | Decide Action, Decide Company Action | none |

Confirms the window closed cleanly — a single consistent value across both declaring
nodes, no partial-desync.

**Verdict: WINDOWS.md #2 fully resolved — the scheduled-arm companion successfully
arms a bounded window, PATCHes the target record with the derived veto fields as
strings, and disarms, all independently confirmed.**

## Cleanup

- `DELETE companies/280155690475` -> `204`.
- Portal-wide sweep (`CONTAINS_TOKEN "ZZ-SCORING-TEST-DELETE-ME-"`) -> `0` survivors.

## Conclusion

Both pre-existing infrastructure blockers recorded in `docs/OPERATOR-VETO-REFRESH.md`'s
Known Blockers section are now live-proven resolved:

1. The SJ-3 scheduled poller's dispatch chain reaches `LV Enrichment (Cloud template)`
   without error (WINDOWS.md #3).
2. The `scheduled_arm.py` companion grants a bounded write window that lands
   `lv_anti_icp_flag`/`lv_anti_icp_reason` as strings via a real HubSpot PATCH, then
   disarms cleanly (WINDOWS.md #2).

40-05's veto-branch deletion (removing the Geography flow's now-redundant veto branch,
per D-01) is unblocked.
