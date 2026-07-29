---
status: root_caused_not_fixed
created: 2026-07-29
found_by: "Generalizing execution 22's mechanism (ingest, BUG 22) to the enrichment contacts lane — not yet reproduced there live"
related: bug-22 (fixed, same mechanism), bug-10 (the transport that is immune)
---

# BUG 23 — enrichment contacts: a no-match search stops the chain, so `contact:create` is unreachable

## Claim

`wf_enrichment_cloud.json`'s `HubSpot Search` and `HubSpot Fetch By Id` are native
`n8n-nodes-base.hubspot` `contact:search` nodes. Execution 22 (ingest lane) established
empirically that this node emits **zero items on zero hits, and n8n stops the chain there**
— downstream nodes simply never run.

Applied to the enrichment lane, that means:

- A webhook event for an email with **no existing HubSpot record** dies at `HubSpot
  Search`. The Enrichment Gate never runs, providers never run, and `action: "create"`
  can never be reached. **The enrichment contacts create path is structurally dead**, not
  merely unexercised.
- A bare event for a **deleted/nonexistent object id** dies at `HubSpot Fetch By Id`,
  which means `adaptFetchById`'s carefully-tested 0-result / `lookup_failed` handling is
  dead code for the exact case it exists for: the adapter cannot classify a result that
  never arrives as an item.

## Why the offline suite is green anyway

`bareEventChainFlow.test.mjs` (and the SC-6 safe-degradation tests) mock every HTTP-typed
step as **one item** — including the 0-result case, modeled as `{total: 0, results: []}`
arriving as an item. That is the CRM v3 envelope shape, which is what the **httpRequest**
transport returns. The native node flattens instead: 0 results → 0 items. The harness
faithfully models the hazard bd682a2 taught ($json replacement) but not this one (item
non-emission), so the no-match path passes offline and stalls live.

## Why every live execution to date missed it

Every enrichment contacts execution ever run (8–15, 19) used contact 201 or another
**existing** record — the match case. The no-match case has never once been fired at the
live lane. The companies branch is immune by accident of BUG 10: its searches were forced
onto the httpRequest envelope transport, which emits exactly one item regardless of hits
— and its no-match path HAS run live (execution 16's create attempt reached the write).

## Status: not fixed here, deliberately

The fix is known and now proven twice in this repo (BUG 10, BUG 22): move the two nodes to
the credential-bound httpRequest envelope transport; `ENRICH_ADAPT_SEARCH` and
`adaptFetchById.js` already parse the envelope shape. But:

- `HubSpot Search` (match case) is the single most live-proven node in the system — the
  entire 16.7 non-clobber canary chain runs through it. Churning it at the tail of this
  session, without a live re-canary of the match case afterwards, trades a dead
  never-used path for risk to the one path that demonstrably works.
- `tests/test_bug10_company_search_transport.py` pins both nodes byte-identical **by
  design**, precisely to stop drive-by migration of the proven path. Overriding that
  guard deserves its own plan, its own tests (a no-match live canary BEFORE and AFTER),
  and a fresh session.

## What the fix's plan must include

1. Transport swap for `HubSpot Search` + `HubSpot Fetch By Id` (mirror BUG 22's change,
   including the `lookup_failed` item-error mapping).
2. Drop both nodes from the byte-identical pin with the same documented rationale as the
   prior two removals (the guard was pinning a node broken for half its input space).
3. Live canary BOTH cases: existing contact (201 — must still match and enrich) and a
   nonexistent email (must reach `Decide Action` as `create`, write-gated).
4. The harness gap: teach `bareEventChainFlow`'s http mocks to model the native node's
   0-item behavior, or better, assert the lane no longer contains native search nodes.
