#!/usr/bin/env python3
"""scripts/rollback_canary_proof.py

Phase 15 Task 8 — the one genuinely necessary LIVE proof that archival mechanics work
against portal 22617666, without touching any property the migration actually needs
(RESEARCH.md §3.6).

Usage:
    DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true python scripts/rollback_canary_proof.py

Behavior (all live steps two-key gated; no credentials -> exit 0):
    1. Build a throwaway property spec `lv_rollback_canary_<UTC>` on `companies`, type
       string (cheapest, most inert), no data written.
    2. Create it via scripts.sync_hubspot_properties' create-property path, into a
       single-entry canary manifest.
    3. Run scripts.rollback_property_migration's archive path against ONLY that canary
       manifest, in reverse-creation order.
    4. Assert via GET /crm/v3/properties/companies/lv_rollback_canary_<UTC> that it now
       reports archived (or is absent from the default non-archived listing). Print
       PASS/FAIL.

This proves the ARCHIVE-CALL mechanics work against this specific portal. The separate
"recreate-by-name restores DATA within 90 days" claim (RESEARCH.md §2.6/§3.6) stays
[CITED, MEDIUM confidence] and is an accepted residual risk — this phase never lets real
data accumulate on any new property, so that specific claim is never relied on in anger
before a future phase would need it.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve

from scripts import sync_hubspot_properties as sync  # noqa: E402
from scripts import rollback_property_migration as rollback  # noqa: E402

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow


def build_canary_property_spec(ts: str) -> dict:
    name = f"lv_rollback_canary_{ts}"
    return {"name": name, "label": f"LV Rollback Canary {ts}", "type": "string",
            "fieldType": "text", "groupName": "lv_enrichment", "options": []}


def build_canary_manifest(ts: str) -> list:
    spec = build_canary_property_spec(ts)
    return [{"kind": "property", "object_type": "companies", "name": spec["name"],
             "group_name": spec["groupName"], "request_body": spec}]


def is_archived(get_response) -> bool:
    """True when the canary reports `archived: true`, OR is entirely absent from the
    default (non-archived) listing (the caller passes None for a 404)."""
    if get_response is None:
        return True
    return bool(get_response.get("archived"))


def main(argv=None) -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this canary proof.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if not _writes_allowed():
        print("skipped: DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_WRITES=true are both "
              "required to run the canary proof (two-key gate).")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    spec = build_canary_property_spec(ts)
    print(f"canary property: {spec['name']}")

    status, body = sync._create_property_live("companies", spec)
    if status != 201:
        print(f"FAIL: canary create returned HTTP {status}, expected 201 — {body}")
        return 1
    print(f"created {spec['name']} (201)")

    manifest = build_canary_manifest(ts)
    for entry in rollback.reverse_archive_order(manifest):
        object_type = entry["object_type"]
        name = entry["name"]
        live = rollback._get_property_live(object_type, name)
        if live is None:
            print(f"FAIL: canary {name} disappeared before archive")
            return 1
        if live.get("hubspotDefined"):
            print(f"FAIL: canary {name} reports hubspotDefined=true — refusing to archive")
            return 1
        archive_status = rollback._archive_property_live(object_type, name)
        print(f"archived {name} -> HTTP {archive_status}")

    confirm = rollback._get_property_live("companies", spec["name"])
    if is_archived(confirm):
        print(f"PASS: {spec['name']} reports archived (or absent from the default listing).")
        return 0
    print(f"FAIL: {spec['name']} does not report archived: {confirm}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
