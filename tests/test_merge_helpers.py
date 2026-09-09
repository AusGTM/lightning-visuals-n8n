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


def test_classify_convergence_entry_points_for_a_mixed_three_source_convergence():
    """Phase 70 Plan 03 (Rule 1 fix): reproduces `Parse HubSpot Event`'s real shape —
    THREE sources, where two (on the SAME trigger, mutually-exclusive branches) share a
    trigger with EACH OTHER but NOT with the third (a genuinely different trigger). The
    original pairwise-partition check returned "fan_in" here because not ALL pairs were
    disjoint; the fix returns "entry_points" because ANY pair (the third vs. either of
    the first two) is disjoint, and a Merge here would hang on every execution that
    entered via "Trigger C" (the other two sources never even dispatch)."""
    trigger_a = _trigger_node("Trigger A", "n8n-nodes-base.webhook")
    trigger_c = _trigger_node("Trigger C", "n8n-nodes-base.executeWorkflowTrigger")
    if_one = _code_node("IF Branch One", 0, 0)
    if_two = _code_node("IF Branch Two", 0, 0)
    target = _code_node("Target")
    nodes = [trigger_a, trigger_c, if_one, if_two, target]
    conns = {
        "Trigger A": {"main": [[{"node": "IF Branch One", "type": "main", "index": 0},
                                 {"node": "IF Branch Two", "type": "main", "index": 0}]]},
        "IF Branch One": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
        "IF Branch Two": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
        "Trigger C": {"main": [[{"node": "Target", "type": "main", "index": 0}]]},
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


def test_ingest_workflow_carries_exactly_one_append_merge_named_ingest_merge_response():
    """D-70-01/D-70-04 (Phase 70 Plan 02 Task 3): "Ingest Merge Response" is still the
    ONE append-mode convergence Merge in front of "Build Ingest Response" — every OTHER
    Merge on this lane is a `combine`-mode carry merge across a specific HTTP hop
    (D-70-04), never a second fan-in convergence."""
    wf = b.build_cloud()
    merges = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.merge"]
    append_merges = [n for n in merges if n["parameters"]["mode"] == "append"]
    assert [n["name"] for n in append_merges] == ["Ingest Merge Response"]

    ingest_merge = append_merges[0]
    # Task 3: a THIRD input — "Decide Action Snapshot" — alongside "Associate Carry
    # Merge"'s output and "Set Review". Phase 70 Plan 05 Task 2 sub-step 2c (D-70-14)
    # adds a FOURTH and FIFTH: one per write gate's refusal lane. Each gets its OWN input
    # rather than sharing the association lane's, because on an armed batch with a mixed
    # verdict the zero-hop refusal would beat the permitted row's multi-hop association
    # to a shared input and the Merge would fire and lock without it (walker-proven,
    # tests/n8n/writeGateShape.test.mjs's armed-mixed case).
    assert ingest_merge["parameters"]["numberInputs"] == 5

    combine_merges = {n["name"]: n for n in merges if n["parameters"]["mode"] == "combine"}
    # Every per-item HTTP hop this lane carries a row across — Task 3's full inventory.
    assert set(combine_merges) == {
        "Update Carry Merge", "Create Carry Merge", "Associate Carry Merge",
        "Verify Email Carry Merge", "Search By Email Carry Merge",
        "Company Domain Carry Merge", "Company Name Carry Merge",
        "Source By Field Broadcast",
    }
    for name, node in combine_merges.items():
        if name == "Source By Field Broadcast":
            assert node["parameters"]["combineBy"] == "combineAll", name
        else:
            assert node["parameters"]["combineBy"] == "combineByPosition", name


def test_splice_carry_merge_after_reroutes_the_http_node_and_fans_the_carry_source():
    http_node = _code_node("HTTP Hop", 300, 0)
    carry_source = _code_node("Carry Source", 100, 0)
    consumer = _code_node("Consumer", 500, 0)
    nodes = [carry_source, http_node, consumer]
    conns = {
        "Carry Source": {"main": [[{"node": "HTTP Hop", "type": "main", "index": 0}]]},
        "HTTP Hop": {"main": [[{"node": "Consumer", "type": "main", "index": 0}]]},
    }
    merge_name = b.splice_carry_merge_after(nodes, conns, "HTTP Hop", "Carry Source",
                                            merge_name="Test Carry Merge")
    assert merge_name == "Test Carry Merge"

    merges = [n for n in nodes if n["type"] == "n8n-nodes-base.merge"]
    assert len(merges) == 1
    assert merges[0]["parameters"]["mode"] == "combine"
    assert merges[0]["parameters"]["combineBy"] == "combineByPosition"

    # HTTP Hop's own edge now targets the merge's input 0, unchanged consumer inherited
    # by the merge's own output, and Carry Source fans an EXTRA edge to input 1 —
    # its original edge into HTTP Hop is untouched.
    assert conns["HTTP Hop"]["main"][0] == [{"node": "Test Carry Merge", "type": "main", "index": 0}]
    assert conns["Test Carry Merge"]["main"][0] == [{"node": "Consumer", "type": "main", "index": 0}]
    assert conns["Carry Source"]["main"][0] == [
        {"node": "HTTP Hop", "type": "main", "index": 0},
        {"node": "Test Carry Merge", "type": "main", "index": 1},
    ]


def test_splice_carry_merge_after_accepts_combine_all_for_a_broadcast():
    http_node = _code_node("Fan Node", 300, 0)
    carry_source = _code_node("Config Source", 100, 0)
    nodes = [carry_source, http_node]
    conns = {"Fan Node": {"main": [[]]}}
    b.splice_carry_merge_after(nodes, conns, "Fan Node", "Config Source",
                               merge_name="Broadcast Merge", combine_by="combineAll")
    merges = [n for n in nodes if n["type"] == "n8n-nodes-base.merge"]
    assert merges[0]["parameters"]["combineBy"] == "combineAll"


def test_splice_carry_merge_after_raises_on_missing_nodes():
    nodes = [_code_node("Only Node")]
    with pytest.raises(ValueError, match="no node named"):
        b.splice_carry_merge_after(nodes, {}, "Missing", "Only Node")
    with pytest.raises(ValueError, match="no carry_source"):
        b.splice_carry_merge_after(nodes, {}, "Only Node", "Missing")


def test_parse_hubspot_event_is_entry_points_and_splice_merge_before_refuses_it():
    """Phase 70 Plan 03 acceptance: `Parse HubSpot Event` (real built graph) converges
    `Execute Workflow Trigger` with the two webhook-path branches — an alternate-entry-
    point convergence per D-70-01's own worked example. Must NOT get a Merge."""
    wf = b.build_enrichment_cloud()
    nodes_by_name = {n["name"]: n for n in wf["nodes"]}
    conns = wf["connections"]
    assert b.classify_convergence(nodes_by_name, conns, "Parse HubSpot Event") == "entry_points"
    with pytest.raises(ValueError, match="(?i)entry points"):
        b.splice_merge_before(wf["nodes"], conns, "Parse HubSpot Event")
