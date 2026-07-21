#!/usr/bin/env python3
"""scripts/sync_hubspot_properties.py

Phase 15 Task 3 — forward property-migration tool (RESEARCH.md §4).

Same idiom as scripts/snapshot_hubspot_schema.py / src/hubspot_client.py: env-gated,
dry-run-by-default, `_has_credentials()` skip-to-exit-0. This is the FIRST schema-mutating
script in the repo, so it uses a stronger TWO-KEY write gate than hubspot_client's single
DRY_RUN gate: a POST is refused unless BOTH DRY_RUN=false AND
ALLOW_HUBSPOT_PROPERTY_WRITES=true.

Usage:
    python scripts/sync_hubspot_properties.py          # dry-run diff (default, zero writes)
    DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true \
        python scripts/sync_hubspot_properties.py      # live create

Idempotent: "missing" is always re-derived from a fresh GET, never from local state, so a
re-run against a matching portal is a pure no-op, and a re-run after a mid-batch network
blip picks up exactly where it left off.

DESIGN NOTE (per-property creates, not a single batch/create call): HubSpot's CRM v3
`batch/create` endpoint's partial-failure semantics are undocumented (RESEARCH.md §2.2/§9)
— whether one invalid property in a 33-property batch fails the WHOLE call or only that
item is not something this migration should guess at, because the undo manifest's
correctness (recording ONLY confirmed creates) is safety-critical. This script instead
issues one `POST /crm/v3/properties/{objectType}` per property, giving each an
unambiguous, individually-confirmed status code. At 33 properties total this costs 33
extra HTTP calls against a 190/10s rate limit, on a one-time operator-run migration —
free at this scale.
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

MANIFEST_DIR = ROOT / ".planning" / "phases" / "15-hubspot-property-migration"
CONFIG_PATH = ROOT / "config" / "hubspot_properties.yaml"

# Same portal guard as scripts/snapshot_hubspot_schema.py — asserted before ANY call.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow


def load_desired_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def _options_values(options) -> set:
    return {str(o.get("value")) for o in (options or [])}


def compute_property_diff(desired_properties: list, actual_properties: list) -> dict:
    """desired - actual = create-list; matching-name-mismatching-shape = drift (report
    only, never auto-fixed). A `hubspotDefined` actual property is NEVER proposed for
    either list, even if the config named a collision (belt-and-braces)."""
    actual_by_name = {p["name"]: p for p in actual_properties}
    create, drift = [], []
    for desired in desired_properties:
        name = desired["name"]
        actual = actual_by_name.get(name)
        if actual is None:
            create.append(desired)
            continue
        if actual.get("hubspotDefined"):
            continue
        mismatch = (
            actual.get("type") != desired.get("type")
            or actual.get("fieldType") != desired.get("fieldType")
            or _options_values(actual.get("options")) != _options_values(desired.get("options"))
        )
        if mismatch:
            drift.append({"name": name, "desired": desired, "actual": actual})
    return {"create": create, "drift": drift}


def compute_group_diff(desired_groups: list, actual_groups: list) -> list:
    actual_names = {g["name"] for g in actual_groups}
    return [g for g in desired_groups if g["name"] not in actual_names]


def _get_live_properties(object_type: str) -> list:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def _get_live_groups(object_type: str) -> list:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}/groups", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def _create_group_live(object_type: str, group: dict):
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    body = {"name": group["name"], "label": group["label"], "displayOrder": -1}
    r = requests.post(f"{BASE_URL}/crm/v3/properties/{object_type}/groups", headers=hs_headers(),
                       json=body, timeout=30)
    return r.status_code, body


def _create_property_live(object_type: str, prop: dict):
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    body = dict(prop)  # name/label/type/fieldType/groupName/options — the create-property shape
    r = requests.post(f"{BASE_URL}/crm/v3/properties/{object_type}", headers=hs_headers(),
                       json=body, timeout=30)
    return r.status_code, body


def manifest_path(run_id: str, directory: Path = MANIFEST_DIR) -> Path:
    return directory / f"undo-manifest-{run_id}.json"


def append_manifest_entries(run_id: str, entries: list, directory: Path = MANIFEST_DIR) -> Path:
    """Append confirmed-created entries to the undo manifest. Called ONLY after a
    confirmed 201 for each entry — never speculatively — so the manifest never claims
    something exists that doesn't."""
    directory.mkdir(parents=True, exist_ok=True)
    path = manifest_path(run_id, directory)
    existing = json.loads(path.read_text()) if path.exists() else []
    existing.extend(entries)
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
    return path


def _print_report(object_type: str, group_create: list, prop_diff: dict) -> None:
    print(f"\n=== {object_type} ===")
    print(f"Groups to create: {[g['name'] for g in group_create]}")
    print(f"Properties to create ({len(prop_diff['create'])}): "
          f"{[p['name'] for p in prop_diff['create']]}")
    if prop_diff["drift"]:
        print(f"DRIFT (report only, never auto-fixed): "
              f"{[d['name'] for d in prop_diff['drift']]}")


def sync_object_type(object_type: str, desired: dict, run_id: str, live_writes: bool,
                      manifest_dir: Path = MANIFEST_DIR) -> None:
    actual_groups = _get_live_groups(object_type)
    actual_properties = _get_live_properties(object_type)

    group_create = compute_group_diff(desired["groups"], actual_groups)
    prop_diff = compute_property_diff(desired["properties"], actual_properties)

    _print_report(object_type, group_create, prop_diff)

    if not live_writes:
        return

    manifest_entries = []

    for group in group_create:
        status, body = _create_group_live(object_type, group)
        if status == 201:
            manifest_entries.append({"kind": "group", "object_type": object_type,
                                      "name": group["name"], "request_body": body})
            print(f"created group {object_type}/{group['name']} (201)")
        else:
            print(f"FAILED to create group {object_type}/{group['name']} ({status}) — "
                  "not recorded in undo manifest")

    for prop in prop_diff["create"]:
        status, body = _create_property_live(object_type, prop)
        if status == 201:
            manifest_entries.append({"kind": "property", "object_type": object_type,
                                      "name": prop["name"], "group_name": prop.get("groupName"),
                                      "request_body": body})
            print(f"created property {object_type}/{prop['name']} (201)")
        else:
            print(f"FAILED to create property {object_type}/{prop['name']} ({status}) — "
                  "not recorded in undo manifest")

    if manifest_entries:
        path = append_manifest_entries(run_id, manifest_entries, directory=manifest_dir)
        print(f"undo manifest: {path}")

    # Post-write confirmation: re-GET and confirm every manifested name now exists.
    fresh_props = {p["name"] for p in _get_live_properties(object_type)}
    fresh_groups = {g["name"] for g in _get_live_groups(object_type)}
    for entry in manifest_entries:
        if entry["kind"] == "property":
            assert entry["name"] in fresh_props, f"post-write confirmation FAILED for {entry['name']}"
        else:
            assert entry["name"] in fresh_groups, f"post-write confirmation FAILED for group {entry['name']}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this sync.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    desired = load_desired_config()
    live_writes = _writes_allowed()
    if not live_writes:
        print("DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_HUBSPOT_PROPERTY_WRITES=true to create.")

    run_id = str(uuid.uuid4())
    for object_type in ("companies", "contacts"):
        sync_object_type(object_type, desired[object_type], run_id, live_writes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
