---
status: resolved
created: 2026-07-29
resolved: 2026-07-29
found_by: "Second armed review canary (execution 52) — the gate denied a correctly-allowlisted record"
related: bug-24-domain-allowlist-inert-on-company-write-lanes.md (my own incomplete fix), bug-12 / bug-21 (row-carry family)
---

# BUG 25 — `Apply Review` dropped the row, so BUG 24's fix never reached the gate

## Symptom

With the build armed (`ALLOW_HUBSPOT_RECORD_WRITES="true"`,
`TEST_RECORD_DOMAINS="lv-review-canary-delete-me.example"`) and a canary company carrying
exactly that domain, execution 52 still denied the write:

```
Review Extract Rows   domain = 'lv-review-canary-delete-me.example'   <- present
Apply Review          domain = None                                   <- GONE
Review Apply Update Write Gate   0 items (denied)
```

Deployed constants were verified correct on the live workflow, so the allowlist was not the
problem: the field the gate compares against simply no longer existed on the row.

## Root cause

`ENRICH_APPLY_REVIEW` ended with:

```js
return { json: { hs_object_id: row.hs_object_id, ...result, properties } };
```

A freshly constructed object with no `...row` spread — so every field except the four it
names is discarded. `domain` died two nodes before the gate that reads it.

This is the row-carry family (BUG 12's Set node, BUG 21's Set Config binary) in a Code node,
and it made **my own BUG 24 fix inert**: adding `domain` to Review Search's property list was
necessary and insufficient, because the value was dropped in transit. Worth stating plainly —
the earlier fix was verified at the search and at the gate's *expression*, never along the
path between them.

## The guard hole that let it through

`test_write_gates_domain_allowlist_is_usable_by_every_company_lane` (added with BUG 24)
computed availability as `_emitted_fields(feeder) | _search_properties(feeder)`. That union
answers "is `domain` requested somewhere upstream", not "does it survive to the gate" — so a
lane that requests it and then drops it passed.

Tightened: `_search_properties` is now consulted only when the chain actually flattens a
search row (`{ ...(r.properties || {}) }`), via a new `_spreads_search_row()` helper.
`_emitted_fields` — which inherits only across an explicit spread, and therefore correctly
models a fresh-object node as dropping everything — is the authority.

**Non-vacuity proven by reconstruction**, not assumed:

| artifact | guard result |
|---|---|
| HEAD (both fixes) | clean |
| pre-BUG-25 (row spread removed) | fires on `Review Apply Update Write Gate` |
| pre-BUG-24 as well (`domain` also removed from the search) | fires |

## Fix

`return { json: { ...row, hs_object_id: row.hs_object_id, ...result, properties } };` —
`properties` and the result keys are assigned after the spread, so they still win.

## Exposure

None. Fail-closed at every step; the cost was two armed operator windows that produced no
write. Both canary records were throwaways.
