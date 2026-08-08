---
plan: 43-05
phase: 43
status: complete
requirements: [PIPE-01, PIPE-02]
completed: 2026-08-08
executed_by: orchestrator (direct — two spawned executors died on API quota/session limits mid-run)
---

# 43-05: Deploy + bounce the regenerated workflows

## Precondition — satisfied and re-verified live

43-05's gate required quoted evidence that Phase 41 disarmed. Verified immediately before
deploying, against the live instance rather than trusting the earlier payload:

```
ALLOW_HUBSPOT_RECORD_WRITES = false
ALLOW_HUBSPOT_CREATE        = false
TEST_RECORD_IDS             = (absent)
```

## What was done

1. **Dry run** — 5 workflows to update, 0 to create. Inspected before proceeding.
2. **Deploy** — `DRY_RUN=false ALLOW_N8N_DEPLOY=true`, with `ALLOW_N8N_ARM` deliberately
   UNSET so the deploy landed disarmed content. All 5 workflows returned HTTP 200.
3. **Bounce** — `LV Enrichment (Cloud template)` (950HPb7a1GgSAIyZ) and `LV Scheduled
   Maintenance (Cloud)` (1fXPuIabz3RsAHgn), deactivate→activate, both `verdict=verified`.
   Without this the running instances keep executing the previous code.
4. **Read-back of RUNNING content** (not the mutation echo):
   - `ALLOW_HUBSPOT_RECORD_WRITES = "false"` on both, no node disagreement.
   - `june_2026` marker present in the enrichment merge node.

## PIPE-01 deployment proof

The generic June marker is not sufficient proof that 43-01's coercion shipped, so the
deployed content was checked directly for the defect pattern:

| Check | Live | Repo |
|---|---|---|
| bare-boolean `lv_*_needs_review` writes | **0** | 0 |
| string-coerced `lv_*_needs_review` writes | **2** | 2 |

Deployed content matches the repo exactly. The boolean-coercion fix is live.

## State after this plan

- Write gates remain **disarmed**. Nothing was armed; arming is the operator's decision.
- No canary record (9604614548, 15008671672, 16047156820, 17861423879, 15274105699) and no
  June record was written.
- The repo/deployed divergence that existed since 43-01 is now closed.

## Note on execution

Two spawned executors (`43-04` retry, then `43-05`) terminated mid-run on API quota and
session limits. Neither left partial state: no orphaned disposable companies, no partial
deploy, clean git tree. 43-05 was completed directly by the orchestrator rather than
re-spawning a third agent that could die at the same point — the deploy is a short,
verifiable sequence and repeated agent death mid-deploy is itself a risk.
