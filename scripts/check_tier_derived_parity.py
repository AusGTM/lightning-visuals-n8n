#!/usr/bin/env python3
"""scripts/check_tier_derived_parity.py

Phase 50 Plan 01 (D-07's gate, D-17 item 4's evidence renderer) -- read-only comparator
between the old `lv_icp_tier` enum and the new `lv_icp_tier_derived` calculated property.
Never issues a write of any kind (no `requests.{post,patch,delete}` call anywhere in this
module) -- this is D-16's zero-company-write-window guarantee for the whole comparison
half of the phase.

Re-derives the scored population live on every invocation via
scripts/rescore_population.py::select_scored_population() (the same
`HAS_PROPERTY(lv_icp_fit_score)` search shape run_scoring_parity.py /
simulate_rubric_weights.py already share) -- never trusts a stale local snapshot. `--ids`
restricts the run to named records (the tracer task's own use).

The 4 known stuck records (WINDOWS.md ids 9-12) are the ONE class of expected mismatch:
`lv_icp_tier` stuck at "C" while `lv_icp_tier_derived` correctly reads "B". Any other
divergence is a defect, not a rounding difference.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['check_tier_derived_parity.py', '--out', 'PATH/TO/report.md']; \
         runpy.run_path('scripts/check_tier_derived_parity.py', run_name='__main__')"

Usage:
    python scripts/check_tier_derived_parity.py [--ids ID1,ID2,...] [--out PATH]
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# WINDOWS.md ids 9-12 -- the 4 stuck records, hard-coded per the plan (RESEARCH.md Code
# Examples): score already correct at 45, tier stuck at "C" instead of "B".
KNOWN_STUCK_IDS = frozenset({
    "9605273630", "9604738976", "17696004613", "19100977027",
})

FETCH_PROPS = ["name", "lv_icp_tier", "lv_icp_tier_derived", "lv_icp_fit_score", "lv_anti_icp_flag"]


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _id_sort_key(rid: str):
    # Same numeric-first sort as scripts/build_rescore_report.py::_id_sort_key -- keeps
    # rendering deterministic for real HubSpot ids and any non-digit fixture id alike.
    return (0, int(rid)) if rid.isdigit() else (1, rid)


# --- pure functions pinned by tests/test_tier_derived_tools.py -------------------------

def classify_row(record_id, live_tier, derived_tier, known_stuck_ids) -> str:
    """"expected_mismatch" only for a known stuck id whose live tier is "C" and derived
    tier is "B" -- the one class D-07's gate accepts. A known stuck id landing anywhere
    else (including a live-tier match) is a "defect": the fix the phase exists to prove
    did not happen. Any other id: "match" when the two tiers agree, "defect" otherwise."""
    if record_id in known_stuck_ids:
        if live_tier == "C" and derived_tier == "B":
            return "expected_mismatch"
        return "defect"
    return "match" if live_tier == derived_tier else "defect"


def render_parity_markdown(rows, population_count) -> str:
    """Pure function of (rows, population_count) -- called twice on the same inputs
    returns byte-identical strings. Raises on an empty population (never renders "zero
    mismatches" as a clean pass for nothing) and raises when the row count and the
    recorded population count disagree."""
    if population_count <= 0:
        raise ValueError(
            f"population_count is {population_count}; refusing to render an empty parity "
            "report as a clean pass"
        )
    if len(rows) != population_count:
        raise ValueError(
            f"row count ({len(rows)}) does not match the recorded population_count "
            f"({population_count})"
        )

    ordered = sorted(rows, key=lambda r: _id_sort_key(r["record_id"]))
    match = sum(1 for r in ordered if r["classification"] == "match")
    expected_mismatch = sum(1 for r in ordered if r["classification"] == "expected_mismatch")
    defect = sum(1 for r in ordered if r["classification"] == "defect")

    lines = [
        "# lv_icp_tier vs lv_icp_tier_derived -- Parity Report",
        "",
        f"- population: {population_count}",
        f"- match: {match}",
        f"- expected_mismatch: {expected_mismatch}",
        f"- defect: {defect}",
        "",
        "| Record ID | Name | lv_icp_tier | lv_icp_tier_derived | Fit Score | Anti-ICP Flag | Classification |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ordered:
        lines.append(
            f"| {r['record_id']} | {r.get('name') or '(name unavailable)'} | "
            f"{r['live_tier']} | {r['derived_tier']} | {r.get('fit_score')} | "
            f"{r.get('anti_icp_flag')} | {r['classification']} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_rows(records, known_stuck_ids=KNOWN_STUCK_IDS) -> list:
    rows = []
    for r in records:
        rid = r["id"]
        live_tier = r.get("lv_icp_tier")
        derived = r.get("lv_icp_tier_derived")
        rows.append({
            "record_id": rid,
            "name": r.get("name"),
            "live_tier": live_tier,
            "derived_tier": derived,
            "fit_score": r.get("lv_icp_fit_score"),
            "anti_icp_flag": r.get("lv_anti_icp_flag"),
            "classification": classify_row(rid, live_tier, derived, known_stuck_ids),
        })
    return rows


# --- live reads (read-only; D-16) -------------------------------------------------------

def _fetch_records(ids: list) -> list:
    from src.hubspot_client import get_record
    return [{"id": i, **get_record("companies", i, FETCH_PROPS)["properties"]} for i in ids]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", default=None,
                         help="Comma-separated company ids; restricts the run instead of "
                              "re-deriving the full live scored population.")
    parser.add_argument("--out", default=None,
                         help="Path to write the markdown report to. Defaults to stdout.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "parity check.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    from scripts.rescore_population import select_scored_population

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    else:
        ids = select_scored_population()

    if not ids:
        print("REFUSED: no ids to check (empty --ids or empty live population).")
        return 1

    records = _fetch_records(ids)
    rows = build_rows(records)
    text = render_parity_markdown(rows, len(rows))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        print(f"wrote {out_path}")
    else:
        print(text)

    defects = [r for r in rows if r["classification"] == "defect"]
    expected = [r for r in rows if r["classification"] == "expected_mismatch"]
    print(f"population={len(rows)} match={len(rows) - len(defects) - len(expected)} "
          f"expected_mismatch={len(expected)} defect={len(defects)}")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
