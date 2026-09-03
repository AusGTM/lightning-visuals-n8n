---
created: 2026-09-04T20:30:00.000Z
updated: 2026-09-04
title: phone is never asked for — only accepted if a provider volunteers it, so most enriched contacts land email-only
area: n8n
severity: major
files:
  - scripts/build_cloud_workflows.py   # ENRICH_GATE's REQUIRED list
  - n8n/code/enrichmentGate.js
  - n8n/code/normalizeProviders.js
  - config/field_policy.yaml
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
