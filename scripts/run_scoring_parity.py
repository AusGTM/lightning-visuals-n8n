#!/usr/bin/env python3
"""scripts/run_scoring_parity.py

Phase 40 Plan 02 (D-11/D-12) — the read-only scheduled parity tier. Recomputes the
oracle's opinion (src/icp_scoring.compute_icp_score, via tests/scoring_fixtures.py's
shared expected_for/fetch_for_parity) for a sample of real companies and compares it
against HubSpot's live lv_icp_fit_score / lv_icp_tier / lv_anti_icp_flag.

Read-only. GET and search calls only — this script never creates, patches, or deletes a
company (T-40-06's structural mitigation: no create-record, patch-record, delete-record,
or disposable-company helper is imported anywhere in this file). That is what makes it safe to run
unattended on a cadence; the on-demand full fixture tier (tests/test_scoring_parity.py's
`live` tier, RUN_LIVE_PARITY=true) is the create/exercise/delete tier and stays separate.

The false-green guard is the point of this script, not a nicety (T-40-05). If
`assertions_executed` is 0 — empty sample, missing credentials, portal mismatch, search
returned nothing, every read raised — the script exits non-zero with an explicit
"zero assertions executed" verdict in the written report. A sweep that checked nothing
must never look like a sweep that found nothing wrong (D-13).

Env vars:
    PARITY_SAMPLE_IDS  Comma-separated real company ids to check. If unset, ids are
                        selected via a HAS_PROPERTY search on lv_icp_fit_score.
    PARITY_REPORT_DIR  Directory the JSON verdict report is written to. Defaults to
                        .planning/phases/40-scoring-engine-remediation-notes/.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/run_scoring_parity.py', run_name='__main__')"
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`tests.*` imports resolve

import yaml  # noqa: E402

from tests.scoring_fixtures import expected_for, fetch_for_parity  # noqa: E402

DEFAULT_REPORT_DIR = ROOT / ".planning" / "phases" / "40-scoring-engine-remediation-notes"

# Portal 22617666 (ap1) — asserted before any network call, same discipline as
# scripts/snapshot_hubspot_schema.py / scripts/probe_scoring_recalc_latency.py /
# tests/scoring_fixtures.py.
EXPECTED_PORTAL_ID = "22617666"

RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _rubric_version() -> str:
    with RUBRIC_PATH.open() as f:
        return yaml.safe_load(f).get("version", "unknown")


def _select_sample_ids() -> list:
    """PARITY_SAMPLE_IDS if set, else a HAS_PROPERTY search on lv_icp_fit_score. This is
    the only place this script touches search_records — imported locally so a pure-unit
    call to build_report() never needs src.hubspot_client at all."""
    env_ids = os.getenv("PARITY_SAMPLE_IDS", "")
    if env_ids.strip():
        return [i.strip() for i in env_ids.split(",") if i.strip()]

    from src.hubspot_client import search_records

    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
        ["lv_icp_fit_score"],
        limit=100,
    )
    return [r["id"] for r in result.get("results", [])]


def _flag_matches(live_value, expected_flag: bool) -> bool:
    """Phase 40-07 (Rule 1 -- bug fix, third instance of the same defect class 40-05 and
    40-06 each fixed once in tests/test_scoring_parity.py's live pytest assertions): since
    D-01's veto handover, no HubSpot workflow writes lv_anti_icp_flag -- only the n8n
    pipeline does. A real company this sweep has never run through the pipeline reads
    None, not the string "false". A literal string-equality comparison against
    str(expected_flag).lower() therefore reports a mismatch on every never-enriched
    record, which is not what "diverges from the oracle" should mean. Compare boolean
    equivalence instead: anything other than the literal string "true" is treated as
    False, matching the pytest module's own `!= "true"` correction pattern."""
    return (str(live_value) == "true") == expected_flag


def _classify_mismatch(live_triple: dict, expected_triple: dict, expected_result) -> str:
    """PARITY-01/Task 3: the oracle's documented `Needs Review` divergence (40-02's
    flagged assumption, restated in this module's own header) -- compute_icp_score
    downgrades tier to 'Needs Review' when lv_org_type is unknown or lv_produces_content
    is null and no veto fired, with score >= 15. HubSpot's live lv_icp_tier enum has no
    'Needs Review' value (only A/B/C/D/Unscored) -- WF1 grades strictly off the numeric
    score+veto ladder, so a live tier of A/B/C/D against an oracle 'Needs Review' is an
    accepted, documented divergence, not a defect -- PROVIDED the score and veto state
    themselves agree. Any other disagreement (score itself diverges, or veto state
    itself diverges) is a real finding, never silently absorbed into this classification."""
    if expected_triple["lv_icp_tier"] != "Needs Review":
        return "real_finding"
    if str(live_triple.get("lv_icp_fit_score")) != expected_triple["lv_icp_fit_score"]:
        return "real_finding"
    if not _flag_matches(live_triple.get("lv_anti_icp_flag"), expected_result.anti_icp_flag):
        return "real_finding"
    return "documented_needs_review_divergence"


def build_report(sample_ids, fetch_fn=fetch_for_parity):
    """The comparison core, offline-testable with an empty sample_ids or a stubbed
    fetch_fn — no network call is reachable when sample_ids is empty. Returns
    (report_dict, exit_code)."""
    comparisons = []
    mismatches = []
    real_findings = []

    for company_id in sample_ids:
        try:
            props = fetch_fn(company_id)
        except Exception as exc:  # noqa: BLE001 -- one bad record must not sink the sweep
            mismatches.append({"company_id": company_id, "error": str(exc)})
            real_findings.append({"company_id": company_id, "error": str(exc)})
            continue

        expected = expected_for(props)
        live_triple = {
            "lv_icp_fit_score": props.get("lv_icp_fit_score"),
            "lv_icp_tier": props.get("lv_icp_tier"),
            "lv_anti_icp_flag": props.get("lv_anti_icp_flag"),
        }
        expected_triple = {
            "lv_icp_fit_score": str(expected.score),
            "lv_icp_tier": str(expected.tier),
            "lv_anti_icp_flag": str(expected.anti_icp_flag).lower(),
        }
        # HubSpot returns every property as a string; coerce score/tier before comparing.
        # The flag uses boolean-equivalence comparison (_flag_matches), not string
        # equality -- see its docstring for why.
        score_match = str(live_triple["lv_icp_fit_score"]) == expected_triple["lv_icp_fit_score"]
        tier_match = str(live_triple["lv_icp_tier"]) == expected_triple["lv_icp_tier"]
        flag_match = _flag_matches(live_triple["lv_anti_icp_flag"], expected.anti_icp_flag)
        match = score_match and tier_match and flag_match
        record = {
            "company_id": company_id,
            "live": live_triple,
            "expected": expected_triple,
            "match": match,
        }
        if not match:
            record["classification"] = _classify_mismatch(live_triple, expected_triple, expected)
            if record["classification"] != "documented_needs_review_divergence":
                real_findings.append(record)
            mismatches.append(record)
        comparisons.append(record)

    assertions_executed = len(comparisons)
    if assertions_executed == 0:
        verdict = (
            "FAIL: zero assertions executed. A sweep that checked nothing must never "
            "report success (D-13) -- empty sample, missing credentials, portal "
            "mismatch, or every read raised."
        )
        exit_code = 1
    elif real_findings:
        verdict = (
            f"FAIL: {len(real_findings)} of {assertions_executed} sampled companies "
            "diverge from the oracle with a real finding (not the documented Needs "
            "Review divergence)."
        )
        exit_code = 1
    elif mismatches:
        verdict = (
            f"PASS (with {len(mismatches)} documented Needs Review divergence(s)): "
            f"{assertions_executed} sampled companies checked, every mismatch is the "
            "accepted oracle-vs-live-enum divergence (40-02), zero real findings."
        )
        exit_code = 0
    else:
        verdict = f"PASS: {assertions_executed} sampled companies match the oracle."
        exit_code = 0

    report = {
        "rubric_version": _rubric_version(),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "sample_ids": list(sample_ids),
        "comparisons": comparisons,
        "mismatches": mismatches,
        "real_findings": real_findings,
        "assertions_executed": assertions_executed,
        "verdict": verdict,
    }
    return report, exit_code


def _write_report(report: dict) -> Path:
    report_dir = Path(os.getenv("PARITY_REPORT_DIR", str(DEFAULT_REPORT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = report_dir / f"parity-report-{date_stamp}.json"
    with path.open("w") as f:
        json.dump(report, f, indent=2, default=str)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run "
              "this parity sweep.")
        report, exit_code = build_report([])
        path = _write_report(report)
        print(f"wrote {path}")
        return exit_code

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        report, exit_code = build_report([])
        path = _write_report(report)
        print(f"wrote {path}")
        return 1

    sample_ids = _select_sample_ids()
    report, exit_code = build_report(sample_ids)
    path = _write_report(report)
    print(f"wrote {path}")
    print(report["verdict"])
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
