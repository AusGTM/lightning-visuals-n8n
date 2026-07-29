---
status: root_caused_not_fixed
created: 2026-07-29
found_by: "Reading the create payload before firing it, while attempting 16.9 SC-4; then confirmed live against a throwaway company"
related: bug-13-create-nodes (fixed), bug-18-dedupe-contact-update-nonexistent-operation.md
---

# BUG 19 — `create` writes a record with no identity, and will re-create it forever

## Symptom (confirmed live, 2026-07-29)

A create sends `{properties: {...merge.canonicalPatch, ...cacheKeys}}` plus status and
provenance. That object contains **no `domain` and no `name`** for companies, and **no
`email`** for contacts. HubSpot accepts it without complaint.

Exercised against a throwaway (created and deleted within the same script, re-read 404):

```
1. POST /crm/v3/objects/companies   <the node's exact payload>     -> HTTP 201, id=278591842756
2. GET  /crm/v3/objects/companies/278591842756
       name                 = None
       domain               = None
       lv_org_type          = 'governing_body_league'
       lv_enrichment_status = 'complete'
3. POST /companies/search  domain EQ "lv-sc4-canary-delete-me.example"  -> 200, total=0
4. DELETE -> 204     5. GET -> 404
```

Step 3 is the damaging one. `HubSpot Company Search` — the node whose zero-result answer is
what decided `action: "create"` in the first place — filters on `domain EQ`. A record created
without a domain is invisible to it. So:

> every subsequent run for that domain searches, finds nothing, and creates **another**
> orphan. Unbounded duplicate creation, one per run, none of them findable.

At SJ-1's current match count (712 companies) on an hourly cadence, this is not a slow leak.

## Root cause

The create path reuses the **update path's non-clobber field policy**.

`domain` is `manual_protected` in `DEFAULT_COMPANY_POLICY` (`n8n/code/mergeCompanies.js:32`)
and `email` is `manual_protected` in `DEFAULT_CONTACT_POLICY` (`mergeContacts.js:25`, plus an
explicit hard-force at `:173` — "email never promotes to canonical on the enrich path"). Both
are correct and deliberate **for an update**: never overwrite a human-maintained identity
value on a record that already exists.

They are incoherent **for a create**, where there is no existing record and no human value to
protect, and where the identity field is precisely the thing that must be written. `name` is
worse still — it is not in the company policy at all, and no provider adapter emits it, so it
could never appear in a candidate set.

Nothing distinguishes the two cases: `properties` is computed once, identically, and the
`action` is decided afterwards.

## Blast radius

All five decide-node payload builders in `scripts/build_cloud_workflows.py` share the shape:

| Constant | Line | Lane |
|---|---|---|
| `DECIDE_LOCAL` | 264 | contacts, local replica |
| `DECIDE_CLOUD` | 328 | contacts, contact-ingest cloud |
| `ENRICH_DECIDE_LOCAL` | 1038 | contacts, local |
| `ENRICH_DECIDE_CLOUD` | 1113 | contacts, enrichment cloud |
| `ENRICH_DECIDE_CO_CLOUD` | 2330 | companies, enrichment cloud |

Every create-capable lane is affected.

## Why it was never caught

- Offline tests assert the patch's *shape* and the non-clobber *decisions*, never that a
  create carries an identity.
- BUG 13 fixed the create nodes' transport (they were discarding the patch and reading
  fields that did not exist). It made creates send the right object — it did not ask whether
  that object was sufficient to identify a record.
- `company:create` has never run live (that is 16.9 SC-4, still open), and `contact:create`
  only runs in the never-activated contact-ingest workflow.
- The write-safety gate reads `row.identity_keys.domain`, not the payload — so the domain
  allowlist passes and the create fires, while the record it writes has no domain. The
  containment mechanism cannot recognise its own creations afterwards either.

## Not fixed here — deliberately

The fix is small in concept (on `action === "create"`, seed identity from `identity_keys`
into `properties`) but touches five payload builders across three write lanes, none of which
has ever executed live. This session already produced BUG 16 by making a "mechanical" change
across write lanes that had quietly drifted apart — and the correction to that was to read
each lane first. The same discipline applies here.

`tests/test_create_payload_identity.py` pins the defect with `xfail(strict=True)`: it fails
today by design, and the moment someone fixes a lane it XPASSes and forces the test to be
promoted to a real assertion.

### A near-miss worth keeping

The guard's first version grepped each lane's source for `email:` and reported `DECIDE_LOCAL`
and `ENRICH_DECIDE_LOCAL` as already fixed (two strict-XPASSes). They are not. Both echo
`email: row.email || null` at the **top level of the emitted row**, for the dry-run display —
nowhere near the `patch` object actually sent to HubSpot. A looser predicate would have
declared two of five lanes clean and quietly halved the reported blast radius.

The predicate now only accepts assignment onto the payload variable itself (`patch.<prop> =`,
`properties["<prop>"] =`). Same lesson as the extractor loosening in BUG 11/16: a guard over
this codebase must be scoped to the object that reaches the API, not to the source text.

## Fix sketch for whoever takes it

For each lane, in the decide node, after `properties` is computed:

```js
if (action === "create") {
  const id = row.identity_keys || {};
  if (id.domain) properties.domain = id.domain;              // companies
  if (id.companyName) properties.name = id.companyName;
  if (id.email) properties.email = id.email;                 // contacts
}
```

Read each lane's actual `identity_keys` shape before writing this — the three lanes were
found to have drifted once already (BUG 16), and contact ingest carries different keys from
enrichment. The guard test asserts per-lane, so it will catch a lane done from memory.
