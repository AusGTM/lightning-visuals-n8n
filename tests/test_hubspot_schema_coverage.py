# tests/test_hubspot_schema_coverage.py
#
# Phase 16.9 SC-2 — the schema-coverage guard.
#
# BUG 14: `lv_enrichment_status` was referenced by the companies write path, was declared
# in config/hubspot_properties.yaml, and did not exist in the portal — because no migration
# had ever run for it. HubSpot rejected the PATCH live with PROPERTY_DOESNT_EXIST, on the
# first execution that ever reached a company write. Nothing offline could have caught it.
#
# So the oracle here is deliberately NOT config/hubspot_properties.yaml. Declaring a
# property is not the same as the portal having it, and conflating the two is the bug.
# The oracle is what the portal actually held:
#
#   portal snapshot (scripts/snapshot_hubspot_schema.py output, committed under Phase 15)
#   UNION the properties recorded as CREATED by a migration undo-manifest since
#
# A workflow may reference a property only if it is in that union. A property that is
# merely declared, or newly invented in a Code node, fails here rather than live.
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".planning" / "phases" / "15-hubspot-property-migration" / "baseline"
MANIFEST_DIR = ROOT / ".planning" / "phases" / "15-hubspot-property-migration"
CLOUD_WORKFLOWS = sorted(ROOT.glob("n8n/wf_*_cloud.json"))

# The project's own property namespaces. Canonical HubSpot properties (domain, jobtitle,
# hs_object_id...) are portal built-ins and are not what drifts; every property this
# project has ever had to create for itself carries one of these prefixes.
PROPERTY_RE = re.compile(r"\b(lv_[a-z0-9_]+|enrichment_[a-z0-9_]+)\b")

# Sticky notes are documentation pinned to the canvas, not executable node parameters.
# Excluding them is not a convenience: wf_scheduled_maintenance_cloud.json's note says in
# prose that SJ-1/2/3 never reference `lv_icp_scored_at`, and scanning it would report the
# property as referenced by the very text asserting it is not.
NON_EXECUTABLE_NODE_TYPES = {"n8n-nodes-base.stickyNote"}


def _portal_snapshot_properties() -> set[str]:
    """Every property name the portal held at the last committed snapshot."""
    names: set[str] = set()
    snaps = sorted(BASELINE.glob("portal-schema-*-post-canary.json"))
    assert snaps, f"no portal schema snapshot under {BASELINE}"
    for snap in snaps:
        doc = json.loads(snap.read_text())
        results = doc.get("results") or doc.get("body", {}).get("results") or []
        assert results, f"{snap.name} has no results[] — snapshot shape changed"
        names |= {p["name"] for p in results}
    return names


def _migration_created_properties() -> set[str]:
    """Properties a recorded migration created AFTER the snapshot was taken.

    An undo manifest is the audit trail of a `sync_hubspot_properties.py` run: each entry
    is something that run actually created in the portal. That is evidence of existence in
    a way config/hubspot_properties.yaml is not."""
    names: set[str] = set()
    for manifest in sorted(MANIFEST_DIR.glob("undo-manifest-*.json")):
        for entry in json.loads(manifest.read_text()):
            if entry.get("kind") == "property" and entry.get("name"):
                names.add(entry["name"])
    return names


def _referenced_properties(workflow_path: Path) -> dict[str, list[str]]:
    """Project-namespace property names referenced by executable nodes -> node names."""
    doc = json.loads(workflow_path.read_text())
    refs: dict[str, list[str]] = {}
    for node in doc["nodes"]:
        if node.get("type") in NON_EXECUTABLE_NODE_TYPES:
            continue
        blob = json.dumps(node.get("parameters", {}))
        for name in set(PROPERTY_RE.findall(blob)):
            refs.setdefault(name, []).append(node["name"])
    return refs


@pytest.fixture(scope="module")
def portal_properties() -> set[str]:
    return _portal_snapshot_properties() | _migration_created_properties()


@pytest.mark.parametrize("workflow", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_every_property_a_cloud_workflow_references_exists_in_the_portal(workflow, portal_properties):
    """SC-2. A cloud workflow may only name a property the portal is known to have."""
    missing = {
        name: nodes
        for name, nodes in _referenced_properties(workflow).items()
        if name not in portal_properties
    }
    assert not missing, (
        f"{workflow.name} references {len(missing)} property name(s) that are in neither the "
        f"portal snapshot nor any migration manifest — this is BUG 14's shape, and it fails "
        f"live with PROPERTY_DOESNT_EXIST on the first execution that reaches the write:\n"
        + "\n".join(f"  {n} -> referenced by {', '.join(sorted(ns))}" for n, ns in sorted(missing.items()))
        + "\nIf the property is legitimately new, run the Phase 15 migration so a manifest "
          "records its creation; declaring it in config/hubspot_properties.yaml is not enough."
    )


def test_the_guard_is_not_vacuous_because_it_catches_an_injected_unknown_property(tmp_path, portal_properties):
    """The predicate above passes trivially if the extractor finds nothing. Prove it bites:
    inject BUG 14's exact shape — a Code node naming a property no portal has — and require
    the extractor to surface it, attributed to the node that introduced it."""
    doc = json.loads(CLOUD_WORKFLOWS[0].read_text())
    doc["nodes"].append({
        "parameters": {"jsCode": "return [{json:{properties:{lv_totally_invented_field:'x'}}}];"},
        "id": "injected", "name": "Injected Offender",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [0, 0],
    })
    injected = tmp_path / "injected.json"
    injected.write_text(json.dumps(doc))

    refs = _referenced_properties(injected)
    assert "lv_totally_invented_field" in refs
    assert refs["lv_totally_invented_field"] == ["Injected Offender"]
    assert "lv_totally_invented_field" not in portal_properties


def test_sticky_note_prose_is_not_mistaken_for_a_property_reference(tmp_path):
    """The other half of non-vacuity: the exclusion must actually exclude. A note naming a
    property must not register as a reference, or the guard reports documentation as drift
    (which is precisely what it did before the exclusion, on `lv_icp_scored_at`)."""
    doc = {"nodes": [{
        "parameters": {"content": "SJ-1/2/3 never reference lv_icp_scored_at."},
        "id": "note", "name": "Sticky Note",
        "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [0, 0],
    }], "connections": {}}
    path = tmp_path / "note.json"
    path.write_text(json.dumps(doc))
    assert _referenced_properties(path) == {}


def test_declaring_a_property_in_config_alone_does_not_satisfy_the_guard():
    """The design decision, asserted rather than left to a comment: the oracle must not be
    config/hubspot_properties.yaml. BUG 14's property was declared there the whole time and
    still did not exist in the portal, so a config-based guard would have passed while the
    live PATCH 400'd."""
    import yaml

    declared = set()
    cfg = yaml.safe_load((ROOT / "config" / "hubspot_properties.yaml").read_text())
    for object_type in ("companies", "contacts"):
        for prop in (cfg.get(object_type) or {}).get("properties", []) or []:
            if prop.get("name"):
                declared.add(prop["name"])
    assert declared, "config parse found no properties — shape changed, guard rationale untested"

    snapshot_only = _portal_snapshot_properties()
    assert declared - snapshot_only, (
        "every declared property is already in the portal snapshot, so this repo currently "
        "cannot distinguish a config-based oracle from a portal-based one — but the "
        "distinction is the whole point of SC-2. Re-check that the oracle is still the "
        "snapshot plus migration manifests, never the config."
    )


def test_the_guard_would_have_caught_bug_14():
    """Historical bite, not a hypothetical. BUG 14 was `lv_enrichment_status` referenced by
    the companies write path while the portal lacked it; migration 73c5342c created it and
    is why the guard passes today. Reconstruct the pre-migration oracle by dropping that one
    manifest — the property must go missing. If it does not, the guard is passing for some
    reason other than the fix, and it would not have caught the bug it exists for."""
    pre_bug14 = _portal_snapshot_properties()
    for manifest in sorted(MANIFEST_DIR.glob("undo-manifest-*.json")):
        if "73c5342c" in manifest.name:
            continue
        for entry in json.loads(manifest.read_text()):
            if entry.get("kind") == "property" and entry.get("name"):
                pre_bug14.add(entry["name"])

    enrichment_wf = next(p for p in CLOUD_WORKFLOWS if p.name == "wf_enrichment_cloud.json")
    referenced = _referenced_properties(enrichment_wf)
    assert "lv_enrichment_status" in referenced, \
        "the enrichment workflow no longer references BUG 14's property — re-anchor this test"
    assert "lv_enrichment_status" not in pre_bug14, \
        "BUG 14's property looks present even without its migration — oracle is too permissive"
