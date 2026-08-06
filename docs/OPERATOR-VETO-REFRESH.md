# Operator procedure: refreshing a stale `lv_anti_icp_flag` / `lv_anti_icp_reason`

**Applies from:** Phase 40 Plan 03 (D-01/D-02, `.planning/phases/40-scoring-engine-remediation-notes/40-CONTEXT.md`)

## What changed

`lv_anti_icp_flag` and `lv_anti_icp_reason` are now derived by the n8n pipeline — the
Decide Company Action node inside `LV Enrichment (Cloud template)` — on every enrichment
run, from three canonical inputs already on the record:

- `lv_country_region_normalized`
- `lv_produces_content`
- `lv_is_hardware_vendor`

This is a direct port of `src/icp_scoring.py`'s hard-veto block (lines 84–97), byte-
identical to the rubric oracle every fix in this phase is checked against
(`tests/test_scoring_parity.py`). No HubSpot-native workflow writes this field anymore
after 40-05 removes the Geography flow's veto branch — the pipeline is the sole writer
(D-01, HANDOVER §5 decision 2).

## KNOWN BLOCKERS (found during 40-03 Task 3 live validation, 2026-08-06)

Two pre-existing, out-of-scope infrastructure defects currently prevent the refresh path
below from working at all. Neither was introduced by 40-03 (the veto derivation code
itself is confirmed correct — see 40-03-SUMMARY.md's Live Validation Findings); both
block **every** write through this pipeline, not just the veto fields.

1. **All HubSpot record writes are globally disabled in the currently deployed build.**
   `scripts/build_cloud_workflows.py`'s `WRITE_SAFETY_DEFAULTS` bakes
   `ALLOW_HUBSPOT_RECORD_WRITES = "false"` into every build this repo has ever produced —
   this is not an env var, it is a Python-source literal compiled into the Code node at
   build time. A live webhook-triggered run against a disposable company on 2026-08-06
   confirmed the Decide Company Action node computes `lv_anti_icp_flag`/`lv_anti_icp_reason`
   correctly (as quoted strings) but returns `"action":"write_blocked"` and never PATCHes
   HubSpot. **No enrichment run — poller or webhook — can write to a real company record
   until this is flipped to `"true"`, rebuilt, and redeployed.** That flip is a deliberate
   rollout gate (CLAUDE.md §25.5's phased ramp), not something this validation task should
   change unilaterally.
2. **SJ-3 (the 15-minute requested-enrichment poller) cannot dispatch to enrichment at
   all.** Its `SJ-3 Dispatch To Enrichment` node calls `LV Enrichment (Cloud template)` via
   n8n's Execute-Workflow "call another workflow" mode, but that target workflow's only
   entry point is a Webhook Trigger node — Execute-Workflow calls require an Execute
   Workflow Trigger node, which does not exist there. Every SJ-3 run that finds a
   non-empty search result errors with `NodeOperationError: Missing node to start
   execution` (live n8n executions 1891, 1893, both reproduced against real disposable
   companies with `lv_enrichment_requested="true"` set). **Step 3 below (wait for the
   poller) currently never completes** — the poller runs on schedule and finds the
   record, but the dispatch step it depends on always errors before reaching enrichment.

Until both are fixed, the only way to actually exercise the Decide Company Action node
live is to POST directly to the workflow's own webhook
(`{N8N_URL}/webhook/hubspot/enrichment/event`, header `X-Enrichment-Secret`) — which still
hits the same `ALLOW_HUBSPOT_RECORD_WRITES` gate for the actual PATCH.

## D-02: the stale-flag policy (accepted, not a bug)

The derivation only runs when an enrichment run actually executes for a record. A manual
property fix made directly in HubSpot (correcting `lv_country_region_normalized` from a
typo, for example) does **not** itself recompute `lv_anti_icp_flag` — the flag stays
stale **until the next enrichment run**. This is accepted behavior (D-02), not a defect,
and VETO-02 ("correcting the input clears the flag") is satisfied through the refresh
path below, not by any HubSpot-side trigger reacting to the property edit directly.

## The refresh path

To force a record's `lv_anti_icp_flag` / `lv_anti_icp_reason` to recompute against its
current inputs:

1. Correct the underlying input field(s) on the HubSpot company record
   (`lv_country_region_normalized`, `lv_produces_content`, and/or `lv_is_hardware_vendor`)
   if that is what needs fixing.
2. Set `lv_enrichment_requested = true` on the record (the actual poller-search
   property — see `scripts/build_cloud_workflows.py`'s SJ-3 search filter; the
   unprefixed `enrichment_requested` name that appears in `CLAUDE.md`'s local-MVP
   Python code and in an earlier draft of this document is a different, unrelated
   property from the old local-first prototype and does nothing on the cloud
   pipeline).
3. Wait for the existing 15-minute scheduled poller
   (`LV Scheduled Maintenance (Cloud)` → the requested-enrichment poll job,
   CLAUDE.md §19.1) to pick the record up. Latency is **up to 15 minutes**, not
   immediate.
4. The poller triggers a normal enrichment run against the record, which reaches the
   Decide Company Action node and recomputes both veto fields from the record's current
   (now-corrected) inputs — clearing the flag if no hard veto still fires, or updating the
   reason string if a different veto now applies.

No script, no manual PATCH, and no direct HubSpot workflow edit is needed or supported
for this refresh — routing correction through the same enrichment path the pipeline
already owns is what keeps HubSpot and the parity oracle from drifting apart (D-01's
whole point).

## Pre-existing stale flags on the 712 (F4)

An unknown subset of the 712 existing companies currently carry a stale
`lv_anti_icp_flag = true` written by the Geography flow's AU-spelling bug (F4,
HANDOVER §10.2) before this phase's remediation. **D-02 accepts these staying stale**
until they are naturally refreshed — either by the record's own next enrichment run
(individually, via the refresh path above) or by Phase 41's portfolio-wide backfill,
which is the natural point the whole 712 refresh together. No mass correction is in
scope for Phase 40 (see `.planning/phases/40-scoring-engine-remediation-notes/40-CONTEXT.md`
domain boundary: "No mass backfill of the 712 existing companies... the portfolio-wide
run is Phase 41").

## Deploy mechanics (for whoever runs the next flow/pipeline change)

- Editing `n8n/code/*.js` or `scripts/build_cloud_workflows.py` changes nothing live
  until the workflow JSON is rebuilt (`python scripts/build_cloud_workflows.py`),
  deployed (`scripts/deploy_n8n_workflows.py`), **and the workflow is bounced**
  (deactivated then reactivated) in n8n Cloud.
- A bare PUT to `/api/v1/workflows/{id}` stores the new JSON but does **not** reload a
  running workflow — n8n keeps executing the old in-memory code until the workflow is
  bounced. Confirming a deploy landed by reading the stored JSON back only proves the
  stored content changed, not that live executions are using it.
- `scripts/deploy_n8n_workflows.py` is disarmed by default (`DRY_RUN=true`); arming
  requires both `DRY_RUN=false` and `ALLOW_N8N_DEPLOY=true` in the same invocation.
