---
status: resolved
created: 2026-07-29
resolved: 2026-07-29
resolved_by: "61988dd — fix: BUG 17 — Lusha company enrichment, live-probed contract"
found_by: "Live canary execution 19 (first ever run of HubSpot Company Search, all providers)"
---

## Resolution (2026-07-29, commit `61988dd`)

Contract re-probed live against `racingnsw.com.au`:

- `GET /v2/company?domain=` → `200 { data:{...}, meta:{} }` — this is the shape `lushaCandidates()`
  already unwraps.
- `domain` is the ONLY accepted query property. `?domain=&companyName=` 400s with
  `"property companyName should not exist"` — the exact mirror of the old POST body's
  `"property domain should not exist"`. So `companyName` stays out of the URL and lives on in
  `identity_keys` for Apollo/ZoomInfo.
- A `POST {companies:[{id,domain}]}` envelope also succeeds (mirroring `/v2/person`), but returns an
  id-keyed map `lushaCandidates()` does not unwrap. Not used.

`Lusha Company` is now a GET consuming the prebuilt `lusha_company_url` (which nothing consumed
before). Both halves of the bug — the ignored URL and the URL's own bad `companyName` param — are
covered by tests: `tests/test_cloud_companies_branch.py:199` (node method/URL) and `:221` (the
builder line), plus `tests/test_provider_gate_topology.py:362` (method-mismatch guard).

Company enrichment now runs on three providers. Historical scores computed before this commit were
Apollo + ZoomInfo only; the franchise/subsidiary conflict detector was comparing two sources where it
should have compared three.

**Still open (spun out, not a BUG 17 regression):** the "Related observation" below — ZoomInfo's
numeric `industry: "71"` winning a text field is a normalization gap with no ticket yet.

# BUG 17 — Lusha company enrichment has never worked, and the failure is invisible

## Symptom

`Lusha Company`'s output item carries an error while the node's own error field is `null`:

```
400 - {"name":"BadRequest","message":"property domain should not exist",
       "code":400,"className":"bad-request","errors":{}}
```

`onError: continueRegularOutput` is set on the provider nodes, so the failed call flows downstream as
a normal-looking item and every later node continues as if Lusha simply returned nothing. Execution 19
reported `status: success` with no error node. Company enrichment has therefore been running
two-provider (Apollo + ZoomInfo) while appearing to run three.

## Root cause

The builder computes a correct query-style URL and the node ignores it.

`Build Company Requests` (`scripts/build_cloud_workflows.py`) emits:

```js
const lusha_company_url = "https://api.lusha.com/v2/company?" + q.join("&");  // domain=…&companyName=…
```

But the `Lusha Company` node does not use `lusha_company_url`. It POSTs to the bare endpoint with the
identity object as a JSON body:

```json
{"method":"POST","url":"https://api.lusha.com/v2/company",
 "jsonBody":"={{ JSON.stringify($('Build Company Requests').item.json.identity_keys) }}"}
```

`identity_keys` is `{domain, companyName}`, and Lusha's `/v2/company` rejects `domain` as a body
property — it expects it as a query parameter. So every company run has 400ed.

This is the same shape as the earlier Lusha v2 *person* contract bug (request shape wrong in both
halves), and the same masking mechanism as the ZoomInfo 401 bug: the real error sits in the item, not
the node.

## Not fixed here

Fixing it means correcting the request contract against Lusha's live v2 company API, which needs a
probe of the real endpoint to confirm whether it wants query params, a different body shape, or a
`companies[]` envelope like the person endpoint did. That is its own task with its own test, not an
in-flight patch.

## Impact

- Company enrichment silently runs on two providers, not three. Every company ICP score to date is
  computed without Lusha's firmographics.
- Provider-conflict detection (the franchise/subsidiary detector on `lv_revenue_band` /
  `lv_employee_band`) has been comparing two sources where it should compare three, so some genuine
  three-way disagreements will have looked like two-way agreement.
- No credits were consumed for these failed calls, which is why the Lusha balance never moved on
  company runs — a signal that was visible all along and not read.

## Related observation (minor, not a bug)

ZoomInfo returns `industry: "71"` — a numeric code — which won the waterfall over Apollo's
`"media production"` and normalized to `"71"` unchanged. It was correctly routed to `needs_review` by
the `stale_refreshable` policy against the existing `SPORTS`, so nothing was clobbered, but a numeric
industry code winning a text field is a normalization gap worth its own ticket.
