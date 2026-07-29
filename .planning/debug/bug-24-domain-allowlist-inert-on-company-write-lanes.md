---
status: resolved
created: 2026-07-29
resolved: 2026-07-29
found_by: "First armed review canary — the operator armed TEST_RECORD_DOMAINS and the lane could not possibly have used it"
related: bug-16-write-lane-contract-drift.md (same family, unconditional form)
---

# BUG 24 — `TEST_RECORD_DOMAINS` was silently inert on every company write lane

## Symptom

Every write gate resolves its domain as:

```js
(it.json.identity_keys && it.json.identity_keys.domain) || it.json.domain || null
```

The three scheduled-maintenance company write lanes emit **neither**. Their rows are built
by `Extract Search Rows` as `{ ...(r.properties || {}), hs_object_id: r.id }`, so the row
contains exactly the properties the SEARCH requested — and `domain` was in none of the three
property lists:

| Lane | Gate | `domain` requested? |
|---|---|---|
| SJ-1 Set Requested | SJ-1 Set Requested Write Gate | no |
| SJ-2 Set Requested | SJ-2 Set Requested Write Gate | no |
| Review Apply Update | Review Apply Update Write Gate | no |

So `_writeSafetyAllows(action, hs_object_id, null)` could only ever be satisfied by
`TEST_RECORD_IDS`. Arming with `TEST_RECORD_DOMAINS` produced silence, not a write.

Confirmed live on execution 47's captured row: `Extract Rows` keys were
`createdate, hs_lastmodifieddate, hs_object_id, lv_*` — no `domain`.

## Root cause

Same family as BUG 16: **a gate reading a field its lane never emits**. BUG 16 was the
unconditional form (the id was absent, so the gate denied everything). This is the partial
form — one of the two allowlists works, the other is inert — which is why it survived the
BUG 16 sweep and its guard. `test_write_lane_contracts.py` asserted the gate's *id*
expression was satisfiable; nothing asserted the *domain* expression was.

The blind spot was structural, not careless: `_emitted_fields()` reads Code-node source,
and these field names never appear in any Code node — they live in the search node's
`properties: [...]` list.

## Fix

`domain` added to all three searches' property lists (SJ-1, SJ-2, Review), and the pins in
`test_bug10_company_search_transport.py` updated to match.

`tests/test_write_lane_contracts.py::test_write_gates_domain_allowlist_is_usable_by_every_company_lane`
closes the class: for every gated COMPANY write node whose gate consults a domain
allowlist, the lane must make `domain` (or `identity_keys`) available. It resolves
search-derived properties via a new `_search_properties()` helper that walks back to the
search node's `properties` list — the blind spot that hid this.

CONTACT lanes are exempt by construction and the test says so: a contact has no `domain`,
so `TEST_RECORD_DOMAINS` is legitimately inapplicable there and `TEST_RECORD_IDS` is the
only allowlist that can apply. An earlier draft of the guard over-fired on exactly that and
was scoped rather than suppressed.

## Blast radius / exposure

None. Fail-closed in every case — the failure mode is a write that does not happen. The
cost was an operator arming a canary by domain and getting an unexplained no-op, which is
precisely what BUG 16's write-up warned about: "a wall rather than a gate, silent about why."
