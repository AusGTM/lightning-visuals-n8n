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
    # F1 (2026-08-25): the weaker fallback search — lastname EQ only, no company clause
    # at all (dropped entirely rather than loosened; see test_hubspot_name_search_
    # fallback_carries_no_company_filter below). Its own predecessor is "HubSpot Name
    # Search", an HTTP node that has already replaced $json with its own response by the
    # time this node's expressions evaluate — so its filter value reads "Build Identity"
    # BY NODE NAME, never bare $json (the bd682a2 idiom "HubSpot Fetch By Id" already
    # follows, mirrored here for the same reason).
    "HubSpot Name Search Fallback": {
        "properties_csv": ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
        "filter_tokens": [
            'propertyName: "lastname"', 'operator: "EQ"',
            "$('Build Identity').item.json.identity_keys.lastName",
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

# --- Phase 36 Plan 02: HubSpot Name Search shares HubSpot Search's transport shape -----

def test_hubspot_name_search_uses_contains_token_never_the_bare_operator():
    """HubSpot CRM v3's string-operator vocabulary is closed and has no bare `CONTAINS` —
    a bare one is a guaranteed 400 that only surfaces against the live tenant. Asserted
    directly against the node's own jsonBody string (not a re-`json.dumps()`'d copy of the
    whole document, which double-encodes this field's embedded quotes and would make a
    substring check like this misfire)."""
    doc = _load()
    body = _node(doc, "HubSpot Name Search")["parameters"]["jsonBody"]
    assert 'operator: "CONTAINS_TOKEN"' in body
    operators = re.findall(r'operator:\s*"([A-Z_]+)"', body)
    assert "CONTAINS" not in operators, operators


def test_hubspot_name_search_has_shape_parity_with_hubspot_search():
    """The new match-lane search node must use the SAME credential-bound httpRequest
    transport as the existing email-EQ search — never a native n8n HubSpot node
    (BUG 10 / BUG 23)."""
    doc = _load()
    email_search = _node(doc, "HubSpot Search")
    name_search = _node(doc, "HubSpot Name Search")
    assert name_search["type"] == email_search["type"]
    assert name_search["typeVersion"] == email_search["typeVersion"]
    assert name_search.get("onError") == email_search.get("onError")
    for key in ("authentication", "nodeCredentialType", "method", "url"):
        assert name_search["parameters"].get(key) == email_search["parameters"].get(key), (
            f"HubSpot Name Search.{key} diverges from HubSpot Search.{key}"
        )


# --- F1 (2026-08-25): the fallback search's own shape and wiring --------------------------

def test_hubspot_name_search_fallback_has_shape_parity_with_hubspot_name_search():
    doc = _load()
    primary = _node(doc, "HubSpot Name Search")
    fallback = _node(doc, "HubSpot Name Search Fallback")
    assert fallback["type"] == primary["type"]
    assert fallback["typeVersion"] == primary["typeVersion"]
    assert fallback.get("onError") == primary.get("onError")
    for key in ("authentication", "nodeCredentialType", "method", "url"):
        assert fallback["parameters"].get(key) == primary["parameters"].get(key), (
            f"HubSpot Name Search Fallback.{key} diverges from HubSpot Name Search.{key}"
        )


def test_hubspot_name_search_fallback_carries_no_company_filter_at_all():
    """The fallback drops the company clause entirely rather than loosening it — company
    re-verification for a hit found this way happens in Adapt Name Search's own JS
    (mediumCandidates({requireCompanyToken: false})), never at the HubSpot filter.
    `company` still appears in the requested PROPERTIES list (mediumCandidates' output
    projects it onto every candidate) — this checks the filterGroups only."""
    doc = _load()
    body = _node(doc, "HubSpot Name Search Fallback")["parameters"]["jsonBody"]
    assert 'propertyName: "company"' not in body
    operators = re.findall(r'operator:\s*"([A-Z_]+)"', body)
    assert operators == ["EQ"], operators


def test_the_fallback_sits_sequentially_between_the_primary_search_and_its_adapter():
    """Never a parallel fan-out from IF Name Searchable — a Code node reading an
    unexecuted node via $() throws, and item alignment across primary/fallback must stay
    1:1 by row."""
    doc = _load()
    conns = doc["connections"]
    assert conns["HubSpot Name Search"]["main"][0][0]["node"] == "HubSpot Name Search Fallback"
    assert conns["HubSpot Name Search Fallback"]["main"][0][0]["node"] == "Adapt Name Search"


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
