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

---

## RESOLVED — Phase 48, D-04 (2026-08-13)

Folded into Phase 48 as decision **D-04** and fixed at the lane, not at the driver.

**What shipped.** `IF Research Errored` + `Build Research Failure Response` were added to the
CLOUD build site in `scripts/build_cloud_workflows.py`, immediately after `Claude Web Research`
and before `Validate Research Output`. An error-shaped payload now routes to a failure branch
terminating at a response with a stated reason, instead of flowing downstream where a
`ProviderResult` belongs. `n8n/wf_enrichment_cloud.json` was regenerated from the builder (never
hand-edited) and is byte-reproducible.

**Deployed and live.** Phase 48's one declared deploy+bounce (plan 48-04) put it on the running
instance. Proven by execution `11865`'s own embedded workflow node list — 111 nodes, up from the
109-node pre-deploy baseline, containing both new nodes. A stored read-back was not accepted as
proof (stored ≠ running).

**Honest limitation.** The gate's live *firing* on a real Anthropic 400 is **not** proven. No
Phase 48 execution traverses the research branch, and a credit-exhaustion 400 cannot be induced
on demand. What is proven is structural presence in the running instance plus
`tests/n8n/researchErrorGateFlow.test.mjs`, which drives the node's REAL emitted expression
(loaded from the workflow JSON, evaluated via `new Function`) against the live-observed 400 shape
from execution `11833` — this todo's own evidence — plus a healthy shape and a degenerate shape.

Closing on that basis: the fix exists, is deployed, and is tested against the exact payload shape
this todo recorded. If a future run ever does observe it firing live, that observation belongs in
the phase that sees it.
