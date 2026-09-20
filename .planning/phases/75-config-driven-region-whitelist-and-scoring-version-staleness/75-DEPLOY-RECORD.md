# Phase 75 — Deploy record (plan 75-06 Task 1, DISARMED)

Operator-run from the interactive shell (`!`, `.env` sourced inline) on 2026-09-20, after
selecting `proceed` at the plan 06 Task 0 `blocking-human` checkpoint. Nothing armed.

## Pre-deploy disclosure (printed before any PUT)

| Committed body | Nodes | Nodes at phase start (`dfef89d9`) | `ALLOW_HUBSPOT_RECORD_WRITES` / `_CREATE` / `_REVIEW_WRITES` / `_RECOMPUTE_WRITES` | `executeWorkflow` nodes |
| --- | --- | --- | --- | --- |
| `n8n/wf_enrichment_cloud.json` | 289 | 289 | `"false"` at every site (4 sites each) | 0 |
| `n8n/wf_scheduled_maintenance_cloud.json` | 43 | 43 | `"false"` at every site (5 sites each) | 1 (SJ-3's keyed cross-workflow exemption, unchanged) |

Bodies regenerated this phase (`git diff --stat dfef89d9 -- n8n/*.json`): enrichment,
scheduled-maintenance, contact-ingest, review-decision (cloud) plus the two local enrichment
bodies (not deployed). Backend-status and suggest-discovery bodies are byte-unchanged and were
NOT deployed. `build_cloud_workflows.py` re-run → `git status --porcelain -- n8n/` empty.

## Deploy calls (`scripts/deploy_n8n_workflows.py --only <file>`, dry then live)

| `--only` | dry-run | live (`DRY_RUN=false ALLOW_N8N_DEPLOY=true`) | rc |
| --- | --- | --- | --- |
| `wf_enrichment_cloud.json` | update `['LV Enrichment (Cloud template)']` | `updated workflow LV Enrichment (Cloud template) (200)` | 0 |
| `wf_scheduled_maintenance_cloud.json` | update `['LV Scheduled Maintenance (Cloud)']` | `updated ... (200)` | 0 |
| `wf_contact_ingest_cloud.json` | update `['LV Contact Ingest (Cloud template)']` | `updated ... (200)` | 0 |
| `wf_review_decision_cloud.json` | update `['LV Review Decision (Cloud)']` | `updated ... (200)` | 0 |

Every call listed zero creates. (An earlier all-workflow dry-run listed all six as "to update"
— the known deploy-diff noise; the four `--only` calls are what was executed.)

## Bounce + read-back (`scripts/bounce_n8n_workflows.py`, `bounce_exit=0`)

| workflow | id | active | live nodes | committed | write flags | recompute flag | execution order |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LV Backend Status (Cloud template) | `Cj83mOgrIm59oxcX` | True | 33 | 33 | (none declared) | (none) | v1 |
| LV Contact Ingest (Cloud template) | `AwbBeShdPgV48eiY` | True | 101 | 101 | RECORD_WRITES=false, CREATE=false | `ALLOW_HUBSPOT_RECOMPUTE_WRITES=false` | v1 |
| LV Enrichment (Cloud template) | `950HPb7a1GgSAIyZ` | True | 289 | 289 | RECORD_WRITES=false, CREATE=false | `ALLOW_HUBSPOT_RECOMPUTE_WRITES=false` | v1 |
| LV Review Decision (Cloud) | `WBJwoZOo63wzeP69` | True | 55 | 55 | RECORD_WRITES=false, CREATE=false | `ALLOW_HUBSPOT_RECOMPUTE_WRITES=false` | v1 |
| LV Scheduled Maintenance (Cloud) | `1fXPuIabz3RsAHgn` | True | 43 | 43 | RECORD_WRITES=false, CREATE=false | `ALLOW_HUBSPOT_RECOMPUTE_WRITES=false` | v1 |
| LV Suggest Discovery (Cloud template) | `VJJBZ2oJ0079MSzG` | True | 26 | 26 | (none declared) | (none) | v1 |

Script verdict: "OK — all active, node counts match, write flags false, recompute flag matches
committed, execution order v1." First live read-back of the fourth flag (plan 04's
`bounce_n8n_workflows.py` extension) — `[observed live]`.

## Burst watch (post-bounce)

Baseline before deploy: enrichment max execution id `12677`, maintenance `12681`.
After deploy + bounce: enrichment `12677`, maintenance `12681` — zero executions fired.

Rollback: PUT of the pre-phase bodies (`git show dfef89d9:n8n/<file>`) through the same script.
