#!/usr/bin/env python3
"""scripts/deploy_n8n_workflows.py

Phase 16 Task 1 — deploy the built `n8n/wf_*.json` workflows to n8n Cloud via the
Public API.

Same idiom as scripts/sync_hubspot_properties.py: env-gated, dry-run-by-default,
`_has_n8n()` skip-to-exit-0, a two-key write gate (DRY_RUN=false AND
ALLOW_N8N_DEPLOY=true), idempotent diff re-derived from a fresh GET every run (never
local state).

Usage:
    python scripts/deploy_n8n_workflows.py          # dry-run diff (default, zero writes)
    DRY_RUN=false ALLOW_N8N_DEPLOY=true \
        python scripts/deploy_n8n_workflows.py       # live create/update

CREDENTIAL BINDING (review consensus #1): the built Cloud workflow JSONs carry zero
`credentials` blocks, so importing them unchanged would leave every node unbound. Before
POST/PUT, `bind_credentials()` attaches a per-node top-level `credentials` object,
resolved from a static node-name -> credential-name map (NODE_CREDENTIAL_MAP, below) and
the credential name->id map `provision_n8n_credentials.py` writes to
`.n8n_credential_ids.json` (gitignored). A node whose mapped credential name has no
resolvable id fails the deploy closed rather than importing an unbound node.

Activation (POST .../activate) is a separate operator-runbook step, not performed here —
n8n creates new workflows inactive by default.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

N8N_DIR = ROOT / "n8n"
CRED_ID_MAP_PATH = ROOT / ".n8n_credential_ids.json"

# node name -> {cred_type: <n8n credential type key used in the node's top-level
# "credentials" block>, cred_name: <name provision_n8n_credentials.py provisions it under>}.
# Lusha/Apollo/Anthropic all share the httpHeaderAuth generic credential TYPE but are three
# DIFFERENT credential objects — disambiguated here by node name, not by type (review #1).
NODE_CREDENTIAL_MAP = {
    "HubSpot Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Create": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Update": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Company Search": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Company Create": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "HubSpot Company Update": {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"},
    "Lusha Enrich": {"cred_type": "httpHeaderAuth", "cred_name": "LV Lusha"},
    "Lusha Company": {"cred_type": "httpHeaderAuth", "cred_name": "LV Lusha"},
    "Apollo Match": {"cred_type": "httpHeaderAuth", "cred_name": "LV Apollo"},
    "Apollo Org": {"cred_type": "httpHeaderAuth", "cred_name": "LV Apollo"},
    "Claude Web Research": {"cred_type": "httpHeaderAuth", "cred_name": "LV Anthropic"},
    "Judge Call": {"cred_type": "httpHeaderAuth", "cred_name": "LV Anthropic"},
    # ZoomInfo (Task 2 decision: split-code-node) — the Mint HTTP node is the ONLY node
    # that ever touches client_id/client_secret, via this generic Basic Auth credential.
    # The Token Gate/Cache Token/Enrich Code nodes are secret-free and need no binding.
    "ZoomInfo Mint": {"cred_type": "httpBasicAuth", "cred_name": "LV ZoomInfo"},
    "ZoomInfo Mint Company": {"cred_type": "httpBasicAuth", "cred_name": "LV ZoomInfo"},
}


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _instance_ok() -> bool:
    """Wrong-instance guard (review consensus #4) — must NOT fail open. If
    N8N_EXPECTED_URL is set, N8N_URL must equal it exactly. If unset, refuse unless
    N8N_URL's host genuinely ends with `.n8n.cloud` — an unset/unrecognized URL refuses,
    it never defaults to "ok"."""
    url = os.getenv("N8N_URL", "")
    expected = os.getenv("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_N8N_DEPLOY", "false").lower() == "true"
    return (not dry_run) and allow


def _base_url() -> str:
    return os.getenv("N8N_URL", "").rstrip("/")


def _n8n_headers() -> dict:
    return {"X-N8N-API-KEY": os.getenv("N8N_API_KEY", ""), "Content-Type": "application/json"}


def _load_local_workflows() -> list:
    return [json.loads(p.read_text()) for p in sorted(N8N_DIR.glob("wf_*.json"))]


def _get_live_workflows() -> list:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/workflows", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def _load_credential_id_map(path: Path = CRED_ID_MAP_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def compute_workflow_diff(local_workflows: list, live_workflows: list) -> dict:
    """Match on the workflow's top-level `name` — n8n assigns `id` server-side, so
    matching on the local JSON's internal id would never find an existing live workflow.
    Re-derive from a FRESH `live_workflows` (a fresh GET) every call, never from local
    state, so a re-run after a mid-batch failure picks up exactly where it left off."""
    live_by_name = {w["name"]: w for w in live_workflows}
    create, update = [], []
    for wf in local_workflows:
        live = live_by_name.get(wf["name"])
        if live is None:
            create.append(wf)
        else:
            update.append({"id": live["id"], "body": wf})
    return {"create": create, "update": update}


def bind_credentials(workflow: dict, name_to_id: dict, node_cred_map: dict = None) -> dict:
    """Pure function. Returns a NEW workflow dict with each mapped node's top-level
    `credentials` block attached. Fails closed: raises ValueError if a mapped node's
    credential name has no resolvable id in `name_to_id` — never emits an unbound node."""
    node_cred_map = NODE_CREDENTIAL_MAP if node_cred_map is None else node_cred_map
    wf = json.loads(json.dumps(workflow))  # deep copy, stdlib only
    for node in wf.get("nodes", []):
        mapping = node_cred_map.get(node.get("name"))
        if mapping is None:
            continue
        cred_name = mapping["cred_name"]
        cred_id = name_to_id.get(cred_name)
        if cred_id is None:
            raise ValueError(
                f"cannot deploy {wf.get('name')!r}: node {node['name']!r} needs credential "
                f"{cred_name!r}, which is not in the provisioned name->id map "
                f"({CRED_ID_MAP_PATH.name}). Run provision_n8n_credentials.py first."
            )
        node["credentials"] = {mapping["cred_type"]: {"id": cred_id, "name": cred_name}}
    return wf


def _create_workflow_live(body: dict):
    import requests
    payload = {k: v for k, v in body.items() if k in ("name", "nodes", "connections", "settings")}
    r = requests.post(f"{_base_url()}/api/v1/workflows", headers=_n8n_headers(), json=payload, timeout=30)
    return r.status_code, r


def _update_workflow_live(workflow_id: str, body: dict):
    import requests
    payload = {k: v for k, v in body.items() if k in ("name", "nodes", "connections", "settings")}
    r = requests.put(f"{_base_url()}/api/v1/workflows/{workflow_id}", headers=_n8n_headers(),
                      json=payload, timeout=30)
    return r.status_code, r


def main(argv=None) -> int:
    if not _has_n8n():
        print("skipped (no n8n creds): N8N_URL and N8N_API_KEY must both be set to run this deploy.")
        return 0

    if not _instance_ok():
        print("REFUSED: N8N_URL does not match the expected instance. Set N8N_EXPECTED_URL to pin "
              "it, or use a genuine *.n8n.cloud host. No API call made.")
        return 1

    local_workflows = _load_local_workflows()
    live_workflows = _get_live_workflows()
    diff = compute_workflow_diff(local_workflows, live_workflows)

    print(f"Workflows to create: {[w['name'] for w in diff['create']]}")
    print(f"Workflows to update: {[u['body']['name'] for u in diff['update']]}")

    if not _writes_allowed():
        print("DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_N8N_DEPLOY=true to deploy.")
        return 0

    name_to_id = _load_credential_id_map()
    failures = []

    for wf in diff["create"]:
        try:
            bound = bind_credentials(wf, name_to_id)
        except ValueError as exc:
            failures.append(("create", wf["name"], str(exc)))
            continue
        status, _ = _create_workflow_live(bound)
        if status in (200, 201):
            print(f"created workflow {wf['name']} ({status})")
        else:
            failures.append(("create", wf["name"], status))
            print(f"FAILED to create workflow {wf['name']} ({status})")

    for u in diff["update"]:
        name = u["body"]["name"]
        try:
            bound = bind_credentials(u["body"], name_to_id)
        except ValueError as exc:
            failures.append(("update", name, str(exc)))
            continue
        status, _ = _update_workflow_live(u["id"], bound)
        if status == 200:
            print(f"updated workflow {name} ({status})")
        else:
            failures.append(("update", name, status))
            print(f"FAILED to update workflow {name} ({status})")

    # Activation is a deliberate separate operator-runbook step — not performed here.
    if failures:
        print(f"\nPARTIAL FAILURE — {len(failures)} item(s) not deployed:")
        for kind, name, detail in failures:
            print(f"  {kind} {name}: {detail}")
        print("Re-run after fixing; a re-run re-diffs against a fresh GET so it is idempotent.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
