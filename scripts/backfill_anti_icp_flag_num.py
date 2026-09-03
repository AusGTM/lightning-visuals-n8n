#!/usr/bin/env python3
"""scripts/backfill_anti_icp_flag_num.py

Phase 50 Plan 06 Task 3 (D-16, D-20, D-22) -- the phase's ONE authorised company-write
deviation: copies `lv_anti_icp_flag` onto its numeric mirror `lv_anti_icp_flag_num` for
every company that already carries `lv_anti_icp_flag=true`. Not a re-derivation --
copies an existing property, so no record's veto status can change as a result of the
write itself.

Target set is re-derived LIVE on every invocation via a `lv_anti_icp_flag EQ "true"`
company search -- NEVER read from 50-MIRROR-SCOPE.md or any other local snapshot, so a
stale artifact cannot widen the blast radius. Refuses (never truncates) if the live set
exceeds MAX_BACKFILL_RECORDS -- a cap that has to be raised by an edit is a cap that gets
noticed.

Every PATCH body carries exactly one key, `lv_anti_icp_flag_num` -- assert_payload_scope
raises rather than sends if a body ever carries a second key. Every write is verified by
an independent per-record re-read, never from the PATCH response body.

Two-key write gate, this script's own allow-key (never another script's):
    DRY_RUN=false AND ALLOW_ANTI_ICP_MIRROR_BACKFILL=true

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    DRY_RUN=false ALLOW_ANTI_ICP_MIRROR_BACKFILL=true .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['backfill_anti_icp_flag_num.py', '--execute']; \
         runpy.run_path('scripts/backfill_anti_icp_flag_num.py', run_name='__main__')"

Usage:
    python scripts/backfill_anti_icp_flag_num.py            # --plan (default), zero writes
    python scripts/backfill_anti_icp_flag_num.py --execute  # armed only with both env keys set
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve
from src.guards import emit_json  # noqa: E402

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# A cap that has to be raised by an edit is a cap that gets noticed (50-06-PLAN.md Task
# 3). 50-MIRROR-SCOPE.md's live search found 6 -- well under this.
MAX_BACKFILL_RECORDS = 10

MIRROR_PROP = "lv_anti_icp_flag_num"


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_ANTI_ICP_MIRROR_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow


# --- population (D-20: re-derived live, never from a local snapshot) -------------------

def veto_search_filter() -> list:
    """The ONLY filter this script ever searches with -- EQ "true" structurally excludes
    every record whose lv_anti_icp_flag is false or unset (a record whose flag is not
    literally the string "true" can never match an EQ filter for "true")."""
    return [{"propertyName": "lv_anti_icp_flag", "operator": "EQ", "value": "true"}]


def select_vetoed_population() -> list:
    from src.hubspot_client import search_records

    result = search_records("companies", veto_search_filter(), ["name", "lv_anti_icp_flag"], limit=100)
    ids = sorted(r["id"] for r in result.get("results", []))
    total = result.get("total")
    if total is not None and total > len(ids):
        raise RuntimeError(
            f"REFUSED: the live veto search reports {total} records but this search "
            f"returned only {len(ids)}. Operating on a truncated set would silently "
            "narrow or corrupt the authorised backfill scope."
        )
    return ids


def enforce_backfill_cap(ids: list) -> bool:
    """True if the sample is at or under MAX_BACKFILL_RECORDS. Refuse (return False),
    never truncate -- same contract as scripts/backfill_seed_company_scores.py's
    enforce_sample_cap."""
    return len(ids) <= MAX_BACKFILL_RECORDS


# --- payload (T-50-28: the backfill widening beyond its authorised scope) ---------------

def build_updates(ids: list) -> list:
    # D-04/P4 string-literal rule -- the value the pipeline PATCHes is the string "1",
    # never a bare int/bool, matching what the n8n engine emits (Task 4) and what a
    # HubSpot GET echoes back.
    return [{"id": i, "properties": {MIRROR_PROP: "1"}} for i in ids]


def assert_payload_scope(updates: list) -> None:
    """Raises ValueError unless every payload entry's properties key set is EXACTLY
    {lv_anti_icp_flag_num} -- stated positively as an equality so a body carrying a
    second key (accidental or otherwise) is refused rather than sent."""
    expected = {MIRROR_PROP}
    for entry in updates:
        keys = set(entry.get("properties", {}).keys())
        if keys != expected:
            raise ValueError(
                f"payload entry for id={entry.get('id')!r} has properties key set "
                f"{sorted(keys)}, expected exactly {sorted(expected)}."
            )


# --- write leg ---------------------------------------------------------------------------

def run_plan() -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this driver.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    ids = select_vetoed_population()
    if not enforce_backfill_cap(ids):
        print(f"REFUSED: live vetoed population has {len(ids)} records, exceeding "
              f"MAX_BACKFILL_RECORDS ({MAX_BACKFILL_RECORDS}). No API call made.")
        return 1

    updates = build_updates(ids)
    assert_payload_scope(updates)
    emit_json({
        "mode": "plan", "ids": ids, "count": len(ids),
        "max_backfill_records": MAX_BACKFILL_RECORDS, "updates": updates,
    }, indent=2)
    print("DISARMED -- no write performed. Set DRY_RUN=false and "
          "ALLOW_ANTI_ICP_MIRROR_BACKFILL=true to arm --execute.")
    return 0


def run_execute() -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this driver.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    ids = select_vetoed_population()
    if not enforce_backfill_cap(ids):
        print(f"REFUSED: live vetoed population has {len(ids)} records, exceeding "
              f"MAX_BACKFILL_RECORDS ({MAX_BACKFILL_RECORDS}). No API call made.")
        return 1

    updates = build_updates(ids)
    assert_payload_scope(updates)
    emit_json({
        "mode": "execute", "ids": ids, "count": len(ids), "updates": updates,
    }, indent=2)

    armed = _writes_allowed()
    if not armed:
        print("DISARMED -- no write performed. Set DRY_RUN=false and "
              "ALLOW_ANTI_ICP_MIRROR_BACKFILL=true to arm.")
        return 0

    from src.hubspot_client import batch_update_companies, get_record

    batch_update_companies(updates, dry_run=False)

    print(f"armed run complete -- {len(ids)} companies written. Verifying by "
          "independent per-record re-read...")
    all_ok = True
    for i in ids:
        value = get_record("companies", i, [MIRROR_PROP])["properties"].get(MIRROR_PROP)
        ok = value == "1"
        all_ok = all_ok and ok
        print(f"  {i}: {MIRROR_PROP}={value!r} ({'ok' if ok else 'MISMATCH'})")
    return 0 if all_ok else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true",
                       help="Dry plan mode (default): re-derive the live vetoed population "
                            "and print the exact PATCH bodies. No writes of any kind.")
    mode.add_argument("--execute", action="store_true",
                       help="Write the mirror to the live-derived vetoed population and "
                            "verify by re-read. Requires DRY_RUN=false and "
                            "ALLOW_ANTI_ICP_MIRROR_BACKFILL=true to actually write; "
                            "disarmed, prints what would be written.")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.execute:
        return run_execute()
    return run_plan()  # --plan is the default when no mode flag is given.


if __name__ == "__main__":
    sys.exit(main())
