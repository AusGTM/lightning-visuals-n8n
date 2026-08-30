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
    # Phase 61 Plan 06 Task 5: wf_enrichment_cloud.json is no longer this test's example —
    # it now carries its OWN executeWorkflow node ("Dispatch Self", the substrate-3
    # self-reference; see test_self_reference_resolves_via_its_own_live_name below).
    # wf_contact_ingest_cloud.json carries none and is the re-anchored example.
    wf = json.loads((ROOT / "n8n" / "wf_contact_ingest_cloud.json").read_text())
    assert not any(n["type"] == "n8n-nodes-base.executeWorkflow" for n in wf["nodes"])
    out = rebind_subworkflow_refs(wf, {})  # empty live map must not matter here
    assert json.dumps(out, sort_keys=True) == json.dumps(wf, sort_keys=True)


def test_self_reference_resolves_via_its_own_live_name():
    """Phase 61 Plan 06 Task 5 (T-61-25, substrate-3 scale-up). wf_enrichment_cloud.json's
    "Dispatch Self" node references the workflow's OWN name/id
    ("LVenrichmentCloud01"/"LV Enrichment (Cloud template)") — self-reference needs no
    special-casing in rebind_subworkflow_refs because the workflow already exists live
    (61-05's substrate-1 deploy): its own name already resolves to its own live id via the
    SAME fresh live name->id map every other executeWorkflow node uses."""
    wf = json.loads((ROOT / "n8n" / "wf_enrichment_cloud.json").read_text())
    node = next(n for n in wf["nodes"] if n["name"] == "Dispatch Self")
    assert node["type"] == "n8n-nodes-base.executeWorkflow"
    assert node["parameters"]["workflowId"]["value"] == "LVenrichmentCloud01", \
        "the committed artifact no longer bakes the local self-reference id — re-anchor this test"
    assert node["parameters"]["workflowId"]["cachedResultName"] == "LV Enrichment (Cloud template)"
    assert node["parameters"]["options"]["waitForSubWorkflow"] is False, \
        "self-dispatch must be detached (P-13's proven shape) — a waiting self-reference " \
        "would deadlock the parent on its own child"

    out = rebind_subworkflow_refs(wf, LIVE)
    rebound = next(n for n in out["nodes"] if n["name"] == "Dispatch Self")
    assert rebound["parameters"]["workflowId"]["value"] == "srv-abc123", (
        "a workflow's own name must resolve through the SAME live map used for every "
        "other reference — no self-reference special-casing"
    )
