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

Two pre-existing, out-of-scope infrastructure defects were found blocking the refresh path
below. Neither was introduced by 40-03 (the veto derivation code itself is confirmed
correct — see 40-03-SUMMARY.md's Live Validation Findings); both block **every** write
through this pipeline, not just the veto fields.

1. **All HubSpot record writes are globally disabled in the currently deployed build —
   STILL OPEN (WINDOWS.md #2).** `scripts/build_cloud_workflows.py`'s `WRITE_SAFETY_DEFAULTS`
   bakes `ALLOW_HUBSPOT_RECORD_WRITES = "false"` into every build this repo has ever
   produced — this is not an env var, it is a Python-source literal compiled into the Code
   node at build time. A live webhook-triggered run against a disposable company on
   2026-08-06 confirmed the Decide Company Action node computes
   `lv_anti_icp_flag`/`lv_anti_icp_reason` correctly (as quoted strings) but returns
   `"action":"write_blocked"` and never PATCHes HubSpot. **No enrichment run — poller or
   webhook — can write to a real company record until this is armed.** Investigated
   2026-08-06 (ad-hoc fix-40 between 40-04 and 40-05): permanently flipping the build-time
   default is NOT a simple flag flip — `ALLOW_HUBSPOT_RECORD_WRITES` is a load-bearing
   safety invariant across THREE systems (`scripts/deploy_n8n_workflows.py`'s
   `ENABLE_BAKED_FLAGS` deploy-time overlay, `operator-claude-plugin`'s
   `arm_for_dispatch()`/`armed_window` arm-verify-disarm cycle from Phase 28, and
   `scripts/verify_live_write_safety.py`'s dedicated live-state verifier); a spike that
   flipped the default broke 64 tests across both packages and was reverted. This is a Rule
   4 architectural decision requiring explicit operator sign-off, not something an
   automated fix session should push through. **Two scoped arm mechanisms already exist and
   need no code change:**
   - `operator-claude-plugin`'s `arm_for_dispatch()`/`armed_window` arms writes for exactly
     one manual dispatch, scoped to the record ids/domains in that dispatch, then disarms
     automatically — usable **today**, via the `enrich-records` skill, to run the refresh
     path below against one specific company without waiting for the scheduler.
   - `scripts/deploy_n8n_workflows.py`'s
     `ENABLE_BAKED_FLAGS=ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=<id>` deploy-time
     overlay, for a scripted canary against one record.

   **Neither covers the autonomous SJ-1/SJ-2/SJ-3 scheduled poller** — nothing arms a
   write window around a cron tick. A persistent write path for the scheduled refresh
   procedure below (step 3), and for 40-05's veto-branch deletion, requires an operator
   decision between building a new bounded "scheduled arm" companion job or the
   permanent-flip refactor (both out of this fix session's scope).
2. **SJ-3 (the 15-minute requested-enrichment poller) could not dispatch to enrichment at
   all — FIXED, pending deploy (WINDOWS.md #3).** Its `SJ-3 Dispatch To Enrichment` node
   calls `LV Enrichment (Cloud template)` via n8n's Execute-Workflow "call another
   workflow" mode, which requires the CALLED workflow to expose an Execute Workflow
   Trigger node — that target workflow's only entry point was a Webhook Trigger node, so
   every SJ-3 run that found a non-empty search result errored with `NodeOperationError:
   Missing node to start execution` (live n8n executions 1891, 1893, both reproduced
   against real disposable companies with `lv_enrichment_requested="true"` set).
   **Fixed** (ad-hoc fix-40): the enrichment workflow now also exposes a passthrough
   Execute Workflow Trigger, wired as a second entry point into `Parse HubSpot Event`;
   SJ-3's dispatch chain gained a "SJ-3 Build Dispatch Event" node reshaping the poller's
   matched rows into the event shape the parser expects. Built, tested, rebuilt
   deterministically — **not yet deployed to n8n Cloud** (disarmed dry-run diff reviewed;
   see the fix-40 checkpoint for the exact deploy command and node-level diff).

Until blocker 1 is resolved, the only way to exercise the Decide Company Action node with
an actual HubSpot write is through one of the two scoped arm mechanisms above (record-
scoped, temporary) or a direct POST to the workflow's own webhook
(`{N8N_URL}/webhook/hubspot/enrichment/event`, header `X-Enrichment-Secret`) while armed —
an unarmed POST still returns `"action":"write_blocked"`.

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
   immediate. Once WINDOWS.md #3's fix is deployed and bounced, the poller successfully
   *dispatches* to enrichment again — but the dispatched run still needs the write gate
   armed (WINDOWS.md #2, still open) to actually PATCH the record. Until an operator
   decision resolves #2 for the scheduled path, step 3 will reliably *reach* Decide
   Company Action but the write itself will be `"action":"write_blocked"` unless armed by
   one of the two scoped mechanisms in Known Blockers above.
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
