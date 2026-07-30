# tests/test_backend_status_wiring.py
#
# Phase 27 Plan 01 — structural proof for the four HubSpot count searches added to
# `hubspot/backend-status` (n8n/wf_backend_status_cloud.json): every new search node is
# credential-bound (NODE_CREDENTIAL_MAP), every property it filters on actually exists in
# this portal's declared schema (derived from config/hubspot_properties.yaml at test
# time, not a hardcoded list — a property that does not exist cannot be introduced
# without this failing), every new filter body requests `limit: 1` (a badge count never
# needs row payloads), and the endpoint's chain contains no write node (this phase is
# strictly read-only, T-27-05).
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "n8n" / "wf_backend_status_cloud.json"
PROPERTIES_YAML = ROOT / "config" / "hubspot_properties.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from deploy_n8n_workflows import NODE_CREDENTIAL_MAP  # noqa: E402

NEW_SEARCH_NODES = {
    "HS Requested Search (Companies)": "companies",
    "HS Review Search (Companies)": "companies",
    "HS Requested Search (Contacts)": "contacts",
    "HS Review Search (Contacts)": "contacts",
}

# HubSpot's httpRequest search body is baked as a single n8n expression string
# (`={{ JSON.stringify({...}) }}`) — see _hs_search_json_body_expr — so this regex reads
# the property names back out of the rendered JS object literal rather than parsing JSON.
_PROPERTY_NAME_RE = re.compile(r'propertyName:\s*"([^"]+)"')
_LIMIT_RE = re.compile(r"\blimit:\s*(\d+)\b")


def _load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text())


def _declared_properties() -> dict:
    """object_type -> set of every property name declared in the portal's schema."""
    schema = yaml.safe_load(PROPERTIES_YAML.read_text())
    return {
        obj_type: {p["name"] for p in obj["properties"]}
        for obj_type, obj in schema.items()
    }


def _node(doc: dict, name: str) -> dict:
    return next(n for n in doc["nodes"] if n["name"] == name)


def _search_json_body(node: dict) -> str:
    return node["parameters"]["jsonBody"]


# --- non-vacuity guard ------------------------------------------------------------------

def test_all_four_new_search_nodes_exist():
    doc = _load_workflow()
    names = {n["name"] for n in doc["nodes"]}
    found = [name for name in NEW_SEARCH_NODES if name in names]
    assert len(found) == 4, f"expected 4 new search nodes, found {len(found)}: {found}"


# --- credential binding -------------------------------------------------------------------

@pytest.mark.parametrize("node_name", sorted(NEW_SEARCH_NODES))
def test_new_search_node_is_credential_bound(node_name):
    """A credential-bearing node absent from NODE_CREDENTIAL_MAP deploys UNBOUND (HTTP
    200) and only fails at activation — the failure class this repo has been bitten by
    three times before (deploy_n8n_workflows.py's own docstring)."""
    assert node_name in NODE_CREDENTIAL_MAP, (
        f"{node_name!r} is missing from NODE_CREDENTIAL_MAP — it deploys unbound"
    )
    mapping = NODE_CREDENTIAL_MAP[node_name]
    assert mapping["cred_type"] == "hubspotAppToken"
    assert mapping["cred_name"] == "LV HubSpot"


# --- schema-derived property guard ---------------------------------------------------------

@pytest.mark.parametrize("node_name,object_type", sorted(NEW_SEARCH_NODES.items()))
def test_new_search_node_filters_only_on_declared_properties(node_name, object_type):
    """Every propertyName in this node's filter body must be declared for that object
    type in config/hubspot_properties.yaml — derived at test time, never a hardcoded
    allowlist, so an undeclared property (D-07a's exact defect class) fails here instead
    of 400ing live."""
    declared = _declared_properties()
    doc = _load_workflow()
    node = _node(doc, node_name)
    body = _search_json_body(node)
    property_names = _PROPERTY_NAME_RE.findall(body)
    assert property_names, f"{node_name}: no propertyName found in filter body — regex or node shape drifted"
    for prop in property_names:
        assert prop in declared[object_type], (
            f"{node_name} filters on {prop!r}, which is not declared for {object_type!r} "
            f"in config/hubspot_properties.yaml"
        )


# --- limit: 1 (badge count only, never pull row payloads) ----------------------------------

@pytest.mark.parametrize("node_name", sorted(NEW_SEARCH_NODES))
def test_new_search_node_requests_limit_one(node_name):
    doc = _load_workflow()
    node = _node(doc, node_name)
    body = _search_json_body(node)
    m = _LIMIT_RE.search(body)
    assert m, f"{node_name}: no limit found in filter body"
    assert m.group(1) == "1", f"{node_name}: expected limit: 1, got {m.group(1)}"


# --- OR'd filter groups: requested-unresolved must not be a single AND-only NEQ group ------

@pytest.mark.parametrize(
    "node_name", ["HS Requested Search (Companies)", "HS Requested Search (Contacts)"]
)
def test_requested_unresolved_uses_ord_groups_not_a_single_neq_group(node_name):
    """HubSpot's NEQ operator does not match a record whose property is absent — a
    single group of NEQ predicates would silently under-count to zero exactly the
    population this phase exists to surface (plan note / Pitfall 2)."""
    doc = _load_workflow()
    node = _node(doc, node_name)
    body = _search_json_body(node)
    assert body.count("filterGroups:") == 1
    # Two OR'd groups: the property-absent case and the has-a-value-but-not-terminal case.
    assert body.count("filters: [") >= 2, f"{node_name}: expected at least 2 OR'd filter groups"
    assert "NOT_HAS_PROPERTY" in body, (
        f"{node_name}: must cover the property-absent case (NEQ alone under-counts)"
    )


@pytest.mark.parametrize(
    "node_name", ["HS Review Search (Companies)", "HS Review Search (Contacts)"]
)
def test_awaiting_review_ors_the_two_independent_reasons(node_name):
    doc = _load_workflow()
    node = _node(doc, node_name)
    body = _search_json_body(node)
    assert "lv_enrichment_needs_review" in body
    assert "lv_icp_needs_review" in body
    assert body.count("filters: [") >= 2, f"{node_name}: expected 2 OR'd single-filter groups"


# --- no write node anywhere in this endpoint's chain ----------------------------------------

WRITE_NODE_TYPES = {"n8n-nodes-base.hubspot"}


def test_endpoint_chain_contains_no_write_node():
    """This phase is strictly read-only (T-27-05) — no PATCH, no create, no property
    set. httpRequest search nodes are fine (they read); a native hubspot node performing
    update/create, or an httpRequest node using PATCH/POST against a HubSpot write
    endpoint, would not be."""
    doc = _load_workflow()
    for node in doc["nodes"]:
        assert node.get("type") not in WRITE_NODE_TYPES, (
            f"{node['name']}: native HubSpot node type is not permitted in a read-only endpoint"
        )
        if node.get("type") == "n8n-nodes-base.httpRequest":
            method = node.get("parameters", {}).get("method", "POST")
            url = node.get("parameters", {}).get("url", "")
            if "hubapi.com" in url and "/search" not in url:
                assert method not in ("PATCH", "PUT"), (
                    f"{node['name']}: HubSpot write method {method!r} in a read-only endpoint"
                )
