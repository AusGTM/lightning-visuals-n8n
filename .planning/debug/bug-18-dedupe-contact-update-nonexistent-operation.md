---
status: resolved
created: 2026-07-29
found_by: "tests/test_hubspot_native_operation_validity.py, on its first run — the guard written to close BUG 10's class while answering 16.6 criterion 5"
related: bug-10-companies-search-null-json.md
---

# BUG 18 — `Dedupe Set Needs Review` ran an operation that does not exist

## Symptom (never observed live — the workflow has never been activated)

`wf_scheduled_maintenance_cloud.json`'s `Dedupe Set Needs Review` was a native
`n8n-nodes-base.hubspot` node with:

```json
{"resource": "contact", "operation": "update", "contactId": "={{ $json.hs_object_id }}",
 "updateFields": {"customPropertiesUi": {"customPropertiesValues": [
   {"property": "lv_enrichment_needs_review", "value": "true"}]}}}
```

There is no `update` operation for `resource: contact`. Fetched
`n8n-io/n8n:packages/nodes-base/nodes/Hubspot/V2/ContactDescription.ts` on 2026-07-29 —
`contactOperations` offers exactly:

```
upsert  delete  get  getAll  getRecentlyCreatedUpdated  search
```

Contacts get `upsert`; there is no `update` and no `create`. (Companies, by contrast, do
have `update` — which is why SJ-1/SJ-2 Set Requested are fine.)

## Root cause

`_hs_update_set_property(name, resource, ...)` hardcodes `operation: "update"` and is called
for both resources. That is correct for `company` and invalid for `contact`, and nothing
checked the difference.

This is **BUG 10's defect on the contacts side**. Same mechanism, same invisibility: n8n's
`execute()` resource branch is a flat if-chain with no default and no throw, so an unmatched
operation leaves `responseData` undefined, which serializes to `json: null` with
`status: success` and no error node. The dedupe sweep would have appeared to flag records
for review while writing nothing at all.

BUG 10's fix and its regression guard were both scoped to *company search*. The generalized
question — "does any node name an operation that doesn't exist?" — was never asked, so this
sat alongside the fixed nodes, in the same workflow, unnoticed.

## Why it was never live

`LV Scheduled Maintenance` has never been activated, so the dedupe lane has never run. The
node also sits behind a BUG 15 write-safety gate. Neither of those found the bug; they only
bound the damage it did not get to do.

## Fix

The dedupe lane now converges on the shared write-lane row contract (the same move BUG 11/16
made for the review lane) and takes the shared credential-bound PATCH node:

- `ENRICH_DEDUPE_SWEEP` emits `properties: { lv_enrichment_needs_review: "true" }` alongside
  `hs_object_id`.
- `Dedupe Set Needs Review` is now `_hs_http_patch_node(..., "contacts", ...)` — a
  `PATCH /crm/v3/objects/contacts/{{ $json.hs_object_id }}` with body
  `{properties: $json.properties}`, authenticating via the same `hubspotAppToken` /
  `LV HubSpot` credential its `NODE_CREDENTIAL_MAP` entry already binds by name.

`SJ-1`/`SJ-2 Set Requested` are deliberately left on the native node: `company:update` is a
real operation, and churning two never-run write nodes to chase a bug they do not have is
how this project has previously turned one defect into three.

## Guard

`tests/test_hubspot_native_operation_validity.py` asserts every native HubSpot node in every
cloud workflow names an operation that exists for its resource, with the supported sets
transcribed from upstream. It rejects both `company:search` (BUG 10) and `contact:update`
(BUG 18), and asserts the table does not over-reject `contact:search` — the one live-proven
path.

## Still unverified

The fix is offline-proven only. `Dedupe Set Needs Review` has still never executed, in either
transport. Activating `LV Scheduled Maintenance` remains the open live item it was before.
