#!/usr/bin/env python3
"""scripts/run_scoring_parity.py

Phase 40 Plan 02 (D-11/D-12) — the read-only scheduled parity tier. Recomputes the
oracle's opinion (src/icp_scoring.compute_icp_score, via tests/scoring_fixtures.py's
shared expected_for/fetch_for_parity) for a sample of real companies and compares it
against HubSpot's live lv_icp_fit_score / lv_icp_tier / lv_anti_icp_flag.

Read-only by default. GET and search calls only, UNLESS the operator explicitly passes
--write-breakdown (Phase 43 Plan 02, D-01), which patches exactly one property
(lv_icp_score_breakdown) on each company this invocation successfully compared -- no
create-record or delete-record call exists anywhere in this file, live or otherwise, so
even the flagged path cannot create or destroy a record. Phase 40 D-12's scheduled
unattended pass never passes --write-breakdown and therefore never writes; that
guarantee, not the absence of a patch import, is what keeps the standing sweep safe to
run unattended on a cadence. The on-demand full fixture tier (tests/test_scoring_parity.py's
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

from src.hubspot_client import patch_record  # noqa: E402
from tests.scoring_fixtures import expected_for, fetch_for_parity  # noqa: E402

DEFAULT_REPORT_DIR = ROOT / ".planning" / "phases" / "40-scoring-engine-remediation-notes"

# Portal 22617666 (ap1) — asserted before any network call, same discipline as
# scripts/snapshot_hubspot_schema.py / scripts/probe_scoring_recalc_latency.py /
# tests/scoring_fixtures.py.
EXPECTED_PORTAL_ID = "22617666"

RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"

# D-02: the HubSpot property limit this serializer's shedding budget is set against
# (config/hubspot_properties.yaml: lv_icp_score_breakdown is `type: string,
# fieldType: textarea`, 60k chars).
BREAKDOWN_PROPERTY_LIMIT = 60000

# Shed 2's bound on each individual hard-veto reason string, once shedding component
# detail alone wasn't enough.
_HARD_VETO_REASON_MAX_LEN = 120


def serialize_breakdown(result) -> str:
    """D-02: serialize an ICPScoreResult's breakdown into a string that always fits
    BREAKDOWN_PROPERTY_LIMIT and always parses as JSON -- never a byte slice through the
    middle of the assembled string (the rejected src/merge_policy.py anti-pattern, C4).

    `breakdown` (src/icp_scoring.py) carries no `total` key -- the score lives only on
    the sibling `result.score` -- so it is added here on every path, including the
    shed/fallback ones.

    Shed order when over budget: (1) drop each component's `value`, keep `signal` and
    `points`; (2) bound each hard_vetoes reason string's length; (3) pathological
    fallback -- keep only version/total/counts, still valid JSON, still carries the
    total. `truncated` is stamped True only on a path that actually shed something.
    """
    breakdown = result.breakdown
    version = breakdown.get("version")
    total = result.score
    graduated_deductions = breakdown.get("graduated_deductions", [])
    hard_vetoes = list(breakdown.get("hard_vetoes", []))
    components = breakdown.get("components", [])

    def _dump(components_, hard_vetoes_, truncated):
        return json.dumps({
            "version": version,
            "components": components_,
            "hard_vetoes": hard_vetoes_,
            "graduated_deductions": graduated_deductions,
            "total": total,
            "truncated": truncated,
        })

    text = _dump(components, hard_vetoes, False)
    if len(text) <= BREAKDOWN_PROPERTY_LIMIT:
        return text

    # Shed 1: drop each component's `value` (the detail); keep `signal` and `points`.
    stripped_components = [
        {"signal": c.get("signal"), "points": c.get("points")} for c in components
    ]
    text = _dump(stripped_components, hard_vetoes, True)
    if len(text) <= BREAKDOWN_PROPERTY_LIMIT:
        return text

    # Shed 2: bound each hard-veto reason string's length.
    bounded_vetoes = [
        v[:_HARD_VETO_REASON_MAX_LEN] if isinstance(v, str) else v
        for v in hard_vetoes
    ]
    text = _dump(stripped_components, bounded_vetoes, True)
    if len(text) <= BREAKDOWN_PROPERTY_LIMIT:
        return text

    # Shed 3: pathological volume (e.g. thousands of components/vetoes) -- keep only
    # counts. Still valid JSON, still carries version + total, never a slice.
    return json.dumps({
        "version": version,
        "components": [],
        "components_count": len(components),
        "hard_vetoes": [],
        "hard_vetoes_count": len(hard_vetoes),
        "graduated_deductions": [],
        "total": total,
        "truncated": True,
    })


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


def _find_blank_score_with_inputs() -> list:
    """Phase 41 task #3, option 4 — the detector for the failure class that shipped as
    success.

    `_select_sample_ids()` searches HAS_PROPERTY on lv_icp_fit_score, so a company whose
    score is BLANK is invisible to the entire comparison above. That is exactly how 63 of
    66 records went unscored through a full phase and the sweep still reported PASS: the
    harness only ever looked at records that had a score.

    This searches the complement — a company that HAS `org_type_score` (so the pipeline
    has run on it and it is meant to be scored) but has NO `lv_icp_fit_score`. Under the
    null-safe formula that set is empty; a non-empty result means the score is blanking
    again, whatever the mechanism. Findings are real, never a documented divergence.

    Returns a list of company ids. Search failures propagate — a detector that silently
    returns [] on error is the same false green it exists to prevent (D-13).
    """
    from src.hubspot_client import search_records

    result = search_records(
        "companies",
        [
            {"propertyName": "org_type_score", "operator": "HAS_PROPERTY"},
            {"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"},
        ],
        ["name", "org_type_score"],
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


def _require_provenance() -> bool:
    """Phase 41 Plan 02 Task 2: exact-'true' semantics, same as every other env kill
    switch in this repo. Unset (the standing unattended sweep's default) means missing
    provenance is recorded but never a real_finding -- records this sweep has never run
    through the pipeline legitimately have none."""
    return os.getenv("PARITY_REQUIRE_PROVENANCE") == "true"


def _provenance_check(props: dict) -> dict:
    """Presence/shape assertion for the single `lv_enrichment_provenance` JSON blob
    (n8n/code/mergeCompanies.js's provenance model: one object keyed by field, each entry
    carrying at least `source`) -- not the per-field `*_source`/`*_confidence` properties
    CLAUDE.md's superseded local-MVP design describes."""
    raw = props.get("lv_enrichment_provenance")
    present = bool(raw)
    valid_json = False
    fields = []
    sources = []

    if present:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            valid_json = True
            fields = sorted(parsed.keys())
            sources = sorted({
                entry.get("source")
                for entry in parsed.values()
                if isinstance(entry, dict) and entry.get("source")
            })

    return {"present": present, "valid_json": valid_json, "fields": fields, "sources": sources}


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


def build_report(sample_ids, fetch_fn=fetch_for_parity, write_breakdown=False,
                 write_fn=patch_record, blank_score_ids=None):
    """The comparison core, offline-testable with an empty sample_ids or a stubbed
    fetch_fn — no network call is reachable when sample_ids is empty. `write_breakdown`
    defaults to False (D-01): with it off, `write_fn` is never called, proving the
    standing unattended sweep stays read-only regardless of what `write_fn` is. With it
    on, `write_fn` is called once per company this invocation successfully compared
    (D-03 -- never a company whose fetch raised, never a portfolio backfill).

    `blank_score_ids` carries _find_blank_score_with_inputs()'s result. `None` means the
    detector did not run (offline/unit callers); `[]` means it ran and found nothing, which
    is itself one executed assertion. Any id in it is a real finding — a company the
    pipeline has scored components for whose lv_icp_fit_score is blank is the exact
    condition that swallowed 63 records in Phase 41 while the sweep reported PASS.

    Returns (report_dict, exit_code)."""
    comparisons = []
    mismatches = []
    real_findings = []
    breakdowns_written = 0
    detector_ran = blank_score_ids is not None
    blank_score_ids = list(blank_score_ids or [])

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

        # Phase 41 Plan 02 Task 2: recorded on every comparison (DATA-01's "provenance
        # stamped" bar needs this to be measured, not spot-checked) but only becomes a
        # real_finding when a caller explicitly demands it via PARITY_REQUIRE_PROVENANCE
        # -- the standing unattended sweep runs over records this phase never touches,
        # which legitimately carry no provenance, and must keep passing by default.
        record["provenance"] = _provenance_check(props)
        record["needs_review"] = props.get("lv_enrichment_needs_review")
        record["review_reason"] = props.get("lv_enrichment_review_reason")
        if _require_provenance() and not record["provenance"]["valid_json"]:
            real_findings.append({**record, "classification": "provenance_missing"})

        comparisons.append(record)

        # D-01/D-03: strictly opt-in and confined to the records this invocation
        # successfully compared -- a company whose fetch raised `continue`d above and
        # never reaches here, so it never gets a write. No portfolio backfill exists.
        if write_breakdown:
            write_fn(
                "companies",
                company_id,
                {"lv_icp_score_breakdown": serialize_breakdown(expected)},
                dry_run=False,
            )
            breakdowns_written += 1

    sample_findings = len(real_findings)  # before the detector appends its own
    for company_id in blank_score_ids:
        real_findings.append({
            "company_id": company_id,
            "classification": "has_scoring_inputs_but_no_fit_score",
            "detail": ("org_type_score is set but lv_icp_fit_score is blank -- the "
                       "calculated property is blanking on a null term again."),
        })

    # The detector counts as one executed assertion ("no company has inputs but no
    # score"), so a run whose comparison sample is empty but whose detector ran clean is
    # not mistaken for a run that checked nothing.
    assertions_executed = len(comparisons) + (1 if detector_ran else 0)
    if assertions_executed == 0:
        verdict = (
            "FAIL: zero assertions executed. A sweep that checked nothing must never "
            "report success (D-13) -- empty sample, missing credentials, portal "
            "mismatch, or every read raised."
        )
        exit_code = 1
    elif real_findings:
        verdict = (
            f"FAIL: {sample_findings} of {len(sample_ids)} sampled companies "
            "diverge from the oracle or could not be checked (not the documented Needs "
            "Review divergence)."
        )
        if blank_score_ids:
            verdict += (f" [detector: {len(blank_score_ids)} compan(ies) have scoring "
                        "inputs but a blank lv_icp_fit_score]")
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

    if write_breakdown:
        verdict += f" [--write-breakdown: wrote lv_icp_score_breakdown to {breakdowns_written} companies]"

    report = {
        "rubric_version": _rubric_version(),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "sample_ids": list(sample_ids),
        "blank_score_detector_ran": detector_ran,
        "blank_score_ids": blank_score_ids,
        "comparisons": comparisons,
        "mismatches": mismatches,
        "real_findings": real_findings,
        "assertions_executed": assertions_executed,
        "breakdowns_written": breakdowns_written,
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
    parser.add_argument(
        "--write-breakdown",
        action="store_true",
        default=False,
        help=(
            "Opt-in (D-01): also write lv_icp_score_breakdown to every company this "
            "invocation successfully compares. Off by default -- the standing "
            "unattended sweep (Phase 40 D-12) never passes this flag and therefore "
            "never writes."
        ),
    )
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run "
              "this parity sweep.")
        report, exit_code = build_report([], write_breakdown=args.write_breakdown)
        path = _write_report(report)
        print(f"wrote {path}")
        return exit_code

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        report, exit_code = build_report([], write_breakdown=args.write_breakdown)
        path = _write_report(report)
        print(f"wrote {path}")
        return 1

    sample_ids = _select_sample_ids()
    blank_score_ids = _find_blank_score_with_inputs()
    report, exit_code = build_report(sample_ids, write_breakdown=args.write_breakdown,
                                     blank_score_ids=blank_score_ids)
    path = _write_report(report)
    print(f"wrote {path}")
    print(report["verdict"])
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
