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

@pytest.mark.parametrize("name,resource", [("HubSpot Create", "contacts"),
                                           ("HubSpot Company Create", "companies")])
def test_create_nodes_post_the_computed_patch(name, resource):
    """BUG 13, found 2026-07-29 while auditing the write lane before exercising creates
    live. This test previously pinned both create nodes as NATIVE and deliberately
    unverified — 16.7-01 left them alone because ALLOW_HUBSPOT_CREATE stayed false for that
    whole phase. The audit found they were broken two ways at once, either of which alone
    would have made a create canary meaningless:

      1. `additionalFields: {}` — the same empty-map placeholder as BUG 11, so the computed
         patch on $json.properties was discarded and a create would have produced a record
         carrying only its identifier.
      2. They read fields absent from their own input. Decide Action / Decide Company Action
         emit exactly {action, object_type, hs_object_id, gap_flag, needs_review, properties}
         (verified from live execution 12's runData), yet HubSpot Company Create read
         `$json.name || $json.identity_keys.companyName || $json.identity_keys.domain` and
         HubSpot Create read `$json.properties.email` — which is never present, because
         email is manual_protected and can never promote into the patch.

    Both now POST {"properties": $json.properties} to the CRM v3 collection endpoint."""
    doc = _load()
    node = _node(doc, name)
    params = node["parameters"]
    assert node["type"] == "n8n-nodes-base.httpRequest", "must not regress to the native node"
    assert params["method"] == "POST"
    assert params["url"] == f"https://api.hubapi.com/crm/v3/objects/{resource}"
    assert params["authentication"] == "predefinedCredentialType"
    assert params["nodeCredentialType"] == "hubspotAppToken"
    assert params["jsonBody"] == "={{ JSON.stringify({ properties: $json.properties }) }}"
    # The two expressions that could never have resolved must be gone for good.
    assert "identity_keys" not in params["jsonBody"]
    assert "properties.email" not in params["jsonBody"]
    assert node.get("onError") is None, "a rejected create must fail its execution loudly"
