---
status: testing
phase: 16-scheduled-workflows-review-surface
source: [16-VERIFICATION.md]
started: 2026-07-23T07:00:00Z
updated: 2026-07-23T07:00:00Z
---

## Current Test

number: 1
name: Live n8n Cloud deploy + credential provisioning + SJ-3 property creation
expected: |
  Both workflows ("LV Enrichment (Cloud template)" and "LV Scheduled Maintenance (Cloud)")
  active on n8n Cloud with every node credential-bound (no unbound-node import errors);
  the two SJ-3 HubSpot properties live-created.
awaiting: user response

## Tests

### 1. Live operator runbook — deploy + provision + property creation
expected: Run `scripts/provision_n8n_credentials.py` then `scripts/deploy_n8n_workflows.py` (with `N8N_URL`/`N8N_API_KEY`/`ALLOW_N8N_DEPLOY=true`), activate both Cloud workflows, live-create `lv_enrichment_requested`/`lv_enrichment_status`. Both workflows appear active, all nodes credential-bound, pipeline runs live + schedules fire.
why_manual: Requires a live n8n Cloud subscription, live HubSpot writes, and live provider credentials — none exist offline.
result: [pending]

### 2. Live review-loop apply — reviewApply patch actually writes
expected: Flip `lv_enrichment_review_approved=true` on one real needs_review company; the "Apply Review" branch fires and `reviewApply`'s `canonicalPatch`+`clearPatch` reach the record.
blocker: The built "Review Apply Update" node ships `updateFields:{}` (deliberate placeholder, same convention as the webhook-branch Update nodes). An operator must map `{...canonicalPatch, ...clearPatch}` onto the node's custom-properties UI before live approval writes.
why_manual: The dynamic per-record patch is not baked into builder JSON by design (values vary per record).
result: [pending]

### 3. Real HubSpot webhook event shape — identity resolves by objectId
expected: Send a real company-object webhook event (objectId/objectType/subscriptionType only, no email/domain/firstname); identity resolves to the correct company and enrichment runs end to end.
blocker: 16-01 Deviation 3 (MINIMUM-scope shim) — Build Identity/Build Company Identity still read direct body fields, not fetch-by-objectId. A follow-up fetch-by-id node (plan-scoped-out) is needed for a genuine event shape.
why_manual: Unprovable offline without a live webhook call.

## Pre-live-deploy follow-ups (from VERIFICATION.md, not gating the offline deliverable)

- **[fix before first live deploy] `deploy_n8n_workflows.py` globs all `wf_*.json`** — would also import the local-replica fixtures (`wf_enrichment_local.json`, `wf_enrichment_local_live.json`) which legitimately keep `$env`/`$vars` and would import as broken/unbound on Cloud. Restrict the deploy set to the Cloud workflows (reuse the `ACTIVE` set that `test_top_level_is_exactly_the_deployable_set` guards, or glob `*_cloud.json` + `wf_scheduled_maintenance_cloud.json`).
- Item 2's `updateFields:{}` and item 3's fetch-by-id shim above are the other two live-wiring steps.

## Summary

All 9 ROADMAP Phase-16 success criteria verified structurally offline (266 pytest / 147 node, builder deterministic, frozen files intact, every cross-AI review finding confirmed landed). The remaining work is exclusively the live operator runbook + 3 wiring items above — matching the Phase-15 precedent (tooling offline-proven, live runbook pending).
