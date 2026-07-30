# tests/test_hubspot_native_operation_validity.py
#
# Phase 16.6 criterion 5 — BUG 10's root cause, turned into a predicate.
#
# BUG 10: the native-search node builder emitted `operation: "search"` for `resource: company`.
# n8n's HubSpot node has no such operation — its company branch is a flat if-chain with no
# matching case and no default/throw — so `responseData` stayed undefined and serialized to
# `null` with `status: success` and no error node. Six nodes were affected and the failure
# was invisible in n8n's own UI.
#
# The fix moved those six to httpRequest. This guard closes the class instead: a native
# HubSpot node may only name an operation that actually exists for its resource. Two of
# these nodes still run `company:update` through the native transport, so the check is not
# hypothetical.
#
# Operation sets transcribed from upstream on 2026-07-29:
#   n8n-io/n8n:packages/nodes-base/nodes/Hubspot/V2/CompanyDescription.ts  (companyOperations)
#   n8n-io/n8n:packages/nodes-base/nodes/Hubspot/V2/ContactDescription.ts  (contactOperations)
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WORKFLOWS = sorted(ROOT.glob("n8n/wf_*_cloud.json"))
NATIVE_TYPE = "n8n-nodes-base.hubspot"

# Note what is NOT here: company has no "search". That single absence is all of BUG 10.
SUPPORTED_OPERATIONS = {
    "company": {
        "create", "delete", "get", "getAll", "getRecentlyCreatedUpdated",
        "searchByDomain", "update",
    },
    # Nor is there a contact "update" or "create" — contacts get `upsert` and nothing else
    # write-shaped. That absence is BUG 18, found by this guard on its first run.
    "contact": {
        "upsert", "delete", "get", "getAll", "getRecentlyCreatedUpdated", "search",
    },
}


def _native_nodes(workflow_path: Path):
    doc = json.loads(workflow_path.read_text())
    for node in doc["nodes"]:
        if node.get("type") == NATIVE_TYPE:
            params = node.get("parameters", {})
            yield node["name"], params.get("resource"), params.get("operation")


@pytest.mark.parametrize("workflow", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_native_hubspot_nodes_only_use_operations_that_exist_for_their_resource(workflow):
    offenders = []
    for name, resource, operation in _native_nodes(workflow):
        supported = SUPPORTED_OPERATIONS.get(resource)
        if supported is None:
            offenders.append(f"{name}: unknown resource {resource!r} — extend this table")
        elif operation not in supported:
            offenders.append(
                f"{name}: {resource}:{operation} does not exist "
                f"(supported: {', '.join(sorted(supported))})"
            )
    assert not offenders, (
        f"{workflow.name} has native HubSpot node(s) naming a non-existent operation. n8n does "
        f"NOT validate this — it falls through its dispatch chain and returns json:null with "
        f"status:success, which is how BUG 10 stayed invisible across six nodes:\n  "
        + "\n  ".join(offenders)
    )


def test_the_guard_rejects_the_two_inputs_it_was_built_from():
    """Non-vacuity, anchored to real defects rather than invented ones: `company:search` is
    what BUG 10's six nodes carried, and `contact:update` is what BUG 18's Dedupe Set Needs
    Review carried. Both must be absent, and the operations that DO exist on those resources
    must be present — a table that over-rejects is wrong in the other direction and would
    condemn contact:search, the one live-proven path."""
    assert "search" not in SUPPORTED_OPERATIONS["company"]      # BUG 10
    assert "update" not in SUPPORTED_OPERATIONS["contact"]      # BUG 18
    assert "search" in SUPPORTED_OPERATIONS["contact"]
    assert "update" in SUPPORTED_OPERATIONS["company"]


def test_the_guard_is_actually_looking_at_something():
    """A parametrized check over zero nodes passes silently. Two native company:update nodes
    exist today (scheduled maintenance SJ-1/SJ-2); if native nodes ever disappear entirely
    this should be re-read rather than left green and empty."""
    found = [
        (wf.name, name, resource, operation)
        for wf in CLOUD_WORKFLOWS
        for name, resource, operation in _native_nodes(wf)
    ]
    assert found, "no native HubSpot nodes found in any cloud workflow — guard is vacuous"
    assert any(r == "company" for _, _, r, _ in found), \
        "no native company node left — re-read 16.6-CRITERION-5-ANSWER.md, which documents " \
        "SJ-1/SJ-2 as the reason this guard covers company operations at all"
