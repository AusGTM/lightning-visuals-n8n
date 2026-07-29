---
phase: 17-enrichment-contacts-reachability-bug-23
plan: 02
title: Dual live canary evidence — BUG 23 transport swap
created: 2026-07-29
---

# 17-02 Live Canary Evidence — BUG 23

Workflow under test: `LV Enrichment (Cloud template)`, id `950HPb7a1GgSAIyZ` (confirmed live
by name against `GET /api/v1/workflows`, matches 16.7's recorded id). No secret value is
quoted anywhere in this file — only literal config values (`"false"`, `""`, node types,
record ids, execution ids, timestamps).

## Case A — BEFORE (pre-swap)

### Precondition verification (step 1)

Live read-back of workflow `950HPb7a1GgSAIyZ`, `GET /api/v1/workflows/950HPb7a1GgSAIyZ`:

- `active`: `true`
- `HubSpot Search`: type `n8n-nodes-base.hubspot`, `resource: contact`, `operation: search`
  — **still native**, confirming no deploy has run since Plan 01 committed (`1de085f`).
- `HubSpot Fetch By Id`: type `n8n-nodes-base.hubspot`, `resource: contact`,
  `operation: search` — **still native**.
- Write-safety literals (quoted verbatim from the `Decide Action` / `Decide Company Action`
  Code node source, both contacts and companies lanes carry the same literals):
  - `ALLOW_HUBSPOT_RECORD_WRITES = "false"`
  - `ALLOW_HUBSPOT_CREATE = "false"`
  - `TEST_RECORD_DOMAINS = ""`
  - `TEST_RECORD_IDS = ""`
  - `ALLOW_WEB_RESEARCH = false` (Research Trigger Gate / Contact Research Trigger Gate)
  - `ALLOW_SONNET_ESCALATION = false` (Judge Gate / Contact Judge Gate)

All disarmed. Precondition **HOLDS** — proceeding.

### Contact 201, current state (step 2, GET only)

```json
{
  "id": "201",
  "properties": {
    "email": "brendan@lightningvisuals.com",
    "firstname": "Brendan",
    "lastname": "Carmody",
    "jobtitle": "Carmody, our developer. His email copied above",
    "phone": "+61413232200",
    "mobilephone": "+61 439 135 604",
    "seniority": "",
    "lv_jobtitle_verified_at": null,
    "lv_mobilephone_verified_at": null,
    "lv_contact_enrichment_provenance": "",
    "lastmodifieddate": "2026-07-28T23:57:37.092Z"
  }
}
```

Note (recorded, not investigated — out of this plan's scope): `seniority` and
`lv_contact_enrichment_provenance` read as empty strings here, though 16.8's addendum
recorded `seniority: "Non-Manager"` being written by execution 15. `lastmodifieddate`
(`23:57:37.092Z`) postdates execution 15's write (`23:56:33.743Z` provenance timestamp) by
about a minute, so some later action (manual test-data reset, most likely) cleared these
fields again. This does not affect the canary: A1/A2 below re-derive the gate decision from
whatever state is live, and record what IS, per the plan's instruction.

A1 payload's `email` is this contact's real email, `brendan@lightningvisuals.com`, used
verbatim.

### Fire A1 — direct-field envelope (step 3)

- Fired: `2026-07-29T06:51:0Xs` (webhook POST), execution **68**, `startedAt`
  `2026-07-29T06:51:08.213Z`, status `success`.
- Webhook response: `{"action":"write_blocked","object_type":"contacts","hs_object_id":"201","gap_flag":true,"properties":{},"remaining_credits":[]}`
  (recorded but not trusted as evidence per house convention — every claim below quotes
  `runData`).
- `HubSpot Search` — **1 item emitted**, raw shape is the **flattened native record**
  (this is the pre-swap shape that changes post-swap):
  ```json
  {"id": "201", "properties": {"email": "brendan@lightningvisuals.com", "firstname": "Brendan",
   "lastname": "Carmody", "jobtitle": "Carmody, our developer. His email copied above",
   "mobilephone": "+61 439 135 604", "phone": "+61413232200", "seniority": "",
   "lastmodifieddate": "2026-07-28T23:57:37.092Z", ...}}
  ```
- `Adapt Search` output:
  - `existingRecord`: the same flattened record above (non-empty)
  - `lookup_failed`: `false`
  - `identity_keys`: `{"email": "brendan@lightningvisuals.com", "domain": "lightningvisuals.com", "linkedin_url": null, "firstName": null, "lastName": null, "companyName": null}`
- `Enrichment Gate` output: `gate.action = "enrich"`, `staleFields: ["jobtitle","mobilephone"]`,
  `reason: "stale: jobtitle,mobilephone"`, top-level `action: "enrich"`.
- `Decide Action` output: `{"action":"write_blocked","object_type":"contacts","hs_object_id":"201","gap_flag":true,"properties":{}}`.

### Fire A2 — bare event (step 4)

- Fired: execution **69**, `startedAt` `2026-07-29T06:51:45.060Z`, status `success`.
- Webhook response: `{"action":"write_blocked","object_type":"contacts","hs_object_id":"201","gap_flag":true,"properties":{},"remaining_credits":[]}`.
- `HubSpot Fetch By Id` — **1 item emitted**, flattened native record (same shape as A1's
  search, plus `company: null` and `lv_linkedin_url: null` in the requested property set).
- `Adapt Fetch By Id` output:
  - `existingRecord`: the flattened record (non-empty)
  - `lookup_failed`: `false`
  - `fetch_diagnostic`: `"ok: matched via single object"`
  - `identity_keys`: `{"email": "brendan@lightningvisuals.com", "domain": "lightningvisuals.com", "linkedin_url": null, "firstName": "Brendan", "lastName": "Carmody", "companyName": null}`
- `Enrichment Gate` output: `gate.action = "enrich"`, `staleFields: ["jobtitle","mobilephone"]`,
  top-level `action: "enrich"` — identical shape to A1.
- `Decide Action` output: `{"action":"write_blocked","object_type":"contacts","hs_object_id":"201","gap_flag":true,"properties":{}}` — identical to A1.

### Execution ids and timestamps (step 5)

| Fire | Execution id | `startedAt` |
|---|---|---|
| A1 (pre-swap) | 68 | 2026-07-29T06:51:08.213Z |
| A2 (pre-swap) | 69 | 2026-07-29T06:51:45.060Z |

Most recent pre-existing full-chain execution (contacts, all three providers, contact 201):
**execution 15**, `startedAt` `2026-07-28T23:56:27.237Z` (from the executions list, ids 1-19
inspected; execution 19 is a COMPANIES-lane run, not contacts — the actual historical
full-chain contacts run with `Merge Winners` populated and all three provider nodes present
is execution **15**, referenced in `16.7-02-SUMMARY.md`'s ADDENDUM as the run that wrote
`seniority` to contact 201 after the BUG 12 fix). This is the execution Task 2 step 4
compares the post-swap full-chain re-run against.

Historical execution 15's `Merge Winners` output (winning-source-per-field map, captured
here for the Task 2 diff):

| field | current_value (at exec 15 time) | chosen_value | decision | validation_status |
|---|---|---|---|---|
| `email` | `brendan@lightningvisuals.com` | `brendan@lightningvisuals.com` | `needs_review` | `human_review_required` |
| `mobilephone` | `+61 439 135 604` | `+61 413 232 200` | `stage_only` | `provider_only` |
| `jobtitle` | `Carmody, our developer. His email copied above` | `Product Manager` | `needs_review` | `human_review_required` |
| `seniority` | `null` | `Non-Manager` | `promote` | `provider_only` |

All four decisions' `source_provider` field is the literal string `"waterfall"` (the merge
policy's generic label, not a specific provider name) in this codebase's output shape — this
is the source-attribution granularity available to diff against, recorded as-is.

**Verdict: Case A BEFORE capture complete.** Zero HubSpot writes issued (GETs and one
search/fetch per fire only). Both A1 and A2 show `action: "enrich"` at the gate (contact
201 has genuinely stale `jobtitle`/`mobilephone`) and `write_blocked` at Decide Action
(writes disarmed) — this is the expected pre-swap behavior for an EXISTING record match.

<!-- gsd:write-continue -->
