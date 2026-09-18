---
created: 2026-09-18T13:35:00.000Z
updated: 2026-09-18
title: "A later ZoomInfo mint invalidates the earlier token, live-confirmed offline -- does the enrich lane's 24h cross-execution token cache buy anything given any concurrent mint can silently kill it?"
area: n8n-zoominfo-token
severity: minor
kind: design
decision_needed: "keep _zoom_split_gate_js's 24-hour cross-execution token cache on the enrich lane (accepting that ANY other mint -- backend-status's own mint node, a local probe, or a future discovery-lane request -- can invalidate a cached token mid-lifetime, relying on the leaf's existing isAuthError-clears-cache self-heal to recover on the NEXT run), or drop the cache there too and mint per-execution like the discovery lane now does (73.1-11 Task 1) -- trading one guaranteed free mint per run for immunity to this failure class"
owner: operator
files:
  - scripts/build_cloud_workflows.py
  - n8n/code/zoominfoToken.js
---

## Observed (73.1-11 Task 2, 2026-09-18, offline replay + one live token-replay round)

`scripts/probe_provider_discovery.py --token-replay` (`.venv/bin/python` via an in-process
dotenv driver, zero n8n executions, zero HubSpot calls, zero ZoomInfo search credits per D-13)
minted two ZoomInfo OAuth tokens (client-credentials grant) back to back against
`tennis.com.au`, then replayed the SAME `/gtm/data/v1/contacts/search` request:

```
step 1: mint A, search with A              -> 200, totalResults 1094
step 2: mint B (second mint)                -> 200 (mint succeeded)
step 3: replay the SAME search with token A -> 401
step 4: replay with token B (control)       -> 200, totalResults 1094
```

`prior_token_invalidated_by_later_mint: true`. Token A worked once, then stopped working
immediately after token B was minted -- with no expiry involved (both tokens' own `iat`/`exp`
claims show a normal 24h lifetime; token A's `exp` was over 23 hours away when it failed). The
full verdict, with only the two integer time claims recorded (no token value, no other claim):
`.planning/phases/73.1-provider-backed-contact-discovery-as-source-tier-2/73.1-TOKEN-REPLAY-VERDICT.json`.

This directly explains the `12668`/`12669` live 401s (`73.1-UAT.md` section 5a): those
executions reused a token cached by execution `12666` twenty-seven minutes earlier, and
*something* minted a new ZoomInfo token in the interim -- this replay shows that alone is
sufficient to invalidate the cached one, independent of the JWT's own claimed expiry.

## Consequence

This account issues (at most) one VALID ZoomInfo bearer token at a time -- minting a new one
invalidates whatever was minted before it, regardless of the earlier token's own `exp`. Any
node holding a cached token in workflow static data (`_zoom_split_gate_js`'s
`$getWorkflowStaticData("global").zoominfo`, used by the enrich lane, the company-enrich
branch, and the usage/credit-check branch -- see `scripts/build_cloud_workflows.py` lines
~5998-6053) is exposed to silent invalidation by ANY other process that mints a fresh token in
the meantime: `LV Backend Status`'s own mint node, a local `check_provider_credits.py`/
`probe_provider_discovery.py` run, or (after this plan) the discovery lane's own per-execution
mint. `73.1-11` Task 1 sidesteps this for the discovery lane specifically by dropping its
cache entirely (`_discovery_zoom_search_gate_js`, mint-per-execution, unconditional) -- that
lane runs exactly one execution per round (D-08), so the cache bought at most one free mint in
exchange for the whole failure class. The enrich lane makes MANY ZoomInfo calls per execution,
so the same tradeoff does not obviously hold there, and this todo is deliberately NOT changing
it (its leaf already clears the cache on its OWN 401 and self-heals on the next run -- see
`_zoom_split_enrich_contacts_js`/`_zoom_split_enrich_companies_js`'s `isAuthError`-clears-cache
path -- so the cache's downside is bounded to "the current run 401s once, the next run
re-mints", not an unrecoverable outage).

## Decision needed

Whether to:
(a) keep the enrich lane's 24-hour cross-execution cache as-is, accepting that a concurrent
    mint anywhere else can invalidate it mid-lifetime and cost the CURRENT run one 401 (which
    the existing `isAuthError`-clears-cache path already recovers from on the next run); or
(b) drop the cache on the enrich lane too, mirroring the discovery lane's mint-per-execution
    gate, trading the one-free-mint-per-run saving for immunity to this whole failure class --
    at the cost of one extra OAuth mint call on every enrich-lane execution that touches
    ZoomInfo (this account's OAuth mints are unmetered/free, per `check_provider_credits.py`'s
    own usage of the same endpoint).

Not resolved here -- 73.1-11 Task 2's own explicit scope boundary ("Do NOT change the enrich
lane here").
