---
created: 2026-09-04T18:10:00.000Z
updated: 2026-09-04
resolved_by: quick-260904-pav
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

## Closure (quick task 260904-pav, 2026-09-04)

Resolved by
`.planning/quick/260904-pav-provenance-aware-manual-protected/260904-pav-PLAN.md`.

**What landed.**

- `manual_protected` is provenance-aware in BOTH engines (`n8n/code/mergeCompanies.js`,
  `src/merge_policy.py`, one commit, Phase 46 parity, `n8n/*.json` regenerated). Four
  conjuncts, each independently asserted to refuse: an allowlisted provenance source
  (`system_correctable_sources`, per-field, `["create_seed"]` on `companies.domain` and
  nowhere else), the recorded value still equal to the current value (grounding finding 2),
  no material conflict on the row (the `harveynorman.com.au` franchise detector, reused not
  reinvented), and the field's own `min_confidence` of 95 with no new threshold key.
- The `domain` hard guard in `mergeCompanies.js` — a SECOND refusal seam the todo did not
  name, which would have re-refused every correction — now tests a structural
  `gate.correction` flag. Every other `domain` promote still demotes.
- The create branch stamps `{source: "create_seed", validation_status: "request_echo",
  confidence: 0}` for the domain it seeds (grounding finding 1), so the correction path has
  something to key on. `request_echo` is a new entry in CLAUDE.md §6.1's vocabulary.
- The enrichment lane's provenance write is now ADDITIVE. It previously REPLACED the blob
  with this run's `merge.provenance`, so the first enrich after a create wiped the seed —
  and, independently, every other field's entry it did not touch that run. A latent loss
  affecting every field, not just `domain`.
- Grounding finding 3 honoured: `n8n/code/mergeContacts.js`'s identical `manual_protected`
  branch is unreachable (no contact field carries the class after 260826-20w) and was left
  alone.

**What did NOT land, and is not implied to work.** The live Brisbane Lions record
`285583534546` is still stuck. Nothing in the pipeline can PROPOSE a company domain: no
`normalizeProviders.js` branch pushes one, the research fold does not supply one, and the
company providers are looked up BY the record's domain so they cannot contradict it. The
mechanism is correct, tested and inert. Recorded as its own todo —
`.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md` — which also
names a second decision the first real candidate will force (a REFUSED candidate's entry
overwrites the `create_seed` entry under this-run-wins, closing the path for that record).

Zero live HubSpot calls, zero provider credits, zero n8n executions; the regenerated JSON is
committed undeployed per CLAUDE.md §13.0.2.
