---
created: 2026-09-04T21:30:00.000Z
updated: 2026-09-04
title: nothing in the pipeline can propose a company domain, so the correction mechanism has nothing to correct WITH
area: n8n
severity: major
files:

  - n8n/code/normalizeProviders.js
  - n8n/code/mergeCompanies.js
  - scripts/build_cloud_workflows.py

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The gap

Quick task `260904-pav`
(`.planning/quick/260904-pav-provenance-aware-manual-protected/260904-pav-PLAN.md`)
landed a provenance-aware `manual_protected` correction path: a company `domain` the
enrichment system parked itself (provenance `source: "create_seed"`), still unedited, on a
conflict-free row, can now be replaced by a >=95-confidence candidate. The mechanism is
implemented in both engines and tested.

**No such candidate exists.** Verified by reading the code at planning time and again at
execution time:

- **No branch of `n8n/code/normalizeProviders.js` pushes a company `domain` candidate at
  all.** The complete `_push` field set is: city, country, email,
  hs_country_region_code, hs_state_code, industry, jobtitle,
  lv_country_region_normalized, lv_employee_band, lv_revenue_band, mobilephone,
  numberofemployees, persona_group, phone, seniority, state.
- **The Claude-web research fold does not supply one** — it answers org_type,
  produces_content, content_type, hardware, gambling, sponsorship, and (since COPY-01)
  lv_country_region_normalized. Nothing identity-shaped.
- **The company providers are looked up BY the record's domain**, so they structurally
  cannot return one that disagrees with it: ZoomInfo `matchCompanyInput:
  [{companyWebsite|companyName}]`, Lusha company `?domain=`.

So `Merge Company`'s `domain` slot in its candidate allowlist is never populated, and the
correction path is reachable only in tests. **Live company `285583534546` (Brisbane Lions)
stays stuck** on the `brisbanelions.com.au` it was created with, and G-62-7's
email-domain relatedness rule keeps holding every correct `@lions.com.au` contact as
`email_domain_mismatch` against it.

## A second, subtler seam that has to be decided at the same time

The outgoing provenance blob is now additive, and **this run wins on collision**. So the
FIRST domain candidate that ever arrives and is REFUSED (confidence below 95, or a
conflicted row) writes `provenance.domain = {source: "waterfall", value: <candidate>}`
over the `create_seed` entry — permanently closing the correction path for that record,
because `waterfall` is not on `system_correctable_sources` and never will be (admitting it
is exactly the self-authorisation hole the allowlist exists to prevent).

Whoever adds a candidate source must decide whether a REFUSED candidate on a field with
`system_correctable_sources` should preserve the prior entry rather than replace it. Do
not treat this as a detail: it decides whether the mechanism survives contact with its
own first candidate.

## Plausible directions — none chosen, each needs live verification

1. **A provider raw field.** Some provider payloads carry a company website/domain
   distinct from the one queried (e.g. a ZoomInfo record matched by NAME rather than
   website). Adding a `_push` for it is a few lines — but the payload KEY and whether the
   value is ever independent of the query cannot be confirmed without a live call.
2. **A research question that returns a domain.** The web-research contract already
   returns evidence URLs; asking it for the organisation's own primary domain, with the
   existing citation-sufficiency machinery, would produce an evidenced candidate. Needs a
   contract change plus live output to confirm the shape and typical confidence.
3. **The plugin's own held evidence.** `partition_for_dispatch` already HOLDS
   `@lions.com.au` contacts as `email_domain_mismatch` — the held set is itself a signal
   that the recorded domain may be wrong. Turning a held-contact majority into a domain
   candidate is the only direction needing no new provider surface, but it inverts a
   guard into a proposal and deserves its own design pass.

4. **Not a direction — a precondition to check first.** Conjunct 2 of the correction is
   `String(entry.value) === String(currentValue)`. The seed records `id.domain` and the
   create writes `properties.domain = id.domain`, the same string — but if HubSpot
   NORMALIZES `domain` on write (lowercasing, stripping `www.`), the stored value diverges
   from the recorded one and the conjunct refuses that record forever. It fails closed, so
   there is no safety hole; the failure mode is a mechanism that stays inert even after a
   candidate source exists. Confirm the seeded domain reads back byte-identical from
   HubSpot; if it does not, the seed must record the normalized form. Cannot be checked
   offline. (Brisbane Lions' `brisbanelions.com.au` is already lowercase and www-less, so
   it is probably fine — check rather than assume.)

Each needs live provider/research calls, which `260904-pav` forbade
(zero credits, zero executions). That is why the mechanism landed without a source rather
than with a guessed one.

## Also worth knowing

- The confidence bar is `domain`'s existing `min_confidence: 95`, deliberately NOT tuned
  down to the waterfall's flat 85. Whoever adds a source owns arguing it down, with a real
  candidate in hand — the waterfall fold as it stands would produce 85 and be refused.
- `ENRICH_DECIDE_CO_LOCAL`'s dry-run echo reports `row.merge.provenance`, not the outgoing
  blob, so its echo will not show the `create_seed` entry. It writes nothing to HubSpot.
