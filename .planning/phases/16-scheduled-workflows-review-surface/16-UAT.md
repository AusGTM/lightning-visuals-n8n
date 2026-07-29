---
status: partial
phase: 16-scheduled-workflows-review-surface
source: [16-VERIFICATION.md]
started: 2026-07-23T07:00:00Z
updated: 2026-07-29T17:05:00+10:00
---

## Current Test

[paused — both remaining checkpoints reduce to one prerequisite: activate LV Scheduled Maintenance]

## Tests

### 1. Live operator runbook — deploy + provision + property creation
expected: Run `scripts/provision_n8n_credentials.py` then `scripts/deploy_n8n_workflows.py` (with `N8N_URL`/`N8N_API_KEY`/`ALLOW_N8N_DEPLOY=true`), activate both Cloud workflows, live-create `lv_enrichment_requested`/`lv_enrichment_status`. Both workflows appear active, all nodes credential-bound, pipeline runs live + schedules fire.
result: pass
source: automated
evidence: |
  Completed 2026-07-29, in stages across two sessions:
    - Credentials provisioned earlier; deploys have run repeatedly (executions 10-25).
    - Both SJ-3 properties live-created by the Phase 15 migration (manifest 73c5342c).
    - "LV Enrichment (Cloud template)" active since the 16.7 canary window.
    - "LV Contact Ingest (Cloud template)" ACTIVATED TODAY (HTTP 200) — first time ever.
    - "LV Scheduled Maintenance (Cloud)" activation first 400'd — BUG 20, the
      executeWorkflow node baked the LOCAL template id which never existed server-side —
      fixed by rebind_subworkflow_refs() in the deploy script (88914d5), redeployed, then
      ACTIVATED (HTTP 200).
  All three cloud workflows read back active=true. SCHEDULES FIRE: executions 23 and 24
  (mode=trigger) ran on the 15-minute tick — SJ-3 Search total=0 and Review Search
  total=0, both correct against current portal state. The phase goal's "background
  reconciliation layer runs on schedule" clause is now literally true.

### 2. Live review-loop apply — reviewApply patch actually writes
expected: Flip `lv_enrichment_review_approved=true` on one real needs_review company; the "Apply Review" branch fires and `reviewApply`'s `canonicalPatch`+`clearPatch` reach the record.
result: blocked
blocked_by: write-arming
reason: |
  THE ORIGINALLY STATED BLOCKER IS OBSOLETE (BUG 11's updateFields:{} — closed by 6d2565c;
  the node is a credential-bound PATCH sending {properties: $json.properties}, and
  ENRICH_APPLY_REVIEW emits that key; no operator wiring step remains).

  PROGRESS 2026-07-29: the Review lane's SEARCH half now runs live on schedule —
  execution 24, Review Search (approved=true) HTTP-executed inside n8n, total=0 (no
  approved record exists, correctly). What remains is only the WRITE half: flipping a real
  record to approved and letting Review Apply Update PATCH it requires arming
  ALLOW_HUBSPOT_RECORD_WRITES with an allowlist, and the permission classifier refuses the
  arming deploy (it allowed the disarmed one). Writes stay off; the gate denies.

### 3. Real HubSpot webhook event shape — identity resolves by objectId
expected: Send a real company-object webhook event (objectId/objectType/subscriptionType only, no email/domain/firstname); identity resolves to the correct company and enrichment runs end to end.
result: pass
source: automated
evidence: |
  The stated blocker — "Build Identity/Build Company Identity still read direct body
  fields, not fetch-by-objectId; a follow-up fetch-by-id node (plan-scoped-out) is needed"
  — was precisely the scope of Phase 16.4, which added those nodes and the by-node-name
  adapters.

  Offline: `tests/n8n/bareEventChainFlow.test.mjs` drives the compiled workflow from a seed
  containing ONLY {objectId, objectType, subscriptionType, propertyName, occurredAt} and
  lands on a patch keyed to the FETCHED record id, on both branches.

  Live: `HubSpot Company Fetch By Id` returned {total:1, results:[real record]} in execution
  12; execution 19 ran the companies branch end to end (Company Gate enrich, providers,
  Merge Company non-null). 16.4's unproven precondition — that `hs_object_id` is actually
  filterable on CRM v3 search — was measured directly on 2026-07-29; see 16.4-UAT.md.

  Not claimed: that all six company search nodes work live. That is 16.6 criterion 1,
  currently 2 of 6, tracked in that phase.

## Pre-live-deploy follow-ups (from VERIFICATION.md, not gating the offline deliverable)

- ~~**[fix before first live deploy] `deploy_n8n_workflows.py` globs all `wf_*.json`**~~ —
  **RESOLVED.** `scripts/deploy_n8n_workflows.py:175` now reads "Deploy ONLY the
  Cloud-targeted workflows (`wf_*_cloud.json`)", so the local-replica fixtures that
  legitimately keep `$env`/`$vars` are excluded and cannot import as unbound on Cloud.
- ~~Item 2's `updateFields:{}`~~ — **RESOLVED** by 6d2565c (see test 2).
- ~~Item 3's fetch-by-id shim~~ — **RESOLVED** by Phase 16.4 (see test 3).

All three pre-live wiring items are closed. None of them is what still blocks this phase.

## Summary

total: 3
passed: 2
issues: 0
pending: 0
blocked: 1
skipped: 0

## Gaps

[none — the remaining blocked test is a prerequisite gate (write arming), not a code defect]

## Notes

2026-07-29, second pass: activation happened. All three cloud workflows are active; the
15-minute schedules fire (executions 23/24); the contact-ingest webhook serves uploads end
to end (execution 25, {"queue":"needs_review"}). Getting there surfaced and closed three
more live-only bugs — BUG 20 (executeWorkflow baked the local template id; activation
400'd), BUG 21 (Set Config dropped the webhook's binary CSV; first upload died at
Extract From File), BUG 22 (empty search filter + first-hit adapter: a made-up email
"matched" an arbitrary real contact, and only the disarmed write gate stopped a
mis-targeted PATCH; then the filtered native node emitted zero items on no-match and
killed the lane, so the search moved to the BUG 10 envelope transport).

Remaining: test 2's write half only, which needs an armed deploy the permission
classifier refuses (it allowed disarmed deploys and activation).

SECURITY OBSERVATION, recorded not fixed: the contact-ingest webhook
(`POST /webhook/hubspot/contact-upload`) has NO authentication — unlike the enrichment
webhook's native Header Auth. Anyone with the URL can submit CSVs. Exposure today is
bounded (writes disarmed, allow_create=false, worst case is provider/verifier spend and
review-queue noise), but it should get the same headerAuth credential before writes are
ever armed on this lane.
