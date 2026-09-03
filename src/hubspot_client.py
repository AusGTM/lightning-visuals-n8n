import os
import json
import requests

from src.guards import FORBIDDEN_PROPS, assert_disjoint

BASE_URL = "https://api.hubapi.com"

# The arm keys registered as authorising a live company batch write. A driver that wants
# to arm `batch_update_companies` must add its key HERE as well as gating its own CLI --
# that friction is the point, and it is why this is an explicit list and never a
# wildcard `ALLOW_*` scan. `.env.example` ships several unrelated `ALLOW_*` flags
# (ALLOW_ICP_SCORE_WRITES, ALLOW_STAGING_WRITES) that a local-MVP shell sets true; a
# wildcard would let one of those arm a mass write it was never meant to authorise.
BATCH_WRITE_ARM_KEYS = (
    "ALLOW_SCORE_BACKFILL",            # rescore_population, backfill_seed_company_scores
    "ALLOW_VETO_REMEDIATION",          # remediate_veto_companies
    "ALLOW_ANTI_ICP_MIRROR_BACKFILL",  # backfill_anti_icp_flag_num
    "ALLOW_ENRICH_COVERAGE",           # enrich_coverage_companies
)


def _batch_write_armed() -> bool:
    """The generalized form of the two-key gate every batch driver already implements
    for itself: `DRY_RUN=false` AND one registered arm key true.

    Deliberately NOT a lift-and-shift of `rescore_population._writes_allowed()`, which
    hardcodes `ALLOW_SCORE_BACKFILL` -- that exact function moved here would refuse the
    armed runs of the other three drivers, which use three different keys.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = any(os.getenv(k, "false").lower() == "true" for k in BATCH_WRITE_ARM_KEYS)
    return (not dry_run) and allow


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

    # Phase 49 audit, Divergence 1 (operator-granted 2026-09-03): the gate travels with
    # the write. Before this, `batch_update_companies` checked only `len(updates) > 100`
    # -- the two-key arming gate lived entirely in each driver's own `_writes_allowed()`
    # and the scope gate in each driver's own `assert_payload_scope()`, so ANY importer
    # calling this with dry_run=False reached `requests.post` below from an unarmed
    # shell with an arbitrary property set. That is not hypothetical: it happened once
    # during phase 49's W1 window (`49-W1-ARM-RECORD.md:200-210`) and was disclosed at
    # the time. Both checks below are unconditional raises, never `assert` (removed
    # under `python -O`, WR-02) and never a silent downgrade to dry-run -- a caller that
    # asked for a live write and is not entitled to one must fail loudly.
    #
    # Deliberately scoped to this function. `patch_record`/`create_record`/
    # `delete_record` keep the §21 caller-gates convention their own comments document;
    # this is the mass-write endpoint (up to 100 records per call), so the floor lives
    # with it. The drivers keep their own exact-set `assert_payload_scope()` ceilings --
    # this is only the universal never-write floor beneath them.
    if not _batch_write_armed():
        raise ValueError(
            "REFUSED: batch_update_companies was called with dry_run=False from an "
            "unarmed shell. A live company batch write requires DRY_RUN=false AND one "
            f"of {', '.join(BATCH_WRITE_ARM_KEYS)} set to true. Run the driver that "
            "owns this write rather than calling the client directly."
        )
    for entry in updates:
        assert_disjoint(
            entry.get("properties", {}).keys(), FORBIDDEN_PROPS,
            f"REFUSED: payload entry for id={entry.get('id')!r} carries a derived "
            f"property owned by the calculated properties and the n8n Decide node "
            f"({sorted(FORBIDDEN_PROPS)}). These are never written directly.",
        )

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
