#!/usr/bin/env python3
"""scripts/probe_scoring_tool_availability.py

Phase 39 Task 3 — disarmed-by-default, read-only availability probe for HubSpot's
native lead-scoring tool (DECIDE-01, D-01/D-02). Runs the negative-evidence ladder
this phase's RESEARCH.md establishes: neither the account-info endpoint nor the
properties listing can produce a positive "yes, available" verdict — only the
operator's in-portal walkthrough can. This script exists so that walkthrough time
isn't spent re-deriving what the API already rules out.

Zero writes: GET only, verbatim to disk. No credentials -> exit 0, no call. Wrong
portal -> refuse, no call. The bearer token is never constructed here directly —
headers come only from `src.hubspot_client.hs_headers()` — and is never printed,
logged, or placed in an evidence file.

Usage (operator-invoked; `.env` is Read/Bash-permission-blocked, loaded in-process):
    .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; \
runpy.run_path('scripts/probe_scoring_tool_availability.py', run_name='__main__')"
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src.hubspot_client import BASE_URL, hs_headers  # noqa: E402

# WR-01 fix: hard-coded, no env override — same "module constant, no CLI/env
# override" discipline as other disposable-artifact constants in this probe family. An
# env override here would let a stale HUBSPOT_EXPECTED_PORTAL_ID silently redefine the
# portal guard.
EXPECTED_PORTAL_ID = "22617666"

EVIDENCE_DIR = ROOT / ".planning" / "phases" / "39-path-decision-fit-score-verification" / "evidence"

TIER_KEYS_CHECKED = ("hubTier", "subscriptionTier", "productTier", "hubs", "products", "addOns")


def classify_account_info(body: dict) -> dict:
    """Pure classifier — no network, no env reads. `has_tier_field` is a real
    measurement (proven True-reachable by a fixture in tests/), not a classifier
    that can only ever report False."""
    return {
        "has_tier_field": any(k in body for k in TIER_KEYS_CHECKED),
        "portal_id": body.get("portalId"),
        "ui_domain": body.get("uiDomain"),
        "data_hosting_location": body.get("dataHostingLocation"),
        "tier_keys_checked": list(TIER_KEYS_CHECKED),
    }


def find_score_properties(results: list[dict]) -> list[dict]:
    """Pure filter — every entry whose fieldType is calculation_score."""
    return [p for p in results if p.get("fieldType") == "calculation_score"]


def probe_account_info(headers: dict) -> dict:
    r = requests.get(f"{BASE_URL}/account-info/v3/details", headers=headers, timeout=30)
    body = r.json() if r.ok else {"status": r.status_code, "text": r.text}
    result = {
        "endpoint": "GET /account-info/v3/details",
        "status": r.status_code,
        "body": body,
        "note": (
            "This endpoint's documented schema carries portal identity and locale "
            "only (portalId/accountType/timeZone/companyCurrency/uiDomain/"
            "dataHostingLocation). Absence of a tier field is expected and is not "
            "a signal about entitlement."
        ),
    }
    result.update(classify_account_info(body if isinstance(body, dict) else {}))
    return result


def probe_existing_score_properties(headers: dict) -> dict:
    r = requests.get(f"{BASE_URL}/crm/v3/properties/companies", headers=headers, timeout=30)
    body = r.json() if r.ok else {"status": r.status_code, "text": r.text}
    results = body.get("results", []) if isinstance(body, dict) else []
    return {
        "endpoint": "GET /crm/v3/properties/companies",
        "status": r.status_code,
        "total_properties": len(results),
        "calculation_score_properties_found": find_score_properties(results),
        "note": (
            "Empty list is inconclusive — score properties only appear here AFTER "
            "the operator builds one in-portal; absence does not mean unavailable."
        ),
    }


def main(argv=None) -> int:
    if not os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"):
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run "
              "this availability probe.")
        return 0

    if os.getenv("HUBSPOT_PORTAL_ID") != EXPECTED_PORTAL_ID:
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    headers = hs_headers()
    account_info = probe_account_info(headers)
    properties_probe = probe_existing_score_properties(headers)

    stamp = datetime.now(timezone.utc).isoformat()
    for evidence in (account_info, properties_probe):
        evidence["probed_at_utc"] = stamp
        evidence["expected_portal_id"] = EXPECTED_PORTAL_ID

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    account_info_path = EVIDENCE_DIR / "account_info_response.json"
    properties_path = EVIDENCE_DIR / "properties_probe_response.json"
    with account_info_path.open("w") as f:
        json.dump(account_info, f, indent=2, default=str)
    with properties_path.open("w") as f:
        json.dump(properties_probe, f, indent=2, default=str)

    print(f"account-info probe: has_tier_field={account_info['has_tier_field']} "
          f"-> wrote {account_info_path}")
    print(f"properties probe: total_properties={properties_probe['total_properties']}, "
          f"calculation_score_found={len(properties_probe['calculation_score_properties_found'])} "
          f"-> wrote {properties_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
