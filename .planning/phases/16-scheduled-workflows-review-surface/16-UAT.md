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
why_manual: Requires a live n8n Cloud subscription, live HubSpot writes, and live provider credentials — none exist offline.
result: blocked
blocked_by: deploy-permission
reason: |
  Three of four sub-parts have since been done — re-derived from the record on 2026-07-29,
  not assumed:
    - Credentials provisioned; `deploy_n8n_workflows.py` has run repeatedly against the
      real instance (executions 10-19 exist), credential binding fail-closed, no
      unbound-node import errors.
    - The two SJ-3 properties were live-created on BOTH object types by the Phase 15
      migration during the BUG 14 fix — undo manifest
      73c5342c-a455-4d69-a0a7-41df85ef1a8f.
    - "LV Enrichment (Cloud template)" IS active and has served live executions.
  Remaining: **"LV Scheduled Maintenance (Cloud)" has never been activated**, so the phase
  goal's "background reconciliation layer runs on schedule" clause is still unmet. Needs a
  deploy, which the permission classifier refuses.

### 2. Live review-loop apply — reviewApply patch actually writes
expected: Flip `lv_enrichment_review_approved=true` on one real needs_review company; the "Apply Review" branch fires and `reviewApply`'s `canonicalPatch`+`clearPatch` reach the record.
result: blocked
blocked_by: deploy-permission
reason: |
  THE STATED BLOCKER IS OBSOLETE. This test was written against "the built Review Apply
  Update node ships `updateFields:{}` ... an operator must map `{...canonicalPatch,
  ...clearPatch}` onto the node's custom-properties UI." That empty map was later
  classified as BUG 11, and its scope gap in this workflow was closed by 6d2565c. Read
  from the built artifact on 2026-07-29:

    n8n-nodes-base.httpRequest  PATCH
    url      =https://api.hubapi.com/crm/v3/objects/companies/{{ $json.hs_object_id }}
    jsonBody ={{ JSON.stringify({ properties: $json.properties }) }}
    auth     predefinedCredentialType / hubspotAppToken

  and `ENRICH_APPLY_REVIEW` emits `properties = {...canonicalPatch, ...clearPatch}`. The
  per-record patch IS baked in — as an expression rather than a static map, which is why
  the original "values vary per record so it cannot be baked" reasoning no longer holds.
  **No operator wiring step remains.**

  Blocked only on the live half: firing it needs LV Scheduled Maintenance active (test 1).

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
passed: 1
issues: 0
pending: 0
blocked: 2
skipped: 0

## Gaps

[none — blocked tests are prerequisite gates, not code defects]

## Notes

Both blocked tests reduce to a single prerequisite: **activate LV Scheduled Maintenance**.
Neither is a code gap. Every code-level item this UAT originally listed as blocking has
since been fixed by a later phase, and each was re-derived here from the built artifact or
the live record rather than trusted from a fix report.

Unblocking needs a permission rule the assistant cannot grant itself — add
`"Bash(DRY_RUN=false ALLOW_N8N_DEPLOY=true:*)"` to `.claude/settings.local.json`.
