#!/usr/bin/env python3
"""scripts/measure_research_reproducibility.py

Phase 51 Plan 03 checkpoint round 2 (operator ruling): measure how often
src.web_research.claude_web_research returns a DIFFERENT answer for the SAME company
across repeated live calls, for every GAP_FILL_FIELDS name -- not just lv_produces_content
(the field a raw Run1-vs-Run2 diff happened to catch moving on 2 of 6 companies).

Zero ZoomInfo cost: the companies measured are re-derived via the SAME deterministic
scripts.backfill_dry_run.select_diversified_never_scored_sample() call already used to
build the committed Run 2 predictions (a HubSpot-only search) -- filtered to the ids that
matched in Run 2. No enrich_company() call exists anywhere in this module; ZoomInfo is
never touched.

Also records, per observation, the ProviderResult's own `confidence` and whether
`evidence_by_field` names that field -- CLAUDE.md field_policy.yaml declares
lv_produces_content min_confidence=85/require_evidence_url=True and lv_org_type
min_confidence=80/require_evidence_url_for=[...], neither of which
scripts.backfill_dry_run.apply_research_to_patch currently enforces. Recording both next
to the raw value lets the fix (work item 2, checkpoint round 2) be judged against real
correlation, not assumed.

Read-only throughout: no HubSpot write, no ZoomInfo call, no n8n execution.

`.env` is Read/Bash permission-blocked this session -- operator invocation:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import os; \
         os.environ['USE_MOCK_WEB_RESEARCH'] = 'false'; import runpy; \
         runpy.run_path('scripts/measure_research_reproducibility.py', run_name='__main__')"
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.schemas import HubSpotRecord  # noqa: E402
from src.web_research import claude_web_research  # noqa: E402
from scripts.backfill_dry_run import (  # noqa: E402
    EXPECTED_PORTAL_ID,
    GAP_FILL_FIELDS,
    select_diversified_never_scored_sample,
)

DEFAULT_REPETITIONS = 3  # 3 fresh live calls per company; combined with the 2 already
                          # committed (Run 1 + Run 2) that is 5 observations per company.

# The two companies neither Run 1 nor Run 2 could ZoomInfo-match -- excluded, there is no
# research call for an unmatched record (D-04: no whole-record research rescue).
UNMATCHED_IDS = {"9604726292", "9604623716"}


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")) and bool(os.getenv("ANTHROPIC_API_KEY"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def matched_companies() -> list:
    """Re-derives the exact Run 2 sample (zero ZoomInfo cost -- pure HubSpot search) and
    returns the matched (non-skipped) company dicts."""
    sample = select_diversified_never_scored_sample(10, media_slots=5)
    return [c for c in sample if c["id"] not in UNMATCHED_IDS]


def _record_for(company: dict) -> HubSpotRecord:
    return HubSpotRecord(
        object_type="companies",
        id=company["id"],
        properties={
            "name": company.get("name"),
            "domain": company.get("domain"),
            "website": company.get("website"),
            "country": company.get("country"),
            "industry": company.get("industry"),
        },
    )


def _observation(research_result) -> dict:
    """One repetition's raw answer for every GAP_FILL_FIELDS name, plus the result's own
    confidence and whether evidence_by_field names that field -- kept RAW (never passed
    through normalize_org_type/apply_research_to_patch's bool coercion) so a genuine model
    disagreement is visible, not masked by post-processing."""
    data = getattr(research_result, "data", None)
    data = data if isinstance(data, dict) else {}
    confidence = getattr(research_result, "confidence", None)
    evidence_by_field = getattr(research_result, "evidence_by_field", None) or {}
    return {
        "confidence": confidence,
        "fields": {
            field: {
                "value": data.get(field),
                "has_evidence_url": field in evidence_by_field,
            }
            for field in GAP_FILL_FIELDS
        },
    }


def measure(companies: list, repetitions: int = DEFAULT_REPETITIONS) -> dict:
    # company_id -> field -> [observation dicts]
    observations = defaultdict(lambda: defaultdict(list))
    calls_made = 0

    for _ in range(repetitions):
        for company in companies:
            result = claude_web_research(_record_for(company))
            calls_made += 1
            obs = _observation(result)
            for field in GAP_FILL_FIELDS:
                observations[company["id"]][field].append({
                    "value": obs["fields"][field]["value"],
                    "has_evidence_url": obs["fields"][field]["has_evidence_url"],
                    "confidence": obs["confidence"],
                })

    per_field_flip_counts = {field: 0 for field in GAP_FILL_FIELDS}
    per_company = {}
    for company in companies:
        cid = company["id"]
        per_company[cid] = {"name": company.get("name"), "fields": {}}
        for field in GAP_FILL_FIELDS:
            obs_list = observations[cid][field]
            distinct_values = {o["value"] for o in obs_list}
            flipped = len(distinct_values) > 1
            per_company[cid]["fields"][field] = {
                "observations": obs_list,
                "distinct_values": sorted(distinct_values, key=str),
                "flipped": flipped,
            }
            if flipped:
                per_field_flip_counts[field] += 1

    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "portal_id_verified": EXPECTED_PORTAL_ID,
        "repetitions": repetitions,
        "companies_measured": len(companies),
        "anthropic_calls_made": calls_made,
        "gap_fill_fields": GAP_FILL_FIELDS,
        "per_field_flip_counts": per_field_flip_counts,
        "per_company": per_company,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS,
                         help=f"Fresh live research calls per company (default {DEFAULT_REPETITIONS}).")
    parser.add_argument("--out", default=None, help="Path to write the measurement JSON to.")
    parser.add_argument("--label", default="before",
                         help="Label stamped into the artifact ('before' or 'after' the "
                              "work-item-2 fix) so both measurements can share one file.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN and ANTHROPIC_API_KEY "
              "must both be set to run.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    companies = matched_companies()
    result = measure(companies, repetitions=args.repetitions)
    result["label"] = args.label

    print(json.dumps({"label": result["label"],
                       "per_field_flip_counts": result["per_field_flip_counts"],
                       "anthropic_calls_made": result["anthropic_calls_made"]}, indent=2))

    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
