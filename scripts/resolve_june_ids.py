#!/usr/bin/env python3
"""scripts/resolve_june_ids.py

Phase 41 Plan 02 Task 1 (D-09) — read-only pre-flight resolver for the 66 June-era
HubSpot company ids recorded in config/june_candidates.json's `rows` object (built by
scripts/build_june_candidates.py, Plan 01).

For each June id:
  - GET the record. If it still exists, outcome is `live`.
  - On a 404, re-match by domain (a best-effort guess derived from the candidate row's
    evidence URLs — the June source snapshot carries no explicit domain field), then by
    name (from the committed config/june_candidates_source.json snapshot). A search
    returning exactly one result is a `rematched` outcome; two or more is `ambiguous`;
    zero from both searches is `unmatched`. Both `ambiguous` and `unmatched` are excluded
    from the resolved id list but recorded, never silently dropped (D-09/T-41-10).

Read-only by construction: no write primitive (record PATCH/create/delete/batch-update
helper) is imported anywhere in this file.

Refuses before any network call without HUBSPOT_PRIVATE_APP_TOKEN, or against any portal
other than the hard-coded expected one (no env override — the same WR-01 discipline
scripts/run_scoring_parity.py and tests/scoring_fixtures.py already use).

Writes .planning/phases/41-validation-data-import-end-to-end-proof/41-id-resolution.json
and prints the comma-joined resolved id list on the final stdout line so the operator can
paste it straight into the arm command.

The false-green guard is the point of the empty-input check, not a nicety (same
discipline as scripts/run_scoring_parity.py, D-13): a run that examined zero records must
never write a report that looks like a clean sweep.

`.env` is Read/Bash permission-blocked in this session — the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/resolve_june_ids.py', run_name='__main__')"
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

import requests  # noqa: E402

from src.hubspot_client import get_record, search_records  # noqa: E402

CANDIDATES_PATH = ROOT / "config" / "june_candidates.json"
SOURCE_SNAPSHOT_PATH = ROOT / "config" / "june_candidates_source.json"
REPORT_PATH = (
    ROOT / ".planning" / "phases" / "41-validation-data-import-end-to-end-proof"
    / "41-id-resolution.json"
)

# Portal 22617666 (ap1) — hard-coded, no env override. Same discipline as
# scripts/run_scoring_parity.py / tests/scoring_fixtures.py.
EXPECTED_PORTAL_ID = "22617666"

GET_PROPERTIES = [
    "name", "domain", "hs_object_id", "lv_org_type", "lv_icp_fit_score",
    "annualrevenue", "numberofemployees",
]


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _candidate_domain(candidate_row: dict):
    """Best-effort domain guess from the candidate row's per-field evidence URLs
    (41-01's `_evidence`). The June source snapshot carries no explicit domain field at
    all, so this is the only signal available for a domain-first re-match. Returns None
    when no evidence URL is present or none parses to a usable netloc."""
    evidence = (candidate_row or {}).get("_evidence") or {}
    for url in evidence.values():
        if not url:
            continue
        netloc = urlparse(url).netloc
        if netloc:
            return netloc[4:] if netloc.startswith("www.") else netloc
    return None


def _source_name(source_snapshot: dict, june_id: str):
    row = (source_snapshot or {}).get(june_id) or {}
    return row.get("name")


def _search_one(filters):
    """One search call -> ('single', hit) | ('none', None) | ('ambiguous', None)."""
    result = search_records("companies", filters, GET_PROPERTIES)
    results = result.get("results", [])
    if len(results) == 1:
        return "single", results[0]
    if len(results) > 1:
        return "ambiguous", None
    return "none", None


def _fill_from_hit(entry: dict, resolved_id: str, props: dict) -> dict:
    entry["outcome"] = "rematched"
    entry["resolved_id"] = resolved_id
    entry["name"] = props.get("name") or entry["name"]
    entry["domain"] = props.get("domain")
    entry["annualrevenue_present"] = bool(props.get("annualrevenue"))
    entry["numberofemployees_present"] = bool(props.get("numberofemployees"))
    return entry


def _resolve_one(june_id: str, candidate_row: dict, source_snapshot: dict) -> dict:
    """One June id -> a resolution record. Never raises: a non-404 HTTPError at the GET
    call site is caught at the call site and recorded as `unmatched` with the error text
    (matching src/hubspot_client.py's bare-raise_for_status convention, no new exception
    class introduced)."""
    entry = {
        "june_id": june_id,
        "name": _source_name(source_snapshot, june_id),
        "outcome": None,
        "resolved_id": None,
        "domain": None,
        "annualrevenue_present": False,
        "numberofemployees_present": False,
    }

    try:
        record = get_record("companies", june_id, GET_PROPERTIES)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status != 404:
            entry["outcome"] = "unmatched"
            entry["error"] = str(exc)
            return entry
        record = None

    if record is not None:
        props = record.get("properties", {})
        entry["outcome"] = "live"
        entry["resolved_id"] = june_id
        entry["name"] = props.get("name") or entry["name"]
        entry["domain"] = props.get("domain")
        entry["annualrevenue_present"] = bool(props.get("annualrevenue"))
        entry["numberofemployees_present"] = bool(props.get("numberofemployees"))
        return entry

    # 404 -- re-match by domain, then by name (D-09). A search returning more than one
    # result is ambiguous and stops the re-match immediately -- it is never safe to guess
    # among candidates.
    domain = _candidate_domain(candidate_row)
    if domain:
        status, hit = _search_one(
            [{"propertyName": "domain", "operator": "EQ", "value": domain}]
        )
        if status == "ambiguous":
            entry["outcome"] = "ambiguous"
            return entry
        if status == "single":
            return _fill_from_hit(entry, hit.get("id"), hit.get("properties", {}))

    name = entry["name"]
    if name:
        status, hit = _search_one(
            [{"propertyName": "name", "operator": "EQ", "value": name}]
        )
        if status == "ambiguous":
            entry["outcome"] = "ambiguous"
            return entry
        if status == "single":
            return _fill_from_hit(entry, hit.get("id"), hit.get("properties", {}))

    entry["outcome"] = "unmatched"
    return entry


def build_report(rows: dict, source_snapshot: dict, meta: dict):
    """The resolution core, offline-testable with an empty `rows` -- no network path is
    reachable when `rows` is empty. Returns (report_dict, exit_code)."""
    records = []
    resolved_ids = []
    unmatched = []

    for june_id, candidate_row in (rows or {}).items():
        entry = _resolve_one(june_id, candidate_row, source_snapshot or {})
        records.append(entry)
        if entry["outcome"] in ("live", "rematched"):
            resolved_ids.append(entry["resolved_id"])
        else:
            unmatched.append(june_id)

    examined = len(records)
    if examined == 0:
        verdict = (
            "FAIL: zero records examined. Empty rows table, or every id could not be "
            "read -- a run that checked nothing must never look like a clean report."
        )
        exit_code = 1
    elif not resolved_ids:
        verdict = (
            f"FAIL: {examined} records examined, zero resolved (all unmatched or "
            "ambiguous)."
        )
        exit_code = 1
    else:
        verdict = (
            f"PASS: {len(resolved_ids)} of {examined} June ids resolved "
            f"({len(unmatched)} unmatched)."
        )
        exit_code = 0

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": (meta or {}).get("source_sha256"),
        "records": records,
        "resolved_ids": resolved_ids,
        "unmatched": unmatched,
        "verdict": verdict,
    }
    return report, exit_code


def _write_report(report: dict) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w") as f:
        json.dump(report, f, indent=2, default=str)
    return REPORT_PATH


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


def main(argv=None) -> int:
    if not _has_credentials():
        print("REFUSED: HUBSPOT_PRIVATE_APP_TOKEN is not set. No API call made.")
        report, exit_code = build_report({}, {}, {})
        _write_report(report)
        return 1

    if not _portal_ok():
        print(
            f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
            f"({EXPECTED_PORTAL_ID}). No API call made."
        )
        report, exit_code = build_report({}, {}, {})
        _write_report(report)
        return 1

    candidates = _load_json(CANDIDATES_PATH)
    source_snapshot = _load_json(SOURCE_SNAPSHOT_PATH)

    report, exit_code = build_report(
        candidates.get("rows", {}), source_snapshot, candidates.get("_meta", {})
    )
    path = _write_report(report)
    print(f"wrote {path}")
    print(report["verdict"])
    print(",".join(report["resolved_ids"]))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
