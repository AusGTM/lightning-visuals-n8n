---
phase: 17-enrichment-contacts-reachability-bug-23
plan: 01
subsystem: n8n-cloud-workflows
tags: [bug-23, hubspot, transport-swap, offline-harness, tdd]
dependency-graph:
  requires: [BUG-10, BUG-22]
  provides: [REACH-01-node-shape, REACH-02-pin-removal, REACH-04-harness-reachability]
  affects: [scripts/build_cloud_workflows.py, n8n/wf_enrichment_cloud.json]
tech-stack:
  added: []
  patterns: [resource->URL lookup table, credential-bound httpRequest envelope transport, red-before-green test authorship]
key-files:
  created:
    - tests/test_enrichment_contacts_search_transport.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - tests/test_bug10_company_search_transport.py
    - tests/test_fetch_by_id_topology.py
    - tests/test_cloud_write_path.py
    - tests/test_deploy_flag_overlay.py
    - tests/n8n/bareEventChainFlow.test.mjs
decisions:
  - "Widened `_hs_http_search_node()` from a companies-only hard-fail to a resource->URL table (company/contact) rather than adding a second helper — one call site for both resources, still hard-fails on anything unaudited."
  - "Node NAMES preserved across the transport swap so NODE_CREDENTIAL_MAP required zero changes — credential binding by name was already correct."
  - "Widened tests/test_deploy_flag_overlay.py's composition check via the house `_hubspot_bound_node_names()` helper (copied, not cross-imported, per house convention) instead of leaving a native-only filter that would have gone vacuous."
metrics:
  duration: "~35 minutes"
  completed: 2026-07-29
status: complete
---

# Phase 17 Plan 01: Transport swap + pin removal + harness reachability (offline) Summary

Moved `wf_enrichment_cloud.json`'s "HubSpot Search" and "HubSpot Fetch By Id" off the native
`n8n-nodes-base.hubspot` `contact:search` node onto the credential-bound httpRequest CRM v3
envelope transport (BUG 22's proven pattern), dropped both from the byte-identical
transport pin, and taught the offline harness to drive a no-match search all the way to
`action: "create"`, write-gated — closing the gap where the harness's one-item HTTP mocks
were faithful to the transport this lane now uses, but were never faithful to the native
node they replaced. No live call, no deploy — Plan 02 is the live canary.

## What Was Done

### Task 1 — Transport swap, pin removal, guard rebuild (commit `7b95309`)

1. **RED first.** Wrote `tests/test_enrichment_contacts_search_transport.py` (10 tests:
   vacuity guard, transport shape, credential-map entries, real-JSON-array properties,
   filter parity, no-native-node assertion) and ran it against the pre-swap committed
   workflow. 7 of 10 failed, exactly the transport-dependent assertions (see Red-Before-
   Green Evidence below). The 3 that passed (vacuity + credential-map checks) were
   correctly unaffected by transport and expected to pass regardless.
2. **Widened `_hs_http_search_node()`** (`scripts/build_cloud_workflows.py`) from a
   `resource != "company": raise ValueError` hard-fail to a `_HS_SEARCH_URLS` lookup table
   (`company` -> companies search URL, `contact` -> contacts search URL); anything else
   still hard-fails, so the migration cannot silently spread to an unaudited resource.
   Docstring extended with BUG 23's honest distinction from BUG 10: BUG 10's operation
   doesn't exist at all; BUG 23's operation exists and works on a hit, but emits zero items
   on zero hits and n8n stops the chain there.
3. **Rebuilt both nodes** through `_hs_http_search_node()` in `build_enrichment_cloud()`,
   preserving filter semantics (`email`/`EQ`/`$json.identity_keys.email` for the search;
   `hs_object_id`/`EQ`/`$('Build Identity').item.json.object_id` for the fetch) and node
   NAMES exactly, so `NODE_CREDENTIAL_MAP` in `scripts/deploy_n8n_workflows.py` needed zero
   changes. Rebuild touched only `n8n/wf_enrichment_cloud.json`; verified deterministic
   between two successive builder runs (byte-identical output) and, after commit,
   `git diff --quiet n8n/` passes.
4. **`_hs_search_node()`** docstring updated: it now has exactly one call site left
   ("Dedupe Search (candidate contacts)", `wf_scheduled_maintenance_cloud.json`), which
   carries the SAME zero-item hazard and is deliberately out of this phase's fence — see
   "Known, Unfixed Sibling" below.
5. **Dropped both nodes from the byte-identical pin** (`tests/test_bug10_company_search_transport.py`'s
   `CONTACT_NODES_BY_WORKFLOW`) with the rationale the three prior removals used: the guard
   was pinning a node broken for half its input space. `contact:search` really does return
   the record on a hit (why the pin looked justified and why executions 8-15/19 all
   passed); zero hits emit zero items and stop the chain, so `contact:create` was
   structurally dead. Named `tests/test_enrichment_contacts_search_transport.py` as the
   replacement guard.
6. **Fixed the shape guards that assumed a native contacts node** — all fixed by describing
   the new shape, never by loosening an assertion:
   - `tests/test_fetch_by_id_topology.py`: deleted the native-only fetch test, generalized
     the httpRequest fetch test to `@pytest.mark.parametrize("branch", ["contacts",
     "companies"])` (added `url` to `BRANCHES`); merged the two property-match tests into
     one parametrized test using `_extract_json_body_properties`; replaced the
     now-vacuous `test_every_hubspot_node_uses_an_allowed_operation` with
     `test_no_native_hubspot_node_remains_in_the_workflow`; widened the httpRequest sweep
     vacuity test to require all four search/fetch nodes.
   - `tests/test_cloud_write_path.py`: converted both contacts filter tests to read
     `jsonBody` exactly as their `HubSpot Company Search` twins already do; updated the
     docstring that said contacts "stays the native node".
   - `tests/test_deploy_flag_overlay.py`: widened
     `test_enabled_through_real_path_and_bind_credentials_succeeds`'s composition check
     from a bare `type == "n8n-nodes-base.hubspot"` filter (which would have gone vacuous —
     the exact "a guard that silently stops applying" failure mode) to the house
     `_hubspot_bound_node_names()` helper (native + httpRequest/hubspotAppToken), copied
     into this file per the house no-cross-import convention rather than inventing a third
     variant.

### Task 2 — Harness reachability (commit `0ce1fd8`)

1. Added a comment block in `tests/n8n/bareEventChainFlow.test.mjs` recording why one-item
   HTTP mocks are faithful now (envelope transport: always exactly one item) and were not
   before (native node: 0 hits -> 0 items -> chain stops), citing BUG 23 and execution 22.
2. Added a precondition test asserting "HubSpot Search"/"HubSpot Fetch By Id" in the loaded
   workflow are `n8n-nodes-base.httpRequest` — the harness states its own precondition
   instead of assuming it.
3. Added `CONTACT_NO_MATCH_CHAIN` (`CONTACT_CHAIN` with the fetch-by-id hop swapped for the
   direct-search hop) and `CONTACT_NO_MATCH_HTTP_MOCKS` (`{"HubSpot Search": {results: [],
   total: 0}, "Lusha Enrich": {}, "Apollo Match": {}}`), seeded with
   `lv-bug23-canary-delete-me@lv-canary-delete-me.example` — the same address family Plan 02
   fires live.
4. New test asserts: `Adapt Search` reports `lookup_failed: false` with `existingRecord`
   deep-equal `{}` (confirmed-absent, not a lookup failure — getting this backwards would
   route a genuine new contact to skip); `Enrichment Gate` returns `action: "create"` (the
   path structurally unreachable before the transport swap); `Decide Action` returns
   `action: "write_blocked"` with the BUG 19 create-seed email in `properties.email`
   (create path reachable AND write-gated by default).

## Red-Before-Green Evidence

Captured against the pre-swap committed `n8n/wf_enrichment_cloud.json`, before touching
`scripts/build_cloud_workflows.py`:

```
.FF..FFFFF                                                               [100%]
FAILED tests/test_enrichment_contacts_search_transport.py::test_node_is_credential_bound_httprequest_via_hubspot_apptoken[HubSpot Search]
FAILED tests/test_enrichment_contacts_search_transport.py::test_node_is_credential_bound_httprequest_via_hubspot_apptoken[HubSpot Fetch By Id]
FAILED tests/test_enrichment_contacts_search_transport.py::test_node_requests_the_expected_properties_as_a_real_json_array[HubSpot Search]
FAILED tests/test_enrichment_contacts_search_transport.py::test_node_requests_the_expected_properties_as_a_real_json_array[HubSpot Fetch By Id]
FAILED tests/test_enrichment_contacts_search_transport.py::test_node_body_preserves_the_original_filter_semantics[HubSpot Search]
FAILED tests/test_enrichment_contacts_search_transport.py::test_node_body_preserves_the_original_filter_semantics[HubSpot Fetch By Id]
FAILED tests/test_enrichment_contacts_search_transport.py::test_no_native_hubspot_node_remains_in_enrichment_contacts_lane
7 failed, 3 passed in 0.08s
```

(The 3 passing were the vacuity guard and the credential-map checks — correctly unaffected
by transport, since node NAMES don't change.)

Task 2's test cannot be run red against the pre-swap JSON by the same mechanism (the
harness already modelled one item regardless of transport — that IS the harness gap
REACH-04 names). Its red-run proof is the precondition assertion instead, verified directly
against the pre-swap workflow (`git show 705b001:n8n/wf_enrichment_cloud.json`): both nodes
are `n8n-nodes-base.hubspot`, so `assert.equal(byName[name].type,
"n8n-nodes-base.httpRequest")` would fail there.

## Deviations from Plan

### Auto-fixed / documented, no user permission needed

**1. Exact pytest count is 596, not 587+N.** The plan's verify step says "expect 587+N
passed (N = new tests)". `tests/test_enrichment_contacts_search_transport.py` adds 10
tests, so a naive count would predict 597. The actual count is **596**: dropping the
`wf_enrichment_cloud.json` key from `CONTACT_NODES_BY_WORKFLOW` (REACH-02, by design) also
removed one parametrized case from
`test_bug10_company_search_transport.py::test_every_contact_node_is_byte_identical_to_head`
(2 dict keys -> 1 key = 2 parametrized instances -> 1). Net: 587 + 10 - 1 = 596. This is a
deliberate consequence of the pin removal the plan itself specifies, not a regression —
documented here per the plan's own "record the exact new baseline count" instruction.
**Phase 18's baseline is 596 pytest / 285 node tests.**

**2. One transient node-test flake observed, unrelated to this plan's files.** A single
rerun of `node --test tests/n8n/*.test.mjs` showed one assertion failure comparing two
`new Date().toISOString()` values a millisecond apart (a `lv_jobtitle_verified_at`
timestamp mismatch), in a test file not touched by this plan. Reran immediately after and
got a clean 285/285 with zero failures; ran it again for good measure — clean. Not
investigated further (out of this plan's file scope per the deviation rules' scope
boundary), but flagged here in case it recurs and needs its own bug report.

No Rule 4 (architectural) deviations. No auth gates encountered. No live calls made,
per the plan's OFFLINE ONLY constraint.

## Verification Results

- `.venv/bin/python -m pytest -q` -> **596 passed, 0 failed** (new Phase 18 baseline).
- `node --test tests/n8n/*.test.mjs` -> **285 passed, 0 failed** (283 baseline + 2 new
  tests: the precondition assertion + the BUG 23 no-match test). One transient flake
  observed on a single rerun in an unrelated file (see Deviation 2); confirmed clean on
  two subsequent reruns.
- `.venv/bin/python scripts/build_cloud_workflows.py` run twice -> byte-identical
  `n8n/wf_enrichment_cloud.json` output (deterministic builder). Post-commit,
  `git diff --quiet n8n/` passes.
- Built `n8n/wf_enrichment_cloud.json` contains **zero** `n8n-nodes-base.hubspot` nodes;
  both swapped nodes ("HubSpot Search", "HubSpot Fetch By Id") kept their exact NAMES,
  now `n8n-nodes-base.httpRequest` typeVersion 4.2, `POST
  https://api.hubapi.com/crm/v3/objects/contacts/search`,
  `authentication: predefinedCredentialType` / `nodeCredentialType: hubspotAppToken`,
  `onError: continueRegularOutput`.
- `tests/test_deploy_flag_overlay.py::test_enabled_through_real_path_and_bind_credentials_succeeds`
  passes: the widened sweep collects all 4 `hubspotAppToken` httpRequest nodes and asserts
  each is credential-bound.

## Known, Unfixed Sibling (recorded, not fixed)

`Dedupe Search (candidate contacts)` in `wf_scheduled_maintenance_cloud.json` is now the
**only** remaining call site of `_hs_search_node()` (the native-node helper). It carries the
exact same zero-items-on-zero-hits hazard BUG 23 fixes here, and is deliberately **out of
this phase's fence** — REACH-01 is scoped to the enrichment lane, not the scheduled
maintenance dedupe lane. Left as a known concern for a future phase, per the plan's explicit
carve-out.

## ROADMAP Success Criteria Status

| # | Criterion | Status |
|---|---|---|
| 1 | `HubSpot Search`/`HubSpot Fetch By Id` on the credential-bound httpRequest envelope transport | **Node-shape half done** — both nodes rebuilt, shape/credential/filter/property parity offline-pinned. The *live* half (proving a zero-hit search actually emits one classifiable item against the real n8n Cloud instance) is Plan 02's job; nothing here is proven live yet. |
| 2 | Pin dropped + harness updated, offline suite green with zero regressions | **Fully met.** Both nodes removed from `CONTACT_NODES_BY_WORKFLOW` with documented rationale; shape re-pinned in the new guard file; `bareEventChainFlow.test.mjs` now drives a no-match search to `action: "create"`, write-gated. 596 pytest / 285 node tests green. |
| 3 | Live canary case A (match regression) | **Belongs to Plan 02.** Not attempted here (OFFLINE ONLY). |
| 4 | Live canary case B (create reachability) | **Belongs to Plan 02.** Offline twin built and green here (this Summary's Task 2); the live proof is Plan 02's job. |
| 5 | Deployment restored disarmed, read back to confirm | **Belongs to Plan 02.** No deploy occurred in this plan. |

## What Plan 02 Must Know

- The built `n8n/wf_enrichment_cloud.json` is ready to deploy: both "HubSpot Search" and
  "HubSpot Fetch By Id" are now `n8n-nodes-base.httpRequest` POSTs to
  `https://api.hubapi.com/crm/v3/objects/contacts/search`, credential-bound via
  `predefinedCredentialType`/`hubspotAppToken` (`NODE_CREDENTIAL_MAP` unchanged — same
  node names, same "LV HubSpot" credential).
- Live canary case A (regression) target: contact **201** (the same record every prior
  enrichment contacts execution 8-15/19 matched against) — must still match and enrich
  exactly as before the transport swap.
- Live canary case B (reachability) target: fire an event for an email with no existing
  HubSpot record and confirm it reaches `Decide Action` with `action: "create"`, write-
  gated (no actual write unless the deploy is deliberately armed for an allowlisted test
  record). The offline twin of this case is
  `tests/n8n/bareEventChainFlow.test.mjs`'s new "BUG 23: a no-match search reaches
  action:create..." test — seeded with
  `lv-bug23-canary-delete-me@lv-canary-delete-me.example`. Plan 02 should use the same
  address family for its live canary (per this plan's own note) so the fixture and the
  live probe stay recognizably paired.
- After both canaries: restore the deploy to its disarmed state and read it back from n8n
  Cloud to confirm no write gate was left armed — per Phase 17's Success Criterion 5.
- `Dedupe Search (candidate contacts)` remains on the native node with the same hazard,
  out of scope for both plans in this phase.
- New baseline for any future plan in this milestone: **596 pytest passed / 285 node tests
  passed**, both 0 failures.

## Self-Check: PASSED

- `tests/test_enrichment_contacts_search_transport.py` — FOUND
- `n8n/wf_enrichment_cloud.json` (modified) — FOUND
- `scripts/build_cloud_workflows.py` (modified) — FOUND
- `tests/n8n/bareEventChainFlow.test.mjs` (modified) — FOUND
- commit `7b95309` — FOUND in `git log --oneline --all`
- commit `0ce1fd8` — FOUND in `git log --oneline --all`
