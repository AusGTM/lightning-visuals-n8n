---
created: 2026-08-12T00:00:00.000Z
title: n8n reports success when Claude Web Research 400s on Anthropic credit exhaustion
area: n8n
severity: major
files:
  - n8n/wf_enrichment_cloud.json
discovered_in: phase-47-veto-remediation
---

## What happens

When the `Claude Web Research` node in `wf_enrichment_cloud.json` receives a `400
invalid_request_error` from the Anthropic API, the execution does **not** fail. Observed live on
execution `11833` (2026-08-11, triggered by a single disarmed probe POST during Phase 47):

- execution `status: success`, `finished: true`
- **zero** node-level errors in `resultData.runData`
- the `Claude Web Research` node itself reports `executionStatus: "success"`

The 400 is carried as **data** on the node's main output:

```json
{"json": {"error": {"message": "400 - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",
 \"message\":\"Your credit balance is too low to access the Anthropic API...\"}}",
 "name": "AxiosError"}}}
```

## Why it matters

**1. Monitoring is blind to it.** Anything keying on execution status or node errors — the
operator plugin's `backend-status` / `backend-sweep` surfaces, n8n's own execution list — sees a
green run. A total research outage looks like a healthy pipeline.

**2. Downstream nodes consume an error object where a `ProviderResult` belongs.** The probe's
own webhook response returned `lv_revenue_band: "1-5M"` and `lv_employee_band: "10-50"` for
Tweed Valley Jockey Club, a regional racing club — values that did not come from a successful
research call. If the same execution had been armed, those would have been candidates for a
write.

The combination is the dangerous part: research silently degrades to garbage, and nothing in the
run signals it.

## Suggested fix

- Make the research node fail the execution on a non-2xx response, or add an explicit gate
  immediately after it that detects an `error`-shaped payload and routes to a failure branch
  rather than into the merge/normalize path.
- Treat "research returned an error object" as `unknown`, never as data — the same
  prefer-unknown-over-guessing rule `docs/WEB-RESEARCH-SPEC.md` already states for the model's
  own output.
- Consider a credit/quota precheck so an exhausted account surfaces as an operator alert rather
  than as silently degraded enrichment.

## Verification

Reproducible while the account is unfunded: POST one synthetic property-change event to
`{N8N_URL}/webhook/hubspot/enrichment/event` with `X-Enrichment-Secret` (safe while disarmed —
`ALLOW_HUBSPOT_RECORD_WRITES` is baked `"false"` at rest and the empty `TEST_RECORD_IDS`
allowlist denies every write), then read the execution back with `includeData=true` and search
the payload for `credit balance is too low`.

Full context: `.planning/phases/47-veto-remediation/47-BLOCKED.md`.
