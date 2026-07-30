#!/usr/bin/env python3
"""scripts/canary_record_snapshot.py

Phase 22 Plan 01 Task 1 — read-only HubSpot record snapshot/compare tool, and the
neighbour-untouched verifier the armed canary (Plan 04) reuses. Two modes:

  snapshot  GET the target + neighbour records live, print a research-gate prediction
            for the target, and write ONE JSON artifact under this phase's snapshots/.
  compare   Re-GET the same records — using the snapshot's OWN recorded property list,
            never a freshly recomputed one, so a config change between snapshot and
            compare can't silently change what's being compared — and report a target
            diff + a neighbour verdict (`neighbors_changed`). Exits non-zero only when a
            neighbour changed; a changed target is the expected outcome of an armed run,
            not a failure.

Read-only throughout: `src/hubspot_client.get_record` is the ONLY HubSpot function this
module may call. No PATCH/POST path exists here by design (T-22-01) — a guard test in
tests/test_canary_record_snapshot.py asserts this module's own source contains no write
call.

Same idiom as scripts/inventory_org_type_values.py / scripts/snapshot_hubspot_schema.py:
`_has_credentials()` skip-to-exit-0, the portal guard refusing before any call, "a
finding exits non-zero, it never crashes."

Usage:
    python scripts/canary_record_snapshot.py
    python scripts/canary_record_snapshot.py snapshot --label pre-canary --json
    python scripts/canary_record_snapshot.py compare --snapshot PATH
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

from src import taxonomy  # noqa: E402
from src.hubspot_client import get_record  # noqa: E402
from snapshot_hubspot_schema import KNOWN_COMPANY_CUSTOM_PROPS  # noqa: E402

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")
PROPERTIES_CONFIG_PATH = ROOT / "config" / "hubspot_properties.yaml"
SNAPSHOT_DIR = ROOT / ".planning" / "phases" / "22-armed-e2e-enrichment-canary" / "snapshots"

# Phase 19 runbook precedent (contact `201`, company `9604614548`) — the standing test
# fixtures used throughout Milestones 3-5 for read-only neighbour spot-checks, defaulted
# here so the operator can run this with no arguments.
DEFAULT_TARGET_OBJECT_TYPE = "companies"
DEFAULT_TARGET_ID = "9604614548"
DEFAULT_NEIGHBOR_COMPANY_IDS: list = []
DEFAULT_NEIGHBOR_CONTACT_IDS = ["201"]

# HubSpot's modification-timestamp PROPERTY name is not assumed (this is exactly the kind
# of undocumented-per-portal detail Assumption A1 warns against for the executions API) —
# request both candidates and record whichever the portal actually returns for that
# object's properties.
TIMESTAMP_PROPERTY_CANDIDATES = ("hs_lastmodifieddate", "lastmodifieddate")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _declared_properties(object_type: str) -> list:
    """config/hubspot_properties.yaml's declared property names for one object type,
    plus — companies only — the pre-existing ICP fields (lv_org_type,
    lv_produces_content, ...) that predate that config. Reused verbatim from
    scripts/snapshot_hubspot_schema.py's own drift-check constant, never re-typed."""
    config = yaml.safe_load(PROPERTIES_CONFIG_PATH.read_text())
    names = {p["name"] for p in config.get(object_type, {}).get("properties", [])}
    if object_type == "companies":
        names |= KNOWN_COMPANY_CUSTOM_PROPS
    return sorted(names)


def evidence_gated_org_types() -> list:
    """The live gate's evidence-gated vocabulary, imported from src/taxonomy.py — never
    re-typed as a literal list here (must_haves key_link)."""
    return list(taxonomy.EVIDENCE_GATED_ORG_TYPES)


def predict_research_gate(existing_record: dict) -> dict:
    """Mirrors n8n/wf_enrichment_cloud.json's company `Research Trigger Gate` node's
    needsResearch(existingRecord) verbatim (RT-3):

        orgUnresolved = !orgType || orgType === "" || orgType === "unknown"
                         || EVIDENCE_GATED_ORG_TYPES.indexOf(orgType) !== -1
        contentBlank = pc === undefined || pc === null || pc === ""
        return orgUnresolved || contentBlank

    Kept as its own pure function so tests can drive its truth table directly."""
    org_type = existing_record.get("lv_org_type")
    org_type_unresolved = org_type in (None, "", "unknown")
    org_type_evidence_gated = org_type in taxonomy.EVIDENCE_GATED_ORG_TYPES
    content = existing_record.get("lv_produces_content")
    content_blank = content in (None, "")

    will_fire = org_type_unresolved or org_type_evidence_gated or content_blank

    if org_type_unresolved:
        reason = f"lv_org_type is unresolved ({org_type!r})"
    elif org_type_evidence_gated:
        reason = f"lv_org_type {org_type!r} is evidence-gated (requires evidence)"
    elif content_blank:
        reason = f"lv_produces_content is blank ({content!r})"
    else:
        reason = f"lv_org_type {org_type!r} is resolved and lv_produces_content is present"

    return {
        "research_gate_will_fire": will_fire,
        "lv_org_type": org_type,
        "lv_produces_content": content,
        "reason": reason,
    }


def _capture_record(object_type: str, record_id: str) -> dict:
    requested = sorted(set(_declared_properties(object_type)) | set(TIMESTAMP_PROPERTY_CANDIDATES))
    response = get_record(object_type, record_id, requested)
    props = response.get("properties", {}) or {}
    modified_property = next(
        (name for name in TIMESTAMP_PROPERTY_CANDIDATES if props.get(name) not in (None, "")),
        None,
    )
    return {
        "object_type": object_type,
        "id": record_id,
        "requested_properties": requested,
        "properties": props,
        "modified_property": modified_property,
        "modified_value": props.get(modified_property) if modified_property else None,
    }


def build_snapshot(label: str, target_object_type: str, target_id: str,
                    neighbor_company_ids: list, neighbor_contact_ids: list) -> dict:
    target = _capture_record(target_object_type, target_id)
    neighbors = [_capture_record("companies", cid) for cid in neighbor_company_ids]
    neighbors += [_capture_record("contacts", cid) for cid in neighbor_contact_ids]
    prediction = predict_research_gate(target["properties"]) if target_object_type == "companies" else None
    return {
        "label": label,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "neighbors": neighbors,
        "prediction": prediction,
    }


def _write_snapshot(snapshot: dict, directory: Path = SNAPSHOT_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{snapshot['label']}-{ts}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str) + "\n")
    return path


def _record_diff(before: dict, after_properties: dict) -> dict:
    """Field-by-field diff over the snapshot's OWN recorded requested_properties list."""
    changed = {}
    for prop in before["requested_properties"]:
        b = before["properties"].get(prop)
        a = after_properties.get(prop)
        if b != a:
            changed[prop] = {"before": b, "after": a}
    return changed


def compare_snapshot(snapshot: dict) -> dict:
    target_before = snapshot["target"]
    target_after = get_record(
        target_before["object_type"], target_before["id"], target_before["requested_properties"]
    ).get("properties", {}) or {}
    target_diff = _record_diff(target_before, target_after)

    neighbor_reports = []
    for neighbor_before in snapshot["neighbors"]:
        after = get_record(
            neighbor_before["object_type"], neighbor_before["id"], neighbor_before["requested_properties"]
        ).get("properties", {}) or {}
        diff = _record_diff(neighbor_before, after)
        neighbor_reports.append({
            "object_type": neighbor_before["object_type"],
            "id": neighbor_before["id"],
            "changed": bool(diff),
            "changed_fields": diff,
        })

    neighbors_changed = sum(1 for n in neighbor_reports if n["changed"])
    return {
        "target": {
            "object_type": target_before["object_type"],
            "id": target_before["id"],
            "changed_fields": target_diff,
        },
        "neighbors": neighbor_reports,
        "neighbors_changed": neighbors_changed,
    }


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="snapshot", choices=["snapshot", "compare"])
    parser.add_argument("--label", default="pre-canary")
    parser.add_argument("--target-object-type", default=DEFAULT_TARGET_OBJECT_TYPE)
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--neighbor-company-id", action="append", default=None,
                         help="repeatable; defaults to none")
    parser.add_argument("--neighbor-contact-id", action="append", default=None,
                         help="repeatable; defaults to the standing contact 201 fixture")
    parser.add_argument("--snapshot", default=None, help="path to a snapshot JSON (compare mode)")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this tool.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if args.mode == "compare":
        if not args.snapshot:
            print("REFUSED: compare mode requires --snapshot PATH.")
            return 1
        snapshot = json.loads(Path(args.snapshot).read_text())
        result = compare_snapshot(snapshot)
        print(f"target {result['target']['object_type']}/{result['target']['id']} "
              f"changed fields: {sorted(result['target']['changed_fields'])}")
        print(f"neighbors_changed: {result['neighbors_changed']}")
        for n in result["neighbors"]:
            tag = "CHANGED" if n["changed"] else "unchanged"
            print(f"neighbor {n['object_type']}/{n['id']}: {tag} {sorted(n['changed_fields'])}")
        if args.json:
            print(json.dumps(result, default=str))
        return 1 if result["neighbors_changed"] else 0

    neighbor_company_ids = (
        args.neighbor_company_id if args.neighbor_company_id is not None else DEFAULT_NEIGHBOR_COMPANY_IDS
    )
    neighbor_contact_ids = (
        args.neighbor_contact_id if args.neighbor_contact_id is not None else DEFAULT_NEIGHBOR_CONTACT_IDS
    )
    snapshot = build_snapshot(args.label, args.target_object_type, args.target_id,
                               neighbor_company_ids, neighbor_contact_ids)
    path = _write_snapshot(snapshot, directory=SNAPSHOT_DIR)
    print(f"wrote {path}")
    prediction = snapshot["prediction"]
    if prediction is not None:
        print(f"research_gate_will_fire: {str(prediction['research_gate_will_fire']).lower()}")
        print(f"lv_org_type={prediction['lv_org_type']!r} lv_produces_content={prediction['lv_produces_content']!r}")
        print(f"reason: {prediction['reason']}")
    if args.json:
        print(json.dumps({"path": str(path), "prediction": prediction}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
