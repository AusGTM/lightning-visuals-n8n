---
created: 2026-09-04T18:10:00.000Z
updated: 2026-09-04
title: manual_protected refuses unconditionally, so a SYSTEM-written wrong domain can never self-correct
area: n8n
severity: major
files:
  - n8n/code/mergeCompanies.js:147
  - config/field_policy.yaml
  - src/merge_policy.py
  - operator-claude-plugin/scripts/enrichment.py
---

## The gap

`mergeCompanies.js:147` refuses without ever asking who wrote the existing value:

```js
if (fieldClass === "manual_protected") {
  return { decision: "stage_only", reason: "Field is manual_protected." };
}
```

`companies.domain` is `manual_protected` (`config/field_policy.yaml`: `promote_to_canonical:
false`, `stage_only: true`, `min_confidence: 95`). The class exists to stop enrichment
clobbering a human-curated value — a real risk, and the merge wrapper documents the exact
failure it guards (providers returning a franchisor's or parent company's domain; see the
`harveynorman.com.au` note in `ENRICH_MERGE_CO`). That protection is correct and must survive
any fix here.

**But the branch cannot distinguish a human-curated value from one the system wrote itself.**
So a domain the pipeline supplied — e.g. from an operator's domain-only company create — is
protected against the pipeline's own later, better answer. The protection shields the wrong
value and blocks the correction.

## Why it is worse than an inert stale field

A wrong domain is load-bearing downstream. G-62-7's email-domain relatedness rule
(`operator-claude-plugin/scripts/enrichment.py`, `partition_for_dispatch`) compares a
discovered contact's email domain against the company's recorded domain. With a wrong domain
on the record, **every correct email is held as `email_domain_mismatch`.** One bad
system-written value silently suppresses good data, and there is no in-product correction
path — the only fix is a human opening HubSpot and retyping the domain.

Live instance, 2026-09-04: company `285583534546` (Brisbane Lions) carries a parked
`brisbanelions.com.au` from its own create request; every `@lions.com.au` contact is held
against it.

## The fix is already specified, just not implemented

CLAUDE.md §17.2's own PROMOTE list contains the missing clause verbatim:

> Existing value was previously written by the enrichment system and the new candidate has
> higher confidence.

And the data needed to evaluate it already exists: `lv_enrichment_provenance` is a per-field
object `{source, confidence, verified_at, evidence_url, validation_status, value}` (Phase 15
provenance model, `mergeCompanies.js` header). Nothing in the merge path consults it before
protecting — verified by grep, 2026-09-04.

## Shape of the fix

Make `manual_protected` **provenance-aware** rather than making `domain` promotable:

- Existing value has no provenance entry, or its provenance says a human/CRM source → refuse
  exactly as today. Unchanged behaviour, the `harveynorman` guard intact.
- Existing value's provenance says the enrichment system wrote it → allow correction when the
  new candidate clears a higher bar than the ordinary threshold (decide the bar; `domain` is
  `min_confidence: 95` today).
- Never let a franchisor/parent-company candidate win on confidence alone — the size-conflict
  detector already treats provider disagreement as a franchise signal; consider requiring
  no material conflict on the row.

**Parity (Phase 46 rule):** this is a shared merge predicate, so any change lands in
`src/merge_policy.py` in the SAME commit as `n8n/code/mergeCompanies.js`. Regenerate
`n8n/*.json` via `scripts/build_cloud_workflows.py` — never hand-edit.

**Test shape:** a system-provenance value is corrected; a human-provenance value is refused; a
value with no provenance at all is refused (fail closed). Offline, no live calls.

## Provenance

Operator raised it 2026-09-04 — *"why can't this be self-correcting? Can't the domain simply
be written over?"* — after hitting the Brisbane Lions case. Confirmed as a real gap rather
than a deliberate constraint; scheduled after the then-current work queue at the operator's
direction.

## Grounding established 2026-09-04 (read before planning — one of these changes the shape)

**1. The create seed writes NO provenance, so the fix as written is inert on the motivating
case.** `scripts/build_cloud_workflows.py` (`ENRICH_DECIDE_CO_CLOUD`, the `row.action ===
"create" && !returnOnly` branch) seeds `properties.domain = id.domain` directly — BUG 19's
fix — and never adds an entry to `lv_enrichment_provenance`. `properties.
lv_enrichment_provenance` is only written from `merge.provenance`, and `mergeCompanies` never
produces an entry for a `manual_protected` field because the gate refuses before the entry is
built. So Brisbane Lions `285583534546` carries a system-written domain with **no provenance
entry at all** — and the fail-closed rule ("no provenance entry → refuse") refuses it. The
offline test would pass while the live record stays stuck.

Therefore the fix needs a SECOND seam: the create branch must stamp a provenance entry for
the domain it seeds (a distinct system source — the seed is an identity echo of the request,
not a researched value), or the correction path has nothing to key on.

**2. Require the recorded value to still BE the current value.** A positive allowlist of
system sources is not enough on its own: if a human retyped the domain after the system wrote
it, the provenance entry still says "system". Gate on `provenance[field].value ===
currentValue` as well — mismatch means a human has since edited it, so refuse.

**3. Parity is TWO engines, not three.** `n8n/code/mergeContacts.js:128` carries the identical
`manual_protected` branch, but after 260826-20w no contact field is `manual_protected` any
more (`config/field_policy.yaml` contacts: `email` is `fill_blank_only` @ 80). The branch is
unreachable on the contacts lane; leave it alone and say so. The Phase 46 parity rule binds
`n8n/code/mergeCompanies.js` and `src/merge_policy.py`, in one commit, with `n8n/*.json`
regenerated by `scripts/build_cloud_workflows.py` — never hand-edited.
