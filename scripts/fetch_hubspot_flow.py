#!/usr/bin/env python3
"""scripts/fetch_hubspot_flow.py

Phase 40 Plan 01 (D-05) — GET, strip, and archive one or more HubSpot Automation v4
flow definitions to `config/hubspot_flows/{flow_id}-{slug}.{label}.json`.

Every subsequent flow edit this phase (40-01 Task 2, 40-04, 40-05, 40-06) starts from a
live GET of this shape, not a repo read — the flows exist only in the HubSpot portal
(40-RESEARCH.md Anti-Patterns). `createdAt`, `updatedAt`, and `dataSources` are popped
before writing: PUT is replace-not-merge and these are the documented round-trip poison
fields (Pitfall 1). Sorted keys + stable indent make the `.before.json`/`.after.json` diff
the evidence that a later PUT did not silently drop an action.

Read-only. Zero writes. Safe to run without credentials (prints "skipped" and exits 0).

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/fetch_hubspot_flow.py', run_name='__main__')" \
        -- --flow-id 4626124224 --flow-id 4626722240 --flow-id 4626722237 --flow-id 4625147345

Usage:
    python scripts/fetch_hubspot_flow.py --flow-id 4626124224 [--flow-id ...] [--label before]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

import os  # noqa: E402

DEFAULT_OUT_DIR = ROOT / "config" / "hubspot_flows"

# Portal 22617666 (ap1) — asserted before any call, same discipline as
# scripts/snapshot_hubspot_schema.py / scripts/probe_scoring_recalc_latency.py.
EXPECTED_PORTAL_ID = "22617666"

# HANDOVER-2026-08-06-icp-scoring.md §10.1 — the six company scoring flows this phase
# remediates (four original + two added by 40-04: produces-content, gambling). Module
# constant, no CLI override for the slug mapping (the --flow-id list is the
# operator-facing override surface; slugs stay tied to these known ids).
FLOW_SLUGS = {
    "4626124224": "org-type-score",
    "4626722240": "geography-score",
    "4626722237": "annual-revenue-score",
    "4625147345": "wf1-set-icp-tier",
    "4634822079": "produces-content-score",
    "4634822085": "gambling-score",
}

# PUT is replace-not-merge (40-RESEARCH.md Pitfall 1) — these round-trip poison fields
# are stripped from every archived body before it is ever written to disk.
STRIP_KEYS = ("createdAt", "updatedAt", "dataSources")


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def slug_for(flow_id: str) -> str:
    return FLOW_SLUGS.get(flow_id, flow_id)


def fetch_flow(flow_id: str) -> dict:
    """GET /automation/v4/flows/{flow_id} and strip the PUT round-trip poison fields."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    url = f"{BASE_URL}/automation/v4/flows/{flow_id}"
    r = requests.get(url, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    body = r.json()
    for key in STRIP_KEYS:
        body.pop(key, None)
    return body


def archive_flow(flow_id: str, label: str, out_dir: Path) -> Path:
    body = fetch_flow(flow_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{flow_id}-{slug_for(flow_id)}.{label}.json"
    with path.open("w") as f:
        json.dump(body, f, indent=2, sort_keys=True)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow-id", action="append", default=None,
                         help="Flow id to fetch and archive. Repeatable. Defaults to all "
                              "four FLOW_SLUGS entries if omitted.")
    parser.add_argument("--label", default="before",
                         help="Snapshot label used in the output filename (before/after).")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                         help="Directory to write archived flow JSON into.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to fetch "
              "live flow definitions.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    flow_ids = args.flow_id or list(FLOW_SLUGS.keys())
    out_dir = Path(args.out_dir)

    for flow_id in flow_ids:
        path = archive_flow(flow_id, args.label, out_dir)
        print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
