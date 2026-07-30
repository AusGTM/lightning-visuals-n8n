# tests/test_enrichment_contacts_search_transport.py
#
# BUG 23 (root-caused 2026-07-29, generalizing execution 22's live-established mechanism
# — BUG 22, the ingest lane — to the enrichment contacts lane; not yet reproduced live
# there, see .planning/debug/bug-23-enrichment-contact-nomatch-chain-stop.md). Execution 22
# proved the native `n8n-nodes-base.hubspot` `contact:search` node emits ZERO items on
# zero hits, and n8n stops the chain there. `contact:search` genuinely EXISTS and genuinely
# returns the record on a hit (unlike BUG 10's `company:search`, which does not exist at
# all) — which is why every enrichment contacts execution ever run (8-15, 19, all against
# an existing record) passed. On a no-match it is fatal: an event for an email with no
# HubSpot record dies at "HubSpot Search" (Enrichment Gate never runs, `action: "create"`
# is structurally unreachable), and a bare event for a deleted/nonexistent object id dies
# at "HubSpot Fetch By Id" (adaptFetchById.js's 0-result / lookup_failed branch is dead
# code for the exact case it exists for).
#
# This file is what REACH-02's pin removal (tests/test_bug10_company_search_transport.py,
# CONTACT_NODES_BY_WORKFLOW) hands the pinning duty to: both nodes moved off the native
# node onto the SAME credential-bound httpRequest envelope transport BUG 10/22 already
# proved correct, so this is REACH-01's offline shape guard for that swap.
#
# RED-before-green: every assertion below failed against the pre-swap committed workflow
# JSON (both nodes were n8n-nodes-base.hubspot, typeVersion 2.1, operation:"search") — see
# the captured red-run output quoted in 17-01-SUMMARY.md / this task's commit message.
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import (  # noqa: E402
    ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
    ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
)

import scripts.deploy_n8n_workflows as deploy  # noqa: E402

N8N_DIR = ROOT / "n8n"
WORKFLOW = "wf_enrichment_cloud.json"
SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"

NODES = {
    "HubSpot Search": {
        "properties_csv": ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
        "filter_tokens": [
            'propertyName: "email"', 'operator: "EQ"', "$json.identity_keys.email",
        ],
    },
    "HubSpot Fetch By Id": {
        "properties_csv": ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
        "filter_tokens": [
            'propertyName: "hs_object_id"', 'operator: "EQ"',
            "$('Build Identity').item.json.object_id",
        ],
    },
}


def _load() -> dict:
    return json.loads((N8N_DIR / WORKFLOW).read_text())


def _node(doc: dict, name: str) -> dict:
    return next(n for n in doc["nodes"] if n["name"] == name)


def _extract_json_body_properties(json_body: str) -> list:
    m = re.search(r"properties:\s*(\[[^\]]*\])", json_body)
    assert m, f"no `properties: [...]` array found in jsonBody: {json_body!r}"
    return json.loads(m.group(1))


def _csv_to_list(csv: str) -> list:
    return [p.strip() for p in csv.split(",") if p.strip()]


# --- vacuity guard ----------------------------------------------------------------------

def test_workflow_carries_both_target_nodes():
    doc = _load()
    for name in NODES:
        assert any(n["name"] == name for n in doc["nodes"]), (
            f"{name!r} not found in {WORKFLOW} — fixture/build drifted"
        )


# --- transport shape: credential-bound httpRequest, predefinedCredentialType -----------

@pytest.mark.parametrize("name", list(NODES))
def test_node_is_credential_bound_httprequest_via_hubspot_apptoken(name):
    doc = _load()
    node = _node(doc, name)
    assert node["type"] == "n8n-nodes-base.httpRequest", (
        f"{name}: expected httpRequest transport, got {node.get('type')!r}"
    )
    assert node["typeVersion"] == 4.2
    assert node.get("onError") == "continueRegularOutput", (
        f"{name}: must keep the fail-closed onError the native node carried"
    )
    params = node["parameters"]
    assert params.get("method") == "POST"
    assert params.get("url") == SEARCH_URL, (
        f"{name}: wrong URL {params.get('url')!r} — a copy-paste of the companies URL "
        "would search the wrong object type and is exactly the mistake this asserts against"
    )
    assert params.get("authentication") == "predefinedCredentialType", (
        f"{name}: authentication must be predefinedCredentialType so "
        "_node_requires_credential() treats this node as credential-bearing "
        "(deploy_n8n_workflows.py's _CREDENTIAL_BEARING_HTTP_AUTH_MODES)"
    )
    assert params.get("nodeCredentialType") == "hubspotAppToken", (
        f"{name}: nodeCredentialType must be hubspotAppToken to reuse the LV HubSpot "
        "credential deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP already binds by this name"
    )


# --- credential binding: NODE_CREDENTIAL_MAP entries, unchanged --------------------------

@pytest.mark.parametrize("name", list(NODES))
def test_node_name_stays_mapped_to_lv_hubspot_in_node_credential_map(name):
    """Node NAMES are unchanged by the transport swap, so NODE_CREDENTIAL_MAP binds them
    exactly as before — no deploy-script change is needed, and the fail-closed
    unmapped-credential guard stays untouched."""
    assert name in deploy.NODE_CREDENTIAL_MAP, (
        f"{name!r} has no NODE_CREDENTIAL_MAP entry — it would deploy UNBOUND and 401 at runtime"
    )
    assert deploy.NODE_CREDENTIAL_MAP[name] == {
        "cred_type": "hubspotAppToken", "cred_name": "LV HubSpot",
    }


# --- properties: real JSON array, never a CSV string ------------------------------------

@pytest.mark.parametrize("name", list(NODES))
def test_node_requests_the_expected_properties_as_a_real_json_array(name):
    cfg = NODES[name]
    doc = _load()
    node = _node(doc, name)
    body = node["parameters"]["jsonBody"]
    assert _extract_json_body_properties(body) == _csv_to_list(cfg["properties_csv"]), (
        f"{name}: jsonBody properties do not match the expected CSV-derived list — HubSpot "
        "rejects a CSV string here with a 400 VALIDATION_ERROR (live-confirmed 2026-07-28)"
    )


# --- filter parity with the native nodes each replaces -----------------------------------

@pytest.mark.parametrize("name", list(NODES))
def test_node_body_preserves_the_original_filter_semantics(name):
    cfg = NODES[name]
    doc = _load()
    node = _node(doc, name)
    body = node["parameters"]["jsonBody"]
    for token in cfg["filter_tokens"]:
        assert token in body, f"{name}: jsonBody missing expected token {token!r}\n{body}"


# --- REACH-04: no native HubSpot node remains in this lane -------------------------------

def test_no_native_hubspot_node_remains_in_enrichment_contacts_lane():
    """The offline harness (tests/n8n/bareEventChainFlow.test.mjs) models every
    HTTP-typed step as exactly ONE item — faithful only for the envelope transport. A
    native node reappearing in this lane would silently invalidate the harness rather than
    fail it, so this is asserted directly over the whole built workflow, not just the two
    nodes this file names."""
    doc = _load()
    native = [n["name"] for n in doc["nodes"] if n.get("type") == "n8n-nodes-base.hubspot"]
    assert not native, (
        f"{WORKFLOW} still contains native n8n-nodes-base.hubspot node(s): {native} — "
        "BUG 23's fix requires zero native HubSpot nodes in the enrichment contacts lane"
    )
