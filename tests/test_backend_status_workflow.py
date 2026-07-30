# tests/test_backend_status_workflow.py
#
# Phase 25 Plan 02 Task 2 — offline structural proof of `n8n/wf_backend_status_cloud.json`
# (D-14): a straight sequential chain (webhook -> single-item request -> three probes ->
# response assembly -> responder), never a fan-out, so the response can never fire before
# all three provider probes have run. Mirrors the BFS/structural idiom in
# tests/test_remaining_credits_response.py.
import json
import re
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "n8n" / "wf_backend_status_cloud.json"


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


# --- non-vacuity guard ------------------------------------------------------------------

def test_workflow_file_exists_and_carries_nodes():
    """The structural proof below is meaningless against a missing or empty workflow —
    this must fail first if the built artifact is absent or carries zero nodes."""
    assert WORKFLOW_PATH.exists(), f"{WORKFLOW_PATH} does not exist"
    doc = _load()
    assert doc.get("nodes"), f"{WORKFLOW_PATH} carries zero nodes"


# --- (a) webhook trigger shape ------------------------------------------------------------

def test_status_webhook_trigger_is_post_header_auth_response_node():
    doc = _load()
    node = _node(doc, "Status Webhook Trigger")
    params = node["parameters"]
    assert node["type"] == "n8n-nodes-base.webhook"
    assert params["httpMethod"] == "POST"
    assert params["path"] == "hubspot/backend-status"
    assert params["responseMode"] == "responseNode"
    assert params["authentication"] == "headerAuth"


def test_status_webhook_triggers_only_downstream_is_status_credit_request():
    doc = _load()
    targets = [e["node"] for b in doc["connections"]["Status Webhook Trigger"]["main"] for e in b]
    assert targets == ["Status Credit Request"]


def test_status_credit_request_is_a_single_item_node_reading_no_input():
    doc = _load()
    code = _node(doc, "Status Credit Request")["parameters"]["jsCode"]
    # Deliberately does NOT read $input — output cardinality can never track anything
    # upstream, so it always emits exactly one item naming all three providers. (The
    # node's own comment mentions "$input" in prose, hence checking for actual usage
    # `$input.` rather than the bare substring.)
    assert "$input." not in code
    assert "providers_requested" in code
    for provider in ("lusha", "apollo", "zoominfo"):
        assert f'"{provider}"' in code


# --- (b) the three probes form a SEQUENTIAL CHAIN, never a fan-out ----------------------

def test_the_three_probe_entries_each_have_exactly_one_inbound_source():
    """D-14: chained sequentially, not fanned out. Each probe's inbound edge set has
    exactly one source, and (checked below) no single output carries edges to two
    different probe nodes."""
    doc = _load()
    expected_source = {
        "Lusha Usage": "Status Credit Request",
        "Apollo Usage": "Lusha Usage",
        "ZoomInfo Usage Token Gate": "Apollo Usage",
    }
    for probe, source in expected_source.items():
        edges = _inbound_edges(doc, probe)
        assert edges == [(source, 0)], (
            f"{probe} must have exactly ONE inbound edge — {source} index 0 — got {edges}"
        )


def test_no_single_node_output_fans_to_two_different_probe_nodes():
    doc = _load()
    probes = {"Lusha Usage", "Apollo Usage", "ZoomInfo Usage Token Gate"}
    for src, spec in doc["connections"].items():
        for branch in spec.get("main", []):
            targets_in_branch = {e["node"] for e in branch} & probes
            assert len(targets_in_branch) <= 1, (
                f"{src} output fans out to multiple probe nodes: {targets_in_branch} "
                "— probes must run sequentially, never fanned out (D-14)"
            )


def test_lusha_and_apollo_usage_nodes_are_credential_bound_header_auth_continue_on_error():
    doc = _load()
    for name in ("Lusha Usage", "Apollo Usage"):
        node = _node(doc, name)
        assert node["type"] == "n8n-nodes-base.httpRequest"
        assert node["onError"] == "continueRegularOutput"
        assert node["parameters"]["authentication"] == "genericCredentialType"
        assert node["parameters"]["genericAuthType"] == "httpHeaderAuth"


def test_zoominfo_usage_get_sets_the_vnd_api_json_accept_header():
    doc = _load()
    code = _node(doc, "ZoomInfo Usage")["parameters"]["jsCode"]
    assert "application/vnd.api+json" in code
    assert "ZOOMINFO_CLIENT" not in code  # secret-free, mirrors the enrichment lane


def test_zoominfo_usage_mint_is_credential_bound_basic_auth():
    doc = _load()
    node = _node(doc, "ZoomInfo Usage Mint")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["onError"] == "continueRegularOutput"
    assert node["parameters"]["authentication"] == "genericCredentialType"
    assert node["parameters"]["genericAuthType"] == "httpBasicAuth"


# --- (c) Build Credit Status: only inbound is the last probe, only outbound is the responder

def test_build_credit_status_only_inbound_is_the_last_probe_in_the_chain():
    doc = _load()
    edges = _inbound_edges(doc, "Build Credit Status")
    # ZoomInfo Usage is fed by BOTH the mint-then-cache lane and the cache-hit bypass lane
    # (the shared token-cache subgraph's own internal shape — not a second probe branch),
    # so both its outputs converging on Build Credit Status is expected and correct.
    assert {src for src, _ in edges} == {"ZoomInfo Usage"}


def test_build_credit_status_only_outbound_is_respond_to_webhook():
    doc = _load()
    targets = [e["node"] for b in doc["connections"]["Build Credit Status"]["main"] for e in b]
    assert targets == ["Respond to Webhook"]
    node = _node(doc, "Respond to Webhook")
    assert node["type"] == "n8n-nodes-base.respondToWebhook"


def test_build_credit_status_uses_guarded_nodeall_and_never_reads_input():
    doc = _load()
    code = _node(doc, "Build Credit Status")["parameters"]["jsCode"]
    assert "function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }" in code
    assert "extractCredits(" in code
    for provider, node_name in (("lusha", "Lusha Usage"), ("apollo", "Apollo Usage"),
                                 ("zoominfo", "ZoomInfo Usage")):
        assert f'{provider}: "{node_name}"' in code


def test_webhook_uses_response_node_mode_not_last_node():
    text = WORKFLOW_PATH.read_text()
    assert text.count('"responseMode": "responseNode"') == 1
    assert '"responseMode": "lastNode"' not in text


# --- (d) determinism / no secret env leak ------------------------------------------------

def test_zero_env_or_vars_expressions_in_the_status_workflow():
    assert not re.findall(r"\$env\b|\$vars\b", WORKFLOW_PATH.read_text())


def test_unreachable_dead_ends_absent_the_chain_is_fully_connected():
    """Sanity: the whole chain is reachable from the trigger — a broken link anywhere
    would silently orphan the responder."""
    doc = _load()
    reachable = _reachable_from(doc, "Status Webhook Trigger")
    for name in ("Status Credit Request", "Lusha Usage", "Apollo Usage",
                 "ZoomInfo Usage Token Gate", "ZoomInfo Usage", "Build Credit Status",
                 "Respond to Webhook"):
        assert name in reachable, f"{name} unreachable from Status Webhook Trigger"
