# tests/test_deploy_credential_binding.py
#
# Quick task 2026-07-28 — pre-activation blocker regression guard.
#
# bind_credentials()'s `mapping is None: continue` deployed any node absent from
# NODE_CREDENTIAL_MAP unbound with no error — 401-ing only at runtime. 10 hubspot nodes
# (1 in wf_contact_ingest_cloud.json, 9 in wf_scheduled_maintenance_cloud.json) were in
# this state; Phase 16.4-02's credential guard was scoped to wf_enrichment_cloud.json
# only, which is exactly why they stayed invisible. This file generalizes that guard to
# every built workflow and proves the new fail-closed-by-node-type behavior.
#
# Pure-function tests only: bind_credentials() makes no network call, so this file needs
# no hermetic requests monkeypatch (unlike tests/test_deploy_n8n_workflows.py's main()
# tests).
import copy
import json
import re
from pathlib import Path

import pytest

import scripts.deploy_n8n_workflows as deploy

ROOT = Path(__file__).resolve().parents[1]

FAKE_ID_MAP = {
    "LV Lusha": "id-lusha", "LV Apollo": "id-apollo", "LV ZoomInfo": "id-zoominfo",
    "LV HubSpot": "id-hubspot", "LV Anthropic": "id-anthropic",
    "LV Enrichment Webhook": "id-webhook-secret",
}


def _load_built_cloud_workflows() -> list:
    return [json.loads(p.read_text()) for p in sorted((ROOT / "n8n").glob("wf_*_cloud.json"))]


# --- 1. zero-unmapped sweep across every n8n/wf_*.json --------------------------------

def test_zero_hubspot_nodes_unmapped_across_every_built_cloud_workflow():
    """Generalizes 16.4-02's enrichment-only credential guard to all built workflows.

    Uses deploy._node_requires_credential() itself rather than a hand-filtered
    type=="n8n-nodes-base.hubspot" check, so this sweep automatically covers any
    credential-bearing node regardless of transport — including the 6 BUG 10 / Phase 16.6
    company-search nodes now on httpRequest+predefinedCredentialType, which a
    type-filtered sweep would silently stop seeing the moment their transport changed."""
    unmapped = []
    for wf in _load_built_cloud_workflows():
        for node in wf.get("nodes", []):
            if not deploy._node_requires_credential(node):
                continue
            if node.get("name") not in deploy.NODE_CREDENTIAL_MAP:
                unmapped.append((wf.get("name"), node.get("name")))
    assert unmapped == [], f"unmapped credential-requiring nodes (would deploy unbound): {unmapped}"


def test_bind_credentials_succeeds_on_every_built_cloud_workflow():
    for wf in _load_built_cloud_workflows():
        bound = deploy.bind_credentials(wf, FAKE_ID_MAP)
        hubspot_nodes = [n for n in bound["nodes"] if n.get("type") == "n8n-nodes-base.hubspot"]
        assert hubspot_nodes, f"{wf['name']} has no hubspot nodes — fixture drifted?"
        for node in hubspot_nodes:
            assert "credentials" in node, f"{wf['name']}: {node['name']!r} was not bound"


# --- 2. fail-closed on an unmapped HubSpot node ----------------------------------------

def test_fail_closed_when_a_mapped_hubspot_node_is_removed_from_a_copied_map():
    """Prove the fail-closed path with a MODIFIED COPY of the map — never mutate the
    real NODE_CREDENTIAL_MAP."""
    partial_map = copy.deepcopy(deploy.NODE_CREDENTIAL_MAP)
    del partial_map["HubSpot Search by Email"]

    wf = json.loads((ROOT / "n8n" / "wf_contact_ingest_cloud.json").read_text())
    with pytest.raises(ValueError, match="HubSpot Search by Email"):
        deploy.bind_credentials(wf, FAKE_ID_MAP, node_cred_map=partial_map)

    # The real map is untouched by the copy.
    assert "HubSpot Search by Email" in deploy.NODE_CREDENTIAL_MAP


def test_fail_closed_error_names_node_type_and_workflow():
    workflow = {"name": "My Workflow", "nodes": [
        {"name": "Some New HubSpot Node", "type": "n8n-nodes-base.hubspot"},
    ]}
    with pytest.raises(ValueError) as excinfo:
        deploy.bind_credentials(workflow, FAKE_ID_MAP, node_cred_map={})
    msg = str(excinfo.value)
    assert "My Workflow" in msg
    assert "Some New HubSpot Node" in msg
    assert "n8n-nodes-base.hubspot" in msg
    assert "NODE_CREDENTIAL_MAP" in msg


def test_fail_closed_on_unmapped_httprequest_node_with_credential_bearing_auth():
    workflow = {"name": "wf", "nodes": [
        {"name": "New Provider Call", "type": "n8n-nodes-base.httpRequest",
         "parameters": {"authentication": "genericCredentialType"}},
    ]}
    with pytest.raises(ValueError, match="New Provider Call"):
        deploy.bind_credentials(workflow, FAKE_ID_MAP, node_cred_map={})


def test_fail_closed_on_unmapped_webhook_node_with_authentication_set():
    workflow = {"name": "wf", "nodes": [
        {"name": "New Webhook", "type": "n8n-nodes-base.webhook",
         "parameters": {"authentication": "headerAuth"}},
    ]}
    with pytest.raises(ValueError, match="New Webhook"):
        deploy.bind_credentials(workflow, FAKE_ID_MAP, node_cred_map={})


# --- 3. pass-through for non-credential node types -------------------------------------

def test_code_if_set_nodes_pass_through_unmapped_with_no_raise_and_no_credentials():
    workflow = {"name": "wf", "nodes": [
        {"name": "A Code Node", "type": "n8n-nodes-base.code"},
        {"name": "An IF Node", "type": "n8n-nodes-base.if"},
        {"name": "A Set Node", "type": "n8n-nodes-base.set"},
        {"name": "A NoOp Node", "type": "n8n-nodes-base.noOp"},
        {"name": "A Merge Node", "type": "n8n-nodes-base.merge"},
        {"name": "A Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger"},
    ]}
    bound = deploy.bind_credentials(workflow, name_to_id={}, node_cred_map={})
    for node in bound["nodes"]:
        assert "credentials" not in node, node["name"]


def test_secret_free_httprequest_node_with_no_authentication_param_passes_through():
    """The repo's secret-free Bearer-only nodes (e.g. ZoomInfo Usage, which uses a token
    minted upstream by the credential-bound ZoomInfo Mint node) must keep deploying
    unbound — this is a deliberate Phase 16-01 split-code-node architecture decision."""
    workflow = {"name": "wf", "nodes": [
        {"name": "Verify Emails (batch)", "type": "n8n-nodes-base.httpRequest", "parameters": {}},
    ]}
    bound = deploy.bind_credentials(workflow, name_to_id={}, node_cred_map={})
    assert "credentials" not in bound["nodes"][0]


def test_zoominfo_usage_code_node_is_untouched_by_the_guard():
    workflow = {"name": "wf", "nodes": [
        {"name": "ZoomInfo Usage", "type": "n8n-nodes-base.code"},
        {"name": "ZoomInfo Enrich", "type": "n8n-nodes-base.code"},
        {"name": "ZoomInfo Company", "type": "n8n-nodes-base.code"},
    ]}
    bound = deploy.bind_credentials(workflow, name_to_id={}, node_cred_map={})
    for node in bound["nodes"]:
        assert "credentials" not in node, node["name"]


def test_webhook_node_with_no_authentication_or_none_passes_through():
    workflow = {"name": "wf", "nodes": [
        {"name": "Unmapped Webhook A", "type": "n8n-nodes-base.webhook", "parameters": {}},
        {"name": "Unmapped Webhook B", "type": "n8n-nodes-base.webhook",
         "parameters": {"authentication": "none"}},
    ]}
    bound = deploy.bind_credentials(workflow, name_to_id={}, node_cred_map={})
    for node in bound["nodes"]:
        assert "credentials" not in node, node["name"]


# --- 4. pre-existing fail-closed behavior for a mapped-but-unresolvable credential -----

def test_mapped_node_with_unresolvable_credential_name_still_fails_closed():
    workflow = {"name": "wf", "nodes": [
        {"name": "Lusha Enrich", "type": "n8n-nodes-base.httpRequest"},
    ]}
    with pytest.raises(ValueError, match="LV Lusha"):
        deploy.bind_credentials(workflow, name_to_id={})  # default map: Lusha Enrich IS mapped


# --- built-workflow proof: prove fail-closed cannot be tripped by removing entries from
# a COPY of the real map, never the real map itself ------------------------------------

@pytest.mark.parametrize("node_name", [
    "HubSpot Search by Email",
    "SJ-3 Search (requested poller)",
    "SJ-1 Search (input-gap scan)",
    "SJ-1 Set Requested",
    "SJ-2 Search (stale refresh)",
    "SJ-2 Set Requested",
    "Dedupe Search (candidate contacts)",
    "Dedupe Set Needs Review",
    "Review Search (approved=true)",
    "Review Apply Update",
])
def test_each_of_the_10_bound_nodes_fails_closed_if_removed_from_a_copied_map(node_name):
    partial_map = copy.deepcopy(deploy.NODE_CREDENTIAL_MAP)
    del partial_map[node_name]

    for wf in _load_built_cloud_workflows():
        node_names = {n["name"] for n in wf.get("nodes", [])}
        if node_name not in node_names:
            continue
        with pytest.raises(ValueError, match=re.escape(node_name)):
            deploy.bind_credentials(wf, FAKE_ID_MAP, node_cred_map=partial_map)
        break
    else:
        pytest.fail(f"{node_name!r} not found in any built cloud workflow")

    # The real map is untouched by the copy-and-delete.
    assert node_name in deploy.NODE_CREDENTIAL_MAP
