#!/usr/bin/env python3
"""scripts/apply_fit_score_formula.py

Sync the live `lv_icp_fit_score` calculation_equation to the formula archived in
`config/hubspot_flows/lv_icp_fit_score-property.after.json`. The archive is the source of
truth; this script only pushes it. tests/test_flow_rubric_conformance.py guards the
archive's shape, so reverting the fix in the repo fails the suite, and re-running this
script is how the portal is brought back into line after any drift.

Why the formula is what it is (Phase 41, task #3):
    HubSpot blanks a calculated property entirely when ANY referenced term is null. The
    research prompt correctly answers null for `gambling_score` unless a source supports
    it, so ~95% of companies had a null term and therefore NO SCORE AT ALL. Spike evidence:
    .planning/phases/41-validation-data-import-end-to-end-proof/41-FORMULA-SPIKE.md.

    `org_type_score` is deliberately left UNGUARDED. It is the sentinel for "this record has
    been through the pipeline" — the org-type mapper writes it for every enriched company
    (`unknown` maps to 0 in the rubric, so it is never skipped). Guarding it too would make
    all 646 never-enriched companies compute to 0, which enrolls every one of them in the
    tier flow. Blank must keep meaning "never scored".

Write gate (repo idiom, exact-'true'): ALLOW_FORMULA_WRITE=true. Without it this prints the
PATCH it would make and exits 0 — no network write.

    .venv/bin/python scripts/apply_fit_score_formula.py                     # dry run
    ALLOW_FORMULA_WRITE=true .venv/bin/python scripts/apply_fit_score_formula.py

Phase 50 Plan 01 (D-14): generalized with a `--property NAME` flag, defaulting to
`lv_icp_fit_score` so the invocation above keeps working byte-for-byte. Both the archive
path (`config/hubspot_flows/{NAME}-property.after.json`) and the property URL are derived
from `--property`, so `--property lv_icp_tier_derived` is the repeatable path back into
line if that property's live formula ever drifts from its archived source of truth.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv()

from src.hubspot_client import hs_headers  # noqa: E402

EXPECTED_PORTAL_ID = "22617666"
DEFAULT_PROPERTY = "lv_icp_fit_score"


def archive_path(property_name: str) -> Path:
    return ROOT / "config" / "hubspot_flows" / f"{property_name}-property.after.json"


def property_url(property_name: str) -> str:
    return f"https://api.hubapi.com/crm/v3/properties/companies/{property_name}"


def archived_formula(archive: Path) -> str:
    with archive.open() as f:
        return json.load(f)["calculationFormula"]


def live_formula(url: str) -> str:
    r = requests.get(url, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("calculationFormula")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--property", default=DEFAULT_PROPERTY,
                         help=f"Company property name to sync (default: {DEFAULT_PROPERTY}).")
    args = parser.parse_args(argv)

    archive = archive_path(args.property)
    url = property_url(args.property)

    if not os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"):
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set.")
        return 1
    if os.getenv("HUBSPOT_PORTAL_ID") != EXPECTED_PORTAL_ID:
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match {EXPECTED_PORTAL_ID}. "
              "No API call made.")
        return 1

    want = archived_formula(archive)
    have = live_formula(url)
    print(f"archived: {want}")
    print(f"live    : {have}")
    if have == want:
        print("in sync — nothing to do.")
        return 0

    if os.getenv("ALLOW_FORMULA_WRITE") != "true":
        print("\nDRY RUN (set ALLOW_FORMULA_WRITE=true to apply):")
        print(json.dumps({"method": "PATCH", "url": url,
                          "payload": {"calculationFormula": want}}, indent=2))
        return 0

    r = requests.patch(url, headers=hs_headers(),
                       json={"calculationFormula": want}, timeout=30)
    print(f"PATCH {r.status_code}")
    if r.status_code not in (200, 201, 204):
        print(r.text[:500])
        return 1

    # Independent re-read, not the PATCH's own response body.
    back = live_formula(url)
    ok = back == want
    print(f"verified by re-read: {ok}")
    if not ok:
        print(f"  !! live is now: {back}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
