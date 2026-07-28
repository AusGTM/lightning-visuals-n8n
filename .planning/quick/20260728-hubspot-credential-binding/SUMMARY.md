---
type: quick
slug: hubspot-credential-binding
subsystem: infra
tags: [n8n, hubspot, deploy, credentials, pre-activation]

key-files:
  created:
    - tests/test_deploy_credential_binding.py
  modified:
    - scripts/deploy_n8n_workflows.py

key-decisions:
  - "Scoped the fail-closed guard by node TYPE (hubspot always; httpRequest/webhook only when their own authentication param is credential-bearing), not a blanket every-node-needs-a-credential rule -- preserves the deliberate secret-free Bearer-only ZoomInfo Code-node pattern from Phase 16-01."
  - "Proved the fail-closed path against a deepcopy of NODE_CREDENTIAL_MAP with one entry deleted, never by mutating the real map."

duration: ~25min
completed: 2026-07-28
status: complete
---

# Quick: HubSpot credential binding -- Summary

**Bound the 10 unmapped HubSpot nodes to `LV HubSpot` and made `bind_credentials()` fail closed by node type instead of silently deploying any unmapped node unbound.**

## Performance

- **Tasks:** 3/3 complete
- **Files modified:** 2 (1 modified, 1 created)

## Accomplishments

- Added all 10 previously-unmapped `n8n-nodes-base.hubspot` nodes to `NODE_CREDENTIAL_MAP` (1 in `wf_contact_ingest_cloud.json`, 9 in `wf_scheduled_maintenance_cloud.json`), each bound to `hubspotAppToken` / `LV HubSpot` -- grouped under per-workflow comments matching the map's existing style.
- Replaced the silent `if mapping is None: continue` in `bind_credentials()` with a type-scoped fail-closed check: `n8n-nodes-base.hubspot` nodes always require a credential; `n8n-nodes-base.httpRequest` nodes require one only when `parameters.authentication` is `genericCredentialType`/`predefinedCredentialType`; `n8n-nodes-base.webhook` nodes require one only when `parameters.authentication` is set and not `"none"`. Every other node type (Code, IF, Set, NoOp, Merge, Schedule Trigger, ...) is unaffected and still passes through untouched.
- Added `tests/test_deploy_credential_binding.py` (21 tests) covering: the zero-unmapped sweep generalized across every built `n8n/wf_*_cloud.json` (not just `wf_enrichment_cloud.json`, closing the exact gap that let these 10 nodes hide), fail-closed for unmapped hubspot/httpRequest/webhook nodes with credential-bearing auth, pass-through for non-credential node types and the secret-free ZoomInfo Bearer-only nodes, and the pre-existing mapped-but-unresolvable-credential-name fail-closed path.

## Task Commits

1. **Task 1: bind the 10 nodes** - `dbb07d5` (fix)
2. **Task 2: fail closed on unmapped credential-requiring nodes** - `fbc7509` (fix)
3. **Task 3: regression test** - `16ca87c` (test)

## Files Created/Modified

- `scripts/deploy_n8n_workflows.py` - 10 new `NODE_CREDENTIAL_MAP` entries; new `_node_requires_credential()` helper; `bind_credentials()` now raises for unmapped nodes whose type requires a credential.
- `tests/test_deploy_credential_binding.py` - new regression suite (21 tests), pure-function only, no network mocking needed.

## Decisions Made

- Scoped the guard by node type + `authentication` parameter rather than a blanket rule, per the plan's explicit warning not to break the secret-free ZoomInfo split-code-node architecture (Phase 16-01 decision).
- Proved fail-closed behavior with a `copy.deepcopy()` of `NODE_CREDENTIAL_MAP` with entries deleted -- never mutated the real map, per plan's scope fence.

## Deviations from Plan

None -- plan executed exactly as written. All three tasks' acceptance criteria verified live against the built `n8n/wf_*_cloud.json` workflows (not just asserted in isolation):
- Zero unmapped hubspot nodes across all three built cloud workflows.
- `bind_credentials()` succeeds on all three built workflows with a fake id-map.
- Removing any one of the 10 newly-mapped nodes from a copied map raises for that node (proven individually via a parametrized test, one per node).
- Code/IF/Set nodes and the secret-free `httpRequest` node (`Verify Emails (batch)`, no `authentication` param) pass through with no `credentials` block and no raise.

## Issues Encountered

None. One pre-existing, unrelated 1ms-timing flake was observed in `tests/n8n/mergeContacts.test.mjs` on the first `node --test` run (a `Date.now()` value differing by 1ms between two calls in that test); a clean rerun showed 258/258 passing. This file is untouched by this quick task's scope and the flake is not a regression introduced here.

## Verification

```
.venv/bin/python -m pytest -q          # 384 passed (363 baseline + 21 new), 0 regressions
node --test tests/n8n/*.test.mjs       # 258 passed, 0 regressions (rerun after unrelated 1ms flake)
git status --short n8n/                # empty -- no workflow JSON regenerated
```

## Next Phase Readiness

Pre-activation blocker resolved: all HubSpot nodes across all three built Cloud workflows now bind to a real credential id or the deploy fails closed before any write -- no path remains for a HubSpot node to deploy unbound and 401 silently at runtime. Track B live runbook (referenced in the paused `e7fc6ca` commit) can proceed without this specific blocker.

---
*Quick task: 20260728-hubspot-credential-binding*
*Completed: 2026-07-28*
