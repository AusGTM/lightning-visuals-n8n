# tests/test_subworkflow_ref_rebinding.py
#
# BUG 20 — the first-ever activation attempt of LV Scheduled Maintenance 400'd live:
#   "Cannot publish workflow: Node "SJ-3 Dispatch To Enrichment" references workflow
#    LVenrichmentCloud01 which is not published."
# The builder bakes executeWorkflow nodes with the LOCAL template id; n8n assigns its own
# server-side id on create and the deploy matches by NAME, so the baked id never exists on
# the server. rebind_subworkflow_refs() rewrites the id from the node's cachedResultName
# (the workflow NAME — the only identifier stable across both sides) via a fresh live map.
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_n8n_workflows import rebind_subworkflow_refs  # noqa: E402


def _sched_maintenance() -> dict:
    return json.loads((ROOT / "n8n" / "wf_scheduled_maintenance_cloud.json").read_text())


LIVE = {"LV Enrichment (Cloud template)": {"id": "srv-abc123", "name": "LV Enrichment (Cloud template)"}}


def test_rewrites_the_baked_local_id_to_the_live_server_id():
    wf = _sched_maintenance()
    node = next(n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.executeWorkflow")
    assert node["parameters"]["workflowId"]["value"] == "LVenrichmentCloud01", \
        "the committed artifact no longer bakes the local id — re-anchor this test"

    out = rebind_subworkflow_refs(wf, LIVE)
    rebound = next(n for n in out["nodes"] if n["type"] == "n8n-nodes-base.executeWorkflow")
    assert rebound["parameters"]["workflowId"]["value"] == "srv-abc123"
    # cachedResultName is the lookup key and must survive for the next deploy's lookup.
    assert rebound["parameters"]["workflowId"]["cachedResultName"] == "LV Enrichment (Cloud template)"


def test_is_pure_and_does_not_mutate_its_input():
    wf = _sched_maintenance()
    before = json.dumps(wf, sort_keys=True)
    rebind_subworkflow_refs(wf, LIVE)
    assert json.dumps(wf, sort_keys=True) == before


def test_fails_closed_when_the_referenced_workflow_is_not_live():
    with pytest.raises(ValueError, match="does not exist on the instance yet"):
        rebind_subworkflow_refs(_sched_maintenance(), {})


def test_workflows_without_executeworkflow_nodes_pass_through_unchanged():
    # Phase 61 Plan 06 Task 5 had re-anchored this away from wf_enrichment_cloud.json,
    # which then carried its own self-referencing "Dispatch Self" node. Phase 70 Plan 13
    # (D-70-24) deleted that node, so the enrichment workflow carries none again — and it
    # is the more valuable example, because it is the one that regressed.
    wf = json.loads((ROOT / "n8n" / "wf_enrichment_cloud.json").read_text())
    assert not any(n["type"] == "n8n-nodes-base.executeWorkflow" for n in wf["nodes"])
    out = rebind_subworkflow_refs(wf, {})  # empty live map must not matter here
    assert json.dumps(out, sort_keys=True) == json.dumps(wf, sort_keys=True)


def test_no_committed_workflow_contains_a_self_referencing_execute_workflow_node():
    """Phase 70 Plan 13 Task 1/2 (G-70-5, D-70-24/D-70-26a). This test's subject used to be
    wf_enrichment_cloud.json's "Dispatch Self" node and how `rebind_subworkflow_refs`
    resolved its self-reference. That node looped live on 2026-09-10 — 135 child executions
    in six minutes from four disarmed sends (12211-12348), by a mechanism this repo never
    isolated — and was deleted rather than guarded, because only the ABSENCE of a
    self-referencing Execute Workflow node makes recursion impossible on this engine.

    So the assertion inverts: no committed workflow may contain one at all. Generation
    itself refuses one (`build_cloud_workflows.assert_no_self_dispatch`); this is the
    matching check over what is actually on disk.
    """
    for path in sorted((ROOT / "n8n").glob("wf_*.json")):
        wf = json.loads(path.read_text())
        for node in wf["nodes"]:
            if node["type"] != "n8n-nodes-base.executeWorkflow":
                continue
            ref = node["parameters"]["workflowId"]
            assert ref["value"] != wf["id"], (
                f"{path.name}: {node['name']!r} dispatches to its own id — D-70-24")
            assert ref["cachedResultName"] != wf["name"], (
                f"{path.name}: {node['name']!r} dispatches to its own name — D-70-24")


def test_the_only_committed_execute_workflow_node_is_sj3s_cross_workflow_dispatch():
    """The one legitimate dispatch, and the one `rebind_subworkflow_refs` exists for."""
    found = []
    for path in sorted((ROOT / "n8n").glob("wf_*.json")):
        wf = json.loads(path.read_text())
        for node in wf["nodes"]:
            if node["type"] == "n8n-nodes-base.executeWorkflow":
                found.append((path.name, node["name"]))
    assert found == [("wf_scheduled_maintenance_cloud.json", "SJ-3 Dispatch To Enrichment")]
