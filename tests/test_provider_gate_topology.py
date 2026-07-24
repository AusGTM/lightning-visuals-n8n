# tests/test_provider_gate_topology.py
#
# Phase 16.1 Task 1 — offline BFS proof of the gated, bypass-convergence provider
# waterfall (SC-1/SC-2), the reviews A1 (single-execution dispatch) and A2 (unsupported
# object-type termination) input-hardening fixes, and the Phase 16.2 contacts seam
# marker (CONTEXT Locked Decision 8). Mirrors the graph-ancestry BFS precedent in
# tests/test_cloud_companies_branch.py / tests/test_cloud_write_path.py. Task 2 extends
# this file with the companies-branch mirror + the shared-helper structural-identity
# assertion.
import json
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


def _inbound_edges(doc, target):
    """Every (source_node, branch_index) pair with an edge landing on `target`."""
    edges = []
    for src, spec in doc["connections"].items():
        for branch_idx, branch in enumerate(spec.get("main", [])):
            for edge in branch:
                if edge["node"] == target:
                    edges.append((src, branch_idx))
    return edges


# --- CONTACTS gate topology (SC-1/SC-2) -----------------------------------------------

CONTACTS_PROVIDER_NODES = ["Lusha Enrich", "Apollo Match", "ZoomInfo Token Gate"]
CONTACTS_GATES = ["IF Lusha Enabled", "IF Apollo Enabled", "IF ZoomInfo Enabled"]


def test_each_contacts_provider_nodes_only_inbound_is_its_own_gate_true_output():
    doc = _load()
    expected_gate = dict(zip(CONTACTS_PROVIDER_NODES, CONTACTS_GATES))
    for provider_node, gate_name in expected_gate.items():
        edges = _inbound_edges(doc, provider_node)
        assert edges == [(gate_name, 0)], (
            f"{provider_node} must have exactly ONE inbound edge — its own {gate_name} "
            f"TRUE (index 0) output — got {edges}"
        )


def test_each_contacts_gates_false_lane_rejoins_the_same_stage_as_its_true_lane():
    """The bypass (false) lane and the provider's own exit both land on the SAME next
    stage — SC-2's convergence guarantee, proven structurally rather than by execution."""
    doc = _load()
    gate_next_stage = {
        "IF Lusha Enabled": "IF Apollo Enabled",
        "IF Apollo Enabled": "IF ZoomInfo Enabled",
        "IF ZoomInfo Enabled": "Normalize + Score",
    }
    for gate, next_stage in gate_next_stage.items():
        conns = doc["connections"][gate]["main"]
        false_targets = [e["node"] for e in conns[1]]
        assert false_targets == [next_stage], f"{gate} false lane does not bypass to {next_stage}"

    # And the provider's own exit reaches the SAME next stage.
    exit_next_stage = {
        "Lusha Enrich": "IF Apollo Enabled",
        "Apollo Match": "IF ZoomInfo Enabled",
        "ZoomInfo Enrich": "Normalize + Score",
    }
    for exit_node, next_stage in exit_next_stage.items():
        targets = [e["node"] for b in doc["connections"][exit_node]["main"] for e in b]
        assert targets == [next_stage], f"{exit_node} does not rejoin at {next_stage}"


def test_empty_enabled_set_bypass_only_path_reaches_normalize_and_decide_action():
    """SC-2: following ONLY the gates' false/bypass lanes from the dispatch entry (the
    none/blank/absent providers path — zero provider HTTP calls) still reaches
    Normalize + Score and Decide Action, proving the row spine is never dead-ended."""
    doc = _load()
    conns = doc["connections"]
    node = "IF Lusha Enabled"
    visited = set()
    for gate in CONTACTS_GATES:
        visited.add(gate)
        node = conns[gate]["main"][1][0]["node"]  # false/bypass lane only
    assert node == "Normalize + Score"
    reachable = _reachable_from(doc, "Normalize + Score")
    assert "Decide Action" in reachable


def test_contacts_provider_request_bodies_read_identity_by_node_name_not_bare_json():
    """Closes the latent identity-loss bug: a provider positioned after another
    provider's HTTP node would see that provider's RESPONSE as $json, not the row."""
    doc = _load()
    lusha_body = _node(doc, "Lusha Enrich")["parameters"]["jsonBody"]
    apollo_body = _node(doc, "Apollo Match")["parameters"]["jsonBody"]
    assert "$('Enrichment Gate').item.json.identity_keys" in lusha_body
    assert "$('Enrichment Gate').item.json.identity_keys" in apollo_body
    assert "$json.identity_keys" not in lusha_body
    assert "$json.identity_keys" not in apollo_body


def test_provider_gates_read_provider_enabled_by_node_name_not_bare_json():
    doc = _load()
    for gate in CONTACTS_GATES:
        left = _node(doc, gate)["parameters"]["conditions"]["conditions"][0]["leftValue"]
        assert "$('Parse HubSpot Event').item.json.provider_enabled." in left


def test_shared_provider_gate_bypass_chain_helper_is_called_not_hand_wired():
    """CONTEXT Locked Decision 8: the gate+bypass topology must come from the SHARED
    `_provider_gate_bypass_chain(...)` helper, not two hand-rolled inline connection
    dicts. Grep the builder source for the call site."""
    src = (ROOT / "scripts" / "build_cloud_workflows.py").read_text()
    assert "_provider_gate_bypass_chain(" in src
    assert src.count("_provider_gate_bypass_chain(") >= 1


# --- reviews A2 — unsupported object type terminates before any provider gate ---------

def test_unsupported_object_type_reaches_a_terminal_no_op_with_no_path_to_any_gate():
    doc = _load()
    assert "Unsupported Object Type" in {n["name"] for n in doc["nodes"]}
    reachable_from_unsupported = _reachable_from(doc, "Unsupported Object Type")
    all_gates = CONTACTS_GATES + [
        "IF Lusha Company Enabled", "IF Apollo Org Enabled", "IF ZoomInfo Company Enabled",
    ]
    for gate in all_gates:
        assert gate not in reachable_from_unsupported, (
            f"Unsupported Object Type can reach {gate} — a malformed event could still "
            "burn provider credits (reviews A2)"
        )
    # And Unsupported Object Type is reachable FROM the router itself (not orphaned).
    reachable_from_check = _reachable_from(doc, "IF Object Type Supported")
    assert "Unsupported Object Type" in reachable_from_check


def test_object_type_supported_gate_precedes_route_by_object_type():
    """IF Object Type Supported's TRUE lane feeds the existing (unchanged) Route By
    Object Type 2-way router; FALSE terminates. Route By Object Type itself keeps its
    original companies/contacts shape (tests/test_cloud_write_path.py pins it)."""
    doc = _load()
    conds = doc["connections"]["IF Object Type Supported"]["main"]
    true_targets = [e["node"] for e in conds[0]]
    false_targets = [e["node"] for e in conds[1]]
    assert true_targets == ["Route By Object Type"]
    assert false_targets == ["Unsupported Object Type"]


# --- reviews A1 — single-execution dispatch lane --------------------------------------

def test_provider_gate_chain_is_fed_by_a_single_action_not_skip_lane():
    """The create+enrich double-feed into the provider gate entry is gone — exactly ONE
    node (IF Provider Processing Needed) feeds the first gate, not two converging edges
    from a create/enrich switch."""
    doc = _load()
    edges = _inbound_edges(doc, "IF Lusha Enabled")
    assert edges == [("IF Provider Processing Needed", 0)], (
        f"IF Lusha Enabled (the gate chain entry) must have exactly one inbound edge "
        f"from IF Provider Processing Needed's TRUE lane — got {edges}"
    )
    # And the dispatch itself tests action != "skip", not a 3-way create/enrich/skip split.
    node = _node(doc, "IF Provider Processing Needed")
    cond = node["parameters"]["conditions"]["conditions"][0]
    assert cond["leftValue"] == "={{ $json.action }}"
    assert cond["rightValue"] == "skip"
    assert cond["operator"]["operation"] == "notEquals"


def test_route_action_switch_no_longer_feeds_the_provider_waterfall():
    """The old 3-way Route Action switch (create/enrich both -> Lusha Enrich) must no
    longer exist as a connections key feeding the waterfall — the dispatch is now the
    single IF Provider Processing Needed lane."""
    doc = _load()
    assert "Route Action" not in doc["connections"]


# --- reviews A3 — side-effect-free registry -------------------------------------------

def test_provider_registry_module_is_syntactically_valid_python():
    import ast
    ast.parse((ROOT / "scripts" / "provider_registry.py").read_text())


def test_importing_provider_registry_writes_no_files():
    import glob
    before = set(glob.glob(str(ROOT) + "/**/*", recursive=True))
    sys.path.insert(0, str(ROOT / "scripts"))
    import provider_registry  # noqa: F401
    after = set(glob.glob(str(ROOT) + "/**/*", recursive=True))
    assert after == before, f"importing provider_registry created file(s): {after - before}"


# --- Phase 16.2 seam marker -------------------------------------------------------------

def test_contacts_seam_is_documented_and_no_research_judge_node_exists():
    doc = _load()
    node_names = {n["name"] for n in doc["nodes"]}
    forbidden = {
        "Research Trigger Gate", "IF Research Needed", "Build Research Request",
        "Claude Web Research", "Validate Research Output", "Judge Gate", "IF Needs Judge",
        "Build Judge Request", "Judge Call", "Apply Judge Verdict",
    }
    # These names DO legitimately exist — but only on the COMPANIES branch. Assert none
    # of them are reachable from the CONTACTS "Normalize + Score" node.
    reachable = _reachable_from(doc, "Normalize + Score")
    leaked = forbidden & reachable
    assert not leaked, f"contacts branch leaked research/judge node(s): {leaked}"

    # The seam edge itself exists.
    targets = [e["node"] for b in doc["connections"]["Normalize + Score"]["main"] for e in b]
    assert "Merge Winners" in targets

    # A builder comment documents the seam.
    src = (ROOT / "scripts" / "build_cloud_workflows.py").read_text()
    assert "Phase 16.2 seam" in src or "16.2 seam" in src

    # An in-graph sticky note also documents it (kimi LOW-4 / gemini).
    sticky_contents = [
        n["parameters"]["content"] for n in doc["nodes"]
        if n["type"] == "n8n-nodes-base.stickyNote"
    ]
    assert any("Phase 16.2" in c and "seam" in c.lower() for c in sticky_contents), (
        "no in-graph sticky note documents the Phase 16.2 contacts research->judge seam"
    )


# --- determinism -----------------------------------------------------------------------

def test_zero_env_or_vars_expressions_in_the_new_gate_topology():
    """Belt-and-braces on top of test_architecture_guard.py's AR-4 guard: the new gate
    nodes/expressions introduce no $env/$vars usage."""
    import re
    text = WORKFLOW_PATH.read_text()
    assert not re.findall(r"\$env\b|\$vars\b", text)
