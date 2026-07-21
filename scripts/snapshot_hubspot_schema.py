#!/usr/bin/env python3
"""scripts/snapshot_hubspot_schema.py

Phase 15 Task 1 — read-only HubSpot property-schema snapshot + unknown-property probe.

Non-gating, env-gated, safe to run without credentials (CI/dev machines never touch the
network). Captures the FULL current property schema for both object types as committed,
versioned JSON — this IS the rollback target `rollback_property_migration.py` diffs
against (RESEARCH.md §3.1), independent of the undo manifest (which only records what one
sync run created). Also offers a --probe mode that settles whether an unknown PATCH
property name silently no-ops or 400s (RESEARCH.md §2.8/§9-A2), gated two ways so it can
never fire by accident.

Usage:
    python scripts/snapshot_hubspot_schema.py [--label SUFFIX]
    python scripts/snapshot_hubspot_schema.py --probe

Zero writes in the default mode: GET only, verbatim to disk. --probe performs exactly one
PATCH of a deliberately-unknown property name to a designated TEST company, gated by
DRY_RUN=false (in addition to the --probe flag itself) so a bare `--probe` invocation never
fires without an explicit second signal.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

BASELINE_DIR = ROOT / ".planning" / "phases" / "15-hubspot-property-migration" / "baseline"

# Portal 22617666 is the only portal this migration is designed against — asserted BEFORE
# any call so a multi-portal credential mixup refuses pre-call, not mid-batch (RESEARCH
# §9/T-15-03). Never a token/secret, so a hardcoded module constant is fine here; the env
# var is an override for testing against a different target portal, not a default source.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# 2026-07-20 portal audit (docs/WEB-RESEARCH-SPEC.md §0.6) — the 5 custom company
# properties known to exist before this migration. This is a live DRIFT CHECK only, never
# a gate: Task 1's whole point is confirming (or correcting) this against the live GET.
KNOWN_COMPANY_CUSTOM_PROPS = {
    "lv_anti_icp_flag", "lv_icp_fit_score", "lv_icp_tier", "lv_org_type", "lv_produces_content",
}

# The property name the --probe PATCH sends. Deliberately not `lv_`-prefixed and not in
# any manifest — this is throwaway, single-use, and never intended to exist.
PROBE_PROPERTY_NAME = "lv__phase15_unknown_property_probe"


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _get_properties_raw(object_type: str) -> str:
    """GET /crm/v3/properties/{objectType} -> raw response text (verbatim, unparsed).

    Not added to src/hubspot_client.py: that module is the object-record CRUD dev-oracle
    client (get_record/patch_record/create_record/search_records) — the CRM v3 PROPERTIES
    (schema) endpoints are new surface kept local to this script, per the plan's own
    instruction to add the calls here rather than touch the shared client.
    """
    import requests
    from src.hubspot_client import hs_headers, BASE_URL

    url = f"{BASE_URL}/crm/v3/properties/{object_type}"
    r = requests.get(url, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.text


def _assert_no_secrets(text: str) -> None:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or ""
    assert "Authorization" not in text, "serializer leaked the Authorization header"
    if token:
        assert token not in text, "serializer leaked the bearer token value"
    assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text, "serializer leaked the token env var name"


def _write_snapshot(object_type: str, raw_text: str, label: str | None,
                     directory: Path = BASELINE_DIR) -> Path:
    """Write the HubSpot response body VERBATIM (no re-serialization/reordering) to
    baseline/portal-schema-{object_type}-{label or UTC-timestamp}.json."""
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = label if label else ts
    path = directory / f"portal-schema-{object_type}-{suffix}.json"
    _assert_no_secrets(raw_text)
    path.write_text(raw_text)
    return path


def _print_drift(companies_body: dict) -> None:
    live_custom = {
        p["name"] for p in companies_body.get("results", [])
        if not p.get("hubspotDefined")
    }
    added = live_custom - KNOWN_COMPANY_CUSTOM_PROPS
    removed = KNOWN_COMPANY_CUSTOM_PROPS - live_custom
    print(f"Live custom company properties: {sorted(live_custom)}")
    if added or removed:
        print(f"DRIFT vs the 2026-07-20 audit — added: {sorted(added)}, missing: {sorted(removed)}")
    else:
        print("No drift vs the 2026-07-20 audit's 5 known custom company properties.")


def _run_probe(test_company_id: str) -> int:
    """PATCH one deliberately-unknown property name to a designated TEST company and
    report the HTTP status/body — settles RESEARCH §2.8/§9-A2 (silent no-op vs 400) live
    before the batch migration (Task 3) trusts that assumption."""
    import requests
    from src.hubspot_client import hs_headers, BASE_URL

    url = f"{BASE_URL}/crm/v3/objects/companies/{test_company_id}"
    payload = {"properties": {PROBE_PROPERTY_NAME: "probe"}}
    r = requests.patch(url, headers=hs_headers(), json=payload, timeout=30)
    print(f"PROBE: PATCH unknown property '{PROBE_PROPERTY_NAME}' -> HTTP {r.status_code}")
    try:
        print(f"PROBE response body: {json.dumps(r.json())}")
    except ValueError:
        print(f"PROBE response body (non-JSON): {r.text[:500]}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default=None,
                         help="Suffix for the snapshot filenames instead of a UTC timestamp "
                              "(e.g. 'post' for the post-migration re-run).")
    parser.add_argument("--probe", action="store_true",
                         help="Also run the unknown-property PATCH probe against "
                              "TEST_COMPANY_IDS' first id. Two-key gated: this flag AND "
                              "DRY_RUN=false must both hold, or the probe is skipped.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "live snapshot.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made. If this is genuinely a different "
              f"target portal, set HUBSPOT_EXPECTED_PORTAL_ID to override.")
        return 1

    companies_raw = _get_properties_raw("companies")
    contacts_raw = _get_properties_raw("contacts")

    co_path = _write_snapshot("companies", companies_raw, args.label)
    ct_path = _write_snapshot("contacts", contacts_raw, args.label)
    print(f"wrote {co_path}")
    print(f"wrote {ct_path}")

    _print_drift(json.loads(companies_raw))

    if args.probe:
        dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        if dry_run:
            print("PROBE requested but DRY_RUN is not 'false' — refusing (two-key gate). "
                  "Set DRY_RUN=false to actually run the probe PATCH.")
        else:
            test_ids = os.getenv("TEST_COMPANY_IDS", "")
            first_id = test_ids.split(",")[0].strip() if test_ids else ""
            if not first_id:
                print("PROBE requested and DRY_RUN=false, but TEST_COMPANY_IDS is empty — refusing.")
            else:
                return _run_probe(first_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
