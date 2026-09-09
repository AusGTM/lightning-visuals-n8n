# tests/test_merge_helpers.py
#
# Phase 70 Plan 02 (D-70-01/D-70-02/D-70-04): unit proof for the new Merge-node builder
# helpers in scripts/build_cloud_workflows.py, over small hand-built graphs — never the
# committed JSON (that proof is tests/n8n/ingestTracerFlow.test.mjs, over the walker).
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_cloud_workflows as b  # noqa: E402


def _code_node(name, x=0, y=0):
    return {"parameters": {"jsCode": "return $input.all();"}, "id": f"id-{name}",
            "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [x, y]}


def _trigger_node(name, node_type="n8n-nodes-base.webhook"):
    return {"parameters": {}, "id": f"id-{name}", "name": name, "type": node_type,
            "position": [0, 0]}


def test_merge_node_append_mode_shape():
    node = b.merge_node("My Merge", 10, 20, inputs=3, mode="append")
    assert node["type"] == "n8n-nodes-base.merge"
    assert node["typeVersion"] == 3.2
    assert node["parameters"] == {"mode": "append", "numberInputs": 3}
    assert node["position"] == [10, 20]


def test_merge_node_combine_by_position_sets_preferlast_clash_handling():
    node = b.merge_node("Carry Merge", 0, 0, inputs=2, mode="combine",
                        combine_by="combineByPosition")
    assert node["parameters"]["mode"] == "combine"
    assert node["parameters"]["combineBy"] == "combineByPosition"
    assert node["parameters"]["options"]["clashHandling"]["values"]["resolveClash"] == "preferLast"


def test_classify_convergence_fan_in_for_two_edges_from_one_trigger():
    trigger = _trigger_node("Trigger")
    a = _code_node("A")
    target = _code_node("Target")
    nodes = [trigger, a, target]
    conns = {
        "Trigger": {"main": [[{"node": "A", "type": "main", "index": 0},
                               {"node": "Target", "type": "main", "index": 0}]]},
        "A": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
    }
    nodes_by_name = {n["name"]: n for n in nodes}
    assert b.classify_convergence(nodes_by_name, conns, "Target") == "fan_in"


def test_classify_convergence_entry_points_for_two_disjoint_triggers():
    trigger_a = _trigger_node("Trigger A", "n8n-nodes-base.webhook")
    trigger_b = _trigger_node("Trigger B", "n8n-nodes-base.executeWorkflowTrigger")
    target = _code_node("Target")
    nodes = [trigger_a, trigger_b, target]
    conns = {
        "Trigger A": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
        "Trigger B": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
    }
    nodes_by_name = {n["name"]: n for n in nodes}
    assert b.classify_convergence(nodes_by_name, conns, "Target") == "entry_points"


def test_splice_merge_before_raises_on_an_alternate_entry_point_convergence():
    """The must-have this plan pins: 'splice_merge_before raises when asked to merge an
    alternate-entry-point convergence, asserted by a test over a hand-built graph with
    two trigger nodes.'"""
    trigger_a = _trigger_node("Trigger A", "n8n-nodes-base.webhook")
    trigger_b = _trigger_node("Trigger B", "n8n-nodes-base.executeWorkflowTrigger")
    target = _code_node("Target")
    nodes = [trigger_a, trigger_b, target]
    conns = {
        "Trigger A": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
        "Trigger B": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
    }
    with pytest.raises(ValueError, match="(?i)entry points"):
        b.splice_merge_before(nodes, conns, "Target")


def test_splice_merge_before_creates_one_merge_with_two_distinct_inputs():
    a = _code_node("A", 100, 0)
    c = _code_node("C", 100, 200)
    target = _code_node("Target", 300, 100)
    nodes = [a, c, target]
    conns = {
        "A": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
        "C": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
    }
    merge_name = b.splice_merge_before(nodes, conns, "Target", merge_name="Test Merge")
    assert merge_name == "Test Merge"
    merges = [n for n in nodes if n["type"] == "n8n-nodes-base.merge"]
    assert len(merges) == 1
    assert merges[0]["parameters"]["numberInputs"] == 2

    a_target = conns["A"]["main"][0][0]
    c_target = conns["C"]["main"][0][0]
    assert {a_target["node"], c_target["node"]} == {"Test Merge"}
    assert {a_target["index"], c_target["index"]} == {0, 1}
    assert conns["Test Merge"]["main"][0][0]["node"] == "Target"


def test_splice_merge_before_raises_with_fewer_than_two_inbound_edges():
    a = _code_node("A")
    target = _code_node("Target")
    nodes = [a, target]
    conns = {"A": {"main": [[{"node": "Target", "type": "main", "index": 0}]]}}
    with pytest.raises(ValueError, match="nothing to converge"):
        b.splice_merge_before(nodes, conns, "Target")


def test_set_always_output_data_flags_named_nodes_and_raises_on_a_missing_one():
    a = _code_node("A")
    c = _code_node("C")
    nodes = [a, c]
    b.set_always_output_data(nodes, ["A", "C"])
    assert a["alwaysOutputData"] is True
    assert c["alwaysOutputData"] is True

    with pytest.raises(ValueError, match="no node named"):
        b.set_always_output_data(nodes, ["Missing"])


def test_ingest_workflow_carries_exactly_one_merge_named_ingest_merge_response():
    wf = b.build_cloud()
    merges = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.merge"]
    assert sorted(n["name"] for n in merges) == ["Associate Carry Merge", "Ingest Merge Response"]

    ingest_merge = next(n for n in merges if n["name"] == "Ingest Merge Response")
    assert ingest_merge["parameters"]["mode"] == "append"

    carry_merge = next(n for n in merges if n["name"] == "Associate Carry Merge")
    assert carry_merge["parameters"]["mode"] == "combine"
    assert carry_merge["parameters"]["combineBy"] == "combineByPosition"
