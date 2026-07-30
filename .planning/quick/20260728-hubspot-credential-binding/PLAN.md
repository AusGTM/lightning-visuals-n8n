---
type: quick
slug: hubspot-credential-binding
created: 2026-07-28
status: complete
files_modified:
  - scripts/deploy_n8n_workflows.py
  - tests/test_deploy_credential_binding.py
---

# Quick: bind the 10 unmapped HubSpot nodes + make unmapped credential-requiring nodes fail closed

## Why now

Pre-activation blocker found during Phase 16.4 and confirmed live 2026-07-28. `bind_credentials()`
(`scripts/deploy_n8n_workflows.py:153-172`) fails closed for a node that IS in `NODE_CREDENTIAL_MAP`
but whose credential name has no provisioned id — but a node that is **absent from the map entirely**
hits `if mapping is None: continue` and deploys **unbound**, silently, 401-ing only at runtime.

Enumerated against the built workflows (verified, not assumed):

```
wf_contact_ingest_cloud.json        3 hubspot nodes, 1 UNMAPPED
    - HubSpot Search by Email
wf_enrichment_cloud.json            8 hubspot nodes, 0 UNMAPPED
wf_scheduled_maintenance_cloud.json 9 hubspot nodes, 9 UNMAPPED
    - SJ-3 Search (requested poller)
    - SJ-1 Search (input-gap scan)
    - SJ-1 Set Requested
    - SJ-2 Search (stale refresh)
    - SJ-2 Set Requested
    - Dedupe Search (candidate contacts)
    - Dedupe Set Needs Review
    - Review Search (approved=true)
    - Review Apply Update
```

All 10 are `n8n-nodes-base.hubspot` and all need the same binding the 8 already-mapped enrichment
nodes use: `cred_type: "hubspotAppToken"`, `cred_name: "LV HubSpot"`.

Phase 16.4-02 added a credential guard, but scoped it to `wf_enrichment_cloud.json` only — which is
exactly why these 10 stayed invisible. Adding 10 map entries fixes today; the silent-skip path is
what invites the next one, so both get fixed.

## Tasks

### Task 1 — bind the 10 nodes

Add the 10 node names above to `NODE_CREDENTIAL_MAP`, each as
`{"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"}`.

Group them under comments naming their workflow (`wf_scheduled_maintenance_cloud.json`,
`wf_contact_ingest_cloud.json`) so the map stays readable and the next reader can tell at a glance
which workflow a name belongs to — the existing map already uses this commenting style per phase.

**Acceptance:**
- A script iterating every `n8n/wf_*.json`, collecting nodes of type `n8n-nodes-base.hubspot` not
  present in `NODE_CREDENTIAL_MAP`, returns **zero** across all workflows.
- No other entry in the map is modified — `git diff` on the map shows additions only.

### Task 2 — make unmapped credential-requiring nodes fail closed

Change the `mapping is None` branch so it raises for node types that REQUIRE credentials, instead of
silently continuing. Non-credential nodes (Code, IF, Set, NoOp, Merge, Schedule Trigger…) must keep
passing through untouched — the guard must not become a blanket "every node needs a credential".

Scope the requirement by node type:
- `n8n-nodes-base.hubspot` — always requires a credential.
- `n8n-nodes-base.httpRequest` — requires one only when `parameters.authentication` is set to a
  credential-bearing mode (`genericCredentialType` / `predefinedCredentialType`); the repo's
  secret-free Bearer-only nodes (e.g. `ZoomInfo Usage`, which uses a token minted upstream) must
  keep deploying unbound, as they do today.
- `n8n-nodes-base.webhook` — requires one only when `parameters.authentication` is set (the Cloud
  webhook's native Header Auth gate).

The raised error must name the offending node, its type, and its workflow, and say to add it to
`NODE_CREDENTIAL_MAP` — matching the tone and usefulness of the existing `ValueError`.

**Acceptance:**
- With the Task 1 additions in place, `bind_credentials()` succeeds on all three built workflows.
- Removing any one HubSpot node from the map makes `bind_credentials()` raise for that node
  (prove it in-test with a modified copy of the map — do NOT mutate the real one).
- A Code/IF/Set node, and a secret-free `httpRequest` node with no `authentication` parameter, both
  still pass through with no `credentials` block and no raise.

### Task 3 — regression test

New `tests/test_deploy_credential_binding.py` covering:
1. The zero-unmapped sweep across every `n8n/wf_*.json` (this is the guard that generalizes
   16.4-02's enrichment-only version to all workflows).
2. Fail-closed on an unmapped HubSpot node.
3. Pass-through for non-credential node types.
4. The pre-existing fail-closed behaviour for a mapped-but-unresolvable credential name still works.

**Acceptance:** full suite green, zero regressions vs the 363 pytest / 258 node baseline.

## Scope fence

- `scripts/deploy_n8n_workflows.py` and the new test file ONLY.
- NO workflow JSON regeneration — this touches no builder input, so `git status n8n/` must stay clean.
- NO live n8n calls, no deploy, no activation. `bind_credentials()` is a pure function; test it as one.
- NO credential VALUE handling — this is name→id binding only; no secret is read, printed, or committed.
- NO change to provisioning (`provision_n8n_credentials.py`) — the 6 credential objects it creates
  already cover all 10 nodes (they all reuse `LV HubSpot`).

## Verify

```bash
.venv/bin/python -m pytest -q
node --test tests/n8n/*.test.mjs
git status --short n8n/    # must be empty
```
