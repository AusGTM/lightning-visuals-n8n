# tests/test_cloud_write_path.py
#
# Phase 16 Task 6 — offline, structural proof that the Cloud webhook write path is
# authenticated, targets real record ids, fails closed on a HubSpot lookup failure, and
# performs zero record writes unless the build-time write-safety gate is enabled. Closes
# reviews #7/#8/#9 (all VERIFIED against source per the plan).
import json
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import (  # noqa: E402
    CONFIG_FLAG_DEFAULTS,
    ENRICH_ADAPT_CO_SEARCH,
    ENRICH_ADAPT_SEARCH,
    ENRICH_GATE,
    ENRICH_CO_GATE,
    WRITE_SAFETY_DEFAULTS,
)

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _reachable_from(doc, start):
    conns = doc["connections"]
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for branch in conns.get(cur, {}).get("main", []):
            for edge in branch:
                nm = edge["node"]
                if nm not in seen:
                    seen.add(nm)
                    q.append(nm)
    return seen


# --- (a) webhook auth + event parse (review #7) --------------------------------------

def test_webhook_trigger_uses_native_header_auth():
    """CLAUDE.md §18.1 — the shared-secret check is the Webhook Trigger node's OWN
    native Header Auth (n8n rejects an unauthenticated request before any node runs),
    never a Code node reading the secret value."""
    doc = _load()
    webhook = _node(doc, "Webhook Trigger")
    assert webhook["type"] == "n8n-nodes-base.webhook"
    assert webhook["parameters"]["authentication"] == "headerAuth"


def test_parse_hubspot_event_node_exists_upstream_of_build_identity():
    doc = _load()
    reachable_from_webhook = _reachable_from(doc, "Webhook Trigger")
    assert "Parse HubSpot Event" in reachable_from_webhook
    # It must be an ANCESTOR of Build Identity (and Build Company Identity), not a
    # sibling/unrelated node: BFS from Parse HubSpot Event must reach both.
    from_parser = _reachable_from(doc, "Parse HubSpot Event")
    assert "Build Identity" in from_parser
    assert "Build Company Identity" in from_parser


def test_object_type_router_sends_companies_events_to_the_company_branch():
    doc = _load()
    router = _node(doc, "Route By Object Type")
    assert router["type"] == "n8n-nodes-base.if"
    cond = router["parameters"]["conditions"]["conditions"][0]
    assert cond["leftValue"] == "={{ $json.object_type }}"
    assert cond["rightValue"] == "companies"
    true_branch, false_branch = router["parameters"] and doc["connections"]["Route By Object Type"]["main"]
    assert true_branch[0]["node"] == "Build Company Identity"
    assert false_branch[0]["node"] == "Build Identity"


def test_parse_hubspot_event_jscode_normalizes_object_type_per_claude_md_18_3():
    doc = _load()
    node = _node(doc, "Parse HubSpot Event")
    code = node["parameters"]["jsCode"]
    for token in ("normalizeObjectType", '"contacts"', '"companies"', "objectId", "subscriptionType"):
        assert token in code, f"Parse HubSpot Event jsCode missing {token!r}"


# --- (b) real HubSpot nodes + record-id preservation + fail-closed (review #8) -------

def test_hubspot_search_node_carries_nonempty_filtergroups_and_requests_hs_object_id():
    """BUG 23 (Phase 17.01): "HubSpot Search" moved off the native node onto the same
    credential-bound httpRequest transport "HubSpot Company Search" already uses (BUG 10 /
    Phase 16.6) — filters/properties now live in the jsonBody expression, not
    filterGroupsUi/additionalFields. See
    test_hubspot_company_search_node_carries_nonempty_filters_and_requests_hs_object_id
    below for the twin this test now mirrors exactly."""
    doc = _load()
    node = _node(doc, "HubSpot Search")
    body = node["parameters"]["jsonBody"]
    assert "filterGroups:" in body and "filters:" in body, (
        "HubSpot Search jsonBody has no filterGroups/filters — matches no record ever"
    )
    assert '"hs_object_id"' in body, "HubSpot Search does not request hs_object_id"


def test_hubspot_company_search_node_carries_nonempty_filters_and_requests_hs_object_id():
    """httpRequest-transport equivalent of the guard above, for "HubSpot Company Search"
    (BUG 10 / Phase 16.6). Filters/properties live in the jsonBody expression, not
    filterGroupsUi/additionalFields — parses the SAME facts out of that expression."""
    doc = _load()
    node = _node(doc, "HubSpot Company Search")
    body = node["parameters"]["jsonBody"]
    assert "filterGroups:" in body and "filters:" in body, (
        "HubSpot Company Search jsonBody has no filterGroups/filters — matches no record ever"
    )
    assert '"hs_object_id"' in body, "HubSpot Company Search does not request hs_object_id"


def test_hubspot_search_filters_use_the_correct_identity_property():
    doc = _load()
    contact_body = _node(doc, "HubSpot Search")["parameters"]["jsonBody"]
    assert 'propertyName: "email"' in contact_body
    assert 'operator: "EQ"' in contact_body

    company_body = _node(doc, "HubSpot Company Search")["parameters"]["jsonBody"]
    assert 'propertyName: "domain"' in company_body
    assert 'operator: "EQ"' in company_body


@pytest.mark.parametrize("adapt_js,label", [(ENRICH_ADAPT_SEARCH, "contacts"), (ENRICH_ADAPT_CO_SEARCH, "companies")])
def test_adapt_step_preserves_hs_object_id_and_tags_lookup_failed(adapt_js, label):
    assert "hs_object_id" in adapt_js, f"Adapt ({label}) does not preserve hs_object_id"
    assert "lookup_failed" in adapt_js, f"Adapt ({label}) does not tag lookup_failed"


@pytest.mark.parametrize("gate_js,label", [(ENRICH_GATE, "contacts"), (ENRICH_CO_GATE, "companies")])
def test_gate_never_routes_a_lookup_failed_row_to_create(gate_js, label):
    """Fail-closed (review #8): decideAction({}) returns "create" (enrichmentGate.js:61,
    frozen) — indistinguishable from a genuinely absent record unless the wrapper
    overrides it. Assert the override exists and targets exactly this case."""
    assert "lookup_failed" in gate_js, f"Gate ({label}) does not consult lookup_failed"
    assert 'action = "skip"' in gate_js, f"Gate ({label}) does not override a failed lookup to skip"


def test_hubspot_update_nodes_target_hs_object_id_not_the_never_set_contact_id():
    """Phase 16.7-01 (BUG 11): both update nodes moved off the native hubspot node onto a
    credential-bound httpRequest PATCH (tests/test_write_node_transport.py has the full
    structural guard) — the real id now travels in the URL expression rather than a
    native `contactId`/`companyId` parameter. This test still protects the same original
    fact review #8 cared about: the target is the REAL id preserved upstream, never a
    hardcoded/never-set placeholder."""
    doc = _load()
    hs_update = _node(doc, "HubSpot Update")
    assert hs_update["type"] == "n8n-nodes-base.httpRequest"
    assert "contactId" not in hs_update["parameters"]
    assert hs_update["parameters"]["url"] == (
        "=https://api.hubapi.com/crm/v3/objects/contacts/{{ $json.hs_object_id }}"
    )

    hs_co_update = _node(doc, "HubSpot Company Update")
    assert hs_co_update["type"] == "n8n-nodes-base.httpRequest"
    assert "companyId" not in hs_co_update["parameters"]
    assert hs_co_update["parameters"]["url"] == (
        "=https://api.hubapi.com/crm/v3/objects/companies/{{ $json.hs_object_id }}"
    )


# --- (c) write-safety gate (review #9) ------------------------------------------------

def test_write_safety_defaults_is_not_in_the_parity_guarded_config_flags():
    """WRITE_SAFETY_DEFAULTS is Cloud-write-only — LOCAL/LOCAL-LIVE never write a
    HubSpot record, so it must NOT enter CONFIG_FLAG_DEFAULTS (the parity-guarded set;
    tests/test_builder_flag_parity.py asserts exactly 6 flags there)."""
    assert set(WRITE_SAFETY_DEFAULTS.keys()).isdisjoint(CONFIG_FLAG_DEFAULTS.keys())
    assert WRITE_SAFETY_DEFAULTS["ALLOW_HUBSPOT_RECORD_WRITES"] == "false"


@pytest.mark.parametrize("name", ["Decide Action", "Decide Company Action"])
def test_decide_nodes_bake_write_safety_constants_and_gate_the_action(name):
    doc = _load()
    node = _node(doc, name)
    code = node["parameters"]["jsCode"]
    for const_name in WRITE_SAFETY_DEFAULTS:
        assert f"const {const_name} = " in code, f"{name} missing baked constant {const_name}"
    assert "_writeSafetyAllows(" in code
    assert '"write_blocked"' in code


def test_grep_allow_hubspot_record_writes_present_in_built_cloud_json():
    text = WORKFLOW_PATH.read_text()
    assert text.count("ALLOW_HUBSPOT_RECORD_WRITES") >= 1


def test_if_create_and_if_enrich_gates_are_downstream_of_decide_action():
    doc = _load()
    reachable = _reachable_from(doc, "Decide Action")
    assert "IF Create" in reachable
    assert "IF Enrich" in reachable
    co_reachable = _reachable_from(doc, "Decide Company Action")
    assert "IF Company Create" in co_reachable
    assert "IF Company Enrich" in co_reachable


def test_zero_env_or_vars_expressions_still_survive_write_safety_addition():
    """Write-safety constants are baked (Task 6), not env expressions — belt-and-braces
    on top of test_architecture_guard.py::test_no_env_or_vars_in_cloud_workflows."""
    import re
    text = WORKFLOW_PATH.read_text()
    assert not re.findall(r"\$env\b|\$vars\b", text)


# --- (d) Plan 04 (REQ-lusha-id-staging): the id row field reaches the property patch -----

def test_decide_action_spreads_lusha_ids_into_the_contact_patch():
    doc = _load()
    code = _node(doc, "Decide Action")["parameters"]["jsCode"]
    assert "row.lusha_ids" in code, "Decide Action does not spread row.lusha_ids into properties"


def test_decide_company_action_spreads_lusha_ids_into_the_company_patch():
    doc = _load()
    code = _node(doc, "Decide Company Action")["parameters"]["jsCode"]
    assert "row.lusha_ids" in code, "Decide Company Action does not spread row.lusha_ids into properties"


def test_normalize_score_nodes_extract_lusha_record_id():
    """The three normalize-and-score producers (contacts CLOUD, companies CLOUD) must call
    lushaRecordId() and attach it as its OWN row field, never as a scored candidate."""
    doc = _load()
    contact_code = _node(doc, "Normalize + Score")["parameters"]["jsCode"]
    assert "lushaRecordId(" in contact_code
    assert "lusha_contact_id" in contact_code

    company_code = _node(doc, "Normalize + Score Company")["parameters"]["jsCode"]
    assert "lushaRecordId(" in company_code
    assert "lusha_company_id" in company_code
