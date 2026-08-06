# tests/test_enrichment_list_branch.py
#
# Phase 25 Plan 03 Task 2 — the structural proof of the list-resolution branch against the
# BUILT workflow. Mirrors the BFS/inbound-edge idiom in tests/test_remaining_credits_response.py.
#
# What this file is for, in one sentence: the branch is ADDITIVE, and a structural test is
# the only offline way to prove that. `Parse HubSpot Event` treats an object with no `events`
# array as a single bare event, so a list body that reached it UNEXPANDED would resolve to
# one unknown-object-type event, terminate as unsupported and return a clean 200 — a silent
# no-op, not an error (T-25-16). The branch therefore has to sit UPSTREAM of that node, and
# the record-ID lane has to be the untouched false lane of the IF that puts it there.
import copy
import json
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"

# The four nodes the branch is made of, plus the expansion gate. Named once, so the
# non-vacuity sweep below cannot drift out of step with the wiring assertions.
BRANCH_NODES = (
    "IF List Input",
    "HubSpot List By Name",
    "HubSpot List Memberships",
    "Expand List To Events",
    "IF List Expanded",
)


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _outbound(doc, name):
    """[[targets of branch 0], [targets of branch 1], ...] for `name`."""
    return [[e["node"] for e in branch]
            for branch in doc["connections"].get(name, {}).get("main", [])]


def _inbound_edges(doc, target):
    edges = []
    for src, spec in doc["connections"].items():
        for branch_idx, branch in enumerate(spec.get("main", [])):
            for edge in branch:
                if edge["node"] == target:
                    edges.append((src, branch_idx))
    return sorted(edges)


def _reachable_from(doc, start):
    conns = doc["connections"]
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for branch in conns.get(cur, {}).get("main", []):
            for edge in branch:
                if edge["node"] not in seen:
                    seen.add(edge["node"])
                    q.append(edge["node"])
    return seen


# --- the whole wiring contract, as ONE callable so non-vacuity can exercise it -------------

def assert_branch_wiring(doc):
    """Every structural property of the list branch, in one place.

    Called by the individual tests below (so a failure names the property it broke) AND by
    the non-vacuity sweep (so we prove these assertions actually bite when a node vanishes).
    """
    names = {n["name"] for n in doc["nodes"]}
    for name in BRANCH_NODES:
        assert name in names, f"{name} is missing from the built workflow"

    # The trigger no longer edges straight into the parser — it edges into the list IF.
    assert _outbound(doc, "Webhook Trigger") == [["IF List Input"]]

    # true -> resolve the list; false -> EXACTLY the edge the trigger used to carry, and
    # nothing else. This is the "additive, not a re-route" property.
    assert _outbound(doc, "IF List Input") == [
        ["HubSpot List By Name"],
        ["Parse HubSpot Event"],
    ]

    assert _outbound(doc, "HubSpot List By Name") == [["HubSpot List Memberships"]]
    assert _outbound(doc, "HubSpot List Memberships") == [["Expand List To Events"]]
    assert _outbound(doc, "Expand List To Events") == [["IF List Expanded"]]

    # Success re-enters the ordinary path; a refusal reaches the caller as a response
    # rather than dangling.
    assert _outbound(doc, "IF List Expanded") == [
        ["Parse HubSpot Event"],
        ["Respond to Webhook"],
    ]

    # The parser is fed by exactly these three lanes and nothing else. fix(40) /
    # WINDOWS.md #3 added "Execute Workflow Trigger" as a second entry point (SJ-3's
    # dispatch target) feeding the parser directly, alongside the two list-branch lanes.
    assert _inbound_edges(doc, "Parse HubSpot Event") == [
        ("Execute Workflow Trigger", 0), ("IF List Expanded", 0), ("IF List Input", 1),
    ]


def test_branch_wiring_holds_on_the_built_workflow():
    assert_branch_wiring(_load())


def test_the_record_id_path_still_runs_trigger_to_parser_without_touching_the_list_nodes():
    """The record-ID envelope's path: Webhook -> IF List Input (false) -> Parse HubSpot
    Event. No HubSpot Lists call sits on it, so a record-ID batch cannot spend a Lists
    API call or depend on the crm.lists.read scope."""
    doc = _load()
    false_lane = _outbound(doc, "IF List Input")[1]
    assert false_lane == ["Parse HubSpot Event"]
    assert "Parse HubSpot Event" in _reachable_from(doc, "Webhook Trigger")


def test_the_list_nodes_sit_upstream_of_the_parser_not_beside_it():
    """T-25-16: an unexpanded list body reaching the parser is a silent 200, so the branch
    must be an ANCESTOR of it, never a sibling."""
    doc = _load()
    from_if = _reachable_from(doc, "IF List Input")
    for name in ("HubSpot List By Name", "HubSpot List Memberships",
                 "Expand List To Events", "Parse HubSpot Event"):
        assert name in from_if
    # ...and the parser must not loop back into the branch.
    from_parser = _reachable_from(doc, "Parse HubSpot Event")
    assert set(BRANCH_NODES) & from_parser == set()


# --- credential binding: the client never holds a HubSpot token (D-01) --------------------

@pytest.mark.parametrize("name", ["HubSpot List By Name", "HubSpot List Memberships"])
def test_list_nodes_are_credential_bound_httprequest_nodes(name):
    node = _node(_load(), name)
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["parameters"]["method"] == "GET"
    assert node["parameters"]["authentication"] == "predefinedCredentialType"
    assert node["parameters"]["nodeCredentialType"] == "hubspotAppToken"
    # A failed Lists read must arrive at the expansion node as an unreadable response it
    # can refuse in words, never as a thrown execution that 500s with no explanation.
    assert node["onError"] == "continueRegularOutput"


@pytest.mark.parametrize("name", ["HubSpot List By Name", "HubSpot List Memberships"])
def test_list_nodes_are_mapped_for_credential_binding(name):
    """bind_credentials() fails closed on an unmapped credential-requiring node, so an
    unmapped list node would block the whole deploy (or, before that guard existed, deploy
    unbound and 401 only at runtime)."""
    import scripts.deploy_n8n_workflows as deploy
    assert name in deploy.NODE_CREDENTIAL_MAP
    assert deploy.NODE_CREDENTIAL_MAP[name]["cred_name"] == "LV HubSpot"


def test_list_nodes_call_the_crm_v3_lists_endpoints():
    doc = _load()
    by_name = _node(doc, "HubSpot List By Name")["parameters"]["url"]
    memberships = _node(doc, "HubSpot List Memberships")["parameters"]["url"]
    assert by_name.startswith("=https://api.hubapi.com/crm/v3/lists/object-type-id/")
    assert "/name/" in by_name
    assert memberships.startswith("=https://api.hubapi.com/crm/v3/lists/")
    assert "/memberships?limit=" in memberships


# --- the ceiling: asked for as ceiling+1, enforced by refusal (D-15, T-25-07) -------------

def test_memberships_asks_for_one_more_than_the_baked_ceiling():
    """At exactly `limit` a caller cannot tell "the whole list" from "the first page", so
    the request has to overshoot by one for an oversize list to be detectable at all."""
    import build_cloud_workflows as builder
    ceiling = builder.ENRICH_MAX_LIST_RECORDS
    assert isinstance(ceiling, int) and ceiling >= 1
    url = _node(_load(), "HubSpot List Memberships")["parameters"]["url"]
    assert url.endswith(f"/memberships?limit={ceiling + 1}")


def test_the_expansion_node_bakes_the_ceiling_as_a_build_time_constant():
    import build_cloud_workflows as builder
    code = _node(_load(), "Expand List To Events")["parameters"]["jsCode"]
    assert f"const MAX_LIST_RECORDS = {builder.ENRICH_MAX_LIST_RECORDS};" in code


def test_the_expansion_gate_admits_only_a_nonempty_events_array():
    """A refusal carries `events: []`, and so would a regressed expansion node that refused
    and expanded at once. Gating on the events themselves means zero events can never reach
    the enrichment chain — which also closes D-22 (zero items into a responseNode webhook
    returns NO response and hangs until Cloudflare 524s)."""
    left = _node(_load(), "IF List Expanded")["parameters"]["conditions"]["conditions"][0]["leftValue"]
    assert "Array.isArray($json.events)" in left
    assert "$json.events.length > 0" in left


# --- the expansion node's own reads --------------------------------------------------------

def test_expansion_reads_the_body_and_both_responses_by_node_name_not_bare_json():
    """An upstream HTTP response has already replaced $json by the time this Code node runs
    — the same identity-loss class the provider request bodies fix."""
    code = _node(_load(), "Expand List To Events")["parameters"]["jsCode"]
    for name in ('"Webhook Trigger"', '"HubSpot List By Name"', '"HubSpot List Memberships"'):
        assert f"nodeFirstJson({name})" in code
    # Guarded: a node that failed or never executed degrades to a refusal, never a throw.
    assert "catch (e) { return null; }" in code


def test_expansion_carries_the_provider_selection_through_unchanged():
    """T-25-02: an expanded batch must not silently enable more providers than were
    approved, and an absent selection must stay absent so the parser fails closed."""
    code = _node(_load(), "Expand List To Events")["parameters"]["jsCode"]
    assert 'hasOwnProperty.call(body, "providers")' in code
    assert "envelope.providers = result.providers" in code


def test_the_view_refusal_wording_is_baked_into_the_workflow():
    """Amendment #7's recorded operator-facing sentence, and Pitfall 2's mitigation: a view
    is refused, never resolved against the list endpoint."""
    code = _node(_load(), "Expand List To Events")["parameters"]["jsCode"]
    assert "HubSpot doesn't expose views through its API" in code
    assert "Save that view as a list in HubSpot" in code
    assert "body.view !== undefined" in code


# --- determinism / safety ------------------------------------------------------------------

def test_zero_env_or_vars_expressions_workflow_wide():
    assert not re.findall(r"\$env\b|\$vars\b", WORKFLOW_PATH.read_text())


def test_the_branch_arms_nothing():
    text = WORKFLOW_PATH.read_text()
    assert not re.findall(r'ALLOW_HUBSPOT_[A-Z_]* = "true"', text)


# --- non-vacuity: prove the wiring assertions actually bite --------------------------------

@pytest.mark.parametrize("missing", BRANCH_NODES)
def test_wiring_assertions_fail_when_any_branch_node_is_absent(missing):
    """Without this, every assertion above could be silently satisfied by a workflow that
    never grew the branch at all."""
    doc = copy.deepcopy(_load())
    doc["nodes"] = [n for n in doc["nodes"] if n["name"] != missing]
    doc["connections"].pop(missing, None)
    for spec in doc["connections"].values():
        for branch in spec.get("main", []):
            branch[:] = [e for e in branch if e["node"] != missing]
    with pytest.raises(AssertionError):
        assert_branch_wiring(doc)


def test_wiring_assertions_fail_if_the_record_id_lane_is_re_routed():
    """The single most important negative: if the IF's false lane stops landing on
    `Parse HubSpot Event`, the record-ID path has been re-routed, not left alone."""
    doc = copy.deepcopy(_load())
    doc["connections"]["IF List Input"]["main"][1] = [
        {"node": "HubSpot List By Name", "type": "main", "index": 0}
    ]
    with pytest.raises(AssertionError):
        assert_branch_wiring(doc)


def test_wiring_assertions_fail_if_a_refusal_is_routed_into_the_enrichment_chain():
    doc = copy.deepcopy(_load())
    doc["connections"]["IF List Expanded"]["main"][1] = [
        {"node": "Parse HubSpot Event", "type": "main", "index": 0}
    ]
    with pytest.raises(AssertionError):
        assert_branch_wiring(doc)
