#!/usr/bin/env python3
"""scripts/scored_population_snapshot.py

Phase 51 Plan 03 (SAFE-01, T-51-12/T-51-13) -- the read-only before-snapshot of the
already-scored company population (D-01: deliberately excluded from this milestone's
write set). "We did not touch them" is only provable against a baseline captured before
any write existed in the milestone -- captured here, in a phase that structurally cannot
write, so the baseline cannot have been influenced by a write.

This module is READ-ONLY throughout. It never issues a HubSpot write of any kind -- no
create, no update, no delete call site exists anywhere in this file, enforced by this
module's own test suite via source inspection.

Population definition is imported, never restated: `select_scored_population` from
`scripts.rescore_population` (the same `HAS_PROPERTY(lv_icp_fit_score)` search shape three
other scripts already share), which refuses (raises) rather than silently truncating if the
live scored population exceeds one search page -- a partial baseline would be worse than no
baseline, because Phase 52's closing diff would silently pass over the omitted records.

Must be run from the repo root (config/icp_scoring.yaml loads via a CWD-relative path
elsewhere in this codebase; this module follows the same repo-wide convention).

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['scored_population_snapshot.py', '--out', 'PATH/TO/snapshot.json']; \
         runpy.run_path('scripts/scored_population_snapshot.py', run_name='__main__')"

Usage:
    python scripts/scored_population_snapshot.py [--out PATH]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.hubspot_client import get_record  # noqa: E402
from scripts.rescore_population import select_scored_population  # noqa: E402 -- import, never a fourth inline definition

# WR-01-style discipline: hard-coded, no env override.
EXPECTED_PORTAL_ID = "22617666"

# The exact property list, in this order: six scoring inputs, five component scores, the
# veto pair, the anti-ICP reason, the two calculated outputs, plus name/domain for human
# readability. Reading a calculated property is free and safe -- D-01's exclusion is on
# writing, not reading -- and Phase 52's closing diff needs the derived tier in the
# baseline to prove it did not move.
SNAPSHOT_PROPS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
    "lv_revenue_band",
    "lv_is_gambling_operator",
    "lv_is_hardware_vendor",
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
    "lv_anti_icp_flag",
    "lv_anti_icp_flag_num",
    "lv_anti_icp_reason",
    "lv_icp_fit_score",
    "lv_icp_tier_derived",
    "name",
    "domain",
]


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_snapshot() -> dict:
    """Portal guard lives only in main(), not here -- so offline tests can call this
    directly without setenv ceremony (mirrors scripts/backfill_dry_run.py's own
    run_dry_run() precedent). main() still asserts the portal before any network call.

    `select_scored_population()` is the population's single source of truth; its own
    refuse-rather-than-truncate guard raises RuntimeError (propagated, never swallowed)
    if the live population exceeds one search page -- no snapshot is written in that case.

    Records are re-sorted here by ascending NUMERIC id (not the imported function's own
    lexicographic string sort) -- this portal mixes 10- and 11-digit HubSpot ids, and a
    string sort would misorder them (the exact landmine 51-02 already fixed for the
    never-scored sample)."""
    ids = sorted(select_scored_population(), key=int)
    records = []
    for company_id in ids:
        props = get_record("companies", company_id, SNAPSHOT_PROPS).get("properties", {}) or {}
        records.append({
            "id": company_id,
            "properties": {name: props.get(name) for name in SNAPSHOT_PROPS},
        })
    return {
        "captured_at": _now_iso(),
        "portal_id_verified": os.getenv("HUBSPOT_PORTAL_ID"),
        "population_definition": "HAS_PROPERTY(lv_icp_fit_score)",
        "population_count": len(records),
        "records": records,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None,
                         help="Path to write the snapshot JSON to. Defaults to stdout.")
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this tool.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    snapshot = capture_snapshot()
    text = json.dumps(snapshot, indent=2, sort_keys=True, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"snapshot written to {args.out} ({snapshot['population_count']} records).")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
