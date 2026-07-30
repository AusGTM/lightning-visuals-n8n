# tests/test_hubspot_node_auth.py
#
# n8n's HubSpot node selects its credential TYPE from its own `authentication` parameter.
# Left unset it falls back to the legacy API-key mode, which requires a `hubspotApi`
# credential — while this project provisions `hubspotAppToken` (from
# HUBSPOT_PRIVATE_APP_TOKEN). The mismatch is invisible until ACTIVATION: the workflow
# deploys with HTTP 200, and only `POST /workflows/{id}/activate` fails with
# "Missing required credential: hubspotApi" for every HubSpot node.
#
# Found live 2026-07-28 activating LV Enrichment — 8 nodes rejected at publish. Nothing
# offline caught it because the whole suite checks that nodes are BOUND (a `credentials`
# block exists) and never that the node ASKS FOR the type we bind.
#
# This is the third distinct class of "deploys fine, breaks later" defect this project
# has hit (after credential-map omissions and duplicate node names), so it gets the same
# treatment: a generic sweep over every built workflow, not a hand-maintained node list.
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
N8N_DIR = ROOT / "n8n"

HUBSPOT_NODE_TYPE = "n8n-nodes-base.hubspot"
EXPECTED_AUTH = "appToken"

# The credential type each `authentication` mode makes the node demand. Only appToken
# matches what scripts/provision_n8n_credentials.py creates.
AUTH_MODE_TO_CRED_TYPE = {
    "appToken": "hubspotAppToken",
    "apiKey": "hubspotApi",
    "oAuth2": "hubspotOAuth2Api",
}

WORKFLOW_FILES = sorted(N8N_DIR.glob("wf_*.json"))


def _hubspot_nodes(doc: dict) -> list:
    return [n for n in doc.get("nodes", []) if n.get("type") == HUBSPOT_NODE_TYPE]


@pytest.mark.parametrize("wf_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_hubspot_node_declares_apptoken_auth(wf_path: Path):
    """An unset `authentication` silently means legacy apiKey auth, which demands a
    credential type this project never provisions — an activation-time failure."""
    doc = json.loads(wf_path.read_text())
    wrong = {
        n["name"]: n.get("parameters", {}).get("authentication")
        for n in _hubspot_nodes(doc)
        if n.get("parameters", {}).get("authentication") != EXPECTED_AUTH
    }
    assert not wrong, (
        f"{wf_path.name}: HubSpot node(s) not set to authentication={EXPECTED_AUTH!r}: {wrong}. "
        f"n8n would demand credential type "
        f"{ {k: AUTH_MODE_TO_CRED_TYPE.get(v, '<default: hubspotApi>') for k, v in wrong.items()} } "
        f"and reject the workflow at ACTIVATION time, not at deploy."
    )


@pytest.mark.parametrize("wf_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_bound_hubspot_credential_type_matches_declared_auth_mode(wf_path: Path):
    """Where a node carries a bound credential block, its type must be the one its
    `authentication` mode actually asks for — binding the wrong type is exactly the
    failure this file exists to prevent."""
    doc = json.loads(wf_path.read_text())
    for node in _hubspot_nodes(doc):
        creds = node.get("credentials") or {}
        if not creds:
            continue  # binding happens at deploy time; absence here is not a defect
        mode = node.get("parameters", {}).get("authentication")
        expected_type = AUTH_MODE_TO_CRED_TYPE.get(mode, "hubspotApi")
        assert expected_type in creds, (
            f"{wf_path.name}: node {node['name']!r} declares authentication={mode!r} "
            f"(needs {expected_type!r}) but is bound as {sorted(creds)}."
        )


def test_company_create_carries_the_patch_and_needs_no_name_parameter():
    """n8n's NATIVE company:create required a `name` parameter (omitting it is an
    activation-time error). Phase 16.9 (BUG 13) moved company creates off that node onto a
    CRM v3 POST, where `name` is an ordinary member of `properties` — so the old guard no
    longer has a native node to apply to. What replaces it is the property that actually
    matters: the create must send the computed patch rather than an empty field map, which
    is what made the native node useless."""
    checked = 0
    for wf_path in WORKFLOW_FILES:
        doc = json.loads(wf_path.read_text())
        # No native company:create may survive anywhere — that is the regression to catch.
        for node in _hubspot_nodes(doc):
            params = node.get("parameters", {})
            assert not (params.get("resource") == "company"
                        and params.get("operation") == "create"), (
                f"{wf_path.name}: {node['name']!r} regressed to a native company:create")
        for node in doc["nodes"]:
            params = node.get("parameters", {})
            if (node.get("type") == "n8n-nodes-base.httpRequest"
                    and params.get("method") == "POST"
                    and str(params.get("url", "")).endswith("/crm/v3/objects/companies")):
                checked += 1
                assert "$json.properties" in params.get("jsonBody", "")
    assert checked, "no company create node found — this guard is vacuous"


# Phase 21 Plan 01 — the native-node CSV-vs-list pair that used to live here
# (test_hubspot_properties_are_a_list_not_a_csv_string + its vacuity guard
# test_at_least_one_node_actually_requests_properties) is retired. "Dedupe Search
# (candidate contacts)" was the last native-hubspot node anywhere in this repo carrying
# `additionalFields.properties` — every other search site moved to the httpRequest
# transport back in Phase 16.6/17.01, and this plan closed the final call site. The two
# remaining native hubspot nodes (SJ-1/SJ-2 "Set Requested") are `update` operations that
# use `updateFields.customPropertiesUi`, never `additionalFields.properties`
# (`_hs_update_set_property`, scripts/build_cloud_workflows.py) — so this class is now
# PERMANENTLY empty, not just empty today. Following this file's own stated philosophy
# ("a guard that silently stops applying is worse than no guard"), keeping a vacuity
# guard that can never again pass would be exactly that failure mode in reverse: a test
# that can never again DO anything but fail, forcing a future editor to silently delete
# it under time pressure instead of understanding why. The defect class itself remains
# fully covered — by the httpRequest-transport equivalents below,
# test_hubspot_httprequest_search_properties_are_a_real_json_array_never_a_csv_string and
# its own vacuity guard test_at_least_one_hubspot_credentialed_httprequest_node_exists_to_check
# — which is where every search node's CSV-vs-list risk actually lives now.


def test_workflow_files_were_actually_discovered():
    """Vacuity guard: an empty glob would make every parametrized test above pass by
    collecting zero cases."""
    assert WORKFLOW_FILES, f"no wf_*.json found under {N8N_DIR}"


def test_at_least_one_hubspot_node_exists_to_check():
    """Vacuity guard: if no workflow contained a HubSpot node, the sweeps above would
    pass trivially."""
    total = sum(len(_hubspot_nodes(json.loads(p.read_text()))) for p in WORKFLOW_FILES)
    assert total, "no HubSpot nodes found in any built workflow — the sweep is vacuous"


# --- BUG 10 / Phase 16.6: the httpRequest-transport equivalent of the two sweeps above ---
#
# 6 nodes (companies search/fetch-by-id across wf_enrichment_cloud.json and
# wf_scheduled_maintenance_cloud.json) moved from n8n-nodes-base.hubspot to
# n8n-nodes-base.httpRequest (n8n's HubSpot node has no `operation: "search"` for
# resource:company — confirmed by reading CompanyDescription.ts's companyOperations
# option list; the native node silently returned json:null live). This changes their TYPE,
# so test_every_hubspot_node_declares_apptoken_auth /
# test_hubspot_properties_are_a_list_not_a_csv_string above — both filtered to
# HUBSPOT_NODE_TYPE — silently stop covering them. "A guard that silently stops applying is
# worse than no guard" (16.6-CONTEXT.md): these two tests are that guard's httpRequest-
# transport equivalent, over the SAME class of defect (a CSV string reaching HubSpot's
# search API, which requires a real array).
HTTP_NODE_TYPE = "n8n-nodes-base.httpRequest"


def _hubspot_credentialed_http_nodes(doc: dict) -> list:
    """httpRequest nodes authenticating AS the hubspotAppToken credential type
    (predefinedCredentialType) — the BUG 10 replacement transport."""
    return [
        n for n in doc.get("nodes", [])
        if n.get("type") == HTTP_NODE_TYPE
        and n.get("parameters", {}).get("nodeCredentialType") == "hubspotAppToken"
    ]


@pytest.mark.parametrize("wf_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_hubspot_credentialed_httprequest_node_uses_predefined_credential_type(wf_path: Path):
    """Companion to test_every_hubspot_node_declares_apptoken_auth for the httpRequest
    transport: every node claiming nodeCredentialType:hubspotAppToken must actually declare
    authentication:predefinedCredentialType — the mode _node_requires_credential() and
    deploy_n8n_workflows.py's _CREDENTIAL_BEARING_HTTP_AUTH_MODES require for the node to be
    treated as credential-bearing and bound rather than deployed unbound."""
    doc = json.loads(wf_path.read_text())
    wrong = {
        n["name"]: n.get("parameters", {}).get("authentication")
        for n in _hubspot_credentialed_http_nodes(doc)
        if n.get("parameters", {}).get("authentication") != "predefinedCredentialType"
    }
    assert not wrong, (
        f"{wf_path.name}: hubspotAppToken httpRequest node(s) not set to "
        f"authentication=predefinedCredentialType: {wrong} — would deploy unbound "
        "(deploy_n8n_workflows.py's _node_requires_credential() would not recognize them)"
    )


@pytest.mark.parametrize("wf_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_hubspot_httprequest_search_properties_are_a_real_json_array_never_a_csv_string(wf_path: Path):
    """Companion to test_hubspot_properties_are_a_list_not_a_csv_string for the httpRequest
    transport: the SAME defect class (HubSpot's search API rejects a CSV string with a 400
    VALIDATION_ERROR) applies to the `properties: [...]` array embedded in this transport's
    jsonBody expression — it must be built from genuine JSON-array-of-strings syntax
    (`["a", "b"]`), never a single CSV-joined string literal (`"a,b"`)."""
    doc = json.loads(wf_path.read_text())
    bad = {}
    for n in _hubspot_credentialed_http_nodes(doc):
        body = n.get("parameters", {}).get("jsonBody", "")
        m = re.search(r"properties:\s*(\[[^\]]*\]|\"[^\"]*\")", body)
        if not m:
            continue
        if not m.group(1).startswith("["):
            bad[n["name"]] = m.group(1)
    assert not bad, (
        f"{wf_path.name}: hubspotAppToken httpRequest node(s) pass `properties` as a "
        f"non-array in jsonBody: {bad}. HubSpot's search API rejects a CSV string with a "
        "400 VALIDATION_ERROR."
    )


def test_at_least_one_hubspot_credentialed_httprequest_node_exists_to_check():
    """Vacuity guard: if no workflow contained a hubspotAppToken httpRequest node, the two
    sweeps above would pass trivially."""
    total = sum(
        len(_hubspot_credentialed_http_nodes(json.loads(p.read_text()))) for p in WORKFLOW_FILES
    )
    assert total, (
        "no hubspotAppToken-credentialed httpRequest nodes found in any built workflow — "
        "the httpRequest-transport sweep is vacuous"
    )
