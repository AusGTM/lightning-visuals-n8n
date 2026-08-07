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

---

## 2026-08-07 — remaining VETO-01/02 human-verification items closed

**Purpose:** live proof of the two items 40-VERIFICATION.md left `human_needed` —
the no-content and hardware-vendor vetoes individually (VETO-01 had only proven
non-ANZ), and the symmetric clear on a real PATCH (VETO-02/F6).

### Setup

Three disposable companies, no domain/website (mirrors the `280155690475` shape above),
created directly via the HubSpot API (not gated — same as this document's own setup):

| Case | Record id | Inputs | Purpose |
|---|---|---|---|
| D1 | `280205875649` | AU, `lv_produces_content=false`, hardware=false | no-content veto |
| D2 | `280234186174` | AU, content=true, `lv_is_hardware_vendor=true` | hardware-vendor veto |
| D3 | `280234186175` | US, content=true, hardware=false | non-ANZ veto (cycle 1), then clear (cycle 2) |

SJ-3 execution **2080** (started `2026-08-06T23:30:11Z`) matched exactly these three
ids — batch purity confirmed via a read-only re-scan of `scheduled_arm.
find_latest_sj3_batch` before ever handing an arm command to the operator.

### Bug 1 (found in Cycle 1 attempt #1): `scheduled_arm.py` never chunked the dispatch

The operator's first arm cycle armed and disarmed cleanly, but the dispatch was refused:
`"Request carries 3 events, more than this backend can enrich in one request — the
limit is 2 record(s) per request. Nothing was enriched."` Nothing was written.

**Root cause:** `scheduled_arm.py` sent the whole SJ-3-matched batch as ONE webhook POST
regardless of size, ignoring the backend's own cap (`ENRICH_MAX_LIST_RECORDS = 2`,
`scripts/build_cloud_workflows.py:3540`, mirrored client-side by the `max_records_per_chunk`
config key every other dispatch caller in the plugin already reads via `chunking.py`).

**Fix (commit `bf9cecd`):** reuse `chunking.plan_chunks`/`chunking.dispatch_plan`
(already used by `preingest.rerequest_unanswered`/`preview_enrichment`) inside the same
armed window — one arm covering the whole batch's allowlist, dispatch chunked into
`<=max_records_per_chunk` POSTs, guaranteed single disarm after all chunks. Locked with
3 new tests (batch-of-3 → 2+1 chunked dispatch in one arm window; a partial chunk
failure stays visible in `results`/`failed_batch` rather than silently folding into a
false-clean outcome; missing ceiling config refuses before any arm). Both suites green
(root 2307/118 skipped, plugin 1284/5 skipped) before re-checkpointing.

### Cycle 1 (post-fix): all three vetoes fire, but with a spurious prefix

Operator re-ran the arm command. Outcome: `dispatched`, `chunk_count: 2`, both chunks
`ok: true`. Independent GETs (execution ~`03:02Z`):

| Record | `lv_anti_icp_flag` | `lv_anti_icp_reason` |
|---|---|---|
| D1 | `"true"` | `"Non-ANZ geography; No broadcast or streaming content"` — **unexpected prefix** |
| D2 | `"true"` | `"Non-ANZ geography; Hardware/AV/LED vendor, not sports-media buyer"` — **unexpected prefix** |
| D3 | `"true"` | `"Non-ANZ geography"` — exactly correct (D3 IS non-ANZ) |

D1/D2 are true-AU records; a non-ANZ veto firing on them alongside their correct reason
is the F4 failure mode reborn in the derivation, not a re-proof of VETO-01 as written.

### Bug 2: `existingRecord.lv_country_region_normalized` never fetched

Diagnosed directly from live n8n execution data (read-only GETs against executions
2150/2152/2155/2157/2160 of `LV Enrichment (Cloud template)`, walking the `Merge
Company`/`Validate Research Output`/`Decide Company Action` node runData for D1/D2):

- `existingRecord.lv_country_region_normalized` was `None` in **every** execution for
  D1 and D2, despite both carrying `lv_country_region_normalized="AU"` live in HubSpot.
- `research_candidate.matched` was `false` in every execution (fake companies, no
  domain — research legitimately found nothing), so `merge.canonicalPatch.
  lv_country_region_normalized` was also never set (correctly gated by
  `mergeCompanies.js`'s own `if (rc && rc.matched)` check).
- With both the fresh-candidate path and the existing-value fallback empty,
  `ENRICH_DECIDE_CO_CLOUD`'s `properties.lv_country_region_normalized ?? existing.
  lv_country_region_normalized` resolved to `undefined`, and `_regionKey(undefined)`
  returns `"non_anz"` — firing "Non-ANZ geography" on every company whose region
  wasn't freshly re-promoted that run, true-AU or not.

**Root cause:** `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` (the ONE property list feeding
both `HubSpot Company Search` and `HubSpot Company Fetch By Id`) never requested
`lv_country_region_normalized`. `lv_produces_content`/`lv_is_hardware_vendor` were
already present, which is why only the region veto fired spuriously. Same class of gap
WR-01 already fixed for `lv_sponsorship_reliant` (18-REVIEW.md) — one property short of
covering the field that actually feeds a hard veto.

**Fix:** added `lv_country_region_normalized` to the one CSV declaration (feeds only
HTTP search-node parameters, moves zero Code-node fingerprints — confirmed via
`test_companies_factory_frozen.py` staying green), rebuilt `n8n/wf_enrichment_cloud.json`
deterministically. Locked with a Python CSV-membership pin
(`test_hubspot_properties_config.py`) and a chained Merge-Company-then-Decide-Company-
Action Node fixture (`tests/n8n/decideCompanyActionRegionFallbackNoSpuriousVeto.test.mjs`,
4 cases: existing-AU-with-unmatched-research fires no veto; existing-US still vetoes
correctly; existing-AU-with-no-content-veto fires ONLY that reason; existing-AU-with-
hardware-veto fires ONLY that reason). Root suite 2308/118 skipped, Node suite 625/625,
both green before deploy.

**Deploy:** n8n serves a running workflow's pre-PUT content until deactivated/reactivated
(the same mechanism `n8n_arming` already brackets for the write-safety flags — proven
live 2026-08-03). Operator ran `DRY_RUN=false ALLOW_N8N_DEPLOY=true python
scripts/deploy_n8n_workflows.py` (200 on all 5 workflows), then bounced every active
workflow via the n8n Cloud UI (deactivate/activate, 200 each; `LV Review Decision` was
already inactive and correctly skipped). Confirmed via a fresh, read-only SJ-3 batch
scan: execution **2167** (started `2026-08-07T03:30:11Z`, after the bounce) matched
exactly the three disposables — no foreign ids.

Meanwhile D3 was corrected directly (no arm needed — a plain property write on the
team's own disposable, same as the original setup): `lv_country_region_normalized` →
`"AU"`, re-queued (`lv_enrichment_requested="true"`, `lv_enrichment_status="queued"`).
D1/D2 needed no touch — both still carried `lv_enrichment_requested="true"`/
`status="complete"` (never reset by the pipeline), so SJ-3's own filter
(`requested=true AND status != running`) kept re-matching all three together.

### Cycle 2 (post-fix, post-deploy): corrected proof

Operator ran the arm command a second time. Outcome: `dispatched`, `chunk_count: 2`,
both chunks `ok: true`, disarm clean. Independent GETs (this session, `~03:33Z`):

| Record | `lv_anti_icp_flag` | `lv_anti_icp_reason` | `lv_icp_tier` |
|---|---|---|---|
| D1 (`280205875649`) | `"true"` | `"No broadcast or streaming content"` | `D` |
| D2 (`280234186174`) | `"true"` | `"Hardware/AV/LED vendor, not sports-media buyer"` | `D` |
| D3 (`280234186175`) | `"false"` | `""` | `C` |

No spurious prefix on D1/D2. D3's `lv_anti_icp_flag` flipped `"true"` → `"false"` on a
real PATCH with `lv_anti_icp_reason` cleared to `""` — the symmetric-clear proof
(VETO-02/F6), no one-way latch. D3's `lv_icp_tier` also moved off `D` to `C` on the same
event (VETO-03 corroboration, already independently proven in 40-06).

Gate re-verified disarmed via `scripts/verify_live_write_safety.py` (12 declaring nodes
across 5 workflows, `VERDICT: disarmed PASS`) — all `ALLOW_HUBSPOT_*` flags `"false"`,
both allowlist constants `""`, no disagreement.

### Cleanup

- `DELETE companies/280205875649, 280234186174, 280234186175` → `204` each.
- Portal-wide sweep (`CONTAINS_TOKEN "ZZ-SCORING-TEST-DELETE-ME"`) → `0` survivors.

### Conclusion

VETO-01 is now live-PATCH-proven for all three hard vetoes individually (non-ANZ from
this document's earlier setup section, no-content and hardware-vendor from this run),
each with the rubric-correct reason string and no cross-contamination between them.
VETO-02/F6 is live-PATCH-proven: a real record's veto flag and reason both clear on
correction, no one-way latch. Two real defects were found and fixed along the way
(`scheduled_arm.py`'s missing dispatch-chunking, and the company existingRecord fetch's
missing `lv_country_region_normalized`) — both would have silently corrupted future
scheduled-poller runs had this evidence-gathering pass not exercised them against a real
armed window. Per-run bounded arming (`scheduled_arm.py` + `WINDOWS.md` #5) remains the
operational model; nothing here permanently flips `WRITE_SAFETY_DEFAULTS`.
