# SJ-3 gate / drain / cap — live evidence trail (Phase 44 Plan 03)

**Date:** 2026-08-10 (in progress)
**Portal:** 22617666 (ap1)
**Purpose:** Live proof that (a) a gate-closed SJ-3 tick costs exactly one execution and
zero `LV Enrichment (Cloud template)` sub-executions (GATE-01, discharging research
assumption A1), (b) the tick emits the named `SJ-3 Tick Outcome` item (GATE-02), and
(c) the drain lands `lv_enrichment_requested="false"` + `lv_enrichment_status="skipped"`
on a seeded disposable, judged by HubSpot read-back (DRAIN-01).

## Pre-deploy state (2026-08-10, this session)

Precondition (Task 1): **no arm window open** — confirmed two ways:

1. No `scheduled_arm.py` process running (`ps aux` — zero matches).
2. Live `verify_live_write_safety.py` (disarmed expectation): 5 workflows fetched,
   12 declaring nodes, every declaring node reads
   `ALLOW_HUBSPOT_RECORD_WRITES="false"`, `ALLOW_HUBSPOT_CREATE="false"`,
   `ALLOW_HUBSPOT_REVIEW_WRITES="false"`, `TEST_RECORD_IDS=""`, `TEST_RECORD_DOMAINS=""`.
   Sole FAIL line: `ALLOW_SJ3_DRAIN_WRITES is declared by no node in any deployed
   workflow` — the expected interim state 44-01-SUMMARY.md records ("Interim
   live-verifier FAIL window"), which this deploy closes.

Live workflow inventory (GET `/api/v1/workflows`, pre-deploy):

| id | active | name |
|---|---|---|
| `1fXPuIabz3RsAHgn` | true | LV Scheduled Maintenance (Cloud) |
| `950HPb7a1GgSAIyZ` | true | LV Enrichment (Cloud template) |
| `AwbBeShdPgV48eiY` | true | LV Contact Ingest (Cloud template) |
| `Cj83mOgrIm59oxcX` | true | LV Backend Status (Cloud template) |
| `WBJwoZOo63wzeP69` | **false** | LV Review Decision (Cloud) |

`LV Review Decision (Cloud)` is deliberately inactive (operator state) — it receives the
content PUT but is NOT bounced/activated (no running instance to reload; activating it
would be an unrequested mutation, same call the 2026-08-07 deploy made).

Deployed commit: `d8863ac` (44-02 complete; tree clean, suites green
656 node / 2438 pytest / 1286 plugin per 44-02-SUMMARY.md).

## Deploy

Run by the operator in the orchestrating session, 2026-08-10 (agent-side deploy is
denied by the permission classifier per the standing 2026-08-05 rule: deploys are
operator steps; bounce + read-backs are agent steps). Disarmed — no
`ENABLE_BAKED_FLAGS`. Command:

```bash
DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

Verbatim output (exit 0):

```text
Workflows to create: []
Workflows to update: ['LV Backend Status (Cloud template)', 'LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Review Decision (Cloud)', 'LV Scheduled Maintenance (Cloud)']
updated workflow LV Backend Status (Cloud template) (200)
updated workflow LV Contact Ingest (Cloud template) (200)
updated workflow LV Enrichment (Cloud template) (200)
updated workflow LV Review Decision (Cloud) (200)
updated workflow LV Scheduled Maintenance (Cloud) (200)
```

## Bounce

Performed by this session immediately after the deploy, via
`n8n_control.set_active` (each step GETs prior state, POSTs activate/deactivate, then
judges from an independent GET — never from the mutation's own echo). Order: full
deactivate → activate per workflow, one workflow at a time:

| # | Workflow | id | deactivate | activate |
|---|---|---|---|---|
| 1 | LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | verified | verified |
| 2 | LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | verified | verified |
| 3 | LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | verified | verified |
| 4 | LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | verified | verified |

`LV Review Decision (Cloud)` (`WBJwoZOo63wzeP69`) was NOT bounced: it was inactive
before the deploy (operator state), has no running instance to reload, and activating
it would be an unrequested mutation — same call the 2026-08-07 deploy made
(VETO-WRITE-EVIDENCE.md: "was already inactive and correctly skipped").

## Post-bounce write-safety read-back

`verify_live_write_safety.py` (disarmed expectation), run after the bounce — exit 0:

```text
expectation: disarmed
coverage: 5 workflow(s) fetched, 14 declaring node(s) found
drain authority: ALLOW_SJ3_DRAIN_WRITES expected "true", declared by 13 node(s) — PASS
VERDICT: disarmed PASS
```

Every declaring node across all 5 workflows reads the five overlay constants disarmed
(`"false"` / `""`), and `ALLOW_SJ3_DRAIN_WRITES='true'` in all 13 nodes that declare it
— including the two new SJ-3 nodes now visible live: `SJ-3 Dispatch Gate` (declares all
six constants) and `SJ-3 Drain Gate` (declares only the drain authority). The interim
FAIL window recorded in 44-01-SUMMARY.md is closed.

## Seeded disposable

Fresh disposable (280155690475 from the prior evidence is deleted/404 and was not
reused). Created directly via the HubSpot API (same ungated path as the prior
evidence's setup), 2026-08-10:

- **id `280176525780`**, name `ZZ-SCORING-TEST-DELETE-ME-23b8a66814c1`
- created `2026-08-10T02:19:02.950Z`, no domain/website
- seeded properties: `lv_enrichment_requested="true"`, `lv_enrichment_status="queued"`
- Full 272-property baseline GET captured immediately after creation. Non-null
  baseline beyond HubSpot system/pipeline defaults: the two seeded properties plus
  portal-calculated score fields that auto-populate on create
  (`annual_revenue_score="0"`, `geography_score="0"`, `org_type_score="0"`,
  `lv_icp_fit_score="0"` — the calculated-property behaviour PORTAL-FACTS.md records).

**Pre-seed queue state:** SJ-3's exact live predicate
(`lv_enrichment_requested EQ "true" AND lv_enrichment_status NEQ "running"`, read out
of the deployed `SJ-3 Search (requested poller)` node body, not reconstructed) returned
**total=0** before seeding — the tick's drain can touch only the seed (D-06 blast
radius for this observation: one record).

**Post-seed index confirmation:** the same predicate returned `total=1`,
ids=`["280176525780"]` on the first poll — the seed is the entire SJ-3 batch.

**Execution watermark (pre-tick):** latest `LV Scheduled Maintenance (Cloud)`
execution = **11819** (`trigger`, success, `2026-08-09T23:15:17.040Z`); latest
`LV Enrichment (Cloud template)` execution = **11817** (`integrated`, success,
`2026-08-09T23:01:20.540Z`). Anything above these ids is post-bounce activity.

## Observed tick — execution 11820

The public API has no run-now for a schedule trigger (documented 405,
`control_actions.start_scheduled_scan`), and the next natural daily tick was ~21h out
(the 23:00–23:15Z cluster above), so the operator fired a manual execution from the
`SJ-3 Trigger` node in the n8n Cloud UI (the plan's preferred mechanism; SJ-3's trigger
only, no other lane).

- **Execution id 11820**, workflow `LV Scheduled Maintenance (Cloud)`
  (`1fXPuIabz3RsAHgn`), **mode `manual`**, status `success`,
  started `2026-08-10T02:39:30.208Z`, stopped `2026-08-10T02:39:33.219Z`,
  `resultData.error: null`.

### GATE-01 — one execution, zero enrichment sub-executions

Nodes that ran (execution 11820's `runData` keys, complete list):

```text
SJ-3 Trigger, SJ-3 Search (requested poller), SJ-3 Extract Rows, SJ-3 Dispatch Gate,
SJ-3 Build Dispatch Event, SJ-3 Drain Gate, SJ-3 Drain Clear Flag, SJ-3 Tick Outcome
```

**`SJ-3 Dispatch To Enrichment` is absent from runData — it never ran.**
`SJ-3 Build Dispatch Event` ran and emitted **zero items** (`[[]]`) — the gate filtered
its one input row to nothing before the Execute Workflow node.

`LV Enrichment (Cloud template)` executions after the tick: latest id is still
**11817** (`2026-08-09T23:01:20.540Z`, pre-watermark) — **zero sub-executions**
attributable to the tick. Research assumption A1 (`executeWorkflow` "each" mode costs
nothing on zero items) is now an observation, not an inference: a fully gate-closed
tick costs exactly **1** execution.

### GATE-02 — the named outcome item

`SJ-3 Tick Outcome`'s emitted item, verbatim:

```json
{
  "sj3_tick_outcome": "gate_closed",
  "found": 1,
  "permitted": 0,
  "dispatched": 0,
  "declined": 1,
  "deferred": 0,
  "cap": 40
}
```

Consistent counts: `found(1) = permitted(0) + declined(1)`; `deferred = 0`; cap echoes
the baked build-time derivation (40 at daily cadence). The gate's per-row annotation
(`SJ-3 Dispatch Gate` output, one item) carried `sj3_dispatch: false`,
`sj3_drain: true`, and the same `sj3_tick` summary object.

### DRAIN-01 — the drain write, judged from the HubSpot read-back

`SJ-3 Drain Clear Flag` runData: `executionStatus: success`, `executionTime: 678ms`,
fed solely by `SJ-3 Drain Gate`. The PATCH response inside runData
(`requestId 019fe98a-261a-7a61-9938-710eab0659d3`, timestamp `1786329572911` =
`2026-08-10T02:39:32.911Z`) shows exactly two lv-properties written:
`lv_enrichment_requested: "false"` and `lv_enrichment_status: "skipped"`.

Per BUG 10/11/13/18, success is judged from the **independent HubSpot read-back**, not
the node's response. Fresh GET of `280176525780` with the same 272 properties as the
baseline:

- `lv_enrichment_requested = "false"` ✔
- `lv_enrichment_status = "skipped"` ✔

Full 272-property diff (baseline at creation → post-tick), complete:

| Property | Before | After | Attribution |
|---|---|---|---|
| `lv_enrichment_requested` | `"true"` | `"false"` | **drain write** (ts `02:39:32.911Z`) |
| `lv_enrichment_status` | `"queued"` | `"skipped"` | **drain write** (ts `02:39:32.911Z`) |
| `hs_lastmodifieddate` | `02:19:03.386Z` | `02:39:32.911Z` | system timestamp of the drain PATCH |
| `gambling_score` | null | `"0"` | portal flow, `AUTOMATION_PLATFORM`, ts `02:19:05.733Z` (creation enrollment, pre-tick) |
| `produces_content_score` | null | `"0"` | portal flow, `AUTOMATION_PLATFORM`, ts `02:19:05.620Z` (creation enrollment, pre-tick) |
| `lv_icp_tier` | null | `"Unscored"` | portal flow, `AUTOMATION_PLATFORM`, ts `02:19:06.783Z` (creation enrollment, pre-tick) |
| `hs_v2_date_entered_lead` | null | `02:19:02.950Z` | `CALCULATED` rollup at creation |

The four non-drain rows are the portal's own creation-time scoring-flow enrollment
(PORTAL-FACTS.md calculated-property behaviour), timestamped 02:19:02–06Z — twenty
minutes **before** the tick — and landed between record creation and the baseline GET
completing its index. Property history (`propertiesWithHistory`) confirms each source
and timestamp. **Nothing else on the record changed**; the drain touched exactly its
two-key allowlist.

### Post-tick queue state

The SJ-3 predicate search after the tick would return total=0 (the drained record no
longer matches `lv_enrichment_requested EQ "true"`). No production records were drained:
the pre-seed queue was empty (total=0 above), so this tick's decline/drain set was
exactly the one seeded disposable.

## Cleanup

- `DELETE companies/280176525780` → **204**.
- Portal-wide sweep (`CONTAINS_TOKEN "ZZ-SCORING-TEST-DELETE-ME"`, after index lag) →
  **0 survivors**.

## Requirement traceability

| Requirement | Discharged by |
|---|---|
| GATE-01 | **This document**: execution 11820, zero `LV Enrichment (Cloud template)` sub-executions (watermark 11817 unmoved), `SJ-3 Dispatch To Enrichment` absent from runData. |
| GATE-02 | **This document**: `SJ-3 Tick Outcome`'s verbatim `gate_closed` item with consistent counts, seen in real execution data. |
| DRAIN-01 | **This document**: HubSpot read-back of `280176525780` showing both drained values, full-diff-verified that nothing else changed. |
| GATE-03 | Tests (Plan 01/02): `tests/n8n/sj3DispatchGate.test.mjs` (gate-open dispatch order/mutation pin added in 44-02 Task 3) + `tests/n8n/sjPredicates.test.mjs` wiring pins. |
| DRAIN-02 | Test (Plan 01): `tests/test_write_gate_coverage.py::test_drain_write_patch_is_exactly_the_two_pair_allowlist` (key+value allowlist, D-07 as amended). |
| DRAIN-03 | Test (Plan 01): drain provenance `lv_enrichment_status="skipped"` baked-literal assertions in `tests/test_write_gate_coverage.py`; `skipped` written by nothing else in the pipeline (`build_cloud_workflows.py` writes only `needs_review`/`complete`). Live corroboration: the read-back above. |
| CAP-01 | Tests (Plan 02): cap derived from `config/execution_budget.yaml` × `SJ3_TRIGGER_SCHEDULE` (40 at daily, 19 at 12-hourly — `tests/n8n/sj3DispatchGate.test.mjs` + builder assert ≥ 1). Live corroboration: `cap: 40` in the tick outcome above. |
| CAP-02 | Tests (Plan 02): overflow defers (`sj3_dispatch=false`, `sj3_drain=false`), never drained; found-vs-dispatched reported on every tick (`SJ-3 Tick Outcome`). |
| CAP-03 | Test (Plan 02): `tests/test_execution_budget.py` idle-floor guard over every committed `scheduleTrigger` (95.3/month vs 625 ceiling). |

## Known limits, recorded honestly

1. **D-12 scope limit (accepted):** the cap bounds the SJ-3 lane only — webhook and
   operator-initiated dispatch bypass it entirely. Acceptable because SJ-3 is the
   unattended path, the one that ran away; operator-initiated dispatch sits behind the
   plugin's existing cost guard.
2. **Arm-window residual (surfaced at Plan 01's checkpoint, accepted):**
   `scheduled_arm.py` arms only the enrichment workflow; the maintenance workflow's
   baked constants stay disarmed during an armed window. If the window closes between
   the companion's dispatch and the next tick, that tick declines and drains records
   still in flight — clearing the retry flag D-04 says a dispatched-and-failed record
   should keep. Low probability at daily cadence; recoverable via SJ-1/SJ-2 re-queue.
   A `lv_enrichment_status !== "running"` guard was considered and rejected as vacuous:
   nothing in this pipeline writes `"running"` (`build_cloud_workflows.py:2797,2802`
   write only `"needs_review"` and `"complete"`), so the guard could never match an
   in-flight record. Closing the residual properly needs a real in-flight marker —
   its own change, out of this phase's scope.
3. **The observed tick was `mode: manual`,** not a schedule fire — n8n has no API
   run-now for schedule triggers and the next natural tick was ~21h out. The manual
   execution runs the identical node chain from the identical trigger node; the
   schedule's own firing was already proven live (the 23:00–23:15Z tick cluster and
   every prior evidence tick in VETO-WRITE-EVIDENCE.md).
