# tests/test_remaining_credits_response.py
#
# Phase 16.1 Plan 02 Task 1 — offline BFS/structural proof of the single-item credit
# branch (reviews C1 — each provider's usage/credit check fires AT MOST ONCE per run, fed
# from a dedicated single-item node off "Parse HubSpot Event", never the multi-row
# terminal/enrichment flow) and the honest "Build Response" convergence (reviews C3 —
# reachable from every terminal branch; per-batch first-arrival semantics are documented,
# NOT hard-determinism, and are NOT asserted here — response ordering + the 0-event case
# are Track B execution-level test items). Mirrors the BFS pattern in
# tests/test_cloud_companies_branch.py / tests/test_provider_gate_topology.py.
import json
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _inbound_edges(doc, target):
    """Every (source_node, branch_index) pair with an edge landing on `target`."""
    edges = []
    for src, spec in doc["connections"].items():
        for branch_idx, branch in enumerate(spec.get("main", [])):
            for edge in branch:
                if edge["node"] == target:
                    edges.append((src, branch_idx))
    return edges


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


# --- (a) once-per-run structural proof (reviews C1) -----------------------------------

def test_credit_request_is_a_single_item_node_fed_only_by_parse_hubspot_event():
    doc = _load()
    assert _inbound_edges(doc, "Credit Request") == [("Parse HubSpot Event", 0)]
    code = _node(doc, "Credit Request")["parameters"]["jsCode"]
    # Deliberately does NOT read $input — its output cardinality can never track the row
    # count upstream, so it always emits exactly one item.
    assert "$input" not in code
    assert "return [{ json: { providers_requested } }];" in code


def test_each_credit_gate_is_fed_only_by_credit_request_not_a_terminal_or_row_node():
    doc = _load()
    for gate in ("IF Lusha Credit Requested", "IF Apollo Credit Requested",
                 "IF ZoomInfo Credit Requested"):
        assert _inbound_edges(doc, gate) == [("Credit Request", 0)], (
            f"{gate} must be fed ONLY by the single-item Credit Request node"
        )


def test_each_credit_http_nodes_only_inbound_is_its_own_gate_true_lane():
    """The C1 once-per-run structural proof: a credit HTTP node's only inbound is its own
    `IF <provider> Credit Requested` TRUE (index 0) lane — never a terminal / multi-row
    enrichment node (which would fire once per row -> the live-observed Lusha 429)."""
    doc = _load()
    expected_gate = {
        "Lusha Usage": "IF Lusha Credit Requested",
        "Apollo Usage": "IF Apollo Credit Requested",
        "ZoomInfo Usage Mint": "IF ZoomInfo Credit Requested",
    }
    for credit_node, gate_name in expected_gate.items():
        edges = _inbound_edges(doc, credit_node)
        assert edges == [(gate_name, 0)], (
            f"{credit_node} must have exactly ONE inbound edge — its own {gate_name} "
            f"TRUE (index 0) output — got {edges}"
        )
    # ZoomInfo Usage (the secret-free GET) is fed only by its own Mint node.
    assert _inbound_edges(doc, "ZoomInfo Usage") == [("ZoomInfo Usage Mint", 0)]


def test_credit_gates_false_lane_is_a_dead_end_no_rejoin_needed():
    """Unlike the enabled-provider gate chain, credit gates do NOT rejoin at a shared
    exit — Build Response reads each credit node independently by name (guarded nodeAll),
    so a not-requested provider's gate false lane simply dead-ends."""
    doc = _load()
    for gate in ("IF Lusha Credit Requested", "IF Apollo Credit Requested",
                 "IF ZoomInfo Credit Requested"):
        false_targets = _node(doc, gate)  # sanity: node exists
        conns = doc["connections"][gate]["main"]
        assert conns[1] == [], f"{gate} false lane should dead-end (got {conns[1]})"


# --- (b) credit HTTP node shape: onError, credential-bound, ZoomInfo Accept header ------

def test_lusha_and_apollo_usage_nodes_are_credential_bound_header_auth():
    doc = _load()
    for name in ("Lusha Usage", "Apollo Usage"):
        node = _node(doc, name)
        assert node["type"] == "n8n-nodes-base.httpRequest"
        assert node["onError"] == "continueRegularOutput"
        assert node["parameters"]["authentication"] == "genericCredentialType"
        assert node["parameters"]["genericAuthType"] == "httpHeaderAuth"


def test_zoominfo_usage_mint_is_credential_bound_basic_auth():
    doc = _load()
    node = _node(doc, "ZoomInfo Usage Mint")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["onError"] == "continueRegularOutput"
    assert node["parameters"]["authentication"] == "genericCredentialType"
    assert node["parameters"]["genericAuthType"] == "httpBasicAuth"


def test_zoominfo_usage_get_sets_the_vnd_api_json_accept_header():
    doc = _load()
    code = _node(doc, "ZoomInfo Usage")["parameters"]["jsCode"]
    assert "application/vnd.api+json" in code
    assert "client_id" not in code and "client_secret" not in code  # secret-free (C2)


def test_zero_env_or_vars_expressions_in_the_credit_branch():
    assert not re.findall(r"\$env\b|\$vars\b", WORKFLOW_PATH.read_text())


# --- (c) Build Response convergence: 5 real terminals + 2 re-pointed lanes + unsupported

BUILD_RESPONSE_SOURCES = {
    ("HubSpot Create", 0), ("HubSpot Update", 0), ("Skip (NoOp)", 0),
    ("HubSpot Company Create", 0), ("HubSpot Company Update", 0),
    ("IF Enrich", 1), ("IF Company Enrich", 1),
    ("Unsupported Object Type", 0),
}


def test_build_response_is_reachable_from_every_terminal_branch():
    """Fails if only the five real terminal nodes converge — the two re-pointed
    IF-enrich-false lanes and the unsupported terminal must ALSO feed Build Response."""
    doc = _load()
    edges = set(_inbound_edges(doc, "Build Response"))
    assert edges == BUILD_RESPONSE_SOURCES, (
        f"Build Response inbound edges {edges} != expected {BUILD_RESPONSE_SOURCES}"
    )


def test_build_response_feeds_respond_to_webhook():
    doc = _load()
    targets = [e["node"] for b in doc["connections"]["Build Response"]["main"] for e in b]
    assert targets == ["Respond to Webhook"]
    node = _node(doc, "Respond to Webhook")
    assert node["type"] == "n8n-nodes-base.respondToWebhook"


def test_webhook_uses_response_node_mode_not_last_node():
    """Proves the MODE FLAG, not response determinism — per-batch first-arrival semantics
    are documented (Build Response's own jsCode comment), not asserted here (reviews C3)."""
    text = WORKFLOW_PATH.read_text()
    assert text.count('"responseMode": "responseNode"') == 1
    assert '"responseMode": "lastNode"' not in text


def test_unsupported_terminal_reaches_build_response_not_dead_ended():
    doc = _load()
    reachable = _reachable_from(doc, "Unsupported Object Type")
    assert "Build Response" in reachable


# --- (d) Build Response reads remaining_credits via the guarded nodeAll idiom ----------

def test_build_response_uses_guarded_nodeall_and_references_the_expected_fields():
    doc = _load()
    code = _node(doc, "Build Response")["parameters"]["jsCode"]
    assert "function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }" in code
    assert "remaining_credits" in code
    assert "providers_requested" in code
    assert "extractCredits(" in code
    # providers none/blank/absent -> providers_requested [] -> .map() -> remaining_credits [].
    assert "providers_requested.map(" in code


def test_build_response_maps_credit_node_names_to_all_three_providers():
    doc = _load()
    code = _node(doc, "Build Response")["parameters"]["jsCode"]
    for provider, node_name in (("lusha", "Lusha Usage"), ("apollo", "Apollo Usage"),
                                 ("zoominfo", "ZoomInfo Usage")):
        assert f'{provider}: "{node_name}"' in code


# --- determinism -------------------------------------------------------------------------

def test_zero_env_or_vars_expressions_workflow_wide():
    assert not re.findall(r"\$env\b|\$vars\b", WORKFLOW_PATH.read_text())
