#!/usr/bin/env python3
"""scripts/put_hubspot_flow.py

Phase 40 Plan 01 Task 2 (D-05/D-07/D-08) — PUT a stripped flow JSON body to
`/automation/v4/flows/{flow_id}`. This is the reproducible record of what was sent for
every flow edit this phase, not an arming ceremony — D-08 permits executing these PUTs
directly in-session, with D-07's disable -> edit -> validate-on-disposable -> re-enable
protocol as the safety envelope. Still two-key gated (DRY_RUN=false AND
ALLOW_HUBSPOT_FLOW_WRITE=true) so a bare invocation never fires by accident, mirroring
scripts/probe_scoring_recalc_latency.py's convention.

Prints only the payload dict, never `hs_headers()`/the token (same discipline as every
write helper in src/hubspot_client.py).

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    ALLOW_HUBSPOT_FLOW_WRITE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['put_hubspot_flow.py', '--file', 'path/to/flow.json', \
                      '--flow-id', '4626124224', '--disable']; \
         runpy.run_path('scripts/put_hubspot_flow.py', run_name='__main__')"

Usage:
    python scripts/put_hubspot_flow.py --file path/to/flow.json --flow-id 4626124224 \
        [--disable | --enable]

Phase 50 Plan 05 (D-24, operator-authorised override of D-08): `--delete` issues
`DELETE /automation/v4/flows/{flow_id}` instead of a PUT — no body required, so `--file`
is optional for this action only. Reuses the exact same two-key gate
(`_writes_allowed()`) as the PUT path; no third gate idiom introduced. This is the
one-way action D-08 originally prohibited ("WF1 4625147345 is not deleted"); the
operator explicitly overrode that prohibition after `DELETE
/crm/v3/properties/companies/lv_icp_tier` refused to archive a property still
referenced by a disabled workflow's action (`CANNOT_DELETE_PROPERTY_IN_USE`). Confirm
the flow's before/after JSON snapshots are committed BEFORE running this — after a
delete they are the only copy; there is no `--undelete`.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve
from src.guards import emit_json  # noqa: E402

# Portal 22617666 (ap1) — asserted before any call, same discipline as
# scripts/fetch_hubspot_flow.py / scripts/snapshot_hubspot_schema.py.
EXPECTED_PORTAL_ID = "22617666"

# PUT is replace-not-merge (40-RESEARCH.md Pitfall 1) — a body carrying any of these is
# refused rather than silently stripped, since their presence means the caller skipped
# fetch_hubspot_flow.py's archive step and is PUTting a raw GET response.
STRIP_KEYS = ("createdAt", "updatedAt", "dataSources")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_FLOW_WRITE", "false").lower() == "true"
    return (not dry_run) and allow


def load_flow_body(path: str) -> dict:
    with Path(path).open() as f:
        body = json.load(f)
    poisoned = [k for k in STRIP_KEYS if k in body]
    if poisoned:
        raise ValueError(
            f"{path} still carries {poisoned} — strip these before PUT (Pitfall 1). "
            f"Run scripts/fetch_hubspot_flow.py, not a raw GET, to produce this file."
        )
    return body


def put_flow(flow_id: str, body: dict, dry_run: bool) -> dict:
    payload = body
    url_desc = f"/automation/v4/flows/{flow_id}"

    if dry_run:
        emit_json({
            "dry_run": True,
            "method": "PUT",
            "url": url_desc,
            "isEnabled": payload.get("isEnabled"),
        }, indent=2, default=str)
        return {"dry_run": True}

    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    r = requests.put(f"{BASE_URL}{url_desc}", headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else {}


def delete_flow(flow_id: str, dry_run: bool) -> dict:
    """Phase 50 Plan 05 (D-24) -- DELETE /automation/v4/flows/{flow_id}. No body, no
    round-trip poison-field concern (Pitfall 1 only applies to PUT). Dry-run prints the
    call it would make and issues nothing."""
    url_desc = f"/automation/v4/flows/{flow_id}"

    if dry_run:
        emit_json({"dry_run": True, "method": "DELETE", "url": url_desc}, indent=2)
        return {"dry_run": True}

    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    r = requests.delete(f"{BASE_URL}{url_desc}", headers=hs_headers(), timeout=30)
    return {"status_code": r.status_code, "text": r.text[:500] if r.text else ""}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=None,
                         help="Path to the stripped flow JSON body. Required unless --delete.")
    parser.add_argument("--flow-id", required=True, help="Flow id to PUT or DELETE.")
    toggle = parser.add_mutually_exclusive_group()
    toggle.add_argument("--disable", action="store_true", help="Set isEnabled=false before PUT.")
    toggle.add_argument("--enable", action="store_true", help="Set isEnabled=true before PUT.")
    toggle.add_argument("--delete", action="store_true",
                         help="DELETE the flow entirely instead of PUTting a body "
                              "(Phase 50 Plan 05, D-24). No --file needed.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to PUT a "
              "live flow definition.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    dry_run = not _writes_allowed()
    if dry_run:
        print("DRY_RUN=false AND ALLOW_HUBSPOT_FLOW_WRITE=true are both required to "
              "actually PUT/DELETE (two-key gate) — printing payload only.")

    if args.delete:
        result = delete_flow(args.flow_id, dry_run)
        emit_json(result, indent=2, default=str)
        return 0

    if not args.file:
        print("REFUSED: --file is required unless --delete is given.")
        return 1

    body = load_flow_body(args.file)
    if args.disable:
        body["isEnabled"] = False
    elif args.enable:
        body["isEnabled"] = True

    result = put_flow(args.flow_id, body, dry_run)
    emit_json(result, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
