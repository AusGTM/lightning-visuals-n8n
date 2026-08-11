# Phase 47 — BLOCKED on Anthropic account credit

**Raised:** 2026-08-12
**Blocks:** Plan 47-03 Task 3 (research pass + disarmed dry-run) and all of Plan 47-04 (the armed window)
**Nothing written:** zero HubSpot PATCHes, zero arming, `$0` Anthropic spend.

---

## The blocker

The Anthropic account behind `ANTHROPIC_API_KEY` has insufficient credit:

```
400 invalid_request_error — "Your credit balance is too low to access the Anthropic API.
Please go to Plans & Billing to upgrade or purchase credits."
```

**Both** research legs of this phase depend on that one account, so neither can run:

| Leg | Path | State |
| --- | --- | --- |
| Plan 03 Task 3(a) | `scripts/remediate_veto_companies.py --research-only` → `src/web_research.py` | fails on call 1 of 17 |
| The armed window | n8n `Claude Web Research` node inside `wf_enrichment_cloud.json` | fails identically |

## How the n8n leg was verified (read-only, no writes)

A single synthetic property-change event was POSTed for one pinned id (`9604732797`,
Tweed Valley Jockey Club) to `{N8N_URL}/webhook/hubspot/enrichment/event`. This is safe while
disarmed: the `Decide Company Action` node's gate has `ALLOW_HUBSPOT_RECORD_WRITES` baked
`"false"` at rest and an empty `TEST_RECORD_IDS` allowlist, which denies every write. The
response confirmed it — `"action":"write_blocked"`.

Execution `11833` (started 0.4s after the POST) was then read back via the n8n API:

```
NODE: Claude Web Research
  "error": { "message": "400 - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",
  \"message\":\"Your credit balance is too low to access the Anthropic API.
  Please go to Plans & Billing to upgrade or purchase credits.\"}}" }
```

## Secondary finding — worth its own fix later

**The n8n flow does not fail loudly on Anthropic credit exhaustion.** Execution `11833` reported
`status: success`, `finished: true`, and **zero node-level errors**. The `Claude Web Research`
node itself reported `executionStatus: "success"`. The 400 was carried *as data* on the node's
main output — an error object passed downstream as though it were a research result.

Consequences worth checking before trusting any recent enrichment run:

- A monitoring surface that keys on execution status or node errors sees a green run.
- Downstream nodes consume an error object where they expect `ProviderResult`-shaped data. The
  probe's own response body returned `lv_revenue_band: "1-5M"` and `lv_employee_band: "10-50"`
  for a regional jockey club — values that did not come from a successful research call.

This is a distinct defect from the billing state and outlives it. It is **not** in Phase 47's
scope; recorded here so it is not lost. Candidate for a Phase 48+ todo.

## Why hand-researching the 17 was rejected as a workaround

Doing the classification in-session with the orchestrator's own web search would have satisfied
D-08's substance (classify from a website read, not provider firmographics) and produced a valid
`47-RESEARCH-RESULTS.json`. It was rejected because it does not unblock the phase: the armed
window's veto-clearing leg is the n8n `Decide Company Action` node (D-18), reached through the
same workflow whose `Claude Web Research` node is dead. Seventeen hand-researches would buy a
dry-run and nothing past it — and would be wasted outright the moment credit is added, since that
also revives the tested, committed script path.

## To resume

1. Add credit to the account behind `ANTHROPIC_API_KEY` (console.anthropic.com → Plans & Billing).
   Ex-ante estimate for this phase is **17 calls, ~$1.17** (`47-COST-ESTIMATE.md`), plus D-20's
   ~4 redundant second-pass calls inside n8n.
2. Re-run the research pass (free to retry; it refuses over-budget rather than truncating):

   ```
   USE_MOCK_WEB_RESEARCH=false .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/remediate_veto_companies.py', run_name='__main__')" --research-only --out .planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json
   ```

3. Plan 03 Task 3(b) (disarmed dry-run → `47-DRYRUN.md`), then Plan 04's armed window.

No code change is needed. D-21's narrowed property contract was re-verified live after the
narrowing (read-only, zero missing names, exit 0), so the guard passes and Task 3 runs straight
through once credit exists.

## State at the time of blocking

- Working tree clean; full suite green (2574 passed, 128 skipped).
- `47-BEFORE.json` holds the live before-snapshot of all 17 — every row `lv_icp_tier=D`,
  `lv_anti_icp_flag=true`, reason `"Non-ANZ geography"`, all three inputs `null`. Agrees exactly
  with `46-SIMULATION-REPORT.md`. No excluded id (Entain / Gravity Media / Ironman) present.
- No `47-RESEARCH-RESULTS.json` exists — the incremental-flush design meant the failed first call
  left no partial file.
- Nothing armed. No `ALLOW_*` variable was ever set in any shell.
