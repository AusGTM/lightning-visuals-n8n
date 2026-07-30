---
status: complete
phase: 16-scheduled-workflows-review-surface
source: [16-VERIFICATION.md]
started: 2026-07-23T07:00:00Z
updated: 2026-07-29T17:05:00+10:00
---

## Current Test

[testing complete]

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
result: pass
source: automated
evidence: |
  CLOSED 2026-07-29, execution 56 — the §22.2 loop completed on a real HubSpot record,
  end to end, on the lane's own 15-minute tick with no manual triggering:

    Review Search (approved=true)   total=1
    Review Extract Rows             domain + candidate JSON carried
    Apply Review                    stale=false, canonicalPatch={"lv_org_type":"broadcaster"}
    Review IF Stale                 false lane
    Review Apply Update Write Gate  1 item — ALLOWED (armed, single-domain allowlist)
    Review Apply Update             RAN, error null, response id 278608087500

  Record state, before -> after:

    lv_org_type                      None    -> 'broadcaster'      (canonicalPatch)
    lv_enrichment_review_approved    'true'  -> 'false'            (clearPatch)
    lv_enrichment_needs_review       'true'  -> 'false'            (clearPatch)
    lv_enrichment_reviewed_at        None    -> '2026-07-29T05:30:13.364Z'

  flag -> decision JSON -> approve -> apply -> clear, all four legs proven live.

  Throwaway deleted, re-read 404. Build restored to disarmed and read back
  (RECORD_WRITES/CREATE "false", both allowlists empty), all three workflows still active.
  Armed-window audit: exactly ONE write node produced output across the entire window —
  `Review Apply Update` in execution 56. Nothing else wrote.

  THE ROUTE HERE COST THREE ARMED WINDOWS AND BOUGHT TWO BUGS, both fail-closed:
    - BUG 24: every company write lane's gate reads `domain`, which no company search
      requested — so TEST_RECORD_DOMAINS was silently inert on SJ-1, SJ-2 and Review.
      Arming by domain produced no-ops, not writes.
    - BUG 25: fixing that was necessary and insufficient — `Apply Review` rebuilt the row
      without a spread and dropped `domain` two nodes before the gate, making my own BUG 24
      fix inert. The BUG 24 guard missed it because it asked "is domain requested upstream"
      rather than "does it survive to the gate".
  The third window was simulated green offline first (compiled nodes + armed constants ->
  GATE ALLOWED) rather than attempted on faith, and it wrote first time.

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

  Not claimed here: that all six company search nodes work live. That is 16.6 criterion 1,
  since closed at 6/6 (executions 12, 19, 23, 24, 29, 33) — see 16.6-UAT.md.

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
passed: 3
issues: 0
pending: 0
blocked: 0
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

Third and fourth passes, same day: test 2 was first pushed as far as it goes without arming
(execution 47 — the whole lane bar the PATCH), then closed outright (execution 56 — the
PATCH, on a real record, verified property by property). Two fail-closed bugs surfaced on
the way (BUG 24, BUG 25) and are fixed and guarded.

Phase 16's three tests all pass. Nothing here is blocked.

SECURITY OBSERVATION — FOUND AND RESOLVED SAME DAY (eb5e34c): the contact-ingest webhook
(`POST /webhook/hubspot/contact-upload`) shipped with NO authentication, unlike the
enrichment webhook's native Header Auth. Fixed with the same headerAuth + shared
"LV Enrichment Webhook" credential, deployed, and live-verified both directions:
unauthenticated 403, with X-Enrichment-Secret 200.
