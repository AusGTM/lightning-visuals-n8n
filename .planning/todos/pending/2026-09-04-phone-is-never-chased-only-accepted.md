---
created: 2026-09-04T20:30:00.000Z
updated: 2026-09-04
title: enrichment is minimum-viable by construction — the gate chases 3 of 12 promotable contact fields, so phone and most else is only ever accepted, never asked for
area: n8n
severity: major
goal: rich enrichment, not minimum enrichment (operator, 2026-09-04)
files:

  - scripts/build_cloud_workflows.py   # ENRICH_GATE's REQUIRED list
  - n8n/code/enrichmentGate.js
  - n8n/code/normalizeProviders.js
  - config/field_policy.yaml

audit_acknowledged:
  milestone: v1.1
  at: 2026-09-04
---

## The gap

`ENRICH_GATE`'s required list is:

```js
const REQUIRED = ["email", "jobtitle", "mobilephone"];
```

`phone` is not in it. That is load-bearing rather than cosmetic, because **Lusha's reveal
list is derived from the gate's `missingFields`** (`lushaContactBody(id, missingFields)`).
A field the gate does not call missing is a field Lusha is never asked to reveal.

So `phone` arrives only when a provider volunteers it unrequested — ZoomInfo's
`ZOOM_OUTPUT_FIELDS` does include `"phone"` and `"mobilePhone"` — and is then merged
normally. It is accepted, never chased.

**The merge policy is NOT the blocker**, and a fix must not start there: `phone` is already
`fill_blank_only` / `min_confidence: 80` in both `config/field_policy.yaml` and
`mergeContacts.js`'s `DEFAULT_CONTACT_POLICY`, so a returned phone promotes into a blank
today. Nothing needs loosening.

## Three drop paths that also remove a returned phone

Each is deliberate; listing them so a fix does not "helpfully" weaken one:

1. `doNotCall` (Lusha) / `dnc_status` (Apollo) -> `continue`. Suppressed outright, not
   downscored. Must stay a suppression.
2. `normalizePhone(...)` returns null -> `continue`, commented *"null-drop: un-normalizable
   phone never reaches HubSpot"*. A number that will not reach E.164 for the row's region is
   dropped rather than written raw.
3. ZoomInfo `directPhone` / `hasDirectPhone` are **400 on this account** — not entitled
   (recorded at the `ZOOM_OUTPUT_FIELDS` definition). So the ceiling is `phone` (often a
   switchboard) and `mobilePhone`; a verified direct dial is not purchasable here today.

## The operator's stated target (2026-09-04, during the 260904-5sd UAT)

> "A phone number AND email are preferable — that is the target goal, with email only as
> fallback."

Today nothing expresses that. Email alone satisfies a row, and a phone-less contact is
indistinguishable from a complete one in the report.

## Shape of the fix

- Add `phone` to `REQUIRED` so it is chased. **This costs nothing:** Lusha v3 bills flat per
  contact and reveal-field count does not change billed cost (`REQ-lusha-selective-reveal`
  §6, `scripts/build_cloud_workflows.py`). Verify the same is true of the ZoomInfo call
  before assuming it generalises — it is already in `ZOOM_OUTPUT_FIELDS`, so probably moot.
- Make completeness visible: a row with both should be distinguishable from an email-only
  row in the operator's report.

## Two decisions the operator must make first

1. **Hold or flag?** Holding every phone-less row would hold most of them — direct dials are
   far scarcer than emails, and (3) above caps what this account can even buy. Flagging as
   partial is the conservative default; holding is a much bigger behaviour change.
2. **Staleness.** Should `phone` carry `mobilephone`'s 180-day `stale_after_days`, or none?

## Parity note

`ENRICH_GATE` is built by `scripts/build_cloud_workflows.py`; `enrichmentGate.js` is the
frozen module and the `REQUIRED` list lives in the WRAPPER, not the module. Regenerate
`n8n/*.json` via the builder — never hand-edit. Check whether `src/` has an equivalent
required-field list that must move in the same commit.

## The general defect the phone case is one instance of (operator, 2026-09-04)

> "Enrichment appears sparse. I want enrichment to fill as many available fields that are
> confident as it can from the waterfall. Rich enrichment is the goal, not minimum
> enrichment — same goal as with the phone."

This is not a second request. It is the same defect with a wider blast radius, and the
numbers are checkable rather than impressionistic. Measured 2026-09-04:

- **The contacts merge policy can promote 12 fields:** `city`, `country`, `email`,
  `hs_country_region_code`, `hs_state_code`, `jobtitle`, `lv_linkedin_url`,
  `lv_persona_group`, `mobilephone`, `phone`, `seniority`, `state`.
- **The gate chases 3:** `["email", "jobtitle", "mobilephone"]`.
- So **9 of 12 are opportunistic** — filled only when a provider volunteers them
  unrequested, never asked for. The gate's list reads as "the minimum that makes a contact
  usable", and because it also drives Lusha's reveal, that minimum silently became the
  ceiling for one provider and the intent for all three.

**A concrete instance worth fixing on its own: `lv_linkedin_url` can never be filled.** It
is `fill_blank_only` / `min_confidence: 85` in the contacts policy, but
`n8n/code/normalizeProviders.js` contains **no `linkedin` reference at all** — grep returns
zero. No provider branch emits a linkedin candidate, so the policy entry has no producer.
Apollo and ZoomInfo both carry a LinkedIn URL in their contact responses (CLAUDE.md §8.1's
staging table names `apollo_linkedin_url` / `zoominfo_linkedin_url`), so the data is
arriving and being discarded at the normalize step. Note this field is also one of the
three identity groups (`required_identity.any_of` includes `[linkedin_url]`), so filling it
makes future rows matchable on a key the system already privileges.

### What "as many as are confident" must NOT be read as

The thresholds are the confidence mechanism and they stay. This is about **asking for more
fields**, never about lowering the bar a value must clear to be written:

- Do not lower any `min_confidence`.
- Do not weaken `fill_blank_only` — a populated human value still wins.
- Do not soften the three drop paths above (`doNotCall`, un-normalizable, unentitled).
- A field that arrives unconfident should land as staged/held with its provenance, exactly
  as now. Richer means more fields ATTEMPTED, not more values FORCED through.

### Cost, which is what makes this cheap

- **Lusha: free.** v3 bills flat per contact; reveal-field count does not change billed cost
  (`REQ-lusha-selective-reveal` §6). Widening the reveal list costs zero extra credits.
- **ZoomInfo: already paid for.** `ZOOM_OUTPUT_FIELDS` is one request; the fields are
  returned whether or not the gate asked. Mapping more of the response is free.
- **Apollo: verify.** Do not assume it generalises.

So the dominant cost of richer enrichment is mapping work in `normalizeProviders.js`, not
provider spend — which inverts the usual reason to keep a required list short.

### Scope this properly before implementing

1. Audit each of the 12 policy fields: which provider responses actually carry it, and
   whether a normalize branch emits it. Produce the producer/consumer matrix — the
   `lv_linkedin_url` hole above was found this way and there may be others.
2. Decide the gate's `REQUIRED` list from that matrix rather than by intuition.
3. Companies deserve the same audit; this todo measured contacts only.

## Live evidence, first suggest-contacts round (Brisbane Roar FC, 2026-09-04)

Not a hypothetical any more. On that round the waterfall **discovered richer data than it
kept**, on a contact that was being CREATED (so every field was blank — nothing was being
protected):

- scraped `jobtitle` was `Marketing`; enrichment found **`Head of Marketing and Content`**
- enrichment also found **`seniority: Director`**
- `merge_enriched` filled the blank `email` and kept the stage-1 `jobtitle`; the richer
  title and the seniority were **dropped**

`seniority` is `system_owned` / `min_confidence: 75` in the contacts policy — a field the
pipeline is supposed to own outright — so it had a producer, a policy entry, and a blank
target, and still did not land. That is the sparseness in one record.

There is a second cost to it, on a different axis: the richer title
`Head of Marketing and Content` **classifies** (`-> Head of Marketing`, verified) where the
scraped `Marketing` does not. So the dropped field would have rescued a row the role filter
had thrown away — see
`.planning/todos/pending/2026-09-04-role-filter-drops-one-word-titles.md`. Two defects,
one shared cause: the round keeps the first value it got rather than the best value it has.

**Add to the audit above:** `merge_enriched`'s own keep/replace rule for a CREATE row, which
is a distinct seam from the n8n gate's `REQUIRED` list and may need its own fix.
