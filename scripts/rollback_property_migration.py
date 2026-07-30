#!/usr/bin/env python3
"""scripts/rollback_property_migration.py

Phase 15 Task 7 — the reverse-direction property migration tool (RESEARCH.md §3.4).

Same idiom as scripts/sync_hubspot_properties.py: env-gated, dry-run-by-default,
`_has_credentials()` skip-to-exit-0. Refuses to run at all without BOTH the undo manifest
(Task 3's output) and a baseline snapshot (Task 1's output) — a manifest-less run has
nothing safe to undo, and guessing from a schema diff alone risks archiving a property
another workflow created independently in the interim.

Usage:
    python scripts/rollback_property_migration.py [--live] [--manifest PATH] [--baseline PATH]

Behavior:
    1. Load the undo manifest + baseline snapshot(s). REFUSE (hard error, non-zero, no
       calls) if EITHER is missing.
    2. For each manifested property, confirm live GET still shows it exists and is NOT
       `hubspotDefined` (belt-and-braces — never touch a native property even if a
       manifest were somehow corrupted to list one).
    3. REFUSE to archive anything NOT present in the manifest, even with --live —
       enforced structurally: this script only ever iterates the manifest, never the
       live schema.
    4. Dry-run (default): print the would-archive list in REVERSE creation order
       (properties before their group; a group only if it ends empty). Change nothing.
    5. --live: require a second explicit typed "yes" confirmation, then DELETE (archive)
       each manifested property/group in reverse order.
    6. Post-archive: re-GET and diff against the baseline snapshot; print any residual
       discrepancy (should be empty).

HUMAN RUNBOOK (RESEARCH.md §3.4):
    WHEN to roll back: the post-migration GET diff (Task 1's --label post snapshot vs the
    baseline) shows an unexpected shape (wrong type landed, wrong option set, a property
    the manifest didn't intend), OR a downstream phase discovers the schema is wrong
    BEFORE any real enrichment data has accumulated on the new properties — the "no data
    yet" condition is what keeps this cheap; once real data accumulates, rolling back
    destroys work, so decide fast.
    WHAT to run: `python scripts/rollback_property_migration.py` (dry run) first, read the
    printed diff, confirm it matches expectations, THEN re-run with `--live`.
    HOW to verify: re-run `scripts/snapshot_hubspot_schema.py` and diff the output against
    the pre-migration baseline file committed by Task 1 — an empty diff is the bar.
    COUPLED-ROLLBACK RECOVERY: if code was reverted but properties remain, they are inert
    (nothing writes to them with the old code active) — do NOT reflexively archive them;
    check each property's fill rate via a live GET first (RESEARCH.md §3.3).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

MANIFEST_DIR = ROOT / "config" / "hubspot_migration"
BASELINE_DIR = MANIFEST_DIR / "baseline"

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def find_latest_manifest(directory: Path = MANIFEST_DIR) -> Path | None:
    candidates = sorted(directory.glob("undo-manifest-*.json"))
    return candidates[-1] if candidates else None


def find_latest_baseline(object_type: str, directory: Path = BASELINE_DIR) -> Path | None:
    candidates = sorted(directory.glob(f"portal-schema-{object_type}-*.json"))
    # Prefer a non-"-post" baseline (the PRE-migration snapshot is the rollback target);
    # fall back to whatever exists if only one snapshot was ever taken.
    pre = [p for p in candidates if not p.name.endswith("-post.json")]
    return (pre or candidates)[-1] if candidates else None


def load_manifest(path: Path) -> list:
    return json.loads(path.read_text())


def load_baseline(path: Path) -> dict:
    return json.loads(path.read_text())


def reverse_archive_order(manifest: list) -> list:
    """Properties before their group (mirrors the forward creation order, reversed): a
    group is only ever archived once every property this run created inside it is
    already being archived first, in the same list. Whether the group is ACTUALLY empty
    on the live portal at archive time (e.g. some other workflow added a property to it
    independently) is a live-time check performed by the caller before the DELETE call,
    not something this pure static-ordering function can know from the manifest alone."""
    properties = [e for e in manifest if e.get("kind") == "property"]
    groups = [e for e in manifest if e.get("kind") == "group"]
    return list(reversed(properties)) + list(reversed(groups))


def refuses_entries_outside_manifest(manifest: list, candidate_names: list) -> list:
    """Returns the subset of `candidate_names` that are NOT in the manifest — anything in
    this list must NEVER be archived, even with --live. Enforced structurally by the
    archive loop only ever iterating `manifest`, never a live schema listing; this
    function exists purely so tests can assert the refusal set directly."""
    manifested = {(e.get("object_type"), e.get("name")) for e in manifest}
    return [n for n in candidate_names if n not in manifested]


def diff_against_baseline(live_properties: list, baseline_properties: list) -> list:
    """Empty for a clean rollback; non-empty lists residual property names present live
    but absent from the baseline (anything left over was not created by this migration
    and is out of scope for this script to touch)."""
    live_names = {p["name"] for p in live_properties}
    baseline_names = {p["name"] for p in baseline_properties}
    return sorted(live_names - baseline_names)


def _get_property_live(object_type: str, name: str):
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}", headers=hs_headers(), timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _archive_property_live(object_type: str, name: str) -> int:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.delete(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}", headers=hs_headers(), timeout=30)
    return r.status_code


def _archive_group_live(object_type: str, name: str) -> int:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.delete(f"{BASE_URL}/crm/v3/properties/{object_type}/groups/{name}", headers=hs_headers(), timeout=30)
    return r.status_code


def _get_live_properties(object_type: str) -> list:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                         help="Actually archive (requires a typed 'yes' confirmation).")
    parser.add_argument("--manifest", default=None, help="Path to the undo manifest JSON.")
    parser.add_argument("--baseline-companies", default=None,
                         help="Path to the companies baseline snapshot JSON.")
    parser.add_argument("--baseline-contacts", default=None,
                         help="Path to the contacts baseline snapshot JSON.")
    parser.add_argument("--confirm", default=None,
                         help="Pre-supplied typed confirmation (for non-interactive callers). "
                              "Must be exactly 'yes' to proceed with --live.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this rollback.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    manifest_path = Path(args.manifest) if args.manifest else find_latest_manifest()
    if not manifest_path or not manifest_path.exists():
        print("REFUSED: no undo manifest found — nothing safe to undo. "
              "Run scripts/sync_hubspot_properties.py first, or pass --manifest PATH.")
        return 1

    baseline_co_path = Path(args.baseline_companies) if args.baseline_companies else find_latest_baseline("companies")
    baseline_ct_path = Path(args.baseline_contacts) if args.baseline_contacts else find_latest_baseline("contacts")
    if not baseline_co_path or not baseline_co_path.exists() or not baseline_ct_path or not baseline_ct_path.exists():
        print("REFUSED: no baseline snapshot found for both object types — nothing to diff "
              "against. Run scripts/snapshot_hubspot_schema.py first, or pass "
              "--baseline-companies/--baseline-contacts PATH.")
        return 1

    manifest = load_manifest(manifest_path)
    baseline_co = load_baseline(baseline_co_path)
    baseline_ct = load_baseline(baseline_ct_path)

    ordered = reverse_archive_order(manifest)
    print(f"Would archive (reverse creation order), {len(ordered)} entries:")
    for entry in ordered:
        print(f"  {entry['kind']} {entry.get('object_type')}/{entry['name']}")

    if not args.live:
        print("DRY RUN (default) — nothing archived. Re-run with --live to actually archive.")
        return 0

    confirm = args.confirm if args.confirm is not None else input(
        "Type 'yes' to archive the above entries: ")
    if confirm.strip().lower() != "yes":
        print("REFUSED: confirmation not given — nothing archived.")
        return 1

    for entry in ordered:
        object_type = entry["object_type"]
        name = entry["name"]
        if entry["kind"] == "property":
            live = _get_property_live(object_type, name)
            if live is None:
                print(f"skip {object_type}/{name}: already absent")
                continue
            if live.get("hubspotDefined"):
                print(f"REFUSED to archive {object_type}/{name}: hubspotDefined=true "
                      "(belt-and-braces — never touch a native property)")
                continue
            status = _archive_property_live(object_type, name)
            print(f"archived property {object_type}/{name} -> HTTP {status}")
        else:
            live_props = _get_live_properties(object_type)
            remaining = [p for p in live_props if p.get("groupName") == name]
            if remaining:
                print(f"skip group {object_type}/{name}: {len(remaining)} property(ies) "
                      "still remain — never archive a non-empty group")
                continue
            status = _archive_group_live(object_type, name)
            print(f"archived group {object_type}/{name} -> HTTP {status}")

    for object_type, baseline in (("companies", baseline_co), ("contacts", baseline_ct)):
        live_properties = _get_live_properties(object_type)
        residual = diff_against_baseline(live_properties, baseline.get("results", []))
        if residual:
            print(f"RESIDUAL DISCREPANCY ({object_type}): {residual} — not created by this "
                  "migration, out of scope for this script to touch.")
        else:
            print(f"{object_type}: clean rollback, no residual discrepancy vs baseline.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
