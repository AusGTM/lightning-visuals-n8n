# tests/test_write_node_transport.py
#
# BUG 11 (found reading the built artifact, 2026-07-29, Phase 16.7-01): the deployed
# "HubSpot Update" / "HubSpot Company Update" nodes were native `n8n-nodes-base.hubspot`
# nodes with an EMPTY `updateFields` map — a well-formed node that references
# `$json.properties` nowhere. A canary fired against them would issue a property-less
# update: no field ever reaches HubSpot, and a non-clobber proof against an empty write is
# vacuous. This is the same class of defect as BUG 10 (a node config that passes the whole
# offline suite and deploys clean, wrong only against the real API) — see
# tests/test_bug10_company_search_transport.py for that precedent's structural guard,
# which this file mirrors.
#
# Structural guard on both update nodes: httpRequest transport, PATCH method, an
# expression URL carrying hs_object_id and the correct CRM v3 object path, a body
# expression referencing `properties`, credential-bound via predefinedCredentialType/
# hubspotAppToken (reusing "LV HubSpot" — never a new credential, never $env/$vars), and
# NO `onError` key at all (a WRITE node must fail its execution on a rejected PATCH, never
# swallow it via continueRegularOutput — see _hs_http_patch_node's docstring in
# scripts/build_cloud_workflows.py). A companion guard pins both CREATE nodes as still
# native and explicitly UNVERIFIED live — this fix does not touch them.
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"

# name -> expected CRM v3 object-type path segment
UPDATE_NODES = {
    "HubSpot Update": "contacts",
    "HubSpot Company Update": "companies",
}
CREATE_NODES = {
    "HubSpot Create": ("contact", "create"),
    "HubSpot Company Create": ("company", "create"),
}


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


# --- the two update nodes: credential-bound httpRequest PATCH, fails hard --------------

@pytest.mark.parametrize("name,resource", list(UPDATE_NODES.items()))
def test_update_node_is_credential_bound_httprequest_patch(name, resource):
    doc = _load()
    node = _node(doc, name)
    assert node["type"] == "n8n-nodes-base.httpRequest", (
        f"{name}: expected httpRequest transport (BUG 11 fix), got {node.get('type')!r}"
    )
    params = node["parameters"]
    assert params.get("method") == "PATCH", f"{name}: expected PATCH method"
    url = params.get("url", "")
    assert isinstance(url, str) and url.startswith("="), f"{name}: url must be an n8n expression"
    assert "hs_object_id" in url, f"{name}: url must carry hs_object_id"
    assert f"/crm/v3/objects/{resource}/" in url, (
        f"{name}: url must target the CRM v3 {resource} object path, got {url!r}"
    )
    body = params.get("jsonBody", "")
    assert isinstance(body, str) and "properties" in body, (
        f"{name}: request body must reference the computed properties patch"
    )
    assert params.get("authentication") == "predefinedCredentialType", (
        f"{name}: authentication must be predefinedCredentialType so "
        "_node_requires_credential() treats this node as credential-bearing"
    )
    assert params.get("nodeCredentialType") == "hubspotAppToken", (
        f"{name}: nodeCredentialType must be hubspotAppToken to reuse the LV HubSpot "
        "credential deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP already binds by this name"
    )
    # No leftover field-map parameter from the native shape.
    assert "updateFields" not in params, f"{name}: must not carry a leftover native updateFields param"
    assert "contactId" not in params and "companyId" not in params, (
        f"{name}: must not carry a leftover native id parameter — the id travels in the URL now"
    )


@pytest.mark.parametrize("name", list(UPDATE_NODES))
def test_update_node_deliberately_has_no_on_error_key(name):
    """A rejected PATCH must fail the execution, not flow on to Build Response as a
    healthy item — `continueRegularOutput` (which every OTHER httpRequest node in this
    builder carries) would reproduce exactly the swallowed-failure mechanism that hid ten
    live-only bugs offline."""
    doc = _load()
    node = _node(doc, name)
    assert "onError" not in node, (
        f"{name}: must NOT carry an onError key — a WRITE node's rejected PATCH must "
        "fail the execution, never be swallowed as a healthy item"
    )


@pytest.mark.parametrize("name", list(UPDATE_NODES))
def test_update_node_body_carries_exactly_one_properties_key(name):
    doc = _load()
    node = _node(doc, name)
    body = node["parameters"]["jsonBody"]
    assert body == "={{ JSON.stringify({ properties: $json.properties }) }}", (
        f"{name}: jsonBody must be exactly the single-key properties patch expression, got {body!r}"
    )


# --- both nodes stay resolvable in NODE_CREDENTIAL_MAP (name preserved) ----------------

def test_both_update_node_names_are_present_in_node_credential_map():
    import scripts.deploy_n8n_workflows as deploy
    for name in UPDATE_NODES:
        assert name in deploy.NODE_CREDENTIAL_MAP, (
            f"{name}: node name must stay in NODE_CREDENTIAL_MAP so credential binding "
            "by name keeps working unchanged after the transport swap"
        )
        assert deploy.NODE_CREDENTIAL_MAP[name] == {
            "cred_type": "hubspotAppToken", "cred_name": "LV HubSpot",
        }


# --- creates: untouched, native, explicitly pinned as live-unverified ------------------

@pytest.mark.parametrize("name,expected", list(CREATE_NODES.items()))
def test_create_nodes_are_still_native_and_unchanged_by_this_fix(name, expected):
    """company:create / contacts create are NOT touched by this plan (ALLOW_HUBSPOT_CREATE
    stays "false" for the whole phase, per 16.7-CONTEXT.md Locked Decision 2). Their live
    defect status remains UNKNOWN — this pin exists so a future change cannot silently
    imply they were fixed too, the same spirit as BUG 10's UNCHANGED_WRITE_NODES pin in
    tests/test_bug10_company_search_transport.py."""
    resource, operation = expected
    doc = _load()
    node = _node(doc, name)
    assert node["type"] == "n8n-nodes-base.hubspot"
    assert node["parameters"]["resource"] == resource
    assert node["parameters"]["operation"] == operation
