import os
import json
import requests

BASE_URL = "https://api.hubapi.com"


def hs_headers():
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_record(object_type: str, record_id: str, properties: list[str]):
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
    params = {"properties": ",".join(properties)}
    r = requests.get(url, headers=hs_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def patch_record(object_type: str, record_id: str, properties: dict, dry_run=True):
    payload = {"properties": properties}

    # Phase 4 (MVP-04, CLAUDE.md §21): dry_run stays True everywhere. Print only the
    # payload dict (never hs_headers/token) and return the sentinel WITHOUT hitting the
    # network. Live writeback is a future milestone, out of scope here.
    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "method": "PATCH",
            "url": f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}",
            "payload": payload
        }, indent=2, default=str))
        return {"dry_run": True, "payload": payload}

    url = f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
    r = requests.patch(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def create_record(object_type: str, properties: dict, dry_run=True):
    payload = {"properties": properties}

    # Phase 8 (P8-SC2, CLAUDE.md §21): mirrors patch_record. dry_run short-circuits
    # BEFORE any requests.post — prints only the payload dict (never hs_headers/token)
    # and returns the sentinel. The ALLOW_CONTACT_CREATE gate is the CALLER's job, not
    # the client's (§21 safety-gate pattern), so it is deliberately not checked here.
    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "method": "POST",
            "url": f"{BASE_URL}/crm/v3/objects/{object_type}",
            "payload": payload
        }, indent=2, default=str))
        return {"dry_run": True, "payload": payload}

    url = f"{BASE_URL}/crm/v3/objects/{object_type}"
    r = requests.post(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def search_records(object_type: str, filters: list[dict], properties: list[str], limit=100):
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/search"
    payload = {
        "filterGroups": [{"filters": filters}],
        "properties": properties,
        "limit": limit
    }
    r = requests.post(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
