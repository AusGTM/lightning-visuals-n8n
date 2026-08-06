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
2. Set `enrichment_requested = true` on the record.
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
