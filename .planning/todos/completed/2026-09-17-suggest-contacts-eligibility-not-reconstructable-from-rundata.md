---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-18
title: suggest-contacts per-company eligibility (num_associated_contacts) cannot be reconstructed offline from n8n runData, forcing every live audit to scope to a representative subset
area: operator-plugin
severity: low
kind: question
trigger: "the next suggest-contacts batch run where either (a) a direct HubSpot read is available to the plugin at audit time, or (b) the Decide/company-list node's own output is extended to carry num_associated_contacts alongside the company id"
owner: operator
resolved_by: "73.1-07-SUMMARY.md"
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage C of stress attempt 3, 2026-09-17/18.

## What happened

`num_associated_contacts` is carried on the suggest-contacts anonymous response rows, but the
Decide-stage output that names each eligible company carries only the company id, not the
count. The two cannot be joined from runData alone, and the plugin has no direct HubSpot read
available at audit time to compute per-company eligibility independently. As a result, Stage C
of stress attempt 3 was scoped to a representative eligible subset rather than the full
~24-eligible-company crawl, and the audit could not confirm the full eligible set matched what
was actually offered.

## Question

Is it worth wiring `num_associated_contacts` through to the Decide output (or granting the
plugin a narrow direct-read path) so a future audit can reconstruct full eligibility from
runData/response alone, or is a representative-subset spot-check an acceptable standing
practice for this skill? Revisit at the trigger above.

## Resolution

Trigger clause (b) satisfied by Phase 73.1 Plan 07 (D-09). The new discovery lane's
`Build Discovery Response` node echoes `num_associated_contacts` alongside `company_id`
for EVERY eligible company in its round — gap and non-gap alike — in both the response
body and the node's own runData (`tests/n8n/suggestDiscoveryLane.test.mjs`, Task 1
Test 2). A future audit can now reconstruct the full eligible set with its counts
directly from one execution's runData, without a representative-subset scope-down.
