# tests/test_write_gate_coverage.py
#
# BUG 15 — `_writeSafetyAllows()` and the ALLOW_HUBSPOT_* constants existed ONLY in
# wf_enrichment_cloud.json. wf_scheduled_maintenance_cloud.json and
# wf_contact_ingest_cloud.json carried SIX write nodes between them with no allowlist
# check at all: SJ-1/SJ-2 Set Requested, Dedupe Set Needs Review, Review Apply Update,
# and contact ingest's HubSpot Update / HubSpot Create.
#
# Both workflows are INACTIVE, so there was never live exposure — but activating either
# would have written to HubSpot with nothing bounding the blast radius, which is exactly
# the guarantee the write-path canary was run to establish. Found 2026-07-29 while
# auditing coverage after that canary.
#
# The property this file defends is structural and applies to workflows nobody has run:
# EVERY write node in EVERY cloud workflow sits directly behind a gate that calls
# _writeSafetyAllows. A write node added later cannot quietly skip one.
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WORKFLOWS = sorted((ROOT / "n8n").glob("wf_*_cloud.json"))


def _load(path):
    return json.loads(path.read_text())


def _is_write_node(node):
    """A node that can mutate a HubSpot record: either the native node doing
    create/update, or an httpRequest issuing a mutating method at a non-search CRM URL."""
    params = node.get("parameters", {})
    if node.get("type") == "n8n-nodes-base.hubspot":
        return params.get("operation") in ("create", "update")
    if node.get("type") == "n8n-nodes-base.httpRequest":
        url = str(params.get("url", ""))
        method = str(params.get("method", "")).upper()
        return ("hubapi.com" in url and "/search" not in url
                and method in ("POST", "PATCH", "PUT"))
    return False


def _feeders(wf, name):
    return [src for src, spec in wf["connections"].items()
            if any(c["node"] == name
                   for outputs in spec.get("main", []) for c in (outputs or []))]


def _all_paths_cross_a_gate(wf, write_name, max_hops=6):
    """True when every inbound path to `write_name`, walked up to `max_hops` back, passes
    through a node whose jsCode calls _writeSafetyAllows."""
    frontier = [(f, 0) for f in _feeders(wf, write_name)]
    while frontier:
        name, depth = frontier.pop()
        if "_writeSafetyAllows" in _js(wf, name):
            continue  # this path is gated
        if depth >= max_hops:
            return False
        parents = _feeders(wf, name)
        if not parents:
            return False  # reached a trigger without crossing a gate
        frontier.extend((p, depth + 1) for p in parents)
    return True


def _js(wf, name):
    node = next((n for n in wf["nodes"] if n["name"] == name), None)
    return (node or {}).get("parameters", {}).get("jsCode", "") or ""


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_every_write_node_sits_behind_a_write_safety_gate(path):
    wf = _load(path)
    writes = [n for n in wf["nodes"] if _is_write_node(n)]
    assert writes, f"{path.name}: no write node found — this guard would be vacuous"
    ungated = []
    for node in writes:
        feeders = _feeders(wf, node["name"])
        if not feeders:
            continue  # unreachable node cannot write
        # Walk upstream: the enrichment workflow gates INSIDE `Decide Action` (which sets
        # action="write_blocked" so the routing IF cannot match), while the other two use
        # a spliced gate node directly in front. Both are valid — what matters is that no
        # path from a trigger reaches the write without crossing _writeSafetyAllows.
        if not _all_paths_cross_a_gate(wf, node["name"]):
            ungated.append((node["name"], feeders))
    assert not ungated, (
        f"{path.name}: write node(s) reachable without passing a write-safety gate — "
        f"activating this workflow would write to HubSpot with no allowlist bounding it: "
        f"{ungated}"
    )


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_every_cloud_workflow_with_a_write_declares_the_safety_constants(path):
    """The gate is only meaningful if the constants it reads are actually declared in the
    same workflow — a gate whose ALLOW_HUBSPOT_RECORD_WRITES is undefined would throw
    rather than deny, which is a different failure but not a safe one."""
    wf = _load(path)
    if not any(_is_write_node(n) for n in wf["nodes"]):
        pytest.skip("no write nodes in this workflow")
    blob = json.dumps(wf)
    for const in ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                  "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"):
        assert f"const {const} = " in blob, f"{path.name}: {const} is never declared"


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_committed_write_safety_constants_are_all_disabled(path):
    """The committed artifact must never ship armed, in ANY workflow — the same invariant
    tests/test_enabled_build_invariants.py holds for the enrichment workflow, now that two
    more workflows carry these constants."""
    import re
    blob = json.dumps(_load(path))
    for const, disabled in (("ALLOW_HUBSPOT_RECORD_WRITES", '\\"false\\"'),
                            ("ALLOW_HUBSPOT_CREATE", '\\"false\\"'),
                            ("TEST_RECORD_IDS", '\\"\\"'),
                            ("TEST_RECORD_DOMAINS", '\\"\\"')):
        for literal in re.findall(rf"const {const} = ([^;]+);", blob):
            assert literal == disabled, (
                f"{path.name}: {const} is committed as {literal!r}, not {disabled!r}")
