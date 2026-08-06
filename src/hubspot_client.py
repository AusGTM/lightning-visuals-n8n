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


def delete_record(object_type: str, record_id: str, dry_run=True):
    # Phase 39 (39-03, DECIDE-01): mirrors patch_record/create_record. dry_run
    # short-circuits BEFORE any live DELETE call — prints only the URL (never
    # hs_headers/token; there is no payload on a DELETE) and returns the sentinel.
    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "method": "DELETE",
            "url": f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
        }, indent=2, default=str))
        return {"dry_run": True}

    url = f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
    r = requests.delete(url, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    # HubSpot answers a successful company delete with 204 No Content, which has
    # no JSON body — return the response object itself; caller asserts
    # r.status_code == 204. Do not "fix" this into r.json(), there is no body.
    return r


def batch_update_companies(updates: list[dict], dry_run=True):
    # Phase 40 (40-07, D-10): mirrors patch_record/create_record's dry_run discipline.
    # Two deliberate deviations from create_record's shape, both load-bearing for the
    # backfill caller (Task 2): an empty list short-circuits in BOTH modes (nothing to
    # send, so live mode must not POST an empty batch either), and a >100-entry list
    # raises rather than being sent or silently truncated -- the caller chunks, this
    # helper refuses to guess.
    if len(updates) > 100:
        raise ValueError(
            f"batch_update_companies received {len(updates)} updates; HubSpot's batch "
            "update endpoint accepts at most 100 per call. Chunk the caller's list "
            "instead of sending an oversized batch."
        )

    payload = {"inputs": updates}

    if dry_run or not updates:
        print(json.dumps({
            "dry_run": True,
            "method": "POST",
            "url": f"{BASE_URL}/crm/v3/objects/companies/batch/update",
            "payload": payload
        }, indent=2, default=str))
        return {"dry_run": True, "payload": payload}

    url = f"{BASE_URL}/crm/v3/objects/companies/batch/update"
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
